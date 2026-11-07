"""Check the built explainer page in a real browser against HANDOVER.md.

    python docs/eunice-web/tools/check_page.py                 # checks docs/eunice-web/eunice.html
    python docs/eunice-web/tools/check_page.py PAGE.html       # checks another build of it
    python docs/eunice-web/tools/check_page.py --shots DIR     # also saves screenshots to DIR

Needs Playwright with Chromium (pip install playwright; python -m playwright install chromium).
Expected values come from HANDOVER.md and from a small model of its own (below), worked out here in Python
from data/, never read back from the page. It checks, and exits 1 if anything fails:
  * the regression numbers ("Numbers the page must show") at $34 and $40, each in its own card, row or bar,
    and every cell of the operating-points and year tables, the callout, the bars' colours and the share bars;
  * the decision ladder at four export values, and its split bar's proportions;
  * each of the six scenarios from its deep link and its chip: settings, zoom, headline, story, and the window's
    £ (with their labels) at every hashprice and minimum run, the handover's "Check £" figures included;
  * the week chart as drawn, measured: a column per mining half-hour at its place, as tall as the miners plus
    cooling and coloured by state; the export-value line; the red band; the hour axis labelled every 3 hours;
    the outline across both panels and above the columns; at 1280 and 390 px, for the whole week, a day and
    each scenario, and after the strategy toggle;
  * the tooltips' contents against the model, and a tooltip on every chart, by mouse and by touch;
  * the table view cell by cell; Previous / Next / Whole week, the arrow keys, focus rings and focus, Back;
  * every chart drawn at its box's width with labels of 11 px or more, inside it and not on top of each other;
    page text of 11.5 px or more at 390 px; the flow diagram's layout and arrows, the one-day view, its picker
    and a swipe, a resize;
  * no horizontal page scroll at 390 px, whatever is open, and no console errors or uncaught exceptions.
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

D = Path(__file__).resolve().parents[1]
PAGE = D / "eunice.html"

# HANDOVER.md, "Scenarios to run through". win and zoom are inclusive half-hour indices.
SCENARIOS = [
    dict(n=1, head="Red-band evening", hp=34, bs=8, win=(32, 37), zoom=(12, 47), when="Mon 16:00–19:00",
         story="Day-ahead £85–105 plus the red-band credit (£34/MWh) puts export at £120–139. The miners stay off and all 371 kW goes to the grid. This happens on almost every weekday evening.",
         check=("£145.61", "£145.61", "£145.61")),
    dict(n=2, head="A normal day: export wins", hp=34, bs=8, win=(300, 331), zoom=(288, 335), when="Sun 06:00–22:00",
         story="Export is worth £70–103. At $34/PH/day the miners earn at most £66/MWh, even in efficient mode, so Eunice exports everything. Last year this was the case for 83% of engine-running hours.",
         check=("£505.05", "£505.05", "£505.05")),
    dict(n=3, head="Overnight slump: mine flat out", hp=34, bs=8, win=(140, 157), zoom=(132, 167), when="Wed 22:00 – Thu 07:00",
         story="Prices slide from £64 to £2. Eunice starts in efficient mode at 22:00, runs at full power (7.8 kW per miner) from midnight and eases back to efficient at 06:00 as prices recover.",
         check=("£207.36", "£205.76", "£98.05")),
    dict(n=4, head="A short dip isn't worth a start", hp=34, bs=8, win=(285, 289), zoom=(276, 299), when="Sat 22:30 – Sun 01:00",
         story="Prices dip to £54 and £39 for an hour, between £80–90. On the 8-period rule a start would lock the miners on for 4 hours, mostly into prices above £66, so Eunice keeps exporting. Switch to a 4-period minimum: it starts for 2 hours and earns about £1.40 more over the night, for one extra cycle.",
         check=("£63.03", "£63.03", "£63.03"), night=(280, 299), night_check=("£282.37", "£280.95")),
    dict(n=5, head="Locked in: efficient mode limits the cost", hp=34, bs=8, win=(190, 203), zoom=(180, 215), when="Thu 23:00 – Fri 06:00",
         story="A crash to £18 at 23:30 starts a run. The 8-period rule keeps the miners on through 00:00–02:00, when export is worth £63–76, so Eunice drops them to 6.2 kW and exports 75 kW. Mine-or-export runs at full power throughout.",
         check=("£167.02", "£159.61", "£147.53")),
    dict(n=6, head="Hashprice rises to $40", hp=40, bs=8, win=(288, 304), zoom=(288, 335), when="Sun 00:00–08:30",
         story="Efficient mining is now worth up to £77/MWh. The same Sunday morning that exported at $34 runs the miners at 6.2 kW and still exports 75 kW.",
         check=("£242.08", "£229.70", "£236.55")),
]
FIG_LABELS = ("Eunice (3 states)", "Mine or export (same minimum run)", "Export only")

# HANDOVER.md, "Numbers the page must show", placed where each belongs.
CARDS = {  # state card → (row → text) at $34 and $40
    34: {"Full mining": {"Earns": "£61.46/MWh", "Miners draw": "343.5 kW", "Efficiency": "15.91 J/TH", "Exported": "0 kW"},
         "Efficient mining + export": {"Earns": "£65.63/MWh", "Miners draw": "272.8 kW", "Efficiency": "14.85 J/TH", "Exported": "75 kW"}},
    40: {"Full mining": {"Earns": "£72.31/MWh"}, "Efficient mining + export": {"Earns": "£77.21/MWh"}},
}
OPS = {  # operating-points row → {column: text}; columns: kW per miner, total draw, J/TH, £/MWh
    34: {"Efficient": {0: "6.20", 2: "14.85", 3: "£65.63"}, "Installed": {0: "7.208", 2: "15.53"},
         "Full surplus": {0: "7.81", 1: "371 kW", 2: "15.91", 3: "£61.46"}, "Max overclock": {0: "9.911", 2: "17.09"}},
    40: {"Efficient": {3: "£77.21"}, "Full surplus": {3: "£72.31"}},
}
LADDER = {34: ("£43.75", "£46.75", "£65.75"), 40: ("£51.50", "£55.00", "£77.25")}
WEEK_STATS = {34: ("£5,013.73", "5", ("31", "44", "261"), "+£14.28"), 40: ("£5,210.59", "7", ("41", "117", "178"), "+£50.49")}
YEAR_8 = {34: ("+£677", "161", "142"), 40: ("+£2,074", "351", "244")}
# section 3 at $34: export value → (mode badge, split text or None, cmp table rows or None)
SLIDER = {40: ("Full mining", None, None),
          45: ("Trimming toward efficient", None, None),
          60: ("Efficient mining + export", "Miners 272.8 kW (6.20 kW each) · cooling 23 kW · exported 75 kW",
               ["Export everything £11.13", "Mine everything (full) £11.40", "Eunice’s choice £11.96", "Gain over the better single option £0.56"]),
          70: ("Stop & export everything", "Miners off · all 371 kW exported", None)}

# ---------------------------------------------------------------- the reference model (HANDOVER.md, "Data contract")
WEEK = json.loads((D / "data" / "week.json").read_text(encoding="utf-8"))
YEAR = json.loads((D / "data" / "year_blocks.json").read_text(encoding="utf-8"))
N, INST, THS, ALPHA, S, FIXED, COOLER, GBPUSD = 44, 7.208, 464, 0.70, 371, 5, 25 / 381.6, 1.3413


def K(hp):  # £/h per kW^alpha
    return N * THS * (1 / (N * INST)) ** ALPHA / 1000 * hp / 24 / GBPUSD


def window_gbp(key, a, b, hp):
    """0.5 × (export value × (371 − P − parasitic(P)) / 1000 + K·P^0.7), summed over a..b; key None = export only."""
    total = 0.0
    for i in range(a, b + 1):
        P = WEEK["variants"][key]["miner_kw"][i] if key else 0.0
        par = FIXED + COOLER * P if P > 0 else 0.0
        total += 0.5 * (WEEK["export_value"][i] * (S - P - par) / 1000 + (K(hp) * P ** ALPHA if P > 0 else 0.0))
    return total


def money(v, d=2):
    return ("−" if v < 0 else "") + "£" + f"{abs(v):,.{d}f}"


def hh_time(i):
    sp = i % 48
    return f"{sp // 2:02d}:{'30' if sp % 2 else '00'}"


def scenario_figs(s, hp, bs):
    a, b = s["win"]
    return tuple(money(window_gbp(k, a, b, hp)) for k in (f"hp{hp}_b{bs}_partial", f"hp{hp}_b{bs}_binary", None))


# ---------------------------------------------------------------- browser helpers
class Checker:
    def __init__(self):
        self.failures, self.passes = [], 0

    def ok(self, cond, what):
        if cond:
            self.passes += 1
        else:
            self.failures.append(what)
            print("FAIL  " + what)

    def eq(self, got, want, what):
        self.ok(got == want, f"{what}: got {got!r}, want {want!r}")


def text(page, sel):
    return " ".join((page.locator(sel).first.text_content() or "").split())


def pressed(page, bind):
    return page.locator(f'#week .seg[data-bind="{bind}"] button[aria-pressed="true"]').get_attribute("data-v")


def click_toggle(page, bind, value, section="week"):
    page.locator(f'#{section} .seg[data-bind="{bind}"] button[data-v="{value}"]').click()


def chart(page):
    c = page.locator("#weekChart")
    return c.get_attribute("data-range"), c.get_attribute("data-window"), page.locator('#weekChart [data-role="window"]').count()


def figs(page):
    return tuple(text(page, f'#scenCard [data-fig="{k}"]') for k in ("eunice", "mine-or-export", "export-only"))


def fig_labels(page):
    return tuple(page.evaluate("""() => [...document.querySelectorAll('#scenCard .scen-figs > div')]
        .map(d => d.querySelector('span').textContent.trim())"""))


def no_hscroll(page, c, what):
    sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    c.ok(sw <= cw, f"no horizontal page scroll ({what}): scrollWidth {sw} > clientWidth {cw}")


PAGE_FACTS = """() => {
  const cards = {};
  document.querySelectorAll('#stateCards .state').forEach(c => { const o = {}, dd = c.querySelectorAll('dd');
    c.querySelectorAll('dt').forEach((d, i) => o[d.textContent.trim()] = dd[i].textContent.trim());
    cards[c.querySelector('h3').textContent.trim()] = o; });
  const ops = {};
  document.querySelectorAll('#opsTable tr').forEach(tr => { const td = tr.querySelectorAll('td');
    if (td.length) ops[td[0].querySelector('b').textContent.trim()] = [...td].slice(1).map(t => t.textContent.trim()); });
  const bars = {};
  ['blkRev', 'blkCyc'].forEach(id => document.querySelectorAll(`#${id} text[data-series]`).forEach(t =>
    bars[`${id}/${t.dataset.block}/${t.dataset.series}`] = t.textContent.trim()));
  const year = {};
  document.querySelectorAll('#blockTable tr').forEach(tr => { const td = tr.querySelectorAll('td');
    if (td.length) year[td[0].textContent.trim().split(' ')[0]] = [...td].slice(1).map(t => t.textContent.trim()); });
  const big = {};
  document.querySelectorAll('#stateCards .state').forEach(c => big[c.querySelector('h3').textContent.trim()] = c.querySelector('.big').textContent.trim());
  const barFill = {};
  ['blkRev', 'blkCyc'].forEach(id => document.querySelectorAll(`#${id} rect[data-series]`).forEach(r =>
    barFill[`${id}/${r.dataset.block}/${r.dataset.series}`] = r.getAttribute('fill').toUpperCase()));
  const share = [...document.querySelectorAll('#shareChart rect')].map(r => [+r.getAttribute('y'), +r.getAttribute('width')]);
  return {cards, ops, bars, year, big, barFill, share};
}"""

CHARTS = ["flowChart", "sliceChart", "ladderScale", "weekChart", "blkRev", "blkCyc", "shareChart", "infoChart"]
# For each chart: is it drawn at the width of its box (one SVG unit = one CSS pixel), and is every label at least
# 11 px and inside the chart?
CHART_JS = """ids => ids.map(id => {
  const svg = document.getElementById(id), r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
  const scale = r.width / vb.width, bad = [];
  const boxes = [];
  svg.querySelectorAll('text').forEach(t => {
    if (!t.textContent.trim()) return;
    const px = parseFloat(getComputedStyle(t).fontSize) * scale, b = t.getBBox();
    if (px < 10.95) bad.push(`${JSON.stringify(t.textContent)} at ${px.toFixed(1)} px`);
    if (b.x < -0.5 || b.x + b.width > vb.width + 0.5 || b.y < -0.5 || b.y + b.height > vb.height + 0.5)
      bad.push(`${JSON.stringify(t.textContent)} outside the chart`);
    boxes.push([t.textContent, b]);
  });
  // no two labels on top of each other (a 1.5 px brush allowed for glyph boxes)
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [s, a] = boxes[i], [u, b] = boxes[j];
    const ox = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x), oy = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
    if (ox > 1.5 && oy > 1.5) bad.push(`${JSON.stringify(s)} overlaps ${JSON.stringify(u)}`);
  }
  return {id, width: r.width, vbw: vb.width, bad};
})"""

GEOMETRY_JS = """() => {
  const svg = document.getElementById('weekChart'), plot = svg.querySelector('[data-role=plot]'), win = svg.querySelector('[data-role=window]');
  const n = a => +plot.getAttribute(a), ex = svg.querySelector('[data-role=export]'), kids = [...svg.children];
  const colsG = svg.querySelector('g[shape-rendering=crispEdges]');
  const out = {px: n('x'), pw: n('width'), py: n('y'), ph: n('height'), axis: svg.dataset.axis || '',
    exY: +ex.getAttribute('y'), exH: +ex.getAttribute('height'),
    times: [...svg.querySelectorAll('text')].map(t => t.textContent).filter(s => /^[0-9]{2}(:[0-9]{2})?$/.test(s)),
    days: [...svg.querySelectorAll('text')].filter(t => /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) [0-9]+$/.test(t.textContent))
      .map(t => [+t.getAttribute('x'), t.textContent]).sort((a, b) => a[0] - b[0]).map(d => d[1]),
    cols: [...colsG.querySelectorAll('rect')].map(r => ({i: +r.dataset.i, x: +r.getAttribute('x'), w: +r.getAttribute('width'),
      y: +r.getAttribute('y'), h: +r.getAttribute('height'), fill: r.getAttribute('fill').toUpperCase()})),
    red: [...svg.querySelectorAll('[data-role=red]')].map(r => [+r.dataset.i, +r.getAttribute('x')]),
    line: (svg.querySelector('[data-role=line]').getAttribute('d').match(/-?[0-9.]+,-?[0-9.]+/g) || []).map(p => p.split(',').map(Number)),
    outlineAboveColumns: !win || kids.indexOf(win) > kids.indexOf(colsG)};
  if (win) { const cs = getComputedStyle(win);
    Object.assign(out, {wx: +win.getAttribute('x'), ww: +win.getAttribute('width'), wy: +win.getAttribute('y'), wh: +win.getAttribute('height'),
      stroke: parseFloat(cs.strokeWidth), strokeColour: cs.stroke, visible: cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0}); }
  return out;
}"""
FULL, EFF = "#D06A1F", "#9A4A9E"
TEAL, MUTED = "#156082", "#A6B3BD"
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parasitic(P):
    return FIXED + COOLER * P if P > 0 else 0.0


def hh_value(i, P, hp):
    return 0.5 * (WEEK["export_value"][i] * (S - P - parasitic(P)) / 1000 + (K(hp) * P ** ALPHA if P > 0 else 0.0))


def day_label(i):
    d = i // 48
    return f"{DAY_NAMES[d]} {int(WEEK['days'][d][-2:])}"


STATE_TIP = {"M": "Full mining", "P": "Efficient mining + export", "E": "Stop & export"}
STATE_TABLE = {"M": "Full mining", "P": "Efficient + export", "E": "Stop & export"}
BAND = {"r": "Red", "a": "Amber", "g": "Green"}


def tip_lines(i, key, hp):
    """The week chart's tooltip for half-hour i, worked out here."""
    P = WEEK["variants"][key]["miner_kw"][i]
    exp = max(0.0, S - P - parasitic(P))
    red = " (red band)" if WEEK["band"][i] == "r" else ""
    return [f"{day_label(i)} Nov {hh_time(i)}",
            f"Day-ahead £{WEEK['price'][i]:,.2f} · export value £{WEEK['export_value'][i]:,.2f}{red}",
            STATE_TIP[WEEK["variants"][key]["mode"][i]],
            f"Miners {P:,.1f} kW · exported {exp:,.0f} kW",
            f"This half-hour {money(hh_value(i, P, hp))}"]


