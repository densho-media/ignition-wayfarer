# Vertex 2.9: B2d collective plasma and magnetic nozzle verification

| Field | Value |
| --- | --- |
| Kind | study (numbers only, no geometry) |
| Status | ACTIVE, research, not canon |
| Question | Does the B2d plugged near-burn nozzle keep its 2.8 credited cosine (0.906) and meet SR-26F (<= 1 % of each pulse in the thin-particle escape regime) when the plasma and field interact self-consistently? |
| Model base | Vertex 2.8 (lab/studies/vertex-closure/vertex-2-8, commit 17d5be1): B2d plug R3 m 5 T at z -6, main R10 m 1.5 T, burn z 9, E_B/E_p 150; mission28 ledger, JUSTIFIED dust, 200 m spine |
| Owner brief | 2026-11-17 13:26Z, decisions Q1-Q5 |
| Open owner questions | O1-O3 below |

Nothing here changes Blender geometry, canonical parameters, workbooks or lore. No Drive writes. B2d and Compact Vertex A+ stay research
references. Nothing in src/, tests/, tools/, godot/, web/ or CI reads this folder.

## Owner decisions this study carries (2026-11-17 13:26Z)

- Q1 min(collective, single-particle) cosine: a provisional screening rule, not a law.
- Q2 SR-26F restated as an open requirement (not an achieved capability, explicitly speculative).
- Q3 B2d a conditional research reference at ~6,154 t with the 5 % delta-v reserve; 4.6 kt canon target unchanged.
- Q4 He-3 supply as a PROPOSED Economy/Technology item: `HE3_ITEM.md` (local draft, not in Drive).
- Q5 this study.

## 1. Capability audit (requirement 1)

- No hybrid-PIC code is installed or installable as a validated package here (no network-free install of e.g. a published hybrid code
  with its test suite). Machine: 4 cores, 15 GB RAM. Vertex 1.4 estimated ~11 core-h for a 2D hybrid PIC and ~12,500 core-h / 1 TB for 3D:
  3D at useful resolution is out of reach on this machine.
- So the study wrote a **reduced** 2D axisymmetric hybrid (`hybrid.py`, numpy/scipy/numba): kinetic relativistic ions (Boris push in r-z
  with v_theta), massless quasi-neutral electrons, ideal + weak resistive Ohm's law, poloidal field only (psi = r A_theta), free-space
  boundary by the loop Green's function, coil reaction from the plasma field at each coil. Ions below the dense-plasma cutoff n_c are test
  particles in the instantaneous field. Escaping ions continue as test particles in the exact coil field to a 150 m box.
- Not in the model: Hall-generated B_theta (whistler dynamics), electron inertia and kinetics, any non-axisymmetric mode, coil current
  response, radiation. **This is an intermediate tool, not a validated hybrid-PIC code.**

## 2. Verification and benchmarks (requirements 2, 8)

| Check | Result | Verdict |
| --- | --- | --- |
| B1 field solver: current ring vs exact loop field | 0.04-0.17 % (dx 0.5), 0.00-0.04 % (dx 0.25); zero boundary 3-12 % | PASS |
| B2 single-particle limit, A (E_B/E_p 1e5) | kappa 0.878, forward 2.48 %, on ship 1.94 % (2.8 traces 0.884 / 2.4 % / 2.0 %) | PASS |
| B2 single-particle limit, B2d | kappa 0.947, forward 2.91 % (2.8: 0.961 / 2.9 %) | PASS |
| B3 magnetic cavity, uniform 1 T, R_B 8 m | stops at 8-10 m and rebounds; energy closure -5 % at peak compression, -11 % after rebound (n_c 1e17); +54 % at n_c 1e16, -36 % at n_c 1e18 | cutoff-dependent |
| B4 one coil, E_B 5 E_p, 30/50/70 deg (Nagamine & Nakashima ~0.65 peaked near 50 deg) | 0.59 / 0.53 / 0.28, energy closure 16-28 % | magnitude within ~20 %, peak angle wrong: FAIL |
| Energy closure, B2d | 5-37 % lost (mostly numerical flux relaxation outside the dense region) | FAIL as a validated result |
| Momentum closure | dominated by the test-particle region, whose reaction is not booked on the coils (0.1-0.9 of p0) | diagnostic only |
| Convergence dx 0.5 -> 0.35, 20k -> 40k particles, seed | kappa 0.731 -> 0.711, 0.735, 0.735; energy closure not improved by dx | particle noise small; the error is structural |

Two defects were found and fixed on the way: the ion push used an inductive E_theta inconsistent with its own Hall field (energy was
created, +100-800 %), and first-order flux advection diffused too much; after the fixes the ion-side work equals the field-side J.E
exactly, and the remaining error sits in the dense/tenuous cutoff.

## 3. B2d results (requirements 4-6)

All runs: 20k particles, dx 0.5, 6 us (`scan_conv.json`, `scan_all2.json`). E_space = energy that reached the box.

