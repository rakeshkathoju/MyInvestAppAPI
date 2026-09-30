"""Persistence and deduplication for inbound signals."""
import logging
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import config
import db
from signals.models import Signal

logger = logging.getLogger(__name__)

_recent: Dict[Tuple[str, str], datetime] = {}
_memory_log: deque = deque(maxlen=500)
_lock = threading.Lock()
_memory_id = 0


def is_duplicate(signal: Signal) -> bool:
    """True when the same symbol/action fired inside the dedupe window."""
    window = config.SIGNAL_DEDUPE_SECONDS
    if window <= 0:
        return False

    key = (signal.symbol, signal.action)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window)

    with _lock:
        last = _recent.get(key)
        if last and last > cutoff:
            return True
        _recent[key] = now
        for stale_key in [k for k, ts in _recent.items() if ts <= cutoff]:
            _recent.pop(stale_key, None)
    return False


def save(signal: Signal, status: str = "received", reject_reason: Optional[str] = None) -> Optional[int]:
    """Persist a signal and return its id."""
    global _memory_id

    try:
        with db.cursor(commit=True) as cur:
            if cur is not None:
                cur.execute(
                    "INSERT INTO trade_signals "
                    "(source, symbol, action, price, stop_loss, target, quantity, "
                    " strategy, exchange, raw_payload, status, reject_reason) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        signal.source, signal.symbol, signal.action, signal.price,
                        signal.stop_loss, signal.target, signal.quantity, signal.strategy,
                        signal.exchange, signal.raw_payload, status, reject_reason,
                    ),
                )
                signal.id = cur.fetchone()["id"]
                return signal.id
    except Exception as exc:  # pragma: no cover - depends on live DB
        logger.error("Failed to persist signal for %s: %s", signal.symbol, exc)

    with _lock:
        _memory_id += 1
        signal.id = _memory_id
        record = signal.to_dict()
        record.update(id=_memory_id, status=status, reject_reason=reject_reason)
        _memory_log.append(record)
    return signal.id


def update_status(signal_id: Optional[int], status: str, reject_reason: Optional[str] = None) -> None:
    if signal_id is None:
        return

    try:
        with db.cursor(commit=True) as cur:
            if cur is not None:
                cur.execute(
                    "UPDATE trade_signals SET status = %s, reject_reason = %s WHERE id = %s",
                    (status, reject_reason, signal_id),
                )
                return
    except Exception as exc:  # pragma: no cover - depends on live DB
        logger.error("Failed to update signal %s: %s", signal_id, exc)

    with _lock:
        for record in _memory_log:
            if record.get("id") == signal_id:
                record.update(status=status, reject_reason=reject_reason)
                break


def recent(limit: int = 50, source: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with db.cursor() as cur:
            if cur is not None:
                if source:
                    cur.execute(
                        "SELECT * FROM trade_signals WHERE source = %s "
                        "ORDER BY received_at DESC LIMIT %s",
                        (source, limit),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM trade_signals ORDER BY received_at DESC LIMIT %s",
                        (limit,),
                    )
                return [dict(row) for row in cur.fetchall()]
    except Exception as exc:  # pragma: no cover - depends on live DB
        logger.error("Failed to read signals: %s", exc)

    with _lock:
        records = [r for r in _memory_log if not source or r.get("source") == source]
        return records[-limit:][::-1]


def clear_dedupe_cache() -> None:
    with _lock:
        _recent.clear()
