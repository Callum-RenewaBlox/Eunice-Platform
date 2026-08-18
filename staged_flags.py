"""Staged low-price flags panel — shared by app.py and app_domestic.py.

Renders the rebuilt engine's probability columns (p_neg, p_sub5, p_sub10, p_hi40) as:
  1. stacked/overlaid per-slot probability bars under the price fan (P(<10p) lightest,
     P(<5p) mid, P(negative) darkest — nested events, so overlaid bars read as a stack);
  2. a per-day headline built from the report's tiers:
       negative:   possible P>=8%   · likely P>=25% · very likely P>=50%
       <5p, <10p:  possible P>=10%  · likely P>=30% · very likely P>=60%
     with the time window of the flagged block, e.g.
     "Sat 11 Apr — very likely <10p 09:00-16:00 (P 70-85%), negative possible 12:00-14:00".
Slots on days 5-7 (lead_days >= 5) are styled lighter and labelled "outlook" — indicative,
not point forecasts (see rebuild/eunice_rebuild_report.html section 4.4).
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# (threshold, tier label), strongest first — from report section 4.4 / kickoff step 4
TIERS = {
    "neg":   ((0.50, "very likely"), (0.25, "likely"), (0.08, "possible")),
    "sub5":  ((0.60, "very likely"), (0.30, "likely"), (0.10, "possible")),
    "sub10": ((0.60, "very likely"), (0.30, "likely"), (0.10, "possible")),
}
EVENT_LABEL = {"sub10": "<10p", "sub5": "<5p", "neg": "negative"}
HI40_THRESHOLD = 0.30
# nested greens: lightest = <10p, darkest = negative; alpha halved for outlook days
BAR_STYLE = {"sub10": (16, 185, 129, 0.30), "sub5": (5, 150, 105, 0.60), "neg": (4, 90, 66, 0.95)}
OUTLOOK_LEAD = 5


def has_flag_data(predicted):
    """True when the forward rows carry the rebuilt engine's probability columns."""
    return (
        not predicted.empty
        and all(c in predicted.columns for c in ("p_neg", "p_sub5", "p_sub10"))
        and predicted["p_sub10"].notna().any()
    )


def _is_outlook(df):
    if "lead_days" in df.columns and df["lead_days"].notna().any():
        return df["lead_days"].fillna(0) >= OUTLOOK_LEAD
    day4 = pd.Timestamp.now(tz="UTC").floor("D") + pd.Timedelta(days=OUTLOOK_LEAD - 1)
    return df["valid_from"] >= day4


def probability_bars(predicted, x_range=None):
    """Per-slot probability bars, aligned under the main price chart via x_range."""
    df = predicted.sort_values("x")
    outlook = _is_outlook(df).values
    fig = go.Figure()
    for ev in ("sub10", "sub5", "neg"):
        r, g, b, a = BAR_STYLE[ev]
        colors = [f"rgba({r},{g},{b},{a * (0.45 if o else 1.0)})" for o in outlook]
        fig.add_trace(go.Bar(
            x=df["x"], y=df[f"p_{ev}"] * 100,
            name=f"P({EVENT_LABEL[ev]})", marker_color=colors, marker_line_width=0,
            hovertemplate=f"P({EVENT_LABEL[ev]}) " + "%{y:.0f}%<extra></extra>",
        ))
    fig.update_layout(
        barmode="overlay", height=190, bargap=0,
        yaxis=dict(title="P(%)", range=[0, 100], tickvals=[0, 25, 50, 75, 100]),
        xaxis=dict(tickformat="%a %d %b", title=None, range=x_range),
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.35, x=0),
        margin=dict(t=8, b=8, l=0, r=0),
    )
    return fig


def _window(day_rows, mask):
    hit = day_rows[mask]
    start = hit["x"].iloc[0]
    end = hit["x"].iloc[-1] + pd.Timedelta(minutes=30)
    return f"{start:%H:%M}–{end:%H:%M}"


def _prange(p):
    lo, hi = p.min() * 100, p.max() * 100
    return f"P ≈ {hi:.0f}%" if hi - lo < 5 else f"P {lo:.0f}–{hi:.0f}%"


def daily_headlines(predicted):
    """One headline dict per local day that has at least one flagged event."""
    df = predicted.sort_values("x").copy()
    df["_day"] = df["x"].dt.date
    df["_outlook"] = _is_outlook(df).values
    out = []
    for day, rows in df.groupby("_day"):
        parts = []
        for ev in ("sub10", "sub5", "neg"):
            p = rows[f"p_{ev}"]
            if p.isna().all():
                continue
            for thr, tier in TIERS[ev]:
                if (p >= thr).any():
                    mask = (p >= thr).values
                    wording = (f"negative {tier}" if ev == "neg" else f"{tier} {EVENT_LABEL[ev]}")
                    parts.append(f"{wording} {_window(rows, mask)} ({_prange(p[mask])})")
                    break
        if "p_hi40" in rows.columns and rows["p_hi40"].notna().any() and (rows["p_hi40"] >= HI40_THRESHOLD).any():
            mask = (rows["p_hi40"] >= HI40_THRESHOLD).values
            parts.append(f"⚠ peak >40p likely {_window(rows, mask)}")
        if parts:
            out.append({"day": pd.Timestamp(day), "text": ", ".join(parts),
                        "outlook": bool(rows["_outlook"].all())})
    return out


def render(predicted, x_range=None):
    """The full panel: bars + per-day tier headlines. Call only when has_flag_data() is True."""
    st.markdown("**\U0001f7e2 Cheap-price flags — next 7 days**")
    st.plotly_chart(probability_bars(predicted, x_range), width="stretch")
    headlines = daily_headlines(predicted)
    if headlines:
        lines = []
        for h in headlines:
            day_txt = f"**{h['day']:%a %d %b}** — {h['text']}"
            if h["outlook"]:
                day_txt = f"<span style='color:#9ca3af'>{day_txt} · <i>outlook</i></span>"
            lines.append(f"- {day_txt}")
        st.markdown("\n".join(lines), unsafe_allow_html=True)
    else:
        st.caption("No elevated cheap-price probabilities in the next 7 days.")
    st.caption(
        "Bars show each half-hour's probability of settling below 10p / below 5p / below 0p "
        "(nested, so the darker bar is always inside the lighter one). Day headlines use the "
        "staged tiers — *possible* / *likely* / *very likely* at P ≥ 8/25/50% (negative) and "
        "≥ 10/30/60% (<5p, <10p). Greyed days 5–7 are outlook: directionally useful, "
        "not point forecasts."
    )
