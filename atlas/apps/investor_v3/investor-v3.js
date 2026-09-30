/* Investor Atlas v3: adapts the investor modules (core/js/investor/*) to the shared product skin in the RenewaBlox
   brand. Bundled after them and right before core/js/app.js. Nothing in core/ or in the investor modules is
   edited, so the Investor Atlas v2 page is unchanged; every change is a replaced property or a wrapper:
   - the KPI band, its GB power strip and the footer bar are not rendered: the headline figures move into the
     skin's brand KPI card in the panel (config views[v].kpis, formatted by the investor band metrics);
   - the header carries the "Investor Atlas / Confidential" lockup; the panel is one calm column: label, scope,
     one-line description, the KPI card (hero, treasury line, ledger, disclaimer), the legend and a one-row
     capacity disclosure; explanations move behind the (i) popover and "Sources & method";
   - hollow "Awaiting BM figure" rings keep no shadow; Present mode frames the map clear of the floating header.
   The site sheet, Present mode and the map chrome / PNG export live in v3-sheet.js, v3-present.js and v3-map.js.
   Inert unless <html data-skin="product" data-app="investor"> (apps/investor_v3/template.html). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, doc = document.documentElement;
  if (doc.getAttribute('data-skin') !== 'product' || doc.getAttribute('data-app') !== 'investor') return;
  var B = RBX.band, K = RBX.kpi, I = RBX.inv;
  var V3 = RBX.v3 = {};
  var INFO = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.1"/></svg>';

  // ------------------------------------------------------------------ shared helpers (also used by v3-sheet/present/map.js)
  /** Money in the v3 grammar: full-size £ on the baseline, small magnitude letter (£221.9M, £7.17bn, £595k). */
  V3.money = function (v) {
    var s = typeof v === 'number' ? U.abbr(v) : String(v == null ? '' : v);
    var m = /^(-?£?[\d.,]+)\s*(k|M|bn)?$/.exec(s);
    return m ? '<span class="money">' + U.esc(m[1]) + (m[2] ? '<span class="mag">' + m[2] + '</span>' : '') + '</span>' : U.esc(s);
  };
  /** The model / registers stamp and the disclaimer for a view (config band.asOf), always ending in the caveat. */
  V3.CAVEAT = 'Indicative; not investment advice.';
  V3.asOf = function (view) {
    var bc = (RBX.config.band || {}).asOf || {}, s = String(bc[view === 'tam' ? 'tam' : view === 'ppa' ? 'ppa' : view === 'hydro' ? 'hydro' : 'sam'] || '');
    var stamp = s.split(' · Indicative')[0].replace(/\s*·\s*$/, '');
    return { stamp: stamp, caveat: V3.CAVEAT, line: stamp + ' · ' + V3.CAVEAT };
  };

  // ------------------------------------------------------------------ no band, no market strip, no footer bar
  // band.js looks these up on RBX.band at call time; its popover, Scale control, Present button, drawer sections
  // and PPA chips keep working. With render a no-op, B.update returns before touching the DOM or the live region.
  if (B) {
    B.render = function () {};
    B.renderFoot = function () {};
    B.fitMkt = function () {};
  }

  // ------------------------------------------------------------------ KPI card: investor figures in the brand card
  // Each investor band metric becomes a KPI metric; the formatter comes along so the card prints £221.9M, 90.5 MW.
  if (B && B.metrics) {
    Object.keys(B.metrics).forEach(function (id) {
      if (K.metrics[id]) return;
      K.metrics[id] = function (rows) { var m = B.metrics[id](rows); return { v: m.v, d: 0, f: m.f }; };
    });
  }
  var LOCK = '<svg class="i lock" viewBox="0 0 20 20" aria-hidden="true"><rect x="4.5" y="9" width="11" height="8" rx="1.8"/><path d="M7 9V6.8a3 3 0 0 1 6 0V9"/></svg>';
  var CHEV = '<svg class="i chev" viewBox="0 0 20 20" aria-hidden="true"><path d="M7.5 4.5 13 10l-5.5 5.5"/></svg>';
  var DOWN = '<svg class="i chev" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 7.5 10 13l5-5.5"/></svg>';
  var MONEY = { tcv: 1, tcvT: 1, tcvPot: 1 };
  function cfg() { return RBX.config || {}; }
  function confText() { return cfg().confidential || 'Confidential · investor use only'; }
  /** TAM: the TCV Potential that comes from sites of 10 MW and over (the caveat), and the Scale state. */
  function bigPot(rows) {
    var big = rows.filter(function (r) { return r.big && r.bt > 0; });
    return { rows: big, v: big.length ? I.tcvPot(big) : 0, adOnly: (RBX.state.hidden.scale || new Set()).has(1) };
  }
  /** A hero label never silently changes meaning: any filter swaps in views[v].kpis[0].labelFiltered. */
  function filtered(view) { return RBX.filters.anyHidden(view); }

  // the card markup: the skin's hero + tiles become hero + treasury line + ledger + disclaimer band
  var kpiHtml = K.html;
  K.html = function (view) {
    var h = kpiHtml.apply(this, arguments); if (!h) return h;
    RBX.state.inView = false;                       // no "In view" switch on an investor hero
    var vc = (cfg().views || {})[view] || {}, kp = vc.kpis || [];
    var t = document.createElement('template'); t.innerHTML = h;
    var f = t.content, grid = f.querySelector('.kpis'), hero = f.querySelector('.kpi-hero');
    if (!grid || !hero) return h;
    grid.classList.add('v3-ledger');
    var sw = f.querySelector('#ivSw'); if (sw) sw.remove();
    var top = hero.querySelector('.kpi-top');
    var pp = document.getElementById('tcvPop'), popOpen = !!(pp && !pp.hidden && B && B.popAnchor && B.popAnchor.id === 'tcvInfo');
    if (top) top.insertAdjacentHTML('beforeend', '<button type="button" class="i-btn" id="tcvInfo" aria-haspopup="dialog" aria-expanded="' + popOpen + '" aria-controls="tcvPop" aria-label="' +
      (view === 'tam' ? 'How TCV Potential is calculated' : 'How contract value is modelled') + '">' + INFO + '</button>');
    kp.forEach(function (k, i) {
      if (k.role !== 'sub') return;
      var cell = f.querySelector('#kpi' + i); cell = cell && cell.closest('.kpi'); if (!cell) return;
      cell.remove();
      hero.insertAdjacentHTML('beforeend', '<div class="kpi-sub"><b class="kpi-v" id="kpi' + i + '"></b> <span class="kpi-l" id="kpil' + i + '"></span></div>');
    });
    var uni = f.querySelector('.universe');
    var a = V3.asOf(view);
    var cav = document.createElement('div'); cav.className = 'caveat';   // no icon: the text sits flush with the ledger
    cav.innerHTML = '<div class="cv"><span class="conf-fb">' + LOCK + U.esc(confText()) + '</span><b>' + U.esc(a.caveat) + '</b>' +
      '<div class="row"><span>' + U.esc(a.stamp) + '</span><button type="button" class="src-link" data-foot="sources" aria-label="Sources &amp; method">Sources' + CHEV + '</button></div></div>';
    if (uni) uni.replaceWith(cav); else grid.appendChild(cav);
    var card = f.querySelector('.kcard');
    var peek = '<p class="v3-peekline">' + LOCK + '<span>' + U.esc(confText().split(' · ')[0]) + '</span><i>·</i><span>' + U.esc(a.stamp.replace(' · ', ' ')) + '</span><i>·</i><span>' + U.esc(a.caveat) + '</span></p>';
    if (card) card.insertAdjacentHTML('afterend', peek);
    return t.innerHTML;
  };

  var announce = U.debounce(function (msg) { var l = document.getElementById('live'); if (l) l.textContent = msg; }, 400);
  /** The rail's screen-reader h2 (rail.js prints views[v].headline, a fixed sentence with unfiltered figures): a
      neutral name for the panel instead, which says when the figures below cover only the sites shown. */
  var SCOPE = { sam: 'serviceable market (SAM)', tam: 'addressable market (TAM)' };
  function railHeading(view, vc, filt) {
    var h2 = document.querySelector('#rail h2.headline'); if (!h2) return;
    var t = (vc.label || '') + (SCOPE[view] ? ', ' + SCOPE[view] : '') + (filt ? ': figures for the sites shown' : '');
    if (h2.textContent !== t) h2.textContent = t;
  }
  K.update = function (instant) {
    var view = RBX.state.view, vc = (RBX.config.views || {})[view] || {};
    if (!vc.kpis || view === 'ppa') return;
    var rows = K.rows(view), all = RBX.data.rows[view] || [], parts = [], filt = filtered(view);
    var heroEl = document.querySelector('.kcard .kpi-hero'); if (heroEl) heroEl.classList.toggle('filtered', filt);
    // TAM with Scale = < 10 MW: the hero caption already says "AD-scale only", so the variant line steps aside
    if (heroEl) heroEl.classList.toggle('v3-adonly', view === 'tam' && bigPot(rows).adOnly);
    railHeading(view, vc, filt);
    vc.kpis.forEach(function (k, i) {
      var el = document.getElementById('kpi' + i), cap = document.getElementById('kpic' + i), lb = document.getElementById('kpil' + i);
      if (!el) return;
      var sub = k.role === 'sub', m, fmt, label = i === 0 && filt && k.labelFiltered ? k.labelFiltered : k.label, capTxt = '';
      if (sub && k.metric === 'tcvPot') {                          // TAM: "£4.08bn of it from 76 sites ≥ 10 MW"
        var bp = bigPot(rows);
        m = { v: bp.v, f: U.abbr };
        label = bp.rows.length ? 'of it from ' + U.int(bp.rows.length) + ' sites ≥ 10 MW' : bp.adOnly ? 'AD-scale only (<10 MW)' : 'no sites ≥ 10 MW shown';
      } else m = (K.metrics[k.metric] || K.metrics.count)(rows);
      var base = m.f ? m.f : function (x) { return U.num(x, m.d); };
      if (i === 0 && k.metric === 'tcvPot') capTxt = bigPot(rows).adOnly ? 'AD-scale only' : (k.caption || '');
      else capTxt = U.template(k.caption || '', { known: U.int(m.known), n: U.int(rows.length), total: U.int(all.length) });
      if (MONEY[k.metric]) fmt = function (x) { return V3.money(base(x)); };
      else if (i === 0 || sub) fmt = function (x) { return base(x); };
      else fmt = function (x) {                                     // ledger: value, then its unit and caption small
        var v = String(base(x));                                    // (a real space before each, so it reads "105 of 129")
        if (k.unit && v.indexOf('<small>') < 0) v += '<small>' + U.esc(k.unit) + '</small>';
        return v.replace(/\s*<small>/g, ' <small>') + (capTxt ? ' <small>' + U.esc(capTxt) + '</small>' : '');
      };
      if (sub && k.metric === 'tcvPot' && !bigPot(rows).rows.length) { el.setAttribute('data-v', '0'); el.innerHTML = ''; }
      else if (instant || RBX.reduced) { el.setAttribute('data-v', String(m.v)); el.innerHTML = fmt(m.v); } else U.countUp(el, m.v, fmt, 600);
      if (cap) cap.textContent = i === 0 ? capTxt : '';
      if (lb) {
        if (sub) lb.innerHTML = '<span class="lf">' + U.esc(label) + '</span>' + (k.labelShort ? '<span class="ls">' + U.esc(k.labelShort) + '</span>' : '');
        else lb.textContent = label;
      }
      parts.push(label + ' ' + fmt(m.v).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
    });
    if (!instant) announce(parts.join(', '));
  };

  // ------------------------------------------------------------------ (i) popover: view-aware ("How contract value is modelled")
  /** TAM's ≥ 10 MW arithmetic: the £4.08bn comes from the 76 sites ≥ 10 MW with a BM tier, while "< 10 MW" hides all
      81 sites of that size (the other 5 are in Scotland, outside the modelled tiers, and carry no potential). */
  function bigSplit() {
    var big = (RBX.data.rows.tam || []).filter(function (r) { return r.big; }), pot = big.filter(function (r) { return r.bt > 0; }).length;
    return { all: big.length, pot: pot, rest: big.length - pot };
  }
  function scaleNote() {
    var s = bigSplit();
    return 'The <span class="nw">&lt; 10 MW</span> view hides all ' + U.int(s.all) + ' sites of that size' + (s.rest > 0 ? ', including ' + U.int(s.rest) + ' in Scotland with no modelled potential.' : '.');
  }
  if (B && B.popHtml) {
    var pop0 = B.popHtml;
    B.popHtml = function () {
      var view = RBX.state.view;
      if (view === 'tam') return pop0.apply(this, arguments).replace('The AD-scale view excludes them.', scaleNote()).replace('tiers 1–5', 'tiers <span class="nw">1–5</span>');
      var c = cfg(), n = (c.notes || {})[view === 'hydro' ? 'hydro' : 'sam'] || '', a = V3.asOf(view), L = (c.labels || {}).tiers || {}, r = I.TCVRATE || {};
      var tbl = view === 'hydro' ? '' : '<table class="pop-tbl"><caption>' + U.caseSafe('TCV rate by tier, £ per kW available for BM') + '</caption><tbody>' +
        [1, 2, 3, 4, 5].map(function (k) { return '<tr><th scope="row">' + U.esc(L[k] || 'Tier ' + k) + '</th><td class="num">£' + U.num(r[k], 2) + '</td></tr>'; }).join('') + '</tbody></table>';
      // the Sources link carries no data-pop-close: band.js would stop there and never open the drawer (closed below)
      return '<div class="pop-h"><h2 class="pop-t" id="tcvPopT">How contract value is modelled</h2>' +
        '<button type="button" class="sh-x" data-pop-close="1" aria-label="Close (Esc)"><svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15"/></svg></button></div>' +
        '<p>' + U.esc(n) + '</p>' + tbl +
        '<p class="pop-warn"><b>' + U.esc(a.caveat) + '</b> ' + U.esc(a.stamp) + '.</p>' +
        '<div class="pop-act"><button type="button" class="src-link" data-foot="sources">Sources &amp; method' + CHEV + '</button></div>';
    };
  }
  // Placement: band.js drops the popover under its anchor (over the rail, and off the bottom on TAM). v3 docks it
  // beside the open panel, level with the card, and keeps it inside the viewport (it scrolls if it still does not fit).
  if (B && B.openPop) {
    var open0 = B.openPop;
    B.openPop = function (anchor) {
      open0.apply(this, arguments);
      var pop = document.getElementById('tcvPop'); if (!pop || pop.hidden) return;
      var rail = anchor && anchor.closest && anchor.closest('.rail'), top = parseFloat(pop.style.top) || 0;
      var min = (RBX.skin && RBX.skin.headerBottom ? RBX.skin.headerBottom() : 0) + 14;
      if (rail && !rail.classList.contains('collapsed') && !U.isMobile()) {
        var rr = rail.getBoundingClientRect(), kc = anchor.closest('.kcard');
        pop.style.left = Math.round(rr.right + 14) + 'px';
        top = (kc || rail).getBoundingClientRect().top;
      }
      pop.style.maxHeight = '';
      top = Math.max(min, Math.min(top, window.innerHeight - 14 - pop.getBoundingClientRect().height));
      pop.style.top = Math.round(top) + 'px';
      pop.style.maxHeight = Math.round(window.innerHeight - top - 14) + 'px';
    };
  }
  // The popover sits at the end of <body>: Tab past its last control returns to the control after its trigger,
  // Shift+Tab before its first returns to the trigger, and it closes once focus has left it and its trigger.
  /** The popover's trigger; a rail re-render (the TAM Scale button inside the popover) replaces #tcvInfo. */
  function popAnchor() {
    var a = B && B.popAnchor;
    if (a && !a.isConnected && a.id) a = B.popAnchor = document.getElementById(a.id);
    return a && a.isConnected ? a : null;
  }
  function tabbables(root) {
    return U.$$('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])', root)
      .filter(function (el) { return el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden'; });
  }
  document.addEventListener('keydown', function (e) {
    var pop = document.getElementById('tcvPop'), ae = document.activeElement, anchor;
    if (e.key !== 'Tab' || e.altKey || e.ctrlKey || e.metaKey || !pop || pop.hidden || !pop.contains(ae) || !(anchor = popAnchor())) return;
    var f = tabbables(pop); if (!f.length || ae !== (e.shiftKey ? f[0] : f[f.length - 1])) return;
    var target = anchor;
    if (!e.shiftKey) {
      var all = tabbables(document).filter(function (el) { return !pop.contains(el); }), i = all.indexOf(anchor);
      target = i >= 0 && all[i + 1] ? all[i + 1] : anchor;
    }
    e.preventDefault();
    B.closePop(false);
    target.focus();
  });
  document.addEventListener('focusout', function (e) {
    var pop = document.getElementById('tcvPop'), to = e.relatedTarget;
    if (!pop || pop.hidden || !pop.contains(e.target) || !to || pop.contains(to) || to === popAnchor()) return;
    B.closePop(false);
  });
  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('#tcvPop [data-foot="sources"], #tcvPop [data-scale-set]'); if (!t) return;
    // Sources & method: close the popover first (focus back on its trigger, which the drawer returns to on Esc);
    // band.js's own delegation then opens the drawer
    if (t.hasAttribute('data-foot')) { B.closePop(); return; }
    // Scale: band.js re-renders the popover, so put focus back on its (new) Scale button
    setTimeout(function () { var b = document.querySelector('#tcvPop:not([hidden]) [data-scale-set]'); if (b) b.focus({ preventScroll: true }); }, 0);
  }, true);

  // ------------------------------------------------------------------ Sources & method drawer: plainer section titles and words
  // (the method text names the model's variables, AVRATIO and bmKw; the reader sees the words the popover uses)
  if (RBX.hooks.drawerSections) {
    var dr0 = RBX.hooks.drawerSections, RENAME = { 'Legend notes': 'How to read the map', 'TCV method': 'How contract value is modelled', 'Footers': 'Sources' };
    var plain = function (h) {
      return String(h || '').replace(/<b>AVRATIO<\/b>/g, '<b>Available-for-BM ratio</b>').replace(/\bAVRATIO\b/g, 'the available-for-BM ratio')
        .replace(/<b>bmKw<\/b>/g, '<b>Available for BM</b>').replace(/\bbmKw\b/g, 'available-for-BM kW')
        .replace(/( of it from [\d,]+ sites ≥ 10 MW)\./, '$1 with a BM tier; ' + scaleNote().replace(/^The /, 'the '));
    };
    RBX.hooks.drawerSections = function () {
      return (dr0.apply(this, arguments) || []).map(function (sec) { return Object.assign({}, sec, { title: RENAME[sec.title] || sec.title, html: plain(sec.html) }); });
    };
  }

  // ------------------------------------------------------------------ header: "Investor Atlas / Confidential" lockup; Present in the menu
  var hdr0 = RBX.header.render;
  RBX.header.render = function () {
    hdr0.apply(this, arguments);
    var prod = document.querySelector('#hdr .brand-prod');
    if (prod && !prod.closest('.prod-lock')) {
      var lock = document.createElement('div'); lock.className = 'prod-lock';
      prod.parentNode.insertBefore(lock, prod); lock.appendChild(prod);
      lock.insertAdjacentHTML('beforeend', '<span class="conf">' + LOCK + U.esc(confText()) + '</span>');
    }
  };
  // PPA Benchmark: the disclaimer joins the page's "Data as of" line (and the Confidential mark wherever the header
  // lockup is hidden, ≤ 1100 px); ppa.js builds its page once, on first entry
  if (RBX.ppaHost && RBX.ppaHost.show) {
    var ppaShow0 = RBX.ppaHost.show;
    RBX.ppaHost.show = function () {
      var r = ppaShow0.apply(this, arguments);
      var as = document.querySelector('#ppa .ppa-asof');
      if (as && !as.querySelector('.v3-ppa-disc')) {
        as.insertAdjacentHTML('afterbegin', '<span class="v3-ppa-conf">' + LOCK + U.esc(confText()) + ' <i>·</i> </span>');
        as.insertAdjacentHTML('beforeend', '<span class="v3-ppa-disc"> <i>·</i> ' + U.esc(V3.CAVEAT) + '</span>');
      }
      return r;
    };
  }
  RBX.header.menu.push({ id: 'present', order: 5, label: 'Present', hint: 'P',
    icon: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M6.5 4.5v11l9-5.5z" fill="currentColor" stroke="none"/></svg>',
    run: function () { if (RBX.present) RBX.present.enter(0, { gesture: true }); } });

  // ------------------------------------------------------------------ legends: why the tiers pay; calm single-line rows
  var G = RBX.hooks.legendGroups || {};
  if (G.sam) {
    var gSam = G.sam;
    G.sam = function () {
      var sp = gSam.apply(this, arguments), c = cfg(), P = RBX.theme.pal();
      sp.after = '';
      var tiers = sp.groups[0], pend = sp.groups[1];
      if (tiers) {
        tiers.valueFn = function (f) { return U.esc(U.abbr(f.kw || 0)); };
        tiers.items.forEach(function (it) {
          var a = +((c.bmrev || {})[it.value] || {}).a || 0;
          it.sec = U.num(a, 1) + 'p · +' + I.uplift(it.value) + '%'; it.secClass = 'v3t';
          it.title = ''; it.color = P.tier[it.value - 1];
        });
      }
      if (pend) {
        var mw = (RBX.filters.facet('sam', 'pricing', function (r) { return r.kw || 0; })[0] || { kw: 0 }).kw;
        pend.valueFn = function () { return 'No TCV yet'; };
        pend.items.forEach(function (it) { it.sec = U.mw(mw) + ' MW'; it.secClass = 'v3a'; });
      }
      return sp;
    };
  }
  if (G.hydro) {
    var gHyd = G.hydro;
    G.hydro = function () { var sp = gHyd.apply(this, arguments); sp.after = ''; return sp; };
  }
  if (G.tam) {
    var gTam = G.tam;
    G.tam = function () {
      var sp = gTam.apply(this, arguments), lc = (cfg().legend || {}).tam || {};
      sp.after = '';
      var by = {}; sp.groups.forEach(function (g) { by[g.type === 'html' ? 'scale' : g.set] = g; });
      if (by.fuels) { by.fuels.title = lc.fuelTitle || 'Fuel · ring colour'; by.fuels.note = ''; }
      if (by.shapes) by.shapes.title = lc.subsidyTitle || 'Subsidy · shape';
      if (by.tamTiers) by.tamTiers.caption = '';
      sp.groups = [by.fuels, by.shapes, by.fuels && by.fuels.items.length > 6 ? { type: 'html', html: '<span class="v3-more-mark"></span>' } : null,
        by.fuels && by.fuels.items.length > 6 ? { type: 'rows', set: 'fuels', prop: 'fu', mwDigits: 0, items: by.fuels.items.slice(6) } : null,
        by.fuels ? null : null, byFam(sp), by.precision, by.tamTiers, by.scale].filter(Boolean);
      if (by.fuels) by.fuels.items = by.fuels.items.slice(0, 6);
      return sp;
    };
  }
  function byFam(sp) { return sp.groups.filter(function (g) { return g.type === 'famChips'; })[0] || null; }
  /** The sets that sit behind "More filters" (it opens by itself while any of them is filtered). */
  var MORE_SETS = ['precision', 'tamTiers'];
  function moreHidden() {
    var extra = (RBX.legend.fuelOrder ? RBX.legend.fuelOrder() : []).slice(6), fu = RBX.state.hidden.fuels || new Set();
    return MORE_SETS.some(function (s) { return (RBX.state.hidden[s] || new Set()).size > 0; }) || extra.some(function (j) { return fu.has(j); });
  }
  V3.moreOpen = false;

  var lg0 = RBX.legend.html;
  RBX.legend.html = function (view) {
    var h = lg0.apply(this, arguments); if (!h) return h;
    var t = document.createElement('template'); t.innerHTML = h;
    var f = t.content, sec = f.querySelector('.lg'), head = f.querySelector('.r-sec-h');
    if (!sec || !head) return h;
    sec.classList.add('v3-lg', 'v3-lg-' + view);
    var showAll = head.querySelector('[data-showall]');
    if (view === 'sam' || view === 'hydro') {
      if (!showAll) head.insertAdjacentHTML('beforeend', '<span class="lg-cap">' + (view === 'sam' ? 'Contract value' : 'Sites · capacity') + '</span>');
    }
    if (view === 'sam') {
      var subEl = f.querySelector('.r-sub');
      if (subEl) subEl.innerHTML = U.esc(subEl.textContent).replace(/(\d+(?:\.\d+)?p wholesale)/, '<i class="stub" aria-hidden="true"></i>$1');
      U.$$('.lg-row[data-set="tiers"]', f).forEach(function (row) {
        var t0 = +row.getAttribute('data-v'), a = +((cfg().bmrev || {})[t0] || {}).a || 0, s = row.querySelector('.lg-sec'), bar = row.querySelector('.lg-bar b');
        var col = bar ? bar.style.background : 'var(--ink-3)';
        if (s) s.innerHTML = '<span class="bar" aria-hidden="true"><i class="b0"></i><i class="b1" style="width:calc(' + Math.max(0, a - (I.WHOLESALE || 8)).toFixed(1) + ' * var(--v3-ppx));background:' + col + '"></i></span>' +
          U.esc(U.num(a, 1) + 'p') + '<i class="dot">·</i><span class="up">+' + I.uplift(t0) + '%</span>';
        var n = row.querySelector('.lg-n'); if (n) { var k = +n.textContent.replace(/[^\d]/g, ''); n.textContent = U.int(k) + (k === 1 ? ' site' : ' sites'); }
        var bb = row.querySelector('.lg-bar'); if (bb) bb.remove();
      });
      U.$$('.lg-row[data-set="pricing"]', f).forEach(function (row) {
        row.classList.add('await');
        var n = row.querySelector('.lg-n'); if (n) { var k = +n.textContent.replace(/[^\d]/g, ''); n.textContent = U.int(k) + (k === 1 ? ' site' : ' sites'); }
      });
    }
    if (view === 'hydro' || view === 'tam') U.$$('.lg-row', f).forEach(function (row) {
      row.classList.add('one');
      // the "·" between count and MW is CSS: give the toggle a spoken name that keeps the figures apart
      var b = row.querySelector('.lg-main'), lbl = row.querySelector('.lg-lbl'), n = row.querySelector('.lg-n'), mw = row.querySelector('.lg-mw'), k = n ? +n.textContent.replace(/[^\d]/g, '') : 0;
      if (b && lbl && n && mw) b.setAttribute('aria-label', lbl.textContent.trim() + ', ' + U.int(k) + (k === 1 ? ' site, ' : ' sites, ') + mw.textContent.replace(/(\d)([A-Za-z])/, '$1 $2').trim());
    });
    if (view === 'tam') {
      // Scale → a mini segmented control in the legend header
      var seg = f.querySelector('.inv-seg');
      if (seg) {
        var grp = seg.closest('.lg-group');
        seg.className = 'seg-mini'; seg.setAttribute('aria-label', 'Scale');
        U.$$('button', seg).forEach(function (b) {
          var ad = b.getAttribute('data-scale-set') === 'ad', n = b.querySelector('.n');
          b.title = (ad ? 'AD-scale only (<10 MW)' : 'All sizes') + (n ? ': ' + n.textContent + ' sites' : '');
          b.innerHTML = ad ? '&lt; 10 MW' : 'All sizes';
        });
        head.appendChild(seg);
        if (grp) grp.remove();
      }
      U.$$('.r-note', f).forEach(function (n) { n.remove(); });
      // everything after the marker goes behind "More filters"
      var mark = f.querySelector('.v3-more-mark');
      if (mark) {
        var mg = mark.closest('.lg-group'), open = V3.moreOpen || moreHidden();
        var det = document.createElement('details'); det.className = 'v3-more'; if (open) det.open = true;
        var nExtra = Math.max(0, ((RBX.legend.fuelOrder ? RBX.legend.fuelOrder() : []).length) - 6);
        det.innerHTML = '<summary class="more-row"><span>More filters</span><em>' + (nExtra ? nExtra + ' more fuels · ' : '') + 'location · BM tier</em>' + DOWN + '</summary>';
        var after = []; for (var el = mg.nextElementSibling; el; el = el.nextElementSibling) after.push(el);
        after.forEach(function (x) { if (x.classList.contains('lg-group')) det.appendChild(x); });
        mg.replaceWith(det);
      }
    }
    if (showAll && view === 'tam') {           // right of the first group title, whose row is empty on the right (no extra row)
      var gh = f.querySelector('.lg-group-h');
      showAll.classList.add('v3-showall');
      if (gh) gh.appendChild(showAll); else head.insertAdjacentElement('afterend', showAll);
    }
    return t.innerHTML;
  };
  document.addEventListener('toggle', function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('v3-more')) V3.moreOpen = e.target.open;
  }, true);

  // ------------------------------------------------------------------ capacity: a one-row disclosure at the panel foot
  V3.capOpen = false;
  var hist0 = RBX.hist.html;
  RBX.hist.html = function (view) {
    var h = hist0.apply(this, arguments); if (!h) return h;
    var t = document.createElement('template'); t.innerHTML = h;
    var f = t.content, capSec = f.querySelector('#capSec'), head = f.querySelector('#capSec > .r-sec-h');
    if (!capSec || !head) return h;
    var open = V3.capOpen || !!RBX.state.kw[view], title = f.querySelector('#capTitle'), read = f.querySelector('#capRead');
    var h3 = document.createElement('h3'); h3.className = 'r-sec-t v3-cap-h'; h3.id = 'capTitle';
    h3.innerHTML = '<button type="button" class="cap-row" id="capToggle" aria-expanded="' + open + '" aria-controls="capBody"><span class="cap-t">' +
      U.esc(title ? title.textContent : 'Capacity') + '</span>' + (read ? read.outerHTML : '') + DOWN + '</button>';
    head.replaceWith(h3);
    var body = document.createElement('div'); body.className = 'cap-body'; body.id = 'capBody'; if (!open) body.hidden = true;
    ['#capSeg', '#histToggle', '#hist'].forEach(function (q) { var x = capSec.querySelector(q); if (x) body.appendChild(x); });
    capSec.appendChild(body);
    capSec.classList.toggle('active', !!RBX.state.kw[view]);
    return t.innerHTML;
  };
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('#capToggle'); if (!b) return;
    var body = document.getElementById('capBody'); if (!body) return;
    V3.capOpen = body.hidden;
    body.hidden = !V3.capOpen;
    b.setAttribute('aria-expanded', String(V3.capOpen));
    if (V3.capOpen) { RBX.hist.draw(); RBX.hist.sync(); }
    fitRail();
    // bring the opened presets and histogram into view inside the panel (never scroll the page)
    var rb = document.getElementById('railBody');
    if (V3.capOpen && rb) requestAnimationFrame(function () { rb.scrollTop = rb.scrollHeight; });
  });

  // ------------------------------------------------------------------ panel: the bottom fade only when it actually scrolls
  // and, once it has scrolled, a top fade too, so the content passes under a clear head (the collapse button stays
  // on clean glass instead of floating over the hero)
  function fitRail() {
    var body = document.getElementById('railBody'); if (!body) return;
    body.classList.toggle('v3-overflow', body.scrollHeight > body.clientHeight + 1);
    railScrolled();
  }
  function railScrolled() {
    var body = document.getElementById('railBody'), rail = document.getElementById('rail'); if (!body || !rail) return;
    rail.classList.toggle('v3-scrolled', body.scrollTop > 2 && body.classList.contains('v3-overflow'));
  }
  var rail0 = RBX.rail.render;
  RBX.rail.render = function () { rail0.apply(this, arguments); requestAnimationFrame(fitRail); };
  if (window.ResizeObserver) {
    var ro = new ResizeObserver(U.rafThrottle(fitRail));
    RBX.bus.on('ready', function () { var body = document.getElementById('railBody'); if (body) ro.observe(body); });
  }
  window.addEventListener('resize', U.rafThrottle(fitRail));
  document.addEventListener('scroll', function (e) { if (e.target && e.target.id === 'railBody') railScrolled(); }, { capture: true, passive: true });

  // (the PNG export band with the confidentiality marking and the disclaimer is drawn by v3-map.js)

  // ------------------------------------------------------------------ map: hollow "Awaiting BM figure" rings stay hollow
  if (RBX.skin && RBX.skin.syncShadows) {
    var sync0 = RBX.skin.syncShadows;
    RBX.skin.syncShadows = function () {
      sync0.apply(this, arguments);
      var m = RBX.map;
      if (!m || !m.getLayer || !m.getLayer('sam-shadow')) return;
      try { m.setFilter('sam-shadow', ['all', RBX.filters.expr('sam'), ['==', ['get', 'pr'], 1]]); } catch (e) { /* style rebuilt */ }
    };
  }

  // ------------------------------------------------------------------ Present: frame chapters clear of the floating header
  // present.js keeps its own padding (top 40 px); while a chapter moves the camera, top padding and the fly offset
  // also clear whatever part of the floating header stays on screen (V3.presentInset, 0 when it is hidden).
  var Pr = RBX.present, inGo = false;
  V3.presentInset = function () {
    var hdr = document.getElementById('hdr');
    if (!hdr || getComputedStyle(hdr).visibility === 'hidden' || +getComputedStyle(hdr).opacity === 0) return 0;
    return RBX.skin && RBX.skin.headerBottom ? RBX.skin.headerBottom() : 0;
  };
  if (Pr && Pr.go) {
    var go0 = Pr.go;
    Pr.go = function () {
      inGo = true;
      try { return go0.apply(this, arguments); } finally { inGo = false; }
    };
  }
  RBX.bus.on('mapready', function (map) {
    var fit0 = map.fitBounds, fly0 = map.flyTo, inFit = 0;
    map.fitBounds = function (b, o) {
      var ins = inGo ? V3.presentInset() : 0;
      if (ins && o && o.padding && typeof o.padding === 'object') o = Object.assign({}, o, { padding: Object.assign({}, o.padding, { top: Math.max(o.padding.top || 0, ins + 24) }) });
      inFit++;
      try { return fit0.call(this, b, o); } finally { inFit--; }
    };
    map.flyTo = function (o, e) {
      // fitBounds ends in this.flyTo(), which already honours the fit's padding: only direct flights are shifted
      var ins = inGo && !inFit ? V3.presentInset() : 0;
      if (ins && o) { var off = o.offset || [0, 0]; o = Object.assign({}, o, { offset: [off[0], off[1] + Math.round(ins / 2)] }); }
      return fly0.call(this, o, e);
    };
  });
})();
