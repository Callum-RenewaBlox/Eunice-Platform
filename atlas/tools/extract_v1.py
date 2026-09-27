#!/usr/bin/env python3
"""One-off migration: parse the v1 atlas pages into the v2 data files.

Reads   atlas/tools/v1/client_atlas.html and atlas/tools/v1/investor_atlas.html
        (frozen copies of the v1 pages; the live paths are overwritten by build.py)
Writes  atlas/data/shared/{tam,ppa_prices}.json
        atlas/data/client/{sam,hydro,ppa_register}.json
        atlas/data/investor/{sam,hydro,ppa_register,tam_extra,model}.json

Run:    python3 atlas/tools/extract_v1.py          (idempotent; prints a summary)

Kept in the repo for audit. The data files are the source of truth for build.py;
re-running this script regenerates them from the frozen v1 pages.

Client data is written with a closed field allowlist (spec section 13.1). Anything
not on it stays in the investor files or is dropped.
"""
import json
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.dirname(HERE)
V1 = os.path.join(HERE, 'v1')
DATA = os.path.join(ATLAS, 'data')


# ------------------------------------------------------------------ parsing helpers
def _const(src, name):
    """Return the raw text of `const NAME = <literal>;` (balanced brackets)."""
    m = (re.search(r'(?:const|let|var)\s+' + re.escape(name) + r'\s*=\s*', src)
         or re.search(r'[,;]\s*' + re.escape(name) + r'\s*=\s*(?=[\[{])', src))
    if not m:
        raise KeyError(name)
    i = m.end()
    open_ch = src[i]
    close_ch = {'[': ']', '{': '}'}[open_ch]
    depth, j, in_str, q = 0, i, False, ''
    while j < len(src):
        c = src[j]
        if in_str:
            if c == '\\':
                j += 2
                continue
            if c == q:
                in_str = False
        elif c in '"\'':
            in_str, q = True, c
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    raise ValueError('unbalanced ' + name)


def _js_literal(txt):
    """Tiny JS-object-literal → JSON converter (unquoted keys, single-quoted strings)."""
    out, i = [], 0
    while i < len(txt):
        c = txt[i]
        if c == "'":
            j = i + 1
            buf = []
            while txt[j] != "'":
                if txt[j] == '\\':
                    buf.append(txt[j:j + 2])
                    j += 2
                    continue
                if txt[j] == '"':
                    buf.append('\\"')
                else:
                    buf.append(txt[j])
                j += 1
            out.append('"' + ''.join(buf) + '"')
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            while txt[j] != '"':
                j += 2 if txt[j] == '\\' else 1
            out.append(txt[i:j + 1])
            i = j + 1
            continue
        out.append(c)
        i += 1
    s = ''.join(out)
    s = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*|\d+)\s*:', r'\1"\2":', s)
    s = re.sub(r',\s*([}\]])', r'\1', s)
    return json.loads(s)


def load_v1(fname):
    return open(os.path.join(V1, fname), encoding='utf-8').read()


# ------------------------------------------------------------------ text helpers
KEEP_UPPER = {'AD', 'CHP', 'UK', 'GB', 'STW', 'WTW', 'WWTW', 'SPV', 'LLP', 'NHS', 'II', 'III', 'IV', 'JV',
              'PLC', 'LTD', 'EFW', 'AEL', 'AE', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M',
              'N', 'P', 'R', 'S', 'T', 'W', 'WRC', 'WWT', 'STC', 'RAF', 'MOD', 'CIC', 'EU', 'UKPN', 'NGED'}
SPECIAL = {'LTD': 'Ltd', 'PLC': 'plc', 'EFW': 'EfW'}
SMALL = {'and', 'of', 'the', 'at', 'on', 'in', 'for', 'to', 'de', 'by', 'upon', 'le'}


