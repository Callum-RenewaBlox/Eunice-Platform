"""RenewaBlox Investor Atlas — investor presentation map.

A presentation-oriented Leaflet map of the UK flexibility opportunity
(peaker and hydro assets) with headline KPIs, for investor meetings.
Self-contained: reads ``investor_atlas.html`` (Leaflet from a CDN, data
embedded) and renders it via ``st.iframe``. No database, no secrets.

Carries site-level commercial detail (developer, capacity, contract-value
metrics), so deploy this one GATED to invited investor viewers rather than
public. Run locally:  streamlit run app_investor_atlas.py
"""
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="RenewaBlox Investor Atlas",
    page_icon=":material/map:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Read the map fresh from the main script on each run (Streamlit caches
# imported modules but re-runs this script, so reading here keeps the
# embedded map current after every redeploy). The HTML carries its own
# header, KPIs, tabs and legend, so the Streamlit chrome stays minimal.
INVESTOR_HTML = (Path(__file__).resolve().parent / "investor_atlas.html").read_text(
    encoding="utf-8")

st.iframe(INVESTOR_HTML, height=820)
st.caption("RenewaBlox · Investor Atlas · contact callum@renewablox.com")
