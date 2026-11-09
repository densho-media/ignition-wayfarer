# T05 Stage B Revision 3: structure and access across the T-B stretch

| | |
| --- | --- |
| Thread | T05, mechanical architecture and spacecraft geometry |
| Date | 2026-11-09 |
| Status | DONE (Revision 3); stops before detailed surface geometry, waiting for owner review |
| Base | `7fc1da8` (Revision 2) on `claude/project-thread-ctwplp`; integrated research baseline `claude/project-thread-9rsgog` `a1c8246` (read only) |
| Review file | `REVIEW_VERTEX_BLENDER.blend` (packed, opens on `COMPARE_SIDE_BY_SIDE`; not in Git); copy, renders and contact sheet in `review/vertex_blender_rev3_2026-11-09/` |
| Numbers | `rev3.py` → `rev3.json` (standard library, beam-level screening); placements in `checks.json` |

NON-CANON. Canon, Drive, production geometry and the propulsion calculator are unchanged. Every structural member here is PROTOTYPE.
Masses are beam-model lower bounds with the FDP-1 CFRP assumptions (600 MPa, E 120 GPa, 1,700 kg/m³, safety factor 2,
splice efficiency 0.8), not finite-element results.

## 1. ISS-013: the stretch needs a structure, and stiffness sizes it

**What it carries.** The stretch runs X 140.75-416.15 m (275.4 m in 9 bays of 30.6 m). It holds 110 T-B vessels with 25.1 kt of
propellant (the canon farm vessels are filled first), 2.4 kt of tanks, and the shifted bow. The bow is taken as 300 t, PROTOTYPE:
the Brow is 100 t PROVISIONAL plus the Lance, Crown, EYE and hub.

**Load cases.**

| case | value | basis |
| --- | --- | --- |
| axial, burn | 1.88 MN peak at the root (thrust 2.90 MN × forward mass / ship mass), 3.75 MN design | dynamic factor 2 on the 195.7 Hz pulse train |
| lateral | 0.002 g on everything forward of the root: 0.54 MN shear, 67 MN·m root moment | 2× a canon 0.1°/s slew started in 60 s (0.0013 g at the bow); sensitivity case 0.01 g |
| canon 1.5 g ceiling | 408 MN at the root | the owner ceiling the FDP-1 structure uses; V4 never reaches it (peak 0.0187 g) |

**Dynamics decide the layout.**
- With full tanks, the propellant sloshes at 0.022-0.040 Hz and the rings spin at 4 rpm (0.067 Hz).
- The pulse train is 195.7 Hz. Every global mode is 100 to 1,000 times below it, so the response is quasi-static (axial ripple
  transmissibility 5×10⁻⁶).
- Rev 3 sets a target first bending mode of 0.2 Hz with full tanks: 3× the ring spin and 5× the highest slosh mode.
- Frame and saddle local modes must stay off 195.7 Hz and its harmonics.

**Layouts.** Strength mass is sized by the load cases; "mass for f₁ ≥ 0.2 Hz" adds area until the target is met.

| layout | strength mass | f₁ bending full / dry | mass for f₁ ≥ 0.2 Hz | canon load-path rule | verdict |
| --- | --- | --- | --- | --- | --- |
| S1 spine only (r 0.95 m) | 2.2 kt (714 mm wall) | 0.011 / 0.025 Hz | infeasible | violates "hub alone forbidden" | REJECTED |
| S2 canon sectors (spine + three keels at r 5 m, az 30/150/270, frames every 7.6 m, radial girders to the tank saddles) | 0.32 kt | 0.011 / 0.029 Hz (sits on the slosh band) | 11.5 kt | meets | strength only |
| S3 outer cage (six longerons at r 34.8 m, ring frames) | 0.77 kt | 0.067 / 0.17 Hz | 0.88 kt | partly (no r 5 m sectors) | candidate |
| S4 S2 + three belt keels at r 20.1 m between the tank rings | 0.40 kt | 0.027 / 0.071 Hz | 1.08 kt, but the stiff belt keels (r about 1.0 m) do not fit the 1.75 m gap | meets | REJECTED for stiffness |
| **S5 S2 + S3 (sectors for the Brow load path, outer longerons for stiffness)** | 1.07 kt | 0.068 / 0.17 Hz | **1.18 kt** | meets | **PREFERRED** |

