/*!
 * RenewaBlox basemap kit  (window.RBXBasemap)
 * A bespoke, resilient MapLibre GL (4.x) basemap for Great Britain & Ireland.
 *
 *  - National scale (z < ~6.6) is fully self-contained: Natural Earth 10m land/sea/bathymetry/
 *    lakes/rivers/borders from an embedded TopoJSON pack (ne_pack.json), plus AWS terrarium
 *    hillshade, plus glyph-free city / region / sea labels rasterised with the page's own fonts.
 *  - Zoomed in, OpenFreeMap vector tiles (OpenMapTiles schema) cross-fade in for water,
 *    waterways, landcover, roads, boundaries and place labels.
 *  - If OpenFreeMap / its glyphs are unreachable (corporate firewall, offline), the kit degrades
 *    gracefully: NE layers + canvas labels stay on at all zooms; map.__rbxBasemapMode = 'offline'.
 *
 *  API
 *    RBXBasemap.style(theme, opts)   -> MapLibre style object   (theme: 'light' | 'dark')
 *    RBXBasemap.attach(map, opts)    -> controller {setTheme(t), mode(), destroy()}
 *    RBXBasemap.applyTheme(map, t)   -> live re-theme without setStyle (keeps your data layers)
 *    RBXBasemap.palettes             -> {light:{...tokens}, dark:{...tokens}}
 *    RBXBasemap.decode(topo)         -> {layerName: FeatureCollection}
 *    RBXBasemap.DATA_BEFORE          -> 'rbx-slot-labels'  (map.addLayer(yourLayer, RBXBasemap.DATA_BEFORE))
 *
 *  Attribution (added to the sources; MapLibre's AttributionControl shows it):
 *    Natural Earth · Terrain: Mapzen / AWS Terrain Tiles · OpenFreeMap © OpenStreetMap contributors
 */
