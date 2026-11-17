# Web Graphics Engineering (GFX)

The technical standard for how G.U. WAYFARER 001 looks and performs in the browser. It applies to every change that affects what a
visitor sees or how fast it draws: Blender visual detail and export, Godot scenes and rendering, the three.js viewer, materials,
lighting, textures and shaders, browser delivery and loading, graphics performance, and the CI and runtime checks around them.

- **Authority.** This file is the technical authority. `TODO.md` section **W** is the only execution tracker (task IDs `GFX-…`);
  completed tasks leave it and their result lands here (§2, §12) and in `references/evidence/`. AGENTS.md "Web Graphics Engineering"
  holds the binding principles in short form; `.claude/rules/web-graphics.md` is the Claude Code checklist.
- **Related.** Materials and their physics: [MATERIALS.md](MATERIALS.md) (PMDS). Site colours and UI: [WEB_IDENTITY.md](WEB_IDENTITY.md).
  Site structure, budgets, CI and the WEB-002 measurements: [wayfarer-web-experience-plan.md](wayfarer-web-experience-plan.md) and
  [web/README.md](../web/README.md). Phone rendering and touch: [wayfarer-mobile-controls-plan.md](wayfarer-mobile-controls-plan.md).
  Runtime package, mesh sharing, benchmark protocol: [IMPLEMENTATION.md](IMPLEMENTATION.md) "Godot runtime" and "Runtime benchmark
  protocol". Exterior art direction: [PHASE4_PLAN.md](PHASE4_PLAN.md).
- **Status of this document (2026-11-15, Phase 0, owner-approved).** Sections 2, 3 and 12 describe what is built and what was measured. Everything in
  sections 7, 8 and 13 is a plan until its TODO task is done and its evidence is recorded. No real-hardware frame time exists yet.

## 1. Principles

These restate AGENTS.md "Web Graphics Engineering" with their technical consequences.

| | Principle | Consequence here |
| --- | --- | --- |
| A | Visual fidelity and performance are equally important | Every graphical change states what it adds to the image and what it costs (frame time, memory, download, complexity) against the experience's budget (§9.4). Neither side wins by default. A change does not have to raise FPS to succeed: a meaningful visual improvement may justify extra rendering cost when it is reviewed, documented and stays within the budget. |
| B | Engineering geometry remains authoritative | Drive → parameters → shared formulas → Blender → exported representations → Godot / three.js. Rendering representations are generated from the engineering geometry and never feed back. Dimensions, clearances, routes, colliders, mechanisms, component IDs and metadata never change for a rendering budget. |
| C | Optimize perceived visual quality | Materials, light, shadow, contrast, emission, composition and material hierarchy usually buy more realism per millisecond than polygons. A technique is used only where it works in the browser renderer (§3). |
| D | Browser constraints are first-class | GitHub Pages, static files, no custom headers, Godot Compatibility on WebGL 2, single-threaded web export, three.js 0.170.0. A renderer or engine change needs an explicit, evidence-backed owner decision. |
| E | Optimize by context | Engineering viewer, interior walk and exterior EVA share one ship but have their own runtime assets, profiles and budgets (§4). |
| F | Measure before and after | Comparable scene, camera, resolution and hardware. Real-hardware, emulated and software-rendered numbers are labelled and never mixed (§9). Software-rendering benchmarks give reproducibility and relative comparisons, never real-GPU performance. A visual review accompanies every performance claim. |
| G | Incremental, reversible improvements | One controlled change per task, a working baseline kept, no new frameworks, custom renderers or CI services without need. A failed experiment keeps its findings and leaves production. |

## 2. Architecture as built

```
Drive workbooks → data/wayfarer_3d.toml → shared formulas (src/wayfarer/*.py) → Blender generators → saved assets (assets/*.blend)
   → export/godot.py (one exporter, RT-005 mesh sharing, manifests with IDs, zones, layers, look, lights)
        ├─ COAST GLB + Draco  → web/viewer (three.js 0.170.0)                     Explore Ship, Engineering compare/ and build/ pages
        └─ DOCKED GLB + rig   → Godot 4.7.2 import → web export (single-threaded)   Explore Interior (walk), Explore Exterior (EVA Ops)
```

