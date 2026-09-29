#!/usr/bin/env python3
"""RenewaBlox Atlas v2 build.

    python3 atlas/build.py                     build both apps → ../client_atlas_v2.html, ../investor_atlas_v2.html
    python3 atlas/build.py --only client       build one app
    python3 atlas/build.py --check             rebuild in memory and fail if the committed HTML differs (CI)
    python3 atlas/build.py --qa                also print the size table and the token map

Every build runs, and fails on any violation of:
  * the canonical-number asserts (spec appendix A), recomputed from atlas/data
  * the MUST-preserve copy check (spec section 12) over the final HTML
  * the client-safety contract (spec section 13): data-key allowlist, textual deny-list over the
    WHOLE client HTML (comments included), code partition (no investor/ paths in the client bundle)
  * the size budget (data ≤ 170 KB per app, HTML ≤ 1.2 MB)

Inputs: atlas/apps/<app>/{template.html, manifest.json, config.json}, atlas/core/**, atlas/data/**.
An app whose template.html is missing is skipped with a message (so the client can build on its own).
"""
import argparse
import html as htmllib
import json
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(HERE, 'data')
OUT = {'client': os.path.join(REPO, 'client_atlas_v2.html'), 'investor': os.path.join(REPO, 'investor_atlas_v2.html')}
FONTS_URL = ('https://fonts.googleapis.com/css2?family=Inter:wght@400..700&family=Newsreader:ital,opsz,wght@'
             '0,6..72,400..600;1,6..72,400..500&display=swap')
INIT_MARKER = '/*__ATLAS_INIT__*/'
# MapLibre from jsDelivr with Subresource Integrity. The hashes are of the npm tarball's dist files (jsDelivr /npm/
# serves them byte for byte); the tarball was checked against the registry's sha512 integrity. Bump all three together.
MAPLIBRE_VERSION = '4.7.1'
MAPLIBRE_SRI = {'js': 'sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj',
                'css': 'sha384-MinO0mNliZ3vwppuPOUnGa+iq619pfMhLVUXfC4LHwSCvF9H+6P/KO4Q7qBOYV5V'}


def cdn_head():
    """Third-party tags, all non-blocking (a hanging CDN must never freeze the shell): the fonts CSS and the
    MapLibre CSS load as preload→stylesheet (with a <noscript> fallback), MapLibre JS loads async;
    RBX.mapctl.init waits for window.maplibregl (8 s, then the fallback panel)."""
    ml = 'https://cdn.jsdelivr.net/npm/maplibre-gl@%s/dist/maplibre-gl.' % MAPLIBRE_VERSION
    sri = ' integrity="%s" crossorigin="anonymous"'
    swap = ' onload="this.onload=null;this.rel=\'stylesheet\'"'
    return ('<link rel="preload" as="style" href="%s"%s><noscript><link rel="stylesheet" href="%s"></noscript>\n'
            '<link rel="preload" as="style" href="%scss"%s%s><noscript><link rel="stylesheet" href="%scss"%s></noscript>\n'
            '<script async src="%sjs"%s onerror="window.__rbxMaplibreFailed=1"></script>'
            % (FONTS_URL, swap, FONTS_URL, ml, sri % MAPLIBRE_SRI['css'], swap, ml, sri % MAPLIBRE_SRI['css'],
               ml, sri % MAPLIBRE_SRI['js']))
DATA_BUDGET = 170 * 1024
HTML_BUDGET = int(1.2 * 1024 * 1024)

FAVICON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
               '<rect x="0" y="0" width="9" height="9" rx="2" fill="#8FD14F"/>'
               '<rect x="11" y="0" width="9" height="9" rx="2" fill="#3E8A6A"/>'
               '<rect x="0" y="11" width="9" height="9" rx="2" fill="#2F6B55"/>'
               '<rect x="11" y="11" width="9" height="9" rx="2" fill="#245744"/></svg>')


class BuildError(Exception):
    pass


def fail(msg):
    raise BuildError(msg)


