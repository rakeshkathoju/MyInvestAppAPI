"""Optional AI confirmation filter for incoming signals.

When ``AI_CONFIRMATION_ENABLED`` is true, every BUY signal is checked against
the AI service before it reaches the broker. Exit/SELL signals are never
blocked - refusing to close a position is more dangerous than opening one.
"""
import logging
from typing import Optional, Tuple

import requests

import config
from signals.models import Signal

logger = logging.getLogger(__name__)


def _allow(reason: str) -> Tuple[bool, str]:
    return True, reason


def confirm(signal: Signal) -> Tuple[bool, Optional[str]]:
    """Return ``(allowed, reason)`` for a signal."""
    if not config.AI_CONFIRMATION_ENABLED:
        return _allow("ai filter disabled")

    if signal.action != "BUY":
        return _allow("exit signals bypass the ai filter")

    url = f"{config.AI_SERVICE_URL.rstrip('/')}/predict"
    try:
        response = requests.post(
            url,
            json={"ticker": signal.symbol, "symbol": signal.symbol},
            timeout=config.AI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("AI confirmation unavailable for %s: %s", signal.symbol, exc)
        if config.AI_FAIL_OPEN:
            return _allow(f"ai service unreachable, failing open ({exc})")
        return False, f"AI service unreachable: {exc}"

    verdict = str(payload.get("signal") or payload.get("prediction") or "").upper()
    try:
        confidence = float(
            payload.get("probability")
            if payload.get("probability") is not None
            else payload.get("confidence", 0)
        )
    except (TypeError, ValueError):
        confidence = 0.0

    if verdict == "BUY" and confidence >= config.AI_MIN_CONFIDENCE:
        return True, f"ai confirmed BUY at {confidence:.2f}"

    return False, (
        f"AI filter rejected {signal.symbol}: verdict={verdict or 'unknown'} "
        f"confidence={confidence:.2f} (min {config.AI_MIN_CONFIDENCE})"
    )
