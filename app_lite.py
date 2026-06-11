"""Eunice-lite — a stripped-back, commercial-only partner tool.

Same data + model backend as Eunice (reads the shared data.sqlite), but a simplified, guided
UI for non-specialist partners to show SME clients their savings. Deploy as a SEPARATE Streamlit
Cloud app pointing at this file (app_lite.py) — it shares the repo + database with the full app.

Differences vs the full Eunice (app.py):
  - Commercial only (no domestic toggle)
  - Savings calculator sits at the TOP; chart below
  - Linked rate / annual-cost / annual-kWh inputs (enter any two, the third is derived)
  - Solar (TopCon, 0-6 panels) + STREAM Ultra battery (0-2 units) only; discharge fixed at 1200 W
  - Heating-shift slider clamped to 30-100%
  - Scenario table starts at the RenewaBlox-solution (shift) line — no "no behaviour change" row
  - No manual refresh button: latest data renders on every page load
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Bridge Streamlit Cloud secrets → env vars before importing config (same pattern as app.py).
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except (FileNotFoundError, Exception):
    pass

# Point the data layer at the slim, normal-file database when present. Streamlit Cloud does NOT
# pull Git LFS, so the full LFS-tracked data.sqlite isn't readable there — data_lite.sqlite
# (committed as a normal git file) is. Falls back to data.sqlite for local dev if absent.
# Must run before importing config/db so config.DB_PATH picks it up.
_lite_db = Path(__file__).resolve().parent / "data_lite.sqlite"
if _lite_db.exists():
    os.environ["EUNICE_DB_PATH"] = str(_lite_db)

from config import REGION, REGION_NAMES, ALL_REGIONS
from db import conn
from octopus import fetch_agile_rates
from region_lookup import lookup_region
from scenarios import (
    apply_load_shift,
    compute_scenario,
    get_mean_agile_by_hour,
    get_profile,
)

DISPLAY_TZ = "Europe/London"
PRODUCT = "SHAPE_SHIFTERS"          # commercial only — never changes
DISCHARGE_KW = 1.2                  # fixed 1200 W (16A commando plug) — no other options
TOPCON_KWP_PER_PANEL = 0.210        # each TopCon bifacial panel = 210 W
ULTRA_KWH_PER_UNIT = 3.84           # each STREAM Ultra module = 3.84 kWh
MAX_PANELS = 6
MAX_BATTERIES = 2
MIN_PANELS_WITH_BATTERY = 2
REFERRAL_URL = "https://share.octopus.energy/dull-brook-170"

st.set_page_config(page_title="Eunice-lite — RenewaBlox", layout="wide")


# ─────────────────────────────────────────────────────────────────────────────
# Header: title + £75 commercial signup bonus
# ─────────────────────────────────────────────────────────────────────────────
head_l, head_r = st.columns([3, 1])
with head_l:
    st.title("Eunice-lite")
    st.caption("Commercial savings calculator — see what your business could save with the RenewaBlox Solution.")
with head_r:
    st.write("")
    st.link_button(
        "🎁 £75 commercial signup bonus",
        REFERRAL_URL,
        help="Sign up via this RenewaBlox referral link to claim the bonus credit on your first bill.",
        type="primary",
        width="stretch",
    )

# ─────────────────────────────────────────────────────────────────────────────
# Region (drives region-specific tariff prices). Postcode-friendly for partners,
# defaults to South Wales. Auto-applies on change — no submit button.
# ─────────────────────────────────────────────────────────────────────────────
if "lite_region" not in st.session_state:
    st.session_state["lite_region"] = REGION


def _on_postcode():
    q = st.session_state.get("lite_postcode", "")
    if q:
        matched = lookup_region(q)
        if matched:
            st.session_state["lite_region"] = matched


reg_l, reg_r = st.columns([2, 3])
with reg_l:
    st.text_input(
        "Client postcode (optional)",
        key="lite_postcode",
        on_change=_on_postcode,
        placeholder="e.g. SA1 1AA",
        help="Sets the local grid region so the prices match the client's area. Defaults to South Wales.",
    )
region = st.session_state["lite_region"]
with reg_r:
    st.write("")
    st.caption(f"📍 Region: **{region} — {REGION_NAMES[region]}**")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT SAVINGS CALCULATOR (top of page)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("💷 Client savings calculator")

# Linked inputs: rate (p/kWh) × kWh = cost (pence) → £. Enter any two, derive the third.
for _k in ("lite_rate", "lite_cost", "lite_kwh"):
    st.session_state.setdefault(_k, None)


def _sync_from_cost():
    rate = st.session_state.get("lite_rate") or 0
    cost = st.session_state.get("lite_cost") or 0
    if rate > 0 and cost > 0:
        st.session_state["lite_kwh"] = float(round(cost * 100.0 / rate))


def _sync_from_kwh():
    rate = st.session_state.get("lite_rate") or 0
    kwh = st.session_state.get("lite_kwh") or 0
    if rate > 0 and kwh > 0:
        st.session_state["lite_cost"] = float(round(kwh * rate / 100.0, 2))


def _sync_from_rate():
    rate = st.session_state.get("lite_rate") or 0
    kwh = st.session_state.get("lite_kwh") or 0
    cost = st.session_state.get("lite_cost") or 0
    if rate > 0:
        # Keep the physical quantity (kWh) fixed if we have it; otherwise back out kWh from cost.
        if kwh > 0:
            st.session_state["lite_cost"] = float(round(kwh * rate / 100.0, 2))
        elif cost > 0:
            st.session_state["lite_kwh"] = float(round(cost * 100.0 / rate))


rate_col, amount_col = st.columns(2)
with rate_col:
    st.number_input(
        "Current tariff rate (p/kWh)",
        min_value=0.0, max_value=200.0, step=0.01,
        key="lite_rate", on_change=_sync_from_rate,
        placeholder="e.g. 26.50",
        help="The unit rate the client pays today. Drives both the savings table and the comparison line on the chart.",
    )
    st.caption(
        "📊 Check live SME rates: "
        "[AquaSwitch](https://www.aquaswitch.co.uk/business-electricity-prices/) · "
        "[BusinessElectricityPrices.org.uk](https://www.businesselectricityprices.org.uk/)"
    )
with amount_col:
    st.number_input(
        "Cost / annum (£)",
        min_value=0.0, max_value=100_000_000.0, step=100.0,
        key="lite_cost", on_change=_sync_from_cost,
        placeholder="e.g. 13,000",
        help="The client's total annual electricity spend. Enter this with the rate and we'll work out their annual kWh.",
    )
    st.number_input(
        "Annual consumption (kWh)",
        min_value=0.0, max_value=500_000_000.0, step=500.0,
        key="lite_kwh", on_change=_sync_from_kwh,
        placeholder="auto-calculated, or enter directly",
        help="Auto-calculated from rate + cost. Or enter it directly and we'll work out the annual cost.",
    )

rate = st.session_state.get("lite_rate") or 0
annual_kwh = st.session_state.get("lite_kwh") or 0

# System configuration: solar, battery, heating shift -------------------------------------------
# Defaults (0 / 0 / 30%) apply on every fresh page load because a browser refresh starts a new
# Streamlit session with empty state.
st.session_state.setdefault("lite_solar", 0)
st.session_state.setdefault("lite_batt", 0)


def _enforce_min_solar():
    """A battery needs somewhere to charge from — selecting one forces at least 2 panels on."""
    batt = st.session_state.get("lite_batt") or 0
    solar = st.session_state.get("lite_solar") or 0
    if batt >= 1 and solar < MIN_PANELS_WITH_BATTERY:
        st.session_state["lite_solar"] = MIN_PANELS_WITH_BATTERY


cfg_solar, cfg_batt, cfg_shift = st.columns([1, 1, 2])
with cfg_solar:
    solar_panels = st.number_input(
        "TopCon solar panels", min_value=0, max_value=MAX_PANELS, step=1,
        key="lite_solar", on_change=_enforce_min_solar,
        help=f"TopCon bifacial, 210 W each. Up to {MAX_PANELS} panels.",
    )
    solar_kwp = solar_panels * TOPCON_KWP_PER_PANEL
    st.caption(f"= **{solar_kwp:.2f} kWp**" if solar_panels else "No solar")
with cfg_batt:
    batt_units = st.number_input(
        "STREAM Ultra batteries", min_value=0, max_value=MAX_BATTERIES, step=1,
        key="lite_batt", on_change=_enforce_min_solar,
        help=f"STREAM Ultra, 3.84 kWh each. Up to {MAX_BATTERIES} units. Selecting one switches at least {MIN_PANELS_WITH_BATTERY} panels on.",
    )
    battery_kwh = batt_units * ULTRA_KWH_PER_UNIT
    st.caption(f"= **{battery_kwh:.2f} kWh**" if batt_units else "No battery")
with cfg_shift:
    shift_pct_pct = st.slider(
        "Heating load % shifted out of the 4–7pm peak",
        min_value=30, max_value=100, value=30, step=5,
        key="lite_shift",
        help=(
            "Share of evening-peak heating moved to pre-heat (3–4pm) and catch-up (7–8pm). "
            "30% is a realistic floor with smart controls; higher needs thermal storage / buffer tanks."
        ),
    )

# Scenario table ---------------------------------------------------------------------------------
if rate > 0 and annual_kwh > 0:
    mean_tariff = get_mean_agile_by_hour(region, PRODUCT)
    profile = get_profile(PRODUCT)
    shifted = apply_load_shift(profile, shift_pct_pct / 100.0, target_hours=(15, 19))

    rows = [
        {
            "label": f"RenewaBlox Solution — shift {shift_pct_pct}% of heating peak",
            **compute_scenario(annual_kwh, rate, mean_tariff, shifted),
        },
    ]
    if solar_kwp > 0:
        rows.append({
            "label": f"+ {solar_panels} solar panels ({solar_kwp:.2f} kWp)",
            **compute_scenario(annual_kwh, rate, mean_tariff, shifted, solar_kwp=solar_kwp),
        })
    if battery_kwh > 0:
        rows.append({
            "label": f"+ {batt_units} STREAM Ultra battery ({battery_kwh:.2f} kWh)",
            **compute_scenario(annual_kwh, rate, mean_tariff, shifted,
                               solar_kwp=solar_kwp, battery_kwh=battery_kwh,
                               discharge_power_kw=DISCHARGE_KW),
        })

    md = "| Scenario | Cost / yr now | Cost / yr — RenewaBlox | You save / yr | Saving % |\n"
    md += "| --- | ---: | ---: | ---: | ---: |\n"
    for s in rows:
        md += (f"| {s['label']} | £{s['fixed_cost']:,.0f} | £{s['agile_net']:,.0f} "
               f"| **£{s['saving']:,.0f}** | {s['saving_pct']:.0f}% |\n")
    st.markdown(md)
    st.caption(
        "Cumulative scenarios for a typical SME load profile, using historical half-hourly prices for the "
        "selected region. Consumption-only (no export value). Solar yield ~950 kWh/kWp/yr × 1.06 TopCon uplift; "
        "battery discharge capped at 1200 W. Excludes standing charge. Real installs typically achieve 85–95% of these figures."
    )
else:
    st.info("👆 Enter the client's **current tariff rate** and either their **annual cost** or **annual kWh** to see the savings.")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# PRICE CHART (below calculator). Loads + renders on every run — no refresh button.
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data(region, product):
    with conn() as c:
        tariff = pd.read_sql_query(
            "SELECT valid_from, value_inc_vat FROM tariff WHERE region = ? AND product = ? ORDER BY valid_from",
            c, params=(region, product),
        )
        preds_all = pd.read_sql_query(
            "SELECT valid_from, predicted_price, p05, p10, p90, generated_at, model_version "
            "FROM prediction WHERE region = ? AND product = ?",
            c, params=(region, product),
        )
    if not tariff.empty:
        tariff["valid_from"] = pd.to_datetime(tariff["valid_from"], utc=True)
    if not preds_all.empty:
        preds_all["valid_from"] = pd.to_datetime(preds_all["valid_from"], utc=True)
        preds_all["generated_at"] = pd.to_datetime(preds_all["generated_at"], utc=True)
    return tariff, preds_all


@st.cache_data(ttl=1800)
def fetch_live_tariff(region, product):
    """Pull the most recent published rates straight from the source so the live/published
    line and the Now/Next prices are always current — the committed database is only a
    periodic snapshot, so on a hosted app it goes stale between data refreshes. Public
    endpoint, no key needed. Returns recent + current + any day-ahead published slots."""
    period_from = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        rows = fetch_agile_rates(region, product, period_from=period_from)
    except Exception:
        return pd.DataFrame(columns=["valid_from", "value_inc_vat"])
    if not rows:
        return pd.DataFrame(columns=["valid_from", "value_inc_vat"])
    df = pd.DataFrame(rows)[["valid_from", "value_inc_vat"]]
    df["valid_from"] = pd.to_datetime(df["valid_from"], utc=True)
    return df.sort_values("valid_from").reset_index(drop=True)


def to_local(series):
    return series.dt.tz_convert(DISPLAY_TZ).dt.tz_localize(None)


def to_local_one(ts):
    return ts.tz_convert(DISPLAY_TZ).tz_localize(None)


st.subheader("Live & predicted unit price")

tariff, preds_all = load_data(region, PRODUCT)

# Merge live published rates over the (possibly stale) snapshot so the blue line + Now/Next
# always reflect the current half-hour. Live rows win on overlap; DB still provides deep history.
live = fetch_live_tariff(region, PRODUCT)
if not live.empty:
    tariff = (
        pd.concat([tariff, live], ignore_index=True)
        .drop_duplicates("valid_from", keep="last")
        .sort_values("valid_from")
        .reset_index(drop=True)
    )

if tariff.empty:
    st.warning(f"No commercial tariff data for region {region} yet.")
    st.stop()

now = pd.Timestamp.now(tz="UTC")
horizon_end = now + pd.Timedelta(days=7)

# Pick the latest model run for the forward predictions
if not preds_all.empty:
    latest_model = preds_all.sort_values("generated_at")["model_version"].iloc[-1]
    preds = preds_all[preds_all["model_version"] == latest_model]
    forward = preds[preds["generated_at"] == preds["generated_at"].max()]
else:
    forward = pd.DataFrame()

# Current settlement metric
cur_start = now.floor("30min")
nxt_start = cur_start + pd.Timedelta(minutes=30)
current_slot = tariff[tariff["valid_from"] == cur_start]
next_slot = tariff[tariff["valid_from"] == nxt_start]

m1, m2, m3 = st.columns([2, 2, 3])
with m1:
    if not current_slot.empty:
        st.metric(f"Now · {to_local_one(cur_start).strftime('%H:%M')}–{to_local_one(nxt_start).strftime('%H:%M')}",
                  f"{current_slot.iloc[0]['value_inc_vat']:.2f} p")
    else:
        st.metric("Now", "—")
with m2:
    if not next_slot.empty:
        st.metric(f"Next · {to_local_one(nxt_start).strftime('%H:%M')}–{to_local_one(nxt_start + pd.Timedelta(minutes=30)).strftime('%H:%M')}",
                  f"{next_slot.iloc[0]['value_inc_vat']:.2f} p")
    else:
        st.metric("Next", "—", help="Day-ahead settlement is published ~4pm.")
with m3:
    next_ms = int(nxt_start.timestamp() * 1000)
    components.html(
        f"""
