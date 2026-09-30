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
    if (top) top.insertAdjacentHTML('beforeend', '<button type="button" class="i-btn" id="tcvInfo" aria-haspopup="dialog" aria-expanded="false" aria-controls="tcvPop" aria-label="' +
      (view === 'tam' ? 'How TCV Potential is calculated' : 'How contract value is modelled') + '">' + INFO + '</button>');
    kp.forEach(function (k, i) {
      if (k.role !== 'sub') return;
      var cell = f.querySelector('#kpi' + i); cell = cell && cell.closest('.kpi'); if (!cell) return;
      cell.remove();
      hero.insertAdjacentHTML('beforeend', '<div class="kpi-sub"><b class="kpi-v" id="kpi' + i + '"></b> <span class="kpi-l" id="kpil' + i + '"></span></div>');
    });
    var uni = f.querySelector('.universe');
    var a = V3.asOf(view);
    var cav = document.createElement('div'); cav.className = 'caveat';
    cav.innerHTML = INFO + '<div class="cv"><span class="conf-fb">' + LOCK + U.esc(confText()) + '</span><b>' + U.esc(a.caveat) + '</b>' +
      '<div class="row"><span>' + U.esc(a.stamp) + '</span><button type="button" class="src-link" data-foot="sources" aria-label="Sources &amp; method">Sources' + CHEV + '</button></div></div>';
    if (uni) uni.replaceWith(cav); else grid.appendChild(cav);
    var card = f.querySelector('.kcard');
    var peek = '<p class="v3-peekline">' + LOCK + '<span>' + U.esc(confText().split(' · ')[0]) + '</span><i>·</i><span>' + U.esc(a.stamp.replace(' · ', ' ')) + '</span><i>·</i><span>' + U.esc(a.caveat) + '</span></p>';
    if (card) card.insertAdjacentHTML('afterend', peek);
    return t.innerHTML;
  };

  var announce = U.debounce(function (msg) { var l = document.getElementById('live'); if (l) l.textContent = msg; }, 400);
  K.update = function (instant) {
    var view = RBX.state.view, vc = (RBX.config.views || {})[view] || {};
    if (!vc.kpis || view === 'ppa') return;
    var rows = K.rows(view), all = RBX.data.rows[view] || [], parts = [], filt = filtered(view);
    var heroEl = document.querySelector('.kcard .kpi-hero'); if (heroEl) heroEl.classList.toggle('filtered', filt);
    vc.kpis.forEach(function (k, i) {
      var el = document.getElementById('kpi' + i), cap = document.getElementById('kpic' + i), lb = document.getElementById('kpil' + i);
      if (!el) return;
      var sub = k.role === 'sub', m, fmt, label = i === 0 && filt && k.labelFiltered ? k.labelFiltered : k.label, capTxt = '';
      if (sub && k.metric === 'tcvPot') {                          // TAM: "£4.08bn of it from 76 sites ≥ 10 MW"
        var bp = bigPot(rows);
        m = { v: bp.v, f: U.abbr };
        label = bp.rows.length ? 'of it from ' + U.int(bp.rows.length) + ' sites ≥ 10 MW' : bp.adOnly ? 'AD-scale only (<10 MW)' : 'no sites ≥ 10 MW in view';
      } else m = (K.metrics[k.metric] || K.metrics.count)(rows);
      var base = m.f ? m.f : function (x) { return U.num(x, m.d); };
      if (i === 0 && k.metric === 'tcvPot') capTxt = bigPot(rows).adOnly ? 'AD-scale only' : (k.caption || '');
      else capTxt = U.template(k.caption || '', { known: U.int(m.known), n: U.int(rows.length), total: U.int(all.length) });
      if (MONEY[k.metric]) fmt = function (x) { return V3.money(base(x)); };
      else if (i === 0 || sub) fmt = function (x) { return base(x); };
      else fmt = function (x) {                                     // ledger: value, then its unit and caption small
        var v = String(base(x));
        if (k.unit && v.indexOf('<small>') < 0) v += '<small>' + U.esc(k.unit) + '</small>';
        return v + (capTxt ? '<small>' + U.esc(capTxt) + '</small>' : '');
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
  if (B && B.popHtml) {
    var pop0 = B.popHtml;
    B.popHtml = function () {
      var view = RBX.state.view;
      if (view === 'tam') return pop0.apply(this, arguments);
      var c = cfg(), n = (c.notes || {})[view === 'hydro' ? 'hydro' : 'sam'] || '', a = V3.asOf(view), L = (c.labels || {}).tiers || {}, r = I.TCVRATE || {};
      var tbl = view === 'hydro' ? '' : '<table class="pop-tbl"><caption>' + U.caseSafe('TCV rate by tier, £ per kW available for BM') + '</caption><tbody>' +
        [1, 2, 3, 4, 5].map(function (k) { return '<tr><th scope="row">' + U.esc(L[k] || 'Tier ' + k) + '</th><td class="num">£' + U.num(r[k], 2) + '</td></tr>'; }).join('') + '</tbody></table>';
      return '<div class="pop-h"><h2 class="pop-t" id="tcvPopT">How contract value is modelled</h2>' +
        '<button type="button" class="sh-x" data-pop-close="1" aria-label="Close (Esc)"><svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15"/></svg></button></div>' +
        '<p>' + U.esc(n) + '</p>' + tbl +
        '<p class="pop-warn"><b>' + U.esc(a.caveat) + '</b> ' + U.esc(a.stamp) + '.</p>' +
        '<div class="pop-act"><button type="button" class="src-link" data-foot="sources" data-pop-close="1">Sources &amp; method' + CHEV + '</button></div>';
    };
  }

  // ------------------------------------------------------------------ Sources & method drawer: plainer section titles
  if (RBX.hooks.drawerSections) {
    var dr0 = RBX.hooks.drawerSections, RENAME = { 'Legend notes': 'How to read the map', 'TCV method': 'How contract value is modelled', 'Footers': 'Sources' };
    RBX.hooks.drawerSections = function () {
      return (dr0.apply(this, arguments) || []).map(function (sec) { return Object.assign({}, sec, { title: RENAME[sec.title] || sec.title }); });
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
    if (view === 'hydro' || view === 'tam') U.$$('.lg-row', f).forEach(function (row) { row.classList.add('one'); });
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
    if (showAll && view === 'tam') { showAll.classList.add('v3-showall'); head.insertAdjacentElement('afterend', showAll); }
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
  function fitRail() {
    var body = document.getElementById('railBody'); if (!body) return;
    body.classList.toggle('v3-overflow', body.scrollHeight > body.clientHeight + 1);
  }
  var rail0 = RBX.rail.render;
  RBX.rail.render = function () { rail0.apply(this, arguments); requestAnimationFrame(fitRail); };
  if (window.ResizeObserver) {
    var ro = new ResizeObserver(U.rafThrottle(fitRail));
    RBX.bus.on('ready', function () { var body = document.getElementById('railBody'); if (body) ro.observe(body); });
  }
  window.addEventListener('resize', U.rafThrottle(fitRail));

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
