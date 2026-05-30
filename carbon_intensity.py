"""NESO Carbon Intensity API (api.carbonintensity.org.uk).

No authentication. Half-hourly GB-wide carbon intensity (gCO2/kWh):
  - Historical: both `intensity.forecast` (what was published as forecast at the time)
    and `intensity.actual` (settled value)
  - 48h ahead: forecast only (no actuals yet)

We use `intensity.forecast` consistently for both training and prediction so the model
sees comparable feature distributions. Beyond 48h we impute by hour-of-day median.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

CI_BASE = "https://api.carbonintensity.org.uk"


def _row(r):
    intensity = r.get("intensity") or {}
    return {
        "timestamp": pd.to_datetime(r["from"], utc=True),
        "carbon_intensity_forecast": intensity.get("forecast"),
        "carbon_intensity_actual": intensity.get("actual"),
    }


def fetch_intensity_history(start_dt, end_dt, chunk_days=14):
    """Half-hourly historical intensity. Returns DataFrame."""
    rows = []
    s = start_dt
    while s < end_dt:
        e = min(s + timedelta(days=chunk_days), end_dt)
        r = requests.get(
            f"{CI_BASE}/intensity/{s.strftime('%Y-%m-%dT%H:%MZ')}/{e.strftime('%Y-%m-%dT%H:%MZ')}",
            timeout=60,
        )
        r.raise_for_status()
        rows.extend(r.json().get("data", []))
        s = e
    if not rows:
        return pd.DataFrame(columns=["timestamp", "carbon_intensity_forecast", "carbon_intensity_actual"])
    df = pd.DataFrame([_row(r) for r in rows])
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def fetch_intensity_forecast_48h():
    """Next 48h half-hourly intensity forecast. Returns DataFrame."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    r = requests.get(
        f"{CI_BASE}/intensity/{now.strftime('%Y-%m-%dT%H:%MZ')}/fw48h",
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json().get("data", [])
    if not rows:
        return pd.DataFrame(columns=["timestamp", "carbon_intensity_forecast"])
    df = pd.DataFrame([{
        "timestamp": pd.to_datetime(r["from"], utc=True),
        "carbon_intensity_forecast": (r.get("intensity") or {}).get("forecast"),
    } for r in rows])
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
