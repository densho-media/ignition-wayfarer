# Vertex 2.11: Stern Mirror feasibility verification

| Field | Value |
| --- | --- |
| Kind | study (numbers only, no geometry) |
| Status | ACTIVE, research, not canon. Gate result: **Stern Mirror FAILS**, so the branch is preserved as a research result and not optimized further |
| Question | Can the 2.10 Stern Mirror (electrostatic reflector on the stern disk) show acceptable voltage stability, reflection efficiency and total mass, so that A1 + Stern Mirror becomes a credible comparison candidate next to B2d? |
| Model base | Vertex 2.10 (work/vertex-2-10): A1 nozzle (B2d coils, burn z 12), forward escapes from forward.py / recover.py, ledger mission210 on mission28 / 2.7 / 2.6; 5 % delta-v reserve |
| Owner brief | 2026-11-18 15:51Z (P1 carry A1 + Mirror as a parallel comparison candidate; P2 staged validation; P3 He-3 storage item to the request Doc) |
| Open owner questions | R1-R3 below |

Nothing here changes Blender geometry, canonical parameters, workbooks or lore. B2d stays the research reference and the A1 improvement
(burn 3 m aft, forward x0.61 at the same cosine) is kept whatever happens to the mirror. No squash, no deployment.

## Result in one paragraph

The Stern Mirror does not pass. **Voltage stability:** the 2.10 stack (10 MV over 8.5 m) exceeds large-area MeV-accelerator hold-off data by
~31x in E x V (~5.6x in volts per stage), and its suppressor wires would see 120-240 MV/m. Stacks that respect that data must be 60-126 m
deep, plus a rear grading column of similar depth to insulate the +10 MV plate, which together exceed the 200 m spine. In the PIC, the
113 m stack's own space charge then raises its wire fields 4-13x above vacuum, so it fails hold-off again. **Reflection efficiency:**
1D PIC (benchmarked, converged) gives 92.5 % reflection and 13.6 % heat at the 2.10 design. Secondary electrons climbing the stack carry
two thirds of that heat and draw 6 % of the stream power from the supply (0.8 GW per engine at 10 %). The pass criteria (reflection >= 95 %,
heat <= 5 %) are met only with 0.1 % opaque grids. A broadened thermal spectrum reflects 74 %. Unthermalized fusion products reflect 21 %
at 10 MV and need ~17 MV. **3D:** the 2.10 facets had the wrong sign. Edges aft tilt the normals inward, so the reflected beam crosses the
axis through the spine. In the four engines' coil fields, the cluster's own magnetic mirror turns 99 % of that beam back past the ship.
Inverted (convex) facets at -10 deg pass 89 % aft with zero engine strikes. **Total mass:** with the PIC losses and the 3D returns, no
hold-off-consistent mirror closes below 8.1 kt. 6.4-6.6 kt is reached at 10 % only by the 2.10 stack (hold-off exceeded x31) with
optimistic secondary suppression or supply mass. Nothing closes at 30 % below 7.4 kt, and nothing approaches 4.6 kt.

## P3: He-3 storage item (done)

Posted to the request Doc "IGNITION — Wayfarer Claude Request" as **2026-11-18T16:55+01:00 — He-3 storage volume vs BODY-C3 cryostat
(proposed research item, unresolved)**, appended after the 2026-10-24 item and read back. Text: `SE_QUEUE_HE3_POST.md`. It covers
1.9-2.3 kt He-3, ~34,000 m^3 of liquid against the 4,072 m^3 BODY-C3 study (8x; canon 1,094 t needs ~18,700 m^3), and questions on
tankage, refrigeration, boil-off and reconciliation. Boil-off screen: 0.05-0.3 W/m^2 at 3 K on 5,100 m^2 is 3-16 t/day, so
zero-boil-off refrigeration looks mandatory. It links the proposed Economy/Technology supply item. No inventory, mining programme or
storage geometry is changed. The wayfarer-drive-writer agent had no Docs tools in this session, so the main session made the
precondition check, the append and the read-back itself.

## 1. Electrostatic PIC (`pic1d.py`, `bench.py`, `cases.py`)

1D planar column through the stack: entrance grid (0 V), suppressor (-V_s), graded grids, solid plate (V_top).
- Kinetic relativistic ions of several species and spectra, pulsed. Each pulse is born within 1 us and flies 244 m, so species and
  energies separate in time; 56 kHz train; the last period is diagnosed.
