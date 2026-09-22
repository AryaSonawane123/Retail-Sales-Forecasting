"""
feature_engineering.py
-----------------------
Creates a rich feature set for the sales forecasting model:

  Lag features      : sales t-1, t-7, t-14, t-28
  Rolling features  : 7-day & 30-day rolling mean / std
  Calendar features : day_of_week, week_of_year, month, quarter, is_weekend
  Fourier terms     : sin/cos harmonics to capture annual seasonality
  Trend feature     : integer day index (linear trend)
  External features : is_promotion, is_holiday, weather_index, price_ratio
"""

import os
import numpy as np
import pandas as pd

CLEAN_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "sales_clean.csv")
FEAT_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "sales_features.csv")

LAG_DAYS    = [1, 7, 14, 28]
ROLL_WINDOWS = [7, 30]
N_FOURIER   = 3   # number of sin/cos pairs


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    for lag in LAG_DAYS:
        df[f"sales_lag_{lag}"] = df.groupby("product")["sales"].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    for w in ROLL_WINDOWS:
        df[f"rolling_mean_{w}"] = (
            df.groupby("product")["sales"]
            .transform(lambda s: s.shift(1).rolling(w, min_periods=1).mean())
        )
        df[f"rolling_std_{w}"] = (
            df.groupby("product")["sales"]
            .transform(lambda s: s.shift(1).rolling(w, min_periods=1).std().fillna(0))
        )
    return df


def add_fourier_terms(df: pd.DataFrame, period: int = 365) -> pd.DataFrame:
    day_idx = (df["date"] - df["date"].min()).dt.days
    for k in range(1, N_FOURIER + 1):
        df[f"sin_{k}"] = np.sin(2 * np.pi * k * day_idx / period)
        df[f"cos_{k}"] = np.cos(2 * np.pi * k * day_idx / period)
    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    df["day_of_week"]   = df["date"].dt.dayofweek
    df["week_of_year"]  = df["date"].dt.isocalendar().week.astype(int)
    df["month"]         = df["date"].dt.month
    df["quarter"]       = df["date"].dt.quarter
    df["year"]          = df["date"].dt.year
    df["is_weekend"]    = (df["day_of_week"] >= 5).astype(int)
    df["day_of_year"]   = df["date"].dt.dayofyear
    return df


def add_trend_feature(df: pd.DataFrame) -> pd.DataFrame:
    """Integer day index as a linear trend proxy."""
    df["trend_index"] = (df["date"] - df["date"].min()).dt.days
    return df


def add_product_encoding(df: pd.DataFrame) -> pd.DataFrame:
    df["product_id"] = df["product"].astype("category").cat.codes
    return df


def build_feature_set(clean_path: str = CLEAN_PATH, out_path: str = FEAT_PATH) -> pd.DataFrame:
    df = pd.read_csv(clean_path, parse_dates=["date"])
    df.sort_values(["product", "date"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    df = add_calendar_features(df)
    df = add_trend_feature(df)
    df = add_lag_features(df)
    df = add_rolling_features(df)
    df = add_fourier_terms(df)
    df = add_product_encoding(df)

    # Ensure required columns exist from preprocessing
    for col in ["is_promotion", "is_holiday", "weather_index", "price_ratio"]:
        if col not in df.columns:
            df[col] = 0

    # Drop rows with NaN from lag creation (first 28 days per product)
    before = len(df)
    df.dropna(subset=[f"sales_lag_{LAG_DAYS[-1]}"], inplace=True)
    print(f"[feature_engineering] Dropped {before - len(df)} rows (lag warm-up).")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[feature_engineering] Feature set: {df.shape} -> {out_path}")
    return df


# Convenience: return column names used as model features
def get_feature_columns() -> list:
    lag_cols     = [f"sales_lag_{d}" for d in LAG_DAYS]
    roll_cols    = [f"rolling_mean_{w}" for w in ROLL_WINDOWS] + \
                   [f"rolling_std_{w}"  for w in ROLL_WINDOWS]
    fourier_cols = [f"{fn}_{k}" for k in range(1, N_FOURIER+1) for fn in ("sin", "cos")]
    cal_cols     = ["day_of_week", "week_of_year", "month", "quarter",
                    "is_weekend", "day_of_year", "trend_index", "year"]
    ext_cols     = ["is_promotion", "is_holiday", "weather_index", "price_ratio", "product_id"]
    return lag_cols + roll_cols + fourier_cols + cal_cols + ext_cols


if __name__ == "__main__":
    build_feature_set()
