"""Build contract tests: canonical numbers, client-safety, copy check, size budget, data packing.

Run:  python3 -m pytest atlas/tests/test_build.py      (if pytest is installed)
  or  python3 atlas/tests/test_build.py                (plain runner, no dependencies)
"""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.dirname(HERE)
sys.path.insert(0, ATLAS)

import build  # noqa: E402
sys.path.insert(0, os.path.join(ATLAS, 'tools'))
import extract_v1  # noqa: E402

_CACHE = {}


def client_build():
    if 'client' not in _CACHE:
        _CACHE['client'] = build.build_app('client', [])
    return _CACHE['client']


def test_client_builds_within_budget():
    res = client_build()
    assert res is not None
    assert res['size'] <= build.HTML_BUDGET, res['size']
    assert res['data'] <= build.DATA_BUDGET, res['data']
    assert build.INIT_MARKER in res['html']


def test_client_committed_output_is_fresh():
    """CI guard (same as `build.py --check`): the committed client_atlas_v2.html is a fresh build."""
    with open(build.OUT['client'], encoding='utf-8') as fh:
        assert fh.read() == client_build()['html'], 'client_atlas_v2.html is stale: run python3 atlas/build.py'


def test_canonical_numbers_client_and_investor():
    for app in ('client', 'investor'):
        data = build.ASSEMBLE[app]({'switches': {}})
        assert build.assert_numbers(app, data, {}) > 30


def test_sam_kw_switch():
    rows = build.load(build.DATA, 'client', 'sam.json')
    assert sum(r['kw'] for r in build.apply_sam_kw_source(rows, 'fit_register')) == 143571
    assert sum(r['kw'] for r in build.apply_sam_kw_source(rows, 'dno_split')) == 142573


def test_client_data_allowlist_is_enforced():
    data = build.assemble_client({'switches': {}})
    bad = copy.deepcopy(data)
    bad['sam'][0]['tcv'] = 1
    try:
        build.client_safety(bad, '/*__ATLAS_INIT__*/', 'softened')
    except build.BuildError as e:
        assert 'allowlist' in str(e)
    else:
        raise AssertionError('extra client key was not rejected')


def test_client_data_research_notes_are_rejected():
    data = build.assemble_client({'switches': {}})
    assert not any(re.search(r'verify|\bTBC\b|site=', r.get('op') or '', re.I) for r in data['sam'])
    bad = copy.deepcopy(data)
    bad['sam'][0]['op'] = 'Some Farm Ltd (in liquidation; verify owner)'
    try:
        build.public_text_checks('client', bad)
    except build.BuildError as e:
        assert 'research note' in str(e)
    else:
        raise AssertionError('a research note in client data must fail the build')


def test_client_p1_modules_bundled_and_safe():
    res = client_build()
    for f in ('core/js/notes.js', 'core/js/dialogs.js', 'core/js/export.js', 'core/js/nearme.js', 'core/js/drag.js', 'core/js/ppa.js'):
        assert f in res['files'], f
    html = res['html']
    assert 'api.postcodes.io' in html            # the only runtime host the client calls besides map/fonts CDNs


def test_client_textual_scan_catches_denied_tokens():
    data = build.assemble_client({'switches': {}})
    html = client_build()['html']
    for token in ['var tcvT=1;', '<!-- Bitcoin -->', '"rank": 3', 'archetype', 'RenewaBlox CRM', 'likely ceased',
                  '/* modelled with Modo */', 'score', 'x1.20', 'TCV Potential', '"dev":"x"']:
        try:
            build.client_safety(data, html + token, 'softened')
        except build.BuildError:
            continue
        raise AssertionError('denied token passed the scan: %r' % token)


def test_client_html_has_no_investor_or_internal_strings():
    html = client_build()['html']
    for pat in [r'\btcv', r'\bbitcoin\b', r'\btreasury\b', r'"rank"\s*:', r'\barchetype\b', r'RenewaBlox CRM',
                r'likely ceased', r'lagging/winding down', r'\binternal\b']:
        assert not re.search(pat, html, re.I), pat


def test_client_manifest_has_no_investor_paths():
    man = build.load(ATLAS, 'apps', 'client', 'manifest.json')
    for rel in man['css'] + man['js']:
        assert '/investor/' not in rel and not rel.startswith('apps/investor'), rel


def test_copy_check_reports_missing_strings():
    try:
        build.copy_check('client', '<html></html>', False, [])
    except build.BuildError as e:
        assert 'Peaker Model' in str(e)
    else:
        raise AssertionError('copy check passed on an empty page')


def test_universe_strings_verbatim():
    html = build.norm_text(client_build()['html'])
    for s in ['129 sites · 144 MW', '1,306 sites · 3,610 MW', '57 sites · 15.2 MW stranded']:
        assert s in html, s
    assert '3609.9' not in html


