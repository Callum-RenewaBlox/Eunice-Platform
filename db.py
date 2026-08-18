import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tariff (
    valid_from    TEXT NOT NULL,
    region        TEXT NOT NULL,
    product       TEXT NOT NULL,
    valid_to      TEXT NOT NULL,
    value_inc_vat REAL NOT NULL,
    PRIMARY KEY (valid_from, region, product)
);
CREATE TABLE IF NOT EXISTS weather_history (
    timestamp        TEXT PRIMARY KEY,
    temperature_c    REAL,
    wind_speed_kmh   REAL,
    cloud_cover_pct  REAL,
    shortwave_wm2    REAL,
    precipitation_mm REAL
);
CREATE TABLE IF NOT EXISTS weather_forecast (
    timestamp        TEXT PRIMARY KEY,
    temperature_c    REAL,
    wind_speed_kmh   REAL,
    cloud_cover_pct  REAL,
    feels_like_c     REAL,
    shortwave_wm2    REAL,
    precipitation_mm REAL,
    source           TEXT NOT NULL,
    fetched_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prediction (
    valid_from      TEXT NOT NULL,
    region          TEXT NOT NULL,
    product         TEXT NOT NULL,
    valid_to        TEXT NOT NULL,
    predicted_price REAL NOT NULL,
    p05             REAL,
    p10             REAL,
    p90             REAL,
    p_spike         REAL,
    p_trough        REAL,
    p25             REAL,
    p50             REAL,
    p75             REAL,
    p95             REAL,
    p_neg           REAL,
    p_sub5          REAL,
    p_sub10         REAL,
    p_hi40          REAL,
    origin_time     TEXT,
    lead_days       INTEGER,
    model_version   TEXT NOT NULL,
    generated_at    TEXT NOT NULL,
    PRIMARY KEY (valid_from, region, product, model_version, generated_at)
);
CREATE TABLE IF NOT EXISTS forecast_vintages (
    source      TEXT NOT NULL,
    issue_time  TEXT NOT NULL,
    target_time TEXT NOT NULL,
    variable    TEXT NOT NULL,
    value       REAL,
    PRIMARY KEY (source, issue_time, target_time, variable)
);
CREATE TABLE IF NOT EXISTS scorecard (
    product       TEXT NOT NULL,
    model_version TEXT NOT NULL,
    lead_d        REAL NOT NULL,
    n             INTEGER,
    mae           REAL,
    bias          REAL,
    cov10_90      REAL,
    neg_n         INTEGER,
    neg_recall    REAL,
    neg_precision REAL,
    computed_at   TEXT NOT NULL,
    PRIMARY KEY (product, model_version, lead_d)
);
CREATE TABLE IF NOT EXISTS wholesale_price (
    valid_from        TEXT PRIMARY KEY,
    price_gbp_per_mwh REAL NOT NULL,
    source            TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS grid_history (
    timestamp                    TEXT PRIMARY KEY,
    carbon_intensity_forecast    REAL,
    carbon_intensity_actual      REAL,
    wind_generation_mw           REAL,
    demand_mw                    REAL,
    wholesale_price_gbp_per_mwh  REAL
);
CREATE TABLE IF NOT EXISTS grid_forecast (
    timestamp                 TEXT PRIMARY KEY,
    wind_generation_mw        REAL,
    demand_mw                 REAL,
    carbon_intensity_forecast REAL,
    fetched_at                TEXT NOT NULL
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        # Tariff PK migrations:
        #   - v1 → v2: PK (valid_from) → (valid_from, region)
        #   - v2 → v3: PK (valid_from, region) → (valid_from, region, product) — backfill 'AGILE'
        tariff_cols = c.execute("PRAGMA table_info(tariff)").fetchall()
        if tariff_cols:
            tariff_pk = [col[1] for col in tariff_cols if col[5] > 0]
            tariff_col_names = [col[1] for col in tariff_cols]
            if tariff_pk == ["valid_from"]:
                c.executescript(
                    """
                    CREATE TABLE tariff_new (
                        valid_from    TEXT NOT NULL,
                        region        TEXT NOT NULL,
                        valid_to      TEXT NOT NULL,
                        value_inc_vat REAL NOT NULL,
                        PRIMARY KEY (valid_from, region)
                    );
                    INSERT OR IGNORE INTO tariff_new (valid_from, region, valid_to, value_inc_vat)
                    SELECT valid_from, region, valid_to, value_inc_vat FROM tariff;
                    DROP TABLE tariff;
                    ALTER TABLE tariff_new RENAME TO tariff;
                    """
                )
                tariff_pk = ["valid_from", "region"]
                tariff_col_names = ["valid_from", "region", "valid_to", "value_inc_vat"]
            if "product" not in tariff_col_names:
                c.executescript(
                    """
                    CREATE TABLE tariff_new (
                        valid_from    TEXT NOT NULL,
                        region        TEXT NOT NULL,
                        product       TEXT NOT NULL,
                        valid_to      TEXT NOT NULL,
                        value_inc_vat REAL NOT NULL,
                        PRIMARY KEY (valid_from, region, product)
                    );
                    INSERT OR IGNORE INTO tariff_new (valid_from, region, product, valid_to, value_inc_vat)
                    SELECT valid_from, region, 'AGILE', valid_to, value_inc_vat FROM tariff;
                    DROP TABLE tariff;
                    ALTER TABLE tariff_new RENAME TO tariff;
                    """
                )
        c.executescript(SCHEMA)
        cols_forecast = {row[1] for row in c.execute("PRAGMA table_info(weather_forecast)").fetchall()}
        if "shortwave_wm2" not in cols_forecast:
            c.execute("ALTER TABLE weather_forecast ADD COLUMN shortwave_wm2 REAL")
        if "precipitation_mm" not in cols_forecast:
            c.execute("ALTER TABLE weather_forecast ADD COLUMN precipitation_mm REAL")
        cols_pred = {row[1] for row in c.execute("PRAGMA table_info(prediction)").fetchall()}
        if "p_spike" not in cols_pred:
            c.execute("ALTER TABLE prediction ADD COLUMN p_spike REAL")
        if "p05" not in cols_pred and cols_pred:
            # v3: lower band quantile so the downside can reach negative prices
            c.execute("ALTER TABLE prediction ADD COLUMN p05 REAL")
        if "p_trough" not in cols_pred and cols_pred:
            # v3: P(price < 0) classifier — downside mirror of p_spike
            c.execute("ALTER TABLE prediction ADD COLUMN p_trough REAL")
        if "region" not in cols_pred and cols_pred:
            # v1 → v2: add `region` to PK
            c.executescript(
                """
                CREATE TABLE prediction_new (
                    valid_from      TEXT NOT NULL,
                    region          TEXT NOT NULL,
                    valid_to        TEXT NOT NULL,
                    predicted_price REAL NOT NULL,
                    p10             REAL,
                    p90             REAL,
                    p_spike         REAL,
                    model_version   TEXT NOT NULL,
                    generated_at    TEXT NOT NULL,
                    PRIMARY KEY (valid_from, region, model_version, generated_at)
                );
                INSERT INTO prediction_new (valid_from, region, valid_to, predicted_price, p10, p90, p_spike, model_version, generated_at)
                SELECT valid_from, 'K', valid_to, predicted_price, p10, p90, p_spike, model_version, generated_at FROM prediction;
                DROP TABLE prediction;
                ALTER TABLE prediction_new RENAME TO prediction;
                """
            )
            cols_pred.add("region")
        if "product" not in cols_pred and cols_pred:
            # v2 → v3: add `product` to PK, backfill 'AGILE'
            c.executescript(
                """
                CREATE TABLE prediction_new (
                    valid_from      TEXT NOT NULL,
                    region          TEXT NOT NULL,
                    product         TEXT NOT NULL,
                    valid_to        TEXT NOT NULL,
                    predicted_price REAL NOT NULL,
                    p10             REAL,
                    p90             REAL,
                    p_spike         REAL,
                    model_version   TEXT NOT NULL,
                    generated_at    TEXT NOT NULL,
                    PRIMARY KEY (valid_from, region, product, model_version, generated_at)
                );
                INSERT INTO prediction_new (valid_from, region, product, valid_to, predicted_price, p10, p90, p_spike, model_version, generated_at)
                SELECT valid_from, region, 'AGILE', valid_to, predicted_price, p10, p90, p_spike, model_version, generated_at FROM prediction;
                DROP TABLE prediction;
                ALTER TABLE prediction_new RENAME TO prediction;
                """
            )
        # v4: rebuilt-engine columns — full quantile set, event probabilities, origin metadata
        # (re-read PRAGMA: the v2/v3 rebuilds above may have changed the column set; p05/p_trough
        # are re-added here because those rebuilds' column lists predate them and drop them)
        cols_pred = {row[1] for row in c.execute("PRAGMA table_info(prediction)").fetchall()}
        for col, typ in (("p05", "REAL"), ("p_trough", "REAL"),
                         ("p25", "REAL"), ("p50", "REAL"), ("p75", "REAL"), ("p95", "REAL"),
                         ("p_neg", "REAL"), ("p_sub5", "REAL"), ("p_sub10", "REAL"), ("p_hi40", "REAL"),
                         ("origin_time", "TEXT"), ("lead_days", "INTEGER")):
            if col not in cols_pred:
                c.execute(f"ALTER TABLE prediction ADD COLUMN {col} {typ}")
        cols_grid = {row[1] for row in c.execute("PRAGMA table_info(grid_history)").fetchall()}
        if "wind_generation_mw" not in cols_grid:
            c.execute("ALTER TABLE grid_history ADD COLUMN wind_generation_mw REAL")
        if "demand_mw" not in cols_grid:
            c.execute("ALTER TABLE grid_history ADD COLUMN demand_mw REAL")
        if "wholesale_price_gbp_per_mwh" not in cols_grid:
            c.execute("ALTER TABLE grid_history ADD COLUMN wholesale_price_gbp_per_mwh REAL")


def upsert_tariff(rows, region, product):
    with conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO tariff (valid_from, region, product, valid_to, value_inc_vat) VALUES (?, ?, ?, ?, ?)",
            [(r["valid_from"], region, product, r["valid_to"], r["value_inc_vat"]) for r in rows],
        )


def upsert_weather_history(rows):
    with conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO weather_history VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )


def replace_forecast(rows, source):
    fetched_at = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        c.execute("DELETE FROM weather_forecast")
        c.executemany(
            "INSERT INTO weather_forecast (timestamp, temperature_c, wind_speed_kmh, cloud_cover_pct, feels_like_c, shortwave_wm2, precipitation_mm, source, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(*r, source, fetched_at) for r in rows],
        )


def insert_predictions(rows, model_version, region, product):
    default_generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO prediction (valid_from, region, product, valid_to, predicted_price, p05, p10, p90, p_spike, p_trough, model_version, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["valid_from"],
                    region,
                    product,
                    r["valid_to"],
                    r["predicted_price"],
                    r.get("p05"),
                    r.get("p10"),
                    r.get("p90"),
                    r.get("p_spike"),
                    r.get("p_trough"),
                    model_version,
                    r.get("generated_at", default_generated_at),
                )
                for r in rows
            ],
        )


