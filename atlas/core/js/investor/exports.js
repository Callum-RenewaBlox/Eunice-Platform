/* Investor build only. Investor columns for the shared P1 modules when they are bundled: CSV downloads
   (RBX.exporter.cols; the file opens with the config.csvHeader confidentiality row) and the accessible Sites list
   (RBX.modal.COLS). The SAM order column is the v1 rank (#), never the client's neutral Ref. */
(function () {
  'use strict';
  var RBX = window.RBX;
  function rank(r) { return r.rank; }
  var E = RBX.exporter;
  if (E && E.cols) {
    if (E.cols.sam) {
      E.cols.sam = E.cols.sam.filter(function (c) { return c[0] !== 'Ref'; });
      E.cols.sam.unshift(['#', rank]);
      E.cols.sam.splice(7, 0, ['Operator status', function (r) { return r.opSt || ''; }], ['Developer', function (r) { return r.dev; }],
        ['GSP group', function (r) { return r.gsp; }]);
      E.cols.sam.push(['Priced', function (r) { return r.pr ? 'Yes' : 'Awaiting BM figure'; }],
        ['Available for BM kW (model)', function (r) { return r.av; }], ['BTC mined (Yr 5)', function (r) { return r.btc; }],
        ['Energy and BM revenue £ (Yr 5)', function (r) { return r.en; }], ['TCV no treasury £', function (r) { return r.tcv; }],
        ['TCV treasury £', function (r) { return r.tcvT; }]);
    }
    if (E.cols.hydro) {
      E.cols.hydro.push(['BTC mined (Yr 5)', function (r) { return r.btc; }], ['TCV no treasury £', function (r) { return r.tcv; }],
        ['TCV treasury £', function (r) { return r.tcvT; }]);
    }
    if (E.cols.tam) {
      E.cols.tam.push(['Source register', function (r) { return r.src; }],
        ['Indicative TCV potential £', function (r) { return r.bt > 0 ? Math.round(r.pot || 0) : ''; }]);
    }
    if (E.cols.register) {
      E.cols.register[0] = ['#', function (o) { return o.rank; }];
      E.cols.register.splice(2, 0, ['Operator status', function (o) { return o.op_status || ''; }]);
    }
  }
  var M = RBX.modal;
  if (M && M.COLS && M.COLS.sam) {
    // T13: # · Site · TCV first (TCV is what an investor sorts by), Town dropped from the modal (kept in the CSV).
    // The key stays 'ref' so the list opens sorted by rank and a click sorts it ascending first.
    M.COLS.sam = M.COLS.sam.filter(function (c) { return c.k !== 'ref' && c.k !== 'town'; });
    M.COLS.sam.unshift({ k: 'ref', l: '#', n: 1, v: rank });
    M.COLS.sam.splice(2, 0, { k: 'tcv', l: 'TCV (no treasury)', n: 1, v: function (r) { return r.tcv == null ? -1 : r.tcv; },
      f: function (r) { return r.tcv == null ? 'Awaiting BM figure' : RBX.util.abbr(r.tcv); } });
    if (M.COLS.hydro) M.COLS.hydro.push({ k: 'tcv', l: 'TCV (no treasury)', n: 1, v: function (r) { return r.tcv || 0; }, f: function (r) { return RBX.util.abbr(r.tcv); } });
    if (M.COLS.tam) M.COLS.tam.push({ k: 'pot', l: 'TCV potential', n: 1, v: function (r) { return r.pot || 0; }, f: function (r) { return r.bt > 0 ? RBX.util.abbr(r.pot) : '—'; } });
  }
})();
