import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Bridge Streamlit Cloud secrets → environment variables so config.py (which is also imported
# by the headless GitHub Actions ingest) can keep reading credentials the same way it does
# locally via .env. Runs before any config import so the values are present when config loads.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except (FileNotFoundError, Exception):
    # No secrets.toml present (local dev with .env, or first-run on Cloud before secrets set).
    # config.py's dotenv loader handles the local-dev case.
    pass

from config import ALL_REGIONS, DEFAULT_PRODUCT, PRODUCTS, REGION, REGION_NAMES
from db import conn
from region_lookup import lookup_region

DISPLAY_TZ = "Europe/London"

st.set_page_config(page_title="Eunice — RenewaBlox", layout="wide")

st.title("Eunice")
st.caption("**E**nergy **U**tilisation, **N**etwork **I**nsight & **C**omparison **E**ngine")
st.divider()

REGION_OPTIONS = [f"{r} — {REGION_NAMES[r]}" for r in ALL_REGIONS]
PRODUCT_KEYS = list(PRODUCTS.keys())

# Session state defaults
if "region_select" not in st.session_state:
    st.session_state["region_select"] = f"{REGION} — {REGION_NAMES[REGION]}"
if "product_select" not in st.session_state:
    st.session_state["product_select"] = "SHAPE_SHIFTERS"


def _on_location_submit():
    q = st.session_state.get("location_input", "")
    if q:
        matched = lookup_region(q)
        if matched:
            st.session_state["region_select"] = f"{matched} — {REGION_NAMES[matched]}"


# === Tariff toggle (top of page) ===
product_cols = st.columns([3, 1])
with product_cols[0]:
    product = st.radio(
        "Tariff",
        options=PRODUCT_KEYS,
        format_func=lambda k: PRODUCTS[k]["label"],
        horizontal=True,
        key="product_select",
        help="Switch between the Domestic and Commercial RenewaBlox Solution.",
    )
with product_cols[1]:
    seg = PRODUCTS[product]["segment"]
    st.caption(f"**{seg}**")


def _on_client_rate_change():
    """When the client enters a rate at the top of the page, cascade it into the savings
    calculator's fixed-rate input. Leaves the calculator alone if the top box is cleared."""
    rate = st.session_state.get("client_fixed_rate")
    if rate is not None:
        st.session_state["calc_fixed_price"] = float(rate)


client_fixed_rate = st.number_input(
    "Your current fixed electricity rate (p/kWh)",
    min_value=1.0, max_value=80.0, value=None, step=0.01,
    key="client_fixed_rate",
    on_change=_on_client_rate_change,
    placeholder="e.g. 26.50",
    help=(
        "Enter the unit rate you currently pay on your fixed tariff to overlay it as a "
        "horizontal reference line on the price chart below and drive the savings comparison. "
        "Leave blank to use the market-default rate (25p domestic / 26p commercial)."
    ),
)

st.divider()

# === Region + location + refresh ===
header_cols = st.columns([2, 2, 2, 1])
with header_cols[0]:
    st.title("7-Day Tariff Forecast")
with header_cols[1]:
    selected_region_label = st.selectbox(
        "GSP region",
        REGION_OPTIONS,
        key="region_select",
        help="14 GB distribution regions. Same national wholesale price; per-region DUoS + supplier formula produce different unit prices.",
    )
    region = selected_region_label.split(" — ")[0]
with header_cols[2]:
    location_query = st.text_input(
        "Find by location",
        key="location_input",
        placeholder="e.g. Cardiff, BS1, Edinburgh",
        help="Type any UK city, town, county, or postcode and press Enter — the dropdown will snap to the matched region.",
        on_change=_on_location_submit,
    )
    if location_query:
        matched = lookup_region(location_query)
        if matched:
            st.caption(f"📍 Matched **{matched}** ({REGION_NAMES[matched]})")
        else:
            st.caption(f"⚠️ No match for '{location_query}'")
with header_cols[3]:
    st.write("")
    refresh_clicked = st.button(
        "🔄 Refresh data",
        width="stretch",
        help="Pull the latest market and weather data, retrain the model, and regenerate predictions (~30s).",
    )

st.caption(
    f"Tariff **{PRODUCTS[product]['label']}** · Region **{region}** ({REGION_NAMES[region]}) · "
    "Day 1 is the live RenewaBlox Solution settlement (published ~4pm); days 2–7 are Eunice model predictions. Times in Europe/London."
)

if refresh_clicked:
    with st.spinner("Pulling latest data + regenerating predictions…"):
        try:
            from db import init_db
            from ingest import (
                ingest_forecast,
                ingest_tariff,
                ingest_weather_history,
                run_predictions,
            )
            init_db()
            ingest_tariff(full=False)
            ingest_weather_history(full=False)
            ingest_forecast()
            run_predictions()
            st.cache_data.clear()
            st.toast("Data refreshed.", icon="✅")
            st.rerun()
        except Exception as e:
            st.error(f"Refresh failed: {e}")
            st.stop()


@st.cache_data(ttl=60)
def load_data(region, product):
    with conn() as c:
        tariff = pd.read_sql_query(
            "SELECT valid_from, value_inc_vat FROM tariff WHERE region = ? AND product = ? ORDER BY valid_from",
            c, params=(region, product),
        )
        forecast = pd.read_sql_query(
            "SELECT timestamp, temperature_c, wind_speed_kmh, cloud_cover_pct FROM weather_forecast ORDER BY timestamp", c
        )
        preds_all = pd.read_sql_query(
            "SELECT valid_from, predicted_price, p10, p90, p_spike, generated_at, model_version FROM prediction WHERE region = ? AND product = ?",
            c, params=(region, product),
        )
    if not tariff.empty:
        tariff["valid_from"] = pd.to_datetime(tariff["valid_from"], utc=True)
    if not forecast.empty:
        forecast["timestamp"] = pd.to_datetime(forecast["timestamp"], utc=True)
    if not preds_all.empty:
        preds_all["valid_from"] = pd.to_datetime(preds_all["valid_from"], utc=True)
        preds_all["generated_at"] = pd.to_datetime(preds_all["generated_at"], utc=True)
    return tariff, forecast, preds_all


def to_local(series):
    return series.dt.tz_convert(DISPLAY_TZ).dt.tz_localize(None)


def to_local_one(ts):
    return ts.tz_convert(DISPLAY_TZ).tz_localize(None)


def fmt_local(ts):
    return to_local_one(ts).strftime("%a %d %b %H:%M")


tariff, forecast, preds_all = load_data(region, product)

if tariff.empty:
    st.warning(
        f"No **{PRODUCTS[product]['label']}** tariff data for region **{region}** yet. "
        "Run `python ingest.py --full` to populate the database."
    )
    st.stop()

_latest_pub = to_local_one(tariff["valid_from"].iloc[-1])
st.caption(f"📡 Latest published slot: **{_latest_pub.strftime('%a %d %b %H:%M')}** (London) · auto-refresh scheduled daily at 16:35")

if not preds_all.empty:
    latest_model = preds_all.sort_values("generated_at")["model_version"].iloc[-1]
    preds = preds_all[preds_all["model_version"] == latest_model].copy()
else:
    latest_model = ""
    preds = pd.DataFrame()
forward = preds[preds["generated_at"] == preds["generated_at"].max()] if not preds.empty else pd.DataFrame()

now = pd.Timestamp.now(tz="UTC")
horizon_end = now + pd.Timedelta(days=7)

# Current and next half-hourly settlement periods
current_period_start = now.floor("30min")
next_period_start = current_period_start + pd.Timedelta(minutes=30)

current_slot = tariff[tariff["valid_from"] == current_period_start]
next_slot_row = tariff[tariff["valid_from"] == next_period_start]

# === Live section ===
live_cols = st.columns([2, 2, 3])

with live_cols[0]:
    if not current_slot.empty:
        cur = current_slot.iloc[0]
        cur_label = f"Now · {to_local_one(current_period_start).strftime('%H:%M')}–{to_local_one(next_period_start).strftime('%H:%M')}"
        st.metric(cur_label, f"{cur['value_inc_vat']:.2f} p")
    else:
        st.metric("Now", "—", help="No tariff for current half-hour. Run ingest.")

with live_cols[1]:
    if not next_slot_row.empty:
        nxt = next_slot_row.iloc[0]
        nxt_label = f"Next · {to_local_one(next_period_start).strftime('%H:%M')}–{to_local_one(next_period_start + pd.Timedelta(minutes=30)).strftime('%H:%M')}"
        st.metric(nxt_label, f"{nxt['value_inc_vat']:.2f} p")
    else:
        st.metric("Next", "—", help="Not yet published — day-ahead settlement is released at ~4pm.")

with live_cols[2]:
    next_ms = int(next_period_start.timestamp() * 1000)
    components.html(
        f"""
<div style='font-family: -apple-system, system-ui, sans-serif; padding-top: 4px;'>
  <div style='font-size: 14px; color: #6b7280;'>Next settlement in</div>
  <div id='cd' style='font-size: 32px; font-weight: 600; color: #2563eb; line-height: 1.1; margin-top: 2px;'>--</div>
</div>
<script>
(function() {{
  const target = {next_ms};
  const el = document.getElementById('cd');
  function tick() {{
    const diff = target - Date.now();
    if (diff <= 0) {{ el.textContent = "now — refresh page"; el.style.color = "#dc2626"; return; }}
    const m = Math.floor(diff / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    el.textContent = m + "m " + String(s).padStart(2, "0") + "s";
  }}
  tick();
  setInterval(tick, 1000);
}})();
</script>
""",
        height=80,
    )

# === Main forecast chart ===
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
    if "p10" in predicted.columns and predicted["p10"].notna().any():
        fig.add_trace(go.Scatter(
            x=list(predicted["x"]) + list(predicted["x"][::-1]),
            y=list(predicted["p90"]) + list(predicted["p10"][::-1]),
            fill="toself", fillcolor="rgba(245,158,11,0.15)",
            line=dict(color="rgba(0,0,0,0)"), name="P10–P90", hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=predicted["x"], y=predicted["predicted_price"], mode="lines",
        name="Predicted", line=dict(color="#f59e0b", width=2, dash="dot"),
    ))

if not current_slot.empty:
    cur_x = to_local_one(now)
    cur_price = float(current_slot.iloc[0]["value_inc_vat"])
    fig.add_trace(go.Scatter(
        x=[cur_x], y=[cur_price],
        mode="markers", name="Now",
        marker=dict(size=14, color="#dc2626", line=dict(color="white", width=2)),
        hovertemplate=f"Now · {cur_price:.2f} p<extra></extra>",
    ))
    fig.add_vline(x=cur_x, line_dash="dot", line_color="rgba(220,38,38,0.5)")

# Horizon zones — visual cue that days 5–7 are lower-confidence outlook, not point forecast
day1_end_local = to_local_one(now.floor("D") + pd.Timedelta(days=1))
day4_end_local = to_local_one(now.floor("D") + pd.Timedelta(days=4))
day7_end_local = to_local_one(now.floor("D") + pd.Timedelta(days=7))
fig.add_vrect(
    x0=day4_end_local, x1=day7_end_local,
    fillcolor="rgba(107,114,128,0.07)", layer="below", line_width=0,
)
fig.add_annotation(
    x=to_local_one(now + pd.Timedelta(hours=12)), y=1.04, xref="x", yref="paper",
    text="📡 Day 1: published", showarrow=False,
    font=dict(size=11, color="#2563eb"),
)
fig.add_annotation(
    x=to_local_one(now + pd.Timedelta(days=2.5)), y=1.04, xref="x", yref="paper",
    text="🎯 Days 2–4: forecast", showarrow=False,
    font=dict(size=11, color="#f59e0b"),
)
fig.add_annotation(
    x=to_local_one(now + pd.Timedelta(days=5.5)), y=1.04, xref="x", yref="paper",
    text="🌫 Days 5–7: lower confidence outlook", showarrow=False,
    font=dict(size=11, color="#6b7280"),
)

# Client's own fixed rate as a horizontal reference line (only when they've entered one).
# Spans the union of published + predicted x range so it covers the visible chart.
if client_fixed_rate is not None and client_fixed_rate > 0:
    _line_x = []
    if not known.empty:
        _line_x.extend(known["x"].tolist())
    if not predicted.empty:
        _line_x.extend(predicted["x"].tolist())
    if _line_x:
        fig.add_trace(go.Scatter(
            x=[min(_line_x), max(_line_x)],
            y=[client_fixed_rate, client_fixed_rate],
            mode="lines",
            name=f"Your fixed rate ({client_fixed_rate:.2f} p)",
            line=dict(color="#10b981", width=2, dash="dash"),
            hovertemplate=f"Your fixed rate: {client_fixed_rate:.2f} p/kWh<extra></extra>",
        ))

fig.update_layout(
    height=480,
    xaxis=dict(tickformat="%a %d %b\n%H:%M", title=None, showgrid=True),
    yaxis_title="Unit price (p/kWh, inc VAT)",
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.18, x=0),
    margin=dict(t=60, b=70),
)
st.plotly_chart(fig, width="stretch")

