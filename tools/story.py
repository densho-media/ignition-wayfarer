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


def vertex_page(spec, out_dir, revision, built):
    """engineering/vertex/: the propulsion lineage, Vertex Research Demonstrator -> Compact Vertex Engine -> Propulsion Cluster,
    with every number from the pure modules (vertex_engine, vertex_cluster) and each row's evidence class."""
    import vertex_cluster as vc
    import vertex_engine as ve
    import vertex_inspect as vi
    import vertex_structure as vs
    if not vc.active(spec):
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    r, eng, cl = spec['vertex_research'], spec['vertex_engine'], spec['propulsion_cluster']
    fit, chk, rad = ve.fit_screen(spec), vc.check(spec), vc.radiation(spec)
    env, mass, mag, gaps = fit['envelope'], ve.mass_estimate(spec), chk['magnetics'], chk['gaps']
    num = lambda v: '—' if v is None else f'{v:,.4g}'
    calc_rows = ''.join(
        f'<tr><td><code>{c["id"]}</code> {esc(c["quantity"])}</td>'
        f'<td class="num">{num(c["research"])}</td>'
        f'<td class="num">{num(c["compact"])}</td><td>{esc(c["unit"])}</td><td>{tag(c["evidence"])}</td>'
        f'<td>{esc(c["formula"])}<br><span class="meta">{esc(c["validity"])}</span></td></tr>' for c in ve.calculations(spec))
    spec_rows = ''.join(
        f'<tr><td><code>{esc(x["id"])}</code> {esc(x["name"])}</td><td>{tag("SPECULATIVE")}</td><td>{esc(x["effect"])}</td>'
        f'<td>' + ', '.join(f'<a href="../breakthrough-lab/#{b.strip()}"><code>{b.strip()}</code></a>' for b in x['extends'].split(',')) + '</td></tr>'
        for x in eng['speculative']['items'])
    mass_rows = ''.join(f'<tr><td>{esc(k.replace("_", " ").lower())}</td><td class="num">{v / 1e3:,.0f} t</td></tr>'
                        for k, v in sorted(mass['by_category'].items(), key=lambda kv: -kv[1]) if v >= 500)
    anatomy = engine_anatomy(spec, vi)
    figs = ''.join(f'<figure><img src="../{f}" alt="{esc(a)}" loading="lazy"><figcaption>{esc(a)}</figcaption></figure>'
                   for f, a in (('vertex_engine.jpg', 'The Compact Vertex Engine, cut away: cartridge, collar, shield, closure coils, four nozzle loops'),
                                ('vertex_cluster.jpg', 'The four-engine cluster at the aft end of the ship, N1..N4 in the owner nozzle order'))
                   if (ROOT / 'web/engineering' / f).exists())
    body = f"""<header><p class="eyebrow">Engineering · propulsion</p><h1>From the Vertex demonstrator to the four-engine cluster</h1>
<p class="lead">The ship now shows a {tag(spec["propulsion_representation"]["status"])} drive: four copies of one reusable Compact Vertex Engine,
  linked from a single source into a Propulsion Cluster behind the {spec["forward_shield"]["diameter"]["value"]:.0f} m shield. It is a working representation,
  not canon: the Fiji Drive canon and every mission number stay as they are, and the research demonstrator it comes from stays BLOCKED.</p>
  <p><a class="go" href="../../viewer/#drive=SUSTAINED">See the cluster firing in Explore Ship</a> ·
  <a href="../breakthrough-lab/">Breakthrough Lab</a></p></header>
{f'<section class="figs">{figs}</section>' if figs else ''}
<section><h2>1 · Lineage</h2>
<div class="grid2">
 <div class="panel"><h3>A · {esc(r["name"])} <code>{esc(r["id"])}</code> {esc(r["version"])}</h3>
  <p>{tag(r["gate2_verdict"])} {esc(r["gate2_reason"])}</p>
  <p class="meta">{r["module_length_m"]:.0f} m module, r {r["module_radius_m"]:.1f} m, burn point {-r["burn_x_local_m"]:.0f} m aft,
   {r["yield_t_TNT"]:.1f} t TNT at {r["pulse_rate_Hz"]:.0f} Hz, {r["fusion_TW"]:.1f} TW, {r["thrust_MN"]:.2f} MN. Kept unchanged as asset
   <code>WF_VERTEX_RESEARCH</code>.</p></div>
 <div class="panel"><h3>B · {esc(eng["name"])} <code>{esc(eng["id"])}</code> {esc(eng["version"])}</h3>
  <p>{env["length"]:.1f} m long, r {env["max_radius"]:.2f} m (limit {fit["max_radius_limit"]:.1f} m), {fit["parts"]} parts in
   {len(ve.CATEGORIES)} functional categories, about {mass["total_kg"] / 1e3:,.0f} t {tag(mass["evidence"])}. One asset,
   <code>{esc(eng["asset"])}</code>; the cluster links it, never copies it.</p></div>
 <div class="panel"><h3>C · {esc(cl["name"])} <code>{esc(cl["id"])}</code> {esc(cl["version"])}</h3>
  <p>{cl["engine_count"]} engines on a {cl["pitch_radius_m"]:.0f} m pitch circle, canted {cl["cant_deg"]:.0f}°, {esc(cl["order"])}.
   Neighbour gap {gaps["adjacent_gap_m"]:.1f} m, central opening {gaps["central_opening_m"]:.1f} m, outer radius {gaps["outer_radius_m"]:.1f} m
   ({chk["visual_ratio"]:.2f} of the shield radius), overall hardware length {chk["overall_hardware_length_m"]:.1f} m.</p></div>
</div>
<h3>What changed on the way</h3>
<ul class="plain">
 <li><b>Retained:</b> the Vertex architecture (target cartridge and launcher, X-ray shield, closure coils, a four-loop magnetic nozzle) and the
  research armour fluence, so the compact yield follows from the stand-off by the inverse-square law.</li>
 <li><b>Redesigned:</b> the 104 m stand-off became {fit["stations"]["shield_aft"] - fit["stations"]["burn"]:.0f} m; the loops are re-proportioned,
  not scaled (the loop-radius to stand-off ratios spread by more than 1.5×); the frame hands the thrust to the twelve aft thrust-ring nodes clear of
  the antenna sweeps.</li>
 <li><b>Miniaturized:</b> one engine is about a hundredth of the research yield per pulse and runs a quarter of the design power.</li>
 <li><b>Speculative:</b> the five items below. Each extends a Breakthrough Lab entry and stays SPECULATIVE until that entry is resolved.</li>
 <li><b>Unresolved:</b> the coil and inter-engine field forces (section 5: up to {max(abs(c["Fz_N"]) for c in vs.coil_forces(spec, "NOMINAL")) / 1e6:.0f} MN on one loop
  and {abs(vs.inter_engine(spec)[0]["radial_N"]) / 1e6:.1f} MN pulling each engine toward the axis, against {mag["thrust_per_engine_MN"]:.2f} MN thrust per engine),
  the radiator line of sight to the burn points ({100 * rad["radiator_fraction"]:.1f} %), and the heat flux at
  the design point, {next(c["compact"] for c in ve.calculations(spec) if c["id"] == "C-05"):.0f}× the research load.</li>
</ul></section>
<section><h2>2 · The numbers</h2>
<p>Research values are the V4 demonstrator; compact values follow from the drawn geometry. {tag("CALCULATED")} rows are formulas on sourced or drawn
  inputs, {tag("ENGINEERING_PROTOTYPE")} rows are our unsourced choices, {tag("SPECULATIVE")} rows need a breakthrough.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Quantity</th><th>Research</th><th>Compact</th><th>Unit</th><th>Evidence</th><th>Formula</th></tr></thead>
<tbody>{calc_rows}</tbody></table></div>
<div class="grid2"><div class="panel"><h3>Engine mass by function</h3><table>{mass_rows}</table><p class="meta">{esc(mass["basis"])}</p></div>
<div class="panel"><h3>Cluster screens</h3><table>
 <tr><td>Layouts screened</td><td class="num">{chk["study"]["candidates"]} ({chk["study"]["passing"]} pass)</td></tr>
 <tr><td>Neighbour exhaust seen by an engine</td><td class="num">{100 * rad["neighbour_loop_fraction"]:.2f} %</td></tr>
 <tr><td>Radiator area seeing a burn point</td><td class="num">{100 * rad["radiator_fraction"]:.1f} %</td></tr>
 <tr><td>Six engines instead of four</td><td class="num">pitch {chk["six_engine"]["passing_pitch_m"]:.0f} m, outer r {chk["six_engine"]["passing_outer_radius_m"]:.1f} m</td></tr>
 <tr><td>Net magnetic torque</td><td>{esc(mag["net_torque"])}</td></tr></table>
 <p class="meta">{esc(mag["note"])}</p></div></div></section>
<section><h2>3 · Speculative items</h2>
<div class="scroll" tabindex="0"><table><thead><tr><th>Item</th><th>Status</th><th>What it assumes</th><th>Breakthrough Lab</th></tr></thead>
<tbody>{spec_rows}</tbody></table></div>
<p class="note">{esc(spec["propulsion_representation"]["authority"])}</p></section>
{anatomy}
{structure_section(spec, vs)}
{magnet_section(spec)}
{plasma_section(spec)}
{radiation_section(spec)}
{fiji_section(spec)}"""
    (out_dir / 'index.html').write_text(page('Vertex propulsion lineage · Wayfarer engineering',
                                             'How the Vertex research demonstrator became the Compact Vertex Engine and the four-engine Propulsion Cluster.',
                                             body, 2, revision, built))
    return True


