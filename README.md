# Retail Sales Forecasting

> AI-powered retail demand forecasting using **XGBoost + SARIMA ensemble** to optimize inventory management.

---

## 🎯 Project Goals

| Goal | Target | Status |
|------|--------|--------|
| Forecast Accuracy | ≥ 90% | ✅ Achieved |
| Reduce Stockouts | −15% | 📊 Measured |
| Reduce Overstock | −10% | 📊 Measured |

---

## 🏗 Project Structure

```
Retail Sales Forecasting/
├── src/
│   ├── data_generator.py       # Synthetic data (3 yrs, 10 categories)
│   ├── preprocessing.py        # Cleaning, outlier removal, splits
│   ├── feature_engineering.py  # Lag, rolling, Fourier, calendar features
│   ├── models.py               # SARIMA + XGBoost + Ensemble
│   ├── evaluation.py           # MAPE, RMSE, MAE, R², risk analysis
│   └── insights.py             # Business insights & JSON export
├── dashboard/
│   ├── index.html              # Web dashboard (open in browser)
│   ├── style.css               # Premium dark-mode UI
│   └── app.js                  # Chart.js visualizations & logic
├── data/
│   ├── raw/sales_data.csv      # Generated after pipeline run
│   └── processed/
│       ├── sales_clean.csv
│       ├── sales_features.csv
│       └── insights.json       # Consumed by dashboard
├── run_pipeline.py             # ▶ Main entry point
└── requirements.txt
```

---

## ⚡ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Full Pipeline
```bash
python run_pipeline.py
```

Options:
```bash
python run_pipeline.py --tune      # Optuna hyperparameter tuning (slower, better)
python run_pipeline.py --xgb-only  # Skip SARIMA for faster runs
python run_pipeline.py --no-regen  # Skip data generation if CSV exists
```

### 3. View the Dashboard
Open `dashboard/index.html` in any modern browser.

> **No server needed** — The dashboard auto-loads `data/processed/insights.json`
> and falls back to built-in demo data if the file is not found.

---

## 🧠 Methodology

### Data
- **3 years** of daily sales (2021–2023)
- **10 product categories**: Electronics, Clothing, Groceries, Sports, Toys, Home Decor, Books, Beauty, Furniture, Automotive
- Embedded seasonality, holiday spikes, promotions, price elasticity, and noise

### Preprocessing
- Forward-fill + linear interpolation for missing values (~1% of data)
- Winsorization (1.5× IQR) for outlier capping
- Chronological 70/15/15 train/validation/test split (no data leakage)

### Feature Engineering
| Category | Features |
|----------|----------|
| Lag | sales_lag_1, 7, 14, 28 |
| Rolling | mean/std over 7 & 30 days |
| Fourier | 3 sin/cos pairs (annual seasonality) |
| Calendar | DoW, week, month, quarter, is_weekend, is_holiday |
| External | promotion flag, price_ratio, weather_index |
| Trend | linear day index |

### Models
| Model | Weight | Role |
|-------|--------|------|
| XGBoost | 70% | Handles complex feature interactions |
| SARIMA(1,1,1)(1,1,0,7) | 30% | Captures weekly seasonal patterns |
| **Ensemble** | — | Weighted average of both |

### Evaluation
- **MAPE**: Primary metric (target ≤10%)
- **RMSE, MAE**: Secondary metrics
- **R²**: Goodness of fit
- **Inventory Risk**: Stockout/overstock probability, safety stock, reorder points

---

## 📊 Dashboard Pages

| Page | Contents |
|------|----------|
| **Overview** | KPI cards, forecast vs actual chart, per-product accuracy table |
| **Forecast** | Product drill-down, daily/weekly/monthly view, DoW & seasonal patterns |
| **Inventory Alerts** | Stockout/overstock risk charts, safety stock table, recommendations |
| **Insights** | Seasonal heatmap, promo lift, XGBoost feature importance, key findings |

---

## 📦 Requirements

```
pandas          numpy           matplotlib      seaborn
plotly          statsmodels     xgboost         optuna
scikit-learn    scipy           joblib          fpdf2
```

---

## 👤 Author

**Vaidsys Internship Project** · Retail Sales Forecasting
