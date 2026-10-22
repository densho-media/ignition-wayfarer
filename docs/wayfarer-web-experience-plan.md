# Wayfarer web experience and deployment (WEB-002)

Working plan and decision record for the public Wayfarer website: a start page, the Explore Ship viewer, the Enter Wayfarer
Godot experience and a technical review page, each loaded only when chosen, built and deployed by GitHub Actions.
How to build, check and roll back lives in [web/README.md](../web/README.md); this document records why it is built this way,
what was measured and what is left. Dated 2026-10-22.

## 1. Starting point (audit, 2026-10-22)

- **Repository.** `densho-media/ignition-wayfarer` is public, with `main` plus task branches (`claude/*`, `local/*`), no other
  worktrees and no pull requests (AGENTS.md step 5). The modeling session works on its own branch or workstation. This work
  stayed on `claude/affectionate-goodall-orfxcx` in a fresh cloud clone, so it shares no working tree with it.
- **Existing web.** WEB-001 (commits `954abc3`–`0fc1651`) already deployed a three.js 0.170.0 viewer at the site root.
  - It loads a Draco COAST GLB (5.86 MB) exported from the saved assets by the same exporter as the Godot package.
  - `.github/workflows/web-explorer.yml` covers unit tests, the Blender 5.2.2 build, a geometry diff that must be 0, the export,
    and a 20-check headless-Chrome test. Only `main` deploys to Pages, through `actions/deploy-pages`.
- **Godot.**
  - Godot 4.7.2 project in `godot/`: GDScript only, no C#, `.csproj` or GDExtension. Renderer `gl_compatibility` (WebGL 2
    capable). Physics is the built-in "Jolt Physics" module with zero project gravity and damping.
  - There are no export presets. The workstation runs the Mono editor, but the project needs no .NET.
  - The start scene is the developer review menu (`review.tscn`).
- **Demonstrator.** Integrated Demonstrator 01 (`demo01.tscn` over `boarding.gd`) runs nine chapters, EXTERIOR to INSPECT. It
  reads the DOCKED package (`wayfarer_docked.glb`, `manifest_docked.json`, `wf_sim_rig.json`), plus `manifest.json` (COAST,
  forward explorer), `wf_route_v1.json` and `wf_eva.json` (navigator remote view). The MPFB characters are optional: without
  them the exported proxies stay.
- **Runtime package.** `runtime-export` needs the MPFB characters and EVA suits, which take a 325 MB download and an
  isolated Blender user tree. It publishes `godot/generated/`, which the modeling session uses. The web build must not touch it.
- **Owner workbooks** (read 2026-10-22, IGNITION — Wayfarer Ship, revision `APfK_pD-…`):
  - 60 UX-018: the web is a DEFERRED, optional packaging; "Local offline Godot experience remains authoritative runtime for
    this phase."
  - 59 POL-014: no website dependency for local production.
  - 59 POL-002 and POL-013: no second solver, and no hand-keyed truth in any engine.
  - 59 POL-010 and POL-011: licence provenance before publication.
  - 60 UX-002 and UX-017: visitors get one journey; review scenes stay developer tools.
  - 60 UX-011: every display classifies CANON, DERIVED, WORKING, PROTOTYPE, DIAGNOSTIC, OPEN or HOLD.
  - 48 WF-025: Demonstrator 01 acceptance.
  - The owner's handoff of 2026-10-22 authorises this deployment work. The rows above shape it: the website is a derived,
    optional package, the native Godot build stays the reference, and the local production loop gains no dependency.
  - The status sheet and the request Doc were not read; this change makes no Drive write.

## 2. Research and decisions

