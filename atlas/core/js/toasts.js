/* RBX.toast(message, {label, run}?): bottom-centre toast, 3.2 s, optional action (e.g. Undo). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  RBX.toast = function (msg, action, ms) {
    var host = document.getElementById('toasts'); if (!host) return;
    var t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = '<span>' + U.esc(msg) + '</span>' + (action ? '<button type="button">' + U.esc(action.label) + '</button>' : '');
    host.appendChild(t);
    var done = function () { if (t.isConnected) t.remove(); };
    if (action) t.querySelector('button').addEventListener('click', function () { done(); action.run(); });
    setTimeout(done, ms || (action ? 6000 : 3200));
    while (host.children.length > 2) host.firstChild.remove();
  };
})();