# === Compact stats ===
def _stats_row(source, df, value_col):
    if df.empty:
        return None
    cheap = df.nsmallest(1, value_col).iloc[0]
    exp = df.nlargest(1, value_col).iloc[0]
    return {
        "Source": source,
        "Cheapest": f"{cheap[value_col]:.2f}p · {fmt_local(cheap['valid_from'])}",
        "Most expensive": f"{exp[value_col]:.2f}p · {fmt_local(exp['valid_from'])}",
    }


stats_rows = [
    r for r in [
        _stats_row("Published", known, "value_inc_vat"),
        _stats_row("Predicted", predicted, "predicted_price"),
    ]
    if r is not None
]
if stats_rows:
    md = "| | Cheapest | Most expensive |\n| --- | --- | --- |\n"
    for r in stats_rows:
        md += f"| **{r['Source']}** | {r['Cheapest']} | {r['Most expensive']} |\n"
    st.markdown(md)

# === Spike risk: likely expensive periods ===
if "p_spike" in predicted.columns and predicted["p_spike"].notna().any():
    high_risk = predicted[predicted["p_spike"] > 0.25].nlargest(8, "p_spike")
    if not high_risk.empty:
        st.markdown("**🚨 Likely expensive periods (P(price > 25p) ≥ 25% — next 7 days)**")
        spike_md = "| Slot (Europe/London) | Spike probability | Predicted median |\n| --- | --- | --- |\n"
        for _, r in high_risk.iterrows():
            spike_md += f"| {fmt_local(r['valid_from'])} | **{r['p_spike'] * 100:.0f}%** | {r['predicted_price']:.2f} p |\n"
        st.markdown(spike_md)
    else:
        st.caption("✅ No high-spike-risk slots (P > 25%) in the next 7 days.")

