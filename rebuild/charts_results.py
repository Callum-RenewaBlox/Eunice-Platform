import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score
from pathlib import Path
_R = Path(__file__).resolve().parent.as_posix()
D = f"{_R}/data"; O = f"{_R}/out"
BLUE, ORANGE, AQUA, YELLOW, RED, VIOLET, GREY, MAG = '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e34948', '#4a3aa7', '#52514e', '#e87ba4'
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': '#e6e6e3', 'grid.linewidth': 0.6, 'axes.edgecolor': '#c3c2b7'})

P = pd.read_parquet(f"{O}/preds_v2_1635_C.parquet")
E = pd.read_parquet(f"{D}/eunice_forward_preds_scored.parquet")
E3 = E[(E.model_version == 'hgbt_quantile_v3_trough')]

# ---------- Fig: coverage & negative-slot detection by lead ----------
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
ax = axes[0]
h = sorted(P.horizon.unique())
cov_new = [((P[P.horizon == k].agile >= P[P.horizon == k].q10) & (P[P.horizon == k].agile <= P[P.horizon == k].q90)).mean() * 100 for k in h]
lead = sorted(E3.lead_d.unique()); lead = [l for l in lead if 1 <= l <= 7]
cov_e = [E3[E3.lead_d == l]['cov'].mean() * 100 for l in lead]
ax.plot(h, cov_new, marker='o', color=BLUE, lw=2, label='Rebuilt (walk-forward Aug-25→Aug-26, region K)')
ax.plot(lead, cov_e, marker='o', color=ORANGE, lw=2, label='Eunice v3 live runs (Jun–Aug 26, all regions)')
ax.axhline(80, color=GREY, ls='--', lw=1); ax.text(7.05, 80.5, 'target 80%', color=GREY, fontsize=8, ha='right')
ax.set_ylim(0, 100); ax.set_xlabel('lead (days ahead)'); ax.set_ylabel('% of actuals inside P10–P90'); ax.set_title('Interval calibration', loc='left', fontsize=11)
ax.legend(frameon=False, fontsize=8, loc='lower left')
ax = axes[1]
mae_new = [np.abs(P[P.horizon == k].q50 - P[P.horizon == k].agile).mean() for k in h]
mae_e = [E3[E3.lead_d == l].err.abs().mean() for l in lead]
mae_p = [np.abs(P[P.horizon == k].px_lag7 - P[P.horizon == k].agile).mean() for k in h]
ax.plot(h, mae_new, marker='o', color=BLUE, lw=2, label='Rebuilt median')
ax.plot(lead, mae_e, marker='o', color=ORANGE, lw=2, label='Eunice v3 live runs')
ax.plot(h, mae_p, marker='o', color=GREY, lw=1.5, ls=':', label='same slot last week (naive)')
ax.set_ylim(0, 9); ax.set_xlabel('lead (days ahead)'); ax.set_ylabel('MAE, p/kWh'); ax.set_title('Point accuracy', loc='left', fontsize=11)
ax.legend(frameon=False, fontsize=8)
ax = axes[2]
rec_new = []
for k in h:
    r = P[P.horizon == k]; rec_new.append(((r.p_neg >= 0.1) & (r.neg == 1)).sum() / max(r.neg.sum(), 1) * 100)
rec_e = []
for l in lead:
    r = E3[E3.lead_d == l]; rec_e.append(((r.p_trough.fillna(0) >= 0.1) & (r.neg)).sum() / max(r.neg.sum(), 1) * 100)
ax.plot(h, rec_new, marker='o', color=BLUE, lw=2, label='Rebuilt: P(neg) ≥ 10%')
ax.plot(lead, rec_e, marker='o', color=ORANGE, lw=2, label='Eunice v3: p_trough ≥ 10%')
ax.set_ylim(0, 100); ax.set_xlabel('lead (days ahead)'); ax.set_ylabel('% of negative slots flagged'); ax.set_title('Negative-price recall', loc='left', fontsize=11)
ax.legend(frameon=False, fontsize=8)
plt.tight_layout(); plt.savefig(f"{O}/fig_eunice_vs_rebuilt.png", dpi=150); plt.close()

# ---------- Fig: example week — origin 2026-04-09 (Easter negatives Apr 11-12) ----------
def example(origin, fname, title):
    r = P[P.origin_date == pd.Timestamp(origin)].sort_values('target_local').copy()
    if len(r) == 0:
        print('no rows for', origin); return
    t = pd.to_datetime(r.target_local).dt.tz_convert('Europe/London')
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 6.2), sharex=True, gridspec_kw={'height_ratios': [2.2, 1]})
    a1.fill_between(t, r.q05, r.q95, color='#cde2fb', label='P05–P95')
    a1.fill_between(t, r.q10, r.q90, color='#86b6ef', label='P10–P90')
    a1.plot(t, r.q50, color=BLUE, lw=1.6, label='median')
    a1.plot(t, r.agile, color='#0b0b0b', lw=1.4, label='actual (published later)')
    a1.axhline(0, color=GREY, lw=0.8); a1.axhline(5, color=GREY, lw=0.6, ls=':')
    a1.set_ylabel('p/kWh inc VAT'); a1.set_title(title, loc='left', fontsize=11); a1.legend(frameon=False, ncol=4, fontsize=8, loc='upper left')
    w = pd.Timedelta(minutes=30)
    a2.bar(t, r.p_sub10 * 100, width=w, color='#cde2fb', label='P(< 10p)')
    a2.bar(t, r.p_sub5 * 100, width=w, color='#86b6ef', label='P(< 5p)')
    a2.bar(t, r.p_neg * 100, width=w, color='#1c5cab', label='P(negative)')
    a2.set_ylim(0, 100); a2.set_ylabel('probability, %'); a2.legend(frameon=False, ncol=3, fontsize=8, loc='upper left')
    for d in pd.date_range(t.min().normalize(), t.max().normalize(), freq='D'):
        a1.axvline(d, color='#e6e6e3', lw=0.8); a2.axvline(d, color='#e6e6e3', lw=0.8)
    a2.set_xlabel('target time (Europe/London)')
    plt.tight_layout(); plt.savefig(f"{O}/{fname}", dpi=150); plt.close()
