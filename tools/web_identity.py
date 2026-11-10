"""Wayfarer website identity (WEB-005): the one source of the site's design tokens, its engineering colours and its lunar background.

Four colour layers, kept apart (docs/WEB_IDENTITY.md):
  1. UI identity     the First Ignition palette and the tokens derived from it (IDENTITY below): surfaces, text, actions, focus.
  2. Function        the engineering function colours of src/wayfarer/functional_colors.py PALETTE (the Blender review colours), shown on
                     the site as the sRGB encoding of their scene-linear values, so a page shows the hue the Blender viewport shows.
                     The M5 subsystem overlay colours (shots/m5_subsystems.toml, already sRGB: the viewer sets them with SRGBColorSpace)
                     are carried as --sub-<id> for legends that speak about the viewer's subsystem holograms.
  3. Material        PMDS appearance base colours (data/materials/appearances.toml, linear) for material swatches; a material with no
                     appearance of its own shows its parent's, marked as inherited, or none.
  4. Status          state chips (good, info, warn, bad): never a function or identity colour.

`python3 tools/web_identity.py` rewrites the generated block between the <wf-identity> markers of web/site.css and web/viewer/viewer.css;
`--check` only reports whether they are current (web_export.verify_site runs it, so a stale block fails the site build). The background
art is drawn here, deterministically, as compact SVG data URIs inside site.css: the start page still loads only index.html, site.css and
release.json. Presentation only: nothing here feeds a calculation, a material or the geometry.
"""
import argparse
import math
import random
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
from functional_colors import PALETTE  # noqa: E402

BEGIN, END = '/* <wf-identity>', '/* </wf-identity> */'

# 1. UI identity. The five First Ignition colours, then the tokens derived from them (contrast ratios against --surface-1 #121A24 in
# docs/WEB_IDENTITY.md). Pure accents are used for small marks and rules, never as large fills.
IDENTITY = [
    ('wf-charcoal', '#1B2633', 'deep spacecraft charcoal'),
    ('wf-ignition', '#D8EAFF', 'blue-white ignition'),
    ('wf-plasma', '#D99AC9', 'deuterium plasma pink'),
    ('wf-violet', '#8C83C5', 'plasma violet'),
    ('wf-radiator', '#FF843C', 'radiator orange'),
    ('bg', '#0A0F15', 'page: deep space, charcoal at 40 % lightness'),
    ('surface-0', 'rgba(12, 18, 25, 0.88)', 'reading sheet over the scene'),
    ('surface-1', '#121A24', 'panel'),
    ('surface-2', '#1B2633', 'raised card, hover: the charcoal itself'),
    ('surface-3', '#243246', 'selected'),
    ('line', '#2A3747', 'hairline'),
    ('line-strong', '#3B4B60', 'card edge, control edge'),
    ('ink', '#DCE5EF', 'body text 13.8:1'),
    ('ink-strong', '#D8EAFF', 'titles: ignition'),
    ('muted', '#9AA9BA', 'secondary text 7.3:1'),
    ('accent', '#D99AC9', 'eyebrows, rules, the identity mark'),
    ('accent-2', '#8C83C5', 'secondary identity mark'),
    ('link', '#E7B9DA', 'links 10.1:1'),
    ('action', '#FF843C', 'primary action fill (charcoal text on it 6.3:1)'),
    ('action-hover', '#FF9B5E', ''),
    ('action-ink', '#1B2633', ''),
    ('focus', '#D8EAFF', 'focus ring'),
    ('selected', '#D99AC9', 'selected control edge and text'),
    ('good', '#7FD39B', 'status: holds, closes, locked'),
    ('info', '#8FC1F0', 'status: working, calculated'),
    ('warn', '#E9B85A', 'status: prototype, assumed, conditional'),
    ('bad', '#FF7F73', 'status: open, fails, error'),
]
VIEWER_KEYS = ('wf-charcoal', 'wf-ignition', 'wf-plasma', 'wf-violet', 'wf-radiator', 'bg', 'surface-1', 'surface-2', 'line', 'line-strong',
               'ink', 'ink-strong', 'muted', 'accent', 'link', 'action', 'action-ink', 'focus', 'selected', 'good', 'info', 'warn', 'bad')

