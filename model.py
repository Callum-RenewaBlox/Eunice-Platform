import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error

from config import ALL_REGIONS, SPIKE_THRESHOLD_P
from features import build_forecast_features, build_training_data

MODEL_VERSION = "hgbt_quantile_v3_trough"
HP = dict(max_iter=200, max_depth=4, learning_rate=0.05, random_state=42)
RECENT_HALF_LIFE_DAYS = 14   # samples 14 days old get half the weight
PEAK_HOURS_LOCAL = (16, 17, 18)
PEAK_WEIGHT_BOOST = 5.0      # peak slots are 5× weighted to overcome their off-peak-dominated minority
LOW_PRICE_THRESHOLD_P = 5.0  # slots at/below this are the under-represented "trough" regime
LOW_PRICE_WEIGHT_BOOST = 6.0 # up-weight troughs so the lower quantiles can learn negative pricing
NEG_THRESHOLD_P = 0.0        # trough classifier target: was this slot negatively priced?


def _time_decay_weights(ts, y=None, half_life_days=RECENT_HALF_LIFE_DAYS,
                        peak_boost=PEAK_WEIGHT_BOOST, low_boost=LOW_PRICE_WEIGHT_BOOST):
    """Exponential time decay + peak-hour boost + (optional) low-price boost.

    - Peak hours (16-18 London local) get a ×peak_boost weight: only 12.5% of slots but they
      drive most user-facing error (right-skewed peak distribution, structurally few samples).
    - Low-price slots (y < LOW_PRICE_THRESHOLD_P) get a ×low_boost weight when `y` is supplied.
      Negative/near-zero prices are ~2% of slots and were being statistically drowned, so the
      lower quantiles never dipped below zero. Boosting them lets p05/p10 learn the trough.
    Peak and trough sets are essentially disjoint, so we combine via max() — a slot that is
    somehow both keeps the larger boost rather than one silently overriding the other.
    """
    ts_max = ts.max()
    ages_days = (ts_max - ts).dt.total_seconds().values / 86400.0
    base = np.exp(-ages_days / half_life_days)
    hours_local = ts.dt.tz_convert("Europe/London").dt.hour.values
    peak_mask = np.isin(hours_local, PEAK_HOURS_LOCAL)
    w = np.where(peak_mask, base * peak_boost, base)
    if y is not None:
        low_mask = np.asarray(y) < LOW_PRICE_THRESHOLD_P
        w = np.where(low_mask, np.maximum(w, base * low_boost), w)
    return w


def _train_quantiles(X, y, sample_weight=None):
    # p05 added (v3) so the downside band can actually reach negative prices — p10 alone
    # floored well above zero at the ~2% negative base rate.
    return {
        name: HistGradientBoostingRegressor(loss="quantile", quantile=alpha, **HP).fit(
            X, y, sample_weight=sample_weight
        )
        for name, alpha in [("p05", 0.05), ("p10", 0.1), ("p50", 0.5), ("p90", 0.9)]
    }


def _train_spike(X, y, sample_weight=None):
    y_bin = (y > SPIKE_THRESHOLD_P).astype(int)
    if y_bin.sum() < 10:
        return None
    return HistGradientBoostingClassifier(**HP).fit(X, y_bin, sample_weight=sample_weight)


def _train_trough(X, y, sample_weight=None):
    """Classifier for P(price < 0) — the downside mirror of the spike classifier. Gives an
    explicit negative-price probability we can surface to clients, independent of the band."""
    y_bin = (y < NEG_THRESHOLD_P).astype(int)
    if y_bin.sum() < 10:
        return None
    return HistGradientBoostingClassifier(**HP).fit(X, y_bin, sample_weight=sample_weight)


