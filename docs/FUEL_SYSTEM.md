# Fuel & Propellant System (FPS)

Owner briefs 2026-11-18 ("Wayfarer Propulsion — Fuel & Propellant System", V0) and 2026-11-19 ("Fuel & Propellant System V1, Continue
Engineering, Modeling, and Engine Integration": D–³He fuel baseline with D–D kept for evaluation, H2 reaction mass with water kept as an
alternative, feedstock water ice refined off-ship). Version 1 (section 9) closes the chain from the farm to every engine's burn.
PROTOTYPE geometry. Code: `src/wayfarer/fuel_system.py`
(pure: flows, regimes, trades, routes, fit screen), `src/wayfarer/components/fuel_feed.py` (Blender, `WF_STORAGE`), parameters
`[fuel_system]` in `data/wayfarer_3d.toml`. The forward storage it starts from is TANK-AXIAL (`fuel_storage.py`, docs/MODEL.md "Tank-farm
load path"). `python3 src/wayfarer/fuel_system.py` prints every number quoted here.

## 1. What the ship already had, and what was missing

The audit (2026-11-18) found storage complete and the last 40 m missing:

- **Existing:** thirteen axial vessels in the forward farm (6 He-3, 5 H2, 2 D2) on skirts and a thrust deck, outlet valves into one ring
  main per species and ring, two cryocooler cold boxes per species, two transfer trunks per species (exterior leg along the bypass
  collar, hull penetration, interior lane) to four feed run tanks (`Feed_Run_Tank_01` D2, `02` He-3, `03`/`04` H2, X -105.25 to -93.25).
- **Missing in the shown ship:** the Vertex cluster replaced the Fiji drive, but `CRYO_FEED_LINE_01..04` still ended on the Fiji core face
  and injection ring, inside what is now the cluster's power and conditioning bay. The cluster carries a `TARGET_FEED` trunk from that bay
  to the engines and no hydrogen line at all. Nothing metered, conditioned, isolated, vented, purged, instrumented or refuelled the feed.

## 2. Version 0 architecture

Fusion fuel, reaction mass and feedstock are kept apart (canon `propulsion.inventories`: never mix bulk hydrogen into the fuel inventory).

| | V0 choice | Path |
| --- | --- | --- |
| Fusion fuel | **Deuterium** (D-D capable reactor assumed); **helium-3** kept as the canon second fuel | farm → transfer → run tank → outlet valve → metering and conditioning unit → isolation valve → own stepped shield sleeve → `IF_FPS_FUEL_BAY_*` on the cluster bay (target fabrication, engine side) |
| Reaction mass | **Hydrogen** | farm → transfer → run tanks 03/04 → outlet valve → boost pump → conditioning skid (filter, vaporiser/heater, mass-flow controller) → isolation valve → shield sleeve → cage-to-skin corridor → inside the thrust ring → header ring → one branch per engine → `IF_FPS_H2_ENGINE_0n` |
| Feedstock | **Water ice**, refined off the ship | the ship receives D2, He-3 and H2 at the refuelling receptacle |

The D : He-3 blend is a setpoint at the target fill (`fuel_system.he3_per_d_molar`: 1.0 is the canon D-3He point, 0 is the V0 D-D mode),
so either fuel cycle uses the same hardware. Removing the helium-3 stores would change the canon inventory and the engine workstream's
He-3 supply request, so V0 keeps them (section 6 shows what a D-only burn costs).

Operating states (browser demonstration, section 5): STANDBY (valves shut, cryocoolers holding), PREP (purge, chill-down, pumps primed),
IGNITION (fuel only, H2 shut), PROPELLANT FEED (H2 opens), ACTIVE (operating point), THROTTLE (H2 factor 0 to 2 at fixed jet power),
SHUTDOWN (H2 first, then fuel; purge), REFUEL (couplings mated, fill lines open, engines safe).

## 3. Engineering numbers (operating point, peak of the first burn)

Flows follow the B01 burn's proportions (`fuel_system.flows`); "per engine" divides by four.

| | Whole ship | Per engine | Liquid flow | Run-tank endurance | Mission load |
| --- | --- | --- | --- | --- | --- |
| D (fuel) | 0.296 kg/s | 74 g/s | 1.7 L/s | 12.1 h | 731 t |
| He-3 (fuel) | 0.444 kg/s | 111 g/s | 7.6 L/s | 2.7 h | 1,094 t |
| H2 (reaction mass) | 0.385 kg/s | 96 g/s | 5.4 L/s | 7.6 h | 972 t |
| Total exhaust | 1.134 kg/s | 0.283 kg/s | | burn 9.99 days | |

- **Line size:** at 2 m/s the liquid bores are 16 mm (D), 35 mm (He-3) and 29 mm (H2, per engine). The 0.16 m display line is the vacuum
  jacket. The run tanks hold hours, the burn lasts ten days, so the transfer trunks run continuously.
- **Transfer head:** the farm deck is 200 m forward of the run tanks; under thrust (0.50 to 0.64 g) transfer is downhill, adding 173 to
  222 kPa (D2), 58 to 74 kPa (He-3) and 70 to 90 kPa (H2) at the run tanks. In the coast there is no head: transfer needs tank pressure and
  propellant management devices (OPEN). The aft RCS jets are canted aft and settle the run tanks before a start.
- **Hydrogen conditioning:** 4.45 MJ/kg from 20 K liquid to 300 K gas, 1.7 MW at the peak flow, taken from the warm loop (a small heat
  sink, not a source). Ionising it outside the engine would cost 0.58 GW, so the injected gas is ionised by the exhaust (engine side).
  Boost pump power about 5.4 kW per MPa of rise.
- **Thrust regimes at the fixed 209 TW jet power:** H2 off gives 17.7 MN at 23,600 km/s (0.079 c); the operating point 21.8 MN at
  19,200 km/s; twice the hydrogen 25.2 MN at 16,600 km/s; three times 28.2 MN at 14,800 km/s. This assumes the jet keeps its directed
  efficiency with any hydrogen load. The coupling of MeV fusion products to cold hydrogen is SPECULATIVE and belongs to the engine.
- **Centre of mass:** every vessel drains in proportion with zero lateral moment (docs/MODEL.md "Placed mass model"); the CG moves 11.4 m
  aft over the first burn. The aft feed train holds under 0.5 t of fluid and does not move it measurably.
- **Recovery:** B01 assumes 80 % burnup with 95 % recovery of the unburned fuel (0.18 kg/s back to the feed). A pulsed target engine
  cannot return unburned fuel, so the Vertex cluster either reaches near-complete burnup or the lost feed grows; flagged to the engine thread.

## 4. Interfaces with the engine workstream

The FPS stops at declared empties (`IF_FPS_*`, `engineering_status` OPEN). It changes no engine or cluster file.

| Interface | Where (ship frame) | Delivered | Owner beyond |
| --- | --- | --- | --- |
| `IF_FPS_FUEL_BAY_D2` | X -114.25, r 4.17, az 45°, bay forward face | D2 liquid ~20 K, metered, 0.296 kg/s peak | target fabrication in the cluster bay, `CL_Trunk_TARGET_FEED` |
| `IF_FPS_FUEL_BAY_HE3` | X -114.25, r 4.17, az 135° | He-3 ~3 K, metered, 0.444 kg/s peak (0 in V0 D-D mode) | as above |
| `IF_FPS_H2_ENGINE_01..04` | X -142.7, r 18.4, engine azimuth: collar, 2 m forward of the cradle plane | H2 gas ~300 K, mass-flow controlled, 0.096 kg/s each | the engine's injection manifold and energy coupling (SPECULATIVE) |
| `IF_FPS_H2_HEADER` | X -137.75, ring r 3.4 | either trunk feeds all four branches | FPS |
| `IF_FPS_SHIELD_*` | shadow-shield slab | stepped sleeves, no core-to-tank line of sight | OD-026 (dose, intercepts) |
| `IF_FPS_REFUEL` | farm deck rim, az 242.8°, r 33.2 | tanker umbilical, one dry-break coupling per species | refuelling standard OPEN |
| `IF_FPS_VENT_01..04` | hull skin, X -93.85 | relief vent penetration, tee outlet | FPS |

Power: boost pumps ~2 to 11 kW each, the H2 heaters take 1.7 MW of warm-loop heat, valves and sensors are small. Telemetry: every line's
pressure, temperature and flow sleeve reports to the drive controller; the isolation valves close on leak (jacket vacuum loss, pressure
decay), fire, or reactor trip. Unresolved: the engine-side target fabrication rate (one engine at 5.7 kHz with 6.6 mg targets burns about
38 g/s against the ~185 g/s of fuel per engine the operating point needs), the H2 injection point inside the engine, and who owns the
service panel's seventh line.

## 5. Model inventory (authoritative, V1.1)

This table is the one FPS inventory; sections 9.6 and 10.2 describe what each version added. State at V1.1 release readiness (section 11).
Status: planned, blockout, detailed, integrated, validated (built, clash-screened by `lab/studies/fuel-propellant/probe.py --cluster`, pipe ends
by `endpoints.py`, removal path by `extraction.py`, whole-ship inspection PASS). Confidence: ESTABLISHED (existing engineering), PLAUSIBLE (extrapolation),
SPECULATIVE (breakthrough), UNSUPPORTED. Every FPS object carries `fps_id`, `function`, `species`, `confidence` and `engineering_status`.
Positions are ship frame (+X bow); the existing farm items are documented in docs/MODEL.md.

| ID | Component | Assembly | Function | In → out | Location / size | Confidence | Pri | Status | Model |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPS-ST-HE3 | He-3 vessels (6) | Fuel storage | store He-3 at ~3 K | refuel → ring main | farm X 109-138, r 27.75, 13.5 m dia | ESTABLISHED tank, PLAUSIBLE 3 K | 1 | integrated | `Fuel_Tank_O*_He3` |
| FPS-ST-D2 | D2 vessels (2) | Fuel storage | store D2 at ~20 K | refuel → ring main | farm, inner ring r 13.5, 11.5 m dia | ESTABLISHED | 1 | integrated | `Fuel_Tank_I1/I3_D2` |
| FPS-ST-H2 | H2 vessels (5) | Propellant storage | store LH2 at ~20 K | refuel → ring mains | farm, outer and inner rings | ESTABLISHED | 1 | integrated | `Fuel_Tank_*_H2` |
| FPS-ST-MNT | skirts, deck, guides | Supporting structure | fix aft, guide forward | thrust → collar | farm deck X 107-109 | ESTABLISHED | 1 | integrated | `Fuel_Skirt_*`, `Fuel_Deck_*`, `Fuel_Fwd_Link_*` |
| FPS-ST-CRYO | cryocoolers (6) | Fuel/propellant storage | zero boil-off, 0.40 MW to LOW | tanks → LOW radiator | deck aft face | PLAUSIBLE | 2 | blockout | `Fuel_Cryocooler_*` |
| FPS-TR-MAIN | ring mains, outlets, valves | Distribution | join vessel outlets | vessels → trunks | deck forward face | ESTABLISHED | 1 | integrated | `Fuel_Ring_Main_*`, `Fuel_Outlet_*`, `Fuel_Valve_*` |
| FPS-TR-TRUNK | transfer trunks (6) | Distribution | farm → run tanks, A/B redundant | ring main → run tank | bypass collar, keel lanes, ~260 m | ESTABLISHED | 1 | integrated | `Fuel_Transfer_*` |
| FPS-RT | feed run tanks (4) | Fuel/propellant storage | buffer, settle, condition | trunk → feed line | X -105.25..-93.25, r 1.4 × 12 m | ESTABLISHED | 1 | blockout | `Feed_Run_Tank_0n` |
| FPS-VL-OV | run-tank outlet valves (4) | Distribution | isolate each run tank | tank sump → line | X -105.55 | ESTABLISHED | 1 | blockout | `FPS_Outlet_Valve_*` |
| FPS-CU-D2 / He3 | fuel metering and conditioning units | Fuel conditioning | filter, sample, trim P/T, meter | run tank → isolation | X -106.6..-108.6, 2.0 × 0.8 × 0.7 m | ESTABLISHED | 1 | blockout | `FPS_Fuel_Meter_*` |
| FPS-PU-H2 | LH2 boost pumps (2) | Propellant distribution | raise feed pressure | run tank → skid | X ~-106.3, r 0.3 × 0.9 m | ESTABLISHED | 1 | blockout | `FPS_Boost_Pump_H2_*` |
| FPS-CU-H2 | H2 conditioning skids (2) | Propellant conditioning | vaporise/heat to 300 K, flow control | pump → isolation | X -107.35..-109.55, 2.2 × 0.9 × 0.8 m | ESTABLISHED | 1 | blockout | `FPS_H2_Conditioner_*` |
| FPS-VL-EIV | emergency isolation valves (4) | Safety | fail-closed ahead of the shield | → sleeve | X -112.3 | ESTABLISHED | 1 | blockout | `FPS_Isolation_Valve_*` |
| FPS-DL-D2 / He3 | fuel feed lines (2) | Fuel distribution | to the bay through own sleeves | run tank → `IF_FPS_FUEL_BAY_*` | X -105.25..-114.25 | ESTABLISHED | 1 | blockout | `FPS_Feed_D2`, `FPS_Feed_He3` |
| FPS-DL-H2 | H2 trunks A/B | Propellant distribution | corridor r 5.4, inside the ring r 3.4 | run tank → header | X -105.25..-137.75 | ESTABLISHED | 1 | blockout | `FPS_Feed_H2_A/B` |
| FPS-HD-H2 | H2 header ring | Propulsion interface | cross-feed to four engines | trunks → branches | X -137.75, r 3.4 | ESTABLISHED | 1 | blockout | `FPS_H2_Header` |
| FPS-BR-N1..N4 | H2 branches (4) | Propulsion interface | header → engine collar inlet | header → `IF_FPS_H2_ENGINE_0n` | X -137.75..-142.7, r 3.4 → 18.4 | PLAUSIBLE | 1 | blockout | `FPS_H2_Branch_N*` |
| FPS-IN | sensor sleeves (P, T, flow) | Instrumentation | measure, leak detect | on every line | 3 per feed line, 1 per branch | ESTABLISHED | 2 | blockout | `FPS_Sensors_*` |
| FPS-SS | line clamps | Supporting structure | trunks to primary frames | | corridor frame stations | ESTABLISHED | 2 | blockout | `FPS_Supports_*` |
| FPS-RV / VT | relief valves, vents, tee outlets (4) | Safety | boil-off and overpressure, non-propulsive | run tank → space | X -93.85, hull skin | ESTABLISHED | 2 | blockout | `FPS_Relief_Valve_*`, `FPS_Vent_*` |
| FPS-PG | He purge bottles and lines (2) | Safety | inert H2 lines | bottle → isolation valve | X -110.95 | ESTABLISHED | 2 | blockout | `FPS_Purge_He_*` |
| FPS-RF | refuelling receptacle, couplings, fill lines, valves | Refuelling | receive D2, He-3, H2 | tanker → ring mains | farm deck rim, az 242.8° | ESTABLISHED | 2 | blockout | `FPS_Refuel_*` |
| FPS-XO-H2 | H2 inner–outer crossover + valve | Propellant distribution | let inner-ring H2 vessels reach the trunks | `Fuel_Ring_Main_H2_I` → outer main | farm, az 315° | ESTABLISHED | 1 | validated | `FPS_H2_Crossover*` |
| FPS-FT-* | hull feedthroughs (6) | Distribution | carry each trunk through the aft hull skin | trunk exterior → interior leg | aft hull skin | ESTABLISHED | 1 | validated | `FPS_Feedthrough_*` |
| FPS-TI-01..04, FPS-VL-CK-* | run-tank inlet tees, nozzles, inlet and check valves | Distribution | fill each run tank through its cap | trunk → run tank | run-tank caps | ESTABLISHED | 1 | validated | `FPS_Tank_Inlet_*`, `FPS_Check_Valve_*` |
| FPS-FAB-* | target fabrication: receiver dewars (D2, He-3), purifier/blend unit, fill and layering station, inspection with reject chute, buffer magazine, conveyor | Fuel conditioning (engine side) | make D–³He targets | `IF_FPS_FUEL_BAY_*` → buffer magazine | cluster bay core, r < 1.9 | ESTABLISHED dewars, **SPECULATIVE** process and rate | 1 | blockout, validated geometry | `FPS_Fab_*`, `FPS_Bay_Target_Fabrication_*` |
| FPS-FAB-XFER | cold-target transfer | Fuel distribution | buffer magazine → target trunk | `IF_FPS_FAB_TRUNK` → `CL_Trunk_TARGET_FEED` | bay aft face | PLAUSIBLE | 1 | validated | `FPS_Target_Transfer_Bay` |
| FPS-TF-N1..N4 | target feeds, panel → magazine, flanged | Propulsion interface (engine side) | deliver targets into each engine | `TARGET_FEED` slot → `IF_FPS_TARGET_Nj` | engine collar, r 5.8 → 3.7 | PLAUSIBLE | 1 | validated; CANDIDATE for the engine workstream | `FPS_Nj_Target_Feed`, `FPS_Nj_Flanges` |
| FPS-IJ-N1..N4 | H2 control valve, line, manifold ring, 8 fast-valved ports | Propulsion interface (engine side) | puff H2 ahead of each pulse | `IF_FPS_H2_ENGINE_0n` → `IF_FPS_H2_INJECT_Nj` | collar → burn face | **SPECULATIVE** coupling | 1 | validated; CANDIDATE | `FPS_Nj_H2_*` |
| FPS-IJ-Nj-P | shielding galleries round each port at the collar and the shadow shield | Shielding | no straight streaming path | — | X −9.15 … −12.30 | PLAUSIBLE | 2 | blockout | in `FPS_Nj_H2_Injectors` |
| FPS-SS-Nj | target-feed clamps (2 per engine, low-conductance standoffs) and cold-strap collars on the feed and the H2 line, inside the panel/inlet turns | Supporting structure | hold cold lines, intercept heat leaks | — | engine collar | PLAUSIBLE | 2 | validated (collars moved inside the removal passage at release readiness) | `FPS_Nj_Supports` |
| FPS-TI-V11 | thermal intercepts on the feed lines at the shield sleeve, the feedthroughs and the bay legs | Insulation | cold-strap heat leaks to the LOW loop | — | aft train, bay fore face | PLAUSIBLE | 2 | validated | `FPS_Thermal_Intercepts` |
| FPS-PMD-* | gallery vanes (4) and aft sponge (8 plates) in 4 run tanks and 13 farm vessels | Propellant storage | coast transfer without settling thrust | vessel → outlet | in the vessels | ESTABLISHED principle, sizing OPEN | 2 | blockout | `FPS_PMD_Run_Tanks`, `FPS_PMD_Farm` |
| FPS-EQ-* | boost-pump motors, heat-exchanger shells, pressure regulators, flow-meter spools | Conditioning | pump, heat, regulate, meter | on the V0 train | aft train | PLAUSIBLE | 2 | blockout | `FPS_Equipment_Detail_*` |
| (engine/cluster) | service panel at the shared 0.36 m pitch, forward of the cradle | Propulsion interface | one face for six services | `CL_Nj_Line_*` → `IF_VTX_*` | collar forward face, X −9.2 … −8.3 | PLAUSIBLE | 1 | validated | `VTX_Service_Panel` |
| (cluster) | flank thrust ties (8), cradle R 6.8 m, trunk spider rings (3), annular power bay | Supporting structure | cradle → thrust ring outside the engines | cradle → ring nodes | cluster frame | PLAUSIBLE (FE screen, section 11.2) | 1 | validated | `CL_Nj_Flank_Tie_A/B`, `CL_Nj_Cradle`, `CL_Trunk_Spider_*` |
| (removal) | engine removal: pins out, line spools out, engine aft on a guided stroke | Service | replace an engine | — | each engine | PLAUSIBLE; guidance fixture OPEN | 2 | validated geometry (section 11.3) | — |
| FPS-MLI | MLI and cooled shields | Insulation | 0.3 / 0.15 / 0.01 W/m² | | in the 0.30 m wall stack | ESTABLISHED | 3 | in wall stack, not drawn | — |

Unresolved engineering assumptions (V1.1):

| Assumption | State | Owner |
| --- | --- | --- |
| Engine fusion power is 1/7.31 of the ship operating point (section 10.3) | OPEN, visible | engine workstream |
| H2 takes its energy from the charged debris (snowplow coupling, section 9.3) | SPECULATIVE, not validated; 80 % jet share not claimed | engine workstream |
| Target recipe, fill and cryogenic layering, fabrication rate | SPECULATIVE | engine workstream |
| Drawn Vertex mass (6.4 kt) outside the 250 t drive allowance (section 11.1) | OPEN canon decision | owner |
| CONSERVATIVE-field frame case (1.66) and the thrust-ring node joints (section 11.2) | OPEN | engine workstream |
| Removal guidance fixture, spool joints and pin stroke (section 11.3) | PROTOTYPE allowances | FPS / cluster |
| PMD sizing, pressurant, boil-off return | OPEN | FPS |
| Pump, heater, valve and regulator hardware; fast-valve life at 5.7 kHz | OPEN | FPS |
| Clamp spacing against pulse-rate vibration | OPEN | FPS |
| Vent set points and plume keep-outs; refuelling approach and umbilical loads | OPEN | FPS |
| Vessel ullage (the +83 t case fills He-3 to 98.4 %) | OPEN | FPS |

## 6. Trade study

Classification: **E** established physics and engineering, **P** plausible extrapolation, **S** major speculative breakthrough,
**U** currently unsupported.

**Fusion fuels** at the operating point's 261 TW of fusion power (`fuel_system.fuel_cycles`):

| Fuel | Specific energy | Fuel flow | Neutron share | Neutron power | Mission fuel | Supply | Class |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D-T | 3.37e14 J/kg | 0.77 kg/s | 80 % | 209 TW | 1.9 kt | tritium decays 5.5 %/yr, bred from Li-6 in a blanket the ship would carry | physics E, reactor P; unfit for a six-year ship |
| D-D (no product burn) | 8.7e13 J/kg | 2.99 kg/s | 34 % | 88 TW | 7.4 kt | D from any water | physics E, reactor S; the fuel alone exceeds the 1.13 kg/s exhaust: the mission does not close |
| D-D catalysed (T and He-3 burned in place) | 3.45e14 J/kg | 0.76 kg/s | 38 % | 100 TW | 1.9 kt | D from any water | physics E, in-place burn S |
| D-He-3 (canon) | 3.52e14 J/kg | 0.74 kg/s | ~1 % (D-D side) | 2.6 TW | 1.8 kt | lunar regolith at ~10 ppb: 110 Gt processed; or 65 Mt of ice-giant atmosphere gas | physics E, reactor S, supply S at this scale |
| p-B11 | 7.0e13 J/kg | 3.75 kg/s | ~0 | ~0 | 9.2 kt | boron is common | net thermal burn U (bremsstrahlung) |

Findings: only D-He-3 and catalysed D-D give the fuel flow the mission needs. D-D is the cheapest fuel (deuterium from any water), but
it puts 100 TW into neutrons, 38 times D-He-3's; the operating point lets the drive structure absorb only 10.4 GW, so the ship could
intercept at most 1e-4 of the neutron power (D-He-3 allows ~0.4 %). That is the speculative breakthrough a D-D Wayfarer needs: a neutron
standoff or shield far beyond today's, or a catalysed burn whose neutrons leave the ship almost entirely. Helium-3's difficulty is supply,
not physics: 1.1 kt is about a century of a mature lunar or ice-giant industry at the scales usually discussed. V0 builds D-capable hardware
and leaves the choice to Phase 6.

**Reaction masses** for the mission's 972 t (same jet power and ve, so the same mass; `fuel_system.reaction_masses`):

| Mass | Volume | First-order tankage | Storage | Exhaust and hardware | Class |
| --- | --- | --- | --- | --- | --- |
| Hydrogen (V0) | 13,700 m³ | 146 t | 20 K, boil-off | Z = 1, cleanest | E |
| Water | 970 m³ | 29 t | room temperature, also shielding | oxygen (Z = 8) radiates and erodes in the mixing region | E storage, P exhaust |
| Ammonia | 1,420 m³ | 49 t | 240 K | nitrogen, Z = 7 | E storage, P exhaust |
| Methane | 2,300 m³ | 78 t | 112 K | carbon deposits on hot hardware | E storage, P exhaust |

At 0.064 c the ionisation energy is about 1e-5 of the jet energy per kilogram, so the species hardly changes the energy budget: storage
and what heavy nuclei do in the exhaust decide it. Water would cut the reaction-mass volume 14-fold and its tankage by about 117 t, and it
is already aboard as shielding and ordinary water; it is the strongest Phase 6 alternative, pending the engine's tolerance of oxygen.

**Feedstock chain** (`fuel_system.feedstock`): water ice from C-type asteroids, Ceres, the Jovian and Saturnian moons, comets or the lunar
poles is electrolysed (52 kWh/kg H2, oxygen sold or used), liquefied (about 10 kWh/kg), and its hydrogen cryogenically distilled for HD/D2.
A mission's 731 t of deuterium needs about 26 Mt of Earth-ocean-like water at 80 % recovery, or about 14 Mt of comet-like water (D/H
about twice VSMOW). The ship's 972 t of H2 is only about 9 kt of that water: the propellant is a by-product stream of the deuterium
enrichment, which sets the refinery's size. H2 for one mission costs about 60 GWh of electrolysis and liquefaction. Abundance is not cost:
the deuterium refinery's throughput, not the ice, is the bottleneck. The ship carries no refinery: it receives processed D2, He-3 and H2.

