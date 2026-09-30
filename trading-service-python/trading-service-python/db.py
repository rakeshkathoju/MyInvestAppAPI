"""Database helpers for the trading service.

Everything degrades gracefully: when ``DATABASE_URL`` is not configured the
service still runs and the paper-trading store keeps state in memory only.
"""
import logging
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

import config

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trade_signals (
    id              SERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,
    symbol          TEXT        NOT NULL,
    action          TEXT        NOT NULL,
    price           NUMERIC,
    stop_loss       NUMERIC,
    target          NUMERIC,
    quantity        INTEGER,
    strategy        TEXT,
    exchange        TEXT,
    raw_payload     TEXT,
    status          TEXT        NOT NULL DEFAULT 'received',
    reject_reason   TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_signals_symbol_time
    ON trade_signals (symbol, received_at DESC);

CREATE TABLE IF NOT EXISTS paper_orders (
    id              SERIAL PRIMARY KEY,
    signal_id       INTEGER REFERENCES trade_signals (id),
    broker          TEXT        NOT NULL,
    broker_order_id TEXT,
    symbol          TEXT        NOT NULL,
    action          TEXT        NOT NULL,
    quantity        INTEGER     NOT NULL,
    requested_price NUMERIC,
    fill_price      NUMERIC,
    charges         NUMERIC     DEFAULT 0,
    status          TEXT        NOT NULL,
    message         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_positions (
    id              SERIAL PRIMARY KEY,
    broker          TEXT        NOT NULL,
    symbol          TEXT        NOT NULL,
    quantity        INTEGER     NOT NULL,
    avg_price       NUMERIC     NOT NULL,
    stop_loss       NUMERIC,
    target          NUMERIC,
    strategy        TEXT,
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    exit_price      NUMERIC,
    realized_pnl    NUMERIC,
    charges         NUMERIC     DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'open'
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_open
    ON paper_positions (status, symbol);
"""


def is_configured() -> bool:
    return bool(config.DATABASE_URL)


def get_connection():
    """Return a new connection, or ``None`` when the DB is unavailable."""
    if not is_configured():
        return None
    try:
        return psycopg2.connect(config.DATABASE_URL, sslmode="require")
    except Exception as exc:  # pragma: no cover - depends on live DB
        logger.error("Database connection failed: %s", exc)
        return None


@contextmanager
def cursor(dict_rows: bool = True, commit: bool = False):
    """Yield a cursor, or ``None`` when no database is reachable."""
    conn = get_connection()
    if conn is None:
        yield None
        return

    cur = conn.cursor(cursor_factory=RealDictCursor if dict_rows else None)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def init_schema() -> bool:
    """Create the signal/order/position tables if they do not exist."""
    conn = get_connection()
    if conn is None:
        logger.warning("Skipping schema init - no database configured")
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
        logger.info("Trading schema ready")
        return True
    except Exception as exc:  # pragma: no cover - depends on live DB
        conn.rollback()
        logger.error("Schema init failed: %s", exc)
        return False
    finally:
        conn.close()
