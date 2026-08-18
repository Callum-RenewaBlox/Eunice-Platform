"""Archive every forecast issue we can see into the forecast_vintages table.

Captured daily by the Action (both the 09:45 and 16:35 runs) — this quietly builds the
horizon-honest training archive that NESO / Met Office do not provide:
  - NESO embedded wind/solar (live CSV issues, via rebuild/data/live/embedded_issues.parquet)
  - NESO demand cardinal points (1-day / 2-14 day / 7-day, via live/demand_cp.parquet;
    target_time is the cardinal-point window start on the target date, local wall clock)
  - NESO 14-day national wind forecast (current CSV; each row carries its ForecastDateTime issue)
  - Elexon WINDFOR (via live/windfor.parquet), NDF (half-hourly), NDFD / TSDFD (daily)
  - Met Office site-specific hourly + three-hourly for the GB_SITES hubs
    (2 calls per hub per run — 20 of the 360 daily free-plan calls at one run/day)

Each source is isolated: a failing fetch logs a warning and never blocks the others or the job.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests

_ROOT = Path(__file__).resolve().parent
import db  # noqa: E402
from config import GB_SITES, METOFFICE_API_KEY, METOFFICE_BASE  # noqa: E402

LIVE = _ROOT / "rebuild" / "data" / "live"
NESO_API = "https://api.neso.energy/api/3/action/package_show"
ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"

_S = requests.Session()
_S.headers["User-Agent"] = "eunice-vintages/1.0"


def _z(ts):
    return pd.to_datetime(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url, **kw):
    for a in range(4):
        try:
            r = _S.get(url, timeout=90, **kw)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(3 * (a + 1))
    raise RuntimeError(f"GET failed after retries: {url}")


def _since(source, fallback_days=3):
    """Only re-insert issues near/after the stored high-water mark (OR IGNORE dedupes the rest)."""
    last = db.latest_vintage_issue(source)
    if last:
        return pd.to_datetime(last) - pd.Timedelta(hours=1)
    return pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.Timedelta(days=fallback_days)


def capture_embedded():
    p = LIVE / "embedded_issues.parquet"
    if not p.exists():
        return 0
    e = pd.read_parquet(p)
    e = e[e.issue >= _since("neso_embedded")]
    rows = []
    for var in ("emb_wind", "emb_solar", "wind_cap", "solar_cap"):
        rows += [("neso_embedded", _z(i), _z(t), var, float(v))
                 for i, t, v in zip(e.issue, e.target_start, e[var]) if pd.notna(v)]
    db.insert_vintages(rows)
    return len(rows)


def capture_demand_cp():
    p = LIVE / "demand_cp.parquet"
    if not p.exists():
        return 0
    d = pd.read_parquet(p)
    d = d[d.issue >= _since("neso_demand_cp")]
    tgt = pd.to_datetime(d.TARGETDATE) + pd.to_timedelta((d.CP_ST_TIME // 100) * 60 + d.CP_ST_TIME % 100, unit="m")
    rows = [("neso_demand_cp", _z(i), _z(t), f"nd_cp_{cp}", float(v))
            for i, t, cp, v in zip(d.issue, tgt, d.CARDINALPOINT, d.FORECASTDEMAND) if pd.notna(v)]
    db.insert_vintages(rows)
    return len(rows)


def capture_wind14d():
    j = _get(NESO_API, params={"id": "14-days-ahead-wind-forecasts"}).json()["result"]
    url = next(r["url"] for r in j["resources"] if r["name"] == "14 Days Ahead Wind Forecast")
    w = pd.read_csv(pd.io.common.BytesIO(_get(url).content), encoding="utf-8-sig")
    w["issue"] = pd.to_datetime(w.ForecastDateTime, utc=True).dt.tz_localize(None)
    w["target"] = pd.to_datetime(w.Datetime, utc=True).dt.tz_localize(None)
    w = w[w.issue >= _since("neso_wind14d")]
    rows = []
    for var, col in (("wind_fc", "Wind_Forecast"), ("wind_cap", "Capacity")):
        rows += [("neso_wind14d", _z(i), _z(t), var, float(v))
                 for i, t, v in zip(w.issue, w.target, w[col]) if pd.notna(v)]
    db.insert_vintages(rows)
    return len(rows)


def capture_windfor():
    p = LIVE / "windfor.parquet"
    if not p.exists():
        return 0
    w = pd.read_parquet(p)
    w = w[w.publishTime >= _since("elexon_windfor")]
    rows = [("elexon_windfor", _z(i), _z(t), "windfor_mw", float(v))
            for i, t, v in zip(w.publishTime, w.startTime, w.generation) if pd.notna(v)]
    db.insert_vintages(rows)
    return len(rows)


def capture_elexon_demand():
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    total = 0
    for ds, var, tcol in (("NDF", "ndf_mw", "startTime"), ("NDFD", "ndfd_mw", "forecastDate"), ("TSDFD", "tsdfd_mw", "forecastDate")):
        src = f"elexon_{ds.lower()}"
        start = max(_since(src), now - pd.Timedelta(days=3))
        t = start
        while t < now:   # these datasets reject wide publish windows — fetch in daily chunks
            t2 = min(t + pd.Timedelta(days=1), now)
            r = _get(f"{ELEXON_BASE}/datasets/{ds}",
                     params={"publishDateTimeFrom": t.strftime("%Y-%m-%dT%H:%MZ"),
                             "publishDateTimeTo": t2.strftime("%Y-%m-%dT%H:%MZ"), "format": "json"})
            data = r.json().get("data", [])
            rows = [(src, _z(d["publishTime"]), _z(d[tcol]), var, float(d["demand"]))
                    for d in data if d.get("demand") is not None]
            db.insert_vintages(rows)
            total += len(rows)
            t = t2
    return total


MET_PARAMS = ("screenTemperature", "windSpeed10m", "windGustSpeed10m", "totalCloudCover",
              "globalIrradiance", "feelsLikeTemperature", "precipitationRate")


def capture_metoffice():
    if not METOFFICE_API_KEY:
        print("metoffice: no METOFFICE_API_KEY — skipped", flush=True)
        return 0
    total = 0
    for site in GB_SITES:
        slug = site["name"].lower().replace(" ", "_").replace("/", "-")
        for freq in ("hourly", "three-hourly"):
            r = _get(f"{METOFFICE_BASE}/point/{freq}",
                     params={"latitude": site["lat"], "longitude": site["lon"], "excludeParameterMetadata": "true"},
                     headers={"apikey": METOFFICE_API_KEY, "accept": "application/json"})
            props = r.json()["features"][0]["properties"]
            issue = props.get("modelRunDate") or pd.Timestamp.now(tz="UTC").isoformat()
            rows = []
            for p in props["timeSeries"]:
                for var in MET_PARAMS:
                    if p.get(var) is not None:
                        rows.append((f"metoffice_{freq}", _z(issue), _z(p["time"]), f"{var}@{slug}", float(p[var])))
            db.insert_vintages(rows)
            total += len(rows)
    return total


def main():
    db.init_db()
    sources = [("neso_embedded", capture_embedded), ("neso_demand_cp", capture_demand_cp),
               ("neso_wind14d", capture_wind14d), ("elexon_windfor", capture_windfor),
               ("elexon_demand", capture_elexon_demand), ("metoffice", capture_metoffice)]
    failures = 0
    for name, fn in sources:
        try:
            n = fn()
            print(f"vintages[{name}]: +{n} rows", flush=True)
        except Exception as e:
            failures += 1
            print(f"WARNING: vintage capture failed for {name}: {e}", flush=True)
    if failures == len(sources):
        sys.exit(1)   # everything failed — surface it


if __name__ == "__main__":
    main()
