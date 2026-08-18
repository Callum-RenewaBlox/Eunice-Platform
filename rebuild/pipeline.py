"""Live as-of feature builder for a single origin date (16:35 or 10:00 London).

Reproduces build_features.py + add_lastknown_feats.py for one origin, sourcing anything newer
than the shipped archives from the live NESO / Elexon / Octopus endpoints:
  - NESO 'Embedded Solar and Wind Forecast' (current CSV, latest issue only — the issue time is
    taken from the CKAN resource's last_modified, since the live CSV carries no
    Forecast_Datetime column) -> data/live/embedded_issues.parquet
  - NESO demand cardinal points ('Day Ahead National Demand Forecast', '2-14 Days Ahead
    Cardinal Point Forecast', '7 Day Ahead Demand Forecast'; same last_modified stamping)
    -> data/live/demand_cp.parquet
  - Elexon Insights WINDFOR (all publications since the stored high-water mark)
    -> data/live/windfor.parquet
  - Octopus Agile region-K unit rates (domestic + business), appended to the archive parquets.

Each run appends the latest issues to those stores, so as-of history accumulates run over run;
the finished feature block is appended to features_{origin}.parquet (replacing any previous
rows for the same origin) so that later refits train on exactly what was served.

As-of discipline: for a live build (today's origin) the cutoff is max(origin time, now) — the
prediction is actually issued at run time, so it may honestly use everything available then.
For an explicit past date the cutoff is strictly the origin time, keeping backfills honest.

Usage: python pipeline.py <1635|1000> [YYYY-MM-DD] [--no-fetch]
"""
import sys, time
import numpy as np, pandas as pd, requests, holidays
from pathlib import Path
from zoneinfo import ZoneInfo

D = f"{Path(__file__).resolve().parent.as_posix()}/data"
LIVE = f"{D}/live"
LON = ZoneInfo('Europe/London')
NESO_API = "https://api.neso.energy/api/3/action/package_show"
ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"
OCTOPUS_BASE = "https://api.octopus.energy/v1/products/{prod}/electricity-tariffs/E-1R-{prod}-K/standard-unit-rates/"
DEMAND_RESOURCES = [('1-day-ahead-demand-forecast', 'Day Ahead National Demand Forecast'),
                    ('2-14-days-ahead-national-demand-forecast', '2-14 Days Ahead Cardinal Point Forecast'),
                    ('7-day-ahead-national-forecast', '7 Day Ahead Demand Forecast')]
# NESO refreshes these archives daily; self-seeded into data/neso/ when absent so the
# last-known-day demand features work from the very first run (and local backfills work at all).
DEMAND_ARCHIVES = [('1-day-ahead-demand-forecast', 'Historic Day Ahead Demand Forecasts', 'Historic_Day_Ahead_Demand_Forecasts.csv'),
                   ('2-14-days-ahead-national-demand-forecast', 'Historic 2-14 Day Ahead Demand Forecasts', 'Historic_214_Day_Ahead_Demand_Forecasts.csv'),
                   ('7-day-ahead-national-forecast', 'Historic 7 Day Ahead Demand Forecasts', 'Historic_7_Day_Ahead_Demand_Forecasts.csv')]

_S = requests.Session(); _S.headers['User-Agent'] = 'eunice-rebuild/1.0'


def _get(url, **kw):
    for a in range(5):
        try:
            r = _S.get(url, timeout=90, **kw)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(3 * (a + 1))
    raise RuntimeError(f"GET failed after retries: {url}")


def _now_utc():
    return pd.Timestamp.now(tz='UTC').tz_localize(None)


def _append_store(path, new, keys):
    """Append new rows to a parquet store, deduplicating on keys (new rows win)."""
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        new = pd.concat([pd.read_parquet(p), new], ignore_index=True)
    new = new.drop_duplicates(keys, keep='last').sort_values(keys).reset_index(drop=True)
    new.to_parquet(p, index=False)
    return new


def _neso_resource(pkg, name):
    j = _get(NESO_API, params={'id': pkg}).json()['result']
    for r in j['resources']:
        if r['name'] == name:
            return r['url'], pd.to_datetime(r['last_modified']).floor('s')
    raise RuntimeError(f"NESO resource '{name}' not found in package '{pkg}'")


