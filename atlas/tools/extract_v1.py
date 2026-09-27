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


# ------------------------------------------------------------------ smart title case (names, sites, towns)
ACRO = {'AD', 'STW', 'WWTW', 'WTW', 'WWTC', 'CHP', 'CCHP', 'UK', 'GB', 'LLP', 'NHS', 'JV', 'SPV', 'CIC', 'EU', 'WRC',
        'WWT', 'STC', 'RAF', 'MOD', 'II', 'III', 'IV', 'AEL', 'UKPN', 'NGED', 'MFG', 'JFS', 'EDL', 'LGC', 'PMF', 'SSE',
        'CB', 'SIMEC', 'BIFFA', 'NWWA', 'RSTC', 'FDBL', 'GSRE', 'SELCHP', 'BEDZED', 'JLEN', 'ENGIE'}
CASE_FIX = {'ltd': 'Ltd', 'plc': 'plc', 'efw': 'EfW', 'mccain': 'McCain', 'ad': 'AD', 'stw': 'STW', 'wwtw': 'WWTW',
            'wtw': 'WTW', 'chp': 'CHP', 'llp': 'LLP', 'uk': 'UK'}
SMALL_W = {'and', 'of', 'the', 'at', 'on', 'in', 'for', 'to', 'de', 'by', 'upon', 'le', 'nr', 'with', 'via', 'en'}
# v1 already title-cased some acronyms ("Edl", "Fka Jfs"): restore them
TITLE_FIX = {'Edl': 'EDL', 'Jfs': 'JFS', 'Fka': 'fka', 'Pmf': 'PMF', 'Lgc': 'LGC', 'Mfg': 'MFG'}
HYPH_SMALL = {'super', 'upon', 'on', 'under', 'next', 'the', 'le', 'en', 'in', 'by', 'sur', 'de'}
# words inside operator parentheticals that are notes, not names ("fka", "op.", "now", "t/a" …): never capitalised
NOTE_W = {'fka', 'op', 'orig', 'mgd', 'acq', 'now', 'owned', 'via', 'site', 'run', 'by', 't', 'a', 'in', 'liquidation',
          'partnership', 'local', 'authority', 'of', 'former', 'sludge', 'with'}
PC_RX = re.compile(r'^[A-Za-z]{1,2}\d[A-Za-z\d]?$|^\d[A-Za-z]{2}$')
TRAIL_PC_RX = re.compile(r'[\s,]+[A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2}\s*$')


def _cap(w):
    lw = w.lower()
    if lw in CASE_FIX:
        return CASE_FIX[lw]
    if lw.startswith('mc') and len(lw) > 3:
        return 'Mc' + lw[2:3].upper() + lw[3:]
    if re.match(r"^[a-z]'[a-z]", lw):
        return lw[0].upper() + "'" + lw[2].upper() + lw[3:]
    return lw[:1].upper() + lw[1:]


