"""
paper_trade.py
--------------
Simulates the VWAP + EMA crossover strategy in real-time using live
Yahoo Finance quotes. No real money is involved.

Every minute it:
  1. Downloads the latest 1-min candle for ICICIBANK.NS
  2. Recalculates indicators (VWAP, EMA9, EMA21, volume spike)
  3. Checks entry / exit conditions
  4. Logs simulated trades to data/paper_trades.csv

Usage:
    python3 data/paper_trade.py
"""

import os
import time
import logging
from datetime import datetime, time as dtime

import pandas as pd
import numpy as np
import yfinance as yf
import schedule

# ---------- SETTINGS (must match backtest.py) ----------
TICKER         = "ICICIBANK.NS"
TARGET_PCT     = 0.006
STOP_PCT       = 0.004
VOL_MULTIPLIER = 1.5
EMA_FAST       = 9
EMA_SLOW       = 21
START_TIME     = dtime(9, 20)
END_TIME       = dtime(11, 30)
BROKERAGE_PCT  = 0.0005
TRADE_LOG_PATH = "data/paper_trades.csv"
LOOKBACK_MINS  = 60          # how many minutes of history to fetch per tick
# -------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# In-memory state
position = None   # {"entry_price": float, "entry_time": datetime}
equity   = 100_000.0   # starting paper capital in INR


def _in_trading_window() -> bool:
    now = datetime.now().time()
    return START_TIME <= now <= END_TIME


def _fetch_candles() -> pd.DataFrame:
    """Fetch the last LOOKBACK_MINS 1-min candles from Yahoo Finance."""
    df = yf.download(
        tickers=TICKER,
        period=f"{LOOKBACK_MINS + 5}m",
        interval="1m",
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.tail(LOOKBACK_MINS)


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"]     = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["vol_avg20"]= df["volume"].rolling(20).mean()
    df["vol_spike"]= df["volume"] > VOL_MULTIPLIER * df["vol_avg20"]
    return df


def _log_trade(action: str, price: float, reason: str, pnl: float = 0.0):
    row = {
        "timestamp": datetime.now().isoformat(),
        "action":    action,
        "price":     round(price, 2),
        "reason":    reason,
        "pnl":       round(pnl, 2),
        "equity":    round(equity, 2),
    }
    df_row = pd.DataFrame([row])
    header = not os.path.exists(TRADE_LOG_PATH)
    df_row.to_csv(TRADE_LOG_PATH, mode="a", header=header, index=False)
    log.info(f"{action:5s}  price={price:.2f}  reason={reason}  pnl={pnl:.2f}  equity={equity:.2f}")


def run_tick():
    global position, equity

    if not _in_trading_window():
        log.info("Outside trading window — skipping")
        return

    df = _fetch_candles()
    if df is None or len(df) < EMA_SLOW + 5:
        log.warning("Not enough data yet")
        return

    df = _compute_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = float(last["close"])

    # ---- EXIT LOGIC ----
    if position is not None:
        entry = position["entry_price"]
        gain  = (price - entry) / entry

        if gain >= TARGET_PCT:
            pnl = equity * gain - equity * BROKERAGE_PCT
            equity += pnl
            _log_trade("EXIT", price, "TARGET_HIT", pnl)
            position = None
            return

        if gain <= -STOP_PCT:
            pnl = equity * gain - equity * BROKERAGE_PCT
            equity += pnl
            _log_trade("EXIT", price, "STOP_LOSS", pnl)
            position = None
            return

    # ---- ENTRY LOGIC ----
    if position is None:
        price_above_vwap = float(last["close"]) > float(last["vwap"])
        ema_cross_up = (
            float(last["ema_fast"]) > float(last["ema_slow"]) and
            float(prev["ema_fast"]) <= float(prev["ema_slow"])
        )
        vol_spike = bool(last["vol_spike"])

        if price_above_vwap and ema_cross_up and vol_spike:
            position = {"entry_price": price, "entry_time": datetime.now()}
            _log_trade("BUY", price, "SIGNAL_TRIGGERED")

    # Force-close at end of session
    now = datetime.now().time()
    if position is not None and now >= dtime(11, 29):
        entry = position["entry_price"]
        pnl = equity * ((price - entry) / entry) - equity * BROKERAGE_PCT
        equity += pnl
        _log_trade("EXIT", price, "SESSION_END", pnl)
        position = None


def main():
    log.info("Paper trading started. Capital: INR %.2f", equity)
    schedule.every(1).minutes.do(run_tick)
    # Run once immediately on start
    run_tick()
    while True:
        schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    main()