def fetch_embedded():
    """Append the current NESO embedded wind/solar forecast (latest issue) to the live store."""
    url, issue = _neso_resource('embedded-wind-and-solar-forecasts', 'Embedded Solar and Wind Forecast')
    raw = pd.read_csv(pd.io.common.BytesIO(_get(url).content))
    tmin = raw.TIME_GMT.astype(str).str.slice(0, 2).astype(int) * 60 + raw.TIME_GMT.astype(str).str.slice(3, 5).astype(int)
    new = pd.DataFrame({
        'issue': issue,
        'target_start': pd.to_datetime(raw.DATE_GMT.astype(str).str.slice(0, 10)) + pd.to_timedelta(tmin - 30, unit='m'),
        'emb_wind': pd.to_numeric(raw.EMBEDDED_WIND_FORECAST, errors='coerce'),
        'wind_cap': pd.to_numeric(raw.EMBEDDED_WIND_CAPACITY, errors='coerce'),
        'emb_solar': pd.to_numeric(raw.EMBEDDED_SOLAR_FORECAST, errors='coerce'),
        'solar_cap': pd.to_numeric(raw.EMBEDDED_SOLAR_CAPACITY, errors='coerce'),
    })
    return _append_store(f"{LIVE}/embedded_issues.parquet", new, ['issue', 'target_start'])


