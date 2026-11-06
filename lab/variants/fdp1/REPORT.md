# FDP-1 report: Fiji Drive Pulsed prototype, version fdp1-v1 (2026-11-04)

This is a research prototype on the speculative (optimistic) tier. It is not canon. The numbers come from `run.py`, and the full tables
are in `results/fdp1-v1/TABLES.md`.

## 1. Result in one paragraph

FDP-1 closes the four-burn 0.016 c round trip with no refuelling, but only on the speculative tier.

- **Mass:** departs at **20.8 kt**, ends at 7.6 kt, burns 13.1 kt of D–³He.
- **Drive:** **17.3 TW** of fusion gives 1.40 MN at 19,201 km/s.
- **Acceleration:** **0.0069 g** at departure, rising to 0.019 g at the end of the fourth burn.
- **Time:** **5.7 years** under thrust. The shortest possible round trip, to the 1,716 AU stopping distance, is 6.4 years.
- **Against 1 g:** it is far short. With today's FDP-1 hardware per watt, no ship of any size closes above **0.0112 g**, so 1 g needs
  hardware about **89 times lighter per watt of jet power**.
- **Against the study:** the four-burn study's 9.7 kt doubles to 20.8 kt once FDP-1 carries a real shield, structure and the solid
  angle its own geometry presents.
- **Credible tier:** at gain 300 FDP-1 still closes, at 70.6 kt and 0.0001 g, but with 337 years under thrust.

## 2. Cases

| case | closes | departure | a0 → peak | fusion | under thrust | shortest round trip |
| --- | --- | --- | --- | --- | --- | --- |
| baseline (optimistic) | yes | 20,760 t | 0.0069 → 0.0187 g | 17.3 TW | 5.69 y | 6.35 y |
| low power | yes | 9,907 t | 0.0035 → 0.0095 g | 4.2 TW | 11.2 y | 12.5 y |
| high power | yes | 42,158 t | 0.0085 → 0.0231 g | 43.3 TW | 4.61 y | 5.15 y |
| central tier (gain 300) | yes | 70,603 t | 0.0001 → 0.0004 g | 0.79 TW | 337 y | 390 y |
| owner goal 1 g | **no** | none | max 0.0112 g | | | deficit ×89 |

The acceleration ceiling of 1.5 g is never approached; the peak is 0.023 g in the high-power case.

The baseline four-burn mass history:

| burn | start → end | propellant | days |
| --- | --- | --- | --- |
| 1 accelerate | 20,760 → 16,171 t | 4,589 t | 726 |
| 2 brake | 16,171 → 12,596 t | 3,575 t | 566 |
| 3 accelerate home | 12,596 → 9,812 t | 2,784 t | 441 |
| 4 brake home | 9,812 → 7,643 t | 2,169 t | 343 |

Each burn is exactly 4,796.7 km/s by the rocket equation.

## 3. What FDP-1 is

**Fuel preparation (FDP1_01).** Pellets are frozen D₂ shells holding liquid ³He at about 1.5 K, 18.3 mm across, 0.34 g each. They are
fired at 400 m/s from two gas-gun injectors (one a spare) with a 3,000-pellet magazine. The rate is 212 pellets/s, each yielding about
19 t TNT. About 25 pellets are in flight at once, along a 47 m path. The 18 million pellets a day come from a target factory in the
equipment module.

**Heavy-ion drivers (FDP1_02).** Nine Pb³⁺ beams at 4 GeV run in three galleries at r = 12 m (az 90/225/315°, the widest gaps between
the radiator planes). Each linac is 444 m long, folded twice with 10 T arcs. Each pulse delivers 27 MJ of beam energy from 60 MJ
electric. The drivers weigh 640 t, including 151 t of pulse storage. Every beam enters through a 0.4 m port in the shield, and each
port's line of sight ends in a dog-legged LiH beam dump.

**Reaction zone (FDP1_03).** The zone is open, with no chamber. The burn point is 43.2 m aft of the shield, at the X-ray stand-off
distance. Keep-outs are the X-ray fluence sphere, the crew and hardware shadow cones, and the plume. They are drawn in FDP1_11.

**Fiji magnetic nozzle (FDP1_04).** One nozzle, a paraboloid of three coaxial superconducting loops with the burn point at its focus:

- **Loops:** radii 37.4, 64.8 and 112.2 m, at polar angles 60, 90 and 120°.
- **Control:** each loop has four trim sectors with 5° gaps, which give control authority. They are not four engines.
- **Mass:** the virial structure is 86 t, with 91 t of armour on top.
- **Supports:** six lattice struts per loop, chained loop 3 → 2 → 1 → shield frame.
- **Fiji lattice:** a 70° band on the outer face of each loop carries the Fiji amplification lattice, which (as in canon) amplifies
  and stabilises only.

