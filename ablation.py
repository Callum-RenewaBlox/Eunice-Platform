"""Feature ablation — drop each feature group, retrain p50 quantile model, compare val MAE.

Validation = last 30 days of training data, same split as the live training pipeline.
Hyperparameters match those used in production (model.py), so values are directly
comparable to the reported val MAE.
"""
from time import perf_counter

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from features import FEATURE_COLS, build_training_data

HP = dict(
    loss="quantile", alpha=0.5,
    n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42,
)

GROUPS = {
    "(full model — baseline)": [],
    "Temporal (hour, minute, dow, month, is_weekend)": ["hour", "minute", "dow", "month", "is_weekend"],
    "Bank holiday": ["is_bank_holiday"],
    "All weather (5 cols)": ["temperature_c", "wind_speed_kmh", "cloud_cover_pct", "shortwave_wm2", "precipitation_mm"],
    "  · just temperature": ["temperature_c"],
    "  · just wind speed": ["wind_speed_kmh"],
    "  · just cloud cover": ["cloud_cover_pct"],
    "  · just shortwave (solar)": ["shortwave_wm2"],
    "Carbon intensity (NESO)": ["carbon_intensity_forecast"],
    "Wind generation MW (BMRS FUELHH)": ["wind_generation_mw"],
    "Demand MW (BMRS FUELHH)": ["demand_mw"],
    "Lag 1-week price": ["lag_1w_price"],
}


def main():
    X, y, ts, _regions = build_training_data("AGILE")
    cutoff = ts.max() - pd.Timedelta(days=30)
    train_mask = ts < cutoff
    val_mask = ~train_mask
    print(f"Train: {train_mask.sum()} rows · Val: {val_mask.sum()} rows (last 30 days)\n")
    print(f"{'Dropped':<55} {'val MAE':>10} {'delta MAE':>13} {'time':>6}")
    print("-" * 90)

    baseline = None
    for name, drop in GROUPS.items():
        cols = [c for c in FEATURE_COLS if c not in drop]
        if not cols:
            continue
        Xtr, ytr = X[cols][train_mask], y[train_mask]
        Xva, yva = X[cols][val_mask], y[val_mask]
        t0 = perf_counter()
        m = GradientBoostingRegressor(**HP).fit(Xtr, ytr)
        mae = mean_absolute_error(yva, m.predict(Xva))
        elapsed = perf_counter() - t0
        if baseline is None:
            baseline = mae
            delta = "—"
        else:
            d = mae - baseline
            delta = f"{'+' if d >= 0 else ''}{d:.3f} p"
        print(f"{name:<55} {mae:>8.3f} p {delta:>15} {elapsed:>5.1f}s")


if __name__ == "__main__":
    main()