def table_cells(i, key, hp):
    """A row of the week table for half-hour i, worked out here."""
    P = WEEK["variants"][key]["miner_kw"][i]
    return [f"{day_label(i)} {hh_time(i)}", BAND[WEEK["band"][i]], f"{WEEK['price'][i]:,.2f}", f"{WEEK['export_value'][i]:,.2f}",
            STATE_TABLE[WEEK["variants"][key]["mode"][i]], f"{P:,.1f}", f"{max(0.0, S - P - parasitic(P)):,.1f}", money(hh_value(i, P, hp))]


def ops_rows(hp):
    """The operating-points table (kW per miner, total draw, J/TH, £/MWh), worked out here."""
    pmax = min(N * 9.911, (S - FIXED) / (1 + COOLER))
    rows = {}
    for name, kw, txt_kw in (("Efficient", 6.2, "6.20"), ("Installed", INST, "7.208"), ("Full surplus", pmax / N, f"{pmax / N:.2f}"), ("Max overclock", 9.911, "9.911")):
        P = N * kw
        jth = kw * 1000 / (THS * (kw / INST) ** ALPHA)
        rows[name] = [txt_kw, f"{P + parasitic(P):,.0f} kW", f"{jth:.2f}", money(K(hp) * P ** ALPHA / (P + parasitic(P)) * 1000)]
    return rows


