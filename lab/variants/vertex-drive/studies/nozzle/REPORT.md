# T03 report: magnetic nozzle, helical fields and energy recovery

| | |
| --- | --- |
| Thread | T03, plasma physics and electromagnetic propulsion (Vertex Phase 1) |
| Date | 2026-11-09 |
| Base | `8de3ffa`, generation V1 (FDP-1 calculator, 10,416 t, 107 Hz, 81 GJ pulses, 8.0e10 J of plasma per pulse at 21,600 km/s rms) |
| Scope | Analytical, vacuum-field, field-line and test-particle work (D-PLAN-1). No self-consistent MHD or PIC (D-09 not approved). |
| Status | Research only. Nothing here changes canon, `data/`, `src/`, the registry, the calculators or Drive. |

Labels: PUBLISHED, MODEL, EXTRAPOLATION, ASSUMPTION, TARGET, FICTIONAL, UNKNOWN (as `planning/HANDOFF.md`). Every MODEL number is
reproduced by the scripts in this folder (section 9); the field maps are in `results/` as data.

## Summary

- **Efficiency definition.** The 0.79 that FDP-1 and the Atlas call "the theoretical bound for beta >> 1 nozzles" comes from NASA MSFC
  (Thio et al. 1999) and is a **momentum** efficiency. The calculator uses it as an **energy** (thrust) efficiency. Read
  consistently, 0.79 is 0.62 and V1 is 39.7 kt; the published simulations (about 0.55-0.70 momentum) do not close.
- **Stored field energy.** FDP-1 stores one joule of field per joule of pulse. In every coil set modelled here, the pulse can't be
  turned efficiently below about 10 joules of field per joule of pulse; the best case is about 15. Virial coil structure rises from
  86 t to about 0.9-1.3 kt.
- **Geometry.** The FDP-1 three-loop cup (A) leaks about 20% of the plasma forward along the field axis, onto the shield and the
  ship. Two forward closure coils on the X-ray stand-off sphere (C) close the leak: momentum efficiency 0.86-0.89 (energy 0.74-0.79)
  in an ideal model. The coupled best case is **V1 at 22.7 kt** (2.2x). That is an upper bound, because the model has no
  instabilities.
- **Helical fields.** Clocked sectors (B) twist the field at the stopping surface by under about 1° of shear. That is harmless and
  useless. Helical windings that reach useful shear (18-50°) cost 10-20 points of momentum efficiency and add 0.3-0.7 MN·m of roll
  torque. "Balanced" windings (D) don't cancel the torque robustly in this model. Shear and collimation conflict, and the
  stability benefit is unproven.
- **Recovery.** VTX-02C has to extract only 0.13-0.20% of fusion power for the electric load. This is booked once, upstream of the
  nozzle, as the calculator already does. The real recovery hardware question is different: the superconducting windings must be
  screened from the per-pulse current swing of about 5%, or they dissipate about 7 GW at 20-40 K.
- **Worth pursuing:** the axisymmetric shaped nozzle C (forward closure coils, optimised currents). **Not worth pursuing as a
  performance feature:** clocked-sector helicity (B), one-handed helical windings (C3D), and helical windings "balanced" by reversing
  the twist (D). **What decides it:** a D-09 pulsed-plasma simulation of A vs C (and C with a helix) that reports thrust (energy)
  efficiency, plume on hardware and Rayleigh-Taylor mixing. Success means eta_T ≥ 0.70 for C at ≤ 15 E_p with ≤ 2% of the plasma
  on hardware.

## 1. Nozzle efficiency: definitions and literature

### Definitions

| Symbol | Definition | Notes |
| --- | --- | --- |
| eta_mom (momentum, "nozzle efficiency" in Thio) | net axial momentum / sum of the magnitudes of the particles' momenta, sum m v_z / sum m \|v\| | for a monoenergetic shell = mean cos theta |
| eta_div (divergence) | F / (mdot v) for the jet that leaves | equal to eta_mom when no mass is lost |
| eta_T (thrust efficiency) | F² / (2 mdot P_in) | the quantity that sets the effective exhaust velocity in the rocket equation: P_jet = ½ mdot (F/mdot)² = eta_T P_in |
| eta_E (axial energy) | sum ½ m v_z² / E | = mean cos² theta; not the rocket quantity |
| eta_det (detachment) | share of the plasma that leaves the field without returning | multiplies the others |

