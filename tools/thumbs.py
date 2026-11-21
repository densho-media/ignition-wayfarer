#!/usr/bin/env python3
"""WOS thumbnails (docs/WOS.md section 7): the pictures the Overview and the module cards show, made from the project's own
model, renders and simulations, never stock imagery. The finished WebP files are committed in web/thumbs/, so the site build
needs neither Blender nor a browser; run this again when the ship or a simulation changes visibly.

  python3 tools/thumbs.py render                     # Blender stills from the saved assets (existing preview scripts) -> runs/wos-thumbs
  python3 tools/thumbs.py capture runs/<site>        # headless Chrome frames of a built site (viewer, simulations, elevation)
  python3 tools/thumbs.py pack                       # crop, resize and encode into web/thumbs/, with web/thumbs/thumbs.json

Each picture keeps its representation class (wos.THUMBS: model, simulation, schematic, illustrative), shown on its chip."""

import argparse
import base64
import functools
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
SRC = ROOT / 'runs/wos-thumbs'
OUT = ROOT / 'web/thumbs'
BLENDER = os.environ.get('BLENDER', '/snap/bin/blender')

# Blender stills: (output, script, arguments); captions are drawn into the frame and cropped away in pack.
RENDERS = [
    ('entry', 'src/wayfarer/presentation/entry_preview.py', ['--views', 'landing_aisle', '--look', '--size', '960']),
    ('hero', 'src/wayfarer/presentation/hero_preview.py', ['--views', 'brow', '--size', '960', '--samples', '24', '--state', 'COAST']),
]
# Crops in source pixels (left, top, right, bottom) and the sizes written; ratio 16:9 for cards, 3:1 for the Overview band.
CARD, BAND = ((480, 270), (960, 540)), ((960, 320), (1920, 640))
PACK = {
    'ship-side': ('capture/ship-side.png', (330, 120, 1830, 620), BAND, 'Chrome: viewer/, side view, Standard style, interface hidden'),
    'ship-3d': ('capture/ship-3d.png', (360, 170, 1360, 732), CARD, 'Chrome: viewer/, three-quarter view, Standard style, interface hidden'),
    'interior': ('entry/entry_landing_aisle.png', (0, 150, 960, 690), CARD, 'Blender: entry_preview.py landing_aisle --look (ring A aisle, ladder well)'),
    'exterior': ('hero/hero_brow.png', (100, 30, 900, 460), CARD, 'Blender: hero_preview.py brow, COAST (bow shield and forward structure)'),
    'sim-dust': ('capture/sim-dust.png', None, CARD, 'Chrome: engineering/dust/#autostart, stage'),
    'sim-ignition': ('capture/sim-ignition.png', None, CARD, 'Chrome: engineering/ignition/#autostart, overload, stage'),
    'sim-build': ('../../web/engineering/build_preview.jpg', (0, 40, 443, 290), CARD, 'existing build_preview.jpg, left panel (Build sequence page)'),
    'sim-compare': ('../../web/engineering/compare_preview.jpg', None, CARD, 'existing compare_preview.jpg (Compare page)'),
    'sim-lab': ('capture/sim-lab.png', None, CARD, 'Chrome: engineering/breakthrough-lab/, the builder'),
    'engineering': ('capture/eng-subsystems.png', (430, 230, 1410, 781), CARD, 'Chrome: viewer/, three-quarter view, Subsystems style (each '
                    'functional subsystem in its overlay colour), interface hidden'),
}
LIFT = {'exterior': 1.5}
LIMIT = {480: 24_000, 960: 60_000, 1920: 120_000}       # bytes per width (band 960 shares the 960 limit)


