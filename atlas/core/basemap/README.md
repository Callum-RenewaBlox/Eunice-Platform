# RenewaBlox basemap kit

A bespoke, resilient MapLibre GL JS 4.7.1 basemap for Great Britain and Ireland, built for the
Client Atlas and Investor Atlas. It contains no data about any site, so it is safe for both the public and the gated page.

* **National scale (z < 6.6) is self-contained.** Natural Earth 10m land, sea, bathymetry, lakes, rivers and
  UK nation borders come from an embedded TopoJSON pack. Hillshade comes from AWS terrarium tiles. City, region and sea
  labels are drawn onto a `<canvas>` with the page's own fonts, so they need no glyph server. QA screenshots
  therefore match what users see at the zooms the atlases open on. OpenFreeMap tiles are not requested below z6.6.
* **Zoomed in (z ≥ 6.6), OpenFreeMap vector detail cross-fades in.** This covers water, waterways, subtle landcover,
  hairline roads, admin boundaries and Noto Sans place labels, using OpenMapTiles source-layer names checked against
  the real OpenFreeMap *positron* style.
* **Graceful degradation.** If OpenFreeMap or its glyphs are unreachable (a corporate firewall, or this QA container), the
  vector layers and source are removed, the Natural Earth layers and canvas labels stay on at every zoom (with extra
  Natural Earth towns from z7.4), and `map.__rbxBasemapMode === 'offline'`. A TileJSON request that hangs
  goes offline after 6 s, so the map's `load` event is never blocked.

## Files

| file | size | what |
|---|---|---|
| `basemap.js` | 43 KB (13 KB gz) | `window.RBXBasemap`: plain ES5, no modules |
| `ne_pack.json` | 212 KB (68 KB gz) | Natural Earth TopoJSON pack (land, ocean, borders, bathy, lakes, rivers, places) |
| `ne_pack.js` | 212 KB | the same pack as `window.RBX_NE_PACK=…;`, ready to inline in a `<script>` |
| `demo.html` | 8 KB | demo: `?theme=dark`, `?view=gb/highlands/wales/london`, `?z=&lat=&lon=`, `?data=0`, `?focus=gbi` |
| `demo_points.json` | 29 KB | sample site coordinates for the demo only (client-safe: lon/lat/tier/tech index) |
| `validate.js` | | runs `@maplibre/maplibre-gl-style-spec` `validateStyleMin` on 5 style variants plus the runtime label layers. **0 errors** |
| `style_light.sample.json` | | the light style with GeoJSON data stripped, for inspection |
| `src/build_pack.sh` | | rebuilds `ne_pack.json` from Natural Earth 10m GeoJSON using mapshaper (the source files are in `src/`) |
| `qa_sim/shoot_sim.js` | | QA harness that emulates tiles.openfreemap.org with synthetic OpenMapTiles tiles, to test the online path and cross-fade |
| `shot_*.png` | | screenshots (see below) |

Total inline weight in an atlas page is about 255 KB (basemap.js plus pack), within the 1.2 MB page budget.

## Usage (single self-contained HTML)

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@1,8..60,400&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>:root{ --rbx-map-font: Inter, sans-serif; --rbx-map-serif: "Source Serif 4", Georgia, serif; }</style>
<script>/* paste ne_pack.js */ window.RBX_NE_PACK = {...};</script>
<script>/* paste basemap.js */</script>
<script>
  const map = new maplibregl.Map({
    container: 'map',
    style: RBXBasemap.style('light'),            // or 'dark'; opts below
    bounds: [[-10.9, 49.8], [2.1, 60.95]], fitBoundsOptions: { padding: 40 },
    minZoom: 3.8, maxZoom: 16, attributionControl: { compact: true }
  });
  const bm = RBXBasemap.attach(map, { onMode: m => console.log('basemap', m) });
  map.on('load', () => {
    map.addSource('sites', { type: 'geojson', data: SITES });
    // Data goes ABOVE the basemap and sea/region labels, BELOW city labels:
    map.addLayer({ id: 'sites', type: 'circle', source: 'sites', paint: { /* … */ } }, RBXBasemap.DATA_BEFORE);
  });
  // Live theme switch. There is no setStyle call, so your data layers are untouched:
  // RBXBasemap.applyTheme(map, 'dark');