def test_pack_roundtrip():
    rows = [{'key': 'a', 'town': 'X', 'units': None, 'n': 1}, {'key': 'b', 'town': 'X', 'units': 3, 'n': 2},
            {'key': 'c', 'town': None, 'units': None, 'n': 3}]
    p = build.compact(rows, ('town',))
    # mirror of core/js/data.js decode()
    out = []
    for i in range(p['n']):
        r = {}
        for f, col in p['c'].items():
            v = col[i]
            r[f] = p.get('d', {}).get(f)[v] if f in p.get('d', {}) and v is not None else v
        out.append(r)
    for f, sp in p.get('sp', {}).items():
        for r in out:
            r[f] = None
        for ix, v in zip(sp['i'], sp['v']):
            out[ix][f] = v
    assert out == rows


def test_rego_labels_switch():
    assert build.REGO_LABELS['softened']['ceased'] == 'No recent certificates'
    assert build.REGO_LABELS['softened']['declining'] == 'Certificates declining'
    assert build.REGO_LABELS['raw']['ceased'] == 'likely ceased'


def test_unknown_copy_token_fails():
    try:
        build.fill_tokens({'a': 'x {{nope}}'}, {})
    except build.BuildError:
        return
    raise AssertionError('unknown token accepted')


def test_config_switch_defaults():
    cfg = build.load(ATLAS, 'apps', 'client', 'config.json')
    sw = cfg['switches']
    assert sw['sam_kw_source'] == 'fit_register'
    assert sw['rego_labels'] == 'softened'
    assert sw['tam_colour_mode'] == 'fuels'
    assert cfg['publicUrl'] == 'https://renewablox-client-atlas-v2.streamlit.app/'
    assert cfg['contactEmail'] == 'callum@renewablox.com'


# ---------------------------------------------------------------------------------------------- investor build
def investor_build():
    if 'investor' not in _CACHE:
        _CACHE['investor'] = build.build_app('investor', [])
    return _CACHE['investor']


def test_investor_builds_within_budget():
    res = investor_build()
    assert res is not None
    assert res['size'] <= build.HTML_BUDGET, res['size']
    assert res['data'] <= build.DATA_BUDGET, res['data']
    assert build.INIT_MARKER in res['html']
    for f in ('core/js/investor/model.js', 'core/js/investor/band.js', 'core/js/investor/present.js', 'core/js/ppa.js'):
        assert f in res['files'], f
    assert res['files'][-1] == 'core/js/app.js'



def test_tam_merged_rows_keep_crm_order_and_drop_at_build():
    """CRM 10 Oct 2026: tam.json keeps every register row (row n = CRM TAM card #n); rows naming another row's plant in
    tam_merged.json are dropped at build. The Melton Ross AD's three FiT phases (#1188, #1205, #1240) merge into #110."""
    raw = build.load(build.DATA, 'shared', 'tam.json')
    into = build.load(build.DATA, 'shared', 'tam_merged.json')['into']
    assert len(raw) == 1309
    assert [raw[n - 1]['key'] for n in (110, 1188, 1205, 1240)] == ['tprospect-farm-bi-gcx', 'tnorth-lincolnshi-gcx',
                                                                  'tnorth-lincolnshi-gcx-2', 'tnorth-lincolnshi-gcx-3']
    assert sorted(into) == ['tnorth-lincolnshi-gcx', 'tnorth-lincolnshi-gcx-2', 'tnorth-lincolnshi-gcx-3']
    assert sum(r['kw'] for r in raw if r['key'] in into) == raw[109]['kw'] == 1993
    for data in (build.assemble_client({'switches': {}}), build.assemble_investor({'switches': {}})):
        keys = [r['key'] for r in data['tam']]
        assert len(keys) == 1306 and not set(into) & set(keys)
        t = next(r for r in data['tam'] if r['key'] == 'tprospect-farm-bi-gcx')
        assert t['sam'] == 'DN386AE' and t['bm'] == 0 and t['p'] == 0


