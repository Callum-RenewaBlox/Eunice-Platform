/* RBX.kpi: the client rail KPI strip (spec 6.3b). Three cells per view from config.views[v].kpis, a verbatim
   Universe line with the P1 "In view" switch (recount over the visible, unobstructed map on moveend), count-up
   from the previous value, and a debounced aria-live sentence. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var K = RBX.kpi = {};

  /** Named metrics over the active rows. Audience modules may add more. */
  K.metrics = {
    count: function (rows) { return { v: rows.length, d: 0 }; },
    sumKw: function (rows) { var s = U.sum(rows, function (r) { return r.kw; }); return { v: s / 1000, d: U.mwDigits(s) }; },
    sumBm: function (rows) {
      var f = function (r) { return r.kind === 'sam' ? r.kwBm : r.bm; };
      var s = U.sum(rows, f);
      return { v: s / 1000, d: U.mwDigits(s), known: rows.filter(function (r) { return f(r) != null; }).length };
    },
    sumInst: function (rows) { var s = U.sum(rows, function (r) { return r.inst; }); return { v: s / 1000, d: U.mwDigits(s) }; }
  };

  /** Rows of a view that sit inside the unobstructed part of the map (rail, sheet and mobile peek excluded). */
  K.inViewRows = function (rows) {
    var m = RBX.map; if (!m) return rows;
    var c = m.getContainer(), o = RBX.mapctl.obstruction(), W = c.clientWidth, H = c.clientHeight;
    var x0 = (o.left || 0), x1 = W - (o.right || 0), y0 = o.top || 0, y1 = H - (o.bottom || 0);
    var b = m.getBounds().toArray(), pad = 0.5;   // cheap pre-filter in degrees before projecting
    return rows.filter(function (r) {
      if (r.lon < b[0][0] - pad || r.lon > b[1][0] + pad || r.lat < b[0][1] - pad || r.lat > b[1][1] + pad) return false;
      var p = m.project([r.lon, r.lat]);
      return p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1;
    });
  };
  /** Rows the KPIs count: the active (filtered) rows, optionally limited to the map view. */
  K.rows = function (view) {
    var rows = RBX.filters.active(view);
    return RBX.state.inView && RBX.map ? K.inViewRows(rows) : rows;
  };

  function label(k) { return RBX.state.inView ? String(k.label).replace(/\bshown\b/i, 'in view') : k.label; }

  K.html = function (view) {
    var vc = (RBX.config.views || {})[view] || {};
    if (!vc.kpis) return '';
    var on = !!RBX.state.inView;
    var sw = RBX.map ? '<button type="button" class="iv-sw" id="ivSw" role="switch" aria-checked="' + on + '" title="Count only the sites visible on the map">' +
      '<span class="iv-track" aria-hidden="true"><span class="iv-dot"></span></span>In view</button>' : '';
    return '<div class="kpis' + (on ? ' in-view' : '') + '" role="group" aria-label="Key figures">' + vc.kpis.map(function (k, i) {
      return '<div class="kpi"><div class="kpi-l" id="kpil' + i + '">' + U.esc(label(k)) + '</div><div class="kpi-v" id="kpi' + i + '"></div><div class="kpi-c" id="kpic' + i + '"></div></div>';
    }).join('') + '</div><div class="universe"><span>Universe · <b>' + U.esc(vc.universe || '') + '</b></span>' + sw + '</div>';
  };

  var announce = U.debounce(function (msg) { var l = document.getElementById('live'); if (l) l.textContent = msg; }, 400);
  K.update = function (instant) {
    var view = RBX.state.view, vc = (RBX.config.views || {})[view] || {};
    if (!vc.kpis || view === 'ppa') return;
    var rows = K.rows(view), all = RBX.data.rows[view] || [];
    vc.kpis.forEach(function (k, i) {
      var el = document.getElementById('kpi' + i), cap = document.getElementById('kpic' + i), lb = document.getElementById('kpil' + i);
      if (!el) return;
      var m = (K.metrics[k.metric] || K.metrics.count)(rows);
      var fmt = function (x) { return U.num(x, m.d) + (k.unit ? '<small>' + U.esc(k.unit) + '</small>' : ''); };
      if (instant) { el.setAttribute('data-v', String(m.v)); el.innerHTML = fmt(m.v); } else U.countUp(el, m.v, fmt, 600);
      if (cap) cap.textContent = !rows.length && /\{known\}/.test(k.caption || '') ? 'no sites shown'
        : U.template(k.caption || '', { known: U.int(m.known), n: U.int(rows.length), total: U.int(all.length) });
      if (lb) lb.textContent = label(k);
    });
    if (!instant) {
      var kwSum = U.sum(rows, function (r) { return r.kw; });
      announce((RBX.state.inView ? 'In view: ' : 'Showing ') + U.int(rows.length) + ' of ' + U.int(all.length) + ' sites, ' + U.mw(kwSum) + ' MW' + (view === 'hydro' ? ' stranded' : ''));
    }
  };

  K.setInView = function (on) {
    RBX.state.inView = !!on;
    var b = document.getElementById('ivSw'); if (b) b.setAttribute('aria-checked', String(!!on));
    var g = document.querySelector('.kpis'); if (g) g.classList.toggle('in-view', !!on);
    K.update(false);
  };
  document.addEventListener('click', function (e) { if (e.target.closest('#ivSw')) K.setInView(!RBX.state.inView); });
  RBX.bus.on('mapready', function (map) {
    map.on('moveend', function () { if (RBX.state.inView && RBX.state.view !== 'ppa') K.update(false); });
    if (RBX.rail && RBX.state.view !== 'ppa') RBX.rail.render();   // the switch needs the map
  });
  RBX.bus.on('select', function () { if (RBX.state.inView) setTimeout(function () { K.update(false); }, 0); });
})();
