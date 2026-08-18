"""Assemble the modelling dataset: for each daily origin (16:35 London: D+1 prices known) and each target
half-hour in D+2..D+7 (and origin 10:00 for D+1..D+7), features available at origin + targets.
"""
import pandas as pd, numpy as np, holidays, sys, time
from zoneinfo import ZoneInfo
from pathlib import Path

D = f"{Path(__file__).resolve().parent.as_posix()}/data"
LON = ZoneInfo('Europe/London')
ORIGIN = sys.argv[1] if len(sys.argv) > 1 else '1635'   # '1635' or '1000'
H_MIN, H_MAX = (2, 7) if ORIGIN == '1635' else (1, 7)

t0 = time.time()
# ---------------- prices (targets + lags) ----------------
ag = pd.read_parquet(f"{D}/octopus_AGILE-24-10-01_K.parquet")[['valid_from', 'value_inc_vat']].rename(columns={'valid_from': 't', 'value_inc_vat': 'agile'})
ss = pd.read_parquet(f"{D}/octopus_AGILE-BUS-25-02-05_K.parquet")[['valid_from', 'value_inc_vat']].rename(columns={'valid_from': 't', 'value_inc_vat': 'ss'})
px = ag.merge(ss, on='t', how='left').sort_values('t').reset_index(drop=True)
px['t_utc'] = px.t.dt.tz_convert('UTC').dt.tz_localize(None)
px_idx = px.set_index('t_utc')

# ---------------- origins ----------------
hh, mm = (16, 35) if ORIGIN == '1635' else (10, 0)
# origins through yesterday: origin D needs D(+1)'s prices published, so today is never complete
days = pd.date_range('2024-09-16', pd.Timestamp.now(tz=LON).date() - pd.Timedelta(days=1), freq='D')
origins = pd.DataFrame({'origin_date': days.date})
origins['origin_utc'] = [pd.Timestamp(d.year, d.month, d.day, hh, mm, tz=LON).tz_convert('UTC').tz_localize(None) for d in days]
# last known price day: for 16:35 origin, D+1 fully published (Agile publishes ~16:00). For 10:00 origin, D is known (published D-1 16:00).
origins['known_until_local_date'] = [d + pd.Timedelta(days=1 if ORIGIN == '1635' else 0) for d in days]

# ---------------- target grid ----------------
rows = []
for _, o in origins.iterrows():
    for h in range(H_MIN, H_MAX + 1):
        tgt_day = pd.Timestamp(o.origin_date) + pd.Timedelta(days=h)
        start = pd.Timestamp(tgt_day.year, tgt_day.month, tgt_day.day, 0, 0, tz=LON)
        slots = pd.date_range(start, start + pd.Timedelta(hours=23, minutes=30), freq='30min')
        rows.append(pd.DataFrame({'origin_date': o.origin_date, 'origin_utc': o.origin_utc, 'horizon': h,
                                  'target_local': slots}))
tg = pd.concat(rows, ignore_index=True)
tg['target_utc'] = tg.target_local.dt.tz_convert('UTC').dt.tz_localize(None)
print('grid rows', len(tg), 'elapsed', round(time.time() - t0), flush=True)

# targets
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
emb = pd.read_parquet(f"{D}/asof_embedded_{ORIGIN}.parquet")
emb['origin_date'] = pd.to_datetime(emb.origin_date).dt.date
emb = emb.rename(columns={'target_start': 'target_utc', 'issue': 'emb_issue'})
tg = tg.merge(emb[['origin_date', 'target_utc', 'emb_wind', 'emb_solar', 'wind_cap', 'solar_cap', 'emb_issue']], on=['origin_date', 'target_utc'], how='left')
tg['emb_wind_lf'] = tg.emb_wind / tg.wind_cap
tg['emb_solar_lf'] = tg.emb_solar / tg.solar_cap
# daily aggregates of the target day (as forecast)
g = tg.groupby(['origin_date', 'horizon'])
tg['emb_solar_daymax'] = g.emb_solar.transform('max')
tg['emb_wind_daymean'] = g.emb_wind.transform('mean')
tg['emb_wind_daymin'] = g.emb_wind.transform('min')
tg['emb_ren_daymean'] = (tg.emb_wind + tg.emb_solar).groupby([tg.origin_date, tg.horizon]).transform('mean')
print('embedded merged; missing share %.3f' % tg.emb_wind.isna().mean(), 'elapsed', round(time.time() - t0), flush=True)

# ---------------- WINDFOR (transmission wind fcst, Elexon) as-of ----------------
wf = pd.read_parquet(f"{D}/elexon/WINDFOR.parquet")
wf['publishTime'] = pd.to_datetime(wf.publishTime, utc=True).dt.tz_localize(None)
wf['startTime'] = pd.to_datetime(wf.startTime, utc=True).dt.tz_localize(None)
wf = wf.sort_values(['publishTime', 'startTime'])
# for each origin: latest publish <= origin
pubs = np.sort(wf.publishTime.unique())
sel = []
for _, o in origins.iterrows():
    i = np.searchsorted(pubs, np.datetime64(o.origin_utc), side='right') - 1
    if i >= 0:
        sel.append((o.origin_date, pubs[i]))
