"""Sync the durable tables from data.sqlite to BigQuery (dataset `eunice`, europe-west2).

Self-activating: does nothing (exit 0) until credentials exist — either the GCP_SA_KEY env var
(service-account JSON, set from the Actions secret) or GOOGLE_APPLICATION_CREDENTIALS. Once
live, each daily run appends the increments, so BigQuery becomes the durable store and SQLite
remains the small runtime extract.

Synced:
  - tariff            append rows with valid_from > BQ high-water mark
  - prediction        append rows with generated_at > BQ high-water mark
  - forecast_vintages append rows with issue_time > BQ high-water mark (per source)
  - scorecard         truncate + reload (small, recomputed daily)
  - view `scorecard_live`: MAE / P10-P90 coverage by model_version and lead over the raw tables
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pandas as pd

from config import DB_PATH

PROJECT = os.environ.get("GCP_PROJECT_ID", "")     # optional; else taken from the key file
DATASET = "eunice"
LOCATION = "europe-west2"


def _credentials():
    key = os.environ.get("GCP_SA_KEY", "").strip()
    if key:
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        f.write(key); f.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
        return json.loads(key).get("project_id")
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        with open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]) as fh:
            return json.load(fh).get("project_id")
    return None


def main():
    project = PROJECT or _credentials()
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("bq_sync: no GCP credentials (GCP_SA_KEY secret not set) — skipped", flush=True)
        return
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    ds_ref = bigquery.Dataset(f"{client.project}.{DATASET}")
    ds_ref.location = LOCATION
    client.create_dataset(ds_ref, exists_ok=True)
    src = sqlite3.connect(str(DB_PATH))

    def sync_incremental(table, watermark_col, extra_key=None):
        full = f"{client.project}.{DATASET}.{table}"
        try:
            hw = next(client.query(f"SELECT MAX({watermark_col}) m FROM `{full}`").result()).m
        except Exception:
            hw = None
        q = f"SELECT * FROM {table}"
        params = ()
        if hw:
            q += f" WHERE {watermark_col} > ?"
            params = (hw,)
        df = pd.read_sql(q, src, params=params)
        if df.empty:
            print(f"bq_sync: {table} up to date", flush=True)
            return
        job = client.load_table_from_dataframe(
            df, full, job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"))
        job.result()
        print(f"bq_sync: {table} +{len(df)} rows (watermark {watermark_col} > {hw})", flush=True)

    def sync_replace(table):
        full = f"{client.project}.{DATASET}.{table}"
        df = pd.read_sql(f"SELECT * FROM {table}", src)
        job = client.load_table_from_dataframe(
            df, full, job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"))
        job.result()
        print(f"bq_sync: {table} replaced ({len(df)} rows)", flush=True)

    sync_incremental("tariff", "valid_from")
    sync_incremental("prediction", "generated_at")
    sync_incremental("forecast_vintages", "issue_time")
    sync_replace("scorecard")

    client.query(f"""
    CREATE OR REPLACE VIEW `{client.project}.{DATASET}.scorecard_live` AS
    WITH scored AS (
      SELECT p.model_version, p.product,
             CEIL(TIMESTAMP_DIFF(TIMESTAMP(p.valid_from), TIMESTAMP(p.generated_at), HOUR) / 24.0) AS lead_d,
             p.predicted_price - t.value_inc_vat AS err,
             CAST(t.value_inc_vat BETWEEN p.p10 AND p.p90 AS INT64) AS covered,
             CAST(t.value_inc_vat < 0 AS INT64) AS neg
      FROM `{client.project}.{DATASET}.prediction` p
      JOIN `{client.project}.{DATASET}.tariff` t
        ON t.valid_from = p.valid_from AND t.region = p.region AND t.product = p.product
      WHERE TIMESTAMP(p.generated_at) < TIMESTAMP(p.valid_from)
    )
    SELECT model_version, product, lead_d, COUNT(*) n, AVG(ABS(err)) mae, AVG(err) bias,
           AVG(covered) cov10_90, SUM(neg) neg_n
    FROM scored GROUP BY model_version, product, lead_d
    """).result()
    print("bq_sync: scorecard_live view refreshed", flush=True)
    src.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"bq_sync FAILED: {e}", flush=True)
        sys.exit(1)
