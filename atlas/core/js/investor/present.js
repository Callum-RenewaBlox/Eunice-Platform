/* Investor build only. Present mode (spec 10.3): six chapters from ATLAS_CONFIG.story (apps/investor/story.json),
   stepped with ← → Space PageUp PageDown Home End, Esc exits and restores the prior view, filters, camera, theme
   and open card. Stats are computed from data at runtime. P1: autoplay (9 s per chapter) and 3D Highlands terrain. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, I = RBX.inv;
  var Pr = RBX.present = {};
  var on = false, idx = 0, prior = null, playing = false, timer = null, fsEntered = false, terrainOn = false;

  function story() { return (RBX.config && RBX.config.story) || { chapters: [] }; }
  function chapters() { return story().chapters || []; }

  // ------------------------------------------------------------------ stats, computed from data (never typed)
  function all(kind) { return RBX.data.rows[kind] || []; }
  function vis(kind) { return RBX.filters.active(kind); }
  function mw1(kw) { return U.num(kw / 1000, 1) + ' MW'; }
  function cps() {
    var by = {};
    all('sam').forEach(function (r) { if (r.off && r.off !== 'Generator is sole holder') by[r.off] = (by[r.off] || 0) + (r.kw || 0); });
    return Object.keys(by).map(function (k) { return [k, by[k]]; }).sort(function (a, b) { return b[1] - a[1]; });
  }
  function shortName(s) { return String(s).replace(/\s+(Customers|Energy Solutions|Energy|Commercial|Supply)\b.*$/i, '').replace(/\s+(Limited|Ltd|plc)\.?$/i, ''); }
  var STAT = {
    'tam.n': function () { return U.int(all('tam').length); },
    'tam.mw': function () { return U.int(U.sum(all('tam'), function (r) { return r.kw; }) / 1000) + ' MW'; },
    'tam.pot': function () { return U.abbr(I.tcvPot(all('tam'))); },
    'tam.big': function () { return U.abbr(I.tcvPot(all('tam').filter(function (r) { return r.big; }))); },
    'tam.bigN': function () { return U.int(all('tam').filter(function (r) { return r.big && r.bt > 0; }).length); },
    'sam.n': function () { return U.int(all('sam').length); },
    'sam.unpriced': function () { return U.int(all('sam').filter(function (r) { return !r.pr; }).length); },
    'sam.pricedOf': function () { return U.int(all('sam').filter(function (r) { return r.pr; }).length) + ' of ' + U.int(all('sam').length); },
    'sam.av': function () { return mw1(U.sum(all('sam'), function (r) { return r.pr ? r.av : 0; })); },
    'sam.tcv': function () { return U.abbr(U.sum(all('sam'), function (r) { return r.tcv; })); },
    'sam.tcvT': function () { return U.abbr(U.sum(all('sam'), function (r) { return r.tcvT; })); },
    'rev.t1avg': function () { return RBX.config.bmrev[1].a + 'p'; },
    'rev.t1top': function () { return RBX.config.bmrev[1].t + 'p'; },
    'rev.t1freq': function () { return String((RBX.config.bmfreq || {})[1] || '').replace(/ GB average$/, ''); },
    'hydro.n': function () { return U.int(all('hydro').length); },
    'hydro.mw': function () { return mw1(U.sum(all('hydro'), function (r) { return r.kw; })); },
    'hydro.tcv': function () { return U.abbr(U.sum(all('hydro'), function (r) { return r.tcv; })); },
    'hydro.tcvT': function () { return U.abbr(U.sum(all('hydro'), function (r) { return r.tcvT; })); },
    'ppa.fit': function () { return U.num(RBX.data.ppa.kpi.fit, 2) + 'p'; },
    'ppa.cal28': function () { return U.num(RBX.data.ppa.kpi.cal28, 2) + 'p'; },
    'ppa.fitCpi': function () { var p = RBX.data.ppa, cpi = p.cpi != null ? p.cpi : 0.03; return U.num(p.kpi.fit * Math.pow(1 + cpi, 2), 2) + 'p'; },
    'ppa.cp': function () { return U.int(cps().length); },
    'ppa.cp1': function () { var c = cps()[0]; return c ? mw1(c[1]) : '—'; },
    'ppa.cp2': function () { var c = cps()[1]; return c ? mw1(c[1]) : '—'; },
    'ppa.cp1name': function () { var c = cps()[0]; return c ? shortName(c[0]) : ''; },
    'ppa.cp2name': function () { var c = cps()[1]; return c ? shortName(c[0]) : ''; }
  };
  Pr.STAT = STAT;
  function fill(s) { return String(s || '').replace(/\{([a-zA-Z0-9.]+)\}/g, function (m, k) { return STAT[k] ? STAT[k]() : m; }); }
  /** "*phrase*" → lime italic, everything else escaped. */
  function title(s) { return U.esc(fill(s)).replace(/\*([^*]+)\*/g, '<em>$1</em>'); }

  // ------------------------------------------------------------------ camera helpers
  function pad() {
    var card = document.getElementById('presentCard'), w = card ? card.offsetWidth : 480;
    if (U.isMobile()) return { top: 20, bottom: (card ? card.offsetHeight : 330) + 24, left: 16, right: 16 };
    return { top: 40, bottom: 40, left: w + 60, right: 60 };
  }
  function offset() { var p = pad(); return [Math.round((p.left - p.right) / 2), Math.round((p.top - p.bottom) / 2)]; }
  function dur(ms) { return RBX.reduced ? 0 : ms; }
  function terrain(want) {
    var m = RBX.map; if (!m) return;
    try {
      if (want && !terrainOn) {
        if (!m.getSource('rbx-dem-3d')) {
          var src = (m.getStyle().sources || {})['rbx-dem'] || {};
          m.addSource('rbx-dem-3d', { type: 'raster-dem', tiles: src.tiles || ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], encoding: 'terrarium', tileSize: 256, maxzoom: 12 });
        }
        m.setTerrain({ source: 'rbx-dem-3d', exaggeration: 1.7 });
        terrainOn = true;
      } else if (!want && terrainOn) {
        m.setTerrain(null);
        terrainOn = false;
      }
    } catch (e) { terrainOn = false; }
  }
  function camera(c) {
    var m = RBX.map, cam = c.camera || {};
    if (!m) return;
    terrain(!!cam.terrain && !RBX.reduced);
    if (cam.fit) {
      var b = (RBX.hooks.viewBounds && RBX.hooks.viewBounds(cam.fit)) || RBX.mapctl.viewBounds(cam.fit);
      m.fitBounds(b, { padding: pad(), maxZoom: 7.2, pitch: 0, bearing: 0, duration: dur(2600), essential: true });
    } else if (cam.center) {
      var bearing = Math.max(-18, Math.min(18, cam.bearing || 0));
      m.flyTo({ center: cam.center, zoom: cam.zoom, pitch: terrainOn ? (cam.pitch || 0) : 0, bearing: terrainOn ? bearing : 0,
        offset: offset(), duration: dur(cam.terrain ? 3600 : 3000), essential: true });
    }
    RBX.mapctl.userMoved = true;
  }

  /** Scroll the PPA page itself (never the document) so a section sits just below its sticky filters bar. */
  function scrollPpa(name) {
    var pp = document.getElementById('ppa'), el = pp && pp.querySelector('[data-sec="' + name + '"]');
    if (!el) return;
    var bar = pp.querySelector('.ppa-filters'), top = el.getBoundingClientRect().top - pp.getBoundingClientRect().top + pp.scrollTop;
    var off = bar && bar.getBoundingClientRect().top - pp.getBoundingClientRect().top + pp.scrollTop < top ? bar.offsetHeight : 0;
    try { pp.scrollTo({ top: Math.max(0, top - off - 16), behavior: RBX.reduced ? 'auto' : 'smooth' }); } catch (e) { pp.scrollTop = Math.max(0, top - off - 16); }
  }
  /** Stat value → html, with a trailing unit set small ("34.5 MW", "7.64p"). */
  function statHtml(v) {
    var m = /^(.*?\d)(\s?)(MW|p)$/.exec(v);
    return m ? U.esc(m[1]) + '<small>' + U.esc(m[3]) + '</small>' : U.esc(v);
  }
  /** Chapter filters sit on an all-visible baseline: {set: [visible values]}. */
  function applyFilters(c) {
    var S = RBX.state, F = RBX.filters;
    Object.keys(S.hidden).forEach(function (k) { S.hidden[k].clear(); });
    Object.keys(S.kw).forEach(function (k) { S.kw[k] = null; });
    Object.keys(c.filters || {}).forEach(function (set) {
      var view = c.view, d = F.dimOf(view, set) || { values: [] }, keep = c.filters[set];
      d.values.forEach(function (v) { if (keep.indexOf(v) < 0) S.hidden[set].add(v); });
    });
    F.changed();
  }

  // ------------------------------------------------------------------ card
  function cardEl() {
    var el = document.getElementById('presentCard');
    if (!el) {
      el = document.createElement('section');
      el.id = 'presentCard'; el.className = 'present-card';
      el.setAttribute('role', 'region'); el.setAttribute('aria-label', 'Presentation'); el.setAttribute('aria-live', 'polite');
      document.getElementById('stage').appendChild(el);
      el.addEventListener('click', function (e) {
        var b = e.target.closest('[data-pc]'); if (!b) return;
        var a = b.getAttribute('data-pc');
        if (a === 'prev') Pr.go(idx - 1);
        else if (a === 'next') { if (idx >= chapters().length - 1) Pr.exit(); else Pr.go(idx + 1); }
        else if (a === 'play') Pr.play(!playing);
        else if (a === 'exit') Pr.exit();
        else Pr.go(+a);
      });
    }
    return el;
  }
  var ICON = {
    prev: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M12.5 4.5 7 10l5.5 5.5"/></svg>',
    next: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M7.5 4.5 13 10l-5.5 5.5"/></svg>'
  };
  function render() {
    var ch = chapters(), c = ch[idx], el = cardEl(), n = ch.length, last = idx === n - 1, ms = story().autoplayMs || 9000;
    el.hidden = false;
    el.setAttribute('data-view', c.view);
    el.innerHTML = '<div class="pc-top"><span class="pc-n">Chapter ' + (idx + 1) + ' / ' + n + '</span>' +
      '<button type="button" class="pc-exit" data-pc="exit">Exit · Esc</button></div>' +
      '<h2 class="pc-title">' + title(c.title) + '</h2>' +
      '<p class="pc-body">' + U.esc(fill(c.body)) + '</p>' +
      '<div class="pc-stats">' + (c.stats || []).map(function (s) {
        return '<div><b class="num">' + statHtml(STAT[s.expr] ? STAT[s.expr]() : '—') + '</b><span>' + U.esc(fill(s.label)) + '</span></div>';
      }).join('') + '</div>' +
      '<div class="pc-prog' + (playing ? ' playing' : '') + '" style="--pc-dur:' + ms + 'ms">' + ch.map(function (x, j) {
        return '<button type="button" data-pc="' + j + '" class="' + (j < idx ? 'done' : j === idx ? 'cur' : '') + '" aria-label="Chapter ' + (j + 1) + '"' + (j === idx ? ' aria-current="step"' : '') + '><span></span></button>';
      }).join('') + '</div>' +
      '<div class="pc-ctl"><button type="button" class="pc-btn" data-pc="prev" aria-label="Previous chapter"' + (idx === 0 ? ' disabled' : '') + '>' + ICON.prev + '</button>' +
      '<button type="button" class="pc-btn pri" data-pc="next">' + (last ? 'Finish' : 'Next') + ICON.next + '</button>' +
      (RBX.reduced ? '' : '<button type="button" class="pc-btn" data-pc="play" aria-pressed="' + playing + '">' + (playing ? '❚❚ Pause' : '▶ Play') + '</button>') +
      '<span class="pc-kb" aria-hidden="true">← → · Esc</span></div>';
  }

  // ------------------------------------------------------------------ public API
  Pr.active = function () { return on; };
  Pr.go = function (i) {
    var ch = chapters();
    if (!on || !ch.length) return;
    idx = Math.max(0, Math.min(ch.length - 1, i));
    var c = ch[idx];
    RBX.state.present = idx;
    clearTimeout(timer);
    applyFilters(c);
    if (c.view !== 'ppa') terrain(false);
    RBX.app.setView(c.view, { camera: false });
    render();
    if (c.view === 'ppa') {
      terrain(false);
      setTimeout(function () { scrollPpa(c.ppa || 'price'); }, 80);
    } else camera(c);
    if (playing) timer = setTimeout(function () { if (idx < ch.length - 1) Pr.go(idx + 1); else Pr.play(false); }, story().autoplayMs || 9000);
    RBX.state.writeHash();
  };
  Pr.play = function (p) { playing = !!p && !RBX.reduced; Pr.go(idx); };
  Pr.enter = function (start) {
    if (on || !chapters().length) return;
    var S = RBX.state, m = RBX.map;
    prior = { view: S.view, filters: RBX.filters.snapshot(), theme: S.theme, site: S.site, rail: S.railCollapsed,
      cam: m ? { center: m.getCenter(), zoom: m.getZoom(), pitch: m.getPitch(), bearing: m.getBearing() } : null, cams: JSON.parse(JSON.stringify(S.cams)),
      scroll: (document.getElementById('ppa') || {}).scrollTop || 0 };
    on = true; playing = false;
    if (RBX.search.isOpen()) RBX.search.close(true);
    if (RBX.drawer.isOpen()) RBX.drawer.close();
    if (RBX.band) RBX.band.closePop(false);
    RBX.header.toggleMenu(false);
    if (RBX.sheet.isOpen()) RBX.sheet.close();
    document.getElementById('app').classList.add('presenting');
    // the band and footer collapse at once, so resize now: a resize in the middle of a flight skews its target
    // chapter framing leaves room for the card, so lift the pan clamp (maxBounds) and allow a wider zoom while presenting
    if (m) { m.resize(); prior.minZoom = m.getMinZoom(); prior.maxBounds = m.getMaxBounds(); m.setMaxBounds(null); m.setMinZoom(Math.min(prior.minZoom, 3.4)); }
    fsEntered = false;
    try {
      var de = document.documentElement;
      if (de.requestFullscreen && !document.fullscreenElement) {
        var p = de.requestFullscreen();
        fsEntered = true;
        if (p && p.catch) p.catch(function () { fsEntered = false; RBX.toast('Tip: press F11 for full screen'); });
      } else if (!document.fullscreenElement) RBX.toast('Tip: press F11 for full screen');
    } catch (e) { RBX.toast('Tip: press F11 for full screen'); }
    Pr.go(start || 0);
    setTimeout(function () { var n = document.querySelector('#presentCard [data-pc="next"]'); if (n) n.focus({ preventScroll: true }); }, 50);
  };
  Pr.exit = function () {
    if (!on) return;
    on = false; playing = false; clearTimeout(timer);
    var S = RBX.state, m = RBX.map, p = prior || {};
    var card = document.getElementById('presentCard'); if (card) { card.hidden = true; card.innerHTML = ''; }
    document.getElementById('app').classList.remove('presenting');
    if (m) m.resize();
    terrain(false);
    if (m && p.minZoom != null) m.setMinZoom(p.minZoom);
    if (m && p.maxBounds) m.setMaxBounds(p.maxBounds);
    S.present = null;
    if (p.filters) RBX.filters.restore(p.filters);
    if (p.theme && p.theme !== S.theme) RBX.theme.set(p.theme);
    if (p.cams) S.cams = p.cams;
    RBX.app.setView(p.view || 'sam', { camera: false, scrollTop: false });
    if (m && p.cam && p.view !== 'ppa') m.jumpTo({ center: p.cam.center, zoom: p.cam.zoom, pitch: 0, bearing: 0 });
    else if (m) m.jumpTo({ pitch: 0, bearing: 0 });
    if (p.view === 'ppa') { var pp = document.getElementById('ppa'); if (pp) pp.scrollTop = p.scroll || 0; }
    if (p.site) { var row = RBX.data.find(p.site, p.view); if (row && RBX.filters.pass(row)) RBX.app.openSite(row, { fly: false, focus: false }); }
    try { if (fsEntered && document.fullscreenElement && document.exitFullscreen) document.exitFullscreen(); } catch (e) { /* ignore */ }
    fsEntered = false;
    S.writeHash();
    var b = document.getElementById('presentBtn'); if (b) b.focus({ preventScroll: true });
  };
  /** Keys while presenting (the shortcuts module routes here first). Returns true when handled. */
  Pr.key = function (e) {
    var k = e.key, n = chapters().length;
    if (k === 'ArrowRight' || k === ' ' || k === 'PageDown') { e.preventDefault(); if (idx >= n - 1) Pr.exit(); else Pr.go(idx + 1); return true; }
    if (k === 'ArrowLeft' || k === 'PageUp') { e.preventDefault(); Pr.go(idx - 1); return true; }
    if (k === 'Home') { e.preventDefault(); Pr.go(0); return true; }
    if (k === 'End') { e.preventDefault(); Pr.go(n - 1); return true; }
    return false;
  };
  // leaving full screen with the browser's own Esc also ends the presentation
  document.addEventListener('fullscreenchange', function () { if (on && fsEntered && !document.fullscreenElement) { fsEntered = false; Pr.exit(); } });
  // user interaction on the map pauses autoplay
  RBX.bus.on('mapready', function (m) { m.on('movestart', function (e) { if (on && playing && e && e.originalEvent) Pr.play(false); }); });
})();
