import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error

from config import ALL_REGIONS, SPIKE_THRESHOLD_P
from features import build_forecast_features, build_training_data

MODEL_VERSION = "hgbt_quantile_v2_tdecay"
HP = dict(max_iter=200, max_depth=4, learning_rate=0.05, random_state=42)
RECENT_HALF_LIFE_DAYS = 14   # samples 14 days old get half the weight
PEAK_HOURS_LOCAL = (16, 17, 18)
PEAK_WEIGHT_BOOST = 5.0      # peak slots are 5× weighted to overcome their off-peak-dominated minority


def _time_decay_weights(ts, half_life_days=RECENT_HALF_LIFE_DAYS, peak_boost=PEAK_WEIGHT_BOOST):
    """Exponential time decay + peak-hour boost.

    Peak hours (16-18 London local) get extra weight because they're only 12.5% of slots but
    drive most of the user-facing prediction error (the right-skewed price distribution at peak
    is harder to fit and the model has structurally fewer peak samples to learn from).
    """
    ts_max = ts.max()
    ages_days = (ts_max - ts).dt.total_seconds().values / 86400.0
    base = np.exp(-ages_days / half_life_days)
    hours_local = ts.dt.tz_convert("Europe/London").dt.hour.values
    peak_mask = np.isin(hours_local, PEAK_HOURS_LOCAL)
    return np.where(peak_mask, base * peak_boost, base)


def _train_quantiles(X, y, sample_weight=None):
    return {
        name: HistGradientBoostingRegressor(loss="quantile", quantile=alpha, **HP).fit(
            X, y, sample_weight=sample_weight
        )
        for name, alpha in [("p10", 0.1), ("p50", 0.5), ("p90", 0.9)]
    }


def _train_spike(X, y, sample_weight=None):
    y_bin = (y > SPIKE_THRESHOLD_P).astype(int)
    if y_bin.sum() < 10:
        return None
    return HistGradientBoostingClassifier(**HP).fit(X, y_bin, sample_weight=sample_weight)


def _to_dicts(timestamps, p10, p50, p90, p_spike=None, generated_at_per_row=None):
    out = []
    for i, ts in enumerate(timestamps):
        d = {
            "valid_from": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "valid_to": (ts + pd.Timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "predicted_price": float(p50[i]),
            "p10": float(p10[i]),
            "p90": float(p90[i]),
        }
        if p_spike is not None:
            d["p_spike"] = float(p_spike[i])
        if generated_at_per_row is not None:
            d["generated_at"] = generated_at_per_row[i]
        out.append(d)
    return out


def _train_full_pipeline(product):
    """Validation pass + final train on all data for one product. Returns (models, clf)."""
    X, y, ts, _regions = build_training_data(product)
    if X is None or len(X) < 1000:
        raise RuntimeError(f"Not enough training data for product={product} ({0 if X is None else len(X)} rows)")

    cutoff = ts.max() - pd.Timedelta(days=30)
    train_ts = ts[ts < cutoff]
    train_w = _time_decay_weights(train_ts)
    val_models = _train_quantiles(X[ts < cutoff], y[ts < cutoff], sample_weight=train_w)
    val_clf = _train_spike(X[ts < cutoff], y[ts < cutoff], sample_weight=train_w)

    val_pred = val_models["p50"].predict(X[ts >= cutoff])
    val_mae = mean_absolute_error(y[ts >= cutoff], val_pred)

    if val_clf is not None:
        val_proba = val_clf.predict_proba(X[ts >= cutoff])[:, 1]
        val_brier = brier_score_loss((y[ts >= cutoff] > SPIKE_THRESHOLD_P).astype(int), val_proba)
        spike_msg = f"; spike Brier = {val_brier:.3f}"
    else:
        spike_msg = "; spike clf skipped"
    print(f"[train product={product}] n={len(X)} (val MAE on last 30d = {val_mae:.2f} p{spike_msg})")

    full_w = _time_decay_weights(ts)
    models = _train_quantiles(X, y, sample_weight=full_w)
    clf = _train_spike(X, y, sample_weight=full_w)
    return models, clf


def _predict_for_region(models, clf, region, product):
    df, Xf = build_forecast_features(region, product)
    mask = Xf.notna().all(axis=1)
    df, Xf = df[mask].copy(), Xf[mask]
    if Xf.empty:
        return []
    p10 = models["p10"].predict(Xf)
    p50 = models["p50"].predict(Xf)
    p90 = models["p90"].predict(Xf)
    p_spike = clf.predict_proba(Xf)[:, 1] if clf is not None else None
    return _to_dicts(list(df["valid_from"]), p10, p50, p90, p_spike=p_spike)


def predict_next_7_days_all_regions(product):
    """Train once on this product, predict next 7 days for each of the 14 GSP regions."""
    models, clf = _train_full_pipeline(product)
    return {region: _predict_for_region(models, clf, region, product) for region in ALL_REGIONS}


def backtest_last_n_days_all_regions(n=7, product="AGILE"):
    """Train on data older than `n` days, predict for last n days, grouped by region."""
    X, y, ts, regions = build_training_data(product)
    if X is None:
        return {}
    cutoff = ts.max() - pd.Timedelta(days=n)
    train_mask = ts < cutoff
    val_mask = ~train_mask
    if train_mask.sum() < 1000 or val_mask.sum() == 0:
        return {}
    train_w = _time_decay_weights(ts[train_mask])
    models = _train_quantiles(X[train_mask], y[train_mask], sample_weight=train_w)
    clf = _train_spike(X[train_mask], y[train_mask], sample_weight=train_w)

    Xva = X[val_mask]
    ts_va = ts[val_mask].reset_index(drop=True)
    regions_va = regions[val_mask].reset_index(drop=True)

    p10 = models["p10"].predict(Xva)
    p50 = models["p50"].predict(Xva)
    p90 = models["p90"].predict(Xva)
    p_spike = clf.predict_proba(Xva)[:, 1] if clf is not None else None

    results = {}
    for region in regions_va.unique():
        rmask = (regions_va == region).values
        gen_at = [(t - pd.Timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ") for t in ts_va[rmask]]
        results[region] = _to_dicts(
            list(ts_va[rmask]),
            p10[rmask], p50[rmask], p90[rmask],
            p_spike=p_spike[rmask] if p_spike is not None else None,
            generated_at_per_row=gen_at,
        )
    return results
