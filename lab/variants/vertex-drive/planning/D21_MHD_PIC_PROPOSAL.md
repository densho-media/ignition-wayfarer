# D-21: bounded 2D MHD / hybrid-PIC proposal for the closure-coil nozzle

| | |
| --- | --- |
| Kind | experiment proposal (research, NON-CANON) |
| Status | PREPARED, NOT LAUNCHED. The owner ruled on 2026-11-09: prepare the bounded 2D proposal, do not launch external HPC computations. Full MHD/PIC (D-09) stays not approved. |
| Decision | D-21 (from T03's D-T03-3); launching it needs a new owner approval |
| Basis | T03 study plan, `studies/nozzle/REPORT.md` §8, narrowed to 2D axisymmetric runs |
| Date | 2026-11-09 |

## Question

Does the forward closure-coil nozzle (VTX-03D) keep its thrust efficiency when the plasma is modelled self-consistently? Every number we
have now (η_T 0.74-0.79 at 10-15 E_p) comes from a vacuum-field, thin elastic shell, test-particle model. That model is an **upper bound**.
It has no diamagnetic response, Rayleigh-Taylor mixing, reconnection, detachment or velocity spread. Linear RT theory gives 13-14 e-folds
per pulse, so the bound could be far from the real value.

This is the steepest lever in the ship. Departure-mass elasticity to the nozzle efficiency is -2.9 at V1c (T06). V4 rises from 42.9 kt to
68.5 kt at η_T 0.740 and to 1,726 kt at the literature value 0.64; below 0.63 it does not close (`V4_nozzle_band`).

## Scope (bounded)

The proposal is narrower than T03's full plan:

- **Geometry**: 2D axisymmetric r-z only. No 3D and no helix cases, because D-01 found that clocking gives under 1° of shear and no
  efficiency gain.
- **Pulse**: the V1 pulse (80 GJ, 0.34 g, D/³He/⁴He/p, rms 21,600 km/s, self-similar). The V4 pulse is reached by scaling it.
- **Configurations**: the reference three-loop cup A; closure coils C at 10 E_p and C at 15 E_p.

| Run | Code class | Cases | Core-hours (EXTRAPOLATION) |
| --- | --- | --- | --- |
| 1. Validation | Hall MHD | diamagnetic cavity in a uniform field (analytic); Nagamine and Nakashima 0.65 momentum case | 2e3-2e4 |
| 2. Screening | 2D Hall / resistive MHD with Alfvén-speed limiting (PLUTO or Athena++) | A, C10, C15 | 3e3-3e4 |
| 3. Kinetic check | 2D hybrid PIC, kinetic ions and fluid electrons (HYBRID-VPIC or dHybridR) | A and C15 | 2e4-2e5 |
| **Total** | | 7 runs | **about 3e4-2.5e5 core-hours** |

That is 1-10 % of T03's full campaign (2-10 million core-hours). It still can't run in this container, so it needs an external
allocation: about 1-10 node-days on a 1,000-core partition.

## Physics settings (from T03)

- Two-temperature plasma, expanding adiabatically from a 1 m sphere.
- Coils as flux-conserving circuits, with inductances from `studies/nozzle/multipole.py`.
- Vacuum floor at or below 1e-6 of the shell density, with the Alfvén speed capped at c.
- Resistive eddy screens as thin conducting shells.
- Hall term on; no radiation transport.
- Domain 0-300 m × -600 to +60 m, cell size 0.1-0.25 m (below the ion gyroradius), run to 60 µs.

## Results that count (decided in advance)

| Outcome | Threshold | Consequence |
| --- | --- | --- |
| Shaping works | C15 η_T ≥ 0.70, with ≤ 2 % of the plasma on hardware | VTX-03D moves to SUPPORTED. V4's band narrows to 0.70-0.79. |
| Partial | 0.62 ≤ η_T < 0.70 | V4 grows beyond its 0.740 value of 68.5 kt, and has no solution below 0.63. The nozzle stays a candidate; a structure and stored-field trade is needed. |
| **Decisive negative** | C15 η_T < 0.62, or RT pushes more than 5 % of the plasma into the field region | V4 does not close (its cliff is 0.63), and the historical V1 class goes above about 40 kt (T03). Pulsed magnetic nozzles are ruled out as a mass lever; VTX-03D becomes CONTRADICTED. |

## Stop rules

- Stop after run 1 if the validation cases miss their reference values by more than 10 %.
- Stop after run 2 if A and C15 differ by less than the run-to-run scatter (≥ 0.02 in η_T); the kinetic check would then add nothing.
- Nothing from any run changes canon, the FDP-1 calculator or production geometry. The results update VTX-03D, D-21 and the V3-V5
  nozzle band only.

## What T00 needs to launch it

- An owner approval of D-21.
- An external allocation: a named machine, account and budget. Credentials would never go into the repository.
- One input deck per run, generated from `studies/nozzle/configs.py`. This is about a day of preparation; not done until approval.