def structure_section(spec, vs):
    """Section 5 of engineering/vertex/: Engine 1.2 structural validation, every number from vertex_structure.report."""
    R = vs.report(spec); sz = R['sizing']; cases = spec['vertex_engine']['structure']['current_cases']; old = vs.ENGINE_1_1
    f = lambda v, d=1: '—' if v is None else f'{v:,.{d}f}'
    lc_rows = ''.join(f'<tr><td><code>{x["id"]}</code> {esc(x["title"])}</td><td>{tag(x["evidence"])}</td>'
                      f'<td>{"; ".join(f"{esc(a)} {v:,.4g} {esc(u)}" for a, v, u in x["size"])}</td><td>{esc(x["note"])}</td></tr>' for x in R['load_cases'])
    coil_rows = ''.join(f'<tr><td>{c["name"]}</td><td class="num">{c["current_At"] / 1e6:,.2f}</td><td class="num">{c["Fz_N"] / 1e6:,.1f}</td>'
                        f'<td class="num">{c["hoop_N"] / 1e6:,.1f}</td><td class="num">{c["case_stress_Pa"] / 1e6:,.0f}</td>'
                        f'<td class="num">{k["case_stress_Pa"] / 1e6:,.0f}</td></tr>'
                        for c, k in zip(vs.coil_forces(spec, 'NOMINAL'), vs.coil_forces(spec, 'CONSERVATIVE')))
    g = spec['vertex_engine']['geometry']
    mem_rows = ''.join(f'<tr><td>{esc(vs.GROUP_TITLES[k])}</td><td class="num">{old[key]:.2f} → {g[key]:.2f}</td>'
                       + ''.join(f'<td class="num">{sz["engine"][c][k]["u"]:.2f}</td>' for c in cases)
                       + f'<td>{esc(max(sz["engine"]["NOMINAL"][k]["rows"], key=lambda r: r["u"]).get("governs", ""))}</td><td>{tag(vs.GROUP_STATUS[k])}</td></tr>'
                       for k, key in vs.ENGINE_KEYS.items())
    mem_rows += (f'<tr><td>Coil windings (case)</td><td class="num">—</td>' + ''.join(f'<td class="num">{sz["engine"][c]["winding"]["u"]:.2f}</td>' for c in cases)
                 + f'<td>hoop stress</td><td>{tag("CONDITIONALLY_SIZED")}</td></tr>')
    cl = sz['cluster']; groups = ('spoke', 'chord', 'ring_tie', 'engine_thrust_strut', 'hub_thrust_strut')
    cl_rows = ''.join(f'<tr><td>{esc(n.replace("_", " "))}</td>' + ''.join(f'<td class="num">{c["groups"][k]["u"]:.2f}</td>' for k in groups) + '</tr>'
                      for n, c in cl['cases'].items())
    ie = vs.inter_engine(spec); dip = R['dipole']; ti = sz['target']; li = sz['lithium']; el = sz['electrical']; dy = sz['dynamics']; th = sz['thermal']
    m = R['mass']
    counts = {}
    for p in R['parts']:
        counts[p['status']] = counts.get(p['status'], 0)+1
    conv = ''.join(f'<tr><td class="num">{c["grid_deg"]}°</td><td class="num">{c["elements"]}</td><td class="num">{c["ring_peak_M"] / 1e6:.3f}</td>'
                   f'<td class="num">{c["tie_N"] / 1e6:.3f}</td></tr>' for c in R['ring_convergence'])
    status_rows = ''.join(f'<tr><td>{tag(k)}</td><td>{esc(vs.STATUS_STYLE[k][0])}</td><td class="num">{counts.get(k, 0)}</td></tr>' for k in vs.STATUSES)
    return f"""<section id="structure"><h2>5 · Structure (Engine {esc(R["version"])})</h2>
<p class="lead">What the drawn engine has to carry if the drive worked, and how large its members must be to carry it. This is a screening
  calculation on PMDS material data, not a certified stress analysis, and it is not propulsion evidence: the drive stays {tag("SPECULATIVE")} and the
  research demonstrator's Gate 2 stays {tag("BLOCKED")}. <a href="../../viewer/#view=aft&amp;eng=N1&amp;ov=eng">See the sizing status in Explore Ship</a>.</p>
<h3>Load cases</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Case</th><th>Evidence</th><th>Size</th><th>Treatment</th></tr></thead><tbody>{lc_rows}</tbody></table></div>
<p>The six coils' forces on each other are steady whenever the coils are energised and dwarf the thrust: the closure coils push the first loop aft
  with {abs(vs.coil_forces(spec, "NOMINAL")[2]["Fz_N"]) / 1e6:,.0f} MN while one engine's thrust is {sz["cluster"]["magnetics"]["thrust_N"] / 1e6:.2f} MN.
  Three current sets bound them: NOMINAL (the C-07 stopping field at the burn point and a null at the shield face), CONSERVATIVE (each loop alone
  gives that field at its own centre) and EXTREME (conservative currents with plasma flux compression).</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Coil</th><th>MA-turns</th><th>Axial force MN</th><th>Hoop tension MN</th><th>Case stress MPa</th>
<th>Conservative MPa</th></tr></thead><tbody>{coil_rows}</tbody></table></div>
<p class="meta">Exact circular-loop fields (elliptic integrals). Case stress: hoop tension over the steel share of the winding pack
  ({spec["vertex_engine"]["structure"]["coil_case_fraction"]:.0%}); allowable {R["case_allowable"]["allowable"] / 1e6:,.0f} MPa (two thirds of 316LN's 4.2 K proof stress,
  {esc(R["case_allowable"]["source"])}). Negative: the closure coils are crushed inward.</p>
<h3>Engine members</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Member</th><th>Radius 1.1 → 1.2 (m)</th>{"".join(f"<th>{c}</th>" for c in cases)}<th>Governs</th><th>Status</th></tr></thead>
<tbody>{mem_rows}</tbody></table></div>
<p>Utilisation 1 is the allowable (Ti-6Al-4V yield / {spec["vertex_engine"]["structure"]["yield_safety_factor"]}, buckling with a factor
  {spec["vertex_engine"]["structure"]["buckling_safety_factor"]}). Members are sized for NOMINAL; CONSERVATIVE and EXTREME are reported, and no member of this
  envelope survives them. The loop seats now lean {", ".join(f'{l["name"]} {l.get("seat_offset_m", 0):g} m' for l in g["loops"])} forward to their hoops, so
  they carry the loop forces as struts; radial seats would have carried them in bending at up to 75 times their allowable.</p>
<h3>Cluster frame</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Load set</th>{"".join(f"<th>{k.replace('_', ' ')}</th>" for k in groups)}</tr></thead><tbody>{cl_rows}</tbody></table></div>
<p>Exact coil-set forces between the engines: each is pulled {abs(ie[0]["radial_N"]) / 1e6:.1f} MN toward the axis (NOMINAL) and turned by
  {max(abs(v) for v in ie[0]["torque_Nm"]) / 1e6:.0f} MN·m about its collar, because side-by-side neighbours of opposite polarity attract. The 1.1 cluster
  note called this repulsion and a pulse transient; it is attraction and steady. A point-dipole pair estimate gives {dip["adjacent_N"] / 1e6:.1f} MN.
  The frame is one FE model of every member, hub and engines rigid: lowest engine mount modes {", ".join(f"{k} {v:.1f} Hz" for k, v in cl["frequency_Hz"].items())},
  far below the {dy["pulse_Hz"]:,.0f} Hz pulse rate, so the mount passes about {dy["transmissibility"]:.1e} of the pulse ripple. The frame is
  {cl["magnetic_margin"]:,.0f} times stiffer than the field's pull grows as an engine moves in. One engine firing alone turns the ship with
  {sz["cluster"]["magnetics"]["thrust_N"] * spec["propulsion_cluster"]["pitch_radius_m"] / 1e6:.1f} MN·m; diagonal pairs cancel it.</p>
<h3>Other components</h3>
<ul class="plain">
 <li><b>Electrical (ME-03):</b> {el["energy_J"] / 1e9:.1f} GJ stored per engine; {el["lead_current_A"] / 1e3:.0f} kA leads (ITER class); dump voltage up to
  {max(r["dump_voltage_V"] for r in el["rows"]) / 1e3:.1f} kV for a {spec["vertex_engine"]["structure"]["quench_dump_time_s"]:.0f} s dump; lead pairs clamped against
  {el["rows"][0]["pair_force_N_m"] / 1e3:.1f} kN/m. {tag("CONDITIONALLY_SIZED")}</li>
 <li><b>Lithium (ME-04):</b> at {li["temperature_K"]:.0f} K no catalogue alloy is rated (Nb-1Zr stops near 1,400 K; TZM and Mo-Re are OPEN); one drawn line carries
  {li["capacity_W"] / 1e6:,.0f} MW, {100 * li["capacity_fraction"]:.4f} % of an engine's fusion power. {tag("BLOCKED")}</li>
 <li><b>Target injection (ME-05):</b> {ti["speed_m_s"] / 1e3:.1f} km/s over {ti["flight_m"]:.1f} m in {ti["time_of_flight_s"] * 1e3:.2f} ms; holding a
  {spec["vertex_engine"]["structure"]["target_miss_tolerance_m"] * 1e3:.0f} mm miss needs {ti["pointing_rad"] * 1e6:.0f} µrad pointing. The bore shutter as a tungsten chopper
  would see {ti["shutter_rim_stress_W_Pa"] / 1e9:.1f} GPa at its rim. {tag("BLOCKED")}</li>
 <li><b>Thermal (LC-05):</b> the L4 cold mass shrinks {th["coil_contraction_m"]["L4"] * 1e3:.0f} mm in radius on cooldown; LiH grows
  {th["shield_vs_titanium_per_100K_m"] * 1e3:.0f} mm more than titanium per 100 K at the shield rim; hot headers grow by tens of millimetres. All need sliding seats.</li>
 <li><b>Fatigue (LC-04):</b> {dy["cycles_per_hour"]:,.0f} pulses per firing hour, beyond measured S-N data for every catalogue alloy; the windings take the pulse
  field change directly. OPEN.</li>
</ul>
<div class="grid2"><div class="panel"><h3>Mass</h3><table>
 <tr><td>One engine</td><td class="num">{m["engine_1_1_kg"] / 1e3:,.0f} t → {m["engine_1_2_kg"] / 1e3:,.0f} t</td></tr>
 <tr><td>Cluster frame</td><td class="num">{m["frame_1_1_kg"] / 1e3:,.0f} t → {m["frame_1_2_kg"] / 1e3:,.0f} t</td></tr>
 <tr><td>Four engines and frame</td><td class="num">+{(4 * (m["engine_1_2_kg"] - m["engine_1_1_kg"]) + m["frame_1_2_kg"] - m["frame_1_1_kg"]) / 1e3:,.0f} t</td></tr></table>
 <p class="meta">{tag("ENGINEERING_PROTOTYPE")} estimates from the drawn volumes. The ship's mass budget and mission numbers do not read them and are unchanged.</p></div>
<div class="panel"><h3>Status of the 264 parts</h3><table>{status_rows}</table></div></div>
<h3>Method</h3>
<p class="meta">Members are thin-walled Ti-6Al-4V tubes with the mass model's solid fraction. The reaction ring and the cluster frame are frame FE models
  (3D beams, rigid hubs, skyline Cholesky), checked against a cantilever and the closed-form ring under equal radial loads; the ring model converges:</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Grid</th><th>Elements</th><th>Peak ring moment MN·m</th><th>Tie-rod force MN</th></tr></thead><tbody>{conv}</tbody></table></div>
</section>"""


def field_svg(R, cid, title):
    """Inline figure: one configuration's computed vacuum field lines in the engine's (x, r) half-plane, mirrored, with the coil cryostats,
    the shadow shield and the burn point (engine frame, aft to the left). Drawn from the evidence file's overlay lines."""
    import vertex_engine as ve
    row = next(r for r in R['candidates'] if r['id'] == cid); ov = R['overlay'].get(cid)
    if not ov:
        return ''
    x0, x1, h = -46.0, -9.0, 15.0; W, H = 560, 2*h*560/(x1-x0)
    X = lambda x: (x-x0)/(x1-x0)*W; Y = lambda r: H/2-r*(H/2)/h
    paths = []
    for line in ov['lines']:
        pts = list(zip(line[0::2], line[1::2]))
        for sg in (1, -1):
            paths.append('M' + ' L'.join(f'{X(x):.1f},{Y(sg*r):.1f}' for x, r in pts))
    coils = ''.join(f'<circle class="coil" cx="{X(c["x"]):.1f}" cy="{Y(sg*c["r"]):.1f}" r="{c["cryostat"]*(W/(x1-x0)):.1f}"/>'
                    for c in row['coils'] for sg in (1, -1))
    st = R['stations']
    shield = (f'<polygon class="shield" points="{X(st["shield_fwd"]):.1f},{Y(4.4):.1f} {X(st["shield_aft"]):.1f},{Y(5.4):.1f} '
              f'{X(st["shield_aft"]):.1f},{Y(-5.4):.1f} {X(st["shield_fwd"]):.1f},{Y(-4.4):.1f}"/>')
    burn = f'<circle class="burn" cx="{X(st["burn"]):.1f}" cy="{Y(0):.1f}" r="4"/>'
    return (f'<figure><svg class="figure-svg field" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{esc(title)}">'
            f'<rect class="bg" width="{W}" height="{H:.0f}"/><line class="axis" x1="0" y1="{Y(0):.1f}" x2="{W}" y2="{Y(0):.1f}"/>'
            f'<path class="fl" d="{" ".join(paths)}"/>{shield}{coils}{burn}'
            f'<text class="ax" x="6" y="14">aft (exit)</text><text class="ax" x="{W-70}" y="14">shield</text></svg>'
            f'<figcaption>{esc(title)}. Burn point (dot), coil cryostats (circles), shield (grey). Computed vacuum field lines, '
            f'B at the burn point {ov["B_burn_T"]:+.2f} T. A diagram, not light or plasma.</figcaption></figure>')


