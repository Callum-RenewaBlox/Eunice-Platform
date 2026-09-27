/* RBX.app + RBX.boot: bootstrap and view/selection orchestration. Runs last in the bundle.
   Every map call is guarded (RBX.map may be null when MapLibre is unavailable). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, S = RBX.state;
  var A = RBX.app = {};

  A.setView = function (v, opts) {
    opts = opts || {};
    if (['sam', 'tam', 'hydro', 'ppa'].indexOf(v) < 0) return;
    var prev = S.view;
    if (v === prev && !opts.force) return;
    if (RBX.map && prev !== 'ppa') RBX.mapctl.saveCam(prev);
    S.view = v;
    if (v === 'sam' || v === 'tam') S.lastPeaker = v;
    var cur = RBX.sheet.current();
    if ((cur && cur.kind !== v) || (!cur && RBX.sheet.isOpen())) RBX.sheet.close();
    document.getElementById('app').setAttribute('data-view', v);
    document.getElementById('ppa').hidden = v !== 'ppa';
    if (RBX.layers.ready) { RBX.layers.setPreview(null); RBX.layers.clearHover(); }
    if (v === 'ppa') {
      RBX.ppaHost.show();
      var pp = document.getElementById('ppa'); pp.scrollLeft = 0; if (opts.scrollTop !== false) pp.scrollTop = 0;
    } else {
      RBX.rail.render();
      if (RBX.layers.ready) RBX.layers.showView(v);
      if (RBX.map) {
        if (prev === 'ppa') RBX.map.resize();
        if (opts.camera !== false) RBX.mapctl.enter(v, prev);
      }
      RBX.sizekey.render();
    }
    RBX.mapctl.updateOfflinePill();
    S.persist();
    S.writeHash();
    RBX.bus.emit('view', { view: v, prev: prev });
  };

  A.openSite = function (row, opts) {
    if (!row) return;
    opts = opts || {};
    if (row.kind !== S.view) A.setView(row.kind, { camera: !opts.fly });
    S.site = row.key;
    if (RBX.layers.ready) RBX.layers.select(row);
    RBX.sheet.open(row, { focus: opts.focus });
    if (U.isMobile()) RBX.rail.setOpen(false);
    if (RBX.map) { if (opts.fly) RBX.mapctl.flyTo(row); else RBX.mapctl.ensureVisible(row); }
    S.writeHash();
    RBX.bus.emit('select', row);
  };
  A.clearSelection = function () {
    S.site = null;
    if (RBX.layers.ready) RBX.layers.select(null);
    S.writeHash();
    RBX.bus.emit('select', null);
  };
  /** "See in register": switch to PPA and filter its register to this site. */
  A.showInRegister = function (row) {
    A.setView('ppa');
    setTimeout(function () { RBX.ppaHost.showSite(row); }, 60);
  };

  // ------------------------------------------------------------------ map wiring
  function wireMap(map) {
    RBX.layers.add(map);
    var touch = false;
    map.getCanvasContainer().addEventListener('touchstart', function () { touch = true; }, { passive: true });
    map.on('mousemove', U.rafThrottle(function (e) {
      if (touch || S.view === 'ppa') return;
      var c = RBX.layers.pick(e.point, 8), best = c[0] && c[0].row;
      RBX.layers.setHover(best || null);
      RBX.layers.showTip(best || null, e.point);
    }));
    map.getCanvas().addEventListener('mouseleave', function () { RBX.layers.clearHover(); });
    map.on('click', function (e) {
      var c = RBX.layers.pick(e.point, touch ? 14 : 8);
      if (!c.length) { if (RBX.sheet.isOpen()) RBX.sheet.close(); return; }
      var stack = RBX.layers.stackAt(c);
      if (stack.length >= 2) { RBX.sheet.chooser(stack); return; }
      A.openSite(c[0].row, { fly: false });
    });
    map.on('zoom', U.rafThrottle(RBX.sizekey.render));
    map.on('movestart', function () { var t = document.getElementById('tip'); if (t) t.hidden = true; });
    RBX.sizekey.render();
    var b = S.boot;
    if (b.site) {
      var row = RBX.data.find(b.site, b.view);
      if (row) { if (RBX.filters.hiding(row).length) RBX.filters.resetView(row.kind); A.openSite(row, { fly: !b.cam, focus: false }); }
    }
    RBX.bus.emit('mapready', map);
  }

  // ------------------------------------------------------------------ boot
  RBX.boot = function (cfg, raw) {
    RBX.config = cfg;
    var b = S.resolveBoot(cfg);
    S.theme = b.theme;
    document.documentElement.setAttribute('data-theme', b.theme);
    RBX.data.init(raw, cfg);
    S.view = b.view;
    if (b.view === 'sam' || b.view === 'tam') S.lastPeaker = b.view;
    document.getElementById('app').setAttribute('data-view', b.view);
    RBX.header.render();
    RBX.rail.init();
    RBX.sheet.init();
    RBX.drawer.init();
    RBX.search.init();
    if (b.view !== 'ppa') RBX.rail.render();
    else { document.getElementById('ppa').hidden = false; RBX.ppaHost.show(); }
    RBX.bus.on('filter', function (p) {
      if (RBX.layers.ready) RBX.layers.applyFilters();
      if (!(p && p.light)) {
        var cur = RBX.sheet.current();
        if (cur && !RBX.filters.pass(cur)) RBX.sheet.close();
        else if (cur) RBX.sheet.refresh();
      }
    });
    document.getElementById('zIn').addEventListener('click', function () { if (RBX.map) RBX.map.zoomIn(); });
    document.getElementById('zOut').addEventListener('click', function () { if (RBX.map) RBX.map.zoomOut(); });
    document.getElementById('zReset').addEventListener('click', function () { RBX.mapctl.reset(); });

    RBX.bus.on('mapfail', function () {
      var fr = (document.fonts && document.fonts.ready) ? document.fonts.ready : Promise.resolve();
      fr.then(function () {
        if (b.site) { var row = RBX.data.find(b.site, b.view); if (row) A.openSite(row, { focus: false }); }
        window.__atlasReady = true; RBX.bus.emit('ready');
      });
    });
    RBX.mapctl.init(b, wireMap);
    if (b.present && RBX.present && RBX.present.enter) RBX.bus.on('ready', function () { RBX.present.enter(); });
    RBX.header.sync();
    S.writeHash();
  };

  // a typed or linked short anchor (#ppa, #hydro, #tam, #sam) switches view at runtime too
  window.addEventListener('hashchange', function () {
    var h = (location.hash || '').replace(/^#/, '').toLowerCase();
    var m = /(?:^|&)v=(sam|tam|hydro|ppa)(?:&|$)/.exec(h);
    var v = h === 'peaker' ? 'sam' : ['sam', 'tam', 'hydro', 'ppa'].indexOf(h) >= 0 ? h : m ? m[1] : null;
    if (v && v !== S.view) A.setView(v);
  });

  // ------------------------------------------------------------------ QA API
  window.atlas = {
    setView: function (v) { A.setView(v); },
    select: function (kind, k, fly) {
      var rows = RBX.data.rows[kind] || [], r = typeof k === 'number' ? rows[k] : (RBX.data.byKey[kind][k] || rows.filter(function (x) { return x.name.toLowerCase().indexOf(String(k).toLowerCase()) >= 0; })[0]);
      if (r) RBX.search.reveal(r); if (r && fly === false && RBX.map) RBX.map.stop();
      return r ? r.key : null;
    },
    search: function (q) { RBX.search.open(q); },
    toggle: function (set, v) { RBX.filters.toggle(set, v); },
    only: function (set, v) { RBX.filters.only(set, v); },
    showAll: function () { RBX.filters.resetView(S.view); },
    preset: function (p) { RBX.hist.setPreset(p); },
    setTheme: function (t) { RBX.theme.set(t); },
    present: function (on) { if (RBX.present) { if (on === false) RBX.present.exit(); else RBX.present.enter(); } },
    openRail: function (o) { RBX.rail.setOpen(o !== false); },
    closeSheet: function () { RBX.sheet.close(); },
    reset: function () { RBX.mapctl.reset(); },
    find: function (kind, name) { return (RBX.data.rows[kind] || []).filter(function (r) { return r.name.toLowerCase().indexOf(name.toLowerCase()) >= 0; }).map(function (r) { return r.key; }); },
    state: S
  };

  // boot once the bundle is parsed (config + data are inlined before the bundle)
  try { RBX.boot(window.ATLAS_CONFIG, window.ATLAS_DATA); }
  catch (e) { if (window.console) console.error('[atlas] boot failed', e); window.__atlasBootError = String(e && e.message || e); }
})();
