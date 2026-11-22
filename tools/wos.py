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

# The module registry: the one list of what the ship's interface offers, by visitor intention (docs/WOS.md section 2).
# `paths` claims site paths for a module (longest prefix wins); `sub` are the module's sections (the tab row); `alias` keeps the
# shortcut letters of earlier module names; `station` is the fictional station label (PROTOTYPE, shown in the help sheet only).
MODULES = [
    {'id': 'overview', 'label': 'Overview', 'icon': 'overview', 'key': 'o', 'href': '', 'station': 'OPS Console', 'paths': ['index.html'],
     'sub': []},
    {'id': 'explore', 'label': 'Explore', 'icon': 'ship', 'key': 'e', 'alias': 'sa', 'href': 'viewer/', 'station': 'Engineering Workstation',
     'paths': ['viewer/', 'interior/', 'exterior/', 'play/'],
     'sub': [{'label': 'Ship 3D', 'icon': 'ship', 'href': 'viewer/', 'paths': ['viewer/']},
             {'label': 'Interior', 'icon': 'interior', 'href': 'interior/', 'paths': ['interior/']},
             {'label': 'Exterior', 'icon': 'eva', 'href': 'exterior/', 'paths': ['exterior/']}]},
    {'id': 'sims', 'label': 'Simulations', 'icon': 'sim', 'key': 'm', 'href': 'simulations/', 'station': 'Simulation Workstation',
     'paths': ['simulations/', 'engineering/fusion/', 'engineering/ignition/', 'engineering/dust/', 'engineering/build/', 'engineering/compare/',
               'engineering/breakthrough-lab/'],
     'sub': [{'label': 'All', 'href': 'simulations/', 'paths': ['simulations/']},
             {'label': 'Fusion engine', 'href': 'engineering/fusion/', 'paths': ['engineering/fusion/']},
             {'label': 'Ignition', 'href': 'engineering/ignition/', 'paths': ['engineering/ignition/']},
             {'label': 'Dust', 'href': 'engineering/dust/', 'paths': ['engineering/dust/']},
             {'label': 'Build sequence', 'href': 'engineering/build/', 'paths': ['engineering/build/']},
             {'label': 'Compare', 'href': 'engineering/compare/', 'paths': ['engineering/compare/']},
             {'label': 'Breakthrough Lab', 'href': 'engineering/breakthrough-lab/', 'paths': ['engineering/breakthrough-lab/']}]},
    {'id': 'engineering', 'label': 'Engineering', 'icon': 'engineering', 'key': 'n', 'alias': 'r', 'href': 'engineering/',
     'station': 'Engineering Workstation', 'paths': ['engineering/'],
     'sub': [{'label': 'Summary', 'href': 'engineering/', 'paths': ['engineering/index.html']},
             {'label': 'Baseline', 'href': 'engineering/baseline/', 'paths': ['engineering/baseline/']},
             {'label': 'Weakest links', 'href': 'engineering/weakest-links/', 'paths': ['engineering/weakest-links/']},
             {'label': 'Ship evolution', 'href': 'engineering/evolution/', 'paths': ['engineering/evolution/']},
             {'label': 'Vertex drive', 'icon': 'propulsion', 'href': 'engineering/vertex/', 'paths': ['engineering/vertex/']},
             {'label': 'Open problems', 'icon': 'alert', 'href': 'engineering/#problems', 'paths': ['engineering/problems/']},
             {'label': 'Lab records', 'icon': 'records', 'href': 'engineering/#tried',
              'paths': ['engineering/studies/', 'engineering/variants/']}]},
    {'id': 'status', 'label': 'Status', 'icon': 'status', 'key': 't', 'alias': 'y', 'href': 'status/', 'station': 'OPS Console',
     'paths': ['status/'],
     'sub': [{'label': 'Ship state', 'href': 'status/#ship-state', 'paths': ['status/']},
             {'label': 'Advisories', 'icon': 'alert', 'href': 'status/#advisories', 'paths': []},
             {'label': 'System', 'icon': 'help', 'href': 'status/#system', 'paths': []}]},
]
# The simulations, as the Simulations module and the Overview present them (thumbnail names in web/thumbs/, tools/thumbs.py).
SIMS = [
    {'href': 'engineering/fusion/', 'thumb': 'sim-fusion', 'title': 'Fusion engine', 'icon': 'propulsion',
     'line': 'Where the energy of a fusion burn goes: thrust, neutrons, X-rays or heat.', 'meta': 'Drawn live · no model download'},
    {'href': 'engineering/ignition/', 'thumb': 'sim-ignition', 'title': 'Ignition', 'icon': 'propulsion',
     'line': 'Switch the drive on and see what breaks first.', 'meta': 'Engine parts in 3D · about 0.4 MB'},
    {'href': 'engineering/dust/', 'thumb': 'sim-dust', 'title': 'Dust', 'icon': 'alert',
     'line': 'One grain of dust at 0.016 c, and the shield that has to stop it.', 'meta': 'Drawn live · no model download'},
    {'href': 'engineering/build/', 'thumb': 'sim-build', 'title': 'Build sequence', 'icon': 'ship',
     'line': 'How the ship would be assembled in orbit, step by step.', 'meta': 'Ship model in 3D'},
    {'href': 'engineering/compare/', 'thumb': 'sim-compare', 'title': 'Compare', 'icon': 'engineering',
     'line': 'What the design has, next to what each problem needs.', 'meta': 'Ship model in 3D'},
    {'href': 'engineering/breakthrough-lab/', 'thumb': 'sim-lab', 'title': 'Breakthrough Lab', 'icon': 'sim',
     'line': 'Switch on assumed breakthroughs and see whether the design closes.', 'meta': 'Illustrative scenarios'},
]
# One icon family: 24 px grid, stroke 1.75, round caps, currentColor; one meaning per icon (docs/WOS.md section 7).
ICONS = {
    'overview': '<rect x="3.5" y="3.5" width="7" height="7" rx="1"/><rect x="13.5" y="3.5" width="7" height="7" rx="1"/><rect x="3.5" y="13.5" width="7" height="7" rx="1"/><rect x="13.5" y="13.5" width="7" height="7" rx="1"/>',
    'ship': '<path d="M4 12h15.5M19.5 6.5v11M4 9v6M6.5 10.5v3"/><ellipse cx="13.5" cy="12" rx="1.8" ry="5"/>',
    'interior': '<rect x="6" y="3.5" width="12" height="17" rx="5"/><circle cx="12" cy="12" r="2.2"/><path d="M3.5 20.5h17"/>',
    'eva': '<circle cx="12" cy="9.5" r="6"/><rect x="8.5" y="7.5" width="7" height="4.5" rx="2"/><path d="M5 20.5c.6-3 2.2-4.6 4-5.2M19 20.5c-.6-3-2.2-4.6-4-5.2"/>',
    'sim': '<path d="M3.5 4v16.5H20.5"/><path d="M7 16c2.5 0 3-8 6-8s3 5 6.5 5"/>',
    'engineering': '<circle cx="12" cy="5" r="1.8"/><path d="M11.2 6.6L6 20.5M12.8 6.6l5.2 13.9M8.2 15.5h7.6"/>',
    'status': '<path d="M4.5 17.5a8.5 8.5 0 1 1 15 0"/><path d="M12 14.5l4-5.5"/><circle cx="12" cy="14.5" r="1"/>',
    'help': '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.6a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2 1-1.2 1.8M12 16.6v.2"/>',
    'records': '<path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4M9 12h6M9 15.5h6"/>',
    'propulsion': '<path d="M8 3.5h8l-1 4 3.5 7h-13L9 7.5z"/><path d="M9 18v2.5M12 18v3M15 18v2.5"/>',
    'power': '<path d="M13 3l-7 10h5l-1 8 7-10h-5z"/>',
    'thermal': '<rect x="4" y="5" width="9" height="14" rx="1"/><path d="M6.5 9h4M6.5 12h4M6.5 15h4M16 8c1.5 1.3-1.5 2.7 0 4s-1.5 2.7 0 4M19 8c1.5 1.3-1.5 2.7 0 4s-1.5 2.7 0 4"/>',
    'habitat': '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2"/><path d="M12 3.5V10M12 14v6.5M3.5 12H10M14 12h6.5"/>',
    'navigation': '<path d="M4 18c3-9 9-13 16-13"/><circle cx="4" cy="18" r="1.5"/><path d="M16.5 3.5L20 5l-1.5 3.5"/>',
    'alert': '<path d="M12 4l9 16H3z"/><path d="M12 10v4.5M12 17.2v.1"/>',
    'settings': '<path d="M4 7h10M18 7h2M4 12h4M12 12h8M4 17h12M20 17h0"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="17" r="2"/>',
    'info': '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.1"/>',
    'lock': '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'close': '<path d="M6 6l12 12M18 6L6 18"/>',
}
MARK = re.compile(r'<!--wos:(bar|state|advisories|facts|sims|thumb)(?: ([a-z0-9 -]+))?-->')
CLASS_NAMES = {'SPEC': 'Specification', 'NOM': 'Nominal operating condition', 'SIM': 'Simulation state', 'SCENARIO': 'Scenario state',
               'EXAMPLE': 'Illustrative value'}