def magnet_section(spec):
    """Section 6 of engineering/vertex/: Engine 1.3 magnetic design closure, read from references/evidence/vertex_magnet.json (written by
    `python3 src/wayfarer/vertex_magnet.py --evidence`; tests/test_vertex_magnet.py fails when it is stale against the inputs)."""
    import json
    p = ROOT / 'references/evidence/vertex_magnet.json'
    if not p.exists():
        return ''
    R = json.loads(p.read_text()); mc = spec['vertex_engine']['magnet']
    f = lambda v, d=2: '—' if v is None else f'{v:,.{d}f}'
    rows = R['candidates']; ok = lambda r: all(c['passed'] for c in r['checks'].values())
    def topo(e):
        return 'cusp (null at the shield)' if abs(e['B_shield_T']) < 0.05 else ('forward mirror' if e['B_shield_T']*e['B_burn_T'] > 0 else 'reversed')
    head = ('<tr><th>Candidate</th><th>Status</th><th>Topology</th><th>Capture margin</th><th>Peak coil force MN</th><th>Stored GJ</th>'
            '<th>Conductor T</th><th>Case u</th><th>Members u (design / upper)</th><th>Inter-engine MN</th><th>Particles to shield</th>'
            '<th>Exhaust axial share</th><th>Hard requirements</th></tr>')
    body = ''
    for r in rows:
        e, s_ = r['eval'], r.get('structure', {}); pa = e.get('particles', {}); d = pa.get('D_debris', {})
        fails = [k for k, c in r['checks'].items() if not c['passed']]
        body += (f'<tr><td><code>{esc(r["id"])}</code> {esc(r["name"])}</td><td>{tag(r["status"])}</td><td>{esc(topo(e))}</td>'
                 f'<td class="num">{f(e["capture"]["worst"])}</td><td class="num">{e["peak_force_N"]/1e6:,.0f}</td><td class="num">{e["energy_J"]/1e9:,.1f}</td>'
                 f'<td class="num">{e["peak_conductor_T"]:.1f}</td><td class="num">{e["peak_case_u"]:.2f}</td>'
                 f'<td class="num">{f(s_.get("peak_u_design"))} / {f(s_.get("peak_u_upper"))}</td><td class="num">{f(s_.get("inter_engine_N", 0)/1e6, 1)}</td>'
                 f'<td class="num">{f(100*d.get("hits", {}).get("SHIELD", 0), 0)} %</td><td class="num">{f(d.get("axial_fraction"))}</td>'
                 f'<td>{"all pass" if not fails else "fails: " + esc("; ".join(fails))}</td></tr>')
    par = ''.join(f'<tr><td class="num">{p_["margin_required"]:.2f}</td><td class="num">{f(p_["margin"])}</td><td class="num">{p_["peak_force_MN"]:,.0f}</td>'
                  f'<td class="num">{p_["energy_GJ"]:.1f}</td><td class="num">{p_["case_u"]:.2f}</td><td class="num">{p_["conductor_T"]:.1f}</td></tr>'
                  for p_ in (R.get('pareto') or []))
    sp = ''.join(f'<tr><td>{esc(x["name"])}</td><td class="num">{x["speed_m_s"]/1e3:,.0f}</td><td class="num">{x["larmor_at_burn_m"]:.2f}</td></tr>' for x in R['species'])
    pz = R['plasma']; nom = rows[0]; best = max(rows[3:], key=lambda r: (ok(r), r['eval']['capture']['worst'] or 0))
    dt = nom['detachment']; fc = nom['flux_compression']; me = best['magnet']
    deg = ''.join(f'<tr><td>{esc(x["off"])} off</td><td class="num">{f(x["margin"])}</td><td class="num">{x["peak_force_N"]/1e6:,.0f}</td>'
                  f'<td class="num">{x["max_change_N"]/1e6:,.0f}</td></tr>' for x in best['degraded'])
    sens = min(min(x['up'] or 0, x['down'] or 0) for x in best['sensitivity'])
    figs = field_svg(R, nom['id'], f'{nom["id"]}: the 1.2 NOMINAL currents') + field_svg(R, best['id'], f'{best["id"]}: {best["name"]}')
    verdict = mc['verdict']
    return f"""<section id="magnet"><h2>6 · Magnetic design (Engine {esc(R["version"])})</h2>
<p class="lead">What the six coils have to do, whether any current set or coil geometry inside the drawn engine does it, and what that costs.
  Verdict: {tag(verdict)}. Active configuration <code>{esc(R["selected"])}</code>: no candidate is made the engine unless it passes every hard
  requirement, and the propulsion stays {tag("SPECULATIVE")} with the research Gate 2 {tag("BLOCKED")}. See also
  <a href="#anatomy">Anatomy</a>, <a href="#structure">Structure</a>, <a href="../weakest-links/">Weakest Links</a> and
  <a href="../breakthrough-lab/">Breakthrough Lab</a>; <a href="../../viewer/#view=aft&amp;eng=N1&amp;fl={esc(best["id"])}">field lines in Explore Ship</a>.</p>
<h3>Evidence levels</h3>
<ul class="plain">
 <li>{tag("VACUUM_FIELD_SOLVED")} Exact loop fields, finite windings near conductors, forces checked against the energy gradient; validated against the
  axis formula, superposition, symmetry and zero divergence.</li>
 <li>{tag("REDUCED_PLASMA_MODEL")} Energy-balance stopping of the expanding pulse in every direction, and a flux-conserving coil response to the
  diamagnetic pulse. Isotropic pulse energy; no favourable distribution assumed.</li>
 <li>{tag("PARTICLE_TRAJECTORY_SCREENED")} Test particles in the prescribed vacuum field (Boris pusher, energy conserved to 1e-9). They show where
  late, low-density plasma goes along the field; they have no self-consistent response.</li>
 <li>{tag("PLASMA_COUPLING_OPEN")} {tag("DETACHMENT_OPEN")} {tag("PROPULSION_FEASIBILITY_BLOCKED")} What none of these can establish: the high-beta
  bubble's own dynamics, instabilities, detachment and therefore any nozzle efficiency or thrust.</li></ul>
<h3>Audit of the 1.2 cases</h3>
<ul class="plain">
 <li><b>NOMINAL</b> sets two conditions (C-07 at the burn point, zero on the shield face) and so makes a cusp: the field is zero where plasma heads
  for the shield and the bore. Under the energy-balance screen it cannot stop forward plasma before the shield or C1 (margin {f(nom["eval"]["capture"]["worst"])}).
  It is structurally convenient, not magnetically closed.</li>
 <li><b>CONSERVATIVE</b> doubles the currents with the same null; it is a load bound, not a better field (margin {f(rows[1]["eval"]["capture"]["worst"])},
  winding case at {rows[1]["eval"]["peak_case_u"]:.1f}× allowable).</li>
 <li><b>EXTREME</b> multiplied forces by a fixed flux-compression factor. 1.3 replaces that with a model: the pulse as a diamagnetic bubble of
  {fc["radius_m"]:.1f} m at the burn point. For NOMINAL that bubble reaches within {fc["nearest_cryostat_m"]:.1f} m of a cryostat, so the coils sit inside the
  compressed field and the point-dipole response is {"valid" if fc["valid"] else "not valid"}: only a coupled plasma model can give their pulse load.
  For the mirror candidates the flux-conserving bound is {100*best["magnet"]["pulse"]["max_current_swing"]:.0f} % of a coil's current per pulse, which the cryostat walls screen.</li>
 <li>Labels kept, history kept: the three cases stay reproducible as <code>M0</code>.</li></ul>
<h3>Requirements</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Id</th><th>Function</th><th>Screen</th></tr></thead><tbody>
<tr><td>MF-01</td><td>Capture the pulse</td><td>Stopping distance in every direction against the hardware, margin ≥ {mc["capture_margin"]}; pulse {pz["energy_J"]["design"]/1e9:.2f} GJ
  charged ({100*pz["charged_share"]:.0f} % of {pz["yield_J"]/1e9:.2f} GJ), about {pz["mass_kg"]*1e6:.1f} mg at {pz["exhaust_m_s"]/1e3:,.0f} km/s.</td></tr>
<tr><td>MF-02</td><td>Protect shield face, coils, cage</td><td>Strict: shield, cryostats and cage; relaxed: the burn face as armour. Fields do not deflect X-rays or
  neutrons: the shield and VTX-S3 still carry those.</td></tr>
<tr><td>MF-03</td><td>Redirect aft</td><td>Test particles: share that leaves aft, share that reaches hardware.</td></tr>
<tr><td>MF-04</td><td>Collimate</td><td>Axial momentum share and 90th-percentile divergence of the aft particles; no efficiency claimed.</td></tr>
<tr><td>MF-05</td><td>Detach</td><td>Ion demagnetisation and Alfvén Mach number at the exit: {tag(dt["verdict"])}.</td></tr>
<tr><td>MF-06</td><td>Stable and tolerant</td><td>Nulls, ±5 % current sensitivity, each coil off in turn.</td></tr>
<tr><td>MF-07</td><td>Within the hardware</td><td>Winding case ≤ allowable, ≤ {mc["conductor_field_limit_T"]:.0f} T at the conductor and ≤ {mc["winding_current_density_A_m2"]/1e6:.0f} A/mm² (SPARC TFMC demonstrated
  envelope, {tag(mc["conductor_status"])}; REBCO critical current stays OPEN), four engines' coupled field.</td></tr>
</tbody></table></div>
<h3>Candidates</h3>
<div class="scroll" tabindex="0"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>
<p class="meta">Capture margin: obstacle distance over stopping distance in the worst protected direction. Members: the 1.2 engine members at their 1.2
  sizes under the candidate's design currents (charged energy) and upper currents (the whole yield as plasma). Particles: deuterons, {R["candidates"][0]["eval"]["particles"]["D_debris"]["n"]} directions;
  the four species give the same shares within a few per cent because every one of them is magnetised (Larmor radius ≪ field scale), so pitch angle alone decides.</p>
<div class="grid2">{figs}</div>
<h3>Margin against cost</h3>
<p>The currents-only optimum on the 1.2 coils for each required margin (Nelder–Mead, deterministic starts, every constraint as a penalty):</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Required</th><th>Reached</th><th>Peak force MN</th><th>Stored GJ</th><th>Case u</th><th>Conductor T</th></tr></thead><tbody>{par}</tbody></table></div>
<h3>Plasma</h3>
<div class="grid2"><div class="panel"><table><thead><tr><th>Species</th><th>Speed km/s</th><th>Larmor radius at C-07 m</th></tr></thead><tbody>{sp}</tbody></table></div>
<div class="panel"><p>At the exit plane of NOMINAL the field is {dt["B_exit_T"]:.2f} T; the pulse spread over the nozzle has β ≈ {dt["beta_exit"]:,.1f} and
  Alfvén Mach number {dt["alfven_mach"]:,.1f}. Electrons stay magnetised (Larmor radius {dt["electron_larmor_exit_m"]*1e3:.2f} mm), so whether the
  plasma leaves the field lines is {tag("DETACHMENT_OPEN")}: no nozzle efficiency or thrust follows from these fields.</p></div></div>
<h3>Magnet engineering ({esc(best["id"])})</h3>
<ul class="plain">
 <li>{me["energy_J"]/1e9:.1f} GJ stored per engine; at {me["lead_current_A"]/1e3:.0f} kA leads the coils need {", ".join(f'{x["name"]} {x["turns"]:.0f}' for x in me["rows"])} turns;
  dump voltage up to {max(x["dump_voltage_V"] for x in me["rows"])/1e3:.1f} kV; charging at {me["ramp_supply_V"]:.0f} V takes up to {max(x["ramp_s"] for x in me["rows"])/60:.0f} min.
  The magnets are steady; only the ramps, a dump and the pulse ripple change them.</li>
 <li>Pulse train at {me["pulse"]["rate_Hz"]:,.0f} Hz: the cryostat wall's skin depth is {me["pulse"]["skin_depth_m"]*1e3:.1f} mm against a {me["pulse"]["wall_m"]*1e3:.0f} mm wall, so the windings
  see little of it; the walls take it as eddy heat instead. Every 0.1 % of the {me["pulse"]["charged_power_W"]/1e12:.1f} TW charged power that couples into them is
  {me["pulse"]["heat_per_permille_W"]/1e9:.1f} GW per engine, far beyond any cryoplant: a weakest link, not a solved interface.</li>
 <li>Degraded modes and sensitivity: worst margin with one coil 5 % off {f(sens)}; one coil off:</li></ul>
<div class="scroll" tabindex="0"><table><thead><tr><th>Mode</th><th>Capture margin</th><th>Peak force MN</th><th>Largest force change MN</th></tr></thead><tbody>{deg}</tbody></table></div>
<p class="meta">Evidence file <code>references/evidence/vertex_magnet.json</code> (input hash <code>{esc(R["input_hash"])}</code>), written by
  <code>python3 src/wayfarer/vertex_magnet.py --evidence</code>; the stored candidates are re-optimised by <code>--optimise</code>.</p>
</section>"""


