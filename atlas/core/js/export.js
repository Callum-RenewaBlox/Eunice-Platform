/* RBX.exporter: client P1 downloads (spec 11 P1 #4, #5).
   CSV: the sites shown on the map (current view, current filters, "In view" when on) and the PPA site register,
   client-safe columns only. PNG: a 1600×900 @2x composite of the map canvas (captured on the next render, no
   preserveDrawingBuffer), title, KPIs, legend, annotations and a sources / as-of footer; downloaded with
   <a download>, falling back to a new window. Audience modules may add columns (RBX.exporter.cols[kind]) and a
   header row (config.csvHeader) or an image badge (config.imageBadge). */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var E = RBX.exporter = {};
  E.ICON = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3.5v9M6 9l4 4 4-4M4 15.5h12"/></svg>';
  E.IMG_ICON = '<svg class="i" viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="4.5" width="14" height="11" rx="1.5"/><path d="m3.5 13.5 4-4 3 3 2-2 4 3.5"/><circle cx="13" cy="8" r="1.2"/></svg>';
  function L() { return RBX.config.labels || {}; }

  // ------------------------------------------------------------------ CSV
  E.cols = {
    sam: [
      ['Ref', function (r) { return r.ref; }], ['Site', function (r) { return r.name; }], ['Address', function (r) { return r.site; }],
      ['Town', function (r) { return r.town; }], ['Local authority', function (r) { return r.la; }], ['Postcode', function (r) { return r.pc; }],
      ['Operator', function (r) { return r.op; }], ['BM tier', function (r) { return r.t; }], ['BM tier label', function (r) { return L().tiers[r.t]; }],
      ['Installed kW', function (r) { return r.kw; }], ['Onsite demand kW', function (r) { return r.kwOn; }], ['Available for BM kW', function (r) { return r.kwBm; }],
      ['Commissioned', function (r) { return r.comm; }], ['Export arrangement', function (r) { return (L().export || {})[r.ppa] || ''; }],
      ['Certificate counterparty (inferred)', function (r) { return r.off; }], ['Latitude', function (r) { return r.lat; }], ['Longitude', function (r) { return r.lon; }]
    ],
    tam: [
      ['Site', function (r) { return r.name; }], ['Fuel', function (r) { return r.fuel; }], ['Technology family', function (r) { return L().families[r.fam]; }],
      ['Subsidy', function (r) { return r.ro ? 'RO' : 'FiT'; }], ['RO reference', function (r) { return r.ro; }], ['Capacity kW', function (r) { return r.kw; }],
      ['Available for BM kW', function (r) { return r.bm; }], ['BM tier (indicative)', function (r) { return r.bt ? L().tiers[r.bt] : L().tiers[0]; }],
      ['Location precision', function (r) { return r.ap ? 'Postcode district' : 'Exact'; }], ['Also in SAM', function (r) { return r.inSam ? 'Yes' : 'No'; }],
      ['Latitude', function (r) { return r.lat; }], ['Longitude', function (r) { return r.lon; }]
    ],
    hydro: [
      ['Site', function (r) { return r.name; }], ['Match confidence', function (r) { return r.c === 3 ? 'Unverified' : r.conf; }], ['Export', function (r) { return r.exp; }],
      ['Stranded kW', function (r) { return r.kw; }], ['Installed kW', function (r) { return r.inst; }], ['Export capacity kW', function (r) { return r.mec; }],
      ['Latitude', function (r) { return r.lat; }], ['Longitude', function (r) { return r.lon; }]
    ],
    register: [
      ['Ref', function (o) { return o.ref; }], ['Operator', function (o) { return o.operator; }], ['Site', function (o) { return o.site; }],
      ['Town', function (o) { return o.town; }], ['Postcode', function (o) { return o.postcode; }], ['Installed kW', function (o) { return o.installed_kw; }],
      ['Commissioned', function (o) { return o.commissioned; }], ['Export arrangement', function (o) { return o.ppa_class; }],
      ['Certificate counterparty (inferred)', function (o) { return o.offtaker; }], ['Generator also holds own certificates', function (o) { return o.self_certs ? 'Yes' : 'No'; }],
      ['FiT generation tariff 2026/27 (p/kWh)', function (o) { return o.gen_tariff_p_kwh_2026_27; }], ['FiT end date', function (o) { return o.fit_end_date; }],
      ['Years of subsidy left', function (o) { return o.yrs_subsidy_left; }], ['Generating status', function (o) { return o.rego_status; }]
    ]
  };
  function cell(v) {
    if (v == null) return '';
    var s = String(v);
    if (/^[=+\-@\t\r]/.test(s) && !/^-?\d+(\.\d+)?$/.test(s)) s = "'" + s;       // no spreadsheet formula injection
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  E.csv = function (cols, rows) {
    var lines = [];
    if (RBX.config.csvHeader) lines.push(cell(RBX.config.csvHeader));
    lines.push(cols.map(function (c) { return cell(c[0]); }).join(','));
    rows.forEach(function (r) { lines.push(cols.map(function (c) { return cell(c[1](r)); }).join(',')); });
    return '﻿' + lines.join('\r\n') + '\r\n';
  };
  function stamp() { var a = (RBX.data.ppa && RBX.data.ppa.kpi && RBX.data.ppa.kpi.asOf) || ''; var d = new Date(a); return isNaN(d) ? '' : '-' + d.toISOString().slice(0, 10); }
  function base() { return String(RBX.config.storageKey || 'renewablox-atlas').replace(/^rbx-/, 'renewablox-'); }
  E.sitesCsv = function (view, rows) {
    view = view || (RBX.state.view === 'ppa' ? RBX.state.lastPeaker : RBX.state.view);
    rows = rows || (RBX.state.inView && RBX.kpi.inViewRows ? RBX.kpi.inViewRows(RBX.filters.active(view)) : RBX.filters.active(view));
    U.download(base() + '-' + view + '-sites' + stamp() + '.csv', E.csv(E.cols[view], rows), 'text/csv;charset=utf-8');
    RBX.toast('Downloaded ' + U.int(rows.length) + ' sites as CSV');
  };
  E.registerCsv = function () {
    var rows = RBX.data.register();
    U.download(base() + '-ppa-register' + stamp() + '.csv', E.csv(E.cols.register, rows), 'text/csv;charset=utf-8');
    RBX.toast('Downloaded the site register (' + U.int(rows.length) + ' sites) as CSV');
  };

  // ------------------------------------------------------------------ PNG
  var W = 1600, H = 900, TOP = 64, FOOT = 46;
  function css(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function wrap(g, text, maxW) {
    var words = String(text).split(/\s+/), lines = [], cur = '';
    words.forEach(function (w) { var t = cur ? cur + ' ' + w : w; if (g.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; });
    if (cur) lines.push(cur);
    return lines;
  }
  function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function glyph(g, shape, x, y, r, col, dashed) {
    g.save(); g.beginPath();
    if (shape === 'tri') { var R = r * 1.22, y0 = y + r * 0.1; g.moveTo(x, y0 - R); g.lineTo(x + R * 0.866, y0 + R * 0.5); g.lineTo(x - R * 0.866, y0 + R * 0.5); g.closePath(); }
    else g.arc(x, y, r, 0, Math.PI * 2);
    if (shape === 'dot') { g.fillStyle = col; g.fill(); }
    else { if (dashed) g.setLineDash([2.2, 1.8]); g.strokeStyle = col; g.lineWidth = 1.8; g.stroke(); }
    g.restore();
  }
  function legendRows(view) {
    var P = RBX.theme.pal(), rows = RBX.filters.active(view), lab = L(), out = [];
    var cnt = function (f) { var s = rows.filter(f), kw = U.sum(s, function (r) { return r.kw; }); return U.int(s.length) + ' · ' + (kw >= 100000 ? U.int(kw / 1000) : U.num(kw / 1000, 1)) + ' MW'; };
    if (view === 'sam') {
      // unpriced rows (pr === 0, audience builds only) are drawn hollow: key them, and count the tiers over priced rows
      var aw = ((RBX.config.legend || {}).sam || {}).awaiting, hollow = aw ? rows.filter(function (r) { return r.pr === 0; }) : [];
      [1, 2, 3, 4, 5].forEach(function (t) { out.push({ shape: 'dot', col: P.tier[t - 1], label: lab.tiers[t], right: cnt(function (r) { return r.t === t && (!hollow.length || r.pr !== 0); }) }); });
      if (hollow.length) out.push({ shape: 'ring', col: P.ink2, label: String(aw), right: cnt(function (r) { return r.pr === 0; }) });
    }
    if (view === 'tam') {
      if (RBX.theme.tamMode() === 'fuels') {
        // per-fuel rows (the map colours each fuel): the six largest by MW, then the rest aggregated
        var fr = (lab.fuels || []).map(function (f, j) {
          var s = rows.filter(function (r) { return r.fu === j; });
          return { j: j, n: s.length, kw: U.sum(s, function (r) { return r.kw; }) };
        }).filter(function (x) { return x.n > 0; }).sort(function (a, b) { return b.kw - a.kw || b.n - a.n; });
        fr.slice(0, 6).forEach(function (x) { out.push({ shape: 'ring', col: P.fuel[x.j], label: lab.fuels[x.j], right: cnt(function (r) { return r.fu === x.j; }) }); });
        var rest = fr.slice(6).map(function (x) { return x.j; });
        if (rest.length === 1) out.push({ shape: 'ring', col: P.fuel[rest[0]], label: lab.fuels[rest[0]], right: cnt(function (r) { return r.fu === rest[0]; }) });
        else if (rest.length) out.push({ shape: 'ring', col: P.ink3, label: 'Other fuels (' + rest.length + ')', right: cnt(function (r) { return rest.indexOf(r.fu) >= 0; }) });
      } else {
        [0, 1, 2, 3].forEach(function (f) { out.push({ shape: 'ring', col: P.fam[f], label: lab.families[f], right: cnt(function (r) { return r.fam === f; }) }); });
      }
      out.push({ shape: 'tri', col: P.ink2, label: 'RO accredited', right: U.int(rows.filter(function (r) { return r.ro; }).length) });
      out.push({ shape: 'ring', col: P.ink2, label: 'FiT accredited', right: U.int(rows.filter(function (r) { return !r.ro; }).length) });
    }
    if (view === 'hydro') {
      [0, 1, 2, 3].forEach(function (c) { out.push({ shape: c === 3 ? 'ring' : 'dot', col: c === 3 ? P.unv : P.hyd[c], label: c === 3 ? 'Unverified' : lab.conf[c] + ' confidence',
        right: U.int(rows.filter(function (r) { return r.c === c; }).length) + ' · ' + U.int(U.sum(rows.filter(function (r) { return r.c === c; }), function (r) { return r.kw; })) + ' kW' }); });
    }
    return out;
  }
  /** Copy the map canvas on the next rendered frame (works without preserveDrawingBuffer). */
  E.grabMap = function (cb) {
    var m = RBX.map; if (!m) { cb(null); return; }
    var done = false;
    m.once('render', function () {
      if (done) return; done = true;
      try { var c = m.getCanvas(), cp = document.createElement('canvas'); cp.width = c.width; cp.height = c.height; cp.getContext('2d').drawImage(c, 0, 0); cb(cp); }
      catch (e) { cb(null); }
    });
    m.triggerRepaint();
    setTimeout(function () { if (!done) { done = true; cb(null); } }, 3000);
  };
  E.composite = function (mapCanvas) {
    var view = RBX.state.view === 'ppa' ? RBX.state.lastPeaker : RBX.state.view, cfg = RBX.config, vc = (cfg.views || {})[view] || {};
    var cv = document.createElement('canvas'); cv.width = W * 2; cv.height = H * 2;
    var g = cv.getContext('2d'); g.scale(2, 2);
    var UI = '"Inter", system-ui, sans-serif', SERIF = '"Newsreader", Georgia, serif';
    var land = css('--map-land'), ink1 = css('--ink-1'), ink2 = css('--ink-2'), ink3 = css('--ink-3'), rule = css('--rule'), lime = css('--lime-ink');
    var surf = css('--surface-1') || '#fff', night = RBX.state.theme === 'night';
    g.fillStyle = land; g.fillRect(0, 0, W, H);
    // map, cover-fitted and cropped vertically so the active sites stay in frame
    var mh = H - TOP - FOOT, box = document.getElementById('map');
    if (mapCanvas && box) {
      var cw = box.clientWidth, ch = box.clientHeight, s = Math.max(W / cw, mh / ch), dw = cw * s, dh = ch * s, ox = (W - dw) / 2, oy = TOP + (mh - dh) / 2;
      var m = RBX.map, act = RBX.filters.active(view);
      if (m && act.length && dh > mh) {
        var ys = act.map(function (r) { return m.project([r.lon, r.lat]).y; }).filter(function (y) { return y > -20 && y < ch + 20; });
        if (ys.length) {
          var ymin = Math.min.apply(null, ys) * s, ymax = Math.max.apply(null, ys) * s, want = TOP + mh / 2 - (ymin + ymax) / 2;
          oy = Math.min(TOP, Math.max(TOP + mh - dh, want));
        }
      }
      g.save(); g.beginPath(); g.rect(0, TOP, W, mh); g.clip();
      g.drawImage(mapCanvas, ox, oy, dw, dh);
      // annotations (only those placed on screen)
      var notes = RBX.notes && RBX.notes.items && !document.getElementById('notes').classList.contains('hide') ? RBX.notes.items : [];
      var area = document.getElementById('mapArea').getBoundingClientRect(), mr = box.getBoundingClientRect();
      notes.forEach(function (it) {
        if (!it.pick || it.el.style.opacity === '0') return;
        var tr = /translate\(([-\d.]+)px,\s*([-\d.]+)px\)/.exec(it.el.style.transform); if (!tr) return;
        var nx = (+tr[1] + area.left - mr.left) * s + ox, ny = (+tr[2] + area.top - mr.top) * s + oy, right = it.el.classList.contains('r'), wmax = 200 * s;
        var p = m.project(it.d.anchor), px = p.x * s + ox, py = p.y * s + oy;
        var ring = 0;
        if (it.d.ringKm) {
          var q = m.project([it.d.anchor[0] + it.d.ringKm / (111.32 * Math.cos(it.d.anchor[1] * Math.PI / 180)), it.d.anchor[1]]);
          ring = Math.abs(q.x - p.x) * s;
          g.save(); g.setLineDash([3, 3]); g.strokeStyle = ink2; g.globalAlpha = 0.75; g.lineWidth = 1; g.beginPath(); g.arc(px, py, ring, 0, Math.PI * 2); g.stroke(); g.restore();
        }
        var ex = right ? nx + wmax + 6 : nx - 6, ey = ny + 8, an = Math.atan2(ey - py, ex - px);
        g.strokeStyle = ink2; g.lineWidth = 1; g.beginPath(); g.moveTo(px + Math.cos(an) * (ring || 3), py + Math.sin(an) * (ring || 3)); g.lineTo(ex, ey); g.stroke();
        if (!ring) { g.fillStyle = ink2; g.beginPath(); g.arc(px, py, 2.2, 0, 7); g.fill(); }
        g.textAlign = right ? 'right' : 'left';
        var tx = right ? nx + wmax : nx;
        g.font = '600 ' + (11 * s).toFixed(1) + 'px ' + UI; g.fillStyle = ink1;
        g.lineWidth = 4; g.strokeStyle = land; g.lineJoin = 'round';
        var lead = it.d.lead.toUpperCase(); g.strokeText(lead, tx, ny + 11 * s); g.fillText(lead, tx, ny + 11 * s);
        g.font = '400 ' + (14 * s).toFixed(1) + 'px ' + SERIF;
        wrap(g, it.el.textContent.slice(it.d.lead.length), wmax).forEach(function (ln, i) { var y = ny + (30 + 18.2 * i) * s; g.strokeText(ln, tx, y); g.fillText(ln, tx, y); });
        g.textAlign = 'left';
      });
      g.restore();
    }
    // header band (audience brand chrome)
    g.fillStyle = css('--header-bg') || '#0B2E2A'; g.fillRect(0, 0, W, TOP);
    [['#8FD14F', 0, 0], ['#3E8A6A', 11, 0], ['#2F6B55', 0, 11], ['#245744', 11, 11]].forEach(function (q) { g.fillStyle = q[0]; rr(g, 28 + q[1] * 1.3, 18 + q[2] * 1.3, 11.7, 11.7, 2.6); g.fill(); });
    g.fillStyle = '#FFFFFF'; g.font = '500 25px ' + SERIF; g.textBaseline = 'alphabetic'; g.fillText('RenewaBlox', 64, 41);
    var bw = g.measureText('RenewaBlox').width;
    g.fillStyle = css('--header-rule') || '#1D5A51'; g.fillRect(64 + bw + 14, 20, 1, 24);
    g.fillStyle = css('--header-ink-2') || '#CFE8E2'; g.font = '600 11px ' + UI; g.fillText(String(cfg.productLabel || '').toUpperCase(), 64 + bw + 29, 30);
    g.fillStyle = '#8FD14F'; g.font = 'italic 400 13px ' + SERIF; g.fillText('no Watt wasted', 64 + bw + 29, 46);
    g.textAlign = 'right'; g.fillStyle = css('--header-ink-2') || '#CFE8E2'; g.font = '600 11px ' + UI; g.fillText(String(vc.kicker || '').toUpperCase(), W - 28, 38); g.textAlign = 'left';
    if (cfg.imageBadge) { g.textAlign = 'right'; g.fillStyle = '#F2C66B'; g.font = '600 11px ' + UI; g.fillText(cfg.imageBadge, W - 28, 54); g.textAlign = 'left'; }
    // editorial card (title, KPIs, legend)
    var cx = 28, cy = TOP + 22, cwid = 392, pad = 22, y = cy + pad;
    g.font = '500 30px ' + SERIF;
    var head = wrap(g, vc.headline || '', cwid - pad * 2);
    var leg = legendRows(view), kpis = (vc.kpis || []).slice(0, 3);
    var chH = pad + 14 + head.length * 33 + 16 + (kpis.length ? 72 : 0) + 18 + leg.length * 25 + 12 + pad;
    g.save(); g.shadowColor = 'rgba(0,0,0,' + (night ? 0.45 : 0.14) + ')'; g.shadowBlur = 24; g.shadowOffsetY = 6;
    g.fillStyle = night ? css('--surface-0-solid') : surf; rr(g, cx, cy, cwid, chH, 16); g.fill(); g.restore();
    g.strokeStyle = rule; g.lineWidth = 1; rr(g, cx + 0.5, cy + 0.5, cwid - 1, chH - 1, 16); g.stroke();
    g.fillStyle = lime; g.fillRect(cx + pad, y + 1, 14, 2); g.font = '600 10.5px ' + UI; g.fillText(String(vc.kicker || '').toUpperCase(), cx + pad + 22, y + 6);
    y += 14;
    g.fillStyle = ink1; g.font = '500 30px ' + SERIF; head.forEach(function (ln) { y += 33; g.fillText(ln, cx + pad, y); });
    y += 16;
    if (kpis.length) {
      g.fillStyle = ink1; g.fillRect(cx + pad, y, cwid - pad * 2, 1);
      var rows = RBX.filters.active(view), cwk = (cwid - pad * 2) / kpis.length;
      kpis.forEach(function (k, i) {
        var mm = (RBX.kpi.metrics[k.metric] || RBX.kpi.metrics.count)(rows), x = cx + pad + i * cwk + (i ? 12 : 0);
        if (i) { g.fillStyle = rule; g.fillRect(cx + pad + i * cwk, y + 8, 1, 56); }
        g.fillStyle = ink3; g.font = '600 9.5px ' + UI; g.fillText(String(k.label).toUpperCase(), x, y + 20);
        g.fillStyle = ink1; g.font = '500 26px ' + SERIF; var v = U.num(mm.v, mm.d); g.fillText(v, x, y + 50);
        if (k.unit) { var vw = g.measureText(v).width; g.fillStyle = ink2; g.font = '500 12px ' + UI; g.fillText(k.unit, x + vw + 4, y + 50); }
        g.fillStyle = ink3; g.font = '400 11px ' + UI; g.fillText(U.template(k.caption || '', { known: U.int(mm.known) }).slice(0, 26), x, y + 66);
      });
      y += 72;
    }
    y += 6; g.fillStyle = ink1; g.fillRect(cx + pad, y, cwid - pad * 2, 1); y += 12;
    leg.forEach(function (l) {
      y += 25;
      glyph(g, l.shape, cx + pad + 6, y - 5, 5.5, l.col);
      g.fillStyle = ink1; g.font = '500 13px ' + UI; g.fillText(l.label, cx + pad + 22, y);
      g.textAlign = 'right'; g.fillStyle = ink2; g.font = '500 12px ' + UI; g.fillText(l.right, cx + cwid - pad, y); g.textAlign = 'left';
    });
    // footer: sources and as-of
    g.fillStyle = night ? css('--surface-0-solid') : surf; g.fillRect(0, H - FOOT, W, FOOT);
    g.fillStyle = rule; g.fillRect(0, H - FOOT, W, 1);
    var d = cfg.drawer || {};
    g.fillStyle = ink3; g.font = '400 11.5px ' + UI;
    var src = 'Sources: ' + (d.sources || []).join(' · ');
    while (g.measureText(src).width > W - 460 && src.length > 20) src = src.replace(/\s·\s[^·]*$/, '') + '';
    g.fillText(src, 28, H - 19);
    g.textAlign = 'right'; g.fillStyle = ink2; g.font = '500 11.5px ' + UI; g.fillText((d.asOf || '') + ' · © OpenStreetMap contributors' + (RBX.map && RBX.map.__rbxBasemapMode === 'online' ? ' · © OpenMapTiles' : '') + ' · Natural Earth', W - 28, H - 19); g.textAlign = 'left';
    return cv;
  };
  E.image = function () {
    if (!RBX.map) { RBX.toast('The map image needs the interactive map, which could not load here.'); return; }
    if (RBX.state.view === 'ppa') { RBX.toast('Switch to a map view to download its image.'); return; }
    var fr = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
    fr.then(function () {
      E.grabMap(function (mc) {
        var cv;
        try { cv = E.composite(mc); } catch (e) { RBX.toast('Could not build the map image in this browser.'); return; }
        var name = base() + '-' + RBX.state.view + '-map' + stamp() + '.png';
        var fallback = function () { try { var w = window.open(); if (w) { w.document.title = name; w.document.body.style.margin = 0; var im = w.document.createElement('img'); im.src = cv.toDataURL('image/png'); im.style.maxWidth = '100%'; w.document.body.appendChild(im); } else RBX.toast('Allow pop-ups to save the map image.'); } catch (e) { RBX.toast('Could not save the map image in this browser.'); } };
        try {
          cv.toBlob(function (blob) {
            if (!blob) { fallback(); return; }
            var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
            RBX.toast('Map image downloaded (1600 × 900)');
          }, 'image/png');
        } catch (e) { fallback(); }
      });
    });
  };

  // ------------------------------------------------------------------ menu
  RBX.header.menu.push(
    { id: 'png', order: 40, sep: true, label: 'Download map image (PNG)', icon: E.IMG_ICON, run: function () { E.image(); }, when: function () { return RBX.state.view !== 'ppa' && !!RBX.map; } },
    { id: 'csv', order: 50, label: function () { return 'Download sites shown (CSV)'; }, icon: E.ICON, run: function () { E.sitesCsv(); }, when: function () { return RBX.state.view !== 'ppa'; } },
    { id: 'regcsv', order: 60, label: 'Download site register (CSV)', icon: E.ICON, run: function () { E.registerCsv(); } }
  );
})();
