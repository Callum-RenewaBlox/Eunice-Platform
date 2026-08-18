"""Model core for the rebuilt engine: LightGBM quantiles + event heads + conformal margins.

Refactored from train_eval_v2.py — the maths is identical:
  stage 1  fit the 7 quantile models on history older than the calibration window, then compute
           per-lead conformal margins (P10-P90 -> 80% target, P05-P95 -> 90%) and the median
           bias on the most recent 8 fully-resolved weeks;
  stage 2  refit on all fully-resolved history; serve stage-2 predictions with stage-1 margins.

fit() returns a plain-dict bundle (persist with save_bundle/load_bundle, joblib) carrying the
boosters, margins and provenance; predict() applies it to feature rows built by
pipeline.build_origin_rows or read from features_{origin}.parquet.
"""
import numpy as np, pandas as pd, lightgbm as lgb, joblib
from pathlib import Path

MODEL_VERSION = 'lgbm_conformal_v2'

CAL = ['hh_idx', 'dow', 'is_weekend', 'is_holiday', 'doy_sin', 'doy_cos', 'month', 'is_peak', 'horizon']
LAGS = ['px_lag7', 'px_lastknown_sameslot', 'px_day_mean', 'px_day_min', 'px_day_max', 'px_day_neg', 'px_day_sub5',
        'px_roll7_mean', 'px_roll7_min', 'px_roll7_neg', 'px_roll7_sub5', 'px_roll30_mean', 'px_roll30_neg', 'px_day_offpeak_mean', 'px_slot_roll7']
DEM = ['nd_fc_hh', 'nd_fc_min', 'nd_fc_max', 'nd_fc_mean', 'lk_nd_fc_mean', 'd_nd_fc_mean', 'd_nd_fc_min']
REN = ['emb_wind', 'emb_solar', 'emb_wind_lf', 'emb_solar_lf', 'emb_solar_daymax', 'emb_wind_daymean', 'emb_wind_daymin', 'emb_ren_daymean', 'ren_share_proxy', 'windfor', 'windfor_share',
       'lk_emb_wind_daymean', 'lk_emb_solar_daymax', 'lk_emb_ren_daymean', 'lk_emb_wind_slot', 'lk_emb_solar_slot', 'd_emb_wind_daymean', 'd_emb_solar_daymax', 'd_emb_wind_slot', 'd_emb_solar_slot']
FEATSETS = {'A': CAL + LAGS, 'B': CAL + LAGS + DEM, 'C': CAL + LAGS + DEM + REN}
QS = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
PARAMS = dict(learning_rate=0.03, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, num_threads=2)
NR_Q, NR_B = 450, 400
LEVEL = 'px_day_offpeak_mean'
CAL_WEEKS = 8


def _qpred(qmod, X, lev):
    P = np.column_stack([qmod[q].predict(X) for q in QS]); P.sort(axis=1)
    return P + lev[:, None]


