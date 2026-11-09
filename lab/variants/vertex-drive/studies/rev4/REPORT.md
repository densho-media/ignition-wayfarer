# Vertex Revision 4: T00 engineering report (§3-§6 and Part III)

| | |
| --- | --- |
| Kind | study (research only, NON-CANON) |
| Base | `e24fc7a` on `claude/project-thread-9rsgog`; V4 as integrated in `a1c8246` (never changed here) |
| T05 inputs | `claude/project-thread-ctwplp`: `rev3.json` (stretch, loads, launcher B) and Rev 4 step 1 `f6f527d` (coil builds, ray cast) |
| Code | `studies/rev4/`: `ledger.py`, `injection.py`, `durability.py`, `spine.py`, `handoff.py`, `test_rev4.py`; results in `results/` |
| Handoff | `results/t05_handoff_rev4.json` (version 1) at the Vertex entry |
| Date | 2026-11-09 |

Every ship number comes from the FDP-1 calculator through the Vertex adapter. FDP-1, the four-burn engine, `data/`, `src/`, Drive
and production geometry are unchanged; their test suites pass unchanged (FDP-1 45, four-burn 18, Atlas 24, Rev 4 15).

## Summary

| Question | Result |
| --- | --- |
| §3 Closure-coil heat | **Booked correctly and small:** 6.2 GW (bottom-up) to 11.3 GW (T05 ray cast) of escaping radiation, taken from radiation to space into the coil armour; energy conserved to 1e-9. |
| §3 Closure-coil hardware | **Large and newly visible:** about 2.0-2.3 kt unbooked (winding packs 1.2 kt, LiH neutron screen 0.28 kt, struts, cryostat, Li loop). V4 gears about 12.4 t of departure per added tonne, so the coupled approximation reaches **68-72 kt** (V4 42.9 kt). |
| §4 Launcher B | **NOT DEFENSIBLE.** No layered D/³He target survives 13,700 g (limits 370-930 g). B-long (594 m, 6,660 g) fails too. |
| §4 Alternatives | Fewer, larger pulses: do not fit at 150-100 Hz, and V4 does not close at 60 Hz or below. **Only B-modified survives mechanically** (30 K gas-filled HDC capsule, wall 34 µm), labelled **target physics unproven** (convergence about 44 against 24). |
| §5 Surfaces | Spectrum decides. **W, Mo and SiC fail** for spectra at or below 10 keV. **CFC carbon survives every band** at 4.0 and 8.3 J/cm². A Li film survives all bands. |
| §5 New blocker | **Near-axis plasma.** An axisymmetric field cannot reflect plasma moving along the axis. The shield-face centre and the snout tip receive the raw pulse: about 340-470 J/cm² of 2.4 MeV/u ions per pulse. No solid survives this. |
| §6 S5 spine | S5 as drawn: cantilever f₁ 0.076 Hz, **fails**. Corrected N9 in the tank gaps (R 31 m, tube r 0.61 m): **2.01-2.23 kt** for bow 100-1,000 t, meets 0.2 Hz on the conservative bound. Buckling factor about 500. Frames need spokes (free ring ovalling 0.14 Hz). |

## §3 Closure-coil energy ledger (`ledger.py`, `results/ledger.json`)

**Method.**
- The postprocessor rebuilds the coil assembly bottom-up at V4 scale (T03 C_W15 coils):
  - geometry scaled by 1.501;
  - current field-limited, ×1.227;
  - winding minor radius from 25 T at the surface;
  - hoop case sized from self-tension plus inter-coil loads, ×1.25 dynamic;
  - fixed layers between the winding and the burn face;
  - a burn-facing LiH neutron screen;
  - CFC armour;
  - six struts per coil, sized from T03's axial loads.
- It projects the assembly from the burn point (sin φ · h / d per ring, struts integrated along their length).
- It then moves the intercepted radiation out of radiation to space.
- The coil electricity (pumps, cryoplant) is drawn from the plasma through FDP-1's recovery efficiency (0.95).

