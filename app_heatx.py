"""Eunice HeatX — tailrace heat-exchanger studio (public partner app).

Interactive companion to the Kinlochdamph tailrace heat-exchanger study:
1 MW of data-centre heat rejected into the tailrace of a 999 kW Highland
run-of-river hydro scheme (impulse turbine) via a closed propylene-glycol
loop.

All thermal/hydraulic arithmetic comes from `sizing_model.py` — the single
computational source of truth for this design package. The embedded packing
explorer (heatx_assets.py) mirrors the same equations in JavaScript.

Run locally:  streamlit run app_heatx.py
"""
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import sizing_model as sm
from heatx_assets import EXPLORER_HTML, FLOW_HTML

st.set_page_config(
    page_title="Eunice HeatX — tailrace heat exchanger",
    page_icon=":material/device_thermostat:",
    layout="centered",
)

CORAL, BLUE, TEAL, AMBER, RED, SLATE = (
    "#d85a30", "#378add", "#10b981", "#ef9f27", "#e24b4a", "#64748b")
DISCLAIMER = ("Preliminary engineering for option comparison — not for "
              "construction. Duty and head-loss figures are pending vendor "
              "thermal/hydraulic data and site measurements.")

# Seasonal coincidence assumption: low river flow tends to coincide with
# warm summer water. Same mapping as the project workbook.
TRIV_SEASONAL = {0.05: 16.5, 0.10: 16.0, 0.15: 15.5, 0.20: 15.0, 0.25: 14.0,
                 0.30: 13.0, 0.35: 12.0, 0.40: 11.0, 0.45: 10.5, 0.50: 10.0,
                 0.55: 9.5, 0.60: 9.0, 0.65: 8.7, 0.70: 8.3, 0.75: 8.0,
                 0.80: 7.8, 0.85: 7.5, 0.90: 7.3, 0.95: 7.1, 1.00: 7.0}


def supply_temp_closed_form(duty_w, ua, t_river, mdot, cp):
    """T_s = T_r + dT.E/(E-1), E = exp(UA/(m.cp)) — closed form of
    Q = UA.LMTD with dT_loop = Q/(m.cp). Mirrors the workbook."""
    if duty_w <= 0:
        return t_river
    dt_loop = duty_w / (mdot * cp)
    e = math.exp(ua / (mdot * cp))
    return t_river + dt_loop * e / (e - 1.0)


@st.cache_data
def duty_vs_flow(mode, river_mode, t_fixed, wider_w, k_byp, fin_dp,
                 od, pitch, fin):
    pack = sm.Packing(od, pitch, fin)
    sec = sm.TailraceSection(wider_width_m=wider_w, k_bypass=k_byp)
    mdot, _ = sm.glycol_flow()
    b = sm.BASIS
    rows = []
    for f, t_seas in sorted(TRIV_SEASONAL.items()):
        q = f * b.tailrace_q_max
        t_riv = t_seas if river_mode == "seasonal" else t_fixed
        split = sm.bypass_split(q, pack, sec, fin_dp)
        u, _ = sm.u_effective(h_o=sm.h_o_scaled(split["v_bundle"]))
        ua = u * (pack.area_eff_m2 + b.dn125_area_m2 * b.dn125_derate)
        duty = (f if mode == "tracks" else 1.0) * b.q_duty_w
        dt_loop = duty / (mdot * b.glycol_cp)
        t_sup = supply_temp_closed_form(duty, ua, t_riv, mdot, b.glycol_cp)
        rows.append({"frac": f, "q": q, "t_river": t_riv,
                     "v_bundle": split["v_bundle"],
                     "share": split["bundle_share"], "u": u,
                     "head_m": split["head_m"],
                     "lost_kw": 9.81 * q * split["head_m"],
                     "duty_kw": duty / 1000.0, "dt_loop": dt_loop,
                     "t_supply": t_sup, "miner_in": t_sup - dt_loop})
    return pd.DataFrame(rows)


def line_fig(title, x_title, y_title):
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white", title=title, height=420,
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis_title=x_title, yaxis_title=y_title,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
    )
    return fig


def footer():
    st.caption(f"_{DISCLAIMER}_")


# ----------------------------------------------------------------- sidebar
st.sidebar.title("Eunice HeatX")
st.sidebar.caption(
    "Tailrace heat-exchanger studio · Kinlochdamph 999 kW hydro + "
    "liquid-cooled data centre")
