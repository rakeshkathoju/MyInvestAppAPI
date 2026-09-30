"""The trade engine: signal in, order out.

Webhooks call :func:`submit`, which persists each signal and returns
immediately. A background worker then applies dedupe, market-hour checks, the
optional AI filter, and risk sizing before handing the order to whichever
broker ``TRADING_MODE`` selects.

This accept-then-process split matters: TradingView times out quickly and a
single Chartink alert can carry dozens of stocks, so no order placement
(which involves a price lookup) may happen on the request thread.
"""
import logging
import queue
import threading
from typing import Any, Dict, List, Optional

import config
import execution
from execution.base import OrderRequest
from signals.models import Signal
from . import ai_filter, risk, signal_store

logger = logging.getLogger(__name__)

_queue: "queue.Queue[Signal]" = queue.Queue(maxsize=1000)
_worker: Optional[threading.Thread] = None
_worker_lock = threading.Lock()
_stop = threading.Event()


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def submit(signals: List[Signal], execute: Optional[bool] = None) -> Dict[str, Any]:
    """Persist signals and queue them for execution. Returns fast."""
    should_execute = config.AUTO_EXECUTE if execute is None else execute
    accepted, skipped = [], []

    for signal in signals:
        if signal_store.is_duplicate(signal):
            signal_store.save(signal, status="duplicate", reject_reason="Duplicate within dedupe window")
            skipped.append({"symbol": signal.symbol, "reason": "duplicate"})
            continue

        signal_store.save(signal, status="queued" if should_execute else "recorded")

        if should_execute:
            try:
                _queue.put_nowait(signal)
            except queue.Full:
                signal_store.update_status(signal.id, "rejected", "Execution queue is full")
                skipped.append({"symbol": signal.symbol, "reason": "queue full"})
                continue

        accepted.append({"id": signal.id, "symbol": signal.symbol, "action": signal.action})

    if should_execute and accepted:
        ensure_worker()

    return {
        "status": "accepted",
        "queued": len(accepted),
        "skipped": len(skipped),
        "execute": should_execute,
        "mode": config.TRADING_MODE,
        "signals": accepted,
        "rejected": skipped,
    }


def process_now(signal: Signal) -> Dict[str, Any]:
    """Run a single signal through the engine synchronously (manual/testing)."""
    if signal.id is None:
        signal_store.save(signal, status="manual")
    return _execute(signal)


def ensure_worker() -> None:
    """Start the background worker if it is not already running."""
    global _worker
    with _worker_lock:
        if _worker and _worker.is_alive():
            return
        _stop.clear()
        _worker = threading.Thread(target=_run, name="trade-engine", daemon=True)
        _worker.start()
        logger.info("Trade engine worker started (mode=%s)", config.TRADING_MODE)


def shutdown(timeout: float = 5.0) -> None:
    _stop.set()
    with _worker_lock:
        if _worker and _worker.is_alive():
            _worker.join(timeout=timeout)


def status() -> Dict[str, Any]:
    broker = execution.get_broker()
    return {
        "mode": config.TRADING_MODE,
        "broker": broker.healthcheck(),
        "live_trading": broker.is_live,
        "auto_execute": config.AUTO_EXECUTE,
        "allow_short": config.ALLOW_SHORT,
        "ai_filter_enabled": config.AI_CONFIRMATION_ENABLED,
        "market_open": risk.is_market_open(),
        "enforce_market_hours": config.ENFORCE_MARKET_HOURS,
        "queue_depth": _queue.qsize(),
        "worker_running": bool(_worker and _worker.is_alive()),
        "risk": {
            "risk_per_trade_pct": config.RISK_PER_TRADE_PCT,
            "max_position_pct": config.MAX_POSITION_PCT,
            "max_open_positions": config.MAX_OPEN_POSITIONS,
            "default_stop_loss_pct": config.DEFAULT_STOP_LOSS_PCT,
            "default_target_pct": config.DEFAULT_TARGET_PCT,
        },
    }


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------
def _run() -> None:
    while not _stop.is_set():
        try:
            signal = _queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            _execute(signal)
        except Exception:  # pragma: no cover - worker must never die
            logger.exception("Trade engine failed on %s", signal.symbol)
            signal_store.update_status(signal.id, "error", "Unhandled engine error")
        finally:
            _queue.task_done()


def _reject(signal: Signal, reason: str) -> Dict[str, Any]:
    logger.info("Signal rejected (%s): %s", signal.symbol, reason)
    signal_store.update_status(signal.id, "rejected", reason)
    return {"status": "rejected", "symbol": signal.symbol, "reason": reason}


def _execute(signal: Signal) -> Dict[str, Any]:
    if not risk.is_market_open():
        return _reject(signal, "Market is closed")

    broker = execution.get_broker()
    positions = broker.get_positions()

    exit_order = _as_exit_order(signal, positions)
    if exit_order is None and signal.action == "SELL" and not config.ALLOW_SHORT:
        return _reject(signal, f"No open position in {signal.symbol} and shorting is disabled")

    if exit_order is not None:
        order = exit_order
    else:
        allowed, reason = ai_filter.confirm(signal)
        if not allowed:
            return _reject(signal, reason or "Blocked by AI filter")

        available = _available_capital(broker)
        sized, error = risk.size_position(signal, available, positions)
        if sized is None:
            return _reject(signal, error or "Risk engine rejected the signal")

        order = OrderRequest(
            symbol=signal.symbol,
            action=signal.action,
            quantity=sized.quantity,
            price=sized.price,
            stop_loss=sized.stop_loss,
            target=sized.target,
            exchange=signal.exchange,
            strategy=signal.strategy,
            signal_id=signal.id,
        )

    result = broker.place_order(order)
    signal_store.update_status(
        signal.id,
        "executed" if result.successful else "rejected",
        None if result.successful else result.message,
    )
    logger.info("[%s] %s %s x%s -> %s", broker.name, order.action, order.symbol,
                order.quantity, result.status)
    return result.to_dict()


def _as_exit_order(signal: Signal, positions: List[Dict[str, Any]]) -> Optional[OrderRequest]:
    """Build a square-off order when the signal closes an existing position."""
    held = next((p for p in positions if p.get("symbol") == signal.symbol), None)
    if not held:
        return None

    quantity = int(held.get("quantity") or 0)
    if quantity == 0:
        return None

    closing_long = quantity > 0 and signal.action == "SELL"
    closing_short = quantity < 0 and signal.action == "BUY"
    if not (closing_long or closing_short):
        return None

    return OrderRequest(
        symbol=signal.symbol,
        action=signal.action,
        quantity=abs(quantity),
        price=signal.price,
        exchange=signal.exchange,
        strategy=signal.strategy or held.get("strategy"),
        signal_id=signal.id,
    )


def _available_capital(broker) -> float:
    """Best-effort free capital for sizing; live brokers report their own."""
    funds = broker.get_funds() or {}
    for key in ("available_capital", "available_margin", "net_available"):
        value = funds.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return float(config.PAPER_STARTING_CAPITAL)
