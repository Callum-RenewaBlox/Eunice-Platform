/* Investor Atlas v3 · map chrome and the PNG export band (design spec §8, §4.6, §11). Bundled after investor-v3.js
   and right before core/js/app.js; nothing in core/ or in the skin is edited, every change is a replaced property,
   a wrapper or an extra map layer:
   - the size key is a horizontal glass capsule whose discs are zoom-true (RBX.layers.radiusAt / tamScaleAt): SAM
     £1M / £4M / £9M plus the hollow "Awaiting BM figure" ring, Hydro 100 kW / 500 kW / 1.3 MW, TAM the five capacity
     bands in one row plus the dashed "Postcode district" ring; it stops short of the zoom stack, the attribution (i)
     and an open sheet, staying one row (its title, then the item after its divider give way; else it stands down);
   - while the panel is collapsed a small glass chip keeps the disclaimer and the model date on screen (with the
     Confidential mark at ≤ 1100 px, where the header lockup is hidden), and the scale bar and the size key restack
     above it; on tablets (761–1050 px) a sheet folds the panel (opened there, or brought there by a resize or a
     rotation) and the sheet's foot carries that line; opening the panel beside it re-frames the selected site;
   - the selected site gets a 2.5 px ring, a 2 px halo and a soft teal wash; hollow Hydro "Unverified" rings keep no
     shadow; the attribution folds to its (i) on desktop too; no annotation pencil; the hover tooltip stays clear of
     an open sheet and prints money as the panel does (£2.9M);
   - the PNG export band carries "Confidential · investor use only · <as of> · Indicative; not
     investment advice." right-aligned, with the brand quarter-circle moved clear of the text; the export card is
     v3's own (a quiet title, the panel's three figures, the legend over the sites shown) and the footer names the
     view's sources and date; the basemap is rendered at the image's own resolution for the frame it grabs;
     downloads drop the internal "v3" from their names; CSVs add the as-of and disclaimer.
   Inert unless <html data-skin="product" data-app="investor">. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util, doc = document.documentElement;
  if (doc.getAttribute('data-skin') !== 'product' || doc.getAttribute('data-app') !== 'investor') return;
  var V3 = RBX.v3 = RBX.v3 || {};

  function cfg() { return RBX.config || {}; }
  var CAVEAT = 'Indicative; not investment advice.';
  /** { stamp: 'Model · 16 Jun 2026', caveat, line } for a view: investor-v3.js's helper, or the same rule on config band.asOf. */
  function asOf(view) {
    if (V3.asOf) return V3.asOf(view);
    var bc = (cfg().band || {}).asOf || {}, s = String(bc[view] || bc.sam || '');
    var stamp = s.split(' · Indicative')[0].replace(/\s*·\s*$/, '');
    return { stamp: stamp, caveat: CAVEAT, line: stamp + ' · ' + CAVEAT };
  }
  function confText() {
    // the confidentiality mark never carries the caveat itself (it follows once, from asOf)
    return String(cfg().confidential || 'Confidential · investor use only').split(' · Indicative')[0];
  }
  function mapView() { var v = RBX.state.view; return v === 'ppa' ? RBX.state.lastPeaker || 'sam' : v; }
  var INFO = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.1"/></svg>';

  // ------------------------------------------------------------------ size key: one glass capsule, zoom-true discs (§8.1)
  var Sk = RBX.sizekey;
  var SK_TITLE = { sam: 'Contract value', hydro: 'Stranded capacity', tam: 'Capacity' };
  var TAM_BANDS = ['<250 kW', '<1 MW', '<5 MW', '<20 MW', '20 MW+'];
  /** One key item: an SVG disc drawn 1:1 at radius r (the stroke stays inside the box), then its label. */
  function item(r, label, circleAttr) {
    var b = r + 1.5, s = (2 * b).toFixed(1);
    return '<span class="sk-i"><svg width="' + s + '" height="' + s + '" viewBox="' + (-b).toFixed(1) + ' ' + (-b).toFixed(1) + ' ' + s + ' ' + s + '" aria-hidden="true">' +
      '<circle r="' + r.toFixed(1) + '"' + (circleAttr || '') + '/></svg>' + U.esc(label) + '</span>';
  }
  function hasAwaiting() {
    return (RBX.data.rows.sam || []).some(function (r) { return r.pr === 0; });
  }
  V3.sizeKeyHtml = function (view, z) {
    var vc = (cfg().views || {})[view] || {}, key = vc.sizeKey;
    if (!key) return '';
    var out = [], title = key.label || SK_TITLE[view] || key.title || '';
    if (view === 'tam') {
      var k = RBX.layers.tamScaleAt(z), D = RBX.icons.BAND_D || [7, 9.5, 12.5, 17, 23];
      D.forEach(function (d, i) { out.push(item(d * k / 2, TAM_BANDS[i] || '', ' class="band"')); });
      out.push('<span class="sk-div" aria-hidden="true"></span>');
      out.push(item(4.6, 'Postcode district', ' class="band dash"'));
    } else {
      (key.values || []).forEach(function (v) {
        var r = RBX.layers.radiusAt(view, z, Math.min(1.2, RBX.hooks.sizeValue(view, v)));
        out.push(item(r, RBX.hooks.sizeLabel(view, v)));
      });
      var aw = view === 'sam' ? ((cfg().legend || {}).sam || {}).awaiting : '';
      if (aw && hasAwaiting()) {
        out.push('<span class="sk-div" aria-hidden="true"></span>');
        out.push(item(4.6, aw, ' class="hollow"'));
      }
    }
    return '<span class="sizekey-t">' + U.esc(title) + '</span>' + out.join('');
  };
  if (Sk) {
    Sk.render = function () {
      var el = document.getElementById('sizekey'); if (!el) return;
      var view = RBX.state.view;
      var html = RBX.map && view !== 'ppa' ? V3.sizeKeyHtml(view, RBX.map.getZoom()) : '';
      el.classList.add('v3-sk');
      el.setAttribute('data-sk', view);
      if (el.innerHTML !== html) el.innerHTML = html;          // re-rendered on every zoom frame: touch the DOM only on change
      V3.fitSizeKey();
      if (Sk.clearLabels) Sk.clearLabels();
    };
  }

  /** Where a box comes to rest. The chrome slides (the key when the panel folds, the zoom stack beside an opening
      sheet, the panel's own width), so a running left/right/width transition is read at its end; the sheet slides
      in by transform, so its layout box is used. */
  function restX(el) {
    var r = el.getBoundingClientRect(), dx = 0, dw = 0;
    if (el.id === 'sheet') {
      var p = el.offsetParent; if (p) dx = p.getBoundingClientRect().left + p.clientLeft + el.offsetLeft - r.left;
    } else {
      (el.getAnimations ? el.getAnimations() : []).forEach(function (a) {
        var pr = a.transitionProperty; if (pr !== 'left' && pr !== 'right' && pr !== 'width') return;
        var k = a.effect && a.effect.getKeyframes ? a.effect.getKeyframes() : [];
        var d = (k.length ? parseFloat(k[k.length - 1][pr]) : NaN) - parseFloat(getComputedStyle(el)[pr]);
        if (isNaN(d)) return;
        if (pr === 'width') dw += d; else dx += pr === 'left' ? d : -d;
      });
    }
    return { left: r.left + dx, right: r.right + dx + dw, top: r.top, bottom: r.bottom };
  }
  function shown(el) { return !!el && !el.hidden && el.offsetParent !== null; }
  /** The key ends 12 px short of the zoom stack (when it shares the bottom of the map), 10 px short of the
      attribution (i) (when that sits at the key's height) and 14 px short of an open sheet. It is always one 42 px row
      (§8.1): short of room, first its title gives way (the discs' labels name their measure), then the item after the
      divider (SAM "Awaiting BM figure", TAM "Postcode district": the panel's legend and the sheet still explain
      them); if even that does not fit, it stands down rather than stacking into a box. Phones hide it (§12). */
  V3.fitSizeKey = function () {
    var el = document.getElementById('sizekey'); if (!el) return;
    el.classList.remove('sk-off', 'sk-tight', 'sk-tight2'); el.style.maxWidth = '';
    if (!el.innerHTML || U.isMobile() || !shown(el)) return;
    var k = restX(el), lim = window.innerWidth - 14, ctl = document.getElementById('mapCtl'), sh = document.getElementById('sheet');
    var at = document.querySelector('#map .maplibregl-ctrl-bottom-right');
    if (shown(sh)) lim = Math.min(lim, restX(sh).left - 14);
    if (shown(ctl)) { var c = restX(ctl); if (c.bottom > k.top - 80 && c.top < k.bottom) lim = Math.min(lim, c.left - 12); }
    if (shown(at) && at.offsetWidth) {
      // the container slides with the sheet (restX reads where it comes to rest); opened, the attribution text runs
      // left under the key's row, so only its (i) at the right end counts
      var a = restX(at), ai = at.querySelector('.maplibregl-compact-show') ? a.right - 24 : a.left;
      if (a.top < k.bottom + 8) lim = Math.min(lim, ai - 10);
    }
    var room = Math.floor(lim - k.left);
    if (room < 180) { el.classList.add('sk-off'); return; }
    el.style.maxWidth = room + 'px';
    var over = function () { return el.scrollWidth > room + 1; };
    if (!over()) return;
    el.classList.add('sk-tight'); if (!over()) return;
    if (el.querySelector('.sk-div')) { el.classList.add('sk-tight2'); if (!over()) return; }
    el.classList.remove('sk-tight', 'sk-tight2'); el.classList.add('sk-off'); el.style.maxWidth = '';
  };

  // ------------------------------------------------------------------ disclaimer chip while the panel is collapsed (§4.6)
  function discEl() {
    var el = document.getElementById('v3Disc');
    if (el) return el;
    var area = document.getElementById('mapArea'); if (!area) return null;
    el = document.createElement('div');
    el.id = 'v3Disc'; el.className = 'v3-disc'; el.setAttribute('role', 'note');
    var sk = document.getElementById('sizekey');
    if (sk && sk.parentNode === area) sk.insertAdjacentElement('afterend', el); else area.appendChild(el);
    return el;
  }
  V3.syncDisc = function () {
    var el = discEl(); if (!el) return;
    var a = asOf(mapView()), conf = confText().split(' · ')[0];
    // "Confidential" leads the chip at ≤ 1100 px, where the header lockup that carries it is hidden (v3-map.css)
    var html = INFO + '<b class="cf">' + U.esc(conf) + '</b><span class="d cf" aria-hidden="true"> · </span>' +
      '<b>' + U.esc(String(a.caveat).replace(/\.\s*$/, '')) + '</b><span class="d" aria-hidden="true"> · </span><span>' + U.esc(String(a.stamp).replace(' · ', ' ')) + '</span>';
    if (el.innerHTML !== html) el.innerHTML = html;
    el.setAttribute('aria-label', conf + '. ' + a.caveat + ' ' + a.stamp.replace(' · ', ' '));
  };
  discEl();
  RBX.bus.on('view', V3.syncDisc);
  RBX.bus.on('ready', V3.syncDisc);
  if (RBX.rail && RBX.rail.render) {
    var railRender0 = RBX.rail.render;
    RBX.rail.render = function () { var r = railRender0.apply(this, arguments); V3.syncDisc(); return r; };
  }
  // the key moves with the panel; the sea labels it hides depend on where it sits
  var autoRail = false, inAuto = false;
  if (RBX.rail && RBX.rail.setCollapsed) {
    var coll0 = RBX.rail.setCollapsed;
    RBX.rail.setCollapsed = function (c) {
      if (!inAuto) autoRail = false;                           // the reader folded or opened the panel: theirs from now on
      var r = coll0.apply(this, arguments);
      V3.syncDisc();
      if (Sk && Sk.clearLabels) setTimeout(Sk.clearLabels, 320);
      // the reader opened the panel beside a sheet (a tablet's narrow strip of map): the selected site comes back
      // out from under it (not when a closing sheet unfolds the panel, so the camera never moves as it closes)
      if (!inAuto && !c) reframeSoon();
      return r;
    };
  }

  // ------------------------------------------------------------------ tablets: a sheet folds the panel (761–1050 px)
  // Panel (300) + sheet (352) would leave an 88–400 px sliver of map with the chrome piled into it, so opening a sheet
  // there folds the panel, and closing it unfolds the panel again (unless the reader moved it meanwhile). While
  // folded beside a sheet, the disclaimer line sits in the sheet's foot instead of the chip (v3-sheet.js / .css).
  var TABLET_MAX = 1050;
  function railAuto(c) { inAuto = true; try { RBX.rail.setCollapsed(c); } finally { inAuto = false; } }
  function autoFold() {
    var app = document.getElementById('app');
    if (U.isMobile() || window.innerWidth > TABLET_MAX || RBX.state.railCollapsed || RBX.state.view === 'ppa' || (app && app.classList.contains('presenting'))) return;
    railAuto(true); autoRail = true;
  }
  var Sh = RBX.sheet;
  if (Sh && Sh.open && RBX.rail && RBX.rail.setCollapsed) {
    ['open', 'chooser', 'panel'].forEach(function (fn) {
      var f0 = Sh[fn];
      Sh[fn] = function () {
        var was = Sh.isOpen(), r = f0.apply(this, arguments);
        if (!was && Sh.isOpen()) autoFold();
        return r;
      };
    });
    var close0 = Sh.close;
    Sh.close = function () {
      // unfold first, so focus can return to anything inside the panel
      if (autoRail && Sh.isOpen()) { autoRail = false; if (RBX.state.railCollapsed) railAuto(false); }
      return close0.apply(this, arguments);
    };
  }
  // a rotation or a resize into tablet width with a sheet already open folds the panel as opening one there does (an
  // iPad turned to portrait otherwise kept a 140 px strip of map, and a phone turned to landscape lost the disclaimer
  // with the sheet foot hidden); back above 1050 px, a panel folded that way opens again
  var mqTab = window.matchMedia ? window.matchMedia('(min-width: 761px) and (max-width: ' + TABLET_MAX + 'px)') : null;
  function onTab(e) {
    if (!Sh || !Sh.isOpen || !Sh.isOpen()) return;
    if (e.matches) {
      var was = RBX.state.railCollapsed;
      autoFold();
      if (!was && RBX.state.railCollapsed) reframeSoon();
    } else if (autoRail && window.innerWidth > TABLET_MAX) {
      autoRail = false;
      if (RBX.state.railCollapsed) { railAuto(false); reframeSoon(); }
    }
  }
  if (mqTab) { if (mqTab.addEventListener) mqTab.addEventListener('change', onTab); else if (mqTab.addListener) mqTab.addListener(onTab); }
  /** Once the panel has come to rest (0.32 s), keep the open sheet's site in the map left between the panel and the
      sheet: ensureVisible moves the camera only when the site is covered or off-screen. */
  function reframeSoon() {
    setTimeout(function () {
      var row = Sh && Sh.isOpen && Sh.isOpen() && Sh.current && Sh.current();
      if (row && !U.isMobile() && Mc && Mc.ensureVisible) Mc.ensureVisible(row);
    }, 340);
  }
  // the camera frames the site between the panels where they come to rest: core mapctl measures them mid-slide (the
  // folding panel at full width, the sheet still off-screen), which jammed the selected site against the sheet
  var Mc = RBX.mapctl;
  if (Mc && Mc.obstruction) {
    var obs0 = Mc.obstruction;
    Mc.obstruction = function () {
      var o = obs0.apply(this, arguments), area = document.getElementById('mapArea');
      if (U.isMobile() || !area) return o;
      var a = area.getBoundingClientRect(), rl = document.getElementById('rail'), sh = document.getElementById('sheet');
      if (o.left && shown(rl)) o.left = restX(rl).right - a.left;
      if (shown(sh)) o.right = Math.max(0, a.right - restX(sh).left);
      return o;
    };
  }

  // ------------------------------------------------------------------ keep the chrome in step with the panels
  var fitAll = function () { V3.fitSizeKey(); tipClear(); if (Sk && Sk.clearLabels) Sk.clearLabels(); };
  window.addEventListener('resize', U.rafThrottle(fitAll));
  RBX.bus.on('ready', fitAll);
  RBX.bus.on('mapready', function () {
    var app = document.getElementById('app');
    // sheet open / panel folded / presenting: refit before the frame paints, then again once the slides settle
    if (app && window.MutationObserver) new MutationObserver(fitAll).observe(app, { attributes: true, attributeFilter: ['class'] });
    ['mapCtl', 'sizekey'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('transitionend', function (e) { if (e.target === el && /^(left|right|bottom)$/.test(e.propertyName)) fitAll(); });
    });
    var sh = document.getElementById('sheet'); if (sh) sh.addEventListener('animationend', function (e) { if (e.target === sh) fitAll(); });
  });

  // ------------------------------------------------------------------ hover tooltip: clear of an open sheet, panel money (§1.2)
  // core layers.showTip only flips against the map's own right edge; with a sheet open (and the pointer still on the
  // marker just clicked) the tip is flipped to the left of the pointer instead of sitting on the sheet.
  var tipAt = null;
  function tipClear() {
    var tip = document.getElementById('tip'), sh = document.getElementById('sheet'), area = document.getElementById('mapArea');
    if (!tipAt || !tip || tip.hidden || !area || U.isMobile() || !shown(sh)) return;
    var m = /translate\(\s*([-\d.]+)px\s*,\s*([-\d.]+)px\s*\)/.exec(tip.style.transform || ''); if (!m) return;
    var edge = restX(sh).left - area.getBoundingClientRect().left - 8, w = tip.offsetWidth;
    if (+m[1] + w <= edge) return;
    tip.style.transform = 'translate(' + Math.max(4, tipAt.x - 12 - w) + 'px,' + m[2] + 'px)';
  }
  if (RBX.layers && RBX.layers.showTip) {
    var tip0 = RBX.layers.showTip;
    RBX.layers.showTip = function (row, pt) {
      var r = tip0.apply(this, arguments);
      tipAt = row && pt ? { x: pt.x, y: pt.y } : null;
      tipClear();
      return r;
    };
  }
  // "£2.90M TCV" (two decimals, from the investor model) becomes "£2.9M TCV", as in the panel and the sheet
  if (RBX.hooks.tooltip && RBX.inv && RBX.inv.money2) {
    var tipText0 = RBX.hooks.tooltip;
    RBX.hooks.tooltip = function (r) {
      var s = tipText0.apply(this, arguments);
      return r && r.tcv != null && (r.kind === 'hydro' || (r.kind === 'sam' && r.pr)) ? String(s).replace(RBX.inv.money2(r.tcv), U.abbr(r.tcv)) : s;
    };
  }

  // ------------------------------------------------------------------ selected site: ring, halo and a soft wash (§8.2)
  var SEL_WASH = { paper: 'rgba(21,96,130,0.14)', night: 'rgba(131,203,235,0.16)' };
  var SEL_HALO = { paper: 'rgba(255,255,255,0.9)', night: 'rgba(7,18,26,0.85)' };
  var KINDS = ['sam', 'hydro', 'tam'];
  function selRadius(kind, add) {
    var L = RBX.layers;
    if (kind !== 'tam') return L.R(L.SIZE[kind], add);
    // the TAM ring follows the glyph scale (the same stops as core layers.js tamRing)
    var e = ['interpolate', ['exponential', 1.5], ['zoom']];
    [4, 6, 8, 11, 14].forEach(function (z) { e.push(z, ['+', add, ['*', L.tamScaleAt(z), ['get', 'hr']]]); });
    return e;
  }
  function selTheme() {
    var m = RBX.map; if (!m) return;
    var th = RBX.state.theme === 'night' ? 'night' : 'paper';
    KINDS.forEach(function (k) {
      try {
        if (m.getLayer('v3-sel-' + k + '-wash')) m.setPaintProperty('v3-sel-' + k + '-wash', 'circle-stroke-color', SEL_WASH[th]);
        if (m.getLayer('v3-sel-' + k + '-halo')) m.setPaintProperty('v3-sel-' + k + '-halo', 'circle-stroke-color', SEL_HALO[th]);
      } catch (e) { /* style rebuilt */ }
    });
  }
  function selLayers(map) {
    if (!RBX.layers || !RBX.layers.R || !map.getSource('sel')) return;
    var th = RBX.state.theme === 'night' ? 'night' : 'paper';
    KINDS.forEach(function (k) {
      var ring = 'sel-' + k; if (!map.getLayer(ring)) return;
      var f = ['==', ['get', 'kind'], k];
      try {
        // ring 2.5 px (R + 4 … R + 6.5), then a 2 px halo and a 9 px wash outside it, both drawn under the ring
        map.setPaintProperty(ring, 'circle-stroke-width', 2.5);
        if (map.getLayer(ring + '-halo')) map.setPaintProperty(ring + '-halo', 'circle-stroke-opacity', 0);
        if (!map.getLayer('v3-' + ring + '-wash')) {
          map.addLayer({ id: 'v3-' + ring + '-wash', type: 'circle', source: 'sel', filter: f, paint: {
            'circle-radius': selRadius(k, 6.5), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 9, 'circle-stroke-color': SEL_WASH[th] } }, ring);
        }
        if (!map.getLayer('v3-' + ring + '-halo')) {
          map.addLayer({ id: 'v3-' + ring + '-halo', type: 'circle', source: 'sel', filter: f, paint: {
            'circle-radius': selRadius(k, 6.5), 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 2, 'circle-stroke-color': SEL_HALO[th] } }, ring);
        }
      } catch (e) { /* the core ring keeps working without the extra layers */ }
    });
  }
  RBX.bus.on('mapready', function (map) {
    selLayers(map);
    map.on('styledata', function () { if (RBX.layers.ready && !map.getLayer('v3-sel-sam-wash')) selLayers(map); });
  });
  RBX.bus.on('theme', function () { setTimeout(selTheme, 0); });

  // hollow rings stay hollow: investor-v3.js keeps the SAM shadow off the "Awaiting BM figure" rings; the Hydro
  // "Unverified" rings (c = 3) are hollow too, so their soft shadow would read as a grey fill
  if (RBX.skin && RBX.skin.syncShadows) {
    var shadows0 = RBX.skin.syncShadows;
    RBX.skin.syncShadows = function () {
      shadows0.apply(this, arguments);
      var m = RBX.map;
      if (!m || !m.getLayer || !m.getLayer('hydro-shadow')) return;
      try { m.setFilter('hydro-shadow', ['all', RBX.filters.expr('hydro'), ['!=', ['get', 'c'], 3]]); } catch (e) { /* style rebuilt */ }
    };
  }

  // ------------------------------------------------------------------ attribution: the compact (i) on desktop too (§8.2)
  RBX.bus.on('ready', function () {
    if (U.isMobile()) return;
    var at = document.querySelector('.maplibregl-ctrl-attrib.maplibregl-compact');
    if (at) at.classList.remove('maplibregl-compact-show');
  });

  // ------------------------------------------------------------------ PNG export band (§11)
  // The skin draws the teal band, the sky rule, the wordmark, "no Watt wasted", the divider and the product name (it
  // is called with an empty kicker). Its quarter-circle would sit behind the right-hand text, so it is painted over
  // and redrawn at the far right; then one right-aligned line on the product name's baseline: the confidentiality mark
  // with the as-of stamp and the disclaimer (which appears exactly once). No kicker: it belonged to the headline block
  // the owner removed; the card title and its measure name the view.
  var BAND = '#156082', SKY = '#83CBEB';
  var CARD_X = 28, CARD_W = 392, PAD = 22, FOOT = 46;        // core composite's card frame (x, width, padding) and footer
  var strip = null;                                         // the map under the card, copied while the band is drawn
  V3.exportLines = function (view, vc) {
    var a = asOf(view), conf = confText(), rest = ' · ' + a.line;
    return { kicker: String((vc && vc.kicker) || '').toUpperCase(), conf: conf, rest: rest, text: conf + rest };
  };
  if (RBX.brand && RBX.brand.exportBand) {
    var band0 = RBX.brand.exportBand;
    RBX.brand.exportBand = function (g, o) {
      var vc = o.vc || {};
      // core draws the band after the map and the annotations and before its card: keep the strip the card covers
      strip = null;
      try {
        var c = g.canvas, k = c.width / o.W, sw = Math.min(c.width, Math.ceil((CARD_X + CARD_W + 60) * k));
        var sc = document.createElement('canvas'); sc.width = sw; sc.height = c.height;
        sc.getContext('2d').drawImage(c, 0, 0, sw, c.height, 0, 0, sw, c.height);
        strip = { cv: sc, k: k, top: o.TOP };
      } catch (e) { strip = null; }
      band0.call(this, g, Object.assign({}, o, { vc: Object.assign({}, vc, { kicker: '' }) }));
      var W = o.W, TOP = o.TOP, UI = o.UI, xr = W - 96, ln = V3.exportLines(mapView(), vc);
      g.save();
      g.beginPath(); g.rect(0, 0, W, TOP); g.clip();
      // paint over the skin's arc (centre W − 70, TOP + 30, r 78: x W − 148 … W − 70), keeping the sky rule
      g.fillStyle = BAND; g.fillRect(W - 152, 0, 152, TOP - 3);
      g.fillStyle = 'rgba(131,203,235,.22)'; g.beginPath(); g.arc(W, TOP + 8, 64, 0, Math.PI * 2); g.fill();
      g.fillStyle = SKY; g.fillRect(W - 152, TOP - 3, 152, 3);
      g.textBaseline = 'alphabetic'; g.textAlign = 'left';
      if ('letterSpacing' in g) g.letterSpacing = '0px';
      // Confidential · investor use only · Model · 16 Jun 2026 · Indicative; not investment advice.
      g.font = '600 11.5px ' + UI; var w1 = g.measureText(ln.conf).width;
      g.font = '400 11.5px ' + UI; var w2 = g.measureText(ln.rest).width;
      var x0 = xr - w1 - w2, yb = Math.round(TOP / 2) + 5;
      g.font = '600 11.5px ' + UI; g.fillStyle = '#FFFFFF'; g.fillText(ln.conf, x0, yb);
      g.font = '400 11.5px ' + UI; g.fillStyle = 'rgba(255,255,255,.86)'; g.fillText(ln.rest, x0 + w1, yb);
      g.restore();
    };
  }

  // ------------------------------------------------------------------ PNG export card: the same figures as the panel (§11)
  // core/js/export.js draws an editorial card (the kicker, views[v].headline, three KPI cells, a legend) that v3 cannot
  // shape from outside, so v3 draws its own card in the same frame: the strip kept by the band wrapper is put back
  // over the core card and the v3 card drawn on it. The card carries
  //   - a quiet title: the view's name ("Peaker market", "Stranded hydro") and its measure as a small label
  //     (config png[v].measure; the "shown" form under any filter). No kicker (the band carries it once) and no
  //     headline sentence: the rail headline block is surplus, and a build-time sentence would contradict a filter;
  //   - views[v].kpis.slice(0, 3) over the sites shown, resolved by V3.exportKpis: captions with their numbers
  //     ("of 129"), the TAM "≥ 10 MW" cell as that TCV Potential, labels that fit their 116 px column; money in the
  //     page grammar (full-size £, small magnitude letter), sized down only if a figure would reach the divider;
  //   - the legend over the sites shown: SAM tiers count priced sites (the panel's figure; tiers + "Awaiting BM
  //     figure" = the sites shown), TAM fuels in the panel's order with the rest as "Other fuels", and a row with
  //     no site shown (a hidden tier or fuel) is left out rather than listed as 0.
  // The footer names the view's own sources and its model / registers date (config png[v].sources, band.asOf), so
  // the PNG carries one date, the one in its band.
  var K = RBX.kpi, E = RBX.exporter, I = RBX.inv;
  var PNG_SHORT = {
    sam: [['TCV · Year 5', 'TCV shown · Year 5'], ['With treasury'], ['Priced sites']],
    hydro: [['TCV · Year 5', 'TCV shown · Year 5'], ['With treasury'], ['Sites']],
    tam: [['TCV potential', 'TCV potential shown'], ['TCV ≥ 10 MW'], ['Sites']]
  };
  function bigRows(rows) { return rows.filter(function (r) { return r.big && r.bt > 0; }); }
  if (K && K.metrics && I && I.tcvPot) {
    K.metrics.v3PotBig = function (rows) { var b = bigRows(rows); return { v: b.length ? I.tcvPot(b) : 0, d: 0, f: U.abbr }; };
  }
  V3.exportKpis = function (view, kpis) {
    var rows = RBX.filters.active(view), all = RBX.data.rows[view] || [], filt = RBX.filters.anyHidden ? RBX.filters.anyHidden(view) : false;
    var g = document.createElement('canvas').getContext('2d'), UI = getComputedStyle(doc).getPropertyValue('--font-ui').trim() || 'sans-serif';
    g.font = '600 9.5px ' + UI;
    var colW = (392 - 44) / 3, adOnly = (RBX.state.hidden.scale || new Set()).has(1), nBig = bigRows(rows).length;
    var list = (kpis || []).filter(function (k) { return !(k.role === 'sub' && k.metric === 'tcvPot' && !nBig); }).slice(0, 3);
    return list.map(function (k, i) {
      var o = Object.assign({}, k), fits = function (s) { return s && g.measureText(String(s).toUpperCase()).width <= colW - (i ? 12 : 0) - 8; };
      var sh = ((PNG_SHORT[view] || [])[(kpis || []).indexOf(k)] || []), useF = i === 0 && filt && k.labelFiltered;
      var label = useF ? k.labelFiltered : k.label, short = useF ? sh[1] || sh[0] : sh[0];
      o.label = [k.pngLabel, label, short, k.labelShort].filter(fits)[0] || short || label;
      if (k.role === 'sub' && k.metric === 'tcvPot') {
        o.metric = 'v3PotBig';
        o.caption = 'of it, ' + U.int(nBig) + (nBig === 1 ? ' site' : ' sites');
      } else if (k.metric === 'tcvPot' && V3.potCaption) {     // "AD-scale only", the capacity range shown, or "all sizes"
        o.caption = V3.potCaption(view, rows, k);
      } else {
        var m = (K.metrics[k.metric] || K.metrics.count)(rows);
        o.caption = U.template(k.caption || '', { known: U.int(m.known), n: U.int(rows.length), total: U.int(all.length) });
      }
      return o;
    });
  };
  function css(n) { return getComputedStyle(doc).getPropertyValue(n).trim(); }
  function mwText(s) { var kw = U.sum(s, function (r) { return r.kw; }); return U.int(s.length) + ' · ' + (kw >= 100000 ? U.int(kw / 1000) : U.num(kw / 1000, 1)) + ' MW'; }
  /** Legend rows for the card, over the sites shown: { shape: dot|ring|tri, col, label, right }; empty rows left out. */
  V3.exportLegend = function (view) {
    var P = RBX.theme.pal(), rows = RBX.filters.active(view), lab = cfg().labels || {}, out = [];
    function add(shape, col, label, sub, right) { if (sub.length) out.push({ shape: shape, col: col, label: label, right: right ? right(sub) : mwText(sub) }); }
    function of(f) { return rows.filter(f); }
    function count(s) { return U.int(s.length); }
    if (view === 'sam') {
      var aw = ((cfg().legend || {}).sam || {}).awaiting;
      [1, 2, 3, 4, 5].forEach(function (t) { add('dot', P.tier[t - 1], lab.tiers[t], of(function (r) { return r.t === t && !(aw && r.pr === 0); })); });
      if (aw) add('ring', P.ink2, String(aw), of(function (r) { return r.pr === 0; }));
    } else if (view === 'tam') {
      if (RBX.theme.tamMode() === 'fuels') {
        var order = RBX.legend && RBX.legend.fuelOrder ? RBX.legend.fuelOrder() : (lab.fuels || []).map(function (f, j) { return j; });
        order.slice(0, 6).forEach(function (j) { add('ring', P.fuel[j], lab.fuels[j], of(function (r) { return r.fu === j; })); });
        var rest = order.slice(6).filter(function (j) { return rows.some(function (r) { return r.fu === j; }); });
        if (rest.length === 1) add('ring', P.fuel[rest[0]], lab.fuels[rest[0]], of(function (r) { return r.fu === rest[0]; }));
        else if (rest.length) add('ring', P.ink3, 'Other fuels (' + rest.length + ')', of(function (r) { return rest.indexOf(r.fu) >= 0; }));
      } else {
        [0, 1, 2, 3].forEach(function (f) { add('ring', P.fam[f], lab.families[f], of(function (r) { return r.fam === f; })); });
      }
      add('tri', P.ink2, 'RO accredited', of(function (r) { return r.ro; }), count);
      add('ring', P.ink2, 'FiT accredited', of(function (r) { return !r.ro; }), count);
    } else if (view === 'hydro') {
      [0, 1, 2, 3].forEach(function (c) {
        add(c === 3 ? 'ring' : 'dot', c === 3 ? P.unv : P.hyd[c], c === 3 ? 'Unverified' : lab.conf[c] + ' confidence', of(function (r) { return r.c === c; }),
          function (s) { return count(s) + ' · ' + U.int(U.sum(s, function (r) { return r.kw; })) + ' kW'; });
      });
    }
    return out;
  };
  /** A cell's figure in the page's money grammar: '£327.4' + magnitude 'M'; a metric's own unit ('90.5<small>MW</small>'). */
  function cellParts(mm, o) {
    var plain = function (t) { return String(t == null ? '' : t).replace(/<[^>]+>/g, '').trim(); };
    var p = (mm.f ? String(mm.f(mm.v)) : U.num(mm.v, mm.d)).split(/<small>|<\/small>/), v = plain(p[0]), unit = o.unit || plain(p[1]);
    var m = !unit && /^(-?£[\d.,]+)\s*(k|M|bn)$/.exec(v);
    return m ? { v: m[1], mag: m[2], unit: '' } : { v: v, mag: '', unit: unit };
  }
  function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function glyph(g, shape, x, y, r, col) {
    g.save(); g.beginPath();
    if (shape === 'tri') { var R = r * 1.22, y0 = y + r * 0.1; g.moveTo(x, y0 - R); g.lineTo(x + R * 0.866, y0 + R * 0.5); g.lineTo(x - R * 0.866, y0 + R * 0.5); g.closePath(); }
    else g.arc(x, y, r, 0, Math.PI * 2);
    if (shape === 'dot') { g.fillStyle = col; g.fill(); } else { g.strokeStyle = col; g.lineWidth = 1.8; g.stroke(); }
    g.restore();
  }
  function clip(g, s, w) { s = String(s || ''); if (g.measureText(s).width <= w) return s; while (s.length > 1 && g.measureText(s + '…').width > w) s = s.slice(0, -1); return s.replace(/\s+$/, '') + '…'; }
  /** The v3 card (and its shadow) for the current view on a transparent canvas the size of the kept strip. */
  V3.exportCard = function (view, kpis, sw, sh, k, top) {
    var vc = (cfg().views || {})[view] || {}, png = (cfg().png || {})[view] || {}, filt = RBX.filters.anyHidden(view), rows = RBX.filters.active(view);
    var cv = document.createElement('canvas'); cv.width = sw; cv.height = sh;
    var g = cv.getContext('2d'); g.scale(k, k); g.textBaseline = 'alphabetic';
    var UI = css('--font-ui') || 'sans-serif', ink1 = css('--ink-1'), ink2 = css('--ink-2'), ink3 = css('--ink-3'), rule = css('--rule');
    var night = RBX.state.theme === 'night', surf = night ? css('--surface-0-solid') : css('--surface-1') || '#fff';
    var title = vc.label || '', measure = (filt && png.measureFiltered) || png.measure || '', leg = V3.exportLegend(view);
    var cx = CARD_X, cy = top + 22, inner = CARD_W - PAD * 2, y = cy + PAD;
    var chH = PAD + 16 + (measure ? 19 : 0) + 16 + (kpis.length ? 72 : 0) + (leg.length ? 18 + leg.length * 25 + 12 : 0) + PAD;
    g.save(); g.shadowColor = 'rgba(0,0,0,' + (night ? 0.45 : 0.14) + ')'; g.shadowBlur = 24; g.shadowOffsetY = 6;
    g.fillStyle = surf; rr(g, cx, cy, CARD_W, chH, 16); g.fill(); g.restore();
    g.strokeStyle = rule; g.lineWidth = 1; rr(g, cx + 0.5, cy + 0.5, CARD_W - 1, chH - 1, 16); g.stroke();
    // title: the view's name, then its measure small
    y += 16; g.fillStyle = ink1; g.font = '600 18px ' + UI; g.fillText(clip(g, title, inner), cx + PAD, y);
    if (measure) { y += 19; g.fillStyle = ink2; g.font = '400 12.5px ' + UI; g.fillText(clip(g, measure, inner), cx + PAD, y); }
    y += 16;
    if (kpis.length) {
      g.fillStyle = ink1; g.fillRect(cx + PAD, y, inner, 1);
      var cwk = inner / kpis.length;
      kpis.forEach(function (o, i) {
        var mm = (K.metrics[o.metric] || K.metrics.count)(rows), x = cx + PAD + i * cwk + (i ? 12 : 0), room = cwk - (i ? 12 : 0) - 8;
        if (i) { g.fillStyle = rule; g.fillRect(cx + PAD + i * cwk, y + 8, 1, 56); }
        g.fillStyle = ink3; g.font = '600 9.5px ' + UI; g.fillText(clip(g, String(o.label).toUpperCase(), room + 4), x, y + 20);
        var p = cellParts(mm, o), sz = 26;
        var width = function (s) {
          g.font = '500 ' + s + 'px ' + UI; var w = g.measureText(p.v).width;
          if (p.mag) { g.font = '400 ' + (s * 0.62).toFixed(1) + 'px ' + UI; w += 1.5 + g.measureText(p.mag).width; }
          if (p.unit) { g.font = '500 12px ' + UI; w += 4 + g.measureText(p.unit).width; }
          return w;
        };
        while (sz > 18 && width(sz) > room) sz -= 1;
        g.fillStyle = ink1; g.font = '500 ' + sz + 'px ' + UI; g.fillText(p.v, x, y + 50);
        var vx = x + g.measureText(p.v).width;
        if (p.mag) { g.font = '400 ' + (sz * 0.62).toFixed(1) + 'px ' + UI; g.fillText(p.mag, vx + 1.5, y + 50); vx += 1.5 + g.measureText(p.mag).width; }
        if (p.unit) { g.fillStyle = ink2; g.font = '500 12px ' + UI; g.fillText(p.unit, vx + 4, y + 50); }
        g.fillStyle = ink3; g.font = '400 11px ' + UI; g.fillText(clip(g, U.template(o.caption || '', { known: U.int(mm.known) }), room + 4), x, y + 66);
      });
      y += 72;
    }
    if (leg.length) { y += 6; g.fillStyle = ink1; g.fillRect(cx + PAD, y, inner, 1); y += 12; }
    leg.forEach(function (l) {
      y += 25;
      glyph(g, l.shape, cx + PAD + 6, y - 5, 5.5, l.col);
      g.font = '500 12px ' + UI; var rw = g.measureText(l.right).width;
      g.fillStyle = ink1; g.font = '500 13px ' + UI; g.fillText(clip(g, l.label, inner - 22 - rw - 12), cx + PAD + 22, y);
      g.textAlign = 'right'; g.fillStyle = ink2; g.font = '500 12px ' + UI; g.fillText(l.right, cx + CARD_W - PAD, y); g.textAlign = 'left';
    });
    return cv;
  };
  if (E && E.composite) {
    var comp0 = E.composite;
    E.composite = function () {
      var view = mapView(), c = cfg(), vc = (c.views || {})[view], d = c.drawer || (c.drawer = {}), png = (c.png || {})[view] || {};
      var saved = vc ? { kpis: vc.kpis, headline: vc.headline } : null, dSaved = { asOf: d.asOf, sources: d.sources }, kp = [];
      if (vc && saved.kpis) { try { kp = V3.exportKpis(view, saved.kpis); } catch (e) { kp = saved.kpis.slice(0, 3); } }
      var cv;
      strip = null;
      try {
        // the core card and footer read these for the duration of the (synchronous) composite only
        if (vc) { vc.kpis = kp; vc.headline = ''; }
        d.asOf = asOf(view).stamp;
        if (png.sources) d.sources = png.sources;
        cv = comp0.apply(this, arguments);
      } finally {
        if (vc) { vc.kpis = saved.kpis; vc.headline = saved.headline; }
        d.asOf = dSaved.asOf; d.sources = dSaved.sources;
      }
      var st = strip; strip = null;
      if (cv && st && vc) {
        try {
          var H = cv.height / st.k, top = st.top, y0 = Math.round(top * st.k), y1 = Math.round((H - FOOT) * st.k);
          var card = V3.exportCard(view, kp, st.cv.width, st.cv.height, st.k, top);
          var g = cv.getContext('2d');
          g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
          g.drawImage(st.cv, 0, y0, st.cv.width, y1 - y0, 0, y0, st.cv.width, y1 - y0);
          g.drawImage(card, 0, y0, st.cv.width, y1 - y0, 0, y0, st.cv.width, y1 - y0);
          g.restore();
        } catch (e) { /* the core card stays */ }
      }
      return cv;
    };
  }

  // ------------------------------------------------------------------ PNG export: the basemap at the image's resolution (§11)
  // core composite cover-fits the map canvas into the 1600 × 900 @2x image, so a 1× screen's canvas (1440 px wide)
  // was stretched 2.2× and the basemap labels and markers went soft beside the card's sharp text. For the one frame
  // it grabs, the map renders at the pixel ratio the image needs (at most 3), then follows the screen again (null
  // clears the override: core never sets one, and a number would stop it tracking devicePixelRatio). If no sharp
  // frame comes (core's grab gives up after 3 s), the screen's own frame is grabbed instead: never an image without
  // its map.
  var EXP_W = 1600, EXP_MAP_H = 900 - 64 - FOOT;               // core composite: image width, map between band and footer
  if (E && E.grabMap) {
    var grab0 = E.grabMap;
    E.grabMap = function (cb) {
      var m = RBX.map, box = document.getElementById('map'), self = this, args = arguments;
      if (!m || !box || !m.setPixelRatio || !m.getPixelRatio || !box.clientWidth || !box.clientHeight) return grab0.apply(self, args);
      var need = Math.min(3, 2 * Math.max(EXP_W / box.clientWidth, EXP_MAP_H / box.clientHeight));
      if (need <= m.getPixelRatio() * 1.2) return grab0.apply(self, args);   // a stretch under 1.2× stays crisp (2× screens)
      var started = false, restored = false;
      var restore = function () { if (restored) return; restored = true; try { m.setPixelRatio(null); } catch (e) { /* stays sharp */ } };
      var go = function () {
        if (started) return; started = true;
        var back = function (cv) { restore(); if (cv) cb(cv); else grab0.call(self, cb); };
        try { grab0.call(self, back); } catch (e) { back(null); }
      };
      try { m.setPixelRatio(need); } catch (e) { restore(); return grab0.apply(self, args); }
      m.once('idle', go);
      m.triggerRepaint();
      setTimeout(go, 2500);                                    // 'idle' never comes while something keeps repainting
    };
  }

  // ------------------------------------------------------------------ downloads: file names without the internal "v3"
  // core names every download after config.storageKey ('rbx-investor-atlas-v3-2' → 'renewablox-investor-atlas-v3-2-…').
  // The key stays (it keeps the v2 and v3 saved state apart, and its '-2' retired the saved light-theme choices when
  // the default became night); the files an investor receives drop the version label.
  // core's PNG and CSV downloads both click an <a download> attached to the page, so one capture-phase listener
  // renames them before the browser reads the attribute.
  V3.fileName = function (name) {
    var base = String(cfg().storageKey || '').replace(/^rbx-/, 'renewablox-'), plain = base.replace(/-v\d[\w-]*$/, '');
    name = String(name || '');
    return plain !== base && name.indexOf(base + '-') === 0 ? plain + name.slice(base.length) : name;
  };
  document.addEventListener('click', function (e) {
    var a = e.target;
    if (!a || a.tagName !== 'A' || !a.hasAttribute('download')) return;
    var n = V3.fileName(a.getAttribute('download'));
    if (n !== a.getAttribute('download')) a.setAttribute('download', n);
  }, true);

  // ------------------------------------------------------------------ CSV: the model date and the disclaimer
  // Row 1 stays the confidentiality mark (config.csvHeader); row 2 carries the file's as-of stamp and "Indicative;
  // not investment advice." (config.csvNote[sam|tam|hydro|register]), since the CSVs list per-site £ figures.
  if (E && E.csv) {
    var csv0 = E.csv;
    E.csv = function (cols) {
      var out = csv0.apply(this, arguments), notes = cfg().csvNote || {};
      var kind = Object.keys(E.cols || {}).filter(function (k) { return E.cols[k] === cols; })[0], note = notes[kind];
      var i = out.indexOf('\r\n');
      if (!cfg().csvHeader || !note || i < 0) return out;
      note = String(note);
      if (/[",\n\r]/.test(note)) note = '"' + note.replace(/"/g, '""') + '"';
      return out.slice(0, i + 2) + note + '\r\n' + out.slice(i + 2);
    };
  }
})();
