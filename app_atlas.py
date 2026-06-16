"""Eunice Atlas — UK renewable-site prospecting map (public partner app).

A Leaflet atlas of scored UK sites for the RenewaBlox Solution: a **Hydro**
layer and a **Peaker / AD-BM** layer, each site coloured by priority/tier
and sized by installed capacity, with click-through detail and live
filters. The whole map is a self-contained HTML page (``atlas.html``,
read from its sibling ``atlas.html`` at runtime) embedded via
``st.iframe``.

No database, no secrets — like Eunice HeatX, this app stands alone.

Run locally:  streamlit run app_atlas.py
"""
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="Eunice Atlas — UK renewable-site map",
    page_icon=":material/map:",
    layout="wide",
)

# Read the map fresh in the main script (NOT via an imported module): Streamlit
# reruns this script on each load but can keep imported modules cached, so a
# constant defined in another module may serve a stale atlas.html after a
# redeploy. Reading it here keeps the embedded map current on every rerun.
ATLAS_HTML = (Path(__file__).resolve().parent / "atlas.html").read_text(
    encoding="utf-8")

# ----------------------------------------------------------------- sidebar
st.sidebar.title("Eunice Atlas")
st.sidebar.caption(
    "UK renewable-site prospecting map · Hydro and Peaker / AD-BM layers")
st.sidebar.divider()
st.sidebar.markdown(
    "**Layers** — switch with the tabs in the map header:\n\n"
    "- **Hydro** — 189 sites · ~138 MW · coloured by priority\n"
    "- **Peaker - BM** — 129 sites · ~144 MW · coloured by BM tier\n\n"
    "Bubble size = installed capacity. Use the **Filters** panel (top-right) "
    "to **search** by site, operator or postcode, narrow by priority/tier "
    "and confidence, or show the top 30 by rank only. Click any site for "
    "its detail card.")
st.sidebar.divider()
st.sidebar.caption(
    "Base map © OpenStreetMap contributors · geocoding postcodes.io · "
    "site data from the RenewaBlox CRM.")

# -------------------------------------------------------------------- main
st.title("Eunice Atlas")
st.caption("Where the RenewaBlox Solution fits the map — **no Watt wasted.**")

st.iframe(ATLAS_HTML, height=780)

st.caption("RenewaBlox · Eunice platform · contact callum@renewablox.com")
