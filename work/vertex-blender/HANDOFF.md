# T05 handoff: Vertex Blender requirements and modelling plan (Stage A)

| | |
| --- | --- |
| Thread | T05, mechanical architecture, spacecraft geometry and visual design |
| Date | 2026-11-09 |
| Status | PARTIAL: Stage A DONE; Stage B not started (D-10 Stage B awaits ApeDevil) |

## A. Mission and scope

- Investigated (owner points 1-8, 2026-11-09): V4 as principal configuration (1); canon unchanged, V0 historical, V5 ghost (2); true
  scale incl. the 10.1 km wing tip (3); radiator alternatives (4, `RADIATORS.md`); collections, parametric inputs, cameras, workflow
  (5, `COLLECTIONS.md`, `PARAMETERS.md`, `CAMERAS.md`, `WORKFLOW.md`); evidence status per component (6, `GEOMETRY_SPEC.md`);
  interfaces with closure coils, dust shielding, replaceable sectors, launchers, docking, maintenance (7, `GEOMETRY_SPEC.md` §2,
  `ISSUES.md`); delivery for review (8).
- Excluded: Blender geometry (Stage B, D-10); the D-21 simulation proposal and the story checks (other threads); V1, V2 (historical
  conditional); any change outside `work/vertex-blender/`.

## B. Repository state

| Item | Value |
| --- | --- |
| Starting commit | `a1c8246` (T00 Phase 4) |
| Branch | `claude/project-thread-ctwplp` |
| Resulting commit | see `git log` on the branch (pushed) |
| Changed paths | `work/vertex-blender/` only |
| Rerun | `python3 work/vertex-blender/screen.py` (about 12 s; writes `screen.json`) |

## C. Research findings

### Published evidence
None new. Radiator technology rows are T01's (`studies/thermal/REPORT.md` §3.6); liquid belt radiators are a 1980s-90s NASA concept,
cited without a number (UNVERIFIED).

### Calculated results
- V4 at true scale: X −346.2 to +420.1 m (766 m) with the T-B stretch, wing span 20,255 m. MODEL (`screen.json`).
- Hot-band irradiance: 173 kW/m² on ring A, 91 kW/m² on C1; graded layout 57 and 30 kW/m². MODEL (view-factor integration).
- One-target-in-flight launcher speed: V4 13.4 km/s, V0 9.9, V5 9.4. MODEL.
- Radiator alternatives R0-R7 (`RADIATORS.md` §3). MODEL / EXTRAPOLATION as labelled.

### Engineering extrapolations
- Only half-planes through the axis are edge-on to both the burn and the dust stream; this fixes the wing form in kind.
- A tandem W2 on the T-B stretch would halve the span at equal area (5.5 km). Mass and manifolds not closed.
- A V4 skirt on the 5.5° cone collides with the docking corridors.

### Fictional assumptions
Canon Fiji lattice only, as in the Atlas; no Level C property is used.

### Unknowns
Launcher length, ignitor volume, closure-coil structure, tritium store, wing dynamics, acceptable ring irradiance (`NOTES.md`).

### Negative results
Heat pump to 1,000 K (47-90 GW extra electric), coaxial cone radiator (2.6-5.0 km² dust frontal area), propellant heat sink (1.3 MW
against 78.6 GW), six-wing layout (twice the area for −36 % span).

## D. Quantitative effects

| Quantity | Value | Unit | Range | Label | Source |
| --- | --- | --- | --- | --- | --- |
| V4 wing tip radius | 10,128 | m | 3,400-14,500 (bands) | MODEL | convergence.json, screen.json |
| V4 hot band | r 10-847 | m | graded: r 10-991, X ≤ 48.9 | MODEL / PROTOTYPE | screen.json |
| Ring A irradiance (hot band) | 173 | kW/m² | 57 graded | MODEL | screen.json |
| C1 irradiance | 91 | kW/m² | 30 at 20 m clearance | MODEL | screen.json |
| Launcher, one in flight | 13.4 | km/s | 12-15 | MODEL | screen.json |
| Tandem W2 tip | 5,456 | m | — | EXTRAPOLATION | screen.json |
| Wing root moment | 1.7e9 | N m | — | EXTRAPOLATION | screen.json |

## E. Model and geometry implications

`GEOMETRY_SPEC.md` is the full list. Key additions to the FDP-1 part list for Stage B: closure coils, guard rings, 12 split lines per
loop, sector clock, three skirt extents, launcher and catcher, ignitor line, tritium store, circuit bands, graded hot band, droplet
bars and sheet overlay, tip-bracket circles, radiator-alternative outlines.

## F. Dependencies

| Needed from | What | Status |
| --- | --- | --- |
| T00 | V0/V4/V5 overrides | received at `a1c8246` |
| T01 | ring and C1 irradiance limits, wing structure (ISS-001, -005) | open |
| T02 | skirt extent versus docks, sector count (ISS-004, -007) | open |
| T03 | C1 screen load, coil load path (ISS-002, -003) | open |
| T04 | launcher, catcher, ignitor envelopes (ISS-008) | open; PROTOTYPE sizes used |

## G. Decisions

- Existing: D-10 (Stage B) for the owner; D-05 wings stay experimental geometry; D-06/D-15/D-17 kept open (three skirt extents).
- Proposed: D-T05-1 adopt chordwise hot-band grading as a Stage B requirement (owner with T01; recommend yes). D-T05-2 draw tandem W2
  (R2) and W3 as outline alternatives only (recommend yes).
- A recommendation is not an owner approval.

## H. Validation

- `screen.py` exit 0; V0/V4/V5 departure masses equal `results/convergence.json` (20,760 / 42,916 / 19,442 t).
- Coverage: all 39 records with geometry status other than NONE are drawn or deferred with a reason (`GEOMETRY_SPEC.md` §3).
- `python3 tools/workflow.py checks`: only `work/` changed.
- Limitations: irradiance is diffuse, single-bounce, worst point, no shading by other hardware; wing loads static.

## I. Integration instructions for T00

1. Nothing to integrate yet; `work/vertex-blender/` stays on this branch until Stage B is reviewed.
2. ISS-006: correct the dock position in `lab/variants/fdp1/NOTES.md` and `planning/T05-BLENDER.md`.
3. Consider X-T05-1: a calculator option to place the hot band along the chord (chordwise grading), so the irradiance becomes a
   checked clearance.

## J. Recommended next experiment

Stage B first pass (after D-10): cameras 01, 02, 04, 06, 12 and 13 in Workbench, with the calculated and graded hot bands, to confirm
ISS-001, -002 and -004 on the model before any detail.
