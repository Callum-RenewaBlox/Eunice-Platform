/* Investor build only. Investor legends (spec 6.3c investor table): SAM tiers with the +% uplift and an
   "Awaiting BM figure" row (hollow; toggles pricing), Hydro export class + confidence, TAM as the client plus a
   Scale pair (All sizes | AD-scale only (<10 MW)). Each ends with its verbatim note, clamped to 4 lines. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, H = RBX.hooks, I = RBX.inv;
  var G = H.legendGroups = H.legendGroups || {};
  var noteOpen = {};

  function sw(o) { return RBX.icons.svg(Object.assign({ size: 14 }, o)); }
  function note(view) {
    var t = ((RBX.config.notes || {})[view]) || '';
    if (!t) return '';
    var open = !!noteOpen[view];
    return '<div class="inv-note' + (open ? ' open' : '') + '" data-note="' + view + '"><p class="inv-note-t" id="note-' + view + '">' + U.esc(t) + '</p>' +
      '<button type="button" class="more-link" data-note-more="' + view + '" aria-expanded="' + open + '" aria-controls="note-' + view + '">' + (open ? 'less' : 'more') + '</button></div>';
  }
  /** Hydro export-class glyphs: a part-filled disc (export-limited) and a struck-through ring (no export). */
  function expGlyph(i) {
    var c = 'var(--ink-2)';
    if (i === 0) return '<svg class="glyph" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.6" fill="none" stroke="' + c + '" stroke-width="1.5"/><path d="M1.4 7a5.6 5.6 0 0 0 11.2 0z" fill="' + c + '"/></svg>';
    return '<svg class="glyph" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.6" fill="none" stroke="' + c + '" stroke-width="1.5"/><path d="M3 11 11 3" stroke="' + c + '" stroke-width="1.5"/></svg>';
  }

  G.sam = function () {
    var cfg = RBX.config, lc = (cfg.legend || {}).sam || {}, P = RBX.theme.pal(), tiers = cfg.labels.tiers;
    // live TCV per tier over the rows that pass every filter except the tier set itself (faceted)
    var tcvBy = {};
    RBX.data.rows.sam.forEach(function (r) { if (RBX.filters.pass(r, 'tiers') && r.tcv != null) tcvBy[r.t] = (tcvBy[r.t] || 0) + r.tcv; });
    return {
      title: lc.title, sub: lc.sub, sets: ['tiers', 'pricing'],
      groups: [
        { type: 'rows', set: 'tiers', prop: 't', sumFn: function (r) { return r.tcv || 0; },
          valueFn: function (f, it) { return '<span class="up">+' + I.uplift(it.value) + '%</span>'; },
          items: [1, 2, 3, 4, 5].map(function (t) {
            return { value: t, label: tiers[t], sec: U.abbr(tcvBy[t] || 0) + ' TCV · ' + (cfg.bmrev[t] || {}).a + 'p BM', secClass: 'inv',
              swatch: sw({ shape: 'dot', color: P.tier[t - 1] }), color: P.tier[t - 1] };
          }) },
        { type: 'rows', set: 'pricing', prop: 'pr', sumFn: function (r) { return r.kw || 0; },
          valueFn: function (f) { return U.mw(f.kw) + '<small>MW</small>'; },
          items: [{ value: 0, label: lc.awaiting || 'Awaiting BM figure', sec: 'hollow rings · no TCV yet', swatch: sw({ shape: 'ring', color: P.ink2 }), color: 'var(--ink-3)' }] }
      ],
      after: note('sam')
    };
  };

  G.hydro = function () {
    var cfg = RBX.config, lc = (cfg.legend || {}).hydro || {}, P = RBX.theme.pal(), L = cfg.labels;
    var exp = L.hydroExport || ['Export-limited', 'No export'];
    return {
      title: lc.title, sets: ['export', 'confs'],
      groups: [
        { type: 'rows', title: lc.exportTitle, set: 'export', prop: 'exp', unit: 'kW', items: exp.map(function (e, i) {
          return { value: i, label: e, swatch: expGlyph(i), color: 'var(--ink-3)' };
        }) },
        { type: 'rows', title: lc.confTitle, set: 'confs', prop: 'c', unit: 'kW', items: L.conf.map(function (c, i) {
          return { value: i, label: c, swatch: i === 3 ? sw({ shape: 'ring', color: P.unv }) : sw({ shape: 'dot', color: P.hyd[i] }), color: i === 3 ? P.unv : P.hyd[i] };
        }) }
      ],
      after: note('hydro')
    };
  };

  G.tam = function () {
    var sp = RBX.legend.defaults.tam(), lc = (RBX.config.legend || {}).tam || {};
    var adOnly = (RBX.state.hidden.scale || new Set()).has(1);
    var fac = RBX.filters.facet('tam', 'scale');
    var all = (fac[0] || { n: 0 }).n + (fac[1] || { n: 0 }).n, ad = (fac[0] || { n: 0 }).n;
    sp.sets = sp.sets.concat(['scale']);
    sp.groups.push({ type: 'html', title: lc.scaleTitle || 'SCALE', html: function () {
      return '<div class="inv-seg" role="radiogroup" aria-label="Scale">' +
        '<button type="button" role="radio" data-scale-set="all" aria-checked="' + !adOnly + '">All sizes <span class="n">' + U.int(all) + '</span></button>' +
        '<button type="button" role="radio" data-scale-set="ad" aria-checked="' + adOnly + '">AD-scale only (&lt;10 MW) <span class="n">' + U.int(ad) + '</span></button></div>' +
        '<p class="r-note">Recomputes TCV Potential without the sites of 10 MW and over.</p>';
    } });
    sp.after = note('tam');
    return sp;
  };

  /** Show "more" only when the note is actually clamped. */
  function fitNotes() {
    U.$$('.inv-note:not(.open)').forEach(function (n) {
      var t = n.querySelector('.inv-note-t'), b = n.querySelector('[data-note-more]');
      if (t && b) b.hidden = t.scrollHeight <= t.clientHeight + 1;
    });
  }
  var baseRail = RBX.rail.render;
  RBX.rail.render = function () { baseRail.apply(this, arguments); fitNotes(); };
  RBX.bus.on('theme', function () { setTimeout(fitNotes, 0); });
  window.addEventListener('resize', U.debounce(fitNotes, 200));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitNotes);

  document.addEventListener('click', function (e) {
    var m = e.target.closest('[data-note-more]'); if (!m) return;
    var v = m.getAttribute('data-note-more'), box = m.closest('.inv-note');
    noteOpen[v] = !noteOpen[v];
    box.classList.toggle('open', noteOpen[v]);
    m.textContent = noteOpen[v] ? 'less' : 'more';
    m.setAttribute('aria-expanded', String(noteOpen[v]));
  });
})();