For an elastic, speed-preserving nozzle, eta_T = eta_mom² × (mean v)² / (mean v²). This is ≤ eta_mom², with equality for a single
speed. The thin-shell model is monoenergetic, so eta_T = eta_mom². A velocity spread lowers it further: T04's self-similar profile
gives (mean v)²/(mean v²) ≈ 0.94 (ASSUMPTION: uniform sphere, v ∝ r, mean v = 3/4 v_max, mean v² = 3/5 v_max²).

**Which one the calculator uses:** `lab/studies/four-burn-mission/fourburn/architectures.py::_pulse` sets `jet = eta_n x stream` and
the mission velocity `ve = sqrt(2 eta_jet b eps)`. So `nozzle_efficiency` is eta_T (multiplied by the detachment share, which the
calculator doesn't separate). Any published momentum efficiency has to be squared before it is booked.

### Literature

| Source | Value | Definition | Conditions | Verification |
| --- | --- | --- | --- | --- |
| Thio, Freeze, Kirkpatrick, Landrum, Gerrish, Schmidt, "High-Energy Space Propulsion Based on Magnetized Target Fusion", AIAA 99-2703 (NASA MSFC, 1999), NTRS 19990080042 | about 0.80 achievable; 0.863 theoretical maximum (parabolic flux-compression nozzle, half-angle 45°); 0.789 with losses is attributed to Thio in summaries | momentum: "converting the spherically radial momentum of the fusion plasma to an axial impulse" | analytic flux-compression model, MTF pulses | SECONDARY: abstract and two independent summaries; the full text was not reachable from this container (ntrs.nasa.gov, arxiv.org blocked) |
| Nagamine and Nakashima, Fusion Sci. Technol. 35 (1999) 62-70 | 0.65 | "thrust efficiency in terms of momentum" | 3D hybrid PIC of a laser-fusion magnetic thrust chamber; RT present, effect "limited"; optimum coil angle about 50° | SECONDARY (abstract) |
| Matsuda, Maeno, Kajimura, Nakashima, JPFRS 8 (2009) | 0.67 | thrust efficiency (definition not seen) | shaped target, 3D hybrid | SECONDARY |
| Inatomi et al., Plasma Fusion Res. 18 (2023) 1404080 | | | thrust efficiency independent of plasma energy, species and propellant mass (3D hybrid) | SECONDARY |
| Cassibry, "Pulsed Magnetic Nozzle for Fusion Propulsion", JBIS 71 (2018) 119-125; UAH theses | z-pinch linear nozzle 0.55; hemispherical "could be over 70%"; power-generating nozzle 0.34 | not confirmed (UAH work uses Thio-style internal efficiency) | SPH/MHD, some runs stopped before the plasma left | SECONDARY (S-CASSIBRY-PMN) |
| NASA PuFF slides (Adams et al.) | about 0.70 at Isp 6,500 s | not stated | MSFC pulsed nozzle study | SECONDARY |
| Schilling, Cassibry, Adams, JBIS 76 (2023) 70-76 | power generation costs 7% of nozzle efficiency and of thrust | as their nozzle efficiency | pulsed fission-fusion | SECONDARY (abstract) |
| Romanelli, Mignone, Cervone, Acta Astronautica 139 (2017) 528-544 | no asymptotic value reached | | 2D ideal MHD (PLUTO / Nautilus) of a multi-coil parabolic chamber; relativistic Alfvén speeds broke ideal MHD; Hall or relativistic MHD "mandatory" | SECONDARY (abstract, citing paper) |
| Maeno et al. (2011-2013), laser magnetic thrust chamber | impulse measured, 1.5-2.2 µN s at 0.7 J; 0.02-10 mN s at 30-900 J | impulse, not efficiency | the only experiments; µs plasma, permanent magnets and coils | SECONDARY |

**Assessment.** No experiment has measured a pulsed magnetic nozzle efficiency at any scale. Simulations put momentum efficiency at
about 0.55-0.70. Thio's analytic maximum is 0.86 (momentum). Read as thrust efficiency, these are 0.30-0.49 and 0.74. FDP-1's 0.79 is
above every published energy-equivalent value. **S-MSFC-NOZZLE should be re-identified as Thio et al. 1999**, with its definition
recorded (registry proposal S-T03-THIO-1999).

### Calculator consequences (MODEL, `calc_rerun.py`, `results/calculator_reruns.json`)

| Booked eta_T | Basis | V1 departure t |
| --- | --- | --- |
| 0.790 | FDP-1 as booked | 10,416 |
| 0.745 | Thio maximum 0.863, squared | 12,118 |
| 0.624 | 0.79, squared | 39,715 |
| 0.600 | probe | 78,626 |
| 0.550 | probe | 2,256,043 |
| 0.490 / 0.423 | 0.70 / 0.65 momentum, squared | does not close |

The "cliff" of 0.528 in `CONVERGENCE.md` is an asymptote. Mass doubles between 0.745 and 0.68 and reaches megatonnes by 0.55. The
practical cliff is about 0.62-0.65.

## 2. Field and plasma models

1. **Vacuum fields** (`fields.py`): exact coaxial loops (elliptic integrals), finite-segment Biot-Savart for sectors, gap leads and
   helical windings, Maxwell mutual inductance, ring self-inductance, hoop tension.
2. **Flux-excluding bubble** (`multipole.py`): the burn-point multipole expansion of the loops. A perfectly diamagnetic sphere's
   surface field and the exact work to expand it with fixed coil currents are
   W(b) = (2π/µ0) Σ a_l² l b^(2l+1)/(l+1). In a uniform field this is 1.5 × B²/2µ0 × volume.
3. **Thin-shell reflection** (`shell.py`): each solid-angle element of the shell stops where its work against the surface magnetic
   pressure equals its energy share, then reflects specularly. The output is the stopping surface R(θ), eta_mom, eta_T and the rays
   that strike hardware: loop tubes of 0.5 m, the shield face, or "forward along the ship" for any outgoing ray with a forward
   component. **Limits:** it is elastic, ideal and has no thickness. It leaves out lateral flow, the coils' flux-conserving current
   rise (which helps a little), instabilities, resistivity, reconnection and the energy carried out by stretched field lines. Its
   efficiencies are upper bounds.
4. **Perturbations** (`perturb.py`): 3D vacuum fields of sector gaps, differential sector currents, lost sectors and helical windings
   at the unperturbed stopping surface. The model computes the first-order shift of the surface, 3D normals, reflection, roll torque
   and side force. Torque is a second-order effect and is noisy at the 1e3 N·m level. Ripple above about 30% (the helices at ≥ 5 MA)
   is beyond first order.
5. **Test particles** (`particles.py`): Boris pusher in the vacuum field, for the low-beta tail, late debris and duds. The results
   match the adiabatic loss-cone prediction: 31% vs 34% for A, 4.6% vs 5.5% for C.

Validation (`test_nozzle.py`, 11 tests, about 20 s): on-axis loop field; the loop vs a 3,600-segment Biot-Savart (2e-5); ∇·B = 0 and
B_z = (1/r) ∂ψ/∂r; mutual inductance vs the far dipole and vs the flux function; field energy by quadrature vs L I²/2 (5%); the
multipole expansion vs exact fields (1e-6); the uniform-field bubble (3/2 factor, surface field 1.5 B); dW/db = surface-pressure
integral; one Boris gyro-orbit closes; mirror reflection inside and outside the loss cone.

## 3. Architecture comparison A-D (V1 geometry, optimised currents, W = stored field / pulse plasma energy)

Thin-shell MODEL, upper bounds. "On hardware" = share of the plasma striking the shield, coils, or flying forward along the ship.

| Design | W/E_p | eta_mom | eta_T | On hardware | Forward leak (unstopped) | Coil structure (virial, t) | Envelope solid angle |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A, FDP-1 loops, equal currents | 10 | 0.651 | 0.423 | 23.2% | 14.3% | 855 | 0.030 |
| A*, three loops optimised | 3 / 10 / 30 | 0.497 / 0.678 / 0.660 | 0.25 / 0.46 / 0.44 | 24 / 22 / 17% | 12% at 10 | 257 / 855 / 2,561 | 0.033 at 10 |
| **C, + forward closure coils at 20°, 40°** | 3 | 0.541 | 0.293 | 20.2% | | 257 | |
| C | 6 | 0.768 | 0.589 | 2.1% | 0.3% | 513 | 0.038 |
| C | 10 | 0.860 | 0.740 | 1.6% | 0.3% | 855 | 0.040 |
| **C** | **15** | **0.889** | **0.791** | **1.4%** | 0.15% | 1,281 | 0.051 |
| C | 20 / 30 | 0.886 / 0.882 | 0.786 / 0.779 | 1.8 / 2.6% | | 1,707 / 2,557 | |
| B (A or C + clocked sectors, 5% trim) | as base | ±0.000 | ±0.000 | ±0 | | as base | as base |
| B, 20% trim | as base | −0.005 (C) | −0.009 | +0.5 pt (A) | | as base | as base |
| C3D (C + l = 2 helix, 2 / 5 / 20 MA) | 10 + helix | 0.826 / 0.760 / 0.633 | 0.68 / 0.58 / 0.40 | rises to 18% at 20 MA | | + helix | + helix conductors in the sky |
| D (balanced helix, same currents) | 10 + helix | 0.827 / 0.763 / 0.638 | 0.68 / 0.58 / 0.41 | as C3D | | + helix | as C3D |

Coupled to the calculator (V1 overrides plus each C design's eta_T, W/E_p and plume-strike share of the loss; `calc_rerun.py`):

| C design | 3 E_p | 6 E_p | 10 E_p | 15 E_p | 20 E_p | 30 E_p |
| --- | --- | --- | --- | --- | --- | --- |
| V1 departure | no closure | 1.03 Mt | 30,949 t | **22,683 t** | 30,269 t | 51,283 t |
| plume-strike share of the loss booked | 0.29 | 0.05 | 0.06 | 0.07 | 0.09 | 0.12 |

The Nelder-Mead optimiser is local (C at 30 E_p came out below C at 15). These are achievable values in the model, not its global
optimum.

### Verdicts

- **A (FDP-1 three loops): not viable as drawn.** Near the axis the field runs parallel to the plasma's motion, so the shell is not
  stopped there. Polar angles below about 40° pass through loop 1's 37 m bore toward the shield and the ship, and the reflection
  off a nearly spherical stopping surface sends more forward. The best eta_mom found is 0.68. The low-beta tail and duds also stream
  into the shield centre: the mirror ratio is only 1.16, so 31-34% of that mass lies in the loss cone. The FDP-1 geometry is a sound
  starting envelope, but its currents and its open forward aperture are not.
- **B (clocked sectors): harmless, no benefit.** The 5° gaps give 1.4% peak ripple and 0.25-0.4° of field rotation at the stopping
  surface. A 5% differential (m = 2) trim gives 0.9-1.1°, and 20% gives 3-3.7°. Efficiency is unchanged to 0.5 points. Roll torque is
  1-3 kN·m at 5% trim and 6-28 kN·m at 20% (RCS couple 26 kN·m). Keep the sectors for slow vectoring, fault tolerance and
  replacement (T02), not for helicity. With four sectors the differential pattern is m = 2 (alternating sign) and the gap ripple is
  m = 4. A 45° clock reverses the m = 4 ripple loop to loop, which carries no handedness, and advances the m = 2 trim by 90°. The
  Atlas's "m = 4 helical harmonic" is therefore inexact (registry proposal).
- **C (shaped, axisymmetric): the only configuration worth developing.** A point source at the focus is collimated best by an
  axisymmetric paraboloidal stopping surface. Any non-axisymmetric component tilts normals out of the meridian plane and can only
  add divergence. The shaping freedom that matters is therefore the axisymmetric current distribution plus closure of the forward
  aperture. The cost is a large forward coil (C1: 80-132 MA, hoop tension 3-7 GN, envelope 2-3 m, solid angle 0.015-0.025), placed
  2.6 m aft of the shield face and outside its rim.
- **C3D (non-planar shaping): not recommended.** Helical windings buy shear only by deforming the stopping surface. Its eta_mom loss
  is about 10 points per 18° of shear. The conductors lie in the burn's sky between the loops, and the torque exceeds the RCS couple
  by 10-30x.
- **D (balanced helicity): necessary but not sufficient.** Any helical field must be balanced (D-01 stands). Reversing the twist at
  L2 cancelled the torque only at 5 MA (2.7e4 N·m) and not at 2 or 20 MA (0.24 and 0.57 MN·m). The two halves stop the shell at
  different radii and depths, so a geometric reversal doesn't balance the angular momentum flux. A usable D would need pulse-by-pulse
  torque measurement and trim. Its efficiency cost is that of C3D.

## 4. Instabilities, leakage, detachment

- **Rayleigh-Taylor / interchange at the plasma-field boundary (MODEL, analytic).** The magnetic field pushes the plasma during both
  deceleration and re-acceleration, so the interface is RT-unstable throughout the pulse. The field lines bulge around the bubble,
  so the curvature is bad. For a thin shell, gamma² = g k (1 − 2 sin²ψ), where ψ is the angle of k from the direction perpendicular
  to B. Modes within 45° of B are tension-stabilised; flutes perpendicular to B grow at the full rate. The e-folds per phase are
  sqrt(2 l Δ/R), with stopping depth Δ ≈ R/3. At the finite-Larmor-radius limit (l ≈ 70, wavelength ≈ 2.5 m, He-4 gyroradius about
  0.6 m), that is about 7 e-folds per phase and 13-14 per pulse, so a 1e-6 seed goes nonlinear. Linear theory therefore predicts a
  mixing layer of metre scale every pulse. Nagamine and Nakashima's 3D hybrid PIC found the efficiency effect "limited" (0.65
  momentum). Which picture holds at 80 GJ is the core D-09 question.
- **Shear stabilisation needs tens of degrees** of field rotation within a wavelength of the interface. B supplies about 1°. The
  target's own seed field, compressed and then frozen into the expanding shell, decays to about 1e-7 T at 25 m (flux conservation
  from 1e4 T at 0.1 mm) and contributes nothing (EXTRAPOLATION).
