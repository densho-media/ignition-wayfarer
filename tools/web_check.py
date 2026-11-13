"""Browser check of the Wayfarer site: headless Chrome over the DevTools pipe (standard library only).

Serves the site under /ignition-wayfarer/ (the GitHub Pages project path) with software WebGL (SwiftShader) and the cache off,
and walks it as a visitor does, recording every request:
  start      the start page loads only index.html, site.css and release.json: no model, engine or library, no canvas
  viewer     Explore Ship from its link: whole-ship framing, orbit, zoom, pan, reset, presets, picking, the four styles, assembly states,
             Hybrid focus, the picking policy, exported colours, Reset appearance, the #cam and appearance bookmarks, no Enter Wayfarer file
  play       Explore Interior and Explore Exterior, each from its start-page choice: the launcher requests no engine before Start; Start
             boots Godot and that experience's own scene (the walk, EXC-001; EVA Operations, EVA-OPS-001) and no other, with no viewer
             file and no error; the player acts (the trainee walks on W; the astronaut undocks, lets go, thrusts, takes the drone) and
             the scene's published state follows; Exit returns to that experience's launcher
  switching  Exit back to the start page, Explore Ship again; page-renderer memory returns to the start-page level (Chrome runs
             with the back-forward cache off, so this measures what the pages release)
  equivalence  the walk's own check (both rings round and back to the station), drawing off, must pass in the browser as in the
             native build of the same package (a second browser, alongside the main walk)
  phone      the start page and the viewer at 390 x 844 with one-finger orbit and pinch zoom; the status page renders
  touch walk the walk on an emulated phone (844 x 390, DPR 3): welcome, the 1-D stick down the boarding line to the shut outer
             hatch, Use opens it, a look drag, Map and View (a side browser; emulation, not a phone's frame rate)
Screenshots, metrics and check.json go to --out; --record writes the summary into the site's release.json. It checks behaviour,
loading isolation and transfer sizes, not frame rates on real hardware. The viewer's camera damping is switched off before input.
--part runs one part (main: start, viewer, play, switching, phone, review; equivalence; walk); CI runs each on its own runner and --merge combines their check.json (a missing part fails), recording into
release.json with --record. On request only (not in CI): --part training plays the SYS-001 systems proof (#interior-systems) and the
DS-1 Deadship tutorial (#interior-deadship) with every action answered by the player's own key, then on an emulated phone by its
touch button, and saves their stills; --part training-scripted runs their scripted checks in the browser. --frame-shell runs the equivalence part in a Chrome headless shell with frames on demand (FramePump):
the same checks on the same 1/60 s frames, about ten times sooner than in real time.

    python3 tools/web_check.py <site dir> --out <dir> [--chrome google-chrome] [--record] [--part main|equivalence|walk ...] [--frame-shell <chrome-headless-shell>]
    python3 tools/web_check.py <site dir> --out <dir> --part training [--training systems|deadship] [--no-touch]
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



# CTRL-001: the stored line of one action in the controls profile, read straight from Godot's IndexedDB copy of user://.
IDB_LINE = """new Promise(r => { const q = indexedDB.open('/userfs'); q.onerror = () => r('');
  q.onsuccess = () => { try { const g = q.result.transaction('FILE_DATA').objectStore('FILE_DATA').get('/userfs/godot/app_userdata/Wayfarer/wayfarer_controls.cfg');
    g.onsuccess = () => { const v = g.result; const t = v && v.contents ? new TextDecoder().decode(v.contents) : '';
      const m = t.match(/^{key}=[\\s\\S]*?\\]$/m); r(m ? m[0].slice(0, 300) : ''); }; g.onerror = () => r(''); } catch (e) { r(''); } }; })"""

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
    def __init__(self, chrome, begin_frames=False):
        self.chrome = chrome
        target = chrome.send('Target.createTarget', {'url': 'about:blank', **({'enableBeginFrameControl': True} if begin_frames else {})})['targetId']
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

    def click(self, x, y, hold=0.08):
        # Explicit input timestamps: the release is `hold` seconds after the press, as a person's click, however long the page
        # takes to handle the press (a software-WebGL frame can take seconds and would otherwise read as a long press).
        t = time.time()
        self.mouse('mouseMoved', x, y)
        self.mouse('mousePressed', x, y, button='left', buttons=1, clickCount=1, timestamp=t)
        self.mouse('mouseReleased', x, y, button='left', buttons=0, clickCount=1, timestamp=t + hold)

    def touch(self, kind, points):
        self.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y, 'id': i} for i, (x, y) in enumerate(points)]})

    def screenshot(self, path, timeout=240):
        # A capture waits for the next compositor frame; a software-rendered Godot frame on a runner that also runs the touch
        # journey's browser can take minutes (main run 66 timed out twice at 60 s). Screenshots are evidence, not checks.
        Path(path).write_bytes(base64.b64decode(self.send('Page.captureScreenshot', {'format': 'png'}, timeout)['data']))

    def centre_of(self, selector):
        # scrolled into view first, as a visitor would, so a choice below the fold is still clicked where it is drawn
        return self.js(f'(() => {{ const e = document.querySelector({json.dumps(selector)}); '
                       f"e.scrollIntoView({{block: 'center', behavior: 'instant'}}); const r = e.getBoundingClientRect(); "
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


# The walk check in the Web build takes about 1,470 s in headless Chromium with drawing off (docs/MODEL.md EXC-001), so the
# equivalence part waits longer than the other play sessions.
EQUIVALENCE_SECONDS = 2700
HEAVY = ('.glb', '.wasm', '.pck', '/vendor/', 'engine-', 'walk-', 'viewer.js', 'draco')
# Frames per second of the page's own animation frames (Godot's main loop runs on them too) over a few seconds.
RAF_FPS = ('new Promise(r => { const t0 = performance.now(); let n = 0; const ts = []; let last = t0; '
           'const f = now => { n++; ts.push(now - last); last = now; if (now - t0 < {ms}) requestAnimationFrame(f); else { ts.sort((a, b) => a - b); '
           'r({fps: +(1000 * n / (now - t0)).toFixed(1), p95_ms: +ts[Math.floor(ts.length * 0.95)].toFixed(1), frames: n}); } }; '
           'requestAnimationFrame(f); })')


# EVA Operations check in the browser: with drawing off the Web build still steps once per animation frame, so --fixed-fps 60 runs
# at most in real time (the walk: 97,770 frames in 1,633 s). The budget follows the native reference's simulated time (1,102 s)
# with half again for a slower runner, and never less than the old 1,200 s.
EVA_SECONDS_MIN = 1200
# The engine quits right after printing its result line; its exit errors (leaked RIDs, ...) follow within a moment. Waiting for
# them before reading the console makes those errors count every time, instead of only when they happen to arrive first.
TEARDOWN_SECONDS = 5
EVA_SLACK = 1.5


class FramePump:
    """Animation frames on demand (Chrome headless shell, --enable-begin-frame-control): each HeadlessExperimental.beginFrame runs
    one frame, 1/60 s of frame time, as soon as the last one is done, instead of at the 60 Hz display cadence. With --fixed-fps 60 the
    engine steps exactly one 1/60 s frame per animation frame either way, so the walk and EVA checks see the same frames, only sooner."""

    def __init__(self, page):
        self.page, self.frames, self.stop = page, 0, threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        tick = 0.0
        while not self.stop.is_set():
            tick += 1000 / 60
            try:
                self.page.send('HeadlessExperimental.beginFrame', {'frameTimeTicks': tick, 'interval': 1000 / 60, 'noDisplayUpdates': True},
                               timeout=120)
                self.frames += 1
            except (RuntimeError, TimeoutError):   # mid-navigation, or the browser is closing
                time.sleep(0.05)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=10)


def run_equivalence(url, play_release, binary, sandbox, out, play_seconds, record_check, metrics, frame_shell=None):
    """The walk's own check (excursion check.gd: both rings round and back to the station by the player's actions) in the Web build
    against the native build of the same package (web_play.build), at a fixed 60 fps with drawing off (--disable-render-loop: logic,
    physics and input step exactly as when drawn; the main part covers rendering). Runs in its own browser, alongside the main walk.
    frame_shell: a Chrome headless shell binary; the part then runs there with frames on demand (FramePump), not in real time."""
    native = play_release.get('native_reference') or {}
    profile = tempfile.mkdtemp(prefix='wf-web-equivalence-')
    log = open(out / 'chrome-equivalence.log', 'w')
    chrome = Chrome(frame_shell or binary, profile, log, sandbox,
                    extra=('--enable-begin-frame-control', '--run-all-compositor-stages-before-draw') if frame_shell else ())
    pump = None
    try:
        page, traffic = Page(chrome, begin_frames=bool(frame_shell)), Traffic(chrome)
        pump = FramePump(page) if frame_shell else None
        page.send('Emulation.setDeviceMetricsOverride', {'width': 640, 'height': 400, 'deviceScaleFactor': 1, 'mobile': False})
        mark = traffic.mark()
        t0 = time.monotonic()
        query = '&'.join(f'arg={a}' for a in ('--disable-render-loop', '--fixed-fps', '60', '--', '--check-excursion'))
        page.send('Page.navigate', {'url': url + play_release['page'] + '?' + query})
        line = traffic.wait_console('WF_GODOT_EXCURSION ', mark, max(play_seconds, EQUIVALENCE_SECONDS))
        time.sleep(TEARDOWN_SECONDS if line else 0)
        errors = [text for kind, text in traffic.since(mark)[1] if text.startswith('ERROR')]
        web = json.loads(line.split(' ', 1)[1]) if line else None
        seconds = round(time.monotonic() - t0, 1)
        notes = sorted((web or {}).get('notes', {}))
        same = bool(web) and web.get('result') == native.get('result') and notes == native.get('notes')
        record_check('play: the walk check passes in the browser as natively', same and web.get('result') == 'PASS' and not errors,
                     web={k: (web or {}).get(k) for k in ('result', 'fails', 'physics_frames')}, native={k: native.get(k) for k in ('result', 'fails', 'physics_frames')},
                     notes_differ=sorted(set(notes) ^ set(native.get('notes') or []))[:8], errors=errors[:3], seconds=seconds)
        metrics['equivalence'] = {'web': web and {k: web.get(k) for k in ('result', 'physics_frames', 'wall_s')},
                                  'native': {k: native.get(k) for k in ('result', 'physics_frames', 'seconds')}, 'seconds': seconds,
                                  'frames': 'on demand (headless shell)' if pump else 'real time'}
        # EVA-OPS-001: the EVA Operations check (movement, gas, docking, drone, rescue, scripted First Flight) in the same browser
        nat_eva = native.get('eva_ops') or {}
        mark = traffic.mark()
        t0 = time.monotonic()
        query = '&'.join(f'arg={a}' for a in ('--disable-render-loop', '--fixed-fps', '60', '--', '--eva', '--check-eva-ops'))
        page.send('Page.navigate', {'url': url + play_release['page'] + '?' + query})
        line = traffic.wait_console('WF_GODOT_EVA_OPS ', mark, max(EVA_SECONDS_MIN, EVA_SLACK * float(nat_eva.get('sim_s') or 0) + 120))
        time.sleep(TEARDOWN_SECONDS if line else 0)
        # Errors up to the result line fail the check; engine messages printed after a PASS line (shutdown diagnostics such as
        # 'Pages in use exist at exit in PagedAllocator') are reported but do not fail it (owner decision 2026-11-07).
        texts = [text for kind, text in traffic.since(mark)[1]]
        cut = texts.index(line) if line in texts else len(texts)
        errors = [t for t in texts[:cut] if t.startswith('ERROR')]
        eva = json.loads(line.split(' ', 1)[1]) if line else None
        passed = bool(eva) and eva.get('result') == 'PASS'
        exit_errors = [t for t in texts[cut + 1:] if t.startswith('ERROR')]
        if not passed:
            errors += exit_errors
            exit_errors = []
        record_check('play: the EVA Operations check passes in the browser as natively',
                     passed and nat_eva.get('result') == 'PASS' and len(eva.get('tests', {})) == nat_eva.get('checks')
                     and not errors, web={k: (eva or {}).get(k) for k in ('result', 'fail', 'sim_s', 'wall_s')}, native=nat_eva, errors=errors[:3],
                     exit_messages=exit_errors[:5], seconds=round(time.monotonic() - t0, 1))
        if exit_errors and os.environ.get('GITHUB_ACTIONS'):
            print(f'::warning title=web check::EVA Operations engine exit messages after PASS: {json.dumps(exit_errors[:5])}', flush=True)
    except Exception as error:
        log.flush()
        record_check('play: equivalence browser session', False, error=repr(error),
                     chrome_log=(out / 'chrome-equivalence.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        if pump:
            pump.close()          # before the browser goes: a frame in flight then still gets its reply
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


class JourneyStop(Exception):
    pass


def run_touch_walk(url, play_release, binary, sandbox, out, record_check, metrics, timeout=150):
    """EXC-001 on an emulated phone (844 x 390 CSS px, DPR 3, landscape): the walk starts as the package's main scene, the
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
        page.send('Page.navigate', {'url': url + play_release['page'] + '?arg=--&arg=--touch-probe&arg=--excursion'})   # the boarding-line start
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


