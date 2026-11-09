# T06 assumptions register

Every scientific and fictional assumption T06 uses. Credibility: **A** ESTABLISHED, **B** PLAUSIBLE_FUTURE, **C** FICTIONAL_BREAKTHROUGH
(Atlas levels). Label: PUBLISHED / MODEL / EXTRAPOLATION / ASSUMPTION / TARGET / FICTIONAL / CANON (planning/HANDOFF.md vocabulary).
"Declared" means physics permits it but IGNITION would have to state that it happened, because nothing demonstrated comes close.

Status: GATHERING draft, 2026-11-09. T01-T04 results will replace Atlas-only rows.

## Inherited from FDP-1 and the four-burn study (not re-derived by T06)

| ID | Assumption | Value | Cred. | Label | Source |
| --- | --- | --- | --- | --- | --- |
| A-01 | Mission: four burns of 0.016 c, 6.0 y round trip | 4 x 4,797 km/s; 6.0 y | — | CANON (LOCKED) | `data/wayfarer_3d.toml` `[mission]` |
| A-02 | Exhaust velocity held at the four-burn optimum | 19,201 km/s | B | MODEL | S-FOURBURN, FDP-1 `mission.ve_km_s` |
| A-03 | Departure acceleration held | 0.0069 g | B | MODEL | FDP-1 `mission.a0_g` |
| A-04 | Target gain, optimistic tier | 3,000 (demonstrated 4.1, D-T); **not energy-consistent at 3,000 g/cm³** (needs η_c/α 1.68, T04 EARLY bound) | B in kind, declared in degree | ASSUMPTION | S-NIF-2025, scenario v1, T04 EARLY 1b85941 |
| A-05 | Compressed fuel density | 3,000 g/cm³ (NIF D-T about 600) | B | ASSUMPTION / EXTRAPOLATION | S-T06-NIF-DENSITY |
| A-06 | Pulsed nozzle efficiency | 0.79 (theory 0.79-0.86, simulated 0.34-0.70) | B | ASSUMPTION | S-MSFC-NOZZLE (UNVERIFIED), S-CASSIBRY-PMN |
| A-07 | Heavy-ion driver wall-plug | 0.45 FDP-1; 0.30 used by T06 as base (published 0.20-0.30) | B | ASSUMPTION / PUBLISHED | S-HIF-REVIEWS |
| A-08 | Recovery efficiency | 0.95 | B | ASSUMPTION | scenario v1 |
| A-09 | Payload (non-propulsion dry mass) | 990.2 t | — | CANON (mass_model) | FDP-1 NOTES |
| A-10 | Shield thickness set by crew dose (20 mSv/y, half to the drive) | — | A | PUBLISHED (ICRP) | FDP-1 config |
| A-11 | Radiator areal masses, optimistic | hot 3.0, warm 1.0 kg/m² (published practice 5-8) | B | ASSUMPTION | S-T06-RADMASS |

## Added by T06 (every one a TARGET, never a result)

| ID | Assumption | Value | Cred. | Label | Mechanism that would earn it | Source / ancestry |
| --- | --- | --- | --- | --- | --- | --- |
| A-12 | Gain set at the compression-energy bound G = 1,787 × η_c/α × (ρ/3,000)^(-2/3) | V3: 702 at 2,000 g/cm³ (η_c/α 0.3); V4: 894 at 3,000 (0.5) | B in kind, **declared** (D-T06-1) | TARGET | driver-to-fuel coupling at low adiabat; magnetisation removes the hot-spot requirement only | T04 EARLY 1b85941 |
| A-13 | The draft-1 chains (gain 6,000, density 6,000 g/cm³) | sensitivity only | — | WITHDRAWN as designs | violate the A-12 bound (η_c/α 2.66-5.33) | T04 EARLY |
| A-14 | Driver hardware halved | 0.025 kg/kW | B | TARGET | higher core flux swing, higher gradient | S-HIF-REVIEWS (3e7 kg for 5 MJ terrestrial) |
| A-15 | House load quartered | 0.025 % of fusion (T01 EARLY bottom-up: 0.003-0.014 %, at 81 GJ pulses) | B | TARGET | energy per target in the factory | T01 EARLY 57fe625 |
| A-16 | Warm loop 800 K | 800 K (T01 EARLY: split loop is 628 K equivalent at TARGET components) | B | TARGET, contested | MW SiC/GaN conversion at 800 K; FINEMET cores near 823-843 K Curie | S-NASA-SIC-500C, S-CORE-CURIE, T01 EARLY 57fe625 |
| A-17 | Liquid-sheet warm radiator | 0.5 kg/m² | B | TARGET | droplet or sheet radiator | S-MATTICK-LDR |
| A-18 | Thin refractory hot heat pipes (T06-NEW-1) | 1.5 kg/m² at 1,800 K | B | TARGET | thinner Mo-Re / C-C walls | S-T06-SP100, S-T06-RADMASS |
| A-19 | 3 GPa structural laminate (T06-NEW-2) | twice CFRP specific strength | B | TARGET / EXTRAPOLATION | CNT-reinforced composites | S-T06-CNTF-2024 |
| A-20 | Validated pulsed nozzle at the top of theory | 0.86, plume strike halved | B, **declared** (D-T06-2) | TARGET | 3D-optimised nozzle fields, validated pulsed test stands | S-MSFC-NOZZLE (UNVERIFIED), S-W7X-2025 |
| A-21 | Inductive recovery | 0.98 | B | TARGET | rep-rated flux pickup | S-DAEDALUS-1978 |

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
| A-28 | Recovery and nozzle efficiency treated as independent by the calculator | K3 and V4 are upper bounds until T03 gives a joint model (Atlas link VTX-02C conflicts VTX-03) |