def smart_title(s, lower_fix=True, op_notes=False):
    """Display case for public names, sites and towns (T08 / D2).
    * ALL-CAPS words become Title Case when the string is mostly capitals (≥ 60 %), or when they sit in a run of two
      or more capitalised words ("WEST BERKSHIRE COUNCIL (local authority)" → "West Berkshire Council (local authority)");
      acronyms (AD, STW, WWTW, CHP, UK, LLP …) and postcodes stay upper-case; Ltd / plc / EfW get their house form.
    * lower-case significant words are capitalised ("Station farm" → "Station Farm", "Banbury ad plant" →
      "Banbury AD Plant"); small words (and, of, the, nr …) stay lower except first; hyphenated place names keep
      their joiners lower ("Weston-super-Mare").
    * Existing mixed-case words (McCain, GwyriAD, BioticNRG) are left alone."""
    if not s:
        return s
    s = re.sub(r'\s+', ' ', s.strip()).replace(' ,', ',')
    # share of capitals over the words that are not acronyms or initials
    letters = [c for w in re.findall(r"[A-Za-z]+", s) if len(w) >= 2 and w not in ACRO for c in w]
    caps_mode = bool(letters) and sum(c.isupper() for c in letters) / len(letters) >= 0.6
    toks = re.split(r"([A-Za-z0-9'’]+)", s)       # odd indices are words, even are separators
    words = list(range(1, len(toks), 2))
    is_caps = {i: toks[i].isalpha() and toks[i].isupper() for i in words}
    # runs of all-caps words joined only by spaces / & / , / -
    in_run = set()
    run = []

    def run_ok(r):
        return len(r) >= 2 and any(len(toks[j]) >= 3 and toks[j] not in ACRO for j in r)
    # a parenthetical written wholly in capitals ("(SWALCLIFFE)") is converted like a caps string
    caps_paren = set()
    for m in re.finditer(r'\(([^()]*)\)', s):
        inner = [c for c in m.group(1) if c.isalpha()]
        if inner and all(c.isupper() for c in inner):
            caps_paren.update(range(m.start(), m.end()))
    pos, tok_pos = 0, {}
    for i, t in enumerate(toks):
        tok_pos[i] = pos
        pos += len(t)
    for n, i in enumerate(words):
        if is_caps[i] and (not run or re.fullmatch(r"[\s&,\-]*", toks[i - 1] or '')):
            run.append(i)
        else:
            if run_ok(run):
                in_run.update(run)
            run = [i] if is_caps[i] else []
    if run_ok(run):
        in_run.update(run)
    depth, first = 0, True
    for i in range(len(toks)):
        t = toks[i]
        if i % 2 == 0:
            depth += t.count('(') - t.count(')')
            continue
        prev_sep, next_sep = toks[i - 1], toks[i + 1] if i + 1 < len(toks) else ''
        lw = t.lower()
        if any(c.isdigit() for c in t):
            if PC_RX.match(t):
                toks[i] = t.upper()
        elif is_caps[i]:
            if t in ACRO or len(t) == 1:
                pass
            elif (caps_mode and depth == 0) or i in in_run or (tok_pos[i] in caps_paren and len(t) >= 3):
                toks[i] = 'Ltd' if t == 'LTD' else 'plc' if t == 'PLC' else 'EfW' if t == 'EFW' else (
                    lw if (not first and lw in SMALL_W) else _cap(t))
        elif t in TITLE_FIX:
            toks[i] = TITLE_FIX[t]
        elif t.islower() or (t[:1].isupper() and t[1:].islower() and lw in CASE_FIX):
            if lw in CASE_FIX and (lower_fix or t[:1].isupper()):
                toks[i] = CASE_FIX[lw]
            elif not lower_fix or depth > 0:
                pass                                   # parentheticals keep their own case ("(1 of 3)", "(fka …)")
            elif op_notes and lw in NOTE_W:
                pass
            elif prev_sep.endswith('-') and next_sep.startswith('-') and lw in HYPH_SMALL:
                toks[i] = lw
            elif not first and lw in SMALL_W:
                pass
            elif t.islower():
                toks[i] = _cap(t)
        first = False
    out = ''.join(toks)
    out = re.sub(r'\bAD Site\b', 'AD site', out)
    return out[:1].upper() + out[1:]


def clean_site(site):
    """Public site string: placeholders dropped, trailing postcode stripped, smart-title-cased."""
    site = (site or '').strip()
    if site.upper() in ('DATA NOT AVAILABLE', 'EXPORT', 'IMPORT METER'):
        return ''
    cut = TRAIL_PC_RX.sub('', site).strip(' ,')
    if cut and not re.fullmatch(r'AD site', cut, re.I):      # "AD site LA2 0AG" keeps its postcode (it is the name)
        site = cut
    return smart_title(site)


REDACTED_RX = re.compile(r'^\W*redacted\W*$', re.I)
WITHHELD = 'Name withheld (FiT register)'


