import numpy as np
import requests

from config import (
    GB_SITES,
    LATITUDE, LONGITUDE,
    METOFFICE_API_KEY, METOFFICE_BASE,
    OPEN_METEO_ARCHIVE, OPEN_METEO_FORECAST,
)


def _multisite_get(url, sites, hourly, **extra):
    """Single Open-Meteo call covering all sites. Returns a list of per-site response dicts."""
    lats = ",".join(f"{s['lat']:.4f}" for s in sites)
    lons = ",".join(f"{s['lon']:.4f}" for s in sites)
    params = {
        "latitude": lats,
        "longitude": lons,
        "hourly": hourly,
        "timezone": "UTC",
        **extra,
    }
    r = requests.get(url, params=params, timeout=180)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else [data]


def _stack(multi, var):
    return np.array([d["hourly"][var] for d in multi], dtype=float)


def _norm(weights):
    w = np.array(weights, dtype=float)
    s = w.sum()
    return w / s if s > 0 else w


def fetch_historical(start_date, end_date):
    """GB-aggregated historical weather. Capacity-weighted means across GB_SITES."""
    multi = _multisite_get(
        OPEN_METEO_ARCHIVE, GB_SITES,
        hourly="temperature_2m,wind_speed_10m,cloud_cover,shortwave_radiation,precipitation",
        start_date=start_date,
        end_date=end_date,
    )
    times = multi[0]["hourly"]["time"]
    temps   = np.nan_to_num(_stack(multi, "temperature_2m"))
    winds   = np.nan_to_num(_stack(multi, "wind_speed_10m"))
    clouds  = np.nan_to_num(_stack(multi, "cloud_cover"))
    solars  = np.nan_to_num(_stack(multi, "shortwave_radiation"))
    precips = np.nan_to_num(_stack(multi, "precipitation"))

    w_demand = _norm([s["w_demand"] for s in GB_SITES])
    w_wind   = _norm([s["w_wind"]   for s in GB_SITES])
    w_solar  = _norm([s["w_solar"]  for s in GB_SITES])

    return list(zip(
        times,
        np.dot(w_demand, temps),
        np.dot(w_wind, winds),
        np.dot(w_demand, clouds),
        np.dot(w_solar, solars),
        np.dot(w_demand, precips),
    ))


def fetch_forecast_open_meteo():
    """GB-aggregated 7-day forecast. Capacity-weighted means across GB_SITES."""
    multi = _multisite_get(
        OPEN_METEO_FORECAST, GB_SITES,
        hourly="temperature_2m,wind_speed_10m,cloud_cover,apparent_temperature,shortwave_radiation,precipitation",
        forecast_days=7,
    )
    times = multi[0]["hourly"]["time"]
    temps   = np.nan_to_num(_stack(multi, "temperature_2m"))
    winds   = np.nan_to_num(_stack(multi, "wind_speed_10m"))
    clouds  = np.nan_to_num(_stack(multi, "cloud_cover"))
    feels   = np.nan_to_num(_stack(multi, "apparent_temperature"))
    solars  = np.nan_to_num(_stack(multi, "shortwave_radiation"))
    precips = np.nan_to_num(_stack(multi, "precipitation"))

    w_demand = _norm([s["w_demand"] for s in GB_SITES])
    w_wind   = _norm([s["w_wind"]   for s in GB_SITES])
    w_solar  = _norm([s["w_solar"]  for s in GB_SITES])

    return list(zip(
        times,
        np.dot(w_demand, temps),
        np.dot(w_wind, winds),
        np.dot(w_demand, clouds),
        np.dot(w_demand, feels),
        np.dot(w_solar, solars),
        np.dot(w_demand, precips),
    ))


def fetch_forecast_metoffice():
    """Local Swansea Met Office forecast — kept as a sanity-check feed; not yet load-bearing."""
    if not METOFFICE_API_KEY:
        return []
    r = requests.get(
        f"{METOFFICE_BASE}/point/hourly",
        params={"latitude": LATITUDE, "longitude": LONGITUDE, "excludeParameterMetadata": "true"},
        headers={"apikey": METOFFICE_API_KEY, "accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    series = r.json()["features"][0]["properties"]["timeSeries"]
    out = []
    for p in series:
        wind_ms = p.get("windSpeed10m") or 0
        out.append((
            p["time"],
            p.get("screenTemperature"),
            wind_ms * 3.6,
            p.get("totalCloudCover"),
            p.get("feelsLikeTemperature"),
        ))
    return out
