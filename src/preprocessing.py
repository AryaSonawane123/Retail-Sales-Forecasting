"""
preprocessing.py
----------------
Cleans the raw sales dataset:
  1. Parse dates & sort chronologically
  2. Fill missing sales values (forward-fill then interpolate)
  3. Cap outliers via Winsorization (1.5 × IQR per product)
  4. Encode categorical columns
  5. Train / Validation / Test split  (70 / 15 / 15, chronological)
"""

import os
import numpy as np
import pandas as pd
from scipy import stats

RAW_PATH       = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "sales_data.csv")
PROCESSED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "sales_clean.csv")


# ─── Loaders ──────────────────────────────────────────────────────────────────
def load_raw(path: str = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df.sort_values(["product", "date"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(f"[preprocessing] Loaded {len(df):,} rows, {df['product'].nunique()} products.")
    return df


# ─── Missing value handler ────────────────────────────────────────────────────
def fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill then linear interpolation per product group."""
    original_missing = df["sales"].isna().sum()
    df["sales"] = (
        df.groupby("product")["sales"]
        .transform(lambda s: s.ffill().interpolate(method="linear"))
    )
    remaining = df["sales"].isna().sum()
    print(f"[preprocessing] Missing values: {original_missing} -> {remaining}")
    return df


# ─── Outlier capping (Winsorization) ─────────────────────────────────────────
def cap_outliers(df: pd.DataFrame, iqr_multiplier: float = 1.5) -> pd.DataFrame:
    """Cap outliers per product using IQR method."""
    clipped = 0
    def _cap(s: pd.Series) -> pd.Series:
        nonlocal clipped
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr    = q3 - q1
        lower  = q1 - iqr_multiplier * iqr
        upper  = q3 + iqr_multiplier * iqr
        mask   = (s < lower) | (s > upper)
        clipped += mask.sum()
        return s.clip(lower, upper)

    df["sales"] = df.groupby("product")["sales"].transform(_cap)
    print(f"[preprocessing] Outliers capped: {clipped} values.")
    return df


# ─── Feature scaling ──────────────────────────────────────────────────────────
def add_price_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """Price relative to product mean — removes scale difference across products."""
    df["price_ratio"] = df.groupby("product")["price"].transform(lambda s: s / s.mean())
    return df


# ─── Train / Val / Test split ─────────────────────────────────────────────────
def chronological_split(df: pd.DataFrame, train: float = 0.70, val: float = 0.15):
    """
    Split CHRONOLOGICALLY (no shuffle) to prevent data leakage.
    Returns (train_df, val_df, test_df)
    """
    dates  = df["date"].sort_values().unique()
    n      = len(dates)
    t_end  = dates[int(n * train) - 1]
    v_end  = dates[int(n * (train + val)) - 1]

    train_df = df[df["date"] <= t_end].copy()
    val_df   = df[(df["date"] > t_end) & (df["date"] <= v_end)].copy()
    test_df  = df[df["date"] > v_end].copy()

    print(f"[preprocessing] Split — Train: {len(train_df):,} | Val: {len(val_df):,} | Test: {len(test_df):,}")
    return train_df, val_df, test_df


# ─── Pipeline ─────────────────────────────────────────────────────────────────
def run_preprocessing(raw_path: str = RAW_PATH, out_path: str = PROCESSED_PATH) -> pd.DataFrame:
    df = load_raw(raw_path)
    df = fill_missing(df)
    df = cap_outliers(df)
    df = add_price_ratio(df)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[preprocessing] Saved cleaned data -> {out_path}")
    return df


if __name__ == "__main__":
    run_preprocessing()
