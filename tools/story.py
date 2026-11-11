"""Wayfarer website, Engineering section: the engineering story for outside engineers, generated from the repository.

Writes <site>/engineering/:
  index.html                  the story: the goal, the constraints, the ship today, what we tried, the open problems, how to follow
  <kind>/<name>/index.html    one page per lab/ entry (variant, study, problem map): its header, summary, figures and working notes
  <kind>/<name>/fig/          the entry's committed figures (SVG, or PNG where no SVG of the same name exists)
  compare/                    per open problem, today's ship beside what the problem needs, in 3D at one scale: compare.json from the
                              problem map's `site.py --compare`, drawn by web/engineering/compare.js over the Explore Ship model
  build/                      the assembly sequence: the approved ship put together step by step, from the spine to first ignition,
                              from the assembly-sequence study's `site.py --json`, drawn by web/engineering/build.js over the Explore Ship model
  baseline/ weakest-links/    Engineering 2.0 (tools/story_lab.py): the scientific reference, the ranked bottlenecks, the Breakthrough
  breakthrough-lab/           Lab over the precomputed scenario grid and true-scale envelopes, from the Breakthrough Lab study's
  evolution/                  `site.py --json` (lab/studies/breakthrough-lab), which validates its registries and stops the build on error

Every number comes from the inputs at build time: data/wayfarer_3d.toml through the pure modules (spec, operating_point,
first_ignition), the lab entries' NOTES.md, REPORT.md and result JSON, and a problem map's own `site.py --json` and `--compare` (run as a separate
process, so lab code never runs inside the site build). The text around the numbers is written here. This is the one place outside
lab/ that reads lab/ (AGENTS.md "Where things go"); it reads, never writes, and nothing in the model build depends on it.

    python3 tools/story.py --out runs/story          # the Engineering pages alone, no Blender or assets needed
    python3 tools/workflow.py web ...                # the whole site; calls build() after copying web/
"""
import argparse
import html
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import web_identity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))

REPO = 'https://github.com/densho-media/ignition-wayfarer'
FIGURE_LIMIT = 1_500_000          # a committed figure larger than this is linked, not copied
KINDS = {'variants': 'Variant', 'studies': 'Study', 'problems': 'Problem map'}
C = 299792458.0
G0 = 9.80665


# ---------------------------------------------------------------------------------------------------------------- markdown
INLINE = [
    (re.compile(r'`([^`]+)`'), lambda m: f'<code>{m.group(1)}</code>'),
    (re.compile(r'\*\*(.+?)\*\*'), lambda m: f'<strong>{m.group(1)}</strong>'),
    (re.compile(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])'), lambda m: f'<em>{m.group(1)}</em>'),
]
LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')


class Markdown:
    """The Markdown the repository's notes use: headings, paragraphs, nested lists, tables, fences, code, bold, italics, links.
    A relative link is resolved against the source file and points at that file on GitHub at the built commit."""

    def __init__(self, revision, base, shift=1):
        self.revision, self.base, self.shift = revision, base, shift

    def link(self, target):
        if re.match(r'^[a-z]+:', target) or target.startswith('#'):
            return target
        path, _, frag = target.partition('#')
        resolved = (self.base / path).resolve()
        try:
            rel = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return '#'
        kind = 'tree' if resolved.is_dir() else 'blob'
        return f'{REPO}/{kind}/{self.revision}/{rel}' + (f'#{frag}' if frag else '')

    def inline(self, text):
        out, last = [], 0
        for m in LINK.finditer(text):
            out.append(self._span(text[last:m.start()]))
            out.append(f'<a href="{html.escape(self.link(m.group(2)))}" rel="noopener">{self._span(m.group(1))}</a>')
            last = m.end()
        out.append(self._span(text[last:]))
        return ''.join(out)

    @staticmethod
    def _span(text):
        parts = re.split(r'(`[^`]+`)', text)
        out = []
        for part in parts:
            if part.startswith('`') and part.endswith('`') and len(part) > 1:
                out.append(f'<code>{html.escape(part[1:-1])}</code>')
                continue
            s = html.escape(part, quote=False)
            for rx, fn in INLINE[1:]:
                s = rx.sub(fn, s)
            out.append(s)
        return ''.join(out)

    def render(self, text):
        text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
        lines = text.split('\n')
        out, i = [], 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            if line.startswith('```'):
                j = i + 1
                while j < len(lines) and not lines[j].startswith('```'):
                    j += 1
                out.append('<pre><code>' + html.escape('\n'.join(lines[i + 1:j])) + '</code></pre>')
                i = j + 1
                continue
            m = re.match(r'^(#{1,6})\s+(.*)', line)
            if m:
                level = min(6, len(m.group(1)) + self.shift)
                out.append(f'<h{level}>{self.inline(m.group(2).strip())}</h{level}>')
                i += 1
                continue
            if line.lstrip().startswith('|'):
                j = i
                while j < len(lines) and lines[j].lstrip().startswith('|'):
                    j += 1
                out.append(self.table(lines[i:j]))
                i = j
                continue
            if re.match(r'^\s*([-*]|\d+\.)\s+', line):
                j = i
                while j < len(lines) and (re.match(r'^\s*([-*]|\d+\.)\s+', lines[j]) or (lines[j].startswith('  ') and lines[j].strip())):
                    j += 1
                out.append(self.list(lines[i:j]))
                i = j
                continue
            j = i
            while j < len(lines) and lines[j].strip() and not re.match(r'^(#{1,6}\s|```|\s*\||\s*([-*]|\d+\.)\s)', lines[j]):
                j += 1
            j = max(j, i + 1)
            out.append('<p>' + self.inline(' '.join(x.strip() for x in lines[i:j])) + '</p>')
            i = j
        return '\n'.join(out)

    def table(self, rows):
        cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
        if len(cells) > 1 and all(re.match(r'^:?-{2,}:?$', c) for c in cells[1] if c):
            head, body = cells[0], cells[2:]
        else:
            head, body = None, cells
        out = ['<div class="scroll" tabindex="0"><table>']
        if head and any(head):
            out.append('<thead><tr>' + ''.join(f'<th>{self.inline(c)}</th>' for c in head) + '</tr></thead>')
        out.append('<tbody>' + ''.join('<tr>' + ''.join(f'<td>{self.inline(c)}</td>' for c in r) + '</tr>' for r in body) + '</tbody>')
        return ''.join(out) + '</table></div>'

    def list(self, lines):
        items = []                      # (indent, ordered, text)
        for line in lines:
            m = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)', line)
            if m:
                items.append([len(m.group(1)), m.group(2)[0].isdigit(), m.group(3)])
            elif items:
                items[-1][2] += ' ' + line.strip()
        out, stack = [], []
        for indent, ordered, text in items:
            while stack and indent < stack[-1][0]:
                out.append('</li></%s>' % stack.pop()[1])
            if not stack or indent > stack[-1][0]:
                tag = 'ol' if ordered else 'ul'
                stack.append((indent, tag))
                out.append(f'<{tag}><li>')
            else:
                out.append('</li><li>')
            out.append(self.inline(text))
        while stack:
            out.append('</li></%s>' % stack.pop()[1])
        return ''.join(out)