def check_charts(page, c, tag):
    for ch in page.evaluate(CHART_JS, CHARTS):
        c.ok(abs(ch["width"] - ch["vbw"]) <= 1.01, f"{tag}: #{ch['id']} drawn at its box width ({ch['vbw']} vs {ch['width']:.0f} px)")
        c.ok(not ch["bad"], f"{tag}: #{ch['id']} labels legible and inside the chart: {ch['bad'][:4]}")


def table_rows(page):
    return page.locator("#weekTable tbody tr").count(), page.locator("#weekTable tbody tr.win").count()


def open_table(page):
    """Open "Show the numbers" under the week chart; the table is drawn on the details' toggle event."""
    page.locator("#weekDetails summary").click()
    page.wait_for_function("document.getElementById('weekDetails').open && document.querySelector('#weekTable tbody tr')")


def check_regression(page, c, hp):
    f = page.evaluate(PAGE_FACTS)
    for card, rows in CARDS[hp].items():
        for row, want in rows.items():
            c.eq(f["cards"].get(card, {}).get(row), want, f"${hp}: '{card}' card, {row}")
    for name, cols in OPS[hp].items():
        for col, want in cols.items():
            got = f["ops"].get(name, [None] * 5)[col]
            c.eq(got, want, f"${hp}: operating points, '{name}' column {col + 1}")
    lt = text(page, "#ladderTh")
    for phrase, v in zip(("full mining until", "efficient floor from", "stop & export above"), LADDER[hp]):
        c.ok(f"{phrase} {v}" in lt, f"${hp}: ladder states '{phrase} {v}' in {lt!r}")
    week_v, starts, counts, adv = WEEK_STATS[hp]
    st = text(page, "#weekStats")
    for want in (f"Week value {week_v}", f"Full starts {starts}",
                 f"full {counts[0]} · efficient {counts[1]} · stopped {counts[2]}", f"this week {adv}"):
        c.ok(want in st, f"${hp}: week stat line shows {want!r} in {st!r}")
    adv_y, cyc_p, cyc_b = YEAR_8[hp]
    c.eq((f["year"].get("8", [None] * 5)[2], f["year"].get("8", [None] * 5)[3], f["year"].get("8", [None] * 5)[4]),
         (adv_y, cyc_p, cyc_b), f"${hp}: year table, 8-period advantage and cycles")
    for blk in ("4", "8", "12"):
        y = YEAR[str(hp)][blk]
        for series, rev, cyc in (("partial", y["partial_vs_base"], y["cycles_partial"]), ("binary", y["binary_vs_base"], y["cycles_binary"])):
            c.eq(f["bars"].get(f"blkRev/{blk}/{series}"), ("+" if rev > 0 else "") + money(rev, 0), f"${hp}: £/yr bar {blk}-period {series}")
            c.eq(f["bars"].get(f"blkCyc/{blk}/{series}"), f"{cyc:,}", f"${hp}: cycles bar {blk}-period {series}")
    cb = text(page, "#blockCallout")
    c.ok(f"{adv_y[1:]}/yr" in cb and f"about {cyc_p} full start/stop cycles" in cb, f"${hp}: recommendation callout figures in {cb[:120]!r}")
    Y = YEAR[str(hp)]
    eff = round((Y["8"]["share_partial"]["efficient"] + Y["8"]["share_partial"]["between"]) * 100)
    for want in (f"(4-period: {Y['4']['cycles_partial']}, 12-period: {Y['12']['cycles_partial']})",
                 f"That is {Y['8']['cycles_partial'] - Y['8']['cycles_binary']} more than mine-or-export", f"Efficient mining covers {eff}%"):
        c.ok(want in cb, f"${hp}: recommendation callout says {want!r}")
    c.eq(f["big"], {"Full mining": "7.8 kW", "Efficient mining + export": "6.2 kW", "Stop & export everything": "371 kW"}, f"${hp}: state cards' headline figures")
    for name, cells in ops_rows(hp).items():
        c.eq(f["ops"].get(name, [None] * 5)[:4], cells, f"${hp}: operating points, '{name}' row (worked out here)")
    for blk in ("4", "8", "12"):
        y = Y[blk]
        c.eq(f["year"].get(blk), [money(y["partial_vs_base"], 0), money(y["binary_vs_base"], 0), "+" + money(y["partial_minus_binary"], 0),
                                  str(y["cycles_partial"]), str(y["cycles_binary"])], f"${hp}: year table, {blk}-period row")
        for cid in ("blkRev", "blkCyc"):
            c.eq((f["barFill"].get(f"{cid}/{blk}/partial"), f["barFill"].get(f"{cid}/{blk}/binary")), (TEAL, MUTED), f"${hp}: #{cid} {blk}-period bar colours follow the legend")
    # the share bars: each segment's width in proportion to its share of engine-running hours
    s8 = Y["8"]
    rows = [[s8["share_partial"]["full"], s8["share_partial"]["efficient"] + s8["share_partial"]["between"], s8["share_partial"]["stop"]],
            [s8["share_binary"]["full"], s8["share_binary"]["stop"]]]
    by_row = {}
    for yv, w in f["share"]:
        by_row.setdefault(yv, []).append(w)
    got = [by_row[k] for k in sorted(by_row)]
    ok_w = len(got) == 2 and all(len(g) == len(r) and all(abs((gw + (1 if j else 0)) / sum(g[k] + (1 if k else 0) for k in range(len(g))) - share / sum(r)) < 0.01
                                                          for j, (gw, share) in enumerate(zip(g, r))) for g, r in zip(got, rows))
    c.ok(ok_w, f"${hp}: time-share bars in proportion to the year's shares ({got} vs {rows})")


