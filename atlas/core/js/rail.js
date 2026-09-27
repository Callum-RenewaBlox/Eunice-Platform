/* RBX.rail: the editorial rail (spec 6.3): kicker, headline, standfirst, KPI strip (client), view extras,
   legend-as-filter, capacity, foot. Collapses to a 44 px strip (L); on mobile it is a bottom sheet with a peek.
   Audience modules can add blocks with RBX.hooks.railBlocks[view] = () => html (rendered after the legend). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Rl = RBX.rail = {};
  RBX.hooks.railBlocks = RBX.hooks.railBlocks || {};
  RBX.hooks.railBefore = RBX.hooks.railBefore || {};

  function hydroSplit() {
    var rows = RBX.data.rows.hydro, P = RBX.theme.pal(), lc = (RBX.config.legend || {}).hydro || {};
    var inst = U.sum(rows, function (r) { return r.inst; }), mec = U.sum(rows, function (r) { return r.mec; }), str = U.sum(rows, function (r) { return r.kw; });
    return '<section class="r-sec" aria-labelledby="splitT"><div class="r-sec-h"><h3 class="r-sec-t" id="splitT">' + U.esc(lc.splitTitle || 'Where the power goes') + '</h3>' +
      '<span class="r-sec-a" style="text-decoration:none">all ' + rows.length + ' sites</span></div>' +
      '<div class="split-bar" role="img" aria-label="Installed ' + U.mw(inst) + ' MW: can export ' + U.mw(mec) + ' MW, stranded ' + U.mw(str) + ' MW">' +
      '<span class="hatch" style="flex:' + mec + '"></span><span style="flex:' + str + ';background:' + P.hyd[0] + '"></span></div>' +
      '<div class="split-lab"><span><b>' + U.mw(inst) + ' MW</b>installed</span><span><b>' + U.mw(mec) + ' MW</b>can export</span><span style="text-align:right"><b>' + U.mw(str) + ' MW</b>stranded</span></div></section>';
  }

  Rl.render = function () {
    var view = RBX.state.view, body = document.getElementById('railBody');
    if (!body || view === 'ppa') return;
    var vc = (RBX.config.views || {})[view] || {};
    // keep keyboard focus across re-renders (legend toggles re-render the rail)
    var ae = document.activeElement, key = null;
    if (ae && body.contains(ae)) {
      var host = ae.closest('[data-v],[data-fam],[data-preset],[id]');
      key = host ? { sel: host.id ? '#' + host.id : null, set: host.getAttribute('data-set'), v: host.getAttribute('data-v'), fam: host.getAttribute('data-fam'),
        preset: host.getAttribute('data-preset'), cls: ae.className, only: ae.hasAttribute('data-only') } : null;
    }
    var st = body.scrollTop, prevK = null;
    if (Rl.lastView === view) prevK = U.$$('.kpi-v', body).map(function (e) { return e.getAttribute('data-v'); });
    Rl.lastView = view;
    var h = '<p class="kicker">' + U.esc(vc.kicker || '') + '</p><h2 class="headline">' + U.esc(vc.headline || '') + '</h2>' +
      (vc.standfirst ? '<p class="standfirst" id="standfirst">' + vc.standfirst + '</p>' : '');
    if (RBX.hooks.railBefore[view]) h += RBX.hooks.railBefore[view]();
    h += RBX.kpi.html(view);
    if (view === 'hydro' && RBX.config.audience === 'client') h += hydroSplit();
    h += RBX.legend.html(view);
    if (RBX.hooks.railBlocks[view]) h += RBX.hooks.railBlocks[view]();
    h += RBX.hist.html(view);
    h += '<div class="rail-foot"><span class="rail-links"><button type="button" class="link-btn" data-act="sources">Sources &amp; method ›</button>' +
      (RBX.modal ? '<button type="button" class="link-btn" data-act="list">Sites list</button>' : '') +
      (RBX.nearme ? '<button type="button" class="link-btn" data-near="1">Near a postcode</button>' : '') + '</span>' +
      (vc.highlandsChip ? '<button type="button" class="chip-btn" data-act="highlands"><svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M2.5 15.5 7.5 7l3 5 2-3 5 6.5z"/></svg>' + U.esc(vc.highlandsChip) + '</button>' : '') + '</div>';
    body.innerHTML = h;
    body.scrollTop = st;
    if (prevK) {
      U.$$('.kpi-v', body).forEach(function (e, i) { if (prevK[i] != null) e.setAttribute('data-v', prevK[i]); });
      RBX.kpi.update(false);
    } else RBX.kpi.update(true);
    RBX.hist.draw();
    RBX.hist.sync();
    if (key) {
      var q = key.sel ? key.sel : key.set ? '[data-set="' + key.set + '"][data-v="' + key.v + '"]' : key.fam ? '[data-fam="' + key.fam + '"]' : key.preset ? '[data-preset="' + key.preset + '"]' : null;
      var el = q ? body.querySelector(q) : null;
      if (el && el.classList.contains('lg-row')) el = el.querySelector(key.only ? '.lg-only' : '.lg-main');
      if (el) el.focus({ preventScroll: true });
    }
    Rl.clampStandfirst();
  };
  /** On short viewports the standfirst clamps to 2 lines with a "more" link. */
  Rl.clampStandfirst = function () {
    var sf = document.getElementById('standfirst');
    if (!sf || U.isMobile() || window.innerHeight > 840 || Rl.sfOpen) return;
    sf.classList.add('clamped');
    if (sf.scrollHeight > sf.clientHeight + 2) {
      var more = document.createElement('button');
      more.type = 'button'; more.className = 'more-link'; more.textContent = 'more';
      more.addEventListener('click', function () { Rl.sfOpen = true; sf.classList.remove('clamped'); more.remove(); });
      sf.insertAdjacentElement('afterend', more);
    } else sf.classList.remove('clamped');
  };
  /** Light refresh while dragging the capacity slider: KPIs and histogram only. */
  Rl.light = function () { RBX.kpi.update(true); RBX.hist.sync(true); };

  Rl.setCollapsed = function (c) {
    var rail = document.getElementById('rail'), btn = document.getElementById('railCollapse');
    RBX.state.railCollapsed = !!c;
    rail.classList.toggle('collapsed', !!c);
    document.getElementById('app').classList.toggle('rail-collapsed', !!c);
    btn.setAttribute('aria-expanded', String(!c));
    btn.querySelector('.sr-only').textContent = c ? 'Expand panel' : 'Collapse panel';
    btn.title = (c ? 'Expand panel' : 'Collapse panel') + ' (L)';
  };
  Rl.toggle = function () {
    if (U.isMobile()) { Rl.setOpen(!document.getElementById('rail').classList.contains('open')); return; }
    Rl.setCollapsed(!RBX.state.railCollapsed);
  };
  Rl.setOpen = function (o) {
    var rail = document.getElementById('rail');
    rail.classList.toggle('open', !!o);
    document.getElementById('railHandle').setAttribute('aria-expanded', String(!!o));
    if (o) setTimeout(function () { RBX.hist.draw(); }, 340);
  };

  Rl.init = function () {
    var body = document.getElementById('railBody');
    RBX.legend.wire(body);
    RBX.hist.wire(body);
    body.addEventListener('click', function (e) {
      var a = e.target.closest('[data-act]'); if (!a) return;
      var act = a.getAttribute('data-act');
      if (act === 'sources') RBX.drawer.open();
      if (act === 'list' && RBX.modal) RBX.modal.sitesList();
      if (act === 'highlands' && RBX.map) {
        var rows = RBX.data.rows.hydro.filter(function (r) { return r.lat >= 56.4 && r.lon <= -3.3; });
        RBX.map.fitBounds(U.bbox(rows, 0.2), { padding: RBX.mapctl.fitPadding(), maxZoom: 8, duration: RBX.reduced ? 0 : 1200 });
      }
    });
    document.getElementById('railCollapse').addEventListener('click', Rl.toggle);
    document.getElementById('railHandle').addEventListener('click', function () { Rl.setOpen(!document.getElementById('rail').classList.contains('open')); });
    // tapping the peek (not a control) opens the sheet on mobile
    document.getElementById('rail').addEventListener('click', function (e) {
      if (U.isMobile() && !this.classList.contains('open') && !e.target.closest('button,a,input')) Rl.setOpen(true);
    });
    RBX.bus.on('filter', function (p) { if (p && p.light) Rl.light(); else { Rl.render(); } });
    RBX.bus.on('theme', Rl.render);
    window.addEventListener('resize', U.debounce(function () { RBX.hist.draw(); RBX.hist.thumb(); }, 150));
  };
})();