def seed_demand_archives():
    """Download the NESO historic demand archives into data/neso/ if absent (they are refreshed
    daily upstream). Gives the pipeline the same demand history build_features.py used."""
    for pkg, name, fname in DEMAND_ARCHIVES:
        p = Path(f"{D}/neso/{fname}")
        if p.exists() and p.stat().st_size > 0:
            continue
        url, _ = _neso_resource(pkg, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        with _S.get(url, timeout=600, stream=True) as r:
            r.raise_for_status()
            with open(p, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        print(f"seeded {fname} ({p.stat().st_size / 1e6:.1f} MB)", flush=True)


def fetch_demand():
    """Append the current NESO demand cardinal-point forecasts (latest issues) to the live store."""
    seed_demand_archives()
    parts = []
    for pkg, name in DEMAND_RESOURCES:
        url, issue = _neso_resource(pkg, name)
        raw = pd.read_csv(pd.io.common.BytesIO(_get(url).content))
        parts.append(pd.DataFrame({
            'issue': issue,
            'TARGETDATE': pd.to_datetime(raw.TARGETDATE.astype(str), format='%Y%m%d').dt.date,
            'DAYSAHEAD': raw.DAYSAHEAD.astype(int),
            'FORECASTDEMAND': pd.to_numeric(raw.FORECASTDEMAND, errors='coerce'),
            'CARDINALPOINT': raw.CARDINALPOINT.astype(str),
            'CP_ST_TIME': raw.CP_ST_TIME.astype(int),
            'CP_END_TIME': raw.CP_END_TIME.astype(int),
        }))
    new = pd.concat(parts, ignore_index=True)
    return _append_store(f"{LIVE}/demand_cp.parquet", new,
                         ['issue', 'TARGETDATE', 'CARDINALPOINT', 'CP_ST_TIME', 'CP_END_TIME'])


def fetch_windfor():
    """Append Elexon WINDFOR publications since the stored high-water mark to the live store."""
    p = Path(f"{LIVE}/windfor.parquet")
    if p.exists():
        start = pd.to_datetime(pd.read_parquet(p).publishTime.max()) - pd.Timedelta(hours=1)
    else:
        start = _now_utc() - pd.Timedelta(days=3)
    r = _get(f"{ELEXON_BASE}/datasets/WINDFOR",
             params={'publishDateTimeFrom': start.strftime('%Y-%m-%dT%H:%MZ'),
                     'publishDateTimeTo': _now_utc().strftime('%Y-%m-%dT%H:%MZ'), 'format': 'json'})
    rows = r.json().get('data', [])
    if not rows:
        return pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=['publishTime', 'startTime', 'generation'])
    raw = pd.DataFrame(rows)
    new = pd.DataFrame({
        'publishTime': pd.to_datetime(raw.publishTime, utc=True).dt.tz_localize(None),
        'startTime': pd.to_datetime(raw.startTime, utc=True).dt.tz_localize(None),
        'generation': pd.to_numeric(raw.generation, errors='coerce'),
    })
    return _append_store(f"{LIVE}/windfor.parquet", new, ['publishTime', 'startTime'])


def fetch_octopus():
    """Append new Octopus region-K unit rates (domestic Agile + business) to the archive parquets."""
    for prod in ['AGILE-24-10-01', 'AGILE-BUS-25-02-05']:
        path = Path(f"{D}/octopus_{prod}_K.parquet")
        old = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        params = {'page_size': 1500}
        if len(old):
            params['period_from'] = pd.to_datetime(old.valid_from.max()).strftime('%Y-%m-%dT%H:%M:%SZ')
        url, rows = OCTOPUS_BASE.format(prod=prod) + '?' + '&'.join(f"{k}={v}" for k, v in params.items()), []
        while url:
            j = _get(url).json()
            rows.extend(j['results']); url = j.get('next')
        if not rows:
            continue
        new = pd.DataFrame(rows)
        new['valid_from'] = pd.to_datetime(new.valid_from, utc=True)
        new['valid_to'] = pd.to_datetime(new.valid_to, utc=True)
        both = pd.concat([old, new], ignore_index=True) if len(old) else new
        both = both.sort_values('valid_from').drop_duplicates('valid_from', keep='last').reset_index(drop=True)
        both.to_parquet(path, index=False)
        print(f"octopus {prod}: +{len(new)} rows fetched, store now to {both.valid_from.max()}", flush=True)


def update_stores():
    """Fetch all live sources; each failure is non-fatal (the build proceeds with stored data)."""
    for name, fn in [('octopus', fetch_octopus), ('embedded', fetch_embedded),
                     ('demand', fetch_demand), ('windfor', fetch_windfor)]:
        try:
            fn()
            print(f"store updated: {name}", flush=True)
        except Exception as e:
            print(f"WARNING: live fetch failed for {name}: {e}", flush=True)


def _load_prices():
    ag = pd.read_parquet(f"{D}/octopus_AGILE-24-10-01_K.parquet")[['valid_from', 'value_inc_vat']].rename(columns={'valid_from': 't', 'value_inc_vat': 'agile'})
    ss = pd.read_parquet(f"{D}/octopus_AGILE-BUS-25-02-05_K.parquet")[['valid_from', 'value_inc_vat']].rename(columns={'valid_from': 't', 'value_inc_vat': 'ss'})
    px = ag.merge(ss, on='t', how='left').sort_values('t').reset_index(drop=True)
    px['t_utc'] = px.t.dt.tz_convert('UTC').dt.tz_localize(None)
    return px


def _emb_candidates(origin, od, origin_utc, cutoff):
    """Candidate embedded-forecast rows for one origin: the archive-derived as-of rows for this
    origin_date (if the shipped store covers it) plus live-store issues in the same window."""
    parts = []
    ap = Path(f"{D}/asof_embedded_{origin}.parquet")
    if ap.exists():
        a = pd.read_parquet(ap)
        a = a[pd.to_datetime(a.origin_date).dt.date == od]
        parts.append(a[['issue', 'target_start', 'emb_wind', 'emb_solar', 'wind_cap', 'solar_cap']])
    lp = Path(f"{LIVE}/embedded_issues.parquet")
    if lp.exists():
        l = pd.read_parquet(lp)
        l = l[(l.issue <= cutoff) & (l.issue > origin_utc - pd.Timedelta(hours=30))
              & (l.target_start >= origin_utc - pd.Timedelta(days=1)) & (l.target_start < origin_utc + pd.Timedelta(days=9))]
        parts.append(l[['issue', 'target_start', 'emb_wind', 'emb_solar', 'wind_cap', 'solar_cap']])
    if not parts:
        return pd.DataFrame(columns=['issue', 'target_start', 'emb_wind', 'emb_solar', 'wind_cap', 'solar_cap'])
    cand = pd.concat(parts, ignore_index=True)
    # latest issue <= cutoff per target slot; stable sort keys keep the tie-break deterministic
    # (matters on the clocks-back day, when two UTC slots share one local wall-clock time)
    return (cand.sort_values(['issue', 'target_start'], kind='mergesort')
                .groupby('target_start', as_index=False).tail(1)
                .sort_values('target_start', kind='mergesort'))


def _load_demand_cp():
    parts = []
    for f in ['Historic_214_Day_Ahead_Demand_Forecasts.csv', 'Historic_Day_Ahead_Demand_Forecasts.csv',
              'Historic_7_Day_Ahead_Demand_Forecasts.csv']:
        p = Path(f"{D}/neso/{f}")
        if p.exists():
            raw = pd.read_csv(p)
            raw['issue'] = pd.to_datetime(raw.FORECAST_TIMESTAMP, utc=True).dt.tz_localize(None)
            raw['TARGETDATE'] = pd.to_datetime(raw.TARGETDATE).dt.date
            parts.append(raw[['issue', 'TARGETDATE', 'DAYSAHEAD', 'FORECASTDEMAND', 'CARDINALPOINT', 'CP_ST_TIME', 'CP_END_TIME']])
    lp = Path(f"{LIVE}/demand_cp.parquet")
    if lp.exists():
        parts.append(pd.read_parquet(lp))
    if not parts:
        return pd.DataFrame(columns=['issue', 'TARGETDATE', 'DAYSAHEAD', 'FORECASTDEMAND', 'CARDINALPOINT', 'CP_ST_TIME', 'CP_END_TIME'])
    cp = pd.concat(parts, ignore_index=True)
    cp = cp[cp.issue >= pd.Timestamp('2024-08-01')]
    cp['cp_min'] = (cp.CP_ST_TIME // 100) * 60 + cp.CP_ST_TIME % 100
    cp['cp_max'] = (cp.CP_END_TIME // 100) * 60 + cp.CP_END_TIME % 100
    cp['cp_mid'] = (cp.cp_min + cp.cp_max) / 2.0
    return cp


def _load_windfor():
    parts = []
    for p in [Path(f"{D}/elexon/WINDFOR.parquet"), Path(f"{LIVE}/windfor.parquet")]:
        if p.exists():
            w = pd.read_parquet(p)
            w['publishTime'] = pd.to_datetime(w.publishTime, utc=True).dt.tz_localize(None)
            w['startTime'] = pd.to_datetime(w.startTime, utc=True).dt.tz_localize(None)
            parts.append(w[['publishTime', 'startTime', 'generation']])
    if not parts:
        return pd.DataFrame(columns=['publishTime', 'startTime', 'generation'])
    return pd.concat(parts, ignore_index=True).drop_duplicates(['publishTime', 'startTime'], keep='last')


def build_origin_rows(origin='1635', date=None, fetch=True, append=True):
    """Build the feature rows for one origin date; optionally append them to
    features_{origin}.parquet (replacing prior rows for the same origin). Returns the rows."""
    assert origin in ('1635', '1000')
    if fetch:
        update_stores()
    h_min, h_max = (2, 7) if origin == '1635' else (1, 7)
    hh, mm = (16, 35) if origin == '1635' else (10, 0)
    now = _now_utc()
    od = pd.to_datetime(date).date() if date else pd.Timestamp.now(tz=LON).date()
    origin_utc = pd.Timestamp(od.year, od.month, od.day, hh, mm, tz=LON).tz_convert('UTC').tz_localize(None)
    live_mode = date is None or (now - origin_utc) < pd.Timedelta(hours=12)
    cutoff = max(origin_utc, now) if live_mode else origin_utc
    known_until = (pd.Timestamp(od) + pd.Timedelta(days=1 if origin == '1635' else 0)).date()

    px = _load_prices()
    px_idx = px.set_index('t_utc')
    # The model's price anchors need the last known day published. Octopus's day-ahead window
    # ends at the 22:30-local slot (23:00/23:30 belong to the next publication), so that is the
    # boundary to check; the known day's daily stats then cover 46 of 48 local slots at the live
    # edge, which shifts the level anchor by well under 0.5% versus the historical build.
    ku_end = pd.Timestamp(known_until.year, known_until.month, known_until.day, 22, 30, tz=LON).tz_convert('UTC').tz_localize(None)
    if px.t_utc.max() < ku_end:
        raise RuntimeError(f"Agile prices for the last known day ({known_until}) are not published yet "
                           f"(store ends {px.t_utc.max()}, need {ku_end}); run again after ~16:15 London.")

    # ---------------- target grid ----------------
    rows = []
    for h in range(h_min, h_max + 1):
        tgt_day = pd.Timestamp(od) + pd.Timedelta(days=h)
        start = pd.Timestamp(tgt_day.year, tgt_day.month, tgt_day.day, 0, 0, tz=LON)
        slots = pd.date_range(start, start + pd.Timedelta(hours=23, minutes=30), freq='30min')
        rows.append(pd.DataFrame({'origin_date': od, 'origin_utc': origin_utc, 'horizon': h, 'target_local': slots}))
    tg = pd.concat(rows, ignore_index=True)
    tg['target_utc'] = tg.target_local.dt.tz_convert('UTC').dt.tz_localize(None)
    tg = tg.merge(px[['t_utc', 'agile', 'ss']].rename(columns={'t_utc': 'target_utc'}), on='target_utc', how='left')

    # ---------------- calendar ----------------
    uk_hol = holidays.country_holidays('GB', subdiv='ENG')
    tl = tg.target_local
    tg['hh_idx'] = tl.dt.hour * 2 + tl.dt.minute // 30
    tg['dow'] = tl.dt.dayofweek
    tg['is_weekend'] = (tg.dow >= 5).astype(int)
    tg['is_holiday'] = tl.dt.date.map(lambda d: d in uk_hol).astype(int)
    tg['doy'] = tl.dt.dayofyear
    tg['doy_sin'] = np.sin(2 * np.pi * tg.doy / 365.25); tg['doy_cos'] = np.cos(2 * np.pi * tg.doy / 365.25)
    tg['month'] = tl.dt.month
    tg['is_peak'] = ((tl.dt.hour >= 16) & (tl.dt.hour < 19)).astype(int)

    # ---------------- embedded wind/solar as-of ----------------
    emb = _emb_candidates(origin, od, origin_utc, cutoff)
    emb = emb.rename(columns={'target_start': 'target_utc', 'issue': 'emb_issue'})
    tg = tg.merge(emb[['target_utc', 'emb_wind', 'emb_solar', 'wind_cap', 'solar_cap', 'emb_issue']], on='target_utc', how='left')
    tg['emb_wind_lf'] = tg.emb_wind / tg.wind_cap
    tg['emb_solar_lf'] = tg.emb_solar / tg.solar_cap
    g = tg.groupby('horizon')
    tg['emb_solar_daymax'] = g.emb_solar.transform('max')
    tg['emb_wind_daymean'] = g.emb_wind.transform('mean')
    tg['emb_wind_daymin'] = g.emb_wind.transform('min')
    tg['emb_ren_daymean'] = (tg.emb_wind + tg.emb_solar).groupby(tg.horizon).transform('mean')

    # ---------------- WINDFOR as-of ----------------
    wf = _load_windfor()
    tg['windfor'] = np.nan; tg['windfor_pub'] = pd.NaT
    pubs = np.sort(wf.publishTime.unique()) if len(wf) else np.array([], dtype='datetime64[ns]')
    i = np.searchsorted(pubs, np.datetime64(cutoff), side='right') - 1
    if i >= 0:
        grp = wf[wf.publishTime == pubs[i]]
        s = grp.set_index('startTime').generation.sort_index()
        s = s[~s.index.duplicated()]
        idx = pd.date_range(s.index.min(), s.index.max(), freq='30min')
        s2 = s.reindex(idx).interpolate(limit=2)
        wfi = pd.DataFrame({'target_utc': s2.index, 'windfor_v': s2.values, 'windfor_pub_v': pubs[i]})
        tg = tg.merge(wfi, on='target_utc', how='left')
        tg['windfor'] = tg.windfor_v; tg['windfor_pub'] = tg.windfor_pub_v
        tg = tg.drop(columns=['windfor_v', 'windfor_pub_v'])

    # ---------------- NESO demand cardinal points as-of ----------------
    cp = _load_demand_cp()
    tg['min_of_day'] = tg.target_local.dt.hour * 60 + tg.target_local.dt.minute + 15  # slot midpoint
    aggs, interps = [], []
    for h in range(h_min, h_max + 1):
        tdate = (pd.Timestamp(od) + pd.Timedelta(days=h)).date()
        m = cp[(cp.TARGETDATE == tdate) & (cp.issue <= cutoff)]
        if len(m) == 0:
            continue
        m = m[m.issue == m.issue.max()]
        aggs.append({'horizon': h, 'nd_fc_min': m.FORECASTDEMAND.min(), 'nd_fc_max': m.FORECASTDEMAND.max(),
                     'nd_fc_mean': m.FORECASTDEMAND.mean(), 'nd_fc_daysahead': m.DAYSAHEAD.iloc[0], 'nd_issue': m.issue.iloc[0]})
        grp = m.sort_values('cp_mid').drop_duplicates('cp_mid')
        x = grp.cp_mid.values; y = grp.FORECASTDEMAND.values.astype(float)
        x = np.r_[x[-1] - 1440, x, x[0] + 1440]; y = np.r_[y[-1], y, y[0]]  # wrap-around
        mod = np.arange(15, 1440, 30)
        interps.append(pd.DataFrame({'horizon': h, 'min_of_day': mod, 'nd_fc_hh': np.interp(mod, x, y)}))
    if aggs:
        tg = tg.merge(pd.DataFrame(aggs), on='horizon', how='left')
        tg = tg.merge(pd.concat(interps, ignore_index=True), on=['horizon', 'min_of_day'], how='left')
    else:
        for c in ['nd_fc_min', 'nd_fc_max', 'nd_fc_mean', 'nd_fc_daysahead', 'nd_fc_hh']:
            tg[c] = np.nan
        tg['nd_issue'] = pd.NaT

    # residual-demand proxies (MW)
    tg['resid_emb'] = tg.nd_fc_hh - tg.emb_solar * 0  # ND already nets embedded; keep separate features
    tg['ren_share_proxy'] = (tg.emb_wind + tg.emb_solar) / (tg.nd_fc_hh + tg.emb_wind + tg.emb_solar)
    tg['windfor_share'] = tg.windfor / tg.nd_fc_hh

    # ---------------- price lags (known at origin) ----------------
    tg['known_until'] = known_until
    lag7_utc = (tg.target_local - pd.Timedelta(days=7)).dt.tz_convert('UTC').dt.tz_localize(None)
    tg['px_lag7'] = px_idx.agile.reindex(lag7_utc.values).values
    tg['ss_lag7'] = px_idx.ss.reindex(lag7_utc.values).values
    kd = pd.to_datetime(tg.known_until)
    last_known_slot = pd.to_datetime(kd.dt.strftime('%Y-%m-%d') + ' ' + tg.target_local.dt.strftime('%H:%M')).dt.tz_localize(LON, ambiguous='NaT', nonexistent='shift_forward')
    lks_utc = last_known_slot.dt.tz_convert('UTC').dt.tz_localize(None)
    tg['px_lastknown_sameslot'] = px_idx.agile.reindex(lks_utc.values).values
    tg['ss_lastknown_sameslot'] = px_idx.ss.reindex(lks_utc.values).values
    px['local_date'] = px.t.dt.tz_convert(LON).dt.date
    dstats = px.groupby('local_date').agile.agg(px_day_mean='mean', px_day_min='min', px_day_max='max',
                                                px_day_neg=lambda s: (s < 0).sum(), px_day_sub5=lambda s: (s < 5).sum()).reset_index()
    dstats['px_roll7_mean'] = dstats.px_day_mean.rolling(7).mean()
    dstats['px_roll7_min'] = dstats.px_day_min.rolling(7).min()
    dstats['px_roll7_neg'] = dstats.px_day_neg.rolling(7).sum()
    dstats['px_roll7_sub5'] = dstats.px_day_sub5.rolling(7).sum()
    dstats['px_roll30_mean'] = dstats.px_day_mean.rolling(30).mean()
    dstats['px_roll30_neg'] = dstats.px_day_neg.rolling(30).sum()
    px['is_peak'] = ((px.t.dt.tz_convert(LON).dt.hour >= 16) & (px.t.dt.tz_convert(LON).dt.hour < 19))
    op = px[~px.is_peak].groupby('local_date').agile.mean().rename('px_day_offpeak_mean').reset_index()
    dstats = dstats.merge(op, on='local_date', how='left')
    dstats['known_until'] = dstats.local_date
    tg = tg.merge(dstats.drop(columns=['local_date']), on='known_until', how='left')
    px['hh_idx'] = px.t.dt.tz_convert(LON).dt.hour * 2 + px.t.dt.tz_convert(LON).dt.minute // 30
    pv = px.pivot_table(index='local_date', columns='hh_idx', values='agile')
    pv7 = pv.rolling(7, min_periods=5).mean()
    pv7s = pv7.stack().rename('px_slot_roll7').reset_index().rename(columns={'local_date': 'known_until'})
    tg = tg.merge(pv7s, on=['known_until', 'hh_idx'], how='left')

    # ---------------- last-known-day driver features + deltas ----------------
    lk = emb.copy()
    if len(lk):
        tloc = pd.to_datetime(lk.target_utc).dt.tz_localize('UTC').dt.tz_convert(LON)
        lk['hh_idx'] = tloc.dt.hour * 2 + tloc.dt.minute // 30
        lk = lk[tloc.dt.date.values == known_until]
    if len(lk):
        tg['lk_emb_wind_daymean'] = lk.emb_wind.mean()
        tg['lk_emb_solar_daymax'] = lk.emb_solar.max()
        tg['lk_emb_ren_daymean'] = (lk.emb_wind + lk.emb_solar).mean()
        lk_slot = lk[['hh_idx', 'emb_wind', 'emb_solar']].rename(columns={'emb_wind': 'lk_emb_wind_slot', 'emb_solar': 'lk_emb_solar_slot'}).drop_duplicates('hh_idx')
        tg = tg.merge(lk_slot, on='hh_idx', how='left')
    else:
        for c in ['lk_emb_wind_daymean', 'lk_emb_solar_daymax', 'lk_emb_ren_daymean', 'lk_emb_wind_slot', 'lk_emb_solar_slot']:
            tg[c] = np.nan
    lknd = cp[(cp.TARGETDATE == known_until) & (cp.issue <= cutoff)] if len(cp) else cp
    if len(lknd):
        lknd = lknd[lknd.issue == lknd.issue.max()]
        tg['lk_nd_fc_mean'] = lknd.FORECASTDEMAND.mean()
        tg['lk_nd_fc_min'] = lknd.FORECASTDEMAND.min()
        tg['lk_nd_fc_max'] = lknd.FORECASTDEMAND.max()
    else:
        tg['lk_nd_fc_mean'] = np.nan; tg['lk_nd_fc_min'] = np.nan; tg['lk_nd_fc_max'] = np.nan
    tg['d_emb_wind_daymean'] = tg.emb_wind_daymean - tg.lk_emb_wind_daymean
    tg['d_emb_solar_daymax'] = tg.emb_solar_daymax - tg.lk_emb_solar_daymax
    tg['d_emb_wind_slot'] = tg.emb_wind - tg.lk_emb_wind_slot
    tg['d_emb_solar_slot'] = tg.emb_solar - tg.lk_emb_solar_slot
    tg['d_nd_fc_mean'] = tg.nd_fc_mean - tg.lk_nd_fc_mean
    tg['d_nd_fc_min'] = tg.nd_fc_min - tg.lk_nd_fc_min

    # ---------------- targets' event flags (NaN until prices resolve) ----------------
    tg['neg'] = (tg.agile < 0).astype(float); tg.loc[tg.agile.isna(), 'neg'] = np.nan
    tg['sub5'] = (tg.agile < 5).astype(float); tg.loc[tg.agile.isna(), 'sub5'] = np.nan
    tg['hi40'] = (tg.agile > 40).astype(float); tg.loc[tg.agile.isna(), 'hi40'] = np.nan
    tg['ss_sub10'] = (tg.ss < 10).astype(float); tg.loc[tg.ss.isna(), 'ss_sub10'] = np.nan

    if append:
        fp = Path(f"{D}/features_{origin}.parquet")
        if fp.exists():
            old = pd.read_parquet(fp)
            _refresh_targets(old, px_idx)
            _guard_degradation(old, tg, od, origin)
            keep = old[pd.to_datetime(old.origin_date).dt.date != od]
            tg = tg.reindex(columns=list(old.columns))
            allf = pd.concat([keep, tg], ignore_index=True)
        else:
            allf = tg
        allf.to_parquet(fp, index=False)
        print(f"features_{origin}.parquet: origin {od} written ({len(tg)} rows; file now {len(allf)} rows)", flush=True)
    return tg


def _refresh_targets(df, px_idx):
    """Backfill resolved price targets (agile/ss + event flags) into previously appended live
    rows — without this, refits would train on a frozen archive and the conformal calibration
    window would eventually empty out."""
    stale = (df.agile.isna() & (pd.to_datetime(df.target_utc) <= px_idx.index.max())).values
    if not stale.any():
        return
    t = pd.to_datetime(df.loc[stale, 'target_utc']).values
    df.loc[stale, 'agile'] = px_idx.agile.reindex(t).values
    df.loc[stale, 'ss'] = px_idx.ss.reindex(t).values
    res = df.agile.notna() & stale
    df.loc[stale, 'neg'] = np.where(res[stale], (df.loc[stale, 'agile'] < 0).astype(float), np.nan)
    df.loc[stale, 'sub5'] = np.where(res[stale], (df.loc[stale, 'agile'] < 5).astype(float), np.nan)
    df.loc[stale, 'hi40'] = np.where(res[stale], (df.loc[stale, 'agile'] > 40).astype(float), np.nan)
    ss_res = df.ss.notna() & stale
    df.loc[stale, 'ss_sub10'] = np.where(ss_res[stale], (df.loc[stale, 'ss'] < 10).astype(float), np.nan)
    print(f"backfilled targets into {int(res.sum())} of {int(stale.sum())} resolved live rows", flush=True)


_GUARD_COLS = ['emb_wind', 'nd_fc_hh', 'px_lag7', 'px_day_offpeak_mean', 'lk_nd_fc_mean']


def _guard_degradation(old, new, od, origin):
    """Refuse to overwrite an origin's existing rows with a materially less-populated block
    (e.g. a backfill run on a machine that lacks the demand history)."""
    prev = old[pd.to_datetime(old.origin_date).dt.date == od]
    if not len(prev):
        return
    for c in _GUARD_COLS:
        if c not in old.columns or c not in new.columns:
            continue
        was, now_ = prev[c].notna().mean(), new[c].notna().mean()
        if was >= 0.9 and now_ < was - 0.5:
            raise RuntimeError(
                f"refusing to overwrite features_{origin}.parquet origin {od}: column '{c}' would drop "
                f"from {was:.0%} to {now_:.0%} non-null (source data missing on this machine?). "
                f"Use append=False to inspect the rows without writing.")


if __name__ == '__main__':
    origin = sys.argv[1] if len(sys.argv) > 1 else '1635'
    date = next((a for a in sys.argv[2:] if not a.startswith('-')), None)
    rows = build_origin_rows(origin, date, fetch='--no-fetch' not in sys.argv)
    nn = rows.notna().mean().round(3)
    print(rows[['origin_date', 'horizon', 'target_local']].groupby('horizon').count())
    print('non-null share of key features:')
    print(nn[['emb_wind', 'windfor', 'nd_fc_hh', 'px_lag7', 'px_day_offpeak_mean', 'lk_emb_wind_slot', 'lk_nd_fc_mean', 'd_nd_fc_mean']].to_string())