def sections(text):
    """Split Markdown into (heading, body) by its level-2 headings; the text before the first one has heading None."""
    parts, head, buf = [], None, []
    for line in text.split('\n'):
        m = re.match(r'^##\s+(.*)', line)
        if m:
            parts.append((head, '\n'.join(buf)))
            head, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    parts.append((head, '\n'.join(buf)))
    return parts


# ---------------------------------------------------------------------------------------------------------------- inputs
def git(*args):
    try:
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ''


def lab_entries():
    """The lab/README.md index rows, with each entry's NOTES.md header table."""
    index = (ROOT / 'lab/README.md').read_text()
    entries, dropped = [], []
    part = None
    for line in index.split('\n'):
        if line.startswith('## '):
            part = line[3:].strip()
        if not line.startswith('|') or re.match(r'^\|\s*-', line):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if part == 'Entries' and cells[0] != 'Entry':
            m = LINK.match(cells[0])
            if not m:
                continue
            folder = (ROOT / 'lab' / m.group(2)).parent
            entries.append({'name': m.group(1), 'folder': folder, 'kind_dir': folder.parent.name, 'kind': cells[1], 'status': cells[2],
                            'question': cells[3], 'base': cells[4], 'owner_question': cells[5], 'header': notes_header(folder / 'NOTES.md')})
        elif part == 'Dropped' and cells[0] != 'Work':
            dropped.append(cells)
    return entries, dropped


def notes_header(path):
    text = path.read_text()
    rows = {}
    for line in text.split('\n')[:20]:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if line.startswith('|') and len(cells) == 2 and cells[0] not in ('Lab entry', '---') and not cells[0].startswith('-'):
            rows[cells[0]] = cells[1]
    return rows


def notes_body(path):
    """NOTES.md without the header table."""
    text = re.sub(r'<!--.*?-->', '', path.read_text(), flags=re.S).lstrip()
    lines = text.split('\n')
    i = 0
    while i < len(lines) and (lines[i].startswith('|') or not lines[i].strip()):
        i += 1
    return '\n'.join(lines[i:])


def figures(folder):
    """Committed figures of an entry: SVG first, PNG where no SVG of the same stem exists; small enough to copy."""
    found = {}
    for p in sorted(folder.rglob('*')):
        if p.suffix.lower() not in ('.svg', '.png') or not p.is_file():
            continue
        key = p.with_suffix('').relative_to(folder).as_posix()
        if key in found and found[key].suffix == '.svg':
            continue
        found[key] = p
    return [p for p in found.values() if p.stat().st_size <= FIGURE_LIMIT]


def open_in_canon(spec):
    """Every `known = false` entry of the parameters, by top-level area."""
    out = {}

    def walk(node, path):
        if isinstance(node, dict):
            if node.get('known') is False:
                out.setdefault(path.split('.')[0], []).append((path, node.get('canon_status', ''), node.get('reason') or node.get('note') or ''))
            for k, v in node.items():
                walk(v, f'{path}.{k}' if path else k)
    walk(spec, '')
    return out


def status_counts(spec):
    counts = {}

    def walk(node):
        if isinstance(node, dict):
            st = node.get('canon_status')
            if isinstance(st, str):
                counts[st] = counts.get(st, 0) + 1
            for v in node.values():
                walk(v)
    walk(spec)
    return counts


def lab_story(folder, flag='--json'):
    """A lab entry's own site data (site.py --json, or --compare for the 3D comparison), run as its own process with the entry
    folder first on its path."""
    script = folder / 'site.py'
    if not script.exists():
        return None
    run = subprocess.run([sys.executable, '-I', str(script), flag], cwd=ROOT, capture_output=True, text=True, timeout=300)
    if run.returncode:
        raise RuntimeError(f'{script.relative_to(ROOT)} failed: {run.stderr[-800:]}')
    return json.loads(run.stdout)


def ship_numbers(spec):
    import first_ignition
    import operating_point
    op = operating_point.report(spec)
    fi = first_ignition.result(spec)
    h = spec['habitat']
    omega = h['rpm'] * 2 * math.pi / 60
    floor = h['floor_radius']['value']
    burn = op['operating_point']
    mission = op['mission']
    return {'op': op, 'fi': fi, 'burn': burn, 'mission': mission, 'spin_g': omega ** 2 * floor / G0, 'floor_r': floor,
            'dv_m_s': burn['delta_v_m_s'], 've_m_s': burn['exhaust_velocity_m_s']}


# ---------------------------------------------------------------------------------------------------------------- formatting
def t(kg):
    return f'{kg / 1000:,.0f} t'


def esc(s):
    return html.escape(str(s), quote=True)


def tag(status):
    s = re.sub(r'[^A-Z_]', '', str(status).split()[0].upper()) if status else ''
    return f'<span class="st st-{s or "NONE"}">{esc(status)}</span>'


def page(title, description, body, depth, revision, built, head=''):
    up = '../' * depth
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%231B2633'/%3E%3Ccircle cx='8' cy='8' r='4.6' fill='%238C83C5'/%3E%3Ccircle cx='8' cy='8' r='3' fill='%23D99AC9'/%3E%3Ccircle cx='8' cy='8' r='1.3' fill='%23D8EAFF'/%3E%3C/svg%3E">
<meta name="theme-color" content="#0A0F15">
<link rel="stylesheet" href="{up}site.css">
<link rel="stylesheet" href="{up}engineering/story.css">{head}
</head>
<body class="scene-quiet">
<main class="wrap story">
<div class="sitebar"><a class="mark" href="{up}">Wayfarer</a>
  <nav aria-label="Site"><a href="{up}engineering/" aria-current="true">Engineering</a><a href="{up}viewer/">Explore Ship</a><a href="{up}status/">Technical status</a></nav></div>
<nav class="crumbs" aria-label="Breadcrumb"><a href="{up}">Wayfarer</a> / <a href="{up}engineering/">Engineering</a></nav>
{body}
<footer>
  <span>Generated from <a href="{REPO}/tree/{revision}" rel="noopener"><code>{revision[:7]}</code></a> · {built}</span>
  <a href="{up}viewer/">Explore Ship</a>
  <a href="{up}status/">Technical status</a>
  <a href="{REPO}" rel="noopener">Source</a>