# SYS-001 / DS-1 (opt-in part "training", not in the CI parts): the systems proof (#interior-systems) and the Deadship scrubber
# tutorial (#interior-deadship) run their own checks in the browser with --await-player. The check walks the trainee as before, but
# at every player action it stops and asks (WF_AWAIT); this driver answers with the player's own input: the key the page publishes
# for that action (window.wayfarerControls.keys) on a desktop, the on-screen button (window.wayfarerTouch) on an emulated phone.
# The scene's own input handling then performs the action; a still asked for (WF_SHOT) is a DevTools screenshot of the page. The engine
# runs with --disable-render-loop (software WebGL draws the ship at about 1 frame/s) and draws only for each still.
TRAINING = (('systems', '#interior-systems', ('--systems', '--check-systems'), 'WF_GODOT_SYSTEMS '),
            ('deadship', '#interior-deadship', ('--deadship', '--check-deadship'), 'WF_GODOT_DEADSHIP '))
TRAINING_SECONDS = 2400


def cdp_key(label):
    """The DevTools key event of a published binding label's first keyboard entry ('E · X button' -> E), or None."""
    named = {'Space': ('Space', 32, ' '), 'Enter': ('Enter', 13, 'Enter'), 'Tab': ('Tab', 9, 'Tab'),
             '↑': ('ArrowUp', 38, 'ArrowUp'), '↓': ('ArrowDown', 40, 'ArrowDown'), '←': ('ArrowLeft', 37, 'ArrowLeft'), '→': ('ArrowRight', 39, 'ArrowRight')}
    for part in str(label or '').split(' · '):
        part = part.strip()
        if len(part) == 1 and part.isalnum():
            u = part.upper()
            return ('Key' + u if u.isalpha() else 'Digit' + u), ord(u), part.lower()
        if part in named:
            return named[part]
    return None