if not forward.empty:
    st.caption(f"Model: `{latest_model}` · Latest run: {fmt_local(forward['generated_at'].iloc[0])}")

# === Client savings calculator ===
st.markdown("---")
st.subheader(f"💷 Client savings calculator — {PRODUCTS[product]['label']}")
st.caption(
    "Estimates annual savings vs a fixed unit-rate tariff for a typical "
    + ("UK domestic" if product == "AGILE" else "SME business")
    + " consumption profile. Uses historical hour-of-day average tariff prices for the "
    "selected region. Solar yield is Sheffield-typical (~950 kWh/kWp/yr × 1.06 Topcon bifacial uplift); "
    "battery dispatch heuristic = charge in 4 cheapest hours, discharge in 4 most expensive."
)

calc_cols = st.columns([1, 1, 1, 1.2])
# Default fixed unit rate by product. Business default = UK SME panel-average for a 1-year fixed
# contract on ~50,000 kWh annual usage (May 2026). Domestic default ≈ Ofgem Apr–Jun 2026 SVT.
# Sources: AquaSwitch (May 2026): small SME 26.2p, medium SME 24.2p; BusinessElectricityPrices.org.uk
# (Feb 2026): small 27.8p, medium 26.3p; BE:UK (May 2026): from 26.6p; Bionic (Q1 2026 SME 1-yr fix): 27.4p.
DEFAULT_FIXED_PRICE_P = 26.0 if product == "SHAPE_SHIFTERS" else 25.0
with calc_cols[0]:
    fixed_price_p = st.number_input(
        "Current fixed unit rate (p/kWh)",
        min_value=1.0, max_value=80.0, value=DEFAULT_FIXED_PRICE_P, step=0.01,
        key="calc_fixed_price",
        help=(
            "Inc-VAT for domestic, exc-VAT for business — match the basis of the RenewaBlox Solution data shown. "
            "Auto-fills from the rate you entered at the top of the page (if any); otherwise uses the market "
            "default (25p domestic / 26p commercial). You can override it here if you want to model a different rate."
        ),
    )
    if product == "SHAPE_SHIFTERS":
        st.caption(
            "📊 Check live SME rates: "
            "[AquaSwitch](https://www.aquaswitch.co.uk/business-electricity-prices/) · "
            "[BusinessElectricityPrices.org.uk](https://www.businesselectricityprices.org.uk/)"
        )
    else:
        st.caption(
            "📊 Check live domestic rates: "
            "[Ofgem price cap](https://www.ofgem.gov.uk/energy-price-cap) · "
            "[Uswitch](https://www.uswitch.com/gas-electricity/guides/average-gas-and-electricity-bills-in-the-uk/)"
        )
