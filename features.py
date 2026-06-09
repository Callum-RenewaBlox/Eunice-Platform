import holidays
import pandas as pd

from config import ALL_REGIONS
from db import conn

WEATHER_COLS = [
    "temperature_c",
    "wind_speed_kmh",
    "cloud_cover_pct",
    "shortwave_wm2",
    "precipitation_mm",
]
GRID_COLS = ["carbon_intensity_forecast", "demand_mw", "wind_generation_mw"]
# Pruned 2026-05-06 after ablation: dropped is_bank_holiday and lag_1w_price (the latter
# actively hurt val MAE by ~0.12p).
# 2026-05-07: added wholesale_price_lag_7d (BMRS MID, 7-day lag — always available
# since the lookup horizon is in the past) and region_id (label-encoded GSP region).
# 2026-06-07: RESTORED wind_generation_mw and added derived net_demand_mw (demand - wind).
# The 2026-05-06 ablation pruned wind because it didn't improve *median* MAE — but wind
# surplus is THE driver of negative pricing, which lives entirely in the lower tail the
# median ignores. net_demand_mw gives the tree an explicit renewable-surplus axis.
FEATURE_COLS = [
    "hour",
    "minute",
    "dow",
    "month",
    "is_weekend",
    *WEATHER_COLS,
    *GRID_COLS,
    "net_demand_mw",
    "wholesale_price_lag_7d",
    "region_id",
]

REGION_ENCODING = {r: i for i, r in enumerate(ALL_REGIONS)}
_UK_HOLIDAYS = holidays.UnitedKingdom(years=range(2020, 2032))


def _add_temporal(df, ts_col):
    df["hour"] = df[ts_col].dt.hour
    df["minute"] = df[ts_col].dt.minute
    df["dow"] = df[ts_col].dt.dayofweek
    df["month"] = df[ts_col].dt.month
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    local_dates = df[ts_col].dt.tz_convert("Europe/London").dt.date
    df["is_bank_holiday"] = local_dates.map(lambda d: 1 if d in _UK_HOLIDAYS else 0).astype(int)
    return df


def _attach_lag_1w(df, ts_col, tariff_indexed):
    lag_ts = pd.DatetimeIndex(df[ts_col]) - pd.Timedelta(days=7)
    df["lag_1w_price"] = tariff_indexed.reindex(lag_ts).values
    return df


def _attach_wholesale_lag_7d(df, ts_col, mid_indexed):
    lag_ts = pd.DatetimeIndex(df[ts_col]) - pd.Timedelta(days=7)
    df["wholesale_price_lag_7d"] = mid_indexed.reindex(lag_ts).values
    return df


def _attach_grid(df, ts_col, grid_history):
    """Join grid columns by timestamp. grid_history is a DataFrame indexed by timestamp."""
    target_idx = pd.DatetimeIndex(df[ts_col])
    for col in GRID_COLS:
        if col in grid_history.columns:
            df[col] = grid_history[col].reindex(target_idx).values
        else:
            df[col] = pd.NA
    return df


def _add_net_demand(df):
    """Net demand (MW) = national demand − wind generation. The canonical predictor of
    negative pricing: when wind floods a low-demand grid (sunny, breezy Sunday middays),
    net demand collapses and the wholesale price goes negative. Derived from the (possibly
    imputed) grid columns so it's always present wherever both inputs are."""
    if "demand_mw" in df.columns and "wind_generation_mw" in df.columns:
        df["net_demand_mw"] = df["demand_mw"] - df["wind_generation_mw"]
    else:
        df["net_demand_mw"] = pd.NA
    return df


def _hourly_median(grid_history):
    medians = {}
    for col in GRID_COLS:
        if col in grid_history.columns:
            s = grid_history[col].dropna()
            if not s.empty:
                medians[col] = s.groupby(s.index.hour).median()
    return medians


def _impute_by_hour(df, ts_col, medians):
    for col, med in medians.items():
        if col not in df.columns:
            continue
        mask = df[col].isna()
        if mask.any():
            df.loc[mask, col] = df.loc[mask, ts_col].dt.hour.map(med).values
    return df


