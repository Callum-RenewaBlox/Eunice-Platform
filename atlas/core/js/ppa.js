/* RenewaBlox Atlas · PPA & Price Benchmark module.
   Shared by both audience builds. Public API:
     RBX.ppa.mount(rootEl, ctx) -> { refresh(), setTheme(name), destroy(), setFilter(partial),
                                     getState(), showSite(keyOrPostcode), scrollToSection(name) }
     RBX.ppa.check(prices)       -> [] or a list of copy/number mismatches (for build-time asserts)
   ctx = { prices, register, audience:'client'|'investor', theme:'paper'|'night',
           onChips(fn), onSiteClick(fn), onChange(fn), util, copy }
   All colour comes from the design tokens (tokens.css) plus the .rbx-ppa palette in ppa.css. */
(function () {
  'use strict';
  var RBX = window.RBX = window.RBX || {};
  var SVGNS = 'http://www.w3.org/2000/svg';
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var MINUS = '−';
  var seq = 0;

  /* ------------------------------------------------------------------ copy (verbatim from v1) */
  var COPY = {
    kicker: 'PPA & Price Benchmark',
    deck: 'At 3% CPI, the guaranteed FiT export rate overtakes the forward curve by 2028',
    intro: "Where each SAM site's export sits against the GB market. Realised prices are settlement data; the forward curve is exchange settlement; the FiT export tariff is a published statutory rate. No contracted PPA price is shown anywhere — those are private bilateral contracts and are not obtainable from any source.",
    asOf: 'Data as of',
    tiles: [
      { label: 'Realised baseload · 12m', note: 'Elexon MID, Aug 25 – Jul 26' },
      { label: 'Winter 2026 forward', note: '+47% vs last 12 months' },
      { label: 'Cal-2028 forward', note: 'below the CPI-linked FiT tariff' },
      { label: 'FiT standard export', note: 'statutory, CPI-linked, guaranteed' },
      { label: 'Winter / summer spread', note: 'Win-26 vs Sum-27 — AD runs flat' }
    ],
    priceTitle: 'GB baseload: realised, forward, and the guaranteed alternative',
    priceCap: 'Monthly realised day-ahead baseload against exchange-settled forward blocks, both in p/kWh. The dashed rule is the FiT standard export tariff every FiT site can fall back to.',
    legend: ['Realised — Elexon MID (EPEX)', 'Forward blocks — Montel / EEX, 11 Aug 2026', 'FiT standard export tariff (7.64p, CPI-linked)'],
    priceAria: 'GB baseload realised and forward prices in pence per kilowatt hour against the FiT standard export tariff',
    crossover: '<b>The crossover.</b> The FiT standard export tariff is 39% below the Winter-2026 forward — badly out of the money this winter. But it rises with CPI while the curve falls away: at 3% inflation it reaches ~8.11 p/kWh by 2028 against a Cal-2028 forward of 7.74 p/kWh, about <b>5% above market</b>. On today\'s curve, a long fixed PPA signed now at any discount to Cal-2028 is worse than the guaranteed fallback. The CPI rate is an assumption, not a forecast — the crossover date moves with it.',
    howTitle: 'How to read this chart',
    how: [
      'One point per month: realised day-ahead baseload.',
      'Each bar spans the delivery period of a forward block, labelled with its price.',
      'The FiT standard export tariff today — the guaranteed fallback.',
      'The same tariff rising with CPI at the assumed 3% a year.'
    ],
    howHint: 'Hover or tap the chart, or focus it and use ← →, to read each month and block.',
    fClass: 'Export arrangement', fOff: 'Certificate counterparty', fStatus: 'Generating status',
    fSearch: 'Find a site', fSearchPh: 'operator, town, postcode', fReset: 'Reset', fAll: 'All', fToggle: 'Filters',
    cpTitle: 'Who holds the certificates',
    cpCap: 'Capacity by the largest <em>external</em> certificate holder for each site, from Ofgem certificate history. A supplier holding a site’s REGOs is strong evidence it buys the power — but certificates can trade separately, so treat this as inference, not proof. Most generators also retain a share of their own certificates alongside a supplier relationship; that retention is shown as “+self” in the register rather than replacing the supplier. “Generator is sole holder” means no external party appears at all — genuinely unbundled.',
    cpHint: 'Select a bar to filter the register to that counterparty.',
    regTitle: 'Site register',
    regCap: 'Every SAM site with its observed export arrangement, counterparty, current FiT generation tariff and subsidy end date. Click a column to sort.',
    showMap: 'Show on map ›',
    empty: 'No sites match these filters.',
    showTable: 'Show data table', hideTable: 'Hide data table',
    provenance: '<b>Provenance.</b> Realised prices — Elexon BMRS Market Index Data, APXMIDP feed, 70,085 half-hourly settlement records Aug 2024–Jul 2026 (the N2EX feed reports zero volume and is excluded). Forward curve — Montel, EEX UK power futures, previous-settlement column, snapshot 11 Aug 2026. Export arrangement and FiT tariffs — Ofgem Feed-in Tariff Installation Report, March 2026; 128 of 129 sites matched on outcode, capacity, commissioning date and local authority. Counterparty — Ofgem Renewable Energy Register, REGO Accredited Stations and REGO Certificates (159 MB, 777,188 rows), current-holder field for the most recent output period. <b>Not shown, because it does not exist publicly:</b> contracted PPA prices for the 108 negotiated sites. Sourcing a discount-to-baseload benchmark is the remaining gap. Forward curve and counterparty data are point-in-time snapshots and need re-pulling to stay current.'
  };
  var SOLE = 'Generator is sole holder', NONE = 'Not identified';

  /* export arrangement classes (accepts v1 labels, short labels or codes) */
  var CLASSES = {
    neg: { label: 'Negotiated PPA', full: 'Negotiated export PPA', o: 0 },
    fit: { label: 'FiT standard', full: 'FiT standard export tariff (no PPA)', o: 1 },
    btm: { label: 'Behind meter', full: 'No export — behind the meter', o: 2 },
    unk: { label: 'Unknown', full: 'Unknown — no FiT match', o: 3 }
  };
  function classOf(v) {
    var s = String(v == null ? '' : v).toLowerCase();
    if (!s || /^unk/.test(s)) return 'unk';
    if (/negotiat|^neg/.test(s)) return 'neg';
    if (/behind|^btm|^bhd|no export/.test(s)) return 'btm';
    if (/fit|standard|^std/.test(s)) return 'fit';
    return 'unk';
  }
  /* REGO status: code a (active) / w (declining) / c (no recent) / n (no certificates).
     The label shown is always the label the build supplied (client rows arrive softened). */
  var ST_ORDER = { a: 0, w: 1, c: 2, n: 3 };
  var ST_SOFT = { a: 'Active', w: 'Certificates declining', c: 'No recent certificates', n: 'No REGO certificates' };
  /* neutral codes only (the build ships `rego` as active / declining / ceased / none; a/w/c/n also accepted) */
  var ST_CODE = { active: 'a', a: 'a', declining: 'w', w: 'w', ceased: 'c', c: 'c', none: 'n', n: 'n' };
  function statusOf(v) {
    var s = String(v == null ? '' : v).toLowerCase();
    return ST_CODE[s] || 'n';
  }
  function statusLabel(v, code) {
    if (v == null || v === '') return ST_SOFT.n;
    var s = String(v);
    /* bare codes (no spaces, e.g. "declining", "no_recent") get the public wording */
    if (!/\s/.test(s) && !/^active$/i.test(s) && !/\//.test(s)) return ST_SOFT[code];
    return s;
  }

  /* ------------------------------------------------------------------ helpers */
  function escF(s) {
    return s == null ? '' : String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  /* units / mixed-case acronyms keep their case under text-transform:uppercase (.nc in base.css) */
  function caseSafe(s) { return escF(s).replace(/\b(kW|MW|GW|kWh|MWh|FiT|EfW)\b/g, '<span class="nc">$1</span>'); }
  function first() { for (var i = 0; i < arguments.length; i++) if (arguments[i] !== undefined) return arguments[i]; return undefined; }
  function num(v) { if (v == null || v === '') return null; var n = +v; return isFinite(n) ? n : null; }
  function fmtInt(n) { return n == null ? '' : Math.round(n).toLocaleString('en-GB'); }
  function signed(n) { return n > 0 ? '+' + n : n < 0 ? MINUS + Math.abs(n) : '±0'; }
  function mIdx(m) { var p = String(m).split('-'); return (+p[0]) * 12 + (+p[1] - 1); }
  function mLabel(m) { var p = String(m).split('-'); return MON[+p[1] - 1] + ' ' + String(p[0]).slice(2); }
  function idxLabel(i) { return MON[((i % 12) + 12) % 12] + ' ' + String(Math.floor(i / 12)).slice(2); }
  function fmtEnd(d) { if (!d) return null; var p = String(d).split('-'); if (p.length < 2) return String(d); return MON[+p[1] - 1] + ' ' + p[0]; }
  function fmtAsOf(d) { if (!d) return ''; var p = String(d).split('-'); return (+p[2] || '') + ' ' + MON[+p[1] - 1] + ' ' + p[0]; }
  function compact(pc) { return String(pc || '').replace(/\s+/g, '').toUpperCase(); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function rafThrottle(fn) {
    var q = false;
    return function () { if (q) return; q = true; (window.requestAnimationFrame || setTimeout)(function () { q = false; fn(); }); };
  }
  function svg(tag, attrs, parent) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  /* display-casing: only fully upper-case words of 4+ letters are rewritten, so brands such as
     "EDF", "SmartestEnergy" or "UK" survive; the rule is idempotent on already-cleaned names */
  var WORD_FIX = { LTD: 'Ltd', AND: 'and', THE: 'the', OF: 'of', FOR: 'for', MCCAIN: 'McCain', LLP: 'LLP', PLC: 'plc' };
  var WORD_KEEP = { ENGIE: 1, SARIA: 1, EGGER: 1, TESCO: 1 };
  function displayCase(s) {
    if (s == null) return s;
    s = String(s);
    if (!/[A-Z]{4,}/.test(s)) return s;
    var firstWord = true;
    return s.replace(/[A-Za-z]+/g, function (w) {
      var out = w;
      if (w === w.toUpperCase()) {
        if (WORD_FIX[w] && !(firstWord && /^(AND|THE|OF|FOR)$/.test(w))) out = WORD_FIX[w];
        else if (w.length >= 4 && !WORD_KEEP[w]) out = w.charAt(0) + w.slice(1).toLowerCase();
      }
      firstWord = false;
      return out;
    });
  }
  var TOWN_LOWER = { next: 1, the: 1, on: 1, le: 1, under: 1, upon: 1, super: 1, in: 1, by: 1, en: 1, de: 1, sur: 1 };
  function townCase(s) {
    if (s == null) return null;
    s = String(s).trim();
    if (!s || /^(none|null|data not available|n\/a)$/i.test(s)) return null;
    return s.split(/\s+/).map(function (word) {
      var parts = word.split('-');
      return parts.map(function (p, i) {
        var l = p.toLowerCase();
        if (i > 0 && i < parts.length - 1 && TOWN_LOWER[l]) return l;
        return l.charAt(0).toUpperCase() + l.slice(1);
      }).join('-');
    }).join(' ');
  }
  function cleanName(s) {
    if (s == null) return null;
    s = String(s).trim();
    if (!s) return null;
    s = s.replace(/\s*\(\s*supplier\s*\)\s*$/i, '')
      .replace(/\s+-\s+supplier\s+-\s+SUP\d+\s*$/i, '')
      .replace(/Internatinal/g, 'International')
      .replace(/\b(Limited|Ltd)\.?\s+(Limited|Ltd)\.?$/i, '$1');
    return displayCase(s);
  }

  /* ------------------------------------------------------------------ data normalisation */
  function normPrices(p) {
    p = p || {};
    var kpi = p.kpi || {};
    var fit = num(first(kpi.fit, p.fit));
    var fwd = (p.fwd || []).map(function (b) { return { k: String(b.k), from: b.from, to: b.to, p: +b.p }; });
    var realised = (p.realised || []).map(function (r) { return { m: r.m, p: +r.p }; });
    var spread = p.spread && p.spread.value != null ? p.spread : null;
    return {
      realised: realised, fwd: fwd,
      kpi: { base12: num(kpi.base12), win26: num(kpi.win26), cal28: num(kpi.cal28), fit: fit, asOf: kpi.asOf || null },
      fit: fit == null ? 7.64 : fit,
      cpi: num(p.cpi) == null ? 0.03 : +p.cpi,
      spread: spread ? { value: +spread.value, note: spread.note || null } : { value: 49, note: null }
    };
  }
  function normRows(list, aud) {
    return (list || []).map(function (r, i) {
      var kw = num(first(r.installed_kw, r.kw));
      var offRaw = first(r.offtaker, r.off);
      var kind = 'ext', off = null;
      if (offRaw === true || /sole/i.test(String(offRaw == null ? '' : offRaw))) { kind = 'sole'; off = SOLE; }
      else if (offRaw == null || offRaw === false || offRaw === '' || /^(none|not identified)$/i.test(String(offRaw))) { kind = 'none'; off = NONE; }
      else off = cleanName(offRaw);
      var selfCerts = (num(r.self_certs) || 0) > 0 || r.self === true;
      var ord = num(r.ref);
      var op = displayCase(first(r.operator, r.op) || '');
      var town = townCase(r.town);
      var pc = first(r.postcode, r.pc) || '';
      var stRaw = first(r.rego_status, r.rego);
      var stCode = statusOf(r.rego);
      var cls = classOf(first(r.ppa_class, r.ppa));
      var site = r.site || '';
      var opSt = r.op_status || null;       // audience modules may pass a short company status (shown muted under the operator)
      var hay = [op, first(r.operator, r.op), opSt, town, r.town, pc, compact(pc), site, off, offRaw === true ? '' : offRaw]
        .filter(function (x) { return x != null && x !== ''; }).join(' \u0001 ').toLowerCase();
      return {
        i: i, ord: ord == null ? i + 1 : ord, op: op || '—', opSt: opSt, town: town, pc: pc, key: r.key || compact(pc), site: site,
        kw: kw, comm: num(first(r.commissioned, r.comm)), cls: cls, kind: kind, off: off, self: selfCerts,
        fitGen: num(first(r.gen_tariff_p_kwh_2026_27, r.fitGen)),
        fitEnd: first(r.fit_end_date, r.fitEnd) || null,
        yrs: num(first(r.yrs_subsidy_left, r.yrsLeft)),
        st: stCode, stLabel: statusLabel(stRaw, stCode),
        hay: hay, hayNs: hay.replace(/\s+/g, ''), src: r
      };
    });
  }

  /* ------------------------------------------------------------------ consistency check (build QA) */
  function check(pricesIn) {
    var P = normPrices(pricesIn), k = P.kpi, out = [];
    function eq(label, got, want) { if (String(got) !== String(want)) out.push(label + ': copy says ' + want + ', data gives ' + got); }
    var last12 = P.realised.slice(-12);
    if (last12.length) eq('base12 note months', mLabel(last12[0].m) + ' – ' + mLabel(last12[last12.length - 1].m), 'Aug 25 – Jul 26');
    if (k.win26 && k.base12) eq('win26 vs base12', '+' + Math.round((k.win26 / k.base12 - 1) * 100) + '%', '+47%');
    if (k.win26) eq('crossover below', Math.round((1 - P.fit / k.win26) * 100) + '%', '39%');
    var fc = P.fit * Math.pow(1 + P.cpi, 2);
    eq('FiT +CPI 2028', fc.toFixed(2), '8.11');
    if (k.cal28) eq('crossover above', Math.round((fc / k.cal28 - 1) * 100) + '%', '5%');
    eq('CPI', Math.round(P.cpi * 100) + '%', '3%');
    eq('FiT', P.fit.toFixed(2), '7.64');
    return out;
  }

  /* ------------------------------------------------------------------ mount */
  function mount(host, ctx) {
    if (!host) throw new Error('RBX.ppa.mount: missing root element');
    ctx = ctx || {};
    var util = ctx.util || RBX.util || null;
    var esc = util && typeof util.esc === 'function' ? util.esc : escF;
    var C = {}; for (var ck in COPY) C[ck] = COPY[ck];
    if (ctx.copy) for (var ok in ctx.copy) C[ok] = ctx.copy[ok];
    var aud = ctx.audience === 'investor' ? 'investor' : 'client';
    var theme = ctx.theme === 'night' ? 'night' : 'paper';
    var P = normPrices(ctx.prices);
    var ROWS = normRows(ctx.register, aud);
    var TOTAL = ROWS.length;
    var id = 'rbxppa' + (++seq);
    var st = { cls: '', off: '', status: '', q: '', sort: { key: 'ord', dir: 1 } };
    var ui = { fopen: false, tables: {}, open: {}, pinned: false, tipIdx: -1, mobile: false, destroyed: false };
    var cleanups = [];
    function on(el, ev, fn, opt) { if (!el) return; el.addEventListener(ev, fn, opt); cleanups.push(function () { el.removeEventListener(ev, fn, opt); }); }

    var root = document.createElement('div');
    root.className = 'rbx-ppa';
    root.setAttribute('data-ppa-theme', theme);
    root.setAttribute('data-ppa-aud', aud);
    host.appendChild(root);

    /* ---------- skeleton */
    var t = P.kpi;
    var tileVals = [
      [t.base12, 'p/kWh'], [t.win26, 'p/kWh'], [t.cal28, 'p/kWh'], [t.fit != null ? t.fit : P.fit, 'p/kWh'], [P.spread.value, '%']
    ];
    var tilesHtml = C.tiles.map(function (tl, i) {
      var v = tileVals[i][0], unit = tileVals[i][1];
      var vs = v == null ? '—' : unit === '%' ? String(Math.round(v)) : (+v).toFixed(2);
      var note = i === 4 && P.spread.note ? P.spread.note : tl.note;
      return '<div class="ppa-tile" role="listitem"><div class="ppa-eyebrow ppa-tl">' + caseSafe(tl.label) + '</div>' +
        '<div class="ppa-fig num">' + esc(vs) + '<small>' + (unit === '%' ? '%' : ' ' + unit) + '</small></div>' +
        '<div class="ppa-note">' + esc(note) + '</div></div>';
    }).join('');

    function swatch(kind) {
      var s = '<svg class="ppa-sw" width="30" height="12" viewBox="0 0 30 12" aria-hidden="true" focusable="false">';
      if (kind === 'real') s += '<line x1="1" y1="6" x2="29" y2="6" class="sw-real"/><circle cx="15" cy="6" r="2.4" class="sw-real-dot"/>';
      else if (kind === 'fwd') s += '<line x1="3" y1="6" x2="27" y2="6" class="sw-fwd"/><line x1="3" y1="3" x2="3" y2="9" class="sw-fwd-cap"/><line x1="27" y1="3" x2="27" y2="9" class="sw-fwd-cap"/>';
      else if (kind === 'fit') s += '<line x1="1" y1="6" x2="29" y2="6" class="sw-fit"/>';
      else if (kind === 'cpi') s += '<line x1="1" y1="8" x2="29" y2="4" class="sw-cpi"/>';
      return s + '</svg>';
    }

    root.innerHTML =
      '<div class="ppa-page">' +
      '<header class="ppa-intro">' +
      (C.standfirst ? '<p class="ppa-standfirst">' + esc(C.standfirst) + '</p>' : '') +
      '<h2 class="ppa-kicker">' + esc(C.kicker) + '</h2>' +
      '<p class="ppa-deck">' + esc(C.deck) + '</p>' +
      '<p class="ppa-lede">' + esc(C.intro) + '</p>' +
      '</header>' +
      '<section class="ppa-tiles-wrap" aria-label="Price benchmarks">' +
      (P.kpi.asOf ? '<p class="ppa-asof">' + esc(C.asOf) + ' <time datetime="' + esc(P.kpi.asOf) + '">' + esc(fmtAsOf(P.kpi.asOf)) + '</time></p>' : '') +
      '<div class="ppa-tiles" role="list">' + tilesHtml + '</div></section>' +

      '<div class="ppa-row ppa-row-price" data-sec="price">' +
      '<section class="ppa-panel ppa-price" aria-labelledby="' + id + '-pt">' +
      '<h3 class="ppa-h3" id="' + id + '-pt">' + esc(C.priceTitle) + '</h3>' +
      '<p class="ppa-cap">' + esc(C.priceCap) + '</p>' +
      '<ul class="ppa-legend">' +
      '<li>' + swatch('real') + '<span>' + esc(C.legend[0]) + '</span></li>' +
      '<li>' + swatch('fwd') + '<span>' + esc(C.legend[1]) + '</span></li>' +
      '<li>' + swatch('fit') + '<span>' + esc(C.legend[2]) + '</span></li></ul>' +
      '<div class="ppa-chart ppa-pricechart" tabindex="0" role="img" aria-label="' + esc(C.priceAria) + '" aria-describedby="' + id + '-dtp">' +
      '<svg class="ppa-svg" aria-hidden="true" focusable="false"></svg>' +
      '<div class="ppa-tip" hidden></div></div>' +
      '<div class="sr-only" aria-live="polite" data-live="price"></div>' +
      '<button type="button" class="ppa-btn ppa-dt-toggle" aria-expanded="false" aria-controls="' + id + '-dtp" data-dt="price">' + esc(C.showTable) + '</button>' +
      '<div class="ppa-datatable" id="' + id + '-dtp" hidden></div>' +
      '</section>' +
      '<aside class="ppa-side">' +
      '<div class="ppa-callout">' + C.crossover + '</div>' +
      '<div class="ppa-howto"><h4 class="ppa-eyebrow">' + esc(C.howTitle) + '</h4><ul>' +
      '<li>' + swatch('real') + '<span>' + esc(C.how[0]) + '</span></li>' +
      '<li>' + swatch('fwd') + '<span>' + esc(C.how[1]) + '</span></li>' +
      '<li>' + swatch('fit') + '<span>' + esc(C.how[2]) + '</span></li>' +
      '<li>' + swatch('cpi') + '<span>' + esc(C.how[3]) + '</span></li></ul>' +
      '<p class="ppa-hint">' + esc(C.howHint) + '</p></div>' +
      '</aside></div>' +

      '<div class="ppa-filters" role="search" aria-label="Filter the site register">' +
      '<div class="ppa-fbar">' +
      '<button type="button" class="ppa-btn ppa-ftoggle" aria-expanded="false" aria-controls="' + id + '-ff">' + esc(C.fToggle) + ' <span class="ppa-fcount"></span></button>' +
      '<p class="ppa-result num" aria-live="polite"></p></div>' +
      '<div class="ppa-ffields" id="' + id + '-ff">' +
      '<div class="ppa-field"><label for="' + id + '-fc">' + esc(C.fClass) + '</label><select id="' + id + '-fc" data-f="cls"></select></div>' +
      '<div class="ppa-field"><label for="' + id + '-fo">' + esc(C.fOff) + '</label><select id="' + id + '-fo" data-f="off"></select></div>' +
      '<div class="ppa-field"><label for="' + id + '-fs">' + esc(C.fStatus) + '</label><select id="' + id + '-fs" data-f="status"></select></div>' +
      '<div class="ppa-field ppa-field-q"><label for="' + id + '-fq">' + esc(C.fSearch) + '</label><input id="' + id + '-fq" type="search" autocomplete="off" spellcheck="false" placeholder="' + esc(C.fSearchPh) + '"></div>' +
      '<button type="button" class="ppa-btn ppa-reset">' + esc(C.fReset) + '</button>' +
      '</div></div>' +

      '<section class="ppa-panel ppa-cp" data-sec="counterparty" aria-labelledby="' + id + '-ct">' +
      '<div class="ppa-cp-text">' +
      '<h3 class="ppa-h3" id="' + id + '-ct">' + esc(C.cpTitle) + '</h3>' +
      '<p class="ppa-cap">' + C.cpCap + '</p>' +
      '<p class="ppa-count num" data-count="cp"></p>' +
      '<ul class="ppa-cp-key"><li><i class="k-bar"></i>External supplier</li><li><i class="k-bar k-sole"></i>' + esc(SOLE) + '</li><li><i class="k-bar k-none"></i>' + esc(NONE) + '</li></ul>' +
      '<p class="ppa-hint">' + esc(C.cpHint) + '</p>' +
      '</div>' +
      '<div class="ppa-cp-chart">' +
      '<div class="ppa-chart ppa-bars" role="group" aria-label="Installed capacity by certificate counterparty"></div>' +
      '<div class="ppa-tip ppa-tip-cp" hidden></div>' +
      '<button type="button" class="ppa-btn ppa-dt-toggle" aria-expanded="false" aria-controls="' + id + '-dtc" data-dt="cp">' + esc(C.showTable) + '</button>' +
      '<div class="ppa-datatable" id="' + id + '-dtc" hidden></div>' +
      '</div></section>' +

      '<section class="ppa-panel ppa-reg" data-sec="register" aria-labelledby="' + id + '-rt">' +
      '<div class="ppa-reg-headtext"><div><h3 class="ppa-h3" id="' + id + '-rt">' + esc(C.regTitle) + '</h3>' +
      '<p class="ppa-cap">' + esc(C.regCap) + '</p></div>' +
      '<p class="ppa-count num" data-count="reg"></p></div>' +
      '<div class="ppa-reg-sort"><label for="' + id + '-rs">Sort by</label><select id="' + id + '-rs"></select>' +
      '<button type="button" class="ppa-btn ppa-sortdir" aria-label="Reverse sort order"></button></div>' +
      '<div class="ppa-reg-body"></div>' +
      '</section>' +

      '<footer class="ppa-prov"><p>' + C.provenance + '</p></footer>' +
      '</div>';

    function q(sel) { return root.querySelector(sel); }
    var elPrice = q('.ppa-pricechart'), elSvg = q('.ppa-pricechart svg'), elTip = q('.ppa-pricechart .ppa-tip');
    var elLive = q('[data-live="price"]');
    var elFilters = q('.ppa-filters'), elResult = q('.ppa-result'), elFCount = q('.ppa-fcount');
    var elBars = q('.ppa-bars'), elTipCp = q('.ppa-tip-cp');
    var elCpCount = q('[data-count="cp"]'), elRegCount = q('[data-count="reg"]');
    var elRegBody = q('.ppa-reg-body'), elSortSel = q('#' + id + '-rs'), elSortDir = q('.ppa-sortdir');
    var sel = { cls: q('#' + id + '-fc'), off: q('#' + id + '-fo'), status: q('#' + id + '-fs') };
    var elQ = q('#' + id + '-fq');

    /* ---------- register columns */
    var COLS = [
      { k: 'ord', label: aud === 'client' ? 'Ref' : '#', num: true, w: 50 },
      { k: 'op', label: 'Operator', flex: 0.55, min: 150 },
      { k: 'town', label: 'Town', w: 110 },
      { k: 'kw', label: 'kW', num: true, w: 64 },
      { k: 'comm', label: 'Comm.', num: true, w: 60 },
      { k: 'cls', label: 'Export arrangement', w: 124 },
      { k: 'off', label: 'Supplier (largest external REGO holder)', flex: 0.45, min: 140 },
      { k: 'fitGen', label: 'FiT gen p/kWh', num: true, w: 76 },
      { k: 'fitEnd', label: 'FiT ends', w: 80 },
      { k: 'yrs', label: 'Yrs left', num: true, w: 94 },
      { k: 'st', label: 'Status', w: 166 }
    ];
    var FIXED_W = 0, FLEX_MIN = 0;
    COLS.forEach(function (c) { if (c.w) FIXED_W += c.w; else FLEX_MIN += c.min; });
    var TABLE_MIN = FIXED_W + FLEX_MIN;
    var YRS_MAX = 10;
    elSortSel.innerHTML = COLS.map(function (c) { return '<option value="' + c.k + '">' + esc(c.label) + '</option>'; }).join('');

    /* ---------- filter options */
    function fillSelects() {
      var clsSeen = {}, offSeen = {}, stSeen = {};
      ROWS.forEach(function (r) {
        clsSeen[r.cls] = 1;
        if (r.kind === 'ext') offSeen[r.off] = 1;
        if (!stSeen[r.st]) stSeen[r.st] = r.stLabel;
      });
      sel.cls.innerHTML = '<option value="">' + esc(C.fAll) + '</option>' + Object.keys(clsSeen)
        .sort(function (a, b) { return CLASSES[a].o - CLASSES[b].o; })
        .map(function (c) { return '<option value="' + c + '">' + esc(CLASSES[c].full) + '</option>'; }).join('');
      var names = Object.keys(offSeen).sort(function (a, b) { return a.localeCompare(b, 'en-GB', { sensitivity: 'base' }); });
      var hasSole = ROWS.some(function (r) { return r.kind === 'sole'; }), hasNone = ROWS.some(function (r) { return r.kind === 'none'; });
      sel.off.innerHTML = '<option value="">' + esc(C.fAll) + '</option>' +
        names.map(function (n) { return '<option value="' + esc(n) + '">' + esc(n) + '</option>'; }).join('') +
        (hasSole ? '<option value="__sole">' + esc(SOLE) + '</option>' : '') +
        (hasNone ? '<option value="__none">' + esc(NONE) + '</option>' : '');
      sel.status.innerHTML = '<option value="">' + esc(C.fAll) + '</option>' + Object.keys(stSeen)
        .sort(function (a, b) { return ST_ORDER[a] - ST_ORDER[b]; })
        .map(function (c) { return '<option value="' + c + '">' + esc(stSeen[c]) + '</option>'; }).join('');
    }
    function offKey(r) { return r.kind === 'sole' ? '__sole' : r.kind === 'none' ? '__none' : r.off; }

    function filtered() {
      var toks = st.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
      return ROWS.filter(function (r) {
        if (st.cls && r.cls !== st.cls) return false;
        if (st.off && offKey(r) !== st.off) return false;
        if (st.status && r.st !== st.status) return false;
        for (var i = 0; i < toks.length; i++) {
          if (r.hay.indexOf(toks[i]) < 0 && r.hayNs.indexOf(toks[i]) < 0) return false;
        }
        if (toks.length > 1) { /* postcode typed with a space: also try it joined */ }
        return true;
      });
    }
    function sortVal(r, k) {
      switch (k) {
        case 'op': return r.op && r.op !== '—' ? r.op : null;
        case 'cls': return CLASSES[r.cls].o;
        case 'off': return r.kind === 'ext' ? r.off : null;
        case 'st': return ST_ORDER[r.st];
        case 'fitEnd': return r.fitEnd;
        default: return r[k];
      }
    }
    function sorted(list) {
      var k = st.sort.key, d = st.sort.dir;
      return list.slice().sort(function (a, b) {
        var x = sortVal(a, k), y = sortVal(b, k);
        var xn = x == null || x === '', yn = y == null || y === '';
        if (xn && yn) return a.ord - b.ord;
        if (xn) return 1;
        if (yn) return -1;
        var c = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'en-GB', { sensitivity: 'base', numeric: true });
        if (c === 0) return a.ord - b.ord;
        return c * d;
      });
    }

    /* ---------- chips / result lines */
    function counts(list) {
      var kw = 0, ext = {};
      list.forEach(function (r) { kw += r.kw || 0; if (r.kind === 'ext') ext[r.off] = 1; });
      return { sites: list.length, mw: Math.round(kw / 100) / 10, counterparties: Object.keys(ext).length };
    }

    /* ---------- counterparty chart */
    var cpList = [];
    function renderCp(list) {
      var agg = {};
      list.forEach(function (r) {
        var key = offKey(r);
        if (!agg[key]) agg[key] = { key: key, name: r.off, kind: r.kind, c: 0, mw: 0 };
        agg[key].c++; agg[key].mw += (r.kw || 0) / 1000;
      });
      cpList = Object.keys(agg).map(function (k) { return agg[k]; }).sort(function (a, b) {
        if (a.kind === 'none' && b.kind !== 'none') return 1;
        if (b.kind === 'none' && a.kind !== 'none') return -1;
        return b.mw - a.mw || a.name.localeCompare(b.name, 'en-GB');
      });
      var nExt = cpList.filter(function (d) { return d.kind === 'ext'; }).length;
      elCpCount.textContent = nExt + ' counterpart' + (nExt === 1 ? 'y' : 'ies') + ' across ' + list.length + ' site' + (list.length === 1 ? '' : 's');
      if (!cpList.length) {
        elBars.innerHTML = '<p class="ppa-empty">' + esc(C.empty) + '</p>';
      } else {
        var max = Math.max.apply(null, cpList.map(function (d) { return d.mw; })) || 1;
        elBars.innerHTML = cpList.map(function (d, i) {
          var pressed = st.off === d.key;
          return '<button type="button" class="ppa-cp-row" data-i="' + i + '" aria-pressed="' + pressed + '" ' +
            'aria-label="' + esc(d.name + ', ' + d.mw.toFixed(1) + ' MW, ' + d.c + ' site' + (d.c === 1 ? '' : 's')) + '">' +
            '<span class="cp-name" title="' + esc(d.name) + '">' + esc(d.name) + '</span>' +
            '<span class="cp-track"><span class="cp-bar' + (d.kind === 'sole' ? ' is-sole' : d.kind === 'none' ? ' is-none' : '') + '" style="width:' + Math.max(0.6, d.mw / max * 100).toFixed(2) + '%"></span></span>' +
            '<span class="cp-val num">' + d.mw.toFixed(1) + ' MW</span></button>';
        }).join('');
      }
      q('#' + id + '-dtc').innerHTML = '<table><thead><tr><th scope="col">Counterparty</th><th scope="col" class="num">Sites</th><th scope="col" class="num">MW</th></tr></thead><tbody>' +
        cpList.map(function (d) { return '<tr><td>' + esc(d.name) + '</td><td class="num">' + d.c + '</td><td class="num">' + d.mw.toFixed(1) + '</td></tr>'; }).join('') + '</tbody></table>';
    }
    function showCpTip(btn) {
      var d = cpList[+btn.getAttribute('data-i')]; if (!d) return;
      elTipCp.innerHTML = '<b>' + esc(d.name) + '</b><br>' + d.mw.toFixed(1) + ' MW · ' + d.c + ' site' + (d.c === 1 ? '' : 's');
      elTipCp.hidden = false;
      var wrap = elTipCp.parentNode.getBoundingClientRect(), bar = btn.querySelector('.cp-bar').getBoundingClientRect(), row = btn.getBoundingClientRect();
      var tw = elTipCp.offsetWidth, th = elTipCp.offsetHeight;
      var x = bar.right - wrap.left + 10;
      if (x + tw > wrap.width) x = Math.max(0, bar.right - wrap.left - tw - 10);
      var y = row.top - wrap.top - th - 4;
      if (y < 0) y = row.bottom - wrap.top + 4;
      elTipCp.style.left = x + 'px'; elTipCp.style.top = y + 'px';
    }
    function hideCpTip() { elTipCp.hidden = true; }

    /* ---------- register */
    function chip(r) {
      var c = CLASSES[r.cls];
      return '<span class="ppa-chip chip-' + r.cls + '" title="' + esc(c.full) + '">' + esc(c.label) + '</span>';
    }
    function supplierCell(r) {
      if (r.kind === 'sole') return '<i class="sup-flag">sole holder</i>';
      if (r.kind === 'none') return '<i class="sup-flag is-none">not identified</i>';
      return '<span class="sup-name" title="' + esc(r.off) + '">' + esc(r.off) + '</span>' + (r.self ? ' <span class="sup-self">+self</span>' : '');
    }
    function runway(r) {
      if (r.yrs == null) return '<span class="ppa-na">—</span>';
      var w = clamp(r.yrs / YRS_MAX, 0, 1) * 100;
      return '<span class="yrs"><span class="yrs-v">' + r.yrs.toFixed(1) + '</span><span class="yrs-bar" aria-hidden="true"><i style="width:' + w.toFixed(1) + '%"></i></span></span>';
    }
    function statusCell(r) { return '<span class="ppa-status"><i class="dot dot-' + r.st + '" aria-hidden="true"></i>' + esc(r.stLabel) + '</span>'; }
    function na() { return '<span class="ppa-na">—</span>'; }
    function cell(r, k) {
      switch (k) {
        case 'ord': return '<span class="ref">' + esc(r.ord) + '</span>';
        case 'op': return '<span class="op" title="' + esc(r.op) + '">' + esc(r.op) + '</span>' + (r.opSt ? '<span class="op-st">' + esc(r.opSt) + '</span>' : '');
        case 'town': return r.town ? esc(r.town) : na();
        case 'kw': return r.kw != null ? fmtInt(r.kw) : na();
        case 'comm': return r.comm != null ? esc(r.comm) : na();
        case 'cls': return chip(r);
        case 'off': return supplierCell(r);
        case 'fitGen': return r.fitGen != null ? r.fitGen.toFixed(2) : na();
        case 'fitEnd': return r.fitEnd ? esc(fmtEnd(r.fitEnd)) : na();
        case 'yrs': return runway(r);
        case 'st': return statusCell(r);
      }
      return '';
    }
    function ariaSort(k) { return st.sort.key === k ? (st.sort.dir === 1 ? 'ascending' : 'descending') : 'none'; }
    function colgroup() {
      return '<colgroup>' + COLS.map(function (c) { return '<col' + (c.w ? ' style="width:' + c.w + 'px"' : '') + '>'; }).join('') + '</colgroup>';
    }
    function headRow(sr) {
      return '<tr>' + COLS.map(function (c) {
        var a = ariaSort(c.k), ind = a === 'ascending' ? '↑' : a === 'descending' ? '↓' : '';
        if (sr) return '<th scope="col" aria-sort="' + a + '">' + esc(c.label) + '</th>';
        return '<th scope="col" aria-sort="' + a + '" class="' + (c.num ? 'num ' : '') + 'c-' + c.k + '">' +
          '<button type="button" class="ppa-sort" data-k="' + c.k + '"><span>' + esc(c.label) + '</span><i class="ind" aria-hidden="true">' + ind + '</i></button></th>';
      }).join('') + '</tr>';
    }
    var regList = [];
    var clickable = typeof ctx.onSiteClick === 'function';
    function renderTable(list) {
      var body = list.map(function (r) {
        return '<tr data-key="' + esc(r.key) + '" data-i="' + r.i + '"' + (clickable ? ' tabindex="0"' : '') + '>' + COLS.map(function (c) {
          var inner = cell(r, c.k);
          if (c.k === 'st' && clickable) inner += '<span class="ppa-showmap" aria-hidden="true">' + esc(C.showMap) + '</span>';
          return '<td class="' + (c.num ? 'num ' : '') + 'c-' + c.k + '">' + inner + '</td>';
        }).join('') + '</tr>';
      }).join('');
      elRegBody.innerHTML =
        '<div class="reg-head" aria-hidden="false"><table class="reg-t">' + colgroup() + '<thead>' + headRow(false) + '</thead></table></div>' +
        '<div class="reg-scroll"><table class="reg-t" aria-labelledby="' + id + '-rt">' + colgroup() +
        '<thead class="sr-only">' + headRow(true) + '</thead><tbody>' + body + '</tbody></table>' +
        (list.length ? '' : '<p class="ppa-empty">' + esc(C.empty) + ' <button type="button" class="ppa-linkbtn" data-act="reset">' + esc(C.fReset) + '</button></p>') +
        '</div>';
      sizeTable();
    }
    function renderList(list) {
      elRegBody.innerHTML = '<ul class="reg-list">' + list.map(function (r) {
        var rid = id + '-rl' + r.i;
        return '<li class="rl-item" data-key="' + esc(r.key) + '" data-i="' + r.i + '">' +
          '<button type="button" class="rl-head" aria-expanded="false" aria-controls="' + rid + '">' +
          '<span class="rl-top"><span class="rl-op">' + esc(r.op) + '</span><span class="rl-kw num">' + (r.kw != null ? fmtInt(r.kw) + ' kW' : '—') + '</span></span>' +
          '<span class="rl-town">' + (r.town ? esc(r.town) : '—') + '</span>' +
          '<span class="rl-tags">' + chip(r) + statusCell(r) + '</span></button>' +
          '<div class="rl-more" id="' + rid + '" hidden><dl>' +
          '<div><dt>' + esc(COLS[0].label) + '</dt><dd class="num">' + esc(r.ord) + '</dd></div>' +
          '<div><dt>Comm.</dt><dd class="num">' + (r.comm != null ? esc(r.comm) : '—') + '</dd></div>' +
          '<div class="rl-wide"><dt>Supplier (largest external REGO holder)</dt><dd>' + supplierCell(r) + '</dd></div>' +
          '<div><dt>FiT gen p/kWh</dt><dd class="num">' + (r.fitGen != null ? r.fitGen.toFixed(2) : '—') + '</dd></div>' +
          '<div><dt>FiT ends</dt><dd>' + (r.fitEnd ? esc(fmtEnd(r.fitEnd)) : '—') + '</dd></div>' +
          '<div class="rl-wide"><dt>Yrs left</dt><dd>' + runway(r) + '</dd></div>' +
          '</dl>' + (clickable ? '<button type="button" class="ppa-btn rl-map">' + esc(C.showMap) + '</button>' : '') + '</div></li>';
      }).join('') + '</ul>' + (list.length ? '' : '<p class="ppa-empty">' + esc(C.empty) + ' <button type="button" class="ppa-linkbtn" data-act="reset">' + esc(C.fReset) + '</button></p>');
    }
    function sizeTable() {
      var sc = elRegBody.querySelector('.reg-scroll'); if (!sc) return;
      var w = Math.max(sc.clientWidth, TABLE_MIN), rem = w - FIXED_W;
      var widths = COLS.map(function (c) { return c.w || Math.max(c.min, Math.floor(rem * c.flex)); });
      var total = widths.reduce(function (a, b) { return a + b; }, 0);
      var tabs = elRegBody.querySelectorAll('table.reg-t');
      for (var i = 0; i < tabs.length; i++) {
        tabs[i].style.width = total + 'px';
        var cols = tabs[i].querySelectorAll('col');
        for (var j = 0; j < cols.length; j++) cols[j].style.width = widths[j] + 'px';
      }
      syncScroll();
    }
    function syncScroll() {
      var sc = elRegBody.querySelector('.reg-scroll'), hd = elRegBody.querySelector('.reg-head');
      if (!sc || !hd) return;
      hd.scrollLeft = sc.scrollLeft;
      var more = sc.scrollWidth - sc.clientWidth - sc.scrollLeft > 2;
      elRegBody.classList.toggle('is-scrolled', sc.scrollLeft > 0);
      elRegBody.classList.toggle('has-more', more);
    }

    /* ---------- render everything that depends on filters */
    function render() {
      var list = filtered();
      regList = sorted(list);
      var c = counts(list);
      elResult.textContent = c.sites + ' of ' + TOTAL + ' sites · ' + c.mw.toFixed(1) + ' MW · ' + c.counterparties + ' counterpart' + (c.counterparties === 1 ? 'y' : 'ies');
      elRegCount.textContent = c.sites + ' of ' + TOTAL + ' sites · ' + c.mw.toFixed(1) + ' MW';
      var nf = (st.cls ? 1 : 0) + (st.off ? 1 : 0) + (st.status ? 1 : 0) + (st.q.trim() ? 1 : 0);
      elFCount.textContent = nf ? '(' + nf + ')' : '';
      root.classList.toggle('has-filters', nf > 0);
      renderCp(list);
      if (ui.mobile) renderList(regList); else renderTable(regList);
      elSortSel.value = st.sort.key;
      elSortDir.textContent = st.sort.dir === 1 ? '↑ Asc' : '↓ Desc';
      if (typeof ctx.onChips === 'function') { try { ctx.onChips(c); } catch (e) { /* host callback */ } }
      if (typeof ctx.onChange === 'function') { try { ctx.onChange(getState()); } catch (e) { /* host callback */ } }
    }
    function syncControls() {
      sel.cls.value = st.cls; sel.off.value = st.off; sel.status.value = st.status;
      if (elQ.value !== st.q) elQ.value = st.q;
    }

    /* ---------- price chart */
    var chart = null;
    function drawPrice() {
      var W = Math.floor(elPrice.clientWidth);
      if (!W || W < 120) return;
      var H = Math.round(clamp(W * 0.42, 260, 400));
      var narrow = W < 600;
      var M = { l: 44, r: narrow ? 64 : 96, t: 34, b: 36 };
      var iw = W - M.l - M.r, ih = H - M.t - M.b;
      var s = elSvg;
      while (s.firstChild) s.removeChild(s.firstChild);
      s.setAttribute('width', W); s.setAttribute('height', H);
      s.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      elPrice.style.height = H + 'px';

      var real = P.realised, fwd = P.fwd;
      if (!real.length) return;
      var x0 = mIdx(real[0].m);
      var lastTo = fwd.length ? mIdx(fwd[fwd.length - 1].to) + 1 : mIdx(real[real.length - 1].m) + 1;
      var x1 = Math.max(lastTo, mIdx('2028-12') + 1);
      var yMin = 5, yMax = 14;
      var X = function (mi) { return M.l + (mi - x0) / (x1 - x0) * iw; };
      var Y = function (v) { return M.t + (yMax - v) / (yMax - yMin) * ih; };
      var gAx = svg('g', { 'class': 'ax' }, s);
      var boxes = [];
      function text(g, x, y, str, cls, anchor) {
        var n = svg('text', { x: x, y: y, 'class': cls, 'text-anchor': anchor || 'start' }, g);
        n.textContent = str; return n;
      }
      function bb(n) { try { var b = n.getBBox(); return { x: b.x, y: b.y, w: b.width, h: b.height }; } catch (e) { return { x: 0, y: 0, w: 0, h: 0 }; } }
      function hit(a, b, pad) { pad = pad || 0; return a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad; }

      /* grid + y ticks */
      for (var v = 6; v <= yMax; v += 2) {
        svg('line', { x1: M.l, x2: M.l + iw, y1: Y(v), y2: Y(v), 'class': 'grid' }, gAx);
        text(gAx, M.l - 8, Y(v) + 4, String(v), 'tick', 'end');
      }
      text(gAx, 0, 12, 'p/kWh', 'axlab', 'start');
      /* x ticks */
      for (var i = x0; i < x1; i++) {
        var mo = ((i % 12) + 12) % 12;
        if (mo !== 0 && !(mo === 6 && !narrow)) continue;
        svg('line', { x1: X(i), x2: X(i), y1: Y(yMin), y2: Y(yMin) + 4, 'class': 'base' }, gAx);
        text(gAx, X(i), H - M.b + 19, narrow ? String(Math.floor(i / 12)) : idxLabel(i), 'tick', 'middle');
      }
      svg('line', { x1: M.l, x2: M.l + iw, y1: Y(yMin), y2: Y(yMin), 'class': 'base' }, gAx);

      /* today divider */
      var todayI = mIdx(real[real.length - 1].m) + 1, tx = X(todayI);
      svg('line', { x1: tx, x2: tx, y1: M.t - 20, y2: Y(yMin), 'class': 'today' }, gAx);
      boxes.push(bb(text(gAx, tx - 6, M.t - 10, 'realised', 'axlab era', 'end')));
      boxes.push(bb(text(gAx, tx + 6, M.t - 10, 'forward', 'axlab era', 'start')));

      /* realised area + line + dots */
      var pts = real.map(function (d) { return [X(mIdx(d.m) + 0.5), Y(d.p)]; });
      var area = 'M' + pts[0][0] + ',' + Y(yMin) + ' L' + pts.map(function (p) { return p.join(','); }).join(' L') + ' L' + pts[pts.length - 1][0] + ',' + Y(yMin) + ' Z';
      var gD = svg('g', { 'class': 'data' }, s);
      svg('path', { d: area, 'class': 'real-area' }, gD);

      /* FiT rule + CPI path */
      var fit = P.fit, cpi = P.cpi;
      svg('line', { x1: M.l, x2: M.l + iw, y1: Y(fit), y2: Y(fit), 'class': 'fit' }, gD);
      var y0 = Math.floor(todayI / 12), yEnd = Math.floor((x1 - 1) / 12);
      var cpiPts = [];
      for (var yr = y0; yr <= yEnd; yr++) cpiPts.push([X(yr * 12 + 6), Y(fit * Math.pow(1 + cpi, yr - y0))]);
      svg('polyline', { points: cpiPts.map(function (p) { return p.join(','); }).join(' '), 'class': 'cpi' }, gD);
      var cpiEnd = cpiPts[cpiPts.length - 1];
      svg('circle', { cx: cpiEnd[0], cy: cpiEnd[1], r: 2.2, 'class': 'cpi-end' }, gD);
      var cpiVal = fit * Math.pow(1 + cpi, yEnd - y0);

      svg('path', { d: 'M' + pts.map(function (p) { return p.join(','); }).join(' L'), 'class': 'real-line' }, gD);
      pts.forEach(function (p) { svg('circle', { cx: p[0], cy: p[1], r: 2.4, 'class': 'real-dot' }, gD); });
      for (var pi = 0; pi < pts.length; pi++) {
        boxes.push({ x: pts[pi][0] - 3, y: pts[pi][1] - 3, w: 6, h: 6 });
        if (pi) {
          var q0 = pts[pi - 1], q1 = pts[pi], ns = Math.max(1, Math.ceil(Math.abs(q1[1] - q0[1]) / 6));
          for (var pk = 1; pk < ns; pk++) boxes.push({ x: q0[0] + (q1[0] - q0[0]) * pk / ns - 1.5, y: q0[1] + (q1[1] - q0[1]) * pk / ns - 1.5, w: 3, h: 3 });
        }
      }

      /* forward blocks */
      var blocks = fwd.map(function (b) {
        var xa = X(mIdx(b.from)), xb = X(mIdx(b.to) + 1), y = Y(b.p);
        var g = svg('g', { 'class': 'blk' }, gD);
        svg('line', { x1: xa + 1, x2: xb - 1, y1: y, y2: y, 'class': 'fwd' }, g);
        svg('line', { x1: xa + 1, x2: xa + 1, y1: y - 3, y2: y + 3, 'class': 'fwd-cap' }, g);
        svg('line', { x1: xb - 1, x2: xb - 1, y1: y - 3, y2: y + 3, 'class': 'fwd-cap' }, g);
        boxes.push({ x: xa, y: y - 4, w: xb - xa, h: 8 });
        return { b: b, xa: xa, xb: xb, y: y, g: g };
      });

      /* reference labels in the right margin (FiT below CPI; never overlapping) */
      var gL = svg('g', { 'class': 'labels' }, s);
      var lx = M.l + iw + 8;
      var fitLab = text(gL, lx, Y(fit) + 4, 'FiT ' + fit.toFixed(2) + 'p', 'reflab fitlab', 'start');
      var cpiLab = text(gL, lx, Y(cpiVal) + 4, 'FiT +CPI ' + cpiVal.toFixed(2) + 'p', 'reflab cpilab', 'start');
      if (bb(cpiLab).w > M.r - 10) {
        cpiLab.textContent = '';
        var t1 = svg('tspan', { x: lx, dy: 0 }, cpiLab); t1.textContent = 'FiT +CPI';
        var t2 = svg('tspan', { x: lx, dy: 13 }, cpiLab); t2.textContent = cpiVal.toFixed(2) + 'p';
        cpiLab.setAttribute('y', Y(cpiVal) - 9 + 4);
      }
      if (bb(fitLab).w > M.r - 10) { fitLab.textContent = ''; var f1 = svg('tspan', { x: lx, dy: 0 }, fitLab); f1.textContent = 'FiT'; var f2 = svg('tspan', { x: lx, dy: 13 }, fitLab); f2.textContent = fit.toFixed(2) + 'p'; fitLab.setAttribute('y', Y(fit) + 4); }
      var fb = bb(fitLab), cb = bb(cpiLab);
      if (cb.y + cb.h + 2 > fb.y) {
        var shift = cb.y + cb.h + 2 - fb.y;
        cpiLab.setAttribute('y', +cpiLab.getAttribute('y') - shift);
        var ts = cpiLab.querySelectorAll('tspan'); if (ts.length) ts[0].setAttribute('y', +cpiLab.getAttribute('y'));
      }
      boxes.push(bb(fitLab)); boxes.push(bb(cpiLab));

      /* forward block labels: above the block by default; nudged sideways, dropped below, or lifted with a
         leader when they would collide with another label or bar. Reference lines count as soft obstacles. */
      var top = M.t - 2, bottom = Y(yMin) - 2;
      var soft = [{ x: M.l, y: Y(fit) - 2, w: iw, h: 4 }];
      for (var si = 1; si < cpiPts.length; si++) {
        var a0 = cpiPts[si - 1], a1 = cpiPts[si], nSeg = Math.max(1, Math.ceil((a1[0] - a0[0]) / 8));
        for (var sj = 0; sj < nSeg; sj++) {
          var fx = a0[0] + (a1[0] - a0[0]) * sj / nSeg, fy = a0[1] + (a1[1] - a0[1]) * sj / nSeg;
          soft.push({ x: fx, y: fy - 2, w: (a1[0] - a0[0]) / nSeg, h: 4 });
        }
      }
      var VERT = [{ k: 0, p: 0 }, { k: 1, p: 1.2 }, { k: 2, p: 2 }, { k: 3, p: 2.5 }, { k: 4, p: 3.2 }, { k: 5, p: 3.6 }];
      var DX = [0, 8, -8, 16, -16, 24, -24];
      blocks.forEach(function (o) {
        var cx = (o.xa + o.xb) / 2;
        var g = svg('g', { 'class': 'blab' }, gL);
        var kT = text(g, cx, 0, o.b.k, 'bkey', 'middle');
        var vT = text(g, cx, 0, o.b.p.toFixed(2), 'bval', 'middle');
        var w = Math.max(bb(kT).w, bb(vT).w) + 4, hgt = 27, half = w / 2;
        var best = null, bestCost = 1e9;
        VERT.forEach(function (vv) {
          var lift = Math.floor(vv.k / 2) * 22, above = vv.k % 2 === 0;
          var tp = above ? o.y - 7 - hgt - lift : o.y + 7 + lift;
          if (tp < top || tp + hgt > bottom) return;
          DX.forEach(function (dx) {
            var c = clamp(cx + dx, M.l + half, M.l + iw + M.r - half - 2);
            var box = { x: c - half, y: tp, w: w, h: hgt }, hard = 0, sft = 0;
            for (var bi = 0; bi < boxes.length; bi++) if (hit(box, boxes[bi], 1)) hard++;
            for (var bj = 0; bj < soft.length; bj++) if (hit(box, soft[bj], 0)) { sft = 1; break; }
            var off = c < o.xa + 2 || c > o.xb - 2;
            var cost = vv.p + Math.abs(dx) * 0.04 + (off ? 0.8 : 0) + hard * 10 + sft * 3;
            if (cost < bestCost) { bestCost = cost; best = { top: tp, cx: c, lead: lift > 0 || off, above: above }; }
          });
        });
        if (!best) best = { top: o.y - 7 - hgt, cx: cx, lead: false, above: true };
        kT.setAttribute('x', best.cx); vT.setAttribute('x', best.cx);
        kT.setAttribute('y', best.top + 10); vT.setAttribute('y', best.top + 24);
        if (best.lead) {
          var lx2 = clamp(best.cx, o.xa + 2, o.xb - 2);
          svg('line', { x1: lx2, x2: lx2, y1: best.above ? best.top + hgt + 1 : best.top - 1, y2: best.above ? o.y - 4 : o.y + 4, 'class': 'leader' }, g);
        }
        boxes.push({ x: best.cx - half, y: best.top, w: w, h: hgt });
      });

      /* hover layer */
      var gH = svg('g', { 'class': 'hover' }, s);
      var cross = svg('line', { x1: 0, x2: 0, y1: M.t, y2: Y(yMin), 'class': 'cross', visibility: 'hidden' }, gH);
      var hiDot = svg('circle', { cx: 0, cy: 0, r: 5, 'class': 'hi-dot', visibility: 'hidden' }, gH);
      var hiBlk = svg('line', { x1: 0, x2: 0, y1: 0, y2: 0, 'class': 'hi-blk', visibility: 'hidden' }, gH);
      var marks = real.map(function (d, i) { return { type: 'm', d: d, x: pts[i][0], y: pts[i][1] }; })
        .concat(blocks.map(function (o) { return { type: 'b', d: o.b, x: (o.xa + o.xb) / 2, y: o.y, xa: o.xa, xb: o.xb }; }));
      chart = { W: W, H: H, M: M, iw: iw, marks: marks, cross: cross, hiDot: hiDot, hiBlk: hiBlk, X: X, Y: Y, yMin: yMin };

      /* data table */
      var rows = real.map(function (d) { return '<tr><td>' + esc(mLabel(d.m)) + '</td><td>Realised</td><td class="num">' + d.p.toFixed(2) + '</td></tr>'; }).join('') +
        fwd.map(function (b) { return '<tr><td>' + esc(b.k) + '</td><td>Forward</td><td class="num">' + b.p.toFixed(2) + '</td></tr>'; }).join('');
      q('#' + id + '-dtp').innerHTML = '<table><caption class="sr-only">' + esc(C.priceTitle) + '</caption><thead><tr><th scope="col">Period</th><th scope="col">Basis</th><th scope="col" class="num">p/kWh</th></tr></thead><tbody>' + rows + '</tbody></table>';
      if (ui.tipIdx >= 0) showMark(ui.tipIdx, null);
    }
    function tipHtml(tg) {
      var fit = P.fit;
      if (tg.type === 'b') {
        return '<b>' + esc(tg.d.k) + '</b> forward<br>' + tg.d.p.toFixed(2) + ' p/kWh<br><span class="tip-sub">FiT tariff is ' + signed(Math.round((fit / tg.d.p - 1) * 100)) + '% vs this block</span>';
      }
      return '<b>' + esc(mLabel(tg.d.m)) + '</b> realised<br>' + tg.d.p.toFixed(2) + ' p/kWh<br><span class="tip-sub">FiT tariff is ' + signed(Math.round((fit / tg.d.p - 1) * 100)) + '% vs this month</span>';
    }
    function showMark(idx, px) {
      if (!chart) return;
      var tg = chart.marks[idx]; if (!tg) return;
      ui.tipIdx = idx;
      var cx = px != null && tg.type === 'b' ? clamp(px, tg.xa, tg.xb) : tg.x;
      chart.cross.setAttribute('x1', cx); chart.cross.setAttribute('x2', cx); chart.cross.setAttribute('visibility', 'visible');
      if (tg.type === 'm') {
        chart.hiDot.setAttribute('cx', tg.x); chart.hiDot.setAttribute('cy', tg.y); chart.hiDot.setAttribute('visibility', 'visible');
        chart.hiBlk.setAttribute('visibility', 'hidden');
      } else {
        chart.hiBlk.setAttribute('x1', tg.xa + 1); chart.hiBlk.setAttribute('x2', tg.xb - 1);
        chart.hiBlk.setAttribute('y1', tg.y); chart.hiBlk.setAttribute('y2', tg.y); chart.hiBlk.setAttribute('visibility', 'visible');
        chart.hiDot.setAttribute('visibility', 'hidden');
      }
      elTip.innerHTML = tipHtml(tg);
      elTip.hidden = false;
      var tw = elTip.offsetWidth, th = elTip.offsetHeight;
      var x = cx + 14;
      if (x + tw > chart.W - 2) x = cx - tw - 14;
      x = clamp(x, 0, Math.max(0, chart.W - tw));
      var y = clamp(tg.y - th - 12, 0, chart.H - th);
      if (y + th > tg.y - 6 && y < tg.y + 6) y = clamp(tg.y + 14, 0, chart.H - th);
      elTip.style.left = Math.round(x) + 'px'; elTip.style.top = Math.round(y) + 'px';
    }
    function hideTip() {
      ui.tipIdx = -1; ui.pinned = false;
      elTip.hidden = true;
      if (chart) { chart.cross.setAttribute('visibility', 'hidden'); chart.hiDot.setAttribute('visibility', 'hidden'); chart.hiBlk.setAttribute('visibility', 'hidden'); }
    }
    function pick(px) {
      if (!chart) return -1;
      var tg = chart.marks, best = -1, bd = 1e9;
      for (var i = 0; i < tg.length; i++) if (tg[i].type === 'b' && px >= tg[i].xa && px <= tg[i].xb) return i;
      for (var j = 0; j < tg.length; j++) {
        if (tg[j].type !== 'm') continue;
        var dx = Math.abs(tg[j].x - px);
        if (dx < bd) { bd = dx; best = j; }
      }
      var step = chart.iw / 52;
      return bd <= Math.max(14, step * 1.2) ? best : -1;
    }
    function pointerX(ev) { var r = elPrice.getBoundingClientRect(); return ev.clientX - r.left; }
    on(elPrice, 'pointermove', function (ev) {
      if (ev.pointerType === 'touch' || ui.pinned) return;
      var i = pick(pointerX(ev));
      if (i < 0) hideTip(); else showMark(i, pointerX(ev));
    });
    on(elPrice, 'pointerleave', function (ev) { if (ev.pointerType !== 'touch' && !ui.pinned) hideTip(); });
    on(elPrice, 'pointerdown', function (ev) {
      if (ev.pointerType !== 'touch' && ev.pointerType !== 'pen') return;
      var i = pick(pointerX(ev));
      if (i < 0) { hideTip(); return; }
      showMark(i, pointerX(ev)); ui.pinned = true;
    });
    on(document, 'pointerdown', function (ev) {
      if (ui.pinned && !elPrice.contains(ev.target)) hideTip();
    }, true);
    on(elPrice, 'keydown', function (ev) {
      if (!chart) return;
      var n = chart.marks.length, i = ui.tipIdx;
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft' || ev.key === 'Home' || ev.key === 'End') {
        ev.preventDefault();
        if (ev.key === 'Home') i = 0;
        else if (ev.key === 'End') i = n - 1;
        else if (i < 0) i = ev.key === 'ArrowRight' ? 0 : n - 1;
        else i = clamp(i + (ev.key === 'ArrowRight' ? 1 : -1), 0, n - 1);
        showMark(i, null); ui.pinned = true;
        elLive.textContent = (elTip.innerText || elTip.textContent).replace(/\s*\n\s*/g, ', ');
      } else if (ev.key === 'Escape') { hideTip(); elLive.textContent = ''; }
    });
    on(elPrice, 'blur', function () { if (ui.pinned) hideTip(); });

    /* counterparty interactions */
    on(elBars, 'pointerover', function (ev) { var b = ev.target.closest && ev.target.closest('.ppa-cp-row'); if (b) showCpTip(b); });
    on(elBars, 'pointerleave', hideCpTip);
    on(elBars, 'focusin', function (ev) { var b = ev.target.closest && ev.target.closest('.ppa-cp-row'); if (b) showCpTip(b); });
    on(elBars, 'focusout', hideCpTip);
    on(elBars, 'click', function (ev) {
      var b = ev.target.closest && ev.target.closest('.ppa-cp-row'); if (!b) return;
      var d = cpList[+b.getAttribute('data-i')]; if (!d) return;
      st.off = st.off === d.key ? '' : d.key;
      syncControls(); render();
      var nb = elBars.querySelector('.ppa-cp-row[data-i]');
      var again = null; cpList.forEach(function (x, i) { if (x.key === d.key) again = elBars.querySelector('.ppa-cp-row[data-i="' + i + '"]'); });
      (again || nb) && (again || nb).focus({ preventScroll: true });
    });

    /* filter inputs */
    ['cls', 'off', 'status'].forEach(function (k) { on(sel[k], 'change', function () { st[k] = sel[k].value; render(); }); });
    var qTimer = null;
    on(elQ, 'input', function () { clearTimeout(qTimer); qTimer = setTimeout(function () { st.q = elQ.value; render(); }, 90); });
    function reset() { st.cls = st.off = st.status = st.q = ''; syncControls(); render(); }
    on(q('.ppa-reset'), 'click', reset);
    on(q('.ppa-ftoggle'), 'click', function () {
      ui.fopen = !ui.fopen;
      root.classList.toggle('is-fopen', ui.fopen);
      q('.ppa-ftoggle').setAttribute('aria-expanded', String(ui.fopen));
    });

    /* data table toggles */
    root.querySelectorAll('.ppa-dt-toggle').forEach(function (b) {
      on(b, 'click', function () {
        var tgt = q('#' + b.getAttribute('aria-controls'));
        var open = tgt.hidden;
        tgt.hidden = !open;
        b.setAttribute('aria-expanded', String(open));
        b.textContent = open ? C.hideTable : C.showTable;
      });
    });

    /* register interactions (delegated) */
    function setSort(k, dirOpt) {
      if (dirOpt) { st.sort = { key: k, dir: dirOpt }; }
      else if (st.sort.key === k) st.sort.dir = -st.sort.dir;
      else st.sort = { key: k, dir: 1 };
      render();
    }
    function rowFor(el) { var tr = el.closest && el.closest('[data-i]'); return tr ? ROWS[+tr.getAttribute('data-i')] : null; }
    on(elRegBody, 'click', function (ev) {
      var t0 = ev.target;
      var sb = t0.closest && t0.closest('.ppa-sort');
      if (sb) {
        var k = sb.getAttribute('data-k'); setSort(k);
        var nb = elRegBody.querySelector('.ppa-sort[data-k="' + k + '"]'); if (nb) nb.focus({ preventScroll: true });
        return;
      }
      if (t0.closest && t0.closest('[data-act="reset"]')) { reset(); return; }
      var head = t0.closest && t0.closest('.rl-head');
      if (head) {
        var more = q('#' + head.getAttribute('aria-controls'));
        var open = more.hidden; more.hidden = !open; head.setAttribute('aria-expanded', String(open));
        head.parentNode.classList.toggle('is-open', open);
        return;
      }
      if (t0.closest && t0.closest('.rl-map')) { var rr = rowFor(t0); if (rr && clickable) ctx.onSiteClick(rr.src); return; }
      if (clickable) {
        var tr = t0.closest && t0.closest('tr[data-i]');
        if (tr) { var r = ROWS[+tr.getAttribute('data-i')]; if (r) ctx.onSiteClick(r.src); }
      }
    });
    on(elRegBody, 'keydown', function (ev) {
      if (!clickable || (ev.key !== 'Enter' && ev.key !== ' ')) return;
      var tr = ev.target.matches && ev.target.matches('tr[data-i]') ? ev.target : null;
      if (tr) { ev.preventDefault(); var r = ROWS[+tr.getAttribute('data-i')]; if (r) ctx.onSiteClick(r.src); }
    });
    on(elRegBody, 'scroll', function (ev) { if (ev.target.classList && ev.target.classList.contains('reg-scroll')) syncScroll(); }, true);
    on(elRegBody, 'wheel', function (ev) {
      var hd = ev.target.closest && ev.target.closest('.reg-head'); if (!hd || !ev.deltaX) return;
      var sc = elRegBody.querySelector('.reg-scroll'); if (sc) { sc.scrollLeft += ev.deltaX; ev.preventDefault(); }
    }, { passive: false });
    on(elSortSel, 'change', function () { setSort(elSortSel.value, st.sort.key === elSortSel.value ? st.sort.dir : 1); });
    on(elSortDir, 'click', function () { setSort(st.sort.key, -st.sort.dir); });

    /* ---------- responsive: media + measured widths */
    var mq = window.matchMedia ? window.matchMedia('(max-width: 760px)') : null;
    function applyMq() {
      var m = !!(mq && mq.matches);
      var changed = m !== ui.mobile;
      ui.mobile = m;
      root.classList.toggle('is-mobile', m);
      return changed;
    }
    applyMq();
    var mqFn = function () { if (applyMq()) render(); drawSoon(); };
    if (mq) { if (mq.addEventListener) mq.addEventListener('change', mqFn); else if (mq.addListener) mq.addListener(mqFn); }
    cleanups.push(function () { if (mq) { if (mq.removeEventListener) mq.removeEventListener('change', mqFn); else if (mq.removeListener) mq.removeListener(mqFn); } });

    var lastW = 0;
    var drawSoon = rafThrottle(function () {
      if (ui.destroyed) return;
      var w = elPrice.clientWidth;
      if (w && w !== lastW) { lastW = w; drawPrice(); }
      var fh = elFilters.offsetHeight;
      root.style.setProperty('--ppa-sticky-top', (ui.mobile ? 0 : fh) + 'px');
      /* on wide screens the register breaks out of the 1200px column (up to 120px each side) */
      var gutter = ui.mobile ? 0 : Math.max(0, Math.floor((root.clientWidth - 1200) / 2));
      root.style.setProperty('--ppa-gutter', gutter + 'px');
      root.style.setProperty('--ppa-bleed', Math.min(gutter, 120) + 'px');
      sizeTable();
    });
    var ro = null;
    if (window.ResizeObserver) {
      ro = new ResizeObserver(drawSoon);
      ro.observe(elPrice); ro.observe(elFilters); ro.observe(elRegBody);
    } else on(window, 'resize', drawSoon);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if (!ui.destroyed) { lastW = 0; drawSoon(); } });

    fillSelects();
    syncControls();
    render();
    drawSoon();

    /* ---------- public instance API */
    function getState() { return { cls: st.cls, off: st.off, status: st.status, q: st.q, sort: { key: st.sort.key, dir: st.sort.dir } }; }
    function setFilter(p) {
      p = p || {};
      if ('cls' in p || 'exportArrangement' in p) st.cls = p.cls != null ? p.cls : p.exportArrangement || '';
      if (st.cls && !CLASSES[st.cls]) st.cls = classOf(st.cls);
      if ('off' in p || 'counterparty' in p) {
        var o = p.off != null ? p.off : p.counterparty || '';
        if (o && o !== '__sole' && o !== '__none') {
          if (/sole/i.test(o)) o = '__sole';
          else if (/^not identified$/i.test(o)) o = '__none';
          else o = cleanName(o);
        }
        st.off = o || '';
      }
      if ('status' in p) st.status = p.status ? (ST_ORDER[p.status] != null ? p.status : statusOf(p.status)) : '';
      if ('q' in p || 'search' in p) st.q = (p.q != null ? p.q : p.search) || '';
      if (p.sort && p.sort.key) st.sort = { key: p.sort.key, dir: p.sort.dir === -1 ? -1 : 1 };
      syncControls(); render();
    }
    /* Vertical-only scroll of the nearest scrolling ancestor. scrollIntoView would also scroll overflow-x:hidden
       ancestors sideways (the host page, the wide register), shifting the whole layout. */
    function vScroll(el, block) {
      var sc = el.parentElement;
      while (sc && sc !== document.body) {
        var oy = getComputedStyle(sc).overflowY;
        if ((oy === 'auto' || oy === 'scroll') && sc.scrollHeight > sc.clientHeight) break;
        sc = sc.parentElement;
      }
      var er = el.getBoundingClientRect(), smooth = RBX.reduced ? 'auto' : 'smooth';
      if (!sc || sc === document.body) { window.scrollBy({ top: er.top - (block === 'center' ? (window.innerHeight - er.height) / 2 : 8), behavior: smooth }); return; }
      var sr = sc.getBoundingClientRect();
      var top = sc.scrollTop + er.top - sr.top - (block === 'center' ? (sc.clientHeight - er.height) / 2 : 8);
      try { sc.scrollTo({ top: Math.max(0, top), behavior: smooth }); } catch (e) { sc.scrollTop = Math.max(0, top); }
    }
    function showSite(key) {
      var k = compact(key);
      var r = null;
      for (var i = 0; i < ROWS.length; i++) if (ROWS[i].key === key || compact(ROWS[i].pc) === k || ROWS[i].key === k) { r = ROWS[i]; break; }
      if (!r) return false;
      st.cls = st.off = st.status = ''; st.q = r.pc || r.key;
      syncControls(); render();
      var el = elRegBody.querySelector('[data-i="' + r.i + '"]');
      if (el) {
        vScroll(el, 'center');
        el.classList.add('is-flash');
        setTimeout(function () { el.classList.remove('is-flash'); }, 2400);
      }
      return true;
    }
    function scrollToSection(name) {
      var el = q('[data-sec="' + name + '"]');
      if (el) vScroll(el, 'start');
      return !!el;
    }
    return {
      refresh: function () { lastW = 0; applyMq(); render(); drawSoon(); },
      setTheme: function (name) { theme = name === 'night' ? 'night' : 'paper'; root.setAttribute('data-ppa-theme', theme); lastW = 0; hideTip(); drawSoon(); },
      destroy: function () {
        ui.destroyed = true;
        if (ro) ro.disconnect();
        cleanups.forEach(function (f) { try { f(); } catch (e) { /* ignore */ } });
        if (root.parentNode) root.parentNode.removeChild(root);
      },
      setFilter: setFilter,
      getState: getState,
      showSite: showSite,
      scrollToSection: scrollToSection,
      el: root
    };
  }

  RBX.ppa = { mount: mount, check: check, cleanName: cleanName, displayCase: displayCase };
})();
