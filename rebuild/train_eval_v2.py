"""v2: regularised LightGBM quantile + event heads, level-adjusted target, conformal calibration on a rolling
calibration window, monthly refits (walk-forward). Region K domestic Agile.
Usage: python train_eval_v2.py <origin 1635|1000> <featset A|C> [start_month YYYY-MM] [end_month YYYY-MM]
"""
import pandas as pd, numpy as np, lightgbm as lgb, sys, time, warnings
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
warnings.filterwarnings('ignore')
from pathlib import Path
_R = Path(__file__).resolve().parent.as_posix()
D = f"{_R}/data"; O = f"{_R}/out"
ORIGIN = sys.argv[1]; FS = sys.argv[2]
START = sys.argv[3] if len(sys.argv) > 3 else '2025-08'
END = sys.argv[4] if len(sys.argv) > 4 else '2026-08'
HMAX = int(sys.argv[5]) if len(sys.argv) > 5 else 99
df = pd.read_parquet(f"{D}/features_{ORIGIN}.parquet")
df = df[df.agile.notna() & (df.horizon <= HMAX)].copy()
df['origin_date'] = pd.to_datetime(df.origin_date)

CAL = ['hh_idx', 'dow', 'is_weekend', 'is_holiday', 'doy_sin', 'doy_cos', 'month', 'is_peak', 'horizon']
LAGS = ['px_lag7', 'px_lastknown_sameslot', 'px_day_mean', 'px_day_min', 'px_day_max', 'px_day_neg', 'px_day_sub5',
        'px_roll7_mean', 'px_roll7_min', 'px_roll7_neg', 'px_roll7_sub5', 'px_roll30_mean', 'px_roll30_neg', 'px_day_offpeak_mean', 'px_slot_roll7']
DEM = ['nd_fc_hh', 'nd_fc_min', 'nd_fc_max', 'nd_fc_mean', 'lk_nd_fc_mean', 'd_nd_fc_mean', 'd_nd_fc_min']
REN = ['emb_wind', 'emb_solar', 'emb_wind_lf', 'emb_solar_lf', 'emb_solar_daymax', 'emb_wind_daymean', 'emb_wind_daymin', 'emb_ren_daymean', 'ren_share_proxy', 'windfor', 'windfor_share',
       'lk_emb_wind_daymean', 'lk_emb_solar_daymax', 'lk_emb_ren_daymean', 'lk_emb_wind_slot', 'lk_emb_solar_slot', 'd_emb_wind_daymean', 'd_emb_solar_daymax', 'd_emb_wind_slot', 'd_emb_solar_slot']
FEATS = {'A': CAL + LAGS, 'B': CAL + LAGS + DEM, 'C': CAL + LAGS + DEM + REN}[FS]
QS = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
PARAMS = dict(learning_rate=0.03, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, num_threads=2)
NR_Q, NR_B = 450, 400
LEVEL = 'px_day_offpeak_mean'   # de-level target by last known day's off-peak mean
CAL_WEEKS = 8

