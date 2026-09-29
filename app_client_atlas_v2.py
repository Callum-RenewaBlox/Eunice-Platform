"""RenewaBlox Client Atlas — client-facing opportunity map (public).

A sales-facing MapLibre map for prospective clients and partners, in three modes:
- **Peaker Model** — the serviceable market (SAM: 129 verified AD sites, coloured by Balancing
  Mechanism tier, sized by installed capacity) and the total addressable market (TAM: 1,309
  subsidised generators; ring colour = fuel, shape = subsidy).
- **Hydro** — 57 hydro schemes whose installed capacity exceeds the export capacity the network
  allows (circle area = stranded kW, colour = match confidence).
- **PPA Benchmark** — realised and forward GB power prices against the FiT export tariff, and
  the certificate counterparty and register for every SAM site.

Look: the "product" skin (atlas/apps/client/skin-product.*) — full-bleed map with floating glass panels,
light by default with a dark theme.

Self-contained and client-safe: it reads ``client_atlas_v2.html`` — one self-contained page built by
``atlas/build.py`` from ``atlas/`` (client-safe data only; the build fails if any investor or
internal field reaches it) — and renders it via ``st.iframe``. No database, no secrets required.

Deep links: ``?view=sam|tam|hydro|ppa&site=<key>&theme=paper|night`` are validated here and
injected into the page (``window.__ATLAS_INIT__``). Optional secret ``ATLAS_PUBLIC_URL`` overrides
the public base URL used by "Copy link".

Rebuild the page:  python3 atlas/build.py --only client
Run locally:       streamlit run app_client_atlas_v2.py
"""
import json
import re
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="RenewaBlox Client Atlas",
    page_icon=":material/map:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# Full-bleed: the map page carries its own floating header, so trim Streamlit's padding (the top inset keeps the
# iframe clear of Streamlit's floating toolbar).
st.markdown(
    "<style>.block-container{padding:3.25rem 1rem 0;max-width:100%}"
    "header[data-testid='stHeader']{background:transparent}</style>",
    unsafe_allow_html=True,
)

# Read the map fresh from the main script on each run (NOT via an imported module): Streamlit
# re-runs this script but can keep imported modules cached, so reading here keeps the embedded
# map current after every redeploy.
HTML = (Path(__file__).resolve().parent / "client_atlas_v2.html").read_text(encoding="utf-8")

# Whitelisted deep-link parameters only; values must match exactly or they are dropped.
ALLOWED = {
    "view": r"^(sam|tam|hydro|ppa)$",
    "site": r"^[A-Za-z0-9-]{1,48}$",
    "theme": r"^(paper|night)$",
}
init = {}
for key, pattern in ALLOWED.items():
    value = st.query_params.get(key)
    if value is not None and re.fullmatch(pattern, str(value)):
        init[key] = str(value)
try:
    public_url = str(st.secrets.get("ATLAS_PUBLIC_URL", "") or "")
except Exception:  # no secrets file configured
    public_url = ""
if re.fullmatch(r"https://[A-Za-z0-9.\-]+(/[A-Za-z0-9._~\-/]*)?", public_url):
    init["publicUrl"] = public_url
# JSON-encode and neutralise "</" so the payload can never close the <script> element.
payload = json.dumps(init, ensure_ascii=True).replace("</", "<\\/")
HTML = HTML.replace("/*__ATLAS_INIT__*/", "window.__ATLAS_INIT__=" + payload + ";", 1)

# ----------------------------------------------------------------- sidebar (collapsed by default)
st.sidebar.title("RenewaBlox Client Atlas")
st.sidebar.caption("Where stranded renewable capacity meets new revenue — no Watt wasted.")
st.sidebar.divider()
st.sidebar.markdown(
    "**Views** — switch with *Peaker · Hydro · PPA Benchmark* at the top left of the map "
    "(keys **1 2 3**):\n\n"
    "- **Peaker Model** — *SAM*: 129 verified anaerobic-digestion sites, coloured by projected "
    "Balancing Mechanism tier and sized by installed capacity. *TAM*: 1,309 subsidised biogas, "
    "biomass, energy-from-waste, landfill and sewage-gas generators. Switch SAM / TAM in the "
    "panel on the left (key **S**).\n"
    "- **Hydro** — 57 hydro schemes generating more than the grid will take (stranded kW).\n"
    "- **PPA Benchmark** — realised and forward GB power prices against the guaranteed FiT "
    "export tariff, with each site's export arrangement and certificate counterparty.\n\n"
    "Search with **⌘K** / **Ctrl K** or **/**; click any site for its detail card; **T** switches "
    "between the light and dark theme.")
st.sidebar.divider()
st.sidebar.caption(
    "Base map © OpenStreetMap contributors · OpenFreeMap © OpenMapTiles · Natural Earth · geocoding postcodes.io.")

# -------------------------------------------------------------------- main
st.iframe(HTML, height=820)
st.markdown("RenewaBlox · contact [callum@renewablox.com](mailto:callum@renewablox.com)")
