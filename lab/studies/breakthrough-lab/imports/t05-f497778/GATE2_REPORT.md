# Vertex feasibility gate 2: T05 report (Task C, experimental geometry)

Kind: study. Status: FOR OWNER EVALUATION, research only, NON-CANON. Brief: "WAYFARER — Vertex Feasibility Gate 2" (2026-11-10).
Base: T05 ctwplp `c45ab4a` (gate 1), T00 9rsgog `43fac75` plus T00's gate 2 rows. V4, Revision 4 and the gate 1 lanes are unchanged
and stay in `GATE_COMPARE` (Rev 4 at z +120, A1 at −120, rejected lanes at −330); gate 2 adds lanes from z −560 down. No canon,
production geometry, Drive or story changed. Nothing goes onto `main`.

**Decision: A1 is geometrically blocked for every configuration tested.** T05's envelopes find three farms that fit the 7.5° rim and
the r 45 dust shield. T00's coupled model diverges past 400 kt on all of them, and the only converged ships need farms of r 48-70 m,
which leave the dust shadow and pass the A1 rim limit. The structure independently fails its stiffness target. Twin nozzles do not
fit with FDP-1-sized loops and planar radiator wings.

## 1. Shielding envelopes (with T00 Task A)

Rim rule (FDP-1, T00): rim = atan(R_farm / d_far + 1 m / d_shield), with the farm's near end at X 109.25 (d_far 358.4 m). The canon
forward shield is r 45 m (dust shadow), so a farm must stay at or under r 44 (1 m clearance). Stretch length at the coupled
propellant (lam 2.73) and the V4 bay loading.

| variant | farm | rim (limit) | dust clearance | T05 geometry | T00 coupled |
| --- | --- | --- | --- | --- | --- |
| F0 V4 reference | r 34.5 × 275 m | 6.37° (7.5) | 10.5 m | passes (V4 mass only) | — |
| F1 T00 gate wide | r 57 × 275 m | 9.89° | −12.0 m | fails rim and dust | converged at 117 kt (gate 1) |
| F2 cone-limited | r 41.7 × 515 m | 7.50° | 3.3 m | passes | DIVERGES (> 400 kt) |
| F2x dust-limited | r 44 × 462 m | 7.87° | 1.0 m | fails rim | — |
| F3 long | r 34.5 × 751 m | 6.37° | 10.5 m | passes | DIVERGES |
| F4 burn point 20 m aft | r 44 × 462 m | 7.50° | 1.0 m | passes | DIVERGES (stand-off +100/+200 m too) |
| F6 A1 at 15°, shield face 68.2 m | r 44 × 462 m | 7.83° (8.35) | 1.0 m | passes | DIVERGES |
| F4w wide, burn point 132 m aft | r 57 × 275 m | 7.50° | −12.0 m | fails dust | — |
| F5 elliptical | 77.9 × 41.7 m | 7.50° in the tilt plane | −32.9 m | fails dust | — |

Why the coupled ship diverges (T00): FDP-1 adds about 14 t of departure per tonne of added hardware. The A1 thrust loss, coils and
launcher push the propellant ratio past what a 43 m farm holds at the V4 length, so the stretch grows and the spine mass runs away.

## 2. Tilted-coil clearances, relocation and thrust line

- **Correction to gate 1:** A1 is thrust-aligned. T00 turns the whole field set back by β (2.68° at 14°), so the net thrust lies on
  the ship axis. Gate 1's "152 MN·m unbooked torque" was wrong. The residual is the reflected-plasma torque (lever 2.29 m, about
  18 MN·m untrimmed), which a further 0.32-0.63° turn trims.
- **Larger tilts (T00 rows, drawn at 15° in lane F6):** 15° raises the rim limit to 8.35° and 16° to 9.09°, but C1's near side comes
  inward (envelope 6.49° and 5.69°), so the shield face moves forward to 68.2 m, out of C1's z band. Tilts of 18-22° put C1 into the
  module. The static torque on the C1/C2 pair is 52-74 GN·m (T00), a new strut load that is not yet sized. Beam deflection through the tilted field is
  198-510 mrad by azimuth (T00).
- **Re-landing:** the tilted C1 hits loop-1 struts 4 and 5 (gate 1). Turned −12° and +12° about the ship axis, they clear C1 and
  the leak at the chosen tilt azimuth of 90° (ray-checked, `checks.json` `gate2_reland`, drawn in `GATE2_RELAND`).

## 3. Structure: frame FE (Task C) against beam (T00)

Parametric frame FE (`gate2_fe.py`): fe_s5n.py's elements on a generated section. Calibration: the generator gives 0.118 Hz at V4,
against 0.110 for the drawn model. Two boundary conditions: cantilever (J1 fixed), and free-free with the aft ship (35.9 kt, centroid
244 m aft of J1) as a rigid body on J1. Screens: f1 ≥ 0.12 Hz (3× the 0.022-0.040 Hz slosh band), and clear by 15 % of ring spin
(4 rpm = 0.0667 Hz) and its 2× (0.133 Hz).