- Space charge of ions and electrons. Energy-conserving field (Lewis), Dirichlet electrodes.
- Stream electrons in front of the suppressor: Boltzmann (Newton-solved).
- Grid transparency per crossing.
- Secondary electrons. Yield scales with electronic stopping at the impact energy (1 at 1 MeV/u for p, x Z^2), with an escape factor for
  magnetic suppression. Secondaries are kinetic, relativistic and sub-cycled.
- Optional photoelectrons. Interception heat, collected charge and electrical work per electrode.

| Benchmark | Result |
| --- | --- |
| Single particle, 8.25 / 14.68 MeV p vs 10 MV | reflected 1.000012; plate heat 0.318787 vs 0.318801 exact; electrical 0.681199 exact |
| Child-Langmuir, 1 MV, 1 m (0.5x / 2x drive) | 0.499-0.503 / 0.95-1.05 of J_CL (dx 1 and 0.5 cm) |
| Drift-space limit 8 J_CL (0.9x / 1.3x) | transmitted 0.998 / 0.28 (virtual anode, 70 % reflected) |
| Energy closure (supply work from induced charges) | <= 3e-5 benchmarks, <= 2e-5 D210 cases, <= 1.4 % in the 50-113 m stacks (long Boltzmann region) |
| Convergence D210, 30 % (dx 2/1/0.5 cm, 25k-200k particles, dt/2, seed, 3 periods) | reflect 0.923-0.926, heat 0.134-0.142 |

Single-ion share 10 %: 13.2 GW per engine on its 1,590 m^2 quarter (8.3 MW/m^2); 30 %: 40.6 GW (25.5 MW/m^2).

| Design (thermal set unless noted) | Depth | Reflect 10 / 30 % | Heat (of it e-) | Net electrical | Wire field vs vacuum |
| --- | --- | --- | --- | --- | --- |
| D210: 2.10 stack, 10 x 0.8 m stages, grids 0.5 % opaque | 8.5 m | 0.925 / 0.925 | 0.136 (0.088) | -0.061 (draw) | 1.62 / 2.15 vs 1.50 MV/m |
| D210_o1: same, 0.1 % grids | 8.5 m | 0.985 / 0.985 | 0.028 (0.018) | -0.013 | 1.63 / 2.17 vs 1.50 |
| DBD: 53 stages, 0.1 % grids, 10 m terminating gaps (1 %) | 50 m | 0.899 / 0.892 | 0.178 (0.103) | -0.079 | 0.65 / 1.36 vs 0.27 |
| DBD100: hold-off-compliant in vacuum, 18 x 5.6 m, 0.1 % grids | 113 m | 0.967 / 0.945 | 0.068 (0.037) | -0.029 / +0.002 | 0.49 / 1.40 vs 0.11 |
| D210, broadened thermal (gamma, sigma/mean 0.41) | 8.5 m | 0.735 | 0.166 | +0.099 | p above 10 MV reach the plate |
| D210, equal energy per charge (5.5 MV) | 8.5 m | 0.932 | 0.136 | -0.069 | |
| D210, unthermalized products (p 14.7, alpha 3.7 MeV, 3 % D-D) | 8.5 m | 0.213 (p 0.022) | 0.326 | +0.460 | |
| D17: 17 MV, 17 stages, birth spectrum | 14.1 m | 0.877 | 0.187 | -0.064 | |

Sensitivities (D210, 10 %):
- Secondary yield x0.3 / x3: heat 0.074 / 0.320 (draw 0.246).
- Escape factor 0.3 / 0.1 (magnetic suppression): heat 0.074 / 0.057. No secondaries at all: 0.049.
- T_e 100 keV: PIC unchanged, but suppressor leakage exp(-V_s/T_e) then carries ~5 % of the beam power through 10 MV. V_s 1.5 MV fixes
  that (heat 0.143, suppressor field 3 MV/m).
- Local hot spot x2: same fractions, twice the fluxes. Pulse duration 0.3 us: same.
- X-ray photoemission (3e15 e/m^2/s per grid): +0.1 point.
- 1D vs 3D interception: the 3D angle-dependent opacity (o / cos theta per crossing) gives 0.916 vs 0.924 (o 0.005) and 0.982 vs 0.984
  (o 0.001).

Reading: space charge is not what stops a short stack (no virtual anode, wire fields +8-45 %). Interception, secondaries and the
spectrum are. In long, hold-off-friendly stages, though, the beam's own charge sets the field (4-13x vacuum).

## 2. Breakdown and grid survival (`screen.py`)