# Research notes left inside v1 operator strings (e.g. "(in liquidation; site=Farmgen, Warton — verify owner)",
# "(developer; SPV TBC)") are internal working notes and must never reach a public page.
OP_NOTE_RX = re.compile(r'\s*\((?=[^)]*(?:\bverify\b|\bTBC\b|\bTODO\b|site=|\?))[^)]*\)', re.I)
# researcher parentheticals: role notes ("site op.; X was contractor", "landowner; …", "site owner; …", "developer; …")
ROLE_NOTE_RX = re.compile(r'\s*\((?=[^)]*(?:contractor|\bsite owner\b|\blandowner\b|\bsite op\.|\bdeveloper;))[^)]*\)', re.I)
# private individuals named in a parenthetical: "(Dr Stephen Temple)", "(Neil Gemmell)", "(Glyn family)"
ORG_W = {'Ltd', 'Limited', 'Estates', 'Estate', 'Farms', 'Farm', 'Water', 'Biogas', 'Capital', 'Energy', 'Power', 'Green',
         'Renewables', 'Generation', 'Group', 'Holdings', 'Partners', 'Trust', 'Council', 'Foods', 'Change', 'Upcycle'}
PERSON_RX = re.compile(r'\s*\((?:(?:Dr|Mr|Mrs|Ms|Miss)\.?\s[^)]*|[^)]*\bfamily|([A-Z][a-z]+) ([A-Z][a-z]+))\)')


def _strip_person(m):
    if m.group(1) and (m.group(1) in ORG_W or m.group(2) in ORG_W):
        return m.group(0)
    return ''


# A short factual company status inside a stripped research note ("(in liquidation; site=… — verify owner)") is kept
# for the investor build only, as its own field (`opSt`) that the cards, search and CSV show as a muted tag (DI1).
OP_STATUS_RX = re.compile(r'\b(in liquidation|in administration|in receivership|dissolved|struck off)\b', re.I)


def op_status(*raws):
    """Factual company status from the parentheticals of the raw operator / developer strings, else None."""
    for raw in raws:
        for par in re.findall(r'\(([^)]*)\)', raw or ''):
            m = OP_STATUS_RX.search(par)
            if m:
                return m.group(1).lower()
    return None


# A sole trader's operator string is a private individual's name (e.g. "Firstname Surname"). The public client page
# shows PRIVATE_OPERATOR instead; the gated investor build keeps the name.
PRIVATE_OPERATOR = 'Private operator'
PERSON_NAME_RX = re.compile(r"(?:(?:Dr|Mr|Mrs|Ms|Miss)\.?\s)?[A-Z][a-z]+(?:[-'][A-Za-z]+)?(?:\s[A-Z]\.?)?\s[A-Z][a-z]+(?:[-'][A-Za-z]+)?")


def is_personal_name(op):
    """True when an operator string is just a person's name (no organisation word)."""
    return bool(op) and bool(PERSON_NAME_RX.fullmatch(op.strip())) and not (set(op.split()) & ORG_W)


def client_operator(op):
    """Operator for the public client page: a private individual's name is replaced by PRIVATE_OPERATOR."""
    return PRIVATE_OPERATOR if is_personal_name(op) else op


