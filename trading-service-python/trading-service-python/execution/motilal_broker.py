"""Motilal Oswal OpenAPI live broker adapter.

Uses the REST endpoints directly so no vendor SDK is required. Supply
``MOTILAL_API_KEY``, ``MOTILAL_AUTH_TOKEN`` (from the daily login flow) and
``MOTILAL_CLIENT_CODE``.
"""
import logging
from typing import Any, Dict, List

import requests

import config
from .base import BrokerAdapter, OrderRequest, OrderResult

logger = logging.getLogger(__name__)


class MotilalBroker(BrokerAdapter):
    name = "motilal"
    is_live = True

    def __init__(self):
        self.base_url = config.MOTILAL_BASE_URL.rstrip("/")

    def _credentials_present(self) -> bool:
        return all(
            [config.MOTILAL_API_KEY, config.MOTILAL_AUTH_TOKEN, config.MOTILAL_CLIENT_CODE]
        )

    def _headers(self) -> Dict[str, str]:
        if not self._credentials_present():
            raise RuntimeError(
                "Missing Motilal credentials. Set MOTILAL_API_KEY, MOTILAL_AUTH_TOKEN "
                "and MOTILAL_CLIENT_CODE."
            )
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MOSL/V.1.1.0",
            "apikey": config.MOTILAL_API_KEY,
            "Authorization": config.MOTILAL_AUTH_TOKEN,
            "ClientLocalIp": "127.0.0.1",
            "ClientPublicIp": "127.0.0.1",
            "MacAddress": "00:00:00:00:00:00",
            "SourceId": "WEB",
            "vendorinfo": config.MOTILAL_CLIENT_CODE,
            "osname": "Linux",
        }

    def _post(self, path: str, payload: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}{path}", json=payload, headers=self._headers(), timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    def place_order(self, order: OrderRequest) -> OrderResult:
        payload = {
            "clientcode": config.MOTILAL_CLIENT_CODE,
            "exchange": order.exchange,
            "symboltoken": 0,
            "symbol": order.symbol,
            "buyorsell": order.action,
            "ordertype": "LIMIT" if order.price else "MARKET",
            "producttype": "DELIVERY" if order.product == "CNC" else "NORMAL",
            "orderduration": "DAY",
            "price": order.price or 0,
            "triggerprice": order.stop_loss or 0,
            "quantityinlot": order.quantity,
            "disclosedquantity": 0,
            "amoorder": "N",
            "algoid": "",
            "tag": (order.strategy or "")[:20],
        }

        try:
            response = self._post("/rest/trans/v1/placeorder", payload)
        except Exception as exc:
            logger.exception("Motilal order failed for %s", order.symbol)
            return OrderResult(
                broker=self.name, symbol=order.symbol, action=order.action,
                quantity=order.quantity, status="error", message=str(exc),
                signal_id=order.signal_id,
            )

        success = str(response.get("status", "")).upper() == "SUCCESS"
        return OrderResult(
            broker=self.name,
            symbol=order.symbol,
            action=order.action,
            quantity=order.quantity,
            status="placed" if success else "rejected",
            fill_price=order.price,
            broker_order_id=str(response.get("uniqueorderid") or ""),
            message=response.get("message", "Order placed"),
            signal_id=order.signal_id,
            raw=response,
        )

    def get_positions(self) -> List[Dict[str, Any]]:
        try:
            response = self._post(
                "/rest/book/v1/getposition", {"clientcode": config.MOTILAL_CLIENT_CODE}
            )
            return response.get("data") or []
        except Exception as exc:
            logger.error("Motilal positions lookup failed: %s", exc)
            return []

    def get_funds(self) -> Dict[str, Any]:
        try:
            return self._post(
                "/rest/report/v1/getreportmargindetail",
                {"clientcode": config.MOTILAL_CLIENT_CODE},
            )
        except Exception as exc:
            logger.error("Motilal funds lookup failed: %s", exc)
            return {"error": str(exc)}

    def healthcheck(self) -> Dict[str, Any]:
        if not self._credentials_present():
            return {"broker": self.name, "live": True, "status": "missing_credentials"}
        return {"broker": self.name, "live": True, "status": "ok"}
