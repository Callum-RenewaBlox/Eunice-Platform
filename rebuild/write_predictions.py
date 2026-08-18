"""Predict region K with the persisted bundle and write all 14 GSP regions to `prediction`.

Flow: pipeline.build_origin_rows -> model.predict (region K, published-price scale) -> per-region
peak/offpeak affine map from region_affine.csv -> db.insert_predictions_v2.

Region mapping and VAT. region_affine.csv is fitted on EX-VAT prices:
    price_exvat_region = intercept + slope * price_exvat_K, then published = ex-VAT x VAT, cap 100p.
The model output lives on the published-price scale of its level anchor (the last known day's
off-peak mean), so the VAT multiplier used to DE-scale the model output is the one in force on
the LAST KNOWN day, while the multiplier used to RE-scale the mapped price is the one in force
on the TARGET day. VAT on domestic electricity is abolished from 1 Oct 2026: the multiplier is
1.05 before that date and 1.00 from it. (During the ~1 week when pre-October origins predict
October targets this correctly drops the published level by the removed VAT; the event-head
thresholds keep their published-price meaning to within that 5%.)

Event probabilities (p_neg/p_sub5/p_sub10/p_hi40) are computed for region K and written
unchanged for all regions — regional threshold shifts are within the affine residual noise.

The monthly refit happens here: the bundle is refitted when its `asof` month is not the current
month (mirroring train_eval_v2.py's walk-forward), then persisted to out/bundle_{origin}_C.joblib.

Usage: python write_predictions.py <1635|1000> [--date YYYY-MM-DD] [--no-fetch] [--refit] [--dry-run]
"""
import sys
from datetime import date as _date
from pathlib import Path

import numpy as np
import pandas as pd

_R = Path(__file__).resolve().parent
# repo root goes AFTER the script dir (sys.path[0]) so that `import model` resolves to
# rebuild/model.py, not the repo root's legacy model.py
sys.path.insert(1, str(_R.parent))
import db                                    # noqa: E402  (repo root)
import model                                 # noqa: E402  (rebuild/)
import pipeline                              # noqa: E402  (rebuild/)
assert hasattr(model, 'MODEL_VERSION') and hasattr(model, 'fit'), \
    "import collision: expected rebuild/model.py on sys.path[0]"

FEATSET = 'C'
PRODUCT = 'AGILE'
CAP_P = 100.0
VAT_ABOLISHED = _date(2026, 10, 1)          # domestic electricity VAT removed from this date
QCOLS = ['q05', 'q10', 'q25', 'q50', 'q75', 'q90', 'q95']


def vat_mult(d):
    return 1.05 if d < VAT_ABOLISHED else 1.0


def load_or_refit_bundle(origin, month_start, force=False):
    bpath = _R / 'out' / f'bundle_{origin}_{FEATSET}.joblib'
    if bpath.exists() and not force:
        bundle = model.load_bundle(bpath)
        if bundle.get('asof') == str(month_start) and bundle.get('model_version') == model.MODEL_VERSION:
            return bundle
    feats_all = pd.read_parquet(f"{pipeline.D}/features_{origin}.parquet")
    print(f"refitting bundle for {origin} asof {month_start} on {len(feats_all)} feature rows...", flush=True)
    bundle = model.fit(feats_all, FEATSET, asof=str(month_start))
    model.save_bundle(bundle, bpath)
    print(f"bundle saved: {bpath.name} (hist n={bundle['n_hist']}, trained through {bundle['trained_through']})", flush=True)
    return bundle


def map_regions(rows, pred, known_until):
    """Map region-K predictions to every region; returns {region: DataFrame of db-ready rows}."""
    aff = pd.read_csv(_R / 'region_affine.csv')
    vat_ku = vat_mult(known_until)
    tgt_dates = rows.target_local.dt.date.values
    vat_tgt = np.array([vat_mult(d) for d in tgt_dates])
    seg = np.where(rows.is_peak.values == 1, 'peak', 'offpeak')
    valid_from = rows.target_utc.dt.strftime('%Y-%m-%dT%H:%M:%SZ').values
    valid_to = (rows.target_utc + pd.Timedelta(minutes=30)).dt.strftime('%Y-%m-%dT%H:%M:%SZ').values
    origin_iso = rows.origin_utc.iloc[0].strftime('%Y-%m-%dT%H:%M:%SZ')
    out = {}
    for region, ra in aff.groupby('region'):
        p = ra.set_index('segment')
        a = np.where(seg == 'peak', p.loc['peak', 'intercept_exvat'], p.loc['offpeak', 'intercept_exvat'])
        b = np.where(seg == 'peak', p.loc['peak', 'slope'], p.loc['offpeak', 'slope'])
        df = pd.DataFrame({'valid_from': valid_from, 'valid_to': valid_to,
                           'origin_time': origin_iso, 'lead_days': rows.horizon.values})
        for q in QCOLS:
            mapped = (a + b * (pred[q].values / vat_ku)) * vat_tgt
            df[q.replace('q', 'p')] = np.minimum(mapped, CAP_P)
        df['predicted_price'] = df['p50']
        for ev in ['neg', 'sub5', 'sub10', 'hi40']:
            df[f'p_{ev}'] = np.clip(pred[f'p_{ev}'].values, 0.0, 1.0)
        out[region] = df
    return out


def main(argv):
    origin = argv[1]
    assert origin in ('1635', '1000'), "usage: write_predictions.py <1635|1000> [--date YYYY-MM-DD] [--no-fetch] [--refit] [--dry-run]"
    date = None
    if '--date' in argv:
        date = argv[argv.index('--date') + 1]
    rows = pipeline.build_origin_rows(origin, date, fetch='--no-fetch' not in argv)
    known_until = rows.known_until.iloc[0]
    od = rows.origin_date.iloc[0]
    month_start = _date(od.year, od.month, 1)
    bundle = load_or_refit_bundle(origin, month_start, force='--refit' in argv)
    pred = model.predict(bundle, rows)
    regions = map_regions(rows, pred, known_until)
    k = regions['K']
    print(f"origin {od} {origin}: {len(k)} slots/region, leads {sorted(set(k.lead_days))}, "
          f"K p50 range {k.p50.min():.1f}..{k.p50.max():.1f}p, mean P(neg) {k.p_neg.mean():.3f}", flush=True)
    if '--dry-run' in argv:
        print("dry run — nothing written")
        return
    db.init_db()
    for region, df in regions.items():
        db.insert_predictions_v2(df.to_dict('records'), bundle['model_version'], region, PRODUCT)
    print(f"wrote {sum(len(d) for d in regions.values())} prediction rows "
          f"({len(regions)} regions) as {bundle['model_version']}", flush=True)


if __name__ == '__main__':
    main(sys.argv)
