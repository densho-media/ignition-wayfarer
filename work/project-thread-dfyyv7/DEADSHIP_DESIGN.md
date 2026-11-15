# Deadship in Wayfarer: research, design, Phase 0, Phase 1, Phase 2A and the Phase 2B gate (DS-000, DS-P0, DS-P1, DS-P2A, DS-P2B)

**Status (2026-11-14).** One branch, `claude/project-thread-dfyyv7`, not squashed, not deployed.

| Phase | Status | Where |
| --- | --- | --- |
| DS-000 research and design | Done (6603e08); direction approved 2026-11-13 | §0–§8 |
| Phase 0 minimal engineering integration (SYS-001, `#interior-systems`) | **Implemented and validated**; browser-verified on the Phase 1 build | §10, §13, §14, §19 |
| Phase 1 DS-1 "Scrubber" tutorial (`#interior-deadship`) | **Implemented and browser-tested** (f5e6031); finalized 2026-11-14: phone layout, usability fixes | §17–§21, §22 |
| Phase 2A atmospheric connectivity (SYS-002, `#interior-airflow`) | **Implemented and validated** 2026-11-14; finalized 2026-11-14 (bay instrument panel DS-O10, web-export size) | §23, §26 |
| Phase 2B DS-2 first playable challenge | **Authorized 2026-11-14 subject to an engineering gate; the gate FAILED on SYS-002, so no gameplay was built.** Findings, revised design and the smallest next requirement are in §27 | §24 [HISTORICAL], §27 |
| Phase 2C and later | Design only | §9, §24 |

Sections written before a phase was built are kept as written and marked **[HISTORICAL]** where later work changed them; their
calculations stand unless a note says otherwise.

DS-000 (2026-11-12, commit 6603e08) was research and design only. On 2026-11-13 the owner approved its direction with refinements
and authorized **Phase 0 only**. This revision folds those decisions in, refines the scenario designs and the CO₂ assumptions, and
reports the Phase 0 implementation, its validation and the regression runs. **Phase 1** (the DS-1 "Scrubber" tutorial) was authorized
later on 2026-11-13 and is reported in sections 17 to 21. Phase 2 and later stay **design only** and need separate authorization. Nothing here changes canon, the Blender model, generated geometry, engineering values or the deployment, and no Drive
workbook was written.

Every significant statement carries one of these labels:

