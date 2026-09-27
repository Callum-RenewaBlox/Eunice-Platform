/* RBX.notes: editorial map annotations (spec 16.3, client P1). Every figure is computed at runtime from the data.
   Each view lists note ids in config.views[v].notes ([{id, placements?}]); the definitions below turn data into
   {anchor, ring?, lead, html}. Placement tries each candidate in turn and rejects one that intersects the rail,
   sheet or map controls, sits on more than 3 rendered features, or covers a basemap label. Re-scored on moveend
   and idle. Hidden while a card is open, above z 8.2, when the map area is narrower than 900 px, on mobile, in
   Present mode, or when switched off with "✎ Notes". */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var N = RBX.notes = { on: true, placed: {} };
  var WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
  function word(n) { return n <= 10 ? WORDS[n] : U.int(n); }
  function cap1(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function b(s) { return '<b class="nf">' + U.esc(s) + '</b>'; }
  function mwTxt(kw) { var v = kw / 1000; return (Math.abs(v - Math.round(v)) < 0.05 && v >= 10 ? U.int(v) : U.num(v, 1)) + ' MW'; }
  function centroid(rows) { return [U.sum(rows, function (r) { return r.lon; }) / rows.length, U.sum(rows, function (r) { return r.lat; }) / rows.length]; }
  function spreadKm(c, rows, q) {
    var d = rows.map(function (r) { return U.km(c, [r.lon, r.lat]); }).sort(function (a, b) { return a - b; });
    return d[Math.min(d.length - 1, Math.floor((d.length - 1) * (q == null ? 1 : q)))];
  }
  /** Short place-like name for a big TAM site: a one-word parenthetical, else the first word. */
  function shortName(n) {
    var m = String(n).match(/\(([A-Z][a-z]+)\)/);
    return m ? m[1] : String(n).split(/[\s,(]+/)[0];
  }
  function highlands(r) { return r.lat >= 56.4 && r.lon <= -3.3; }

  /** Note definitions: id → (rows of the view) → {rows, anchor, ringKm?, lead, html} | null. */
  N.defs = {
    sam: {
      t1: function (rows) {
        var t1 = rows.filter(function (r) { return r.t === 1; }); if (!t1.length) return null;
        var c = centroid(t1), se = t1.every(function (r) { return r.lon > -1.2 && r.lon < 1.6 && r.lat > 51.0 && r.lat < 51.8; });
        var n = t1.length, html = se
          ? (n === 1 ? 'The only Tier 1 site sits' : cap1(n === 2 ? 'both' : 'all ' + word(n)) + ' Tier 1 sites sit') + ' in the London–Kent corner, where Balancing-Mechanism offers are called most often.'
          : cap1(word(n)) + ' Tier 1 sites sit within ' + U.int(spreadKm(c, t1)) + ' km of each other, where Balancing-Mechanism offers are called most often.';
        return { rows: t1, anchor: c, ringKm: Math.max(20, spreadKm(c, t1) + 14), lead: 'Tier 1', html: html };
      },
      largest: function (rows) {
        var m = rows.slice().sort(function (a, b) { return (b.kw || 0) - (a.kw || 0); })[0]; if (!m) return null;
        return { rows: [m], anchor: [m.lon, m.lat], lead: 'Largest site',
          html: U.esc(m.name) + (m.town ? ', ' + U.esc(m.town) : '') + ': ' + b(mwTxt(m.kw)) + ', Tier ' + m.t + '.' };
      }
    },
    tam: {
      thames: function (rows) {
        var top = rows.slice().sort(function (a, b) { return (b.kw || 0) - (a.kw || 0); }).slice(0, 5);
        var est = top.filter(function (r) { return r.lon > 0.15 && r.lon < 0.9 && r.lat > 51.25 && r.lat < 51.6; });
        if (est.length < 2) return null;
        var parts = est.map(function (r) { return U.esc(shortName(r.name)) + ' (' + b(mwTxt(r.kw)) + ')'; });
        var list = parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1];
        var c = centroid(est);
        return { rows: est, anchor: c, ringKm: spreadKm(c, est) + 10, lead: 'Thames Estuary',
          html: list + ' are ' + word(est.length) + ' of the ' + word(top.length) + ' largest sites.' };
      },
      scotland: function (rows) {
        var sc = rows.filter(function (r) { return !r.bt; }); if (!sc.length) return null;
        var kw = U.sum(sc, function (r) { return r.kw; });
        return { rows: sc, anchor: centroid(sc), lead: 'Scotland',
          html: b(U.int(sc.length)) + ' sites and ' + b(U.int(kw / 1000) + ' MW') + ' sit outside the BM tier model, with no BM revenue assumed.' };
      }
    },
    hydro: {
      highlands: function (rows) {
        var h = rows.filter(highlands); if (!h.length) return null;
        var all = RBX.data.rows.hydro, kw = U.sum(h, function (r) { return r.kw; }), tot = U.sum(all, function (r) { return r.kw; }), c = centroid(h);
        return { rows: h, anchor: c, ringKm: spreadKm(c, h, 0.8), lead: 'The Highlands',
          html: b(U.int(h.length)) + ' of the ' + U.int(all.length) + ' sites, and ' + b(U.num(kw / 1000, 1)) + ' of the ' + b(U.num(tot / 1000, 1) + ' MW') + ' stranded, are in the Highlands.' };
      },
      largest: function (rows) {
        var m = rows.slice().sort(function (a, b) { return (b.kw || 0) - (a.kw || 0); })[0]; if (!m) return null;
        return { rows: [m], anchor: [m.lon, m.lat], lead: 'Largest', html: U.esc(m.name) + ': ' + b(U.num(m.kw / 1000, 1) + ' MW') + ' that cannot reach the grid.' };
      }
    }
  };

  // ------------------------------------------------------------------ DOM
  var host, svg, btn;
  function key() { return ((RBX.config && RBX.config.storageKey) || 'rbx-atlas') + ':notes'; }
  N.init = function () {
    var area = document.getElementById('mapArea'); if (!area) return;
    host = document.createElement('div'); host.id = 'notes'; host.className = 'notes'; host.setAttribute('aria-hidden', 'true');
    host.innerHTML = '<svg class="notes-svg"></svg>';
    svg = host.firstChild;
    area.insertBefore(host, document.getElementById('rail'));
    btn = document.createElement('button');
    btn.type = 'button'; btn.id = 'notesBtn'; btn.className = 'notes-btn';
    btn.title = 'Show or hide the map annotations';
    btn.innerHTML = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 16l1-4 8.5-8.5a2.1 2.1 0 0 1 3 3L8 15z"/><path d="M12 5l3 3"/></svg><span>Notes</span>';
    area.appendChild(btn);
    N.on = U.store(key()) !== '0';
    btn.setAttribute('aria-pressed', String(N.on));
    var rc = document.getElementById('railCollapse');
    if (rc) rc.addEventListener('click', function () { setTimeout(function () { N.place(true); }, 380); });
    btn.addEventListener('click', function () { N.on = !N.on; btn.setAttribute('aria-pressed', String(N.on)); U.store(key(), N.on ? '1' : '0'); N.build(); });
  };

  function list(view) { return (((RBX.config.views || {})[view] || {}).notes) || []; }
  function hidden() {
    var S = RBX.state, m = RBX.map;
    if (!m || !N.on || S.view === 'ppa' || U.isMobile()) return true;
    if (RBX.sheet.isOpen()) return true;
    if (RBX.present && RBX.present.active && RBX.present.active()) return true;
    if (m.getZoom() > 8.2) return true;
    return document.getElementById('mapArea').clientWidth < 900;
  }

  /** Build the notes of the current view from the active rows, then place them. */
  N.build = function () {
    if (!host) return;
    var view = RBX.state.view, defs = N.defs[view] || {};
    var showBtn = !!(RBX.map && list(view).length && !U.isMobile() && view !== 'ppa');
    btn.hidden = !showBtn;
    U.$$('.note', host).forEach(function (n) { n.remove(); });
    N.items = [];
    if (!showBtn) { svg.innerHTML = ''; return; }
    var rows = RBX.filters.active(view);
    list(view).forEach(function (spec) {
      var f = defs[spec.id]; if (!f) return;
      var d = f(rows); if (!d) return;
      var el = document.createElement('div');
      el.className = 'note'; el.setAttribute('data-note', spec.id);
      el.innerHTML = '<span class="note-lead">' + U.esc(d.lead) + '</span>' + d.html;
      host.appendChild(el);
      N.items.push({ id: spec.id, d: d, el: el, placements: spec.placements, pick: null });
    });
    N.place(true);
  };

  function areaRect() { return document.getElementById('mapArea').getBoundingClientRect(); }
  function obstacles() {
    var a = areaRect(), out = [];
    ['rail', 'sheet', 'mapCtl', 'sizekey', 'notesBtn', 'offlinePill', 'tip'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el || el.hidden || el.offsetParent === null || (id === 'tip')) return;
      var r = el.getBoundingClientRect(); if (!r.width) return;
      out.push({ l: r.left - a.left - 10, t: r.top - a.top - 10, r: r.right - a.left + 10, b: r.bottom - a.top + 10 });
    });
    U.$$('.maplibregl-ctrl-bottom-left,.maplibregl-ctrl-bottom-right').forEach(function (el) {
      var r = el.getBoundingClientRect(); if (r.width) out.push({ l: r.left - a.left - 6, t: r.top - a.top - 6, r: r.right - a.left + 6, b: r.bottom - a.top + 6 });
    });
    return out;
  }
  function hit(bx, o) { return !(bx.r < o.l || bx.l > o.r || bx.b < o.t || bx.t > o.b); }
  /** Basemap label layers to test with queryRenderedFeatures. City labels are excluded (their data-driven icon
      offset makes MapLibre log type warnings when queried) and tested by projection instead (cityHits). */
  function labelLayers(m) {
    try { return m.getStyle().layers.filter(function (l) { return l.type === 'symbol' && !/^rbx-city-labels/.test(l.id) && ((l.metadata || {})['rbx:group'] === 'labels' || /label|place/.test(l.id)) && m.getLayoutProperty(l.id, 'visibility') !== 'none'; }).map(function (l) { return l.id; }); }
    catch (e) { return []; }
  }
  var TIER_MINZ = { 0: 4.6, 1: 3.5, 2: 5.3, 3: 6.2, 4: 7.4, 5: 8.4 };
  function cityHits(m, bx) {
    // only the cities the map actually draws (continental labels are filtered out in RBX.mapctl)
    var list = RBX.mapctl.cities || (window.RBXBasemap && window.RBXBasemap.cities) || [], z = m.getZoom(), n = 0;
    for (var i = 0; i < list.length; i++) {
      var c = list[i]; if (z < (TIER_MINZ[c[3]] != null ? TIER_MINZ[c[3]] : 6)) continue;
      var p = m.project([c[1], c[2]]), w = String(c[0]).length * 7.4 + 14;
      var l = c[4] === 'l' ? p.x - w : p.x - 6, r = c[4] === 'l' ? p.x + 6 : p.x + w;
      if (!(r < bx.l || l > bx.r || p.y + 9 < bx.t || p.y - 9 > bx.b)) n++;
    }
    return n;
  }
  function ringPx(m, d, p) {
    if (!d.ringKm) return 0;
    var dLon = d.ringKm / (111.32 * Math.cos(d.anchor[1] * Math.PI / 180));
    var q = m.project([d.anchor[0] + dLon, d.anchor[1]]);
    return Math.abs(q.x - p.x);
  }
  /** Candidate leader ends around the anchor (sea side first is not assumed: every direction is tried). */
  function candidates(it, rr) {
    // explicit placements (config, e.g. sea-side for the Thames Estuary) are tried first, then every direction
    var out = (it.placements || []).slice();
    [rr + 34, rr + 96].forEach(function (d) {
      [-35, 35, 145, 215, -70, 70, 110, 250, 0, 180].forEach(function (deg) {
        var a = deg * Math.PI / 180; out.push([Math.round(Math.cos(a) * d), Math.round(Math.sin(a) * d)]);
      });
    });
    return out;
  }
  function boxFor(p, c, w, h) {
    var right = c[0] >= 0, up = c[1] < 0;
    var ex = p.x + c[0], ey = p.y + c[1];
    var l = right ? ex + 6 : ex - 6 - w, t = up ? ey - h + 10 : ey - 8;
    return { l: l, t: t, r: l + w, b: t + h, ex: ex, ey: ey, right: right };
  }

  /** Test and place every note. full=false only re-projects the current picks (during camera moves). */
  N.place = function (full) {
    if (!host) return;
    var m = RBX.map;
    var hide = hidden();
    host.classList.toggle('hide', hide);
    if (hide || !N.items || !N.items.length) { svg.innerHTML = ''; return; }
    var a = areaRect(), W = a.width, H = a.height, obs = full ? obstacles() : null, lbl = full ? labelLayers(m) : null;
    var core = RBX.layers.CORE[RBX.state.view], taken = [], s = '';
    N.items.forEach(function (it) {
      var el = it.el, w = el.offsetWidth, h = el.offsetHeight, p = m.project(it.d.anchor), rr = ringPx(m, it.d, p);
      var best = null;
      if (full) {
        var cs = candidates(it, rr), bestN = 99;
        for (var i = 0; i < cs.length && bestN > 0; i++) {
          var bx = boxFor(p, cs[i], w, h);
          if (bx.l < 8 || bx.t < 8 || bx.r > W - 8 || bx.b > H - 8) continue;
          if (obs.some(function (o) { return hit(bx, o); }) || taken.some(function (o) { return hit(bx, o); })) continue;
          var q = [[bx.l, bx.t], [bx.r, bx.b]];
          var nf = core && m.getLayer(core) ? m.queryRenderedFeatures(q, { layers: [core] }).length : 0;
          if (nf > 3 || nf >= bestN) continue;
          var nl = (lbl.length ? m.queryRenderedFeatures(q, { layers: lbl }).length : 0) + cityHits(m, bx);
          if (nl > 0) continue;
          best = cs[i]; bestN = nf;          // first clear placement wins; otherwise the least covered (≤ 3)
        }
        it.pick = best;
      } else best = it.pick;
      if (!best) { el.style.opacity = 0; el.style.transform = 'translate(-9999px,0)'; return; }
      var b2 = boxFor(p, best, w, h);
      if (!full && (b2.l < 0 || b2.t < 0 || b2.r > W || b2.b > H)) { el.style.opacity = 0; return; }
      taken.push({ l: b2.l - 6, t: b2.t - 6, r: b2.r + 6, b: b2.b + 6 });
      el.classList.toggle('r', !b2.right);
      el.style.opacity = 1;
      el.style.transform = 'translate(' + Math.round(b2.l) + 'px,' + Math.round(b2.t) + 'px)';
      // leader: from the ring edge (or a dot on the site) to the note, with a short horizontal tail
      var ang = Math.atan2(b2.ey - p.y, b2.ex - p.x), sx = p.x + Math.cos(ang) * (rr || 3), sy = p.y + Math.sin(ang) * (rr || 3);
      var tail = b2.right ? b2.ex + 4 : b2.ex - 4;
      if (rr) s += '<circle class="n-ring" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + rr.toFixed(1) + '"/>';
      else s += '<circle class="n-dot" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="2.2"/>';
      s += '<path class="n-ld" d="M' + sx.toFixed(1) + ',' + sy.toFixed(1) + 'L' + b2.ex.toFixed(1) + ',' + b2.ey.toFixed(1) + 'L' + tail.toFixed(1) + ',' + b2.ey.toFixed(1) + '"/>';
    });
    svg.innerHTML = s;
  };

  var rescore = U.debounce(function () { N.place(true); }, 60);
  RBX.bus.on('mapready', function (map) {
    N.init();
    map.on('move', U.rafThrottle(function () { if (N.items && N.items.length) N.place(false); }));
    map.on('moveend', rescore);
    map.once('idle', function () { N.build(); });
  });
  // re-place deterministically once the map has settled after a view change or a theme switch
  RBX.bus.on('view', function () { if (host) { N.build(); if (RBX.map) RBX.map.once('idle', function () { N.place(true); }); } });
  RBX.bus.on('filter', function (p) { if (host && !(p && p.light)) N.build(); });
  RBX.bus.on('select', function () { if (host) setTimeout(function () { N.place(true); }, 30); });
  RBX.bus.on('theme', function () { if (host && RBX.map) { RBX.map.once('idle', rescore); setTimeout(rescore, 600); } });
  window.addEventListener('resize', function () { if (host) rescore(); });
})();
