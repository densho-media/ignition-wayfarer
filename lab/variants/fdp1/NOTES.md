<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Variant |
| Status | ACTIVE |
| Question | Can a pulsed D-3He drive with one Fiji magnetic nozzle fly four 0.016 c burns without refuelling? |
| Model base | main 92b83f0 |
| Salvaged from | claude/project-thread-8e13aa @ ec5717d, 2026-11-06 |
| Open owner questions | Target gain (closure needs about 1,100 or more); canon LOCKED 6.0 y mission vs FDP-1 minimum 6.35 y; whether the canon drive topology (one core, four nozzles) changes to one axial nozzle. |
| Review | project files review/fdp1_2026-11-04/ |

# FDP-1 notes

## Function

FDP-1 drives Wayfarer through four 0.016 c burns (accelerate, brake, accelerate home, brake) with no refuelling. Each burn is
4,797 km/s. Pulsed D–³He micro-explosions are ignited by heavy-ion beams. A single Fiji magnetic nozzle (three coaxial loops, each
with four independently powered trim sectors) turns the burning plasma into a directed exhaust. A layered shadow shield protects the
crew and the hardware, and three heat loops carry every watt that is not exhaust to radiators.

## Fixed constraints

- The four-burn calculator (`lab/studies/four-burn-mission/fourburn`, scenario v1) is the only propulsion engine. FDP-1 calls it and does
  not duplicate its physics.
- The canon ship stays unchanged on `main`: data, generators, built assets and the four-nozzle drive. In the review file the
  superseded objects are hidden, not deleted.
- Acceleration may not exceed 1.5 g. 1 g is preferred; less is acceptable.
- Radiator areas are the closure's. They are never shrunk to fit a layout, and the view-factor penalty adds area.
- The 13 existing tanks stay. Added vessels are proposals. The three idle hydrogen vessels are kept, and their dry mass is carried.
- Habitat-ring sweep, docking corridor (Dock_Primary, X 99.40 m, az 195°), EVA routes and the existing hot blades keep their
  clearances.

## Unknowns (OPEN)

- **Target gain.** It is the strongest lever. The baseline needs about 1,100 or more: at 1,000 (rest optimistic) the 0.0069 g design
  does not close.
- Burn fraction (ρR about 90 g/cm²), D–³He ignition and pellet survival at 212 Hz. There is no experimental basis for any of them.
- The magnetic-nozzle detachment efficiency and the 20° plume half-angle.
- Neutron transport: build-up factors, (n,γ), rim scatter, 14 MeV D–T share. The shield is first-order.
- Radiator wing deployment and dynamics at 3.5 km tip radius. The spar mass of 25 kg/m is a placeholder.
- Heavy-ion driver efficiency, repetition rate and lifetime at 212 Hz; final-focus survival 43 m from 19 t TNT-equivalent pulses.
- He-3 supply: 7,840 t of ³He. This is a fuel-economy question, not a drive question.

## Design freedom (PROTOTYPE)

- Module length and radius, gallery count and radius, beam count and folds.
- Coil count and polar angles, strut topology, lattice band.
- Wing layout and root radius, tank layout and bay gap, plug margin.

## Decisions

1. **Tier.** Speculative/optimistic, as the owner selected: gain 3,000, ρR about 90 g/cm². The credible tier runs as the
   `central_tier` variant (70.6 kt, 337 years under thrust).
2. **Departure acceleration.** The baseline holds the four-burn case-5 acceleration (0.0069 g) and lets the mass close. 1 g runs as
   `goal_1g`, which reports the deficit: the highest closable a0 is 0.0112 g, a factor of 89 short.
3. **One nozzle.** It is a paraboloid of three loops with the burn point at the focus. The forward loop sits exactly at the X-ray
   stand-off R_s = 43.2 m, the polar angles are 60/90/120°, and it is open aft. The four "nozzles" of canon become four trim sectors
   per loop. They provide control authority, not separate engines.
4. **Integrated feedback.** The shield mass, the FDP-1 structure, the idle H₂ vessels, the low-loop radiator and the hardware solid
   angle that the drawn geometry actually presents (loops + struts + shield = 0.0195 sr/4π, against the scenario's 0.002) are fed back
   into the closure until the departure mass repeats. This feedback is the main reason FDP-1 comes out at 20.8 kt against the study's
   9.7 kt.
5. **Shield.** LiH, 3.59 m on the crew cone and 1.04 m on the hardware annulus, a 1 cm W face, a frame, and an on-axis plug as thick as
   the crew core + 0.25 m. Total 430 t, replacing the 100 t placeholder.
6. **Radiators.** The lightest layout is W2: two warm wings in the port/starboard plane, which see neither each other nor the
   existing blades. The 1,800 K hot band sits at each wing root, and the three existing hot blades (az 30/150/270°) carry 14,935 m² of
   the hot loop.
7. **Drivers.** Three galleries at r = 12 m, placed in the widest angular gaps (az 90/225/315°), three Pb beams each, folded twice.
   The linac is 444 m long, which is set by 4 GeV at 3 MV/m.
8. **Tanks.** T-B is selected: the farm is stretched forward by four bays (49 vessels, +122.4 m) and the bow assembly moves with it.
   T-A puts the bays aft, close behind the shield. They widen the hardware cone to 22.6°, the shield grows to 1,340 t, and the
   ship costs +11.5 kt. T-C (a third ring at 41.5 m, reaching 77 m) widens
   the hardware shadow cone from 9.6° to 12.9°. The shield grows to 604 t, and the ship costs +2.3 kt.

## Two discrepancies found and resolved

**Gain 300 against 3,000.** Scenario v1 makes the target gain tier-dependent: optimistic 3,000, central 300, pessimistic 50. The
9.7 kt study result uses 3,000. The `CLASS` labels in `fourburn/architectures.py` said "gain 300" for IFD-P/PH. They described the
central value only, so the mismatch was a labelling error, not a second model. The labels now name both tiers. Every FDP-1 record
prints the gain it used (`fusion.target_gain`). The sensitivity runs show what it is worth: at gain 300 with the rest optimistic, the
baseline acceleration cannot be reached (max 0.0028 g).

**Payload 860 t against 990 t.** The four-burn study subtracted a phantom 90 t of legacy tanks and omitted the 40 t CIRC-001 item.
FDP-1 reads the payload from `mass_model.dry_parts` minus the items it sizes itself (`drive_package`, `radiators_thermal`,
`tankage_*`), which gives 990.2 t. The `payload_860t` sensitivity shows the difference: −1,470 t departure.

## Verification

- `tests/test_fdp1.py` has 44 tests. They cover the rocket equation per burn, the mass balance, momentum, jet power, ≤ 1.5 g,
  nonnegative propellant, fused + unburned = fed, energy-ledger closure, no unaccounted heat, radiator capacity, tank coverage, shield
  dose, feedback convergence, the low/high-power and deficit cases, parametric regeneration (coil count, gallery radius), and no
  tracked change outside `work/`.
- `study_reproduction_no_feedback` reproduces the four-burn study's 9,732 t when the feedback is switched off and the 860 t payload is
  used.
