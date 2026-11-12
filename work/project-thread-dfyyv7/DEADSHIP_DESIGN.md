# Deadship in Wayfarer: research and design report (DS-000)

Research, architecture and gameplay design only. Nothing here is implemented, nothing changes canon, the Blender model, generated
geometry, engineering values, dependencies or the deployment. Written 2026-11-12 against `main` c77026d.

Every significant statement carries one of these labels:

| Label | Meaning |
| --- | --- |
| **[EXISTS]** | Implemented in the repository today (file path given) |
| **[LORE]** | Established IGNITION canon, with its Drive owner row |
| **[ENG]** | Engineering assumption: physics or engineering judgment, not an owner row |
| **[PROPOSAL]** | New gameplay or architecture proposal in this report |
| **[OPEN]** | Unresolved: needs the owner, a Drive owner row or a later decision |

Complexity: **S** about 1–3 working days of one agent session, **M** about a week, **L** several weeks. Rough, for ordering only.

---

## 0. Summary and recommendation

**Build Deadship as a Wayfarer systems game inside Explore Interior, starting with Concept B and growing along Concept D.**

1. The interactive experience is a Godot 4 Web export (GDScript, Jolt, `gl_compatibility`), not a TypeScript application. Explore
   Interior already gives a walkable ring A in spin gravity with working doors, a ladder, both ring circuits and the station boarding
   route, nine learning stations at real exported nodes (the ECLSS bay, ops screens, workbench), an action registry that respects
   saved browser-local keys, and touch controls. Explore Exterior already has fault injection (failed valves), conserved resource
   ledgers and a state-driven staged scenario. That is most of a Deadship runtime, minus a systems simulation and an interaction
   registry.
2. The repository has real engineering screens (life support stock/flow, cabin atmosphere rules, power storage and the nine-step
   black start, the three heat loops, radiator health cells) but **no runtime systems simulation**: the life-support and thermal
   simulators were retired (removed in cf1f953, restorable from `038ae90`). Their pattern is the right one: a pure Python module writes
   a JSON package with checkpoints, and the GDScript runtime repeats the same step and proves it reproduces the checkpoints before
   anything is shown.
3. The canon leaves the decisive numbers OPEN (whole-ship electrical load, ECLSS internals and tolerances, loop heat capacities, Heat
   Debt, degraded modes). Lore resolves this cleanly: **a Deadship scenario is a deliberately disabled ship whose organizers set the
   numbers.** Scenario-owned values are labelled PROTOTYPE, the laws (conservation of mass and energy, Stefan–Boltzmann, ideal gas)
   are never relaxed, and released owner values replace scenario values without code changes.
4. Recommended first playable (**DS-1 "Scrubber"**, section 10): ring A, one CO₂-removal fault in the sector-3 ECLSS bay, a
   diagnosis at the bay and the sector-2 ops screen, a replacement part carried from the sector-2 workbench through the circulation
   corridor doors, and a "Stable" call checked by a projected watch. The CO₂ clock comes straight from canon numbers: with six people in
   ring A, CO₂ rises from the 0.3 % target to the 0.5 % limit in about **1.4 h** of ship time (section 7.2).
5. The engineering model (`ship_systems`) must not know Deadship. Deadship is one consumer of it; the story, the Engineering pages and
   the Breakthrough Lab can be others.

