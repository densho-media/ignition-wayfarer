# Wayfarer website (WEB-001, WEB-002)

The public site of G.U. WAYFARER 001 (IGNITION). GitHub Actions builds it from a clean checkout and publishes it on GitHub Pages
at <https://densho-media.github.io/ignition-wayfarer/>. Its four entry points each load their own files only when chosen:

| Path | Page | Loads |
| --- | --- | --- |
| `/` | start page: Explore Ship or Enter Wayfarer | `index.html`, `site.css`, `release.json` (about 7 kB plus the manifest); no engine, model or library |
| `/viewer/` | **Explore Ship**: three.js 0.170.0 engineering viewer | the viewer, three.js with the Draco decoder, `model/wayfarer-<hash>.glb` (5.9 MB) and its labels |
| `/play/` | **Enter Wayfarer**: launcher; Start opens the walk (`demo01-<hash>.html?arg=--&arg=--excursion`, EXC-001), the second button the guided Demonstrator 01 tour | Godot 4.7.2 `engine-<hash>.{js,wasm}` and the one ship pack `demo01-<hash>.pck` (both experiences) |
| `/review/` | technical review: release, model, checks, limitations, this browser | `release.json` |

**Hologram styles (WEB-003).** Both experiences can show the ship as the two hologram looks of the Blender shots and the Godot
M5 scene, as presentation only: **Subsystems** (unshaded, additive rim and scan bands in each functional subsystem's overlay colour,
the M5 subsystem hologram) and **Engine holo** (one colour, rim glow and, in the viewer, wire edges: the SH_ENGINE_HOLOGRAM look).
The colours and node classification come from `representation.py holo-style` over the export manifest (shots/m5_subsystems.toml,
the SH_ENGINE_HOLOGRAM colour, and the manifest lineage for groups); the viewer loads them (`model/holo-<hash>.json`) only when
something other than the standard look is first asked for. In Enter Wayfarer, F3 or the Holo touch button cycles standard,
subsystem and engine (`generated/wf_holo.json`). Overlay colours explain function and are never materials.

**Hybrid appearance (WEB-004, Explore Ship).** Three separate parts of the viewer state, resolved per node by `viewer/appearance.js`
(pure logic) and drawn by `viewer/viewer.js`:

- **Style**, the global look: Standard, Subsystems, Engine holo, **Hybrid** (keys S, H, E, X). Hybrid looks like Standard until a
  part is clicked; a click then focuses it.
- **States** the visitor sets on a part, a group (the manifest lineage below the assembly: a drive nozzle, a radiator mechanism), an
  assembly or a subsystem: **Solid** (imported materials), **Hologram**, **Ghost**, **Hidden**. Assemblies have a state menu in the
  Assemblies panel (Auto = no state); the pick box sets states on the selected part, group, assembly or subsystem (Part / Group /
  Assembly / Subsystem chips) and Restore removes one.
- **Focus**, the subject: a part, group, assembly or subsystem (pick box Focus, the legend, or a click in Hybrid). The subject takes the
  focus look (Solid, Subsystem colour or Cyan; the focus bar and the Appearance panel); everything else takes the context look
  (Ghost by default, or Hologram). Frame (F) frames the focus from the current direction; the camera never moves by itself.
  Whole ship (Esc) clears the focus.

Precedence, first match wins: (1) Hidden by any state that covers the node; (2) the node's own state, then its group's, assembly's,
subsystem's; (3) the focus (subject: focus look; others: context look); (4) the style default (Standard and Hybrid solid; Subsystems a
hologram per subsystem colour with the unclassified casing as a ghost; Engine holo a cyan hologram). A state stays when the selection,
the focus or the camera changes. **Show all** lifts every Hidden state and nothing else. **Reset appearance** returns to the initial
state: Standard, no focus, no states, ghost 6 % with outlines, no selection; every mesh gets its imported material (kept in
`userData.material`) and its exported visibility back, the added edge lines are removed and their geometry disposed. The camera
stays where it is.

Rendering. Ghosts use one low-opacity, normal-blended material per tint (grey; cyan in Engine holo) with an optional rim term
(**Ghost outlines**); a stencil bit lets each pixel take only one ghost layer, nearest first, so the thousand stacked radiator cells
show as one faint layer instead of adding up. **Ghost strength** (0-20 %, default 6 %) is one shared uniform. Holograms keep the
additive M5 look but a stencil count lets a pixel add at most two hologram layers. Solid subjects are opaque, so a ghost in front
of one only tints it by the ghost strength. The shaders carry the logarithmic depth chunks of the renderer, so they test depth
against the solid meshes. Engine wire edges are made only for meshes drawn in the engine hologram, once per geometry; the
selection is marked by its feature edges, not by replacing its material (except the plain WEB-001 highlight in Standard).

Cost, measured 2026-10-24 on SwiftShader software WebGL at 1280 × 800, three-quarter view, median of 30 frames (software timing
only; real-GPU numbers are still to be taken): Standard 2,397 → 2,337 ms (WEB-003 → WEB-004), Subsystems 937 → 930 ms, Engine holo
1,482 → 1,553 ms, Hybrid with the propulsion focused 974 ms, the radiators as a subsystem hologram 960 ms. Draw calls are unchanged
(3,987 Standard; 3,947 holograms and ghosts; 7,894 Engine holo with its edges): the stencil limits add no pass. Shader programs
grow by one (the ghost). Edge geometry doubles the geometry count only while Engine holo edges exist; Reset appearance returns it
to 2,721.

Picking. Hidden meshes are never hit. With a focus, the nearest Solid or Hologram hit wins over ghosts in front of it; a ghost is
picked only where the ray meets nothing else. A click on empty space clears the selection, not the focus.

Bookmarks keep the camera part first (`#view=` or `#cam=`, as before) and add only non-default state:
`style=hybrid&focus=a:Assembly_PROPULSION001&look=cyan&ctx=hologram&ghost=12&outl=0&ov=a:Assembly_HULL001.x,n:WF_….g`
(`n`/`g`/`a`/`s` = part, group, assembly, subsystem; `s`/`h`/`g`/`x` = solid, hologram, ghost, hidden). A target that a later
build no longer has is dropped. WEB-003 links (`&style=subsystem`) still open.

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
  - WEB-004: each of the four styles draws every mesh in its look; subsystem colours equal the exported classification; an
    assembly takes Solid, Hologram, Ghost and Hidden and Show all lifts Hidden; a Hybrid click focuses the picked part solid with
    the rest ghosted; changing the selection keeps other states; hidden parts never take a pick and ghosts never take one from a
    visible subject behind them; Reset appearance restores materials, visibility and transforms (no lines left); the appearance
    bookmark restores style, focus, look, ghost strength and states and drops a missing part
  - the `#cam=` bookmark after a reload
  - no request to `play/`, and no script errors
- **Enter Wayfarer:**
  - The launcher requests no engine before Start.
  - Start boots Godot and the walk (it prints `WF_EXCURSION ready`) with no request to `viewer/` and no engine or script error.
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
- **Touch walk (EXC-001):** the walk on the same emulated phone, after the touch journey in the same browser: the touch welcome by
  a tap; the 1-D stick down the boarding line to the shut outer hatch (the push-off into the coast across it is refused); Use opens
  it; a look drag turns the view; Map and View answer; no engine or script error.

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