</footer>
</main>
</body>
</html>
'''


def elevation_svg(p):
    """P11 side elevation (half-section, bow right): every part's radial extent along the ship, classified against the shield
    shadow for the aligned stream. Generated from the problem map's own protection model."""
    el = p['elevation']
    cells = el['cells']
    cx, cr = el['cell_m']
    xs = [c[0] for c in cells]
    x0, x1 = min(xs) - 10, max(max(xs), p['shield_x_m']) + 20
    rmax = el['r_clip_m']
    W, H, L, B, T = 960, 360, 56, 40, 24
    sx = (W - L - 16) / (x1 - x0)
    sy = (H - B - T) / rmax
    X = lambda x: L + (x - x0) * sx
    Y = lambda r: H - B - r * sy
    colour = {'shield': 'var(--accent)', 'part_covered': 'var(--good)', 'part_outside': 'var(--bad)',
              'radiator_covered': '#4f8fbf', 'radiator_outside': '#b07cd8'}
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="elev-t" class="figure-svg">',
           '<title id="elev-t">Side elevation: the forward shield shadow against the FDP-1 hardware</title>',
           f'<rect x="{X(x0):.1f}" y="{Y(p["shield_radius_m"]):.1f}" width="{X(p["shield_x_m"]) - X(x0):.1f}" '
           f'height="{Y(0) - Y(p["shield_radius_m"]):.1f}" fill="var(--good)" opacity="0.07"/>']
    for x, r, kind in cells:
        out.append(f'<rect x="{X(x - cx / 2):.1f}" y="{Y(r + cr / 2):.1f}" width="{max(cx * sx, 1):.1f}" height="{max(cr * sy, 1):.1f}" '
                   f'fill="{colour[kind]}"/>')
    sr = p['shield_radius_m']
    out += [f'<line x1="{X(x0):.1f}" y1="{Y(sr):.1f}" x2="{X(p["shield_x_m"]):.1f}" y2="{Y(sr):.1f}" stroke="var(--good)" stroke-dasharray="6 4"/>',
            f'<text x="{X(x0) + 6:.1f}" y="{Y(sr) - 6:.1f}" class="lbl">shield shadow, r {sr:.0f} m (aligned stream)</text>']
    er = p['engine']['max_radius_m']
    out += [f'<line x1="{X(x0):.1f}" y1="{Y(er):.1f}" x2="{X(x1):.1f}" y2="{Y(er):.1f}" stroke="var(--bad)" stroke-dasharray="2 4"/>',
            f'<text x="{X(x0) + 6:.1f}" y="{Y(er) - 6:.1f}" class="lbl">FDP-1 engine hardware to r {er:.1f} m</text>']
    if el['wings_max_r_m'] > rmax:
        out.append(f'<text x="{W - 16}" y="{T - 6}" text-anchor="end" class="lbl">radiator wings continue to r {el["wings_max_r_m"]:,.0f} m ↑</text>')
    out.append(f'<line x1="{L}" y1="{Y(0):.1f}" x2="{W - 16}" y2="{Y(0):.1f}" stroke="var(--muted)"/>')
    step = 50
    for v in range(int(math.ceil(x0 / step)) * step, int(x1) + 1, step):
        out.append(f'<line x1="{X(v):.1f}" y1="{Y(0):.1f}" x2="{X(v):.1f}" y2="{Y(0) + 5:.1f}" stroke="var(--muted)"/>'
                   f'<text x="{X(v):.1f}" y="{Y(0) + 18:.1f}" text-anchor="middle" class="ax">{v}</text>')
    for v in range(0, int(rmax) + 1, 25):
        out.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" class="ax">{v}</text>')
    out.append(f'<text x="{W - 16}" y="{H - 6}" text-anchor="end" class="ax">x along the ship (m), bow → right</text>'
               f'<text x="12" y="{T - 6}" class="ax">r (m)</text></svg>')
    legend = ''.join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in (
        ('forward shield', colour['shield']), ('critical part inside the shadow', colour['part_covered']),
        ('critical part outside', colour['part_outside']), ('radiator inside', colour['radiator_covered']),
        ('radiator outside', colour['radiator_outside'])))
    return '\n'.join(out) + f'<p class="legend">{legend}</p>'


# ---------------------------------------------------------------------------------------------------------------- pages
def register_table(reg, link=None, compare=None):
    rows = []
    for r in reg:
        title = f'<a href="{link}#{r["id"]}">{esc(r["title"])}</a>' if link else esc(r['title'])
        three = f'<td><a href="{compare}#{r["id"]}">3D</a></td>' if compare else ''
        rows.append(f'<tr><td><code>{r["id"]}</code></td><td>{title}</td><td>{web_identity.topic_chip(r["id"])}</td><td>{tag(r["status"])}</td>'
                    f'<td>{esc(r["gap"])}</td>{three}</tr>')
    return ('<div class="scroll" tabindex="0"><table class="register"><thead><tr><th>ID</th><th>Problem</th><th>System</th><th>Status</th><th>Gap</th>'
            f'{"<th>Compare</th>" if compare else ""}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def register_cards(reg, compare=None):
    out = []
    for r in reg:
        cur = ''.join(f'<li>{esc(c)}</li>' for c in r['current'])
        unres = ''.join(f'<li>{esc(u)}</li>' for u in r.get('unresolved', []))
        cls = ' · '.join(esc(c) for c in r['classification'])
        dep = ', '.join(f'<a href="#{d}">{d}</a>' for d in r['depends'])
        out.append(f'''<article class="problem topic {(web_identity.topic(r["id"]) or ("",))[0]}" id="{r["id"]}">
  <h3><code>{r["id"]}</code> {esc(r["title"])} {tag(r["status"])} {web_identity.topic_chip(r["id"])}</h3>
  <p>{esc(r["description"])}</p>
  <dl>
    <dt>Now</dt><dd><ul class="plain">{cur}</ul></dd>
    <dt>Needed</dt><dd>{esc(r["target"])}</dd>
    <dt>Gap</dt><dd>{esc(r["gap"])}</dd>
    {f'<dt>Unresolved</dt><dd><ul class="plain">{unres}</ul></dd>' if unres else ''}
    <dt>Kind</dt><dd>{cls}{f" · depends on {dep}" if dep else ""}</dd>
  </dl>
  {f'<p class="compare-link"><a href="{compare}#{r["id"]}">Compare in 3D: what Wayfarer has, what it needs</a></p>' if compare else ''}