def display_case(s):
    """ALL-CAPS strings → Title Case, keeping acronyms. Mixed-case strings are left alone."""
    if not s:
        return s
    s = re.sub(r'\s+', ' ', s.strip())
    letters = [c for c in s if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return s
    parts = re.split(r'(\s+|-|/|\(|\)|&|,|\.)', s)
    out = []
    for i, w in enumerate(parts):
        if not w or re.fullmatch(r'\s+|-|/|\(|\)|&|,|\.', w):
            out.append(w)
            continue
        core = re.sub(r'[^A-Za-z0-9]', '', w).upper()
        if core in SPECIAL:
            out.append(SPECIAL[core])
        elif core in KEEP_UPPER and len(core) > 1:
            out.append(w.upper())
        elif re.search(r'\d', w):
            out.append(w.upper())
        elif i > 0 and w.lower() in SMALL:
            out.append(w.lower())
        elif "'" in w:
            out.append(w[:1].upper() + w[1:].lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    r = ''.join(out)
    return r[:1].upper() + r[1:]


# Research notes left inside v1 operator strings (e.g. "(in liquidation; site=Farmgen, Warton — verify owner)",
# "(developer; SPV TBC)") are internal working notes and must never reach a public page.
OP_NOTE_RX = re.compile(r'\s*\((?=[^)]*(?:\bverify\b|\bTBC\b|\bTODO\b|site=|\?))[^)]*\)', re.I)


def public_operator(op):
    """Operator as shown publicly: research-note parentheticals stripped, then display-cased."""
    return display_case(OP_NOTE_RX.sub('', op or '').strip())


def clean_counterparty(o):
    """Build-time cleaning of certificate-holder names (spec 8.3)."""
    if not o:
        return None
    if re.search(r'sole holder', o, re.I):
        return 'Generator is sole holder'
    o = re.sub(r'\s*\(Supplier\)\s*$', '', o, flags=re.I)
    o = re.sub(r'\s*-\s*Supplier\s*-\s*SUP\d+\s*$', '', o, flags=re.I)
    o = o.replace('Internatinal', 'International').strip()
    o = display_case(o)
    # a trailing " Limited"/" Ltd" duplicate, e.g. "X Ltd Limited"
    o = re.sub(r'\s+(Ltd|Limited)\s+(Ltd|Limited)$', r' \1', o)
    return o


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', (s or '').lower()).strip('-')[:40]


_B32 = '0123456789bcdefghjkmnpqrstuvwxyz'


def geohash(lat, lon, n=3):
    lat_r, lon_r, bits, bit, ch, even, out = [-90.0, 90.0], [-180.0, 180.0], [16, 8, 4, 2, 1], 0, 0, True, ''
    while len(out) < n:
        rng, v = (lon_r, lon) if even else (lat_r, lat)
        mid = (rng[0] + rng[1]) / 2
        if v > mid:
            ch |= bits[bit]
            rng[0] = mid
        else:
            rng[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            out += _B32[ch]
            bit, ch = 0, 0
    return out


pcn = lambda p: (p or '').replace(' ', '').upper()

PPA_CODE = {'Negotiated export PPA': 'neg', 'FiT standard export tariff (no PPA)': 'fit',
            'No export — behind the meter': 'btm', 'Unknown — no FiT match': 'unk'}
REGO_CODE = {'active': 'active', 'lagging/winding down': 'declining', 'likely ceased': 'ceased',
             'no REGO certs': 'none'}
FUELS = ['Landfill gas', 'Fuelled (biomass/AD/EfW)', 'Biomass', 'Waste / EfW', 'Biogas (AD)', 'Sewage gas',
         'Advanced fuel', 'Biofuel - other', 'Biodiesel']   # v1 legend order (MW descending)


def r5(x):
    return None if x is None else round(float(x), 5)


def intish(x):
    if x is None or x == '':
        return None
    f = float(x)
    return int(f) if f == int(f) else f


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write('\n')


# ------------------------------------------------------------------ main
def main():
    csrc, isrc = load_v1('client_atlas.html'), load_v1('investor_atlas.html')
    C = {k: json.loads(_const(csrc, k)) for k in ('PEAKER', 'HYDRO_S', 'HYX', 'TAM')}
    C['PKD'] = {int(k): v for k, v in _js_literal(_const(csrc, 'PKD')).items()}
    C['DATA'] = json.loads(_const(csrc, 'DATA'))
    fwd = _js_literal(_const(csrc, 'FWD_BLOCKS'))
    bmrev = _js_literal(_const(csrc, 'BMREV'))
    I = {k: json.loads(_const(isrc, k)) for k in ('PEAKER', 'HYDRO', 'TAM')}
    I['DATA'] = json.loads(_const(isrc, 'DATA'))
    assert C['DATA'] == I['DATA'], 'client and investor PPA DATA differ'
    assert {int(k): v for k, v in bmrev.items()} == {1: {'a': '29.6', 't': '122'}, 2: {'a': '25.3', 't': '104'},
                                                      3: {'a': '21.7', 't': '80'}, 4: {'a': '18.0', 't': '61'},
                                                      5: {'a': '16.0', 't': '50'}}

    # ---------------- PPA register (v1 DATA.sites), joined by normalised postcode
    reg_by_pc = {pcn(s['postcode']): s for s in C['DATA']['sites']}
    assert len(reg_by_pc) == 129

    # ---------------- SAM (client)
    sam, sam_reg, inv_sam, inv_reg, kw_dno = [], [], [], [], {}
    inv_by_pc = {pcn(p['pc']): p for p in I['PEAKER']}
    assert len(inv_by_pc) == 129
    for p in C['PEAKER']:
        key = pcn(p['postcode'])
        pk = C['PKD'][p['rank']]
        reg = reg_by_pc[key]
        assert abs(float(reg['installed_kw']) - float(p['installed_kw'])) < 0.01, key
        site = (p.get('site') or '').strip()
        if site.upper() == 'DATA NOT AVAILABLE':
            site = ''
        pname = site.split(',')[0].strip() if site else (p.get('operator') or p.get('town') or p['postcode'])
        town = (p.get('town') or '').strip()
        if town.upper() == 'DATA NOT AVAILABLE':
            town = ''
        la = (p.get('local_authority') or '').strip()
        la = re.sub(r'-\s*County of$', '', la).strip() if la.upper() != 'DATA NOT AVAILABLE' else ''
        op = (p.get('operator') or '').strip()
        if op.upper() == 'DATA NOT AVAILABLE':
            op = ''
        comm = intish(reg.get('commissioned') or p.get('commissioned'))
        row = {
            'key': key, 'name': display_case(pname), 'site': site, 'town': display_case(town), 'la': la,
            'pc': p['postcode'].strip().upper(), 'op': public_operator(op), 't': int(p['tier']),
            'kw': intish(p['installed_kw']), 'kwOn': intish(pk[1]), 'kwBm': intish(pk[2]),
            'comm': comm, 'lat': r5(p['lat']), 'lon': r5(p['lon'])}
        sam.append(row)
        if pk[0] is not None and intish(pk[0]) != row['kw']:
            kw_dno[key] = intish(pk[0])      # build-only input for switches.sam_kw_source = "dno_split"
        sam_reg.append({
            'key': key, 'ppa': PPA_CODE[reg['ppa_class']], 'off': clean_counterparty(reg.get('offtaker')),
            'self': bool((reg.get('self_certs') or 0) > 0), 'fitGen': reg.get('gen_tariff_p_kwh_2026_27'),
            'fitEnd': reg.get('fit_end_date'), 'yrsLeft': reg.get('yrs_subsidy_left'),
            'rego': REGO_CODE[reg['rego_status']]})
        # investor overlay (commercial fields + raw register)
        ip = inv_by_pc[key]
        assert ip['t'] == p['tier'], key
        inv_sam.append(dict(row, rank=p['rank'], invName=ip['n'], g=ip['g'], dev=ip['dev'], inst=intish(ip['inst']),
                            av=ip['av'], btc=ip['btc'], en=ip['en'], tcv=ip['tcv'], tcvT=ip['tcvT'],
                            web=(p.get('website') or '').strip() or None))
        ir = {k: v for k, v in reg.items() if k not in ('lat', 'lon')}
        ir.update({'key': key, 'offtaker_raw': reg.get('offtaker'), 'offtaker': clean_counterparty(reg.get('offtaker')),
                   'operator': display_case((reg.get('operator') or '').strip()),
                   'town': display_case((reg.get('town') or '').strip()) or None})
        inv_reg.append(ir)

    # neutral register order for the client: tier ascending, then kW descending, then name
    order = sorted(sam, key=lambda r: (r['t'], -(r['kw'] or 0), r['name'].lower()))
    ref = {r['key']: i + 1 for i, r in enumerate(order)}
    for r in sam_reg:
        r['ref'] = ref[r['key']]
    sam.sort(key=lambda r: ref[r['key']])
    sam_reg.sort(key=lambda r: r['ref'])
    inv_sam.sort(key=lambda r: r['rank'])
    inv_reg.sort(key=lambda r: r['rank'])

    # ---------------- Hydro (client HYDRO_S + HYX aligned by index; investor HYDRO joined by name+coords)
    hyd = []
    for h, x in zip(C['HYDRO_S'], C['HYX']):
        hyd.append({'key': 'h-' + slug(h['name']), 'name': display_case(h['name']), 'exp': h['exp'], 'conf': h['conf'],
                    'kw': h['kw'], 'inst': x[0], 'mec': x[1], 'lat': r5(h['lat']), 'lon': r5(h['lon'])})
    assert len({h['key'] for h in hyd}) == 57, 'hydro keys not unique'
    inv_hyd = []
    for ih in I['HYDRO']:
        m = [h for h in hyd if abs(h['lat'] - ih['lat']) < 1e-4 and abs(h['lon'] - ih['lon']) < 1e-4
             and slug(h['name']) == slug(ih['n'])]
        if len(m) != 1:
            m = [h for h in hyd if abs(h['lat'] - ih['lat']) < 1e-4 and abs(h['lon'] - ih['lon']) < 1e-4]
        assert len(m) == 1, ('hydro join', ih['n'])
        assert m[0]['kw'] == ih['kw'] and m[0]['exp'] == ih['exp'] and m[0]['conf'] == ih['conf'], ih['n']
        inv_hyd.append(dict(m[0], invName=ih['n'], btc=ih['btc'], en=ih['en'], tcv=ih['tcv'], tcvT=ih['tcvT']))
    assert len({h['key'] for h in inv_hyd}) == 57
    hyd.sort(key=lambda h: -h['kw'])
    inv_hyd.sort(key=lambda h: -h['kw'])

    # ---------------- TAM (shared, client-safe) + investor extras
    sam_by_ll = {}
    for r in sam:
        sam_by_ll.setdefault((round(r['lat'], 4), round(r['lon'], 4)), []).append(r)
    tam, tam_extra, keys = [], {}, Counter()
    n_full = 0
    for i, (t, it) in enumerate(zip(C['TAM'], I['TAM'])):
        assert t['n'] == it['n'] and t['f'] == it['f'] and t.get('kw') == it.get('kw'), i
        ro = t.get('ro') or None
        base = ro if ro else 't' + slug(t['n'])[:16].strip('-') + '-' + geohash(t['lat'], t['lon'], 3)
        keys[base] += 1
        key = base if keys[base] == 1 else base + '-' + str(keys[base])
        samkey = None
        if t.get('sam'):
            cand = sam_by_ll.get((round(t['lat'], 4), round(t['lon'], 4)), [])
            if len(cand) > 1:
                cand = [c for c in cand if c['kw'] == t.get('kw')] or cand
            assert cand, ('TAM sam join', t['n'])
            samkey = cand[0]['key']
        name = t['n']
        if len(name) >= 54:
            # v1 cut TAM names at 54 characters; restore the full site string from the SAM row it matches
            full = [c['site'] for c in sam if c.get('site') and c['site'].startswith(name) and len(c['site']) > len(name)]
            if samkey:
                full = [c['site'] for c in sam if c['key'] == samkey and c.get('site', '').startswith(name)] or full
            exact = any(c.get('site') == name for c in sam)
            if len(set(full)) == 1:
                name = full[0]
                n_full += 1
            elif not exact:
                name = name.rstrip(' ,-(/') + '…'     # no full source exists: mark the v1 cut honestly
        row = {'key': key, 'n': display_case(name), 'f': t['f'], 'kw': t.get('kw'), 'bm': t.get('bm'),
               'p': 1 if t.get('p') == 'approx' else 0, 'bt': t['bt'], 'ro': ro, 'units': t.get('units'),
               'sam': samkey, 'lat': r5(t['lat']), 'lon': r5(t['lon'])}
        tam.append(row)
        ex = {'src': it.get('src'), 's': it.get('s')}
        if ('bm' in it) and it.get('bm') != t.get('bm'):
            ex['bm'] = it.get('bm')          # investor v1 carries an explicit null for 16 SAM rows
        tam_extra[key] = ex
    samkeys = [t['sam'] for t in tam if t['sam']]
    assert len(samkeys) == 129 and len(set(samkeys)) == 129, ('TAM→SAM keys', len(samkeys), len(set(samkeys)))
    assert len({t['key'] for t in tam}) == len(tam)

    # ---------------- PPA prices (shared)
    kpi = C['DATA']['kpi']
    ppa = {'realised': C['DATA']['realised'], 'fwd': fwd, 'kpi': kpi,
           'spread': {'value': 49, 'note': 'Win-26 vs Sum-27 — AD runs flat'}, 'fit': 7.64, 'cpi': 0.03}

    # ---------------- client register (v1 DATA.sites shape is produced at runtime from these fields)
    # ---------------- investor model constants (checked by build.py against appendix A)
    model = {'WHOLESALE': 8.0, 'TAVG': {'1': 29.6, '2': 25.3, '3': 21.7, '4': 18.0, '5': 16.0},
             'asOf': {'model': '16 Jun 2026', 'registers': 'Jul–Aug 2026', 'prices': '11 Aug 2026'}}

    dump(os.path.join(DATA, 'shared', 'tam.json'), tam)
    dump(os.path.join(DATA, 'shared', 'ppa_prices.json'), ppa)
    dump(os.path.join(DATA, 'client', 'sam.json'), sam)
    dump(os.path.join(DATA, 'client', 'ppa_register.json'), sam_reg)
    dump(os.path.join(DATA, 'client', 'hydro.json'), hyd)
    dump(os.path.join(DATA, 'shared', 'sam_kw_dno.json'), {'_doc': 'Build-only (never shipped): installed kW per the DNO split where it differs from the FiT register. Used when switches.sam_kw_source = "dno_split".', 'kw': kw_dno})
    dump(os.path.join(DATA, 'investor', 'sam.json'), inv_sam)
    dump(os.path.join(DATA, 'investor', 'ppa_register.json'), inv_reg)
    dump(os.path.join(DATA, 'investor', 'hydro.json'), inv_hyd)
    dump(os.path.join(DATA, 'investor', 'tam_extra.json'), tam_extra)
    dump(os.path.join(DATA, 'investor', 'model.json'), model)
    print('extract_v1: SAM %d · Hydro %d · TAM %d · register %d · fwd %d' % (len(sam), len(hyd), len(tam), len(sam_reg), len(fwd)))
    print('  TAM keys from RO %d, synthetic %d; SAM-in-TAM %d; truncated names restored %d' % (sum(1 for t in tam if t['ro']), sum(1 for t in tam if not t['ro']), len(samkeys), n_full))
    return 0


if __name__ == '__main__':
    sys.exit(main())
