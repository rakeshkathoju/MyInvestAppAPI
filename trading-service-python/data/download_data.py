"""
download_data.py
----------------
Downloads ICICIBANK 1-minute OHLCV data from Yahoo Finance and saves it
as data/ICICIBANK_1min.csv in the format expected by backtest.py.

Note: yfinance provides up to 7 days of 1-min data for free.
Run this script daily to keep your local dataset fresh.

Usage:
    python3 data/download_data.py
"""

import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

TICKER = "ICICIBANK.NS"   # NSE ticker on Yahoo Finance
INTERVAL = "1m"
DAYS_BACK = 7             # yfinance cap for 1-min data
OUTPUT_PATH = "data/ICICIBANK_1min.csv"


def download():
    end = datetime.today()
    start = end - timedelta(days=DAYS_BACK)

    print(f"Downloading {TICKER} 1-min data from {start.date()} to {end.date()} ...")
    df = yf.download(
        tickers=TICKER,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval=INTERVAL,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        print("ERROR: No data returned. Check your internet connection or ticker symbol.")
        return

    # Flatten multi-level columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Normalise column names to lowercase
    df.columns = [c.lower() for c in df.columns]

    # Reset index so 'datetime' becomes a regular column
    df.index.name = "datetime"
    df = df.reset_index()

    # Keep only the columns backtest.py needs
    df = df[["datetime", "open", "high", "low", "close", "volume"]]

    # Convert timezone-aware timestamps to naive (IST already, strip tz info)
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(None)

    # Append to existing CSV (or create new one)
    if os.path.exists(OUTPUT_PATH):
        existing = pd.read_csv(OUTPUT_PATH, parse_dates=["datetime"])
        combined = pd.concat([existing, df]).drop_duplicates(subset="datetime").sort_values("datetime")
        combined.to_csv(OUTPUT_PATH, index=False)
        print(f"Updated {OUTPUT_PATH}  ({len(combined)} total rows)")
    else:
        df.to_csv(OUTPUT_PATH, index=False)
        print(f"Created {OUTPUT_PATH}  ({len(df)} rows)")


if __name__ == "__main__":
    download()
