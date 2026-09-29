/* RBX.nearme: "Sites near my postcode" (spec 11 P1 #3, client). Geocodes a full postcode or an outcode with
   postcodes.io, flies there, draws a dashed radius ring and lists the 5 nearest sites of the current map view
   (with their indicative tier) in the sheet. Offline or when postcodes.io is unreachable, it falls back to the
   atlas's own postcodes (an exact site postcode, else the centre of the sites in that outcode), and otherwise
   fails gracefully with a message. Entry points: the overflow menu, the rail foot, and a search-palette action
   whenever the query looks like a postcode. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var NM = RBX.nearme = { api: 'https://api.postcodes.io', timeout: 6000 };
  var PC_FULL = /^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/i, PC_OUT = /^[A-Z]{1,2}\d[A-Z\d]?$/i;
  var PIN = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 17.5s5.5-5.2 5.5-9.3a5.5 5.5 0 0 0-11 0c0 4.1 5.5 9.3 5.5 9.3z"/><circle cx="10" cy="8.2" r="1.9"/></svg>';
  NM.ICON = PIN;

  function fmtPc(s) {
    var c = U.compactPc(s);
    return PC_FULL.test(c) ? c.slice(0, -3) + ' ' + c.slice(-3) : c;
  }
  function fetchJson(url) {
    if (!window.fetch) return Promise.reject(new Error('offline'));
    var ctl = window.AbortController ? new AbortController() : null;
    var t = setTimeout(function () { if (ctl) ctl.abort(); }, NM.timeout);
    return fetch(url, ctl ? { signal: ctl.signal } : {}).then(function (r) {
      clearTimeout(t);
      if (r.status === 404) { var e = new Error('notfound'); e.code = 'notfound'; throw e; }
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    }, function (e) { clearTimeout(t); throw e; });
  }
  /** Offline fallback from the atlas's own site postcodes. */
  function local(pc) {
    var c = U.compactPc(pc), rows = [].concat(RBX.data.rows.sam || []);
    var ex = rows.filter(function (r) { return r.pc && U.compactPc(r.pc) === c; })[0];
    if (ex) return { lat: ex.lat, lon: ex.lon, label: fmtPc(pc), approx: false, local: true };
    var out = PC_FULL.test(c) ? U.outcode(fmtPc(c)) : c;
    var inOut = rows.filter(function (r) { return r.outcode === out; });
    if (inOut.length) return { lat: U.sum(inOut, function (r) { return r.lat; }) / inOut.length, lon: U.sum(inOut, function (r) { return r.lon; }) / inOut.length, label: out, approx: true, local: true };
    return null;
  }
  /** Resolve a postcode or outcode to {lat, lon, label, approx}. Rejects with .code 'invalid' | 'notfound' | 'offline'. */
  NM.lookup = function (q) {
    var c = U.compactPc(q), full = PC_FULL.test(c), out = PC_OUT.test(c);
    var err = function (code) { var e = new Error(code); e.code = code; return e; };
    if (!full && !out) return Promise.reject(err('invalid'));
    var url = NM.api + (full ? '/postcodes/' : '/outcodes/') + encodeURIComponent(c);
    return fetchJson(url).then(function (j) {
      var r = j && j.result;
      if (!r || r.latitude == null) throw err('notfound');
      return { lat: r.latitude, lon: r.longitude, label: full ? fmtPc(r.postcode || c) : (r.outcode || c), approx: !full };
    }).catch(function (e) {
      if (e && e.code === 'notfound') throw e;
      var l = local(c);
      if (l) return l;
      throw err('offline');
    });
  };

  // ------------------------------------------------------------------ map ring
  function circle(lon, lat, km, n) {
    var pts = [], k = km / 6371, la = lat * Math.PI / 180, lo = lon * Math.PI / 180;
    for (var i = 0; i <= (n || 72); i++) {
      var b = 2 * Math.PI * i / (n || 72);
      var y = Math.asin(Math.sin(la) * Math.cos(k) + Math.cos(la) * Math.sin(k) * Math.cos(b));
      var x = lo + Math.atan2(Math.sin(b) * Math.sin(k) * Math.cos(la), Math.cos(k) - Math.sin(la) * Math.sin(y));
      pts.push([x * 180 / Math.PI, y * 180 / Math.PI]);
    }
    return pts;
  }
  function ensureLayers(m) {
    if (m.getSource('near')) return;
    var P = RBX.theme.pal();
    m.addSource('near', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    var before = m.getLayer('sam-glow') ? 'sam-glow' : undefined;
    m.addLayer({ id: 'near-fill', type: 'fill', source: 'near', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': P.ink1, 'fill-opacity': 0.04 } }, before);
    m.addLayer({ id: 'near-ring', type: 'line', source: 'near', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'line-color': P.ink1, 'line-width': 1.2, 'line-dasharray': [3, 2.5], 'line-opacity': 0.75 } });
    m.addLayer({ id: 'near-pin', type: 'circle', source: 'near', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 5, 'circle-color': P.ink1, 'circle-stroke-width': 2.5, 'circle-stroke-color': P.stroke } });
  }
  NM.clear = function () {
    NM.active = null;
    var m = RBX.map; if (!m || !m.getSource('near')) return;
    m.getSource('near').setData({ type: 'FeatureCollection', features: [] });
  };
  RBX.bus.on('theme', function () {
    var m = RBX.map; if (!m || !m.getLayer('near-ring')) return;
    var P = RBX.theme.pal();
    m.setPaintProperty('near-fill', 'fill-color', P.ink1); m.setPaintProperty('near-ring', 'line-color', P.ink1);
    m.setPaintProperty('near-pin', 'circle-color', P.ink1); m.setPaintProperty('near-pin', 'circle-stroke-color', P.stroke);
    if (NM.active && RBX.sheet.isOpen() && !RBX.sheet.current()) NM.panel(NM.active);
  });
  RBX.bus.on('select', function (row) { if (!row && !NM.keep) NM.clear(); });
  RBX.bus.on('view', function (e) { if (NM.active && e.view !== NM.active.view) NM.clear(); });

  // ------------------------------------------------------------------ result
  function subFor(r) {
    var L = RBX.config.labels;
    if (r.kind === 'sam') return L.tiers[r.t] + ' · ' + U.cap(r.kw);
    if (r.kind === 'tam') return r.fuel + ' · ' + (r.bt ? 'Tier ' + r.bt + ' (indicative)' : 'Scotland · no BM revenue') + ' · ' + U.cap(r.kw);
    return (r.c === 3 ? 'Unverified' : r.conf + ' confidence') + ' · ' + U.int(r.kw) + ' kW stranded';
  }
  NM.panel = function (a) {
    var near = a.near;
    var html = '<h2 class="sh-name" id="sheetName">' + U.int(near.length) + ' nearest ' + (near.length === 1 ? 'site' : 'sites') + ' to ' + U.esc(a.pt.label) + '</h2>' +
      '<p class="sh-meta">' + U.esc(((RBX.config.views || {})[a.view] || {}).searchGroup || '') + ' · within ' + U.int(a.km) + ' km, straight-line distance' +
      (a.pt.approx ? ' · centred on the postcode district' : '') + '</p>' +
      '<div class="chooser near-list">' + near.map(function (p) {
        return '<button type="button" data-pick="' + p.r.kind + ':' + p.r.id + '">' + RBX.icons.forRow(p.r, 14) +
          '<span style="min-width:0"><span class="near-n" style="display:block">' + U.esc(p.r.name) + '</span><span class="near-s">' + U.esc(subFor(p.r)) + '</span></span>' +
          '<span class="near-d">' + (p.d < 10 ? U.num(p.d, 1) : U.int(p.d)) + ' km</span></button>';
      }).join('') + '</div>' +
      (a.pt.local ? '<div class="note-i">' + RBX.cards.INFO + '<span>Postcode lookup is unavailable right now, so this uses the location of ' + (a.pt.approx ? 'the atlas sites in that postcode district' : 'the site with that postcode') + '.</span></div>' : '') +
      (a.view !== 'hydro' ? '<div class="note-i">' + RBX.cards.INFO + '<span>Tiers are indicative projections of Balancing Mechanism value at each connection point.</span></div>' : '');
    NM.keep = true;
    RBX.sheet.panel({ chip: PIN.replace('class="i"', 'class="i" style="width:13px;height:13px"') + '<span>Near ' + U.esc(a.pt.label) + '</span>', html: html,
      actions: '<button type="button" class="btn" data-near="again">' + PIN + 'Another postcode</button>' });
    NM.keep = false;
  };
  NM.show = function (pt) {
    var S = RBX.state, view = S.view === 'ppa' ? (S.lastPeaker || 'sam') : S.view;
    if (S.view === 'ppa') RBX.app.setView(view, { camera: false });
    var rows = RBX.filters.active(view);
    if (!rows.length) rows = RBX.data.rows[view];
    var near = rows.map(function (r) { return { r: r, d: U.km([pt.lon, pt.lat], [r.lon, r.lat]) }; }).sort(function (a, b) { return a.d - b.d; }).slice(0, 5);
    var km = Math.max(5, Math.ceil((near.length ? near[near.length - 1].d : 10) + 3));
    NM.keep = true;
    RBX.app.clearSelection();
    NM.keep = false;
    NM.active = { pt: pt, near: near, km: km, view: view };
    var m = RBX.map;
    if (m) {
      ensureLayers(m);
      var ring = circle(pt.lon, pt.lat, km);
      m.getSource('near').setData({ type: 'FeatureCollection', features: [
        { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} },
        { type: 'Feature', geometry: { type: 'Point', coordinates: [pt.lon, pt.lat] }, properties: {} }] });
    }
    NM.panel(NM.active);
    if (m) {
      var b = U.bbox(circle(pt.lon, pt.lat, km, 24).map(function (p) { return { lon: p[0], lat: p[1] }; }), 0);
      RBX.mapctl.userMoved = true;
      m.fitBounds(b, { padding: RBX.mapctl.fitPadding(), maxZoom: 11, duration: RBX.reduced ? 0 : 1100, essential: true });
    }
    var l = document.getElementById('live'); if (l) l.textContent = near.length + ' nearest sites to ' + pt.label + ' listed in the panel.';
  };

  // ------------------------------------------------------------------ form (modal)
  NM.ask = function (pre) {
    if (!RBX.modal) return;
    RBX.modal.open({ title: 'Sites near a postcode', cls: 'modal-sm',
      sub: 'Finds the five nearest sites on the current map. The postcode is looked up with postcodes.io and is not stored.',
      html: '<form class="pc-form" novalidate><label for="pcIn" class="sr-only">Postcode or postcode district</label>' +
        '<input id="pcIn" name="pc" autocomplete="postal-code" inputmode="text" spellcheck="false" maxlength="9" placeholder="e.g. KT16 0EF or EX4" autofocus value="' + U.esc(pre || '') + '">' +
        '<button type="submit" class="btn btn-primary">' + PIN + 'Find sites</button></form><p class="pc-msg" id="pcMsg" role="status"></p>',
      onOpen: function (box) {
        var f = box.querySelector('form'), msg = box.querySelector('#pcMsg'), inp = box.querySelector('#pcIn');
        f.addEventListener('submit', function (e) {
          e.preventDefault();
          var v = inp.value.trim();
          msg.className = 'pc-msg'; msg.textContent = 'Looking up ' + fmtPc(v) + '…';
          NM.go(v).then(function () { RBX.modal.close(true); }, function (er) {
            msg.className = 'pc-msg err';
            msg.textContent = NM.message(er, v);
            inp.focus(); inp.select();
          });
        });
      } });
  };
  NM.message = function (er, v) {
    var code = er && er.code;
    if (code === 'invalid') return 'Enter a UK postcode such as KT16 0EF, or a postcode district such as EX4.';
    if (code === 'notfound') return 'We couldn’t find ' + fmtPc(v) + '. Check it and try again.';
    return 'Postcode lookup is unavailable right now. Try again later, or search for a site, town or operator with /.';
  };
  NM.go = function (v) { return NM.lookup(v).then(function (pt) { NM.show(pt); return pt; }); };

  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-near]'); if (!b) return;
    var pre = NM.active ? NM.active.pt.label : '';
    NM.ask(b.getAttribute('data-near') === 'again' ? '' : pre);
  });
  // search palette: offer the action whenever the query looks like a postcode
  RBX.search.extras.push(function (raw) {
    var c = U.compactPc(raw);
    if (!(PC_FULL.test(c) || (PC_OUT.test(c) && c.length >= 3 && /\d/.test(c)))) return [];
    return [{ label: 'Sites near ' + fmtPc(c), sub: 'Five nearest sites on the current map · postcodes.io', icon: PIN, run: function () {
      NM.go(c).catch(function (er) { RBX.toast(NM.message(er, c)); });
    } }];
  });
  RBX.header.menu.push({ id: 'near', order: 35, label: 'Sites near a postcode…', icon: PIN, run: function () { NM.ask(''); } });
})();
