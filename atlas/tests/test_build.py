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
    """CI guard (same as `build.py --check`): the committed client_atlas.html is a fresh build."""
    with open(build.OUT['client'], encoding='utf-8') as fh:
        assert fh.read() == client_build()['html'], 'client_atlas.html is stale: run python3 atlas/build.py'


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
        build.client_safety(bad, '/*__ATLAS_INIT__*/', 'softened')
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
    for s in ['129 sites · 144 MW', '1,309 sites · 3,612 MW', '57 sites · 15.2 MW stranded']:
        assert s in html, s
    assert '3611.9' not in html


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
    assert cfg['publicUrl'] == 'https://renewablox-client-atlas.streamlit.app/'
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


def test_investor_committed_output_is_fresh():
    with open(build.OUT['investor'], encoding='utf-8') as fh:
        assert fh.read() == investor_build()['html'], 'investor_atlas.html is stale: run python3 atlas/build.py'


def test_investor_headlines_are_computed():
    html = build.norm_text(investor_build()['html'])
    for s in ['£221.9M of contract value across 105 priced AD peakers',
              '£7.17bn indicative potential across 1,309 subsidised sites',
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
    assert cfg['publicUrl'] == 'https://renewablox-investor-atlas.streamlit.app/'
    assert 'Confidential' in cfg['csvHeader']


def test_investor_wrapper_deep_links_whitelisted():
    with open(os.path.join(build.REPO, 'app_investor_atlas.py'), encoding='utf-8') as fh:
        src = fh.read()
    assert 'INVESTOR_PASSWORD' not in src          # owner decision 3: Streamlit Cloud viewer allowlist only
    assert '"present": r"^1$"' in src


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