example('2026-04-09', 'fig_example_easter2026.png', 'Forecast issued Thu 9 Apr 2026 16:35 for Sat 11 → Thu 16 Apr (Easter weekend) — rebuilt model, region K')
example('2026-06-05', 'fig_example_june2026.png', 'Forecast issued Fri 5 Jun 2026 16:35 for Sun 7 → Fri 12 Jun — rebuilt model, region K')
example('2026-08-06', 'fig_example_aug2026.png', 'Forecast issued Thu 6 Aug 2026 16:35 for Sat 8 → Thu 13 Aug — rebuilt model, region K')

# ---------- Fig: reliability + PR curves ----------
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
ax = axes[0]
for ev, col, lab in [('neg', '#1c5cab', 'negative'), ('sub5', '#5598e7', '< 5p'), ('sub10', '#9ec5f4', '< 10p')]:
    p = P[f'p_{ev}'].values; y = P[ev].values
    bins = [0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
    b = pd.cut(p, bins, include_lowest=True)
    g = pd.DataFrame({'p': p, 'y': y, 'b': b}).groupby('b', observed=True).agg(mean_p=('p', 'mean'), obs=('y', 'mean'), n=('y', 'size'))
    ax.plot(g.mean_p * 100, g.obs * 100, marker='o', color=col, lw=2, label=lab)
ax.plot([0, 100], [0, 100], color=GREY, ls='--', lw=1)
ax.set_xlabel('forecast probability, %'); ax.set_ylabel('observed frequency, %'); ax.set_title('Reliability of event probabilities (days 2–7)', loc='left', fontsize=11); ax.legend(frameon=False)
ax = axes[1]
for k, col in [(2, '#1c5cab'), (4, '#5598e7'), (7, '#9ec5f4')]:
    r = P[P.horizon == k]; pr, rc, _ = precision_recall_curve(r.neg, r.p_neg)
    ax.plot(rc * 100, pr * 100, color=col, lw=2, label=f'rebuilt, day {k} (AP {average_precision_score(r.neg, r.p_neg):.2f})')
e2 = E3[E3.lead_d >= 2]
pr, rc, _ = precision_recall_curve(e2.neg.astype(int), e2.p_trough.fillna(0))
ax.plot(rc * 100, pr * 100, color=ORANGE, lw=2, label=f'Eunice v3 live, lead ≥ 2 (AP {average_precision_score(e2.neg.astype(int), e2.p_trough.fillna(0)):.2f})')
ax.axhline(P.neg.mean() * 100, color=GREY, ls=':', lw=1); ax.text(60, P.neg.mean() * 100 + 1.5, 'base rate', color=GREY, fontsize=8)
ax.set_xlabel('recall — % of negative slots caught'); ax.set_ylabel('precision — % of flags correct'); ax.set_title('Negative-price flags: precision vs recall', loc='left', fontsize=11); ax.legend(frameon=False, fontsize=8)
plt.tight_layout(); plt.savefig(f"{O}/fig_reliability_pr.png", dpi=150); plt.close()

# ---------- Fig: monthly MAE ----------
P['m'] = P.month.astype(str)
mm = P.groupby('m').apply(lambda r: pd.Series({'rebuilt': np.abs(r.q50 - r.agile).mean(), 'naive': np.abs(r.px_lag7 - r.agile).mean(), 'cov': ((r.agile >= r.q10) & (r.agile <= r.q90)).mean() * 100}))
fig, ax = plt.subplots(figsize=(10, 3.4))
x = np.arange(len(mm))
ax.bar(x - 0.2, mm.naive, width=0.4, color='#c3c2b7', label='naive: same slot last week')
ax.bar(x + 0.2, mm.rebuilt, width=0.4, color=BLUE, label='rebuilt median (days 2–7)')
ax.set_xticks(x); ax.set_xticklabels(mm.index, rotation=45, ha='right', fontsize=8); ax.set_ylabel('MAE, p/kWh'); ax.set_title('Walk-forward accuracy by month (region K, forecasts issued 16:35 for days 2–7)', loc='left', fontsize=11)
ax.legend(frameon=False)
plt.tight_layout(); plt.savefig(f"{O}/fig_monthly_mae.png", dpi=150); plt.close()
print('charts done')