| section | frame mass | FE free-free global | FE cantilever | T00 beam cantilever | FE/beam |
| --- | --- | --- | --- | --- | --- |
| V4 r 34.5 × 275 m | 1.83 kt | 0.165 Hz | 0.118 Hz | 0.181 Hz | 0.65 |
| r 41.7 × 514 m | 3.74 kt | 0.084 | 0.053 | 0.059 | 0.90 |
| r 44 × 462 m | 3.46 kt | 0.096 | 0.061 | 0.071 | 0.86 |
| r 34.5 × 751 m | 4.96 kt | 0.049 | 0.028 | 0.030 | 0.92 |

- The drawn saddles hang the tanks from the keel ring only. On every coupled farm this gives tank-swing modes at 0.028-0.031 Hz,
  inside the slosh band. Tying the saddles to the longerons removes them: the lowest mode becomes 0.054-0.059 Hz, and r 41.7 reaches
  0.087 Hz global at 4.3 kt (r 44: 0.099 at 4.0 kt).
- **Stiffening r 41.7:**

  | change | mass | free-free bending |
  | --- | --- | --- |
  | 18 longerons r 0.8 m | 9.5 kt | 0.119 Hz |
  | 18 longerons r 1.0 m | 13.0 kt | 0.128 Hz |
  | 18 longerons r 1.2 m | 17.4 kt | 0.133 Hz (on 2× spin) |
  | 7.65 m frames | +3 kt | no gain |

  The section saturates near 0.13 Hz, so **0.2 Hz is not reachable at any mass**. The spin windows are 0.077-0.113 Hz and
  above 0.153 Hz.
- The beam model is unconservative mainly on short, wide sections, where frame shear governs; on long stretches it is within about
  10 % (T00 ratios).
- **Verdict on structure:** no tested section reaches the 0.12 Hz screen at a plausible mass. The best practical point is tied
  saddles at about 0.09 Hz, between 1× and 2× spin, and this has not been checked against joint or shell FE.

## 4. Twin splayed nozzles (conceptual, not adopted)

- With FDP-1 loops (L3 R 168 m), each nozzle axis sits about 173 m off the ship axis (138 m at half pulse energy each).
- In the radiator-wing plane each forward channel runs along a wing from its aft edge, 70 m ahead of the burn. Out of the plane, the
  radiators see each burn face-on.
- Splaying 12-16° clears the farm, at a cosine loss of 2-4 %. It moves the aft loops inward, and it needs four nozzles to cancel
  both force and torque.
- The one benefit is half the pulse rate per nozzle (230 Hz), which eases the launcher.
- Verdict: BLOCKED with FDP-1-sized nozzles. A twin architecture needs a nozzle several times smaller and a radiator layout that is
  edge-on to two burns, which is a different design and is not evaluated here.

## 5. Joint questions

T00's report (9rsgog `030fc14`, studies/gate2/REPORT.md; copy /mnt/project-files/vertex/gate2/GATE2_REPORT_T00.md) answers all
five and carries Tasks A, B and D. Short answers:

1. **Can A1 stay viable at a shield cone of 7.5° or less?** No. Three T05 geometries fit, and none of T00's nine rim ≤ 7.5° variants converges.
2. **Is any fusion-target operating point defensible?** No (T00 Task B): FDP-1 needs a target gain of 703 or more, against an analytic best of 440, and D-³He ignition needs 7.8 MJ in 20 ps.
3. **Does any combination have a converged mass model and a plausible structural response?** No. The converged ships fail the dust
   shield and the A1 rim limit. Their spines (FE 0.04-0.06 Hz, T00 estimate) sit in the slosh and spin band.
4. **What should be researched next?** T00 recommends a like-for-like coupled closure of the four-burn IFD-C architectures, not more
   Vertex geometry. T05 agrees: the geometry adds a dust-limited farm radius and a long-stack stiffness ceiling (about 0.13 Hz),
   which any replacement architecture must also clear. Twin nozzles stay a conceptual comparison: they do not touch the three upstream
   blocks (gain, ignitor, eta_T ≥ 0.75), and their doubled coil mass would be amplified about 14x (T00).
5. **Is an expensive simulation justified?** Not D-21: the A1 ship fails on geometry and mass before the plasma question matters. T00
   proposes the 1D radiation-hydrodynamics study only as a falsification test (acceptance: coupling of 0.30 or more at alpha 1.2 or
   less), which needs separate owner approval.

## Files

- Code and data: `gate2.py`, `gate2.json`, `gate2_fe.py`, `gate2_fe.json`, `build_vertex.py`.
- Gate 2 lanes, from z −560 down: `GATE2_F2`, `F4`, `F6` with `GATE2_T15`, `F1`, `F3`, `TWIN`, and `GATE2_RELAND`.
- New scene `GATE2_TWIN`; cameras CAM_VTX_51-54. Issue register: "Feasibility gate 2 register".
