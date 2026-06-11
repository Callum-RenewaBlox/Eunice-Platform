"""Build data_lite.sqlite — the small, normal-file database the HOSTED apps read.

Why this exists: Streamlit Community Cloud does NOT pull Git LFS files — the full
LFS-tracked data.sqlite (110 MB) arrives on their servers as a tiny pointer stub, so the
app can't open it and every query fails. This extracts only what the deployed (commercial)
app needs at runtime — the latest forward predictions + a recent window of commercial tariff
for the savings-calculator averages — into a few-MB SQLite that is committed as a NORMAL git
file (reliably cloned on every deploy). Live published prices are fetched from the API at
runtime, so they are intentionally NOT included here.

Run after each ingest:  python build_lite_db.py
Then commit data_lite.sqlite and push — Streamlit redeploys with fresh predictions.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data.sqlite"
DST = ROOT / "data_lite.sqlite"

PRODUCTS = ("SHAPE_SHIFTERS",)   # lite is commercial-only
TARIFF_DAYS = 14                 # short raw window kept only as a chart fallback if the live API is down
HOURLY_AVG_DDL = (
    "CREATE TABLE tariff_hourly_avg ("
    "region TEXT NOT NULL, product TEXT NOT NULL, hour INTEGER NOT NULL, "
    "avg_price REAL NOT NULL, PRIMARY KEY (region, product, hour))"
)


def main():
    if not SRC.exists():
        raise SystemExit(f"Source DB not found: {SRC}. Run ingest first.")
    if DST.exists():
        DST.unlink()

    src = sqlite3.connect(str(SRC))
    dst = sqlite3.connect(str(DST))
    ph = ",".join("?" for _ in PRODUCTS)

    # Recreate the two needed tables with byte-identical DDL (so app queries work unchanged).
    for tbl in ("tariff", "prediction"):
        ddl = src.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not ddl:
            raise SystemExit(f"Table '{tbl}' missing from source DB.")
        dst.execute(ddl[0])

    # Tariff: commercial, short recent window, all regions — kept ONLY as a chart fallback if
    # the live price API is unreachable. The live API is the primary source for published prices.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=TARIFF_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    trows = src.execute(
        f"SELECT * FROM tariff WHERE product IN ({ph}) AND valid_from >= ?",
        (*PRODUCTS, cutoff),
    ).fetchall()
    if trows:
        dst.executemany(f"INSERT INTO tariff VALUES ({','.join('?' * len(trows[0]))})", trows)

    # Hourly averages: computed from the FULL commercial history at London-local hour, so the
    # hosted savings calculator matches the full app exactly without shipping years of rows.
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

    # Predictions: commercial, the latest run per region (= the forward 7-day predictions for
    # all 14 regions). generated_at is stamped per region at insert time, so a global MAX()
    # would keep only the last region written — we take each region's own latest run instead.
    latest_model = src.execute(
        f"SELECT model_version FROM prediction WHERE product IN ({ph}) ORDER BY generated_at DESC LIMIT 1",
        PRODUCTS,
    ).fetchone()
    pred_n = 0
    if latest_model:
        mv = latest_model[0]
        prows = src.execute(
            f"""
            SELECT p.* FROM prediction p
            JOIN (
                SELECT region, MAX(generated_at) AS mg FROM prediction
                WHERE product IN ({ph}) AND model_version = ? GROUP BY region
            ) m ON p.region = m.region AND p.generated_at = m.mg
            WHERE p.product IN ({ph}) AND p.model_version = ?
            """,
            (*PRODUCTS, mv, *PRODUCTS, mv),
        ).fetchall()
        if prows:
            dst.executemany(f"INSERT INTO prediction VALUES ({','.join('?' * len(prows[0]))})", prows)
            pred_n = len(prows)

    dst.commit()
    nt = dst.execute("SELECT COUNT(*) FROM tariff").fetchone()[0]
    regions = dst.execute("SELECT COUNT(DISTINCT region) FROM prediction").fetchone()[0]
    dst.execute("VACUUM")
    src.close()
    dst.close()

    size_mb = DST.stat().st_size / 1e6
    model_msg = latest_model[0] if latest_model else "n/a"
    print(f"Built {DST.name}: {nt:,} tariff rows, {pred_n:,} prediction rows "
          f"across {regions} regions, model {model_msg} — {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
