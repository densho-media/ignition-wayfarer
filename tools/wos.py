#!/usr/bin/env python3
"""Wayfarer Operating System (WOS): the module registry, the generated ship-state record (wos.json) and the ship line baked
into every page of the site. docs/WOS.md is the standard.

Every value the shell shows comes from data/wayfarer_3d.toml through the pure modules, with its canon status and source; an
unknown stays OPEN. The ship line is static HTML written at build time (no layout shift, works without JavaScript).
`python3 tools/wos.py --out DIR` builds a preview of the site without Blender (the viewer opens without a model there)."""

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
sys.path.insert(0, str(ROOT / 'tools'))

# The module registry: the one list of what the ship's interface offers. `paths` claims site paths for a module (longest
# prefix wins); `station` is the fictional station the module is used from on a workstation layout (PROTOTYPE device label).
MODULES = [
    {'id': 'overview', 'label': 'Overview', 'key': 'o', 'href': '', 'station': 'OPS Console', 'paths': ['index.html']},
    {'id': 'ship', 'label': 'Ship', 'key': 's', 'href': 'viewer/', 'station': 'Engineering Workstation', 'paths': ['viewer/']},
    {'id': 'sims', 'label': 'Simulations', 'key': 'm', 'href': 'engineering/#simulations', 'station': 'Simulation Workstation',
     'paths': ['engineering/ignition/', 'engineering/dust/', 'engineering/build/', 'engineering/compare/', 'engineering/breakthrough-lab/']},
    {'id': 'records', 'label': 'Records', 'key': 'r', 'href': 'engineering/', 'station': 'Engineering Workstation', 'paths': ['engineering/']},
    {'id': 'aboard', 'label': 'Aboard', 'key': 'a', 'href': 'interior/', 'station': 'OPS Console',
     'paths': ['interior/', 'exterior/', 'play/']},
    {'id': 'system', 'label': 'System', 'key': 'y', 'href': 'status/', 'station': 'OPS Console', 'paths': ['status/']},
]
# One line icon per module, 20 x 20, stroke only (currentColor).
ICONS = {
    'overview': '<rect x="3" y="3" width="6" height="6"/><rect x="11" y="3" width="6" height="6"/><rect x="3" y="11" width="6" height="6"/><rect x="11" y="11" width="6" height="6"/>',
    'ship': '<path d="M2 10h12l4-2.5v5L14 10"/><path d="M5 6.5v7M9 7.5v5"/>',
    'sims': '<path d="M2 10c2-6 4-6 6 0s4 6 6 0 3-4 4-2"/>',
    'records': '<path d="M5 2.5h7l3 3v12H5z"/><path d="M7.5 9h5M7.5 12h5M7.5 15h3"/>',
    'aboard': '<path d="M5 18V3h10v15"/><path d="M3 18h14"/><circle cx="12" cy="11" r=".8"/>',
    'system': '<circle cx="10" cy="10" r="7"/><path d="M10 10l4-3M10 4v1.5M4 10h1.5M16 10h-1.5"/>',
}
MARK = re.compile(r'<!--wos:(bar|state|advisories)-->')
CLASS_NAMES = {'SPEC': 'Specification', 'NOM': 'Nominal operating condition', 'SIM': 'Simulation state', 'SCENARIO': 'Scenario state',
               'EXAMPLE': 'Illustrative value'}
ADVISORY_LEVEL = {'unresolved': 'warning', 'speculative': 'caution', 'assumed': 'caution', 'calculated': 'caution'}


def esc(s):
    return html.escape(str(s), quote=True)


def module_for(rel):
    """The module a site path belongs to (longest claimed prefix)."""
    best, size = None, -1
    for m in MODULES:
        for p in m['paths']:
            if (rel == p or (p.endswith('/') and rel.startswith(p))) and len(p) > size:
                best, size = m, len(p)
    return best


# ---------------------------------------------------------------------------------------------------------------- the record
def _item(label, value, unit, status, source, cls='SPEC', fmt=None, basis=None):
    out = {'label': label, 'class': cls, 'known': value is not None, 'unit': unit, 'canon_status': status, 'source_ref': source}
    if value is not None:
        out['value'] = value
        out['text'] = fmt.format(value) if fmt else str(value)
    if basis:
        out['basis'] = basis
    return out


