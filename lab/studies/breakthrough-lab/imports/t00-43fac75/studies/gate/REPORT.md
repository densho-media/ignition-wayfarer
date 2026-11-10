# Vertex propulsion feasibility gate: T00 report

| | |
| --- | --- |
| Kind | feasibility review, research only, NON-CANON |
| Branch | `claude/project-thread-9rsgog`, from `fa2103a` (T00 Revision 4 final) |
| T05 input | `claude/project-thread-ctwplp` `4c1a29b`: first-hit axis kernel on the drawn V4 set (copied to `inputs/`) |
| Methods | T03's thin-shell nozzle model (analytical, vacuum field, flux-excluding shell); 3D vacuum-field ray integration; test-particle-free closed-form estimates; FDP-1 via the Atlas adapter; Rev 4 beam model. **No MHD, no PIC, no external computing** (no D-21). |
| Unchanged | canon, IGNITION Drive, lore, production geometry and physics, `data/`, `src/`, FDP-1 and four-burn code, V4 and every historical generation; nothing on `main` |
| Date | 2026-11-09 |

## 0. Verdict for the owner

**Vertex is not yet a coherent propulsion architecture. It is BLOCKED on two counts that this gate cannot remove, and it has one
analytically promising fix for the axial plasma problem.**

1. **Target physics blocks it (Phase 3).** Compressing FDP-1's 0.77 g of D-3He to its 2,000 g/cc costs about 78 MJ even on the
   ideal cold adiabat, which is 47 % of FDP-1's 168 MJ driver. Heavy-ion drivers couple 10-20 %. This is an FDP-1 target assumption
   (gain 1,084), upstream of the launcher. The gas-filled capsule makes it worse: it starts at 0.023 g/cc (convergence 44), its 34 µm
   wall is a third of the 4 GeV ion range so the beam preheats the gas, the wall is 0.76x the fuel mass while the burn tolerates
   about 2 % carbon, the wall leaves as exhaust that FDP-1 does not carry (ve x0.75), and no fill process exists at 300+ Hz.
   B-modified and B-ray are **NOT DEFENSIBLE as fusion targets**; mechanical survival is not enough. This agrees with T04's
   compression bound (owner question D-T04-1, still open).
2. **Mass closure blocks it (Phase 2).** Re-sizing every added item on each solution, the ship converges only while the added items
   stay small: coils alone 70.2 kt, coils and launcher 72.8 kt, plus the axis fix 85.2 kt. With the spine sized to T05's basis
   (0.2 Hz cantilever) **it does not converge**: V4 gears about 12 t of departure per added tonne, so a spine that grows with the
   ship drives a loop gain above 1. Relaxed spine criteria close at 117-143 kt and 460-560 Hz, where the launcher needs 27.5 km/s
   and a 1.3 km barrel. Capping the rate at 196 or 250 Hz diverges. The 68-72 kt of Revision 4 is not a converged ship.
3. **The axial plasma leak has a retained concept (Phase 1).** No field can remove it: on any closed flux-excluding surface the
   tangential field has at least two zeros (it is the surface gradient of a potential). An axisymmetric nozzle puts one on the axis.
   **Tilting C1 and C2 together by 14°** (and turning the nozzle 2.7° so the thrust stays through the centre of mass) moves the zero
   to 10.8° ± 3.0°, off the shield, through the C1 ring, at a 1.7 % thrust cost and no added conductor. Status: **ANALYTICALLY
   PROMISING, NOT DEMONSTRATED**: lateral plasma flow toward the zero is outside the thin-shell model. It needs a shadow cone of
   at most about 7.5°; the converged coupled ships need 9.4°, which puts the moved leak back on the shield rim.

The next decisive experiment is the target (section 7).

## 1. Phase 1: the axial plasma problem (ISS-022)

### 1.1 How much escapes along the axis (V4, isotropic pulse, 0.025° resolution)

| Quantity | Value |
| --- | --- |
| Unstopped channel half-angle | **3.5°** (shield angular radius 6.37°) |
| Plasma reaching the shield face | 0.094 % of the plasma, **157 MJ per pulse, 31 GW** |
| Shield-centre fluence | **342 J/cm² per pulse** (the free-expansion value: the axis is a field zero) |
| Snout tip of launcher B (0-1°, 45 m) | 11 MJ per pulse, 2.2 GW, 708 J/cm² |
| Fast-ignitor port (1-2°) / beam ports (3.5-4°) | 344 J/cm² / 343 J/cm² (the ports sit at the channel edge) |
| Booked in V4 | as heat inside FDP-1's aggregate `plume_to_hardware` (478 GW); its fluence, erosion and the parts in the channel are not booked |

