/* RBX.legend: legend-as-filter (spec 6.3c). Rows are <button aria-pressed>, with an "Only" affordance
   (also ⌥/⌘-click), "Show all" in the section title bar, faceted live counts, and map preview on hover.
   Groups are data: RBX.hooks.legendGroups[view]() may replace a view's groups (investor legends). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Lg = RBX.legend = {};
  RBX.hooks.legendGroups = RBX.hooks.legendGroups || {};

  function sw(o) { return RBX.icons.svg(Object.assign({ size: 14 }, o)); }
  function fmtMw(kw, d) { return U.num((kw || 0) / 1000, d == null ? ((kw || 0) >= 100000 ? 0 : 1) : d); }

  // ------------------------------------------------------------------ default (client) groups
  var DEF = {};
  DEF.sam = function () {
    var cfg = RBX.config, lc = (cfg.legend || {}).sam || {}, P = RBX.theme.pal(), tiers = cfg.labels.tiers;
    return { title: lc.title, sets: ['tiers'], groups: [{
      type: 'rows', set: 'tiers', prop: 't', foot: lc.foot,
      items: [1, 2, 3, 4, 5].map(function (t) {
        return { value: t, label: tiers[t], sec: (lc.rev || {})[t], secClass: 'rev', swatch: sw({ shape: 'dot', color: P.tier[t - 1] }), color: P.tier[t - 1] };
      })
    }] };
  };
  DEF.tam = function () {
    var cfg = RBX.config, lc = (cfg.legend || {}).tam || {}, P = RBX.theme.pal(), fuels = cfg.labels.fuels, fams = cfg.labels.families;
    var ink = P.ink2, mode = RBX.theme.tamMode();
    var famOf = RBX.data.FAM_OF;
    return { title: lc.title, sets: ['shapes', 'precision', 'fuels', 'tamTiers'], groups: [
      { type: 'chips', title: lc.subsidyTitle, set: 'shapes', prop: 'sh', items: [
        { value: 't', label: 'RO accredited', swatch: sw({ shape: 'tri', color: ink }) },
        { value: 'c', label: 'FiT accredited', swatch: sw({ shape: 'ring', color: ink }) }] },
      { type: 'chips', set: 'precision', prop: 'ap', items: [
        { value: 0, label: 'Exact location', swatch: sw({ shape: 'ring', color: ink }) },
        { value: 1, label: 'Postcode district', swatch: sw({ shape: 'ring', color: ink, dashed: true }) }] },
      // family quick-filter (spec 6.3). In 'fuels' mode the map colours each fuel, so the family chips are
      // neutral (the per-fuel rows below carry the colour key).
      { type: 'famChips', title: lc.techTitle, set: 'fuels', items: fams.map(function (f, i) {
        return { label: f, values: fuels.map(function (x, j) { return famOf[x] === i ? j : -1; }).filter(function (j) { return j >= 0; }),
          swatch: mode === 'fuels' ? sw({ shape: 'ring', color: ink }) : sw({ shape: 'ring', color: P.fam[i], dot: i === 3 }), fam: i };
      }) },
      { type: 'rows', set: 'fuels', prop: 'fu', mwDigits: 0, note: mode === 'fuels' ? lc.techNoteFuels : lc.techNote, items: fuelOrder().map(function (j) {
        var f = fuels[j], fam = famOf[f] != null ? famOf[f] : 3, col = mode === 'fuels' ? P.fuel[j] : P.fam[fam];
        return { value: j, label: f, swatch: sw({ shape: 'ring', color: col, dot: mode === 'families' && fam === 3 }), color: col };
      }) },
      { type: 'stack', title: lc.tierTitle, set: 'tamTiers', prop: 'bt', caption: lc.tierCaption, items: [1, 2, 3, 4, 5, 0].map(function (t) {
        return { value: t, label: cfg.labels.tiers[t], color: t ? P.tier[t - 1] : null };
      }) }
    ] };
  };
  DEF.hydro = function () {
    var cfg = RBX.config, lc = (cfg.legend || {}).hydro || {}, P = RBX.theme.pal();
    return { title: lc.title, sets: ['confs'], groups: [{
      type: 'rows', set: 'confs', prop: 'c', foot: lc.foot, unit: 'kW', items: cfg.labels.conf.map(function (c, i) {
        return { value: i, label: c, swatch: i === 3 ? sw({ shape: 'ring', color: P.unv }) : sw({ shape: 'dot', color: P.hyd[i] }), color: i === 3 ? P.unv : P.hyd[i] };
      })
    }] };
  };
  Lg.defaults = DEF;
  /** Fuel indices ordered by site count over the whole TAM (then MW), fixed for the session so rows never jump. */
  var FUEL_ORDER = null;
  function fuelOrder() {
    if (FUEL_ORDER) return FUEL_ORDER;
    var n = (RBX.config.labels.fuels || []).map(function () { return [0, 0]; });
    (RBX.data.rows.tam || []).forEach(function (r) { if (n[r.fu]) { n[r.fu][0]++; n[r.fu][1] += r.kw || 0; } });
    FUEL_ORDER = n.map(function (_, j) { return j; }).sort(function (a, b) { return (n[b][0] - n[a][0]) || (n[b][1] - n[a][1]) || a - b; });
    return FUEL_ORDER;
  }
  Lg.fuelOrder = fuelOrder;

  // ------------------------------------------------------------------ render
  function rowsHTML(view, g) {
    var H = RBX.state.hidden[g.set] || new Set();
    var fac = RBX.filters.facet(view, g.set, g.sumFn);
    var tot = 0; Object.keys(fac).forEach(function (k) { tot += fac[k].kw; });
    return '<div class="lg-rows">' + g.items.map(function (it) {
      var f = fac[it.value] || { n: 0, kw: 0 }, off = H.has(it.value);
      var val = g.unit === 'kW' ? U.int(f.kw) + '<small>kW</small>' : fmtMw(f.kw, g.mwDigits) + '<small>MW</small>';
      if (g.valueFn) val = g.valueFn(f, it);
      var bar = tot ? Math.max(1.5, f.kw / tot * 100) : 0;
      return '<div class="lg-row' + (off ? ' off' : '') + '" data-set="' + g.set + '" data-v="' + U.esc(it.value) + '" data-prop="' + g.prop + '">' +
        '<button type="button" class="lg-main" aria-pressed="' + (!off) + '" title="' + U.esc(it.title || '') + '">' +
        '<span class="lg-sw">' + it.swatch + '</span>' +
        '<span class="lg-lbl">' + U.esc(it.label) + (it.sec ? '<span class="lg-sec ' + (it.secClass || '') + '">' + U.esc(it.sec) + '</span>' : '') +
        '<span class="lg-bar" aria-hidden="true"><b style="width:' + bar.toFixed(1) + '%;background:' + (it.color || 'var(--ink-3)') + '"></b></span></span>' +
        '<span class="lg-n">' + U.int(f.n) + '</span><span class="lg-mw">' + val + '</span></button>' +
        '<button type="button" class="lg-only" data-only="1" aria-label="Show only ' + U.esc(it.label) + '">Only</button></div>';
    }).join('') + '</div>' + (g.note ? '<p class="r-note">' + U.esc(g.note) + '</p>' : '') + (g.foot ? '<p class="r-foot">' + U.esc(g.foot) + '</p>' : '');
  }
  function chipsHTML(view, g) {
    var H = RBX.state.hidden[g.set] || new Set(), fac = RBX.filters.facet(view, g.set);
    return '<div class="lg-chips" role="group" aria-label="' + U.esc(g.title || g.set) + '">' + g.items.map(function (it) {
      var off = H.has(it.value), f = fac[it.value] || { n: 0 };
      return '<button type="button" class="lg-chip" data-set="' + g.set + '" data-v="' + U.esc(it.value) + '" data-prop="' + g.prop + '" aria-pressed="' + (!off) + '">' +
        it.swatch + '<span>' + U.esc(it.label) + '</span> <span class="n">' + U.int(f.n) + '</span></button>';
    }).join('') + '</div>';
  }
  function famChipsHTML(view, g) {
    var H = RBX.state.hidden[g.set] || new Set();
    var fac = RBX.filters.facetBy(view, g.set, function (r) { return r.fam; });
    return '<div class="lg-chips" role="group" aria-label="Technology families">' + g.items.map(function (it) {
      var hid = it.values.filter(function (v) { return H.has(v); }).length;
      var st = hid === 0 ? 'true' : hid === it.values.length ? 'false' : 'mixed';
      return '<button type="button" class="lg-chip fam" data-fam="' + it.fam + '" data-vals="' + it.values.join(',') + '" aria-pressed="' + st + '">' + it.swatch +
        '<span>' + U.esc(it.label) + '</span> <span class="n">' + U.int((fac[it.fam] || { n: 0 }).n) + '</span></button>';
    }).join('') + '</div>';
  }
  function stackHTML(view, g) {
    var H = RBX.state.hidden[g.set] || new Set(), fac = RBX.filters.facet(view, g.set);
    var bar = '<div class="lg-stack" role="img" aria-label="Sites by indicative BM tier">' + g.items.map(function (it) {
      var n = (fac[it.value] || { n: 0 }).n;
      return '<span style="flex:' + Math.max(n, 0.001) + ';' + (it.color ? 'background:' + it.color : 'box-shadow:inset 0 0 0 1px var(--rule-2)') + (H.has(it.value) ? ';opacity:.25' : '') + '" title="' + U.esc(it.label) + ': ' + n + '"></span>';
    }).join('') + '</div>';
    var chips = { set: g.set, prop: g.prop, title: g.title, items: g.items.map(function (it) {
      return { value: it.value, label: it.label, swatch: it.color ? sw({ shape: 'dot', color: it.color, size: 10 }) : sw({ shape: 'ring', color: 'var(--ink-3)', size: 10 }) };
    }) };
    return bar + chipsHTML(view, chips) + (g.caption ? '<p class="r-note">' + U.esc(g.caption) + '</p>' : '');
  }
  var TYPES = { rows: rowsHTML, chips: chipsHTML, famChips: famChipsHTML, stack: stackHTML, html: function (v, g) { return typeof g.html === 'function' ? g.html() : g.html; } };
  Lg.TYPES = TYPES;

  Lg.spec = function (view) { var f = RBX.hooks.legendGroups[view] || DEF[view]; return f ? f() : null; };
  Lg.html = function (view) {
    var sp = Lg.spec(view); if (!sp) return '';
    var anyOff = (sp.sets || []).some(function (s) { return (RBX.state.hidden[s] || new Set()).size > 0; });
    var h = '<section class="r-sec lg" aria-labelledby="lgTitle"><div class="r-sec-h"><h3 class="r-sec-t" id="lgTitle">' + U.esc(sp.title || '') + '</h3>' +
      (anyOff ? '<button type="button" class="r-sec-a" data-showall="' + (sp.sets || []).join(',') + '">Show all</button>' : '') + '</div>' + (sp.sub ? '<p class="r-sub">' + U.esc(sp.sub) + '</p>' : '');
    sp.groups.forEach(function (g) {
      var body = TYPES[g.type] ? TYPES[g.type](view, g) : '';
      h += g.title ? '<div class="lg-group"><div class="lg-group-h"><h4 class="lg-group-t">' + U.esc(g.title) + '</h4></div>' + body + '</div>' : '<div class="lg-group">' + body + '</div>';
    });
    return h + (sp.after || '') + '</section>';
  };

  // ------------------------------------------------------------------ interaction (delegated on the rail)
  function val(el) {
    var v = el.getAttribute('data-v');
    return /^-?\d+(\.\d+)?$/.test(v) ? +v : v;
  }
  Lg.wire = function (root) {
    root.addEventListener('click', function (e) {
      var only = e.target.closest('[data-only]'), row = e.target.closest('.lg-row'), chip = e.target.closest('.lg-chip[data-set]'),
        fam = e.target.closest('.lg-chip.fam'), all = e.target.closest('[data-showall]');
      var F = RBX.filters, view = RBX.state.view;
      if (all) { all.getAttribute('data-showall').split(',').forEach(function (s) { (RBX.state.hidden[s] || new Set()).clear(); }); F.changed(); return; }
      if (only && row) { F.only(row.getAttribute('data-set'), val(row), view); return; }
      if (row && e.target.closest('.lg-main')) {
        if (e.altKey || e.metaKey) F.only(row.getAttribute('data-set'), val(row), view); else F.toggle(row.getAttribute('data-set'), val(row));
        return;
      }
      if (fam) {
        var vals = fam.getAttribute('data-vals').split(',').map(Number), H = RBX.state.hidden.fuels;
        if (e.altKey || e.metaKey) { F.setVisible('fuels', vals, 'tam'); return; }
        var allOn = vals.every(function (v) { return !H.has(v); });
        vals.forEach(function (v) { if (allOn) H.add(v); else H.delete(v); });
        F.changed();
        return;
      }
      if (chip) {
        if (e.altKey || e.metaKey) F.only(chip.getAttribute('data-set'), val(chip), view); else F.toggle(chip.getAttribute('data-set'), val(chip));
      }
    });
    var prev = function (e) {
      var row = e.target.closest('.lg-row:not(.off)'), chip = e.target.closest('.lg-chip[data-set][aria-pressed="true"]'), fam = e.target.closest('.lg-chip.fam');
      var view = RBX.state.view, pv = null;
      if (row) pv = { view: view, prop: row.getAttribute('data-prop'), values: [val(row)] };
      else if (chip) pv = { view: view, prop: chip.getAttribute('data-prop'), values: [val(chip)] };
      else if (fam) pv = { view: view, prop: 'fam', values: [+fam.getAttribute('data-fam')] };
      if (RBX.layers) RBX.layers.setPreview(pv);
    };
    root.addEventListener('mouseover', prev);
    root.addEventListener('focusin', prev);
    root.addEventListener('mouseleave', function () { if (RBX.layers) RBX.layers.setPreview(null); });
    root.addEventListener('focusout', function (e) { if (!root.contains(e.relatedTarget) && RBX.layers) RBX.layers.setPreview(null); });
  };
})();