(function () {
  'use strict';

  // ------------------------------------------------------------------------------------------
  // Palettes (design tokens). Brand: deep green #0E3A2F / #0b2e2a, lime #8FD14F (data only).
  // ------------------------------------------------------------------------------------------
  var palettes = {
    light: {
      name: 'light',
      land: '#F2F0E9',          // warm paper
      landContext: '#E7E6E0',   // continent / non-focus land (recedes)
      veilNear: 0.45,           // context-veil opacity over Ireland (focus 'uk')
      veilFar: 0.72,            // … over the continent
      sea: '#D4E0E0',           // muted grey-teal
      sea200: '#CEDBDC',        // deeper than 200 m (beyond the shelf edge)
      sea1000: '#C9D7D9',
      sea2000: '#C4D3D6',
      coastGlow: '#E7EEEB',     // soft light band hugging the coast (sea side)
      coastline: '#A7BAB8',
      lake: '#CFDCDB',
      river: '#9DBCBF',
      riverWidth: 1,
      border: '#8E9C95',
      borderIntl: '#7F8E87',
      wood: '#E3E8DC',
      grass: '#EAEDE2',
      park: '#E2E9DC',
      residential: '#E9E6DE',
      ice: '#F7F8F6',
      road: '#FFFFFF',
      roadMajor: '#E4DCCB',
      rail: '#CFCAC0',
      hsShadow: '#2F4640',
      hsHighlight: '#FFFFFF',
      hsAccent: '#56675F',
      hsExaggeration: [4, 0.72, 6, 0.56, 8, 0.40, 11, 0.30, 14, 0.22],
      label: '#46534D',
      labelMajor: '#1F2F2A',
      labelHalo: 'rgba(242,240,233,0.92)',
      dot: '#1F2F2A',
      dotHalo: '#F2F0E9',
      region: 'rgba(52,72,64,0.40)',
      sea_label: '#6F8E8E',
      waterLabel: '#5E8487'
    },
    dark: {
      name: 'dark',
      land: '#16231F',          // deep green-ink
      landContext: '#121C1A',
      veilNear: 0.45,
      veilFar: 0.72,
      sea: '#0A1416',
      sea200: '#091113',
      sea1000: '#070E10',
      sea2000: '#060B0D',
      coastGlow: '#12302F',
      coastline: '#2F4843',
      lake: '#0C1618',
      river: '#1F4D4E',
      riverWidth: 1,
      border: '#4A5E57',
      borderIntl: '#556A62',
      wood: '#16241F',
      grass: '#172320',
      park: '#172620',
      residential: '#1A2522',
      ice: '#1C2826',
      road: '#2B3A36',
      roadMajor: '#33443F',
      rail: '#2A3834',
      hsShadow: '#020605',
      hsHighlight: '#5E7E75',
      hsAccent: '#0B1513',
      hsExaggeration: [4, 0.75, 6, 0.62, 8, 0.48, 11, 0.36, 14, 0.26],
      label: '#9FB2AA',
      labelMajor: '#DCE7E1',
      labelHalo: 'rgba(12,20,18,0.88)',
      dot: '#DCE7E1',
      dotHalo: '#0C1412',
      region: 'rgba(170,196,186,0.30)',
      sea_label: '#4C6C6C',
      waterLabel: '#5C8A8A'
    }
  };

  var DEFAULTS = {
    vectorZoom: 6.6,                                   // OpenFreeMap detail fades in from here
    ofmUrl: 'https://tiles.openfreemap.org/planet',
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    demUrl: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
    terrain: true,
    vector: true,
    focus: 'uk'                                        // 'uk' dims IE + continent; 'gbi' dims continent only
  };

  var ATTR = {
    ne: '<a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener">Natural Earth</a>',
    dem: 'Terrain: <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">Mapzen / AWS Terrain Tiles</a>',
    ofm: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
  };

  var DATA_BEFORE = 'rbx-slot-labels';

  // ------------------------------------------------------------------------------------------
  // Tiny TopoJSON decoder (quantized, delta-encoded arcs; Polygon/MultiPolygon/Line/Point)
  // Normalises polygon winding to RFC 7946 (exterior CCW) so line-offset is predictable.
  // ------------------------------------------------------------------------------------------
  function decode(topo) {
    var tf = topo.transform, sx = 1, sy = 1, tx = 0, ty = 0;
    if (tf) { sx = tf.scale[0]; sy = tf.scale[1]; tx = tf.translate[0]; ty = tf.translate[1]; }
    var R = 1e5;
    function rnd(v) { return Math.round(v * R) / R; }
    var arcs = topo.arcs.map(function (arc) {
      var x = 0, y = 0;
      return arc.map(function (p) {
        if (tf) { x += p[0]; y += p[1]; return [rnd(x * sx + tx), rnd(y * sy + ty)]; }
        return [p[0], p[1]];
      });
    });
    function pt(p) { return tf ? [rnd(p[0] * sx + tx), rnd(p[1] * sy + ty)] : p; }
    function line(ids) {
      var out = [];
      for (var i = 0; i < ids.length; i++) {
        var id = ids[i], a = arcs[id < 0 ? ~id : id];
        var seg = id < 0 ? a.slice().reverse() : a;
        for (var j = out.length ? 1 : 0; j < seg.length; j++) out.push(seg[j]);
      }
      return out;
    }
    function area(r) { var s = 0; for (var i = 0, n = r.length - 1; i < n; i++) s += (r[i + 1][0] - r[i][0]) * (r[i + 1][1] + r[i][1]); return s; } // >0 => clockwise
    function ring(ids, outer) { var r = line(ids); var cw = area(r) > 0; if ((outer && cw) || (!outer && !cw)) r.reverse(); return r; }
    function poly(rs) { return rs.map(function (r, i) { return ring(r, i === 0); }); }
    function geom(g) {
      switch (g.type) {
        case 'Polygon': return { type: 'Polygon', coordinates: poly(g.arcs) };
        case 'MultiPolygon': return { type: 'MultiPolygon', coordinates: g.arcs.map(poly) };
        case 'LineString': return { type: 'LineString', coordinates: line(g.arcs) };
        case 'MultiLineString': return { type: 'MultiLineString', coordinates: g.arcs.map(line) };
        case 'Point': return { type: 'Point', coordinates: pt(g.coordinates) };
        case 'MultiPoint': return { type: 'MultiPoint', coordinates: g.coordinates.map(pt) };
        default: return null;
      }
    }
    var out = {};
    Object.keys(topo.objects).forEach(function (k) {
      var o = topo.objects[k], gs = o.type === 'GeometryCollection' ? o.geometries : [o];
      out[k] = { type: 'FeatureCollection', features: gs.filter(function (g) { return g.type; }).map(function (g) {
        return { type: 'Feature', properties: g.properties || {}, geometry: geom(g) };
      }) };
    });
    return out;
  }

  // Coastline = ocean rings minus the straight edges of the pack's clip rectangle.
  function coastFromOcean(oceanFC) {
    var xs = [], ys = [];
    oceanFC.features.forEach(function (f) { eachRing(f.geometry, function (r) { r.forEach(function (p) { xs.push(p[0]); ys.push(p[1]); }); }); });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys), e = 1e-3;
    function onEdge(a, b) {
      return (Math.abs(a[0] - x0) < e && Math.abs(b[0] - x0) < e) || (Math.abs(a[0] - x1) < e && Math.abs(b[0] - x1) < e) ||
             (Math.abs(a[1] - y0) < e && Math.abs(b[1] - y0) < e) || (Math.abs(a[1] - y1) < e && Math.abs(b[1] - y1) < e);
    }
    var lines = [];
    oceanFC.features.forEach(function (f) {
      eachRing(f.geometry, function (r) {
        var cur = [r[0]];
        for (var i = 1; i < r.length; i++) {
          if (onEdge(r[i - 1], r[i])) { if (cur.length > 1) lines.push(cur); cur = [r[i]]; }
          else cur.push(r[i]);
        }
        if (cur.length > 1) lines.push(cur);
      });
    });
    return { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'MultiLineString', coordinates: lines } }] };
  }
  function eachRing(g, fn) {
    if (!g) return;
    if (g.type === 'Polygon') g.coordinates.forEach(fn);
    else if (g.type === 'MultiPolygon') g.coordinates.forEach(function (p) { p.forEach(fn); });
  }

  var _packCache = null, _packSrc = null;
  function getPack(opts) {
    var src = (opts && opts.pack) || window.RBX_NE_PACK;
    if (!src) throw new Error('RBXBasemap: Natural Earth pack missing (pass opts.pack or set window.RBX_NE_PACK)');
    if (_packSrc === src && _packCache) return _packCache;
    var d = src.type === 'Topology' ? decode(src) : src;
    if (!d.coast && d.ocean) d.coast = coastFromOcean(d.ocean);
    _packSrc = src; _packCache = d;
    return d;
  }

  // ------------------------------------------------------------------------------------------
  // Expression helpers
  // ------------------------------------------------------------------------------------------
  function zi() { var a = ['interpolate', ['linear'], ['zoom']]; for (var i = 0; i < arguments.length; i++) a.push(arguments[i]); return a; }
  function ze() { var a = ['interpolate', ['exponential', 1.5], ['zoom']]; for (var i = 0; i < arguments.length; i++) a.push(arguments[i]); return a; }
  function fadeIn(z0, z1, v) { return zi(z0, 0, z1, v == null ? 1 : v); }
  function fadeOut(z0, z1, v) { return zi(z0, v == null ? 1 : v, z1, 0); }
  var isLine = ['match', ['geometry-type'], ['LineString', 'MultiLineString'], true, false];
  var isPoly = ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false];
  function cls(list) { return ['match', ['get', 'class'], list, true, false]; }
  var NAME = ['coalesce', ['get', 'name:en'], ['get', 'name_en'], ['get', 'name']];

  // ------------------------------------------------------------------------------------------
  // Layers (a pure function of palette + options, so the theme can be re-applied live)
  // metadata['rbx:offline'] = paint overrides applied when vector tiles are unreachable
  // metadata['rbx:group']   = 'ne' | 'ofm' | 'dem' | 'slot'
  // ------------------------------------------------------------------------------------------
  function buildLayers(p, o) {
    var V = o.vectorZoom, L = [];
    var vec = o.vector !== false;
    // NE layers hand over to vector tiles between V+0.5 and V+0.9 (after vector water is opaque)
    var neOut = vec ? fadeOut(V + 0.5, V + 0.9) : 1;
    function ne(layer, offline) { layer.metadata = { 'rbx:group': 'ne', 'rbx:offline': offline || {} }; L.push(layer); return layer; }
    function ofm(layer) { layer.source = 'rbx-ofm'; layer.metadata = { 'rbx:group': 'ofm' }; if (layer.minzoom == null) layer.minzoom = V; L.push(layer); return layer; }

    L.push({ id: 'rbx-background', type: 'background', paint: { 'background-color': p.land }, metadata: { 'rbx:group': 'base' } });


    if (vec) {
      ofm({ id: 'ofm-landcover-wood', type: 'fill', 'source-layer': 'landcover', filter: ['all', isPoly, cls(['wood', 'forest'])],
        paint: { 'fill-color': p.wood, 'fill-opacity': fadeIn(V + 0.4, V + 1.6, 0.9), 'fill-antialias': false } });
      ofm({ id: 'ofm-landcover-grass', type: 'fill', 'source-layer': 'landcover', minzoom: 9, filter: ['all', isPoly, cls(['grass', 'wetland', 'farmland'])],
        paint: { 'fill-color': p.grass, 'fill-opacity': fadeIn(9, 11, 0.6), 'fill-antialias': false } });
      ofm({ id: 'ofm-landcover-ice', type: 'fill', 'source-layer': 'landcover', filter: ['all', isPoly, cls(['ice', 'glacier'])],
        paint: { 'fill-color': p.ice, 'fill-opacity': 0.8 } });
      ofm({ id: 'ofm-park', type: 'fill', 'source-layer': 'park', minzoom: 8, filter: isPoly,
        paint: { 'fill-color': p.park, 'fill-opacity': fadeIn(8, 10, 0.7), 'fill-antialias': false } });
      ofm({ id: 'ofm-residential', type: 'fill', 'source-layer': 'landuse', minzoom: 8, filter: ['all', isPoly, cls(['residential', 'suburb', 'neighbourhood'])],
        paint: { 'fill-color': p.residential, 'fill-opacity': fadeIn(8, 10, 0.85), 'fill-antialias': false } });
    }

    if (o.terrain !== false) {
      L.push({ id: 'rbx-hillshade', type: 'hillshade', source: 'rbx-dem', metadata: { 'rbx:group': 'dem' },
        paint: {
          'hillshade-exaggeration': zi.apply(null, p.hsExaggeration),
          'hillshade-shadow-color': p.hsShadow,
          'hillshade-highlight-color': p.hsHighlight,
          'hillshade-accent-color': p.hsAccent,
          'hillshade-illumination-direction': 315,
          'hillshade-illumination-anchor': 'map'
        } });
    }

    // Context veil: sits ABOVE the hillshade, so it both tints and mutes relief outside the focus area.
    var ctxFilter = o.focus === 'gbi' ? ['==', ['get', 'c'], 'CTX'] : ['match', ['get', 'c'], ['CTX', 'IRL'], true, false];
    var veil = ['match', ['get', 'c'], 'IRL', p.veilNear, p.veilFar];
    ne({ id: 'rbx-land-context', type: 'fill', source: 'rbx-land', filter: ctxFilter,
      paint: { 'fill-color': p.landContext, 'fill-antialias': false,
        'fill-opacity': vec ? zi(V + 0.6, veil, V + 1.6, 0) : veil } },
      { 'fill-opacity': veil });

    // Sea (masks the hillshade's bathymetry), bathymetric steps, coast glow
    ne({ id: 'rbx-sea', type: 'fill', source: 'rbx-ocean', paint: { 'fill-color': p.sea, 'fill-opacity': neOut, 'fill-antialias': false } }, { 'fill-opacity': 1 });
    ne({ id: 'rbx-bathy', type: 'fill', source: 'rbx-bathy',
      paint: { 'fill-color': ['match', ['get', 'd'], 200, p.sea200, 1000, p.sea1000, 2000, p.sea2000, p.sea],
        'fill-opacity': neOut, 'fill-antialias': false } }, { 'fill-opacity': 1 });
    ne({ id: 'rbx-coast-glow', type: 'line', source: 'rbx-coast', layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': p.coastGlow, 'line-width': zi(4, 5, 7, 12, 10, 18), 'line-offset': zi(4, 2.5, 7, 6, 10, 9),
        'line-blur': zi(4, 4, 7, 9, 10, 14), 'line-opacity': vec ? fadeOut(V + 0.3, V + 0.8, 0.9) : 0.9 } }, { 'line-opacity': 0.9 });

    if (vec) {
      ofm({ id: 'ofm-water', type: 'fill', 'source-layer': 'water', filter: ['all', isPoly, ['!=', ['get', 'brunnel'], 'tunnel']],
        paint: { 'fill-color': ['match', ['get', 'class'], ['lake', 'river', 'pond', 'dock', 'swimming_pool'], p.lake, p.sea],
          'fill-opacity': fadeIn(V, V + 0.5) } });
    }

    ne({ id: 'rbx-lakes', type: 'fill', source: 'rbx-lakes', paint: { 'fill-color': p.lake, 'fill-opacity': neOut } }, { 'fill-opacity': 1 });
    ne({ id: 'rbx-coastline', type: 'line', source: 'rbx-coast', layout: { 'line-join': 'round' },
      paint: { 'line-color': p.coastline, 'line-width': zi(4, 0.4, 7, 0.8, 10, 1.1), 'line-opacity': vec ? fadeOut(V + 0.2, V + 0.6, 0.85) : 0.85 } }, { 'line-opacity': 0.85 });
    ne({ id: 'rbx-lakes-line', type: 'line', source: 'rbx-lakes',
      paint: { 'line-color': p.coastline, 'line-width': 0.5, 'line-opacity': vec ? fadeOut(V + 0.2, V + 0.6, 0.7) : 0.7 } }, { 'line-opacity': 0.7 });
    ne({ id: 'rbx-rivers', type: 'line', source: 'rbx-rivers', layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': p.river, 'line-width': zi(4, 0.5 * p.riverWidth, 7, 1.2 * p.riverWidth, 10, 2 * p.riverWidth),
        'line-opacity': vec ? fadeOut(V + 0.3, V + 0.8, 0.9) : 0.9 } }, { 'line-opacity': 0.9 });

    if (vec) {
      ofm({ id: 'ofm-waterway-river', type: 'line', 'source-layer': 'waterway', filter: ['all', isLine, cls(['river', 'canal']), ['!=', ['get', 'brunnel'], 'tunnel']],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': p.river, 'line-width': ze(V, 0.6, 10, 1.4, 14, 3.5), 'line-opacity': fadeIn(V, V + 0.6, 0.95) } });
      ofm({ id: 'ofm-waterway-stream', type: 'line', 'source-layer': 'waterway', minzoom: 10.5, filter: ['all', isLine, cls(['stream', 'drain', 'ditch']), ['!=', ['get', 'brunnel'], 'tunnel']],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': p.river, 'line-width': ze(10.5, 0.4, 14, 1.2), 'line-opacity': fadeIn(10.5, 11.5, 0.8) } });

      // Roads: hairline, low contrast, progressive disclosure
      ofm({ id: 'ofm-road-minor', type: 'line', 'source-layer': 'transportation', minzoom: 11.5, filter: ['all', isLine, cls(['minor', 'service'])],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': p.road, 'line-width': ze(11.5, 0.4, 16, 5), 'line-opacity': fadeIn(11.5, 12.5, 0.9) } });
      ofm({ id: 'ofm-road-secondary', type: 'line', 'source-layer': 'transportation', minzoom: 9, filter: ['all', isLine, cls(['secondary', 'tertiary'])],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': p.road, 'line-width': ze(9, 0.4, 12, 1.2, 16, 7), 'line-opacity': fadeIn(9, 10, 0.95) } });
      ofm({ id: 'ofm-road-primary', type: 'line', 'source-layer': 'transportation', minzoom: 7.5, filter: ['all', isLine, cls(['primary', 'trunk'])],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': p.roadMajor, 'line-width': ze(7.5, 0.4, 10, 0.9, 14, 3.5, 16, 9), 'line-opacity': fadeIn(7.5, 8.5, 0.9) } });
      ofm({ id: 'ofm-road-motorway', type: 'line', 'source-layer': 'transportation', filter: ['all', isLine, cls(['motorway'])],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': p.roadMajor, 'line-width': ze(V, 0.5, 10, 1.3, 14, 4, 16, 10), 'line-opacity': fadeIn(V, V + 0.8, 0.95) } });
      ofm({ id: 'ofm-rail', type: 'line', 'source-layer': 'transportation', minzoom: 10, filter: ['all', isLine, ['==', ['get', 'class'], 'rail'], ['!', ['has', 'service']]],
        paint: { 'line-color': p.rail, 'line-width': zi(10, 0.5, 14, 1.2), 'line-dasharray': [3, 2], 'line-opacity': fadeIn(10, 11, 0.8) } });

      // Boundaries (OSM: UK nations are admin_level 4)
      ofm({ id: 'ofm-boundary-4', type: 'line', 'source-layer': 'boundary',
        filter: ['all', ['==', ['get', 'admin_level'], 4], ['!=', ['get', 'maritime'], 1], ['!=', ['get', 'disputed'], 1]],
        layout: { 'line-join': 'round' },
        paint: { 'line-color': p.border, 'line-width': zi(V, 0.7, 12, 1.4), 'line-dasharray': [3, 2.5], 'line-opacity': fadeIn(V + 0.3, V + 0.8, 0.8) } });
      ofm({ id: 'ofm-boundary-2', type: 'line', 'source-layer': 'boundary',
        filter: ['all', ['==', ['get', 'admin_level'], 2], ['!=', ['get', 'maritime'], 1], ['!=', ['get', 'disputed'], 1], ['!', ['has', 'claimed_by']]],
        layout: { 'line-join': 'round' },
        paint: { 'line-color': p.borderIntl, 'line-width': zi(V, 0.9, 12, 1.8), 'line-dasharray': [4, 2], 'line-opacity': fadeIn(V + 0.3, V + 0.8, 0.85) } });
    }

    ne({ id: 'rbx-borders', type: 'line', source: 'rbx-borders', layout: { 'line-join': 'round' },
      paint: { 'line-color': ['match', ['get', 'k'], 'uk-ie', p.borderIntl, p.border],
        'line-width': zi(4, 0.6, 7, 1, 10, 1.4), 'line-dasharray': [3, 2.5],
        'line-opacity': vec ? fadeOut(V + 0.3, V + 0.8, 0.75) : 0.75 } }, { 'line-opacity': 0.75 });

    // Slots: insertion anchors (never drawn). Sea/region annotations go before 'rbx-slot-annotations';
    // your data goes before 'rbx-slot-labels' (RBXBasemap.DATA_BEFORE) — i.e. above the basemap and
    // annotations, below city labels.
    L.push({ id: 'rbx-slot-annotations', type: 'background', layout: { visibility: 'none' }, paint: { 'background-opacity': 0 }, metadata: { 'rbx:group': 'slot' } });
    L.push({ id: 'rbx-slot-labels', type: 'background', layout: { visibility: 'none' }, paint: { 'background-opacity': 0 }, metadata: { 'rbx:group': 'slot' } });

    if (vec) {
      var halo = { 'text-halo-color': p.labelHalo, 'text-halo-width': 1.4, 'text-halo-blur': 0.4 };
      function withHalo(paint) { for (var k in halo) paint[k] = halo[k]; return paint; }
      ofm({ id: 'ofm-label-water', type: 'symbol', 'source-layer': 'water_name', minzoom: 8, filter: ['match', ['geometry-type'], ['Point', 'MultiPoint'], true, false],
        layout: { 'text-field': NAME, 'text-font': ['Noto Sans Italic'], 'text-size': zi(8, 11, 12, 13), 'text-letter-spacing': 0.12, 'text-max-width': 6 },
        paint: withHalo({ 'text-color': p.waterLabel }) });
      ofm({ id: 'ofm-label-waterway', type: 'symbol', 'source-layer': 'waterway', minzoom: 11, filter: ['all', isLine, cls(['river', 'canal'])],
        layout: { 'symbol-placement': 'line', 'text-field': NAME, 'text-font': ['Noto Sans Italic'], 'text-size': 11, 'text-letter-spacing': 0.1, 'symbol-spacing': 400 },
        paint: withHalo({ 'text-color': p.waterLabel }) });
      ofm({ id: 'ofm-label-village', type: 'symbol', 'source-layer': 'place', minzoom: 10.5, filter: cls(['village']),
        layout: { 'text-field': NAME, 'text-font': ['Noto Sans Regular'], 'text-size': zi(10.5, 10, 14, 13), 'text-max-width': 8 },
        paint: withHalo({ 'text-color': p.label, 'text-opacity': fadeIn(10.5, 11, 0.9) }) });
      ofm({ id: 'ofm-label-town', type: 'symbol', 'source-layer': 'place', minzoom: 8, filter: cls(['town']),
        layout: { 'text-field': NAME, 'text-font': ['Noto Sans Regular'], 'text-size': zi(8, 10.5, 12, 14), 'text-max-width': 8 },
        paint: withHalo({ 'text-color': p.label, 'text-opacity': fadeIn(8, 8.5) }) });
      ofm({ id: 'ofm-label-city', type: 'symbol', 'source-layer': 'place', filter: cls(['city']),
        layout: { 'text-field': NAME, 'text-font': ['Noto Sans Bold'], 'text-size': zi(V, 11.5, 10, 15, 14, 19), 'text-max-width': 8,
          'text-letter-spacing': 0.02, 'symbol-sort-key': ['coalesce', ['get', 'rank'], 99] },
        paint: withHalo({ 'text-color': p.labelMajor, 'text-opacity': fadeIn(V + 0.3, V + 0.7) }) });
    }
    return L;
  }

  function buildSources(o, pack) {
    var S = {};
    var gj = function (data) { return { type: 'geojson', data: data, maxzoom: 10, tolerance: 0.3, attribution: ATTR.ne }; };
    S['rbx-land'] = gj(pack.land);
    S['rbx-ocean'] = gj(pack.ocean);
    S['rbx-coast'] = gj(pack.coast);
    S['rbx-bathy'] = gj(pack.bathy);
    S['rbx-lakes'] = gj(pack.lakes);
    S['rbx-rivers'] = gj(pack.rivers);
    S['rbx-borders'] = gj(pack.borders);
    if (o.terrain !== false) S['rbx-dem'] = { type: 'raster-dem', tiles: [o.demUrl], encoding: 'terrarium', tileSize: 256, maxzoom: 12, attribution: ATTR.dem };
    if (o.vector !== false) S['rbx-ofm'] = { type: 'vector', url: o.ofmUrl, attribution: ATTR.ofm };
    return S;
  }

  function opts0(opts) { var o = {}; for (var k in DEFAULTS) o[k] = DEFAULTS[k]; for (k in (opts || {})) o[k] = opts[k]; return o; }
  function pal(theme) { return typeof theme === 'object' && theme ? theme : (palettes[theme] || palettes.light); }

  function style(theme, opts) {
    var o = opts0(opts), p = pal(theme), pack = getPack(o);
    var s = {
      version: 8,
      name: 'RenewaBlox ' + (p.name || 'custom'),
      metadata: { 'rbx:theme': p.name, 'rbx:vectorZoom': o.vectorZoom, 'rbx:focus': o.focus, 'rbx:vector': o.vector !== false, 'rbx:terrain': o.terrain !== false },
      sources: buildSources(o, pack),
      layers: buildLayers(p, o)
    };
    if (o.vector !== false) s.glyphs = o.glyphs;
    return s;
  }

  // ------------------------------------------------------------------------------------------
  // Glyph-free labels: text rasterised on a <canvas> with the page's fonts, used as icons.
  // They live inside the GL canvas (proper layer order + MapLibre collision), need no glyph server.
  // ------------------------------------------------------------------------------------------
  // [name, lon, lat, tier, side('r'|'l'|'t'|'b'), capital]
  var CITIES = [
    ['London', -0.118, 51.509, 1, 'r', 1], ['Edinburgh', -3.189, 55.953, 1, 'r', 1], ['Cardiff', -3.179, 51.481, 1, 'l', 1],
    ['Belfast', -5.930, 54.597, 1, 'r', 1], ['Dublin', -6.260, 53.350, 1, 'l', 1],
    ['Birmingham', -1.898, 52.480, 1, 'r'], ['Manchester', -2.244, 53.480, 1, 'r'], ['Glasgow', -4.251, 55.864, 1, 'l'],
    ['Leeds', -1.549, 53.801, 2, 'r'], ['Bristol', -2.588, 51.455, 2, 'r'], ['Newcastle', -1.614, 54.978, 2, 'r'],
    ['Liverpool', -2.978, 53.408, 2, 'l'], ['Aberdeen', -2.094, 57.149, 2, 'r'], ['Inverness', -4.224, 57.478, 2, 'r'],
    ['Cork', -8.472, 51.898, 2, 'r'], ['Sheffield', -1.470, 53.381, 2, 'r'], ['Plymouth', -4.143, 50.376, 2, 'r'],
    ['Norwich', 1.297, 52.630, 2, 'r'], ['Southampton', -1.404, 50.910, 2, 'r'], ['Nottingham', -1.150, 52.955, 3, 'r'],
    ['Dundee', -2.970, 56.462, 3, 'r'], ['Perth', -3.437, 56.396, 3, 'l'], ['Fort William', -5.105, 56.820, 3, 'r'],
    ['Oban', -5.472, 56.415, 3, 'l'], ['Stornoway', -6.387, 58.209, 3, 'r'], ['Kirkwall', -2.960, 58.981, 3, 'r'],
    ['Lerwick', -1.145, 60.155, 3, 'r'], ['Wick', -3.093, 58.439, 3, 'r'], ['Thurso', -3.522, 58.593, 3, 'l'],
    ['Ullapool', -5.160, 57.895, 3, 'r'], ['Derry', -7.309, 54.997, 3, 'l'], ['Galway', -9.049, 53.271, 3, 'l'],
    ['Limerick', -8.630, 52.668, 3, 'r'], ['Exeter', -3.533, 50.718, 3, 'r'], ['Swansea', -3.944, 51.621, 3, 'l'],
    ['York', -1.082, 53.960, 3, 'r'], ['Hull', -0.337, 53.745, 3, 'r'], ['Carlisle', -2.936, 54.892, 3, 'r'],
    ['Cambridge', 0.122, 52.205, 3, 'r'], ['Oxford', -1.258, 51.752, 3, 'l'], ['Aberystwyth', -4.082, 52.415, 3, 'r'],
    ['Dumfries', -3.605, 55.070, 3, 'l'], ['Douglas', -4.482, 54.150, 3, 'r'], ['Penzance', -5.537, 50.119, 3, 'r'],
    ['Paris', 2.349, 48.857, 0, 'r'], ['Brussels', 4.352, 50.847, 0, 'r'], ['Amsterdam', 4.900, 52.370, 0, 'r']
  ];
  var TIER_MINZOOM = { 0: 4.6, 1: 3.5, 2: 5.3, 3: 6.2, 4: 7.4, 5: 8.4 };
  var REGIONS = [ // [text, lon, lat, minz, maxz]
    ['SCOTLAND', -4.35, 57.05, 4.4, 6.9], ['ENGLAND', -1.9, 51.95, 4.4, 6.9], ['WALES', -3.75, 52.30, 4.4, 6.9],
    ['NORTHERN\nIRELAND', -6.7, 54.62, 5.6, 6.9], ['IRELAND', -8.3, 52.72, 4.4, 6.9]
  ];
  var SEAS = [ // [text, lon, lat, minz, maxz]
    ['North Sea', 1.3, 56.55, 3.5, 8], ['Irish Sea', -5.15, 53.75, 5.0, 8], ['Atlantic\nOcean', -13.0, 55.2, 3.5, 7.5],
    ['English Channel', -2.2, 50.12, 5.3, 8.5], ['Celtic Sea', -7.4, 50.95, 5.0, 8], ['The Minch', -6.05, 58.05, 6.3, 9],
    ['Bristol Channel', -4.35, 51.33, 6.8, 9], ['Moray Firth', -3.55, 57.83, 6.8, 9.5], ['Sea of the\nHebrides', -7.05, 57.05, 6.6, 9],
    ['Firth of Forth', -2.75, 56.12, 7.4, 10]
  ];

  function cssFont(name, fallback) {
    try { var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim(); if (v) return v; } catch (e) {}
    return fallback;
  }

  // Draw text (+ optional dot) into ImageData. Returns {img, w, h, ax, ay} (anchor point in px within image, at 1x)
  function rasterLabel(lines, st, dpr) {
    var c = document.createElement('canvas'), g = c.getContext('2d');
    var font = (st.italic ? 'italic ' : '') + st.weight + ' ' + (st.size * dpr) + 'px ' + st.family;
    g.font = font;
    var ls = (st.spacing || 0) * dpr, lh = st.size * (st.lineHeight || 1.18) * dpr, hw = (st.halo || 0) * dpr;
    function measure(t) { if (!ls) return g.measureText(t).width; var w = 0; for (var i = 0; i < t.length; i++) w += g.measureText(t[i]).width + ls; return w - ls; }
    var widths = lines.map(measure), tw = Math.max.apply(null, widths), th = lh * lines.length;
    var dotR = st.dot ? st.dot.r * dpr : 0, dotPad = st.dot ? (st.dot.stroke || 0) * dpr : 0, gap = st.dot ? 4 * dpr : 0;
    var side = st.side || 'c';
    var pad = Math.ceil(hw + 2 * dpr);
    var dotBox = dotR ? 2 * (dotR + dotPad) : 0;
    var W, H, tx, ty, dx = 0, dy = 0;
    if (!dotR || side === 'c') { W = tw + 2 * pad; H = th + 2 * pad; tx = pad; ty = pad; }
    else if (side === 'r' || side === 'l') {
      W = dotBox + gap + tw + 2 * pad; H = Math.max(th, dotBox) + 2 * pad;
      ty = (H - th) / 2; dy = H / 2;
      if (side === 'r') { dx = pad + dotBox / 2; tx = pad + dotBox + gap; } else { tx = pad; dx = pad + tw + gap + dotBox / 2; }
    } else {
      W = Math.max(tw, dotBox) + 2 * pad; H = dotBox + gap + th + 2 * pad; tx = (W - tw) / 2; dx = W / 2;
      if (side === 'b') { dy = pad + dotBox / 2; ty = pad + dotBox + gap; } else { ty = pad; dy = pad + th + gap + dotBox / 2; }
    }
    c.width = Math.ceil(W); c.height = Math.ceil(H);
    g = c.getContext('2d'); g.font = font; g.textBaseline = 'middle'; g.lineJoin = 'round'; g.miterLimit = 2;
    function draw(t, x, y, stroke) {
      var align = st.align || (side === 'l' ? 'right' : side === 'r' ? 'left' : 'center');
      var w = measure(t), x0 = align === 'left' ? x : align === 'right' ? x + (tw - w) : x + (tw - w) / 2;
      if (!ls) { stroke ? g.strokeText(t, x0, y) : g.fillText(t, x0, y); return; }
      for (var i = 0; i < t.length; i++) { stroke ? g.strokeText(t[i], x0, y) : g.fillText(t[i], x0, y); x0 += g.measureText(t[i]).width + ls; }
    }
    lines.forEach(function (t, i) {
      var y = ty + lh * i + lh / 2;
      if (hw) { g.strokeStyle = st.haloColor; g.lineWidth = hw * 2; draw(t, tx, y, true); }
      g.fillStyle = st.color; draw(t, tx, y, false);
    });
    if (dotR) {
      g.beginPath(); g.arc(dx, dy, dotR, 0, Math.PI * 2);
      if (dotPad) { g.lineWidth = dotPad * 2; g.strokeStyle = st.dot.strokeColor; g.stroke(); }
      g.fillStyle = st.dot.color; g.fill();
    }
    return { img: g.getImageData(0, 0, c.width, c.height), w: c.width / dpr, h: c.height / dpr, ax: (dotR ? dx : c.width / 2) / dpr, ay: (dotR ? dy : c.height / 2) / dpr };
  }

  function attach(map, opts) {
    opts = opts || {};
    function styleMeta() { try { return (map.style && map.style._loaded && map.style.stylesheet && map.style.stylesheet.metadata) || (map.getStyle() || {}).metadata || {}; } catch (e) { return {}; } }
    var state = { imgs: [], destroyed: false, themeSet: !!opts.theme, theme: opts.theme || 'light' };
    // Read theme / handover zoom / vector flag from the style's metadata (once the style has parsed).
    function syncMeta() {
      var meta = styleMeta();
      if (!state.themeSet && meta['rbx:theme']) state.theme = meta['rbx:theme'];
      state.V = opts.vectorZoom || meta['rbx:vectorZoom'] || DEFAULTS.vectorZoom;
      state.vector = meta['rbx:vector'] !== false && !!(map.getSource && safeSource('rbx-ofm'));
      if (!state.mode) state.mode = state.vector ? 'online' : 'offline';
      map.__rbxBasemapMode = state.mode;
    }
    function safeSource(id) { try { return map.getSource(id); } catch (e) { return null; } }
    var dpr = Math.max(2, Math.ceil(window.devicePixelRatio || 1));
    var fonts = {
      label: opts.labelFont || cssFont('--rbx-map-font', 'Inter, "Helvetica Neue", Arial, sans-serif'),
      sea: opts.seaFont || cssFont('--rbx-map-serif', '"Source Serif 4", Georgia, "Times New Roman", serif')
    };
    state.V = opts.vectorZoom || DEFAULTS.vectorZoom; state.vector = true;
    map.__rbxBasemapMode = 'online';

    function cityList() {
      var list = (opts.cities || CITIES).slice();
      if (state.mode === 'offline' && opts.packPlaces !== false) {
        // add Natural Earth places for higher zooms when vector labels are unavailable
        try {
          var pk = getPack(opts), have = {};
          list.forEach(function (c) { have[c[0].toLowerCase()] = 1; });
          pk.places.features.forEach(function (f) {
            var n = f.properties.n, k = f.properties.k;
            if (!n || have[n.toLowerCase()] || ['GBR', 'IRL', 'IMN', 'JEY', 'GGY'].indexOf(k) < 0) return;
            n = n.replace('Derry~Londonderry', 'Derry');
            list.push([n, f.geometry.coordinates[0], f.geometry.coordinates[1], f.properties.r <= 7 ? 4 : 5, 'r']);
          });
        } catch (e) {}
      }
      return list;
    }

    function buildImages() {
      var p = pal(state.theme), feats = { city: [], region: [], sea: [] };
      state.imgs.forEach(function (id) { if (map.hasImage(id)) map.removeImage(id); });
      state.imgs = [];
      function add(id, r) { map.addImage(id, r.img, { pixelRatio: dpr }); state.imgs.push(id); }
      if (opts.cityLabels !== false) cityList().forEach(function (c, i) {
        var tier = c[3], cap = c[5], id = 'rbx-lbl-c' + i;
        var r = rasterLabel([c[0]], {
          family: fonts.label, weight: tier <= 1 ? 600 : 500, size: tier === 0 ? 11 : tier <= 1 ? 12.5 : tier === 2 ? 11.5 : 11,
          color: tier <= 1 ? p.labelMajor : p.label, halo: 2, haloColor: p.labelHalo, side: c[4] || 'r', spacing: 0.1,
          dot: { r: cap ? 3 : tier <= 2 ? 2.4 : 2, color: tier === 0 ? p.label : p.dot, stroke: cap ? 1.5 : 1.2, strokeColor: p.dotHalo }
        }, dpr);
        add(id, r);
        feats.city.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [c[1], c[2]] },
          properties: { img: id, tier: tier, sort: i,
            off: [+(r.w / 2 - r.ax).toFixed(2), +(r.h / 2 - r.ay).toFixed(2)] } });
      });
      if (opts.regionLabels !== false) REGIONS.forEach(function (c, i) {
        var id = 'rbx-lbl-r' + i;
        add(id, rasterLabel(c[0].split('\n'), { family: fonts.label, weight: 600, size: 11, color: p.region, spacing: 4.2, align: 'center' }, dpr));
        feats.region.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [c[1], c[2]] }, properties: { img: id, minz: c[3], maxz: c[4] } });
      });
      if (opts.seaLabels !== false) SEAS.forEach(function (c, i) {
        var id = 'rbx-lbl-s' + i;
        add(id, rasterLabel(c[0].split('\n'), { family: fonts.sea, weight: 400, italic: true, size: c[0].length > 12 ? 12.5 : 14, color: p.sea_label, spacing: 1.6, align: 'center', lineHeight: 1.25 }, dpr));
        feats.sea.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [c[1], c[2]] }, properties: { img: id, minz: c[3], maxz: c[4] } });
      });
      return feats;
    }

    function fc(f) { return { type: 'FeatureCollection', features: f }; }

    var CITY_LAYERS = [], ANN_LAYERS = [];
    function install() {
      syncMeta();
      var feats = buildImages(), V = state.V;
      var off = state.mode === 'offline' || !state.vector;
      var firstOfm = (map.getStyle().layers.filter(function (l) { return l.metadata && l.metadata['rbx:group'] === 'ofm' && l.type === 'symbol'; })[0] || {}).id;
      var setData = function (id, d) { var s = map.getSource(id); if (s) s.setData(d); else map.addSource(id, { type: 'geojson', data: d }); };
      setData('rbx-lbl-city', fc(feats.city)); setData('rbx-lbl-region', fc(feats.region)); setData('rbx-lbl-sea', fc(feats.sea));
      var annBefore = map.getLayer('rbx-slot-annotations') ? 'rbx-slot-annotations' : undefined;
      // Annotations: one layer per (minz,maxz) window — layer zoom ranges are exact, whereas
      // filters only see the integer tile zoom. Placed after cities, so cities win collisions.
      ANN_LAYERS.forEach(function (id) { if (map.getLayer(id)) map.removeLayer(id); });
      ANN_LAYERS = [];
      [['sea', feats.sea], ['region', feats.region]].forEach(function (g) {
        var groups = {};
        g[1].forEach(function (f) { var k = f.properties.minz + '_' + f.properties.maxz; (groups[k] = groups[k] || []).push(f.properties.img); });
        Object.keys(groups).forEach(function (k, i) {
          var zz = k.split('_').map(Number), id = 'rbx-' + g[0] + '-labels-' + i;
          map.addLayer({ id: id, type: 'symbol', source: 'rbx-lbl-' + g[0], minzoom: zz[0], maxzoom: zz[1],
            filter: ['match', ['get', 'img'], groups[k], true, false],
            layout: { 'icon-image': ['get', 'img'], 'icon-allow-overlap': g[0] === 'sea', 'icon-ignore-placement': true, 'icon-padding': 4 },
            paint: { 'icon-opacity': 1 }, metadata: { 'rbx:group': 'labels' } }, annBefore);
          ANN_LAYERS.push(id);
        });
      });
      // Cities: one layer per tier (layer min/max zoom are exact); lower tiers first so tier 1 sits on top
      // and wins collisions (MapLibre places symbols top layer first).
      CITY_LAYERS.forEach(function (id) { if (map.getLayer(id)) map.removeLayer(id); });
      CITY_LAYERS = [];
      var tiers = {};
      feats.city.forEach(function (f) { tiers[f.properties.tier] = 1; });
      Object.keys(tiers).map(Number).sort(function (x, y) { return y - x; }).forEach(function (t) {
        var id = 'rbx-city-labels-' + t, minz = TIER_MINZOOM[t] != null ? TIER_MINZOOM[t] : 6;
        var maxz = off ? 24 : V + 0.7;
        if (minz >= maxz) return;
        map.addLayer({ id: id, type: 'symbol', source: 'rbx-lbl-city', minzoom: minz, maxzoom: maxz,
          filter: ['==', ['get', 'tier'], t],
          layout: { 'icon-image': ['get', 'img'], 'icon-offset': ['array', 'number', 2, ['get', 'off']], 'symbol-sort-key': ['get', 'sort'],
            'icon-padding': 2, 'icon-allow-overlap': false },
          paint: { 'icon-opacity': off ? 1 : ['interpolate', ['linear'], ['zoom'], V + 0.2, 1, V + 0.6, 0] },
          metadata: { 'rbx:group': 'labels' } }, firstOfm);
        CITY_LAYERS.push(id);
      });
    }

    function styleReady() { return !!(map.style && map.style._loaded); }

    function goOffline(reason) {
      if (state.mode === 'offline' || state.destroyed) return;
      if (!styleReady()) { map.once('style.load', function () { goOffline(reason); }); return; }
      state.mode = 'offline'; map.__rbxBasemapMode = 'offline'; map.__rbxBasemapOfflineReason = reason || 'vector source error';
      var layers = map.getStyle().layers;
      layers.forEach(function (l) {
        var m = l.metadata || {};
        // Remove (not just hide) vector layers + source: an unreachable TileJSON otherwise keeps
        // map.isStyleLoaded() false forever and the map 'load' event would never fire.
        if (m['rbx:group'] === 'ofm') { try { map.removeLayer(l.id); } catch (e) {} return; }
        if (m['rbx:offline']) Object.keys(m['rbx:offline']).forEach(function (k) { map.setPaintProperty(l.id, k, m['rbx:offline'][k]); });
      });
      try { if (map.getSource('rbx-ofm')) map.removeSource('rbx-ofm'); } catch (e) {}
      // city labels take over at all zooms, with extra Natural Earth places
      if (state.fontsReady) {
        install();
      }
      try { map.fire('rbx:basemapmode', { mode: 'offline', reason: reason }); } catch (e) {}
      if (opts.onMode) opts.onMode('offline', reason);
    }

    function onError(e) {
      var err = (e && e.error) || {}, msg = String(err.message || err || ''), url = String(err.url || '');
      if (e && e.sourceId === 'rbx-ofm') return goOffline('vector tiles unreachable');
      if (/openfreemap|\/fonts\/|\.pbf/i.test(msg + ' ' + url)) return goOffline('vector tiles/glyphs unreachable');
    }
    map.on('error', onError);

    // Safety net: if we are zoomed in and the vector source never loads, fall back.
    var watchdog = null;
    function checkLoaded() {
      if (state.mode === 'offline' || !state.vector || state.destroyed) return;
      if (map.getZoom() < state.V) return;
      if (watchdog) return;
      watchdog = setTimeout(function () {
        watchdog = null;
        try { if (map.getZoom() >= state.V && !map.isSourceLoaded('rbx-ofm')) {
          var sc = map.style && map.style.sourceCaches && map.style.sourceCaches['rbx-ofm'];
          var tiles = sc ? Object.keys(sc._tiles || {}).length : 1;
          var loaded = sc ? Object.keys(sc._tiles || {}).filter(function (k) { return sc._tiles[k].state === 'loaded'; }).length : 1;
          if (tiles > 0 && loaded === 0) goOffline('vector tiles timed out');
        } } catch (e) {}
      }, opts.timeoutMs || 9000);
    }
    map.on('moveend', checkLoaded);
    // If the TileJSON hangs (firewall silently dropping), don't hold up the map's 'load' event.
    var bootTimer = state.vector ? setTimeout(function () {
      try { var src = map.getSource('rbx-ofm'); if (src && !src.loaded()) goOffline('vector TileJSON timed out'); } catch (e) {}
    }, opts.bootTimeoutMs || 6000) : null;

    var ready = (document.fonts && document.fonts.load) ? Promise.all([
      document.fonts.load('600 12px ' + fonts.label), document.fonts.load('500 12px ' + fonts.label),
      document.fonts.load('italic 400 14px ' + fonts.sea)
    ]).catch(function () {}) : Promise.resolve();
    var timeout = new Promise(function (r) { setTimeout(r, 2500); });
    var installed = Promise.race([ready, timeout]).then(function () {
      if (state.destroyed) return;
      state.fontsReady = true;
      if (styleReady()) install(); else map.once('style.load', install);
    });

    var ctl = {
      ready: installed,
      mode: function () { return state.mode || 'online'; },
      setTheme: function (t) { state.theme = t; state.themeSet = true; applyTheme(map, t, { skipLabels: true }); install(); return ctl; },
      destroy: function () {
        state.destroyed = true; clearTimeout(bootTimer); map.off('error', onError); map.off('moveend', checkLoaded);
        CITY_LAYERS.concat(ANN_LAYERS).forEach(function (id) { if (map.getLayer(id)) map.removeLayer(id); });
        state.imgs.forEach(function (id) { if (map.hasImage(id)) map.removeImage(id); });
      }
    };
    map.__rbxBasemap = ctl;
    return ctl;
  }

  // Re-apply a palette to an existing map (no setStyle, your data layers are untouched)
  function applyTheme(map, theme, o2) {
    var st = map.getStyle(), meta = st.metadata || {};
    var o = opts0({ vectorZoom: meta['rbx:vectorZoom'], focus: meta['rbx:focus'], vector: meta['rbx:vector'], terrain: meta['rbx:terrain'] });
    var defs = buildLayers(pal(theme), o), offline = map.__rbxBasemapMode === 'offline';
    defs.forEach(function (d) {
      if (!map.getLayer(d.id)) return;
      Object.keys(d.paint || {}).forEach(function (k) {
        var v = d.paint[k];
        if (offline && d.metadata && d.metadata['rbx:offline'] && k in d.metadata['rbx:offline']) v = d.metadata['rbx:offline'][k];
        map.setPaintProperty(d.id, k, v);
      });
    });
    if (map.__rbxBasemap && !(o2 && o2.skipLabels)) map.__rbxBasemap.setTheme(theme);
  }

  window.RBXBasemap = {
    version: '1.0.0',
    style: style,
    attach: attach,
    applyTheme: applyTheme,
    palettes: palettes,
    decode: decode,
    _rasterLabel: rasterLabel,
    cities: CITIES,
    attribution: ATTR,
    DATA_BEFORE: DATA_BEFORE
  };
})();
