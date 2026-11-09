# T04 handoff: fusion ignition, target design and radiation conversion

| | |
| --- | --- |
| Thread | T04, fusion physics and target engineering |
| Date | 2026-11-09 |
| Status | DONE (owner question D-T04-1 open; the next experiment, a 1-D burn calculation, is not started) |

## A. Mission and scope

- Investigated (prompt section 3):
  1. Magnetised targets: B R requirement for 14.7 MeV protons; effect on hot-spot rhoR, not on burn rhoR or the gain ceiling.
  2. Reliable D-3He ignition: ideal-ignition temperature, 0-D hot-spot boundary (validated on D-T), hot-spot energies, gain ceiling.
  3. D-T spark: as a booster core inside the fuel (energy, 14.1 MeV escape, tritium per pulse and per mission).
  4. Multilayer targets: layering scale per design; adiabat alpha as the ceiling's divisor (qualitative).
  5. Tamper-enhanced burnup: new tamper-inertia case beside the Atlas liner table.
  6. Geometries: central vs fast ignition, two-stage, lower-density spheres (cylindrical and shock ignition: UNKNOWN, not modelled).
  7. Hydrogen low gear: mission phases and times (D-04 argument).
  8. Isotopic tailoring: propulsive value bounded by the escaping neutron share.
  9. Diagnostics and safe stop: pulse timing, dud ledger, asymmetric impulse; plus the target-in-flight problem found on the way.
  10. Engineering vs physics per need, and the explicit breakthrough (REPORT.md section 6, D-T04-1).
- Deliberately excluded: radiation-hydrodynamic or burn simulation (beyond the scope of a calculator adapter; proposed as the next
  experiment); neutron transport (T02); target-factory energy (T01); nozzle response to debris (T03); any calculator change.

## B. Repository state

| Item | Value |
| --- | --- |
| Starting commit (Phase 1 base) | `8de3ffa189b47ce9a1212b550b7ea75f8c36314a` |
| Branch | `claude/project-thread-9hxayw` |
| Resulting commit | see `/mnt/project-files/vertex/threads/T04.md` (early package `1b85941`; this handoff the commit after it) |
| Changed paths | `lab/variants/vertex-drive/studies/ignition/` only: `ignition.py`, `targets.py`, `tests/test_ignition.py`, `results/ignition.json`, `results/IGNITION.md`, `EARLY.md`, `REPORT.md`, `HANDOFF.md`, `registry_proposal.toml` |
| Rerun | `python3 lab/variants/vertex-drive/studies/ignition/ignition.py` (about 2 min on 4 cores; exit 0 means the Atlas cliffs and liner table are reproduced); `python3 lab/variants/vertex-drive/studies/ignition/tests/test_ignition.py` (seconds); `--quick` runs the pure-model cases only |

## C. Research findings

### Published evidence
- D-T target gain about 4.1 (S-NIF-2025, SECONDARY_VERIFIED).
- Minimum H_B 7.3 (D-T), 51 (D-3He) g/cm2; isochoric D-T ignition T > 8 keV, rhoR > 0.25 g/cm2 (S-T04-ATZENI-2004, SECONDARY_VERIFIED).
- Fast-ignition energy ~ rho^-1.85, optimum hot spot about 0.6 g/cm2 (S-T04-ATZENI-1999, SECONDARY_VERIFIED).
- D-3He pellets with a D-T ignitor: fuel gain about 500 at rhoR_DT 3 / total 14 g/cm2; the implosion follow-up found pre-ignition and a
  gain of about 3; later fast-ignition work about 100 below 10 MJ (S-T04-NAKAO-1992, SECONDARY_VERIFIED, abstracts only).
- Magnetised ignition benefit above B R about 0.6 MG cm, saturating near 1.0; MagLIF 0.4-0.5 (S-T04-MAGLIF-BR, SECONDARY_VERIFIED).
- Spin polarisation raises reactivity up to 1.5x (S-T04-POLARISED, UNVERIFIED).

