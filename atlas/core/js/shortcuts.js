/* RBX.shortcuts: the keymap (spec 7.1). Ignored while focus is in a text input.
   / ⌘K Ctrl-K search · 1 2 3 views · S scope · T theme · R reset · L rail · J/K step · Esc closes in order ·
   P present (when an audience module registers RBX.present). */
(function () {
  'use strict';
  var RBX = window.RBX;
  RBX.shortcuts = {};
  function typing(t) { return t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable); }
  RBX.shortcuts.escape = function () {
    if (RBX.modal && RBX.modal.isOpen()) { RBX.modal.close(); return true; }
    if (RBX.search.isOpen()) { RBX.search.close(); return true; }
    var pop = document.getElementById('menuPop'); if (pop && !pop.hidden) { RBX.header.toggleMenu(false); return true; }
    if (RBX.sheet.isOpen()) { RBX.sheet.close(); return true; }
    if (RBX.drawer.isOpen()) { RBX.drawer.close(); return true; }
    if (RBX.present && RBX.present.active && RBX.present.active()) { RBX.present.exit(); return true; }
    return false;
  };
  document.addEventListener('keydown', function (e) {
    var k = e.key;
    if ((e.metaKey || e.ctrlKey) && (k === 'k' || k === 'K')) { e.preventDefault(); RBX.search.isOpen() ? RBX.search.close() : RBX.search.open(); return; }
    if (k === 'Escape') { if (RBX.shortcuts.escape()) e.preventDefault(); return; }
    if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
    if (RBX.search.isOpen() || RBX.drawer.isOpen() || (RBX.modal && RBX.modal.isOpen())) return;
    if (RBX.present && RBX.present.active && RBX.present.active() && RBX.present.key && RBX.present.key(e)) return;
    var S = RBX.state, A = RBX.app;
    switch (k) {
      case '/': e.preventDefault(); RBX.search.open(); break;
      case '1': A.setView(S.lastPeaker || 'sam'); break;
      case '2': A.setView('hydro'); break;
      case '3': A.setView('ppa'); break;
      case 's': case 'S': A.setView(S.view === 'sam' ? 'tam' : S.view === 'tam' ? 'sam' : (S.lastPeaker === 'sam' ? 'tam' : 'sam')); break;
      case 't': case 'T': RBX.theme.toggle(); break;
      case 'r': case 'R': if (S.view !== 'ppa') RBX.mapctl.reset(); break;
      case 'l': case 'L': if (S.view !== 'ppa') RBX.rail.toggle(); break;
      case 'j': case 'J': RBX.sheet.step(1); break;
      case 'k': case 'K': RBX.sheet.step(-1); break;
      case 'p': case 'P': if (RBX.present && RBX.present.enter) RBX.present.enter(); break;
      default: return;
    }
  });
})();
