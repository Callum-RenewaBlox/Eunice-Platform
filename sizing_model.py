"""
Tailrace heat exchanger sizing model — verified handover version
=================================================================
Project : 1 MW data centre heat rejection into a run-of-river hydro
          tailrace (Scottish Highlands). Closed 30% glycol loop.
Origin  : Built in Claude.ai from 'Heat_Exchanger_TailRace_Study.docx',
          with corrections. Handed over to Claude Code 2026-06-12.

Key corrections vs the source study (see HANDOVER.md, Findings 1-4):
  1. The study's 120-150 m finned-tube target does NOT fit the
     1.0 x 0.9 x 0.8 m envelope at the stated 150-200 mm pitch.
     Honest single-module capacity is ~250-500 kW (+ DN125 margin).
  2. Bundle backwater (head loss in the generating flow path) costs
     generation and is missing from the study's parasitic comparison.
  3. The design point should be the low-river-flow coincident case,
     not peak flow — unless mining load tracks hydro generation.
  4. Referenced to finned area, the GLYCOL side dominates 1/U, so
     fin multipliers beyond ~3x have diminishing returns.

All units SI unless suffixed. Run `python sizing_model.py` for the
scenario table that reproduces the numbers in HANDOVER.md.
"""

from dataclasses import dataclass, field
import math

G = 9.81
RHO_WATER = 1000.0


# ----------------------------------------------------------------- design basis
@dataclass
class DesignBasis:
    q_duty_w: float = 1_000_000.0      # heat to reject, W
    glycol_cp: float = 3_800.0         # J/kg.K  (30% glycol)
    glycol_rho: float = 1_030.0        # kg/m3
    glycol_dt: float = 10.0            # K, loop temperature drop
    t_glycol_in: float = 50.0          # degC, supply to exchanger
    t_river: float = 10.0              # degC, average tailrace
    tailrace_q_max: float = 1.3        # m3/s
    tailrace_area: float = 0.8         # m2 (1.0 w x 0.8 d at exchanger)
    # drop-in envelope: 1.0 m (tube span) x 0.9 m (along flow) x 0.8 m (depth)
    env_flow_m: float = 0.9
    env_depth_m: float = 0.8
    tube_straight_m: float = 0.85      # usable straight after manifolds
    dn125_area_m2: float = 13.35       # pi * 0.125 * 34 m of submerged runs
    dn125_derate: float = 0.70         # slower local sweep, no fins


BASIS = DesignBasis()


# ----------------------------------------------------------------- thermal core
def glycol_flow(b: DesignBasis = BASIS):
    """Heat balance Q = mdot.cp.dT  ->  (mdot kg/s, vdot L/s)."""
    mdot = b.q_duty_w / (b.glycol_cp * b.glycol_dt)
    return mdot, mdot / b.glycol_rho * 1000.0


def lmtd(t_hot_in, t_hot_out, t_cold):
    """Log-mean temperature difference, river treated as isothermal
    (valid: 1 MW into 1.3 m3/s raises the river only ~0.18 K)."""
    d1, d2 = t_hot_in - t_cold, t_hot_out - t_cold
    if d2 <= 0:
        return 0.0
    if abs(d1 - d2) < 1e-9:
        return d1
    return (d1 - d2) / math.log(d1 / d2)


def u_effective(h_i=4000.0, h_o=4900.0, fin_mult=3.0, fin_eff=0.80,
                wall_t=0.002, wall_k=15.0, d_o=0.063, d_i=0.059,
                rf_i=0.0001, rf_o=0.0003):
    """Overall U referenced to the EFFECTIVE (finned) external area.

    1/U = (Ae/Ai)(1/hi + Rf,i) + (Ae/Am)(t/k) + 1/(eta_fin.ho) + Rf,o

    Returns (U, dict of resistance shares). With the defaults this
    gives U ~ 480 W/m2.K and shows the glycol side at ~53% of total —
    the basis of Finding 4.
    """
    ae_ai = fin_mult * d_o / d_i
    ae_am = fin_mult * d_o / ((d_o + d_i) / 2)
    r = {
        "glycol film":    ae_ai / h_i,
        "glycol fouling": ae_ai * rf_i,
        "wall":           ae_am * wall_t / wall_k,
        "river film":     1.0 / (fin_eff * h_o),
        "river fouling":  rf_o,
    }
    total = sum(r.values())
    return 1.0 / total, {k: v / total for k, v in r.items()}