The four canon nozzles are hidden, not deleted.

**Shielding (FDP1_05).** The total is 430 t, against the four-burn placeholder of 100 t:

| layer | thickness | mass |
| --- | --- | --- |
| LiH crew core | 3.59 m (10.4 neutron decades to the crew budget of 10 mSv/y) | 236 t |
| LiH hardware annulus | 1.04 m (3 decades) | 114 t |
| W X-ray face | 1 cm (3.2 mm needed) | 42 t |
| on-axis LiH plug behind the pellet bore | 3.84 m | 6 t |
| frame | | 31 t |

The crew cone half-angle is 5.3°. The hardware cone is 9.6°, set by the driver galleries.

**Thermal (FDP1_06).** Nothing is left unaccounted, and the ledger closes to 1 part in 10⁹:

- **Jet:** 78.0 % of fusion goes to the jet and 20.3 % into the off-axis plume. 1.13 % leaves as X-rays and neutrons that miss the
  hardware.
- **Hot loop (1,800 K):** 77.1 GW, almost all of it plume striking hardware. It needs 71,977 m², of which the three existing canon
  blades carry 14,935 m².
- **Warm loop (600 K):** 24.4 GW: driver losses, the target factory and power systems, and cryoplant input. It needs **1.84 km²**,
  carried on two edge-on wings (layout W2, port/starboard plane). The wings reach a **3.57 km tip radius**, with the 1,800 K band at
  each root.
- **Low loop (300 K):** 1.5 MW of added cryocooling for the larger farm.

**Structure (FDP1_00).** 529 t in total:

- radiator-wing spars: 356 t;
- driver galleries: 82 t;
- equipment module: 54 t;
- nozzle struts: 37 t. They are sized by buckling at 1.5 g, though FDP-1 peaks at 0.019 g.

The thrust ring carries 1.40 MN, 6 % of the canon Q45 collar limit.

**Tanks (FDP1_10).** The ship needs 143,238 m³ of ³He and 31,999 m³ of D, 7.1 and 6.5 times the existing farm. That means a complete
storage redesign:

- **Selected, T-B:** keeps the 13 existing vessels and adds 49 more in four bays ahead of them. The ship grows by 122.4 m, and the bow
  assembly moves forward. Tankage is 1,231 t and cooling 1.73 MW.
- **Load:** the axial load at 1.5 g would be 9.3 times the existing farm's.
- **Idle hydrogen:** the three hydrogen vessels (15,022 m³) are idle; FDP-1 burns no H. They are kept, as the brief requires, at 105 t.
- **Alternatives:** T-A (aft stack, +11.5 kt) and T-C (outer ring, +2.3 kt). Both are hidden collections in the review file.

**Centre of mass.** The dry ship's centre moves from x = +35.1 m to −9.3 m, and the loaded ship's sits at +113 m. The thrust axis
passes through both, so it needs no trim beyond the nozzle sectors.

## 4. Why the study's 9.7 kt became 20.8 kt

| step | departure |
| --- | --- |
| four-burn study as published (100 t shield, scenario solid angle 0.002, 860 t payload) | 9,732 t |
| + payload read from canon (990 t: the study missed CIRC-001 and subtracted 90 t of legacy tanks that no longer exist) | +1,470 t |
| + real shield, structure, idle H₂ vessels, and the drawn solid angle (0.0195 against 0.002: loops 0.0090, shield 0.0090, struts 0.0015) | +9,558 t |
| **FDP-1 baseline** | **20,760 t** |

Every added tonne of dry mass costs **11.3 t** at departure.

## 5. Levers (the same 0.0069 g, departure against 20,760 t)

| change | departure | Δ |
| --- | --- | --- |
| warm loop at 800 K instead of 600 K | 11,431 t | **−9,329 t** |
| target factory and controls at 0.05 % of fusion instead of 0.1 % | 14,470 t | **−6,290 t** |
| payload 860 t | 19,290 t | −1,470 t |
| idle H₂ vessels removed | 19,574 t | −1,187 t |
| four loops instead of three | 20,749 t | −12 t |
| star struts instead of chain | 21,737 t | +977 t |
| tanks T-C / T-A | 23,099 / 32,217 t | +2,339 / +11,457 t |
| wings W3 / W6 | 25,437 t / does not close | +4,676 t / diverges |
| target gain 1,000 / 300 (rest optimistic) | does not close (max 0.0065 / 0.0028 g) | |

## 6. Limitations (what this prototype does not prove)

