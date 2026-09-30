"""Shared-secret verification for inbound TradingView/Chartink webhooks."""
import hmac
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

import config

_SECRET_KEYS = ("secret", "passphrase", "token", "webhook_secret")


def _presented_secret(request: Request, payload: Any) -> Optional[str]:
    header = (
        request.headers.get("x-webhook-secret")
        or request.headers.get("x-tradingview-secret")
    )
    if header:
        return header.strip()

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    if isinstance(payload, dict):
        for key in _SECRET_KEYS:
            value = payload.get(key)
            if value:
                return str(value).strip()

    return request.query_params.get("secret")


def verify(request: Request, payload: Any) -> None:
    """Raise 401 when a secret is configured and the request does not match."""
    if not config.WEBHOOK_SECRET:
        return

    presented = _presented_secret(request, payload)
    if not presented or not hmac.compare_digest(presented, config.WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def strip_secret(payload: Any) -> Dict[str, Any]:
    """Remove secret fields so they are never persisted with the signal."""
    if not isinstance(payload, dict):
        return payload
    return {key: value for key, value in payload.items() if key not in _SECRET_KEYS}
