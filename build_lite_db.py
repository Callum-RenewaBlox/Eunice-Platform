"""Build data_lite.sqlite — the small, normal-file database BOTH hosted apps read.

Why this exists: Streamlit Community Cloud does NOT pull Git LFS files — the full
LFS-tracked data.sqlite (110 MB) arrives on their servers as a tiny pointer stub, so the
app can't open it and every query fails. This extracts only what the deployed apps need at
runtime into a few-MB SQLite committed as a NORMAL git file (reliably cloned on every deploy).

One shared slim DB serves both:
  - Eunice-lite (app_lite.py) — commercial only; reads the SHAPE_SHIFTERS slice.
  - Eunice full (app.py)      — both products, plus the "Prediction vs actual" learning view.

Contents (both products, all 14 regions):
  - tariff            : recent window only (chart fallback + accuracy actuals + stats)
  - tariff_hourly_avg : hour-of-day averages from the FULL history (savings calculator)
  - prediction        : recent target slots — the latest forward run (chart / spike / trough)
                        AND the aged forward predictions the accuracy view compares to actuals
  - weather_forecast  : small, copied whole (full app's weather panel)
  - grid_forecast     : small, copied whole (full app's grid panel)

Live published prices are fetched from the API at runtime, so deep tariff history is NOT shipped.

Run after each ingest:  python build_lite_db.py   (the daily Action does this automatically)
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data.sqlite"
DST = ROOT / "data_lite.sqlite"

PRODUCTS = ("AGILE", "SHAPE_SHIFTERS")   # both — one slim DB serves lite + full
TARIFF_DAYS = 21                         # recent tariff window kept (fallback + accuracy actuals)
PRED_VALID_DAYS = 10                     # keep predictions whose TARGET slot is within this window
COPY_WHOLE = ("weather_forecast", "grid_forecast")   # small forecast tables, copied entire
HOURLY_AVG_DDL = (
    "CREATE TABLE tariff_hourly_avg ("
    "region TEXT NOT NULL, product TEXT NOT NULL, hour INTEGER NOT NULL, "
    "avg_price REAL NOT NULL, PRIMARY KEY (region, product, hour))"
)


def _copy_ddl(src, dst, table):
    ddl = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not ddl:
        raise SystemExit(f"Table '{table}' missing from source DB.")
    dst.execute(ddl[0])


def main():
    if not SRC.exists() or SRC.stat().st_size < 100_000:
        raise SystemExit(f"Source DB not found or is an LFS pointer: {SRC}. Run ingest / git lfs pull first.")
    if DST.exists():
        DST.unlink()

    src = sqlite3.connect(str(SRC))
    dst = sqlite3.connect(str(DST))
    ph = ",".join("?" for _ in PRODUCTS)
    now = datetime.now(timezone.utc)
    tariff_cut = (now - timedelta(days=TARIFF_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pred_cut = (now - timedelta(days=PRED_VALID_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for tbl in ("tariff", "prediction", *COPY_WHOLE):
        _copy_ddl(src, dst, tbl)

    # Tariff: both products, recent window (chart fallback if live API down + accuracy actuals + stats).
    trows = src.execute(
        f"SELECT * FROM tariff WHERE product IN ({ph}) AND valid_from >= ?", (*PRODUCTS, tariff_cut)
    ).fetchall()
    if trows:
        dst.executemany(f"INSERT INTO tariff VALUES ({','.join('?' * len(trows[0]))})", trows)

    # Hourly averages from the FULL history (London local hour) — keeps the savings calculator
    # identical to the full app without shipping years of half-hourly rows.
    dst.execute(HOURLY_AVG_DDL)
    tdf = pd.read_sql_query(
        f"SELECT valid_from, value_inc_vat, region, product FROM tariff WHERE product IN ({ph})",
        src, params=PRODUCTS,
    )
    if not tdf.empty:
        tdf["valid_from"] = pd.to_datetime(tdf["valid_from"], utc=True)
        tdf["hour"] = tdf["valid_from"].dt.tz_convert("Europe/London").dt.hour
        avg = (tdf.groupby(["region", "product", "hour"])["value_inc_vat"].mean()
               .reset_index().rename(columns={"value_inc_vat": "avg_price"}))
        dst.executemany(
            "INSERT INTO tariff_hourly_avg (region, product, hour, avg_price) VALUES (?, ?, ?, ?)",
            [(r.region, r.product, int(r.hour), float(r.avg_price)) for r in avg.itertuples(index=False)],
        )

    # Predictions — two minimal, deduped sets (keeps the file small so daily commits stay cheap):
    #   (A) the latest forward run per region+product → the future slots the chart/spike/trough use
    #   (B) the EARLIEST forward prediction (generated_at < valid_from) for each recent past slot →
    #       exactly what the "Prediction vs actual" accuracy view compares against actuals.
    ncols = len(src.execute("SELECT * FROM prediction LIMIT 1").description)
    insert_pred = f"INSERT OR IGNORE INTO prediction VALUES ({','.join('?' * ncols)})"

    # (A) latest run per region+product (generated_at is stamped per region, so group by both)
    set_a = src.execute(
        f"""
        SELECT p.* FROM prediction p
        JOIN (SELECT region, product, MAX(generated_at) AS mg FROM prediction
              WHERE product IN ({ph}) GROUP BY region, product) m
          ON p.region = m.region AND p.product = m.product AND p.generated_at = m.mg
        WHERE p.product IN ({ph})
        """,
        (*PRODUCTS, *PRODUCTS),
    ).fetchall()
    if set_a:
        dst.executemany(insert_pred, set_a)

    # (B) earliest forward prediction per recent past slot
    set_b = src.execute(
        f"""
        SELECT p.* FROM prediction p
        JOIN (SELECT valid_from, region, product, MIN(generated_at) AS mg FROM prediction
              WHERE product IN ({ph}) AND valid_from >= ? AND generated_at < valid_from
              GROUP BY valid_from, region, product) m
          ON p.valid_from = m.valid_from AND p.region = m.region
             AND p.product = m.product AND p.generated_at = m.mg
        WHERE p.product IN ({ph})
        """,
        (*PRODUCTS, pred_cut, *PRODUCTS),
    ).fetchall()
    if set_b:
        dst.executemany(insert_pred, set_b)

    # Small forecast tables — copied whole for the full app's weather + grid panels.
    for tbl in COPY_WHOLE:
        rows = src.execute(f"SELECT * FROM {tbl}").fetchall()
        if rows:
            dst.executemany(f"INSERT INTO {tbl} VALUES ({','.join('?' * len(rows[0]))})", rows)

    dst.commit()
    nt = dst.execute("SELECT COUNT(*) FROM tariff").fetchone()[0]
    npd = dst.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
    regions = dst.execute("SELECT COUNT(DISTINCT region) FROM prediction").fetchone()[0]
    prods = dst.execute("SELECT COUNT(DISTINCT product) FROM prediction").fetchone()[0]
    dst.execute("VACUUM")
    src.close()
    dst.close()

    size_mb = DST.stat().st_size / 1e6
    print(f"Built {DST.name}: {nt:,} tariff rows, {npd:,} prediction rows "
          f"({prods} products × {regions} regions) — {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