Evidence, not Cranberg alone. H1: JT-60 / ITER MeV accelerators, five 200 kV stages, where 200 kV was marginal at 72 mm and large grids
held less than half of what small electrodes do; taken as E x V = 4e11 V^2/m at ~2 m^2. H2: E x V proportional to S^-0.33 (QST, plane and
coaxial electrodes up to 10 m^2, clump model), extrapolated to stern-disk grids. H3: graded accelerator columns at 1.5-2 MV/m, but with
small-area electrodes. Grids inside a graded stack sit at their natural potential (wire field ~2x the gap field). The entrance and
suppressor grids terminate field lines (wire field (E_up + E_dn)/(pi o)) and are held below 10 MV/m.

- D210 overstress: x31 in E x V on its wires (S 164 m^2), x5.6 in volts per stage. Suppressor wires: 120-240 MV/m for o 1-0.5 %.
- Hold-off-consistent 10 MV stacks: 62 m (43 stages, ion loss 7 %, 15 % with secondaries) to 126 m (18 stages, 4 % / 9 %). At 17 MV:
  123 m (13 % / 28 %). The +10 MV plate needs a rear grading column of similar depth to reach ship ground, so the total exceeds the
  200 m spine. 2.10's Cranberg law (C 1e13 V^2/m, no area effect) allowed a single 10 m gap; the large-area data do not.
- Grid heat: a radiatively cooled ribbon below 1,500 K (tungsten thermionic emission 1e-3 A/m^2; 0.49 A/m^2 at 1,800 K) only survives
  incidence spreads below 0.5-4.6 deg at 10 % and 0.2-1.5 deg at 30 %. Ions reach the facets at 10-12 deg. Grid heat 18-280 kW/m^2 of
  disk at the suppressor, which therefore needs active cooling across MV stages.

## 3. 3D field and trajectories (`traj3d.py`)

The field is phi0 + psi. phi0 is the layered stack potential (exact between flat grids). psi is the 3D finite-difference correction on
one quadrant (h 0.25 m, ~0.6 M unknowns, mirror symmetry), driven by the folds of the layers at the seams and apex, with an ideally
graded rim. The correction reaches 21-75 % of the local field on the seam line and stays within 0.35-1.1 m of it; 0.1 % of the
landing stream falls within 1 m of a seam. The 1,342 energy-weighted forward escapes of the A1 nozzle (24 azimuths) were pushed by Boris
(E and B) through the stack and aft through the static coil field of all four engines. Classification: housing strikes (r 11.44 m,
z -31.93 .. 0), an assumed r 3 m spine envelope (PROTOTYPE), aft, radial, back past the ship, multi-bounce.

| Facets | Field | Aft | Spine | Back past ship | Radial | Engines | Aft cos |
| --- | --- | --- | --- | --- | --- | --- | --- |
| +10 deg (2.10: edges aft, normals tilt inward) | ballistic | 0.607 | 0.373 | 0 | 0 | 0.020 front | 0.94 |
| +10 deg | four engines' coils | 0.009 | 0.481 | 0.396 | 0.100 | 0.014 | 0.48 |
| -10 deg (convex, normals outward) | ballistic | 0.986 | 0 | 0.014 | 0 | 0 | 0.94 |
| -10 deg | four engines' coils | **0.887** | 0 | 0.014 | 0.099 | 0 | 0.57 |
| -20 deg | coils | 0.776 | 0 | 0.224 | 0 | 0 | 0.71 |
| -30 deg | coils | 0 | 0 | 0.913 | 0.087 | 0 | |

- Correction to 2.10 B1: the facets there ("tilted outward") have their edges aft, so the reflection is inward. Its 94.9 % pass and 5.1 %
  strike omitted the spine and the engines' magnetic field.
- The cluster's coils are a magnetic mirror seen from the front: ions that come within ~30 m of the cluster (Larmor radius ~10 m) are
  turned back. Only a beam steered outward past the cluster leaves, and the cluster's field still bends it (cos 0.57). That momentum is
  not credited (min rule).

## 4. Ledger (`mission211.py`, 5 % delta-v reserve, departure t)

The mirror's stack heat comes from the PIC. Its electrical draw is supplied at eta 0.5, at 1 kg/kW (0.1 kg/kW sensitivity); a surplus is
dumped as heat. The plate flux joins the stern gate. The 3D return share is heat on the ship. Stack mass from its layout (36 kg/m^2 for
D210, ~95 kg/m^2 for DBD100, PROTOTYPE).

