/* Investor build only. Investor sections for the detail sheet (spec 6.4 "Investor cards"), registered into the
   core section registry: SAM head (tier | town · postcode · GSP), Commercials (TCV, TCV treasury, TCV split
   bar energy vs BTC value, BTC mined) or "Awaiting BM figure", route to market with the full operator, register
   data from the PPA module's data; Hydro commercials; TAM facts with the source-register subsidy and location. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, Sh = RBX.sheet, C = RBX.cards, I = RBX.inv;
  var STATUS = { active: 'good', 'lagging/winding down': 'warning', 'likely ceased': 'critical', 'no REGO certs': 'neutral' };

  function L() { return RBX.config.labels; }
  function money(label, v, cls) {
    return '<div class="fig"><div class="fig-l">' + U.esc(label) + '</div><div class="fig-v l ' + (cls || '') + '">' + U.esc(U.abbr(v)) + '</div>' +
      '<div class="fig-s num">' + U.esc(U.gbp0(v)) + '</div></div>';
  }
  function kv(pairs) {
    return '<dl class="kv">' + pairs.filter(Boolean).map(function (p) { return '<dt>' + U.esc(p[0]) + '</dt><dd' + (p[2] ? ' class="' + p[2] + '"' : '') + '>' + p[1] + '</dd>'; }).join('') + '</dl>';
  }
  /** Energy / BM revenue (en) vs BTC value (tcv − en), spec 6.4. */
  function tcvSplit(r, P) {
    var en = Math.max(0, r.en || 0), btcV = Math.max(0, (r.tcv || 0) - en), tot = en + btcV || 1;
    var pe = Math.round(en / tot * 100), pb = 100 - pe;
    return C.splitBar([{ v: en, color: P.tier[r.t - 1] }, { v: btcV, cls: 'btcv' }], 'Energy and BM revenue ' + pe + '%, BTC value ' + pb + '%') +
      '<div class="capbar-l"><span><i class="k" style="background:' + P.tier[r.t - 1] + '"></i>Energy &amp; BM ' + U.esc(U.abbr(en)) + ' · ' + pe + '%</span>' +
      '<span><i class="k btcv"></i>BTC value ' + U.esc(U.abbr(btcV)) + ' · ' + pb + '%</span></div>';
  }
  function statusHtml(label) {
    if (!label) return '—';
    return '<span class="stat-dot ' + (STATUS[label] || 'neutral') + '" aria-hidden="true"></span>' + U.esc(label);
  }

  // ------------------------------------------------------------------ SAM
  Sh.section('sam', 'head', { order: 10, render: function (r) {
    var meta = [r.town, r.pc, r.gsp].filter(Boolean).map(U.esc).join(' · ');
    return '<h2 class="sh-name" id="sheetName">' + U.esc(r.name) + '</h2><div class="sh-meta">' + U.esc(L().tiers[r.t]) + ' <span class="sep">|</span> ' + meta + '</div>';
  } });
  Sh.section('sam', 'commercials', { order: 15, render: function (r) {
    var P = RBX.theme.pal();
    if (!r.pr) {
      return C.sec('Commercials', 'Year 5', kv([['Status', '<b>Awaiting BM figure</b>', 'hl']]) +
        '<p class="note-i">' + C.INFO + '<span>This site has no available-for-BM figure yet, so no contract value is modelled. It is drawn as a hollow ring.</span></p>');
    }
    return C.sec('Commercials', 'Year 5',
      '<div class="figs two">' + money('TCV · no treasury', r.tcv) + money('TCV · treasury', r.tcvT, 'hl') + '</div>' +
      tcvSplit(r, P) +
      kv([['BTC mined (Yr 5)', '<span class="num">' + U.num(r.btc, 2) + '</span>'],
        ['TCV per kW available', '<span class="num">£' + U.num(r.tcv / (r.av || 1), 0) + '</span>']]));
  } });
  Sh.section('sam', 'capacity', { order: 30, render: function (r) {
    var P = RBX.theme.pal(), inst = r.kw || 0, av = r.pr ? r.av : r.kwBm;
    var bar = '';
    if (av != null && inst) {
      var pa = Math.round(av / inst * 100);
      bar = C.splitBar([{ v: av, color: P.tier[r.t - 1] }, { v: Math.max(0, inst - av), cls: 'hatch' }], 'Available for BM ' + pa + '% of installed') +
        '<div class="capbar-l"><span>Available for BM ' + pa + '%</span><span>Onsite / not split ' + (100 - pa) + '%</span></div>';
    }
    return C.sec('Capacity', 'kW', '<div class="figs two">' + C.fig('Installed capacity', U.int(r.kw), 'kW') +
      C.fig('Available for BM', av == null ? null : U.int(av), 'kW') + '</div>' + bar);
  } });
  Sh.section('sam', 'route', { order: 40, render: function (r) {
    var cc = RBX.config.cards || {}, off = r.off === 'Generator is sole holder' ? 'Sole holder · unbundled' : (r.off || 'Not identified');
    var op = r.dev || r.op;
    var exp = r.ppa ? '<span class="expchip ' + r.ppa + '">' + U.esc(L().export[r.ppa] || 'Unknown') + '</span>' : 'Unknown';
    return C.sec('Route to market', '', kv([
      op ? ['Operator', '<span class="ell" title="' + U.esc(op) + '">' + U.esc(op) + '</span>' + I.opTag(r)] : null,
      ['Offtaker', U.esc(off) + ' <span class="tag" tabindex="0" title="' + U.esc(cc.offtakerTip || '') + '">inferred</span>'],
      ['Export', exp]
    ]));
  } });
  Sh.section('sam', 'register', { order: 50, render: function (r) {
    var yrs = r.yrsLeft, runway = yrs == null ? '' : '<span class="runway" aria-hidden="true"><b style="width:' + Math.min(100, yrs / 10 * 100).toFixed(0) + '%"></b></span>';
    var status = ((L().rego || {})[r.rego]) || r.regoRaw;
    return C.sec('Register', 'PPA Benchmark', kv([
      r.comm ? ['Commissioned', '<span class="num">' + r.comm + '</span>'] : null,
      ['FiT gen p/kWh', r.fitGen == null ? '—' : '<span class="num">' + U.num(r.fitGen, 2) + '</span>'],
      ['FiT ends', U.esc(U.fmtDate(r.fitEnd))],
      ['Yrs left', yrs == null ? '—' : runway + '<span class="num">' + U.num(yrs, 1) + '</span>'],
      ['REGO status', statusHtml(status)]
    ]));
  } });
  Sh.removeAction('sam', 'talk');

  // ------------------------------------------------------------------ Hydro
  Sh.chip.hydro = function (r) {
    var P = RBX.theme.pal(), ex = (L().hydroExport || [])[r.expc] || r.exp;
    return (r.c === 3 ? RBX.icons.svg({ shape: 'ring', color: P.unv, size: 11 }) : RBX.icons.svg({ shape: 'dot', color: P.hyd[r.c], size: 11 })) +
      '<span>' + U.esc(ex + ' · ' + (r.c === 3 ? 'Unverified' : r.conf + ' confidence')) + '</span>';
  };
  Sh.section('hydro', 'commercials', { order: 15, render: function (r) {
    if (r.tcv == null) return '';
    return C.sec('Commercials', 'Year 5',
      '<div class="figs two">' + money('TCV · no treasury', r.tcv) + money('TCV · treasury', r.tcvT, 'hl') + '</div>' +
      kv([['BTC mined (Yr 5)', '<span class="num">' + U.num(r.btc, 2) + '</span>'], ['Energy export', '£0 · 100% mining']]));
  } });
  Sh.removeAction('hydro', 'talk');

  // ------------------------------------------------------------------ TAM
  Sh.section('tam', 'facts', { order: 20, render: function (r) {
    var L2 = L(), cap = r.kw == null ? '—' : U.int(r.kw) + (r.kw >= 10000 ? '<small>kW (' + U.num(r.kw / 1000, 1) + ' MW)</small>' : '<small>kW</small>');
    var sub = r.ro ? 'RO accredited' : r.src === 'FiT' ? 'FiT accredited' : 'Not confirmed';
    var pot = r.bt > 0 ? '<div class="pot-line"><span>Indicative TCV potential</span><b class="num">' + U.esc(U.abbr(r.pot)) + '</b>' +
      '<button type="button" class="band-i" data-tcv-method="1" aria-label="How TCV Potential is calculated" title="Available-for-BM kW × the Tier ' + r.bt + ' TCV rate (£' + U.num(I.TCVRATE[r.bt], 2) + '/kW)">' + C.INFO + '</button></div>' +
      (r.big ? '<p class="note-i">' + C.INFO + '<span>10 MW and over: valued with AD-peaker economics, so treat this figure with the most caution.</span></p>' : '') : '';
    return C.sec('Capacity & subsidy', '',
      '<div class="figs two"><div class="fig"><div class="fig-l">Capacity</div><div class="fig-v">' + cap + '</div></div>' +
      C.fig('Available for BM', r.bm == null ? null : U.int(r.bm), 'kW') + '</div>' + pot +
      '<div style="margin-top:12px">' + kv([
        r.units > 1 ? ['Aggregated units', '<span class="num">' + U.int(r.units) + '</span>'] : null,
        [r.bt ? 'BM tier' : 'BM status', U.esc(L2.tiers[r.bt]) + (r.bt ? ' <i>(indicative)</i>' : ''), 'hl'],
        ['Subsidy', sub],
        r.ro ? ['RO ref', '<span class="mono">' + U.esc(r.ro) + '</span>'] : null,
        ['Location', r.ap ? 'Approx · postcode district' : 'Exact · DNO register'],
        r.samRow ? ['In SAM', 'Verified site', 'hl'] : null
      ]) + '</div>');
  } });

  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-tcv-method]'); if (!b) return;
    var info = document.getElementById('tcvInfo');
    RBX.band.openPop(b);
    if (info) info.setAttribute('aria-expanded', 'true');
  });
})();
