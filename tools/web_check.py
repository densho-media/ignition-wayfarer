"""Browser check of the Wayfarer site: headless Chrome over the DevTools pipe (standard library only).

Serves the site under /ignition-wayfarer/ (the GitHub Pages project path) with software WebGL (SwiftShader) and the cache off,
and walks it as a visitor does, recording every request:
  start      the start page loads only index.html, site.css and release.json: no model, engine or library, no canvas
  viewer     Explore Ship from its link: whole-ship framing, orbit, zoom, pan, reset, presets, picking, assembly hiding, the
             #cam bookmark, no Enter Wayfarer file requested
  play       the launcher requests no engine before Start; Start boots Godot and Demonstrator 01 with no viewer file, no error
  switching  Exit back to the start page, Explore Ship again; page-renderer memory returns to the start-page level (Chrome runs
             with the back-forward cache off, so this measures what the pages release)
  equivalence  Demonstrator 01's 68-check suite and its whole-journey autoplay recording, drawing off, must match the native build
             of the same package check by check and frame by frame (a second browser, alongside the walk)
  phone      the start page and the viewer at 390 x 844 with one-finger orbit and pinch zoom; the review page renders
  touch      Enter Wayfarer on an emulated phone (844 x 390, DPR 3) played by touch from the welcome to ring A, upright and tablet
             sizes (a third browser, alongside the walk; emulation, not a phone's frame rate)
Screenshots, metrics and check.json go to --out; --record writes the summary into the site's release.json. It checks behaviour,
loading isolation and transfer sizes, not frame rates on real hardware. The viewer's camera damping is switched off before input.

    python3 tools/web_check.py <site dir> --out <dir> [--chrome google-chrome] [--record]
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

    def screenshot(self, path):
        Path(path).write_bytes(base64.b64decode(self.send('Page.captureScreenshot', {'format': 'png'})['data']))

    def centre_of(self, selector):
        return self.js(f'(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); '
                       f'return [r.x + r.width / 2, r.y + r.height / 2]; }})()')


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


def run_touch(url, play_release, binary, sandbox, out, record_check, metrics, timeout=300):
    """MOB-001: Enter Wayfarer played by touch on an emulated phone (844 x 390 CSS px, DPR 3, touch, landscape), in its own browser
    alongside the walk. CDP touch events go through the browser into Godot as a phone's would; the game publishes its touch state
    (window.wayfarerTouch, -- --touch-probe) and the check reads it. Covers the touch welcome, Skip, Pause, the rail stick with the
    look finger at once, release, weightless (no stick, no force; look; Push off), Map and the systems card, the transfer line,
    walking on ring A with Drop by a second finger, Help as a modal, portrait and a tablet size keeping the same run. Emulation,
    not a phone: it says nothing about a phone's frame rate."""
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
        s = until(lambda s: s['mode'] == 'welcome' and s['panel'])
        record_check('touch: phone detected, CSS-pixel interface, welcome without a key', s and s['primary'] and s['density'] == 3
                     and s['ui'] == [844, 390], seconds=round(time.monotonic() - t0, 1), scale_3d=s and s['scale_3d'])
        page.screenshot(out / 'touch_1_welcome.png')
        tap_at(next((centre(r) for t, r in (s or {}).get('panel', []) if t.startswith('Start with tips')), (422, 300)))
        s = until(lambda s: s['mode'] == '' and s['intro_done'])
        record_check('touch: welcome completed by a tap (tips on)', s and s['preference'] == 'SUGGESTED')
        page.frames(2)
        page.screenshot(out / 'touch_2_exterior.png')
        record_check('touch: guided chapter offers Pause and Skip, no stick', s and s['move'] == '' and {'demo.pause', 'ui.confirm'} <= set(buttons(s)),
                     buttons=buttons(s))
        tap('ui.confirm')
        tap('demo.pause')
        s = until(lambda s: scene(s)['chapter'] == 'ENTRY' and scene(s)['paused'])
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
        tap_at(next((centre(r) for t, r in (s or {}).get('panel', []) if t == 'Close'), (422, 300)))
        s = until(lambda s: s['mode'] == '' and not s['paused'])
        record_check('touch: Help closes by touch', s)
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
        s = until(lambda s: s['ui'] == [1180, 820])
        page.frames(2)
        page.screenshot(out / 'touch_10_tablet.png')
        record_check('touch: tablet size, same run', s and scene(s)['chapter'] == chapter, ui=s and s['ui'])
        errors = [t for k, t in traffic.since((0, 0))[1] if k in ('error', 'exception') and not t.startswith('   at:')]
        record_check('touch: no engine or script errors', not errors and not traffic.crashed, errors=errors[:5])
        metrics['touch'] = {'seconds': round(time.monotonic() - t_start, 1), 'scale_3d': s and s['scale_3d'], 'godot_fps': s and s['fps'],
                            'renderer': 'SwiftShader software WebGL, emulated phone 844x390 DPR 3: behaviour only, not a phone frame rate'}
    except Exception as error:
        log.flush()
        record_check('touch: phone session', False, error=repr(error),
                     chrome_log=(out / 'chrome-touch.log').read_text(errors='replace').splitlines()[-8:])
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()