### Calculated results
- Atlas reproduced: cliffs 1,257 / 705 / 581 (0.00 %), liner table exact (`ignition.py`, cases cliff_V0..V2, liner_reproduction).
- Compression ceiling (case compression): eps_F(D-3He) 132 MJ/g at 3,000 g/cm3, 64 at 1,000; ceiling 1,787 eta_c/alpha at 3,000 g/cm3;
  FDP-1's gain 3,000 needs eta_c/alpha 1.68; V1 cliff needs 0.41 (3,000), 0.32 (2,000), 0.26 (1,500), 0.20 (1,000), 0.13 (500 g/cm3).
- V1 gain cliff vs density: 705 / 705 / 710 / 714 / 719 at 3,000 / 2,000 / 1,500 / 1,000 / 500 g/cm3; departure at gain 3,000: 10,416 /
  12,450 / 15,648 / 23,869 / 64,208 t (cases cliff_V1_rho).
- Consistent frontier (gain capped at the ceiling, V1): at eta_c/alpha 0.3, 3,000 g/cm3 does not close; 1,500 closes at 96,631 t; 1,000
  at 59,477 t; 500 at 92,852 t; at 0.2 only 500 g/cm3 closes (155,284 t) (cases frontier).
- H_B: calculator 44.2 g/cm2 at 100 keV; V1 departure 10,959 t at the published 51, 11,828 t at the D-T-matched shape, 9,476 t polarised;
  the cliff stays 705 within the bisection resolution.
- Hot spot (case hotspot): 0-D D-T minimum 0.17 g/cm2 at 8 keV; D-3He 1.97 g/cm2 at 50 keV (11.5x); D-3He ideal ignition above 33 keV,
  best heating/bremsstrahlung 4.1 at 103 keV (D-T 27); 14.7 MeV proton range 6.0 g/cm2 at 100 keV.
- D-T core (case spark): rhoR_DT 2-3 g/cm2 -> 0.28-1.27 MJ, 3.4e-6 to 1.6e-5 of yield, escaping 14.1 MeV 3.3e-8 to 1.6e-7 of fusion,
  tritium 43-144 kg loaded and 9.5-43 kg burned per mission.
- Two-stage (case staged): 26-52 t tritium per mission; 0.22-0.45 % of fusion as outside 14.1 MeV neutrons.
- Tamper inertia (case liner): best ve gain +1.15 % at rhoR 90 (k = 1, mu 0.03), +10.7 % at rhoR 1 (mu 0.18); k = 0.5: +0.34 % / +3.0 %.
- Target in flight (case in_flight): at 400 m/s, 22.9 targets in the burn sky, next at 1.88 m, 2.1 kJ/cm2 X-rays; one-in-sky needs 9.17 km/s.
- Low gear (case low_gear): escape spirals 0.5-2.1 days at 0.0069 g; mu = 3 halves them; idle vessels 667 t at V1 departure.

### Engineering extrapolations
- D-3He hot spot about 6.9 g/cm2 at 50 keV after a 3.5x dynamics factor calibrated on D-T fast ignition; confirm with a 1-D burn code.
- Proton B R threshold 1.2 MG cm, saturation 2.0 (D-T values scaled by Larmor radius); confirm with a magnetised burn calculation.
- Present ablative implosions reach driver-to-fuel coupling in the percent range: engineering judgment, not sourced (UNKNOWN as a number).
- 14.1 MeV removal opacity 0.05 cm2/g in D-3He (half the 2.45 MeV value).

### Fictional assumptions
- Canon Fiji card used only as in the Atlas (no numeric credit). Level C option named, not assumed: a compression aid delivering
  0.4-1.7x the driver energy into the fuel each pulse (D-T04-1, would be a new Fiji property under D-07).