annual_kwh = calc_cols[1].number_input(
    "Annual consumption (kWh)",
    min_value=500, max_value=2_000_000, value=50_000, step=500,
)
TOPCON_KWP_PER_PANEL = 0.210
with calc_cols[2]:
    use_topcon = st.toggle(
        "TOPCon Bifacial",
        value=True,
        help="Toggle on to specify by panel count (each panel = 210 W).",
    )
    if use_topcon:
        topcon_panels = st.number_input(
            "Solar array (kWp) — TOPCon Bifacial (× N panels)",
            min_value=1, max_value=10, value=5, step=1,
            help="Each TOPCon bifacial panel = 210 W. Max 10 panels = 2.10 kWp.",
        )
        solar_kwp = topcon_panels * TOPCON_KWP_PER_PANEL
        st.markdown(f"##### × {topcon_panels} = **{solar_kwp:.2f} kWp**")
    else:
        solar_kwp = st.number_input(
            "Solar array (kWp)",
            min_value=0.0, max_value=30.0, value=4.0, step=0.5,
            help="Total installed peak (any panel type). 0 = no solar.",
        )
        if solar_kwp > 0:
            st.caption(f"= **{solar_kwp:.2f} kWp** custom")
        else:
            st.caption("No solar in scenario")

ULTRA_X_KWH_PER_UNIT = 3.84
ANKER_KWH_PER_UNIT = 7.0
with calc_cols[3]:
    battery_type = st.radio(
        "Battery product",
        options=["STREAM Ultra X", "Anker Solarbank Max AC UK", "Custom"],
        index=0,
        help=(
            "STREAM Ultra X: 3.84 kWh per module. Anker Solarbank Max AC UK: "
            "7 kWh per unit, supports up to 3500 W discharge (pair with the 20A toggle below)."
        ),
        horizontal=False,
    )
    if battery_type == "STREAM Ultra X":
        ultra_x_units = st.number_input(
            "Battery (kWh) — STREAM Ultra X (× N units)",
            min_value=1, max_value=5, value=2, step=1,
            help="Each STREAM Ultra X module = 3.84 kWh. Max stack = 5 (19.2 kWh).",
        )
        battery_kwh = ultra_x_units * ULTRA_X_KWH_PER_UNIT
        st.markdown(f"##### × {ultra_x_units} = **{battery_kwh:.2f} kWh**")
    elif battery_type == "Anker Solarbank Max AC UK":
        anker_units = st.number_input(
            "Battery (kWh) — Anker Solarbank Max AC UK (× N units)",
            min_value=1, max_value=3, value=1, step=1,
            help="Each Anker Solarbank Max AC UK = 7 kWh and supports up to 3500 W discharge.",
        )
        battery_kwh = anker_units * ANKER_KWH_PER_UNIT
        st.markdown(f"##### × {anker_units} = **{battery_kwh:.2f} kWh**")
    else:
        battery_kwh = st.number_input(
            "Battery (kWh)",
            min_value=0.0, max_value=60.0, value=0.0, step=0.5,
            help="Custom battery capacity. 0 to model no battery.",
        )
        if battery_kwh > 0:
            st.caption(f"= **{battery_kwh:.2f} kWh** custom")
        else:
            st.caption("No battery in scenario")

