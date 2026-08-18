"""Download NESO data-portal resources (historic forecast archives + demand actuals)."""
import requests, json, os, sys, time
from pathlib import Path

OUT = f"{Path(__file__).resolve().parent.as_posix()}/data/neso"
os.makedirs(OUT, exist_ok=True)

PKGS = ['embedded-wind-and-solar-forecasts', 'day-ahead-wind-forecast', '2-14-days-ahead-national-demand-forecast',
        '7-day-ahead-national-forecast', '1-day-ahead-demand-forecast', 'historic-demand-data',
        '14-days-ahead-wind-forecasts', '14-days-ahead-operational-metered-wind-forecasts',
        'day-ahead-half-hourly-demand-forecast-performance', 'national-carbon-intensity-forecast',
        '2-day-ahead-demand-forecast']

WANT = ['Embedded Solar and Wind Forecast Archive 2024', 'Embedded Solar and Wind Forecast Archive 2025',
        'Embedded Solar and Wind Forecast Archive 2026 (Jan- Jun)', 'Embedded Solar and Wind Forecast Archive 2026 (Jun - Dec)',
        'Embedded Solar and Wind Forecast', 'Historic Day Ahead Wind Forecasts', 'Historic 2-14 Day Ahead Demand Forecasts',
        'Historic 7 Day Ahead Demand Forecasts', 'Historic Day Ahead Demand Forecasts', 'Historic Demand Data 2024',
        'Historic Demand Data 2025', 'Historic Demand Data 2026', '14 Days Ahead Wind Forecast', 'Day Ahead Wind Forecast']


def get(url, **kw):
    for a in range(6):
        try:
            r = requests.get(url, timeout=kw.pop('timeout', 120), **kw)
            if r.status_code == 200:
                return r
            print('status', r.status_code, url, flush=True)
        except Exception as e:
            print('retry', a, url, e, flush=True)
        time.sleep(5 * (a + 1))
    raise RuntimeError('failed ' + url)


def main():
    res = {}
    for p in PKGS:
        d = get(f"https://api.neso.energy/api/3/action/package_show?id={p}").json()['result']
        for r in d['resources']:
            res[r['name']] = {'url': r['url'], 'id': r['id'], 'pkg': p, 'format': r.get('format'), 'last_modified': r.get('last_modified')}
            if p in ('14-days-ahead-operational-metered-wind-forecasts', 'day-ahead-half-hourly-demand-forecast-performance', '2-day-ahead-demand-forecast', '14-days-ahead-wind-forecasts'):
                print(p, '|', r['name'], '|', r['url'], flush=True)
    json.dump(res, open(f"{OUT}/resources.json", 'w'), indent=1)
    for w in WANT:
        info = res.get(w)
        if not info:
            print('MISSING', w); continue
        fn = f"{OUT}/" + w.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '') + '.csv'
        if os.path.exists(fn) and os.path.getsize(fn) > 0:
            print('exists', fn); continue
        t0 = time.time()
        with requests.get(info['url'], stream=True, timeout=300) as r:
            r.raise_for_status()
            n = 0
            with open(fn, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk); n += len(chunk)
        print(f"downloaded {w} -> {fn} {n/1e6:.1f} MB in {time.time()-t0:.0f}s", flush=True)


if __name__ == '__main__':
    main()