def test_melton_ross_record_matches_crm():
    """SAM #110 (once 'Prospect Farm'): Singleton Birch's Melton Ross AD, output used by the lime works, still awaiting a BM figure."""
    for aud in ('client', 'investor'):
        data = build.assemble_client({'switches': {}}) if aud == 'client' else build.assemble_investor({'switches': {}})
        r = next(x for x in data['sam'] if x['key'] == 'DN386AE')
        assert (r['name'], r['op'], r['pc'], r['town']) == ('Singleton Birch Melton Ross AD', 'Singleton Birch Ltd', 'DN38 6AE', 'Barnetby')
        assert (r['kw'], r['kwOn'], r['kwBm'], r['mec']) == (1993, 1993, 0, 2800)
        assert abs(r['lat'] - 53.58647) < 1e-4 and abs(r['lon'] + 0.36446) < 1e-4
        assert not any('Prospect Farm' in str(v) or 'Castillium' in str(v) for v in r.values())
        if aud == 'investor':
            assert r['tcv'] is None and r['rank'] == 110            # stays "awaiting a BM figure"
    lay = next(r for r in build.load_tam() if r['key'] == 'tlaynes-piggery-b-gcr')
    assert (lay['f'], lay['kw'], lay['bm']) == ('Biogas (AD)', 498, 485)
    for out in ('client', 'investor', 'investor_v3'):
        with open(build.OUT[out], encoding='utf-8') as fh:
            html = fh.read()
        assert 'Prospect Farm' not in html and 'North Lincolnshire AD (DN38)' not in html, out
        assert 'Export connection' in html, out

def test_investor_committed_output_is_fresh():
    with open(build.OUT['investor'], encoding='utf-8') as fh:
        assert fh.read() == investor_build()['html'], 'investor_atlas_v2.html is stale: run python3 atlas/build.py'


def test_investor_headlines_are_computed():
    html = build.norm_text(investor_build()['html'])
    for s in ['£221.9M of contract value across 105 priced AD peakers',
              '£7.16bn indicative potential across 1,306 subsidised sites',
              '57 stranded hydro units worth £13.6M (£35.6M with treasury)']:
        assert s in html, s
    assert not re.search(r'\{\{[A-Za-z0-9_]+\}\}', html)


def test_investor_story_chapters():
    story = build.load(ATLAS, 'apps', 'investor', 'story.json')
    ch = story['chapters']
    assert len(ch) == 6
    assert [c['view'] for c in ch] == ['tam', 'sam', 'sam', 'hydro', 'ppa', 'ppa']
    with open(os.path.join(ATLAS, 'core', 'js', 'investor', 'present.js'), encoding='utf-8') as fh:
        src = fh.read()
    for c in ch:
        for s in c.get('stats', []):
            assert "'%s'" % s['expr'] in src, s['expr']        # every stat is computed from data at runtime
        assert not re.search(r'\d', re.sub(r'\{[^}]+\}', '', c['title'])), c['title']


def test_investor_config_switch_defaults():
    cfg = build.load(ATLAS, 'apps', 'investor', 'config.json')
    sw = cfg['switches']
    assert sw['sam_kw_source'] == 'fit_register'
    assert sw['rego_labels'] == 'raw'
    assert sw['tam_colour_mode'] == 'fuels'
    assert cfg['defaultTheme'] == 'night'
    assert cfg['publicUrl'] == 'https://renewablox-investor-atlas-v2.streamlit.app/'
    assert 'Confidential' in cfg['csvHeader']


def test_investor_wrapper_deep_links_whitelisted():
    with open(os.path.join(build.REPO, 'app_investor_atlas_v2.py'), encoding='utf-8') as fh:
        src = fh.read()
    assert 'INVESTOR_PASSWORD' not in src          # owner decision 3: Streamlit Cloud viewer allowlist only
    assert '"present": r"^1$"' in src


def investor_build():
    if 'investor' not in _CACHE:
        _CACHE['investor'] = build.build_app('investor', [])
    return _CACHE['investor']


def _inlined_config(html):
    m = re.search(r'window\.ATLAS_CONFIG=(\{.*?\});window\.ATLAS_DATA=', html, re.S)
    assert m, 'ATLAS_CONFIG not found'
    return json.loads(m.group(1))


def test_private_config_keys_never_inlined():
    """T03: maintainer notes (`_doc`, `_sam_kw_source` …) are stripped from the inlined config of both builds."""
    for res in (client_build(), investor_build(), investor_v3_build()):
        cfg = _inlined_config(res['html'])

        def walk(o, path=''):
            if isinstance(o, dict):
                for k, v in o.items():
                    assert not k.startswith('_'), path + '.' + k
                    walk(v, path + '.' + k)
            elif isinstance(o, list):
                for x in o:
                    walk(x, path)
        walk(cfg)
        assert 'Owner decisions pending' not in res['html'] and 'not CVD-validated' not in res['html']