DISCHARGE_KW_13A = 0.8     # UK 13A standard socket (residential plug-in)
DISCHARGE_KW_16A = 1.2     # UK 16A commando plug (commercial plug-in)
DISCHARGE_KW_20A = 3.5     # UK 20A circuit (for higher-output batteries like Anker Solarbank Max AC UK)

_PLUG_KEYS = ("plug_800", "plug_1200", "plug_3500")


def _enforce_plug_exclusive(active_key):
    """Mutual-exclusion callback for the three plug-discharge toggles.

    Streamlit writes the new toggle value to session_state BEFORE firing on_change, so when
    we read st.session_state[active_key] here it already reflects the post-click state.
    If the user just turned `active_key` ON, force the other two OFF. If they turned it
    OFF, leave the others alone (all-off = no rate limit, i.e. hardwired/MCS install).
    """
    if st.session_state.get(active_key):
        for k in _PLUG_KEYS:
            if k != active_key:
                st.session_state[k] = False


# Auto-toggle plug discharge to match battery capability when battery type changes.
# - Anker Solarbank Max AC UK: supports 3500 W native discharge → set 20A toggle.
# - STREAM Ultra X: default to 16A commando (1200 W) — the standard commercial plug-in setup.
# - Custom: leave whatever the user has set (they're doing something specific).
# In all cases the user can still override manually afterwards.
prev_battery_type = st.session_state.get("_last_battery_type", "STREAM Ultra X")
if battery_type != prev_battery_type:
    if battery_type == "Anker Solarbank Max AC UK":
        st.session_state["plug_800"] = False
        st.session_state["plug_1200"] = False
        st.session_state["plug_3500"] = True
    elif battery_type == "STREAM Ultra X":
        st.session_state["plug_800"] = False
        st.session_state["plug_1200"] = True
        st.session_state["plug_3500"] = False
