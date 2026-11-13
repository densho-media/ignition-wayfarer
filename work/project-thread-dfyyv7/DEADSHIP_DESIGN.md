# Deadship in Wayfarer: research, design and Phase 0 report (DS-000, DS-P0)

DS-000 (2026-11-12, commit 6603e08) was research and design only. On 2026-11-13 the owner approved its direction with refinements
and authorized **Phase 0 only**. This revision folds those decisions in, refines the scenario designs and the CO₂ assumptions, and
reports the Phase 0 implementation, its validation and the regression runs. Phase 1 and later stay **design only** and need separate
authorization. Nothing here changes canon, the Blender model, generated geometry, engineering values or the deployment, and no Drive
workbook was written.

Every significant statement carries one of these labels:

| Label | Meaning |
| --- | --- |
| **[EXISTS]** | Implemented in the repository before this work (file path given) |
| **[BUILT P0]** | Implemented by Phase 0 on this branch (file path given) |
| **[LORE]** | Established IGNITION canon, with its Drive owner row |
| **[ENG]** | Engineering assumption: physics or engineering judgment, not an owner row |
| **[PROPOSAL]** | Gameplay or architecture design, not implemented |
| **[OPEN]** | Unresolved: needs the owner, a Drive owner row or a later decision |

Complexity: **S** about 1–3 working days of one agent session, **M** about a week, **L** several weeks. Rough, for ordering only.

---

## 0. Summary

**Direction (owner-approved 2026-11-13).** One spacecraft engineering model, several consumers: engineering tools, Deadship and later
the story. Deadship is a gameplay consumer of reusable engineering systems, never a separate fictional simulation.
- Concept **B** first: Deadship training on the real Wayfarer, inside Explore Interior.
- Concept **D** as the long-term progression (training → competitive Deadship → narrative survival).
- Concept **C** later, on the same engineering systems, following the Tale's sequence.
- Concept **A** (a separate training spacecraft) is not built for the MVP.

**Phase 0 (built on this branch, section 10).** The smallest engineering integration that works:
- `src/wayfarer/cabin_air.py`: ring A's cabin CO₂ as one reusable engineering state, from canon pressure, control band and the 41 STUDY
  CO₂ rate, with every PROTOTYPE value labelled. It has an exact deterministic step, a conserved ledger, three unit states and reference
  checkpoints.
- `godot/scripts/systems/cabin_air.gd`: the runtime copy. It must reproduce the checkpoints within a stated tolerance before anything
  is shown.
- `godot/scripts/excursion/equipment.gd`: Ops at the real ring A sector 3 ECLSS bay isolates or restores the CO₂-removal unit, and the
  bay's status board shows the model's readout. Only the opt-in start `#interior-systems` (`-- --systems`) creates it, so the default
  Explore Interior start is unchanged.
- `godot/scripts/excursion/check_systems.gd`: a headless check through the player's own requests.

**What the refinement changed in the design.**
- The CO₂ clock is not a survival deadline. Three tiers (operational control limit, degraded habitability, physiological danger) are
  kept apart (section 7.2).
- DS-000's 120 m³ was the canon *usable-space allocation*, not the connected gas volume. With ring A's corridors (CIRC-001) and doors
  open, the free gas volume is about **466 m³**, so with six people and the unit off, CO₂ rises from the 0.3 % target to the 0.5 %
  control limit in about **5.4 h**, not 1.4 h. With sector 3 sealed alone (about 46 m³ net), the same rise for the people inside
  happens far faster. Door states therefore matter, and coupling them to the volume is a Phase 1 prerequisite (section 7.2).
- The docking contradiction is resolved by a four-layer state model (section 4.1). The real ship stays DOCKED with its rings locked.
  The training runs a **simulated COAST**, which is what the existing ring start already shows (boom retracted to stand-off, rings at
  4 rpm).
- DS-1 "Scrubber" becomes an unscored guided tutorial. DS-2 is designed as the first true Deadship challenge (section 5.8).

---

## Decisions applied (owner, 2026-11-13)

| ID | Decision | Where applied |
| --- | --- | --- |
| DS-Q1 | Station-run Deadship training is approved as a gameplay concept. It is not an official Wayfarer crew qualification without more lore approval. | §2, §4 |
| DS-Q2 | The First Ignition failure sequence is deferred to the Tale and engineering owner sources. No invented canon. | §9 Phase 5 |
| DS-Q3 | Solo training is permitted. Competitive rules and scoring weights stay provisional. | §5.6, §5.7 |
| DS-Q4 | The CO₂-removal architecture is a labelled prototype grounded in credible ECLSS engineering, with its unknowns kept. | §7.2, `cabin_air.PROTOTYPE` |
| DS-Q5 | `data/deadship/` is approved for game-owned scenario definitions, separate from canon. It is created when first needed, not now. | §6 |
| DS-Q6 | Browser-local progress and records only. No backend or shared leaderboard. | §6.7 |
| DS-Q7 | A simulated COAST configuration is approved. The real docking and rotation constraints are kept. | §4.1 |
| DS-Q8 | Resolved by reading the row (below). No owner decision was needed. | §2 |

**DS-Q8 read 2026-11-13.** IGNITION — Sports (`1jTQwjXinvHve-1vBJ6mgmefPRos4adC4UCdZc9mEUU0`), `'Occupational Sports'!I2`, Deadship,
ESTABLISHED: "Scoring: survivability + resource conservation + system stability + time. Wayfarer becomes the nightmare real-world
version." Mechanics (F2): "Restore breathable atmosphere, thermal control, navigation, power etc. with deliberately insufficient
parts/resources."

**Traceability.** Decisions, sources and implementation tasks:

| Item | Source or decision | Implemented as |
| --- | --- | --- |
| Cabin 80 kPa | spec `habitat.atmosphere` (BASELINE, `cabin_atmosphere`) | `cabin_air.spec_values` |
| CO₂ target 0.3 %, control maximum 0.5 % | spec `habitat.atmosphere.control` (WORKING, `cabin_atmosphere_control`, 02!A49:H52) | `cabin_air.spec_values`, band CONTROL |
| CO₂ 1.0 kg per person-day | `data/life_support.toml` `CO2_REMOVED` (41!B15, STUDY) | `cabin_air.co2_rate` |
| Free gas volume 466.4 m³ | built rooms: `pressure_volumes.rooms` (sector net), `ring_circulation.budget` (corridor gross) | `cabin_air.volume` (PROTOTYPE) |
| Occupants 6, 295 K, unit rated for 12, well mixed | DS-Q4 | `cabin_air.PROTOTYPE` |
| Degraded 0.8 kPa, danger 3.0 kPa | DS-Q4, public reference levels | `cabin_air.BANDS` (PROTOTYPE) |
| ECLSS bay `Prod_RA3_GDN_ECLSS` | `route_fitout` ECLSS_Bay, UJ-004 station | `cabin_air.BINDING` |
| Simulated COAST | DS-Q7 | the ring start (existing) + `#interior-systems` |
| No new key | owner §7 | `exc.ops` reused |

---

## 1. Current state audit

### 1.1 Interactive experience

| Question | Finding | Evidence |
| --- | --- | --- |
| Rendering | Godot 4 (4.7.2 measured), `gl_compatibility` on desktop and mobile, exported to Web (WASM engine 39.5 MB, pack 23.1 MB). Explore Ship is a separate three.js viewer. | **[EXISTS]** `godot/project.godot:27-28`; `docs/wayfarer-web-experience-plan.md` §5; `web/viewer/viewer.js` |
| Scenes | Two playable scenes: Explore Interior `godot/scenes/excursion.tscn` (main scene), Explore Exterior `godot/scenes/eva_ops.tscn`. The page hash picks the start (`#interior`, `#interior-excursion`, `#exterior`, `#exterior-first-flight`). | **[EXISTS]** `godot/scripts/web_page.gd`; `web/play/launch.js`; `docs/MODEL.md` "Runtime representation" |
| Player control | A crew body moved by the walk: hand over hand along rig body lines when weightless, a friction-limited deck walk (walk, run, jump) in spin gravity, the ladder rung by rung; third or first person camera; MPFB character with blended gait. | **[EXISTS]** `godot/scripts/excursion/excursion.gd`, `locomotion.gd`, `line.gd`, `godot/scripts/physics/crew_body.gd`, `godot/scripts/characters/character_rig.gd`; `docs/LOCOMOTION.md` |
| Interactions | One contextual **Use** (`exc.use`): hatch from its panel, corridor/sector door, drum cycle, ladder foot, ring B branch; **Ops** (`exc.ops`) at a trunk panel runs the DOCKED ↔ COAST mode sequence. Each kind is hard-coded in `use()` / `_hatch_in_reach()` / `_door_in_reach()`. | **[EXISTS]** `excursion.gd:994-1195` |
| Interactable objects | Closures bound from the manifest (`induction.mechanisms`), CIRC doors (mesh and collider move together), learning stations bound to exported nodes by manifest `source_name` (e.g. `Prod_RA3_GDN_ECLSS`, `Prod_RA2_WRK_Ops_2`, `Prod_RA2_WRK_Tools_Workbench`). There is no general interactable registry. | **[EXISTS]** `excursion.gd:208-292`; `godot/scripts/excursion/learning.gd`; `src/wayfarer/learning_stations.py:74-150` |
| Physics and collision | Jolt for contact; colliders from the rig and shared route/hull formulas, never from visual meshes; ring frames with centrifugal, Coriolis and Euler terms; fail-closed mode controller. | **[EXISTS]** `godot/scripts/physics/` (`frame_field.gd`, `mode_controller.gd`, `vestibule.gd`); `docs/PHYSICS.md` |
| Game state | Scene-local variables in `excursion.gd` (mode, closures, drums, progress bins per ring, visits) and `WfModeController`. No save game. The controls profile is the only persistent state. | **[EXISTS]** `excursion.gd:31-110`; `godot/scripts/controls/wf_input.gd` |
| Scenario engine | EVA "First Flight": eight stages that advance only on real scene state, one labelled training intervention (reserve vented), gas never created. | **[EXISTS]** `godot/scripts/eva/eva_scenario.gd` |
| Fault injection and ledgers | EVA allocator forces failed valves shut and gives the body the wrench the duties actually produce; four N₂ inventories each keep a ledger (contents + used − reset = first fill). | **[EXISTS]** `godot/scripts/eva/allocator.gd`, `n2_tank.gd`; `docs/EVA_OPERATIONS.md` |
| Interior/exterior separation | One Godot package, two scenes; F8/F9 switch; every exported node carries a zone (`EXTERIOR`, `SHELL`, `INTERIOR:<area>`). | **[EXISTS]** `representation.zone`; `docs/MODEL.md` "Zones" |
| Controls | `WfInput` autoload: action ids, contexts per scene, setup only for essential actions, browser-local profile `user://wayfarer_controls.cfg` (schema 4, IndexedDB), conflicts checked across contexts, touch buttons via `wf_touch.gd`. A new action is a new row in `SCENE_ACTIONS`. | **[EXISTS]** `wf_input.gd:157-166`; `docs/MODEL.md` "Player controls (ACI, CTRL-001)"; `godot/scripts/check_controls.gd` |
| Deployment | GitHub Pages from `main` only, through `.github/workflows/web-explorer.yml` (tests, build, browser-check, site, deploy, verify, verify-browser). | **[EXISTS]** |
| Checks | Headless Godot checks drive the player's own semantic actions (`--check-excursion`, `--check-locomotion`, `controls`, EVA 44 checks); browser check `tools/web_check.py`. | **[EXISTS]** `godot/scripts/excursion/check.gd`, `check_locomotion.gd`; `tools/runtime_export.py` |

