# Wayfarer implementation reference

Read only the sections relevant to the task. The rules and the working loop
live in [AGENTS.md](../AGENTS.md). Paths and commands in this reference are
relative to the project root. Runtime versions below record the prior
implementation environment; check the installed runtime when troubleshooting.

## Commands

Run everything from the project root. System `python3` (3.14) runs the pure-Python layer. Blender 5.2.2 at `/snap/bin/blender`, with its bundled Python 3.13, runs everything that imports `bpy`. There is no venv, package install or build tool.

```bash
python3 src/wayfarer/spec.py                      # validate inputs + print derived quantities; run before any build
python3 -m unittest discover -s tests              # owner-number and invariant tests (132 tests, ~57 s measured 2026-10-14)
python3 -m unittest discover -s tests -k view_factor   # single test by name substring

# Full build: components → subsystems → the vehicle (then retires listed files, see RETIRED in build.py)
/snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/build.py
# Targeted: --target NOZZLE|RADIATOR|RING_SECTOR|INTERIOR_HABITATION|INTERIOR_WORK|INTERIOR_GARDEN (rebuilds dependents + the vehicle), a subsystem name (e.g. HULL), or vehicle
#   --target HABITAT_A|HABITAT_B rebuilds one ring asset and its detail only (not the other ring, the assembly or the vehicle); HABITAT rebuilds both rings, the assembly and the vehicle
#   --target CHARACTERS rebuilds only assets/characters/WF_CHAR_INDUCTION.blend (IND-001; also rebuilt by all and SERVICE)
/snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/build.py -- --target RADIATOR

# Saved-asset inspection, rig contract, previews, visibility screen
/snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/inspect.py -- --output references/p1_validation.json
#   --scope <groups> (drive rotation hull thermal forward timeline route, or core) limits the posed checks; the core checks always run and the report's `scope` lists what ran
python3 src/wayfarer/sim_rig.py --check           # simulations/wf_sim_rig.json matches current inputs
python3 src/wayfarer/flight_timeline.py [--check] # simulations/wf_first_ignition_timeline.json (FUT-004); the build rewrites it too
# Accessories beside the ship (EVA suit look, drone bodies, compact PLSS study, standalone viewer tools/accessory_viewer.py): docs/ACCESSORIES.md "Run"
/snap/bin/blender --background --factory-startup --threads 8 --python-exit-code 1 --python src/wayfarer/presentation/preview.py -- --state COAST --size 1024 --views side top bow aft threequarter body_detail habitat_detail ring_detail root_detail hull_detail
#   --quality draft (default: Workbench, form and fit, no emission) | material (Eevee, 16 samples, GPU) | review (Cycles 16 samples) | look (Cycles 64 samples, explicit look reviews); section views are always Workbench
#   Eevee uses the graphics GPU automatically; the Cycles compute-device preference does not control it. Material mode uses direct lights without baked indirect lighting; use review/look for lighting and emission review.
#   without --views it renders side top threequarter body_detail; --views all renders every view (35)
#   --state takes any buildable configuration (COAST, LOW_THRUST, EVA, HIGH_POWER, FIRST_IGNITION, DOCKED on the one vehicle file) or a display pose (DEFENSE_ENGAGED, SHIELD_DAMAGED, RADIATOR_DAMAGED: the base preset plus the pose's control values, in memory) or a timeline mark (TL_*: the configuration its phase shows, posed with the timeline's control values by `common.pose_timeline`, captioned by `flight_timeline.caption`)
#   extra views: service_detail bay_detail power_detail hub_detail hub_section_detail (the section clips in front of the XZ plane; since P1-001 it spans the vestibule) crew_detail (coast crew route at the hubs); --hull hide also hides the rotor-bay doors; --sim-proxies show renders the hidden WF_SIMPROXY_* cages; output renders/p1/<config>
/snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/visibility.py   # writes references/p1_visibility.json

# On-demand reports (PROTOTYPE fit screens and studies; not part of spec validation)
python3 tests/verify_rebuild.py                   # in a disposable copy: ART_* preservation, regeneration, relocation, targeted isolation -> references/p1_regression.json
python3 src/wayfarer/studies/shadow_screen.py     # shadow-shield line of sight -> references/p1_shadow_screen.json
python3 src/wayfarer/studies/mass_proposal.py     # PROTOTYPE CoM/inertia proposal for the owner -> references/p1_mass_proposal.json
python3 src/wayfarer/habitat_interior.py          # rough interior fit report -> references/p1_interior.json
/snap/bin/blender --background --factory-startup --threads 8 --python-exit-code 1 --python src/wayfarer/presentation/interior_preview.py -- --size 768   # plan/section/cutaway per pod function -> renders/p1/interior
python3 src/wayfarer/drive_manifold.py            # drive-manifold geometry/clearance screen -> references/p1_drive_manifold.json
python3 src/wayfarer/power_storage.py             # storage/black-start checks -> references/p1_power_storage.json
python3 src/wayfarer/rotor_interface.py           # hub mechanism, service-path and state checks -> references/p1_rotor_interface.json
python3 src/wayfarer/crew_transfer.py             # crew route clearances, hatches, refuge reachability -> references/p1_crew_transfer.json
python3 src/wayfarer/storeroom.py                 # HUM-002 SP-45 storeroom fit screen: clearances, port branches, ladder reach, program volume and aisle
/snap/bin/blender -b --python src/wayfarer/studies/storeroom_survey.py -- --out runs/<stamp>-sp45   # every placement of the SP-45 cuboid against the saved vehicle, with trunk access
python3 src/wayfarer/human_entry.py               # HUM-001 route fit screen: passage to the trunk, hull gap, both leaf swings, fixtures, trunk fixtures, neighbours, both rings' vestibules and crew tubes, sector landing, refuge leg, mannequins -> references/p1_human_entry.json
/snap/bin/blender --background --factory-startup --threads 8 --python-exit-code 1 --python src/wayfarer/presentation/entry_preview.py -- --size 640   # exterior, twenty first-person cameras, the five induction stop views (stop_*) and the eight induction stills (ind_*), port/junction, trunk, both rings' vestibule and spoke cutaways, landing cross-section, refuge cutaway (hatches opened in memory; --views to pick; --look renders with the FUT-003 S004 look applied in memory) -> renders/p1/human_entry
python3 src/wayfarer/ring_circulation.py         # CIRC-001 fit screen: section, doors, compartments, budget, conflicts, the walked circuit's clearance -> references/p1_ring_circulation.json + RING_CIRCULATION_PLAN.svg
python3 src/wayfarer/station.py                  # STN-001 fit screen: the station boarding area and the boarding line into the trunk -> references/p1_station.json
$WAYFARER_BLENDER -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/circulation_preview.py -- --out runs/<stamp>-circulation   # CIRC-001: each ring from aft with the fill cut away, eye level in a corridor and in the through-passages (in memory, saves nothing)
godot --path godot res://scenes/excursion.tscn [-- --check-excursion [--shots=<dir>]]   # EXC-001: the station-to-ring excursion; the check drives both rings through the player's actions (WF_GODOT_EXCURSION; --shots with a display)
/snap/bin/blender --background --factory-startup --threads 8 --python-exit-code 1 --python src/wayfarer/presentation/hero_preview.py -- --size 1600   # FUT-003 First Ignition exterior stills ([look.exterior]; --views, --samples, --out-dir) -> renders/p1/hero_first_ignition
/snap/bin/blender --background --factory-startup --threads 8 --python-exit-code 1 --python src/wayfarer/presentation/m4_look.py -- --size 1600   # M4 (WF-006): crew-end exterior and ring A aisle with the MPFB pair, each physical and labelled fill, plus the pair's point of view with its fit (--views, --samples, --out-dir) -> renders/p1/m4_look
/snap/bin/blender --background --factory-startup --threads 8 --python-exit-code 1 --python src/wayfarer/presentation/drive_preview.py -- --size 1024   # 14 drive review targets x cinematic/engineering -> renders/p1/drive
#   --targets <names> renders a subset; --state picks the configuration (default HIGH_POWER); --modes cinematic|engineering
/snap/bin/blender --background --factory-startup --threads 8 --python-exit-code 1 --python src/wayfarer/shots/build_shots.py -- --render   # FUT-002 shots from shots/shots.toml -> shots/SH_*.blend + renders/shots/
/snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/shots/build_flight.py -- --render   # FUT-006 shots/SH_FIRST_IGNITION_FLIGHT.blend from the flight timeline + mark renders
/snap/bin/blender --background --factory-startup --python-exit-code 1 shots/SH_FIRST_IGNITION_FLIGHT.blend --python tests/verify_flight_shot.py   # mark frames against the timeline
/snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/shots/build_nav_stage.py -- --render   # NAV-001 shots/SH_NAV_STAGE.blend (ANALYTICAL + PRESENTATION) from simulations/wf_route_v1.json
/snap/bin/blender --background --factory-startup --python-exit-code 1 shots/SH_NAV_STAGE.blend --python tests/verify_nav_stage.py   # every frame against its route row
#   --shots <names>; --render-only; --frames <n...>; --size; --root <dir>
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_cutaway.py -- --asset   # M5: BODY-C study asset (assets/wayfarer/studies/) + overlap screen; before building the SH_M5_* shots
/snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_attitude.py -- --masses   # M5 slice 2: mass-region moments (runs/m5_mass_regions.json)
python3 src/wayfarer/studies/m5_attitude.py --out runs/<stamp>-m5-attitude   # inertia tensor, jet couples, shadow tolerance, LOS maps -> references/m5_attitude.json
/snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_eva_l2.py -- --asset   # M5 slice 3: EVA L2 comparison asset + rotor-bay channel and suit-corridor clearances -> references/m5_eva_l2.json
/snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_drive_support.py -- --asset   # M5 slice 4: nozzle support study asset + pickup/frame loads, support heat leak, bore gaps, measured overlaps -> references/m5_drive_support.json
python3 src/wayfarer/studies/m5_drive_support.py --legend <render> <png>   # annotate a SH_M5_DRIVE_SUPPORT* render with the legend and findings
/snap/bin/blender -b --factory-startup --python src/wayfarer/studies/m5_lettering.py   # M5 slice 5: lettering review asset (L1-L3) on the measured skin + obstruction screen -> references/m5_lettering.json
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/export/m5_hologram.py -- --out <package dir>   # M5 Godot hologram data + study GLB (runtime-export step export-m5; needs the COAST manifest.json there)
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_rcs_balanced.py   # M5 RCS-B: balanced RCS couples, plume / clearance / sweep screens -> references/m5_rcs_balanced.json + WF_STUDY_RCS_BALANCED
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_nozzle_mounts.py -- --asset   # M5 NOZ-2: F4/F8 frame statics, ring screen, REBCO mounts, bore -> references/m5_nozzle_mounts.json + WF_STUDY_NOZZLE_MOUNTS (python3 without --asset: screens only)
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_aft_robotic.py -- --asset   # M5 AFT-R: robot reach / paths / gates per aft target -> references/m5_aft_robotic.json + WF_STUDY_AFT_ROBOTIC (python3 without --asset: screen only)
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_body_c2.py -- --asset   # M5 BODY-C2: separate-species layout, free volume, interfaces, tankage ledger -> references/m5_body_c2.json + WF_STUDY_BODY_C2 (python3 without --asset: numbers only)
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_body_c3.py -- --asset   # M5 BODY-C3: grouped C2 layout, comparison C / C2 / C3 -> references/m5_body_c3.json + WF_STUDY_BODY_C3 (python3 without --asset: numbers only)
python3 src/wayfarer/studies/m5_gnc_comms.py --out runs/<stamp>-m5-gnc-comms   # M5 attitude modes + COAST comms contacts -> references/m5_gnc_comms.json + sheets
python3 src/wayfarer/studies/m5_cutaway.py --map   # M5 subsystem map references/m5_subsystem_map.json; --legend <src> <dst> <title> annotates a shot render
python3 -m unittest discover -s tests -k crew_dynamics   # PHYS-001 frames, ring field, modes, push/tether, nav gating (docs/PHYSICS.md)
timeout -s KILL 180 /snap/bin/godot-4 --headless --fixed-fps 60 --path godot res://scenes/physics_lab.tscn -- --check-physics   # WF_GODOT_PHYSICS (Jolt crew physics checks)
timeout -s KILL 120 /snap/bin/godot-4 --headless --path godot --script res://scripts/check_route.gd   # WF_GODOT_ROUTE (route playback against all rows)
/snap/bin/godot-4 --path godot res://scenes/physics_lab.tscn   # interactive lab: G grab, Space push, R release, T tool, 1/2/3 zone, M mode, P profile, WASD walk on a floor
/snap/bin/blender -b --python src/wayfarer/shots/physics_traces.py -- --out runs/<stamp>-physics-shots runs/physics/<scenario>.json ...   # bake Godot traces onto proxies (+ --character <glb> ARTISTIC layer)
#   always run headless Godot under `timeout -s KILL`: a script parse error hangs it and the snap process can't be killed otherwise
```

### Claude Drive workers

`CLAUDE.md` routes substantial retrieval to `.claude/agents/wayfarer-drive-reader.md`
and exact user-authorized edits to `wayfarer-drive-writer.md`. Both use Sonnet;
Haiku is deferred until representative retrievals pass an evidence/usage comparison.
The main agent retains canon interpretation, local parameter/source-map changes,
capture/delta processing and the model build/check loop. Tiny reads can remain local
to the main conversation to avoid delegation overhead.

