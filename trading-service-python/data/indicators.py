"""
indicators.py
-------------
Shared technical indicator calculations used by backtest, paper_trade,
live_trade, and the AI service.
"""

import pandas as pd
import numpy as np


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Cumulative VWAP from the start of the slice."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    return df


def add_emas(df: pd.DataFrame, fast: int = 9, slow: int = 21) -> pd.DataFrame:
    df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()
    return df


def add_volume_spike(df: pd.DataFrame, window: int = 20, multiplier: float = 1.5) -> pd.DataFrame:
    df["vol_avg"] = df["volume"].rolling(window).mean()
    df["vol_spike"] = df["volume"] > multiplier * df["vol_avg"]
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.ewm(span=period, adjust=False).mean()
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all indicators and return a DataFrame with feature columns.
    Used for both ML training (backtest data) and live prediction.
    """
    df = df.copy()
    df = add_vwap(df)
    df = add_emas(df)
    df = add_volume_spike(df)
    df = add_rsi(df)
    df = add_atr(df)

    # Derived features
    df["vwap_gap"]    = (df["close"] - df["vwap"]) / df["vwap"]
    df["ema_ratio"]   = df["ema_fast"] / df["ema_slow"] - 1
    df["vol_ratio"]   = df["volume"] / df["vol_avg"].replace(0, np.nan)
    df["body_size"]   = (df["close"] - df["open"]).abs() / df["close"]
    df["candle_dir"]  = (df["close"] > df["open"]).astype(int)
    df["momentum_3"]  = df["close"].pct_change(3)

    return df


FEATURE_COLS = [
    "vwap_gap", "ema_ratio", "vol_ratio",
    "rsi", "atr", "body_size", "candle_dir", "momentum_3",
]