| | Explore Ship (engineering viewer) | Explore Interior (walk, EXC-001) | Explore Exterior (EVA Operations) |
| --- | --- | --- | --- |
| Code | `web/viewer/viewer.js`, `appearance.js`, `inspect.js`, `shield.js` | `godot/scenes/excursion.tscn`, `scripts/excursion/` | `godot/scenes/eva_ops.tscn`, `scripts/eva/` |
| Asset | `model/wayfarer-<hash>.glb`, Draco, COAST | `walk-<hash>.pck` (DOCKED scene), shared by both Godot experiences | same pack |
| Renderer | WebGL 2, `antialias`, `logarithmicDepthBuffer`, `stencil`; pixel ratio `min(devicePixelRatio, 2)`; ACES filmic; RoomEnvironment PMREM at 0.35 + hemisphere + two directional lights; no shadows; continuous `setAnimationLoop` | `gl_compatibility`, MSAA 3D ×2; AgX tonemap; colour ambient 0.18; one OmniLight per manifest emitter, the 16 nearest within 14 m on (checked every 0.25 s); a dim inspection key light | same project settings; colour ambient 0.6; a key and a fill DirectionalLight; no shadows set |
| Materials | the exported glTF PBR factors (no image textures in the ship exports); presentation overrides: ghost, hologram, engine holo, outlines (stencil-limited layers) | the exported factors, the Phase 4 runtime grammar (`look.exterior.grammar`), the fractal-shield shader | same |
| Existing optimizations | Draco; content-named files; click-to-load isolation; context release on `pagehide`; one ghost layer and ≤ 2 hologram layers per pixel by stencil; engine edges made once per geometry and disposed; always-on `stats` and `?diag` | RT-005 shared meshes (2,740 meshes for 3,989 nodes, Phase 4 S11); production-layer visibility ranges (28 m interior, per-tier exterior, `production_layer.gd`); nearest-16 lamp culling; touch-first 3-D resolution `RENDER_DENSITY` 1.25 with an adaptive 0.35–1.0 scale in a 24–45 fps band (`wf_touch.gd`); S3TC/BPTC desktop texture compression in the web export | same pack and touch scale |

Delivery (WEB-002): GitHub Pages from Actions, every file content-named, gzip by Pages, `Cache-Control: max-age=600`, no custom
headers. Budgets in `tools/web_export.py` (raw bytes): start page 60 kB, viewer 12 MB, play 90 MB, engine inspection 600 kB. CI
(`web-explorer.yml`) builds every branch, checks it in headless Chrome under SwiftShader (begin-frame control for the equivalence run)
and deploys only `main`.

Engineering · Ignition: what breaks (`web/engineering/ignition.js`, the ignition-failures study): the four engines as one `InstancedMesh`
of the 264 inspection parts (no ship GLB), per-part temperature, melt, vapour and fragment motion in two float `DataTexture`s read in the
vertex and fragment shaders (black-body emission, dithered vapour, no transparency sorting), additive plume cones, one particle cloud and
shock shells; both halves of the split view with one camera through scissor viewports; render on demand while paused; pixel ratio 1.5 on
touch, 2 on desktop, with a 0.25-step adaptive drop after a slow second. 5–9 draw calls and about 107 k triangles per half; SW frame times
in `references/evidence/gfx_ignition.json`, HW PENDING.

Engineering · Dust: what hits at speed (`web/engineering/dust.js`, the dust-impacts study): fully procedural, no model download.
One grain: section-cut bumper and skin plates whose shader (`onBeforeCompile`) draws the hit spot, heat, scorch, cracks and a
discarded hole; the debris cloud is an additive point cloud computed from the timeline uniform, so scrubbing runs both ways; sprite
flashes and a shock shell; the two speeds side by side through scissor viewports. The trip: the ship from lathe, cylinder and box
primitives, dust streaks as shader-driven `LineSegments`, one CPU-written spark pool. Same render-on-demand and pixel-ratio policy as
the ignition page. 10 draw calls for the split view, 24–30 for the trip; SW and EMU frame times in
`references/evidence/gfx_dust.json`, HW PENDING.