def _to_dicts(timestamps, p50, p10, p90, p05=None, p_spike=None, p_trough=None,
              generated_at_per_row=None):
    out = []
    for i, ts in enumerate(timestamps):
        d = {
            "valid_from": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "valid_to": (ts + pd.Timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "predicted_price": float(p50[i]),
            "p10": float(p10[i]),
            "p90": float(p90[i]),
        }
        if p05 is not None:
            d["p05"] = float(p05[i])
        if p_spike is not None:
            d["p_spike"] = float(p_spike[i])
        if p_trough is not None:
            d["p_trough"] = float(p_trough[i])
        if generated_at_per_row is not None:
            d["generated_at"] = generated_at_per_row[i]
        out.append(d)
    return out


def _train_full_pipeline(product):
    """Validation pass + final train on all data for one product. Returns (models, clf, trough_clf)."""
    X, y, ts, _regions = build_training_data(product)
    if X is None or len(X) < 1000:
        raise RuntimeError(f"Not enough training data for product={product} ({0 if X is None else len(X)} rows)")

    cutoff = ts.max() - pd.Timedelta(days=30)
    train_ts = ts[ts < cutoff]
    train_w = _time_decay_weights(train_ts, y=y[ts < cutoff])
    val_models = _train_quantiles(X[ts < cutoff], y[ts < cutoff], sample_weight=train_w)
    val_clf = _train_spike(X[ts < cutoff], y[ts < cutoff], sample_weight=train_w)

    yv = y[ts >= cutoff]
    val_pred = val_models["p50"].predict(X[ts >= cutoff])
    val_mae = mean_absolute_error(yv, val_pred)
    # Trough-region diagnostics so the daily log shows whether negatives are being captured.
    neg = (yv < NEG_THRESHOLD_P).values
    if neg.any():
        neg_mae = mean_absolute_error(yv[neg], val_pred[neg])
        neg_hit = (val_pred[neg] < 0).mean()
        neg_msg = f"; neg n={neg.sum()} MAE={neg_mae:.1f}p hit={neg_hit*100:.0f}%"
    else:
        neg_msg = "; neg n=0"

    if val_clf is not None:
        val_proba = val_clf.predict_proba(X[ts >= cutoff])[:, 1]
        val_brier = brier_score_loss((yv > SPIKE_THRESHOLD_P).astype(int), val_proba)
        spike_msg = f"; spike Brier = {val_brier:.3f}"
    else:
        spike_msg = "; spike clf skipped"
    print(f"[train product={product}] n={len(X)} (val MAE on last 30d = {val_mae:.2f} p{spike_msg}{neg_msg})")

    full_w = _time_decay_weights(ts, y=y)
    models = _train_quantiles(X, y, sample_weight=full_w)
    clf = _train_spike(X, y, sample_weight=full_w)
    trough_clf = _train_trough(X, y, sample_weight=full_w)
    return models, clf, trough_clf


def _predict_for_region(models, clf, trough_clf, region, product):
    df, Xf = build_forecast_features(region, product)
    mask = Xf.notna().all(axis=1)
    df, Xf = df[mask].copy(), Xf[mask]
    if Xf.empty:
        return []
    p05 = models["p05"].predict(Xf)
    p10 = models["p10"].predict(Xf)
    p50 = models["p50"].predict(Xf)
    p90 = models["p90"].predict(Xf)
    p_spike = clf.predict_proba(Xf)[:, 1] if clf is not None else None
    p_trough = trough_clf.predict_proba(Xf)[:, 1] if trough_clf is not None else None
    return _to_dicts(list(df["valid_from"]), p50, p10, p90, p05=p05,
                     p_spike=p_spike, p_trough=p_trough)


def predict_next_7_days_all_regions(product):
    """Train once on this product, predict next 7 days for each of the 14 GSP regions."""
    models, clf, trough_clf = _train_full_pipeline(product)
    return {region: _predict_for_region(models, clf, trough_clf, region, product) for region in ALL_REGIONS}


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
    train_w = _time_decay_weights(ts[train_mask], y=y[train_mask])
    models = _train_quantiles(X[train_mask], y[train_mask], sample_weight=train_w)
    clf = _train_spike(X[train_mask], y[train_mask], sample_weight=train_w)
    trough_clf = _train_trough(X[train_mask], y[train_mask], sample_weight=train_w)

    Xva = X[val_mask]
    ts_va = ts[val_mask].reset_index(drop=True)
    regions_va = regions[val_mask].reset_index(drop=True)

    p05 = models["p05"].predict(Xva)
    p10 = models["p10"].predict(Xva)
    p50 = models["p50"].predict(Xva)
    p90 = models["p90"].predict(Xva)
    p_spike = clf.predict_proba(Xva)[:, 1] if clf is not None else None
    p_trough = trough_clf.predict_proba(Xva)[:, 1] if trough_clf is not None else None

    results = {}
    for region in regions_va.unique():
        rmask = (regions_va == region).values
        gen_at = [(t - pd.Timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ") for t in ts_va[rmask]]
        results[region] = _to_dicts(
            list(ts_va[rmask]),
            p50[rmask], p10[rmask], p90[rmask],
            p05=p05[rmask],
            p_spike=p_spike[rmask] if p_spike is not None else None,
            p_trough=p_trough[rmask] if p_trough is not None else None,
            generated_at_per_row=gen_at,
        )
    return results