### Unknowns
- Burn propagation from a D-T core into D-3He at 1,000-3,000 g/cm3 (needs a burn calculation).
- Achievable eta_c and alpha for fuel-only targets at these densities (no published scheme found).
- Survival of spin polarisation through compression; polarised He-3 at target scale.
- Cylindrical and shock-ignited D-3He targets (no data found).
- Target-factory energy per target (T01).

### Negative results
- FDP-1's gain 3,000 at 3,000 g/cm3 is not reachable by compression (eta_c/alpha 1.68 > 1).
- Central (isobaric) D-3He hot spot: larger than the fuel ball (0.36 vs 0.30 mm), 76 MJ: infeasible.
- Two-stage target: 26-52 t tritium per mission; rejected.
- Tamper: below +1.2 % ve at the mission rhoR even with inertia; D-02 holds within about 1 %.
- Isotopic layers in the target: propulsive value at most the 5.5e-6 escaping neutron share.
- FDP-1's 400 m/s injection: the next target is inside the previous pulse.
- Hydrogen low gear: no phase gains more than about a day.

## D. Quantitative effects

| Quantity | Value | Unit | Uncertainty / range | Label | Source |
| --- | --- | --- | --- | --- | --- |
| Gain ceiling at 3,000 g/cm3 | 1,787 x eta_c/alpha | 1 | b 0.64-0.75 (H_B band) | MODEL | case:compression |
| eta_c/alpha for V1 cliff | 0.41 / 0.20 / 0.13 | 1 | at 3,000 / 1,000 / 500 g/cm3 | MODEL | case:cliff_V1_rho |
| eta_c/alpha for FDP-1 gain | 1.68 | 1 | | MODEL | case:compression |
| Minimum compression energy, FDP-1 target | 45.6 | MJ | alpha = 1 floor | MODEL | case:compression |
| V1 departure at gain 3,000, 1,000 g/cm3 | 23,869 | t | | MODEL | case:cliff_V1_rho |
| V1 consistent (eta_c/alpha 0.3), best | 59,477 | t | 1,000 g/cm3 | MODEL | case:frontier |
| D-3He hot spot | 6.9 at 50 | g/cm2 at keV | 0-D 1.97; range x0.5-x2 band in IGNITION.md | EXTRAPOLATION | case:hotspot |
| D-3He ideal ignition | >= 33 | keV | | MODEL | case:hotspot |
| D-3He hot-spot energy | 1.1 / 10 | MJ | at 3,000 / 1,000 g/cm3 | EXTRAPOLATION | case:hotspot |
| B R for protons | 1.2-2.0 | MG cm | threshold-saturation | EXTRAPOLATION | S-T04-MAGLIF-BR |
| Tritium per mission (D-T core 2-3 g/cm2) | 43-144 | kg | loaded; 27 % decays | MODEL | case:spark |
| Escaping 14.1 MeV share (core 3 g/cm2) | 1.6e-7 | 1 | kappa 0.05 cm2/g ASSUMPTION | MODEL | case:spark |
| X-ray escape share | 1.15 | % | | MODEL | S-FDP1 |
| Debris mean energy | 2.4 | MeV/u | rms 21,600 km/s, edge about 27,900 | MODEL / ASSUMPTION | EARLY.md |
| One-target-in-sky injection | 9.2 / 4.6 | km/s | V0 / V1 | MODEL | case:in_flight |
| H_B (calculator, 100 keV) | 44.2 | g/cm2 | published minimum 51 | MODEL / PUBLISHED | case:hb |
| Tamper-inertia ve gain at rhoR 90 | +0.3 to +1.2 | % | k 0.5-1 | EXTRAPOLATION | case:liner |
| Idle H2 vessels | 667 | t | V1 departure | MODEL | S-convergence V1_keep_idle_H2 |
| Required gain (V1 cliff) | 705 | 1 | | TARGET | case:gain_threshold |

## E. Model and geometry implications