Diagnostics that exist: the viewer's `stats` / `renderer.info` and `?diag` overlay (frame time mean and p95 over 120 frames, draw calls,
triangles, geometries, textures, programs, JS heap, transfer); `web_check.py` metrics in `release.json` (`tests.metrics`: ready times,
transfer, requests, renderer memory); `godot/scripts/profile_views.gd` (native Godot: frame time, draw calls, primitives, objects, video
memory; walk only); the touch provider's `fps`. **Missing:** an in-page frame-time readout for the Godot web build, and any EVA view in
`profile_views.gd`.

## 3. Renderer capabilities and limits

### 3.1 Godot 4.7.2 Compatibility (OpenGL ES 3 / WebGL 2)

From the Godot 4.7 renderer comparison (`godot-docs` branch 4.7, `tutorials/rendering/renderers.rst`, read 2026-11-15). "Doc" means the
documentation says so; each row still needs a check in our actual web export before a task relies on it.

| Feature | Compatibility | Use for Wayfarer |
| --- | --- | --- |
| Lighting | forward single-pass; **8 omni and 8 spot lights per mesh** (adjustable); lights with shadows are multi-pass | the walk turns on up to 16 lamps: on a mesh near more than 8 the extra ones do not light it. Budget lights per mesh, not per scene (GFX-5B). |
| Shadows | supported; no PCSS, no contact shadows, no projector textures | few, deliberate shadow casters; every shadowed light is another pass |
| LightmapGI | **rendering baked lightmaps supported; baking needs a RenderingDevice (Vulkan/D3D12/Metal) machine** | the strongest realism tool for static interiors; bake on a GPU workstation (or a cloud lavapipe run, to be tested), ship the lightmaps in the pack |
| ReflectionProbe | supported, **2 per mesh** | interior metal and glass; probe placement per compartment |
| VoxelGI, SDFGI, SSIL, SSR, volumetric fog, DOF, TAA, FSR2, FXAA, SMAA | **not supported** | never assume them from native Forward+ or Blender |
| SSAO | supported (doc); cost on WebGL unmeasured | candidate for ambient contrast; measure first |
| Glow, tonemapping, adjustments, depth/height fog, fullscreen-quad post | supported | glow for real emitters only; AgX stays the tonemapper unless a review changes it |
| MSAA 3D | supported, no alpha-to-coverage; SSAA supported | today MSAA ×2 |
| 3-D resolution scaling | bilinear only (FSR modes need RenderingDevice) | what the touch scale already uses |
| Colour buffer | **RGBA8, low dynamic range**; no debanding, no HDR output | bright emitters and glow clip; gradients can band; exposure must be set for LDR |
| Depth buffer | **24-bit, no reverse Z** | camera near/far ranges matter: a 300 m ship seen from 1 m and from 1 km needs bounded clip distances per view |
| Decals | 8 per surface, 64 per view | restrained wear and markings without geometry |
| MultiMesh, visibility ranges, mesh LOD, occlusion culling | engine features available in all renderers; web cost to be measured | §7.4; mesh LOD and occluders change import or scene setup and must keep IDs and colliders |
| Compute shaders, RenderingDevice, particle trails / SDF collision | not supported | plume and field effects stay mesh/shader based |

Web specifics: single-threaded build (Jolt on the main thread, so physics and rendering share one CPU thread); the 4.7 templates need
wasm SIMD (Safari 16.4+); Godot documents WebGL 2 issues on Safari; the export compresses textures for desktop (S3TC/BPTC) only and not
for mobile (ETC2/ASTC off), which matters once the pack carries image textures (GFX-7C).

### 3.2 three.js 0.170.0 (WebGL 2)

