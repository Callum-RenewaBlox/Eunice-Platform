"""Fetch full history of Octopus Agile (domestic) and Shape Shifters Agile (business) unit rates.
Saves parquet per product/region under data/.
"""
import requests, pandas as pd, sys, time, json, os
from pathlib import Path

D = f"{Path(__file__).resolve().parent.as_posix()}/data"
BASE = "https://api.octopus.energy/v1/products/{prod}/electricity-tariffs/E-1R-{prod}-{reg}/standard-unit-rates/"

def fetch(prod, reg, out):
    url = BASE.format(prod=prod, reg=reg) + "?page_size=1500"
    rows = []
    n = 0
    while url:
        for attempt in range(5):
            try:
                r = requests.get(url, timeout=60)
                if r.status_code == 200:
                    break
                time.sleep(2 * (attempt + 1))
            except Exception as e:
                time.sleep(2 * (attempt + 1))
        j = r.json()
        rows.extend(j["results"])
        url = j.get("next")
        n += 1
        if n % 10 == 0:
            print(prod, reg, "pages", n, "rows", len(rows), flush=True)
    df = pd.DataFrame(rows)
    df["valid_from"] = pd.to_datetime(df["valid_from"], utc=True)
    df["valid_to"] = pd.to_datetime(df["valid_to"], utc=True)
    df = df.sort_values("valid_from").drop_duplicates("valid_from")
    df.to_parquet(out, index=False)
    print("saved", out, len(df), df.valid_from.min(), df.valid_from.max(), flush=True)

if __name__ == "__main__":
    prod = sys.argv[1]
    regs = sys.argv[2].split(",")
    for reg in regs:
        out = f"{D}/octopus_{prod}_{reg}.parquet"
        if os.path.exists(out):
            print("exists", out); continue
        fetch(prod, reg, out)