def h_o_scaled(v_river, h_o_ref=4900.0, v_ref=1.62):
    """External crossflow coefficient ~ v^0.6 (Zukauskas exponent)."""
    return h_o_ref * (max(v_river, 0.01) / v_ref) ** 0.6


# ----------------------------------------------------------------- geometry
@dataclass
class Packing:
    tube_od_mm: float
    pitch_mm: float
    fin_mult: float
    n_flow: int = field(init=False)
    n_vert: int = field(init=False)
    n_tubes: int = field(init=False)
    length_m: float = field(init=False)
    area_bare_m2: float = field(init=False)
    area_eff_m2: float = field(init=False)
    fin_od_mm: float = field(init=False)

    def __post_init__(self, b: DesignBasis = BASIS):
        self.n_flow = int(b.env_flow_m * 1000 // self.pitch_mm)
        self.n_vert = int(b.env_depth_m * 1000 // self.pitch_mm)
        self.n_tubes = self.n_flow * self.n_vert
        self.length_m = self.n_tubes * b.tube_straight_m
        self.area_bare_m2 = math.pi * self.tube_od_mm / 1000 * self.length_m
        self.area_eff_m2 = self.area_bare_m2 * self.fin_mult
        # crude fin envelope: 3x multiplier ~ 1.8x OD with wide helical fins
        self.fin_od_mm = self.tube_od_mm * (1 + 0.4 * (self.fin_mult - 1))

    @property
    def fins_clash(self):
        return self.pitch_mm < self.fin_od_mm + 20  # 20 mm cleaning clearance

    @property
    def blockage_first_row(self):
        return self.n_vert * self.tube_od_mm / (BASIS.env_depth_m * 1000)


def duty_kw(u, area_m2, dt_lm):
    return u * area_m2 * dt_lm / 1000.0


def dn125_margin_kw(u, dt_lm, b: DesignBasis = BASIS):
    return u * b.dn125_area_m2 * dt_lm * b.dn125_derate / 1000.0


# ----------------------------------------------------------------- hydraulics
def bundle_backwater(v_approach, pack: Packing, f_row=0.35):
    """Order-of-magnitude tube-bank head loss (Zukauskas-style).
    Returns (dP_kPa, head_m, lost_generation_kW at tailrace Qmax).
    Uses BARE OD for gap velocity — i.e. optimistic; fins make it worse.
    Refine with vendor Kv data (priority task)."""
    gap = pack.pitch_mm - pack.tube_od_mm
    if gap <= 0:
        return float("inf"), float("inf"), float("inf")
    v_max = v_approach * pack.pitch_mm / gap
    dp = pack.n_flow * f_row * RHO_WATER * v_max ** 2 / 2.0     # Pa
    head = dp / (RHO_WATER * G)
    lost_kw = RHO_WATER * G * BASIS.tailrace_q_max * head / 1000.0
    return dp / 1000.0, head, lost_kw


def pump_power_kw(vdot_ls, dp_kpa, eta=0.70):
    return vdot_ls / 1000.0 * dp_kpa / eta


# ----------------------------------------------------------------- scenarios
def scenario_table():
    mdot, vdot = glycol_flow()
    dt_lm = lmtd(BASIS.t_glycol_in, BASIS.t_glycol_in - BASIS.glycol_dt,
                 BASIS.t_river)
    u, shares = u_effective()
    v = BASIS.tailrace_q_max / BASIS.tailrace_area

    print(f"Glycol flow            : {mdot:.1f} kg/s = {vdot:.1f} L/s")
    print(f"LMTD (50/40 vs 10 C)   : {dt_lm:.1f} K")
    print(f"U (fouled, eff. area)  : {u:.0f} W/m2.K")
    print("Resistance shares      : "
          + ", ".join(f"{k} {s:.0%}" for k, s in shares.items()))
    print(f"Tailrace core velocity : {v:.2f} m/s\n")

    hdr = (f"{'OD':>4} {'pitch':>6} {'fin':>4} | {'tubes':>5} {'len m':>6} "
           f"{'Aeff':>6} | {'coil kW':>7} {'+DN125':>7} {'total':>6} | "
           f"{'bw m':>5} {'lost kW':>7} | flags")
    print(hdr)
    print("-" * len(hdr))
    for od, pitch, fin in [(63, 200, 3.0), (63, 150, 3.0), (63, 120, 3.0),
                           (38, 100, 3.0), (25, 70, 3.0), (63, 70, 3.0)]:
        p = Packing(od, pitch, fin)
        q_coil = duty_kw(u, p.area_eff_m2, dt_lm)
        q_pipe = dn125_margin_kw(u, dt_lm)
        _, head, lost = bundle_backwater(v, p)
        flags = []
        if p.fins_clash:
            flags.append("FINS CLASH")
        if p.n_flow > 7:
            flags.append("many rows")
        print(f"{od:>4} {pitch:>6} {fin:>4.1f} | {p.n_tubes:>5} "
              f"{p.length_m:>6.0f} {p.area_eff_m2:>6.1f} | {q_coil:>7.0f} "
              f"{q_pipe:>7.0f} {q_coil + q_pipe:>6.0f} | {head:>5.2f} "
              f"{lost:>7.1f} | {' '.join(flags)}")

    print("\nStudy target check: 126 m of tube needs "
          f"{126 / BASIS.tube_straight_m:.0f} straights; at 150 mm pitch the "
          f"envelope holds {Packing(63, 150, 3.0).n_tubes} -> does not fit.")
    print("Pump powers (study basis): coil loop "
          f"{pump_power_kw(vdot, 150):.1f}-{pump_power_kw(vdot, 200):.1f} kW; "
          f"PHE total {pump_power_kw(vdot, 120) + pump_power_kw(47.8, 80):.1f}"
          f"-{pump_power_kw(vdot, 160) + pump_power_kw(47.8, 120):.1f} kW")


# =================================================================
# EXTENSIONS — Claude Code, 12 June 2026 (HANDOVER.md tasks 2, 3, 5
# and the hybrid-sizing half of task 1). Everything above this line
# is byte-identical to the verified handover version; the original
# scenario_table() still reproduces every HANDOVER.md number.
#
# New site facts folded in from 'Feasibility Study R1.0 30072025.pdf'
# (Contracts/Kinlochdamph):
#   * Turbine is a twin-jet Gilkes TURGO (999 kW, 114 m gross head,
#     rated flow 1.371 m3/s). Impulse machine -> tailwater rise eats
#     runner clearance ~1:1. Backwater is therefore a HARD CONSTRAINT
#     (clearance budget) first and an energy cost second; rho.g.Q.dh
#     is retained as the bounding energy figure.
#   * Scheme is islanded until ~2035 (SSEN export offer 2035), so in
#     the near term mining load MUST track generation (Finding 3's
#     'tracks' mode). 'constant' mode kept for the post-2035 case.
#   * Year-1 generation value ~ GBP 95/MWh (feasibility study).
# =================================================================

WATER_NU = 1.31e-6        # m2/s kinematic viscosity, water ~10 degC
GBP_PER_MWH = 95.0        # feasibility study year-1 mean gross revenue
NET_HEAD_M = 105.0        # ~114 m gross less pipeline losses (assumption)
ETA_TURBINE = 0.88        # Turgo near best efficiency point (assumption)


@dataclass
class TailraceSection:
    """The bundle sits in a WIDER downstream section than the 1.0 m
    channel used for the 1.62 m/s core figure. Width is an assumption
    pending a site measurement — flagged in the assumptions register."""
    wider_width_m: float = 1.4        # ASSUMPTION — measure on site
    depth_m: float = 0.8
    bundle_span_m: float = 1.0        # bundle frontal width
    k_bypass: float = 1.5             # contraction+expansion loss coeff

    @property
    def area_total(self):
        return self.wider_width_m * self.depth_m

    @property
    def area_bundle(self):
        return self.bundle_span_m * self.depth_m

    @property
    def area_bypass(self):
        return max(self.area_total - self.area_bundle, 0.0)


SECTION = TailraceSection()


# ------------------------------------------------- refined backwater (task 3)
def jakob_friction(re_max, pitch_ratio):
    """Per-row friction factor, STAGGERED tube bank (Jakob, as given in
    Holman 'Heat Transfer': dP = 2.f'.rho.v_max^2.N_rows). Valid for the
    Re ~ 1e4-2e5 range seen here. Replaces the f_row = 0.35 placeholder."""
    return (0.25 + 0.118 / (pitch_ratio - 1.0) ** 1.08) * re_max ** -0.16


def bundle_dp_refined(v_face, pack: Packing, fin_dp_mult=1.5):
    """Bundle pressure drop at a given FACE (approach) velocity.
    fin_dp_mult ~1.3-1.6 for widely spaced helical fins (ASSUMPTION —
    replace with vendor Kv data when quoted). Returns (dP_Pa, K_face)."""
    gap = pack.pitch_mm - pack.tube_od_mm
    if gap <= 0:
        return float("inf"), float("inf")
    v_max = v_face * pack.pitch_mm / gap
    re = max(v_max * pack.tube_od_mm / 1000 / WATER_NU, 1e3)
    f = jakob_friction(re, pack.pitch_mm / pack.tube_od_mm)
    dp = 2.0 * f * RHO_WATER * v_max ** 2 * pack.n_flow * fin_dp_mult
    k_face = dp / (0.5 * RHO_WATER * v_face ** 2) if v_face > 0 else 0.0
    return dp, k_face


def bypass_split(q_river, pack: Packing, sec: TailraceSection = SECTION,
                 fin_dp_mult=1.5, iters=6):
    """Parallel-path split between bundle and the open bypass strip in
    the wider section. Equal head loss across both paths:
        K_b.v_b^2 = K_byp.v_byp^2 ;  v_b.A_b + v_byp.A_byp = Q
    Fixed-point on K_b(Re). Returns dict with v_bundle, v_bypass,
    dP_Pa, head_m, share_through_bundle."""
    if sec.area_bypass <= 0:
        v_b = q_river / sec.area_bundle
        dp, _ = bundle_dp_refined(v_b, pack, fin_dp_mult)
        return {"v_bundle": v_b, "v_bypass": 0.0, "dp_pa": dp,
                "head_m": dp / (RHO_WATER * G), "bundle_share": 1.0}
    v_b = q_river / sec.area_total          # first guess: uniform
    for _ in range(iters):
        _, k_b = bundle_dp_refined(max(v_b, 0.01), pack, fin_dp_mult)
        ratio = math.sqrt(k_b / sec.k_bypass) if sec.k_bypass > 0 else 0.0
        v_b = q_river / (sec.area_bundle + sec.area_bypass * ratio)
    v_byp = v_b * ratio
    dp, _ = bundle_dp_refined(v_b, pack, fin_dp_mult)
    share = v_b * sec.area_bundle / q_river if q_river > 0 else 0.0
    return {"v_bundle": v_b, "v_bypass": v_byp, "dp_pa": dp,
            "head_m": dp / (RHO_WATER * G), "bundle_share": share}


def backwater_cost(head_m, q_river, run_hours=4380.0):
    """Bounding energy cost of tailwater rise. For the Gilkes TURGO the
    first-order effect is runner-clearance erosion (hard limit, confirm
    freeboard with Gilkes); rho.g.Q.dh is the upper-bound energy rate,
    exact only once clearance must be bought back. run_hours default
    4380 h = 50% capacity factor (ASSUMPTION — refine from FDC)."""
    lost_kw = RHO_WATER * G * q_river * head_m / 1000.0
    gbp_yr = lost_kw * run_hours * GBP_PER_MWH / 1000.0
    return lost_kw, gbp_yr


# ------------------------------------------- duty vs river flow (task 2)
def equilibrium_supply_temp(duty_w, u, area_eff_m2, t_river,
                            mdot=None, b: DesignBasis = BASIS,
                            include_dn125=True):
    """Glycol supply temperature at which the exchanger sheds `duty_w`
    into river water at t_river. Glycol pump assumed fixed-speed, so
    the loop dT scales with duty: dT = Q/(mdot.cp). Bisection on the
    supply temperature; returns degC (or None if > 95 degC)."""
    if mdot is None:
        mdot = b.q_duty_w / (b.glycol_cp * b.glycol_dt)   # 26.3 kg/s
    dt_loop = duty_w / (mdot * b.glycol_cp)
    a_pipe = b.dn125_area_m2 * b.dn125_derate if include_dn125 else 0.0
    ua = u * (area_eff_m2 + a_pipe)

    def shed(t_supply):
        return ua * lmtd(t_supply, t_supply - dt_loop, t_river)

    lo, hi = t_river + dt_loop + 0.05, 95.0
    if shed(hi) < duty_w:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if shed(mid) < duty_w:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def duty_vs_flow_table(pack: Packing, mode="tracks", t_river_seq=None,
                       fractions=(0.10, 0.20, 0.35, 0.50, 0.75, 1.00),
                       b: DesignBasis = BASIS):
    """Finding 3 quantified. For each river-flow fraction:
      * bundle velocity from the bypass split,
      * h_o scaled with v^0.6 -> new U,
      * duty demanded: 'tracks' = fraction x 1 MW (islanded, mining
        follows generation — the pre-2035 reality) or 'constant' = 1 MW
        (grid-import-backed, post-2035 question),
      * equilibrium glycol supply temperature.
    Returns list of row dicts."""
    if t_river_seq is None:
        # ASSUMPTION: low flow coincides with warm water in summer
        t_river_seq = {0.10: 16.0, 0.20: 15.0, 0.35: 12.0,
                       0.50: 10.0, 0.75: 8.0, 1.00: 7.0}
    rows = []
    for f in fractions:
        q_river = f * b.tailrace_q_max
        split = bypass_split(q_river, pack)
        h_o = h_o_scaled(split["v_bundle"])
        u, _ = u_effective(h_o=h_o)
        t_riv = t_river_seq.get(f, b.t_river) if isinstance(t_river_seq, dict) \
            else t_river_seq
        duty = (f if mode == "tracks" else 1.0) * b.q_duty_w
        t_sup = equilibrium_supply_temp(duty, u, pack.area_eff_m2, t_riv)
        lost_kw, gbp = backwater_cost(split["head_m"], q_river)
        rows.append({"fraction": f, "q_river": q_river, "t_river": t_riv,
                     "v_bundle": split["v_bundle"], "u": u,
                     "duty_kw": duty / 1000.0, "t_supply": t_sup,
                     "head_m": split["head_m"], "lost_kw": lost_kw,
                     "gbp_yr": gbp})
    return rows


# ------------------------------------------------- hybrid sizing (task 1)
def phe_trim(duty_kw_target, river_dt=5.0, dp_kpa=(80.0, 120.0), eta=0.70):
    """Secondary river-water side of a PHE trim. Returns (flow L/s,
    pump kW low, pump kW high)."""
    vdot_ls = duty_kw_target / (4.186 * river_dt)
    return vdot_ls, pump_power_kw(vdot_ls, dp_kpa[0], eta), \
        pump_power_kw(vdot_ls, dp_kpa[1], eta)


def penstock_fed_cost(vdot_ls, net_head=NET_HEAD_M, eta_t=ETA_TURBINE):
    """Forgone generation if the PHE secondary is fed from the penstock
    tap (feasibility study concept) instead of a low-head pump: water
    diverted upstream of the nozzles at full head. kW forgone."""
    return vdot_ls / 1000.0 * RHO_WATER * G * net_head * eta_t / 1000.0


def hybrid_table(b: DesignBasis = BASIS):
    """Coil sized honestly + balance covered three ways. Uses the
    63 mm / 150 mm / 3x reference packing at the design point."""
    pack = Packing(63, 150, 3.0)
    dt_lm = lmtd(b.t_glycol_in, b.t_glycol_in - b.glycol_dt, b.t_river)
    u, _ = u_effective()
    coil = duty_kw(u, pack.area_eff_m2, dt_lm)
    pipe = dn125_margin_kw(u, dt_lm)
    base = coil + pipe
    balance = b.q_duty_w / 1000.0 - base
    vdot, p_lo, p_hi = phe_trim(balance)
    return {"coil_kw": coil, "dn125_kw": pipe, "base_kw": base,
            "balance_kw": balance,
            "extra_bay_kw": coil,                       # per extra bay
            "bays_for_1mw": 1 + math.ceil(balance / coil),
            "phe_flow_ls": vdot, "phe_pump_lo": p_lo, "phe_pump_hi": p_hi,
            "penstock_kw": penstock_fed_cost(vdot)}


# ------------------------------------------------- sensitivity (task 5)
def sensitivity(pack: Packing, supplies=(45, 50, 55, 60),
                rivers=(4, 7, 10, 14, 18), b: DesignBasis = BASIS):
    """Total duty (coil + DN125) in kW for glycol supply x river temp.
    U held at the design-point value — at fixed pump speed the glycol
    side, which dominates 1/U, does not change with temperature."""
    u, _ = u_effective()
    grid = {}
    for ts in supplies:
        for tr in rivers:
            dt_lm = lmtd(ts, ts - b.glycol_dt, tr)
            grid[(ts, tr)] = (duty_kw(u, pack.area_eff_m2, dt_lm)
                              + dn125_margin_kw(u, dt_lm))
    return grid


# ------------------------------------------------------------ reporting
def extended_report():
    pack = Packing(63, 150, 3.0)
    v_core = BASIS.tailrace_q_max / BASIS.tailrace_area

    print("\n" + "=" * 79)
    print("EXTENSIONS — refined backwater, duty vs flow, hybrid, sensitivity")
    print("=" * 79)

    print("\n--- Refined backwater, reference packing 63 mm / 150 mm pitch / 3x fins")
    print(f"Wider section {SECTION.wider_width_m} x {SECTION.depth_m} m "
          f"(width is an ASSUMPTION), bypass K = {SECTION.k_bypass}, "
          f"fin dP mult = 1.5")
    old_dp, old_head, old_lost = bundle_backwater(v_core, pack)
    split = bypass_split(BASIS.tailrace_q_max, pack)
    lost_kw, gbp = backwater_cost(split["head_m"], BASIS.tailrace_q_max)
    print(f"Placeholder (f_row=0.35, no bypass) : {old_head:5.2f} m "
          f"-> {old_lost:5.1f} kW bound")
    print(f"Refined (Jakob + fins + bypass)     : {split['head_m']:5.2f} m "
          f"-> {lost_kw:5.1f} kW bound, ~GBP {gbp:,.0f}/yr at 50% CF")
    print(f"Bundle sees {split['v_bundle']:.2f} m/s "
          f"({split['bundle_share']:.0%} of flow); bypass "
          f"{split['v_bypass']:.2f} m/s")
    print("TURGO NOTE: first-order effect is runner-clearance erosion — "
          "treat head rise as a hard budget; confirm freeboard with Gilkes.")

    for mode, label in [("tracks", "mining load TRACKS generation "
                         "(islanded reality, pre-2035)"),
                        ("constant", "CONSTANT 1 MW (grid-import-backed, "
                         "post-2035 question)")]:
        print(f"\n--- Duty vs river flow — {label}")
        print(f"{'flow':>5} {'Q m3/s':>7} {'Triv':>5} {'v_bun':>6} "
              f"{'U':>4} | {'duty kW':>7} {'T_supply':>8} | {'bw m':>5} "
              f"{'lost kW':>7}")
        for r in duty_vs_flow_table(pack, mode=mode):
            tsup = f"{r['t_supply']:.1f}" if r["t_supply"] else "  >95!"
            print(f"{r['fraction']:>5.0%} {r['q_river']:>7.2f} "
                  f"{r['t_river']:>5.1f} {r['v_bundle']:>6.2f} "
                  f"{r['u']:>4.0f} | {r['duty_kw']:>7.0f} {tsup:>8} | "
                  f"{r['head_m']:>5.2f} {r['lost_kw']:>7.1f}")

    print("\n--- Hybrid sizing (coil honest + balance to 1 MW)")
    h = hybrid_table()
    print(f"Coil {h['coil_kw']:.0f} kW + DN125 {h['dn125_kw']:.0f} kW "
          f"= base {h['base_kw']:.0f} kW -> balance {h['balance_kw']:.0f} kW")
    print(f"  Path A  extra drop-in bays: {h['extra_bay_kw']:.0f} kW/bay -> "
          f"{h['bays_for_1mw']} bays total for 1 MW (zero extra parasitics, "
          f"more backwater)")
    print(f"  Path B  PHE trim {h['balance_kw']:.0f} kW: secondary "
          f"{h['phe_flow_ls']:.1f} L/s, pump {h['phe_pump_lo']:.1f}-"
          f"{h['phe_pump_hi']:.1f} kW")
    print(f"  Path B' penstock-fed secondary (feasibility-study concept): "
          f"forgoes {h['penstock_kw']:.1f} kW of generation — "
          f"{h['penstock_kw'] / max(h['phe_pump_hi'], 1e-9):.1f}x worse than "
          f"pumping; reject in both islanded and grid-connected eras")

    print("\n--- Sensitivity: total duty kW (63/150/3x + DN125), "
          "U fixed at design point")
    sups, rivs = (45, 50, 55, 60), (4, 7, 10, 14, 18)
    grid = sensitivity(pack, sups, rivs)
    print("supply\\river " + "".join(f"{tr:>7}" for tr in rivs))
    for ts in sups:
        print(f"{ts:>11}  " + "".join(f"{grid[(ts, tr)]:>7.0f}"
                                      for tr in rivs))
    print("\n40 degC return is at typical hydro-ASIC inlet limits "
          "(site units: Whatsminer M63 464T x88) — confirm ceiling "
          "before fixing the thermal design point.")


if __name__ == "__main__":
    scenario_table()
    extended_report()
