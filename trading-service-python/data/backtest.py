import os
import sys
import pandas as pd
import numpy as np
import vectorbt as vbt

# ---------- SETTINGS ----------
TARGET_PCT = 0.006      # 0.6%
STOP_PCT = 0.004        # 0.4%
VOL_MULTIPLIER = 1.5
EMA_FAST = 9
EMA_SLOW = 21
START_TIME = "09:20"
END_TIME = "11:30"
BROKERAGE_PCT = 0.0005   # 0.05% slippage+cost
# ------------------------------

# Load data
CSV_PATH = "data/ICICIBANK_1min.csv"
if not os.path.exists(CSV_PATH):
    print(f"ERROR: Data file not found: '{CSV_PATH}'")
    print("Please place ICICIBANK_1min.csv inside the data/ folder before running this script.")
    sys.exit(1)
df = pd.read_csv(CSV_PATH, parse_dates=['datetime'])
df.set_index('datetime', inplace=True)

# Keep only trading window
df = df.between_time(START_TIME, END_TIME)

# ---------- INDICATORS ----------

# VWAP
typical_price = (df['high'] + df['low'] + df['close']) / 3
vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
df['vwap'] = vwap

# EMAs
df['ema_fast'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()
df['ema_slow'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()

# Volume condition
df['vol_avg20'] = df['volume'].rolling(20).mean()
df['vol_spike'] = df['volume'] > VOL_MULTIPLIER * df['vol_avg20']

# ---------- ENTRY CONDITION ----------
price_above_vwap = df['close'] > df['vwap']
ema_cross_up = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))

entries = price_above_vwap & ema_cross_up & df['vol_spike']

# ---------- EXIT CONDITION (dynamic using target/SL) ----------
close = df['close']

# Create portfolio with vectorbt
pf = vbt.Portfolio.from_signals(
    close=close,
    entries=entries,
    exits=None,  # we will use TP/SL
    sl_stop=STOP_PCT,
    tp_stop=TARGET_PCT,
    fees=BROKERAGE_PCT,
    freq="1min"
)

# ---------- RESULTS ----------
print("\n========== BACKTEST RESULTS ==========\n")
print(pf.stats())

# Plot equity curve
pf.plot().show()