"""v3 candidate: train_eval_v2 plus the report's phase-3 upgrades that need no external key:
  - peak-level anchor: last known day's 16-19h mean (px_day_peak_mean) + peak/off-peak spread
    as features (the level target stays anchored on the off-peak mean, exactly as v2)
  - >60p event head alongside >40p
  - adaptive conformal window: when the last 7 days of the calibration window are much worse
    (median |error| > 2x the window's), margins come from the most recent 4 weeks only

Promotion gate: walk-forward 2025-08..2026-08 must beat rebuild/out/summary_v2_1635_C.csv on
MAE, P10-P90 coverage and negative-price AP before any of this reaches model.py / serving.
Usage: python train_eval_v3.py <origin 1635|1000> <featset A|C> [start_month] [end_month]
"""
import pandas as pd, numpy as np, lightgbm as lgb, sys, time, warnings
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from zoneinfo import ZoneInfo
warnings.filterwarnings('ignore')
from pathlib import Path
_R = Path(__file__).resolve().parent.as_posix()
D = f"{_R}/data"; O = f"{_R}/out"
LON = ZoneInfo('Europe/London')
ORIGIN = sys.argv[1]; FS = sys.argv[2]
START = sys.argv[3] if len(sys.argv) > 3 else '2025-08'
END = sys.argv[4] if len(sys.argv) > 4 else '2026-08'
HMAX = int(sys.argv[5]) if len(sys.argv) > 5 else 99


def augment_price_anchors(df):
    """Add the last known day's peak (16-19h local) mean and the peak/off-peak spread."""
    px = pd.read_parquet(f"{D}/octopus_AGILE-24-10-01_K.parquet")[['valid_from', 'value_inc_vat']]
    t = px.valid_from.dt.tz_convert(LON)
    px = px.assign(local_date=t.dt.date, is_peak=(t.dt.hour >= 16) & (t.dt.hour < 19))
    pk = px[px.is_peak].groupby('local_date').value_inc_vat.mean().rename('px_day_peak_mean').reset_index()
    pk = pk.rename(columns={'local_date': 'known_until'})
    df = df.merge(pk, on='known_until', how='left')
    df['px_peak_offpeak_spread'] = df.px_day_peak_mean - df.px_day_offpeak_mean
    return df


df = pd.read_parquet(f"{D}/features_{ORIGIN}.parquet")
df = df[df.agile.notna() & (df.horizon <= HMAX)].copy()
df = augment_price_anchors(df)
df['origin_date'] = pd.to_datetime(df.origin_date)

CAL = ['hh_idx', 'dow', 'is_weekend', 'is_holiday', 'doy_sin', 'doy_cos', 'month', 'is_peak', 'horizon']
LAGS = ['px_lag7', 'px_lastknown_sameslot', 'px_day_mean', 'px_day_min', 'px_day_max', 'px_day_neg', 'px_day_sub5',
        'px_roll7_mean', 'px_roll7_min', 'px_roll7_neg', 'px_roll7_sub5', 'px_roll30_mean', 'px_roll30_neg', 'px_day_offpeak_mean', 'px_slot_roll7',
        'px_day_peak_mean', 'px_peak_offpeak_spread']
DEM = ['nd_fc_hh', 'nd_fc_min', 'nd_fc_max', 'nd_fc_mean', 'lk_nd_fc_mean', 'd_nd_fc_mean', 'd_nd_fc_min']
REN = ['emb_wind', 'emb_solar', 'emb_wind_lf', 'emb_solar_lf', 'emb_solar_daymax', 'emb_wind_daymean', 'emb_wind_daymin', 'emb_ren_daymean', 'ren_share_proxy', 'windfor', 'windfor_share',
       'lk_emb_wind_daymean', 'lk_emb_solar_daymax', 'lk_emb_ren_daymean', 'lk_emb_wind_slot', 'lk_emb_solar_slot', 'd_emb_wind_daymean', 'd_emb_solar_daymax', 'd_emb_wind_slot', 'd_emb_solar_slot']
