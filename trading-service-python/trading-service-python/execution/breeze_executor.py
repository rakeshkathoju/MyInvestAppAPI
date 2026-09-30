"""Backwards-compatible helpers for direct ICICI Direct (Breeze) orders.

New code should use :func:`execution.get_broker` instead, which returns an
adapter that works identically for paper and live trading.
"""
import logging

from .base import OrderRequest
from .breeze_broker import BreezeBroker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def init_breeze_client():
    return BreezeBroker().client


def execute_market_order(symbol, quantity, order_type="BUY", product="MIS", exchange="NSE"):
    """Place a market order through Breeze and return the raw broker result."""
    result = BreezeBroker().place_order(
        OrderRequest(
            symbol=symbol,
            action=order_type.upper(),
            quantity=quantity,
            product=product,
            exchange=exchange,
        )
    )
    return result.raw or result.to_dict()