</article>''')
    return '\n'.join(out)


def entry_page(e, out_dir, revision, built, data):
    folder = e['folder']
    rel = folder.relative_to(ROOT).as_posix()
    md = Markdown(revision, folder)
    head = e['header']
    rows = ''.join(f'<tr><th>{esc(k)}</th><td>{md.inline(v)}</td></tr>' for k, v in head.items() if k != 'Review')
    body = [f'<header><p class="eyebrow">Lab · {esc(e["kind"])}</p><h1>{esc(e["name"])}</h1>',
            f'<p class="lead">{md.inline(e["question"])}</p></header>',
            f'<section class="panel"><table class="meta">{rows}'
            f'<tr><th>Source</th><td><a href="{REPO}/tree/{revision}/{rel}" rel="noopener"><code>{rel}/</code></a></td></tr></table>'
            '<p class="note">Nothing in lab/ is canon. The approved ship is the model on <code>main</code>; a lab number reaches it only '
            'through its owner workbook and the normal build loop.</p></section>']
    report = folder / 'REPORT.md'
    summary = None
    if report.exists():
        summary = next((b for h, b in sections(report.read_text()) if h and h.lower().startswith('summary')), None)
    if summary is None:
        summary = next((b for h, b in sections(notes_body(folder / 'NOTES.md')) if h and h.lower().startswith('findings')), None)
    if summary:
        body.append(f'<section><h2>Summary</h2>{Markdown(revision, report.parent if report.exists() else folder).render(summary)}</section>')
    if data and 'protection' in data:
        p = data['protection']
        body.append(f'''<section id="p11"><h2>Where the shield shadow ends</h2>
<p>The forward shield protects only what lies in its shadow. The problem map places the FDP-1 drive behind it and tests every part
against the shadow for an aligned dust stream (no arrival cone, no margin): {p["critical_outside"]} of {p["critical_parts"]} critical parts
lie partly or wholly outside, the farthest by {p["max_protrusion_m"]:.1f} m, and {100 * p["radiator_outside_fraction"]:.1f} % of the radiator
planform is outside. Geometric coverage is necessary, not sufficient: the shield's stopping power is not modelled.</p>
<div class="figure">{elevation_svg(p)}</div>
<div class="scroll" tabindex="0"><table><thead><tr><th>Protection question</th><th>State</th></tr></thead><tbody>
{"".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in p["unresolved"])}</tbody></table></div></section>''')
        body.append(f'<section><h2>Problem register</h2><p class="note">Values are filled from the FDP-1 record by the map\'s own model '
                    f'({data["checks"]["passed"]}/{data["checks"]["total"]} of its checks pass). TBD marks a value with no adequate source.</p>'
                    f'{register_cards(data["register"], "../../compare/" if data.get("compare") else None)}</section>')
    figs = figures(folder)
    if figs:
        (out_dir / 'fig').mkdir(parents=True, exist_ok=True)
        cards = []
        for f in figs:
            name = f.relative_to(folder).as_posix().replace('/', '__')
            shutil.copy2(f, out_dir / 'fig' / name)
            caption = f.stem.replace('_', ' ')
            cards.append(f'<figure><a href="fig/{esc(name)}"><img src="fig/{esc(name)}" alt="{esc(caption)}" loading="lazy"></a>'
                         f'<figcaption>{esc(caption)}</figcaption></figure>')
        body.append(f'<section><h2>Figures</h2><div class="gallery">{"".join(cards)}</div></section>')
    body.append('<section><details><summary>Working notes (NOTES.md, as committed)</summary>'
                f'<div class="notes">{md.render(notes_body(folder / "NOTES.md"))}</div></details></section>')
    if report.exists():
        body.append(f'<p class="note">Full report: <a href="{REPO}/blob/{revision}/{rel}/REPORT.md" rel="noopener"><code>{rel}/REPORT.md</code></a></p>')
    (out_dir / 'index.html').write_text(page(f'{e["name"]} · Wayfarer engineering', e['question'], '\n'.join(body), 3, revision, built))


COMPARE_HEAD = '''
<link rel="stylesheet" href="../compare.css">
<script type="importmap">
{ "imports": { "three": "../../viewer/vendor/three/three.module.min.js", "three/addons/": "../../viewer/vendor/three/addons/" } }
</script>
<script type="module" src="../compare.js"></script>'''


def compare_page(e, data, out_dir, revision, built):
    """engineering/compare/: per problem, today's ship (the Explore Ship GLB, the problem's subsystems solid) beside what the problem
    needs (the problem map's blockout, its groups solid), at one scale (web/engineering/compare.js). False if the map has no pairs."""
    cmp = lab_story(e['folder'], '--compare')
    if not cmp or not cmp.get('pairs'):
        return False
    reg = {r['id']: r for r in data['register']}
    cmp['problems'] = {i: {k: reg[i][k] for k in ('title', 'status', 'current', 'target', 'gap')} for i in reg}
    cmp['source'] = {'map': e['name'], 'link': f'../{e["kind_dir"]}/{e["folder"].name}/'}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'compare.json').write_text(json.dumps(cmp, separators=(',', ':')))
    tabs = ''.join(f'<button role="tab" data-pair="{p["id"]}" class="{(web_identity.topic(p["id"]) or ("",))[0]}" title="{esc(reg[p["id"]]["title"])}'
                   f' · {esc((web_identity.topic(p["id"]) or ("", "", ""))[1])}"><i aria-hidden="true"></i>{p["id"]}</button>' for p in cmp['pairs'])
    body = f'''<header><p class="eyebrow">Engineering · open problems</p><h1>What we have, what we need</h1>
<p class="lead">For each open problem: on the left the ship as it is built today, on the right what the problem needs. Both sides share
one camera and one scale, so a size difference is a real size difference.</p></header>
<section class="compare">
  <div class="pairs" role="tablist" aria-label="Problem">{tabs}</div>
  <div class="stage" id="stage">
    <canvas id="compare-view" aria-label="Side-by-side 3D comparison"></canvas>
    <div class="side-label left"><b>Today</b><span id="label-left"></span></div>
    <div class="side-label right"><b>Needed</b><span id="label-right"></span></div>
    <div class="gate" id="gate"><button id="load" class="primary">Load the 3D comparison</button>
      <span class="meta">Loads the Explore Ship model (a few MB) and the problem blockout.</span></div>
    <div class="cstatus" id="cstatus" hidden></div>
  </div>
  <div class="ctools"><span class="views" role="toolbar" aria-label="Camera"><button data-view="threequarter">3/4</button>
    <button data-view="side">Side</button><button data-view="top">Top</button><button data-view="front">Bow</button></span>
    <label><input type="checkbox" id="fit"> Fit each side (sizes no longer comparable)</label>
    <span class="meta" id="scale"></span></div>
  <article class="caption" id="caption"></article>
  <p class="note">Left: the approved model on <code>main</code>, as Explore Ship shows it; the problem's subsystems are solid and the rest is
    a ghost. Right: the <a href="{cmp["source"]["link"]}">{esc(e["name"])}</a> blockout, built at 1 m from the FDP-1 record on an
    earlier baseline of the ship. It shows what the problem needs, not a design: nothing on the right is canon.</p>
