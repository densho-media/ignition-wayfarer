# Vertex Drive Technology Atlas: report

Research only. Nothing here replaces the canonical Fiji Drive, changes production geometry, the Drive workbooks or IGNITION canon.
Every ship number below comes from the FDP-1 calculator (optimistic tier, four 0.016 c burns) through `convergence.py`; the full
tables are in `results/CONVERGENCE.md`, the records in `ATLAS.md`, the 3D readiness in `READINESS.md`.

## Summary

The Atlas holds 34 records (8 workstreams VTX-01 to VTX-08, 26 technologies), 24 sources, 29 interactions and 12 decisions, all in
validated TOML. Run through the FDP-1 calculator, **plausible engineering alone (Vertex 1) halves the ship: 20,760 t to 10,416 t**, and
the canon-bounded Vertex 2 reaches 9,272 t. The gain comes almost entirely from heat and recirculating power (a hotter warm loop, a
smaller house load, driver galleries inside the shadow cone), not from better collimation: halving the plume striking hardware saves
only 3 %. Every generation flies the four 0.016 c burns. None meets the LOCKED 6.0-year mission at FDP-1's 0.0069 g (6.35 y); all do
at 0.0073 g (V1 10,935 t, V2 9,638 t). **1-1.5 g is out of reach** by a factor of 57 (V2) to 100 (V0). The design still lives above a
**target gain cliff** of 1,257 (V0), 705 (V1) and 581 (V2) against a demonstrated 4.1 (D-T), and its steepest risk is nozzle efficiency
(0.79 to 0.72 adds 30 % to V1). The sacrificial liner stays rejected: the pulse ledger finds no tamper that raises exhaust velocity at
any fuel areal density. The largest unaddressed integration problem is dust at 0.016 c, worst during engine-first braking.

## A. Implementation

Everything is in `lab/variants/vertex-drive/` on branch `claude/project-thread-dqcppt`, plus one row in `lab/README.md`.

| Path | Content |
| --- | --- |
| `registry/technologies.toml` | 34 records with all 20 brief attributes, three maturity stages, A/B/C answers, geometry block, priority scores, numerical claims with provenance |
| `registry/sources.toml` | 24 sources (title, authors, date, locator, finding, limits, relation, PMDS verification state) |
| `registry/links.toml` | 29 enables / improves / worsens / conflicts / shares interactions, each quantified by a result case or marked UNKNOWN |
| `registry/generations.toml` | V0, V1, V2 as FDP-1 overrides; each change names its technology, basis (TARGET or MODEL) and any owner decision |
| `registry/decisions.toml` | 4 technical conclusions, 5 canon approvals, 3 experiment approvals |
| `atlas.py` | validator (duplicate IDs, missing attributes, broken references, cycles, enums, PMDS IDs, palette keys, claim provenance, unit conflicts, case references) and generator |
| `convergence.py` | adapter to `lab/variants/fdp1/run.solve` and `fourburn.architectures._pulse`; benchmarks, bisection thresholds, sensitivity bands, VTX-04 studies |
| `ATLAS.md`, `READINESS.md`, `figures/dependency_map.svg` | generated documentation |
| `results/convergence.json`, `results/CONVERGENCE.md` | generated results (346 s on 4 cores) |
| `tests/test_vertex_atlas.py` | 16 checks: registry valid, each error class caught, documents in sync, V0 = FDP-1, energy ledger closes, canon guard |

## B. Atlas summary

