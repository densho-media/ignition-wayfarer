# Parametric configuration requirements (T05 Stage A)

One parameter file per drawn generation, `params/<g>.json`, written by `build_vertex.py --params-only` (Stage B) from a live solve; it
is never hand-edited. `screen.py` already produces the same content under `screen.json` → `generations.<g>`.

| Group | Quantities | From |
| --- | --- | --- |
| Generation | id, record status, departure t, overrides list with basis and technology | `convergence.generations()` (registry/generations.toml) |
| Full record `R` | everything `geometry.parts(R)` reads: `layout`, `nozzle`, `shield`, `drivers`, `structure`, `thermal`, `tanks`, `injection`, `fusion`, `closure`, `pellet` | `fdp1.solve('baseline', overrides minus vertex)`; the `vertex` block is resolved by `convergence.resolve` first |
| Closure coils | polar angles 20°/40°, winding minor and envelope ratios | T03 `studies/nozzle/results/nozzle_results.json` → `designs.C_W15`, scaled by R_s / 43.11 m |
| Warm circuit bands | band temperatures and area shares | T01 `studies/thermal/ledger.json` |
| Dust protection | skirt apex and half-angle (from R), r 45 m limit, guard-ring offsets 20-25 m, bumper stand-off 2 m | T02 HANDOFF E (values), re-derived on R |
| Bands (ghosts) | density scan stand-offs, launcher path, warm/driver tip radii | `results/convergence.json` → `cases.V4_*` |
| Canon datums | AFT, FWD, RADIATOR_FRONT, RING_A, ring sweep, dock and airlock x/az, farm x | `data/wayfarer_3d.toml` through `src/wayfarer/layout.py` (read only) |
| Canon objects | names, counts, transforms for the unchanged-ship check | the built `assets/wayfarer/WF_WAYFARER_001.blend` |
| T05 PROTOTYPE sizes | launcher 20 m, ignitor 1 m tube, tritium sphere 2 m, split-line count 12, skirt extents A/B/C | `build_vertex.py` constants, each named `PR_*` and listed in `VERTEX_PART_STATUS` |

Revision rule: a thread result changes a number in its JSON (or a registry override); the rebuild picks it up. A `PR_*` constant changes
only with a `NOTES.md` log line. No mesh is edited by hand.