page = st.sidebar.radio("Section", [
    "Concept & flow diagrams",
    "Packing explorer",
    "Duty vs river flow",
    "Hybrid & parasitics",
    "Sensitivity",
    "Assumptions register",
    "About & lineage",
], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(DISCLAIMER)

# ------------------------------------------------------------ concept page
if page == "Concept & flow diagrams":
    st.title("Tailrace heat exchanger — the concept")
    st.markdown(
        "Up to **1 MW** of heat from a hydro-cooled data centre is rejected "
        "to the river through one of two architectures: a **submerged "
        "finned-tube bundle** sitting directly in the tailrace (option A, "
        "single closed glycol loop), or a **plate heat exchanger** with a "
        "pumped open river-water secondary (option B). Dashes move in the "
        "direction of flow.")
    components.html(FLOW_HTML, height=1190, scrolling=False)
    st.subheader("What the analysis found")
    st.markdown(
        "1. **Envelope is the binding constraint.** The study's 120–150 m "
        "finned-tube target does not fit the 1.0 × 0.9 × 0.8 m drop-in "
        "envelope at a cleanable pitch — an honest single module delivers "
        "roughly **250–500 kW**, plus ~150 kW from the submerged DN125 runs "
        "(margin, not guaranteed duty).\n"
        "2. **Backwater is a hard constraint, not just lost energy.** The "
        "turbine is an impulse machine (Turgo): tailwater rise erodes "
        "runner clearance ~1:1. Refined estimate ≈ 0.25 m at rated flow — "
        "the allowable figure rests with the turbine supplier.\n"
        "3. **The design point is low river flow, not peak.** With no grid "
        "export until the mid-2030s the mining load tracks generation, yet "
        "even then one module exceeds a 40 °C miner inlet above ~25% flow. "
        "A **staged hybrid** (honest coil + PHE trim or extra bays) is "
        "needed in both load modes.\n"
        "4. **The glycol side dominates the thermal resistance** (~53% of "
        "1/U), so fins beyond ~3× buy little — open, cleanable geometry "
        "wins over fin density.")
    footer()

# ----------------------------------------------------------- explorer page
elif page == "Packing explorer":
    st.title("Tube packing explorer")
    st.markdown(
        "How many finned tubes actually fit the drop-in envelope, and what "
        "duty they deliver. Equations are identical to `sizing_model.py` "
        "(counts from envelope ÷ pitch, duty from Q = U·A·ΔT_lm).")
    components.html(EXPLORER_HTML, height=1130, scrolling=False)
    st.caption(
        "Defaults reproduce the reference packing: 63 mm OD at 150 mm pitch "
        "with 3× fins → 30 tubes, ~25 m, ~15 m² effective, ~407 kW with the "
        "DN125 runs included.")
    footer()

# ------------------------------------------------------- duty vs flow page
elif page == "Duty vs river flow":
    st.title("Duty vs river flow")
    st.markdown(
        "The question that drives the architecture: what glycol temperature "
        "does the loop settle at as river flow varies — and does it stay "
        "under the miners' inlet ceiling?")
    c1, c2 = st.columns(2)
    mode = c1.radio("Mining load", ["tracks", "constant"],
                    format_func=lambda m: "Tracks generation (islanded)"
                    if m == "tracks" else "Constant 1 MW (grid-backed)")
    river_mode = c2.radio("River temperature", ["seasonal", "fixed"],
                          format_func=lambda m: "Seasonal coincidence"
                          if m == "seasonal" else "Fixed value")
    t_fixed = c2.slider("Fixed river temperature °C", 4.0, 18.0, 10.0, 0.5,
                        disabled=(river_mode == "seasonal"))
    miner_max = c1.slider("Miner inlet ceiling °C", 35, 55, 40, 1)
    with st.expander("Hydraulic & packing assumptions"):
        a1, a2, a3 = st.columns(3)
        wider_w = a1.slider("Wider-section width m", 1.0, 2.0, 1.4, 0.05,
                            help="Channel width at the bundle — site "
                                 "measurement pending; drives the bypass split")
        k_byp = a2.slider("Bypass loss coefficient", 0.5, 3.0, 1.5, 0.1)
        fin_dp = a3.slider("Fin ΔP multiplier", 1.0, 2.0, 1.5, 0.05,
                           help="On bare-bank pressure drop — vendor Kv "
                                "data will replace this")
        p1, p2, p3 = st.columns(3)
        od = p1.selectbox("Tube OD mm", [25, 38, 50, 63], index=3)
        pitch = p2.slider("Pitch mm", 60, 250, 150, 5)
        fin = p3.slider("Fin multiplier", 1.0, 3.5, 3.0, 0.1)

    df = duty_vs_flow(mode, river_mode, t_fixed, wider_w, k_byp, fin_dp,
                      od, pitch, fin)
    ceiling = df["dt_loop"] + miner_max

    fig = line_fig("Equilibrium glycol supply temperature",
                   "Fraction of rated river flow", "°C")
    fig.add_scatter(x=df["frac"], y=df["t_supply"], name="Supply temperature",
                    line=dict(color=CORAL, width=3))
    fig.add_scatter(x=df["frac"], y=ceiling, name="Max supply for miner ceiling",
                    line=dict(color=SLATE, width=2, dash="dash"))
    hot = df["t_supply"] > ceiling
    if hot.any():
        fig.add_scatter(x=df.loc[hot, "frac"], y=df.loc[hot, "t_supply"],
                        mode="markers", name="Above ceiling",
                        marker=dict(color=RED, size=9, symbol="x"))
    fig.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)
    if hot.any():
        first = df.loc[hot, "frac"].min()
        st.warning(
            f"This packing exceeds the {miner_max} °C miner inlet ceiling "
            f"from ~{first:.0%} of rated flow — the balance must come from "
            "extra bays or a PHE trim (see Hybrid & parasitics).")
    else:
        st.success("Within the miner inlet ceiling across the full flow range.")

    fig2 = line_fig("Tailwater rise at the bundle (refined model)",
                    "Fraction of rated river flow", "m")
    fig2.add_scatter(x=df["frac"], y=df["head_m"], name="Tailwater rise",
                     line=dict(color=BLUE, width=3))
    fig2.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True)

    r = df.iloc[-1]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bundle velocity (rated)", f"{r.v_bundle:.2f} m/s")
    m2.metric("Flow through bundle", f"{r.share:.0%}")
    m3.metric("Tailwater rise", f"{r.head_m:.2f} m")
    m4.metric("Lost generation bound", f"{r.lost_kw:.1f} kW")
    st.info(
        "Impulse-turbine note: tailwater rise erodes runner clearance "
        "before it costs energy — treat the rise as a hard budget and "
        "confirm the allowable figure with the turbine supplier. The kW "
        "figure is the bounding rate ρ·g·Q·Δh.")
    footer()