| Workstream | Records | Credibility | Verdict | Status |
| --- | --- | --- | --- | --- |
| VTX-01 Advanced pulsed fusion ignition | 01A magnetised target, 01B heavy-ion driver, 01C target factory, 01D D-T spark | B | Plausible future | Under investigation; gain is the cliff |
| VTX-02 Fiji lattice field engineering | 02A canon capability card, 02B NI REBCO loops, 02C inductive recovery | C (Fiji) | Fictional-dependent | Canon card only; no Fiji credit |
| VTX-03 Helical magnetic capture | 03A clocked sectors, 03B shaping coils, 03C counter-helicity | B | Unresolved | Sign unknown until simulated |
| VTX-04 Sacrificial injection (reopened) | 04A tamper, 04B hydrogen low gear, 04C vapour curtains, 04D Li-6/B-10 | A | Possible, not practical | Tamper contradicted; 04B mode only |
| VTX-05 Predictive ignition control | 05A target/driver-side control, 05B diagnostics and safe stop | B | Plausible future | Enabler, no mass credit |
| VTX-06 Directional radiation escape | 06A shadow shield and cone, 06B renewable faces | A | Plausible future | Supported |
| VTX-07 Advanced thermal systems | 07A split warm loop, 07B droplet radiator, 07C house load, 07D deployable wings | B | Plausible future | Highest leverage |
| VTX-08 Particle protection (new) | 08A vaporisation bumpers, 08B detection, 08C magnetic deflection, 08D braking | B | Unresolved | 08C impossible for grains |

## C. Most promising directions

Ranked by the Atlas priority score and checked against the measured sensitivities:

1. **Warm loop temperature (VTX-07A).** 600 to 700 to 800 K takes V1 from 12,996 to 10,416 to 9,499 t and the wing tip from 1,461 m to
   366 m. Bottleneck: MW-class power conversion at 700-800 K and induction cores below their Curie points.
2. **House load (VTX-07C, VTX-01C).** 0.1 % to 0.05 % to 0.025 % of fusion: 12,037 to 10,416 to 9,758 t. The 0.1 % baseline itself is
   unsourced; the energy per target in the factory is the cheapest high-value study in the record.
3. **Driver efficiency (VTX-01B).** At the published 0.30 instead of the assumed 0.45, V1 grows to 12,978 t and the gain cliff rises to
   1,160. This is the most likely optimism in FDP-1.
4. **Gain (VTX-01, VTX-01A).** Each generation lowers the cliff (1,257, 705, 581), but every one is two to three orders above anything
   demonstrated. Magnetisation is the only lever in the record, and its benefit is UNKNOWN.
5. **Dust protection (VTX-08, 08A, 08D).** No mass benefit, but essential: without it the 112 m loops and the wings are not credible.

## D. Convergence

| Generation | Departure t | Closes 4 x 0.016 c | Six-year a0 (departure) | Ceiling a0 | 1 g deficit | Gain cliff | Nozzle-eff. cliff |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V0 FDP-1 | 20,760 | yes | 0.0073 g (23,845 t) | 0.0100 g | 100x | 1,257 | 0.575 |
| V1 engineering | 10,416 | yes | 0.0073 g (10,935 t) | 0.0155 g | 65x | 705 | 0.528 |
| V2 canon Fiji | 9,272 | yes | 0.0073 g (9,638 t) | 0.0176 g | 57x | 581 | 0.528 |

Variants: V1 keeping the idle H2 vessels 11,083 t (+667 t, decision D-04); V1 at driver efficiency 0.30 12,978 t; V2 with the
collimation band (plume strike halved) 8,961 t (-3 %). The nozzle-efficiency cliff of V1 and V2 lands on the same bisection step
(about 0.53), so below that the thermal package no longer moves the cliff; the cause was not separated.

Sensitivity of V1 (none credited to any generation): plume strike 0.005-0.04 gives 9,859-11,274 t; nozzle efficiency 0.65 / 0.72 /
0.79 / 0.86 gives 25,423 / 13,560 / 10,416 / 8,898 t. The integration study's package (ptw 0.01, 800 K, house half, no idle H2) is
reproduced at 9,633 t, and galleries alone at 19,829 t.

What V2 still lacks, stated as the extra capability that would be needed and not assumed: to make the mission robust, D-3He target gain
of about 600 or more at 100-200 Hz; to hold 6.0 y at 0.0069 g, a minimum round trip 0.35 y shorter (V2 needs 0.0073 g instead); for 1 g, drive,
power and radiator specific mass about 57 times lower at constant exhaust velocity. No record in the Atlas, and no Fiji property in canon,
provides the last.

## E. Barriers