</script>
```

### API
* `RBXBasemap.style(theme, opts)` returns a style object. `theme` is `'light'`, `'dark'` or a palette object. `opts`:
  `pack` (defaults to `window.RBX_NE_PACK`), `vectorZoom` (6.6), `focus` (`'uk'` veils Ireland and the continent,
  `'gbi'` veils only the continent), `terrain` (true), `vector` (true; false gives a pure Natural Earth basemap with no glyphs),
  `ofmUrl`, `glyphs`, `demUrl`.
* `RBXBasemap.attach(map, opts)` adds the canvas labels and failure detection, and returns `{ready, mode(), setTheme(t), destroy()}`.
  `opts`: `theme` (read from the style metadata when omitted), `labelFont`, `seaFont` (defaults to the CSS vars `--rbx-map-font` and `--rbx-map-serif`),
  `cities` (your own `[name, lon, lat, tier(0-5), side 'r'|'l'|'t'|'b', capital]` list),
  `cityLabels`, `regionLabels` and `seaLabels` (booleans), `packPlaces` (extra towns when offline), `onMode(mode, reason)`, `bootTimeoutMs` (6000), `timeoutMs` (9000).
  Call it right after `new maplibregl.Map()`; it waits for the style and fonts before drawing labels.
  It also fires `map.fire('rbx:basemapmode', {mode, reason})`.
* `RBXBasemap.applyTheme(map, theme)` re-paints every basemap layer and redraws the label images.
* `RBXBasemap.palettes`, `RBXBasemap.decode(topojson)`, `RBXBasemap.cities`, `RBXBasemap.attribution`, `RBXBasemap.DATA_BEFORE` (`'rbx-slot-labels'`).
* Mode flag: `map.__rbxBasemapMode` is `'online'` or `'offline'`; `map.__rbxBasemapOfflineReason` holds the reason. For a small
  "Offline basemap" pill, see `demo.html`.

## Design notes
* **Light**: warm "paper" land `#F2F0E9`, desaturated grey-teal sea, a soft light coast glow on the sea side, and
  a hairline coastline. Deep-water steps (200 / 1000 / 2000 m) show the continental-shelf edge, Rockall and the Norwegian Trench.
  Hillshade uses a deep-green shadow `#2F4640` lit from the NW; exaggeration falls from 0.72 at z4 to 0.22 at z14, so the Highlands read strongly
  without muddying data at street level. The data markers (deep green, lime, cyan) stay the most saturated things on the map.
* **Dark**: deep green-ink land `#16231F` on near-black teal sea, with a faint luminous teal coast glow. Luminous markers
  (lime, cyan) glow against it. The brand lime `#8FD14F` is deliberately **not** used anywhere in the basemap, so it stays free for data.
* **Context veil**: a fill of `landContext` drawn *above* the hillshade over the continent (72%) and Ireland (45%, focus `uk`). It
  pushes non-UK land and relief back, so Norway's fjords do not compete with the Highlands.
* The sea polygon is drawn above the hillshade, so the seabed relief in the DEM never shows. Vector water does the same once zoomed in.
* **Labels**: city labels have a dot and a halo and use Inter 500/600. Region labels (SCOTLAND, WALES…) are widely letter-spaced caps and sit *below* data.
  Sea labels are italic Source Serif. Cities use tiered layers (tier 1 from z3.5, tier 2 from z5.3, tier 3 from z6.2) with MapLibre collision; region and sea labels are placed after cities, so cities win.

## Palette tokens
| token | light | dark |
|---|---|---|
| `land` | `#F2F0E9` | `#16231F` |
| `landContext` | `#E7E6E0` | `#121C1A` |
| `veilNear` | `0.45` | `0.45` |
| `veilFar` | `0.72` | `0.72` |
| `sea` | `#D4E0E0` | `#0A1416` |
| `sea200` | `#CEDBDC` | `#091113` |
| `sea1000` | `#C9D7D9` | `#070E10` |
| `sea2000` | `#C4D3D6` | `#060B0D` |
| `coastGlow` | `#E7EEEB` | `#12302F` |
| `coastline` | `#A7BAB8` | `#2F4843` |
| `lake` | `#CFDCDB` | `#0C1618` |
| `river` | `#9DBCBF` | `#1F4D4E` |
| `riverWidth` | `1` | `1` |
| `border` | `#8E9C95` | `#4A5E57` |
| `borderIntl` | `#7F8E87` | `#556A62` |
| `wood` | `#E3E8DC` | `#16241F` |
| `grass` | `#EAEDE2` | `#172320` |
| `park` | `#E2E9DC` | `#172620` |
| `residential` | `#E9E6DE` | `#1A2522` |
| `ice` | `#F7F8F6` | `#1C2826` |
| `road` | `#FFFFFF` | `#2B3A36` |
| `roadMajor` | `#E4DCCB` | `#33443F` |
| `rail` | `#CFCAC0` | `#2A3834` |
| `hsShadow` | `#2F4640` | `#020605` |
| `hsHighlight` | `#FFFFFF` | `#5E7E75` |
| `hsAccent` | `#56675F` | `#0B1513` |
| `hsExaggeration` | `[4,0.72,6,0.56,8,0.4,11,0.3,14,0.22]` | `[4,0.75,6,0.62,8,0.48,11,0.36,14,0.26]` |
| `label` | `#46534D` | `#9FB2AA` |
| `labelMajor` | `#1F2F2A` | `#DCE7E1` |
| `labelHalo` | `rgba(242,240,233,0.92)` | `rgba(12,20,18,0.88)` |
| `dot` | `#1F2F2A` | `#DCE7E1` |
| `dotHalo` | `#F2F0E9` | `#0C1412` |
| `region` | `rgba(52,72,64,0.40)` | `rgba(170,196,186,0.30)` |
| `sea_label` | `#6F8E8E` | `#4C6C6C` |
| `waterLabel` | `#5E8487` | `#5C8A8A` |