- **D–³He ignition** at gain 3,000 and ρR 90 g/cm² is extrapolation. NIF's best D–T gain is about 4. Below a gain of about 1,100 the
  baseline does not close.
- **The 212 Hz cadence** is unproven for heavy-ion drivers, and so is final-focus survival 43 m from 19 t TNT pulses. So is pellet
  survival (³He liquid inside a D₂ shell) during injection.
- **The shield is first-order:** no build-up, no (n,γ) photons, no rim scatter, and a D–D spectrum. Hardware decades are a
  placeholder.
- **Nozzle loops:** their mass is a virial minimum plus armour. The giga-newton attraction between loops is inside that mass and is
  not designed.
- **Detachment efficiency and the 20° plume** are assumptions.
- **Radiator wings 3.6 km long** (9.0 km in the high-power case) have no deployment, dynamics or micrometeoroid design. The spar mass
  of 25 kg/m is a placeholder.
- **The tank bays** are volumes and masses. The bay frames and the bow-move mechanics are not designed.
- **Geometry:** it is placed by the engineering record, but meshes are not inspected against the ship's clearance contract. The seven
  computed clearances all pass.

## 7. Breakthroughs FDP-1 depends on

1. D–³He ignition with a target gain of at least about 1,100. 3,000 is assumed.
2. A heavy-ion driver at 212 Hz for years, with a wall-plug efficiency of at least 45 %.
3. Mass-produced cryogenic ³He-in-D₂ targets, 18 million a day.
4. A magnetic nozzle that detaches 78 % of fusion power into a 20° jet.
5. About 7,800 t of ³He. That is an industrial (lunar or gas-giant) supply question, not a drive question.

## 8. What must improve to bring Wayfarer closer to 0.016 c

In order of leverage, all measured above:

1. **Warm-loop temperature.** It is the largest single lever: 600 → 800 K nearly halves the ship (−45 %). This needs power electronics
   and induction cores that run hot (SiC/GaN at 800 K, or a heat-pump stage).
2. **Recirculating power.** Halving the target-factory and control load saves 30 %. Every watt of house power becomes 600 K heat.
3. **Hardware solid angle.** The nozzle loops and the shield each intercept about 0.9 % of the burn. That is ten times the study's
   allowance, and it doubles the ship. Gains come from thinner loop envelopes (higher-field conductor, less armour), a narrower
   hardware cone (move the galleries in or shield them separately), and a smaller shield face.
4. **Target gain.** It is the cliff, not a slope: the design only exists above a gain of about 1,100.
5. **Dry mass discipline.** Every tonne costs 11 t at departure. Leaving the idle hydrogen vessels behind saves 1.2 kt. The payload
   must be booked from canon (+1.5 kt over the study).
6. **The 1 g goal** needs drive-plus-radiator mass per watt of jet power 89 times lower (3.0 × 10⁻⁹ kg/W against 2.7 × 10⁻⁷). No
   combination of the levers above reaches it. 0.01 to 0.02 g is the honest regime for this physics.

## 9. Colour hierarchy

The colours follow `src/wayfarer/functional_colors.py`:

| colour | system |
| --- | --- |
| grey | structure |
| ochre | shield |
| magenta | main propulsion |
| indigo | power and drivers |
| teal | deuterium |
| violet | ³He |
| blue | hydrogen |
| red | hot 1,800 K |
| orange | warm 600 K |
| pale blue | low 300 K / cryo |
| cyan | sensors and guidance |
| cream | service |

Plasma, X-ray and beam overlays are translucent and illustrative. Every part carries `fdp1_status`, which is one of:

- ENGINEERED: placed by a computed number;
- PLACEHOLDER: drawn volume, design open;
- ILLUSTRATIVE: not hardware.

## 10. Outputs

| what | where |
| --- | --- |
| review file (packed, opens on the aft assembly) | `/mnt/project-files/review/fdp1_2026-11-04/REVIEW_FDP1.blend` |
| renders, 1920×1080 Workbench | `/mnt/project-files/review/fdp1_2026-11-04/renders/` (CAM_01 side elevation … CAM_09 tank comparison, plus close-ups) |
| energy-flow diagram | `diagrams/energy_flow_baseline.png` (also in the review file, scene FDP1_ENERGY_FLOW) |
| engineering records | `results/fdp1-v1/*.json`, tables `results/fdp1-v1/TABLES.md` |
| config, generator, calculator integration | `config/`, `blender/build_fdp1.py`, `engineering/` |
| tests | `tests/test_fdp1.py` (44, `python3 -m unittest discover -s lab/variants/fdp1/tests`) |