- **Kink**: it needs a current along the plasma. The nozzle field drives none, and D-01 forbids the net twist that would. It is not
  a nozzle mode here.
- **Off-axis leakage**: covered by the thin-shell strike shares above. Magnetised ions (gyroradius 0.3-0.6 m at 0.7 T) never reach
  the coils in the vacuum field (test particles: 0% coil hits).
- **Low-beta tail, duds**: these follow the axis field lines. The forward loss cone goes field-aligned to the shield centre: 34% (A),
  5.5% (C), independent of species and of speed down to 0.1 v. A T04 dud (27 MJ, 400 km/s) behaves the same way. The C1 coil is
  also the shield's plasma plug (mirror ratio 5.7-7.6).
- **Detachment**: in the vacuum field the aft-going magnetised tail leaves with mean cos θ = 0.998 and demagnetises about a kilometre
  aft (r_L > L_B). The main shell is beta >> 1 everywhere outside its stopping surface: plasma energy density falls as r^-3 and
  field energy density as r^-6. It drags field lines out and detaches by stretching and reconnection. The flux it carries away, and
  the energy the coils lose with it per pulse, is **UNKNOWN** and needs resistive or Hall MHD (D-09).

## 5. Maxwell stresses, forces, struts (MODEL, `results/nozzle_results.json` → `stresses`)