sel = pd.DataFrame(sel, columns=['origin_date', 'publishTime'])
wfa = sel.merge(wf, on='publishTime')
# interpolate hourly -> half-hourly per origin
parts = []
for od, grp in wfa.groupby('origin_date'):
    s = grp.set_index('startTime').generation.sort_index()
    s = s[~s.index.duplicated()]
    idx = pd.date_range(s.index.min(), s.index.max(), freq='30min')
    s2 = s.reindex(idx).interpolate(limit=2)
    parts.append(pd.DataFrame({'origin_date': od, 'target_utc': s2.index, 'windfor': s2.values, 'windfor_pub': grp.publishTime.iloc[0]}))
wfi = pd.concat(parts, ignore_index=True)
tg = tg.merge(wfi, on=['origin_date', 'target_utc'], how='left')
print('windfor merged; available share by horizon:', tg.groupby('horizon').windfor.apply(lambda s: round(1 - s.isna().mean(), 2)).to_dict(), flush=True)

# ---------------- NESO demand cardinal points as-of ----------------
cp = pd.concat([pd.read_csv(f"{D}/neso/Historic_214_Day_Ahead_Demand_Forecasts.csv"),
                pd.read_csv(f"{D}/neso/Historic_Day_Ahead_Demand_Forecasts.csv"),
                pd.read_csv(f"{D}/neso/Historic_7_Day_Ahead_Demand_Forecasts.csv")], ignore_index=True)
