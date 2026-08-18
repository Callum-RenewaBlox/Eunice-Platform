"""Train/evaluate probabilistic Agile price models with tail-event heads. Rolling-origin evaluation.
Usage: python train_eval.py 1635
"""
import pandas as pd, numpy as np, lightgbm as lgb, sys, time, json, warnings
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
warnings.filterwarnings('ignore')
from pathlib import Path
_R = Path(__file__).resolve().parent.as_posix()
D = f"{_R}/data"; O = f"{_R}/out"
ORIGIN = sys.argv[1] if len(sys.argv) > 1 else '1635'
df = pd.read_parquet(f"{D}/features_{ORIGIN}.parquet")
df = df[df.agile.notna()].copy()
df['origin_date'] = pd.to_datetime(df.origin_date)

CAL = ['hh_idx', 'dow', 'is_weekend', 'is_holiday', 'doy_sin', 'doy_cos', 'month', 'is_peak', 'horizon']
LAGS = ['px_lag7', 'px_lastknown_sameslot', 'px_day_mean', 'px_day_min', 'px_day_max', 'px_day_neg', 'px_day_sub5',
        'px_roll7_mean', 'px_roll7_min', 'px_roll7_neg', 'px_roll7_sub5', 'px_roll30_mean', 'px_roll30_neg', 'px_day_offpeak_mean', 'px_slot_roll7']
DEM = ['nd_fc_hh', 'nd_fc_min', 'nd_fc_max', 'nd_fc_mean']
REN = ['emb_wind', 'emb_solar', 'emb_wind_lf', 'emb_solar_lf', 'emb_solar_daymax', 'emb_wind_daymean', 'emb_wind_daymin', 'emb_ren_daymean', 'ren_share_proxy', 'windfor', 'windfor_share']
FEATSETS = {
    'A_cal_lags': CAL + LAGS,                       # ~ what a model without any grid/weather forecast can do
    'B_cal_lags_demand': CAL + LAGS + DEM,
    'C_full': CAL + LAGS + DEM + REN,               # + NESO embedded wind/solar 14d + Elexon WINDFOR
}
QS = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
FOLDS = [('2025-08-01', '2026-02-01'), ('2026-02-01', '2026-08-11')]   # test windows by origin date (train = all origins < test start, with target before test start)

PARAMS = dict(learning_rate=0.05, num_leaves=63, min_data_in_leaf=80, feature_fraction=0.85, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=2)


def fit_quantiles(Xtr, ytr, Xte, n_round=700):
    out = {}
    for q in QS:
        m = lgb.train(dict(PARAMS, objective='quantile', alpha=q), lgb.Dataset(Xtr, ytr), num_boost_round=n_round)
        out[q] = m.predict(Xte)
    P = np.column_stack([out[q] for q in QS])
    P.sort(axis=1)  # enforce monotone quantiles
    return {q: P[:, i] for i, q in enumerate(QS)}


def fit_binary(Xtr, ytr, Xte, n_round=500):
    if ytr.sum() < 20:
        return np.full(len(Xte), ytr.mean())
    m = lgb.train(dict(PARAMS, objective='binary'), lgb.Dataset(Xtr, ytr), num_boost_round=n_round)
    return m.predict(Xte)


def prec_recall_at(p, y, thr):
    pred = p >= thr
    tp = (pred & (y == 1)).sum(); fp = (pred & (y == 0)).sum(); fn = (~pred & (y == 1)).sum()
    return (tp / (tp + fp) if tp + fp else np.nan), (tp / (tp + fn) if tp + fn else np.nan), int(tp + fp)


