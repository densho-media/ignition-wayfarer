# T03 handoff: magnetic nozzle, helical fields and energy recovery

| | |
| --- | --- |
| Thread | T03, plasma physics and electromagnetic propulsion |
| Date | 2026-11-09 |
| Status | DONE (within D-PLAN-1; the self-consistent questions wait on D-09) |

Detailed evidence: `REPORT.md` (this folder). Early numbers: `EARLY.md`. All MODEL values are reproduced by the scripts below.

## A. Mission and scope
- Investigated (T03-NOZZLE.md questions):
  1. Nozzle efficiency definitions and the literature behind the 0.79 (REPORT §1).
  2. Configurations A (three-loop FDP-1), B (clocked sectors), C (shaped, axisymmetric with forward closure coils, plus non-planar
     C3D) and D (balanced / counter-helical), with stored-field ratios 3-30 (REPORT §3).
  3. Field-line and stopping-surface geometry, Maxwell stresses, struts (REPORT §5, `results/field_lines.json`).
  4. Instabilities, leakage, low-beta tail and duds, detachment (REPORT §4).
  5. Coupled energy accounting and one recovery fraction for T01 (REPORT §6).
  6. Calculator re-runs at corrected efficiency and field ratio, read-only (REPORT §1, §3).
  7. D-09 study plan (REPORT §8). Extra, at T02's request: one loop sector lost (EARLY §5).
- Deliberately excluded: self-consistent MHD or PIC (D-09 not approved); edits to the calculator, registry, canon, Drive or Blender
  (out of scope); new Fiji properties (VTX-02A read-only; no Fiji credit taken).

## B. Repository state
| Item | Value |
| --- | --- |
| Starting commit (Phase 1 base) | `8de3ffa189b47ce9a1212b550b7ea75f8c36314a` |
| Branch | `claude/project-thread-ujxhjo` |
| Resulting commit | the commit that adds this file (see `git log -1 -- lab/variants/vertex-drive/studies/nozzle/HANDOFF.md`); EARLY at `b7631e3` |
| Changed paths | `lab/variants/vertex-drive/studies/nozzle/**` only (plus `/mnt/project-files/vertex/threads/T03.md`, outside Git) |
| Rerun | `python3 lab/variants/vertex-drive/studies/nozzle/test_nozzle.py` (about 20 s); `.../run_nozzle.py` (about 5 min); `.../calc_rerun.py` (about 4 min); `.../sector_loss.py` (about 2 min). numpy only. |

## C. Research findings
### Published evidence
- FDP-1's 0.79 traces to Thio et al., AIAA 99-2703 (MSFC, 1999): about 0.80 momentum efficiency, maximum 0.863. SECONDARY_VERIFIED
  (S-MSFC-NOZZLE → S-T03-THIO-1999).
- Simulations: 0.65 momentum (S-T03-NAGAMINE-1999, 3D hybrid PIC, RT effect limited); 0.67 (S-T03-MATSUDA-2009); 0.55 / >0.70 / 0.34
  (S-CASSIBRY-PMN). Efficiency independent of energy and species (S-T03-INATOMI-2023). Ideal MHD fails on Alfvén speed
  (S-T03-ROMANELLI-2017). Power generation costs 7% (S-T03-SCHILLING-2023). Only experiments measure impulse, not efficiency
  (S-T03-MAENO-2013). All SECONDARY_VERIFIED (abstracts).
### Calculated results
- The calculator's `nozzle_efficiency` is the thrust efficiency eta_T = F²/(2 mdot P) (`fourburn/architectures.py::_pulse`). For an
  elastic, monoenergetic nozzle eta_T = eta_mom². V1 at 0.624: 39,715 t; at 0.745: 12,118 t; at ≤ 0.49: no closure.
  `calc_rerun.py`.
- The pulse needs ≥ 10 E_p of stored field: C reaches eta_mom 0.54 / 0.77 / 0.86 / 0.889 at 3 / 6 / 10 / 15 E_p. `run_nozzle.py`.
- A (three loops) leaks forward: best eta_mom 0.68, about 22% of plasma on the shield or the ship. C (closure coils 20°/40°): 1.4-1.6%.
- Coupled V1 with C: 22,683 t at 15 E_p (best), 30,949 t at 10 E_p. `calc_rerun.py` t03 cases.
- B: 0.25-1.1° shear, no efficiency effect. Helices: 7-52° shear at a cost of 3-23 points of eta_mom; torque 0.24-0.7 MN·m.
- Test-particle loss cone onto the shield centre: A 34%, C 5.5% (matches adiabatic theory). `particles.py`.
- Sector lost: −0.4 to −2 points of eta_mom, 2-8 kN side force (C); L2 worst. `sector_loss.py`.
- Recovery extraction 0.13-0.20% of fusion. Screens about 0.1% of plasma. REPORT §6.
### Engineering extrapolations
- The superconducting windings need warm eddy-current screens. Without them the pulse loss is 6-10 GW at 20-40 K (Bean estimate,
  ×10 band). The screens double as the VTX-02C pickup. Confirm with a coupled circuit and eddy-current model of the screen.
