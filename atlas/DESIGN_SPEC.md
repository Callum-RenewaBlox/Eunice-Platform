# RenewaBlox Atlas v2: unified design spec (build contract)

**Status:** design-director decision, ready for implementation.
**Scope:** `client_atlas.html` (public) and `investor_atlas.html` (gated), and their Streamlit wrappers. The internal `atlas.html` / `app_atlas.py` are out of scope and must not be touched.
**Inputs this spec is based on:**
- the audits `scratchpad/audit/{client,investor}_audit.md`;
- the basemap kit `scratchpad/basemap/`;
- prototypes D1, D2 and D3 in `scratchpad/design/d{1,2,3}/` (all final screenshots were reviewed);
- palettes re-validated with the dataviz validator (section 3.4);
- canonical numbers recomputed from `scratchpad/data/*_v1_extract.json` (appendix A).

> How to read this document: **MUST** is a contract. **SHOULD** is a strong default: deviate only with a written reason in the PR. Anything marked *P1* or *P2* is out of scope for the first ship unless P0 is finished.

---

## 0. The decision in one paragraph

We build **one design system and one codebase: "RenewaBlox Atlas"**. It has two themes, **Paper** (light) and **Night** (dark), and ships as two audience builds.

- The **Client Atlas** is **light-first editorial cartography**. It follows the D1 direction: warm paper map, serif headline and standfirst per view, ruled KPI strip, legends laid out as tables, data-computed annotations.
- The **Investor Atlas** is a **dark-first presentation console**. It follows the D3 direction: Night basemap with relief, glowing markers, a commercial KPI band, and a **Present** mode for meetings.
- Both share D2's interaction layer: ⌘K command palette, faceted legend-as-filter, slide-in detail sheet, capacity histogram-slider and camera choreography.
- Both use the same header, typography, tokens, components, map layer factory, PPA module and build pipeline.

The two builds differ only in:
- the default theme;
- the header colour (client green, investor teal gradient, both carried over from v1);
- the data allowlist;
- a set of investor-only modules (commercial KPIs, commercial card sections, TCV potential, Present mode chapters).

Both are **self-contained single HTML files** at the existing paths, so the Streamlit wrappers keep working.

---

## 1. Scorecard

Weights: beauty 25%, cartographic clarity 20%, usability 20%, brand 10%, mobile 10%, accessibility 10%, implementation risk 5% (a higher score means lower risk). Scores are 1–10.

| Direction | Beauty | Clarity | Usability | Brand | Mobile | A11y | Risk | **Weighted** |
|---|---|---|---|---|---|---|---|---|
| **D1 · Editorial cartography** | 9 | 8 | 7.5 | 7 | 8 | 8 | 6 | **7.95** |
| **D3 · Night-ops console** | 8.5 | 6.5 | 8.5 | 9 | 7 | 6 | 6 | **7.63** |
| **D2 · Premium product UI** | 7.5 | 7 | 8.5 | 7 | 7.5 | 7 | 8 | **7.53** |

### D1 · Editorial cartography

**Strengths**
- The most distinctive and polished of the three. The serif headline and standfirst turn each view into a claim ("129 AD plants that can earn when the grid runs tight").
- Data-computed annotations (the Tier 1 London–Kent cluster, the Thames Estuary) actually explain the map.
- TAM is the most legible of the three at national zoom: 3 families + Other, 5 capacity bands, and a translucent paper fill so overlapping symbols layer like coins.
- Filtered-out sites stay on the map as 9% ghosts, so the geography survives filtering.
- Palettes were checked with the validator.
- Mobile is good: the peek sheet shows the headline and KPIs.

**Weaknesses**
- The claret tier ramp makes T2–T4 hard to tell apart at small sizes, and brand lime is almost absent.
- The rail overflows at 780–820 px, and first-click-solo in the legend surprises users.
- The Hydro framing still clips the 6 England and Wales sites.
- ink-3 `#7C847E` is 3.5:1 (fails AA).
- The PPA tab is a placeholder, and the annotation engine is the riskiest code of the three.

### D3 · Night-ops console

**Strengths**
- Night mode is the most cinematic and on-brand: lime and deep green throughout, and relief drama in the Highlands.
- Present mode and 3D Highlands terrain suit investor meetings.
- The GB power strip gives price context.
- Search, filters, prev/next and keyboard shortcuts are strong.

**Weaknesses**
- TAM becomes a pastel "confetti" and heat blob, and the Day heatmap looks like a smudge.
- The Day tier ramp **fails** ordinal validation: lightness is non-monotone, `L = 0.49 / 0.63 / 0.60 / 0.59 / 0.74`.
- 9.5 px mono eyebrows, and ink-3 at 4.2:1.
- The mobile header plus ticker costs about 260 px.
- Three marker layers and per-frame JS rings add risk.

### D2 · Premium product UI

**Strengths**
- The best interaction layer: tokenised fuzzy ⌘K palette, faceted legend counts, "In view" KPIs, detail step-through and nearby sites, and a TAM→SAM cross-link.
- The simplest and lowest-risk code.
- Hydro frames all 57 sites.

**Weaknesses**
- Looks like generic SaaS, with the weakest brand identity.
- 9 fuel hues are not CVD-safe, and T5 straw is weak on paper.
- The mobile framing puts Scotland under the floating header.
- The PPA tab is a placeholder.

**Verdict.**
- **Client = D1**, the highest score, and editorial storytelling suits prospective clients.
- **Investor = D3**, the best fit for a presentation audience, second-highest score, strongest brand.
- **D2 is the interaction layer for both.** All three are rebuilt on the shared system below, so the family reads as one product.

---

## 2. What we take from each direction (grafts)

**From D1 (system spine, both apps)**
- The editorial rail: kicker, serif headline, standfirst, a ruled KPI strip with a 1 px ink top rule opening each section, and legend tables with inline bars.
- Ghosts at 9%.
- Capacity histogram with a log-scale dual slider and the v1 presets.
- On-map size key that recomputes with zoom, plus a scale bar.
- TAM: 3 families + Other, 5 capacity bands, paper fill, small-on-top sorting.
- The revenue ladder in the SAM card.
- Paper basemap overrides and the "Simplified basemap" pill.
- Data-computed annotations (client, P1).
- Palette validation discipline.

**From D2 (interaction layer, both apps)**
- ⌘K / `/` command palette. Scoring is tokenised and matches postcodes with or without the space, RO refs and operator. Results are grouped, with an empty state.
- Legend rows as toggles:
  - counts are **faceted**, so each row's count ignores its own dimension;
  - an explicit "Only" affordance, plus ⌥/⌘-click, isolates a row;
  - "Show all" resets.
- Hover snaps to the nearest feature centre within ±8 px.
- "In view" KPI switch (P1).
- Detail sheet: step-through, Nearby, Copy link.
- Camera offsets that account for the panels.
- TAM "Verified in SAM → open peaker profile" cross-link.
- Spring segmented controls, and a toast with Undo when search clears a filter.

**From D3 (presentation layer and dark theme)**
- The Night basemap palette.
- Glow markers in Night only: halo, core and hot centre.
- The 2×2 "blox" brand mark.
- **Present** mode: chapters, progress, keyboard.
- 3D Highlands terrain (P1).
- TAM icons generated lazily on `styleimagemissing`, with the theme encoded in the icon id.
- The GB power market strip (investor).
- Full-screen search on mobile.
- The shortcut keymap.
- Build-time forbidden-key assertions.

**From the audits (new, not in any prototype)**
- A **validated green brand tier ramp** used in both themes: Tier 1 is deepest on Paper and brightest on Night.
- "Talk to us about this site" pre-filled mailto (client).
- Offtaker tagged *inferred*.
- Investor:
  - unpriced sites drawn as hollow rings;
  - the TCV Potential caveat shown **next to the number**, plus an "AD-scale (<10 MW)" filter;
  - a TCV split bar (`en` vs BTC value).
- One-number-one-source reconciliation.
- Softened public REGO status labels.
- Wrapper query-param deep links and a password gate.
- CSV and PNG exports (P1).
- Postcode "near me" (P1).

---

## 3. Design tokens

All tokens live in `atlas/core/css/tokens.css`, on `:root` and `[data-theme]`.

> **Never** prefix the token block with a scoping selector. The v1 S1 bug was `.rb-root /*…*/ .rb-root{…}`, which matched nothing.

The theme is set with `<html data-theme="paper|night">`. There is no `prefers-color-scheme` auto-switching, because each audience has a designed default. The toggle persists the choice in `localStorage` (inside try/catch).

### 3.1 Surfaces, ink, brand

```css
:root, :root[data-theme="paper"] {
  color-scheme: light;
  /* surfaces */
  --map-land:      #F1ECE1;               /* basemap land; also page bg behind the map */
  --surface-0:     #F8F5EE;               /* rail, PPA page plane, mobile sheets */
  --surface-1:     #FFFDF9;               /* cards, detail sheet, inputs, palette, tiles */
  --surface-2:     #F1EDE3;               /* sunken: slider tracks, chips, zebra rows */
  --surface-float: rgba(255,253,249,.94); /* floating map chrome (controls, size key, notes) */
  --wash:          rgba(27,35,32,.045);   /* hover rows */
  --scrim:         rgba(20,26,24,.30);
  /* ink (all text tokens pass WCAG AA ≥ 4.5:1 on --surface-0/1) */
  --ink-1: #1B2320;   /* 14.8:1 */
  --ink-2: #48524D;   /*  7.5:1 */
  --ink-3: #646D68;   /*  4.9:1 (D1's #7C847E failed at 3.5:1) */
  --ink-4: #A3A9A4;   /* decorative only: disabled, ghost swatches; never text */
  --ink-inverse: #FFFDF9;
  /* rules */
  --rule:        rgba(27,35,32,.12);
  --rule-2:      rgba(27,35,32,.22);
  --rule-strong: #1B2320;                 /* 1px editorial top rule opening each rail section */
  /* brand */
  --brand:        #0E3A2F;
  --brand-2:      #1C4A3C;
  --lime:         #8FD14F;                /* fills and marks only on paper; never text on paper */
  --lime-ink:     #3E7A12;                /* lime-family text/accents on paper, 4.8:1 */
  --lime-wash:    rgba(143,209,79,.16);
  --focus:        #3E7A12;                /* focus ring on paper surfaces */
  --tooltip-bg:   #1B2320;
  --tooltip-ink:  #F8F5EE;
  --marker-stroke:#FFFDF8;
}
:root[data-theme="night"] {
  color-scheme: dark;
  --map-land:      #0E1917;
  --surface-0:     rgba(10,19,20,.80);    /* glass rail; needs --glass */
  --surface-0-solid:#0C1618;              /* fallback when backdrop-filter is unsupported */
  --surface-1:     #111C1A;
  --surface-2:     rgba(255,255,255,.045);
  --surface-float: rgba(12,22,21,.86);
  --wash:          rgba(174,226,208,.06);
  --scrim:         rgba(0,0,0,.45);
  --ink-1: #E8F1ED;   /* 15.4:1 on #0F1A18 */
  --ink-2: #A9BAB3;   /*  8.8:1 */
  --ink-3: #83978F;   /*  5.8:1 (D3's #6A807A failed at 4.2:1) */
  --ink-4: #4E605A;
  --ink-inverse: #0E1917;
  --rule:        rgba(174,226,208,.10);
  --rule-2:      rgba(174,226,208,.18);
  --rule-strong: rgba(232,241,237,.72);
  --brand:        #0E3A2F;
  --brand-2:      #1C4A3C;
  --lime:         #8FD14F;
  --lime-ink:     #B9EC7A;                /* 13:1 */
  --lime-wash:    rgba(143,209,79,.14);
  --teal:         #3FD0C0;
  --focus:        #B9EC7A;
  --tooltip-bg:   rgba(8,15,16,.94);
  --tooltip-ink:  #E8F1ED;
  --marker-stroke:rgba(232,242,237,.80);
  --glass:        saturate(140%) blur(16px);
  --vignette:     radial-gradient(ellipse at 55% 45%, transparent 55%, rgba(0,0,0,.42) 100%);
}
```

### 3.2 Header (audience brand chrome, identical in both themes)

```css
/* client build */
:root { --header-bg: #0B2E2A; --header-ink: #FFFFFF; --header-ink-2: #CFE8E2; --header-rule: #1D5A51; }
/* investor build (v1 deep-teal identity) */
:root { --header-bg: linear-gradient(90deg,#16323A 0%,#1F6F78 100%); --header-ink:#FFFFFF; --header-ink-2:#D3E6E8; --header-rule: rgba(255,255,255,.16); }
```

The header focus ring is `--lime`, which is 6.9:1 on `#0E3A2F`. The active-scope pill is lime fill `#8FD14F` with `#0B2E2A` text (8.3:1).

### 3.3 Data palettes (validated; section 3.4 has the evidence)

| Role | Paper | Night | Notes |
|---|---|---|---|
| **BM tier T1…T5** (SAM colour; TAM tier chips) | `#004A2D #1D6835 #478638 #6F9E45 #93B163` | `#D7F96C #A2DD50 #6FBF5D #4E9F63 #407E5B` | One-hue green ordinal ramp. Tier 1 always has the most contrast against the land: deepest forest on Paper, brightest lime at Night. Night T2 is almost brand lime. Names: `Tier 1 · Highest`, `Tier 2 · Strong`, `Tier 3 · Moderate`, `Tier 4 · Modest`, `Tier 5 · Lower`. |
| Tier "hot centre" (Night glow only) | — | `#F7FFD6 #E6F7C9 #D5F0D2 #CCE7D4 #C3DACB` | Decorative |
| **TAM technology family** (ring colour) | Landfill `#B07A1C` · Digestion `#0B7C55` · Thermal `#5A62CA` · Other `#8A877C` | `#BF8834 #2A9E7A #7F88E4 #8C8A80` | Families: Landfill gas → Landfill. Biogas (AD) + Sewage gas → Digestion. Biomass + Waste / EfW + Fuelled (biomass/AD/EfW) → Thermal. Advanced fuel + Biofuel - other + Biodiesel → Other (a neutral that also gets a centre dot as its secondary encoding). |
| TAM symbol fill / halo | fill `rgba(250,247,240,.66)`, halo `rgba(250,247,240,.85)` | fill `rgba(10,18,17,.62)`, halo `rgba(6,11,12,.80)` | |
| SAM-in-TAM marker | `#8FD14F` dot, 1 px `#0B2E2A` stroke | same | "Verified site" |
| **Hydro confidence** High/Medium/Low | `#15557E #3F84AE #7EADC7` | `#A5D2EA #5E9EC3 #3A7596` | Ordinal blue (water). **Unverified = hollow ring** stroke `#8A877C` / `#8C8A80` |
| PPA realised series | `#2A78D6` | `#3987E5` | v1's intended series-1 |
| PPA forward series | `#EB6834` | `#D95926` | v1's intended series-2 |
| PPA reference lines | FiT rule `--ink-3` dashed `5 4`; CPI path `--ink-2` dotted `1 3`; grid `--rule`; baseline `--rule-2` | same tokens | |
| Counterparty bars | `#2A78D6`; "Not identified" `--ink-4`; sole holder = 45° hatch of `#2A78D6` | `#3987E5` | |
| Export arrangement chips | Negotiated PPA bg `rgba(42,120,214,.12)` text `#1D5BA8`; FiT standard bg `rgba(237,161,0,.18)` text `#7A5200`; Behind meter bg `--surface-2` text `--ink-2`; Unknown: 1 px `--rule-2` outline, text `--ink-3` | text `#8DB8F0` / `#F2C66B` / `--ink-2` / `--ink-3` | Chips always carry text |
| Status (fixed, never themed) | good `#0CA30C` · warning `#FAB219` · critical `#D03B3B` · neutral `#9AA19C` | same | Always dot **plus text label** |

