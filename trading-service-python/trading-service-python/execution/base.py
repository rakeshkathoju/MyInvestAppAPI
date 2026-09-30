"""Broker-agnostic execution interface.

Every adapter (paper, ICICI Direct Breeze, Motilal Oswal) implements
:class:`BrokerAdapter`, so the trade engine can switch venues by changing the
``TRADING_MODE`` environment variable only.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class OrderRequest:
    symbol: str
    action: str                 # BUY or SELL
    quantity: int
    price: Optional[float] = None   # None => market order
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    exchange: str = "NSE"
    product: str = "MIS"
    strategy: Optional[str] = None
    signal_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrderResult:
    broker: str
    symbol: str
    action: str
    quantity: int
    status: str                 # filled | placed | rejected | error
    fill_price: Optional[float] = None
    charges: float = 0.0
    broker_order_id: Optional[str] = None
    message: Optional[str] = None
    signal_id: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def successful(self) -> bool:
        return self.status in {"filled", "placed"}

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data.pop("raw", None)
        return data


class BrokerAdapter(ABC):
    """Common contract for paper and live brokers."""

    name: str = "base"
    is_live: bool = False

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult:
        """Submit an order and describe the outcome."""

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Return currently open positions."""

    @abstractmethod
    def get_funds(self) -> Dict[str, Any]:
        """Return available capital / margin."""

    def healthcheck(self) -> Dict[str, Any]:
        return {"broker": self.name, "live": self.is_live, "status": "ok"}