def check_scenario_open(page, c, s, how):
    tag = f"scenario {s['n']} ({how})"
    c.eq((pressed(page, "hp"), pressed(page, "bs"), pressed(page, "strat")), (str(s["hp"]), str(s["bs"]), "partial"), f"{tag} settings")
    rng, win, outline = chart(page)
    c.eq((rng, win, outline), (f"{s['zoom'][0]}-{s['zoom'][1]}", f"{s['win'][0]}-{s['win'][1]}", 1), f"{tag} zoom, window and outline")
    vis = page.evaluate("""() => { const e = document.getElementById('scenCard'), cs = getComputedStyle(e);
        return !e.hidden && cs.display !== 'none' && cs.visibility === 'visible' && +cs.opacity === 1 && e.getBoundingClientRect().height > 50; }""")
    c.ok(vis, f"{tag} caption card visible")
    c.eq(text(page, "#scenCard h3"), s["head"], f"{tag} headline")
    c.eq(text(page, "#scenCard p"), s["story"], f"{tag} story")
    c.ok(s["when"] in text(page, "#scenCard .when"), f"{tag} window label {s['when']!r} in {text(page, '#scenCard .when')!r}")
    c.eq(figs(page), s["check"], f"{tag} Check £ (Eunice / mine-or-export / export only)")
    c.eq(fig_labels(page), FIG_LABELS, f"{tag} £ labels")
    if "night" in s:
        c.eq((text(page, '#scenCard [data-fig="night-4"]'), text(page, '#scenCard [data-fig="night-8"]')), s["night_check"],
             f"{tag} night, 4-period vs 8-period")
    c.eq(page.locator(f'#scenChips .chip[data-k="{s["n"]}"]').get_attribute("aria-pressed"), "true", f"{tag} chip pressed")


