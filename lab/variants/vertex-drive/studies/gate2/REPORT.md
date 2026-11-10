# Vertex Feasibility Gate 2: T00 report (Tasks A, B, D) and joint conclusions

Kind: study. Status: FOR OWNER EVALUATION, research only, NON-CANON. Brief: "WAYFARER — Vertex Feasibility Gate 2" (ApeDevil,
2026-11-10). Base: T00 gate `43fac75` and T05 gate `c45ab4a`, both verified as the latest pushed commits before work started. V4, Revision 4
and the first gate stay reproducible and unchanged (`studies/gate`, `studies/rev4`, `studies/nozzle` untouched; gate tests 13/13). No
canon, production geometry, Drive, lore or story changed. Nothing on `main`. No MHD/PIC, no rad-hydro run, no HPC.

## Decision summary

| Question | Answer |
| --- | --- |
| Can A1 remain viable at a shield cone of 7.5° or less? | **No. A1 is geometrically blocked for every spacecraft configuration tested.** Nine variants hold the rim at or under 7.5° (cone-limited farms on three spine bases, aft stand-off +100 and +200 m, a 15° tilt with the shield moved, the farm held at r 34.5 m). All nine diverge past 400 kt. The converged ships have rims of 8.2-11.6° and farms of r 46-71 m, which also break the canon r 45 m dust shield. |
| Is any fusion-target operating point physically defensible? | **No.** The 78 MJ compression energy is confirmed from first principles (77.8 MJ). FDP-1 closes only at a target gain of 703 or more on V4 alone. The best analytical gain is 440, and that already assumes α = 1, 20 % driver-to-fuel coupling and an ignitor that does not exist (7.8 MJ in 20 ps). D-³He hot-spot ignition needs ρR 8-10 g/cm² at about 60 keV. D-T assistance needs 8 t of tritium per mission. |
| Does any combination have a converged mass and a plausible structure? | **No.** Every converged case relies on a spine whose estimated frame-FE first bending is 0.04-0.07 Hz, inside the slosh and ring-spin band (0.022-0.040 and 0.067 Hz). Every case with a plausible spine basis diverges. |
| Which architecture next? | Not more Vertex geometry. The binding problem sits upstream of the ship, in the pulsed D-³He target gain and the nozzle efficiency. The next study should compare the four-burn engine's non-ICF architectures with the same coupled closure, before any more layout work (§6). |
| Is an expensive simulation justified? | **D-21 MHD/PIC of A1: no.** It cannot unblock A1 (geometry) or the target (gain). **The 1D target rad-hydro study is justified only as a cheap falsification test** of the compression leg, with the acceptance criteria in §5. It needs workstation compute, not HPC. |

## 1. Task A: shield-cone feasibility (A1 at ≤ 7.5°)

### 1.1 What limits the cone (`cone.py` → `results/cone.json`)

The whole A1 field set is turned back by β so that the net thrust lies on the ship axis (vacuum field, thin shell). Rim limit = leak inner edge − 0.34° (the gate margin).

| tilt | β | leak centre ± radius | rim limit (leak) | C1 near side (polar, r) | C1 envelope polar | pair torque | beams at 3.75° |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 14° | 2.68° | 10.83 ± 2.99° | 7.50° | 8.68°, 9.77 m | 7.30° | 52.6 GN·m | 198-510 mrad |
| 15° | 2.88° | 11.65 ± 2.97° | 8.35° | 7.88°, 8.87 m | 6.49° | 60.1 GN·m | up to 557 mrad |
| 16° | 3.08° | 12.42 ± 2.98° | 9.09° | 7.08°, 7.98 m | 5.69° | 69.7 GN·m | up to 612 mrad |
| 18° | 3.51° | 13.92 ± 2.98° | 10.60° | 5.51°, 6.22 m (inside module r 6.5) | 4.12° | 104 GN·m | up to 764 mrad |
| 20-22° | | | | C1 passes through the module and bore | | invalid | |

- **Two limits pull against each other.** More tilt moves the leak outward by about 0.8° per degree. It also brings C1's near side toward the axis by about 0.8° per degree.
  - With the shield in C1's z band (62.4-65.7 m, the V4 layout), the rim must stay inside the C1 envelope: 7.30° at 14°. So 7.3-7.5° is the most A1 allows in that layout.
  - Moving the shield face about 3.5 m forward frees 15° up to 8.35°. That is lane T15.
  - 16° is the last tilt that clears the equipment module.