**The eight terms (V4, preferred bottom-up case, GW):**

| Term | GW | | Term | GW |
| --- | --- | --- | --- | --- |
| 1 Radiation to space | 395.67 | | 5 Plasma through the nozzle | 6,883.13 |
| 2 Radiation on the closure coils | 6.15 | | 6 Useful jet | 27,861.59 (unchanged) |
| 3 Radiation on other hardware | 10.24 | | 7 Cryogenic and electrical conversion losses | 84.46 |
| 4 Plasma on hardware | 478.51 (unchanged) | | 8 Coil cooling-system loads | 0.020 |

The sum is the gross fusion power, 35,719.76 GW, to 1e-9 in every case. The coil heat is split once:
- hot (armour, 1,800 K): 6.14 GW;
- warm (back-face leak and neutron screen, net of the MLI loads): 5.7 MW;
- lifted at 80 K and 20 K: 0.07 MW, with 2.8 MW of cryoplant input;
- lithium pumps: 16.9 MW electric.

**Cases** (coupled = labelled approximation; see the limitation below):

| Case | Share | On coils | Hot added | Hot radiator | Coil hardware | Coupled departure |
| --- | --- | --- | --- | --- | --- | --- |
| V4 as integrated | 0 | 0 | 0 | 0 | 0 | 42,916 t |
| T03 geometry (kept) | 0.029 | 11.95 GW | 11.96 GW | 11,165 m² | 2,224 t | 70,869 t |
| C1 grown with the pulse (kept) | 0.0377 | 15.53 GW | 15.55 GW | 14,515 m² | 2,332 t | 72,357 t |
| T05 Rev 2 upper (kept) | 0.073 | 30.08 GW | 30.12 GW | 28,109 m² | 2,768 t | 78,457 t |
| T05 Rev 4 ray cast (+0.0118 other hardware) | 0.0273 | 11.25 GW | 16.31 GW | 15,223 m² | 2,291 t | 71,883 t |
| **Bottom-up, case in its own shadow, TARGET composite** | **0.0149** | **6.15 GW** | **6.15 GW** | **5,741 m²** | **2,050 t** | **68,472 t** |
| Bottom-up, wrapped case | 0.0187 | 7.70 GW | 7.71 GW | 7,192 m² | 2,185 t | 70,206 t |
| Bottom-up, CFRP case at 1.2 GPa | 0.0149-0.0227 | 6.2-9.3 GW | | | 3.9-4.2 kt | 91-95 kt |
| Bottom-up, cryogenic steel case (ITER class) | 0.0149-0.0269 | | | | 28-29 kt | **409-417 kt (ruled out)** |

**Heat sensitivity.** Departure moves only about 260 t from the 6.2 GW of heat itself. The added hardware drives the coupled result. Each
GW of coil heat needs about 935 m² and 1.4 t of 1,800 K radiator. If the coils reject through their own shadow cone, edge-on to the burn,
they need 6,070 m² at 1,800 K, 16,600 m² at 1,400 K or 63,700 m² at 1,000 K.

**Mass sensitivity** (preferred case, coupled departure):

| Parameter | Low | High |
| --- | --- | --- |
| LiH e-fold 0.08-0.18 m | 67.3 kt | 70.2 kt |
| WC / steel screen instead of LiH | | 98.3 kt |
| Winding J_e 300 / 75 A/mm² | 61.0 kt | 83.4 kt |
| Neutron escape ×10 | | 70.2 kt |
| Screen 0.20 m (REBCO fluence limit exceeded 10×) | 69.6 kt, cryo 30 MW | |

**What sets the hardware.**
- REBCO fast fluence: the coils sit 64.7 m from the burn, so they receive about 1.1e20 n/cm² over the 5.7-year burn. That is about 35× the
  level where degradation is already measured (3.3e18). The in-situ 14 MeV data at 40 K degrade even earlier.