def check_drawing(page, c, tag, rng, key, win=None):
    """What the week chart draws, measured, not what the page says about itself: a column per mining half-hour at its
    place, with the height of the miners plus their cooling and the colour of its state; the export-value line through
    the export values (not the prices) at the columns' centres; the red band; the hour axis; the outline."""
    g = page.evaluate(GEOMETRY_JS)
    z0, z1 = rng
    n = z1 - z0 + 1
    v = WEEK["variants"][key]
    xs = lambda i: g["px"] + g["pw"] * (i - z0) / n
    want = {i: v for i in range(z0, z1 + 1) if WEEK["variants"][key]["miner_kw"][i] > 0}
    got = {col["i"]: col for col in g["cols"]}
    c.eq(sorted(got), sorted(want), f"{tag}: a column for each mining half-hour of {key}")
    bad = []
    for i, col in got.items():
        P = v["miner_kw"][i]
        h = g["exH"] * min(S, P + parasitic(P)) / S
        if abs(col["x"] - xs(i)) > 0.6 or not (g["pw"] / n - 0.1 <= col["w"] <= g["pw"] / n + 0.7) or abs(col["h"] - h) > 0.6 \
                or abs(col["y"] + col["h"] - (g["exY"] + g["exH"])) > 0.6 or col["fill"] != (FULL if v["mode"][i] == "M" else EFF):
            bad.append(i)
    c.ok(not bad, f"{tag}: columns at their half-hour, as tall as miners + cooling, coloured by state (wrong: {bad[:5]})")
    pts = g["line"]
    c.eq(len(pts), n, f"{tag}: the export-value line has a point per half-hour")
    if len(pts) == n:
        ev = WEEK["export_value"][z0:z1 + 1]
        lo, hi = min(range(n), key=lambda k: ev[k]), max(range(n), key=lambda k: ev[k])
        slope = (pts[hi][1] - pts[lo][1]) / (ev[hi] - ev[lo]) if ev[hi] != ev[lo] else 0
        off = max(abs(pts[k][1] - (pts[lo][1] + slope * (ev[k] - ev[lo]))) for k in range(n))
        offx = max(abs(pts[k][0] - (xs(z0 + k) + g["pw"] / n / 2)) for k in range(n))
        c.ok(slope < 0 and off < 0.3 and offx < 0.3, f"{tag}: the line follows the export value at the columns' centres (off by {off:.2f} / {offx:.2f} px)")
    red = sorted(i for i, x in g["red"] if abs(x - xs(i)) < 0.6)
    c.eq(red, [i for i in range(z0, z1 + 1) if WEEK["band"][i] == "r"], f"{tag}: red band shaded on the red-band half-hours")
    # every 3 hours wherever there is room for a two-digit label (24 px per 3 hours), whatever the page says it chose
    every = 6 if g["pw"] * 6 / n >= 24 else 12
    short = bool(g["times"]) and all(len(t) == 2 for t in g["times"])
    if n <= 96:
        times = [(hh_time(i)[:2] if short else hh_time(i)) for i in range(z0, z1 + 2) if i % every == 0]
        c.ok(g["times"] in (times, times[:-1]), f"{tag}: hour axis labelled evenly every {every // 2} h ({g['axis']}): {g['times']} vs {times}")
        days = [day_label(i) for i in range(z0, z1 + 1) if i % 48 == 0]
        c.ok(all(d in g["days"] for d in days), f"{tag}: each midnight named on the axis: {g['days']} vs {days}")
    else:
        c.eq(g["days"], [day_label(48 * d) for d in range(7)], f"{tag}: the whole week's days in order")
    if win:
        (w0, w1) = win
        ex, ew = xs(w0), g["pw"] * (w1 - w0 + 1) / n
        c.ok(abs(g["wx"] - ex) < 0.6 and abs(g["ww"] - ew) < 0.6, f"{tag}: outline at x {g['wx']:.1f} width {g['ww']:.1f}, want {ex:.1f} / {ew:.1f}")
        c.ok(g["wy"] <= g["py"] and g["wy"] + g["wh"] >= g["py"] + g["ph"], f"{tag}: outline spans both panels")
        c.ok(g["stroke"] >= 2 and g["visible"] and g["strokeColour"] not in ("none", "rgba(0, 0, 0, 0)") and g["outlineAboveColumns"],
             f"{tag}: outline visible above the columns ({g['stroke']}, {g['strokeColour']})")


def check_geometry(page, c, s, hp, bs, strat="partial"):
    check_drawing(page, c, f"scenario {s['n']} at ${hp}, {bs}-period, {strat}", s["zoom"], f"hp{hp}_b{bs}_{strat}", s["win"])


def hover_tip(page, i, rng):
    """Point at half-hour i on the week chart (scrolled into view) and read the tooltip's lines."""
    page.locator("#weekChart").scroll_into_view_if_needed()
    page.wait_for_timeout(120)            # the scroll's own event (which hides any tooltip) first
    g = page.evaluate(GEOMETRY_JS)
    box = page.locator("#weekChart").bounding_box()
    scale = box["width"] / page.evaluate("document.getElementById('weekChart').viewBox.baseVal.width")
    z0, z1 = rng
    n = z1 - z0 + 1
    page.mouse.move(box["x"] + (g["px"] + g["pw"] * (i - z0 + 0.5) / n) * scale, box["y"] + (g["py"] + g["ph"] * 0.4) * scale)
    shown = page.evaluate("document.getElementById('tip').style.opacity === '1'")
    return shown, [ln.strip() for ln in page.locator("#tip").inner_text().split("\n") if ln.strip()]


def check_tip(page, c, i, rng, key, hp, tag):
    shown, lines = hover_tip(page, i, rng)
    c.ok(shown, f"{tag}: the tooltip shows for {day_label(i)} {hh_time(i)}")
    c.eq(lines, tip_lines(i, key, hp), f"{tag}: the tooltip for {day_label(i)} {hh_time(i)}")


def hover_every_chart(page, c, tag):
    """Point at the middle of each chart's marks, scrolled into view, and see a tooltip each time."""
    for sel in ("#sliceChart rect", "#ladderScale rect", "#blkRev rect[data-series]", "#blkCyc rect[data-series]", "#shareChart rect", "#infoChart rect"):
        loc = page.locator(sel).first
        loc.scroll_into_view_if_needed()
        page.wait_for_timeout(120)
        loc.hover(force=True)
        shown = page.evaluate("document.getElementById('tip').style.opacity === '1'") and page.locator("#tip").inner_text().strip() != ""
        c.ok(shown, f"{tag}: hovering {sel} shows its tooltip")
        page.mouse.move(1, 1)


FOCUS_JS = "() => { const e = document.activeElement, s = getComputedStyle(e); return [e.id || e.className || e.tagName, s.outlineStyle, parseFloat(s.outlineWidth)]; }"


def check_focus_rings(page, c, selectors, tag):
    page.keyboard.press("Tab")                     # keyboard use, so :focus-visible applies to what is focused next
    for sel in selectors:
        page.locator(sel).first.focus()
        who, style, width = page.evaluate(FOCUS_JS)
        c.ok(style == "solid" and width >= 2, f"{tag}: {sel} shows a focus ring ({who}: {style} {width})")


