"""Pipeline: pull tariff (all regions) + weather + grid data + 7-day forecasts, then generate predictions."""
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from bmrs import (
    fetch_demand_forecast,
    fetch_fuelhh_history,
    fetch_market_index_history,
    fetch_wind_forecast,
)
from carbon_intensity import fetch_intensity_forecast_48h, fetch_intensity_history
from config import ALL_REGIONS, HISTORY_YEARS, PRODUCTS
from db import (
    clear_predictions,
    init_db,
    insert_predictions,
    latest_grid_history_timestamp,
    latest_tariff_timestamp,
    latest_weather_history_timestamp,
    replace_forecast,
    replace_grid_forecast,
    upsert_grid_history_carbon,
    upsert_grid_history_fuelhh,
    upsert_grid_history_wholesale,
    upsert_tariff,
    upsert_weather_history,
)
from model import (
    MODEL_VERSION,
    backtest_last_n_days_all_regions,
    predict_next_7_days_all_regions,
)
from octopus import fetch_agile_rates
from weather import fetch_forecast_metoffice, fetch_forecast_open_meteo, fetch_historical


def ingest_tariff(full=False):
    """Pull tariff for every (product × region) combination in parallel."""
    def fetch_one(product, region):
        latest = latest_tariff_timestamp(product=product)
        product_meta = PRODUCTS[product]
        if full or not latest:
            history_start = product_meta.get("history_start")
            cutoff = (date.today() - timedelta(days=HISTORY_YEARS * 365)).isoformat()
            if history_start and history_start > cutoff:
                cutoff = history_start
            period_from = f"{cutoff}T00:00:00Z"
        else:
            period_from = latest
        return product, region, period_from, fetch_agile_rates(region, product, period_from=period_from)

    jobs = [(p, r) for p in PRODUCTS for r in ALL_REGIONS]
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda j: fetch_one(*j), jobs))

    total_per_product = {}
    for product, region, period_from, rows in results:
        upsert_tariff(rows, region, product)
        total_per_product[product] = total_per_product.get(product, 0) + len(rows)
    for product, total in total_per_product.items():
        print(f"[tariff] product={product}: {total} rows across {len(ALL_REGIONS)} regions")


def ingest_weather_history(full=False):
    end = date.today() - timedelta(days=2)
    last = latest_weather_history_timestamp()
    if full or not last:
        start = end - timedelta(days=HISTORY_YEARS * 365)
    else:
        start = date.fromisoformat(last[:10]) - timedelta(days=1)
    if start >= end:
        print("[weather history] up to date")
        return
    rows = fetch_historical(start.isoformat(), end.isoformat())
    upsert_weather_history(rows)
    print(f"[weather history] {start} -> {end}, {len(rows)} hourly rows")