T05's 6° keep-out is the shield's angular radius, not a plasma result. The plasma channel is 3.5°.

### 1.2 Sensitivity to the plasma distribution and to the closing field

| Profile g(θ) | Leak (GW) | Half-angle |
| --- | --- | --- |
| isotropic | 33 | 3.50° |
| prolate P2 +0.25 / +0.5 | 51 / 72 | 3.88° / 4.23° |
| oblate P2 −0.25 | 19 | 3.05° |
| forward-heavy P1 +0.2 / aft-heavy −0.2 | 47 / 21 | 3.80° / 3.12° |
| forward jet x2 / x5 within 10° | 114 / 473 | 4.70° / 6.35° |

The leak share falls as 1/I² with the closing current (x3 current: 1.18°, 0.011 %), but **the centre fluence does not change**: only
the size of the spot does.

### 1.3 What a face must survive

At about 3 µs arrival spread, 342 J/cm² is a heat-flux factor of about 2,000 MJ m⁻² s⁻½, 40x the tungsten melt limit. A solid face
would ablate about 34 µm per pulse (metres per hour at 196 Hz); a renewable lithium face would consume lithium at plug-like rates.
For 3.5e10 pulses a permanent face needs **about 1.7 J/cm²** (10 MJ m⁻² s⁻½ fatigue level), a **200x reduction**.

### 1.4 Concepts compared

| Concept | What it does | Result | Status |
| --- | --- | --- | --- |
| E: stronger axisymmetric field (shadowed coil behind the shield, 40-162 MA) | narrows the channel to 1.4-0.45° | centre fluence unchanged; 690-7,400 MN hoop, 670-2,700 MN pull toward C1 | **REJECT** (narrows, never removes) |
| A1: tilt C1 and C2 as a rigid pair | moves the field zero off the axis (zero follows the tilt within 0.4°) | 14° tilt + 2.7° nozzle turn: leak at 10.8° ± 3.0°, 0 on the shield, 24 GW leaves through the C1 ring; thrust −1.7 %; no conductor added; C1 conductor comes to 8.7° (rim 6.37°) | **RETAIN: ANALYTICALLY PROMISING** |
| A2: transverse plug coil behind the shield | pushes the zero sideways | needs about 240 MA (254 GJ, +9 % stored energy); 82,000 MN·m static torque from the main field; driver beams deflected 87 mrad | **REJECT** |
| B: forward cap on the target | momentum sharing | 200 mg in 5° (26 % of the fuel) to reach 2.5 J/cm²; 4.4 t/year of debris on the shield; sits in the driver and fast-ignitor path | **RESEARCH ONLY** (target physics, T04 class) |
| C: two splayed nozzles | each forward channel passes beside the ship | geometrically clears every envelope at 40-80 m offset and 5-15° splay; two coil sets, shields and driver sets | **OPEN** (a different architecture, not evaluated as a ship) |
| D: move hardware out of the channel | B-ray, ports, trackers, rail | everything except the shield face can move; the face cannot | needed with A1 for the port and strut placement |
| S: sacrificial or renewable centre insert | absorbs the channel | 34 µm/pulse ablation; 200x over a permanent limit | **REJECT** |
| Lithium droplet plug (Rev 4) | consumable | 230-32,000x the propellant flow | **REJECT** (unchanged) |

The A1 leak cone still meets struts and wing spars at some azimuths (azimuth-averaged kernel: about 5.6 GW on nozzle struts, coil
struts and wing spars). Choosing the tilt-plane azimuth between them is the T05 task in Phase 4 (handoff below).

### 1.5 Limits of these results

- Thin shell, vacuum field, no lateral flow: plasma sliding along the surface toward a field zero (funnelling) would enlarge the leak.
  Only MHD (D-21) can settle that. The tilted-closure result is therefore a vacuum-field prediction.
- **New issue (gate G1):** the specular-reflection ledger of the thin-shell model depends on angular resolution. At 1° about 1.2 % of
  the plasma reflects forward; at 0.25° and finer, 6.4-6.7 %, mostly from kinks of the aft stopping surface near L2 and L3. The axial
  leak (stopping-based) is not affected. This bears on the ideal-nozzle efficiency 0.791 (already a D-21 item).
- The 3D method uses a flux-exclusion factor k = 1.71, calibrated so that it reproduces T03's exact axisymmetric leak (0.091 % against
  0.094 %).

