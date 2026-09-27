/* RBX.header: brand lockup, mode tabs (tablist), Peaker scope (radiogroup, only in Peaker mode), search trigger,
   theme toggle, optional audience actions (RBX.hooks.headerActions), overflow menu (spec 6.2). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Hd = RBX.header = {};

  var MARK = '<svg class="mark" viewBox="0 0 20 20" aria-hidden="true"><rect class="m-lime" x="0" y="0" width="9" height="9" rx="2" fill="#8FD14F"/>' +
    '<rect x="11" y="0" width="9" height="9" rx="2" fill="#3E8A6A"/><rect x="0" y="11" width="9" height="9" rx="2" fill="#2F6B55"/>' +
    '<rect x="11" y="11" width="9" height="9" rx="2" fill="#245744"/></svg>';
  Hd.MARK = MARK;
  var ICON = {
    search: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M13 13l4 4"/></svg>',
    theme: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="M10 3.5v13a6.5 6.5 0 0 0 0-13z" fill="currentColor" stroke="none"/></svg>',
    more: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="4.5" cy="10" r="1.2" fill="currentColor"/><circle cx="10" cy="10" r="1.2" fill="currentColor"/><circle cx="15.5" cy="10" r="1.2" fill="currentColor"/></svg>',
    book: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 4.5h5a2 2 0 0 1 2 2v9a1.6 1.6 0 0 0-1.6-1.6H4z"/><path d="M16 4.5h-5a2 2 0 0 0-2 2v9a1.6 1.6 0 0 1 1.6-1.6H16z"/></svg>',
    link: '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M8.5 11.5a3.5 3.5 0 0 0 5 0l2.5-2.5a3.5 3.5 0 0 0-5-5l-1 1"/><path d="M11.5 8.5a3.5 3.5 0 0 0-5 0L4 11a3.5 3.5 0 0 0 5 5l1-1"/></svg>'
  };
  Hd.ICON = ICON;
  /** Overflow menu items; audience modules may add entries ({id,label,icon,run}). */
  Hd.menu = [
    { id: 'sources', label: 'Sources & method', icon: ICON.book, run: function () { RBX.drawer.open(); } },
    { id: 'link', label: 'Copy link to this view', icon: ICON.link, run: function (btn) {
      var url = RBX.state.shareUrl(RBX.state.site ? RBX.sheet.current() : null);
      U.copyText(url, null).then(function (ok) { RBX.toast(ok ? 'Link copied' : url); });
    } }
  ];

  Hd.render = function () {
    var cfg = RBX.config, el = document.getElementById('hdr'), sc = cfg.scope || {};
    var tabs = cfg.tabs || [];
    var tabHTML = function (t) {
      var extra = t.count ? ' <span class="t-count num">' + U.esc(t.count) + '</span>' : '';
      return '<button type="button" class="tab" role="tab" id="tab-' + t.id + '" data-tab="' + t.id + '" aria-selected="false" aria-controls="' + (t.id === 'ppa' ? 'ppa' : 'mapArea') + '">' +
        '<span class="t-long">' + U.esc(t.label) + '</span><span class="t-short">' + U.esc(t.short || t.label) + extra + '</span></button>';
    };
    var scope = '<div class="scope" id="scope" role="radiogroup" aria-label="Peaker market scope">' +
      '<button type="button" class="scope-opt" role="radio" data-scope="tam" aria-checked="false"><span class="t-long">' + U.esc(sc.tam) + '</span></button>' +
      '<button type="button" class="scope-opt" role="radio" data-scope="sam" aria-checked="true"><span class="t-long">' + U.esc(sc.sam) + '</span></button></div>';
    var nav = '';
    tabs.forEach(function (t) {
      if (t.id === 'ppa') nav += '<span class="tab-div" aria-hidden="true"></span>';
      nav += tabHTML(t);
      if (t.id === 'peaker') nav += scope;
    });
    var actions = (RBX.hooks.headerActions ? RBX.hooks.headerActions() : '') +
      '<button type="button" class="hbtn" id="themeBtn" aria-pressed="false" aria-label="Night theme" title="Night theme (T)">' + ICON.theme + '</button>' +
      '<button type="button" class="hbtn" id="menuBtn" aria-haspopup="menu" aria-expanded="false" aria-controls="menuPop" aria-label="More">' + ICON.more + '</button>';
    el.innerHTML = '<div class="hdr-brand">' + MARK +
      '<h1 class="brand"><span aria-hidden="true">RenewaBlox</span><span class="sr-only">' + U.esc(cfg.h1 || cfg.title) + '</span></h1>' +
      '<span class="brand-rule" aria-hidden="true"></span><span class="brand-sub" aria-hidden="true"><span class="brand-product">' + U.esc(cfg.productLabel) + '</span>' +
      '<span class="brand-tag">no Watt wasted</span></span></div>' +
      '<nav class="hdr-nav" aria-label="Atlas views"><div class="tabs" role="tablist" aria-label="Atlas views">' + nav + '</div></nav>' +
      '<button type="button" class="hdr-search" id="hdrSearch" aria-label="Search sites (/)" aria-haspopup="dialog" aria-controls="palette">' + ICON.search +
      '<span class="lbl">Search sites, towns, postcodes…</span><span class="kbd" aria-hidden="true">/</span></button>' +
      '<div class="hdr-actions">' + actions + '</div>';

    el.addEventListener('click', function (e) {
      var t = e.target.closest('[data-tab]'), s = e.target.closest('[data-scope]');
      if (t) { var id = t.getAttribute('data-tab'); RBX.app.setView(id === 'peaker' ? RBX.state.lastPeaker : id); }
      else if (s) RBX.app.setView(s.getAttribute('data-scope'));
      else if (e.target.closest('#hdrSearch')) RBX.search.open();
      else if (e.target.closest('#themeBtn')) RBX.theme.toggle();
      else if (e.target.closest('#menuBtn')) Hd.toggleMenu();
    });
    // arrow keys move between tabs (roving focus within the tablist)
    el.querySelector('[role="tablist"]').addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      var list = U.$$('[role="tab"],[role="radio"]', el).filter(function (b) { return b.offsetParent !== null; });
      var i = list.indexOf(document.activeElement); if (i < 0) return;
      e.preventDefault();
      list[(i + (e.key === 'ArrowRight' ? 1 : -1) + list.length) % list.length].focus();
    });
    Hd.sync();
    RBX.bus.on('view', Hd.sync);
    RBX.bus.on('theme', Hd.sync);
  };

  Hd.sync = function () {
    var S = RBX.state, v = S.view, peaker = v === 'sam' || v === 'tam';
    U.$$('.tab').forEach(function (b) {
      var id = b.getAttribute('data-tab');
      var on = id === 'peaker' ? peaker : id === v;
      b.setAttribute('aria-selected', String(on));
      b.tabIndex = on ? 0 : -1;
    });
    var sc = document.getElementById('scope');
    if (sc) {
      sc.setAttribute('aria-hidden', String(!peaker));
      U.$$('.scope-opt', sc).forEach(function (b) {
        var on = b.getAttribute('data-scope') === (peaker ? v : S.lastPeaker);
        b.setAttribute('aria-checked', String(on));
        b.tabIndex = peaker ? (on ? 0 : -1) : -1;
      });
    }
    var tb = document.getElementById('themeBtn');
    if (tb) tb.setAttribute('aria-pressed', String(S.theme === 'night'));
  };

  // ------------------------------------------------------------------ overflow menu
  Hd.toggleMenu = function (force) {
    var pop = document.getElementById('menuPop'), btn = document.getElementById('menuBtn');
    var open = force != null ? force : pop.hidden;
    if (!open) { pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); return; }
    var items = Hd.menu.map(function (m, i) { return { m: m, o: m.order != null ? m.order : (i + 1) * 10 }; }).sort(function (a, b) { return a.o - b.o; }).map(function (x) { return x.m; });
    pop.innerHTML = items.filter(function (m) { return !m.when || m.when(); }).map(function (m, i) {
      var lab = typeof m.label === 'function' ? m.label() : m.label;
      return (m.sep && i ? '<div class="menu-sep" role="separator"></div>' : '') + '<button type="button" role="menuitem" data-mi="' + m.id + '">' + (m.icon || '') + '<span>' + U.esc(lab) + '</span>' +
        (m.hint ? '<span class="kbd menu-kbd" aria-hidden="true">' + U.esc(m.hint) + '</span>' : '') + '</button>';
    }).join('');
    var r = btn.getBoundingClientRect();
    pop.style.top = (r.bottom + 6) + 'px';
    pop.style.right = Math.max(8, window.innerWidth - r.right) + 'px';
    pop.hidden = false; btn.setAttribute('aria-expanded', 'true');
    var first = pop.querySelector('button'); if (first) first.focus();
  };
  document.addEventListener('click', function (e) {
    var pop = document.getElementById('menuPop'); if (!pop || pop.hidden) return;
    var mi = e.target.closest('[data-mi]');
    if (mi) {
      var item = Hd.menu.filter(function (m) { return m.id === mi.getAttribute('data-mi'); })[0];
      Hd.toggleMenu(false);
      if (item) item.run(mi);
      return;
    }
    if (!e.target.closest('#menuPop') && !e.target.closest('#menuBtn')) Hd.toggleMenu(false);
  });
  document.addEventListener('keydown', function (e) {
    var pop = document.getElementById('menuPop'); if (!pop || pop.hidden) return;
    var items = U.$$('button', pop), i = items.indexOf(document.activeElement);
    if (e.key === 'Escape') { Hd.toggleMenu(false); document.getElementById('menuBtn').focus(); e.stopPropagation(); e.preventDefault(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
  }, true);
})();
