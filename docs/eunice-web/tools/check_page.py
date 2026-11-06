"""Check the built explainer page in a real browser against HANDOVER.md.

    python docs/eunice-web/tools/check_page.py                 # checks docs/eunice-web/eunice.html
    python docs/eunice-web/tools/check_page.py --shots DIR     # also saves screenshots to DIR

Needs Playwright with Chromium (pip install playwright; python -m playwright install chromium).
It checks, and exits 1 if anything fails:
  * the regression numbers ("Numbers the page must show") at $34 and $40;
  * each of the six scenarios, opened from its deep link and from its chip: settings, zoom, outline,
    headline, story and the "Check £" figures to the penny, plus scenario 4's 4- vs 8-period night;
  * Previous / Next / Whole week, the arrow keys on the chart, and a toggle changed while a scenario is open;
  * no horizontal page scroll at 390 px, whatever is open;
  * no console errors or uncaught exceptions.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGE = Path(__file__).resolve().parents[1] / "eunice.html"

# HANDOVER.md, "Scenarios to run through".
SCENARIOS = [
    dict(n=1, head="Red-band evening", hp="34", bs="8", win="32-37", zoom="12-47", when="Mon 16:00–19:00",
         story="Day-ahead £85–105 plus the red-band credit (£34/MWh) puts export at £120–139. The miners stay off and all 371 kW goes to the grid. This happens on almost every weekday evening.",
         check=("£145.61", "£145.61", "£145.61")),
    dict(n=2, head="A normal day: export wins", hp="34", bs="8", win="300-331", zoom="288-335", when="Sun 06:00–22:00",
         story="Export is worth £70–103. At $34/PH/day the miners earn at most £66/MWh, even in efficient mode, so Eunice exports everything. Last year this was the case for 83% of engine-running hours.",
         check=("£505.05", "£505.05", "£505.05")),
    dict(n=3, head="Overnight slump: mine flat out", hp="34", bs="8", win="140-157", zoom="132-167", when="Wed 22:00 – Thu 07:00",
         story="Prices slide from £64 to £2. Eunice starts in efficient mode at 22:00, runs at full power (7.8 kW per miner) from midnight and eases back to efficient at 06:00 as prices recover.",
         check=("£207.36", "£205.76", "£98.05")),
    dict(n=4, head="A short dip isn't worth a start", hp="34", bs="8", win="285-289", zoom="276-299", when="Sat 22:30 – Sun 01:00",
         story="Prices dip to £54 and £39 for an hour, between £80–90. On the 8-period rule a start would lock the miners on for 4 hours, mostly into prices above £66, so Eunice keeps exporting. Switch to a 4-period minimum: it starts for 2 hours and earns about £1.40 more over the night, for one extra cycle.",
         check=("£63.03", "£63.03", "£63.03"), night=("£282.37", "£280.95")),
    dict(n=5, head="Locked in: efficient mode limits the cost", hp="34", bs="8", win="190-203", zoom="180-215", when="Thu 23:00 – Fri 06:00",
         story="A crash to £18 at 23:30 starts a run. The 8-period rule keeps the miners on through 00:00–02:00, when export is worth £63–76, so Eunice drops them to 6.2 kW and exports 75 kW. Mine-or-export runs at full power throughout.",
         check=("£167.02", "£159.61", "£147.53")),
    dict(n=6, head="Hashprice rises to $40", hp="40", bs="8", win="288-304", zoom="288-335", when="Sun 00:00–08:30",
         story="Efficient mining is now worth up to £77/MWh. The same Sunday morning that exported at $34 runs the miners at 6.2 kW and still exports 75 kW.",
         check=("£242.08", "£229.70", "£236.55")),
]

# HANDOVER.md, "Numbers the page must show": (element, text) pairs at each hashprice.
REGRESSION = {
    "34": [("#stateCards", "£65.63/MWh"), ("#stateCards", "£61.46/MWh"), ("#opsTable", "£65.63"), ("#opsTable", "£61.46"),
           ("#ladderTh", "full mining until £43.75"), ("#ladderTh", "efficient floor from £46.75"), ("#ladderTh", "stop & export above £65.75"),
           ("#weekStats", "Week value £5,013.73"), ("#weekStats", "Full starts 5"),
           ("#blockCallout", "£677/yr"), ("#blockTable", "+£677"),
           ("#blockCallout", "about 161 full start/stop cycles"), ("#blkCyc", "161"), ("#blkCyc", "142")],
    "40": [("#stateCards", "£77.21/MWh"), ("#stateCards", "£72.31/MWh"), ("#opsTable", "£77.21"), ("#opsTable", "£72.31"),
           ("#ladderTh", "full mining until £51.50"), ("#ladderTh", "efficient floor from £55.00"), ("#ladderTh", "stop & export above £77.25"),
           ("#weekStats", "Week value £5,210.59"), ("#weekStats", "Full starts 7"),
           ("#blockCallout", "£2,074/yr"), ("#blockTable", "+£2,074"),
           ("#blockCallout", "about 351 full start/stop cycles"), ("#blkCyc", "351"), ("#blkCyc", "244")],
}
FIXED = [("#stateCards", "343.5 kW"), ("#stateCards", "272.8 kW"), ("#stateCards", "Exported75 kW"),
         ("#opsTable", "371 kW"), ("#opsTable", "14.85"), ("#opsTable", "15.53"), ("#opsTable", "15.91"), ("#opsTable", "17.09"),
         ("#opsTable", "7.208"), ("#opsTable", "9.911"), ("#opsTable", "7.81"), ("#opsTable", "6.20")]


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


def chart(page):
    c = page.locator("#weekChart")
    return c.get_attribute("data-range"), c.get_attribute("data-window"), page.locator('#weekChart [data-role="window"]').count()


def figs(page):
    return tuple(text(page, f'#scenCard [data-fig="{k}"]') for k in ("eunice", "mine-or-export", "export-only"))


def no_hscroll(page, c, what):
    sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    c.ok(sw <= cw, f"no horizontal scroll at 390 px ({what}): scrollWidth {sw} > clientWidth {cw}")


def check_scenario_open(page, c, s, how):
    tag = f"scenario {s['n']} ({how})"
    c.eq((pressed(page, "hp"), pressed(page, "bs"), pressed(page, "strat")), (s["hp"], s["bs"], "partial"), f"{tag} settings")
    rng, win, outline = chart(page)
    c.eq((rng, win, outline), (s["zoom"], s["win"], 1), f"{tag} zoom, window and outline")
    c.ok(page.locator("#scenCard").is_visible(), f"{tag} caption card visible")
    c.eq(text(page, "#scenCard h3"), s["head"], f"{tag} headline")
    c.eq(text(page, "#scenCard p"), s["story"], f"{tag} story")
    c.ok(s["when"] in text(page, "#scenCard .when"), f"{tag} window label {s['when']!r} in {text(page, '#scenCard .when')!r}")
    c.eq(figs(page), s["check"], f"{tag} Check £ (Eunice / mine-or-export / export only)")
    if "night" in s:
        c.eq((text(page, '#scenCard [data-fig="night-4"]'), text(page, '#scenCard [data-fig="night-8"]')), s["night"],
             f"{tag} night, 4-period vs 8-period")
    c.eq(page.locator(f'#scenChips .chip[data-k="{s["n"]}"]').get_attribute("aria-pressed"), "true", f"{tag} chip pressed")


def run(path, shots):
    c = Checker()
    url = path.resolve().as_uri()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def new_page(width, height=900):
            pg = browser.new_page(viewport={"width": width, "height": height})
            pg.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(f"page error: {e}"))
            return pg

        # --- regression numbers, desktop width
        page = new_page(1280)
        page.goto(url)
        for hp in ("34", "40"):
            page.locator(f'#states .seg[data-bind="hp"] button[data-v="{hp}"]').click()
            for sel, want in REGRESSION[hp] + FIXED:
                c.ok(want in text(page, sel), f"${hp}: {sel} shows {want!r}")
        page.locator('#states .seg[data-bind="hp"] button[data-v="34"]').click()
        c.eq(chart(page), ("0-335", "", 0), "whole week shown by default")
        c.ok(page.locator("#scenCard").is_hidden(), "no caption card on the whole week")

        # --- each scenario from its deep link (a fresh load, as from a shared link)
        for s in SCENARIOS:
            page.goto("about:blank")
            page.goto(f"{url}#scenario-{s['n']}")
            check_scenario_open(page, c, s, "deep link")
            if shots:
                page.locator("#week").screenshot(path=str(Path(shots) / f"scenario-{s['n']}-1280.png"))

        # --- chips, Previous / Next, Whole week, arrow keys
        page.goto(url)
        for s in SCENARIOS:
            page.locator(f'#scenChips .chip[data-k="{s["n"]}"]').click()
            check_scenario_open(page, c, s, "chip")
            c.eq(page.evaluate("location.hash"), f"#scenario-{s['n']}", f"scenario {s['n']} chip sets the address")
        c.ok(page.locator("#scenNext").is_disabled(), "Next disabled on the last scenario")
        page.locator("#scenPrev").click()
        c.eq(chart(page)[0], SCENARIOS[4]["zoom"], "Previous steps back to scenario 5")
        page.locator("#scenAll").click()
        c.eq(chart(page), ("0-335", "", 0), "Whole week resets the zoom")
        c.ok(page.locator("#scenCard").is_hidden(), "Whole week hides the caption card")
        c.ok(page.locator("#scenPrev").is_disabled(), "Previous disabled on the whole week")
        page.locator("#scenNext").click()
        c.eq(chart(page)[0], SCENARIOS[0]["zoom"], "Next from the whole week opens scenario 1")
        page.locator("#weekChart").focus()
        page.keyboard.press("ArrowRight")
        page.keyboard.press("ArrowRight")
        c.eq(chart(page)[0], SCENARIOS[2]["zoom"], "two right-arrow presses on the chart reach scenario 3")
        page.keyboard.press("ArrowLeft")
        c.eq(chart(page)[0], SCENARIOS[1]["zoom"], "left arrow on the chart steps back to scenario 2")
        page.keyboard.press("Escape")
        c.eq(chart(page)[0], "0-335", "Escape on the chart returns to the whole week")

        # --- a toggle changed while a scenario is open keeps the zoom and recomputes the £
        page.goto(f"{url}#scenario-4")
        page.locator('#week .seg[data-bind="bs"] button[data-v="4"]').click()
        c.eq(chart(page)[:2], ("276-299", "285-289"), "scenario 4 keeps its zoom after switching to a 4-period minimum")
        c.eq(figs(page), ("£64.45", "£63.03", "£63.03"), "scenario 4 £ recomputed at a 4-period minimum")
        c.ok(page.locator("#scenCard [data-restore]").count() == 1, "scenario 4 offers to restore its settings")
        page.locator("#scenCard [data-restore]").click()
        c.eq(figs(page), SCENARIOS[3]["check"], "restoring scenario 4's settings restores its £")
        page.goto(f"{url}#scenario-3")
        page.locator('#week .seg[data-bind="strat"] button[data-v="binary"]').click()
        c.eq(figs(page), SCENARIOS[2]["check"], "scenario 3 £ unchanged by the strategy toggle (both strategies shown)")
        page.locator('#ladder .seg[data-bind="hp"] button[data-v="40"]').click()
        c.eq(chart(page)[:2], ("132-167", "140-157"), "scenario 3 keeps its zoom after a hashprice change elsewhere on the page")
        c.eq(pressed(page, "hp"), "40", "hashprice toggles stay in sync across sections")
        if shots:
            page.goto(url)
            page.screenshot(path=str(Path(shots) / "page-1280.png"), full_page=True)
        page.close()

        # --- 390 px: no horizontal page scroll, whatever is open
        page = new_page(390, 844)
        page.goto(url)
        no_hscroll(page, c, "whole week")
        page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        no_hscroll(page, c, "every 'Show the numbers' open")
        if shots:
            page.screenshot(path=str(Path(shots) / "page-390.png"), full_page=True)
        for s in SCENARIOS:
            page.goto("about:blank")
            page.goto(f"{url}#scenario-{s['n']}")
            check_scenario_open(page, c, s, "deep link, 390 px")
            no_hscroll(page, c, f"scenario {s['n']}")
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