</section>'''
    (out_dir / 'index.html').write_text(page('What we have, what we need · Wayfarer engineering',
                                             'Per open problem, the ship as built beside what the problem needs, in 3D at one scale.',
                                             body, 2, revision, built, COMPARE_HEAD))
    return True


BUILD_HEAD = '''
<link rel="stylesheet" href="../build.css">
<script type="importmap">
{ "imports": { "three": "../../viewer/vendor/three/three.module.min.js", "three/addons/": "../../viewer/vendor/three/addons/" } }
</script>
<script type="module" src="../build.js"></script>'''


def build_page(e, seq, out_dir, revision, built):
    """engineering/build/: the assembly sequence, step by step on the Explore Ship model (web/engineering/build.js). The step list
    is written into the page, so it reads without WebGL; the 3D view adds the parts of each step to the ship built so far."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'sequence.json').write_text(json.dumps(seq, separators=(',', ':')))
    phases = {p['id']: p for p in seq['phases']}
    led = seq['ledger']
    items, last = [], None
    for st in seq['steps']:
        if st['phase'] != last:
            if last:
                items.append('</ol></li>')
            ph = phases[st['phase']]
            items.append(f'<li class="phase" data-phase="{ph["id"]}"><h3><span>{ph["id"][1:]}</span> {esc(ph["name"])}</h3>'
                         f'<p class="note">{esc(ph["note"])}</p><ol class="steps">')
            last = st['phase']
        m = st['mass']
        mass = f'+{m["added_t"]:,.0f} t' if m['added_t'] >= 0.5 else ''
        items.append(f'<li class="step" id="{st["id"]}" data-step="{st["id"]}"><button type="button" aria-controls="build-view">'
                     f'<b>{st["n"]}</b><span class="t">{esc(st["title"])}</span><span class="m">{mass}</span></button></li>')
    items.append('</ol></li>')
    n = len(seq['steps'])
    body = f'''<header><p class="eyebrow">Engineering · assembly</p><h1>How Wayfarer is built</h1>
<p class="lead">The approved ship, put together in the order its load paths allow: first the spine everything hangs from, then the
drive at the open aft end, the radiators, the habitat rings, the tank farm and the shield that closes the bow, and last the insides,
the propellant and the first burn. {n} steps in {len(seq["phases"])} phases, each shown on the Explore Ship model.</p></header>
<section class="build">
  <div class="stage" id="stage">
    <canvas id="build-view" aria-label="The ship as built up to the selected step"></canvas>
    <div class="step-label" id="step-label"></div>
    <div class="gate" id="gate"><button id="load" class="primary">Load the 3D build sequence</button>
      <span class="meta">Loads the Explore Ship model (a few MB). The steps below read without it.</span></div>
    <div class="cstatus" id="cstatus" hidden></div>
  </div>
  <div class="btools">
    <span class="nav" role="toolbar" aria-label="Step"><button id="prev" aria-label="Previous step">◀</button>
      <button id="play" aria-label="Play the sequence">▶ Play</button><button id="next" aria-label="Next step">▶</button></span>
    <input type="range" id="scrub" min="1" max="{n}" value="1" aria-label="Step">
    <label><input type="checkbox" id="ghost" checked> Show what comes later as a ghost</label>
    <span class="views" role="toolbar" aria-label="Camera"><button data-view="auto" aria-pressed="true">Step</button><button data-view="threequarter">3/4</button>
      <button data-view="side">Side</button><button data-view="top">Top</button><button data-view="front">Bow</button><button data-view="aft">Aft</button></span>
  </div>
  <div class="massbar" id="massbar" aria-hidden="true"></div>
  <div class="bgrid">
    <ol class="phases" id="steps">{"".join(items)}</ol>
    <article class="caption" id="caption" aria-live="polite"></article>
  </div>
  <p class="note">The order is a {tag(seq["status"])} judgment from the model's load paths, not canon: no workbook owns an assembly
    sequence yet. Mass comes from the placed mass model and the operating point: {led["dry_t"]:,.0f} t of hardware and stores plus
    {led["propellant_t"]:,.0f} t of propellant is {led["total_t"]:,.0f} t, the departure mass of {led["departure_t"]:,.0f} t plus the
    {led["circulation_t"]:,.0f} t ring corridors the operating point does not carry yet. The sequence will gain detail as the ship does;
    the reasoning is in the <a href="../{e["kind_dir"]}/{e["folder"].name}/">assembly-sequence study</a>.</p>
</section>'''
    (out_dir / 'index.html').write_text(page('How Wayfarer is built · Wayfarer engineering',
                                             'The assembly sequence of G.U. Wayfarer 001, step by step from the spine to first ignition.',
                                             body, 2, revision, built, BUILD_HEAD))
    return True


def build_teaser(seq):
    """The main page's entry to engineering/build/."""
    phases = ''.join(f'<a href="build/#{next(s["id"] for s in seq["steps"] if s["phase"] == p["id"])}"><code>{p["id"][1:]}</code> {esc(p["name"])}</a>'
                     for p in seq['phases'])
    shot = ('<a class="shot" href="build/#radiator_blades"><img src="build_preview.jpg" alt="The ship part-built: spine, drive and casing '
            'in place, the radiator blades going on" loading="lazy"></a>') if (ROOT / 'web/engineering/build_preview.jpg').exists() else ''
    return f'''<section id="build" class="teaser build-teaser">
  {shot}
  <div>
    <h2>How Wayfarer is built · step by step</h2>
    <p>The approved ship assembled in the order its load paths allow, from the spine to the first burn: {len(seq["steps"])} steps on the
      Explore Ship model, each with what it rests on, why it comes where it does and the mass it adds.</p>
    <p><a class="go" href="build/">Open the build sequence</a></p>
    <div class="pick">{phases}</div>
  </div>
