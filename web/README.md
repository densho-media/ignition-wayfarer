# Wayfarer website (WEB-001, WEB-002)

The public site of G.U. WAYFARER 001 (IGNITION). GitHub Actions builds it from a clean checkout and publishes it on GitHub Pages
at <https://densho-media.github.io/ignition-wayfarer/>. Its four entry points each load their own files only when chosen:

| Path | Page | Loads |
| --- | --- | --- |
| `/` | start page: Explore Ship or Enter Wayfarer | `index.html`, `site.css`, `release.json` (about 7 kB plus the manifest); no engine, model or library |
| `/viewer/` | **Explore Ship**: three.js 0.170.0 engineering viewer | the viewer, three.js with the Draco decoder, `model/wayfarer-<hash>.glb` (5.9 MB) and its labels |
| `/play/` | **Enter Wayfarer**: launcher; Start opens `demo01-<hash>.html` | Godot 4.7.2 `engine-<hash>.{js,wasm}` and the Demonstrator 01 pack `demo01-<hash>.pck` |
| `/review/` | technical review: release, model, checks, limitations, this browser | `release.json` |

Both experiences are REP_PROXY, SIMULATION_ONLY representations. The pages compute no spacecraft facts: geometry, labels and
behaviour come from the exporter, the manifests, the rig and the unchanged Godot scenes. Why it is built this way, the
measurements and the open items are in [docs/wayfarer-web-experience-plan.md](../docs/wayfarer-web-experience-plan.md).

## Sources here

- `index.html`, `site.css`: the start page and the stylesheet the launcher and review pages share.
- `viewer/`: the viewer (its own stylesheet).
- `play/index.html`: the click-to-load launcher.
- `play/shell.html`: the Godot HTML shell. It is an export input, not a site file.
- `review/`: the review page.

`tools/web_export.py` copies these pages and adds the generated files (`vendor/`, `model/`, the Godot export, `build.json`,
`play.json`, `release.json`). Every path is relative, so the site serves from any subpath on any static host.

## Build

The pipeline builds the assets; `web` exports the viewer GLB and the Godot Web build and assembles the site; `web_check`
walks it in headless Chrome.

```bash
python3 tools/workflow.py pipeline --quick --previews none
python3 tools/workflow.py web --pipeline-run runs/<that run> --out runs/web-site [--native] [--no-play] \
    [--reuse-play <previous site> [--reuse-native <its native zip>]]
python3 tools/web_check.py runs/web-site --out runs/web-check --chrome <chrome or chromium> [--record]
```

- **Reuse.** With `--reuse-play`, an Enter Wayfarer whose inputs are unchanged is copied from that previous site instead of
  rebuilt. The inputs are the staged Godot project (the commit fields in its manifests left out), the shell, `web_play.py`
  and the pinned Godot. The previous site must carry the same `input_key`, passing play and equivalence tests, and play files
  (and native zip) matching its `release.json`. The import, native check, recording and exports are skipped, and the browser
  check carries that release's browser-vs-native result. Godot's `.pck` differs between two exports of the same inputs, so
  the key is computed from the inputs, not the pack. CI passes the latest `web-*` release.
- **Toolchain.** `web` needs Blender (`WAYFARER_BLENDER`).
  - Enter Wayfarer also needs the official Godot 4.7.2 standard build. `tools/web_play.py` downloads it once into
    `~/.cache/wayfarer/godot-4.7.2` (`WAYFARER_GODOT_CACHE`), checks it against the release SHA-512 sums, and keeps only the Web
    and Linux templates from the 1.3 GB archive.
  - `--no-play` builds the site without Godot.
- **The play build** runs in `runs/<stamp>-web/play/`, a copy of `godot/`.
  - It exports DOCKED from the saved assets and adds the COAST manifest, the route and the EVA data.
  - It sets the main scene to `demo01.tscn` in that copy only, imports, and runs Demonstrator 01's own check (68 checks) plus a
    fixed-30-fps recording natively.
  - It then exports Web (single-threaded, no COOP/COEP needed) and, with `--native`, a Linux build of the same package.
  - The project's `godot/` and `godot/generated/` are never written.
- **Before PASS,** `web` checks that every local reference in the site resolves, that no file exceeds 95 MB, that the site
  stays under 900 MB, and that the start page names no engine or model.

**Local preview.** Serve a directory that contains the site as `ignition-wayfarer/`, then open
`http://localhost:8000/ignition-wayfarer/`:

```bash
mkdir -p runs/preview && ln -sfn ../web-site runs/preview/ignition-wayfarer && python3 -m http.server -d runs/preview
```

`file://` does not work, because ES modules and the engine need HTTP.

## What the browser check covers (`tools/web_check.py`)