# ------------------------------------------------- hybrid & parasitics page
elif page == "Hybrid & parasitics":
    st.title("Hybrid sizing & parasitic comparison")
    b = sm.BASIS
    c1, c2, c3 = st.columns(3)
    t_sup = c1.slider("Glycol supply °C (ΔT 10 K)", 45, 60, 50, 1)
    t_riv = c2.slider("River temperature °C", 4.0, 18.0, 10.0, 0.5)
    river_dt = c3.slider("PHE secondary rise K", 3.0, 8.0, 5.0, 0.5)
    p1, p2, p3 = st.columns(3)
    od = p1.selectbox("Tube OD mm", [25, 38, 50, 63], index=3)
    pitch = p2.slider("Pitch mm", 60, 250, 150, 5)
    fin = p3.slider("Fin multiplier", 1.0, 3.5, 3.0, 0.1)

    pack = sm.Packing(od, pitch, fin)
    dtlm = sm.lmtd(t_sup, t_sup - b.glycol_dt, t_riv)
    u, _ = sm.u_effective()
    coil = sm.duty_kw(u, pack.area_eff_m2, dtlm)
    pipe = sm.dn125_margin_kw(u, dtlm)
    base = coil + pipe
    balance = max(b.q_duty_w / 1000.0 - base, 0.0)
    if pack.fins_clash:
        st.error("Fins clash at this pitch — uncleanable dense core. "
                 "Open the pitch before reading the numbers below.")

    m1, m2, m3 = st.columns(3)
    m1.metric("Coil (one bay)", f"{coil:,.0f} kW")
    m2.metric("DN125 margin", f"{pipe:,.0f} kW")
    m3.metric("Balance to 1 MW", f"{balance:,.0f} kW")

    st.subheader("Covering the balance")
    if balance > 0:
        bays = 1 + math.ceil(balance / coil)
        flow_ls, p_lo, p_hi = sm.phe_trim(balance, river_dt=river_dt)
        pen = sm.penstock_fed_cost(flow_ls)
        a, bcol = st.columns(2)
        a.markdown(
            f"**Path A — extra drop-in bays**\n\n{coil:,.0f} kW per extra "
            f"bay → **{bays} bays** in total. No extra pumps, but backwater "
            "adds roughly per bay and the clearance budget must cover the sum.")
        bcol.markdown(
            f"**Path B — PHE trim**\n\nTrim duty {balance:,.0f} kW → "
            f"secondary **{flow_ls:.1f} L/s** at +{river_dt:.1f} K, pump "
            f"**{p_lo:.1f}–{p_hi:.1f} kW** (80–120 kPa). Penstock-fed "
            f"variant would forgo **{pen:.1f} kW** of generation — "
            f"~{pen / max(p_hi, 1e-9):.0f}× worse than pumping; rejected.")
    else:
        st.success("This configuration meets the full duty without a trim.")

    st.subheader("Parasitic totals at 1 MW duty")
    mdot, vdot = sm.glycol_flow()
    sec_flow = (b.q_duty_w / 1000.0) / (4.186 * river_dt)
    rows = [
        ("A — submerged coil", sm.pump_power_kw(vdot, 150),
         sm.pump_power_kw(vdot, 200), "glycol pump only; backwater bound adds ~0–3 kW"),
        ("B — PHE, pumped open loop",
         sm.pump_power_kw(vdot, 120) + sm.pump_power_kw(sec_flow, 80),
         sm.pump_power_kw(vdot, 160) + sm.pump_power_kw(sec_flow, 120),
         "primary + secondary river pump and strainer"),
        ("B′ — PHE, penstock-fed",
         sm.pump_power_kw(vdot, 120) + sm.penstock_fed_cost(sec_flow),
         sm.pump_power_kw(vdot, 160) + sm.penstock_fed_cost(sec_flow),
         "diverted water bypasses the runner — rejected"),
    ]
    tbl = pd.DataFrame(
        [{"Option": o, "kW (low)": round(lo, 1), "kW (high)": round(hi, 1),
          "kWth/kWe (low–high)": f"{1000 / hi:,.0f}–{1000 / lo:,.0f}",
          "Note": n} for o, lo, hi, n in rows])
    st.dataframe(tbl, hide_index=True, use_container_width=True)
    footer()

