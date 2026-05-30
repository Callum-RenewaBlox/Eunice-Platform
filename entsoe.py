"""ENTSO-E Transparency Platform — GB day-ahead wholesale prices.

Stub. Becomes active once `ENTSOE_API_KEY` is set in `.env`.

Setup (free):
1. Register at https://transparency.entsoe.eu/
2. Email transparency@entsoe.eu requesting REST API access (auto-approved within ~3 days)
3. After approval: My Account Settings → Web API Security Token → Generate
4. Save the token in `.env` as `ENTSOE_API_KEY=<token>`

Usage will become:
    from entsoe import fetch_day_ahead_prices
    rows = fetch_day_ahead_prices(start_dt_utc, end_dt_utc)  # [(iso_ts, price_gbp_per_mwh), ...]
"""
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

import requests

from config import ENTSOE_API_KEY, ENTSOE_BASE

GB_BIDDING_ZONE = "10YGB----------A"
NS = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0"}


def fetch_day_ahead_prices(period_start, period_end):
    """Returns [(iso_ts, price_gbp_per_mwh), ...] — empty list if API key missing."""
    if not ENTSOE_API_KEY:
        return []
    r = requests.get(ENTSOE_BASE, params={
        "securityToken": ENTSOE_API_KEY,
        "documentType": "A44",
        "in_Domain": GB_BIDDING_ZONE,
        "out_Domain": GB_BIDDING_ZONE,
        "periodStart": period_start.strftime("%Y%m%d%H%M"),
        "periodEnd": period_end.strftime("%Y%m%d%H%M"),
    }, timeout=120)
    r.raise_for_status()
    return _parse_publication(r.text)


def _parse_publication(xml_text):
    root = ET.fromstring(xml_text)
    out = []
    for ts in root.findall(".//ns:TimeSeries", NS):
        period = ts.find("ns:Period", NS)
        if period is None:
            continue
        start_text = period.find("ns:timeInterval/ns:start", NS).text
        start_dt = datetime.strptime(start_text, "%Y-%m-%dT%H:%MZ")
        resolution = period.find("ns:resolution", NS).text  # e.g. "PT60M"
        step = timedelta(hours=1) if "60M" in resolution else timedelta(minutes=30)
        for point in period.findall("ns:Point", NS):
            pos = int(point.find("ns:position", NS).text)
            price = float(point.find("ns:price.amount", NS).text)
            ts_iso = (start_dt + step * (pos - 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            out.append((ts_iso, price))
    return out
