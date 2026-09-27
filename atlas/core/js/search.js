/* RBX.search: ⌘K / "/" command palette across every layer (spec 6.5). Tokenised AND matching with per-field
   weights; postcodes match with or without the space; outcodes; RO refs; operators. Grouped results, a
   "Zoom to all N results" action, keyboard (↑ ↓ Enter Esc), empty state with suggestions. Choosing a result
   switches view, clears any filter hiding it (toast with Undo), flies there, opens the sheet and pulses it. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Sr = RBX.search = { extras: [] };
  var IDX = [], hits = [], act = -1, lastFocus = null, expanded = {};
  var PC_FULL = /^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/i, PC_OUT = /^[A-Z]{1,2}\d[A-Z\d]?$/i;

  /** Index fields per row: [text, weight, isName]. Audience modules may extend via RBX.hooks.searchFields. */
  RBX.hooks.searchFields = RBX.hooks.searchFields || function () { return []; };
  function fields(r) {
    var f = [];
    if (r.kind === 'sam') {
      f.push([r.name, 1, 1], [r.site, 0.8], [r.town, 0.8], [r.la, 0.6], [r.pc, 0.95], [r.op, 0.7], [r.off && r.off !== 'Generator is sole holder' ? r.off : '', 0.5]);
    } else if (r.kind === 'tam') {
      f.push([r.name, 1, 1], [r.fuel, 0.5], [RBX.config.labels.families[r.fam], 0.5], [r.ro, 0.95]);
    } else f.push([r.name, 1, 1]);
    return f.concat(RBX.hooks.searchFields(r) || []).filter(function (x) { return x[0]; }).map(function (x) {
      var n = U.norm(x[0]);
      return { n: n, w: ' ' + n, wt: x[1], name: !!x[2] };
    });
  }
  Sr.build = function () {
    IDX = [];
    ['sam', 'hydro', 'tam'].forEach(function (k) {
      RBX.data.rows[k].forEach(function (r) {
        IDX.push({ r: r, f: fields(r), pc: r.pc ? U.compactPc(r.pc) : '', out: r.outcode || '' });
      });
    });
  };

  function subseq(tok, s) { var i = 0; for (var j = 0; j < s.length && i < tok.length; j++) if (s[j] === tok[i]) i++; return i === tok.length; }
  /** Points for one token against one entry (best field), 0 when it does not match. */
  function tokPts(e, t) {
    var best = 0;
    for (var i = 0; i < e.f.length; i++) {
      var f = e.f[i], p = 0;
      if (f.n.indexOf(t) === 0) p = 100;
      else if (f.w.indexOf(' ' + t) >= 0) p = 82;
      else if (f.n.indexOf(t) >= 0) p = 55;
      else if (f.name && t.length >= 3 && subseq(t, f.n.replace(/ /g, ''))) p = 30;
      p *= f.wt;
      if (p > best) best = p;
    }
    return best;
  }
  Sr.query = function (q) {
    var raw = (q || '').trim();
    if (!raw) return [];
    var out = [], view = RBX.state.view;
    var qc = U.compactPc(raw), isPc = PC_FULL.test(raw), isOut = PC_OUT.test(raw);
    var toks = U.norm(raw).split(' ').filter(Boolean);
    if (!toks.length && !isPc) return [];
    IDX.forEach(function (e) {
      var pts = 0;
      if (isPc && e.pc) { if (e.pc === qc) pts = 100 * 0.95 * 2; else if (e.pc.indexOf(qc) === 0) pts = 70; }
      if (!pts && isOut && e.out === qc) pts = 100 * 0.95;
      if (!pts && e.pc && qc.length >= 4 && e.pc.indexOf(qc) === 0) pts = 70;
      if (!pts) {
        for (var i = 0; i < toks.length; i++) { var p = tokPts(e, toks[i]); if (!p) { pts = 0; break; } pts += p; }
      }
      if (pts > 0) out.push({ e: e, s: pts + (e.r.kind === view ? 10 : 0) });
    });
    out.sort(function (a, b) { return (b.s - a.s) || ((b.e.r.kw || 0) - (a.e.r.kw || 0)); });
    return out.map(function (x) { return x.e.r; });
  };

  // ------------------------------------------------------------------ UI
  var GROUP_ORDER = ['sam', 'hydro', 'tam'];
  function groupLabel(k) { return ((RBX.config.views || {})[k] || {}).searchGroup || k.toUpperCase(); }
  function sub(r) {
    if (r.kind === 'sam') return [r.town, r.pc, r.op].filter(Boolean).join(' · ');
    if (r.kind === 'tam') return r.fuel + (r.ro ? ' · ' + r.ro : ' · FiT accredited');
    return 'Stranded hydro' + (r.exp === 'No export' ? ' · No export' : '');
  }
  function right(r) {
    var L = RBX.config.labels;
    if (r.kind === 'sam') return U.cap(r.kw) + '<small>' + U.esc(L.tiers[r.t]) + '</small>';
    if (r.kind === 'tam') return U.cap(r.kw) + '<small>' + U.esc(r.bt ? 'Tier ' + r.bt + ' (indicative)' : 'Scotland') + '</small>';
    return U.int(r.kw) + ' kW<small>' + U.esc(r.c === 3 ? 'Unverified' : r.conf + ' confidence') + '</small>';
  }
  function hl(name, raw) {
    var toks = U.norm(raw).split(' ').filter(function (t) { return t.length >= 2; });
    var s = String(name), low = s.toLowerCase(), marks = [];
    toks.forEach(function (t) { var i = low.indexOf(t); if (i >= 0) marks.push([i, i + t.length]); });
    if (!marks.length) return U.esc(s);
    marks.sort(function (a, b) { return a[0] - b[0]; });
    var o = '', p = 0;
    marks.forEach(function (m) { if (m[0] < p) return; o += U.esc(s.slice(p, m[0])) + '<u>' + U.esc(s.slice(m[0], m[1])) + '</u>'; p = m[1]; });
    return o + U.esc(s.slice(p));
  }
  function optHTML(r, i, raw) {
    return '<div class="pal-opt" role="option" id="po' + i + '" data-h="' + i + '" aria-selected="false"><span class="pal-ic">' + RBX.icons.forRow(r, 14) + '</span>' +
      '<span style="min-width:0"><div class="pal-n">' + hl(r.name, raw) + '</div><div class="pal-s">' + U.esc(sub(r)) + '</div></span><span class="pal-v">' + right(r) + '</span></div>';
  }

  Sr.render = function () {
    var inp = document.getElementById('palQ'), list = document.getElementById('palList'), raw = inp.value.trim();
    hits = []; act = -1;
    var h = '';
    if (!raw) {
      var all = [].concat(RBX.data.rows.sam, RBX.data.rows.hydro, RBX.data.rows.tam).sort(function (a, b) { return (b.kw || 0) - (a.kw || 0); }).slice(0, 5);
      h += '<div class="pal-h"><span>Largest sites</span></div>';
      all.forEach(function (r) { hits.push({ row: r }); h += optHTML(r, hits.length - 1, ''); });
      h += '<div class="pal-h"><span>Try</span></div><div class="pal-sugg">' +
        ['Tier 1 sites', 'Highlands hydro', 'Over 1 MW', 'KT16 0EF'].map(function (s) { return '<button type="button" class="chip-btn" data-sugg="' + U.esc(s) + '">' + U.esc(s) + '</button>'; }).join('') + '</div>';
      document.getElementById('palCount').textContent = '';
    } else {
      var res = Sr.query(raw), view = RBX.state.view, acts = [];
      // feature actions for this query (e.g. "Sites near KT16 0EF"): fn(raw) → [{label, sub, icon, run}]
      Sr.extras.forEach(function (fn) { acts = acts.concat(fn(raw) || []); });
      var actHTML = function () {
        return acts.map(function (x) {
          hits.push({ run: x.run }); var i = hits.length - 1;
          return '<div class="pal-opt" role="option" id="po' + i + '" data-h="' + i + '" aria-selected="false"><span class="pal-ic">' + (x.icon || '') + '</span>' +
            '<span style="min-width:0"><div class="pal-n">' + U.esc(x.label) + '</div><div class="pal-s">' + U.esc(x.sub || '') + '</div></span><span class="pal-v"></span></div>';
        }).join('');
      };
      var order = [view].concat(GROUP_ORDER).filter(function (k, i, a) { return k !== 'ppa' && GROUP_ORDER.indexOf(k) >= 0 && a.indexOf(k) === i; });
      var groups = {};
      res.forEach(function (r) { (groups[r.kind] = groups[r.kind] || []).push(r); });
      var firstK = order.filter(function (k) { return groups[k]; })[0];
      if (firstK && groups[firstK].length > 1) {
        hits.push({ zoom: firstK, rows: groups[firstK] });
        h += '<div class="pal-opt" role="option" id="po0" data-h="0" aria-selected="false"><span class="pal-ic"><svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 7V3h4M17 7V3h-4M3 13v4h4M17 13v4h-4"/></svg></span>' +
          '<span><div class="pal-n">Zoom to all ' + U.int(groups[firstK].length) + ' results</div><div class="pal-s">' + U.esc(groupLabel(firstK)) + '</div></span><span class="pal-v"></span></div>';
      }
      order.forEach(function (k) {
        var g = groups[k]; if (!g) return;
        h += '<div class="pal-h" role="presentation"><span>' + U.esc(groupLabel(k)) + '</span><span>' + U.int(g.length) + '</span></div>';
        var lim = expanded[k] ? 60 : 6;
        g.slice(0, lim).forEach(function (r) { hits.push({ row: r }); h += optHTML(r, hits.length - 1, raw); });
        if (g.length > lim) { hits.push({ more: k }); h += '<button type="button" class="pal-more" role="option" id="po' + (hits.length - 1) + '" data-h="' + (hits.length - 1) + '" aria-selected="false">Show all ' + U.int(g.length) + '</button>'; }
      });
      if (acts.length && res.length) h += '<div class="pal-h" role="presentation"><span>Near a postcode</span></div>' + actHTML();
      if (!res.length) {
        hits = [];
        h = (acts.length ? '<div class="pal-h" role="presentation"><span>Near a postcode</span></div>' + actHTML() : '') +
          '<div class="pal-empty">No sites match ‘' + U.esc(raw) + '’.</div><div class="pal-sugg">' +
          ['Tier 1 sites', 'Highlands hydro', 'Over 1 MW'].map(function (s) { return '<button type="button" class="chip-btn" data-sugg="' + U.esc(s) + '">' + U.esc(s) + '</button>'; }).join('') + '</div>';
      }
      document.getElementById('palCount').textContent = res.length ? U.int(res.length) + ' result' + (res.length === 1 ? '' : 's') : '';
    }
    list.innerHTML = h;
    inp.setAttribute('aria-expanded', String(hits.length > 0));
    mark(hits.length ? (raw && hits[0].zoom && hits.length > 1 ? 1 : 0) : -1);
  };
  function mark(i) {
    act = i;
    var inp = document.getElementById('palQ');
    U.$$('#palList [data-h]').forEach(function (el) { el.setAttribute('aria-selected', String(+el.getAttribute('data-h') === i)); });
    var el = document.getElementById('po' + i);
    if (el) { inp.setAttribute('aria-activedescendant', 'po' + i); el.scrollIntoView({ block: 'nearest' }); } else inp.removeAttribute('aria-activedescendant');
  }
  function choose(i) {
    var h = hits[i]; if (!h) return;
    if (h.more) { expanded[h.more] = true; Sr.render(); return; }
    if (h.run) { Sr.close(true); h.run(); return; }
    if (h.zoom) {
      Sr.close(true);
      RBX.app.setView(h.zoom);
      if (RBX.map) RBX.map.fitBounds(U.bbox(h.rows, 0.05), { padding: RBX.mapctl.fitPadding(), maxZoom: 12, duration: RBX.reduced ? 0 : 900 });
      return;
    }
    Sr.close(true);
    Sr.reveal(h.row);
  };
  /** Switch view, un-hide the site if filtered out (toast with Undo), fly there and open the sheet. */
  Sr.reveal = function (row) {
    if (!row) return;
    var F = RBX.filters, hid = F.hiding(row);
    if (hid.length) {
      var snap = F.snapshot(), names = [];
      hid.forEach(function (h) {
        if (h.set === 'kw') { RBX.state.kw[row.kind] = null; names.push('all sizes'); }
        else { RBX.state.hidden[h.set].delete(h.value); names.push(Sr.valueLabel(row, h.set)); }
      });
      F.changed();
      RBX.toast('Showing ' + names.join(' and ') + ' again so you can see this site', { label: 'Undo', run: function () { F.restore(snap); } });
    }
    RBX.app.openSite(row, { fly: true });
  };
  Sr.valueLabel = function (r, set) {
    var L = RBX.config.labels;
    if (set === 'tiers') return 'Tier ' + r.t;
    if (set === 'fuels') return r.fuel;
    if (set === 'shapes') return r.ro ? 'RO sites' : 'FiT sites';
    if (set === 'precision') return r.ap ? 'approximate locations' : 'exact locations';
    if (set === 'tamTiers') return L.tiers[r.bt];
    if (set === 'confs') return (L.conf[r.c] || '') + ' confidence';
    return (RBX.hooks.filterLabel && RBX.hooks.filterLabel(r, set)) || 'hidden sites';
  };
  function suggestion(s) {
    Sr.close(true);
    if (s === 'Tier 1 sites') { RBX.app.setView('sam'); RBX.filters.only('tiers', 1, 'sam'); }
    else if (s === 'Highlands hydro') { RBX.app.setView('hydro'); var b = document.querySelector('[data-act="highlands"]'); if (b) b.click(); }
    else if (s === 'Over 1 MW') { if (RBX.state.view === 'ppa') RBX.app.setView('sam'); RBX.hist.setPreset('over'); }
    else { Sr.open(s); }
  }

  Sr.open = function (q) {
    var pal = document.getElementById('palette'), inp = document.getElementById('palQ');
    lastFocus = document.activeElement;
    expanded = {};
    pal.hidden = false;
    inp.value = q || '';
    Sr.render();
    setTimeout(function () { inp.focus(); if (q) inp.setSelectionRange(q.length, q.length); }, 0);
  };
  Sr.close = function (keepFocus) {
    var pal = document.getElementById('palette');
    if (pal.hidden) return;
    pal.hidden = true;
    if (!keepFocus && lastFocus && lastFocus.focus) lastFocus.focus();
  };
  Sr.isOpen = function () { return !document.getElementById('palette').hidden; };

  Sr.init = function () {
    Sr.build();
    var inp = document.getElementById('palQ'), pal = document.getElementById('palette'), list = document.getElementById('palList');
    inp.addEventListener('input', function () { expanded = {}; Sr.render(); });
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (hits.length) mark(Math.min(hits.length - 1, act + 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); if (hits.length) mark(Math.max(0, act - 1)); }
      else if (e.key === 'Enter') { e.preventDefault(); if (act >= 0) choose(act); }
      else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); Sr.close(); }
      else if (e.key === 'Tab') { e.preventDefault(); }
    });
    list.addEventListener('mousemove', function (e) { var o = e.target.closest('[data-h]'); if (o && +o.getAttribute('data-h') !== act) mark(+o.getAttribute('data-h')); });
    list.addEventListener('click', function (e) {
      var s = e.target.closest('[data-sugg]'); if (s) { suggestion(s.getAttribute('data-sugg')); return; }
      var o = e.target.closest('[data-h]'); if (o) choose(+o.getAttribute('data-h'));
    });
    pal.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) Sr.close(); });
  };
})();