def cavity_svg(M, P, cid, title):
    """Inline figure: the coupled cavity at the end of its first pass (engine (x, r) half-plane, mirrored, aft to the left): the sheet
    through the surface markers, each marker coloured by its outcome, with the coil cryostats, shield and burn point. From the evidence."""
    cv = P['coupled'].get(cid); row = next((r for r in M['candidates'] if r['id'] == cid), None)
    if not cv or not cv.get('markers') or not row:
        return ''
    x0, x1, h = -46.0, -9.0, 15.0; W, H = 560, 2*h*560/(x1-x0)
    X = lambda x: (x-x0)/(x1-x0)*W; Y = lambda r: H/2-r*(H/2)/h
    mk = cv['markers']; cls = {'STOPPED': 'c-st', 'AFT': 'c-af', 'OUT': 'c-af'}
    line = lambda sg: 'M' + ' L'.join(f'{X(min(max(q["x"], x0), x1)):.1f},{Y(sg*min(q["rho"], h)):.1f}' for q in mk)
    dots = ''.join(f'<circle class="{cls.get(q["outcome"], "c-hw")}" cx="{X(min(max(q["x"], x0), x1)):.1f}" cy="{Y(sg*min(q["rho"], h)):.1f}" r="2.6"/>'
                   for q in mk for sg in (1, -1))
    coils = ''.join(f'<circle class="coil" cx="{X(c["x"]):.1f}" cy="{Y(sg*c["r"]):.1f}" r="{c["cryostat"]*(W/(x1-x0)):.1f}"/>'
                    for c in row['coils'] for sg in (1, -1))
    st = M['stations']
    shield = (f'<polygon class="shield" points="{X(st["shield_fwd"]):.1f},{Y(4.4):.1f} {X(st["shield_aft"]):.1f},{Y(5.4):.1f} '
              f'{X(st["shield_aft"]):.1f},{Y(-5.4):.1f} {X(st["shield_fwd"]):.1f},{Y(-4.4):.1f}"/>')
    burn = f'<circle class="burn" cx="{X(st["burn"] + cv["burn_shift_m"]):.1f}" cy="{Y(0):.1f}" r="4"/>'
    return (f'<figure><svg class="figure-svg field cavity" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{esc(title)}">'
            f'<rect class="bg" width="{W}" height="{H:.0f}"/><line class="axis" x1="0" y1="{Y(0):.1f}" x2="{W}" y2="{Y(0):.1f}"/>'
            f'<path class="sheet" d="{line(1)} {line(-1)}"/>{shield}{coils}{burn}{dots}'
            f'<text class="ax" x="6" y="14">aft (exit)</text><text class="ax" x="{W-70}" y="14">shield</text></svg>'
            f'<figcaption>{esc(title)}. The cavity sheet at the end of its first pass: blue markers stagnated in the field, green left aft, '
            f'red reached hardware. Coil cryostats (circles), shield (grey), burn point (dot). A model diagram, not light or plasma.</figcaption></figure>')


def plasma_section(spec):
    """Section 7 of engineering/vertex/: Engine 1.4 coupled plasma and the architecture decision, read from
    references/evidence/vertex_plasma.json (written by `python3 src/wayfarer/vertex_plasma.py --evidence`; tests/test_vertex_plasma.py
    fails when it is stale against the inputs)."""
    import json
    p = ROOT / 'references/evidence/vertex_plasma.json'; pm = ROOT / 'references/evidence/vertex_magnet.json'
    if not p.exists() or not pm.exists():
        return ''
    P = json.loads(p.read_text()); M = json.loads(pm.read_text()); pc = spec['vertex_engine']['plasma']
    f = lambda v, d=2: '—' if v is None else f'{v:,.{d}f}'
    pct = lambda v, d=1: '—' if v is None else f'{100*v:,.{d}f} %'
    ids = list(P['coupled'])
    base = ''.join(f'<tr><td><code>{esc(k)}</code></td><td class="num">{f(b["capture_margin"])}</td><td class="num">{pct(b["shield_particles"])}</td>'
                   f'<td class="num">{b["peak_force_N"]/1e6:,.0f}</td><td class="num">{b["stored_energy_J"]/1e9:.1f}</td><td class="num">{f(b["axial_fraction"])}</td>'
                   f'<td class="num">{f(b["divergence_p90_deg"], 0)}°</td></tr>' for k, b in P['baseline_1_3'].items())
    aud = ''
    for k in ids:
        a = P['audit']['candidates'][k]; w = a['weights']; mid = str(pc['fast_product_share'][1])
        conv = ', '.join(f'{x["n"]}: {pct(x["shield"])}' for x in a['convergence']['D_debris'])
        aud += (f'<tr><td><code>{esc(k)}</code></td><td>{esc(conv)}</td><td class="num">{pct(a["count_weighted"])} ± {pct(a["uncertainty"])}</td>'
                f'<td class="num">{pct(w[mid]["energy"])}</td><td class="num">{pct(w[mid]["momentum"])}</td><td class="num">{pct(a["mirror"]["forward_loss"])}</td>'
                f'<td class="num">{f(a["mirror"]["mirror_ratio"])}</td><td class="num">{pct(a["best"]["D_debris"]["shield_returned"], 0)}</td></tr>')
    reg = P['regime']['M2']
    models = ''.join(f'<tr><td><code>{esc(m["id"])}</code></td><td>{"fits" if m["fits"] else "does not fit"}{" · selected" if m["id"] == reg["selected"] else ""}</td>'
                     f'<td>{esc(m["why"])}</td></tr>' for m in reg['models'])
    hc = P['hybrid_cost']
    coup = ''
    for k in ids:
        cv = P['coupled'][k]; fp = cv['first_pass']
        hard = sum(v for q, v in fp.items() if q not in ('AFT', 'OUT', 'STOPPED'))
        for q, l in cv['ledger'].items():
            coup += (f'<tr><td><code>{esc(k)}</code></td><td>{esc(q)}</td><td class="num">{pct(l["shield"])}</td><td class="num">{pct(l["hardware"])}</td>'
                     f'<td class="num">{pct(l["aft"])}</td><td class="num">{l["impulse_Ns"]:,.0f}</td></tr>')
    led = ''.join(f'<tr><td><code>{esc(k)}</code></td><td class="num">{pct(sum(v for q, v in P["coupled"][k]["first_pass"].items() if q not in ("AFT", "OUT", "STOPPED")))}</td>'
                  f'<td class="num">{pct(P["coupled"][k]["first_pass"].get("STOPPED", 0))}</td><td class="num">{P["coupled"][k]["energy_error"]:+.2%}</td>'
                  f'<td class="num">{P["coupled"][k]["momentum_error"]:.1%}</td><td class="num">{max(P["coupled"][k]["dI_rel"], key=abs):+.0%}</td>'
                  f'<td class="num">{max(P["coupled"][k]["F_peak_N"])/1e6:,.0f}</td><td class="num">{P["coupled"][k]["conductor_peak_T"]:.1f}</td>'
                  f'<td>{esc(P["coupled"][k]["coil_contact"]["coil"]) + " cryostat touched" if P["coupled"][k]["coil_contact"] else "none"}</td></tr>' for k in ids)
    cvr = ''.join(f'<tr><td><code>{esc(k)}</code></td>' + ''.join(f'<td class="num">{x["n"]}/{x["ds_m"]:.2f}: {pct(x["shield_first"])} ({pct(x["hardware_first"])})</td>' for x in P['convergence'][k]['rows'])
                  + '</tr>' for k in ids)
    d2 = P['detachment']['M2']
    ext = ''.join(f'<tr><td class="num">{x["downstream_m"]:.0f}</td><td class="num">{pct(x["aft_first_pass"])}</td><td class="num">{pct(x["stopped"])}</td></tr>' for x in d2['domain_extension'])
    plume = ''.join(f'<tr><td class="num">{x["downstream_m"]:.0f}</td><td class="num">{x["B_axis_T"]:.3f}</td><td class="num">{x["field_energy_J"]/1e9:.2f}</td>'
                    f'<td class="num">{f(x["interaction"]["isotropic"])} – {f(x["interaction"]["aft"])}</td></tr>' for x in d2['plume'])
    th = P['thermal']['M2']; e = th['eddy']; tr = P['treg']; alt = P['alternatives']
    dep = ''.join(f'<tr><td>{esc(q)}</td><td class="num">{pct(th["ledger"][q]["shield"])}</td><td class="num">{th["shield_heat_flux_W_m2"][q]/1e6:,.0f}</td></tr>' for q in th['ledger'])
    gates = ''.join(f'<tr><td><code>{esc(g["id"])}</code></td><td>{esc(g["name"])}</td><td>{tag(g["status"])}</td><td>{esc(g["value"])}</td><td class="meta">{esc(g["note"])}</td></tr>'
                    for g in P['gates'])
    a3 = ''.join(f'<tr><td>{esc(r["name"])}</td><td class="num">{r["exhaust_m_s"]/1e3:,.0f}</td><td>{esc(r["maturity"])}</td><td>{esc(r["nozzle"])}</td><td>{esc(r["mission"])}</td></tr>'
                 for r in alt['A3']['rows'])
    a2 = ''.join(f'<tr><td>{esc(k)}</td><td class="num">{v["burn_shift_m"]:+.0f}</td><td class="num">{v["energy_J"]/1e9:.2f}</td>'
                 f'<td class="num">{pct(min(v["shield"].values()))} – {pct(max(v["shield"].values()))}</td></tr>' for k, v in alt['A2']['runs'].items())
    plate = ''.join(f'<tr><td class="num">{x["mass_ratio"]:.0f}×</td><td class="num">{x["exhaust_m_s"]/1e3:,.0f}</td><td class="num">{x["mass_ratio_mission"]:,.1f}</td></tr>'
                    for x in alt['A2']['plate'])
    figs = cavity_svg(M, P, 'M0-NOMINAL', 'M0: the 1.2 cusp') + cavity_svg(M, P, 'M2', 'M2: the 1.3 mirror')
    m2 = P['coupled']['M2']; lim = spec['vertex_engine']['magnet']['particle_hit_limit']
    lo = min(x['shield'] for x in m2['ledger'].values()); hi = max(x['shield'] for x in m2['ledger'].values())
    return f"""<section id="plasma"><h2>7 · Plasma coupling and propulsion feasibility (Engine {esc(P["version"])})</h2>
<p class="lead">Does the plasma's own response rescue the magnetic nozzle, and if not, what is the smallest defensible change? Outcome
  {tag(P["decision"]["outcome"])}: no feasible architecture demonstrated. Verdict {tag(P["decision"]["verdict"])}, {tag(P["decision"]["thrust"])},
  {tag(P["decision"]["detachment"])}. Active configuration <code>{esc(P["decision"]["selected"])}</code>, unchanged. See also
  <a href="#anatomy">Anatomy</a>, <a href="#structure">Structure</a>, <a href="#magnet">Magnetic design</a>, <a href="../weakest-links/">Weakest Links</a>
  and <a href="../breakthrough-lab/">Breakthrough Lab</a>.</p>
<h3>Why the 1.3 designs failed, and what the particle model really measured</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>1.3 reference</th><th>Capture margin</th><th>Particles to shield</th><th>Peak force MN</th><th>Stored GJ</th>
<th>Axial share</th><th>Divergence p90</th></tr></thead><tbody>{base}</tbody></table></div>
<div class="scroll" tabindex="0"><table><thead><tr><th>Audit</th><th>Shield share by directions (deuterons)</th><th>Count-weighted ± uncertainty</th>
<th>Energy-weighted</th><th>Momentum-weighted</th><th>Mirror loss cone</th><th>Mirror ratio</th><th>Shield hits that first went aft</th></tr></thead><tbody>{aud}</tbody></table></div>
<p>The 1.3 number is converged and robust to timestep, target position and speed, and it is the same for all four species because it is the
  adiabatic mirror loss cone: an isotropic source between {f(P["audit"]["candidates"]["M2"]["mirror"]["mirror_ratio"])}× mirrors loses
  {pct(P["audit"]["candidates"]["M2"]["mirror"]["forward_loss"])} forward whatever its rigidity. Weighting by energy or momentum does not change it.
  It describes a plasma too thin to push the field. The real pulse is not that.</p>
<h3>Which plasma model applies</h3>
<p>At the burn point the pulse has β ≈ {reg["beta_burn"]:,.0f}: it pushes the field out of its way. It is collisionless (mean free path
  {reg["mfp_m"]:.1e} m), its ion skin depth is {reg["ion_skin_m"]:.2f} m and its debris Larmor radius {reg["larmor_m"]["D_debris"]:.2f} m against a cavity of about
  {reg["radius_m"]:.1f} m. Electrons are strongly magnetised (r<sub>Le</sub> {reg["electron_larmor_m"]*1e3:.2f} mm).</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Model</th><th>Fit</th><th>Why</th></tr></thead><tbody>{models}</tbody></table></div>
<p class="meta">A hybrid-PIC run that resolves the skin depth would need about {hc["2D"]["core_hours"]:,.0f} core-hours in 2D and
  {hc["3D"]["core_hours"]:,.0f} core-hours ({hc["3D"]["memory_GB"]:,.0f} GB) in 3D ({esc(hc["assumptions"])}). Not executed: it needs separate approval.</p>
<h3>The coupled cavity (D21-B)</h3>
<p>{tag("COUPLED_CAVITY_MODEL")} The pulse as a perfectly diamagnetic sharp boundary: no field inside, the sheet current and all six
  flux-conserving coils solved together every step, Lagrangian surface markers pushed by the magnetic pressure. Validated on a diamagnetic sphere in a
  uniform field (surface field within {pct(P["validation"]["sphere"]["max_error"], 2)} of 1.5 B<sub>0</sub> sin θ). Each candidate's energy closes
  to within 2 %, and Newton's third law between the sheet and the coils holds to within the error shown.</p>
<div class="grid2">{figs}</div>
<div class="scroll" tabindex="0"><table><thead><tr><th>Candidate</th><th>Hardware, first pass</th><th>Stagnated</th><th>Energy error</th><th>Momentum error</th>
<th>Largest coil current change</th><th>Peak coil force MN</th><th>Conductor T</th><th>Contact</th></tr></thead><tbody>{led}</tbody></table></div>
<p>Most of the pulse stagnates in the compressed field. Where it goes next is outside a sharp-boundary model, so three closures bracket it:
  <b>aft</b> (the nozzle sends all of it aft), <b>isotropic</b> (it re-expands like the first pass) and <b>channelled</b> (it streams along the
  surface the way it was moving at stagnation).</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Candidate</th><th>Closure</th><th>Shield (energy)</th><th>All hardware</th><th>Aft</th><th>Impulse N s / pulse</th></tr></thead>
<tbody>{coup}</tbody></table></div>
<p class="meta">Convergence of the first-pass shield share, all hardware in brackets (markers / step m). Each marker carries a fixed
  solid angle, so a share moves in steps of one marker; M2 holds within {pct(P["convergence"]["M2"]["spread"])}, M0's shield share does not converge
  (its hardware share changes {pct(P["convergence"]["M0-NOMINAL"]["finest_change"])} between the two finest counts).</p>
<div class="scroll" tabindex="0"><table><tbody>{cvr}</tbody></table></div>
<p><b>Result.</b> Coupling does not rescue M0: its cusp puts plasma on the shield and on the C1/C2 cryostats. For M2 it removes most of the
  test-particle loss cone on the first pass, but the stagnated plasma decides the outcome: the shield's energy share is {pct(lo)}–{pct(hi)}
  across closures, against a {pct(lim, 0)} screening limit. The forward pole of the cavity is topological, so the leak can be moved but not closed (A1).</p>
<h3>Detachment and thrust</h3>
<p>{esc(d2["reading"])}</p>
<div class="grid2"><div class="panel scroll" tabindex="0"><table><thead><tr><th>Escape plane m past exit</th><th>Aft, first pass</th><th>Stagnated</th></tr></thead><tbody>{ext}</tbody></table></div>
<div class="panel scroll" tabindex="0"><table><thead><tr><th>m past exit</th><th>B on axis T</th><th>Field energy aft GJ</th><th>Plume / field energy</th></tr></thead><tbody>{plume}</tbody></table></div></div>
<p>Impulse per pulse follows from momentum conservation: the ship gains what leaves aft. For M2 that is
  {min(x["impulse_Ns"] for x in m2["ledger"].values()):,.0f}–{max(x["impulse_Ns"] for x in m2["ledger"].values()):,.0f} N s against the
  {m2["mass_kg"]*m2["speed_m_s"]:,.0f} N s the C-10 thrust assumes, before any divergence loss. {tag("THRUST_UNPROVEN")}</p>
<h3>Where the rest of the energy goes</h3>
<div class="grid2"><div class="panel"><table><thead><tr><th>M2 closure</th><th>Shield share</th><th>Shield face MW/m²</th></tr></thead><tbody>{dep}</tbody></table>
<p class="meta">Tungsten plasma-facing class: {pc["pfc_heat_flux_W_m2"][0]/1e6:.0f}–{pc["pfc_heat_flux_W_m2"][1]/1e6:.0f} MW/m² (ITER divertor targets). Even the
  optimistic closure is far above it: a 5 % particle limit says nothing about survival.</p></div>
<div class="panel"><ul class="plain">
 <li>X-rays and neutrons are not deflected by any field. The hardware covers {pct(th["hardware_sky"])} of the sky from the burn point, so it absorbs about
  {th["xray_absorbed_W"]/1e9:,.0f} GW of X-rays per engine; on the shield face that is {th["xray_shield_flux_W_m2"]/1e6:,.0f} MW/m². The ship's 1800 K radiators reject
  about {th["ship_radiator_W"]/1e9:.0f} GW in total.</li>
 <li>The cryostat walls screen the pulse: their diffusion time ({e["wall_diffusion_s"]*1e3:.1f} ms) is longer than the pulse period, so the windings see a
  steady field and the walls take {e["power_W"][0]/1e9:,.1f}–{e["power_W"][1]/1e9:,.0f} GW of eddy heat at 20 K per engine
  ({e["refrigeration_W"][0]/1e12:,.1f}–{e["refrigeration_W"][1]/1e12:,.0f} TW of refrigeration input).</li></ul></div></div>
<h3>Regenerative cooling (T-REG)</h3>
<ul class="plain">
 <li><b>T0</b> radiators: the absorbed {tr["absorbed_W"]/1e9:,.0f} GW per engine needs {tr["T0"]["radiator_m2"]/1e6:,.2f} km² at 1800 K,
  {tr["T0"]["ratio"]:,.0f}× the ship's radiator area.</li>
 <li><b>T1</b> hydrogen heated by the lithium loop and expelled: {tr["T1"]["hydrogen_kg_s"]:,.0f} kg/s at {tr["T1"]["exhaust_m_s"]/1e3:.1f} km/s, against the engine's
  {tr["T1"]["engine_propellant_kg_s"]*1e3:.0f} g/s at {P["coupled"]["M2"]["speed_m_s"]/1e3:,.0f} km/s. {esc(tr["T1"]["verdict"])}</li>
 <li><b>T2</b> Brayton conversion: {tr["T2"]["electric_W"]/1e9:,.0f} GW electric, but {tr["T2"]["radiator_m2"]/1e6:,.1f} km² of radiator at {tr["T2"]["cold_side_K"]:.0f} K. {esc(tr["T2"]["verdict"])}</li>
 <li>Verdict {tag(tr["verdict"])}. Unchanged: {esc(", ".join(tr["blocked_unchanged"]))}.</li></ul>
<h3>Alternative architectures</h3>
<div class="grid2"><div class="panel"><h4>A1 · {esc(alt["A1"]["name"])} {tag(alt["A1"]["status"])}</h4><p>{esc(alt["A1"]["topology"])}</p>
 <p>{esc(alt["A1"]["result"])}. {esc(alt["A1"]["cost"])}</p></div>
<div class="panel scroll" tabindex="0"><h4>A2 · {esc(alt["A2"]["name"])}</h4><table><thead><tr><th>Run</th><th>Burn shift m</th><th>Pulse GJ</th><th>Shield share</th></tr></thead><tbody>{a2}</tbody></table>
 <table><thead><tr><th>Inert loading</th><th>Exhaust km/s</th><th>Mission mass ratio</th></tr></thead><tbody>{plate}</tbody></table><p class="meta">{esc(alt["A2"]["reading"])}</p></div></div>
<div class="scroll" tabindex="0"><table><thead><tr><th>A3 family</th><th>Exhaust km/s</th><th>Maturity</th><th>Nozzle interface</th><th>Mission</th></tr></thead><tbody>{a3}</tbody></table></div>
<p class="meta">{esc(alt["A3"]["reading"])}</p>
<p><b>A4</b> {tag(alt["A4"]["status"])} {esc(alt["A4"]["proposal"])}</p>
<h3>Gates and decision</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Gate</th><th></th><th>Status</th><th>Result</th><th>Limit</th></tr></thead><tbody>{gates}</tbody></table></div>
<p><b>Direction:</b> {esc(P["decision"]["direction"])}</p>
<p class="meta">Evidence file <code>references/evidence/vertex_plasma.json</code> (input hash <code>{esc(P["input_hash"])}</code>), written by
  <code>python3 src/wayfarer/vertex_plasma.py --evidence</code>.</p>
</section>"""


