/* RBX.state: the single app state, plus boot-order resolution and hash (de)serialisation (spec 7.3).
   Boot order: window.__ATLAS_INIT__ (wrapper, from st.query_params) → location.hash → localStorage → defaults. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;

  var S = RBX.state = {
    view: 'sam', theme: 'paper', site: null,
    hidden: { tiers: new Set(), fuels: new Set(), shapes: new Set(), precision: new Set(), tamTiers: new Set(),
      confs: new Set(), export: new Set(), pricing: new Set(), scale: new Set() },
    kw: { sam: null, tam: null, hydro: null },
    cams: {}, ppa: {}, present: null, railCollapsed: false, preview: null, lastPeaker: 'sam', boot: {}
  };
  var VIEWS = ['sam', 'tam', 'hydro', 'ppa'];

  /** Resolve the initial state. Returns {view, theme, site, cam} (cam may be null). */
  S.resolveBoot = function (cfg) {
    var out = { view: cfg.defaultView || 'sam', theme: cfg.defaultTheme || 'paper', site: null, cam: null, present: false };
    var key = cfg.storageKey || 'rbx-atlas';
    var lsTheme = U.store(key + ':theme'), lsView = U.store(key + ':view');
    if (lsTheme === 'paper' || lsTheme === 'night') out.theme = lsTheme;
    if (VIEWS.indexOf(lsView) >= 0) out.view = lsView;
    var h = {};
    try { new URLSearchParams((location.hash || '').replace(/^#/, '')).forEach(function (v, k) { h[k] = v; }); } catch (e) { /* ignore */ }
    if (VIEWS.indexOf(h.v) >= 0) out.view = h.v;
    // short anchors: #ppa, #hydro, #tam, #sam (and #peaker) open that view
    var bare = (location.hash || '').replace(/^#/, '').toLowerCase();
    if (bare === 'peaker') bare = 'sam';
    if (VIEWS.indexOf(bare) >= 0) out.view = bare;
    if (h.th === 'paper' || h.th === 'night') out.theme = h.th;
    if (h.s && /^[A-Za-z0-9-]{1,48}$/.test(h.s)) out.site = h.s;
    if (h.z && h.c) {
      // only a camera inside the map's maxBounds is honoured; zoom is clamped to the map's range
      var c = h.c.split(',').map(Number), z = +h.z;
      if (c.length === 2 && isFinite(c[0]) && isFinite(c[1]) && isFinite(z) &&
          c[0] >= -28 && c[0] <= 18 && c[1] >= 44.5 && c[1] <= 63.5) out.cam = { c: c, z: Math.max(4.2, Math.min(15, z)) };
    }
    if (h.present === '1') out.present = true;
    // ?present=1 on a direct link (the Streamlit wrapper passes it through __ATLAS_INIT__; srcdoc has no search)
    try { if (new URLSearchParams(location.search || '').get('present') === '1') out.present = true; } catch (e) { /* ignore */ }
    var init = window.__ATLAS_INIT__ || {};
    if (VIEWS.indexOf(init.view) >= 0) { out.view = init.view; out.cam = null; }
    if (init.theme === 'paper' || init.theme === 'night') out.theme = init.theme;
    if (init.site && /^[A-Za-z0-9-]{1,48}$/.test(init.site)) out.site = init.site;
    if (init.present === '1' || init.present === 1 || init.present === true) out.present = true;
    if (typeof init.publicUrl === 'string' && /^https:\/\//.test(init.publicUrl)) cfg.publicUrl = init.publicUrl;
    S.boot = out;
    return out;
  };

  S.persist = function () {
    var key = (RBX.config && RBX.config.storageKey) || 'rbx-atlas';
    U.store(key + ':theme', S.theme);
    U.store(key + ':view', S.view);
  };

  /** Hash is written with replaceState; it silently no-ops inside sandboxed iframes. Never carries commercial values. */
  S.writeHash = U.debounce(function () {
    var p = ['v=' + S.view];
    if (S.site) p.push('s=' + encodeURIComponent(S.site));
    var m = RBX.map;
    if (m && S.view !== 'ppa') {
      var c = m.getCenter();
      p.push('z=' + m.getZoom().toFixed(2), 'c=' + c.lng.toFixed(3) + ',' + c.lat.toFixed(3));
    }
    p.push('th=' + S.theme);
    if (S.present != null) p.push('present=1');
    try { history.replaceState(null, '', '#' + p.join('&')); } catch (e) { /* sandboxed */ }
  }, 250);

  /** Shareable link: the public app URL with query params, else the hash URL. */
  S.shareUrl = function (row) {
    var cfg = RBX.config || {}, v = row ? row.kind : S.view;
    var q = 'view=' + v + (row ? '&site=' + encodeURIComponent(row.key) : '') + '&theme=' + S.theme;
    if (cfg.publicUrl) return cfg.publicUrl.replace(/[?#].*$/, '') + '?' + q;
    var base = '';
    try { base = location.href.split('#')[0]; } catch (e) { base = ''; }
    if (!/^https?:/.test(base)) base = '';
    return base + '#v=' + v + (row ? '&s=' + encodeURIComponent(row.key) : '') + '&th=' + S.theme;
  };
})();
