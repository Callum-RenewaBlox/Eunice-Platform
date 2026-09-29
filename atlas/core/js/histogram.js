/* RBX.hist: capacity histogram-slider with presets (spec 6.3d). 26 log bins over the view's universe (bar
   height ∝ √count, faceted: counts ignore the kW range itself), two keyboard-accessible range thumbs snapped to
   2 significant figures, presets All sizes · Over 1 MW (> 1000 kW) · Under 1 MW (≤ 1000 kW). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var Hs = RBX.hist = {};
  var NB = 26, DOM = {};
  var open = null;   // disclosure state (null = auto by viewport height)

  function domain(view) {
    if (DOM[view]) return DOM[view];
    var vals = (RBX.data.rows[view] || []).map(RBX.filters.capOf).filter(function (v) { return v > 0; });
    var lo = Math.log10(Math.min.apply(null, vals)), hi = Math.log10(Math.max.apply(null, vals));
    return (DOM[view] = [lo, hi, Math.pow(10, lo), Math.pow(10, hi)]);
  }
  function toKw(view, s) { var d = domain(view); return Math.pow(10, d[0] + (d[1] - d[0]) * s / 1000); }
  function toS(view, kw) { var d = domain(view); if (kw <= 0) return 0; return Math.max(0, Math.min(1000, (Math.log10(kw) - d[0]) / (d[1] - d[0]) * 1000)); }
  function preset(view) {
    var k = RBX.state.kw[view];
    if (!k) return 'all';
    if (k[0] === 1000.001 && k[1] === Infinity) return 'over';
    if (k[0] === 0 && k[1] === 1000) return 'under';
    return '';
  }
  function readout(view) {
    var k = RBX.state.kw[view], d = domain(view);
    if (!k) return 'All sizes';
    var p = preset(view);
    if (p === 'over') return 'Over 1 MW';
    if (p === 'under') return '1 MW and under';
    var lo = Math.max(k[0], d[2]), hi = Math.min(k[1], d[3]);
    if (lo >= 1000 && hi >= 1000) return U.num(lo / 1000, 1) + '–' + U.num(hi / 1000, 1) + ' MW';
    return U.cap(lo) + '–' + U.cap(hi);
  }
  function expanded() { return open != null ? open : window.innerHeight > 840 && !U.isMobile(); }

  Hs.html = function (view) {
    var vc = RBX.config.views[view] || {}, d = domain(view), p = preset(view), ex = expanded();
    return '<section class="r-sec" id="capSec" aria-labelledby="capTitle"><div class="r-sec-h"><h3 class="r-sec-t" id="capTitle">' + U.esc(vc.capTitle || 'Capacity') + '</h3>' +
      '<span class="cap-read" id="capRead">' + U.esc(readout(view)) + '</span></div>' +
      '<div class="seg" role="group" aria-label="Capacity presets" id="capSeg"><span class="seg-thumb" aria-hidden="true"></span>' +
      '<button type="button" data-preset="all" aria-pressed="' + (p === 'all') + '">All sizes</button>' +
      '<button type="button" data-preset="over" aria-pressed="' + (p === 'over') + '">Over 1 MW</button>' +
      '<button type="button" data-preset="under" aria-pressed="' + (p === 'under') + '" title="1 MW and under">Under 1 MW</button></div>' +
      '<button type="button" class="hist-toggle" id="histToggle" aria-expanded="' + ex + '" aria-controls="hist"><svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M7.5 4.5 13 10l-5.5 5.5"/></svg>Distribution and custom range</button>' +
      '<div class="hist" id="hist"' + (ex ? '' : ' hidden') + '><svg id="histSvg" aria-hidden="true"></svg>' +
      '<div class="range"><div class="track"></div><div class="fill" id="capFill"></div>' +
      '<label class="sr-only" for="capLo">Minimum capacity</label><input type="range" id="capLo" min="0" max="1000" step="1" value="0">' +
      '<label class="sr-only" for="capHi">Maximum capacity</label><input type="range" id="capHi" min="0" max="1000" step="1" value="1000"></div>' +
      '<div class="hist-ends"><span>' + U.cap(U.sig2(d[2])) + '</span><span>' + U.cap(U.sig2(d[3])) + '</span></div></div></section>';
  };

  Hs.draw = function () {
    var view = RBX.state.view, svg = document.getElementById('histSvg');
    if (!svg || svg.closest('[hidden]')) return;
    var W = svg.clientWidth || 300, H = 34, d = domain(view), bins = new Array(NB).fill(0);
    (RBX.data.rows[view] || []).forEach(function (r) {
      if (!RBX.filters.pass(r, 'kw')) return;
      var c = RBX.filters.capOf(r); if (c <= 0) c = d[2];
      var i = Math.floor((Math.log10(c) - d[0]) / (d[1] - d[0]) * NB);
      bins[Math.max(0, Math.min(NB - 1, i))]++;
    });
    var mx = Math.max.apply(null, bins) || 1, bw = W / NB, s = '';
    bins.forEach(function (n, i) {
      if (!n) return;
      var h = Math.max(1.5, Math.sqrt(n / mx) * H);
      s += '<rect class="hb" data-i="' + i + '" x="' + (i * bw + 0.8).toFixed(1) + '" y="' + (H + 4 - h).toFixed(1) + '" width="' + Math.max(1, bw - 1.6).toFixed(1) + '" height="' + h.toFixed(1) + '" rx="1"/>';
    });
    svg.setAttribute('width', W); svg.setAttribute('height', H + 6);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + (H + 6));
    svg.innerHTML = s;
    Hs.sync();
  };

  Hs.sync = function (fromSlider) {
    var view = RBX.state.view, lo = document.getElementById('capLo'), hi = document.getElementById('capHi');
    var k = RBX.state.kw[view];
    if (lo && hi && !fromSlider) {
      lo.value = k ? toS(view, k[0]) : 0;
      hi.value = k && isFinite(k[1]) ? toS(view, k[1]) : 1000;
    }
    if (lo && hi) {
      var f = document.getElementById('capFill');
      f.style.left = (lo.value / 10) + '%'; f.style.right = (100 - hi.value / 10) + '%';
      lo.setAttribute('aria-valuetext', U.cap(U.sig2(toKw(view, +lo.value))));
      hi.setAttribute('aria-valuetext', U.cap(U.sig2(toKw(view, +hi.value))));
      var a = +lo.value / 1000 * NB, b = +hi.value / 1000 * NB;
      U.$$('#histSvg .hb').forEach(function (r) { var i = +r.getAttribute('data-i'); r.classList.toggle('out', i + 1 <= a || i >= b); });
    }
    var rd = document.getElementById('capRead'); if (rd) rd.textContent = readout(view);
    var p = preset(view);
    U.$$('#capSeg button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-preset') === p)); });
    Hs.thumb();
  };
  Hs.thumb = function () {
    var seg = document.getElementById('capSeg'); if (!seg) return;
    var on = seg.querySelector('button[aria-pressed="true"]'), t = seg.querySelector('.seg-thumb');
    if (!on) { t.style.width = '0px'; return; }
    t.style.left = on.offsetLeft + 'px'; t.style.width = on.offsetWidth + 'px';
  };

  Hs.setPreset = function (p, view) {
    view = view || RBX.state.view;
    RBX.filters.setKw(view, p === 'over' ? [1000.001, Infinity] : p === 'under' ? [0, 1000] : null);
  };

  Hs.wire = function (root) {
    root.addEventListener('click', function (e) {
      var b = e.target.closest('#capSeg button'); if (b) { Hs.setPreset(b.getAttribute('data-preset')); return; }
      var t = e.target.closest('#histToggle');
      if (t) {
        open = !expanded();
        t.setAttribute('aria-expanded', String(open));
        document.getElementById('hist').hidden = !open;
        if (open) Hs.draw();
      }
    });
    var light = U.rafThrottle(function (view, range) { RBX.filters.setKw(view, range, true); });
    root.addEventListener('input', function (e) {
      if (e.target.id !== 'capLo' && e.target.id !== 'capHi') return;
      var lo = document.getElementById('capLo'), hi = document.getElementById('capHi'), view = RBX.state.view;
      var a = +lo.value, b = +hi.value;
      if (a > b - 20) { if (e.target === lo) lo.value = a = Math.max(0, b - 20); else hi.value = b = Math.min(1000, a + 20); }
      var range = (a <= 0 && b >= 1000) ? null : [a <= 0 ? 0 : U.sig2(toKw(view, a)), b >= 1000 ? Infinity : U.sig2(toKw(view, b))];
      RBX.state.kw[view] = range;
      Hs.sync(true);
      light(view, range);
    });
    root.addEventListener('change', function (e) {
      if (e.target.id === 'capLo' || e.target.id === 'capHi') RBX.filters.changed();
    });
  };
})();
