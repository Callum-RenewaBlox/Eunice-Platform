"""SRV Atlas — Scrivelsby (Home Farm AD) electrical site survey.

A standalone Leaflet site-survey map of the Home Farm AD site at Scrivelsby
(LN9 6JB, operator Qila Energy): site assets (CHP, transformer, LV switchroom,
proposed data centre), geolocated site photos, and grid/site context.

Self-contained: reads ``srv_atlas.html`` (Leaflet from a CDN, all data and
photos embedded) and renders it via ``st.iframe``. No database, no secrets.

Public tool. Run locally:  streamlit run app_srv_atlas.py
"""
import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="SRV Atlas",
    page_icon=":material/map:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Read the map fresh from the main script each run (Streamlit re-runs this
# script but can keep imported modules cached, so reading here keeps the
# embedded map current after every redeploy). The HTML carries its own brand
# bar, map, layer controls and legend, so the Streamlit chrome stays minimal.
SRV_HTML = (Path(__file__).resolve().parent / "srv_atlas.html").read_text(
    encoding="utf-8")

st.iframe(SRV_HTML, height=880)
st.caption(
    "RenewaBlox · Scrivelsby Atlas — Home Farm AD electrical site survey · "
    "contact callum@renewablox.com")
