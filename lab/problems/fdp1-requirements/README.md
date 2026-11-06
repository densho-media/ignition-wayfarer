# FDP-1 engineering requirements map

## V3 (2026-11-05): `FDP-1_Spatial_Systems_V3.blend`, the main file

V3 is a separate implementation built on V2. The V2, phase-2 and phase-1 files and their data are unchanged. V3 adds
exploration modes, two camera families and **P11, the high-velocity collision protection envelope** (UNRESOLVED).
FDP-1 physics and IGNITION canon are untouched; every protection-only value lives in `data/protection_inputs.json`
with its source and status.

### Open and navigate

- Open the file with Python auto-run allowed (or run the text `V3_controls.py` once). The sidebar (N) gets the tab **FDP-1 V3**.
- **Mode** (one switch, hides everything else): Clean ship · A Energy · B Thermal · C Mass & Thrust · D Mission ·
  P11 Protection · All layers · Technical board. *Detail labels* adds the small print; *Superseded* shows the old
  four-nozzle drive.
- **Cameras**: scrub the timeline (markers bind them). Each camera stores the mode it was framed for.
  - Spacecraft focus: `F1` overview, `F2` energy, `F3` thermal, `F4` mass & thrust, `F5` mission, `F6` forward
    shield, `F7` propulsion protection.
  - Full physical scale: `S1` the 7.15 km span from above, `S2` the wing shadow strip (radiator envelope), `S3` the
    whole-ship protection elevation, `S4` acceleration feedback. The radiators are never shrunk.
  - `X` the phase-1 technical board.

### Controls (sidebar, tab FDP-1 V3)

| panel | control | effect |
| --- | --- | --- |
| Propulsion scenario | acceleration, warm loop, scaling, presets 0.0069 g to 1.5 g | the V2 closure; the protection layer updates with it |
| P11 protection | arrival cone (presets 0°, 2.29° diagnostic, 5° prototype) | intersection of the shield shadows over the cone |
| | safety margin (presets 0, 8 m radiator, 15 m ring) | lowers every clearance by the margin |
| | uncertain band | clearances inside the band are drawn yellow |
| | shield: canon 90 m / sized to cover the engine / custom radius | the larger shield is a **ghost**; the canonical shield never changes |
| | assume areal density (kg/m², ASSUMPTION) | off by default: shield mass stays UNRESOLVED (OD-014); on, the added mass feeds the closure |
| | engine geometry: fixed / r ∝ P^1/3 / r ∝ P^1/2 | fixed by default; the laws are labelled hypothetical |
| Constraint status | per family PASS / FAIL / UNRESOLVED / ASSUMPTION | "mathematically closed" and "physically validated" are reported apart |

### P11: what is computed

