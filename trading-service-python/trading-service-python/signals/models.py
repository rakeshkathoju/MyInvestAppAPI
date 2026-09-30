"""Normalized representation of an incoming buy/sell signal."""
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

BUY_WORDS = {"buy", "long", "entry", "enter_long", "cover", "bullish"}
SELL_WORDS = {"sell", "short", "exit", "exit_long", "enter_short", "bearish"}

_SYMBOL_SUFFIXES = ("-EQ", ".NS", ".BSE", ".BO")


class SignalError(ValueError):
    """Raised when an inbound payload cannot be turned into a Signal."""


def normalize_symbol(raw: Any) -> str:
    symbol = str(raw or "").strip().upper()
    # TradingView sends things like "NSE:RELIANCE" or "RELIANCE.NS".
    if ":" in symbol:
        symbol = symbol.split(":", 1)[1]
    for suffix in _SYMBOL_SUFFIXES:
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
            break
    symbol = re.sub(r"[^A-Z0-9&_-]", "", symbol)
    if not symbol:
        raise SignalError("Signal is missing a usable symbol")
    return symbol


def normalize_action(raw: Any) -> str:
    action = str(raw or "").strip().lower().replace(" ", "_")
    if action in BUY_WORDS:
        return "BUY"
    if action in SELL_WORDS:
        return "SELL"
    raise SignalError(f"Unrecognized signal action: {raw!r}")


def to_float(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        value = float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def to_int(raw: Any) -> Optional[int]:
    value = to_float(raw)
    return int(value) if value else None


@dataclass
class Signal:
    """A broker-agnostic trade instruction."""

    source: str
    symbol: str
    action: str
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    quantity: Optional[int] = None
    strategy: Optional[str] = None
    exchange: str = "NSE"
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Optional[str] = None
    id: Optional[int] = None

    @classmethod
    def build(cls, source: str, payload: Dict[str, Any], **overrides) -> "Signal":
        def pick(key):
            return overrides[key] if key in overrides else payload.get(key)

        return cls(
            source=source,
            symbol=normalize_symbol(pick("symbol")),
            action=normalize_action(pick("action")),
            price=to_float(pick("price")),
            stop_loss=to_float(pick("stop_loss")),
            target=to_float(pick("target")),
            quantity=to_int(pick("quantity")),
            strategy=pick("strategy"),
            exchange=(pick("exchange") or "NSE"),
            raw_payload=json.dumps(payload, default=str)[:4000],
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["received_at"] = self.received_at.isoformat()
        data.pop("raw_payload", None)
        return data
