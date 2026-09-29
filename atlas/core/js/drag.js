/* RBX.drag: mobile bottom-sheet drag gesture with snap points (spec 6.8, P1 #13).
   Rail sheet: peek (--peek-h) ↔ open (78vh). Card sheet: 46vh ↔ 90vh, and a drag well below the lower snap
   closes it. The grab handles stay buttons (tap still toggles); a drag suppresses the click that follows. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var D = RBX.drag = {};

  function vh() { return window.innerHeight; }
  function peek() { return parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--peek-h')) || 136; }

  /** Wire a drag on `grip` (element or selector resolved at pointerdown) that resizes `sheet`. */
  function attach(o) {
    var st = null, swallow = false;
    document.addEventListener('pointerdown', function (e) {
      if (!U.isMobile() || e.button > 0) return;
      var g = e.target.closest(o.grip); if (!g) return;
      var sh = document.getElementById(o.sheet); if (!sh || sh.hidden) return;
      if (o.allow && !o.allow(e, sh)) return;
      st = { y: e.clientY, t: performance.now(), h0: sh.getBoundingClientRect().height, sh: sh, moved: false, id: e.pointerId, g: g };
    }, { passive: true });
    document.addEventListener('pointermove', function (e) {
      if (!st || e.pointerId !== st.id) return;
      var dy = e.clientY - st.y;
      if (!st.moved && Math.abs(dy) < 7) return;
      if (!st.moved) { st.moved = true; st.sh.classList.add('dragging'); try { st.g.setPointerCapture(e.pointerId); } catch (er) { /* ignore */ } }
      var h = Math.max(o.min(), Math.min(vh() * 0.94, st.h0 - dy));
      st.sh.style.height = h + 'px'; st.sh.style.maxHeight = h + 'px';
      st.last = { dy: dy, t: performance.now() };
    }, { passive: true });
    function end(e) {
      if (!st || (e && e.pointerId !== st.id)) return;
      var s = st; st = null;
      if (!s.moved) return;
      swallow = true; setTimeout(function () { swallow = false; }, 350);
      var h = s.sh.getBoundingClientRect().height, dt = Math.max(1, performance.now() - s.t), v = (s.last ? s.last.dy : 0) / dt;   // px/ms, + = down
      s.sh.classList.remove('dragging');
      s.sh.style.height = ''; s.sh.style.maxHeight = '';
      o.snap(h, v, s.sh);
    }
    document.addEventListener('pointerup', end);
    document.addEventListener('pointercancel', end);
    document.addEventListener('click', function (e) { if (swallow && e.target.closest(o.grip)) { e.preventDefault(); e.stopPropagation(); swallow = false; } }, true);
  }

  // rail: peek ↔ open
  attach({
    sheet: 'rail', grip: '#railHandle, #rail:not(.open) .rail-body, #rail.open .kicker, #rail.open .headline',
    min: function () { return peek() - 30; },
    snap: function (h, v) {
      var open = v < -0.5 ? true : v > 0.5 ? false : h > (peek() + vh() * 0.78) / 2;
      RBX.rail.setOpen(open);
    }
  });
  // card: 46vh ↔ 90vh ↔ close
  attach({
    sheet: 'sheet', grip: '#shHandle, #sheet .sh-top',
    allow: function (e) { return !e.target.closest('button:not(#shHandle), a'); },
    min: function () { return 80; },
    snap: function (h, v, sh) {
      var a = vh() * 0.46, b = vh() * 0.90;
      if ((v > 0.9 && h < a + 40) || h < a * 0.62) { RBX.sheet.close(); return; }
      var full = v < -0.5 ? true : v > 0.5 ? false : h > (a + b) / 2;
      sh.classList.toggle('full', full);
      var hb = document.getElementById('shHandle'); if (hb) hb.setAttribute('aria-label', full ? 'Collapse details' : 'Expand details');
    }
  });
})();
