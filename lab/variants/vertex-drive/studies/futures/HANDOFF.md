# T06 handoff: technology convergence and IGNITION technology history

| | |
| --- | --- |
| Thread | T06, technology convergence and IGNITION technology history |
| Date | 2026-11-09 |
| Status | DONE (history unanchored to the IGNITION timeline: drive reader not available, A-27 / D-T06-3) |

Research only, not canon. Nothing here changes `data/`, `src/`, Drive, production Blender or the Atlas registry.

## A. Mission and scope

- Investigated (planning/T06-CONVERGENCE.md):
  1. Convergence chains K1-K5 (recirculating power, thermal, nozzle, compression, structure): mechanisms, link status, single and
     combined FDP-1 solves, combined against summed and multiplied (CONVERGENCE.md §4-5).
  2. Steepest parameters: elasticities at V1c, downside cases, the exhaust-velocity gate (§6).
  3. Mission ambitions: four 0.016 c burns, LOCKED 6.0 y, 1 g, 1.5 g, as MET / MET ONLY ABOVE / NOT MET (§7).
  4. Energy consistency of every generation under T04's gain-compression bound, and a frontier over coupling and density (§1, §3).
  5. Final synthesis with all T01-T04 corrections together, per-thread attribution and unbooked penalties (§0, §2, §3).
  6. Which breakthroughs IGNITION would have to declare (§8).
  7. Roadmap (ROADMAP.md), dependency matrix (DEPENDENCY_MATRIX.md/.json), assumptions (ASSUMPTIONS.md), non-canon history
     (HISTORY_PROPOSALS.md), generation and registry proposals.
- Deliberately excluded: dating the eras (IGNITION timeline unread, A-27); the ³He supply economy; any full MHD/PIC (D-09 not approved);
  any change to Fiji (D-07); replacing the canon four-nozzle drive (D-08); calculator changes (proposed to T00 as X-T06-1..4 instead).

## B. Repository state

| Item | Value |
| --- | --- |
| Starting commit (Phase 1 base) | `8de3ffa189b47ce9a1212b550b7ea75f8c36314a` |
| Branch | `claude/project-thread-pv2pie` |
| Resulting commit | the commit that adds this file (pushed; hash in `/mnt/project-files/vertex/threads/T06.md`) |
| Changed paths | `lab/variants/vertex-drive/studies/futures/` only |
| Rerun | `python3 lab/variants/vertex-drive/studies/futures/futures.py` (about 9.5 min on 4 cores; exits 0 only if V0 is within 1 % of 20,760 t and every ledger closes), then `python3 lab/variants/vertex-drive/studies/futures/deps.py` (seconds) |

Files: `futures.py`, `deps.py`, `results/futures.json`, `results/CHAINS.md` (generated), `CONVERGENCE.md`, `ROADMAP.md`,
`DEPENDENCY_MATRIX.md`, `DEPENDENCY_MATRIX.json`, `ASSUMPTIONS.md`, `HISTORY_PROPOSALS.md` (NON-CANON), `generations_proposal.toml`,
`registry_proposal.toml`, `EARLY.md` (superseded early record), this file.

## C. Research findings

### Published evidence
- NIF high-convergence implosions: fuel density about 500-800 g/cm³ (S-T06-NIF-DENSITY, UNVERIFIED snippet).
- CNT fibres with dynamic strength up to 14 GPa (S-T06-CNTF-2024, UNVERIFIED).
- SP-100 Mo-13Re lithium heat pipes (S-T06-SP100); space-radiator specific masses 5-8 kg/m² in practice (S-T06-RADMASS), so FDP-1's
  1.0/3.0 kg/m² are already beyond practice.
- All other evidence is inherited from the Atlas registry and the T01-T04 handoffs.

### Calculated results
- Final ships (generations_proposal.toml, `case:proposals`): **V3** η_c/α 0.5, 2,000 g/cm³, gain 1,171: **37,895 t**; **V4** ideal
  limit, 3,000 g/cm³, gain 1,787: **17,907 t**; at driver 0.45: 24,143 t and 14,314 t.
