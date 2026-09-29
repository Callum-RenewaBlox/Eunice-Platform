/* RBX.data: decode the compact columnar payload (the build’s compact() encoder) into rows, derive the map properties
   (sv, sk, fam, band, …) and build GeoJSON. Audience-specific derivations go through RBX.hooks.derive. */
(function () {
  'use strict';
  var RBX = window.RBX, U = RBX.util;
  var D = RBX.data = { rows: {}, byKey: {}, geo: {}, meta: {} };

  // TAM technology families (spec 3.3): Landfill · Digestion · Thermal · Other
  var FAM_OF = { 'Landfill gas': 0, 'Biogas (AD)': 1, 'Sewage gas': 1, 'Biomass': 2, 'Waste / EfW': 2, 'Fuelled (biomass/AD/EfW)': 2,
    'Advanced fuel': 3, 'Biofuel - other': 3, 'Biodiesel': 3 };
  D.FAM_OF = FAM_OF;
  D.BAND_KW = [250, 1000, 5000, 20000];
  D.band = function (kw) { kw = kw || 0; for (var i = 0; i < 4; i++) if (kw < D.BAND_KW[i]) return i; return 4; };
  D.CONF = ['High', 'Medium', 'Low', 'Unverified'];

  D.decode = function (packed) {
    if (!packed || !packed.c) return [];
    var n = packed.n, cols = packed.c, dict = packed.d || {}, sp = packed.sp || {}, keys = Object.keys(cols), out = new Array(n);
    for (var i = 0; i < n; i++) {
      var r = {};
      for (var k = 0; k < keys.length; k++) {
        var f = keys[k], v = cols[f][i];
        r[f] = (dict[f] && v != null) ? dict[f][v] : v;
      }
      out[i] = r;
    }
    // sparse columns: {i: [row indices], v: [values]}; every other row gets null
    Object.keys(sp).forEach(function (f) {
      for (var j = 0; j < n; j++) out[j][f] = null;
      sp[f].i.forEach(function (ix, m) { out[ix][f] = sp[f].v[m]; });
    });
    return out;
  };

  // ------------------------------------------------------------------ default derivations (client semantics)
  RBX.hooks.derive = RBX.hooks.derive || {};
  var H = RBX.hooks.derive;
  /** SAM: size ∝ √installed kW; Tier 1 on top, then small above large (spec 5.1, 5.3). */
  H.sam = H.sam || function (r, ctx) {
    r.sv = Math.sqrt((r.kw || 0) / ctx.samMax);
    r.sk = (6 - r.t) * 1e5 - (r.kw || 0);
    r.pr = 1;
  };
  H.hydro = H.hydro || function (r, ctx) {
    r.sv = Math.sqrt((r.kw || 0) / ctx.hydroMax);
    r.sk = -(r.kw || 0);
  };
  H.tam = H.tam || function () {};

  D.init = function (raw, cfg) {
    var fuels = (cfg.labels && cfg.labels.fuels) || [];
    var sam = D.decode(raw.sam), hyd = D.decode(raw.hydro), tam = D.decode(raw.tam);
    var ctx = {
      samMax: Math.max.apply(null, sam.map(function (r) { return r.kw || 0; })) || 1,
      hydroMax: Math.max.apply(null, hyd.map(function (r) { return r.kw || 0; })) || 1,
      cfg: cfg, raw: raw
    };
    D.meta = ctx;
    sam.forEach(function (r, i) {
      r.id = i; r.kind = 'sam';
      r.name = r.name || r.op || r.pc;
      r.cap = r.kw || 0;
      r.outcode = U.outcode(r.pc);
      H.sam(r, ctx);
    });
    hyd.forEach(function (r, i) {
      r.id = i; r.kind = 'hydro';
      r.c = D.CONF.indexOf(r.conf); if (r.c < 0) r.c = 3;
      r.expc = r.exp === 'No export' ? 1 : 0;
      r.cap = r.inst != null ? r.inst : r.kw;
      H.hydro(r, ctx);
    });
    var samByKey = Object.create(null);
    sam.forEach(function (r) { samByKey[r.key] = r; });
    tam.forEach(function (r, i) {
      r.id = i; r.kind = 'tam';
      if (!r.key) r.key = r.ro;
      r.name = r.n; r.fuel = r.f;
      r.fu = fuels.indexOf(r.f); if (r.fu < 0) r.fu = 8;
      r.fam = FAM_OF[r.f] != null ? FAM_OF[r.f] : 3;
      r.sh = r.ro ? 't' : 'c';
      r.ap = r.p ? 1 : 0;
      r.band = D.band(r.kw);
      r.cap = r.kw || 0;
      r.samRow = r.sam && Object.prototype.hasOwnProperty.call(samByKey, r.sam) ? samByKey[r.sam] : null;
      if (r.samRow) r.samRow.tamRow = r;
      r.inSam = r.sam ? 1 : 0;
      // half-diameter + 3 at icon-size 1 (selection and hover ring radius, spec 5.1)
      var d = [7, 9.5, 12.5, 17, 23][r.band];
      r.hr = d / 2 * (r.sh === 't' ? 1.22 : 1) + 3;
      H.tam(r, ctx);
    });
    D.rows = { sam: sam, hydro: hyd, tam: tam };
    D.byKey = { sam: samByKey, hydro: Object.create(null), tam: Object.create(null) };
    hyd.forEach(function (r) { D.byKey.hydro[r.key] = r; });
    tam.forEach(function (r) { D.byKey.tam[r.key] = r; });
    D.ppa = raw.ppa || null;
    RBX.bus.emit('data', D);
    return D;
  };

  /** Find a row by key in any layer (first match in view order). */
  D.find = function (key, prefer) {
    var order = [prefer, 'sam', 'hydro', 'tam'];
    if (typeof key !== 'string' || !key) return null;
    for (var i = 0; i < order.length; i++) {
      var k = order[i];
      if (k && D.byKey[k] && Object.prototype.hasOwnProperty.call(D.byKey[k], key)) return D.byKey[k][key];
    }
    return null;
  };

  // ------------------------------------------------------------------ GeoJSON (every feature has a numeric id for feature-state)
  var PROPS = {
    sam: function (r) { return { id: r.id, key: r.key, t: r.t, kw: r.kw || 0, sv: r.sv, sk: r.sk, pr: r.pr == null ? 1 : r.pr }; },
    hydro: function (r) { return { id: r.id, key: r.key, c: r.c, kw: r.kw || 0, inst: r.inst || 0, exp: r.expc, sv: r.sv, sk: r.sk }; },
    tam: function (r) {
      return { id: r.id, key: r.key, fam: r.fam, fu: r.fu, sh: r.sh, ap: r.ap, band: r.band, kw: r.kw || 0, bt: r.bt, sam: r.inSam,
        cc: RBX.theme.tamMode() === 'fuels' ? 'f' + r.fu : String(r.fam) };
    }
  };
  RBX.hooks.props = RBX.hooks.props || {};
  D.geojson = function (kind) {
    var extra = RBX.hooks.props[kind];
    return { type: 'FeatureCollection', features: D.rows[kind].map(function (r) {
      var p = PROPS[kind](r);
      if (extra) Object.assign(p, extra(r));
      return { type: 'Feature', id: r.id, geometry: { type: 'Point', coordinates: [r.lon, r.lat] }, properties: p };
    }) };
  };

  /** Register rows in the v1 DATA.sites shape for the PPA module (client: neutral `ref`, softened labels). */
  D.register = function () {
    var cfg = RBX.config, L = cfg.labels || {}, cls = L.ppaClass || {}, rego = L.rego || {};
    var hook = RBX.hooks.registerRow;
    return D.rows.sam.map(function (r) {
      var o = {
        key: r.key, operator: r.op || null, site: r.site || r.name, name: r.name, town: r.town || null, postcode: r.pc,
        installed_kw: r.kw, commissioned: r.comm, ppa_class: cls[r.ppa] || r.ppa, ppa: r.ppa,
        offtaker: r.off || null, self_certs: r.self ? 1 : 0, gen_tariff_p_kwh_2026_27: r.fitGen,
        fit_end_date: r.fitEnd || null, yrs_subsidy_left: r.yrsLeft, rego_status: rego[r.rego] || r.rego, rego: r.rego,
        tier: r.t, lat: r.lat, lon: r.lon
      };
      if (r.ref != null) o.ref = r.ref;
      return hook ? hook(o, r) : o;
    });
  };
})();
