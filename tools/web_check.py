"""Browser check of the Wayfarer site: headless Chrome over the DevTools pipe (standard library only).

Serves the site under /ignition-wayfarer/ (the GitHub Pages project path) with software WebGL (SwiftShader) and the cache off,
and walks it as a visitor does, recording every request:
  start      the start page loads only index.html, site.css and release.json: no model, engine or library, no canvas
  viewer     Explore Ship from its link: whole-ship framing, orbit, zoom, pan, reset, presets, picking, the four styles, assembly states,
             Hybrid focus, the picking policy, exported colours, Reset appearance, the #cam and appearance bookmarks, no Enter Wayfarer file
  play       the launcher requests no engine before Start; Start boots Godot and the walk (EXC-001, the main experience) with no viewer
             file, no error
  switching  Exit back to the start page, Explore Ship again; page-renderer memory returns to the start-page level (Chrome runs
             with the back-forward cache off, so this measures what the pages release)
  equivalence  Demonstrator 01's 68-check suite and its whole-journey autoplay recording, drawing off, must match the native build
             of the same package check by check and frame by frame (a second browser, alongside the walk)
  phone      the start page and the viewer at 390 x 844 with one-finger orbit and pinch zoom; the review page renders
  touch      Enter Wayfarer on an emulated phone (844 x 390, DPR 3) played by touch from the welcome to ring A, upright and tablet
             sizes (a third browser, alongside the walk; emulation, not a phone's frame rate)
  touch walk the walk on the same emulated phone: welcome, the 1-D stick down the boarding line to the shut outer hatch, Use opens
             it, a look drag, Map and View (after the touch journey, in the same side browser)
Screenshots, metrics and check.json go to --out; --record writes the summary into the site's release.json. It checks behaviour,
loading isolation and transfer sizes, not frame rates on real hardware. The viewer's camera damping is switched off before input.
--part runs one part (main: start, viewer, play, switching, phone, review; equivalence; touch; walk); CI runs the four on their
own runners and --merge combines their check.json (a missing part fails), recording into release.json with --record.

    python3 tools/web_check.py <site dir> --out <dir> [--chrome google-chrome] [--record] [--part main|equivalence|touch|walk ...]
    python3 tools/web_check.py <site dir> --merge <part out dir> ... --out <dir> [--record]
"""
import argparse
import base64
import fcntl
import functools
import http.server
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

BASE = '/ignition-wayfarer/'