months = pd.period_range(START, END, freq='M')
preds = []
for mth in months:
    t0 = time.time()
    ts = mth.to_timestamp(); te = (mth + 1).to_timestamp()
    tst = df[(df.origin_date >= ts) & (df.origin_date < te)]
    if len(tst) == 0: continue
    hist = df[df.origin_date < ts - pd.Timedelta(days=8)]           # all fully-resolved history
    cal_start = ts - pd.Timedelta(weeks=CAL_WEEKS) - pd.Timedelta(days=8)
    fit = hist[hist.origin_date < cal_start - pd.Timedelta(days=8)]  # fit set (older)
    cal = hist[hist.origin_date >= cal_start]                        # calibration set (recent)
    # ---- stage 1: fit on 'fit', calibrate on 'cal' ----
    yfit = (fit.agile - fit[LEVEL]).values
    qmod = {q: lgb.train(dict(PARAMS, objective='quantile', alpha=q), lgb.Dataset(fit[FEATS], yfit), NR_Q) for q in QS}
    def qpred(X, lev):
        P = np.column_stack([qmod[q].predict(X) for q in QS]); P.sort(axis=1)
        return P + lev[:, None]
    Pcal = qpred(cal[FEATS], cal[LEVEL].values)
    ycal = cal.agile.values
    # conformal margins per horizon for the 10-90 and 5-95 intervals, and median bias
    margins = {}
    for h in sorted(cal.horizon.unique()):
        mk = (cal.horizon == h).values
        for lo, hi, a in [(1, 5, 0.2), (0, 6, 0.1)]:
            E = np.maximum(Pcal[mk, lo] - ycal[mk], ycal[mk] - Pcal[mk, hi])
            n = mk.sum(); k = min(int(np.ceil((n + 1) * (1 - a))), n) - 1
            margins[(h, lo, hi)] = np.sort(E)[k]
        margins[(h, 'bias')] = np.median(ycal[mk] - Pcal[mk, 3])
    # ---- stage 2: refit on all history (fit+cal) for test predictions, then apply margins ----
    yall = (hist.agile - hist[LEVEL]).values
    qmod = {q: lgb.train(dict(PARAMS, objective='quantile', alpha=q), lgb.Dataset(hist[FEATS], yall), NR_Q) for q in QS}
    Pte = qpred(tst[FEATS], tst[LEVEL].values)
    res = tst[['origin_date', 'horizon', 'target_local', 'agile', 'ss', 'neg', 'sub5', 'hi40', 'px_lag7', 'px_lastknown_sameslot', 'px_slot_roll7', 'hh_idx', 'dow']].copy()
    for i, q in enumerate(QS): res[f'q{int(q*100):02d}_raw'] = Pte[:, i]
    hz = tst.horizon.values
    res['q10'] = res.q10_raw - np.array([margins[(h, 1, 5)] for h in hz]); res['q90'] = res.q90_raw + np.array([margins[(h, 1, 5)] for h in hz])
    res['q05'] = res.q05_raw - np.array([margins[(h, 0, 6)] for h in hz]); res['q95'] = res.q95_raw + np.array([margins[(h, 0, 6)] for h in hz])
    res['q50'] = res.q50_raw + np.array([margins[(h, 'bias')] for h in hz])
    res['q25'] = res.q25_raw; res['q75'] = res.q75_raw
    # event heads (binary), trained on all history; probabilities calibrated by isotonic on cal? keep raw + report reliability
    for ev, thr_name in [('neg', 'neg'), ('sub5', 'sub5'), ('hi40', 'hi40')]:
        y = hist[ev].values
        if y.sum() < 30:
            res[f'p_{ev}'] = y.mean(); continue
        bm = lgb.train(dict(PARAMS, objective='binary', scale_pos_weight=1.0), lgb.Dataset(hist[FEATS], y), NR_B)
        res[f'p_{ev}'] = bm.predict(tst[FEATS])
    # sub10 head (staged flags)
    y10 = (hist.agile < 10).astype(int).values
    bm = lgb.train(dict(PARAMS, objective='binary'), lgb.Dataset(hist[FEATS], y10), NR_B)
    res['p_sub10'] = bm.predict(tst[FEATS]); res['sub10'] = (tst.agile < 10).astype(int).values
    res['month'] = str(mth); res['featset'] = FS
    preds.append(res)
    print(f"{FS} {mth} n_test={len(tst)} n_fit={len(fit)} n_cal={len(cal)} margins h2 10-90={margins[(2,1,5)] if (2,1,5) in margins else margins[(1,1,5)]:.2f} done {time.time()-t0:.0f}s", flush=True)

P = pd.concat(preds, ignore_index=True)
P.to_parquet(f"{O}/preds_v2_{ORIGIN}_{FS}.parquet", index=False)

# ---- summary ----
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
        for ev in ['neg', 'sub5', 'sub10', 'hi40']:
            yv = r[ev].values; p = r[f'p_{ev}'].values
            row[f'{ev}_rate'] = yv.mean()
            if yv.sum() >= 5 and (yv == 0).sum() >= 5:
                row[f'{ev}_auc'] = roc_auc_score(yv, p); row[f'{ev}_ap'] = average_precision_score(yv, p)
                row[f'{ev}_bss'] = 1 - brier_score_loss(yv, p) / brier_score_loss(yv, np.full(len(yv), yv.mean()))
        rows.append(row)
    return pd.DataFrame(rows)
S = summarize(P)
S.to_csv(f"{O}/summary_v2_{ORIGIN}_{FS}.csv", index=False)
pd.set_option('display.width', 250)
print(S.round(3).to_string())