- **S5 cost.** At 1.18 kt, S5 is 4.7 % of the propellant it carries.
- **The 1.5 g canon ceiling** would raise S5 to 3.3 kt, which is not prohibitive.
- **Lateral sensitivity.** At 0.01 g lateral, S5 needs 1.48 kt.
- **Global buckling.**
  - S2 alone has a margin of 0.95 under a conservative tip-load idealisation, so it fails.
  - S5's stiffened section is far above the design load: EI 7.6×10¹³ N·m² gives Euler about 2.5 GN against 7.5 MN.
- **Joints.**

  | Joint | Where | What it does |
  | --- | --- | --- |
  | J1 | X 137.9-140.75 m | Transfer frame: splices the canon spine end and sector rails to the stretch keels and outer longerons |
  | J2 | every bay | Keels and longerons in 30.6 m segments, 0.8 splice efficiency |
  | J3 | X 413-416 m | Spine to the canon shield spine column, keels to the Brow-side sector keels, outer longerons into the Brow outer truss ring (the Q45 bypass collar's radius family) |
  | J4 | each tank | Isolating G10/CFRP saddles, one fixed and one sliding: 1.5-20 K tanks on a warm frame, about 0.1 m axial contraction per tank |

- **New conflicts.**
  - The outer longerons (outer face r 35.05 m) sit 0.95 m inside skirt B2's shadow (r 36.0 m). The 0.3° braking attitude budget
    already set by the tanks still holds, but the margin is thin.
  - Tank exchange is possible only between frames.

## 2. ISS-015: a crew and robot corridor through the stretch

| option | what | mass | notes |
| --- | --- | --- | --- |
| K1 trunk inside the spine | continue the canon crew trunk in the spine bore (1.65 m clear after service trays) | 36 t | spine becomes a pressure vessel; single route; blocks a longer launcher |
| **K2 own tube beside the spine (preferred)** | 2.2 m tube at r 3 m, az 90° between keels 30° and 150°, 80 kPa, 2.5 mm Al-Li minimum gauge, 132 kg/m, 10 bulkhead hatches (0.75 m clear), transfer node at the trunk end (X 134.7 m) | 40 t | 2.96 m from keel 30°, 3.65 m from the inner tank envelope; the spine bore stays free |
| K3 robot rail and EVA only | rail along keel 270° | 1.7 t | no shirt-sleeve access to the bow |

- **Transit.** The bow is 4.7 min away at 1 m/s, shielded by 25 kt of propellant on every side.
- **Robot rail.** It is drawn on keel 270° in every option, for saddle inspection and cable runs.

## 3. ISS-009/016: launcher B kept; target survival is the gate, and the snout cartridge depends on the X-ray spectrum

**Target survival at 13,700 g.** There is no evidence that a target survives this.
- GA extrapolated D2-ice data (measured at 16.4 K; no DT data) to about 10,000 m/s², roughly 1,000 g, for IFE targets.
- A levitated-sabot mockup concept stays under 500 g.
- The bare-pellet fracture data used in Rev 2 (about 5×10⁵ g) apply to solid MFE pellets, not to layered shells.
- B is 13.7× above the IFE extrapolation.

The accelerator length follows L = (open flight × 195.7 Hz)² / 2a:

| target tolerance | open flight 45 m (B) | open flight 25 m |
| --- | --- | --- |
| 500 g | 7.9 km | 2.4 km |
| 1,000 g | 4.0 km | 1.2 km |
| 3,000 g | 1.3 km | 0.41 km |
| 6,400 g | 620 m (B-long: bow to snout) | 191 m |
| 13,700 g | 289 m (B) | 89 m |

- **B-long** (drawn as an outline): the accelerator runs from the bow to the snout through the stretch spine. That gives 6,400 g but
  needs the crew trunk moved out of the spine bore (corridor K2 makes room in the stretch, not through the habitat at X 93.85-134.7 m).
- **With a 289 m accelerator, a 1,000 g target would need the tip 12 m from the burn,** at 113 J/cm² per pulse.
- **The decision is T04's.** Lower acceleration means a much longer accelerator or a much closer, hotter tip.

**Snout cartridge durability.** Per pulse:
- The tip at 45 m receives 8.3 J/cm²; the shield face at 64.7 m receives 4.0 J/cm².
- Published single-pulse limits for tungsten are lower: damage at 0.15-0.21 J/cm² (soft X-rays), no roughening at 0.5-0.7 J/cm²,
  HAPL design 0.4-1.2 J/cm².
- The adiabatic surface jump at the tip is roughly fluence × mass attenuation / heat capacity:

  | photon energy | 3 keV | 10 keV | 30 keV | 50 keV | 100 keV |
  | --- | --- | --- | --- | --- | --- |
  | W | 117,000 K | 5,700 K | 1,400 K | 370 K | 270 K |
  | carbon | 495 K | 13 K | 1 K | 1 K | 1 K |

- **Spectrum.** A soft spectrum ablates any solid armour every pulse, and that applies to the shield face as well (ISS-017). A hard
  bremsstrahlung spectrum (the burn runs at 50-100 keV) puts tungsten at about 300 K of cycling and carbon near zero.
- **Steady load.** The tip takes 16.2 MW/m² steady (810 K across 5 mm of W), divertor class, so the cartridge needs active cooling.
- **Fatigue.** About 6×10⁹ cycles per year.
- **Recommendation.** A carbon-faced (CFC), actively cooled, replaceable cartridge, sized after T04 gives the spectrum.

## 4. ISS-014: closure coils, cooling chain, coordinated with T00

T00 checked this at `222dad1` on the integrated baseline (`lab/variants/vertex-drive/planning/ISS-014_COIL_RADIATION.md`).

- **The coil load is not booked anywhere.** The calculator's 478.5 GW "plume on hardware" is plasma only. Its 10.2 GW "radiation on
  hardware" covers the loops, struts and shield (solid angle 0.0248), not the coils.
- **The radii match T03.** C1 is r 22.13 m and C2 r 41.59 m (T03 C_W15 scaled 1.5007).
- **C2 was 12× too high in Rev 2.** Rev 2 gave C2 C1's 4.8 m envelope (`screen.py` copied it across). T03's C2 carries 10.6 MA in a
  0.085 m winding (envelope about 0.25 m), so its share is 0.0038, or 1.6 GW.
- **Basis now.** 11.9 GW on T03 geometry (C1 10.4 + C2 1.6). That rises to about 15.5 GW if C1's winding grows with V4's pulse energy.
  30.1 GW is kept only as an upper case. Nothing assumes the load goes away.

Passive radiation would need about 3,600 K, so the P2 armour needs a pumped loop:

| | C1 | C2 |
| --- | --- | --- |
| X-ray on the burn face | 10.4 GW, 7.8 MW/m² | 1.6 GW, 7.8 MW/m² |
| armour ΔT (5 mm W) | 390 K | 390 K |
| tin at 1,800 K, 300 K rise | 21 m³/s, two lines per side, r 0.81 m | 3.2 m³/s, r 0.32 m |
| lithium alternative | 17 m³/s | 2.6 m³/s |
| back face to warm screen (0.02 foil stack) | 24 MW | 3.7 MW |
| warm screen to cold mass (1 W/m²) | 2.7 kW (160 kW electric at 20 K) | 0.4 kW (25 kW electric) |

- **Extra hot radiator, by case.**

  | Case | X-ray on coils | Extra hot radiator |
  | --- | --- | --- |
  | T03 basis | 11.9 GW | 11,100 m² |
  | C1 grows with V4 pulse energy | 15.5 GW | 14,500 m² |
  | upper case (Rev 2 C2 envelope) | 30.1 GW | 28,100 m² |

  On T03 geometry that is 23 t at the V4 hot areal mass (T00 quotes 16.7 t), about 24 MW of pumping and 2.4 % of the 494.6 GW hot
  circuit.
- **Lines.** The coolant lines are drawn from each coil to the graded wing's hot-band root, 20-35 m away.
- **Armour.** The P2 armour drawn on C2 still follows the 4.8 m envelope (113 t). On T03 geometry it shrinks with the winding. C1's
  60 t stands.
- **Neutrons.** Nuclear heating is small: T04's 5.5×10⁻⁶ escape gives about 14 kW on the coils. The coils still share the loops'
  per-area fluence, 3-62× REBCO tolerance (T02).
- **Booking it** needs a closure-coil share in a Vertex adapter (T00 X-T06-3).

**Update 2026-11-09 18:00Z (T00 `e24fc7a`).** T00 now books the coil heat in the Vertex adapter (case
`V4_coil_booking` in `results/convergence.json`), as a proxy through `plume_to_hardware` on the same 1,800 K hot loop.
V4 departure mass: 43,211 t at the T03 basis of 11.9 GW (+0.7 %; radiators 3,620 t, hot area 0.476 km², wing tip
10,218 m), 43,301 t at 15.5 GW, 43,668 t at the 30.1 GW upper case (+1.8 %, wing tip 10,359 m). The booking covers
the heat only. The cooling plant (about 24 MW of pumping, tin inventory, lines and pumps) stays a T05 item and is
still unsized. ISS-014 moves from "unbooked" to "booked heat, plant open", and drops below the stretch-stiffness
blocker in section 6.

## 5. Kept

- **Every Rev 2 alternative** is still in `OPT_VERTEX_V4_*`: radiator layouts, the canon blades in the Rev 1 layout, launchers
  REV1/A/B/C, skirts A/B/B2/C, docking and EVA routes.
- **The preferred `ASM_V4` is now:** launcher B, graded wings, coil armour P2 with sized struts and cooling, S5 (`STRUCT_S2` +
  `STRUCT_S3`), corridor K2, skirt B2.
- **The Rev 2 spine placeholder** is kept as `OPT_VERTEX_V4_SPINE_EXT`.

## 6. Remaining design blockers (priority order)

1. **Target survival (T04).** Nothing supports 13,700 g. Below about 6,400 g the launcher must leave the spine bore's present length
   or the tip must move closer (27 J/cm² per pulse and 52 MW/m² at 25 m). This decides whether target injection at 195.7 Hz is possible at all.
2. **X-ray spectrum and per-pulse fluence on solid surfaces (T04, T02).** The shield face (4 J/cm²) and the snout tip (8.3 J/cm²) are
   above published tungsten limits unless the spectrum is hard. Carbon armour or a renewable surface is needed. New: ISS-017.
3. **Closure-coil X-ray, 11.9 GW on T03 geometry (15.5 GW extrapolated, 30.1 GW upper case) (T00, T03).** It is unbooked (needs a
   Vertex adapter share), plus a 24 m³/s liquid-metal loop, plus the coil structure (855-1,281 t, 3-7 GN hoop) still unsized.
4. **Stretch stiffness (T05, T00).** S5 at about 1.2 kt meets 0.2 Hz with full tanks. This needs a coupled slosh, ring-spin and
   attitude-control model and an FE check of J1/J3, plus the bow mass (OD-014 shield mass is OPEN).
5. **Braking attitude (T02, T00).** About 0.3° hold, with the tanks' 1.5 m and the outer longerons' 0.95 m margins in B2's shadow.
6. **Radiator span and spar dynamics (T01).** 20.4 km span; ISS-005 is still open.
7. **Integration texts (T00).** ISS-006 dock position; canon blades retired in V4 only.

## 7. Views

| view | camera |
| --- | --- |
| stretch layouts side by side (S1-S5) | `CAM_VTX_32` (scene `STRUCTURE_COMPARE`) |
| stretch cross-sections (end view, S1-S5) | `CAM_VTX_33` (scene `STRUCTURE_SECTION`) |
| root joint J1, crew trunk end and K2 corridor | `CAM_VTX_34` |
| bow joint J3 | `CAM_VTX_35` |
| coil cooling lines | `CAM_VTX_36` |
| launchers including B-long | `CAM_VTX_20` |
| Rev 2 views (thermal, coils, skirts, true scale) | `CAM_VTX_21`-`31` |

Sources:
- [GA, IFE target fabrication and injection (DT-ice strength, about 10,000 m/s²)](https://fusion.gat.com/pubs-ext/MISCONF00/A23379.pdf)
- [Goodin, target injection and tracking](https://aries.pppl.gov/LIB/MEETINGS/0105-IAEA-IFE-CRP/PDF/Goodin.pdf)
- [LLNL, thermal and structural issues of target injection](https://www.osti.gov/pages/servlets/purl/1811765)
- [Levitated-sabot mockup (< 500 g)](https://www.researchgate.net/publication/330947930_Mechanical_Mockup_of_IFE_Reactor_Intended_for_the_Development_of_Cryogenic_Target_Mass_Production_and_Target_Rep-Rate_Delivery_into_the_Reaction_Chamber)
- [Pulsed X-ray exposures of tungsten (XAPPER)](https://www.osti.gov/etdeweb/biblio/20849929)
- [W thermomechanical damage thresholds under soft X-rays](https://www.sciencedirect.com/science/article/abs/pii/S0920379618305799)
- [IFE dry-wall response to pulsed X-rays and ions](https://www.sciencedirect.com/science/article/abs/pii/S0920379603000097)
