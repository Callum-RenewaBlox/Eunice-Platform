"""Fetch Elexon Insights datasets over a date range in chunks.
 - WINDFOR: transmission wind generation forecast (all publications) -> features for D+1/D+2
 - AGWS actuals: wind & solar actual generation (half-hourly) -> diagnostics
"""
import requests, pandas as pd, sys, time, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = f"{Path(__file__).resolve().parent.as_posix()}/data/elexon"
os.makedirs(OUT, exist_ok=True)
BASE = "https://data.elexon.co.uk/bmrs/api/v1"


def get(url, params):
    for a in range(6):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.status_code == 200:
                return r.json()
            print('status', r.status_code, url, params, r.text[:200], flush=True)
        except Exception as e:
            print('retry', a, e, flush=True)
        time.sleep(3 * (a + 1))
    raise RuntimeError('failed')


def fetch_dataset_by_publish(ds, start, end, step_days=3):
    fn = f"{OUT}/{ds}.parquet"
    if os.path.exists(fn):
        print('exists', fn); return
    rows = []
    t = start
    while t < end:
        t2 = min(t + timedelta(days=step_days), end)
        j = get(f"{BASE}/datasets/{ds}", {"publishDateTimeFrom": t.strftime('%Y-%m-%dT%H:%MZ'), "publishDateTimeTo": t2.strftime('%Y-%m-%dT%H:%MZ'), "format": "json"})
        rows.extend(j.get('data', []))
        t = t2
        if len(rows) % 20000 < 700:
            print(ds, t, len(rows), flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(fn, index=False)
    print('saved', fn, len(df), flush=True)


def fetch_actual_wind_solar(start, end, step_days=7):
    fn = f"{OUT}/actual_wind_solar.parquet"
    if os.path.exists(fn):
        print('exists', fn); return
    rows = []
    t = start
    while t < end:
        t2 = min(t + timedelta(days=step_days), end)
        j = get(f"{BASE}/generation/actual/per-type/wind-and-solar", {"from": t.strftime('%Y-%m-%dT%H:%MZ'), "to": t2.strftime('%Y-%m-%dT%H:%MZ'), "format": "json"})
        d = j.get('data', j) if isinstance(j, dict) else j
        rows.extend(d)
        t = t2
    df = pd.DataFrame(rows)
    df.to_parquet(fn, index=False)
    print('saved', fn, len(df), flush=True)


def fetch_demand_outturn(start, end, step_days=7):
    fn = f"{OUT}/demand_outturn.parquet"
    if os.path.exists(fn):
        print('exists', fn); return
    rows = []
    t = start
    while t < end:
        t2 = min(t + timedelta(days=step_days), end)
        j = get(f"{BASE}/demand/outturn", {"settlementDateFrom": t.strftime('%Y-%m-%d'), "settlementDateTo": t2.strftime('%Y-%m-%d'), "format": "json"})
        d = j.get('data', j) if isinstance(j, dict) else j
        rows.extend(d)
        t = t2
    df = pd.DataFrame(rows)
    df.to_parquet(fn, index=False)
    print('saved', fn, len(df), flush=True)


if __name__ == '__main__':
    start = datetime(2024, 9, 10, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc)
    which = sys.argv[1]
    if which == 'WINDFOR':
        fetch_dataset_by_publish('WINDFOR', start, end, step_days=2)
    elif which == 'AGWS':
        fetch_actual_wind_solar(start, end)
    elif which == 'DEMAND':
        fetch_demand_outturn(start, end)
    elif which == 'MID':
        # market index prices (APX) half-hourly
        fn = f"{OUT}/MID.parquet"
        rows = []
        t = start
        while t < end:
            t2 = min(t + timedelta(days=7), end)
            j = get(f"{BASE}/datasets/MID", {"from": t.strftime('%Y-%m-%dT%H:%MZ'), "to": t2.strftime('%Y-%m-%dT%H:%MZ'), "format": "json"})
            rows.extend(j.get('data', []))
            t = t2
        pd.DataFrame(rows).to_parquet(fn, index=False)
        print('saved', fn, len(rows))