st.session_state["_last_battery_type"] = battery_type

if product == "SHAPE_SHIFTERS":
    enable_heating_shift = st.toggle(
        "🔥 Enable heating load shift",
        value=True,
        help=(
            "Most SME business consumption we serve is electrified heating (heat pumps, "
            "electric boilers, immersion). A meaningful fraction of that can be moved out "
            "of the 4–7pm peak via pre-heating, post-peak heating, or smart thermostatic controls. "
            "Toggle OFF for inflexible loads (e.g. retail/hospitality with fixed evening trade)."
        ),
    )
    if enable_heating_shift:
        shift_pct_pct = st.slider(
            "Heating load % shiftable from 4–7pm peak",
            min_value=0, max_value=100, value=30, step=5,
            help=(
                "Fraction of evening-peak heating load that gets re-timed. The shifted "
                "consumption is split evenly between **pre-heating at 15:00–16:00** "
                "(two settlement periods before peak) and **catch-up heating at 19:00–20:00** "
                "(two settlement periods after peak). This realistically reflects how "
                "heat-on-demand systems pre-warm the building and ramp back up after peak — "
                "the heating energy is still consumed, just shifted out of the red DUoS band. "
                "30% is a realistic central estimate with smart controls; up to 70-80% with "
                "thermal storage / hot-water buffer tanks."
            ),
        )
    else:
        shift_pct_pct = 0
        st.caption("Heating shift disabled — model assumes inflexible peak-hour load.")
    plug_cols = st.columns(3)
    with plug_cols[0]:
        plug_in_800 = st.toggle("🔌 800 W discharge", value=False, key="plug_800",
            on_change=_enforce_plug_exclusive, args=("plug_800",),
            help="UK regulation cap for plug-in via standard 13A 240V socket. Use for domestic residential installs.")
        st.caption("13a")
    with plug_cols[1]:
        plug_in_1200 = st.toggle("🔌 1200 W discharge", value=True, key="plug_1200",
            on_change=_enforce_plug_exclusive, args=("plug_1200",),
            help="16A commando plug allows ~1200 W discharge. Simple to install at commercial sites (no hardwiring / MCS certification needed).")
        st.caption("16a")
    with plug_cols[2]:
        plug_in_3500 = st.toggle("🔌 3500 W discharge", value=False, key="plug_3500",
            on_change=_enforce_plug_exclusive, args=("plug_3500",),
            help="20A circuit allows ~3500 W discharge. Pair with the Anker Solarbank Max AC UK (which supports 3500 W native discharge) for the largest throughput.")
        st.caption("20a")
else:
    shift_pct_pct = st.slider(
        "Load-shift percentage (move from 16-19 evening peak to cheaper hours)",
        min_value=0, max_value=50, value=30, step=5,
        help="Realistic for a willing-to-shift household: ~30% (washing/dishwasher/EV charging shifted).",
    )
    plug_cols = st.columns(3)
    with plug_cols[0]:
        plug_in_800 = st.toggle("🔌 800 W discharge", value=True, key="plug_800",
            on_change=_enforce_plug_exclusive, args=("plug_800",),
            help="UK regulation cap for plug-in via 13A socket. Defaults ON for domestic plug-in.")
        st.caption("13a")
    with plug_cols[1]:
        plug_in_1200 = st.toggle("🔌 1200 W discharge", value=False, key="plug_1200",
            on_change=_enforce_plug_exclusive, args=("plug_1200",),
            help="16A commando plug allows ~1200 W discharge. Toggle ON for commercial-style installs.")
        st.caption("16a")
    with plug_cols[2]:
        plug_in_3500 = st.toggle("🔌 3500 W discharge", value=False, key="plug_3500",
            on_change=_enforce_plug_exclusive, args=("plug_3500",),
            help="20A circuit allows ~3500 W discharge. Pair with high-output batteries like Anker Solarbank Max AC UK.")
        st.caption("20a")