C at 15 E_p (W = 1.2e12 J):

| Coil | I MA | Hoop tension (self) MN | Net radial from others MN | Net axial from others MN (+ = toward bow) |
| --- | --- | --- | --- | --- |
| C1 @20° | 132 | 6,920 | +7,978 | −1,856 |
| C2 @40° | 10.6 | 80 | +316 | +401 |
| L1 | 17.0 | 200 | +965 | +566 |
| L2 | 24.9 | 442 | +762 | +244 |
| L3 | 29.0 | 631 | +51 | +645 |

- The loops attract each other along the axis with forces of 0.2-1.9 GN, and the struts must carry them as compression between
  loops. Most of the forward coil's load is self-hoop and is carried in the winding pack. The virial minimum mass,
  ρW/σ = 1,281 t at FDP-1's optimistic 1.07e-6 kg/J, already includes this.
- **Pulse loading:** each pulse delivers 6.6 kN·s (thrust/rep) in a few microseconds. Flux conservation swings each coil current by
  about E_p/(2W), which is 3-5%, so the magnetic loads cycle by 7-10% about 1.9e10 times over the 5.7 y of thrust. This is a fatigue
  requirement outside any coil database (EXTRAPOLATION). T05 and structures should treat the coil packs as fatigue-designed.
- **Reaction torque:** zero for axisymmetric designs. 1-30 kN·m for B with 5-20% trim (mirror-symmetric patterns cancel exactly).
  0.24-0.7 MN·m for helices.