- The screen is therefore sized for 100× attenuation, 0.56 m of LiH.
- The winding pack of C1 alone (162 MA at 150 A/mm²) is 1.05 kt. FDP-1 books no conductor mass for any of its loops, only the virial
  structure. This is a finding about the FDP-1 loops too (OPEN; their code is protected).

**Cooling-system mass assumptions** (all PROTOTYPE or EXTRAPOLATION, listed in `ledger.json` `assumptions`):
- Li loop: 1,500 → 1,800 K, 10 m/s, 1 MPa, 170 m out and back to the hot-radiator root;
- piping: Mo-TZM tubes of 0.15 m radius, wall r/50;
- EM pumps: 1 kg/kW, efficiency 0.6;
- cryoplant: 30 % of Carnot to the 628 K warm loop, 2-10 kg/W of input.

Totals: Li inventory 83 t, pipes 70 t, pumps 17 t, cryoplant 6-28 t.

**Limitation (stated as the brief requires).** FDP-1's solid angle and plasma ledger are protected, so an exact treatment inside the solver
is not possible. The coupled solves are a **labelled approximation**:
- the coil heat enters through `plume_to_hardware` (the same 1,800 K loop, exact in heat);
- the warm and electric loads enter through `house_fraction`. This over-books the radiation-borne warm heat by the recovery loss
  (×1/0.95 − 1, about 5 % of 6 MW);
- the hardware enters as payload.

After the solve, `relabel` restores the eight categories. These are converged FDP-1 solutions of an approximate model. **They are not a
converged spacecraft design.** In particular:
- the coil hardware is held at the V4 pulse size;
- FDP-1 raises the pulse rate to about 312 Hz to supply the heavier ship. Capped at 196 Hz, the same ship is 91 kt with an 82 m
  stand-off.

## §4 Target injection (`injection.py`, `results/injection.json`)

**Evidence:**

| Item | Kind | Value |
| --- | --- | --- |
| GA IFE gas gun | demonstrated / design | 400 m/s, 8 m barrel, ≤ 10,000 m/s² (1,020 g); sabot for direct drive |
| Frozen-DT strength | calculated (Petzoldt and Moir) | > 1,020 g below 17 K; hohlraum membranes about 204 g |
| IFE injector ranges | design studies | 100-1,020 g; 400 m/s set by chamber heating |
| EM sabot mock-ups | demonstrated (mock-up) | about 500 g |
| Two-stage light-gas gun, D₂ with sabot | demonstrated | 3.8 km/s (European group); ORNL bare D₂ 2.85 km/s; plastic 4.5 km/s; repetitive 2.5 km/s at 1 Hz |
| Repetitive sabot stripping at km/s | **not demonstrated** | none reported |
| ³He phase | property | never solid below 2.93 MPa; liquid below 3.3 K |

**Target classes** (computed limits; mechanism in `injection.json`):

| Class | Limit | Mechanism |
| --- | --- | --- |
| Solid pellet | 21,300 g, D₂ only | ³He cannot be carried as a solid |
| Layered: liquid ³He in 25 / 10 nm foam | **373 / 933 g** | Capillary retention. Drained liquid cannot rewet in a 5 ms flight. The drain distance k ρ v / µ does not depend on the acceleration. |
| Layered: D₂ ice on the wall | 7,600-25,500 g | Shear in the layer |
| Indirect drive on membranes | 204 g | Membrane strength. A foam bed would need 160 kPa at 13,700 g. |
| **Strong shell, gas fill at 30 K, HDC** | **102,000 g** | Fill 1.7 MPa, wall 34 µm, 0.59 g. Uniform by construction: a gas re-equilibrates in about 0.1 ms. |

**Candidates:**