cp['issue'] = pd.to_datetime(cp.FORECAST_TIMESTAMP, utc=True).dt.tz_localize(None)
cp['TARGETDATE'] = pd.to_datetime(cp.TARGETDATE).dt.date
cp = cp[cp.issue >= pd.Timestamp('2024-08-01')]
cp['cp_min'] = (cp.CP_ST_TIME // 100) * 60 + cp.CP_ST_TIME % 100
cp['cp_max'] = (cp.CP_END_TIME // 100) * 60 + cp.CP_END_TIME % 100
cp['cp_mid'] = (cp.cp_min + cp.cp_max) / 2.0
# choose latest issue <= origin for each (origin, target date)
tdays = tg[['origin_date', 'origin_utc', 'horizon']].drop_duplicates()
tdays['TARGETDATE'] = [pd.Timestamp(d) + pd.Timedelta(days=int(h)) for d, h in zip(tdays.origin_date, tdays.horizon)]
tdays['TARGETDATE'] = tdays.TARGETDATE.dt.date
m = tdays.merge(cp[['TARGETDATE', 'issue', 'DAYSAHEAD', 'FORECASTDEMAND', 'CARDINALPOINT', 'cp_mid']], on='TARGETDATE', how='left')
m = m[m.issue <= m.origin_utc]
last_issue = m.groupby(['origin_date', 'horizon']).issue.transform('max')
m = m[m.issue == last_issue]
# daily aggregates
agg = m.groupby(['origin_date', 'horizon']).agg(nd_fc_min=('FORECASTDEMAND', 'min'), nd_fc_max=('FORECASTDEMAND', 'max'), nd_fc_mean=('FORECASTDEMAND', 'mean'), nd_fc_daysahead=('DAYSAHEAD', 'first'), nd_issue=('issue', 'first')).reset_index()
tg = tg.merge(agg, on=['origin_date', 'horizon'], how='left')
# interpolate cardinal points to the target local minute-of-day
tg['min_of_day'] = tg.target_local.dt.hour * 60 + tg.target_local.dt.minute + 15  # slot midpoint
interp = []
for (od, h), grp in m.groupby(['origin_date', 'horizon']):
    grp = grp.sort_values('cp_mid').drop_duplicates('cp_mid')
    x = grp.cp_mid.values; y = grp.FORECASTDEMAND.values.astype(float)
    x = np.r_[x[-1] - 1440, x, x[0] + 1440]; y = np.r_[y[-1], y, y[0]]  # wrap-around
    mod = np.arange(15, 1440, 30)
    interp.append(pd.DataFrame({'origin_date': od, 'horizon': h, 'min_of_day': mod, 'nd_fc_hh': np.interp(mod, x, y)}))
interp = pd.concat(interp, ignore_index=True)
tg = tg.merge(interp, on=['origin_date', 'horizon', 'min_of_day'], how='left')
print('demand cp merged; missing share %.3f' % tg.nd_fc_hh.isna().mean(), 'elapsed', round(time.time() - t0), flush=True)

# residual-demand proxies (MW)
tg['resid_emb'] = tg.nd_fc_hh - tg.emb_solar * 0  # ND already nets embedded; keep separate features
tg['ren_share_proxy'] = (tg.emb_wind + tg.emb_solar) / (tg.nd_fc_hh + tg.emb_wind + tg.emb_solar)
tg['windfor_share'] = tg.windfor / tg.nd_fc_hh

# ---------------- price lags (known at origin) ----------------
# last known local day K = known_until_local_date; features relative to target: same slot 7 days before target
# (always known when horizon<=7 and K>=D+1 for 16:35; for 10:00 origin with h=7 the slot D is known; h<=7 => target-7 <= D)
tg['known_until'] = pd.to_datetime(tg.origin_date.map(dict(zip(origins.origin_date, origins.known_until_local_date)))).dt.date
lag7_utc = (tg.target_local - pd.Timedelta(days=7)).dt.tz_convert('UTC').dt.tz_localize(None)
tg['px_lag7'] = px_idx.agile.reindex(lag7_utc.values).values
tg['ss_lag7'] = px_idx.ss.reindex(lag7_utc.values).values
# same slot on the last known day
kd = pd.to_datetime(tg.known_until)
last_known_slot = pd.to_datetime(kd.dt.strftime('%Y-%m-%d') + ' ' + tg.target_local.dt.strftime('%H:%M')).dt.tz_localize(LON, ambiguous='NaT', nonexistent='shift_forward')
lks_utc = last_known_slot.dt.tz_convert('UTC').dt.tz_localize(None)
tg['px_lastknown_sameslot'] = px_idx.agile.reindex(lks_utc.values).values
tg['ss_lastknown_sameslot'] = px_idx.ss.reindex(lks_utc.values).values
# daily stats of last known day and rolling windows ending at last known day (computed on local dates)
px['local_date'] = px.t.dt.tz_convert(LON).dt.date
dstats = px.groupby('local_date').agile.agg(px_day_mean='mean', px_day_min='min', px_day_max='max', px_day_neg=lambda s: (s < 0).sum(), px_day_sub5=lambda s: (s < 5).sum()).reset_index()
dstats['px_roll7_mean'] = dstats.px_day_mean.rolling(7).mean()
dstats['px_roll7_min'] = dstats.px_day_min.rolling(7).min()
dstats['px_roll7_neg'] = dstats.px_day_neg.rolling(7).sum()
dstats['px_roll7_sub5'] = dstats.px_day_sub5.rolling(7).sum()
dstats['px_roll30_mean'] = dstats.px_day_mean.rolling(30).mean()
dstats['px_roll30_neg'] = dstats.px_day_neg.rolling(30).sum()
# off-peak level (excl 16-19) of last known day: proxy for wholesale level
px['is_peak'] = ((px.t.dt.tz_convert(LON).dt.hour >= 16) & (px.t.dt.tz_convert(LON).dt.hour < 19))
op = px[~px.is_peak].groupby('local_date').agile.mean().rename('px_day_offpeak_mean').reset_index()
dstats = dstats.merge(op, on='local_date', how='left')
dstats['known_until'] = dstats.local_date
tg = tg.merge(dstats.drop(columns=['local_date']), on='known_until', how='left')
# hour-of-day mean of last 7 known days for the target slot (climatology-lite)
px['hh_idx'] = px.t.dt.tz_convert(LON).dt.hour * 2 + px.t.dt.tz_convert(LON).dt.minute // 30
# build per (date, hh) then rolling over 7 days
pv = px.pivot_table(index='local_date', columns='hh_idx', values='agile')
pv7 = pv.rolling(7, min_periods=5).mean()
pv7s = pv7.stack().rename('px_slot_roll7').reset_index().rename(columns={'local_date': 'known_until'})
tg = tg.merge(pv7s, on=['known_until', 'hh_idx'], how='left')
print('lags merged', 'elapsed', round(time.time() - t0), flush=True)

# ---------------- final ----------------
tg['neg'] = (tg.agile < 0).astype(float); tg.loc[tg.agile.isna(), 'neg'] = np.nan
tg['sub5'] = (tg.agile < 5).astype(float); tg.loc[tg.agile.isna(), 'sub5'] = np.nan
tg['hi40'] = (tg.agile > 40).astype(float); tg.loc[tg.agile.isna(), 'hi40'] = np.nan
tg['ss_sub10'] = (tg.ss < 10).astype(float); tg.loc[tg.ss.isna(), 'ss_sub10'] = np.nan
out = f"{D}/features_{ORIGIN}.parquet"
tg.to_parquet(out, index=False)
print('saved', out, tg.shape, 'target missing share %.3f' % tg.agile.isna().mean(), 'elapsed', round(time.time() - t0), flush=True)
print(tg.describe().T[['count', 'mean', 'min', 'max']].to_string())