- The V1/V2 masses (10.4 / 9.3 kt) are conditional on a gain the compression bound does not allow at 3,000 g/cm3. A consistent V1 is a
  heavier ship with larger, slower pulses: X-ray stand-off 130 m (1,000 g/cm3) or 259 m (500), instead of 43 m. T05 must not draw V1's
  43 m burn as settled. ENGINEERING_SUPPORTED by the calculator, conditional on eta_c.
- New hardware for T05 (REPORT.md section 8): 4.6-9.2 km/s target launcher on the bore axis (PARAMETRIC_PLACEHOLDER); fast-ignitor beam
  line (PARAMETRIC_PLACEHOLDER); tritium store in the equipment module (CONCEPTUAL_ILLUSTRATION); seed-field coil only if VTX-01A.
- Remove: the H2 low-gear feed if D-04 removes it.

## F. Dependencies

| Needed from | What | Status |
| --- | --- | --- |
| T01 | target-factory energy per target, driver limits | not received; Atlas house fraction used |
| T02 | shield limits on neutron share | not received; neutron share is tiny either way |
| T03 | what debris the nozzle takes | not received; Atlas nozzle efficiency 0.79 used |
| T00 | none | |

## G. Decisions

- Existing register: D-02 amended (proposal in `registry_proposal.toml`: holds within about 1 % with tamper inertia). D-04: argument
  delivered, recommendation remove; owner decides. D-07: untouched; the Level C option would fall under it. D-08 not touched.
- Proposed: **D-T04-1** (owner): accept compression-consistent targets (recommended) or declare a Level C compression aid. **D-T04-2**
  (technical): no mission phase needs the low gear.
- A recommendation is not an owner approval.

## H. Validation

- `atlas.py validate`: 34 records, 24 sources, 29 links, 12 decisions, 0 errors. Atlas tests OK; FDP-1 tests (45) OK; four-burn tests (18)
  OK; `studies/ignition/tests/test_ignition.py` 7 tests OK; `ignition.py` exit 0 (cliffs and liner table reproduced).
- Ledger: every `_pulse` ledger used sums to fusion to 1e-9 (test). The consistent-frontier case at 1,000 g/cm3 and eta 0.2 did not
  converge (FDP-1 integration diverged near the cliff); reported as "no".
- Model limitations: REPORT.md section 10.

## I. Integration instructions for T00

1. Bring in `studies/ignition/` as is (owned folder; nothing outside it changed).
2. `registry_proposal.toml`: add sources S-T04-*, records T04-NEW-1..5 (assign VTX-01E.. and VTX-01F.. or the next free IDs; T04-NEW-5 as
   CONTRADICTED), apply the [revise.*] appends to VTX-01, 01A, 01D, 04A, 04B, the D-02 amendment, and D-T04-1/2.
3. Proposed generation change: none to V1/V2 values; add a reported band "V1 at compression-consistent gain" (case frontier) and a
   published-H_B band. A calculator change (capping the optimistic gain at the ceiling) would be a shared-calculator change needing
   ApeDevil's approval.
4. Conflicts: if T01 credits V1's 10.4 kt as achievable, it conflicts with T04 section E; deciding test: eta_c/alpha needed at the
   density T01 assumes (`eta_needed` in `ignition.py`).
5. Re-run after integrating: `atlas.py validate`, Atlas tests, FDP-1 and four-burn tests, `ignition.py` (exit 0).

## J. Recommended next experiment

1-D radiation-hydrodynamic burn of a fast-ignited, D-T-cored fuel-only D-3He sphere at 1,000 and 3,000 g/cm3: burn propagation, burn
fraction against b = rhoR/(rhoR + H_B), and ignitor energy. It replaces the 0-D boundary and its 3.5x calibration and decides whether the
D-T core route works. Method: a small Lagrangian code in `studies/ignition/` or an open 1-D ICF code; output: burn fraction and yield per
ignitor energy; cost about one thread-week; thread: a follow-up T04 (no MHD/PIC, so not D-09).
