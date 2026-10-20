"""External character dependencies (assets/external/manifest.toml): status, fetch, verify, install.

`python3 tools/workflow.py deps [status|fetch|install] [--optional]`. Archives go to the cache (outside the repository); MPFB is
unpacked into an isolated Blender user-resource tree there, so the Wayfarer Blender scripts run it with BLENDER_USER_RESOURCES set
and never touch the user's own Blender configuration. A checksum mismatch is an error; nothing is installed from an unverified file.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'assets/external/manifest.toml'


def manifest():
    return tomllib.loads(MANIFEST.read_text())


def cache_root(m=None):
    return Path(os.environ.get('WAYFARER_EXTERNAL') or (m or manifest())['cache']['root']).expanduser()


def blender_user(m=None):
    """The isolated BLENDER_USER_RESOURCES tree (Blender's config, extensions and MPFB's user data live under it)."""
    return cache_root(m) / 'blender/user'


def mpfb_dirs(m=None):
    u = blender_user(m)
    return u / 'extensions/user_default/mpfb', u / 'extensions/.user/user_default/mpfb/data'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def archive(d, m=None):
    return cache_root(m) / 'downloads' / d['file'] if d.get('file') else None


def state(d, m=None):
    """'verified', 'missing', 'unpinned' (manual entry without an archive yet) or 'MISMATCH'."""
    if not d.get('sha256'):
        return 'unpinned'
    p = archive(d, m)
    if not p.exists():
        return 'missing'
    return 'verified' if sha256(p) == d['sha256'] else 'MISMATCH'


def installed(d, m=None):
    ext, data = mpfb_dirs(m)
    stamp = {'blender_extension': ext, 'mpfb_user_data': data}.get(d.get('install'))
    if stamp is None:
        return None
    s = stamp / f".wayfarer_{d['name']}.json"
    return s.exists() and json.loads(s.read_text()).get('sha256') == d['sha256']


def status(include_optional=True):
    m = manifest(); rows = []
    for d in m['dependency']:
        if d['required'] or include_optional:
            rows.append(dict(name=d['name'], required=d['required'], version=d['version'], acquisition=d['acquisition'], archive=state(d, m),
                             installed=installed(d, m), license=d['license'].split(' (')[0]))
    ok = all(r['archive'] == 'verified' and r['installed'] is not False for r in rows if r['required'])
    return dict(manifest=str(MANIFEST.relative_to(ROOT)), cache=str(cache_root(m)), ready=ok, dependencies=rows)


def fetch(include_optional=False):
    m = manifest(); out = []
    for d in m['dependency']:
        if not (d['required'] or include_optional):
            continue
        st = state(d, m)
        if st == 'verified':
            out.append((d['name'], 'cached')); continue
        if d['acquisition'] != 'auto':
            out.append((d['name'], f"manual: download from {d.get('download_page') or d['source_page']} into {cache_root(m) / 'downloads'}"
                        + (f" as {d['file']}" if d.get('file') else '; then pin file, size and sha256 in the manifest')))
            if d['required']:
                raise SystemExit(f"required dependency {d['name']} needs manual acquisition")
            continue
        p = archive(d, m); p.parent.mkdir(parents=True, exist_ok=True); part = p.with_suffix(p.suffix + '.part')
        for url in [d['url']] + ([d['mirror']] if d.get('mirror') else []):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'wayfarer-deps/1 (+https://github.com/makehumancommunity/mpfb2)'})
                with urllib.request.urlopen(req, timeout=60) as r, open(part, 'wb') as f:
                    shutil.copyfileobj(r, f, 1 << 20)
                break
            except OSError as e:
                print(f"{d['name']}: {url} failed ({e})", file=sys.stderr)
        else:
            if d['required']:
                raise SystemExit(f"could not download {d['name']}")
            out.append((d['name'], 'download failed (optional)')); continue
        got = sha256(part)
        if got != d['sha256']:
            part.unlink()
            raise SystemExit(f"{d['name']}: SHA-256 {got} does not match the manifest's {d['sha256']}")
        part.rename(p); out.append((d['name'], 'downloaded and verified'))
    return out


def install():
    """Unpack the verified required archives into the isolated Blender tree (idempotent: a stamp records the installed checksum)."""
    m = manifest(); ext, data = mpfb_dirs(m); out = []
    for d in m['dependency']:
        target = {'blender_extension': ext, 'mpfb_user_data': data}.get(d.get('install'))
        if target is None:
            continue
        if state(d, m) != 'verified':
            raise SystemExit(f"{d['name']} is not cached and verified; run `workflow.py deps fetch` first")
        if installed(d, m):
            out.append((d['name'], f'installed ({target})')); continue
        if d['install'] == 'blender_extension' and target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive(d, m)) as z:
            z.extractall(target)
        (target / f".wayfarer_{d['name']}.json").write_text(json.dumps(dict(name=d['name'], version=d['version'], sha256=d['sha256'])))
        out.append((d['name'], f'installed into {target}'))
    return out


def blender_env():
    """Environment for Blender runs that use MPFB: the isolated user-resource tree."""
    return dict(os.environ, BLENDER_USER_RESOURCES=str(blender_user()))


def main(argv):
    action = argv[0] if argv else 'status'; opt = '--optional' in argv
    if action == 'status':
        print(json.dumps(status(), indent=1))
    elif action == 'fetch':
        for name, what in fetch(opt):
            print(f'{name}: {what}')
    elif action == 'install':
        for name, what in fetch(opt) + install():
            print(f'{name}: {what}')
    else:
        raise SystemExit(f'unknown deps action {action}')


if __name__ == '__main__':
    main(sys.argv[1:])
