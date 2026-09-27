/* RBX.ppaHost: mounts the PPA Benchmark module (core/js/ppa.js, RBX.ppa.mount) into #ppa on first entry and
   keeps it in sync with theme changes. If the module is not bundled, a placeholder is shown instead. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var P = RBX.ppaHost = { inst: null };

  /** Chip callback: the client has no header chips, so it only feeds the live region. Audiences override. */
  RBX.hooks.ppaChips = RBX.hooks.ppaChips || function (c) {
    var l = document.getElementById('live');
    if (l && c) l.textContent = U.int(c.sites) + ' sites, ' + (c.mw != null ? U.num(c.mw, 1) : '') + ' MW, ' + U.int(c.counterparties) + ' counterparties';
  };

  P.ensure = function () {
    var el = document.getElementById('ppa');
    if (P.inst || P.placeholder) return P.inst;
    if (RBX.ppa && typeof RBX.ppa.mount === 'function') {
      try {
        P.inst = RBX.ppa.mount(el, {
          prices: RBX.data.ppa, register: RBX.data.register(), audience: RBX.config.audience || 'client', theme: RBX.state.theme,
          onChips: function (c) { RBX.hooks.ppaChips(c); RBX.bus.emit('ppaChips', c); },
          onChange: function (st) { RBX.state.ppa = st; },
          onSiteClick: function (row) { var r = row && (RBX.data.byKey.sam[row.key] || RBX.data.byKey.sam[U.compactPc(row.postcode)]); if (r) RBX.app.openSite(r, { fly: true }); },
          util: RBX.util
        });
      } catch (e) {
        if (window.console) console.error('[atlas] PPA module failed to mount', e);
        P.inst = null;
      }
    }
    if (!P.inst) {
      // Safety net only: ppa.js is a required bundle file; this shows if the module throws while mounting.
      P.placeholder = true;
      var vc = (RBX.config.views || {}).ppa || {};
      el.innerHTML = '<div class="ppa-ph"><p class="kicker">' + U.esc(vc.kicker || 'PPA & PRICE BENCHMARK') + '</p><h2>PPA Benchmark</h2><p>' + U.esc(RBX.config.ppaPlaceholder || '') + '</p></div>';
    }
    return P.inst;
  };
  P.show = function () {
    var i = P.ensure();
    if (i && i.refresh) { try { i.refresh(); } catch (e) { /* module handles its own state */ } }
  };
  P.setFilter = function (partial) { var i = P.ensure(); if (i && i.setFilter) i.setFilter(partial); };
  /** Filter the register to one site, scroll to its row and flash it (falls back to a text filter). */
  P.showSite = function (row) {
    var i = P.ensure(); if (!i) return;
    if (i.showSite) { if (i.showSite(row.key)) return; }
    if (i.setFilter) i.setFilter({ q: row.pc });
  };
  RBX.bus.on('theme', function (t) { if (P.inst && P.inst.setTheme) { try { P.inst.setTheme(t); } catch (e) { /* ignore */ } } });
})();
