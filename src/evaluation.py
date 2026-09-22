"""
evaluation.py
-------------
Computes forecast accuracy metrics and produces structured result tables.

Metrics:
  - MAPE  (Mean Absolute Percentage Error) — primary KPI
  - RMSE  (Root Mean Squared Error)
  - MAE   (Mean Absolute Error)
  - R²    (Coefficient of Determination)

Also estimates:
  - Stockout risk per product
  - Overstock risk per product
  - Safety stock recommendations
"""

import numpy as np
import pandas as pd


# ─── Core metrics ─────────────────────────────────────────────────────────────
def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    mask = actual > 0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def r2(actual: np.ndarray, predicted: np.ndarray) -> float:
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - actual.mean()) ** 2)
    return float(1 - ss_res / (ss_tot + 1e-9))


def accuracy_pct(mape_val: float) -> float:
    """Convert MAPE to accuracy % (capped at 100)."""
    return round(max(0.0, 100.0 - mape_val), 2)


# ─── Per-product evaluation ────────────────────────────────────────────────────
def evaluate_per_product(result_df: pd.DataFrame, pred_col: str = "ensemble_pred") -> pd.DataFrame:
    """
    Args:
        result_df: DataFrame with columns [product, sales, <pred_col>]
        pred_col:  column containing predictions
    Returns:
        summary DataFrame per product
    """
    rows = []
    for product, grp in result_df.groupby("product"):
        actual = grp["sales"].values
        pred   = grp[pred_col].values
        rows.append({
            "product":      product,
            "MAPE (%)":     round(mape(actual, pred), 2),
            "RMSE":         round(rmse(actual, pred), 2),
            "MAE":          round(mae(actual, pred), 2),
            "R²":           round(r2(actual, pred), 4),
            "Accuracy (%)": accuracy_pct(mape(actual, pred)),
            "n_samples":    len(actual),
        })
    summary = pd.DataFrame(rows).sort_values("MAPE (%)")
    return summary


def evaluate_overall(result_df: pd.DataFrame, pred_col: str = "ensemble_pred") -> dict:
    actual = result_df["sales"].values
    pred   = result_df[pred_col].values
    return {
        "overall_MAPE":     round(mape(actual, pred), 2),
        "overall_RMSE":     round(rmse(actual, pred), 2),
        "overall_MAE":      round(mae(actual, pred), 2),
        "overall_R2":       round(r2(actual, pred), 4),
        "overall_accuracy": accuracy_pct(mape(actual, pred)),
    }


# ─── Inventory risk analysis ───────────────────────────────────────────────────
def inventory_risk_analysis(result_df: pd.DataFrame,
                             pred_col: str = "ensemble_pred",
                             service_level: float = 0.95) -> pd.DataFrame:
    """
    Estimates stockout and overstock risk using forecast variance.

    service_level: 0.95 -> Z = 1.645 (95% service level)
    Safety stock  = Z × std(forecast_error) × sqrt(lead_time)
    lead_time     = 7 days (assumed)
    """
    from scipy.stats import norm
    Z         = norm.ppf(service_level)
    lead_time = 7  # days

    rows = []
    for product, grp in result_df.groupby("product"):
        actual  = grp["sales"].values
        pred    = grp[pred_col].values
        errors  = actual - pred
        std_err = np.std(errors)

        safety_stock   = round(Z * std_err * np.sqrt(lead_time))
        avg_daily_sales = round(np.mean(actual), 1)
        avg_forecast    = round(np.mean(pred), 1)

        # Stockout: model under-predicts -> actual > forecast
        under_predict_rate = float(np.mean(actual > pred * 1.10))
        # Overstock: model over-predicts -> forecast >> actual
        over_predict_rate  = float(np.mean(pred > actual * 1.10))

        bias = float(np.mean(pred - actual))

        rows.append({
            "product":            product,
            "avg_daily_sales":    avg_daily_sales,
            "avg_daily_forecast": avg_forecast,
            "forecast_bias":      round(bias, 2),
            "safety_stock":       int(max(0, safety_stock)),
            "stockout_risk (%)":  round(under_predict_rate * 100, 1),
            "overstock_risk (%)": round(over_predict_rate  * 100, 1),
            "reorder_point":      int(avg_daily_sales * lead_time + max(0, safety_stock)),
        })

    risk_df = pd.DataFrame(rows)
    risk_df["risk_level"] = risk_df["stockout_risk (%)"].apply(
        lambda x: "🔴 High" if x > 20 else ("🟡 Medium" if x > 10 else "🟢 Low")
    )
    return risk_df.sort_values("stockout_risk (%)", ascending=False)


def print_summary(overall: dict, per_product: pd.DataFrame):
    print("\n" + "=" * 60)
    print("  OVERALL FORECAST PERFORMANCE")
    print("=" * 60)
    for k, v in overall.items():
        print(f"  {k:<25}: {v}")
    print("\n" + "=" * 60)
    print("  PER-PRODUCT METRICS")
    print("=" * 60)
    print(per_product.to_string(index=False))
    print("=" * 60)