# 2. Function: short site labels for the functional_colors keys (the registry's own label stays the long name and the title).
SHORT = {'STRUCTURE': 'Structure', 'SHIELD': 'Shielding', 'SENSORS_COMMS': 'EYE and sensors', 'HABITAT': 'Habitat and crew',
         'HYDROGEN': 'Hydrogen', 'DEUTERIUM': 'Deuterium', 'HELIUM3': 'Helium-3', 'HOT_RADIATOR': 'Hot radiators',
         'WARM_RADIATOR': 'Warm radiators', 'LOW_RADIATOR': 'Low-temperature radiators', 'MAIN_PROPULSION': 'Fusion propulsion',
         'RCS': 'Manoeuvring', 'POWER': 'Electrical power', 'SERVICE': 'Docking and service'}
# A topic about the whole ship (mass loop, mission, layout) has no single function: it takes the identity mark, labelled as such.
WHOLE_SHIP = ('SHIP', 'Whole ship', '#D8EAFF')

# Engineering topics -> function key: the subsystem each lab entry, problem, weakest link and breakthrough is mainly about (presentation;
# the research records are unchanged). WL-008 and P05 are radiation shielding, which the Blender registry folds into MAIN_PROPULSION
# (the shadow shield) and SHIELD (the forward dust shield); the site files them under SHIELD, the protection family (owner question in
# docs/WEB_IDENTITY.md).
TOPICS = {
    'fdp1-requirements': 'MAIN_PROPULSION', 'breakthrough-lab': 'SHIP', 'four-burn-mission': 'SHIP',
    'graded-thermal-blade': 'WARM_RADIATOR', 'fdp1': 'MAIN_PROPULSION', 'fiji-drive': 'MAIN_PROPULSION', 'redesign-layout': 'SHIP',
    'P01': 'MAIN_PROPULSION', 'P02': 'POWER', 'P03': 'MAIN_PROPULSION', 'P04': 'MAIN_PROPULSION', 'P05': 'SHIELD', 'P06': 'WARM_RADIATOR',
    'P07': 'HOT_RADIATOR', 'P08': 'HYDROGEN', 'P09': 'STRUCTURE', 'P10': 'SHIP', 'P11': 'SHIELD',
    'WL-001': 'MAIN_PROPULSION', 'WL-002': 'MAIN_PROPULSION', 'WL-003': 'SHIP', 'WL-004': 'MAIN_PROPULSION', 'WL-005': 'HOT_RADIATOR',
    'WL-006': 'STRUCTURE', 'WL-007': 'MAIN_PROPULSION', 'WL-008': 'SHIELD', 'WL-009': 'MAIN_PROPULSION',
    'BT-001': 'MAIN_PROPULSION', 'BT-002': 'STRUCTURE', 'BT-003': 'MAIN_PROPULSION', 'BT-004': 'HOT_RADIATOR', 'BT-005': 'MAIN_PROPULSION',
    'BT-006': 'POWER', 'BT-007': 'STRUCTURE',
}


def srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hexcolor(rgb, linear=True):
    return '#' + ''.join(f'{round((srgb(v) if linear else max(0.0, min(1.0, v))) * 255):02X}' for v in rgb[:3])


def function_colors():
    """key -> (short label, registry label, sRGB hex)."""
    return {k: (SHORT[k], label, hexcolor(rgba)) for k, (label, rgba, _) in PALETTE.items()}


def subsystem_colors():
    subs = tomllib.loads((ROOT / 'shots/m5_subsystems.toml').read_text())['subsystem']
    return [(s['id'], s['name'], hexcolor(s['color'], linear=False)) for s in subs]


def topic(key):
    """(css class, short label, long label) of an engineering topic id; None if the topic is not mapped."""
    fn = TOPICS.get(key)
    if fn is None:
        return None
    if fn == 'SHIP':
        return 'fn-SHIP', WHOLE_SHIP[1], 'Whole-ship topic: no single subsystem'
    short, label, _ = function_colors()[fn]
    return f'fn-{fn}', short, label


def topic_chip(key):
    t = topic(key)
    return f'<span class="fnchip {t[0]}" title="{t[2]}"><i aria-hidden="true"></i>{t[1]}</span>' if t else ''


# 3. Material: PMDS appearance swatches.
_MATERIALS = None


def materials():
    global _MATERIALS
    if _MATERIALS is None:
        cat = tomllib.loads((ROOT / 'data/materials/catalogue.toml').read_text())['material']
        app = tomllib.loads((ROOT / 'data/materials/appearances.toml').read_text())['appearance']
        first = {}
        for aid, a in app.items():
            first.setdefault(a['material'], (aid, a))
        _MATERIALS = (cat, first)
    return _MATERIALS