def insert_predictions_v2(rows, model_version, region, product):
    """Insert rows from the rebuilt engine (rebuild/write_predictions.py): full quantile set,
    event probabilities and origin metadata. predicted_price mirrors p50 for the apps."""
    default_generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO prediction (valid_from, region, product, valid_to, predicted_price, "
            "p05, p10, p25, p50, p75, p90, p95, p_neg, p_sub5, p_sub10, p_hi40, origin_time, lead_days, "
            "model_version, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["valid_from"],
                    region,
                    product,
                    r["valid_to"],
                    r["predicted_price"],
                    r.get("p05"),
                    r.get("p10"),
                    r.get("p25"),
                    r.get("p50"),
                    r.get("p75"),
                    r.get("p90"),
                    r.get("p95"),
                    r.get("p_neg"),
                    r.get("p_sub5"),
                    r.get("p_sub10"),
                    r.get("p_hi40"),
                    r.get("origin_time"),
                    r.get("lead_days"),
                    model_version,
                    r.get("generated_at", default_generated_at),
                )
                for r in rows
            ],
        )


def insert_vintages(rows):
    """Archive forecast vintages: (source, issue_time, target_time, variable, value) tuples.
    Vintages are immutable — INSERT OR IGNORE keeps re-captures idempotent."""
    with conn() as c:
        c.executemany(
            "INSERT OR IGNORE INTO forecast_vintages (source, issue_time, target_time, variable, value) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )


def latest_vintage_issue(source):
    with conn() as c:
        row = c.execute("SELECT MAX(issue_time) FROM forecast_vintages WHERE source = ?", (source,)).fetchone()
        return row[0] if row else None


def replace_scorecard(rows, product):
    """Replace the live scorecard for one product. rows: dicts with model_version, lead_d
    (0 = all leads), n, mae, bias, cov10_90, neg_n, neg_recall, neg_precision."""
    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn() as c:
        c.execute("DELETE FROM scorecard WHERE product = ?", (product,))
        c.executemany(
            "INSERT INTO scorecard (product, model_version, lead_d, n, mae, bias, cov10_90, "
            "neg_n, neg_recall, neg_precision, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (product, r["model_version"], r["lead_d"], r.get("n"), r.get("mae"), r.get("bias"),
                 r.get("cov10_90"), r.get("neg_n"), r.get("neg_recall"), r.get("neg_precision"), computed_at)
                for r in rows
            ],
        )


