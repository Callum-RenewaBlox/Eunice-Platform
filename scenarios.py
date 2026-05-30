"""Client-facing savings calculator: estimate annual savings on the RenewaBlox Solution
versus a fixed tariff, with optional solar + battery overlays.

Approach is deliberately simplified — uses an hour-of-day-averaged tariff price profile
(per region+product) crossed with a stylised hourly consumption profile (domestic or
business). Solar is a typical UK-midland yield curve scaled by kWp. Battery dispatch
uses a heuristic: charge in the cheapest hours, discharge during the most expensive.
Good enough for client illustration; not a half-hourly settlement-grade simulation.
"""
import pandas as pd

from db import conn

# Stylised UK domestic Profile Class 1/2 hourly fraction of daily consumption
# (morning peak ~7-9, evening peak ~17-19, low overnight). Sums to 1.0 after normalisation.
_DOMESTIC = [
    0.024, 0.020, 0.018, 0.018, 0.018, 0.020,  # 00-05
    0.030, 0.052, 0.058, 0.044, 0.038, 0.038,  # 06-11
    0.044, 0.044, 0.038, 0.038, 0.050, 0.080,  # 12-17
    0.090, 0.080, 0.058, 0.048, 0.038, 0.030,  # 18-23
]
DOMESTIC_PROFILE = [x / sum(_DOMESTIC) for x in _DOMESTIC]

# Stylised SME business profile: 9-5 weighted, low overnight
_BUSINESS = [
    0.018, 0.016, 0.016, 0.016, 0.016, 0.018,
    0.024, 0.032, 0.052, 0.072, 0.082, 0.085,
    0.082, 0.080, 0.078, 0.072, 0.060, 0.044,
    0.030, 0.024, 0.020, 0.020, 0.020, 0.020,
]
BUSINESS_PROFILE = [x / sum(_BUSINESS) for x in _BUSINESS]

# Average solar yield per kWp installed by hour (Sheffield-like, mid-UK latitude).
# Annual sum ~950 kWh/kWp/year (south-facing, ~30° pitch), bifacial Topcon uplift applied externally.
SOLAR_KWH_PER_KWP_BY_HOUR = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.006,
    0.024, 0.071, 0.142, 0.213, 0.273, 0.308,
    0.332, 0.320, 0.290, 0.243, 0.184, 0.119,
    0.053, 0.018, 0.006, 0.000, 0.000, 0.000,
]


def get_profile(product):
    return BUSINESS_PROFILE if product == "SHAPE_SHIFTERS" else DOMESTIC_PROFILE


def get_mean_agile_by_hour(region, product):
    """Mean tariff price by hour of day (UK local), p/kWh inc VAT."""
    with conn() as c:
        df = pd.read_sql_query(
            "SELECT valid_from, value_inc_vat FROM tariff WHERE region = ? AND product = ?",
            c, params=(region, product),
        )
    if df.empty:
        return pd.Series([20.0] * 24, index=range(24))
    df["valid_from"] = pd.to_datetime(df["valid_from"], utc=True)
    df["hour"] = df["valid_from"].dt.tz_convert("Europe/London").dt.hour
    return df.groupby("hour")["value_inc_vat"].mean().reindex(range(24)).fillna(20.0)


def apply_load_shift(profile, shift_pct, peak_hours=(16, 17, 18), target_hours=(0, 1, 2, 3, 4, 11, 12, 13)):
    """Move `shift_pct` of consumption from peak hours to cheaper target hours."""
    p = list(profile)
    shifted_total = sum(p[h] * shift_pct for h in peak_hours)
    for h in peak_hours:
        p[h] *= (1 - shift_pct)
    per_target = shifted_total / len(target_hours)
    for h in target_hours:
        p[h] += per_target
    s = sum(p)
    return [x / s for x in p]