### 3.4 Validation evidence

Palettes were validated with `dataviz/scripts/validate_palette.js`, against the surface each palette actually renders on. Re-run the validator in CI whenever a hex changes.

| Palette | Result |
|---|---|
| Tier, Paper, on `#F1ECE1`, `--ordinal` | PASS: monotone lightness, ΔL ≥ .06, light end 2.05:1, hue spread 33° |
| Tier, Night, on `#0E1917`, `--ordinal` | PASS: light end 3.72:1, hue spread 36° |
| TAM three hues (Landfill, Digestion, Thermal), `--pairs all` | PASS in both themes: worst CVD ΔE 8.3 / 8.2, normal-vision ΔE 18.9 / 17.5 |
| TAM "Other" grey | A deliberate neutral, not a hue; it carries a centre dot as its secondary encoding |
| Hydro, both themes, `--ordinal` | PASS |
| PPA series, both themes | PASS: ΔE 24–34 |
| D3 Day tier ramp (rejected) | FAILED |

### 3.5 Typography

**Google Fonts, one request:**

```
https://fonts.googleapis.com/css2?family=Inter:wght@400..700&family=Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400..500&display=swap
```

`<link rel="preconnect">` to both `fonts.googleapis.com` and `fonts.gstatic.com`.

**Font stacks**

```css
--font-ui:      "Inter", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
--font-display: "Newsreader", Georgia, "Times New Roman", serif;
--font-mono:    ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;  /* RO refs, kbd hints only; no web font */
--rbx-map-font:  var(--font-ui);        /* read by the basemap kit for canvas city labels */
--rbx-map-serif: var(--font-display);   /* sea labels in Newsreader italic */
```

**Numbers.** Put `.num { font-variant-numeric: tabular-nums lining-nums; }` on every figure in tables, KPIs, axes, legends and cards. On Newsreader, use `font-variant-numeric: lining-nums tabular-nums`.

**Type scale.** Size is in px; line height is unitless.

| Role | Face | Size / LH / weight | Notes |
|---|---|---|---|
| Wordmark "RenewaBlox" | Newsreader | 20 / 1 / 600, opsz 36 | Header |
| Product label "CLIENT ATLAS" | Inter | 10.5 / 1.2 / 600, caps, +.14em | Header |
| Tagline "no Watt wasted" | Newsreader italic | 12.5 / 1.2 / 400, `--lime` | Never uppercase; the capital W is part of the brand |
| Display XL | Newsreader | 40 / 1.05 / 500, opsz 72, −.02em | PPA deck, Present chapter titles (34 on ≤1180) |
| Rail headline | Newsreader | 27 / 1.08 / 500, opsz 60, −.018em, `text-wrap: balance` | 23 when `max-height ≤ 840px`; 20 on mobile peek |
| Card name | Newsreader | 24 / 1.12 / 500 | |
| Figure L | Newsreader | 30 / 1 / 500, tnum | Card hero numbers |
| Figure M | Newsreader | 26 / 1 / 500, tnum | KPI values |
| Standfirst | Newsreader | 14.5 / 1.42 / 400, `--ink-2` | The encoding sentence is in italic |
| Body | Inter | 13 / 1.45 / 400 | |
| Body S | Inter | 12 / 1.4 / 400 | Legend secondary lines, table cells |
| Label | Inter | 11.5 / 1.3 / 500 | |
| Eyebrow / kicker / section title | Inter | 10.5 / 1.2 / 600, caps, +.12em (kicker +.15em) | **Minimum text size anywhere is 10.5 px** (no 9.5 px mono) |
| Chart ticks | Inter | 11 / 1 / 400, tnum | At every viewport; SVGs are drawn at CSS pixel width, never scaled by a viewBox |

### 3.6 Space, radii, elevation, motion, layers

```css
--sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:20px; --sp-6:24px; --sp-8:32px; --sp-10:40px;
--r-1:4px; --r-2:8px; --r-3:12px; --r-4:16px; --r-pill:999px;
--header-h:56px; --kpiband-h:64px; /* investor */ --footer-h:24px; /* investor */
--rail-w:348px; --sheet-w:384px; --gutter:12px;
@media (max-width:1180px){ :root{ --rail-w:320px; --sheet-w:352px; } }

/* Paper */
--sh-1: 0 1px 2px rgba(27,35,32,.06), 0 4px 14px rgba(27,35,32,.07);
--sh-2: 0 2px 6px rgba(27,35,32,.08), 0 18px 42px rgba(27,35,32,.16);
--sh-3: 0 0 0 .5px rgba(27,35,32,.08), 0 16px 40px -8px rgba(27,35,32,.22), 0 40px 80px -24px rgba(27,35,32,.28);
/* Night */
--sh-1: 0 0 0 .5px rgba(255,255,255,.06), 0 2px 8px rgba(0,0,0,.35);
--sh-2: 0 0 0 .5px rgba(255,255,255,.07), 0 24px 60px rgba(0,0,0,.55), 0 2px 10px rgba(0,0,0,.35);
--sh-3: 0 0 0 .5px rgba(255,255,255,.08), 0 30px 80px rgba(0,0,0,.6);

--dur-1:120ms; --dur-2:200ms; --dur-3:320ms; --dur-4:500ms; --dur-count:600ms;
--ease: cubic-bezier(.2,.8,.2,1);  --ease-spring: cubic-bezier(.32,1.28,.54,1);
```

**Layers.** Paper uses solid surfaces with no blur, for the editorial look. Night uses glass: `backdrop-filter: var(--glass)`, with a `@supports not (backdrop-filter: blur(1px))` fallback to `--surface-0-solid`.

**Motion rules**
- Hover: `--dur-1`. Toggles: `--dur-2`. Sheet slide: `--dur-3` (`--ease`). Segmented thumb: `--dur-2` (`--ease-spring`).
- KPI count-up: `--dur-count`, easeOutQuart.
- Selection pulse: 1.1 s × 2. In Present mode it loops at 1.8 s.
- `flyTo`: `{speed:1.3, curve:1.42, maxDuration:2200}`. Present-mode flights: 2600–3600 ms.
- `prefers-reduced-motion: reduce` sets every duration to 0.01 ms. JS reads `RBX.reduced`, and then:
  - `flyTo` becomes `jumpTo`;
  - there is no pulse, count-up or autoplay;
  - glow opacity is fixed.

**Z-index scale**

| z | Element |
|---|---|
| 0 | map |
| 5 | annotations |
| 6 | size key and scale |
| 10 | offline pill |
| 20 | rail |
| 25 | map controls |
| 30 | detail sheet |
| 35 | KPI band |
| 40 | header |
| 50 | tooltip |
| 60 | palette scrim |
| 61 | palette |
| 70 | toasts |
| 80 | Present overlay |
| 90 | drawers and dialogs |
| 100 | skip link |

### 3.7 Brand mark

A 2×2 "blox" mark, as an inline SVG 20×20 px:
- four 9×9 squares at `rx = 2` with a 2 px gap;
- top-left `#8FD14F` (lime), top-right `#3E8A6A`, bottom-left `#2F6B55`, bottom-right `#245744`;
- on Night headers, the lime cell gets `filter: drop-shadow(0 0 6px rgba(143,209,79,.55))`.

The favicon is the same SVG as a data URI.

---

## 4. Basemap

We use the kit in `scratchpad/basemap/` **unmodified**. Copy `basemap.js` and `ne_pack.js` to `atlas/core/basemap/`. Theme palettes are registered at runtime in `atlas/core/js/theme.js`. Never mutate the kit's own `light` / `dark` objects; register new keys instead.

```js
RBXBasemap.palettes.paper = Object.assign({}, RBXBasemap.palettes.light, {           // D1 editorial paper
  name:'paper', land:'#F1ECE1', landContext:'#E9E5DB', sea:'#DAE2E0', sea200:'#D5DEDC', sea1000:'#D0DAD9', sea2000:'#CBD6D5',
  coastGlow:'#E7ECE8', coastline:'#A6B2AC', lake:'#D3DDDB', river:'#A3BCBC', border:'#9C9B8D', borderIntl:'#8E8D80',
  hsShadow:'#4A4638', hsAccent:'#6E6A5A', hsHighlight:'#FFFDF6', hsExaggeration:[4,.5, 6,.42, 8,.33, 11,.26, 14,.2],
  label:'#4C5550', labelMajor:'#1F2724', labelHalo:'rgba(241,236,225,.94)', dot:'#1F2724', dotHalo:'#F1ECE1',
  region:'rgba(60,66,58,.34)', sea_label:'#72898A'
});
RBXBasemap.palettes.night = Object.assign({}, RBXBasemap.palettes.dark, {            // D3 night
  name:'night', land:'#0E1917', landContext:'#0B1413', sea:'#04090B', sea200:'#03080A', sea1000:'#030709', sea2000:'#020507',
  coastGlow:'#0D2A2A', coastline:'#244440', lake:'#061011', river:'#1B4646', border:'#3D524B', borderIntl:'#4A6159',
  wood:'#0F1B18', grass:'#101B19', park:'#0F1D19', residential:'#131D1B', ice:'#16211F', road:'#22302D', roadMajor:'#2B3B37', rail:'#1F2B28',
  hsShadow:'#000000', hsHighlight:'#6F948A', hsAccent:'#07100E', hsExaggeration:[4,.86, 6,.74, 8,.56, 11,.4, 14,.3],
  label:'#8AA098', labelMajor:'#D3E0DA', labelHalo:'rgba(5,10,10,.9)', dot:'#D3E0DA', dotHalo:'#050A0A',
  region:'rgba(160,190,180,.20)', sea_label:'#395757', waterLabel:'#4F7C7C'
});
```

**Map configuration**

```js
const map = new maplibregl.Map({
  container:'map', style: RBXBasemap.style(theme /* 'paper'|'night' */, { focus:'uk' }),
  bounds: VIEW_BOUNDS[initialView], fitBoundsOptions:{ padding: fitPadding() },
  minZoom: 4.2, maxZoom: 15, maxBounds: [[-16,47.5],[8,62.5]],
  attributionControl: { compact: true, customAttribution: 'Geocoding: <a href="https://postcodes.io">postcodes.io</a>' },
  dragRotate: false, pitchWithRotate: false, touchPitch: false   // enabled only by Present/3D (P1)
});
map.touchZoomRotate.disableRotation(); map.keyboard.disableRotation();
const bm = RBXBasemap.attach(map, {
  cities: RBXBasemap.cities.filter(c => c[1] > -11 && c[1] < 1.9),   // GB + Ireland only; no Amsterdam/Brussels/Paris
  onMode: m => RBX.ui.setBasemapMode(m)
});
```

**Rules**
- Data layers are added with `map.addLayer(layer, RBXBasemap.DATA_BEFORE)`. This puts them above the basemap and the region and sea labels, and below city labels.
- A theme switch calls `RBXBasemap.applyTheme(map, 'paper'|'night')`, **never `setStyle`**. The app then re-applies its own data paint (section 5.6).
- **Per-view relief.** In Hydro, multiply the active palette's `hsExaggeration` values by 1.30 on Paper and 1.15 on Night, via `map.setPaintProperty('rbx-hillshade','hillshade-exaggeration', expr)`. Restore the base values on the other views. The relief explains stranded hydro.
- **Offline pill.** When `map.__rbxBasemapMode === 'offline'` and zoom ≥ 7.2, show a bottom-centre pill: "Simplified basemap · detail tiles unavailable". Use `--surface-float`, 11.5 px `--ink-2`.
- **Attribution.** Keep the kit's source attributions (© OpenStreetMap contributors, OpenFreeMap, Natural Earth, Terrain: Mapzen / AWS Terrain Tiles) plus "Geocoding: postcodes.io". **Remove "RenewaBlox CRM".**
- `window.__atlasReady = true` is set after the first `idle` **and** `document.fonts.ready`. The kit does not set it.

---

## 5. Map layers and encodings (exact)

### 5.1 Sources

GeoJSON sources are built client-side from the compact inlined data. Every feature has a numeric `id` so that feature-state works.

| Source | Properties |
|---|---|
| `sam` | `id`, `key` (stable string id, see 14.4), `t` (1–5), `kw` (canonical installed kW), `sv` (size value 0–1), `sk` (sort key), `pr` (investor: 1 = priced, 0 = awaiting) |
| `hydro` | `id`, `key`, `c` (0 = High, 1 = Medium, 2 = Low, 3 = Unverified), `kw` (stranded), `inst` (installed; filter basis), `exp` (0 = Export-limited, 1 = No export), `sv` |
| `tam` | `id`, `key`, `fam` (0–3), `fu` (fuel index 0–8, v1 order), `sh` (`'t'` RO / `'c'` FiT), `ap` (0/1), `band` (0–4), `kw` (null→0), `bt` (0–5), `sam` (0/1) |
| `sel`, `hover` | One point each, with `{kind, sv, hr}` (`hr` = TAM half-diameter + 3) |

**Size value `sv`**

| Layer | Formula | Notes |
|---|---|---|
| Client SAM | `sqrt(kw / 5936)` | 5,936 kW is the largest SAM site |
| Investor SAM | `sqrt(tcv / 9267581)` | Unpriced sites: `sv = 0` |
| Hydro, both apps | `sqrt(kw_stranded / 1309)` | Investor hydro TCV is exactly proportional to stranded kW (£900.48/kW), so size ∝ √TCV holds and both apps look identical |

This preserves "size ∝ capacity" (client) and "size ∝ √TCV" (investor). The v1 26 px cap is replaced by zoom scaling.

**TAM `band`:** `kw < 250 → 0; < 1000 → 1; < 5000 → 2; < 20000 → 3; else 4` (null → 0).

### 5.2 Radius factory (true area-proportional symbols with a floor)

```js
// R(stops, add = 0, mult = 1): zoom-interpolated radius. `add` may be a feature-state expression.
function R(stops, add = 0, mult = 1) {
  const e = ['interpolate', ['exponential', 1.5], ['zoom']];
  for (const [z, base, span] of stops)
    e.push(z, ['+', add, ['*', mult, ['max', base, ['*', span, ['get', 'sv']]]]]);
  return e;
}
const SIZE = {
  sam:   [[4,2.8, 9.2],[6,3.6,14.6],[8,5.0,20.8],[11,7.0,30.8],[14,9.0,42.4]],   // 5.9 MW ≈ 14.6 px at z6
  hydro: [[4,3.0, 9.8],[6,3.8,13.8],[8,5.0,18.8],[11,7.0,26.0],[14,9.0,34.4]]
};
const HOVER_ADD = ['case', ['boolean', ['feature-state','hover'], false], 2, 0];
const tierMatch = (P) => ['match', ['get','t'], 1,P[0], 2,P[1], 3,P[2], 4,P[3], P[4]];
```

**Size key.** The size key computes the same radii in JS for the current zoom:

| Layer | Key values |
|---|---|
| Client SAM | 250 kW · 1 MW · 5 MW |
| Investor SAM | £1M · £4M · £9M |
| Hydro | 100 kW · 500 kW · 1.3 MW |
| TAM | The five bands `<250 kW · <1 MW · <5 MW · <20 MW · 20 MW+`, plus "○ Exact location  ◌ Postcode district" |

### 5.3 SAM and Hydro circle stack

Hydro is identical to SAM, with the substitutions given below.

