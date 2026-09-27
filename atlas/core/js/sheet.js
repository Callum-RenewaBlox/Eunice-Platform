/* RBX.sheet: the detail sheet shell (spec 6.4). Non-modal dialog; focus moves to × on open and returns on close.
   Header: kind chip, ‹ n of N › step-through (J/K), ×. Body sections come from a registry so audiences can add,
   replace or remove sections per kind:
     RBX.sheet.section(kind, id, { order, render(row) → html|'' , after(el,row)? })
     RBX.sheet.remove(kind, id)
     RBX.sheet.action(kind, id, { order, render(row) → html })   // sticky footer buttons
     RBX.sheet.chip[kind] = row → html                            // header kind chip
   Also opens the "N sites at this location" chooser for co-located stacks. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Sh = RBX.sheet = { sections: { sam: [], tam: [], hydro: [] }, actions: { sam: [], tam: [], hydro: [] }, chip: {} };
  var cur = null, opener = null;

  Sh.section = function (kind, id, def) {
    var list = Sh.sections[kind] = (Sh.sections[kind] || []).filter(function (s) { return s.id !== id; });
    list.push(Object.assign({ id: id, order: 50 }, def));
    list.sort(function (a, b) { return a.order - b.order; });
  };
  Sh.remove = function (kind, id) { Sh.sections[kind] = (Sh.sections[kind] || []).filter(function (s) { return s.id !== id; }); };
  Sh.action = function (kind, id, def) {
    var list = Sh.actions[kind] = (Sh.actions[kind] || []).filter(function (s) { return s.id !== id; });
    list.push(Object.assign({ id: id, order: 50 }, def));
    list.sort(function (a, b) { return a.order - b.order; });
  };
  Sh.removeAction = function (kind, id) { Sh.actions[kind] = (Sh.actions[kind] || []).filter(function (s) { return s.id !== id; }); };
  Sh.current = function () { return cur; };
  Sh.isOpen = function () { return !document.getElementById('sheet').hidden; };

  /** Ordered list for step-through: the active rows of the kind (audience hook for the order). */
  RBX.hooks.stepOrder = RBX.hooks.stepOrder || function (kind, rows) {
    if (kind === 'sam') return rows.slice().sort(function (a, b) { return (a.ref || 0) - (b.ref || 0) || a.t - b.t || (b.kw || 0) - (a.kw || 0); });
    return rows.slice().sort(function (a, b) { return (b.kw || 0) - (a.kw || 0); });
  };
  function order(kind) { return RBX.hooks.stepOrder(kind, RBX.filters.active(kind)); }

  var X = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15"/></svg>';
  var PREV = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M12.5 4.5 7 10l5.5 5.5"/></svg>';
  var NEXT = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M7.5 4.5 13 10l-5.5 5.5"/></svg>';

  function frame(chip, stepHTML, body, actions) {
    return '<button type="button" class="sh-handle" id="shHandle" aria-label="Expand details"><span class="rail-grip" aria-hidden="true"></span></button>' +
      '<div class="sh-top"><div class="sh-kind">' + chip + '</div>' + stepHTML +
      '<button type="button" class="sh-x" id="shX" aria-label="Close details (Esc)">' + X + '</button></div>' +
      '<div class="sh-body" id="shBody">' + body + '</div>' + (actions ? '<div class="sh-actions">' + actions + '</div>' : '');
  }
  function show(el, focus) {
    var was = !el.hidden;
    el.hidden = false;
    el.classList.remove('full');
    document.getElementById('app').classList.add('sheet-open');
    if (!was) opener = document.activeElement && document.activeElement !== document.body ? document.activeElement : opener;
    if (focus !== false) { var x = document.getElementById('shX'); if (x) x.focus({ preventScroll: true }); }
  }

  Sh.open = function (row, opts) {
    opts = opts || {};
    var el = document.getElementById('sheet'), kind = row.kind;
    cur = row;
    var list = order(kind), i = list.indexOf(row);
    var step = list.length > 1 && i >= 0 ? '<div class="sh-step"><button type="button" data-step="-1" aria-label="Previous site (K)">' + PREV + '</button><span>' + U.int(i + 1) + ' of ' + U.int(list.length) +
      '</span><button type="button" data-step="1" aria-label="Next site (J)">' + NEXT + '</button></div>' : '';
    var body = '', afters = [];
    (Sh.sections[kind] || []).forEach(function (s) {
      var h = s.render(row);
      if (h) { body += '<div data-sec="' + s.id + '">' + h + '</div>'; if (s.after) afters.push(s); }
    });
    var acts = (Sh.actions[kind] || []).map(function (a) { return a.render(row) || ''; }).join('');
    el.innerHTML = frame((Sh.chip[kind] || function () { return ''; })(row), step, body, acts);
    el.setAttribute('aria-labelledby', 'sheetName');
    show(el, opts.focus);
    afters.forEach(function (s) { var sec = el.querySelector('[data-sec="' + s.id + '"]'); if (sec) s.after(sec, row); });
    document.getElementById('shBody').scrollTop = 0;
  };

  Sh.chooser = function (rows) {
    var el = document.getElementById('sheet');
    cur = null;
    var body = '<h2 class="sh-name" id="sheetName">' + U.int(rows.length) + ' sites at this location</h2><p class="sh-meta">These sites share the same coordinates. Choose one.</p>' +
      '<div class="chooser">' + rows.map(function (r) {
        return '<button type="button" data-pick="' + r.kind + ':' + r.id + '">' + RBX.icons.forRow(r, 14) + '<span class="near-n">' + U.esc(r.name) + '</span><span class="near-d">' + U.cap(r.kw) + '</span></button>';
      }).join('') + '</div>';
    el.innerHTML = frame('<span>Co-located sites</span>', '', body, '');
    show(el);
  };

  /** A free-form panel in the sheet shell (e.g. "Sites near a postcode"): {chip, html, focus?}. */
  Sh.panel = function (o) {
    var el = document.getElementById('sheet');
    cur = null;
    el.innerHTML = frame(o.chip || '', '', o.html, o.actions || '');
    show(el, o.focus);
    document.getElementById('shBody').scrollTop = 0;
  };

  Sh.close = function () {
    var el = document.getElementById('sheet');
    if (el.hidden) return false;
    el.hidden = true; el.innerHTML = '';
    cur = null;
    document.getElementById('app').classList.remove('sheet-open');
    RBX.app.clearSelection();
    if (opener && opener.focus && document.body.contains(opener)) opener.focus({ preventScroll: true });
    opener = null;
    return true;
  };
  Sh.step = function (d) {
    if (!cur) return;
    var list = order(cur.kind); if (!list.length) return;
    var i = list.indexOf(cur), n = list[(i + d + list.length) % list.length];
    RBX.app.openSite(n, { fly: true, focus: false });
  };
  Sh.refresh = function () { if (cur) Sh.open(cur, { focus: false }); };

  Sh.init = function () {
    var el = document.getElementById('sheet');
    el.addEventListener('click', function (e) {
      if (e.target.closest('#shX')) { Sh.close(); return; }
      if (e.target.closest('#shHandle')) { el.classList.toggle('full'); return; }
      var st = e.target.closest('[data-step]'); if (st) { Sh.step(+st.getAttribute('data-step')); return; }
      var p = e.target.closest('[data-pick]');
      if (p) { var a = p.getAttribute('data-pick').split(':'); RBX.app.openSite(RBX.data.rows[a[0]][+a[1]], { fly: false }); return; }
      var hop = e.target.closest('[data-hop]');
      if (hop) { var b = hop.getAttribute('data-hop').split(':'); RBX.app.openSite(RBX.data.rows[b[0]][+b[1]], { fly: true, focus: false }); }
    });
    el.addEventListener('keydown', function (e) {
      if (e.target.closest('input,textarea')) return;
      if (e.key === 'ArrowRight') { Sh.step(1); e.preventDefault(); }
      if (e.key === 'ArrowLeft') { Sh.step(-1); e.preventDefault(); }
    });
    RBX.bus.on('theme', Sh.refresh);
  };
})();