# Highest cap wins if multiple are toggled; all off = no rate limit (hardwired/MCS)
if plug_in_3500:
    discharge_power_kw = DISCHARGE_KW_20A
elif plug_in_1200:
    discharge_power_kw = DISCHARGE_KW_16A
elif plug_in_800:
    discharge_power_kw = DISCHARGE_KW_13A
else:
    discharge_power_kw = None

try:
    from scenarios import all_scenarios
    scenarios = all_scenarios(
        annual_kwh=annual_kwh,
        fixed_price_p=fixed_price_p,
        region=region,
        product=product,
        solar_kwp=solar_kwp,
        battery_kwh=battery_kwh,
        shift_pct=shift_pct_pct / 100.0,
        discharge_power_kw=discharge_power_kw,
    )
    md = "| Scenario | Current cost / yr | Cost / yr - RenewaBlox | Saving / yr | Saving % | Battery cycles / day |\n"
    md += "| --- | ---: | ---: | ---: | ---: | ---: |\n"
    for s in scenarios:
        cycles_str = f"{s['battery_cycles_per_day']:.2f}" if s['battery_cycles_per_day'] is not None else "—"
        md += f"| {s['label']} | £{s['fixed_cost']:,.0f} | £{s['agile_net']:,.0f} | **£{s['saving']:,.0f}** | {s['saving_pct']:.0f}% | {cycles_str} |\n"
    st.markdown(md)
    st.caption(
        "Scenarios are cumulative. **Consumption-only model** — no value is assigned to grid export "
        "(any solar surplus the battery can't absorb is treated as curtailed/lost). "
        "Excludes standing charge (similar between the RenewaBlox Solution and most fixed offers). "
        "Battery model is heuristic — real installs with smart RenewaBlox Solution integration typically achieve "
        "85–95% of the figures shown."
    )
except Exception as e:
    st.warning(f"Couldn't compute scenarios: {e}")

# === Prediction vs actual ===
st.markdown("---")
st.subheader("Prediction vs actual")

if not preds.empty:
    forecasts = (
        preds[preds["generated_at"] < preds["valid_from"]]
        .sort_values("generated_at")
        .drop_duplicates("valid_from", keep="first")
    )
    accuracy = tariff.merge(
        forecasts[["valid_from", "predicted_price", "p10", "p90", "generated_at"]],
        on="valid_from", how="inner",
    )
else:
    accuracy = pd.DataFrame()


def _acc_chart(df):
    df = df.copy()
    df["x"] = to_local(df["valid_from"])
    f = go.Figure()
    f.add_trace(go.Scatter(x=df["x"], y=df["value_inc_vat"], mode="lines",
                           name="Actual", line=dict(color="#2563eb", width=2)))
    if "p10" in df.columns and df["p10"].notna().any():
        f.add_trace(go.Scatter(
            x=list(df["x"]) + list(df["x"][::-1]),
            y=list(df["p90"]) + list(df["p10"][::-1]),
            fill="toself", fillcolor="rgba(245,158,11,0.15)",
            line=dict(color="rgba(0,0,0,0)"), name="P10–P90", hoverinfo="skip",
        ))
    f.add_trace(go.Scatter(x=df["x"], y=df["predicted_price"], mode="lines",
                           name="Predicted", line=dict(color="#f59e0b", width=2, dash="dot")))
    f.update_layout(
        height=320,
        xaxis=dict(tickformat="%a %d %b\n%H:%M", title=None),
        yaxis_title="p/kWh inc VAT",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0),
        margin=dict(t=20, b=70),
    )
    return f


def _stats(df):
    err = df["predicted_price"] - df["value_inc_vat"]
    return {
        "n": len(df),
        "mae": err.abs().mean(),
        "me": err.mean(),
        "in_band": ((df["value_inc_vat"] >= df["p10"]) & (df["value_inc_vat"] <= df["p90"])).mean() * 100,
    }


def _show_section(df, empty_msg):
    if df.empty:
        st.info(empty_msg)
        return
    s = _stats(df)
    a, b, c, d = st.columns(4)
    a.metric("MAE", f"{s['mae']:.2f} p")
    b.metric("Mean error", f"{s['me']:+.2f} p")
    c.metric("Slots", s["n"])
    d.metric("Within P10–P90", f"{s['in_band']:.0f}%")
    st.plotly_chart(_acc_chart(df), width="stretch")


today_start = now.floor("D")
tomorrow_start = today_start + pd.Timedelta(days=1)
day_after = today_start + pd.Timedelta(days=2)

