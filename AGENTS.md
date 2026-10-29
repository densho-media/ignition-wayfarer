# Wayfarer: agent contract

Google Drive workbooks define the spacecraft. Follow **Drive → structured
parameters → shared formulas → Blender geometry**. Blender is a derived
representation, never an independent authority. Godot consumes generated geometry
and shared data. This standalone spacecraft project
does not use the parent Densho application's stack.

The goal is visible, constraint-respecting 3D progress. Don't add process,
tests, tooling or abstractions the next visible result doesn't need.

## Where things go

Each purpose and development stage has one place. Add no top-level folder without the owner.

| Place | Holds |
| --- | --- |
| `data/` | the parameters (`wayfarer_3d.toml`), source map, detail packs and `data/simulations/` (imported and generated scenario JSON) |
| `src/wayfarer/` | pure modules, Blender generators (`components/`, `build/`), validation, presentation, shots, export |
| `assets/` | the built `.blend` libraries of the approved ship (generated, not in Git) |
| `tests/`, `tools/` | owner-number and invariant tests; the workflow commands |
| `godot/`, `web/` | the walk and its runtime checks; the website (start page, Explore Ship, Enter Wayfarer, status page) |
| `references/` | the geometry baseline, `p1_*.json` reports the code writes, `evidence/` (kept study results); local-only captures and notes |
| `runs/` | every run directory and `runs/renders/`; disposable, pruned per step 6 |
| `work/<task>/` | everything not yet approved, one folder per task, named like its branch |

- **Work in progress** lives only in `work/<task>/`: `NOTES.md` (function, fixed constraints, unknowns, design freedom, decisions),
  study code, `WORK_<TASK>.blend` and `REVIEW_<TASK>.blend`. Nothing in `src/`, `tests/`, `tools/`, `godot/`, `web/` or CI reads
  `work/`. Text and code there are committed on the task branch; `.blend` files are not.
- **Review** means only the owner handoff: `work/<task>/REVIEW_<TASK>.blend`, one packed file that opens showing the change (the
  approved ship appended, the change in `WORK_<task>` collections, a framed camera, nothing to run), copied to the owner's
  checkout, or a GitHub Pages link. Never hand over a script or command as the review path.
- **On approval** the chosen form goes into the generators and `data/`, numbers worth keeping into `references/evidence/<task>.json`,
  `work/<task>/` is deleted, and the branch is squashed onto `main` (step 5). On `main`, `work/` holds only `README.md`.
- **Inside every `.blend`:** `GEN_<asset>` is generator-owned. In the vehicle file it has numbered groups: `10_SHIP` with one group
  per system (`11_STRUCTURE`, `12_DRIVE`, `13_THERMAL`, `14_HABITAT`, `15_FORWARD`, `16_SERVICE`, `build.py` SYSTEM_GROUPS),
  `20_HUMAN_SCALE` (one `HUMAN_<figure>` each), `30_CAMERAS`, `40_SIM_RIG`. `ART_<asset>` holds hand work; `WORK_<task>` appears only
  in work and review files. Exported nodes carry a zone (`EXTERIOR`, `SHELL`, `INTERIOR:<area>`, `representation.zone`): one model,
  never an exterior and an interior copy.
  Outliner colours: a colour is a ship system or an unapproved stage, grey is a helper. Structure brown, drive red, thermal orange,
  habitat green, forward blue, service yellow (`build.py` SYSTEM_COLORS); `ART_` violet, `WORK_` pink; GEN, `10_SHIP`, human scale,
  cameras and the sim rig stay uncoloured.

## The loop

1. `python3 tools/workflow.py status` checks the inputs. Read only
   the relevant TODO entry, `docs/MODEL.md` section and modules.
2. Edit the named parameters in `data/wayfarer_3d.toml`, the pure geometry
   module or the Blender generator in `src/wayfarer/components/`. For an
   uncertain form, try it in `work/<task>/` (a study script or a `WORK_<task>`
   collection) with explicit PROTOTYPE choices first; only the chosen form goes
   into the generators.