| Run | kappa | aft cos | forward (pulse) | forward on ship | E_space | energy err |
| --- | --- | --- | --- | --- | --- | --- |
| n_c 3e16 | 0.848 | 0.938 | 0.02 % | 0.01 % | 0.88 | 0.19 |
| n_c 1e17 | 0.731 | 0.937 | 0.36 % | 0.12 % | 0.66 | 0.34 |
| n_c 3e17 | 0.789 | 0.947 | 0.29 % | 0.24 % | | 0.25 |
| n_c 1e18 | 0.905 | 0.966 | 0.70 % | 0.65 % | 0.91 | 0.09 |
| sensitivities at n_c 1e17 (pulse x0.5/x2, field x0.7, plug z-9 / R2, burn z7/z11, b 0.99, r0 2 m, Te 10 keV) | 0.73-0.77 | 0.93-0.95 | 0.13-0.70 % | 0.07-0.25 % | | 0.28-0.34 |
| the same at n_c 1e18 | 0.87-0.94 | 0.95-0.97 | 0.47-0.96 % | 0.42-0.86 % | | 0.05-0.12 |

- Physical inputs move the cosine by about +-0.03; the unphysical cutoff moves it by 0.2. The cutoff, not the physics, dominates.
- Loss-corrected (lost energy assumed to leave like the rest): kappa 0.90 (3e16), 0.90 (1e17), 0.95 (1e18), consistent with the 2.8 credit
  0.906. The cosine is not where B2d fails.
- Coil impulse: shared 13 % plug / 87 % main at n_c 1e17 (2.8: 18 / 79 %). Aft ion energy medians 2.7-5.8 MeV (p) and 5.9-8.8 MeV (alpha)
  from a born 8.2 MeV: the cavity shares energy between species (charge-weighted).

## 4. SR-26F test (requirement 5)

SR-26F (restated): no more than 1 % of each pulse enters the thin-particle escape regime before the plug. In the traced single-particle
limit that regime sends 2.9 % of the energy forward, so SR-26F means forward <= ~0.03 % of the pulse. The hybrid gives forward 0.02-0.96 %,
i.e. an equivalent tail share of 0.7-33 %: **met in 1 of 26 B2d runs** (n_c 3e16, the case with the most plasma held collectively and a
19 % energy error). Forward escape exceeds the requirement by 4-33x in the other 25.

## 5. 3D (requirement 7): analytic flute screen (`instab.py`), not a simulation

Magnetic Rayleigh-Taylor (flute) modes on the decelerating cavity edge grow sqrt(l) e-folds; large-Larmor-radius stabilisation leaves modes
up to l ~ R / rho_i. For B2d: 3.7-7.4 e-folds (x40-x1,600) at the 3-5 m cavity edge, 6-9 at 14 m. A seed asymmetry of 0.06-2.5 % reaches
order unity, so a 2D axisymmetric result cannot stand for the 3D pulse; flutes could open channels through the plug and raise the forward
stream. New implied requirement: drive and pellet symmetry better than ~0.1-1 % per pulse, untested.

## 6. Mission ledger (requirement 9) (`mission29.py`, 5 % delta-v reserve on every case)

- 2.8 reference with reserve: 6,154 t (kappa 0.906, forward 2.9e-4).
- Hybrid pairs: 1 of 26 closes (n_c 3e16: 6,519 t, He-3 2,256 t). The other 25 have **no heat-passing closure**: the forward stream on the
  ship overloads stern/coil heat. A forward beam dump does not rescue them (lightest 9.5-27 kt, still heat-failing).
- Loss-corrected: 5,798 t (3e16); no closure at 1e17 or 1e18 (forward 0.18 %, 0.71 %).
- Grid: closure inside 7 kt needs kappa >= ~0.85 **and** forward on ship <= ~3e-4; at 1e-3 the best is 8.4 kt.
- **Decision gate: B2d is not shown to stay within the 7 kt envelope. It fails on the forward stream, not on the cosine. No speculative
  assumption was added to compensate.**

## 7. Other unresolved requirements stay visible (requirement 10)

VBC chain ignition (SR-22), isotropic-radiation suppression SR-26A (x0.01), near-complete burnup (b 0.99), He-3 supply (1.9-2.3 kt, no
canon source, storage volume ~8x the BODY-C3 cryostat study, `HE3_ITEM.md`), spacecraft protection (JUSTIFIED dust, 200 m spine), and now
SR-26F failing in the reduced hybrid plus the flute-symmetry requirement.

## Owner questions

- O1 Next step for SR-26F: (a) a validated hybrid-PIC code run off this machine (2D first, then 3D, ~10^4 core-h), (b) a different
  forward-stream architecture (closed plug side, forward magnetic dump, plasma-facing stern shield), or (c) accept that B2d stays a
  conditional reference with SR-26F open.
- O2 Keep the min-cosine screen (Q1)? The hybrid's loss-corrected cosine (0.90-0.95) agrees with the 2.8 credit, so the screen is not
  contradicted.
- O3 He-3 item: the two questions in `HE3_ITEM.md` (canonical source; storage-volume conflict to S&E).

## Files

`hybrid.py` model; `bench_field.py` B1; `scan.py` benchmarks, convergence and sensitivity (`scan_*.json/.log`); `instab.py` flute screen;
`mission29.py` ledger (`mission29.json/.log`); `HE3_ITEM.md` proposed Economy/Technology item.
