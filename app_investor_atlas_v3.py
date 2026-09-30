"""RenewaBlox Investor Atlas v3 — investor presentation map in the RenewaBlox brand (gated).

A presentation-oriented MapLibre map of the GB flexibility opportunity for investor meetings, in three modes:
- **Peaker plants** — the serviceable market (SAM: 129 AD peakers, coloured by Balancing Mechanism tier and
  sized by Year-5 Total Contract Value; the 24 sites awaiting a BM figure are hollow rings) and the total
  addressable market (TAM: 1,309 subsidised generators with an indicative TCV Potential and its caveat).
- **Hydro** — 57 stranded hydro units (stranded capacity, Bitcoin mined, TCV).
- **PPA Benchmark** — realised and forward GB power prices against the FiT export tariff, the certificate
  counterparties and the full site register.
The headline figures sit in the brand KPI card of the left panel; a Sources & method drawer and a **Present**
mode (six chapters, ← → Esc) are built in.

Look: the shared "product" skin (atlas/skins/product/) with the RenewaBlox brand (official wordmark, Blox teal /
navy / sky, Leelawadee UI with Open Sans as the web fallback), like the Client Atlas v2. Compared with the
Investor Atlas v2 (app_investor_atlas_v2.py, kept as it is) there is no GB power ticker and no headline block.

It reads ``investor_atlas_v3.html`` — one self-contained page built by ``atlas/build.py`` from ``atlas/`` — and
renders it via ``st.iframe``. The page carries site-level commercial detail (developer, contract values, BTC),
so deploy this app GATED to invited investor viewers (Streamlit Cloud viewer allowlist), never public.

Deep links: ``?view=sam|tam|hydro|ppa&site=<key>&theme=paper|night&present=1`` are validated here and injected
into the page (``window.__ATLAS_INIT__``). Optional secret ``ATLAS_PUBLIC_URL`` overrides the base URL used by
"Copy link". Commercial values are never put in URLs.

Rebuild the page:  python3 atlas/build.py --only investor_v3
Run locally:       streamlit run app_investor_atlas_v3.py
"""
import json
import re
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(
    page_title="RenewaBlox Investor Atlas",
    page_icon=str(ROOT / "atlas" / "brand" / "roundel-192.png"),  # the BLOX. roundel (atlas/brand/README.md)
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "") or "")
    except Exception:  # no secrets file configured
        return ""


# Full-bleed: the map page carries its own header, so trim Streamlit's padding (the top inset keeps the iframe
# clear of Streamlit's floating toolbar).
st.markdown(
    "<style>.block-container{padding:3.25rem 1rem 0;max-width:100%}"
    "header[data-testid='stHeader']{background:transparent}</style>",
    unsafe_allow_html=True,
)

# Read the map fresh from the main script on each run (NOT via an imported module): Streamlit re-runs this
# script but can keep imported modules cached, so reading here keeps the embedded map current after every
# redeploy.
HTML = (ROOT / "investor_atlas_v3.html").read_text(encoding="utf-8")

# Whitelisted deep-link parameters only; values must match exactly or they are dropped.
ALLOWED = {
    "view": r"^(sam|tam|hydro|ppa)$",
    "site": r"^[A-Za-z0-9-]{1,48}$",
    "theme": r"^(paper|night)$",
    "present": r"^1$",
}
init = {}
for key, pattern in ALLOWED.items():
    value = st.query_params.get(key)
    if value is not None and re.fullmatch(pattern, str(value)):
        init[key] = str(value)
public_url = _secret("ATLAS_PUBLIC_URL")
if re.fullmatch(r"https://[A-Za-z0-9.\-]+(/[A-Za-z0-9._~\-/]*)?", public_url):
    init["publicUrl"] = public_url
# JSON-encode and neutralise "</" so the payload can never close the <script> element.
payload = json.dumps(init, ensure_ascii=True).replace("</", "<\\/")
HTML = HTML.replace("/*__ATLAS_INIT__*/", "window.__ATLAS_INIT__=" + payload + ";", 1)

# ----------------------------------------------------------------- sidebar (collapsed by default)
st.sidebar.title("RenewaBlox Investor Atlas")
st.sidebar.caption("Confidential — investor use only. Indicative; not investment advice.")
st.sidebar.divider()
st.sidebar.markdown(
    "**Views** — switch with the tabs in the map header:\n\n"
    "- **Peaker plants** — *SAM*: 129 AD peakers sized by Year-5 Total Contract Value (hollow rings await a "
    "BM figure). *TAM*: 1,309 subsidised generators with an indicative TCV Potential — its caveat and method "
    "sit next to the number.\n"
    "- **Hydro** — 57 stranded hydro units: stranded capacity, Bitcoin mined and contract value.\n"
    "- **PPA Benchmark** — realised and forward GB power prices against the FiT export tariff, with each "
    "site's export arrangement and certificate counterparty.\n\n"
    "Press **Present** (or **P**) for the six-chapter meeting mode; **←/→** step, **Esc** exits. "
    "Search with **/** or **⌘K**.")
st.sidebar.divider()
st.sidebar.caption(
    "Base map © OpenStreetMap contributors · OpenFreeMap © OpenMapTiles · Natural Earth · geocoding postcodes.io.")

# -------------------------------------------------------------------- main
st.iframe(HTML, height=820)
st.markdown("RenewaBlox · Investor Atlas · contact [callum@renewablox.com](mailto:callum@renewablox.com)")