<div style='font-family:-apple-system,system-ui,sans-serif;padding-top:4px;'>
  <div style='font-size:14px;color:#6b7280;'>Next settlement in</div>
  <div id='cd' style='font-size:32px;font-weight:600;color:#2563eb;line-height:1.1;margin-top:2px;'>--</div>
</div>
<script>
(function(){{
  const target={next_ms};const el=document.getElementById('cd');
  function tick(){{const d=target-Date.now();
    if(d<=0){{el.textContent="now — refresh page";el.style.color="#dc2626";return;}}
    const m=Math.floor(d/60000),s=Math.floor((d%60000)/1000);
    el.textContent=m+"m "+String(s).padStart(2,"0")+"s";}}
  tick();setInterval(tick,1000);
}})();
</script>
""",
        height=80,
    )

known = tariff[(tariff["valid_from"] >= now - pd.Timedelta(hours=1)) & (tariff["valid_from"] < horizon_end)].copy()
predicted = (
    forward[(~forward["valid_from"].isin(known["valid_from"])) & (forward["valid_from"] >= now - pd.Timedelta(hours=1))].copy()
    if not forward.empty else pd.DataFrame()
)
if not known.empty:
    known["x"] = to_local(known["valid_from"])
if not predicted.empty:
    predicted["x"] = to_local(predicted["valid_from"])

fig = go.Figure()
if not known.empty:
    fig.add_trace(go.Scatter(
        x=known["x"], y=known["value_inc_vat"], mode="lines",
        name="Published", line=dict(color="#2563eb", width=2),
    ))
if not predicted.empty:
    if "p05" in predicted.columns and predicted["p05"].notna().any():
        lower_band, band_label = predicted["p05"], "P05–P90"
    else:
        lower_band, band_label = predicted["p10"], "P10–P90"
    if predicted["p90"].notna().any():
        fig.add_trace(go.Scatter(
            x=list(predicted["x"]) + list(predicted["x"][::-1]),
            y=list(predicted["p90"]) + list(lower_band[::-1]),
            fill="toself", fillcolor="rgba(245,158,11,0.15)",
            line=dict(color="rgba(0,0,0,0)"), name=band_label, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=predicted["x"], y=predicted["predicted_price"], mode="lines",
        name="Predicted", line=dict(color="#f59e0b", width=2, dash="dot"),
    ))

# Client's current rate as a horizontal comparison line — present once the rate is entered.
if rate > 0:
    line_x = []
    if not known.empty:
        line_x += list(known["x"])
    if not predicted.empty:
        line_x += list(predicted["x"])
    if line_x:
        fig.add_trace(go.Scatter(
            x=[min(line_x), max(line_x)], y=[rate, rate], mode="lines",
            name=f"Your rate ({rate:.2f} p)",
            line=dict(color="#10b981", width=2, dash="dash"),
            hovertemplate=f"Your current rate: {rate:.2f} p/kWh<extra></extra>",
        ))

# Zero / free reference when the band approaches negative pricing
if not predicted.empty and lower_band.min() < 2:
    fig.add_hline(y=0, line_dash="dot", line_color="rgba(16,185,129,0.5)",
                  annotation_text="£0 / free", annotation_position="bottom right",
                  annotation_font_color="#10b981", annotation_font_size=10)

if not current_slot.empty:
    cur_x = to_local_one(cur_start)
    fig.add_trace(go.Scatter(
        x=[cur_x], y=[float(current_slot.iloc[0]["value_inc_vat"])],
        mode="markers", name="Now",
        marker=dict(size=14, color="#dc2626", line=dict(color="white", width=2)),
        hovertemplate=f"Now · {current_slot.iloc[0]['value_inc_vat']:.2f} p<extra></extra>",
    ))
    fig.add_vline(x=cur_x, line_dash="dot", line_color="rgba(220,38,38,0.5)")

fig.update_layout(
    height=460,
    xaxis=dict(tickformat="%a %d %b\n%H:%M", title=None, showgrid=True),
    yaxis_title="Unit price (p/kWh)",
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.18, x=0),
    margin=dict(t=20, b=70),
)
st.plotly_chart(fig, width="stretch")

if rate > 0:
    st.caption(
        f"The green dashed line is the client's current rate ({rate:.2f} p/kWh). Wherever the blue/orange "
        "price sits below it, the RenewaBlox Solution is cheaper than what they pay today."
    )
_latest = to_local_one(tariff["valid_from"].iloc[-1])
st.caption(f"📡 Latest published slot: **{_latest.strftime('%a %d %b %H:%M')}** (London) · data refreshes automatically.")
