"""
models.py
---------
Houses two forecasting models and a blending ensemble:

  1. SARIMAForecaster  – classical statsmodels SARIMAX per product
  2. XGBoostForecaster – gradient boosted trees on engineered features
  3. EnsembleForecaster – weighted average (70% XGB + 30% SARIMA)

Usage:
    from src.models import EnsembleForecaster
    model = EnsembleForecaster()
    model.fit(train_df, val_df)
    preds = model.predict(test_df)
"""

import os
import warnings
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.preprocessing import StandardScaler
from src.feature_engineering import get_feature_columns

warnings.filterwarnings("ignore")

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


# ─── SARIMA ────────────────────────────────────────────────────────────────────
class SARIMAForecaster:
    """Fits one SARIMA(1,1,1)(1,1,0,7) model per product (weekly seasonality)."""

    ORDER        = (1, 1, 1)
    SEASONAL_ORDER = (1, 1, 0, 7)   # weekly period

    def __init__(self):
        self.models_  = {}   # product -> fitted SARIMAXResults
        self.history_ = {}   # product -> pd.Series (training sales)

    def fit(self, train_df: pd.DataFrame) -> "SARIMAForecaster":
        for product, grp in train_df.groupby("product"):
            series = grp.set_index("date")["sales"].asfreq("D").fillna(method="ffill")
            try:
                m = SARIMAX(series, order=self.ORDER, seasonal_order=self.SEASONAL_ORDER,
                            enforce_stationarity=False, enforce_invertibility=False)
                self.models_[product]  = m.fit(disp=False)
                self.history_[product] = series
                print(f"  [SARIMA] Fitted: {product}")
            except Exception as e:
                print(f"  [SARIMA] Warning – {product}: {e}")
        return self

    def predict(self, test_df: pd.DataFrame) -> pd.DataFrame:
        results = []
        for product, grp in test_df.groupby("product"):
            if product not in self.models_:
                continue
            fitted = self.models_[product]
            start  = grp["date"].min()
            end    = grp["date"].max()
            try:
                preds = fitted.predict(start=start, end=end)
                preds = preds.reindex(grp["date"]).fillna(method="ffill")
            except Exception:
                preds = pd.Series(grp["sales"].mean(), index=grp["date"])
            tmp = grp[["date", "product", "sales"]].copy()
            tmp["sarima_pred"] = preds.values
            results.append(tmp)
        return pd.concat(results, ignore_index=True)


# ─── XGBoost ──────────────────────────────────────────────────────────────────
class XGBoostForecaster:
    """
    Single XGBoost model trained on all products simultaneously.
    Uses the full feature set from feature_engineering.py.
    Optionally tunes via Optuna (n_trials > 0).
    """

    BEST_PARAMS = {
        "n_estimators":     800,
        "max_depth":        6,
        "learning_rate":    0.05,
        "subsample":        0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "gamma":            0.1,
        "reg_alpha":        0.05,
        "reg_lambda":       1.0,
        "random_state":     42,
        "n_jobs":           -1,
        "tree_method":      "hist",
    }

    def __init__(self, tune: bool = False, n_trials: int = 30):
        self.tune_     = tune
        self.n_trials_ = n_trials
        self.model_    = None
        self.scaler_   = StandardScaler()
        self.feat_cols_ = get_feature_columns()

    def _get_xy(self, df: pd.DataFrame):
        X = df[self.feat_cols_].copy()
        y = df["sales"].values
        return X, y

    def fit(self, train_df: pd.DataFrame, val_df: pd.DataFrame = None) -> "XGBoostForecaster":
        X_train, y_train = self._get_xy(train_df)

        if self.tune_ and val_df is not None:
            params = self._tune(train_df, val_df)
        else:
            params = self.BEST_PARAMS.copy()

        self.model_ = XGBRegressor(**params)
        eval_set = [(X_train, y_train)]
        if val_df is not None:
            X_val, y_val = self._get_xy(val_df)
            eval_set.append((X_val, y_val))

        self.model_.fit(
            X_train, y_train,
            eval_set=eval_set,
            verbose=False,
        )
        print(f"  [XGBoost] Trained on {len(X_train):,} samples.")
        return self

    def _tune(self, train_df, val_df):
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        X_tr, y_tr = self._get_xy(train_df)
        X_v,  y_v  = self._get_xy(val_df)

        def objective(trial):
            params = {
                "n_estimators":     trial.suggest_int("n_estimators", 200, 1000),
                "max_depth":        trial.suggest_int("max_depth", 3, 9),
                "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "random_state":     42,
                "n_jobs":          -1,
                "tree_method":     "hist",
            }
            m = XGBRegressor(**params)
            m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=False)
            preds = m.predict(X_v)
            mape = np.mean(np.abs((y_v - preds) / (y_v + 1e-9))) * 100
            return mape

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=self.n_trials_, show_progress_bar=False)
        print(f"  [XGBoost Optuna] Best MAPE: {study.best_value:.2f}%")
        return {**study.best_params, "random_state": 42, "n_jobs": -1, "tree_method": "hist"}

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X, _ = self._get_xy(df)
        preds = self.model_.predict(X)
        return np.clip(preds, 0, None)

    def feature_importance(self) -> pd.Series:
        return pd.Series(
            self.model_.feature_importances_,
            index=self.feat_cols_
        ).sort_values(ascending=False)

    def save(self, path: str = None):
        path = path or os.path.join(MODEL_DIR, "xgb_model.pkl")
        joblib.dump(self.model_, path)
        print(f"  [XGBoost] Saved -> {path}")

    def load(self, path: str = None):
        path = path or os.path.join(MODEL_DIR, "xgb_model.pkl")
        self.model_ = joblib.load(path)
        return self


# ─── Ensemble ─────────────────────────────────────────────────────────────────
class EnsembleForecaster:
    """
    Weighted average of SARIMA + XGBoost predictions.
    Default weights: XGB=0.70, SARIMA=0.30
    """

    def __init__(self, xgb_weight: float = 0.70, tune_xgb: bool = False):
        self.xgb_weight_    = xgb_weight
        self.sarima_weight_ = 1.0 - xgb_weight
        self.xgb_    = XGBoostForecaster(tune=tune_xgb)
        self.sarima_ = SARIMAForecaster()

    def fit(self, train_df: pd.DataFrame, val_df: pd.DataFrame = None) -> "EnsembleForecaster":
        print("[Ensemble] Training SARIMA models…")
        self.sarima_.fit(train_df)
        print("[Ensemble] Training XGBoost model…")
        self.xgb_.fit(train_df, val_df)
        return self

    def predict(self, test_df: pd.DataFrame) -> pd.DataFrame:
        # XGBoost predictions
        xgb_preds = self.xgb_.predict(test_df)

        # SARIMA predictions (returns a df with 'sarima_pred')
        sarima_df  = self.sarima_.predict(test_df)
        sarima_pred_map = sarima_df.set_index(["date", "product"])["sarima_pred"]

        result = test_df[["date", "product", "sales"]].copy()
        result["xgb_pred"] = xgb_preds

        def _sarima_lookup(row):
            try:
                return sarima_pred_map.loc[(row["date"], row["product"])]
            except Exception:
                return row["xgb_pred"]

        result["sarima_pred"]   = result.apply(_sarima_lookup, axis=1)
        result["ensemble_pred"] = (
            self.xgb_weight_    * result["xgb_pred"] +
            self.sarima_weight_ * result["sarima_pred"]
        ).clip(0)
        result["ensemble_pred"] = result["ensemble_pred"].round()
        return result

    def save_xgb(self):
        self.xgb_.save()