| # | Layer id | Themes | Paint and layout |
|---|---|---|---|
| 1 | `sam-glow` | Night only (`visibility:none` on Paper) | `circle-radius: R(SIZE.sam, 3, 2.2)`, `circle-color: tierMatch(NIGHT_TIER)`, `circle-blur: 1`, `circle-opacity: ['interpolate',['linear'],['zoom'],5,.5,9,.28,12,.18]`, filter = ACTIVE |
| 2 | `sam-ghost` | both | `circle-radius: R(SIZE.sam)`, `circle-color: tierMatch(P)`, `circle-opacity: .09` (Night .12), `circle-stroke-width: 0`, filter = `['!', ACTIVE]` |
| 3 | `sam-core` | both | `circle-radius: R(SIZE.sam, HOVER_ADD)`, `circle-color: tierMatch(P)`, `circle-opacity`: client `.94`, investor `['case',['==',['get','pr'],0],0,.94]` (unpriced = hollow), `circle-stroke-color`: Paper `['case',['==',['get','pr'],0], tierMatch(P), '#FFFDF8']`, Night `tierMatch(NIGHT_TIER_HOT)` at `circle-stroke-opacity .75` (unpriced: tier colour at 1), `circle-stroke-width: ['interpolate',['linear'],['zoom'], 5,['case',HOV,2.2,['==',['get','pr'],0],1.6,0.9], 10,['case',HOV,2.6,['==',['get','pr'],0],2,1.5]]`, `circle-sort-key: ['get','sk']`, filter = ACTIVE |
| 4 | `sam-hot` | Night only, `minzoom 5.5` | `circle-radius: R(SIZE.sam, 0, .34)`, `circle-color: tierMatch(NIGHT_TIER_HOT)`, `circle-blur: .9`, `circle-opacity: ['interpolate',['linear'],['zoom'],5.5,0,7,.85]`, filter = `['all', ACTIVE, ['!=',['get','pr'],0]]` |

