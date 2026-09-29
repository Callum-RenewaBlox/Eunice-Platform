/* RBX.icons: TAM glyphs generated lazily on `styleimagemissing` (spec 5.4).
   Id: tam:{theme}:{cc}:{sh}:{ap}:{band}; cc = family 0–3, or f0–f8 in the per-fuel colour mode.
   Shape = subsidy (triangle RO, circle FiT), dash = approximate location, band = capacity; the stroke stays constant. */
(function () {
  'use strict';
  var RBX = window.RBX;
  var I = RBX.icons = {};
  var BAND_D = [7, 9.5, 12.5, 17, 23];
  var BAND_W = [1.5, 1.5, 1.6, 1.7, 1.8];
  I.BAND_D = BAND_D;

  function palFor(theme) {
    // read the theme's colours even if it is not the active one (icons are drawn per theme id)
    var cur = document.documentElement.getAttribute('data-theme');
    if (cur === theme) return RBX.theme.pal();
    document.documentElement.setAttribute('data-theme', theme);
    var p = RBX.theme.pal();
    document.documentElement.setAttribute('data-theme', cur);
    return p;
  }

  I.draw = function (map, id) {
    var parts = String(id).split(':');
    if (parts[0] !== 'tam' || parts.length !== 6) return;
    var th = parts[1], cc = parts[2], sh = parts[3], ap = parts[4], band = +parts[5];
    var P = palFor(th), col = cc.charAt(0) === 'f' ? P.fuel[+cc.slice(1)] : P.fam[+cc];
    var pr = 2, d = BAND_D[band] || 7, pad = 3, S = Math.ceil(d * 1.25 + 2 * pad), r = d / 2;
    var cv = document.createElement('canvas');
    cv.width = cv.height = S * pr;
    var g = cv.getContext('2d');
    g.scale(pr, pr);
    var path = new Path2D(), cx = S / 2, cy = S / 2;
    if (sh === 't') {
      var R = r * 1.22, y0 = cy + r * 0.10;
      path.moveTo(cx, y0 - R); path.lineTo(cx + R * 0.866, y0 + R * 0.5); path.lineTo(cx - R * 0.866, y0 + R * 0.5); path.closePath();
    } else path.arc(cx, cy, r, 0, Math.PI * 2);
    g.lineJoin = 'round';
    g.strokeStyle = P.tamHalo; g.lineWidth = BAND_W[band] + 2; g.stroke(path);
    g.fillStyle = P.tamFill; g.fill(path);
    if (th === 'night') { g.shadowColor = col + '99'; g.shadowBlur = 4; }
    g.strokeStyle = col; g.lineWidth = BAND_W[band];
    if (ap === '1') { g.setLineDash([2.2, 1.8]); g.globalAlpha = 0.9; }
    g.stroke(path);
    g.setLineDash([]); g.globalAlpha = 1; g.shadowBlur = 0;
    if (cc === '3') { g.fillStyle = col; g.beginPath(); g.arc(cx, cy, 1.3, 0, 7); g.fill(); }
    try { if (!map.hasImage(id)) map.addImage(id, g.getImageData(0, 0, S * pr, S * pr), { pixelRatio: pr }); } catch (e) { /* duplicate */ }
  };

  /** Draw every icon the data actually uses for a theme before a layout pass needs it. Symbols laid out while an
      image is still missing get no collision box, so they would not be pickable until the next re-layout;
      styleimagemissing stays as the safety net. */
  I.ensure = function (map, theme) {
    var seen = {};
    (RBX.data.rows.tam || []).forEach(function (r) {
      var cc = RBX.theme.tamMode() === 'fuels' ? 'f' + r.fu : String(r.fam);
      var id = 'tam:' + theme + ':' + cc + ':' + r.sh + ':' + r.ap + ':' + r.band;
      if (seen[id]) return; seen[id] = 1;
      if (!map.hasImage(id)) I.draw(map, id);
    });
  };
  I.expr = function (theme) {
    return ['concat', 'tam:', theme, ':', ['get', 'cc'], ':', ['get', 'sh'], ':', ['to-string', ['get', 'ap']], ':', ['to-string', ['get', 'band']]];
  };

  /** Small inline SVG glyphs for legends, cards and search (the exact map glyph). */
  I.svg = function (o) {
    var s = o.size || 14, h = s / 2, col = o.color || 'currentColor', dash = o.dashed ? ' stroke-dasharray="2.2 1.6"' : '';
    var body;
    if (o.shape === 'tri') body = '<path d="M' + h + ' ' + (s * 0.12) + ' L' + (s * 0.92) + ' ' + (s * 0.84) + ' L' + (s * 0.08) + ' ' + (s * 0.84) + 'Z" fill="' + (o.fill || 'none') + '" stroke="' + col + '" stroke-width="1.6" stroke-linejoin="round"' + dash + '/>';
    else if (o.shape === 'ring') body = '<circle cx="' + h + '" cy="' + h + '" r="' + (h - 1.6) + '" fill="' + (o.fill || 'none') + '" stroke="' + col + '" stroke-width="1.7"' + dash + '/>';
    else body = '<circle cx="' + h + '" cy="' + h + '" r="' + (h - 1) + '" fill="' + col + '"' + (o.stroke ? ' stroke="' + o.stroke + '" stroke-width="1"' : '') + '/>';
    if (o.dot) body += '<circle cx="' + h + '" cy="' + (o.shape === 'tri' ? s * 0.6 : h) + '" r="1.3" fill="' + col + '"/>';
    return '<svg class="glyph" width="' + s + '" height="' + s + '" viewBox="0 0 ' + s + ' ' + s + '" aria-hidden="true">' + body + '</svg>';
  };
  /** Glyph for a data row in the current theme. */
  I.forRow = function (r, size) {
    var P = RBX.theme.pal();
    if (r.kind === 'sam') {
      if (r.pr === 0) return I.svg({ shape: 'ring', color: P.tier[r.t - 1], size: size });
      return I.svg({ shape: 'dot', color: P.tier[r.t - 1], size: size });
    }
    if (r.kind === 'hydro') return r.c === 3 ? I.svg({ shape: 'ring', color: P.unv, size: size }) : I.svg({ shape: 'dot', color: P.hyd[r.c], size: size });
    var mode = RBX.theme.tamMode();
    return I.svg({ shape: r.sh === 't' ? 'tri' : 'ring', color: RBX.theme.tamColour(r, P), dashed: !!r.ap, size: size, dot: mode === 'families' && r.fam === 3 });
  };
})();
