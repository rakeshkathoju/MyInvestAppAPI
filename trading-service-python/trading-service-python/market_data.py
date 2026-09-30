"""Last-traded-price lookups used for paper fills and mark-to-market."""
import logging
import time
from threading import Lock
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_CACHE: Dict[str, tuple] = {}
_CACHE_TTL_SECONDS = 30
_LOCK = Lock()


def _fetch_from_yfinance(symbol: str, exchange: str) -> Optional[float]:
    try:
        import yfinance as yf
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("yfinance is not installed; cannot fetch quotes")
        return None

    suffix = ".BO" if exchange.upper() == "BSE" else ".NS"
    try:
        history = yf.Ticker(f"{symbol}{suffix}").history(period="1d", interval="1m")
        if history is None or history.empty:
            return None
        return float(history["Close"].iloc[-1])
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Quote lookup failed for %s: %s", symbol, exc)
        return None


def get_ltp(symbol: str, exchange: str = "NSE") -> Optional[float]:
    """Return the latest traded price, cached briefly to limit API calls."""
    key = f"{exchange.upper()}:{symbol.upper()}"
    now = time.time()

    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[1] < _CACHE_TTL_SECONDS:
            return cached[0]

    price = _fetch_from_yfinance(symbol, exchange)
    if price is not None:
        with _LOCK:
            _CACHE[key] = (price, now)
    return price


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