- **Torque, correcting T05's 152 MN·m.**
  - The thrust line is not 2.68° off the axis, because the turn is chosen to put the net thrust on the axis.
  - The residual torque is the angular momentum carried away by the reflected plasma: a 2.29 m lever at 14°, about 18-23 MN·m untrimmed.
  - A further nozzle turn of 0.32° (full tanks) to 0.63° (dry) puts the thrust through the centre of mass. It is trimmable.
- **New load: the static pair torque.** The loop field exerts 52.6 GN·m on the tilted C1/C2 pair at V4 scale, 74 GN·m on the coupled ships. The gate booked nothing for it. It is now booked as strut mass, 1.25 × 2ρτ/σ: 1.0-1.3 kt.
  - This is the same class of load the gate used to reject A2 (82 GN·m). A1 and A2 differ less than the gate stated.
- **New issue: driver-beam deflection.**
  - The V4 nozzle field already bends the 4 GeV beams by 116 mrad, uniform in azimuth. A1 makes it 198-510 mrad, varying with azimuth.
  - That is a static aim, but the chromatic spot shift (θ·Δp/p·L/2) grows about 4×, to about 17 mm at Δp/p = 10⁻³.
- **Correction to the gate (Task D):** the A1 thrust loss must be booked as η_T × (momentum factor)², i.e. 0.967. The gate applied the momentum factor itself (0.983). The calculator's nozzle_efficiency is η_T = η_mom².

### 1.2 The coupled matrix (`coupled2.py` → `results/matrix.json`)

Method: the gate's fixed-point loop, with the shadow geometry computed rather than assumed.
- **Shield rim:** FDP-1's own rule, rim = atan(tan θ_hw + 1 m/d_shield). The protected envelopes come from FDP-1, with the tank envelopes replaced by the variant farm.
- **Shield mass:** FDP-1's layered-shield formulas re-evaluated at the variant's cones. The gate scaled the whole shield; the crew core does not grow, so that over-counted.
- **Dust limit:** canon forward shield r 45 m, so the farm must stay at r 44 m or less (T05).
- **Spine:** N9 sized on the stated beam basis.
- **FE estimate:** beam cantilever × T05's FE/beam ratio. That ratio is 0.65 on short sections and 0.86-0.92 on long ones (`fe_cal.py`, T05 `gate2_fe.py`).

| variant | rim ≤ 7.5°? | status | departure | rate | launcher | farm (r × stretch) | spine added | est. FE f1 | remaining conflicts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G0: gate reference, wide farm, ff 0.2 | 10.60° no | CONVERGED | 145.8 kt | 489 Hz | 31.1 km/s, 1,647 m | 63.6 m × 275 m | 1.15 kt | 0.044 Hz | A1 limit, dust, C1 clash, spine in slosh/spin band |
| G0-noA1 | 8.52° (no A1) | CONVERGED | 83.6 kt | 381 Hz | 21.6 km/s, 790 m | 48.1 × 275 | 0.60 kt | 0.043 Hz | axis leak unsolved (342 J/cm²), dust, spine |
| G0-P: wide, cant 0.1 | 11.64° no | CONVERGED | 179.1 kt | 601 Hz | 38.3 km/s, 2,487 m | 70.5 × 275 | 2.85 kt | 0.065 Hz | A1 limit, dust, spine at 1× spin |
| K1: cone farm, ff 0.2 | 7.50° yes | NON-CONVERGING | > 400 kt | 1,000 Hz cap | 43.5 km/s | 43.2 × 765 | 18 kt and rising | 0.043 | spine runs away |
| K2: cone, cant 0.1 | 7.50° yes | NON-CONVERGING | > 1 Mt | cap | 52.9 km/s | 43.2 × 918 | 71 kt (tube at cap) | 0.049 | spine at cap |
| K3: cone, cant 0.2 | 7.50° yes | NON-CONVERGING | > 800 kt | cap | | 43.2 × 581 | 45 kt (cap) | 0.119 | spine at cap |
| S1: +100 m stand-off | 6.16° yes | NON-CONVERGING | > 1 Mt | cap | | 44 × 949 | 74 kt | 0.048 | spine, truss 0.7 kt |
| S2: +200 m | 5.63° yes | NON-CONVERGING | > 500 kt | cap | | 44 × 581 | 22 kt | 0.090 | spine, truss 3.5 kt |
| S3: +200 m, cant 0.2 | 5.63° yes | NON-CONVERGING | > 1.5 Mt | cap | | 44 × 918 | 72 kt | 0.051 | spine, truss 15 kt |
| T15: 15° tilt, shield +3.5 m | 7.54° (limit 8.35°) yes | NON-CONVERGING | > 1.6 Mt | cap | | 44 × 1,102 | 86 kt | 0.036 | spine |
| T15-S2: T15 + 200 m | 5.25° yes | NON-CONVERGING | > 690 kt | cap | | 44 × 612 | 32 kt | 0.090 | spine, truss 3.7 kt |
| N-V4: farm held at r 34.5 | 6.16° yes | NON-CONVERGING | > 1 Mt | cap | | 34.5 × 826 | 58 kt | 0.060 | spine |