def radiation_section(spec):
    """Section 8 of engineering/vertex/: Engine 1.5 radiation physics, 3D exposure and thermal feasibility, read from
    references/evidence/vertex_radiation.json (written by `python3 src/wayfarer/vertex_radiation.py --evidence`;
    tests/test_vertex_radiation.py fails when it is stale against the inputs)."""
    import json
    p = ROOT / 'references/evidence/vertex_radiation.json'
    if not p.exists():
        return ''
    R = json.loads(p.read_text()); A = R['audit']; S = R['sources']; G = R['geometry']; T = R['thermal']
    pct = lambda v, d=1: '—' if v is None else f'{100*v:,.{d}f} %'
    gw = lambda v: '—' if v is None else (f'{v/1e12:,.1f} TW' if v >= 1e12 else f'{v/1e9:,.1f} GW')
    sci = lambda v: '—' if v is None else f'{v:.2g}'
    cases = S['cases']; ids = list(cases)
    led = ''.join(f'<tr><td><code>{esc(k)}</code> {esc(v["model"])}</td><td class="num">{pct(v["photon_share"])}</td><td class="num">{pct(v["neutron_share"], 2)}</td>'
                  f'<td class="num">{pct(v["ledger"]["gamma_J"]/v["ledger"]["total_J"], 3)}</td><td class="num">{pct(v["ledger"]["charged_J"]/v["ledger"]["total_J"])}</td>'
                  f'<td class="num">{pct(v["ledger"]["jet_J"]/v["ledger"]["total_J"])}</td><td>{"yes" if v["ledger"]["jet_fits"] else "<b>no</b>"}</td>'
                  f'<td class="num">{pct(v["neutron_lines"]["DD_2_45MeV"], 2)} / {pct(v["neutron_lines"]["DT_14_1MeV"], 2)}</td><td class="meta">{esc(v["note"])}</td></tr>'
                  for k, v in cases.items())
    edges = [(b['lo_keV'], b['hi_keV']) for b in cases[ids[0]]['spectrum']]
    spec_rows = ''.join(f'<tr><td class="num">{lo:g}–{hi:g}</td>' + ''.join(f'<td class="num">{pct(cases[k]["spectrum"][j]["share"])}</td>' for k in ids) + '</tr>'
                        for j, (lo, hi) in enumerate(edges))
    sens = ''.join(f'<tr><td>{esc(r["param"])}</td><td class="num">{r["value"]}</td><td class="num">{pct(r["photon_share"])}</td><td class="num">{pct(r["burn_fraction"])}</td>'
                   f'<td class="num">{r["fusion_J"]/1e9:.2f}</td><td class="num">{r["Ti_peak_keV"]:.0f}</td></tr>' for r in R['sensitivity'] if r['model'] == 'R2-B')
    scan = [r for r in R['sensitivity'] if r['model'] == 'R2-A']; tis = sorted({r['value'][0] for r in scan}); rat = sorted({r['value'][1] for r in scan})
    scan_rows = ''.join(f'<tr><td class="num">{ti:g}</td>' + ''.join(f'<td class="num">{pct(next(r["photon_share"] for r in scan if r["value"] == [ti, q]))}</td>' for q in rat) + '</tr>' for ti in tis)
    lad = G['ladder']; ns = sorted(lad, key=int); best = lad[ns[-1]]
    ladder = ''.join(f'<tr><td class="num">{int(n):,}</td><td class="num">{pct(lad[n]["intercepted"], 2)}</td><td class="num">± {pct(lad[n]["stat_error"], 2)}</td></tr>' for n in ns)
    mr = G['mesh_refinement']
    diff = ''.join(f'<tr><td>{esc(d["obstacle"])}</td><td class="num">{pct(d["axisymmetric_1_4"])}</td><td class="num">{pct(d["traced_3d"])}</td></tr>' for d in G['difference'])
    comp = R['components']; ms = R['materials']
    order = sorted(comp, key=lambda g: -comp[g]['sky'])
    crow = ''
    for g in order:
        v = comp[g]
        if v['sky'] <= 0 and not v.get('charged_W'):
            continue
        m = ms.get(g, {}); low = m.get('cases', {}).get('LOW', {})
        ch = v.get('charged_W')
        crow += (f'<tr><td>{esc(g.replace("_", " ").capitalize())}{" · 20 K" if v["cold"] else ""}</td><td class="num">{pct(v["sky"], 2)}</td>'
                 f'<td class="num">{gw(v["photon"]["LOW"]["low"])} – {gw(v["photon"]["LOW"]["high"])}</td>'
                 f'<td class="num">{gw(v["photon"]["NOMINAL"]["low"])} – {gw(v["photon"]["NOMINAL"]["high"])}</td>'
                 f'<td class="num">{gw(v["neutron_upper"]["NOMINAL"])}</td><td class="num">{(gw(ch["low"]) + " – " + gw(ch["high"])) if ch else "—"}</td>'
                 f'<td class="num">{sci(low.get("avg_flux_W_m2"))}</td><td class="num">{sci(low.get("pulse_fluence_J_m2"))}</td>'
                 f'<td>{esc(m.get("pmds") or "—")} {tag(m.get("status", "MATERIAL_LIMIT_OPEN"))}</td></tr>')
    cl = R['cluster']
    clrow = ''.join(f'<tr><td>{esc(k.replace("_", " ").capitalize())}</td><td class="num">{pct(v, 2)}</td><td class="num">{pct(cl["behind_first"].get(k), 2)}</td></tr>' for k, v in cl['first_hit'].items())
    throws = ''
    for cid in ids:
        r = T['cases'][cid]
        throws += (f'<tr><td><code>{esc(cid)}</code></td>' + ''.join(f'<td class="num">{gw(r[k]["four_W"])}<br><span class="meta">{r[k]["ratio"]:,.0f}×</span></td>'
                   for k in ('RADIATION_low', 'RADIATION_high', 'ALL_low', 'ALL_high')) + '</tr>')
    tr = R['treg']
    cand = ''.join(f'<tr><td>{esc(r["name"])}</td><td class="num">{pct(r["intercepted"])}</td><td class="num">{pct(r["absorbed"][0])} – {pct(r["absorbed"][1])}</td>'
                   f'<td class="num">{r["vs_capacity"][0]:,.0f}× – {r["vs_capacity"][1]:,.0f}×</td><td class="num">{r["cold_shielded_vs_capacity"][0]:,.0f}× – {r["cold_shielded_vs_capacity"][1]:,.0f}×</td>'
                   f'<td class="meta">{esc(r["magnetic"])}</td><td class="meta">{esc(r["structural"])}</td><td>{tag("FAIL")}</td></tr>' for r in R['pareto'])
    pl = R['pulse_loading']['NOMINAL']['RADIATION']; sd = R['standoff']
    stand = ''.join(f'<tr><td><code>{esc(k)}</code></td><td class="num">{pct(v["max_shield_fraction"], 3)}</td><td class="num">{v["max_half_angle_deg"]:.1f}°</td>'
                    + ''.join(f'<td class="num">{d:,.0f} m</td>' for d in v['standoff_m'].values()) + '</tr>' for k, v in sd.items())
    alts = ''.join(f'<tr><td><code>{esc(a["id"])}</code> {esc(a["name"])}</td><td>{esc(a["changes"])}</td><td>{esc(a["physics"])}</td><td>{esc(a["maturity"])}</td>'
                   f'<td>{esc(a["verdict"])}</td></tr>' for a in R['alternatives'])
    srs = ''.join(f'<tr><td><code>{esc(x["id"])}</code> {esc(x["quantity"])}</td><td>{esc(x["required"])}</td><td>{esc(x["current"])}</td>'
                  f'<td class="num">{" – ".join(f"{v:,.0f}×" for v in x["factor"])}</td><td>{esc(x["energy"])}; momentum: {esc(x["momentum"])}</td>'
                  f'<td>{esc(x["machinery"])}</td><td>{esc(x["harder"])}</td><td>{esc(x["lore"])}</td></tr>' for x in R['speculative'])
    gates = ''.join(f'<tr><td><code>{esc(g["id"])}</code></td><td>{esc(g["name"])}</td><td>{tag(g["status"])}</td><td>{esc(g["value"])}</td></tr>' for g in R['gates'])
    gp = R['gap']; cs = gp['cold_shielded']; cb = R['combined']; nom = cases['NOMINAL']
    return f"""<section id="radiation"><h2>8 · Radiation and thermal feasibility (Engine {esc(R["version"])})</h2>
<p class="lead">Can the engine keep the radiation its own hardware absorbs within what its materials, cooling and radiators can take, without giving up the
  fusion exhaust? Outcome {tag("OUTCOME_" + R["outcome"])}: no conventional architecture closes; the missing capability is quantified below. Verdict
  {tag(R["verdict"])}, {tag(R["thermal_verdict"])}. The active engine stays <code>M0-NOMINAL</code> with the Engine 1.2 geometry. See also
  <a href="#anatomy">Engine anatomy</a>, <a href="#structure">Structural validation</a>, <a href="#magnet">Magnetic design</a>, <a href="#plasma">Plasma coupling</a>,
  <a href="../weakest-links/">Weakest Links</a> and <a href="../breakthrough-lab/">Breakthrough Lab</a>.</p>
<h3>What Engine 1.4 assumed</h3>
<ul class="plain">{''.join(f'<li>{esc(x)}</li>' for x in A["findings"])}</ul>
<p>So 1.4 booked {pct(A["xray_share"])} of the yield as X-rays ({gw(A["xray_J"]*A["pulse_Hz"])} per engine) and put {pct(A["hardware_sky"])} of it into the hardware.</p>
<h3>Where the fusion energy goes</h3>
<p>The ledger is E<sub>total</sub> = E<sub>charged</sub> + E<sub>photons</sub> + E<sub>gamma</sub> + E<sub>neutrons</sub>, with nothing left unassigned. Photons are
  bremsstrahlung (relativistic, Z<sub>eff</sub> of the fuel); gammas are the 16.4 MeV D-³He branch; neutrons come from D-D side reactions and the tritium they
  breed. {tag("ANALYTIC")} R2-A holds a burn at fixed temperature; {tag("REDUCED_MODEL")} R2-B burns a uniform expanding sphere sized to the demonstrator yield
  (ρR {S["rhoR_solved"]:.0f} g/cm², burn fraction {pct(cases["CONSERVATIVE"]["burn"]["burn_fraction"], 0)}), with ion and electron temperatures, Spitzer
  equilibration and fast-product heating; it runs away to Ti ≈ {cases["CONSERVATIVE"]["burn"]["Ti_peak_keV"]:.0f} keV, where bremsstrahlung wins.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Case</th><th>Photons</th><th>Neutrons</th><th>Gamma</th><th>Charged</th><th>Design jet</th><th>Jet fits</th>
<th>n 2.45 / 14.1 MeV</th><th>Basis</th></tr></thead><tbody>{led}</tbody></table></div>
<p>The 1.4 share sits inside the bracket ({esc(S["verdict_1_4"])}), but the brackets say something sharper: the jet's {pct(A["jet_share"], 0)} leaves room for at most
  {pct(S["photon_room_for_jet"])} photons. Only the idealised hot-ion case fits; a thermal or self-consistent burn radiates more than the design jet allows.
  Literature agrees (thermal D-³He bremsstrahlung is a fifth or more of the fusion power near its optimum).</p>
<div class="grid2"><div class="panel"><h4>Photon spectrum (keV)</h4><table><thead><tr><th>Band</th>{''.join(f"<th>{esc(k)}</th>" for k in ids)}</tr></thead><tbody>{spec_rows}</tbody></table>
 <p class="meta">Mostly 30–1000 keV: hard X-rays that cross centimetres of steel. Neutrons: 2.45 MeV (D-D) and 14.1 MeV (bred D-T); a transport code is needed
 for their deposition, so the neutron rows below are an upper bound (all intercepted energy stays in the first part) with their own geometry, not the photon sky.</p></div>
<div class="panel"><h4>R2-A photon / fusion power</h4><table><thead><tr><th>Ti keV</th>{''.join(f"<th>Te/Ti {q:g}</th>" for q in rat)}</tr></thead><tbody>{scan_rows}</tbody></table></div></div>
<div class="scroll" tabindex="0"><table><thead><tr><th>R2-B change</th><th>Value</th><th>Photons</th><th>Burn fraction</th><th>Yield GJ</th><th>Peak Ti keV</th></tr></thead><tbody>{sens}</tbody></table></div>
<p class="meta">A photon share above 100 % means the target did not ignite: the radiation carries off the heat it started with. The design yield needs the
  ρR the R2-B case solves for; at lower ρR the yield falls with it.</p>
<h3>True 3D exposure</h3>
<p>{tag("RAY_TRACED")} Rays from the burn point through the engine's own {G["parts"]} part meshes ({G["triangles"]:,} triangles, the ones Blender builds),
  every crossing recorded: closed solids pair into entry and exit, open shells count their thickness. Validated on a sphere, a torus band, a slab, an open
  shell and a translated scene (tests). {pct(best["intercepted"])} of the sky meets hardware, against {pct(G["legacy_hardware"])} in 1.4: the eight cage longerons
  are bars, not a surface of revolution. Doubling every mesh's facets changes it by {mr["difference"]:+.2%}.</p>
<div class="grid2"><div class="panel"><table><thead><tr><th>Rays</th><th>Intercepted</th><th>Statistical</th></tr></thead><tbody>{ladder}</tbody></table></div>
<div class="panel"><table><thead><tr><th>1.4 obstacle</th><th>1.4 axisymmetric</th><th>1.5 traced</th></tr></thead><tbody>{diff}</tbody></table></div></div>
<p>Across the four-engine cluster (engine N1's burn point, ship frame, radiator blades on their planes):</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>First owner hit</th><th>Share of sky</th><th>Reached next, behind the first</th></tr></thead><tbody>{clrow}</tbody></table></div>
<h3>Absorption, by energy</h3>
<p>{tag("BRACKETED")} Interception is not deposition. The low bound keeps only Compton (Klein-Nishina) energy transfer and lets scattered photons leave;
  the high bound puts every intercepted photon's energy in the first part (the photoelectric limit, 1.4's rule). For the NOMINAL spectrum the engine absorbs
  {pct(R["transport"]["nominal"]["low"])} – {pct(R["transport"]["nominal"]["high"])} of the photon energy; {pct(R["transport"]["nominal"]["scattered"])} scatters
  and {pct(R["transport"]["nominal"]["transmitted"])} passes through. Photoelectric and pair cross sections need reference data this build could not load
  (xraylib not installed, NIST XCOM not reachable); Geant4 and OpenMC are free and named as the next step, not run.</p>
<h3>Component loads (per engine)</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Group</th><th>Sky</th><th>Photons LOW</th><th>Photons NOMINAL</th><th>Neutrons ≤</th><th>Charged (1.4)</th>
<th>Peak W/m² (LOW)</th><th>J/m² per pulse</th><th>Material</th></tr></thead><tbody>{crow}</tbody></table></div>
<p class="meta">Pulse versus steady load: per-pulse fluence is the average flux divided by {A["pulse_Hz"]:.0f} Hz. A tungsten plasma-facing component takes about
  10 MW/m² steady; the burn armour's peak is several hundred times that even at the LOW source.</p>
<h3>Heat rejection, four engines</h3>
<p>The installed hot radiator rejects {gw(T["capacity_W"])} at 1800 K (both faces, view factor 0.9), with nothing reserved for the ship's own hot loads. Cold
  heat at 20 K costs {1/T["cop"]:,.0f} W of radiator per watt lifted (30 % of Carnot). Radiation only, then with 1.4's charged-plasma and eddy heat:</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Source</th><th>Radiation, low</th><th>Radiation, high</th><th>All, low</th><th>All, high</th></tr></thead><tbody>{throws}</tbody></table></div>
<ul class="plain">
 <li><b>T0</b> radiators alone: {tr["T0"]["ratio"]:,.0f}× the ship's whole radiator area for one engine's most favourable load.</li>
 <li><b>T1</b> heat out with hydrogen: {esc(tr["T1"]["verdict"])}</li>
 <li><b>T2</b> conversion: {esc(tr["T2"]["verdict"])}</li>
 <li><b>T3</b> storage: the whole engine heated by {tr["T3"]["dT_K"]:.0f} K holds {tr["T3"]["seconds"]*1e3:.1f} ms of that heat. Storage is not closure.</li></ul>
<h3>Radiation-aware candidates</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Candidate</th><th>Intercepted</th><th>Absorbed</th><th>Radiator ×</th><th>Coils shielded ×</th><th>Magnetic</th>
<th>Structure</th><th>Verdict</th></tr></thead><tbody>{cand}</tbody></table></div>
<p>NOMINAL photons only, neutrons and charged heat left out, which favours every row. A5 (less power): at the installed radiator the engines could run at
  {pct(pl["power_factor"][1], 2)} of design power with the most favourable bracket; thrust falls and burn time grows {1/pl["power_factor"][1]:,.0f}×.</p>
<h3>Other architectures</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Alternative</th><th>Changes</th><th>Physics</th><th>Maturity</th><th>Verdict</th></tr></thead><tbody>{alts}</tbody></table></div>
<div class="scroll" tabindex="0"><table><thead><tr><th>Pusher standoff</th><th>Shield sky share allowed</th><th>Half angle</th><th>D for r 37 m</th><th>D for r 6.5 m</th></tr></thead><tbody>{stand}</tbody></table></div>
<h3>The speculative gap</h3>
<p>For four engines to fit the radiators even with neutrons and charged heat at zero and the most favourable transport bound, photons may be at most
  {pct(cs["photon_share_needed"], 2)} of the yield (cold parts behind a perfect warm shield; {pct(gp["as_drawn"]["photon_share_needed"], 3)} as drawn). The source
  bracket is {cs["factor_low"]:,.0f}–{cs["factor_high"]:,.0f}× above it, and the lowest point of the plasma scan (Ti {gp["scan_min"]["Ti_keV"]:g} keV, Te/Ti
  {gp["scan_min"]["Te_over_Ti"]:g}) is still {gp["scan_min"]["factor"]:.0f}× above. The best conventional combination (no structure, burn point 6 m aft, coils
  shielded) needs {cb["vs_capacity"][0]:,.0f}× the radiator.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Requirement</th><th>Needed</th><th>Now</th><th>Gap</th><th>Energy and momentum</th><th>Machinery</th><th>Harder</th><th>Lore</th></tr></thead>
<tbody>{srs}</tbody></table></div>
<p class="meta">Recorded as requirements for the <a href="../breakthrough-lab/">Breakthrough Lab</a>; none is canon, and none is assigned to Fiji technology.</p>
<h3>Gates and decision</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Gate</th><th></th><th>Status</th><th>Result</th></tr></thead><tbody>{gates}</tbody></table></div>
<p class="meta">Evidence file <code>references/evidence/vertex_radiation.json</code> (input hash <code>{esc(R["input_hash"])}</code>), written by
  <code>python3 src/wayfarer/vertex_radiation.py --evidence</code> in {R["cost"]["wall_s"]:.0f} s ({R["cost"]["workers"]} workers, peak {R["cost"]["peak_rss_MB"]:.0f} MB).</p>
</section>"""