def test_public_text_checks_both_apps():
    """T08/T09: researcher notes, private individuals, placeholders and lower-case names fail either build."""
    for app in ('client', 'investor'):
        data = build.ASSEMBLE[app]({'switches': {}})
        build.public_text_checks(app, data)          # the committed data passes
        for field, val, why in (('op', 'X Ltd (Dr Jane Smith)', 'research note'), ('name', 'Station farm', 'title-cased'),
                                ('name', 'Export', 'placeholder'), ('site', 'Home Farm, Rectory Lane LN9 6JC', 'postcode')):
            bad = copy.deepcopy(data)
            bad['sam'][0][field] = val
            try:
                build.public_text_checks(app, bad)
            except build.BuildError as e:
                assert why in str(e), (app, field, str(e))
            else:
                raise AssertionError('%s: %s=%r was not rejected' % (app, field, val))
        if app == 'investor':
            bad = copy.deepcopy(data)
            bad['sam'][0]['dev'] = 'Castillium Ltd (developer; SPV TBC)'
            try:
                build.public_text_checks(app, bad)
            except build.BuildError:
                pass
            else:
                raise AssertionError('investor dev research note was not rejected')


def test_withheld_names_and_people():
    data = build.assemble_client({'switches': {}})
    by = {r['key']: r for r in data['sam']}
    for k in ('OX106SL', 'DT28PE', 'SP78PX', 'RG73XJ', 'CO77BN', 'NR231NY'):
        assert re.fullmatch(r'AD site \([A-Z]{1,2}\d[A-Z\d]?\)', by[k]['name']), by[k]['name']
    assert by['PE220SE']['name'] == 'Station Farm'
    html = client_build()['html']
    for s in ('Stephen Temple', 'Neil Gemmell', 'Glyn family', 'was contractor', '--Redacted--', 'Adam Balch', 'adam-balch'):
        assert s not in html, s
    # a sole trader's personal name is never the public operator; the gated investor build keeps it
    assert by['SP78PX']['op'] == 'Private operator'
    assert not [r['op'] for r in data['sam'] if r.get('op') and extract_v1.is_personal_name(r['op'])]


def test_cdn_tags_non_blocking_with_sri():
    """T12: MapLibre JS/CSS carry SRI + crossorigin; no render-blocking third-party tag in either build."""
    for res in (client_build(), investor_build(), investor_v3_build()):
        html = res['html']
        head = html.split('<style>')[0]
        assert re.search(r'<script async src="https://cdn\.jsdelivr\.net/npm/maplibre-gl@[\d.]+/dist/maplibre-gl\.js" '
                         r'integrity="sha384-[A-Za-z0-9+/=]{64}" crossorigin="anonymous"', head)
        assert re.search(r'rel="preload" as="style" href="https://cdn\.jsdelivr\.net/[^"]+maplibre-gl\.css" integrity="sha384-', head)
        assert not re.search(r'rel="stylesheet"', re.sub(r'<noscript>.*?</noscript>', '', head))   # nothing render-blocking
        assert '<script src=' not in html                   # every external script is async


def test_fuel_palette_tokens_per_theme():
    """T06/D1: one 9-colour fuel set per theme in tokens.css; theme.js reads the tokens (no hard-coded hues)."""
    with open(os.path.join(ATLAS, 'core', 'css', 'tokens.css'), encoding='utf-8') as fh:
        css = fh.read()
    paper, night = css.split(':root[data-theme="night"]')
    sets = []
    for block in (paper, night):
        vals = [re.search(r'--fuel-%d:\s*(#[0-9A-Fa-f]{6})' % i, block) for i in range(9)]
        assert all(vals), 'missing --fuel-* token'
        sets.append([v.group(1).upper() for v in vals])
        assert len(set(sets[-1])) == 9
    assert sets[0] != sets[1]
    with open(os.path.join(ATLAS, 'core', 'js', 'theme.js'), encoding='utf-8') as fh:
        assert 'FUEL_HUES' not in fh.read()


def test_investor_display_names_clean_with_status_tag():
    """DI1: investor display names carry no research note; a factual company status ships as opSt (muted tag)."""
    data = build.assemble_investor({'switches': {}})
    html = investor_build()['html']
    build.investor_name_checks(data, html)               # the committed data and page pass
    by = {r['key']: r for r in data['sam']}
    assert by['FY85RP']['op'] == 'R-Group of Companies Limited' and by['FY85RP']['dev'] == 'R-Group of Companies Limited'
    assert by['FY85RP']['opSt'] == 'in liquidation'
    assert by['DN386AE']['dev'] == 'Singleton Birch Ltd' and 'opSt' not in by['DN386AE']
    for s in ('verify owner', 'SPV TBC', 'Farmgen', '(developer;'):
        assert s not in html, s
    for field, val in (('op', 'X Ltd (verify)'), ('dev', 'Castillium Ltd (developer; SPV TBC)'), ('name', 'Farm (site=Y)'),
                       ('dev', 'R-Group Limited (in liquidation)'), ('opSt', 'probably bust')):
        bad = copy.deepcopy(data)
        bad['sam'][0][field] = val
        try:
            build.investor_name_checks(bad)
        except build.BuildError:
            pass
        else:
            raise AssertionError('%s=%r was not rejected' % (field, val))
    try:
        build.investor_name_checks(data, html + '<!-- R-GROUP (in liquidation; site=Farmgen, Warton - verify owner) -->')
    except build.BuildError:
        pass
    else:
        raise AssertionError('research-note fragment in the HTML was not rejected')


