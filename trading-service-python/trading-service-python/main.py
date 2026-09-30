import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from psycopg2.extras import RealDictCursor

import config
import db
import execution
import market_data
import webhook_auth
from engine import signal_store, trade_engine
from scanner.sector_strength import build_sector_strength_json, fetch_sector_strength
from signals import chartink, tradingview
from signals.models import Signal, SignalError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Service", version="2.0.0")


@app.on_event("startup")
def on_startup() -> None:
    db.init_schema()
    if config.AUTO_EXECUTE:
        trade_engine.ensure_worker()
    logger.info("Trading service ready in '%s' mode", config.TRADING_MODE)


@app.on_event("shutdown")
def on_shutdown() -> None:
    trade_engine.shutdown()


def get_db_connection():
    """Backwards-compatible helper used by the legacy endpoints."""
    return db.get_connection()


async def _read_payload(request: Request) -> Any:
    body = (await request.body()).decode("utf-8", errors="replace").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Empty webhook payload")
    try:
        return json.loads(body)
    except ValueError:
        return body


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"status": "Trading Service is running", "mode": config.TRADING_MODE}


@app.get("/health")
def health_check():
    conn = db.get_connection()
    database = "disconnected"
    if conn:
        conn.close()
        database = "connected"
    return {
        "status": "healthy" if database == "connected" else "degraded",
        "database": database,
        "mode": config.TRADING_MODE,
        "worker_running": trade_engine.status()["worker_running"],
    }


# ---------------------------------------------------------------------------
# Webhooks - TradingView and Chartink
# ---------------------------------------------------------------------------
@app.post("/webhooks/tradingview")
async def tradingview_webhook(request: Request, execute: Optional[bool] = Query(None)):
    """Receive a TradingView alert and queue it for execution."""
    payload = await _read_payload(request)
    webhook_auth.verify(request, payload)

    try:
        signals = tradingview.parse(webhook_auth.strip_secret(payload))
    except SignalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return trade_engine.submit(signals, execute=execute)


@app.post("/webhooks/chartink")
async def chartink_webhook(request: Request, execute: Optional[bool] = Query(None)):
    """Receive a Chartink alert (one payload may carry many stocks)."""
    payload = await _read_payload(request)
    webhook_auth.verify(request, payload)

    try:
        signals = chartink.parse(webhook_auth.strip_secret(payload))
    except SignalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return trade_engine.submit(signals, execute=execute)


@app.post("/chartink/scan")
def run_chartink_scan(body: Dict[str, Any]):
    """Run a Chartink screener clause on demand and optionally trade the hits."""
    try:
        signals = chartink.screener_signals(
            scan_clause=body.get("scan_clause"),
            action=body.get("action", "BUY"),
            strategy=body.get("strategy"),
        )
    except SignalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chartink request failed: {exc}") from exc

    matches = [s.to_dict() for s in signals]
    if not body.get("execute", False):
        return {"matches": len(matches), "executed": False, "signals": matches}

    result = trade_engine.submit(signals, execute=True)
    result["matches"] = len(matches)
    return result


@app.get("/signals")
def list_signals(limit: int = Query(50, ge=1, le=500), source: Optional[str] = None):
    return {"signals": signal_store.recent(limit=limit, source=source)}


@app.post("/signals/manual")
def manual_signal(body: Dict[str, Any]):
    """Push a hand-crafted signal through the full engine (useful for testing)."""
    try:
        signal = Signal.build(body.get("source", "manual"), body)
    except SignalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return trade_engine.process_now(signal)


# ---------------------------------------------------------------------------
# Paper trading
# ---------------------------------------------------------------------------
@app.get("/engine/status")
def engine_status():
    return trade_engine.status()


@app.get("/paper/positions")
def paper_positions():
    broker = execution.get_paper_broker()
    return {"open": broker.get_positions(), "closed": broker.get_closed_positions()}


@app.get("/paper/pnl")
def paper_pnl():
    return execution.get_paper_broker().get_pnl()


@app.get("/paper/orders")
def paper_orders(limit: int = Query(100, ge=1, le=500)):
    return {"orders": execution.get_paper_broker().get_orders(limit=limit)}


@app.post("/paper/square-off")
def paper_square_off(body: Optional[Dict[str, Any]] = None):
    """Exit one position or all of them. Pass ``price`` to force an exit
    price when live quotes are unavailable."""
    broker = execution.get_paper_broker()
    body = body or {}
    symbol = body.get("symbol")
    price = body.get("price")
    price = float(price) if price else None

    if symbol:
        return broker.square_off(str(symbol).upper(), price).to_dict()
    return {"results": [r.to_dict() for r in broker.square_off_all(price)]}


@app.post("/paper/reset")
def paper_reset():
    signal_store.clear_dedupe_cache()
    return execution.get_paper_broker().reset()


@app.get("/quote/{symbol}")
def quote(symbol: str, exchange: str = "NSE"):
    price = market_data.get_ltp(symbol.upper(), exchange)
    if price is None:
        raise HTTPException(status_code=404, detail=f"No quote available for {symbol}")
    return {"symbol": symbol.upper(), "exchange": exchange, "ltp": price}


# ---------------------------------------------------------------------------
# Legacy endpoints
# ---------------------------------------------------------------------------
@app.get("/stocks")
def get_stocks():
    conn = db.get_connection()
    if not conn:
        return {"error": "Database connection failed"}

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM stock_signals LIMIT 10")
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return [{"stock_name": "RELIANCE", "price": 2950}]

        return [
            {
                "id": row.get("id"),
                "stock_name": row.get("stock_name"),
                "price": row.get("price"),
                "target": row.get("target"),
                "stop_loss": row.get("stop_loss"),
                "quantity": row.get("quantity"),
                "risk_reward": row.get("risk_reward"),
                "pnl": row.get("pnl"),
            }
            for row in rows
        ]
    except Exception as exc:
        logger.exception("Query failed")
        return {"error": "Query failed", "details": str(exc)}
    finally:
        conn.close()


@app.get("/sector-strength")
def get_sector_strength():
    return build_sector_strength_json(fetch_sector_strength())


@app.post("/trade")
def place_trade(trade: dict):
    conn = db.get_connection()
    if not conn:
        return {"error": "Database connection failed"}

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO stock_signals
            (stock_name, price, target, stop_loss, quantity, risk_reward, pnl)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                trade.get("stock_name"),
                trade.get("price"),
                trade.get("target"),
                trade.get("stop_loss"),
                trade.get("quantity"),
                trade.get("risk_reward"),
                trade.get("pnl"),
            ),
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return {"message": "Trade inserted", "id": new_id}
    except Exception as exc:
        conn.rollback()
        logger.exception("Insert failed")
        return {"error": "Insert failed", "details": str(exc)}
    finally:
        conn.close()
