import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
_R = Path(__file__).resolve().parent.as_posix()
D = f"{_R}/data"; O = f"{_R}/out"
BLUE, ORANGE, AQUA, YELLOW, RED, VIOLET, GREY = '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e34948', '#4a3aa7', '#52514e'
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': '#e6e6e3', 'grid.linewidth': 0.6, 'axes.edgecolor': '#c3c2b7'})

a = pd.read_parquet(f"{D}/octopus_AGILE-24-10-01_K.parquet")
a['t'] = a.valid_from.dt.tz_convert('Europe/London')
a['ym'] = a.t.dt.strftime('%Y-%m')
a = a[a.t >= '2024-10-01']
m = a.groupby('ym').value_inc_vat.agg(neg=lambda s: (s < 0).mean() * 100, sub5=lambda s: (s < 5).mean() * 100, sub10=lambda s: (s < 10).mean() * 100, hi40=lambda s: (s > 40).mean() * 100)

fig, ax = plt.subplots(figsize=(10, 3.8))
x = np.arange(len(m))
ax.bar(x, m.sub10, color='#cde2fb', width=0.8, label='< 10p')
ax.bar(x, m.sub5, color='#86b6ef', width=0.8, label='< 5p')
ax.bar(x, m.neg, color='#1c5cab', width=0.8, label='negative')
ax.plot(x, m.hi40, color=ORANGE, lw=2, marker='o', ms=4, label='> 40p')
ax.set_xticks(x); ax.set_xticklabels(m.index, rotation=60, ha='right', fontsize=8)
ax.set_ylabel('% of half-hour slots'); ax.set_title('Agile (region K, inc VAT): share of slots in each tail band, by month', loc='left', fontsize=11)
ax.legend(frameon=False, ncol=4, loc='upper left')
plt.tight_layout(); plt.savefig(f"{O}/fig_tail_by_month.png", dpi=150); plt.close()

# hour x dow heatmap of negative frequency and sub5
a['hour'] = a.t.dt.hour; a['dow'] = a.t.dt.dayofweek
fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
for ax, (lab, thr) in zip(axes, [('P(negative)', 0), ('P(< 5p)', 5)]):
    h = a.assign(e=(a.value_inc_vat < thr)).pivot_table(index='dow', columns='hour', values='e', aggfunc='mean') * 100
    im = ax.imshow(h.values, aspect='auto', cmap='Blues', vmin=0)
    ax.set_yticks(range(7)); ax.set_yticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    ax.set_xticks(range(0, 24, 2)); ax.set_xlabel('hour of day (local)'); ax.set_title(f'{lab} by weekday × hour, Oct-24 → Aug-26 (%)', loc='left', fontsize=10)
    ax.grid(False)
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
plt.tight_layout(); plt.savefig(f"{O}/fig_neg_heatmap.png", dpi=150); plt.close()
print(m.round(1).to_string())
