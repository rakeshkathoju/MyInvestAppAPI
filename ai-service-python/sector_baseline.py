"""
Prototype: sector winner baseline + RandomForest regression

Usage: python sector_baseline.py

Downloads daily ETF data for a set of sector ETFs, builds simple features,
trains a RandomForest to predict next-day returns, and compares to a
rule-based baseline (past-3-day momentum).

Outputs a short backtest summary (hit rate and average realized return).
"""
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import RandomForestRegressor


SECTORS = [
    "XLF", "XLK", "XLY", "XLE", "XLI", "XLB", "XLV", "XLU", "XLC", "XLP", "XLRE"
]


def download_data(tickers, period_days=365):
    end = dt.date.today()
    start = end - dt.timedelta(days=period_days)
    df = yf.download(tickers=tickers, start=start.isoformat(), end=end.isoformat(), interval="1d", progress=False)
    # yfinance returns MultiIndex columns; use Adj Close when available else Close
    if isinstance(df.columns, pd.MultiIndex) and "Adj Close" in df.columns.levels[0]:
        prices = df["Adj Close"].copy()
    else:
        # fall back
        prices = df["Close"].copy()
    prices.columns = [c for c in prices.columns]
    prices = prices.dropna(how="all")
    return prices


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    # prices: DataFrame indexed by date, columns=sectors
    df_list = []
    for sector in prices.columns:
        s = prices[sector].dropna()
        if s.empty:
            continue
        f = pd.DataFrame(index=s.index)
        f["sector"] = sector
        f["close"] = s
        f["ret_1d"] = s.pct_change(1)
        f["ret_3d"] = s.pct_change(3)
        f["ret_5d"] = s.pct_change(5)
        f["vol_5d"] = s.pct_change().rolling(5).std()
        f["next_ret_1d"] = s.pct_change().shift(-1)
        df_list.append(f)
    allf = pd.concat(df_list).dropna()
    return allf


def prepare_ml_data(allf: pd.DataFrame):
    # One-hot encode sector; features are ret_1d,ret_3d,ret_5d,vol_5d + sector dummies
    feats = ["ret_1d", "ret_3d", "ret_5d", "vol_5d"]
    X = allf[feats].copy()
    X = pd.get_dummies(allf["sector"]).join(X)
    y = allf["next_ret_1d"].copy()
    return X, y


def backtest_rule(allf: pd.DataFrame, test_dates):
    # Rule: pick sector with highest ret_3d on previous close
    wins = 0
    rets = []
    for d in test_dates:
        today = pd.to_datetime(d).normalize()
        try:
            day_rows = allf.loc[today]
        except KeyError:
            continue
        if isinstance(day_rows, pd.Series):
            day_rows = day_rows.to_frame().T
        if "ret_3d" not in day_rows.columns:
            continue
        # choose sector with max ret_3d
        chosen = day_rows["ret_3d"].idxmax()
        actual = day_rows.loc[chosen, "next_ret_1d"]
        actuals = day_rows["next_ret_1d"].dropna()
        if actuals.empty:
            continue
        rank_top = actual >= actuals.max()
        wins += int(rank_top)
        rets.append(float(actual))
    return {"days": len(rets), "hit_rate": wins / max(1, len(rets)), "avg_return": np.mean(rets) if rets else 0}


def backtest_model(model, allf: pd.DataFrame, test_dates, model_feature_columns):
    wins = 0
    rets = []
    feats = ["ret_1d", "ret_3d", "ret_5d", "vol_5d"]
    for d in test_dates:
        today = pd.to_datetime(d).normalize()
        try:
            day_rows = allf.loc[today]
        except KeyError:
            continue
        if isinstance(day_rows, pd.Series):
            day_rows = day_rows.to_frame().T
        X_day = day_rows[feats].copy()
        X_day = pd.get_dummies(day_rows["sector"]).join(X_day)
        for c in model_feature_columns:
            if c not in X_day.columns:
                X_day[c] = 0.0
        X_day = X_day[model_feature_columns]
        preds = model.predict(X_day.values)
        chosen_idx = np.argmax(preds)
        chosen_sector = X_day.index[chosen_idx]
        actual = day_rows.loc[chosen_sector, "next_ret_1d"]
        actuals = day_rows["next_ret_1d"].dropna()
        if actuals.empty:
            continue
        rank_top = actual >= actuals.max()
        wins += int(rank_top)
        rets.append(float(actual))
    return {"days": len(rets), "hit_rate": wins / max(1, len(rets)), "avg_return": np.mean(rets) if rets else 0}


if __name__ == "__main__":
    print("Downloading price data for sectors:", SECTORS)
    prices = download_data(SECTORS, period_days=400)
    if prices.empty:
        print("No price data downloaded — aborting")
        raise SystemExit(1)

    print("Building features")
    allf = build_features(prices)

    allf = allf.reset_index()
    if "level_0" in allf.columns:
        allf = allf.rename(columns={allf.columns[0]: "date"})
    if "date" not in allf.columns:
        allf["date"] = allf.index
    allf["date"] = pd.to_datetime(allf["date"]).dt.normalize()
    allf = allf.set_index(["date", "sector"]).sort_index()

    X, y = prepare_ml_data(allf.reset_index())
    model_feature_columns = list(X.columns)

    all_dates = sorted(set(allf.reset_index()["date"]))
    split = int(len(all_dates) * 0.7)
    train_dates = all_dates[:split]
    test_dates = all_dates[split:]

    df_rows = allf.reset_index()
    train_idx = df_rows["date"].isin(train_dates)
    test_idx = df_rows["date"].isin(test_dates)
    X_train = X[train_idx.values]
    y_train = y[train_idx.values]

    print("Training RandomForestRegressor")
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
    model.fit(X_train.fillna(0).values, y_train.fillna(0).values)

    print("Evaluating on test set")
    rule_res = backtest_rule(allf.reset_index().set_index(["date", "sector"]), test_dates)
    model_res = backtest_model(model, allf.reset_index().set_index(["date", "sector"]), test_dates, model_feature_columns)

    print("--- Baseline (3-day momentum) ---")
    print(f"Days evaluated: {rule_res['days']}")
    print(f"Hit rate (top-1): {rule_res['hit_rate']:.3f}")
    print(f"Avg realized return: {rule_res['avg_return']:.4f}")

    print("--- Model (RandomForest) ---")
    print(f"Days evaluated: {model_res['days']}")
    print(f"Hit rate (top-1): {model_res['hit_rate']:.3f}")
    print(f"Avg realized return: {model_res['avg_return']:.4f}")
