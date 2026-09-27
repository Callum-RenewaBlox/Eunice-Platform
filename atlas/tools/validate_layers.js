#!/usr/bin/env node
/* Regression check for the data layers (spec appendix B): validates a style dumped from a running atlas page
   with @maplibre/maplibre-gl-style-spec validateStyleMin. Dump the style in the browser console (or the QA
   harness) with   copy(JSON.stringify(RBX.map.getStyle()))   and save it to a file, then:
     NODE_PATH=<dir with @maplibre/maplibre-gl-style-spec> node atlas/tools/validate_layers.js style.json
   Exit code 1 on any error. Basemap layers are validated too (the kit ships its own validator). */
const fs = require('fs');
const spec = require('@maplibre/maplibre-gl-style-spec');
const style = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// inline GeoJSON sources are large: stub them, the validator only needs their type
Object.keys(style.sources || {}).forEach(k => { const s = style.sources[k]; if (s.type === 'geojson') s.data = { type: 'FeatureCollection', features: [] }; });
const errs = spec.validateStyleMin(style);
const data = (style.layers || []).filter(l => /^(sam|hydro|tam|sel|hover)-/.test(l.id)).map(l => l.id);
console.log('layers: ' + style.layers.length + ' (data: ' + data.join(', ') + ')');
errs.forEach(e => console.log('ERROR ' + e.message));
console.log(errs.length ? errs.length + ' error(s)' : '0 errors');
process.exit(errs.length ? 1 : 0);
