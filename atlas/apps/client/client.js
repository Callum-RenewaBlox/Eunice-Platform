/* Client-only wiring. The client build uses the core defaults; this file only declares the audience. */
(function () {
  'use strict';
  var RBX = window.RBX;
  RBX.audience = 'client';
})();