def run_training(url, play_release, binary, sandbox, out, record_check, metrics, touch=False, scripted=False, names=None):
    """Each training's own check in the browser. touch: an emulated phone answering by its on-screen buttons. scripted: no
    --await-player (the check itself calls the handlers: an in-browser engine run, not player input; the Phase 0 site has no other)."""
    how = 'scripted' if scripted else ('touch' if touch else 'keys')
    profile = tempfile.mkdtemp(prefix=f'wf-web-training-{how}-')
    log = open(out / f'chrome-training-{how}.log', 'w')
    chrome = Chrome(binary, profile, log, sandbox)
    shots_dir = out / 'training'
    shots_dir.mkdir(exist_ok=True)
    runs = metrics.setdefault('training', {})
    try:
        page, traffic = Page(chrome), Traffic(chrome)
        if touch:
            page.send('Emulation.setDeviceMetricsOverride', {'width': 844, 'height': 390, 'deviceScaleFactor': 3, 'mobile': True,
                                                              'screenOrientation': {'type': 'landscapePrimary', 'angle': 90}})
            page.send('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5})
        else:
            page.send('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
        for name, hash_, flags, line_prefix in TRAINING:
            if names and name not in names:
                continue
            mark = traffic.mark()
            t0 = time.monotonic()
            args = ['--disable-render-loop', '--fixed-fps', '60', '--', *flags, *([] if scripted else ['--await-player']), *(['--touch-probe'] if touch else [])]
            page.send('Page.navigate', {'url': url + play_release['page'] + '?' + '&'.join(f'arg={a}' for a in args) + hash_})
            answered, seen, shots, line = [], 0, [], None
            beat = time.monotonic() + 30
            end = time.monotonic() + TRAINING_SECONDS
            while time.monotonic() < end and not traffic.crashed:
                lines = [t for _, t in traffic.since(mark)[1]]
                for text in lines[seen:]:
                    if os.environ.get('WF_TRAINING_TRACE') or text.startswith(('WF_', 'ERROR', 'SCRIPT ERROR', 'Godot Engine', 'check:')):
                        print(f'  [{name} {how} {round(time.monotonic() - t0)} s] {text[:160]}', flush=True)
                    if text.startswith('WF_AWAIT '):
                        rec = json.loads(text.split(' ', 1)[1])
                        if touch:
                            b = None
                            for _ in range(120):
                                st = page.js('window.wayfarerTouch || null') or {}
                                b = next((b for b in st.get('buttons', []) if b[0] == rec['action']), None)
                                if b:
                                    break
                                time.sleep(0.25)
                            if b:
                                at = (b[2][0] + b[2][2] / 2, b[2][1] + b[2][3] / 2)
                                page.touch('touchStart', [at])
                                time.sleep(0.15)
                                page.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                            answered.append({**rec, 'input': 'tap ' + (b[1] if b else 'NO BUTTON')})
                        else:
                            label = (page.js('window.wayfarerControls && window.wayfarerControls.keys') or {}).get(rec['action'])
                            k = cdp_key(label)
                            if k:
                                page.js("document.querySelector('canvas') && document.querySelector('canvas').focus()")
                                page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': k[2], 'code': k[0], 'windowsVirtualKeyCode': k[1]})
                                time.sleep(0.15)
                                page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': k[2], 'code': k[0], 'windowsVirtualKeyCode': k[1]})
                            answered.append({**rec, 'input': f'key {label}' if k else f'NO KEY for {label}'})
                    elif text.startswith('WF_SHOT '):
                        shot = text.split(' ', 1)[1].strip()
                        try:
                            page.screenshot(shots_dir / f'{name}_{how}_{shot}.png')
                            shots.append(shot)
                        finally:
                            page.js(f'window.wayfarerShotDone = {json.dumps(shot)}')
                    elif text.startswith(line_prefix):
                        line = text
                seen = len(lines)
                if line:
                    break
                if time.monotonic() > beat:              # a heartbeat: where the trainee is and how fast the page runs
                    beat = time.monotonic() + 60
                    try:
                        w = page.js('window.wayfarerWalk || null') or {}
                        fps = page.js(RAF_FPS.replace('{ms}', '2000'), timeout=30)
                        print(f'  [{name} {how} {round(time.monotonic() - t0)} s] at {[round(w.get(k, 0), 1) for k in "xyz"]} {fps}', flush=True)
                    except (RuntimeError, TimeoutError) as e:
                        print(f'  [{name} {how}] heartbeat: {e!r}'[:200], flush=True)
                time.sleep(0.25)
            time.sleep(TEARDOWN_SECONDS if line else 0)
            texts = [t for _, t in traffic.since(mark)[1]]
            cut = texts.index(line) if line in texts else len(texts)
            errors = [t for t in texts[:cut] if t.startswith(('ERROR', 'SCRIPT ERROR'))]
            res = json.loads(line.split(' ', 1)[1]) if line else {}
            seconds = round(time.monotonic() - t0, 1)
            real = scripted or (answered and all(not a['input'].startswith('NO ') for a in answered))
            what = {'scripted': 'its scripted check passes in the browser (engine run, no player input)',
                    'keys': "every action answered by the player's own key in the browser",
                    'touch': "every action answered by an on-screen button on an emulated phone"}[how]
            record_check(f'training: {name}: {what}', res.get('result') == 'PASS' and real and not errors and not traffic.crashed,
                         result=res.get('result'), fails=res.get('fails', [])[:5], answered=answered, shots=shots, errors=errors[:3],
                         physics_frames=res.get('physics_frames'), seconds=seconds)
            runs[f'{name}_{how}'] = {'result': res.get('result'), 'answered': len(answered), 'shots': shots, 'seconds': seconds,
                                     'physics_frames': res.get('physics_frames')}
            (shots_dir / f'{name}_{how}.json').write_text(json.dumps({'result': res, 'answered': answered, 'errors': errors}, indent=1) + '\n')
    except Exception as error:
        log.flush()
        record_check(f'training: {how} browser session', False, error=repr(error),
                     chrome_log=(out / f'chrome-training-{how}.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


def run_main(url, release, build, binary, sandbox, out, record_check, metrics):
    """The visitor's walk in one browser: start page, Explore Ship, Explore Interior and Explore Exterior, switching and memory, phone, review."""
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
        names = sorted({u[len(url):] or 'index.html' for u, *_ in reqs if not u.startswith(('data:', 'blob:'))})     # inline images are no request
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
        page.wait("document.readyState === 'complete' && !!document.getElementById('go-interior')", 30)
        heaps.append(('start after viewer', heap(settled)))

        # C: the two experiences, each from its start-page choice: the launcher loads no engine; Start loads the engine and the pack
        # and starts the right scene (the hash picks it; one package holds both); the player can act; Exit returns to that launcher.
        if play_release:
            def key(k, code, vk, hold=0.0):
                page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': k, 'code': code, 'windowsVirtualKeyCode': vk})
                time.sleep(hold)
                page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': k, 'code': code, 'windowsVirtualKeyCode': vk})

            # CTRL-001: the controls state the engine publishes (window.wayfarerControls) and a key press the setup can read
            CTL = 'window.wayfarerControls'
            KEYS = {'ArrowUp': ('ArrowUp', 38), 'ArrowDown': ('ArrowDown', 40), 'ArrowLeft': ('ArrowLeft', 37), 'ArrowRight': ('ArrowRight', 39),
                    ' ': ('Space', 32), 'Shift': ('ShiftLeft', 16), ',': ('Comma', 188), '.': ('Period', 190), '9': ('Digit9', 57),
                    'w': ('KeyW', 87), 'F10': ('F10', 121), 'Enter': ('Enter', 13), 'Escape': ('Escape', 27)}

            def press(k, hold=0.15):
                code, vk = KEYS[k]
                key(k, code, vk, hold)

            def answer(keys, timeout=120):
                """Answers the setup's questions in order; returns [(asked, key)] and whether each answer moved the setup on."""
                got = []
                for k in keys:
                    asked = page.js(f'{CTL} && {CTL}.asking')
                    press(k)
                    moved = page.wait(f"{CTL} && ({CTL}.asking !== {json.dumps(asked)} || {CTL}.state === '')", timeout)
                    got.append((asked, k, bool(moved)))
                return got

            def walk_until(k, timeout, metres=0.5):
                code, vk = KEYS[k]
                before = page.js('window.wayfarerWalk')
                page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': k, 'code': code, 'windowsVirtualKeyCode': vk})
                moved = page.wait(f"window.wayfarerWalk && Math.hypot(window.wayfarerWalk.x - {before['x']}, window.wayfarerWalk.y - {before['y']}, "
                                  f"window.wayfarerWalk.z - {before['z']}) > {metres}" if before else 'false', timeout)
                page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': k, 'code': code, 'windowsVirtualKeyCode': vk})
                return bool(moved), before, page.js('window.wayfarerWalk')

            def launcher(name):
                mark = traffic.mark()
                page.click(*page.centre_of(f'#go-{name}'))
                page.wait("document.readyState === 'complete' && !document.getElementById('start').disabled && "
                          "document.getElementById('size').textContent.includes('MB')", 30)
                reqs, _ = traffic.since(mark)
                heavy = [u for u, *_ in reqs if any(h in u for h in HEAVY)]
                record_check(f'play launcher: {name} loads no engine or pack before Start', not heavy and page.js('location.pathname').endswith(f'/{name}/'),
                             requests=sorted({u[len(url):] for u, *_ in reqs}))
                page.screenshot(out / f'{name}_launcher.png')

            def start(name, ready_line):
                mark = traffic.mark()
                t0 = time.monotonic()
                page.click(*page.centre_of('#start'))
                running = page.wait("window.wayfarerPlay && ['running', 'failed'].includes(window.wayfarerPlay.state)", 300) and \
                    page.js("window.wayfarerPlay.state") == 'running'
                seconds = round(time.monotonic() - t0, 1)
                booted = traffic.wait_console('Godot Engine v', mark, 30)
                ready = traffic.wait_console(ready_line, mark, 300) if running else None
                time.sleep(3)
                lines = traffic.since(mark)[1]
                other = [t for _, t in lines if t.startswith(('WF_EXCURSION ready', 'WF_EVA_OPS ready')) and not t.startswith(ready_line)]
                identity = {'experience': page.js('window.wayfarerPlay && window.wayfarerPlay.experience'), 'hash': page.js('location.hash'),
                            'exit': page.js("document.getElementById('exit').getAttribute('href')"), 'title': page.js("document.getElementById('title').textContent")}
                record_check(f'play: {name} starts the engine and its own scene', running and booted and ready and not other
                             and identity['experience'] == name and identity['exit'] == f'../{name}/' and identity['hash'] == f'#{name}',
                             seconds=seconds, engine=booted, ready=ready, other_scene=other, **identity, state=page.js('window.wayfarerPlay'))
                return mark, running, seconds

            def leave(name):
                # the in-game Exit link returns to this experience's launcher, its Back link to the start page
                page.click(*page.centre_of('#exit'))
                back = page.wait("document.readyState === 'complete' && !!document.getElementById('start')", 30)
                record_check(f'play: Exit from {name} returns to its launcher', back and page.js('location.pathname').endswith(f'/{name}/'),
                             path=page.js('location.pathname'))
                page.click(*page.centre_of('.sitebar .mark'))      # the site mark returns to the start page
                page.wait("document.readyState === 'complete' && !!document.getElementById('go-viewer')", 30)
                heaps.append((f'start after {name}', heap(settled)))

            def after(mark, name):
                reqs, lines = traffic.since(mark)
                viewer = [u for u, *_ in reqs if '/viewer/' in u]
                record_check(f'play: {name} requested no Explore Ship file', not viewer, viewer_requests=viewer[:3])
                requests_ok(f'play: {name}: every request served from the project subpath', reqs)
                errors = [text for kind, text in lines if kind in ('error', 'exception') and not text.startswith('   at:')]
                record_check(f'play: {name}: no engine or script errors', not errors and not traffic.crashed, errors=errors[:5], crashed=traffic.crashed)
                return reqs

            # Explore Interior (LOCO-001): the trainee stands on ring A's deck in spin gravity, as the newcomer model. W walks (the state
            # record shows the walk clip), Space jumps once and the trainee lands again.
            launcher('interior')
            mark, running, play_s = start('interior', 'WF_EXCURSION ready')
            if running:
                # CTRL-001: this browser profile is new (a fresh Chrome profile per run): the controls setup opens before anything moves,
                # asking for Move forward first. The player answers with keys of their own (the arrows, Space, Shift), never the
                # suggested W/A/S/D; nothing is put into the profile beforehand.
                setup = page.wait(f"{CTL} && {CTL}.state === 'listen' && {CTL}.mode === 'setup'", 120) and page.js(CTL)
                page.screenshot(out / 'interior_first_launch.png')
                record_check('controls: a new browser profile opens the controls setup, Move forward first',
                             bool(setup) and setup['asking'] == 'player.move_forward' and setup['experience'] == 'interior'
                             and setup['missing'][:1] == ['player.move_forward'] and setup['profile'] == 'new', state=setup)
                answers = answer(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'Shift'])
                done = page.wait(f"{CTL} && {CTL}.state === '' && {CTL}.missing.length === 0", 60) and page.js(CTL)
                record_check('controls: the setup takes the chosen keys and closes',
                             bool(done) and [a for a, *_ in answers] == ['player.move_forward', 'player.move_back', 'player.move_left', 'player.move_right',
                                                                          'exc.jump', 'exc.run'] and all(m for *_, m in answers)
                             and done['keys']['player.move_forward'].startswith('↑') and done['keys']['exc.run'].startswith('Shift'),
                             answers=answers, state=done, persistent=(done or {}).get('persistent'))
                time.sleep(3)
                page.wait('!!window.wayfarerWalk', 60)
                before = page.js('window.wayfarerWalk')
                record_check('play: interior: the trainee stands on ring A at about 0.5 g as the newcomer model', bool(before)
                             and before.get('start') == 'RING' and before.get('zone') == 'RING_A' and before.get('move') == 'WALK'
                             and before.get('model') is True and 0.45 < (before.get('g') or 0) < 0.55, state=before)
                # W, the old default, is not the player's key: held for 30 s it moves nothing.
                w_moved, w_before, w_after = walk_until('w', 30, metres=0.05)
                record_check('controls: the old default W does not move the trainee', not w_moved, before=w_before, after=w_after)
                # The chosen Move forward held: a software-rendered runner steps physics at a fraction of real time (as in the touch
                # walk), so the key stays down until the body has moved.
                t_w = time.monotonic()
                dist = lambda a, b: math.dist([a[k] for k in 'xyz'], [b[k] for k in 'xyz']) if a and b else 0.0
                page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'ArrowUp', 'code': 'ArrowUp', 'windowsVirtualKeyCode': 38})
                walked = page.wait(f"window.wayfarerWalk && window.wayfarerWalk.clip === 'walk' && Math.hypot(window.wayfarerWalk.x - {before['x']}, "
                                  f"window.wayfarerWalk.y - {before['y']}, window.wayfarerWalk.z - {before['z']}) > 0.5" if before else 'false', 180)
                page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'ArrowUp', 'code': 'ArrowUp', 'windowsVirtualKeyCode': 38})
                now = page.js('window.wayfarerWalk')
                record_check('play: interior: the trainee walks on the chosen Move forward (↑) with the walk clip', bool(before) and walked and dist(before, now) > 0.5,
                             metres=round(dist(before, now), 2), seconds=round(time.monotonic() - t_w, 1), before=before, after=now)
                page.wait("window.wayfarerWalk && window.wayfarerWalk.state === 'GROUND' && window.wayfarerWalk.speed < 0.1", 60)
                key(' ', 'Space', 32)
                jumped = page.wait('window.wayfarerWalk && window.wayfarerWalk.jumps >= 1 && window.wayfarerWalk.landings >= 1', 120)
                record_check('play: interior: the chosen Jump (Space) jumps once and the trainee lands', jumped, state=page.js('window.wayfarerWalk'))
                # The Controls menu (F10 here; the Controls button is the pointer route): Move forward changes from ↑ to W at once.
                press('F10')
                opened = page.wait(f"{CTL} && {CTL}.state === 'codex'", 60)
                page.screenshot(out / 'interior_controls_menu.png')
                for _ in range(40):
                    if page.js(f"{CTL}.pick") == 'player.move_forward':
                        break
                    press('ArrowDown', 0.05)
                    page.wait(f"{CTL} && {CTL}.pick !== ''", 10)
                picked = page.js(f"{CTL}.pick") == 'player.move_forward'
                press('Enter')
                listening = page.wait(f"{CTL} && {CTL}.state === 'listen' && {CTL}.mode === 'rebind'", 60)
                press('w')
                changed = page.wait(f"{CTL} && {CTL}.state === 'codex' && {CTL}.keys['player.move_forward'].startsWith('W')", 60)
                press('Escape')
                closed = page.wait(f"{CTL} && {CTL}.state === ''", 60)
                moved_w, *_ = walk_until('w', 180)
                record_check('controls: the Controls menu changes Move forward to W and it works at once',
                             bool(opened and picked and listening and changed and closed and moved_w), opened=opened, picked=picked, listening=listening,
                             changed=changed, closed=closed, walked=moved_w, state=page.js(CTL))
                # The same browser profile after a reload: the choices are restored and no setup is asked again.
                # Godot copies user:// to IndexedDB on its own schedule after a save (tens of seconds with software
                # rendering on a CI runner); reload only once the stored profile holds W (KEY_W = 87), as a player would.
                stored = page.wait(IDB_LINE.replace('{key}', 'player.move_forward') + ".then(l => /\"k\": 87,/.test(l.split('}')[0]))", 180)
                record_check('controls: the changed key reaches the browser storage (IndexedDB)', bool(stored),
                             line=page.js(IDB_LINE.replace('{key}', 'player.move_forward')))
                mark_r = traffic.mark()
                page.send('Page.reload', {})
                reloaded = traffic.wait_console('WF_EXCURSION ready', mark_r, 300)
                restored = page.wait(f"{CTL} && {CTL}.experience === 'interior'", 60) and (time.sleep(5) or page.js(CTL))
                page.wait('!!window.wayfarerWalk', 60)
                moved_r, *_ = walk_until('w', 180)
                record_check('controls: after a reload the same profile keeps W and asks nothing',
                             bool(reloaded and restored) and restored['state'] == '' and restored['missing'] == []
                             and restored['keys']['player.move_forward'].startswith('W') and restored['profile'] == '' and moved_r,
                             state=restored, walked=moved_r)
                fps = page.js(RAF_FPS.replace('{ms}', '8000'), timeout=120)
                page.screenshot(out / 'interior_running.png')
                reqs = after(mark, 'interior')
                metrics['play'] = {'interactive_s': play_s, 'transferred_bytes': sum(b for _, _, b, _ in reqs), 'requests': len(reqs),
                                   'raf': fps, 'start_ms': page.js('window.wayfarerPlay.start_ms'), 'renderer_rss_mb': rss(chrome.process.pid, 'renderer'),
                                   'renderer': 'SwiftShader software WebGL, 1280x800'}
            leave('interior')
            canvases = page.js("document.querySelectorAll('canvas').length")
            record_check('switching: back on the start page with no canvas or engine left', canvases == 0 and not page.js('!!window.Engine'))

            # Explore Exterior (LOCO-002): standing on the magnetic walkway in drift, both boots attached, the Y155 suit model, drone docked,
            # tether clipped. W (the player's Move forward) walks on the boots, 9 (their boots key) releases them, R thrusts away from
            # the plate, X releases the drone, 2 takes it.
            launcher('exterior')
            mark, running, play_s = start('exterior', 'WF_EVA_OPS ready')
            if running:
                # CTRL-001: the moves chosen in Explore Interior carry over; the setup asks only turning and the magnetic boots.
                ext = page.wait(f"{CTL} && {CTL}.state === 'listen' && {CTL}.mode === 'setup'", 120) and page.js(CTL)
                page.screenshot(out / 'exterior_first_launch.png')
                record_check('controls: Explore Exterior reuses the shared moves and asks only what it adds',
                             bool(ext) and ext['missing'] == ['evaops.yaw_left', 'evaops.yaw_right', 'evaops.boots'] and ext['asking'] == 'evaops.yaw_left'
                             and ext['keys']['evaops.fwd'].startswith('W'), state=ext)
                ext_answers = answer([',', '.', '9'])
                ext_done = page.wait(f"{CTL} && {CTL}.state === '' && {CTL}.missing.length === 0", 60) and page.js(CTL)
                record_check('controls: the exterior setup takes the chosen keys', bool(ext_done) and all(m for *_, m in ext_answers)
                             and ext_done['keys']['evaops.boots'] == '9', answers=ext_answers, state=ext_done)
                time.sleep(2)
                eva0 = page.wait("window.wayfarerEva && window.wayfarerEva.active === 'suit'", 60) and page.js('window.wayfarerEva')
                boots0 = (eva0 or {}).get('boots') or {}
                record_check('play: exterior starts on the magnetic walkway: both boots attached, suit model, drone docked, tether clipped',
                             bool(eva0) and eva0.get('start') == 'WALKWAY' and boots0.get('attached') == 2 and eva0.get('model') is True
                             and eva0['docked'] and eva0.get('tether') and not eva0['held'] and not eva0['scenario'], state=eva0)
                # The state record comes once a game second, and a software-rendered runner plays game time at a fraction of real time
                # (CI run 214: 4 game seconds in 80 s), so each step waits long enough and a held key stays down until the state follows.
                page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'w', 'code': 'KeyW', 'windowsVirtualKeyCode': 87})
                walking = page.wait("window.wayfarerEva && window.wayfarerEva.v_suit > 0.05 && window.wayfarerEva.boots.attached >= 1 "
                                    "&& window.wayfarerEva.clip === 'eva_mag_walk'", 120)
                page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'w', 'code': 'KeyW', 'windowsVirtualKeyCode': 87})
                mag_walk = page.js('window.wayfarerEva')
                page.screenshot(out / 'exterior_mag_walk.png')
                press('9')                                     # the player's Magnetic boots key (chosen above; V is not theirs)
                released = page.wait('window.wayfarerEva && window.wayfarerEva.boots.armed === false && window.wayfarerEva.boots.attached === 0', 90)
                page.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'r', 'code': 'KeyR', 'windowsVirtualKeyCode': 82})
                lifted = page.wait('window.wayfarerEva && window.wayfarerEva.v_suit > 0.005 && window.wayfarerEva.standing === false', 90)
                page.send('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'r', 'code': 'KeyR', 'windowsVirtualKeyCode': 82})
                key('x', 'KeyX', 88)
                undocked = page.wait('window.wayfarerEva && window.wayfarerEva.docked === false', 90)
                key('2', 'Digit2', 50)
                drone = page.wait("window.wayfarerEva && window.wayfarerEva.active === 'drone'", 90)
                time.sleep(2)
                page.screenshot(out / 'exterior_running.png')
                record_check('play: exterior: the astronaut walks on the boots, releases them, thrusts off, releases the drone and hands it control',
                             walking and released and lifted and undocked and drone, walking=walking, released=released, lifted=lifted,
                             undocked=undocked, drone=drone, mag_walk=mag_walk, state=page.js('window.wayfarerEva'))
                metrics['exterior'] = {'interactive_s': play_s, 'start_ms': page.js('window.wayfarerPlay.start_ms'),
                                       'renderer_rss_mb': rss(chrome.process.pid, 'renderer'), 'renderer': 'SwiftShader software WebGL, 1280x800'}
                after(mark, 'exterior')
            leave('exterior')
            canvases = page.js("document.querySelectorAll('canvas').length")
            record_check('switching: back on the start page after Explore Exterior with no canvas or engine left', canvases == 0 and not page.js('!!window.Engine'))

            # D: the other experience again after the game: the viewer still starts.
            page.click(*page.centre_of('#go-viewer'))
            again = page.wait('!!(window.wayfarer && window.wayfarer.model)', 240)
            record_check('switching: Explore Ship starts again after the experiences', again)
            page.click(*page.centre_of('a.back'))
            page.wait("document.readyState === 'complete' && !!document.getElementById('go-viewer')", 30)
            heaps.append(('start after second viewer', heap(settled)))
            record_check('switching: renderer memory returns to the start-page level after each experience',
                         all(h <= settled for _, h in heaps) and not traffic.crashed, renderer_rss_mb=heaps, crashed=traffic.crashed)
            metrics['memory'] = {'renderer_rss_mb': heaps, 'in_viewer_mb': metrics['viewer'].get('renderer_rss_mb'),
                                 'in_play_mb': metrics.get('play', {}).get('renderer_rss_mb'), 'in_exterior_mb': metrics.get('exterior', {}).get('renderer_rss_mb'),
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
        page.send('Page.navigate', {'url': url + 'status/'})
        rendered = page.wait("document.querySelectorAll('section.panel').length >= 6", 30)
        record_check('status page renders release.json', rendered and release['release'] in page.js('document.body.innerText'))
        page.screenshot(out / 'status.png')
    except SystemExit:
        pass
    except Exception as error:      # a browser session failure is a failed check with Chrome's own last words
        log.flush()
        record_check('browser session', False, error=repr(error), chrome_log=(out / 'chrome.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


PARTS = ('main', 'equivalence', 'walk')     # the main visitor walk, browser-vs-native, the touch walk
OPTIONAL_PARTS = ('training', 'training-scripted')   # on request only (not in CI): the SYS-001 / DS-1 trainings, see run_training


def record_release(site, release, results, metrics, version):
    """Writes the summary and metrics into the site's release.json (tests)."""
    group = lambda prefix: [r for r in results if r['check'].split(':')[0] in prefix]
    summary = lambda rs: rs and {'result': 'PASS' if all(r['ok'] for r in rs) else 'FAIL', 'passed': sum(r['ok'] for r in rs),
                                 'total': len(rs), 'failed': [r['check'] for r in rs if not r['ok']], 'browser': version}
    release['tests'] = {'viewer': summary(group(('viewer', 'phone'))), 'isolation': summary(group(('start', 'play launcher', 'switching'))),
                        'play': summary(group(('play',))), 'touch': summary(group(('touch',))), 'all': summary(results), 'metrics': metrics}
    equivalence = [r for r in results if r['check'].startswith('play: the walk check')]
    if equivalence:
        eq = metrics.get('equivalence') or {}
        release['tests']['equivalence'] = {
            'result': 'PASS' if all(r['ok'] for r in equivalence) else 'FAIL',
            'note': f"browser vs native on the same package: the walk check at a fixed 60 fps, {(eq.get('web') or {}).get('physics_frames', '-')} "
                    f"physics frames in the browser vs {(eq.get('native') or {}).get('physics_frames', '-')} natively, same result and milestones"}
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


def check(site, out, binary, sandbox=True, record=False, play_seconds=900, live=None, recording=True, touch=True, parts=PARTS,
          frame_shell=None, training_names=None):
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

    equivalence = 'equivalence' in parts and recording
    side_parts = [k for k in ('walk',) if touch and k in parts]
    # The side browser runs the equivalence session and then the touch journey and the touch walk (at most two browsers share a
    # runner with the main walk; CI runs each part on its own runner and merges them, --part and --merge).
    def side_work():
        if equivalence:
            run_equivalence(url, play_release, binary, sandbox, out, play_seconds, record_check, metrics, frame_shell)
        if 'walk' in side_parts:
            run_touch_walk(url, play_release, binary, sandbox, out, record_check, metrics)
    side = threading.Thread(target=side_work) if play_release and (equivalence or side_parts) else None
    t0 = time.monotonic()
    if side:
        side.start()
    try:
        if 'main' in parts:
            run_main(url, release, build, binary, sandbox, out, record_check, metrics)
        if 'training' in parts and play_release:
            run_training(url, play_release, binary, sandbox, out, record_check, metrics, names=training_names)
            if touch:
                run_training(url, play_release, binary, sandbox, out, record_check, metrics, touch=True, names=training_names)
        if 'training-scripted' in parts and play_release:
            run_training(url, play_release, binary, sandbox, out, record_check, metrics, scripted=True, names=training_names)
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
    parser.add_argument('--no-recording', action='store_true', help='skip the browser-vs-native walk check')
    parser.add_argument('--no-touch', action='store_true', help='skip the emulated-phone touch journey')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--chrome', default=os.environ.get('CHROME', 'google-chrome'))
    parser.add_argument('--no-sandbox', action='store_true', help="disposable CI VMs whose AppArmor blocks Chrome's namespace sandbox")
    parser.add_argument('--record', action='store_true', help="write the results into the site's release.json (tests)")
    parser.add_argument('--play-seconds', type=int, default=900, help='time allowed for the browser walk check')
    parser.add_argument('--part', action='append', choices=PARTS + OPTIONAL_PARTS,
                        help='run only this part (repeatable; default the CI parts main, equivalence, walk); training: the systems proof and the '
                             'Deadship tutorial answered by real keys and touch; training-scripted: their scripted checks in the browser')
    parser.add_argument('--training', action='append', choices=[t[0] for t in TRAINING], help='with training or training-scripted: only these trainings')
    parser.add_argument('--frame-shell', type=Path, help='Chrome headless shell binary: run the equivalence part there with frames on demand '
                        '(begin-frame control) instead of in real time; same checks, same frames')
    parser.add_argument('--merge', type=Path, nargs='+', metavar='DIR', help="merge these parts' check.json into --out (with --record, into the site)")
    args = parser.parse_args()
    if args.merge:
        report = merge(args.site.resolve(), [d.resolve() for d in args.merge], args.out.resolve(), record=args.record)
    else:
        report = check(args.site and args.site.resolve(), args.out.resolve(), args.chrome, sandbox=not args.no_sandbox, record=args.record,
                       play_seconds=args.play_seconds, live=args.live, recording=not args.no_recording, touch=not args.no_touch,
                       parts=tuple(args.part or PARTS), frame_shell=args.frame_shell and str(args.frame_shell.resolve()),
                       training_names=args.training)
    print(report['result'], f"{sum(r['ok'] for r in report['checks'])}/{len(report['checks'])} checks")
    if os.environ.get('GITHUB_ACTIONS'):
        loads = {r['check']: r.get('seconds') for r in report['checks'] if 'seconds' in r}
        print(f"::notice title=web check::{report['result']} {sum(r['ok'] for r in report['checks'])}/{len(report['checks'])}; {report['browser']}; load s {loads}")
    sys.exit(report['result'] != 'PASS')