The workers allowlist the Drive, Sheets and Docs tool IDs observed in this user's
Claude sessions. The reader has only remote read/export tools; the writer adds
bounded Sheets value updates and Docs updates, not file creation, sharing or
spreadsheet structure changes. Neither has shell, local write or delegation tools.
Docs update scope is constrained by the worker's exact-patch instructions; its
connector tool itself can perform broader edits. Permission mode stays `default`.
If a connector is reconnected under a different ID, verify its live tool names
before updating these allowlists; do not grant an entire server as a workaround.
Synced Claude connectors may not appear in `claude mcp list`.
In Claude Code Cloud sessions the same connectors appear as `mcp__Google_Drive__*`,
`mcp__Google_Sheets__*` and `mcp__Google_Docs__*`, so a worker allowlisted by
instance ID has no Drive tool there and returns BLOCKED; until the allowlists
cover the cloud names, the parent session does the bounded reads itself.

Start a new Claude session to load the new agent directory. For a read check, ask
for the reader to retrieve a known bounded range with its units, status and source
metadata, and compare it to direct evidence. Test owner discovery and a range with
formulas/notes as well before trying Haiku. Compare elapsed time and actual usage,
including retries and main-agent review. No cost or speed improvement is assumed.
Exercise the writer only during a real authorized edit: supply the exact patch and
expected old contents, then review its before/after and read-back receipt. Missing
tools or changed preconditions must return to the main agent without mutation.

First real runs (2026-10-09, Sonnet, no Haiku comparison yet):
- **Reader.** Drift check over the IGNITION and Wayfarer workbooks, the request Doc sections and a status range: 190 s, 14 tool calls,
  about 61k tokens, no retries. Its drift verdict and Doc excerpts matched direct reads. `read_doc` output for the 80k-character Doc
  came back as one JSON line too long for Read/Grep; the reader fell back to the Drive text export, which drops comments and authors.
- **Writer.** Six Doc questions and three status cells: it stopped at its 16-turn limit mid-task (24 tool calls, 110 s) and finished
  when resumed (37 tool calls, 193 s, about 65k tokens in all). It used `requiredRevisionId` on every Doc write, kept the new paragraphs
  off the next heading's style, and found and repaired one dropped sentence itself. It replaced a long cell's first sentence by
  rewriting the whole cell, so the main agent compared the rest against its own earlier read.
- The writer stopped at its 16-turn limit twice (a long Doc read overflows to a file it can only Grep), so its limit is 30.
  Give it one file per hand-off, or a long edit list in parts. The main agent still reviews each receipt.

### Workflow commands

Each command prints short JSON:

```bash
python3 tools/workflow.py checks [paths] [--base REV] [--run]
                                                     # what a change selects: tests, build target, inspection groups, Godot checks, with reasons; --run runs the tests
python3 tools/workflow.py pipeline --quick [--target T|auto] [--tests auto|all|none] [--inspect auto|all|none|<groups>] [--quality draft|material|review|look] [--expect PREFIX...]
                                                     # the modeling loop: spec -> selected tests -> build -> [scoped inspection] -> fingerprint diff -> draft COAST previews
python3 tools/workflow.py pipeline [--target T] [--previews auto|none|<preset>...] [--quality Q] [--expect PREFIX...]
                                                     # spec -> all tests -> build -> whole-ship inspect -> fingerprint diff -> scene report -> Cycles previews, once before a geometry commit
python3 tools/workflow.py accept runs/<pipeline run> <name>   # intended geometry change: new baseline references/baseline_<name>
python3 tools/workflow.py report                     # compact scene report of references/p1_validation.json (no Blender)
python3 tools/workflow.py readback [--install]       # owner measurement readback of the saved vehicle (~10 s): runs/<stamp>-readback/{readback,station_map}.csv + readback.md; --install copies to references/p1_*
python3 tools/workflow.py route-import [--check]       # NAV-001: 23_ROUTE_FRAMES of the route_frames capture -> simulations/wf_route_v1.json, refused unless 25_ROUTE_VALIDATION rows 2:13 PASS
python3 tools/workflow.py frames-import [--check]      # FRM-002-2026-10-10 (15!A125, C-017/C-018): time-tagged channels and phase/event streams -> simulations/wf_flight_frames_v1.json; UNKNOWN (null) until Sheets releases a table, refused on import-fidelity failures
python3 tools/workflow.py sources <term>             # source records and the parameters that cite them
python3 tools/workflow.py drift --since <UTC>        # hook-saved Drive metadata vs data/source_sync.json
python3 tools/workflow.py capture references/drive_capture_<date> [--file <key>=<xlsx>]   # exports -> evidence
python3 tools/workflow.py delta references/drive_capture_<date>   # cell delta -> delta.json + delta.md
python3 tools/workflow.py sync commit references/drive_capture_<date> --note "<what was done>"
python3 tools/workflow.py deps [status|fetch|install] [--optional]   # character dependencies: assets/external/manifest.toml, cache outside the repo
python3 tools/workflow.py characters [--only <ids>] [--no-fit] [--stages build rig export fit]   # MPFB humans: build, rig review, glTF + Godot check, in-ship fit (docs/CHARACTERS.md, ~2 min)
python3 tools/workflow.py runtime-check [names|auto]  # Godot checks in godot/ against the published package, refused (STALE) unless its inputs and tool versions match build_identity.json
python3 tools/workflow.py web [--pipeline-run runs/<quick run>] [--out DIR] [--native] [--no-play] [--reuse-play SITE [--reuse-native ZIP]]   # WEB-001/002 website from the saved assets: start page, Explore Ship (Draco COAST GLB, three.js), Enter Wayfarer (Demonstrator 01 Godot Web build, tools/web_play.py), review, release.json (web/README.md, ~4 min)
python3 tools/web_check.py <site> --out DIR --chrome <binary> [--record] [--live URL] [--part main|equivalence|touch|walk]   # headless-Chrome walk: loading isolation, viewer, play, switching, browser-vs-native recording, phone, touch
python3 tools/web_check.py <site> --merge DIR... --out DIR [--record]   # one report (and release.json tests) from the parts' check.json; CI runs each part on its own runner
python3 src/wayfarer/representation.py holo-style --manifest <manifest.json> --out <wf_holo.json>   # WEB-003 hologram colours per node (runtime-export, web play build; the viewer's holo-<hash>.json)
python3 tools/web_check.py <site> --out <dir>      # headless Chrome check of that site under /ignition-wayfarer/: framing, orbit, zoom, pan, reset, presets, picking, phone touch
python3 tools/workflow.py prune [--delete RUN...]     # AGENTS.md step 6 candidates in runs/ with sizes; deletes only named, approved candidates
python3 tools/workflow.py module list|show|contracts|build|validate|preview|publish|rebind <module|pack|assembly> [--integrate]
                                                     # modular detail (docs/MODULES.md): a pack's own detail assets, screens, readback and publication
python3 tools/workflow.py module export-authored <assembly> --id <ID> --objects <names>
                                                     # ART meshes of a detail asset -> data/detail/<pack>/<id>.glb + its manifest entry
python3 tools/workflow.py assembly validate           # every detail pack's saved assets and contract against its publication record
python3 tools/workflow.py eva [--no-renders] [--no-route] [--only <stages>]   # EVA suit: build on the saved pair, coverage/envelope/hold checks, access-pose hulls, SP-11/12/13 study (eva_access.py, then measured and rendered in the vehicle), EVA-003 comparison (eva_sp11.py + validation/eva_sp11_study.py, rigs posed in the chambers), renders, glTF, route (docs/EVA.md, ~9 min; --only <stages> reruns part of it)
/snap/bin/blender -b --python src/wayfarer/studies/eva3_district.py -- --out runs/<stamp>-eva3-district   # EVA-003 / SERV-003 integrated forward district (references/p1_eva_district.json, EVA3_DISTRICT_MAP.svg)
```

Measured on 2026-10-14 on production (before → after the DEV-FLOW changes, same
assets and inputs): full pipeline 475–498 s → 252 s (tests 123–135 → 58 s,
build 73–78 → 41 s, inspect 248–253 → 145 s, fingerprint 4 s); the quick loop
98 s → about 59 s for a generator-only change (no tests; the sum of the
measured spec 3 s, build 41 s, fingerprint 4 s and draft previews 10 s); standalone `preview.py` 78 s (35 Cycles views) → 13 s (default 4 views),
10 s in draft; scoped inspection 48 s (core), 81 s (core + hull), 103 s (core +
hull, rotation, route); `runtime-export` 290 s against `runtime-check` 113 s for all
14 Godot checks or about 2 s for two; the EVA loop 537 s, `eva --only route` 8 s.
The savings came from exact speed-ups (the access pose search 29 → 4.5 s, the
rig contract about 40 → 11 s, the hull BVH contacts 100 → 35 s, with identical
outputs) and from tests that evaluate only what they assert. Which check a
change needs is in the table in AGENTS.md. The
pipeline holds `.wayfarer-write.lock`, so a second session gets BUSY (exit 75)
instead of building the same assets. The geometry diff compares against the
baseline named in `references/baselines.json`.

Blender and the per-step timeout can be overridden with `WAYFARER_BLENDER` and `WAYFARER_STEP_TIMEOUT`.


Blender script arguments go after `--`. Every Blender entrypoint accepts `--root <dir>` so that it can run against a disposable copy of `data/` + `assets/`.

A geometry-neutral change shows 0 changed/added/removed objects in the pipeline's geometry diff. For an intended change, pass the affected object or file prefixes with `--expect`; any other changed, added or removed object, file or link is listed as unexpected and fails the run (the previews still render so the change can be looked at).

## Architecture

**Data layer (pure Python, no bpy).** `data/wayfarer_3d.toml` holds the offline spec, at schema version 5 (the source map must carry the same version). `data/source_map.toml` records the provenance of each value (workbook, sheet, range, status, revision, inspection date).

