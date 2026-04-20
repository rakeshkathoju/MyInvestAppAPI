"""
live_trade.py
-------------
Live trading using Zerodha Kite Connect API.
Places real market orders based on the same strategy as backtest.py.

Prerequisites:
  1. Install kiteconnect:  pip install kiteconnect
  2. Set KITE_API_KEY and KITE_ACCESS_TOKEN in your .env file
     (Generate the access token each morning via Kite login flow)

Usage:
    python3 data/live_trade.py
"""

import os
import time
import logging
from datetime import datetime, time as dtime, date

import pandas as pd
from dotenv import load_dotenv
import schedule

load_dotenv()

# ---------- SETTINGS ----------
TICKER         = "ICICIBANK"
EXCHANGE       = "NSE"
QUANTITY       = 1           # shares per trade — increase after testing
TARGET_PCT     = 0.006
STOP_PCT       = 0.004
VOL_MULTIPLIER = 1.5
EMA_FAST       = 9
EMA_SLOW       = 21
START_TIME     = dtime(9, 20)
END_TIME       = dtime(11, 30)
LOOKBACK_MINS  = 60
# ------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# Lazy import so the file can be opened even without kiteconnect installed
try:
    from kiteconnect import KiteConnect
    _KITE_AVAILABLE = True
except ImportError:
    _KITE_AVAILABLE = False
    log.warning("kiteconnect not installed. Run: pip install kiteconnect")

position_entry_price = None


def _get_kite() -> "KiteConnect":
    if not _KITE_AVAILABLE:
        raise RuntimeError("kiteconnect package is not installed.")
    api_key    = os.environ.get("KITE_API_KEY")
    access_token = os.environ.get("KITE_ACCESS_TOKEN")
    if not api_key or not access_token:
        raise RuntimeError(
            "KITE_API_KEY and KITE_ACCESS_TOKEN must be set in your .env file.\n"
            "Generate today's access token at https://kite.trade/connect/login?api_key=<YOUR_KEY>"
        )
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def _fetch_historical(kite: "KiteConnect") -> pd.DataFrame:
    instrument_token = kite.ltp(f"{EXCHANGE}:{TICKER}")[f"{EXCHANGE}:{TICKER}"]["instrument_token"]
    today = date.today()
    records = kite.historical_data(
        instrument_token=instrument_token,
        from_date=today,
        to_date=today,
        interval="minute",
    )
    df = pd.DataFrame(records)
    df.rename(columns={"date": "datetime"}, inplace=True)
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(None)
    df.set_index("datetime", inplace=True)
    return df.tail(LOOKBACK_MINS)


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"]     = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["vol_avg20"]= df["volume"].rolling(20).mean()
    df["vol_spike"]= df["volume"] > VOL_MULTIPLIER * df["vol_avg20"]
    return df


def _place_order(kite: "KiteConnect", transaction_type: str) -> str:
    order_id = kite.place_order(
        variety=KiteConnect.VARIETY_REGULAR,
        exchange=EXCHANGE,
        tradingsymbol=TICKER,
        transaction_type=transaction_type,
        quantity=QUANTITY,
        order_type=KiteConnect.ORDER_TYPE_MARKET,
        product=KiteConnect.PRODUCT_MIS,   # intraday
    )
    log.info(f"Order placed: {transaction_type}  order_id={order_id}")
    return order_id


def run_tick():
    global position_entry_price

    now = datetime.now().time()
    if not (START_TIME <= now <= END_TIME):
        log.info("Outside trading window")
        return

    try:
        kite = _get_kite()
        df   = _fetch_historical(kite)
    except Exception as exc:
        log.error(f"Failed to fetch data: {exc}")
        return

    if len(df) < EMA_SLOW + 5:
        log.warning("Not enough candles yet")
        return

    df   = _compute_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = float(last["close"])

    # ---- EXIT ----
    if position_entry_price is not None:
        gain = (price - position_entry_price) / position_entry_price
        if gain >= TARGET_PCT:
            _place_order(kite, KiteConnect.TRANSACTION_TYPE_SELL)
            log.info(f"EXIT: target hit  gain={gain*100:.2f}%")
            position_entry_price = None
            return
        if gain <= -STOP_PCT:
            _place_order(kite, KiteConnect.TRANSACTION_TYPE_SELL)
            log.info(f"EXIT: stop loss   gain={gain*100:.2f}%")
            position_entry_price = None
            return

    # ---- ENTRY ----
    if position_entry_price is None:
        price_above_vwap = price > float(last["vwap"])
        ema_cross_up = (
            float(last["ema_fast"]) > float(last["ema_slow"]) and
            float(prev["ema_fast"]) <= float(prev["ema_slow"])
        )
        vol_spike = bool(last["vol_spike"])

        if price_above_vwap and ema_cross_up and vol_spike:
            _place_order(kite, KiteConnect.TRANSACTION_TYPE_BUY)
            position_entry_price = price

    # ---- Force-close at session end ----
    if position_entry_price is not None and now >= dtime(11, 29):
        _place_order(kite, KiteConnect.TRANSACTION_TYPE_SELL)
        log.info("EXIT: session end force-close")
        position_entry_price = None


def main():
    log.info("Live trading started — real orders will be placed!")
    schedule.every(1).minutes.do(run_tick)
    run_tick()
    while True:
        schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    main()