ADVISORY_LEVEL = {'unresolved': 'warning', 'speculative': 'caution', 'assumed': 'caution', 'calculated': 'caution'}


def esc(s):
    return html.escape(str(s), quote=True)


def _claims(rel, p):
    return rel == p or (p.endswith('/') and rel.startswith(p))


def module_for(rel):
    """The module a site path belongs to (longest claimed prefix)."""
    best, size = None, -1
    for m in MODULES:
        for p in m['paths']:
            if _claims(rel, p) and len(p) > size:
                best, size = m, len(p)
    return best


def sub_for(module, rel):
    """The module section (tab) a site path belongs to, if any (longest claimed prefix)."""
    best, size = None, -1
    for t in (module or {}).get('sub', []):
        for p in t['paths']:
            if _claims(rel, p) and len(p) > size:
                best, size = t, len(p)
    return best


def icon(name, cls='wos-i'):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


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


# Thumbnails (web/thumbs/, written by tools/thumbs.py): what each picture is, so an illustration is never read as the model.
THUMBS = {
    'ship-side': ('MODEL', 'Wayfarer from the side: engines on the left, radiators, the two habitat rings, the bow shield on the right'),
    'ship-3d': ('MODEL', 'Wayfarer in the 3D viewer, seen from three-quarter view'),
    'interior': ('MODEL', 'A habitat ring room cut open, showing the deck, rooms and a person for scale'),
    'exterior': ('MODEL', 'The bow of Wayfarer at close range: the shield and the forward structure'),
    'sim-fusion': ('SIM', 'The Fusion engine explainer: the energy budget of a D-3He burn, from fusion power to thrust and heat'),
    'sim-ignition': ('SIM', 'The Ignition simulation: the engine cluster at the moment of overload'),
    'sim-dust': ('SIM', 'The Dust simulation: one grain hitting the shield layer at test speed and at cruise speed'),
    'sim-build': ('MODEL', 'The Build sequence: the ship partly assembled'),
    'sim-compare': ('MODEL', 'The Compare view: the ship next to what one problem needs, at one scale'),
    'sim-lab': ('ILLUSTRATIVE', 'The Breakthrough Lab: assumed breakthroughs switched on against the design gaps'),
    'engineering': ('MODEL', 'The whole ship with each subsystem in its own colour: structure, drive, thermal, habitat, forward and service'),
}
THUMB_CLASS = {'MODEL': 'Model', 'SIM': 'Simulation', 'SCHEMATIC': 'Schematic', 'ILLUSTRATIVE': 'Illustrative'}