def _open(label, field):
    return {'label': label, 'class': 'SPEC', 'known': False, 'canon_status': field.get('canon_status', 'OPEN'),
            'source_ref': field.get('source_ref') or field.get('evidence_ref'), 'reason': field.get('reason', '')}


def status(spec=None, register=None):
    """wos.json: the reference configuration, the sourced figures the ship line shows and the standing advisories."""
    import habitat_ring
    if spec is None:
        import spec as spec_module
        spec = spec_module.load(ROOT)[0]
    s = spec
    ref = s['vehicle']['saved_preset']
    cfg = s['configuration'][ref]
    h, atm, mission, crew = s['habitat'], s['habitat']['atmosphere'], s['mission'], s['crew']
    items = {
        'configuration': _item('Reference configuration', ref, None, cfg['canon_status'], cfg['source_ref'], 'NOM'),
        'drive': _item('Drive', cfg['drive'], None, cfg['canon_status'], cfg['source_ref'], 'NOM'),
        'habitat': _item('Habitat rings', cfg['habitat'], None, cfg['canon_status'], cfg['source_ref'], 'NOM'),
        'thermal_load': _item('Thermal load', cfg['thermal_load'], None, cfg['canon_status'], cfg['source_ref'], 'NOM'),
        'ring_rpm': _item('Ring rate', float(h['rpm']), 'rpm', h['canon_status'], h['source_ref'], 'SPEC', '{:.1f}'),
        'spin_gravity': _item('Gravity at the ring floor', round(habitat_ring.floor_gravity_g(s), 3), 'g', 'DERIVED', h['floor_radius']['source_ref'],
                              'SPEC', '{:.2f}', 'ω² r / g0 at the floor radius (habitat_ring.floor_gravity_g)'),
        'floor_radius': _item('Ring floor radius', float(h['floor_radius']['value']), 'm', h['floor_radius']['canon_status'],
                              h['floor_radius']['source_ref'], 'SPEC', '{:.0f}'),
        'cabin_pressure': _item('Cabin pressure', float(atm['cabin_pressure_kpa']), 'kPa', atm['canon_status'], atm['source_ref'], 'NOM', '{:.0f}'),
        'cabin_o2': _item('Cabin O2 partial pressure', float(atm['o2_partial']['value']), 'kPa', atm['o2_partial']['canon_status'],
                          atm['o2_partial']['source_ref'], 'NOM', '{:.0f}'),
        'target_speed': _item('Cruise speed', float(mission['target_speed']['value']), 'c', mission['target_speed']['canon_status'],
                              mission['target_speed']['source_ref'], 'SPEC', '{:.3f}'),
        'mission_duration': _item('Mission duration', float(mission['duration']['value']), 'yr', mission['duration']['canon_status'],
                                  mission['duration']['source_ref'], 'SPEC', '{:.1f}'),
        'length': _item('Body length', float(s['ship']['length']['value']), 'm', s['ship']['length']['canon_status'],
                        s['ship']['length']['source_ref'], 'SPEC', '{:.1f}', 'aft end to shield face; selection PROTOTYPE'),
        'crew_rated': _item('Crew (design occupancy)', int(crew['rated_occupancy']['value']), 'persons',
                            crew['rated_occupancy']['canon_status'], crew['rated_occupancy']['source_ref']),
        'power_rating': _open('Electrical load', s['power']['rating']),
    }
    reg = register or []
    by_status = {}
    for r in reg:
        by_status[r['status']] = by_status.get(r['status'], 0) + 1
    holds = ['Flight EVA: HOLD (S&E 45 O-07); Explore Exterior is a training simulation.']
    advisories = {'problems': len(reg), 'by_status': by_status, 'holds': holds, 'total': len(reg) + len(holds),
                  'items': [{'id': r['id'], 'title': r['title'], 'status': r['status'], 'level': ADVISORY_LEVEL.get(r['status'], 'caution')}
                            for r in reg]}
    return {'contract': 'WF_WOS_STATUS', 'version': 1, 'vessel': 'G.U. WAYFARER 001', 'reference_configuration': ref,
            'classes': CLASS_NAMES, 'items': items,
            'surfaces': {'viewer': ref, 'play': 'DOCKED'},
            'advisories': advisories,
            'modules': [{k: m[k] for k in ('id', 'label', 'href', 'station')} | {'station_status': 'PROTOTYPE'} for m in MODULES],
            'examples': {}}