FEATS = {'A': CAL + LAGS, 'B': CAL + LAGS + DEM, 'C': CAL + LAGS + DEM + REN}[FS]
QS = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
PARAMS = dict(learning_rate=0.03, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, num_threads=2)
NR_Q, NR_B = 450, 400
LEVEL = 'px_day_offpeak_mean'
CAL_WEEKS = 8
CAL_WEEKS_FAST = 4          # adaptive: shrink to this when the recent regime has shifted

months = pd.period_range(START, END, freq='M')
preds = []
for mth in months:
    t0 = time.time()
    ts = mth.to_timestamp(); te = (mth + 1).to_timestamp()
    tst = df[(df.origin_date >= ts) & (df.origin_date < te)]
    if len(tst) == 0: continue
    hist = df[df.origin_date < ts - pd.Timedelta(days=8)]
    cal_start = ts - pd.Timedelta(weeks=CAL_WEEKS) - pd.Timedelta(days=8)
    fit = hist[hist.origin_date < cal_start - pd.Timedelta(days=8)]
    cal = hist[hist.origin_date >= cal_start]
    yfit = (fit.agile - fit[LEVEL]).values
    qmod = {q: lgb.train(dict(PARAMS, objective='quantile', alpha=q), lgb.Dataset(fit[FEATS], yfit), NR_Q) for q in QS}
    def qpred(X, lev):
        P = np.column_stack([qmod[q].predict(X) for q in QS]); P.sort(axis=1)
        return P + lev[:, None]
    Pcal = qpred(cal[FEATS], cal[LEVEL].values)
    ycal = cal.agile.values
    # ---- adaptive conformal window ----
    abs_err = np.abs(ycal - Pcal[:, 3])
    last7 = (cal.origin_date >= cal.origin_date.max() - pd.Timedelta(days=7)).values
    adaptive = last7.any() and np.median(abs_err[last7]) > 2 * np.median(abs_err)
    if adaptive:
        keep = (cal.origin_date >= cal.origin_date.max() - pd.Timedelta(weeks=CAL_WEEKS_FAST)).values
        Pcal_m, ycal_m, cal_m = Pcal[keep], ycal[keep], cal[keep]
    else:
        Pcal_m, ycal_m, cal_m = Pcal, ycal, cal
    margins = {}
    for h in sorted(cal_m.horizon.unique()):
        mk = (cal_m.horizon == h).values
        for lo, hi, a in [(1, 5, 0.2), (0, 6, 0.1)]:
            E = np.maximum(Pcal_m[mk, lo] - ycal_m[mk], ycal_m[mk] - Pcal_m[mk, hi])
            n = mk.sum(); k = min(int(np.ceil((n + 1) * (1 - a))), n) - 1
            margins[(h, lo, hi)] = np.sort(E)[k]
        margins[(h, 'bias')] = np.median(ycal_m[mk] - Pcal_m[mk, 3])
    yall = (hist.agile - hist[LEVEL]).values
    qmod = {q: lgb.train(dict(PARAMS, objective='quantile', alpha=q), lgb.Dataset(hist[FEATS], yall), NR_Q) for q in QS}
    Pte = qpred(tst[FEATS], tst[LEVEL].values)
    res = tst[['origin_date', 'horizon', 'target_local', 'agile', 'ss', 'neg', 'sub5', 'hi40', 'px_lag7', 'px_lastknown_sameslot', 'px_slot_roll7', 'hh_idx', 'dow']].copy()
    for i, q in enumerate(QS): res[f'q{int(q*100):02d}_raw'] = Pte[:, i]
    hz = tst.horizon.values
    def _m(key):
        avail = sorted({k[0] for k in margins if isinstance(k, tuple) and len(k) > 1})
        return np.array([margins[(h, *key)] if (h, *key) in margins else margins[(min(avail, key=lambda a: abs(a - h)), *key)] for h in hz])
    res['q10'] = res.q10_raw - _m((1, 5)); res['q90'] = res.q90_raw + _m((1, 5))
    res['q05'] = res.q05_raw - _m((0, 6)); res['q95'] = res.q95_raw + _m((0, 6))
    res['q50'] = res.q50_raw + _m(('bias',))
    res['q25'] = res.q25_raw; res['q75'] = res.q75_raw
    for ev in ['neg', 'sub5', 'hi40']:
        y = hist[ev].values
        if y.sum() < 30:
            res[f'p_{ev}'] = y.mean(); continue
        bm = lgb.train(dict(PARAMS, objective='binary', scale_pos_weight=1.0), lgb.Dataset(hist[FEATS], y), NR_B)
        res[f'p_{ev}'] = bm.predict(tst[FEATS])
    y10 = (hist.agile < 10).astype(int).values
    bm = lgb.train(dict(PARAMS, objective='binary'), lgb.Dataset(hist[FEATS], y10), NR_B)
    res['p_sub10'] = bm.predict(tst[FEATS]); res['sub10'] = (tst.agile < 10).astype(int).values
    y60 = (hist.agile > 60).astype(int).values
    if y60.sum() >= 30:
        bm = lgb.train(dict(PARAMS, objective='binary'), lgb.Dataset(hist[FEATS], y60), NR_B)
        res['p_hi60'] = bm.predict(tst[FEATS])
    else:
        res['p_hi60'] = y60.mean()
    res['hi60'] = (tst.agile > 60).astype(int).values
    res['month'] = str(mth); res['featset'] = FS
    preds.append(res)
    print(f"{FS} {mth} n_test={len(tst)} n_fit={len(fit)} n_cal={len(cal)} adaptive={adaptive} done {time.time()-t0:.0f}s", flush=True)