# ------------------------------------------------------------ sensitivity
elif page == "Sensitivity":
    st.title("Sensitivity — duty vs temperatures")
    st.markdown(
        "Total duty (bays × coil + DN125 margin) at the design-point U. "
        "The glycol side dominates the thermal resistance, so U barely "
        "moves with temperature — LMTD does the work.")
    c1, c2 = st.columns(2)
    bays = c1.number_input("Bays installed", 1, 4, 1)
    target = c2.number_input("Duty target kW", 250, 1500, 1000, 50)
    b = sm.BASIS
    pack = sm.Packing(63, 150, 3.0)
    u, _ = sm.u_effective()
    supplies = list(range(45, 61))
    rivers = list(range(4, 19))
    z = [[bays * sm.duty_kw(u, pack.area_eff_m2, sm.lmtd(ts, ts - b.glycol_dt, tr))
          + sm.dn125_margin_kw(u, sm.lmtd(ts, ts - b.glycol_dt, tr))
          for tr in rivers] for ts in supplies]
    fig = go.Figure(go.Heatmap(
        z=z, x=rivers, y=supplies, colorscale="RdYlGn",
        colorbar=dict(title="kW"),
        hovertemplate="river %{x} °C · supply %{y} °C → %{z:,.0f} kW<extra></extra>"))
    fig.add_contour(z=z, x=rivers, y=supplies, showscale=False,
                    contours=dict(start=target, end=target, coloring="lines",
                                  showlabels=True),
                    line=dict(color="#0f172a", width=2, dash="dash"),
                    hoverinfo="skip")
    fig.update_layout(template="plotly_white", height=520,
                      margin=dict(l=10, r=10, t=50, b=10),
                      title=f"Duty kW — dashed line marks {target:,} kW",
                      xaxis_title="River temperature °C",
                      yaxis_title="Glycol supply °C")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Reference packing (63 mm / 150 mm / 3×). At one bay the grid tops "
        "out around 600 kW even at 60 °C supply and 4 °C river — a single "
        "module cannot reach 1 MW. The 55 °C row is the miner-inlet lever: "
        "worth ~14% duty if the fleet accepts 55/45 °C.")
    footer()

