# T06 assumptions register

Every scientific and fictional assumption T06 uses. Credibility: **A** ESTABLISHED, **B** PLAUSIBLE_FUTURE, **C** FICTIONAL_BREAKTHROUGH
(Atlas levels). Label: PUBLISHED / MODEL / EXTRAPOLATION / ASSUMPTION / TARGET / FICTIONAL / CANON (planning/HANDOFF.md vocabulary).
"Declared" means physics permits it but IGNITION would have to state that it happened, because nothing demonstrated comes close.

Status: FINAL, 2026-11-09. Rows A-29 to A-36 carry the T01-T04 handoff values used in the final synthesis.

## Inherited from FDP-1 and the four-burn study (not re-derived by T06)

| ID | Assumption | Value | Cred. | Label | Source |
| --- | --- | --- | --- | --- | --- |
| A-01 | Mission: four burns of 0.016 c, 6.0 y round trip | 4 x 4,797 km/s; 6.0 y | — | CANON (LOCKED) | `data/wayfarer_3d.toml` `[mission]` |
| A-02 | Exhaust velocity held at the four-burn optimum | 19,201 km/s | B | MODEL | S-FOURBURN, FDP-1 `mission.ve_km_s` |
| A-03 | Departure acceleration held | 0.0069 g | B | MODEL | FDP-1 `mission.a0_g` |
| A-04 | Target gain, optimistic tier | 3,000 (demonstrated 4.1, D-T); **not energy-consistent at 3,000 g/cm³** (needs η_c/α 1.68, T04 EARLY bound) | B in kind, declared in degree | ASSUMPTION | S-NIF-2025, scenario v1, T04 EARLY 1b85941 |
| A-05 | Compressed fuel density | 3,000 g/cm³ (NIF D-T about 600) | B | ASSUMPTION / EXTRAPOLATION | S-T06-NIF-DENSITY |
| A-06 | Pulsed nozzle efficiency | calculator value is thrust efficiency η_T = η_mom² (T03); 0.791 only for closure-coil nozzle C at 15 E_p (ideal-model upper bound); literature η_T 0.30-0.64 | B | ASSUMPTION / MODEL | T03 HANDOFF 59244a9, S-CASSIBRY-PMN |
| A-07 | Heavy-ion driver wall-plug | 0.45 FDP-1; 0.30 used by T06 as base (published 0.20-0.30) | B | ASSUMPTION / PUBLISHED | S-HIF-REVIEWS |
| A-08 | Recovery efficiency | 0.95 | B | ASSUMPTION | scenario v1 |
| A-09 | Payload (non-propulsion dry mass) | 990.2 t | — | CANON (mass_model) | FDP-1 NOTES |
| A-10 | Shield thickness set by crew dose (20 mSv/y, half to the drive) | — | A | PUBLISHED (ICRP) | FDP-1 config |
| A-11 | Radiator areal masses, optimistic | hot 3.0, warm 1.0 kg/m² (published practice 5-8) | B | ASSUMPTION | S-T06-RADMASS |

## Added by T06 (every one a TARGET, never a result)