def check(site, out, binary, sandbox=True, record=False, play_seconds=900, live=None, recording=True, touch=True):
    """site: the local site directory, or None with live=<deployed URL ending in />, which reads release.json from there."""
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

    side, carried = None, (play_release or {}).get('reused_from')
    if play_release and recording and carried:
        # The play files are byte-identical to a verified release with the same inputs (web_play.reusable): its browser-vs-native
        # result holds for them. The walk below still boots and plays them.
        record_check(f"play: browser-vs-native equivalence carried from release {carried['release']} (same play files)",
                     carried['equivalence'].get('result') == 'PASS', release=carried['release'], git_revision=carried['git_revision'],
                     note=carried['equivalence'].get('note'))
    elif play_release and recording:
        side = threading.Thread(target=run_equivalence, args=(url, play_release, binary, sandbox, out, play_seconds, record_check, metrics))
        side.start()
    touch_side = None
    if play_release and touch:
        touch_side = threading.Thread(target=run_touch, args=(url, play_release, binary, sandbox, out, record_check, metrics))
        touch_side.start()
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
        page.click(*page.centre_of('#panel-toggle'))
        first = page.js("document.querySelector('#assemblies li span').textContent")
        page.click(*page.centre_of('#assemblies li input'))
        page.frames()
        hidden = page.js('[...window.wayfarer.groups.values()].filter(g => !g.visible).length')
        page.screenshot(out / 'desktop_assembly_hidden.png')
        page.click(*page.centre_of('#show-all'))
        page.frames()
        shown = page.js('[...window.wayfarer.groups.values()].every(g => g.visible)')
        record_check('viewer: assembly hide and Show all', hidden == 1 and shown, hidden_assembly=first)
        fps = page.js(RAF_FPS.replace('{ms}', '4000'), timeout=120)
        stats = page.js('(() => { const s = window.wayfarer.stats; return {calls: s.calls, triangles: s.triangles, ready_ms: s.ready_ms}; })()')
        reqs, lines = traffic.since(mark)
        engine = [u for u, *_ in reqs if '/play/' in u]
        record_check('viewer: no Enter Wayfarer file requested', not engine, play_requests=engine[:3])
        requests_ok('viewer: every request served from the project subpath', reqs)
        errors = [text for kind, text in lines if kind in ('error', 'assert', 'exception')]
        record_check('viewer: no script errors', not errors, errors=errors[:5])
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
            record_check('play: engine and Demonstrator 01 start', running and booted, seconds=play_s, engine=booted,
                         state=page.js('window.wayfarerPlay'))
            if running:
                time.sleep(5)
                page.screenshot(out / 'play_first_launch.png')
                for key, code in (('Enter', 13), ('Enter', 13)):        # ACI first launch: the suggested Confirm; then the next chapter
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
        if side:
            side.join()
        if touch_side:
            touch_side.join()
        if server:
            server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)
        log.close()
    version = subprocess.run([binary, '--version'], capture_output=True, text=True).stdout.strip()
    report = {'result': 'PASS' if results and all(r['ok'] for r in results) else 'FAIL', 'browser': version,
              'renderer': 'SwiftShader (software WebGL), headless', 'url': live or BASE, 'git_revision': release['git_revision'],
              'release': release['release'], 'metrics': metrics, 'checks': results}
    (out / 'check.json').write_text(json.dumps(report, indent=2) + '\n')
    if record and not live:
        group = lambda prefix: [r for r in results if r['check'].split(':')[0] in prefix]
        summary = lambda rs: rs and {'result': 'PASS' if all(r['ok'] for r in rs) else 'FAIL', 'passed': sum(r['ok'] for r in rs),
                                     'total': len(rs), 'failed': [r['check'] for r in rs if not r['ok']], 'browser': version}
        release['tests'] = {'viewer': summary(group(('viewer', 'phone'))), 'isolation': summary(group(('start', 'play launcher', 'switching'))),
                            'play': summary(group(('play',))), 'touch': summary(group(('touch',))), 'all': summary(results), 'metrics': metrics}
        equivalence = [r for r in results if r['check'].startswith(('play: Demonstrator 01 check suite', 'play: whole-journey'))]
        if carried and recording:
            release['tests']['equivalence'] = {**carried['equivalence'], 'carried_from': carried['release']}
        elif equivalence:
            eq, suite = metrics.get('equivalence') or {}, metrics.get('check_suite') or {}
            release['tests']['equivalence'] = {
                'result': 'PASS' if all(r['ok'] for r in equivalence) else 'FAIL',
                'note': f"browser vs native on the same package: check suite {(suite.get('web') or {}).get('checks', '-')} checks, "
                        f"{len(suite.get('differ', []))} differing; whole-journey autoplay at a fixed 30 fps {(eq.get('web') or {}).get('frames', '-')} "
                        f"frames vs {(eq.get('native') or {}).get('frames', '-')} natively, same chapters and production-layer flips"}
        (site / 'release.json').write_text(json.dumps(release, indent=1) + '\n')
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
    args = parser.parse_args()
    report = check(args.site and args.site.resolve(), args.out.resolve(), args.chrome, sandbox=not args.no_sandbox, record=args.record,
                   play_seconds=args.play_seconds, live=args.live, recording=not args.no_recording, touch=not args.no_touch)
    print(report['result'], f"{sum(r['ok'] for r in report['checks'])}/{len(report['checks'])} checks")
    if os.environ.get('GITHUB_ACTIONS'):
        loads = {r['check']: r.get('seconds') for r in report['checks'] if 'seconds' in r}
        print(f"::notice title=web check::{report['result']} {sum(r['ok'] for r in report['checks'])}/{len(report['checks'])}; {report['browser']}; load s {loads}")
    sys.exit(report['result'] != 'PASS')
