# T05 experimental Blender handoff (from T00 Phase 4, 2026-11-09)

| | |
| --- | --- |
| For | T05, the experimental Vertex Blender thread |
| Supersedes | The configuration list in `T05-BLENDER.md` §2 (V0, V1, optional V2). Everything else in that prompt still applies. |
| Base | branch `claude/project-thread-9rsgog`, the Phase 4 commit named in `/mnt/project-files/vertex/threads/T00.md` |
| Approval state | D-10 approved in principle (non-destructive, isolated files only). Stage A, the requirements review, may start now. Stage B modelling starts only after ApeDevil has seen Stage A. |
| Status | NON-CANON research geometry. Never in `assets/`, the generators or `data/`. |

## 1. Configurations to draw

The Atlas V1 and V2 are **historical conditional cases**. Their targets are energy-inconsistent, so do not draw them as designs. Draw
these configurations at one scale, next to the canonical ship:

| Collection | Configuration | Role | Departure | Source |
| --- | --- | --- | --- | --- |
| (appended, unchanged) | Canonical Wayfarer, four-nozzle Fiji drive | reference; never altered | — | `main` |
| `VAR_VERTEX_V0` | FDP-1 | reference | 20,760 t | `results/convergence.json` → `generations.V0` |
| `VAR_VERTEX_V4` | **corrected research target (preferred)** | the experimental configuration | 42,916 t | `generations.V4` |
| `VAR_VERTEX_V5` | bound at coupling 1.0 | outline or ghost only, never as a target | 19,442 t | `generations.V5` |

Read every dimension from `results/convergence.json` at the commit you start from. Never copy a figure from this page into geometry
code. The tables below are for orientation.

## 2. V4 envelope with its uncertainty ranges

| Element | V4 nominal | Range to show | Range source (convergence.json case) | Geometry status |
| --- | --- | --- | --- | --- |
| Burn point aft of the shadow shield (X-ray stand-off) | 64.7 m | 43 m (dense fuel, V5) to 65 m; T04 density scan 1,000-3,000 g/cm³ | `V4_density_scan` | ENGINEERING_SUPPORTED |
| Magnetic loops (radii) | 56.0 / 97.0 / 168.1 m | V5: 37.3 / 64.5 / 111.8 m | generations V4, V5 | ENGINEERING_SUPPORTED |
| Closure coils C1, C2 (VTX-03D, preferred nozzle) | C1 r 14.74 m at z +40.51 m, C2 r 27.71 m at z +33.03 m (nozzle frame x = x_burn + z, V1 scale) | scale with the stand-off (×1.5 for V4); C1 envelope r 2-3.2 m | T03 `studies/nozzle/results/nozzle_results.json` C_W15 | PARAMETRIC_PLACEHOLDER |
| Hardware cone half-angle | 5.5° | V5 7.9°. Closure coils raise the solid angle 2.4-3.0×, so show their shadow cone | generations | ENGINEERING_SUPPORTED |
| Shadow shield | 514 t | 359 t (V5) to 665 t (nozzle 0.740) | `V4_nozzle_band` | ENGINEERING_SUPPORTED |
| Target injection path (shield face to burn) | 68.4 m | 82.7 m with a 12 km/s launcher | `V4_launcher_sweep` | PARAMETRIC_PLACEHOLDER |
| Target launcher barrel and sabot catcher (VTX-01H) | on the bore axis inside the shadow cone | 12-15 km/s class: length UNKNOWN (10-20 m at 1e5 g, T01) | T01 HANDOFF | PARAMETRIC_PLACEHOLDER |
| Fast-ignitor beam line (VTX-01G) | beside the target path | UNKNOWN volume | T04 | PARAMETRIC_PLACEHOLDER |
| Warm radiator wings (W2, azimuth 0° and 180°) | tip radius 10.1 km, 4.95 km² | 6.7 km (670 K) to 14.5 km (12 km/s launcher); 3.4 km at driver efficiency 0.45 | `V4_warm_band`, `V4_launcher_sweep`, `V4_driver_band` | PARAMETRIC_PLACEHOLDER |
| Warm wing circuit bands (VTX-07E) | 1,000 / 740 / 700 / 640 / 550 K bands along the span | proportions from T01 `studies/thermal/ledger.json` | T01 | PARAMETRIC_PLACEHOLDER |
| Hot radiator (root bands, VTX-07F) | 0.462 km² | 0.21 (V5) to 0.97 km² (nozzle 0.740) | generations, `V4_nozzle_band` | PARAMETRIC_PLACEHOLDER |
| Propellant tanks | 2,545 t of tank for 27,116 t of propellant | up to 38,886 t of propellant (12 km/s launcher) | generations | ENGINEERING_SUPPORTED |
| Skirt in the shadow cone (VTX-08E) | 44,878 m² at V1 scale, 22-90 t | competing with bumpers (VTX-08F) and replaceable sectors (VTX-03E): draw all three as alternatives | T02 `studies/dust/results/impacts.json` | CONCEPTUAL_ILLUSTRATION |
| Replaceable loop sectors (VTX-03E) | six per loop | split lines only | T02 | PARAMETRIC_PLACEHOLDER |
| Idle H2 vessels | **removed** in V4 (owner, 2026-11-09) | keep them hidden, not deleted, in the canonical appended ship | `V4_keep_idle_H2` (+3.0 %) | — |

## 3. Rules that follow from the integration

- Draw **no helix**. Clocked sectors give under 1° of shear (D-01, refined by T03); show a sector clock instead.
- Draw **no half-size dense-compression nozzle**. Chain K4 was withdrawn (T06).
- Every V4 mass is a lower bound. These are unbooked:
  - closure-coil structure, 855-1,281 t;
  - the skirt;
  - the launcher;
  - the tritium store.
  Label their placeholders with that.
- The warm wings dominate the silhouette. Review whole-ship framing with the wing span before any detail. One camera must show the
  20 km span against the canonical ship (about 290 m long, docs/MODEL.md).
- Destination and heading are not locked. The dust protection is a set of alternatives, never one design.
- Keep the Vertex and canonical drives apart: D-08 is not approved. The Vertex is a comparison, not a replacement.

## 4. Stage A deliverable (unchanged from `T05-BLENDER.md`, with these inputs)

Deliver `work/vertex-blender/NOTES.md`, covering:

- function;
- fixed constraints (the canon keep-outs, plus the V4 envelope above);
- unknowns: launcher length, ignitor volume, closure-coil structure, tritium store;
- design freedom;
- the collection plan;
- the camera list.

Post it for ApeDevil's review before Stage B.
