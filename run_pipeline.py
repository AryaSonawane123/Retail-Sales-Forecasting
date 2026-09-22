"""
run_pipeline.py
---------------
End-to-end runner script for the Retail Sales Forecasting pipeline.

Steps:
  1. Generate synthetic data
  2. Preprocess & clean
  3. Feature engineering
  4. Train SARIMA + XGBoost ensemble
  5. Evaluate on held-out test set
  6. Generate & export insights JSON (consumed by dashboard)

Run:
    python run_pipeline.py
    python run_pipeline.py --tune      # enables Optuna hyperparameter tuning
    python run_pipeline.py --xgb-only  # skips SARIMA (faster)
"""

import os
import sys
import argparse
import json
import time

# ── Ensure src/ is on the path ───────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from src.data_generator    import generate_sales_data
from src.preprocessing     import run_preprocessing, chronological_split
from src.feature_engineering import build_feature_set
from src.models            import EnsembleForecaster, XGBoostForecaster
from src.evaluation        import evaluate_overall, evaluate_per_product, inventory_risk_analysis, print_summary
from src.insights          import export_insights


def parse_args():
    p = argparse.ArgumentParser(description="Retail Sales Forecasting Pipeline")
    p.add_argument("--tune",     action="store_true", help="Run Optuna HPO for XGBoost")
    p.add_argument("--xgb-only", action="store_true", help="Use XGBoost only (skip SARIMA)")
    p.add_argument("--no-regen", action="store_true", help="Skip data generation if data exists")
    return p.parse_args()


def main():
    args   = parse_args()
    t_start = time.time()

    # ── 1. Data Generation ───────────────────────────────────────────────────
    raw_path = os.path.join("data", "raw", "sales_data.csv")
    if args.no_regen and os.path.exists(raw_path):
        print("[Pipeline] Skipping data generation (--no-regen).")
    else:
        print("\n[Pipeline] Step 1: Generating synthetic sales data...")
        generate_sales_data(raw_path)

    # ── 2. Preprocessing ─────────────────────────────────────────────────────
    print("\n[Pipeline] Step 2: Preprocessing...")
    clean_path = os.path.join("data", "processed", "sales_clean.csv")
    df_clean   = run_preprocessing(raw_path, clean_path)

    # ── 3. Feature Engineering ───────────────────────────────────────────────
    print("\n[Pipeline] Step 3: Feature engineering...")
    feat_path = os.path.join("data", "processed", "sales_features.csv")
    df_feat   = build_feature_set(clean_path, feat_path)

    # ── 4. Train / Val / Test Split ───────────────────────────────────────────
    print("\n[Pipeline] Step 4: Splitting data...")
    import pandas as pd
    train_df, val_df, test_df = chronological_split(df_feat)

    # Also get raw clean splits for SARIMA (needs unlagged data)
    df_clean_full = pd.read_csv(clean_path, parse_dates=["date"])
    df_clean_full.sort_values(["product", "date"], inplace=True)
    train_clean, val_clean, test_clean = chronological_split(df_clean_full)

    # ── 5. Model Training ─────────────────────────────────────────────────────
    print("\n[Pipeline] Step 5: Training models...")

    if args.xgb_only:
        xgb = XGBoostForecaster(tune=args.tune)
        xgb.fit(train_df, val_df)
        result_df = test_df[["date", "product", "sales"]].copy()
        result_df["ensemble_pred"] = xgb.predict(test_df)
        result_df["xgb_pred"]      = result_df["ensemble_pred"]
        result_df["sarima_pred"]   = result_df["ensemble_pred"]
        ensemble = type("_Fake", (), {"xgb_": xgb})()
    else:
        xgb_weight = 0.70
        ensemble   = EnsembleForecaster(xgb_weight=xgb_weight, tune_xgb=args.tune)
        ensemble.fit(train_clean, val_clean)
        # XGBoost uses feature-engineered data; re-fit separately
        ensemble.xgb_.fit(train_df, val_df)
        result_df = ensemble.predict(test_df)

    # ── 6. Evaluation ─────────────────────────────────────────────────────────
    print("\n[Pipeline] Step 6: Evaluating...")
    overall    = evaluate_overall(result_df)
    per_prod   = evaluate_per_product(result_df)
    risk_df    = inventory_risk_analysis(result_df)
    print_summary(overall, per_prod)

    # ── 7. Insights Export ────────────────────────────────────────────────────
    print("\n[Pipeline] Step 7: Exporting insights...")
    processed_dir = os.path.join("data", "processed")
    insights = export_insights(
        train_clean, result_df, overall, per_prod, risk_df,
        ensemble.xgb_, output_dir=processed_dir
    )

    # ── 8. Generate Executive PDF Report ─────────────────────────────────────
    print("\n[Pipeline] Step 8: Generating Executive PDF Report...")
    try:
        from src.generate_report import main as generate_pdf_report
        generate_pdf_report()
    except Exception as e:
        print(f"[Pipeline] Notice: PDF report compilation skipped ({e})")

    elapsed = time.time() - t_start
    print(f"\n[DONE] Pipeline complete in {elapsed:.1f}s")
    print(f"   Overall Accuracy : {overall['overall_accuracy']}%")
    print(f"   Overall MAPE     : {overall['overall_MAPE']}%")
    print(f"   Insights JSON    : data/processed/insights.json")
    print(f"   Dashboard Ready  : dashboard/index.html")
    print(f"   Executive Report : reports/Retail_Sales_Forecasting_Executive_Report.pdf")
    print("\n>> Open dashboard/index.html in your browser to explore interactive results.")


if __name__ == "__main__":
    main()
