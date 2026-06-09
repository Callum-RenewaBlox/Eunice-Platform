"""Guardrail harness for the negative-price fix.

Trains on data older than HOLDOUT_DAYS, predicts the held-out tail, and reports the
metrics that matter for this change:

  - overall MAE
  - PEAK-hour (16-18 local) MAE      <- guardrail: must NOT regress
  - negative-hour MAE (actual < 0)   <- the thing we're trying to fix
  - low-hour MAE (actual < 5p)       <- broader trough region
  - directional hit rate on negatives (did we even predict below zero?)
  - p10-p90 band coverage (overall + on negative hours)
  - min predicted / min p10 / min p05 (can the model reach negative at all?)

Run before and after the model changes; compare the two printouts.
Usage:  python diagnose_negatives.py [HOLDOUT_DAYS] [PRODUCT]
"""
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from features import build_training_data
from model import _time_decay_weights, _train_quantiles, _train_trough

PEAK_HOURS_LOCAL = (16, 17, 18)


def evaluate(product="AGILE", holdout_days=14):
    X, y, ts, regions = build_training_data(product)
    if X is None:
        print(f"[{product}] no training data")
        return
    cutoff = ts.max() - pd.Timedelta(days=holdout_days)
    tr, va = ts < cutoff, ts >= cutoff
    if tr.sum() < 1000 or va.sum() == 0:
        print(f"[{product}] insufficient split")
        return

    w = _time_decay_weights(ts[tr], y=y[tr])
    models = _train_quantiles(X[tr], y[tr], sample_weight=w)
    trough_clf = _train_trough(X[tr], y[tr], sample_weight=w)
    # p05 is optional — only present after the trough-band change
    has_p05 = "p05" in models

    yv = y[va].reset_index(drop=True)
    p50 = models["p50"].predict(X[va])
    p10 = models["p10"].predict(X[va])
    p90 = models["p90"].predict(X[va])
    p05 = models["p05"].predict(X[va]) if has_p05 else None

    hours = ts[va].dt.tz_convert("Europe/London").dt.hour.reset_index(drop=True).values
    peak_mask = np.isin(hours, PEAK_HOURS_LOCAL)
    neg_mask = (yv < 0).values
    low_mask = (yv < 5).values

    lo_band = p05 if has_p05 else p10
    overall_cov = ((yv.values >= lo_band) & (yv.values <= p90)).mean()
    neg_cov = (((yv.values >= lo_band) & (yv.values <= p90))[neg_mask]).mean() if neg_mask.any() else float("nan")

    print(f"\n========== {product}  (holdout = last {holdout_days} days) ==========")
    print(f"val rows: {va.sum()}   negative-actual slots: {neg_mask.sum()}   low(<5p) slots: {low_mask.sum()}")
    print(f"{'overall MAE':<34}{mean_absolute_error(yv, p50):>8.2f} p")
    print(f"{'PEAK-hour MAE (GUARDRAIL)':<34}{mean_absolute_error(yv[peak_mask], p50[peak_mask]):>8.2f} p"
          if peak_mask.any() else "  (no peak rows in holdout)")
    if neg_mask.any():
        print(f"{'negative-hour MAE':<34}{mean_absolute_error(yv[neg_mask], p50[neg_mask]):>8.2f} p")
        hit = (p50[neg_mask] < 0).mean()
        print(f"{'  directional hit (pred<0 | actual<0)':<34}{hit*100:>7.0f} %")
    if low_mask.any():
        print(f"{'low-hour (<5p) MAE':<34}{mean_absolute_error(yv[low_mask], p50[low_mask]):>8.2f} p")
    band = "p05-p90" if has_p05 else "p10-p90"
    print(f"{'band coverage ('+band+') overall':<34}{overall_cov*100:>7.0f} %")
    print(f"{'band coverage on NEGATIVE hours':<34}{neg_cov*100:>7.0f} %")
    print(f"{'min predicted (p50)':<34}{p50.min():>8.2f} p")
    print(f"{'min p10':<34}{p10.min():>8.2f} p")
    if has_p05:
        print(f"{'min p05':<34}{p05.min():>8.2f} p")
    print(f"{'min ACTUAL in holdout':<34}{yv.min():>8.2f} p")

    # Trough classifier: the cleanest negative-price signal (doesn't need the median to cross 0)
    if trough_clf is not None and neg_mask.any():
        p_trough = trough_clf.predict_proba(X[va])[:, 1]
        from sklearn.metrics import roc_auc_score
        try:
            auc = roc_auc_score(neg_mask.astype(int), p_trough)
        except ValueError:
            auc = float("nan")
        print(f"{'trough clf: mean P(neg) on negatives':<34}{p_trough[neg_mask].mean()*100:>7.0f} %")
        print(f"{'trough clf: mean P(neg) on positives':<34}{p_trough[~neg_mask].mean()*100:>7.0f} %")
        print(f"{'trough clf: ROC-AUC':<34}{auc:>8.3f}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    prods = [sys.argv[2]] if len(sys.argv) > 2 else ["AGILE", "SHAPE_SHIFTERS"]
    for p in prods:
        evaluate(p, days)
