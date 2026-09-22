"""
data_generator.py
-----------------
Generates a realistic synthetic retail sales dataset spanning 3 years
(2021-01-01 to 2023-12-31) for 10 product categories with:
  - Weekly & annual seasonality
  - Holiday spikes (Christmas, Thanksgiving, Black Friday, etc.)
  - Promotional events
  - Price sensitivity
  - Random noise & occasional outliers
"""

import numpy as np
import pandas as pd
import os

# ─── Configuration ────────────────────────────────────────────────────────────
RANDOM_SEED = 42
START_DATE  = "2021-01-01"
END_DATE    = "2023-12-31"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "sales_data.csv")

PRODUCTS = {
    "Electronics":    {"base": 120, "trend": 0.03,  "seasonality": "winter"},
    "Clothing":       {"base":  95, "trend": 0.015, "seasonality": "spring_fall"},
    "Groceries":      {"base": 300, "trend": 0.01,  "seasonality": "flat"},
    "Sports":         {"base":  70, "trend": 0.025, "seasonality": "summer"},
    "Toys":           {"base":  80, "trend": 0.02,  "seasonality": "winter"},
    "Home_Decor":     {"base":  60, "trend": 0.012, "seasonality": "spring"},
    "Books":          {"base":  50, "trend": 0.005, "seasonality": "flat"},
    "Beauty":         {"base":  85, "trend": 0.018, "seasonality": "flat"},
    "Furniture":      {"base":  40, "trend": 0.01,  "seasonality": "spring"},
    "Automotive":     {"base":  30, "trend": 0.008, "seasonality": "summer"},
}

# US holidays (month, day) with sales multipliers
US_HOLIDAYS = {
    (1,  1): 1.8,   # New Year
    (2, 14): 1.6,   # Valentine's Day
    (7,  4): 1.4,   # Independence Day
    (10, 31): 1.5,  # Halloween
    (12, 25): 2.5,  # Christmas
    (12, 26): 1.8,  # Boxing Day
    (12, 31): 1.6,  # New Year's Eve
}
# Thanksgiving = 4th Thursday of November, Black Friday = day after
def thanksgiving_dates(years):
    dates = {}
    for y in years:
        nov = pd.date_range(f"{y}-11-01", f"{y}-11-30", freq="D")
        thursdays = [d for d in nov if d.dayofweek == 3]
        thanksgiving = thursdays[3]
        black_friday  = thanksgiving + pd.Timedelta(days=1)
        dates[thanksgiving] = 2.2
        dates[black_friday]  = 3.0
    return dates


# ─── Seasonality helpers ──────────────────────────────────────────────────────
def annual_season_factor(day_of_year: pd.Series, season_type: str) -> np.ndarray:
    """Return a per-day seasonality multiplier based on product season type."""
    angle = 2 * np.pi * day_of_year / 365
    if season_type == "winter":
        return 1.0 + 0.4 * np.cos(angle)             # peak Dec–Jan
    elif season_type == "summer":
        return 1.0 - 0.3 * np.cos(angle)             # peak Jun–Aug
    elif season_type == "spring":
        return 1.0 + 0.3 * np.sin(angle)             # peak Mar–May
    elif season_type == "spring_fall":
        return 1.0 + 0.25 * np.abs(np.sin(angle))    # two peaks
    else:  # flat
        return np.ones(len(day_of_year))


def weekly_factor(day_of_week: pd.Series) -> np.ndarray:
    """Weekends sell more for most categories."""
    factors = {0: 0.90, 1: 0.88, 2: 0.87, 3: 0.92, 4: 1.05, 5: 1.20, 6: 1.18}
    return day_of_week.map(factors).values


# ─── Main generator ───────────────────────────────────────────────────────────
def generate_sales_data(output_path: str = OUTPUT_PATH) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    date_range = pd.date_range(START_DATE, END_DATE, freq="D")
    years = date_range.year.unique().tolist()

    holiday_map = {(d.month, d.day): m for (m, d_), m in US_HOLIDAYS.items()
                   for d in date_range if d.month == m and d.day == d_}
    thanksgiving_map = thanksgiving_dates(years)

    records = []
    for product, cfg in PRODUCTS.items():
        base        = cfg["base"]
        trend_rate  = cfg["trend"]
        season_type = cfg["seasonality"]

        # Price: slow drift with random promotions
        prices = np.full(len(date_range), round(rng.uniform(10, 200), 2))
        # Random promotions: ~6 times per year, lasting 3–7 days
        promo_flags = np.zeros(len(date_range), dtype=int)
        n_promos = int(len(date_range) / 60)
        promo_starts = rng.choice(len(date_range) - 7, size=n_promos, replace=False)
        for ps in promo_starts:
            dur = rng.integers(3, 8)
            promo_flags[ps:ps+dur] = 1
            prices[ps:ps+dur] *= rng.uniform(0.7, 0.90)

        # Trend component (linear + small quadratic)
        trend = np.array([base * (1 + trend_rate) ** (i / 365) for i in range(len(date_range))])

        # Seasonality
        ann_factor  = annual_season_factor(pd.Series(date_range.dayofyear), season_type)
        week_factor = weekly_factor(pd.Series(date_range.dayofweek))

        # Holiday multiplier
        hol_factor = np.ones(len(date_range))
        for i, d in enumerate(date_range):
            key = (d.month, d.day)
            if key in US_HOLIDAYS:
                hol_factor[i] = US_HOLIDAYS[key]
            if d in thanksgiving_map:
                hol_factor[i] = thanksgiving_map[d]

        # Promotional boost
        promo_boost = 1.0 + 0.35 * promo_flags

        # Price elasticity (higher price -> lower demand, elasticity ~= -1.2)
        base_price   = prices.mean()
        price_factor = (base_price / prices) ** 1.2

        # Final sales
        noise  = rng.normal(1.0, 0.08, len(date_range))
        sales  = trend * ann_factor * week_factor * hol_factor * promo_boost * price_factor * noise
        sales  = np.clip(sales, 0, None).round().astype(int)

        # Inject ~1% missing values
        missing_idx = rng.choice(len(date_range), size=int(len(date_range) * 0.01), replace=False)
        sales_with_nan = sales.astype(float)
        sales_with_nan[missing_idx] = np.nan

        # Inject ~0.3% outliers (data entry errors, returns)
        outlier_idx = rng.choice(len(date_range), size=int(len(date_range) * 0.003), replace=False)
        for oi in outlier_idx:
            sales_with_nan[oi] = sales[oi] * rng.choice([0.1, 4.0])

        # Weather index (synthetic, correlated with season)
        weather = 50 + 40 * np.sin(2 * np.pi * date_range.dayofyear / 365) + rng.normal(0, 5, len(date_range))

        for i, d in enumerate(date_range):
            records.append({
                "date":          d,
                "product":       product,
                "sales":         sales_with_nan[i],
                "price":         round(prices[i], 2),
                "is_promotion":  int(promo_flags[i]),
                "weather_index": round(weather[i], 2),
                "day_of_week":   d.dayofweek,
                "month":         d.month,
                "year":          d.year,
                "week_of_year":  d.isocalendar().week,
                "is_holiday":    int((d.month, d.day) in US_HOLIDAYS or d in thanksgiving_map),
            })

    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[data_generator] Saved {len(df):,} rows -> {output_path}")
    return df


if __name__ == "__main__":
    generate_sales_data()