results = []
preds_all = []
for fs_name, feats in FEATSETS.items():
    for (ts, te) in FOLDS:
        t0 = time.time()
        ts_, te_ = pd.Timestamp(ts), pd.Timestamp(te)
        tr = df[(df.origin_date < ts_ - pd.Timedelta(days=8))]   # avoid target overlap into test window
        tst = df[(df.origin_date >= ts_) & (df.origin_date < te_)]
        Xtr, Xte = tr[feats], tst[feats]
        q = fit_quantiles(Xtr, tr.agile.values, Xte)
        pneg = fit_binary(Xtr, tr.neg.values, Xte)
        psub5 = fit_binary(Xtr, tr.sub5.values, Xte)
        phi40 = fit_binary(Xtr, tr.hi40.values, Xte)
        res = tst[['origin_date', 'horizon', 'target_local', 'agile', 'ss', 'neg', 'sub5', 'hi40', 'px_lag7', 'px_lastknown_sameslot', 'px_slot_roll7']].copy()
        for k in QS: res[f'q{int(k*100):02d}'] = q[k]
        res['p_neg'] = pneg; res['p_sub5'] = psub5; res['p_hi40'] = phi40
        res['featset'] = fs_name; res['fold'] = f"{ts}..{te}"
        preds_all.append(res)
        y = res.agile.values
        # metrics overall + per horizon
        for h in ['all'] + sorted(res.horizon.unique().tolist()):
            r = res if h == 'all' else res[res.horizon == h]
            yy = r.agile.values
            row = dict(featset=fs_name, fold=f"{ts}..{te}", horizon=h, n=len(r),
                       mae_median=np.abs(r.q50 - yy).mean(), bias=(r.q50 - yy).mean(),
                       cov10_90=((yy >= r.q10) & (yy <= r.q90)).mean(), cov05_95=((yy >= r.q05) & (yy <= r.q95)).mean(),
                       mae_persist7=np.abs(r.px_lag7 - yy).mean(), mae_lastknown=np.abs(r.px_lastknown_sameslot - yy).mean(), mae_slotroll7=np.abs(r.px_slot_roll7 - yy).mean(),
                       neg_rate=r.neg.mean(), sub5_rate=r.sub5.mean(), hi40_rate=r.hi40.mean())
            for ev, p in [('neg', r.p_neg), ('sub5', r.p_sub5), ('hi40', r.p_hi40)]:
                yv = r[ev].values
                if yv.sum() >= 5 and (yv == 0).sum() >= 5:
                    row[f'{ev}_auc'] = roc_auc_score(yv, p); row[f'{ev}_ap'] = average_precision_score(yv, p); row[f'{ev}_brier'] = brier_score_loss(yv, p)
                    row[f'{ev}_brier_clim'] = brier_score_loss(yv, np.full(len(yv), yv.mean()))
                    for thr in [0.3, 0.5]:
                        pr, rc, npos = prec_recall_at(p, yv, thr)
                        row[f'{ev}_prec@{thr}'] = pr; row[f'{ev}_rec@{thr}'] = rc
                # quantile-implied event probability alternative: share of quantile mass below threshold
            results.append(row)
        print(fs_name, ts, te, 'done in', round(time.time() - t0), 's', flush=True)

R = pd.DataFrame(results)
R.to_csv(f"{O}/eval_{ORIGIN}.csv", index=False)
P = pd.concat(preds_all, ignore_index=True)
P.to_parquet(f"{O}/preds_{ORIGIN}.parquet", index=False)
pd.set_option('display.width', 250)
cols = ['featset', 'fold', 'horizon', 'n', 'mae_median', 'bias', 'cov10_90', 'mae_persist7', 'mae_slotroll7', 'neg_rate', 'neg_auc', 'neg_ap', 'neg_brier', 'neg_brier_clim', 'neg_prec@0.5', 'neg_rec@0.5', 'sub5_auc', 'sub5_ap', 'sub5_prec@0.5', 'sub5_rec@0.5', 'hi40_auc', 'hi40_ap']
print(R[R.horizon == 'all'][cols].round(3).to_string())
print()
print(R[(R.featset == 'C_full')][cols].round(3).to_string())