- The coil packs see a 7-10% load cycle 1.9e10 times: a fatigue requirement outside any database.
- RT: linear theory gives about 13-14 e-folds per pulse at l ≈ 70, so the interface goes nonlinear every pulse. Simulations at laser
  scale saw only a limited effect. D-09 decides which holds.
### Fictional assumptions
- None used. The Fiji card (VTX-02A) gives no nozzle credit. The model does not need it, and T03 proposes no Level C property.
### Unknowns
- Detachment and the field energy carried away per pulse: needs resistive or Hall MHD (D-09).
- RT mixing depth at 80 GJ: D-09.
- Velocity-spread factor on eta_T: about 0.94 for a self-similar shell (ASSUMPTION), not in the numbers above.
- Screen eddy loss: band 0.03-1% of plasma.
### Negative results
- FDP-1's three-loop cup (A) at any current pattern: eta_mom ≤ 0.68, so eta_T ≤ 0.46. V1 does not close on it.
- 1 E_p of stored field cannot stop the pulse; even 3 E_p gives eta_mom ≤ 0.54.
- Clocked sectors produce no useful shear.
- Helical windings trade collimation for shear. Twist reversal does not cancel torque robustly.
- No published or modelled energy-equivalent efficiency reaches 0.79, except the ideal C model at 15 E_p (0.791, upper bound).

## D. Quantitative effects
| Quantity | Value | Unit | Uncertainty / range | Label | Source |
| --- | --- | --- | --- | --- | --- |
| Literature momentum efficiency | 0.55-0.80 | 1 | max 0.863 analytic | PUBLISHED | S-T03-THIO-1999, S-T03-NAGAMINE-1999 |
| Same as thrust efficiency | 0.30-0.64 | 1 | max 0.745 | MODEL | definition, REPORT §1 |
| eta_mom / eta_T, C at 15 E_p | 0.889 / 0.791 | 1 | upper bound | MODEL | nozzle_results.json C_W15 |
| eta_mom / eta_T, C at 10 E_p | 0.860 / 0.740 | 1 | upper bound | MODEL | C_W10 |
| eta_mom, A best | 0.68 | 1 | 0.29-0.68 over 3-30 E_p | MODEL | Astar_W10 |
| Stored field needed | 10-15 | E_p | 6 marginal | MODEL | sweeps |
| Coil structure (virial) | 855-1,281 | t | at 1.07e-6 kg/J | MODEL | ledger |
| Plasma on hardware, C | 1.4-1.6 | % of plasma | | MODEL | C_W10, C_W15 |
| Plume-strike share of nozzle loss | 0.06-0.07 | 1 | calculator 0.02 | MODEL | calculator_reruns.json |
| V1 departure, coupled C 15 E_p | 22,683 | t | lower bound | MODEL | calc_rerun.py |
| V1 departure, 0.79 read as momentum | 39,715 | t | | MODEL | calc_rerun.py |
| C1 current / hoop tension (15 E_p) | 132 / 6.9 | MA / GN | | MODEL | stresses |
| Inter-coil axial forces | 0.24-1.9 | GN | | MODEL | stresses |
| Envelope solid angle | 0.040-0.051 | sr/4π-equiv. | V1 0.017 | MODEL | ledger |
| B shear (5% trim) | 0.9-1.1 | deg | 3-3.7 at 20% | MODEL | perturbations |
| Helix roll torque | 0.24-0.7 | MN·m | RCS 0.026 | MODEL | perturbations |
| Trim power, 1% in 5 ms | 3.2-4.8 | TW | D-03 quotes 0.34 | MODEL | REPORT §5 |
| Recovery extraction | 0.0013 | of fusion | 0.0012-0.0020 | MODEL | REPORT §6 |
| Recovery efficiency | 0.80-0.95 | 1 | | ASSUMPTION | |
| Screen dissipation | 0.1 | % of plasma | 0.03-1 | EXTRAPOLATION | REPORT §6 |
| Unscreened winding loss | 6-10 | GW | ×10 | EXTRAPOLATION | REPORT §6 |
| Loss cone to shield (tail, duds) | 34 / 5.5 | % (A / C) | | MODEL | particles.py |
| One sector lost (C) | −0.4 to −2 / 2-8 | pt eta_mom / kN | | MODEL | sector_loss.json |
| RT e-folds per pulse | 13-14 | 1 | l ≈ 70 | MODEL (analytic) | REPORT §4 |
| D-09 minimum campaign | 2-10 | million core-hours | | EXTRAPOLATION | REPORT §8 |