SKIN_CSS = os.path.join(ATLAS, 'skins', 'product', 'skin-product.css')
SKIN_SCOPE = ':root[data-skin="product"]'


def _html_tag(html):
    return re.match(r'<!doctype html><html[^>]*>', html, re.I).group(0)


def test_client_uses_product_skin():
    """Client: <html data-skin="product">, skin CSS last and skin JS just before app.js; client-only files."""
    res = client_build()
    assert 'data-skin="product"' in _html_tag(res['html'])
    files = res['files']
    css = [f for f in files if f.endswith('.css')]
    js = [f for f in files if f.endswith('.js')]
    assert css[-1] == 'skins/product/skin-product.css', css[-3:]
    assert js[-2:] == ['skins/product/skin-product.js', 'core/js/app.js'], js[-3:]
    assert js.index('skins/product/skin-product.js') > js.index('apps/client/client.js')
    assert res['html'].count(SKIN_SCOPE) > 100            # the skin's rules are inlined
    assert 'RBX.skin' in res['html']
    # the panel label / one-line description the skin renders are configured for every map view
    cfg = build.load(ATLAS, 'apps', 'client', 'config.json')
    for v in ('sam', 'tam', 'hydro'):
        assert cfg['views'][v].get('label') and cfg['views'][v].get('summary'), v


def test_investor_never_gets_the_client_skin():
    """Investor keeps its own look: no data-skin attribute, no skin rules or module, no apps/client/ files."""
    res = investor_build()
    assert 'data-skin' not in _html_tag(res['html'])
    assert SKIN_SCOPE not in res['html'] and 'RBX.skin' not in res['html']
    assert not [f for f in res['files'] if f.startswith('apps/client/')], res['files']
    man = build.load(ATLAS, 'apps', 'investor', 'manifest.json')
    assert not [f for f in man['css'] + man['js'] if 'skin' in f or f.startswith('apps/client/')]


def test_client_carries_the_renewablox_brand():
    """Client: the official wordmarks inlined as --rbx-wordmark-* data URIs, the BLOX. roundel as a PNG favicon and
    Open Sans (the web fallback for Leelawadee UI) as the only web font. Investor keeps its own favicon and fonts."""
    res = client_build()
    head = res['html'].split('</head>', 1)[0]
    for name in ('light', 'dark', 'mono'):
        assert re.search(r'--rbx-wordmark-%s:url\("data:image/png;base64,[A-Za-z0-9+/=]{200,}"\)' % name, head), name
    assert re.search(r'<link rel="icon" href="data:image/png;base64,', head)
    fonts = re.search(r'href="(https://fonts\.googleapis\.com/css2\?[^"]+)"', head).group(1)
    assert 'family=Open+Sans' in fonts and 'Inter' not in fonts and 'Newsreader' not in fonts, fonts
    css = open(SKIN_CSS, encoding='utf-8').read()
    assert '--font-ui:"Leelawadee UI","Open Sans"' in css
    for hexcol in ('#156082', '#0B3549', '#218099', '#83CBEB'):
        assert hexcol in css, hexcol
    assert 'no Watt wasted' in res['html'] and 'aria-label="RenewaBlox"' in res['html']
    inv = investor_build()['html'].split('</head>', 1)[0]
    assert '--rbx-wordmark' not in inv and 'data:image/svg+xml;base64,' in inv and 'family=Inter' in inv


def test_brand_assets_stay_inside_atlas_brand():
    """build.data_uri only inlines existing images under atlas/brand/."""
    for bad in ('../client_atlas_v2.html', 'brand/missing.png', 'data/ai_sites.json'):
        try:
            build.data_uri(bad)
        except build.BuildError:
            continue
        raise AssertionError('%s was inlined' % bad)
    assert build.data_uri('brand/roundel-64.png').startswith('data:image/png;base64,')