def thumb(prefix, name, sizes='(min-width: 1100px) 25vw, (min-width: 700px) 50vw, 160px', band=False, eager=False):
    """A lazy, responsive thumbnail with its representation chip (docs/WOS.md section 7)."""
    cls, alt = THUMBS[name]
    w, h, big = (960, 320, 1920) if band else (480, 270, 960)
    load = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<span class="wos-thumb{" band" if band else ""}"><img src="{prefix}thumbs/{name}-{w}.webp" '
            f'srcset="{prefix}thumbs/{name}-{w}.webp {w}w, {prefix}thumbs/{name}-{big}.webp {big}w" sizes="{sizes}" width="{w}" '
            f'height="{h}" alt="{esc(alt)}" {load} decoding="async"><span class="wos-tc tc-{cls}">{THUMB_CLASS[cls]}</span></span>')


def _thumb_mark(prefix, args):
    name, *flags = args.split()
    if 'band' in flags:
        return thumb(prefix, name, sizes='(min-width: 1100px) 58vw, 100vw', band=True, eager=True)
    return thumb(prefix, name)


def facts(st, prefix):
    """The ship in numbers: the values a newcomer asks for first, from wos.json; status and sources behind a disclosure."""
    it, adv = st['items'], st['advisories']
    tiles = [('length', 'ship', 'Length', 'bow shield to engines'),
             ('crew_rated', 'interior', 'Crew', 'design occupancy'),
             ('target_speed', 'navigation', 'Cruise speed', 'c is the speed of light'),
             ('mission_duration', 'navigation', 'Mission', 'out and back'),
             ('spin_gravity', 'habitat', 'Gravity on the ring', f'rings turn at {it["ring_rpm"]["text"]} rpm')]
    unit = {'persons': '', 'yr': 'years'}
    out = []
    for key, ic, label, sub in tiles:
        i = it[key]
        u = unit.get(i['unit'], i['unit']) or ''
        out.append(f'<li>{icon(ic)}<span class="k">{label}</span><span class="v"><b>{esc(i["text"])}</b> {esc(u)}</span>'
                   f'<span class="s">{esc(sub)}</span></li>')
    out.append(f'<li class="warn"><a href="{prefix}engineering/#problems">{icon("alert")}<span class="k">Open problems</span>'
               f'<span class="v"><b>{adv["problems"]}</b></span><span class="s">where the design still fails</span></a></li>')
    rows = ''.join(f'<tr><th scope="row">{esc(it[k]["label"])}</th><td class="v">{esc(it[k]["text"])} {esc(it[k]["unit"] or "")}</td>'
                   f'<td>{_chip(it[k]["class"])} {_status(it[k]["canon_status"])}</td><td><code class="src">{esc(it[k]["source_ref"])}</code></td></tr>'
                   for k, *_ in tiles + [('ring_rpm',)])
    return (f'<ul class="wos-facts">{"".join(out)}</ul>'
            f'<details class="wos-facts-src"><summary>Status and sources</summary><div class="scroll wos-table" tabindex="0"><table>'
            f'<thead><tr><th scope="col">Item</th><th scope="col">Value</th><th scope="col">Class · status</th><th scope="col">Source</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div><p class="note">{_chip("SPEC")} specification and {_chip("NOM")} nominal values come from the '
            f'design parameters; nothing here is live telemetry. <a href="{prefix}status/#ship-state">Full ship state</a></p></details>')