`HOV` is `['boolean',['feature-state','hover'],false]`. Zoom must stay the top-level `interpolate`, because `zoom` inside `case` is invalid (D1's round-1 bug).

**Sort key `sk`**
- Client SAM: `(6 − t) × 1e5 − kw`, so Tier 1 draws on top, and within a tier smaller sites draw above larger ones.
- Investor SAM: `(6 − t) × 1e8 − tcv`. Unpriced sites get `+1e9`, so the small hollow rings draw on top.

**Hydro substitutions**
- Colour is `['match',['get','c'],0,H,1,M,2,L,'rgba(0,0,0,0)']`.
- Unverified (`c = 3`) is a hollow ring: stroke `#8A877C` / `#8C8A80`, width 1.7 → 2 px.
- There is no sort by tier. Use `sk = −kw`.

### 5.4 TAM symbol layer (no DOM markers)

**Icons** are generated lazily on `map.on('styleimagemissing', e => drawTamIcon(e.id))`. The id is `tam:{theme}:{fam}:{sh}:{ap}:{band}`, so there are at most 160 icons, and only the combinations that are used get drawn.

```js
const BAND_D = [7, 9.5, 12.5, 17, 23];        // logical diameter (px) at icon-size 1
const BAND_W = [1.5, 1.5, 1.6, 1.7, 1.8];     // stroke width stays constant because bands, not icon-size, carry kW
function drawTamIcon(id){
  const [, th, fam, sh, ap, band] = id.split(':'); if (!th) return;
  const pr = 2, d = BAND_D[+band], pad = 3, S = Math.ceil(d + 2*pad), r = d/2, P = PAL[th];
  const cv = document.createElement('canvas'); cv.width = cv.height = S*pr; const g = cv.getContext('2d'); g.scale(pr,pr);
  const path = new Path2D(); const cx = S/2, cy = S/2;
  if (sh === 't') { const R = r*1.22, y0 = cy + r*0.10;                // RO triangle, visually area-balanced
    path.moveTo(cx, y0 - R); path.lineTo(cx + R*0.866, y0 + R*0.5); path.lineTo(cx - R*0.866, y0 + R*0.5); path.closePath();
  } else path.arc(cx, cy, r, 0, Math.PI*2);                              // FiT circle
  g.lineJoin = 'round';
  g.strokeStyle = P.tamHalo; g.lineWidth = BAND_W[band] + 2; g.stroke(path);            // halo separates overlaps
  g.fillStyle = P.tamFill; g.fill(path);                                               // coin-like layering
  if (th === 'night') { g.shadowColor = P.fam[fam] + '99'; g.shadowBlur = 4; }
  g.strokeStyle = P.fam[fam]; g.lineWidth = BAND_W[band]; if (ap === '1') { g.setLineDash([2.2,1.8]); g.globalAlpha = .9; }
  g.stroke(path); g.setLineDash([]); g.globalAlpha = 1; g.shadowBlur = 0;
  if (fam === '3') { g.fillStyle = P.fam[3]; g.beginPath(); g.arc(cx, cy, 1.3, 0, 7); g.fill(); }   // "Other" secondary encoding
  map.addImage(id, g.getImageData(0,0,S*pr,S*pr), { pixelRatio: pr });
}
```

**Layers**

| Layer id | Type | Specification |
|---|---|---|
| `tam-heat` | heatmap | Night only, **P1**, `maxzoom 8`. `heatmap-weight: ['interpolate',['linear'],['get','kw'],0,.15,1000,.5,20000,1]`; `heatmap-intensity: zoom 4→.7, 7→1.1`; `heatmap-radius: zoom 4→10, 6→18, 8→30`; `heatmap-color: 0 transparent, .15 rgba(18,70,76,.20), .4 rgba(30,130,110,.32), .7 rgba(120,200,110,.42), 1 rgba(215,249,108,.55)`; `heatmap-opacity: zoom 5→.75, 7→.35, 7.8→0` |
| `tam-ghost` | symbol | Same layout as `tam-core`; `icon-opacity .10`; filter = `['!', ACTIVE]` |
| `tam-core` | symbol | Layout: `icon-image: ['concat','tam:',THEME,':',['to-string',['get','fam']],':',['get','sh'],':',['to-string',['get','ap']],':',['to-string',['get','band']]]` (`THEME` is a string literal re-set on theme change), `icon-size: ['interpolate',['exponential',1.5],['zoom'],4,.66,6,.84,8,1.05,11,1.4,14,1.75]`, `icon-allow-overlap: true`, `icon-ignore-placement: true`, `symbol-sort-key: ['-',0,['get','kw']]` (small on top). Paint: `icon-opacity: ['case',['boolean',['feature-state','hover'],false],1,['==',['get','ap'],1],.82,.96]` |
| `tam-samdot` | circle | filter `['all', ACTIVE, ['==',['get','sam'],1]]`; `circle-radius: zoom 5→1.6, 8→2.4, 12→3.2`; `circle-color #8FD14F`; `circle-stroke 1px #0B2E2A`. This is the "Verified in SAM" marker |

**Overplotting strategy for TAM** (P0):
- capacity bands with constant stroke;
- the paper fill and halo;
- small symbols on top;
- zoom-scaled `icon-size`;
- 10% ghosts;
- one-click family, subsidy and precision filters;
- the lime SAM dot.

No clustering in P0: the national pattern is the message. Hex-bin density at z < 6 is P2.

### 5.5 Selection, hover, picking

**Selection** uses three ring layers, one per kind, because zoom `interpolate` cannot be nested in `match`. Each has filter `['==',['get','kind'],K]`. The sources and radii are:
- `sel-sam`: `R(SIZE.sam, 4)`;
- `sel-hydro`: `R(SIZE.hydro, 4)`;
- `sel-tam`: `['interpolate',['exponential',1.5],['zoom'],4,['*',.66,['get','hr']],6,['*',.84,['get','hr']],8,['*',1.05,['get','hr']],11,['*',1.4,['get','hr']],14,['*',1.75,['get','hr']]]`.

The ring is 2 px, `--ink-1` on Paper and `#FFFFFF` on Night, with no fill. A halo layer uses the same radius at 10% ink. A pulse layer animates `add` from 5 to 21 and `circle-stroke-opacity` from .55 to 0 over 1.1 s, twice. In Present mode the pulse loops every 1.8 s. It is off under reduced motion.

**Hover**
- SAM and Hydro use `feature-state {hover:true}`: radius +2 and a thicker stroke.
- TAM uses the `hover` source with the same ring as `sel-tam` at 1.5 px and 70% opacity.

**Picking** (fixes v1's hollow-ring click interception):
- On `mousemove` (rAF-throttled) and `click`, call `queryRenderedFeatures([[x−8,y−8],[x+8,y+8]], {layers: CORE_LAYERS_OF_VIEW})`. On touch, use ±14 px.
- Choose the candidate whose **projected centre** is nearest the pointer. On ties, prefer the smaller radius.
- **Co-located stacks** (7 stacks in TAM, one 12 deep): if two or more candidates have centres within 3 px of each other, the sheet opens a **"N sites at this location"** chooser list first.

**Tooltip** (desktop, hover only)
- Shows the name, a colour key plus "Tier 2 · 5.9 MW · Boston" (SAM), "Biomass · RO · 60.0 MW" (TAM) or "High confidence · 1,309 kW stranded" (Hydro). Investor SAM adds "· £9.27M TCV".
- Styled with `--tooltip-bg` / `--tooltip-ink`, radius `--r-2`, padding 8×10, 12 px, max-width 260, offset (12, 12), clamped to the viewport.

### 5.6 Filters (MapLibre expressions mirrored by a JS predicate)

The state holds one `Set` per dimension, plus `kwMin` / `kwMax`. **Hidden sets persist across tabs** (v1 investor behaviour).

```js
const inSet = (prop, set) => ['in', ['get', prop], ['literal', [...set]]];
ACTIVE.sam   = ['all', inSet('t', tiers), ['>=',['get','kw'],kwMin], ['<=',['get','kw'],kwMax] /* investor: , inSet('pr', pricing) */];
ACTIVE.tam   = ['all', inSet('fu', fuels), inSet('sh', shapes), inSet('ap', precision), inSet('bt', tamTiers),
                ['>=',['get','kw'],kwMin], ['<=',['get','kw'],kwMax] /* investor: , scale<10MW chip */];
ACTIVE.hydro = ['all', inSet('c', confs), /* investor: */ inSet('exp', exportClasses), ['>=',['get','inst'],kwMin], ['<=',['get','inst'],kwMax]];
```

- `setFilter` is applied to the core, glow and hot layers with ACTIVE, and to the ghost layer with `['!', ACTIVE]`.
- The **same predicate in JS** drives the KPIs, the faceted legend counts and the histogram. Faceted counts are computed per dimension by evaluating all the *other* dimensions.
- **Filter changes never move the camera.** This fixes the v1 investor refit on toggle.
- On a theme change, re-apply the data paint, run `setLayoutProperty('tam-core'|'tam-ghost','icon-image', iconExpr(theme))`, and toggle the glow and hot layers' visibility.

### 5.7 Camera and framing

| View | Bounds on first entry | Padding |
|---|---|---|
| SAM | The SAM data bounds, padded by 0.25° | `{top:24, bottom:44, left: railW + 36, right: sheetOpen ? sheetW + 36 : 56}`. Mobile: `{top:16, bottom: peekH + 16, left:16, right:16}`. `maxZoom 7.2` for fits |
| TAM | **All** TAM data, including Scotland to 58.9°N | Same. This fixes the 26–34 missing Scottish sites |
| Hydro | **All 57** sites | Same. This fixes the 6 England and Wales sites that were missing. The Highlands intent is kept by the annotation, a "Zoom to Highlands · 31 sites" chip in the rail and the stronger relief |

**Rules**
- **Per-view camera memory.** Re-entering a view restores the camera it was left at. The Reset control (⟲) and `R` fit the view again. Switching SAM ↔ TAM keeps the camera if at least 80% of the new layer's active sites are inside the current bounds.
- A `ResizeObserver` on `#map` calls `map.resize()`. This fixes v1's stale size after tab switches and after the PPA page is shown. Returning from PPA calls `map.resize()` and restores the view camera.
- **Fly-to a site:** `flyTo({center, zoom: Math.max(map.getZoom(), 8.3), offset: [(leftObstruction − rightObstruction)/2, mobile ? −sheetH/2 : 0]})`. Map padding is never mutated. If the site is already visible and not covered, `easeTo` only if needed.

---

## 6. Layout and components

### 6.1 Desktop shell (target 1440×800; must also work at 1060–1300 wide × 780–820 tall)

```
┌─ header 56 (--header-bg) ───────────────────────────────────────────────────────────────────────┐
│ ■■ RenewaBlox │ CLIENT ATLAS      Peaker Model [TAM · 1,309|SAM · 129]  Hydro · 57 ┆ PPA Benchmark   [⌕ Search sites, towns, postcodes…  /] [◐] [⋯] │
│ ■■            │ no Watt wasted                                                       (investor: [▶ Present] before [◐])         │
├─ (investor) KPI band 64 ───────────────────────────────────────────────────────────────────────────┤
├─ map, full-bleed ───────────────────────────────────────────────────────────────────────────────────┤
│ ┌ rail 348 ┐  [✎ Notes]                                                        ┌ sheet 384 (open) ┐ │
│ │ kicker   │                                                                   │                  │ │
│ │ headline │                  (annotations, P1)                                │                  │ │
│ │ standfirst│                                                                  │                  │ │
│ │ KPI strip│                                                                   │                  │ │
│ │ legend   │                                                        [+][−][⟲] │                  │ │
│ │ capacity │  [size key]  [50 km]            [Simplified basemap pill]         │                  │ │
│ └──────────┘                                                              ⓘ attr └──────────────────┘ │
├─ (investor) footer 24: verbatim view footer, ellipsis, "Sources & method ›" ───────────────────────────┤
```

- The rail floats at `--gutter` inset from the top, bottom and left of the map area, with radius `--r-4` and `--sh-2`.
  - Paper: `--surface-0` solid with a 1 px `--rule`.
  - Night: glass.
  - Internal scroll with top and bottom scroll-shadows.
  - It **collapses** to a 44 px icon strip (button top-right of the rail, or the `L` key). On collapse, the map padding updates without moving the camera.
- The detail sheet slides in from the right: `--sheet-w`, same inset, radius `--r-4`, `--sh-3`. Map controls shift left by `sheetW + gutter`.
- The PPA view replaces the map area with a scrolling page (section 8). The header stays.

### 6.2 Header

Structure: `<header role="banner">`, then brand, `<nav>` with `role="tablist"`, then search, then actions.

**Brand.** Mark, then "RenewaBlox" wordmark (Newsreader), a 1 px `--header-rule` divider, then a stacked block: product label ("CLIENT ATLAS" / "INVESTOR ATLAS") over the tagline *no Watt wasted*. The `<h1>` is visually this lockup, and its accessible text is "RenewaBlox Client Atlas" / "RenewaBlox Investor Atlas".

**Mode tabs.** `role="tab"`, `aria-selected`, `aria-controls`.

| App | Tab labels (verbatim) |
|---|---|
| Client | `Peaker Model` · `Hydro · 57` · `PPA Benchmark` |
| Investor | `Peaker plants` · `Hydro` · `PPA Benchmark` |

- Tab styling: 13 px Inter 500, `--header-ink-2`. The active tab is `--header-ink` at 600 with a 2 px `--lime` underline.
- **PPA Benchmark** sits last, after a 1 px `--header-rule` vertical divider, so it is set apart.
- **Scope segmented control:** `role="radiogroup"` with labels `TAM · 1,309` | `SAM · 129`.
  - It sits inline, immediately after the Peaker tab, and is **only rendered in Peaker mode**: collapse its width over `--dur-2`, and set `aria-hidden` when hidden.
  - Pill track `rgba(255,255,255,.08)`. The active option is `--lime` fill with `#0B2E2A` text 600, and the count is in tabular numerals.
  - The scope control is hidden outside Peaker mode. The `S` shortcut still works there: it switches to Peaker and toggles the scope (v1 investor behaviour: choosing a scope forces Peaker).

**Search trigger.** A 240 px pill: `rgba(255,255,255,.08)` background, `--header-ink-2` text "Search sites, towns, postcodes…", and a `/` kbd hint. It collapses to a 36 px icon button at ≤ 1180 px.

**Actions**
- Theme toggle: `aria-pressed`, label "Night theme".
- Investor **Present** button: lime fill, `#0B2E2A` text, ▶ icon.
- `⋯` overflow menu with these items:
  - Sources & method
  - Download map image (P1)
  - Download CSV (P1)
  - Copy link to this view
  - Keyboard shortcuts (P1)
  - About this map (P1)

**Widths**
- ≤ 1180: the tagline hides.
- ≤ 980: the product label hides, and the tabs use short labels (`Peaker`, `Hydro`, `PPA`).
- It must not wrap at 1060.

### 6.3 Rail: editorial head, KPIs, legend-as-filter, capacity

Every section opens with a 1 px `--rule-strong` top rule, a 10 px gap, and then an eyebrow title. This is the D1 signature.

**(a) Head**

Client:

| View | Kicker | Headline | Standfirst |
|---|---|---|---|
| SAM | `PEAKER MODEL · SERVICEABLE MARKET (SAM)` | "129 AD plants that can earn when the grid runs tight" | "Verified anaerobic-digestion sites, graded into five Balancing-Mechanism tiers by where they connect. *Circle area shows installed capacity.*" |
| TAM | `PEAKER MODEL · ADDRESSABLE MARKET (TAM)` | "1,309 subsidised generators, 3.6 GW that could flex" | "Biogas, biomass, energy-from-waste, landfill and sewage-gas generators holding RO or FiT accreditation. *Colour is technology; shape is subsidy.*" |
| Hydro | `STRANDED HYDRO` | "57 hydro schemes generating more than the grid will take" | "Installed capacity exceeds the export capacity the network allows, so power is stranded behind the meter. *Circle area shows stranded kW.*" |

Investor. The standfirst is the **verbatim v1 subtitle**, and the headlines are new:

| View | Headline | Standfirst (verbatim) |
|---|---|---|
| SAM | "£221.9M of contract value across 105 priced AD peakers" | "Total Contract Value · Year 5 · 129 AD-peaker sites in the GB Balancing Mechanism" |
| TAM | "£7.17bn indicative potential across 1,309 subsidised sites" | "Total addressable market · 1,309 subsidised biogas, biomass & EfW sites · 3,612 MW" |
| Hydro | "57 stranded hydro units worth £13.6M (£35.6M with treasury)" | "Total Contract Value · Year 5 · 57 stranded hydro units · 100% Bitcoin mining" |

**Every number in a headline is computed from data at build time.** Never hand-type them.

When `max-height ≤ 840px`, the headline drops to 23 px and the standfirst clamps to 2 lines, with a "more" link.

**(b) KPI strip (client).** Three cells separated by 1 px `--rule` verticals. Each cell has an eyebrow label, a value in Figure M plus a unit in Inter 12 `--ink-2`, and a caption in Body S `--ink-3`. Below the cells is a **Universe line**: `Universe · 129 sites · 144 MW` (verbatim strings; see section 12). In P1, an **In view** switch (`role="switch"`) sits right-aligned on the Universe line.

| View | Cell 1 | Cell 2 | Cell 3 |
|---|---|---|---|
| SAM | CAPACITY SHOWN `143.6 MW` "installed" | SITES SHOWN `129` "of 129" | AVAILABLE FOR BM `90.5 MW` "known for 105 sites" |
| TAM | CAPACITY SHOWN `3,612 MW` "installed" | SITES SHOWN `1,309` "of 1,309" | AVAILABLE FOR BM `2,489 MW` "known for 727 sites" |
| Hydro | STRANDED CAPACITY SHOWN `15.2 MW` "behind the meter" | SITES SHOWN `57` "of 57" | INSTALLED `36.2 MW` "FiT register" |

- Number format is en-GB. MW values below 1,000 have 1 dp; at 1,000 MW and above there are 0 dp with a thousands separator. **"3611.9" must never appear again.**
- Values count up from their previous value.
- An `aria-live="polite"` sentence, debounced by 400 ms, announces changes: "Showing 25 of 129 sites, 49.9 MW".

The investor build has **no KPI strip in the rail**. Its KPIs live in the KPI band (section 10.1).

**(c) Legend-as-filter.** It is a `<table>`-like list of `<button aria-pressed>` rows.

Row anatomy:
- a 12 px swatch (the exact map glyph: filled dot, hollow ring, triangle or circle, dashed where relevant);
- the label (Inter 13, 500);
- the count (tnum `--ink-2`) and MW (tnum 600);
- a 2 px inline capacity bar under the label, in the swatch colour, scaled to the row's share of MW;
- a secondary line in Body S. On SAM tier rows this is the revenue string in `--lime-ink`.

Behaviour:
- Click, Enter or Space toggles the row. An off row is shown at 45% opacity, with a strikethrough on the label, and its features ghost on the map.
- An "Only" text button appears on row hover or focus, and isolates that row. ⌥/⌘-click does the same.
- "Show all" appears in the section title bar when anything is off.
- Hovering a row **previews** it on the map: the matching features stay at full opacity and other active features drop to 22%.

Client legends. The copy is verbatim; the counts are faceted and live.

| View | Title | Rows |
|---|---|---|
| SAM | `BM Tier — projected p/kWh (next 12m)` | `Tier 1 · Highest` … `Tier 5 · Lower`, each with the secondary line `29.6p avg · 122p top 5%` / `25.3p avg · 104p top 5%` / `21.7p avg · 80p top 5%` / `18.0p avg · 61p top 5%` / `16.0p avg · 50p top 5%`. Footnote: "Tier 1 sees ~2× and Tier 2 ~1.5× the GB-average offer-event frequency." |
| TAM | `TAM · total addressable market` (a real middle dot, so the S1 entity bug is fixed) | See the three groups below |
| Hydro | `Confidence` | `High` 37 · `Medium` 8 · `Low` 4 · `Unverified` 8, each with stranded kW. Footnote: "How confidently each FiT installation was matched to its network export record." Above the legend sits the "Where the power goes" split bar (D1): installed 36.2 MW, can export 21.1 MW, stranded 15.2 MW. |

The TAM legend has three groups:
- `SUBSIDY · SHAPE`: two chip toggles, `△ RO accredited 945` and `○ FiT accredited 364`. A precision chip pair follows: `○ Exact location 1,089` and `◌ Postcode district 220`.
- `TECHNOLOGY · RING`:
  - The **9 verbatim rows in v1 order** (sorted by MW): `Landfill gas 435 sites · 961 MW`, `Fuelled (biomass/AD/EfW) 262 · 877`, `Biomass 81 · 715`, `Waste / EfW 81 · 616`, `Biogas (AD) 294 · 234`, `Sewage gas 138 · 143`, `Advanced fuel 4 · 38`, `Biofuel - other 11 · 27`, `Biodiesel 3 · 1`.
  - Each row's swatch uses its **family** colour.
  - Above the rows is a 4-chip family quick-filter: `Landfill gas` · `Digestion gas` · `Thermal` · `Other fuels`.
  - A one-line note: "Colours group fuels into three families for colour-blind legibility; each site card names its exact fuel."
- `BM TIER · INDICATIVE`: a 10 px stacked bar in the tier ramp, with 6 labelled toggle chips below: `Tier 1 · Highest 78`, `Tier 2 · Strong 294`, `Tier 3 · Moderate 342`, `Tier 4 · Modest 455`, `Tier 5 · Lower 57`, `Scotland · no BM revenue 83`. Caption: "Filter only; not shown by colour on the map."

Investor legend differences:

| View | Title | Rows and notes |
|---|---|---|
| SAM | `Balancing Mechanism Tiers`, with subtitle "avg BM revenue vs 8.0p wholesale baseline" | `Tier 1 · Highest  4 · +270%`, `Tier 2 · Strong 41 · +216%`, `Tier 3 · Moderate 41 · +171%`, `Tier 4 · Modest 37 · +125%`, `Tier 5 · Lower 6 · +100%` (the uplift is in `--lime-ink`, 600). Plus a row `◯ Awaiting BM figure 24` (hollow swatch; toggles `pr = 0`). Then the verbatim SAM note (section 12.2). |
| Hydro | `Stranded Hydro` | Groups `Export class` (`Export-limited 48`, `No export 9`) and `Confidence` (4 rows), then the verbatim Hydro note |
| TAM | As client | Plus a **Scale** chip pair `All sizes` | `AD-scale only (<10 MW)`, then the verbatim TAM note |

The notes are shown expanded, clamped to 4 lines with "more".

**(d) Capacity** (D1/D2 histogram-slider)
- Title row: `CAPACITY` for SAM and TAM, `INSTALLED CAPACITY` for Hydro (v1 semantics: hydro filters on installed kW), with the current range right-aligned ("All sizes" / "1.0–5.9 MW").
- **Presets:** segmented `All sizes` · `Over 1 MW` · `Under 1 MW` (verbatim). Over is `> 1000 kW`; Under is `≤ 1000 kW`, with the tooltip "1 MW and under".
- The histogram is collapsed by default on heights ≤ 840 px, and opens with a disclosure. It has:
  - 26 log-scaled bins over the view's universe, with bar height ∝ √count;
  - in-range bars in `--ink-2` (Night: `--lime`) and out-of-range bars in `--ink-4` at 50%;
  - two overlaid `<input type="range">` thumbs (keyboard-accessible), snapped to 2 significant figures;
  - end labels (`100 kW` / `5.9 MW`).
- KPIs update live during a drag (rAF-throttled `setFilter`).

**(e) Rail foot.** A "Sources & method ›" link opens the drawer (section 6.7). Client Hydro also has a "Zoom to Highlands · 31 sites" chip.

### 6.4 Detail sheet (replaces all Leaflet popups)

**Container**
- Desktop: right sheet, `role="dialog"` **non-modal** (`aria-modal="false"`), `aria-labelledby` pointing at the name.
- Focus moves to the close button on open and returns to the invoking element on close.
- Header row: kind chip (e.g. `● TIER 1 · HIGHEST`, `△ BIOMASS · RO`, `● HIGH CONFIDENCE`), then in P1 `‹ 3 of 129 ›` step-through (J/K), then ×.
- The body scrolls, and the actions footer is sticky.

**Common anatomy**
- Name in Newsreader 24, **display-cased**: ALL-CAPS names are converted to Title Case, keeping acronyms such as AD, STW, WTW, CHP, EfW, UK, SPV and Ltd.
- Meta line: `Town · Postcode · Local authority` (SAM), `Fuel · RO ref` (TAM), `Stranded hydro · 57.66° N, 4.36° W` (Hydro).
- Sections separated by a 1 px `--rule-strong` top rule and eyebrow titles.
- Figures in Newsreader; labels in Inter.

**Client SAM card**, in this order:
1. **Projected Balancing Mechanism Revenues** (verbatim heading), with right-aligned "next 12 months".
   - Two hero figures: `Average 29.6 p/kWh` | `Top 5% 122 p/kWh` (Figure L).
   - The **revenue ladder** (D1): a 5-row dumbbell chart from avg to top 5% for T1–T5 on a 0–125p axis. This site's tier is highlighted in its tier colour; the others are `--ink-4`.
   - For Tier 1 and 2 only, a callout chip: `Offer-event frequency: ~2× GB average` (T1) / `~1.5×` (T2).
2. **Capacity:** three figures, `Installed`, `Onsite demand / Stranded` and `Available for BM`, in kW from the canonical split. A null shows *Unknown*.
   - The split bar has a hatched onsite segment and a solid tier-colour BM segment, plus a hatched grey "not yet split" remainder when onsite + BM < installed (Rotherdale, Scrivelsby).
   - Captions give the percentages.
3. **Route to market:**
   - `Offtaker`: cleaned name, or `Sole holder · unbundled`, or `Not identified`. It carries an `inferred` tag, with the tooltip "Inferred from the largest external REGO certificate holder: strong evidence of who buys the power, not contractual proof."
   - `Export`: `Negotiated PPA` / `FiT standard` / `Behind meter` / `Unknown`.
   - `Operator`.
   - `Commissioned 2014 · 12 yrs`.
4. **Nearby** (P1): the 3 nearest active sites in the same layer, with distance in km. Tap to hop.
5. **Actions:**
   - Primary (lime fill): **Talk to us about this site**, a `mailto:` link.
   - Secondary: `Zoom to site`, `Copy link`, `See in register`. The last switches to PPA, filters the register to this site and scrolls to and highlights its row.

The mailto link:
- address `ATLAS_CONFIG.contactEmail` (`callum@renewablox.com`);
- subject `RenewaBlox — {name}, {town} ({outcode})`;
- body `Hi Callum,\n\nI'd like to talk about {name} ({postcode}): {tier label}, {installed} kW installed.\n\nLink: {shareUrl}\n`.

**Client TAM card**
- Fuel chip: glyph plus exact fuel, tinted `--surface-2`, text `--ink-1`. This fixes the v1 white-on-light pill (2.85:1).
- If `sam = 1`: a banner "**Also verified in SAM** · open peaker profile ›".
- `Capacity {kw} kW`, or `—`. At ≥ 10,000 kW, append "(53.0 MW)".
- `Available for BM {bm} kW`, or *Unknown*.
- `Site aggregates {units} MPAN records` when units > 1.
- `BM tier: Tier N · Label (indicative)`, or `BM tier: Scotland · no BM revenue`.
- `Subsidy: RO accredited` | `FiT accredited`.
- The RO code in `--font-mono`.
- `Approximate location (postcode district)` when `ap = 1`.
- Then Nearby and the actions (Zoom, Copy link).

**Client Hydro card**
- Confidence in **words** in the chip: "High confidence".
- A `No export` badge, **or** `Installed capacity {inst} kW` and `Export capacity {mec} kW`.
- Hero: `{kw} kW stranded` (Figure L, in the hydro colour).
- Split bar (export vs stranded), captioned "94% stranded".
- Explanation line: "Installed capacity (FiT register) exceeds the export capacity (MEC) the network operator allows, so this share of output has nowhere to go."
- Nearby, then actions: **Talk to us about this site**, Zoom, Copy link.

**Investor cards.** Same shell and components, with these additions.

*Investor SAM*
- Meta, verbatim format: `Tier 3 · Moderate | NG4 2JT · B East Midlands` (tier name | town · postcode · GSP).
- **Commercials** section:
  - Hero `TCV · no treasury £9.27M` and `TCV · treasury £12.4M` (abbr), each with the full `gbp0` value beneath in Body S.
  - **TCV split bar:** BM / energy revenue (`en`) vs BTC value (`tcv − en`), with a legend.
  - `BTC mined (Yr 5) 26.86` (2 dp).
- **Capacity:** Installed, Available for BM.
- **Route to market:** Operator (`dev`, full name, CSS ellipsis with a `title`, no hard truncation), Offtaker (inferred), Export.
- **Register** (from the PPA data): Commissioned, FiT gen p/kWh, FiT ends, Yrs left (a runway bar out of 10 years), REGO status (raw label with a status dot).
- Unpriced sites: `Status: Awaiting BM figure` replaces Commercials.

*Investor Hydro*
- `Stranded capacity`.
- Chip `{Export-limited|No export} · {conf} confidence`.
- `BTC mined (Yr 5)`.
- `Energy export £0 · 100% mining`.
- `TCV · no treasury`, `TCV · treasury`.
- Plus installed and export capacity, joined from the client HYX by name and coordinates.

*Investor TAM*
- Capacity, Available for BM, Aggregated units, `BM tier` (or `BM status` when bt = 0), Subsidy (`RO accredited` / `FiT accredited` / `Not confirmed`, from `src`), RO ref, `Location: Approx · postcode district | Exact · DNO register`, `In SAM: Verified site`.
- P1: "Indicative TCV potential for this site: {bmKw × TCVRATE[bt]}", with a method ⓘ.

### 6.5 Command palette (search)

- **Open** with `/`, ⌘K / Ctrl-K, or the header pill. Structure: `role="dialog"` with a combobox (`aria-expanded`, `aria-activedescendant`) and a listbox.
- **Layout.** Desktop: 640 px wide, centred at 12vh, over a scrim, `--surface-1`, `--sh-3`, `--r-4`. Mobile: full screen.

**Index** (built once at load)

| Layer | Fields indexed |
|---|---|
| SAM | name, full site address, town, local authority, postcode (both spaced and compact), outcode, operator, cleaned offtaker. Investor adds `dev`. |
| TAM | name, fuel, family, RO ref |
| Hydro | name |

**Normalisation:** lower-case, strip diacritics, collapse whitespace, strip punctuation. Postcode compact form is uppercase with no space. A query is detected as a postcode by `/^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/i` (full) or `/^[A-Z]{1,2}\d[A-Z\d]?$/i` (outcode).

**Scoring** (D2), per token, with all tokens required (AND):
- prefix of a field: 100;
- word-start: 82;
- compact-postcode match: 70;
- substring: 55;
- subsequence fuzzy on names only, for tokens of 3 or more characters: 30.

Field weights: name 1.0, RO ref .95, postcode .95, town .8, operator / dev .7, local authority .6, offtaker .5, fuel .5. Results in the current view get +10.

**Results**
- Grouped as `VERIFIED AD · SAM`, `STRANDED HYDRO`, `ALL SUBSIDISED · TAM` (current view first), with 6 per group and a "Show all N" row.
- Row: glyph, name with the matched text **underlined** in `--lime-ink` (not colour alone), a sub-line (`Town · Postcode · Operator`, or `Fuel · RO ref`), and a right column with capacity plus tier or confidence.
- The top row is a **Zoom to all N results** action. This preserves v1's zoom-to-results via `fitBounds`.
- Keyboard: ↑ ↓ Enter Esc.
- **Empty state:** "Largest sites" (top 5 across layers) plus suggestion chips: `Tier 1 sites`, `Highlands hydro`, `Over 1 MW`, `KT16 0EF`.

**Choosing a result:**
1. Switch mode and scope.
2. If a filter hides the site, clear that dimension and show a toast: "Showing Tier 4 again so you can see this site · Undo".
3. `flyTo` the site, open the sheet and pulse the marker.

**Zero results:** "No sites match '…'". If the query is a postcode, add the action "Show sites near {postcode}" (P1, via postcodes.io).

### 6.6 Map chrome

- **Controls.** Bottom-right stack at `--surface-float`, 36 px buttons with `--sh-1`: `+`, `−`, `⟲ Reset view`. Investor P1 adds `3D` in Hydro. Mobile keeps `⟲` only; pinch handles zoom.
- **Size key.** Bottom-left of the map area, to the right of the rail: nested circles or bands with labels (section 5.2), and a title such as `INSTALLED CAPACITY`, `STRANDED CAPACITY`, `CONTRACT VALUE (TCV)` or `CAPACITY BAND`.
- **Scale bar.** MapLibre `ScaleControl` (metric), below the size key.
- **Notes toggle.** Client P1: a pill button "✎ Notes" at the top-left of the map area, beside the rail.
- **Toasts.** Bottom-centre, 3.2 s, optional action.
- **Night vignette.** A `--vignette` overlay with `pointer-events: none`.

### 6.7 Sources & method drawer (P0)

A right-side drawer 480 px wide (full screen on mobile), `role="dialog"` `aria-modal="true"`. Sections:

1. **Data sources:**
   - Ofgem FiT Installation Report (Mar 2026);
   - Ofgem RO / REGO registers (Aug 2026);
   - DNO Embedded Capacity Registers (NGED, NPG, SPEN, SSEN Jul-2026, UKPN);
   - Elexon BMRS MID;
   - Montel / EEX (11 Aug 2026);
   - postcodes.io;
   - OpenFreeMap / © OpenStreetMap contributors;
   - Natural Earth;
   - AWS Terrain Tiles.
2. **Provenance** (the PPA paragraph, verbatim).
3. **Glossary:** BM, BM tier, SAM, TAM, REGO, FiT, RO, MEC / export capacity, stranded, MPAN, offer event. Investor adds TCV, Treasury and Year 5.
4. **Investor only:**
   - the three legend notes and three footers, verbatim;
   - the **TCV method table**: TCVRATE £/kW-available by tier (2,671.41 / 2,544.82 / 2,438.84 / 2,329.91 / 2,271.03), AVRATIO 73.4% (0.73392), and the formulas for `bmKw` and `tcvPot`;
   - the as-of stamps.
5. "Data as of 11 Aug 2026" (from `DATA.kpi.asOf`).

### 6.8 Mobile (≤ 760 px; QA at 390×844)

**Header**
- Row 1 (52 px): mark, "RenewaBlox", the product label (10.5 caps), and on the right `⌕`, `◐`, investor `▶` and `⋯` (44 px targets).
- Row 2 (44 px): `Peaker [TAM 1,309 | SAM 129]  Hydro 57  PPA`. Scope only appears in Peaker mode; labels are compact. It scrolls horizontally if needed; nothing may overlap.

**Investor KPI band.** A horizontal scroll-snap strip, 52 px, with 2.5 cells visible so the next is peeking.

**Map.** Full-bleed. Attribution is collapsed to ⓘ, and zoom buttons are hidden.

**Rail → bottom sheet**
- Peek of 136 px: kicker, a 1-line headline (20 px), and the KPI strip (client) or the scope description (investor).
- The handle is a `<button aria-expanded>`. Tapping it expands to 78vh with the full legend and filters. A drag gesture is P1.
- The map fit padding includes the peek height.

**Card → bottom sheet** (replaces the rail sheet while open)
- Snap A at 46vh: kind chip, name, the hero figures, and the primary CTA.
- Snap B at 90vh: everything.
- Fly-to offset keeps the site visible above the sheet.

**Search.** Full-screen overlay, input autofocused.

**PPA.** Single column. Tiles are a 2-up grid with the fifth spanning. Charts are measured to width (section 8). Filters sit in a collapsible "Filters (2)" bar. The register is a stacked row list: Operator / Town / kW / Export chip / Status, and tapping a row expands the rest.

**Touch.** Hit radius ±14 px. There is no hover tooltip on touch; a tap opens the card.

---

## 7. Interactions

### 7.1 Keyboard

Shortcuts are ignored while focus is in a text input.

| Key | Action |
|---|---|
| `/`, ⌘K, Ctrl-K | Open search |
| `1` `2` `3` | Peaker / Hydro / PPA |
| `S` | Toggle TAM ↔ SAM (in Peaker mode) |
| `T` | Toggle theme |
| `R` | Reset view |
| `L` | Collapse or expand the rail |
| `J` / `K` (and ← → when focus is inside the sheet) | Next / previous site in the filtered list (P1) |
| `Esc` | Close the palette, then the sheet, then the drawer, then exit Present |
| `P` | Present (investor) |
| `?` | Shortcut dialog (P1) |
| In Present | ← → Space PageUp PageDown step, Home goes to the first chapter, Esc exits |

MapLibre's own keyboard handling (arrows pan, `+`/`-` zoom) is active when the map canvas has focus. The canvas gets a visible inset focus ring.

### 7.2 Focus and accessibility behaviour

- `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }` on every control. The header uses `--lime`. The removed-outline input from v1 is gone.
- `<html lang="en-GB">`.
- A skip link: "Skip to search".
- Every input and select has a `<label>`, visually hidden where needed.
- Tabs use `tablist` / `tab` / `aria-selected`. Legend rows are `<button aria-pressed>`. Scope is a `radiogroup`. PPA sort headers are `<button>` inside `<th aria-sort>`. Data-table toggles carry `aria-expanded` and `aria-controls`.
- **The accessible path to every site is the search palette.** The map has no per-feature tab stops; the 945 v1 tab stops are removed. A P1 "Sites list" (`role="table"`) shows the visible sites.
- **Redundant encodings everywhere:**
  - TAM shape = subsidy, dash = precision, and the "Other" family gets a centre dot;
  - hydro Unverified is a hollow ring;
  - investor unpriced sites are hollow rings;
  - every card and tooltip states tier, fuel and confidence **in words**;
  - status dots always carry a label.

### 7.3 State, URL and persistence

**State**

```js
state = { view:'sam'|'tam'|'hydro'|'ppa', theme:'paper'|'night', site:'<key>'|null,
          hidden:{ tiers:Set, fuels:Set, shapes:Set, precision:Set, tamTiers:Set, confs:Set, export:Set, pricing:Set },
          kw:{ sam:[min,max], tam:[..], hydro:[..] }, cams:{ sam:{c,z}, tam:{..}, hydro:{..} },
          ppa:{ cls, off, status, q, sort:{key,dir} }, present:null|chapterIndex }
```

**Boot order**
1. `window.__ATLAS_INIT__`, which the wrapper injects from `st.query_params` (section 15);
2. `location.hash`;
3. `localStorage` (theme and last view only);
4. the app defaults.

**Hash.** `#v=sam&s=KT160EF&z=8.3&c=-0.52,51.39&th=night`, written with `history.replaceState` inside try/catch. This works when the page is hosted standalone.

**Copy link**
- If `ATLAS_CONFIG.publicUrl` is set, build `publicUrl + '?view=sam&site=KT160EF&theme=paper'`; otherwise use the hash URL.
- Copy with `navigator.clipboard.writeText`. If that fails, as it can in a sandboxed srcdoc iframe, show a popover containing a selected read-only input and the hint "Press ⌘C / Ctrl-C".
- **The investor build never puts commercial values in URLs**, only view, site key, theme and chapter.

---

## 8. PPA Benchmark (full port and restyle; all content preserved)

**The S1 bug is fixed by construction.** All tokens are on `:root` / `[data-theme]` (section 3), and the PPA CSS contains no scoping prefix.

The view is a page that scrolls inside the area below the header (and below the KPI band for the investor). Content has `max-width: 1200px` and padding 32 / 40, or 16 on mobile.

### 8.1 Page structure

1. **Intro**
   - `<h2 class="kicker">` with the text `PPA & Price Benchmark` (verbatim).
   - A deck in Display XL: "At 3% CPI, the guaranteed FiT export rate overtakes the forward curve by 2028". The CPI qualifier is mandatory.
   - The intro paragraph verbatim ("Where each SAM site's export sits against the GB market. … not obtainable from any source."), in Newsreader 14.5 at `--ink-2`.
2. **Stat tiles.** Five tiles in D1's ruled style: a 1 px `--rule-strong` top rule and no card chrome on Paper; glass tiles on Night.
   - Each tile has an eyebrow label, a Figure M value with the unit `p/kWh` (Inter 12), and a note in Body S.
   - Values are bound to `DATA.kpi` (base12, win26, cal28, fit). The spread (49%) comes from `data/*/ppa.json` → `spread`. Nothing is hard-coded in HTML.
   - An as-of stamp "Data as of 11 Aug 2026" sits right-aligned above the row.
3. **Chart row** (12-column grid)
   - Price chart panel: 8 columns.
   - Right column: 4 columns, containing
     - **The crossover** callout (verbatim), with a 3 px `--lime` left rule (on Paper it pairs with `--lime-wash`) and "**5% above market**" in 600;
     - a small "How to read this chart" key.
   - Below 1100 px the row stacks.
4. **Filters bar**
   - `position: sticky; top: 0` inside the PPA scroller, `--surface-0`, with a 1 px bottom rule.
   - Labelled selects: `Export arrangement`, `Certificate counterparty` (cleaned names), `Generating status`.
   - Input `Find a site` with placeholder `operator, town, postcode`. It searches operator, town, postcode (normalised, with or without the space), site and offtaker.
   - A `Reset` button.
   - Result line: `{n} of 129 sites · {mw} MW · {k} counterparties`.
   - The filters drive the counterparty chart, the register and the result line (client) or the KPI band (investor). They do not drive the price chart (v1 behaviour).
5. **Counterparty chart** (5 columns) and **Site register** (7 columns) side by side at ≥ 1280 px, stacked below that.
6. **Provenance** (verbatim), in Body S at `--ink-2` with 1.6 line height, under a `--rule-strong` rule.

### 8.2 Price chart

- **Sizing.** The SVG is drawn at the container's **CSS pixel width**, measured with a `ResizeObserver`. Height is `clamp(260px, width × .42, 400px)`. Margins are L44 R96 T20 B36, or R64 when width < 700. There is **no viewBox scaling**, so text stays 11–12 px at every width.
- **Axes**
  - y runs 5–14 with gridlines at 6, 8, 10, 12, 14 (`--rule`). The label `p/kWh` sits above the axis top-left, which fixes the collision with the "14" tick.
  - x runs 2024-08 to 2028-12. Ticks are every Jan and Jul (`Jan 25`, `Jul 25`) at ≥ 700 px, and Jan only below that.
  - The baseline is `--rule-2`.
- **Series**
  - Realised: 24 points, a 2 px line in series-1, dots r 2.4, and an area fill of series-1 at 8% down to the baseline.
  - Forward blocks: 3 px bars in series-2 with 6 px vertical end caps. Above each block, the key (10.5 px `--ink-3`) and the value `toFixed(2)` (11.5 px 600 `--ink-1`). The blocks are `Q4-2026 12.601`, `Q1-2027 12.391`, `Q2-2027 8.605`, `H2-2027* 8.25`, `Cal-2028 7.744`.
  - FiT rule: 1.5 px dashed `--ink-3` at 7.64, labelled `FiT 7.64p` right-aligned below the line.
  - CPI path: dotted `--ink-2` through Jul-2026 / Jul-2027 / Jul-2028 at `7.64 × 1.03^(y−2026)`, labelled `FiT +CPI 8.11p` above the line end. The two labels must never overlap; shift them vertically if they would.
  - Today divider: a dashed `--rule-2` line at 2026-08, labelled `realised` on the left and `forward` on the right.
- **Legend** above the chart, verbatim: `Realised — Elexon MID (EPEX)` · `Forward blocks — Montel / EEX, 11 Aug 2026` · `FiT standard export tariff (7.64p, CPI-linked)`. Each entry has a line swatch of its actual stroke style.
- **Footnote** under the chart: `* H2-2027: {text supplied by the product owner}` (see the open questions).
- **Tooltip.** Solid `--tooltip-bg` with verbatim formats:
  - a forward block: `**{k}** forward / {p} p/kWh / FiT tariff is {±n}% vs this block`;
  - a realised month: `**{Mon YY}** realised / {p} p/kWh / FiT tariff is {±n}% vs this month`.
  - **The sign is always shown**, including "+". A crosshair hairline follows the pointer.
- **Input methods**
  - Mouse: hover.
  - Touch: tap pins the tooltip; tap outside clears it.
  - Keyboard: the chart is `tabindex=0 role="img"` with `aria-describedby` pointing at the data table. ← → steps through the 24 months and then the 5 blocks, and Esc clears.
- **Data table.** A `Show data table` / `Hide data table` button (`aria-expanded`) reveals a table with columns `Period | Basis | p/kWh`.

### 8.3 Counterparty chart ("Who holds the certificates")

- Title verbatim. The caption is verbatim, with *external* in italic.
- Count line: `{n} counterparties across {m} sites`. **n counts real external suppliers only**, so the default is 21, not 23: "Not identified" and "Generator is sole holder" are excluded.
- **Bars**
  - Horizontal, 28 px rows, sorted by MW descending.
  - **"Not identified" is pinned last** in `--ink-4` grey. **"Generator is sole holder"** is series-1 with a 45° hatch (an SVG pattern).
  - Name column 40% width: cleaned names, CSS ellipsis and a `title`. Value `34.5 MW`, tnum, right-aligned.
- **Tooltip:** `{name} / {mw} MW · {c} site(s)`.
- **Data table** toggle with columns `Counterparty | Sites | MW`.
- P1: clicking a bar sets the Certificate counterparty filter. With "Show on map", the SAM view is filtered to those sites.

**Name cleaning** is applied at build time, in the same way for the chart, filter, register and card:
- strip `(Supplier)`, ` - Supplier - SUP\d+` and a trailing ` Limited`/` Ltd` duplicate;
- fix the source typo "Internatinal" to "International";
- display-case.

The raw names are kept in the investor data for audit.

### 8.4 Site register

- Title `Site register`. Caption verbatim.
- Count line: `{n} of 129 sites · {mw} MW`, using the canonical MW (143.6 when unfiltered).
- **11 columns**, headers verbatim:
  1. `#`: the client shows the display label **`Ref`** (a neutral register order: tier, then kW descending; see section 13); the investor shows `#` (v1 rank);
  2. `Operator`: display-cased, CSS ellipsis at 28ch with a `title`;
  3. `Town`;
  4. `kW`;
  5. `Comm.`;
  6. `Export arrangement`: chip;
  7. `Supplier (largest external REGO holder)`: cleaned name, plus `+self` in `--ink-3` when `self_certs > 0`; *sole holder* and *not identified* in italic;
  8. `FiT gen p/kWh`: 2 dp;
  9. `FiT ends`: `Mar 2031` format;
  10. `Yrs left`: 1 dp plus a 40 px runway micro-bar;
  11. `Status`: dot plus label.
- **Status labels**
  - Investor: raw (`active`, `lagging/winding down`, `likely ceased`, `no REGO certs`).
  - Client: **softened** to `Active`, `Certificates declining`, `No recent certificates`, `No REGO certificates` (see the open questions). The filter options use the same labels.
- **Sort.** Header buttons with `aria-sort`, ↑ / ↓ glyphs, numeric or `localeCompare('en-GB')`, **nulls always last**, and a consistent comparator. Default sort: Ref / # ascending.
- **No nested scroll box.** The table flows in the PPA page. `thead` is sticky at `top: {filtersBarHeight}`. The first column (Ref + Operator combined on ≤ 1280) is sticky-left with a `--surface-1` background and a right shadow while scrolled.
- **Rows.** Hover `--wash`. P1: a row click opens the site on the map ("Show on map ›" appears on hover or focus).
- **CSV** (P1): the client-safe columns of the filtered rows. The investor CSV adds a first row "Confidential — investor use only".

---

## 9. Night vs Paper per app (theme behaviour)

| | Client | Investor |
|---|---|---|
| Default theme | Paper | Night |
| Marker glow and hot centres | Night only | Night only |
| Rail surface | solid paper / glass | glass / solid paper |
| KPI location | Rail strip | KPI band (+ market strip ≥ 1280 px) |
| Header | `#0B2E2A` | teal gradient |
| Present mode | P2 | P0 (minimal), P1 (autoplay, 3D) |
| Annotations | P1 | Via Present chapters |

---

## 10. Investor-only specifics

### 10.1 KPI band (64 px, below the header)

**Cells.** Each cell has an eyebrow label (10.5 caps), a value (Newsreader 26, tnum) and a sub-caption (Body S `--ink-3`). Cells count up and are separated by 1 px `--rule`. An as-of stamp sits at the right of the cell group: `Model · 16 Jun 2026 · Indicative; not investment advice.` for SAM / Hydro, `Registers · Jul–Aug 2026` for TAM, `Prices · 11 Aug 2026` for PPA.

**Formulas** are preserved exactly (investor audit §1.3–1.4). They are computed over **visible** sites.

| View | Cells (labels verbatim) | Default values |
|---|---|---|
| SAM | `SITES` (priced visible; sub "priced · of 129") · `AVAIL. FOR BM` (Σav, 1 dp MW) · `BTC MINED` (round Σbtc; sub "Year 5") · `TCV` (abbr Σtcv; sub "no treasury") · `TCV (TREASURY)` (abbr ΣtcvT) | **105 · 90.5 MW · 639 · £221.9M · £327.4M** |
| Hydro | `SITES` · `STRANDED` · `BTC MINED` · `TCV` · `TCV (TREASURY)` | **57 · 15.2 MW · 177 · £13.6M · £35.6M** |
| TAM | `SITES` · `CAPACITY` · `IN BM TIERS` · `TCV POTENTIAL` | **1,309 · 3,612 MW · 3,337 MW · £7.17bn** |
| PPA | `SITES SHOWN` · `CAPACITY SHOWN` · `COUNTERPARTIES` · `REALISED 12M` · `WINTER-26 FWD` | **129 · 143.6 MW · 21 · 8.52p · 12.50p** |

**TCV Potential caveat.** The caveat sits **inside the TCV Potential cell**, directly under the value: "£4.08bn of it from 76 sites ≥ 10 MW ⓘ". The ⓘ opens a method popover with the TCVRATE table, AVRATIO, the formula and the "727 sites" basis. The rail's Scale chip `AD-scale only (<10 MW)` recomputes the value, giving £3.09bn by default.

**Market strip.** At ≥ 1280 px, a right-aligned, static strip: `GB POWER  Baseload 12m 8.52p · Win-26 12.50p ▲47% · Cal-28 7.74p · FiT 7.64p · 11 Aug 2026`. It has **no "live" pulse dot**, because the data is a snapshot.

**Footer bar** (24 px). The verbatim footer for the current view (SAM/Hydro, TAM or PPA), 11 px `--ink-3` (AA; this fixes v1's 2.38:1), on one line with an ellipsis, plus a "Sources & method ›" link.

### 10.2 Derived economics (unchanged; computed at runtime from investor data)

- `WHOLESALE = 8.0`
- `TAVG = {1:29.6, 2:25.3, 3:21.7, 4:18.0, 5:16.0}`
- uplift = `round((TAVG[t]/8.0 − 1) × 100)`
- `TCVRATE[t] = Σtcv / Σav` over priced PEAKER rows in tier t
- `AVRATIO = Σav / Σinst` over priced rows
- `bmKw(d) = d.bm ?? (d.kw || 0) × AVRATIO`
- `tcvPot(rows) = Σ over bt>0 of bmKw × TCVRATE[bt]`
- `abbr()` and `gbp0()` semantics exactly as in v1.

The build asserts these reproduce the literals (appendix A).

### 10.3 Present mode (P0 minimal; P1 autoplay and 3D)

- **Entry:** `▶ Present` or `P`, or boot straight into it with `?present=1` or `#present=1`.
- It calls `requestFullscreen()` on `documentElement` inside try/catch. If the iframe forbids fullscreen, a toast says "Tip: press F11 for full screen".
- The rail, KPI band and footer fade to 0 over `--dur-4`, and the header dims to 60%.
- **Chapter card.** Bottom-left glass card, 480 px wide, `--r-4`, `--sh-3`. It contains:
  - an eyebrow `CHAPTER 2 / 6`;
  - a title in Display XL, with one phrase in `--lime-ink` italic;
  - a body of 2–3 lines in Inter 14;
  - a row of three stats (Newsreader 26 plus an eyebrow);
  - 6 progress segments;
  - `‹` / `Next ›` (lime) / `Play` (P1, 9 s per chapter) / `Exit · Esc`.
- **Chapters** are data in `atlas/apps/investor/story.json`: `{view, filters, camera:{center,zoom,pitch?,bearing?}, title, body, stats:[{label, expr}]}`. Stats are computed from data at runtime.

| # | Title | View and camera | Stats |
|---|---|---|---|
| 1 | "The market: *1,309* fuelled generators" | TAM, fit GB | 1,309 sites · 3,612 MW · £7.17bn potential. The caveat "£4.08bn from 76 sites ≥ 10 MW" is shown in the body |
| 2 | "The verified pipeline" | SAM, fit | 105 priced of 129 · 90.5 MW available for BM · £221.9M TCV (£327.4M treasury) |
| 3 | "Where flexibility *pays most*" | SAM filtered to T1 + T2; camera `[0.35, 51.75]` z 7.4 (pitch 30 in P1) | 29.6p avg · 122p top 5% · ~2× offer frequency |
| 4 | "Stranded hydro in *the Highlands*" | Hydro; camera `[-4.6, 57.1]` z 6.9 (P1: 3D terrain, pitch 58, bearing −12) | 57 sites · 15.2 MW stranded · £13.6M (£35.6M treasury) |
| 5 | "Why now: *the crossover*" | PPA, scrolled to the price chart | FiT 7.64p · Cal-28 7.74p · FiT +CPI 8.11p |
| 6 | "Who buys the power" | PPA, scrolled to the counterparty chart | 21 counterparties · EDF 34.5 MW · Drax 16.5 MW |

- On exit, restore the pre-Present state (view, filters, camera, theme).
- P1 3D: add a raster-dem source `rbx-dem-3d`, reusing the kit's `demUrl` with encoding `terrarium`, then `map.setTerrain({source:'rbx-dem-3d', exaggeration:1.7})`. Enable `dragRotate` while it is on. Keep bearing ≤ 18°, because the canvas city labels don't rotate.

---

## 11. Feature priorities

### P0: ship now (both apps unless marked)

1. **Build pipeline** (section 14): `atlas/` source tree, shared core, two app templates, per-audience data JSON, `atlas/build.py` writing `client_atlas.html` and `investor_atlas.html` at the existing paths, with number asserts, a must-preserve copy check and the client-safety scan.
2. **Design system:** tokens (section 3), Google Fonts, Paper and Night themes with a toggle and persistence. Client defaults to Paper, investor to Night.
3. **Basemap:** kit integration with the `paper` / `night` palettes, `focus:'uk'`, GB and Ireland labels only, per-view relief, offline pill, correct attribution (postcodes.io in; RenewaBlox CRM out).
4. **Header and navigation**, responsive at 1440 / 1060 / 390: modes, scope shown only in Peaker mode, search trigger, theme, overflow menu, investor Present button.
5. **Map layers** per section 5:
   - sqrt-area zoom-scaled circles and the validated palettes;
   - ghosts and sort keys, with Tier 1 and small sites on top;
   - Night glow;
   - TAM lazy icons (family × shape × dash × band) and the SAM-in-TAM dot;
   - hover state and tooltip, nearest-centre picking, the co-located stack chooser, the selection ring and pulse.
6. **Rail:** editorial head (investor: verbatim subtitles); client KPI strip with the Universe line and aria-live; legend-as-filter (toggle, Only, Show all, faceted counts, hover preview); capacity presets and histogram slider; size key and scale bar; rail collapse.
7. **Camera:** per-view fit to the full data (fixes all v1 clipping), per-view camera memory, no refit on filter changes, `ResizeObserver`, Reset view.
8. **Command palette search** across all layers: postcodes with or without the space, outcodes, RO refs, operator. Grouped results, "Zoom to all N results", fly, open and pulse, and clearing any hiding filter with Undo.
9. **Detail sheets** for SAM / TAM / Hydro, with every v1 field, value first. Client: the *Talk to us about this site* mailto CTA and *See in register*. Investor: Commercials (TCV, treasury, TCV split bar using `en`, BTC), register data, unpriced status. Both: Zoom to site and Copy link.
10. **PPA Benchmark full port** (section 8): tokens fixed; responsive, measured SVG charts; mouse, touch and keyboard tooltips; data tables; filters; counterparty chart (grey Not-identified pinned last, cleaned names, count of 21); 11-column register (`aria-sort`, sticky header and first column, no nested scroll); tiles bound to `DATA.kpi`; as-of stamp; provenance; client status labels softened.
11. **Mobile layouts** (section 6.8): header rows, bottom-sheet rail and card, full-screen search, investor KPI scroll strip, single-column PPA with row-list register.
12. **Accessibility baseline** (sections 7.1–7.2): `lang`, labels, roles and ARIA state, focus-visible rings, keyboard shortcuts including `/` and Esc, AA text tokens, validated CVD-safe palettes, redundant encodings, reduced motion, no marker tab-stop traps.
13. **Investor numbers:** KPI band with exact formulas and as-of stamps; TCV Potential caveat plus the AD-scale chip plus the method popover; unpriced hollow rings; verbatim legend notes, footers and subtitles; hidden filter state persisting across tabs.
14. **Investor Present mode** (minimal): the 6 chapters from `story.json`, manual stepping, Esc to exit and state restore.
15. **Sources & method drawer** (section 6.7), holding every verbatim provenance, footer and note.
16. **Deep links and sharing:** hash state, `window.__ATLAS_INIT__` boot, Copy link with a fallback popover. **Wrappers:** full-bleed layout, iframe height 820, `st.query_params` injection, investor password gate (section 15).
17. **One number, one source:**
    - canonical SAM kW (see the open questions): 143.6 MW everywhere, and the Universe 144 MW stays consistent;
    - the Hydro chip renamed "Stranded capacity shown";
    - investor "105 priced of 129" consistent between the KPI and the legend;
    - en-GB formatting everywhere.
18. **QA hooks:** `window.__atlasReady`, and `window.atlas = {setView, select, search, toggle, preset, setTheme, present}`.

### P1: should (next)

1. "In view" live KPIs: recount over `map.getBounds()` on `moveend`.
2. Client **annotations** (D1), computed from data at runtime with collision scoring (section 16.3).
3. Client **"Sites near my postcode"** via postcodes.io: fly there, show a radius ring, list the 5 nearest sites with indicative tiers. Fails gracefully offline.
4. **Download CSV:** the client-safe register and the visible sites. Investor CSV carries a confidentiality header row.
5. **Download map image (PNG):**
   - a 1600×900 @2x composite of the map canvas, title, legend strip, KPIs, and a sources / as-of footer (investor adds "Confidential — investor use only");
   - capture with `map.once('render')` plus `triggerRepaint()`, not `preserveDrawingBuffer`;
   - download via `<a download>`, falling back to opening a new window.
6. Cross-links: register row → map; card → register (P0 for "See in register"); counterparty bar → filter and "Show on map".
7. Detail sheet **Nearby** (3 nearest) and **step-through** (`‹ n of N ›`, J/K). Order: client by tier then kW; investor by TCV.
8. Night-only TAM density glow heatmap (section 5.4).
9. Investor **Present** autoplay (9 s) and **3D Highlands terrain** (chapter 4, plus a `3D` control in Hydro).
10. Investor **Colour by** switch: SAM `BM tier | Export arrangement`; Hydro `Confidence | Export class`.
11. Accessible **Sites list** view (`role="table"`) of the visible sites, sortable.
12. `?` shortcuts dialog. "About this map" popover. Glossary tooltips on BM, REGO, MEC, FiT/RO, TCV.
13. Mobile bottom-sheet drag gesture with snap points.
14. Investor TAM card: per-site indicative TCV potential with method ⓘ.
15. CI: `python atlas/build.py --check` on PRs touching `atlas/`, plus a palette validation step.

### P2: stretch

1. "What could my site earn?" illustrative estimator (client), pending owner sign-off.
2. Investor scenario sliders: BTC price and a treasury toggle rescale TCV exactly (the model is linear). Pending confirmation of the implied BTC prices.
3. CPI slider on the PPA chart, which moves the FiT +CPI path and a live crossover sentence. The verbatim callout stays at 3%.
4. Compare tray (pin up to 3 sites) and investor deal basket or shortlist with running totals and CSV.
5. Lasso or box select summing MW, TCV and BTC.
6. Region lens: GSP-group chips and regional summary.
7. TAM hex-bin density at z < 6, handing over to glyphs.
8. "Detailed fuel colours" toggle (9-hue mode for zoomed-in use).
9. Client story or fly-through mode.
10. Print stylesheet and a one-page site tear sheet.
11. 3-step first-visit tour.
12. Context layers: GSP / DNO boundaries, constraint zones.
13. A Felt companion map (section 17).

---

## 12. MUST-preserve checklist

The build's `copy_check` greps the output HTML for every quoted string below, after whitespace normalisation. Lift copy from the v1 HTML (the source of truth) with `atlas/tools/extract_v1.py`; the text here is the checklist.

### 12.1 Client Atlas

1. A single self-contained page, with three modes.
   - Tab labels: `Peaker Model` (default, scope SAM), `Hydro · 57`, `PPA Benchmark`. PPA is visually set apart at the end of the tab group.
   - Scope labels: `TAM · 1,309` and `SAM · 129`, shown only in Peaker mode. SAM is the default.
2. Brand: header `#0B2E2A`, lime `#8FD14F`, tagline `no Watt wasted` (capital W, never uppercased).
3. The Capacity shown KPI is a live sum. The Universe strings are verbatim: `57 sites · 15.2 MW stranded`, `129 sites · 144 MW`, `1,309 sites · 3,612 MW`.
4. SAM:
   - colour = BM tier 1–5 (the new validated ramp); size = installed capacity, with proportional-by-capacity semantics;
   - legend title `BM Tier — projected p/kWh (next 12m)`;
   - rows `29.6p avg · 122p top 5%`, `25.3p avg · 104p top 5%`, `21.7p avg · 80p top 5%`, `18.0p avg · 61p top 5%`, `16.0p avg · 50p top 5%`.
5. SAM card fields:
   - name (the site before the first comma, else the operator when the site is "DATA NOT AVAILABLE");
   - `Installed`, `Onsite demand / Stranded`, `Available for BM` (kW; *Unknown* when null);
   - `Offtaker` (cleaned; `Sole holder · unbundled`; `Not identified`);
   - `Export` (`Negotiated PPA` / `FiT standard` / `Behind meter` / `Unknown`);
   - Tier;
   - `Projected Balancing Mechanism Revenues`, `Average`, `Top 5%`;
   - `Offer-event frequency: ~2× GB average` (T1) and `~1.5×` (T2) only.
   - Constants: `BMREV = {1:{a:'29.6',t:'122'},2:{a:'25.3',t:'104'},3:{a:'21.7',t:'80'},4:{a:'18.0',t:'61'},5:{a:'16.0',t:'50'}}`.
6. TAM:
   - encodings: ring colour = technology (family colour, exact fuel named everywhere else), triangle = RO, circle = FiT, dashed = approximate location;
   - legend `RO accredited 945`, `FiT accredited 364`;
   - the 9 technology rows with sites and MW (section 6.3);
   - indicative BM tier `78 / 294 / 342 / 455 / 57` and `Scotland · no BM revenue 83`.
7. TAM card:
   - name, fuel;
   - `Capacity` kW (or `—`);
   - `Available for BM` kW (or *Unknown*);
   - `Site aggregates N MPAN records`;
   - `BM tier: Tier N · Label (indicative)`;
   - `Subsidy: RO accredited|FiT accredited`;
   - the RO code;
   - `Approximate location (postcode district)`.
8. Hydro:
   - size = stranded kW; colour = confidence (now also stated in words);
   - card: `No export`, or `Installed capacity` plus `Export capacity` kW; `N kW stranded`.
9. Search and size filter:
   - `All sizes / Over 1 MW / Under 1 MW` (> 1000 and ≤ 1000 kW);
   - a sites-shown count;
   - zoom to results.
10. Default framing intent: Peaker centred on England; Hydro emphasising the Highlands. Clipping is fixed (section 5.7).
11. PPA. Everything in sections 8.1–8.4, including:
    - the intro sentence "No contracted PPA price is shown anywhere — those are private bilateral contracts and are not obtainable from any source.";
    - the tiles `8.52` (`Elexon MID, Aug 25 – Jul 26`), `12.50` (`+47% vs last 12 months`), `7.74` (`below the CPI-linked FiT tariff`), `7.64` (`statutory, CPI-linked, guaranteed`), `49`% (`Win-26 vs Sum-27 — AD runs flat`);
    - the chart content and verbatim tooltips;
    - the crossover callout;
    - the filters, counterparty chart and caption, the 11-column register and captions, and the provenance.
12. Client-safety contract (section 13).
13. Attribution: OSM (OpenFreeMap / OpenMapTiles) contributors plus `postcodes.io`.
14. Wrapper: re-reads `client_atlas.html` on every run; `st.iframe` at 820 px; page title `RenewaBlox Client Atlas`; contact `RenewaBlox · contact callum@renewablox.com` (now a mailto link).

### 12.2 Investor Atlas

1. Title `RenewaBlox Investor Atlas`; deep-teal header gradient `#16323A → #1F6F78`; `st.iframe` height 820; caption `RenewaBlox · Investor Atlas · contact callum@renewablox.com`.
2. Modes `Peaker plants` (TAM/SAM scope, SAM default, scope only in Peaker mode), `Hydro`, `PPA Benchmark`. Scope labels `TAM · 1,309` / `SAM · 129`.
3. The KPI labels, values and formulas in section 10.1, the `abbr` / `gbp0` semantics, and the tier names and uplifts `+270% +216% +171% +125% +100%` with counts `4 / 41 / 41 / 37 / 6`.
4. 24 unpriced SAM sites shown distinctly, with `Awaiting BM figure`.
5. Size ∝ √TCV for SAM and Hydro; ∝ capacity (banded) for TAM. The TAM encodings are as for the client. Scotland = no BM revenue.
6. Click-to-toggle filtering on: SAM tiers, Hydro export class, TAM subsidy, TAM technology, TAM BM tier. Hidden state persists across tabs.
7. Card fields as in section 6.4 (investor), including:
   - `BTC mined (Yr 5)`, `TCV · no treasury`, `TCV · treasury`, `Operator`, `Offtaker`, `Export`;
   - hydro `Energy export £0 · 100% mining` and `{conf} confidence`;
   - TAM `Approx · postcode district` / `Exact · DNO register` and `In SAM · Verified site`.
8. **Legend notes, verbatim:**
   - **SAM:** "+% = average BM revenue per tier vs a wholesale market baseline. TCV is per kW of available-for-BM; 24 sites (grey) await a figure. Popup offtaker is inferred from the largest external REGO certificate holder — strong evidence of who buys the power, not contractual proof. Full detail on the PPA Benchmark tab."
     - Allowed edits: "(grey)" becomes "(hollow)", and "Popup" becomes "Card".
   - **TAM:** "Markers are unfilled: ring colour = technology, shape = subsidy (triangle = RO, circle = FiT), size = capacity, dashed = approximate location. BM tier is indicative, modelled from the verified SAM sites. TCV Potential applies the priced SAM sites’ own Year-5 TCV per kW-available (by tier) to each site’s available-for-BM capacity — the DNO maximum export capacity where the register gives one (727 sites), otherwise installed capacity at the SAM fleet’s ratio. Scotland sits outside the modelled tiers, so it carries no BM revenue and is excluded from TCV Potential."
   - **Hydro:** "Stranded generation runs Bitcoin mining 24/7 — no grid export and no BM revenue, so TCV = mined BTC value."
9. **Footers, verbatim** (section 10.1 footer bar and the drawer):
   - **SAM / Hydro:** "RenewaBlox Investor Atlas · Year-5 Total Contract Values modelled from the Scrivelsby peaker and 1,000 kW stranded-hydro client cases, scaled across the portfolio. Sources: RenewaBlox_AD_BM_CRM & RenewaBlox_Hydro_Stranded (16 Jun 2026). Indicative; not investment advice."
   - **TAM:** "RenewaBlox Investor Atlas · TAM — every subsidised biogas, biomass, EfW, landfill and sewage-gas CHP holding an RO or FiT accreditation. Sources: DNO Embedded Capacity Registers (NGED, NPG, SPEN, SSEN Jul-2026, UKPN) + Ofgem FiT, RO and REGO registers (Aug-2026). Co-located records are collapsed to one marker per site with capacity capped at the DNO connection figure (194 MW of double-counting removed across 87 sites); 8 transmission-connected thermal stations >100 MW are excluded. 220 sites are plotted at postcode-district centroid (dashed). BM tier is indicative, modelled from the 129 verified SAM sites; Scotland sits outside the modelled tiers."
   - **PPA:** "RenewaBlox Investor Atlas · PPA & Price Benchmark — Elexon BMRS Market Index (APXMIDP) settlement data, Montel/EEX forward curve snapshot 11 Aug 2026, Ofgem Feed-in Tariff and REGO registers. Contracted PPA prices are private bilateral terms and are not shown anywhere; the counterparty is inferred from REGO certificate holdings."
10. **Subtitles, verbatim:** the SAM, TAM and Hydro strings in section 6.3(a), plus PPA "PPA & price benchmark · 129 SAM sites · applies across peakers and hydro" (shown as the PPA page standfirst above the intro).
11. PPA: identical to the client, except that the investor keeps `#` rank and the raw status labels. The PPA chips appear in the KPI band.
12. Investor-only fields (`tcv`, `tcvT`, `btc`, `en`, `av`, `dev`, TCV Potential and the rates) exist only in this build.
13. The map re-frames and resizes correctly on each view entry and after leaving PPA (section 5.7).

---

## 13. Client-safety rules (enforced by `build.py`; the build fails on any violation)

### 13.1 Client data allowlist (a tightened subset of v1's)

**SAM** ships only these fields:
- `key` (from the postcode);
- `name` (derived);
- `site` (the full address string, used only for search; it was already public in v1);
- `town`, `la` (local_authority), `pc` (postcode), `op` (operator);
- `t` (tier);
- `kw`, `kwOn`, `kwBm` (the canonical split);
- `comm` (commissioned year);
- `lat`, `lon`;
- register fields: `ppa` (class code), `off` (cleaned offtaker, or a sole-holder or none flag), `self` (bool), `fitGen`, `fitEnd`, `yrsLeft`, `rego` (softened status code);
- `ref` (the neutral register order, derived as tier ascending then kW descending, with ties broken by name; **not** the v1 `rank` value, which never ships). This order is fully derivable from public fields, so it discloses nothing.

**Hydro:** `key, name, exp, conf, kw, inst, mec, lat, lon`.

**TAM:** `key, n, f, kw, bm, p, bt, ro, units, sam, lat, lon` (`sam` is a boolean or a SAM key).

**PPA:** `realised[{m,p}]`, `kpi{base12,win26,cal28,fit,asOf}`, `fwd[{k,from,to,p}]`, `spread{value,note}`, `fit`, `cpi`.

### 13.2 Never in the client HTML

These must not appear in data keys, strings, code or comments:
- investor fields `tcv`, `tcvT`, `btc`, `en`, `av`, `dev`, the investor short keys (`t` is allowed only as the tier key in the SAM source), and `TCVRATE`, `AVRATIO`, `WHOLESALE`, `tcvPot`;
- the words "TCV", "Bitcoin", "BTC", "treasury", "TCV Potential";
- `rank` (as a key), `archetype`, `accred_ref`, `supplier_1`, `supplier_2`, `supplier_1_certs`, `n_external`, `bm_tier`, `yrs_old`, `website`, `gsp`/`gspc`, SAM `units`, TAM `s` / `src`;
- "score", "internal", "RenewaBlox CRM", `RenewaBlox_AD_BM_CRM`, `RenewaBlox_Hydro_Stranded`, "Scrivelsby peaker", "Modo", the methodology anchors (`17p`, `70p`, `×1.20` / `x1.20`, `1.45`…`0.79` multipliers);
- raw status labels "likely ceased" and "lagging/winding down".

**Mechanism**
1. **Structural:** client data JSON keys must be ⊆ the allowlist. Any extra key fails the build.
2. **Textual:** case-insensitive regexes over the **entire** output `client_atlas.html`, with word boundaries for short tokens (`\btcvT?\b`, `\bbtc\b`, `\bbitcoin\b`, `\btreasury\b`, `\bdev\b"?:`, `"rank"\s*:`, …).
   - Note: `en-GB` and `lang="en"` are legitimate. The `en` check is structural (JSON keys only), not textual.
   - "Scrivelsby" alone is allowed, because it is a real SAM site name. Only "Scrivelsby peaker" is denied.
3. **Code partition:** investor-only JS and CSS live under `atlas/apps/investor/` and `atlas/core/js/investor/`. The client manifest can never include them, and the build asserts that no path under `investor/` is in the client bundle.
4. **Comments:** the output must contain no methodology comments.
   - The build strips CSS `/* … */` comments. It does **not** regex-strip JS, because that is unsafe around strings and regex literals.
   - The rule instead: source comments must never contain methodology, model parameters or internal names.
   - The textual scan (2) over the final HTML, comments included, is the gate. The `/*__ATLAS_INIT__*/` marker is whitelisted.
5. **The investor build** must contain `Confidential` in its export templates (P1), and must never write commercial values to URLs.

### 13.3 Public copy rules

- Offtaker is always tagged *inferred*.
- REGO statuses are softened (section 8.4).
- No "rank" or "target" language anywhere; the register column is "Ref".

---

## 14. Source architecture and build

### 14.1 Tree (new; nothing outside `atlas/` changes except the two output HTML files and the two wrappers)

```
atlas/
  build.py                    # python3 atlas/build.py [--check] [--only client|investor] [--qa]
  README.md                   # how to edit, rebuild, QA; data refresh steps
  tools/
    extract_v1.py             # one-off: parse v1 HTML consts → data/*.json (migration; kept for audit)
    validate_palettes.sh      # runs the dataviz validator on tokens (section 3.4)
  core/
    basemap/ne_pack.js  basemap.js            # copied unmodified from the kit
    css/ tokens.css base.css header.css rail.css legend.css kpi.css sheet.css palette.css
         controls.css drawer.css ppa.css mobile.css present.css
    js/  util.js (fmt en-GB, abbr, gbp0, esc, displayCase, cleanName, debounce, rafThrottle, store(try/catch),
                  copyText(fallback), download(fallback), haversine)
         state.js (store, pub/sub, hash + __ATLAS_INIT__ + localStorage (de)serialisation)
         theme.js (palettes 'paper'/'night', applyTheme, data paint re-apply)
         data.js  (decode compact columnar → rows + GeoJSON; derived props sv/sk/band/fam)
         map.js   (init, fit padding, camera memory, ResizeObserver, __atlasReady)
         layers.js (R(), layer factories §5.3–5.5, filters §5.6, picking, hover, tooltip, selection/pulse)
         icons.js (TAM styleimagemissing generator)
         filters.js (predicate + expressions + faceted counts)
         header.js rail.js legend.js histogram.js kpi.js sizekey.js
         search.js (index, scorer, palette UI)
         sheet.js (card shell, section registry: cards register section renderers by kind)
         cards.js (client-safe sections: SAM/TAM/Hydro common)
         ppa.js   (tiles, price chart, callout, filters, counterparty chart, register, data tables)
         drawer.js toasts.js shortcuts.js a11y.js mobile.js
         annotations.js (P1, client) export.js (P1) sites_list.js (P1)
         investor/  kpiband.js commercials.js tcvpot.js story.js present.css.js   # investor-only
         app.js   (bootstrap: RBX.boot(ATLAS_CONFIG, ATLAS_DATA))
  apps/
    client/   template.html  manifest.json  config.json (copy strings, views, headlines, annotations)
    investor/ template.html  manifest.json  config.json  story.json
  data/
    shared/   tam.json  ppa_prices.json          # client-safe; used by both (must pass the client scan)
    client/   sam.json  hydro.json  ppa_register.json
    investor/ sam.json  hydro.json  ppa_register.json  model.json   # model: TAVG, WHOLESALE, as-of stamps
  qa/        shots.mjs (matrix runner around scratch qa/shoot_ca.js) axe.mjs (P1)
  tests/     test_build.py (asserts, allowlist, copy check, size budget)
```

### 14.2 JavaScript conventions

- Vanilla ES2019, with no modules and no frameworks at runtime.
- Each file is an IIFE that attaches to `window.RBX`, concatenated in manifest order.
- There is exactly **one global** `RBX`, plus `window.atlas` (the QA API) and `window.__atlasReady`.
- Data arrives as `window.ATLAS_DATA` and config as `window.ATLAS_CONFIG`. The wrapper-injection marker is `/*__ATLAS_INIT__*/`.
- `innerHTML` is only used with `esc()`-escaped values. `esc` escapes `& < > " '`.

### 14.3 Template placeholders

```html
<!doctype html><html lang="en-GB" data-theme="{{DEFAULT_THEME}}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{{TITLE}}</title><link rel="icon" href="{{FAVICON_DATA_URI}}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{{FONTS_URL}}" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<style>{{CSS}}</style></head><body>
{{BODY}}  <!-- shell markup from template -->
<script>/*__ATLAS_INIT__*/</script>
<script>window.ATLAS_CONFIG={{CONFIG}};window.ATLAS_DATA={{DATA}};</script>
<script>{{NE_PACK}}</script><script>{{BASEMAP}}</script>
<script src="https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>{{JS}}</script></body></html>
```

**Robustness** (fixes v1's single point of failure). If `window.maplibregl` is undefined because the CDN is blocked:
- the app still boots the header, PPA page, search and drawer;
- the map area shows a calm fallback panel: "The interactive map couldn't load on this network. The PPA Benchmark and site search still work.";
- search results then open cards without flying.

Every module guards map calls with `if (RBX.map)`.

### 14.4 Data derivation (`build.py`)

**1. Canonical SAM capacity.** `kw = installed_kw` from the FiT register (the 998 kW default for Rotherdale Farm and Scrivelsby; see the open questions). `kwOn` and `kwBm` come from PKD. If `kwOn + kwBm < kw`, the card draws the "not yet split" remainder.

Result: map, register and KPI all show **143.6 MW**, and the Universe string "144 MW" is consistent (143.6 rounds to 144).

**2. Stable keys**

| Layer | Key |
|---|---|
| SAM | compact postcode, e.g. `KT160EF` (all 129 are unique; asserted) |
| Hydro | `h-` + slug(name) (asserted unique) |
| TAM | the RO code when present, else `t` + slug(name) + `-` + a 3-char geohash suffix |

**3. Joins**
- PKD → SAM by v1 rank. This is done at build time only; rank is then dropped for the client.
- Investor PEAKER → client register by normalised postcode (129/129 asserted).
- Investor HYDRO → HYX installed/export by name plus coordinates (57/57 asserted).

**4. Derived fields:** `sv`, `sk`, `fam`, `band`, `ref`, cleaned and display-cased names, and softened status codes (client).

**5. Compact serialisation:** columnar arrays with dictionary-encoded strings (fuels, towns, operators). **Budget:** the data payload is ≤ 170 KB per app, and each total HTML is ≤ 1.2 MB (target about 650 KB).

**6. Outputs:** write `../client_atlas.html` and `../investor_atlas.html` (UTF-8, LF), then print their sizes. `--check` rebuilds in a temporary directory and fails if the output differs from the committed HTML (for CI).

**7. Asserts, the copy check and the client-safety scan** (appendix A and sections 12–13) run on every build.

---

## 15. Streamlit wrappers

### 15.1 `app_client_atlas.py`

- Keep the "read on every run" contract.
- Add `initial_sidebar_state="collapsed"`.
- Remove `st.title` and the pre-iframe caption from the main area, so the iframe sits above the fold. The HTML header carries the brand.
- Update the sidebar copy to describe Peaker (SAM/TAM), Hydro and PPA Benchmark.

```python
import json, re
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="RenewaBlox Client Atlas", page_icon=":material/map:",
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>.block-container{padding-top:.75rem;padding-bottom:0;max-width:100%}</style>",
            unsafe_allow_html=True)

HTML = (Path(__file__).resolve().parent / "client_atlas.html").read_text(encoding="utf-8")

ALLOWED = {"view": r"^(sam|tam|hydro|ppa)$", "site": r"^[A-Za-z0-9-]{1,48}$", "theme": r"^(paper|night)$"}
init = {k: v for k, v in st.query_params.items() if k in ALLOWED and re.fullmatch(ALLOWED[k], str(v))}
try:
    init["publicUrl"] = st.secrets.get("ATLAS_PUBLIC_URL", "")
except Exception:
    init["publicUrl"] = ""
HTML = HTML.replace("/*__ATLAS_INIT__*/",
                    "window.__ATLAS_INIT__=" + json.dumps(init).replace("</", "<\\/") + ";", 1)

# sidebar (collapsed): title, one-line description per mode, "Base map © OpenStreetMap contributors · OpenFreeMap · geocoding postcodes.io."
st.iframe(HTML, height=820)
st.markdown("RenewaBlox · contact [callum@renewablox.com](mailto:callum@renewablox.com)")
```

### 15.2 `app_investor_atlas.py`

Same pattern as the client, plus:
- a **password gate** (defence in depth on top of the Streamlit Cloud viewer allowlist);
- `ALLOWED` extended with `present` (`^1$`).

```python
import hmac
def _gate():
    try:
        secret = st.secrets.get("INVESTOR_ATLAS_PASSWORD", "")
    except Exception:
        secret = ""
    if not secret:                       # fail closed (see open questions)
        st.error("Investor Atlas is locked. Set INVESTOR_ATLAS_PASSWORD in Streamlit secrets.")
        st.stop()
    if st.session_state.get("_atlas_ok"):
        return
    with st.form("atlas_gate"):
        code = st.text_input("Access code", type="password")
        go = st.form_submit_button("Enter")
    if go and hmac.compare_digest(code, secret):
        st.session_state["_atlas_ok"] = True
        st.rerun()
    elif go:
        st.error("That code isn't right.")
    st.stop()
_gate()
# … then the same read / inject / st.iframe(HTML, height=820) / caption
#     "RenewaBlox · Investor Atlas · contact [callum@renewablox.com](mailto:callum@renewablox.com)"
```

Keep the docstrings accurate: MapLibre, not Leaflet; gated; built by `atlas/build.py`. Add `ATLAS_PUBLIC_URL` and `INVESTOR_ATLAS_PASSWORD` to `.env.example` / README as documentation only.

---

## 16. QA and acceptance

### 16.1 Harness

Use `scratchpad/qa/shoot_ca.js`. **Do not use `shoot.js`**: its Chromium distrusts the proxy CA, so fonts and hillshade are missing. Run shots **sequentially**, because parallel SwiftShader runs starve `idle`.

**Screenshot matrix**

| Dimension | Values |
|---|---|
| App | client, investor |
| Theme | paper, night |
| View | sam, tam, hydro, ppa |
| Viewport | 1440×820, 1060×820, 390×844 @2x |

**Plus these states:**
- card open (all three kinds);
- palette open with the query "farm", and with "kt160ef";
- filters: Tier 1+2 only, and Over 1 MW;
- legend hover preview;
- the co-located stack chooser;
- PPA tooltip, data table open, and sort by `Yrs left`;
- investor Present chapters 1, 3 and 4.

Every screenshot must be **looked at**.

### 16.2 Acceptance criteria (P0)

**Runtime**
- `window.__atlasReady === true` in every run.
- No console errors other than blocked tile or glyph hosts in the container.

**Correctness**
- `build.py` passes the number asserts (appendix A), the copy check (section 12), the client-safety scan (section 13), and the size budget.
- The v1 S1 defects are verified fixed: the PPA chart lines, bars and tooltip render; the TAM legend title has a real "·"; the mobile header never overlaps controls, and PPA is reachable in one tap.

**Layout**
- No horizontal page scroll at 390 px.
- The 1060 px header fits on one row.
- The rail content at 780 px tall is reachable with a single internal scroll, with no clipped controls.

**Accessibility**
- Tab order: skip link → header → rail → map → sheet.
- Every control is operable by keyboard, with visible focus.
- Legend buttons expose `aria-pressed`.
- Chart text is ≥ 11 px at 390 px.
- P1: axe-core finds 0 serious or critical violations.

**Performance**
- A TAM filter toggle takes ≤ 16 ms of JS (measured over 20 toggles).
- Hover picking takes ≤ 4 ms per frame.
- First idle is ≤ 3 s in the harness, not counting fonts and tiles.

### 16.3 Client annotations (P1)

**Definition.** Each view defines 2–4 notes in `config.json` as `{id, anchor: expr | [lon,lat], ring?: {center, radiusKm}, lead, text(data) → string, placements: [[dx,dy], …]}`. **All text is computed at runtime from data.**

| View | Notes |
|---|---|
| SAM | "All four Tier 1 sites sit in the London–Kent corner…" (dashed ring around the T1 centroid); "Largest site: {name}, {town}: {MW}, Tier {t}." |
| TAM | "{n} sites and {MW} sit outside the BM tier model" (Scotland); the Thames Estuary note on the 3 of the 5 largest sites |
| Hydro | "{n} of the 57 sites, and {MW} of the {MW} stranded, are in the Highlands"; "Largest: {name}: {MW} that cannot reach the grid." |

**Rendering.** DOM text in Newsreader 14 / 1.3 with a 4-layer surface-colour halo; the lead-in in Inter 600 11 px caps; an SVG hairline leader in `--ink-2`.

**Placement.** Try each placement in turn. Reject a placement if it:
- intersects the rail, sheet or controls;
- has more than 3 rendered features under its box (via `queryRenderedFeatures`);
- collides with city labels.

Re-score on `idle`. The notes hide when the card is open, at z > 8.2, when the map is narrower than 900 px (unless the camera reserves a gutter), on mobile, or when toggled off with "✎ Notes".

---

## 17. Felt maps: decision

We evaluated embedding Felt, or using it as the renderer. **We do not use Felt at runtime**, for these reasons:
- **Single-file contract.** Both apps must be one self-contained HTML file with inlined data and no API keys. A Felt embed means hosting the data on Felt, plus an iframe inside Streamlit's iframe.
- **Client safety.** A public Felt share link exposes the underlying layer data. The investor data must never sit behind a shareable URL, and Felt adds no gating we control.
- **Resilience.** No offline fallback; the MapLibre and Natural Earth path renders even when tile hosts are blocked.
- **Design control.** Felt cannot give us the validated palettes, lazy TAM glyphs, legend-as-filter, the PPA module or Present mode.

The Felt *design language* (calm floating panels, command palette) is already absorbed through D2. **P2 option:** a Felt *companion* map for internal analysts. It would use the client-safe layers only, to curate annotations or explore data. It is never linked from the public or investor pages.

---

## 18. Open questions for the product owner (short)

1. **Data reconciliation.** Please confirm three things:
   - Are Rotherdale Farm and Scrivelsby 998 kW (the FiT register; default, giving SAM 143.6 MW everywhere) or 499 kW (the DNO split and investor `inst`)?
   - What does the asterisk in `H2-2027*` mean, for the chart footnote?
   - The implied BTC prices differ between peaker and hydro (£73.9k vs £77.2k; with treasury, £238.8k vs £201.5k). Is that intended? This blocks the P2 scenario slider.
2. **Public REGO labels.** OK to show "No recent certificates" / "Certificates declining" on the client page, instead of "likely ceased" / "lagging/winding down"? The investor keeps the raw labels.
3. **Investor gating.** OK to add a password gate via `st.secrets` that **fails closed** when unset, on top of the Streamlit Cloud viewer allowlist? Or should we use `st.login` (OIDC) instead?
4. **TAM colours.** OK to colour TAM by 3 technology families + Other on the map, for colour-blind legibility? All 9 fuels stay in the legend, cards and search.
5. **Public URLs for Copy link.** Confirm `ATLAS_PUBLIC_URL` for each app (e.g. `https://renewablox-client-atlas.streamlit.app/`). Also: do you want the P2 Felt companion map for internal use?

---

## Appendix A: canonical numbers (`build.py` asserts; recomputed from the v1 extracts)

### SAM
- 129 sites. Tiers T1–T5: 4 / 41 / 41 / 37 / 6. Largest site 5,936 kW.
- **Canonical installed:** Σ 143,571 kW = **143.6 MW** (the 998 kW default; PKD's Σ is 142,573).
- Available for BM: Σ 90,465 kW, known for 105 sites.
- The PKD vs PEAKER differences are only ranks 53 (Rotherdale) and 74 (Scrivelsby).

### Hydro
- 57 sites.
- Stranded Σ 15,153 kW (15.2 MW); installed Σ 36,227 kW; export Σ 21,075 kW; largest stranded 1,309 kW.
- Confidence: High 37 / Medium 8 / Low 4 / Unverified 8. Export class: Export 48 / No export 9.

### TAM
- 1,309 sites. kW Σ 3,611,922 ("3,612 MW"). RO 945 / FiT 364. Approximate 220. `bm` known for 727 sites (Σ 2,489.0 MW). `sam` = 129. Largest 99,800 kW.
- BM tier: 1: 78 · 2: 294 · 3: 342 · 4: 455 · 5: 57 · Scotland (0): 83. Scotland is 275 MW.
- Stacks (co-located sites): 12, 3, 2, 2, 2, 2, 2.

| Fuel | Sites | MW |
|---|---|---|
| Landfill gas | 435 | 961 |
| Fuelled (biomass/AD/EfW) | 262 | 877 |
| Biomass | 81 | 715 |
| Waste / EfW | 81 | 616 |
| Biogas (AD) | 294 | 234 |
| Sewage gas | 138 | 143 |
| Advanced fuel | 4 | 38 |
| Biofuel - other | 11 | 27 |
| Biodiesel | 3 | 1 |

### PPA
- `DATA.kpi = {base12:8.52, win26:12.5, cal28:7.74, fit:7.64, asOf:'2026-08-11'}`.
- 24 realised months, 2024-08 → 2026-07.
- Forward blocks: 12.601 / 12.391 / 8.605 / 8.25 / 7.744.
- `ppa_class`: 108 / 16 / 4 / 1.
- Offtaker null: 37.
- `rego_status`: active 64 · no REGO certs 40 · likely ceased 14 · lagging/winding down 11.

### Investor

| Measure | Value |
|---|---|
| Priced sites | 105 |
| Σav | 90,465 kW |
| Σbtc | 639.394 |
| Σtcv | £221,933,920 |
| ΣtcvT | £327,351,233 |
| Σen | £174,685,396 |
| max tcv | £9,267,581 |
| Hydro Σbtc | 176.813 |
| Hydro Σtcv | £13,644,961 |
| Hydro ΣtcvT | £35,624,972 |
| TCVRATE (T1–T5) | 2,671.41 / 2,544.82 / 2,438.84 / 2,329.91 / 2,271.03 |
| AVRATIO | 0.73392 |
| In BM tiers | 3,337.4 MW |
| TCV Potential | £7,165,922,831 ("£7.17bn") |
| from 76 sites ≥ 10 MW | £4,080,456,539 ("£4.08bn") |
| AD-scale (< 10 MW) | £3,085,466,292 ("£3.09bn") |

## Appendix B: evidence reviewed

- **Before (v1):** `scratchpad/before/{client,investor}_v1.png`.
- **D1:** `final_01…16`. **D2:** `final_*` (13). **D3:** `final_01…20`.
- **Palette check renders:**
  - `scratchpad/design/spec_tools/test_green_light.png` and `test_green_dark.png` (the chosen tier ramps drawn on the D3 prototype);
  - `spec_tools/oklch.js` (ramp generator);
  - `spec_tools/contrast.js` (text-token contrast).
- **Layer expressions.** `spec_tools/validate_layers.js` runs `@maplibre/maplibre-gl-style-spec` `validateStyleMin` over the section 5 layers (`sam-glow/ghost/core/hot`, `hydro-core`, `tam-heat/core/samdot`, `sel-sam`, `sel-tam`). Result: **0 errors**. Run it with `NODE_PATH=scratchpad/qa/node_modules node design/spec_tools/validate_layers.js`, and keep it in `atlas/tools/` as a regression check.
