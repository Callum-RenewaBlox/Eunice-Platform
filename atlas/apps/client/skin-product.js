/* Client skin "product" (Direction B, premium product UI): full-bleed map with floating glass chrome.
   Client-only: listed in apps/client/manifest.json after the core modules and before core/js/app.js.
   Every change here is a wrapper or a registered hook around the core modules; nothing in core/ is edited,
   and the whole file is inert unless <html data-skin="product"> (set by apps/client/template.html). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, doc = document.documentElement;
  if (doc.getAttribute('data-skin') !== 'product') return;
  var SK = RBX.skin = { name: 'product' };

  // ------------------------------------------------------------------ basemap: the kit's own light / dark palettes
  // The skin keeps the theme ids ("paper" / "night") so hash, storage and the wrapper stay compatible.
  var BM = window.RBXBasemap;
  if (BM && BM.palettes && BM.palettes.light && BM.palettes.dark) {
    BM.palettes.paper = Object.assign({}, BM.palettes.light, { name: 'paper' });
    BM.palettes.night = Object.assign({}, BM.palettes.dark, { name: 'night' });
  }

  var ICON = {
    peaker: '<svg class="i mi" viewBox="0 0 16 16" aria-hidden="true"><path class="f" d="M9.2 1.5 3.5 9h4l-1 5.5L12.5 7h-4z"/></svg>',
    hydro: '<svg class="i mi" viewBox="0 0 16 16" aria-hidden="true"><path class="f" d="M8 1.8C8 1.8 3.4 7 3.4 10a4.6 4.6 0 0 0 9.2 0C12.6 7 8 1.8 8 1.8z"/></svg>',
    ppa: '<svg class="i mi" viewBox="0 0 16 16" aria-hidden="true"><path d="M2 13.5h12M3.5 11l3-4 2.5 2 3.5-5.5"/></svg>',
    moon: '<svg class="i i-moon" viewBox="0 0 16 16" aria-hidden="true"><path d="M13.2 9.6A5.6 5.6 0 0 1 6.4 2.8a5.6 5.6 0 1 0 6.8 6.8z"/></svg>',
    sun: '<svg class="i i-sun" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3"/><path d="M8 1.2v1.6M8 13.2v1.6M1.2 8h1.6M13.2 8h1.6M3.2 3.2l1.1 1.1M11.7 11.7l1.1 1.1M3.2 12.8l1.1-1.1M11.7 4.3l1.1-1.1"/></svg>',
    search: '<svg class="i" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.6"/><path d="m10.6 10.6 3.2 3.2"/></svg>',
    trend: '<svg class="i" viewBox="0 0 16 16" aria-hidden="true"><path d="M1.8 11.5 6 7.3l2.6 2.6 5.6-5.6"/><path d="M10.4 4.3h3.8v3.8"/></svg>'
  };
  // brand mark: a lime spark line on the deep-green tile
  var MARK = '<svg class="mark mark-b" viewBox="0 0 32 32" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="9" fill="#0E3A2F"/>' +
    '<path d="M9 21.5 L13.4 16.2 L16.6 19 L23 10.5" fill="none" stroke="#8FD14F" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<circle cx="23" cy="10.5" r="2.3" fill="#8FD14F"/></svg>';
  var lastScope = null;
  var MODE_LABEL = { peaker: 'Peaker', hydro: 'Hydro', ppa: 'PPA<em> Benchmark</em>' };
  var isMac = /Mac|iPhone|iPad/i.test((navigator.platform || '') + ' ' + (navigator.userAgent || ''));

  // ------------------------------------------------------------------ header: brand pill + mode switch, search pill
  function place(thumb, btn) {
    if (!thumb) return;
    if (!btn || !btn.offsetWidth) { thumb.style.opacity = '0'; return; }
    thumb.style.opacity = '1';
    thumb.style.width = btn.offsetWidth + 'px';
    thumb.style.transform = 'translateX(' + btn.offsetLeft + 'px)';
  }
  SK.syncModes = function () {
    var tabs = document.querySelector('#hdr .tabs'); if (!tabs) return;
    var v = RBX.state.view, id = v === 'sam' || v === 'tam' ? 'peaker' : v;
    place(tabs.querySelector('.seg-thumb'), tabs.querySelector('[data-tab="' + id + '"]'));
  };
  /** Bottom of the floating header, in px from the top of the page (drives the panel, fit padding and PPA offset). */
  SK.headerBottom = function () {
    var p = document.querySelector('#hdr .hdr-pill');
    return p ? Math.round(p.getBoundingClientRect().bottom) : 0;
  };
  function syncHeaderVar() {
    var b = SK.headerBottom();
    if (b > 0) doc.style.setProperty('--hdr-b', b + 'px');
  }
  function decorateHeader() {
    var cfg = RBX.config, el = document.getElementById('hdr'); if (!el) return;
    var brand = el.querySelector('.hdr-brand'), nav = el.querySelector('.hdr-nav');
    if (brand) {
      brand.innerHTML = MARK + '<div class="brand-txt"><h1 class="brand">RenewaBlox <span>' + U.esc(cfg.productLabel || 'Client Atlas') + '</span></h1>' +
        '<p class="brand-tag"><span class="brand-dot" aria-hidden="true"></span>no Watt wasted</p></div>';
    }
    if (brand && nav && !el.querySelector('.hdr-pill')) {
      var pill = document.createElement('div');
      pill.className = 'hdr-pill';
      el.insertBefore(pill, brand);
      pill.appendChild(brand);
      var sep = document.createElement('span'); sep.className = 'vsep'; sep.setAttribute('aria-hidden', 'true');
      pill.appendChild(sep);
      pill.appendChild(nav);
    }
    U.$$('.tab', el).forEach(function (b) {
      var id = b.getAttribute('data-tab'), long = b.querySelector('.t-long');
      if (!MODE_LABEL[id] || b.querySelector('.t-b')) return;
      if (long) b.title = long.textContent;
      b.insertAdjacentHTML('afterbegin', ICON[id] || '');
      b.insertAdjacentHTML('beforeend', '<span class="t-b" aria-hidden="true">' + MODE_LABEL[id] + '</span>');
    });
    var tabs = el.querySelector('.tabs');
    if (tabs && !tabs.querySelector('.seg-thumb')) tabs.insertAdjacentHTML('afterbegin', '<span class="seg-thumb" aria-hidden="true"></span>');
    var srch = el.querySelector('#hdrSearch');
    if (srch) {
      var ic = srch.querySelector('svg'); if (ic) ic.outerHTML = ICON.search;
      var k = srch.querySelector('.kbd'); if (k) k.textContent = isMac ? '⌘K' : 'Ctrl K';
      srch.setAttribute('aria-label', 'Search sites (' + (isMac ? '⌘K' : 'Ctrl K') + ' or /)');
    }
    var tb = el.querySelector('#themeBtn');
    if (tb) { tb.innerHTML = ICON.moon + ICON.sun; tb.setAttribute('aria-label', 'Dark theme'); tb.title = 'Dark theme (T)'; }
    syncHeaderVar();
    requestAnimationFrame(function () { SK.syncModes(); syncHeaderVar(); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { SK.syncModes(); syncHeaderVar(); });
  }
  var hdRender = RBX.header.render;
  RBX.header.render = function () {
    hdRender.apply(this, arguments);
    decorateHeader();
  };
  window.addEventListener('resize', U.rafThrottle(function () { SK.syncModes(); SK.syncScope(); syncHeaderVar(); }));
  RBX.bus.on('view', function (e) {
    requestAnimationFrame(SK.syncModes);
    if (e && e.view !== 'sam' && e.view !== 'tam') lastScope = null;
  });

  // ------------------------------------------------------------------ panel: label, SAM/TAM switch, one-line description
  function viewCfg(v) { return ((RBX.config || {}).views || {})[v] || {}; }
  function head(view) {
    var vc = viewCfg(view), h = '<p class="p-label">' + U.esc(vc.label || '') + '</p>';
    if (view === 'sam' || view === 'tam') {
      var sc = RBX.config.scope || {}, from = lastScope || view;
      var opt = function (id, name, n, title) {
        var on = id === view;
        return '<button type="button" role="radio" data-pscope="' + id + '" aria-checked="' + on + '" tabindex="' + (on ? 0 : -1) + '" aria-label="' + U.esc(sc[id]) + '" title="' + U.esc(title) + '">' +
          '<b>' + name + '</b><span class="n num">' + U.esc(n) + '</span></button>';
      };
      h += '<div class="p-scope" id="pScope" role="radiogroup" aria-label="Peaker market scope" data-on="' + from + '"><span class="seg-thumb" aria-hidden="true"></span>' +
        opt('sam', 'SAM', sc.samN, 'Serviceable market') + opt('tam', 'TAM', sc.tamN, 'Total addressable market') + '</div>';
    }
    if (vc.summary) h += '<p class="p-desc">' + U.esc(vc.summary) + '</p>';
    return h;
  }
  SK.syncScope = function () {
    var sc = document.getElementById('pScope'); if (!sc) return;
    var v = RBX.state.view;
    if (v !== 'sam' && v !== 'tam') return;
    sc.setAttribute('data-on', v);
    lastScope = v;
  };
  RBX.hooks.railBefore = RBX.hooks.railBefore || {};
  ['sam', 'tam', 'hydro'].forEach(function (v) { RBX.hooks.railBefore[v] = function () { return head(v); }; });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-pscope]'); if (!b) return;
    RBX.app.setView(b.getAttribute('data-pscope'));
    var nb = document.querySelector('[data-pscope="' + b.getAttribute('data-pscope') + '"]'); if (nb) nb.focus({ preventScroll: true });
  });
  document.addEventListener('keydown', function (e) {
    var b = e.target.closest && e.target.closest('[data-pscope]'); if (!b) return;
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].indexOf(e.key) < 0) return;
    e.preventDefault();
    var next = RBX.state.view === 'sam' ? 'tam' : 'sam';
    RBX.app.setView(next);
    var nb = document.querySelector('[data-pscope="' + next + '"]'); if (nb) nb.focus({ preventScroll: true });
  });

  // ------------------------------------------------------------------ KPI card: hero figure with the "In view" switch, two tiles, universe line
  var kpiHtml = RBX.kpi.html;
  RBX.kpi.html = function (view) {
    var h = kpiHtml.apply(this, arguments); if (!h) return h;
    var t = document.createElement('template'); t.innerHTML = h;
    var f = t.content, grid = f.querySelector('.kpis'), uni = f.querySelector('.universe'), sw = f.querySelector('#ivSw');
    var hero = grid && grid.querySelector('.kpi');
    if (hero) {
      hero.classList.add('kpi-hero');
      var top = document.createElement('div'); top.className = 'kpi-top';
      var lab = hero.querySelector('.kpi-l'); hero.insertBefore(top, lab); top.appendChild(lab);
      if (sw) top.appendChild(sw);
    }
    if (uni) {
      uni.insertAdjacentHTML('afterbegin', '<span class="u-dot" aria-hidden="true"></span>');
      grid.appendChild(uni);
    }
    var card = document.createElement('div'); card.className = 'kcard';
    f.insertBefore(card, grid); card.appendChild(grid);
    return t.innerHTML;
  };

  // ------------------------------------------------------------------ capacity: histogram always open, a 1 MW tick on the axis
  var histHtml = RBX.hist.html;
  RBX.hist.html = function (view) {
    var h = histHtml.apply(this, arguments);
    var t = document.createElement('template'); t.innerHTML = h;
    var f = t.content, hist = f.querySelector('#hist'), tog = f.querySelector('#histToggle');
    if (hist) hist.removeAttribute('hidden');
    if (tog) { tog.setAttribute('aria-expanded', 'true'); tog.hidden = true; }
    var vals = (RBX.data.rows[view] || []).map(RBX.filters.capOf).filter(function (v) { return v > 0; });
    var ends = f.querySelector('.hist-ends');
    if (ends && vals.length) {
      var lo = Math.log10(Math.min.apply(null, vals)), hi = Math.log10(Math.max.apply(null, vals)), p = (3 - lo) / (hi - lo);
      if (p > 0.18 && p < 0.82) ends.insertAdjacentHTML('beforeend', '<span class="mid" style="left:' + (p * 100).toFixed(1) + '%">1 MW</span>');
    }
    return t.innerHTML;
  };

  // ------------------------------------------------------------------ legend: tier names and revenue figures emphasised (text unchanged)
  var lgHtml = RBX.legend.html;
  RBX.legend.html = function () {
    var h = lgHtml.apply(this, arguments);
    h = h.replace(/(<span class="lg-lbl">)(Tier \d) · ([^<]+)/g, '$1<b class="lg-k">$2</b> <span class="lg-q">· $3</span>');
    return h.replace(/(<span class="lg-sec rev">)([^<]+)(<\/span>)/g, function (m, a, txt, c) {
      return a + txt.replace(/(\d+(?:\.\d+)?p)/g, '<b>$1</b>') + c;
    });
  };

  // after every panel render: slide the SAM/TAM thumb from the previous scope
  var railRender = RBX.rail.render;
  RBX.rail.render = function () {
    railRender.apply(this, arguments);
    requestAnimationFrame(SK.syncScope);
    setTimeout(SK.syncScope, 80);   // backstop when frames are throttled (background tab, busy main thread)
  };

  // ------------------------------------------------------------------ detail sheet: mini-report cards
  var Sh = RBX.sheet, C = RBX.cards;
  function L() { return RBX.config.labels; }
  function find(kind, id) { return (Sh.sections[kind] || []).filter(function (s) { return s.id === id; })[0]; }
  function meter(t, col) {
    var s = '';
    for (var k = 5; k >= 1; k--) s += '<i' + (k === t ? ' class="on"' : '') + ' style="background:' + col(k) + '"></i>';
    return '<div class="meter" aria-hidden="true">' + s + '</div><div class="meter-l" aria-hidden="true"><span>Tier 5 · lower</span><span>Tier 1 · highest</span></div>';
  }
  /** Badge text colour with the better contrast on a hex fill. */
  function onFill(hex) {
    var n = parseInt(String(hex).replace('#', ''), 16);
    if (isNaN(n)) return '#FFFFFF';
    var c = [n >> 16, (n >> 8) & 255, n & 255].map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] > 0.2 ? '#1B1206' : '#FFFFFF';
  }
  function tierRow(t, sub) {
    var P = RBX.theme.pal(), col = P.tier[t - 1];
    return '<div class="tier-row"><span class="tier-badge num" style="background:' + col + ';color:' + onFill(col) + '" aria-hidden="true">' + t + '</span>' +
      '<div class="tier-name">' + U.esc(L().tiers[t]) + '<small>' + U.esc(sub) + '</small></div></div>' +
      meter(t, function (k) { return P.tier[k - 1]; });
  }
  function inject(html, after) {
    var t = document.createElement('template'); t.innerHTML = html;
    var hh = t.content.querySelector('.sh-sec-h');
    if (hh) hh.insertAdjacentHTML('afterend', after);
    return t.innerHTML;
  }
  function kvs(rows) {
    return '<dl class="kvs">' + rows.map(function (r) {
      return '<dt>' + (r.sw ? '<i class="' + (r.swCls || '') + '"' + (r.sw !== true ? ' style="background:' + r.sw + '"' : '') + '></i>' : '') + U.esc(r.k) + '</dt>' +
        '<dd class="num' + (r.v == null ? ' unk' : '') + '">' + (r.v == null ? 'Unknown' : r.v) + '</dd>';
    }).join('') + '</dl>';
  }
  function pct(a, b) { return b ? ' <small>' + Math.round(a / b * 100) + '%</small>' : ''; }

  // SAM: chip names the layer (the tier gets its own badge), capacity first, BM card with badge + meter
  Sh.chip.sam = function (r) {
    return RBX.icons.svg({ shape: r.pr === 0 ? 'ring' : 'dot', color: RBX.theme.pal().tier[r.t - 1], size: 10 }) + '<span>Verified AD · SAM</span>';
  };
  Sh.section('sam', 'capacity', { order: 15, render: function (r) {
    var P = RBX.theme.pal(), inst = r.kw || 0, on = r.kwOn, bm = r.kwBm, col = P.tier[r.t - 1], bar = '', note = '';
    if (on != null && bm != null && inst) {
      var rest = Math.max(0, inst - on - bm);
      bar = C.splitBar([{ v: on, cls: 'seg-on' }, { v: bm, color: col }, { v: rest, cls: 'hatch' }],
        'Onsite demand ' + Math.round(on / inst * 100) + '%, available for BM ' + Math.round(bm / inst * 100) + '%' + (rest ? ', not yet split ' + Math.round(rest / inst * 100) + '%' : ''));
    } else note = '<div class="note-i">' + C.INFO + '<span>Onsite demand is not yet split out for this site, so the capacity available for the Balancing Mechanism is unknown.</span></div>';
    var rows = [{ k: 'Installed', v: U.int(inst) + ' kW' },
      { k: 'Onsite demand / Stranded', sw: true, swCls: 'sw-on', v: on == null ? null : U.int(on) + ' kW' + pct(on, inst) },
      { k: 'Available for BM', sw: col, v: bm == null ? null : U.int(bm) + ' kW' + pct(bm, inst) }];
    if (on != null && bm != null && inst && inst - on - bm > 0) rows.push({ k: 'Not yet split', sw: true, swCls: 'hatch', v: U.int(inst - on - bm) + ' kW' });
    return C.sec('Capacity', 'kW', '<div class="big"><b class="num">' + U.int(inst) + '</b><small>kW installed</small></div>' + bar + kvs(rows) + note);
  } });
  var samRev = find('sam', 'revenue');
  if (samRev) {
    Sh.section('sam', 'revenue', { order: 20, after: samRev.after, render: function (r) {
      return inject(samRev.render(r), tierRow(r.t, 'Location tier for BM offer revenue'));
    } });
  }

  // TAM: capacity card and a BM tier & subsidy card (every v1 field kept)
  Sh.section('tam', 'facts', { order: 20, render: function (r) {
    var L2 = L(), P = RBX.theme.pal(), col = RBX.theme.tamColour(r, P), kw = r.kw, bm = r.bm, cap;
    cap = kw == null ? '—' : U.int(kw);
    var bar = kw && bm != null ? C.splitBar([{ v: bm, color: col }, { v: Math.max(0, kw - bm), cls: 'seg-on' }], 'Available for BM ' + Math.round(bm / kw * 100) + '% of capacity') : '';
    var h = C.sec('Capacity', 'kW', '<div class="big"><b class="num">' + cap + '</b><small>kW' + (kw >= 10000 ? ' (' + U.num(kw / 1000, 1) + ' MW)' : '') + '</small></div>' + bar +
      kvs([{ k: 'Capacity', v: kw == null ? null : U.int(kw) + ' kW' }, { k: 'Available for BM', sw: col, v: bm == null ? null : U.int(bm) + ' kW' + pct(bm, kw) }]));
    var tier = r.bt ? tierRow(r.bt, 'Indicative location tier') : '<div class="tier-row"><span class="tier-badge tier-none" aria-hidden="true">–</span><div class="tier-name">' + U.esc(L2.tiers[0]) + '<small>Outside the BM tier model</small></div></div>';
    var body = tier + '<dl class="kv" style="margin-top:12px">' +
      '<dt>BM tier</dt><dd>' + (r.bt ? U.esc(L2.tiers[r.bt]) + ' <i>(indicative)</i>' : U.esc(L2.tiers[0])) + '</dd>' +
      '<dt>Subsidy</dt><dd>' + (r.ro ? 'RO accredited' : 'FiT accredited') + '</dd>' +
      (r.ro ? '<dt>RO reference</dt><dd class="mono">' + U.esc(r.ro) + '</dd>' : '') +
      (r.units > 1 ? '<dt>Metering</dt><dd>Site aggregates ' + U.int(r.units) + ' MPAN records</dd>' : '') + '</dl>' +
      '<p class="sr-only">BM tier: ' + U.esc(r.bt ? L2.tiers[r.bt] + ' (indicative)' : L2.tiers[0]) + '. Subsidy: ' + (r.ro ? 'RO accredited' : 'FiT accredited') + '.</p>' +
      (r.ap ? '<div class="note-i approx">' + RBX.icons.svg({ shape: 'ring', color: 'currentColor', dashed: true, size: 14 }) + '<span>Approximate location (postcode district)</span></div>' : '');
    return h + C.sec('BM tier & subsidy', r.bt ? 'indicative' : '', body);
  } });

  // ------------------------------------------------------------------ map: fit padding, obstruction and fly offset clear the floating header
  var M = RBX.mapctl;
  var obs0 = M.obstruction, fit0 = M.fitPadding, off0 = M.offset;
  function topBlock() {
    var area = document.getElementById('mapArea'); if (!area) return 0;
    return Math.max(0, SK.headerBottom() - area.getBoundingClientRect().top);
  }
  M.obstruction = function () {
    var o = obs0.apply(this, arguments);
    // the sheet slides in with a transform: measure its layout box, not its (moving) painted box
    var sh = document.getElementById('sheet'), area = document.getElementById('mapArea');
    if (sh && area && !sh.hidden && sh.offsetParent === area) {
      if (U.isMobile()) o.bottom = Math.max(0, area.clientHeight - sh.offsetTop);
      else o.right = Math.max(0, area.clientWidth - sh.offsetLeft);
    }
    o.top = Math.max(o.top || 0, topBlock());
    return o;
  };
  M.fitPadding = function () {
    var p = fit0.apply(this, arguments), tb = topBlock();
    if (tb) p.top = Math.max(p.top, tb + (U.isMobile() ? 14 : 20));
    return p;
  };
  M.offset = function () {
    var o = off0.apply(this, arguments), ob = M.obstruction();
    o[1] = Math.round(((ob.top || 0) - (ob.bottom || 0)) / 2);
    return o;
  };

  // soft drop shadow under the SAM and Hydro dots; flat markers (no night glow) in both themes
  function shadowColour() { return RBX.state.theme === 'night' ? 'rgba(0,0,0,0.55)' : 'rgba(9,24,19,0.28)'; }
  SK.syncShadows = function () {
    var m = RBX.map; if (!m || !RBX.layers.ready) return;
    ['sam', 'hydro'].forEach(function (k) {
      var id = k + '-shadow'; if (!m.getLayer(id)) return;
      try {
        m.setLayoutProperty(id, 'visibility', RBX.state.view === k ? 'visible' : 'none');
        m.setFilter(id, RBX.filters.expr(k));
        m.setPaintProperty(id, 'circle-color', shadowColour());
      } catch (e) { /* style rebuilt */ }
    });
  };
  RBX.bus.on('mapready', function (map) {
    var Ly = RBX.layers;
    ['sam', 'hydro'].forEach(function (k) {
      try {
        if (!map.getLayer(k + '-shadow') && map.getLayer(k + '-core')) {
          map.addLayer({ id: k + '-shadow', type: 'circle', source: k, layout: { visibility: 'none' }, paint: {
            'circle-radius': Ly.R(Ly.SIZE[k], 1.4), 'circle-color': shadowColour(), 'circle-blur': 0.85, 'circle-translate': [0, 1.6] } }, k + '-ghost');
        }
        ['-glow', '-hot'].forEach(function (s) { if (map.getLayer(k + s)) map.setPaintProperty(k + s, 'circle-opacity', 0); });
      } catch (e) { /* the map keeps working without the shadows */ }
    });
    SK.syncShadows();
    SK.notesOff(map);
  });
  RBX.bus.on('view', function () { SK.syncShadows(); });
  RBX.bus.on('filter', function (p) { if (!(p && p.light)) SK.syncShadows(); else requestAnimationFrame(SK.syncShadows); });
  RBX.bus.on('theme', function () { setTimeout(SK.syncShadows, 0); });

  // ------------------------------------------------------------------ map annotations: kept, but off by default in this skin
  SK.notesOff = function () {
    var N = RBX.notes; if (!N) return;
    var key = ((RBX.config && RBX.config.storageKey) || 'rbx-atlas') + ':notes';
    if (U.store(key) == null) {
      N.on = false;
      var b = document.getElementById('notesBtn'); if (b) b.setAttribute('aria-pressed', 'false');
    }
    var nb = document.getElementById('notesBtn'), ctl = document.getElementById('mapCtl');
    if (nb && ctl && nb.parentNode !== ctl) { nb.classList.add('ctl'); ctl.appendChild(nb); }
  };

  // TAM legend: technology first (family quick-filters, then the per-fuel rows), then subsidy, location, BM tier
  RBX.hooks.legendGroups = RBX.hooks.legendGroups || {};
  if (!RBX.hooks.legendGroups.tam) {
    RBX.hooks.legendGroups.tam = function () {
      var sp = RBX.legend.defaults.tam(), rank = { famChips: 0, rows: 1, chips: 2, stack: 3 };
      sp.groups = sp.groups.map(function (g, i) { return { g: g, i: i }; })
        .sort(function (a, b) { return (rank[a.g.type] - rank[b.g.type]) || (a.i - b.i); }).map(function (x) { return x.g; });
      return sp;
    };
  }

  // ------------------------------------------------------------------ small touches
  // the sheet knows which layer it shows (styling hook: no place pin on TAM metadata)
  RBX.bus.on('select', function (row) {
    var el = document.getElementById('sheet'); if (!el) return;
    if (row && row.kind) el.setAttribute('data-kind', row.kind); else el.removeAttribute('data-kind');
    // narrow desktops: fold the attribution to its (i) button while a card takes the right-hand side
    if (row && window.innerWidth <= 1180) {
      var at = document.querySelector('.maplibregl-ctrl-attrib.maplibregl-compact');
      if (at) at.classList.remove('maplibregl-compact-show');
    }
  });
  ['chooser', 'panel'].forEach(function (fn) {
    var f0 = Sh[fn];
    Sh[fn] = function () { var el = document.getElementById('sheet'); if (el) el.removeAttribute('data-kind'); return f0.apply(this, arguments); };
  });
  // short offline pill (B wording); the longer explanation stays as its tooltip
  (function () {
    var p = document.getElementById('offlinePill');
    if (p) { p.title = p.textContent; p.textContent = 'Offline basemap'; }
  })();
  RBX.bus.on('ready', function () { syncHeaderVar(); SK.syncModes(); });
  SK.icons = ICON;
})();