# --------------------------------------------------------------- register
elif page == "Assumptions register":
    st.title("Open questions & assumptions")
    st.markdown("Everything the numbers currently lean on, with status. "
                "**Red** blocks design freeze · **amber** to refine before "
                "RFQ award · **green** answered or decided.")
    R = [
        (1, "Grid import at low river flow", "Open question",
         "No export connection until the mid-2030s — mining load must track generation near-term", "AMBER"),
        (2, "Miner inlet ceiling", "Open question",
         "40 °C assumed — confirm the hydro-ASIC fleet datasheet & warranty for sustained 45–50 °C", "RED"),
        (3, "Regulator thermal discharge (CAR licence)", "Open question",
         "+0.18 °C at rated flow but +1–2 °C at low summer flow, in a protected-species catchment", "RED"),
        (4, "Turbine tailwater tolerance", "Answered → action open",
         "Impulse turbine confirmed — obtain runner freeboard and allowable tailwater from the supplier", "AMBER"),
        (5, "Wider-section width at bundle", "Assumption (1.4 m)",
         "Drives the bypass split; ±0.2 m ⇒ roughly ∓30% tailwater rise — measure on site", "AMBER"),
        (6, "Bundle hydraulic coefficients", "Assumption",
         "Fin ΔP ×1.5, bypass K 1.5, staggered-bank friction — vendor Kv curve will replace", "AMBER"),
        (7, "Film coefficients & fouling", "Assumption",
         "h_i 4000, h_o 4900 at 1.62 m/s, standard fouling factors — U ±20% moves duty pro rata", "AMBER"),
        (8, "DN125 margin derate 0.70", "Assumption",
         "~155 kW from submerged runs — treat as margin, never as guaranteed duty", "AMBER"),
        (9, "Capacity factor & £/MWh", "Assumption",
         "50% CF, £95/MWh for £/yr figures — refine from the flow-duration curve", "AMBER"),
        (10, "Net head & turbine efficiency", "Assumption",
         "Used only in the penstock-fed comparison; verdict (~5× worse) robust to ±20%", "GREEN"),
        (11, "Fleet load vs 1 MW design duty", "Open question",
         "Current fleet electrical load is below 1 MW — design duty is expansion headroom; confirm intent", "AMBER"),
        (12, "Glycol type", "Decided",
         "Propylene (not ethylene) — direct immersion in a watercourse", "GREEN"),
    ]
    df = pd.DataFrame(R, columns=["No.", "Item", "Type", "Current basis", "Status"])
    colours = {"RED": "background-color:#fde8e8",
               "AMBER": "background-color:#fef3c7",
               "GREEN": "background-color:#d1fae5"}
    st.dataframe(df.style.map(lambda v: colours.get(v, ""), subset=["Status"]),
                 hide_index=True, use_container_width=True, height=490)
    footer()

# -------------------------------------------------------------- about page
else:
    st.title("About & lineage")
    st.markdown(
        "**Eunice HeatX** is the interactive companion to the tailrace "
        "heat-exchanger design study for the Kinlochdamph hydro scheme "
        "(999 kW run-of-river, Wester Ross) and its co-located liquid-"
        "cooled data centre.\n\n"
        "- `sizing_model.py` in this repository is the **single "
        "computational source of truth** — every figure in this app comes "
        "from it, and the packing explorer mirrors the same equations in "
        "JavaScript.\n"
        "- The model was built and independently verified from the source "
        "design note (June 2026), with four corrections folded in: honest "
        "envelope packing, bundle backwater, the low-flow design point, "
        "and the glycol-dominated resistance stack.\n"
        "- A multi-sheet Excel workbook and a vendor RFQ accompany this "
        "app in the project's internal design package.\n\n"
        "Conventions: British English, SI units, temperatures in °C, "
        "duty in kW.")
    st.info(DISCLAIMER)
    st.caption("RenewaBlox · Eunice platform · contact "
               "callum@renewablox.com")