def fit(df, featset='C', asof=None):
    """Fit a deployable bundle on the feature rows in df (features_{origin}.parquet layout).

    asof: exclusive start of the period the bundle will predict — normally the first day of the
    current month, matching train_eval_v2.py's monthly walk-forward refits. Rows whose
    origin_date is within 8 days of asof are excluded (targets not fully resolved).
    """
    feats = FEATSETS[featset]
    df = df[df.agile.notna()].copy()
    df['origin_date'] = pd.to_datetime(df.origin_date)
    ts = pd.Timestamp(asof) if asof is not None else pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()
    hist = df[df.origin_date < ts - pd.Timedelta(days=8)]           # all fully-resolved history
    cal_start = ts - pd.Timedelta(weeks=CAL_WEEKS) - pd.Timedelta(days=8)
    fit_ = hist[hist.origin_date < cal_start - pd.Timedelta(days=8)]  # fit set (older)
    cal = hist[hist.origin_date >= cal_start]                         # calibration set (recent)
    if len(fit_) == 0 or len(cal) == 0:
        raise ValueError(f"not enough history to fit: n_fit={len(fit_)} n_cal={len(cal)} (asof={ts.date()})")
    # ---- stage 1: fit on 'fit_', calibrate on 'cal' ----
    yfit = (fit_.agile - fit_[LEVEL]).values
    qmod = {q: lgb.train(dict(PARAMS, objective='quantile', alpha=q), lgb.Dataset(fit_[feats], yfit), NR_Q) for q in QS}
    Pcal = _qpred(qmod, cal[feats], cal[LEVEL].values)
    ycal = cal.agile.values
    margins = {}
    for h in sorted(cal.horizon.unique()):
        mk = (cal.horizon == h).values
        for lo, hi, a in [(1, 5, 0.2), (0, 6, 0.1)]:
            E = np.maximum(Pcal[mk, lo] - ycal[mk], ycal[mk] - Pcal[mk, hi])
            n = mk.sum(); k = min(int(np.ceil((n + 1) * (1 - a))), n) - 1
            margins[(int(h), lo, hi)] = float(np.sort(E)[k])
        margins[(int(h), 'bias')] = float(np.median(ycal[mk] - Pcal[mk, 3]))
    # ---- stage 2: refit on all history for serving ----
    yall = (hist.agile - hist[LEVEL]).values
    qmod = {q: lgb.train(dict(PARAMS, objective='quantile', alpha=q), lgb.Dataset(hist[feats], yall), NR_Q) for q in QS}
    events = {}
    for ev in ['neg', 'sub5', 'hi40']:
        y = hist[ev].values
        if y.sum() < 30:
            events[ev] = float(y.mean())
        else:
            events[ev] = lgb.train(dict(PARAMS, objective='binary', scale_pos_weight=1.0), lgb.Dataset(hist[feats], y), NR_B)
    y10 = (hist.agile < 10).astype(int).values
    events['sub10'] = lgb.train(dict(PARAMS, objective='binary'), lgb.Dataset(hist[feats], y10), NR_B)
    return {'model_version': MODEL_VERSION, 'featset': featset, 'feats': feats, 'quantiles': QS,
            'level': LEVEL, 'qmod': qmod, 'events': events, 'margins': margins,
            'asof': str(ts.date()), 'trained_through': str(hist.origin_date.max().date()),
            'n_hist': int(len(hist)), 'n_fit': int(len(fit_)), 'n_cal': int(len(cal))}


def _margin(margins, h, key):
    """Margin for horizon h, falling back to the nearest calibrated horizon."""
    if (int(h), *key) in margins:
        return margins[(int(h), *key)]
    avail = sorted({k[0] for k in margins})
    return margins[(min(avail, key=lambda a: abs(a - int(h))), *key)]


def predict(bundle, rows):
    """Predict the bundle on feature rows (needs the bundle's feats + level + horizon columns).

    Returns a DataFrame aligned to rows.index with raw quantiles q05_raw..q95_raw, the
    conformally adjusted q05..q95 (monotone; q50 bias-corrected), and p_neg/p_sub5/p_sub10/p_hi40.
    """
    feats, margins = bundle['feats'], bundle['margins']
    X = rows[feats]
    P = _qpred(bundle['qmod'], X, rows[bundle['level']].values)
    out = pd.DataFrame(index=rows.index)
    for i, q in enumerate(bundle['quantiles']):
        out[f'q{int(q*100):02d}_raw'] = P[:, i]
    hz = rows.horizon.values
    m1090 = np.array([_margin(margins, h, (1, 5)) for h in hz])
    m0595 = np.array([_margin(margins, h, (0, 6)) for h in hz])
    bias = np.array([_margin(margins, h, ('bias',)) for h in hz])
    out['q10'] = out.q10_raw - m1090; out['q90'] = out.q90_raw + m1090
    out['q05'] = out.q05_raw - m0595; out['q95'] = out.q95_raw + m0595
    out['q50'] = out.q50_raw + bias
    out['q25'] = out.q25_raw; out['q75'] = out.q75_raw
    for ev in ['neg', 'sub5', 'sub10', 'hi40']:
        mdl = bundle['events'][ev]
        out[f'p_{ev}'] = mdl if isinstance(mdl, float) else mdl.predict(X)
    return out


def save_bundle(bundle, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path, compress=3)


def load_bundle(path):
    return joblib.load(path)
