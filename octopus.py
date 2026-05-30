import requests

from config import OCTOPUS_BASE, PRODUCTS


def fetch_agile_rates(region, product_key, period_from=None, period_to=None):
    """Fetch half-hourly rates for a (region, product) combination.

    `product_key` is the logical name (e.g. "AGILE" or "SHAPE_SHIFTERS"); the actual
    Octopus product code is resolved from config.PRODUCTS.
    """
    product_code = PRODUCTS[product_key]["code"]
    tariff_code = f"E-1R-{product_code}-{region}"
    url = f"{OCTOPUS_BASE}/products/{product_code}/electricity-tariffs/{tariff_code}/standard-unit-rates/"
    params = {"page_size": 1500}
    if period_from:
        params["period_from"] = period_from
    if period_to:
        params["period_to"] = period_to

    rows = []
    while url:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        body = r.json()
        rows.extend(body["results"])
        url = body.get("next")
        params = None
    return rows
