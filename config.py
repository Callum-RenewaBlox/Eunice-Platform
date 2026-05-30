import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

LOCATION_NAME = "Swansea"
LATITUDE = 51.6214
LONGITUDE = -3.9436
REGION = "K"  # default region

# RenewaBlox Solution tariff variants supported by Eunice.
# Each entry has the upstream API product code (internal — used for data ingest), the customer-
# facing display label, and a segment description. Logical key (AGILE / SHAPE_SHIFTERS) is what
# we store in the DB `product` column — these are internal identifiers, never shown to clients.
PRODUCTS = {
    "AGILE": {
        "code": "AGILE-24-10-01",
        "label": "Domestic",
        "segment": "Domestic half-hourly RenewaBlox Solution",
        "history_start": "2024-05-01",
    },
    "SHAPE_SHIFTERS": {
        "code": "AGILE-BUS-25-02-05",
        "label": "Commercial",
        "segment": "Commercial half-hourly RenewaBlox Solution",
        "history_start": "2025-01-15",
    },
}
DEFAULT_PRODUCT = "AGILE"

OCTOPUS_BASE = "https://api.octopus.energy/v1"
# Legacy single-product constants (kept for backward compatibility — prefer PRODUCTS)
OCTOPUS_PRODUCT = PRODUCTS[DEFAULT_PRODUCT]["code"]
OCTOPUS_TARIFF_CODE = f"E-1R-{OCTOPUS_PRODUCT}-{REGION}"

# 14 GSP regions used by Octopus (letters I and O are skipped)
ALL_REGIONS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P"]
REGION_NAMES = {
    "A": "Eastern England",
    "B": "East Midlands",
    "C": "London",
    "D": "Merseyside & N. Wales",
    "E": "West Midlands",
    "F": "North East England",
    "G": "North West England",
    "H": "Southern England",
    "J": "South East England",
    "K": "South Wales",
    "L": "South West England",
    "M": "Yorkshire",
    "N": "Southern Scotland",
    "P": "Northern Scotland",
}

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

METOFFICE_BASE = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0"
METOFFICE_API_KEY = os.environ.get("METOFFICE_API_KEY", "").strip()

ENTSOE_BASE = "https://web-api.tp.entsoe.eu/api"
ENTSOE_API_KEY = os.environ.get("ENTSOE_API_KEY", "").strip()

ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"
ELEXON_API_KEY = os.environ.get("ELEXON_API_KEY", "").strip()

DB_PATH = ROOT / "data.sqlite"
HISTORY_YEARS = 2

GB_SITES = [
    {"name": "East Anglia offshore", "lat": 54.0, "lon": 2.0,  "w_wind": 0.30, "w_solar": 0.05, "w_demand": 0.03},
    {"name": "Yorks/Lincs coast",    "lat": 53.5, "lon": 0.2,  "w_wind": 0.18, "w_solar": 0.08, "w_demand": 0.10},
    {"name": "NE Scotland offshore", "lat": 57.5, "lon": -2.0, "w_wind": 0.30, "w_solar": 0.02, "w_demand": 0.05},
    {"name": "South Wales",          "lat": 51.4, "lon": -3.5, "w_wind": 0.07, "w_solar": 0.10, "w_demand": 0.05},
    {"name": "Cornwall/Devon",       "lat": 50.5, "lon": -4.5, "w_wind": 0.05, "w_solar": 0.20, "w_demand": 0.05},
    {"name": "Kent / SE England",    "lat": 51.2, "lon": 1.0,  "w_wind": 0.05, "w_solar": 0.20, "w_demand": 0.10},
    {"name": "Greater London",       "lat": 51.5, "lon": -0.1, "w_wind": 0.00, "w_solar": 0.05, "w_demand": 0.30},
    {"name": "Manchester / NW",      "lat": 53.5, "lon": -2.2, "w_wind": 0.05, "w_solar": 0.10, "w_demand": 0.20},
    {"name": "Glasgow / W Scotland", "lat": 55.9, "lon": -4.3, "w_wind": 0.00, "w_solar": 0.05, "w_demand": 0.07},
    {"name": "East Midlands",        "lat": 52.6, "lon": -1.1, "w_wind": 0.00, "w_solar": 0.15, "w_demand": 0.05},
]

SPIKE_THRESHOLD_P = 25.0