- **Model.** Particles arrive from +X. A point is protected if, for every direction in the arrival cone, the ray traced
  forward hits the shield silhouette (r 45 m at x 260.55 m, the shield's aft plane). Clearance = distance inside the
  silhouette − L·tanθ − margin. Components are sampled on their surfaces; each sample carries projected area.
  Circle and polygon silhouettes are supported (`fdp1diag/protection.py`).
- **Classes.** CRITICAL (engine, loops, Fiji, feeds, tanks, structure, habitat), RADIATOR (assessed separately),
  SHIELD, NON_CRITICAL (service, ASSUMPTION), EXCLUDED (superseded drive). Exposure is reported, not called a failure:
  each part has its protrusion, exposed frontal area and status (COVERED, AT_BOUNDARY, PARTIAL, EXPOSED).
- **Only geometric coverage is computed.** Stopping, ejecta, penetration, radiation/shock transmission and survival
  probability are UNRESOLVED. A covered part is not a safe part.

### Build and check (from the repository root)

```
/snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_v3.py -- --render --shots --gltf --pct 50
python3 lab/problems/fdp1-requirements/check_v3.py --regen      # 128 checks: the 88 V2 checks + 40 P11 checks
```

Options: `--accel`, `--temp`, `--cone`, `--margin`, `--shield baseline|required|custom`, `--only F1,S3`, `--out DIR`,
`--no-board`. `--shots` adds the enlarged-shield, 2.29° cone and 1 g / 2,500 K renders. Renders go to `renders_v3/`
(not in Git). New files: `build_v3.py`, `check_v3.py`, `VALIDATION_V3.md`, `fdp1diag/protection.py`,
`fdp1diag/scenario_v3.py`, `fdp1diag/v3_layers.py`, `fdp1diag/v3_controls.py`, `data/protection_inputs.json`,
`data/requirements_p11.json`.

## V2 (2026-11-05): `FDP-1_Spatial_Systems_V2.blend`

Wayfarer with FDP-1 is the centrepiece, at 1 BU = 1 m (+X bow, +Z dorsal). Every number is drawn on the hardware that
makes, carries, absorbs or rejects it. The phase-2 file (`FDP-1_Spatial_Systems.blend`) and the phase-1 board stay as
they were; the board is also inside V2 as the hidden Layer B.

### Open and navigate

- **Cameras.** The timeline runs frames 1-8, one camera per frame. Scrub it, or press Numpad 0 for the active camera:
  01 main overview, 02 fusion energy, 03 thermal management, 04 thrust and mass, 05 acceleration comparison (baseline
  against target), 06 requirements and mission, 07 isometric, 08 the phase-1 technical board.
- **Layers (Outliner).**
  - `V2_00_PHYSICAL` holds the hardware, one child collection per system.
  - `V2_99_SUPERSEDED_FOUR_NOZZLE_DRIVE` is the four-nozzle drive that FDP-1 replaces. It is hidden.
  - `V2_10_BASELINE_INFO` holds today's numbers: fusion, jet and plume, radiation, waste heat, radiator rejection,
    driver loop, thrust and the mass budget.
  - `V2_19_EQUIVALENT_MASS_CUBE` holds the 20,760 t cube near the bow.
  - `V2_20_TARGET` holds the target ghosts.
  - `V2_21_TARGET_EQUIVALENT_AREA_SQUARE` is hidden by default.
  - `V2_30_REQUIREMENTS` has one child collection per problem, P01–P10. Solo one with Ctrl-click on its eye.
  - `V2_40_MISSION` shows the four burns. `V2_50_SCALE_KEY` explains the encodings.
- **Inspection.** Every object carries custom properties. Information objects have `layer = information`, `state`
  (baseline or target), `component`, `encoding`, `param_keys`, `req_ids` and the value (`value_W`, `value_N`,
  `mass_kg` or `area_m2`). Hardware has `layer = physical`, `group`, `function`, `status` (ENGINEERED, PLACEHOLDER or
  SUPERSEDED) and `source`.

### Controls (sidebar)

Press N in the 3D viewport and open the **FDP-1 V2** tab.

- **Acceleration** runs from 0.0069 to 1.5 g.
- **Warm loop** runs from 800 to 2,500 K, or tick "Record radiator temperatures". The hot loop stays at 1,800 K.
- **Scaling** offers two options:
  - baseline closure, with a ceiling of 0.0106 g;
  - the record's goal-1g variant, with a ceiling of 0.0112 g.
- **Presets** load the five test cases plus 1.5 g.
- **Live** rebuilds `V2_20_TARGET` on every change. Without Live, press Rebuild target.
- **Show/hide** toggles the baseline, the target, the equivalent-area square, the requirements and the superseded drive.

A status box shows CLOSES, BASELINE or INFEASIBLE, the ceiling, the loop gain and the flags. When no departure mass
closes, the ghosts are a lower bound at today's mass, and the scene says so. The panel needs Python auto-run. If
Blender blocked it, open the Text Editor, select `V2_controls.py` and press Run Script.

### Build and check (from the repository root)

```
python3 lab/problems/fdp1-requirements/check_v2.py [--regen]          # 88 checks, writes VALIDATION_V2.md
/snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_v2.py -- \
    [--accel 0.25 --temp 2000 --scaling baseline_closure] [--render] [--cases] [--gltf] [--pct 50] [--only 01,05] [--no-board]
python3 lab/problems/fdp1-requirements/export_geometry.py          # only when the Wayfarer baseline or the FDP-1 record changes
```

- `--render` writes `renders_v2/CAM_*.png`.
- `--cases` renders cameras 01 and 05 for the five test configurations.
- `--gltf` writes `renders_v2/web/fdp1_spatial_v2.glb` plus a JSON manifest. Custom properties travel as glTF extras.

### Interfaces

| file | role |
| --- | --- |
| `data/ship_geometry.json` | physical blockout. Every part has a name, group, function, shape, status and source. Written by `export_geometry.py` from the Wayfarer baseline fingerprint and the FDP-1 record's `geometry.py`, with the T-B bow shift |
| `data/scenario_inputs.json` | 31 closure inputs copied from the FDP-1 record, each with its `record_path` |
| `fdp1diag/scenario.py` | `Scenario().evaluate(accel_g, warm_T_K or None, scaling)` returns the five states: authoritative inputs, derived baseline, user target, hypothetical assumptions and feasibility (status, ceiling, loop gain, feedback passes, flags). Standard library only |
| `fdp1diag/v2_target.py` | turns an `evaluate` result into the target ghosts. The `ENC` encodings live here |
| `fdp1diag/v2kit.py` | mesh kit (bpy + math) |
| `fdp1diag/v2_controls.py` | the sidebar panel. It is embedded in the .blend with the three modules above and the inputs |
| `build_v2.py`, `check_v2.py`, `VALIDATION_V2.md` | generator, Blender-free validation, report |

Scenario values never reach the data files: the panel and `--accel`/`--temp` rebuild only `V2_20_TARGET`.
`check_v2.py` hashes the data files before and after.

---

## Phase 2 (2026-11-05): `FDP-1_Spatial_Systems.blend`

This file is a 3D model of the engineering problem:
- a fusion sphere with four energy branches;
- the ship as a mass block pushed by a 1.40 MN arrow;
- 1 g ghosts;
- radiators at true area;
- P01-P10 requirement satellites.

The phase-1 board below is inside it as the hidden Layer B. Read `VISUAL_GRAMMAR.md` for the encodings, islands, cameras and
interactivity notes. Build it from the repository root:

```
/snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_spatial.py -- --render [--out DIR] [--pct 40] [--only 01,05]
```

## Phase 1 board (now Layer B)

A Blender diagram of why FDP-1 (Fiji Drive Pulsed prototype 1) closes the four-burn 0.016 c round trip but cannot
approach 1 g. It maps the problems; it proposes no solution and changes no FDP-1 physics, canon or Wayfarer asset.

## Files

| file | what |
| --- | --- |
| `FDP-1_Spatial_Systems_V2.blend` | V2 (generated, not in Git; review copy in the shared folder) |
| `FDP-1_Engineering_Requirements.blend` | the diagram (generated, not in Git; review copy in the shared folder) |
| `build_spatial.py` | builds the spatial model (Layer A) plus the board (Layer B), cameras 01-10, optional `--render` |
| `VISUAL_GRAMMAR.md` | how the spatial model encodes the numbers; islands; cameras; future interactive viewer |
| `build_diagram.py` | builds the .blend from scratch in an empty file, optional `--render` of every camera |
| `data/fdp1_parameters.json` | 186 parameters: value, unit, source (record path), class, requirement IDs, note |
| `data/requirements.json` | P01-P10 problem register; braces in its text are filled from the parameters |
| `fdp1diag/model.py` | derived values (each with its formula) and 20 validation checks; standard library only |
| `fdp1diag/bkit.py` | the small Blender geometry kit (prisms, ribbons, arrows, tori, text, collections) |
| `check.py` | runs the checks without Blender, compares every parameter with the FDP-1 record, compares the owner brief's figures, writes `results/derived.json` and `REQUIREMENTS.md` |
| `REQUIREMENTS.md` | generated register linking each problem to its scene objects |
| `NOTES.md` | function, constraints, findings, inconsistencies, open questions |

## Open and navigate

Open the .blend: it starts on the overview camera with flat material colours, so it reads in the viewport without a
render.

- **Views.** Numpad 0 shows the active camera. The timeline runs frames 1-16, one camera per frame (markers bind
  them), so scrubbing steps through: 01 overview, 02 fusion energy, 03 mass/thrust/acceleration, 04 radiation and
  thermal, 05 requirements, 06 schematic, 07 mission, 08 legend, 09-15 single panels, 16 isometric 3D schematic.
- **Sections.** Outliner collections `00_REFERENCES_AND_LEGEND` … `08_CAMERAS_AND_LIGHTING`, each split into
  functional sub-collections with the Outliner colour of their function. The eye toggle hides a section; the
  radiator temperature examples are separate collections (`05.radiator example 800 K` … `2500 K`).
- **Inspection.** Objects carry custom properties (`req_ids`, `value_keys`, `classification`, `component`). The text
  datablocks `VALIDATION` and `README_FDP1_DIAGRAM` are in the Text Editor.

## Update

Edit a value in `data/fdp1_parameters.json` (or run `check.py --sync` after the FDP-1 record changes), then from the
repository root:

```
python3 lab/problems/fdp1-requirements/check.py
/snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_diagram.py -- --render --out <dir>
```

Every label, bar, graph and the requirements cards are recomputed. The build stops if any check fails (dimensions,
mass and energy conservation, F = m a = ṁ v_e, P_jet = ½ F v_e, the rocket equation per burn, radiator areas).
Changing an input such as departure mass without re-closing FDP-1 will (correctly) break the mass checks: the
record's outputs belong together.

## Colours and classes

Orange fusion, cyan directed exhaust, blue propellant, red waste heat, magenta radiation, grey mass and structure,
violet Fiji magnetics, yellow unresolved, green verified. Blender's Outliner has 8 colour tags and no cyan, so
exhaust collections share the blue tag. Glyphs mark how each number is known: filled square established, open
square calculated here, diamond assumed (FDP-1 model output, speculative tier), yellow dot unknown (TBD), triangle
proposed (none used).
