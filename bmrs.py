"""Elexon BMRS new API (data.elexon.co.uk/bmrs/api/v1) — no authentication required.

Endpoints used:
  - WINDFOR — wind generation forecast (~2-3 day horizon, hourly granularity, latest only)
  - NDF     — National Demand Forecast (~2 day horizon, half-hourly, latest only)
  - FUELHH  — Half-hourly fuel-mix outturn (historical actuals — used as training proxy)

Forecast endpoints (WINDFOR/NDF) only retain the latest publication, so we use them at
predict time. For training data, we use FUELHH actuals as a proxy: wind from the WIND
fuel type, demand from the sum across all fuels (= total supply ≈ demand).
"""
from datetime import timedelta

import pandas as pd
import requests

from config import ELEXON_BASE


def _dataset(name, params):
    r = requests.get(
        f"{ELEXON_BASE}/datasets/{name}",
        params={"format": "json", **params},
        timeout=180,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def _latest_per_slot(rows, value_col):
    if not rows:
        return pd.DataFrame(columns=["timestamp", value_col])
    df = pd.DataFrame(rows)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    df = df.sort_values("publishTime").drop_duplicates("startTime", keep="last")
    src = "generation" if "generation" in df.columns else "demand"
    return df.rename(columns={"startTime": "timestamp", src: value_col})[
        ["timestamp", value_col]
    ].sort_values("timestamp").reset_index(drop=True)


def fetch_wind_forecast(from_dt, to_dt):
    """Latest WINDFOR (wind generation forecast). ~2-3 day horizon."""
    rows = _dataset("WINDFOR", {
        "from": from_dt.strftime("%Y-%m-%dT%H:%M"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M"),
    })
    return _latest_per_slot(rows, "wind_generation_mw")


def fetch_demand_forecast(from_dt, to_dt):
    """Latest NDF (demand forecast). ~2 day horizon."""
    rows = _dataset("NDF", {
        "from": from_dt.strftime("%Y-%m-%dT%H:%M"),
        "to": to_dt.strftime("%Y-%m-%dT%H:%M"),
    })
    return _latest_per_slot(rows, "demand_mw")


def fetch_market_index_history(start_date, end_date, chunk_days=7):
    """Pull MID (Market Index Data) — GB half-hourly day-ahead reference price (£/MWh).

    Two providers per slot: APXMIDP (EPEX SPOT GB) and N2EXMIDP (Nord Pool GB). N2EX
    publishes 0 throughout — appears retired/superseded — so we use APXMIDP only.

    Returns DataFrame (timestamp, wholesale_price_gbp_per_mwh).
    """
    rows = []
    s = start_date
    while s < end_date:
        e = min(s + timedelta(days=chunk_days), end_date)
        rows.extend(_dataset("MID", {
            "from": s.isoformat(),
            "to": e.isoformat(),
        }))
        s = e + timedelta(days=1)
    if not rows:
        return pd.DataFrame(columns=["timestamp", "wholesale_price_gbp_per_mwh"])
    df = pd.DataFrame(rows)
    df = df[df["dataProvider"] == "APXMIDP"]
    df["timestamp"] = pd.to_datetime(df["startTime"], utc=True)
    df = df.rename(columns={"price": "wholesale_price_gbp_per_mwh"})[
        ["timestamp", "wholesale_price_gbp_per_mwh"]
    ].drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return df


def fetch_fuelhh_history(start_date, end_date, chunk_days=7):
    """Pull FUELHH historical fuel-mix outturn and aggregate to wind + demand per half-hour.

    Returns DataFrame (timestamp, wind_generation_mw, demand_mw).
    Chunks the request to keep responses manageable (~30 days at a time).
    """
    rows = []
    s = start_date
    while s < end_date:
        e = min(s + timedelta(days=chunk_days), end_date)
        rows.extend(_dataset("FUELHH", {
            "settlementDateFrom": s.isoformat(),
            "settlementDateTo": e.isoformat(),
        }))
        s = e + timedelta(days=1)
    if not rows:
        return pd.DataFrame(columns=["timestamp", "wind_generation_mw", "demand_mw"])

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["startTime"], utc=True)
    pivot = df.pivot_table(
        index="timestamp",
        columns="fuelType",
        values="generation",
        aggfunc="sum",
    ).fillna(0)
    out = pd.DataFrame({"timestamp": pivot.index})
    out["wind_generation_mw"] = pivot["WIND"].values if "WIND" in pivot.columns else 0.0
    out["demand_mw"] = pivot.sum(axis=1).values
    return out.sort_values("timestamp").reset_index(drop=True)