- **Trim power (D-03):** with W = 1.2e12 J, a 1% trim in 5 ms takes about 4.8 TW, 14x D-03's 340 GW. D-03 stands, strengthened.

## 6. Coupled energy accounting (booked once)

Per pulse of fusion energy, in the order the calculator books it (V1 shares; MODEL):

1. Escaping radiation: 1.15% X-rays plus 5.5e-6 neutrons (T04). Not plasma.
2. **Recovery extraction (VTX-02C):** P_ext = P_e/eta_r, taken from the plasma before the nozzle. P_e = 1.24e-3 of fusion (driver
   loss 4.1e-4, beam 3.3e-4, house 5.0e-4, cryo). Extraction is **0.13% of fusion** (eta_r 0.95) to 0.20% (driver efficiency 0.30,
   eta_r 0.80). The loss (1 − eta_r) × P_ext goes to the hot loop. It can't be credited again: whatever is extracted is missing from
   the stream the nozzle turns.
3. **Nozzle:** jet = eta_T × (stream − P_ext). The loss (1 − eta_T) × stream leaves as divergent or forward plasma. Of that loss,
   0.06-0.07 strikes hardware in C (0.02 in the calculator).
4. **Field compression work:** the compression returns to the plasma within the pulse. It is not a loss in the elastic model and is
   already inside eta_T. In reality the irreversible part (screen eddy losses, field energy dragged out by detachment) is a loss of
   about 0.1% of plasma (screens, EXTRAPOLATION) plus an UNKNOWN detachment term.
