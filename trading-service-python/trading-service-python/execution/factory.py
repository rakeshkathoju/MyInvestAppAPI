"""Broker selection. Switching paper -> live is a ``TRADING_MODE`` change only."""
import logging
from threading import Lock
from typing import Dict, Optional

import config
from .base import BrokerAdapter
from .breeze_broker import BreezeBroker
from .motilal_broker import MotilalBroker
from .paper_broker import PaperBroker

logger = logging.getLogger(__name__)

_REGISTRY = {
    "paper": PaperBroker,
    "breeze": BreezeBroker,
    "icici": BreezeBroker,
    "icicidirect": BreezeBroker,
    "motilal": MotilalBroker,
    "motilaloswal": MotilalBroker,
}

_instances: Dict[str, BrokerAdapter] = {}
_lock = Lock()


def available_modes():
    return sorted(set(_REGISTRY))


def get_broker(mode: Optional[str] = None) -> BrokerAdapter:
    """Return a cached broker adapter for ``mode`` (defaults to TRADING_MODE)."""
    key = (mode or config.TRADING_MODE or "paper").strip().lower()
    broker_cls = _REGISTRY.get(key)

    if broker_cls is None:
        logger.warning("Unknown TRADING_MODE %r - falling back to paper trading", key)
        key, broker_cls = "paper", PaperBroker

    with _lock:
        if key not in _instances:
            _instances[key] = broker_cls()
        return _instances[key]


def get_paper_broker() -> PaperBroker:
    """Always return the paper broker, regardless of the configured mode."""
    return get_broker("paper")  # type: ignore[return-value]


def reset_cache() -> None:
    with _lock:
        _instances.clear()