def build_training_data(product):
    """Returns (X, y, ts, regions) for a given product — `regions` lets callers split by region for backtest."""
    with conn() as c:
        tariff = pd.read_sql_query(
            "SELECT valid_from, value_inc_vat, region FROM tariff WHERE product = ? ORDER BY valid_from",
            c, params=(product,),
        )
        weather = pd.read_sql_query(
            f"SELECT timestamp, {', '.join(WEATHER_COLS)} FROM weather_history", c
        )
        grid = pd.read_sql_query(
            "SELECT timestamp, carbon_intensity_forecast, wind_generation_mw, demand_mw, wholesale_price_gbp_per_mwh FROM grid_history", c
        )
    if tariff.empty or weather.empty:
        return None, None, None, None

    tariff["valid_from"] = pd.to_datetime(tariff["valid_from"], utc=True)
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    weather_idx = weather.set_index("timestamp")

    if not grid.empty:
        grid["timestamp"] = pd.to_datetime(grid["timestamp"], utc=True)
        grid_idx = grid.set_index("timestamp")
        mid_idx = grid_idx["wholesale_price_gbp_per_mwh"]
    else:
        grid_idx = pd.DataFrame()
        mid_idx = pd.Series(dtype=float)

    tariff = tariff.sort_values(["valid_from", "region"]).reset_index(drop=True)
    tariff["weather_hour"] = tariff["valid_from"].dt.floor("h")
    merged = tariff.merge(weather_idx, left_on="weather_hour", right_index=True, how="left")
    merged = _add_temporal(merged, "valid_from")

    # Lag-1w from same region's tariff (region-aware lookup)
    tariff_per_region = {
        r: tariff[tariff["region"] == r].set_index("valid_from")["value_inc_vat"]
        for r in tariff["region"].unique()
    }
    lag_values = []
    target_lag = merged["valid_from"] - pd.Timedelta(days=7)
    for region, lag_ts in zip(merged["region"].values, target_lag.values):
        s = tariff_per_region.get(region)
        lag_values.append(s.get(pd.Timestamp(lag_ts), float("nan")) if s is not None else float("nan"))
    merged["lag_1w_price"] = lag_values

    merged = _attach_grid(merged, "valid_from", grid_idx)
    merged = _add_net_demand(merged)
    merged = _attach_wholesale_lag_7d(merged, "valid_from", mid_idx)

    merged["region_id"] = merged["region"].map(REGION_ENCODING).astype("Int64")

    out = merged.dropna(subset=FEATURE_COLS + ["value_inc_vat"]).reset_index(drop=True)
    return out[FEATURE_COLS], out["value_inc_vat"], out["valid_from"], out["region"]


def build_forecast_features(region, product):
    """Build features for next 7 days for a specific (region, product) combination."""
    with conn() as c:
        forecast = pd.read_sql_query(
            f"SELECT timestamp, {', '.join(WEATHER_COLS)} FROM weather_forecast", c
        )
        tariff = pd.read_sql_query(
            "SELECT valid_from, value_inc_vat FROM tariff WHERE region = ? AND product = ? ORDER BY valid_from",
            c, params=(region, product),
        )
        grid_fc = pd.read_sql_query(
            "SELECT timestamp, carbon_intensity_forecast, wind_generation_mw, demand_mw FROM grid_forecast", c
        )
        grid_hist = pd.read_sql_query(
            "SELECT timestamp, carbon_intensity_forecast, wind_generation_mw, demand_mw, wholesale_price_gbp_per_mwh FROM grid_history", c
        )
    forecast["timestamp"] = pd.to_datetime(forecast["timestamp"], utc=True)
    forecast_idx = forecast.set_index("timestamp")
    tariff["valid_from"] = pd.to_datetime(tariff["valid_from"], utc=True)
    tariff_indexed = tariff.set_index("valid_from")["value_inc_vat"]

    if not grid_fc.empty:
        grid_fc["timestamp"] = pd.to_datetime(grid_fc["timestamp"], utc=True)
        grid_fc_idx = grid_fc.set_index("timestamp")
    else:
        grid_fc_idx = pd.DataFrame()
    if not grid_hist.empty:
        grid_hist["timestamp"] = pd.to_datetime(grid_hist["timestamp"], utc=True)
        grid_hist_idx = grid_hist.set_index("timestamp")
    else:
        grid_hist_idx = pd.DataFrame()

    horizon_start = pd.Timestamp.now(tz="UTC").floor("30min")
    horizon_end = horizon_start + pd.Timedelta(days=7)
    slots = pd.date_range(horizon_start, horizon_end, freq="30min", inclusive="left")

    df = pd.DataFrame({"valid_from": slots})
    df["weather_hour"] = df["valid_from"].dt.floor("h")
    df = df.merge(forecast_idx, left_on="weather_hour", right_index=True, how="left")
    df = _add_temporal(df, "valid_from")
    df = _attach_lag_1w(df, "valid_from", tariff_indexed)
    df = _attach_grid(df, "valid_from", grid_fc_idx)
    if not grid_hist.empty and "wholesale_price_gbp_per_mwh" in grid_hist.columns:
        df = _attach_wholesale_lag_7d(df, "valid_from", grid_hist_idx["wholesale_price_gbp_per_mwh"])
    else:
        df["wholesale_price_lag_7d"] = pd.NA

    df["region_id"] = REGION_ENCODING[region]

    medians = _hourly_median(grid_hist_idx)
    df = _impute_by_hour(df, "valid_from", medians)
    df = _add_net_demand(df)

    return df, df[FEATURE_COLS]
