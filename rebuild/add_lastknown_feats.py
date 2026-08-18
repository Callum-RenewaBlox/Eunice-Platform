"""Add last-known-day (D+1 for 16:35 origin; D for 10:00 origin) driver features and deltas to features_{origin}.parquet"""
import pandas as pd, numpy as np, sys
from zoneinfo import ZoneInfo
from pathlib import Path
D = f"{Path(__file__).resolve().parent.as_posix()}/data"; LON = ZoneInfo('Europe/London')
ORIGIN = sys.argv[1] if len(sys.argv) > 1 else '1635'
tg = pd.read_parquet(f"{D}/features_{ORIGIN}.parquet")
emb = pd.read_parquet(f"{D}/asof_embedded_{ORIGIN}.parquet")
emb['origin_date'] = pd.to_datetime(emb.origin_date).dt.date
# local date of each embedded target
emb['tloc'] = pd.to_datetime(emb.target_start).dt.tz_localize('UTC').dt.tz_convert(LON)
emb['tdate'] = emb.tloc.dt.date
emb['hh_idx'] = emb.tloc.dt.hour * 2 + emb.tloc.dt.minute // 30
ku = dict(zip(tg.origin_date, tg.known_until))
emb['known_until'] = emb.origin_date.map(ku)
lk = emb[emb.tdate == emb.known_until]
lk_day = lk.groupby('origin_date').agg(lk_emb_wind_daymean=('emb_wind', 'mean'), lk_emb_solar_daymax=('emb_solar', 'max'), lk_emb_ren_daymean=('emb_wind', lambda s: np.nan)).reset_index()
lk_day['lk_emb_ren_daymean'] = lk.assign(r=lk.emb_wind + lk.emb_solar).groupby('origin_date').r.mean().values
lk_slot = lk[['origin_date', 'hh_idx', 'emb_wind', 'emb_solar']].rename(columns={'emb_wind': 'lk_emb_wind_slot', 'emb_solar': 'lk_emb_solar_slot'}).drop_duplicates(['origin_date', 'hh_idx'])
tg = tg.merge(lk_day, on='origin_date', how='left').merge(lk_slot, on=['origin_date', 'hh_idx'], how='left')
# demand for last known day: use the day-ahead cardinal file (DAYSAHEAD=1 published on D-... ) -> approximate via nd forecast for that date from any issue <= origin
cp = pd.concat([pd.read_csv(f"{D}/neso/Historic_Day_Ahead_Demand_Forecasts.csv"), pd.read_csv(f"{D}/neso/Historic_214_Day_Ahead_Demand_Forecasts.csv")], ignore_index=True)
cp['issue'] = pd.to_datetime(cp.FORECAST_TIMESTAMP, utc=True).dt.tz_localize(None)
cp['TARGETDATE'] = pd.to_datetime(cp.TARGETDATE).dt.date
cp = cp[cp.issue >= pd.Timestamp('2024-08-01')]
o = tg[['origin_date', 'origin_utc', 'known_until']].drop_duplicates()
m = o.merge(cp[['TARGETDATE', 'issue', 'FORECASTDEMAND']], left_on='known_until', right_on='TARGETDATE', how='left')
m = m[m.issue <= m.origin_utc]
last = m.groupby('origin_date').issue.transform('max'); m = m[m.issue == last]
lk_nd = m.groupby('origin_date').agg(lk_nd_fc_mean=('FORECASTDEMAND', 'mean'), lk_nd_fc_min=('FORECASTDEMAND', 'min'), lk_nd_fc_max=('FORECASTDEMAND', 'max')).reset_index()
tg = tg.merge(lk_nd, on='origin_date', how='left')
# deltas target-day minus last-known-day
tg['d_emb_wind_daymean'] = tg.emb_wind_daymean - tg.lk_emb_wind_daymean
tg['d_emb_solar_daymax'] = tg.emb_solar_daymax - tg.lk_emb_solar_daymax
tg['d_emb_wind_slot'] = tg.emb_wind - tg.lk_emb_wind_slot
tg['d_emb_solar_slot'] = tg.emb_solar - tg.lk_emb_solar_slot
tg['d_nd_fc_mean'] = tg.nd_fc_mean - tg.lk_nd_fc_mean
tg['d_nd_fc_min'] = tg.nd_fc_min - tg.lk_nd_fc_min
tg.to_parquet(f"{D}/features_{ORIGIN}.parquet", index=False)
print(tg[['lk_emb_wind_daymean', 'lk_emb_solar_daymax', 'lk_nd_fc_mean', 'd_emb_wind_daymean', 'd_emb_solar_slot', 'd_nd_fc_mean']].describe().T[['count', 'mean', 'min', 'max']])
