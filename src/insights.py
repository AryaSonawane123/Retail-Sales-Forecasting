"""
insights.py
-----------
Generates actionable business insights from the forecasting results:

  1. Top products at risk of stockout / overstock
  2. Seasonal patterns per category
  3. Promotional effectiveness analysis
  4. Feature importance from XGBoost
  5. Monthly demand trends
  6. Recommendations summary
"""

import os
import json
import numpy as np
import pandas as pd


# ─── Seasonal analysis ────────────────────────────────────────────────────────
def monthly_demand_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Average sales by product × month."""
    trend = (
        df.groupby(["product", "month"])["sales"]
        .mean()
        .round(1)
        .reset_index()
        .rename(columns={"sales": "avg_sales"})
    )
    trend["month_name"] = pd.to_datetime(trend["month"], format="%m").dt.strftime("%b")
    return trend


def peak_months(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Identify the 3 peak selling months per product."""
    return (
        monthly_df.sort_values("avg_sales", ascending=False)
        .groupby("product")
        .head(3)
        .sort_values(["product", "avg_sales"], ascending=[True, False])
    )


# ─── Promotional effectiveness ─────────────────────────────────────────────────
def promo_effectiveness(df: pd.DataFrame) -> pd.DataFrame:
    """Compare average sales during vs. outside promotions."""
    grp = df.groupby(["product", "is_promotion"])["sales"].mean().unstack(fill_value=0)
    grp.columns = ["non_promo_avg", "promo_avg"]
    grp["promo_lift (%)"] = ((grp["promo_avg"] - grp["non_promo_avg"]) /
                              (grp["non_promo_avg"] + 1e-9) * 100).round(1)
    return grp.reset_index().sort_values("promo_lift (%)", ascending=False)


# ─── Day-of-week patterns ─────────────────────────────────────────────────────
def dow_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """Average sales by day of week (0=Mon … 6=Sun)."""
    day_names = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"}
    pattern = (
        df.groupby(["product", "day_of_week"])["sales"]
        .mean().round(1).reset_index()
    )
    pattern["day"] = pattern["day_of_week"].map(day_names)
    return pattern


# ─── Feature importance ────────────────────────────────────────────────────────
def get_feature_importance(xgb_forecaster) -> pd.DataFrame:
    fi = xgb_forecaster.feature_importance()
    fi_df = fi.reset_index()
    fi_df.columns = ["feature", "importance"]
    fi_df["importance_pct"] = (fi_df["importance"] / fi_df["importance"].sum() * 100).round(2)
    return fi_df.head(20)


# ─── Recommendations engine ────────────────────────────────────────────────────
def generate_recommendations(risk_df: pd.DataFrame, promo_df: pd.DataFrame) -> list:
    recs = []

    # Stockout alerts
    high_risk = risk_df[risk_df["stockout_risk (%)"] > 20]
    for _, row in high_risk.iterrows():
        recs.append({
            "type":     "⚠️ Stockout Risk",
            "product":  row["product"],
            "message":  (f"Stockout risk is {row['stockout_risk (%)']:.1f}%. "
                         f"Increase stock to ≥{row['reorder_point']} units. "
                         f"Safety stock buffer: {row['safety_stock']} units."),
            "priority": "High",
        })

    # Overstock alerts
    over_risk = risk_df[risk_df["overstock_risk (%)"] > 20]
    for _, row in over_risk.iterrows():
        recs.append({
            "type":     "📦 Overstock Risk",
            "product":  row["product"],
            "message":  (f"Overstock risk is {row['overstock_risk (%)']:.1f}%. "
                         f"Consider reducing orders or running clearance promotions."),
            "priority": "Medium",
        })

    # Promotional opportunities
    high_lift = promo_df[promo_df["promo_lift (%)"] > 30]
    for _, row in high_lift.iterrows():
        recs.append({
            "type":     "📈 Promo Opportunity",
            "product":  row["product"],
            "message":  (f"Promotions lift {row['product']} sales by "
                         f"{row['promo_lift (%)']:.1f}%. "
                         f"Schedule promotions ahead of peak season."),
            "priority": "Low",
        })

    return recs


# ─── Export all insights to JSON ───────────────────────────────────────────────
def export_insights(
    train_df: pd.DataFrame,
    result_df: pd.DataFrame,
    overall_metrics: dict,
    per_product_metrics: pd.DataFrame,
    risk_df: pd.DataFrame,
    xgb_forecaster,
    output_dir: str = None,
) -> dict:
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

    monthly   = monthly_demand_trend(train_df)
    peaks     = peak_months(monthly)
    promo_eff = promo_effectiveness(train_df)
    dow_pat   = dow_pattern(train_df)
    feat_imp  = get_feature_importance(xgb_forecaster)
    recs      = generate_recommendations(risk_df, promo_eff)

    # Build forecast time-series per product
    forecast_ts = {}
    for product, grp in result_df.groupby("product"):
        forecast_ts[product] = {
            "dates":          grp["date"].dt.strftime("%Y-%m-%d").tolist(),
            "actual":         grp["sales"].round().astype(int).tolist(),
            "xgb_pred":       grp["xgb_pred"].round().astype(int).tolist()
                              if "xgb_pred" in grp else [],
            "sarima_pred":    grp["sarima_pred"].round().astype(int).tolist()
                              if "sarima_pred" in grp else [],
            "ensemble_pred":  grp["ensemble_pred"].round().astype(int).tolist(),
        }

    insights = {
        "overall_metrics":   overall_metrics,
        "per_product_metrics": per_product_metrics.to_dict(orient="records"),
        "risk_analysis":     risk_df.to_dict(orient="records"),
        "monthly_trend":     monthly.to_dict(orient="records"),
        "peak_months":       peaks.to_dict(orient="records"),
        "promo_effectiveness": promo_eff.to_dict(orient="records"),
        "dow_pattern":       dow_pat.to_dict(orient="records"),
        "feature_importance": feat_imp.to_dict(orient="records"),
        "recommendations":   recs,
        "forecast_ts":       forecast_ts,
        "products":          result_df["product"].unique().tolist(),
    }

    out_path = os.path.join(output_dir, "insights.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2, default=str)
    print(f"[insights] Saved -> {out_path}")

    # Also save directly into dashboard directory for standalone browser support
    dashboard_dir = os.path.join(os.path.dirname(output_dir), "..", "dashboard")
    if os.path.isdir(dashboard_dir):
        dash_json = os.path.join(dashboard_dir, "insights.json")
        dash_js   = os.path.join(dashboard_dir, "insights_data.js")
        with open(dash_json, "w", encoding="utf-8") as f:
            json.dump(insights, f, indent=2, default=str)
        with open(dash_js, "w", encoding="utf-8") as f:
            f.write(f"window.INSIGHTS_DATA = {json.dumps(insights, indent=2, default=str)};\n")
        print(f"[insights] Exported dashboard data -> {dash_js}")
    return insights
