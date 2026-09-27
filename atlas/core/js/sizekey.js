/* RBX.sizekey: on-map size key that recomputes with zoom (spec 5.2). SAM/Hydro: nested circles computed with
   the same radius function as the map; TAM: the five capacity bands plus the precision key. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Sk = RBX.sizekey = {};
  /** Map a key value to the layer's size value `sv` (audience hook; an audience may key other units). */
  RBX.hooks.sizeValue = RBX.hooks.sizeValue || function (view, v) {
    var m = RBX.data.meta;
    return Math.sqrt(v / (view === 'sam' ? m.samMax : m.hydroMax));
  };
  RBX.hooks.sizeLabel = RBX.hooks.sizeLabel || function (view, v) { return U.cap(v); };

  function nested(view, cfgKey) {
    var z = RBX.map.getZoom(), vals = cfgKey.values || [];
    var rs = vals.map(function (v) { return RBX.layers.radiusAt(view, z, Math.min(1.2, RBX.hooks.sizeValue(view, v))); });
    var rm = rs[rs.length - 1] || 10, base = Math.max(rm * 2, 30) + 2, cx = rm + 1, lx = rm * 2 + 14, last = -1e9, s = '';
    var items = vals.map(function (v, i) { return { v: v, r: rs[i], top: base - 2 * rs[i] }; }).reverse();
    items.forEach(function (it) { it.ly = Math.max(it.top, last + 12); last = it.ly; });
    items.forEach(function (it) {
      s += '<circle cx="' + cx + '" cy="' + (base - it.r).toFixed(1) + '" r="' + it.r.toFixed(1) + '" fill="var(--wash)" stroke="var(--ink-2)" stroke-width="1"/>';
      s += '<path d="M' + cx + ',' + it.top.toFixed(1) + ' L' + (lx - 8) + ',' + it.top.toFixed(1) + ' L' + (lx - 3) + ',' + it.ly.toFixed(1) + '" fill="none" stroke="var(--ink-3)" stroke-width=".75"/>';
      s += '<text x="' + lx + '" y="' + (it.ly + 3.8).toFixed(1) + '">' + U.esc(RBX.hooks.sizeLabel(view, it.v)) + '</text>';
    });
    var H = Math.max(base, last + 6) + 2, W = lx + 52;
    return '<div class="sizekey-t">' + U.esc(cfgKey.title) + '</div><svg width="' + W + '" height="' + H.toFixed(0) + '" viewBox="0 -2 ' + W + ' ' + H.toFixed(0) + '">' + s + '</svg>';
  }
  function bands(cfgKey) {
    var z = RBX.map.getZoom(), k = RBX.layers.tamScaleAt(z), SL = 48, D = RBX.icons.BAND_D, dmax = D[4] * k, cy = dmax / 2 + 2, s = '';
    var lab = ['<250 kW', '<1 MW', '<5 MW', '<20 MW', '20 MW+'];
    D.forEach(function (d, i) {
      var x = SL * i + SL / 2;
      s += '<circle cx="' + x + '" cy="' + cy.toFixed(1) + '" r="' + (d * k / 2).toFixed(1) + '" fill="var(--wash)" stroke="var(--ink-2)" stroke-width="1.4"/>' +
        '<text x="' + x + '" y="' + (dmax + 16).toFixed(1) + '" text-anchor="middle">' + U.esc(lab[i]) + '</text>';
    });
    var y2 = dmax + 36;
    return '<div class="sizekey-t">' + U.esc(cfgKey.title || 'Capacity band') + '</div><svg width="' + SL * 5 + '" height="' + (y2 + 8).toFixed(0) + '">' + s +
      '<line x1="0" x2="' + SL * 5 + '" y1="' + (dmax + 24).toFixed(1) + '" y2="' + (dmax + 24).toFixed(1) + '" stroke="var(--rule)"/>' +
      '<circle cx="8" cy="' + y2.toFixed(1) + '" r="5" fill="none" stroke="var(--ink-2)" stroke-width="1.4"/><text x="18" y="' + (y2 + 3.8).toFixed(1) + '">Exact location</text>' +
      '<circle cx="124" cy="' + y2.toFixed(1) + '" r="5" fill="none" stroke="var(--ink-2)" stroke-width="1.4" stroke-dasharray="2.2 1.6"/><text x="134" y="' + (y2 + 3.8).toFixed(1) + '">Postcode district</text></svg>';
  }
  Sk.render = function () {
    var el = document.getElementById('sizekey'); if (!el) return;
    var view = RBX.state.view, vc = (RBX.config.views || {})[view] || {};
    if (!RBX.map || view === 'ppa' || !vc.sizeKey) { el.innerHTML = ''; Sk.clearLabels(); return; }
    el.innerHTML = view === 'tam' ? bands(vc.sizeKey) : nested(view, vc.sizeKey);
    Sk.clearLabels();
  };

  /** The basemap's sea labels are drawn on the map canvas; hide any whose box would sit under the size key
      (e.g. "Celtic Sea" at 1440 × 820 in TAM) instead of letting the key clip it. */
  var SEA_SRC = 'rbx-lbl-sea';
  function seaLayers(m) { return ((m.getStyle() || {}).layers || []).filter(function (l) { return l.source === SEA_SRC && l.type === 'symbol'; }); }
  Sk.clearLabels = U.rafThrottle(function () {
    var m = RBX.map, key = document.getElementById('sizekey'); if (!m || !m.getSource(SEA_SRC)) return;
    var hide = [];
    if (key && key.innerHTML && key.offsetParent !== null) {
      var kr = key.getBoundingClientRect(), mr = m.getContainer().getBoundingClientRect(), z = m.getZoom(), feats = [];
      try { feats = (m.getSource(SEA_SRC).serialize().data || {}).features || []; } catch (e) { feats = []; }
      feats.forEach(function (f) {
        var id = f.properties.img, img = null;
        try { img = m.getImage ? m.getImage(id) : null; } catch (e) { img = null; }
        var pr = (img && img.pixelRatio) || 2, w = img && img.data ? img.data.width / pr : 110, h = img && img.data ? img.data.height / pr : 24;
        var p = m.project(f.geometry.coordinates), x = p.x + mr.left, y = p.y + mr.top;
        if (x + w / 2 > kr.left - 6 && x - w / 2 < kr.right + 6 && y + h / 2 > kr.top - 6 && y - h / 2 < kr.bottom + 6) hide.push(id);
      });
    }
    seaLayers(m).forEach(function (l) {
      var f = m.getFilter(l.id), orig = f && f[0] === 'all' && f.length === 3 && f[2] && f[2][0] === '!' ? f[1] : f;
      var next = hide.length ? ['all', orig, ['!', ['in', ['get', 'img'], ['literal', hide]]]] : orig;
      if (JSON.stringify(next) !== JSON.stringify(f)) { try { m.setFilter(l.id, next); } catch (e) { /* layer rebuilt by the basemap */ } }
    });
  });
  RBX.bus.on('mapready', function (map) {
    map.on('moveend', Sk.clearLabels);
    map.on('styledata', function () { Sk.clearLabels(); });
  });
})();
