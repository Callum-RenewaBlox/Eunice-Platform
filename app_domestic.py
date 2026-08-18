"""Eunice Domestic — a clean, consumer-facing tool for households comparing their fixed tariff
vs switching to a half-hourly (Agile-style) RenewaBlox Solution with load-shifting.

Same backend + shared slim DB as Eunice / Eunice-lite (reads the AGILE slice). Deploy as a
SEPARATE public Streamlit Cloud app pointing at this file.

Differences vs Eunice-lite:
  - Domestic prices (AGILE) + £50 domestic signup bonus
  - Load-shift bar STARTS AT 0%
  - Guided usage estimator: Low / Medium / High typical-use bands (Ofgem TDCV), then tickable
    appliances (dishwasher / washing machine / tumble dryer; EV for Med+/High; heat pump for
    High) that auto-move the shift bar to the share of annual use moved out of the 4–7pm peak
  - Domestic plug-in discharge capped at 800 W (13A socket)
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

# Use the slim, normal-file DB when present (Streamlit Cloud can't read Git LFS). Must run
# before importing config/db so config.DB_PATH picks it up.
_lite_db = Path(__file__).resolve().parent / "data_lite.sqlite"
if _lite_db.exists():
    os.environ["EUNICE_DB_PATH"] = str(_lite_db)

from config import REGION, REGION_NAMES
from db import conn
from octopus import fetch_agile_rates
from region_lookup import lookup_region
from scenarios import apply_load_shift, compute_scenario, get_mean_agile_by_hour, get_profile
import staged_flags

DISPLAY_TZ = "Europe/London"
PRODUCT = "AGILE"                   # domestic only
DISCHARGE_KW = 0.8                  # UK 13A socket plug-in cap (domestic)
TOPCON_KWP_PER_PANEL = 0.210
ULTRA_KWH_PER_UNIT = 3.84
MAX_PANELS = 6
MAX_BATTERIES = 2
MIN_PANELS_WITH_BATTERY = 2
REFERRAL_URL = "https://share.octopus.energy/dull-brook-170"
DEFAULT_RATE_P = 24.5              # ~current domestic price-cap unit rate; the user can change it

# Guided usage model -----------------------------------------------------------------------------
# Ofgem Typical Domestic Consumption Values (electricity, single-rate), as used across the industry.
USAGE_BANDS = {"Low": 1800, "Medium": 2700, "High": 4100}   # kWh / year
# Everyday shiftable appliances — part of the base band usage; name -> (state key, annual kWh).
BASE_APPLIANCES = {
    "Dishwasher": ("dom_dish", 250),
    "Washing machine": ("dom_wash", 180),
    "Tumble dryer": ("dom_dry", 350),
}
EV_KWH = 2500             # additional annual load (≈8–9k miles); charging is fully shiftable overnight
HEATPUMP_KWH = 3000       # additional annual load
HEATPUMP_SHIFT_FRAC = 0.5  # only part of heating is realistically moved off the evening peak

st.set_page_config(page_title="Eunice Domestic — RenewaBlox", layout="wide")


# ─────────────────────────────────────────────────────────────────────────────
# Header: title + £50 domestic signup bonus
# ─────────────────────────────────────────────────────────────────────────────
head_l, head_r = st.columns([3, 1])
with head_l:
    st.title("Eunice Domestic")
    st.caption("See what your home could save by switching from a fixed tariff to a smart, "
               "half-hourly RenewaBlox Solution — and shifting use out of the evening peak.")
with head_r:
    st.write("")
    st.link_button(
        "🎁 £50 domestic signup bonus",
        REFERRAL_URL,
        help="Sign up via this RenewaBlox referral link to claim the bonus credit on your first bill.",
        type="primary",
        width="stretch",
    )

# ─────────────────────────────────────────────────────────────────────────────
# Region (postcode-friendly; drives region-specific prices)
# ─────────────────────────────────────────────────────────────────────────────
if "dom_region" not in st.session_state:
    st.session_state["dom_region"] = REGION


def _on_postcode():
    q = st.session_state.get("dom_postcode", "")
    if q:
        matched = lookup_region(q)
        if matched:
            st.session_state["dom_region"] = matched


reg_l, reg_r = st.columns([2, 3])
with reg_l:
    st.text_input(
        "Your postcode (optional)",
        key="dom_postcode",
        on_change=_on_postcode,
        placeholder="e.g. SA1 1AA",
        help="Sets your local grid region so the prices match your area.",
    )
region = st.session_state["dom_region"]
with reg_r:
    st.write("")
    st.caption(f"📍 Region: **{region} — {REGION_NAMES[region]}**")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# SAVINGS CALCULATOR (top of page)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("💷 Your savings calculator")

# Initial state (a fresh page load = a new session, so these defaults apply on every refresh).
st.session_state.setdefault("dom_band", "Medium")
st.session_state.setdefault("dom_kwh", USAGE_BANDS["Medium"])
st.session_state.setdefault("dom_shift", 0)
for _key, _ in BASE_APPLIANCES.values():
    st.session_state.setdefault(_key, False)
st.session_state.setdefault("dom_ev", False)
st.session_state.setdefault("dom_hp", False)
st.session_state.setdefault("dom_solar", 0)
st.session_state.setdefault("dom_batt", 0)


def _recompute():
    """Derive annual usage + the load-shift % from the chosen band and ticked appliances.
    EV and heat pump add their full load to annual use; the shiftable share moves the bar."""
    band = st.session_state.get("dom_band", "Medium")
    annual = float(USAGE_BANDS[band])
    shifted = sum(kwh for _name, (key, kwh) in BASE_APPLIANCES.items() if st.session_state.get(key))
    # EV/heat pump only apply at the relevant bands; clear them otherwise so hidden ticks don't linger.
    if band == "Low":
        st.session_state["dom_ev"] = False
    if band != "High":
        st.session_state["dom_hp"] = False
    if band in ("Medium", "High") and st.session_state.get("dom_ev"):
        annual += EV_KWH
        shifted += EV_KWH
    if band == "High" and st.session_state.get("dom_hp"):
        annual += HEATPUMP_KWH
        shifted += HEATPUMP_KWH * HEATPUMP_SHIFT_FRAC
    st.session_state["dom_kwh"] = int(annual)
    st.session_state["dom_shift"] = int(min(100, round(shifted / annual * 100))) if annual else 0


def _enforce_min_solar():
    if (st.session_state.get("dom_batt") or 0) >= 1 and (st.session_state.get("dom_solar") or 0) < MIN_PANELS_WITH_BATTERY:
        st.session_state["dom_solar"] = MIN_PANELS_WITH_BATTERY


# --- Current rate ---
rate_col, use_col = st.columns(2)
with rate_col:
    rate = st.number_input(
        "Your current tariff rate (p/kWh)",
        min_value=0.0, max_value=200.0, value=DEFAULT_RATE_P, step=0.01,
        key="dom_rate",
        help="The unit rate you pay today. Default is roughly the current price-cap rate — "
             "enter your own for an accurate comparison.",
    )
    st.caption(
        "📊 Check your rate: [Ofgem price cap](https://www.ofgem.gov.uk/energy-price-cap) · "
        "[Uswitch](https://www.uswitch.com/gas-electricity/guides/average-gas-and-electricity-bills-in-the-uk/)"
    )

# --- Typical usage band ---
with use_col:
    st.radio(
        "Typical household electricity use",
        options=list(USAGE_BANDS.keys()),
        horizontal=True,
        key="dom_band",
        on_change=_recompute,
        help="Ofgem typical values — Low ≈ 1,800 · Medium ≈ 2,700 · High ≈ 4,100 kWh/year. "
             "Pick the closest; you can fine-tune the kWh below.",
    )
    annual_kwh = st.number_input(
        "Annual usage (kWh)",
        min_value=0, max_value=60000, step=100,
        key="dom_kwh",
        help="Auto-filled from your band (plus any EV / heat pump). Edit if you know your exact figure.",
    )

# --- Shiftable loads ---
st.markdown("**Which loads could you run off-peak?**  Tick them — we'll shift them out of the 4–7pm peak.")
app_cols = st.columns(3)
for (label, (key, kwh)), col in zip(BASE_APPLIANCES.items(), app_cols):
    with col:
        st.checkbox(f"{label} (~{kwh} kWh/yr)", key=key, on_change=_recompute)

extra_cols = st.columns(2)
band = st.session_state["dom_band"]
with extra_cols[0]:
    if band in ("Medium", "High"):
        st.checkbox(f"🔌 EV charging (~{EV_KWH:,} kWh/yr)", key="dom_ev", on_change=_recompute,
                    help="Charging shifts fully to cheap overnight hours. Adds to your annual use.")
with extra_cols[1]:
    if band == "High":
        st.checkbox(f"♨️ Heat pump (~{HEATPUMP_KWH:,} kWh/yr)", key="dom_hp", on_change=_recompute,
                    help="Pre-heating / buffering moves roughly half the heating load off the evening peak. "
                         "Adds to your annual use.")

# --- Shift bar (auto-set by the ticks above; still manually adjustable) + solar + battery ---
cfg_shift, cfg_solar, cfg_batt = st.columns([2, 1, 1])
with cfg_shift:
    shift_pct_pct = st.slider(
        "% of annual use shifted out of the 4–7pm peak",
        min_value=0, max_value=100, step=1,
        key="dom_shift",
        help="Auto-set from the loads you ticked above. Drag to explore shifting more (or less).",
    )
with cfg_solar:
    solar_panels = st.number_input(
        "Solar panels", min_value=0, max_value=MAX_PANELS, step=1,
        key="dom_solar", on_change=_enforce_min_solar,
        help=f"TopCon bifacial, 210 W each. Up to {MAX_PANELS}.",
    )
    solar_kwp = solar_panels * TOPCON_KWP_PER_PANEL
    st.caption(f"= **{solar_kwp:.2f} kWp**" if solar_panels else "No solar")
with cfg_batt:
    batt_units = st.number_input(
        "Batteries", min_value=0, max_value=MAX_BATTERIES, step=1,
        key="dom_batt", on_change=_enforce_min_solar,
        help=f"STREAM Ultra, 3.84 kWh each. Up to {MAX_BATTERIES}. Selecting one switches at least "
             f"{MIN_PANELS_WITH_BATTERY} panels on.",
    )
    battery_kwh = batt_units * ULTRA_KWH_PER_UNIT
    st.caption(f"= **{battery_kwh:.2f} kWh**" if batt_units else "No battery")

# --- Scenario table ---
if rate > 0 and annual_kwh > 0:
    mean_tariff = get_mean_agile_by_hour(region, PRODUCT)
    profile = get_profile(PRODUCT)
    shifted_profile = apply_load_shift(profile, shift_pct_pct / 100.0)

    rows = [{
        "label": f"Switch to RenewaBlox Solution — shift {shift_pct_pct}% off-peak",
        **compute_scenario(annual_kwh, rate, mean_tariff, shifted_profile),
    }]
    if solar_kwp > 0:
        rows.append({
            "label": f"+ {solar_panels} solar panels ({solar_kwp:.2f} kWp)",
            **compute_scenario(annual_kwh, rate, mean_tariff, shifted_profile, solar_kwp=solar_kwp),
        })
    if battery_kwh > 0:
        rows.append({
            "label": f"+ {batt_units} STREAM Ultra battery ({battery_kwh:.2f} kWh)",
            **compute_scenario(annual_kwh, rate, mean_tariff, shifted_profile,
                               solar_kwp=solar_kwp, battery_kwh=battery_kwh, discharge_power_kw=DISCHARGE_KW),
        })

    md = "| Scenario | Cost / yr now | Cost / yr — RenewaBlox | You save / yr | Saving % |\n"
    md += "| --- | ---: | ---: | ---: | ---: |\n"
    for s in rows:
        md += (f"| {s['label']} | £{s['fixed_cost']:,.0f} | £{s['agile_net']:,.0f} "
               f"| **£{s['saving']:,.0f}** | {s['saving_pct']:.0f}% |\n")
    st.markdown(md)
    st.caption(
        "Cumulative scenarios for a typical UK domestic load profile, using historical half-hourly prices "
        "for your region. Consumption-only (no export value). Solar yield ~950 kWh/kWp/yr × 1.06 TopCon uplift; "
        "battery discharge capped at 800 W (13A plug-in). Excludes standing charge. Illustrative — real savings vary."
    )
else:
    st.info("👆 Enter your **current rate** and pick a **usage band** to see your savings.")

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# PRICE CHART (below calculator). Renders on every load — no refresh button.
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data(region, product):
    with conn() as c:
        tariff = pd.read_sql_query(
            "SELECT valid_from, value_inc_vat FROM tariff WHERE region = ? AND product = ? ORDER BY valid_from",
            c, params=(region, product),
        )
        try:
            preds_all = pd.read_sql_query(
                "SELECT valid_from, predicted_price, p05, p10, p25, p50, p75, p90, p95, "
                "p_neg, p_sub5, p_sub10, p_hi40, lead_days, generated_at, model_version "
                "FROM prediction WHERE region = ? AND product = ?",
                c, params=(region, product),
            )
        except Exception:
            # Deployed DB predates the rebuilt-engine schema (no p_neg/p_sub5/... columns yet).
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
    """Pull the latest published rates from the source so the live line + Now/Next are always
    current. Public endpoint, no key needed."""
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

live = fetch_live_tariff(region, PRODUCT)
if not live.empty:
    tariff = (
        pd.concat([tariff, live], ignore_index=True)
        .drop_duplicates("valid_from", keep="last")
        .sort_values("valid_from")
        .reset_index(drop=True)
    )

if tariff.empty:
    st.warning(f"No domestic tariff data for region {region} yet.")
    st.stop()

now = pd.Timestamp.now(tz="UTC")
horizon_end = now + pd.Timedelta(days=7)

if not preds_all.empty:
    latest_model = preds_all.sort_values("generated_at")["model_version"].iloc[-1]
    preds = preds_all[preds_all["model_version"] == latest_model]
    forward = preds[preds["generated_at"] == preds["generated_at"].max()]
else:
    forward = pd.DataFrame()

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
        f"The green dashed line is your current rate ({rate:.2f} p/kWh). Wherever the blue/orange price "
        "sits below it, the half-hourly RenewaBlox Solution is cheaper than what you pay now — and you can "
        "run flexible loads (dishwasher, EV, etc.) in those cheaper windows."
    )

# === Staged low-price flags (rebuilt engine) ===
if not predicted.empty and staged_flags.has_flag_data(predicted):
    _flag_xs = ([*known["x"]] if not known.empty else []) + [*predicted["x"]]
    staged_flags.render(predicted, x_range=[min(_flag_xs), max(_flag_xs)] if _flag_xs else None)
_latest = to_local_one(tariff["valid_from"].iloc[-1])
st.caption(f"📡 Latest published slot: **{_latest.strftime('%a %d %b %H:%M')}** (London) · live prices update automatically.")

if not forward.empty:
    pred_gen = to_local_one(forward["generated_at"].max())
    pred_to = to_local_one(forward["valid_from"].max())
    if pred_to < to_local_one(now):
        st.warning(
            f"⚠️ The 7-day forecast was last generated **{pred_gen:%a %d %b}** and only extends to "
            f"**{pred_to:%a %d %b}** — the daily refresh may have failed. Live prices above are still current."
        )
    else:
        st.caption(f"🔮 Forecast generated **{pred_gen:%a %d %b %H:%M}**, covering through **{pred_to:%a %d %b}** (London).")