| Candidate | 10 % single-ion | 30 % | 3 % | 1 % |
| --- | --- | --- | --- | --- |
| B2d, plate | no closure | no | 7,834 | 6,154 |
| A1, plate | no | no | 6,718 | 5,881 |
| A1 + D210 mirror, -10 deg facets (hold-off x31 exceeded) | no (8,083 at 0.1 kg/kW) | no | | |
| A1 + D210, secondary escape 0.1 or yield x0.3 | 6,418 | | | |
| A1 + D210_o1 (0.1 % grids, hold-off x25 exceeded) | 9,853 (6,598 at 0.1 kg/kW) | no (7,364 at 0.1 kg/kW) | | |
| A1 + DBD100 (vacuum-compliant, 113 m + rear column > spine) | no (8,377 at 0.1 kg/kW) | 8,066 | | |
| A1 + any mirror with the 2.10 +10 deg facets | no (12.5 kt at best) | no | | |
| 2.10 claim (h_B 5 %, ballistic 5.1 % strikes) | 6,380 | 6,981 | 6,193 | 6,142 |

He-3 2.2-3.3 kt in the mirror closures. None meets 4.6 kt. Operating inside the ~7 kt research envelope is not the 4.6 kt requirement.

## 5. Failure modes and reliability

- Arcs: each 0.8 m stage of one quarter stores ~10 kJ (17.6 nF), the whole stack ~88 kJ. Large-area MeV accelerators still break down
  during long pulses after long conditioning. Four 467-day burns need either near-zero breakdown rates or fast recovery.
- A tripped mirror exposes the plate to the full forward stream: 8.3 MW/m^2 at 10 % (inside the plate gate if the plate is designed
  for it), 25.5 MW/m^2 at 30 % (above it, so the engine must throttle on every trip).
- Supply: 0.4-0.8 GW per engine at ~10 MV (D210, DBD100 at 10 %), unprecedented for DC.
- Secondary electrons striking the plate at several MeV radiate ~20 % of their power as bremsstrahlung, ~0.25 GW per engine at the stern
  (D210, 10 %), half of it toward the ship.
- Suppressor leakage scales as exp(-V_s/T_e). T_e of the escaping stream is unknown (10-300 keV), so V_s may need 1.5-4.5 MV.
- A broken grid wire bridges a stage. Grid cooling lines must cross MV potentials.

## 6. Engine operation (A+)

The A+ mechanical ignition stays as decided. The 2.10 "mirror charge" start-up step is not supported by this model and is not added.

## 7. Gate decision

Final gate (brief): the Stern Mirror cannot show acceptable voltage stability (x31 over data, or more than 200 m of stack once compliant),
reflection efficiency (92.5 % with 13.6 % heat at the 2.10 design; 21 % for unthermalized products at 10 MV) or total mass (no
hold-off-consistent closure below 8.1 kt). It is kept as this research result and the branch is not optimized further. The local gates
did not pass, so no external 2D hybrid study of A1/B2d was prepared or run (P2 made it conditional on those gates).

Recommendation: stop adding speculative corrections to B2d and run a broader comparison of fusion cycles and propulsion architectures on
one ledger:
- Fuel cycles: D-He3, catalysed D-D, p-B11 and D-T with neutron shielding.
- Architectures: pulsed magnetic nozzle (Vertex), steady direct fusion drive, fusion-electric with electric thrusters, the external-pulse
  family (EXT-01), and beamed or infrastructure-assisted options.
- Common loss channels: forward and isotropic radiation, the charged-particle spectrum, neutrons, specific power, jet efficiency, fuel
  supply and storage.

The Fuel & Propellant thread's pulsed-target findings (fuel rate per engine 38 vs 185 g/s; no unburned-fuel return) belong in that
comparison too.

## Owner questions

- R1 Accept the gate result: Stern Mirror kept as a research result (SR-210B not credible as specified), B2d and A1 stay the references,
  SR-26F stays open?
- R2 Start the broader fuel-cycle and propulsion-architecture comparison as the next Vertex study (one ledger, no geometry)?
- R3 Keep A1 (burn 3 m aft) as the B2d nozzle setting for future ledgers (5,881 t at 1 %, 6,718 t at 3 %)?

## Files

`pic1d.py` model; `bench.py` benchmarks (`bench.json/.log`); `cases.py` PIC sets main, sens, conv, bd100 (`cases_*.json/.log`);
`screen.py` hold-off, transparency and grid-heat screen (`screen.json/.log`); `traj3d.py` 3D field and trajectories
(`traj3d.json/.log`); `mission211.py` ledger (`mission211.json/.log`); `SE_QUEUE_HE3_POST.md` posted request-Doc item.