def upsert_wholesale_prices(rows, source):
    with conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO wholesale_price (valid_from, price_gbp_per_mwh, source) VALUES (?, ?, ?)",
            [(r[0], r[1], source) for r in rows],
        )


def upsert_grid_history_carbon(rows):
    """rows: list of (timestamp, carbon_intensity_forecast, carbon_intensity_actual)."""
    with conn() as c:
        c.executemany(
            """
            INSERT INTO grid_history (timestamp, carbon_intensity_forecast, carbon_intensity_actual)
            VALUES (?, ?, ?)
            ON CONFLICT(timestamp) DO UPDATE SET
                carbon_intensity_forecast = excluded.carbon_intensity_forecast,
                carbon_intensity_actual = excluded.carbon_intensity_actual
            """,
            rows,
        )


def upsert_grid_history_fuelhh(rows):
    """rows: list of (timestamp, wind_generation_mw, demand_mw)."""
    with conn() as c:
        c.executemany(
            """
            INSERT INTO grid_history (timestamp, wind_generation_mw, demand_mw)
            VALUES (?, ?, ?)
            ON CONFLICT(timestamp) DO UPDATE SET
                wind_generation_mw = excluded.wind_generation_mw,
                demand_mw = excluded.demand_mw
            """,
            rows,
        )


