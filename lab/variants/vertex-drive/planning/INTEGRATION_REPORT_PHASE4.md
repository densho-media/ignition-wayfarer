# Vertex Drive: Phase 4 integration report (T00, 2026-11-09)

| | |
| --- | --- |
| Kind | variant (research, NON-CANON); nothing here changes canon, production geometry, `data/`, `src/` or Google Drive |
| Branch | `claude/project-thread-9rsgog` |
| Base | `8de3ffa` (Phase 1 base) |
| Merged | T01 thermal `1302708`, T02 dust `3c665ec`, T03 nozzle `59244a9`, T04 ignition `fd4ff3d`, T06 convergence `f39023a` (merge `80d757a`) |
| Owner rulings applied | ApeDevil, 2026-11-09 (Phase 4 message): see `DECISIONS.md` |
| Not done | no squash onto `main`; no HPC run; no Drive write; no Blender geometry |

## 0. Summary

- **Corrected research target (V4): 42.9 kt at departure.** That is 2.1× FDP-1's 20.8 kt and 4.1× the Atlas V1 (10.4 kt). The Atlas V0-V2
  figures assumed an energy-inconsistent target: gain 3,000 at 3,000 g/cm³ needs a compression coupling η_c/α of 1.68 for compression
  alone, or 2.1 with the ignitor, against a physical maximum of 1. They also used the 0.79 momentum efficiency as a thrust efficiency
  and a 700-800 K warm loop that T01 could not book. V0-V2 are kept unchanged as **historical conditional** cases.
- **The lightest energy-consistent ship (V5, bound): 19.4 kt** at a perfect compression coupling of 1.0. FDP-1's 20.8 kt is in practice
  an ideal-limit ship.
- **V3, the conservative planning case, does not close.** It uses today's panel radiators (0.96 kg/m²) and no driver or structure
  package. At 1,000 g/cm³ it closes at 623 kt. This is a negative result, recorded as one.
- **Mission performance is unchanged in kind.** Every closing generation flies four 0.016 c burns at a0 0.0069 g (peak 0.0187 g),
  ve 19,201 km/s, burn 5.69 y and a minimum round trip of 6.35 y. The IGNITION "about six years" needs a0 0.0073 g, which takes V4 to
  50.3 kt. 1 g is 108× beyond V4's ceiling.
- **The new hard constraint is the target launcher.** Only one target may be in the open per pulse period, which needs a fast cryogenic
  launcher: V4 needs at least about 12 km/s and grows to 61.5 kt at 12 km/s. At 10 km/s or slower the calculator finds no solution.
- **The steepest lever is still the nozzle.** V4 closes down to η_T 0.63: 68.5 kt at 0.740, and 1,726 kt at the published 0.64, which
  sits just above that cliff. The closure-coil figure 0.791 comes from an ideal model. The D-21 2D simulation proposal is the test of it
  (prepared, not launched).

## 1. What was integrated

| Thread | Folder | Main result | Registry |
| --- | --- | --- | --- |
| T01 thermal | `studies/thermal/` | Split warm-loop ledger: 628 K equivalent with TARGET components, 489 K with today's; the 700-800 K loop is withdrawn. One target in flight needs 4.7-7.5 km/s injection. House load 4.4e-5 of fusion | VTX-07E (new), VTX-01H (new, merged); VTX-07, -07A, -07B, -07C, -01B, -01C revised |
| T02 dust | `studies/dust/` | Dust at 0.016 c: 1.15e13 J/kg (corrected unit); engine-first braking through a shadow-cone skirt; burn-facing bumpers; replaceable loop sectors; destination and heading unlocked | VTX-08E, -08F, -03E, -03F (new); VTX-08A to -08D revised |
| T03 nozzle | `studies/nozzle/` | η_T = η_mom²; 1 E_p cannot stop the pulse, 10-15 E_p needed; closure coils give η_T 0.74-0.79 (vacuum-field upper bound); clocked sectors give < 1° of shear | VTX-03D (new); VTX-03, -03A, -02C revised; S-MSFC-NOZZLE corrected |
| T04 ignition | `studies/ignition/` | Compression-energy ceiling on gain; FDP-1's target needs η_c/α > 1; D-T-cored fast ignition is the most credible route (43-144 kg tritium per mission); tampers add ≤ 1 % ve; staged D-T primaries rejected | VTX-01E, -01F, -01G, -01I (new), -01H (merged); VTX-01, -01A, -01D, -04A, -04B revised |
| T06 convergence | `studies/futures/` | Chains K1-K5; elasticities (nozzle -2.9, warm -1.7); final ship frontier; non-canon history scaffold | VTX-02D, -07F (new); links |

