"""Check the built explainer page in a real browser against HANDOVER.md.

    python docs/eunice-web/tools/check_page.py                 # checks docs/eunice-web/eunice.html
    python docs/eunice-web/tools/check_page.py PAGE.html       # checks another build of it
    python docs/eunice-web/tools/check_page.py --shots DIR     # also saves screenshots to DIR

Needs Playwright with Chromium (pip install playwright; python -m playwright install chromium).
Expected values come from HANDOVER.md and from a small model of its own (below), worked out here in Python
from data/, never read back from the page. It checks, and exits 1 if anything fails:
  * the regression numbers ("Numbers the page must show") at $34 and $40, each in its own card, row or bar;
  * the decision ladder at four export values;
  * each of the six scenarios from its deep link and its chip: settings, zoom, the outline's position across
    both panels, the 3-hourly axis, the columns and their colours, headline, story, and the window's £ (with
    their labels) at every hashprice and minimum run, the handover's "Check £" figures included;
  * Previous / Next / Whole week, the arrow keys and focus, Back to the whole week, a toggle changed while a
    scenario is open;
  * every chart drawn at its box's width with labels of 11 px or more inside it, at 1280 and 390 px; the flow
    diagram's layout, the one-day view and its picker, a resize, and the table view;
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
    c.ok(sw <= cw, f"no horizontal scroll at 390 px ({what}): scrollWidth {sw} > clientWidth {cw}")


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
  return {cards, ops, bars, year};
}"""

CHARTS = ["flowChart", "sliceChart", "ladderScale", "weekChart", "blkRev", "blkCyc", "shareChart", "infoChart"]
# For each chart: is it drawn at the width of its box (one SVG unit = one CSS pixel), and is every label at least
# 11 px and inside the chart?
CHART_JS = """ids => ids.map(id => {
  const svg = document.getElementById(id), r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
  const scale = r.width / vb.width, bad = [];
  svg.querySelectorAll('text').forEach(t => {
    if (!t.textContent.trim()) return;
    const px = parseFloat(getComputedStyle(t).fontSize) * scale, b = t.getBBox();
    if (px < 10.95) bad.push(`${JSON.stringify(t.textContent)} at ${px.toFixed(1)} px`);
    if (b.x < -0.5 || b.x + b.width > vb.width + 0.5) bad.push(`${JSON.stringify(t.textContent)} outside the chart`);
  });
  return {id, width: r.width, vbw: vb.width, bad};
})"""

GEOMETRY_JS = """() => {
  const svg = document.getElementById('weekChart'), plot = svg.querySelector('[data-role=plot]'), win = svg.querySelector('[data-role=window]');
  const n = a => +plot.getAttribute(a);
  const out = {px: n('x'), pw: n('width'), py: n('y'), ph: n('height'),
    times: [...svg.querySelectorAll('text')].map(t => t.textContent).filter(s => /^[0-9]{2}:[0-9]{2}$/.test(s)),
    cols: [...svg.querySelectorAll('g[shape-rendering=crispEdges] rect')].map(r => r.getAttribute('fill').toUpperCase())};
  if (win) { const cs = getComputedStyle(win);
    Object.assign(out, {wx: +win.getAttribute('x'), ww: +win.getAttribute('width'), wy: +win.getAttribute('y'), wh: +win.getAttribute('height'),
      stroke: parseFloat(cs.strokeWidth), strokeColour: cs.stroke, visible: cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0}); }
  return out;
}"""
FULL, EFF = "#D06A1F", "#9A4A9E"


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


