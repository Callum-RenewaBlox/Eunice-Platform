/* Investor build only. The commercial KPI band (spec 10.1) with the exact v1 formulas over visible sites, as-of
   stamps, the TCV Potential caveat inside its cell plus the method popover, the static GB power market strip,
   the verbatim footer bar, the ▶ Present header button, the PPA chips feed and the drawer's investor sections. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, H = RBX.hooks, I = RBX.inv;
  var B = RBX.band = { chips: null };
  var INFO = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.1"/></svg>';
  var PLAY = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M6.5 4.5v11l9-5.5z" fill="currentColor" stroke="none"/></svg>';

  function cfg() { return RBX.config || {}; }
  function mwHtml(kw, d) { return U.num((kw || 0) / 1000, d) + '<small>MW</small>'; }

  // ------------------------------------------------------------------ metrics (spec 10.1; investor audit 1.3)
  /** Each returns {v, f(v) → html}. `rows` are the visible rows of the current view. */
  var M = B.metrics = {
    count: function (rows) { return { v: rows.length, f: U.int }; },
    samPriced: function (rows) { return { v: rows.filter(function (r) { return r.pr; }).length, f: U.int }; },
    samAv: function (rows) {
      return { v: U.sum(rows, function (r) { return r.pr ? r.av : 0; }), f: function (x) { return mwHtml(x, 1); } };
    },
    btc: function (rows) { return { v: U.sum(rows, function (r) { return r.btc; }), f: function (x) { return U.int(x); } }; },
    tcv: function (rows) { return { v: U.sum(rows, function (r) { return r.tcv; }), f: U.abbr }; },
    tcvT: function (rows) { return { v: U.sum(rows, function (r) { return r.tcvT; }), f: U.abbr }; },
    stranded: function (rows) { return { v: U.sum(rows, function (r) { return r.kw; }), f: function (x) { return mwHtml(x, 1); } }; },
    tamCap: function (rows) { return { v: U.sum(rows, function (r) { return r.kw; }), f: function (x) { return U.int(x / 1000) + '<small>MW</small>'; } }; },
    tamInBm: function (rows) {
      return { v: U.sum(rows, function (r) { return r.bt > 0 ? r.kw : 0; }), f: function (x) { return U.int(x / 1000) + '<small>MW</small>'; } };
    },
    tcvPot: function (rows) { return { v: I.tcvPot(rows), f: U.abbr }; },
    ppaSites: function () { return { v: ppaChips().sites, f: U.int }; },
    ppaMw: function () { return { v: ppaChips().mw * 1000, f: function (x) { return mwHtml(x, 1); } }; },
    ppaCp: function () { return { v: ppaChips().counterparties, f: U.int }; },
    base12: function () { var k = kpi(); return { v: k.base12, f: function (x) { return U.num(x, 2) + '<small>p</small>'; } }; },
    win26: function () { var k = kpi(); return { v: k.win26, f: function (x) { return U.num(x, 2) + '<small>p</small>'; } }; }
  };
  function kpi() { return (RBX.data.ppa && RBX.data.ppa.kpi) || {}; }
  /** PPA chips: the module's last onChips payload, else the unfiltered register (129 · 143.6 MW · 21). */
  function ppaChips() {
    if (B.chips) return B.chips;
    var rows = RBX.data.rows.sam, ext = {};
    rows.forEach(function (r) { if (r.off && r.off !== 'Generator is sole holder') ext[r.off] = 1; });
    return { sites: rows.length, mw: U.sum(rows, function (r) { return r.kw; }) / 1000, counterparties: Object.keys(ext).length };
  }

  /** Sub-caption under a value; the TCV Potential cell carries the caveat next to the number (spec 10.1). */
  function subHtml(view, c, rows) {
    if (c.metric === 'tcvPot') {
      var big = rows.filter(function (r) { return r.big && r.bt > 0; });
      var btn = '<button type="button" class="band-i" id="tcvInfo" aria-haspopup="dialog" aria-expanded="false" aria-controls="tcvPop" aria-label="How TCV Potential is calculated">' + INFO + '</button>';
      if (!big.length) return '<span>AD-scale only (&lt;10 MW)</span>' + btn;
      return '<span>' + U.esc(U.abbr(I.tcvPot(big))) + ' of it from ' + U.int(big.length) + ' sites ≥ 10 MW</span>' + btn;
    }
    if (c.metric === 'win26') {
      var k = kpi();
      return k.base12 ? '▲' + Math.round((k.win26 / k.base12 - 1) * 100) + '% vs 12m' : '';
    }
    return U.esc(c.sub || '');
  }

  // ------------------------------------------------------------------ band DOM
  function viewKey() { return RBX.state.view; }
  B.render = function () {
    var slot = document.getElementById('bandSlot'); if (!slot) return;
    var view = viewKey(), bc = cfg().band || {}, cells = bc[view] || [];
    var k = kpi(), asOf = (bc.asOf || {})[view] || '';
    var up = k.base12 ? Math.round((k.win26 / k.base12 - 1) * 100) : null;
    slot.innerHTML = '<div class="band" role="region" aria-label="Key figures">' +
      '<div class="band-cells" id="bandCells">' + cells.map(function (c, i) {
        return '<div class="band-cell' + (c.metric === 'tcvPot' ? ' pot' : '') + '"><div class="band-l">' + U.esc(c.label) + '</div>' +
          '<div class="band-v num" id="bandV' + i + '"></div><div class="band-s" id="bandS' + i + '"></div></div>';
      }).join('') +
      '<div class="band-cell band-asof">' + asOfHtml(asOf) + '</div></div>' +
      (k.base12 ? '<div class="band-mkt" aria-label="GB power market snapshot">' +
        '<div class="mkt-t">' + U.esc(((cfg().market || {}).title) || 'GB power') + '<span>' + U.esc(fmtIso(k.asOf)) + '</span></div>' +
        '<div class="mkt-v num">Baseload 12m <b>' + U.num(k.base12, 2) + 'p</b><i>·</i>Win-26 <b>' + U.num(k.win26, 2) + 'p</b> <span class="mkt-up">▲' + up + '%</span>' +
        '<i>·</i>Cal-28 <b>' + U.num(k.cal28, 2) + 'p</b><i>·</i>FiT <b>' + U.num(k.fit, 2) + 'p</b></div></div>' : '') +
      '</div>';
    B.lastView = view;
    B.update(true);
  };
  /** "Model · 16 Jun 2026 · Indicative; not investment advice." → stamp on line 1, caveat on line 2. */
  function asOfHtml(s) {
    var p = String(s || '').split(' · ');
    if (p.length < 3) return '<span class="asof-1">' + U.esc(s) + '</span>';
    return '<span class="asof-1">' + U.esc(p.slice(0, 2).join(' · ')) + ' ·</span> <span class="asof-2">' + U.esc(p.slice(2).join(' · ')) + '</span>';
  }
  function fmtIso(iso) { if (!iso) return ''; var p = String(iso).split('-'); return (+p[2]) + ' ' + U.MONTHS[+p[1] - 1] + ' ' + p[0]; }

  var announce = U.debounce(function (msg) { var l = document.getElementById('live'); if (l) l.textContent = msg; }, 400);
  B.update = function (instant) {
    var view = viewKey(), cells = (cfg().band || {})[view] || [];
    if (B.lastView !== view) { B.render(); return; }
    var rows = view === 'ppa' ? [] : RBX.filters.active(view), parts = [];
    cells.forEach(function (c, i) {
      var el = document.getElementById('bandV' + i), sub = document.getElementById('bandS' + i);
      if (!el) return;
      var m = (M[c.metric] || M.count)(rows);
      if (instant || RBX.reduced) { el.setAttribute('data-v', String(m.v)); el.innerHTML = m.f(m.v); } else U.countUp(el, m.v, m.f, 600);
      if (sub) {
        var focusInfo = document.activeElement && document.activeElement.id === 'tcvInfo';
        sub.innerHTML = subHtml(view, c, rows);
        if (focusInfo) { var b = document.getElementById('tcvInfo'); if (b) b.focus({ preventScroll: true }); }
      }
      parts.push(c.label + ' ' + m.f(m.v).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
    });
    if (!instant) announce(parts.join(', '));
  };

  // ------------------------------------------------------------------ footer bar (verbatim footers, spec 10.1)
  B.footText = function (view) {
    var f = cfg().footers || {};
    return view === 'tam' ? f.tam : view === 'ppa' ? f.ppa : f.sam;
  };
  B.renderFoot = function () {
    var slot = document.getElementById('footSlot'); if (!slot) return;
    var t = B.footText(viewKey()) || '';
    slot.innerHTML = '<footer class="foot" role="contentinfo"><p class="foot-t" title="' + U.esc(t) + '">' + U.esc(t) + '</p>' +
      '<button type="button" class="foot-link" data-foot="sources">Sources &amp; method ›</button></footer>';
  };

  // ------------------------------------------------------------------ TCV Potential method popover
  B.popHtml = function () {
    var r = I.TCVRATE, t = I.totals || {}, L = cfg().labels || {}, tiers = L.tiers || {};
    var adOnly = (RBX.state.hidden.scale || new Set()).has(1);
    var rows = [1, 2, 3, 4, 5].map(function (k) {
      return '<tr><th scope="row">' + U.esc(tiers[k] || 'Tier ' + k) + '</th><td class="num">£' + U.num(r[k], 2) + '</td></tr>';
    }).join('');
    return '<div class="pop-h"><h2 class="pop-t" id="tcvPopT">How TCV Potential is calculated</h2>' +
      '<button type="button" class="sh-x" data-pop-close="1" aria-label="Close (Esc)"><svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15"/></svg></button></div>' +
      '<p>Each TAM site’s available-for-BM capacity is valued at the priced SAM sites’ own Year-5 TCV per kW-available for its BM tier. Scotland sits outside the modelled tiers and is excluded.</p>' +
      '<table class="pop-tbl"><caption>TCV rate by tier, £ per kW available for BM</caption><tbody>' + rows + '</tbody></table>' +
      '<dl class="pop-kv"><dt>Available-for-BM ratio</dt><dd class="num">' + U.num(I.AVRATIO * 100, 1) + '% <span>(' + I.AVRATIO.toFixed(5) + ', Σ available ÷ Σ installed over priced SAM sites)</span></dd>' +
      '<dt>Available for BM, per site</dt><dd>the DNO maximum export capacity where the register gives one (' + U.int(t.bmKnown) + ' sites), otherwise installed capacity × the ratio</dd>' +
      '<dt>TCV Potential</dt><dd>Σ available-for-BM kW × TCV rate of the site’s tier, over tiers 1–5</dd></dl>' +
      '<p class="pop-warn"><b>Caveat.</b> ' + U.esc(U.abbr(t.tamBig)) + ' of the ' + U.esc(U.abbr(t.tamPot)) + ' total comes from ' + U.int(t.tamBigN) +
      ' sites of 10 MW and over (biomass, EfW and large CHP), valued with economics taken from 1–5 MW AD peakers. The AD-scale view excludes them.</p>' +
      '<div class="pop-act"><button type="button" class="btn' + (adOnly ? '' : ' btn-primary') + '" data-scale-set="' + (adOnly ? 'all' : 'ad') + '">' +
      (adOnly ? 'Show all sizes' : 'Show AD-scale only (&lt;10 MW)') + '</button></div>';
  };
  B.openPop = function (anchor) {
    var pop = document.getElementById('tcvPop');
    if (!pop) {
      pop = document.createElement('section');
      pop.id = 'tcvPop'; pop.className = 'tcv-pop'; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-modal', 'false'); pop.setAttribute('aria-labelledby', 'tcvPopT');
      pop.hidden = true;
      document.body.appendChild(pop);
    }
    pop.innerHTML = B.popHtml();
    pop.hidden = false;
    var r = anchor.getBoundingClientRect(), w = Math.min(400, window.innerWidth - 16);
    pop.style.width = w + 'px';
    pop.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left - 24)) + 'px';
    pop.style.top = (r.bottom + 8) + 'px';
    anchor.setAttribute('aria-expanded', 'true');
    B.popAnchor = anchor;
    var x = pop.querySelector('[data-pop-close]'); if (x) x.focus();
  };
  B.closePop = function (refocus) {
    var pop = document.getElementById('tcvPop');
    if (!pop || pop.hidden) return false;
    pop.hidden = true;
    var a = document.getElementById('tcvInfo');
    if (a) { a.setAttribute('aria-expanded', 'false'); if (refocus !== false) a.focus({ preventScroll: true }); }
    return true;
  };
  /** The Scale filter (spec 10.1): AD-scale only hides TAM sites of 10 MW and over. */
  B.setScale = function (mode) {
    var h = RBX.state.hidden.scale || (RBX.state.hidden.scale = new Set());
    h.clear();
    if (mode === 'ad') h.add(1);
    RBX.filters.changed();
  };

  document.addEventListener('click', function (e) {
    if (e.target.closest('#tcvInfo')) { var p = document.getElementById('tcvPop'); if (p && !p.hidden) B.closePop(); else B.openPop(e.target.closest('#tcvInfo')); return; }
    var sc = e.target.closest('[data-scale-set]');
    if (sc) { B.setScale(sc.getAttribute('data-scale-set')); var pp = document.getElementById('tcvPop'); if (pp && !pp.hidden) pp.innerHTML = B.popHtml(); return; }
    if (e.target.closest('[data-pop-close]')) { B.closePop(); return; }
    if (e.target.closest('[data-foot="sources"]')) { RBX.drawer.open(); return; }
    if (e.target.closest('#presentBtn')) { if (RBX.present) RBX.present.enter(); return; }
    var pop = document.getElementById('tcvPop');
    if (pop && !pop.hidden && !e.target.closest('#tcvPop')) B.closePop(false);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && B.closePop()) { e.preventDefault(); e.stopPropagation(); }
  }, true);
  window.addEventListener('resize', function () { B.closePop(false); });

  // ------------------------------------------------------------------ hooks
  H.headerActions = function () {
    return '<button type="button" class="hbtn-present" id="presentBtn" aria-label="Present (P)" title="Present (P)">' + PLAY + '<span>Present</span></button>';
  };
  var basePpaChips = H.ppaChips;
  H.ppaChips = function (c) {
    B.chips = c;
    if (basePpaChips) basePpaChips(c);
    if (RBX.state.view === 'ppa') B.update(false);
  };
  H.drawerSections = function () {
    var c = cfg(), n = c.notes || {}, f = c.footers || {}, a = I.asOf || {}, r = I.TCVRATE, L = (c.labels || {}).tiers || {};
    var p = function (s) { return '<p>' + U.esc(s || '') + '</p>'; };
    var tbl = '<table class="dr-tbl"><thead><tr><th scope="col">BM tier</th><th scope="col" class="num">TCV rate, £/kW available</th></tr></thead><tbody>' +
      [1, 2, 3, 4, 5].map(function (k) { return '<tr><td>' + U.esc(L[k]) + '</td><td class="num">' + U.num(r[k], 2) + '</td></tr>'; }).join('') + '</tbody></table>' +
      '<p><b>AVRATIO</b> ' + U.num(I.AVRATIO * 100, 1) + '% (' + I.AVRATIO.toFixed(5) + '): Σ available-for-BM ÷ Σ installed over the ' + U.int(I.priced) + ' priced SAM sites.</p>' +
      '<p><b>bmKw</b> = the DNO maximum export capacity where known, otherwise installed kW × AVRATIO.</p>' +
      '<p><b>TCV Potential</b> = Σ over tiers 1–5 of bmKw × TCV rate of the tier. Scotland is excluded. Total ' + U.esc(U.abbr((I.totals || {}).tamPot)) +
      '; ' + U.esc(U.abbr((I.totals || {}).tamBig)) + ' of it from ' + U.int((I.totals || {}).tamBigN) + ' sites ≥ 10 MW.</p>' +
      '<p><b>Uplift</b> = average BM revenue per tier ÷ the ' + U.num(I.WHOLESALE, 1) + 'p wholesale baseline − 1: ' +
      [1, 2, 3, 4, 5].map(function (k) { return 'Tier ' + k + ' +' + I.uplift(k) + '%'; }).join(', ') + '.</p>';
    return [
      { title: 'Legend notes', html: '<h4>Peaker plants (SAM)</h4>' + p(n.sam) + '<h4>Addressable market (TAM)</h4>' + p(n.tam) + '<h4>Stranded hydro</h4>' + p(n.hydro) },
      { title: 'TCV method', html: tbl },
      { title: 'Footers', html: p(f.sam) + p(f.tam) + p(f.ppa) },
      { title: 'As of', html: '<dl><dt>Model</dt><dd>' + U.esc(a.model || '') + '</dd><dt>Registers</dt><dd>' + U.esc(a.registers || '') + '</dd><dt>Prices</dt><dd>' + U.esc(a.prices || '') + '</dd></dl>' }
    ];
  };

  // The page is a fixed app shell: never let a scrollIntoView() (PPA "See in register", chapter scrolls) scroll the
  // document or the #app grid, which would slide the header off the top.
  function pinShell() {
    var se = document.scrollingElement, a = document.getElementById('app');
    if (se && se.scrollTop) se.scrollTop = 0;
    if (a && a.scrollTop) a.scrollTop = 0;
    var pp = document.getElementById('ppa');
    if (pp && pp.scrollLeft) pp.scrollLeft = 0;
  }
  window.addEventListener('scroll', pinShell, true);

  // ------------------------------------------------------------------ lifecycle: render with the header at boot, then follow events
  var baseHeader = RBX.header.render;
  RBX.header.render = function () {
    baseHeader.apply(this, arguments);
    B.render();
    B.renderFoot();
  };
  RBX.bus.on('view', function () { B.closePop(false); B.render(); B.renderFoot(); });
  RBX.bus.on('filter', function (p) { B.update(!!(p && p.light)); });
})();
