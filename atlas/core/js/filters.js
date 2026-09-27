/* RBX.filters: one hidden Set per dimension plus a kW range per view. The same definition produces the
   MapLibre expressions and the JS predicate that drives KPIs, faceted legend counts and the histogram (spec 5.6).
   Filter changes never move the camera. Hidden sets persist across views. */
(function () {
  'use strict';
  var RBX = window.RBX;
  var F = RBX.filters = {};

  /** Dimensions per view. Investor modules push extra ones (pricing, export class, scale) before boot.
      `prop` is the GeoJSON feature property; `rowProp` (optional) the row field when it differs. */
  F.dims = {
    sam: [{ set: 'tiers', prop: 't', values: [1, 2, 3, 4, 5] }],
    tam: [
      { set: 'fuels', prop: 'fu', values: [0, 1, 2, 3, 4, 5, 6, 7, 8] },
      { set: 'shapes', prop: 'sh', values: ['t', 'c'] },
      { set: 'precision', prop: 'ap', values: [0, 1] },
      { set: 'tamTiers', prop: 'bt', values: [1, 2, 3, 4, 5, 0] }
    ],
    hydro: [{ set: 'confs', prop: 'c', values: [0, 1, 2, 3] }]
  };
  /** Property the capacity filter reads (hydro filters on installed kW, as in v1). */
  F.capProp = { sam: 'kw', tam: 'kw', hydro: 'inst' };
  F.capOf = function (r) { var v = r[F.capProp[r.kind]]; return v == null ? 0 : v; };

  function hidden(set) { return RBX.state.hidden[set] || (RBX.state.hidden[set] = new Set()); }
  F.visibleValues = function (d) { var h = hidden(d.set); return d.values.filter(function (v) { return !h.has(v); }); };

  /** Row passes every dimension (optionally skipping one set, or the kW range when skip === 'kw'). */
  F.pass = function (r, skip) {
    var dims = F.dims[r.kind] || [];
    for (var i = 0; i < dims.length; i++) {
      var d = dims[i];
      if (d.set === skip) continue;
      if (hidden(d.set).has(r[d.rowProp || d.prop])) return false;
    }
    if (skip !== 'kw') {
      var k = RBX.state.kw[r.kind];
      if (k) { var c = F.capOf(r); if (c < k[0] || c > k[1]) return false; }
    }
    return true;
  };
  F.active = function (view) { return (RBX.data.rows[view] || []).filter(function (r) { return F.pass(r); }); };

  /** MapLibre expression for the active set of a view. */
  F.expr = function (view) {
    var e = ['all'];
    (F.dims[view] || []).forEach(function (d) {
      if (!hidden(d.set).size) return;
      e.push(['in', ['get', d.prop], ['literal', F.visibleValues(d)]]);
    });
    var k = RBX.state.kw[view];
    if (k) {
      var p = F.capProp[view];
      e.push(['>=', ['get', p], k[0]]);
      if (isFinite(k[1])) e.push(['<=', ['get', p], k[1]]);
    }
    return e.length > 1 ? e : ['boolean', true];
  };

  /** Faceted counts for one dimension: each value's count/sum ignoring that dimension's own filter. */
  F.facet = function (view, set, sumFn) {
    var dim = (F.dims[view] || []).filter(function (d) { return d.set === set; })[0];
    var out = {};
    if (!dim) return out;
    dim.values.forEach(function (v) { out[v] = { n: 0, kw: 0 }; });
    (RBX.data.rows[view] || []).forEach(function (r) {
      if (!F.pass(r, set)) return;
      var o = out[r[dim.rowProp || dim.prop]];
      if (!o) return;
      o.n++; o.kw += (sumFn ? sumFn(r) : r.kw) || 0;
    });
    return out;
  };
  /** Group counts by an arbitrary key over rows passing all filters except `set` (used for family chips). */
  F.facetBy = function (view, set, keyFn, sumFn) {
    var out = {};
    (RBX.data.rows[view] || []).forEach(function (r) {
      if (!F.pass(r, set)) return;
      var k = keyFn(r), o = out[k] || (out[k] = { n: 0, kw: 0 });
      o.n++; o.kw += (sumFn ? sumFn(r) : r.kw) || 0;
    });
    return out;
  };

  F.anyHidden = function (view) {
    return (F.dims[view] || []).some(function (d) { return hidden(d.set).size > 0; }) || !!RBX.state.kw[view];
  };
  F.dimOf = function (view, set) { return (F.dims[view] || []).filter(function (d) { return d.set === set; })[0]; };

  // ------------------------------------------------------------------ mutations (all emit 'filter')
  F.toggle = function (set, value) {
    var h = hidden(set);
    if (h.has(value)) h.delete(value); else h.add(value);
    F.changed();
  };
  F.only = function (set, value, view) {
    var d = F.dimOf(view || RBX.state.view, set) || { values: [] };
    var h = hidden(set);
    h.clear();
    d.values.forEach(function (v) { if (v !== value) h.add(v); });
    F.changed();
  };
  /** Show only the given values of a set (used by family chips and story/present chapters). */
  F.setVisible = function (set, values, view) {
    var d = F.dimOf(view || RBX.state.view, set) || { values: [] };
    var h = hidden(set);
    h.clear();
    d.values.forEach(function (v) { if (values.indexOf(v) < 0) h.add(v); });
    F.changed();
  };
  F.showAll = function (set) { hidden(set).clear(); F.changed(); };
  F.resetView = function (view) {
    (F.dims[view] || []).forEach(function (d) { hidden(d.set).clear(); });
    RBX.state.kw[view] = null;
    F.changed();
  };
  F.setKw = function (view, range, light) {
    RBX.state.kw[view] = range;
    F.changed(light);
  };
  /** Which filters hide a given row (for the search "clear the hiding filter + Undo" behaviour). */
  F.hiding = function (r) {
    var out = [];
    (F.dims[r.kind] || []).forEach(function (d) { var v = r[d.rowProp || d.prop]; if (hidden(d.set).has(v)) out.push({ set: d.set, value: v }); });
    var k = RBX.state.kw[r.kind];
    if (k) { var c = F.capOf(r); if (c < k[0] || c > k[1]) out.push({ set: 'kw', value: k }); }
    return out;
  };
  F.snapshot = function () {
    var h = {};
    Object.keys(RBX.state.hidden).forEach(function (k) { h[k] = Array.from(RBX.state.hidden[k]); });
    return { hidden: h, kw: JSON.parse(JSON.stringify(RBX.state.kw, function (k, v) { return v === Infinity ? 'Inf' : v; })) };
  };
  F.restore = function (snap) {
    Object.keys(snap.hidden).forEach(function (k) { RBX.state.hidden[k] = new Set(snap.hidden[k]); });
    Object.keys(snap.kw).forEach(function (v) { var k = snap.kw[v]; RBX.state.kw[v] = k ? [k[0], k[1] === 'Inf' ? Infinity : k[1]] : null; });
    F.changed();
  };
  F.changed = function (light) { RBX.bus.emit('filter', { light: !!light }); };
})();
