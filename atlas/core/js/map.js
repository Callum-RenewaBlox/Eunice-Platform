/* RBX.mapctl: map init, fit padding that accounts for the panels, per-view camera memory, fly-to-site with
   obstruction offsets, ResizeObserver, offline pill, and window.__atlasReady (spec 4, 5.7).
   If MapLibre is unavailable (CDN blocked / no WebGL) RBX.map stays null and a calm fallback panel shows. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var M = RBX.mapctl = {};
  RBX.map = null;

  M.viewBounds = function (view) {
    var rows = RBX.data.rows[view];
    if (!rows || !rows.length) return [[-8.2, 49.8], [1.9, 58.9]];
    return U.bbox(rows, 0.25);
  };
  function rect(id) { var el = document.getElementById(id); return el && !el.hidden && el.offsetParent !== null ? el.getBoundingClientRect() : null; }
  /** Pixels hidden by the rail (left) and the sheet (right) inside the map area. */
  M.obstruction = function () {
    var area = document.getElementById('mapArea').getBoundingClientRect();
    if (U.isMobile()) {
      var sh = rect('sheet'), rl = rect('rail');
      return { left: 0, right: 0, bottom: sh ? area.bottom - sh.top : (rl ? area.bottom - rl.top : 0), top: 0 };
    }
    var r = rect('rail'), s = rect('sheet');
    return { left: r ? r.right - area.left : 0, right: s ? area.right - s.left : 0, bottom: 0, top: 0 };
  };
  M.fitPadding = function () {
    if (U.isMobile()) {
      var peek = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--peek-h')) || 136;
      return { top: 16, bottom: peek + 16, left: 16, right: 16 };
    }
    var o = M.obstruction(), area = document.getElementById('mapArea').getBoundingClientRect();
    var pad = { top: 24, bottom: 44, left: (o.left || 0) + 36, right: o.right ? o.right + 36 : 56 };
    // never let padding swallow the canvas (narrow iframes)
    var spare = area.width - pad.left - pad.right;
    if (spare < 160) { var cut = (160 - spare) / 2; pad.left = Math.max(12, pad.left - cut); pad.right = Math.max(12, pad.right - cut); }
    return pad;
  };

  M.fit = function (view, animate) {
    var m = RBX.map; if (!m) return;
    M.userMoved = false;
    var b = (RBX.hooks.viewBounds && RBX.hooks.viewBounds(view)) || M.viewBounds(view);
    m.fitBounds(b, { padding: M.fitPadding(), maxZoom: 7.2, duration: animate && !RBX.reduced ? 900 : 0, essential: true });
  };
  M.saveCam = function (view) {
    var m = RBX.map; if (!m || !view || view === 'ppa') return;
    if (!M.userMoved) return;
    var c = m.getCenter();
    RBX.state.cams[view] = { c: [c.lng, c.lat], z: m.getZoom() };
  };
  /** Enter a view: restore its camera, keep the camera for SAM↔TAM when ≥ 80 % of active sites are in view, else fit. */
  M.enter = function (view, prev) {
    var m = RBX.map; if (!m || view === 'ppa') return;
    var cam = RBX.state.cams[view];
    if (cam) { m.jumpTo({ center: cam.c, zoom: cam.z }); M.userMoved = true; return; }
    // keep the camera across SAM ↔ TAM only when the user has moved it themselves (an automatic fit of one
    // layer would otherwise clip the other, e.g. TAM's Scottish sites)
    if (((prev === 'sam' && view === 'tam') || (prev === 'tam' && view === 'sam')) && M.userMoved) {
      var act = RBX.filters.active(view), b = m.getBounds(), n = 0;
      act.forEach(function (r) { if (b.contains([r.lon, r.lat])) n++; });
      if (act.length && n / act.length >= 0.8) return;
    }
    M.fit(view, prev !== 'ppa' && prev != null);
  };
  M.reset = function () { M.fit(RBX.state.view, true); };

  /** Offset [x, y] that centres a point in the unobstructed part of the map. */
  M.offset = function () {
    var o = M.obstruction();
    if (U.isMobile()) return [0, -Math.round((o.bottom || 0) / 2)];
    return [Math.round(((o.left || 0) - (o.right || 0)) / 2), 0];
  };
  M.flyTo = function (row, opts) {
    var m = RBX.map; if (!m || !row) return;
    opts = opts || {};
    var z = opts.zoom != null ? opts.zoom : Math.max(m.getZoom(), 8.3);
    var o = { center: [row.lon, row.lat], zoom: z, offset: M.offset(), essential: true };
    M.userMoved = true;
    if (RBX.reduced) { o.duration = 0; m.easeTo(o); return; }
    o.speed = 1.3; o.curve = 1.42; o.maxDuration = 2200;
    m.flyTo(o);
  };
  /** Only move if the site is covered by a panel or off-screen. */
  M.ensureVisible = function (row) {
    var m = RBX.map; if (!m || !row) return;
    var p = m.project([row.lon, row.lat]), c = m.getContainer(), o = M.obstruction();
    var ok = p.x > (o.left || 0) + 24 && p.x < c.clientWidth - (o.right || 0) - 24 && p.y > 24 && p.y < c.clientHeight - (o.bottom || 0) - 24;
    if (!ok) M.userMoved = true;
    if (!ok) m.easeTo({ center: [row.lon, row.lat], offset: M.offset(), duration: RBX.reduced ? 0 : 600, essential: true });
  };

  M.updateOfflinePill = function () {
    var el = document.getElementById('offlinePill'), m = RBX.map;
    if (!el) return;
    el.hidden = !(m && m.__rbxBasemapMode === 'offline' && m.getZoom() >= 7.2 && RBX.state.view !== 'ppa');
  };

  M.fallback = function (reason) {
    RBX.map = null;
    var fb = document.getElementById('mapFallback'); if (fb) fb.hidden = false;
    var ctl = document.getElementById('mapCtl'); if (ctl) ctl.hidden = true;
    if (window.console) console.warn('[atlas] map unavailable: ' + reason);
    RBX.bus.emit('mapfail', reason);
  };

  /** Streamlit renders the page in an about:srcdoc iframe. There `location.origin` is "null" while the document
      (and so MapLibre's blob worker) keeps the parent's origin; MapLibre's Actor drops every worker message whose
      origin differs, so no source ever loads. Re-mint the worker with a shim that reports the same "null" origin. */
  M.prepareWorker = function () {
    var ml = window.maplibregl;
    var needed = false;
    try { needed = window.location.origin === 'null' && !!ml.getWorkerUrl && !!ml.setWorkerUrl && /^blob:/.test(ml.getWorkerUrl()); } catch (e) { needed = false; }
    if (!needed || !window.fetch) return Promise.resolve(false);
    var shim = '(function(){try{var L=self.location,o={};["href","protocol","host","hostname","port","pathname","search","hash"].forEach(function(k){o[k]=L[k];});' +
      'o.origin="null";o.toString=function(){return L.href;};Object.defineProperty(self,"location",{value:o,configurable:true});}catch(e){}})();\n';
    return fetch(ml.getWorkerUrl()).then(function (r) { return r.text(); }).then(function (src) {
      ml.setWorkerUrl(URL.createObjectURL(new Blob([shim + src], { type: 'text/javascript' })));
      return true;
    }).catch(function () { return false; });
  };

  M.init = function (boot, onLoad) {
    if (!window.maplibregl || !window.RBXBasemap) { M.fallback('MapLibre not loaded'); return false; }
    M.prepareWorker().then(function () { M.create(boot, onLoad); });
    return true;
  };
  M.create = function (boot, onLoad) {
    var cfg = RBX.config;
    var start = boot.view === 'ppa' ? (RBX.state.lastPeaker || 'sam') : boot.view;
    var opts = {
      container: 'map', style: window.RBXBasemap.style(boot.theme, { focus: 'uk' }),
      minZoom: 4.2, maxZoom: 15, maxBounds: [[-28, 44.5], [18, 63.5]],
      attributionControl: { compact: true, customAttribution: cfg.attribution || 'Geocoding: <a href="https://postcodes.io">postcodes.io</a>' },
      dragRotate: false, pitchWithRotate: false, touchPitch: false
    };
    if (boot.cam) { opts.center = boot.cam.c; opts.zoom = boot.cam.z; }
    else { opts.bounds = M.viewBounds(start); opts.fitBoundsOptions = { padding: M.fitPadding(), maxZoom: 7.2 }; }
    var map;
    try { map = new window.maplibregl.Map(opts); } catch (e) { M.fallback(e && e.message); return false; }
    RBX.map = map;
    try { map.getCanvas().setAttribute('aria-label', 'Map of sites. Arrow keys pan, plus and minus zoom; use search (/) to reach any site.'); } catch (e) { /* ignore */ }
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.addControl(new window.maplibregl.ScaleControl({ maxWidth: 90, unit: 'metric' }), 'bottom-left');
    map.on('error', function (e) {
      var msg = String((e && e.error && (e.error.message || e.error.status)) || e);
      var url = (e && e.error && e.error.url) || (e && e.source && e.source.url) || '';
      if (!/openfreemap|Failed to fetch|NetworkError|AJAXError|\.pbf|terrarium|elevation-tiles|glyphs|tiles/i.test(msg + ' ' + url) && window.console) console.warn('[atlas] map error: ' + msg);
    });
    var cities = window.RBXBasemap.cities.filter(function (c) { return c[1] > -11 && c[1] < 1.9; });
    M.basemap = window.RBXBasemap.attach(map, { cities: cities, onMode: function () { M.updateOfflinePill(); } });

    map.on('load', function () {
      if (U.isMobile()) { var ab = document.querySelector('.maplibregl-ctrl-attrib'); if (ab) ab.classList.remove('maplibregl-compact-show'); }
      onLoad(map);
      var ready = function () {
        var fr = (document.fonts && document.fonts.ready) ? document.fonts.ready : Promise.resolve();
        var br = (M.basemap && M.basemap.ready && M.basemap.ready.then) ? M.basemap.ready : Promise.resolve();
        Promise.all([fr, br.catch ? br.catch(function () {}) : br]).then(function () { setTimeout(function () { window.__atlasReady = true; RBX.bus.emit('ready'); }, 120); });
      };
      map.once('idle', ready);
    });
    map.on('zoomend', M.updateOfflinePill);
    map.on('movestart', function (e) { if (e && e.originalEvent) M.userMoved = true; });
    map.on('moveend', function () { if (RBX.state.view !== 'ppa') RBX.state.writeHash(); });
    if (window.ResizeObserver) {
      new ResizeObserver(U.rafThrottle(function () { if (RBX.map) RBX.map.resize(); })).observe(document.getElementById('map'));
    }
    return true;
  };
})();