3. Check only what the change can affect (table below).
   `python3 tools/workflow.py pipeline --quick --expect <prefixes>` validates,
   runs the unit tests the change selects, builds, diffs the geometry against
   the current baseline and renders draft COAST side, top and three-quarter
   previews. A geometry change outside the `--expect` prefixes fails the run.
   Read the diff, open the previews, whole ship first, and repeat.
4. Before a commit that changes geometry, run the full
   `python3 tools/workflow.py pipeline --expect <prefixes>` once. It adds all unit
   tests, whole-ship saved-asset inspection and Cycles COAST and HIGH_POWER previews.
   Explain any unexpected geometry change. For an intended one,
   `python3 tools/workflow.py accept <run_dir> <name>` makes it the new baseline.
   With an empty geometry diff, the quick run is enough.
5. Update `docs/MODEL.md` and TODO in the same change. Commit only when the user
   asks, one change per commit. Git is the undo.
   Branches: `main` is the approved, validated baseline; nobody commits to it
   directly. Work on `local/<task>` (workstation) or `claude/<task>` (Claude Code
   Cloud) and validate as above. Feature branches are the whole Git process: no pull
   requests, GitHub issues or tags (an old state is a commit hash). Once the owner
   approves in chat or by text, squash the branch onto `main` as one commit
   (`git merge --squash`) and push `main`. Then delete the branch, or restart it
   from the new `main` before reusing it. The repository is public: every pushed
   branch and `main` are visible at once, so push nothing that the publication
   rules below keep local.
6. After a slice or phase is committed, prune `runs/`: delete every run directory
   the commit no longer needs. Keep the newest passing `pipeline` and
   `runtime-export` runs, any run named in TODO, docs, `references/` or an open
   owner question, uncommitted `runs/drive_inbox` captures and deliberate backups
   (`*-pre-*`). `python3 tools/workflow.py prune` lists the candidates with sizes
   and deletes nothing; show the list and ask, then
   `prune --delete <runs>` removes only approved candidates. Never prune while a
   build or export runs (prune takes the write lock).

`python3 tools/workflow.py checks` shows what the working-tree change selects
(tests, build target, inspection groups, Godot checks) and why; `--run` runs
the selected tests. The quick pipeline uses the same selection.

