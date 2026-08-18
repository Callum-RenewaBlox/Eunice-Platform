"""Build as-of (latest issue <= origin) NESO embedded wind/solar forecasts for each daily origin, using DuckDB.
Origins: every day D, at two origin times (London local): 16:35 (Eunice refresh, D+1 prices known) and 10:00 (before D+1 publication).
Output: data/asof_embedded_{origin}.parquet with rows (origin_date, target_start_utc, issue_utc, emb_wind, emb_solar, wind_cap, solar_cap)
"""
import duckdb, pandas as pd, numpy as np, sys, time, os
from zoneinfo import ZoneInfo
from pathlib import Path

D = f"{Path(__file__).resolve().parent.as_posix()}/data"
con = duckdb.connect()
con.execute("SET memory_limit='4GB'; SET threads=2;")

files = [f"{D}/neso/Embedded_Solar_and_Wind_Forecast_Archive_2024.csv",
         f"{D}/neso/Embedded_Solar_and_Wind_Forecast_Archive_2025.csv",
         f"{D}/neso/Embedded_Solar_and_Wind_Forecast_Archive_2026_Jan_Jun.csv",
         f"{D}/neso/Embedded_Solar_and_Wind_Forecast_Archive_2026_Jun__Dec.csv"]

t0 = time.time()
# Read all with all_varchar to cope with mixed formats, then normalise
parts = []
for f in files:
    parts.append(f"SELECT DATE_GMT, TIME_GMT, SETTLEMENT_DATE, SETTLEMENT_PERIOD, EMBEDDED_WIND_FORECAST, EMBEDDED_WIND_CAPACITY, EMBEDDED_SOLAR_FORECAST, EMBEDDED_SOLAR_CAPACITY, Forecast_Datetime FROM read_csv('{f}', all_varchar=true, header=true)")
union = " UNION ALL ".join(parts)
con.execute(f"""
CREATE TABLE emb AS
SELECT
  (strptime(substr(replace(DATE_GMT,'Z',''),1,10), '%Y-%m-%d') + INTERVAL (CASE WHEN length(TIME_GMT)=5 THEN CAST(substr(TIME_GMT,1,2) AS INT)*60 + CAST(substr(TIME_GMT,4,2) AS INT) ELSE CAST(substr(TIME_GMT,1,2) AS INT)*60 + CAST(substr(TIME_GMT,4,2) AS INT) END) MINUTE - INTERVAL 30 MINUTE) AS target_start,
  strptime(substr(replace(Forecast_Datetime,'Z',''),1,19), '%Y-%m-%dT%H:%M:%S') AS issue,
  TRY_CAST(EMBEDDED_WIND_FORECAST AS DOUBLE) AS emb_wind,
  TRY_CAST(EMBEDDED_WIND_CAPACITY AS DOUBLE) AS wind_cap,
  TRY_CAST(EMBEDDED_SOLAR_FORECAST AS DOUBLE) AS emb_solar,
  TRY_CAST(EMBEDDED_SOLAR_CAPACITY AS DOUBLE) AS solar_cap
FROM ({union})
""")
n = con.execute("SELECT COUNT(*), MIN(issue), MAX(issue), MIN(target_start), MAX(target_start) FROM emb").fetchall()
print("emb rows", n, "elapsed", round(time.time() - t0), flush=True)

# sanity: check a summer row mapping
print(con.execute("SELECT * FROM emb WHERE issue = (SELECT MIN(issue) FROM emb WHERE issue >= TIMESTAMP '2025-06-15 12:00:00') ORDER BY target_start LIMIT 3").fetchdf())

# Build origins (through today; issues only reach the archives' publication edge)
lon = ZoneInfo('Europe/London')
days = pd.date_range('2024-09-10', pd.Timestamp.now(tz=lon).date(), freq='D')
for label, (hh, mm) in {'1635': (16, 35), '1000': (10, 0)}.items():
    org = pd.DataFrame({'origin_date': days.date})
    org['origin_utc'] = [pd.Timestamp(d.year, d.month, d.day, hh, mm, tz=lon).tz_convert('UTC').tz_localize(None) for d in days]
    con.register('org', org)
    t1 = time.time()
    df = con.execute("""
    WITH cand AS (
      SELECT o.origin_date, o.origin_utc, e.issue, e.target_start, e.emb_wind, e.emb_solar, e.wind_cap, e.solar_cap
      FROM org o JOIN emb e
        ON e.issue <= o.origin_utc AND e.issue > o.origin_utc - INTERVAL 30 HOUR
       AND e.target_start >= o.origin_utc - INTERVAL 1 DAY AND e.target_start < o.origin_utc + INTERVAL 9 DAY
    )
    SELECT * EXCLUDE (rn) FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY origin_date, target_start ORDER BY issue DESC) AS rn FROM cand
    ) WHERE rn = 1
    ORDER BY origin_date, target_start
    """).fetchdf()
    con.unregister('org')
    out = f"{D}/asof_embedded_{label}.parquet"
    df.to_parquet(out, index=False)
    lag = (df.origin_utc - df.issue).dt.total_seconds() / 3600
    print(label, "rows", len(df), "origins", df.origin_date.nunique(), "issue lag hours: median %.2f p90 %.2f max %.1f" % (lag.median(), lag.quantile(.9), lag.max()), "elapsed", round(time.time() - t1), flush=True)