class Site(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.js': 'text/javascript', '.wasm': 'application/wasm', '.glb': 'model/gltf-binary', '.json': 'application/json'}

    def translate_path(self, path):
        if not path.startswith(BASE):
            return '/nonexistent'          # only the project subpath exists, as on GitHub Pages
        return super().translate_path('/' + path[len(BASE):])

    def log_message(self, *args):
        pass


class Chrome:
    """One browser over --remote-debugging-pipe: NUL-terminated JSON messages on fds 3 (in) and 4 (out)."""

    def __init__(self, binary, profile, log, sandbox=True, extra=()):
        to_chrome, from_chrome = os.pipe(), os.pipe()
        child_in, child_out = (fcntl.fcntl(fd, fcntl.F_DUPFD, 10) for fd in (to_chrome[0], from_chrome[1]))

        def fds():
            os.dup2(child_in, 3); os.dup2(child_out, 4)
        args = [binary, '--headless=new', '--remote-debugging-pipe', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                '--ignore-gpu-blocklist', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
                f'--user-data-dir={profile}', '--window-size=1280,800', *([] if sandbox and os.geteuid() else ['--no-sandbox']), *extra, 'about:blank']
        self.process = subprocess.Popen(args, pass_fds=(3, 4, child_in, child_out), preexec_fn=fds,
                                        stdout=log, stderr=log)
        for fd in (to_chrome[0], from_chrome[1], child_in, child_out):
            os.close(fd)
        self.out, self.inp = to_chrome[1], from_chrome[0]
        self.next_id, self.replies, self.events = 0, {}, queue.Queue()
        self.lock = threading.Condition()
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        buffer = b''
        while chunk := os.read(self.inp, 1 << 16):
            buffer += chunk
            *messages, buffer = buffer.split(b'\0')
            for raw in messages:
                message = json.loads(raw)
                if 'id' in message:
                    with self.lock:
                        self.replies[message['id']] = message
                        self.lock.notify_all()
                else:
                    self.events.put(message)

    def send(self, method, params=None, session=None, timeout=60):
        with self.lock:
            self.next_id += 1
            ident = self.next_id
        os.write(self.out, json.dumps({'id': ident, 'method': method, 'params': params or {},
                                       **({'sessionId': session} if session else {})}).encode() + b'\0')
        with self.lock:
            if not self.lock.wait_for(lambda: ident in self.replies, timeout):
                raise TimeoutError(method)
            reply = self.replies.pop(ident)
        if 'error' in reply:
            raise RuntimeError(f'{method}: {reply["error"]}')
        return reply['result']

    def close(self):
        self.process.kill()
        self.process.wait()


class Page:
    def __init__(self, chrome):
        self.chrome = chrome
        target = chrome.send('Target.createTarget', {'url': 'about:blank'})['targetId']
        self.session = chrome.send('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        for domain in ('Page', 'Runtime', 'Network'):
            self.send(f'{domain}.enable')

    def send(self, method, params=None, timeout=60):
        return self.chrome.send(method, params, self.session, timeout)

    def js(self, expression, timeout=60):
        result = self.send('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True}, timeout)
        if 'exceptionDetails' in result:
            raise RuntimeError(f'{expression[:80]}: {result["exceptionDetails"]}')
        return result['result'].get('value')

    def wait(self, expression, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                if self.js(expression):
                    return True
            except (RuntimeError, TimeoutError):   # the previous page is still showing, or the next one is mid-navigation
                pass
            time.sleep(0.25)
        return False

    def frames(self, n=2):
        """Let the render loop run (software WebGL on a CI runner can take seconds per frame)."""
        self.js(f'new Promise(r => {{ let k = {n}; const f = () => --k ? requestAnimationFrame(f) : r(1); requestAnimationFrame(f); }})', timeout=180)

    def mouse(self, kind, x, y, button='none', buttons=0, **extra):
        self.send('Input.dispatchMouseEvent', {'type': kind, 'x': x, 'y': y, 'button': button, 'buttons': buttons, **extra})

    def drag(self, start, end, button='left', steps=3):
        mask = {'left': 1, 'right': 2, 'middle': 4}[button]
        self.mouse('mouseMoved', *start)
        self.mouse('mousePressed', *start, button=button, buttons=mask, clickCount=1)
        for i in range(1, steps + 1):
            t = i / steps
            self.mouse('mouseMoved', start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t, button=button, buttons=mask)
        self.mouse('mouseReleased', *end, button=button, buttons=0, clickCount=1)

    def click(self, x, y):
        self.mouse('mouseMoved', x, y)
        self.mouse('mousePressed', x, y, button='left', buttons=1, clickCount=1)
        self.mouse('mouseReleased', x, y, button='left', buttons=0, clickCount=1)

    def touch(self, kind, points):
        self.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in enumerate(points)]})

    def screenshot(self, path, timeout=240):
        # A capture waits for the next compositor frame; a software-rendered Godot frame on a runner that also runs the touch
        # journey's browser can take minutes (main run 66 timed out twice at 60 s). Screenshots are evidence, not checks.
        Path(path).write_bytes(base64.b64decode(self.send('Page.captureScreenshot', {'format': 'png'}, timeout)['data']))

    def centre_of(self, selector):
        return self.js(f'(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); '
                       f'return [r.x + r.width / 2, r.y + r.height / 2]; }})()')


# WEB-004 viewer checks (window.wayfarer exposes the records, the resolved states and the state).
details = lambda result: {k: v for k, v in result.items() if k != 'ok'}
SNAPSHOT = ('(() => { const w = window.wayfarer; let h = 0, mats = 0, vis = 0, n = 0, lines = 0; w.model.traverse(o => { '
            'if (o.isLineSegments) lines++; if (!o.isMesh) return; n++; o.updateMatrixWorld(); '
            'h += o.matrixWorld.elements.reduce((a, x, i) => a + x * (i + 1), 0); if (o.material === o.userData.material) mats++; '
            'if (o.visible === o.userData.visible) vis++; }); return {style: w.style(), meshes: n, transform_sum: +h.toFixed(2), '
            'original_materials: mats, original_visibility: vis, added_lines: lines}; })()')
STYLED = ('(() => { const w = window.wayfarer; let wrong = 0, n = 0; for (const r of w.records) for (const m of r.meshes) { if (!m.visible) continue; n++; '
          "const solid = m.material === m.userData.material; const want = ['standard', 'hybrid'].includes('{style}') ? solid : m.material.isShaderMaterial; "
          'if (!want) wrong++; } return {meshes: n, wrong}; })()')
TINTS = ('(() => { const w = window.wayfarer, h = w.holo(); let checked = 0, wrong = 0; for (const r of w.records) { if (r.res.state !== "HOLOGRAM") continue; '
         'const c = h.nodes[r.id] ?? "CTX"; const sid = Array.isArray(c) ? c[0] : c; const rgb = Array.isArray(c) ? c[1] : h.subsystems.find(s => s.id === sid).color; '
         'const want = w.srgb(rgb), got = r.meshes[0].material.uniforms.tint.value; checked++; '
         'if (Math.abs(want.r - got.r) + Math.abs(want.g - got.g) + Math.abs(want.b - got.b) > 1e-6 || sid !== r.sid) wrong++; } return {checked, wrong}; })()')
HYBRID_FOCUS = ('(() => { const w = window.wayfarer, r = w.selected(), f = w.state.focus; if (!r) return {selected: false, ok: false}; '
                'const ctx = w.records.filter(x => x !== r && x.res.state !== "HIDDEN"); '
                'return {selected: r.id, focus: f, ok: !!f && f.kind === "node" && f.id === r.id && r.res.state === "SOLID" '
                '&& r.meshes.every(m => m.material === m.userData.material) && ctx.every(x => x.res.state === "GHOST")}; })()')
KEEPS_OVERRIDES = ('(async () => { const w = window.wayfarer, other = [...w.groups.keys()].find(a => a !== w.selected().assembly); '
                   'await w.update(s => { s.overrides.set("a:" + other, "HOLOGRAM"); }); '
                   'for (const r of [w.records[10], w.records[200], w.records[1000]]) w.select(r.node || r.id); '
                   'await new Promise(res => setTimeout(res, 300)); '
                   'const ok = w.state.overrides.get("a:" + other) === "HOLOGRAM" && w.records.filter(r => r.assembly === other).every(r => r.res.state === "HOLOGRAM"); '
                   'await w.update(s => { s.overrides.delete("a:" + other); }); return {assembly: other, ok}; })()')
HIDDEN_PICK = ('(async () => { const w = window.wayfarer; await w.update(s => { s.focus = null; }); const before = w.pickAt({x}, {y}); if (!before) return {ok: false}; '
               'await w.update(s => { s.overrides.set("a:" + before.assembly, "HIDDEN"); }); const after = w.pickAt({x}, {y}); '
               'await w.update(s => { s.overrides.delete("a:" + before.assembly); }); '
               'return {hidden_assembly: before.assembly, picked_after: after && after.id, ok: !after || after.assembly !== before.assembly}; })()')
GHOST_PICK = ('(async () => { const w = window.wayfarer, T = w.THREE; '
              'await w.update(s => { s.focus = {kind: "assembly", id: "Assembly_PROPULSION001"}; }); w.frameSelection(); '
              'const subject = w.records.filter(r => r.assembly === "Assembly_PROPULSION001"); const box = new T.Box3(); '
              'for (const r of subject) for (const m of r.meshes) box.expandByObject(m); '
              'const sx = [], sy = []; for (let i = 0; i < 8; i++) { const v = new T.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, '
              'i & 4 ? box.max.z : box.min.z).project(w.camera); sx.push((v.x + 1) / 2 * innerWidth); sy.push((1 - v.y) / 2 * innerHeight); } '
              'const rc = new T.Raycaster(); let tested = 0, bad = 0; '
              'for (let i = 1; i < 14; i++) for (let j = 1; j < 14; j++) { '
              'const x = Math.min(...sx) + (Math.max(...sx) - Math.min(...sx)) * i / 14, y = Math.min(...sy) + (Math.max(...sy) - Math.min(...sy)) * j / 14; '
              'rc.setFromCamera(new T.Vector2(x / innerWidth * 2 - 1, -(y / innerHeight) * 2 + 1), w.camera); '
              'const hits = rc.intersectObject(w.model, true).filter(h => h.object.isMesh && h.object.visible); const rec = h => w.recordOf(h.object); '
              'if (!hits.length || rec(hits[0])?.res.state !== "GHOST" || !hits.some(h => rec(h)?.res.state !== "GHOST")) continue; '
              'tested++; const p = w.pickAt(x, y); if (!p || p.res.state === "GHOST") bad++; } '
              'await w.update(s => { s.focus = null; }); w.frame("threequarter"); '
              'return {points_with_ghost_in_front: tested, wrong: bad, ok: tested > 0 && bad === 0}; })()')
CAMERA = ('(() => { const w = window.wayfarer, c = w.camera, t = w.controls.target; '
          'return {p: c.position.toArray(), t: t.toArray(), d: c.position.distanceTo(t)}; })()')
# The whole ship's bounding box corners in normalized device coordinates: framed when all are on screen and one axis is mostly filled.
FRAMING = ('(() => { const w = window.wayfarer, b = w.box, v = new w.camera.position.constructor(); let x = 0, y = 0;'
           'for (let i = 0; i < 8; i++) { v.set(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z)'
           '.project(w.camera); x = Math.max(x, Math.abs(v.x)); y = Math.max(y, Math.abs(v.y)); } return [x, y]; })()')


def moved(a, b, key):
    return math.dist(a[key], b[key]) if key in 'pt' else abs(a[key] - b[key])


def rss(pid, kind=None):
    """Summed resident memory (MB) of a process and all its descendants, from /proc (Linux); kind='renderer' counts only the page
    renderers (not the browser, GPU or utility processes)."""
    children = {}
    for stat in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = stat.read_text().rsplit(')', 1)[1].split()
            children.setdefault(int(fields[1]), []).append(int(stat.parent.name))
        except (OSError, IndexError, ValueError):
            pass
    total, todo = 0, [pid]
    while todo:
        p = todo.pop()
        todo += children.get(p, [])
        try:
            if kind and f'--type={kind}'.encode() not in Path(f'/proc/{p}/cmdline').read_bytes():
                continue
            total += next(int(l.split()[1]) for l in Path(f'/proc/{p}/status').read_text().splitlines() if l.startswith('VmRSS:'))
        except (OSError, StopIteration):
            pass
    return round(total / 1024)


class Traffic:
    """Requests, transfer sizes, console lines and crashes from the DevTools events, collected per phase."""

    def __init__(self, chrome):
        self.chrome, self.urls, self.status, self.bytes, self.failed = chrome, {}, {}, {}, {}
        self.console, self.crashed = [], False

    def drain(self):
        while not self.chrome.events.empty():
            event = self.chrome.events.get()
            params, method = event.get('params', {}), event['method']
            rid = params.get('requestId')
            if method == 'Network.requestWillBeSent':
                self.urls[rid] = params['request']['url']
            elif method == 'Network.responseReceived':
                self.status[rid] = params['response']['status']
            elif method == 'Network.loadingFinished':
                self.bytes[rid] = params.get('encodedDataLength', 0)
            elif method == 'Network.loadingFailed':
                self.failed[rid] = params.get('errorText', '')
            elif method == 'Runtime.exceptionThrown':
                self.console.append(('exception', params['exceptionDetails'].get('exception', {}).get('description', 'exception')))
            elif method == 'Runtime.consoleAPICalled':
                self.console.append((params['type'], ' '.join(str(a.get('value', a.get('description', ''))) for a in params['args'])))
            elif method in ('Inspector.targetCrashed', 'Target.targetCrashed'):
                self.crashed = True

    def mark(self):
        self.drain()
        return len(self.urls), len(self.console)

    def since(self, mark):
        """(url, status, encoded bytes, failure) of the requests and the console lines after a mark."""
        self.drain()
        ids = list(self.urls)[mark[0]:]
        return ([(self.urls[i], self.status.get(i), self.bytes.get(i, 0), self.failed.get(i)) for i in ids], self.console[mark[1]:])

    def wait_console(self, prefix, mark, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for kind, text in self.since(mark)[1]:
                if text.startswith(prefix):
                    return text
            if self.crashed:
                return None
            time.sleep(0.5)
        return None


HEAVY = ('.glb', '.wasm', '.pck', '/vendor/', 'engine-', 'demo01-', 'viewer.js', 'draco')
# Frames per second of the page's own animation frames (Godot's main loop runs on them too) over a few seconds.
RAF_FPS = ('new Promise(r => { const t0 = performance.now(); let n = 0; const ts = []; let last = t0; '
           'const f = now => { n++; ts.push(now - last); last = now; if (now - t0 < {ms}) requestAnimationFrame(f); else { ts.sort((a, b) => a - b); '
           'r({fps: +(1000 * n / (now - t0)).toFixed(1), p95_ms: +ts[Math.floor(ts.length * 0.95)].toFixed(1), frames: n}); } }; '
           'requestAnimationFrame(f); })')


def run_equivalence(url, play_release, binary, sandbox, out, play_seconds, record_check, metrics):
    """Demonstrator 01 in the Web build against the native build of the same package (web_play.build): the 68-check suite and the
    whole journey in autoplay, both at a fixed frame rate with drawing off (--disable-render-loop: logic, physics and input step
    exactly as when drawn; the walk covers rendering). Runs in its own browser, alongside the walk: it is CPU-bound Godot logic,
    the walk mostly waits on software-rendered frames."""
    native = play_release.get('native_reference') or {}
    profile = tempfile.mkdtemp(prefix='wf-web-equivalence-')
    log = open(out / 'chrome-equivalence.log', 'w')
    chrome = Chrome(binary, profile, log, sandbox)
    try:
        page, traffic = Page(chrome), Traffic(chrome)
        page.send('Emulation.setDeviceMetricsOverride', {'width': 640, 'height': 400, 'deviceScaleFactor': 1, 'mobile': False})

        def browser_run(args, prefix):
            mark = traffic.mark()
            t0 = time.monotonic()
            query = '&'.join(f'arg={a}' for a in ('--disable-render-loop', *args))
            page.send('Page.navigate', {'url': url + play_release['page'] + '?' + query})
            line = traffic.wait_console(prefix, mark, play_seconds)
            lines = traffic.since(mark)[1]
            errors = [text for kind, text in lines if text.startswith('ERROR')]
            return (json.loads(line.split(' ', 1)[1]) if line else None), errors, round(time.monotonic() - t0, 1)

        demo, errors, seconds = browser_run(['--fixed-fps', '60', '--', '--check-demo'], 'WF_GODOT_DEMO ')
        web_ok = {c['id']: c['ok'] for c in (demo or {}).get('checks', [])}
        differ = sorted(k for k in set(web_ok) | set(native.get('ok_by_check', {})) if web_ok.get(k) != native.get('ok_by_check', {}).get(k))
        record_check('play: Demonstrator 01 check suite passes in the browser as natively', demo and demo.get('result') == 'PASS'
                     and not differ and not errors, checks=len(web_ok), native_checks=native.get('checks'), differ=differ[:8],
                     errors=errors[:3], seconds=seconds)
        metrics['check_suite'] = {'web': demo and {'result': demo.get('result'), 'checks': len(web_ok),
                                                    'failed': [k for k, ok in web_ok.items() if not ok]},
                                  'native': {k: native.get(k) for k in ('result', 'checks', 'failed')}, 'differ': differ, 'seconds': seconds}
        web, errors, seconds = browser_run(['--fixed-fps', '30', '--', '--autoplay', '--record-exit'], 'WF_DEMO_RECORDING ')
        rec = native.get('recording')
        keys = ('result', 'chapters', 'frames', 'flips', 'display_s')
        same = bool(web and rec) and all(web.get(k) == rec.get(k) for k in keys)
        record_check('play: whole-journey autoplay recording matches the native build', same and web['result'] == 'PASS' and not errors,
                     web=web, native=rec, errors=errors[:3], seconds=seconds)
        metrics['equivalence'] = {'web': web, 'native': rec, 'seconds': seconds}
    except Exception as error:
        log.flush()
        record_check('play: equivalence browser session', False, error=repr(error),
                     chrome_log=(out / 'chrome-equivalence.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


class JourneyStop(Exception):
    pass


def run_touch(url, play_release, binary, sandbox, out, record_check, metrics, timeout=150):
    """MOB-001: Enter Wayfarer played by touch on an emulated phone (844 x 390 CSS px, DPR 3, touch, landscape), in its own browser
    alongside the walk. CDP touch events go through the browser into Godot as a phone's would; the game publishes its touch state
    (window.wayfarerTouch, -- --touch-probe) and the check reads it. Covers the touch welcome, Skip, Pause, the rail stick with the
    look finger at once, release, weightless (no stick, no force; look; Push off), Map and the systems card, the transfer line,
    walking on ring A with Drop by a second finger, Help as a modal, portrait and a tablet size keeping the same run. Emulation,
    not a phone: it says nothing about a phone's frame rate. A step the rest depends on stops the journey when it fails (one failed
    check, no cascade of waits); it runs after the equivalence session, so at most two browsers share the runner."""
    profile = tempfile.mkdtemp(prefix='wf-web-touch-')
    log = open(out / 'chrome-touch.log', 'w')
    chrome = Chrome(binary, profile, log, sandbox)
    fingers = {}
    t_start = time.monotonic()
    try:
        page, traffic = Page(chrome), Traffic(chrome)

        def touch(kind, fid, at=None):
            if at is not None:
                fingers[fid] = at
            else:
                fingers.pop(fid, None)
            page.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in fingers.items()]})

        def state():
            return page.js('window.wayfarerTouch || null') or {}

        def until(pred, limit=timeout):
            end, s = time.monotonic() + limit, {}
            while time.monotonic() < end:
                s = state()
                try:
                    if s and pred(s):
                        return s
                except (KeyError, TypeError, IndexError):
                    pass
                time.sleep(0.5)
            return None

        def centre(r):
            return (r[0] + r[2] / 2, r[1] + r[3] / 2)

        def button(s, bid):
            return next((centre(b[2]) for b in s.get('buttons', []) if b[0] == bid), None)

        def tap_at(at, fid=7):
            touch('touchStart', fid, at)
            page.frames(2)
            touch('touchEnd', fid)
            page.frames(2)

        def need(name, ok, **detail):
            record_check(name, ok, **detail)
            if not ok:
                raise JourneyStop(name)

        def tap_panel(prefix, done):
            """A modal panel's button: wait until its place is settled (the panel lays out over a few frames), tap, confirm."""
            for _ in range(3):
                a = until(lambda s: any(t.startswith(prefix) for t, r in s['panel']), 60)
                time.sleep(1.0)
                b = state()
                ra = next((r for t, r in (a or {}).get('panel', []) if t.startswith(prefix)), None)
                rb = next((r for t, r in (b or {}).get('panel', []) if t.startswith(prefix)), None)
                if not rb or ra != rb:
                    continue
                tap_at(centre(rb))
                s = until(done, 60)
                if s:
                    return s
            return None

        def tap(bid):
            s = until(lambda s: button(s, bid) is not None)
            if s:
                tap_at(button(s, bid))
            return bool(s)

        def scene(s):
            return (s or {}).get('scene') or {}

        def body(s):
            return scene(s).get('body') or {}

        def skip_to(name):
            for _ in range(10):
                now = scene(state()).get('chapter')
                if now == name:
                    return True
                tap('ui.confirm')
                until(lambda s: scene(s).get('chapter') != now, 120)
            return scene(state()).get('chapter') == name

        def buttons(s):
            return [b[0] for b in (s or {}).get('buttons', [])]

        page.send('Emulation.setDeviceMetricsOverride', {'width': 844, 'height': 390, 'deviceScaleFactor': 3, 'mobile': True,
                                                          'screenOrientation': {'type': 'landscapePrimary', 'angle': 90}})
        page.send('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5})
        t0 = time.monotonic()
        page.send('Page.navigate', {'url': url + play_release['page'] + '?arg=--&arg=--touch-probe'})
        s = until(lambda s: s['mode'] == 'welcome' and s['panel'], 300)
        need('touch: phone detected, CSS-pixel interface, welcome without a key', s and s['primary'] and s['density'] == 3
             and abs(s['ui'][0] - 844) < 2 and abs(s['ui'][1] - 390) < 2, seconds=round(time.monotonic() - t0, 1), scale_3d=s and s['scale_3d'])
        page.screenshot(out / 'touch_1_welcome.png')
        s = tap_panel('Start with tips', lambda s: s['mode'] == '' and s['intro_done'])
        need('touch: welcome completed by a tap (tips on)', s and s['preference'] == 'SUGGESTED')
        page.frames(2)
        page.screenshot(out / 'touch_2_exterior.png')
        record_check('touch: guided chapter offers Pause and Skip, no stick', s and s['move'] == '' and {'demo.pause', 'ui.confirm'} <= set(buttons(s)),
                     buttons=buttons(s))
        tap('ui.confirm')
        tap('demo.pause')
        s = until(lambda s: scene(s)['chapter'] == 'ENTRY' and scene(s)['paused'])
        need('touch: Skip and Pause by touch reach a paused ENTRY', s)
        p0, lo0 = scene(s).get('progress', 0), scene(s).get('look_offset', [0, 0])
        touch('touchStart', 1, (110, 300))
        touch('touchMove', 1, (110, 250))
        touch('touchStart', 2, (600, 200))
        for k in range(1, 5):
            touch('touchMove', 2, (600 + 15 * k, 200))
            page.frames(1)
        s = until(lambda s: scene(s)['progress'] > p0 + 0.05)
        page.screenshot(out / 'touch_3_entry_stick_look.png')
        record_check('touch: stick walks the rail while a second finger looks', s and s['claims'] == 2 and abs(scene(s)['look_offset'][0] - lo0[0]) > 0.02,
                     progress=[p0, scene(s).get('progress')], look=[lo0, scene(s).get('look_offset')])
        touch('touchEnd', 1)
        touch('touchEnd', 2)
        page.frames(3)
        a = state()
        time.sleep(3)
        b = state()
        record_check('touch: lifting the fingers stops at once', not b['virtual'] and b['claims'] == 0 and scene(a)['progress'] == scene(b)['progress'],
                     progress=[scene(a)['progress'], scene(b)['progress']])
        tap('demo.pause')
        ok = skip_to('MICROGRAVITY')
        s = until(lambda s: body(s).get('grip'))
        need('touch: Skip by touch reaches MICROGRAVITY, holding the start rail', ok and s)
        page.frames(2)
        page.screenshot(out / 'touch_4_microgravity.png')
        record_check('touch: weightless: Push off and Release, no stick', ok and s and s['move'] == '' and {'player.push', 'player.release'} <= set(buttons(s)),
                     buttons=buttons(s))
        touch('touchStart', 1, (110, 300))
        touch('touchMove', 1, (110, 240))
        page.frames(4)
        s = state()
        record_check('touch: weightless: a left drag adds no force', not s['virtual'] and body(s).get('v') == 0, v=body(s).get('v'))
        touch('touchEnd', 1)
        y0 = body(s).get('yaw', 0)
        touch('touchStart', 2, (600, 200))
        for k in range(1, 4):
            touch('touchMove', 2, (600 + 20 * k, 200))
            page.frames(1)
        touch('touchEnd', 2)
        s = until(lambda s: abs(body(s)['yaw'] - y0) > 0.05)
        record_check('touch: a right drag turns the view (the push aim)', s, yaw=[y0, body(s).get('yaw')])
        tap('player.push')
        s = until(lambda s: body(s)['v'] > 0.01 and not body(s)['grip'])
        record_check('touch: Push off by touch moves the body (crew physics)', s, v=body(s).get('v'))
        tap('ship.map')
        tap('ship.card')
        s = until(lambda s: scene(s)['card_page'] == 0 and scene(s)['map_level'] == 1)
        page.frames(2)
        page.screenshot(out / 'touch_5_systems_card.png')
        for _ in range(3):
            tap('ship.card')
            page.frames(2)
        closed = until(lambda s: scene(s)['card_page'] == -1)
        record_check('touch: Map and the systems card open and close by touch', s and closed)
        tap('ship.map')
        tap('ship.map')
        ok = skip_to('TRANSFER')
        s = until(lambda s: s['move'] == '1d')
        record_check('touch: the transfer line takes the 1-D stick', ok and s)
        ok = skip_to('GRAVITY')
        s = until(lambda s: s['move'] == '2d' and body(s).get('standing'))
        pos0 = body(s).get('pos', [0, 0, 0])
        touch('touchStart', 1, (110, 300))
        touch('touchMove', 1, (110, 245))
        s = until(lambda s: math.dist(body(s)['pos'], pos0) > 0.2)
        page.screenshot(out / 'touch_6_gravity_walk.png')
        record_check('touch: walking on ring A by the stick', ok and s, moved=s and round(math.dist(body(s)['pos'], pos0), 2))
        d0 = body(state()).get('drops', 0)
        tap_at(button(state(), 'body.drop_tool') or (0, 0), 8)
        s = until(lambda s: body(s)['drops'] == d0 + 1)
        record_check('touch: Drop object with a second finger while walking', s and s['claims'] >= 1)
        touch('touchEnd', 1)
        tap('touch.help')
        s = until(lambda s: s['mode'] == 'help')
        page.frames(2)
        page.screenshot(out / 'touch_7_help.png')
        record_check('touch: Help is a modal (game paused, stick released)', s and s['paused'] and not s['virtual'])
        s = tap_panel('Close', lambda s: s['mode'] == '' and not s['paused'])
        need('touch: Help closes by touch', s)
        chapter = scene(state()).get('chapter')
        page.send('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 3, 'mobile': True,
                                                          'screenOrientation': {'type': 'portraitPrimary', 'angle': 0}})
        page.frames(3)
        turn = page.wait("!document.getElementById('turn').hidden", 20)
        page.screenshot(out / 'touch_8_portrait_hint.png')
        page.click(*page.centre_of('#turn-stay'))
        s = until(lambda s: s['ui'][0] < s['ui'][1])
        page.frames(2)
        page.screenshot(out / 'touch_9_portrait.png')
        record_check('touch: upright: a turn suggestion, then the same run continues', turn and s and scene(s)['chapter'] == chapter and s['claims'] == 0,
                     chapter=[chapter, scene(s).get('chapter')], ui=s and s['ui'])
        page.send('Emulation.setDeviceMetricsOverride', {'width': 1180, 'height': 820, 'deviceScaleFactor': 2, 'mobile': True,
                                                          'screenOrientation': {'type': 'landscapePrimary', 'angle': 90}})
        s = until(lambda s: abs(s['ui'][0] - 1180) < 2 and abs(s['ui'][1] - 820) < 2)
        page.frames(2)
        page.screenshot(out / 'touch_10_tablet.png')
        record_check('touch: tablet size, same run', s and scene(s)['chapter'] == chapter, ui=s and s['ui'])
        errors = [t for k, t in traffic.since((0, 0))[1] if k in ('error', 'exception') and not t.startswith('   at:')]
        record_check('touch: no engine or script errors', not errors and not traffic.crashed, errors=errors[:5])
        metrics['touch'] = {'seconds': round(time.monotonic() - t_start, 1), 'scale_3d': s and s['scale_3d'], 'godot_fps': s and s['fps'],
                            'renderer': 'SwiftShader software WebGL, emulated phone 844x390 DPR 3: behaviour only, not a phone frame rate'}
    except JourneyStop as stop:
        try:
            page.screenshot(out / 'touch_stopped.png')
            print(f'touch journey stopped at: {stop}; state {json.dumps(state())[:600]}', flush=True)
        except (RuntimeError, TimeoutError):
            print(f'touch journey stopped at: {stop}', flush=True)
    except Exception as error:
        log.flush()
        record_check('touch: phone session', False, error=repr(error),
                     chrome_log=(out / 'chrome-touch.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


def run_touch_walk(url, play_release, binary, sandbox, out, record_check, metrics, timeout=150):
    """EXC-001 on the emulated phone of run_touch (844 x 390 CSS px, DPR 3, landscape): the walk starts by the launcher's switch, the
    touch welcome is tapped through, the 1-D stick carries the trainee down the boarding line to the shut outer hatch (the push-off
    into the coast across it is refused), Use opens it, a look drag turns the view, Map and View answer. Behaviour only."""
    profile = tempfile.mkdtemp(prefix='wf-web-touch-walk-')
    log = open(out / 'chrome-touch-walk.log', 'w')
    chrome = Chrome(binary, profile, log, sandbox)
    fingers = {}
    t_start = time.monotonic()
    try:
        page, traffic = Page(chrome), Traffic(chrome)

        def touch(kind, fid, at=None):
            if at is not None:
                fingers[fid] = at
            else:
                fingers.pop(fid, None)
            page.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in fingers.items()]})

        def state():
            return page.js('window.wayfarerTouch || null') or {}

        def until(pred, limit=timeout):
            end = time.monotonic() + limit
            while time.monotonic() < end:
                s = state()
                try:
                    if s and pred(s):
                        return s
                except (KeyError, TypeError, IndexError):
                    pass
                time.sleep(0.5)
            return None

        def centre(r):
            return (r[0] + r[2] / 2, r[1] + r[3] / 2)

        def button(s, bid):
            return next((b for b in (s or {}).get('buttons', []) if b[0] == bid), None)

        def tap_at(at, fid=7):
            touch('touchStart', fid, at)
            page.frames(2)
            touch('touchEnd', fid)
            page.frames(2)

        def need(name, ok, **detail):
            record_check(name, ok, **detail)
            if not ok:
                raise JourneyStop(name)

        def scene(s):
            return (s or {}).get('scene') or {}

        page.send('Emulation.setDeviceMetricsOverride', {'width': 844, 'height': 390, 'deviceScaleFactor': 3, 'mobile': True,
                                                          'screenOrientation': {'type': 'landscapePrimary', 'angle': 90}})
        page.send('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5})
        page.send('Page.navigate', {'url': url + play_release['page'] + '?arg=--&arg=--excursion&arg=--touch-probe'})
        s = until(lambda s: s['mode'] == 'welcome' and s['panel'] and scene(s).get('scene') == 'excursion', 300)
        need('touch walk: the walk starts on a phone with the touch welcome', s, seconds=round(time.monotonic() - t_start, 1))
        for _ in range(3):
            r = next((r for t_, r in state().get('panel', []) if t_.startswith('Start with tips')), None)
            if r:
                time.sleep(1.0)
                tap_at(centre(r))
            s = until(lambda s: s['mode'] == '' and s['intro_done'], 30)
            if s:
                break
        need('touch walk: welcome completed by a tap', s)
        page.frames(2)
        page.screenshot(out / 'touch_walk_1_station.png')
        record_check('touch walk: weightless line: 1-D stick, look, View and Map', s['move'] == '1d' and s['look']
                     and button(s, 'exc.view') and button(s, 'exc.map'), buttons=[b[0] for b in s['buttons']])
        s0 = scene(s).get('s', 0.0)
        touch('touchStart', 1, (110, 300))
        page.frames(2)
        touch('touchMove', 1, (110, 236))                   # stick up: along the line toward the view (down the tunnel)
        # the line pace is in game time: a software-rendered runner at 1 fps steps physics 8 ticks a frame, about 1/8 of real time
        s = until(lambda s: button(s, 'exc.use') and 'open outer hatch' in scene(s).get('use', ''), 300)
        touch('touchEnd', 1)
        need('touch walk: the stick carries the body down the boarding line to the shut outer hatch', s and scene(s)['s'] > s0 + 3.0,
             s=[s0, scene(s or state()).get('s')])
        page.screenshot(out / 'touch_walk_2_hatch.png')
        tap_at(centre(button(s, 'exc.use')[2]))
        s = until(lambda s: 'close outer hatch' in scene(s).get('use', ''), 30)
        record_check('touch walk: Use opens the outer hatch', s, use=scene(s).get('use') if s else None)
        yaw0 = scene(state()).get('yaw', 0.0)
        touch('touchStart', 2, (620, 200))
        for x in (650, 690, 730):
            touch('touchMove', 2, (x, 200))
            page.frames(1)
        touch('touchEnd', 2)
        s = until(lambda s: abs(scene(s).get('yaw', yaw0) - yaw0) > 0.05, 20)
        record_check('touch walk: a look drag turns the view', s, yaw=[yaw0, scene(s).get('yaw') if s else None])
        s = state()
        for bid in ('exc.map', 'exc.view', 'exc.view', 'exc.map'):
            b = button(state(), bid)
            if b:
                tap_at(centre(b[2]))
        s = until(lambda s: s['triggered'][-4:] == ['exc.map', 'exc.view', 'exc.view', 'exc.map'], 20)
        record_check('touch walk: Map and View answer by touch', s, triggered=(s or state()).get('triggered', [])[-4:])
        page.screenshot(out / 'touch_walk_3_after.png')
        errors = [t_ for k, t_ in traffic.since((0, 0))[1] if k in ('error', 'exception') and not t_.startswith('   at:')]
        record_check('touch walk: no engine or script errors', not errors and not traffic.crashed, errors=errors[:5])
        metrics['touch_walk'] = {'seconds': round(time.monotonic() - t_start, 1)}
    except JourneyStop as stop:
        try:
            page.screenshot(out / 'touch_walk_stopped.png')
            print(f'touch walk stopped at: {stop}; state {json.dumps(state())[:600]}', flush=True)
        except (RuntimeError, TimeoutError):
            print(f'touch walk stopped at: {stop}', flush=True)
    except Exception as error:
        log.flush()
        record_check('touch walk: phone session', False, error=repr(error),
                     chrome_log=(out / 'chrome-touch-walk.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


def run_main(url, release, build, binary, sandbox, out, record_check, metrics):
    """The visitor's walk in one browser: start page, Explore Ship, Enter Wayfarer (the walk), switching and memory, phone, review."""
    play_release = release['experiences'].get('play')
    profile = tempfile.mkdtemp(prefix='wf-web-check-')
    log = open(out / 'chrome.log', 'w')
    # The back-forward cache stays off so the memory check measures what the pages release, not what Chrome chooses to keep.
    chrome = Chrome(binary, profile, log, sandbox, extra=["--disable-features=BackForwardCache"])
    try:
        page = Page(chrome)
        page.send('Network.setCacheDisabled', {'cacheDisabled': True})        # every phase measures a cold load
        traffic = Traffic(chrome)

        def requests_ok(name, reqs, prefix=url):
            reqs = [r for r in reqs if not r[0].startswith(('blob:', 'data:'))]      # in-memory objects (Draco worker, audio worklet)
            bad = [(u, s, f) for u, s, _, f in reqs if f or (s or 0) >= 400 or s is None]
            off = sorted({u for u, *_ in reqs if not u.startswith(prefix) and not u.startswith('data:')})
            record_check(name, not bad and not off, failed=bad[:5], offsite=off[:5], requests=len(reqs))

        def heap(limit=None):
            """Page-renderer memory (MB) once it settles: polled for up to 30 s until it is under `limit`."""
            end = time.monotonic() + 30
            while True:
                time.sleep(2)
                now = rss(chrome.process.pid, 'renderer')
                if limit is None or now <= limit or time.monotonic() > end:
                    return now

        # A: the start page loads alone: no model, engine or library request, no canvas, within its byte budget.
        mark = traffic.mark()
        t0 = time.monotonic()
        page.send('Page.navigate', {'url': url})
        page.wait("document.readyState === 'complete' && document.getElementById('release').textContent.startsWith('Release 2')", 30)
        start_s = round(time.monotonic() - t0, 2)
        time.sleep(1)
        reqs, lines = traffic.since(mark)
        heavy = [u for u, *_ in reqs if any(h in u for h in HEAVY)]
        names = sorted({u[len(url):] or 'index.html' for u, *_ in reqs})
        record_check('start: loads only the page, its stylesheet and release.json', not heavy and names == ['index.html', 'release.json', 'site.css'],
                     requests=names, heavy=heavy)
        canvases = page.js("document.querySelectorAll('canvas').length")
        record_check('start: no canvas or engine initialized', canvases == 0 and not page.js('!!(window.Engine || window.wayfarer)'), canvases=canvases)
        start_bytes = sum(b for _, _, b, _ in reqs)
        timing = page.js("(() => { const n = performance.getEntriesByType('navigation')[0]; return {dcl: Math.round(n.domContentLoadedEventEnd), "
                         "load: Math.round(n.loadEventEnd)}; })()")
        record_check('start: under its transfer budget', start_bytes < 150_000, transferred=start_bytes, load_ms=timing)
        metrics['start'] = {'transferred_bytes': start_bytes, 'navigation_ms': timing, 'ready_s': start_s, 'requests': len(reqs)}
        requests_ok('start: every request served from the project subpath', reqs)
        page.screenshot(out / 'start.png')
        heaps = [('start', heap())]
        settled = heaps[0][1] + 200          # back on the start page, the renderers return to within 200 MB of the first visit

        # B: Explore Ship opens from its link and loads the viewer only.
        mark = traffic.mark()
        t0 = time.monotonic()
        page.click(*page.centre_of('#go-viewer'))
        ready = page.wait('!!(window.wayfarer && window.wayfarer.model)', 240)
        viewer_s = round(time.monotonic() - t0, 1)
        if ready:
            page.js('window.wayfarer.controls.enableDamping = false')
        page.frames()
        record_check('viewer: model loaded from the start page link', ready, seconds=viewer_s,
                     status=page.js("document.getElementById('status').textContent"))
        if not ready:
            raise SystemExit
        counts = page.js('(() => { let n = 0; window.wayfarer.model.traverse(o => { if (o.name.startsWith("WF_")) n++; }); '
                         'return [n, window.wayfarer.groups.size]; })()')
        record_check('viewer: every exported mesh node is in the scene', counts[0] == build['glb']['mesh_nodes'], nodes=counts[0],
                     expected=build['glb']['mesh_nodes'])
        record_check('viewer: assembly groups present', counts[1] == 14, groups=counts[1])
        x, y = page.js(FRAMING)
        record_check('viewer: whole ship framed on load', max(x, y) <= 1.0 and max(x, y) >= 0.6, ndc_extent=[round(x, 3), round(y, 3)])
        page.screenshot(out / 'desktop_threequarter.png')
        home = page.js(CAMERA)

        page.drag((640, 400), (900, 330))
        page.frames()
        orbit = page.js(CAMERA)
        record_check('viewer: left drag orbits', moved(home, orbit, 'p') > 1 and moved(home, orbit, 't') < 1e-3
                     and moved(home, orbit, 'd') < 0.01 * home['d'], moved_m=round(moved(home, orbit, 'p'), 2))
        page.mouse('mouseWheel', 640, 400, deltaX=0, deltaY=-600)
        page.frames()
        zoom = page.js(CAMERA)
        record_check('viewer: wheel zooms in', zoom['d'] < 0.9 * orbit['d'], distance=[round(orbit['d'], 1), round(zoom['d'], 1)])
        page.drag((640, 400), (520, 470), button='right')
        page.frames()
        pan = page.js(CAMERA)
        record_check('viewer: right drag pans', moved(zoom, pan, 't') > 0.5, target_moved_m=round(moved(zoom, pan, 't'), 2))
        bookmark = page.js('location.hash')
        page.click(*page.centre_of('[data-view=reset]'))
        page.frames()
        reset = page.js(CAMERA)
        record_check('viewer: Reset restores the whole-ship view', moved(home, reset, 'p') < 0.05 and moved(home, reset, 't') < 0.05)
        for view in ('side', 'top', 'front'):
            page.click(*page.centre_of(f'[data-view={view}]'))
            page.frames()
            x, y = page.js(FRAMING)
            record_check(f'viewer: {view} preset frames the ship', max(x, y) <= 1.0 and max(x, y) >= 0.6, ndc_extent=[round(x, 3), round(y, 3)])
            page.screenshot(out / f'desktop_{view}.png')
        page.click(*page.centre_of('[data-view=reset]'))
        page.frames()
        picked = None
        for px, py in ((640, 400), (600, 400), (700, 410), (560, 380), (740, 380)):
            page.click(px, py)
            page.frames()
            if page.js("!document.getElementById('pick').hidden"):
                picked = page.js("document.getElementById('pick').innerText")
                break
        record_check('viewer: click picks a part and names it', picked, label=picked)
        page.screenshot(out / 'desktop_pick.png')
        page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
        page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
        # WEB-004 appearance: styles, per-assembly states, Hybrid focus, picking policy, colours from the export, reset (web/README.md).
        snap0 = page.js(SNAPSHOT)
        for name in ('subsystem', 'engine', 'hybrid', 'standard'):
            page.click(*page.centre_of(f'[data-style={name}]'))
            ok = page.wait(f"window.wayfarer.style() === '{name}' && window.wayfarer.records.every(r => r.res)", 120)
            page.frames()
            styled = page.js(STYLED.replace('{style}', name))
            record_check(f'viewer: {name} style draws every mesh in its look', ok and styled['wrong'] == 0, **styled)
            if name in ('subsystem', 'engine'):
                page.screenshot(out / f'desktop_holo_{name}.png')
            if name == 'subsystem':
                tints = page.js(TINTS)
                record_check('viewer: subsystem colours are the exported classification', tints['checked'] > 0 and tints['wrong'] == 0, **tints)
        page.click(*page.centre_of('#panel-toggle'))
        first = page.js("document.querySelector('#assemblies li select').dataset.assembly")
        states = {}
        for st in ('SOLID', 'HOLOGRAM', 'GHOST', 'HIDDEN'):
            page.js(f"(() => {{ const s = document.querySelector('#assemblies li select'); s.value = '{st}'; s.dispatchEvent(new Event('change')); }})()")
            states[st] = page.wait(f"window.wayfarer.records.filter(r => r.assembly === '{first}').every(r => r.res.state === '{st}' "
                                   f"&& r.meshes.every(m => m.visible === ('{st}' !== 'HIDDEN')))", 60)
        page.frames()
        page.screenshot(out / 'desktop_assembly_hidden.png')
        page.click(*page.centre_of('#show-all'))
        shown = page.wait(f"window.wayfarer.records.filter(r => r.assembly === '{first}').every(r => r.res.state !== 'HIDDEN')", 60)
        record_check('viewer: an assembly takes Solid, Hologram, Ghost and Hidden; Show all lifts Hidden', all(states.values()) and shown,
                     assembly=first, states=states)
        page.js("document.querySelector('#assemblies li select').value = ''; document.querySelector('#assemblies li select').dispatchEvent(new Event('change'))")
        page.click(*page.centre_of('#panel-toggle'))
        page.click(*page.centre_of('[data-style=hybrid]'))
        page.wait("window.wayfarer.style() === 'hybrid'", 60)
        hybrid = None
        for px, py in ((640, 400), (600, 400), (700, 410), (560, 380), (740, 380)):
            page.click(px, py)
            page.frames()
            hybrid = page.js(HYBRID_FOCUS)
            if hybrid['selected']:
                hit = (px, py)
                break
        record_check('viewer: Hybrid click focuses the picked part solid, the rest ghost', hybrid['ok'], **details(hybrid))
        page.screenshot(out / 'desktop_hybrid_focus.png')
        kept = page.js(KEEPS_OVERRIDES)
        record_check('viewer: changing the selection keeps unrelated assembly states', kept['ok'], **details(kept))
        hidden_pick = page.js(HIDDEN_PICK.replace('{x}', str(hit[0])).replace('{y}', str(hit[1]))) if hybrid['selected'] else {'ok': False}
        record_check('viewer: hidden parts never take a pick', hidden_pick['ok'], **details(hidden_pick))
        ghost_pick = page.js(GHOST_PICK, timeout=180)
        record_check('viewer: ghosts never take a pick from a visible subject behind them', ghost_pick['ok'], **details(ghost_pick))
        page.click(*page.centre_of('#appearance-toggle'))
        page.click(*page.centre_of('#reset-appearance'))
        page.click(*page.centre_of('#appearance-toggle'))
        page.frames()
        snap1 = page.js(SNAPSHOT)
        record_check('viewer: Reset appearance restores materials, visibility and transforms', snap1 == {**snap0, 'style': 'standard'} and
                     snap1['original_materials'] == snap1['meshes'] == snap1['original_visibility'] and not snap1['added_lines'],
                     before=snap0, after=snap1)
        fps = page.js(RAF_FPS.replace('{ms}', '4000'), timeout=120)
        stats = page.js('(() => { const s = window.wayfarer.stats; return {calls: s.calls, triangles: s.triangles, ready_ms: s.ready_ms}; })()')
        reqs, lines = traffic.since(mark)
        engine = [u for u, *_ in reqs if '/play/' in u]
        record_check('viewer: no Enter Wayfarer file requested', not engine, play_requests=engine[:3])
        requests_ok('viewer: every request served from the project subpath', reqs)
        errors = [text for kind, text in lines if kind in ('error', 'assert', 'exception')
                  or (kind == 'warning' and any(w in text for w in ('WebGL', 'THREE', 'shader', 'Shader')))]
        record_check('viewer: no script errors or WebGL warnings', not errors, errors=errors[:5])
        metrics['viewer'] = {'ready_s': viewer_s, 'transferred_bytes': sum(b for _, _, b, _ in reqs), 'requests': len(reqs),
                             'raf': fps, **stats, 'renderer_rss_mb': rss(chrome.process.pid, 'renderer'),
                             'renderer': 'SwiftShader software WebGL, 1280x800'}

        # The camera bookmark the drags wrote reopens the same view after a reload.
        page.send('Page.navigate', {'url': url + 'viewer/?reopen' + bookmark})     # a new URL, so the page really reloads
        page.wait('!!(window.wayfarer && window.wayfarer.model)', 240)
        page.frames()
        again = page.js(CAMERA)
        record_check('viewer: #cam bookmark reopens the camera', bookmark.startswith('#cam=') and moved(pan, again, 'p') < 0.05
                     and moved(pan, again, 't') < 0.05, bookmark=bookmark)
        # WEB-004: style, focus, focus look, ghost strength and an assembly state come back from the link; a missing target is dropped.
        mark_state = ('#view=side&style=hybrid&focus=a:{a}&look=cyan&ghost=12&ov=a:{b}.x,n:WF_NO_SUCH_NODE.g'
                      .format(a=first, b=page.js("[...window.wayfarer.groups.keys()].sort().at(-1)")))
        page.send('Page.navigate', {'url': url + 'viewer/?appearance' + mark_state})
        page.wait("!!(window.wayfarer && window.wayfarer.model && window.wayfarer.records.every(r => r.res))", 240)
        restored_state = page.js("(() => { const s = window.wayfarer.state; return {style: s.style, focus: s.focus, look: s.focusLook, ghost: s.ghost, "
                                 "overrides: [...s.overrides]}; })()")
        record_check('viewer: the bookmark restores style, focus and states', restored_state['style'] == 'hybrid' and restored_state['look'] == 'cyan'
                     and restored_state['focus'] == {'kind': 'assembly', 'id': first} and abs(restored_state['ghost'] - 0.12) < 1e-9
                     and len(restored_state['overrides']) == 1 and restored_state['overrides'][0][1] == 'HIDDEN', bookmark=mark_state, state=restored_state)

        # Back to the start page: the viewer's context is released (pagehide) and nothing of it stays loaded.
        page.click(*page.centre_of('a.back'))
        page.wait("document.readyState === 'complete' && !!document.getElementById('go-play')", 30)
        heaps.append(('start after viewer', heap(settled)))

        # C: Enter Wayfarer: the launcher loads no engine; Start loads the engine and the pack only.
        if play_release:
            mark = traffic.mark()
            page.click(*page.centre_of('#go-play'))
            page.wait("document.readyState === 'complete' && !document.getElementById('start').disabled && "
                      "document.getElementById('size').textContent.includes('MB')", 30)
            reqs, _ = traffic.since(mark)
            heavy = [u for u, *_ in reqs if any(h in u for h in HEAVY)]
            record_check('play launcher: no engine or pack before Start', not heavy, requests=sorted({u[len(url):] for u, *_ in reqs}))
            page.screenshot(out / 'play_launcher.png')
            mark = traffic.mark()
            t0 = time.monotonic()
            page.click(*page.centre_of('#start'))
            running = page.wait("window.wayfarerPlay && ['running', 'failed'].includes(window.wayfarerPlay.state)", 300) and \
                page.js("window.wayfarerPlay.state") == 'running'
            play_s = round(time.monotonic() - t0, 1)
            booted = traffic.wait_console('Godot Engine v', mark, 30)
            walk = traffic.wait_console('WF_EXCURSION ready', mark, 300) if running else None
            record_check('play: engine and the walk start', running and booted and walk, seconds=play_s, engine=booted, walk=walk,
                         state=page.js('window.wayfarerPlay'))
            if running:
                time.sleep(5)
                page.screenshot(out / 'play_first_launch.png')
                for key, code in (('Enter', 13), ('Enter', 13)):        # ACI first launch: the suggested Confirm (the walk ignores the second)
                    page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': key, 'code': key, 'windowsVirtualKeyCode': code})
                    page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': key, 'code': key, 'windowsVirtualKeyCode': code})
                    time.sleep(3)
                fps = page.js(RAF_FPS.replace('{ms}', '8000'), timeout=120)
                page.screenshot(out / 'play_running.png')
                reqs, lines = traffic.since(mark)
                viewer = [u for u, *_ in reqs if '/viewer/' in u]
                record_check('play: no Explore Ship file requested', not viewer, viewer_requests=viewer[:3])
                requests_ok('play: every request served from the project subpath', reqs)
                errors = [text for kind, text in lines if kind in ('error', 'exception') and not text.startswith('   at:')]
                record_check('play: no engine or script errors', not errors and not traffic.crashed, errors=errors[:5], crashed=traffic.crashed)
                metrics['play'] = {'interactive_s': play_s, 'transferred_bytes': sum(b for _, _, b, _ in reqs), 'requests': len(reqs),
                                   'raf': fps, 'start_ms': page.js('window.wayfarerPlay.start_ms'), 'renderer_rss_mb': rss(chrome.process.pid, 'renderer'),
                                   'renderer': 'SwiftShader software WebGL, 1280x800'}
            # Leave through the in-game Exit link to the launcher and on to the start page.
            page.click(*page.centre_of('#exit'))
            page.wait("document.readyState === 'complete' && !!document.getElementById('start')", 30)
            page.click(*page.centre_of('header a'))
            page.wait("document.readyState === 'complete' && !!document.getElementById('go-viewer')", 30)
            heaps.append(('start after play', heap(settled)))
            canvases = page.js("document.querySelectorAll('canvas').length")
            record_check('switching: back on the start page with no canvas or engine left', canvases == 0 and not page.js('!!window.Engine'))

            # D: the other experience again after the game: the viewer still starts.
            page.click(*page.centre_of('#go-viewer'))
            again = page.wait('!!(window.wayfarer && window.wayfarer.model)', 240)
            record_check('switching: Explore Ship starts again after Enter Wayfarer', again)
            page.click(*page.centre_of('a.back'))
            page.wait("document.readyState === 'complete' && !!document.getElementById('go-viewer')", 30)
            heaps.append(('start after second viewer', heap(settled)))
            record_check('switching: renderer memory returns to the start-page level after each experience',
                         all(h <= settled for _, h in heaps) and not traffic.crashed, renderer_rss_mb=heaps, crashed=traffic.crashed)
            metrics['memory'] = {'renderer_rss_mb': heaps, 'in_viewer_mb': metrics['viewer'].get('renderer_rss_mb'),
                                 'in_play_mb': metrics.get('play', {}).get('renderer_rss_mb'),
                                 'note': 'page-renderer RSS on the start page after each experience, settled up to 30 s; Chrome runs with '
                                         'the back-forward cache off (with it on, Chrome keeps left pages until it evicts them)'}

        # Phone: the start page and the viewer at 390 x 844 with touch.
        page.send('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        page.send('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5})
        page.send('Page.navigate', {'url': url})
        page.wait("document.readyState === 'complete'", 30)
        record_check('phone: start page has no horizontal overflow', not page.js('document.documentElement.scrollWidth > window.innerWidth'))
        page.screenshot(out / 'phone_start.png')
        page.send('Page.navigate', {'url': url + 'viewer/'})
        if page.wait('!!(window.wayfarer && window.wayfarer.model)', 240):
            page.js('window.wayfarer.controls.enableDamping = false')
            page.frames()
            x, y = page.js(FRAMING)
            record_check('phone: whole ship framed', max(x, y) <= 1.0 and max(x, y) >= 0.6, ndc_extent=[round(x, 3), round(y, 3)])
            page.screenshot(out / 'phone_threequarter.png')
            start = page.js(CAMERA)
            page.touch('touchStart', [(195, 420)])
            for i in range(1, 4):
                page.touch('touchMove', [(195 + 40 * i, 420)])
            page.touch('touchEnd', [])
            page.frames()
            spun = page.js(CAMERA)
            record_check('phone: one-finger drag orbits', moved(start, spun, 'p') > 1 and moved(start, spun, 't') < 1e-3,
                         moved_m=round(moved(start, spun, 'p'), 2))
            page.touch('touchStart', [(165, 420), (225, 420)])
            for i in range(1, 4):
                page.touch('touchMove', [(165 - 27 * i, 420), (225 + 27 * i, 420)])
            page.touch('touchEnd', [])
            page.frames()
            pinch = page.js(CAMERA)
            record_check('phone: pinch zooms in', pinch['d'] < 0.9 * spun['d'], distance=[round(spun['d'], 1), round(pinch['d'], 1)])
            record_check('phone: no horizontal overflow', not page.js('document.documentElement.scrollWidth > window.innerWidth'))
            page.screenshot(out / 'phone_zoomed.png')
        else:
            record_check('phone: model loaded', False)
        page.send('Page.navigate', {'url': url + 'review/'})
        rendered = page.wait("document.querySelectorAll('section.panel').length >= 6", 30)
        record_check('review page renders release.json', rendered and release['release'] in page.js('document.body.innerText'))
        page.screenshot(out / 'review.png')
    except SystemExit:
        pass
    except Exception as error:      # a browser session failure is a failed check with Chrome's own last words
        log.flush()
        record_check('browser session', False, error=repr(error), chrome_log=(out / 'chrome.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


PARTS = ('main', 'equivalence', 'touch', 'walk')     # the main walk, browser-vs-native, the touch journey, the touch walk


def record_release(site, release, results, metrics, version):
    """Writes the summary and metrics into the site's release.json (tests)."""
    carried = (release['experiences'].get('play') or {}).get('reused_from')
    group = lambda prefix: [r for r in results if r['check'].split(':')[0] in prefix]
    summary = lambda rs: rs and {'result': 'PASS' if all(r['ok'] for r in rs) else 'FAIL', 'passed': sum(r['ok'] for r in rs),
                                 'total': len(rs), 'failed': [r['check'] for r in rs if not r['ok']], 'browser': version}
    release['tests'] = {'viewer': summary(group(('viewer', 'phone'))), 'isolation': summary(group(('start', 'play launcher', 'switching'))),
                        'play': summary(group(('play',))), 'touch': summary(group(('touch',))), 'all': summary(results), 'metrics': metrics}
    equivalence = [r for r in results if r['check'].startswith(('play: Demonstrator 01 check suite', 'play: whole-journey'))]
    if carried and any(r['check'].startswith('play: browser-vs-native equivalence carried') for r in results):
        release['tests']['equivalence'] = {**carried['equivalence'], 'carried_from': carried['release']}
    elif equivalence:
        eq, suite = metrics.get('equivalence') or {}, metrics.get('check_suite') or {}
        release['tests']['equivalence'] = {
            'result': 'PASS' if all(r['ok'] for r in equivalence) else 'FAIL',
            'note': f"browser vs native on the same package: check suite {(suite.get('web') or {}).get('checks', '-')} checks, "
                    f"{len(suite.get('differ', []))} differing; whole-journey autoplay at a fixed 30 fps {(eq.get('web') or {}).get('frames', '-')} "
                    f"frames vs {(eq.get('native') or {}).get('frames', '-')} natively, same chapters and production-layer flips"}
    (site / 'release.json').write_text(json.dumps(release, indent=1) + '\n')


def merge(site, part_dirs, out, record=False):
    """One report from the parts' check.json (CI runs each part on its own runner against the same site); a part without a report,
    or with one for another release, fails. record: write it into the site's release.json, as a single run would."""
    release = json.loads((site / 'release.json').read_text())
    results, metrics, browsers, seconds, parts = [], {}, [], {}, []
    for d in part_dirs:
        try:
            rep = json.loads((d / 'check.json').read_text())
        except (OSError, ValueError):
            rep = {'checks': [{'check': f'browser check part {d.name}: reported', 'ok': False}]}
        if rep.get('git_revision', release['git_revision']) != release['git_revision']:
            rep['checks'] = [{'check': f'browser check part {d.name}: same release', 'ok': False, 'git_revision': rep.get('git_revision')}]
        results += rep['checks']
        metrics.update(rep.get('metrics') or {})
        browsers += [rep['browser']] if rep.get('browser') and rep['browser'] not in browsers else []
        seconds[d.name] = rep.get('seconds')
        parts += rep.get('parts', [])
    version = ', '.join(browsers)
    report = {'result': 'PASS' if results and all(r['ok'] for r in results) else 'FAIL', 'browser': version,
              'renderer': 'SwiftShader (software WebGL), headless', 'url': BASE, 'git_revision': release['git_revision'],
              'release': release['release'], 'parts': parts, 'part_seconds': seconds, 'metrics': metrics, 'checks': results}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'check.json').write_text(json.dumps(report, indent=2) + '\n')
    if record:
        record_release(site, release, results, metrics, version)
    return report


def check(site, out, binary, sandbox=True, record=False, play_seconds=900, live=None, recording=True, touch=True, parts=PARTS):
    """site: the local site directory, or None with live=<deployed URL ending in />, which reads release.json from there.
    parts: the sessions to run (PARTS); each part's check.json can be merged later (merge)."""
    out.mkdir(parents=True, exist_ok=True)
    if live:
        fetch = lambda path: json.loads(urllib.request.urlopen(urllib.request.Request(live + path, headers={'Cache-Control': 'no-cache'}),
                                                               timeout=60).read())
        release, build, server, url = fetch('release.json'), fetch('viewer/build.json'), None, live
    else:
        release = json.loads((site / 'release.json').read_text())
        build = json.loads((site / 'viewer/build.json').read_text())
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Site, directory=str(site)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}' + BASE
    play_release = release['experiences'].get('play')
    results, metrics = [], {}

    def record_check(name, ok, **detail):
        results.append({'check': name, 'ok': bool(ok), **detail})
        print(('PASS ' if ok else 'FAIL ') + name, json.dumps(detail) if detail else '', flush=True)
        if os.environ.get('GITHUB_ACTIONS') and not ok:
            print(f'::error title=web check::{name} {json.dumps(detail)}'.replace('\n', ' '), flush=True)     # public run annotation

    carried = (play_release or {}).get('reused_from')
    if 'equivalence' in parts and play_release and recording and carried:
        # The play files are byte-identical to a verified release with the same inputs (web_play.reusable): its browser-vs-native
        # result holds for them. The walk below still boots and plays them.
        record_check(f"play: browser-vs-native equivalence carried from release {carried['release']} (same play files)",
                     carried['equivalence'].get('result') == 'PASS', release=carried['release'], git_revision=carried['git_revision'],
                     note=carried['equivalence'].get('note'))
    equivalence = 'equivalence' in parts and recording and not carried
    side_parts = [k for k in ('touch', 'walk') if touch and k in parts]
    # The side browser runs the equivalence session and then the touch journey and the touch walk (at most two browsers share a
    # runner with the main walk; CI runs each part on its own runner and merges them, --part and --merge).
    def side_work():
        if equivalence:
            run_equivalence(url, play_release, binary, sandbox, out, play_seconds, record_check, metrics)
        if 'touch' in side_parts:
            run_touch(url, play_release, binary, sandbox, out, record_check, metrics)
        if 'walk' in side_parts:
            run_touch_walk(url, play_release, binary, sandbox, out, record_check, metrics)
    side = threading.Thread(target=side_work) if play_release and (equivalence or side_parts) else None
    t0 = time.monotonic()
    if side:
        side.start()
    try:
        if 'main' in parts:
            run_main(url, release, build, binary, sandbox, out, record_check, metrics)
    finally:
        if side:
            side.join()
        if server:
            server.shutdown()
    version = subprocess.run([binary, '--version'], capture_output=True, text=True).stdout.strip()
    report = {'result': 'PASS' if results and all(r['ok'] for r in results) else 'FAIL', 'browser': version,
              'renderer': 'SwiftShader (software WebGL), headless', 'url': live or BASE, 'git_revision': release['git_revision'],
              'release': release['release'], 'parts': list(parts), 'seconds': round(time.monotonic() - t0), 'metrics': metrics, 'checks': results}
    (out / 'check.json').write_text(json.dumps(report, indent=2) + '\n')
    if record and not live:
        record_release(site, release, results, metrics, version)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('site', type=Path, nargs='?', help='local site directory (omit with --live)')
    parser.add_argument('--live', help='check the deployed site at this URL (ending in /) instead of a local directory')
    parser.add_argument('--no-recording', action='store_true', help='skip the recorded Demonstrator 01 run')
    parser.add_argument('--no-touch', action='store_true', help='skip the emulated-phone touch journey')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--chrome', default=os.environ.get('CHROME', 'google-chrome'))
    parser.add_argument('--no-sandbox', action='store_true', help="disposable CI VMs whose AppArmor blocks Chrome's namespace sandbox")
    parser.add_argument('--record', action='store_true', help="write the results into the site's release.json (tests)")
    parser.add_argument('--play-seconds', type=int, default=900, help='time allowed for the recorded Demonstrator 01 run')
    parser.add_argument('--part', action='append', choices=PARTS, help='run only this part (repeatable; default all): main, equivalence, touch, walk')
    parser.add_argument('--merge', type=Path, nargs='+', metavar='DIR', help="merge these parts' check.json into --out (with --record, into the site)")
    args = parser.parse_args()
    if args.merge:
        report = merge(args.site.resolve(), [d.resolve() for d in args.merge], args.out.resolve(), record=args.record)
    else:
        report = check(args.site and args.site.resolve(), args.out.resolve(), args.chrome, sandbox=not args.no_sandbox, record=args.record,
                       play_seconds=args.play_seconds, live=args.live, recording=not args.no_recording, touch=not args.no_touch,
                       parts=tuple(args.part or PARTS))
    print(report['result'], f"{sum(r['ok'] for r in report['checks'])}/{len(report['checks'])} checks")
    if os.environ.get('GITHUB_ACTIONS'):
        loads = {r['check']: r.get('seconds') for r in report['checks'] if 'seconds' in r}
        print(f"::notice title=web check::{report['result']} {sum(r['ok'] for r in report['checks'])}/{len(report['checks'])}; {report['browser']}; load s {loads}")
    sys.exit(report['result'] != 'PASS')