**Reusable components.** `WfInput` and the overlay, `wf_touch.gd` context buttons, `WfKeyText` key chips, the learning-station
binding by exported node (the template for interactables), the ring map (the template for a systems schematic), `WfModeController`
(ordered, fail-closed procedures), `WfEvaScenario` (state-driven stages), `WfN2Tank` (ledgers), the allocator's "deliver what the
hardware actually produces" rule, the runtime check harness.

**Architectural weaknesses that matter for Deadship.**
- `excursion.gd` is 1,839 lines and owns movement, closures, drums, HUD, station and checks. Adding Deadship inside it would make it
  unmaintainable. Deadship needs its own modules and a small hook (section 6.6).
- Interactions are kinds hard-coded in `use()`; there is no registry of "things in reach with verbs".
- There is no runtime systems state at all: no power bus, atmosphere, coolant or component health exists while walking.
- No save/persistence beyond controls; adding scores must not touch the controls schema.
- The registry still lists the retired scenes' contexts (`walk`, `life`, `thermal`, …; TODO J05). New Deadship actions should get a
  clean context, and pruning first avoids confusion.
- Browser CI runs SwiftShader at 0.3 fps; anything real-time cannot be verified there, so Deadship checks must be headless and
  deterministic (they can be: section 6.7).
- Small doc drift seen during the audit: `docs/MODEL.md` names Explore Ship `web/explore/`, the folder is `web/viewer/`.

### 1.2 The model: what Deadship can use

| Area | State | Deadship use | Evidence |
| --- | --- | --- | --- |
| Station and entrance | STN-001/002 boarding node, tunnel, boom, hatches, airlock chamber; walkable as the excursion's boarding line. PROTOTYPE, not part of Wayfarer. | The Deadship organizers' base: briefing at the boarding node (Phase 4). | **[EXISTS]** `station.py`; MODEL "Station-to-ring excursion" |
| Ring A and ring B | Three pressurized sectors per ring (HABITATION, WORK_MEDICAL_OPS, LIFE_SUPPORT_GARDEN_COMMON), mirrored; CIRC-001 corridors with sliding pressure doors and a mid-corridor bulkhead door; 177 m circuit per ring; fully walkable both rings. | The playfield. Doors are real isolation tools. The mirrored ring B is the natural cannibalization source. | **[EXISTS]** `ring_circulation.py`, `route_fitout.py:494-599`; CIRC-001 PROTOTYPE |
| Sector fit-out | ECLSS bay and Garden racks (sector 3), workbench, lab bench, medical couch, three ops screens (sector 2), hygiene and berths (sector 1); visible air line, water line and power/data conduit at each sector's service drop; SP-54 hazard and cue panel in every sector overhead; SP-46 waste door; drone cassettes (DS-05/07 floor, DS-06/08 duct door on the ECLSS bay). | Diagnosis points, repair points, alarm displays, service routes, a spares source. | **[EXISTS]** `route_fitout.py`, `survival_fit.py`, `drone_fleet.py` |
| Maintenance access | Crew trunk, drums, crew tubes and ladders, landing wells (walkable); storeroom SP-45 and storm refuge SP-48 exist as geometry off the trunk but are **not on a walkable line**. | Hullrun-style routes; storeroom becomes reachable only when a trunk line to its port is added. | **[EXISTS]** `storeroom.py`, `survival_fit.py`; **[OPEN]** walk lines to SP-45/SP-48 |
| Power | Two generators, two buses A/B, layered storage (2 MWh main battery, 200 kWh / 50 MW pulse bank WORKING; survival reserve BASELINE with capacity OPEN), nine-step black start (WORKING). Whole-ship load `power.rating` **OPEN**. | Bus A/B redundancy, survival-load list, the black start as a procedure scenario. | **[EXISTS]** `data/wayfarer_3d.toml` `[power]`, `power_storage.py` |
| Life support | Cabin 80 kPa, O₂ 25 % (20 kPa) BASELINE; CO₂ target 0.3 %, max 0.5 %, RH 40–50 % WORKING; tolerances, medical limits, emergency O₂ OPEN; stock/flow integrator for the owner's 41 STUDY rates (O₂ 0.84, CO₂ 1.0, water 4.16, food 1.83 kg per person-day). | The fastest, most teachable clock (CO₂) and the slow ones (O₂, water, food). | **[EXISTS]** `[habitat.atmosphere]`, `cabin_atmosphere.py`, `life_support.py`, `data/life_support.toml` |
| Thermal | Hot (1800 K blades), warm (440 K) and cold (~320 K ring faces) loops; F02 two-mode warm loop with heat pumping in the burn; Stefan–Boltzmann budget; radiator health display of 480 isolatable cells (display only). Heat capacities, Heat Debt, failure clock **OPEN**. | Load shedding, cooling capacity as a resource, the radiator cell isolation as an exterior task (later). | **[EXISTS]** `thermal_budget.py`, `heat_rejection.py`, `thermal_loops.py`, `radiator_health.py` |
| Propellant | Thirteen-vessel longitudinal tank farm, three species, feed run tanks; boil-off and feed faults not modelled. | Phase 5 only (story-scale stakes). | **[EXISTS]** `fuel_storage.py` |
| Fiji/Lattice drive | One core, four nozzles; startup/shutdown key tables; lattice activation in the black start steps 7–8. | Procedure knowledge, not an MVP repair target (its internals are fiction and mostly OPEN). | **[EXISTS]** `drive_manifold.py`, `[power.black_start]` |
| Shielding and navigation | Forward shield, Eyes, Crown, Dust Lance with damage poses (`SHIELD_DAMAGED`, display); learning stations on the ops screens. | Later: "navigation lost" scenarios on the ops screens. | **[EXISTS]** `forward_shield.py`, `eye_placement.py` |
| Diagnostic interfaces | Learning stations (WHAT/WHY/SHOW ME); radiator health display; the HR-001 fault register (fourteen faults, step replays) as a study. | The teaching layer and the manual's voice. | **[EXISTS]** `learning.gd`; `studies/hr001_states.py` |

**Placeholders.** Every interior, its equipment and every room position is PROTOTYPE; equipment is block geometry without opening
covers, internal parts or connectors. A carried spare part, an opened service cover or a bypass jumper has no mesh today.

### 1.3 Engineering simulation: real logic versus presentation

| System | Real calculation exists? | Runtime simulation? |
| --- | --- | --- |
| Power generation/distribution | Storage layers, exact energy consequences, black-start step table and its alignment with the drive key tables. No load model, no bus flows. | No |
| Atmosphere, O₂, CO₂ | Partial pressures, control bands, consistency checks; daily stock/flow of O₂, CO₂ removed, water, food, waste with exact depletion days and ledgers (worst 3e-9 kg). No cabin volume dynamics. | No (the Godot life-support simulator was retired) |
| Thermal | Stefan–Boltzmann budgets, view-factor screen, F02 loop sizing, the root calibration margin. No heat capacity or temperature transients (OPEN by canon). | No (the thermal explorer was retired) |
| Water processing | Recovery 90/98 % scenarios and makeup in the stock/flow. | No |
| Propellant | Masses, volumes, operating point (mass flow, jet power). | No |
| Structure | Fit screens and hand checks (CIRC-C7 116/200 MPa); FEA OPEN. | No |
| Damage/degradation | Radiator cells (display), `SHIELD_DAMAGED` / `RADIATOR_DAMAGED` poses (display), `DAMAGED` configuration declared but not buildable (OD-010). | No |
| Failure propagation | HR-001 fourteen-fault study with step replays; the drone fault replays (power loss, rail jam, lost link). | Replays only |
| Resources | EVA N₂ ledgers and allocation (real, runtime). | **Yes, exterior only** |
| Materials (PMDS) | Purposes, catalogue, appearances, applications; material screens with verdicts (EXCEEDS_LIMIT / NOT_EVALUABLE / WITHIN_CHECKED_LIMITS). | No; a source for component temperature limits |

**Authoritative data.** `data/wayfarer_3d.toml` with `data/source_map.toml` (statuses), `data/life_support.toml`, `data/materials/`,
`data/simulations/*.json`. Deadship must read these through pure modules, never copy them (AGENTS.md "Data rules").