- Available and already used: PBR `MeshStandardMaterial` from glTF, PMREM environment, ACES tone mapping, stencil, logarithmic depth,
  Draco, `renderer.info`.
- Available, not used yet: `InstancedMesh` and `BatchedMesh` (shared-geometry repetition with per-instance IDs), `reverseDepthBuffer`
  (r170: only when the browser exposes `EXT_clip_control`; otherwise it silently stays off), shadow maps, render on demand (draw only
  when something changed), `KHR_mesh_quantization` / meshopt decoding.
- Cost to know: logarithmic depth writes `gl_FragDepth` in every fragment shader, which disables early depth rejection, so overdraw costs
  full shading. The ghost, hologram and outline shaders carry the log-depth chunks (web/README.md); any depth change touches them.
- WebGPU (`WebGPURenderer`) is research only (GFX-8D), not a production path.

### 3.3 Browsers and hosting

GitHub Pages cannot set headers, so no COOP/COEP (no threads, no `SharedArrayBuffer`), no custom compression and no long cache lifetimes
beyond what content naming already gives. Pages caps files at 100 MB and sites at 1 GB. Tested so far: Chromium/Chrome headless with
SwiftShader only. Firefox, Safari, real GPUs, Android and iOS are **untested** (wayfarer-web-experience-plan.md §6).

## 4. Visual quality objectives and review

All three experiences are REP_PROXY, SIMULATION_ONLY representations of one ship. Each has its own profile and budget.

| | Objective | Reviewed by |
| --- | --- | --- |
| **Engineering viewer** | complete visibility of the model, faithful geometry, stable selection and picking, readable materials and annotations, consistent hologram and ghost states, responsive camera, efficient repeated geometry | whole ship (side, top, three-quarter), the aft cluster, an engine drawer; each style (Standard, Subsystems, Engine holo, Hybrid); a pick, a hide, a focus |
| **Interior walk** | convincing human-scale materials, atmospheric but readable lighting, plausible construction, spatial orientation, smooth movement and gravity transitions | station boarding line, spine corridor, a hub transfer, a ring A sector at eye height, a ring B sector |
| **Exterior EVA** | strong silhouette, realistic light response on metal, coatings and radiators, detail that holds at each viewing distance, clear component identity, convincing scale, smooth flight around the whole ship | the hatch at suit distance, the Brow and ram faces, a radiator blade root, the propulsion cluster, a whole-ship view from the drone |

Rules for every review:
- Screenshots or an interactive session at the named views (§9.2), before and after, at the same resolution. Automated checks prove
  behaviour, not looks.
- Hard-science-fiction punk (AGENTS.md, Art Style Bible): no glow, bloom, lens flare, fog or decoration that the physics or the culture
  does not explain. Emission only on real emitters (lamps, displays, plasma, hot surfaces at their temperature).
- Overlay colours (function, subsystem, hologram) explain function and are never materials (WEB-005). PMDS appearances are the only
  source of material looks.
- Owner acceptance is needed before a look is extended across the ship (GFX-3).

## 5. Material and lighting workflow

- **Physical versus graphical.** PMDS (MATERIALS.md) owns what a part is made of and its physics; its `appearances.toml` owns how that
  material looks (base colour, metallic, roughness, surface cue). Graphics work changes appearances and runtime presentation, never a
  material selection, property, evidence level or binding. A new appearance for an unselected material stays a PROTOTYPE look.
- **Path to the browser.** The runtime receives glTF PBR factors and the manifest `look` (S004 surface classes, the Phase 4 exterior
  grammar, wear, fractal shield). New appearance detail travels the same way: from the generator or the appearance record, through the
  exporter, into both runtimes. Godot and three.js never hold their own material catalogue.
- **Surface detail.** Today there are no image textures in the ship exports; detail is geometry or procedural shader (fractal shield).
  Normal and roughness maps, trim sheets and decals are candidates (GFX-3), baked in Blender from the same appearance, at a stated texture
  budget (§6.3), shared across parts, and only where a review shows they read.