- **Start page:** it requests only `index.html`, `site.css` and `release.json`, has no canvas or engine, and stays under its
  transfer budget.
- **Explore Ship,** opened from its link:
  - framing, orbit, zoom, pan, Reset and the presets
  - picking and hiding assemblies
  - the `#cam=` bookmark after a reload
  - no request to `play/`, and no script errors
- **Enter Wayfarer:**
  - The launcher requests no engine before Start.
  - Start boots Godot and Demonstrator 01 with no request to `viewer/` and no engine or script error.
  - The ACI first-launch prompt takes Enter.
- **Switching:**
  - Exit and Back return to the start page with no canvas left.
  - Explore Ship starts again.
  - Browser memory (the summed RSS of all Chrome processes) returns to the start-page level.
- **Recording:** Demonstrator 01 autoplays GRAVITY to INSPECT at a fixed 30 fps and must match the native run of the same
  package: chapters, frame count and production-layer flips.
- **Phone, review page:**
  - At 390 × 844 with touch, the start page has no overflow and the viewer frames the ship, orbits with one finger and zooms
    with a pinch.
  - The review page renders the release.
- **Touch (MOB-001):** Enter Wayfarer on an emulated phone (844 × 390 CSS px, DPR 3, touch, landscape), in a third browser
  alongside the walk. The game publishes its touch state (`?arg=--&arg=--touch-probe`, `window.wayfarerTouch`).
  - The touch welcome is completed by a tap, and Skip and Pause work by touch.
  - The rail stick works together with a look finger, and lifting the fingers stops at once.
  - Weightless: no stick and no force, a look drag, then Push off.
  - Map and the systems card open and close.
  - The transfer line takes the 1-D stick.
  - Walking on ring A, with Drop by a second finger.
  - Help is a modal.
  - Upright and tablet sizes keep the same run.
  This is emulation: it checks behaviour, not a phone's frame rate (docs/wayfarer-mobile-controls-plan.md).

`--record` writes the summary and metrics into the site's `release.json`. `--live <url>` repeats the checks against a deployed
site, `--no-recording` skips the recording and `--no-touch` the touch journey.

## GitHub Actions

`.github/workflows/web-explorer.yml`:
- **Triggers.** Pushes to `main`, `claude/**` and `local/**`, plus a manual run. There is no `pull_request` trigger. A push
  that changes only `docs/`, `TODO.md`, `README.md`, `AGENTS.md` or `CLAUDE.md` runs nothing (none of it is in the site or
  read by a test); the live site stays at the last built commit.
- **Every branch.** Unit tests, the Blender build with geometry diff 0, `web --native`, and `web_check --record`. Artifacts:
  - the site (`wayfarer-web-site`, the preview build)
  - the check screenshots and logs
  - the native Linux zip
- **`main` only:**
  - `deploy` publishes to Pages, only after every check passes.
  - `verify` waits until the live `release.json` names the commit, records each file type's status, type, encoding and cache
    headers, and runs the browser check against the live URL.
  - `release` keeps the verified site, its `release.json` and the native Linux zip as GitHub Release `web-<release>`.
- **Permissions.**
  - Build jobs are read-only.
  - `deploy` has `pages: write` and `id-token: write`; `release` has `contents: write`.
  - Every action is pinned to a commit SHA, and toolchains are checksum-pinned.

**Rollback.** In *Actions → Web rollback → Run workflow*, enter a `web-<release>` tag (`.github/workflows/web-rollback.yml`).
The workflow downloads that release's site, checks every file against its `release.json`, and deploys it. The next push to
`main` deploys the current build again; revert on `main` to make the rollback permanent. *Settings → Pages → Unpublish*
takes the site down. The WEB-001 viewer that preceded this site is kept as release `web-20261022-a5ceda2`
(the exact files Pages served from `a5ceda2`, compared with the live site before it was replaced); redeploying that tag
restores it.

**Pages setting.** *Settings → Pages → Source: GitHub Actions* (set 2026-10-22). No secrets, variables or approval rules are
configured.

## Viewer use

- **Mouse:** left-drag (or one finger) orbits, the wheel (or a pinch) zooms, right-drag (or two fingers) pans.
- **Picking:** click a part to see its component, kind and canon or geometry status. Esc clears the selection.
- **Presets:** 1 side, 2 top, 3 three-quarter, 4 bow, 5 aft; Home or Reset returns to the whole ship. The Assemblies panel
  hides and shows each assembly.
- **Bookmarks:** the address bar keeps the view as `#view=<preset>` or, after a drag, `#cam=<x,y,z,tx,ty,tz>` (metres, runtime
  axes: bow +X, dorsal +Y). Reopen the link to get the same camera.
- **Diagnostics:** `?diag` shows frame time, draw calls, GPU objects and transferred bytes.
