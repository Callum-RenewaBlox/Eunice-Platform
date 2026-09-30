/* Investor Atlas v3 · present (design spec §10). core/js/investor/present.js keeps driving Present mode (chapters,
   camera, keys, autoplay, focus, exit and restore); this file only dresses each chapter card it renders:
   - the kicker after the eyebrow ("Chapter 2 / 6 · Serviceable market", story.json chapters[].kicker);
   - the contract-value stat (chapters 1, 2 and 4: tam.pot, sam.tcv, hydro.tcv) promoted to a hero figure with its
     treasury / ≥ 10 MW figure on the right, the other two stats as a two-column ledger below it; chapters without
     one lay their three stats out as columns (.three) with an optional caption (stats[].cap, .pc-cap);
   - a trailing p unit reads p/kWh; SVG arrows and an SVG Play/Pause (aria-pressed kept) instead of text glyphs;
   - the key hints (.pc-kb) become the disclaimer foot: ⓘ, the chapter view's model / registers / prices stamp over
     "Indicative; not investment advice." (at ≤1100 px, where the header lockup is hidden: "Confidential · …" with a
     lock).
   A MutationObserver watches #stage for the card and the card for each re-render; it only restyles the new nodes and
   never moves focus (present.js keeps it on the same control across renders). Registers STAT['rev.t1up'].
   While presenting: Space on a focused control presses it, Tab cycles through the card's controls (the passive tabs
   and the skip link leave the tab order), and phones frame a filtered chapter's sites above the card.
   Inert unless <html data-skin="product" data-app="investor">. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, doc = document.documentElement;
  if (doc.getAttribute('data-skin') !== 'product' || doc.getAttribute('data-app') !== 'investor') return;
  var Pr = RBX.present;
  if (!Pr || !Pr.STAT) return;
  var STAT = Pr.STAT;

  // ------------------------------------------------------------------ one extra caption token (spec §10.6)
  // the Tier 1 uplift over the wholesale baseline ("+270%"); used only inside a caption, never as a stat expr
  STAT['rev.t1up'] = function () { return '+' + RBX.inv.uplift(1) + '%'; };

  var HERO = /^(sam|hydro)\.tcv$|^tam\.pot$/;
  var SVG = function (d, cls) { return '<svg class="' + (cls || 'i') + '" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' + d + '</svg>'; };
  var ICON = {
    prev: SVG('<path d="M13 8H3M6.8 4.2 3 8l3.8 3.8"/>'),
    next: SVG('<path d="M3 8h10M9.2 4.2 13 8l-3.8 3.8"/>'),
    play: SVG('<path class="f" d="M5 3.2v9.6l7.4-4.8z"/>'),
    pause: SVG('<rect class="f" x="4.2" y="3.4" width="2.6" height="9.2" rx=".8"/><rect class="f" x="9.2" y="3.4" width="2.6" height="9.2" rx=".8"/>'),
    info: SVG('<circle cx="8" cy="8" r="6.2"/><path d="M8 7.3v3.9"/><circle class="f" cx="8" cy="5.1" r=".9"/>', 'i pc-i-info'),
    lock: SVG('<rect x="3.2" y="7" width="9.6" height="7" rx="1.8"/><path d="M5.3 7V5.3a2.7 2.7 0 0 1 5.4 0V7"/>', 'i pc-i-lock')
  };

  function chapters() { return ((RBX.config && RBX.config.story) || {}).chapters || []; }
  function stat(k) { try { return STAT[k] ? String(STAT[k]()) : ''; } catch (e) { return ''; } }
  function fill(s) { return String(s || '').replace(/\{([a-zA-Z0-9.]+)\}/g, function (m, k) { return STAT[k] ? stat(k) : m; }); }
  /** "£221.9M" → the v3 money grammar (full-size £, small magnitude letter); investor-v3.js owns the formatter. */
  function money(s) {
    if (RBX.v3 && RBX.v3.money) return RBX.v3.money(s);
    var m = /^(-?£?[\d.,]+)\s*(k|M|bn)?$/.exec(s);
    return m ? '<span class="money">' + U.esc(m[1]) + (m[2] ? '<span class="mag">' + m[2] + '</span>' : '') + '</span>' : U.esc(s);
  }
  /** A stat value with its trailing unit set small; a bare trailing p reads p/kWh ("29.6p" → 29.6 p/kWh). */
  function valueHtml(v) {
    var m = /^(.*?\d[%×]?)\s*(p|MW|kW|of\s+[\d,]+)$/.exec(v);
    if (!m) return U.esc(v);
    return U.esc(m[1]) + '<small>' + U.esc(m[2] === 'p' ? 'p/kWh' : m[2]) + '</small>';
  }
  /** A caption whose leading {token} is its figure: "{rev.t1up} vs 8.0p wholesale" → <b>+270%</b> vs 8.0p wholesale. */
  function capParts(cap) {
    var m = /^\s*\{([a-zA-Z0-9.]+)\}\s*([\s\S]*)$/.exec(String(cap || ''));
    if (m && STAT[m[1]]) return { fig: stat(m[1]), rest: fill(m[2]) };
    return { fig: '', rest: fill(cap) };
  }
  function asOf(view) {
    if (RBX.v3 && RBX.v3.asOf) return RBX.v3.asOf(view);
    var s = String((((RBX.config.band || {}).asOf) || {})[view] || '');
    return { stamp: s.split(' · Indicative')[0].replace(/\s*·\s*$/, ''), caveat: 'Indicative; not investment advice.' };
  }
  /** The hero's inline caption: the view's KPI caption ("no treasury" / "all sizes"), as in the rail. */
  function heroCaption(view) {
    var k = ((((RBX.config.views || {})[view] || {}).kpis) || [])[0];
    return (k && k.caption) || (view === 'tam' ? 'all sizes' : 'no treasury');
  }
  /** No-break spaces inside the *phrase* and between the title's last two words (no one-word last line). */
  function bindTitle(h) {
    if (!h) return;
    Array.prototype.forEach.call(h.querySelectorAll('em'), function (em) { em.textContent = em.textContent.replace(/ +/g, ' '); });
    var walker = document.createTreeWalker(h, NodeFilter.SHOW_TEXT, null), nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    var tail = '';
    for (var i = nodes.length - 1; i >= 0; i--) {
      var t = nodes[i].nodeValue, at = t.lastIndexOf(' ');
      if (at < 0) { tail = t + tail; continue; }
      // bind only when a single word follows the last breakable space (an already bound phrase is left alone)
      if (!/[\s ]/.test((t.slice(at + 1) + tail).trim())) nodes[i].nodeValue = t.slice(0, at) + ' ' + t.slice(at + 1);
      break;
    }
  }

  // ------------------------------------------------------------------ dress one rendered card
  var busy = false, cardObs = null;
  function enhance(el) {
    var a = el && el.querySelector('.pc-a');
    if (!a || a.hasAttribute('data-v3') || busy) return false;
    var i = RBX.state.present, c = chapters()[i];
    if (!c) return false;
    busy = true;
    try {
      a.setAttribute('data-v3', '');
      // eyebrow: "Chapter 2 / 6" + " · Serviceable market"
      var n = el.querySelector('.pc-n');
      if (n && c.kicker) {
        var k = document.createElement('span');
        k.className = 'k'; k.textContent = '· ' + c.kicker;
        n.appendChild(document.createTextNode(' ')); n.appendChild(k);
      }
      var ex = el.querySelector('.pc-exit');
      if (ex) {
        ex.innerHTML = 'Exit<span class="kbd" aria-hidden="true">Esc</span>';
        ex.setAttribute('aria-label', 'Exit presentation'); ex.setAttribute('aria-keyshortcuts', 'Escape');
      }
      bindTitle(el.querySelector('.pc-title'));
      // never break "Cal-2028" (and the like) at its hyphen; the body is escaped text, so only spans are added
      var bd = el.querySelector('.pc-body');
      if (bd) bd.innerHTML = bd.innerHTML.replace(/([A-Za-z]+-\d+)/g, '<span class="nw">$1</span>');

      // stats: rebuild each cell as label, figure, optional caption (the label reads first)
      var box = el.querySelector('.pc-stats'), cells = box ? Array.prototype.slice.call(box.children) : [], stats = c.stats || [], hero = -1;
      stats.forEach(function (s, j) { if (hero < 0 && HERO.test(s.expr)) hero = j; });
      cells.forEach(function (cell, j) {
        var s = stats[j]; if (!s) return;
        var lab = cell.querySelector('span'), v = STAT[s.expr] ? stat(s.expr) : '—';
        var html = '<span class="pc-l">' + (lab ? lab.innerHTML : U.esc(fill(s.label))) + '</span><b class="num">' + valueHtml(v) + '</b>';
        if (s.cap && j !== hero) {
          var cp = capParts(s.cap);
          html += '<span class="pc-cap">' + (cp.fig ? '<b>' + U.esc(cp.fig) + '</b> ' : '') + U.esc(cp.rest) + '</span>';
        }
        cell.innerHTML = html;
      });
      if (box && hero >= 0 && cells[hero]) {
        var hs = stats[hero], hp = capParts(hs.cap), hv = document.createElement('div');
        hv.className = 'pc-hero';
        hv.innerHTML = '<div class="pc-hero-l">' + U.esc(fill(hs.label)) + '</div>' +
          '<div class="pc-hero-row"><div class="pc-hero-v"><b class="num">' + money(stat(hs.expr)) + '</b><span class="cap">' + U.esc(heroCaption(c.view)) + '</span></div>' +
          (hp.fig || hp.rest ? '<div class="pc-hero-alt">' + (hp.fig ? '<b>' + U.esc(hp.fig) + '</b>' : '') + '<span>' + U.esc(hp.rest) + '</span></div>' : '') + '</div>';
        box.parentNode.insertBefore(hv, box);
        box.removeChild(cells[hero]);
        box.classList.add('two');
      } else if (box) box.classList.add('three');

      // controls: SVG arrows and Play / Pause (the button, its aria-pressed and any focus on it are kept)
      var pv = el.querySelector('[data-pc="prev"]');
      if (pv) pv.innerHTML = ICON.prev;
      var nx = el.querySelector('[data-pc="next"]');
      if (nx) { var lbl = (nx.textContent || '').trim() || 'Next'; nx.innerHTML = '<span>' + U.esc(lbl) + '</span>' + ICON.next; }
      var pl = el.querySelector('[data-pc="play"]');
      if (pl) {
        var on = pl.getAttribute('aria-pressed') === 'true';
        pl.innerHTML = (on ? ICON.pause : ICON.play) + '<span class="pc-bl">' + (on ? 'Pause' : 'Play') + '</span>';
        pl.classList.add('pc-play');
      }
      // the key hints become the disclaimer foot (Present's disclaimer; spec §10.2 item 6, §10.4)
      var kb = el.querySelector('.pc-kb'), ao = asOf(c.view);
      var conf = String((RBX.config && RBX.config.confidential) || 'Confidential · investor use only').split(' · ')[0];
      var foot = document.createElement('p');
      foot.className = 'pc-foot';
      foot.innerHTML = ICON.info + ICON.lock + '<span class="pc-ft"><span class="pc-l1"><span class="pc-conf">' + U.esc(conf) + ' · </span>' + U.esc(ao.stamp) + '</span>' +
        '<span class="pc-l2">' + U.esc(ao.caveat) + '</span></span>';
      if (kb) kb.parentNode.replaceChild(foot, kb);
      else { var ctl = el.querySelector('.pc-ctl'); if (ctl) ctl.appendChild(foot); }
    } finally {
      if (cardObs) cardObs.takeRecords();         // drop the records of our own edits
      busy = false;
    }
    return true;
  }

  function watchCard(el) {
    if (!window.MutationObserver || !el || el.__v3obs) return;
    el.__v3obs = true;
    cardObs = new MutationObserver(function () { enhance(el); });
    cardObs.observe(el, { childList: true });
  }
  var stage = document.getElementById('stage');
  if (stage && window.MutationObserver) {
    new MutationObserver(function (recs) {
      for (var r = 0; r < recs.length; r++) {
        for (var j = 0; j < recs[r].addedNodes.length; j++) {
          var nd = recs[r].addedNodes[j];
          if (nd.id === 'presentCard') { watchCard(nd); enhance(nd); }
        }
      }
    }).observe(stage, { childList: true });
    var pc = document.getElementById('presentCard');
    if (pc) { watchCard(pc); enhance(pc); }
  }

  // ------------------------------------------------------------------ keyboard: the tab order stays in the card
  // The passive header tabs and the skip link (which targets the hidden search) leave the tab order and the
  // accessibility tree while presenting; Tab and Shift+Tab then cycle through the card's own controls.
  function passive(on) {
    U.$$('#hdr .hdr-nav, .skip-link').forEach(function (el) { if (on) el.setAttribute('inert', ''); else el.removeAttribute('inert'); });
  }
  if (Pr.enter) {
    var enter0 = Pr.enter;
    Pr.enter = function () {
      var r = enter0.apply(this, arguments);
      if (Pr.active()) passive(true);
      return r;
    };
  }
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab' || e.altKey || e.ctrlKey || e.metaKey || !Pr.active || !Pr.active()) return;
    if ((RBX.modal && RBX.modal.isOpen()) || RBX.search.isOpen() || RBX.drawer.isOpen() || RBX.sheet.isOpen()) return;
    var el = document.getElementById('presentCard');
    if (!el || el.hidden) return;
    var f = U.$$('button:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])', el).filter(function (b) { return b.offsetParent !== null; });
    var i = f.indexOf(document.activeElement);
    if (!f.length || (i > 0 && e.shiftKey) || (i >= 0 && i < f.length - 1 && !e.shiftKey)) return;
    e.preventDefault();
    f[e.shiftKey ? f.length - 1 : 0].focus();
  });
  // present.js reads Space as "next" and prevents its default, so Space on a focused Exit, Prev, Play or progress
  // segment moved on a chapter instead of pressing it: leave Space to a focused control (its click runs on keyup;
  // Space on the focused Next still steps on through that click). Arrow keys and PageDown are unchanged.
  if (Pr.key) {
    var key0 = Pr.key;
    Pr.key = function (e) {
      var t = e && e.target;
      if (e && e.key === ' ' && t && t.closest && t.closest('button,a[href],[role="button"],summary,input,select,textarea')) return false;
      return key0.apply(this, arguments);
    };
  }

  // ------------------------------------------------------------------ phones: focus lands on "…" after Present
  // present.js returns focus to #presentBtn, which phones do not show (Present lives in the "…" menu there); when
  // that leaves focus nowhere, it goes to the menu button instead
  if (Pr.exit) {
    var exit0 = Pr.exit;
    Pr.exit = function () {
      passive(false);
      var r = exit0.apply(this, arguments), a = document.activeElement, mb = document.getElementById('menuBtn');
      if ((!a || a === document.body) && mb && mb.offsetParent !== null) mb.focus({ preventScroll: true });
      return r;
    };
  }

  // ------------------------------------------------------------------ phones: frame the map above the dressed card
  // present.js sizes the phone camera padding from the card as rendered, a moment before the observer dresses it
  // (the hero block makes it taller). While a chapter moves the camera, dress the card first and re-measure it.
  var inGo = false;
  if (Pr.go) {
    var go0 = Pr.go;
    Pr.go = function () { inGo = true; try { return go0.apply(this, arguments); } finally { inGo = false; } };
  }
  function cardH() {
    var el = document.getElementById('presentCard');
    if (!el || el.hidden) return 0;
    enhance(el);
    return el.offsetHeight;
  }
  // MapLibre's fitBounds ends in this.flyTo(): that inner flight already honours the fit's padding, so it must not
  // pick up the chapter fly offsets (investor-v3.js shifts every flight made during a chapter by half the header,
  // which pushed fitted chapters ~33 px down, ~56 px on phones); it goes straight to MapLibre's own flyTo.
  // On a short phone the card can leave less room than the padding asks for (MapLibre then refuses to fit), so the
  // bottom padding keeps at least 120 px of map below the header inset (investor-v3.js pads the top to inset + 24).
  // A filtered chapter with a fixed camera (chapter 3, Tier 1–2 around London) covers ~150 km on a phone, which
  // leaves most of its sites off screen or under the header: phones fit the chapter's visible sites instead,
  // never closer than its camera zoom (desktop keeps the story camera).
  RBX.bus.on('mapready', function (map) {
    var fit0 = map.fitBounds, fly0 = map.flyTo, proto = Object.getPrototypeOf(map), flyP = proto && proto.flyTo, inFit = 0;
    map.fitBounds = function (b, o) {
      if (inGo && U.isMobile() && o && o.padding && typeof o.padding === 'object') {
        var h = cardH();
        if (h) {
          var ins = RBX.v3 && RBX.v3.presentInset ? RBX.v3.presentInset() : 0, top = Math.max(o.padding.top || 0, ins ? ins + 24 : 0);
          var room = this.getContainer().clientHeight - top - 120;
          o = Object.assign({}, o, { padding: Object.assign({}, o.padding, { bottom: Math.max(0, Math.min(h + 24, room)) }) });
        }
      }
      inFit++;
      try { return fit0.call(this, b, o); } finally { inFit--; }
    };
    map.flyTo = function (o, e) {
      if (inFit && inGo && typeof flyP === 'function') return flyP.call(this, o, e);
      if (inGo && U.isMobile() && o && o.offset) {
        var c = chapters()[RBX.state.present], cam = (c && c.camera) || {}, rows = c && c.filters && cam.center && !cam.terrain ? RBX.filters.active(c.view) : [];
        if (rows.length) return this.fitBounds(U.bbox(rows, 0.05), { padding: { top: 20, bottom: 24, left: 20, right: 20 }, maxZoom: cam.zoom || 7.4, pitch: 0, bearing: 0, duration: o.duration, essential: true });
        var h = cardH();
        if (h) o = Object.assign({}, o, { offset: [o.offset[0], Math.round((20 - (h + 24)) / 2)] });
      }
      return fly0.call(this, o, e);
    };
  });
})();
