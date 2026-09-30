/* Investor Atlas v3: adapts the investor modules (core/js/investor/*) to the shared product skin in the RenewaBlox
   brand. Bundled after them and right before core/js/app.js. Nothing in core/ or in the investor modules is
   edited, so the Investor Atlas v2 page is unchanged; every change is a replaced property or a wrapper:
   - the KPI band, its GB power strip and the footer bar are not rendered: the headline figures move into the
     skin's brand KPI card in the panel (config views[v].kpis, formatted by the investor band metrics);
   - hollow "Awaiting BM figure" rings keep no shadow; Present mode frames the map clear of the floating header.
   Inert unless <html data-skin="product" data-app="investor"> (apps/investor_v3/template.html). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, doc = document.documentElement;
  if (doc.getAttribute('data-skin') !== 'product' || doc.getAttribute('data-app') !== 'investor') return;
  var B = RBX.band, K = RBX.kpi, I = RBX.inv;
  var V3 = RBX.v3 = {};
  var INFO = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.1"/></svg>';

  // ------------------------------------------------------------------ shared helpers (also used by v3-sheet/present/map.js)
  /** Money in the v3 grammar: full-size £ on the baseline, small magnitude letter (£221.9M, £7.17bn, £595k). */
  V3.money = function (v) {
    var s = typeof v === 'number' ? U.abbr(v) : String(v == null ? '' : v);
    var m = /^(-?£?[\d.,]+)\s*(k|M|bn)?$/.exec(s);
    return m ? '<span class="money">' + U.esc(m[1]) + (m[2] ? '<span class="mag">' + m[2] + '</span>' : '') + '</span>' : U.esc(s);
  };
  /** The model / registers stamp and the disclaimer for a view (config band.asOf), always ending in the caveat. */
  V3.CAVEAT = 'Indicative; not investment advice.';
  V3.asOf = function (view) {
    var bc = (RBX.config.band || {}).asOf || {}, s = String(bc[view === 'tam' ? 'tam' : view === 'ppa' ? 'ppa' : view === 'hydro' ? 'hydro' : 'sam'] || '');
    var stamp = s.split(' · Indicative')[0].replace(/\s*·\s*$/, '');
    return { stamp: stamp, caveat: V3.CAVEAT, line: stamp + ' · ' + V3.CAVEAT };
  };

  // ------------------------------------------------------------------ no band, no market strip, no footer bar
  // band.js looks these up on RBX.band at call time; its popover, Scale control, Present button, drawer sections
  // and PPA chips keep working. With render a no-op, B.update returns before touching the DOM or the live region.
  if (B) {
    B.render = function () {};
    B.renderFoot = function () {};
    B.fitMkt = function () {};
  }

  // ------------------------------------------------------------------ KPI card: investor figures in the brand card
  // Each investor band metric becomes a KPI metric; the formatter comes along so the card prints £221.9M, 90.5 MW.
  if (B && B.metrics) {
    Object.keys(B.metrics).forEach(function (id) {
      if (K.metrics[id]) return;
      K.metrics[id] = function (rows) { var m = B.metrics[id](rows); return { v: m.v, d: 0, f: m.f }; };
    });
  }
  /** The TCV Potential caption carries the ≥ 10 MW caveat and the method button (#tcvInfo opens band.js's popover). */
  function potCaption(rows) {
    var btn = '<button type="button" class="band-i" id="tcvInfo" aria-haspopup="dialog" aria-expanded="false" aria-controls="tcvPop" aria-label="How TCV Potential is calculated">' + INFO + '</button>';
    var big = rows.filter(function (r) { return r.big && r.bt > 0; });
    if (!big.length) {
      var adOnly = (RBX.state.hidden.scale || new Set()).has(1);
      return '<span>' + (adOnly ? 'AD-scale only (&lt;10 MW)' : 'No sites ≥ 10 MW in view') + '</span>' + btn;
    }
    return '<span>' + U.esc(U.abbr(I.tcvPot(big))) + ' of it from ' + U.int(big.length) + ' sites ≥ 10 MW</span>' + btn;
  }
  var announce = U.debounce(function (msg) { var l = document.getElementById('live'); if (l) l.textContent = msg; }, 400);
  function kLabel(k) { return RBX.state.inView ? String(k.label).replace(/\bshown\b/i, 'in view') : k.label; }
  K.update = function (instant) {
    var view = RBX.state.view, vc = (RBX.config.views || {})[view] || {};
    if (!vc.kpis || view === 'ppa') return;
    var rows = K.rows(view), all = RBX.data.rows[view] || [], parts = [];
    vc.kpis.forEach(function (k, i) {
      var el = document.getElementById('kpi' + i), cap = document.getElementById('kpic' + i), lb = document.getElementById('kpil' + i);
      if (!el) return;
      var m = (K.metrics[k.metric] || K.metrics.count)(rows);
      var fmt = m.f ? function (x) { return m.f(x); } : function (x) { return U.num(x, m.d) + (k.unit ? '<small>' + U.esc(k.unit) + '</small>' : ''); };
      if (instant || RBX.reduced) { el.setAttribute('data-v', String(m.v)); el.innerHTML = fmt(m.v); } else U.countUp(el, m.v, fmt, 600);
      if (cap) {
        var focusInfo = document.activeElement && document.activeElement.id === 'tcvInfo';
        if (k.metric === 'tcvPot') cap.innerHTML = potCaption(rows);
        else cap.textContent = U.template(k.caption || '', { known: U.int(m.known), n: U.int(rows.length), total: U.int(all.length) });
        if (focusInfo) { var b = document.getElementById('tcvInfo'); if (b) b.focus({ preventScroll: true }); }
      }
      if (lb) lb.textContent = kLabel(k);
      parts.push(kLabel(k) + ' ' + fmt(m.v).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
    });
    if (!instant) announce((RBX.state.inView ? 'In view: ' : '') + parts.join(', '));
  };

  // (the PNG export band with the confidentiality marking and the disclaimer is drawn by v3-map.js)

  // ------------------------------------------------------------------ map: hollow "Awaiting BM figure" rings stay hollow
  if (RBX.skin && RBX.skin.syncShadows) {
    var sync0 = RBX.skin.syncShadows;
    RBX.skin.syncShadows = function () {
      sync0.apply(this, arguments);
      var m = RBX.map;
      if (!m || !m.getLayer || !m.getLayer('sam-shadow')) return;
      try { m.setFilter('sam-shadow', ['all', RBX.filters.expr('sam'), ['==', ['get', 'pr'], 1]]); } catch (e) { /* style rebuilt */ }
    };
  }

  // ------------------------------------------------------------------ Present: frame chapters clear of the floating header
  // present.js keeps its own padding (top 40 px); while a chapter moves the camera, top padding and the fly offset
  // also clear whatever part of the floating header stays on screen (V3.presentInset, 0 when it is hidden).
  var Pr = RBX.present, inGo = false;
  V3.presentInset = function () {
    var hdr = document.getElementById('hdr');
    if (!hdr || getComputedStyle(hdr).visibility === 'hidden' || +getComputedStyle(hdr).opacity === 0) return 0;
    return RBX.skin && RBX.skin.headerBottom ? RBX.skin.headerBottom() : 0;
  };
  if (Pr && Pr.go) {
    var go0 = Pr.go;
    Pr.go = function () {
      inGo = true;
      try { return go0.apply(this, arguments); } finally { inGo = false; }
    };
  }
  RBX.bus.on('mapready', function (map) {
    var fit0 = map.fitBounds, fly0 = map.flyTo;
    map.fitBounds = function (b, o) {
      var ins = inGo ? V3.presentInset() : 0;
      if (ins && o && o.padding && typeof o.padding === 'object') o = Object.assign({}, o, { padding: Object.assign({}, o.padding, { top: Math.max(o.padding.top || 0, ins + 24) }) });
      return fit0.call(this, b, o);
    };
    map.flyTo = function (o, e) {
      var ins = inGo ? V3.presentInset() : 0;
      if (ins && o) { var off = o.offset || [0, 0]; o = Object.assign({}, o, { offset: [off[0], off[1] + Math.round(ins / 2)] }); }
      return fly0.call(this, o, e);
    };
  });
})();