</section>'''


def compare_teaser(prob):
    """The main page's entry to engineering/compare/: a preview, one sentence and one link per problem."""
    links = ''.join(f'<a href="compare/#{r["id"]}" title="{esc(r["title"])}"><code>{r["id"]}</code> {esc(r["title"])}</a>' for r in prob['register'])
    return f'''<section id="compare" class="teaser">
  <a class="shot" href="compare/#P08"><img src="compare_preview.jpg" alt="Today's tank farm beside the tank bays FDP-1 needs, in 3D at one scale" loading="lazy"></a>
  <div>
    <h2>What we have, what we need · in 3D</h2>
    <p>For every open problem, the ship as it is built today on the left and what the problem needs on the right, under one camera at one
      scale, so a size difference is a real one. P07, for example, sets today's radiators beside the wing area FDP-1 needs.</p>
    <p><a class="go" href="compare/">Open the 3D comparison</a></p>
    <div class="pick">{links}</div>
  </div>
</section>'''


def lab_ship(spec):
    """The canon ship as Engineering 2.0 draws it for scale, and its mission-ledger numbers (canon operating point)."""
    import layout
    o = layout.origins(spec)
    n = ship_numbers(spec)
    h = spec['habitat']
    r_out = h['outer_radius']['value'] if isinstance(h['outer_radius'], dict) else h['outer_radius']
    return {'hull': {'x_aft': o['AFT'], 'x_fwd': o['FWD'], 'r': spec['ship']['body_diameter']['value'] / 2, 'ring_x': o['RING_A'],
                     'ring_r': r_out}, 'departure_t': n['mission']['departure_mass_kg'] / 1e3, 'peak_g': n['burn']['accel_g'][1],
            'length_m': spec['ship']['length']['value']}


def main_page(site, spec, entries, dropped, problem, revision, built, play=True, lab2=None, seq=None):
    import story_lab
    n = ship_numbers(spec)
    b, m, fi = n['burn'], n['mission'], n['fi']
    sh = spec['ship']
    ve_c = n['ve_m_s'] / C
    total_dv = n['dv_m_s'] * m['burns']
    rad = spec['radiators']
    four = ROOT / 'lab/studies/four-burn-mission/REPORT.md'
    four_summary = next((bd for h, bd in sections(four.read_text()) if h and h.lower().startswith('summary')), '') if four.exists() else ''
    fdp1 = json.loads((ROOT / 'lab/variants/fdp1/results/fdp1-v1/summary.json').read_text())
    base, goal = fdp1['baseline'], fdp1.get('goal_1g', {})
    open_items = open_in_canon(spec)
    counts = status_counts(spec)

    def row(name, value, status, why):
        return f'<tr><td>{name}</td><td class="num">{value}</td><td>{tag(status)}</td><td>{why}</td></tr>'

    constraints = ''.join([
        row('Cruise speed', f'{spec["mission"]["target_speed"]["value"]} c = {spec["mission"]["target_speed"]["value"] * C / 1e3:,.0f} km/s',
            spec['mission']['target_speed']['canon_status'], 'The mission. Fixed.'),
        row('Burns', f'{m["burns"]} (out, brake, home, brake)', 'WORKING', 'Full return without refuelling: the ship carries its return propellant.'),
        row('Total Δv', f'{total_dv / C:.3f} c = {total_dv / 1e3:,.0f} km/s', 'DERIVED', 'Four times the cruise speed.'),
        row('Exhaust velocity', f'{n["ve_m_s"] / 1e3:,.0f} km/s ({ve_c:.4f} c)', spec['physics']['operating_point']['canon_status'],
            'Total Δv is almost exactly one exhaust velocity, so the whole mission needs a mass ratio of e.'),
        row('Mass ratio', f'{m["mass_ratio_per_burn"]:.3f} per burn, {m["mass_ratio_per_burn"] ** m["burns"]:.3f} overall', 'DERIVED', 'Rocket equation.'),
        row('Mission duration', f'{spec["mission"]["duration"]["value"]:.1f} years', spec['mission']['duration']['canon_status'],
            'Bounds the burn times and the coast.'),
        row('Design crew', f'{spec["crew"]["rated_occupancy"]["value"]} persons', spec['crew']['rated_occupancy']['canon_status'],
            f'The ship is built for {spec["crew"]["rated_occupancy"]["value"]}: habitat, life support, refuge, bunks and burn couches, and the protected '
            f'mass. Only {spec["crew"]["count"]} are aboard in the story; that is a story fact, not a design limit.'),
        row('Design acceleration', f'0 → {spec["mission"]["first_ignition"]["max_accel"]} g ramp', spec['mission']['first_ignition']['canon_status'],
            'The structural design-load case. The flight burns are power-limited and gentler.'),
        row('Peak fusion power', f'{b["peak_fusion_power_W"] / 1e12:,.0f} TW', spec['physics']['operating_point']['canon_status'],
            f'Directed jet efficiency {spec["physics"]["operating_point"]["directed_efficiency"]}.'),
        row('Drive heat absorbed', f'{b["peak_absorbed_heat_W"] / 1e9:.2f} GW of {b["hot_budget_W"] / 1e9:.2f} GW budget',
            spec['physics']['operating_point']['canon_status'],
            f'Only {spec["physics"]["operating_point"]["absorbed_fraction"]:.0e} of fusion power may reach the structure: a requirement on the drive, not a demonstrated property.'),
        row('Radiators', f'{rad["temperature"]["value"]:.0f} K, ε {rad["emissivity"]["value"]}, {rad["effective_area"]["value"]:,.0f} m² effective',
            rad['temperature']['canon_status'], f'Ideal rejection {b["ideal_rejection_W"] / 1e9:.2f} GW. Physical area is never shrunk to fit.'),
        row('Spin gravity', f'{spec["habitat"]["rpm"]:.0f} rpm at r {n["floor_r"]:.0f} m = {n["spin_g"]:.2f} g', spec['habitat']['canon_status'],
            'Two counter-rotating rings; they spin down and lock for high thrust.'),
        row('Forward shield', f'{spec["forward_shield"]["diameter"]["value"]:.0f} m diameter', spec['forward_shield']['diameter']['canon_status'],
            'Everything critical must stay in its shadow at 0.016 c. Its stack, material and mass are OPEN (OD-014).'),
    ])
    op_rows = ''.join(f'<tr><td>{a}</td><td class="num">{v}</td></tr>' for a, v in (
        ('Departure mass', t(m['departure_mass_kg'])), ('Mission propellant', t(m['propellant_kg'])), ('End mass (protected + operational)', t(m['end_mass_kg'])),
        ('First burn', f'{b["duration_d"]:.1f} days at {b["accel_g"][0]:.2f} to {b["accel_g"][1]:.2f} g, {b["distance_AU"]:.1f} AU'),
        ('Peak thrust', f'{b["peak_thrust_N"] / 1e6:.1f} MN'),
        ('Design ramp (0 → 1.5 g)', f'{fi["duration_d"]:.2f} days, {fi["distance_AU"]:.2f} AU')))
    open_html = ''.join(
        f'<details><summary><strong>{esc(area)}</strong> · {len(items)}</summary><ul class="plain">'
        + ''.join(f'<li><code>{esc(p)}</code> {esc(r)}</li>' for p, _, r in items) + '</ul></details>'
        for area, items in sorted(open_items.items(), key=lambda kv: -len(kv[1])))
    count_html = ' '.join(f'{tag(k)} {v}' for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    lab_cards = ''.join(
        f'<a class="card topic {(web_identity.topic(e["folder"].name) or ("",))[0]}" href="{e["kind_dir"]}/{e["folder"].name}/"><span class="kicker">{esc(e["kind"])}</span>'
        f'<strong>{esc(e["name"])}</strong><span>{Markdown(revision, ROOT / "lab").inline(e["question"])}</span>'
        f'<span class="meta">{tag(e["status"])} {web_identity.topic_chip(e["folder"].name)}</span></a>' for e in entries)
    dropped_rows = ''.join(f'<tr><td>{Markdown(revision, ROOT / "lab").inline(a)}</td><td><code>{esc(b_)}</code></td><td>{esc(c)}</td></tr>'
                           for a, b_, c in dropped)
    prob = problem['data']
    pmap = problem['entry']
    plink = f'{pmap["kind_dir"]}/{pmap["folder"].name}/'
    pp = prob['protection']
    play_card = ('<a class="choice" href="../interior/"><span class="kicker">Experience · inside</span><strong>Explore Interior</strong>'
                 '<span>Walk from the station into a habitat ring, at human scale.</span></a>'
                 '<a class="choice" href="../exterior/"><span class="kicker">Experience · outside</span><strong>Explore Exterior</strong>'
                 '<span>Fly the suited astronaut and the companion drone along the hull, on finite gas.</span></a>') if play else ''
    body = f'''<header>
  <p class="eyebrow">IGNITION · Wayfarer · Engineering</p>
  <h1>0.016 c and back</h1>
  <p class="lead">G.U. Wayfarer 001 is a fictional crewed fusion ship that we design as if it had to fly. This page shows the engineering
    state for other engineers: what the ship must do, the constraints, what is built, what we tried, and where the design still fails.
    Every number is generated from the repository at commit <code>{revision[:7]}</code>. The pages are read-only for now.</p>