The registry has 47 records (34 before), 66 sources, 44 links and 25 decisions. Every provisional ID got the next free letter in its
workstream (mapping in `integrate_phase4.py`). `prior_finding`, `limitations` and `uncertainties` were only appended to. Thread study
sources (`S-T0n-STUDY`, `S-T01-LEDGER`) are PRIMARY_VERIFIED because T00 reran them (§7). Snippet sources stay UNVERIFIED.

## 2. Reconciliation

`RECONCILIATION.md` lists 17 items. The ones that change numbers:

1. **T02 dust energy, unit error.** The text says 1.15e10 J/kg; the value is 1.15e13 J/kg (1.15e10 J/g). T02's calculations used the
   right value; only the prose was wrong.
2. **Nozzle**: 0.79 is a momentum efficiency, so V0-V2 overstate the nozzle.
3. **Gain bound**: T06's form omits the ignitor and is 8-12 % optimistic. T04's ceiling is used: 1,084 at 2,000 g/cm³ and
   coupling 0.5 (T06 had 1,171).
4. **House load**: 4.4e-5 of fusion (T01), not T06's 2.6e-5.
5. **Plume on hardware**: 0.065 of the nozzle loss (T03 model), against FDP-1's 0.02 assumption.
6. **Injection figures**: T01 quoted V1 figures as "FDP-1". Both threads agree on the constraint.

## 3. Generations

Every number is an FDP-1 calculator result: optimistic tier, four 0.016 c burns, a0 0.0069 g (`results/convergence.json`,
`results/CONVERGENCE.md`). V0-V2 equal the frozen 2026-11-08 results exactly (`results/history/2026-11-08_atlas/`, test
`test_history_unchanged`).

| | V0 FDP-1 | V1 (hist.) | V2 (hist.) | V3 planning | **V4 research target** | V5 bound |
| --- | --- | --- | --- | --- | --- | --- |
| Status | HISTORICAL_CONDITIONAL | HISTORICAL_CONDITIONAL | HISTORICAL_CONDITIONAL | RESEARCH_TARGET | RESEARCH_TARGET | BOUND |
| Compression coupling needed | 2.11 (impossible) | 2.11 | 2.11 | 0.5 | 0.5 | 1.0 |
| Density / gain | 3,000 / 3,000 | 3,000 / 3,000 | 3,000 / 3,000 | 2,000 / 1,084 | 2,000 / 1,084 | 3,000 / 1,593 |
| Closes | yes | yes | yes | **no** (loop gain 1.10) | yes | yes |
| Departure t | 20,760 | 10,416 | 9,272 | — | **42,916** | 19,442 |

The corrections common to V3-V5:

- gallery radius 4.5 m;
- idle H2 vessels removed (owner: low gear out of the preferred configuration; canon unchanged);
- driver efficiency 0.30;
- warm loop at 628 K;
- house load 4.4e-5;
- nozzle η_T 0.791 at 15 E_p (TARGET upper bound);
- plume on hardware 0.065;
- payload 1,240.2 t, including T02's protection;
- coupling 0.5 (V5: 1.0).

V4 then adds the research package:

- driver 0.025 kg/kW;
- warm sheet 0.5 kg/m² (D-05);
- hot panels 1.5 kg/m²;
- nozzle structure 5.35e-7 kg/J;
- CFRP spars and trusses 12.5 / 60;
- loop armour 100.

V4 with the idle H2 vessels kept: 44,218 t (+3.0 %).

### Revised mass (t)

