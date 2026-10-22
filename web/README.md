# Wayfarer web explorer (WEB-001)

A static browser viewer of the generated G.U.C. WAYFARER 001 (IGNITION), built by GitHub Actions from a clean
checkout and intended for GitHub Pages at <https://densho-media.github.io/ignition-wayfarer/>. It is a REP_PROXY
engineering view, not the Godot experience.

## How it is built

```
pipeline --quick --previews none     full Blender build + geometry diff against references/baselines.json (must be 0)
workflow.py web --pipeline-run <run> export/godot.py --out --draco on the saved assets -> GLB check -> site
tools/web_check.py <site>            headless Chrome, served under /ignition-wayfarer/
```

- **Export.** The browser GLB comes from the same exporter as the Godot package (`src/wayfarer/export/godot.py`, COAST, S004
  look), called with `--out`, `--identity` and `--draco`. It needs no Godot, MPFB characters or EVA suits, which
  `runtime-export` requires. It reads the saved assets and does not build geometry of its own. The Godot package is unchanged.
- **Identity kept.** Fourteen `Assembly_*` group nodes contain 3,936 `WF_<id>` mesh nodes, the same IDs as `manifest.json`.
  `model/nodes.json` maps each ID to its component, kind and canon/geometry status for picking. Axes: metres, bow +X,
  dorsal +Y (glTF Y-up from Blender `(x,z,-y)`).
- **Checked before publication.** `web_export.check_glb` checks the glTF header and chunk and the required extensions.
  It requires the mesh nodes to equal the manifest's records and the 14 assemblies to be present, and it checks the bounds
  and the 100 MB Pages file limit. `build.json` records the commit, dirty flag, Blender and three.js versions, input hashes,
  GLB SHA-256, bounds, triangle count and the pipeline run's geometry diff.
- **Draco.** It cuts the GLB from 32.5 MB to 5.9 MB. Positions are quantized to about 1.5 cm at the ship's 237 m length,
  which is acceptable for display and not a measurement source.

**Viewer technology: three.js 0.170.0** with no build step and no framework. It has a mature glTF/Draco loader, `OrbitControls`
with mouse and touch input, and supports node extras. Babylon.js is heavier. PlayCanvas Engine is tied to its editor and
was parked as FUT-006. The npm tarball is downloaded once, checked against its registry SHA-512 and copied into
`vendor/three/`. The site makes no CDN or other off-site requests. All paths are relative, so the site serves from any subpath.

## Use

Left-drag (one finger) orbits, the wheel (pinch) zooms, right-drag (two fingers) pans. Click a part to see its component.
Presets: 1 side, 2 top, 3 three-quarter, 4 bow, 5 aft; Home or Reset gives the whole-ship view. Esc clears the selection.
The Assemblies panel hides and shows each assembly. The footer links the source commit, Densho and the repository.

## Local test

```bash
python3 tools/workflow.py pipeline --quick --previews none
```

```bash
python3 tools/workflow.py web --pipeline-run runs/<that run> --out runs/web-site
```

```bash
python3 tools/web_check.py runs/web-site --out runs/web-check
```

To look at it yourself, serve a directory that contains the site as `ignition-wayfarer/` (for example
`python3 -m http.server -d <dir>`) and open `http://localhost:8000/ignition-wayfarer/`. Opening `index.html` as a
`file://` page does not work, because ES modules need HTTP.

## GitHub Actions (`.github/workflows/web-explorer.yml`)

- **Triggers.** Pushes to `main`, `claude/**` and `local/**`, plus a manual run. There is no `pull_request` trigger, so
  fork PRs never run it.
- **Jobs and permissions.** `tests` (all unit tests) and `build` are read-only (`contents: read`). `build` installs
  Blender 5.2.2 from download.blender.org with a pinned SHA-256 and caches the tarball. It then runs the quick pipeline
  (whose geometry diff must be 0), the web export and the browser check. Every action is pinned to a commit SHA.
- **Outputs on every branch.** Artifacts `wayfarer-web-site` (the site) and `wayfarer-web-check` (screenshots,
  `check.json`, logs). The run summary reports durations, sizes, the geometry diff and the browser checks.
- **Deployment.** On `main` only, `build` also packages the Pages artifact. The `deploy` job has `pages: write` and
  `id-token: write` and needs both other jobs to pass, so a failed test, geometry diff, export or browser check never
  deploys. `main` is the approved public version: every push to it updates the site. A feature-branch push never does.

## GitHub Pages setting (owner, once)

Settings → Pages → Build and deployment → Source: **GitHub Actions**. Until then the deploy job fails on `main`
and the site stays unpublished. After that, every `main` push that passes deploys. The deploy job prints the URL.
Settings → Pages → Unpublish takes the site down.

## Results

**Workstation, 2026-10-21.** Blender 5.2.2, from the saved assets of a quick pipeline run:
- Pipeline: PASS; geometry diff vs `baseline_m8_exterior` was 0 changed, 0 added, 0 removed. It took 72 s.
- Web export: 56 s. GLB 5.86 MB; site 7.35 MB, of which three.js and the Draco decoder take 1.1 MB.
- Model: 3,936 mesh nodes, 2,704 distinct meshes, 718,984 triangles, 14 assemblies.
- Browser check: Google Chrome 156, headless with software WebGL (SwiftShader). 20/20 PASS:
  - The page loads and the whole ship is framed (9 s).
  - Every mesh node and assembly is present.
  - Orbit, zoom, pan, Reset and the side, top and bow presets work.
  - Clicking a part shows its label; hiding an assembly and Show all work.
  - On a 390 × 844 phone emulation, the ship is framed, one-finger orbit and pinch zoom work, and there is no horizontal overflow.
  - Every request is served from `/ignition-wayfarer/`; there are no script errors.

**GitHub Actions, 2026-10-22, run 39736387702 on `7cd4c58`.** ubuntu-24.04 runner, Blender tarball from the cache:
- Unit tests: PASS in 68 s.
- Blender install: 32 s. Pipeline: 50 s; it passed with geometry diff PASS, which `web` requires before it builds.
- Export and site: 46 s.
- Browser check: 20/20 PASS on Chrome 155 (SwiftShader). The model loads in 25 s.
- The whole check takes 12 min, because software rendering on the runner is slow. That is CI time, not visitor load time.
- Build job: 14.5 min in total. Artifacts: `wayfarer-web-site` is 3.3 MB zipped and `wayfarer-web-check` is 1.2 MB.

Each run's summary (visible when signed in) gives that run's timings and sizes; failed checks also appear as public annotations.

**Not verified.** Real phones and tablets, Safari/iOS and Firefox, and frame rate on real GPUs. The check uses emulated touch
in Chrome. The built-in Claude browser pane has WebGL disabled; the viewer then shows a clear message instead of the model.