</header>

<nav class="toc"><a href="#goal">1 Goal</a><a href="#constraints">2 Constraints</a><a href="#ship">3 The ship today</a>
  <a href="#tried">4 What we tried</a><a href="#problems">5 Open problems</a><a href="#follow">6 Follow along</a>
  {'<a href="compare/"><b>Compare in 3D</b></a>' if prob.get("compare") else ''}
  {'<a href="build/"><b>Build sequence</b></a>' if seq else ''}</nav>
{story_lab.teaser(lab2) if lab2 else ''}
{build_teaser(seq) if seq else ''}
{compare_teaser(prob) if prob.get("compare") else ''}

<section id="goal"><h2>1 · The goal</h2>
  <p>A ship built for a crew of {spec["crew"]["rated_occupancy"]["value"]} cruises at <strong>{spec["mission"]["target_speed"]["value"]} c</strong> ({spec["mission"]["target_speed"]["value"] * C / 1e3:,.0f} km/s)
    and comes home without refuelling. The mission is four burns: accelerate out, brake at the destination, accelerate home, and brake home.
    That totals {total_dv / C:.3f} c of Δv, which is almost exactly the drive's exhaust velocity of {ve_c:.4f} c. The rocket equation then
    says the departing ship must be <strong>e ≈ {m["mass_ratio_per_burn"] ** m["burns"]:.2f} times</strong> the ship that comes home.</p>
  <div class="grid2"><div class="panel"><h3>Today's mission ledger</h3><table>{op_rows}</table></div>
  <div class="panel"><h3>The hard parts</h3><ul class="plain">
    <li>The drive needs {b["peak_fusion_power_W"] / 1e12:,.0f} TW of fusion and must lose almost nothing of it to the structure.</li>
    <li>Everything critical must hide behind a {spec["forward_shield"]["diameter"]["value"]:.0f} m shield from dust that hits at {spec["mission"]["target_speed"]["value"] * C / 1e3:,.0f} km/s.</li>
    <li>The waste heat goes out at {rad["temperature"]["value"]:.0f} K through radiators that must not see the habitat or the cryogenic tanks.</li>
    <li>The crew live for years in {n["spin_g"]:.2f} g of spin gravity, with the rings locked during high thrust.</li></ul></div></div>
</section>

<section id="constraints"><h2>2 · The constraints</h2>
  <p>Wayfarer follows its engineering workbooks: <strong>Drive workbooks → parameters → shared formulas → geometry</strong>. Each value carries
    its status. LOCKED and BASELINE values come from the owner, WORKING values are agreed and still movable, DERIVED values are calculated,
    PROTOTYPE values are our unsourced choices, and OPEN means nobody knows yet. An unknown stays unknown and is never set to zero.</p>
  <div class="scroll" tabindex="0"><table><thead><tr><th>Quantity</th><th>Value</th><th>Status</th><th>Why it matters</th></tr></thead><tbody>{constraints}</tbody></table></div>
  <h3>What canon does not know yet</h3>
  <p>{sum(len(v) for v in open_items.values())} parameters are explicitly unknown (<code>known = false</code>). By area:</p>
  <div class="open">{open_html}</div>
  <p class="note">Statuses across all parameters: {count_html}</p>
</section>

<section id="ship"><h2>3 · The ship today</h2>
  <p>The approved model on <code>main</code> is a {sh["length"]["value"]} m body ({sh["length"]["canon_status"]}, inside the {sh["length"]["min"]:.0f}–{sh["length"]["max"]:.0f} m
    envelope) around a {sh["body_diameter"]["value"]:.0f} m spine. It has two {2 * spec["habitat"]["outer_radius"]["value"]:.0f} m counter-rotating habitat rings, a
    {spec["forward_shield"]["diameter"]["value"]:.0f} m conical forward shield, thirteen axial propellant vessels, and three {rad["temperature"]["value"]:.0f} K
    radiator blades graded through warm and low-temperature sections. It is proxy geometry (<code>REP_PROXY</code>): every shape comes from
    sourced or labelled parameters. It is not flight hardware.</p>
  <div class="choices">
    <a class="choice" href="../viewer/#view=threequarter"><span class="kicker">Inspect</span><strong>Explore Ship</strong>
      <span>The whole vehicle in 3D. Click any part to see its source status.</span></a>
    <a class="choice" href="../viewer/#view=side"><span class="kicker">Side elevation</span><strong>Ship in profile</strong>
      <span>The shield, the rings, the tank farm and the radiator blades along the axis.</span></a>
    {play_card}
  </div>