**Conclusion of the audit.** Nothing to recreate: Deadship should consume `life_support.py`, `cabin_atmosphere.py`, `power_storage.py`,
`thermal_budget.py`, `heat_rejection.py` and PMDS through a new reusable systems model. What is missing is the dynamic layer (lumped
stocks, flows and component states stepping in time) and the interaction registry.

---

## 2. Lore alignment

**[LORE] IGNITION — Sports** (Drive file `1jTQwjXinvHve-1vBJ6mgmefPRos4adC4UCdZc9mEUU0`, read 2026-11-12):
- *Overview*: "Deadship — You cannot save everything. Diagnose, prioritize, cannibalize, stabilize." Design principle: "IGNITION sports
  are technologies of survival that civilization eventually learns to play with."
- *Occupational Sports*, Deadship row: status **ESTABLISHED**; culture "Spacer engineering / emergency response"; participants "Small
  technical teams"; environment "Disabled ship or high-fidelity simulator"; mechanics "Restore breathable atmosphere, thermal control,
  navigation, power etc. with deliberately insufficient parts/resources"; tests "Diagnosis, prioritization, cannibalization, teamwork, systems
  thinking"; character link **Rian Osei**; note "Scoring: survivability + resource conservation + system stability + time. Wayfarer
  becomes the nightmare real-world version." (Occupational Sports A2:I2, full row read 2026-11-13, DS-Q8.)
- Hullrun row: **ESTABLISHED**; "Station maintenance / engineering"; "Ducts, trusses, micro-g chambers, tether lanes"; "Traverse a
  realistic ship-maintenance obstacle course, often carrying components/tools"; tests "Climbing, crawling, EVA-style movement, spatial
  awareness, tool handling"; Rian Osei; "Rian's physical sport; pairs naturally with Deadship."
- *Timeline*: Y100–155 "Hullrun / Deadship culture" in the Wayfarer generation; ~Y155 "Deadship/Hullrun skill culture" aboard
  Wayfarer; canon note "Wayfarer is a major sports-history ancestor without being a sports story."
- *Canon & Sources*: "Maintenance becomes competition; navigation becomes racing…" (HIGH confidence).

**[LORE] Tale** (`data/source_map.toml` notes, LOCKED): Rian Osei is Wayfarer's systems engineer and de facto captain, Seraph's
Bolt-Sworn; the six occupants and the person-to-system mapping (Tale A13:G19) are LOCKED. The ship is designed for twelve (LOCKED
2026-11-08); six is the story manifest.

**What follows for the design.**
1. **Deadship is a training discipline turned sport, so a station-run training scenario aboard the real ship is lore-native.** The
   Sports row allows "disabled ship or high-fidelity simulator". Running it aboard Wayfarer while docked at the development station
   (the GU acceptance and crew-qualification period) needs no new canon. **[PROPOSAL]**
2. **Scoring is canon in its four terms** (survivability, resource conservation, system stability, time). The weights and formula are
   ours to propose (section 5.6) and stay **[OPEN]** for the Sports owner.
3. **"Deliberately insufficient parts" is canon**, so scarcity is a rule of the game, not a difficulty knob.
4. **Hullrun pairs with Deadship.** The walk's routes (corridors, ladders, drums, trunk) are a Hullrun course already; Deadship's
   carry tasks make them meaningful. Hullrun itself (timed traversal with components) is a separate, cheap mode later.
5. **The story must not become a sports story.** "Wayfarer is a major sports-history ancestor without being a sports story." Story mode
   (Concept C) therefore must not show scores, leaderboards or "Deadship" branding during the real accident; Rian's Deadship habits show
   in how he works, and the debrief after the fact can say "that was a Deadship". **[PROPOSAL]**
6. **The ship-first rule holds.** Deadship never changes geometry, a pressure boundary, an interface or a canon value. A scenario may
   mark components failed, isolated, removed or bypassed in its own state only. Story conflicts are logged as STORY_DEPENDENT issues.
7. **Sports workbook points to keep apart.** Vector Run is the Wayfarer-born navigation sport (First Loop, Y155–161); Durak is the crew's
   ritual. A navigation-loss Deadship scenario should not drift into Vector Run's identity.

**[OPEN]** No Drive row describes a Deadship rulebook (team size, penalties, standard scenarios, league), the First Ignition accident's
failure sequence, or whether a Deadship-style qualification is part of Wayfarer's crew acceptance. DS-Q1 to DS-Q3 were decided on 2026-11-13: training is a gameplay concept and not an official qualification, the accident waits for its owner sources, and solo training is allowed with provisional competitive rules.

---

## 3. Gameplay concepts compared