## Layer stack (light style; `attach()` adds the label layers)
| id | type | source / source-layer | group | minzoom |
|---|---|---|---|---|
| `rbx-background` | background |  | base |  |
| `ofm-landcover-wood` | fill | rbx-ofm / landcover | ofm | 6.6 |
| `ofm-landcover-grass` | fill | rbx-ofm / landcover | ofm | 9 |
| `ofm-landcover-ice` | fill | rbx-ofm / landcover | ofm | 6.6 |
| `ofm-park` | fill | rbx-ofm / park | ofm | 8 |
| `ofm-residential` | fill | rbx-ofm / landuse | ofm | 8 |
| `rbx-hillshade` | hillshade | rbx-dem | dem |  |
| `rbx-land-context` | fill | rbx-land | ne |  |
| `rbx-sea` | fill | rbx-ocean | ne |  |
| `rbx-bathy` | fill | rbx-bathy | ne |  |
| `rbx-coast-glow` | line | rbx-coast | ne |  |
| `ofm-water` | fill | rbx-ofm / water | ofm | 6.6 |
| `rbx-lakes` | fill | rbx-lakes | ne |  |
| `rbx-coastline` | line | rbx-coast | ne |  |
| `rbx-lakes-line` | line | rbx-lakes | ne |  |
| `rbx-rivers` | line | rbx-rivers | ne |  |
| `ofm-waterway-river` | line | rbx-ofm / waterway | ofm | 6.6 |
| `ofm-waterway-stream` | line | rbx-ofm / waterway | ofm | 10.5 |
| `ofm-road-minor` | line | rbx-ofm / transportation | ofm | 11.5 |
| `ofm-road-secondary` | line | rbx-ofm / transportation | ofm | 9 |
| `ofm-road-primary` | line | rbx-ofm / transportation | ofm | 7.5 |
| `ofm-road-motorway` | line | rbx-ofm / transportation | ofm | 6.6 |
| `ofm-rail` | line | rbx-ofm / transportation | ofm | 10 |
| `ofm-boundary-4` | line | rbx-ofm / boundary | ofm | 6.6 |
| `ofm-boundary-2` | line | rbx-ofm / boundary | ofm | 6.6 |
| `rbx-borders` | line | rbx-borders | ne |  |
| `rbx-slot-annotations` | background |  | slot |  |
| `rbx-slot-labels` | background |  | slot |  |
| `ofm-label-water` | symbol | rbx-ofm / water_name | ofm | 8 |
| `ofm-label-waterway` | symbol | rbx-ofm / waterway | ofm | 11 |
| `ofm-label-village` | symbol | rbx-ofm / place | ofm | 10.5 |
| `ofm-label-town` | symbol | rbx-ofm / place | ofm | 8 |
| `ofm-label-city` | symbol | rbx-ofm / place | ofm | 6.6 |

Runtime layers added by `attach()`: `rbx-sea-labels-*` and `rbx-region-labels-*` (before `rbx-slot-annotations`), and `rbx-city-labels-<tier>`
(after `rbx-slot-labels`, before the OpenFreeMap text layers). Cross-fade: vector water fades in over z6.6–7.1. Natural Earth sea, lakes, rivers and coast
fade out over z6.8–7.5, after the vector water is opaque, so the hillshade never leaks through. The context veil fades out over z7.2–8.2. Canvas city labels hand over to
OpenFreeMap labels over z6.8–7.3. In offline mode every fade is pinned to its fully visible value.

