# PSA Phase I report: owner review gate

STUDY / NONCANON. Base: main `11f1e94`, ISSA `5eae701`. All numbers are from `results/psa_phase1.json` (first-order,
±30-50 %), labelled RESEARCH unless marked FICTIONAL-BASELINE. No production geometry, parameter, budget or Drive row is changed.

## 1. Answer in brief

- **Loads are thrust-bounded.** The drive is power-limited at 21.77 MN in all three configurations (P 4.5 kt, F1 8.2 kt,
  R 12.9 kt), so a heavier ship accelerates less and the sections see nearly the same force: ~21 MN at the transition,
  ~16 MN at the tank-farm aft face, under 2 MN at the shield root. The canon envelope (1.5 g on the full ship) is 63.5 MN,
  three times what the drive can push.
- **The 150 t main-structure line does not close with lunar aluminium alone.** A conventional all-aluminium frame (A) is
  ~240 t under flight loads and ~650 t under the canon envelope. Only multi-material zoning (C 138 t, HC 157 t) or moving
  the tank farm aft (G 117 t) gets near 150 t, and the line must also hold 25 t of rotating structure.
- **Recommended Phase II pair: H (vertebral modular skeleton, lunar-first, ~200 t) and HC (H with alumina-fibre/Al and
  CF/PEEK cassettes, ~160 t).** H wins on lifecycle and yard weights; HC wins on mass weight. Both use 6 paired rails.
- **Each tonne of structure costs ~3.6 t of departure mass** (propellant and tankage growth), so 80 t saved is ~290 t at departure.

## 2. What is credible, and what the existing design gets right

| Existing feature | Assessment |
| --- | --- |
| 4 nozzles → 12-node ring → 8 m transition → 3 sectors + spine (07 BASELINE) | Correct topology: thrust enters at the aft end and spreads into a few long compression members. |
| 4 m frame spacing, 3 sectors at r 5 m | Sound: bay buckling, not strength, governs titanium and composite rails at this pitch. |
| Kinematic mounting of blades and tanks (one datum + slides) | Correct and essential: it must extend to the hot loop, the spine and every long system. |
| Tank farm aft fixity + forward V-links, 0.095 m contraction vs 0.20 m slide | Credible. |
| Brow bypass collar around the rotor bay (Q45) | Necessary: the rotating rings break any straight path forward. |
| Counter-rotating rings locked before thrust | Correct: spin torque (28 kN·m) never enters the frame under thrust. |
| Fixed radiator blades on root booms and stays | Correct, but their backbone runs at 1650-1800 K: it belongs to thermal and must be C/C or refractory. |

## 3. What needs reconsidering

1. **Design load (PSA-P01, D01).** Use a thrust-bounded design load (power-limited thrust × DLF × ultimate factor) with a
   stated abort/transient case, and keep 1.5 g as a proof envelope only where a real event can produce it.
2. **Nozzle pickups at 78.7° (PSA-P04).** They multiply each 7.35 MN share into 37.7 MN per strut. Re-angled to ≤ 17° from
   the axis they carry ~1.9 MN.
3. **3 single rails (PSA-P08, D03).** One cut rail removes a third of the axial area and the symmetry. 6 paired keels cost
   0-40 % more rail mass and survive a cut.
4. **Tank shells in the 150 t line (PSA-P03, D04).** The owner rule and the 458 t modelled tankage cannot both hold.
5. **Global stiffness (PSA-P05).** A strength-sized frame has f1 ~0.06-0.12 Hz. Follower thrust is far less critical than
   static Euler (a factor of ~11 in EI), but TVC-structure coupling must be modelled before the rail radius is frozen.
6. **Thermal growth (PSA-P07).** Aluminium grows ~1 m over the ship for 150 K, titanium 0.36 m, CFRP ~0. A mixed structure
   needs designed slides at every material boundary.

## 4. Materials

**Promising (R track)**

| Role | Material | Why | Lunar? |
| --- | --- | --- | --- |
| Frames, rails, general | Al 6061 / 5083 | lunar Al-Mg-Si, weldable (FSW), proven | yes |
| Lightweight rails | Al₂O₃-fibre / Al MMC | lunar alumina fibre; 23 t of longerons vs 83 t Al | yes (RESEARCH route) |
| Long cassettes | CF/PEEK thermoplastic | 21 t of longerons, CTE ~0, weldable in orbit | no: carbon imported |
| Nodes, thrust frame | Ti-6Al-4V (DED + HIP) | ilmenite Ti, strength at 500-700 K | V imported (~4 %) |
| Hot stand-offs | Inconel 718 + YSZ | 2-stage break: ~120 W → ~13 W into the frame | Ni/Cr partly lunar (FeNi) |
| Cryo struts | G-10/GFRP | low conductivity | glass lunar, resin imported |
| Blade backbone | C/C, SiC/SiC | only classes that survive 1800 K | no |

**Restricted:** 2xxx/7xxx and Al-Li (Cu, Zn, Li imports; Al-Li is the tank-shell alloy), steels (heavy; ferromagnetic:
excluded where |∇B| > 10⁻³ T/m), Mg (flammability, creep), monolithic ceramics (brittle), additive parts in primary load
paths without ISM-33 qualification.

**Excluded:** Fiji as a structural material (canon: cannot be synthesised; reserved for the drive).

**F track (FICTIONAL-BASELINE bridging advances):** nano-dispersed Al-Sc, CNT/CFRP, CNT yarn tension stays, SiC/SiC at
1800 K (linked to ISSA FT-01), graded Ti-SiC nodes, embedded sensing and self-healing layers. They are kept out of every R mass.

## 5. How Luna Yard builds it