def ingest_carbon_intensity_history(full=False):
    now = datetime.now(timezone.utc).replace(microsecond=0, second=0, minute=0)
    last = latest_grid_history_timestamp("carbon_intensity_forecast")
    if full or not last:
        start = now - timedelta(days=HISTORY_YEARS * 365)
    else:
        start = pd.to_datetime(last, utc=True).to_pydatetime() - timedelta(hours=2)
    if start >= now:
        print("[grid history: carbon] up to date")
        return
    df = fetch_intensity_history(start, now)
    if df.empty:
        print("[grid history: carbon] no rows fetched")
        return
    rows = [
        (
            r["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            None if pd.isna(r["carbon_intensity_forecast"]) else float(r["carbon_intensity_forecast"]),
            None if pd.isna(r["carbon_intensity_actual"]) else float(r["carbon_intensity_actual"]),
        )
        for _, r in df.iterrows()
    ]
    upsert_grid_history_carbon(rows)
    print(f"[grid history: carbon] {len(rows)} rows ({start.date()} -> {now.date()})")


def ingest_wholesale_history(full=False):
    end = date.today()
    last = latest_grid_history_timestamp("wholesale_price_gbp_per_mwh")
    if full or not last:
        start = end - timedelta(days=HISTORY_YEARS * 365)
    else:
        start = date.fromisoformat(last[:10]) - timedelta(days=1)
    if start >= end:
        print("[grid history: wholesale] up to date")
        return
    print(f"[grid history: wholesale] fetching {start} -> {end}…")
    df = fetch_market_index_history(start, end)
    if df.empty:
        print("[grid history: wholesale] no rows fetched")
        return
    rows = [
        (
            r["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            None if pd.isna(r["wholesale_price_gbp_per_mwh"]) else float(r["wholesale_price_gbp_per_mwh"]),
        )
        for _, r in df.iterrows()
    ]
    upsert_grid_history_wholesale(rows)
    print(f"[grid history: wholesale] {len(rows)} half-hourly rows")


def ingest_fuelhh_history(full=False):
    end = date.today() - timedelta(days=1)
    last = latest_grid_history_timestamp("wind_generation_mw")
    if full or not last:
        start = end - timedelta(days=HISTORY_YEARS * 365)
    else:
        start = date.fromisoformat(last[:10]) - timedelta(days=1)
    if start >= end:
        print("[grid history: fuelhh] up to date")
        return
    print(f"[grid history: fuelhh] fetching {start} -> {end} (this can take a few minutes)…")
    df = fetch_fuelhh_history(start, end)
    if df.empty:
        print("[grid history: fuelhh] no rows fetched")
        return
    rows = [
        (
            r["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            None if pd.isna(r["wind_generation_mw"]) else float(r["wind_generation_mw"]),
            None if pd.isna(r["demand_mw"]) else float(r["demand_mw"]),
        )
        for _, r in df.iterrows()
    ]
    upsert_grid_history_fuelhh(rows)
    print(f"[grid history: fuelhh] {len(rows)} half-hourly rows")


def ingest_forecast():
    om = fetch_forecast_open_meteo()
    replace_forecast(om, "open_meteo")
    print(f"[forecast] open-meteo: {len(om)} hourly rows")
    try:
        mo = fetch_forecast_metoffice()
        print(f"[forecast] met-office: {len(mo)} rows fetched (sanity check; not stored as canonical yet)")
    except Exception as e:
        print(f"[forecast] met-office skipped: {e}")


def ingest_grid_forecast():
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=8)

    try:
        ci = fetch_intensity_forecast_48h()
    except Exception as e:
        ci = pd.DataFrame(columns=["timestamp", "carbon_intensity_forecast"])
        print(f"[grid forecast] carbon intensity skipped: {e}")

    try:
        wind = fetch_wind_forecast(now, end)
    except Exception as e:
        wind = pd.DataFrame(columns=["timestamp", "wind_generation_mw"])
        print(f"[grid forecast] BMRS WINDFOR skipped: {e}")

    try:
        demand = fetch_demand_forecast(now, end)
    except Exception as e:
        demand = pd.DataFrame(columns=["timestamp", "demand_mw"])
        print(f"[grid forecast] BMRS NDF skipped: {e}")

    merged = wind.merge(demand, on="timestamp", how="outer").merge(ci, on="timestamp", how="outer")
    merged = merged.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)

    rows = [
        (
            r["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            None if pd.isna(r.get("wind_generation_mw")) else float(r["wind_generation_mw"]),
            None if pd.isna(r.get("demand_mw")) else float(r["demand_mw"]),
            None if pd.isna(r.get("carbon_intensity_forecast")) else float(r["carbon_intensity_forecast"]),
        )
        for _, r in merged.iterrows()
    ]
    replace_grid_forecast(rows)
    print(
        f"[grid forecast] {len(rows)} rows "
        f"(wind={wind.shape[0]}, demand={demand.shape[0]}, ci={ci.shape[0]})"
    )


def run_predictions():
    for product in PRODUCTS:
        try:
            all_preds = predict_next_7_days_all_regions(product)
        except Exception as e:
            print(f"[predict] product={product} skipped: {e}")
            continue
        total = 0
        for region, preds in all_preds.items():
            if preds:
                insert_predictions(preds, MODEL_VERSION, region, product)
                total += len(preds)
        print(f"[predict] product={product}: {total} forward predictions across {len(all_preds)} regions ({MODEL_VERSION})")


def run_backtest():
    for product in PRODUCTS:
        try:
            all_preds = backtest_last_n_days_all_regions(7, product=product)
        except Exception as e:
            print(f"[backtest] product={product} skipped: {e}")
            continue
        total = 0
        for region, preds in all_preds.items():
            if preds:
                insert_predictions(preds, MODEL_VERSION, region, product)
                total += len(preds)
        if total:
            print(f"[backtest] product={product}: {total} backfill predictions across {len(all_preds)} regions ({MODEL_VERSION})")


if __name__ == "__main__":
    init_db()
    full = "--full" in sys.argv
    if full:
        clear_predictions()
    ingest_tariff(full=full)
    ingest_weather_history(full=full)
    ingest_carbon_intensity_history(full=full)
    ingest_fuelhh_history(full=full)
    ingest_wholesale_history(full=full)
    ingest_forecast()
    ingest_grid_forecast()
    if full:
        run_backtest()
    run_predictions()
