/* RBX.modal + client P1 dialogs (spec 11 P1 #11, #12): a generic centred modal (focus trap, Esc, focus return),
   the "?" keyboard-shortcuts dialog, the "About this map" popover and the accessible Sites list (a sortable
   <table> of the sites currently shown, row → open the site). Menu entries are added to RBX.header.menu. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var M = RBX.modal = {};
  var el = null, last = null, onClose = null;
  var X = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15"/></svg>';

  function host() {
    if (el) return el;
    el = document.createElement('div');
    el.id = 'modal'; el.className = 'modal'; el.hidden = true;
    el.innerHTML = '<div class="modal-scrim" data-mclose="1"></div><section class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modalTitle"></section>';
    document.body.appendChild(el);
    el.addEventListener('click', function (e) { if (e.target.closest('[data-mclose]')) M.close(); });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); M.close(); return; }
      if (e.key !== 'Tab') return;
      var f = U.$$('button:not([disabled]),a[href],input,select,[tabindex]:not([tabindex="-1"])', el.querySelector('.modal-box')).filter(function (x) { return x.offsetParent !== null; });
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { f[f.length - 1].focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { f[0].focus(); e.preventDefault(); }
    });
    return el;
  }
  /** Open a modal: {title, html, cls?, sub?, onOpen(box)?, onClose()?}. */
  M.open = function (o) {
    var h = host(), box = h.querySelector('.modal-box');
    if (!h.hidden) M.close(true);
    last = document.activeElement;
    onClose = o.onClose || null;
    box.className = 'modal-box' + (o.cls ? ' ' + o.cls : '');
    box.innerHTML = '<div class="modal-top"><div><h2 class="modal-title" id="modalTitle">' + U.esc(o.title) + '</h2>' + (o.sub ? '<p class="modal-sub">' + o.sub + '</p>' : '') + '</div>' +
      '<button type="button" class="sh-x" data-mclose="1" aria-label="Close (Esc)">' + X + '</button></div><div class="modal-body">' + o.html + '</div>';
    h.hidden = false;
    if (o.onOpen) o.onOpen(box);
    var f = box.querySelector('[autofocus]') || box.querySelector('[data-mclose]');
    if (f) f.focus();
  };
  M.close = function (silent) {
    if (!el || el.hidden) return false;
    el.hidden = true;
    el.querySelector('.modal-box').innerHTML = '';
    var cb = onClose; onClose = null;
    if (cb) cb();
    if (!silent && last && last.focus && document.body.contains(last)) last.focus();
    return true;
  };
  M.isOpen = function () { return !!el && !el.hidden; };

  // ------------------------------------------------------------------ keyboard shortcuts ("?")
  var KEYS = [
    [['/'], 'Search sites, towns, postcodes'], [['⌘', 'K'], 'Search (also Ctrl-K)'], [['1'], 'TAB:peaker'], [['2'], 'TAB:hydro'], [['3'], 'TAB:ppa'],
    [['S'], 'Switch TAM ↔ SAM (Peaker)'], [['T'], 'Paper / Night theme'], [['R'], 'Reset the map view'], [['L'], 'Collapse or expand the panel'],
    [['J'], 'Next site in the card'], [['K'], 'Previous site in the card'], [['←', '→'], 'Previous / next site (focus in the card)'],
    [['Esc'], 'Close search, card, drawer or dialog'], [['?'], 'This list']
  ];
  M.shortcuts = function () {
    // view keys are named after this build's tabs (e.g. "Peaker plants" in the investor build)
    var tabs = {};
    (RBX.config.tabs || []).forEach(function (t) { tabs[t.id] = String(t.label || '').replace(/\s*·\s*[\d,]+$/, ''); });
    var dflt = { peaker: 'Peaker Model', hydro: 'Hydro', ppa: 'PPA Benchmark' };
    var rows = KEYS.map(function (r) { var m = /^TAB:(\w+)$/.exec(r[1]); return m ? [r[0], tabs[m[1]] || dflt[m[1]]] : r; });
    if (RBX.present && RBX.present.enter) {
      rows.splice(rows.length - 1, 0, [['P'], 'Present'], [['←', '→'], 'Previous / next chapter (while presenting)'],
        [['Space'], 'Next chapter (while presenting)']);
    }
    M.open({ title: 'Keyboard shortcuts', cls: 'modal-sm', sub: 'Shortcuts are ignored while you type in a field. When the map has focus, arrow keys pan and + / − zoom.',
      html: '<table class="keys"><tbody>' + rows.map(function (r) {
        return '<tr><th scope="row">' + r[0].map(function (k) { return '<span class="kbd">' + U.esc(k) + '</span>'; }).join(' ') + '</th><td>' + U.esc(r[1]) + '</td></tr>';
      }).join('') + '</tbody></table>' });
  };

  // ------------------------------------------------------------------ About this map
  M.about = function () {
    var a = RBX.config.about || {};
    M.open({ title: a.title || 'About this map', cls: 'modal-sm',
      html: (a.body || []).map(function (p) { return '<p>' + U.esc(p) + '</p>'; }).join('') +
        '<div class="modal-acts"><button type="button" class="btn" data-go="sources">' + RBX.header.ICON.book + 'Sources &amp; method</button>' +
        (RBX.config.contactEmail ? '<a class="btn btn-primary" href="mailto:' + U.esc(String(RBX.config.contactEmail).replace(/[^A-Za-z0-9@._+-]/g, '')) + '" target="_blank" rel="noopener">Contact ' + U.esc(RBX.config.contactEmail) + '</a>' : '') +
        '</div><p class="modal-foot">' + U.esc((RBX.config.drawer || {}).asOf || '') + '</p>',
      onOpen: function (box) { box.querySelector('[data-go="sources"]').addEventListener('click', function () { M.close(true); RBX.drawer.open(); }); } });
  };

  // ------------------------------------------------------------------ accessible Sites list
  var COLS = {
    sam: [
      { k: 'ref', l: 'Ref', n: 1, v: function (r) { return r.ref; } },
      { k: 'name', l: 'Site', v: function (r) { return r.name; } },
      { k: 'town', l: 'Town', v: function (r) { return r.town || ''; } },
      { k: 't', l: 'BM tier', v: function (r) { return r.t; }, f: function (r) { return RBX.config.labels.tiers[r.t]; } },
      { k: 'kw', l: 'Installed kW', n: 1, v: function (r) { return r.kw; }, f: function (r) { return U.int(r.kw); } },
      { k: 'bm', l: 'Available for BM kW', n: 1, v: function (r) { return r.kwBm == null ? -1 : r.kwBm; }, f: function (r) { return r.kwBm == null ? '—' : U.int(r.kwBm); } }
    ],
    tam: [
      { k: 'name', l: 'Site', v: function (r) { return r.name; } },
      { k: 'fuel', l: 'Fuel', v: function (r) { return r.fuel; } },
      { k: 'sub', l: 'Subsidy', v: function (r) { return r.ro ? 'RO' : 'FiT'; } },
      { k: 'bt', l: 'BM tier (indicative)', v: function (r) { return r.bt || 9; }, f: function (r) { return r.bt ? 'Tier ' + r.bt : 'Scotland'; } },
      { k: 'kw', l: 'Capacity kW', n: 1, v: function (r) { return r.kw || 0; }, f: function (r) { return U.int(r.kw); } }
    ],
    hydro: [
      { k: 'name', l: 'Site', v: function (r) { return r.name; } },
      { k: 'c', l: 'Confidence', v: function (r) { return r.c; }, f: function (r) { return r.c === 3 ? 'Unverified' : r.conf; } },
      { k: 'kw', l: 'Stranded kW', n: 1, v: function (r) { return r.kw; }, f: function (r) { return U.int(r.kw); } },
      { k: 'inst', l: 'Installed kW', n: 1, v: function (r) { return r.inst; }, f: function (r) { return U.int(r.inst); } },
      { k: 'mec', l: 'Export capacity kW', n: 1, v: function (r) { return r.mec; }, f: function (r) { return U.int(r.mec); } }
    ]
  };
  M.COLS = COLS;
  var sort = { key: null, dir: 1 };
  function listRows(view) { return RBX.state.inView && RBX.kpi.inViewRows ? RBX.kpi.inViewRows(RBX.filters.active(view)) : RBX.filters.active(view); }
  function tableHTML(view, rows) {
    var cols = COLS[view];
    var c = cols.filter(function (x) { return x.k === sort.key; })[0];
    if (c) rows = rows.slice().sort(function (a, b) { var x = c.v(a), y = c.v(b); return (x < y ? -1 : x > y ? 1 : 0) * sort.dir; });
    return '<table class="sites-t" data-view="' + view + '"><caption class="sr-only">Sites shown, ' + rows.length + ' rows. Select a column header to sort.</caption><thead><tr>' + cols.map(function (x) {
      var s = x.k === sort.key ? (sort.dir > 0 ? 'ascending' : 'descending') : 'none';
      return '<th scope="col" aria-sort="' + s + '" class="c-' + x.k + (x.n ? ' n' : '') + '"><button type="button" data-sort="' + x.k + '"><span>' + U.caseSafe(x.l) + '</span>' +
        '<span class="st" aria-hidden="true">' + (s === 'ascending' ? '▲' : s === 'descending' ? '▼' : '') + '</span></button></th>';
    }).join('') + '</tr></thead><tbody>' + rows.map(function (r) {
      return '<tr>' + cols.map(function (x, i) {
        var v = x.f ? x.f(r) : x.v(r);
        if (i === (view === 'sam' ? 1 : 0)) return '<th scope="row" class="c-' + x.k + '"><button type="button" class="st-open" data-open="' + r.kind + ':' + r.id + '">' + RBX.icons.forRow(r, 12) + '<span>' + U.esc(v) + '</span></button></th>';
        return '<td class="c-' + x.k + (x.n ? ' n' : '') + '">' + U.esc(v) + '</td>';
      }).join('') + '</tr>';
    }).join('') + '</tbody></table>';
  }
  M.sitesList = function () {
    var view = RBX.state.view === 'ppa' ? (RBX.state.lastPeaker || 'sam') : RBX.state.view;
    var rows = listRows(view), all = RBX.data.rows[view].length;
    sort = { key: view === 'sam' ? 'ref' : 'kw', dir: view === 'sam' ? 1 : -1 };
    var grp = ((RBX.config.views || {})[view] || {}).searchGroup || view.toUpperCase();
    M.open({ title: 'Sites list', cls: 'modal-wide modal-sites', sub: U.esc(grp) + ' · ' + U.int(rows.length) + ' of ' + U.int(all) + ' sites shown' + (RBX.state.inView ? ' (in view)' : '') + ' · the current filters apply',
      html: '<div class="modal-acts top"><button type="button" class="btn" data-csv="1">' + (RBX.exporter ? RBX.exporter.ICON : '') + 'Download CSV</button></div><div class="sites-wrap" id="sitesWrap">' + tableHTML(view, rows) + '</div>',
      onOpen: function (box) {
        box.addEventListener('click', function (e) {
          var s = e.target.closest('[data-sort]');
          if (s) { var k = s.getAttribute('data-sort'); sort.dir = sort.key === k ? -sort.dir : (k === 'name' || k === 'town' || k === 'fuel' || k === 'ref' ? 1 : -1); sort.key = k;
            document.getElementById('sitesWrap').innerHTML = tableHTML(view, rows); var nb = box.querySelector('[data-sort="' + k + '"]'); if (nb) nb.focus(); return; }
          var o = e.target.closest('[data-open]');
          if (o) { var a = o.getAttribute('data-open').split(':'); M.close(true); RBX.app.openSite(RBX.data.rows[a[0]][+a[1]], { fly: true }); return; }
          if (e.target.closest('[data-csv]') && RBX.exporter) RBX.exporter.sitesCsv(view, rows);
        });
      } });
  };

  // ------------------------------------------------------------------ menu + keys
  var ICON = {
    list: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M7 5.5h10M7 10h10M7 14.5h10"/><circle cx="3.6" cy="5.5" r=".9" fill="currentColor"/><circle cx="3.6" cy="10" r=".9" fill="currentColor"/><circle cx="3.6" cy="14.5" r=".9" fill="currentColor"/></svg>',
    key: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><rect x="2.5" y="5" width="15" height="10" rx="2"/><path d="M5.5 8h1M8.5 8h1M11.5 8h1M14.5 8h.1M6 12h8"/></svg>',
    info: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.1"/></svg>'
  };
  M.ICON = ICON;
  var menu = RBX.header.menu;
  menu.push({ id: 'list', order: 30, label: 'Sites list', icon: ICON.list, run: M.sitesList, when: function () { return RBX.state.view !== 'ppa'; } });
  menu.push({ id: 'keys', order: 80, sep: true, label: 'Keyboard shortcuts', hint: '?', icon: ICON.key, run: M.shortcuts, when: function () { return !U.isTouch(); } });
  menu.push({ id: 'about', order: 90, label: 'About this map', icon: ICON.info, run: M.about });

  document.addEventListener('keydown', function (e) {
    if (e.key !== '?' || e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target; if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return;
    if (RBX.search.isOpen() || M.isOpen()) return;
    e.preventDefault(); M.shortcuts();
  });
})();
