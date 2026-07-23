"""West Newton Infrastructure Map — client deliverable (Reabold).

A standalone Leaflet map of the electricity network around the West Newton
site: substations, GSPs (Creyke Beck, Driffield/Beverley), 11/33/66 kV lines
and well spurs, offshore wind and cables, with grid-headroom / RAG status and
nearest-connection distances.

Self-contained: reads ``wn_infrastructure_map.html`` (Leaflet from a CDN, all
data embedded) and renders it via ``st.iframe``. No database, no secrets.

Prepared by RenewaBlox for Reabold — deploy GATED to the client's viewers,
not public. Run locally:  streamlit run app_wn_infrastructure.py
"""
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="WN Infrastructure Map",
    page_icon=":material/map:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Read the map fresh from the main script each run (Streamlit re-runs this
# script but can keep imported modules cached, so reading here keeps the
# embedded map current after every redeploy). The HTML carries its own map,
# control panel and legend, so the Streamlit chrome stays minimal.
WN_HTML = (Path(__file__).resolve().parent / "wn_infrastructure_map.html").read_text(
    encoding="utf-8")

st.iframe(WN_HTML, height=860)
st.caption(
    "Prepared by RenewaBlox · West Newton infrastructure map · "
    "contact callum@renewablox.com")
