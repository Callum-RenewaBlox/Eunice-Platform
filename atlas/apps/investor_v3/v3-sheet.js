/* Investor Atlas v3 · site sheet (design spec §9). Bundled after core/js/investor/cards.js, the product skin and
   investor-v3.js, so each registration below replaces the earlier one with the same id (last registration wins):
   - the kind chip: SAM tier dot + "Tier 2 · Strong" (unpriced: hollow ring + "Awaiting BM figure"), Hydro
     confidence dot + "High confidence";
   - SAM head (order 10): name, then town · postcode · GSP; the tier lives in the chip only;
   - Contract value (SAM and Hydro, order 15): a white card with the no-treasury figure, the treasury variant on the
     right, the energy-vs-BTC split bar (solid teal vs sky hatch) and a hairline ledger;
   - Projected BM revenue (SAM, order 20): the uplift over wholesale, average and top 5% figures and the core ladder
     (the registered section's own `after`), redrawn in the v3 grammar;
   - Capacity, route, register, stranded and nearby keep the investor modules' content and take the card style.
   Inert unless <html data-skin="product" data-app="investor">. */
(function () {
  'use strict';
  var RBX = window.RBX, doc = document.documentElement;
  if (doc.getAttribute('data-skin') !== 'product' || doc.getAttribute('data-app') !== 'investor') return;
  var U = RBX.util, Sh = RBX.sheet, C = RBX.cards, I = RBX.inv || {};
  if (!Sh || !C) return;

  var TARGET = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="5.5"/><path d="M10 1.8v3.4M10 14.8v3.4M1.8 10h3.4M14.8 10h3.4"/></svg>';

  function L() { return RBX.config.labels || {}; }
  function find(kind, id) { return (Sh.sections[kind] || []).filter(function (s) { return s.id === id; })[0]; }
  function awaitingLabel() { return (((RBX.config.legend || {}).sam) || {}).awaiting || 'Awaiting BM figure'; }
  /** £2.9M with a small magnitude letter (RBX.v3.money from investor-v3.js; same markup if it is missing). */
  function money(v) {
    if (RBX.v3 && RBX.v3.money) return RBX.v3.money(v);
    var m = /^(-?£?[\d.,]+)\s*(k|M|bn)?$/.exec(U.abbr(v));
    return m ? '<span class="money">' + U.esc(m[1]) + (m[2] ? '<span class="mag">' + m[2] + '</span>' : '') + '</span>' : U.esc(U.abbr(v));
  }
  /** A sheet card: tracked-caps title, a quiet note on the right, then the body. */
  function sec(title, right, body, cls) {
    return '<section class="sh-sec' + (cls ? ' ' + cls : '') + '"><div class="sh-sec-h"><h3 class="sh-sec-t">' + U.esc(title) + '</h3>' +
      (right ? '<span class="sh-sec-a">' + U.esc(right) + '</span>' : '') + '</div>' + body + '</section>';
  }
  /** Hairline ledger rows: [label, label suffix (quiet), value html, unit]. */
  function ledger(rows) {
    return '<dl class="sh-ledger">' + rows.filter(Boolean).map(function (r) {
      return '<div><dt>' + U.esc(r[0]) + (r[1] ? ' <em>' + U.esc(r[1]) + '</em>' : '') + '</dt><dd class="num">' + r[2] +
        (r[3] ? '<small>' + U.esc(r[3]) + '</small>' : '') + '</dd></div>';
    }).join('') + '</dl>';
  }
  function dot(color, ring) {
    return '<i class="v3-dot' + (ring ? ' ring' : '') + '" style="' + (ring ? 'color' : 'background') + ':' + color + '" aria-hidden="true"></i>';
  }

  // ------------------------------------------------------------------ contract value (SAM and Hydro share the grammar)
  /** Hero row: the no-treasury figure on the left, the treasury variant right-aligned. */
  function heroRow(r) {
    return '<div class="v3-com-hero">' +
      '<div class="v3-com-l"><div class="v3-com-big">' + money(r.tcv) + '<span class="cap">no treasury</span></div>' +
      '<div class="v3-com-ex num">' + U.esc(U.gbp0(r.tcv)) + '</div></div>' +
      '<div class="v3-com-alt"><span>With BTC held in treasury</span><b>' + money(r.tcvT) + '</b>' +
      '<small class="num">' + U.esc(U.gbp0(r.tcvT)) + '</small></div></div>';
  }
  /** Energy & BM revenue (en, solid teal) against BTC value (tcv − en, sky hatch), with a keyed legend. */
  function split(r) {
    var en = Math.max(0, r.en || 0), bv = Math.max(0, (r.tcv || 0) - en), tot = en + bv || 1;
    var pe = Math.round(en / tot * 100), pb = 100 - pe;
    var bar = C.splitBar([{ v: en, cls: 'v3-e' }, { v: bv, cls: 'btcv' }], 'Energy and BM revenue ' + pe + '%, BTC value ' + pb + '%');
    var btc = '<span><i class="k btcv"></i>BTC value <b>' + U.esc(U.abbr(bv)) + '</b> ' + pb + '%</span>';
    var left = en > 0 ? '<span><i class="k v3-e"></i>Energy &amp; BM <b>' + U.esc(U.abbr(en)) + '</b> ' + pe + '%</span>' + btc
      : btc + '<span>Energy export <b>£0</b></span>';
    return bar + '<div class="capbar-l v3-split-l">' + left + '</div>';
  }

  // ------------------------------------------------------------------ SAM
  /** Priced: tier dot + tier name. Unpriced: the legend's neutral hollow ring + "Awaiting BM figure". */
  Sh.chip.sam = function (r) {
    return r.pr ? dot(RBX.theme.pal().tier[r.t - 1]) + '<span>' + U.esc(L().tiers[r.t]) + '</span>'
      : dot('var(--ink-2)', true) + '<span>' + U.esc(awaitingLabel()) + '</span>';
  };
  /** Town · postcode · GSP. The chip carries the tier, so it is not repeated here (only an unpriced site, whose chip
      reads "Awaiting BM figure", names its tier at the end). */
  Sh.section('sam', 'head', { order: 10, render: function (r) {
    var gsp = r.gsp ? 'GSP ' + String(r.gsp).replace(/\s*\([^)]*\)\s*$/, '') : '';
    return C.head(r.name, [r.town, r.pc, gsp, r.pr ? '' : L().tiers[r.t]]);
  } });
  Sh.section('sam', 'commercials', { order: 15, render: function (r) {
    if (!r.pr) {
      return sec('Contract value', 'Year 5', '<div class="v3-await"><i class="v3-dot ring" aria-hidden="true"></i><b>' + U.esc(awaitingLabel()) + '</b></div>' +
        '<p class="note-i">' + C.INFO + '<span>This site has no available-for-BM figure yet, so no contract value is modelled. It is drawn as a hollow ring.</span></p>',
        'v3-com is-await');
    }
    return sec('Contract value', 'Year 5', heroRow(r) + split(r) + ledger([
      ['BTC mined', '· Year 5', U.num(r.btc, 2), 'BTC'],
      r.av ? ['TCV per kW available', '', '£' + U.num(r.tcv / r.av, 0)] : null
    ]), 'v3-com');
  } });

  /** The core ladder (drawn by the registered section's `after`) in the v3 grammar: hairline grid, hollow end dots
      (2.6 px, ink-4) on the other tiers, 3.6 px dots with a hollow top 5% cap on the site's own tier. */
  function tuneLadder(el, r) {
    var svg = el.querySelector('.ladder svg'); if (!svg) return;
    Array.prototype.forEach.call(svg.querySelectorAll('line'), function (ln) {
      if (ln.getAttribute('stroke') === 'var(--rule)') { ln.setAttribute('stroke', 'var(--v3-hair)'); ln.setAttribute('class', 'g'); }
      else ln.setAttribute('stroke-linecap', 'round');
    });
    Array.prototype.forEach.call(svg.querySelectorAll('text[text-anchor="middle"]'), function (t) { t.setAttribute('class', 'ax'); });
    var cs = svg.querySelectorAll('circle');
    for (var j = 0; j + 1 < cs.length; j += 2) {
      var a = cs[j], top = cs[j + 1], col = top.getAttribute('stroke'), own = j / 2 + 1 === r.t;
      top.setAttribute('fill', 'var(--surface-1)');
      if (own) {
        a.setAttribute('r', '3.6'); top.setAttribute('r', '3.6'); top.setAttribute('stroke-width', '2');
      } else {
        a.setAttribute('r', '2.6'); a.setAttribute('fill', 'var(--surface-1)'); a.setAttribute('stroke', col); a.setAttribute('stroke-width', '1.5');
        top.setAttribute('r', '2.6'); top.setAttribute('stroke-width', '1.5');
      }
    }
  }
  var rev0 = find('sam', 'revenue'), ladder = rev0 && rev0.after;
  Sh.section('sam', 'revenue', { order: 20, after: function (el, r) { if (ladder) ladder(el, r); tuneLadder(el, r); }, render: function (r) {
    var b = (RBX.config.bmrev || {})[r.t];
    if (!b) return '';
    var up = I.uplift ? I.uplift(r.t) : null, wh = I.WHOLESALE || 8;
    var why = up == null || isNaN(up) ? '' : '<p class="v3-why"><b>' + (up < 0 ? '−' : '+') + Math.abs(up) + '%</b> against the ' + U.num(wh, 1) + 'p wholesale baseline</p>';
    return sec('Projected BM revenue', 'next 12 months', why +
      '<div class="v3-rev-figs"><div><span>Average</span><b class="num">' + U.esc(b.a) + '<small>p/kWh</small></b></div>' +
      '<div><span>Top 5%</span><b class="num">' + U.esc(b.t) + '<small>p/kWh</small></b></div></div>' +
      (ladder ? '<div class="ladder"></div>' : ''), 'v3-rev');
  } });

  // ------------------------------------------------------------------ Hydro
  Sh.chip.hydro = function (r) {
    var P = RBX.theme.pal();
    return r.c === 3 ? dot(P.unv, true) + '<span>Unverified</span>' : dot(P.hyd[r.c]) + '<span>' + U.esc(r.conf + ' confidence') + '</span>';
  };
  /** The export class moves from the chip (which now carries confidence only) into the meta line. */
  Sh.section('hydro', 'head', { order: 10, render: function (r) {
    var ex = (L().hydroExport || [])[r.expc] || r.exp;
    return C.head(r.name, ['Stranded hydro', ex, U.num(Math.abs(r.lat), 2) + '° ' + (r.lat >= 0 ? 'N' : 'S') + ', ' + U.num(Math.abs(r.lon), 2) + '° ' + (r.lon < 0 ? 'W' : 'E')]);
  } });
  Sh.section('hydro', 'commercials', { order: 15, render: function (r) {
    if (r.tcv == null) return '';
    return sec('Contract value', 'Year 5', heroRow(r) + split(r) + ledger([['BTC mined', '· Year 5', U.num(r.btc, 2), 'BTC']]), 'v3-com');
  } });
  /** Stranded capacity keeps its content; its headline figure is ink, not the confidence colour (the chip carries it). */
  var str0 = find('hydro', 'stranded');
  if (str0) {
    Sh.section('hydro', 'stranded', { order: str0.order, after: str0.after, render: function (r) {
      return String(str0.render(r) || '').replace(/<div class="hero" style="color:[^"]*">/, '<div class="hero">');
    } });
  }

  // ------------------------------------------------------------------ actions: three equal ghost buttons
  var zoom = { order: 20, render: function () { return '<button type="button" class="btn" data-act="zoom">' + TARGET + 'Zoom to site</button>'; } };
  ['sam', 'hydro', 'tam'].forEach(function (k) {
    if ((Sh.actions[k] || []).some(function (a) { return a.id === 'zoom'; })) Sh.action(k, 'zoom', zoom);
  });
})();