## Screenshots
Taken with Chromium + SwiftShader. OpenFreeMap is blocked here, so the main shots show **offline mode**. That is identical to online mode below
z6.6; at z7.5 users would also get vector detail.
* Final: `shot_light_gb.png`, `shot_dark_gb.png` (1440×820), `shot_light_highlands.png`, `shot_dark_highlands.png` (z7.5),
  `shot_light_mobile.png`, `shot_dark_mobile.png` (390×844 @2x), `shot_theme_toggle_dark.png` (live `applyTheme` light→dark→light→dark).
* Refinement history: `shot_round1_light_gb.png` (busy bathymetry, heavy Norway relief, missing region labels) →
  `shot_round2_*` (context veil, smoother bathymetry, stronger GB relief; the dark labels had a theme bug) → final (softer sea steps, teal coast glow
  in dark, fixed label theme and positions, North Sea label pulled in for mobile).
* Simulated online (`qa_sim/shoot_sim.js`, with synthetic OpenMapTiles tiles and empty glyphs): `shot_sim_online_gb.png` (0 vector tiles requested at national
  zoom), `shot_sim_online_crossfade_z695.png`, `shot_sim_online_highlands.png`, `shot_sim_online_z9.png`. These confirm that the online path keeps
  `mode === 'online'`, that the vector layers render without errors, and that the cross-fade is seamless.

## QA harness note (important for anyone else screenshotting)
The shared `qa/shoot.js` launches Chromium, which does **not** trust the sandbox's TLS-inspection CA. Google Fonts,
`s3.amazonaws.com` terrarium tiles and `raw.githubusercontent.com` all fail there with `ERR_CERT_AUTHORITY_INVALID`, so pages render with fallback fonts
and no hillshade. `qa/shoot_ca.js` is a copy that adds `--ignore-certificate-errors-spki-list=<SPKI hashes of the Anthropic egress CAs from
/root/.ccr/ca-bundle.crt>`, which trusts only those CAs. It also accepts `--query "?theme=dark"`. Use it for faithful shots.

## Known risks / not verified offline
1. **OpenFreeMap rendering was not seen for real.** Tiles and glyphs are blocked here. Layer names, filters and classes were checked against
   the real positron style (`src/positron.json`) and the OpenMapTiles schema, and the style passes the spec validator. The online path ran against
   *synthetic* tiles only. Exact road widths and colours, label density and the look of landcover at z8–14 still need an eyeball check in a normal browser.
2. **Glyph-only failure is treated as offline.** MapLibre surfaces a glyph fetch failure as a tile error on the vector source, so the kit drops all
   vector layers rather than only the text. That is the safe choice, but less detailed.
3. **Terrarium CORS**: one run logged a single `s3.amazonaws.com` tile without an `Access-Control-Allow-Origin` header (probably a proxy or cache artefact).
   The tile is skipped and the map still renders. `opts.demUrl` can point at another terrarium host if needed.
4. **Streamlit `st.iframe(html)`**: pages run from a `srcdoc` / `null` origin. OpenFreeMap, jsDelivr, Google Fonts and S3 all send
   `Access-Control-Allow-Origin: *`, but this was not tested inside Streamlit here.
5. The Natural Earth coast (1:10m, simplified to about 180 m) looks good up to about z8. In offline mode beyond z9 it is visibly generalised.
   Natural Earth has few GB rivers and lakes (the Thames, Severn, Trent, Tweed, Tay, Ness, lochs Ness, Lomond, Awe, Maree and Rannoch, and so on).
6. Canvas label images are raster (drawn at 2× or more). They are crisp at 1× and 2× DPR, slightly soft at 3×, and do not rotate (the demo disables rotation).
7. The `vectorZoom` handover (6.6) is tuned for the atlases' default views. Lower it for more OpenStreetMap detail earlier, at the cost of QA fidelity.

## Attribution (must be visible; these strings are already on the sources and shown by MapLibre's AttributionControl)
* `© OpenStreetMap contributors`, linked to https://www.openstreetmap.org/copyright (map data, via OpenFreeMap)
* `OpenFreeMap`, linked to https://openfreemap.org (vector tiles)
* `Natural Earth`, linked to https://www.naturalearthdata.com (public domain; credit appreciated)
* `Terrain: Mapzen / AWS Terrain Tiles`, linked to https://registry.opendata.aws/terrain-tiles/ (terrarium DEM; the underlying sources include
  SRTM, GMTED2010, ETOPO1, NRCan CDEM, EU-DEM (© EEA / Copernicus), the Great Lakes bathymetry and others. The full list is at
  https://github.com/tilezen/joerd/blob/master/docs/attribution.md)
