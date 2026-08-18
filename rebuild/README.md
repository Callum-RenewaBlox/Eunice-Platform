# Eunice rebuild — prototype pipeline (Aug 2026)

Everything here was run in a clean Linux workspace with Python 3.11: pandas, numpy, lightgbm, scikit-learn,
duckdb, holidays, pyarrow, matplotlib, requests. Absolute paths default to `/home/claude/eunice`; change `D`/`O`
at the top of each script (or symlink) to relocate.

## 1. Data pulls (public APIs, no keys)

```bash
python fetch_octopus.py AGILE-24-10-01 K                 # domestic Agile, region K (all regions: A,B,C,...)
python fetch_octopus.py AGILE-BUS-25-02-05 K            # Shape Shifters (commercial) — for the affine check only
python fetch_neso.py                                    # NESO archives: embedded wind/solar 14d (all issues, 2024→), demand cardinal points, historic demand
python fetch_elexon.py WINDFOR                           # Elexon WINDFOR history by publish time (transmission wind, ~3 days ahead)
python fetch_elexon.py AGWS ; python fetch_elexon.py DEMAND   # actual wind/solar and demand outturn (diagnostics)
```

## 2. As-of feature store

```bash
python build_asof_embedded.py          # DuckDB: latest embedded-forecast issue <= origin (16:35 and 10:00 London), targets D-1..D+8
python build_features.py 1635          # origin 16:35: targets D+2..D+7 (Eunice's cron; D+1 published)
python build_features.py 1000          # origin 10:00: targets D+1..D+7 ("tomorrow" before publication)
python add_lastknown_feats.py 1635 ; python add_lastknown_feats.py 1000
```
Outputs `data/features_{1635,1000}.parquet` (one row per origin × target half-hour) with targets `agile`, `ss`, flags
`neg/sub5/hi40` and ~60 features. Only information available at the origin time is used (embedded/demand/WINDFOR issues,
published prices).

## 3. Walk-forward training and evaluation

```bash
python train_eval_v2.py 1635 C 2025-08 2026-08          # monthly refits Aug-25→Aug-26, all history, conformal calibration
python train_eval_v2.py 1000 C 2025-08 2026-08 3        # 10:00 origin, leads 1-3 only
```
Featset `A` = calendar + price memory (no grid forecasts), `B` = + demand, `C` = full. Outputs `out/preds_v2_*.parquet`,
`out/summary_v2_*.csv`. `charts_results.py` draws the report figures; `score_eunice_live.py data.sqlite` scores Eunice's own
stored runs.

## 4. Production sketch (what to wire into eunice-platform)

* Nightly: append latest NESO embedded issues (live CSV), NESO 2–14d demand, Elexon WINDFOR/NDF, Octopus prices, into the
  same parquet/BigQuery tables; rebuild the as-of rows for today's origins only.
* Weekly/monthly: refit LightGBM quantiles (7) + heads (neg/<5p/<10p/>40p) on all history; conformal margins from the last
  8 weeks per lead; store model + margins.
* Daily 16:35 (and 09:45 for "tomorrow"): predict region K wholesale-equivalent, map to 14 regions with `region_affine.csv`,
  write p05..p95 + probabilities to `prediction`; UI shows staged flags (possible/likely/very likely) per slot and per day.
* Live scorecard: the query in `score_eunice_live.py`, run against stored vintages, replaces the in-app "backtest".