## 7. Explore Ship: the Fuel drawer

The Fuel button (key P) opens `web/viewer/fuel.js`, which loads `build.fuel_file` (`fuel_system.web`, about 20 kB) on first use only:

- **M1, installed system.** "Isolate feed train" ghosts the rest of the ship, frames the aft train and gives every FPS object and run
  tank its species colour (deuterium teal, helium-3 violet, hydrogen blue, helium purge cream: the WEB-005 functional colours). The
  exported materials come back with "Whole ship".
- **M2, flow.** Dots run along every pipe in the flow direction (tank to bay or engine, header loop, panel to ring main, bottle to line),
  coloured by what flows: helium dots on the hydrogen lines while they are purged. One instanced draw call for all 145 dots.
- **M3, operating states.** Standby, Prep, Ignition, Propellant feed, Active, Throttle (hydrogen ×0 to ×3), Shutdown and Refuel, each
  with its text and the D, He-3 and H2 flows, thrust, exhaust velocity and jet power from the shared numbers. The bookmark keeps the
  state, the throttle setting and the isolation (`#fuel=THROTTLE.2.iso`).

It is a CONCEPTUAL display. The flows are fractions of the operating point, with jet power in proportion to the fuel fraction. Dot speed
is a display value. Nothing here is a fluid simulation. Browser check (2026-11-18, software renderer SW, local export without the walk):
no console errors, the bookmark reopens, and the phone layout keeps the drawer usable.

