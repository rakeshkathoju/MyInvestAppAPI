"""Parse TradingView alert webhooks into :class:`Signal` objects.

Configure the TradingView alert message as JSON, for example::

    {
      "secret": "your-webhook-secret",
      "symbol": "{{ticker}}",
      "action": "{{strategy.order.action}}",
      "price": "{{close}}",
      "stop_loss": "",
      "target": "",
      "quantity": "{{strategy.order.contracts}}",
      "strategy": "{{strategy.order.id}}"
    }

Plain-text alerts such as ``BUY RELIANCE 2950`` are also accepted.
"""
import json
import re
from typing import Any, Dict, List

from .models import Signal, SignalError

SOURCE = "tradingview"

_TEXT_PATTERN = re.compile(
    r"^\s*(?P<action>buy|sell|long|short|exit|cover)\s+(?P<symbol>[A-Za-z0-9:&._-]+)"
    r"(?:\s+(?:@\s*)?(?P<price>[\d.,]+))?",
    re.IGNORECASE,
)

# TradingView placeholders that were never substituted come through literally.
_UNRESOLVED = re.compile(r"^\{\{.*\}\}$")


def _clean(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: (None if isinstance(value, str) and _UNRESOLVED.match(value.strip()) else value)
        for key, value in payload.items()
    }


def parse_text_alert(body: str) -> Dict[str, Any]:
    match = _TEXT_PATTERN.match(body or "")
    if not match:
        raise SignalError(
            "TradingView alert must be JSON or 'BUY <SYMBOL> <price>' text"
        )
    return {
        "action": match.group("action"),
        "symbol": match.group("symbol"),
        "price": match.group("price"),
    }


def parse(body: Any) -> List[Signal]:
    """Turn a TradingView alert body (dict, JSON string, or text) into signals."""
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", errors="replace")

    if isinstance(body, str):
        stripped = body.strip()
        try:
            body = json.loads(stripped)
        except (ValueError, TypeError):
            body = parse_text_alert(stripped)

    if not isinstance(body, dict):
        raise SignalError("Unsupported TradingView alert payload")

    payload = _clean(body)
    return [Signal.build(SOURCE, payload)]