def compute_scenario(annual_kwh, fixed_price_p, mean_agile, profile,
                     solar_kwp=0.0, battery_kwh=0.0, seg_rate_p=0.0,
                     bifacial_uplift=1.06, discharge_power_kw=None):
    """Compute annual fixed cost vs RenewaBlox Solution net cost for a given configuration.

    Returns dict with totals + a kWh breakdown. The `agile_net` key in the return dict is
    a legacy internal name — it represents the net cost on the RenewaBlox Solution.
    """
    cons_by_hour = [annual_kwh * profile[h] for h in range(24)]
    solar_by_hour = [solar_kwp * SOLAR_KWH_PER_KWP_BY_HOUR[h] * 365 * bifacial_uplift
                     for h in range(24)]

    # Solar offsets same-hour consumption first; surplus is what reaches the battery
    # (or gets curtailed in this consumption-only model if the battery can't absorb it).
    net_by_hour = [cons_by_hour[h] - solar_by_hour[h] for h in range(24)]
    grid_import = [max(0.0, n) for n in net_by_hour]
    export = [max(0.0, -n) for n in net_by_hour]

    actual_dispatch = 0.0  # battery throughput (kWh/yr) — populated below if battery present

    if battery_kwh > 0:
        # Allow up to 2 cycles/day. Each cycle dispatches `useable` kWh (after DoD).
        useable_per_cycle = battery_kwh * 0.8
        rte = 0.9
        max_cycles_per_day = 2
        annual_dispatch_cap = useable_per_cycle * max_cycles_per_day * 365

        # Charge sources (cheapest hours): used both to set the discharge profitability threshold
        # and to absorb any grid charging the battery needs (when solar isn't enough).
        sorted_h_cheap = sorted(range(24), key=lambda h: mean_agile.iloc[h])
        cheap_charge_hours = sorted_h_cheap[:6]
        cheap_avg = sum(mean_agile.iloc[h] for h in cheap_charge_hours) / len(cheap_charge_hours)

        # Profitable to discharge into any hour where tariff price > charge cost after RTE
        # losses + a 5% margin. For typical Sheffield this gives ~8-10 discharge target hours.
        discharge_threshold = (cheap_avg / rte) * 1.05
        discharge_targets = sorted(
            (h for h in range(24) if mean_agile.iloc[h] > discharge_threshold),
            key=lambda h: -mean_agile.iloc[h],  # most expensive first → discharge greedily there
        )

        # Optional per-hour power cap (e.g. 0.8 kW for UK plug-in 13A socket installs).
        # Translates to per-hour-of-day annual ceiling: power_kw × 365 days.
        per_hour_annual_cap = (discharge_power_kw * 365) if discharge_power_kw else float("inf")

        # Greedy dispatch: walk down expense, drain imports until cap reached
        if discharge_targets:
            remaining = annual_dispatch_cap
            for h in discharge_targets:
                if remaining <= 0:
                    break
                h_dispatch = min(grid_import[h], remaining, per_hour_annual_cap)
                grid_import[h] -= h_dispatch
                actual_dispatch += h_dispatch
                remaining -= h_dispatch

        # Source the energy: solar export first (free), then cheapest grid hours.
        energy_to_store_kwh = actual_dispatch / rte
        annual_export_total = sum(export)
        solar_charge = min(energy_to_store_kwh, annual_export_total)
        grid_charge = max(0.0, energy_to_store_kwh - solar_charge)

        # Reduce export proportionally for solar diverted into the battery
        if annual_export_total > 0 and solar_charge > 0:
            factor = max(0.0, 1 - solar_charge / annual_export_total)
            for h in range(24):
                export[h] *= factor

        # Apply remaining grid charge to the cheapest hours
        if grid_charge > 0 and cheap_charge_hours:
            per_h = grid_charge / len(cheap_charge_hours)
            for h in cheap_charge_hours:
                grid_import[h] += per_h

    annual_grid_cost = sum(grid_import[h] * mean_agile.iloc[h] / 100 for h in range(24))
    annual_export_value = sum(export) * seg_rate_p / 100
    agile_net = annual_grid_cost - annual_export_value
    fixed_cost = annual_kwh * fixed_price_p / 100

    if battery_kwh > 0:
        useable = battery_kwh * 0.8
        cycles_per_day = actual_dispatch / (useable * 365) if useable > 0 else 0
    else:
        cycles_per_day = None

    return {
        "fixed_cost": fixed_cost,
        "agile_net": agile_net,
        "saving": fixed_cost - agile_net,
        "saving_pct": (fixed_cost - agile_net) / fixed_cost * 100 if fixed_cost > 0 else 0,
        "grid_import_kwh": sum(grid_import),
        "export_kwh": sum(export),
        "solar_self_kwh": sum(solar_by_hour) - sum(export),
        "battery_dispatch_kwh": actual_dispatch,
        "battery_cycles_per_day": cycles_per_day,
    }


def all_scenarios(annual_kwh, fixed_price_p, region, product,
                  solar_kwp=4.0, battery_kwh=13.5, shift_pct=0.30, seg_rate_p=0.0,
                  discharge_power_kw=None):
    """Run the four standard scenarios. Returns a list of dicts ready for tabular display."""
    mean_tariff = get_mean_agile_by_hour(region, product)
    profile = get_profile(product)

    # Product-specific load-shift targets:
    # - Commercial (heating): pre-heat in the 2 settlement periods (hour 15)
    #   immediately before the 4-7pm peak, and catch-up reheat in the 2 settlement
    #   periods (hour 19) immediately after. Realistic for heat-on-demand systems
    #   that lack the thermal mass to shift heating overnight.
    # - Domestic (flexible loads — dishwasher / washing / EV charging):
    #   move to cheap overnight + solar-peak midday hours where load is genuinely
    #   deferrable for hours-to-half-a-day.
    if product == "SHAPE_SHIFTERS":
        target_hours = (15, 19)
        shift_qualifier = "heating peak load"
    else:
        target_hours = (0, 1, 2, 3, 4, 11, 12, 13)
        shift_qualifier = "evening peak load"

    shifted = apply_load_shift(profile, shift_pct, target_hours=target_hours)

    rows = [
        {
            "label": "Switch to the RenewaBlox Solution (no behaviour change)",
            **compute_scenario(annual_kwh, fixed_price_p, mean_tariff, profile),
        },
        {
            "label": f"+ Shift {int(shift_pct * 100)}% of {shift_qualifier}",
            **compute_scenario(annual_kwh, fixed_price_p, mean_tariff, shifted),
        },
        {
            "label": f"+ {solar_kwp:.2f} kWp solar (Topcon bifacial)",
            **compute_scenario(annual_kwh, fixed_price_p, mean_tariff, shifted,
                              solar_kwp=solar_kwp, seg_rate_p=seg_rate_p),
        },
        {
            "label": f"+ {battery_kwh:.2f} kWh battery (e.g. STREAM Ultra)",
            **compute_scenario(annual_kwh, fixed_price_p, mean_tariff, shifted,
                              solar_kwp=solar_kwp, battery_kwh=battery_kwh,
                              seg_rate_p=seg_rate_p,
                              discharge_power_kw=discharge_power_kw),
        },
    ]
    return rows