## 2. Phase 2: the coupled ship (ISS-024)

Every added item is re-sized on each FDP-1 solution until the departure mass changes by less than 1 t (`coupled.py`). The closure
coils follow the stand-off and the nozzle field energy of each solution; the spine follows the propellant; the launcher follows the
rate; the axis fix enters as a nozzle-efficiency factor (0.983). Propellant, radiators, drivers, shield, tanks, yield and rate are
FDP-1's own on each solve.

| Case | Status (iterations) | Departure | Rate | Yield | Stand-off | Thrust | Propellant | Added items (t) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V4 reference | | 42,916 t | 196 Hz | 182 GJ | 64.7 m | 2.90 MN | 27,116 t | none |
| Rev 4 method: coils, one pass | single pass | 68,472 t | 312 Hz | 182 GJ | 64.7 m | 4.63 MN | 43,264 t | coils 2,050 |
| Coils only | **CONVERGED** (5) | **70,173 t** | 320 Hz | 182 GJ | 64.7 m | 4.75 MN | 44,338 t | coils 2,188 |
| Coils + launcher B-ray | **CONVERGED** (6) | **72,845 t** | 332 Hz | 183 GJ | 64.7 m | 4.93 MN | 46,027 t | coils 2,201, launcher 155 |
| + axis fix A1 (thrust x0.983) | **CONVERGED** (7) | **85,224 t** | 334 Hz | 216 GJ | 68.6 m | 5.76 MN | 53,848 t | coils 2,436, launcher 178 |
| + spine, cantilever 0.2 Hz (T05 basis) | **NON-CONVERGING** (diverges, gain 2.5) | > 400 kt | → 1,000 Hz | | | | | spine 21,169 at the 4th pass |
| + spine, cantilever 0.1 Hz | CONVERGED (26) | 142,805 t | 560 Hz | 216 GJ | 68.6 m | 9.66 MN | 90,230 t | coils 2,687, spine 2,073, shield 1,530, launcher 499 |
| + spine, free-free 0.2 Hz (upper bound) | CONVERGED (16) | **117,089 t** | 459 Hz | 216 GJ | 68.6 m | 7.92 MN | 73,982 t | coils 2,577, spine 877, shield 1,160, launcher 336 |
| same, rate cap 250 Hz | **NON-CONVERGING** (gain 1.1) | > 400 kt | 250 Hz | 1,367 GJ | 125 m | | | coils 7,301 at the last pass |
| same, rate cap 196 Hz | **NON-CONVERGING** (gain 1.4) | > 400 kt | 196 Hz | 2,256 GJ | 147 m | | | coils 8,438 at the last pass |
| cantilever 0.2 Hz, long farm (same section) | **NON-CONVERGING** (gain 10) | > 400 kt | | | | | | spine 45,256 at the 2nd pass |
| free-free 0.2 Hz + FDP-1 loop conductor (J_e 150) | CONVERGED (35) | 224,432 t | 879 Hz | 216 GJ | 68.6 m | 15.2 MN | 141,806 t | + loop conductor 3,152 |
| same at J_e 300 A/mm² | CONVERGED (18) | 141,269 t | 554 Hz | 216 GJ | 68.6 m | 9.55 MN | 89,260 t | loop conductor 1,575 |

Peak acceleration stays at FDP-1's 0.0187 g in every case (FDP-1 holds the departure acceleration and lets the mass close). Heat
rejection on the preferred converged case (free-free spine): hot radiators 1.37 km², warm 13.98 km² (V4: 0.46 and 4.95 km²).

**Two couplings break the retained pieces on the converged ships:**
- **Launcher:** at 459 Hz the one-target-in-flight rule needs a 27.5 km/s muzzle and a 1,288 m barrel at 30,000 g (336 t, 3.1 GWe).
  B-ray was plausible at 196 Hz (11 km/s, 208 m); at the coupled rates it is not.
- **Shield and axis fix:** the wider tank farm (the only farm that converges) needs a 9.4° shadow cone (shield radius 11.4 m). The A1
  leak at 10.8° ± 3.0° then falls on the shield rim again, and tilting further makes C1 cross the axis. **A1 works only on a ship
  whose shadow cone stays at or below about 7.5°**, which none of the converged coupled ships has.

What it means:
- **V4 gears about 12 t of departure per added tonne,** and FDP-1 raises the pulse rate rather than the pulse when the ship grows
  (320-560 Hz). Any item that grows with the ship multiplies; the spine at T05's 0.2 Hz cantilever basis diverges, and so does the
  long (same-section) tank farm.
