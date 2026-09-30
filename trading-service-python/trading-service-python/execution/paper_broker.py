"""Paper trading broker: realistic simulated fills with full P&L accounting.

Positions are net and signed (``quantity > 0`` long, ``< 0`` short). State is
persisted to Postgres when ``DATABASE_URL`` is configured and falls back to an
in-process store otherwise, so the service is always usable.
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config
import db
import market_data
from .base import BrokerAdapter, OrderRequest, OrderResult

logger = logging.getLogger(__name__)

BROKER_NAME = "paper"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _charges(turnover: float) -> float:
    return round(turnover * config.BROKERAGE_PCT / 100.0, 2)


def _apply_slippage(price: float, action: str) -> float:
    drift = price * config.SLIPPAGE_PCT / 100.0
    return round(price + drift if action == "BUY" else price - drift, 2)


class _MemoryStore:
    """In-process fallback used when no database is configured."""

    def __init__(self):
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed: List[Dict[str, Any]] = []
        self.orders: List[Dict[str, Any]] = []
        self._order_id = 0

    def get_open(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self.positions.get(symbol)

    def list_open(self) -> List[Dict[str, Any]]:
        return list(self.positions.values())

    def list_closed(self, limit: int) -> List[Dict[str, Any]]:
        return self.closed[-limit:][::-1]

    def upsert_open(self, position: Dict[str, Any]) -> None:
        self.positions[position["symbol"]] = position

    def close(self, symbol: str, exit_price: float, realized_pnl: float, charges: float) -> None:
        position = self.positions.pop(symbol, None)
        if not position:
            return
        position.update(
            status="closed",
            closed_at=_now(),
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            charges=position.get("charges", 0.0) + charges,
        )
        self.closed.append(position)

    def add_order(self, record: Dict[str, Any]) -> int:
        self._order_id += 1
        record["id"] = self._order_id
        self.orders.append(record)
        return self._order_id

    def list_orders(self, limit: int) -> List[Dict[str, Any]]:
        return self.orders[-limit:][::-1]

    def reset(self) -> None:
        self.__init__()


class _DatabaseStore:
    """Postgres-backed store for paper positions and orders."""

    def get_open(self, symbol: str) -> Optional[Dict[str, Any]]:
        with db.cursor() as cur:
            if cur is None:
                return None
            cur.execute(
                "SELECT * FROM paper_positions WHERE symbol = %s AND status = 'open' "
                "AND broker = %s ORDER BY id DESC LIMIT 1",
                (symbol, BROKER_NAME),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def list_open(self) -> List[Dict[str, Any]]:
        with db.cursor() as cur:
            if cur is None:
                return []
            cur.execute(
                "SELECT * FROM paper_positions WHERE status = 'open' AND broker = %s "
                "ORDER BY opened_at DESC",
                (BROKER_NAME,),
            )
            return [dict(row) for row in cur.fetchall()]

    def list_closed(self, limit: int) -> List[Dict[str, Any]]:
        with db.cursor() as cur:
            if cur is None:
                return []
            cur.execute(
                "SELECT * FROM paper_positions WHERE status = 'closed' AND broker = %s "
                "ORDER BY closed_at DESC LIMIT %s",
                (BROKER_NAME, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    def upsert_open(self, position: Dict[str, Any]) -> None:
        with db.cursor(commit=True) as cur:
            if cur is None:
                return
            if position.get("id"):
                cur.execute(
                    "UPDATE paper_positions SET quantity = %s, avg_price = %s, "
                    "stop_loss = %s, target = %s, charges = %s WHERE id = %s",
                    (
                        position["quantity"],
                        position["avg_price"],
                        position.get("stop_loss"),
                        position.get("target"),
                        position.get("charges", 0),
                        position["id"],
                    ),
                )
            else:
                cur.execute(
                    "INSERT INTO paper_positions "
                    "(broker, symbol, quantity, avg_price, stop_loss, target, strategy, charges) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        BROKER_NAME,
                        position["symbol"],
                        position["quantity"],
                        position["avg_price"],
                        position.get("stop_loss"),
                        position.get("target"),
                        position.get("strategy"),
                        position.get("charges", 0),
                    ),
                )
                position["id"] = cur.fetchone()["id"]

    def close(self, symbol: str, exit_price: float, realized_pnl: float, charges: float) -> None:
        with db.cursor(commit=True) as cur:
            if cur is None:
                return
            cur.execute(
                "UPDATE paper_positions SET status = 'closed', closed_at = NOW(), "
                "exit_price = %s, realized_pnl = %s, charges = COALESCE(charges, 0) + %s "
                "WHERE symbol = %s AND status = 'open' AND broker = %s",
                (exit_price, realized_pnl, charges, symbol, BROKER_NAME),
            )

    def add_order(self, record: Dict[str, Any]) -> Optional[int]:
        with db.cursor(commit=True) as cur:
            if cur is None:
                return None
            cur.execute(
                "INSERT INTO paper_orders "
                "(signal_id, broker, broker_order_id, symbol, action, quantity, "
                " requested_price, fill_price, charges, status, message) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    record.get("signal_id"),
                    BROKER_NAME,
                    record.get("broker_order_id"),
                    record["symbol"],
                    record["action"],
                    record["quantity"],
                    record.get("requested_price"),
                    record.get("fill_price"),
                    record.get("charges", 0),
                    record["status"],
                    record.get("message"),
                ),
            )
            return cur.fetchone()["id"]

    def list_orders(self, limit: int) -> List[Dict[str, Any]]:
        with db.cursor() as cur:
            if cur is None:
                return []
            cur.execute(
                "SELECT * FROM paper_orders WHERE broker = %s ORDER BY id DESC LIMIT %s",
                (BROKER_NAME, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    def reset(self) -> None:
        with db.cursor(commit=True) as cur:
            if cur is None:
                return
            cur.execute("DELETE FROM paper_orders WHERE broker = %s", (BROKER_NAME,))
            cur.execute("DELETE FROM paper_positions WHERE broker = %s", (BROKER_NAME,))


class PaperBroker(BrokerAdapter):
    name = BROKER_NAME
    is_live = False

    def __init__(self, starting_capital: Optional[float] = None):
        self.starting_capital = float(
            starting_capital if starting_capital is not None else config.PAPER_STARTING_CAPITAL
        )
        self._store = _DatabaseStore() if db.is_configured() else _MemoryStore()
        self._lock = threading.Lock()

    # -- helpers ----------------------------------------------------------
    @property
    def persistent(self) -> bool:
        return isinstance(self._store, _DatabaseStore)

    def _resolve_fill_price(self, order: OrderRequest) -> Optional[float]:
        price = order.price or market_data.get_ltp(order.symbol, order.exchange)
        return _apply_slippage(float(price), order.action) if price else None

    # -- BrokerAdapter ----------------------------------------------------
    def place_order(self, order: OrderRequest) -> OrderResult:
        if order.quantity <= 0:
            return self._record(order, "rejected", None, 0.0, "Quantity must be positive")

        fill_price = self._resolve_fill_price(order)
        if fill_price is None:
            return self._record(
                order, "rejected", None, 0.0,
                f"No price available for {order.symbol}; send 'price' in the signal",
            )

        with self._lock:
            charges = _charges(fill_price * order.quantity)
            try:
                message = self._apply_fill(order, fill_price, charges)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Paper fill failed for %s", order.symbol)
                return self._record(order, "error", fill_price, 0.0, str(exc))

        return self._record(order, "filled", fill_price, charges, message)

    def _apply_fill(self, order: OrderRequest, fill_price: float, charges: float) -> str:
        signed_qty = order.quantity if order.action == "BUY" else -order.quantity
        position = self._store.get_open(order.symbol)

        if not position:
            self._store.upsert_open(
                {
                    "symbol": order.symbol,
                    "quantity": signed_qty,
                    "avg_price": fill_price,
                    "stop_loss": order.stop_loss,
                    "target": order.target,
                    "strategy": order.strategy,
                    "charges": charges,
                    "opened_at": _now(),
                    "status": "open",
                }
            )
            return f"Opened {'LONG' if signed_qty > 0 else 'SHORT'} {abs(signed_qty)} {order.symbol} @ {fill_price}"

        held = int(position["quantity"])
        avg = float(position["avg_price"])
        net = held + signed_qty

        # Adding to an existing position in the same direction.
        if held * signed_qty > 0:
            position["avg_price"] = round(
                (avg * abs(held) + fill_price * abs(signed_qty)) / abs(net), 4
            )
            position["quantity"] = net
            position["charges"] = float(position.get("charges") or 0) + charges
            if order.stop_loss:
                position["stop_loss"] = order.stop_loss
            if order.target:
                position["target"] = order.target
            self._store.upsert_open(position)
            return f"Added {abs(signed_qty)} {order.symbol} @ {fill_price}, avg {position['avg_price']}"

        closed_qty = min(abs(held), abs(signed_qty))
        realized = round((fill_price - avg) * closed_qty * (1 if held > 0 else -1) - charges, 2)

        if net == 0:
            self._store.close(order.symbol, fill_price, realized, charges)
            return f"Closed {closed_qty} {order.symbol} @ {fill_price}, P&L {realized}"

        if abs(net) < abs(held):
            # Partial reduction: book P&L on the closed slice, keep the rest.
            position["quantity"] = net
            position["charges"] = float(position.get("charges") or 0) + charges
            self._store.upsert_open(position)
            self._book_partial(order.symbol, closed_qty, realized)
            return f"Reduced {order.symbol} by {closed_qty} @ {fill_price}, P&L {realized}"

        # Reversal: close the old position, open the remainder the other way.
        self._store.close(order.symbol, fill_price, realized, charges)
        remainder = net
        self._store.upsert_open(
            {
                "symbol": order.symbol,
                "quantity": remainder,
                "avg_price": fill_price,
                "stop_loss": order.stop_loss,
                "target": order.target,
                "strategy": order.strategy,
                "charges": 0.0,
                "opened_at": _now(),
                "status": "open",
            }
        )
        return (
            f"Reversed {order.symbol}: booked {realized} on {closed_qty}, "
            f"now {'LONG' if remainder > 0 else 'SHORT'} {abs(remainder)}"
        )

    def _book_partial(self, symbol: str, quantity: int, realized: float) -> None:
        """Record realized P&L for a partial exit as a closed audit row."""
        record = {
            "symbol": symbol,
            "action": "PARTIAL_EXIT",
            "quantity": quantity,
            "status": "filled",
            "fill_price": None,
            "charges": 0,
            "message": f"Partial exit realized P&L {realized}",
        }
        self._store.add_order(record)

    def _record(
        self,
        order: OrderRequest,
        status: str,
        fill_price: Optional[float],
        charges: float,
        message: Optional[str],
    ) -> OrderResult:
        record = {
            "signal_id": order.signal_id,
            "symbol": order.symbol,
            "action": order.action,
            "quantity": order.quantity,
            "requested_price": order.price,
            "fill_price": fill_price,
            "charges": charges,
            "status": status,
            "message": message,
        }
        order_id = self._store.add_order(record)
        return OrderResult(
            broker=self.name,
            symbol=order.symbol,
            action=order.action,
            quantity=order.quantity,
            status=status,
            fill_price=fill_price,
            charges=charges,
            broker_order_id=str(order_id) if order_id else None,
            message=message,
            signal_id=order.signal_id,
        )

    def get_positions(self) -> List[Dict[str, Any]]:
        positions = []
        for row in self._store.list_open():
            quantity = int(row["quantity"])
            avg_price = float(row["avg_price"])
            ltp = market_data.get_ltp(row["symbol"]) or avg_price
            positions.append(
                {
                    "symbol": row["symbol"],
                    "side": "LONG" if quantity > 0 else "SHORT",
                    "quantity": quantity,
                    "avg_price": round(avg_price, 2),
                    "ltp": round(ltp, 2),
                    "stop_loss": float(row["stop_loss"]) if row.get("stop_loss") else None,
                    "target": float(row["target"]) if row.get("target") else None,
                    "strategy": row.get("strategy"),
                    "unrealized_pnl": round((ltp - avg_price) * quantity, 2),
                    "invested": round(abs(quantity) * avg_price, 2),
                }
            )
        return positions

    def get_closed_positions(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [
            {
                "symbol": row["symbol"],
                "quantity": int(row["quantity"]),
                "avg_price": round(float(row["avg_price"]), 2),
                "exit_price": round(float(row["exit_price"]), 2) if row.get("exit_price") else None,
                "realized_pnl": round(float(row["realized_pnl"]), 2) if row.get("realized_pnl") else 0.0,
                "strategy": row.get("strategy"),
                "closed_at": str(row.get("closed_at")),
            }
            for row in self._store.list_closed(limit)
        ]

    def get_orders(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._store.list_orders(limit)

    def get_funds(self) -> Dict[str, Any]:
        return self.get_pnl()

    def get_pnl(self) -> Dict[str, Any]:
        open_positions = self.get_positions()
        closed = self.get_closed_positions(limit=1000)

        unrealized = round(sum(p["unrealized_pnl"] for p in open_positions), 2)
        realized = round(sum(c["realized_pnl"] for c in closed), 2)
        deployed = round(sum(p["invested"] for p in open_positions), 2)
        wins = [c for c in closed if c["realized_pnl"] > 0]

        return {
            "broker": self.name,
            "persistent": self.persistent,
            "starting_capital": self.starting_capital,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": round(realized + unrealized, 2),
            "equity": round(self.starting_capital + realized + unrealized, 2),
            "capital_deployed": deployed,
            "available_capital": round(self.starting_capital + realized - deployed, 2),
            "open_positions": len(open_positions),
            "closed_trades": len(closed),
            "win_rate_pct": round(len(wins) / len(closed) * 100, 2) if closed else 0.0,
        }

    def reset(self) -> Dict[str, Any]:
        with self._lock:
            self._store.reset()
        market_data.clear_cache()
        return {"status": "reset", "starting_capital": self.starting_capital}

    def square_off(self, symbol: str, price: Optional[float] = None) -> OrderResult:
        """Exit an open position. ``price`` overrides the live quote lookup,
        so a position can still be closed during a market-data outage."""
        position = self._store.get_open(symbol)
        if not position:
            return OrderResult(
                broker=self.name, symbol=symbol, action="SELL", quantity=0,
                status="rejected", message=f"No open position for {symbol}",
            )
        quantity = int(position["quantity"])
        return self.place_order(
            OrderRequest(
                symbol=symbol,
                action="SELL" if quantity > 0 else "BUY",
                quantity=abs(quantity),
                price=price,
                strategy=position.get("strategy"),
            )
        )

    def square_off_all(self, price: Optional[float] = None) -> List[OrderResult]:
        return [self.square_off(row["symbol"], price) for row in self._store.list_open()]