def public_operator(op):
    """Operator as shown publicly: research-note, role-note and personal-name parentheticals stripped, then
    display-cased per word (mixed-case words kept)."""
    op = OP_NOTE_RX.sub('', op or '')
    op = ROLE_NOTE_RX.sub('', op)
    op = PERSON_RX.sub(_strip_person, op).strip()
    op = display_case(op)
    return smart_title(op, lower_fix=True, op_notes=True)


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
    sam, sam_reg, inv_sam, inv_reg, kw_dno, raw_site = [], [], [], [], {}, {}
    inv_by_pc = {pcn(p['pc']): p for p in I['PEAKER']}
    assert len(inv_by_pc) == 129
    for p in C['PEAKER']:
        key = pcn(p['postcode'])
        pk = C['PKD'][p['rank']]
        reg = reg_by_pc[key]
        assert abs(float(reg['installed_kw']) - float(p['installed_kw'])) < 0.01, key
        raw_site[key] = (p.get('site') or '').strip()
        site = clean_site(p.get('site'))
        op = (p.get('operator') or '').strip()
        if op.upper() == 'DATA NOT AVAILABLE':
            op = ''
        op = public_operator(op)
        if inv_by_pc[key]['n'] == 'AD site (name withheld)':
            # v1 investor withheld these names; the operator stays in the Operator row, never as the title
            pname = 'AD site (%s)' % re.match(r'^([A-Z]{1,2}\d[A-Z\d]?)', key).group(1)
        else:
            pname = site.split(',')[0].strip() if site else (re.sub(r'\s*\([^)]*\)', '', op).strip() or smart_title(p.get('town') or '') or p['postcode'])
        town = (p.get('town') or '').strip()
        if town.upper() == 'DATA NOT AVAILABLE':
            town = ''
        la = (p.get('local_authority') or '').strip()
        la = re.sub(r'-\s*County of$', '', la).strip() if la.upper() != 'DATA NOT AVAILABLE' else ''
        comm = intish(reg.get('commissioned') or p.get('commissioned'))
        row = {
            'key': key, 'name': smart_title(pname), 'site': site, 'town': smart_title(town), 'la': la,
            'pc': p['postcode'].strip().upper(), 'op': client_operator(op), 't': int(p['tier']),
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
        inv_sam.append(dict(row, op=op, rank=p['rank'], g=ip['g'], dev=public_operator(ip['dev']) or None, inst=intish(ip['inst']),
                            av=ip['av'], btc=ip['btc'], en=ip['en'], tcv=ip['tcv'], tcvT=ip['tcvT'],
                            web=(p.get('website') or '').strip() or None))
        st = op_status(p.get('operator'), ip['dev'], reg.get('operator'))
        if st:
            inv_sam[-1]['opSt'] = st          # investor only; never in the client allowlist
        ir = {k: v for k, v in reg.items() if k not in ('lat', 'lon')}
        ir.update({'key': key, 'offtaker_raw': reg.get('offtaker'), 'offtaker': clean_counterparty(reg.get('offtaker')),
                   'operator': public_operator((reg.get('operator') or '').strip()),
                   'town': smart_title((reg.get('town') or '').strip()) or None})
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
        hyd.append({'key': 'h-' + slug(h['name']), 'name': smart_title(display_case(h['name'])), 'exp': h['exp'], 'conf': h['conf'],
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
        inv_hyd.append(dict(m[0], btc=ih['btc'], en=ih['en'], tcv=ih['tcv'], tcvT=ih['tcvT']))
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
            full = [v for v in raw_site.values() if v and v.startswith(name) and len(v) > len(name)]
            if samkey:
                full = [raw_site[samkey]] if raw_site.get(samkey, '').startswith(name) else full
            exact = any(v == name for v in raw_site.values())
            if len(set(full)) == 1:
                name = full[0]
                n_full += 1
            elif not exact:
                name = name.rstrip(' ,-(/') + '…'     # no full source exists: mark the v1 cut honestly
        srow = next((c for c in sam if c['key'] == samkey), None) if samkey else None
        if srow and (srow['name'].startswith('AD site (') or re.fullmatch(r'export|import meter', name, re.I)
                     or name == (inv_by_pc[samkey].get('dev') or '')):
            name = srow['name']                  # withheld / placeholder / operator-as-name: use the SAM title
        elif REDACTED_RX.match(name):
            name = WITHHELD
        elif re.fullmatch(r'export|import meter', name, re.I):
            name = 'Unnamed site (FiT register)'
        else:
            cut = TRAIL_PC_RX.sub('', name).strip(' ,')
            if cut and not re.fullmatch(r'AD site', cut, re.I):
                name = cut
        pub = name if (name in (WITHHELD, 'Unnamed site (FiT register)') or (srow and name == srow['name'])) else smart_title(display_case(name))
        # stable key from the RO code, else from the PUBLIC name (a raw name can hold a withheld or personal name)
        base = ro if ro else 't' + slug(pub)[:16].strip('-') + '-' + geohash(t['lat'], t['lon'], 3)
        keys[base] += 1
        key = base if keys[base] == 1 else base + '-' + str(keys[base])
        row = {'key': key, 'n': pub, 'f': t['f'], 'kw': t.get('kw'), 'bm': t.get('bm'),
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