def validate(st, source_map):
    """Every shown item carries a status and a source the source map names; an unknown carries no value."""
    problems = []
    for key, it in st['items'].items():
        if not it.get('canon_status'):
            problems.append(f'wos.json {key}: no canon status')
        if it.get('source_ref') and it['source_ref'] not in source_map:
            problems.append(f'wos.json {key}: source_ref {it["source_ref"]!r} is not in data/source_map.toml')
        if not it['known'] and 'value' in it:
            problems.append(f'wos.json {key}: an unknown carries a value')
    return problems


# ---------------------------------------------------------------------------------------------------------------- rendering
def _chip(cls):
    return f'<span class="wos-cls cls-{cls}" title="{esc(CLASS_NAMES[cls])}">{cls}</span>'


def _status(st):
    word = re.sub(r'[^A-Z_]', '', str(st).upper()) or 'NONE'
    return f'<span class="st st-{word}">{esc(st)}</span>'


def state_table(st, caption=True):
    rows = []
    for key, it in st['items'].items():
        if it['known']:
            unit = f' <small>{esc(it["unit"])}</small>' if it.get('unit') else ''
            val = f'<span class="num">{esc(it["text"])}</span>{unit}'
        else:
            val = f'<span class="wos-open" title="{esc(it.get("reason", ""))}">OPEN</span>'
        src = f'<br><code class="src" title="data/source_map.toml">{esc(it["source_ref"])}</code>' if it.get('source_ref') else ''
        note = f'<br><small class="muted">{esc(it.get("basis") or it.get("reason") or "")}</small>' if (it.get('basis') or it.get('reason')) else ''
        rows.append(f'<tr data-item="{key}"><th scope="row">{esc(it["label"])}{src}{note}</th><td class="v">{val}</td>'
                    f'<td>{_chip(it["class"])} {_status(it["canon_status"])}</td></tr>')
    cap = (f'<caption>Reference configuration {esc(st["reference_configuration"])}: the state the published model is built in. '
           'Generated from the spec; no live telemetry.</caption>') if caption else ''
    return (f'<div class="scroll wos-table" tabindex="0"><table>{cap}<thead><tr><th scope="col">Item</th><th scope="col">Value</th>'
            f'<th scope="col">Class · status</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def advisories_list(st, prefix):
    a = st['advisories']
    items = ''.join(f'<li class="adv-{i["level"]}"><a href="{prefix}engineering/#problems"><code>{esc(i["id"])}</code> {esc(i["title"])}</a>'
                    f' <span class="st st-{esc(i["status"].upper())}">{esc(i["status"])}</span></li>' for i in a['items'])
    holds = ''.join(f'<li class="adv-hold"><span class="st st-HOLD">HOLD</span> {esc(h)}</li>' for h in a['holds'])
    return f'<ul class="wos-adv">{holds}{items}</ul>'


def bar(prefix, module, st, local=False):
    """The ship line: vessel mark, module switcher, the reference state, advisories and the station label."""
    it = st['items']
    nav = []
    for m in MODULES:
        cur = ' aria-current="page"' if module and m['id'] == module['id'] else ''
        nav.append(f'<a href="{prefix}{m["href"]}" data-wos-key="{m["key"]}"{cur}><svg viewBox="0 0 20 20" aria-hidden="true">{ICONS[m["id"]]}</svg>'
                   f'<span>{m["label"]}</span></a>')
    chips = (f'<span class="wos-chip"><b>{esc(st["reference_configuration"])}</b></span>'
             f'<span class="wos-chip w2">DRIVE {esc(it["drive"]["text"])}</span>'
             f'<span class="wos-chip w1">RINGS {esc(it["ring_rpm"]["text"])} rpm · {esc(it["spin_gravity"]["text"])} g</span>'
             f'<span class="wos-chip w2">CABIN {esc(it["cabin_pressure"]["text"])} kPa</span>'
             f'<span class="wos-chip adv" title="Standing advisories: open engineering problems and HOLD items">ADV {st["advisories"]["total"]}</span>')
    station = esc((module or MODULES[0])['station']).upper()
    keys = ' · '.join(f'<kbd>g</kbd> <kbd>{m["key"]}</kbd> {m["label"]}' for m in MODULES)
    # A page that shows the full state itself (Overview, System) links to it instead of repeating it in the sheet.
    detail = ('<p class="wos-sheet-h">The ship state and the advisories are on this page: <a href="#ship-state">Ship state</a> · '
              '<a href="#advisories">Advisories</a></p>') if local else (
        f'<p class="wos-sheet-h">Ship state · {_chip("NOM")} nominal and {_chip("SPEC")} specification values from the model, '
        f'not telemetry</p>{state_table(st, caption=False)}<p class="wos-sheet-h">Advisories</p>{advisories_list(st, prefix)}')
    sheet = (f'<div class="wos-sheet" role="group" aria-label="Ship state">{detail}'
             f'<p class="muted small">Station: {station} on a wide screen, PERSONAL TERMINAL on a phone. Device names are '
             f'<span class="st st-PROTOTYPE">PROTOTYPE</span>; the layout follows your screen and every function is on every size. '
             f'Keys: {keys} · <kbd>\\</kbd> focus mode.</p></div>')
    return (f'<a class="wos-skip" href="#wos-work">Skip to the workspace</a>'
            f'<header class="wos-bar" id="wos-bar">'
            f'<a class="mark" href="{prefix}" title="G.U. WAYFARER 001 · Overview"><span class="wos-logo" aria-hidden="true"></span>'
            f'<span class="wos-vessel">G.U. WAYFARER 001</span></a>'
            f'<nav class="wos-nav" aria-label="Modules">{"".join(nav)}</nav>'
            f'<span class="wos-scn" role="status" hidden></span>'
            f'<details class="wos-state"><summary title="Ship state and advisories">{chips}</summary>{sheet}</details>'
            f'<span class="wos-station" title="Station profile (PROTOTYPE)"><span class="ws">{station}</span>'
            f'<span class="tm">PERSONAL TERMINAL</span></span>'
            f'</header>')


def bake(site, st, skip=('play/',)):
    """Replace the WOS markers in every page of the built site; returns the pages and any page left without a bar."""
    site = Path(site)
    baked, problems = [], []
    for page in sorted(site.rglob('*.html')):
        rel = page.relative_to(site).as_posix()
        if any(rel.startswith(p) for p in skip) or '/vendor/' in rel:
            continue
        text = page.read_text()
        if '<!--wos:' not in text:
            continue
        prefix = '../' * rel.count('/')
        module = module_for(rel)
        local = '<!--wos:state-->' in text
        out = MARK.sub(lambda m: {'bar': lambda: bar(prefix, module, st, local), 'state': lambda: state_table(st),
                                  'advisories': lambda: advisories_list(st, prefix)}[m.group(1)](), text)
        if out.count('class="wos-bar"') != 1:
            problems.append(f'{rel}: {out.count(chr(60) + "header class=" + chr(34) + "wos-bar")} ship lines (one expected)')
        page.write_text(out)
        baked.append(rel)
    return baked, problems


def write(site, st):
    text = json.dumps(st, indent=1, ensure_ascii=False) + '\n'
    (Path(site) / 'wos.json').write_text(text)
    return len(text.encode())


def build(site, register=None):
    """Write wos.json and bake every page; returns a summary for release.json."""
    import tomllib
    st = status(register=register)
    source_map = tomllib.loads((ROOT / 'data/source_map.toml').read_text())['sources']
    problems = validate(st, source_map)
    size = write(site, st)
    pages, bake_problems = bake(site, st)
    return {'entry': 'wos.json', 'bytes': size, 'pages': len(pages), 'problems': problems + bake_problems}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path, required=True, help='preview site directory (replaced)')
    args = ap.parse_args()
    import story
    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / 'web', out, ignore=shutil.ignore_patterns('README.md', 'shell.html'))
    eng = story.build(ROOT, out, play=False)
    print(json.dumps({'engineering_pages': len(eng['pages']), **build(out, eng.get('register'))}, indent=1))


if __name__ == '__main__':
    main()