1. **Luna (surface):** regolith → molten-salt or FFC electrolysis → Al, Ti, Si, Fe, O₂; casting and rolling of Al plate,
   extrusion of rail profiles, alumina fibre drawing (RESEARCH), Ti wire for DED.
2. **Luna Lift → Harbor:** profiles, plate, wire and fibre go up as bulk (ISM-29/30). Imports (carbon fibre, V, resin)
   arrive at Harbor.
3. **Yard (microgravity):** each vertebra (8-12 m bay: two deep frames, node rings, hard-points, service corridors) is
   built in one jig by FSW and DED nodes, NDT-inspected and proof-loaded as a class C module (ISM-14).
4. **Stack:** vertebrae join by longeron cassettes (pinned or bolted, exchangeable), then the thrust ring, collar and Brow
   keels; systems mount kinematically on standard hard-points.
5. **Proving ground (ISM-31):** a thrust test at a separate site before the ship is crewed.

Embodied energy: MX-A 6.7-17 GWh per 150 t (1.5 % imports), MX-H 9-23 GWh (11 %), MX-C 13-31 GWh (54 %).

## 6. Concepts

| | Concept | P flight | Canon 1.5 g | F1 flight | Pareto |
| --- | --- | --- | --- | --- | --- |
| A | Conventional modular spaceframe (Al) | 239 t | 649 t | 234 t | |
| B | Hybrid lattice, optimised nodes | 226 t | 608 t | 221 t | |
| C | Multi-material hybrid skeleton | 138 t | 338 t | 136 t | ● |
| D | Continuous manufactured lattice | 165 t | 425 t | 162 t | |
| E | Deep cellular / stressed-skin hull | 313 t | 583 t | 308 t | |
| F | Wide cage / parallel keels | 267 t | 716 t | 261 t | |
| G | Integral tank-structure (tanks aft) | 117 t | 278 t | 117 t | ● |
| H | Vertebral modular skeleton | 197 t | 492 t | 193 t | ● |
| HC | Vertebral + multi-material zoning | 157 t | 359 t | 155 t | ● |

Rankings: W-MASS HC > H > C; W-LIFECYCLE H > HC > A; W-YARD H > A > HC. A mass-weight sweep picks H up to 0.4, HC from 0.5.
H and HC were proposed and scored by PSA: Phase II re-scores them from computed models.

G is the lightest but moves cryogenic He-3 and D₂ into the drive's neutron and heat zone; it is an ISSA-level layout
question, not a structure choice. E is heavy because shell buckling is inefficient at this low load intensity. F only
pays if engines are widely separated (Vertex cluster).

## 7. How PSA and ISSA develop together

- **Shared interface PSA-IF 0.1** (`data/interface.toml`): ISSA owns equipment requirements, PSA owns zones, hard-point
  classes (HP-S 10 kN, HP-M 50 kN, HP-L 250 kN, HP-X per item), stiffness, keep-outs and corridors. Unknowns are OPEN.
- **Strongest couplings:** the H6a hot loop (565 t F1, 1,833 t R at 1990 K over 170 m), the L2 power district (3 × ~97 t
  at X -92..-80), the thermal bulkhead station (F1 X 42.76), the tank-farm growth option, the drive stray field.
- **Handoffs HO-01..05** in `HANDOFF_ISSA.md`.

## 8. Subsystem classification (dual philosophy)

| Subsystem | Established physics | Contemporary capability | Unresolved challenge | Plausible advance | Adopted fictional assumption |
| --- | --- | --- | --- | --- | --- |
| Longitudinal structure | inertial load N = T·m_ahead/M | Al/Ti/CFRP trusses (ISS, launch vehicles) | 150 t line with lunar material | lunar Al₂O₃f/Al MMC at scale | HC-class cassettes ~160 t (FICTIONAL-BASELINE until Phase II) |
| Thrust frame | load spreading, fatigue | Ti forgings, DED Ti | kHz pulse fatigue (10¹⁰-10¹¹ cycles/yr) | qualified DED + HIP with endurance data | thrust frame fatigue-qualified |
| Hot interfaces | radiative and conductive heat | YSZ/Inconel stand-offs | 1990 K trunks over 170 m | SiC/SiC at 1800 K (F-SICSIC-1800) | ISSA FT-01 |
| Blade backbone | 1800 K two-sided emitter | C/C in re-entry | long-life C/C in vacuum at 1800 K | oxidation-free C/C, SiC/SiC | thermal-owned refractory backbone |
| Manufacturing | electrolysis, FSW, DED | terrestrial; ISS-scale printing | microgravity throughput of 150-250 t | Yard automation (ISM-32..37) | Luna Yard per canon ISM chain |
| Health monitoring | strain, AE | FBG, AE in aircraft | full-ship digital twin | embedded sensing layer | F-SMART-LAYER |

Bridging advance named for each gap above; none needs a change of physical law.

## 9. Conflicts and unresolved items

PSA-P01..P20 in `data/problems.toml`. Critical: P01 design load, P02 150 t line, P03 tank-shell double count. Major: pickups,
global modes, blade backbone, thermal growth, rail count, ferromagnetic exclusion, pulse fatigue, hot-loop supports, forward
tank farm, carbon imports, DED throughput, unverified properties.

## 10. Next experiments (Phase II, on owner go)

1. 3D frame FE (`src/wayfarer/fe_frame.py`, reused unchanged) of A, H, HC and G: sizing, modes, one-rail-cut redistribution.
2. Follower-thrust stability vs fixed-direction Euler on the same model.
3. Re-angled nozzle pickup study.
4. Thermal-gradient loads for a mixed Al/CFRP/Ti vertebra.
5. Hot-loop stand-off design with ISSA data (HO-01, HO-04).

Owner questions PSA-D01..D08 are in `NOTES.md`.