- Frontier (`case:integrated`): T06 package 362 / 110 / 37.9 / 17.9 kt at coupling 0.2 / 0.3 / 0.5 / 1.0; Atlas engineering none /
  1,747 / 368 / 68.4 kt. At nozzle 10 E_p (0.740) 655 / 189 / 57.8 / 22.7 kt; at literature 0.64 ≥110 kt.
- Attribution (`case:attribution`, coupling 0.5, start 13,144 t): T01 628 K alone 25,141 t; T03 15 E_p 18,865 t; all six 45,786 t.
- V0 reproduces 20,760 t; energy ledger closes in every combined solve.
- Floor (`case:floor`, V4, specific masses ×1e-4): 5,665 t.
- 1 g on V4: 5,084-fold specific-mass reduction, 30,155 t, 3,605 TW; 1.5 g no solution (`case:one_g`).
- Elasticities at V1c: nozzle -2.87, warm -1.74, driver -0.74, gain -0.63, recovery -0.04 (`case:elasticities`).
- ve gate η_jet·b ≥ 0.5236 sets the nozzle cliff near 0.53 (`case:ve_gate`).

### Engineering extrapolations
- Convergence is sub-multiplicative in mass because payload + propellant + tanks form a floor; its real effect is on closure under the
  bound. Confirm or refute: rerun with calculator extensions X-T06-1..4.
- Gain lowers recirculating power, not the fusion power a thrust needs; the prompt's example chain is mis-ordered.

### Fictional assumptions
- Canon Fiji card only: ×30 amplification of a slow seed field, flux stabilisation; no energy creation, heat sink, fast actuation or
  light bending. No numeric credit (A-22..A-24). No Level C proposal is made by T06.

### Unknowns
- Achievable compression coupling for heavy-ion direct drive of D-³He (T04: per-cent range today).
- Closure-coil nozzle validation (T03: 0.791 is an ideal-model upper bound).
- Dust survival at 0.016 c (T02).
- IGNITION timeline dates (A-27).

### Negative results
- Atlas V0-V2 are not energy-consistent (η_c/α 1.68 needed).
- K4 dense-compression chain and grand endpoint withdrawn; 800 K warm loop, nozzle 0.86, plume ÷2 withdrawn.
- At 489 K (present components) no T06 ship closes; at coupling 0.2 the Atlas engineering package never closes.
- Recovery efficiency does not matter (0.4 % for 0.90→0.98).
- 1 g and 1.5 g are not met.

## D. Quantitative effects

| Quantity | Value | Unit | Range | Label | Source |
| --- | --- | --- | --- | --- | --- |
| V3 departure | 37,895 | t | 43,266 for 6.0 y | MODEL | `case:proposals` |
| V4 departure | 17,907 | t | 19,154 for 6.0 y | MODEL | `case:proposals` |
| V3 fusion power / rate / yield | 31.5 / 173 / 43.5 | TW / Hz / t TNT | | MODEL | same |
| V3 loops r | 56 / 97 / 168 | m | | MODEL | same |
| V3 warm wing tip | 8,278 | m | 3,012 at driver 0.45 | MODEL | same |
| V4 fusion / rate / yield | 14.9 / 185 / 19.2 | TW / Hz / t TNT | | MODEL | same |
| V4 loops r | 37 / 64.5 / 112 | m | | MODEL | same |
| V4 warm wing tip | 2,696 | m | 1,276 at driver 0.45 | MODEL | same |
| Compression coupling, V3 | 0.5 | — | 0.2-1.0 explored | TARGET (declared) | D-T06-1 |
| Nozzle η_T | 0.791 | — | 0.740 (10 E_p), 0.64 literature | TARGET (declared) | T03, D-T06-2 |
| Convergence floor | 5,665 | t | | MODEL | `case:floor` |
| 1 g specific-mass gap | 5,084 | × | | MODEL | `case:one_g` |
| Minimum round trip at 0.0069 g | 6.35 | y | 6.0 above 0.0073 g | MODEL | `case:proposals` |
| Nozzle cliff (ve gate) | 0.528 | — | 0.607 on V3 | MODEL | `case:ve_gate` |
| Unbooked penalties | launcher +6-18 %, solid angle +0.023-0.034 +0.0127, eddy 0.1 % | | | MODEL / EXTRAPOLATION | T01-T04 |