def material_chip(mid):
    """A material code with its PMDS swatch: its own first appearance, else its parent's (marked inherited), else a neutral 'none'."""
    cat, first = materials()
    m = cat.get(mid)
    if m is None:
        return f'<code>{mid}</code>'
    own, src = first.get(mid), mid
    if own is None and m.get('parent') in first:
        own, src = first[m['parent']], m['parent']
    name = m['name'].replace('"', '&quot;')
    if own is None:
        sw, note = '<i class="sw none" aria-hidden="true"></i>', 'no PMDS appearance recorded'
    else:
        aid, a = own
        cls = 'sw metal' if a.get('metallic', 0) >= 0.5 else 'sw'
        sw = f'<i class="{cls}" style="--mat:{hexcolor(a["base_color"])}" aria-hidden="true"></i>'
        note = f'appearance {aid}' + (f', inherited from {src}' if src != mid else '')
    return (f'<span class="mat" title="{name} · level {m.get("level", "?")} · {note}">{sw}<code>{mid}</code>'
            f'<span class="lvl">{m.get("level", "?")}</span></span>')


# ---------------------------------------------------------------------------------------------------------------- background art
def _svg_uri(svg):
    svg = re.sub(r'\s+', ' ', svg).replace('> <', '><').strip()
    return 'url("data:image/svg+xml,' + quote(svg, safe=" =:/;,'()-.") + '")'