| Candidate | Muzzle | Accelerator | Verdict | Coupled departure (coil hardware + launcher) |
| --- | --- | --- | --- | --- |
| B (T05 Rev 3): 45 m open, 13,700 g | 8.81 km/s | 289 m | **NOT DEFENSIBLE** (14.7× the best layered limit) | 69.4 kt |
| B-long: longest straight run, 594 m | 8.81 km/s | 594 m at 6,656 g | **NOT DEFENSIBLE** | 70.4 kt |
| **B-modified: B kinematics, gas-filled HDC capsule** | 8.81 km/s | 289 m | **CANDIDATE, TARGET PHYSICS UNPROVEN** | 69.5 kt |
| Fewer, larger pulses, 150 Hz (1,000 / 3,000 g) | 8.12 km/s | 3,358 / 1,119 m | DOES NOT FIT (V4 itself grows to 58.8 kt) | 152-169 kt |
| Fewer, larger pulses, 100 Hz | 9.32 km/s | 4,431 / 1,477 m | DOES NOT FIT (212 kt) | 1.4-1.7 Mt |
| 60 / 30 / 15 Hz | | | **V4 does not close** | |

- **Why fewer pulses do not help.** At a fixed tip fluence the open flight grows as √E_p while the rate falls as 1/E_p. So the muzzle
  speed falls only as √f and the accelerator only as f, while the stand-off, loops, coils and radiators grow. Reaching 1,000 g in 289 m
  would need about 14 Hz, and the ship does not close below about 100 Hz.
- **The B-modified penalties stay open:**
  - convergence about 44 (fuel starts at 0.023 g/cm³), not the 24 assumed for liquid/solid fuel;
  - a cold 1.7 MPa fill at 196 Hz;
  - carbon mixing;
  - FDP-1's gain is not re-derived for it.
- **On the coupled ship** the rate rises to 312 Hz, which needs 14.0 km/s and 732 m at 13,700 g (it fits the longer coupled ship).
  Capped at 196 Hz, it needs 11.2 km/s, 467 m and 91 kt. The adapter's one-target rule on the full path at 8.81 km/s does not close.
- **Energetics of B-modified:**
  - shot energy about 240 kJ;
  - 94 MW electric at 0.4 efficiency;
  - sabot catcher 28 MW;
  - launcher about 73 t;
  - about 3.5e10 shots per mission. Only a contactless coilgun has a credible life; a railgun cannot run that many shots.
- **Requirements:**
  - open flight 5.1 ms;
  - lateral velocity error ≤ 0.02 m/s;
  - pointing 2.2 µrad untracked, or 110 µrad with ±5 mm beam steering;
  - axial error absorbed by driver timing on the tracked arrival;
  - ship drift 2.4 µm (negligible);
  - a rotating chopper at the snout, closed for each flash.
- **The axis field** (vacuum, T03 set at V4 scale) is 0.67 T at the burn, 3.1 T at the snout tip and 5.1 T near the shield. A metal
  hohlraum cannot cross it at 8.8 km/s without eddy heating and drag. The B-modified capsule is non-conducting (direct drive).

**Recommended Blender configuration.**
- Draw B-modified as the preferred lane, with its gas-capsule label.
- Draw B and B-long as labelled failed lanes.
- Draw no fewer-pulse lane.
- Mount the barrel on its own kinematic rail, not on the spine.

## §5 Pulsed-radiation durability (`durability.py`, `results/durability.json`)

**Spectrum.** The V4 fuel is Compton-thick (τ about 20), so the escaping spectrum is not the burn temperature. Six bands bound it, from
Planck 1 keV (a disassembling surface) to 50 keV bremsstrahlung above 5 keV (hard bound). Deposition uses xraylib µ_en/ρ. The
surface rise is averaged over the 1 ns diffusion length (W 0.26 µm).

Surface rise per pulse at 4.0 J/cm² (shield face and coil armour); the snout at 8.3 J/cm² is about 2×:

| Material | Planck 1 keV | Planck 3 keV | Wien 10 keV | Wien 30 keV | Brems 50 keV with soft tail | Brems 50 keV above 5 keV |
| --- | --- | --- | --- | --- | --- | --- |
| W (base 1,500 K) | 26,600 K ablates | 6,370 K ablates | 721 K fatigue (4 s) | 80 K OK | 4,240 K ablates | 1,160 K fatigue (2 s) |
| **CFC carbon** | 495 K **OK** | 42 K OK | 1 K OK | 0 K OK | 113 K OK | 2 K OK |
| Be (base 700 K) | 94 K fatigue | 7 K OK | OK | OK | 22 K OK | OK |
| SiC | 2,030 K ablates | 313 K cracks | 10 K OK | OK | 294 K cracks | 28 K OK |
| Mo | ablates | ablates | 242 K fatigue | 27 K OK | ablates | 435 K fatigue |
| Sn film | vapour loss | vapour loss | OK | OK | vapour loss | OK |
| **Li film** | 19 K **OK** | OK | OK | OK | 5 K OK | OK |

- **Fatigue dominates.** A face sees about 3.5e10 cycles per mission, so every surface must stay elastic, below shakedown (W 220 K,
  Be 110 K). Plastic cycling cracks W in seconds to minutes.
- **Cooling.** The steady flux is 7.8 MW/m² (shield face and coils) and 16.2 MW/m² (snout). A 300 K conduction drop limits the armour to:

  | Material | 7.8 MW/m² | 16.2 MW/m² |
  | --- | --- | --- |
  | W | 3.8 mm | 1.8 mm |
  | CFC | 5.7 mm | 2.8 mm |
  | SiC | 2.3 mm | 1.1 mm |

- **Recommendation: one shared technology.** CFC monoblocks on Mo-TZM lithium tubes, which keep lithium away from carbon (Li₂C₂), on the
  shield rim, the coil armour and the snout cartridge sides:
  - 5 mm faces at 7.8 MW/m²;
  - 2.5 mm at the snout.
  - The replacement interval is set by the neutron loss of CFC conductivity, not by erosion (OPEN, needs data at 1,500 K).
  - A renewable lithium surface is the fallback for the snout tip face.
- **Near-axis plasma: failed check, not hidden.** The shield-face centre and the snout tip sit in the unstopped axis channel. They receive
  the raw pulse:
  - 343 J/cm² per pulse, mean about 670 MW/m², as 2.4 MeV/u ions;
  - T03's thin shell puts 0.32 % of the plasma, 113 GW, onto the shield disk.

  FDP-1 books the heat (`plume_to_hardware`), but no surface check used it. No solid face survives this. It needs an axis plug, either a
  sacrificial or renewable stagnation target or a non-axisymmetric field, and D-21-class plasma modelling to confirm it.

## §6 S5 spine (`spine.py`, `results/spine.json`)