def sims_cards(prefix):
    """The simulations as pictured cards (Simulations module home)."""
    cards = ''.join(f'<li><a class="wos-card" href="{prefix}{x["href"]}">{thumb(prefix, x["thumb"])}<span class="wos-card-b">'
                    f'<strong>{icon(x["icon"])}{esc(x["title"])}</strong><span class="l">{esc(x["line"])}</span>'
                    f'<span class="act">Open {icon("arrow")}</span><span class="meta">{esc(x["meta"])}</span></span></a></li>' for x in SIMS)
    return f'<ul class="wos-cards">{cards}</ul>'


def bar(prefix, module, st, local=False, sub=None):
    """The ship line (vessel mark, modules, ship state, help) and the module's section row."""
    it = st['items']
    nav = []
    for m in MODULES:
        cur = ' aria-current="page"' if module and m['id'] == module['id'] else ''
        alias = f' data-wos-alias="{m["alias"]}"' if m.get('alias') else ''
        nav.append(f'<a href="{prefix}{m["href"]}" data-wos-key="{m["key"]}"{alias}{cur}>{icon(m["icon"])}<span>{m["label"]}</span></a>')
    chips = (f'<span class="wos-chip" title="Reference configuration: coasting, drive off"><b>{esc(st["reference_configuration"])}</b></span>'
             f'<span class="wos-chip w1">Rings {esc(it["ring_rpm"]["text"])} rpm · {esc(it["spin_gravity"]["text"])} g</span>'
             f'<span class="wos-chip w2">Cabin {esc(it["cabin_pressure"]["text"])} kPa</span>'
             f'<span class="wos-chip adv" title="Advisories: open engineering problems and HOLD items">{icon("alert")}{st["advisories"]["total"]}</span>')
    # A page that shows the full state itself (Status) links to it instead of repeating it in the sheet.
    detail = (f'<p class="wos-sheet-h">The ship state and the advisories are on this page.</p>') if local else (
        f'<p class="wos-sheet-h">Ship state: the design values the model is built in, not live telemetry. '
        f'<a href="{prefix}status/">Status</a></p>{state_table(st, caption=False)}<p class="wos-sheet-h">Advisories</p>{advisories_list(st, prefix)}')
    keys = ' · '.join(f'<kbd>g</kbd> <kbd>{m["key"]}</kbd> {m["label"]}' for m in MODULES)
    station = esc((module or MODULES[0])['station'])
    help_sheet = (f'<div class="wos-sheet wos-help" role="group" aria-label="Help and system">'
                  f'<p><b>G.U. WAYFARER 001</b> is a fictional spacecraft, designed with real physics. Everything here is a simulation '
                  f'of an evolving design. <a href="{prefix}#about">About this project</a></p>'
                  f'<p class="wos-sheet-h">Keys</p><p>{keys} · <kbd>\\</kbd> focus mode · <kbd>Esc</kbd> close</p>'
                  f'<p><button type="button" class="secondary" data-wos-reset-guides>Show the guidance again</button></p>'
                  f'<p class="muted small">Station: {station} on a wide screen, Personal Terminal on a phone (device names '
                  f'<span class="st st-PROTOTYPE">PROTOTYPE</span>). <span data-wos-profile></span></p>'
                  f'<p><a href="{prefix}status/#system">System and release</a> · <a href="https://github.com/densho-media/ignition-wayfarer" '
                  f'rel="noopener">Source</a> · <a href="https://densho.media" rel="noopener">Densho</a></p></div>')
    subnav = ''
    if module and module.get('sub'):
        tabs = []
        for t in module['sub']:
            cur = ' aria-current="page"' if sub is t else ''
            ic = icon(t['icon']) if t.get('icon') else ''
            tabs.append(f'<a href="{prefix}{t["href"]}"{cur}>{ic}<span>{esc(t["label"])}</span></a>')
        # The row scrolls sideways when it does not fit; wos.js shows the arrow buttons and edge fades only while more tabs lie that way.
        more = lambda side: (f'<button type="button" class="wos-sub-more" data-side="{side}" hidden tabindex="-1" '
                                f'aria-label="More {module["label"]} sections">{icon("arrow")}</button>')
        subnav = (f'<div class="wos-subw">{more("l")}<nav class="wos-sub" aria-label="{module["label"]} sections">{"".join(tabs)}</nav>'
                  f'{more("r")}</div>')
    return (f'<a class="wos-skip" href="#wos-work">Skip to the workspace</a>'
            f'<header class="wos-bar" id="wos-bar">'
            f'<a class="mark" href="{prefix}" title="G.U. WAYFARER 001 · Overview"><span class="wos-logo" aria-hidden="true"></span>'
            f'<span class="wos-vessel">G.U. WAYFARER 001</span></a>'
            f'<nav class="wos-nav" aria-label="Modules">{"".join(nav)}</nav>'
            f'<span class="wos-scn" role="status" hidden></span>'
            f'<details class="wos-state"><summary aria-label="Ship state and advisories" title="Ship state and advisories">{chips}</summary>'
            f'<div class="wos-sheet" role="group" aria-label="Ship state">{detail}</div></details>'
            f'<details class="wos-util"><summary aria-label="Help and system" title="Help and system">{icon("help")}</summary>{help_sheet}</details>'
            f'</header>{subnav}')


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
        sub = sub_for(module, rel)
        local = '<!--wos:state-->' in text
        out = MARK.sub(lambda m: {'bar': lambda: bar(prefix, module, st, local, sub), 'state': lambda: state_table(st),
                                  'advisories': lambda: advisories_list(st, prefix), 'facts': lambda: facts(st, prefix),
                                  'sims': lambda: sims_cards(prefix), 'thumb': lambda: _thumb_mark(prefix, m.group(2))}[m.group(1)](), text)
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