HTML_TEXT_JS = """() => {
  const bad = [];
  document.querySelectorAll('body *').forEach(e => {
    if (e.closest('svg') || /^(SUP|SUB)$/.test(e.tagName) || !e.offsetParent || ![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    const px = parseFloat(getComputedStyle(e).fontSize);
    if (px < 11.5) bad.push(`${e.tagName}.${e.className}: ${px}px`);
  });
  return bad;
}"""


def run(path, shots):
    c = Checker()
    # The reference model must first reproduce every figure the handover gives.
    for s in SCENARIOS:
        c.eq(scenario_figs(s, s["hp"], s["bs"]), s["check"], f"reference model reproduces scenario {s['n']}'s Check £")
        if "night" in s:
            c.eq(tuple(money(window_gbp(f"hp{s['hp']}_b{b}_partial", *s["night"], s["hp"])) for b in (4, 8)), s["night_check"],
                 "reference model reproduces scenario 4's night")
    if c.failures:
        print("the reference model is wrong; stopping")
        return False

    url = path.resolve().as_uri()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def new_page(width, height=900):
            pg = browser.new_page(viewport={"width": width, "height": height})
            pg.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(f"page error: {e}"))
            return pg

        # --- regression numbers and the decision ladder, desktop width
        page = new_page(1280)
        page.goto(url)
        for hp in (34, 40):
            click_toggle(page, "hp", hp, "states")
            check_regression(page, c, hp)
        click_toggle(page, "hp", 34, "states")
        for e, (badge, split, rows) in SLIDER.items():
            page.evaluate("v => { const s = document.getElementById('eSlider'); s.value = v; s.dispatchEvent(new Event('input')); }", e)
            c.eq(text(page, "#modeBadge"), badge, f"ladder at £{e}: mode")
            if split:
                c.eq(text(page, "#splitText"), split, f"ladder at £{e}: split")
            if rows:
                got = page.evaluate("() => [...document.querySelectorAll('#cmpTable tr')].map(r => [...r.cells].map(c => c.textContent.trim()).join(' '))")
                c.eq(got, rows, f"ladder at £{e}: this half-hour earns")
        # the split bar at £60: miners, cooling and export in proportion
        page.evaluate("v => { const s = document.getElementById('eSlider'); s.value = v; s.dispatchEvent(new Event('input')); }", 60)
        widths = page.evaluate("() => [...document.querySelectorAll('#splitBar > div')].map(d => d.getBoundingClientRect().width)")
        P = N * 6.2
        want = [P / S, parasitic(P) / S, (S - P - parasitic(P)) / S]
        c.ok(len(widths) == 3 and all(abs(w / sum(widths) - x) < 0.01 for w, x in zip(widths, want)), f"ladder at £60: split bar in proportion ({widths})")
        c.eq(chart(page), ("0-335", "", 0), "whole week shown by default")
        c.ok(page.locator("#scenCard").is_hidden(), "no caption card on the whole week")
        check_charts(page, c, "1280 px")
        c.eq(page.locator("#flowChart").get_attribute("data-layout"), "horizontal", "flow diagram is horizontal at 1280 px")
        flow = " ".join(page.evaluate("() => [...document.querySelectorAll('#flowChart text')].map(t => t.textContent)"))
        for title in ("Day-ahead prices", "gDUoS credit", "Hashprice", "Expected surplus", "Eunice", "setpoint", "Foreman", "44 miners", "Grid export"):
            c.ok(title in flow, f"flow diagram names {title!r}")
        c.eq(page.locator("#flowChart path[marker-end]").count(), 7, "flow diagram: an arrow from each input, to Foreman, and to the miners and export")
        c.ok(page.locator("#dayPick").is_hidden(), "no day picker at 1280 px")
        check_drawing(page, c, "whole week, $34, 8-period, Eunice", (0, 335), "hp34_b8_partial")
        check_tip(page, c, 34, (0, 335), "hp34_b8_partial", 34, "whole week")
        check_tip(page, c, 146, (0, 335), "hp34_b8_partial", 34, "whole week")
        page.mouse.move(1, 1)
        hover_every_chart(page, c, "1280 px")
        click_toggle(page, "strat", "binary")
        check_drawing(page, c, "whole week, $34, 8-period, mine or export", (0, 335), "hp34_b8_binary")
        mb = WEEK["variants"]["hp34_b8_binary"]["mode"]
        st = text(page, "#weekStats")
        c.ok(f"full {mb.count('M')} · efficient {mb.count('P')} · stopped {mb.count('E')}" in st and "this week +£14.28" in st,
             f"mine or export: the week's half-hours and Eunice's advantage still +£14.28: {st!r}")
        click_toggle(page, "strat", "partial")
        check_focus_rings(page, c, ['.brandrow a.home', '#states .seg button', '#eSlider', '#scenChips .chip', '#scenNext', '#week .seg button', '#weekChart'], "1280 px")
        c.eq(page.evaluate("document.querySelector('.brandrow a.home').getAttribute('href')"), "/", "the wordmark leads to the RenewaBlox AI home page")

        # --- the week chart's table view follows the chart
        open_table(page)
        c.eq(table_rows(page), (336, 0), "table view lists all 336 half-hours of the week")
        c.eq(page.locator("#weekTable tfoot").count(), 0, "no total row for the whole week (the week value is the optimiser's)")
        page.locator('#scenChips .chip[data-k="3"]').click()
        c.eq(table_rows(page), (36, 18), "table view follows scenario 3's zoom and highlights its window")
        c.eq(text(page, "#weekTable [data-total]"), money(window_gbp("hp34_b8_partial", 132, 167, 34)), "table view total over scenario 3's zoom")
        c.ok("Wed 12 22:00" in text(page, "#weekTable tbody tr.win"), "table view's first window row is Wed 12 22:00")
        page.locator("#scenAll").click()
        page.locator("#weekDetails summary").click()

        # --- each scenario from its deep link (a fresh load, as from a shared link), then at every setting
        for s in SCENARIOS:
            page.goto("about:blank")
            page.goto(f"{url}#scenario-{s['n']}")
            check_scenario_open(page, c, s, "deep link")
            check_geometry(page, c, s, s["hp"], s["bs"])
            if shots:
                page.locator("#week").screenshot(path=str(Path(shots) / f"scenario-{s['n']}-1280.png"))
            for hp in (34, 40):
                click_toggle(page, "hp", hp)
                for bs in (4, 8, 12):
                    click_toggle(page, "bs", bs)
                    tag = f"scenario {s['n']} at ${hp}, {bs}-period"
                    c.eq(figs(page), scenario_figs(s, hp, bs), f"{tag}: £")
                    c.eq(fig_labels(page), FIG_LABELS, f"{tag}: £ labels")
                    c.ok(f"${hp}/PH/day, {bs}-period minimum" in text(page, "#scenCard .scen-note"), f"{tag}: note names the settings")
                    c.eq(chart(page)[:2], (f"{s['zoom'][0]}-{s['zoom'][1]}", f"{s['win'][0]}-{s['win'][1]}"), f"{tag}: zoom kept")
                    changed = (hp, bs) != (s["hp"], s["bs"])
                    c.eq(page.locator("#scenCard [data-restore]").count(), int(changed), f"{tag}: offers to restore the scenario's settings")
                    if "night" in s:
                        k4, k8 = (window_gbp(f"hp{hp}_b{b}_partial", *s["night"], hp) for b in (4, 8))
                        c.eq((text(page, '#scenCard [data-fig="night-4"]'), text(page, '#scenCard [data-fig="night-8"]')), (money(k4), money(k8)), f"{tag}: night")
                        c.ok(f"({'+' if k4 >= k8 else ''}{money(k4 - k8)})" in text(page, "#scenCard"), f"{tag}: night difference")
                    check_geometry(page, c, s, hp, bs)
            click_toggle(page, "hp", 40 if s["hp"] == 34 else 34)      # away from the scenario's settings, then restore them
            page.locator("#scenCard [data-restore]").focus()
            page.keyboard.press("Enter")
            c.eq(figs(page), s["check"], f"scenario {s['n']}: restoring its settings restores its £")
            c.eq(page.evaluate("document.activeElement.dataset.k"), str(s["n"]), f"scenario {s['n']}: focus moves to its chip after Restore")

        # --- chips, Previous / Next, Whole week, arrow keys, focus
        page.goto(url)
        for s in SCENARIOS:
            page.locator(f'#scenChips .chip[data-k="{s["n"]}"]').click()
            check_scenario_open(page, c, s, "chip")
            c.eq(page.evaluate("location.hash"), f"#scenario-{s['n']}", f"scenario {s['n']} chip sets the address")
        c.ok(page.locator("#scenNext").is_disabled(), "Next disabled on the last scenario")
        page.locator("#scenPrev").click()
        c.eq(chart(page)[0], "180-215", "Previous steps back to scenario 5")
        page.locator("#scenNext").focus()
        page.keyboard.press("Enter")
        c.eq(page.evaluate("document.activeElement.dataset.k || document.activeElement.id"), "6", "focus moves to chip 6 when Next is disabled under it")
        page.locator("#scenAll").focus()
        page.keyboard.press("Enter")
        c.eq(chart(page), ("0-335", "", 0), "Whole week resets the zoom")
        c.ok(page.locator("#scenCard").is_hidden(), "Whole week hides the caption card")
        c.ok(page.locator("#scenPrev").is_disabled(), "Previous disabled on the whole week")
        c.eq(page.evaluate("document.activeElement.dataset.k || document.activeElement.tagName"), "1", "focus moves to chip 1 after Whole week")
        page.locator("#scenNext").click()
        c.eq(chart(page)[0], "12-47", "Next from the whole week opens scenario 1")
        page.locator("#scenAll").focus()
        page.keyboard.press("Tab")
        c.eq(page.evaluate("document.activeElement.id"), "weekChart", "Tab from the scenario buttons reaches the chart")
        c.eq(page.evaluate("getComputedStyle(document.activeElement).outlineStyle"), "solid", "the chart shows a focus ring")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("ArrowRight")
        c.eq(chart(page)[0], "132-167", "two right-arrow presses on the chart reach scenario 3")
        page.keyboard.press("ArrowLeft")
        c.eq(chart(page)[0], "288-335", "left arrow on the chart steps back to scenario 2")
        page.keyboard.press("Escape")
        c.eq(chart(page)[0], "0-335", "Escape on the chart returns to the whole week")
        c.eq(text(page, "#scenStatus"), "Whole week shown.", "screen readers hear that the whole week is shown")
        page.locator('#scenChips .chip[data-k="2"]').click()
        c.ok(text(page, "#scenStatus").startswith("Scenario 2 of 6, A normal day: export wins."), "screen readers hear the scenario and its £")
        page.locator('nav.toc a[href="#week"]').click()
        page.wait_for_timeout(200)
        c.eq(chart(page)[:2], ("288-335", "300-331"), "the nav link to section 4 leaves the scenario open")
        page.evaluate("location.hash = ''")
        page.wait_for_function("document.getElementById('weekChart').dataset.range === '0-335'")
        c.eq(chart(page), ("0-335", "", 0), "going back to the page with no scenario in its address closes the scenario")

        # --- a toggle changed elsewhere on the page while a scenario is open
        page.goto(f"{url}#scenario-3")
        check_tip(page, c, 146, (132, 167), "hp34_b8_partial", 34, "scenario 3")
        check_tip(page, c, 141, (132, 167), "hp34_b8_partial", 34, "scenario 3")
        page.mouse.move(1, 1)
        click_toggle(page, "strat", "binary")
        c.eq(figs(page), SCENARIOS[2]["check"], "scenario 3 £ unchanged by the strategy toggle (both strategies shown)")
        check_geometry(page, c, SCENARIOS[2], 34, 8, "binary")
        click_toggle(page, "hp", 40, "ladder")
        c.eq(chart(page)[:2], ("132-167", "140-157"), "scenario 3 keeps its zoom after a hashprice change elsewhere on the page")
        c.eq(pressed(page, "hp"), "40", "hashprice toggles stay in sync across sections")
        check_tip(page, c, 146, (132, 167), "hp40_b8_binary", 40, "scenario 3 at $40, mine or export")
        page.mouse.move(1, 1)
        # the table view, cell by cell, at $40 and mine or export
        open_table(page)
        cells = page.evaluate("() => [...document.querySelectorAll('#weekTable tbody tr')].map(r => [...r.cells].map(c => c.textContent.trim()))")
        want = [table_cells(i, "hp40_b8_binary", 40) for i in range(132, 168)]
        c.eq(cells, want, "table view, every cell of scenario 3's zoom at $40, mine or export (worked out here)")
        c.eq(text(page, "#weekTable [data-total]"), money(window_gbp("hp40_b8_binary", 132, 167, 40)), "table view total at $40, mine or export")
        page.locator("#scenCard [data-restore]").click()
        c.eq(page.evaluate("() => document.querySelector('#weekTable tbody tr').cells[7].textContent"), money(hh_value(132, WEEK['variants']['hp34_b8_partial']['miner_kw'][132], 34)),
             "table view follows a change of settings while open")
        page.locator("#weekDetails summary").click()
        if shots:
            page.goto(url)
            page.screenshot(path=str(Path(shots) / "page-1280.png"), full_page=True)
        page.close()

        # --- 390 px: no horizontal page scroll, legible charts, one day at a time
        page = new_page(390, 844)
        page.goto(url)
        no_hscroll(page, c, "whole week")
        check_charts(page, c, "390 px")
        c.eq(page.locator("#flowChart").get_attribute("data-layout"), "vertical", "flow diagram is vertical at 390 px")
        c.eq((page.locator("#weekChart").get_attribute("data-layout"), chart(page)[0]), ("day", "0-47"),
             "week chart shows one day at a time at 390 px, Monday first")
        c.ok(page.locator("#dayPick").is_visible(), "day picker shown at 390 px")
        c.eq(page.evaluate(HTML_TEXT_JS), [], "390 px: no page text below 11.5 px (superscripts aside)")
        check_drawing(page, c, "390 px, Monday", (0, 47), "hp34_b8_partial")
        page.locator('#dayPick .dayb[data-day="3"]').click()
        c.eq(chart(page)[0], "144-191", "day picker shows Thursday")
        c.eq(page.evaluate("() => [...document.querySelectorAll('#dayPick .dayb')].map(b => b.getAttribute('aria-pressed'))"),
             ["false", "false", "false", "true", "false", "false", "false"], "the day picker shows Thursday as chosen")
        check_drawing(page, c, "390 px, Thursday", (144, 191), "hp34_b8_partial")
        check_tip(page, c, 146, (144, 191), "hp34_b8_partial", 34, "390 px, Thursday")
        page.mouse.move(1, 1)
        hover_every_chart(page, c, "390 px")
        check_focus_rings(page, c, ['#dayPick .dayb', '#scenChips .chip', '#week .seg button'], "390 px")
        open_table(page)
        c.eq(table_rows(page), (48, 0), "table view follows the day shown")
        no_hscroll(page, c, "week table open")
        page.locator("#weekDetails summary").click()
        page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        no_hscroll(page, c, "every 'Show the numbers' open")
        page.evaluate("document.querySelectorAll('details').forEach(d => d.open = false)")
        page.set_viewport_size({"width": 1280, "height": 900})
        page.wait_for_function("document.getElementById('weekChart').dataset.layout === 'week'")
        c.eq(chart(page)[0], "0-335", "widening the window redraws the whole week")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_function("document.getElementById('weekChart').dataset.layout === 'day'")
        check_charts(page, c, "390 px after a resize")
        if shots:
            page.goto(url)
            page.screenshot(path=str(Path(shots) / "page-390.png"), full_page=True)
        for s in SCENARIOS:
            page.goto("about:blank")
            page.goto(f"{url}#scenario-{s['n']}")
            check_scenario_open(page, c, s, "deep link, 390 px")
            no_hscroll(page, c, f"scenario {s['n']}")
            check_charts(page, c, f"scenario {s['n']}, 390 px")
            check_drawing(page, c, f"scenario {s['n']}, 390 px", s["zoom"], f"hp{s['hp']}_b{s['bs']}_partial", s["win"])
            c.ok(page.locator("#dayPick").is_hidden(), f"scenario {s['n']}: no day picker while a scenario is open")
            if shots:
                page.locator("#week").screenshot(path=str(Path(shots) / f"scenario-{s['n']}-390.png"))
        # a scenario with its settings changed (the Restore note) and its table open still fits
        page.goto(f"{url}#scenario-4")
        click_toggle(page, "hp", 40)
        click_toggle(page, "bs", 4)
        no_hscroll(page, c, "scenario 4 with its settings changed")
        open_table(page)
        no_hscroll(page, c, "scenario 4 with its table open")
        page.close()

        # --- 320 px (the narrowest phones): still no sideways scroll, legible charts, labels apart
        page = new_page(320, 640)
        for h in ("", "#scenario-3", "#scenario-5"):
            page.goto("about:blank")
            page.goto(url + h)
            no_hscroll(page, c, f"320 px {h or 'whole week'}")
            check_charts(page, c, f"320 px {h or 'whole week'}")
        page.close()

        # --- a phone with touch: taps show tooltips; a swipe changes the day
        ctx = browser.new_context(**p.devices["iPhone 13"])
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"page error: {e}"))
        page.goto(url)
        for sel in ("#weekChart [data-role=plot]", "#sliceChart rect", "#blkRev rect[data-series]"):
            loc = page.locator(sel).first
            loc.scroll_into_view_if_needed()
            page.wait_for_timeout(120)
            loc.tap(force=True)
            shown = page.evaluate("document.getElementById('tip').style.opacity === '1'") and page.locator("#tip").inner_text().strip() != ""
            c.ok(shown, f"touch: a tap on {sel} shows its tooltip")
        cdp = ctx.new_cdp_session(page)

        def swipe(dx):
            page.locator("#weekChart").scroll_into_view_if_needed()
            b = page.locator("#weekChart").bounding_box()
            x0, y0 = b["x"] + b["width"] / 2, b["y"] + b["height"] * 0.6
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
            for k in range(1, 6):
                cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + dx * k / 5, "y": y0}]})
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            page.wait_for_timeout(100)
        c.eq(chart(page)[0], "0-47", "touch: the week chart starts on Monday")
        swipe(-140)
        c.eq(chart(page)[0], "48-95", "touch: a swipe to the left shows the next day")
        swipe(140)
        c.eq(chart(page)[0], "0-47", "touch: a swipe to the right goes back a day")
        ctx.close()
        browser.close()

    c.eq(errors, [], "console errors and uncaught exceptions")
    print(f"{c.passes} checks passed, {len(c.failures)} failed")
    return not c.failures


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("page", nargs="?", type=Path, default=PAGE)
    ap.add_argument("--shots", help="directory to save screenshots in")
    ap.add_argument("--font", help="check the page as it looks in this font family (e.g. 'DejaVu Sans', whose glyphs are wide)")
    a = ap.parse_args()
    if a.shots:
        Path(a.shots).mkdir(parents=True, exist_ok=True)
    page = a.page
    if a.font:   # a copy of the page whose font stack is this family alone, so layouts are tested against other glyph widths
        import re
        import tempfile
        html = page.read_text(encoding="utf-8")
        html, n = re.subn(r'--font:[^;]+;', f'--font:"{a.font}",sans-serif;', html, count=1)
        assert n == 1, "the page's --font token is gone"
        page = Path(tempfile.mkdtemp()) / "eunice.html"
        page.write_text(html, encoding="utf-8")
        print(f"checking in {a.font}")
    sys.exit(0 if run(page, a.shots) else 1)


if __name__ == "__main__":
    main()