def test_product_skin_rules_are_scoped():
    """Every selector in the skin stylesheet starts with :root[data-skin="product"], so it cannot style a page
    that does not opt in (at-rule wrappers and keyframe steps excepted)."""
    css = build.strip_css_comments(open(SKIN_CSS, encoding='utf-8').read())
    css = re.sub(r'@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}', '', css)   # drop keyframe blocks
    bad = []
    for m in re.finditer(r'([^{}]+)\{', css):
        prelude = m.group(1).strip()
        if not prelude or prelude.startswith('@'):
            continue
        for sel in prelude.split(','):
            if not sel.strip().startswith(SKIN_SCOPE):
                bad.append(sel.strip()[:80])
    assert not bad, bad[:10]
    js = open(os.path.join(ATLAS, 'skins', 'product', 'skin-product.js'), encoding='utf-8').read()
    assert "getAttribute('data-skin') !== 'product'" in js       # the module is inert without the attribute


def _lum(hexcol):
    c = [int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_product_skin_tier_ramp_is_ordered_and_visible():
    """Owner feedback on Direction B: Tier 5 was too faint on the light basemap. The skin's BM-tier ramp must stay
    an ordered ramp (luminance rising Tier 1 → Tier 5) whose faintest step clears 2:1 on each theme's land colour
    (light: Tier 5; dark: Tier 1). The land colours are the skin's own (--map-land), and the basemap palettes the
    skin registers must paint the same land."""
    css = open(SKIN_CSS, encoding='utf-8').read()
    js = open(os.path.join(ATLAS, 'skins', 'product', 'skin-product.js'), encoding='utf-8').read()
    light, dark = css.split(':root[data-skin="product"][data-theme="night"]{', 1)
    for block, theme, faint in ((light, 'paper', 4), (dark, 'night', 0)):
        land = re.search(r'--map-land:\s*(#[0-9A-Fa-f]{6})', block).group(1)
        assert re.search(r"name: '%s', land: '%s'" % (theme, land), js), (theme, land)
        ramp = [re.search(r'--tier-%d:\s*(#[0-9A-Fa-f]{6})' % i, block).group(1) for i in range(1, 6)]
        lums = [_lum(c) for c in ramp]
        assert lums == sorted(lums) and len(set(ramp)) == 5, ramp
        assert _contrast(ramp[faint], land) >= 2.0, (ramp[faint], land, _contrast(ramp[faint], land))


# ---------------------------------------------------------------------------------------------- investor v3 build
V3_DIR = os.path.join(ATLAS, 'apps', 'investor_v3')


def investor_v3_build():
    if 'investor_v3' not in _CACHE:
        _CACHE['investor_v3'] = build.build_app('investor_v3', [])
    return _CACHE['investor_v3']


def _split_selectors(prelude):
    """Split a selector list on top-level commas (commas inside :is()/:not() stay with their selector)."""
    out, depth, cur = [], 0, ''
    for ch in prelude:
        depth += ch == '('
        depth -= ch == ')'
        if ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    return out + [cur]


def test_investor_v3_builds_within_budget_with_skin_and_investor_modules():
    """v3 reuses the investor modules and numbers under the shared product skin; the skin JS precedes the investor
    modules (their sheet sections and legends win), the v3 overlay comes right before app.js, investor.css is not
    bundled, and the overlay CSS comes last."""
    res = investor_v3_build()
    assert res is not None and res['audience'] == 'investor'
    assert res['size'] <= build.HTML_BUDGET, res['size']
    assert res['data'] <= build.DATA_BUDGET, res['data']
    assert res['asserts'] == investor_build()['asserts']          # every investor canonical-number assert runs
    files = res['files']
    for f in ('core/js/investor/model.js', 'core/js/investor/band.js', 'core/js/investor/cards.js',
              'core/js/investor/present.js', 'core/js/ppa.js', 'skins/product/skin-product.js'):
        assert f in files, f
    assert files.index('skins/product/skin-product.js') < files.index('core/js/investor/model.js')
    js = [f for f in files if f.endswith('.js')]
    assert js[-1] == 'core/js/app.js' and js[-5] == 'apps/investor_v3/investor-v3.js', js[-6:]
    assert all(f.startswith('apps/investor_v3/') for f in js[-5:-1]), js[-6:]
    assert js.index('core/js/investor/present.js') < js.index('apps/investor_v3/investor-v3.js')
    css = [f for f in files if f.endswith('.css')]
    assert css[-4] == 'apps/investor_v3/investor-v3.css' and all(f.startswith('apps/investor_v3/') for f in css[-4:]), css[-5:]
    assert css.index('core/css/present.css') < css.index('skins/product/skin-product.css')
    assert 'apps/investor/investor.css' not in files and 'core/css/notes.css' not in files
    assert not [f for f in files if f.startswith('apps/client/')], files


def test_investor_v3_committed_output_is_fresh():
    with open(build.OUT['investor_v3'], encoding='utf-8') as fh:
        assert fh.read() == investor_v3_build()['html'], 'investor_atlas_v3.html is stale: run python3 atlas/build.py'


def test_investor_v3_drops_the_surplus_sections():
    """Owner feedback on v2: no GB power ticker and no rail headline block (kicker + headline + standfirst)."""
    cfg = build.load(V3_DIR, 'config.json')
    assert 'market' not in cfg
    for v in ('sam', 'tam', 'hydro'):
        assert 'standfirst' not in cfg['views'][v], v
    res = investor_v3_build()
    assert 'data-skin="product"' in _html_tag(res['html']) and 'data-app="investor"' in _html_tag(res['html'])
    js = open(os.path.join(V3_DIR, 'investor-v3.js'), encoding='utf-8').read()
    assert 'B.render = function () {};' in js and 'B.renderFoot = function () {};' in js
    css = open(os.path.join(V3_DIR, 'investor-v3.css'), encoding='utf-8').read()
    assert ':root[data-skin="product"] .band-slot,:root[data-skin="product"] .foot-slot{display:none}' in css
    # the skin hides the kicker/standfirst and keeps the headline for screen readers only
    skin = open(SKIN_CSS, encoding='utf-8').read()
    assert '.rail-body > .kicker' in skin and '.rail-body > .headline{position:absolute' in skin


def test_investor_v3_sheet_reregisters_the_investor_cards():
    """Spec §9: v3-sheet.js re-registers the SAM chip/head/commercials/revenue and the Hydro chip/commercials,
    reuses the core ladder via the registered section's `after`, and its stylesheet keeps sky as a hatch only."""
    js = open(os.path.join(V3_DIR, 'v3-sheet.js'), encoding='utf-8').read()
    for sec in ("Sh.section('sam', 'head', { order: 10", "Sh.section('sam', 'commercials', { order: 15",
                "Sh.section('sam', 'revenue', { order: 20", "Sh.section('hydro', 'commercials', { order: 15"):
        assert sec in js, sec
    assert "find('sam', 'revenue')" in js and 'Sh.chip.sam = ' in js and 'Sh.chip.hydro = ' in js
    assert 'I.uplift' in js and 'WHOLESALE' in js
    css = open(os.path.join(V3_DIR, 'v3-sheet.css'), encoding='utf-8').read()
    assert 'var(--v3-split-b)' in css and 'var(--v3-split-e)' in css
    assert not re.search(r'#8FD14F|#9EDB60|#0B2E2A|143,\s*209,\s*79', css, re.I)

def test_investor_v3_story_chapters():
    """v3 ships its own Present story (design spec §10.6): the v2 views, cameras, chapter filters and 9 s autoplay;
    a kicker on every chapter; titles without digits; every stat expr (and every {token}) is a STAT key quoted in
    present.js (or registered by v3-present.js); the contract-value hero stat sits on chapters 1, 2 and 4 only.
    (Replaces test_investor_v3_story_ships_from_the_investor_story.)"""
    story = build.load(V3_DIR, 'story.json')
    v2 = build.load(ATLAS, 'apps', 'investor', 'story.json')
    assert _inlined_config(investor_v3_build()['html'])['story'] == build.strip_private(story)
    ch = story['chapters']
    assert story['autoplayMs'] == 9000 and len(ch) == 6
    assert [c['view'] for c in ch] == ['tam', 'sam', 'sam', 'hydro', 'ppa', 'ppa']
    for a, b in zip(ch, v2['chapters']):
        assert (a.get('camera'), a.get('filters'), a.get('ppa')) == (b.get('camera'), b.get('filters'), b.get('ppa')), a['title']
    with open(os.path.join(ATLAS, 'core', 'js', 'investor', 'present.js'), encoding='utf-8') as fh:
        src = fh.read()
    with open(os.path.join(V3_DIR, 'v3-present.js'), encoding='utf-8') as fh:
        v3js = fh.read()
    assert "STAT['rev.t1up']" in v3js
    known = lambda k: "'%s'" % k in src or "STAT['%s']" % k in v3js
    hero = re.compile(r'^(sam|hydro)\.tcv$|^tam\.pot$')
    for i, c in enumerate(ch):
        assert c.get('kicker'), i
        assert not re.search(r'\d', re.sub(r'\{[^}]+\}', '', c['title'])), c['title']
        assert len(c['stats']) == 3, i
        texts = [c['title'], c['body']]
        for s in c['stats']:
            assert "'%s'" % s['expr'] in src, s['expr']          # computed from data at runtime, never typed
            texts += [s['label'], s.get('cap', '')]
        for tok in re.findall(r'\{([a-zA-Z0-9.]+)\}', ' '.join(texts)):
            assert known(tok), tok
        assert any(hero.match(s['expr']) for s in c['stats']) == (i in (0, 1, 3)), i


def test_investor_v3_present_overlay():
    """Present keeps the glass header at full opacity (a dimmed .hdr loses its backdrop blur), uses no lime or
    green-black and no text glyphs for Play / Pause."""
    with open(os.path.join(V3_DIR, 'v3-present.css'), encoding='utf-8') as fh:
        css = fh.read()
    assert ':root[data-skin="product"] .app.presenting .hdr,' in css and ':focus-within{opacity:1}' in css
    for bad in ('#0B2E2A', '#9EDB60', '#8FD14F', 'rgba(10,19,20', 'rgba(143,209,79', '--lime)', 'italic'):
        assert bad not in css, bad
    with open(os.path.join(V3_DIR, 'v3-present.js'), encoding='utf-8') as fh:
        js = fh.read()
    assert '▶' not in js and '❚' not in js


def test_investor_v3_brand_and_identity():
    res = investor_v3_build()
    head = res['html'].split('</head>', 1)[0]
    for name in ('light', 'dark', 'mono'):
        assert '--rbx-wordmark-%s:url("data:image/png;base64,' % name in head, name
    assert re.search(r'<link rel="icon" href="data:image/png;base64,', head)
    assert '<meta name="robots" content="noindex,nofollow">' in head
    cfg = build.load(V3_DIR, 'config.json')
    inv = build.load(ATLAS, 'apps', 'investor', 'config.json')
    assert cfg['audience'] == 'investor' and cfg['app'] == 'investor_v3'
    assert cfg['publicUrl'] == 'https://renewablox-investor-atlas-v3.streamlit.app/'
    assert cfg['storageKey'] != inv['storageKey']                    # never inherits v2's saved theme or view
    assert cfg['switches'] == inv['switches']
    assert 'Confidential' in cfg['csvHeader'] and 'Confidential' in cfg['imageBadge']



def test_investor_v3_kpis_use_known_metrics():
    """The brand KPI card reads views[v].kpis; every metric is an investor band metric or a core KPI metric."""
    cfg = build.load(V3_DIR, 'config.json')
    band = open(os.path.join(ATLAS, 'core', 'js', 'investor', 'band.js'), encoding='utf-8').read()
    kpi = open(os.path.join(ATLAS, 'core', 'js', 'kpi.js'), encoding='utf-8').read()
    known = set(re.findall(r'^\s{4}(\w+): function', band, re.M)) | set(re.findall(r'^\s{4}(\w+): function', kpi, re.M))
    for v in ('sam', 'tam', 'hydro'):
        vc = cfg['views'][v]
        assert vc.get('label') and vc.get('kpis'), v
        for k in vc['kpis']:
            assert k['metric'] in known, (v, k['metric'])


def test_investor_v3_overlay_rules_are_scoped():
    """Every selector in investor-v3.css starts with :root[data-skin="product"]; the overlay JS is inert elsewhere."""
    css = ''.join(build.strip_css_comments(open(os.path.join(V3_DIR, f), encoding='utf-8').read())
                  for f in sorted(os.listdir(V3_DIR)) if f.endswith('.css'))
    css = re.sub(r'@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}', '', css)
    bad = []
    for m in re.finditer(r'([^{}]+)\{', css):
        prelude = m.group(1).strip()
        if not prelude or prelude.startswith('@'):
            continue
        bad += [sel.strip()[:80] for sel in _split_selectors(prelude) if not sel.strip().startswith(SKIN_SCOPE)]
    assert not bad, bad[:10]
    for f in sorted(os.listdir(V3_DIR)):
        if f.endswith('.js'):
            js = open(os.path.join(V3_DIR, f), encoding='utf-8').read()
            assert "getAttribute('data-skin') !== 'product' || doc.getAttribute('data-app') !== 'investor'" in js, f


def test_investor_v3_wrapper_gated_and_deep_links_whitelisted():
    with open(os.path.join(build.REPO, 'app_investor_atlas_v3.py'), encoding='utf-8') as fh:
        src = fh.read()
    assert 'INVESTOR_PASSWORD' not in src          # owner decision 3: Streamlit Cloud viewer allowlist only
    assert '"present": r"^1$"' in src and '"investor_atlas_v3.html"' in src
    assert 'roundel-192.png' in src


def test_v2_pages_untouched_by_v3():
    """Investor v2 stays unskinned (its own manifest, no brand block, no skin files)."""
    man = build.load(ATLAS, 'apps', 'investor', 'manifest.json')
    assert 'brand' not in man and 'apps/investor/investor.css' in man['css']
    assert not [f for f in man['css'] + man['js'] if f.startswith('skins/') or 'investor_v3' in f]

if __name__ == '__main__':
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print('ok   ', name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print('FAIL ', name, '-', e)
    print('%d failed' % fails if fails else 'all passed')
    sys.exit(1 if fails else 0)
