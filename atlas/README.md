# RenewaBlox Atlas v2

One design system and one codebase for the map pages:

| Build | Output (repo root) | Wrapper | Default theme |
|---|---|---|---|
| Client Atlas (public) | `client_atlas_v2.html` | `app_client_atlas_v2.py` | Paper (light), "product" skin — see below |
| Investor Atlas (gated) | `investor_atlas_v2.html` | `app_investor_atlas_v2.py` | Night |
| Investor Atlas v3 (gated) | `investor_atlas_v3.html` | `app_investor_atlas_v3.py` | Night (dark), "product" skin + RenewaBlox brand — see "Investor Atlas v3" |

All outputs are single self-contained HTML files (data, CSS, JS and the Natural Earth basemap pack inlined;
MapLibre GL 4.7.1 from jsDelivr; Google Fonts: Inter + Newsreader for the investor v2 build, Open Sans for the
RenewaBlox-branded client and investor v3 builds). The build contract is
`DESIGN_SPEC.md` (design director's spec; section numbers below refer to it).

The internal `atlas.html` / `app_atlas.py` are not part of this tree.

---

## Quick start

```bash
python3 atlas/build.py                  # build both apps (an app without apps/<app>/template.html is skipped)
python3 atlas/build.py --only client    # one app
python3 atlas/build.py --check          # CI: fail if the committed HTML differs from a fresh build
python3 atlas/tests/test_build.py       # contract tests (or: python3 -m pytest atlas/tests)
streamlit run app_client_atlas.py       # local preview inside the real wrapper
streamlit run app_investor_atlas.py     # investor wrapper
```

Every build fails on any of:

* **canonical numbers** (spec appendix A) recomputed from `atlas/data` — e.g. SAM 129 sites / 143,571 kW,
  TAM 1,306 / 3,609,942 kW, Hydro 57 / 15,153 kW stranded, investor Σtcv £221,933,920, TCV Potential £7.16bn;
* the **MUST-preserve copy check** (spec 12) over the final HTML (PPA strings are checked whenever
  `core/js/ppa.js` is bundled);
* the **client-safety scan** (spec 13): client data keys ⊆ the allowlist, a case-insensitive deny-list over the
  *entire* `client_atlas_v2.html` (comments included: TCV, BTC, Bitcoin, treasury, rank-as-key, archetype, score,
  internal, "RenewaBlox CRM", model file names, methodology anchors, raw REGO labels…), and the code partition
  (no `investor/` path may appear in the client manifest);
* the **size budget**: data ≤ 170 KB per app, HTML ≤ 1.2 MB (client today: ~846 KB, data ~135 KB).

## Refreshing data

`atlas/data/**` is the source of truth. It was migrated from the v1 pages by `atlas/tools/extract_v1.py`,
which reads the frozen copies in `atlas/tools/v1/` (the live `client_atlas.html` / `investor_atlas.html` are
build outputs now). To refresh: regenerate the JSON files (same shapes), run the build, fix any assert the new
data trips (they are deliberately exact), commit data + outputs together.

**CRM alignment.** The CRM (crm.renewablox.com) numbers its cards after these files: SAM card #n is the SAM row of
`rank` n, and TAM card #n is row n of `data/shared/tam.json`. Never delete or reorder `tam.json` rows. A row found to
duplicate another row's plant stays in place and is listed in `tam_merged.json`; `build.py load_tam()` drops it (and
fails unless the merged rows' kW add up to the row they merge into). The optional SAM field `mec` is an export
connection shared with on-site load (cards say so); Melton Ross AD (#110) is the only site with one.

CRM corrections, 10 Oct 2026: SAM #110 "Prospect Farm" is Singleton Birch's Melton Ross AD (DN38 6AE; 1,993 kW,
onsite demand ≈ all, available for BM 0 kW, 2,800 kW export connection shared with the lime works; still awaiting a
BM figure, so no TCV), and its three FiT phases (TAM #1188, #1205, #1240) merge into TAM #110; TAM #479 Laynes
Piggery is farm AD (Biogas, 498 kW installed, 485 kW export), not landfill gas.

```
data/shared/tam.json           TAM rows (client-safe): key n f kw bm p bt ro units sam lat lon
data/shared/ppa_prices.json    realised[{m,p}], fwd[{k,from,to,p}], kpi{base12,win26,cal28,fit,asOf}, spread{value,note}, fit, cpi
data/shared/sam_kw_dno.json    build-only (never shipped): DNO-split installed kW where it differs (owner decision 1)
data/shared/tam_merged.json    build-only (never shipped): {into: {row key: key of the row it duplicates}}; dropped at build
data/client/sam.json           SAM map fields: key name site town la pc op t kw kwOn kwBm [mec] comm lat lon
data/client/ppa_register.json  SAM register fields: key ppa off self fitGen fitEnd yrsLeft rego ref
data/client/hydro.json         key name exp conf kw inst mec lat lon
data/investor/sam.json         client SAM fields + rank g dev inst av btc en tcv tcvT web (+ opSt where a note gave a company status)
data/investor/ppa_register.json v1 DATA.sites rows (raw, incl. rank, raw rego_status, offtaker_raw) + key
data/investor/hydro.json       client hydro fields + btc en tcv tcvT
data/investor/tam_extra.json   {key: {src, s, bm?}} — investor-only TAM fields (bm = v1 investor's explicit nulls)
data/investor/model.json       WHOLESALE, TAVG, as-of stamps
```

Public-text cleaning in `extract_v1.py` (both builds):
* research notes left inside v1 operator / developer strings (a parenthetical containing "verify", "TBC", "TODO", "site="
  or "?", e.g. "(in liquidation; site=Farmgen, Warton — verify owner)"), role notes ("(site op.; X was contractor)",
  "(landowner; …)", "(site owner; …)", "(developer; …)") and private individuals ("(Dr Stephen Temple)", "(Neil Gemmell)",
  "(Glyn family)") are stripped. Legal notes stay: "(fka …)", "t/a …", "(local authority)", "(1 of 3)";
* `smart_title()` display-cases SAM name / site / town, Hydro names and TAM names: ALL-CAPS words become Title Case
  (acronyms AD, STW, WWTW, CHP, UK, LLP …, Ltd / plc / EfW and postcodes kept), lower-case significant words are
  capitalised ("Station farm" → "Station Farm", "Banbury ad plant" → "Banbury AD Plant"), mixed-case words are kept;
* placeholder sites ("EXPORT", "IMPORT METER", "DATA NOT AVAILABLE") are dropped and trailing postcodes cut from site
  strings; the 6 sites v1 investor listed as "AD site (name withheld)" are titled `AD site (<outcode>)` in both builds
  (the operator stays in the Operator row); TAM "--Redacted--" names read "Name withheld (FiT register)".
A short factual company status inside a stripped note ("in liquidation", "in administration", "dissolved" …) is kept for the
investor build only, as `opSt` (FY85RP: "in liquidation"); cards, search, the PPA register and both CSVs show it as a muted
tag / its own column, never inside the name. `build.py investor_name_checks()` fails the investor build if a displayed name
field (name, site, town, la, op, dev, off) shows "verify" / "TBC" / "TODO" / "site=" / "??" or a status, if `opSt` is outside
the closed vocabulary, or if the page carries a v1 note fragment ("verify owner", "SPV TBC", "site=Farmgen" …).
`build.py public_text_checks()` fails either build if a data string still carries a note, or a public name / town has a
lower-case significant word, a placeholder or a trailing postcode. Owner to confirm: a sole-trader operator (SP78PX)
still shows in the public Operator row, as in v1, but never as the title. v1 cut 24 TAM names at 54 characters: the 8
that match a SAM site string are restored in full; the 16 with no full source end in "…" so the cut is visible (keys are
unchanged).

Keys: SAM = compact postcode (`KT160EF`); Hydro = `h-` + slug(name); TAM = RO reference, else
`t` + slug + `-` + 3-char geohash. `ref` is the neutral client register order (tier ascending, kW descending,
name); v1 `rank` never ships to the client.

REGO status is stored as a neutral code (`active` / `declining` / `ceased` / `none`); the label set comes from
the build (`switches.rego_labels`). Export arrangement is stored as a code (`neg` / `fit` / `btm` / `unk`).

## Owner decisions

Each is **one switch** in `atlas/apps/<app>/config.json` (`switches`), defaulted as below. Change it and rebuild.

| # | Decision | Switch | Default | Alternative |
|---|---|---|---|---|
| 1 | SAM capacity for Rotherdale Farm & Scrivelsby | `switches.sam_kw_source` | `"fit_register"` (owner decision, 27 Sep 2026) — 998 kW each (FiT register), SAM = **143.6 MW** in map, KPI and register; Universe "144 MW" | `"dno_split"` — 499 kW each (DNO onsite + BM split), SAM = 142.6 MW; the Universe string and asserts follow |
| 2 | Public REGO status wording | `switches.rego_labels` (client) | `"softened"` (owner decision, 27 Sep 2026) — Active / Certificates declining / No recent certificates / No REGO certificates | `"raw"` — v1 labels (the client-safety scan then stops denying them). The investor build always uses raw labels |
| 3 | Investor gate | — (decided) | **Streamlit Cloud viewer allowlist only** (owner decision, 27 Sep 2026): no password gate in code. Deploy the investor app with viewer access restricted to invited investors | — |
| 4 | TAM colour | `switches.tam_colour_mode` | `"fuels"` (owner decision, 27 Sep 2026): 9 per-fuel ring colours, one validated set per theme (`--fuel-0..8`, see "TAM fuel palette"); the legend (rows by site count), PNG legend, cards and search also name the fuel | `"families"`: 3 technology families + Other (CVD-safe) |
| 5 | `H2-2027*` asterisk | — | kept exactly as v1; no footnote invented | supply the footnote text to the PPA module |
| 6 | Copy-link base URLs | `publicUrl` (config) / secret `ATLAS_PUBLIC_URL` (overrides) | client `https://renewablox-client-atlas-v2.streamlit.app/`, investor `https://renewablox-investor-atlas-v2.streamlit.app/` | |
| 7 | Felt | — | no Felt links or embeds in v2 (spec 17) | |

### TAM fuel palette (owner decision 4)

Two designed 9-colour sets, one per theme, as `--fuel-0..8` tokens in `core/css/tokens.css` (read by `RBX.theme.pal().fuel`;
the TAM icons are drawn per theme id, so a theme switch re-renders them). Fuel → hue: landfill gas earthy ochre, fuelled
(mixed) slate, biomass orange, waste / EfW red, biogas (AD) green, sewage gas purple, advanced fuel blue, biofuel-other
olive, biodiesel grey. Chosen by a search over OKLCH within those hue windows that maximises the worst all-pairs ΔE
(normal and protan / deutan), with every hue ≥ 3:1 on the theme's land colour and inside the validator's lightness band.

| Fuel | Paper (`#F1ECE1`) | contrast | Night (`#0E1917`) | contrast |
|---|---|---|---|---|
| Landfill gas | `#8F5202` | 5.3 | `#A56500` | 3.8 |
| Fuelled (biomass/AD/EfW) | `#6D84AD` | 3.2 | `#7E95BD` | 5.9 |
| Biomass | `#E25E01` | 3.1 | `#EB6803` | 5.6 |
| Waste / EfW | `#960B28` | 7.5 | `#C13750` | 3.4 |
| Biogas (AD) | `#0A7756` | 4.7 | `#02AF7F` | 6.4 |
| Sewage gas | `#844386` | 5.7 | `#A458A3` | 3.9 |
| Advanced fuel | `#0947BE` | 6.7 | `#4C82F0` | 4.9 |
| Biofuel - other | `#778F49` | 3.1 | `#8E9448` | 5.5 |
| Biodiesel | `#524F50` | 6.9 | `#717171` | 3.7 |

Evidence (dataviz `validate_palette.js`, run by `tools/validate_palettes.sh`, 27 Sep 2026):
* legend order (by site count), 7 chromatic hues, adjacent pairs: **PASS** in both themes — Paper worst CVD ΔE 8.5,
  normal 16.9; Night worst CVD ΔE 9.4, normal 15.6; all ≥ 3:1. With the two neutrals included the adjacent CVD/normal
  checks still pass (8.5 / 16.7 Paper, 8.6 / 15.6 Night); slate and grey are deliberate neutrals below the chroma floor.
* all pairs (a map, where any two fuels can touch): CVD worst ΔE 7.0 Paper / 6.1 Night (floor band: legal only with
  secondary encoding), normal-vision worst 13.0 (biofuel-other ↔ biogas) / 11.4 — below 15. No 9-colour set can clear
  the all-pairs floors (the method caps all-pairs forms at three series); the relief channels are the ring shape
  (subsidy), the per-fuel legend rows with counts, the family quick-filter chips, and the fuel named in the tooltip,
  card, search and CSV. The weakest pairs involve the three smallest fuels (18 sites between them).
  `"families"` remains the fully CVD-validated alternative.

## Client look: the "product" skin (Direction B)

The client build wears Direction B ("premium product UI", chosen by the owner, 29 Sep 2026): a full-bleed map with
floating glass chrome — a brand pill with the *Peaker · Hydro · PPA Benchmark* switch, a search pill (⌘K / Ctrl K) and
theme button, a left panel (label, SAM/TAM switch, one-line description, KPI card with "In view", capacity histogram
and presets, legend-as-filter) and a right slide-in mini-report card. Light by default with a dark theme (theme ids
stay `paper` / `night`). Map notes are kept but default to off.

* **Files (shared by the client and Investor v3):** `skins/product/skin-product.css` (every selector starts with
  `:root[data-skin="product"]`, tokens included) and `skins/product/skin-product.js` (`RBX.skin`; wraps `RBX.header.render`, `RBX.kpi.html`,
  `RBX.hist.html`, `RBX.legend.html`, `RBX.rail.render` and `RBX.mapctl.obstruction / fitPadding / offset`; registers
  `hooks.railBefore`, the TAM `hooks.legendGroups` order and the sheet sections `sam.capacity`, `sam.revenue` (tier
  badge + meter) and `tam.facts`; adds soft SAM/Hydro shadow layers; registers RenewaBlox basemap palettes on the kit's
  light/dark; sets `RBX.brand.exportBand`, the PNG export's header band). Panel copy: `views[v].label` and
  `views[v].summary` in `apps/client/config.json`. The only `core/` hook it relies on is `RBX.brand.exportBand` in
  `core/js/export.js` (without it the export draws the core band).
* **Isolation:** only the client and Investor v3 templates set `data-skin="product"`, only their manifests list the
  two files, and the JS returns at once without the attribute. The skin stays audience-neutral (the client-safety scan
  reads it inside the client page), so every investor adaptation lives in `apps/investor_v3/`. Tests: `test_client_uses_product_skin`,
  `test_investor_never_gets_the_client_skin`, `test_product_skin_rules_are_scoped`,
  `test_product_skin_tier_ramp_is_ordered_and_visible`, `test_client_carries_the_renewablox_brand`.
* **Palettes** (dataviz `validate_palette.js`, 29 Sep 2026): BM tiers, claret → gold, luminance rising Tier 1 → 5 —
  light `#6B1034 #A02429 #C24D1E #DA7222 #D0A631` (Tier 5 2.07:1 on the brand land `#F1F4F6`, the prototype's `#EBD58E`
  was 1.28:1; adjacent CVD ΔE ≥ 8.0), dark `#A92E55 #E1363A #F36E2A #F8A142 #F2D07D` (Tier 1 2.65:1 on `#0F1C24`; CVD ≥ 8.7).
  Monotone with ΔL ≥ .06; multi-hue by design, so it fails the validator's one-hue ordinal check. Hydro confidence
  blues: light `#0E5F95 #2588C2 #4CB5EC` (Low 2.08:1), dark `#157ABD #3AA2DE #8DC7E5`. The TAM fuel palettes are the
  core ones (≥ 3.26:1 / 3.24:1 on the skin's lands).
* **RenewaBlox brand** (owner request, 29 Sep 2026; assets and tokens in `brand/README.md`):
  * **Logos:** the official wordmark is RENEWA in teal and BLOX. in black, and it sits over "no Watt wasted".
    The dark theme puts it on a Blox-teal plate, using the white/black version made for teal. The favicon and the
    Streamlit page icon are the BLOX. roundel.
  * **Wiring:** `apps/client/manifest.json` has a `brand` block. `build.py brand_assets` inlines the favicon and
    the `--rbx-wordmark-light|dark|mono` data URIs, and swaps the client's Google Fonts request for Open Sans.
  * **Colours:** Blox teal `#156082`, deep navy `#0B3549` (ink), sea teal `#218099` and sky `#83CBEB`. The
    basemap has cool paper land `#F1F4F6` and a sky-tinted sea.
  * **Type:** Leelawadee UI, the brand face, on Windows, with Open Sans elsewhere. Weights snap to 400/600/700,
    and labels are tracked capitals as in the pitch deck.
  * **Brand touches:** the headline KPI sits on a teal panel with the deck's sky quarter-circle. The site sheet
    has a teal-to-sky hairline. PNG exports carry a teal band with the wordmark.
* **Switch back:** delete `data-skin="product"` from `apps/client/template.html` (the skin files then do nothing; drop
  their two manifest entries as well to ship without them) and rebuild. The core look returns: docked header, serif
  headline and standfirst, notes on by default.

## QA

* `window.__atlasReady === true` after the first map `idle` following the data-layer wiring (or 12 s at most), the
  basemap labels and `document.fonts.ready` (or right after fonts when the map falls back).
* `window.atlas` — QA / automation API:
  `setView(v)`, `select(kind, key|index|name)`, `search(q)`, `toggle(set, value)`, `only(set, value)`,
  `showAll()`, `preset('all'|'over'|'under')`, `setTheme('paper'|'night')`, `present(on?)`, `openRail(open?)`,
  `closeSheet()`, `reset()`, `find(kind, name) → keys`, `state`.
* Layer regression: dump `JSON.stringify(RBX.map.getStyle())` from a running page and run
  `NODE_PATH=… node atlas/tools/validate_layers.js style.json` (0 errors expected).
* Palette regression: `VALIDATOR=…/dataviz/scripts/validate_palette.js sh atlas/tools/validate_palettes.sh`.
* Screenshots: 1440×820, 1060×800, 390×844 @2x; Paper + Night; every view; card, search, filters, mobile sheets.
* Client P1 checks: annotations placed (`RBX.notes.items.map(i => [i.id, !!i.pick])`), "In view" switch
  (`#ivSw`), overflow-menu downloads (PNG 3200×1800, sites CSV, register CSV), Sites list sort, `?` dialog,
  postcode search — postcodes.io is blocked in CI containers, so test the failure message with a non-site postcode
  (e.g. SW1A 1AA), the offline fallback with a site postcode (KT16 0EF), and the success path by stubbing `fetch`
  for `api.postcodes.io` only. Mobile drags need real touch/pointer events (CDP `Input.dispatchTouchEvent`).
* Streamlit: the page runs at `about:srcdoc` with Streamlit's sandbox (`allow-downloads`, `allow-popups`,
  `clipboard-write` are granted), so CSV/PNG downloads and Copy link work inside the wrapper.
* Investor checks: band defaults SAM `105 · 90.5 MW · 639 · £221.9M · £327.4M`, Hydro `57 · 15.2 MW · 177 · £13.6M ·
  £35.6M`, TAM `1,306 · 3,610 MW · 3,335 MW · £7.16bn` (caveat `£4.08bn of it from 76 sites ≥ 10 MW`;
  `RBX.band.setScale('ad')` → `£3.09bn`), PPA `129 · 143.6 MW · 21 · 8.52p · 12.50p`; `atlas.present()` then
  `RBX.present.go(0…5)`; `RBX.present.exit()` restores view, filters, camera, theme and the open card.

---

## Investor build

`apps/investor/{template.html, manifest.json, config.json, story.json, investor.css}` plus the investor-only modules
in `core/js/investor/` (all listed after the core files and before `core/js/app.js`) and `core/css/present.css`:

| Module | What it does |
|---|---|
| `model.js` | `RBX.inv`: `TCVRATE`, `AVRATIO`, `WHOLESALE`, `TAVG`, `bmKw()`, `tcvPot(rows)`, `uplift(t)` recomputed from the investor data at runtime (spec 10.2); SAM `sv = √(tcv/max)`, `pr`, `sk`; extra filter dims `pricing` (SAM `pr`), `export` (Hydro `expc`), `scale` (TAM `big` = kW ≥ 10,000); tooltip, size key (£1M · £4M · £9M), search (`dev`), TCV step order, register rows with v1 `rank` + raw REGO labels |
| `band.js` | `RBX.band`: the KPI band (config `band[view]` cells, exact v1 formulas over visible sites, count-up, as-of stamps), the TCV Potential caveat in its cell ("AD-scale only" only when the Scale filter hides ≥ 10 MW sites, else "No sites ≥ 10 MW in view") + method popover (`openPop`, `setScale('ad'|'all')`), the static GB power strip (≥ 1280 px, and only while the cells at their natural width clear it by 16 px: `fitMkt()` on render, resize and cell-size changes; the as-of lines ellipsize), the verbatim footer bar, the `▶ Present` header button, the PPA chips feed, and the drawer's investor sections (notes, TCV method table, footers, as-of) |
| `legends.js` | investor legends: tiers with `+%` uplift and live TCV, `Awaiting BM figure` (hollow; toggles `pricing`), Hydro export class + confidence, TAM + the `Scale` pair; verbatim notes clamped to 4 lines with "more" |
| `cards.js` | sheet sections: SAM head `Tier | town · postcode · GSP`, Commercials (TCV, TCV treasury, energy-vs-BTC split bar, BTC mined) or `Awaiting BM figure`, capacity, route to market (full operator), register data (commissioned, FiT gen, FiT ends, yrs-left runway, raw REGO status); Hydro commercials (`Energy export £0 · 100% mining`); TAM facts (`Not confirmed` subsidy from `src`, location precision, `In SAM`, indicative TCV potential). No "Talk to us" CTA |
| `exports.js` | investor columns for the shared CSV export (`#` rank, operator status, developer, GSP, TCV, BTC) and the Sites list (`# · Site · TCV (no treasury)` first, Town left to the CSV; the box widens to 1080 px and phones show only `#`, Site and TCV); files open with `csvHeader` "Confidential — investor use only" (also `imageBadge` on the PNG) |
| `present.js` | `RBX.present` (spec 10.3): six chapters from `story.json` (`{view, filters{set:[visible]}, camera{fit}|{center,zoom,pitch?,bearing?,terrain?}, ppa?, title (*phrase* = lime italic), body, stats[{label, expr}]}`); stats and `{tokens}` are computed from data (`RBX.present.STAT`); ← → Space PageUp/PageDown Home End, Esc exits and restores; `?present=1` / `#present=1` boots into it (no full-screen request and no tip without a user gesture: `enter(i, {gesture})`, else `navigator.userActivation`; the F11 tip only on desktop pointers; `webkit*` fallbacks); P1 autoplay (9 s) and 3D terrain on the Highlands chapter; `maxBounds` is lifted while presenting so the framing can clear the chapter card. PPA chapters never cover the chart: with ≥ 900 px of page beside the card (`.pc-side`) the page is padded right by the card's width; narrower desktops dock a compact full-width card (`.pc-dock`) and pad the page below (`--pc-h`); the chapter scroll also clears the section's chart above the card. Focus stays on the pressed card control across chapters |

Investor-only config keys: `band{sam,hydro,tam,ppa: [{label, metric, sub}], asOf{view}}`, `footers{sam,tam,ppa}`,
`notes{sam,tam,hydro}`, `market.title`, `labels.hydroExport`, `legend.sam.{sub, awaiting}`, `legend.hydro.{exportTitle,
confTitle}`, `legend.tam.scaleTitle`, `csvHeader`, `imageBadge`; `story` is inlined from `story.json` by `build.py`.
Investor copy tokens (`build.py investor_tokens`, investor build only): `{{inv_priced}} {{inv_tcv}} {{inv_tcv_t}}
{{tam_pot}} {{hydro_tcv}} {{hydro_tcv_t}} {{model_as_of}} {{registers_as_of}}`. The investor copy check covers the
subtitles, KPI labels, as-of stamps, legend notes, footers and card labels (spec 12.2).

Wrapper `app_investor_atlas.py`: same read-on-every-run / full-bleed / 820 px / whitelisted deep-link pattern as the
client (`view site theme present`). Access is controlled by the Streamlit Cloud viewer allowlist (owner decision 3).

---

## Investor Atlas v3

`apps/investor_v3/` builds `investor_atlas_v3.html`, wrapped by `app_investor_atlas_v3.py`. It is the investor
build in the RenewaBlox-branded "product" skin (owner request, 30 Sep 2026: branded, beautiful, not busy). The design
came from a three-direction design panel ("quiet luxury" won; the spec and mock-ups were kept outside the repo).
Investor v2 is kept as it is.

* **Same data and checks as v2:** `config.audience = "investor"`, so `build.py` runs the investor assembly, all 50
  canonical-number asserts, the investor copy tokens, the name checks and the story (from its own `story.json`,
  else `apps/investor/story.json`). `COPY['investor_v3']` keeps every investor disclaimer, note, footer and card string.
* **Bundle:** core → `skins/product/skin-product.js` → the investor modules (so their sheet sections and legends win)
  → `apps/investor_v3/investor-v3.js`, `v3-sheet.js`, `v3-present.js`, `v3-map.js` → `core/js/app.js`. The CSS is
  core → `present.css` → the skin → the v3 files. `apps/investor/investor.css` is not bundled.
* **What v3 removes:** the KPI band, its GB power strip and the footer bar (`RBX.band.render`, `renderFoot` and
  `fitMkt` are no-ops), and the rail headline block (the skin hides the kicker and standfirst; `views.*.standfirst`
  is gone; the headline stays for screen readers and the PNG title). The legend notes and the "In view" switch are
  also gone.
* **The panel:**
  * one teal hero per view (SAM £221.9M, TAM £7.16bn, Hydro £13.6M), with the treasury or ≥ 10 MW line;
  * a three-row ledger;
  * the disclaimer band ("Indicative; not investment advice." · model or registers stamp · Sources & method);
  * legend rows that show why each tier pays (an 8.0p wholesale stub plus the uplift in the tier colour);
  * TAM extras behind "More filters";
  * a one-row capacity disclosure.

  When any filter is active, the hero label reads "Contract value shown".
* **Confidentiality:**
  * The header carries "Investor Atlas / Confidential · investor use only". Below 1100 px that moves to the
    disclaimer band.
  * The phone peek, the Present card and PNG exports carry the confidential mark and the disclaimer.
* **Tokens:** `--v3-*` in `investor-v3.css` (`--v3-num-w` 400 is the hero weight; set 600 for the client's heavier
  look).

## Architecture

### Tree

```
atlas/
  build.py                 bundler + asserts + copy check + client-safety scan + budget (--only, --check, --qa)
  core/
    shell.html             DOM shell shared by both apps ({{SHELL}})
    basemap/               RBXBasemap kit (basemap.js, ne_pack.js, README.md; Atlas v2 changes listed in its README)
    css/                   tokens base header rail legend kpi controls sheet palette drawer notes dialogs mobile (+ ppa.css, PPA module)
    js/                    util state theme data filters icons layers map header kpi legend histogram sizekey rail
                           search sheet cards drawer toasts shortcuts notes dialogs export nearme drag ppa_host app
                           (+ ppa.js, PPA module). notes/dialogs/export/nearme/drag are the client P1 features; any
                           audience can list them in its manifest.
    js/investor/           investor-only modules (never in the client manifest; build.py enforces it)
  skins/product/           the shared "product" skin (client + investor v3)
  brand/                   RenewaBlox wordmarks, roundel and brand tokens (README.md)
  apps/<app>/              template.html · manifest.json (bundle order) · config.json (copy, views, switches)
  data/                    see "Refreshing data"
  tools/                   extract_v1.py (migration) · v1/ (frozen v1 pages) · validate_layers.js · validate_palettes.sh
  tests/test_build.py
```

### Build and runtime conventions

* Vanilla ES2019, no modules at runtime. Each file is an IIFE attached to the single global `RBX`,
  concatenated in `apps/<app>/manifest.json` order; `core/js/app.js` must be last (it boots).
  Audience modules go **between the core files and `app.js`** so their hook assignments exist at boot.
* Inlined globals: `window.ATLAS_CONFIG` (config.json after `{{token}}` substitution, plus build-computed
  `labels.rego` and `labels.ppaClass`) and `window.ATLAS_DATA` (compact columnar data, decoded by `RBX.data`).
* `/*__ATLAS_INIT__*/` is replaced by the wrapper with `window.__ATLAS_INIT__={view,site,theme,present?,publicUrl?}`
  (validated, whitelisted, JSON-encoded, `</` escaped). Boot order: `__ATLAS_INIT__` → `location.hash`
  (`#v=sam&s=KT160EF&z=8.3&c=-0.52,51.39&th=night`) → localStorage (theme, last view) → config defaults.
* Template placeholders: `{{DEFAULT_THEME}} {{TITLE}} {{FAVICON_DATA_URI}} {{FONTS_URL}} {{CSS}} {{SHELL}}
  {{CONFIG}} {{DATA}} {{NE_PACK}} {{BASEMAP}} {{JS}}`.
* Config copy tokens available to `config.json` strings: `{{sam_n}} {{sam_mw}} {{sam_mw0}} {{sam_bm_mw}}
  {{sam_bm_n}} {{tam_n}} {{tam_mw}} {{tam_gw}} {{tam_ro}} {{tam_fit}} {{hydro_n}} {{hydro_str_mw}}
  {{hydro_inst_mw}} {{hydro_mec_mw}} {{highlands_n}} {{as_of}}` (computed from data; unknown tokens fail the build).
* `innerHTML` only with `RBX.util.esc()`-escaped values (config HTML such as `standfirst` / `provenance` is trusted build input).
* Every map call is guarded; if MapLibre cannot load, `RBX.map` is `null`, a fallback panel shows, and header,
  rail, search, cards, drawer and PPA keep working.
* **Third-party hosts never block the page:** the fonts CSS and MapLibre CSS load preload→stylesheet, MapLibre JS
  loads `async` with Subresource Integrity (`build.py MAPLIBRE_SRI`, hashed from the registry-verified npm tarball;
  bump version and hashes together). `RBX.mapctl.init` waits up to 8 s for `window.maplibregl`, else the fallback.
  The data layers are wired on the first `style.load` (not `load`, which waits for every source); the DEM hillshade is
  added only after `__atlasReady` (`RBXBasemap.addTerrain`); `__atlasReady` fires on the first `idle` or after 12 s;
  if none of the data sources has loaded 9 s after wiring (map worker unreachable), or the style never parsed within
  12 s, the fallback panel shows. A bad hash camera (`#c=0,999`) is dropped at boot, and `new Map` is retried once
  without a boot camera.
* **Streamlit srcdoc fix (both apps):** inside `st.iframe` the page runs at `about:srcdoc`, where
  `location.origin` is `"null"` but MapLibre's blob worker keeps the parent origin, so MapLibre's Actor drops
  every worker message and no source ever loads. `RBX.mapctl.prepareWorker()` re-mints the worker with a shim
  reporting the same origin before the map is created. Do not remove it.

### Data model at runtime (`RBX.data`)

`RBX.data.rows.{sam,hydro,tam}` (arrays, `row.id` = index = GeoJSON feature id), `RBX.data.byKey.{sam,hydro,tam}`,
`RBX.data.find(key, preferKind)`, `RBX.data.ppa` (prices), `RBX.data.register()` (v1 `DATA.sites`-shaped rows for
the PPA module), `RBX.data.meta` (`samMax`, `hydroMax`, `cfg`, `raw`).

Every row has `kind`, `key`, `name`, `lat`, `lon`, `cap` (capacity-filter basis) plus:

| kind | fields | derived |
|---|---|---|
| sam | name site town la pc op t kw kwOn kwBm comm ppa off self fitGen fitEnd yrsLeft rego ref (investor adds rank g dev inst av btc en tcv tcvT regoRaw offRaw) | `outcode`, `sv`, `sk`, `pr` (1 = priced), `tamRow` |
| hydro | name exp conf kw inst mec (investor adds btc en tcv tcvT) | `c` (0–3 confidence), `expc` (0 export-limited, 1 no export), `sv`, `sk` |
| tam | n→`name`, f→`fuel`, kw bm p bt ro units sam (investor adds src) | `fu` (fuel index), `fam` (0–3), `sh` (`t` RO / `c` FiT), `ap`, `band` (0–4), `hr`, `samRow`, `inSam` |

GeoJSON properties: sam `{id,key,t,kw,sv,sk,pr}`; hydro `{id,key,c,kw,inst,exp,sv,sk}` (`exp` = `expc`);
tam `{id,key,fam,fu,sh,ap,band,kw,bt,sam,cc}` (`cc` = icon colour class). Extra properties:
`RBX.hooks.props[kind] = row => ({…})`.

### Module API (`window.RBX`)

| Module | Surface |
|---|---|
| `RBX.util` | `$ $$ esc num int mw mwDigits cap abbr gbp0 sum sig2 displayCase caseSafe cleanName norm compactPc outcode fmtDate template debounce rafThrottle countUp store copyText download km bbox isMobile isTouch reduced MONTHS` |
| `RBX.bus` | `on(ev, fn)`, `off`, `emit`. Events: `data`, `view {view,prev}`, `filter {light}`, `select row|null`, `theme t`, `mapready map`, `mapfail`, `ready`, `ppaChips c` |
| `RBX.state` | `view theme site hidden{tiers,fuels,shapes,precision,tamTiers,confs,export,pricing,scale} kw{sam,tam,hydro} cams ppa present railCollapsed preview lastPeaker inView boot`, `resolveBoot(cfg)`, `persist()`, `writeHash()`, `shareUrl(row?)` |
| `RBX.theme` | `set('paper'|'night')`, `toggle()`, `pal()` (data colours read from tokens.css), `tamMode()`, `tamColour(row)` |
| `RBX.filters` | `dims[view]` (push `{set, prop, rowProp?, values}`), `capProp`, `pass(row, skipSet?)`, `active(view)`, `expr(view)`, `facet(view, set, sumFn?)`, `facetBy`, `toggle(set,v)`, `only(set,v,view?)`, `setVisible(set, values, view?)`, `showAll(set)`, `resetView(view)`, `setKw(view, [min,max]|null, light?)`, `hiding(row)`, `snapshot()`, `restore(snap)`, `changed(light?)` |
| `RBX.layers` | `SIZE`, `R()`, `radiusAt(kind, z, sv)`, `tamScaleAt(z)`, `add(map)`, `showView(v)`, `applyFilters()`, `paint()`, `applyTheme()`, `setPreview({view,prop,values}|null)`, `relief(view)`, `pick(point, pad)`, `stackAt(cands)`, `setHover(row)`, `clearHover()`, `showTip(row, pt)`, `select(row|null)`, `pulse(kind, loop?)` (loop = Present mode 1.8 s) |
| `RBX.icons` | `draw(map, id)`, `ensure(map, theme)`, `expr(theme)`, `svg({shape:'dot'|'ring'|'tri', color, dashed, dot, size})`, `forRow(row, size)`, `BAND_D` |
| `RBX.mapctl` | `init(boot, onLoad)`, `fit(view, animate)`, `enter(view, prev)`, `reset()`, `saveCam(view)`, `fitPadding()`, `obstruction()`, `offset()`, `flyTo(row, {zoom})`, `ensureVisible(row)`, `viewBounds(view)`, `updateOfflinePill()`, `centreChrome(el)`, `addRelief()`, `prewarm()`, `cities`; `RBX.map` = the maplibre map (or `null`) |
| `RBX.app` | `setView(v, {camera, force})`, `openSite(row, {fly, focus})`, `clearSelection()`, `showInRegister(row)`, `syncEmpty()` ("No sites match these filters · Clear filters" pill) |
| `RBX.header` | `render()`, `sync()`, `menu` (push `{id, label (string or fn), icon, run, order?, when()?, sep?, hint?}`; sorted by `order`, hidden when `when()` is false), `toggleMenu()`, `MARK`, `ICON` |
| `RBX.rail` | `render()`, `setCollapsed(b)`, `toggle()`, `setOpen(b)` (mobile sheet) |
| `RBX.kpi` | `metrics` (add named metrics), `html(view)`, `update(instant)`, `rows(view)` (active rows, limited to the map view when "In view" is on), `inViewRows(rows)` (unobstructed viewport test), `setInView(bool)` — driven by `config.views[v].kpis` (omit for no rail KPI strip) |
| `RBX.legend` | `defaults.{sam,tam,hydro}()` (client group specs), `fuelOrder()`, `TYPES` (`rows`, `chips`, `famChips`, `stack`, `html`), `html(view)`, `spec(view)` |
| `RBX.hist` | `html(view)`, `draw()`, `sync()`, `setPreset('all'|'over'|'under', view?)` |
| `RBX.sizekey` | `render()` — `config.views[v].sizeKey = {title, values}` |
| `RBX.search` | `open(q?)`, `close()`, `isOpen()`, `query(q) → rows`, `queryScored(q) → [{r, s}]` (exact matches beat word-start fuzzy matches; groups follow their best result), `reveal(row)` (un-hide + toast Undo + fly + open), `build()`, `extras` (push `raw → [{label, sub, icon, run}]` to add palette actions, e.g. "Sites near KT16 0EF") |
| `RBX.sheet` | **section registry:** `section(kind, id, {order, render(row) → html, after(el,row)?})`, `remove(kind, id)`, `action(kind, id, {order, render(row)})`, `removeAction(kind, id)`, `chip[kind] = row → html`; `open(row)`, `chooser(rows)`, `panel({chip, html, actions?, focus?})` (free-form content in the sheet shell), `close()`, `step(±1)`, `refresh()`, `current()`, `isOpen()` |
| `RBX.cards` | client-safe section helpers: `sec(title, right, body)`, `fig(label, v, unit, cls)`, `head(name, meta[])`, `nearby(row)`, `splitBar(parts, label)`, `mailto(row)`, `actTalk actZoom actLink actRegister`, `INFO`, `ICON` |
| `RBX.drawer` | `open()`, `close()`, `isOpen()`, `html()` |
| `RBX.toast(msg, {label, run}?, ms?)` | |
| `RBX.notes` | client annotations (spec 16.3): `defs[view][id](activeRows) → {rows, anchor, ringKm?, lead, html}` (all figures computed from data), `build()`, `place(full)`, `items`, `on`. Driven by `config.views[v].notes = [{id, placements?}]` |
| `RBX.modal` | `open({title, html, cls?, sub?, onOpen(box)?, onClose()?})`, `close()`, `isOpen()`, `shortcuts()` (`?`), `about()` (`config.about`), `sitesList()` (sortable `<table>` of the sites shown), `COLS` |
| `RBX.exporter` | `cols[kind|'register']` (`[header, row → value]`), `csv(cols, rows)`, `sitesCsv(view?, rows?)`, `registerCsv()`, `grabMap(cb)` (canvas copy on the next render), `composite(mapCanvas) → canvas` (1600×900 @2x), `image()` |
| `RBX.nearme` | `lookup(q) → Promise<{lat, lon, label, approx, local?}>` (postcodes.io, then the atlas's own postcodes offline), `show(pt)`, `go(q)`, `ask(prefill)`, `clear()`, `message(err, q)`, `api` |
| `RBX.drag` | mobile bottom-sheet drag with snap points (rail: peek ↔ 78vh; card: 46vh ↔ 90vh, drag down to close) |
| `RBX.ppaHost` | `ensure()`, `show()`, `setFilter(partial)`, `showSite(row)`, `inst` (the PPA module instance) |
| `RBX.ppa` | the PPA module (`core/js/ppa.js`): `mount(root, ctx) → {refresh, setTheme, destroy, setFilter, getState, showSite, scrollToSection}` |

Existing default sheet section ids (client-safe, `order`): **sam** `head`10 `revenue`20 `capacity`30 `route`40
`nearby`60 · actions `talk`10 `zoom`20 `link`30 `register`40. **tam** `head`10 `facts`20 `nearby`60 · actions
`zoom` `link`. **hydro** `head`10 `stranded`20 `nearby`60 · actions `talk` `zoom` `link`.

### Hooks (`RBX.hooks`) — set them in an audience module listed before `app.js`

| Hook | Default | Use |
|---|---|---|
| `derive.sam/hydro/tam(row, ctx)` | client: `sv = √(kw/max)`, `sk = (6−t)·1e5 − kw`, `pr = 1` | investor: `sv = √(tcv/9,267,581)`, `sk = (6−t)·1e8 − tcv (+1e9 unpriced)`, `pr` |
| `props[kind](row) → {}` | — | extra GeoJSON properties (e.g. TAM scale class) |
| `tooltip(row) → string` | tier · capacity · town / fuel · RO · MW / confidence · stranded | investor appends `· £9.27M TCV` |
| `sizeValue(view, v) → sv`, `sizeLabel(view, v)` | kW | investor: £ values for the SAM key |
| `searchFields(row) → [[text, weight, isName?]]` | — | investor: `[[row.dev, .7]]` |
| `legendGroups[view]() → {title, sub?, sets[], groups[], after?}` | client legends | investor legends (uplift, Awaiting BM figure, export class, Scale chip) |
| `railBefore[view]()`, `railBlocks[view]()` | — | html inserted before the KPI strip / after the legend |
| `headerActions() → html` | — | investor `▶ Present` button |
| `drawerSections() → [{title, html}]` | — | investor notes, footers, TCV method table, as-of stamps |
| `stepOrder(kind, rows)` | SAM by `ref`; others by kW desc | investor: by TCV |
| `viewBounds(view)` | all rows of the view, padded 0.25° | |
| `registerRow(o, row)` | — | investor: `o.rank = row.rank; o.rego_status = row.regoRaw` |
| `ppaChips(c)` | writes the live region | investor: drive the KPI band |
| `filterLabel(row, set)` | — | toast wording for audience-specific filter sets |

`RBX.present = {enter(), exit(), active(), key(e) → handled?}` is picked up by the shortcuts (`P`, Esc) and by
`?present=1` / `#present=1` at boot when an audience module defines it.

### Config keys (`apps/<app>/config.json`)

`app`, `audience` (`client`|`investor`), `title`, `h1`, `productLabel`, `defaultTheme`, `defaultView`,
`storageKey`, `contactEmail`, `publicUrl`, `switches{sam_kw_source, rego_labels, tam_colour_mode}`,
`tabs[{id,label,short,count?}]`, `scope{tam,sam}`, `views.{sam,tam,hydro}{kicker, headline, standfirst (HTML),
universe, kpis[{label,metric,unit,caption}], capTitle, sizeKey{title,values}, searchGroup, highlandsChip?}`,
`views.ppa.kicker`, `labels{tiers, tierShort, export, conf, families, fuels}` (+ build adds `rego`, `ppaClass`),
`bmrev`, `bmfreq`, `legend.{sam,tam,hydro}` (titles, revenue strings, notes), `cards{offtakerTip, hydroExplain,
hydroNoExport, mailSubject, mailBody}`, `drawer{title, sources[], provenance (HTML), glossary[[term, def]], asOf}`,
`attribution`, `ppaPlaceholder`, `about{title, body[]}` (About popover), `views[v].notes` (annotation ids, client), optional `csvHeader` (first CSV row, e.g. a confidentiality line) and `imageBadge` (text on the PNG header).