</section>

<section id="tried"><h2>4 · What we tried</h2>
  <p>Work that is not approved is kept in <code>lab/</code>. A <em>variant</em> proposes another form, a <em>study</em> computes numbers, and a
    <em>problem map</em> shows where a design fails without proposing a fix. None of it is canon.</p>
  <div class="cards">{lab_cards}</div>
  <h3>The finding that drives everything</h3>
  <p class="note">From the <a href="studies/four-burn-mission/">four-burn mission study</a>, as committed:</p>
  <div class="quote">{Markdown(revision, four.parent).render(four_summary)}</div>
  <h3>The candidate drive: FDP-1</h3>
  <p>FDP-1 is a pulsed D-³He drive with one magnetic nozzle, sized by the study in the speculative tier (target gain 3,000). It closes the
    four burns at <strong>{base["departure_t"]:,.0f} t</strong> departure mass, starting at {base["a0_g"]:.4f} g with {base["burn_years"]:.1f} years under thrust and a
    round trip of at least {base["min_round_trip_years"]:.2f} years. Its radiator wings reach r {base["wing_tip_radius_m"]:,.0f} m.
    {f'Holding 1 g does not close. The most it can reach is {goal["max_a0_g"]:.4f} g, a factor of {goal["deficit_factor"]:.0f} short.' if goal.get("max_a0_g") else ''}
    <a href="variants/fdp1/">The variant</a>.</p>
  {f'<details><summary>Dropped work</summary><div class="scroll" tabindex="0"><table><tbody>{dropped_rows}</tbody></table></div></details>' if dropped_rows else ''}
</section>

<section id="problems"><h2>5 · Open problems</h2>
  <p>The <a href="{plink}">FDP-1 problem map</a> lists where the candidate drive fails or is unsupported. Each problem gives the
    value it has now, the value it needs, and the gap. These are the places where outside engineering help matters most.</p>
  <div class="figure">{elevation_svg(pp)}</div>
  <p class="note">The {spec["forward_shield"]["diameter"]["value"]:.0f} m shield shades r {pp["shield_radius_m"]:.0f} m. FDP-1 engine hardware reaches r
    {pp["engine"]["max_radius_m"]:.1f} m, and {pp["critical_outside"]} of {pp["critical_parts"]} critical parts lie outside the shadow even for an aligned stream
    (<a href="{plink}#p11">P11</a>).</p>
  {f'<p><a href="compare/">Compare in 3D</a>: for each problem, the ship as built today on the left and what the problem needs on '
     'the right, at the same scale.</p>' if prob.get("compare") else ''}
  {register_table(prob["register"], plink, "compare/" if prob.get("compare") else None)}
</section>

<section id="follow"><h2>6 · Follow along</h2>
  <p>This section is read-only for now. Everything behind it is public:</p>
  <ul class="plain">
    <li><a href="{REPO}/blob/{revision}/lab/README.md" rel="noopener">lab/README.md</a> is the index of variants, studies and problem maps.</li>
    <li><a href="{REPO}/blob/{revision}/data/wayfarer_3d.toml" rel="noopener">data/wayfarer_3d.toml</a> holds the parameters and their statuses, and
      <a href="{REPO}/blob/{revision}/data/source_map.toml" rel="noopener">data/source_map.toml</a> holds where each one comes from.</li>
    <li><a href="{REPO}/blob/{revision}/docs/MODEL.md" rel="noopener">docs/MODEL.md</a> describes the current model.</li>
    <li><a href="{REPO}/commits/main" rel="noopener">The history on main</a>.</li>
  </ul>
</section>'''
    (site / 'engineering/index.html').write_text(page('Wayfarer engineering', 'The engineering story of G.U. Wayfarer 001: a 0.016 c full-return '
                                                      'fusion ship, its constraints, the lab work and the open problems.', body, 1, revision, built,
                                                      '\n<link rel="stylesheet" href="lab.css">' if lab2 else ''))


def build(root, site, revision=None, built=None, play=True):
    """Write <site>/engineering/ (with web/engineering/'s styles and scripts). Returns a small record for release.json."""
    from datetime import datetime, timezone
    from spec import load
    spec = load(root)[0]
    revision = revision or git('rev-parse', 'HEAD') or 'main'
    built = built or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    out = Path(site) / 'engineering'
    out.mkdir(parents=True, exist_ok=True)
    for src in (root / 'web/engineering').iterdir():
        if src.is_file():
            shutil.copy2(src, out / src.name)
    entries, dropped = lab_entries()
    problem = lab2 = seq = None
    pages = ['engineering/index.html']
    for e in entries:
        d = out / e['kind_dir'] / e['folder'].name
        d.mkdir(parents=True, exist_ok=True)
        data = lab_story(e['folder'])
        if data and problem is None and e['kind_dir'] == 'problems':
            problem = {'entry': e, 'data': data}
            data['compare'] = compare_page(e, data, out / 'compare', revision, built)
            if data['compare']:
                pages.append('engineering/compare/index.html')
        entry_page(e, d, revision, built, data)
        pages.append(d.relative_to(site).as_posix() + '/index.html')
        if data and 'breakthroughs' in data:
            lab2 = data
        if data and data.get('contract') == 'WF_ASSEMBLY_SEQUENCE' and seq is None:
            seq = data
            build_page(e, seq, out / 'build', revision, built)
            pages.append('engineering/build/index.html')
    if problem is None:
        raise RuntimeError('no lab problem map with a site.py: the Engineering page needs one')
    if lab2 is not None:
        import story_lab
        pages += story_lab.build(Path(site), lab2, lab_ship(spec), page, revision, built)
    main_page(Path(site), spec, entries, dropped, problem, revision, built, play, lab2, seq)
    files = sorted(p.relative_to(site).as_posix() for p in out.rglob('*') if p.is_file())
    return {'entry': 'engineering/', 'pages': pages, 'files': len(files),
            'bytes': sum((Path(site) / f).stat().st_size for f in files), 'lab_entries': len(entries),
            'problems': len(problem['data']['register'])}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path, required=True, help='site directory; writes <out>/engineering/ and copies site.css')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'web/site.css', args.out / 'site.css')
    print(json.dumps(build(ROOT, args.out.resolve()), indent=1))


if __name__ == '__main__':
    main()