## 9. Version 1: the chain closed to every engine

### 9.1 Connection audit (M1, 2026-11-19, repository state at 80933b0)

Status words: **connected** (geometry meets geometry), **interface only** (the parts stop at a declared empty with a gap), **missing**.

| Segment | Before V1 | Gap | V1 |
| --- | --- | --- | --- |
| Vessels → ring mains (13 outlets, valves) | connected | 0 | unchanged |
| Inner H2 ring main (`Fuel_Ring_Main_H2_I`, vessels I2, I4) → trunks | **missing**: both H2 trunks leave the outer main, so 2 of 5 H2 vessels could not reach the engines | 14.25 m (r 13.5 → 27.75) | `FPS_H2_Crossover` + valve at az 315° (clear of every vessel) |
| Ring mains → transfer trunks (exterior legs) | connected | 0 | unchanged |
| Trunk exterior leg → interior leg at the aft hull skin (6×) | interface only (`IF_FUEL_HULL_*`) | 0.30 m across the skin | `FPS_Feedthrough_*`: jacketed sleeve, bellows, flange each side, process line through |
| Interior leg → run tank (6×) | **defective**: the trunks entered the run tank through its cap and left through its barrel; no valve | inside the tank | trunks end at a tee on the tank axis 0.9 m forward of the cap; `FPS_Tank_Inlet_0n` nozzle into the cap, inlet valve, one `FPS_Check_Valve_*` per trunk |
| Run tanks → bay / header → engine collars (V0) | connected | 0 | unchanged |
| Bay fuel inlets → `CL_Trunk_TARGET_FEED` | **missing**: target fabrication has no geometry | 8 m through the bay | conceptual leg only (engine workstream owns the bay); dashed in the viewer |
| `CL_Nj_Line_TARGET_FEED` → engine target magazine | interface only: the line ends on the panel's hub face; nothing inside the engine | ~5 m | `FPS_Nj_Target_Feed` from the panel's forward face to the magazine (CANDIDATE) |
| `IF_FPS_H2_ENGINE_0n` → burn | **missing**: no injection hardware | to the burn face | `FPS_Nj_H2_Injection_Line`, control valve, `FPS_Nj_H2_Manifold`, `FPS_Nj_H2_Injectors` (8 ports, fast valves) (CANDIDATE) |
| Engine magazine → transfer → launcher → bore → burn | connected (engine-owned) | 0 | unchanged |