def load(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return json.load(fh)


def read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return fh.read()


# ============================================================================ formatting helpers
def gb(n, d=0):
    """en-GB number format."""
    return f'{n:,.{d}f}'


def mw_str(kw):
    """MW values below 1,000 have 1 dp; at 1,000 MW and above 0 dp with a thousands separator."""
    mw = kw / 1000.0
    return gb(mw, 0) if mw >= 1000 else gb(mw, 1)


def abbr(v):
    v = round(v)
    if v >= 1e9:
        return '£%.2fbn' % (v / 1e9)
    if v >= 1e6:
        return '£%.1fM' % (v / 1e6)
    if v >= 1e3:
        return '£%.0fk' % (v / 1e3)
    return '£%d' % v


# ============================================================================ data assembly
PPA_CLASS = {'neg': 'Negotiated export PPA', 'fit': 'FiT standard export tariff (no PPA)',
             'btm': 'No export — behind the meter', 'unk': 'Unknown — no FiT match'}
REGO_LABELS = {
    'softened': {'active': 'Active', 'declining': 'Certificates declining', 'ceased': 'No recent certificates',
                 'none': 'No REGO certificates'},
    'raw': {'active': 'active', 'declining': 'lagging/winding down', 'ceased': 'likely ceased', 'none': 'no REGO certs'},
}

# client data allowlist (spec 13.1) — a closed set; any other key fails the build
CLIENT_ALLOW = {
    'sam': {'key', 'name', 'site', 'town', 'la', 'pc', 'op', 't', 'kw', 'kwOn', 'kwBm', 'comm', 'lat', 'lon',
            'ppa', 'off', 'self', 'fitGen', 'fitEnd', 'yrsLeft', 'rego', 'ref'},
    'hydro': {'key', 'name', 'exp', 'conf', 'kw', 'inst', 'mec', 'lat', 'lon'},
    'tam': {'key', 'n', 'f', 'kw', 'bm', 'p', 'bt', 'ro', 'units', 'sam', 'lat', 'lon'},
    'ppa': {'realised', 'kpi', 'fwd', 'spread', 'fit', 'cpi'},
}


def apply_sam_kw_source(rows, source):
    """Owner decision 1. 'fit_register' (default): installed kW from the FiT register (Rotherdale Farm and
    Scrivelsby = 998 kW, SAM = 143.6 MW). 'dno_split': installed = onsite + available-for-BM where that
    split is known and smaller (499 kW for those two sites, SAM = 142.6 MW)."""
    if source == 'fit_register':
        return rows
    if source != 'dno_split':
        fail('switches.sam_kw_source must be "fit_register" or "dno_split", got %r' % source)
    dno = load(DATA, 'shared', 'sam_kw_dno.json')['kw']
    return [dict(r, kw=dno[r['key']]) if r['key'] in dno else r for r in rows]


def assemble_client(cfg):
    sw = cfg.get('switches', {})
    sam = apply_sam_kw_source(load(DATA, 'client', 'sam.json'), sw.get('sam_kw_source', 'fit_register'))
    reg = {r['key']: r for r in load(DATA, 'client', 'ppa_register.json')}
    rows = []
    for r in sam:
        x = dict(r)
        x.update({k: v for k, v in reg[r['key']].items() if k != 'key'})
        rows.append(x)
    data = {'sam': rows, 'hydro': load(DATA, 'client', 'hydro.json'), 'tam': load(DATA, 'shared', 'tam.json'),
            'ppa': load(DATA, 'shared', 'ppa_prices.json')}
    return data


def assemble_investor(cfg):
    """Investor data: the client-safe fields plus the commercial overlay. The investor app decides what to show."""
    sw = cfg.get('switches', {})
    sam = apply_sam_kw_source(load(DATA, 'investor', 'sam.json'), sw.get('sam_kw_source', 'fit_register'))
    creg = {r['key']: r for r in load(DATA, 'client', 'ppa_register.json')}
    ireg = {r['key']: r for r in load(DATA, 'investor', 'ppa_register.json')}
    rows = []
    for r in sam:
        x = dict(r)
        c = creg[r['key']]
        x.update({k: v for k, v in c.items() if k not in ('key', 'ref')})
        x['regoRaw'] = ireg[r['key']]['rego_status']
        x['offRaw'] = ireg[r['key']].get('offtaker_raw')
        rows.append(x)
    extra = load(DATA, 'investor', 'tam_extra.json')
    tam = []
    for t in load(DATA, 'shared', 'tam.json'):
        x = dict(t)
        ex = extra.get(t['key'], {})
        x['src'] = ex.get('src')
        if 'bm' in ex:
            x['bm'] = ex['bm']
        tam.append(x)
    return {'sam': rows, 'hydro': load(DATA, 'investor', 'hydro.json'), 'tam': tam,
            'ppa': load(DATA, 'shared', 'ppa_prices.json'), 'model': load(DATA, 'investor', 'model.json')}


ASSEMBLE = {'client': assemble_client, 'investor': assemble_investor}


def compact(rows, dict_fields=()):
    """Columnar arrays; strings in dict_fields are dictionary-encoded. Decoded by core/js/data.js."""
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    cols, dicts, sparse = {}, {}, {}
    for k in keys:
        col = [r.get(k) for r in rows]
        nn = [i for i, v in enumerate(col) if v is not None]
        if k not in dict_fields and len(nn) < 0.4 * len(col):
            sparse[k] = {'i': nn, 'v': [col[i] for i in nn]}
            continue
        if k in dict_fields:
            vocab = []
            idx = {}
            enc = []
            for v in col:
                if v is None:
                    enc.append(None)
                    continue
                if v not in idx:
                    idx[v] = len(vocab)
                    vocab.append(v)
                enc.append(idx[v])
            cols[k], dicts[k] = enc, vocab
        else:
            cols[k] = col
    out = {'n': len(rows), 'c': cols}
    if dicts:
        out['d'] = dicts
    if sparse:
        out['sp'] = sparse
    return out


DICT_FIELDS = {'sam': ('town', 'la', 'op', 'ppa', 'off', 'rego', 'fitEnd', 'g', 'dev', 'regoRaw', 'offRaw'),
               'hydro': ('exp', 'conf'), 'tam': ('f', 'src')}


def pack_data(data):
    out = {}
    for k, v in data.items():
        if k == 'tam':
            # a TAM key equals its RO reference when there is one: ship it once (data.js restores key = ro)
            v = [dict(r, key=None) if r.get('ro') and r.get('key') == r.get('ro') else r for r in v]
        if isinstance(v, list):
            out[k] = compact(v, DICT_FIELDS.get(k, ()))
        else:
            out[k] = v
    return out


def js_json(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return s.replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


# ============================================================================ canonical numbers (appendix A)
def near(a, b, tol=0.5):
    return abs(a - b) <= tol


def assert_numbers(app, data, sw):
    sam, hyd, tam, ppa = data['sam'], data['hydro'], data['tam'], data['ppa']
    fit_reg = sw.get('sam_kw_source', 'fit_register') == 'fit_register'
    checks = []

    def chk(name, got, want, tol=0):
        ok = (abs(got - want) <= tol) if isinstance(want, (int, float)) and not isinstance(want, bool) else got == want
        checks.append((name, ok, got, want))

    chk('SAM sites', len(sam), 129)
    chk('SAM tiers', [sum(1 for r in sam if r['t'] == t) for t in range(1, 6)], [4, 41, 41, 37, 6])
    chk('SAM largest kW', max(r['kw'] for r in sam), 5936)
    chk('SAM installed Σ kW', sum(r['kw'] for r in sam), 143571 if fit_reg else 142573)
    chk('SAM available-for-BM Σ kW', sum(r['kwBm'] or 0 for r in sam), 90465)
    chk('SAM BM known', sum(1 for r in sam if r['kwBm'] is not None), 105)
    chk('SAM keys unique', len({r['key'] for r in sam}), 129)
    chk('Hydro sites', len(hyd), 57)
    chk('Hydro stranded Σ', sum(r['kw'] for r in hyd), 15153)
    chk('Hydro installed Σ', sum(r['inst'] for r in hyd), 36227)
    chk('Hydro export Σ', sum(r['mec'] for r in hyd), 21075)
    chk('Hydro largest stranded', max(r['kw'] for r in hyd), 1309)
    chk('Hydro confidence', [sum(1 for r in hyd if r['conf'] == c) for c in ('High', 'Medium', 'Low', 'Unverified')], [37, 8, 4, 8])
    chk('Hydro export class', [sum(1 for r in hyd if r['exp'] == e) for e in ('Export', 'No export')], [48, 9])
    chk('Hydro keys unique', len({r['key'] for r in hyd}), 57)
    chk('TAM sites', len(tam), 1309)
    chk('TAM Σ kW', sum(r['kw'] or 0 for r in tam), 3611922)
    chk('TAM RO / FiT', [sum(1 for r in tam if r['ro']), sum(1 for r in tam if not r['ro'])], [945, 364])
    chk('TAM approx', sum(1 for r in tam if r['p']), 220)
    chk('TAM largest', max(r['kw'] or 0 for r in tam), 99800)
    chk('TAM in SAM', sum(1 for r in tam if r['sam']), 129)
    chk('TAM BM tiers', [sum(1 for r in tam if r['bt'] == t) for t in (1, 2, 3, 4, 5, 0)], [78, 294, 342, 455, 57, 83])
    chk('TAM Scotland MW', round(sum(r['kw'] or 0 for r in tam if r['bt'] == 0) / 1000), 275)
    fuels = {}
    for r in tam:
        f = fuels.setdefault(r['f'], [0, 0])
        f[0] += 1
        f[1] += r['kw'] or 0
    want = {'Landfill gas': (435, 961), 'Fuelled (biomass/AD/EfW)': (262, 877), 'Biomass': (81, 715),
            'Waste / EfW': (81, 616), 'Biogas (AD)': (294, 234), 'Sewage gas': (138, 143), 'Advanced fuel': (4, 38),
            'Biofuel - other': (11, 27), 'Biodiesel': (3, 1)}
    chk('TAM fuels', {k: (v[0], round(v[1] / 1000)) for k, v in fuels.items()}, want)
    stacks = Counter((r['lat'], r['lon']) for r in tam)
    chk('TAM stacks', sorted([c for c in stacks.values() if c > 1], reverse=True), [12, 3, 2, 2, 2, 2, 2])
    if app == 'client':
        chk('TAM bm known', sum(1 for r in tam if r['bm'] is not None), 727)
        chk('TAM bm Σ MW', round(sum(r['bm'] or 0 for r in tam) / 1000, 1), 2489.0)
    chk('PPA kpi', ppa['kpi'], {'base12': 8.52, 'win26': 12.5, 'cal28': 7.74, 'fit': 7.64, 'asOf': '2026-08-11'})
    chk('PPA realised months', [len(ppa['realised']), ppa['realised'][0]['m'], ppa['realised'][-1]['m']], [24, '2024-08', '2026-07'])
    chk('PPA forward blocks', [f['p'] for f in ppa['fwd']], [12.601, 12.391, 8.605, 8.25, 7.744])
    chk('PPA forward keys', [f['k'] for f in ppa['fwd']], ['Q4-2026', 'Q1-2027', 'Q2-2027', 'H2-2027*', 'Cal-2028'])
    chk('PPA class', [sum(1 for r in sam if r['ppa'] == c) for c in ('neg', 'fit', 'btm', 'unk')], [108, 16, 4, 1])
    chk('PPA offtaker null', sum(1 for r in sam if r['off'] is None), 37)
    chk('PPA rego', [sum(1 for r in sam if r['rego'] == c) for c in ('active', 'none', 'ceased', 'declining')], [64, 40, 14, 11])
    ext = {r['off'] for r in sam if r['off'] and r['off'] != 'Generator is sole holder'}
    chk('PPA counterparties (external)', len(ext), 21)

    if app == 'investor':
        pr = [r for r in sam if r.get('tcv') is not None]
        chk('INV priced', len(pr), 105)
        chk('INV Σav', sum(r['av'] for r in pr), 90465)
        chk('INV Σbtc', round(sum(r['btc'] for r in pr), 3), 639.394, 0.001)
        chk('INV Σtcv', sum(r['tcv'] for r in pr), 221933920)
        chk('INV ΣtcvT', sum(r['tcvT'] for r in pr), 327351233)
        chk('INV Σen', sum(r['en'] for r in pr), 174685396)
        chk('INV max tcv', max(r['tcv'] for r in pr), 9267581)
        chk('INV hydro Σbtc', round(sum(r['btc'] for r in hyd), 3), 176.813, 0.001)
        chk('INV hydro Σtcv', sum(r['tcv'] for r in hyd), 13644961)
        chk('INV hydro ΣtcvT', sum(r['tcvT'] for r in hyd), 35624972)
        rate = {}
        for t in range(1, 6):
            g = [r for r in pr if r['t'] == t]
            rate[t] = sum(r['tcv'] for r in g) / sum(r['av'] for r in g)
        chk('INV TCVRATE', [round(rate[t], 2) for t in range(1, 6)], [2671.41, 2544.82, 2438.84, 2329.91, 2271.03])
        avr = sum(r['av'] for r in pr) / sum(r['inst'] for r in pr)
        chk('INV AVRATIO', round(avr, 5), 0.73392)
        chk('INV in BM tiers MW', round(sum(r['kw'] or 0 for r in tam if r['bt'] > 0) / 1000, 1), 3337.4)

        def bmkw(d):
            return d['bm'] if d.get('bm') is not None else (d['kw'] or 0) * avr

        pot = sum(bmkw(d) * rate[d['bt']] for d in tam if d['bt'] > 0)
        big = sum(bmkw(d) * rate[d['bt']] for d in tam if d['bt'] > 0 and (d['kw'] or 0) >= 10000)
        nbig = sum(1 for d in tam if d['bt'] > 0 and (d['kw'] or 0) >= 10000)
        chk('INV TCV potential', round(pot), 7165922831, 2)
        chk('INV TCV potential ≥10MW', round(big), 4080456539, 2)
        chk('INV sites ≥10MW', nbig, 76)
        chk('INV TCV potential abbr', abbr(pot), '£7.17bn')
    bad = [c for c in checks if not c[1]]
    if bad:
        fail('canonical-number asserts failed:\n' + '\n'.join('  %s: got %r, want %r' % (n, g, w) for n, _, g, w in bad))
    return len(checks)


# ============================================================================ build-time tokens for copy
def tokens_for(data):
    sam, hyd, tam = data['sam'], data['hydro'], data['tam']
    s_kw = sum(r['kw'] for r in sam)
    t_kw = sum(r['kw'] or 0 for r in tam)
    h_str = sum(r['kw'] for r in hyd)
    return {
        'sam_n': gb(len(sam)), 'sam_mw': mw_str(s_kw), 'sam_mw0': gb(round(s_kw / 1000)),
        'tam_n': gb(len(tam)), 'tam_mw': gb(round(t_kw / 1000)), 'tam_gw': '%.1f' % (t_kw / 1e6),
        'hydro_n': gb(len(hyd)), 'hydro_str_mw': mw_str(h_str),
        'hydro_inst_mw': mw_str(sum(r['inst'] for r in hyd)), 'hydro_mec_mw': mw_str(sum(r['mec'] for r in hyd)),
        'highlands_n': str(sum(1 for r in hyd if r['lat'] >= 56.4 and r['lon'] <= -3.3)),
        'sam_bm_mw': mw_str(sum(r['kwBm'] or 0 for r in sam)),
        'sam_bm_n': str(sum(1 for r in sam if r['kwBm'] is not None)),
        'tam_ro': gb(sum(1 for r in tam if r['ro'])), 'tam_fit': gb(sum(1 for r in tam if not r['ro'])),
        'as_of': '11 Aug 2026',
    }


def investor_tokens(data):
    """Investor-only copy tokens (headlines, as-of stamps), computed from the investor data (spec 6.3a: never
    hand-typed). Only merged for the investor build, so none of these values can reach the client HTML."""
    sam, hyd, tam = data['sam'], data['hydro'], data['tam']
    pr = [r for r in sam if r.get('tcv') is not None]
    rate = {t: sum(r['tcv'] for r in pr if r['t'] == t) / (sum(r['av'] for r in pr if r['t'] == t) or 1) for t in range(1, 6)}
    avr = sum(r['av'] for r in pr) / (sum(r['inst'] for r in pr) or 1)
    pot = sum((d['bm'] if d.get('bm') is not None else (d['kw'] or 0) * avr) * rate[d['bt']] for d in tam if d['bt'] > 0)
    asof = data.get('model', {}).get('asOf', {})
    return {
        'inv_priced': gb(len(pr)), 'inv_tcv': abbr(sum(r['tcv'] for r in pr)), 'inv_tcv_t': abbr(sum(r['tcvT'] for r in pr)),
        'tam_pot': abbr(pot), 'hydro_tcv': abbr(sum(r['tcv'] for r in hyd)), 'hydro_tcv_t': abbr(sum(r['tcvT'] for r in hyd)),
        'model_as_of': asof.get('model', ''), 'registers_as_of': asof.get('registers', ''),
    }


def strip_private(obj):
    """Drop every dict key that starts with '_' (config.json notes for maintainers: `_doc`, `_sam_kw_source`, …).
    They document owner decisions and alternatives and must never be inlined into a page (either app)."""
    if isinstance(obj, dict):
        return {k: strip_private(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith('_'))}
    if isinstance(obj, list):
        return [strip_private(x) for x in obj]
    return obj


def fill_tokens(obj, tok):
    if isinstance(obj, str):
        def rep(m):
            k = m.group(1)
            if k not in tok:
                fail('unknown copy token {{%s}}' % k)
            return tok[k]
        return re.sub(r'\{\{([a-z0-9_]+)\}\}', rep, obj)
    if isinstance(obj, list):
        return [fill_tokens(x, tok) for x in obj]
    if isinstance(obj, dict):
        return {k: fill_tokens(v, tok) for k, v in obj.items()}
    return obj


# ============================================================================ CSS / JS bundling
def strip_css_comments(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'\n\s*\n+', '\n', css)
    return css.strip() + '\n'


def bundle(app, manifest, warnings):
    css_parts, js_parts, used = [], [], []
    optional = set(manifest.get('optional', []))
    for kind, parts in (('css', css_parts), ('js', js_parts)):
        for rel in manifest[kind]:
            p = os.path.join(HERE, rel)
            if not os.path.exists(p):
                if rel in optional:
                    warnings.append('optional %s missing: %s (placeholder used)' % (kind, rel))
                    continue
                fail('manifest %s: missing %s' % (app, rel))
            used.append(rel)
            src = read(p)
            if kind == 'css':
                parts.append(strip_css_comments(src))
            else:
                parts.append(';' + src.strip() + '\n')
    if app == 'client':
        leaked = [u for u in used if '/investor/' in u or u.startswith('apps/investor')]
        if leaked:
            fail('code partition: investor paths in the client bundle: %s' % leaked)
    return ''.join(css_parts), ''.join(js_parts), used


# ============================================================================ MUST-preserve copy check (spec 12)
COPY_COMMON = [
    'no Watt wasted', 'TAM · 1,309', 'SAM · 129', 'PPA Benchmark',
    'Tier 1 · Highest', 'Tier 2 · Strong', 'Tier 3 · Moderate', 'Tier 4 · Modest', 'Tier 5 · Lower',
    'Scotland · no BM revenue', 'Landfill gas', 'Fuelled (biomass/AD/EfW)', 'Biomass', 'Waste / EfW',
    'Biogas (AD)', 'Sewage gas', 'Advanced fuel', 'Biofuel - other', 'Biodiesel',
    'Approximate location (postcode district)', 'postcodes.io', 'Sources & method',
]
COPY = {
    'client': COPY_COMMON + [
        'Peaker Model', 'Hydro · 57', 'RenewaBlox Client Atlas', '#0B2E2A', '#8FD14F',
        '57 sites · 15.2 MW stranded', '129 sites · 144 MW', '1,309 sites · 3,612 MW',
        'BM Tier — projected p/kWh (next 12m)',
        '29.6p avg · 122p top 5%', '25.3p avg · 104p top 5%', '21.7p avg · 80p top 5%',
        '18.0p avg · 61p top 5%', '16.0p avg · 50p top 5%',
        'Installed', 'Onsite demand / Stranded', 'Available for BM', 'Offtaker', 'Sole holder · unbundled',
        'Not identified', 'Negotiated PPA', 'FiT standard', 'Behind meter', 'Unknown',
        'Projected Balancing Mechanism Revenues', 'Average', 'Top 5%', 'Offer-event frequency: ',
        '~2× GB average', '~1.5×', 'TAM · total addressable market', 'RO accredited', 'FiT accredited',
        'Capacity', 'Site aggregates', 'MPAN records', 'BM tier: ', '(indicative)', 'Subsidy: ',
        'No export', 'Installed capacity', 'Export capacity', 'stranded', 'All sizes', 'Over 1 MW', 'Under 1 MW',
        'Talk to us about this site', 'callum@renewablox.com', 'Stranded capacity shown',
        "29.6", "122", "25.3", "104", "21.7", "80", "18.0", "61", "16.0", "50",
    ],
    'investor': COPY_COMMON + [
        'Peaker plants', 'RenewaBlox Investor Atlas', '#16323A', '#1F6F78',
        # subtitles (spec 12.2 item 10)
        'Total Contract Value · Year 5 · 129 AD-peaker sites in the GB Balancing Mechanism',
        'Total addressable market · 1,309 subsidised biogas, biomass & EfW sites · 3,612 MW',
        'Total Contract Value · Year 5 · 57 stranded hydro units · 100% Bitcoin mining',
        'PPA & price benchmark · 129 SAM sites · applies across peakers and hydro',
        # KPI band labels + as-of stamps (spec 10.1)
        'Avail. for BM', 'BTC mined', 'TCV (Treasury)', 'In BM tiers', 'TCV Potential', 'Sites shown', 'Capacity shown',
        'Counterparties', 'Realised 12m', 'Winter-26 fwd', 'Model · 16 Jun 2026 · Indicative; not investment advice.',
        'Registers · Jul–Aug 2026', 'Prices · 11 Aug 2026', 'AD-scale only (<10 MW)',
        # legends (spec 6.3c investor, 12.2 items 3–4, 8)
        'Balancing Mechanism Tiers', 'avg BM revenue vs 8.0p wholesale baseline', 'Awaiting BM figure', 'Stranded Hydro',
        'Export-limited', 'No export',
        '+% = average BM revenue per tier vs a wholesale market baseline. TCV is per kW of available-for-BM; 24 sites '
        '(hollow) await a figure. Card offtaker is inferred from the largest external REGO certificate holder — strong '
        'evidence of who buys the power, not contractual proof. Full detail on the PPA Benchmark tab.',
        'Markers are unfilled: ring colour = technology, shape = subsidy (triangle = RO, circle = FiT), size = capacity, '
        'dashed = approximate location. BM tier is indicative, modelled from the verified SAM sites. TCV Potential applies '
        'the priced SAM sites’ own Year-5 TCV per kW-available (by tier) to each site’s available-for-BM capacity — the DNO '
        'maximum export capacity where the register gives one (727 sites), otherwise installed capacity at the SAM fleet’s '
        'ratio. Scotland sits outside the modelled tiers, so it carries no BM revenue and is excluded from TCV Potential.',
        'Stranded generation runs Bitcoin mining 24/7 — no grid export and no BM revenue, so TCV = mined BTC value.',
        # footers (spec 12.2 item 9)
        'RenewaBlox Investor Atlas · Year-5 Total Contract Values modelled from the Scrivelsby peaker and 1,000 kW '
        'stranded-hydro client cases, scaled across the portfolio. Sources: RenewaBlox_AD_BM_CRM & '
        'RenewaBlox_Hydro_Stranded (16 Jun 2026). Indicative; not investment advice.',
        'RenewaBlox Investor Atlas · TAM — every subsidised biogas, biomass, EfW, landfill and sewage-gas CHP holding an '
        'RO or FiT accreditation. Sources: DNO Embedded Capacity Registers (NGED, NPG, SPEN, SSEN Jul-2026, UKPN) + Ofgem '
        'FiT, RO and REGO registers (Aug-2026). Co-located records are collapsed to one marker per site with capacity '
        'capped at the DNO connection figure (194 MW of double-counting removed across 87 sites); 8 '
        'transmission-connected thermal stations >100 MW are excluded. 220 sites are plotted at postcode-district '
        'centroid (dashed). BM tier is indicative, modelled from the 129 verified SAM sites; Scotland sits outside the '
        'modelled tiers.',
        'RenewaBlox Investor Atlas · PPA & Price Benchmark — Elexon BMRS Market Index (APXMIDP) settlement data, '
        'Montel/EEX forward curve snapshot 11 Aug 2026, Ofgem Feed-in Tariff and REGO registers. Contracted PPA prices '
        'are private bilateral terms and are not shown anywhere; the counterparty is inferred from REGO certificate '
        'holdings.',
        # card fields (spec 12.2 item 7)
        'BTC mined (Yr 5)', 'TCV · no treasury', 'TCV · treasury', 'Operator', 'Offtaker', 'Export', 'Energy export',
        '£0 · 100% mining', ' confidence', 'Approx · postcode district', 'Exact · DNO register', 'In SAM',
        'Verified site', 'Installed capacity', 'Available for BM', 'Sole holder · unbundled', 'Not identified',
    ],
}
# PPA page copy lives in core/js/ppa.js (separate module); checked whenever that module is bundled.
COPY_PPA = [
    'PPA & Price Benchmark',
    'No contracted PPA price is shown anywhere — those are private bilateral contracts and are not obtainable from any source.',
    'Elexon MID, Aug 25 – Jul 26', '+47% vs last 12 months', 'below the CPI-linked FiT tariff',
    'statutory, CPI-linked, guaranteed', 'Win-26 vs Sum-27 — AD runs flat',
    'Realised — Elexon MID (EPEX)', 'Forward blocks — Montel / EEX, 11 Aug 2026',
    'FiT standard export tariff (7.64p, CPI-linked)', 'H2-2027*', 'Who holds the certificates', 'Site register',
    'Export arrangement', 'Certificate counterparty', 'Generating status', 'operator, town, postcode',
    'Supplier (largest external REGO holder)', 'FiT gen p/kWh', 'FiT ends', 'Yrs left',
    'The crossover.', '5% above market', 'Provenance.',
]


def norm_text(s):
    s = htmllib.unescape(s)
    s = s.replace('\\"', '"').replace("\\'", "'").replace('\\u00b7', '·').replace('\\u2014', '—')
    return re.sub(r'\s+', ' ', s)


def copy_check(app, html_out, has_ppa, warnings, sw=None):
    txt = norm_text(html_out)
    need = list(COPY.get(app, COPY_COMMON))
    if (sw or {}).get('sam_kw_source') == 'dno_split':
        need = [s for s in need if s != '129 sites · 144 MW']
    if has_ppa:
        need += COPY_PPA
    else:
        warnings.append('copy check: PPA strings skipped (core/js/ppa.js not bundled yet)')
    missing = [s for s in need if re.sub(r'\s+', ' ', s) not in txt]
    if missing:
        fail('MUST-preserve copy missing from %s build:\n  ' % app + '\n  '.join(missing))
    return len(need)


# ============================================================================ client-safety scan (spec 13)
def client_deny_patterns(rego_mode):
    pats = [
        r'\btcvT?\b', r'\bbtc\b', r'\bbitcoin\b', r'\btreasury\b', r'TCV Potential', r'"dev"\s*:', r'\bdev\s*:',
        r'"rank"\s*:', r'[{,]\s*rank\s*:', r'\barchetype\b', r'\baccred_ref\b', r'\bsupplier_1\b', r'\bsupplier_2\b',
        r'\bsupplier_1_certs\b', r'\bn_external\b', r'\bbm_tier\b', r'\byrs_old\b', r'\bwebsite\b', r'"gspc?"\s*:',
        r'\bTCVRATE\b', r'\bAVRATIO\b', r'\bWHOLESALE\b', r'\btcvPot\b', r'\bscores?\b', r'\binternal\b',
        r'RenewaBlox CRM', r'RenewaBlox_AD_BM_CRM', r'RenewaBlox_Hydro_Stranded', r'Scrivelsby peaker', r'\bModo\b',
        r'\blagging\b', r'winding\s*down', r'\.rank\b', r'\(Dr [A-Z]', r'was contractor',
        r'Owner decision', r'decisions pending', r'CVD-validated', r'client-safety', r'build\.py', r'\bREADME\b',
        r'\b17p\b', r'\b70p\b', r'[x×]\s?1\.20\b', r'\b1\.45\s*(?:T1|\.\.|…)', r'\b0\.79\s*T5', r'"src"\s*:', r'"s"\s*:',
    ]
    if rego_mode != 'raw':
        pats += [r'likely ceased', r'lagging/winding down']
    return [re.compile(p, re.I) for p in pats]


NOTE_RX = re.compile(r'\bverify\b|\bTBC\b|\bTODO\b|site=|\?\?|was contractor|\blandowner\b|\bsite owner\b|'
                     r'\bsite op\.|\(Dr [A-Z]|\bfamily\)', re.I)
SMALL_WORDS = r'(?:and|of|the|at|on|in|for|to|de|by|nr|upon|le|with|via|en)\b'
LOWER_WORD_RX = re.compile(r'(?:^|[\s,/])(?!' + SMALL_WORDS + r')[a-z]')
NAME_FIELDS = {'sam': ('name', 'site', 'town'), 'hydro': ('name',), 'tam': ('n',)}


def public_text_checks(app, data):
    """Both apps (T08/T09): researcher notes never ship in any free-text field; public display names and towns
    are title-cased (a lower-case significant word outside a parenthetical fails), are never a placeholder
    ("Export", "Redacted") and never carry a trailing postcode."""
    bad = []
    for k, rows in data.items():
        for r in (rows if isinstance(rows, list) else []):
            for f, v in (r.items() if isinstance(r, dict) else []):
                if f in ('offRaw',):
                    continue                     # raw certificate-holder string (investor PPA register, verbatim v1)
                if isinstance(v, str) and NOTE_RX.search(v):
                    bad.append('%s.%s carries a research note: %r' % (k, f, v))
            for f in NAME_FIELDS.get(k, ()):
                v = r.get(f)
                if not isinstance(v, str) or not v:
                    continue
                bare = re.sub(r'\([^)]*\)', '', v)
                if LOWER_WORD_RX.search(bare) and not re.match(r'^(AD site|Name withheld|Unnamed site)\b', v):
                    bad.append('%s.%s is not title-cased: %r' % (k, f, v))
                if re.fullmatch(r'\s*(export|import meter)\s*', v, re.I) or re.search(r'redacted', v, re.I):
                    bad.append('%s.%s is a placeholder: %r' % (k, f, v))
                if f != 'name' and re.search(r'[\s,][A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$', v, re.I) and not v.startswith('AD site'):
                    bad.append('%s.%s ends in a postcode: %r' % (k, f, v))
    if bad:
        fail('%s public-text check failed (%d):\n  ' % (app, len(bad)) + '\n  '.join(bad[:30]))


# DI1 (investor build): every displayed name field (cards, search, Sites list, CSV) is a cleaned name. A company
# status found in a research note ships only as `opSt`, from a closed vocabulary, shown as a separate muted tag.
INV_NAME_FIELDS = {'sam': ('name', 'site', 'town', 'la', 'op', 'dev', 'off'), 'hydro': ('name',), 'tam': ('n',)}
INV_NAME_NOTE_RX = re.compile(r'\bverify\b|\bTBC\b|\bTODO\b|site=|\?\?', re.I)
OP_STATUSES = {'in liquidation', 'in administration', 'in receivership', 'dissolved', 'struck off'}
# fragments of the v1 research notes that must never reach the investor page, in any form
INV_NOTE_FRAGMENTS = re.compile(r'verify owner|SPV TBC|site=Farmgen|\(developer;|\(in liquidation', re.I)


def investor_name_checks(data, html_out=None):
    bad = []
    for k, fields in INV_NAME_FIELDS.items():
        for r in data.get(k) or []:
            for f in fields:
                v = r.get(f)
                if isinstance(v, str) and INV_NAME_NOTE_RX.search(v):
                    bad.append('%s.%s shows a research note: %r' % (k, f, v))
                if isinstance(v, str) and re.search(r'\b(in liquidation|in administration|in receivership)\b', v, re.I):
                    bad.append('%s.%s carries a company status inside the name (use opSt): %r' % (k, f, v))
            st = r.get('opSt')
            if st is not None and st not in OP_STATUSES:
                bad.append('%s.opSt %r is not a known company status' % (k, st))
    if html_out is not None:
        m = INV_NOTE_FRAGMENTS.search(html_out)
        if m:
            bad.append('investor HTML carries a research-note fragment: …%s…' % html_out[max(0, m.start() - 60):m.end() + 60])
    if bad:
        fail('investor display-name check failed (%d):\n  ' % len(bad) + '\n  '.join(bad[:30]))


def client_safety(data, html_out, rego_mode):
    # 1. structural: data keys ⊆ allowlist
    for k, rows in data.items():
        if k not in CLIENT_ALLOW:
            fail('client data: unexpected dataset %r' % k)
        keys = set(rows.keys()) if isinstance(rows, dict) else {kk for r in rows for kk in r}
        extra = keys - CLIENT_ALLOW[k]
        if extra:
            fail('client data %s: keys outside the allowlist: %s' % (k, sorted(extra)))
    # 1b. research notes / display names: see public_text_checks (run for both apps)
    # 2. textual: whole output (comments included); the init marker is whitelisted
    body = html_out.replace(INIT_MARKER, '')
    hits = []
    for p in client_deny_patterns(rego_mode):
        for m in p.finditer(body):
            a = max(0, m.start() - 50)
            hits.append('%s → …%s…' % (p.pattern, body[a:m.end() + 50].replace('\n', ' ')))
            break
    if hits:
        fail('client-safety scan failed:\n  ' + '\n  '.join(hits))
    if INIT_MARKER not in html_out:
        fail('client build lacks the %s marker' % INIT_MARKER)


# ============================================================================ PPA copy ↔ data check
def ppa_copy_check(warnings):
    """Run RBX.ppa.check(prices) (core/js/ppa.js) under node: the verbatim PPA copy numbers (+47%, 39%, 8.11,
    5%, 3%, 7.64, "Aug 25 – Jul 26") must still match data/shared/ppa_prices.json. Skipped with a warning when
    node is not installed."""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        warnings.append('node not found: PPA copy-vs-data check skipped')
        return
    src = read(HERE, 'core', 'js', 'ppa.js')
    prices = read(DATA, 'shared', 'ppa_prices.json')
    js = ('global.window={};' + src + ';let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{'
          'const r=window.RBX.ppa.check(JSON.parse(d));process.stdout.write(JSON.stringify(r||[]));});')
    try:
        out = subprocess.run([node, '-e', js], input=prices, capture_output=True, text=True, timeout=60)
    except Exception as e:  # pragma: no cover - environment specific
        warnings.append('PPA copy-vs-data check could not run: %s' % e)
        return
    if out.returncode != 0:
        fail('PPA copy-vs-data check crashed: %s' % out.stderr.strip()[:400])
    bad = json.loads(out.stdout or '[]')
    if bad:
        fail('PPA copy no longer matches data/shared/ppa_prices.json:\n  ' + '\n  '.join(map(str, bad)))


# ============================================================================ build one app
def build_app(app, warnings):
    adir = os.path.join(HERE, 'apps', app)
    tpl_path = os.path.join(adir, 'template.html')
    if not os.path.exists(tpl_path):
        return None
    cfg = load(adir, 'config.json')
    manifest = load(adir, 'manifest.json')
    sw = cfg.get('switches', {})
    data = ASSEMBLE[app](cfg)
    n_checks = assert_numbers(app, data, sw)

    # client-only transforms: REGO labels are a config switch (owner decision 2)
    rego_mode = sw.get('rego_labels', 'softened' if app == 'client' else 'raw')
    if rego_mode not in REGO_LABELS:
        fail('switches.rego_labels must be "softened" or "raw"')
    cfg.setdefault('labels', {})['rego'] = REGO_LABELS[rego_mode]
    cfg['labels']['ppaClass'] = PPA_CLASS

    tok = tokens_for(data)
    if app == 'investor':
        tok.update(investor_tokens(data))
        # Present-mode chapters (spec 10.3) ship as ATLAS_CONFIG.story
        if os.path.exists(os.path.join(adir, 'story.json')):
            cfg['story'] = load(adir, 'story.json')
    cfg = strip_private(fill_tokens(cfg, tok))
    left_tok = re.findall(r'\{\{[A-Za-z0-9_]+\}\}', json.dumps(cfg, ensure_ascii=False))
    if left_tok:
        fail('unfilled copy tokens in %s config: %s' % (app, sorted(set(left_tok))))
    # verbatim Universe strings must equal the computed ones (spec 12.1 item 3)
    uni = {v: cfg['views'][v].get('universe') for v in ('sam', 'tam', 'hydro') if v in cfg.get('views', {})}
    want = {'sam': '129 sites · 144 MW', 'tam': '1,309 sites · 3,612 MW', 'hydro': '57 sites · 15.2 MW stranded'}
    if sw.get('sam_kw_source') == 'dno_split':
        want['sam'] = '129 sites · %s MW' % tok['sam_mw0']
    if app == 'client':
        for v, s in uni.items():
            if s != want[v]:
                fail('Universe string for %s is %r, expected %r' % (v, s, want[v]))

    public_text_checks(app, data)
    packed = pack_data(data)
    data_js = js_json(packed)
    cfg_js = js_json(cfg)
    if len(data_js.encode('utf-8')) > DATA_BUDGET:
        fail('%s data payload %d B exceeds %d B' % (app, len(data_js.encode('utf-8')), DATA_BUDGET))

    css, js, used = bundle(app, manifest, warnings)
    has_ppa = 'core/js/ppa.js' in used
    shell = read(HERE, 'core', 'shell.html')
    tpl = read(tpl_path)
    import base64
    fav = 'data:image/svg+xml;base64,' + base64.b64encode(FAVICON_SVG.encode()).decode()
    repl = {
        '{{DEFAULT_THEME}}': cfg.get('defaultTheme', 'paper'), '{{TITLE}}': htmllib.escape(cfg['title']),
        '{{FAVICON_DATA_URI}}': fav, '{{FONTS_URL}}': FONTS_URL, '{{CDN_HEAD}}': cdn_head(), '{{CSS}}': css, '{{SHELL}}': shell,
        '{{CONFIG}}': cfg_js, '{{DATA}}': data_js,
        '{{NE_PACK}}': read(HERE, 'core', 'basemap', 'ne_pack.js').strip(),
        '{{BASEMAP}}': read(HERE, 'core', 'basemap', 'basemap.js').strip(), '{{JS}}': js,
    }
    out = tpl
    # single pass, so placeholder-like text inside inserted content is never re-substituted
    pat = re.compile('|'.join(re.escape(k) for k in repl))
    out = pat.sub(lambda m: repl[m.group(0)], out)
    left = re.findall(r'\{\{[A-Z_]+\}\}', tpl)
    for k in left:
        if k not in repl:
            fail('template placeholder %s has no value' % k)
    if INIT_MARKER not in out:
        fail('template lacks the %s marker' % INIT_MARKER)
    out = out.replace('\r\n', '\n')

    n_copy = copy_check(app, out, has_ppa, warnings, sw)
    if has_ppa:
        ppa_copy_check(warnings)
    if app == 'client':
        client_safety(data, out, rego_mode)
    else:
        investor_name_checks(data, out)
    size = len(out.encode('utf-8'))
    if size > HTML_BUDGET:
        fail('%s HTML %d B exceeds the %d B budget' % (app, size, HTML_BUDGET))
    return {'html': out, 'size': size, 'data': len(data_js.encode('utf-8')), 'css': len(css.encode()),
            'js': len(js.encode()), 'asserts': n_checks, 'copy': n_copy, 'files': used, 'has_ppa': has_ppa}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', choices=['client', 'investor'])
    ap.add_argument('--check', action='store_true', help='fail if the committed HTML differs from a fresh build')
    ap.add_argument('--qa', action='store_true', help='print bundle details')
    a = ap.parse_args(argv)
    apps = [a.only] if a.only else ['client', 'investor']
    warnings, rc = [], 0
    for app in apps:
        try:
            res = build_app(app, warnings)
        except BuildError as e:
            print('BUILD FAILED (%s): %s' % (app, e), file=sys.stderr)
            return 1
        if res is None:
            print('%-8s skipped: atlas/apps/%s/template.html not found' % (app, app))
            continue
        if a.check:
            cur = open(OUT[app], encoding='utf-8').read() if os.path.exists(OUT[app]) else ''
            if cur != res['html']:
                print('CHECK FAILED: %s differs from a fresh build; run python3 atlas/build.py' % os.path.relpath(OUT[app], REPO))
                rc = 1
            else:
                print('%-8s up to date (%s)' % (app, os.path.relpath(OUT[app], REPO)))
            continue
        with open(OUT[app], 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(res['html'])
        print('%-8s %s  %7.1f KB  (data %.1f KB · css %.1f KB · js %.1f KB) · %d number asserts · %d copy strings · safety %s'
              % (app, os.path.relpath(OUT[app], REPO), res['size'] / 1024, res['data'] / 1024, res['css'] / 1024,
                 res['js'] / 1024, res['asserts'], res['copy'], 'PASS' if app == 'client' else 'n/a'))
        if a.qa:
            print('   files: ' + ', '.join(res['files']))
    for w in warnings:
        print('warning: ' + w)
    return rc


if __name__ == '__main__':
    sys.exit(main())