| | V0 | V4 | V5 |
| --- | --- | --- | --- |
| Propellant | 13,117 | 27,116 | 12,284 |
| Drive (drivers, nozzle, coils) | 2,750 | 7,358 | 3,026 |
| Radiators | 2,147 | 3,572 | 1,247 |
| Tanks | 1,231 | 2,545 | 1,153 |
| Structure | 529 | 724 | 293 |
| Shadow shield | 430 | 514 | 359 |
| Payload (incl. protection) | 990 | 1,240 | 1,240 |
| **Departure** | **20,760** | **42,916** | **19,442** |

### Revised power and pulse

| | V0 | V4 | V5 |
| --- | --- | --- | --- |
| Fusion power | 17.3 TW | 35.7 TW | 16.2 TW |
| Jet power | 13.5 TW | 27.9 TW | 12.6 TW |
| Thrust | 1.40 MN | 2.90 MN | 1.31 MN |
| Yield per pulse | 81 GJ (19.5 t TNT) | 182 GJ (43.6 t TNT) | 81 GJ (19.2 t TNT) |
| Driver energy per pulse | 27 MJ | 168 MJ | 51 MJ |
| Pulse rate | 212 Hz | 196 Hz | 201 Hz |
| Electrical driver input | — | about 110 GW (168 MJ × 196 Hz / 0.30) | about 34 GW |

### Revised thermal

| | V0 | V4 | V5 |
| --- | --- | --- | --- |
| Warm reject | 24.4 GW | 78.6 GW (628 K) | 24.5 GW |
| Warm area | 1.84 km² | 4.95 km² | 1.54 km² |
| Hot reject | 77 GW | 495 GW | 225 GW |
| Hot area | 0.072 km² | 0.462 km² | 0.210 km² |
| Wing tip radius | 3.6 km | **10.1 km** | 3.3 km |

Both sides of every warm-area figure check against Stefan-Boltzmann (Q / 2εσT⁴, ε 0.9) in `ResultArithmetic`. The V4 warm wings reach a
10.1 km tip radius (about 20 km span), so the warm radiator is the dominant visual and structural element.

### Revised structural envelope

| | V0 | V4 | V5 |
| --- | --- | --- | --- |
| X-ray stand-off (burn aft of shield) | 43.2 m | 64.7 m | 43.0 m |
| Loop radii | 37 / 65 / 112 m | 56 / 97 / 168 m | 37 / 65 / 112 m |
| Hardware cone half-angle | 9.6° | 5.5° | 7.9° |
| Injection path | 46.8 m | 68.4 m | 46.6 m |
| Hardware solid angle (calculator) | 0.019 | 0.025 | 0.033 |

These loads and masses are **unbooked** in the calculator (every mass above is a lower bound):

- closure-coil hoop tension 3-7 GN and inter-coil forces 0.2-1.9 GN, with coil structure 855-1,281 t on the virial bound (T03);
- closure coils raise the hardware solid angle 2.4-3.0× (0.040-0.051 at V1);
  ISS-014 puts their X-ray load at V4 at 11.9 GW (C1 10.4, C2 1.6) on T03's geometry, with a band of 11.9-16 GW
  (`ISS-014_COIL_RADIATION.md`);
- skirt 22-90 t (T02);
- launcher and sabot catcher;
- tritium store.

### Mission performance

| | V0 | V4 | V5 |
| --- | --- | --- | --- |
| Four 0.016 c burns | closes | closes | closes |
| a0 / peak | 0.0069 / 0.0187 g | same | same |
| Burn time | 5.69 y | 5.69 y | 5.69 y |
| Minimum round trip | 6.35 y | 6.35 y | 6.35 y |
| 6.0-year round trip | 23.8 kt at 0.0073 g | 50.3 kt | 21.0 kt |
| Ceiling a0 | 0.0100 g | 0.0093 g | 0.0117 g |
| 1 g | 100× short | 108× short | 85× short |
| Nozzle-efficiency cliff | 0.575 | **0.630** | 0.538 |

## 4. Uncertainty bands on V4 (`results/convergence.json` cases)

