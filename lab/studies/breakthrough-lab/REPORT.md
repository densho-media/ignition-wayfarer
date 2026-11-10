# Breakthrough Lab: report

| | |
| --- | --- |
| Kind | study, research only, NON-CANON |
| Calculators | T00 at `030fc14` (Feasibility Gate 2; the calculators are byte-identical to the first gate's `43fac75`): FDP-1 `fdp1-v1` through the Technology Atlas adapter (`convergence.solve`), the feasibility gate's coupled solver (`coupled.run`) with the A1 loss booked as Gate 2 corrects it |
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
| BT-001 0.7, BT-003 0.791, BT-004, BT-005 unconstrained | 1 | 85,226 t | 219,056 t, converged |
| BT-001 0.7, BT-003 0.791, BT-002, BT-006, BT-005 unconstrained | 1 | 56,493 t | 144,407 t, converged |
| BT-001 0.5, BT-003 0.791, BT-004, BT-006, BT-005 unconstrained | 1 | 75,136 t | 184,648 t, converged |

The lightest closing case (every lever at its strongest table level) is 29,625 t, 668 m long in the calculator's layout, with a 5.3 km
radiator tip radius; its coupled check is 62,037 t.

**The coupled check more than doubles every closing ship (2.1-2.6x).** Re-sizing the closure-coil hardware on every pass and booking the
A1 tilted closure's thrust loss as Gate 2 corrects it (eta_T x 0.967, the momentum factor squared; the first gate applied 0.983 once)
takes V4 from 42,916 t to 96,696 t. The spine is not
in this check: at T05's 0.2 Hz cantilever basis the gate shows the coupled ship diverging, so every closing case here still carries
that open blocker, together with target survival, D-3He ignition and the MHD validity of A1.

**A finite launcher breaks the coupled check.** The only closing set with no fictional level (V4 with a 12 km/s launcher) closes alone
at 61,544 t, but with the coil hardware and A1 added at its launcher-limited 145 Hz the coupled loop diverges past 400 kt. That matches the gate's finding that rate caps make the coupled ship diverge. The lightest case keeps 62,037 t with a
12 km/s launcher because its launcher does not bind. A finite launcher enters this check as the pulse-rate cap of its own uncoupled
solve, held fixed (as the gate's capped runs); the cap a coupled ship would need is not iterated.

**Ranking (Weakest Links).** Tier 1, fundamental: WL-001 target compression and gain, WL-002 axial plasma leak, WL-004 target
injection and survival. Tier 2, coupled: WL-006 spine stiffness, WL-009 nozzle efficiency, WL-003 mass closure. Tier 3, penalties:
WL-007 closure coils, WL-005 radiators. Tier 4: WL-008 shielding faces. The 20 km radiator span ranks below the target physics
because fixing it cannot make the engine work.

## What Feasibility Gate 2 adds (T00 030fc14, T05 f497778)

Gate 2 does not change a calculator; it changes what the closing cases mean. Each point below is in the register with its pointer.

- **A1 is geometrically blocked.** Every tested ship that holds the 7.5 deg shadow cone diverges past 400 kt. The coupled check here
  still books A1 (as the only candidate fix for the axial leak), so every closing case carries a fix that Gate 2 shows no tested ship
  can use. Without A1 the axial leak (342 J/cm2 per pulse) is unsolved.
- **The target cannot reach the gain these cases use.** BT-001's levels take the gain from T04's compression ceiling (1,084 at
  coupling 0.5). Gate 2 finds the best analytical operating point at gain 440, needing a 7.8 MJ, 20 ps ignitor; V4 closes only at
  703 or more. BT-001 L2 and L3 therefore also assume an ignitor that is not in any lever.
- **The 0.791 nozzle is the calculator's 1 deg value.** The converged ledger gives 0.67 and shell-scale smoothing 0.80-0.82; the coupled
  ship needs about 0.75. BT-003's limit is now Gate 2's 0.82; the table levels are unchanged.
- **The spine stays the open blocker.** T05's Gate 2 FE puts the section's saturation near 0.13 Hz; every converged coupled case sits
  at an estimated 0.04-0.07 Hz, inside the slosh and ring-spin band.
- Gate 2 recommends pausing Vertex geometry and closing the four-burn engine's non-ICF architectures with the same coupled method.

## What would change these results

Gate 2 narrows the decisive experiments to one: a 1D radiation-hydrodynamics implosion of the FDP-1 D-3He target as a falsification
test of the compression leg (pass: fuel energy at least 0.30 of the driver at alpha 1.2 or less; fail: below 0.25), not run. It
recommends against D-21 MHD of A1 while A1 is geometrically blocked. Next for this study: a spine lever (BT-007) once the owner chooses a stiffness criterion, a launcher cap
iterated inside the coupled loop, and the target wall as exhaust mass.

## Files

| File | What |
| --- | --- |
| `import_research.py` → `imports/` | pinned T00 and T05 result files with manifests |
| `compute.py` → `results/scenarios.json` | the scenario grid, the named scenarios and the coupled checks (about 3 minutes on 4 cores) |
| `lab.py` | registry loading, validation, ranking rule, metric pointers |
| `site.py --json` | the website record (validates; any error stops the site build) |
| `tests/test_breakthrough_lab.py`, `tests/web_check.js` | data, scientific and website checks |