P = pd.concat(preds, ignore_index=True)
P.to_parquet(f"{O}/preds_v3_{ORIGIN}_{FS}.parquet", index=False)

def summarize(P):
    rows = []
    for h in ['all'] + sorted(P.horizon.unique().tolist()):
        r = P if h == 'all' else P[P.horizon == h]
        y = r.agile.values
        row = dict(horizon=h, n=len(r), mae=np.abs(r.q50 - y).mean(), bias=(r.q50 - y).mean(), mae_raw=np.abs(r.q50_raw - y).mean(),
                   cov10_90=((y >= r.q10) & (y <= r.q90)).mean(), cov05_95=((y >= r.q05) & (y <= r.q95)).mean(),
                   cov10_90_raw=((y >= r.q10_raw) & (y <= r.q90_raw)).mean(), width10_90=(r.q90 - r.q10).mean(),
                   mae_persist7=np.abs(r.px_lag7 - y).mean(), mae_slotroll7=np.abs(r.px_slot_roll7 - y).mean(),
                   mae_lastknown=np.abs(r.px_lastknown_sameslot - y).mean())
        for ev in ['neg', 'sub5', 'sub10', 'hi40', 'hi60']:
            yv = r[ev].values; p = r[f'p_{ev}'].values
            row[f'{ev}_rate'] = yv.mean()
            if yv.sum() >= 5 and (yv == 0).sum() >= 5:
                row[f'{ev}_auc'] = roc_auc_score(yv, p); row[f'{ev}_ap'] = average_precision_score(yv, p)
                row[f'{ev}_bss'] = 1 - brier_score_loss(yv, p) / brier_score_loss(yv, np.full(len(yv), yv.mean()))
        rows.append(row)
    return pd.DataFrame(rows)
S = summarize(P)
S.to_csv(f"{O}/summary_v3_{ORIGIN}_{FS}.csv", index=False)
pd.set_option('display.width', 250)
print(S.round(3).to_string())