| Band | Case | Departure t |
| --- | --- | --- |
| Nozzle | η_T 0.791 (15 E_p) / 0.740 (10 E_p) / 0.64 (published) | 42,916 / 68,549 / 1,726,125 |
| Target launcher | ≥ 15 km/s / 12 / ≤ 10 km/s | 42,916 (not binding) / 61,544 (145 Hz cap, path 82.7 m) / no solution |
| Density at coupling 0.5 | 1,000 / 1,500 / 2,000 / 3,000 g/cm³ | 72,423 / 48,587 / **42,916** / 57,165 |
| Coupling | 0.2 (1,000) / 0.3 (1,000) / 0.3 (2,000) / 0.5 (2,000) / 1.0 (3,000) | no solution / 126,006 / no solution / 42,916 / 19,442 |
| Driver efficiency | 0.25 / 0.30 / 0.45 | 72,852 / 42,916 / 25,319 |
| Driver specific mass | 0.025 / 0.05 (Atlas) / 0.1 kg/kW | 42,916 / 199,129 / does not close |
| Warm loop | 489 K / 628 K / 670 K; panels 0.96 kg/m² | does not close / 42,916 / 35,949; 123,539 |

V5's launcher sweep: 10 km/s does not bind; 8 km/s gives 22,124 t; 6 km/s gives 47,519 t; 4 km/s has no solution. In every "no
solution" row of this table the FDP-1 integration diverges or the loop gain reaches 1 or more, so no ship exists. Each reason is in the JSON.

Density has an optimum near 2,000 g/cm³. Denser fuel is cheaper to burn but costs gain through compression. Thinner fuel gives larger,
slower pulses and longer stand-offs.

## 5. Successful and unsuccessful results (Atlas update)

**Supported or quantified**:

- VTX-07E, the circuit-by-circuit warm loop at 628 K: SUPPORTED as a booking method (TARGET components);
- VTX-01G, the D-T-cored ignitor: most credible route;
- VTX-03D, closure coils: preferred experimental candidate (D-24), physics UNRESOLVED;
- VTX-08E and VTX-08F, skirt and bumpers: proposed;
- VTX-03E, replaceable sectors: proposed;
- V4 and V5 close.

**Unsuccessful, kept as negative results**:

- V0-V2 are energy-inconsistent.
- The 700-800 K warm loop is withdrawn.
- The 0.79 thrust efficiency is withdrawn.
- K4, the dense-compression chain, is withdrawn (T06).
- VTX-01I, staged D-T primaries: CONTRADICTED.
- Clocked "helical capture" gives no useful shear (D-01 refined).
- Tampers add no ve at the mission ρR (D-02 amended).
- V3 does not close.
- At 489 K, at coupling 0.2, or at the Atlas driver mass of 0.05 kg/kW with V3 radiators, no ship closes.
- A 400 m/s gas-gun injector allows about 1 Hz.
- 1 g and 1.5 g are not met.

## 6. IGNITION timeline (read only, D-25)

The timeline was readable this time (T06 could not read it). Its content is summarised in `RECONCILIATION.md`, and nothing was copied
into the repository. Engineering conflicts:

- **T056**: a self-sustaining runaway departure to 0.016 c. A pulsed ICF drive stops when injection stops, so the departure needs a
  story mechanism or a Level C property. This is an owner question.
- **T057/G10**: about six years, against a 6.35 y minimum. 6.0 y needs a0 0.0073 g (V4 50.3 kt).
- **T042/G08**: high-g drives before First Ignition must be short, low-Δv stages, not this drive class.
- **T055**: "relativistic" is a story label for 0.016 c. Compatible with O04, which keeps the performance ladder OPEN.

The T058 gravity-assisted turn, the T060 fail-safe doctrine, T089 lattice degradation and G07 are compatible.

## 7. Validation

All checks ran on this branch with Python 3.13 on 4 cores.

