/* RBX.theme: Paper / Night. Registers the basemap palettes (never mutating the kit's own light/dark objects),
   reads data colours from tokens.css so there is one source of truth, and re-applies data paint on switch. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var T = RBX.theme = {};

  if (window.RBXBasemap) {
    var BM = window.RBXBasemap;
    BM.palettes.paper = Object.assign({}, BM.palettes.light, {
      name: 'paper', land: '#F1ECE1', landContext: '#E9E5DB', sea: '#DAE2E0', sea200: '#D5DEDC', sea1000: '#D0DAD9', sea2000: '#CBD6D5',
      coastGlow: '#E7ECE8', coastline: '#A6B2AC', lake: '#D3DDDB', river: '#A3BCBC', border: '#9C9B8D', borderIntl: '#8E8D80',
      hsShadow: '#4A4638', hsAccent: '#6E6A5A', hsHighlight: '#FFFDF6', hsExaggeration: [4, 0.5, 6, 0.42, 8, 0.33, 11, 0.26, 14, 0.2],
      label: '#4C5550', labelMajor: '#1F2724', labelHalo: 'rgba(241,236,225,.94)', dot: '#1F2724', dotHalo: '#F1ECE1',
      region: 'rgba(60,66,58,.34)', sea_label: '#72898A'
    });
    BM.palettes.night = Object.assign({}, BM.palettes.dark, {
      name: 'night', land: '#0E1917', landContext: '#0B1413', sea: '#04090B', sea200: '#03080A', sea1000: '#030709', sea2000: '#020507',
      coastGlow: '#0D2A2A', coastline: '#244440', lake: '#061011', river: '#1B4646', border: '#3D524B', borderIntl: '#4A6159',
      wood: '#0F1B18', grass: '#101B19', park: '#0F1D19', residential: '#131D1B', ice: '#16211F', road: '#22302D', roadMajor: '#2B3B37', rail: '#1F2B28',
      hsShadow: '#000000', hsHighlight: '#6F948A', hsAccent: '#07100E', hsExaggeration: [4, 0.86, 6, 0.74, 8, 0.56, 11, 0.4, 14, 0.3],
      label: '#8AA098', labelMajor: '#D3E0DA', labelHalo: 'rgba(5,10,10,.9)', dot: '#D3E0DA', dotHalo: '#050A0A',
      region: 'rgba(160,190,180,.20)', sea_label: '#395757', waterLabel: '#4F7C7C'
    });
  }

  /** v1 per-fuel colours, used only when switches.tam_colour_mode === 'fuels' (not CVD-validated). */
  var FUEL_HUES = ['#8c6d31', '#7b3294', '#e08214', '#d73027', '#1a9850', '#6a51a3', '#2166ac', '#4d9221', '#999999'];

  var cache = {};
  /** Data colours for the current theme, read from the CSS custom properties in tokens.css. */
  T.pal = function () {
    var th = document.documentElement.getAttribute('data-theme') || 'paper';
    if (cache[th]) return cache[th];
    var cs = getComputedStyle(document.documentElement), v = function (n) { return cs.getPropertyValue(n).trim(); };
    var p = {
      theme: th, night: th === 'night',
      tier: [1, 2, 3, 4, 5].map(function (i) { return v('--tier-' + i); }),
      tierHot: [1, 2, 3, 4, 5].map(function (i) { return v('--tier-hot-' + i); }),
      fam: [0, 1, 2, 3].map(function (i) { return v('--fam-' + i); }),
      fuel: FUEL_HUES.slice(),
      hyd: [0, 1, 2].map(function (i) { return v('--hyd-' + i); }),
      hydHot: [0, 1, 2].map(function (i) { return v('--hyd-hot-' + i); }),
      unv: v('--hyd-unv'), tamFill: v('--tam-fill'), tamHalo: v('--tam-halo'),
      samdot: v('--samdot'), samdotStroke: v('--samdot-stroke'), selRing: v('--sel-ring'),
      stroke: v('--marker-stroke'), ink1: v('--ink-1'), ink2: v('--ink-2'), ink3: v('--ink-3'), ink4: v('--ink-4')
    };
    cache[th] = p;
    return p;
  };
  /** Colour class used for a TAM row's ring: technology family, or exact fuel in 'fuels' mode. */
  T.tamMode = function () { return ((RBX.config || {}).switches || {}).tam_colour_mode === 'fuels' ? 'fuels' : 'families'; };
  T.tamColour = function (row, pal) { pal = pal || T.pal(); return T.tamMode() === 'fuels' ? pal.fuel[row.fu] : pal.fam[row.fam]; };

  T.set = function (t, opts) {
    t = t === 'night' ? 'night' : 'paper';
    var S = RBX.state;
    S.theme = t;
    document.documentElement.setAttribute('data-theme', t);
    S.persist();
    var m = RBX.map;
    if (m && window.RBXBasemap && m.isStyleLoaded && RBX.layers && RBX.layers.ready) {
      try { window.RBXBasemap.applyTheme(m, t); } catch (e) { /* basemap handles its own failures */ }
      RBX.layers.applyTheme();
    }
    RBX.bus.emit('theme', t);
    if (!(opts && opts.silent)) S.writeHash();
  };
  T.toggle = function () { T.set(RBX.state.theme === 'night' ? 'paper' : 'night'); };
})();