Concept C (Deadship as the story's survival mechanic) is the long-term destination, but it waits for the Tale's First Ignition accident
rows and the OD-010 degraded modes. Concept A (a separate simulator building) duplicates modeling and is not recommended as a first
step.

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
  navigation, power etc. with deliberately insufficient par[ts]…"; tests "Diagnosis, prioritization, cannibalization, teamwork, systems
  thinking"; character link **Rian Osei**; note "Scoring: survivability + resource conservation + system stability + time. Wayfarer
  becomes the nightmare …" (the cell text was cut in the read; the full sentence is DS-Q8).
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
failure sequence, or whether a Deadship-style qualification is part of Wayfarer's crew acceptance. These are DS-Q1, DS-Q2 and DS-Q3.

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

**Recommendation [PROPOSAL]: Concept D as the roadmap, Concept B as the first implementation, Concept C after its inputs exist.**

The player is a trainee (the walk's existing newcomer) during Wayfarer's commissioning at the development station. The GU instructor
who already greets the trainee offers Deadship qualification runs: the ship's real compartments, real systems knowledge, faults injected
into the simulated systems state by the instructors. Rian Osei, an experienced Deadship competitor, sets or reviews harder runs once his
identity and appearance are released (K01; until then he is named in text only, no body).

Why this answer:
- It reuses the walk wholesale and adds no geometry for the MVP.
- Learning comes from the ship itself: the trainee who repeatedly loses CO₂ control learns where the ECLSS bay is, that sector doors
  isolate air, and that ring B mirrors ring A.
- It matches canon (training origin, simulator or disabled ship, insufficient parts, the four scoring terms, Rian's sport).
- The systems foundation it forces into existence (section 6) is exactly what Concept C needs later.

Entry point **[PROPOSAL]**: a third start of Explore Interior, `#interior-deadship` (`-- --deadship` natively), plus an in-walk offer
from the instructor at spawn. The default `#interior` start stays exactly as it is. Explore Exterior gains Deadship tasks only in Phase 4+.

---

## 5. Gameplay mechanics

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

### 5.6 Scoring [PROPOSAL; weights OPEN for the Sports owner]

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

| Mode | In MVP? | Notes |
| --- | --- | --- |
| Training | **Yes** | No time pressure beyond the physics, hints on, the instructor explains WHAT/WHY (reuse the learning panel) |
| Challenge | Phase 3 | One emergency, limited parts, scored |
| Competition | Phase 4 | Standardized scenario set, fixed seeds, replay codes, local best scores; no backend |
| Survival | Phase 4–5 | Cascading faults over a long watch |
| Story | Phase 5 | No scores, no Deadship branding (section 2, point 5) |

---

## 6. Technical architecture

### 6.1 Layers [PROPOSAL]

```
 data/  (canon + PROTOTYPE parameters)          data/deadship/  (scenarios: PROTOTYPE, game-owned)
   │                                               │
   ▼                                               ▼
 src/wayfarer/ship_systems.py  ───────►   src/wayfarer/deadship.py
 (ENGINEERING MODEL: components, ports,     (SCENARIO compiler: faults, inventory, objectives,
  flows, limits, from spec and life_support;  scoring weights; scenario screens)
  knows nothing of Deadship)                     │
   │  systems_sim.py (reference stepper,         │
   │  fixed dt, deterministic, checkpoints)      │
   ▼                                             ▼
 package: wf_ship_systems.json        package: wf_deadship.json          (written by runtime-export / web build)
   │                                             │
   ▼                                             ▼
 godot/scripts/systems/  WfShipSystems     godot/scripts/deadship/  WfDeadship (scenario engine, scoring, debrief)
 (SIMULATION: same step as Python,          ├─ interaction layer: WfInteractables (registry by exported node)
  proves the checkpoints at load)           ├─ visualization: cue panels, board, schematic, alarms
                                            └─ gameplay: objectives, hints, the watch, score, local records
```

### 6.2 Engineering model (`ship_systems.py`, pure Python, standard library) [PROPOSAL, M]

- Builds the component graph from `data/wayfarer_3d.toml` and `data/life_support.toml` through the existing modules
  (`cabin_atmosphere`, `life_support`, `power_storage`, `thermal_budget`, `heat_rejection`, `materials`): every parameter carries its
  `source_ref` and status; `known = false` stays unknown and must be supplied by the consumer (a scenario) with a PROTOTYPE label.
- Binds components to exported nodes (`Prod_RA3_GDN_ECLSS`, …) through the manifest's `source_name`, like `learning_stations.py`.
- Exposes a generic override interface (component state, part state, parameter override) so any consumer (Deadship, story, an
  Engineering page) can apply faults without the model knowing why.
- Writes `wf_ship_systems.json` with its own checkpoints: given a stated initial state and a stated sequence of overrides, the state
  after N steps.

### 6.3 Simulation (`systems_sim.py` and `WfShipSystems`) [PROPOSAL, M]

- Lumped stocks (gas moles per air volume and species, battery Wh, thermal energy per lumped mass, coolant flow) and flows per step.
- Fixed step (1 s ship time), time compression as a labelled display factor (as the walk's ×90 ring ramp), no randomness at run time:
  every fault time comes from the scenario (seeded at compile time).
- GDScript repeats the exact step; at load it runs the package's checkpoints and refuses to start Deadship if any differs (the retired
  `life_support.gd` did this). Cost: a few hundred components at 1–10 Hz is negligible in GDScript even in the Web build.
- Ledgers per resource; a conservation check every step in debug builds and in the headless check.

### 6.4 Scenario engine (`deadship.py` → `wf_deadship.json` → `WfDeadship`) [PROPOSAL, M]

A scenario is data (TOML under `data/deadship/`, a new subfolder of `data/`; DS-Q5): ship configuration (COAST, DOCKED), occupants and
their positions per ring, scenario-owned PROTOTYPE values for anything OPEN, fault schedule (component, part, time or trigger), inventory
(parts, consumables, tools, where they are), objectives, hint texts, watch length, scoring weights. The engine advances like
`WfEvaScenario`: on real state, never on timers, except the faults the scenario schedules.

### 6.5 Interaction layer (`WfInteractables`) [PROPOSAL, S–M]

A registry of `{node, reach, verbs, condition}` entries built from `wf_deadship.json` and the manifest. `excursion.gd`'s `use()`
consults it first when Deadship is active; the label shown on touch ("Use · isolate CO₂ unit") comes from it. Verbs call the systems
model's override interface. Physical props (a carried fan, a jumper) are Godot-authored presentation scenes under `godot/scenes/deadship/`
(display only, never spacecraft facts); equipment covers become bound mechanisms only after a detail pack adds them (Phase 3+).

### 6.6 Visualization and gameplay UI [PROPOSAL, S–M]

- Status colours on the existing SP-54 cue panels and the ECLSS board (emission changes at runtime: presentation only).
- A systems schematic (2-D Control, like the ring map) drawn from the graph, opened at an ops screen or by its action.
- Alarms as sound and text; the HUD shows at most three clocks.
- The debrief reuses the learning panel: WHAT happened, WHY (the dependency that bit), SHOW ME (the schematic replay of the run).

### 6.7 Controls, persistence, deployment [PROPOSAL]

- **Controls.** A new `deadship` context in `SCENE_ACTIONS`, active together with `excursion`; physical operations reuse `exc.use`.
  New rows: `deadship.scan` (handheld readout), `deadship.schematic`, `deadship.stable` (hold), `deadship.drop`. None marked `setup`, so
  no existing profile is asked anything new; conflict checks cover them automatically; touch gets context buttons (`wf_touch.gd`). No key
  is hard-coded; every prompt prints `WfInput.keys(...)`.
- **Persistence.** A separate `user://wayfarer_deadship.cfg` (runs, best scores, replay codes, training progress). The controls profile
  (schema 4) is not touched. Same IndexedDB behaviour and the same "this visit only" notice when storage is not persistent.
- **Replay and competition.** A replay code = scenario id + scenario hash + semantic action log (ship-time stamped). Local only; a
  shared leaderboard is not needed until the owner asks (it would be the first backend; DS-Q6).
- **Deployment.** Nothing new: the package files ride in the existing Godot pack; Pages from `main` after the owner's squash.
- **Checks.** A headless `--check-deadship` drives the scenario through semantic actions (like `--check-excursion`): checkpoint parity,
  ledger invariants, the scripted reference solution stabilizes, the "do nothing" run is lost at the expected time, the default
  Explore Interior start is unchanged. The browser check only confirms the scene loads and one action works.

### 6.8 What goes where

| Part | Place | Why |
| --- | --- | --- |
| Systems graph, reference stepper | `src/wayfarer/ship_systems.py`, `systems_sim.py` | Pure, testable, shared with the Engineering pages and story |
| Scenario data | `data/deadship/*.toml` | Data, not code; owner-reviewable |
| Scenario compiler and screens | `src/wayfarer/deadship.py` | Pure; writes the package; runs the solvability screen on demand |
| Runtime simulation | `godot/scripts/systems/` | Reusable by any scene |
| Deadship gameplay | `godot/scripts/deadship/`, `godot/scenes/deadship/` | Separate from `excursion.gd` |
| Blender | Nothing for the MVP; later a detail pack for service covers and spares racks (`docs/MODULES.md`) | Geometry stays generator-owned |
| TypeScript / WebAssembly / backend | **None** | The runtime is Godot; the simulation is tiny; single-player is local |

**Separation principle.** `ship_systems` never imports `deadship`; `WfShipSystems` never references `WfDeadship`. Deadship only applies
overrides and reads state. A unit test protects the physical invariants of `ship_systems` (conservation, canon parameter agreement), not
Deadship content (AGENTS.md: tests protect owner numbers and physical invariants).

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

### 7.2 What the canon already gives (worked example) [ENG, DERIVED from canon]

Air volume per ring: 120 m³ usable (`[habitat.layout] usable_per_ring_m3`, WORKING), 80 kPa, assumed 295 K (cabin temperature not
found in the spec: **[ENG]** assumption). Ideal gas: n = PV/RT ≈ 3,914 mol.
- CO₂ at the 0.3 % target ≈ 0.52 kg; at the 0.5 % max ≈ 0.86 kg; the window is 0.34 kg.
- At the 41 STUDY rate of 1.0 kg CO₂ per person-day: **six people in ring A take about 1.4 h** from target to max, three people about
  2.8 h, twelve about 0.7 h.
- O₂ at 20 kPa in the same volume ≈ 31 kg; at 0.84 kg per person-day, six people consume about 5 kg a day, so O₂ is a slow clock and
  CO₂ the fast one. That is the real lesson of spacecraft air (CO₂ removal, not oxygen, is what fails first in a closed cabin), and it
  falls out of canon numbers without tuning.

Using the usable rather than gross volume is conservative (shorter clock); the scenario can state which it uses.

### 7.3 Limits and what stays honest [ENG]

- **Electrical loads are OPEN** (`power.rating`). Scenario-owned PROTOTYPE loads, labelled, with bus capacities and the battery's 2 MWh
  (WORKING) where used. No endurance claim is shown as ship canon.
- **Heat capacities and Heat Debt are OPEN.** Lumped thermal masses are scenario values; Stefan–Boltzmann and the cold-loop numbers from
  `heat_rejection.py` are used as published; temperatures shown are labelled simulation values.
- **ECLSS internals are OPEN.** The CO₂ unit's parts (fan, bed, valve, controller) are a PROTOTYPE taxonomy; the technology
  (regenerable sorbent) is an engineering assumption to put to the owner (DS-Q4).
- **Medical limits are OPEN** (12!G22). The run ends at the WORKING control band with a labelled safety margin, not at a claimed
  physiological limit.
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

| Phase | Content | Depends on | Acceptance | Size |
| --- | --- | --- | --- | --- |
| **0 Foundations** | Prune retired contexts from `wf_input.gd` (TODO J05); extract an interaction registry hook from `excursion.gd`; `ship_systems.py` skeleton with the ring A air volume only | Owner approval of this report | Explore Interior unchanged (all existing checks pass); registry used by one existing interaction | S |
| **1 Minimal prototype (DS-1)** | Section 10 | Phase 0 | Section 10 criteria | M |
| **2 Connected systems** | Bus A/B power, the CO₂ unit, fans, the ring cold loop, cabin heat, RH; load shedding at the ops screen; door isolation of air volumes | DS-1; PROTOTYPE loads (DS-Q4) | Two faults whose fixes interact (e.g. bus fault stops the coolant pump; restoring power overheats until flow returns); conservation checks pass | M |
| **3 Resource decisions** | Insufficient parts; cannibalize ring B's mirrored unit through the trunk and drum (a Hullrun carry); jury-rig with reliability; the watch scoring; Challenge mode; first detail pack (service covers, spares rack) | Phase 2; detail pack via `docs/MODULES.md` | At least two valid stabilizations with different scores; scenario screen proves no full repair is possible | M–L |
| **4 Full Deadship** | Both rings, station briefing at the boarding node, black-start procedure scenario, Competition mode with standard scenarios, replay codes, local records; Survival mode; Hullrun timed carry mode; optional exterior task (radiator cell isolation) | Phase 3; walk lines to SP-45 storeroom (geometry already exists) | Standard scenario set replays identically native and Web; scores stable across runs | L |
| **5 Narrative** | First Ignition / voyage events driven by the same systems model; no scores, no branding | Tale rows for the accident (DS-Q2), OD-010 degraded modes, heat capacities | Story beats played on the same model; no canon invented | L+ |

---

## 10. First playable prototype: DS-1 "Scrubber"

**Goal.** One compartment set, one malfunction, one diagnosis and repair sequence, one success condition, on the existing walk.

**Setting [PROPOSAL].** Explore Interior, `#interior-deadship`. Wayfarer docked at the station, ring A spinning for the training run
(scenario choice; the docked rule keeps rings stopped and locked (14!A8), so the run states it is a COAST configuration in simulation
only, or the run uses the DOCKED-locked ship with the deck in the rig's training gravity: **[OPEN]** DS-Q7; the walk already starts on
ring A's deck in spin gravity, so COAST-in-simulation is the low-cost reading). Six simulated occupants in ring A.

**Fault.** The sector-3 CO₂ removal unit (at `Prod_RA3_GDN_ECLSS`) stops removing CO₂: its fan has failed (cause), visible as zero fan
current and a cold bed (symptoms).

**Sequence.**
1. Briefing by the instructor: "Ring A's board shows CO₂ rising. Find out why and stabilize the ring."
2. The sector-3 board shows ppCO₂ rising; the HUD shows one clock (time to the 0.5 % limit, about 1.4 h ship time at the scenario's
   labelled compression, e.g. ×8 gives about 10 minutes of play).
3. Inspect the unit (Use): fan current 0 A, bed temperature low, controller healthy. The schematic at the sector-2 ops screen shows
   the unit powered.
4. Isolate the unit (Use: power off at the unit). Working on it live is refused with the reason ("isolate before opening").
5. Fetch the spare fan from the sector-2 workbench: walk through the CIRC corridor and its doors, carry one item.
6. Install, restore power: CO₂ starts to fall.
7. Call "Stable" (hold): a 12 h watch runs in seconds; the debrief shows the CO₂ curve, what the fan does, and that a sector door left
   open or closed changed nothing here but would have in a leak (a teaser for Phase 2).

**Success.** CO₂ back below the 0.3 % target within the watch and no out-of-band exposure beyond the scenario allowance.
**Failure.** CO₂ reaches the limit: the run stops with a debrief (no harm to the walk).

**Optional second solution (if cheap).** Take the Garden circulation fan (same family) instead of walking to the workbench: faster, but
the watch shows RH climbing in sector 3 over hours (stability term lower). This demonstrates the Deadship idea from the first scenario.

**What it builds.** The air-volume part of `ship_systems.py` and its stepper with checkpoints; `WfShipSystems`; `WfDeadship` with one
scenario; `WfInteractables` with four verbs; four new actions in the `deadship` context; the debrief panel reusing the learning panel;
`--check-deadship`. No geometry, no Blender change, no canon change, no new dependency.

**Acceptance criteria.**
- Godot reproduces the Python checkpoints exactly (tolerance stated), or Deadship refuses to start.
- The CO₂ ledger closes every step (produced = removed + accumulated).
- With no action the run is lost at the predicted ship time (±1 step); the reference solution stabilizes.
- The default `#interior` start, `--check-excursion`, `--check-locomotion` and `controls` checks are unchanged and pass.
- All prompts print the player's bindings; touch shows a context button for each verb; no new setup question for existing profiles.
- The Web build loads and plays it; headless check native and Web.

**Size.** M (about a week of focused sessions), most of it in the reusable systems layer.

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

## 12. Unresolved decisions (owner questions, drafted locally)

| ID | Question | Recommended default while open |
| --- | --- | --- |
| DS-Q1 | Is a Deadship-style qualification part of Wayfarer's crew acceptance at the development station? | Treat it as a GU training exercise (PROTOTYPE framing) |
| DS-Q2 | What fails in the First Ignition accident, in what order (Tale)? | Phase 5 waits; no invention |
| DS-Q3 | Deadship rules: team size, solo training allowed, penalties, standard scenarios, scoring weights | Solo training; weights 40/30/20/10 as a proposal |
| DS-Q4 | ECLSS CO₂ removal technology and its serviceable parts; PROTOTYPE electrical loads per device for training | Regenerable sorbent unit with fan/bed/valve/controller; scenario loads |
| DS-Q5 | May scenario data live in `data/deadship/` (a new subfolder of `data/`)? | Yes, as game-owned PROTOTYPE data |
| DS-Q6 | Is a shared leaderboard ever wanted (first backend)? | No; local records and replay codes |
| DS-Q7 | DS-1 ship state: COAST in simulation while docked, or DOCKED-locked? | COAST in simulation, labelled |
| DS-Q8 | The full Sports note "Wayfarer becomes the nightmare …" (cell cut in the read) | Read it before Phase 5 framing |

---

## 13. Final recommendation

Integrate Deadship as **a systems game played on the real Wayfarer**: start as a station-run training simulation inside Explore
Interior (Concept B), grow it through connected systems, scarcity and competition (Concept D), and only then let the same systems carry
the First Ignition story (Concept C) once the Tale gives the accident. Build one reusable, conserving, deterministic **ship systems
model** fed by the canon data, with a Python reference and a GDScript runtime that must agree, and keep Deadship as a thin scenario,
interaction and scoring layer on top of it. Judge every run by the canon's four terms through a projected **watch**, so a lean, stable
ship beats a fully repaired, stripped one. The first step is DS-1 "Scrubber": one CO₂ fault in ring A, diagnosed at the bay, fixed with a
part carried through the ring's own doors, clocked by numbers that come straight from the ship's canon. It needs no new geometry, no
dependency and no canon change, and everything it builds is the foundation the story will use.