5. **Coil heating:** screen dissipation about 0.1% of plasma (8.6 GW, band 0.03-1%) to the hot loop. The unscreened superconductor
   pulse loss (6-10 GW at 20-40 K, Bean estimate, ×10 band) is not acceptable and is a design requirement on the screens, not a
   ledger item. Coil armour radiation scales with the solid angle: 0.040-0.051 against V1's 0.017, so 2.4-3.0x
   radiation_on_hardware.

**Handed to T01: one recovery fraction.** Extraction 0.0013 of fusion (bounds 0.0012-0.0020), recovery efficiency 0.80-0.95
(ASSUMPTION), loss to the hot loop. No extra recovery credit. The coupling to eta_T is second order at this size. Schilling et al.'s
7% penalty applies to a nozzle designed to power its own vehicle, with an extraction share UNKNOWN to T03.

## 7. Mechanical and 3D integration requirements (for T05, T00)

- **Nozzle frame to ship:** x = x_burn + z. V1 x_burn ≈ −227.5 m (PARAMETRIC_PLACEHOLDER). The coil table is in `EARLY.md` section 2
  (C at 10 E_p) and `results/nozzle_results.json` (every design).
- **Draw for C at 15 E_p (recommended review geometry, PARAMETRIC_PLACEHOLDER):**

  | Coil | Polar | Loop r m | z m | Winding r m | Envelope r m |
  | --- | --- | --- | --- | --- | --- |
  | C1 | 20° | 14.74 | +40.51 | 1.06 | 3.2 |
  | C2 | 40° | 27.71 | +33.03 | 0.08 | 0.25 |
  | L1 | 60° | 37.34 | +21.56 | 0.14 | 0.41 |
  | L2 | 90° | 64.67 | 0 | 0.20 | 0.60 |
  | L3 | 120° | 112.01 | −64.67 | 0.23 | 0.70 |

  The envelope is 3x the winding (FDP-1 factor) plus burn-facing armour shoes. C1 sits immediately aft of the shield face (z = 43.1 m,
  rim 6.0 m), so it can hang from the shield frame. The other coils keep FDP-1's chain struts (L3 → L2 → L1 → shield frame), sized
  for 0.2-1.9 GN axial attraction plus the 7-10% fatigue cycle.
- **Sectors:** keep four per loop for fault tolerance. Joints are at the clock angle + 45° + 90° q. Each sector needs its own feed
  and a warm eddy-current screen around the winding (VTX-02C pickup = screen).
- **Field-line overlay:** `results/field_lines.json` (A, A*, C at 10 E_p; r-z half-plane; ILLUSTRATIVE).
- **Remove from the drawing:** nothing physical. The "helical capture" depiction should be shown as a sector clock, not as a helix.

## 8. D-09 study plan (for ApeDevil's decision; not run)

