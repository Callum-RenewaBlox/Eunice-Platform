"""RenewaBlox Client Atlas — client-facing opportunity map (public).

A sales-facing Leaflet map for clients and partners:
- **Hydro** — GB hydro sites with stranded electricity (installed vs export
  capacity); bubble size = stranded kW, colour = data confidence.
- **Peaker - BM** — sites with projected Balancing Mechanism offer revenues
  by tier (average and top-5% p/kWh, next 12 months).

Self-contained and client-safe: it reads ``client_atlas.html`` (a standalone
Leaflet map with ONLY client-facing data embedded — no scores, operators'
internal notes, or target rankings) and renders it via ``st.iframe``. No
database, no secrets.

``client_atlas.html`` is derived from the internal atlas with all internal
fields stripped out; regenerate it with ``_make_client.py`` if the source
changes (see git history).

Run locally:  streamlit run app_client_atlas.py
"""
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="RenewaBlox Client Atlas",
    page_icon=":material/map:",
    layout="wide",
)

# Read the map fresh from the main script on each run (NOT via an imported
# module): Streamlit re-runs this script but can keep imported modules cached,
# so reading here keeps the embedded map current after every redeploy.
CLIENT_HTML = (Path(__file__).resolve().parent / "client_atlas.html").read_text(
    encoding="utf-8")

# ----------------------------------------------------------------- sidebar
st.sidebar.title("RenewaBlox Client Atlas")
st.sidebar.caption(
    "Where stranded renewable capacity meets new revenue — no Watt wasted.")
st.sidebar.divider()
st.sidebar.markdown(
    "**Layers** — switch with the tabs in the map header:\n\n"
    "- **Hydro** — GB hydro sites with **stranded electricity** (installed vs "
    "export capacity). Bubble size = stranded kW; colour = data confidence.\n"
    "- **Peaker - BM** — sites with **projected Balancing Mechanism revenues** "
    "by tier (average and top-5% p/kWh over the next 12 months).\n\n"
    "Click any site for its detail card.")
st.sidebar.divider()
st.sidebar.caption(
    "Base map © OpenStreetMap contributors · geocoding postcodes.io.")

# -------------------------------------------------------------------- main
st.title("RenewaBlox Client Atlas")
st.caption("Where the RenewaBlox Solution fits the map — **no Watt wasted.**")

st.iframe(CLIENT_HTML, height=780)

st.caption("RenewaBlox · contact callum@renewablox.com")