Shielding margins (rim minus each protected envelope's half-angle), crew and hardware decades, thrust, torque, coil clearance and
every iteration are in `matrix.json` under `report`. Shield decades are FDP-1's own (hardware 3, crew neutron 10.7); no shielding
was reduced in any variant.

**Why every ≤ 7.5° case fails.**
- FDP-1 near V4 amplifies added mass about 14×: 4.1 kt of extras turns 58.7 kt into 117 kt in one step.
- A rim of 7.5° with the farm's near end at X 109 m allows a farm radius of 41.7-43.2 m. At the V4 stretch length that holds λ ≤ 1.57 of V4 propellant.
- The coils, launcher and A1 thrust loss alone push λ past 2. The stretch must therefore grow to 460-1,100 m.
- The spine mass for a long stretch grows faster than it lifts, so the loop gain exceeds 1 (3.8-11).
- **Aft stand-off does not rescue it:**
  - It lowers the rim (5.3-6.2°), but the farm is then capped by the r 44 m dust limit, not by the cone.
  - The new truss carries the drive as a tip mass, 0.7-15 kt.
- **Decision gate: no defensible, mass-converged configuration at ≤ 7.5° exists among those tested. A1 is geometrically blocked.**

## 2. Task B: fusion-target feasibility (`target2.py` → `results/target2.json`)

- **Compression energy verified.**
  - A first-principles degenerate electron gas (exact relativistic Fermi gas, x = p_F/m_e c = 0.11) gives 77.8 MJ for 0.772 g of D-³He at 2,000 g/cm³ and α = 1. The gate's Lindl scaling gave 78.5 MJ (ratio 1.008).
  - Exchange and a cold ion lattice would lower it to 62.7 MJ. That is a lower bound for strongly coupled cold ions, not an implosion.
  - Either way the figure is 37-47 % of the 168 MJ driver before any coupling loss.
- **Why 2,000 g/cm³.**
  - The density follows from FDP-1's own chain: burn fraction 0.671 → H_B 44.2 g/cm² (the four-burn engine at 100 keV, which also reproduces the burn fraction) → ρR 90.3 → ρ = (ρR)^1.5 / (3m/4π)^0.5 = 2,000.
  - At fixed ρR, the compression energy grows as m^(2/3) and the yield as m. Gain therefore rises only as m^(1/3).
- **Ignition** (0D power balance validated on D-T: ideal ignition 4.4 keV against the textbook 4.3; minimum hot spot 0.43 g/cm² at 7.5 keV):
  - D-³He ideal ignition is at 32.8 keV. The minimum hot spot is ρR 8.2-9.6 g/cm² at 59-65 keV, about 20× D-T.
  - The products' ranges at 60 keV and 2,000 g/cm³: alpha 3.4 g/cm², proton 27 g/cm².
  - **Central (isobaric) ignition:** the hot spot would weigh 4 g and hold 34,500 MJ, larger than the whole fuel. Impossible.
  - **Fast ignition at 2,000 g/cm³:** 7.8 MJ deposited in a 48 µm spot within 20 ps (3.9 × 10¹⁷ W). That is about 10⁴× beyond any existing ignitor, and a heavy-ion driver cannot make 20 ps pulses.
  - **D-T-assisted:** the spark needs 39 MJ of D-T yield per pulse: 0.23 mg of tritium per pulse, 8.2 t per mission, plus 6 GW of 14 MeV neutrons (30× V4). Not defensible.
- **Operating map** (yield fixed at V4's 182 GJ; ρR 10-90 g/cm², α 1-2, η_c 5-20 %, ignitor 10-30 %):
  - Best gain: 440 (ρR 90, α 1, η_c 0.20, ignitor 30 %).
  - Best with η_c ≤ 0.15 and α ≥ 1.5: 227.
  - Lower ρR makes ignition worse: ρR 40 gives gain 285; ρR 20 gives 34.
- **Gain the ship can live with** (FDP-1 V4, no coupled extras):
  - Closure needs gain ≥ 703. At 842 the departure is 83 kt; at 703 it is 1.4 Mt.
  - Even with a free ignitor, closure needs driver-to-fuel coupling η_c ≥ 0.30 at α = 1, 0.45 at 1.5, 0.60 at 2.
  - Published heavy-ion direct-drive designs quote about 0.10-0.20 (a literature range, not verified here).
  - The coupled extras raise the threshold further.
- **Inert mass.** The exhaust velocity falls as 1/√(1 + m_inert/m_fuel): ×0.75 for the Rev 4 HDC wall, ×0.53 for a range-matched ablator.
- **Analytically feasible:** none at the ship's gain.
- **Experimental speculation:** compression coupling above 0.3; a 10¹⁷ W, 20 ps ignitor; D-³He burn propagation from a D-T spark.

**Verdict: no fusion-target operating point is physically defensible under the evaluated assumptions.**

## 3. Task D: model reliability

- **G1 resolved as a model artefact** (`g1.py`). The ledger converges in resolution: η_T 0.791 at 1° (the V4 value), 0.697 at 0.5°, and 0.670-0.674 from 0.25° to 0.06°. Doubling n_rho changes nothing.
  - The forward reflection comes from 120-150° polar: sub-2 m kinks of the aft stopping surface.
  - The shell is 5-15 m thick (10-30 % velocity spread at a 48 m stopping radius) and cannot reflect specularly off them.
  - Smoothing on the shell scale (2-8 m) gives η_T 0.80-0.82.
  - Thin-shell band: 0.67 (artefact bound) to 0.82. The physically meaningful thin-shell value is about 0.80. It is not demonstrated (D-21).
- **Momentum vs energy.**
  - The calculator's η_T is a thrust efficiency, η_mom².
  - A1's loss belongs in η_T as the momentum factor squared (§1.1).
  - The energy that leaves clean but off-axis is not thrust, and the gate's single-factor booking under-counted it.
- **Lower nozzle performance and mass convergence** (`eta.py`, matrix D-rows):
  - V4 alone: 32.7 kt at η_T 0.82, 42.9 kt at 0.791, 58.6 kt at 0.765, 122 kt at 0.72, 451 kt at 0.67. Closure threshold 0.63.
  - Coupled ship without A1: 74.9 kt at 0.80, 83.6 kt at 0.791; it diverges at 0.72.
  - Coupled ship with A1: 125 kt at 0.80, 146 kt at 0.791; it diverges at 0.72.
  - The ship needs η_T ≥ about 0.75 coupled. The 0.791 must not be treated as demonstrated.
- **Validity of the analytical plasma model** (`validity.py`):
  - Bulk-ion Larmor radii at the surface field are a median 0.4 m, at most 7.5 % of R, so the fluid picture holds.
  - 14.7 MeV protons reach 11 % of R where the field is weak, which is marginal (kinetic).
  - Rm ≥ 5 × 10⁶, so the field is frozen in.
  - Outside the model: lateral flow toward field zeros, Rayleigh-Taylor, detachment, velocity spread.
- **Mathematical vs engineering convergence.** G0 (146 kt) and G0-noA1 (84 kt) converge mathematically. Neither is an engineering-feasible ship:
  - the rim is above the A1 limit, or the axis leak is unsolved;
  - the farm is r 48-64 m against the canon r 45 dust shield;
  - the C1 envelope clashes with the shield;
  - the spine's FE estimate is 0.043 Hz, between the slosh band and 1× ring spin.

## 4. Structure (with T05's Gate 2 FE)

- T05's parametric frame FE (`gate2_fe.py`) puts the r 41.7 m section's saturation at about 0.13 Hz, so 0.2 Hz is unreachable at any mass.
- With tied saddles, the practical window is FE free-free 0.077-0.113 Hz (clear of 1× and 2× spin by ± 15 %); the r 41.7 m section reaches 0.087 Hz at 4.3 kt.
- The beam model agrees with the FE to within 8-14 % on long stretches (cantilever ratio 0.86-0.92) and is 35 % optimistic on the short V4 section (0.65) (`fe_cal.py`).
- The ≤ 7.5° divergence holds on every basis down to T05's practical target. It is a mass-loop failure, not a choice of criterion.

## 5. Candidate simulations and their decision value

| study | resolves | decision value now | recommendation |
| --- | --- | --- | --- |
| D-21 MHD/PIC of the A1 tilted leak | funnelling into the moved zero; real η_T (G1 band 0.67-0.82) | none while A1 is geometrically blocked and the target cannot reach gain 703 | **Do not run.** Revisit only if both blockers lift. |
| 1D radiation-hydrodynamics of the FDP-1 target | driver-to-fuel coupling η_c and the achieved adiabat α for a heavy-ion direct-drive D-³He target | moderate: a cheap test of the compression leg, the one number the analysis has to take from literature | **Justified as a falsification test only**, if the owner wants Vertex kept open |

**1D study definition (proposed, not run).**
- **Solver:** a 1D Lagrangian radiation-hydrodynamics code with:
  - tabulated EOS (SESAME/QEOS class) for D-³He and the ablator;
  - multigroup diffusion radiation;
  - flux-limited Spitzer-Härm electron conduction;
  - an ion-beam deposition package (Bethe stopping in hot, partly ionised matter);
  - charged-product transport for alpha and 14.7 MeV protons.
  - Candidates: MULTI-IFE (open source) or HELIOS (commercial). Confirm each one's ion-beam deposition capability before choosing; adding it is part of the study if needed.
- **Physics left out:** asymmetry, mix and fast ignition. A 1D code cannot test the ignitor.
- **Boundary conditions:**
  - spherical capsule;
  - FDP-1's 0.772 g D-³He and 168 MJ of 4 GeV Bi⁺ (the species is an assumption);
  - ablator thickness, pulse shape and radius as scan variables;
  - free outer boundary.
- **Validation:**
  - reproduce a published 1D direct-drive DT capsule (implosion velocity, adiabat, ρR, gain);
  - check beam deposition against SRIM/Bethe tables;
  - check the cold-fuel energy against the 77.8 MJ here.
- **Compute:** about 100-300 runs of minutes each on a workstation. No HPC or external allocation.
- **Acceptance criteria:**
  - **pass:** fuel internal energy ≥ 0.30 × driver at α ≤ 1.2, with ρR ≥ 90 g/cm² at stagnation, for some realisable pulse;
  - **fail:** coupling below 0.25 across the scan, which closes the target question for this ship;
  - either way the ignitor stays an open, unproven requirement.
- **Expected outcome:** fail, given the literature range.

## 6. Which architecture next

- The Vertex blocks are not layout problems. Three would remain even with perfect geometry:
  - FDP-1 needs a target gain of 703 or more, while the analysis supports 440 at best;
  - D-³He ignition needs a 10¹⁷ W, 20 ps ignitor;
  - the nozzle needs η_T ≥ 0.75, which is not demonstrated.
- Twin splayed nozzles (lane C, T05 Task C) move the leak beside the ship. They do not touch these three blocks, and their doubled coil hardware is amplified about 14× by the same mass loop.
- **Recommendation:** pause Vertex geometry. Run a like-for-like closure of the four-burn engine's continuous-burn architectures (IFD-C central and optimistic) through the same coupled-ship method:
  - coil and shield hardware;
  - spine stiffness on T05's FE basis;
  - the dust limit;
  - the 14× amplification check.
- Those architectures avoid target compression and ignitors. Their open physics is τ_p and wall flux, which the four-burn study already tiers.
- This does not invent a Fiji capability, and it may well show that no four-burn 0.016 c ship closes at any tier. That would be the honest answer to carry back to the mission requirements.

## Files

- `g2.py` (paths)
- `cone.py` → `cone.json`
- `coupled2.py` → `matrix.json` (each variant: the eight report items and every iteration)
- `target2.py` → `target2.json`
- `g1.py` → `g1.json`
- `eta.py` → `eta.json`
- `validity.py` → `validity.json`
- `fe_cal.py` → `fe_cal.json`
- `test_gate2.py`: 9 checks, all OK. They cover Bosch-Hale against the table, the Fermi gas against Lindl, D-T ignition 4.3 keV, the shadow-cone and shield formulas reproducing FDP-1, η_T at 1° = 0.791, ledger convergence, honest statuses and the canon guard.