- **Target gain.** Demonstrated 4.1 (D-T), needed about 600-1,300 (D-3He). D-3He has never ignited.
- **Nozzle efficiency.** 0.79 is the theoretical bound for beta >> 1 nozzles; simulations reach 0.34-0.70. The design is steepest here.
- **Driver.** Published heavy-ion efficiency 0.20-0.30 against 0.45 assumed; mass per watt and final-focus survival unknown.
- **Hot machinery.** No MW-class power electronics at 800 K; induction cores lose permeability near 668 K (amorphous) and 823-843 K
  (nanocrystalline).
- **Dust.** No shield physics validated above about 9 km/s; impact speed 4,800 km/s; magnetic deflection does not work for grains
  (charge-to-mass about 0.6 C/kg); braking burns fly engine-first.
- **Tamper.** The pulse ledger finds no tamper that raises exhaust velocity at fuel areal densities 1-90 g/cm2, even where 26 % of fusion
  escapes. The 2026-11-08 analytic break-even near 12 % leak is not borne out; tamper-enhanced burnup remains unmodelled.

## F. Proposed architecture

**Vertex 1 is the proposed research baseline**, not a canon proposal: FDP-1's axial pulsed point burn and three-loop nozzle, with a split
warm loop (cores about 600 K, power conversion about 773-800 K), house load at or below 0.05 % of fusion, driver galleries folded inside
the 7.9 deg shadow cone, clocked trim sectors with balanced helicity as the only helical feature, and no tamper. Deployable warm wings
(650 m tip radius in V1, 360 m in V2) and an engine-side dust strategy are required but undecided (D-05, D-06). Vertex 2 adds an 800 K
loop and lighter tungsten armour and is the upper bound of canon-bounded engineering. Adopting either instead of the canon four-nozzle
Fiji Drive is an owner decision (D-08), not proposed here.

## G. Blender readiness

From `READINESS.md`: engineering-supported (could be drawn now from calculator numbers) are the burn point and stand-off sphere, the three
loops (r 37.3 / 64.7 / 112.0 m in V1), the shadow shield and hardware cone, and the H2 vessels. Parametric placeholders are the driver
galleries, equipment module, target factory, split warm wings (tip 653 m V1, 356 m V2), armour panels, bumpers, sensors and recovery
hardware. Conceptual illustrations only: the helical harmonic, shaping coils, droplet sheet, vapour curtains and the engine-side braking
shield. Nothing has been drawn. A blockout would go to `work/` as pink `VAR_vertex` collections after decision D-10.

## H. Open decisions

Owner, canon: D-04 idle H2 vessels; D-05 deployable warm wings; D-06 engine-first braking through dust (also affects the canon ship);
D-07 which open Fiji lattice parameters canon fixes; D-08 Vertex vs the canon drive topology. Owner, experiments: D-09 pulsed nozzle MHD
study; D-10 Blender blockout; D-11 a non-canon Drive record. Technical conclusions D-01, D-02, D-03 and D-12 stand unless challenged.

### Roadmap (research order)

1. Source the energy per target (VTX-01C / 07C) and book driver losses by component (VTX-07A): cheap, and they set the warm loop.
2. Re-run V1 at published driver efficiency as the conservative case; carry 0.30 as the planning value.
3. Dust exposure map in both orientations using the FDP-1 requirements map (P11), then a vaporisation-regime bumper estimate (VTX-08A, 08D).
4. Pulsed nozzle MHD study, plain vs clocked vs shaped (VTX-03, decision D-09).
5. Published magnetised D-3He gain curves (VTX-01A); D-T spark with tamper capture (VTX-01D with 04A).
6. Blockout in `work/` (D-10), only after 1-3.

## I. Validation

`atlas.py validate`: 34 records, 24 sources, 29 links, 12 decisions, 0 errors. `tests/test_vertex_atlas.py`: 16 tests pass, including
detection of each brief error class, generated documents in sync, V0 reproducing FDP-1 (20,760 t), every generation's energy ledger
summing to fusion power, and the canon guard (no file changed outside this folder and `lab/README.md`). The FDP-1 and four-burn code,
`data/`, `src/`, `tests/`, `tools/`, `godot/`, `web/` and the production assets are unchanged.