**Model.**
- A 1D Timoshenko beam, 37 nodes at the 7.65 m frame pitch, from J1 to J3. **This is not FEA.**
- T05 Rev 3 bay masses are lumped at the frame nodes.
- Two boundary cases bound the truth:
  - cantilever at J1 (T05's basis, lower bound);
  - free-free with the 15 kt aft ship lumped at J1 (upper bound).
- Bending stiffness of the longerons plus the S2 spine and keels; shear stiffness from diagonal lacing (0.25 of the longeron area).
- Euler buckling under the inertial axial load at peak acceleration, with SF 2.
- Closed-form local checks: longeron bay modes, ring-frame ovalling and the tank saddles.
- The rotary inertia of the tank rings is neglected (a few per cent high).

**Geometries** (full tanks, 300 t bow):

| Geometry | Cantilever f₁ | Free-free f₁ | Buckling factor | 0.01 g stress | Bay mode | Added structure |
| --- | --- | --- | --- | --- | --- | --- |
| S2 sectors only | 0.013 Hz | 0.056 Hz | 2.7 | **1,880 MPa (fails)** | | 0 |
| S5 as drawn (N6, r 0.29 m) | **0.075 Hz (fails)** | 0.255 Hz | 76 | 135 MPa | 44 Hz | 533 t |
| N6 corrected (r 0.76 m) | 0.189 Hz | 0.653 Hz | 489 | 22 MPa | 115 Hz | 2,504 t |
| N9 in the gaps (r 0.52 m, T05 Rev 4) | 0.172 Hz | 0.618 Hz | 497 | 33 MPa | 79 Hz | 1,475 t |

The allowable is 240 MPa (600 MPa CFRP, SF 2, splice 0.8). This confirms T05's correction (cantilever 0.075 Hz against its 0.077 Hz).

**Sized for 0.2 Hz on the conservative cantilever bound** (bow 100 / 300 / 1,000 t):

| Layout | Tube radius | Total structure |
| --- | --- | --- |
| N6 at R 34.8 m | 0.80-0.84 m | 2.84-3.11 kt |
| **N9 at R 31 m** | **0.60-0.64 m** | **2.01-2.23 kt** |

**Revised S5 mass range: 2.0-2.2 kt** (N9). That is about 1.7-1.9× the 1.18 kt in the brief, which came from the undercounted Rev 3 option.
If the aft ship is as stiff as the free-free bound, N9 at r 0.52 m already gives 0.62 Hz.

**Other checks:**
- **Joint loads (N9, design SF 2):**
  - J1: axial 3.75 MN; moment 350 MN·m and shear 2.9 MN at 0.01 g lateral (70 MN·m at 0.002 g).
  - J3: axial 0.11 MN for a 300 t bow.
- **Buckling** is not critical (factor about 500); longeron bay buckling margins are large (`spine.json`).
- **Frames:** a free ring frame (r 0.15 m tube) ovalises at about 0.14 Hz. Frames need spokes or tie rods to the keel hub.
- **Tank saddles:** isolate at 10-30 Hz. That passes 0.3-2.3 % of the pulse ripple and stays clear of f₁ and the slosh band. A saddle
  stiffened above 196 Hz would need about 7e11 N/m per 409 t vessel.
- **Pulse:** the longeron bay modes (79-121 Hz) clear 195.7 Hz and its harmonics by more than 10 %.
- **Thermal bow:** a 10-50 K side-to-side difference bends the stretch by 0.4-2 mrad. The launcher must not be a spine member.
- **Independence:** K2 (own 2.2 m tube at r 3 m, az 90°) and the launcher (own rail) share no primary member. Services run on keels 150
  and 270. With one keel lost, cantilever f₁ stays 0.17-0.19 Hz.

## Part III validation

| Check | How | Result |
| --- | --- | --- |
| Energy conservation | eight terms sum to the fusion power, postprocess and coupled, every case | PASS (1e-9) |
| No radiation double counting | radiation to space + coils + other = FDP-1's escaping radiation; coil heat split once (hot + warm + cold − intercepted = 0) | PASS |
| Thrust and plasma separate | jet and plasma on hardware unchanged; plume to space falls only by the coil electricity / η_rec | PASS |
| Circuits | hot and warm additions equal the coil terms exactly | PASS |
| V4 reproduced | coupled solve with zero additions gives 42,915.78 t | PASS |
| Dimensions | hoop tension matches T03 (6.92 GN, 1 %); launcher B reproduces T05 (8.81 km/s, 289 m, 8.3 J/cm²); cantilever beam matches 1.875² (2 %) | PASS |
| Canon preservation | only `lab/variants/vertex-drive/` changed since `a1c8246`; FDP-1, four-burn and Atlas suites unchanged | PASS |
| Repeatability | all scripts deterministic; `ledger.py` about 30 s, `injection.py` about 3 min, the others seconds | PASS |
| Engineering checks | launcher B, B-long, S5 as drawn, S2 lateral, W / Mo / SiC at soft spectra, shield-face centre in the axis channel | **FAIL, reported as results** |