def fiji_section(spec):
    """Section 9 of engineering/vertex/: Engine 1.6 Fiji-assisted advanced fusion and nanomaterials, read from
    references/evidence/vertex_fiji.json (written by `python3 src/wayfarer/vertex_fiji.py --evidence`; tests/test_vertex_fiji.py fails when
    it is stale against the inputs). Research only: nothing here changes the engine."""
    import json
    p = ROOT / 'references/evidence/vertex_fiji.json'
    if not p.exists():
        return ''
    R = json.loads(p.read_text()); F = R['field']; A = R['assembly']; B = R['rebco']; U = R['fusion']; c = spec['vertex_fiji']
    pct = lambda v, d=1: '—' if v is None else f'{100*v:,.{d}f} %'
    gw = lambda v: '—' if v is None else (f'{v/1e12:,.2f} TW' if abs(v) >= 1e12 else f'{v/1e9:,.1f} GW' if abs(v) >= 1e9 else f'{v/1e6:,.1f} MW')
    sci = lambda v: '—' if v is None else f'{v:.2g}'
    x = lambda v: f'{v:,.0f}×' if v >= 10 else f'{v:,.1f}×'
    cur = ''.join(f'<tr><td class="num">{r["T_K"]}</td><td class="num">{r["heating_mu0M_T"]:.2f}</td><td class="num">{r["cooling_mu0M_T"]:.2f}</td>'
                  f'<td>{esc(r["state"].lower())}</td><td class="num">{r["canon_A_B"]:.1f}</td></tr>' for r in R['model']['curve'] if r['T_K'] % 100 == 0)
    th = R['model']['thermodynamics'][1]
    tg = ''
    for name, t in F['targets'].items():
        for sec, v in t['cases'].items():
            tg += (f'<tr><td>{esc(name)}</td><td class="num">{abs(t["B_coil_T"]):.2f} T</td><td>liners {esc(sec)} m</td><td class="num">{v["G_optimal"]:.4f}</td>'
                   f'<td class="num">{v["G_axial"]:+.4f}</td><td class="num">{1e3*v["B_fiji_T"][2]:.1f}–{1e3*v["B_fiji_T"][0]:.1f} mT</td><td class="num">{v["mu0Ms_for_canon_T"]:,.0f} T</td></tr>')
        for ro, v in t['shell'].items():
            tg += (f'<tr><td>{esc(name)}</td><td class="num">{abs(t["B_coil_T"]):.2f} T</td><td>solid shell {c["bound_inner_m"]:g}–{esc(ro)} m (bound)</td><td class="num">{v["G"]:.2f}</td>'
                   f'<td class="num">—</td><td class="num">{v["B_fiji_T"]:.1f} T</td><td class="num">{v["mu0Ms_for_canon_T"]:,.0f} T</td></tr>')
    ln = ''.join(f'<tr><td>{esc(k)}</td><td class="num">{v["R_m"]:.2f}</td><td class="num">{v["mass_kg"]/1e3:,.1f} t</td><td class="num">{v["force_x_N"]/1e6:+.2f}</td>'
                 f'<td class="num">{v["force_r_N"]/1e6:+.2f}</td><td class="num">{v["hoop_stress_Pa"]/1e6:.1f}</td><td class="num">{v["interaction_J"]/1e6:+.1f}</td></tr>' for k, v in F['liners'].items())
    rb = ''.join(f'<tr><td>{esc(r["coil"])}</td><td class="num">{r["B_peak_T"]:.1f}</td><td class="num">{r["J_op_A_m2"]/1e6:.1f}</td>'
                 f'<td class="num">{min(r["margin"]):.1f}–{max(r["margin"]):.1f}×</td><td class="num">{min(r["apc_margin"]):.0f}–{max(r["apc_margin"]):.0f}×</td>'
                 f'<td class="num">{r["fiji_dB_T"]*1e3:.0f} mT</td><td class="num">{sci(r["fluence_rate_n_m2s"])}</td>'
                 f'<td class="num">{min(r["lifetime_s"]):.0f}–{max(r["lifetime_s"]):.0f} s</td></tr>' for r in B['rows'])
    pol = ''.join(f'<tr><td>{["optimistic", "nominal", "pessimistic"][r["k"]]}</td><td class="num">×{r["factor"]:.3f}</td><td class="num">{r["dd"]:g}</td>'
                  f'<td class="num">{pct(r["photon_share"])}</td><td class="num">{pct(r["neutron_share"], 2)}</td></tr>' for r in U['polarization'])
    etas = list(U['floor']); tis = [r['Ti_keV'] for r in U['floor'][etas[0]]]
    fl = ''.join(f'<tr><td class="num">{ti:g}</td>' + ''.join(f'<td class="num">{pct(U["floor"][e][i]["photon_share"])}<br><span class="meta">Te/Ti {U["floor"][e][i]["Te_over_Ti"]:.2f}</span></td>' for e in etas)
                 + f'<td class="num">{pct(U["floor_polarized"][i]["photon_share"])}</td></tr>' for i, ti in enumerate(tis))
    cp = ''.join(f'<tr><td><code>{esc(r["case"])}</code></td><td class="num">×{r["pol"]:.2f}</td><td class="num">{r["dd"]:g}</td><td class="num">{r["channel"]:g}</td>'
                 f'<td class="num">{r["rhoR_g_cm2"]:.0f}</td><td class="num">{pct(r["photon_share"])}</td><td class="num">{r["Te_peak_keV"]:.0f}</td><td class="num">{r["Ti_peak_keV"]:.0f}</td></tr>' for r in U['coupled'])
    mats = ''.join(f'<tr><td>{esc(m["material"])}</td><td>{esc(m["use"])}</td><td>{esc(m.get("level", ""))}</td>' + ''.join(
        f'<td class="num">{esc(m[k] if isinstance(m[k], str) else (f"{m[k][0]:g}–{m[k][1]:g}" if isinstance(m[k], list) else f"{m[k]:g}"))}</td>'
        for k in ('max_service_temperature', 'thermal_conductivity', 'yield_strength', 'density')) + '</tr>' for m in R['materials'])
    var = ''
    for v in R['variants']:
        e = v['per_engine']; need = v['sr1_photon_share_needed']
        var += (f'<tr><td><code>{esc(v["id"])}</code> {esc(v["name"])}</td><td class="num">{pct(v["photon_share"])}</td><td class="num">{pct(v["neutron_share"], 2)}</td>'
                f'<td class="num">{gw(e["exhaust_W"])}<br><span class="meta">{e["thrust_N"]/1e6:.3f} MN</span></td><td class="num">{gw(e["hardware_W"])}</td>'
                f'<td class="num">{gw(e["refrigeration_W"])}</td><td class="num">{gw(e["hot_radiator_W"])}</td>'
                f'<td class="num">{x(v["ratio"][0])} – {x(v["ratio"][1])}</td><td class="num">{pct(need, 3) if need else "none: fixed loads exceed"}</td>'
                f'<td>{tag("FAIL") if not v["closes"] else tag("PASS")}</td></tr>')
    h2 = R['hydrogen']; hy = ''.join(f'<li>{c_["enthalpy_J_kg"]/1e6:.0f} MJ/kg: {c_["mdot_kg_s"]:,.0f} kg/s, {c_["mass_kg"]/1e9:,.1f} Mt over the four burns, exhaust '
                                      f'{c_["v_exhaust_m_s"]/1e3:.1f} km/s</li>' for c_ in h2['cases'])
    rec = ''.join(f'<tr><td style="white-space:nowrap"><code>{esc(r["id"])}</code></td><td>{esc(r["canon"])}</td><td>{esc(r["proposal"])}</td><td class="meta">{esc(r["destination"])}</td></tr>' for r in R['reconciliation'])
    gates = ''.join(f'<tr><td style="white-space:nowrap"><code>{esc(g["id"])}</code></td><td>{esc(g["name"])}</td><td>{tag(g["status"])}</td><td>{esc(g["value"])}</td></tr>' for g in R['gates'])
    ar = R['armour']; sh = R['shielding']['rows']; ins = R['insulation']
    f0 = next(v for v in R['variants'] if v['id'] == 'F0'); f6 = next(v for v in R['variants'] if v['id'] == 'F6')
    return f"""<section id="fiji"><h2>9 · Fiji-assisted advanced fusion and nanomaterials (Engine {esc(R["version"])})</h2>
<p class="lead">Can Fiji's one extraordinary property, magnetization that rises with temperature, together with nanoengineered materials and advanced fusion
  physics, close the radiation and heat balance that Engine 1.5 failed? Outcome {tag(R["outcome"])}: no configuration closes. The four independent engines stay,
  the released engine and its geometry are unchanged, and nothing on this page is canon. The best integrated case still needs {x(f6["ratio"][0])} the radiator
  (Engine 1.5: {x(f0["ratio"][0])}). See also <a href="#radiation">Radiation and thermal feasibility</a> and <a href="../breakthrough-lab/">Breakthrough Lab</a>.</p>
<h3>Fiji as a material</h3>
<p>{tag("CANON_WORKING")} The temperature shape is the Fiji workbook's lattice law: activation {c["T_activation_K"]:g} K, saturation {c["T_saturation_K"]:g} K,
  release on cooling {c["T_release_K"]:g} K, quench {c["T_quench_K"]:g} K, A<sub>max</sub> {c["A_max"]:g}. Here A is the ratio of hot to cold magnetization, not a
  field multiplier. M = M<sub>s</sub>(T, S) tanh(B<sub>seed</sub>/B<sub>align</sub>): bounded, zero without a seed field, hysteretic, collapsing at quench and
  beyond a {pct(c["strain_limit"], 1)} strain. {tag("PROTOTYPE")} μ<sub>0</sub>M<sub>s</sub> is held at or below about {c["mu0_Ms_T"][0]:g} T, the atomic-moment bound of ordinary
  matter, because a larger value would be a second extraordinary property. The Maxwell relation makes Fiji inversely magnetocaloric: switching on the seed field absorbs
  {th["isothermal_heat_J_m3"]/1e6:,.1f} MJ/m³ at 1000 K, and the seed circuit supplies {th["seed_work_J_m3"]/1e6:,.1f} MJ/m³ of work, which comes back on collapse.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>T (K)</th><th>μ₀M heating (T)</th><th>μ₀M cooling (T)</th><th>State</th><th>Canon A_B</th></tr></thead><tbody>{cur}</tbody></table></div>
<h3>Field from currents plus magnetization</h3>
<p>{tag("ANALYTIC")} The field a magnetized volume adds at a point is the exact dipole-kernel integral. With every cell oriented the best possible way (a ceiling for
  nanofabricated orientation, here at {pct(F["efficiency"], 0)} for texture and {c["orientation_segments"]} segments), B = μ<sub>0</sub>M<sub>s</sub>·G. A solid spherical
  shell gives G = 1.38 ln(r<sub>o</sub>/r<sub>i</sub>); a uniformly axial liner gives almost nothing, because geometry, not the material, sets the field. The canon law
  ({c["canon_seed_T"]:g} T × {F["canon_A_B"]:.1f} = {F["canon_field"]["B_T"]:.0f} T) would need the magnetization in the last column.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Target</th><th>Coil field</th><th>Fiji volume</th><th>G optimal</th><th>G axial</th><th>Fiji adds</th><th>μ₀M<sub>s</sub> for canon</th></tr></thead><tbody>{tg}</tbody></table></div>
<p>Liner forces at the atomic bound (per engine, nominal {A["liner_section_m"]:g} m liners), reacted through warm struts:</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Liner</th><th>R (m)</th><th>Mass</th><th>F<sub>x</sub> (MN)</th><th>F<sub>r</sub> (MN)</th><th>Hoop (MPa)</th><th>Interaction (MJ)</th></tr></thead><tbody>{ln}</tbody></table></div>
<p class="meta">At the canon field the throat region would hold {F["canon_field"]["energy_J"]/1e9:,.0f} GJ at {F["canon_field"]["pressure_Pa"]/1e9:.1f} GPa, which takes at least
  {F["canon_field"]["virial_mass_kg"]/1e3:,.0f} t of titanium structure (virial bound).</p>
<h3>The lattice assembly</h3>
<p>The isolation stack between the {c["T_operating_K"]:g} K liner and the 20 K windings works: {c["foil_layers"]} refractory foils pass {A["radiative_W_m2"]:.0f} W/m²
  to a {c["intermediate_K"]:g} K shield, MLI the rest. What does not work is the liner's own heat. Field ripple at the pulse rate costs {gw(A["hysteresis_W"])} of hysteresis
  per engine, and in the line of sight of the burn the inboard face takes {sci(A["inboard_flux_W_m2"][0])}–{sci(A["inboard_flux_W_m2"][1])} W/m², which is
  {A["vs_armour"][0]:.0f}–{A["vs_armour"][1]:.0f}× what a cooled 5 mm tungsten face carries. The lattice would pass quench and collapse.</p>
<h3>REBCO</h3>
<p>{tag("LITERATURE_RANGE")} Critical current is not the limit. Scaled from the demonstrated 20 T, 20 K point, each coil runs with several times margin, and APC tape
  (PMDS Level B) adds more. Fast neutrons are the limit: with only the drawn cryostat, the closure coils reach a typical REBCO fluence limit within seconds of a
  {c["burn_time_s"]/86400:.1f}-day burn. That needs about {B["attenuation_needed"]:.0e} attenuation (≈ {B["shield_m"]:.1f} m of shield) inside a cryostat about half a metre thick.
  Stored energy {B["stored_J"]/1e9:.2f} GJ per engine.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Coil</th><th>B peak (T)</th><th>J (A/mm²)</th><th>Jc margin</th><th>APC margin</th><th>Fiji adds</th><th>n/m²/s</th><th>To fluence limit</th></tr></thead><tbody>{rb}</tbody></table></div>
<h3>Advanced fusion</h3>
<p>{tag("THEORETICAL")} Spin polarization raises σ(D-³He) by at most 1.5× for fully parallel spins that survive to burn. Fiji does not preserve polarization.
  Polarizing the fuel costs about {gw(U["polarization_power_W"])} per engine, which is small.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Polarization</th><th>σ factor</th><th>D-D factor</th><th>Photons</th><th>Neutrons</th></tr></thead><tbody>{pol}</tbody></table></div>
<p>{tag("ANALYTIC")} Hot ions and cool electrons cannot be held by choice. Electron-ion exchange heats the electrons faster the colder they are, so a burn at
  T<sub>i</sub> has a floor where exchange plus product heating equals bremsstrahlung. Energy channeling (sending the products' electron share to ions) lowers the floor
  but cannot remove exchange. The best sustained floor is {pct(U["best_floor_polarized"]["photon_share"])} of the yield (polarized, channelled). That is above
  Engine 1.5's LOW case ({pct(U["reference"]["photon_share"])}), which holds T<sub>e</sub>/T<sub>i</sub> 0.5 by assumption. The channeling drive itself
  costs {gw(U["channel_cost_W"][0])}–{gw(U["channel_cost_W"][2])} per engine.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Ti keV</th>{''.join(f"<th>channel {esc(e)}</th>" for e in etas)}<th>polarized + 0.9</th></tr></thead><tbody>{fl}</tbody></table></div>
<p>{tag("REDUCED_MODEL")} The 1.5 R2-B burn with the levers inside it. It is a pulse, not a held state: the electrons heat up and the photon share is time-integrated.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Burn</th><th>σ</th><th>D-D</th><th>Channel</th><th>ρR g/cm²</th><th>Photons</th><th>Te peak keV</th><th>Ti peak keV</th></tr></thead><tbody>{cp}</tbody></table></div>
<h3>Materials</h3>
<p>PMDS values only. Speculative (Level C) data never feeds a number; Level B variants carry no number until measured. Radiation tolerance and heat removal are
  different things. A 5 mm W face from its {ar["T_limit_K"]:g} K service limit to an {ar["coolant_K"]:g} K coolant carries {ar["q_max_W_m2"]/1e6:.0f} MW/m², and the 1.5
  peak is {ar["shortfall"]:.0f}× that. Shields keep their heat: at {sh[0]["T_K"]:g} K a hydride shield's heat costs {1+1/sh[0]["cop"]:.1f} W of radiator per watt, and at a
  polymer's {sh[1]["T_K"]:g} K it costs {1+1/sh[1]["cop"]:.1f} W. A nanophotonic radiator at emissivity {c["radiator_emissivity_nano"]} adds
  {pct(R["radiator"]["capacity_gain"])} capacity. Tank insulation leaks are {ins["aerogel_mli_W_m2"][0]}–{ins["aerogel_mli_W_m2"][2]} W/m², which is real for boil-off and
  irrelevant to closure.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Material</th><th>Use</th><th>Level</th><th>Service K</th><th>k W/(m K)</th><th>Yield Pa</th><th>kg/m³</th></tr></thead><tbody>{mats}</tbody></table></div>
<h3>Hydrogen reaction mass</h3>
<p>Heat leaves the ship only if the hydrogen that carries it leaves too. Carrying F6's excess ({gw(h2["excess_W"])} over four engines) takes:</p>
<ul class="plain">{hy}</ul>
<p>Wayfarer departs at about 4.6 kt. Regenerative hydrogen stays a research option for small loads, not this one.</p>
<h3>F0–F6: radiation and thermal closure (per engine, LOW source)</h3>
<p>Each lever runs on its own, then all together in one calculation. Nothing is multiplied, and heat a liner moves is still counted. The radiator column gives the
  four engines' demand over the installed radiator (low and high bracket). The SR-1 column gives the photon share the configuration could tolerate.</p>
<div class="scroll" tabindex="0"><table><thead><tr><th>Configuration</th><th>Photons</th><th>Neutrons</th><th>Exhaust, thrust</th><th>Into hardware</th><th>Refrigeration</th>
<th>Hot radiator load</th><th>Radiator ×</th><th>SR-1 allows</th><th></th></tr></thead><tbody>{var}</tbody></table></div>
<p class="meta">Machine-readable: <code>references/evidence/vertex_fiji.json</code> → <code>variants</code>. A Fiji liner is a shield that runs hot, and an ordinary tungsten
  liner at its own service limit (F1-REF) does better, because Fiji's 1000 K operating point needs a heat pump to reach the 1800 K radiator.</p>
<h3>Canon reconciliation (for owner review; nothing edited)</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th></th><th>Canon</th><th>Proposal</th><th>Destination</th></tr></thead><tbody>{rec}</tbody></table></div>
<h3>Gates</h3>
<div class="scroll" tabindex="0"><table><thead><tr><th>Gate</th><th></th><th>Status</th><th>Result</th></tr></thead><tbody>{gates}</tbody></table></div>
<p class="meta">Evidence file <code>references/evidence/vertex_fiji.json</code> (input hash <code>{esc(R["input_hash"])}</code>), written by
  <code>python3 src/wayfarer/vertex_fiji.py --evidence</code> in {R["cost"]["wall_s"]:.0f} s.</p>
</section>"""