Findings for the engine workstream (all three resolved in V1.1, section 10.1): the cluster spaces the six panel services at 0.34 m (`CL_Nj_Line_*` end at z = (i − 2.5)·0.34) and the
engine its panel interfaces at 0.36 m (`IF_VTX_*`), so `TARGET_FEED` lands 5 cm apart (z −0.85 against −0.90; the FPS feed follows the
engine's −0.90). The service panel (r 5.6 to 6.1) reaches into the cradle torus (inner radius 5.92). `CL_Nj_Strut_Ring_Tie` runs from
the cradle's outer point (engine frame Y +6.6) to the thrust ring (Y −18.7) in the engine's Z = 0 plane, so it passes through the collar
and cartridge at X ≈ −9.3; the FPS keeps its ports out of that plane.

### 9.2 What was built (M2, M3, M4)

Fuel: farm → crossover/ring mains → trunks → feedthroughs → run-tank tees and nozzles → run tanks 01 (D2), 02 (He-3) → V0 feed lines to the
bay → (target fabrication, conceptual) → `CL_Trunk_TARGET_FEED` → `CL_Nj_Line_TARGET_FEED` → service panel → `FPS_Nj_Target_Feed`
(forward along the collar clear of the lithium manifold and cryogen header at r 5.85, radially in at X −7.6 beside the hub-side pulse
pod, forward outside the cartridge shell at r 3.7 and in through it at X −4.0) → `VTX_Target_Magazine` → the engine's own transfer,
launcher and bore. Engine-frame coordinates: X along the engine axis, Y radial outward, Z tangential.

Hydrogen: farm (both mains) → trunks → run tanks 03/04 → V0 trunks, header and branches → `IF_FPS_H2_ENGINE_0n` (X −7.9, r 5.9, az 180°)
→ `FPS_Nj_H2_Control_Valve` → `FPS_Nj_H2_Manifold` (ring X −8.1, R 5.0, forward of the collar: aft of it the cage longerons, tie rods and
cradle leave no free annulus) → eight `FPS_Nj_H2_Injectors`, one in each gap between a cage longeron (22.5° + 45°k) and the next tie rod
(11.25° + 45°k), at 42.4°, 87.4°, 129.4°, 196.9°, 222.4°, 264.4°, 309.4° and 348.75° (clear of the lithium feeders, coil leads, exchange
rails and the cluster's strut-ring tie; the service-panel sector carries none), each with a fast valve at X −8.3, through drilled galleries in the thrust collar, across the gap and into the shadow shield
at r 5.0, radially in to r 4.3 at X −12.5, then axially to the burn face at X −12.86 (the tips, `IF_FPS_H2_INJECT_Nj`).

Pipe classes (`[fuel_system.v1] pipe`, `fuel_system.pipe_spec`; bore at the class velocity, wall by Barlow at 4× the design pressure,
316L at 140 MPa, weld efficiency 0.85, +1 mm; the drawn radius is the vacuum jacket or insulation):

| Class | Fluid | Flow per line | Bore mm | Wall mm | OD mm | Material | Joints |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LH2-TRUNK | H2 liquid, 20 K, 0.6 MPa | 192 g/s | 42 | 1.4 | 44 | 316LN inner, 304L vacuum jacket, MLI 30 layers | orbital butt welds; bayonets at equipment |
| LD2-TRUNK | D2 liquid, 20 K, 0.6 MPa | 296 g/s | 33 | 1.3 | 35 | as LH2 | as LH2 |
| LHE3-TRUNK | He-3 liquid, 3 K, 0.3 MPa | 444 g/s | 69 | 1.3 | 72 | 316LN, 20 K intercept shield, vacuum jacket | welds; all-metal seals (He-3 is scarce) |
| GH2-INJECT | H2 gas, 300 K, 2.0 MPa | 96 g/s | 50 | 2.7 | 56 | 316L line, Inconel 718 valve bodies, foil insulation near the shield | welded; flanged at valves |
| TARGET-FEED | filled targets in cold He carrier, 20 K | 185 g/s of fuel | 25 (capsule) | 1.1 | 27 | 316L guide tube, vacuum jacket | flanged at the panel and the magazine |

Flanges are drawn at every V1 line end and bend (`FPS_*_Flanges`): an engine removal breaks the target feed at the panel and the H2 line at
its inlet. Each engine's target feed and H2 line carry a P/T/flow sleeve (`FPS_Nj_Instruments`). Cold-line supports beyond V0's corridor
clamps, the collar galleries' detail and the fast valves' life at 5.7 kHz are OPEN.

### 9.3 How the hydrogen gets its energy (SPECULATIVE, not validated)

Before each pulse the fast valves puff hydrogen gas from the eight tips into the region ahead of the burn face. The pulse's X-rays ionise
it within nanoseconds; the expanding charged debris shell (D–³He products at MeV energies) sweeps it up and shares momentum with it by
collisions and the compressed field (a snowplow). The heated mix is then turned into the exhaust by the loops L1 to L4 like the debris
itself. This sets the propellant's place: downstream of the burn, never in the target. What is not established: the coupling efficiency,
the mixing length against the 0.18 ms pulse period, ablation of the tips and the burn face, and whether a puff survives the field. The
operating point's 80 % jet share assumes the coupling works.

### 9.4 Energy and fuel rate (M6)

`fuel_system.energy_ledger` puts the engine workstream's burn model (`vertex_radiation.sources`) beside B01; nothing is tuned to agree:

| Burn model case | Photons | Neutrons | Charged debris | Against the 80 % canon jet share |
| --- | --- | --- | --- | --- |
| LOW (hot-ion lower bound) | 12.5 % | 4.4 % | 83.1 % | closes, 3.1 % left for coupling losses and intercepted heat |
| NOMINAL | 21.7 % | 4.8 % | 73.5 % | **does not close**: 6.5 % short |
| CONSERVATIVE | 84.8 % | 2.9 % | 12.4 % | does not close |

At 261 TW the NOMINAL photons are 57 TW and the neutrons 12.5 TW. The canon's absorbed fraction (4×10⁻⁵, about 10 GW) is what the shield
and armour must reject; the rest leaves the open geometry. The injection hardware sits in the shield's shadow and adds no line of sight.

Fuel rate: one engine's own pulse point is 6.63 mg at 5,697 Hz, 37.8 g/s, 8.9 TW of fusion. Four engines make 35.7 TW, **1/7.3** of the
ship operating point's 261 TW, which needs 185 g/s of fuel per engine. The "38 vs 185 g/s" gap is therefore the same factor in power, not
a feed shortfall. The FPS feeds the operating point and changes neither side; the engine workstream owns pulse rate and target mass.
V1.1 (section 10.3) reconciles the 4.9× and the 7.3× and stops claiming the 80 % jet share.

### 9.5 Interface contract with the engine workstream

The FPS-side parts inside an engine are CANDIDATES (`owner_workstream = ENGINE (candidate)`): built by `components/fuel_feed.py` in
`WF_STORAGE` from the engine's own placement (`vertex_cluster.placements`, `to_ship`) and stations (`vertex_engine.stations`), so they follow
the engine if it moves. No engine or cluster file is edited.

| Interface | FPS delivers | Engine provides | State |
| --- | --- | --- | --- |
| `IF_FPS_FUEL_BAY_D2` / `HE3` | metered D2 (~20 K) and He-3 (~3 K), 296 and 444 g/s peak, blend set at the target fill (D–³He 1:1) | target fabrication in the bay, fill to the `TARGET_FEED` trunk | OPEN (no geometry) |
| `TARGET_FEED` panel slot → `IF_FPS_TARGET_Nj` | target feed tube from the panel to the magazine, flanged both ends | panel slot, magazine inlet, carrier gas and rate | CANDIDATE |
| `IF_FPS_H2_ENGINE_0n` | conditioned H2 gas, 300 K, 2 MPa, 96 g/s per engine | — | built |
| `IF_FPS_H2_INJECT_Nj` | control valve, manifold, 8 fast-valved ports to the burn face | galleries in the collar and shield, timing to the pulse | CANDIDATE |
| Energy transfer | H2 placed downstream of the burn | coupling of the debris into the H2 (SPECULATIVE) | OPEN |
| Cooling | the H2 line is warm gas; the target feed is jacketed and cold | the shield and armour reject the absorbed heat | engine |
| Power and control | fast-valve drive (~kW class per engine, PROTOTYPE), sensors to the drive controller | pulse timing signal | OPEN |
| Mounting and service | lines clamp to the collar; the engine removal breaks at the panel and the H2 inlet flanges | removal axis aft (`IF_VTX_ENGINE_0n_REMOVAL`) | PLAUSIBLE |

### 9.6 Model inventory, V1 status (superseded by section 5)

Statuses: existing and connected; existing but not connected; missing and required; conceptual placeholder; integrated and geometrically
validated (built, clash-screened by `lab/studies/fuel-propellant/probe.py`, whole-ship inspection PASS); assumptions unresolved.

| ID | Component | Status | Model |
| --- | --- | --- | --- |
| FPS-XO-H2 | H2 inner-outer crossover + valve | integrated and geometrically validated | `FPS_H2_Crossover*` |
| FPS-FT-* | hull feedthroughs (6) | integrated and geometrically validated | `FPS_Feedthrough_*` |
| FPS-TI-01..04, FPS-VL-CK-* | run-tank nozzles, inlet valves, check valves | integrated and geometrically validated | `FPS_Tank_Inlet_*`, `FPS_Check_Valve_*` |
| FPS-TF | target fabrication in the bay | conceptual placeholder (V1.1: modeled, section 10.2) | dashed viewer leg |
| FPS-TF-N1..N4 | target feeds, panel → magazine | integrated and geometrically validated; assumptions unresolved (carrier, rate) | `FPS_Nj_Target_Feed` |
| FPS-IJ-N1..N4 | H2 control valve, line, manifold, 8 ports with fast valves | integrated and geometrically validated; assumptions unresolved (coupling, valve life) | `FPS_Nj_H2_*` |
| FPS-FL, FPS-IN | flanges, instrument sleeves | integrated | `FPS_*_Flanges`, `FPS_Nj_Instruments` |
| FPS-PMD, cold-line supports past the corridor, collar galleries | — | missing and required (V1.1: modeled, section 10.2) | — |

Physical integration (geometry joins geometry) is separate from conceptual interfaces: the bay leg and the energy coupling are conceptual;
every other V1 segment is modeled.

### 9.7 Explore Ship (M5)

The Fuel drawer adds views: **Whole propulsion** (farm to burn faces), **Fuel flow** (D, He-3 and target lines with their vessels),
**Propellant flow** (hydrogen and its helium purge) and **Combined** (everything, the energy readout, and the drive set to match the
state: Prep → pre-ignition, Ignition → ignition pulse, Active/Feed/Throttle → sustained, Shutdown, Standby/Refuel → off). Each view
ghosts the rest of the ship, tints its objects by species and frames them. Dots run only on modeled pipes (farm outlets, ring mains as
loops, trunks, feedthroughs, inlets, the aft train, the cluster's target-feed lines, each engine's feed, line and ports); the bay leg is
dashed. Amber markers show where a flow ends unresolved (bay inlets, magazines, injector tips, the refuelling receptacle), listed with
their notes. A component list frames and selects any object in the view. Bookmark: `#fuel=ACTIVE.combined`.

## 10. Version 1.1: geometry conflicts resolved, missing components modeled

Owner brief 2026-11-19 09:23Z. V1 (dd4a64c) is the accepted baseline; V1.1 changes the engine and cluster interface the three V1 findings
named, models every V1 "missing" component as an engineering blockout and reconciles the fuel and power numbers. The engine workstream
agreed that this work owns `vertex_engine.py`, `vertex_cluster.py`, `components/vertex.py`, `[vertex_engine.geometry]` and
`[propulsion_cluster]` while the V1.1 review is open. Positions and sizes are PROTOTYPE; the target process is SPECULATIVE.

### 10.1 The three conflicts

| Conflict (V1 finding) | Resolution | Shared source |
| --- | --- | --- |
| Service spacing: cluster lines at 0.34 m, engine interfaces at 0.36 m | one pitch, 0.36 m, for the engine panel part, its six `IF_VTX_*` slots, the cluster's six `CL_Nj_Line_*` and the FPS target feed; `service_line_spacing_m` deleted | `vertex_engine.geometry.service_slot_pitch_m`, `vertex_engine.service_panel()` (panel station, faces, width and slot z of every service) |
| `CL_Nj_Strut_Ring_Tie` from the cradle's outboard point through the engine to the hub | replaced by a symmetric pair of **flank thrust ties** `CL_Nj_Flank_Tie_A/B` from the cradle flanks (local 90° and 270°, between the trunnions) to the nearest thrust-ring node that clears the comms sweeps: the cradle now meets the ring at four points (two hub-side struts, two flank ties), all outside the engine. The FE group is `flank_tie` (same r 0.54 m) | `vertex_cluster.frame` |
| Service panel inside the cradle tube (panel r 5.6–6.1 at the cradle station, cradle bore 5.92) | the panel moves **axially forward** of the cradle onto the collar's forward face (X −9.2 to −8.3, r 5.55–5.80, 2.3 m wide); the cluster lines approach it radially at its station and end on its hub face; the lithium panel lines shorten to the panel's inner face; the power bus leaves its forward face | `service_panel_length_m`, `_depth_m`, `_width_m` |

Engine removal (`vertex_cluster.removal_sweep`, with the FPS engine parts in `fuel_system.removal_check`): the engine leaves aft along its
axis through the cradle once the four trunnion pins withdraw and the panel lines and the two FPS flanges are released, so every part
forward of the cradle's aft face must pass the cradle bore. V1 failed this regardless of the panel: the trunnion lugs reached r 6.3
inside the bore. V1.1 shortens the lugs to 0.30 m proud of the collar (the cluster pins enter their sockets), keeps every forward part
inside a removal passage of r 5.92 m (`removal_passage_radius_m`: the panel's corners, the FPS H2 inlet line at r 5.80, whose standoff
drops from 0.30 to 0.20 m, and the target feed), and widens the cradle ring from R 6.6 to 6.8 m so its bore is 6.12 m: **0.20 m radial
clearance**, least at the trunnion lugs and the panel corners. No part is blocked. The engines did not move.

### 10.2 Components added

| ID | Component | Model | Status |
| --- | --- | --- | --- |
| FPS-FAB-* | target fabrication in the cluster bay core: D2 and He-3 legs from the bay fore face to their **receiver dewars**, a purifier and **blend unit**, the **shell fill and cryogenic layering station**, **inspection** with a reject chute, a **buffer magazine**, the target conveyor | `FPS_Bay_Target_Fabrication_D2/He3`, `FPS_Fab_Receiver_*`, `FPS_Fab_Blend_Unit`, `FPS_Fab_Fill_Station`, `FPS_Fab_Inspection`, `FPS_Fab_Buffer_Magazine`, `FPS_Fab_Links` | blockout; process SPECULATIVE (`IF_FPS_FAB_FILL`) |
| FPS-FAB-XFER | cold-target transfer from the buffer magazine to `CL_Trunk_TARGET_FEED` on the bay's aft face | `FPS_Target_Transfer_Bay` | modeled |
| (cluster) | the power and conditioning bay is an annulus (r 1.9–4.2) round the fabrication core; the five service trunks leave the annulus at r 2.3 and step in to r 1.0; three **trunk spider rings** tie the six trunks between the bay and the hub | `CL_Power_Conditioning_Bay`, `CL_Trunk_*`, `CL_Trunk_Spider_1..3` | PROTOTYPE |
| FPS-IJ-Nj-P | **shielding galleries**: a sleeve round each injector port where it crosses the thrust collar and the shadow shield (with the V1 dog-leg, no straight streaming path) | in `FPS_Nj_H2_Injectors` | blockout |
| FPS-SS-Nj | **cryogenic supports**: two clamps per engine (ring + low-conductance standoff) holding the target feed's inner run to the cartridge shell; **thermal intercepts** on the target feed and the H2 line at the panel side | `FPS_Nj_Supports` | PLAUSIBLE |
| FPS-TI-V11 | **thermal intercepts** (cold-strap collars) where the four feed lines cross the shadow-shield sleeve, at each hull feedthrough's interior end and on the D2/He-3 bay legs | `FPS_Thermal_Intercepts` | PLAUSIBLE |
| FPS-PMD-* | **propellant management devices** for coast transfer: four gallery vanes along the barrel and an eight-plate sponge at the aft outlet, in the 4 run tanks and the 13 farm vessels | `FPS_PMD_Run_Tanks`, `FPS_PMD_Farm` | ESTABLISHED principle, sizing OPEN |
| FPS-EQ-* | **pump, regulator and conditioning detail**: the boost pumps' motors, the conditioners' heat-exchanger shells, a pressure regulator and a flow-meter spool on each feed line | `FPS_Equipment_Detail_*` | PLAUSIBLE |

Objects are merged per function (the play download budget): V1.1 adds 21 exported FPS nodes. The feed lines' V0 supports, sensors, relief
and purge are unchanged.

### 10.3 Fuel rate and power: one gap, not two

`fuel_system.rate_reconciliation` puts the ship operating point (`flows`) and the engine's pulse point (`vertex_magnet.plasma`) in one
energy and mass account:

| Quantity | Ship (per engine) | Engine point | Ratio |
| --- | --- | --- | --- |
| Fusion power | 65.3 TW | 8.93 TW (1.567 GJ × 5,697 Hz) | **7.31** |
| Jet power, share of fusion | 52.3 TW, 0.800 (B01) | 6.97 TW, 0.780 | 7.50 |
| Exhaust mass | 283 g/s | 37.8 g/s (6.63 mg per pulse) | 7.50 |
| Reacted D+He-3 | 185 g/s | 25.3 g/s (4.44 mg per pulse at 3.53×10¹⁴ J/kg) | 7.31 |
| Exhaust per reacted fuel | 1.53 | 1.49 | — |

The ship's flows are **reacted** fuel (fed = reacted / burnup 0.8: 0.925 kg/s); the engine's 6.63 mg pulse mass is not a fuel mass but the
mass that carries the pulse's jet energy at the exhaust speed (m = 2E/vₑ²). V1 set the ship's reacted D+He-3 against the engine's exhaust
mass: 7.50 / 1.53 = **4.9**. Like for like, the specific fusion energy is the same (full D–³He burn of what reacts, 3.53×10¹⁴ J/kg),
burnup cancels, and target mass and pulse rate enter only through yield × rate: the one mismatch is the engine's fusion power, ×7.31.
It would close at 41.7 kHz at today's yield, 11.5 GJ at today's rate, or 29 engines; none is changed here (engine workstream).

Jet share: the **current result is NOMINAL, 73.5 %** of the fusion power in charged debris, the ceiling of any directed jet before
conversion losses. The 80 % B01 share (and the engine model's 78 %) is not claimed, because no conversion mechanism above the charged share
is shown. At NOMINAL the jet the ship needs (209 TW) takes 284 TW of fusion, not 261 TW. The viewer shows this.

### 10.4 Validation

- Mesh screen, whole rear cluster (`lab/studies/fuel-propellant/probe.py --cluster`): every FPS and CL object against all other geometry, 185
  objects, no unexpected contact. Designed contacts are listed in the script: cluster lines on the panels, pins in the lugs, struts and
  ties on the thrust ring, the transfer leg on the trunk, the target feed through the panel and the cartridge, the ports through collar
  and shield. No cluster member touches an engine part other than its panel and lugs.
- Pipe ends (`lab/studies/fuel-propellant/endpoints.py`, pure): 288 line ends; every one lands on a line, equipment, tank, the bay, a panel or a
  declared interface; the only open ends are the documented ones (injector tips `IF_FPS_H2_INJECT_Nj`, magazines `IF_FPS_TARGET_Nj`,
  vents, hull feedthroughs, the refuelling receptacle).
- Removal sweep: no blocked part, least clearance 0.20 m (section 10.1).

### 10.5 Explore Ship

Two views join the Fuel drawer: **Target fabrication** (the cluster bay core, its legs and transfer; dots on every modeled line) and
**Propulsion assembly** (the aft feed train, the cluster frame and service lines, the four engines with their FPS parts; the state
buttons drive the engines, whose materials and animations are kept). Views now select by chain group as well as species. The combined
and assembly readouts show the NOMINAL charged share as the current result, the B01 share as not claimed, and the one-gap reconciliation.
Bookmarks: `#fuel=ACTIVE.fab`, `#fuel=ACTIVE.assembly`.

## 11. V1.1 release readiness

Owner brief 2026-11-19 12:05Z: V1.1 (b274e55) is the provisional mechanical and modeling baseline; the engine positions, the shared
service pitch, the symmetric flank ties and the removal geometry stay. Study code and results: `lab/studies/fuel-propellant/readiness.py`
(mass, mission, loads; `results/readiness_v1.json` at dd4a64c and `results/readiness_v11.json`), `lab/studies/fuel-propellant/extraction.py` (the extraction
path in the saved vehicle, `results/extraction.json`). Mission targets (0.016 c, the burn delta-v, the drive's power cap, the owner's case E) are
held in every number below; only consequences move.

### 11.1 Mass, centre of mass, acceleration and mission

The ship's canonical mass account (`physics.mass_budget`, the B02 placement in `mass_model.py`, `operating_point.py`) carries the drive
as the 250 t `drive_package` allowance and reads no Vertex file. V1.1 therefore changes **no canonical number**: departure 4,426 t,
2,797 t propellant, 0.50 to 0.64 g, 9.99 days per burn, dry centre of mass X +35.1 m, departure X +89.6 m (identical at V1 and V1.1).

The drawn cluster is an ENGINEERING_PROTOTYPE estimate (`vertex_structure.mass_rollup`): frame 1,353 t (V1) → **1,436 t (V1.1, +83 t:
the wider cradle rings, the eight flank ties, the trunk spider)**; each engine 1,243.7 → 1,241.7 t (the shorter lugs); the cluster
6,328 → **6,403 t (+75 t net)**. Placed on the ship (a spec copy, never written back), the same calculations give:

| Case | Dry added | Propellant | Departure | Accel (start–burnout) | Days per burn | Dry CG X | Departure CG X | Vessel fill (He-3 / D2 / H2) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Canon (V1 and V1.1) | — | 2,797 t | 4,426 t | 0.50–0.64 g | 9.99 | +35.1 m | +89.6 m | 0.92 / 0.85 / 0.91 |
| V1.1 frame delta alone (+82.7 t at the frame centroid X −142.6 m) | +83 t | **2,988 t (+6.8 %)** | **4,729 t** | **0.47–0.60 g** | **10.67** | **+28.2 m** | +87.9 m | 0.98 / 0.91 / 0.98 |
| Whole drawn cluster in place of the 250 t allowance (context) | +6,153 t | 17,017 t | 26,932 t | 0.08–0.11 g | 60.8 | −56.7 m | — | 5.6 / 5.2 / 5.6 (does not fit) |

- The +83 t alone costs **+191 t of propellant** for the same delta-v (the full-return mass ratio applies to every dry tonne), +29 t of
  tankage, +0.68 days per burn and 0.03–0.04 g of acceleration. It still fits the existing vessels, with little left: He-3 at 98.4 % and
  H2 at 97.6 % of liquid capacity (ullage is not budgeted). Lateral CG at departure 37 mm (canon 7 mm, the trimmed loading has less
  freedom at that fill): 1.4 % differential thrust against the 5 % limit.
- The whole drawn cluster is 25.6 times the drive allowance and does not fit the ship's mission (5.6 times the He-3 capacity); this is
  the known Vertex mass gap (lab Vertex 2.x ledgers), not a V1.1 effect. V1.1 adds 1.2 % to it.
- Not adopted: the drive allowance, the mission targets and the vessel sizes are unchanged. A canon decision is needed before any of the
  drawn Vertex mass enters `mass_budget` (owner, with the engine workstream).

### 11.2 Structure and the flank-tie load paths

Frame FE (`vertex_structure.cluster_members`, Ti-6Al-4V, unchanged method), governing utilisation per load set, V1 → V1.1:

| Load set | V1 (ring ties) | V1.1 (flank ties) | V1.1 governing member |
| --- | --- | --- | --- |
| LC01 engine thrust (C-10, 0.73 MN each) | 0.028 | 0.042 | `CL_N3_Flank_Tie_A` |
| LC03 NOMINAL field + thrust | **0.815** | **0.412** | `CL_N3_Thrust_Strut_10` |
| LC03 CONSERVATIVE field + thrust | 3.306 | 1.657 (fails) | `CL_N3_Spoke_B`; flank ties 1.382 |
| LC06 N2 coils off | 0.990 | 0.524 | `CL_N3_Spoke_B` |
| LC06 single engine N1 | 0.017 | 0.026 | `CL_N1_Flank_Tie_B` |
| Ship operating-point thrust, 5.44 MN per engine (new set) | — | 0.313 | `CL_N4_Flank_Tie_B` |
| + engine inertia at 0.11 g / 0.64 g | — | 0.239 / 0.023 | flank ties |
| + engine inertia + NOMINAL field | — | 0.396 / 0.438 | thrust strut / spoke |

Engine-mount stiffness: axial 153 → 294 MN/m, tangential 154 → 265 MN/m, radial 3,330 → 3,222 MN/m; lowest rocking mode 1.77 → 2.45 Hz
(the 5.7 kHz pulse rate stays far above every frame mode); magnetic stiffness margin 1,597 → 1,545.

Attachment points: each tie runs from the cradle flank (engine-local 90° or 270°, between two trunnions) to a thrust-ring node, landing on
the node's strut foot 0.34 m from the node centre like every thrust strut (the FE treats both as on the node). N1 and N2 take ring nodes
2/1 and 5/4 with mirror-equal ties (21.75 m, 67.7° to the axis). N3 and N4 mirror each other, but on each, one tie (`N3_A`, `N4_B`) goes
to the farther node 1 or 5 (24.51 m) because the nearer node fails the comms keep-out; nodes 1 and 5 therefore carry two ties. In thrust
the ties are compressed (0.52–0.78 MN at LC01) and carry most of the axial load: the cradles now reach the ring outside the engines at
four points each. Thrust load path: engine collar → trunnion pins → cradle → (two hub-side thrust struts, two flank ties) → thrust-ring
nodes → ring → ship. The largest ring-node reaction rises from 1.12 to 1.46 MN at LC01.

Findings, not hidden: (1) the 1.2 load sets carry the engine's own 0.73 MN thrust; the ship operating point needs 5.44 MN per engine
(the same 7.5× as the jet-power gap). With it the frame stays under 0.44 at NOMINAL. (2) CONSERVATIVE currents still fail the frame
(1.66; V1 3.31): pre-existing, halved by the ties. (3) The thrust-ring node joints and the ring itself are not in the FE (fixed nodes):
their capacity at 1.46 MN per node and the double-tie nodes 1 and 5 are OPEN.

### 11.3 Engine removal: the whole extraction path

`extraction.py` moves engine N1 and everything it carries (the VTX instance on its placement and every `FPS_N1_*` object) aft along its
axis by any distance and checks every other evaluated vertex and edge midpoint in the saved vehicle (7,447 static objects: cluster
frame and lines, the other engines, the FPS lines, the thrust ring, the hull) against the largest moving radius at stations forward of
it, per 3° azimuth sector. The pure `fuel_system.removal_check` now also includes the clamps and cold-strap collars the engine carries.

Result (V1.1 with the release-readiness fix):

| Check | Result |
| --- | --- |
| Pure sweep through the cradle bore (`removal_check`, analytical radii) | no part blocked; least clearance **0.203 m** (the four trunnion lugs), panel 0.207 m, power bus 0.239 m, H2 line 0.26 m |
| Mesh sweep, whole path, everything not removed first (`extraction.py`) | least clearance **0.194 m**: the cradle ring's inner face against the service panel; the cradle is drawn as a 48-segment polygon whose chord midpoints sit 13 mm inside the true 6.12 m bore. Next: cluster service lines 1.56 m, every other object more than 1.9 m |
| Found and fixed at release readiness | the two cold-strap collars V1.1 added at the panel and the H2 inlet (`FPS_Nj_Supports`) stood 23 mm proud of the passage (0.177 m on the mesh, outside r 5.92 in the pure sweep, which did not yet include them). Both moved 0.3 m onto the radial-in legs of their lines; the pure sweep now includes clamps and collars |
| Removed first: trunnion pins | they reach 0.217 m inside the swept envelope (they sit in the lugs): each pin must withdraw radially at least **0.42 m** (0.217 + 0.20) before the stroke |
| Removed first: line stubs at the panel and the H2 inlet | the six `CL_N1_Line_*` stubs end on the panel (0.06–0.10 m inside the envelope) and `FPS_H2_Branch_N1` on the inlet (0.175 m inside): each needs a **removable spool** of at least 0.30 m (cluster lines) and 0.38 m (H2 branch) between its last flange and the panel or inlet, so the stub ends clear by 0.20 m once the spool is out. The flanges exist (`FPS_*_Flanges`); the spools are a procedure and joint definition, not new geometry |

Procedure the geometry supports: shut down and warm to structure temperature; disconnect and remove the six panel spools and the H2 inlet
spool (purge first); withdraw the four trunnion pins by 0.42 m or more; translate the engine aft along its axis on a guidance fixture
until it is clear of the cradle and the neighbouring engines' nozzles (no static object lies within 1.9 m of the path after the cradle).

Thermal expansion and tolerances: removal is a cold, shut-down operation (no hot-circuit growth); the coils' cold-mass contraction is
inside their cryostats and does not move the outer envelope. The collar and cradle are both titanium (8.6×10⁻⁶ /K): a 100 K difference
between engine and frame moves the 5.92 m envelope 5 mm against the 6.12 m bore. Clearance stack (PROTOTYPE allowances, not sourced):

| Item | Allowance |
| --- | --- |
| Engine/frame temperature difference, 100 K | 5 mm |
| Cradle ring position and roundness | 15 mm |
| Panel, lug and FPS part fabrication | 10 mm |
| Guidance during the stroke (rails or fixture, 0.5 mrad over 20 m) | 10 mm |
| **Total** | **40 mm of the 203 mm (true geometry); about 160 mm left** |

The drawn mesh's 13 mm tessellation loss (0.194 m) belongs to the proxy, not to the hardware, and is not counted against the stack.

The guidance fixture and its rails are not modeled (OPEN, TODO F06).

### 11.4 Browser performance

Measured with the established checks (`workflow.py web`, which enforces the `web_export.py` budgets) on clean exports of V1 (dd4a64c,
rebuilt in a worktree) and V1.1 (577bff8), and `lab/studies/fuel-propellant/perf.js` (`results/perf_v1.json`, `results/perf_v11.json`) in the same headless
Chromium. Evidence class **SW** (SwiftShader, 1400×900, no GPU): frame times are relative only, never device performance.

| Measure | V1 | V1.1 | Change | Budget |
| --- | --- | --- | --- | --- |
| Explore Ship download (before compression) | 11.594 MB | 11.699 MB | +105 kB (+0.9 %) | 12 MB: 97.5 % used, PASS |
| Ship GLB (Draco) | 9.887 MB | 9.990 MB | +103 kB | — |
| Ship GLB gzipped (if the host compresses it) | 5.81 MB | 5.90 MB | +87 kB | — |
| Engine part inspection (on demand) | 453.9 kB | 453.8 kB | 0 | 600 kB, PASS |
| Enter Wayfarer / Explore Exterior package | 66.28 MB | 66.55 MB | +273 kB (+0.4 %) | 90 MB: 74 % used, PASS |
| Viewer GLB nodes / meshes | 5,383 / 3,844 | 5,404 / 3,865 | +21 / +21 | — |
| Viewer triangles (file) | 1.175 M | 1.192 M | +17.2 k (+1.5 %) | — |
| Draw calls, whole ship / Fuel whole / assembly | 5,353 / 5,317 / — | 5,374 / 5,336 / 5,385 | +21 | — |
| Rendered triangles, whole ship | 1.433 M | 1.450 M | +1.2 % | — |
| Ready (model shown), SW | 5.95–6.03 s | 5.87–6.27 s | within run spread | — |
| Frame time median, whole ship, SW | 2.97–3.18 s | 3.03–3.17 s | within run spread | — |
| Frame time median, Fuel whole view, SW | 1.45 s | 1.48–1.60 s | +2 to +10 % (spread) | — |

No optimization was needed: the 21 FPS nodes cost 0.9 % of the viewer download and 21 draw calls (0.4 %); the viewer stays inside its
budget. The viewer was already at 96.6 % of its budget at V1; the next addition should come with the GFX-7 download work (Draco settings,
selective loading) rather than a budget increase (TODO W). The play package's native EVA check fails locally on the known
"resources still in use at exit" error after all 44 checks pass (pre-existing on main); the export here used `--no-native-check`. The first export stopped on a real release blocker: the ignition-failures study result was stale
after V1.1 regenerated the engine radiation evidence, which would have failed the site build after a squash; `lab/studies/ignition-failures/model.py`
was rerun (melt time 29.51 → 29.47 ms, the engine 2 t lighter; nothing else moves).

### 11.5 Open items kept visible

- **Fusion power ×7.31.** The engine point (1.567 GJ × 5,697 Hz × 4) gives 1/7.31 of the 261 TW the ship operating point needs
  (section 10.3). Unresolved; owned by the engine workstream. Nothing in the FPS hides it: lines are sized for the ship's flows.
- **Hydrogen energy coupling, SPECULATIVE.** The H2 is placed downstream of the burn and assumed to take momentum from the charged debris
  (section 9.3). No coupling efficiency, mixing length or tip life is established; the NOMINAL 73.5 % charged share is the current
  result and the 80 % B01 jet share is not claimed.
- The drawn Vertex mass outside the ship's mass budget (11.1); the CONSERVATIVE frame case and the thrust-ring node joints (11.2); the
  removal guidance fixture (11.3).

## 8. Next priorities

V1 status and the remaining work are in section 9. Still open from V0:

Phase 5: choose the hardware for pumps, heaters and valves; design the jackets and thermal intercepts; solve coast transfer; set the
vent plume keep-outs; plan the refuelling approach. Phase 6: re-run the trades with the engine's target and injection answers, and
study water as reaction mass and D-D with a neutron standoff. Engine side (OPEN interfaces): the target fabrication rate, the H2
injection point and its energy coupling.