def upsert_grid_history_wholesale(rows):
    """rows: list of (timestamp, wholesale_price_gbp_per_mwh)."""
    with conn() as c:
        c.executemany(
            """
            INSERT INTO grid_history (timestamp, wholesale_price_gbp_per_mwh)
            VALUES (?, ?)
            ON CONFLICT(timestamp) DO UPDATE SET
                wholesale_price_gbp_per_mwh = excluded.wholesale_price_gbp_per_mwh
            """,
            rows,
        )


def replace_grid_forecast(rows):
    """rows: list of (timestamp, wind_generation_mw, demand_mw, carbon_intensity_forecast)."""
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn() as c:
        c.execute("DELETE FROM grid_forecast")
        c.executemany(
            "INSERT INTO grid_forecast (timestamp, wind_generation_mw, demand_mw, carbon_intensity_forecast, fetched_at) VALUES (?, ?, ?, ?, ?)",
            [(*r, fetched_at) for r in rows],
        )


def latest_tariff_timestamp(product=None):
    with conn() as c:
        if product:
            row = c.execute("SELECT MAX(valid_from) AS t FROM tariff WHERE product = ?", (product,)).fetchone()
        else:
            row = c.execute("SELECT MAX(valid_from) AS t FROM tariff").fetchone()
        return row["t"]


def latest_weather_history_timestamp():
    with conn() as c:
        row = c.execute("SELECT MAX(timestamp) AS t FROM weather_history").fetchone()
        return row["t"]


def latest_grid_history_timestamp(column="carbon_intensity_forecast"):
    with conn() as c:
        row = c.execute(
            f"SELECT MAX(timestamp) AS t FROM grid_history WHERE {column} IS NOT NULL"
        ).fetchone()
        return row["t"]


def clear_predictions(model_version=None, product=None):
    with conn() as c:
        clauses = []
        params = []
        if model_version:
            clauses.append("model_version = ?")
            params.append(model_version)
        if product:
            clauses.append("product = ?")
            params.append(product)
        sql = "DELETE FROM prediction"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        c.execute(sql, params)