| # | Decision | Chosen | Considered | Why |
| --- | --- | --- | --- | --- |
| D1 | Host | **GitHub Pages via Actions** (unchanged) | Cloudflare Pages; object storage (R2) for large files | Pages limits fit the measured site (70 MB of the 1 GB limit; largest file 39.5 MB of 100 MB; deploys from an artifact, no files in Git). Cloudflare Pages caps files at 25 MiB, so the stock Godot `.wasm` (39.5 MB) would need a custom engine build or a second origin. No headers are needed (D3). The site has relative paths only, so any static host can serve it unchanged. |
| D2 | Site shape | **One site, four static entry points** (`/`, `/viewer/`, `/play/`, `/review/`) with no framework or bundler | A single-page app with lazy chunks; separate repositories or sites | Real page navigation makes loading isolation and resource release structural: leaving a page unloads its engine. There is no router or build step to maintain. |
| D3 | Godot variant | **Web, single-threaded** (`web_nothreads_release`, `variant/thread_support=false`) | The threaded build with COOP/COEP through a service worker (coi-serviceworker or Godot's PWA option) | GitHub Pages cannot set headers. The single-threaded build needs no cross-origin isolation and is Godot's default since 4.3. Jolt runs on the main thread there (it is compiled into the web templates: `modules/jolt_physics/config.py`, `register_types.cpp`). |
| D4 | What to play | **Integrated Demonstrator 01** as the only scene (main scene set in the build workspace copy) | The review menu with all eight sessions | 60 UX-002 and UX-017 (one visitor journey). Demonstrator 01 is the existing L3 vertical slice from boarding through the spine and ring transfer to spin gravity (48 WF-025). EVA, flight and hologram need packages the browser build does not carry. |
| D5 | Package | **DOCKED export from the saved assets plus tracked JSON**, no MPFB characters | The full `runtime-export` package | It needs no 325 MB character toolchain in CI and leaves `godot/generated/` alone. The proxies standing in for the induction pair are a presentation-only difference, and the native check on this exact package passes 68/68. |
| D6 | Toolchain | **Official Godot 4.7.2 standard editor and templates**, SHA-512 checked against the release `SHA512-SUMS`; only `web_nothreads_release.zip` and `linux_release.x86_64` are extracted and cached | The workstation's Mono snap; distro packages | Pinned and reproducible. The 1.28 GB archive is downloaded once per cache key and deleted after extraction. |
| D7 | Cache safety | **Content-named engine, pack and model files**; small JSON indexes fetched with `cache: 'no-store'` | Versioned subfolders per release; query-string busting | Pages serves every file with a 10-minute `max-age`. A visitor caught mid-deploy could otherwise combine a new `.js` with an old `.wasm`. Content names keep unchanged files cacheable across releases. |
| D8 | Equivalence | **The native checks repeated in the browser**: the 68-check `--check-demo` suite (compared check by check) and the whole-journey autoplay recording (chapters, frame count, display time and production-layer flips), both at a fixed frame rate with `--disable-render-loop` | Drawn runs; a short partial recording | Measured with drawing on and software WebGL, at 640 × 400: the suite did not finish in 20 minutes, and GRAVITY→INSPECT alone (617 frames) took 857 s. With drawing off, that recording took 16 s with an identical result, and the suite took about 3 minutes. Logic, physics and input step the same per frame either way; the interactive run checks rendering separately. |
| D9 | Rollback | **GitHub Release per verified main deploy** (exact site tarball, `release.json`, native Linux zip) and the `web-rollback.yml` redeploy; Pages artifacts expire | Re-running an old workflow run; reverting on `main` | Rollback needs no rebuild, Blender or Godot. Each file is checked against the kept manifest before deploying. A revert on `main` remains the way to make a rollback permanent. |
| D10 | Native release | **Linux x86_64 export of the same package** attached to the release; the full development runtime stays `runtime-export` | A separate native pipeline | One package, two targets. The native build stays the gameplay reference. |
| D11 | Viewer | **Preserved** (three.js 0.170.0, Draco GLB, same export). Added: back link, `#view=`/`#cam=` bookmarks, `?diag` frame-time overlay, context release on `pagehide` | PlayCanvas (parked as FUT-006); Babylon.js | It already works on desktop and phone. There is no second model pipeline. |

Sources:
- Godot web export: [exporting_for_web](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html), the
  [4.3 single-threaded export](https://godotengine.org/article/progress-report-web-export-in-4-3/#single-threaded-web-export),
  [export_plugin.cpp @4.7.2](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/web/export/export_plugin.cpp),
  [jolt config.py @4.7.2](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/jolt_physics/config.py) and
  [feature tags](https://docs.godotengine.org/en/stable/tutorials/export/feature_tags.html).
- GitHub Pages: [limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
  [custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
  and [no custom headers](https://github.com/orgs/community/discussions/13309).
- Cloudflare: [Pages limits](https://developers.cloudflare.com/pages/platform/limits/) and
  [R2 pricing](https://developers.cloudflare.com/r2/pricing/).
- Headless WebGL: [SwiftShader in Chromium](https://chromium.googlesource.com/chromium/src/+/da170c2267b2201954efe1c8fa5d2d89ab09f7bf/docs/gpu/swiftshader.md).
- Several sites could not be reached from the sandbox; their content was read from the GitHub sources of the same pages.
  GitHub Pages compression and cache headers are not documented: the live verify job records them on each deploy.

## 3. Structure and loading boundaries

```
web/index.html, site.css        start page          loads index.html, site.css, release.json (no script library, canvas or engine)
web/viewer/                     Explore Ship        three.js + Draco decoder + content-named GLB and labels (viewer/build.json)
web/play/index.html             launcher            loads play.json only; Start opens the content-named Godot page
web/play/shell.html             Godot HTML shell    (export input, not published) boots demo01-<hash>.pck on engine-<hash>.wasm
web/review/                     review page         renders release.json and probes the browser with a throwaway context
release.json                    release manifest    identity, toolchain, inputs, all files (bytes, SHA-256), experiences, checks
```

Ownership and status labels:
- Geometry and every value come from the existing exporter and the rig (`export/godot.py`, `wf_sim_rig.json`, the manifests).
  The pages compute no spacecraft fact.
- Labels come from the manifests and the Godot scenes as they stand. The site adds only the legend (review page) and the
  SIMULATION_ONLY notes.

Releasing resources:
- Every choice is a page navigation; Exit, Back and the browser's own back button all unload the previous page.
- The viewer also disposes its renderer and forces context loss on `pagehide`. A page restored from the back-forward cache
  reloads.

## 4. Build, deploy and roll back

```
pipeline --quick --previews none        geometry diff 0 (unchanged)
workflow.py web --pipeline-run R --native
  viewer GLB (Draco, checked against manifest)  ->  play workspace: DOCKED export + manifests + route + EVA data
  -> Godot import -> native Demonstrator 01 check (68) + native recording -> Web export (+ Linux export)
  -> content naming -> release.json -> reference/size check of the whole site
web_check.py _site --record             start / viewer / play / switching / recording / phone / review in headless Chrome
deploy (main only) -> verify (live release.json = commit, headers, browser check on the live URL) -> release web-<id>
```

## 5. Measurements

Filled from the runs below; CI reports the same keys in each run summary and in `release.json` → `tests.metrics`.

Measured 2026-10-22 in Claude Code cloud (4 vCPU, no GPU):
- Setup: Blender 5.2.2, Godot 4.7.2, and Chromium 141.0.7390.37 headless with SwiftShader software WebGL.
- Site build: `runs/20261022T113752Z-web`. Browser check: `runs/web-check`, 37/37 PASS.
- The local test server does not compress. "gzip -9" is the size gzip gives locally; the live verify job records what Pages
  actually sends.

**Download per experience** (bytes in the site; the budgets checked by `web_export.verify_site` are in brackets):

| Experience | Files | Raw | gzip -9 | Budget |
| --- | --- | --- | --- | --- |
| Start page | `index.html`, `site.css` (+ `release.json`) | 6.6 kB (+ 12.8 kB manifest) = **19.4 kB transferred, 3 requests** | — | 60 kB raw; 150 kB transferred; no engine, model or library |
| Explore Ship | viewer, three.js 0.69 MB, Draco, GLB 5.85 MB, labels | **7.35 MB, 18 requests** | GLB 2.89 MB, three.js 0.17 MB | 12 MB |
| Enter Wayfarer, launcher | `play/index.html`, `play.json` | 3 requests, no engine | — | no engine before Start |
| Enter Wayfarer, Start | engine `.wasm` 39.5 MB, `.js` 0.28 MB, pack 23.1 MB, shell, worklets | **62.9 MB, 5 requests** | wasm 10.1 MB, pack 18.7 MB, js 0.07 MB (about 29 MB in all) | 90 MB |
| Whole site | 29 files | 70.4 MB | — | 900 MB (Pages: 1 GB) |

**Time and frames** (headless software rendering; a measure of the pipeline, not of visitor hardware):

| Measure | Value |
| --- | --- |
| Start page: DOMContentLoaded / load | 39 ms / 39 ms; usable 0.29 s |
| Viewer ready (model framed), cold cache | 2.6 s from clicking Explore Ship |
| Godot interactive, cold cache | 12.6 s from Start (engine start 8.0 s after the page loaded) |
| Frame rate under SwiftShader | viewer 0.5 fps (3,976 draw calls, 0.74 M triangles at 1280 × 800); game 0.3 fps. Real-GPU rates **not measured** |
| Page-renderer memory, in viewer / in game | 465 MB / 703 MB |
| Page-renderer memory on the start page: first, after viewer, after game, after second viewer | 269, 369, 388, 382 MB (settled; back-forward cache off) |
| With the back-forward cache on (Chrome default) | Chrome keeps the left game page (about 450 MB renderer plus GPU memory) for an instant Back, until it evicts it; three play/viewer cycles grew the browser from 835 to about 2,100–2,300 MB. That is browser caching, not a page leak (with the cache off it stays flat). |
| Browser vs native, check suite | 68/68 PASS in both builds, no check differs; 168 s in the browser with drawing off, 65 s natively |
| Browser vs native, whole-journey autoplay at a fixed 30 fps | both builds: 9 chapters, 5,438 frames, 181.29 s display time, 4 flips, PASS; 96 s in the browser |
| JavaScript or WebAssembly errors, failed requests | none (after the `wf_input.gd` fix; before it, 1,770 `keyboard_get_keycode_from_physical` errors per run) |

**Build and check time** (local, cached toolchains): `workflow.py web --native` took 227 s.
- Viewer export: 59 s.
- Play build: 168 s, of which DOCKED export 46 s, EVA route 10 s, import 9 s, native check suite 65 s, native recording
  about 22 s, Web export 7 s and Linux export 4 s.
- `web_check.py`: 13.9 min, most of it the two equivalence runs and software rendering.
- The first CI run also downloads the 1.28 GB Godot template archive once per cache key.

**Optimization record.**
- *Measured bottleneck:* the Enter Wayfarer download. 63% of it is the stock engine (`.wasm`, identical for every project).
  The pack is the imported DOCKED scene (18.1 MB, already compressed by Godot's import) plus 4 MB of JSON. The 32.5 MB source
  GLB is not packed.
- *Done:* click-to-load isolation (0 engine bytes on the start page and the launcher); content-named files, so an unchanged
  engine stays cacheable across releases; no duplicate GLB in the pack.
- *Not done, with reasons:*
  - Decimating or LOD-reducing the engineering geometry: AGENTS.md forbids changing engineering geometry for a rendering budget.
  - A custom size-optimized engine build: it adds a C++ toolchain to CI for about 10 MB compressed.
  - Splitting the pack into chapter packs: the DOCKED scene is a single resource every chapter shows.
  - Revisit if real-GPU measurements show the download or frame rate as the visitor problem.

## 6. Browser and device coverage

| Browser | How | Result |
| --- | --- | --- |
| Chromium 141.0.7390.37 (Playwright build), Linux, software WebGL | `web_check.py` locally | 37/37 PASS (§5) |
| Google Chrome 155.0.8059.84 (ubuntu-24.04 runner), software WebGL | CI build job (run 39776132097 at `99e25c5`) | 37/37 PASS: viewer ready 5.6 s, Godot interactive 11.5 s, check suite 68/68 equal to native in 158 s, whole-journey recording equal in 94 s; build job 17.5 min (pipeline 54 s, export and Godot 181 s, browser check 774 s) |
| Firefox (Linux) | not available in this environment | **not tested** |
| Safari (macOS, iOS) | not available | **not tested**; Godot documents WebGL 2 issues in Safari, and the 4.7 templates need wasm SIMD (Safari 16.4+) |
| Phones | Chrome emulation 390 × 844 with touch (viewer, start page) | viewer PASS in emulation; the Godot build expects a keyboard and the launcher says so |
| Real GPUs | not available | frame rates on hardware are **not measured** |

## 7. Native and browser behaviour

| Area | Classification | Evidence |
| --- | --- | --- |
| Demonstrator 01's checked behaviour: chapters, rail, closures, vestibule interlock, crew physics (Jolt) in microgravity, transfer and spin gravity, mode controller, navigator | **Equivalent behaviour** | the 68-check suite gives the same result per check in both builds, and the whole-journey autoplay matches in chapters, frames, display time and flips (§5) |
| Rendering (look, lighting, fonts) | **Acceptable presentation-only difference** | the same Compatibility renderer on WebGL 2; checked visually on screenshots, not compared pixel by pixel |
| Navigator markers (▶ ◆ ○ …) | **Acceptable presentation-only difference** | the default font lacks them, and the browser has no system font to fall back on |
| Induction pair and EVA suits | **Acceptable presentation-only difference** | exported proxies instead of the MPFB bodies |
| Key labels | **Acceptable presentation-only difference** | Web cannot map physical keys to the layout; US positions are shown (`wf_input.gd` `from_physical`) |
| Threads | **Documented reduced fidelity**: single-threaded | Jolt runs on the main thread; frame rate on slow machines is lower than native |
| Recording, capture, Movie Maker, `user://` capture files | **Unsupported / not offered** in the browser | native only |

## 8. Implementation tasks (dependency order, all done in this change)

1. The play workspace build: `tools/web_play.py`, with the pinned toolchain, DOCKED package, native check and recording, Web
   and Linux exports, and content naming.
2. The site: `web/` split into the start page, viewer, play launcher and shell, and review page; `tools/web_export.py`
   assembles it and writes `release.json` and the reference and size checks.
3. The checks: `tools/web_check.py` covers loading isolation, viewer, play, switching and memory, recording equivalence,
   phone and review, plus `--live` and `--record`.
4. CI: `web-explorer.yml` adds the Godot cache, play build, native artifact, live verify job and release job;
   `web-rollback.yml` is new.
5. A web-only fix in `wf_input.gd`: the Web display server cannot map physical keys, so the ERROR spam is gone.

## 9. Risks and fallbacks

- **CI time grows** with the Godot steps and the browser play checks; §5 has the measured times.
  - If the job nears its 45-minute limit, `--no-recording` or a separate play job is the fallback.
- **The Godot export is skipped or fails.** `workflow.py web --no-play` builds the site without Enter Wayfarer, and the start
  page then dims that choice. A failed play step fails the whole run, so the live site stays as it was.
- **The modeling session changes Demonstrator 01's inputs.** The play build reads the same saved assets and scenes on every
  run, and the native check plus the recording must pass before anything deploys.
- **Pages cache or CDN lag.** The verify job waits up to 10 minutes for the new `release.json` and fails visibly.
- **Rollback.** Run *Actions → Web rollback* with tag `web-<release>`, or revert on `main`. Pages' own *Unpublish* takes the
  site down. The WEB-001 viewer live before this deploy is kept as `web-20261022-a5ceda2`, checked file by file
  against the live site.

## 10. Definition of done

- [x] The start page loads only its HTML, stylesheet and release record (checked by request inspection).
- [x] Explore Ship works from its link and requests nothing from `play/`.
- [x] Enter Wayfarer boots Demonstrator 01 and requests nothing from `viewer/`.
- [x] Exit and Back work, and memory returns to the start-page level.
- [x] The browser and native builds of the same package match on the recorded path.
- [x] One command builds the site locally (`workflow.py web`), with a documented local preview.
- [x] CI builds and checks every branch; only `main` deploys, after all checks.
- [x] `release.json` identifies every file; the review page shows it.
- [x] Rollback is documented and automated.
- [ ] The live deployment is verified by the verify job after the owner approves the squash onto `main`.
- [ ] Firefox, Safari, phones running the Godot build, and real-GPU frame rates: not yet tested (TODO P05).
