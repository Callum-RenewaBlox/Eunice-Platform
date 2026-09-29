/* Investor build only (never in the client manifest). RBX.inv: the derived economics of spec 10.2, computed at
   runtime from the investor data, plus the audience hooks: size ∝ √TCV for SAM, unpriced sites as hollow rings,
   extra filter dimensions (pricing, hydro export class, TAM scale), tooltip, size key, search, step order,
   register rows with v1 rank and raw REGO labels. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, H = RBX.hooks;
  RBX.audience = 'investor';
  var I = RBX.inv = { TCVRATE: {}, AVRATIO: 0, WHOLESALE: 8.0, TAVG: {}, tcvMax: 1, asOf: {} };

  // ------------------------------------------------------------------ formatting (v1 semantics: U.abbr, U.gbp0)
  /** Tooltip / label money: £9.27M, £845k. */
  I.money2 = function (v) {
    if (v == null) return '—';
    if (v >= 1e9) return '£' + (v / 1e9).toFixed(2) + 'bn';
    if (v >= 1e6) return '£' + (v / 1e6).toFixed(2) + 'M';
    return '£' + Math.round(v / 1e3) + 'k';
  };
  I.uplift = function (t) { return Math.round((I.TAVG[t] / I.WHOLESALE - 1) * 100); };
  I.gsp = function (g) { return g ? String(g).replace(/North Wale$/, 'North Wales') : ''; };

  // ------------------------------------------------------------------ economics (spec 10.2), after data decode
  /** Available-for-BM kW for a TAM row: DNO max export where known, else installed × AVRATIO. */
  I.bmKw = function (d) { return d.bm != null ? d.bm : (d.kw || 0) * I.AVRATIO; };
  /** Indicative TCV potential of one TAM row (Scotland, bt = 0, carries none). */
  I.pot = function (d) { return d.bt > 0 ? I.bmKw(d) * (I.TCVRATE[d.bt] || 0) : 0; };
  I.tcvPot = function (rows) { var s = 0; for (var i = 0; i < rows.length; i++) s += rows[i].pot || 0; return s; };

  RBX.bus.on('data', function (D) {
    var model = (D.meta.raw && D.meta.raw.model) || {};
    I.WHOLESALE = model.WHOLESALE || 8.0;
    I.TAVG = model.TAVG || {};
    I.asOf = model.asOf || {};
    var priced = D.rows.sam.filter(function (r) { return r.tcv != null; });
    [1, 2, 3, 4, 5].forEach(function (t) {
      var g = priced.filter(function (r) { return r.t === t; });
      I.TCVRATE[t] = U.sum(g, function (r) { return r.tcv; }) / (U.sum(g, function (r) { return r.av; }) || 1);
    });
    I.AVRATIO = U.sum(priced, function (r) { return r.av; }) / (U.sum(priced, function (r) { return r.inst; }) || 1);
    I.priced = priced.length;
    D.rows.tam.forEach(function (r) { r.pot = I.pot(r); });
    I.totals = {
      tamPot: I.tcvPot(D.rows.tam),
      tamBig: I.tcvPot(D.rows.tam.filter(function (r) { return r.big; })),
      tamBigN: D.rows.tam.filter(function (r) { return r.big && r.bt > 0; }).length,
      bmKnown: D.rows.tam.filter(function (r) { return r.bm != null; }).length
    };
  });

  // ------------------------------------------------------------------ derivations (called inside RBX.data.init)
  H.derive = H.derive || {};
  H.derive.sam = function (r, ctx) {
    if (!ctx.tcvMax) {
      var raw = RBX.data.decode(ctx.raw.sam);
      ctx.tcvMax = Math.max.apply(null, raw.map(function (x) { return x.tcv || 0; })) || 1;
      I.tcvMax = ctx.tcvMax;
    }
    r.pr = r.tcv != null ? 1 : 0;
    r.sv = r.pr ? Math.sqrt(r.tcv / ctx.tcvMax) : 0;
    r.sk = (6 - r.t) * 1e8 - (r.tcv || 0) + (r.pr ? 0 : 1e9);
    r.gsp = I.gsp(r.g);
  };
  H.derive.tam = function (r) { r.big = (r.kw || 0) >= 10000 ? 1 : 0; };
  H.props = H.props || {};
  H.props.tam = function (r) { return { big: r.big }; };

  // ------------------------------------------------------------------ extra filter dimensions (hidden sets persist across views)
  RBX.filters.dims.sam.push({ set: 'pricing', prop: 'pr', values: [1, 0] });
  RBX.filters.dims.hydro.push({ set: 'export', prop: 'exp', rowProp: 'expc', values: [0, 1] });
  RBX.filters.dims.tam.push({ set: 'scale', prop: 'big', values: [0, 1] });

  H.filterLabel = function (r, set) {
    if (set === 'pricing') return r.pr ? 'priced sites' : 'sites awaiting a BM figure';
    if (set === 'export') return r.expc ? 'no-export sites' : 'export-limited sites';
    if (set === 'scale') return 'sites of 10 MW and over';
    return '';
  };

  // ------------------------------------------------------------------ tooltip, size key, search, order, register
  var baseTip = H.tooltip;
  H.tooltip = function (r) {
    var s = baseTip ? baseTip(r) : '';
    if (r.kind === 'sam') return s + (r.pr ? ' · ' + I.money2(r.tcv) + ' TCV' : ' · Awaiting BM figure');
    if (r.kind === 'hydro' && r.tcv != null) return s + ' · ' + I.money2(r.tcv) + ' TCV';
    if (r.kind === 'tam') return s + (r.bt > 0 ? ' · ' + U.abbr(r.pot) + ' potential' : ' · no BM revenue');
    return s;
  };
  var baseSv = H.sizeValue, baseSl = H.sizeLabel;
  H.sizeValue = function (view, v) { return view === 'sam' ? Math.sqrt(v / I.tcvMax) : baseSv(view, v); };
  H.sizeLabel = function (view, v) { return view === 'sam' ? '£' + U.num(v / 1e6, 0) + 'M' : baseSl(view, v); };
  H.searchFields = function (r) {
    if (r.kind !== 'sam') return [];
    var f = r.dev && r.dev !== r.op ? [[r.dev, 0.7]] : [];
    if (r.opSt) f.push([r.opSt, 0.3]);
    return f;
  };
  /** DI1: a short factual company status ("in liquidation") as a muted tag, never inside the operator name. */
  I.opTag = function (r) { return r && r.opSt ? ' <span class="op-st">' + U.esc(r.opSt) + '</span>' : ''; };
  H.searchTag = function (r) { return r.kind === 'sam' && r.opSt ? I.opTag(r) : ''; };
  H.stepOrder = function (kind, rows) {
    if (kind === 'sam' || kind === 'hydro') {
      return rows.slice().sort(function (a, b) { return ((b.tcv != null) - (a.tcv != null)) || (b.tcv || 0) - (a.tcv || 0) || (b.kw || 0) - (a.kw || 0); });
    }
    return rows.slice().sort(function (a, b) { return (b.kw || 0) - (a.kw || 0); });
  };
  H.registerRow = function (o, r) {
    o.rank = r.rank;
    o.ref = r.rank; // the register's Ref column and order use the v1 rank in the investor build
    if (r.regoRaw) o.rego_status = r.regoRaw;
    if (r.opSt) o.op_status = r.opSt;   // DI1: company status kept out of the name, shown as a muted tag
    return o;
  };
})();
