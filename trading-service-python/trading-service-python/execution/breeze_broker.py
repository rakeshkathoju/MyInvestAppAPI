"""ICICI Direct (Breeze) live broker adapter."""
import logging
from typing import Any, Dict, List

import config
from .base import BrokerAdapter, OrderRequest, OrderResult

logger = logging.getLogger(__name__)


class BreezeBroker(BrokerAdapter):
    name = "breeze"
    is_live = True

    def __init__(self):
        self._client = None

    def _credentials_present(self) -> bool:
        return all(
            [config.BREEZE_API_KEY, config.BREEZE_API_SECRET, config.BREEZE_SESSION_TOKEN]
        )

    @property
    def client(self):
        if self._client is not None:
            return self._client
        if not self._credentials_present():
            raise RuntimeError(
                "Missing Breeze credentials. Set BREEZE_API_KEY, BREEZE_API_SECRET "
                "and BREEZE_SESSION_TOKEN (the session token is regenerated daily)."
            )

        from breeze_connect import BreezeConnect

        client = BreezeConnect(api_key=config.BREEZE_API_KEY)
        client.generate_session(
            api_secret=config.BREEZE_API_SECRET,
            session_token=config.BREEZE_SESSION_TOKEN,
        )
        self._client = client
        return client

    def place_order(self, order: OrderRequest) -> OrderResult:
        try:
            response = self.client.place_order(
                stock_code=order.symbol,
                exchange_code=order.exchange,
                product="margin" if order.product == "MIS" else "cash",
                action="buy" if order.action == "BUY" else "sell",
                order_type="market" if not order.price else "limit",
                stoploss=str(order.stop_loss or ""),
                quantity=str(order.quantity),
                price=str(order.price or ""),
                validity="day",
            )
        except Exception as exc:
            logger.exception("Breeze order failed for %s", order.symbol)
            return OrderResult(
                broker=self.name, symbol=order.symbol, action=order.action,
                quantity=order.quantity, status="error", message=str(exc),
                signal_id=order.signal_id,
            )

        success = str(response.get("Status")) == "200"
        payload = response.get("Success") or {}
        return OrderResult(
            broker=self.name,
            symbol=order.symbol,
            action=order.action,
            quantity=order.quantity,
            status="placed" if success else "rejected",
            fill_price=order.price,
            broker_order_id=payload.get("order_id") if isinstance(payload, dict) else None,
            message=response.get("Error") or "Order placed",
            signal_id=order.signal_id,
            raw=response,
        )

    def get_positions(self) -> List[Dict[str, Any]]:
        try:
            response = self.client.get_portfolio_positions()
            return response.get("Success") or []
        except Exception as exc:
            logger.error("Breeze positions lookup failed: %s", exc)
            return []

    def get_funds(self) -> Dict[str, Any]:
        try:
            return self.client.get_funds()
        except Exception as exc:
            logger.error("Breeze funds lookup failed: %s", exc)
            return {"error": str(exc)}

    def healthcheck(self) -> Dict[str, Any]:
        if not self._credentials_present():
            return {"broker": self.name, "live": True, "status": "missing_credentials"}
        try:
            self.client  # noqa: B018 - forces session generation
            return {"broker": self.name, "live": True, "status": "ok"}
        except Exception as exc:
            return {"broker": self.name, "live": True, "status": "error", "detail": str(exc)}
