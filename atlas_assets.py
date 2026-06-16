"""Self-contained HTML asset for Eunice Atlas (app_atlas.py).

The map is a standalone Leaflet page (``atlas.html``) rendered via
``st.iframe`` inside a sandboxed iframe, so it carries its own
styles and pulls Leaflet from a CDN.

Unlike ``heatx_assets.py`` (which inlines its HTML as a Python string), the
Atlas is kept as a sibling ``atlas.html`` file because it embeds the full
site dataset (~300 records). As real HTML it stays easy to edit, diff and
regenerate, and it can still be opened directly in a browser on its own.

To add a new layer/tab of data, edit ``atlas.html``:
  1. Add a data array next to ``HYDRO`` / ``PEAKER`` (e.g. ``SOLAR=[...]``).
  2. Add one entry to the ``ATLAS`` config object (see the existing
     ``hydro`` / ``peaker`` entries) with a ``label`` plus ``data``,
     ``center``, ``zoom``, ``univ``, ``ftitle``, ``fmuted``, ``legtitle``,
     ``legend``, ``colour``, ``ok`` and ``popup``.
The tab buttons are generated from that object, so nothing else changes.
"""
from pathlib import Path


def load_atlas_html():
    """Read ``atlas.html`` fresh on every call.

    Deliberately a function, not a module-level constant: Streamlit reruns
    the *main* script but keeps imported modules cached, so a constant here
    would go stale after a redeploy that only changes ``atlas.html`` — the
    sidebar would update but the embedded map would not. Reading on each
    call (from the main script) keeps the map current without a reboot.
    """
    return (Path(__file__).resolve().parent / "atlas.html").read_text(
        encoding="utf-8")
