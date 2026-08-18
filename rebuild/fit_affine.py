"""Refit the per-region peak/offpeak affine map from published tariffs (monthly).

Same construction as the shipped region_affine.csv: on EX-VAT prices,
    price_exvat_region = intercept + slope * price_exvat_K
fitted separately for peak (16:00-18:59 London) and offpeak slots, per region, on a recent
window of the tariff table (regional peak adders change with tariff versions, so a rolling
window tracks them). VAT: domestic multiplier is 1.05 before 2026-10-01 and 1.00 after.

Writes rebuild/data/region_affine_fitted.csv (gitignored, carried in the Actions cache);
write_predictions.py prefers it over the shipped CSV when it is current.
Usage: python fit_affine.py [months_back]   (default 6)
"""
import sqlite3
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

_R = Path(__file__).resolve().parent
LON = ZoneInfo('Europe/London')
VAT_ABOLISHED = date(2026, 10, 1)
OUT = _R / 'data' / 'region_affine_fitted.csv'


def fit_affine(db_path, months_back=6, product='AGILE'):
    c = sqlite3.connect(str(db_path))
    cut = (pd.Timestamp.now(tz='UTC') - pd.DateOffset(months=months_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
    tf = pd.read_sql("SELECT valid_from, region, value_inc_vat FROM tariff WHERE product=? AND valid_from >= ?",
                     c, params=(product, cut))
    c.close()
    tf['valid_from'] = pd.to_datetime(tf.valid_from, utc=True)
    t = tf.valid_from.dt.tz_convert(LON)
    vat = np.where(t.dt.date < VAT_ABOLISHED, 1.05, 1.0)
    tf['exvat'] = tf.value_inc_vat / vat
    tf['segment'] = np.where((t.dt.hour >= 16) & (t.dt.hour < 19), 'peak', 'offpeak')
    k = tf[tf.region == 'K'][['valid_from', 'segment', 'exvat']].rename(columns={'exvat': 'exvat_k'})
    m = tf.merge(k, on=['valid_from', 'segment'])
    rows = []
    for (region, segment), g in m.groupby(['region', 'segment']):
        if len(g) < 500:
            continue
        slope, intercept = np.polyfit(g.exvat_k.values, g.exvat.values, 1)
        resid = g.exvat.values - (intercept + slope * g.exvat_k.values)
        rows.append(dict(region=region, segment=segment, intercept_exvat=round(intercept, 5),
                         slope=round(slope, 5), resid_sd=round(float(np.std(resid)), 4), n=len(g),
                         note='price_exvat_region = intercept + slope * price_exvat_K; refit monthly',
                         fitted_through=str(pd.Timestamp.now(tz='UTC').date())))
    out = pd.DataFrame(rows).sort_values(['region', 'segment'], ascending=[True, False])
    # sanity: identity for K, all 14 regions x 2 segments present
    kk = out[(out.region == 'K')]
    assert len(out) == 28, f"expected 28 rows, got {len(out)}"
    assert (kk.slope.round(3) == 1.0).all() and (kk.intercept_exvat.round(3) == 0.0).all(), "region K must be identity"
    return out


if __name__ == '__main__':
    sys.path.insert(1, str(_R.parent))
    from config import DB_PATH
    months = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    out = fit_affine(DB_PATH, months)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"fitted affine map from last {months} months -> {OUT.name}")
    print(out.to_string(index=False))
