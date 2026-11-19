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

## 5. Model inventory

Status: planned, blockout, detailed, integrated, validated. Confidence: ESTABLISHED (existing engineering), PLAUSIBLE (extrapolation),
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
| FPS-TF | target fabrication / fill | Fuel conditioning (engine side) | make D or D-3He targets | `IF_FPS_FUEL_BAY_*` → magazine | cluster bay | SPECULATIVE rate | 1 | conceptual placeholder (V1: dashed leg in the viewer, no geometry) | — |
| FPS-INJ | H2 injection train | Propulsion interface (engine side) | put H2 into the exhaust | `IF_FPS_H2_ENGINE_0n` → burn face | engine | SPECULATIVE | 1 | V1 candidate, section 9 | `FPS_N*_H2_*` |
| FPS-PMD | propellant management devices | Propellant storage | coast transfer without settling | in vessels | farm, run tanks | PLAUSIBLE | 3 | planned | — |
| FPS-MLI | MLI and cooled shields | Insulation | 0.3 / 0.15 / 0.01 W/m² | | in the 0.30 m wall stack | ESTABLISHED | 3 | in wall stack, not drawn | — |

Outstanding engineering questions: coast transfer (PMDs, pressurant), pump and heater hardware, line jacket and thermal intercepts, vent
set points and plume keep-outs, refuelling approach corridor and umbilical loads, the target fabrication rate, the H2 injection point.

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

Findings for the engine workstream: the cluster spaces the six panel services at 0.34 m (`CL_Nj_Line_*` end at z = (i − 2.5)·0.34) and the
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

### 9.6 Model inventory, V1 status

Statuses: existing and connected; existing but not connected; missing and required; conceptual placeholder; integrated and geometrically
validated (built, clash-screened by `work/fuel-propellant/probe.py`, whole-ship inspection PASS); assumptions unresolved.

| ID | Component | Status | Model |
| --- | --- | --- | --- |
| FPS-XO-H2 | H2 inner-outer crossover + valve | integrated and geometrically validated | `FPS_H2_Crossover*` |
| FPS-FT-* | hull feedthroughs (6) | integrated and geometrically validated | `FPS_Feedthrough_*` |
| FPS-TI-01..04, FPS-VL-CK-* | run-tank nozzles, inlet valves, check valves | integrated and geometrically validated | `FPS_Tank_Inlet_*`, `FPS_Check_Valve_*` |
| FPS-TF | target fabrication in the bay | conceptual placeholder | dashed viewer leg |
| FPS-TF-N1..N4 | target feeds, panel → magazine | integrated and geometrically validated; assumptions unresolved (carrier, rate) | `FPS_Nj_Target_Feed` |
| FPS-IJ-N1..N4 | H2 control valve, line, manifold, 8 ports with fast valves | integrated and geometrically validated; assumptions unresolved (coupling, valve life) | `FPS_Nj_H2_*` |
| FPS-FL, FPS-IN | flanges, instrument sleeves | integrated | `FPS_*_Flanges`, `FPS_Nj_Instruments` |
| FPS-PMD, cold-line supports past the corridor, collar galleries | — | missing and required | — |

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

## 8. Next priorities

V1 status and the remaining work are in section 9. Still open from V0:

Phase 5: choose the hardware for pumps, heaters and valves; design the jackets and thermal intercepts; solve coast transfer; set the
vent plume keep-outs; plan the refuelling approach. Phase 6: re-run the trades with the engine's target and injection answers, and
study water as reaction mass and D-D with a neutron standoff. Engine side (OPEN interfaces): the target fabrication rate, the H2
injection point and its energy coupling.
