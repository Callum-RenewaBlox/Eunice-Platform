/* RBX.layers: MapLibre layer factory (spec 5.2–5.6): area-true circle stacks for SAM and Hydro with ghosts,
   Night glow, sort keys; TAM symbol layer with lazy icons; SAM-in-TAM dot; selection rings + pulse;
   hover state, nearest-centre picking with co-located stack detection; tooltip. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var L = RBX.layers = { ready: false };

  var SIZE = L.SIZE = {
    sam: [[4, 2.8, 9.2], [6, 3.6, 14.6], [8, 5.0, 20.8], [11, 7.0, 30.8], [14, 9.0, 42.4]],
    hydro: [[4, 3.0, 9.8], [6, 3.8, 13.8], [8, 5.0, 18.8], [11, 7.0, 26.0], [14, 9.0, 34.4]]
  };
  var TAM_SCALE = [[4, 0.66], [6, 0.84], [8, 1.05], [11, 1.4], [14, 1.75]];
  var HOV = ['boolean', ['feature-state', 'hover'], false];
  var HOVER_ADD = ['case', HOV, 2, 0];

  /** Zoom-interpolated radius; `add` may be a feature-state expression. Zoom stays the top-level interpolate. */
  function R(stops, add, mult) {
    var e = ['interpolate', ['exponential', 1.5], ['zoom']];
    stops.forEach(function (s) { e.push(s[0], ['+', add || 0, ['*', mult == null ? 1 : mult, ['max', s[1], ['*', s[2], ['get', 'sv']]]]]); });
    return e;
  }
  L.R = R;
  function interpExp(z, pts) {
    if (z <= pts[0][0]) return pts[0][1];
    for (var i = 0; i < pts.length - 1; i++) {
      var a = pts[i], b = pts[i + 1];
      if (z <= b[0]) { var t = (Math.pow(1.5, z - a[0]) - 1) / (Math.pow(1.5, b[0] - a[0]) - 1); return a[1] + (b[1] - a[1]) * t; }
    }
    return pts[pts.length - 1][1];
  }
  /** JS twin of R() for the size key. */
  L.radiusAt = function (kind, z, sv) { return interpExp(z, SIZE[kind].map(function (s) { return [s[0], Math.max(s[1], s[2] * sv)]; })); };
  L.tamScaleAt = function (z) { return interpExp(z, TAM_SCALE); };
  function tamRing(add) {
    var e = ['interpolate', ['exponential', 1.5], ['zoom']];
    TAM_SCALE.forEach(function (s) { e.push(s[0], ['+', add || 0, ['*', s[1], ['get', 'hr']]]); });
    return e;
  }

  var CORE = { sam: 'sam-core', hydro: 'hydro-core', tam: 'tam-core' };
  L.CORE = CORE;
  var VIEW_LAYERS = {
    sam: ['sam-glow', 'sam-ghost', 'sam-core', 'sam-hot'],
    hydro: ['hydro-glow', 'hydro-ghost', 'hydro-core', 'hydro-hot'],
    tam: ['tam-heat', 'tam-ghost', 'tam-core', 'tam-samdot', 'hover-tam']
  };
  L.VIEW_LAYERS = VIEW_LAYERS;
  var NIGHT_ONLY = { 'sam-glow': 1, 'sam-hot': 1, 'hydro-glow': 1, 'hydro-hot': 1, 'tam-heat': 1 };

  // ------------------------------------------------------------------ colour expressions
  function colour(kind, P, hot) {
    if (kind === 'sam') { var t = hot ? P.tierHot : P.tier; return ['match', ['get', 't'], 1, t[0], 2, t[1], 3, t[2], 4, t[3], t[4]]; }
    var h = hot ? P.hydHot : P.hyd;
    return ['match', ['get', 'c'], 0, h[0], 1, h[1], 2, h[2], 'rgba(0,0,0,0)'];
  }
  function hollow(kind) { return kind === 'sam' ? ['==', ['get', 'pr'], 0] : ['==', ['get', 'c'], 3]; }
  function strokeColour(kind, P) {
    var base = kind === 'sam' ? colour('sam', P) : P.unv;
    if (P.night) return ['case', hollow(kind), base, colour(kind, P, true)];
    return ['case', hollow(kind), base, P.stroke];
  }
  function strokeWidth(kind) {
    var hw = kind === 'sam' ? [1.6, 2] : [1.7, 2];
    return ['interpolate', ['linear'], ['zoom'],
      5, ['case', HOV, 2.2, hollow(kind), hw[0], 0.9],
      10, ['case', HOV, 2.6, hollow(kind), hw[1], 1.5]];
  }
  /** Legend-hover preview: matching active features stay at full opacity, others drop to ~22%. */
  function previewWrap(kind, base) {
    var pv = RBX.state.preview;
    if (!pv || pv.view !== kind) return base;
    var m = ['in', ['get', pv.prop], ['literal', pv.values]];
    return ['case', m, base, ['*', base, 0.234]];
  }
  function coreOpacity(kind) { return previewWrap(kind, ['case', hollow(kind), 0, 0.94]); }
  function strokeOpacity(kind, P) {
    var base = P.night ? ['case', hollow(kind), 1, 0.75] : 1;
    return previewWrap(kind, base);
  }
  function tamOpacity() { return previewWrap('tam', ['case', HOV, 1, ['==', ['get', 'ap'], 1], 0.82, 0.96]); }

  // ------------------------------------------------------------------ build
  L.add = function (map) {
    var P = RBX.theme.pal(), B = window.RBXBasemap ? window.RBXBasemap.DATA_BEFORE : undefined, th = RBX.state.theme;
    var D = RBX.data;
    map.on('styleimagemissing', function (e) { RBX.icons.draw(map, e.id); });
    RBX.icons.ensure(map, th);
    ['sam', 'hydro', 'tam'].forEach(function (k) { map.addSource(k, { type: 'geojson', data: D.geojson(k) }); });
    map.addSource('sel', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addSource('hover', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    var add = function (l) { map.addLayer(l, B); };

    ['sam', 'hydro'].forEach(function (k) {
      add({ id: k + '-glow', type: 'circle', source: k, layout: { visibility: 'none' }, paint: {
        'circle-radius': R(SIZE[k], 3, 2.2), 'circle-color': colour(k, P), 'circle-blur': 1,
        'circle-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 9, 0.28, 12, 0.18] } });
      add({ id: k + '-ghost', type: 'circle', source: k, layout: { visibility: 'none' }, paint: {
        'circle-radius': R(SIZE[k]), 'circle-color': colour(k, P), 'circle-opacity': P.night ? 0.12 : 0.09, 'circle-stroke-width': 0 } });
      add({ id: k + '-core', type: 'circle', source: k, layout: { visibility: 'none', 'circle-sort-key': ['get', 'sk'] }, paint: {
        'circle-radius': R(SIZE[k], HOVER_ADD), 'circle-color': colour(k, P), 'circle-opacity': coreOpacity(k),
        'circle-stroke-color': strokeColour(k, P), 'circle-stroke-opacity': strokeOpacity(k, P), 'circle-stroke-width': strokeWidth(k),
        'circle-pitch-alignment': 'map' } });
      add({ id: k + '-hot', type: 'circle', source: k, minzoom: 5.5, layout: { visibility: 'none' }, paint: {
        'circle-radius': R(SIZE[k], 0, 0.34), 'circle-color': colour(k, P, true), 'circle-blur': 0.9,
        'circle-opacity': ['interpolate', ['linear'], ['zoom'], 5.5, 0, 7, 0.85] } });
    });
    var tamLayout = function (vis) {
      return { visibility: vis, 'icon-image': RBX.icons.expr(th),
        'icon-size': ['interpolate', ['exponential', 1.5], ['zoom'], 4, 0.66, 6, 0.84, 8, 1.05, 11, 1.4, 14, 1.75],
        'icon-allow-overlap': true, 'icon-ignore-placement': true, 'symbol-sort-key': ['-', 0, ['get', 'kw']] };
    };
    // Night-only density glow under the TAM glyphs (spec 5.4, P1); fades out by z 7.8
    add({ id: 'tam-heat', type: 'heatmap', source: 'tam', maxzoom: 8, layout: { visibility: 'none' }, paint: {
      'heatmap-weight': ['interpolate', ['linear'], ['get', 'kw'], 0, 0.15, 1000, 0.5, 20000, 1],
      'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 4, 0.7, 7, 1.1],
      'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 4, 10, 6, 18, 8, 30],
      'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(0,0,0,0)', 0.15, 'rgba(18,70,76,0.20)', 0.4, 'rgba(30,130,110,0.32)',
        0.7, 'rgba(120,200,110,0.42)', 1, 'rgba(215,249,108,0.55)'],
      'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0.75, 7, 0.35, 7.8, 0] } });
    add({ id: 'tam-ghost', type: 'symbol', source: 'tam', layout: tamLayout('none'), paint: { 'icon-opacity': 0.10 } });
    add({ id: 'tam-core', type: 'symbol', source: 'tam', layout: tamLayout('none'), paint: { 'icon-opacity': tamOpacity() } });
    add({ id: 'tam-samdot', type: 'circle', source: 'tam', layout: { visibility: 'none' }, paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 1.6, 8, 2.4, 12, 3.2], 'circle-color': P.samdot,
      'circle-stroke-width': 1, 'circle-stroke-color': P.samdotStroke } });
    add({ id: 'hover-tam', type: 'circle', source: 'hover', layout: { visibility: 'none' }, paint: {
      'circle-radius': tamRing(0), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 1.5, 'circle-stroke-color': P.selRing, 'circle-stroke-opacity': 0.7 } });

    ['sam', 'hydro', 'tam'].forEach(function (k) {
      var ring = function (a) { return k === 'tam' ? tamRing(a) : R(SIZE[k], a); };
      var f = ['==', ['get', 'kind'], k];
      add({ id: 'sel-' + k + '-halo', type: 'circle', source: 'sel', filter: f, paint: {
        'circle-radius': ring(4), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 7, 'circle-stroke-color': P.selRing, 'circle-stroke-opacity': 0.1 } });
      add({ id: 'sel-' + k + '-pulse', type: 'circle', source: 'sel', filter: f, paint: {
        'circle-radius': ring(5), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 2, 'circle-stroke-color': P.selRing, 'circle-stroke-opacity': 0 } });
      add({ id: 'sel-' + k, type: 'circle', source: 'sel', filter: f, paint: {
        'circle-radius': ring(4), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 2, 'circle-stroke-color': P.selRing } });
    });
    L.ready = true;
    L.map = map;
    L.applyFilters();
    L.showView(RBX.state.view);
  };

  L.showView = function (view) {
    var m = L.map; if (!m) return;
    var night = RBX.state.theme === 'night';
    Object.keys(VIEW_LAYERS).forEach(function (k) {
      VIEW_LAYERS[k].forEach(function (id) {
        var on = k === view && (!NIGHT_ONLY[id] || night);
        if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
      });
    });
    L.clearHover();
    L.relief(view);
  };

  L.applyFilters = function () {
    var m = L.map; if (!m) return;
    ['sam', 'hydro'].forEach(function (k) {
      var A = RBX.filters.expr(k);
      m.setFilter(k + '-core', A); m.setFilter(k + '-glow', A); m.setFilter(k + '-ghost', ['!', A]);
      m.setFilter(k + '-hot', ['all', A, ['!', hollow(k)]]);
    });
    var T = RBX.filters.expr('tam');
    m.setFilter('tam-core', T); m.setFilter('tam-ghost', ['!', T]);
    if (m.getLayer('tam-heat')) m.setFilter('tam-heat', T);
    m.setFilter('tam-samdot', ['all', T, ['==', ['get', 'sam'], 1]]);
  };

  /** Re-apply every data paint property for the current theme and preview state. */
  L.paint = function () {
    var m = L.map; if (!m) return;
    var P = RBX.theme.pal();
    ['sam', 'hydro'].forEach(function (k) {
      m.setPaintProperty(k + '-glow', 'circle-color', colour(k, P));
      m.setPaintProperty(k + '-ghost', 'circle-color', colour(k, P));
      m.setPaintProperty(k + '-ghost', 'circle-opacity', P.night ? 0.12 : 0.09);
      m.setPaintProperty(k + '-core', 'circle-color', colour(k, P));
      m.setPaintProperty(k + '-core', 'circle-opacity', coreOpacity(k));
      m.setPaintProperty(k + '-core', 'circle-stroke-color', strokeColour(k, P));
      m.setPaintProperty(k + '-core', 'circle-stroke-opacity', strokeOpacity(k, P));
      m.setPaintProperty(k + '-hot', 'circle-color', colour(k, P, true));
    });
    m.setPaintProperty('tam-core', 'icon-opacity', tamOpacity());
    m.setPaintProperty('tam-samdot', 'circle-color', P.samdot);
    m.setPaintProperty('tam-samdot', 'circle-stroke-color', P.samdotStroke);
    m.setPaintProperty('hover-tam', 'circle-stroke-color', P.selRing);
    ['sam', 'hydro', 'tam'].forEach(function (k) {
      ['sel-' + k, 'sel-' + k + '-halo', 'sel-' + k + '-pulse'].forEach(function (id) { m.setPaintProperty(id, 'circle-stroke-color', P.selRing); });
    });
  };
  L.applyTheme = function () {
    var m = L.map; if (!m) return;
    var th = RBX.state.theme;
    RBX.icons.ensure(m, th);
    m.setLayoutProperty('tam-core', 'icon-image', RBX.icons.expr(th));
    m.setLayoutProperty('tam-ghost', 'icon-image', RBX.icons.expr(th));
    L.paint();
    L.showView(RBX.state.view);
  };
  L.setPreview = function (pv) {
    var cur = RBX.state.preview;
    if (JSON.stringify(cur) === JSON.stringify(pv)) return;
    RBX.state.preview = pv;
    L.paint();
  };

  /** Per-view relief: Hydro gets 1.30× (Paper) / 1.15× (Night) hillshade exaggeration; other views restore the base. */
  L.relief = function (view) {
    var m = L.map; if (!m || !m.getLayer('rbx-hillshade') || !window.RBXBasemap) return;
    var th = RBX.state.theme, base = (window.RBXBasemap.palettes[th] || {}).hsExaggeration;
    if (!base) return;
    var k = view === 'hydro' ? (th === 'night' ? 1.15 : 1.30) : 1;
    var e = ['interpolate', ['linear'], ['zoom']];
    for (var i = 0; i < base.length; i += 2) e.push(base[i], Math.min(1, base[i + 1] * k));
    try { m.setPaintProperty('rbx-hillshade', 'hillshade-exaggeration', e); } catch (err) { /* layer may be gone */ }
  };

  // ------------------------------------------------------------------ hover, picking, tooltip
  var hoverId = null, hoverKind = null;
  L.clearHover = function () {
    var m = L.map; if (!m) return;
    if (hoverId != null && hoverKind && hoverKind !== 'tam') { try { m.setFeatureState({ source: hoverKind, id: hoverId }, { hover: false }); } catch (e) { /* ignore */ } }
    if (hoverKind === 'tam') { var s = m.getSource('hover'); if (s) s.setData({ type: 'FeatureCollection', features: [] }); }
    hoverId = null; hoverKind = null;
    var tip = document.getElementById('tip'); if (tip) tip.hidden = true;
    m.getCanvas().style.cursor = '';
  };
  L.setHover = function (row) {
    var m = L.map; if (!m) return;
    if (row && row.kind === hoverKind && row.id === hoverId) return;
    L.clearHover();
    if (!row) return;
    hoverId = row.id; hoverKind = row.kind;
    if (row.kind === 'tam') {
      m.getSource('hover').setData({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [row.lon, row.lat] }, properties: { hr: row.hr } }] });
    } else m.setFeatureState({ source: row.kind, id: row.id }, { hover: true });
    m.getCanvas().style.cursor = 'pointer';
  };

  /** Candidates under a point within ±pad px, nearest projected centre first (ties → smaller symbol). */
  L.pick = function (pt, pad) {
    var m = L.map, view = RBX.state.view;
    if (!m || !CORE[view] || !m.getLayer(CORE[view])) return [];
    var fs = m.queryRenderedFeatures([[pt.x - pad, pt.y - pad], [pt.x + pad, pt.y + pad]], { layers: [CORE[view]] });
    var rows = RBX.data.rows[view], seen = {}, out = [];
    fs.forEach(function (f) {
      var id = f.properties.id; if (seen[id]) return; seen[id] = 1;
      var r = rows[id]; if (!r) return;
      var p = m.project([r.lon, r.lat]);
      out.push({ row: r, d: Math.hypot(p.x - pt.x, p.y - pt.y), x: p.x, y: p.y, s: view === 'tam' ? r.band : r.sv });
    });
    out.sort(function (a, b) { return (a.d - b.d) || (a.s - b.s); });
    return out;
  };
  /** Rows stacked on the best candidate (centres within 3 px). */
  L.stackAt = function (cands) {
    if (cands.length < 2) return [];
    var b = cands[0];
    var st = cands.filter(function (c) { return Math.hypot(c.x - b.x, c.y - b.y) <= 3; });
    return st.length >= 2 ? st.map(function (c) { return c.row; }) : [];
  };

  RBX.hooks.tooltip = RBX.hooks.tooltip || function (r) {
    var cfg = RBX.config, lab = cfg.labels || {};
    if (r.kind === 'sam') return (lab.tiers || {})[r.t] + ' · ' + U.cap(r.kw) + (r.town ? ' · ' + r.town : '');
    if (r.kind === 'tam') return r.fuel + ' · ' + (r.ro ? 'RO' : 'FiT') + ' · ' + U.cap(r.kw);
    return (r.c === 3 ? 'Unverified' : r.conf + ' confidence') + ' · ' + U.int(r.kw) + ' kW stranded';
  };
  L.showTip = function (row, pt) {
    var tip = document.getElementById('tip'); if (!tip) return;
    if (!row) { tip.hidden = true; return; }
    tip.innerHTML = '<div class="tip-n">' + U.esc(row.name) + '</div><div class="tip-s">' + RBX.icons.forRow(row, 11) + '<span>' + U.esc(RBX.hooks.tooltip(row)) + '</span></div>';
    tip.hidden = false;
    var area = document.getElementById('mapArea').getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    var x = pt.x + 12, y = pt.y + 12;
    if (x + w > area.width - 8) x = pt.x - 12 - w;
    if (y + h > area.height - 8) y = pt.y - 12 - h;
    tip.style.transform = 'translate(' + Math.max(4, x) + 'px,' + Math.max(4, y) + 'px)';
  };

  // ------------------------------------------------------------------ selection ring + pulse
  var pulseRaf = null;
  L.select = function (row) {
    var m = L.map; if (!m) return;
    var s = m.getSource('sel'); if (!s) return;
    if (!row) { s.setData({ type: 'FeatureCollection', features: [] }); cancelAnimationFrame(pulseRaf); return; }
    s.setData({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [row.lon, row.lat] },
      properties: { kind: row.kind, sv: row.sv || 0, hr: row.hr || 0 } }] });
    L.pulse(row.kind);
  };
  L.pulse = function (kind, loop) {
    var m = L.map; cancelAnimationFrame(pulseRaf);
    if (!m || RBX.reduced) return;
    var id = 'sel-' + kind + '-pulse', t0 = performance.now(), period = loop ? 1800 : 1100, reps = loop ? Infinity : 2;
    var ring = function (a) { return kind === 'tam' ? tamRing(a) : R(SIZE[kind], a); };
    (function step(t) {
      var el = (t - t0) / period, n = Math.floor(el), k = el - n;
      if (n >= reps || !m.getLayer(id)) { if (m.getLayer(id)) m.setPaintProperty(id, 'circle-stroke-opacity', 0); return; }
      var e = 1 - Math.pow(1 - k, 3);
      m.setPaintProperty(id, 'circle-radius', ring(5 + 16 * e));
      m.setPaintProperty(id, 'circle-stroke-opacity', 0.55 * (1 - e));
      pulseRaf = requestAnimationFrame(step);
    })(t0);
  };
})();