def check_geometry(page, c, s, hp, bs):
    """What is drawn, not what the page says: the outline over the window, the 3-hourly axis, the columns."""
    tag = f"scenario {s['n']} drawing"
    g = page.evaluate(GEOMETRY_JS)
    (z0, z1), (w0, w1) = s["zoom"], s["win"]
    n = z1 - z0 + 1
    ex, ew = g["px"] + g["pw"] * (w0 - z0) / n, g["pw"] * (w1 - w0 + 1) / n
    c.ok(abs(g["wx"] - ex) < 0.6 and abs(g["ww"] - ew) < 0.6, f"{tag}: outline at x {g['wx']:.1f} width {g['ww']:.1f}, want {ex:.1f} / {ew:.1f}")
    c.ok(g["wy"] <= g["py"] and g["wy"] + g["wh"] >= g["py"] + g["ph"], f"{tag}: outline spans both panels")
    c.ok(g["stroke"] >= 2 and g["visible"] and g["strokeColour"] not in ("none", "rgba(0, 0, 0, 0)"), f"{tag}: outline visible ({g['stroke']}, {g['strokeColour']})")
    c.eq(g["times"], [hh_time(i) for i in range(z0, z1 + 2) if i % 6 == 0], f"{tag}: hourly axis labelled every 3 hours")
    v = WEEK["variants"][f"hp{hp}_b{bs}_partial"]
    want = sorted(FULL if v["mode"][i] == "M" else EFF for i in range(z0, z1 + 1) if v["miner_kw"][i] > 0)
    c.eq(sorted(g["cols"]), want, f"{tag}: one column per mining half-hour, coloured by state")


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
        c.eq(chart(page), ("0-335", "", 0), "whole week shown by default")
        c.ok(page.locator("#scenCard").is_hidden(), "no caption card on the whole week")
        check_charts(page, c, "1280 px")
        c.eq(page.locator("#flowChart").get_attribute("data-layout"), "horizontal", "flow diagram is horizontal at 1280 px")
        c.ok(page.locator("#dayPick").is_hidden(), "no day picker at 1280 px")
        # move over every chart so the hover handlers run (their errors reach the console check)
        for cid in ("weekChart", "sliceChart", "blkRev", "blkCyc", "shareChart", "infoChart", "ladderScale"):
            box = page.locator(f"#{cid}").bounding_box()
            page.mouse.move(box["x"] + 2, box["y"] + box["height"] / 2)
            for k in range(1, 12):
                page.mouse.move(box["x"] + box["width"] * k / 12, box["y"] + box["height"] * (0.3 + 0.04 * k))
        page.mouse.move(5, 5)

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
                if hp == s["hp"]:
                    click_toggle(page, "bs", s["bs"])
                    check_geometry(page, c, s, hp, s["bs"])
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
        page.evaluate("location.hash = '#week'")
        page.wait_for_function("document.getElementById('weekChart').dataset.range === '0-335'")
        c.eq(chart(page), ("0-335", "", 0), "going back to #week closes the scenario")

        # --- a toggle changed elsewhere on the page while a scenario is open
        page.goto(f"{url}#scenario-3")
        click_toggle(page, "strat", "binary")
        c.eq(figs(page), SCENARIOS[2]["check"], "scenario 3 £ unchanged by the strategy toggle (both strategies shown)")
        g = page.evaluate(GEOMETRY_JS)
        v = WEEK["variants"]["hp34_b8_binary"]
        c.eq(sorted(g["cols"]), sorted(FULL if v["mode"][i] == "M" else EFF for i in range(132, 168) if v["miner_kw"][i] > 0),
             "the strategy toggle redraws the columns from mine-or-export's plan")
        click_toggle(page, "hp", 40, "ladder")
        c.eq(chart(page)[:2], ("132-167", "140-157"), "scenario 3 keeps its zoom after a hashprice change elsewhere on the page")
        c.eq(pressed(page, "hp"), "40", "hashprice toggles stay in sync across sections")
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
        page.locator('#dayPick .dayb[data-day="3"]').click()
        c.eq(chart(page)[0], "144-191", "day picker shows Thursday")
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
            c.ok(page.locator("#dayPick").is_hidden(), f"scenario {s['n']}: no day picker while a scenario is open")
            if shots:
                page.locator("#week").screenshot(path=str(Path(shots) / f"scenario-{s['n']}-390.png"))
        page.close()
        browser.close()

    c.eq(errors, [], "console errors and uncaught exceptions")
    print(f"{c.passes} checks passed, {len(c.failures)} failed")
    return not c.failures


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("page", nargs="?", type=Path, default=PAGE)
    ap.add_argument("--shots", help="directory to save screenshots in")
    a = ap.parse_args()
    if a.shots:
        Path(a.shots).mkdir(parents=True, exist_ok=True)
    sys.exit(0 if run(a.page, a.shots) else 1)


if __name__ == "__main__":
    main()