- **Light.** Lights come from the manifest emitters (class, colour, energy, range) or are labelled display lights ("inspection key
  light", no sourced sun). Baked light is a derived, regenerable product of the saved assets, never hand-edited, and kept separate from
  material baking so moving lights stay correct (AGENTS.md "Incremental optimization").
- **Rotating and moving structures.** The rings and rotors turn. Light from lamps fixed to a ring can be baked in the ring's local
  space and moves with it; sunlight, the station, the drone lamp and suit lamps must stay dynamic. Reflection probes inside a ring move
  with the ring. Never bake world-space light onto a moving part.
- **Colour management.** Blender works in linear with AgX/Filmic view transforms; three.js outputs sRGB with ACES; Godot uses AgX on an
  LDR RGBA8 buffer. Exposure and tonemap choices are reviewed per experience against the Blender review stills, not matched number by
  number.

## 6. Geometry and texture optimization

### 6.1 Representations

The exporter produces representations for each consumer; the engineering geometry and its fingerprint stay as they are.

- **Allowed** after a benchmark: shared meshes and materials, instancing and batching with a per-instance identity map, visibility
  ranges, generated render LODs and impostors for distant views, merged static detail that is never picked, hidden or animated alone.
- **Required for any derived representation:** generated by code from the saved assets (deterministic, content-named), labelled as a
  representation in the manifest, the full-detail geometry still used for inspection, picking (or an exact pick map), colliders, routes,
  mechanisms and the geometry baseline.
- **Never:** editing or decimating the engineering source, shrinking radiator area, moving a clearance or collider, merging parts that
  move, are picked or carry their own source/status record.

This refines the WEB-002 record ("decimating or LOD-reducing the engineering geometry: forbidden"): the engineering geometry stays
untouched; a generated rendering LOD beside it is allowed when a measurement justifies it.

### 6.2 Draw calls and repetition

Explore Ship draws 5,241 calls for 1.42 M triangles (exterior default view, Vertex 1.2 evidence, 2026-11-14,
`references/evidence/vertex_structure.json`): one call per mesh node, although many nodes share geometry (radiator cells, fasteners, repeated brackets).
On real GPUs WebGL draw-call submission, not triangle count, is the likely CPU limit; this is a hypothesis until GFX-1 measures it.
Godot already shares meshes (RT-005), but each placement is still its own instance.

### 6.3 Textures

Budgets apply when textures arrive (none in the ship exports today): power-of-two sizes, mipmaps, a stated per-experience texture
memory budget, desktop S3TC/BPTC and, for phones, ETC2/ASTC or a KTX2/Basis path in three.js; shared trim sheets over unique maps.

## 7. Browser performance strategies

Candidates, in the order the evidence suggests; each becomes a TODO task with its own baseline.

1. **Pixel cost.** Viewer pixel ratio policy (today `min(dpr, 2)`: a DPR 3 phone shades 4× the CSS pixels with log depth on every
   fragment). Godot already scales the 3-D view on touch devices.
2. **Idle cost.** Render on demand in the viewer: stop drawing when nothing moves, resume on input, damping, drive animation, appearance
   or resize. Saves battery and heat; does not raise the frame rate during interaction.
3. **Depth.** Bounded near/far per framing, then reverse-Z where `EXT_clip_control` exists, instead of logarithmic depth, verified
   against z-fighting on overlapping shells, distant parts, picking and the ghost/hologram/outline shaders.
4. **Draw calls.** Instancing or `BatchedMesh` of shared geometry with an ID map in the viewer; MultiMesh or merged static detail in
   Godot where nodes are not individually picked or animated.
5. **Lights and shadows in Godot.** Respect 8 lights per mesh; prefer baked light for static interiors; few shadowed lights.
6. **Download.** The viewer is at 11.38 MB of its 12 MB budget (Vertex 1.2). Draco quantization settings or meshopt, and selective
   loading of inspection detail, come before any budget increase (budgets are never raised silently). The 39.5 MB engine wasm is 63 % of
   the play download; a custom engine build stays out of scope unless measurements show download is the visitor problem.

## 8. Adaptive graphics quality

- **Profiles.** High, Medium, Low, each a fixed set: render scale or pixel ratio cap, MSAA, shadow quality, visibility distances,
  texture resolution, optional effects. Defaults from measured capability (a short first-frame probe and the WebGL renderer string)
  rather than device labels alone, with a manual override.
- **Stability.** At most one automatic change per several seconds, hysteresis between thresholds, no oscillation; never change quality
  during a measured run.
- **Storage.** Graphics preferences live apart from the control profile (`user://wayfarer_controls.cfg` in Godot) and from viewer
  bookmarks; a new key never overwrites control mappings.
- **Existing piece.** The touch-first adaptive 3-D scale (MOB-001) is the first adaptive element; GFX-6 generalizes it instead of adding a
  second mechanism.

## 9. Benchmark methodology

Extends IMPLEMENTATION.md "Runtime benchmark protocol" (inputs, browser settings, median of three runs, viewer measures) to all three
experiences and real devices.

### 9.1 Evidence classes

| Class | Meaning | May support |
| --- | --- | --- |
| **HW** | a real device and GPU, named (model, OS, browser version, WebGL renderer string, power state) | frame-rate conclusions and budgets |
| **EMU** | device emulation (viewport, DPR, touch) on another machine | layout, input and pixel-count scaling only |
| **SW** | SwiftShader or llvmpipe software rendering (the cloud and CI) | reproducibility and relative before/after changes on the same machine; draw calls, triangles, bytes, memory (renderer independent); never representative of real-GPU performance |

Never present SW or EMU numbers as device performance. Never invent a measurement; a missing one is written **PENDING (HW)**.

### 9.2 Views

| ID | Experience | View | How to reach it |
| --- | --- | --- | --- |
| B1 | Explore Ship | whole ship, default three-quarter, Standard | `viewer/?diag` |
| B2 | Explore Ship | subsystem and engine holograms | `viewer/?diag#view=threequarter&style=subsystem`, then `style=engine` |
| B3 | Explore Ship | aft cluster, engine drawer with overlay | `viewer/?diag#view=aft&eng=N1&ov=eng` |
| B4 | Explore Interior | spine corridor at walking pace | the walk from the start to the first hub (to be fixed as a scripted path in GFX-1) |
| B5 | Explore Interior | ring A traversal at eye height | a ring A sector, one full sector walk |
| B6 | Explore Exterior | whole ship from the drone; hatch; radiator root and propulsion close-ups | EVA Ops free exploration (camera marks fixed in GFX-1) |

Resolutions: desktop 1920 × 1080 and 1280 × 800 at DPR 1; phone at its native DPR, portrait and landscape. Warm-up 3 s (viewer) or 6 s
(Godot) after ready, then 120 frames still and one scripted movement.

### 9.3 Record

Each run records: date, commit, site build (`release.json` id), device, OS, browser and version, WebGL renderer string, resolution and
DPR, power and thermal state, view ID, frame time p50/p95 and FPS, draw calls, triangles, geometries/textures/programs, JS heap and
(where measurable) GPU memory, load time to ready and bytes transferred, image-quality notes with screenshots, interaction notes.
Kept results go to `references/evidence/gfx_<task>.json` with the evidence class on every number.

### 9.4 Budgets (targets, not verified guarantees)

| | Desktop (suitable discrete or recent integrated GPU) | Supported phone (reference device to be agreed, TODO P05) |
| --- | --- | --- |
| Frame rate | 60 fps (16.7 ms p50, p95 ≤ 25 ms) | 30 fps (33.3 ms p50, p95 ≤ 50 ms) |
| Download | the `web_export.py` budgets | same |
| Interaction | orbit, pick and walk respond within one frame of the budget | touch response within two frames |

## 10. Compatibility constraints

- GitHub Pages: static files, relative paths, no headers, ≤ 100 MB per file, ≤ 1 GB site, content-named assets.
- Godot: 4.7.2 standard build, Compatibility renderer, single-threaded web export, official templates (no custom engine build).
- three.js 0.170.0 pinned in `web_export.py`; an upgrade is its own task with the browser check.
- Every experience loads only its own files (the start page loads three); the Godot experiences share one engine and one pack.
- Deterministic, reproducible exports; `godot/generated/` and `.godot/` are never edited; CI gates unchanged.

## 11. Proven, experimental, incompatible

| Proven here (built and checked) | Experimental (needs a task and evidence) | Incompatible with the current renderer or hosting |
| --- | --- | --- |
| Draco GLB; content naming; click-to-load isolation; instanced engine parts with per-part state textures and scissor split views (ignition page); procedural shader impact plates and timeline-driven particle clouds (dust page); context release; RT-005 mesh sharing; production-layer visibility ranges; nearest-lamp culling; touch 3-D scale; stencil-limited ghost/hologram layers; S3TC desktop textures | viewer DPR policy, render on demand, reverse-Z; instancing/batching; LightmapGI bake and web rendering; reflection probes; SSAO on WebGL; normal/roughness maps and trim sheets; decals for wear; render LODs; quality profiles; meshopt/KTX2 | in Godot Compatibility: VoxelGI, SDFGI, SSIL, SSR, volumetric fog, TAA, FSR2, FXAA, SMAA, DOF, HDR output, compute; on Pages: threaded Godot (COOP/COEP), custom headers; any WebGPU-only path as production |

## 12. Known bottlenecks and open evidence

- **No real-hardware frame time** for any experience (TODO P05, P4 S11, FSH, WEB-003/004). Every bottleneck below is a hypothesis.
- **Viewer:** 5,241 draw calls; continuous rendering when idle; log depth on every fragment; DPR up to 2; download at 95 % of budget.
- **Godot:** lights beyond 8 per mesh are dropped; LDR buffer; no baked light or probes yet; single-threaded physics plus rendering;
  `profile_views.gd` covers the walk only; no frame-time readout in the web build.
- **Delivery:** engine wasm 39.5 MB (10 MB gzip), pack 23 MB (2026-10-22 numbers; current sizes in each `release.json`).
- **Coverage:** Firefox, Safari, Android and iOS untested.

## 13. Roadmap and acceptance

The phases and their tasks are in TODO.md section W. Dependencies:

```
GFX-0 rules (approved 2026-11-15) → GFX-1 baseline ─┬→ GFX-2 viewer improvements (2A pixels, 2B on demand, 2C depth) ──┐
                                                    ├→ GFX-3 visual prototype (owner review) → GFX-5 Godot optimization ├→ GFX-6 profiles → GFX-8 cross-browser
                                                    ├→ GFX-4 draw calls and geometry ──────────────────────────────────┘
                                                    └→ GFX-7 assets and loading (7A early: the viewer budget)
```

GFX-1 can proceed in the cloud for SW evidence and the procedure; its HW rows wait for the owner's devices and do not block GFX-2 work
that is judged on SW relative numbers plus a later HW confirmation.

**Acceptance for any GFX task.** Classify the task first: a **performance improvement** succeeds by measured gain at
unchanged visual quality; a **visual-quality improvement** succeeds by a reviewed visual gain at a documented cost that stays
within the budget (it need not raise FPS). A task that does both reports the two results separately.
1. A baseline and an after measurement on the same view, machine and resolution, each with its evidence class.
2. Before/after screenshots of the affected views; no visual regression in the other styles or states.
3. Behaviour checks pass: `web_check.py` parts the change touches, `runtime-check` for Godot, picking/selection/hide/focus, input
   coordinates, touch controls, the equivalence check where Godot logic is involved.
4. Engineering geometry fingerprint unchanged (or the full pipeline gate when geometry changes for its own engineering reason).
5. The result recorded here (§2, §12) and in `references/evidence/gfx_<task>.json`; the TODO entry removed or narrowed.
6. A change that measures no benefit is reverted or moved to `lab/` with its findings.