| Check | Result |
| --- | --- |
| `atlas.py validate` | 47 records (8 workstreams), 66 sources, 44 links, 25 decisions; **0 errors** |
| `atlas.py render` | ATLAS.md, READINESS.md, dependency map regenerated |
| Atlas tests (`tests/test_vertex_atlas.py`) | **24 OK**: +3 (history unchanged, corrected generations energy-consistent, non-closing generations state why); arithmetic checks skip non-closing ships |
| FDP-1 tests | **45 OK** |
| Four-burn tests | **18 OK** |
| `convergence.py` full run | exit 0; V0 reproduces FDP-1 (20,760 t); 13 min 14 s |
| `convergence.py --report` | new: refreshes record text and CONVERGENCE.md without re-solving |
| `check_v3.py` (problem map) | exit 0; its rewrite of `VALIDATION_V3.md` reverted (pre-existing staleness on main, R-17) |
| `workflow.py checks` | selects no tests, no build, no inspection, no Godot check: only `lab/` changed |
| Paths changed since `8de3ffa` | `lab/` only |
| Study reproductions (clean worktree at `80d757a`) | see the table below |

| Study script | Exit | Time | Committed outputs reproduced |
| --- | --- | --- | --- |
| dust: environment, exposure, impacts, radiation, tables | 0 | 37 s | all outputs byte-identical |
| nozzle: test_nozzle | 0 (11 checks) | 16 s | — |
| nozzle: run_nozzle, calc_rerun, sector_loss | 0 | 459 s | every shared value identical (zero tolerance). The rerun adds `lateral_momentum_share` and `lateral_direction_deg` to 11 helix perturbation cases, which the committed JSON predates (T03 file, not edited) |
| ignition: tests, ignition.py | 0 | 101 s | identical except the runtime line |
| thermal: split.py | 0 | 292 s | identical at zero tolerance except the runtime |
| futures: futures.py, deps.py | 0 (V0 within 1 % of 20,760 t, ledgers close) | 752 s | identical except the runtime line |

## 8. Unresolved scientific barriers (ranked by effect on V4)

1. **Compression coupling.** V4 needs a driver-to-fuel coupling η_c/α of 0.5. Ablative implosions today reach a few percent. This
   is the largest gap in the design, and it is not declared as physics (D-22).
2. **Nozzle efficiency.** V4 closes only down to η_T 0.63. The best published figure (0.64) sits on the cliff, and the closure-coil
   0.74-0.79 is a vacuum-field upper bound with 13-14 RT e-folds per pulse. The test is D-21.
3. **Driver.** V4 needs 0.30 wall-plug efficiency at 0.025 kg/kW. The Atlas value (0.05 kg/kW) gives 199 kt.
4. **Warm radiator.** V4 needs 628 K components (TARGET) and a 0.5 kg/m² droplet sheet. Panels give 124 kt; today's 489 K parts don't close.
5. **Target launcher.** V4 needs 12-15 km/s at about 200 Hz for cryogenic D/³He targets at 1e5-1e6 g. No such launcher exists.
6. **D-³He ignition.** It has never been done. The D-T core route needs 43-144 kg of tritium per mission, and burn propagation from the
   core into D-³He at 1,000-3,000 g/cm³ is unmodelled.
7. **Dust at 0.016 c.** The answer depends on destination and heading (D-15, D-17). Every protective concept stays a candidate.
8. **Unbooked penalties.** Closure-coil structure and solid angle, skirt, launcher, tritium store: every V3-V5 mass is a lower bound.

## 9. Decisions requiring ApeDevil's approval

| ID | Question | Recommendation |
| --- | --- | --- |
| D-21 | Launch the bounded 2D MHD / hybrid-PIC campaign (about 3e4-2.5e5 core-hours, external allocation)? | Approve when an allocation exists. It is the cheapest test of the steepest lever (`D21_MHD_PIC_PROPOSAL.md`) |
| T05 baseline | Use V4 (42.9 kt, with its bands) as T05's preferred experimental configuration, with V0 and V5 as references? | Yes (`T05_HANDOFF.md`) |
| D-10 Stage B | Start the experimental Blender blockout once T05's Stage A is reviewed? | Owner's call after T05 Stage A |
| D-05 | Deployable warm wings: V4's reach a 10 km tip radius | Keep experimental only. They are the dominant visual |
| D-06 / D-15 / D-17 / D-18 | Braking through dust, destination, heading, sector replacement vs a Level C conductor | Keep open until a destination is chosen |
| Timeline T056 | How the story's runaway departure works for a drive that stops when injection stops | An owner story decision. The engineering offers no mechanism |
| Squash | Squash this branch onto `main` | Not yet: after review |
