/* RBX.drawer: Sources & method (spec 6.7). Modal right drawer; content from config.drawer. Audience modules add
   sections with RBX.hooks.drawerSections = () => [{title, html}] (audience notes, footers, method tables). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Dr = RBX.drawer = {};
  var last = null;

  Dr.html = function () {
    var d = RBX.config.drawer || {};
    var h = '<div class="dr-top"><h2 class="dr-title" id="drawerTitle">' + U.esc(d.title || 'Sources & method') + '</h2>' +
      '<button type="button" class="sh-x" data-close="1" aria-label="Close (Esc)"><svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15"/></svg></button></div><div class="dr-body">';
    h += '<section class="dr-sec"><h3>Data sources</h3><ul>' + (d.sources || []).map(function (s) { return '<li>' + U.esc(s) + '</li>'; }).join('') + '</ul></section>';
    if (d.provenance) h += '<section class="dr-sec"><h3>Provenance</h3><p>' + d.provenance + '</p></section>';
    if (d.glossary) h += '<section class="dr-sec"><h3>Glossary</h3><dl>' + d.glossary.map(function (g) { return '<dt>' + U.esc(g[0]) + '</dt><dd>' + U.esc(g[1]) + '</dd>'; }).join('') + '</dl></section>';
    (RBX.hooks.drawerSections ? RBX.hooks.drawerSections() : []).forEach(function (s) { h += '<section class="dr-sec"><h3>' + U.esc(s.title) + '</h3>' + s.html + '</section>'; });
    h += '<p class="dr-asof">' + U.esc(d.asOf || '') + '</p></div>';
    return h;
  };
  Dr.open = function () {
    var dr = document.getElementById('drawer'), panel = dr.querySelector('.drawer-panel');
    last = document.activeElement;
    panel.innerHTML = Dr.html();
    dr.hidden = false;
    var x = panel.querySelector('[data-close]'); if (x) x.focus();
  };
  Dr.close = function () {
    var dr = document.getElementById('drawer');
    if (dr.hidden) return false;
    dr.hidden = true;
    if (last && last.focus) last.focus();
    return true;
  };
  Dr.isOpen = function () { return !document.getElementById('drawer').hidden; };
  Dr.init = function () {
    var dr = document.getElementById('drawer');
    dr.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) Dr.close(); });
    dr.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var f = U.$$('button,a[href],[tabindex]:not([tabindex="-1"])', dr.querySelector('.drawer-panel'));
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { f[f.length - 1].focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { f[0].focus(); e.preventDefault(); }
    });
  };
})();