today_acc = accuracy[(accuracy["valid_from"] >= today_start) & (accuracy["valid_from"] < tomorrow_start)] if not accuracy.empty else pd.DataFrame()
tomorrow_acc = accuracy[(accuracy["valid_from"] >= tomorrow_start) & (accuracy["valid_from"] < day_after)] if not accuracy.empty else pd.DataFrame()
last_week_acc = accuracy[accuracy["valid_from"] >= now - pd.Timedelta(days=7)] if not accuracy.empty else pd.DataFrame()

tab_today, tab_tomorrow, tab_week = st.tabs(["Today", "Tomorrow (after 4pm)", "Last 7 days (backtest)"])

with tab_today:
    _show_section(
        today_acc,
        "No predictions made before today's slots in the DB yet. Re-run `python ingest.py` daily and accuracy data will accumulate. Meanwhile see 'Last 7 days' for backtested accuracy.",
    )

with tab_tomorrow:
    _show_section(
        tomorrow_acc,
        "Tomorrow's prices haven't been published yet (day-ahead settlement is released at ~4pm). Once they are, re-run `python ingest.py` and refresh this page.",
    )

with tab_week:
    _show_section(
        last_week_acc,
        "No backtested predictions found. Run `python ingest.py --full` to generate them.",
    )

with st.expander("Weather forecast (Open-Meteo, 7 day)"):
    if forecast.empty:
        st.info("No forecast yet — run ingest.")
    else:
        wf = go.Figure()
        x = to_local(forecast["timestamp"])
        wf.add_trace(go.Scatter(x=x, y=forecast["temperature_c"], name="Temp °C"))
        wf.add_trace(go.Scatter(x=x, y=forecast["wind_speed_kmh"], name="Wind km/h", yaxis="y2"))
        wf.update_layout(
            height=320,
            xaxis=dict(tickformat="%a %d %b\n%H:%M", title=None),
            yaxis=dict(title="°C"),
            yaxis2=dict(title="km/h", overlaying="y", side="right"),
            hovermode="x unified", legend=dict(orientation="h", y=1.1),
            margin=dict(t=20, b=70),
        )
        st.plotly_chart(wf, width="stretch")

with st.expander("GB grid forecast (BMRS wind + demand · NESO carbon intensity)"):
    with conn() as c:
        gf = pd.read_sql_query(
            "SELECT timestamp, wind_generation_mw, demand_mw, carbon_intensity_forecast FROM grid_forecast ORDER BY timestamp", c
        )
    if gf.empty:
        st.info("No grid forecast yet — run `python ingest.py`.")
    else:
        gf["timestamp"] = pd.to_datetime(gf["timestamp"], utc=True)
        gf["x"] = to_local(gf["timestamp"])
        gfig = go.Figure()
        if gf["wind_generation_mw"].notna().any():
            gfig.add_trace(go.Scatter(
                x=gf["x"], y=gf["wind_generation_mw"], mode="lines",
                name="Wind generation forecast (BMRS, MW)",
                line=dict(color="#16a34a", width=2),
            ))
        if gf["demand_mw"].notna().any():
            gfig.add_trace(go.Scatter(
                x=gf["x"], y=gf["demand_mw"], mode="lines",
                name="Demand forecast (BMRS, MW)",
                line=dict(color="#dc2626", width=2),
            ))
        if gf["carbon_intensity_forecast"].notna().any():
            gfig.add_trace(go.Scatter(
                x=gf["x"], y=gf["carbon_intensity_forecast"], mode="lines",
                name="Carbon intensity (NESO, gCO₂/kWh)",
                line=dict(color="#6b7280", width=2),
                yaxis="y2",
            ))
        gfig.update_layout(
            height=340,
            xaxis=dict(tickformat="%a %d %b\n%H:%M", title=None),
            yaxis=dict(title="MW"),
            yaxis2=dict(title="gCO₂/kWh", overlaying="y", side="right"),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.12),
            margin=dict(t=20, b=70),
        )
        st.plotly_chart(gfig, width="stretch")
        st.caption(
            "Horizons: BMRS WINDFOR/NDF ≈ 2–3 days · NESO Carbon Intensity 48h ahead. "
            "Carbon intensity is a feature in the price model (history + 48h forecast, "
            "imputed by hour-of-day median beyond 48h). Wind/demand are stored for cross-reference "
            "but not yet model features (BMRS doesn't retain historical forecasts)."
        )