| | A. Training simulator (separate) | B. Deadship aboard Wayfarer | C. Survival mechanic (story) | D. Hybrid progression |
| --- | --- | --- | --- | --- |
| What | A dedicated simulator room or mock ship at the station | Controlled simulation mode on the real ship; faults live in systems state | The First Ignition accident and the voyage played as interconnected survival | Training → competitive Deadship → real survival |
| Reuses | Station shell, walk, controls | The whole interior walk, both rings, doors, ladders, learning stations, controls, touch | All of B plus timeline, operating point, black start | All |
| New modeling | A new simulator interior (large), its equipment | None for MVP; later detail packs for service covers and spares | Damage states for many systems; OD-010 degraded modes | As B, then C |
| Teaches the real ship | Partly (a generic mock-up) or duplicates Wayfarer | Directly: the player learns the actual ship's layout and systems | Directly | Directly |
| Lore fit | Good (canon allows simulators) | Very good: a training scenario aboard the docked ship | Good but blocked by OPEN Tale rows; must not read as sport | Very good |
| Canon risk | Low | Low (scenario state only) | High: invents accident details unless the Tale supplies them | Managed by staging |
| Cost to first playable | L (new environment) | S–M | L+ (needs B's systems anyway) | As B |
| Replay value | Medium | High (scenarios × locations × difficulty) | Medium (narrative) | High |

**Evaluation.**
- **A** duplicates what Wayfarer already is: a walkable, systems-explained ship. A separate simulator only pays off later as the
  *briefing room* at the station (a screen and a door, not a modeled ship). Not the first step.
- **B** is the cheapest path to something playable and is the only one that teaches the real ship from the first minute. Its risk is
  confusing simulation state with canon; the scenario-owned labelling and the separate systems state handle that.
- **C** is where the systems are meant to end up, but every interesting choice depends on accident facts the Tale has not released and
  on degraded modes (OD-010) and heat capacities that are OPEN. Built first it would either invent canon or be hollow.
- **D** is the right *roadmap*. Its first stage is B.

---

## 4. Recommended experience

**Approved direction.** Concept D is the roadmap, Concept B the first implementation and Concept C comes after its inputs exist. The
player is a trainee (the walk's existing newcomer) during Wayfarer's commissioning at the development station. The GU instructor who
already greets the trainee offers station-run Deadship training on the real ship, with faults injected into the simulated systems state.
This is a gameplay concept (DS-Q1). It is not an official Wayfarer crew qualification. Rian Osei, an experienced competitor, may set or
review harder runs once his identity and appearance are released (K01). Until then he appears in text only, with no body.

Why this answer:
- It reuses the walk wholesale and needs no geometry for the first phases.
- Learning comes from the ship itself. A trainee who loses CO₂ control learns where the ECLSS bay is, that sector doors split the air,
  and that ring B mirrors ring A.
- It matches canon: the training origin, "disabled ship or high-fidelity simulator", deliberately insufficient parts, the four scoring
  terms and Rian's sport.
- The systems foundation it forces into existence is what Concept C needs later.

**Entry points.** Explore Interior's default `#interior` start stays exactly as it is.
- **[BUILT P0]** `#interior-systems` (`-- --systems` natively) is the Phase 0 proof start.
- **[PROPOSAL]** `#interior-deadship` (`-- --deadship`) would be the training start from Phase 1.
- Explore Exterior gains Deadship tasks only in Phase 4 or later.

### 4.1 State model: the real ship, the simulated configuration, the gameplay, the simulated systems

The contradiction in DS-000: the real ship at the development station is DOCKED, with both rings stopped and locked (14!A8, BASELINE).
Deadship training wants rotating rings. The resolution keeps four layers apart:

| Layer | What it is | Where it lives | Phase 0 |
| --- | --- | --- | --- |
| 1. Real spacecraft configuration | Wayfarer at the station: DOCKED, rings stopped and locked, boom extended. Never changed by training. | Canon (14!A8); the walk's STATION start shows it (`excursion.gd` `ctl` DOCKED) | Untouched |
| 2. Simulated training configuration | COAST: undocked at the boom's 25 m stand-off with the boom retracted (STN-002), rings at 4 rpm. A physically valid state the real ship can reach through the owner's sequence. | `WfModeController` in COAST from the first frame (`excursion.gd` `_ring_start`, existing). No transition is played. | **[EXISTS]** reused as is |
| 3. Player experience | Walk, doors, ladder and learning in spin gravity; the HUD says SIMULATION | `excursion.gd`, `locomotion.gd` | Unchanged; the board says "SIMULATION x60" |
| 4. Simulated systems | Engineering states (Phase 0: ring A cabin CO₂) | `cabin_air.py` → `wf_cabin_air.json` → `WfCabinAir` | **[BUILT P0]** |

Facts from the audit that make this clean:
- **[EXISTS]** The default ring start already builds layer 2. `_ring_start()` creates the mode controller in COAST, puts the station at
  its stand-off (`station_offset = 1.0`, boom retracted) and synchronizes drum A with the ring. It never shows a docked ship with
  spinning rings, so no impossible configuration has to be created or removed.
- **[EXISTS]** The station start (`#interior-excursion`) builds layer 1 and plays the owner's DOCKED → COAST order through Ops at the
  trunk. It is untouched.

**Transitions [PROPOSAL from Phase 1].**
- *Into training*: only through the training start. The run begins in COAST at t = 0, as the ring start does. The real ship's
  undocking is never played as part of a training run, so the simulation cannot imply that the docked ship spins.
- *During a run*: the trunk's Ops mode requests are refused with "the simulator holds Wayfarer in COAST". Equipment operations (Ops at
  equipment) are allowed.
- *Out of training*: the run ends in a debrief. The player then either restarts the run or leaves the experience. A free walk after the
  run continues in the same COAST, and any return to the station uses the existing spin-down, lock and dock order.
- The systems state is session-local. It is never written to canon, the manifest, the rig or the controls profile.

---

## 5. Gameplay mechanics (design; Phase 0 builds none of this)

### 5.1 The loop

**Diagnose → Prioritize → Cannibalize → Improvise → Stabilize** **[LORE]**, played as:

1. **Brief** (instructor text; the scenario's known symptoms only, never the cause).
2. **Notice**: alarms on the SP-54 cue panels, the ECLSS board, the HUD's few vital readouts (only what the trainee can perceive or a
   panel shows).
3. **Diagnose**: walk to equipment, inspect it, read its local indicators, compare with the systems schematic; form a hypothesis.
4. **Prioritize**: clocks are visible (time to CO₂ limit, battery hours left); the player chooses what to fix and what to let go.
5. **Act**: physical tasks at the equipment (isolate, swap, bypass, reroute, shed), each with a modelled cost.
6. **Stabilize**: call "Stable". The simulator runs the **watch** (5.6) and the debrief explains what happened and why.

### 5.2 System graph (first version) [PROPOSAL, ENG]

*Long-term illustration of the couplings Deadship needs, not a framework to build up front (owner 2026-11-13: no ship-wide graph or
generic port/flow framework before a scenario needs it). Each phase adds only the stocks its scenario uses (section 9).*

A lumped, directed graph of **components** with **ports** carrying typed flows. Small enough to explain, real enough that consequences
emerge.

```
   POWER                          THERMAL (cold loop, per ring)          ATMOSPHERE (per ring air volume)
   Gen 1 ─┐                        Cabin heat ──► Coolant pump ──► HX ──► Ring radiator faces ──► space
   Gen 2 ─┼─► Bus A ─┬─► loads     (people, equipment)   ▲ power          (cold-loop rejection)
          └─► Bus B ─┘            Equipment temperature ◄┘ if flow drops
   Main battery ─► buses           (lumped thermal mass, PROTOTYPE)        People ─► CO₂ ─► CO₂ removal unit ─► vent/regenerate
   Survival reserve ─► survival loads (LIFE_SUPPORT, FLIGHT_COMPUTER,       O₂ store ─► O₂ supply ─► People
                       COMMS, EMERGENCY_LIGHTING, CRITICAL_PUMPS_VALVES)   Humidity ─► condensing HX (shares the cold loop)
   Doors/hatches: isolate air volumes (sector, corridor halves); a leak drains one volume
```

Couplings that create decisions:
- CO₂ removal, fans, coolant pumps and condensing heat exchanger draw **bus power**; the survival reserve feeds only its listed loads
  **[EXISTS: list in `[power.storage.survival_reserve]`]**.
- Every watt used in the cabin is **heat** in the cold loop; less coolant flow means equipment heats up and trips; tripped equipment
  stops its function. Energy is conserved: power drawn = heat produced (+ stored).
- Humidity removal shares the cold loop's condensing HX: shedding cooling raises RH over hours.
- Closing doors splits air volumes: isolating a sector protects the rest but leaves its occupants (or its equipment) on their own.
- Ring A and ring B are mirrored: everything exists twice; cannibalizing ring B costs ring B's redundancy, visible later in the watch.

### 5.3 Component states

`NOMINAL → DEGRADED → FAILED`, plus player-set `ISOLATED`, `BYPASSED`, `REMOVED`, `JURY_RIGGED` (works, derated, with a reliability
penalty per hour). A component has a small set of **parts** only where a decision needs them (a CO₂ unit: fan, sorbent bed, valve,
controller). Every part has a **symptom** (what a person can see or measure) and a **cause**.

### 5.4 Resource scarcity [PROPOSAL]

| Resource | Matters as | Kept light by |
| --- | --- | --- |
| Time (ship time, compressed and labelled) | The clocks: CO₂, battery, temperature | One visible clock per active threat |
| Electrical energy and power | Battery Wh left; bus capacity (W) per bus | Two numbers on the schematic, not per-device spreadsheets |
| Cooling capacity | Cold loop W available vs heat produced | One bar per ring |
| Atmosphere (CO₂, O₂, pressure, RH) | Survivability | Partial pressures on the board, colour bands |
| Spare parts | Deliberately too few | A short manifest ("1 fan, 0 sorbent cartridges, 1 jumper cable"), max one carried item |
| Consumables | Sorbent, filters, sealant | Counted only where a scenario uses them |
| Tools | Gate tasks (a jumper needs the electrical kit) | A kit, not an inventory grid |
| Reliability | Jury-rigs and cannibalized parts fail sooner | Shown in the watch, not as a hidden die roll |

The "no tedious inventory" rule: the player never sorts items; the scenario defines a handful of things, each with a reason.

### 5.5 Repair and interaction mechanics

Physical where the body matters, technical interface where a panel is the real way a crew member would do it **[PROPOSAL]**:

| Verb | Physical or interface | How |
| --- | --- | --- |
| Inspect | Physical | Walk to the component, Use: close camera on the equipment, local readouts (fan current, bed temperature, flow) |
| Diagnose | Interface | Ops screen or handheld: schematic with live values; the player marks a hypothesis (optional, scored as "diagnosis time") |
| Open / close service access | Physical | Use at the equipment (needs service covers as bound mechanisms later; MVP highlights the bay) |
| Isolate / power off | Physical at the equipment or interface at a panel | Breaker or valve: the one action that makes work safe; refusing to work on a live unit teaches the rule |
| Remove / carry / install a part | Physical | One item in hand; it slows a run (PROTOTYPE); doors must be opened; the ladder is climbed with it stowed |
| Reroute / bypass | Physical at the service drop (air line, water line, power conduit already exist at each sector) | Jumper or crossover valve; derated and logged |
| Shed load | Interface | Turn non-essential loads off at the ops screen (lights, Garden, lab) |
| Close a pressure door | Physical | Existing CIRC doors; now they change the simulated air volumes |
| Emergency procedure | Interface, with physical steps | Ordered, fail-closed steps like `WfModeController` (e.g. switch to bus B, then restart the unit) |
| Call "Stable" | Interface | Hold to confirm; starts the watch |

Avoid abstract button pressing: a repair is a *sequence in space* (isolate here, fetch there, install, restore), and every step is
something a real technician does.

### 5.6 Scoring [PROPOSAL; provisional, DS-Q3]

Canon terms: survivability + resource conservation + system stability + time.

- **The watch.** When the player calls "Stable", the simulator steps the same model forward a fixed projection (e.g. 24 h ship time,
  scenario-set) with **no further input**. A band-aid that holds for ten minutes and fails at hour six scores as what it is. This is the
  core anti-exploit and the core of "stability".
- **Survivability S (gate and score).** Crew exposure to out-of-band conditions over the run plus the watch (time above CO₂ max, below
  O₂ partial bound, outside temperature band). A hard limit crossed = "ship lost": the run ends with a debrief, no rank.
- **Stability St.** At the end of the watch: margin of each tracked quantity to its limit, number of alarms, jury-rigs still in place.
- **Conservation C.** Value of what is left (battery Wh, spares, consumables, ring B redundancy) against the start.
- **Time T.** Ship time to "Stable", weighted least.
- **Penalties.** Secondary damage caused by the player (working on a live unit, overheating equipment by shedding cooling), unresolved
  critical failures at the end of the watch.

A starting proposal: `score = S_gate × (40 S + 30 St + 20 C + 10 T) − penalties`, each term 0–1. Under these weights a player who
isolates the faulty unit, uses one spare and leaves a non-critical fault documented beats one who repairs everything by stripping ring B.

**Anti-exploit rules [PROPOSAL].**
1. *Closed action world*: only modelled actions exist; an action whose consequence is not modelled is not offered (it is never free).
2. *Ledgers*: every resource keeps the EVA ledger invariant (contents + used − reset = first fill); nothing is created.
3. *The watch* catches temporary fixes.
4. *Unmodelled-consequence flags*: where canon is OPEN, the scenario either fixes a PROTOTYPE value or removes the option.
5. *Scenario screens* (run on demand, not CI tests): a search over the scenario's action space proves at least one stabilizing solution
   exists, no full repair is possible with the parts given (canon: insufficient parts), and no solution scores high without stabilizing.
6. *Deterministic replay*: seed + scenario hash + semantic action log reproduces a run exactly, so a competition result can be checked.
7. *Training resets and hints* mark a run unranked (as EVA's training reset is labelled).

### 5.7 Modes

| Mode | Phase | Notes |
| --- | --- | --- |
| Training | Phase 1 (DS-1, unscored) | No time pressure beyond the physics, hints on, the instructor explains WHAT/WHY (reuse the learning panel) |
| Challenge | Phase 2 (DS-2) | Two interacting problems, insufficient parts, provisional score |
| Competition | Phase 4 | Standardized scenario set, fixed seeds, replay codes, local best scores; no backend |
| Survival | Phase 4–5 | Cascading faults over a long watch |
| Story | Phase 5 | No scores, no Deadship branding (section 2, point 5) |

---


### 5.8 Refined scenarios (design only, not implemented)

#### DS-1 "Scrubber": unscored guided tutorial (Phase 1)

Purpose: teach the loop on one fault, with no competing problems, no inventory management and no score.

| Step | What the player does | What it teaches | Uses |
| --- | --- | --- | --- |
| 1 Recognize | The sector 3 board turns amber (ABOVE TARGET). The instructor points at it. | A warning is a band, not a verdict: what the control band is | Board (built P0), bands |
| 2 Inspect | Use at the bay: fan current 0 A, bed temperature low, controller healthy | Symptoms are measurements | Learning panel, part readouts |
| 3 Interpret | The ops screen shows the unit powered and the CO₂ trend rising at about +0.04 %/h | Powered but not scrubbing points at the fan, not the bed or the supply | Readout `dxdt_per_h` (built P0) |
| 4 Isolate | Ops at the bay: ISOLATED | Isolate before maintenance. Working on a live unit is refused with the reason. | `operate('isolate')` (built P0) |
| 5 Navigate | Walk to the sector 2 workbench through the CIRC doors and carry the one spare fan | Where things are; doors split the air | Walk, doors (existing) |
| 6 Repair | Use at the bay: install the fan | Physical repair at the equipment | Part state (Phase 1) |
| 7 Restore | Ops at the bay: RUNNING | Restoring service is a deliberate step | `operate('restore')` (built P0) |
| 8 Verify | Watch the trend turn negative, then a short projected watch confirms the CO₂ returns below the target and stays there | Stable means stable over time, not just at one moment | Exact step, the watch |

Crossing the 0.5 % control limit ends the tutorial as an **operational failure**. The screen then says plainly that the crew is not
harmed, that the limit is where corrective action is required, and how far the degraded-habitability and danger levels still are
(section 7.2). The tutorial teaches the difference instead of hiding it.

#### DS-2 "Borrowed Air": the first true Deadship challenge (Phase 2)

Principle: **you cannot save everything.** Two interconnected problems, too few parts, at least two valid stabilizations, each with
consequences the model computes.

Situation (scenario-owned values, PROTOTYPE):
- **Problem 1:** ring A's CO₂-removal fan fails. There is no spare fan, because the scenario's manifest has none.
- **Problem 2:** ring A's cabin cooling runs on one of its two cold-loop pumps (the other has failed). Heat removal from the ring is
  limited, and the condensing heat exchanger that removes humidity shares that loop.
- Six people are in ring A. Ring B is empty and healthy.

Valid strategies, and what the model shows for each:

| Strategy | Immediate effect | Consequence the model computes | Resources | Long-term stability |
| --- | --- | --- | --- | --- |
| S1 Cannibalize ring A's condensing-HX fan into the CO₂ unit | CO₂ falls within the hour | Humidity removal stops: the crew's vapour (roughly 2 kg per person-day, ENG estimate) accumulates and RH passes the 50 % band in about an hour (condensation risk); latent heat stays in the ring | No parts used; ring A loses dehumidification | Poor: a second problem now grows |
| S2 Fetch ring B's CO₂ fan through the trunk and drum (a Hullrun carry) | CO₂ falls after the carry time | Ring B can no longer hold anyone; the cold-loop limit is unchanged | Uses ring B's redundancy; time | Good while everyone stays in ring A |
| S3 Move the crew to ring B and seal ring A | Ring A's CO₂ no longer matters | Ring B's unit carries six at its rating; ring A's heat still has to go somewhere; drum cycles and time | No parts; time; ring A unattended | Good, but ring A's faults stay unresolved |
| S4 Shed heat load in ring A (lab, Garden lights) and run on one pump | Temperature margin restored | CO₂ still rises: on its own it does not stabilize the ring | Power; lost functions | Fails the watch unless combined |

A competent player combines strategies (for example S2 with S4), and the score reflects that. Everything in the table must come from
model state: humidity is a stock with sources (crew vapour) and a sink (the condensing HX), heat is a stock with a cooling limit, parts
are entities that can be moved, and occupancy is per ring. No penalty is scripted.

What Phase 2 must add to the model (prerequisites, section 9): two ring air volumes, door-coupled compartments, a water-vapour stock,
a lumped heat stock with the cold-loop limit, parts as model entities, per-ring occupancy, and the watch.

---

## 6. Technical architecture

### 6.1 Layers, as built in Phase 0 and as they will grow

The DS-000 proposal (a ship-wide component graph, a generic port/flow framework and a scenario compiler) is **not** built. The owner
asked for proof first. Phase 0 shows that a simpler shape gives the same validated function, and each later phase adds only what its
scenario needs.

```
 data/wayfarer_3d.toml, data/life_support.toml          (canon + statuses)          data/deadship/   (created when Phase 1 needs it)
        │                                                                                │
        ▼                                                                                ▼
 ENGINEERING MODEL  src/wayfarer/cabin_air.py   [BUILT P0]                     SCENARIO LAYER  (future consumer; not built)
   state, exact step, operations, readout, bands,                                faults (cabin_air.fail), objectives, the watch,
   checkpoints; knows nothing of games                                           scoring, debrief
        │  export/godot.py writes wf_cabin_air.json into the runtime package [BUILT P0]
        ▼
 RUNTIME MODEL  godot/scripts/systems/cabin_air.gd  WfCabinAir   [BUILT P0]
   same step; verify() against the checkpoints before use
        │                                   ▲
        ▼                                   │ operate("isolate" / "restore")
 VISUALIZATION  board (Label3D on the bay),  INTERACTION  godot/scripts/excursion/equipment.gd  WfEquipment  [BUILT P0]
 HUD prompt, touch label  [BUILT P0]         binds the packaged node, reach, Ops → the model; ~5 hook lines in excursion.gd
```

| Layer | Owns | Must not |
| --- | --- | --- |
| Engineering model (`cabin_air.py`, `WfCabinAir`) | Physical state, step, allowed transitions, readout, bands, reference checkpoints | Know about games, scenarios, scores, keys or nodes beyond its binding record |
| Interaction (`WfEquipment`) | Which node, the reach, which operation Ops requests now | Compute numbers or bypass a refused transition |
| Visualization (board, prompt, touch label) | Showing the readout and the band, labelled SIMULATION | Show anything the model did not read out |
| Scenario (future, `data/deadship/`) | Faults, objectives, the watch, scoring | Change the model's laws or write back to canon |

**Independence check (built).** `cabin_air.py` imports only the spec, `life_support`, `pressure_volumes` and `ring_circulation`.
`WfCabinAir` references no scene, no `WfInput` and no Deadship term. The interaction layer calls only `operate`, `step` and `readout`.
`cabin_air.fail()` is the fault entry point that a scenario or story beat would use; Phase 0 does not call it at runtime.

### 6.2 Python reference and GDScript runtime

- **Minimum interface.** One JSON file per engineering state, written by the export: parameters with statuses, the binding, the states
  and allowed operations, the bands, the tolerance and the proof run (events plus checkpoints). Godot reads it and computes no parameter.
- **Exact step.** For constant generation and removal over a step, the CO₂ balance has a closed-form solution, so both sides evaluate
  the same formula and the result does not depend on the step length (verified at 1 s and 60 s).
- **Tolerance, not bit-equality.** Python and Godot both use IEEE 754 doubles, but their `exp()` may differ in the last place.
  Checkpoint agreement is `|got − want| ≤ 1e-9 kg + 1e-9 × |want|`. The justification and the measured margins are in section 13.
  A checkpoint outside the tolerance sets `verified = false`: the board says REFERENCE CHECK FAILED, the walk logs an error, the bay
  offers no operation and the check fails.

### 6.3 Interaction architecture

The smallest reusable abstraction: `WfEquipment` is "a piece of equipment bound to a packaged node, with a reach and an operating state".
- It reuses `WfLearning`'s node lookup (`_mesh`, manifest `source_name`) and the same ring-pivot rule for its centre.
- `excursion.gd` changes only by hooks: a variable, creation behind `systems_requested()`, a step in `_physics_process`, a branch at
  the top of `ops()`, a touch button, a prompt line, a board update and a page-record field.
- Doors, hatches, the ladder, learning stations and Use are not touched. Ops elsewhere behaves as before.
- **Why Ops, not Use.** Use at the bay already steps the UJ-004 learning station (WHAT / WHY / SHOW ME). Ops is the existing "operating
  change" action, so its meaning extends naturally from the trunk panel to equipment panels. No new action, key or setup question is
  needed. The description text of `exc.ops` now names both uses.
- A general registry (several equipment kinds, verbs, conditions) waits until a second piece of equipment exists (Phase 1 adds the
  workbench and a part). Then `WfEquipment` becomes a list.

### 6.4 Controls

- No new action, no hard-coded key and no new `setup` row. Ops (`exc.ops`) is reused, and every prompt prints the player's binding
  through `key()` / `WfInput.label`. Saved profiles (schema 4) are untouched, because profiles store bindings by action id and the
  description text is not stored.
- Touch: the existing contextual-button mechanism (`touch_state()` → `wf_touch.gd`) shows "Ops · isolate CO2 unit" or "Ops · restore
  CO2 unit" while the bay is in reach.
- **Legacy contexts.** The retired contexts in `wf_input.gd` (`walk`, `life`, `thermal`, …) are not needed for Phase 0 and are left
  untouched. Pruning them stays separate maintenance (TODO J05).
- Phase 1 may add `deadship.*` actions (for example a hold-to-confirm "Stable"). Each would be a new non-setup row in the registry,
  checked by the existing conflict checker, with a touch button.

### 6.5 Persistence, deployment, what goes where

- Phase 0 persists nothing. From Phase 1, browser-local progress goes in a separate `user://wayfarer_deadship.cfg` (DS-Q6), never in the
  controls profile.
- No backend, no TypeScript, no WebAssembly module and no new dependency. Nothing is deployed: Pages deploys only from `main`.

| Part | Place | Status |
| --- | --- | --- |
| Engineering state and reference | `src/wayfarer/cabin_air.py`, `tests/test_cabin_air.py` | BUILT P0 |
| Package file | `wf_cabin_air.json`, written by `src/wayfarer/export/godot.py` | BUILT P0 |
| Runtime model | `godot/scripts/systems/cabin_air.gd` | BUILT P0 |
| Interaction and display | `godot/scripts/excursion/equipment.gd` + hooks in `excursion.gd`; `web_page.gd` (`#interior-systems`) | BUILT P0 |
| Headless check | `godot/scripts/excursion/check_systems.gd`; runtime check `systems` in `tools/runtime_export.py` | BUILT P0 |
| Scenario data | `data/deadship/*.toml` | Phase 1 (DS-Q5) |
| Scenario engine, the watch, debrief | `godot/scripts/deadship/` | Phase 1–2 |
| Service covers, a spares rack | A detail pack (`docs/MODULES.md`) | Phase 3+ |

---

## 7. Engineering fidelity

### 7.1 Three levels

| Level | What | Pros | Cons |
| --- | --- | --- | --- |
| 1 Scripted | Predefined fault → predefined fix | Fast to author | No emergent consequences; teaches puzzles, not the ship |
| 2 System | Lumped, conserving stock/flow graph with component states | Real trade-offs; cheap; explainable | Needs PROTOTYPE values where canon is OPEN |
| 3 High fidelity | Parameters and laws derived from the engineering modules | Teaches the real ship; validates designs | Blocked where canon is OPEN; heavier |

**Recommendation [PROPOSAL]: level 2 for the MVP, with level-3 parameters wherever canon exists.** The data format is the same for both,
so moving a component from a scenario value to a released owner value changes data, not code. Level 1 is used only for tutorial
scaffolding (a hint sequence), never for outcomes.

### 7.2 CO₂: equations, volume, the three tiers and the uncertainty [ENG; values as labelled]

**Equations (as built in `cabin_air.py`).** CO₂ stays below 1 % of the cabin gas, so it is treated as a trace gas. The total amount
n = PV/(RT) is held fixed and the CO₂ mass m carries the state:

- dm/dt = G − k·m/V, with G = occupants × 1.0 kg per person-day, and k the unit's effective scrubbed flow (0 unless RUNNING).
- Exact step for constant G and k: m(t+Δt) = m_ss + (m − m_ss)·e^(−kΔt/V), where m_ss = G·V/k. With k = 0: m(t+Δt) = m + G·Δt.
- Mole fraction x = (m/M_CO₂)/n. Partial pressure p = x·P.
- Unit rating (PROTOTYPE): k is set so that the rated twelve are held exactly at the target, k = G₁₂·RT/(P·M·x_target) ≈ **116 m³/h**
  of fully scrubbed air. That is a plausible order for a regenerable sorbent unit with a process-air fan. With six aboard, the steady
  state is 0.15 %.

**What the 120 m³ in DS-000 was.** It is the canon *usable volume allocation per ring* (`habitat.layout.usable_per_ring_m3`, 12!A2:A4,
WORKING): a space-planning figure. It is neither the pressurized volume nor the connected gas volume. The built PROTOTYPE rooms give:

| Volume (PROTOTYPE geometry) | m³ | Source |
| --- | --- | --- |
| Ring A sectors, net (deck to overhead less modelled fit-out; subfloor excluded) | 37.7 + 44.2 + 46.0 = 127.9 | `pressure_volumes.rooms` |
| Ring A sectors, gross (inside the skin) | 3 × 72.4 = 217.2 | `pressure_volumes.rooms` |
| Ring A circulation corridor (CIRC-001), gross clear cavity | 338.5 | `ring_circulation.budget` |
| Crew tubes (each, excluded) | about 49 | `pressure_volumes.rooms` |
| **Phase 0 free gas volume: sectors net + corridor gross** | **466.4** | `cabin_air.volume` |

The connected volume depends on the doors. With the CIRC doors open and ventilation mixing the ring, ring A is one volume of roughly
466–556 m³. With sector 3 sealed it is about 46–72 m³. Phase 0 models the first case as one well-mixed volume (PROTOTYPE `mixing`), and
the door states are not coupled yet. Coupling them is a Phase 1 prerequisite. Without it, closing a door would leave the model's
volume wrong.

**Hours from the 0.3 % target to the 0.5 % control limit with the unit off** (linear rise):

| Volume case | 6 people | 3 people | 2 people | 1 person |
| --- | --- | --- | --- | --- |
| Ring connected, Phase 0 (466 m³) | **5.4** | 10.7 | 16.1 | 32.1 |
| Ring all gross (556 m³) | 6.4 | 12.8 | 19.1 | 38.3 |
| Canon usable allocation (120 m³, DS-000) | 1.4 | 2.8 | 4.1 | 8.3 |
| Sector 3 sealed, net (46 m³) | 0.5 | 1.1 | 1.6 | 3.2 |
| Sector 3 sealed, gross (72 m³) | 0.8 | 1.7 | 2.5 | 5.0 |

Lesson for the design: isolating a compartment (against a leak, a fire or contamination) also shrinks the CO₂ buffer of the people
inside it. That is a real engineering trade-off, and it falls out of the model without any tuning.

**Three tiers, kept apart** (bands by partial pressure, because the body responds to partial pressure, not to the fraction):

| Tier | Level here (80 kPa) | Status | Meaning | Tutorial behaviour |
| --- | --- | --- | --- | --- |
| Operational control limit | x > 0.5 % (0.40 kPa) | WORKING canon (02!A49:H52: "not final medical/ECLSS limits") | Outside the normal operating range: corrective action required | Ends the run as an operational failure, and says so |
| Degraded habitability | p ≥ 0.8 kPa (1.0 % here) | PROTOTYPE reference: the order of long-duration submarine practice (about 0.8 % at one atmosphere) | Safety margin reduced; headaches and lower performance likely over hours | Shown as the next band |
| Physiological danger | p ≥ 3.0 kPa (3.75 % here) | PROTOTYPE reference: the order of the 15-minute occupational limit (3 % at one atmosphere) | Clinically meaningful risk | Shown as the band to avoid |

Medical limits are OPEN in canon (12!G22), so the second and third tiers are teaching references, never canon values. Times from the
steady state with six aboard and the unit off: control limit about 9.4 h, degraded habitability about 23 h, danger about 96 h. A failed
scrubber is therefore a slow, manageable emergency in a ventilated ring, which is the correct engineering lesson. It becomes urgent only
in a small sealed volume or with many people.

**Uncertainty.**
- The volume is PROTOTYPE geometry. It could vary by about −0 % / +19 % (net versus gross), and much more if the doors close.
- The 1.0 kg per person-day rate is a STUDY hypothesis (it depends on metabolism and activity; 0.8–1.2 is a common range).
- Temperature (295 K) is PROTOTYPE, but it enters only through n, as about 0.3 % per kelvin.
- Mixing is idealized: real cabins have local pockets, for example near sleepers.
- The unit rating is PROTOTYPE, and the technology and its parts are OPEN (12!G26:G27, DS-Q4).
- Not modelled: O₂ drawdown (slow: a week-scale clock), humidity, leaks and the sorbent's own capacity and regeneration cycle.

### 7.3 Limits and what stays honest [ENG]

- **Electrical loads are OPEN** (`power.rating`). Scenario-owned PROTOTYPE loads, labelled, with bus capacities and the battery's 2 MWh
  (WORKING) where used. No endurance claim is shown as ship canon.
- **Heat capacities and Heat Debt are OPEN.** Lumped thermal masses are scenario values; Stefan–Boltzmann and the cold-loop numbers from
  `heat_rejection.py` are used as published; temperatures shown are labelled simulation values.
- **ECLSS internals are OPEN.** The CO₂ unit's parts (fan, bed, valve, controller) are a PROTOTYPE taxonomy; the technology
  (regenerable sorbent) is an engineering assumption to put to the owner (DS-Q4).
- **Medical limits are OPEN** (12!G22). The control band (WORKING) is an operational limit. The degraded-habitability and danger
  levels are PROTOTYPE teaching references (section 7.2), never claimed as physiological canon.
- **Fiji/Lattice.** Its internals stay out of repair gameplay; where it appears (black start), the energy flows follow the published
  steps and the pulse bank's 200 kWh / 50 MW. Fictional technology never creates energy, removes heat or skips a pressure rule.
- **Not modelled:** fluid transients, fire chemistry, structural failure, radiation dose. A scenario that needs one is out of scope until
  a model exists (anti-exploit rule 4).

---

## 8. Research: approaches worth borrowing

Drawn from general knowledge of these games and practices; no external code or assets are proposed.

| Reference | What works | Take for Deadship | Avoid |
| --- | --- | --- | --- |
| *FTL* | Power allocation as a small, legible budget; systems as rooms | Bus power as a few bars; clear room-to-system mapping | Abstract button repairs |
| *Barotrauma* | Physical repair in a shared vessel; wiring and junction boxes; mechanical vs electrical skills | Repairs at the equipment, parts carried, the ship as a machine you walk through | Ever-growing item inventories |
| *Oxygen Not Included*, *RimWorld* | Emergent consequences from a resource graph; slow clocks that become crises | Stock/flow with conservation, visible consequences | Simulating so much that cause and effect blur |
| *Space Station 13* (atmospherics) | Gas mixes per room, doors and vents matter | Air volumes split by doors | High-fidelity gas grid (far beyond need) |
| *Keep Talking and Nobody Explodes* | The manual is part of the game | A Wayfarer systems manual (the learning-station texts grown up) | Puzzles for their own sake |
| *Duskers* | Diagnosis under uncertainty; terse, diegetic interfaces | Board readouts and a handheld instead of a god view | |
| Factorio, *Kerbal Space Program* | Learning by failing in a consistent model; deterministic simulation | Determinism; "the model is the teacher" | |
| Real practice: Apollo 13 LiOH adapter, the 1997 Mir fire and Spektr collision, ISS ammonia and CO₂ events, NASA FMEA and fault trees, damage-control training | Isolate, stabilize, then fix; jury-rigs with known derating | The watch; jury-rig reliability; isolation as the first move | Dramatic invention |
| Deterministic lockstep and replay (fixed step, seeded inputs, input logs) | Verifiable results, regression tests from recorded play | Replay codes, the reference-solution check | |
| Browser 3D performance (Godot Web, compatibility renderer) | Simulation cost is negligible; draw calls and memory dominate | No new heavy geometry; runtime emission changes only; profile with `profile_views.gd` | Real-time CI verification under SwiftShader |

---

## 9. Development roadmap

A dependency-based roadmap, not a commitment to build every feature.

| Phase | Status | Content | Depends on | Acceptance | Size |
| --- | --- | --- | --- | --- | --- |
| **0 Minimal engineering integration proof** | **DONE on this branch, awaiting review** | One engineering state (ring A cabin CO₂), one real component (sector 3 ECLSS bay), one interaction (Ops: isolate / restore), one diagnostic display (the bay's board, the prompt, the touch label), deterministic validation | Owner authorization (given 2026-11-13) | Section 13 and section 14 | S |
| **1 Scrubber tutorial** | DESIGN ONLY | DS-1 (section 5.8): unscored and guided; a FAILED unit with part states (fan, bed, controller); the spare fan at the workbench; door-coupled air volumes; a short watch; the tier explanation on failure | Phase 0 approved; the prerequisites below | All eight DS-1 steps play through player actions in a headless check; the default start unchanged; the tutorial explains the three tiers | M |
| **2 First true Deadship challenge** | DESIGN ONLY | DS-2 "Borrowed Air" (section 5.8): two interacting problems, insufficient parts, at least two valid stabilizations with model-computed consequences; the watch and provisional scoring | Phase 1; humidity and heat stocks; two rings; parts as entities | A scenario screen shows ≥ 2 stabilizing strategies, no full repair, and different scores from model state alone | M–L |
| **3 Broader engineering systems** | DESIGN ONLY | Bus A/B power and the survival-reserve loads, cold-loop limits, load shedding, longer watches, ring B through the trunk and drum | Phase 2; PROTOTYPE electrical loads (power.rating OPEN) | Trade-offs between power, heat and air reproduce in Python and Godot within tolerance | L |
| **4 Competitive Deadship and Hullrun** | DESIGN ONLY | Standard scenarios, repeatability (seeds, replay codes), provisional scoring, browser-local records (DS-6), Hullrun timed carries, the station briefing | Phase 3; walk lines to the SP-45 storeroom | Replays identical native and Web; records stay in browser storage only | L |
| **5 Narrative survival** | DESIGN ONLY | First Ignition and the voyage on the same model; no scores and no Deadship branding | Tale and engineering owner rows for the accident (DS-Q2); OD-010 degraded modes; heat capacities | Story beats run on the model with no invented canon | L+ |

**Exact prerequisites for Phase 1:**
1. The owner reviews and approves Phase 0, including the volume and band choices in section 7.2.
2. The FAILED state reachable through a fault input (`cabin_air.fail` exists) and a `repair` transition with part states, added to
   the model, its checkpoints and its tests.
3. Door states coupled to the air volume: each CIRC door joins or splits compartments. This is the main modelling step: compartment
   volumes, occupancy per compartment, and mixing across open doors.
4. A second interaction point (the sector 2 workbench, carrying one part). This is when `WfEquipment` becomes a small registry.
5. `data/deadship/` created for the DS-1 definition (DS-Q5), with a scenario loader that only calls the model's public operations.
6. A `#interior-deadship` start and the transitions of section 4.1 (the trunk's Ops refused during a run).
7. A projected watch: running the same exact step forward with no input, which is cheap because the step is exact for any Δt.

## 10. Phase 0: what was built

**Selection: the ring A sector 3 ECLSS bay.** It was the lowest-risk point:
- It is a real exported node (`Prod_RA3_GDN_ECLSS`) that the walk already finds and follows as the ring turns (UJ-004 learning
  station).
- It is on the ring A circuit that the default start already walks.
- Its system (cabin CO₂) has canon pressure and a canon control band, a sourced STUDY rate, and an exact closed-form model.

No other component was easier: the power and thermal systems have their decisive values OPEN, and the trunk panels belong to the
docking sequence.

**How to see it.**
- Natively: `godot --path godot -- --systems`.
- In a browser build: `play/…#interior-systems`.

Walk to the sector 3 ECLSS bay. The board above the bay shows ring A's CO₂ (fraction, partial pressure, trend, unit state, band and
time to the control limit, at a labelled ×60 simulation rate). Ops there isolates the unit, and the CO₂ starts rising. Ops again
restores it. Nothing is deployed: the owner's review path is the screenshots in the project Library.

**Data flow.**
1. `data/` → `cabin_air.params()`: canon pressure, control band and CO₂ rate, plus the PROTOTYPE volume, occupants, temperature and
   rating.
2. `export/godot.py` → `wf_cabin_air.json` in the runtime package. This includes the proof run's 33 checkpoints and the tolerance.
3. `WfCabinAir.load_package()` → `verify()` replays the proof run and compares every checkpoint and the ledger. Only a verified model is
   offered.
4. `WfEquipment` binds the packaged node and the reach. In `_physics_process` it steps the model by Δt × 60.
5. The player presses Ops (their own binding, or the touch button) → `excursion.ops()` → `WfEquipment.operate()` →
   `WfCabinAir.operate("isolate" | "restore")`. The model accepts the operation or refuses it by its transition table.
6. `readout()` → the board text and colour, the prompt line and the touch label; `record()` → `window.wayfarerWalk.systems` and the
   check.

**Files.**

| File | Change |
| --- | --- |
| `src/wayfarer/cabin_air.py` | new: the engineering state and reference |
| `tests/test_cabin_air.py` | new: 7 invariant tests |
| `src/wayfarer/export/godot.py` | writes `wf_cabin_air.json` into the package (4 lines) |
| `godot/scripts/systems/cabin_air.gd` (+ `.uid`) | new: runtime model with `verify()` |
| `godot/scripts/excursion/equipment.gd` (+ `.uid`) | new: the bay binding, Ops, the board |
| `godot/scripts/excursion/check_systems.gd` (+ `.uid`) | new: the headless check |
| `godot/scripts/excursion/excursion.gd` | hooks only, behind `systems_requested()` |
| `godot/scripts/excursion/check_locomotion.gd` | one assertion: the default start creates no systems proof |
| `godot/scripts/web_page.gd` | `#interior-systems` start variant |
| `godot/scripts/controls/wf_input.gd` | the `exc.ops` description names equipment panels (text only) |
| `tools/runtime_export.py` | the `systems` runtime check |
| `docs/MODEL.md`, `docs/IMPLEMENTATION.md`, `TODO.md` | the SYS-001 entries |

**Deliberately not built:** a scenario engine, faults at runtime, part states, repairs, door coupling, a second ring, humidity, heat,
power, scoring, the watch, persistence, new actions, Deadship branding, any geometry or Blender change, any Drive write and any
deployment.

---

## 11. Risk analysis

| Risk | Mitigation |
| --- | --- |
| Scope grows into a full spacecraft simulator | Phase gates with acceptance criteria; a component enters the graph only when a scenario needs a decision from it |
| Browser performance | Simulation is tiny (lumped); no new geometry; runtime emission only; measure with `profile_views.gd` before and after |
| Duplicated engineering data | `ship_systems` reads the spec and owner modules; scenarios hold only values canon leaves OPEN, labelled PROTOTYPE |
| Gameplay depends on unfinished models | Scenario-owned values; released owner values replace them in data; anti-exploit rule 4 removes options whose consequence is unmodelled |
| Repetitive puzzles | Faults are states of a graph, not scripts; vary location (ring A/B), cause behind the same symptom, occupants, parts given |
| Repairs feel like UI | Sequences in space (isolate, fetch, install, restore); the body carries parts through doors and ladders |
| Hard to explain systems | Learning-station WHAT/WHY/SHOW ME, the schematic, the debrief replay, one clock at a time, progressive scenarios |
| Damage simulation changes canon | Separate runtime state; never written back; no geometry change; the manifest and rig untouched |
| Gameplay coupled to engineering | One-way dependency (Deadship → systems); the systems model has no scenario knowledge; tests on the systems layer only |
| Breaking the walk | Separate start hash, separate modules, a small hook in `excursion.gd`, existing checks as the gate |
| Controls conflicts | New context rows only, none `setup`; the existing conflict checker covers them |
| Story read as a sports story | Story mode without scores or branding (lore point 5) |
| Canon gaps stall progress | Proceed on scenario values; questions DS-Q1..Q8 go to the request Doc only with the owner's authorization |

---

## 12. Open items after the 2026-11-13 decisions

DS-Q1 to DS-Q8 are decided (see "Decisions applied"). What remains open:

| ID | Item | Default until decided |
| --- | --- | --- |
| DS-O1 | Phase 0 review: the PROTOTYPE volume (sectors net + corridor gross), six occupants in ring A, 295 K, the unit rated for twelve | As built |
| DS-O2 | The degraded-habitability (0.8 kPa) and danger (3.0 kPa) reference levels: keep, or replace when ECLSS and medical owner rows exist (12!G22) | As built, labelled PROTOTYPE |
| DS-O3 | The ×60 display rate of the proof (DS-1 may want its own rate, or a compressed clock with a pause) | ×60 in the proof only |
| DS-O4 | Authorization for Phase 1 | Not started |
| DS-O5 | Medical limits, ECLSS technology and its serviceable parts, whole-ship electrical load, heat capacities, OD-010 degraded modes | OPEN in canon; scenario values labelled |
| DS-O6 | Deadship as an official Wayfarer crew qualification | Not established (DS-Q1) |

---

## 13. Engineering validation (Phase 0)

All commands ran from the repository root on 2026-11-13 on this branch, in the cloud container (Blender 4.x snap, Godot 4.7.2).

**13.1 The reference model (Python, `src/wayfarer/cabin_air.py`).**

| Check | Command | Result |
| --- | --- | --- |
| Invariant tests | `python3 -m unittest discover -s tests -k cabin_air` | 7 tests, OK |
| Canon inputs read, not copied | test `canon parameters read` | 80 kPa, 0.3 % target, 0.5 % control limit, 1.0 kg CO₂ per person-day come from `data/` through `spec` and `life_support` |
| Rated crew held at the target | test `rated crew held at target` | 12 people → steady state 0.300 % exactly |
| Exact step, independent of Δt | test `exact and dt-independent` | 60 s and 1 s steps and the analytic solution agree to 1e-12 relative |
| Mass ledger closes | test `ledger` | m = m₀ + generated − removed to < 1e-9 kg over the proof run |
| Isolated rise rate | test `isolated rise rate` | k = 0 gives dm/dt = G exactly (+0.037 %/h with six aboard) |
| Transitions | test `transitions` | restore while RUNNING refused, double isolate refused, FAILED cannot be restored, an unknown operation refused; refusals leave the state unchanged |
| Bands ordered | test `bands ordered` | control < degraded < danger by partial pressure |
| Module summary | `python3 src/wayfarer/cabin_air.py` | 466.4 m³, n 15 211 mol, k 116.1 m³/h, 0.150 % steady with six; target → limit 5.36 h unit off; 33 checkpoints |

**13.2 The runtime copy (GDScript, `godot/scripts/systems/cabin_air.gd`) against the reference.** `WfCabinAir.verify()` replays the
packaged proof run (8 h, isolate at 0.5 h, restore at 4.5 h, Δt 1 s) and compares all 33 checkpoints and the ledger at every step with
the packaged tolerance (1e-9 relative + 1e-9 kg absolute). The walk offers the model only when `verify()` passes; otherwise the board
turns red and an error is pushed.

| Check | How | Result |
| --- | --- | --- |
| Reproduces the reference | `verify()` on the published package (in the `systems` runtime check and a direct script run) | 33 of 33 checkpoints, worst relative deviation 0.0 |
| Ledger in Godot | same run | −2e-13 kg |
| Rejects a wrong reference | a checkpoint altered by 1e-8 relative | rejected with the checkpoint named |
| Accepts noise inside tolerance | a checkpoint altered by 5e-10 relative | accepted |
| Determinism | `check_systems.gd`: 1 s steps vs 60 s steps vs a repeated run | 1.39394102129855 / …843 / …855 kg (agree to 1e-13 relative) |

**13.3 The interaction in the walk (`godot/scripts/excursion/check_systems.gd`).** Run inside `runtime-export` as the `systems` check
(`--fixed-fps 60 res://scenes/excursion.tscn -- --systems --check-systems`), and again with stills under a virtual display.

| Step | Result |
| --- | --- |
| Ops away from the bay | changes nothing (state and operation count unchanged) |
| Walk the ring A circuit as a player (Use opens the doors) | the bay reached, 2.2 m from its centre (reach 2.4 m), 49 walked bins |
| Prompt and touch button at the bay | "Ops · isolate CO2 unit", then "Ops · restore CO2 unit" |
| Ops → ISOLATED | the model's state, the board text and the button change |
| 600 frames isolated (10 s of play, 600 s simulated at ×60) | m = 1.04580580503923 kg against the closed form 1.04580580503922 kg; the trend positive |
| Ops → RUNNING, 600 frames | the exponential closed form met within tolerance; the trend negative |
| Ledger and transition log | closed; exactly 2 transitions |
| Result | `"result":"PASS"`, 8 673 physics frames, 14.4 s wall (final run) |

**What the validation does not show.** It shows that the runtime reproduces the reference and that the interaction drives the model
through its own transitions. It does not validate the PROTOTYPE values (volume, occupancy, rating, the two reference bands) against
reality: those are labelled in the package and listed in DS-O1 and DS-O2.

## 14. Regression report

| Area | Command | Result |
| --- | --- | --- |
| Data validation and selected tests | `python3 tools/workflow.py checks --run` | 39 tests OK (1 skipped, pre-existing); selection: test_cabin_air, test_drive_sync, test_frames_import, test_hooks, test_modules, test_route_import; no build target, no inspection group |
| All unit tests | `python3 -m unittest discover -s tests` | 235 tests OK (1 skipped), 243 s |
| Ship build | `/snap/bin/blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/build.py` (the saved assets were missing in this fresh container) | exit 0; no generator, data or geometry file changed, so the change selects no geometry check |
| Characters (needed by the runtime package) | `python3 tools/workflow.py characters` | PASS |
| EVA loop | `python3 tools/workflow.py eva` | PASS, "FULL EVA loop" |
| Runtime package and all Godot checks | `python3 tools/workflow.py runtime-export` | PASS, 9 checks, first run `20261113T102531048530Z-runtime`; rerun on the final code (after the board-placement fix below) `20261113T111529180970Z-runtime`, PASS, 9 checks |
| · COAST and DOCKED import | `check`, `check-docked` | PASS (5 287 and 5 264 meshes, 242 lights) |
| · Boarding route | `route` | PASS |
| · Interior walk, doors, hatches, learning stations | `excursion` (default start, both rings and back) | PASS |
| · EVA Operations | `eva-ops` | PASS |
| · Locomotion (ladder, gait, run, mag boots); default start has no systems proof | `locomotion` | PASS (the new assertion included) |
| · Phase 0 systems proof | `systems` | PASS |
| · Controls: profiles, setup rows, conflicts, rebinding, touch | `controls` | PASS |
| · Characters in Godot | `characters` | PASS |
| Browser smoke: website build | `python3 tools/workflow.py play-characters --out <dir>`, then `python3 tools/workflow.py web --out <site> --characters <dir>` | PASS (both) |
| Browser smoke: main browser check | `python3 tools/web_check.py <site> --part main --chrome /opt/pw-browsers/chromium --no-sandbox` | PASS, 67 of 67: start page, Explore Ship viewer (28), Explore Interior and Exterior boot and play (15 + 2), controls (8), switching and memory (4), phone (5), status page |

**Compatibility, by the owner's list.**
- *Doors and hatches:* untouched code; the systems check opens the ring A CIRC doors through Use on its way to the bay.
- *Actions and bindings:* no new action, key or context row; Ops (`exc.ops`) is reused at the bay, so whatever key, pad button or touch
  button the player bound works there. Only the action's description text names the new use. No key is hardcoded; the prompt and the
  touch label take the key text from the existing `WfInput` label utilities.
- *Profiles and setup:* the schema-4 profile file and the setup rows are unchanged; the `controls` check passes.
- *Touch:* the existing context button shows "Ops · isolate CO2 unit" at the bay (checked by `_ui_says`).
- *Learning stations:* Use at the bay still opens the UJ-004 life-support station; Ops was chosen precisely so the two do not compete.
- *Movement:* no change to the walk, ladder, run or mag boots.
- *Station walkthrough and default start:* the systems proof exists only with `--systems` or `#interior-systems`; the locomotion check
  fails if the default start ever creates it.
- *Legacy contexts:* none touched.

**Not run, with the reason.**
- The full `pipeline` (Cycles previews, whole-ship inspection, baseline diff): no geometry, generator or `data/` file changed and the
  check selection names no build target, so AGENTS.md step 4 does not require it. The build above confirms the generators still run.
- The browser `equivalence` and `walk` (touch walk) parts of `web_check.py`: CI runs them on their own runners and they take much
  longer; the `controls` runtime check and the `systems` check's touch-label assertion cover the touch path natively. The browser site
  was built while the board placement was still being fixed; the systems proof is off in the default start, so the browser check
  exercised the unchanged default walk.
- The `#interior-systems` start was not opened in a browser; it is the same scene with one start flag, checked natively.

**Fix found during validation.** The first stills showed the board sideways or mirrored, because world Y is not "up" in a spinning
ring. The board now faces the viewer upright and sits above the bay towards the ring's spin axis, in narrower lines; "Control limit
… in -" became "not approaching". Display only; the model and checks were unchanged and rerun.

## 15. Handoff

**F1. What was implemented.** One engineering state (ring A cabin CO₂ in a well-mixed volume), one physical component (the sector 3
ECLSS bay, `Prod_RA3_GDN_ECLSS`), one interaction (Ops: isolate or restore the CO₂ unit), one diagnostic display (the bay's board, the
prompt line and the touch label), and one deterministic validation (the packaged reference with tolerance, plus the `systems` check).
Files and data flow: section 10.

**F2. What was not implemented.** Everything in Phase 1 and later: no scenario, tutorial, fault injection at runtime, part states,
repairs, door coupling, second ring, humidity, heat, power, watch, scoring, persistence, Deadship branding or `data/deadship/`. No
geometry, Blender, canon, Drive, deployment or `main` change.

**F3. What can be reused.** `WfCabinAir` is a model with public operations only and no game knowledge; a tutorial or scenario calls
`operate()` and reads `readout()`. The reference-and-checkpoint pattern (Python writes the proof run, Godot replays it with a packaged
tolerance) is the template for every later system. `WfEquipment` is the binding pattern from a packaged node to an operable state; it
becomes a small registry at the second interaction point (Phase 1 prerequisite 4).

**F4. Independence.** Dependencies run one way: `data/` → `cabin_air.py` → package JSON → `WfCabinAir` → `WfEquipment` → the walk's
existing Ops hook. The model knows nothing about the walk, and the walk knows nothing about CO₂ beyond the readout. Removing the
`--systems` start removes the feature with no trace in the default walk.

**F5. Walkthrough and controls intact.** Section 14: every existing runtime check passes, the default start is asserted free of the
proof, and no action, binding, profile or setup row changed.

**F6. Uncertainties.** The PROTOTYPE volume (466 m³, and the door coupling that makes it change), six occupants, 295 K, the unit rated
for twelve, the two reference bands (0.8 and 3.0 kPa), the ×60 display rate, and the STUDY CO₂ rate (section 7.2). Medical limits and
the ECLSS technology stay OPEN in canon.

**F7. Phase 1 readiness.** Technically ready to start once authorized: the model, the validation pattern and the binding exist. Before
Phase 1 starts, the seven prerequisites in section 9 apply; the first is the owner's review of Phase 0 (DS-O1, DS-O2), and the main
modelling step is door-coupled compartments.

## 16. Final recommendation

Review Phase 0 through the stills in the project Library (the board RUNNING, ISOLATED and restored), and decide DS-O1 and DS-O2. If
they stand, authorize Phase 1 with door-coupled compartments as its first step, since DS-1's lesson (isolating a compartment shrinks
its air buffer) depends on it. Keep the branch unsquashed until then.
