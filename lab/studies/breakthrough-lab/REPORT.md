# Breakthrough Lab: report

| | |
| --- | --- |
| Kind | study, research only, NON-CANON |
| Calculators | T00 at `43fac75`: FDP-1 `fdp1-v1` through the Technology Atlas adapter (`convergence.solve`), the feasibility gate's coupled solver (`coupled.run`) |
| Inputs | `registry/scenarios.toml` (Layer A reference), `registry/breakthroughs.toml` (levels), imports with hashes in `imports/*/MANIFEST.json` |
| Result | `results/scenarios.json`: 288 cases (111 computed, 177 not computed by rule), provenance and reproduction checks |
| Date | 2026-11-10 |

## Summary

**The scientific reference does not close.** Layer A is the Vertex V3/V4 layout with every research target at its present-evidence
value: heavy-ion compression coupling 0.15, the best published nozzle thrust efficiency 0.64, demonstrated cryogenic target injection
at 0.4 km/s, and FDP-1's optimistic tier for structure, driver hardware and radiators. FDP-1 cannot size it: even with targets that
always arrive, the drive, radiators and tanks outweigh what they lift (loop gain 3.1; the most it reaches is 0.0014 g against the
0.0069 g the mission needs). That is the hard-science answer, and the website shows it as such.

**Nine of the 111 computed breakthrough cases close, and every one needs the same three things:** compression coupling of at least
0.5 (BT-001, more than twice anything shown), the ideal-model nozzle efficiency 0.791 (BT-003, a calculated upper bound) and a target
launcher well beyond any target that survives (BT-005). No combination of the Level B mass levers (BT-002 structure and armour, BT-004
radiators, BT-006 driver hardware) closes without those three. The grid reproduces T00 exactly: V4 at 42,916 t, V3 not closing (same
reachable acceleration), and V4 with a 12 km/s launcher at 61,544 t (T00's launcher sweep).

**The smallest sets (no other closing case uses less of every breakthrough):**

| Breakthroughs | Fictional levels | Departure | Coupled check (coils + A1) |
| --- | --- | --- | --- |
| BT-001 0.5, BT-003 0.791, BT-002, BT-004, BT-006, BT-005 at 12 km/s | 0 (two unverified) | 61,544 t | diverges past 400 kt (rate held at the launcher's 145 Hz) |
| BT-001 0.7, BT-003 0.791, BT-004, BT-005 unconstrained | 1 | 85,226 t | 175,877 t, converged |
| BT-001 0.7, BT-003 0.791, BT-002, BT-006, BT-005 unconstrained | 1 | 56,493 t | 115,545 t, converged |
| BT-001 0.5, BT-003 0.791, BT-004, BT-006, BT-005 unconstrained | 1 | 75,136 t | 150,888 t, converged |

The lightest closing case (every lever at its strongest table level) is 29,625 t, 668 m long in the calculator's layout, with a 5.3 km
radiator tip radius; its coupled check is 54,051 t.

**The coupled check roughly doubles every closing ship.** Re-sizing the closure-coil hardware on every pass and applying the A1 tilted
closure's 1.7 % thrust cost takes V4 from 42,916 t to 81,873 t (the gate, with the launcher as well, reports 85,224 t). The spine is not
in this check: at T05's 0.2 Hz cantilever basis the gate shows the coupled ship diverging, so every closing case here still carries
that open blocker, together with target survival, D-3He ignition and the MHD validity of A1.

**A finite launcher breaks the coupled check.** The only closing set with no fictional level (V4 with a 12 km/s launcher) closes alone
at 61,544 t, but with the coil hardware and A1 added at its launcher-limited 145 Hz the coupled loop diverges past 400 kt (loop gain
0.90 per pass). That matches the gate's finding that rate caps make the coupled ship diverge. The lightest case keeps 54,051 t with a
12 km/s launcher because its launcher does not bind. A finite launcher enters this check as the pulse-rate cap of its own uncoupled
solve, held fixed (as the gate's capped runs); the cap a coupled ship would need is not iterated.

**Ranking (Weakest Links).** Tier 1, fundamental: WL-001 target compression and gain, WL-004 target injection and survival, WL-002
axial plasma leak. Tier 2, coupled: WL-006 spine stiffness, WL-009 nozzle efficiency, WL-003 mass closure. Tier 3, penalties:
WL-007 closure coils, WL-005 radiators. Tier 4: WL-008 shielding faces. The 20 km radiator span ranks below the target physics
because fixing it cannot make the engine work.

## What would change these results

The two decisive experiments named by the T00 gate, neither authorised yet: a 1D radiation-hydrodynamics implosion of the FDP-1
D-3He target (replaces BT-001's assumption with a computed coupling and gain), and MHD of the tilted closure (D-21; replaces BT-003's
vacuum-field assumption). Next for this study: a spine lever (BT-007) once the owner chooses a stiffness criterion, a launcher cap
iterated inside the coupled loop, and the target wall as exhaust mass.

## Files

| File | What |
| --- | --- |
| `import_research.py` → `imports/` | pinned T00 and T05 result files with manifests |
| `compute.py` → `results/scenarios.json` | the scenario grid, the named scenarios and the coupled checks (about 3 minutes on 4 cores) |
| `lab.py` | registry loading, validation, ranking rule, metric pointers |
| `site.py --json` | the website record (validates; any error stops the site build) |
| `tests/test_breakthrough_lab.py`, `tests/web_check.js` | data, scientific and website checks |