## E. Model and geometry implications (for T05)

- Do not draw the half-size dense-compression nozzle (K4, withdrawn).
- V4 matches FDP-1's envelope: loops r 37 / 64.5 / 112 m, stand-off 43 m, warm wings about 2.7 km (1.3 km at driver 0.45).
- V3 is larger: loops r 56 / 97 / 168 m, stand-off 65 m, warm wings about 8.3 km. All PARAMETRIC_PLACEHOLDER.
- Both need T03's closure coils (larger envelope, solid angle 0.040-0.051), T02's engine skirt and LiH loop shoes, split warm manifolds
  per component class (T01), and two injectors with km/s launchers (T01, T04). No visible helix (T03: clocking gives no useful shear).
- Axes: +X bow, +Z dorsal; engine aft.

## F. Dependencies

| Needed from | What | Status |
| --- | --- | --- |
| T01 | warm-loop equivalent, house load, launcher, driver split | received at 1302708 |
| T02 | protection masses, solid angle, residual events | received at 3c665ec |
| T03 | η_T definition, closure coils, stored field, plume strike, recovery extraction | received at 59244a9 |
| T04 | gain-compression bound, coupling range, tritium, injection | received at fd4ff3d |
| T00 | integration of X-T06-1..4 calculator hooks | proposed |
| Drive reader | IGNITION timeline for dating eras | not available; placeholder (undated eras) |

## G. Decisions

- Existing register: D-06 (dust) unresolved and confirmed as a precondition; D-07 respected (no Fiji change); D-08 respected; D-09 not
  used; D-11 respected (no Drive). Recommendations only.
- Proposed: **D-T06-1** declare compression coupling ≥ 0.5 (decide with D-T04-1); **D-T06-2** declare the closure-coil nozzle at its ideal
  model (decide with D-T03-2); **D-T06-3** read-only alignment of the history with the IGNITION timeline. Decider: ApeDevil.
- A recommendation is not an owner approval.

## H. Validation

- `futures.py`: V0 20,760 t within 1 %, ledgers close, exit 0 (566 s).
- `atlas.py validate`, Atlas tests, FDP-1 tests and four-burn tests: results in the commit message and `threads/T06.md`.
- Limitations: FDP-1 optimistic-tier calculator; T02 protection booked as payload; five penalties unbooked (every mass is a lower bound);
  T04's bound is a lower bound on compression energy; nozzle η_T from T03's ideal model.
- Unresolved failures: none.

## I. Integration instructions for T00

1. Bring in `studies/futures/` as a study; no file outside it changes.
2. `registry_proposal.toml`: add T06-NEW-1, T06-NEW-2, the six links, four sources, D-T06-1..3 (merge with D-T04-1 and D-T03-2),
   findings F-T06-1..8 into the Atlas text (REPORT.md cause of the 0.53 cliff; V0-V2 conditional).
3. Generations: adopt V3 (planning) and V4 (bound) from `generations_proposal.toml`, or mark V0-V2 "energy-inconsistent, conditional".
4. Conflicts: Atlas gain/density pair vs T04 (bound decides); K3 nozzle 0.86 vs T03 (T03 decides); 800 K vs T01 628 K (T01 decides).
5. After integrating, implement X-T06-1..4 and re-run `futures.py`, `deps.py`, `atlas.py validate` and the Atlas/FDP-1 tests.

## J. Recommended next experiment

Book the unbooked penalties (X-T06-3, X-T06-4) and the gain cap (X-T06-1) in the calculator, then rerun the integrated frontier. It
answers whether V3 stays below about 50 kt once the launcher, closure-coil solid angle and shoes are paid for. Method: calculator
extension by T00, one rerun of `futures.py`; cost about half a day. Owner: T00, with T06's script as the harness.
