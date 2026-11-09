# T05 Stage B report: Vertex experimental Blender blockout

| | |
| --- | --- |
| Thread | T05, mechanical architecture and spacecraft geometry |
| Date | 2026-11-09 |
| Status | DONE (Stage B revision 1); waiting for owner direction |
| Base | `39d05c0` (Stage A) on `claude/project-thread-ctwplp` |
| Review file | `REVIEW_VERTEX_BLENDER.blend` (packed, opens on `COMPARE_SIDE_BY_SIDE`; not in Git), copy and renders in the project folder `review/vertex_blender_2026-11-09/` |
| Rebuild | `/snap/bin/blender -b --factory-startup --python-exit-code 1 --python work/vertex-blender/build_vertex.py -- [--render DIR]` (about 5 min with renders) |

NON-CANON research geometry. The canonical ship, its assets, generators, data, Drive and lore are unchanged. V4 is not claimed viable.

## 1. Modelled

- **Canonical ship (CANON_WAYFARER):** appended once from the built `WF_WAYFARER_001.blend` (made self-contained by
  `localise_ship.py`, a cache copy). A fingerprint of all 6,249 objects (transform, parent, visibility, mesh size) is identical
  before and after the build (`checks.json` canon_unchanged).
- **Working copies (V4, V0):** no copied geometry. They are new instance empties that link the canonical objects, leave out
  `Assembly_PROPULSION` and `Assembly_SHIELDING` (superseded drive), leave out the five H2 vessels for V4 (T-B tanks replace them),
  and split every subsystem at the farm front (X 137.9 m): 549 bow objects are instanced again 275.4 m forward (V4) or 122.4 m (V0).
- **V4 principal (802 tagged parts), V0 historical (408), V5 wire ghost (9),** each in `VAR_VERTEX_<g>_01..12` groups:
  reaction zone, nozzle, shield, drivers, thermal, power, fuel, structure, maintenance, dust protection, keep-out, diagnostics.
  - FDP-1 part list re-solved per generation (shield, module, galleries, drivers, pulse storage, cryoplant, T-B tanks, keep-outs).
  - Nozzle redrawn: 12 replaceable 30° segments per loop with cryostat, lattice band and armour shoe, trim joints clocked 45° loop to
    loop; closure coils C1/C2 (winding and envelope); guard rings 22.5 m forward of L2/L3; local bumpers outside r 45 m.
  - Coil load-path candidates (PROTOTYPE): C1 struts to a shield reaction ring; C2 ties to C1 or to the L1 struts.
  - Module: launcher barrel and sabot catcher, fast-ignitor line and its shield port, tritium store (all PROTOTYPE or illustration).
  - W2 wings at true scale (tip 10,128 m): 1,800 K root band, warm field split into the T01 circuit bands with manifolds, thermal
    break, two spars, ribs every 1 km, droplet generator and collector bars, root booms and struts.
  - Dust protection: skirt A (to r 45 m, with dock apertures), B (ends 10 m aft of ring A), C (none: guard rings and bumpers).
- **Alternatives (outlines, `VAR_VERTEX_V4_ALTERNATIVES`):** graded hot band, W3, tandem R2, panel skin, tip brackets at 3.4, 6.7 and
  14.5 km and the V5 bound.
- **Overlays:** stand-off spheres, injection path and the one target in flight, dust stream (braking), red conflict markers, labels and
  dimension callouts, 100 m and 1 km scale bars, two 1.75 m figures (shield-face rail, wing root).
- **Evidence tags:** every one of the 1,258 Vertex objects carries vtx_id, generation, evidence_status, representation, source,
  revision and `wf_owner = wayfarer.t05`; names start `<gen>_<ES|PP|PR|CI>_`. Counts: 349 ENGINEERING_SUPPORTED, 554
  PARAMETRIC_PLACEHOLDER, 91 PROTOTYPE, 264 CONCEPTUAL_ILLUSTRATION. Text blocks in the file: `VERTEX_PART_STATUS`, `VERTEX_CHECKS.json`,
  `VERTEX_COLOR_LEGEND`, `VERTEX_STATUS_LEGEND`, `VERTEX_PARAMS_<g>.json`.
- **Scenes:** CANON_WAYFARER, VERTEX_V4, VERTEX_V0, COMPARE_SIDE_BY_SIDE, COMPARE_TOP (added: wings hidden so the lanes stay
  readable), COMPARE_SPAN, VERTEX_CUTAWAY (120° wedge removed), BRAKING_EXPOSURE, RADIATOR_ALTERNATIVES.
- **Cameras:** 19 (`CAM_VTX_01` to `17`, plus `07b` module cutaway and `09b` alternatives top view). Changes from `CAMERAS.md`:
  07b and 09b added; 15, 16 and 17 added for whole V0, canon and V4; 09 is an end view along X so the alternatives read as spokes.

## 2. Confirmed on the model

ISS-001 hot band 7.1 m from ring A (173 kW/m²), ISS-002 C1 envelope 4.8 m from the hot band (91 kW/m²), ISS-003 no sized coil load
path, ISS-004 skirt A crossing both docking corridors (r 36.7 m at the docks), ISS-005, ISS-006. Full table: `ISSUES.md`.

## 3. Failed or worse

- **ISS-009 (new, MAJOR):** the launcher does not fit. The bore has 14.5 m between the shield face and the FDP-1 magazine; a 20 m
  barrel runs through the magazine and the LiH plug. One target in flight at 13.4 km/s needs 630,000 g in 14.5 m.
- **ISS-011 (new):** ring A sits only 3.1 m inside V4's hardware shadow (V0 had 24.6 m).
- **ISS-012 (new):** C1/C2 sit outside the shadow on the stand-off sphere with no armour.
- **ISS-010 (new):** the canonical 1,800 K blades remain beside the Vertex hot band; which one is the drive's hot radiator is not set.
- **Scale:** V4 is 766 m long and 20.3 km wide. The canonical ship is a dot in `CAM_VTX_04`. Nothing was shrunk.

## 4. Improved (drawn, not adopted)

- Graded hot band: ring A 173 → 56 kW/m², C1 91 → 30 kW/m² (ISS-001, -002).
- Coil load path made visible with two candidates; strut azimuths clear both wing planes (ISS-003).
- Skirt B and C show how the docking conflict goes away (ISS-004), at the cost of farm and dock exposure while braking.
- 12-segment loops with clocked trim joints give one split for T02/T03 to judge (ISS-007).
- Tandem R2 halves the span to 5.5 km (outline only; mass and manifolds not closed).

## 5. Uncertain

Every PROTOTYPE size (launcher 20 m, ignitor offset 1.6 m, tritium sphere 2 m, coil struts, rib pitch, skirt B edge); coil structure
mass; wing dynamics; whether irradiance limits exist for the rings and C1; the canonical blades' role under Vertex. Workbench renders
show form and fit only.

## 6. Recommended next ship-design step

Fix the module bore first (ISS-009): it decides whether V4's one-target-in-flight injection is possible at all. Ask T04/T01 for the
launcher length at 13-15 km/s, and in T05 draw the three ways out (magazine moved forward, two to four targets in flight, launcher
offset with its own shield port), with their shield streaming paths. Then adopt or reject the graded hot band with T01 (D-T05-1),
since it settles ISS-001, ISS-002 and ISS-010 together.