| ID | Assumption | Value | Cred. | Label | Mechanism that would earn it | Source / ancestry |
| --- | --- | --- | --- | --- | --- | --- |
| A-12 | Gain set at the compression-energy bound G = 1,787 × η_c/α × (ρ/3,000)^(-2/3) | V3: 1,171 at 2,000 g/cm³ (η_c/α 0.5); V4: 1,787 at 3,000 (1.0, the bound itself) | B in kind, **declared** (D-T06-1) | TARGET | driver-to-fuel coupling at low adiabat; magnetisation removes the hot-spot requirement only | T04 HANDOFF fd4ff3d |
| A-13 | The draft-1 chains (gain 6,000, density 6,000 g/cm³) | sensitivity only | — | WITHDRAWN as designs | violate the A-12 bound (η_c/α 2.66-5.33) | T04 EARLY |
| A-14 | Driver hardware halved | 0.025 kg/kW | B | TARGET | higher core flux swing, higher gradient | S-HIF-REVIEWS (3e7 kg for 5 MJ terrestrial) |
| A-15 | House load | final: 2.6e-5 of fusion (T01 advanced; 1.23e-4 conservative); chains used 0.025 % | B | TARGET | 0.6 MJ per pellet in the factory | T01 HANDOFF 1302708 |
| A-16 | Warm loop | final: 628 K equivalent (T01 advanced; 489 K conservative, no T06 ship closes); the K2 chain's 800 K is withdrawn | B | TARGET | MW SiC/GaN conversion; FINEMET cores near 823-843 K Curie | S-NASA-SIC-500C, S-CORE-CURIE, T01 HANDOFF 1302708 |
| A-17 | Liquid-sheet warm radiator | 0.5 kg/m² | B | TARGET | droplet or sheet radiator | S-MATTICK-LDR |
| A-18 | Thin refractory hot heat pipes (T06-NEW-1) | 1.5 kg/m² at 1,800 K | B | TARGET | thinner Mo-Re / C-C walls | S-T06-SP100, S-T06-RADMASS |
| A-19 | 3 GPa structural laminate (T06-NEW-2) | twice CFRP specific strength | B | TARGET / EXTRAPOLATION | CNT-reinforced composites | S-T06-CNTF-2024 |
| A-20 | Validated closure-coil pulsed nozzle at its ideal model | η_T 0.791 at 15 E_p, plume strike 0.065 (the chain's 0.86 and 0.01 are withdrawn) | B, **declared** (D-T06-2) | TARGET | closure coils (T03-NEW-1), validated pulsed test stands | T03 HANDOFF 59244a9 |
| A-21 | Inductive recovery | 0.98 in K3; immaterial (elasticity -0.04; T03 extraction 0.13 % of fusion) | B | TARGET | rep-rated flux pickup | S-DAEDALUS-1978, T03 HANDOFF |

## Fictional (IGNITION) assumptions

| ID | Assumption | Cred. | Label | Note |
| --- | --- | --- | --- | --- |
| A-22 | Fiji lattice: amplification up to x30 of an applied seed field, slow (temperature-set) response, flux-geometry stabilisation | C | FICTIONAL (canon card) | no energy creation, no heat sink, no fast actuation, never bends light; the calculator gives it no numeric credit; T06 adds nothing (D-07) |
| A-23 | Fiji activation and "field lock" at drive start | C | CANON (WORKING) | `power.black_start` steps 7-8: the lattice enters its activation range after first fusion and a field lock develops; used in HISTORY_PROPOSALS.md as narrative only |
| A-24 | Optical conditioning of the lattice | C | CANON (WORKING) | `propulsion.manifold.optical_control`; light conditions the lattice, fields never bend the beam (LOCKED boundary) |

## Method assumptions

| ID | Assumption | Effect |
| --- | --- | --- |
| A-25 | The no-interaction null for combined chains is the product of single mass ratios (the mass feedback compounds), not their sum | the sum is shown beside it so double counting is visible |
| A-26 | The 1 g test scales drive, power, radiator, nozzle and light-structure specific masses by one factor; shield, tanks, payload unscaled | a 64-fold reduction is a lower bound on the specific-mass breakthrough, not a design |
| A-27 | IGNITION timeline unknown in this session: the drive-reader agent named by CLAUDE.md is not available here, and T06 did not fall back to direct Drive reads | eras carry no dates; HISTORY_PROPOSALS.md is unanchored until D-T06-3 |
| A-28 | Recovery and nozzle efficiency treated as independent by the calculator | T03: recovery extracts 0.13 % of fusion, so the double count is below 0.1 % of mass |
| A-29 | T02 protection booked as +250 t payload (skirt 22-90 t, central 56; LiH shoes 193 t) | not scaled with the drive; solid angle not booked (X-T06-4) |
| A-30 | Stored nozzle field 15 E_p (T03) through `nozzle_field_energy_ratio` | 10 E_p gives η_T 0.740 instead |
| A-31 | Gain at the bound everywhere; density searched 500-3,000 g/cm³ | the frontier is the lightest ship per coupling, not a design point |
| A-32 | Driver efficiency 0.30 (published band) for V3/V4; 0.45 shown as V3o/V4o | T01 split runs at 0.25/0.30/0.45 |
| A-33 | Five penalties without a calculator path are not booked (launcher, closure-coil and shoe solid angles, eddy screens, ignitor/tritium) | every final mass is a lower bound (F-T06-7) |
