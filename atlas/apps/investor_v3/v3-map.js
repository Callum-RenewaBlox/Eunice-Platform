/* Investor Atlas v3 · map chrome and the PNG export band (design spec §8, §4.6, §11). Bundled after investor-v3.js
   and right before core/js/app.js; nothing in core/ or in the skin is edited, every change is a replaced property,
   a wrapper or an extra map layer:
   - the size key is a horizontal glass capsule whose discs are zoom-true (RBX.layers.radiusAt / tamScaleAt): SAM
     £1M / £4M / £9M plus the hollow "Awaiting BM figure" ring, Hydro 100 kW / 500 kW / 1.3 MW, TAM the five capacity
     bands in one row plus the dashed "Postcode district" ring;
   - while the panel is collapsed a small glass chip keeps the disclaimer and the model date on screen, and the
     scale bar and the size key restack above it;
   - the selected site gets a 2.5 px ring, a 2 px halo and a soft teal wash; hollow Hydro "Unverified" rings keep no
     shadow; the attribution folds to its (i) on desktop too; no annotation pencil;
   - the PNG export band carries the view kicker and "Confidential · investor use only · <as of> · Indicative; not
     investment advice." right-aligned, with the brand quarter-circle moved clear of the text; the export card's three
     figures match the panel (captions with their numbers, the TAM ≥ 10 MW figure, labels that fit their column).
   Inert unless <html data-skin="product" data-app="investor">. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, doc = document.documentElement;
  if (doc.getAttribute('data-skin') !== 'product' || doc.getAttribute('data-app') !== 'investor') return;
  var V3 = RBX.v3 = RBX.v3 || {};

  function cfg() { return RBX.config || {}; }
  var CAVEAT = 'Indicative; not investment advice.';
  /** { stamp: 'Model · 16 Jun 2026', caveat, line } for a view: investor-v3.js's helper, or the same rule on config band.asOf. */
  function asOf(view) {
    if (V3.asOf) return V3.asOf(view);
    var bc = (cfg().band || {}).asOf || {}, s = String(bc[view] || bc.sam || '');
    var stamp = s.split(' · Indicative')[0].replace(/\s*·\s*$/, '');
    return { stamp: stamp, caveat: CAVEAT, line: stamp + ' · ' + CAVEAT };
  }
  function confText() {
    // the confidentiality mark never carries the caveat itself (it follows once, from asOf)
    return String(cfg().confidential || 'Confidential · investor use only').split(' · Indicative')[0];
  }
  function mapView() { var v = RBX.state.view; return v === 'ppa' ? RBX.state.lastPeaker || 'sam' : v; }
  var INFO = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.1"/></svg>';

  // ------------------------------------------------------------------ size key: one glass capsule, zoom-true discs (§8.1)
  var Sk = RBX.sizekey;
  var SK_TITLE = { sam: 'Contract value', hydro: 'Stranded capacity', tam: 'Capacity' };
  var TAM_BANDS = ['<250 kW', '<1 MW', '<5 MW', '<20 MW', '20 MW+'];
  /** One key item: an SVG disc drawn 1:1 at radius r (the stroke stays inside the box), then its label. */
  function item(r, label, circleAttr) {
    var b = r + 1.5, s = (2 * b).toFixed(1);
    return '<span class="sk-i"><svg width="' + s + '" height="' + s + '" viewBox="' + (-b).toFixed(1) + ' ' + (-b).toFixed(1) + ' ' + s + ' ' + s + '" aria-hidden="true">' +
      '<circle r="' + r.toFixed(1) + '"' + (circleAttr || '') + '/></svg>' + U.esc(label) + '</span>';
  }
  function hasAwaiting() {
    return (RBX.data.rows.sam || []).some(function (r) { return r.pr === 0; });
  }
  V3.sizeKeyHtml = function (view, z) {
    var vc = (cfg().views || {})[view] || {}, key = vc.sizeKey;
    if (!key) return '';
    var out = [], title = key.label || SK_TITLE[view] || key.title || '';
    if (view === 'tam') {
      var k = RBX.layers.tamScaleAt(z), D = RBX.icons.BAND_D || [7, 9.5, 12.5, 17, 23];
      D.forEach(function (d, i) { out.push(item(d * k / 2, TAM_BANDS[i] || '', ' class="band"')); });
      out.push('<span class="sk-div" aria-hidden="true"></span>');
      out.push(item(4.6, 'Postcode district', ' class="band dash"'));
    } else {
      (key.values || []).forEach(function (v) {
        var r = RBX.layers.radiusAt(view, z, Math.min(1.2, RBX.hooks.sizeValue(view, v)));
        out.push(item(r, RBX.hooks.sizeLabel(view, v)));
      });
      var aw = view === 'sam' ? ((cfg().legend || {}).sam || {}).awaiting : '';
      if (aw && hasAwaiting()) {
        out.push('<span class="sk-div" aria-hidden="true"></span>');
        out.push(item(4.6, aw, ' class="hollow"'));
      }
    }
    return '<span class="sizekey-t">' + U.esc(title) + '</span>' + out.join('');
  };
  if (Sk) {
    Sk.render = function () {
      var el = document.getElementById('sizekey'); if (!el) return;
      var view = RBX.state.view;
      var html = RBX.map && view !== 'ppa' ? V3.sizeKeyHtml(view, RBX.map.getZoom()) : '';
      el.classList.add('v3-sk');
      el.setAttribute('data-sk', view);
      if (el.innerHTML !== html) el.innerHTML = html;          // re-rendered on every zoom frame: touch the DOM only on change
      if (Sk.clearLabels) Sk.clearLabels();
    };
  }

  // ------------------------------------------------------------------ disclaimer chip while the panel is collapsed (§4.6)
  function discEl() {
    var el = document.getElementById('v3Disc');
    if (el) return el;
    var area = document.getElementById('mapArea'); if (!area) return null;
    el = document.createElement('div');
    el.id = 'v3Disc'; el.className = 'v3-disc'; el.setAttribute('role', 'note');
    var sk = document.getElementById('sizekey');
    if (sk && sk.parentNode === area) sk.insertAdjacentElement('afterend', el); else area.appendChild(el);
    return el;
  }
  V3.syncDisc = function () {
    var el = discEl(); if (!el) return;
    var a = asOf(mapView());
    var html = INFO + '<b>' + U.esc(String(a.caveat).replace(/\.\s*$/, '')) + '</b><span class="d" aria-hidden="true"> · </span><span>' + U.esc(String(a.stamp).replace(' · ', ' ')) + '</span>';
    if (el.innerHTML !== html) el.innerHTML = html;
    el.setAttribute('aria-label', a.caveat + ' ' + a.stamp.replace(' · ', ' '));
  };
  discEl();
  RBX.bus.on('view', V3.syncDisc);
  RBX.bus.on('ready', V3.syncDisc);
  if (RBX.rail && RBX.rail.render) {
    var railRender0 = RBX.rail.render;
    RBX.rail.render = function () { var r = railRender0.apply(this, arguments); V3.syncDisc(); return r; };
  }
  // the key moves with the panel; the sea labels it hides depend on where it sits
  if (RBX.rail && RBX.rail.setCollapsed) {
    var coll0 = RBX.rail.setCollapsed;
    RBX.rail.setCollapsed = function () {
      var r = coll0.apply(this, arguments);
      V3.syncDisc();
      if (Sk && Sk.clearLabels) setTimeout(Sk.clearLabels, 320);
      return r;
    };
  }

  // ------------------------------------------------------------------ selected site: ring, halo and a soft wash (§8.2)
  var SEL_WASH = { paper: 'rgba(21,96,130,0.14)', night: 'rgba(131,203,235,0.16)' };
  var SEL_HALO = { paper: 'rgba(255,255,255,0.9)', night: 'rgba(7,18,26,0.85)' };
  var KINDS = ['sam', 'hydro', 'tam'];
  function selRadius(kind, add) {
    var L = RBX.layers;
    if (kind !== 'tam') return L.R(L.SIZE[kind], add);
    // the TAM ring follows the glyph scale (the same stops as core layers.js tamRing)
    var e = ['interpolate', ['exponential', 1.5], ['zoom']];
    [4, 6, 8, 11, 14].forEach(function (z) { e.push(z, ['+', add, ['*', L.tamScaleAt(z), ['get', 'hr']]]); });
    return e;
  }
  function selTheme() {
    var m = RBX.map; if (!m) return;
    var th = RBX.state.theme === 'night' ? 'night' : 'paper';
    KINDS.forEach(function (k) {
      try {
        if (m.getLayer('v3-sel-' + k + '-wash')) m.setPaintProperty('v3-sel-' + k + '-wash', 'circle-stroke-color', SEL_WASH[th]);
        if (m.getLayer('v3-sel-' + k + '-halo')) m.setPaintProperty('v3-sel-' + k + '-halo', 'circle-stroke-color', SEL_HALO[th]);
      } catch (e) { /* style rebuilt */ }
    });
  }
  function selLayers(map) {
    if (!RBX.layers || !RBX.layers.R || !map.getSource('sel')) return;
    var th = RBX.state.theme === 'night' ? 'night' : 'paper';
    KINDS.forEach(function (k) {
      var ring = 'sel-' + k; if (!map.getLayer(ring)) return;
      var f = ['==', ['get', 'kind'], k];
      try {
        // ring 2.5 px (R + 4 … R + 6.5), then a 2 px halo and a 9 px wash outside it, both drawn under the ring
        map.setPaintProperty(ring, 'circle-stroke-width', 2.5);
        if (map.getLayer(ring + '-halo')) map.setPaintProperty(ring + '-halo', 'circle-stroke-opacity', 0);
        if (!map.getLayer('v3-' + ring + '-wash')) {
          map.addLayer({ id: 'v3-' + ring + '-wash', type: 'circle', source: 'sel', filter: f, paint: {
            'circle-radius': selRadius(k, 6.5), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 9, 'circle-stroke-color': SEL_WASH[th] } }, ring);
        }
        if (!map.getLayer('v3-' + ring + '-halo')) {
          map.addLayer({ id: 'v3-' + ring + '-halo', type: 'circle', source: 'sel', filter: f, paint: {
            'circle-radius': selRadius(k, 6.5), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 2, 'circle-stroke-color': SEL_HALO[th] } }, ring);
        }
      } catch (e) { /* the core ring keeps working without the extra layers */ }
    });
  }
  RBX.bus.on('mapready', function (map) {
    selLayers(map);
    map.on('styledata', function () { if (RBX.layers.ready && !map.getLayer('v3-sel-sam-wash')) selLayers(map); });
  });
  RBX.bus.on('theme', function () { setTimeout(selTheme, 0); });

  // hollow rings stay hollow: investor-v3.js keeps the SAM shadow off the "Awaiting BM figure" rings; the Hydro
  // "Unverified" rings (c = 3) are hollow too, so their soft shadow would read as a grey fill
  if (RBX.skin && RBX.skin.syncShadows) {
    var shadows0 = RBX.skin.syncShadows;
    RBX.skin.syncShadows = function () {
      shadows0.apply(this, arguments);
      var m = RBX.map;
      if (!m || !m.getLayer || !m.getLayer('hydro-shadow')) return;
      try { m.setFilter('hydro-shadow', ['all', RBX.filters.expr('hydro'), ['!=', ['get', 'c'], 3]]); } catch (e) { /* style rebuilt */ }
    };
  }

  // ------------------------------------------------------------------ attribution: the compact (i) on desktop too (§8.2)
  RBX.bus.on('ready', function () {
    if (U.isMobile()) return;
    var at = document.querySelector('.maplibregl-ctrl-attrib.maplibregl-compact');
    if (at) at.classList.remove('maplibregl-compact-show');
  });

  // ------------------------------------------------------------------ PNG export band (§11)
  // The skin draws the teal band, the sky rule, the wordmark, "no Watt wasted", the divider and the product name (it
  // is called with an empty kicker). Its quarter-circle would sit behind the right-hand text, so it is painted over
  // and redrawn at the far right; then two right-aligned lines: the kicker, and the confidentiality mark with the
  // as-of stamp and the disclaimer (which appears exactly once).
  var BAND = '#156082', SKY = '#83CBEB';
  V3.exportLines = function (view, vc) {
    var a = asOf(view), conf = confText(), rest = ' · ' + a.line;
    return { kicker: String((vc && vc.kicker) || '').toUpperCase(), conf: conf, rest: rest, text: conf + rest };
  };
  if (RBX.brand && RBX.brand.exportBand) {
    var band0 = RBX.brand.exportBand;
    RBX.brand.exportBand = function (g, o) {
      var vc = o.vc || {};
      band0.call(this, g, Object.assign({}, o, { vc: Object.assign({}, vc, { kicker: '' }) }));
      var W = o.W, TOP = o.TOP, UI = o.UI, xr = W - 96, ln = V3.exportLines(mapView(), vc);
      g.save();
      g.beginPath(); g.rect(0, 0, W, TOP); g.clip();
      // paint over the skin's arc (centre W − 70, TOP + 30, r 78: x W − 148 … W − 70), keeping the sky rule
      g.fillStyle = BAND; g.fillRect(W - 152, 0, 152, TOP - 3);
      g.fillStyle = 'rgba(131,203,235,.22)'; g.beginPath(); g.arc(W, TOP + 8, 64, 0, Math.PI * 2); g.fill();
      g.fillStyle = SKY; g.fillRect(W - 152, TOP - 3, 152, 3);
      g.textBaseline = 'alphabetic'; g.textAlign = 'left';
      var ls = 'letterSpacing' in g;
      // line 1: the kicker
      if (ls) g.letterSpacing = '2px';
      g.font = '600 11px ' + UI; g.fillStyle = '#E3F3FB';
      if (ln.kicker) { var kw = g.measureText(ln.kicker).width - (ls ? 2 : 0); g.fillText(ln.kicker, xr - kw, 29); }
      // line 2: Confidential · investor use only · Model · 16 Jun 2026 · Indicative; not investment advice.
      if (ls) g.letterSpacing = '0px';
      g.font = '600 11px ' + UI; var w1 = g.measureText(ln.conf).width;
      g.font = '400 11px ' + UI; var w2 = g.measureText(ln.rest).width;
      var x0 = xr - w1 - w2;
      g.font = '600 11px ' + UI; g.fillStyle = '#FFFFFF'; g.fillText(ln.conf, x0, 47);
      g.font = '400 11px ' + UI; g.fillStyle = 'rgba(255,255,255,.86)'; g.fillText(ln.rest, x0 + w1, 47);
      g.restore();
    };
  }

  // ------------------------------------------------------------------ PNG export card: the same figures as the panel (§11)
  // core/js/export.js draws views[v].kpis.slice(0, 3) into three 116 px columns of the editorial card, reading each
  // cell's metric over the sites shown and templating its caption with {known} only. For the PNG the three cells are
  // resolved here, for the duration of the composite: captions carry their numbers ("of 129"), the TAM "of it from
  // sites ≥ 10 MW" cell shows that TCV Potential (not the all-sizes total again), and a label that would run into the
  // next column uses its short form (a filtered view keeps its "shown" wording, as on the page).
  var K = RBX.kpi, E = RBX.exporter, I = RBX.inv;
  var PNG_SHORT = {
    sam: [['TCV · Year 5', 'TCV shown · Year 5'], ['With treasury'], ['Priced sites']],
    hydro: [['TCV · Year 5', 'TCV shown · Year 5'], ['With treasury'], ['Sites']],
    tam: [['TCV potential', 'TCV potential shown'], ['Sites ≥ 10 MW'], ['Sites']]
  };
  function bigRows(rows) { return rows.filter(function (r) { return r.big && r.bt > 0; }); }
  if (K && K.metrics && I && I.tcvPot) {
    K.metrics.v3PotBig = function (rows) { var b = bigRows(rows); return { v: b.length ? I.tcvPot(b) : 0, d: 0, f: U.abbr }; };
  }
  V3.exportKpis = function (view, kpis) {
    var rows = RBX.filters.active(view), all = RBX.data.rows[view] || [], filt = RBX.filters.anyHidden ? RBX.filters.anyHidden(view) : false;
    var g = document.createElement('canvas').getContext('2d'), UI = getComputedStyle(doc).getPropertyValue('--font-ui').trim() || 'sans-serif';
    g.font = '600 9.5px ' + UI;
    var colW = (392 - 44) / 3, adOnly = (RBX.state.hidden.scale || new Set()).has(1), nBig = bigRows(rows).length;
    var list = (kpis || []).filter(function (k) { return !(k.role === 'sub' && k.metric === 'tcvPot' && !nBig); }).slice(0, 3);
    return list.map(function (k, i) {
      var o = Object.assign({}, k), fits = function (s) { return s && g.measureText(String(s).toUpperCase()).width <= colW - (i ? 12 : 0) - 8; };
      var sh = ((PNG_SHORT[view] || [])[(kpis || []).indexOf(k)] || []), useF = i === 0 && filt && k.labelFiltered;
      var label = useF ? k.labelFiltered : k.label, short = useF ? sh[1] || sh[0] : sh[0];
      o.label = [k.pngLabel, label, short, k.labelShort].filter(fits)[0] || short || label;
      if (k.role === 'sub' && k.metric === 'tcvPot') {
        o.metric = 'v3PotBig';
        o.caption = 'of it, ' + U.int(nBig) + (nBig === 1 ? ' site' : ' sites');
      } else if (k.metric === 'tcvPot' && adOnly) {
        o.caption = 'AD-scale only';
      } else {
        var m = (K.metrics[k.metric] || K.metrics.count)(rows);
        o.caption = U.template(k.caption || '', { known: U.int(m.known), n: U.int(rows.length), total: U.int(all.length) });
      }
      return o;
    });
  };
  if (E && E.composite) {
    var comp0 = E.composite;
    E.composite = function () {
      var vc = (cfg().views || {})[mapView()], saved = vc && vc.kpis;
      if (saved) { try { vc.kpis = V3.exportKpis(mapView(), saved); } catch (e) { vc.kpis = saved; } }
      try { return comp0.apply(this, arguments); } finally { if (saved) vc.kpis = saved; }
    };
  }
})();
