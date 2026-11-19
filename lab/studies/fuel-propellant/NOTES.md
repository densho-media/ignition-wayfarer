<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | PROMOTED into main with the FPS V1.1 squash (2026-11-19); kept as the fuel-system check tools |
| Question | Does the integrated fuel and propellant system fit, connect, come apart for engine removal and stay inside the browser budget? |
| Model base | main 3532857 + FPS V0, V1, V1.1 (branch commit 577bff8) |
| Salvaged from | claude/project-thread-rx5y4x @ 577bff8, 2026-11-19 |
| Open owner questions | Drawn Vertex mass against the 250 t drive allowance; CONSERVATIVE frame case; thrust-ring node joints; removal fixture. Kept numbers: references/evidence/fuel_propellant.json. |
| Review | project files fuel-propellant/REVIEW_FUEL-PROPELLANT.blend (rebuild: make_review.py) |

# Fuel & Propellant System checks (FPS V1.1)

The tools that validated the Fuel & Propellant System through V1.1 (docs/FUEL_SYSTEM.md sections 10 and 11). They read the approved
ship (`data/`, `src/`, the saved assets) and write only their own results; nothing in the build reads them. Run from the repository root.

| Tool | What it checks | Run |
| --- | --- | --- |
| `probe.py` | every FPS (and with `--cluster` every cluster) object against all other evaluated geometry: overlaps and least clearance, designed contacts named | `blender -b assets/wayfarer/WF_WAYFARER_001.blend --python lab/studies/fuel-propellant/probe.py -- --cluster out.json` |
| `probe_lines.py` | one FPS line's sample points against the saved meshes | `blender -b <vehicle> --python lab/studies/fuel-propellant/probe_lines.py -- <name>` |
| `endpoints.py` | every end of every FPS, farm-chain and cluster line lands on a line, equipment, tank, the bay, a panel or a declared interface | `python3 lab/studies/fuel-propellant/endpoints.py out.json` |
| `extraction.py` | engine N1 moved aft along its axis against every static vertex and edge midpoint of the saved vehicle, per 3° sector; pins and line stubs that the procedure removes first are classed | `blender -b assets/wayfarer/WF_WAYFARER_001.blend --python lab/studies/fuel-propellant/extraction.py -- out.json` |
| `readiness.py` | the canonical mass account, and the drawn cluster frame's delta and the whole drawn cluster placed on a copy of the spec: propellant, departure mass, acceleration, CG, vessel fill; frame FE with the ship's thrust | `python3 lab/studies/fuel-propellant/readiness.py [root [v1_frame_t]]` |
| `perf.js` | Explore Ship in headless Chromium (SW): ready time, transferred bytes, draw calls, triangles, frame time | `node lab/studies/fuel-propellant/perf.js <site> out.json` |
| `make_review.py` | the owner review file, opening on the propulsion assembly | `blender -b --factory-startup --python lab/studies/fuel-propellant/make_review.py -- [--render DIR]` |

## Findings

- The ship's canonical mass account carries the drive as its 250 t allowance; the drawn Vertex cluster (6,403 t) is outside it. The
  V1.1 frame's +83 t alone, if it were carried, would cost +191 t of propellant and fill He-3 to 98.4 % of the vessels.
- The flank ties halve the frame's governing utilisation at the NOMINAL field (0.82 → 0.41) and double the axial mount stiffness.
- Engine removal: 0.203 m least clearance on the true geometry; trunnion pins withdraw at least 0.42 m and the panel and inlet
  connections need removable spools of 0.30 and 0.38 m.
- Browser: Explore Ship 11.70 of its 12 MB budget, Enter Wayfarer 66.6 of 90 MB; V1.1 cost 21 draw calls.

Results: `results/` (V1 at dd4a64c and V1.1). The 7.31× fusion-power gap and the speculative hydrogen coupling are not resolved here.
