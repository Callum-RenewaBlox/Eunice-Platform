"""Compute the live scorecard from stored forecast vintages and write it to the scorecard table.

Runs daily in the Action after predictions are written; build_lite_db.py copies the (tiny)
table into data_lite.sqlite so the hosted apps show it. The numbers are produced by the same
code as `python rebuild/score_eunice_live.py data.sqlite`, so page and CLI always agree.
"""
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "rebuild"))

import db
from config import DB_PATH, PRODUCTS
from score_eunice_live import load_scored, scorecard_by_lead


def main():
    db.init_db()
    for product in PRODUCTS:
        f = load_scored(str(DB_PATH), product)
        card = scorecard_by_lead(f)
        rows = card.replace({np.nan: None}).to_dict("records")
        db.replace_scorecard(rows, product)
        print(f"scorecard[{product}]: {len(rows)} rows from {len(f)} scored slots "
              f"({f.model_version.nunique() if len(f) else 0} model versions)", flush=True)


if __name__ == "__main__":
    main()