`src/wayfarer/spec.py` loads both files and runs `validate()` (about 1 s; `load()` validates identical file contents once per process and returns copies), which enforces the following:
- Every `source_ref` resolves, and its `canon_status` matches the source map.
- A `known = false` entry carries no `value`.
- An entry with `min`/`max` bounds stays within them and has `selection_status = "PROTOTYPE"`. A sourced range that is *not* a local selection therefore uses `lower_kg`/`upper_kg`.
- `evidence_ref` must resolve but is not status-compared. Use it for an OPEN sub-value that lives inside a WORKING/BASELINE row.
- LOCKED counts hold: 6 crew, 1 core, 4 channels/nozzles, 4 EYE facets, 3 radiators at 120°.
- Captured DERIVED values (rotor dynamics incl. 08!C39, DIAGNOSTIC ring comparisons 08!C37/C41:C45, cabin O2 partial pressure from `cabin_atmosphere.py`, design thrust) must be reproducible from current inputs (`validate_derived_sources`).
- The captured mass budget, EYE power rows and drive-heat calibration must reproduce the workbook formulas that tie them together (`validate_sourced_budgets`). These checks cover the burnout total, the 350 t rotating allowance, EYE/Brow mass rows, the laser and electrical derivations, and 16 GW = 160 TW × 1e-4. Operating drive waste heat must stay `known = false`.
- The configuration table is consistent (`validate_configurations`, including the 0.1 g low-thrust envelope and EYE modes).
- The radiator blade envelope passes the shadow/casing/ring/exclusion screen (`thermal_geometry.screen`), and the rotor sweeps, cage, forward mount and EYE support keep their clearances.
- The PROTOTYPE fit screens are not part of `validate()`: `habitat_interior.check`, `hull_geometry.check`, `drive_manifold.check` (including the owner's accepted nozzle-placement figures, Q26), `power_storage.check`, `rotor_interface.check` and `crew_transfer.check` run on demand through each module's `__main__`, and `inspect.py` checks the built geometry.
- The owner-answer data agrees: habitat layout (240 m³ inside the usable envelope, 2/2/2 functions), facet map (each quadrant once), mass regions (match the budget's rotating allowances), flight thrust and the ~10.6° low-thrust tilt.

`derived()` computes the quantities that the geometry uses. The other pure modules:
- `thermal_geometry.py`: radiator-blade geometry, the clearance/plume screen, and `supports()`, the radiator root booms, aft stays and coolant feeds (with their expansion-loop legs, `legs()`) shared by the thermal recipe, the hull openings and the rig. It also holds the AFT-001 compliance geometry: `root_band()`, `bay_joints()`, `mounts()` (one fixed datum per blade, sliding mounts elsewhere), `coolant_feed_path()` and the `compliance()` screen.
- `radiator_health.py`: the AFT-005 radiator health display (pure, standard library): the operating-sequence steps and breakpoints, the 480-cell grid and fault order, blade-local overlay geometry, the simple driver expressions and `display()`, spec validation and the `radiator_health` rig section. `validation/radiator_inspect.py` checks the saved overlays and drivers and every posed state against it, and compares a snapshot of the fixed blade objects with the saved one.
- `thermal_budget.py`: Stefan–Boltzmann ideal rejection and area, and the DIAGNOSTIC root-calibration margin that `spec.validate` compares with the captured 40_THERMAL value.
- `habitat_interior.py`: rough pod interiors in the pod frame (+X pod axis, +Y toward the floor): the deck/overhead section solved for 40 m³ (the overhead panel under the sector skin), zone blocks, plates, the overhead hatch and its panel opening (`hatch_opening()`, HUM-001 zone 5) and the fit report (including the coast deck radius against the owner's 30 m floor radius). Shared by spec, `components/interior.py`, inspect, the shot test and the interior preview.
- `drive_manifold.py`: the optically gated drive manifold. It holds the `[drive_manifold]` PROTOTYPE geometry (throat, smooth branch paths, lattice, seed coils, lasers, shield-plug chicane, optics, gate beams, separatrices), the normalized control properties and the single source of driver expressions (`drivers()`), `configuration_state()`, the 12 action key tables (`actions()`, `action_state()`), `couple_arm()` and the clearance screen `check()` with its findings. Shared by spec, `components/drive.py`, inspect, the rig contract and the previews.
- `drive_hot_section.py` (AFT-002): the PROTOTYPE `[drive_hot_section]` geometry around the plasma: replaceable core and throat liner tiles and the Q40 nozzle strike modules at the throat-side coils (`liner_tiles()`), the four cryogenic feed lines with their stepped shadow-shield sleeves (`cryo_feed()`), and the screen `check()`, called from `drive_manifold.check()`. The screen covers liner-to-plasma, coil, lattice and gate-beam gaps, feed clearances over the whole polyline, and `sleeve_sight_lines()`, a 3D check that no straight line passes a sleeve bore. Every OD-024/025/026 quantity stays `known = false`.
- `layout.py` (FGR-004): axial datums. AFT = −L/2 and FWD = +L/2 follow `ship.length`; RADIATOR_FRONT and RING_A are PROTOTYPE offsets in `[layout.datums]`. Every ship-frame X in the spec is `{datum, offset_m}`, resolved with `layout.x(s, ref)`; items take the datum of the zone they occupy (drive, reactor, engineering, tanks, power and thrust ring → AFT; radiator roots → RADIATOR_FRONT; rings, hubs, crew transfer, refuge, airlock, docks and service → RING_A; EYE, Brow and forward mount → FWD), so a length change moves zones rather than individual numbers. `spec.validate` rejects the old fraction and `*_x_m` keys.
- `hull_geometry.py`: the station-lofted hull (spans, openings, shell quads, enclosure margins), the service fittings and refuge, and their clearance checks (including sampled primary-cage members).
- `power_storage.py` (P1-007): the sourced storage layers and nine-step black start. It holds exact energy/time/ratio quantities and a DIAGNOSTIC extrapolated pack mass, the PROTOTYPE `[power_storage]` pack boxes and OPEN interfaces, and the ride-through markers (reusing load interface positions). It runs the member/cage/hull clearance and survival-isolation screens, the CONSTANT `WF_BLACK_START` key table (`step_state()`, `action()`) and `drive_alignment()`, which requires `WF_DRIVE_STARTUP` to show steps 3–9 at the black-start frames. The survival reserve may never charge the pulse bank, and every sizing value stays `known = false`.
- `rotor_interface.py` (P1-008): the sourced hub architecture (`[habitat.transfer.*]`, S&E `16_SPACE_MECHANISMS` MEC-001…015, I5/S6, OD-002/OD-013) and the PROTOTYPE `[rotor_interface]` stack. `stationary()`, `spokes()`, `rotating()` (rotor-local frame) and `ring_stop_locks()` give exact meshes/endpoints; `interfaces()` lists the OPEN stationary and rotating interfaces, including `IF_HUBn_POWER_FEED` on the rotor-transfer point. `running()` screens radial bands, the touchdown-inside-magnetic-gap rule, lock/arm/drum/pod gaps and axial neighbours; `withdrawal()` traces every cartridge's axial exit in COAST and BURN, lists removal prerequisites and requires touchdown and fluid cartridges to come out first. `actions()`/`state_rules()` define the stow and touchdown display states (spin LINEAR, flags CONSTANT; matched spin-down). `contract()` feeds the rig.
- `crew_transfer.py` (P1-001, partial): the PROTOTYPE `[crew_transfer]` route and the OPEN `habitat.transfer.crew_path`. `stationary()` (trunk in the spine bore, spine ports, fitting and refuge connectors; HUM-001: the trunk, the human-entry connectors, the human-entry spine ports and the refuge port (`human_entry.refuge_port_clear_m`) carry `hollow`, their clear radius) and `rotating(s)` (rotor-local vestibule, struts crew tubes and their spoke brackets) give exact curve points and the vestibule ring; `pod_hatches()` holds the overhead (coast) and end-wall (burn) hatches in the pod frame. `clearances()` samples every crew part against every obstacle (hub parts and P1-008 withdrawal paths, locks, spokes, refuge, fittings, packs, mount, cage, hull, radiator envelope, drums, arms, pod envelopes with torus shield bands and rails): exact at the burn index angle, swept (x, r) profiles in coast, open-ended tubes. `fit()` holds hatch/port/vestibule placement rules, `routes()` the reachability graph and route lengths, `alignment()` the hatch coincidence, `placement()` the Art Style crew screen, `derived_constraints()` the retracted-lock radius. `vestibule(s, j)` gives each rotor's vestibule stations: the P1-001 proxy, or for a rotor in `human_entry.vestibule_rotors` (HUM-001 zone 3) a hollow chamber derived from its single spine port and the suited envelope, grown aft from the lock-pin bound. The port is the 1.6 m passage unless another rotor's withdrawal paths (`rotor_interface.withdrawal_extent()`) end aft of the rotor; then it is the largest on a 0.05 m grid whose vestibule stays one clearance forward of them (`window`; ring B: 0.90 m), and the outer hatches take its size. The clearance screen allows 1e-9 m of float noise so this derived placement passes; `rotating()` marks it `hollow`, and `crew.hub()` builds it as a shell open toward the spine. `tube_path(s, j, la)` is a crew tube's axis (root, radial collar, 45° side leg, forward elbow inside the body, radial run beside the crew spoke to the sector-centre hatch); `tube_radii()` gives the 1.6 m tubes of the rotors in `human_entry.tube_rotors` (HUM-001 zone 4, marked `hollow`) or the 0.80 m proxy; `tube_neck()` gives a tube whose vestibule hatch is smaller (ring B) a neck of the hatch's size from the chamber to a bulkhead, the tube's root, placed to leave room above the hatch frame for a seated leaf, and `tube_floor()` the radius where the full bore begins (the vestibule wall or the bulkhead), one tube radius below the collar; `crew.tube_mesh()` builds the neck and bulkhead into the tube's shell; `tube_frames()`/`tube_point()` give mitered sweep frames (normals transported along the axis, rings projected on each joint's bisecting plane) shared by the mesh, the ladder and the mannequin, and `tube_radius_at()` the exact radius of a point inside a mitered segment; `hoop_cuts()` gives the inner-hoop openings for the hollow tubes (zone 5) and `trims()` the cylinder each hollow spine port is intersected with, so it ends on its vestibule chamber's inner radius (eye-level review), and the refuge port on the refuge cavity's inner face. `bores()` lists the HUM-001 openings as cylinders for the generators' boolean cuts (connector bore through the trunk, trunk and connector envelopes through the spine, trunk bore through the connector; the hollow spine ports are among the connectors). The trunk's required gap to every non-mated part is the residual spine shell, because the spine wall separates them (`trunk_inside_spine`). `contract()` feeds the rig.
- `sector_whitebox.py` (IND-001 phase 2, HUM-001 zones 6–8): the human-scale whitebox of the sectors. `[interior.layouts]` blocks are envelopes (`habitat_interior.zones()` takes an optional `z` = [inner] or [inner, outer] and an `open` (service) face: aisle, inner, outer, fore or aft). `shapes()` draws a berth as platform, lid and panels, a couch as back, foot plate, headrest, bolsters, harness and armrest consoles, a Garden rack as reservoir, trays with their crop, lid and panels, a mess as a booth (benches with backs and a table), a treatment couch as a pedestal table with mattress and foot plate, a work bench as top, cabinet, tool wall and shelf, and an operations row as standing desks or a seated console with chairs, within the block's bounds; `components/interior.py` joins them into one mesh per block for the functions in `[sector_whitebox].functions` (rack frames, consoles and displays, and harness straps take their own materials). `figures()` places the review mannequins (aisle, berth, couch, garden, seated, operator, patient, medic). `check()` screens berths (size, clear height, the access strip at the open face, steps, the axis against the spin, aft down), couches (size, the free strip in front, reach to the burn-go console), hygiene, headroom, racks and benches served from one face (depth, the strip in front, reach to the top tray, which way the worker faces against the spin axis), mess seats, operations stations, the treatment couch, the mannequins, the 12A program (`[sector_whitebox.program]`) and the Garden's rack volume against the owner's per-ring share (Q50). It runs on demand; `studies/induction_sectors.py` renders variants (plan, section, aft-down section, eye level) with cameras per function.
- `route_fitout.py` and `characters.py` (IND-001): the cultural fit-out of the entry (`[route_fitout]`, built into WF_SERVICE by `components/fitout.py`; 3.1 adds `trunk_elements()`, `landing_elements()` and `sector_sign()`, which `fitout.build()` builds with WF_CREW_TRANSFER, WF_RING_SECTOR and each interior; 3.2 adds `sector_elements()`, `seraph_elements()` and `service_recess()`, built with each furnished interior, and the screen `sector_check()`; `python3 src/wayfarer/route_fitout.py` prints the checks) and the induction figures with their staging and cameras (`[characters]`, built into `assets/characters/` by `components/figures.py`; 3.3 adds `couch()`, the newcomer on the treatment couch, built by `figures.couch()` in the vehicle frame; 4.2 adds `STAGE_VIEWS` and `stop_views()`, each induction stop's eye-level view (`[induction].stops` `view`) for the stills, the shot and the runtime). Both are PROTOTYPE layers that never change engineering geometry; `studies/induction_*.py` render the unpicked variants.
- `human_entry.py` (HUM-001 zones 1–5, the refuge leg and the thrust review): the primary boarding port, the trunk, the rotary vestibules and crew spokes of both rings, the sector landing and the storm refuge's entry as a hollow, human-scale route (`[human_entry]`, PROTOTYPE; 15!A86, 14!A32). `stations()` derives the chamber and node radius from the hatch hinge and leaf, places the chamber inside the collar by the shared clearance and the node floor one swing clearance below the open inner leaf; `shells()` (revolved pressure shells down to the trunk node and the inboard neck, kind `service_fitting`), `fixtures()` (hatch frames, handrails and brackets, lights, panels, valves of chamber and node; kind `entry_fixture`), `trunk_fixtures()` (trunk handrails, brackets and lights, clipped by `clear_spans()` around every branch in `openings()`, a short rail on each side of the refuge port at its angle, and the thrust ladder: stiles, brackets and rungs as `rods`, the fall-arrest rail and its end brackets), `trunk_ladder()` (the thrust review's ladder at `trunk_ladder_deg`: stile radius and half-angle, floor to top, where `clear_spans(margin=0)` first stops either stile line, rung stations and the rail), `hinge()`/`leaf_local()`/`leaf_points()` (outer leaf into the chamber, inner leaf inboard into the node), `vestibule_station(s, j)` (rotor j, default ring A), `vestibule_fixtures(s, j)` (rotor-local rails, light strips trimmed to the chamber, outer-hatch frames of the port's size as `tube` fixtures and the transfer panel, parented to the rotor), `ring_fixtures(s, j)` (everything that rides on rotor j), `mannequin()`, `trunk_mannequin()`, `vestibule_mannequin(s, j)` (rotor-local, placed at the index pose by `at_index()`; ring B's guides carry `ring_tag()` `_B`), `spoke_fixtures(s, j)` (each tube rotor's crew-tube ladders on the wall away from the spoke, from one end gap above the vestibule wall or bulkhead: polyline stiles through the elbows, rungs on the deck-referenced `rung_heights()` grid and brackets as `rods` segment lists, the fall-arrest rail on the ladder's centre line resting on the rungs (`arrest_rail()`) with its wall brackets where no rung carries it, light strips, the tube-side hatch panel), `spoke_mannequin(s, j)` (on the ladder of rotor j's spine-port sector, `vestibule_port_sectors`: ring A's at about 0.2 g, ring B's near the top of the run, each clipped to the rail by an arrester and link), `ladder_push(s, j)` (the spin lean and the Coriolis push across a tube ladder: which direction pulls the climber off the rungs, the neutral speed, the apparent overhang at `climb_review_speed_m_s` and the unobstructed fall speed), `landing()` (zone 5 stations in the sector frame: hatch frame and seat, closed and slid leaf, stile line and ends, landing well, chase), `landing_fixtures()` (built into the shared `WF_RING_SECTOR`; a `tube` with r0 0 is the leaf disc), `landing_mannequin()`, `landing_aisle_view()`, `refuge_station()` (the refuge leg: the port off the trunk, the inner pressure wall, the hoop-rail stations, one occupant station per rated occupant inboard of its anchor rail and the circulation radius between them and the inner-wall fixtures), `refuge_fixtures()` (hoop and anchor rails with brackets, light strips, the refuge panel; built in `WF_CREW_TRANSFER`; `hull.service()` builds the inner wall, kind `refuge_wall`), `refuge_mannequin()`, `trunk_climber()` (on the trunk ladder with aft down, its eye level with the refuge port, clipped to the rail), `cameras()` (the non-canon guides in the vehicle file), `route()` (the boarding route keyed `A1`…`B3`: to each sector of both rings as a zone-tagged world polyline at the docked pose, through ring B's necks, plus the upright walk to the aisle; `R`, zone `R`, from the trunk up the refuge port and half way round the refuge at the circulation radius; and `E`, the emergency approach, forward along the trunk from the nearest spine port aft of the refuge, up the same port and round the other half; IND-001 adds the induction ring's legs between sectors, `A1-A3` and `A3-A2`, and on the route ending in each induction sector the upright aisle walks to its stops), `induction_stations()` (each sector stop's station: its `pose` figure from `sector_whitebox.figures()`, where it stands on the aisle and its review camera), `induction()` (the `[induction]` stops with a point each and the legs in order, the way back as `-A2`), `induction_graph()` (IND-001 5.1: the rig's `induction_route`, with the rail, stops, sequence, legs, ladders and openings under semantic IDs; a waypoint's zone is that of the segment ending there), `induction_sequence()` (IND-001 4.1: `[induction].sequence` checked against the configurations and the stop order, each stop's operating state, ring rate and spin gravity; stops off the ring need the rings stopped), `induction_figures()` (the induction sectors' review figures in the vehicle frame) and `route_bodies()` (the suited body sampled along it: two chords of the route while floating, upright on the deck; a stop walk's zone is the stop's key). `check()` screens the clear passage to the trunk, the hull gap, both leaf swings, fixture intrusions, neighbours (crew-transfer obstacles, keels, ties), the trunk fixtures against the branch openings, each vestibule chamber and its fixtures against its spine port's passage, the suited envelope through each port and around each annulus, each crew tube's fixtures against its bore, its hatch panel's reach and the suited envelope swept along its axis (ring B: and through its neck), the landing's leaf sweep, well, fixtures and every function's blocks, the suited envelope down the hatch axis and across to the aisle, the refuge port against the suited envelope, the refuge fixtures inside the cavity's walls and out of the port, the occupant stations (inside the cavity, clear of each other and of every fixture but their own anchor rail) and the circulation annulus, the emergency route (the refuge port rails within reach of crew beside the rim, the distance, rungs and time at the review pace from each sector's aisle to the refuge, and the spin-transfer speeds at each spine port), the thrust review (`trunk.thrust`: the ladder from the floor, the rung at each branch sill it passes, the near stile's gap to each mouth and the rail's distance from it, falls from each step-off at the LOW_THRUST limit and the First Ignition peak, and per sector the drop to the spine port, the trunk climb and the legs steeper than `steep_leg_deg` with aft down), the induction legs' lengths and rungs and each sector stop's station and way to the refuge (`induction`), and all nine mannequins' fit and reach; each spoke row carries its `ladder_push` and `arrest_rail` (length, clip-on gravity, the drop to the deck where crew unclip). The climber's fixture gap also measures body samples against each fixture's exact solid, since a long rod's surface samples are metres apart.
- `layout.spine_core()` / `spine_radius_at()` (HUM-001 zones 2–3): the forward spine core (`prototype.spine_core_*`, r 0.95 m from just aft of the ring-A vestibule to the forward end, a cone to the aft `spine_radius_m`). The hubs, vestibules, trunk, refuge and storage obstacle use the core radius; the drive end keeps `spine_radius_m`.
- `common.cut()` applies EXACT boolean differences (or, with `operation='INTERSECT'`, intersections) of closed cylinders (`cylinder_mesh()`) to a generated mesh and deletes the temporary cutters; `revolve_mesh()` revolves a closed (t, rho) profile about any axis. Only the HUM-001 openings and trims use them.
- `sim_rig.py`: the rig anchor frames, the massless simulation proxies (`proxies()`: shapes posed in anchor frames, with realizations and motion) and the `simulations/wf_sim_rig.json` contract.
- `flight_timeline.py` (FUT-004): the First Ignition timeline. `phases()` expands `[flight_timeline.phases]` (induction entries from `[induction].sequence`) into frame spans; `rotor_segment()` and `drive_segment()` re-time the rotor and drive key tables; `track()` plays them phase by phase and checks each hold ends at its configuration's state; `channels()` adds the forward-defense, radiator, EYE, configuration and kinematics channels; `sample()` evaluates every channel at a frame or mark; `bind_frames()` gives every channel its authority (presentation / sheet-import), adds the `frames.*` channels of `tools/frames_import.py` (no keys while UNKNOWN) and marks the presentation channels that stand for them; `validate()` (called by `spec.validate`) checks the structure and, at every frame, the rotor rules, locked rings under thrust and the 07!A39 radiator order; `control_values()` maps a sample onto the controls and `caption()` writes a mark's preview header. FUT-005: `sim_rig.flight_timeline_contract()` (rig section, contract 19) and `inspect.timeline_checks()` (every mark on the saved vehicle).

All of these are imported by both system Python and Blender's Python 3.13, so they must stay standard-library only.

**One vehicle, configuration presets.**
- `[vehicle]` names the one saved vehicle file (`WF_WAYFARER_001`) and its `saved_preset` (COAST). The geometry is the same in every operating state: rings never retract, radiators are fixed (R1/R8), and there are no rotor-bay doors (H3).
- `[configuration.*]` entries are the owner's operating tuples (`11_OPERATING_CONFIGS`), used as presets on that file. Each carries:
  - drive OFF/ACTIVE with `max_accel_g`;
  - habitat state ROTATING or STOPPED_LOCKED;
  - radiators `FIXED`;
  - `controls` (`ring_spin`, `ring_lock`) for the rotor controls;
  - `thermal_load` and `eye_mode`.
- An unbuildable configuration names its `known = false` inputs (DAMAGED).
- A rotating habitat with an active drive must stay at or below `habitat.low_thrust_limit` (0.1 g); above it the rings are STOPPED_LOCKED (`08!A47`, MEC-011).
- Never add a vehicle file per state. Scripts pose a preset in memory with `common.pose_configuration(s, name)` (rotor controls, then the drive display); never save a posed vehicle.
- Retired generated files are listed in `RETIRED` in `build/build.py`. A full build moves each one to its folder's `milestones/<stem>_RETIRED_<UTC>.blend` after checking that it holds no `ART_*` or unowned content; nothing is deleted.
- The drive is a state control the same way: `DRIVE_MANIFOLD_CTRL` in `WF_PROPULSION` holds normalized 0–1 properties (drive, seed field, lattice, lasers A/B, gates L1–L4, flux shares 1–4, nozzle field, plasma visibility). 60 simple-expression drivers read it, and it is saved NEUTRAL (drive off) with no animation data. Four of them (P1-006) set the end of each exhaust's display run from `thrust_level`, a configuration setting that the actions never key: the configuration's sourced `max_accel_g` ÷ the highest drive-ACTIVE limit (LOW_THRUST 0.067, the 1.5 g configurations 1.0), shown as a run of `exhaust_length_m × thrust_level^0.5`. It is saved at 1.0, so the saved geometry holds the full run; exhaust velocity and mass flow stay `known = false`. Six drivers hide the `DRIVE_DEBUG_*` instances unless `magnetic_field_debug`, `separatrix_debug` or `optical_debug` is ≥ 0.5. These drivers live inside WF_PROPULSION on purpose: an override of the propulsion assembly remaps them, but it would not remap a driver in the vehicle file. The flux shares are the commanded input; gates and lattice are display-only, with no invented coupling. Pose with `common.pose_drive_state(drive_manifold.configuration_state(s, name))`. The 12 `WF_*` actions are stored unassigned. Optical power, wavelength, response time, coupling and the throat field profile stay `known = false`. N1–N4 = `Nozzle_01–04` follow the owner map (+Y+Z, −Y+Z, +Y−Z, −Y−Z); `WF_FLUX_CHANNEL_FAIL` isolates one channel and derates its opposite, and the vector limits are rig data and preview cones only.

**Build layer (Blender).** `build/build.py` orchestrates the dependency chain:
0. Detail assets (`assets/wayfarer/detail/WF_DETAIL_<assembly>.blend`, one per detail-pack assembly, docs/MODULES.md), each linked into its
   host by `components/detail.attach()` at its anchor before the host is saved. A `DETAIL_<assembly>` target rebuilds only that file
   (several joined with `+`); a host target also rebuilds the details anchored on it. Committed authored meshes (`data/detail/<pack>/*.glb`)
   are imported into their detail asset here (`components/detail.import_authored`).
1. Components (`assets/wayfarer/components/WF_{NOZZLE,RADIATOR,RING_SECTOR,INTERIOR_HABITATION,INTERIOR_WORK,INTERIOR_GARDEN}.blend`). The interior components map to the pod functions through `interior.components`; the habitat recipe parents the matching one to each pod as `Interior_r_j` with an identity local transform.
2. Subsystems (`subsystems/WF_{STRUCTURE,HABITAT_A,HABITAT_B,HABITAT,STORAGE,SHIELDING,SERVICE,POWER_STORAGE,ROTOR_INTERFACE,CREW_TRANSFER,EYE,DEBUG_MAGNETICS,DEBUG_SEPARATRICES,DEBUG_OPTICS,PROPULSION,THERMAL,HULL}.blend`). The ring assets `HABITAT_A`/`HABITAT_B` are built first and linked by the habitat assembly `HABITAT`, not by the vehicle (as the `DEBUG_*` overlays are by `PROPULSION`).
   - The three DEBUG libraries are built before PROPULSION, which links them as `DRIVE_DEBUG_*` instances. Their hide flags are driven by the drive control's toggles, saved off. Vehicles never link them directly. `--target PROPULSION` rebuilds all three first, and a `DEBUG_*` target also rebuilds PROPULSION.
   - SERVICE holds the airlock, docking ports and refuge.
   - POWER_STORAGE (P1-007) holds the storage packs, their OPEN interfaces, the ride-through markers, `POWER_STORAGE_CTRL` and `WF_BLACK_START`.
   - ROTOR_INTERFACE (P1-008) holds the stationary hub segments, fluid cartridges, spokes and stationary `IF_HUBn_*` interfaces. The rotating drum/rings (parented to `Rotor_n`), the ring-stop locks, `ROTOR_n_MECH_CTRL` (saved at the COAST preset; `spin_fraction` drives the rotor rotation, or, with `spin_integrated` 1, the integrated `spin_turned` from `rotor_interface.spin_turned()`, FUT-007) and the `WF_RING_STOP_LOCK`/`WF_ROTOR_TOUCHDOWN` actions (one slot per rotor control) are built by the habitat recipe via `components/rotor.py`.
   - CREW_TRANSFER (P1-001) holds the stationary crew trunk, spine ports, connectors and their `IF_CREW_*` interfaces. The vestibules, struts and crew tubes with their `IF_VESTIBULE_*`/`IF_CREW_TUBE_*` interfaces are built by the habitat recipe via `components/crew.py`, parented to `Rotor_n`. The interior components carry `IF_POD_OVERHEAD_HATCH` (pod x −1.3).
   - HULL is linked last and only when `hull.enabled`.
3. The vehicle assembly `WF_WAYFARER_001.blend`: rotors animated at ±4 rpm over frames 1–361, saved at the COAST preset; other presets are posed in memory. It also gets the `WF_SIM_*` rig empties (`build/rig.py`), and the build rewrites `simulations/wf_sim_rig.json` and `simulations/wf_first_ignition_timeline.json`.

Higher levels reference lower ones as **linked collection instances with relative paths**. `components/recipes.py` builds NOZZLE, STORAGE, EYE and PROPULSION inline and delegates the pod, radiator, structure, habitat, shielding and thermal recipes to `components/revision.py` and the hull to `components/hull.py`. Recipe dimensions come from the TOML; only cosmetic member radii and small offsets remain literals. Scripts make modules importable by prepending `src/wayfarer`, `build/` and `components/` to `sys.path`. There is no installed package.

**Ownership contract (`build/common.py`), which is load-bearing:**
- `begin()` reopens an existing asset. It refuses when `scene['wf_asset']` doesn't match. It deletes only objects tagged `wf_owner = "wayfarer.p0"` that sit solely in `GEN_<asset>`. Any other object in `GEN_<asset>` moves to `ART_<asset>`. Nested collections in GEN abort the build.
- `tag()` stamps each generated object with `component_id`, `canon_status`, `geometry_status`, `source_ref` and `representation = REP_PROXY`.
- `save()` makes a timestamped backup to `milestones/` and keeps the newest three per asset (`*_RETIRED_*` files stay). It embeds `WF_SOURCE_SNAPSHOT` and `WF_PROVENANCE_SNAPSHOT` texts plus their SHA-256 hashes, and it rewrites direct library paths to relative.
- Because of these hashes, **any edit to either TOML makes every saved asset stale until a full rebuild**, and `inspect.py` asserts hash equality.

**Validation, presentation and studies:**
- `validation/inspect.py` reopens the production assets (never `studies/`, which get a separate summary). It checks hashes, unique IDs and relative links, and that subsystem interfaces pair (`IF_RAD_*_HULL*` meets `IF_SECTOR_*`). It also checks:
- the configuration metadata on `WF_ROOT`, the rig contract and anchor/interface coincidence;
- EYE facet quadrants against `eye.facet_map`, and pod floor direction (outward in coast, aft in burn);
- rough interiors: component blocks match `habitat_interior`, each pod carries exactly the interior of its function in its own frame, and at every sampled frame each deck follows its pod with "up" toward the spin axis in coast and +X when stowed;
- fixed radiators: the thermal file has no hinge, action or radiator articulation control: its only control is the display-only `RADIATOR_HEALTH_CTRL` and its only drivers are the overlay hide drivers; blade matrices are identical in every preset and control state; cells are checked against rotor-sweep and hull contacts;
- the hull envelope, and the BVH intersection test of hull, service fittings, refuge, P1-007 storage packs and P1-008 rotor mechanisms (spokes may touch their cartridge) and P1-001 crew parts (designed contacts listed below) against all geometry;
- P1-007 power storage: pack vertices and interfaces match `power_storage`, OPEN flags on tie/charge/feed/isolator/ride-through interfaces, ride-through markers coincide with their load interfaces, the control is saved at step 0 and `WF_BLACK_START` matches the key table (CONSTANT);
- P1-008 rotor interface: stationary vertices and spoke/lock endpoints match `rotor_interface`, rotating parts sit in the rotor frame with identity local transforms, OPEN flags on `IF_HUB*`/`IF_RING_STOP_LOCK_*`, `IF_HUBn_POWER_FEED` meets the ride-through and rotor-transfer interfaces, controls are saved at the COAST preset, and both actions match the per-slot key tables;
- P1-001 crew transfer: stationary curves and interfaces match `crew_transfer` (HUM-001 hollow parts are meshes inside their outer radius with no vertex left inside their `bores()` cutters or outside their `trims()`; the trunk and refuge fixtures match `human_entry.trunk_fixtures` and `refuge_fixtures`), rotating parts sit in the rotor frame with identity transforms (each hollow vestibule stays inside its ring envelope with an empty transit cavity, the hollow crew tubes are mitered shells with every vertex between bore and outer wall (on ring B, below the bulkhead, between the neck's bore and wall), each ring's inner hoop is open along each tube (ray casts), and the vestibule and spoke fixtures match `human_entry.ring_fixtures` and ride on their rotors; zone 5: the sector skin keeps the envelope's extent, its volume is the envelope less the cavity and the hatch opening, rays pass the opening and the overhead panel's hole, and `WF_RING_SECTOR` holds exactly the landing fixtures), tubes (coast) and collars (burn) end on their pod's hatch at frame 1, OPEN flags on `IF_CREW_*`/`IF_VESTIBULE_*`/`IF_POD_END_HATCH`, and stationary crew interfaces pair by name. Crew trunk, passages and vestibules join the BVH set; designed contacts (passages into the trunk, vestibule, fittings, refuge and pod hatches, trunk in the spine, struts on the vestibule, spoke brackets on the tubes, HUM-001 fixtures on their shells, the trunk, the vestibule, the tubes and the refuge, the refuge's inner wall on its shell and around its port) are skipped symmetrically;
- the rotor animation;
- the HUM-001 route sweep (`route_sweep()`): the suited body of `human_entry.route_bodies` every 0.1 m along the boarding route to each sector of both rings and into the refuge from the dock and from the spine ports (route `E`), against every evaluated surface (mannequins and the standing deck left out), DOCKED with the entry leaves opened in memory; the least margin per sector and zone goes to `human_entry.route_sweep` in the report;
- the drive manifold: hierarchy, the neutral saved control, every driver expression and target against `drive_manifold.drivers()`, every action fcurve against the key tables, debug layers hidden when saved (each toggle shows exactly its own layer), and each configuration and action key posed through the linked drivers (mismatch < 1e-5), with a hull-contact check at the widest pose.
- `presentation/preview.py` defaults to Workbench previews in memory and never saves cameras or lights into the assets. It poses each preset in memory with `common.pose_configuration`.
- `presentation/drive_preview.py` renders the drive review targets from the vehicle file at the HIGH_POWER preset (`--state`). In memory it hides the hull, habitat, thermal and EYE, and replaces the envelopes and the `WF_STRUCTURE` cage with translucent copies. It uses no section cut, because a cut opens tubes into black interiors. The engineering mode switches the debug toggles on. It saves nothing.
- `presentation/hero_preview.py` poses the vehicle at FIRST_IGNITION and applies `[look.exterior]` in memory. Display layers are hidden, and the materials on hidden kinds go transparent, because the glow steps are shown by hide drivers. Every material copy turns proxy grey, the hot-face cells emit at `look.exterior`'s strength and the drive plasma casts no light. One sun and AgX render it. It saves nothing.
- `presentation/interior_preview.py` links one pod shell and one interior component into an empty scene, hides the pressure envelope and overhead in memory, and renders plan, section and cutaway views. It saves nothing.
- **Shots (FUT-002)** follow the rule that a shot references Wayfarer and never becomes it:
  - `representation.py` (pure, stdlib) holds the representation registry, identity keys, selectors, explode vectors and operation key tables, plus `shots/shots.toml` validation. Identity is the instance path plus `component_id`, because components are reused.
  - M5 options: `subsystems = "m5_subsystems.toml"` classifies every item (overlay colour, `subsystem` property) and enables `subsystem:Sxx` selectors in ops and labels; `camera.fit = [selectors]` fits the camera to those items only (the isolated `SH_M5_HOLO_Sxx` holograms).
  - `shots/shot_tools.py` links sources relatively and builds shot-local representation objects (`STD_`/`HOLO_`/`CUT_`) whose data is the linked source mesh or curve. Materials are object-level slots reading per-object `wf_alpha`/`wf_highlight`/`wf_color`/`wf_cut`/`wf_cap`, and explode goes through driven group empties and `SHOT_CTRL['explode']`.
  - `shots/build_shots.py` regenerates `shots/SH_*.blend` wholesale and refuses a non-generated file. Never put shot data in the assets or in `data/`.
  - IND-001 4.2 options (`SH_INDUCTION`): a source `library` (`characters` links `assets/characters/`); `cuts` instead of a fitted `camera` (shot-local copies of saved source cameras, or an induction stop's view with `camera = "stop"` (`characters.stop_views`), bound to timeline markers, each captioned from `[induction]` while it is live); `materials = "source"` (the linked materials, so lit fixtures glow, and no bevel; conceal and reveal then only hide); `controls` (display control values posed in memory with the drivers that read only them, e.g. the entry hatches open; `world()` composes the driven basis).
  - `shots/build_flight.py` (FUT-006) is not in `shots.toml`: it overrides the linked vehicle instead of rebuilding representation objects, because the timeline animates the vehicle's own controls and drivers. Create the override from the linked collection (`override_hierarchy_create(..., reference=instance, do_fully_editable=True)`), then override each `Assembly_*` instance's collection the same way and set the overridden instance's `instance_collection` to it, or the nested overrides are lost on reload. Blender 5 geometry-nodes modifier inputs are `modifiers["X"].properties.inputs.<Socket>.value`, keyable at that path.
  - Blender gotchas found there:
    - Linked objects outside a scene are not evaluated, so compose world matrices from `matrix_basis` and parents and read extents from the data; stored `matrix_world` and `bound_box` can be stale.
    - `hide_viewport` objects are not evaluated either.
    - Blender 5 ignores the new-key interpolation preference, so set `keyframe_points[].interpolation`.
    - Simple driver expressions accept `pow()` but not `**`.
- `studies/` holds reproducible trade studies. Wayfarer 001 radiators are fixed (R1/R8); the former Miura folding study was removed in FGR-001 and its history is in Git and `references/MIURA_STUDY_REVIEW.md`.
- The generated JSON reports live in `references/` (current evidence files are `p1_*.json`), alongside the review markdown, the current geometry baseline (`references/baselines.json` names it) and, on a maintainer's machine only, the Drive captures. Captures and review notes are ignored by Git and never published; tests carry their own synthetic fixtures. `drive_capture_*/` hold full Drive workbook exports (`.xlsx` plus greppable `.txt` dumps and a manifest) or bounded range reads (`ranges.json`), which the source records cite as `capture`.

**Conventions:**
- Units are metres, with +X bow, −X aft, +Z dorsal and +Y left looking forward (owner axis contract, BASELINE). `WF_ROOT` sits at the origin.
- EYE facets `EYE_Facet_01–04` are owner facets F1–F4: +Y+Z, −Y+Z, +Y−Z, −Y−Z (`eye.facet_map`, BASELINE). Nozzles, tanks and ring pickups keep their own order.
- Ring node 0 lies on +Y and increases toward +Z around +X. Nozzle pickups are nodes 0/3/6/9, and sector pickups are 1/5/9.
- Interfaces are empties named `IF_*`. Anything whose mechanism is undesigned carries `engineering_status = "OPEN ..."`; inspect enforces this for rotor-transfer, hull-opening, rotor-bay (including doors), airlock, docking-port, refuge, radiator-hinge, coolant-joint, pod overhead-hatch, convergence-throat, optical-entry, optical-window and laser interfaces.
- Rig anchors are `WF_SIM_*` empties whose local +X is the axis and +Z is up. They carry an `interface_refs` string and a `sim` IDProperty dict; never store `None` in it. The centre of mass is unknown, so no COM object may exist. The mass budget has masses and qualitative regions but no positions. Contract version 5 (v4 plus the `propulsion.drive_manifold` section):
- has 27 anchors (contract version 6 added the four P1-007 storage anchors and the `power` section; version 7 adds the P1-008 `rotor_interface` section and version 8 the P1-001 `crew_transfer` section, both without new anchors); version 9 (FGR-001) replaced the radiator hinge anchors with fixed `WF_SIM_RADIATOR_0n_ROOT` anchors at the blade roots, and version 10 (FGR-002) replaced realizations with the one vehicle and its configuration presets;
- has massless proxies `WF_SIMPROXY_*` (`build/rig.py`) parented to their anchors, saved with `hide_viewport` and `hide_render` so no preview, visibility or geometry check sees them. Radiator proxies are static (motion FIXED). Inspect checks their shapes and that all rotating geometry lies inside the body and sweep proxies. Never give a proxy mass, density or a COM;
- keeps `flight_thrust` (16.18 MN) separate from `structural_design_load` (29.42 MN); never use the latter as flight thrust;
- exposes the budget, EYE loads, drive-heat calibration and low-thrust tilt without deriving a COM.

`studies/mass_proposal.py` is a PROTOTYPE proposal for the owner (15_MODEL_INTERFACES S1) and must not feed the spec.


## Production layer (M7)

The asset standard for L4 production detail (S&E 48!A23). The owner accepted it on 2026-10-20 (M7, `L4_VISUAL_ACCEPTED`) as the
standard for later sections. A new section follows the same steps, and its elements start as `L4_VISUAL_CANDIDATE`:
- an off-switch with an empty geometry diff;
- value steps from `[production.materials]`;
- clearance screens, before/after stills (`m7_section.py` modes), a measured Godot view and an owner review.

- **Geometry:** every assembly is a detail pack (docs/MODULES.md): its manifest `data/detail/<pack>.toml` with `[params]`, its builders
  and screen in `src/wayfarer/detail/pack_<pack>.py` (`@pd.builder('<ID>')`, `pd.CHECKS`) building closed meshes from the engineering
  pure modules, and its own linked asset. `src/wayfarer/production_detail.py` is the shared core (registration, helpers, scopes,
  `standard()`); the shared tables stay in `[production]`, `[production.entry]` (the M7 panel grammar) and `[production.m8]`.
- **Objects:** `components/production.py` joins one family per assembly into one object (`Prod_<assembly>_<family>`), so
  the runtime gets a few batched meshes. A family with a bevel width gets an angle-limited chamfer, which the export
  evaluates.
- **Materials:** `[production.materials]` holds glTF-safe Principled values (`WF_MAT_Prod_<key>`). The saved asset and the
  runtime get the same finish.
- **Metadata:** objects carry `kind = production_detail`, `layer = PRODUCTION`, `representation = REP_HERO`,
  `m7_assembly`, `maturity`, `surface_class` and `source_ref = l4_production_gate`. The runtime manifest (contract v2) repeats
  them per node and adds a `production` block.
- **Colliders:** colliders stay the rig's slabs from engineering data. No physics comes from production meshes.
- **Gate:** with `[production].enabled = false`, `pipeline --quick --expect Prod_` must give an empty geometry diff. With it
  enabled, only `Prod_` objects may appear. `python3 src/wayfarer/production_detail.py` prints element counts and the
  clearance screens. `tests/test_production.py` keeps every assembly outside the route clearances.
- **Performance:** run `profile_views.gd --view=demo_entry|demo_spine|demo_ring|exterior`, three runs per view, on the same
  machine before and after. The baseline is `references/M7_PERF_2026-10-19.md`.
- **Scopes (M8):** `production_detail.scope()` returns the table that switches and labels an assembly, as its pack's `scope` names it:
  `[production]` (M7), `[production.m8]` (M8), each with its own `enabled` and `maturity`, or the pack's own `[pack]`. The manifest's `production.assemblies`
  gives every built assembly its scope and maturity, and `check_export.gd` fails a node whose maturity differs from its assembly's.
  Demonstrator 01's INSPECT flips the M7 section only. Exterior families carry `detail_range_m` (Godot `visibility_range_end`).
- **Exterior gates (M8):** an off-diff; `pipeline --quick --expect Prod_ --inspect forward hull`; the pure screens; then
  `/snap/bin/blender -b --python src/wayfarer/validation/m8_readback.py -- --out <run>/m8_readback.json` (tags, BVH clashes against
  every forward engineering mesh, largest radius, nothing ahead of the skin's aft face; it reads the forward assets and the detail assets
  linked into them). A repeated module (the Crown sector) is gated
  on one instance first (`[production.m8].crown_sectors`). Stills: `presentation/m8_exterior.py -- [--mode xray]`.

## Godot runtime inspector

**Review menu (U01).** `godot/scenes/review.tscn` is the project's start scene: it lists the review sessions (number key or
click; Esc quits). A guided session opens its scene with the development review guide (`godot/scripts/review/`):
`WfReviewGuide` draws a step card with the checklist, the keys that work now as chips (blue available, amber the key that
moves the step on, grey leave), an Expect line, a Last line with the result or the reason a key was refused, and the scene's
engineering text muted on one line (I expands it, F1 hides the guide). A scene's session subclasses `WfReviewSession` and
answers every step from the scene's real state and names the source status of what it shows (`labels()`, outlined badges);
the guide changes no ship, physics or route state. Every menu entry is guided (`--review=<key>`): Ring B body mode and the induction walk (`ring_b_session.gd`,
`walk_session.gd`, boarding), the ring A vestibule drill (`vestibule_session.gd`, physics lab), EVA drift (`eva_session.gd`),
Demonstrator 01 (`demo_session.gd`, Tab expands), the inspector (`inspector_session.gd`) and the First Ignition timeline
(`flight_session.gd`). The inspector's
"Review sessions (guided)" button returns to the menu; Esc in a guided session does too.

```bash
/snap/bin/godot-4 --path godot                                                                  # the review menu
/snap/bin/godot-4 --path godot res://scenes/boarding.tscn -- --review=ring_b                     # one session directly
timeout -s KILL 300 /snap/bin/godot-4 --headless --fixed-fps 60 --path godot res://scenes/physics_lab.tscn --quit-after 9000 -- --review=vestibule --check-review
timeout -s KILL 300 /snap/bin/godot-4 --headless --fixed-fps 60 --path godot res://scenes/boarding.tscn --quit-after 6000 -- --check-review   # WF_GODOT_REVIEW
/snap/bin/godot-4 --fixed-fps 60 --path godot res://scenes/boarding.tscn -- --review-shots=/abs/dir --check-review   # a still per completed step
/snap/bin/godot-4 --path godot -- --capture-menu=/abs/menu.png                                   # a still of the menu
/snap/bin/godot-4 --path godot res://scenes/m5_holo.tscn -- --review=holo                         # M5 subsystem hologram, guided (menu 8)
timeout -s KILL 300 /snap/bin/godot-4 --headless --path godot res://scenes/m5_holo.tscn --quit-after 600 -- --check-holo   # WF_GODOT_HOLO
/snap/bin/godot-4 --path godot --resolution 1600x900 res://scenes/m5_holo.tscn -- --capture=/abs/dir   # overview + four chapter stills
```

**Controls (ACI).** `WfInput` (autoload) holds the action registry (`BASE_ACTIONS` plus the compact per-scene `SCENE_ACTIONS`
table), the profile `user://wayfarer_controls.cfg` and the overlay (`controls/control_overlay.gd`: first launch, capture/validate,
conflict choice, lesson cards, Control Codex). A modal overlay pauses the tree. A scene sets `WfInput.context` in `_ready`, gates
its handler with `WfInput.pressed(e)` and matches `WfInput.key_of(e, [its contexts])`, the default key of the action the input
triggers (KEY_NONE for anything else, including a default key rebound away); Shift step multipliers read `WfInput.shifted(e)`.
Hold inputs read `WfInput.strength(id)` / `held(id)` so the toggle latch and stick settings apply. Help text uses
`WfInput.keys("{flight.play}: play")`. A scene reports success with `WfInput.performed(id)`, offers a lesson with
`WfInput.discover(lesson)` and sets `WfInput.hazard` when no prompt may appear (a context change clears it). The guide passes a
session the default key of the action (`WfInput.canonical_key`), so sessions written against default keys follow rebinds. A new key
in a scene is a new row in `SCENE_ACTIONS`; the `defaults_conflict_free` check fails if it clashes. Delete the profile to see first
launch again.

```bash
rm -f ~/snap/godot-4/current/.local/share/godot/app_userdata/"Wayfarer Inspector"/wayfarer_controls.cfg    # first launch again (snap path)
timeout -s KILL 120 /snap/bin/godot-4 --headless --path godot --quit-after 600 -- --check-controls      # WF_GODOT_CONTROLS (61 checks)
timeout -s KILL 300 /snap/bin/godot-4 --headless --fixed-fps 60 --path godot res://scenes/boarding.tscn --quit-after 3000 -- --check-controls-body   # WF_GODOT_CONTROLS_BODY
timeout -s KILL 600 /snap/bin/godot-4 --headless --fixed-fps 60 --path godot res://scenes/demo01.tscn --quit-after 30000 -- --check-touch --touch   # WF_GODOT_TOUCH (MOB-001 touch controls)
/snap/bin/godot-4 --path godot --resolution 1280x800 -- --capture-controls=/abs/dir                # stills: first launch, conflict, Codex, lesson card
/snap/bin/godot-4 --path godot --resolution 1280x800 res://scenes/boarding.tscn -- --review=walk --capture-lesson=/abs/walk.png   # the MOVE card beside the guide
```

The Godot project lives in `godot/`; it consumes a generated static COAST frame-1
snapshot. It does not generate spacecraft geometry or own physical parameters.
The current runtime is a subsystem inspector, without physics, moving mechanisms
or walking. Click a part or select a sidebar item to highlight its subsystem.
Double-click/F focuses it; H hides/shows it; I isolates/restores the previous
visibility state; Escape clears selection. The sidebar also has a hull toggle
and Show all. Focus makes a hidden selected subsystem visible. Choosing a
different subsystem exits isolation and restores the previous visibility state.

The wrapper resolves current mesh IDs through `manifest.nodes` and binds UI
behavior to the semantic `Assembly_*` lineage, independent of Blender/Godot
suffixes on imported group names. Picking uses cached `TriangleMesh` ray queries
in each mesh's local frame, only for visible meshes; no physics bodies are added.
Highlights are instance material overlays and do not edit imported materials.
Part labels show source and geometry status separately; a PROTOTYPE geometry
label is never promoted by a sourced reference. Subsystem summaries do not
invent a single engineering status for their mixed contents.
 `1`, `2`, `3` select side, top and three-quarter views;
Home resets the camera. Left-drag orbits, Shift-left-drag or middle-drag pans,
and the wheel zooms. A fresh checkout displays generation instructions until
its first export.

**Board Wayfarer** opens `godot/scenes/boarding.tscn`, the guided induction walk
(IND-001 phase 5). `boarding.gd` reads `induction_route` from the generated rig:
it interpolates the rail by the exported `rail_m` distances and converts
`(x,y,z)` to `(x,z,-y)` once. It uses the stops' `view` (eye, look, up and
horizontal field of view) when a stop is chosen, and each aisle waypoint's `up`.
It lists the legs' ladders and openings when the camera passes them. It shows
character nodes whose manifest `scene` is one of the current stop's scenes. The
panel text comes from the graph (titles, steps, sources, limits); the script holds
no stop names, lessons or spacecraft facts. W/S and the hold buttons move along
the rail at a review pace; the stop list sets the stop view; right-drag looks
around; R resets the view; Escape returns to the COAST inspector. F switches to
free flight from the current view (`enter_free_flight`/`fly`): WASD and Q/E move in
the camera frame at 1.5 m/s (Shift ×8), right-drag turns it, and any rail control
(`update_camera`) ends it. `move_free` keeps the camera within
`induction_route.envelope.radius_m` of the nearest rail segment (or within its
current distance, when a stop view starts farther out) by projecting the target back
onto that sphere, so it slides along the envelope; C toggles it.
`human_entry.induction_graph` writes the envelope (the suited envelope radius) and
`check_export.gd --docked` requires it.

RT-004 transfer: `mechanism_frames()` in the exporter turns each `Rotor_n` (its
control's `spin_turned`, one second at full speed) and then each `Drum_n`
(`drum_sync` 1) in memory, and records the instances that move. Each moved instance
must match a turn about the mover's pivot and axis. Node records get `frame` (the
rotor or drum `component_id`) in both packages; characters in the DOCKED package get
the frame of the nearest rail waypoint's zone. In DOCKED, `bind()` records each
closure's travel from the staged open pose as a slide or a turn about its own pivot
and axis, and checks it on every placement. The Q46 closures are closed by
`pose_transfer(s, 0)` and the primary port's leaves by `DOCK_ENTRY_CTRL`. The route's
sector leaves have no driver: each slides from `landing()`'s open pose to its seat,
carried by its sector's placement, and is the `Sector_Hatch_Leaf` nearest to the
opening. The closure's nodes get `closure`. The results go to `manifest_docked.json`
`induction.mechanisms`.

The rig's `induction_route` adds:
- `frames`: each zone as `STATIONARY`, `DRUM` or `RING`, plus ring A's rotor and drum;
- `closures` and `kind` on each opening (`AIRLOCK_OUTER`, `AIRLOCK_INNER`,
  `PORT_GATE`, `DRUM_DOOR_TUBE_HATCH`, `SECTOR_LEAF`);
- `toward_ladder` on each crew-tube ladder (the run's direction toward its ladder, at
  the index pose);
- `body`: review speed, rung pitch, standard gravity, the climber's offset, and ring
  A's `ladder_push` to check against.

`boarding.gd` reparents the meshes under one pivot per ring and drum and one child
pivot per closure. It carries the camera in a holder parented to its zone's frame.
`step_mechanisms()` advances everything each step:
- `step_rings()` ramps each ring STOPPED → SPIN_UP → RUNNING → WAIT_DOWN →
  SPIN_DOWN, depending on whether the stop ahead is ROTATING;
- the drum steps through DESPUN → WAIT_UP → SPIN_UP → SYNCED → WAIT_DOWN →
  SPIN_DOWN;
- each closure moves toward its target.

A ramp starts when the angle plus half the ramp's turn passes a whole revolution, so
it ends at the index or meets the tubes at speed. `safe()` holds the rule a closure
may never break, and `allowed()` adds the sequence. `move_along()` stops the camera
short of a closure that is not fully open, and `settle()` sets the steady state after
a jump. `body_state()` turns the frame's measured spin and the camera's velocity into
spin gravity, the Coriolis push and their components toward the ladder.
`shown_progress()` eases the eye from rung to rung in body pace.

`-- --check-transfer` (headless, in `runtime-export`) walks the rail both ways, waits
for the rings to rest, checks the body line against `ladder_push`, checks every
exported clear volume (its centre held, no step out through its deck or walls, the
body's eye at eye height in a standing one), and fails on any breach. `-- --capture-transfer=/absolute/path` saves seven stills: the airlock, the
drum cycle, body pace on the ladder and the sector leaf. `flight.gd` also binds the
rings by `frame`, so the sector shells and interiors turn in the timeline player.

RT-005: `export/godot.py` shares one mesh between placements whose evaluated meshes are equal (`mesh_signature`: positions, faces,
corner normals, UV and colour layers, face materials and the runtime materials); each placement keeps its node, transform and record.
`WF_EXPORT_SHARE_MESHES=0` turns sharing off, for A/B measurement only. `godot/scripts/profile_views.gd` measures one view per run on the
current machine, windowed with vsync off: frame time median and p95, draw calls, objects, primitives, memory and load time.

```bash
/snap/bin/godot-4 --path godot --script res://scripts/profile_views.gd -- --view=exterior
```

Measured 2026-10-09 on an RTX 3070 (GL Compatibility, NVIDIA 595.91), five alternating runs per package per view
(references/RT005_PROFILE_2026-10-09.txt):

| View | Draw calls | Unshared median frame | Shared median frame | Change |
|---|---|---|---|---|
| Exterior inspector | 3,315 | 8.08 ms | 5.84 ms | −28 % |
| First Ignition player | 2,380 | 5.30 ms | 3.80 ms | −28 % |
| Boarding walk at the Garden stop | 239 | 1.61 ms | 1.66 ms | within noise |

- Sharing leaves 2,218 distinct meshes for 3,417 placements.
- The GLB shrinks from 13.7 to 10.5 MB, video memory falls about 2.8 MB and static memory about 7 MB.
- Draw calls are unchanged, and the three standard inspector views differ in 2–5 pixels.
- Batching or MultiMesh is not needed at these frame times.
- Single runs vary by up to 2 ms, so compare medians of several runs.

**Integrated Demonstrator 01** (`godot/scenes/demo01.tscn`, also a button in the boarding panel) is `boarding.gd` with
`demo_on_start`. `demo01.gd` runs the chapters EXTERIOR, ENTRY, MICROGRAVITY, MODE, TRANSFER, DESCENT and GRAVITY over the existing rail, the
body tour (`body_tour.gd`) and `WfModeController`.

TRANSFER and DESCENT are the body tour's TUBE beat (`build_tube(with_tool, access)`), one physics world in the drum frame at the index:
- `_build_access` builds the rig's `dynamics.stages.access` clear surfaces as slabs outside the free space (`_cyl_x` for the trunk and the
  drum walls with the port's and the door's holes cut by each slab's inboard face, `_radial_bore` for the port's and the door's bores,
  `_mitered` for the tube legs and the run, open into the landing well); the pieces across the holes are `port_patch` / `door_patch`,
  enabled while the gate / door is not fully open (`set_closures`);
- the rig rungs and the access grips are non-colliding grab anchors;
- the body follows one line (the rig's `line` poses, then the run down to the well's deck) by `line_s`, centre lerp and axis nlerp
  (`line_at`). `_step_ladder` takes S/W or autoplay at the review pace and brakes in whole steps (`_brake`) at the line's limits and
  before each pose to `line_vmax`, the speed at which the turn there changes the velocity by `LADDER_ACCEL` (0.5 m/s² PROTOTYPE) in a
  step. `line_limits()` stops the body at `s_port` until the port gate is fully open and at `s_hold` (the restraint pose) until the drum
  door is, and at `s_stop` (the TRANSFER chapter's end, the run top). Inside a coast (`coasts`, the rig's `coasts_s_m`) the speed is
  frozen and the hands are off; the push-off sets exactly the line's velocity, braking counts only the line outside the coasts
  (`_held_length`), and a stop is never inside one;
- `frame_fn` gives the drum's fraction of ring A's spin and its rate; `_apply_frame` sets the field's ω and α from it each step;
- each step's hand load, grips in reach, contacts, phase, drum fraction and field are logged in `hand_log`.

In TRANSFER the demonstrator maps the body's line parameter onto the rail (`access_rail`): 1:1 along the trunk up to the port band, to
the point `INSIDE_M` past the port at the restraint pose (the gate closes behind the whole body), the drum door band's edge while
restrained, then to the run top; `vestibule_sync` takes `restrained` from the body. While it runs, `step_rings()` takes the rings' speed fraction from the controller
(`demo.ring_frac()`), not from the stop. The drum and its closures go through a `WfVestibule`:
- `allowed()` asks `demo.vestibule_allows()`;
- the drum's WAIT_UP/WAIT_DOWN ramps start only when `demo.vestibule_sync()` is accepted;
- `demo.vestibule_follow()` mirrors the opening state and steps the vestibule's drum ramp with the display. The keys are: Enter for the next chapter, P to pause, A for autoplay, V for body view or first
person, O to mark an occupant not secured (MODE), plus the body-tour keys in the two body chapters.

```bash
/snap/bin/godot-4 --path godot res://scenes/demo01.tscn
/snap/bin/godot-4 --path godot res://scenes/demo01.tscn -- --autoplay
/snap/bin/godot-4 --headless --fixed-fps 60 --path godot res://scenes/demo01.tscn --quit-after 60000 -- --check-demo
/snap/bin/godot-4 --fixed-fps 30 --resolution 1280x800 --write-movie /abs/demo.avi --path godot res://scenes/demo01.tscn --quit-after 20000 -- --autoplay --record-exit
python3 tools/review_video.py runs/<recording> runs/<review>      # FFMPEG=<ffmpeg with libx264>: MP4 with chapter marks, highlight, contact sheet
```

- The interactive run is plain; `--autoplay` replays it by itself.
- `--check-demo` prints `WF_GODOT_DEMO` and is the `demo01` step of `runtime-export`. Every chapter must reach its goal, and every
  chapter keeps the transfer check's rail safety rules. It also requires:
  - the catch on a real trunk rail;
  - the owner step order and the rings RUNNING after MODE;
  - drum SYNCED, the ring frame and both vestibule sides opened through the gate with no refusal after TRANSFER; the run top reached,
    no wall contact on the access line, the body restrained for the whole drum ramp with the hands' load within 0.5 N of −m·a_field
    (a step behind), the field zero before the sync and ring A's after the door, a rail in reach in the restraint pose and at every
    step after it, and no hand load (≤ 1 N, a step behind) and no speed change in the coast;
  - `findings`: where the hands load the body with no grip within reach (measured, not a gate; empty while the body keeps the rig line);
  - after DESCENT: arrival standing, a rung in reach at every step, the body inside the bore, the hands' load toward the ladder
    within 3 % of `ladder_push`, and along the run within 5 N of m·ω²·r at steady pace;
  - standing at the floor field and the object landed after GRAVITY.
- `--write-movie` records the replay as MJPEG (about 181 s for the nine chapters). Keep the Godot window visible: hidden, Movie Maker
  runs at about a tenth of real time.
- `--record-exit` (with `--autoplay`) ends an automated recording once INSPECT has *completed*: a 1.5 s tail, then `WF_DEMO_RECORDING`
  and exit 0, so the file is finalized. A skipped chapter, a layer left off or the watchdog (`--record-timeout=<s>`, default 900
  display seconds) prints FAIL and exits 1. Each chapter start prints `WF_DEMO_CHAPTER <name> <s>`. Without the flag, play continues
  after the last chapter. `--from-chapter=<NAME>` starts at a later chapter; the `demo01-record` runtime check runs ARRIVAL → INSPECT
  this way.
- `--lamp-energy=<f>` scales every emitter lamp in the boarding scenes. The default is 0.65 (M7.1); 1.0 gives the manifest energy.

**Ship Navigator** (SNAV-001, docs/MODEL.md "Ship Navigator") is built into demo01. Its pieces:
- `data/ship_navigator.toml`, the registry;
- `src/wayfarer/ship_navigator.py`, which validates it and emits the rig's `navigator` block (sim_rig v33);
- `godot/scripts/navigator/`:
  - `ship_navigator.gd`: map world, marker, texts, card, input and checks;
  - `nav_route.gd`: the two-stage planner;
  - `nav_policy.gd`: the guidance modes.

`demo01.gd` creates the navigator unless `-- --no-navigator` is given, samples it at every check step, and appends its checks.

Keys:

| Key | Action |
| --- | --- |
| M | corner → overview → hidden |
| J | mode: GUIDED / ASSISTED / FREE |
| , / . | target stop |
| I | systems card: WHAT → WHY → SHOW ME → close |
| H | overview cutaway |
| U | isolate the next module |
| Click | overview: isolate the module under the pointer (empty space clears) |
| Left-drag / wheel / shift-drag | overview orbit / zoom / pan |

```bash
python3 src/wayfarer/ship_navigator.py
/snap/bin/godot-4 --path godot --resolution 1280x800 res://scenes/demo01.tscn -- --capture-demo=/abs/dir --navigator-stills
/snap/bin/godot-4 --path godot --resolution 1280x800 --script res://scripts/profile_views.gd -- --view=demo_spine
/snap/bin/godot-4 --path godot --resolution 1280x800 --script res://scripts/profile_views.gd -- --view=demo_ring --no-navigator
/snap/bin/godot-4 --path godot --resolution 1280x800 --script res://scripts/profile_views.gd -- --view=demo_ring --navigator-overview
```

- The first command is the fit screen: every hotspot's facts with their owner ranges, and the rail's nav nodes.
- `--navigator-stills` adds key-driven stills to the chapter capture. The keys go through `Input.parse_input_event`, and the run
  prints `WF_NAV_KEYS` with what each key and click did, including that P still reaches the demonstrator after a click.
- `--check-demo` adds these checks:
  - `nav_registry_bound`: every module frame is in the scene; every scene opening is in the registry; the rail nodes match the
    exported rail (a stale registry fails here); stops and nav nodes are complete.
  - `nav_route_gated`: 12 fixed cases (DOCKED locked, ring ramp, gate, door and sector hatch shut, the dock in COAST, the airlock, EVA
    for both actors, ring B), plus a sweep of 18,432 plans over stop pairs × mode × ring state × 48 closure sets. GO never crosses a
    closure that is not open; HOLD stops at the first such closure; a ramping ring never gives GO through the spine port; the dock is
    never GO outside DOCKED.
  - `nav_modes_parity`: the same target and state give the same route in all three modes; a policy returns guidance keys only.
  - `nav_no_fabricated_values`: for every hotspot, no digits in the WHAT / WHY / SHOW ME wording; every known fact has a value and
    an owner range; unknown facts read OPEN; every status has a glyph and a text.
  - `nav_pick_modules`: with each module isolated, clicks on its triangle centres select it and the card follows it; the radiator
    blade edges are picked with the whole ship shown; empty space selects nothing.
  - `nav_eva_remote_only`: the hatch label carries the exported FLIGHT_EVA state; no route reaches the exterior for any mode and
    actor (suited from SP12); no stop sits on an EVA node; the exported hatch lies within 1.5 m of the map's hull.
  - `nav_drone_demo` (DRONE-001): the drones hotspot's SHOW ME draws every vehicle-frame dock; the spine crawler's service run and
    three fault replays stay on the DS-13 track and end in a safe state; HIGH_POWER keeps it latched; FREE jogging stops at the track
    ends; closing restores the ship state and route. Keys on that page: X run, K what-if configuration, Z / Y play, step or jog by mode,
    C route overlay.
  - `nav_drone_routes` (DGT-009): C steps OFF, ALL, each EVA class and the arms, back to OFF; the overlay shows exactly the selected classes
    (routed legs, job targets by status, dashed reach lines); every drawn reach line equals the contract's `reach_needed_m` to 5 cm; the
    card names DGT-009 HOLD and reach OPEN; closing hides it and changes neither the ship state nor the route.
  - `nav_marker_matches_body`: the marker, through the map's copied frames, equals the tracked place in ship coordinates within
    1 mm at every check step.
  - `nav_frame_switch_continuous`: within a chapter the marker moves exactly as the visitor does, including TRANSFER's drum → ring
    hand-off.
  - `nav_ring_full_revolution`: one revolution of ring A with the body standing on the deck, through the phase wrap. The marker's
    ring-local place follows the body's ring-frame physics position within 1 mm, the sector stays the same, the per-step map motion
    is no more than 1.5 ω r dt, and the map's ring pivot equals the scene's.
- Measured costs are in docs/MODEL.md.
- `-- --capture-demo=/abs/dir` saves two stills per chapter.

**Space Navigator (SPACE Stage 1)** (`godot/scripts/navigator/space_navigator.gd`, S&E 55). B switches SHIP ↔ SPACE in demo01.

| Key (SPACE shown) | Action |
| --- | --- |
| B | back to SHIP (from SHIP: open SPACE) |
| , / . | previous / next released route row (Shift ×30); from LIVE, . previews row 1 |
| Home / End | LIVE / last released row |
| [ / ] | scale: LOCAL SPACE / MISSION JOURNEY / SOLAR SYSTEM |
| I | inspect ship: expanded SHIP map, the selected row kept |
| J | shared guidance mode |
| M (Solar System) | ANALYTICAL / PRESENTATION |
| - / = or wheel (Solar System) | zoom: inner planets / outer planets / Kuiper region |
| ↑ / ↓ or click (Solar System) | select Wayfarer, the Sun, a planet or the Kuiper region |
| I (Solar System) | card WHAT → WHY → SHOW ME → close (elsewhere: inspect ship) |
| 1–8 | layers (SPACE-021): track, motion, events, orbits, Kuiper guide, grid, notes, legend; the LAYERS line lists those of the scale |
| P (not Solar System) | replay the released rows at the route clock (30 rows/s); pause; from the last row, replay from row 1 |
| H (not Solar System) | MOTION card WHAT → WHY → HOW → close (POL-008 Prototype A) |
| R / Shift+R (Local space) | turn the ILLUSTRATIVE display hull 45° / remove it (attitude OPEN, SPACE-014) |

```bash
/snap/bin/godot-4 --path godot --resolution 1280x800 res://scenes/demo01.tscn -- --capture-demo=/abs/dir --space-stills
/snap/bin/godot-4 --path godot --resolution 1280x800 --script res://scripts/profile_views.gd -- --view=demo_ring --space
/snap/bin/godot-4 --path godot --resolution 1280x800 --script res://scripts/profile_views.gd -- --view=demo_ring --space-solar
```

- `--space-stills` drives the keys at the ENTRY and GRAVITY chapters and prints `WF_SPACE_KEYS`.
- `--check-demo` adds these checks:
  - `space_switch_ship_unchanged`: SHIP → SPACE, then every row on every scale (2,700 views), then back to SHIP. Host progress, camera,
    frames, ring angles and rates, openings, closures, drum mode, body, chapter, controller and ship-navigator state all stay identical.
  - `space_scrub_owner_rows`: every scrub position shows exactly one released row; the marker is at that row's AU.
  - `space_frame_units_source`: the frame, scenario, columns and sheet timestamp are as expected.
  - `space_never_sun_relative`: no view text reads as a Sun-relative place; DIAGNOSTIC 1D and UNKNOWN stay on screen.
  - `space_solar_unknown`: no body is drawn while 25!F14:F15 are OPEN.
  - `space_live_vs_preview`: LIVE without route values until a row is selected, then SCENARIO PREVIEW.
  - `space_no_invented_events`: only events with a released displacement are drawn; the four OPEN events are listed and unplaced.
  - `space_rejects_unvalidated_route`: a failed row 6, a missing row 9, another route version, another schema and a missing file are all refused.
  - `space_ship_drilldown`: Inspect ship and back, at the same row.
  - `space_solar_schematic_static`: across both modes, the three zooms and the LIVE state plus rows 1, 451 and 900, the glyphs do not
    move; there is no Wayfarer marker; the SCHEMATIC notice and the mode disclosure are always on.
  - `space_display_transform_reversible`: the LINEAR and SQRT distance transforms invert to 1e-9 for every body; the route rows are
    unchanged after the toggling.
  - `space_reference_cards`: one card for each of the 11 objects; every planet number and the reference title and dates appear; the
    Kuiper card reads "not an event position"; the Wayfarer card reads UNKNOWN.
  - `space_solar_picking`: a click on every glyph in both modes and all zooms selects that body; a click in the Kuiper band selects the
    region.
  - `space_layers_view_only`: on each scale at LIVE and rows 1, 451 and 900, every layer off and back on leaves the shown row, the
    badge and the readout identical; DIAGNOSTIC 1D and UNKNOWN stay, the OPEN events are still counted, the host state is unchanged and
    a hidden Kuiper guide cannot be clicked.
  - `space_replay_owner_rows`: P from LIVE plays every row once, in order, each shown value a released row, stops on row 900 after 30 s
    of replay, the HOW card there reads "not a shutdown"; host and ship-navigator state unchanged.
  - `space_motion_card`: HALFWAY_IN_TIME is 1/4 of the speed and 1/8 of the distance; the rows' acceleration integrated reproduces every
    row within 1e-6; the card pages at LIVE and rows 1, 451, 900 change no row, badge or readout.
  - `space_attitude_independent`: the display hull in 45° steps at rows 1, 451, 900 leaves the row, marker, velocity arrow and readout;
    the ILLUSTRATIVE / attitude OPEN label shows.
- `python3 src/wayfarer/space_navigator.py` prints the chart registry with the derived AU (its fit screen).

**Thermal explorer** (flight scene, key T; `thermal_explorer.gd`): ↑ ↓ pick heat input / surface case / blade temperature / area
in use / duration, `-` `=` change it, Backspace resets to the rig's values. `-- --check-thermal` prints `WF_GODOT_THERMAL` (runtime
step `flight-thermal`); `-- --capture-thermal=/abs/dir` saves four stills.

**Exterior looks** (flight scene, key X cycles: Phase 4 grammar (Y155 baseline), grammar with the wear layer, FUT-003 proxy grey, off;
manifest `look.exterior.grammar`, `godot/shaders/p4_exterior.gdshader`). `-- --check-grammar` prints `WF_GODOT_GRAMMAR` (runtime step
`flight-grammar`); `-- --capture-p4=<p4_review.json>,<dir>` renders the Blender review cameras of a `presentation/p4_review.py` run in
the runtime (needs a display: `xvfb-run -a -s "-screen 0 1600x900x24" godot --path godot --rendering-driver opengl3 --resolution
1600x900 res://scenes/flight.tscn -- --capture-p4=...`). Blender side: `p4_review.py ... [--wear]`.

**Phase 4 runtime cost:** `godot-4 --path godot --script res://scripts/profile_views.gd -- --view=exterior|flight [--hide-assemblies=RA.EXT,RB.,SP.]
[--look=0|1|2|3]` measures a view with or without the named production assemblies and in a given exterior look (same machine only).

**Phase 4 stills:** `/snap/bin/blender -b --python src/wayfarer/presentation/p4_review.py -- --out runs/<x> [--look grammar|hero]
[--views ...] [--pair] [--wear]` (matched review cameras; `--pairs <before> <after> <out>` with system Python for sheets) and
`/snap/bin/blender -b --python src/wayfarer/presentation/p4_hero.py -- --out runs/<x> [--shots ...] [--size 1920] [--samples 64]` (S10
hero set).

**Life support** (`godot/scenes/life_support.tscn`, Milestone C): ↑ ↓ row, `-` `=` change, Backspace owner defaults, `,` `.` day (Shift
×30), P play, Home / End, Esc to the review menu. `python3 src/wayfarer/life_support.py` prints the 41 results and the scenario ends;
`--out DIR` writes `wf_life_support.json` (a `runtime-export` step). `-- --check-life-support` prints `WF_GODOT_LIFE_SUPPORT`
(runtime step `life-support`); `-- --capture-life-support=/abs/dir` saves three stills.

```bash
/snap/bin/godot-4 --path godot --resolution 1280x800 res://scenes/life_support.tscn
```

**First Ignition · timeline** opens `godot/scenes/flight.tscn` (RT-003). The COAST
export copies `simulations/wf_first_ignition_timeline.json` into the package after
checking it against the rig's `flight_timeline.sha256`, and records
`manifest.timeline.mechanisms`: per `Rotor_n` empty its lineage ID, pivot and axis
(runtime basis), the channel `rotor.spin_turned` and the driver's rate in radians
per unit (`rpm·2π/60/fps`); the export fails if the driver stops reading
`spin_turned`. `flight.gd` reparents the meshes whose `frame` is that rotor under one pivot
each and sets the turn from the channel; it samples every channel with the same
rule as `flight_timeline.value_at` and maps the radiator value to the rig's
`radiator_health.steps`. Space plays, arrows step (Shift ×24), the speed button
cycles ×0.25–×16, the lists jump to a phase or mark, Escape returns to the
inspector. `-- --capture=/absolute/path` saves one still per mark. `check_export.gd`
requires the timeline hash and a channel and meshes (by `frame`) for every binding, and the
scene is loaded headlessly in `runtime-export`.

**X** switches the timeline to the First Ignition exterior look (FUT-003 step 2):
`manifest.look.exterior` is `look.runtime_exterior` (the stills' `[look.exterior]`
in runtime axes). `flight.gd` replaces the fill lights and ambient light with one
shadowing sun, overrides every surface with one proxy grey except the drive's display
plasma, hides the stills' hidden kinds and the exhaust run, and sets AgX with the
stills' exposure. The `RadiatorA`/`RadiatorB` hot face emits while
`radiator.thermal_state` is FIRST_IGNITION's step. Godot's light energy carries
the π a Cycles sun divides by, so the sun's energy is the Cycles strength over π
and the emission keeps its Cycles strength, folded into the linear colour with a multiplier of 1
(Compatibility scales the sRGB colour by the multiplier before linearizing it; measured
2026-10-10 on Godot 4.7.2). `-- --exterior` starts with the look
on (combine it with `--capture`/`--capture-states`). `check_export.gd` requires the
record and finds the hot-face materials among the imported surfaces.

Display tracks (`display_tracks` in the exporter): every owned object with a
`hide_render`, object-alpha (`color[3]`) or `scale` driver whose variables all read
timeline-bound control properties is evaluated in Python with its own driver
expression (math, min, max) at the input channels' keys and at every frame of
their ramps. Objects whose result never changes stay in the static pass. The
others skip the static pass and are staged once, posed with `common.pose_timeline`
at the frame where they show fullest (largest opacity, then scale); this includes
the `plasma` and `optical_beam` kinds the static export leaves out. Each node record
then carries `display`: `opacity` and `scale_x/y/z` keys relative to that pose
(Blender local y and z are runtime local z and y), `static_opacity` for the
export's own pose (the inspector shows it), and the driver expressions and
channels. `flight.gd` sets visibility, `GeometryInstance3D.transparency` and a
local scale from the keys. The capture option saves a ring view and a side view
per mark.

Named states (`display_states`): every buildable configuration (control values from
`drive_manifold`, `forward_shield` and `radiator_health.configuration_state`, spin
fraction from `rotor_interface`), each forward-defence and radiator display pose on
its base configuration, and each drive action whose last key is neither nominal nor
neutral, on HIGH_POWER. They go to `manifest.timeline.states`. The same driver
evaluation gives every display record a `states` map (opacity and scale per state),
and an object that changes only between states is staged at the state where it shows
fullest (`staged_state`). `offset_states` handles the location drivers (the Crown
carriages and shutters): it poses Blender at each state and records the runtime
offset of every mesh below a location-driven object; a driver that also turns or
scales is refused. Those meshes stay in the static pass with `display.states.*.offset`.
`flight.gd` lists the states; selecting one applies its values and spins the rings
at the state's fraction. `-- --capture-states=/absolute/path` saves views 3, 5
(shield face) and 6 (nozzles) per state.

`runtime-export` also poses and exports `wayfarer_docked.glb` and
`manifest_docked.json` in the disposable build. Both packages share the rig and
input hashes. The DOCKED export appends the characters asset in memory: its nodes
form the `Characters` group, and their records carry `layer` and `scene`. The
DOCKED manifest's `induction` entry points to the rig's `induction_route` and
carries the transfer mechanisms. `check_export.gd --docked` requires that route,
its frames' ring and drum bindings with meshes, and a binding and meshes for every
closure it names. Both GLBs receive import, hash and
bounds checks. The boarding scene is loaded headlessly as well. Its
`-- --capture=/absolute/path` option saves the nine stop views and the rail
halfway along each leg, in addition to the inspector's three standard views;
`-- --inspection-light --capture=...` takes the same views without the S004 look.
The snap's `/tmp` is private, so capture into the repository (for example
`runs/`). Both manifests carry `look` (the materials it changed and the light
count), and each emitter's node record carries `light` (class, colour, energy,
range, emitter centre in the node frame); `check_export.gd` requires them.

```bash
python3 tools/workflow.py runtime-export
/snap/bin/godot-4 --editor --path godot
/snap/bin/godot-4 --path godot
```

Installed integration baseline: Blender 5.2.2 LTS and Godot 4.7.2 Mono. The viewer
uses GDScript and the Compatibility renderer, with no .NET dependency. Override
executables using `WAYFARER_BLENDER` and `WAYFARER_GODOT`.

`tools/runtime_export.py` holds the existing write lock, copies the parameters
into `runs/<stamp>-runtime/work`, and performs a fresh full Blender build there
using the current generators. Production assets and the tracked rig JSON are
never rewritten. Only generated geometry is included; manual ART content is
not part of this first export. This fresh build also prevents stale geometry
when generator code changes without a TOML change.

`runtime-export --eye-layout r24` (H03) publishes a labelled STUDY package
instead. It sets `forward_defense.eye_layout.selected` in the workspace copy of
the data only, so the project's TOML (r4 canon) and production assets stay
unchanged. It also adds whole-ship inspection of that build
(`validation.json` in the run) and records `study` in `build_identity.json`.
The review menu shows a STUDY row and every guide card shows the label.
`runtime-check` refuses a STUDY package; a plain `runtime-export` restores the
canonical one.

Retention: every run writes to git-ignored `runs/`. Nothing deletes runs
automatically: after a successful publish `runtime-export` reports how many run
directories `workflow.py prune` would propose, and the user approves deletions
(AGENTS.md loop step 6).

The published package carries `godot/generated/build_identity.json`: the hashes
of its inputs (`runtime_export.package_inputs`: non-study Python, the exporter,
every data TOML, the imported route, the EVA inputs, the character assets and
`godot/project.godot`), the Blender and Godot versions, the Git revision and the
checks it passed. `runtime-check` compares them with the current files before
running Godot checks in `godot/`; any difference reports STALE and nothing runs.
Godot scripts and scenes are not package inputs: the check runs the current ones.
`runtime_export.CHECKS` is the one list of Godot checks for both commands, with
the scene or script each runs (for `checks`/`runtime-check auto`) and its PASS
marker.

`src/wayfarer/export/godot.py` resolves evaluated curves, meshes and collection
instances into a temporary export scene. It preserves evaluated transforms and
groups by collection instancer, with one mesh per included object. Snapshot IDs
combine component identity, parent lineage and placement: repeatable for the
same geometry, but not permanent interaction IDs for moving parts. Reusable
mesh optimization and mechanism pivots remain later work.

The export omits cameras, mannequins, simulation cages, debug libraries,
magnetic fields, plasma and optical beams. Basic Principled materials transfer;
the existing object-alpha-driven emission/transparency is sampled into static
materials. Unsupported shader links fail explicitly. Display materials are
presentation choices, not physical measurements.

The output package in `godot/generated/` contains `wayfarer.glb`,
`wf_sim_rig.json`, `wf_first_ignition_timeline.json` and `manifest.json`. The manifest records source-code and input
hashes, Git revision/dirty state, Blender version, node provenance, exclusions,
triangle count, measured bounds and package checksums. Geometry uses metres and
Blender's glTF basis `(x,y,z) -> (x,z,-y)`: bow +X, dorsal +Y. The rig JSON retains
its canonical Blender coordinates and explicitly declares them; a future
runtime consumer must apply the same basis conversion once. Unknown physics
remains `known = false`.

Before publishing, Godot imports the staged package, loads the viewer headlessly,
and `check_export.gd` checks
package hashes, rig/input agreement, mesh identities and vertex bounds against
the Blender measurements (2 cm tolerance). The source hashes are rechecked
before publishing. A failed build/import/check retains the previous generated
package; a successful one moves that package to the run's `previous-generated`
folder and installs the new directory. It imports the published package into the local
Godot cache so the viewer can run immediately; a failed local import rolls back
the package. Logs stay in the run. The Godot editor
reimports changed assets on focus; authored wrapper scenes remain independent.

Git tracks the runtime project, scripts, scenes and script UID sidecars.
`godot/generated/` and `godot/.godot/` are ignored. Import settings currently use
the engine defaults; introduce explicit tracked settings when customizing them.
No generated file is edited manually. The existing Blender modeling loop and
baseline rules remain unchanged; runtime-only changes use this export/import
check, not a production geometry build.

For visual review (requires a display), after import:
`/snap/bin/godot-4 --path godot -- --capture=/absolute/output/directory`
saves the three standard views and exits. The headless integrity check is
`/snap/bin/godot-4 --headless --path godot --script res://scripts/check_export.gd`.