def _f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def stars_svg(size, count, seed):
    """A tile of sparse stars: most faint and blue-white, a few warm, a handful brighter. No twinkle."""
    rnd = random.Random(seed)
    dots = []
    for _ in range(count):
        x, y = rnd.uniform(0, size), rnd.uniform(0, size)
        b = rnd.random() ** 2.4
        r = 0.45 + 0.9 * b
        o = 0.16 + 0.56 * b
        col = '#FFE7CF' if rnd.random() < 0.18 else '#D8EAFF'
        dots.append(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{r:.2f}" fill="{col}" fill-opacity="{o:.2f}"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">{"".join(dots)}</svg>'


def earth_svg():
    """Earth from lunar distance: gibbous, lit from the left like the lunar terrain (the Sun is off-screen upper left), with a thin
    bright limb on the day side only, a few soft cloud bands and a dark night side with sparse city lights."""
    rnd = random.Random(7)
    clouds = ''.join(f'<ellipse cx="{_f(rnd.uniform(14, 60))}" cy="{_f(rnd.uniform(12, 88))}" rx="{_f(rnd.uniform(5, 16))}" '
                     f'ry="{_f(rnd.uniform(0.8, 2.0))}" transform="rotate({_f(rnd.uniform(-25, 25))} 50 50)"/>' for _ in range(14))
    cities = ''.join(f'<circle cx="{_f(rnd.uniform(70, 88))}" cy="{_f(rnd.uniform(30, 72))}" r="0.45"/>' for _ in range(7))
    lit = 'M50 4 A46 46 0 0 0 50 96 A22 46 0 0 0 50 4 Z'      # left half disc + half ellipse: about 66 % lit
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 100 100">
<defs>
<radialGradient id="o" cx="0.32" cy="0.42" r="0.7"><stop offset="0" stop-color="#4C86C4"/><stop offset="0.55" stop-color="#24517F"/><stop offset="1" stop-color="#112B47"/></radialGradient>
<linearGradient id="t" x1="0" x2="1"><stop offset="0.36" stop-color="#070B11" stop-opacity="0"/><stop offset="0.6" stop-color="#070B11" stop-opacity="0.72"/><stop offset="0.72" stop-color="#070B11"/></linearGradient>
<clipPath id="d"><path d="{lit}"/></clipPath>
<filter id="b" x="-0.2" y="-0.2" width="1.4" height="1.4"><feGaussianBlur stdDeviation="1.5"/></filter>
<filter id="g" x="-0.2" y="-0.2" width="1.4" height="1.4"><feGaussianBlur stdDeviation="0.8"/></filter>
</defs>
<circle cx="50" cy="50" r="46" fill="#070B11"/>
<g fill="#FFB070" fill-opacity="0.55">{cities}</g>
<g clip-path="url(#d)"><rect width="100" height="100" fill="url(#o)"/>
<path d="M18 30 C26 22 38 26 36 38 C34 48 24 50 22 60 C20 70 12 64 12 52 Z M34 62 C40 58 46 66 42 76 C38 82 32 76 34 62 Z" fill="#6B7552" fill-opacity="0.3"/>
<g fill="#F4F8FF" fill-opacity="0.34" filter="url(#b)">{clouds}</g>
<rect width="100" height="100" fill="url(#t)"/></g>
<path d="M50 4 A46 46 0 0 0 50 96" fill="none" stroke="#9CC9FF" stroke-width="1.6" stroke-opacity="0.7" filter="url(#g)"/>
</svg>'''


def moon_svg():
    """The lunar horizon from low orbit, 3200 x 360 so any viewport sees an unbroken horizon at a fixed height: regolith lit from the
    upper left, a soft terminator right of centre, foreshortened craters whose sunward inner walls are in shadow, and on the night side a
    faint cluster of station lights. No atmosphere, no glow halo."""
    rnd = random.Random(11)
    W, H, top = 3200, 360, 70.0
    k = 32 / (1600 - 753) ** 2

    def y(x):
        return top + k * (x - 1600) ** 2

    pts = []
    x = 0
    while x <= W:
        bump = 1.6 * math.sin(x / 37) + 1.1 * math.sin(x / 11.3 + 1.7) + (5.5 * math.exp(-((x - 1180) / 60) ** 2)) + (3 * math.exp(-((x - 2060) / 40) ** 2))
        pts.append(f'{x} {_f(y(x) - bump)}')
        x += 16
    horizon = 'L'.join(pts)
    craters = []
    for _ in range(46):
        cx = rnd.uniform(700, 2300)
        cyy = rnd.uniform(y(cx) + 10, H - 6)
        depth = (cyy - y(cx)) / (H - y(cx))            # 0 at the horizon, 1 at the bottom: nearer craters look larger and rounder
        rx = rnd.uniform(6, 18) + 70 * depth ** 1.6 * rnd.random()
        ry = rx * (0.16 + 0.22 * depth)
        lit = max(0.0, min(1.0, (2050 - cx) / 600))      # fades out across the terminator
        if lit < 0.08:
            continue
        craters.append(f'<ellipse cx="{_f(cx)}" cy="{_f(cyy)}" rx="{_f(rx)}" ry="{_f(ry)}" opacity="{lit:.2f}"/>')
    maria = ''.join(f'<ellipse cx="{a}" cy="{b}" rx="{c}" ry="{d}"/>' for a, b, c, d in
                    ((1040, 210, 260, 26), (1430, 290, 330, 40), (1810, 175, 180, 16)))
    lights = []
    for i in range(11):
        lx = 2120 + 28 * i + rnd.uniform(-9, 9)
        ly = y(lx) + rnd.uniform(5, 22)
        lights.append(f'<circle cx="{_f(lx)}" cy="{_f(ly)}" r="{rnd.uniform(0.9, 1.7):.2f}"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax meet">
<defs>
<linearGradient id="s" x1="0" x2="{W}" gradientUnits="userSpaceOnUse"><stop offset="0.22" stop-color="#2C2B29"/><stop offset="0.4" stop-color="#3E3C39"/>
<stop offset="0.5" stop-color="#3A3835"/><stop offset="0.6" stop-color="#26262A"/><stop offset="0.66" stop-color="#121418"/><stop offset="1" stop-color="#0C0F13"/></linearGradient>
<linearGradient id="v" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#05080C" stop-opacity="0.55"/></linearGradient>
<linearGradient id="l" x1="0" x2="{W}" gradientUnits="userSpaceOnUse"><stop offset="0.25" stop-color="#B8B3A8" stop-opacity="0.15"/>
<stop offset="0.45" stop-color="#C9C3B6" stop-opacity="0.55"/><stop offset="0.6" stop-color="#C9C3B6" stop-opacity="0.12"/><stop offset="0.66" stop-color="#C9C3B6" stop-opacity="0"/></linearGradient>
<linearGradient id="cf" x1="0" x2="1"><stop offset="0" stop-color="#17171A" stop-opacity="0.7"/><stop offset="0.7" stop-color="#2A2927" stop-opacity="0.35"/><stop offset="1" stop-color="#5D5A54" stop-opacity="0.55"/></linearGradient>
<radialGradient id="e" cx="2350" cy="80" r="520" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#6E9BD6" stop-opacity="0.07"/><stop offset="1" stop-color="#6E9BD6" stop-opacity="0"/></radialGradient>
<filter id="gl" x="-2" y="-2" width="5" height="5"><feGaussianBlur stdDeviation="2.2"/></filter>
</defs>
<path d="M0 {H}L{horizon}L{W} {H}Z" fill="url(#s)"/>
<g fill="#151517" fill-opacity="0.28">{maria}</g>
<g fill="url(#cf)">{"".join(craters)}</g>
<path d="M0 {H}L{horizon}L{W} {H}Z" fill="url(#e)"/>
<path d="M0 {H}L{horizon}L{W} {H}Z" fill="url(#v)"/>
<path d="M{horizon}" fill="none" stroke="url(#l)" stroke-width="1.2"/>
<g fill="#FFB27A" fill-opacity="0.35" filter="url(#gl)">{"".join(lights)}</g>
<g fill="#FFC79A" fill-opacity="0.9">{"".join(lights)}</g>
<circle cx="2268" cy="{_f(y(2268) + 9)}" r="1.1" fill="#D8EAFF"/>
</svg>'''


# ---------------------------------------------------------------------------------------------------------------- generated blocks
def site_block():
    lines = [f'{BEGIN} generated by tools/web_identity.py from functional_colors.py, m5_subsystems.toml and the PMDS appearances;',
             '   edit the generator, not this block (python3 tools/web_identity.py). */', ':root {']
    for name, value, note in IDENTITY:
        lines.append(f'  --{name}: {value};' + (f'  /* {note} */' if note else ''))
    lines.append('  /* engineering functions: sRGB of the Blender scene-linear review colours (functional_colors.PALETTE) */')
    for k, (short, label, hx) in function_colors().items():
        lines.append(f'  --fn-{k}: {hx};  /* {label} */')
    lines.append(f'  --fn-SHIP: var(--wf-ignition);  /* {WHOLE_SHIP[1]}: identity mark, no subsystem */')
    lines.append('  /* M5 subsystem overlay colours of the viewer holograms (shots/m5_subsystems.toml, sRGB) */')
    for sid, name, hx in subsystem_colors():
        lines.append(f'  --sub-{sid}: {hx};  /* {name} */')
    lines.append('  /* the lunar scene (drawn by this generator) */')
    lines.append(f'  --scene-stars-a: {_svg_uri(stars_svg(397, 24, 3))};')
    lines.append(f'  --scene-stars-b: {_svg_uri(stars_svg(653, 40, 5))};')
    lines.append(f'  --scene-earth: {_svg_uri(earth_svg())};')
    lines.append(f'  --scene-moon: {_svg_uri(moon_svg())};')
    lines.append('}')
    lines.append(' '.join(f'.fn-{k} {{ --fn: var(--fn-{k}); }}' for k in [*PALETTE, 'SHIP']))
    lines.append(END)
    return '\n'.join(lines)


def viewer_block():
    lines = [f'{BEGIN} generated by tools/web_identity.py: the site identity tokens the viewer uses; do not edit by hand. */', ':root {']
    for name, value, note in IDENTITY:
        if name in VIEWER_KEYS:
            lines.append(f'  --{name}: {value};')
    lines.append('}')
    lines.append(END)
    return '\n'.join(lines)


TARGETS = {'web/site.css': site_block, 'web/viewer/viewer.css': viewer_block}


def apply(text, block):
    pattern = re.compile(re.escape(BEGIN) + r'.*?' + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError('no <wf-identity> block')
    return pattern.sub(lambda _: block, text, count=1)


def stale(root=ROOT):
    """The target files whose generated block differs from the generator's output."""
    return [rel for rel, make in TARGETS.items() if apply((root / rel).read_text(), make()) != (root / rel).read_text()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='report stale blocks; change nothing')
    args = ap.parse_args()
    if args.check:
        bad = stale()
        print('identity blocks: ' + ('STALE ' + ', '.join(bad) if bad else 'current'))
        return 1 if bad else 0
    for rel, make in TARGETS.items():
        p = ROOT / rel
        new = apply(p.read_text(), make())
        if new != p.read_text():
            p.write_text(new)
            print('wrote', rel)
    return 0


if __name__ == '__main__':
    sys.exit(main())
