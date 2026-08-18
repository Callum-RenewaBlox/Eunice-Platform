"""Archive Open-Meteo Previous-Runs NWP forecasts for the GB_SITES hubs (phase-2 weather).

BLOCKED ON A KEY: the Previous Runs API needs an Open-Meteo commercial subscription
(OPENMETEO_API_KEY env / Actions secret). Until it is set this script is a clean no-op.
Once live it stores, per hub and per lead (previous_day1..7): 100 m wind speed, GHI and
2 m temperature into rebuild/data/live/nwp_prevruns.parquet — the horizon-honest NWP
archive needed before those features can enter training (they must accumulate history
before the walk-forward gate can evaluate them). UNTESTED against the live API until a
key exists; verify the first run's output manually.

Usage: python fetch_nwp_prevruns.py
"""
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

_R = Path(__file__).resolve().parent
sys.path.insert(1, str(_R.parent))
from config import GB_SITES  # noqa: E402

KEY = os.environ.get("OPENMETEO_API_KEY", "").strip()
BASE = "https://customer-previous-runs-api.open-meteo.com/v1/forecast"
VARS = ["wind_speed_100m", "shortwave_radiation", "temperature_2m"]
LEADS = range(1, 8)
OUT = _R / "data" / "live" / "nwp_prevruns.parquet"


def main():
    if not KEY:
        print("fetch_nwp_prevruns: no OPENMETEO_API_KEY — skipped (needs the commercial plan)", flush=True)
        return
    hourly = ",".join(f"{v}_previous_day{d}" for v in VARS for d in LEADS) + "," + ",".join(VARS)
    frames = []
    for site in GB_SITES:
        r = requests.get(BASE, params={"latitude": site["lat"], "longitude": site["lon"],
                                       "hourly": hourly, "forecast_days": 2, "apikey": KEY}, timeout=90)
        r.raise_for_status()
        h = r.json()["hourly"]
        df = pd.DataFrame(h)
        df["time"] = pd.to_datetime(df.pop("time"))
        df["site"] = site["name"]
        df["captured_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")
        frames.append(df)
        time.sleep(1)
    new = pd.concat(frames, ignore_index=True)
    if OUT.exists():
        new = pd.concat([pd.read_parquet(OUT), new], ignore_index=True)
    new = new.drop_duplicates(["site", "time", "captured_at"], keep="last")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new.to_parquet(OUT, index=False)
    print(f"nwp_prevruns: store now {len(new)} rows", flush=True)


if __name__ == "__main__":
    main()