- A 1.7 % thrust loss costs about 12 kt: nozzle efficiency is as heavily geared as mass.
- Capping the rate forces larger pulses, a longer stand-off and larger coils (at 196-250 Hz the pulse grows to 1.4-2.3 TJ, the stand-off to 125-147 m and the coils to 7-8 kt; both diverge).
- Not in the solve: the HDC wall as exhaust mass (Phase 3: ve x0.75 alone takes V4's mass ratio from 2.7 to 3.8 before re-gearing).

## 3. Phase 3: the gas-filled capsule as a fusion target

| Check | Requirement | Gas capsule (B-modified, B-ray) |
| --- | --- | --- |
| Compression energy | 78 MJ at α 1 for 0.77 g to 2,000 g/cc (D-3He has 1.5x DT's electrons per mass) | 47 % of the 168 MJ driver at α 1; 70 % at α 1.5; 93 % at α 2. A 10-20 % coupling reaches only 110-310 g/cc |
| Convergence | 24 from liquid fuel | 44 from 0.023 g/cc gas |
| Beam deposition | ablator ≥ the ion range (4 GeV Bi in carbon: 0.041 g/cm², Bethe) | wall 0.012 g/cm² = 29 % of the range: most of the beam stops in the gas (preheat). Range-matched: 116 µm, 2.0 g of HDC |
| Mix | about 2 % carbon by mass raises bremsstrahlung 8 %, 5 % by 21 % | wall/fuel 0.76 |
| Exhaust mass | FDP-1 tamper 1.7e-9 per fuel | wall 0.76 per fuel: ve x0.75 (x0.52 range-matched) |
| Fill and rate | a fill per target at 196-560 Hz, 3.5e10 targets, held below 30 K | diamond is impermeable; NIF uses fill tubes; no such process |

**Verdict: NOT DEFENSIBLE as a fusion target.** The first line is FDP-1's own assumption: even a liquid or solid target at 2,000 g/cc
needs about half the driver energy in the fuel. That is the deepest unsupported assumption in the chain, and it is not a launcher
problem. B-ray only moves the launcher off the axis channel; the target verdict is the same.

## 4. Phase 5: S5N spine and J1/J3 under the revised mass

Does the drawn S5N (N9 on a 31 m ring, tube r 0.611 m, about 2 kt) still meet T05's 0.2 Hz cantilever basis?

| Ship | Departure | S5N as drawn: f1 cantilever / free-free | J1 axial design | J1 moment at 0.01 g | Splice stress (allowable 240 MPa) | N9 needed for 0.2 Hz cantilever |
| --- | --- | --- | --- | --- | --- | --- |
| V4 | 42.9 kt | 0.200 / 0.715 Hz: **meets** | 3.8 MN | 357 MN·m | 25 MPa | 1,969 t (r 0.61 m) |
| coils + launcher + A1 | 85.2 kt | 0.146 / 0.521 Hz: **fails** | 7.4 MN | 674 MN·m | 47 MPa | 3,885 t (r 0.81 m) |
| preferred converged (free-free spine) | 117.1 kt | 0.126 / 0.448 Hz: **fails** | 10.2 MN | 912 MN·m | 64 MPa | 5,882 t (r 0.97 m) |
| cantilever 0.1 Hz case | 142.8 kt | 0.115 / 0.407 Hz: **fails** | 12.4 MN | 1,104 MN·m | 77 MPa | 7,838 t (r 1.09 m) |

**About 2 kt is not enough on any coupled ship** at T05's basis: stiffness, not strength, governs (splice stresses stay well under
the allowable). J1's bending moment grows with the ship, from 357 to 674-1,104 MN·m at 0.01 g; J3 (300 t bow) is unchanged. A
spine sized for 0.2 Hz free-free (the upper bound with a rigid aft ship) needs only 0.6-1.1 kt, but its cantilever frequency is then
0.066-0.068 Hz, at the ring-spin frequency (0.067 Hz). Which bound applies decides whether the ship closes at all (section 2); that
needs a real model of the aft-ship stiffness, i.e. FE.

Beam model only (1D Timoshenko with Guyan-condensed modes; joints from beam statics). **No finite-element model was built or run.**

## 5. Rejected and retained architectures

| Item | Status |
| --- | --- |
| Axisymmetric closure with the shield taking the channel (V4 as drawn) | **REJECT** (342 J/cm² per pulse at the shield centre) |
| E: stronger axisymmetric field / shadowed shield coil | **REJECT** (narrows, never removes) |
| A1: C1 + C2 tilted 14°, nozzle turned 2.7° | **RETAIN, ANALYTICALLY PROMISING**, only with a shadow cone ≤ about 7.5°; not a plasma solution |
| A2: transverse plug coil | **REJECT** (240 MA, 82,000 MN·m static torque, beams 87 mrad) |
| B: forward target cap | **RESEARCH ONLY** (target physics; in the beam path) |
| C: twin splayed nozzles | **OPEN** (different architecture) |
| S: sacrificial / renewable centre insert | **REJECT** |
| Lithium droplet plug | **REJECT** (Rev 4) |
| Launcher B, B-long (layered targets) | **REJECT** (Rev 4) |
| Launcher B-modified and B-ray (gas-filled HDC capsule) | **REJECT as fusion targets** (Phase 3); mechanically survivable only |
| FDP-1 target (0.77 g, 2,000 g/cc, gain 1,084 at 168 MJ) | **UNSUPPORTED** (47 % coupling at α 1; agrees with T04's compression bound, owner question D-T04-1) |
| Coupled ship with coils only / + launcher / + A1 | converged at 70.2 / 72.8 / 85.2 kt (approximations; spine not booked) |
| Coupled ship with the spine at T05's basis | **NON-CONVERGING** |
| Coupled ship with relaxed spine bases | converged at 117-143 kt and 460-560 Hz, where the launcher and A1 no longer fit |
| Rate caps 196 / 250 Hz | **NON-CONVERGING** |
| Long (same-section) tank farm | **NON-CONVERGING** |
| S5N as drawn (about 2 kt) | sufficient on V4 only; **REJECT** on every coupled ship at the 0.2 Hz cantilever basis |
| V4 and the historical generations | unchanged, kept as references |

## 6. Validation

`python3 lab/variants/vertex-drive/studies/gate/test_gate.py` (13 tests, OK) checks: the shield-centre fluence equals free
expansion and is unchanged by field shaping; the leak falls as 1/I²; the 3D method reproduces T03's exact axisymmetric leak within
10 %; an axisymmetric closure has no side thrust; a tilted closure still has a field zero; the aligned tilt cancels the side thrust;
the coupled solve with nothing added reproduces V4 (42,915.78 t); converged cases changed by under 1 t and the others are labelled
non-converging; iteration is never lighter than the single pass; Bethe reproduces NIST PSTAR (100 MeV proton in water, 7.72 g/cm²)
within 5 %; the degenerate DT energy matches Lindl; and only `lab/variants/vertex-drive/` changed since `a1c8246`. Unchanged suites:
Rev 4 15, Atlas 24, FDP-1 45, four-burn 18.

## 7. Unresolved, and the next decisive experiment

**Next decisive experiment: a 1D radiation-hydrodynamics implosion of FDP-1's D-3He target at its scale** (0.77 g, 168 MJ heavy-ion
drive, liquid and gas starts), giving the reachable ρR, density, adiabat and gain. If the gain is far below 1,084, no launcher, nozzle
or spine change rescues V4, and Vertex needs a different fuel or driver basis. It needs a code and a D-21-class authorisation.

Then, in order:
1. MHD check of the tilted closure (does lateral flow funnel plasma into the moved zero?), D-21.
2. A ship-mass closure with a stiffness criterion the owner accepts (the 0.2 Hz cantilever basis diverges) and a ve adapter for inert
   target mass.
3. T05's azimuth sweep of the A1 leak cone against the full ship, and the C1 clearance at the shield rim.
4. The reflection-ledger resolution issue G1.
5. Unchanged from Rev 4: FDP-1 loop conductor mass (adapter case here), CFC and REBCO data, the soft X-ray spectrum.

## 8. Files

| File | What |
| --- | --- |
| `axis.py` → `results/axis_base.json` | Phase 1 leak, sensitivity, exposure by part, surface limits |
| `concepts.py` → `results/concepts.json` | Phase 1 concepts, 3D vacuum-field runs, the chosen concept |
| `coupled.py` → `results/coupled.json` | Phase 2 fixed-point coupled ship, all cases with trajectories |
| `target.py` → `results/target.json` | Phase 3 target requirements |
| `structure.py` → `results/structure.json` | Phase 5 spine and joints (beam model) |
| `handoff.py` → `results/t05_handoff_gate.json` | machine-readable geometry for T05 (Phase 4) |
| `test_gate.py` | validation |
| `inputs/t05_axis_kernel_4c1a29b.json` | T05's kernel, as received |