def render():
    for out, script, args in RENDERS:
        cmd = [BLENDER, '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(ROOT / script), '--',
               *args, '--out-dir', str(SRC / out)]
        print(' '.join(cmd), flush=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def capture(site, chrome_bin, only=()):
    import web_check as wc
    site = Path(site).resolve()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(wc.Site, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}' + wc.BASE
    out = SRC / 'capture'
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as profile, open(out / 'chrome.log', 'w') as log:
        chrome = wc.Chrome(chrome_bin, profile, log, sandbox=False)
        page = wc.Page(chrome)
        hide = ("const s = document.createElement('style'); s.textContent = '.wos-bar, .wos-sub, .wos-skip, .wos-guide, "
                ".viewer-work > :not(canvas) { display: none !important }'; document.head.append(s);")

        def shot(name, path, w, h, ready, setup='', clip=None, settle=4, top=None):
            if only and name not in only:
                return
            page.send('Emulation.setDeviceMetricsOverride', {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': False})
            page.send('Page.navigate', {'url': url + path})
            if not page.wait(ready, 240):
                raise SystemExit(f'{name}: {path} did not become ready')
            page.js(hide + (setup or ''))
            if top:
                page.js(f'document.querySelector({json.dumps(top)}).scrollIntoView({{block: "start"}})')
            page.frames(settle)
            time.sleep(1)
            params = {'format': 'png'}
            if clip:
                r = page.js(f'(() => {{ const e = document.querySelector({json.dumps(clip)}); e.scrollIntoView({{block: "center"}}); '
                            'const r = e.getBoundingClientRect(); return {x: r.x + scrollX, y: r.y + scrollY, width: r.width, height: r.height}; })()')
                params.update(clip={**r, 'scale': 1}, captureBeyondViewport=True)
            (out / f'{name}.png').write_bytes(base64.b64decode(page.send('Page.captureScreenshot', params, 240)['data']))
            print(name, flush=True)

        viewer = '!!(window.wayfarer && window.wayfarer.model)'
        shot('ship-side', 'viewer/', 1920, 640, viewer, "dispatchEvent(new Event('resize')); window.wayfarer.frame('side');")
        shot('ship-3d', 'viewer/', 1600, 900, viewer, "dispatchEvent(new Event('resize')); window.wayfarer.frame('threequarter');")
        shot('eng-subsystems', 'viewer/', 1600, 900, viewer, "dispatchEvent(new Event('resize')); window.wayfarer.setStyle('subsystem'); "
             "window.wayfarer.frame('threequarter');", settle=12)
        shot('sim-dust', 'engineering/dust/#autostart', 1600, 900, '!!(window.__dust && window.__dust.ready)', '', '#stage', 8)
        shot('sim-ignition', 'engineering/ignition/#autostart', 1600, 900, '!!(window.__ign && window.__ign.ready)',
             'window.__ign.mode("overload"); window.__ign.seek(window.__ign.run.V + 3)', '#stage', 8)
        shot('sim-lab', 'engineering/breakthrough-lab/', 1280, 720, 'document.readyState === "complete"', top='#builder')
        chrome.close()
    server.shutdown()


def pack():
    from PIL import Image
    import wos
    OUT.mkdir(parents=True, exist_ok=True)
    record = {}
    for name, (src, crop, sizes, method) in PACK.items():
        im = Image.open(SRC / src).convert('RGB')
        if crop:
            im = im.crop(crop)
        if name in LIFT:                            # a dark render, lifted for a small card (no change of content)
            from PIL import ImageEnhance
            im = ImageEnhance.Brightness(im).enhance(LIFT[name])
        ratio = sizes[0][0] / sizes[0][1]
        w, h = im.size                              # centre crop to the ratio
        if w / h > ratio:
            nw = round(h * ratio); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w / ratio); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        files = {}
        for tw, th in sizes:
            q = 78
            while True:
                path = OUT / f'{name}-{tw}.webp'
                im.resize((tw, th), Image.LANCZOS).save(path, 'WEBP', quality=q, method=6)
                if path.stat().st_size <= LIMIT[tw] or q <= 40:
                    break
                q -= 6
            files[path.name] = {'bytes': path.stat().st_size, 'quality': q, 'size': [tw, th]}
        record[name] = {'class': wos.THUMBS[name][0], 'alt': wos.THUMBS[name][1], 'method': method,
                        'source_size': list(Image.open(SRC / src).size), 'files': files}
    rev = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / 'thumbs.json').write_text(json.dumps({'contract': 'WF_WOS_THUMBS', 'git_revision': rev, 'thumbs': record}, indent=1) + '\n')
    total = sum(f['bytes'] for r in record.values() for f in r['files'].values())
    print(json.dumps({n: {k: v['bytes'] for k, v in r['files'].items()} for n, r in record.items()}, indent=1), f'\ntotal {total} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('render')
    c = sub.add_parser('capture'); c.add_argument('site', type=Path); c.add_argument('--chrome', default=os.environ.get('CHROME', 'google-chrome')); c.add_argument('--only', nargs='*', default=())
    sub.add_parser('pack')
    a = ap.parse_args()
    {'render': render, 'pack': pack}.get(a.cmd, lambda: capture(a.site, a.chrome, a.only))()


if __name__ == '__main__':
    main()
