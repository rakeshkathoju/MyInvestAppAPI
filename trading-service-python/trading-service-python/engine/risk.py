"""Risk management: position sizing, stop-loss/target derivation, guard rails."""
import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

import config
import market_data
from signals.models import Signal

logger = logging.getLogger(__name__)


@dataclass
class SizedOrder:
    """Result of running a signal through the risk engine."""

    quantity: int
    price: float
    stop_loss: Optional[float]
    target: Optional[float]
    risk_amount: float
    notes: str = ""


def _parse_time(value: str, fallback: time) -> time:
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (AttributeError, ValueError):
        return fallback


def is_market_open(now: Optional[datetime] = None) -> bool:
    """True when NSE cash market is open (weekday, within session hours)."""
    if not config.ENFORCE_MARKET_HOURS:
        return True

    now = now or datetime.now()
    if now.weekday() >= 5:
        return False

    open_at = _parse_time(config.MARKET_OPEN, time(9, 15))
    close_at = _parse_time(config.MARKET_CLOSE, time(15, 30))
    return open_at <= now.time() <= close_at


def derive_levels(action: str, price: float, signal: Signal) -> Tuple[Optional[float], Optional[float]]:
    """Return (stop_loss, target), using signal values when supplied."""
    stop_loss, target = signal.stop_loss, signal.target
    direction = 1 if action == "BUY" else -1

    if stop_loss is None and config.DEFAULT_STOP_LOSS_PCT > 0:
        stop_loss = round(price * (1 - direction * config.DEFAULT_STOP_LOSS_PCT / 100.0), 2)
    if target is None and config.DEFAULT_TARGET_PCT > 0:
        target = round(price * (1 + direction * config.DEFAULT_TARGET_PCT / 100.0), 2)

    # Guard against levels supplied on the wrong side of the entry.
    if stop_loss is not None and direction * (price - stop_loss) <= 0:
        logger.warning("Ignoring invalid stop-loss %s for %s %s", stop_loss, action, price)
        stop_loss = None
    if target is not None and direction * (target - price) <= 0:
        logger.warning("Ignoring invalid target %s for %s %s", target, action, price)
        target = None

    return stop_loss, target


def size_position(
    signal: Signal,
    available_capital: float,
    open_positions: List[Dict[str, Any]],
) -> Tuple[Optional[SizedOrder], Optional[str]]:
    """Convert a signal into a sized order, or explain why it was rejected."""
    action = signal.action

    held_symbols = {p["symbol"] for p in open_positions}
    is_new_exposure = signal.symbol not in held_symbols
    if is_new_exposure and len(open_positions) >= config.MAX_OPEN_POSITIONS:
        return None, (
            f"Max open positions reached ({config.MAX_OPEN_POSITIONS}); "
            f"skipping {signal.symbol}"
        )

    price = signal.price or market_data.get_ltp(signal.symbol, signal.exchange)
    if not price:
        return None, f"No price available for {signal.symbol}"
    price = float(price)

    stop_loss, target = derive_levels(action, price, signal)

    # An explicit quantity from the alert always wins.
    if signal.quantity:
        quantity = int(signal.quantity)
        risk = abs(price - stop_loss) * quantity if stop_loss else 0.0
        return SizedOrder(quantity, price, stop_loss, target, round(risk, 2), "quantity from signal"), None

    if available_capital <= 0:
        return None, "No capital available"

    cap_by_exposure = int((available_capital * config.MAX_POSITION_PCT / 100.0) // price)

    if stop_loss:
        risk_budget = available_capital * config.RISK_PER_TRADE_PCT / 100.0
        per_share_risk = abs(price - stop_loss)
        cap_by_risk = int(risk_budget // per_share_risk) if per_share_risk > 0 else cap_by_exposure
        quantity = min(cap_by_risk, cap_by_exposure)
        note = "risk-based sizing"
    else:
        quantity = cap_by_exposure
        note = "exposure-capped sizing (no stop-loss)"

    if quantity < 1:
        return None, (
            f"Position size below 1 share for {signal.symbol} at {price} "
            f"(available capital {round(available_capital, 2)})"
        )

    risk = abs(price - stop_loss) * quantity if stop_loss else 0.0
    return SizedOrder(quantity, price, stop_loss, target, round(risk, 2), note), None
