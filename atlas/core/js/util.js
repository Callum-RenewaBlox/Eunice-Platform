/* RBX.util: formatting (en-GB), escaping, timing, storage, clipboard, geometry, and a tiny event bus. */
(function () {
  'use strict';
  var RBX = window.RBX = window.RBX || {};
  var U = RBX.util = {};

  U.$ = function (s, r) { return (r || document).querySelector(s); };
  U.$$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  U.esc = function (s) {
    return s == null ? '' : String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };

  // ------------------------------------------------------------------ numbers (en-GB everywhere)
  var NF = {};
  U.num = function (v, d) {
    d = d || 0;
    if (v == null || isNaN(v)) return '—';
    var k = 'd' + d;
    if (!NF[k]) NF[k] = new Intl.NumberFormat('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
    return NF[k].format(v);
  };
  U.int = function (v) { return v == null ? '—' : U.num(Math.round(v), 0); };
  /** MW from kW: 1 dp below 1,000 MW, 0 dp with separators at or above. Returns the number only. */
  U.mw = function (kw) { var m = (kw || 0) / 1000; return m >= 1000 ? U.num(m, 0) : U.num(m, 1); };
  U.mwDigits = function (kw) { return (kw || 0) / 1000 >= 1000 ? 0 : 1; };
  /** Compact capacity: 249 kW · 5.9 MW · 60.0 MW. */
  U.cap = function (kw) {
    if (kw == null) return '—';
    return kw >= 1000 ? U.num(kw / 1000, 1) + ' MW' : U.num(Math.round(kw), 0) + ' kW';
  };
  /** Currency, v1 semantics. */
  U.abbr = function (v) {
    v = Math.round(v || 0);
    if (v >= 1e9) return '£' + (v / 1e9).toFixed(2) + 'bn';
    if (v >= 1e6) return '£' + (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return '£' + (v / 1e3).toFixed(0) + 'k';
    return '£' + v;
  };
  U.gbp0 = function (v) { return '£' + U.num(Math.round(v || 0), 0); };
  U.sum = function (rows, f) { var s = 0; for (var i = 0; i < rows.length; i++) { var v = f(rows[i]); if (v != null && !isNaN(v)) s += v; } return s; };
  /** 2 significant figures, used to snap slider values. */
  U.sig2 = function (v) { if (!isFinite(v) || v <= 0) return v; var m = Math.pow(10, Math.floor(Math.log10(v)) - 1); return Math.round(v / m) * m; };

  // ------------------------------------------------------------------ text
  var KEEP = { AD: 1, CHP: 1, UK: 1, GB: 1, STW: 1, WTW: 1, WWTW: 1, SPV: 1, LLP: 1, NHS: 1, II: 1, III: 1, JV: 1 };
  /** ALL-CAPS → Title Case keeping acronyms. Mixed case is left alone. (Build-time data is already cased.) */
  U.displayCase = function (s) {
    if (!s) return s;
    var letters = s.replace(/[^A-Za-z]/g, '');
    if (!letters || letters.replace(/[^A-Z]/g, '').length / letters.length < 0.8) return s;
    // per word: only ALL-CAPS words are re-cased; mixed-case words (McCain, BioticNRG) keep their capitals
    return s.replace(/[A-Za-z0-9']+/g, function (w0, i) {
      if (/[a-z]/.test(w0)) return w0;
      var w = w0.toLowerCase(), u = w0;
      if (KEEP[u]) return u;
      if (u === 'LTD') return 'Ltd';
      if (u === 'PLC') return 'plc';
      if (u === 'EFW') return 'EfW';
      if (/\d/.test(w)) return u;
      if (i > 0 && /^(and|of|the|at|on|in|for|to|by)$/.test(w)) return w;
      return w.charAt(0).toUpperCase() + w.slice(1);
    });
  };
  /** Escape, then protect units and mixed-case acronyms (kW, MW, FiT, EfW …) from CSS text-transform:uppercase. */
  U.caseSafe = function (s) {
    return U.esc(s).replace(/\b(kW|MW|GW|kWh|MWh|FiT|EfW)\b/g, '<span class="nc">$1</span>');
  };
  U.cleanName = function (o) {
    if (!o) return o;
    if (/sole holder/i.test(o)) return 'Generator is sole holder';
    return U.displayCase(o.replace(/\s*\(Supplier\)\s*$/i, '').replace(/\s*-\s*Supplier\s*-\s*SUP\d+\s*$/i, '').replace('Internatinal', 'International').trim());
  };
  /** Search normalisation: lower-case, strip diacritics and punctuation, collapse whitespace. */
  U.norm = function (s) {
    s = String(s == null ? '' : s).toLowerCase();
    if (s.normalize) s = s.normalize('NFD').replace(/[̀-ͯ]/g, '');
    return s.replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
  };
  U.compactPc = function (s) { return String(s || '').replace(/\s+/g, '').toUpperCase(); };
  U.outcode = function (pc) { var m = String(pc || '').trim().toUpperCase().match(/^([A-Z]{1,2}\d[A-Z\d]?)\s*\d[A-Z]{2}$/); return m ? m[1] : ''; };
  U.MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  U.fmtDate = function (iso) { if (!iso) return '—'; var p = String(iso).split('-'); return U.MONTHS[+p[1] - 1] + ' ' + p[0]; };
  U.template = function (s, o) { return String(s).replace(/\{(\w+)\}/g, function (m, k) { return o[k] == null ? '' : o[k]; }); };

  // ------------------------------------------------------------------ timing
  U.debounce = function (fn, ms) { var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); }; };
  U.rafThrottle = function (fn) {
    var q = false, a, c;
    return function () { a = arguments; c = this; if (q) return; q = true; requestAnimationFrame(function () { q = false; fn.apply(c, a); }); };
  };
  U.reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  RBX.reduced = U.reduced;
  U.isMobile = function () { return !!(window.matchMedia && window.matchMedia('(max-width: 760px)').matches); };
  U.isTouch = function () { return !!(window.matchMedia && window.matchMedia('(hover: none)').matches); };
  /** Count a number up from its previous value (easeOutQuart). */
  U.countUp = function (el, to, format, dur) {
    if (!el) return;
    var from = parseFloat(el.getAttribute('data-v'));
    el.setAttribute('data-v', String(to));
    if (isNaN(from) || U.reduced || from === to) { el.innerHTML = format(to); return; }
    var t0 = performance.now(), d = dur || 600;
    (function step(t) {
      var k = Math.min(1, (t - t0) / d), e = 1 - Math.pow(1 - k, 4);
      el.innerHTML = format(from + (to - from) * e);
      if (k < 1 && el.getAttribute('data-v') === String(to)) requestAnimationFrame(step);
    })(t0);
  };

  // ------------------------------------------------------------------ storage (every access guarded)
  U.store = function (k, v) {
    try {
      if (v === undefined) return window.localStorage.getItem(k);
      if (v === null) window.localStorage.removeItem(k); else window.localStorage.setItem(k, v);
    } catch (e) { return null; }
    return null;
  };

  // ------------------------------------------------------------------ clipboard with a visible fallback
  U.copyText = function (text, anchor) {
    function fallback() {
      if (!anchor) return;
      var old = anchor.querySelector('.copy-pop');
      if (old) old.remove();
      var d = document.createElement('div');
      d.className = 'copy-pop';
      d.innerHTML = 'Press ⌘C / Ctrl-C to copy<label class="sr-only" for="copyField">Link</label><input id="copyField" readonly value="' + U.esc(text) + '">';
      anchor.appendChild(d);
      var inp = d.querySelector('input'); inp.focus(); inp.select();
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).then(function () { return true; }, function () { fallback(); return false; });
      }
    } catch (e) { /* fall through */ }
    fallback();
    return Promise.resolve(false);
  };
  U.download = function (name, text, type) {
    try {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/plain' }));
      a.download = name; document.body.appendChild(a); a.click(); a.remove();
    } catch (e) { window.open('data:' + (type || 'text/plain') + ',' + encodeURIComponent(text)); }
  };

  // ------------------------------------------------------------------ geometry
  U.km = function (a, b) {
    var R = 6371, r = Math.PI / 180, dLat = (b[1] - a[1]) * r, dLon = (b[0] - a[0]) * r;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  };
  U.bbox = function (rows, pad) {
    var b = [[180, 90], [-180, -90]];
    rows.forEach(function (r) {
      if (r.lon < b[0][0]) b[0][0] = r.lon; if (r.lat < b[0][1]) b[0][1] = r.lat;
      if (r.lon > b[1][0]) b[1][0] = r.lon; if (r.lat > b[1][1]) b[1][1] = r.lat;
    });
    pad = pad || 0;
    return [[b[0][0] - pad, b[0][1] - pad], [b[1][0] + pad, b[1][1] + pad]];
  };

  // ------------------------------------------------------------------ event bus
  var subs = {};
  RBX.bus = {
    on: function (ev, fn) { (subs[ev] = subs[ev] || []).push(fn); return fn; },
    off: function (ev, fn) { subs[ev] = (subs[ev] || []).filter(function (f) { return f !== fn; }); },
    emit: function (ev, payload) {
      (subs[ev] || []).slice().forEach(function (f) {
        try { f(payload); } catch (e) { if (window.console) console.error('[atlas] ' + ev + ' handler failed', e); }
      });
    }
  };
  /** Extension points: investor modules replace or wrap these before RBX.boot runs. */
  RBX.hooks = RBX.hooks || {};
})();