| What changed | Check while working |
| --- | --- |
| Docs, TODO, `docs/MODEL.md` | nothing |
| A detail pack (`data/detail/<pack>.toml`, its committed `.glb` meshes, `src/wayfarer/detail/pack_<pack>.py`) | `module validate <pack>`, `module build <pack>` (`--integrate` for a new pack), `pipeline --quick --target auto --expect Prod_ Detail_ WF_DETAIL`; `module publish <pack>` when done (docs/MODULES.md) |
| A generator in `src/wayfarer/components/` | `pipeline --quick --target auto --expect <prefixes>`; no unit tests (none import Blender code); add `--inspect auto` when it moves a clearance, pressure boundary, mechanism or interface |
| A pure module `src/wayfarer/<m>.py` | `pipeline --quick` (selects its tests and its consumers' tests), or `checks --run` and its fit screen first |
| Values in `data/wayfarer_3d.toml` | `pipeline --quick` (tests of the modules naming the changed keys, plus spec and owner targets; a full build); `--inspect auto` for interfaces |
| `spec.py` or a formula many modules share | `pipeline --quick` (the selection widens to all tests) |
| `tools/` | `checks --run` (the tools tests) or a dry run of the changed command |
| Godot scripts or scenes | `runtime-check auto` against the published package; `runtime-export` when it reports STALE |
| Cameras or preview code only | `preview.py` on the saved assets; no build |

Don't rerun a check that already passed on unchanged files, and don't run the
full pipeline to "be safe" after small edits.

Tests protect owner numbers and physical invariants only, not wording,
provenance bookkeeping, display machinery or PROTOTYPE positions. A review
finding doesn't become a test. Fit screens of PROTOTYPE parts run on demand
(`python3 src/wayfarer/<module>.py` for `crew_transfer`, `drive_manifold`,
`power_storage`, `rotor_interface`, `habitat_interior`, `human_entry`, `sector_whitebox`, `storeroom`, `survival_fit`, `drone_fleet`, `drone_demo`, `drone_routes`, `drone_bodies`); `inspect` checks the
built geometry. Passing checks and previews are not engineering proof.

## Modular detail

Production detail is added in detail packs, one writable owner per pack (docs/MODULES.md); approved hand-authored meshes travel as committed `.glb` data (`module export-authored`), editable `.blend` sources stay local. `module show <pack>` names the owned files,
the read-only dependencies and the anchor; a session edits only its owned files. `data/modules.toml`, the detail core
`production_detail.py`, the anchors and the generators are integration changes. A published pack is eligible for integration, not
owner-accepted; new detail stays `L4_VISUAL_CANDIDATE` until review.

## Development-flow controls

- Check selection (`tools/checks.py`) follows the import graph from the changed
  files, cuts at the spec loader (a shared-formula change selects the spec and
  owner-target tests rather than every test that loads data), maps TOML changes
  to the modules naming the changed keys, and adds neighbouring interfaces from
  an explicit table: shared clearances, pressure boundaries and mechanisms pull
  in the hull-contact, rotation and route inspection groups. Shared modules,
  unplaced files and unnamed TOML keys widen to everything. Do not add unrelated
  EVA, crew-dynamics or study suites by hand.
- The full pipeline in step 4 stays the pre-commit gate: all tests, whole-ship
  inspection and the whole-asset fingerprint. A quick or scoped run prints
  `verification: SCOPED ...` and is never a whole-ship PASS; `accept` refuses it.
  Inspection groups (`inspect.py --scope`, `pipeline --quick --inspect`): drive,
  rotation, hull, thermal, forward, timeline, route; the core checks (file set,
  hashes, IDs, links, interfaces, rig contract, envelope) always run.
- Previews: `--quality draft` (Workbench, form and fit; the quick default),
  `material` (Eevee 16 samples, GPU, quick material preview without baked indirect lighting),
  `review` (Cycles 16 samples, material, emission and display review; the full
  default) and `look` (Cycles 64 samples, explicit look reviews only). Section
  views stay Workbench. Standalone `preview.py` defaults to draft and renders side, top, three-quarter
  and body_detail unless `--views` names others (`--views all` for every view).
  Keep the three whole-ship views and add only relevant close-ups. Camera-only
  work renders the saved assets without a build.
- Runtime: `runtime-check [names|auto]` runs Godot checks in `godot/` against the
  published package only when every package input (non-study code, data, route,
  character assets, project settings, Blender and Godot versions) matches its
  `build_identity.json`; otherwise it reports STALE. `runtime-export` remains the
  rebuild, full check and publication.
- `eva --only <stages>` and `characters --stages <stages>` rerun part of those
  loops; a skipped stage must be current (its inputs unchanged since it last ran
  through the loop), and the summary marks a partial run.
- Keep Python. Profile before optimizing; the access search, rig contract and
  hull contacts were sped up without changing their results. No Mojo migration or
  new build framework. Do not add benchmarks to every modeling edit.
- With concurrent sessions, re-read shared files before patching and preserve
  others' changes. Reuse checks only when their relevant code, inputs and
  dependencies remain unchanged; input TOML hashes alone do not prove that.
  Preserve the single-writer build lock and ART backups.

## Pipeline workflow optimization: calculate constraints, model form

Calculate what constrains the design; use engineering judgment and visual intuition
to shape what fits inside those constraints. Physical consequences, not vertex
count or mesh detail, determine when calculation is needed.

- Source or calculate architecture-driving quantities: propellant volume and mass,
  thermal balance and radiator area, spin gravity, shielding requirements and major
  loads. Keep missing answers OPEN; reversible visual work elsewhere can continue.
- Check local function with dimensions, simple geometry and the affected interfaces:
  movement envelopes, pressure boundaries, crew passages, maintenance access and
  thermal expansion. A credible-looking load path is not proof of strength.
- Design plausible construction by judgment: service covers, assembly divisions,
  equipment housings and local bracket forms. Use intuition for bevels, panel rhythm,
  material and colour hierarchy, lettering, restrained wear and interior atmosphere,
  within the applicable culture and art direction. Details need a functional or
  cultural reason, not a formula for each vertex. Revisit calculations if a detail
  changes a physical budget or interface (for example, a real non-emitting radiator
  seam changes area; a surface marking does not).
- Explore one bounded area in `work/<task>/` first, preserving the
  generated engineering reference and ART backups. Briefly state its function,
  fixed constraints, unknowns and design freedom in its `NOTES.md`;
  do not add a mandatory template or tool. Unsourced physical choices remain
  PROTOTYPE. Review whole-ship silhouette, assembly form and human scale before
  repeating details. Integrate selected repeatable construction into generators;
  keep artistic fit-out separate where appropriate.
- Judge visual choices through previews; add no unit tests for appearance or
  prototype positions. Check affected interfaces for functional edits and shared
  invariants for physical edits, using the existing selection and pipeline controls.
  This does not waive the full pre-commit geometry gate in step 4. A calculation
  should answer a consequential design decision; defer analysis that the next
  visible result does not need.

## Drive canon

- The IGNITION Table of Contents routes each fact to its owner workbook, then
  S&E `15_MODEL_INTERFACES` and the owner rows. Current Drive workbooks supersede
  older uploads and copies; the request Doc and the status sheet are
  correspondence, not canon. Report conflicting owner data with its ranges
  instead of choosing a winner.
- Owner questions live in the request Doc "IGNITION — Wayfarer Claude Request",
  as the TOC routes them (`98_CHANGE_PROTOCOL` Storage B–E): a live queue, flow
  POST → RESOLVE → CANONICALIZE → CONSUME/APPLY → VERIFY → DELETE. New questions
  get an ID `YYYY-MM-DDTHH:MM±HH:MM — short topic`, never a new Q number. Once
  an answer is in its owner workbook, built and checked, Claude deletes the item
  (only the unresolved remainder stays). The short model status per area lives
  in the Implementation tab of the sheet "IGNITION — Wayfarer Claude Model
  Status"; update the row of any area whose state changes.
- New canon: `workflow.py drift` lists changed workbooks; export them as xlsx;
  `workflow.py capture references/drive_capture_<date>` (with `--file key=path`
  when the Drive-inbox hook isn't active); `workflow.py delta <capture>` maps the
  changed cells to parameters. Update the spec and source map together, run the
  loop, then `workflow.py sync commit <capture> --note "<what was done>"`.
- Draft owner questions locally. Write to Drive only with the user's authorization.
- Publication: the GitHub repository is public. Drive captures
  (`references/drive_capture_*`), owner correspondence and internal review notes
  (`references/*.md`) stay local and are ignored by Git; the published production
  inputs are `data/*.toml`, `data/simulations/*.json` and the current baseline. Tests
  carry their own fixtures and never read a capture.

## Data rules

- `data/wayfarer_3d.toml` holds the parameters; `data/source_map.toml` records
  the workbook, sheet, range and status behind each `source_ref`. Workbook
  statuses keep their source meaning; a BASELINE range doesn't canonize a value
  selected inside it.
- Keep source values, derived values (shared pure formulas) and Blender settings
  distinct. An unsourced physical choice is **PROTOTYPE**. Unresolved physics
  stays `known = false`, never zero. Don't copy mesh measurements back into canon.
  Physical radiator area is independent of view factor; never shrink it to fit.
- **Hard Science Fiction Punk (HSFP)** is the design philosophy: research →
  physics → constraint → engineering → adaptation → culture → identity → style.
  Major shapes should be explainable by what they do (shielding, radiators,
  thrust structure, crew protection, service access); no fins, greebles or glow
  just to look futuristic. Neither HSFP nor the Ignition art style overrides
  engineering canon.
- Interiors and people also take Culture `31_ARCHITECTURE` (meaning), the Fashion
  Bible (clothing) and the Art Style Bible (depiction) as inputs (request Doc §13):
  once a zone's whitebox passes its human-scale review, it gets a cultural
  architecture pass, then character and clothing passes, silhouette explorations
  and a selected greybox. Keep these layers apart from the engineering geometry;
  fit-out and characters never change a pressure boundary, an interface or the
  route clearance.

## Blender

- Use the Blender CLI (`/snap/bin/blender`) and its bundled Python for `bpy`.
  The pure modules are standard-library only. Metres, +X bow, +Z dorsal.
- Scripts own only `wf_owner = wayfarer.p0` content in `GEN_*` collections.
  Manual work goes in `ART_*` or untagged collections. Never hand-edit generated
  meshes; every save is backed up to `milestones/` (newest three per asset).
- Shared input or formula changes need a full build; `--target` is for isolated
  component code. Geometry stays `REP_PROXY`.
- One session builds at a time: the pipeline holds a lock and reports BUSY.
  Wait for it; a worktree only for a genuine experiment (a full build regenerates the assets there).

## Godot

- `godot/` owns runtime scenes, input and presentation, never spacecraft facts.
- `python3 tools/workflow.py runtime-export` builds in a disposable workspace,
  exports the static COAST model and checks it in Godot before publishing.
  Use it for exporter, contract, geometry and publication changes; for Godot
  scripts and scenes alone, `runtime-check` against a current package is enough.
  Leave the production Blender loop unchanged. Inspect the three runtime views
  after visual changes.
- Never edit `godot/generated/` or `.godot/`; keep authored wrapper scenes separate
  from imported geometry. Rig JSON retains canonical Blender axes and unknowns.
- Current export IDs identify static placements. Add semantic mechanism bindings
  before interaction. Do not derive physics from visual meshes or proxy cages.

## Incremental optimization

Apply these guidelines when the current task touches the relevant geometry, export or runtime code.
Keep the next visible result as the priority; these are defaults for ongoing work, not a separate refactor backlog.

- Make the smallest useful improvement in the area already being changed. Defer unrelated cleanup, framework
  work and renderer migrations. Reuse the existing build/check loop; add no mandatory benchmark to ordinary edits.
- Keep authoritative dimensions and constraints in shared pure formulas. Generate static geometry during authoring
  or export; Godot consumes it and drives presentation and semantic mechanisms. Use Geometry Nodes only where
  an artistic layer benefits and the project's geometry/inspection contract permits it.
- Reuse linked components, mesh data and materials. Keep instances until unique geometry is actually needed.
  Use stable seeds per component or zone for procedural variation; local edits should not reshuffle the whole model.
  Review selected forms at whole-model and human scale before multiplying them.
- Choose runtime boundaries by visibility, material and independent movement. Batch nearby static repetitions
  only when useful; preserve moving parts, picking, source/status metadata and a distinct identity per placement.
  Avoid both one object per tiny detail and one mesh spanning every space.
- Keep authored Godot scenes separate from generated imports; organize new behavior by feature and extract shared
  components when a real second use appears. Keep Blender working views focused on the current area and expensive
  artistic detail separate from constraint review.
- Before a performance-motivated change, confirm the export matches the intended source snapshot and measure the
  suspected cost in a representative view on the target renderer/hardware. Compare the same view afterward:
  frame time/draw calls for rendering, memory/load time for sharing, or build time for iteration. File triangle
  counts and headless checks alone do not establish runtime speed. Inspect visual quality and behavior as well.
- Check existing import settings before adding optimizations: LOD and surface deduplication may already be enabled.
  Verify actual imported sharing. MultiMesh needs local visibility groups; Forward+ automatic instancing must not
  be assumed in Compatibility. Choose renderer changes from measured needs.
- Preserve silhouette, clearances, interfaces and intended material/light behavior. Spend geometry on visible form;
  use reusable textures or baked procedural surface detail where appropriate. Keep material baking distinct from
  static lighting so moving lights remain correct. Report measured gains separately from hypotheses.
- Preserve irreplaceable ART work and authored assets through deliberate versioned backups. Ignored blend files
  and local milestones are not recoverable through Git alone.

When extending Wayfarer's export, preserve equivalent evaluated meshes across placements; equivalence includes
materials, attributes and object-dependent evaluation, not just a source name. Keep rotor, hatch, Crown and
display-driven bindings intact. Consider local static batching or exterior/interior detail visibility only where
the current feature and measurements justify it; never reduce physical radiator area or alter engineering geometry
to meet a rendering budget.

## Documents

README describes the project and stays stable. `docs/MODEL.md` describes the
current model, without history. TODO holds only unfinished work: delete an
entry once it's done. History lives in Git and `references/`. Commands and
architecture are in `docs/IMPLEMENTATION.md`.