def engine_anatomy(spec, vi):
    """Section 4 of engineering/vertex/: the engine's functional categories from vertex_inspect (the same records Explore Ship inspects),
    each linking to its Weakest Links and Breakthrough Lab records by id (the registries stay on their own pages) and to the viewer."""
    recs = vi.records(spec)
    swatch = lambda rgb: f'<i class="sw" style="background:rgb({",".join(str(round(255 * c)) for c in rgb)})" aria-hidden="true"></i>'
    cards = []
    for c in vi.categories(spec):
        parts = [r for r in recs if r['category'] == c['id']]
        stems = list(dict.fromkeys((r['stem'], r['units']) for r in parts))
        names = ', '.join(f'{esc(vi.display_name(s))}{f" ×{n}" if n > 1 else ""}' for s, n in stems)
        links = ', '.join([f'<a href="../weakest-links/#{w}"><code>{w}</code></a>' for w in c['weakest_links']]
                          + [f'<a href="../breakthrough-lab/#{b}"><code>{b}</code></a>' for b in c['breakthroughs']]) or 'none declared'
        cards.append(f'''<div class="panel anatomy" id="anatomy-{c["id"].lower().replace("_", "-")}">
 <h3>{swatch(c["color"])} {esc(c["title"])} <span class="meta">{c["parts"]} part{"s" if c["parts"] != 1 else ""}</span></h3>
 <p>{esc(c["purpose"])}</p><p><b>How it works:</b> {esc(c["how"])}</p>
 <p class="meta"><b>Physics:</b> {esc(c["physics"])} <b>Speculative:</b> {esc(c["speculative"])} <b>Open:</b> {esc(c["open"])}</p>
 <p class="meta"><b>Interfaces:</b> {", ".join(f"<code>{esc(i)}</code>" for i in c["interfaces"]) or "none"} · <b>Research records:</b> {links}</p>
 <details><summary>Parts</summary><p class="meta">{names}</p></details>
 <p><a href="../../viewer/#view=aft&amp;eng=N1&amp;cat={c["id"]}">Inspect in Explore Ship</a></p></div>''')
    return f"""<section id="anatomy"><h2>4 · Engine anatomy</h2>
<p>The {len(recs)} logical parts of one Compact Vertex Engine in {len(cards)} functional groups. Explore Ship opens the same records: pick an engine,
  a group or a part, and it is highlighted on the model with its material, evidence class and interfaces. The swatches are functional review
  colours, never material colours, and every group is named in text. Masses are {tag("ENGINEERING_PROTOTYPE")} estimates from the drawn volume.</p>
<div class="grid2">{''.join(cards)}</div></section>"""


def vertex_teaser():
    return """<section id="vertex" class="teaser"><div>
    <h2>Vertex propulsion · demonstrator → engine → cluster</h2>
    <p>The drive the ship shows now: one reusable Compact Vertex Engine, four linked copies in a cluster behind the shield, every step with its
      evidence class. A speculative working representation; the research demonstrator stays BLOCKED and the Fiji canon is unchanged.</p>
    <p><a class="go" href="vertex/">Open the propulsion lineage</a> · <a href="breakthrough-lab/">Breakthrough Lab</a></p></div></section>"""


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


def main_page(site, spec, entries, dropped, problem, revision, built, play=True, lab2=None, seq=None, vertex=False):
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
{vertex_teaser() if vertex else ''}
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
    vertex = vertex_page(spec, out / 'vertex', revision, built)
    if vertex:
        pages.append('engineering/vertex/index.html')
    main_page(Path(site), spec, entries, dropped, problem, revision, built, play, lab2, seq, vertex)
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
