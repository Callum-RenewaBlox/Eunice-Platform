/* RBX.cards: client-safe sheet sections for SAM, TAM and Hydro (spec 6.4), value first, every v1 field.
   Registered into RBX.sheet; audience modules add or replace sections by id. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, Sh = RBX.sheet;
  var C = RBX.cards = {};
  var INFO = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.1"/></svg>';
  C.INFO = INFO;

  function L() { return RBX.config.labels; }
  C.sec = function (title, right, body) {
    return '<section class="sh-sec"><div class="sh-sec-h"><h3 class="sh-sec-t">' + U.esc(title) + '</h3>' + (right ? '<span class="sh-sec-a">' + right + '</span>' : '') + '</div>' + body + '</section>';
  };
  C.fig = function (label, v, unit, cls) {
    return '<div class="fig"><div class="fig-l">' + U.esc(label) + '</div>' + (v == null ? '<div class="fig-v u">Unknown</div>' :
      '<div class="fig-v ' + (cls || '') + '">' + v + (unit ? '<small>' + U.esc(unit) + '</small>' : '') + '</div>') + '</div>';
  };
  C.head = function (name, meta) {
    return '<h2 class="sh-name" id="sheetName">' + U.esc(name) + '</h2><div class="sh-meta">' + meta.filter(Boolean).map(U.esc).join('<span class="sep">·</span>') + '</div>';
  };
  C.nearby = function (r, label) {
    var list = RBX.filters.active(r.kind).filter(function (x) { return x !== r; })
      .map(function (x) { return [x, U.km([r.lon, r.lat], [x.lon, x.lat])]; })
      .sort(function (a, b) { return a[1] - b[1]; }).slice(0, 3);
    if (!list.length) return '';
    return C.sec(label || 'Nearby', 'distance', '<div class="near">' + list.map(function (p) {
      return '<button type="button" data-hop="' + p[0].kind + ':' + p[0].id + '">' + RBX.icons.forRow(p[0], 14) + '<span class="near-n">' + U.esc(p[0].name) + '</span><span class="near-d">' +
        (p[1] < 10 ? U.num(p[1], 1) : U.int(p[1])) + ' km</span></button>';
    }).join('') + '</div>');
  };
  C.splitBar = function (parts, label) {
    return '<div class="capbar" role="img" aria-label="' + U.esc(label) + '">' + parts.filter(function (p) { return p.v > 0; }).map(function (p) {
      return '<span class="' + (p.cls || '') + '" style="flex:' + p.v + (p.color ? ';background:' + p.color : '') + '"></span>';
    }).join('') + '</div>';
  };

  // ------------------------------------------------------------------ actions (shared)
  C.mailto = function (r) {
    var cfg = RBX.config, cc = cfg.cards || {}, url = RBX.state.shareUrl(r);
    var o = { name: r.name, town: r.town || (r.kind === 'hydro' ? 'stranded hydro' : ''), outcode: r.outcode || r.pc || '', postcode: r.pc || (U.num(r.lat, 3) + ', ' + U.num(r.lon, 3)),
      tier: r.kind === 'sam' ? L().tiers[r.t] : (r.c === 3 ? 'Unverified' : r.conf + ' confidence'), installed: U.int(r.kind === 'hydro' ? r.inst : r.kw), url: url };
    var subj = U.template(cc.mailSubject || 'RenewaBlox — {name}', o).replace(/, \s*\(\)$/, '').replace(/ \(\)$/, '');
    var body = U.template(cc.mailBody || '', o);
    return 'mailto:' + String(cfg.contactEmail || '').replace(/[^A-Za-z0-9@._+-]/g, '') + '?subject=' + encodeURIComponent(subj) + '&body=' + encodeURIComponent(body);
  };
  var ICON = {
    mail: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="5" width="14" height="10.5" rx="1.5"/><path d="m3.5 6 6.5 5 6.5-5"/></svg>',
    zoom: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M13 13l4 4M8.5 6v5M6 8.5h5"/></svg>',
    link: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M8.5 11.5a3.5 3.5 0 0 0 5 0l2.5-2.5a3.5 3.5 0 0 0-5-5l-1 1"/><path d="M11.5 8.5a3.5 3.5 0 0 0-5 0L4 11a3.5 3.5 0 0 0 5 5l1-1"/></svg>',
    table: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="4" width="14" height="12" rx="1.5"/><path d="M3 8h14M3 12h14M8 4v12"/></svg>'
  };
  C.ICON = ICON;
  C.actTalk = { order: 10, render: function (r) { return '<a class="btn btn-primary" href="' + U.esc(C.mailto(r)) + '" target="_blank" rel="noopener">' + ICON.mail + 'Talk to us about this site</a>'; } };
  C.actZoom = { order: 20, render: function () { return '<button type="button" class="btn" data-act="zoom">' + ICON.zoom + 'Zoom to site</button>'; } };
  C.actLink = { order: 30, render: function () { return '<button type="button" class="btn" data-act="link">' + ICON.link + '<span>Copy link</span></button>'; } };
  C.actRegister = { order: 40, render: function () { return '<button type="button" class="btn" data-act="register">' + ICON.table + 'See in register</button>'; } };

  document.addEventListener('click', function (e) {
    var b = e.target.closest('#sheet [data-act]'); if (!b) return;
    var r = RBX.sheet.current(); if (!r) return;
    var act = b.getAttribute('data-act');
    if (act === 'zoom') RBX.mapctl.flyTo(r, { zoom: 12 });
    if (act === 'link') {
      U.copyText(RBX.state.shareUrl(r), b.closest('.sh-actions')).then(function (ok) {
        if (ok) { var s = b.querySelector('span'); if (s) { s.textContent = 'Link copied'; setTimeout(function () { if (s.isConnected) s.textContent = 'Copy link'; }, 1600); } }
      });
    }
    if (act === 'register') RBX.app.showInRegister(r);
    if (act === 'open-sam' && r.samRow) RBX.app.openSite(r.samRow, { fly: true });
  });

  // ------------------------------------------------------------------ SAM
  var LADDER_MAX = 125;
  function ladder(el, r) {
    var host = el.querySelector('.ladder'); if (!host) return;
    var P = RBX.theme.pal(), rev = RBX.config.bmrev, W = Math.max(240, Math.floor(host.clientWidth || 320)), row = 17, top = 4, H = top + row * 5 + 18;
    var x0 = 26, x1 = W - 8, X = function (v) { return x0 + (x1 - x0) * v / LADDER_MAX; };
    var s = '<svg width="' + W + '" height="' + H + '" role="img" aria-label="Projected revenue by tier, average to top 5%, p/kWh. This site is Tier ' + r.t + '.">';
    [0, 25, 50, 75, 100, 125].forEach(function (v) {
      s += '<line x1="' + X(v) + '" x2="' + X(v) + '" y1="' + top + '" y2="' + (top + row * 5) + '" stroke="var(--rule)"/><text x="' + X(v) + '" y="' + (H - 3) + '" text-anchor="middle">' + v + (v === 125 ? 'p' : '') + '</text>';
    });
    [1, 2, 3, 4, 5].forEach(function (k, i) {
      var y = top + row * i + row / 2, on = k === r.t, col = on ? P.tier[k - 1] : P.ink4, a = +rev[k].a, t = +rev[k].t;
      s += '<text x="0" y="' + (y + 4) + '"' + (on ? ' class="on"' : '') + '>T' + k + '</text>';
      s += '<line x1="' + X(a) + '" x2="' + X(t) + '" y1="' + y + '" y2="' + y + '" stroke="' + col + '" stroke-width="' + (on ? 2.4 : 1.5) + '"/>';
      s += '<circle cx="' + X(a) + '" cy="' + y + '" r="' + (on ? 4 : 3) + '" fill="' + col + '"/>';
      s += '<circle cx="' + X(t) + '" cy="' + y + '" r="' + (on ? 4 : 3) + '" fill="var(--surface-1)" stroke="' + col + '" stroke-width="1.6"/>';
    });
    host.innerHTML = s + '</svg>';
  }
  Sh.chip.sam = function (r) {
    var P = RBX.theme.pal();
    return RBX.icons.svg({ shape: r.pr === 0 ? 'ring' : 'dot', color: P.tier[r.t - 1], size: 11 }) + '<span>' + U.esc(L().tiers[r.t]) + '</span>';
  };
  Sh.section('sam', 'head', { order: 10, render: function (r) {
    var la = r.la && r.la.toLowerCase() !== (r.town || '').toLowerCase() ? r.la : '';
    return C.head(r.name, [r.town, r.pc, la]);
  } });
  Sh.section('sam', 'revenue', { order: 20, render: function (r) {
    var rev = RBX.config.bmrev[r.t], fq = (RBX.config.bmfreq || {})[r.t];
    return C.sec('Projected Balancing Mechanism Revenues', 'next 12 months',
      '<div class="figs two">' + C.fig('Average', rev.a, 'p/kWh', 'l') + C.fig('Top 5%', rev.t, 'p/kWh', 'l') + '</div>' +
      '<div class="ladder"></div>' + (fq ? '<div class="callchip">Offer-event frequency: <b>' + U.esc(fq) + '</b></div>' : ''));
  }, after: ladder });
  Sh.section('sam', 'capacity', { order: 30, render: function (r) {
    var P = RBX.theme.pal(), inst = r.kw || 0, on = r.kwOn, bm = r.kwBm, bar = '';
    if (on != null && bm != null && inst) {
      var rest = Math.max(0, inst - on - bm);
      bar = C.splitBar([{ v: on, cls: 'hatch' }, { v: bm, color: P.tier[r.t - 1] }, { v: rest, cls: 'hatch', color: 'var(--surface-2)' }],
        'Onsite demand ' + Math.round(on / inst * 100) + '%, available for BM ' + Math.round(bm / inst * 100) + '%' + (rest ? ', not yet split ' + Math.round(rest / inst * 100) + '%' : '')) +
        '<div class="capbar-l"><span>Onsite ' + Math.round(on / inst * 100) + '%</span>' + (rest ? '<span>Not yet split ' + Math.round(rest / inst * 100) + '%</span>' : '') + '<span>Available for BM ' + Math.round(bm / inst * 100) + '%</span></div>';
    } else bar = '<div class="note-i">' + INFO + '<span>Onsite demand is not yet split out for this site, so the capacity available for the Balancing Mechanism is unknown.</span></div>';
    return C.sec('Capacity', 'kW', '<div class="figs">' + C.fig('Installed', U.int(r.kw), 'kW') + C.fig('Onsite demand / Stranded', on == null ? null : U.int(on), 'kW') +
      C.fig('Available for BM', bm == null ? null : U.int(bm), 'kW') + '</div>' + bar);
  } });
  Sh.section('sam', 'route', { order: 40, render: function (r) {
    var cc = RBX.config.cards || {}, off;
    if (r.off === 'Generator is sole holder') off = 'Sole holder · unbundled';
    else off = r.off || 'Not identified';
    var yrs = r.comm ? Math.max(0, new Date().getFullYear() - r.comm) : null;
    var exp = r.ppa ? '<span class="expchip ' + r.ppa + '">' + U.esc(L().export[r.ppa] || 'Unknown') + '</span>' : 'Unknown';
    return C.sec('Route to market', '', '<dl class="kv"><dt>Offtaker</dt><dd>' + U.esc(off) + ' <span class="tag" tabindex="0" title="' + U.esc(cc.offtakerTip || '') + '">inferred</span></dd>' +
      '<dt>Export</dt><dd>' + exp + '</dd>' + (r.op ? '<dt>Operator</dt><dd>' + U.esc(r.op) + '</dd>' : '') +
      (r.comm ? '<dt>Commissioned</dt><dd class="num">' + r.comm + ' · ' + yrs + ' yrs</dd>' : '') + '</dl>');
  } });
  Sh.section('sam', 'nearby', { order: 60, render: function (r) { return C.nearby(r, 'Nearby'); } });
  Sh.action('sam', 'talk', C.actTalk); Sh.action('sam', 'zoom', C.actZoom); Sh.action('sam', 'link', C.actLink); Sh.action('sam', 'register', C.actRegister);

  // ------------------------------------------------------------------ TAM
  Sh.chip.tam = function (r) {
    return '<span class="fuelchip">' + RBX.icons.forRow(r, 12) + U.esc(r.fuel) + ' · ' + (r.ro ? 'RO' : 'FiT') + '</span>';
  };
  Sh.section('tam', 'head', { order: 10, render: function (r) {
    var h = C.head(r.name, [r.fuel, r.ro]);
    if (r.samRow) h += '<button type="button" class="banner" data-act="open-sam"><span><b>Also verified in SAM</b> · open peaker profile</span><span class="go">›</span></button>';
    return h;
  } });
  Sh.section('tam', 'facts', { order: 20, render: function (r) {
    var L2 = L(), cap = r.kw == null ? '—' : U.int(r.kw) + (r.kw >= 10000 ? '<small>kW (' + U.num(r.kw / 1000, 1) + ' MW)</small>' : '<small>kW</small>');
    var body = '<div class="figs two"><div class="fig"><div class="fig-l">Capacity</div><div class="fig-v">' + cap + '</div></div>' +
      C.fig('Available for BM', r.bm == null ? null : U.int(r.bm), 'kW') + '</div><dl class="kv" style="margin-top:12px">' +
      '<dt>BM tier</dt><dd>' + (r.bt ? U.esc(L2.tiers[r.bt]) + ' <i>(indicative)</i>' : U.esc(L2.tiers[0])) + '</dd>' +
      '<dt>Subsidy</dt><dd>' + (r.ro ? 'RO accredited' : 'FiT accredited') + '</dd>' +
      (r.ro ? '<dt>RO reference</dt><dd class="mono">' + U.esc(r.ro) + '</dd>' : '') +
      (r.units > 1 ? '<dt>Metering</dt><dd>Site aggregates ' + U.int(r.units) + ' MPAN records</dd>' : '') + '</dl>' +
      '<p class="sr-only">BM tier: ' + U.esc(r.bt ? L2.tiers[r.bt] + ' (indicative)' : L2.tiers[0]) + '. Subsidy: ' + (r.ro ? 'RO accredited' : 'FiT accredited') + '.</p>' +
      (r.ap ? '<div class="note-i">' + RBX.icons.svg({ shape: 'ring', color: 'currentColor', dashed: true, size: 14 }) + '<span>Approximate location (postcode district)</span></div>' : '');
    return C.sec('Capacity & subsidy', '', body);
  } });
  Sh.section('tam', 'nearby', { order: 60, render: function (r) { return C.nearby(r, 'Nearby'); } });
  Sh.action('tam', 'zoom', C.actZoom); Sh.action('tam', 'link', C.actLink);

  // ------------------------------------------------------------------ Hydro
  Sh.chip.hydro = function (r) {
    var P = RBX.theme.pal();
    return (r.c === 3 ? RBX.icons.svg({ shape: 'ring', color: P.unv, size: 11 }) : RBX.icons.svg({ shape: 'dot', color: P.hyd[r.c], size: 11 })) +
      '<span>' + U.esc(r.c === 3 ? 'Unverified' : r.conf + ' confidence') + '</span>';
  };
  Sh.section('hydro', 'head', { order: 10, render: function (r) {
    return C.head(r.name, ['Stranded hydro', U.num(Math.abs(r.lat), 2) + '° ' + (r.lat >= 0 ? 'N' : 'S') + ', ' + U.num(Math.abs(r.lon), 2) + '° ' + (r.lon < 0 ? 'W' : 'E')]);
  } });
  Sh.section('hydro', 'stranded', { order: 20, render: function (r) {
    var P = RBX.theme.pal(), cc = RBX.config.cards || {}, col = r.c === 3 ? P.unv : P.hyd[r.c];
    var tot = r.inst || ((r.kw || 0) + (r.mec || 0)) || 1, pe = (r.mec || 0) / tot * 100, ps = (r.kw || 0) / tot * 100;
    var h = '<div class="hero" style="color:' + col + '">' + U.int(r.kw) + '<small>kW stranded</small></div>';
    if (r.exp === 'No export') h += '<div style="margin-top:10px"><span class="badge">No export</span></div>';
    else h += '<div class="figs two" style="margin-top:14px">' + C.fig('Installed capacity', U.int(r.inst), 'kW') + C.fig('Export capacity', U.int(r.mec), 'kW') + '</div>';
    h += C.splitBar([{ v: pe, cls: 'hatch' }, { v: ps, color: col }], 'Export ' + Math.round(pe) + '%, stranded ' + Math.round(ps) + '%') +
      '<div class="capbar-l"><span>Can export ' + Math.round(pe) + '%</span><span>' + Math.round(ps) + '% stranded</span></div>' +
      '<div class="note-i">' + INFO + '<span>' + U.esc(r.exp === 'No export' ? (cc.hydroNoExport || '') : (cc.hydroExplain || '')) + '</span></div>';
    return C.sec('Stranded capacity', '', h);
  } });
  Sh.section('hydro', 'nearby', { order: 60, render: function (r) { return C.nearby(r, 'Nearby'); } });
  Sh.action('hydro', 'talk', C.actTalk); Sh.action('hydro', 'zoom', C.actZoom); Sh.action('hydro', 'link', C.actLink);
})();