| Label | Meaning |
| --- | --- |
| **[EXISTS]** | Implemented in the repository before this work (file path given) |
| **[BUILT P0]** | Implemented by Phase 0 on this branch (file path given) |
| **[BUILT P1]** | Implemented by Phase 1 on this branch (file path given) |
| **[BUILT P2A]** | Implemented by Phase 2A on this branch (file path given) |
| **[HISTORICAL]** | Written before later work changed it; kept for the record, with a note on what changed |
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
  **[HISTORICAL]** Door coupling moved out of Phase 1 (DS-1 does not need it, §17) and was built as Phase 2A (§23). The 466 m³ is
  the sum of ring A's nine compartments and remains a **model assumption** (sectors net plus corridors gross, everything joined by an
  assumed ventilation), not a finalized ventilation design.
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
| **0 Minimal engineering integration proof** | **IMPLEMENTED AND VALIDATED** (browser-verified on the Phase 1 build, §19) | One engineering state (ring A cabin CO₂), one real component (sector 3 ECLSS bay), one interaction (Ops: isolate / restore), one diagnostic display (the bay's board, the prompt, the touch label), deterministic validation | Owner authorization (given 2026-11-13) | Section 13 and section 14 | S |
| **1 Scrubber tutorial** | **IMPLEMENTED AND BROWSER-TESTED** (§17–§21); finalized 2026-11-14 (§22) | DS-1 (section 5.8): unscored and guided; a FAILED unit with part states (fan, bed, controller); the spare fan at the workbench; ~~door-coupled air volumes~~ (moved to 2A); a short watch; the tier explanation on failure | Phase 0 approved; the prerequisites below | All eight DS-1 steps play through player actions in a headless check; the default start unchanged; the tutorial explains the three tiers | M |
| **2A Atmospheric connectivity** | **IMPLEMENTED AND VALIDATED** 2026-11-14 (§23) | Ring A's nine compartments, doors and ventilation as a graph; the walk's doors are the connections; Ops at the bay switches the ventilation; `#interior-airflow` demo | Phase 1 | Cases A–G, conservation, Python/Godot parity, door truth, browser demo | M |
| **2B "You cannot save everything"** | **DESIGN PROPOSAL ONLY** (§24) | The smallest playable DS-2 step: one removal unit for a crew split across compartments, a door/ventilation choice with model-computed consequences; unscored | Phase 2A; owner authorization | ≥ 2 valid configurations with different, model-computed outcomes; no full repair possible | M |
| **2C "Borrowed Air"** | DESIGN ONLY | The full DS-2 (section 5.8): two interacting problems, insufficient parts, the watch and provisional scoring | 2B; humidity and heat stocks; parts as entities; possibly two rings | A scenario screen shows ≥ 2 stabilizing strategies, no full repair, and different scores from model state alone | M–L |
| **3 Broader engineering systems** | DESIGN ONLY | Bus A/B power and the survival-reserve loads, cold-loop limits, load shedding, longer watches, ring B through the trunk and drum | Phase 2; PROTOTYPE electrical loads (power.rating OPEN) | Trade-offs between power, heat and air reproduce in Python and Godot within tolerance | L |
| **4 Competitive Deadship and Hullrun** | DESIGN ONLY | Standard scenarios, repeatability (seeds, replay codes), provisional scoring, browser-local records (DS-6), Hullrun timed carries, the station briefing | Phase 3; walk lines to the SP-45 storeroom | Replays identical native and Web; records stay in browser storage only | L |
| **5 Narrative survival** | DESIGN ONLY | First Ignition and the voyage on the same model; no scores and no Deadship branding | Tale and engineering owner rows for the accident (DS-Q2); OD-010 degraded modes; heat capacities | Story beats run on the model with no invented canon | L+ |

**Exact prerequisites for Phase 1** **[HISTORICAL, 2026-11-13; status 2026-11-14 in brackets]:**
1. The owner reviews and approves Phase 0, including the volume and band choices in section 7.2. [Done: approved 2026-11-13 as
   prototype working assumptions, not canon.]
2. The FAILED state reachable through a fault input (`cabin_air.fail` exists) and a `repair` transition with part states, added to
   the model, its checkpoints and its tests. [Done in Phase 1: `fault_fan`, `install_spare`, the mode / fan / spare fields.]
3. Door states coupled to the air volume: each CIRC door joins or splits compartments. This is the main modelling step: compartment
   volumes, occupancy per compartment, and mixing across open doors. [Obsolete for Phase 1 (§17); built as Phase 2A (§23).]
4. A second interaction point (the sector 2 workbench, carrying one part). This is when `WfEquipment` becomes a small registry. [Done.]
5. `data/deadship/` created for the DS-1 definition (DS-Q5), with a scenario loader that only calls the model's public operations. [Done.]
6. A `#interior-deadship` start and the transitions of section 4.1 (the trunk's Ops refused during a run). [Done.]
7. A projected watch: running the same exact step forward with no input, which is cheap because the step is exact for any Δt. [Done.]

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

## 12. Open items (updated 2026-11-14)

DS-Q1 to DS-Q8 are decided (see "Decisions applied"). Status of the open items:

| ID | Item | Status |
| --- | --- | --- |
| DS-O1 | The PROTOTYPE volume (sectors net + corridor gross), six occupants in ring A, 295 K, the unit rated for twelve | **Approved 2026-11-13 as prototype working assumptions, not canon.** The 466 m³ is a model assumption, not a ventilation design (§23.1) |
| DS-O2 | The degraded-habitability (0.8 kPa) and danger (3.0 kPa) reference levels | **Approved 2026-11-13 as PROTOTYPE working assumptions**; replace when ECLSS and medical owner rows exist (12!G22) |
| DS-O3 | Display rates | Decided by build: ×60 in the Phase 0 proof, ×30 and the ×1800 watch in DS-1, ×120 in the Phase 2A demo |
| DS-O4 | Authorization for Phase 1 | **Given 2026-11-13; Phase 1 built.** Phase 2A authorized and built 2026-11-14 |
| DS-O7 | Ring ventilation: none is in canon. Phase 2A assumes one intermodule-ventilation duct pair per bulkhead at about 240 m³/h, with dampers; doorway exchange 139 m³/h; 9 compartments, 466.36 m³ | **Kept 2026-11-14 as PROTOTYPE, not canon, configurable** (`ring_air.params`). Finding (§27.4): with twelve crew in one ring these values hold sectors 1 and 2 at 0.447 % with everything working, under the 0.5 % limit but far above the 0.3 % target; an ECLSS owner row would replace them |
| DS-O8 | The crew-tube hatches: closed in the model, not animated in the walk; the tubes (3 × 49 m³) and the vestibule are a second path between sectors | **Decided 2026-11-14: closed and outside the model.** A boundary assumption: the tubes exchange no air with ring A in any scenario (§23.1) |
| DS-O9 | Authorization for Phase 2B | **Authorized 2026-11-14 subject to the engineering gate (§27). The gate failed on SYS-002; no gameplay built.** The next requirement is in §27.6 |
| DS-O10 | The ECLSS bay's board crossed the Map and ? buttons on an upright phone | **Resolved 2026-11-14** (§26.1): a tilted instrument panel mounted on the bay's top edge, measured clear of the touch row |
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

**[HISTORICAL, Phase 0]** Review Phase 0 through the stills in the project Library (the board RUNNING, ISOLATED and restored), and decide DS-O1 and DS-O2. If
they stand, authorize Phase 1 with door-coupled compartments as its first step, since DS-1's lesson (isolating a compartment shrinks
its air buffer) depends on it. Keep the branch unsquashed until then.

---

# Phase 1: DS-1 "Scrubber" tutorial (built 2026-11-13)

The owner authorized Phase 1 on 2026-11-13 (14:09Z) with approved working assumptions: 466 m³, six occupants, 295 K, a unit sized
for twelve, the 0.5 % WORKING control limit and the 0.8 / 3.0 kPa PROTOTYPE reference bands. These are working assumptions, not
canon. Phase 2 and later stay design only. Nothing in Phase 1 changes canon, geometry, Drive, the deployment or `main`.

## 17. What Phase 1 built [BUILT P1]

| Layer | File | Owns |
| --- | --- | --- |
| Engineering model | `src/wayfarer/cabin_air.py` (v2), `godot/scripts/systems/cabin_air.gd` | Physics and state transitions only: mode RUNNING / ISOLATED, fan OK / FAILED, spare NONE / BENCH / CARRIED / INSTALLED; one operation table (requires / sets), refusal reasons, component readings, time to the control limit from the present state. Knows no scenario. |
| Equipment | `godot/scripts/excursion/equipment.gd` | A small registry of equipment points (the ECLSS bay, the sector 2 workbench) bound to packaged nodes, the bay's board, the ship clock (scale, pause). |
| Scenario | `data/deadship/ds1_scrubber.toml`, `src/wayfarer/deadship.py`, `godot/scripts/deadship/scrubber.gd` | Start state and fault, eight steps whose completion reads the model's state or the player's actions, evidence pages, debrief, the watch. No engineering value: the loader refuses one. |
| Checks | `tests/test_cabin_air.py` (12), `tests/test_deadship.py` (4), `check_deadship.gd` (`deadship` runtime check), `check_player.gd` (shared with `check_systems.gd`), `tools/web_check.py --part training` | |

**The start is a model result.** The scenario injects `fault_fan` at the model's steady state (0.150 % with six people) and runs the
same exact step for 4.5 h before the trainee arrives, so the board shows **0.318 %, ABOVE TARGET, the control limit in 4.87 h ship time
from now** (about 9.7 min real at ×30). Wherever a time to a limit appears, its initial condition is stated: "from now, at the present
trend". The control limit is called an operational limit; the 0.8 kPa and 3.0 kPa bands are labelled reference levels and the
tutorial says that crossing 0.5 % is a procedure failure, not an injury.

**The eight steps** (each completes on engineering state or a player action, never on a timer):

| Step | Player | Completes when | Model call |
| --- | --- | --- | --- |
| 1 Recognize | reads the briefing (no cause given), walks to the bay | the trainee is at the bay | none |
| 2 Inspect | Use at the bay | the inspection page was opened | `diagnostics` |
| 3 Diagnose | reads supply, fan, bed and the conclusion (Use pages) | the conclusion page was read | `diagnostics` (supply ENERGIZED, controller SELF-TEST PASS, fan command ON at 0 % speed, flow 0 m³/h, bed NORMAL: the fan) |
| 4 Isolate | Ops at the bay | mode ISOLATED | `operate("isolate")`; repair while RUNNING is refused |
| 5 Retrieve | walks to the sector 2 workbench, Use takes the spare, walks back | spare CARRIED and at the bay | `operate("take_spare")` |
| 6 Repair | Use at the bay | fan OK (spare INSTALLED; unit ISOLATED_READY, "repaired, not restored") | `operate("install_spare")` |
| 7 Restore | Ops at the bay | RUNNING with fan OK | `operate("restore")`; refused while the fan is FAILED |
| 8 Verify | Ops: stability watch | the watch passes | the same step for 6 h ship time |

**States the trainee sees.** FAILED (RUNNING_NOT_REMOVING), ISOLATED with the fault (ISOLATED_FAULT), repaired but not restored
(ISOLATED_READY) and OPERATING, as separate words on the board and in the prompt.

**Watch.** 6 h of ship time with nobody touching the unit, on the same model, at ×1800 (12 s real). It passes when the unit is
removing, never passed the control limit during the watch, ends at or below the 0.3 % target and its steady state is at or below the
target. The reference replay ends at 0.205 % (steady 0.150 %). Unscored.

**Debrief.** What failed (the fan), which measurements found it (fan command ON with 0 % speed and 0 m³/h flow while supply, controller
and bed were normal), why isolation was needed (no fan replacement on an energized unit), what the replacement changed (the scrubbed
flow and the removal rate), why it is now stable (removal exceeds generation until the steady state, with its number).
Ops after the end replays the training from the same start. A run left past the control limit ends as an operational failure with
the tiers explained and a replay offer.

**Compartments (§5 of the brief).** **[HISTORICAL; superseded by Phase 2A, §23.]** Investigated: CIRC doors in ring A are normally CLOSED (`ring_circulation.doors`), and ring A has nine
compartments in a loop (three sectors and six corridor segments). A door-coupled gas model would need per-compartment volumes,
occupancy and a ventilation model that the canon does not hold. DS-1 does not need it: its lesson is a failed fan in a well-mixed ring.
The model keeps one volume under a stated PROTOTYPE assumption (intermodule ventilation mixes the ring; at a few hundred m³/h the local
excess over the ring average is roughly 0.05 to 0.1 % CO₂), and the walk claims no door effect. Compartment connectivity moves to
Phase 2, where DS-2 needs it. *(2026-11-14: Phase 2A computed it. In DS-1's configuration, doors shut and ventilation on, the
compartments settle between 0.150 % (sector 3, the unit's own) and 0.223 % (sector 2), 0.073 points above the well-mixed value: inside
the 0.05–0.1 % estimated here. DS-1 keeps the well-mixed model, §23.6.)*

**Time handling.** Ship time is a scenario multiplier (×30, the watch ×1800) on the CO₂ model only. Rings turn, the trainee walks and
doors move in real time (checked: during the watch the ring turned at its real rate). The clock stops while a tutorial page or the
controls overlay is open, and after the run ends; the board marks "(paused)".

**Interaction.** No new key. Use (`exc.use`) inspects, reads the next page, takes and fits the part; Ops (`exc.ops`) isolates,
restores, starts the watch and replays. Prompts and pages show the player's own bindings (`WfInput.label`), and the touch buttons carry
the same labels. A door within reach keeps Use when the trainee faces it more than the point. The learning station at the bay yields
to the training while it runs. The carried spare is a placeholder box on the trainee; no inventory.

**Preserved.** `#interior` (default start: no equipment, no Deadship), `#interior-systems` (the Phase 0 proof, now on the v2 model),
the walkthrough, Explore Exterior, movement, doors, ladders, learning stations; DOCKED, docking and the trunk are untouched.

## 18. Phase 2 prerequisites

**[HISTORICAL, 2026-11-13]** Item 2 was built as Phase 2A (§23); the rest moves to Phase 2B/2C (§24).

1. The owner reviews Phase 1 and the working assumptions (DS-O1, DS-O2 remain the volume, occupancy, rating and reference bands).
2. Compartment connectivity: per-compartment volumes from the built rooms, occupancy per compartment, door states and a stated
   ventilation exchange per open door and duct. This is DS-2's first modelling step.
3. Humidity and heat stocks next to CO₂ (DS-2 "Borrowed Air" trades between them), with PROTOTYPE capacities labelled.
4. Parts as entities beyond one spare: a small part list per unit, with conserved counts, still without a general inventory.
5. Ring B and the trunk as a second volume, if DS-2 crosses rings.
6. Provisional scoring only after the owner confirms DS-Q3's weights; browser-local only (DS-Q6).

## 19. Validation (Phase 1) [BUILT P1]

**Python reference** (`tests/test_cabin_air.py` 12, `tests/test_deadship.py` 4): rated crew held at the target; the step is exact and
independent of the step length (7.5 s, 60 s and 300 s against 1 s); the mass ledger closes; a failed fan removes nothing even while
RUNNING; isolation repairs nothing; repair needs isolation and the carried spare (NONE, BENCH and INSTALLED refused); a restored unit
returns to a stable steady state (96 × 1800 s, monotonic); every refused operation leaves the state untouched and has a stated reason;
the time to the control limit counts from the present state (including the case where removal cannot hold 24 people); bands ordered.
The scenario: owns no engineering value (a fixture with `co2_max` is refused); the trainee's start is the model's result
(steady + 4.5 h × G = 0.318 %, RUNNING_NOT_REMOVING, between target and limit); the reference replay (isolate, take, install, restore)
passes the watch at 0.205 % and is deterministic; an unrepaired ring fails the watch.

**Python and Godot agree.** `WfCabinAir.verify()` replays the packaged 10 h proof (41 checkpoints, 11 events with their expected
outcomes, refusals unchanged) within 1e-9 relative + 1e-9 kg; `WfDeadship` replays the scenario reference against the packaged
Python result before it starts. In the play-through: the restored mass after 150 ship s, 2.77073302456862 kg against the closed form
2.77073302456864 kg; the watch end 0.00209298480231069 against 0.00209298480231071 (CO₂ fraction); the watch ran exactly 6.0 ship h.

**Runtime check `deadship`** (headless, `--fixed-fps 60`): PASS, about 20,100 physics frames. It plays all eight steps through the
scene's Use and Ops; checks the start, the refusal of a restore with the failed fan (state unchanged), the carry, each status word, the
restore exponential, the watch, the debrief contents, the ledger, the pause while a page is open, the touch buttons and prompt labels
naming the player's keys; that the ring turned at its real rate (0.418878 rad/s) during the ×1800 watch; replay from the same start;
and a run left past the limit ending as an operational failure. `systems`: PASS on the v2 model.
`runtime-export`: 10 of 10 checks PASS (check, check-docked, route, excursion, eva-ops, locomotion, systems, deadship, controls,
characters); 5,287 objects and 1,351,125 triangles, unchanged.

**Browser (Google Chrome for Testing 153, headless, software WebGL), real input.** `web_check.py --part training` on the Phase 1
site. The check walks the trainee by script; every action is the player's own input: the key the page publishes for that action
(`window.wayfarerControls.keys`: E for Use, O for Ops), or on an emulated phone (844 × 390, touch) a tap on the on-screen button.

| Training | Input | Result | Actions answered | Physics frames | Wall s |
| --- | --- | --- | --- | --- | --- |
| `#interior-systems` | keys | PASS | 2 (Ops isolate, Ops restore) | 8,713 | 411 |
| `#interior-systems` | touch | PASS | 2 | 8,693 | 321 |
| `#interior-deadship` | keys | PASS | 13 (inspect, 4 readings, close, isolate, refused restore, take spare, install, restore, watch, replay) | 20,797 | 683 |
| `#interior-deadship` | touch | PASS | 13 | 20,938 | 586 |

What this does not prove: the walking itself is scripted (movement keys were tested by the main part's walk); the browser frame
rate is software WebGL, not a player's GPU.

**Phase 0 browser gap (brief §2).** The 6d0f8f2 build could not be driven in a browser: its web shell passes only listed check
arguments, and `--systems` / `--check-systems` were not listed, so the check never started (a visitor's `#interior-systems` start
itself needs no argument). Fixed in isolation in `web/play/shell.html` (the five training arguments listed). Phase 0's behaviour was
then verified in the browser on the Phase 1 build, where `#interior-systems` runs the Phase 0 proof on the v2 model (table above).

## 20. Regression (Phase 1)

| Area | How | Result |
| --- | --- | --- |
| All Python tests | `unittest discover -s tests` | 244 tests OK (1 skipped) |
| Godot runtime checks | `runtime-export` (10 checks incl. excursion, eva-ops, locomotion, controls, characters) | 10/10 PASS |
| Default interior and exterior, viewer, start page, controls setup, switching, phone | `web_check.py --part main` | 67/67 PASS (same count as Phase 0) |
| `#interior` free of Deadship | the scene creates Deadship only for `#interior-deadship` / `--deadship` (excursion.gd), equipment only for those and `#interior-systems` | by construction, and the default walk checks above |
| Geometry | none changed; the runtime export's object and triangle counts unchanged | unchanged |

## 21. Handoff (Phase 1)

**H1. Implemented.** The playable DS-1 tutorial at `#interior-deadship` (A); the model extension, independent mode / fan / spare
with an operation table and refusals (B); the component interaction, Use and Ops at the bay and the bench, one carried part (C); the
scenario definition in `data/deadship/` with its loader and reference (D); this report (E); validation (F, section 19); stills of the
five moments (G, project Library `deadship_phase1_2026-11-13/`).

**H2. Reused.** The walk, its doors, CIRC routing and learning-station conventions; `WfInput` Use / Ops with the player's bindings and
the touch buttons; the Phase 0 reference-and-checkpoint pattern; the learning panel style; `check.gd`'s walking for the checks.

**H3. Prototype or unresolved.** The 466 m³ well-mixed ring (ventilation assumed), six occupants, 295 K, the unit rated for twelve,
the 0.8 / 3.0 kPa reference bands, the 4.5 h fault lead, the ×30 and ×1800 scales, the 6 h watch, the bench location, the spare's
placeholder box. Medical limits, ECLSS technology and serviceable parts stay OPEN in canon.

**H4. Deferred, and why.** Compartment connectivity and door-coupled air (DS-1 does not need it; the canon holds no compartment
ventilation model; DS-2 does need it); humidity, heat, power; parts beyond one spare; scoring (unscored by brief); persistence of runs
(none needed for a replayable tutorial); a proper spare-fan model; Phase 2.

**H5. Walkthrough intact.** The default start and `#interior-systems` behave as before (sections 19 and 20); Deadship exists only on
its own start; no binding, profile or setup row changed (two action descriptions name Deadship).

**H6. Playable in the browser.** Yes: `#interior-deadship` on the play page, desktop and phone, as tested (section 19). Known rough
edge: on a phone the training panel covers part of the HUD while a page is open. *(Fixed 2026-11-14, §22.1.)*

**H7. Phase 2 readiness.** Ready for design review: the model's operation table, refusals and reference replay extend to new
components; the scenario layer holds steps and texts only. Prerequisites in section 18; the first is compartment connectivity.

---

# Phase 1 finalization and Phase 2A (2026-11-14)

The owner's brief of 2026-11-14 asked for two packages: finish Phase 1 (phone layout, this document, a usability review) and build
Phase 2A, atmospheric connectivity. Phase 2B and the full "Borrowed Air" scenario were not authorized and were not started. The working
assumptions of 2026-11-13 stand as **prototype assumptions, not canon**: 466 m³, six occupants, 295 K, a unit rated for twelve, the
0.5 % WORKING control limit, the 0.8 kPa and 3.0 kPa PROTOTYPE reference bands.

## 22. Phase 1 finalization [BUILT P1]

### 22.1 Phone layout

**The defect.** On a phone the training page took the desktop's right column at desktop type, so it lay over the HUD's goal and
prompt and could cover the touch buttons.

**The fix: one layout rule for every page** (`godot/scripts/excursion/page_panel.gd`, `WfPagePanel`), used by DS-1 and the learning
stations alike. No separate mobile page or component.
- Desktop keeps the right column and its type (15/16 px).
- On a touch-first device (`WfInput.compact`) the page takes the **free band**: below the page's top row (Exit, Full screen, Map, ?),
  above the lowest controls (the touch buttons and the stick's circle), the full width inside the safe area (CSS
  `env(safe-area-inset-*)`, as the touch layer already reads it). The type steps down 13/14 → 12/13 → 11/12 px until the text fits.
- While a page is open on a phone, the goal, prompt and map step aside (the page names the step and the next action; the buttons carry
  the actions). They come back on the next frame after the page closes. The player's own Map choice is kept.
- In compact form the DS-1 page puts "step k of 8 · title" in its header, drops the tab row and blank lines, and shortens the footer.
- The map now sits under the touch utility row. On an upright phone that row drops below the page's Exit row, and the map used to lie
  under the Map and ? buttons (a defect older than Phase 1; fixed here because it is the same screen).
- The pause rule is unchanged: ship time stops while a page or the controls overlay is open.

Also fixed: on an upright phone the bay's 3D status board above the bay showed through the page and crossed its first lines; the page's
background is now 94 % opaque (was 86 %), on every screen. And the compact footer printed "0.5 %% limit" (a format string shown without formatting).

### 22.2 Usability review

**Method.** A reading of the scenario, the code paths and the stills of every step (desktop 1280 × 720; phone 844 × 390 and
390 × 844), plus the scripted play-throughs of §22.3. **This is not a human playtest.** The walking is scripted, and the browser
runs press the player's real key or tap the real button only at the action points. The owner's playtest (§22.4) is still to come.

| Point | Finding | Action |
| --- | --- | --- |
| Objective | The goal line names the step (k of 8), its title and objective; the briefing gives the symptom, not the cause | None |
| Finding the ECLSS bay | Text only: the goal names "the sector 3 ECLSS bay" and the map labels A1–A3, but nothing marked the bay itself | **Fixed:** amber marks on the map's rim for the bay ("ECLSS") and the workbench ("bench"), read from the equipment points |
| Workbench discoverability | The bench is a real fit-out node in sector 2 with the spare's placeholder box on it; the map gave no hint | **Fixed** by the same map mark (stills of the map show it). A still of the bench itself was attempted and not usable (the camera framing in the sector 2 fit-out); the owner checklist covers it |
| Prompts | Every prompt names the player's own binding as a key chip; touch buttons carry the same words; a door in reach keeps Use when the trainee faces it | None |
| Component states | FAILED (running, removal 0), ISOLATED with the fault, repaired not restored, OPERATING: four words on the board and in the prompt | None |
| Diagnosis from evidence | Four pages (supply, fan, bed, conclusion) give the readings with numbers before the conclusion names the fan. The trainee cannot choose wrongly, which suits a tutorial; DS-2 should make the diagnosis a choice | Noted for 2B |
| Refusals | Every refusal is the model's stated reason (restore with a failed fan, repair while energized, a second spare) | None |
| Carried spare | **Defect:** the box hung at waist height, about 53° under the eye line, outside the 75° first-person view; the trainee could not see what they carried | **Fixed:** carried at chest height (about 34° under the eyes) and the goal line adds "Carrying: the spare fan". Verified geometrically, not visually: the `deadship` check asserts the carried box lies inside the first-person view when the trainee looks level (33.7° under the eye line against a 37.5° half-angle, 3° kept as margin). **[HISTORICAL]** That measure used a wrong eye height; the spare was in fact above the head. Corrected 2026-11-14 (§26.1) |
| Watch and debrief | The watch runs 12 s real with the board ticking; the debrief explains what failed, how it was found, why isolation, what changed, why stable | None |
| Replay | Ops at the bay after the end replays from the same start; the goal line says so | None |
| Bay board on an upright phone | Standing at the bay, the 3D status board (a billboard above the bay, world text) is large on a narrow screen and crosses the Map and ? buttons and the map. Buttons stay tappable (they are drawn above it) **Resolved (DS-O10, §26.1):** the board is now a tilted instrument panel fixed to the bay's top edge |
| Phone | Page over the HUD; map under the Map and ? buttons on an upright phone; "%%" in the footer | **Fixed** (§22.1) |

### 22.3 Validation (Phase 1 finalization)

What ran, with its result. Nothing here is a human playtest.

| Check | Result |
| --- | --- |
| Python tests (whole suite) | 258 OK, 1 skipped |
| `runtime-export` (rebuild, all Godot checks, publication) | 11/11 PASS; 5,287 objects, 1,351,125 triangles, unchanged |
| `runtime-check auto` after the last Godot edit | 6/6 PASS against the current package |
| `deadship` Godot check: the carried spare inside the view | PASS (33.7° under the eye line, half-angle 37.5°) |
| Native renders, DS-1 steps 1–5: desktop 1280 × 720, phone 844 × 390 and 390 × 844 with touch | Rendered and read; page in the free band, no touch button covered, HUD back after closing |
| Browser `--part main` (site, viewer, launchers, controls, Explore Interior and Exterior, phone) | 67/67 PASS |
| Browser, DS-1 by the player's own keys | PASS: 13 actions, 569 s (final build) |
| Browser, DS-1 by on-screen buttons, phone in landscape | PASS: 13 actions, 506 s (final build) |
| Browser, DS-1 by on-screen buttons, phone turned upright after the 3rd action | PASS on the rerun: 13 actions plus the turn and the "Continue upright" tap, 485 s, every tap on the button showing the awaited label |
| Browser, learning station (`systems`), keys and touch | PASS both |

**The rotated phone, first attempt.** It failed: after the phone turned upright, the web shell's own "Turn your phone sideways"
prompt (with "Continue upright") covered the canvas, and the check kept tapping the game's buttons underneath it. The prompt is the
shell's intended behaviour, older than Phase 1, so the game was not changed. The check now answers it as a person would, with a tap on
"Continue upright", and it waits for the button that shows the awaited label (the touch probe publishes every 0.25 s, so a label could
lag one action). The rerun is the row above.

### 22.4 Owner playtest checklist

For ApeDevil, on a real desktop and a real phone (the branch build; nothing is deployed). Tick, or note what happened.

**DS-1 `#interior-deadship`, desktop**
1. [ ] The briefing makes clear what is wrong (CO₂ rising) without telling you the cause.
2. [ ] You find the sector 3 ECLSS bay from the goal line and the map's amber "ECLSS" mark, without help.
3. [ ] Use at the bay opens the inspection; the four evidence pages read as evidence, and you could name the failed part before the
   conclusion page.
4. [ ] Trying Ops to restore before the repair is refused with a reason you understand.
5. [ ] Ops isolates; the board's state word changes to ISOLATED.
6. [ ] You find the sector 2 workbench (map mark "bench"), see the spare on it, take it, and **can see it in your hands** walking
   back.
7. [ ] Use fits the spare; the board says repaired but not restored; Ops restores; the CO₂ trend turns negative.
8. [ ] The stability watch and the debrief are clear; Ops after the end replays the training.
9. [ ] Nothing felt like a timer you could not see; the pause while a page is open feels right.

**DS-1 on a phone (landscape, then upright)**
10. [ ] An open page leaves every touch button visible and tappable, and its text is complete (nothing cut off), in both
    orientations.
11. [ ] Closing the page brings the goal line, prompt and map back.
12. [ ] Turning the phone with a page open re-lays the page without losing your place.
13. [ ] On an upright phone the map no longer covers the Map and ? buttons.

**Phase 2A `#interior-airflow`**
14. [ ] The map's compartment colours and numbers are readable; the bulkhead marks (green door, blue duct, red none) make sense.
15. [ ] Walk to the bay with ventilation on: closing doors behind you changes nothing (the ducts still join the compartments).
16. [ ] Ops at the bay turns ventilation off; compartments behind closed doors show "isolated" on the board and red bulkhead marks.
17. [ ] Opening a door joins two compartments and their numbers move toward each other over tens of seconds, not instantly.
18. [ ] The labels (SIMULATION, PROTOTYPE exchange) are visible enough that nobody takes the numbers for canon.

**Everywhere**
19. [ ] `#interior` (the default) and Explore Exterior look and play as before.

## 23. Phase 2A: atmospheric connectivity [BUILT P2A]

### 23.1 Topology audit (ring A)

**Principle.** The layout defines the volumes, doors and hatches the connections, ventilation the mechanical exchange. Every number below
comes from an existing module; none is new canon.

| Node | Location | Volume used (m³) | Basis and source | Status | Doors | Ventilation | Unknowns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Ring A sector 1 | 37.73 | net (deck to overhead less modelled fit-out; subfloor 14.46 m³ not counted): `pressure_volumes.rooms` Sector_1_1 (gross 72.38) | PROTOTYPE | CIRC.A1P → AC1a, CIRC.A1N → AC3b; tube hatch TUBE.A1 (closed) | IMV pairs at A1P and A1N | Fit-out is whitebox; real free volume OPEN |
| A2 | Ring A sector 2 | 44.19 | net, Sector_1_2 | PROTOTYPE | CIRC.A2N ← AC1b, CIRC.A2P → AC2a; TUBE.A2 | IMV at A2N, A2P | as A1 |
| A3 | Ring A sector 3 (ECLSS bay) | 45.96 | net, Sector_1_3 | PROTOTYPE | CIRC.A3N ← AC2b, CIRC.A3P → AC3a; TUBE.A3 | IMV at A3N, A3P | as A1 |
| AC1a, AC1b | Fill 1 corridor, either side of the spoke-node bulkhead | 56.41 each | gross clear cavity: `ring_circulation.compartments` (CIRC-001) | PROTOTYPE (CIRC-001 is an owner design direction, not canon) | AC1a: A1P, AC1; AC1b: AC1, A2N | IMV at each door | Utility-zone fill of the cavity |
| AC2a, AC2b | Fill 2 corridor | 56.41 each | as AC1 | PROTOTYPE | A2P, AC2 / AC2, A3N | as AC1 | as AC1 |
| AC3a, AC3b | Fill 3 corridor | 56.41 each | as AC1 | PROTOTYPE | A3P, AC3 / AC3, A1N | as AC1 | as AC1 |
| *Crew_Tube_1_1..3* | Sector overhead hatch to the despun vestibule | 49.04 each | `pressure_volumes.rooms` (gross) | **Outside the model** | TUBE_HATCH at the sector, DRUM_DOOR at the vestibule (`crew_transfer`) | none known | Hatch states in operation; the walk does not animate them |
| *Crew_Vestibule_1* | Despun drum | 15.85 | gross | **Outside** | the three tube doors; the trunk port gate | none known | Whether it joins rings A and B in normal operation |

**Doors.** Nine CIRC pressure doors form **one loop** round the ring: sector → corridor half → node bulkhead → corridor half → next
sector. Each is 0.75 × 2.0 m, normally CLOSED (PROTOTYPE, `ring_circulation.doors`), sliding into a pocket. A closed door is a pressure
boundary; a closed loop door does not isolate a compartment while the other way round is open (case B).

**Ventilation.** None is in canon: `life_support.toml` holds no air flows, and the only duct-like item in the model is the DS-06/08
duct-crawler door on the ECLSS bay (a drone dock, not air). The visual ducts in the corridors are greybox. Phase 2A therefore
assumes one intermodule-ventilation (IMV) duct pair per bulkhead (DS-O7, PROTOTYPE).

**Double counting.** None. The nine nodes sum to **466.36 m³**, exactly SYS-001's volume: three sectors' net 127.88 m³ and six corridor
halves' gross 338.48 m³ (= `ring_circulation.budget` corridor gross per ring). No room is in two nodes; the tubes and vestibule are in
none. The mix of bases (sectors net, corridors gross) is kept from SYS-001. It is suitable as a model assumption: the corridors' fit-out
is not modelled, so their net free volume is unknown, and the sector subfloor is excluded because its ventilation is unknown. **It is a
model assumption, not a finalized ventilation design.**

**The 466 m³ basis is still the right well-mixed total** for DS-1: it is what the nine compartments hold together when the ventilation
joins them. With every door shut and the ventilation off, the volume a compartment's occupants breathe is that compartment alone
(37.7–56.4 m³), and that is what Phase 2A now models.

**Ring B** has the same structure (B1–B3, BC1a–BC3b, nine CIRC doors) and is not modelled; nothing in Phase 2A crosses rings. **Godot
door state:** `excursion.gd` `circ_doors[id]` holds `value` (0 seated … 1 open) and `target`; the leaf and its collider follow
`value`. `_toggle_door` refuses a close while the doorway is occupied, leaving `target` unchanged.

### 23.2 The model [BUILT P2A, ENG]

`src/wayfarer/ring_air.py` (SYS-002, `WF_RING_AIR` v1). An engineering state with no game logic: consumers set connections
(`set_edge`, `set_vent`), removal and occupants, and read `readout`.

**Graph.** Nodes: the nine compartments above, each with V, its CO₂ mass m_i, fraction x_i = (m_i/M)/n_i, partial pressure x_i·P,
occupants and trend. Edges: 9 doors (state from the walk) and 9 IMV duct pairs (state = ventilation ON and damper OPEN). Boundaries:
three tube hatches, CLOSED, unmodelled.

**Equation.** dm_i/dt = G_i − [i = r]·k·m_i/V_i + Σ_j C_ij·(m_j/V_j − m_i/V_i), with G_i = occupants_i × 1.0 kg/day (41!B15, STUDY), k the
unit's scrubbed flow (SYS-001: 116 m³/h, rated for twelve at the target) drawing from sector 3 only, and C_ij the exchange flow of every
open edge between i and j.

**Connectivity is not mixing.** An open edge carries a finite flow. The exchange time V/C of one compartment through one door is
0.27–0.41 h, through one duct pair 0.16–0.24 h, and a pulse that has to go the long way round (eight doors) needs hours (test B).

**Exchange values (all PROTOTYPE, configurable in `ring_air.PROTOTYPE`, SI units).**

| Edge | Value | Basis |
| --- | --- | --- |
| Open door | 0.0387 m³/s (139 m³/h) each way | Two-way buoyant doorway exchange Q = (C_d/3)·W·H·√(g·H·ΔT/T), C_d 0.6, W 0.75 m, H 2.0 m, g = ring A floor gravity, ΔT 0.5 K, T 295 K. A floor: cabin fans and people walking through add to it |
| IMV duct pair | 0.066 m³/s (238 m³/h) each way | The order of a spacecraft intermodule-ventilation fan (about 140 cfm); runs only with ventilation ON and the damper OPEN |
| Closed door or damper | 0 | Sealed; no leakage path (PROTOTYPE) |

**Why no pressure state.** Every exchange is balanced (a doorway's two-way flow, a duct pair's supply and return), so no compartment
gains or loses gas in total: n_i = P·V_i/(R·T) stays fixed and CO₂ is carried as a trace (below 1 %). Forced flow (the ducts, ON/OFF)
is distinct from passive exchange (an open door). No O₂, humidity, heat, fire or pressure loss is modelled.

**The exact step.** The system is linear with constant coefficients between changes, so y(t+Δt) = exp(A·Δt)·y(t) on
y = [m_1 … m_9, generated, removed, 1]. The generated and removed totals are integrated **inside the same exponential**, independently of
the masses, so the ledger initial + generated − removed = final is a real check of the step, not a definition. exp is scaling and squaring
of an 18-term Taylor series after halving to a norm ≤ 0.5 (truncation below 1e-22), written so that Godot repeats it operation for
operation. One propagator per (configuration, Δt) is cached; a change of a door, the ventilation, removal or occupants clears it. The
step is exact for any Δt: 1 s, 10 s, 600 s and 3600 s steps agree to 1e-10 relative.

**Reference run** (11 hourly checkpoints, 10 h at the runtime's 10 s step): from the well-mixed state with doors closed and ventilation on
(case C); ventilation off at 0.5 h (D: nine groups); A2N opens at 2 h (E: eight groups); at 4 h every door but AC1 opens (B: one group
the long way round); at 6 h all six occupants move to A1 (F); at 8 h the ventilation returns. End: 2.5000 kg generated, 1.9526 kg removed,
ledger closed to 1e-12 relative.

**Steady states** (two per sector, unit in A3; CO₂ %):

| Configuration | A1 | A2 | A3 | Corridors | Ring mean |
| --- | --- | --- | --- | --- | --- |
| Well-mixed (SYS-001, DS-1) | 0.150 | 0.150 | 0.150 | 0.150 | 0.150 |
| Doors closed, ventilation on (the walk's normal state) | 0.223 | 0.223 | 0.150 | 0.174–0.223 | 0.198 |
| All doors open, ventilation on | 0.196 | 0.196 | 0.150 | 0.165–0.196 | 0.180 |
| All doors open, ventilation off | 0.275 | 0.275 | 0.150 | 0.192–0.275 | 0.232 |
| Six in A1, ventilation on, doors closed | 0.297 | 0.223 | 0.150 | 0.174–0.272 | 0.222 |
| Doors closed, ventilation off | rises 0.154 %/h | rises 0.131 %/h | 0.050 | unchanged | — |

The unit's compartment always settles at the well-mixed value G/k (removal equals generation), and every other compartment sits above it.
Isolated with two people, sector 1 climbs from 0.15 % to the 0.5 % control limit in **2.3 h**, sector 2 in 2.7 h; six people sealed
in sector 1 reach it in **0.76 h**. In a well-mixed ring with the unit off the same climb takes about 5.4 h (§7.2).

### 23.3 Godot integration [BUILT P2A]

- `godot/scripts/systems/ring_air.gd` (`WfRingAir`): the runtime copy. It loads `wf_ring_air.json`, replays the packaged reference run
  and compares all 11 checkpoints (nine masses, the two ledger sums, the number of groups) within 1e-9 relative + 1e-12 kg before
  anything is shown (`verify()`). It is testable without 3D: the `airflow` check's determinism part runs fresh copies with no scene.
- `godot/scripts/excursion/airflow.gd` (`WfAirflow`, a `WfEquipment`): the consumer. Every frame it reads the walk's nine ring A door
  leaves (`circ_doors[id].value > 0`: the leaf off its seat passes air) and passes them to the model. **There is no second door state**:
  the walk owns the doors (animation, collision, controls unchanged), the model is told. A refused door operation (the doorway occupied)
  leaves `target` and `value` unchanged, so the model sees nothing. A door that is moving counts as open until its leaf seats.
- Ship time runs ×120 in fixed 10 s model steps (the reference's step) with an accumulator.
- `excursion.gd` changed by three hooks only: the start branch, the goal line (`equipment.goal_text()`, empty for the other starts) and
  the check. Ops, the prompt, the touch button and the page record go through the existing equipment hooks.
- **Visualization** (minimal, all read from the model): the ring map colours each compartment's arc by its CO₂ (teal → yellow at the
  0.3 % target → orange → red at the 0.5 % limit) with its value, and marks every bulkhead with what joins its two sides now: green an
  open door, blue a running duct pair, red nothing. The caption gives the ventilation state and the number of groups; the header says
  SIMULATION, PROTOTYPE. The bay's board lists the nine compartments with "isolated" where true, the ventilation state, the open doors
  and the groups.

### 23.4 The demo `#interior-airflow` (`-- --airflow`) [BUILT P2A]

An opt-in start like `#interior-systems`; the default `#interior` and DS-1 never create it. The ring starts in its normal state:
doors closed, ventilation on, one group, two people per sector, the unit running in sector 3. The goal line explains the map and the two
controls. **One new interaction, no new binding:** Ops at the ECLSS bay switches the ring's ventilation off or on (the existing Ops key
and touch button; prompt "ventilation off / on"). Doors are opened and closed with Use as always.

What the player can observe: with ventilation on, closing doors changes nothing (the ducts join every compartment). Switch it off and
every compartment behind closed doors becomes isolated: the occupied sectors climb, the empty corridors freeze, the unit's sector falls,
and the map shows red bulkheads. Open a door and the two compartments' numbers drift toward each other over tens of seconds of real time
(minutes of ship time). Open the whole loop and everything joins again, more slowly than through the ducts.

### 23.5 Validation (Phase 2A)

| Check | Result |
| --- | --- |
| `tests/test_ring_air.py` (14 tests) | OK. Volumes sum to DS-1's 466.36 m³ with no double counting; one loop of nine doors; the doorway formula; the step exact for any length; conservation and non-negativity on the reference run and from zero CO₂ |
| Case A, fully connected | Settles where removal balances generation; max 0.196 % with ventilation on, 0.275 % with it off |
| Case B, a closed door with the other way round open | Still one group; the two sides converge the long way |
| Case C, closed doors, ventilation on | Still exchange through the ducts; one group; A3 0.150 %, A1/A2 0.223 % |
| Case D, closed doors, ventilation off | Nine isolated compartments; sealed corridors stay bit-exact; A1 reaches 0.5 % in 2.3 h, A2 in 2.7 h |
| Case E, a door reopened | The two compartments join gradually, never in one step |
| Case F, occupants apart | A gradient along the path; six people sealed in A1 reach 0.5 % in 0.76 h |
| Case G, removal elsewhere | Removal in A3 lowers another compartment only through a connection |
| Ledger (generated − removed − change in stored CO₂) | About 5e-14 kg on the reference run; tolerance 1e-9 relative + 1e-12 kg |
| Python ↔ GDScript parity | 11 hourly checkpoints over 3,600 steps of 10 s, within the tolerance (`WfRingAir.verify()`) |
| `airflow` Godot check in the walk | PASS: ventilation off after six doors opened gives 3 groups; sealed corridor bit-exact; reopening gradual; a refused close changes nothing |
| Browser `#interior-airflow`, player's keys / on-screen buttons | PASS (4 actions, 452 s) / PASS (4 actions, 389 s) |
| Desktop stills | Connected, isolated and reconnected states rendered and read |
| DS-1 regression | `cabin_air` and `deadship` tests unchanged and OK; the DS-1 browser runs above PASS |

**Play download budget.** The first site build of Phase 2A went 21.6 kB over the 90,000,000-byte play budget
(`tools/web_export.py`). Fixed without dropping anything the runtime reads: the three model packages are written as compact JSON, the
ring reference keeps hourly checkpoints (11, was 61) and gives its sources once. 25 kB saved, 3.4 kB margin. The values are unchanged.

### 23.6 DS-1 is protected

DS-1 runs on `cabin_air` exactly as before: one well-mixed 466 m³ volume (its documented configuration: ventilation on). Its physics, scenario and
reference are unchanged: `cabin_air.py` and `deadship.py` changed only in how their packages are written (compact JSON, to fit the
play download budget, §23.5), and their checkpoints and reference replay hold the same values. **The difference, reported, not bent:** in DS-1's configuration the compartment model's steady state is 0.150 %
in sector 3 and up to 0.223 % in sectors 1 and 2 (ring mean 0.198 %), against the well-mixed 0.150 %. DS-1's lesson (a failed fan
stops removal; isolate, repair, restore) holds in both models. Its numbers are the well-mixed ring's, and its debrief says so.

### 23.7 Limitations [ENG]

- Every exchange value is PROTOTYPE. The doorway formula is a floor (pure buoyancy at ΔT 0.5 K); people walking and cabin fans mix more.
  The IMV flow is an order of magnitude from spacecraft practice, not a Wayfarer design.
- Each compartment is well mixed inside. The local excess near a breathing person, and stratification, are not modelled.
- No leakage, no pressure difference, no O₂, humidity, heat, fire or contamination. Total gas per compartment is fixed.
- The crew-tube hatches are held closed and unmodelled; the tubes are a real second path in the ship.
- Ring B, the trunk and the vestibule are outside the model.
- Occupants are numbers per compartment, not the walking trainee; the trainee's own breath is not added.
- The demo's ×120 clock and the 10 s model step are display choices; the step itself is exact for any length.

## 24. DS-2 reassessed and the Phase 2B proposal [HISTORICAL; superseded by §27]

> **[HISTORICAL]** Written before the Phase 2B gate. §27 tests this proposal: the strategy search shows that moving everyone to
> sector 3 dominates every other choice, and the "crowded" and "leak" costs in the table are not computed by any model. Kept as
> written; do not build from it.

**What Phase 2A changes for "Borrowed Air".** DS-2 as designed (§5.8) trades two interacting problems with insufficient parts and
needs humidity and heat stocks, parts as entities and perhaps two rings. That is still an M–L step. Phase 2A already supplies the
mechanism a first real choice needs: where the crew is, which doors stand open and whether the ducts run decide who breathes what,
computed and conserved. Recommendation: build a **smaller playable milestone first, Phase 2B "You cannot save everything"**, on
SYS-002 alone, and keep humidity, heat and parts for 2C.

**Phase 2B premise (all scenario values PROTOTYPE; no canon event invented).** Ring A's intermodule fans have failed and no spare is
aboard (ventilation OFF for the scenario). A slow leak is suspected in fill 2, so its doors (A2P, AC2, A3N) are held shut by
procedure. Two crew per sector; the unit in sector 3 works. Every number below is the model's steady state (`ring_air`, CO₂ %):

| Choice | A1 | A2 | A3 | Cost |
| --- | --- | --- | --- | --- |
| Keep everyone in place, open the rest of the loop | 0.400 | **0.525** (above the control limit, slowly) | 0.150 | Sector 2's air has to go the long way round through six doors; it cannot reach the unit fast enough |
| Move sector 2's two people to sector 1 | 0.400 | 0.400 | 0.150 | Sector 1 crowded (4 in 37.7 m³ net); everyone below the limit, above the target |
| Move them to sector 3 | 0.275 | 0.275 | 0.150 | The ECLSS sector crowded (4 people); everyone below the target |
| Open fill 2 as well | 0.275 | 0.275 | 0.150 | Breaks the leak isolation: the cost is a procedure the model does not score |
| Keep the doors shut | climbs 0.154 %/h | climbs 0.131 %/h | 0.050 | Sectors 1 and 2 reach the control limit in 2.3 h and 2.7 h |

No choice keeps everything: quarters, leak isolation and air quality cannot all be held. The player decides with the map and the board,
and the watch shows the consequence. The model needs **no new physics**: occupants per compartment (`set_occupants`) already exist. 2B
would add a scenario file (`data/deadship/ds2a_*.toml`, as DS-1), the "move crew" action (Use at a sector's crew point, or a choice on
the page), a door held by procedure (a refusal with its reason), the watch on the compartment model, and an unscored debrief that names
the trade made. Size M. **Prerequisite: the owner's authorization and review of Phase 2A's PROTOTYPE ventilation and doorway values.**

**Phase 2C "Borrowed Air"** then adds humidity and heat stocks (PROTOTYPE capacities), parts as entities, and the provisional scoring
after DS-Q3's weights; ring B through the trunk only if the scenario crosses rings.

**Revised roadmap after 2A:** 2B "You cannot save everything" (M, SYS-002 only) → 2C "Borrowed Air" (M–L) → 3 broader systems (power,
thermal) → 4 competitive and Hullrun → 5 narrative. Phase 2B requires separate authorization.

**Canon gaps the owner could close** (each would replace a PROTOTYPE value, none blocks the demo): ring ventilation architecture and flow
(DS-O7); the crew-tube hatch rule in normal operation (DS-O8); the corridor fit-out (net volume); ECLSS technology and its serviceable
parts (12!G26:G27); medical CO₂ limits (12!G22).

## 25. Handoff (Phase 1 finalization and Phase 2A)

1. **Implemented.** Phase 1 finalization: one page layout for every screen (`WfPagePanel`); the HUD steps aside on a phone and
   returns; the map clear of the touch row; the carried spare visible; bay and bench marks on the map; the footer fix. Phase 2A: ring A's
   air by compartment (`ring_air.py`, `ring_air.gd`), the walk's doors as its connections (`airflow.gd`), the ventilation switch at the
   bay, the map's air layer and the bay's board, the `#interior-airflow` demo, its runtime and browser checks.
2. **Reused.** The CIRC compartments and doors (`ring_circulation`), the room volumes (`pressure_volumes`), SYS-001's parameters
   (`cabin_air.params`: pressure, CO₂ rate, k, temperature), the reference-and-checkpoint pattern, `WfEquipment` (the bay point, board,
   Ops, prompt, touch button, record), the walk's door mechanism unchanged, the ring map, `WfCheckPlayer`, `web_check.py --part training`.
3. **Prototype or unresolved.** The doorway exchange (C_d 0.6, ΔT 0.5 K), the IMV duct pair and its 0.066 m³/s, dampers, the occupants'
   places (two per sector), the removal drawing from sector 3 only, the closed tube hatches, no leakage, the ×120 demo clock. Canon gaps:
   §24.
4. **Validated.** §22.3 and §23.5: Python cases A–G and conservation, Python/Godot parity at 11 checkpoints over 3,600 steps, the door truth in the
   walk, the runtime checks, the browser runs with real keys, touch and a rotated phone, regression.
5. **Not validated.** No human playtest (the checklist in §22.4 is for the owner); real phones and GPUs (software WebGL only);
   performance on a slow device (the model costs one 12 × 12 matrix-vector product per 10 s ship step, about 12 a second at ×120); the
   physical exchange values themselves.
6. **DS-1 unchanged.** It runs on the well-mixed `cabin_air` as documented; the compartment model's difference is reported in §23.6,
   not applied.
7. **Default start unchanged.** `#interior`, `#interior-systems`, `#interior-deadship` and Explore Exterior create no air model.
8. **Commits.** Phase 1 finalization, Phase 2A and this report are separate commits on `claude/project-thread-dfyyv7`, pushed; not
   squashed, not merged, not deployed. No Drive write, no canon change, no geometry or Blender asset change.
9. **Next step proposed.** Phase 2B "You cannot save everything" (§24), on SYS-002 alone, after the owner's review of Phase 2A's
   PROTOTYPE values. Not authorized; not started.
10. **Owner questions.** Accept the Phase 1 finalization and Phase 2A? Keep the IMV duct-pair assumption and the doorway floor (DS-O7)?
    Hold the crew-tube hatches closed (DS-O8)? Authorize Phase 2B?

---

# Phase 2A finalization and the Phase 2B gate (2026-11-14, second brief)

The owner's decisions of 2026-11-14: DS-O7 keeps the PROTOTYPE ventilation and doorway values (238 m³/h, 139 m³/h, 9 compartments,
466.36 m³), not canon and configurable; DS-O8 keeps the crew-tube hatches closed and outside the model; DS-O1 and DS-O2 stay as
approved. Phase 2B was authorized subject to the engineering gate of §27.

## 26. Phase 2A finalization [BUILT P2A]

### 26.1 DS-O10: the bay's display

**Problem.** The bay's status text was a billboard 0.35 m above the bay, with capitals about 49 mm high. From the stand in front of the
bay it filled the top of an upright phone's screen and lay across the Map and ? buttons and the map (before: §26.4 stills).

**Design.** A fixed instrument panel on the bay, in the same place for every device (`WfEquipment.mount_display`, shared by SYS-001's
readout in `#interior-systems`/`#interior-deadship` and SYS-002's in `#interior-airflow`):

- a dark screen with the text on it, flush on the bay's face 3 cm proud, from 0.95 m above the deck up to just under the eyes (about 1.43 m;
  the walk camera's eye is 1.47 m), its left edge at the bay's middle, so a trainee who stands at the bay and looks level sees it just under and
  right of the centre of the screen, like a rack's own chest-height display;
- capitals about 31 mm (an em of 44 mm, PROTOTYPE), lines of at most about 30 characters, so the panel is about 0.6–0.7 m wide and
  0.45–0.55 m tall;
- one-sided, not a billboard: it rides the ring with the bay, like the rest of the rack;
- the same words as before, regrouped into short lines; the airflow panel lists one sector per row with its two corridor halves.

**A measuring error found on the way, and a Phase 1 defect it hid.** The checks and the scripted stills put the trainee's eyes 1.6 m
above the walking body's origin, but that origin is the body's centre (0.85 m above the deck); the walk camera sits `EYE_UP` = 0.62 m
above it, 1.47 m above the deck. So the earlier stills looked down at the bay from 2.45 m, which put anything at eye level near the top of
the screen, and the Phase 1 check that "the carried spare is 33.7° under the eyes" (§22.2) measured from the same wrong eye: the spare,
placed 1.3 m above the origin, was in fact held at 2.15 m, above the trainee's head. Both are fixed: the checks and stills use `EYE_UP`
(`check_player.gd`, `check_deadship.gd`, `check_airflow.gd`), the spare is held 0.30 m under the eye (`scrubber.gd`), and the check now
requires it to be under the eye line (more than 10°) as well as inside the view; it measures 33.7° under the true eye.

Presentation only (a Label3D and a quad). No ship geometry, camera, interaction distance, ring rotation, touch control, Phase 1
page or Phase 2A map changed. An intermediate version (a panel tilted on the bay's top edge, capitals 22 mm) was rejected after its
stills: still at the top of a phone's screen and too small to read on a desktop.

**Measured clearance.** `check_deadship` (`_board_clear`, runtime check `deadship`) puts the eye at the walk camera (1.47 m) over the stand in front of the
bay, looks level at the bay and measures the panel's corners against the lower edge of the screen's top row on the current viewport:

| Viewport | Panel top over the eye line | Panel bottom | Top row's lower edge | Result |
| --- | --- | --- | --- | --- |
| Desktop 1280 × 720 | −1.0° | −17.5° | 37.5° (no touch row) | Clear; capitals about 9 px at the 1.76 m stand |
| Phone on its side 844 × 390 | −1.0° | −17.5° | 27.3° | Clear of the top row and the buttons; **text small** (about 5 px capitals at 1.76 m): readable from about a metre |
| Phone upright 390 × 844 | −1.0° | −17.5° | 28.8° | Clear of the Map and ? row, the map, the goal box and the touch buttons (still: §26.4); capitals about 11 px |

The panel is 0.61 × 0.48 m (DS-1 text) and lies 0–20° right of the gaze. The angles hold for every screen shape, because the camera
keeps its vertical field of view; only the top row's position changes. The runtime check fails if the panel reaches the top row. The
stills of §26.4 look level at the bay from the same stand, as a trainee does; the earlier stills looked down at the display from a wrong
eye height (below).

### 26.2 Web-export size

The budget the repository validates is the download of Enter Wayfarer (`PLAY_BUDGET = 90,000,000` bytes in `tools/web_export.py`:
engine, shell and pack). Before this work it stood at 89,996,565 bytes, 3.4 kB under the budget.

| Measure | Before | After | Change |
| --- | --- | --- | --- |
| Raw download validated against `PLAY_BUDGET` | 89,996,565 B | 78,129,509 B | −11,867,056 B (−13.2 %) |
| Headroom under the 90 MB budget | 3.4 kB | **11.87 MB** | |
| `walk-*.pck` (the play pack) | 50,179,100 B | 38,312,044 B | −11,867,056 B |
| `walk-*.pck` gzip −9 (what a compressing server could send) | 45.3 MB | 33.5 MB | −11.8 MB |
| `engine-*.wasm` (unchanged) | 39,514,754 B (gzip 10.1 MB) | same | 0 |
| Cached data on a returning visit | the pack and the engine are content-named; a release that changes only the pack re-downloads 38.3 MB instead of 50.2 MB, the engine stays cached | | |
| Runtime memory | not measured; the shadow meshes were loaded with the scene, so the change should lower it, but no number is claimed | | |

**What was removed.** The imported scenes carried a second "shadow mesh" for every mesh. No light in the walk or Explore Exterior casts
shadows, so they were never drawn. In the ship scene they were 10.8 MB of 31.8 MB. `godot/project.godot` now sets the importer default
`meshes/create_shadow_meshes = false`; the runtime export writes fresh imports, so every scene (ship, docked, characters, EVA) follows.
LODs, tangents, surface deduplication, textures and the simulation checkpoints are unchanged; the budget was not raised and no
validation was weakened. Visual trade-off: none, as nothing cast shadows; the runtime export's 11 checks and the web build's native
walk, locomotion and EVA checks pass on the new package (§26.3).

**Recommended target.** Keep `PLAY_BUDGET` at 90 MB and keep at least 5 MB of headroom; a feature that would eat into the last 5 MB
should bring its own saving. Measured candidates for later, not applied: compact JSON for `manifest_docked.json` (about −0.65 MB),
`wf_sim_rig.json` (about −0.29 MB) and `characters.json` (about −0.23 MB); one copy of the characters' identical eye textures (about
−0.8 MB).

### 26.3 Validation (Phase 2A finalization)

Automated runs, not human playtests. All on this branch's working tree, 2026-11-14:

| Check | Command | Result |
| --- | --- | --- |
| Python tests | `python3 -m unittest discover -s tests` | 258 run, OK (1 skipped) |
| Runtime export (fresh import, no shadow meshes) | `python3 tools/workflow.py runtime-export` | PASS, 11 checks (run `20261114T120348956168Z-runtime`) |
| Godot checks after the panel and eye fixes | `python3 tools/workflow.py runtime-check auto` | PASS: excursion, eva-ops, locomotion, systems, deadship, airflow (package CURRENT) |
| Native stills, four screens | `godot --resolution <w>x<h> res://scenes/excursion.tscn -- --deadship --check-deadship [--touch] --shots=<dir>` (and `--airflow --check-airflow`) | PASS at 390 × 844, 844 × 390, 1280 × 720; panel angles above |
| Web build | `python3 tools/workflow.py web --out <site> --characters <chars>` | PASS; Enter Wayfarer 78.13 MB; native walk, locomotion and EVA checks PASS |
| Browser, main | `python3 tools/web_check.py <site> --part main --out <dir> --chrome /opt/pw-browsers/chromium --no-sandbox` | PASS 67/67 |
| Browser, DS-1 by keys, touch and a phone turned upright | `python3 tools/web_check.py <site> --out <dir> --part training --training deadship --rotate` | PASS 3/3 (every action by the player's key or touch button; the turn prompt answered by a tap) |
| Browser, airflow and systems | `... --part training --training airflow`, `... --training systems` | PASS 2/2 each |
| Phase 2B gate | `python3 work/project-thread-dfyyv7/ds2_gate.py` | Deterministic; ledger ≤ 1.4 × 10⁻¹³ kg; step-independent to 6.4 × 10⁻¹⁴ (§27) |

DS-1 and the default start were run unchanged by the browser and runtime checks; DS-1 still uses the well-mixed model.

### 26.4 Stills

`/mnt/project-files/deadship_phase2b_2026-11-14/`: before and after of the bay on an upright phone (390 × 844), a phone on its side
(844 × 390), a desktop (1280 × 720) and the airflow demo, rendered natively at the scenario's Restore and Isolated steps.

---

## 27. Phase 2B: the engineering gate [ENG; gate FAILED, no gameplay built]

Phase 2B was authorized on 2026-11-14 on one condition: a scenario is built only if the existing model produces a genuine decision,
with at least two valid strategies whose consequences the model computes, no trivially ideal strategy and no hidden unmodelled
penalty. This section tests that. **The gate fails on SYS-002 as it stands, so Part C (the playable scenario) was not built.** What
follows is the evidence, a revised design and the smallest requirement that would let it pass.

Study: `work/project-thread-dfyyv7/ds2_gate.py` (task study; it calls `ring_air`'s public functions and changes nothing), results in
`ds2_gate.json`. Run: `python3 work/project-thread-dfyyv7/ds2_gate.py` (about 15 minutes, deterministic).

### 27.1 What each §24 consequence actually is (§5 of the brief)

| §24 consequence | Class | Why |
| --- | --- | --- |
| Sector 2 at 0.525 % with fill 2 shut and nobody moving | **Computed** | `ring_air` steady state, conserved, Python/Godot parity |
| Sectors 1 and 2 reach 0.5 % in 2.3 h and 2.7 h with the doors shut | **Computed** | Same model, transient |
| Which doors can open, and the route a crew walks | **Physically constrained** | The CIRC door graph and the walk's doors; routes are the graph's shortest paths |
| The doorway and duct flows (139 m³/h, 238 m³/h) | **Computed from PROTOTYPE values** | DS-O7: kept, not canon |
| Crew transit time (40 s per compartment) | **Scenario rule (PROTOTYPE)** | No locomotion model; a fixed time per compartment passed |
| Fill 2's doors held shut for a suspected leak | **Scenario rule** | A procedure, enforced as a refusal; there is no leak in the model |
| "Breaks the leak isolation" as the cost of opening fill 2 | **Unmodelled** | No pressure or leak physics (out of scope by the brief). Presenting it as a cost would be a hidden penalty |
| "Sector 1 crowded", "the ECLSS sector crowded" | **Unmodelled** | The only effect of four people in a sector that any model computes is their CO₂, which is already in the numbers. Comfort, heat, humidity and work-space interference are not modelled |
| "Above the target" as harm | **Unmodelled** | 0.3 % and 0.5 % are PROTOTYPE control levels (DS-O1, DS-O2), not injury thresholds. The study reports hours above them, never harm |

So the §24 table's real trade was between one computed cost (CO₂) and two unmodelled ones (crowding, leak). Remove the unmodelled ones
and only CO₂ is left.

### 27.2 The search

Every strategy is the same three things: which doors stand open, where each crew goes, when. A strategy is applied half an hour
after the fault (PROTOTYPE reaction time) with transit included, then the model runs to the horizon with no further input. Each run is
scored only on what the model computes: the worst compartment CO₂ after the action, crew-hours above the target, whether the state
settles (bounded) or keeps climbing, the first time any occupied compartment reaches the limit, and the CO₂ mass held outside the
unit's sector. The Pareto front over those objectives is the set of strategies that no other strategy beats on every count.

| Variant | Premise (every value PROTOTYPE) | Configurations | Viable (no occupied compartment over 0.5 % in the horizon) | Pareto set |
| --- | --- | --- | --- | --- |
| V0 | §24 as written: fans failed, fill 2 held shut, three crews of two free to go anywhere | 1,728 | 297 at 6 h; 146 at 12 h | **1**: everyone to sector 3, 0.215 %, 0 h above target |
| V1 | Refined: fans failed, every door free, sector 2's crew held at the repair, sector 1's crew may go to sector 3 | 1,024 | 376 at 6 h; 172 at 12 h | **1**: all doors open, sector 1's crew to sector 3, 0.216 % (6 h) and 0.226 % (12 h) |
| V3 | V1 with the unit at half duty | 1,024 | 376 at 6 h; 165 at 12 h | **1**: the same strategy, 0.266 % and 0.313 % |
| V4 | Twelve crew in ring A (four per sector), unit at half duty, fans failed, sectors 1 and 2 may each go to sector 3 | 2,048 | 124 at 6 h; **0 at 12 h** | 9 at 6 h (below) |

V1's search also counts the configurations that keep two crews in separate air: 283 of them are viable at 6 h, **none is bounded**.
Every configuration that settles puts every crew in one air group with the unit.

Named strategies (V1 at 12 h), for the debrief a scenario would need:

| Strategy | Doors open | Result |
| --- | --- | --- |
| Seal every sector | 0 | Sector 1 reaches 0.5 % at 2.3 h; not viable |
| Buffer sector 2 with two doors | 2 | Reaches 0.5 % at 9.2 h; not viable at 12 h |
| Buffer sector 2 with all four of its corridor doors | 4 | Viable, still climbing, 0.426 % at 12 h |
| Join sector 2 to the unit (3 doors), sector 1's crew to sector 3 | 3 | Settles, 0.273 % |
| Join both arcs | 6 | Settles, 0.269 % |
| Open the whole loop | 9 | Settles, 0.259 % |

V4's front (6 h): pooling all twelve at the unit gives 0.436 % everywhere and a 0.363 % crew-weighted mean; keeping sector 2's four
in place gives a lower mean (0.335–0.361 %) at the price of a worse compartment (0.458–0.498 %). The trade is real but small (0.03 % of
mean against 0.06 % of peak), and it vanishes if the repair slips: at 12 h no configuration stays under the limit.

### 27.3 Why the gate fails

The model has one species and one sink. CO₂ is removed in proportion to its concentration at the unit, so bringing more air or more
people to the unit is never worse for anyone: pooling dominates. The only thing that makes separation worthwhile is something the
model does not carry. Separate results by criterion:

| Gate criterion | Result |
| --- | --- |
| At least two valid strategies with computed, measurably different consequences | **Fails** in V0, V1 and V3 (one Pareto point). V4 has nine, but in two families 0.03 % of mean apart, and none survives the 12 h slip |
| No trivially ideal strategy | **Fails**: "everyone to sector 3, open the doors" is ideal in every variant but V4 |
| No hidden unmodelled penalty | **Fails** for §24 (crowding, leak). V1 to V4 pass: they score CO₂ only |
| An unavoidable sacrifice | **Fails**: pooling saves everything in V0 to V3; in V4 the sacrifice is a few hundredths of a percent |
| Conservation and determinism | **Pass**: ledger error at most 1.4 × 10⁻¹³ kg; identical results on rerun |
| Time-step independence | **Pass**: 10, 60 and 300 s steps agree to 6.4 × 10⁻¹⁴ relative |
| Fits the architecture | Pass (no new physics), but moot |

Building Part C on this would teach the player one rule ("take everyone to the scrubber"), dressed as a dilemma. Per the brief, nothing
was implemented.

### 27.4 A finding for DS-O7

With twelve crew in ring A and every system working (V4's start), the PROTOTYPE ventilation holds sectors 1 and 2 at 0.447 % and the
corridor arcs between 0.35 % and 0.45 % at steady state. That is under the 0.5 % limit but well above the 0.3 % target, with no fault at
all. The ship is designed for twelve (owner, 2026-11-08), split six per ring in DS-1 and Phase 2A, so this is not a defect of the
modelled baseline. It does show that the 238 m³/h duct assumption has little margin if a ring has to carry the whole crew. Recorded
under DS-O7; no value was changed.

### 27.5 Revised DS-2 design: "Shared Air" [PROPOSAL; not built]

The smallest mechanism that makes separation matter physically is **a second airborne species with a source and its own sink**. The
probe V2 (same graph, same flows, PROTOTYPE values: a trace contaminant released in sector 2 that would reach its limit in 4 h in a
sealed sector, removed only by a 15 m³/h trace-contaminant flow at the unit in sector 3) gives a real trade at 12 h:

| Strategy | Sector 2's crew (× contaminant limit) | The other crews | CO₂ |
| --- | --- | --- | --- |
| Seal every sector | 3.0 | 0 | Sectors 1 and 2 over 0.5 % at 2.3 h |
| Buffer sector 2 with two doors | 0.87 | 0 | Over 0.5 % at 9.2 h |
| Buffer sector 2 with four doors | 0.53 | 0 | Viable, climbing (0.426 %) |
| Join sector 2 to the unit, sector 1's crew to sector 3 | 0.57 | 0.39 | Settles (0.273 %) |
| Open the whole loop | 0.31 | 0.21–0.23 | Settles (0.259 %) |

Now the choices are non-dominated: opening spreads the contaminant to people who were clean, while closing keeps them clean and lets
CO₂ build where the repair crew works. Neither is free. The sacrifice is computed, not narrated. The probe is indicative only: it was not
searched to a full Pareto front, and its species, source and limit are placeholders.

### 27.6 The smallest next requirement

1. **SYS-002 v2: a vector of transported species.** The same transport matrix applied to a second concentration vector, each species
   with its own per-compartment sources and its own removal node and flow. Linear, conserved, exact-step, the same parity and
   checkpoint tests. No thermal, humidity, fire, pressure or electrical physics. Size S in Python and GDScript.
2. **Owner choices** before any build: which trace species and source (a credible ECLSS or equipment off-gas, not an invented canon
   event), its exposure limit and reference (for example a spacecraft maximum allowable concentration, labelled PROTOTYPE until an
   owner row exists), and whether the trace-contaminant control sits with the CO₂ unit in sector 3.
3. **Then rerun this gate** with the new species. Part C (the playable scenario) follows only if the full search finds at least two
   non-dominated, viable strategies at both horizons.

The weaker alternative, a capacity state on the unit with twelve crew (V4), needs no new species but gives a small trade that
disappears at 12 h and depends on the DS-O7 margin finding above. Not recommended.

### 27.7 Roadmap after the gate

2B "Shared Air" needs the requirement above and a second gate (S, then M for the scenario) → 2C "Borrowed Air" (humidity, heat, parts;
M–L) → 3 broader systems → 4 competitive and Hullrun → 5 narrative. Each needs separate authorization.

## 28. Handoff (Phase 2A finalization and the Phase 2B gate)

1. **Implemented.** DS-O10: the bay's readout is a fixed chest-height instrument panel on the bay (`equipment.gd` `mount_display`,
   shared by `#interior-systems`, `#interior-deadship` and `#interior-airflow`), with short lines (`equipment.gd`, `airflow.gd`), and
   the `deadship` check measures its clearance (§26.1). The checks and stills now use the walk camera's real eye height, and the carried
   spare is held at chest height, no longer above the head (§26.1). Web export: shadow meshes off by importer default
   (`godot/project.godot`), 11.87 MB less to download (§26.2). Phase 2B: the engineering gate study (`ds2_gate.py`, `ds2_gate.json`) and
   this report (§27).
2. **Reused.** `WfEquipment` and its board, the ring map, the walk's doors, `ring_air` unchanged (the gate calls its public functions),
   the runtime and browser checks, the existing web budget.
3. **Not built, by the gate.** No Phase 2B scenario, crew relocation, stability watch on SYS-002 or debrief. §27.3 says why; §27.5–27.6
   give the revised design ("Shared Air") and the smallest next requirement (a second transported species, with owner-chosen source and
   limit, then a second gate).
4. **Decisions applied.** DS-O7 kept as PROTOTYPE (with the twelve-crew margin finding, §27.4); DS-O8 hatches closed and outside the
   model; DS-O1 and DS-O2 unchanged; DS-O9 authorized subject to the gate (failed); DS-O10 resolved.
5. **Validated.** §26.3: Python tests, the runtime export's 11 checks, the web build's native checks, the browser runs, the native
   stills; §27: the gate's determinism, conservation and time-step independence.
6. **Not validated.** No human playtest; no real phone or GPU (software WebGL); runtime memory not measured; the panel's readability on
   a landscape phone from more than about a metre (small text, §26.1); the Shared Air probe is indicative, not a full search.
7. **Unchanged.** DS-1 keeps its well-mixed model; `#interior`, Explore Exterior, the Engineering pages, canon, Drive, Blender and ship
   geometry, the deployment.
8. **Commits** on `claude/project-thread-dfyyv7`, pushed, not squashed, not merged, not deployed: the bay panel (DS-O10) with the eye
   height and carried-spare fixes; the export size; the Phase 2B gate study and report.
9. **Owner checklist** (additions to §22.4): on a phone held upright and on its side, stand at the ECLSS bay and read the panel; look
   for anything it hides; carry the spare and confirm it is in front of the chest; open Enter Wayfarer on a slow connection and compare
   the load time.
10. **Owner questions.** Accept the panel (DS-O10) and the export change? For Phase 2B, choose: (a) the "Shared Air" requirement
    (a second species: which source, which limit), (b) the weaker twelve-crew variant, or (c) park Phase 2B.

# SYS-002 v2 and the Phase 2B gate, second attempt (2026-11-14, third brief)

The owner's brief of 2026-11-14 15:21Z: extend SYS-002 to carry CO₂ and NH₃, with a finite NH₃ source and an NH₃ sink separate from
the CO₂ unit; apply NASA JSC 20584 Rev D's ammonia SMACs as duration-specific exposure references (never as injury); extend the Python
and Godot verification; rerun and strengthen the Phase 2B gate; prepare, but not build, the gameplay design. Accepted decisions carried
over: DS-O7 (PROTOTYPE ventilation and doorway values), DS-O8 (hatches closed, outside the model), DS-O10 (panel), the 90 MB web budget
with at least 5 MB headroom, and the rejection of the single-gas 2B.

## 29. SYS-002 v2: CO₂ and NH₃ [BUILT]

### 29.1 Why ammonia, and which source

The first gate failed because one species with one sink makes pooling at the sink always right (§27.3). A second species matters only if
its source and its sink are in different places, so that the connections that help one gas hurt the other. Ammonia fits without
inventing a ship system: it is one of the best documented spacecraft cabin contaminants, it has its own removal path on the ISS (the
trace-contaminant control system's phosphoric-acid-treated carbon bed, separate from CO₂ removal), and it has 1 h, 24 h and long-term
SMACs.

**Source substitution.** The brief's starting idea was a leaking cartridge. No Wayfarer or ISS cartridge holds free ammonia in the cabin,
and an ammonia coolant loop is excluded by the brief (and the cabin loops are not ammonia in canon), so the source is **stored urine in
sector 1's hygiene compartment whose pretreatment failed**. Urine's urea hydrolyses (urease from bacteria) to ammonia,
CO(NH₂)₂ + H₂O → 2 NH₃ + CO₂; the ISS adds a pretreatment to stored urine precisely to stop this. At about 20 g/L urea a fully
hydrolysed litre holds up to about 11 g of ammonia, far more than the cabin air carries, so the release is limited by evaporation from
the spill, not by the air. Modelled as a spill: a finite volatile inventory M₀ leaving at a first-order rate S/τ. **M₀ = 7 g, τ = 1 h are
PROTOTYPE order-of-magnitude values** (about a litre spilled, a fraction of its ammonia leaving before it is bagged); the share that
evaporates depends on pH, temperature, wetted area and airflow, none of which is modelled, so the uncertainty sits in M₀ (3–20 g) and
τ (0.25–4 h), and the gate (§30.6) tests both ends. The values were fixed before the strategy search and were not adjusted after it.
Scale: 7 g is 334 ppm in a sealed A1 and about 27 ppm spread through the whole ring.

### 29.2 Values: external references and PROTOTYPE choices

| Quantity | Value | Status | Source |
| --- | --- | --- | --- |
| NH₃ SMAC | 1 h 30, 24 h 20, 7 d 3, 30 d 3, 180 d 3, 1000 d 3 ppm | EXTERNAL REFERENCE | NASA JSC 20584 Rev D (02/2026) p. 9; read from the document. The 1 h and 24 h values are off-nominal and allow minor reversible effects; an exceedance is a risk to evaluate (p. 7), not an injury |
| TCC process flow | 15.3 m³/h, one element per ring, in the sector 3 ECLSS bay | PROTOTYPE (ISS value) | NASA NTRS 20070019823 (15.3 m³/h); about 15 m³/h in NTRS 20100039332 |
| TCC single-pass NH₃ capture | 0.95 | PROTOTYPE | Phosphoric-acid-treated activated carbon holds NH₃ as an ammonium salt (NTRS 20170006640, 20160009022); bed capacity and breakthrough not modelled |
| CO₂ unit NH₃ removal | 0 | PROTOTYPE | The sinks are independent by construction |
| Condensate NH₃ removal | 0 | PROTOTYPE, conservative | Real condensing heat exchangers dissolve NH₃; there is no humidity model, so leaving it out over-predicts NH₃ |
| Background NH₃ | 0 ppm | PROTOTYPE | Metabolic and off-gassing NH₃ neglected |
| Source M₀, τ, place | 7 g, 1 h, A1 (hygiene A) | PROTOTYPE, scenario data | §29.1; the model has no default source |
| Cabin P, T | 80 kPa, 295 K | unchanged | SYS-002 v1 |
| Exchange flows | 139 m³/h per open door, 238 m³/h per damper pair | PROTOTYPE (DS-O7) | unchanged |

### 29.3 Equations, units and the exact step

The NH₃ state is z = [c₁…c₉ (kg per compartment), S (kg left in the source), released, removed, ∫c₁…∫c₉], 21 values, and
dz/dt = B·z with B built from the same flows as the CO₂ matrix A: each open edge exchanges Q both ways (B[i][j] += Q/Vⱼ, B[i][i] −= Q/Vᵢ),
the LEAKING source moves λ = 1/τ of S per second into its compartment and into `released`, the TCC removes k = Q_TCC·η/V_A3 of c_A3 into
`removed`, and each ∫cᵢ integrates cᵢ. The step is exact, z(t+Δt) = exp(BΔt)·z(t), by the same scaling-and-squaring series as CO₂, so a
step of any length gives the same state, and exposures come from the integral states rather than from sampled concentrations. NH₃ never
enters A: the CO₂ equations, their reference run and their checkpoints are byte-identical to v1 (checked). The NH₃ step costs nothing
while there is no NH₃ and no source.

Units are kept apart (`trace_units`): kg in the compartment, mol/m³ = c/(M·V), mole fraction x = c/(M·n) with n = PV/(RT), ppm = 10⁶·x,
partial pressure x·P. The SMACs are mole-fraction values and Rev D applies them unchanged at reduced cabin pressure, so ppm is compared
directly. Source states: NONE, LEAKING, ISOLATED (what the source still holds stays in it, accounted); a negative inventory or τ ≤ 0 is
refused; the first-order release empties the source asymptotically and S is clamped at 0 so it never goes negative.

### 29.4 Exposure

`src/wayfarer/air_exposure.py` follows a person through the compartments they are actually in, one at a time (a walk is a sequence of
short stays, never two places at once), adding each compartment's exact integral over the stay. Each reference is compared with the
largest time-weighted mean over its own duration, (E(t) − E(t − w))/w with E = 0 before the event, never with one instant. A 24 h value
is reported only from a run covering 24 h, a 7 d value only from a run covering 7 d. Per person: current and peak concentration, dose,
largest 1 h and 24 h means, the 7 d mean, transit dose, and time above the CO₂ target.

### 29.5 Validation

| Requirement | Test (`tests/test_ring_air_nh3.py`, 21) or check | Result |
| --- | --- | --- |
| Isolated release; door spread; ventilation spread; confinement | `release_into_an_isolated_compartment_stays_there`, `an_open_door_carries_it_to_the_next_compartment_only`, `ventilation_spreads_it_with_every_door_closed`, `closing_a_compartments_doors_and_dampers_confines_it` | pass |
| TCC removal; reach | `the_tcc_removes_it_at_its_own_flow`, `the_tcc_reaches_only_what_is_connected_to_it` | pass |
| Both species on the same flows; sinks independent; NH₃ leaves CO₂ unchanged | `both_species_ride_the_same_flows`, `co2_and_nh3_removal_are_independent`, `a_release_does_not_change_the_co2_equations` | pass (same-flow agreement 1e-14 kg) |
| Exhaustion; isolation; nonnegativity; zero source | `the_source_runs_out_and_never_goes_negative`, `isolating_the_source_stops_the_release_and_keeps_its_rest`, `no_source_and_an_empty_source_cost_nothing` | pass |
| Conservation per species | `each_species_is_conserved_through_every_kind_of_change` | ledger ≤ 1e-15 + 1e-10 × scale |
| Time-step independence; 30-day stability | `the_step_length_does_not_change_the_result`, `thirty_days_stay_stable_and_the_tcc_clears_the_ring` | 1e-11 × S₀ |
| Units; exposure; durations; references | `units_are_kept_apart_and_agree`, `the_exposure_integral_is_exact`, `a_person_is_exposed_only_where_they_are`, `duration_windows_are_time_weighted_not_instantaneous`, `the_reference_values_are_rev_d` | pass |
| Existing CO₂ cases | `tests/test_ring_air.py` (14) unchanged | pass |
| Full suite | `python3 -m unittest discover -s tests` | 279 tests OK (1 skipped) |

**Python/Godot parity.** The package (`wf_ring_air.json`, version 2, 19,415 bytes, was 9,514) carries both reference runs. `WfRingAir.verify`
replays them before the model is used; `godot/scripts/systems/verify_ring_air.gd` runs the same replay headless with no scene and
reports:

| Run | Checkpoints | Largest absolute deviation | Largest relative deviation | Largest ledger error |
| --- | --- | --- | --- | --- |
| CO₂ (v1 proof, unchanged) | 11 | 4.1 × 10⁻¹⁴ kg | 3.1 × 10⁻¹⁴ | 3.7 × 10⁻¹³ kg |
| NH₃ (trace proof: release, fans off, a door path to the TCC, isolation, TCC off and on, whole loop, fans on) | 11 | 9.9 × 10⁻¹⁸ kg | 8.1 × 10⁻¹⁴ | 2.7 × 10⁻¹⁴ kg |

Documented tolerance: 1e-9 relative plus 1e-12 kg absolute for CO₂ (v1), and for NH₃ 1e-3 × 1e-12 kg absolute plus 1e-9 relative
(NH₃ masses are grams, so the absolute floor is scaled down). Measured cost in Godot 4.7 (headless, this container): a CO₂-only step
8.0 µs, a step carrying NH₃ 31.6 µs; building the propagators on a topology change (a door, a damper, the fans, the source or the TCC)
1.1 ms for CO₂ and 4.6 ms for NH₃. Propagators are cached per configuration and step length, so the matrix exponential is never
recomputed per frame.

## 30. Phase 2B Gate — Second Attempt [ENG; PASSED for the base scenario, with stated limits]

Study: `work/project-thread-dfyyv7/ds2b_gate.py` (results `ds2b_gate.json`, about 20 minutes on 4 cores) and its reference lens
`ds2b_lens.py` (`ds2b_lens.json`). Both call `ring_air`'s public functions only, change nothing and are deterministic.

### 30.1 The event

At t = 0 the urine spill in A1 begins releasing (M₀ 7 g, τ 1 h). The ring is normal: doors closed, fans and dampers open, CO₂ unit and
TCC on, CO₂ at its steady state. Crew 2/2/2 in sectors 1/2/3 (sector 1's pair off shift in their berths, in the source compartment). At
d = 10 min (PROTOTYPE: smell or sensor) the crew act: Ops sets every damper and door; each pair walks to its destination by the shortest
door route at 40 s per compartment passed (PROTOTYPE; doors cycled behind them, the exchange during cycling neglected); optionally the
person nearest the spill contains it, 10 min of work in A1 (PROTOTYPE: bag the liquid and the absorbent), which sets the source
ISOLATED. Optionally at T₂ = 4 h the ring returns to normal ventilation with the crew where they are. At 24 h the projection puts the ring
back to normal and everybody home and runs to 7 d with no input. Nothing teleports and every exposure is taken along the actual route.

### 30.2 The strategy space

Each of the three sector-to-sector arcs (a door and a damper pair on each of its three links) takes one of six states: normal (dampers
open, doors closed), sealed, dampers and doors open, doors only, or its corridor joined to one end only. 6³ = 216 ring configurations ×
sector 1's pair to A1, A2 or A3 × sector 2's pair to A2 or A3 × sector 3's pair to A3 or A2 × contain or not × reconnect at T₂ or not:
**10,344 strategies** per parameter set, each run to 7 d. The brief's named strategies are members (§30.4). Search cost: 94 s for the base
set on 4 cores (about 30 ms per strategy for 7 days).

*Count reconciliation (Phase 2B brief §16).* The factors multiply to 216 × 3 × 2 × 2 × 2 × 2 = **10,368**. `ds2b_gate.strategies()`
skips one combination per pair destination set and containment choice: reconnecting at T₂ from the all-normal ring (every arc `D`) is
the same run as not reconnecting, so it is generated once. That removes 3 × 2 × 2 (destinations) × 2 (contain) = 24 duplicates:
10,368 − 24 = **10,344 distinct strategies**, the number searched. No strategy was lost; the two figures count the same set with and
without the 24 no-op duplicates.

### 30.3 Objectives and what each one is

| Objective (minimised) | Class |
| --- | --- |
| Largest 1 h mean NH₃ of any person / 30 ppm | Computed, against an external reference |
| Largest 24 h mean NH₃ of any person / 20 ppm (below 24 h: dose so far / 24 h, a lower bound) | Computed, against an external reference |
| Crew mean NH₃ dose (ppm·h) | Computed |
| Crew-hours above the CO₂ target 0.3 % | Computed, against a PROTOTYPE control level (DS-O1) |
| NH₃ still airborne at 6 h and 12 h | Computed |
| Largest 7 d mean of any person / 3 ppm (24 h horizon, through the projection) | Computed, against an external reference |
| Time until every compartment is under 3 ppm | Computed. Its meaning, that A1's berths and hygiene are not fit for continuous occupancy until then, is the long-term SMAC's purpose, not a modelled penalty |
| Viability: no occupied compartment over 0.5 % CO₂ | Constraint, PROTOTYPE control limit (DS-O2), never harm |

A difference counts only if it exceeds ε: 0.05 of a reference ratio, 0.5 ppm·h of dose, 0.5 crew-hours, 0.1 g, 2 h of restoration.

### 30.4 Base results

| Horizon | Viable | ε-Pareto set | Strategy families on it | Trivial optimum (within ε of the best on every objective) |
| --- | --- | --- | --- | --- |
| 6 h | 8,452 | 174 | 10 | none |
| 12 h | 7,756 | 157 | 12 | none |
| 24 h (with the 7 d projection) | 7,444 | 59 | 7 | none |

The brief's named strategies (24 h, with the 7 d projection):

| Strategy | Viable | Worst 1 h / 30 | Worst 24 h / 20 | Worst 7 d / 3 | Crew-h above CO₂ target | Ring under 3 ppm after |
| --- | --- | --- | --- | --- | --- | --- |
| Do nothing (fans on, nobody moves) | yes | **1.16** | **1.05** | **1.92** | 0 | 75 h |
| Seal and stay (every sector sealed) | no (CO₂ 3.8 % in A1) | **10.2** | **14.7** | **15.9** | 92 | 98 h |
| Seal A1, its crew to sector 2 / 3 | yes | 0.14 / 0.13 | 0.09 / 0.08 | **1.91 / 1.90** | 0 | 97 h |
| Seal A1 4 h, then reconnect | yes | 0.85 | 0.86 | **1.82** | 0 | 78 h |
| Ventilation off, crew stay | no | **2.54** | **3.14** | **4.84** | 87 | 99 h |
| Limited doors: A1 to the TCC the short way, everyone in A2 | no (A2 sealed with six) | 0.10 | 0.02 | 0.44 | 141 | 48 h |
| Full loop open | yes | 0.94 | 1.00 | **1.86** | 0 | 75 h |
| Everyone to the scrubber (sector 3) | yes | 0.77 | 0.89 | **1.77** | 0 | 75 h |
| Preserve the clean sectors (A1 sealed, 2–3 joined) | yes | 0.13 | 0.08 | **1.90** | 0 | 97 h |
| Contain the spill, fans on | yes | 0.57 | 0.30 | 0.54 | 0 | 32 h |
| Contain the spill, A1 sealed, reconnect at 4 h | yes | 0.39 | 0.27 | 0.53 | 0 | 35 h |

Bold: over the reference. Sealing A1 without containing only postpones the dose: the 7 g stay in A1, which has no sink, and spread when
the ring is reconnected. Every named strategy without containment exceeds at least the 7 d reference.

### 30.5 The reference lens

The ε-front counts differences far below every reference as trades. The sharper question is the trainee's: which strategies keep every
person inside every reference (CO₂ viable; 1 h, 24 h and 7 d NH₃ means under their SMACs), and is there still a choice among them?

**Base: 3,588 strategies keep everyone inside every reference, and every one of them contains the spill.** Containment is a forced
first move, not a choice, at these values. After it, five families remain non-dominated, and the trade between them is real:

| Family (representative) | Worst 1 h / 30 | Worst 24 h / 20 | Crew dose (ppm·h) | Crew-h above CO₂ target | Worst 7 d / 3 | Ring under 3 ppm after |
| --- | --- | --- | --- | --- | --- | --- |
| Contain, keep A1 and its corridor apart, everyone to sector 3 | 0.26 | 0.02 | 2.6 | 0 | 0.54 | 56 h |
| Contain, A1 joined to A2 only, everyone to sector 3 | 0.24 | 0.02 | 2.6 | 0 | 0.53 | 56 h |
| Contain, A1's air sent round to the TCC through the doors, everyone to sector 3 | 0.27 | 0.22 | 98.6 | 0 | 0.52 | 39 h |
| Contain, A1's arc joined to the TCC, sector 2 sealed with all six, reconnect at 4 h | 0.30 | 0.22 | 99.9 | 82.5 (peak 0.43 %) | 0.44 | 28 h |
| Contain, A1 to the TCC, crews split, reconnect at 4 h | 0.49 | 0.30 | 113.4 | 5.7 (peak 0.34 %) | 0.52 | 29 h |

So the decision is: **keep the residue sealed in sector 1** (the crew breathes clean air, the habitation sector is out of use for
about 56 h), **send it through the occupied ring to the TCC** (everyone breathes about 4 ppm for a day, under the 24 h reference but above
the long-term level, and the habitation sector is back after about 39 h), or **seal the crew away from the purge** (back after about 28 h,
at the price of a day above the CO₂ target in a crowded sector). The person who contains the spill carries the largest 1 h exposure in
every family (7 to 15 ppm mean over the hour, under 30 ppm). No family is within ε of the best on every count.

### 30.6 Sensitivity (criterion F)

One value at a time, the whole search rerun for each (17 sets, 175,848 runs):

| Variation | ε-Pareto families 6 / 12 / 24 h | Trivial optimum at 6 / 12 / 24 h | Inside every reference (of which contain) | Families inside | Restoration on that front |
| --- | --- | --- | --- | --- | --- |
| Base | 10 / 12 / 7 | none | 3,588 (3,588) | 5 | 28–56 h |
| Inventory 3 g | 11 / 11 / 12 | none | 7,219 (3,722) | 12 | 5–70 h |
| Inventory 20 g | 12 / 10 / 6 | none | **0** | 0 | — |
| Release τ 15 min | 14 / 12 / 7 | none | **0** | 0 | — |
| Release τ 4 h | 5 / 5 / 1 | **3 at 24 h** | 3,722 (3,722) | **1** | 2–3 h |
| Ventilation ×0.5 / ×1.5 | 12 / 12 / 9 and 9 / 9 / 7 | none | 3,229 and 3,753 (all contain) | 6 and 5 | 30–59 h and 25–55 h |
| Door flow ×0.5 / ×2 | 10 / 11 / 7 and 10 / 13 / 8 | none | 3,373 and 3,818 (all contain) | 5 and 6 | 28–56 h |
| TCC efficiency 0.5 | 9 / 12 / 7 | none | 3,400 (all contain) | 5 | 40–83 h |
| TCC at twice the flow, η 0.95 | 10 / 10 / 6 | none | 5,064 (3,588) | 6 | 14–63 h |
| Sector 1's pair awake in sector 2 | 10 / 11 / 7 | none | 3,587 (all contain) | 5 | 25–59 h |
| Twelve crew (4/4/4) | 6 / 10 / 11 | none | 1,466 (all contain) | 9 | 27–56 h |
| Reaction 5 min / 30 min | 10 / 12 / 9 and 8 / 10 / 8 | none | 3,722 and 3,089 (all contain) | 6 and 5 | 20–48 h and 48–73 h |
| Containment takes 20 min | 12 / 11 / 6 | none | 3,339 (all contain) | 4 | 25–67 h |
| Transit 80 s per compartment | 10 / 12 / 7 | none | 3,587 (all contain) | 5 | 28–56 h |
| Reconnect at 8 h | 20 / 10 / 8 | none | 3,363 (all contain) | 6 | 26–56 h |

The decision survives every change to the ship's side of the problem: ventilation, door flow, TCC performance, crew positions and number,
reaction time, containment time, walking time and reconnect time. It does **not** survive large changes to the source itself:

- a slow release (τ 4 h): containment catches almost everything and "contain, then anything" is trivially best;
- a fast or large release (τ 15 min, 20 g): no strategy keeps everyone inside every reference; the front is then a choice of whose
  exceedance and which reference, which a training scenario should not be built on without the owner.

So the scenario must fix its source values (§31) and say why; a different source makes a different exercise, not a harder one.

### 30.7 The gate, criterion by criterion

| Criterion | Result |
| --- | --- |
| A. Multiple viable strategies | **Pass.** 7,444 viable at 24 h; 3,588 inside every reference |
| B. Non-dominated | **Pass.** Five families inside every reference, ten to twelve on the 6 h and 12 h fronts; the axes are the crew's 24 h exposure and CO₂ burden against how soon the habitation sector is clean |
| C. Physical consequences only | **Pass.** Every objective is a model output; references are external (SMAC) or the PROTOTYPE CO₂ levels already in DS-O1/DS-O2; nothing scores crowding, leaks or comfort |
| D. No trivial optimum | **Pass, with one forced move.** No strategy is within ε of the best on every objective, but containment is necessary to stay inside the references at the base values. The scenario should treat it as the procedure it is (the first action of the exercise), with the choice after it |
| E. Defensibility | **Pass, PROTOTYPE.** SMACs read from Rev D; TCC flow and chemistry from ISS papers; the source is a documented failure mode with order-of-magnitude values, fixed before the search and exposed in the sensitivity |
| F. Robustness | **Pass for 14 of 17 variations.** Fails for the source's own extremes (τ 4 h trivial; τ 15 min and 20 g leave nothing inside the references) |
| G. Repeatability | **Pass.** Reruns identical; 300 s against 60 s steps agree to 3.1 × 10⁻¹¹ relative; ledgers at most 8.0 × 10⁻¹³ kg CO₂, 1.8 × 10⁻¹³ kg NH₃, 1.0 × 10⁻¹⁵ kg release |

**Verdict: the gate passes for the base scenario.** With a second species whose source and sink are in different places, SYS-002 v2
produces a decision with no right answer that the model does not compute, inside a stated range of source values. What it does not do:
model where the crew sleep while A1 is out of use, the bed's capacity, condensate removal, or anything thermal, humid or pressurized. No
gameplay was built (§31).

## 31. Phase 2B Gameplay Proposal: "Shared Air" [PROPOSAL; not built, needs separate authorization]

### 31.1 The smallest valid scenario

| Field | Value |
| --- | --- |
| ID, name | DS-2B "Shared Air" (the second Deadship training, after DS-1) |
| Start | `#interior-shared-air`, ring A, Ops on the newcomer; the station's training frame as DS-1 |
| Premise | Hygiene A's stored urine was not pretreated; its bag splits and ammonia evaporates in sector 1 |
| Model | SYS-002 v2 (`ring_air`), unchanged values; SYS-001 not used |
| Initial state | Ring normal: doors closed, fans and dampers open, CO₂ unit and TCC on, CO₂ at steady state, NH₃ 0 |
| Crew | Six, 2/2/2; the trainee is one of sector 1's pair (the person nearest the spill) |
| Source | A1, M₀ 7 g, τ 1 h, LEAKING at t = 0 (PROTOTYPE; the scenario file states both and their basis) |
| Trigger to act | 10 min after the release (the smell); before that the clock runs with no input |
| Actions | Contain the spill (stand at hygiene A, 10 min); walk; open or close any CIRC door by hand (existing doors); at the ECLSS bay: each damper pair, the fans, the TCC; order each other pair to a sector (they walk the route) |
| Refusals | Opening a crew-tube hatch (DS-O8); acting on the TCC or dampers away from the bay; ordering a pair through a door that is held |
| Time | ×30 while acting, ×1800 for the watch, as DS-1 |
| Watch | The trainee ends the setup; the model runs to 24 h, then the 7 d projection, with no input |
| End | After the projection, or when the trainee stops |
| Debrief | Per person: route, peak, largest 1 h and 24 h means against 30 and 20 ppm, 7 d mean against 3 ppm, time above the CO₂ target; ring: NH₃ released, held in the bag, removed by the TCC, still airborne; when each sector is back under 3 ppm. Each shown against the five families of §30.5, never as a grade |
| Scoring | None (unscored, as DS-1) |
| Not modelled, said in the debrief | Where the crew sleep while A1 is out of use; TCC capacity; condensate; heat, humidity, pressure |
| Owner sign-off before build | The source and its values; using the SMACs as the debrief's references; whether the trainee may order other pairs |

### 31.2 UI and interaction requirements (requirements only)

1. **Ring map:** each compartment coloured by NH₃ and by CO₂ on two separate layers the trainee switches, each connection drawn as now
   (door, duct, none); the source's compartment marked with its state (LEAKING, ISOLATED).
2. **Bay panel** (DS-O10 layout): per compartment CO₂ % and NH₃ ppm on one line, the fans, each damper pair, the TCC; short lines,
   readable at the stand.
3. **Person readout:** for the trainee always, for each pair on the map, the current NH₃ ppm, the 1 h mean so far and the 24 h mean so
   far as fractions of 30 and 20 ppm, plus the CO₂ where they are. No health words; the references named by duration.
4. **Containment:** a context action at hygiene A (key and touch), a 10 min progress at ×30, interruptible; the source state on the map
   and the panel.
5. **Orders:** a pair is ordered from the map to a sector; the route is shown and walked (40 s per compartment); refused orders say why.
6. **Doors:** the walk's doors stay the door edges; a door the trainee leaves open stays open in the model.
7. **Watch and debrief:** the watch shows the clock, both gases and each person's means; the debrief shows §31.1's numbers and the
   trainee's place among the §30.5 families.
8. **Verification:** the scenario's reference replay (events and checkpoints, both species, per-person exposures) in its package and
   in a headless runtime check, as DS-1; Python/Godot parity within §29.5's tolerances.
9. **Phones:** every action reachable by touch; text within the phone free band (§22).
10. **Budget:** the scenario's data fits in the remaining web headroom with at least 5 MB to spare.

## 32. Roadmap

| Phase | Status |
| --- | --- |
| 0 Minimal engineering integration proof | Complete |
| 1 DS-1 "Scrubber" tutorial | Complete (finalized 2026-11-14) |
| 2A Atmospheric connectivity | Complete (finalized 2026-11-14) |
| SYS-002 v2 (CO₂ and NH₃) and the second 2B gate | Built and validated; gate passed for the base scenario; SYS-002 v2 accepted by the owner (2026-11-14) |
| 2B "Shared Air" | Built, finalized and validated on the task branch (§34, §36: separation viable with a scheduled reconnection); awaiting owner playtest and review |
| 2C "Borrowed Air" (humidity, heat, parts) | Research only (§37): a finite TCC bed is the recommended first model, behind its own gate; not authorized |
| 3 Broader systems | Design only |
| 4 Competitive Deadship and Hullrun | Design only |
| 5 Narrative survival | Design only |

## 33. Handoff (SYS-002 v2 and the second Phase 2B gate)

1. **Implemented.** SYS-002 v2: NH₃ as a second species in `ring_air.py` and `ring_air.gd` (finite source, separate TCC, exact step,
   integral exposures), `air_exposure.py`, 21 tests, a second reference run in the package, a headless verifier
   (`verify_ring_air.gd`), the gate study and its reference lens, this report (§29–§33), `docs/MODEL.md`, TODO.
2. **Reused.** The CO₂ model, its exact step and its checkpoints (unchanged), the exchange graph and flows (DS-O7), the export path, the
   runtime checks.
3. **Not built.** No Phase 2B scenario, UI, orders, containment action, map layers or debrief (§31 is a proposal).
4. **Source substitution.** A leaking cartridge became a urine pretreatment failure in hygiene A (§29.1); no ammonia cooling system.
5. **Validated.** 279 unit tests; Python/Godot parity at 8 × 10⁻¹⁴ relative; the gate's repeatability, step independence and ledgers;
   the runtime export and web size (§33.11).
6. **Not validated.** No playtest (nothing to play); the source values are PROTOTYPE; the TCC's capacity, condensate removal and the
   crew's sleeping places are not modelled; Godot cost measured headless in this container, not on a phone.
7. **Unchanged.** Canon, Drive, Blender and ship geometry, DS-1, `#interior-airflow`'s behaviour, the deployment.
8. **Commits** on `claude/project-thread-dfyyv7`, pushed, not squashed, not merged, not deployed.
9. **Correction.** Rev D p. 9 gives 3 ppm for 7 d, as the brief said; earlier SMAC tables used other long-term values, which do not apply.
10. **Owner questions.** Accept SYS-002 v2? Accept the urine source and its PROTOTYPE values (M₀ 7 g, τ 1 h)? Authorize building 2B
    "Shared Air" as §31, and say whether containment is taught as the procedure (the forced first move) and whether the trainee may
    order the other pairs.

### 33.11 Validation (SYS-002 v2)

| Check | Result |
| --- | --- |
| Unit tests (`python3 -m unittest discover -s tests`) | 279 OK, 1 skipped (was 258 before this work; +21 NH₃) |
| Python/Godot parity, headless, no scene (`verify_ring_air.gd` on the published package) | PASS; CO₂ 3.1 × 10⁻¹⁴, NH₃ 8.1 × 10⁻¹⁴ largest relative deviation (§29.5) |
| `workflow.py runtime-export` (rebuild, 11 runtime checks including `airflow`, `systems`, `deadship`) | PASS, 11/11 |
| `workflow.py web --native` (native walk, locomotion and EVA Operations checks on the web package) | PASS |
| Browser, `web_check.py --part training --training airflow` (keys, then touch on an emulated phone; the package must verify before the demo runs) | PASS 2/2 |
| Enter Wayfarer download against `PLAY_BUDGET` 90,000,000 B | 78,148,545 B (was 78,129,509 B; +19,036 B for the NH₃ reference run); headroom **11.85 MB**, above the 5 MB floor |
| Gate repeatability, step independence, ledgers | §30.7 G |

Not rerun: the browser `main` part and the `systems` and `deadship` training parts (their models and pages are unchanged; their native
checks ran in the runtime export).

## 34. Phase 2B "Shared Air": implementation [BUILT P2B]

Owner brief 2026-11-14 20:59Z. A browser-playable, unscored training on ring A's two-gas model, `#interior-shared-air`
(`-- --shared-air`). The default Explore Interior start, DS-1 and `#interior-airflow` are unchanged. Phase 2C is not started.

### 34.1 Assumptions

- **Approved values, unchanged.** The source is stored urine in hygiene A (A1) whose pretreatment failed: 7 g NH₃, τ = 1 h, first
  order (PROTOTYPE, training only). The SMACs are 1 h 30, 24 h 20 and 7 d 3 ppm (JSC 20584 Rev D). They are duration references,
  not injury thresholds, so the debrief names exceedances but invents no medical consequence. SYS-002 v2 is used only through its
  public operations; not one of its lines changed.
- **Scenario values** (`data/deadship/ds2_shared_air.toml`, every one PROTOTYPE):
  - the alert at 10 ship min, while the source leaks from t = 0;
  - containment work of 10 ship min;
  - ×30 play and ×1800 watch;
  - a 10 s step live and in the watch, 300 s in the projection;
  - 40 s of transit per compartment, of which the last 10 s count as standing in the doorway;
  - a watch to 24 h after the release (at least 1 h more), then a projection to 7 d;
  - the 3 ppm reuse criterion.

  `shared_air.load` refuses a scenario that sets any engineering key.
- **Crew.** Three pairs (A with the trainee, B and C), home in A1, A2 and A3. The five others are abstract places with orders,
  not figures. A pair cycles a shut door; the door's brief exchange is neglected and the walk's leaves do not move. No route crosses
  a **sealed bulkhead** (door shut and its damper pair shut), because that is the trainee's own boundary.
- **The trainee's modelled place.** Live, it is the compartment the body stands in, computed from the body's angle between the
  CIRC door angles (the map's frame). From the watch on it stays where the trainee stood (§34.8). The walk's start (the ring A
  landing) lies in A1 and within reach of the store.

### 34.2 Architecture

The work is in four layers, and each owns one thing.

| Layer | Python | Godot | Owns |
| --- | --- | --- | --- |
| Engineering model | `ring_air.py` (SYS-002 v2) | `WfRingAir` | every equation, value, removal and exposure integral |
| Scenario state | `shared_air.py` (`Run`) | `WfSharedAir` machine (§1 of the script) | the run: people, routes, containment, the watch phases, the log, the debrief |
| Equipment interaction | — | `WfSharedAir` play section, `WfAirflow` points (`bay`, `hygiene`) | what Use and Ops mean at each point, the door hook |
| Interface | — | the pages, HUD lines, the bay's board, `map.gd` layers | display only |

**The machine.** It runs on a fixed 10 s step and does the same things at every boundary, in this order:

1. Apply the due actions (in arrival order).
2. Advance the pairs' walks.
3. Isolate the source if the containment work is complete.
4. Count the occupants.
5. Step the model.
6. Add each person's exposure from the model's exact integral of their compartment.

The same order in both languages is what makes parity exact.

**Hooks in `excursion.gd`.** There are ten minimal hooks (a `shared_air` variable beside `deadship`): creation, step, Use, Ops,
`_toggle_door`, the record, the page, the goal, the labels and prompt, and the HUD update. No Deadship logic lives in the walk.

**The package.** `wf_deadship_ds2.json` holds the scenario, the 16 reference cases with hourly checkpoints, and their debriefs
(490 kB).

### 34.3 Containment

Containment is never automatic. **Ops at the store** starts the work, but only within its 2.2 m reach. The work accrues only while
the trainee stays in reach. Stepping out of reach, or Ops again, pauses it. Progress is kept and the store keeps releasing at the full
first-order rate until the last bag is sealed (rule: `[containment] rule`). Asking for containment from anywhere else is refused with
the reason, by the intercom item or in a reference script, and the state does not change. Opening the hygiene page (Use) only shows
the store's state and pauses the clock; it never grants progress. The checks confirm that containment takes at least 600 ship seconds
of work and that `released` then equals 7 g × (1 − e^(−t/τ)) to 10⁻¹² kg.

### 34.4 Crew model and orders

The intercom offers these orders:

- **Send.** Send pair B or C, or the trainee's partner, to a sector.
- **Hold.** Tell a walking pair to stop where it is.
- **Report.** Show the crew report.

How an order runs:

- A route is the shortest door path that crosses no sealed bulkhead.
- Each compartment takes 40 s, the first 40 s being spent leaving its own.
- Occupancy, and with it the CO₂ source, follows each person.
- NH₃ exposure accrues in transit, compartment by compartment.

These orders are refused, and nothing changes:

- a corridor or other non-sector destination;
- a pair's own sector;
- an unknown pair;
- a route across a seal.

A pair whose next door is sealed after the order stops and waits (`stopped` in the log). Moving pair A moves only the partner; the
trainee is never moved.

### 34.5 Controls

No new action or binding was added. Every prompt shows the player's own key, and touch shows the same labels as buttons.

| Where | Use | Ops |
| --- | --- | --- |
| Hygiene A (store in reach) | inspect the store (page) | start, pause or resume containment |
| Sector 3 ECLSS bay | open the control page, then move down it | open the page; on it, operate the selected control |
| Anywhere else on ring A | (doors and the ladder keep Use) | the intercom |
| After the run | page through the debrief | replay |

**The bay page** lists the fans (IMV), each of the nine damper pairs, the CO₂ unit, the TCC, the intercom and Close. The walk's
doors stay the only door state (`_sync_doors` reads their leaves).

**Refusals** come back with a reason and leave the state unchanged:

- a door close while an ordered pair is in its doorway: "The doorway is occupied by B-1, B-2…";
- any door during the watch;
- a contradictory order.

The walk's own "doorway occupied" refusal for the trainee's body is kept.

### 34.6 Two-gas visualization

The ring map draws one layer at a time, never a merged scale. The intercom's first item switches between them.

| Layer | Unit | Colour scale | Corner label |
| --- | --- | --- | --- |
| CO₂ | % | the Phase 2A target and limit | `CO2 %` |
| NH₃ | ppm | teal at 0, yellow at the 3 ppm reuse criterion, orange to the 24 h reference, red at the 1 h reference | `NH3 ppm`, in amber |

On top of the layer, the map shows:

- compartment IDs where they fit;
- each bulkhead's connection (door, duct or nothing, from Phase 2A);
- the store as the HYG diamond, with the source state in the caption;
- the pairs as lettered discs, hollow and with a line to the destination while walking (no figures).

**The bay's board** is the diegetic summary, six short lines: the CO₂ maximum and the unit, the NH₃ maximum and the TCC, the fans
and the shut dampers, the source and what is left, and the groups and open doors. Its place is the DS-O10 panel. Detail is on the
bay page (the compartment table) and in the crew report.

### 34.7 Exposure

Each person carries the model's integral of their compartment:

- E, in ppm·s, added at every step;
- the current value;
- the peak;
- the running largest completed 1 h mean and 24 h mean (an incremental window, the same rule as `air_exposure.window_max`; the tests
  compare the two);
- the time above the CO₂ target.

The crew report keeps four kinds of number apart:

- **measured now:** the place, the NH₃ now, the CO₂ at the person's place;
- **accumulated:** the peak, the largest completed 1 h mean (or "<1h" before an hour has passed), the running dose and the CO₂ hours;
- **completed windows:** the 24 h and 7 d windows appear only in the debrief, once they are complete;
- **HYPOTHETICAL**, in amber: the 24 h mean ahead and the CO₂ at 24 h, if nothing changes. This is computed on a copy of the model
  and never touches the run.

### 34.8 Watch semantics

**Declaring.** Declaring the ring set (an intercom item) snapshots the exact present state and continues the same model at ×1800.
Nothing is reset or tuned. The snapshot covers:

- the inventories;
- the component states;
- the people's places and walks;
- the doors and vents;
- the remaining source.

**Plans.** There are two:

- **NONE:** nothing changes.
- **RESTORE:** at the end of the watch, and only because the trainee declared it, the ring returns to normal ventilation (fans and
  dampers open, doors closed, both units on). Each person then walks home once every compartment on their way is under the reuse
  criterion, checked hourly, so nobody is moved into unsafe air. The log records `restore` and each `home`; the checks confirm that
  nothing else appears after the watch starts.

**During the watch**, doors are refused and no request changes the run. The trainee's modelled place stays where they stood.

**At the watch's end** (24 h after the release, or 1 h more if declared later), the verdict is taken:

| Verdict | Meaning |
| --- | --- |
| NOT_CONTAINED | the store still leaks |
| CO2_LIMIT | the 0.5 % control limit was passed where people were, at any time |
| TEMPORARY | an occupied group has no CO₂ removal |
| STABLE_RESIDUE | CO₂ held, but NH₃ above the reuse criterion is held where nothing removes it |
| STABLE | stable under the stated assumptions |

The projection then runs to 7 days. It uses 300 s steps, and 10 s steps while anyone walks. None of these is called permanent; the
debrief says what each depends on.

### 34.9 Debrief

The debrief is three pages, and every number on them is the run's own.

**Page 1: the ship.**

- The verdict, with the configuration and family at the watch (isolate, route to the TCC, separate, or uncontained).
- The plan, and whether it ran.
- NH₃: the inventory, the amount released, the amount still in the bag, the amount captured by the TCC, the amount still airborne.
- When the store was contained.
- CO₂ at 7 days: mean and maximum, and when the limit was crossed.
- Per compartment, the time until it stays under the 3 ppm reuse criterion, or "not within 7 d". The criterion is labelled a
  conservative training rule, not a NASA clearance.

**Page 2: per person.**

- Peak, largest 1 h mean, largest 24 h mean, 7 d mean.
- Dose in ppm·h and CO₂ hours above the target.
- The SMACs exceeded, and the route.
- The SMACs are labelled separately as duration references.

**Page 3: the three reference strategies, against the trainee's run.** The reference strategies are the packaged `isolate`, `purge`
and `separate` cases, from the same model. For each one the page gives the worst 1 h and 24 h, the crew-hours above the CO₂ target,
when A1 becomes reusable, and the verdict. It closes with the references text and the replay line. Nothing is hardcoded, and there is
no score or rank.

### 34.10 Parity

`shared_air.py` packages the 16 cases the brief lists (`cases()`); case 16 replays case 1 from the exact initial state. The checkpoints
are hourly in the live phase and the watch, plus the end of the watch and the end of the projection.

| Case | Family | Verdict | NH₃ released / captured / airborne at 7 d (g) | worst 1 h / 24 h / 7 d (ppm) | CO₂ crew-h above target | A1 reusable after | refusals |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 isolate | ISOLATE | STABLE_RESIDUE | 2.39 / 1.90 / 0.49 | 14.8 / 5.7 / 1.53 | 0 | not within 7 d | 0 |
| 2 purge | ROUTE | STABLE | 2.39 / 2.37 / 0.02 | 13.9 / 6.6 / 1.81 | 0 | 38 h | 0 |
| 3 separate | SEPARATE | CO2_LIMIT | 2.39 / 2.37 / 0.02 | 13.9 / 7.0 / 2.00 | 239 | 41 h | 0 |
| 4 no containment | UNCONTAINED | NOT_CONTAINED | 7.00 / 1.04 / 5.96 | 7.1 / 3.1 / 0.83 | 0 | not within 7 d | 0 |
| 5 delayed containment (1 h) | ROUTE | STABLE | 4.82 / 4.79 / 0.03 | 33.9 / 14.6 / 3.96 | 0 | 63 h | 0 |
| 6 invalid containment | ROUTE | STABLE | 2.75 / 2.74 / 0.02 | 22.9 / 8.4 / 2.26 | 0 | 44 h | 1 |
| 7 invalid orders | ISOLATE | CO2_LIMIT | 2.39 / 1.84 / 0.55 | 26.9 / 25.9 / 25.83 | 166 | not within 7 d | 4 |
| 8 doorway refusal | ROUTE | STABLE | 2.39 / 2.37 / 0.02 | 20.2 / 7.3 / 1.96 | 0 | 39 h | 1 |
| 9 ventilation off | ISOLATE | CO2_LIMIT | 2.39 / 0.09 / 2.29 | 26.9 / 25.9 / 25.83 | 499 | not within 7 d | 0 |
| 10 TCC off | ISOLATE | STABLE_RESIDUE | 2.39 / 0.00 / 2.38 | 20.3 / 9.7 / 9.27 | 0 | not within 7 d | 0 |
| 11 CO₂ held, NH₃ spread | UNCONTAINED | NOT_CONTAINED | 7.00 / 6.96 / 0.04 | 23.5 / 18.3 / 5.15 | 0 | 74 h | 0 |
| 12 clean air, slow recovery | ISOLATE | STABLE_RESIDUE | 2.39 / 1.84 / 0.55 | 13.9 / 5.9 / 1.54 | 0 | not within 7 d | 0 |
| 13 interrupted containment | ROUTE | STABLE | 2.52 / 2.51 / 0.02 | 21.3 / 7.7 / 2.07 | 0 | 41 h | 1 |
| 14 watch, no plan | ROUTE | STABLE | 2.39 / 2.37 / 0.02 | 20.3 / 7.3 / 1.96 | 0 | 39 h | 0 |
| 15 watch, restore plan | ISOLATE | STABLE_RESIDUE | 2.39 / 2.37 / 0.02 | 13.9 / 5.9 / 1.93 | 0 | 45 h | 0 |
| 16 replay of 1 | ISOLATE | STABLE_RESIDUE | identical to case 1 (the test compares every checkpoint) | | | | |

**Reading the cases.**

- Cases 7 and 9 leave the partner in a sealed, unventilated sector 1. That is why they show high NH₃ means and CO₂ above its target;
  the model computes this and nothing was added.
- Case 14 shows that the ring's normal state (doors closed, ducts open) already routes the residue through the ducts to the TCC.
- Case 15 shows that isolation followed by the declared restore clears sector 1 at 45 h. Isolation without a plan (case 1) keeps it
  out of use for the whole week.

**The ledgers.** The CO₂ mass ledger, the NH₃ ledger (air + source + bed), the release ledger, and the released = airborne + captured
check all close in every case (tests, and the Godot debrief check).

**Godot parity.** `check_shared_air.gd` replays all 16 cases in Godot, about 1 s each headless. It compares every checkpoint, within
the model's relative 10⁻⁹ on the masses and the exposures, and the debrief numbers to 10⁻⁸ relative. It also compares the families,
the verdicts and the refusal counts. The result is PASS, 16/16. At load the scenario replays case 1 to 3 h, in about 0.2 s headless.

### 34.11 Browser validation

All runs used the site built from this branch: `workflow.py web --native`, served locally, in headless Chromium with software WebGL.

| Run | Input | Result |
| --- | --- | --- |
| `runtime-export` (rebuild, publication, every runtime check) | headless Godot | PASS, 12/12, including the new `shared_air` check (isolate, with the 16-case parity and the replay) |
| `web_check --part training --training shared-air` | the player's own keys (desktop, 1280 × 720) | PASS, 122 actions, each answered by a key |
| the same | emulated phone touch (844 × 390, DPR 3) | PASS, 122 actions, each answered by an on-screen button |
| the same, `--rotate` | the phone turned upright mid-run ("Continue upright") | PASS, 124 actions |
| `--training shared-air-purge` | keys | PASS, 80 actions; route to the TCC, the doorway refusal |
| `--training shared-air-separate` | keys | PASS, 95 actions; sector 2 sealed with four people, the RESTORE plan ran (`restore`, `home`) |
| `--training shared-air-nocontain` | keys | PASS, 120 actions; uncontained, NOT_CONTAINED |
| Regression: `--training systems`, `deadship`, `airflow` (keys and touch) | | PASS, 2/2 each |
| Regression: `--part main` | | PASS, 67/67 |
| Regression: `--part walk` | | PASS, 8/8 |
| Play size | | 78.71 MB of the 90 MB budget, 11.3 MB headroom (Phase 2A: 78.15 MB) |

The stills `SA_1`–`SA_6` (containing, the bay, the crew report, the three debrief pages) come from the browser run with keys.

### 34.12 Performance

These are headless measurements in this container, at 60 fixed fps. They are not measurements on a phone.

| Item | Cost |
| --- | --- |
| Model step, CO₂ and NH₃ | about 32 µs (SYS-002 v2, §29) |
| Scenario per frame (mean over a whole run, 9,600–15,300 frames) | 150–190 µs |
| Worst frame, live | 10–12 ms (11.7 ms in the runtime-export check); a frame where someone changes compartment rebuilds both propagators (~6 ms) |
| Worst frame, projection | bounded by a 6 ms frame budget (it had peaked at 45 ms with 60 steps a frame and people walking home) |
| The 24 h watch | 22 ship h at ×1800 is about 45 s of real play; headless at fixed fps it finished in 8 s |
| The projection | about 0.3 s |
| Reference check at load | about 0.2 s |
| Memory | the exposure samples, one shared time array and six exposures per 10 s step: under 5 MB for 7 days |

Propagators are computed only when something changes (the model's own cache by step length); the hypothetical projection runs only
when the crew report opens.

### 34.13 Limitations and the manual playtest checklist

**Limitations.**

- Pairs are abstract, with no figures or AI.
- The doors a pair cycles leave no exchange.
- The trainee's place is frozen from the watch on.
- Sleeping places, condensate uptake and the TCC bed's capacity are not modelled (SYS-002 v2).
- The source values are PROTOTYPE.
- The stability verdict covers CO₂ removal, containment and the NH₃ residue only; there is no power, thermal or humidity model
  (Phase 2C).
- The doorway rule (the last 10 s of a compartment) is a training abstraction.
- Timing is measured headless, not on a phone.

**Playtest checklist for the owner** (`#interior-shared-air`, desktop and phone):

1. Start: the HUD says "Routine shift in sector 1" with ship time ×30 and real time shown apart. The map shows NH₃ ppm in amber in its
   corner.
2. At ship 0:10 the CAUTION alert appears. Ops opens the intercom and the clock stops; "Contain the spill" from there is refused.
3. At the store (the HYG diamond, sector 1): Use shows the store's state. Ops starts containment; step away and it pauses, keeping
   its progress; come back and Ops resumes. After 10 ship minutes it reports CONTAINED with the grams in the air and in the bag.
4. Walk to the sector 3 ECLSS bay. The board shows both gases. Use or Ops opens the control page; Use moves down it and Ops toggles
   (shut damper pairs A1P and A1N).
5. Intercom from the bay page: send your partner to A3 and watch the hollow disc walk the map. Try sending them back across the seal:
   refused, with the reason. Open the crew report: measured values apart from the amber hypothetical ones.
6. Try closing a door while pair B walks through it (send B to A3 first and leave A2P open): refused, "the doorway is occupied".
7. Declare the ring set (the watch): doors are refused, the HUD counts to 24 h at ×1800, then the 7-day projection, then the debrief.
   Read its three pages, comparing your run with the three reference strategies.
8. Ops replays from the same start.
9. On a phone: the same steps with the touch buttons. Turn the phone upright mid-run; the pages and board stay legible.

## 35. Handoff (Phase 2B "Shared Air")

| Deliverable | Where |
| --- | --- |
| A Playable DS-2 "Shared Air" | `#interior-shared-air` |
| B Containment interaction | §34.3 |
| C Crew commands | §34.4 |
| D Atmospheric controls | §34.5 (bay page, the walk's doors) |
| E Two-gas interface | §34.6 and §34.7 |
| F Stability watch | §34.8 |
| G Engineering debrief | §34.9 |
| H Validation | §34.10 and §34.11 |
| I Documentation | this section, §34.13, the roadmap §32, docs/MODEL.md |
| J Final handoff | below |

1. **What was implemented.**
   - `#interior-shared-air`: the complete Phase 2B slice on SYS-002 v2, unchanged. It covers the scenario data, the deterministic Python
     reference (`shared_air.py`, 16 cases, 18 tests) and its Godot mirror (`WfSharedAir`).
   - In play: the containment at the store, the pair orders and the bay page, the two-gas map, the bay board and the crew report, the
     watch and the projection, the three-page debrief, and the replay.
   - Validation: the parity check and four played strategies. The default experience is unchanged.
2. **Player actions.**
   - Walk, and open and close doors (Use).
   - At the store: inspect it (Use), and start, pause or resume the containment (Ops).
   - At the bay: switch the fans, the nine damper pairs, the CO₂ unit and the TCC.
   - On the intercom, anywhere on ring A:
     - switch the map layer;
     - send pair A (the partner), B or C to a sector, or tell a walking pair to hold;
     - try the containment (refused away from the store);
     - open the crew report;
     - set the plan (NONE or RESTORE);
     - declare the ring set (the watch).
   - Read the debrief, and replay.
   - Every action has a key and a touch button.
3. **Containment.** It needs the trainee's body within reach of the store, Ops, and 10 ship minutes of uninterrupted work. Stepping
   away or Ops pauses it and keeps its progress, and the store keeps leaking at the first-order rate until the work is done. Then
   `isolate_source` is called once, and what remains stays in the bag, accounted for. Nothing else grants it: no page, no order, and
   not the watch (§34.3).
4. **Crew commands.**
   - Orders go by intercom.
   - A route is the shortest path through doors that crosses no sealed bulkhead, at 40 s per compartment.
   - A door a pair stands in cannot be closed.
   - Occupancy, CO₂ and exposure follow each person step by step.
   - A refused order changes nothing.
   - The trainee is never moved (§34.4).
5. **Competing strategies remain possible.** All four families are reachable through play, and each was played to its debrief in the
   browser and headless:
   - isolate: STABLE_RESIDUE; sector 1 is still unusable after 7 d; nobody above the CO₂ target;
   - route to the TCC: STABLE; sector 1 is usable at 38–44 h; worst 1 h 13.9–20 ppm;
   - separate: CO2_LIMIT; 239 crew-hours above the CO₂ target; sector 1 usable at 41 h;
   - uncontained: NOT_CONTAINED.

   No family dominates: what clears sector 1 sooner either costs NH₃ exposure or CO₂.
6. **Model and gameplay agree.** All 16 reference cases replayed in Godot within the model's tolerance (10⁻⁹ relative), checkpoint by
   checkpoint, including the families, the verdicts, the refusal counts and the debrief numbers. Each played strategy reached its
   reference family and verdict. Every ledger closes in every case.
7. **The stability watch is physically consistent.** It continues the same state of the same model with the same step. It resets
   nothing and tunes nothing, and it changes nothing without a declared plan (the check confirms an empty post-watch log). A RESTORE
   plan runs only its listed actions, at the watch's end, and moves nobody into air above 3 ppm. The verdict never calls a
   configuration permanent.
8. **The debrief.**
   - Page 1, the ship:
     - the verdict, the family and the plan;
     - the NH₃ budget (released, retained, captured, airborne), checked against the inventory;
     - the containment time and CO₂ at 7 d;
     - the time each compartment takes to reach the reuse criterion.
   - Page 2, per person: the peak, the 1 h, 24 h and 7 d means against the SMACs, the dose, the CO₂ hours and the route.
   - Page 3: the trainee's run against the packaged isolate, purge and separate cases.

   Completed windows only. The 3 ppm criterion is labelled a training rule, not a NASA clearance. There is no score.
9. **Browser tests passed.** Everything in §34.11:
   - Shared Air with desktop keys, emulated-phone touch in landscape, and the phone turned upright mid-run;
   - the purge, separate and uncontained strategies with keys;
   - the systems, deadship and airflow trainings;
   - the main site (67/67) and the touch walk (8/8);
   - the play size, 78.71 MB.
10. **Unverified on real devices.**
    - A real phone and tablet: frame rate, the touch hit areas at real size, and page legibility in daylight. The tests run on
      software WebGL with drawing mostly off, so frame rates were not measured.
    - The watch's real duration on a phone (about 45 s by design).
    - The cost of the propagator rebuild (~6 ms headless) on a slow phone.
    - Gamepad input (the bindings exist but were not exercised).
    - A person's first playthrough without guidance: the owner's checklist, §34.13.
11. **Still PROTOTYPE.**
    - The source: 7 g, τ = 1 h, in hygiene A.
    - The scenario timings: the 10 min alert, the 10 min containment work, the 40 s per compartment, the 10 s doorway, ×30 and ×1800.
    - The 3 ppm reuse criterion and the 24 h watch with the 7 d projection.
    - The three-pair crew placement.
    - From earlier phases: the TCC (15.3 m³/h, 0.95), the IMV values (DS-O7), and the ring's volumes and occupancy (DS-O1).
    - The SMACs are an external reference, not Wayfarer's medical limit (OPEN).
12. **Phase 2C** (proposal only; it needs its own authorization).
    - Keep the shared-air model fixed and add only what the debrief currently names as "not modelled". The first candidate is the TCC
      bed's finite capacity, which makes routing to the TCC cost something.
    - Then, with the owner's sign-off, real crew rest and sleeping places, so that separation has a time cost.
    - Power, thermal and humidity stay outside until a gate shows that a choice in this scenario depends on them.
    - Before any of this, the owner's playtest (§34.13) should confirm that the four strategies read as real choices.

## 36. Phase 2B finalization [BUILT P2B-F; owner brief 2026-11-15]

The validated engineering model (SYS-002 v2) is unchanged. §34 and §35 keep their historical results; this section records what
changed after them and why.

### 36.1 Gate versus play: why the separation failed

The gate's representative separation (§30.5, `ds2b_gate.py`, arcs `12:Hb 23:Ha 31:B`, all six to sector 2, reconnect at 4 h) was viable.
The playable reference `separate` (§34.10, case 3) ended in CO2_LIMIT with 239 crew-hours above the target. Both were rerun and scored
on the gate's own definitions (`ds2b_reconcile.py`, `ds2b_reconcile.json`). The gate's metrics are 24 h figures; the debrief's dose and
crew-hours are 7-day figures, which is why §34.10 shows 239 crew-hours where the 24 h figure is 131.

| Property | Engineering gate (§30.5) | Playable case 3, before | Playable case 17, after |
| --- | --- | --- | --- |
| Initial state | ring normal (doors closed, fans and dampers open, both units on), CO₂ steady state, crew 2/2/2, 7 g at τ 1 h from t = 0 | the same (`ring_air.start`, the same source) | the same |
| Containment | 10–20 min, by sector 1's off-shift pair member, **in parallel** with the ring being set | 15–25 min, by the trainee, **before** anything else (the Godot play: 11.5–31 min) | 15–25 min |
| When the ring is set | at 10 min, **every door and damper at once by remote "Ops"** | the trainee reaches the bay at 27.5 min and shuts the dampers at 30 min | the same |
| Crew positions | all six to sector 2; the containing person walks A1 → A2 **through the sealed A1P** (the gate cycles any door) | partner, B, C and the trainee in sector 2; the trainee reaches it by sector 3 (the purge path) and A3N | the same |
| Doors | arc 3–1 doors open (`B`), corridors AC1/AC2 joined to sector 2, A1P and A3N sealed | every door closed behind the trainee; A1P and A3N sealed by their dampers | arc 3–1 doors left open by the trainee (the gate's `B`); A1P and A3N sealed |
| Ventilation | per arc state at 10 min | fans on; dampers A1P and A3N shut at 30 min | the same |
| Reconnection | at 4 h: every damper open **and every door closed (remotely)** | **none until the watch's end at 24 h**; the CO₂ limit passed at 5.29 h | at 4 h, scheduled at the bay: every damper pair open, fans on, **doors untouched** |
| At 24 h | ring normal, **everyone placed at home instantly** | RESTORE: dampers, fans and units, doors closed remotely, people walk home under 3 ppm | RESTORE: dampers, fans and units only, people walk home under 3 ppm |
| CO₂ peak where people were | 0.433 % | 1.708 % | 0.419 % |
| CO₂ crew-hours above 0.3 % (24 h) | 82.5 | 130.9 | 39.6 |
| NH₃ worst 1 h / worst 24 h mean | 9.1 / 4.4 ppm | 13.9 / 7.0 ppm | 13.9 / 6.5 ppm |
| Crew mean 24 h NH₃ dose | 99.9 ppm·h | 162.1 ppm·h | 148.8 ppm·h |
| Every compartment under 3 ppm after | 28 h | 41.5 h | 37.3 h (A1 36.9 h) |
| Verdict | viable | CO2_LIMIT | STABLE, with degraded CO₂ control |

**Root causes, in order of effect:**

1. **No reconnection before the limit.** The play offered only the RESTORE plan, at the end of the 24 h watch. Sector 2, sealed with
   its crew and without the CO₂ unit, passes 0.5 % at 5.29 h. The gate reconnected at 4 h, at 0.43 %. This alone turns the verdict:
   with a reconnection at 4 h, case 3's own configuration is STABLE (peak 0.42 %).
2. **Configuration time.** The gate sets the whole ring at 10 min by remote control while another person contains the spill. A single
   trainee must contain the spill first and then walk to the bay, so the ring is set at about 30 min, after the ducts have carried NH₃ into every compartment. The
   gate's own separation, rerun with the crew acting at 15 and 30 min, restores the ring in 35 h and 48 h instead of 28 h. This is why
   the separation's advantage over the purge shrinks in play; it is the play's honest consequence of one trainee, not a model error.
3. **The purge path's doors.** The gate opens the arc 3–1 doors; case 3 closed them behind the trainee. Leaving them open (case 17) cuts
   the CO₂ crew-hours from 74.7 to 39.6 and restores A1 0.7 h sooner.
4. **Remote doors and instant homecoming.** The gate's reconnection and its 24 h return close doors remotely and place everyone at home.
   The play keeps doors physical (§36.2) and walks people home through air under 3 ppm. This changes the late projection only slightly.
5. **Smaller differences:** containment 5 min later (2.39 g released instead of 1.98 g); the trainee's route through sector 3.

### 36.2 The selected solution: a scheduled reconnection (Option A)

The gate's reconnection moves dampers and fans, which are remote equipment at the sector 3 ECLSS bay. Its door closing is a gate
abstraction and is not needed for the result. So the smallest faithful change is Option A, a scheduled operation at the bay. Option B
(an intervention checkpoint) would be needed only if the recovery required doors; it does not, and it was not built.

- **At the bay:** the item "Scheduled reconnection: none -> T+2:00 ..." sets the next offered time (2, 3, 4, 5, 6 or 8 h after the
  release, `[watch] reconnect_options_h`) or cancels it.
- **What it does:** at that ship time, in any phase, the bay opens every damper pair and runs the fans. Doors are never moved remotely.
- **Refusals:** a schedule is refused if its time has passed, if it is off the 10 s step, if it is after the watch's end, or if it is
  changed during the watch.
- **Visibility:** it is logged (`reconnect`), shown in the watch's HUD line, the watch announcement, the bay page and the debrief's
  decisions. It runs only because the trainee declared it, and nothing else changes.
- **Order at a step boundary:** the due actions, then the due reconnection, then the walks and the model step. A test confirms that a
  damper shut at the same boundary is reopened by the reconnection.
- **RESTORE now moves remote equipment only:** every damper pair, the fans, the CO₂ unit and the TCC. The doors stay as the trainee left
  them. In the existing cases the doors were already closed, so their numbers are unchanged.

### 36.3 Operational target versus control limit

- **Verdict:** it stays as defined in §34.8. CO2_LIMIT means 0.5 % was passed where people were. Exceeding the 0.3 % target is not a
  failure.
- **New verdict fields:** `co2_peak_pct` and `co2_peak_h` (the highest CO₂ where anybody was, live and in the watch),
  `co2_above_target_crew_h`, and `degraded` (stable, but above the target for a time).
- **Debrief:** it shows the peak, the crew-hours above the target, and the 0.3 % / 0.5 % levels as Wayfarer's PROTOTYPE operating
  levels, not injury thresholds. The headline reads "Stable, with degraded CO₂ control" or "Operational failure: CO2 control limit".
- **Unchanged:** the NH₃ SMACs and their duration-specific wording.

### 36.4 Reference results, before and after

Cases 1–16 are unchanged, and so are their numbers (§34.10). The new cases are listed below.

| Case | Family | Verdict | CO₂ peak | CO₂ crew-h above target (7 d) | worst 1 h / 24 h / 7 d (ppm) | A1 reusable | Refusals |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3 separate (no reconnection, historical) | SEPARATE | CO2_LIMIT | 1.71 % | 239.5 | 13.9 / 7.0 / 2.00 | 41 h | 0 |
| 17 separate_reconnect (4 h) | SEPARATE | STABLE, degraded | 0.42 % | 39.6 | 13.9 / 6.5 / 1.80 | 37 h | 0 |
| 18 separate_late (6 h) | SEPARATE | CO2_LIMIT | 0.55 % | 89.5 | 13.9 / 6.4 / 1.77 | 37 h | 0 |
| 19 reconnect_refused | SEPARATE | STABLE, degraded (identical to 17, every checkpoint) | 0.42 % | 39.6 | 13.9 / 6.5 / 1.80 | 37 h | 4 |
| 20 reconnect_cancelled | SEPARATE | CO2_LIMIT | 1.71 % | 233.1 | 13.9 / 7.0 / 1.98 | 41 h | 0 |
| 21 replay_reconnect | identical to 17 | | | | | | |

The reference player (`shared_air.play`, and its Godot mirror) now also delivers actions after the watch begins, so each one is
refused and logged as the runtime does. Case 19's cancellation during the watch exercises this.

### 36.5 Strategy viability

The scoring follows the gate's rules (§30.3): ε on each objective, viability being no occupied compartment over 0.5 % within 24 h, and
`ds2b_reconcile.json` as the source.

| Strategy (reference timing) | Viable | Worst 1 h | Crew 24 h dose | CO₂ crew-h above target (24 h) | CO₂ peak | Every compartment under 3 ppm | Dominated? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Isolate, no plan (case 1) | yes | 14.8 | 131.9 | 0 | 0.22 % | not within 7 d | no |
| Isolate, restore at 24 h (case 15) | yes | 13.9 | 129.3 | 0 | 0.26 % | 44.9 h | no |
| Purge (case 2) | yes | 13.9 | 152.5 | 0 | 0.17 % | 38.4 h | no |
| Separate, reconnect at 4 h (case 17) | yes | 13.9 | 148.8 | 39.6 | 0.42 % | 37.3 h | no |
| Separate, reconnect at 6 h (case 18) | **no** (0.55 %) | | | | | | |
| Separate, no reconnection (case 3) | **no** (1.71 %) | | | | | | |

With the trainee containing at the alert (the fastest a single trainee can be), the same three are viable and non-dominated:

| Strategy | Crew 24 h dose | CO₂ crew-h | Restore (h) |
| --- | --- | --- | --- |
| Isolate, restore | 104.1 | 0 | 39.4 |
| Purge | 126.7 | 0 | 32.3 |
| Separate, reconnect at 4 h | 122.3 | 42.2 | 31.1 |

**The trade, honestly stated.**

- **Isolation** gives the lowest crew dose and keeps sector 1 out of use longest.
- **The purge** costs no CO₂ and clears sooner.
- **Separation with a timely reconnection** clears soonest with a slightly lower dose than the purge, at the price of hours of degraded
  CO₂ control and a hard deadline (about 5 h for six people sealed, about 6.4 h for five).

In play the separation's margin over the purge is small: about 1 h of restoration and 3–4 ppm·h of dose. The reason is root cause 2: a
single trainee sets the ring 20 minutes later than the gate's crew. The physics was not changed to widen the margin.

### 36.6 Gameplay and usability review

Method: the stills from each browser run and the HUD and page texts in every phase were read as a first-time player would see them,
checking what is shown against what the model does. This is a review of what appears on screen, not a human playtest; the owner's
playtest (§36.10) remains to do.

**Found and fixed:**

| Problem | Fix |
| --- | --- |
| The walk's tour checklist ("Ring A [x] board … Learning points 0/9") filled the left panel in Shared Air, unrelated to the task | Hidden while Shared Air runs; the panel shows the seven stages, the source line and the hint |
| Nothing told the player that a pair had arrived, or that a pair stopped at a sealed door | HUD news: "Intercom: pair C arrived in A2." or "… stopped in A3: the next bulkhead, A3N, is sealed" |
| Damper items did not say what shutting one does when its door is shut or open | Each item says the consequence: "door shut, so this seals A1P", "door open, so air still passes", "unseals …" |
| Doors, dampers and units were not related anywhere on the bay page | One line: air crosses a bulkhead by its door if open and its damper pair if open; sealed only when both are shut; doors are worked where they are, dampers and units from the bay. The unit line says which gas each unit removes |
| Separation could not succeed; the debrief's family text promised it "clears soonest" without the CO₂ cost being survivable | The scheduled reconnection (§36.2); the family texts name the deadline; the comparison page shows separation with and without reconnection |
| The watch's HUD line used decimal hours and did not say what was declared | "Verify: stability watch, ship T+h:mm of 24 h (x1800), plan …, reconnection scheduled at T+4:00 · real m:ss"; the projection line says "computed ahead" |
| The debrief opened on a dense ship table | A first page answers what happened, what you did, what was saved, what was sacrificed and whether it holds; then the ship, the crew, the alternatives (4 pages) |
| After the projection the HUD still said "the 7-day projection runs now" (fixed in 4190a8a) | "7-day projection complete: … The debrief shows what was saved and what it cost." |
| Stepping the reconnection time to 4 h listed each step ("set for T+2:00 · T+3:00 · T+4:00") in the debrief's "What you did" | Consecutive settings count once, as the last value (Python and Godot) |
| In a 1024×600 window the bay page ran past the bottom of the screen and the checklist's hint ran into the prompt | On a desktop the page's type steps down (15 to 12 px) until it fits; the checklist shows only the lines that fit above the prompt |

**Reviewed and kept:**

| Area | Why kept |
| --- | --- |
| The alert | The CAUTION banner, the "odour … in A1" text, and the NH₃ layer as the map's default |
| Onboarding | The stage objectives name tools and constraints, not a solution ("Choose how to handle the residue: doors, ducts and units at the ECLSS bay, the other pairs by intercom") |
| The NH₃ explanation | Hygiene A's page states what the source is (hydrolysed urine giving off ammonia) and that only the TCC removes it |
| The map | It shows one gas at a time, with its unit in the corner, and the pairs as discs that are hollow while walking, with a line to the destination |
| Pairs passing doors | The leaves do not move. The map shows the pair crossing, the door's state is the trainee's, and the model counts no exchange (§34.1). Animating leaves would need figures and was not added |
| Gamepad | Untested here (no device in the container) |
| The bottom prompt partly behind an open page on a desktop | The open page repeats what the prompt says; the prompt shows in full when the page closes |

### 36.7 Validation results

| Check | Result |
| --- | --- |
| Python tests | 302 OK (1 skipped); `tests/test_shared_air.py` 23 (5 new: reconnection outcome, remote-only, refused/cancelled, boundary, event order) |
| Python/Godot parity (headless, all 21 cases) | 21/21 within the model's tolerance, plus the debrief's CO₂ peak |
| Godot strategies played through Use and Ops (headless) | isolate ISOLATE/STABLE_RESIDUE (with replay); purge ROUTE/STABLE; separate (reconnect 4 h) SEPARATE/STABLE, degraded, peak 0.35 %; separate_late (8 h) SEPARATE/CO2_LIMIT, peak 0.56 %; nocontain UNCONTAINED/NOT_CONTAINED — all PASS, the watch running only declared operations |
| runtime-export, web build, browser runs | §36.8 |

### 36.8 Browser, runtime, performance and size

The checks below were run on the branch with the web build `workflow.py web --native` and `tools/web_check.py`. They use headless
Chromium with software WebGL. The stills from the browser runs are in
`/mnt/project-files/deadship_phase2b_final_2026-11-15/` (not committed).

| Check | Result |
| --- | --- |
| `runtime-export` | PASS, 12 Godot checks including `shared_air` (run `20261115T081935257749Z-runtime`) |
| Web build | PASS; `play/` 79.0 MB of the 90 MB budget (11.0 MB headroom; was 78.7 MB before this finalization) |
| Shared Air, keys, 1280×720 (isolate, then replay) | PASS: ISOLATE / STABLE_RESIDUE, replay restarts at A1 |
| Shared Air, emulated phone landscape with touch buttons | PASS (same strategy) |
| Shared Air, emulated phone turned upright mid-run | PASS (same strategy; the page and the HUD re-place themselves) |
| Shared Air, keys, 1024×600 (`--desktop`) | PASS (same strategy) |
| Purge, keys | PASS: ROUTE / STABLE, CO₂ peak 0.18 % |
| Separate with reconnection at 4 h, keys | PASS: SEPARATE / STABLE, degraded, peak 0.35 %; after the watch only the declared reconnection, RESTORE and the walks home |
| Separate with reconnection at 8 h, keys | PASS: SEPARATE / CO2_LIMIT, peak 0.56 % (over 0.5 % at T+6.9 h) |
| No containment, keys | PASS: UNCONTAINED / NOT_CONTAINED |
| Regression: systems, Scrubber (`deadship`), airflow (keys and touch) | PASS |
| Regression: `--part main` (start page, Explore Ship, Interior and Exterior launchers, controls, phone viewer) | PASS 67/67 |
| Regression: `--part walk` (the touch walk, boarding hatch) | PASS 8/8 |

The ring tour, boarding, doors, ladders and bindings are covered by `runtime-export`'s Godot checks. The phone runs emulate an
844×390 landscape screen and its 390×844 upright turn with touch input. They are not a real device.

**Simulation cost per frame.** This is the Shared Air machine's own time inside a frame, measured by the scene.

| Where | Largest single frame | Total over the whole run |
| --- | --- | --- |
| Godot headless | 8.7–14.5 ms | 1.6–2.9 s over 9.7k–15.3k frames |
| Browser, software WebGL, keys | 11–19 ms | 2.9–3.6 s |
| Browser, software WebGL, touch | 22.7 ms | |

The largest frame is the projection step. The watch and the projection are spread over frames, as before (§34.11). Software rendering
on a container CPU is not a phone measurement, so real-device frame rates remain untested (§38 question 13).

### 36.9 Remaining PROTOTYPE limitations

§34.13 still applies, with these additions:

- The reconnection options are whole hours (2–8 h).
- A single trainee cannot act as fast as the gate's crew.
- The separation's advantage in play is small (§36.5).
- Doors that pairs cycle remain an abstraction.
- Gamepad input and real phones are untested.

### 36.10 Owner playtest guide

**How to play.** Before deployment there is no public URL. On the workstation, build and serve the site locally:

```
python3 tools/workflow.py web --native --characters <play-characters dir> --out /tmp/wf-site
cd /tmp/wf-site && python3 -m http.server 8000
```

Then open `http://localhost:8000/play/#interior-shared-air`. The release sequence: approve the squash, deploy through the established
workflow, then play on real devices; corrections come in a separate change.

**Sessions to play:**

1. **Desktop keys, first time, no coaching.** Read only the HUD.
   - Does the alert make you look at the map?
   - Can you find hygiene A and contain the spill?
   - Do you know when it is contained?
   - Is the step from containment to the decision clear?
2. **Isolate.** Send your partner to A3, shut A1P and A1N at the bay, and declare the watch. Read all four debrief pages.
3. **Replay as a separation.**
   - Leave the short way open.
   - Send the partner and pair C to A2.
   - Shut A1P and A3N.
   - Schedule the reconnection at 4 h.
   - Declare the watch with RESTORE.

   Watch the reconnection appear at T+4:00, and compare the debrief's CO₂ cost and A1 time with session 2.
4. **Replay too late.** The same as session 3, with the reconnection at 8 h. Expect "Operational failure: CO2 control limit".
5. **Phone, landscape then portrait.**
   - Repeat session 3 with the touch buttons.
   - Turn the phone upright on the bay page and in the debrief.
   - Check that the buttons, the map and the page do not overlap, and that the HUD returns after closing a page.

**For each session, judge:**

- Is it understandable?
- Does navigation feel natural?
- Is containment satisfying?
- Are the orders intuitive?
- Does the choice feel meaningful?
- Is the watch clear?
- Does the debrief explain the outcome?

### 36.11 Release recommendation

The branch is ready for the owner's review and playtest. If it is approved:

1. Squash `claude/project-thread-dfyyv7` onto `main` as one commit (AGENTS.md step 5).
2. Run the full pipeline gate if any geometry changed. None did: Deadship touches no geometry.
3. Deploy through the established Pages workflow.
4. Play on real devices.
5. Make corrections as a new change.

## 37. Phase 2C research: a finite TCC bed? [RESEARCH ONLY; nothing implemented]

The question: does a finite NH₃ capacity in the trace-contaminant-control bed create a new, real decision, without shrinking the bed to
make one?

### 37.1 Sources

| Source | What it gives |
| --- | --- |
| ISS TCCS charcoal bed | About 22.7 kg (50 lb) of phosphoric-acid-treated activated carbon (Barnebey-Sutcliffe 3032), expendable, not regenerated, replaced periodically; pre-flight service life one year; flight experience longer than two years; ~15 m³/h process flow (Perry et al., NASA TCCS status papers; NASA/TP-2017-218235; SAE 2009-01-2353) |
| Post-flight bed analysis | The flight carbon held 11.9 mg NH₃/g at the ISS cabin's ~0.2 ppm (SAE 2003-01-2487, as cited in NASA NTRS 20180004945) |
| Ammonia sorbent comparison | At 5 ppm moist NH₃: Chemsorb 1425 21.8 mg/g, Ammonasorb II 21.1 mg/g, Barnebey-Sutcliffe 3032 12.9 mg/g; humidity lowers capacity (water in the pores) (NASA NTRS 20180004945) |
| Humidity and impregnants | Phosphoric-acid impregnants are hygroscopic; above ~20 % impregnant beds can condense and leak acid in humid air (US patent literature on acid-impregnated carbon) |
| Crew load | Metabolic NH₃ about 50 mg per person per day (48.6 in a later review) (NASA NTRS 20190030376, trace-contaminant load model) |

ntrs.nasa.gov is not reachable from this container, so the figures come from the search engine's extracts of those papers. They need a
direct reading before any value becomes canon.

### 37.2 Capacity against the scenario

- **A bed like the ISS one** (22.7 kg at 12–22 mg/g) holds about **270–500 g of NH₃**. A design would derate it for the
  breakthrough front, so call it about 200–400 g usable.
- **Shared Air captures 1.9–2.4 g** in the playable strategies, and 7 g at most (the whole inventory). That is **0.5–3 % of a fresh
  bed**.
- **Twelve crew at 50 mg per person per day load 0.6 g/day.** A bed then lasts about 1–2 years, which is consistent with the ISS's
  observed service life.

**Conclusion.** A realistically sized, ordinarily serviced bed does not notice this event: finite capacity is irrelevant to Shared Air.
It matters only for a bed near the end of its service interval, or in a much larger release. Shrinking the bed to create a constraint
is excluded.

### 37.3 Options compared

| Option | Physical plausibility | Complexity | Reuse | Gameplay significance |
| --- | --- | --- | --- | --- |
| A Finite capacity (loading L, capture efficiency falling as the front nears the outlet) | High; standard constant-pattern breakthrough | Low: one state, one efficiency curve, a ledger term | Every trace species, every scenario | Low for Shared Air with a fresh bed; real only near end of life |
| B Limited replacement media | High for a multi-year voyage: ~0.6 g/day of NH₃ alone uses roughly one 23 kg bed every 1–2 years | Low as logistics, none in the air model | Mission logistics, a ship-level consumables budget | Long-term, not inside a 7-day scenario |
| C Degraded or nearly spent bed (a prior event, humidity, age) | High: beds are replaced on loading, and humidity cuts capacity | A as its basis, plus an initial loading | Scenarios that start "the bed is due" | **Real:** with a bed near breakthrough, purging through the TCC risks breakthrough and a bed change takes time and a spare, so isolation, the purge and the separation trade differently |
| D Defer | — | — | — | A neighbour such as humidity is ruled out by the Phase 2B brief's scope |

### 37.4 Recommendation

**Finite capacity is a justified model, but a scenario should not be built on it before a gate.** The smallest useful Phase 2C
milestone:

1. **A bed-loading state in SYS-002.** L (kg of NH₃), with a source-backed capacity and a breakthrough efficiency η(L), for example
   constant η until the front reaches the outlet and then a logistic fall. It is PROTOTYPE until the owner picks the media.
2. **A gate study** like §30. Run Shared Air from a bed at 0, 90 and 98 % loading, and ask whether a new non-dominated decision appears
   (for example, isolate and change the bed first, against purge through a nearly spent bed).
3. **Only if it passes,** a scenario variant. The bed change is a physical task at the bay with a spare from stores.

The answer to "Is finite capacity justified as Phase 2C's first feature?": as a model, yes; as a gameplay feature, only with a bed near
the end of its life, which the gate must show creates a real choice. Fresh-bed Shared Air would not change.

## 38. Handoff (Phase 2B finalization)

Answers to the brief's questions 1–15. Evidence is in §36 and §37.

**Commits on `claude/project-thread-dfyyv7`:**

| Commit | Change |
| --- | --- |
| 6034ad9 | Reconciliation study (`ds2b_reconcile.py` and `.json`) |
| 9d7fe28 | The scheduled reconnection, remote-only RESTORE, CO₂ peak, tests |
| 70c9657 | Godot mirror and UI |
| 60cee05 | `web_check --desktop` |
| 1687fd4 | Debrief de-duplication |
| 624c4e4 | Small-window layout |
| The docs commit after 624c4e4 | This report, MODEL, TODO, IMPLEMENTATION |

1. **Why did the separation exceed the CO₂ limit?** Sector 2, sealed with its crew and without the CO₂ unit, passes 0.5 % about 5.3 h
   after the release. The play offered no way to reconnect before the watch's end at 24 h (§36.1).
2. **Which differences caused it?**
   - The missing reconnection at 4 h. This decides the verdict.
   - The configuration time: the gate sets every door and damper at 10 min, the trainee sets them at about 30 min. This decides the
     size of the advantage.
   - The purge path's doors, the remote door closing and instant homecoming in the gate, and a 5 min later containment (§36.1).
3. **What solution was selected?** A scheduled duct reconnection at the ECLSS bay (Option A). It moves dampers and fans only, is
   declared and logged, and runs in any phase. RESTORE no longer moves doors (§36.2).
4. **Can the player now execute a viable separation strategy?** Yes. It was played through Use and Ops (headless and in the browser)
   with the reconnection at 4 h: STABLE, with degraded CO₂ control.
5. **What are its measured consequences?**
   - Reference case 17: CO₂ peak 0.42 %, 39.6 crew-hours above the target, under the limit; worst 1 h NH₃ 13.9 ppm, worst 24 h
     6.5 ppm; crew 24 h dose 148.8 ppm·h; A1 reusable after 37 h.
   - Godot play (five sealed, the trainee at the bay): peak 0.35 %.
   - Reconnecting at 6 h (six sealed) or 8 h (five sealed) passes the limit.
6. **Do at least two successful non-dominated strategies remain playable?** Three do: isolation, the purge, and separation with
   reconnection, at the reference timing and at the fastest timing (§36.5). The separation's margin over the purge is small (§36.5).
7. **Which usability problems were found and fixed?** See §36.6.
8. **Does the watch execute only authorized operations?** Yes. The Python tests and the Godot check fail on any post-watch operation
   other than a declared reconnection, the RESTORE plan's own actions and the walks home. Changes during the watch are refused and
   logged.
9. **Are all atmospheric inventories conserved?** Yes. The CO₂, NH₃ and release ledgers close in all 21 cases (tests), and the Godot
   debrief check confirms them in play.
10. **Do Python and Godot agree?** Yes: 21/21 cases checkpoint by checkpoint at relative 10⁻⁹, plus the debriefs, verdicts, families
    and refusal counts.
11. **Which browser and runtime checks passed?** Every check passed (§36.8):
    - `runtime-export`: 12 Godot checks.
    - Shared Air in Chrome, all five strategies: keys, touch, the upright turn and a 1024×600 window.
    - Regression: systems, Scrubber, airflow, main (67/67) and walk (8/8).
12. **What was measured for performance and download size?**
    - `play/` is 79.0 MB of the 90 MB budget, leaving 11.0 MB headroom.
    - The largest Shared Air frame is 8.7–14.5 ms headless and 11–23 ms in software-rendered Chrome (§36.8).
13. **What is untested on real hardware?**
    - Phones and tablets: frame rate, touch sizes, readability.
    - Gamepads.
    - The watch's real duration.
    - A first-time human player.
14. **Is the branch ready for a squash and release review?** Yes, for the owner's review and playtest (§36.11). Nothing was squashed,
    merged or deployed.
15. **Is finite TCC capacity justified as Phase 2C's first feature?** As a model, yes. As a gameplay feature, only for a bed near the
    end of its service life, and only after a gate shows it creates a real choice (§37.4).

## 39. Phase 2C gate G1: does a finite TCC bed create a decision? [ENG; gate FAILED as a gameplay generator]

Owner brief 2026-11-15 13:54Z ("Complete Phase 2 and Phase 3"). The §37 recommendation was tested before anything was built on it.
Study: `work/project-thread-dfyyv7/ds2c_tcc_gate.py` (about 3 min) and its result `ds2c_tcc_gate.json`. Task study only; nothing in the
build reads it.

**Model (PROTOTYPE).**
- A Bohart–Adams irreversible-reaction bed solved by the method of lines: K = 20 segments, NTU = 30 for the whole bed.
- The flight bed's sharp front needs at least ln 600 = 6.4 per fifth of the bed, so NTU = 30 meets it.
- SYS-002 v2's 0.95 single-pass efficiency is kept as a flow factor (bypass and channelling), so a fresh bed reproduces v2.
- Initial loading is laid down by the same model at a low inlet concentration, so the front has the model's own shape.

**Sources.**
- The 22.7 kg phosphoric-acid carbon bed (B-S 3032) at 15.29 m³/h, expendable (NTRS 20060005220).
- Stoichiometric chemisorption: 0.56 mmol/g of available acid gives 215.9 g NH₃ per bed; the conservative 0.26 mmol/g gives 100 g.
- The flight bed's segment profile after 2,595 h, and the moist-gas capacities at 5 ppm (ICES-2018-253, NTRS 20180004945).
- Humidity moves capacity by tens of percent in either direction. It is carried as the capacity range (216 g against 100 g), not as a
  separate law.
- ntrs.nasa.gov is unreachable from the container, so the figures come from extracts. They need a direct reading before any value
  becomes canon.

**Result.** The four Shared Air strategy families (isolate with restore, isolate without a plan, purge, separate with a reconnection
at 4 h) were rerun at 0, 90, 98 and 99.5 % bed loading, for both capacities.

| Bed | Loading | What changes |
| --- | --- | --- |
| 216 g or 100 g | 0 %, 90 %, 98 % | Nothing that matters. Every strategy keeps its verdict. The non-dominated front is unchanged (no strategy dominates another). Isolation's 7-day residue grows (0.64 to 1.37 ppm at 98 %), still inside the reuse criterion. |
| 216 g or 100 g | 99.5 % | Both isolation strategies become dominated by the purge and by the separation. The near-spent bed removes a choice instead of adding one. |

**Verdict: FAILED as a gameplay generator.** The gate asked whether a new, non-dominated decision appears. Only a bed at the very end
of its life, beyond the ISS's ordinary replacement point, changes the front at all, and then it removes options. No bed was shrunk to
force a result. Finite TCC capacity stays a valid model extension (§37.3 A) for a later scenario. It is not Phase 2C's driver.

Phase 2C therefore went to the design's original content (§5.8 DS-2): two interacting problems, humidity and cabin heat stocks, parts
as entities and a second ring. That needed a new reusable model, SYS-003 (§40).

## 40. SYS-003 ring services: heat, humidity, CO₂, cooling, power and parts [BUILT; VALIDATED]

`src/wayfarer/ring_services.py` (pure, standard library), its package `wf_ring_services.json` and the Godot mirror
`godot/scripts/systems/ring_services.gd` (`WfRingServices`).

The model is a reusable engineering state. It knows nothing of scenarios, input or scores. The scenario layer (§41, §42) only
switches, isolates, moves parts and sets the crew.

### 40.1 What it models

**Scope and air.**
- Two habitat rings, each one well-mixed air volume of 466.4 m³. That is ring A's nine compartments summed (`ring_air`), with ring B
  its mirror. This is SYS-001's resolution; compartment transport stays SYS-002's job.
- The rings share no air. Only people and carried parts cross, in a stated transfer time.
- Each ring carries three states: cabin temperature T, vapour mass m_w and CO₂ mass m_c.
- The crew's sensible heat (73.0 W), vapour (2.27 kg/d) and CO₂ (the owner's 1.0 kg/d) come from NASA BVAD 2022 and from SYS-001.
- Every watt of electrical load in a ring ends as heat in that ring's cabin.

**The cooling chain.**
- A cabin heat exchanger (CHX) fan draws air over a counterflow coil (ε-NTU, a fixed UA).
- A proportional temperature control valve sets the coil's air share, with a 15 % minimum so the coil keeps condensing.
- Two coolant pumps (P1, P2), each a part, carry the coil's heat. One pump halves the coolant capacity rate: the coil runs warmer and
  condenses less.
- A heat pump lifts the coolant heat into the ring's 320 K cold loop (thermal.loops.cold, WORKING).
  - Its COP is 0.5 of Carnot (thermal.loops.architecture, WORKING) and its capacity is finite.
  - Cabin heat at 297 K cannot reach a 320 K radiator without work (thermal.loops.separation_rule, BASELINE).
- Condensation follows from the coil surface temperature against the cabin dew point (Magnus, Alduchov–Eskridge), solved by four
  fixed substitutions that Godot repeats.
- The heat pump has two setpoints: normal (4 °C supply) and economy (12 °C). Economy has the better COP and draws less work, but the
  coil is warmer, so the cabin dries less.

**Electricity** (a PROTOTYPE architecture on the spec's two generators and buses A/B, BASELINE).
- G1 feeds bus A and G2 bus B while the fusion plant runs.
- The main battery (2 MWh usable, WORKING) feeds each bus through its own converter, BC-A or BC-B. Each converter is a part with a
  40 kW rating.
- A tie breaker joins the buses.
- A bus asked for more than its sources can give trips, and stays dead until its breaker is reset.
- Each ring's survival packs carry only that ring's survival loads, and only when its bus is dead. The loads are the spec's
  LIFE_SUPPORT, FLIGHT_COMPUTER, COMMS, EMERGENCY_LIGHTING and CRITICAL_PUMPS_VALVES (survival_reserve, BASELINE). The capacity is
  OPEN, so 8 kWh per ring is PROTOTYPE.
- The fusion restart charges the pulse bank (200 kWh, WORKING) from the battery before ignition.
- A load without power does not run, whatever its parts.

**Parts.**
- Line-replaceable units in three families: the ECLSS process fan (common to the CO₂ unit and the CHX), the coolant pump, and the
  battery converter.
- A part fits a slot only within its family. It is always in exactly one place: a slot, a shelf, a store or a carrier.

**Steps.**
- At each step's start the model settles the switchboard: which loads run and where their power comes from.
- It then advances one classical RK4 step. The heat pump's draw follows the cabin through the step.
- Stores are clamped at empty, with the shortfall recorded.

### 40.2 Ledgers (closed in every case, Python and Godot)

| Ledger | Identity |
| --- | --- |
| Water, per ring | m_w + condensed = m_w0 + generated |
| CO₂, per ring | m_c + removed = m_c0 + generated |
| Cabin heat, per ring | C (T − T0) + removed = crew sensible + electrical |
| Coolant, per ring | rejected = removed + latent + heat-pump work |
| Energy | battery drawn + packs drawn + generated = loads served (plus the pulse-bank charge); battery E0 − E = drawn |
| Parts | every part in exactly one place; none made or lost |

### 40.3 Normal state (`python3 src/wayfarer/ring_services.py`)

After 6 h with six people, ring A sits at:
- T 23.98 °C, RH 0.392, dew point 9.2 °C, CO₂ 0.151 %;
- coil 8.0 °C, condensation 0.567 kg/h;
- heat pump 4.16 kW of work against 13.06 kW of sensible heat.

Ring B, empty and normal, sits at 23.86 °C. Every ledger closes to about 10⁻¹³ kg and 10⁻⁶ J.

### 40.4 Parity

`WfRingServices.load_package` replays the package's model proof (two rings, faults, parts moved, a trip and a reset) to its
checkpoints at relative 10⁻⁹ before anything is shown. The proof passes in Godot: about 120 ms native, `model_verify_ms` in the check
notes.

Tests: `tests/test_ring_services.py` (8). They cover:
- a normal ring holding in band;
- a CO₂ fan failure rising to the limit, and a pump failure warming the cabin;
- no temperature change without a flow;
- condensate only below the dew point;
- parts in one place and compatible;
- overload trips, with the packs carrying only survival loads;
- a deterministic proof.

## 41. DS-2C "Borrowed Air" [BUILT; VALIDATED; PLAYABLE (headless and browser)]

`#interior-borrowed-air` (`-- --borrowed-air`); scenario `data/deadship/ds2c_borrowed_air.toml`, scenario values only (PROTOTYPE).
`ship_ops.load` refuses engineering keys.

The reference machine is `src/wayfarer/ship_ops.py` (`Run`). The Godot mirror is `godot/scripts/deadship/ship_ops.gd` (`WfShipOps`).

### 41.1 Premise

- In ring A, the CO₂ unit's fan stops and coolant pump 1 seizes in the same hour.
- No spare is in reach. The one spare ECLSS fan went into this unit at the DS-1 repair, and pumps are kept in the service module,
  out of reach while the rings turn.
- Ring B is empty and whole, but it is in coast setback: 12.3 °C and RH 0.60, with its CO₂ unit, lights, lab, galley and Garden off.
  That is the model's own 72 h equilibrium, not a chosen number.
- The two ECLSS fans of each ring are one family, and so are their pumps.
- The trainee is pair A's first member. Pairs B and C are abstract crew who take orders by intercom.

### 41.2 The player's steps (13, all by Use and Ops)

1. Hear the caution and read the ring readings on the map.
2. Walk to sector 3's ECLSS bay.
3. Inspect the CO₂ unit: process flow none, its fan FAILED.
4. Inspect coolant pump 1: no flow with power on.
5. Inspect the heat exchanger: it is the one fan that both cools and dries.
6. Check the shelf, with no spare on it.
7. Ask ring B's machines by intercom.
8. Walk to sector 2's ops console and shed loads (for example the Garden lights and the lab), or bring ring B out of setback.
9. Order a pair to fetch ring B's CO₂ fan (and, if wanted, pump 1). Each crossing takes 15 min, plus 10 min of work at ring B's bay.
10. Back at the bay, isolate the CO₂ unit. Work on a running machine is refused.
11. Remove the failed fan (5 min) and put it on the shelf.
12. Take the delivered fan and install it (5 min), then return the unit to service.
13. When CO₂, temperature and humidity are under control where people are, declare the watch at the intercom.

The model then runs 24 h at ×1800 and the 7-day projection, and the debrief follows (four pages).

### 41.3 Strategies and consequences (Python reference, all 11 cases)

| Case | Family | Verdict | Peak where people are | Cost (shown, not weighted) |
| --- | --- | --- | --- | --- |
| nothing | NO_REPAIR | CO2_LIMIT at 9.2 h | CO₂ 1.06 % | — |
| borrow_fan | BORROW_FAN | HEAT_LIMIT at 6.5 h | 27.3 °C | 1 part from ring B; one pump carries the full load |
| **borrow_fan_shed** | BORROW_FAN | **STABLE** | 0.18 %, 23.1 °C, RH 0.43 | 1 part from ring B; Garden and lab dark (1,343 kWh shed over 7 d); ring B cannot host |
| **borrow_fan_pump** | BORROW_FAN_PUMP | **STABLE** | 0.17 %, 24.4 °C, RH 0.42 | 2 parts from ring B (8 crossings); ring B loses CO₂ removal and half its cooling |
| **relocate** | RELOCATE | **STABLE** | 0.21 %, 24.7 °C, RH 0.45 | 0 parts; 1.5 h warming ring B first; ring A stands empty with its faults |
| relocate_cold | RELOCATE | COLD_LIMIT at 0.3 h | RH 0.63 | moving before ring B is warm |
| cannibalize | CANNIBALIZE | HEAT_LIMIT at 0.5 h | 272 °C (beyond validity) | ring A's CHX fan moved to the CO₂ unit: no cooling at all |
| shed_only | NO_REPAIR | CO2_LIMIT at 9.4 h | 1.05 % | — |
| late_fetch | BORROW_FAN | STABLE, degraded | 0.36 % (above the 0.3 % target) | the fetch ordered 5 h late |
| refused | BORROW_FAN | STABLE | 0.18 % | 6 refusals logged, none changes state |
| replay | — | identical to borrow_fan_shed | | |

**Why the three viable families are non-dominated.**

| Family | Better than the other two in | Worse in |
| --- | --- | --- |
| Shed and borrow | Lowest peak temperature; only one part from ring B | Sheds 1,343 kWh of Garden and lab work |
| Fan and pump | Ring A whole, nothing shed | Two parts taken (ring B can no longer host anyone), twice the crossings |
| Relocate | Moves no part | Takes longest, and leaves ring A empty and unrepaired |

None of them preserves everything. "Cannibalize" fails, and it teaches why the CHX fan is the cabin's only cooling and drying.

**Peak "beyond validity".** A peak more than 8 K beyond the habitability limit is flagged `beyond_validity`. The model has no passive
hull loss and no equipment thermal cutouts, so the 272 °C figure only means "far past survivable". The debrief says so.

Tests: `tests/test_ship_ops.py` BorrowedAirTests (9). They cover:
- the scenario setting no engineering value;
- refusals changing nothing, and incompatible parts being refused;
- a fetch taking the crossings and stripping ring B;
- parts being conserved, and every ledger closing;
- the outcomes, and the viable strategies differing in cost;
- an identical replay.

## 42. DS-3 "Dark Bus" (Phase 3) [BUILT; VALIDATED; PLAYABLE (headless and browser)]

`#interior-dark-bus` (`-- --dark-bus`); scenario `data/deadship/ds3_dark_bus.toml` (PROTOTYPE scenario values). It uses the same
SYS-003 model and the same scenario machine as DS-2C.

### 42.1 Premise

- A planned 48 h coast segment with the fusion plant shut down for service. Both buses run from the main battery through BC-A and
  BC-B.
- At the start BC-B fails, so bus B goes dark. That is an **electrical failure**.
- Bus B's survival loads fall to each ring's survival packs. These are the CHX fans, the second pumps, the TCC and the avionics.
- No converter spare is in the rings.
- The plant's restart at 48 h fires from the pulse bank, which the battery must first charge with 200 kWh. If the battery holds less
  than that when the window opens, the plant cannot restart. That is the **resource trade-off**: battery energy spent now against
  the black start.
- Ring B is empty in setback, as in DS-2C.

### 42.2 The coupling the player has to read

- With bus B dark and its packs draining, the CHX fans stop once the packs run out (8 kWh at 0.95 kW: about 8.4 h). Ring A's cabin then heats up, which
  is the **thermal consequence**.
- Closing the tie puts both buses on BC-A's 40 kW. With every load on, it trips at once and both buses go dark.
- Shedding enough load makes the tie hold. What is shed decides the rest:
  - Keeping the Garden lit means the tie's load grows as the heat pump works harder, and it trips late (3.6 h).
  - The CO₂ unit then stops. CO₂ and humidity climb, which is the **atmospheric consequence**.
  - The economy setpoint saves energy but lets the humidity rise to RH 0.59, above the control band.

### 42.3 Strategies and consequences (Python reference, all 9 cases)

| Case | Family | Verdict | Battery at restart (needs 200 kWh) | Cost |
| --- | --- | --- | --- | --- |
| nothing | PACKS_ONLY | HEAT_LIMIT at 9.6 h (beyond validity) | 1,048 | packs exhausted, no cooling |
| tie_only | KEEP_GARDEN | trip at once; CO2_LIMIT at 13 h | 1,999 | both buses dark |
| **shed_garden** | SHED_GARDEN | **STABLE** | 275 | Garden, galley, lab dark (1,596 kWh shed) |
| **shed_dark_b** | SHED_DARK_B | **STABLE** | 226 (smallest margin) | Garden and galley dark; empty ring B fully dark (its cooling and pumps off: it cannot be brought up quickly) |
| **shed_economy** | SHED_ECONOMY | **STABLE, degraded** | 288 (largest margin) | as shed_garden, plus humidity at RH 0.59 (above the 0.50 band, under the 0.75 limit) |
| short_reserve | SHED_GARDEN | **RESTART_FAILED** | 149 | the cabin holds, but the plant cannot restart |
| keep_garden | KEEP_GARDEN | late trip at 3.6 h; CO2_LIMIT at 16.5 h | 1,858 | the Garden kept lit costs both buses |
| refused | SHED_GARDEN | STABLE | 275 | 3 refusals (switching at the bay, the overview away from the console) |
| replay | — | identical to shed_garden | | |

**The three viable families are non-dominated.** shed_garden has the best air and a mid-size reserve. shed_dark_b keeps the lab
running but darkens ring B and has the thinnest reserve. shed_economy has the largest reserve but the wettest cabin.

The failure lessons:
- short_reserve: a stable cabin is not enough; the black start needs its energy.
- tie_only: a tie is not a free second source.
- keep_garden: a load that grows with heat trips later.

**Watch and restart.** The watch holds the ship as declared through the 48 h window. At the window it charges the pulse bank and logs
`restart ok`, or RESTART_FAILED if the battery is short. It then runs the 7-day projection with the plant back on (G1 and G2), BC-B
still failed and the tie as left.

Tests: `tests/test_ship_ops.py` DarkBusTests (7). They cover:
- the outcomes;
- physical trips;
- the restart drawing the pulse bank;
- the packs carrying only survival loads;
- the viable strategies not being dominated;
- every ledger closing;
- an identical replay.

## 43. Source and assumption inventory (Phases 2C and 3)

**Spec values used as published (no canon changed).**

| Value | Key | Status |
| --- | --- | --- |
| Cabin pressure, CO₂ target 0.3 % and limit 0.5 %, RH band 0.40–0.50 | habitat.atmosphere | WORKING |
| Ring A gas volume 466.4 m³ (nine compartments) | ring_air topology (SYS-002) | derived |
| Cold loop 320 K; heat pump 0.5 of Carnot; separation rule | thermal.loops.cold, .architecture, .separation_rule | WORKING, WORKING, BASELINE |
| Main battery 2 MWh usable | power.storage.main_battery.usable_energy_Wh | WORKING |
| Pulse bank 200 kWh, charged from the battery | power.storage.pulse_bank.energy_Wh, charge_sources | WORKING |
| Survival reserve loads and their isolation | power.storage.survival_reserve.loads | BASELINE |
| CO₂ 1.0 kg per person per day; CO₂ unit removal rate | SYS-001 (owner value), cabin_air | as SYS-001 |

**External references (applied as published, not canon).**
- NASA BVAD 2022 (NASA/TP-2015-218570/REV2): sensible heat 6.308 MJ/CM-d, vapour 2.27 kg/CM-d, cabin 291–300 K, RH 25–75 %.
- Saturation pressure by Alduchov–Eskridge (1996).
- The ISS CDRA, CCAA and TCCS classes, as the scale for powers and flows.

**PROTOTYPE (training and architecture choices; each is flagged in `ring_services.PROTOTYPE`, `EQUIPMENT` or the scenario TOML).**
- **Cabin and coil:**
  - the cabin heat capacity, 4.4 MJ/K;
  - the CHX air flow (1 m³/s), its UA (1.5 kW/K) and the coolant flow (0.2 kg/s per pump);
  - the supply setpoints (4 °C and economy 12 °C), the control band (2 K) and the coil minimum (15 %);
  - the heat pump capacity, 16 kW.
- **Electrical:**
  - the architecture (G1/G2 per bus, BC-A/BC-B, the tie, trip on overload);
  - the generator rating, 80 kW (power.rating OPEN);
  - the converter rating, 40 kW;
  - the packs, 8 kWh per ring (survival_reserve.capacity OPEN);
  - the 15 kW per bus of lumped non-habitat ship load (the whole-ship load is OPEN).
- **Equipment:** the twelve loads' powers and bus assignments, and the three part families (the common ECLSS fan is a commonality
  choice, not a sourced fact).
- **Restart reserve.** The fusion restart is taken to need the pulse bank's full 200 kWh charge. The ignition energy itself is OPEN
  (power.storage.pulse_bank.ignition_energy).
- **Scenario values:**
  - the faults;
  - the setback state (it is the model's own equilibrium);
  - the crossing time (15 min) and fetch work (10 min);
  - remove and install (5 min each);
  - the time scales (×30 live, ×1800 watch);
  - the 48 h restart window;
  - the pair layout.

**Invented for balance: none.** No resource cost was set to make a strategy win or lose. The scenarios' outcomes come from the model
at its PROTOTYPE values. Only ring B's setback was chosen to make relocation cost time, and it is the model's own coast equilibrium,
not a tuned number.

**Not invented.** No First Ignition accident detail, no medical injury (limits are habitability limits, reported in crew-hours), no
story events.

## 44. Limitations

1. **Well-mixed rings.** SYS-003 does not resolve compartments. DS-2B's compartment air (SYS-002) and SYS-003 do not run together yet.
2. **No passive hull loss.** The cabin's only heat sink is the CHX. A cabin without cooling therefore climbs without bound, and peaks
   more than 8 K beyond the limit are flagged `beyond_validity`, not reported as temperatures to believe. The equipment has no thermal
   cutouts.
3. **The survival packs do not recharge** within a scenario, and the battery is not recharged by the plant after the restart.
4. **The walk stays in ring A** when the crew relocates. The trainee then can use only the intercom. Ring B has no walkable deck in
   the package.
5. **Abstract crew.** Pairs B and C are a place and an order, not characters. There is no fatigue, no injury and no error.
6. **One fault set per scenario**, fixed at the start. There are no random or later faults in the shipped scenarios (the machine
   supports `later_faults`).
7. **The restart is a single check** (the battery holds the pulse bank's charge or it does not). There is no ignition model.
8. **Watch real time.** The 24 h watch takes about 50 s and the 48 h DS-3 window about 1.6 min at ×1800 on a desktop. Phones are
   untested.

## 45. Roadmap

| Phase | Status |
| --- | --- |
| 0 Minimal engineering integration proof | VALIDATED; the owner approved it as the base for Phase 1 (2026-11-13) |
| 1 DS-1 "Scrubber" tutorial | PLAYABLE (finalized 2026-11-14); awaiting owner acceptance |
| 2A Atmospheric connectivity | PLAYABLE (finalized 2026-11-14); awaiting owner acceptance |
| SYS-002 v2 (CO₂ and NH₃) | VALIDATED; OWNER ACCEPTED (2026-11-14) |
| 2B "Shared Air" | PLAYABLE (finalized 2026-11-15, §36); awaiting owner playtest |
| 2C gate G1 (finite TCC bed) | RESEARCHED; gate FAILED as a gameplay generator (§39); the model stays an option |
| SYS-003 ring services | VALIDATED (Python, Godot parity) |
| 2C "Borrowed Air" | PLAYABLE (§41) |
| 3 "Dark Bus" (power, thermal, atmosphere) | PLAYABLE (§42) |
| 4 Competitive Deadship and Hullrun | DESIGNED only; not started (excluded by the brief) |
| 5 Narrative survival | DESIGNED only; not started (excluded by the brief) |

**Next steps, each needing the owner:**
1. Playtest 2B, 2C and 3, and accept or change their PROTOTYPE values.
2. Source the survival reserve's capacity and the whole-ship load, so that Dark Bus's margins become canon-backed.
3. Optionally, add passive hull loss and equipment cutouts to SYS-003 (limitation 2).
4. Optionally, couple SYS-002's compartments with SYS-003, for a scenario that needs both.
5. Phase 4 and 5 only on a separate brief.