Test particles and the thin-shell model don't capture collective plasma behaviour: diamagnetic currents, the field's response, RT
mixing, reconnection, detachment, or the shell's velocity spread. Every efficiency in this report is a vacuum-field upper bound.

- **Question:** for the V1 pulse (80 GJ, 0.34 g, D/He-3/He-4/p, rms 21,600 km/s, self-similar), what are eta_T, the plume on
  hardware and the angular momentum flux in A, C (15 E_p) and C plus a 5 MA balanced helix?
- **Codes (open source first):**
  - Hybrid PIC (kinetic ions, fluid electrons): **HYBRID-VPIC** or **dHybridR**. These have a finite Larmor radius, capture RT/FLR
    and demagnetisation, and are the closest analogue of Nagamine and Nakashima.
  - Hall / resistive MHD with Alfvén-speed limiting: **PLUTO** (relativistic MHD and Boris correction, the code family Romanelli used),
    or **Athena++**.
  - Commercial alternatives: **USim/Nautilus** (TechX), **LSP/Chicago**.
- **Physics:**
  - Two-temperature plasma, adiabatic expansion from a 1 m initial sphere.
  - Coils as flux-conserving circuits, with inductance from this folder's matrix.
  - A vacuum background floor of ≤ 1e-6 of the shell density, with Alfvén speed capped at c (the ideal-MHD failure Romanelli
    reported).
  - Resistive screens as thin conducting shells.
  - Hall term on. Radiation is not needed: X-rays have already left.
- **Domain and resolution:**
  - 2D axisymmetric r-z, 0-300 m × −600 to +60 m, with Δ = 0.1-0.25 m (less than the ion gyroradius), about 3-20 Mcells. 3D for the
    helix cases: 0.5 m over a 300 m cube gives about 2e8 cells, or a 90° wedge with periodic boundaries.
  - Time to 60 µs (shell out past 600 m), Δt limited by the electron cyclotron frequency in Hall MHD or by the ion cyclotron frequency
    in hybrid PIC.
- **Compute estimate (EXTRAPOLATION):**
  - 2D Hall MHD: about 1e3-1e4 core-hours per case.
  - 2D hybrid PIC (100 particles per cell): about 1e4-1e5 core-hours.
  - 3D hybrid: about 1e6-1e7 core-hours. That needs an HPC allocation; it can't be done in this container.
  - Minimum campaign: 3 configurations × 3 energy ratios × 2 codes in 2D plus 2 cases in 3D, about 2-10 million core-hours.
- **Validation cases:**
  1. A diamagnetic cavity in a uniform field: bubble radius and 3/2 energy factor (this folder, analytic).
  2. Laser-plasma expansion into a magnetic field: LAPD (Collette, Gekelman) and Osaka GEKKO magnetic-thrust-chamber impulse (Maeno
     2011-2013).
  3. Nagamine and Nakashima's 0.65 momentum case.
  4. The single-loop test-particle loss cone from this folder.
- **Result that would count:**
  - Real benefit of shaping: C reaches eta_T ≥ 0.70 (eta_mom ≥ 0.84) at ≤ 15 E_p, with ≤ 2% of the plasma on hardware. That keeps
    V1 at or below about 31 kt.
  - Real benefit of a helix: at equal stored energy, C with a balanced helix beats plain C in eta_T by more than the run-to-run
    scatter (≥ 0.02), with residual roll torque ≤ 10 kN·m.
  - **Decisive negative:** C below eta_T 0.62, or RT mixing pushing more than 5% of the plasma into the field region, would put every
    V1-class Vertex above about 40 kt. Pulsed magnetic nozzles would then be ruled out as a mass lever.

## 9. Reproduction

From the repo root (4 cores):

```bash
python3 lab/variants/vertex-drive/studies/nozzle/test_nozzle.py      # 11 analytic checks, about 20 s
python3 lab/variants/vertex-drive/studies/nozzle/run_nozzle.py       # all designs, perturbations, particles; about 5 min
python3 lab/variants/vertex-drive/studies/nozzle/calc_rerun.py       # read-only FDP-1 re-runs incl. coupled C cases; about 4 min
python3 lab/variants/vertex-drive/studies/nozzle/sector_loss.py      # T02 one-sector-lost case; about 2 min
```

numpy is the only dependency; there is no scipy.