## E. Model and geometry implications
- Add the two forward closure coils (T03-NEW-1). Nozzle frame, x = x_burn + z, x_burn ≈ −227.5 m (V1, PARAMETRIC_PLACEHOLDER):
  C1 r 14.74 m at z +40.51 (envelope radius 2-3.2 m), C2 r 27.71 m at z +33.03. Both are PARAMETRIC_PLACEHOLDER.
- Keep L1-L3 positions (ENGINEERING_SUPPORTED). Enlarge their envelope radii to 0.4-0.7 m (from FDP-1's 0.21 m;
  PARAMETRIC_PLACEHOLDER). Size the struts for 0.2-1.9 GN axial attraction plus fatigue.
- Keep four sectors per loop and a warm screen around each winding.
- Show helicity as a sector clock, not a helix. Draw no helical conductors.
- Overlay: `results/field_lines.json` (CONCEPTUAL_ILLUSTRATION of the field, r-z half-plane).

## F. Dependencies
| Needed from | What | Status (received at commit / placeholder used) |
| --- | --- | --- |
| T00 | V1 pulse and loop geometry | `results/convergence.json` at `8de3ffa` |
| T00 | V1 layout (x_burn) | placeholder −227.5 m |
| T04 | Debris velocity and dud figures | T04 EARLY/DONE `fd4ff3d`, consistent with the V1 pulse used |
| T02 | Sector-loss request | answered (EARLY §5) |
| T01 | Hot-loop margin for 137 GW plasma on hardware plus 8.6 GW screens | sent via T03.md; not needed for T03 results |
| ApeDevil | D-09 | not approved; plan in REPORT §8 |

## G. Decisions
- Existing register: **D-01** supported and refined (balanced helicity necessary; sector clocking gives < 1° shear; the harmonic is
  m = 2 for trim and m = 4 for gaps, not a helical m = 4). **D-03** supported and strengthened (trim 3-5 TW at 10-15 E_p).
  **D-09** remains open; the scope is proposed as D-T03-3.
- Proposed: **D-T03-1** book eta_T = eta_mom² in the calculator (T00). **D-T03-2** stored field ratio 10-15 E_p (T00).
  **D-T03-3** approve the D-09 2D campaign (ApeDevil).
- A recommendation is not an owner approval.

## H. Validation
- `atlas.py validate`: 0 errors (34 records). Atlas tests: 21 OK. FDP-1 tests: 45 OK. Four-burn tests: 18 OK. `test_nozzle.py`:
  11 OK. All run on this branch after `git fetch origin main`. The canon guards compare against `origin/main`, so a stale local ref
  fails them spuriously.
- Model limitations: vacuum fields, elastic specular thin shell, no instabilities, no velocity spread, no detachment, first-order
  perturbations (torque noisy at the 1e3 N·m level; ripple above 30% is beyond first order), local optimiser (results non-monotone).
  Test particles have no collective effects. All efficiencies are upper bounds.
- Unresolved failures: none.

## I. Integration instructions for T00
1. Bring in `studies/nozzle/` as evidence. No code in it is imported by the Atlas.
2. `registry_proposal.toml`:
   - Revise S-MSFC-NOZZLE (→ Thio 1999, momentum definition).
   - Add the six S-T03 sources and T03-NEW-1 (under VTX-03).
   - Revise VTX-03A/B/C.
   - Add three claims and D-T03-1..3, and attach the D-01/D-03 evidence.
3. Generations: do not re-base V1 without ApeDevil. Add a sensitivity "V1, nozzle definition corrected" (eta 0.624 → 39,715 t) and
   "V1, C nozzle 15 E_p" (eta 0.791, ratio 15, plume-to-hardware 0.07 → 22,683 t). Fix the REPORT/Atlas wording "0.79 is the
   theoretical bound for beta >> 1 nozzles": it is a momentum figure.
4. Conflicts: T04 independently finds V1 at 59-97 kt (gain). The levers stack; together V1 is far above 10 kt. Deciding test: the
   combined re-run with T03 and T04 overrides. T02's sector-loss numbers come from here.
5. Re-run `atlas.py validate`, the Atlas, FDP-1 and four-burn tests, and `convergence.py` if generations change.

## J. Recommended next experiment
D-09, step 1: a 2D axisymmetric Hall-MHD (PLUTO or Athena++, Alfvén-limited) and hybrid-PIC run of the V1 pulse in A and in C at
15 E_p. It would report eta_T, plasma on hardware and RT mixing. Cost: about 1e4-1e5 core-hours per case on HPC. Decisive
threshold: C eta_T ≥ 0.70 with ≤ 2% on hardware keeps the shaped nozzle; below 0.62 rules out pulsed magnetic nozzles as a mass
lever. Owner: ApeDevil approves (D-T03-3); thread T03 or a new D-09 thread.
