"""Chartink integration: alert webhooks plus screener polling.

Chartink alert webhooks post a payload shaped like::

    {
      "stocks": "SBIN,TATAMOTORS",
      "trigger_prices": "542.5,415.3",
      "triggered_at": "2:34 pm",
      "scan_name": "Intraday breakout",
      "scan_url": "intraday-breakout",
      "alert_name": "Breakout alert"
    }

Because Chartink alerts carry no direction, the action is taken from the
``action`` field when present, otherwise from ``CHARTINK_DEFAULT_ACTION``
(default ``BUY``) — bearish scans should be wired to a ``SELL`` alert.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

import config
from .models import Signal, SignalError, to_float

logger = logging.getLogger(__name__)

SOURCE = "chartink"
SCREENER_URL = "https://chartink.com/screener/process"
BASE_URL = "https://chartink.com/screener/"
DEFAULT_ACTION = "BUY"


def _split(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse(body: Any) -> List[Signal]:
    """Turn a Chartink alert webhook body into one signal per stock."""
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", errors="replace")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise SignalError("Chartink alert payload must be JSON") from exc
    if not isinstance(body, dict):
        raise SignalError("Unsupported Chartink alert payload")

    stocks = _split(body.get("stocks") or body.get("symbol"))
    if not stocks:
        raise SignalError("Chartink alert contains no stocks")

    prices = _split(body.get("trigger_prices") or body.get("price"))
    action = body.get("action") or DEFAULT_ACTION
    strategy = body.get("scan_name") or body.get("alert_name") or "chartink-scan"

    signals = []
    for index, stock in enumerate(stocks):
        price = prices[index] if index < len(prices) else None
        signals.append(
            Signal.build(
                SOURCE,
                body,
                symbol=stock,
                action=action,
                price=price,
                strategy=strategy,
                stop_loss=body.get("stop_loss"),
                target=body.get("target"),
                quantity=body.get("quantity"),
            )
        )
    return signals


def run_screener(scan_clause: Optional[str] = None, timeout: int = 20) -> List[Dict[str, Any]]:
    """Run a Chartink screener clause and return the raw matched rows.

    ``scan_clause`` is the same expression used in the Chartink screener UI,
    e.g. ``( {cash} ( latest close > latest ema( latest close , 20 ) ) )``.
    """
    clause = (scan_clause or config.CHARTINK_SCAN_CLAUSE or "").strip()
    if not clause:
        raise SignalError(
            "No Chartink scan clause provided. Set CHARTINK_SCAN_CLAUSE or pass scan_clause."
        )

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; MyInvestAppAPI/1.0)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": BASE_URL,
        }
    )

    landing = session.get(BASE_URL, timeout=timeout)
    landing.raise_for_status()
    match = re.search(r'name="csrf-token"\s+content="([^"]+)"', landing.text)
    if not match:
        raise SignalError("Could not read Chartink CSRF token")

    response = session.post(
        SCREENER_URL,
        headers={"X-CSRF-TOKEN": match.group(1)},
        data={"scan_clause": clause},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json().get("data", []) or []


def screener_signals(
    scan_clause: Optional[str] = None,
    action: str = DEFAULT_ACTION,
    strategy: Optional[str] = None,
) -> List[Signal]:
    """Run a Chartink screener and convert every match into a Signal."""
    rows = run_screener(scan_clause)
    label = strategy or "chartink-screener"

    signals = []
    for row in rows:
        symbol = row.get("nsecode") or row.get("bsecode") or row.get("name")
        if not symbol:
            continue
        try:
            signals.append(
                Signal.build(
                    SOURCE,
                    row,
                    symbol=symbol,
                    action=action,
                    price=to_float(row.get("close")),
                    strategy=label,
                )
            )
        except SignalError as exc:
            logger.warning("Skipping Chartink row %s: %s", row, exc)
    return signals
