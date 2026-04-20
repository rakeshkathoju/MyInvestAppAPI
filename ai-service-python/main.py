"""
AI Service — FastAPI
--------------------
Exposes:
  POST /predict   — predict BUY / SELL / HOLD for a given stock
  POST /train     — train / retrain the model on fresh downloaded data
  GET  /health    — liveness check

The model is a Random Forest trained on labelled 1-min candles.
Label = 1 (BUY) if close rises >= TARGET_PCT within the next FORWARD_BARS candles.
"""

import os
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# ---------- shared indicator logic (copied inline to keep service self-contained) ----------

TARGET_PCT   = 0.006
FORWARD_BARS = 6           # look 6 minutes ahead for the label
MODEL_PATH   = "model.joblib"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="AI Trading Signal Service")

# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------

def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"]     = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    df["ema_fast"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=21, adjust=False).mean()
    df["vol_avg"]  = df["volume"].rolling(20).mean()
    df["vol_ratio"]= df["volume"] / df["vol_avg"].replace(0, np.nan)

    delta    = df["close"].diff()
    gain     = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss     = (-delta).clip(lower=0).ewm(com=13, min_periods=14).mean()
    df["rsi"]= 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]       = tr.ewm(span=14, adjust=False).mean()
    df["vwap_gap"]  = (df["close"] - df["vwap"]) / df["vwap"]
    df["ema_ratio"] = df["ema_fast"] / df["ema_slow"] - 1
    df["body_size"] = (df["close"] - df["open"]).abs() / df["close"]
    df["candle_dir"]= (df["close"] > df["open"]).astype(int)
    df["momentum_3"]= df["close"].pct_change(3)
    return df


FEATURE_COLS = [
    "vwap_gap", "ema_ratio", "vol_ratio",
    "rsi", "atr", "body_size", "candle_dir", "momentum_3",
]


def _make_labels(df: pd.DataFrame) -> pd.Series:
    future_max = df["close"].shift(-FORWARD_BARS).rolling(FORWARD_BARS).max()
    return ((future_max - df["close"]) / df["close"] >= TARGET_PCT).astype(int)


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_model = None

def _load_model():
    global _model
    if Path(MODEL_PATH).exists():
        _model = joblib.load(MODEL_PATH)
        log.info("Model loaded from %s", MODEL_PATH)
    else:
        log.warning("No trained model found at %s. Call POST /train first.", MODEL_PATH)


_load_model()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    ticker: str = "ICICIBANK.NS"
    # Optionally pass pre-computed feature values directly
    features: dict | None = None


class TrainRequest(BaseModel):
    ticker: str = "ICICIBANK.NS"
    days: int = 7          # yfinance cap for 1-min data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "model_ready": _model is not None}


@app.post("/train")
def train(req: TrainRequest):
    log.info("Training on %s, last %d days of 1-min data", req.ticker, req.days)
    df = yf.download(
        tickers=req.ticker,
        period=f"{req.days}d",
        interval="1m",
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        raise HTTPException(status_code=400, detail="No data returned from Yahoo Finance")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]

    df = _build_features(df)
    df["label"] = _make_labels(df)
    df = df.dropna(subset=FEATURE_COLS + ["label"])

    X = df[FEATURE_COLS].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    clf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    report = classification_report(y_test, clf.predict(X_test), output_dict=True)
    joblib.dump(clf, MODEL_PATH)

    global _model
    _model = clf
    log.info("Model trained and saved to %s", MODEL_PATH)

    return {
        "status": "trained",
        "train_samples": len(X_train),
        "test_samples":  len(X_test),
        "accuracy":      round(report["accuracy"], 4),
        "precision_buy": round(report.get("1", {}).get("precision", 0), 4),
        "recall_buy":    round(report.get("1", {}).get("recall", 0), 4),
    }


@app.post("/predict")
def predict(req: PredictRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not trained yet. Call POST /train first.")

    # If raw feature dict is passed, use it directly
    if req.features:
        try:
            x = np.array([[req.features[c] for c in FEATURE_COLS]])
        except KeyError as e:
            raise HTTPException(status_code=422, detail=f"Missing feature: {e}")
    else:
        # Download latest candles and compute features live
        df = yf.download(
            tickers=req.ticker,
            period="60m",
            interval="1m",
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            raise HTTPException(status_code=400, detail="No data returned from Yahoo Finance")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df = _build_features(df)
        row = df.dropna(subset=FEATURE_COLS).iloc[-1]
        x   = np.array([[row[c] for c in FEATURE_COLS]])

    prob    = _model.predict_proba(x)[0]
    buy_prob = float(prob[1]) if len(prob) > 1 else 0.0
    signal  = "BUY" if buy_prob >= 0.55 else "HOLD"

    return {
        "ticker":   req.ticker,
        "signal":   signal,
        "buy_prob": round(buy_prob, 4),
    }
