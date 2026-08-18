"""Score Eunice's stored forward runs (prediction table) against published tariff prices.
Usage: python score_eunice_live.py /path/to/data.sqlite [AGILE]
Reports MAE, P10-P90 coverage, negative-slot hit rates and p_trough behaviour by lead day and model version.

Also importable: load_scored() returns the vintage-joined scored frame; scorecard_by_lead()
returns the per-(model_version, lead) scorecard the app displays — the numbers on the page are
computed by exactly this code, so the CLI and the app always agree.
"""
import sqlite3, sys, pandas as pd, numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

MIN_RUN_ROWS = 1000        # a forward run spans all regions; backtest rows carry per-row generated_at
NEG_FLAG_P = 0.25          # "likely" tier: flag a slot as negative when P >= this


def load_scored(db, product='AGILE'):
    """Join stored forward-run vintages to published prices. Returns the scored slot frame."""
    c = sqlite3.connect(db)
    pr = pd.read_sql("select * from prediction where product=?", c, params=(product,))
    tf = pd.read_sql("select valid_from, region, value_inc_vat from tariff where product=?", c, params=(product,))
    c.close()
    pr['valid_from'] = pd.to_datetime(pr.valid_from, utc=True); pr['generated_at'] = pd.to_datetime(pr.generated_at, utc=True)
    tf['valid_from'] = pd.to_datetime(tf.valid_from, utc=True)
    m = pr.merge(tf, on=['valid_from', 'region'], how='left')
    m['lead_h'] = (m.valid_from - m.generated_at).dt.total_seconds() / 3600
    m['lead_d'] = np.ceil(m.lead_h / 24)
    runs = m.groupby(['model_version', 'generated_at']).size()
    fwd = runs[runs >= MIN_RUN_ROWS].reset_index()[['model_version', 'generated_at']]
    f = m.merge(fwd, on=['model_version', 'generated_at'])
    f = f[f.value_inc_vat.notna() & (f.lead_h > 0)].copy()
    f['err'] = f.predicted_price - f.value_inc_vat
    f['cov'] = (f.value_inc_vat >= f.p10) & (f.value_inc_vat <= f.p90)
    f['neg'] = f.value_inc_vat < 0; f['sub5'] = f.value_inc_vat < 5
    # negative-slot flag: rebuilt engine's p_neg, else the legacy p_trough (same event, P(<0))
    p_neg = f['p_neg'] if 'p_neg' in f.columns else pd.Series(np.nan, index=f.index)
    f['p_neg_eff'] = p_neg.fillna(f['p_trough'] if 'p_trough' in f.columns else np.nan)
    f['neg_flag'] = f.p_neg_eff >= NEG_FLAG_P
    return f


def summ(g):
    return pd.Series({'n': len(g), 'mae': g.err.abs().mean(), 'bias': g.err.mean(), 'cov10_90': g['cov'].mean(), 'neg_n': g.neg.sum(),
                      'p10<0 hit on neg': (g.p10[g.neg] < 0).mean() if g.neg.any() else np.nan,
                      'mean p_trough on neg': g.p_trough[g.neg].mean() if g.neg.any() else np.nan,
                      'mean p_trough on pos': g.p_trough[~g.neg].mean(),
                      'mae_on_neg': g.err[g.neg].abs().mean() if g.neg.any() else np.nan,
                      'mae_on_sub5': g.err[g.sub5].abs().mean() if g.sub5.any() else np.nan,
                      'bias_on_hi40': g.err[g.value_inc_vat > 40].mean()})


def _lead_row(g):
    flag, act = g.neg_flag, g.neg
    return pd.Series({
        'n': len(g), 'mae': g.err.abs().mean(), 'bias': g.err.mean(), 'cov10_90': g['cov'].mean(),
        'neg_n': int(act.sum()),
        'neg_recall': (flag & act).sum() / act.sum() if act.any() else np.nan,
        'neg_precision': (flag & act).sum() / flag.sum() if flag.any() else np.nan,
    })


def scorecard_by_lead(f):
    """The app's scorecard: per (model_version, lead_d) plus an 'all' row per model_version."""
    if f.empty:
        return pd.DataFrame(columns=['model_version', 'lead_d', 'n', 'mae', 'bias', 'cov10_90', 'neg_n', 'neg_recall', 'neg_precision'])
    by_lead = f.groupby(['model_version', 'lead_d']).apply(_lead_row).reset_index()
    overall = f.groupby('model_version').apply(_lead_row).reset_index()
    overall['lead_d'] = 0.0   # 0 = all leads
    return pd.concat([overall, by_lead], ignore_index=True)[['model_version', 'lead_d', 'n', 'mae', 'bias', 'cov10_90', 'neg_n', 'neg_recall', 'neg_precision']]


if __name__ == '__main__':
    db = sys.argv[1]; product = sys.argv[2] if len(sys.argv) > 2 else 'AGILE'
    f = load_scored(db, product)
    fwd_n = f.groupby(['model_version', 'generated_at']).ngroups
    pd.set_option('display.width', 250)
    print('forward runs:', fwd_n, 'scored slots:', len(f))
    if len(f):
        print(f.groupby('model_version').apply(summ).round(3).T.to_string())
        print(f.groupby(['model_version', 'lead_d']).apply(summ).round(3).to_string())
        print()
        print('scorecard (lead 0 = all leads; neg flag = P(neg) >= %.2f):' % NEG_FLAG_P)
        print(scorecard_by_lead(f).round(3).to_string(index=False))
        for mv, g in f.groupby('model_version'):
            if g.p_trough.notna().any() and g.neg.sum() > 5:
                print(mv, 'p_trough AUC %.3f AP %.3f' % (roc_auc_score(g.neg.astype(int), g.p_trough.fillna(0)), average_precision_score(g.neg.astype(int), g.p_trough.fillna(0))))
        f.to_parquet('eunice_forward_preds_scored.parquet', index=False)
