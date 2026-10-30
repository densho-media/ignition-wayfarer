# Wayfarer current model

What the model contains now. Update this file in the same change as the model.
Leave out history (Git and the reviews in `references/` hold it) and open work
(TODO.md). The parameters are in `data/wayfarer_3d.toml`;
`python3 tools/workflow.py status` shows the source snapshot and
`python3 tools/workflow.py report` the measured scene.

The ordered implementation steps and acceptance criteria for Wayfarer Review Release 1
live in [TODO.md](../TODO.md). This document describes implemented behavior; a planned
feature or a completed prototype study is not an installed or qualified system.

Study scripts named below as `studies/<name>.py` are retired; commit 038ae90 in `main`'s history holds them under
`src/wayfarer/studies/`, and their kept results are in `references/evidence/`. New studies live in `work/<task>/` (AGENTS.md).

## Blender development previews

Whole-ship standalone previews and the quick pipeline use Workbench for form and fit.
Optional `--quality material` uses Eevee on the graphics GPU for fast material previews
with direct lights; it does not establish indirect lighting or emissive illumination.
Cycles review/look modes retain the lighting review, and the full pipeline still defaults
to Cycles review. Previews pose saved assets in memory without changing geometry.
The perspective whole-ship camera sets its near clip to half the distance to the nearest
ship bound, so rasterized depth resolves the 1–2.25 cm radiator display-overlay lifts;
Eevee shadows use 4 rays and 16 steps. Workbench still tints blades with the
translucent glow overlay (material alpha), and Cycles remains the appearance reference.

## Runtime representation

Two experiences consume the generated package; neither computes spacecraft geometry.

- **Explore Ship** (`web/explore/`, three.js): the static COAST GLB (Draco) with the export manifest. Orbit, pan and zoom, the side,
  top and three-quarter views, picking by semantic `Assembly_*` lineage, and the standard, subsystem-hologram and engine-hologram
  styles (`representation.py holo-style`, `shots/m5_subsystems.toml`). A picked part shows its source name, geometry status, source
  status and source reference; a PROTOTYPE geometry label is never promoted by a sourced reference.
- **The walk** (`godot/scenes/excursion.tscn`, "Station-to-ring excursion" below): the Godot project's main scene and the web
  launcher's Start, on the DOCKED package and the rig.

**In Blender** the vehicle file `WF_WAYFARER_001.blend` opens as `GEN_WF_WAYFARER_001` with `10_SHIP` (the linked assemblies by
system: `11_STRUCTURE` STRUCTURE, HULL; `12_DRIVE` PROPULSION, SHIELDING, POWER_STORAGE, STORAGE; `13_THERMAL`; `14_HABITAT` HABITAT,
ROTOR_INTERFACE, CREW_TRANSFER; `15_FORWARD` FORWARD_SHIELD, EYE; `16_SERVICE` SERVICE, DRONES), `20_HUMAN_SCALE` (one group per scale
figure), `30_CAMERAS` (the first-person review views) and `40_SIM_RIG` (anchors and the hidden simulation proxies), beside the empty
`ART_WF_WAYFARER_001`. Each system group carries its outliner colour (AGENTS.md "Inside every .blend"). The groups change no object, transform or link.

**Zones.** Every exported node record carries `zone` (`representation.zone`): `INTERIOR:<area>` for crew-side fixtures, fit-out,
passages and interior production detail (areas RING_A and RING_B by the ring frame a node turns with, TRUNK, SERVICE, else SPINE),
`SHELL` for the sector pressure envelopes and the storeroom shell, `EXTERIOR` for the rest; the manifest's `zones` counts them. One
model is tagged, never split into copies; inside the subsystem files exterior and interior stay mixed (no per-subsystem
interior files, user 2026-10-29). `profile_views.gd --hide-zone` compares a view with a zone hidden.

`python3 tools/workflow.py runtime-export` builds in a disposable workspace, exports the COAST and DOCKED snapshots (manifest, rig,
route, mechanisms, frames, characters) and runs the Godot checks before publishing; it never changes the production Blender assets.
Evaluated curves and linked geometry keep their dimensions and poses; debug fields, mannequins and simulation cages are excluded,
and materials are static presentation approximations. A node record's `frame` names the ring or despun drum it turns with; the
export finds it by turning each ring and drum in Blender, so the sector shells and their linked interiors turn too. The rig keeps
source status and unknown values. `godot/scripts/profile_views.gd` measures the walk's station view and an outside ship view on the
current machine (frame time, draw calls, primitives, memory); `--hide-assemblies` and `--hide-zone` hide detail for a comparison.

## Overview

The model is the P1 engineering prototype: proxy geometry (`REP_PROXY`) in one
vehicle file, `WF_WAYFARER_001.blend`, with the operating configurations as presets
of it (schema 5). The owner's answers come from the Science &
Engineering sheet `15_MODEL_INTERFACES`, the answer contract: one row per request
item with the canonical answer, its status, the PROTOTYPE allowance and a "do not
assume" rule. Final engineering, room-level interiors, materials and hero detail
are not modeled; the ring sectors carry only rough PROTOTYPE interior blocking.

- **Habitat:** two rigid coaxial counter-rotating rings, outer radius 30 m and
  occupied floor radius 28 m. Each ring is a PROTOTYPE annular frame (hoops, fills
  and six spokes) with three recessed pressurized sectors; water, storage and
  structure fill the rest of the frame, so only the sectors are pressure volume.
  The frame reads as construction inside its unchanged envelope (PROTOTYPE,
  `habitat_ring.construction`): 15° assembly segments with rim joints and web
  frames, flank frames either side of each sector, fill cassettes with inspection
  covers, a service node with ochre access covers at each structural spoke, and a
  muted amber band on the rim over each pressure segment.
  The rings stay at full size in every preset: they spin in COAST, LOW_THRUST and
  EVA, and are spun down, indexed and locked for high thrust and docking. Nothing
  retracts, no room turns and there are no rotor-bay doors. Each rotor hub carries
  labelled PROTOTYPE mechanism proxies: magnetic bearings, touchdown cartridges,
  hub motor, contactless power/data and fluid coupling, plus retracted ring-stop
  lock pins at the three crew-spoke angles. A PROTOTYPE crew route runs from a
  trunk in the spine bore through a despun transfer drum beside each hub (Q46: a gate
  in the spine shell, the drum on its own bearings on the spine with two seal planes
  per side and three sliding doors, and a sliding hatch in each crew-tube collar), then
  out along a crew spoke, to every sector; the same route serves both ring states. From the primary boarding port through its trunk
  node and the 1.6 m crew trunk into ring A's rotary vestibule, out along its three
  crew spokes and down through each sector's overhead hatch to the deck the route is
  hollow and human-scale (HUM-001 zones 1–5). Ring B's route is hollow the same way,
  through a 0.90 m spine port and 0.90 m tube necks (zones 3–4 at ring B); the rooms
  are rough blocks.
- **Ship:** a 225 m body (PROTOTYPE inside the 220–240 m WORKING envelope, nozzle exit
  at the aft end), central body 13 m; the rings (~60 m) and the 90 m forward shield
  are wider. The 220–240 m envelope includes the Dust Lance: with the WORKING 12 m
  Lance the ship is 237.0 m overall (225 m body + 12 m, Q2).
- **Forward defense:** `WF_FORWARD_SHIELD` holds the fixed 90 m conical shield (flat hub to r 7.4 m at X 112.5 m, then a cone sweeping aft by the ~3 m crown depth to X 109.5 m at r 45 m) on a conical truss, one full-diameter sacrificial disruptor layer 2.0 m ahead of it, the four EYE facets recessed in protected wells in the flat hub, the Dust Lance, an elongated display-only diversion-field zone, damage/repair display cells and the concealed Aegis Dustbreak Crown (12 sector bays in the rim, shuttered in every preset). One normalized control, `FORWARD_DEFENSE_CTRL`, drives the field zone, damage, repair and Crown engagement. Rear construction (M4 slice 3, `forward_shield.rear_construction`, PROTOTYPE judgment): a gusset plate at every truss node in its spoke's plane, a dark rib on each Crown bay partition and one ochre service hatch per bay on the housing aft plate (the ring service-cover ochre), and (S04 slice 2, `brow_panel_joints`) the Brow's replaceable-panel joints as dark grooves on the skin's aft face: radial joints 10° either side of every spoke, splitting each truss bay into thirds, and hoop joints midway between the truss rings at r 11.2, 20, 30 and 38 m, broken round each spoke's forward chord. All of it stays inside the truss envelope (`rear_construction_screen`); joint, rib and hatch sizing and the carriage service path are OPEN.
- **Structure and thermal:** a 12-node thrust ring and three longitudinal trussed
  thermal blades (the BASELINE production direction), each the owner's equivalent
  rectangle 182.149 × 30.5 m between r 6.5 and 37 m with root booms and four bay stays.
  The blades are not thermally rigid (AFT-009). Each has a cooler root transition row,
  nine 0.125 m non-emitting bay joints in the sheet with guided sliding shoes and bellows
  on its feed and return trunks, and a single axial datum at the aft root boom carried
  by redundant lugs; the forward root and the stays slide on 0.20 m of local travel, and
  feed and return each run in a protected chase with an expansion loop beside the root post.
  Root construction (M4 slice 2, `radiators.root_construction`, PROTOTYPE judgment): every
  boom, stay and chase leaves the r 6.0 m casing through a sealed off-white boot (a flange
  covering its opening, a sleeve with a sliding gap), each root post sits in a dark steel
  saddle on its boom, and two dark stops at the ends of every slide rail bound the 0.20 m
  travel; booms, posts and the datum and slide mount blocks are structure greys (owner
  2026-10-17, 15!A202 m2: red datum / yellow slide is a non-diegetic review legend, key L in
  the Godot inspector, never paint). Nothing lies on the sheet or the root band
  (`thermal_geometry.root_construction_screen`); boot sealing and member sizing are OPEN. A display-only control, `RADIATOR_HEALTH_CTRL`, shows a thermal-state
  glow on the hot faces and isolated or resurfaced thermal-cell markers; it never moves the
  blades or changes an area.
- **Hull and service:** a station-lofted PROTOTYPE service casing (r 6.0 m under the
  blades, the 13 m body elsewhere), a stationary EVA airlock, two docking ports with
  structural capture rings and a storm refuge rated for 12, all in the service zone
  ahead of ring B. The primary boarding port leads through a double-hatch entry
  chamber and a trunk node into the crew trunk, on through a 1.6 m spine port into
  ring A's despun transfer drum, out along its crew spokes and down a ladder into each
  sector's landing well; a 0.90 m spine port and 0.90 m tube necks lead the same way
  into ring B's sectors, and a 0.90 m port off the trunk opens the storm refuge, with an
  anchor rail for each of its 12 occupants. For thrust, when aft is down, a ladder with a
  fall-arrest rail climbs the trunk from its aft end past ring B's port and the refuge
  port. Nine generic mannequins and eighteen first-person cameras are non-canon scale
  guides (HUM-001).
- **Exterior hardware (S02, `[exterior_hardware]`, `exterior_hardware.py`, all PROTOTYPE; owner rows name functions only):**
  each docking port has a passive approach target on a short post 2 m forward of the port, three amber
  alignment lights and four proximity sensors (lidar/radar). All of them stand below the visiting-vehicle
  corridor base less the mechanical clearance, and outside the capture ring plus clearance (screened), so the
  corridor and capture-ring interfaces are unchanged. The EVA airlock has two floodlights beside its hatch.
  White position strobes mark the extremities: four sit flush in the shield rim girder at the bisectors
  between Crown bays, inside the 90 m diameter, and three sit on the aft RCS pods.
  Primary navigation sensors (slice 3, `nav_sensors`): three star-tracker heads on pedestals on the hull at X 20 m, one at each
  radiator bisector (90°, 210°, 330°), clear of the survival masts and trackers at X 40–48 m. Each has a sun baffle, a radial
  boresight and a coarse sun sensor on its pedestal's forward face. The boresights are 120° apart, so with a 40° sun exclusion the
  sun can blind at most one head and two always see stars (`nav_screen`: the whole sky checked); each head's 30° stray-light cone meets
  no blade, ring, shield, hull or plume. FOV, exclusion and size are typical flight values, not requirements.
  Aft of the skin (which ends at X −101.75 m) the only structure is the thrust ring (X −103 m), so every
  aft part stands on its nodes. Each node carries a 0.06 m diaphragm plate filling the ring section
  (S04 slice 4, `Thrust_Node_Plate_*`, PROTOTYPE judgment); the ring is built from twelve bay segments joined by a
  0.40 m bolted splice sleeve on each chord at mid-bay (S04 slice 6, `Thrust_Ring_Splice_*`). Primary comms sit on booms slanted aft from the ring to gimbals at
  X −105 m, aft of the blades, where the aft hemisphere (Earth during outbound coast) is free of blades,
  rings and shield: two gimballed 4 m Ka-band dishes at 90° and 210° and a 0.5 m optical terminal at 330°,
  beside the independent survival terminals. In COAST they point aft; their sweeps clear the blades, hull,
  beacons and RCS pods, and the inspection bounds them inside the shield shadow. During a burn the main
  plume (15°/20° study cones) blocks the aft axis. RCS: three aft pods on the ring nodes at the keel
  azimuths (their jets canted 20° aft, which also settles ullage) and four pods on the shield rim's aft face
  between Crown bays, docking corridors and rim beacons. Every nozzle fires outward or tangentially, canted
  so that its 15° jet cone meets no hull, blade, ring, shield or antenna sweep (screened). The sizing behind these is a stated bounding case in `exterior_hardware.sizing()`:
  a free-space link budget, a mass-budget inertia bound, flip time at 100 N per nozzle and momentum storage
  at twice the ring residual. Momentum storage is internal and not built. The M5 readback (`studies/m5_attitude.py`) spreads the
  burnout mass budget over the built meshes for a full inertia tensor (near-diagonal, transverse ≈ 7.5e9 kg m², stationary roll
  1.8e8 kg m²) and solves duty-cycled pure couples from the 21 jets (all canted aft, so every couple carries forward thrust); the
  geometric shield-shadow tolerance from the built parts is 2.22° toward a blade (screen values; physics.inertia stays OPEN).
- **Casing construction (S04 slice 1, `[casing_panels]`, `casing_panels.py`, PROTOTYPE judgment):** the aft
  body casing (X −101 to 80 m) carries raised joint straps at every primary-cage frame station, where its panels
  bear on the frames, broken across the blade-root band at each keel. Longitudinal straps run on the 15° + 30°
  lines, which miss the keels, masts and trackers. An access panel (1.6 × 1.1 m) sits in every third frame bay
  beside each keel lane (0°, 120°, 240°), opening onto the cage-to-skin corridor. Fixed exterior parts clear
  every strap and panel by at least 0.05 m (screened). Strap and panel faces are wound outward (the runtime draws them double-sided).
  The forward collar (S04 slice 3, `casing_panels.collar_straps`) carries hoop straps every 3 m and
  longitudinal straps on the same lines. They break round every hull opening on it (the airlock, both docking
  ports, the bypass and sector ties, the shield-mount struts) and round each fitting's docking or airlock aids,
  0.25 m clear. Like the fittings, the straps are bounded by the 14 m maximum body diameter.
- **Power:** layered electrical storage (main battery and pulse bank aft beside the
  reactor, survival packs forward beside the refuge) and the owner's nine-step black
  start.
- **Drive:** the optically gated Fiji/lattice magnetic manifold, rigged. It runs
  from the core through a solid common plasma and a convergence throat to four
  flux channels and nozzles. The spine ends on a hub at the reactor shadow
  shield, and the three outer structural sectors carry the drive's thrust ring
  forward around it. The aft A/B lasers reach lattice gates L1–L4 by two
  independent routes, each with its own dog-leg bore through the shield and
  hot-side distributor heads. One normalized state control, 12 unassigned actions,
  and magnetics, separatrix and optics debug layers that the control's toggles
  switch on. The core, throat and nozzle coils carry replaceable plasma-facing
  liners; the seed and nozzle coils are conventional superconducting (HTS) coils;
  the nozzle pickups bear on warm yokes around the nozzle coils; deuterium and
  helium-3 lines feed the core and two hydrogen lines feed an injection ring ahead
  of the manifold, each through a stepped sleeve in the shadow shield.
- **Rig:** a simulation rig with a JSON contract that keeps flight thrust and
  structural load separate.
- **Configurations:** the owner's configuration table as presets of the one
  vehicle. COAST, LOW_THRUST and EVA have rings ROTATING; HIGH_POWER,
  FIRST_IGNITION and DOCKED have rings STOPPED_LOCKED; DAMAGED is declared but
  fault-specific.
- **Shots:** standard, hologram and cutaway representations built in shot files
  from the linked assets ([review](../references/FUT002_SHOTS_REVIEW.md)), and the
  induction shot `SH_INDUCTION`, camera cuts through the eight induction stops. The animated First Ignition
  flight `SH_FIRST_IGNITION_FLIGHT` (FUT-006) overrides the linked vehicle and keys its controls from the
  flight timeline over 1369 frames (below).
  The M5 study shots and the M5/M6 hologram scene are retired (commit 038ae90); their numbers are in
  `references/evidence/m5_*.json`, and `shots/m5_subsystems.toml` still classifies the web viewer's subsystem hologram.

## Sources and implementation

| Quantity | Current source | Implemented proxy |
| --- | --- | --- |
| Body | 220–240 m overall length including the Dust Lance (nominal ~225 m body + ~12 m Lance = ~237 m), WORKING; 12–14 m central body, BASELINE (not the maximum width); legacy station radii SUPERSEDED | 225 m body (`ship.length.value`, scope BODY_AFT_TO_SHIELD_FACE) / 13 m selections, PROTOTYPE; overall 237.0 m = body + `forward_defense.dust_lance.length`, checked against the envelope; 6.0 m casing under the blades (blade root r 6.5 m less the 0.5 m member clearance; 12 m BASELINE minimum body) |
| Crew | Story manifest six, LOCKED; rated design occupancy 12, WORKING (separate fields; 20 m³ usable per rated person, 40 m³ per story person, DERIVED) | 1.8 m orange human scale annotation; 12 bunks and 12 aft couches as blocking |
| Habitat | Two rigid counter-rotating rings, fixed diameter, ±4 rpm, BASELINE; outer radius 30 m, occupied floor radius 28 m, working mass depth 2 m, WORKING; ring-equivalent COM 27 m, 0.501 g at the floor, DERIVED; 330 t rotating mass (165 t per ring; ~20 t of the 180 t water moved to the stationary refuge, Q32), PROVISIONAL; I 120.285e6 kg·m², H 50.38 MN·m·s, 23.45 kW combined peak spin power, 2.427 MN axial load per ring at 1.5 g (~405 kN per spoke), residual-momentum target 50.38 kN·m·s (0.1 %), DERIVED; six spokes per ring at 60° (three crew, three structural/service) of 1.2–1.5 m depth, ring-plane spacing 6 m, ring/radiator-spar clearance ≥ 1.5 m, WORKING; rim axial deflection ≤ 0.05 m is an FEA target | Two `Rotor_n` rings with PROTOTYPE frame r 24.5–30 m × 4 m (its construction relief inset, never proud of it: 24 segments of 15°, 0.08 m rim joints, 0.30 m webs, 0.35 m sector flank frames, cassettes inset 0.04 m with 0.025 m covers, service nodes ±4° to r 27.2 m, a 0.60 × 0.02 m rim band), six spokes (twin rails, 1.30 m deep, PROTOTYPE inside the WORKING 1.2–1.5 m) and three sectors each; ring A's aft sweep is 1.5 m ahead of the leading spar front (nominal, cold); ring rotation at 24 fps; ring section, spoke section, frame and flexible modes OPEN (08!A53, OD-016) |
| Pressurized sectors | 400–460 m³ gross across the occupied sectors of both rings, BASELINE; the torus is not a pressure vessel, BASELINE; fixed interior orientation (radial floor in coast, aft burn couches), WORKING | Six `WF_RING_SECTOR` instances, r 25.0–28.7 m × 3.5 m, 11.93° arc solved from 72.383 m³ gross each (434.298 m³ total), each a 0.05 m pressure skin inside that envelope (67.18 m³ inside it) opened under its crew tube by the 1.6 m overhead hatch (HUM-001 zone 5); deck at r 28 m, floor radially outward; furniture OPEN |
| Habitat volume | 230–260 m³ usable, BASELINE; 240 m³ working usable, 120 m³ per ring, the three functions mirrored in both rings, 80 m³ Garden distributed in both rings, WORKING | One sector of each function per ring (PROTOTYPE); one rough interior component per function with 40 m³ usable inside 57.9 m³ deck-to-overhead; rooms OPEN |
| Cabin atmosphere | 80 kPa, 25 % O2 / 75 % N2 dry-gas, BASELINE; 20 kPa O2, dry-gas approximation, DERIVED; CO2 0.3 % target / 0.5 % upper working limit and RH 40–50 %, WORKING; no pure-O2 nominal cabin, BASELINE; lower-pressure high-O2 suit with pre-breathe/airlock protocol, WORKING; anti-biofilm wetted surfaces and sensor-rich fluid cartridges, WORKING; tolerances, emergency O2, suit pressure/composition, decompression protocol, coating chemistry and cartridge life OPEN | Data and checks only; no geometry |
| Operating states | COAST, HIGH_POWER BASELINE; LOW_THRUST (≤ 0.1 g rotating), EVA (rings may keep rotating), DOCKED (rings stopped and locked, radiators fixed) WORKING; DAMAGED OPEN | Six buildable presets of the one vehicle |
| Service | EVA airlock and 2 docking ports on the stationary structure; one stationary refuge rated for 12 near the stationary transfer hub, reachable with the rings rotating or stopped, ≥ 20 g/cm², ~4 m³ per person and ~50–60 m³ in total, inside ~20 t of the 180 t water (Q31, Q32), WORKING; both ports share one androgynous soft-capture standard with a ~1.6 m clear passage, a larger structural capture ring (diameter OPEN) and a ~3 m keep-out corridor with radial approach through the ring-B/shield gap in DOCKED (Q33), WORKING; the docking path must clear the permanent ring and radiator envelope (D1) | PROTOTYPE service zone ahead of ring B: radial airlock (X 101.85 m) and ports (X 99.40 m, datumed to FWD because their forward bound is the shield truss; angles 195° (`Dock_Primary`, the primary boarding port) and 315° (`Dock_Service`)); annular refuge X 94.15–96.95 m around the spine core, cavity r 1.10–2.89 m (53.85 m³, 4.49 m³ per person) inside a 0.20 m water-equivalent shell (~19.5 t, inside the ~20 t allocation); both ports have a 0.80 m clear radius (1.6 m passage) in a 0.85 m fitting and an identical PROTOTYPE capture ring (r 1.40 m, 0.05 m deep, tip r 6.85 m, inside the 7 m body maximum by ~8 mm); a 3.0 m radial docking corridor (X 96.4–102.4 m) from each port out to the 45 m shield radius is checked against the ring sweeps (3.20 m to ring B), the blade front (15.00 m), the other corridor, the airlock, and the shield truss, rim, Crown housing, sector keels, hoops and ties (1.66 m to the keels); every pair of fittings clears by 0.15 m or more, the capture rings by 0.24 m or more. The corridor radius is compared with the 3 m figure (it also holds as a width). The capture-ring diameter and mechanism stay OPEN (`service.docking.capture_ring`). `Dock_Primary` is a hollow route (HUM-001 zones 1–2, `[human_entry]`, PROTOTYPE; 15!A86, 14!A32): see Hull and service fittings. |
| Structure | 12-node aft ring and 8 m transition to three sectors plus spine; the spine ends at the forward reactor/shadow-shield bulkhead and the three outer sectors bypass the core, common region and manifold to the aft thrust ring, WORKING (06!A47, 15!A72) | 12 m ring OD, 2 m axial depth, 1 m radial depth, 2.5 m hub from WORKING inputs; 1.75 m prototype spine diameter aft, widening over a 0.30 m cone (X 81.05–81.35) to a 1.90 m core that carries the 1.6 m crew trunk in its bore (HUM-001 zones 2–3), both inside the 1.5–2 m envelope, X −79.8 to 108.5, on a PROTOTYPE r 2.0 m terminated hub (15!G70, G72); bulkhead sizing and load shares OPEN (07!H16) |
| Propulsion | One core, common region, manifold, four magnetic channels and nozzles, no plasma pipes, 25% nominal share, LOCKED; convergence throat, 2 A/B optical sources along −X, one distributor and 4 lattice gates, WORKING; two independent chicaned A/B routes with no shared combiner, cold-side lasers and robotic hot-side cartridges, WORKING (06!A55, 15!A73, A83); optical power, wavelength, gate response, optical-lattice coupling and the throat field profile OPEN | Four linked nozzle instances; smooth r 0.65 m flux-domain paths; solid common and throat plasma; WORKING throat (1.5 m long, ~2.4 m waist radius), PROTOTYPE lattice sectors, seed coils, lasers and gate optics, and per route a dog-leg bore through the hub and shield, a splitter in the shield-to-core gap, two corridor legs outside the primary cage and two distributor-head cartridges in lattice gaps (four heads in the one logical distributor; screened for zero open sight lines from the core to cold optics) (`[drive_manifold]`); `DRIVE_MANIFOLD_CTRL` normalized 0–1 controls saved drive-off; N1 +Y+Z, N2 −Y+Z, N3 +Y−Z, N4 −Y−Z (the EYE facet order, WORKING: 06!A48, 15!A71), carried by `Nozzle_0k`, its channel, gate Lk and `IF_*` names; the 20/30/20/30 `WF_MANIFOLD_IMBALANCE` is a yaw couple; `WF_FLUX_CHANNEL_FAIL` isolates the failed channel and derates its diametric opposite, so the surviving diagonal pair flies at about 50% thrust (WORKING: 06!A51, 15!A76); nozzle vector limits ±5° WORKING and ±8° DIAGNOSTIC are rig limits and preview cones only, with no keyed vector pose and the electromagnetic/mechanical authority OPEN |
| Drive hardware | Conventional nanoengineered HTS (REBCO-descended, flux pinning) seed/manifold/nozzle coils beneath the Fiji amplification, independently energized; replaceable graded W/UHTC plasma-facing shell on the core, throat and nozzle-adjacent hot structures; separately solved cryogenic storage and feed, not hidden in the reactor mass; all WORKING (05!A37:A39, 06!A44:A46, 98!A56:A57, 14!A22). Core stack 0.12–0.15 m and throat stack 0.08–0.10 m (Q17); pickups on the nozzle's warm structural yoke, never on the windings or the axis (Q18); dog-leg sleeves with thermal intercepts and no straight core-to-tank sight line (Q19); separate D, ³He, hydrogen and water inventories, D and ³He metered into the core and hydrogen injected downstream before the manifold (Q20, 06!A53:A54); all WORKING (15!A66:A69). Coil current density, temperature, stress, quench and radiation life (OD-024), PFC material, heat flux, erosion, module size and replacement interval (OD-025), and tank layout, temperatures, fuel split, boil-off and refrigeration (OD-026) OPEN | `PFC_LINER_CORE` (r 3.8 m, 0.15 m, 5 × 12 modules) and `PFC_LINER_THROAT` (0.10 m, 2 × 12) in their own refractory material; 0.02 m `PFC_NOZZLE_STRIKE_02/03` local strike modules on the two throat-side nozzle coil inner faces (Q40; magnetic standoff elsewhere, liner performance unknown); seed and nozzle coils keep PROTOTYPE geometry, with the HTS designation only in their `conductor_*` properties; no liner on a spine side, since the plasma is solid; a warm `Nozzle_Yoke_*` (0.08 m shell, 0.30 m wide, 0.05 m off the coil, four straps) around each nozzle's inlet coil carries `Nozzle_Pickup_*` to the thrust ring; the tanks are assigned to deuterium, helium-3 and two hydrogen families; `CRYO_FEED_LINE_01–02` (D, ³He; r 0.08 m) run from the tank aft caps to the core forward face, and `CRYO_FEED_LINE_03–04` (hydrogen) along an r 5.4 m corridor to `H2_INJECTION_RING` (r 3.8 m) around the common region at X −91.5, before the manifold; every line steps through a staggered dog-leg sleeve in the shadow shield, so no straight core-to-tank sight line exists (screened), with OPEN `IF_CRYO_FEED_*` and `IF_H2_INJECTION` interfaces; all sizes PROTOTYPE (`[drive_hot_section]`) |
| EYE | Four facets, LOCKED; F1 +Y+Z, F2 −Y+Z, F3 +Y−Z, F4 −Y−Z, BASELINE; 2.5 m aperture and 8 m baseline, WORKING; recessed into protected wells in the fixed shield (14!A4, Eye 40!A20), WORKING; window/shutter/baffle solution OPEN (OD-020); FOV OPEN | `EYE_Facet_01–04` follow the facet map, faces 2.0 m below the shield face in Ø 3.5 m wells (PROTOTYPE); `EYE_Shared_Mount` is a ring with a 1.15 m bore around the shield spine column; no fifth sensor; the wells sit in the flat hub, so the facets stay 2.0 m below the local face; each well has a coaxial open port in the disruptor layer of RADIUS 2.25 m (Ø 4.50 m; Eye 45 FD-A04, S&E 50 AG-A04, WORKING interpretation, `forward_defense.eye_wells.outer_port`), which is also the smallest that adds no vignetting inside the well's own unvignetted field; `validate` keeps the modelled port from shrinking below it. Q43 keeps these four separate open ports (15!A107, Eye 40!A35, ACCEPTED / vulnerability OPEN); a replaceable window cartridge `EYE_Window_0j` sits 0.4 m ahead of each facet inside its well, and two armoured eyelid leaves `EYE_Shutter_0j_A/B` part tangentially at the well mouth under the layer (FD-E03, AG-007; PROTOTYPE, mechanism and erosion life OPEN, OD-020); closed, they lap 0.05 m at an overlapping seam with leaf B one leaf thickness forward (FD-B10, PROTOTYPE; latch, jam and erosion are prototypes only); no second exposed transparent pane is added. Wells are placed at `forward_defense.eye_wells.centre_radius_m` (14!A28); B_array 8 m is the WORKING r4 calibration input only; geometric baselines follow the placement radius (opposite 2r, adjacent √2 r, rig `forward_defense.shield.eye_baselines`) and the coherent baseline `eye.coherent_baseline` is OPEN (FD-A03, AG-A03); the r16/r24 placement study is below; the saved model carries r30 with hexagonal EYE shells (Eye layout switch and EYE shell, user 2026-10-29). |
| Forward shield | ~90 m fixed shield with recessed EYE wells, WORKING (14!A4); WORKING targets: a shallow forward-convex/conical profile with ~3 m crown depth over 45 m radius backed by a ~3–4 m truss (Q3), carried into all three longitudinal sectors as well as the hub (Q1), behind full-area disruptor layer(s) (FWD1); wells Ø 3.5 × 2.0 m at r ~4 m (Q3); 15 m ring and 8 m radiator shadow margins; thickness, material stack and mass OPEN (15!A35, OD-014); attitude limit OPEN (OD-015) | `[forward_shield.prototype]`: 0.10 m display skin on a conical face (flat to r 7.4 m, linear cone to the sourced ~3 m crown depth at r 45 m; the depth is read from `forward_defense.shield_profile`), a 3.5 m two-chord truss of constant axial depth (inside the owner's 3–4 m; hub ring r 7.0–7.4 m at X 108.9–112.4 m, rim girder r 44.5–45.0 m with its aft face at X 105.9 m), 12 spokes and three truss rings. Load path (PROTOTYPE, 14!H15, 15!I30; Q1): hub path `Shield_Spine_Column` (r 1.0 m, X 108.5–112.5 m) from the Momentum Spine's forward end to the hub plate plus four radial `Shield_Mount_Strut_01–04` at X 111.0 m to the hub ring; sector path three `Shield_Sector_Keel_n` (r 5.0 m at 30°/150°/270°, the sourced sector radius and azimuths of 07!A10, A13; rail r 0.15 m; X 93.65–108.4 m, from ahead of ring B to behind the hub truss; hoops at both ends) and nine `Shield_Sector_Tie_n_*` (r 0.20 m; one to the hub ring and one to each adjacent truss spoke at the first truss ring) through derived hull openings. Disruptor (FWD1): `Disruptor_Layer_01`, a conical layer 2.0 m ahead of the face (0.05 m display thickness, X 114.5 m at the hub, 111.5 m at the rim) carried on 60 posts at truss nodes, with four EYE ports, the Lance hole and twelve Crown ports (1.42 % of the disc open, DIAGNOSTIC); layer count, thickness and spacing OPEN. Every object carries its HSFP design class (`forward_shield.design_classes`, 98!A58). Q45 bypass collar (`forward_defense.bypass_collar`, WORKING principle 15!A99, 07!A57; geometry PROTOTYPE, FEA and mass OPEN): per sector a two-chord girder `Bypass_Chord_n_Outer/Inner` (r 35 m on the Brow's outer truss ring and r 33 m, 2.8 m outside the ring sweep, 9.8 m inside the shield edge) with verticals and diagonals from the Brow truss aft face (X 106.5 m) aft to a frame centred in the blade-front / ring-A slot (X 82.02 m, 0.675 m to each); hoops at that frame, between the ring sweeps (X 88.05 m) and at the keel aft ends (X 93.65 m); `Bypass_Aft_Spoke_n` from the inner chord down to the sector rails, which continue 0.67 m forward of the cage end (`Bypass_Rail_Extension_n`), and `Bypass_Keel_Tie_n` from each keel aft end out to the collar, both through derived hull openings. The Brow now reaches the primary sectors round the rotor bay as well as through the hub path; the spine shares loads (Q1, Q45). |
| Dust Lance and field | Central ~12 m structural/field mast with a replaceable sacrificial tip, r 1.0 → 0.25 m with a ~1.5 m tip cartridge, WORKING (Q2; not the only first-contact surface); material and detailed taper OPEN (OD-017); pre-energized elongated axial/cusp-like diversion field for charged/ionized debris only, neutral dust not diverted (LOCKED, Eye 40!A22): on in COAST, LOW_THRUST, HIGH_POWER and FIRST_IGNITION, off in DOCKED and EVA unless threat procedures require it (Q4, WORKING, `forward_defense.field_states`; the 10,000 m³ stays DIAGNOSTIC); strength, coils and power OPEN (OD-018); regenerative shield, repair rate OPEN (OD-019) | Lance 12.0 m (r 1.0 → 0.25 m) with a 1.5 m replaceable tip cartridge (the sourced values, read from `forward_defense.dust_lance`), rooted on the shield spine column; the field is shown as `Field_Zone`, one translucent closed surface of revolution from the shield face to the Lance tip, pinched onto the Lance (0.30 m clearance) at both ends, 12.0 m long and about 9.8 m across at its widest (aspect 1.23, displayed volume ~470 m³, a display metric that is not the 10,000 m³ DIAGNOSTIC study volume); it is hidden when `field_on` is 0 or `field_strength` is 0. The presets take `field_on` and `field_strength` from `forward_defense.field_states` (Q4); OQ-F3 is closed. 4 × 24 damage cells as display states; no field strength or repair rate is modelled |
| Aegis Dustbreak Crown | Concealed annular close-in defense behind the shield rim: twelve protected bays at 30°, housing ~41–44.5 m, normal engaged hardware inside r ~45 m moving mainly forward, up to four cooperating sectors (Q5, Q6), sector carriages, armoured shutters, mixed effectors, WORKING (14!A19:H21); local sector/sub-array coherence, full-ring ~90 m phasing DIAGNOSTIC (Q7); ~25 t Crown suballocation inside the 100 t forward-protection envelope, never additive, and the 20 MJ pulse banks distributed at the Crown sectors and counted inside it (Q8, Q9); canisters seed a pre-positioned Dustbreak Veil (WORKING; parameters OPEN); engagement boundary LOCKED doctrine, OPEN performance (Eye 40!A28); N_crown 4, 250 kJ at 5 Hz, 20 MJ store WORKING; radius, count, travel, shutters, effector mix, mass and power OPEN (OD-021) | housing r 41.0–44.5 m (the rim girder is its outer wall), X 106.44–109.44 m inside the conical truss; 12 bays at 30°, each with a shutter under its skin window, a carriage (2.0 × 1.2 × 1.0 m), one Ø 0.6 m emitter and one launcher tube, all PROTOTYPE. Engagement translates the four bays around `crown_azimuth` forward 2.949 m (derived: muzzles end 0.15 m ahead of the layer) through their skin windows (r 42.0–43.5 m × 3.0 m) and small disruptor ports; the shutters slide 3.1 m tangentially. Q44 (15!A108, Eye 40!A36): each layer port is only the carriage footprint plus clearance (r 42.0–43.5 m × 1.3 m, 23.4 m² for all twelve instead of 54 m²) behind a normally closed armoured `Crown_Port_Cover_nn` (1.6 × 1.4 × 0.05 m, 0.15 m aft of the layer) that slides 1.4 m tangentially with its skin shutter; the carriages move only forward in fixed bays, so the ports stay aligned, and the covers clear the posts, the stowed muzzles and the field zone (audited in `forward_shield.validate`). Exact apertures, cover cycle and firing round the rim stay OPEN (OD-021). No radial travel: the largest Crown hardware radius is 43.353 m, inside the 45 m limit and the 41–44.5 m housing band are met as hard checks. |
| Defense power and heat | Crown normal/heavy 5/10 MW optical, 10/20 MW electrical, 5/10 MW heat (WORKING), extreme 20/40/20 MW (DIAGNOSTIC) (Eye 20!A9:G16); 20 MJ pulse store; planning bands 15–30 / 30–50 / 50–80 MW with the heat routed to the warm ~450 K stationary loop, never directly to the hot blades (Q10; warm-loop area OPEN); field services 0.5–2 MW OPEN; root-calibration margin 71.8 MW (DIAGNOSTIC); closure OPEN (OD-022) | `[forward_defense.power]` values with their row statuses and pure-formula checks in `forward_shield.py`; no geometry, no radiator change |
| Radiators | Three double-sided petals at 120°, BASELINE; the owner accepts the built blade (Q52 option D, 07!A58:A63, 40!A7, A21:A22): 4,978 m² NET one-face hot area per blade at the 0.125 m working seam (4,972–4,984 m² across 0.10–0.15 m; the ~3 m root band and nine seams excluded), 14,935 m² net and 26,882 m² effective, DERIVED; 5,000 m² per blade is a nominal target the deliberately undersized radiator does not reach; 0.9 WORKING view factor; blade mass per sector OPEN; fixed in every mode (no fold, hinge or cant, R1/R8/E1); outside the nozzle plume and strong-field exclusion zones, BASELINE (boundary OPEN) | The blade is 182.149 × 30.5 m, 5,555.56 m² gross planform per blade (`radiators.physical_area`, WORKING, 07!D58), aft edge fixed; `[radiators.as_built_net_area]` (DERIVED, `radiator_net_area.as_built`) holds its net area at the three seam widths, and `radiators.effective_area` derives from the working one; static blades, identical in every configuration; the only control, `RADIATOR_HEALTH_CTRL`, is display only and never moves geometry or changes an area |
| Blade proportions | Longitudinal thermal blades are the BASELINE production direction; outer radius 37 m and root radius 6.5 m WORKING; equivalent rectangle 30.5 × 182.149 m (aspect 5.972), DERIVED; taper, cant and exact length may stay PROTOTYPE (R4 G5); cant is static only (OPEN) | The equivalent rectangle is built: 182.149 × 30.5 m per sector from the area, root and outer radius; 160 cells and ten bays of 18.215 m; 3 m WORKING truss depth; zero cant, one ribbon (PROTOTYPE); the 90 m shield (45 m radius) leaves 8 m beyond the blades and 15 m beyond the 30 m ring outer radius |
| Thermal expansion | Segmented cells, compliant/sliding mounts, expansion loops and a deliberate hot/cold root transition; "do not model the fixed blade as thermally rigid" (R6, MEC-013), BASELINE; no deployment joints (MEC-012); expansion allowance OPEN (OD-007) | AFT-009 (Q12, Q13, Q15, Q16, under Q52 option D; no length or station change): nine 0.125 m non-emitting bay joints at the bay frames (the cells stop at their edges; a bead in each gap; feed and return bellows on the trunks), truss chords continuous; the cells are 5,521.2 m² per blade and their net of the 3 m root band is the as-built 4,978.2 m² (`thermal_geometry.compliance`); root band = the innermost cell row (20 of each blade's 160 cells), still radiating sheet; the one axial datum at the aft root boom, carried by its datum block (dark grey; red only in the inspector's review legend) and two lugs on the root post (Q15); slide blocks (grey; yellow in the legend) on rails of block plus the WORKING 0.20 m local travel at the forward root and stays 2/4/6/8, and two guided shoes across every joint (Q12); feed A and return B on opposite sides of the sheet, each in a protected chase with a U loop beside the aft root post, leaving the hull aft of the mount block (Q16); all PROTOTYPE; actual growth, CTE and the temperature map `known = false`. RAD-DATUM-2026-10-10 (15!A116) keeps the datum and every station PROVISIONALLY and asks for a growth rig: `studies/radiator_expansion.py` ([RADIATOR_EXPANSION_RIG.md](../references/RADIATOR_EXPANSION_RIG.md), DIAGNOSTIC, free strain only) finds that with one guided datum per cassette the 0.20 m shoes have travel to spare but every 0.125 m seam closes at the owner's ~1.5 m equivalent growth (0.149 m per joint; SiC, W, Mo and Nb close too, C/C does not), and that growth accumulating from the aft-root datum overruns the collar for every material but C/C; reported to the owner, no geometry moved. RAD-002-2026-10-10 (15!A122) keeps this geometry WORKING and authorizes a material-led comparison: `studies/radiator_rad002.py` ([RAD002_RADIATOR_OPTIONS.md](../references/RAD002_RADIATOR_OPTIONS.md), alpha(T), 0.025 m PROTOTYPE margin) finds nine 0.175 m seams pass the owner equivalent, SiC and W (0.20 m Mo, 0.25 m Nb, C/C keeps 0.125 m), more cassettes at 0.125 m don't reach the margin up to 13, and the spar front, built at exactly ring A's 1.5 m sweep clearance, loses it to any forward growth unless the front cassette is held at its front edge (joint 9 about 0.25 m) and the truss stays cool; candidate seams are not built |
| Radiator surface | Nano-engineered stack (emissive skin → transition layer → sensor mesh → spreader → structural cell → coolant/heat-pipe network → crawler access), sensed isolatable cells, crawler repair doctrine, variable emissivity only on cooler roots, WORKING; ε 0.95–0.98 an unqualified target with 0.90 kept (OD-023); angular-emission gain OPEN | Metadata in `[radiators.*]` and on `Radiator_0n`; only the root band may carry the variable-emissivity tag; the build and the margin use ε 0.90; no layer thickness or material property is modelled |
| Radiator health display | Operating sequence fixed structure → coolant flow → heat admitted → high-power rejection → post-shutdown cooldown, "geometry remains unchanged; only thermal state and isolated-cell availability change", BASELINE (07!A39); isolatable thermal cells, BASELINE, count unsourced (40!A26); sensor mesh feeds a thermal-health map and repair doctrine detect → isolate/cool → resurface → reheat → recalibrate, WORKING (40!A55, A58); a resurfaced cell is unqualified and derated until requalified, then may return to full rating (Q42, 15!A102, interim derate OPEN); the hot coolant loop has its own state per configuration, independent of thrust, and DOCKED keeps cooling until safe (Q41, 40!A69, 11!E2:E6; flow and loop temperatures OPEN); prototype fault states may be modelled if clearly labelled (15!G29), degraded-mode matrix OPEN (OD-010 / 09!A11, 11!E7) | `RADIATOR_HEALTH_CTRL` (IMPLEMENTATION, normalized 0–1, saved neutral): `thermal_state` steps through the five sequence phases; `cell_isolation`, `cell_resurface` and `cell_requalify` show nested fractions of 480 PROTOTYPE cells (3 × 20 × 8) isolated, resurfaced or requalified in a PROTOTYPE scattered order (stride 77). Per blade, 4 `Radiator_Thermal_Glow_n_k` objects (one per glow step, hot face only, never the root band) and per cell a dark isolated and a pale resurfaced `Radiator_Health_Cell_n_jj_kk[_R]` marker (a requalified cell is back in service and shows neither) hang on the `Radiator_0n` instances, zero planform, saved hidden, with fixed materials shown by 1,944 simple hide drivers (no shader reads driven object colour). PROTOTYPE presets: HIGH_POWER and FIRST_IGNITION high-power rejection, COAST, LOW_THRUST and EVA heat admitted, DOCKED coolant flow; the cooldown step is shown by the control and the timeline. The rig's `radiator_health.fluid_status` gives each configuration's coolant state (`[radiators.coolant_modes]`: circulating, DOCKED circulating until safe) and `sources.cell_qualification` the four cell states. The `RADIATOR_DAMAGED` preview pose (COAST + 10% isolated, 5% resurfaced, 2% requalified) is not a configuration. The available-cell fraction counts healthy and requalified cells only (0.92 in that pose); it is DIAGNOSTIC and never changes an area, emissivity or the margin |
| Radiator placement | Old radial chords/reach/root radius SUPERSEDED; roots 12 m apart remain WORKING; root station, exact axial position OPEN/PROTOTYPE | Aft edge 1.0 m ahead of the thrust-ring forward face (X −101.0 m); front X +81.149 m (derived, `RADIATOR_FRONT`); roots at the blade mid-length (X −15.93/−3.93 m); stays at bays 2/4/6/8 (X −64.57, −28.14, +8.29, +44.72 m) |
| Aft answers (data only) | Owner answers Q12–Q16, Q22, Q25–Q27, Q36 (S&E `06`, `07`, `15`, `40`; Fiji `25`): N1–N4 map, throat 1.5 m / ~2.4 m, nozzle placement accepted (WORKING, built), channel-loss recovery and vector limits (built as rig behaviour); radiator joints 0.10–0.15 m, travel 0.20 m per station, 3 m root transition; hot, warm and cold rejection regimes with separate loops; field profile, authority, life and dose OPEN. The drive structure answers (Q17–Q21, Q23, Q24, Q34) are built: see Structure, Propulsion and Drive hardware | `[propulsion.*]`, `[radiators.*]` and `[thermal.loops.*]` record these facts and are checked by `validate_aft_answers`; the radiator joints are built (AFT-009, see Thermal expansion); the warm and cold loops have no equipment or credited capacity, only the 18 candidate warm panels (Q38, built PROTOTYPE) that `thermal_loops.py` (AFT-010) screened (below). the as-built net area replaces the Q52 audit: the owner declined lengthening, widening or moving the rings to reach 5,000 m² |
| Power | Two Brayton trains, A/B buses, two habitat motors, BASELINE | Labeled proxy volumes/interfaces; ratings remain unknown |
| Storage | Layered storage and fault-isolated survival reserve, BASELINE; 2 MWh main battery (~800 Wh/kg extrapolation) and 200 kWh / 50 MW pulse bank, WORKING; nine-step black start; survival capacity, endurance and hotel source OPEN | `WF_POWER_STORAGE`: PROTOTYPE main-battery and pulse-bank boxes aft at X −60.4…−57.6 m (beside the reactor, Brayton trains and A/B bus; the bank feeds ignition) and two survival-pack boxes in the service zone at X 99.40–104.65 m, beside the refuge and airlock; ride-through markers, `WF_BLACK_START` action; mass stays in the 50 t power/computers item |
| Thrust | Flight 16.18 MN (4.045 MN/nozzle) and structural design load 29.42 MN, DERIVED | Separate rig channels; the structural load is never flight thrust |
| Rotor interface | Active magnetic primary support, serviceable touchdown cartridges, direct hub motor, contactless power/data with an emergency path, essential-only redundant fluid coupling, independent ring-stop locks that carry the high-thrust load and bypass actuators (MEC-011), seven health channels, WORKING; every size, gap, rating, loss, lock geometry, control law and spin-down OPEN | `WF_ROTOR_INTERFACE` (stationary segments, fluid cartridges, retracted ring-stop lock pins with OPEN drive interfaces) plus rotating drum and rings in the ring assets `WF_HABITAT_A`/`_B` (linked by `WF_HABITAT`); PROTOTYPE radii/stack on the 1.90 m spine core (stationary r 0.975 m to drum r 1.475 m, 0.075 m further out than before HUM-001, with unchanged gaps); `ROTOR_n_MECH_CTRL` saved at the vehicle's preset; `WF_RING_STOP_LOCK` / `WF_ROTOR_TOUCHDOWN` actions |
| Crew transfer | Per ring an independently closable stationary-side hatch, a double-boundary despun transfer drum that synchronizes with the ring, and an independently closable rotating-side hatch at each crew tube; routine transfer while the ring spins, controlled ring stop/index/lock as the backup (I5, Q46, MEC-019; BASELINE architecture, drum, seals, sync cycle and hatches OPEN); refuge reachable with the rings rotating or stopped, WORKING; essential routes passable aft-down to 1.5 g, BASELINE (Q47, MEC-020; step and arrest hardware OPEN); route, hatches, seals and pressurization OPEN (OD-002); entrance-first, human-scale route validation, BASELINE workflow (15!A86, 98!A60; HUM-001) | `WF_CREW_TRANSFER` (trunk in the spine bore, spine ports, connectors to airlock/docks/refuge) plus the despun transfer drums (`Drum_j`, the former vestibules, no longer strutted to the rotor) and one crew tube per sector in the ring assets `WF_HABITAT_A`/`_B`: it starts across a running gap from its drum opening with a radial collar, turns in two mitered elbows inside the 13 m body and runs out beside its crew spoke (1.15 m off the rail plane, bracketed to both rails every 4 m) to the sector's overhead hatch at the sector centre, on the ring plane; PROTOTYPE `[crew_transfer]`; one overhead hatch per sector, no end hatches. Each vestibule ends at u −1.30 m, bounded by the lock pins, with a 0.20 m guard band at each end, so each side has a primary and a secondary seal plane (`IF_VESTIBULE_j_SEAL_*`); `WF_VESTIBULE_SEAL_FAULT` isolates the rotor-1 vestibule and stops and locks both rotors on the stop-lock curve. The trunk (X 81.60–102.45 m) is a hollow pressure shell, 0.80 m clear (the 1.6 m docking passage carried on, PROTOTYPE) in the bore of the spine core, opened by equal tees to the primary port's hollow connector (HUM-001 zone 2) and to ring A's single 1.6 m spine port (zone 3). Ring A's vestibule (u −3.60…−1.30 m, X 81.45–83.75 m) is a hollow shell open toward the spine (see Hull and service fittings); ring A's crew tubes are hollow 1.6 m passages (zone 4) that pass through the opened inner hoop onto each sector's overhead hatch (zone 5). Ring B's vestibule (u −2.90…−1.30 m, X 88.15–89.75 m) is hollow too, entered through one 0.90 m spine port, the largest that hub 1's forward withdrawal paths leave room for (zone 3 at ring B). Ring B's crew tubes are hollow 1.6 m passages too, each rising from a 0.90 m neck through a bulkhead 0.175 m above the vestibule wall (zone 4 at ring B). The refuge port is hollow too, 0.90 m clear (the refuge leg); the other connectors are solid proxies, so the route is human-passable from the primary port to the deck of every sector of both rings and into the refuge. Q46 is built (PROTOTYPE, see Hull and service fittings, "Despun transfer"): spine-port gates, drums, drum doors and tube hatches, driven by `CREW_PORT_GATE_CTRL` and `TRANSFER_j_CTRL` (saved despun and closed). Q47 aft-down footing is built (trunk ladder, crew-tube floor ladders, sector thrust steps, drum crawl rails; every size PROTOTYPE, see the thrust review below) |
| Hull | Secondary service casing, BASELINE (14!A2); rings permanently at full size, no stow doors or fairings, hub fairings OPEN, BASELINE | PROTOTYPE lofted shell; the ring bay (X 82.75–93.35 m, the ring sweep) stays open; no door panels, no hub fairings |

The 330 t rotating-system mass (165 t per ring) is a PROVISIONAL reallocation of
existing allowances, not extra vehicle mass; the 180 t water is ~160 t rotating plus
~20 t stationary refuge shell, not additive. Mass items carry the owner's qualitative
regions (`13_MASS_POSITIONS`). A PROTOTYPE centre-of-mass and inertia proposal for
owner feedback is in [p1_mass_proposal.json](../references/evidence/p1_mass_proposal.json).
The spec and rig keep the centre of mass, inertia, reaction-mass load, fusion-fuel
load and drive output unknown. The reactor shadow shield and the magnet/cage support (the nozzle yokes) are unsized,
non-additive suballocations inside the 250 t engine package (P5/P6, 15!A111, 10!A24:A25): their objects carry
`mass_known = false` and an unknown, not zero, centre-of-mass contribution (`[physics.mass_suballocations]`, rig
`mass_properties.suballocations`). **Fuel storage** (FUEL-SPLIT, WORKING, owner-delegated 2026-10-29; S&E 15!A229;
`fuel_storage.py`, `components/storage.py`, `[fuel_storage]`, all geometry PROTOTYPE): ³He (164.8 t) in 27 sector lobes, three per
station of nine BODY-C3 modules (11 m long, r 1.1–4.72 m, 100° each between the keel lanes at 30/150/270°), each station with a
cryocooler (r 3.9–4.6 m) and its lobes hung from the frames; H2 (145.1 + 180 t) and D2 (110.1 t) in a torus behind the Brow (R 20.5 m,
minor 4.5 m, X 96.1–105.1 m) split by three 6 m gaps (50/195/315°, the EVA azimuth and the keel lanes) into vessels with 2:1 heads, D2
in a 32° end cell of vessel 3, the vessels on struts to the forward collar. Four transfer lines leave the torus, ride the bypass collar
at r 32.5 m clear of both ring sweeps, drop at its aft station and enter the hull at X 80.02 m (`IF_FUEL_HULL_*`, OPEN), then run
along the keel lanes at r 3.6 m over the pulse bank and battery to the four feed run tanks (`Feed_Run_Tank_01–04`, the drive's
short-term run tanks: 4 × r 1.4 × 12 m at X −73…−61 m, `[physics.fuel_tanks]`, no fuel mass; `IF_FUEL_RUN_TANK_*`). Volume margins at
3 % ullage: ³He +1,690 m³, D2 +65 m³, H2 +416 m³. Boil-off, cryocooler power, support loads and insulation are OPEN; no fuel mass
enters the rig. **Body framing and momentum storage** (`body_equipment.py`, `[body_equipment]`, PROTOTYPE): an internal ring frame
(`Body_Frame_01–08`) in every module gap between the keel rails and the skin; on the two 3 m utility frames (X −21, 17 m) three radial
beams at the lobe bisectors carry six double-gimbal control-moment gyros (`Body_CMG_*`, 1.1 m housings at r 2.9 m), sized so five of
six hold twice the rings' allowed residual momentum (100,770 N·m·s; 20,154 N·m·s each, 6000 rpm, 32 kg·m² rotor). Mass, power, loads
and slew rates are OPEN. No quantitative plume or magnetic exclusion boundary
is sourced. Art Style owns depiction; engineering owns dimensions and operating
constraints.

The old 7 m × 10–12 m habitat cylinder is SUPERSEDED and kept only in provenance
and history.

## One vehicle and presets

`WF_WAYFARER_001.blend` is the only vehicle (`[vehicle]` in the spec). It links every
non-debug subsystem once and is saved at the preset named by
`vehicle.saved_preset` (COAST). Ring planes are X = 85.049 m and X = 91.049 m, ahead
of the radiator front at X = 81.149 m. `RING_A` is DERIVED (`layout.ring_a_offset_m`,
3.90 m): the 0.25 m spar radius plus the owner's 1.5 m clearance (Q29) plus the 2.15 m
half sweep (half the 4 m frame plus 0.15 m), so it follows the blade front if the
blade changes. That leaves 1.5 m from ring A's sweep to the radiator spar, 1.70 m
between the rings and 14.20 m to the forward mount. The analytic blade envelope and the saved-geometry checks cover this
separation. The initial phases align the two rotors, so bow/aft stills can show
three overlapping sector pairs.

A configuration is a **preset**: its `habitat` state, `radiators = "FIXED"`, and
`controls` (`ring_spin`, `ring_lock`), IMPLEMENTATION values of the rotor controls.
A preset never changes the file; tools pose it in memory on the linked controls
(`pose_configuration`) and the shots pose it locally (`preset = ...`).

| Preset | Drive | Rings | `ring_spin` / `ring_lock` |
| --- | --- | --- | --- |
| COAST | off | ROTATING | 1 / 0 |
| LOW_THRUST (≤ 0.1 g) | active | ROTATING | 1 / 0 |
| EVA | off | ROTATING | 1 / 0 |
| HIGH_POWER (> 0.1 g to 1.5 g) | active | STOPPED_LOCKED | 0 / 1 |
| FIRST_IGNITION | active | STOPPED_LOCKED | 0 / 1 |
| DOCKED | off | STOPPED_LOCKED | 0 / 1 |

- **Rotation:** each `Rotor_n` driver is `phase + rate * (integ * turned + (1 - integ) * spin * (frame - 1))`,
  reading the control's `spin_fraction`, `spin_turned` and `spin_integrated`. Presets are saved and
  posed with `spin_integrated = 0`: frames 1–361 at 24 fps play one 15-second revolution at ±4 rpm,
  every preset starts at the index angle (the phase), and with `spin = 0` the ring stays there. The
  rotor actions and the flight timeline key `spin_integrated = 1` and `spin_turned`, the integral of
  spin (`rotor_interface.spin_turned`, FUT-007), so a spin ramp slows the ring to rest without
  reversing. A ring at rest sits at its index angle: between two rests the integral is scaled to whole
  turns (a display rate, since the spin-down law is OPEN), and a run that starts spinning is counted back
  from its first stop. This is a PROTOTYPE display, not a control law.
- **Sectors:** the six `Sector_j_k` instances sit on the 28 m deck radius at 0°,
  120° and 240° in every preset and never turn relative to their ring; their
  interiors keep the floor radially outward and carry PROTOTYPE aft-bulkhead couch
  blocks; furniture is OPEN (`habitat.interior_orientation`).
- **Ring-stop locks:** retracted stationary pins on the spine at the three
  crew-spoke angles (`Ring_Stop_Lock_j_k`, `IF_RING_STOP_LOCK_j_k_DRIVE`), OPEN
  MEC-011; each lock set carries 2.427 MN per ring at 1.5 g before safety factors
  (DERIVED, `physics.rotor_dynamics`). The pin tip radius must stay inside the
  vestibule-strut sweep (derived limit 1.19 m).
- **Doors:** none. The rotor bay stays open (`hull.rotor_bay.treatment =
  FULL_SIZE_RINGS_NO_DOORS`); hub fairings are OPEN and not modelled.
- **Retirement:** a full build moves the files listed in `RETIRED`
  (`WF_WAYFARER_001_BURN.blend`, `WF_HABITAT_BURN.blend`, `WF_ROTOR_BAY_DOORS.blend`,
  `WF_HABITAT_POD.blend`)
  to their own `milestones/` folder as `<stem>_RETIRED_<UTC>.blend`, only after
  checking that the file is a generated asset with an empty `ART_` collection and
  nothing hand-made; otherwise the build stops and lists the content. Nothing is
  deleted. `inspect` requires the production file set to be exactly the components,
  the subsystems and the one vehicle.

The preset loop in `inspect` poses every buildable preset and checks the rotation
(a quarter turn in 90 frames for ROTATING, none for STOPPED_LOCKED, index angle at
frame 1), the drive state, hull contacts and the sweep coverage.

The endpoint geometry is modeled; the mechanisms between the states are not
solved: hub bearing/motor/coupler sizing and seals (the hub shows labelled
PROTOTYPE proxies only), the ring section, spokes and lock geometry and strike
fittings, the crew route's seals, hatches and tube telescoping.

## Configurations and operating rules

- The **vehicle** is one saved file (`[vehicle]`); there are no realizations.
- A **configuration** is one of the owner's operating tuples (`[configuration.*]`):
  drive (OFF/ACTIVE with `max_accel_g`), habitat state (`ROTATING` or
  `STOPPED_LOCKED`), fixed radiator state, rotor `controls`, `thermal_load` and
  `eye_mode`. DAMAGED is `buildable = false` because it is fault-specific (OD-010)
  and carries no habitat state or controls.
- Radiators never fold. An ACTIVE drive above `habitat.low_thrust_limit` (0.1 g)
  requires STOPPED_LOCKED rings; rotating rings need a positive rpm and stopped
  rings zero.
- `operating_rules.habitat` states the high-thrust rule: rings stopped and locked,
  never retracted (BASELINE, `habitat_mode_thrust`).

**Forward defense** states are kept apart from the configuration tuples (`[forward_defense.presets]`, PROTOTYPE). A preset row carries only the damage and Crown controls; `field_on` and `field_strength` follow `forward_defense.field_states` (Q4, WORKING): the field zone is shown in COAST, LOW_THRUST, HIGH_POWER and FIRST_IGNITION (14!H16) and hidden in EVA and DOCKED. Every preset keeps damage and repair at 0 and the Crown concealed with closed shutters (14!C20). The control is saved neutral (all 0), so the saved file shows no field. The display poses DEFENSE_ENGAGED (COAST + Crown engaged at azimuth 0.125) and SHIELD_DAMAGED (COAST + damage 0.6, repair 0.3) are only for previews. They are never saved and are not configurations. The EYE eyelid controls `eye_shutter_1..4` (0 open, 1 closed) are 0 in every preset (the Eyes observe); the display poses EYE_SHUTTERS_CLOSED (all closed) and EYE_F1_JAMMED (F1 at 0.6) show closure and a jammed lid, and inspect checks that a closed lid blocks its boresight.

**Crown sector states** (S&E 50 AG-008, Eye 45 FD-E04, PROTOTYPE rig): each carriage carries a gimballed head `Crown_Head_nn` (emitter and launcher turn together about a pivot on the carriage front). Three more controls: `crown_prepare` opens the facing bays' shutters and port covers with the carriages stowed; `crown_point` turns the engaged heads toward `crown_azimuth` by up to `crown_head_max_deg` = 10° (a display limit; pointing range and accuracy OPEN, OD-021), all to the same direction for a distant target (local sub-arrays, no 90 m phased aperture); `crown_fault` × 12 selects one DEGRADED bay whose shutter jams half-open and whose carriage stays stowed. Display poses on the four bays facing 45° (bays 1–4): CROWN_PREPARED, CROWN_ENGAGED (heads at 0.7), CROWN_RECOVERING (carriages at 0.4 on the way back), CROWN_DEGRADED (bay 2 faulted, three engaged); STOWED is every preset. `forward_shield.crown_pose` names each bay's state, and inspect checks the gimbal angles, the emitter rays along each turned boresight and the hardware radius (43.35 m, inside 45 m). No range, power, heat or effectiveness stands behind any of these states. The runtime export bakes the head turns per state (`display.states[*].turn`, runtime axes) and the flight viewer applies them; `crown_bay_detail` is the close-up preview view.

**FWD-V2 Eye placement study** (Eye 45 FD-E01..E03, S&E 50 AG-004..AG-007): `eye_placement.py` screens the wells at r 4 (WORKING), 16 and 24 m (STUDY) against the forward structure, and `studies/eye_placement_study.py` renders the variants in memory on the saved vehicle (nothing saved). At r16/r24 the diagonal wells sit on four truss spokes and cross a truss ring and four layer posts, lose the shared mount and leave the hull; at r4 the Lance sits inside each well's clear field. Results and the owner issue register: [references/FWD_V2_EYE_PLACEMENT_2026-10-13.md](../references/FWD_V2_EYE_PLACEMENT_2026-10-13.md). The production layout stays r4.

**Eye layout switch** (`forward_defense.eye_layout`, user 2026-10-14; STUDY). `selected = "r30"` (user 2026-10-29: 2/3 of the 45 m shield radius, the Eyes as far apart as the review allowed; saved) builds the outer r30 layout through the generators; `"r4"` builds the WORKING source layout above, `"r16"` and `"r24"` the earlier study radii. `spec.apply_eye_layout` moves the well centre radius in memory (the r4 value stays as `source_centre_radius_m`), and `forward_shield.truss`, `disruptor_posts` and `sector_ties` return the alternate truss below (members named `Alt_*`, kinds `shield_truss`, `eye_facet_frame`, `eye_raceway`; raceways stop one clearance off the hull, entry OPEN); a sector tie rerouted onto a well collar still counts as its truss-node tie. At r30 the collars sit between truss rings 25 and 35, so no ring is rerouted, and the alternate-truss screen counts spoke ends on the hub ring, the Crown housing and kept rings as anchored. The skin and layer are cut at the cone wells and ports, the shared EYE mount gives way to the per-facet frames, the rig facet anchors follow the well bottoms, and inspection treats the facets as forward structure. At r30 the Eyes are 60 m apart across the array and 42.4 m adjacent (r16: 32 / 22.6 m). The Drive owner rows keep r4 and B_array 8 m WORKING (FD-B07) and will not be updated (user 2026-10-29), so the owner target `eye_wells` (Q3 r ~4 m) is reported unmet as a declared study deviation, never met. The window-cartridge carrier and sled hardware are not built yet (`eye_release_evidence.handoff`).

**EYE shell** (`forward_defense.eye_shell`, user 2026-10-29, PROTOTYPE/ARTISTIC). Each Eye wears one plate of the fractal facing: `EYE_Shell_0j`, a flat-top hexagonal plate (corners on ±Y, the tiling's orientation) of the facing plate side round the round well, 0.015 m proud of the local face and 0.08 m into the skin, and the disruptor-layer port is the same hexagon. The round well, window and 2.5 m aperture stay inside. The port's inscribed circle keeps the 2.25 m outer-port radius (FD-A04), so the facing plate side went from 2.4 to 2.6 m (apothem 2.252 m); clearances to posts, other ports, the Lance hole, the Crown housing and the collar radius (now 2.85 m) use the hexagon's corner radius. The fractal pattern's EYE keep-out is that hexagon plus the plate gap, so the shell reads as a neighbouring plate.

**FWD-V2 alternate truss for an outer Eye** (owner answers 2026-10-13: Eye 45 FD-A01/A02, S&E 50 AG-A01/A02, 15 FWD-V2-EYE; STUDY, in memory). `eye_truss_study.py` builds the reversible r16 (and r24 comparison) truss the owner selected: each diagonal spoke stops one collar radius before its well and bifurcates into a two-chord collar round the well (centreline radius 2.5 m: the 2.25 m outer port plus the post radius and the shared clearance), with verticals every 90° and the outer spoke resuming beyond it; the truss ring the wells cross (15 m at r16, 25 m at r24) ends on the collars, which carry it through; the four layer posts inside a port move to the collar's radial nodes (clear of the tangential eyelids); the two sector ties that landed on a replaced spoke node move to the collar node of the same ring. The 12-spoke pattern and the Crown bays are untouched. FD-A02: a per-facet backing plate with four struts to collar nodes replaces the shared mount, and a 0.4 m raceway envelope runs from each plate aft out of the truss and inward on the aft face, 1.0 m beside its spoke on the side away from the nearer keel, to the body hull. The screen checks clearances to the wells and facet stacks, the ports, the open eyelids and the structure, one connected structure, no member removed without replacement, member lengths by role (linear mass OPEN), and the window-cartridge service path: a well-wall hatch between two collar verticals, 7.15 m sideways at the window station, then aft out of the truss to the crawler (hatch, seal and latch OPEN; FLIGHT_EVA HOLD). Every size is PROTOTYPE; FEA, stiffness, optical stability, impact rating and frame mass are OPEN. `studies/eye_placement_study.py --alt-truss` renders it, and `studies/eye_truss_plan.py` draws the exact plan sheet (r4 / r16 / r24) with `alternate.md`.

**FWD-V2 Eye geometry-release evidence** (Eye 45 FD-A06 G, S&E 50 AG-A04/A05; STUDY, in memory). `eye_release_evidence.py` (contract `WF_EYE_RELEASE_EVIDENCE` v1) gathers the owner's evidence list for r4 / r16 / r24: one collision table (structure, eyelids through their whole travel against skin, layer, posts and the other wells, Crown, Lance, the cartridge path), a ray trace of the protected field of F1 (43 aperture points, theta 0–60°, through the well, the eyelids in the pose, the layer and its 2.25 m port, the posts, the Lance and all twelve Crown carriages at full engagement; the four facets are equivalent under the layout's 90° symmetry), the window-cartridge service path per facet out of the well wall, aft out of the truss and under the aft face to the body hull, the Brow crawler's approach to that path from its DS-10 track (`crawler_approach`: closest track-to-path gap, the rim gap left after the crawler's half envelope, the cartridge's clearance to the DS-10 hardware, the DS-15 arm base distance), the cartridge hand-off the owner selected (`handoff`, OWN-EYE-H1..H4: well-wall carrier, truss aft-face station, captured raceway sled towed by a crawler; per facet the carrier stroke, the ~95° turn at the station, sled margin, tow and neighbouring-track recovery gaps and the Crown bays to lock; a positive-support sequence in which every hand-over overlaps; r4 as the hub-interior candidate), the mass sensitivity as lengths and break-even linear masses (every linear mass OPEN), and a known/unknown manifest. The field is geometric only (EYE FOV OPEN) and, reversed, the window's directional exposure (impact rating OPEN). On the cone (study wells) the eyelid frame lies on the local face (`eye_shutters` tilt, 0 in the flat hub), so the leaves keep their gap to the skin. `studies/eye_release_sheets.py` draws the section, the field maps, the pose sheet and `evidence.md`.

**Eye cartridge service hardware** (H02, PROTOTYPE, built at r30; `eye_release_evidence.service_hardware`, `WF_FORWARD_SHIELD`
`Eye_Service_F1–F4_*`, kind `eye_service`): per facet the carrier guide from 0.6 m outside the well-wall hatch aft to the truss aft
face, the hand-off station (a clamp frame across the path), the raceway sled (r 1.4 m annular frame, 0.15 m deep) parked there, two
captured sled rails 1.2 m either side of the 19.1 m aft leg and the hull-side service station at r 8 m. The in-well carrier and hatch,
rail supports, mass, tow load, latches and the swap safe state are not modelled (OPEN).

**Radiators** are fixed: `WF_THERMAL` has no hinge, action or radiator articulation control;
its only control is the display-only `RADIATOR_HEALTH_CTRL` and its only drivers are the overlay
hide drivers. The blade matrices are identical in every preset and control state. EVA and DOCKED do not fold, stow or cant them.
The slide mounts, joints and loops stand for thermal strain only; nothing moves in any preset.

**Rough interiors** are three components, `WF_INTERIOR_HABITATION`,
`WF_INTERIOR_WORK` and `WF_INTERIOR_GARDEN`, one per owner function. The
habitat recipe links the matching one into each sector as `Interior_j_k`, in the
sector frame (origin on the centreline at the deck, +X axial with the aft bulkhead
at −X, +Y radially outward), so it spins with the ring. The deck is at r 28 m and
the overhead panel hangs under the 0.05 m skin at r 25.1 m (2.90 m headroom);
deck-to-overhead (r 25–28 m) is 57.9 m³ and holds the owner's 40 m³ usable. Zones line
a 0.9 m centre aisle between the radial side walls. The OPEN overhead hatch sits at the
sector centre, 1.15 m to the side of the crew spoke (HUM-001 zone 4), over a 1.0 m
landing well on side −1 that opens onto the aisle (zone 5).

HABITATION is a human-scale whitebox (HUM-001 zone 6, IND-001 2.2; `sector_whitebox.py`,
`[sector_whitebox]`). Its blocks are envelopes, and the generator draws them as furniture:
- Six berths lie along the spin axis on side +1, in two columns of three, 2.0 m long with
  0.70 m clear over the platform. Rolling over in them turns the head about an axis
  parallel to the spin, so at 4.0 rpm it causes no cross-coupled (Coriolis) stimulus.
- The inner column opens on the aisle. The outer column opens at its aft end onto a
  0.75 m sub-aisle, which is also the couches' free strip.
- Aft down, a sleeper in the inner column stands on its closed aft end, one in the outer
  column on a 0.15 m footboard across the open aft end.
- The top platforms are 1.92 m up. Each column climbs on the lower platforms' edges and a
  0.30 m rung recessed 0.04 m into the near end of each lower berth's opening (the foot
  end, or the aisle side of the outer column's end opening), halfway between the
  platforms: steps of 0.30–0.41 m. A grab bar beside the rungs runs up every berth of the
  column. Nothing enters the aisle or the sub-aisle.
- Two burn couches, 0.70 m wide and 0.45 m deep with the occupant, stand on the aft
  bulkhead with 0.30 m free in front. In coast the occupant stands in a couch, back to
  the bulkhead; under major thrust the same couch holds them supine. Personal lockers
  stand beside the couches.
- Every couch, in every sector, has a five-point harness and a burn-go console on each
  armrest, 0.72–0.86 m above the foot plate, under the hand of an arm hanging at the
  side (0.52 m from the shoulder). Aft down at up to 1.5 g, the arms lie on the armrests
  and work the consoles without lifting against the load (11!A9:J18; Q48(c)).
- The 1.0 × 2.1 m hygiene compartment stands forward of the landing well, with a shelf
  over it.
- 12A SP-22 (six berths per ring), SP-23 and SP-32 fit in 21.6 of the 40 m³. SP-28 (quiet
  retreat) and SP-30 (laundry) don't.

LIFE_SUPPORT_GARDEN_COMMON is a human-scale whitebox too (HUM-001 zone 7, IND-001 2.3):
- The couches and lockers are HABITATION's.
- A booth for six (rated 12 over two rings) stands on side +1, entered from the couch
  strip. Its benches run along the spin axis, so diners face tangentially and nod about an
  axis parallel to the spin.
- A 0.50 m Garden rack on the aisle screens the booth: four closed tray levels 0.45 m
  apart above a reservoir, 2.2 m³ of rack and 4 m² of trays. The gardener faces it
  tangentially and reaches the top tray without steps. Aft down, the trays' contents run
  to their aft ends, so the trays are closed and partitioned.
- The life-support service bay (12A SP-15, with the Garden service SP-44) stands on the
  forward bulkhead of side −1, 0.50 m deep, served from a 0.60 m strip beside the landing
  well. A worker reaches 1.82 m without steps and faces axially.
- The owner's Q50 answer (15!A105, 12!A7, 12!A28): the 80 m³ is the usable volume of the two
  life-support/Garden/common sectors, not planting volume, and the first racks are 4 m² of
  trays per ring (8 m²), as built. Every tray has pull-out slides (two rails and a recessed
  handle; `garden_pull_m` 0.35 m of travel toward the aisle, saved in), so the back of the top
  tray is in reach. The optional later expansion into spare lab space is a display state:
  `GARDEN_EXPANSION_CTRL['expansion']` (0 saved) shows two lit tray tiers (0.92 m²) on the lab
  bench of the work sector, between the bench top and the shelf. No berth, couch or common
  room is converted (15!H105, G106), and no growing area is credited.

WORK_MEDICAL_OPS is a human-scale whitebox too (HUM-001 zone 8, IND-001 2.4):
- The couches and lockers are HABITATION's; with their harnesses and consoles, the two
  couches are the burn station.
- The treatment couch (12A SP-33) lies along the spin axis on side +1, on the aisle:
  2.0 × 0.70 m at 0.80 m, feet aft on a foot plate. The medic works from the aisle,
  facing tangentially. Aft down, a patient on it would stand on the foot plate rather
  than lie chest-to-back, so patients move to a burn couch before a burn.
- Three seated operations stations (SP-39 to SP-41) run along the outer wall behind it,
  entered from the couch strip; operators face tangentially. Medical stowage hangs over
  their displays. Each display stands 0.30 m behind the desk's front edge, 0.60 m from the
  seated operator's eye. The fit-out makes the first station Seraph's post (below), so two
  seated stations per ring are for people and the review operator sits at the second.
- Forward of the landing well on side −1, the lab bench (SP-37) stands on the aisle and
  the workbench (SP-35, with fabrication SP-36) behind a 0.60 m strip off the well. Both
  are 0.95 m high and at most 0.70 m deep; bench workers face tangentially.
- SP-38 fits in the lab or workshop. The closable isolation/recovery berth (SP-34)
  doesn't fit.

The interiors carry 12 berths (two habitation sectors of six)
and 12 aft-facing burn couches against the bulkhead (six sectors of two): rated
occupancy 12, six aboard in the tale. A shot can
link only `WF_HABITAT`, or one sector shell and one interior; shot-local changes go
in library overrides inside the shot.

## Simulation rig

- 42 `WF_SIM_*` anchor empties in the vehicle, with the same frames and sourced
  quantities in `data/simulations/wf_sim_rig.json` (contract version 19), including the
  shield face, the Dust Lance tip, the field zone and the 12 Crown sectors. Anchors
  reference the `IF_*` interfaces, and inspect verifies they coincide.
- The contract separates `flight_thrust` (16.18 MN) from `structural_design_load`
  (29.42 MN). It exports the vehicle and its presets, each configuration's habitat state,
  controls, acceleration limit, thermal load and EYE mode, the low-thrust gravity tilt (11.29°), a `habitat.rings` section (sourced radii and
  occupancy, DERIVED loads, PROTOTYPE frame, sectors, spokes and lock angles), and sections for power
  (survival power is never a restart source), the rotor interface (with the
  `WF_VESTIBULE_SEAL_FAULT` action), the crew transfer route, the docking standard,
  clear passage and capture ring of each port, the refuge shell's water equivalent, `forward_defense` (stations, per-preset control values, Crown
  inputs and power rows with their statuses, the PROTOTYPE engaged envelope
  diameter, 86.706 m (no radial travel), the disruptor layers, sector keels and ties, and the field-zone display metrics) and `radiator_health` (control, sequence steps, PROTOTYPE presets and
  fault order, owner sources with statuses, diagnostics per preset and pose, and the
  unchanged physical area, emissivity and temperature). Its `flight_timeline` section names the First Ignition timeline file with
  its sha256, phases, marks, control bindings and unknown inputs (below).
- Centre of mass, vehicle inertia, mass distribution and drive outputs stay
  `known = false`; no centre-of-mass object is ever placed.
- Massless proxies (`WF_SIMPROXY_*`, nine) hang from the
  anchors: the body envelope, the fixed shield disc and the Dust Lance, the three radiator plates (fixed, anchored at the midpoint of the `IF_RAD_n_ROOT` pair), a ring-sweep keep-out per ring (`WF_SIMPROXY_RING_n_SWEEP`, r 6.5–30 m, ±2.15 m, ROTATING presets) and the hypothetical 15°
  plume keep-out (50 m display reach aft of the exit plane), a study case rather than canon. They are saved hidden;
  `preview.py --sim-proxies show` renders them as wire cages.

## First Ignition timeline

`flight_timeline.py` writes `data/simulations/wf_first_ignition_timeline.json` from `[flight_timeline]` (FUT-004), and the build rewrites it with
the rig. It is data for the flight animation; it changes no geometry.
- **Phases** (PROTOTYPE order, 1739 frames at 24 fps): the induction's three steps, taken from `[induction].sequence` (board docked, the
  visiting craft undocks and the rings spin up, the COAST tour), then the conditioned coast with the coolant loop online, spin-down, stop
  and lock, drive start, the burn, drive shutdown, then unlock and the paired spin-up while the hot blades keep cooling, and coast. The
  ordering follows 08!A47, MEC-011, 11!J4, 07!A39 and Q53 (15!A100, 20!A25:A27, 08!H47): no wait for ambient blade temperature, and no
  radiator cell-loss onset, time or fraction is shown (the failure clock is OPEN, OD-028).
- **Durations:** only the burn (IMPORTED: the 900 rows of the sheet-computed route, 652,166.89 s = 7.5482279 d, 1 frame = 725.436 s) and
  the spin-up (SOURCED, 1800 s, 08!C27) have one. Every other phase is NOT TO SCALE and carries no seconds: spin-down (MEC-010, S6), stop-lock and unlock
  (MEC-011), drive start and stop (S7, OD-009), cooldown (S4).
- **Channels:** each is a control property bound to the vehicle control that shows it (both `ROTOR_n_MECH_CTRL` take the same keys,
  `DRIVE_MANIFOLD_CTRL`, `FORWARD_DEFENSE_CTRL`, `RADIATOR_HEALTH_CTRL`) or a label (configuration, EYE mode, kinematics), keyed as
  `[frame, value, interp]`. The rotor and drive keys re-time `WF_RING_STOP_LOCK`, `WF_DRIVE_STARTUP` and `WF_DRIVE_SHUTDOWN`, and the ring turn integrates the spin (FUT-007, `rotor.spin_turned`); the
  forward-defense, radiator and EYE states follow the configuration a phase shows. Each channel carries its class: SOURCED (the
  kinematics, as imported), DERIVED (the display throttle a / 1.5 g) or PRESENTATION (switching instants and curves).
- **Kinematics** come from the sheet-computed route, never from a Claude formula (NAV-027, 26_BLENDER_CONTRACT C-001):
  `tools/route_import.py` (`workflow.py route-import`) copies 23_ROUTE_FRAMES with 22, 24 and 25 from the capture the `route_frames`
  source record names into `data/simulations/wf_route_v1.json` (scenario WAYFARER_001_IGNITION_V1, DIAGNOSTIC_1D_FIRST_IGNITION), and refuses
  unless 25_ROUTE_VALIDATION rows 2:13 all PASS (C-009). The burn plays one route row per frame, linear between rows (C-010): acceleration,
  speed, traveled distance and mission time are the row's columns. Before ignition they are zero, after it the speed holds; the distance
  after the burn is only a lower bound, because the coast time is OPEN. The timeline stays at the project's 24 fps, so the 900 rows play in
  37.5 s rather than the route's 30 s; mission time is unaffected (22!B17). The distance is traveled displacement along local +X, not a
  heliocentric distance (22!A36). `first_ignition.result` remains only the spec's cross-check of the sourced 20_FIRST_IGNITION values.
- **Flight frames** (FRM-002-2026-10-10, 15!A125, 98!A91, 26 C-017/C-018, WORKFLOW LOCKED / CHANNEL NUMERICS OPEN; refines
  FLIGHT-FRAMES 15!A117): Sheets alone computes and releases the non-trajectory states, as two products. `tools/frames_import.py`
  (`workflow.py frames-import`) declares 12 time-tagged continuous channels (S1–S4 mass, propellant, mass flow and thrust; reactor and
  nozzle power; hot, warm and cold loop heat; S6 measured spin per ring; S7 bus power) and two phase/event streams (OD-010 degraded-mode
  phases, OD-028 radiator-failure events) in `data/simulations/wf_flight_frames_v1.json`. A continuous table has field names in row 1, units in
  row 2, then owner samples with mission_t_s, scenario_id and scenario_version, status, source, the owner's validation and a frame only
  where the sample falls on a 23_ROUTE_FRAMES frame; a phase or event table has its id and start/end (or event) mission_t_s, and an empty
  time stays untimed. Everything is UNKNOWN with null values until Sheets releases its table; a released table is copied as stored and
  refused on any import-fidelity failure. `flight_timeline.bind_frames()` adds a `frames.*` channel per declared channel and stream: a
  released channel keys only its frame-matched samples (null on the next unsampled frame, nothing resampled onto the 24/30 fps frames),
  a stream carries its rows unkeyed; it marks each channel's authority (presentation or sheet-import) and the presentation channels that
  stand for them. The first owner release is planned as the mass, propellant and thrust working scenario (15!I125).
- **Checks** (`flight_timeline.validate`, run with the spec): the rotor display rules at every frame, the rings stopped and locked whenever
  the drive shows output or the ship accelerates, high-power rejection whenever the drive runs, the 07!A39 step order, and no seconds on a
  phase without a sourced duration. Marks `TL_*` (induction, coast start, locked, mid-burn, burn end, cooldown during the spin-up, coast end) name
  preview frames: `preview.py --state TL_*` poses the saved vehicle in memory with the timeline's control values at the mark and
  labels the still with the kinematics, the shown states, their classes and the time compression. Inspect checks every mark on the
  saved vehicle: the file is current, the rotor rules hold and each ring sits at its integrated turn (at its index angle when at rest), the drive drivers
  and exhaust run, the radiator and forward-defense displays match the sample, and the blades stay fixed.
- **Flight shot** (FUT-006): `shots/build_flight.py` writes `shots/SH_FIRST_IGNITION_FLIGHT.blend`. It links the saved vehicle by
  relative path through a fully editable library-override hierarchy, the nested `Assembly_*` subsystem instances included, and keys
  every bound control from the timeline JSON, so the vehicle's own drivers pose it; the vehicle assets stay byte-unchanged. Shot-local
  are the camera (fitted to the ship), lights, world, the `TL_*` markers, one caption per phase shown only in its phase, and a
  geometry-nodes readout of the keyed kinematics. `tests/verify_flight_shot.py` reopens it and checks every mark frame against the
  timeline; it still passes after the assets are rebuilt.
- **Navigation stage** (NAV-001, C-015): `shots/build_nav_stage.py` writes the stand-alone `shots/SH_NAV_STAGE.blend` from the imported
  route at its 30 fps, frame n = row n over 1–900. Metres become display units through one named, reversible transform (NAV_DISPLAY_GM,
  1 unit = 1e9 m, on the scene and on `NAV_DisplayTransform`, C-004). Two scenes share the track, the whole-AU ticks and the events with a
  numeric displacement (IGNITION_START, DAY_1_MARKER, HALFWAY_IN_TIME, TARGET_SPEED_REACHED, 24!D): ANALYTICAL shows the true 1D geometry
  with a symbolic marker, orthographic; PRESENTATION adds the vehicle, linked one way (no override) and enlarged 1e8 times with a label,
  riding the marker under a following camera. Both carry the permanent DIAGNOSTIC 1D legend (NAV-030), a readout of frame, mission time,
  acceleration, speed and traveled AU from the row, and the OPEN events (shutdown, Kuiper deadline, first loop, return) as a list, never
  placed (C-008). No Sun, planets or ephemerides: the frame, epoch, heading and ephemerides are OPEN (25!F14:F15). `tests/verify_nav_stage.py`
  checks every frame's marker (through the inverse transform) and readout against its row, the release gate and the one-way link.
- **Unknown:** centre of mass, inertia, mass history, drive outputs, waste heat and heat debt, rotor losses and spin-down, the hotel power
  source, degraded modes and the plume boundary stay `known = false` in the JSON's `unknown` block. The durations and release thresholds
  stay with S4, S6, S7 and 20!E25:E26.

## Heat-loop screen

**Y155 radiator material scenario (owner 2026-10-17, OWN-RAD-Y155; 40!A110:F123, 98!A108, Technology 01!A20 T17).** An opt-in comparison,
never a build input (`radiators.y155_scenario`, source `radiator_y155`): the root baseline stays emissivity 0.90 and view factor 0.90 on
the same three 182.149 m blades at 1800 K (40!B7:B10, B23 unchanged). `thermal_budget.y155` applies the sheet's formulas: uplift
(ε/0.90)(F/0.90), same-geometry ideal rejection 40!B10 × uplift, equal-load area fraction 1 − 1/uplift and the residual against the 16 GW
calibration. Y155 study (ε 0.96, F 0.92, WORKING SCENARIO / UNQUALIFIED): ×1.09037, 15.703 GW, −8.3 % theoretical area, 0.297 GW deficit;
optimistic sensitivity (0.98 / 0.93): ×1.12519, 16.204 GW, 0.204 GW ideal spare (not a margin). Every result is DIAGNOSTIC / UNQUALIFIED:
no blade is shortened or resized, and actual drive heat, other loads and 1800 K material qualification stay OPEN. The rig carries the
cases (`thermal.y155_scenario`, contract v42).

No temperature rise is shown: the loops' heat capacity and the Heat Debt state are OPEN (40!B13, B15). The actual drive waste heat
(40!B11) stays OPEN. Sunlight and the space background are left out: neither is sourced and the Sun distance is UNKNOWN. The blades are
never resized or recoloured. Check `flight-thermal` (4 checks): it reproduces the rig's `thermal_budget` rejection and 16 GW residual
for every Y155 case and 40!B17's ideal area to 1e-9; checks the energy bookkeeping (gross = net + self-view, the required temperature,
the debt integral) and the honest labels; and confirms that no blade, pivot, hot-face, frame or state changes. Stills:
`runs/20261017T1930Z-thermal-explorer`.

`thermal_loops.py` (AFT-010, `[thermal.loops.study]`, PROTOTYPE) writes `references/p1_thermal_loops.json`, a DIAGNOSTIC screen for owner
question Q38: it samples candidate warm (casing, collar, shield-shadow panels) and cold (ring rims and faces) surfaces against the
1800 K blade faces by ray casting and reports where a gray surface rejects heat and where it absorbs more than it emits. It selects no
area: `thermal.loops.warm.area` and `cold.area` stay `known = false`, and `radiators.view_factor` is never written.
- With the blades at full duty (HIGH_POWER) every warm candidate is net-heated: the casing absorbs 654 MW, and the rings 327 MW (201 MW
  on the aft faces, 122 MW on the inner rims), so the outer rims are no cold radiators then. Only the ring fore faces stay usable
  (0.15 MW). With the blades dark, the casing alone bounds the warm loop at 14.37 MW ideal, below the 15 MW normal band; all warm
  candidates give 13.8 MW, a 1.2 MW shortfall, and the cold candidates 1.38 MW.
- The blocked directions exchange nothing (`zero_exchange_assumption`). That is optimistic for the cold loop, since the hull is a
  ≥450 K warm surface under the study's own premise, and pessimistic for the dark-blade warm shortfall, since cold blades would be
  sinks; the report flags every finding that depends on it.
- The casing sees the blades at a mean F of 0.20, context for revalidating the 0.9 blade view factor (40!A23).
- **Candidate warm panels (Q38, built).** The owner accepted the direction (15!A98, 40!A67:F68): no warm or cold capacity from the
  hot-facing casing or ring surfaces; dedicated, baffled, cold-space-facing 450 K panels; capacity left unknown, candidates shown
  PROTOTYPE only (15!I98). `warm_panels.py` (`[thermal.loops.candidate_panels]`) places them where the screen's blade-plane family is
  least irradiated: in each blade plane, forward of the blade front and inside the shield shadow, where the blade is seen edge-on. The Q45
  bypass collar runs a planar truss in each blade plane there, so each candidate is a pair of 0.10 m single-sided plates flanking the
  collar truss (radiating faces outward), carried on brackets to its chords. They run from r 31.5 m (ring rim plus the 1.5 m ring service
  clearance) to r 37 m (the shield shadow), and from the collar's aft station to the shield truss, split into three segments around the
  collar's r 35 m hoops: 18 `Warm_Panel_<plane><P|M>_<k>` in WF_THERMAL, 746 m² of outward faces in all, about a tenth of the
  7,170 m² that 15 MW needs ideally (15!G98). The spec rejects a panel inside the ring service clearance, the shield truss, the collar
  members and hoops or a dock corridor, and any value for `thermal.loops.warm.area`. The baffles, the coolant route (the collar's aft
  spoke is the natural path to the casing), the temperature map and the net balance against the blades stay OPEN; the screen's panel
  zones (r 30.15 m inward edge) remain the closest DIAGNOSTIC, and no HIGH_POWER rejection is claimed (40!F68). No cold hardware is
  built: in HIGH_POWER only the ring fore faces see no blade (0.15 MW in the screen).
- **HR-001 heat-recovery study (not built).** Owner-approved L2 study (S&E 15!A193:A196, OD-041; source `hr001_heat_recovery`): a
  bypassable hot-loop → intermediate loop → H2 preheater branch on each hydrogen line before the injection ring, Brayton A/B unchanged.
  `studies/hr001_packaging.py` compares a shielded engineering-bay location (A, four new shadow-shield sleeves, 20 m of preheated H2) with
  the aft drive annulus beside the injection ring (B, no shield change, 1.5 m of preheated H2); both clear every built member by 0.21 m.
  B is the selected reversible candidate ([HR001_PACKAGING](../references/HR001_PACKAGING_2026-10-16.md)). Each hydrogen line keeps its built
  run as the bypass: the HR-002 valve table opens the branch only in PREHEAT_STUDY / HYBRID_STUDY, so BYPASS, BRAYTON_BASELINE,
  HX_FAULT_ISOLATED and NO_DATA are the built line (`topology()`, PASS). `studies/hr001_states.py` adds unpowered valve positions that
  land in BYPASS, BYPASS in every ship configuration (HX_FAULT_ISOLATED when DAMAGED), telemetry shown only from owner-approved samples, and
  fourteen faults that each keep hydrogen flowing and the hot branch isolated (three with unresolved consequences). Owner 2026-10-17
  (15!A203 OWN-HR, 98!A113) accepts candidate B as the preferred L2 packaging study only (fail-to-BYPASS, Brayton A/B and the original
  H2 line kept; energy and flight HOLD) and routes HR-F09 (Brayton trip), HR-F10 (HX breach contaminating H2) and HR-F11 (field / plume /
  dose / optical interference) to its supplemental register S&E 39!A32:I36 (distinct from the older F09..F11): each carries the owner row,
  trigger, routing and HOLD gate, and a step replay of the owner response; the bypass isolates the branch but never the consequence
  (heat that must still be rejected, contamination already in the line, an undefined field envelope). `studies/hr001_readback.py`
  returns the regression, proxy volumes, symbolic equal-power / equal-thrust accounting and the owner input packet
  ([HR001_READBACK](../references/HR001_READBACK_2026-10-16.md)); every duty, mass, rating and
  the plasma, field and dose keepouts stay OPEN / HOLD, and nothing is in the saved model.

## Life-support stock and flow

Milestone C (S&E 58 MECH-003, 59 POL-009). `data/life_support.toml` holds the owner's 41_SURVIVAL_RESOURCES study rows (read
2026-10-17; 41!A2 "numeric study targets are NOT canon"):
- five conventional consumers; Seraph eats no human food (41!B7, 38 S27);
- 2,191.5 days;
- per consumer-day: O₂ 0.84, CO₂ removed 1.0 (proxy), water turnover 4.16, food 1.83 with packaging, waste 1.0 kg;
- the 10 t food launch category (41!B21, consumables included);
- water recovery as the owner's 90 / 98 % scenarios (38 S05: 98 % not achieved);
- no O₂ recovery and no Garden credit (38 S02, 41!B20);
- O₂ and makeup-water stores OPEN (38 S03, S05).

`src/wayfarer/life_support.py` integrates per day. For each resource, need = Garden + recovered + drawn from the store + deficit; an
OPEN store has no number, so its draw counts as required. A store that empties stops supplying, the rest becomes a deficit, and the
exact empty day is recorded. Run through the simulator, the owner's eleven 41 results come out exactly:
- food 20,052.225 kg, shortfall 10,052.225 kg;
- 72 h for 12: O₂ 30.24, CO₂ 36, loop water 149.76, potable 90, rations 65.88 kg;
- waste 10,957.5 kg;
- 98 % recovered water 44,671.536 kg;
- makeup 4,558.32 kg at 90 % and 911.664 kg at 98 %.

The 10 t category runs out on day 1,092.9 for five consumers (day 455.4 for twelve).

Checks:
- `life-support` (4): the module's checkpoints for four scenarios, the 41 results, the daily mass ledger (worst 3e-9 kg) and the labels;
- `tests/test_life_support.py` (5).

Stills: `runs/20261017T2000Z-life-support`.

## Hull and service fittings

- **Hull:** `WF_HULL` lofts a PROTOTYPE service casing through the eleven
  `[[layout.stations]]`, rebuilt for the 225 m ship (the legacy station radii are
  SUPERSEDED). It skins X −101.75…82.75 m and 93.35…112.25 m and leaves the
  thrust ring and the ring bay (the ring sweep plus clearance) open; the forward
  collar ends 0.15 m behind the shield skin, inside the truss hub opening (r 7.0 m).
  The aft body is r 6.0 m from the blade aft edge to the blade front, then tapers to
  the 13 m body (r 6.5 m) within the 0.70 m before the bay; the forward collar is r
  6.5 m. Radiator root booms, bay stays, the three service fittings and the four
  shield-mount struts pass through 31 derived openings (the forward collar also encloses the three sector keels, r 5.15 m outer edge, 0.15 m clearance to the inner skin), all flagged OPEN. The 0.75 m lip aft of the blade aft edge also
  keeps r 6.0 m.
- **Service:** `WF_SERVICE` holds the airlock, the two docking ports and the
  refuge (rated for 12) in the forward collar, ahead of ring B's sweep and withdrawal
  path. The fittings
  stand on a 0.3 m collar, to r 6.8 m: they are outside the body zone and bounded by
  the 14 m BASELINE maximum body diameter.
- **Primary boarding route (HUM-001 zones 1–5):** `Dock_Primary` is a hollow pressure
  route along the port axis, from the docking face (r 6.80 m) inward: the outer neck
  (0.80 m clear radius, the 1.6 m passage of Q33) through the hull; the outer hatch
  (frame r 0.80–0.90 m, leaf r 0.85 m × 0.06 m) on the chamber side of the outboard
  bulkhead; the `Dock_Primary_Entry_Chamber`, 2.6 m clear diameter × 2.2 m clear length
  (r 3.85–6.05 m, 0.05 m walls, 0.15 m inside the collar skin); the inner hatch on the
  inboard side of the inboard bulkhead; the `Dock_Primary_Trunk_Node`, 2.6 m clear
  diameter × 1.95 m (r 1.85–3.80 m); the inboard neck to r 1.2 m; and the hollow
  `Crew_Connector_Dock_Primary`, 0.80 m clear, which meets the trunk as an equal tee
  through the trunk and spine walls at X 99.40 m (each hollow connector starts on the trunk's outer skin, so its walls never share the
  trunk wall's volume). Both leaves seat from the ship side,
  so cabin pressure holds them shut. Each swings 90° on its hinge and parks beside the
  passage (0.84 m from the axis, 0.06 m from the wall): the outer leaf into the chamber,
  the inner leaf inboard into the node, whose floor sits one 0.05 m swing clearance
  below the open leaf. Both rooms take their 1.3 m radius from that parking geometry.
  Each room has two yellow handrails (±w) and two light strips; the chamber has a
  leak-check/equalization panel and two equalization valves, and the node has a ship-side
  hatch panel and valve. Both panels sit at 104° (+w side, just below the rail, about 1 m
  above the aft wall), so crew standing on the deck band face them (IND-001). All stay outside the clear passage and both leaves' swings.
  The trunk has two handrails (135° and 255°) and light strips (75° and 315°) that stop
  0.20 m clear of every branch opening, and the thrust ladder at 285° (see the thrust
  review below); together they leave a 1.10 m clear circle inside the 1.6 m bore. `DOCK_ENTRY_CTRL` (`Dock_Primary_outer_open`, `Dock_Primary_inner_open`,
  0–1) opens the leaves; it is saved closed, and DOCKED alone does not open them. The
  vehicle file holds two generic 1.8 m mannequins: `Human_Entry_*` in the chamber (head
  inboard, facing the panel, one hand on the rail, reach 0.63 m) and `Human_Trunk_*`
  floating head-first aft along the trunk just aft of the junction (one hand on a rail,
  reach 0.36 m). There are four 18 mm cameras: `CAM_HUM_ENTRY_PORT` (entering, looking
  inboard), `CAM_HUM_ENTRY_EYE` (the chamber mannequin's eye on the panel),
  `CAM_HUM_NODE` (through the inner hatch, down the neck) and `CAM_HUM_TRUNK_EYE` (the
  trunk mannequin's eye, aft along the trunk). All are non-canon guides.
  Zone 3 (rotary transfer, 12A SP-06): 16.8 m aft of the junction the trunk tees into
  ring A's single spine port, `Crew_Port_1_1` (0.80 m clear, on sector 1's hatch angle,
  90° at the index), at X 82.60 m, trimmed to the chamber's inner radius (a saddle), so
  none of it stands in the drum's annulus. The hollow `Crew_Vestibule_1` is ring A's
  despun transfer drum (Q46, below), on its own bearings on the spine. Its
  chamber is 1.80 m clear between 0.05 m end walls (u −3.40…−1.50 m: the port's 1.70 m
  outer diameter plus a 0.10 m seal allowance at each end) and 0.95 m deep (r
  0.975–1.925 m: the 0.70 m suited envelope between handrails on both walls). It is open
  toward the stationary spine, between the primary seal planes, with the guard rings
  outside them. The annular chamber joins the one port to all three sector hatches, so
  ring A has no other spine ports. On the rotating outer wall: three axial handrails
  midway between the hatches, three light strips, a frame around each 1.6 m sector
  hatch (a flat seal land in the crew tube's collar, its face on the wall's crown, so
  nothing hangs into the annulus) and a transfer panel (seal
  and guard-cavity pressure, hatch, spin and index-lock status) beside the rail next to
  the port. A third mannequin, `Human_Vestibule_*`, floats along a chord at mid-depth just
  past the port, holding that rail (reach 0.37 m), placed for the rotor at its index
  angle. `CAM_HUM_VESTIBULE_PORT` looks up from the trunk through the port, and
  `CAM_HUM_VESTIBULE_EYE` looks around the annulus to the sector-2 hatch.
  Zone 3 at ring B (12A SP-07, the redundant route): `Crew_Vestibule_2` is built the same
  way, with one spine port `Crew_Port_2_2` at X 88.95 m on its sector-2 hatch angle (210°
  at the index, so the trunk ladder runs beside it; thrust review). It
  has less axial room: hub 1's forward cartridge-withdrawal paths end at X 88.00 m, so
  with the 0.15 m clearance only 1.60 m is free aft of rotor 2's lock pins, and a 1.6 m
  port would need 2.30 m. The port is derived down to the largest that fits, 0.90 m
  clear (0.20 m wider than the suited envelope, above the ~0.8 m clear passage of
  current docking hatches); its guard ring sits on the clearance. Moving hub 1's
  withdrawal paths instead would change the P1-008 service interface to make a zone fit
  (15!H86). The chamber is 1.10 m clear (u −2.70…−1.50 m, X 88.35–89.55 m) and 0.95 m
  deep, the outer hatches take the port's 0.90 m, and the light strips are trimmed to
  0.90 m; rails, frames and the transfer panel are ring A's. `Human_Vestibule_B_*` floats
  at the port like the ring-A figure, and `CAM_HUM_VESTIBULE_B_PORT` and
  `CAM_HUM_VESTIBULE_B_EYE` repeat the two vestibule views.
  Despun transfer (Q46, MEC-019: BASELINE architecture, every size PROTOTYPE;
  `crew_transfer.closures`, `transfer_stack`): each ring's vestibule, its guard rings and
  its fixtures are the transfer drum, parented to `Drum_j` instead of the rotor; the
  guard rings carry its bearing races, seals and despin drive (OPEN), and no struts tie
  it to the rotor. Saved despun, it sits at the index angle under its spine port; with
  `TRANSFER_j_CTRL['drum_sync']` at 1 it turns with its ring (the rotor's driver scaled
  by drum_sync, a display, not a control law), so its three openings stay on the crew
  tubes. At the index angle the openings line up in either state, which is the owner's
  backup (isolate, controlled ring stop, indexed transfer). Three closures, saved
  closed, all curved 0.04 m plates that lap their clear opening by 0.05 m and ride a
  0.01 m track gap: the stationary-side gate `Crew_Port_j_k_Gate` in a pocket of the
  0.10 m spine shell between the trunk and the spine core (r 0.88–0.92 m), sliding
  forward 1.80 m on ring A and 1.10 m on ring B; a door per opening on the outside of the
  drum wall (r 1.985–2.025 m), sliding round the drum 55.7° (ring A) or 34.2° (ring B);
  and, across a 0.03 m running gap, the rotating-side hatch `Crew_Tube_j_k_Hatch` in each
  collar's base (r 2.065–2.105 m), sliding round the ring 53.6° or 33.0° into a pocket
  beside the collar. Least placement margins (`crew_transfer.transfer_fit`): the gate
  0.02 m inside the spine shell, parked 0.10 m clear of its port; the doors and hatches
  parked 0.53 m and 0.64 m clear of the next opening; ring A's hatch 0.035 m below its
  collar's first miter. Each opening frame is now the door's seal land on the drum.
  Transfer while a ring spins: in the drum, despun, crew hold the drum's rails (still
  relative to them); the gate closes, the drum spins up with them inside (0.03 g at
  mid-depth at 4 rpm), latches, and the door and the chosen tube's hatch open. The
  reverse leads to the spine and the refuge with the rings spinning (I4). Seen from
  the spine, crew never touch a surface that moves past them.
  Zone 4 (crew spokes, 12A SP-08): each ring-A sector hatch opens into `Crew_Tube_1_k`,
  a hollow tube (0.80 m clear, 0.05 m wall) along its axis. A radial collar starts
  across the running gap from the drum (r 2.055 m) and ends 0.85 m beyond the drum
  wall. It then turns 45° sideways while advancing 0.65 m, and 53°
  forward in a second mitered elbow at r 5.5 m (both inside the 13 m body, 0.03 m
  spare). From there it runs radially out beside its crew spoke on the ring plane,
  1.15 m off the rail plane (tube and rail radii plus the 0.15 m mechanical clearance,
  so neither rail nor web lacing between them touches it), to the overhead hatch at the
  sector centre. Five pairs of brackets tie the run to both rails. A 1.7 m tube fits
  neither between the rails nor aft of them inside the 3.5 m sector, which is why it
  runs beside the spoke. Inside, a ladder runs on the wall facing away from the spoke:
  stiles 0.40 m apart and 0.16 m off the wall (boot room) through both elbows, and 65
  rungs at 0.30 m on the run, where spin gravity grows outward. A grey fall-arrest rail
  (0.04 m) runs on the ladder's centre line, resting on the climber's side of every rung
  and bracketed to the wall through the collar and elbows, from the stiles' start to
  their end above the sector hatch (24.5 m). Crew clip a sliding arrester to a chest ring
  in the collar (0.04 g) and unclip at the hatch, feet 1.59 m above the deck (0.50 g).
  Light strips run on the wall facing the spoke, leaving 1.10 m clear between the rail
  and the lights. Above the sector hatch, a tube-side hatch
  panel (leaf drive, equalization, sector pressure) sits 50° around from the ladder,
  1.45 m above the lowest tube rung (reach 0.55 m from a climber standing there). A fourth mannequin, `Human_Spoke_*`, climbs the sector-1
  ladder with its feet at r 11.1 m (about 0.2 g at 4 rpm), both hands on the stiles
  (reach 0.38 m), clipped to the rail by an arrester at chest height. `CAM_HUM_SPOKE_TOP` looks down the shaft from the top of the run past
  the climber, and `CAM_HUM_SPOKE_EYE` looks up the ladder to the elbows.
  Zone 4 at ring B: a 1.6 m tube is 1.70 m outside, longer than ring B's 1.60 m
  vestibule and its 1.20 m chamber wall, so it can neither stand on the vestibule nor
  open through its wall. Each ring-B hatch therefore opens into a neck: `Crew_Tube_2_k`
  starts as a 0.90 m clear neck (0.05 m wall) that rises from the chamber through the
  outer wall to a bulkhead of the passage wall at r 2.15–2.20 m, 0.175 m above the
  wall. That height leaves room above the hatch frame for a leaf seated on it; the
  closure itself is Q46. Above the bulkhead the tube is ring A's: 0.80 m clear, a collar
  one tube radius above the bulkhead, the same elbows (45°/45°/52°), run, brackets,
  ladder (65 rungs), fall-arrest rail, light strips and hatch panel, 24.1 m along its axis (ring A's
  24.7 m; ring B's hatches sit 0.35 m nearer the ring plane). The stiles start 0.20 m
  above the bulkhead. Ring B's inner hoop is opened for the tubes like ring A's, so the
  route reaches the deck of every ring-B sector. `CAM_HUM_SPOKE_B_BULKHEAD` looks down
  the sector-2 collar (the spine port's sector) from the first elbow at the bulkhead and
  the neck. A second climber, `Human_Spoke_B_*`, stands near the top of ring B's sector-2 run (feet at
  r 7.33 m, 0.13 g), where a descent on ring B feels the Coriolis push most.
  Zone 5 (the occupied sector, the same in all six through the shared `WF_RING_SECTOR`):
  the sector envelope is a 0.05 m pressure skin inside the unchanged envelope. Ring A's
  inner hoop is opened for each hollow tube, which passes through it and lands on the
  skin, and the skin and the overhead panel are opened under it. `Sector_Hatch_Frame`
  (r 0.80–0.90 m) hangs 0.08 m below the overhead panel. The leaf (r 0.85 m × 0.06 m)
  seats on it from the sector side, so sector pressure holds it shut if the tube loses
  pressure. It is shown open: dropped 0.02 m off the seat and slid 1.75 m toward the
  aisle on two guide rails, parked 2.74 m above the deck. A hinged 1.7 m leaf fits
  neither the 1.6 m tube nor the 2.9 m sector without blocking the well. The ladder
  breaks at the leaf, 0.05 m clear on each side, and continues to the deck on the same
  rung grid: 9 rungs at 0.30 m, the first 0.25 m above the deck. It stands in front of a
  utility chase (leaf drive, equalization valve, power and data) carrying the hatch
  panel and a light strip, in a 1.0 × 1.62 m landing well that opens onto the aisle. A
  climber faces the ladder and steps back into the aisle. Two light strips sit over the
  aisle ends. The tube ladder faces away from the spoke: antispinward on ring A, so the
  Coriolis push on a descending climber presses them onto the rungs, and spinward on
  counter-rotating ring B, where it pulls a descending climber off them. A fifth
  mannequin, `Human_Landing_*`, stands on the deck of the sector-1 well at the foot of
  the ladder, both hands on the stiles (reach 0.54 m). `CAM_HUM_LANDING_EYE` looks up
  the ladder through the open hatch into the tube, and `CAM_HUM_LANDING_AISLE` looks
  from the aisle at the well, the ladder and the hatch.
  The refuge leg (OD-011 access path, 12A SP-14): 3.85 m aft of the junction the trunk
  tees into `Crew_Refuge_Port`, a hollow port at X 95.55 m (0° about the ship axis) that
  rises 0.25 m through the spine core into the storm refuge's unshielded inner face, so
  it crosses no shield. It is 0.90 m clear, the size of ring B's spine port, the route's
  narrowest point (0.10 m round the suited envelope), and opens 64° (18 %) of the spine
  core where a 1.6 m port would open most of it. Like the spine ports it is trimmed
  flush to the cavity's face and has no closure. On the trunk wall a 0.60 m rail at the
  port's angle on each side, 0.20 m beyond it (`Crew_Trunk_Refuge_Rail_*`), lets crew
  from the dock or the rings stop at the port and turn in: 0.44 m from the shoulder of
  crew floating beside the rim, where the trunk rails at 135° and 255° are 0.87 m away,
  beyond reach. `Refuge_Inner_Wall`, a 0.05 m pressure
  wall inside the 0.15 m clearance to the spine, closes the cavity's inner face, so the
  cavity keeps its 53.85 m³ (4.49 m³ per person). Inside the 1.79 m deep, 2.40 m long
  annulus: a hoop handrail round the inner wall 0.20 m beyond the port on each side; one
  axial anchor rail per rated occupant on the outer wall, 30° apart, the occupants lying
  axially inboard of them (1.8 m fits the 2.40 m length, not the 1.79 m depth), 0.57 m
  between suited bodies and 0.30 m from the end walls; six light strips between every
  other pair (one across from the port); and the refuge panel (dose rate, pressure and
  air, communications, port status) on the inner wall 60° from the port. Between the
  inner-wall fixtures and the occupants a 1.64 m circulation radius leaves 0.11 m round
  the suited envelope. Under thrust the aft wall is the floor: 2.40 m of headroom and
  1.87 m² per person. An eighth mannequin, `Human_Refuge_*`, floats beside the port over
  the aft hoop rail, head toward the port, one hand on the rail (reach 0.28 m) and the
  panel 0.51 m from its shoulder. `CAM_HUM_REFUGE_PORT` looks up from the trunk through
  the port, `CAM_HUM_REFUGE_EYE` looks round the annulus past the port to the
  anchor rails, and `CAM_HUM_REFUGE_APPROACH` looks forward along the trunk at the port
  as crew from the rings arrive.
  Thrust review (I1 and OD-006: emergency paths for both gravity vectors; I4): for major
  thrust the rings stop and lock and aft is down, at up to 1.5 g through the 7.5-day
  First Ignition ramp and up to 0.1 g in LOW_THRUST, so the trunk is a shaft.
  `Crew_Trunk_Ladder_*` stands on the trunk wall at 285°. It has the tube ladders' 0.40 m
  stiles, 0.16 m standoff and 0.30 m rungs, and runs from the trunk's aft end (the floor,
  X 81.65 m, beside ring A's spine port, whose sill is 0.15 m up) 16.96 m to just short of
  the primary branch, with 56 rungs from 0.25 m above the floor. `Crew_Trunk_Arrest_Rail`
  runs on its centre line and rests on the rungs, as in the crew tubes. Ring A's 1.6 m
  port opens the half of the trunk wall around 90° at the floor, so the ladder stands on
  the other half. Ring B's spine port moved to its sector-2 hatch angle (210°) and the
  refuge port stays at 0°, so the ladder runs midway between them. A stile passes 0.07 m
  beside each mouth, a rung stands at each sill (6.85 m and 13.45 m up), and the rail is
  0.50 m from the mouth's edge, so crew clip on from inside the port. The ladder ends
  0.20 m below the primary branch's sill (16.95 m up); the service dock and the airlock
  above it are not reached. A ninth mannequin, `Human_Trunk_Climber_*`, stands on the
  ladder with its eye level with the refuge port, both hands on the stiles (reach 0.38 m),
  clipped to the rail, with the port's rim 0.60 m from its shoulder. `CAM_HUM_TRUNK_SHAFT`
  looks up the shaft from the floor, and `CAM_HUM_TRUNK_CLIMB_EYE` looks across from the
  climber's eye into the refuge port.
  `human_entry.check()` screens the passage from the docking face to the trunk, the hull
  gap, both leaf swings, fixture intrusions, the trunk fixtures against the branch
  openings, every neighbour, the vestibule chamber against the port and the suited
  envelope, its fixtures against the port passage, each crew tube's fixtures against
  its bore and the suited envelope swept along its axis (and through ring B's necks),
  the landing's leaf sweep, well, fixtures and the blocks of every function, the
  suited envelope down the hatch axis to the deck and across to the aisle, the refuge
  port, fixtures, occupant stations and circulation annulus, the emergency route (the
  port rails' reach, and the distance and rungs from each sector's aisle to the refuge),
  the thrust review (the trunk ladder from the floor, a rung at each sill it passes, its
  stiles beside the mouths, falls to the floor and each sector's way to the refuge with
  aft down), the Q47 footing (each inclined leg's floor ladder and its first and last
  step, the run's handrail height, the step below the sector hatch and the headroom
  above it, each drum chamber's crawl rail), and all eleven mannequins'
  fit and reach (each climber 0.03 m from the fall-arrest rail, its arrester on it),
  and the push across each ring's tube ladder (`human_entry.ladder_push`).
  The vestibule screen sweeps the suited envelope through each spine port and around
  each annulus at mid-depth (0.04 m to the handrails in both rings; ring B's port
  leaves 0.10 m). `inspect` sweeps a suited body (two chords of the route,
  bending at the hip) every 0.1 m along `human_entry.route`, from outside the docking
  face to the aisle of every sector of both rings, and into the refuge from the dock and
  from the spine ports (route `E`, the emergency approach) round its whole annulus,
  against every built surface, docked with the entry leaves open (least
  margins: entry 0.45 m, trunk 0.20 m (the trunk ladder's rail), vestibule 0.04 m in both rings, ring B's spine
  port and necks 0.10 m, tubes 0.10 m on ring A and 0.08 m on ring B, where the body
  turns from the annulus into a neck, landing 0.10 m, refuge 0.09 m past the refuge
  panel and 0.10 m in its port from aft). The eye-level reviews and their open items are in
  [HUM001_EYE_REVIEW](../references/HUM001_EYE_REVIEW.md) (ring A, zones 1–5) and
  [HUM001_EYE_REVIEW_RING_B](../references/HUM001_EYE_REVIEW_RING_B.md) (ring B, zones 3–5)
  and [HUM001_EYE_REVIEW_REFUGE](../references/HUM001_EYE_REVIEW_REFUGE.md) (the refuge leg
  and the emergency route to it) and [HUM001_THRUST_REVIEW](../references/HUM001_THRUST_REVIEW.md)
  (the route with aft down: the trunk ladder) and
  [HUM001_Q47_THRUST_ROUTE](../references/HUM001_Q47_THRUST_ROUTE.md) (the footing for
  every essential route with aft down, and every leg in both gravity vectors).
  `presentation/entry_preview.py` renders the exterior, the twenty eye views, a cutaway
  through the port and the junction, a cutaway of the whole trunk, a cutaway through
  each ring's vestibule (on ring B up through the neck and bulkhead), a cutaway along
  the crew tube of each ring's spine-port sector (ring B's labelled with its ladder
  push), a cross-section of the sector-1 landing and a cutaway of the refuge through its
  port.
- **Survival envelopes (12A SP-46–54, Eye 50!A25:A30; `survival_fit.py`, `[survival]`, `components/survival.py`):**
  PROTOTYPE envelopes inside existing spaces, as 34!B110 asks, each tagged with its SP, source and installed volume
  (kind `survival_envelope`; the sector ones are fit-out elements). Size, mass, power, heat and contents stay OPEN in
  the owner rows, and nothing feeds a budget.
  - Storm refuge: an SP-48 service rack at each end of the annulus opposite the port (0.42 m³ with the rest; the refuge
    net becomes 53.43 m³), the SP-50 triage kit at the aft end, and the SP-54 / Eye A30 hazard alarm on the forward end
    cap. All are clear of the port leg (0.52 m), the hoop rails (0.17 m) and the twelve occupants' envelopes (0.19 m).
  - Ring sectors: the SP-50 overhead medical unit above the treatment couch (in the overhead zone), the SP-47 sealed
    incubator on the lab shelf, the SP-46 sealed waste collection point as the workbench cabinet (its door and filter on
    the cabinet face; collection only, not processing: WK-HYBRID-2026-10-10, 15!I115), and an SP-54 hazard and cue panel high on every sector's aft bulkhead. None enters the aisle, well or strips.
  - SP-49: one 1.8 m³ rack bay of the SP-45 storeroom for general clean stock (12A I52), placard "SP-49 STOCK"; cartridge
    exchange, heavy fabrication and contained SP-46 processing belong to a stationary machine-bay candidate, surveyed as an
    envelope only (references/SERVICE_HOST_SURVEY.md: no free stationary 4.0 m bay has its own trunk port). SERV-002-2026-10-10 (15!A123) prefers the forward X 100.4-108.9 m district as a study: two NONCANON access mock-ups (trunk extension, external corridor) with separate workshop, sealed-cell and SP-52 warm containments screen clear, in references/SERV002_FORWARD_DISTRICT.md; nothing built.
  - Outside: the SP-53 / Eye A25 lasercom terminal and the A26 RF dish on 0.45 m masts at the 90° and 210° bisectors
    between the blades (X 40 m, heads inside the 14 m maximum body diameter), and two A29 star trackers at 330°. Each has a clear 55° cone about its boresight
    against the blades, rings and shield (sampled screen).
  - Guided-EVA handrail (S02 slice 4, PROTOTYPE training fixture; EVA-048 HOLD): along `eva_route` at the airlock azimuth (50°) on the
    forward collar, `Ext_EVA_Rail_Aft` (X 100.6→95.6 m) and `Ext_EVA_Rail_Forward` (X 103.1→106.0 m) on standoffs at every anchor
    station, a tether anchor ring beside each standoff and a foot-restraint plate on the collar straps at each hold; ochre. No crew
    rail crosses the rotor bay.
  - SP-51: per blade a two-rail crawler track on the casing, from 2 m inside the blade's aft end
    to 2 m inside its front, 2.3 m off the blade plane outside the root truss (0.45 m clear), with seven docks (each root and stay, and a charging dock forward). It is 1.30 m clear of
    the radiator supports and chases. The crawler's swept box along the three tracks is 128 m³.
  - Not modelled: SP-52 (split architecture accepted, TH-SP52-2026-10-10, 15!A114: ~320 K equipment ring-local, ~450 K
    stationary; hosts surveyed as envelopes only in references/SERVICE_HOST_SURVEY.md, siting waits on 40_THERMAL / OD-022);
    crawler docks on the Crown rim; reach across the
    blade; the terminals' independent supply lines.
- **Storeroom (HUM-002, 12A SP-45):** the owner's compact walk-in general storeroom,
  5 × 2.5 × 2.4 m clear (30 m³, 33!C85:C88, WORKING with DIMENSIONS PROVISIONAL), as a
  PROTOTYPE `Storeroom_Shell` in `WF_SERVICE` (`storeroom.py`, `[storeroom]`). Its
  2.4 m height runs along +X, so with aft down its aft wall is the floor (X 97.65 m),
  0.65 m forward of the refuge; its 5 m side is tangential and its 2.5 m side radial,
  r 1.65–4.15 m clear, at 35° about the ship axis. `studies/storeroom_survey.py`
  screened every placement of that cuboid against the saved vehicle: the only ones a
  port off the trunk reaches without revising the route lie here, at 30–35° or 65–70°
  (`runs/20261009T140000Z-sp45`); the body aft of the ring bay has room but no access
  short of a hatch in the trunk floor and a bored spine. `Crew_Store_Port`, a new 0.90 m
  clear branch (the refuge port's size) at X 98.10 m, runs from the trunk to the room's
  inner wall with its sill on the floor; the trunk's ends, ladder and boundaries do not
  move, the 75° light strip skips it and two `Crew_Trunk_Store_Rail_*` stand beside it, as
  at the refuge port. The sill is 0.96 m below the thrust ladder's top, 1.18 m from the
  ladder across the trunk. The sealed hatch is a round leaf on the room side, hinged on
  an axis along X, folding flat against the inner wall beside the door
  (`STOREROOM_CTRL['hatch_open']`, saved closed), so room pressure holds it if the trunk
  loses pressure. Two full-height racks of the owner's 0.6 m depth line the 5 m walls
  (the inner row breaks for the door and the parked leaf) and leave the 1.3 m aisle;
  shelves at 0.10, 0.70, 1.30 and 1.90 m carry illustrative containers (no inventory),
  a retention net covers each rack face (0 g) and two tie-down rails run along the aisle
  floor. A panel above the door (fire and smoke detection, ventilation, pressure,
  hatch) and a ceiling light strip. Net after racks 18.9 m³ (racks 11.1 m³, against the
  owner's 12 m³ stowable and 18 m³ unobstructed). Least clearances: 0.18 m to survival
  pack 1, 0.28 m to the service dock, 0.63 m to sector keel 1, 0.35 m from the port to
  the service dock's branch. The figure `Human_Store_*` stands in the aisle with aft
  down (0.60 m headroom, 0.46 m to the shelf); `CAM_HUM_STORE_PORT` looks from the trunk
  through the port and `CAM_HUM_STORE_EYE` along the aisle to the door. `inspect`
  screens the shell against all geometry. Shell structure, seals, ventilation, fire
  detection and suppression, lighting power and mass are OPEN.
- Set `hull.enabled = false` to unlink the hull.

## Induction layers

IND-001 adds two PROTOTYPE layers over the engineering geometry for the induction route
(S&E `98!A36`, request Doc §13). Neither changes a pressure boundary, an interface or the
route clearance: the route sweep is unchanged.

- **Route.** The induction runs on ring A (`[induction]`, `human_entry.induction()`). Its
  eight stops follow S004A–C: the greeting in the entry chamber, the trunk under the refuge
  port, the transfer drum, then the sectors in the order 1 (HABITATION), 3 (Garden) and
  2 (WORK_MEDICAL_OPS: burn readiness, specialist stops at pressurized operations stations,
  and the burn station at the sector's aft couches, Q48). The route ends there: the
  newcomer's departure is Tale-owned (15!I89). Moving between sectors climbs one crew tube,
  crosses the drum's annulus and descends the next, 60–63 m and 148 rungs. Dock to the burn
  station is 179 m and 370 rungs. Each sector stop
  names the review figure it is about (`pose`) and stands on the aisle where the newcomer
  leaves for that station (`human_entry.induction_stations()`): the berths, the Garden
  rack, the treatment couch, the operations row's aft strip and the first burn couch. The
  route sweep covers the legs `A1-A3`, `A3-A2` and Seraph's service leg `A1-A2` and the aisle walk to every stop, at
  0.10 m. The ten `sector_whitebox` figures stand in ring A's induction sectors
  (`Human_Ind_*`), and `CAM_IND_<STOP>` views each stop from the aisle
  (`entry_preview.py --views stop_*`; eye-level review
  `references/HUM001_EYE_REVIEW_SECTORS.md`).

- **Architecture.** The fit-out of the entry chamber and trunk node uses the scheme
  "Layered (§13)" (`[route_fitout]`, `route_fitout.py`, `components/fitout.py`). Its 51
  elements live in `WF_SERVICE` with kind `route_fitout` and layer `ARCHITECTURE`, and each
  carries its grammar, function, HSFP design class and a signage flag. Colour carries
  meaning: greys for structure, blue for wayfinding, orange for safety, line colours only
  in the chase.
  - Spacer: 0.035 m ring frames and stringers carrying replaceable wall panels; a
    ventilation supply in the chamber and a return in the node; orange hatch-rim marks;
    a foot restraint on the deck.
  - Great Union: a blue orientation band on the aft quadrant (160–200°), which is the
    deck under thrust (Culture `42!A3`). Hatch and route signs sit on the bulkhead faces,
    fore up, in 5 cm letters. Each panel has a standard bezel with guarded equalize and
    release handles.
  - Bolt-Sworn: the service chase between the valves (202–215°) stays open, showing its
    air, condensate and power lines and service tags. The node holds the emergency
    locker (12A SP-21).
  - The trunk (built with `WF_CREW_TRANSFER`) has ring frames every 1.5 m, broken round
    the rails, lights and ladder, and a blue route stripe at 105° the length of the trunk
    with a placard at each branch and orange chevrons pointing to the storm refuge. A
    supply diffuser at the floor end sweeps air forward to the node's return.
  - The landing (in `WF_RING_SECTOR`, so in every sector) has the standard bezel and
    handles at its hatch panel, a route placard, an orange hatch-rim mark under the
    overhead and service tags on the chase; each interior adds its sector placard
    ("SECTOR 1 / HABITATION").
  - Each despun transfer drum (`route_fitout.drum_elements()`, parented to `Drum_j`, so
    it turns with the drum) has a placard beside each crew-tube opening, toward its
    handrail: "RING A  SECTOR 1 / HABITATION". The ring letter appears here only, since
    sector numbers are the same on both rings. A Bolt-Sworn service tag for the drum door's
    drive and seal sits below each placard. The aft end wall is a blue deck band, because
    it is the floor under thrust. Both end walls carry an orange moving-edge mark on their
    inner rims, where the drum turns past the stationary spine. The transfer panel has the
    standard bezel. Axial frames run every 10° on the outer wall wherever it is clear of
    the openings, rails, lights and panel, above the crawl rail.
  - Each crew tube (`route_fitout.tube_end_elements()`, on `Rotor_j`) has the standard
    hatch interface at its sector end: a bezel behind the tube-side hatch panel, guarded
    equalize and release handles below it, and a placard above it ("DOWN: SECTOR 1 /
    HABITATION"). At the top of the run a placard points back up ("UP: RING A DRUM /
    SPINE REFUGE DOCKS"). Placards read upright in spin, with up toward the axis. A blue
    deck band runs along the run's aft wall, which is the level floor under thrust (Q47).
    Together that is 73 elements on both rings (91 objects with the placard text); only
    the bezels touch their panels.
    Baseline `ind_transfer_fitout`.
  - Each furnished interior (so both rings) carries the sector fit-out, scheme A
    "Layered" (`route_fitout.sector_elements()`, built by `fitout.sector()`):
    - Spacer: overhead frames every 0.70 m carrying the overhead panels, broken round
      the hatch's rim mark and the aisle lights. A supply diffuser over side +1 and a
      return grille on the aft bulkhead above the aisle, so air crosses over the people.
    - Great Union: a blue route band on the overhead along the aisle's well side, with
      chevrons to the landing, and a placard on each room (HYGIENE, BERTHS 1-6, GARDEN,
      LIFE SUPPORT, MEDICAL, OPERATIONS, LAB, WORKSHOP).
    - Bolt-Sworn: the service block forward on side −1 shows its air, water and power
      lines with service tags. The hygiene compartment's and the life-support bay's open
      faces are recessed 0.06 m to hold them. At the workshop the lines run along the
      tool wall above the bench top, with a tool rail.
    - Below 2.2 m nothing enters the swept aisle or the landing well and nothing reaches
      more than 0.04 m into a floor strip (`route_fitout.sector_check()`, also asserted by
      `inspect`). Placards on aisle faces sit flush. The route sweep is unchanged except
      the habitat stop, now 0.103 m to Bunk_1 (the hygiene face was the 0.10 m limit).
  - Seraph's spaces (12A SP-31, Q51 ACCEPTED: a counted crew person and refuge occupant
    with no human berth, 15!A106, 12!A29). The work post: the first operations station's
    chair gives way to a standing dock (two posts, a spine rail, a docking ring at shoulder
    height and a charging and data rail), Seraph working at the console. The private niche
    by the berths (Rian's domestic area): the couch-2 lockers end at x −1.15 m, as couch 1's
    do, and the 0.55 × 1.26 m slot between them and the landing well, 2.10 m high, holds the
    same dock behind a partition on the well side, a lid, a self-maintenance shelf, a privacy
    panel half drawn across its mouth and a SERAPH placard (1.46 m³ of locker space given
    up; every berth and couch stays). Large repairs go to the workshop by the crew route
    from the habitation to the work sector (`A1-A2`, 58 m, swept with the suited body); it
    ends at the work landing beside the workbench strip. Both spaces are in both rings'
    sectors. The rig's `interior_states` (contract 24) carries the post, the niche, the
    service path and the Garden expansion state. Footprint, posture, charging and service
    stay OPEN (12A I34); the objects carry `sp = SP-31` and that status.
- **Look (FUT-003 step 1, ART-S004-2026-10-10).** The S004 look (`[look]`, `look.py`, local brief
  `docs/SURFACE_BRIEF.md`) is a presentation layer that the induction stills (`entry_preview.py --look`)
  and the runtime export apply in memory over the generated materials. The saved assets keep their
  review colours. It follows the owner's three classes (15!I120):
  - **Physics-locked:** the pressure shells, tubes, drums and the refuge and storeroom walls are
    REP_PROXY grey. The hatches, closures and seal guards are a darker grey. None gets a hero
    finish (15!H120).
  - **Engineering-flexible:** the fit-out keeps its palette's meaning, with matte finishes. The
    handrails and ladders are satin metal, the polish of the touch points. The furniture changes
    from its function-coded review colours to quiet greys and off-whites: charcoal couches, warm-grey
    berths, off-white hygiene and medical. The harness straps are safety orange.
  - **Light (artistic freedom):** the route's 95 light strips emit a cool 6500 K cabin light.
    Each berth has a warm 2900 K reading light, recessed in its lid 0.25 m from the head end
    (`sector_whitebox.shapes`, `berth_light_m`), the only warm light: where people live.
    The lights' look pass (2026-10-29) adds four classes: the Garden/mess pack's 5000 K daylight panels over the table and
    4200 K grow-light bars (spectrum and light level OPEN), the exterior position strobes as 6500 K beacons and the docking
    alignment lights and airlock floods as 1900 K amber approach lights. The walk hangs a light at each of them like the strips.

  Cycles lights the stills from these emitters alone. The export records each emitter's light class
  and emitter centre (`light` on its node record, `look` in the manifest), and the boarding walk
  hangs its lights there. Nothing here is a lighting design, power or heat allocation. The
  MPFB pair wears the S004 outfits (docs/CHARACTERS.md "Outfits": material zones, no geometry). The
  Blender stills still show the IND-001 proxies. Evidence: `runs/20261010T121700Z-s004-look`
  (Blender stills; Godot stop views with the look and the inspection light) and
  `runs/20261010T130000Z-s004-outfit`.
- **First Ignition exterior (FUT-003 step 2, 15!C120 item 2).** `presentation/hero_preview.py` poses
  the vehicle at FIRST_IGNITION and dresses it in memory (`[look.exterior]`, `look.exterior`):
  - **Surfaces:** the exterior is physics-locked (shield, radiators, drive, shells and their
    structure), so every surface is one proxy grey, with no hero finish (15!H120). The field
    display, envelopes, scale figures and the radiator glow overlays are hidden.
  - **Sun:** one hard sun, 1 AU-class. The burn points outward (22!A21), so it stays in the aft
    hemisphere; it sits 87° from aft, and its angle, distance and the global pointing are OPEN.
  - **Hot face:** the radiator cells emit as a grey body at the WORKING 1800 K and emissivity 0.9,
    uniform because the temperature map is OPEN. That is about 104,000 cd/m², 4.0× the luminance of
    a sunlit grey hull and deep orange. The 0.125 m seams and the root band stay dark, and the
    blades light the hull. The exposure is set for the hot face.
  - **Exhaust:** the plume is not drawn (`physics.plume_boundary` and its luminosity are OPEN), and
    the plasma inside the nozzles keeps its display colour without lighting anything.

  The views follow the Art Style spacecraft shot (Spacecraft A14): the establishing three-quarter,
  the Brow, the drive and a blade, plus flat side and three-quarter silhouettes (A16). The Brow's
  forward face lies in its own shadow during the outward burn, so it reads as a dark disc with a
  sunlit rim and Lance against the glowing blades; the EYE wells read only under a sunward attitude,
  which is OPEN. In the three-quarter silhouette the three blades merge into one cylinder; the
  side silhouette shows the slab, the rings and the Brow. Evidence:
  `runs/20261010T143000Z-hero-first-ignition`.

  The Godot flight timeline shows the same look on X (`look.runtime_exterior`, manifest
  `look.exterior`): the sun, the grey and the exposure match the stills. The hot face emits only while
  the timeline's radiator thermal state is FIRST_IGNITION's step, HIGH_POWER_REJECTION (frames
  481–1547, the burn), because the other steps' temperatures are OPEN. The Compatibility renderer has
  no bounce light, so the blades don't light the hull as they do in the stills. Evidence:
  `runs/20261010T200000Z-flight-exterior` (every state and timeline mark).
- **M4 visual identity (WF-006, SIM-035, LOOK-005 next pass).** `presentation/m4_look.py` renders two
  controlled comparisons and one inhabited-space proof in memory. In each pair the illustrative fill is
  the only variable, and the fill still is captioned NOT PHYSICAL.
  - **Crew end, First Ignition:** the working camera's azimuth (120°), 80° off the aft axis, because at
    50° the blades stand in front of the rings. The frame holds both rings' rims. One non-diegetic scale
    figure, the MPFB instructor at 1.78 m, stands on ring A's outer frame (radius 30.0 m by ray cast; the
    shell is at 28.7 m). It is captioned as nobody being outside during the burn. The rings take most of
    their light from the hot blades, so they read orange-grey against the dark shield back.
  - **Ring A habitation aisle, COAST:** the MPFB pair in their S004 outfits stands on the aisle deck in
    the sector frame. The instructor stands by the berths, turned back to the newcomer. The physical still is
    lit only by the S004 emitters.
  - **Proof:** the newcomer's eye view of the instructor. The fit is measured from the evaluated
    meshes in the sector frame: both pairs of feet on the deck within 1 mm; the instructor is 1.78 m tall
    and 0.12 m from the hygiene block, the newcomer 1.70 m tall and 0.14 m from Bunk_1.

  The staging and the framing are PROTOTYPE. It changes no geometry, look value or canon. Evidence:
  `runs/20261012T160000Z-m4` (five stills, `m4_look.json`).
  - **Constructed exterior under the physical light (2026-10-14):** `presentation/hero_look3.py` adds a
    functional-mark variant of the working three-quarter view (`tq_functional`: only
    `look.exterior.functional_materials` keep their colour, the rest proxy grey) and three assembly views
    with a non-diegetic 1.8 m figure (`asm_shield_rear`, `asm_ring`, `asm_roots`). The 1800 K hot faces
    give about 326,000 lm/m², about 2.5 times the sunlight, so the blades read first and light the
    aft-facing structure; the marks are assembly-scale cues. Evidence: `runs/20261014T1600Z-look005`,
    [LOOK005_PASS2_2026-10-14.md](../references/LOOK005_PASS2_2026-10-14.md).
  - **S02/S04 parts in the same grammar (S03 slice 1):** the casing access panels are ochre service covers, the
    casing straps and RCS nozzles are dark joints, and the dishes and the passive docking target are off-white.
    All five materials are functional marks; the pods, booms and sensors stay proxy grey. No owner row gives
    any other spacecraft colour, finish, marking or registry lettering (Drive read 2026-10-18).
- **Characters.** The figures and their cameras live in their own asset,
  `assets/characters/WF_CHAR_INDUCTION.blend`, which is never linked into the vehicle
  (`[characters]`, `characters.py`, `components/figures.py`).
  - The instructor is 1.78 m, in a Spacer suit under a fitted Great Union field vest
    with shoulder boards and a high collar.
  - The newcomer is 1.70 m, in an issued suit with a visitor band and a kit pack.
  - Both carry a seal collar, a safety-orange harness with an arrester ring, and an
    emergency mask.
  - S004A staging: in microgravity the instructor stands anchored on the deck band,
    head fore, and offers a hand to the newcomer, who comes head-first through the outer
    hatch.
  - `CAM_IND_GREETING` (profile) and `CAM_IND_GREETING_POV` (the newcomer's view) frame
    the scene. `entry_preview.py --views greeting greeting_pov` appends the asset in
    memory.
  - S004B staging: the newcomer lies on the treatment couch in ring A's work sector
    (`characters.couch()`), named `S004B_Newcomer_*`.
  - Only these two get figures (user direction 2026-10-08): the six crew of the tale have
    no figures; their stations stay as furniture.
  - The roles are fixed (Q49, 15!A104); identities, faces, bodies and outfits stay open (Tale WTF-16): the male instructor mesh is a
    PROTOTYPE rig, not casting.
- **Sequence and stills.** The induction runs through operating states
  (`[induction].sequence`, `human_entry.induction_sequence()`), the owner's Q48 answer
  (15!A89, 98!A66, BASELINE physical sequence; `[induction.doctrine]`):
  - Board DOCKED: arrival and spine with both rings stopped and locked at their index
    angles (14!A8).
  - The visiting craft may undock; the rings unlock and spin up to COAST.
  - The COAST tour: the despun transfer drum takes the newcomer from the stationary spine
    port and synchronizes with ring A (0.03 g at mid-depth), then the five sector stops at
    4 rpm and 0.50 g on the deck. Every move between sectors stays in COAST; no ring stops
    (15!H89). `induction_sequence()` checks this: the first step docked with the rings
    stopped, every ring stop held by one spinning state.
  Transitions carry no duration (not to scale); FUT-004's timeline takes the sequence as its
  pre-ignition segment, so First Ignition starts from COAST.

  `entry_preview.py --views ind_<stop>` renders one eye-level still per stop with the
  characters of its scenes and no review figures, labelled with the stop, its scenes,
  operating state and sources; the ring stops are drawn at the index angle. At the garden,
  burn-readiness and specialist stops the stop camera stands too close to the station, so
  the still takes a wider view (`characters.STAGE_VIEWS`). The stills and the shot
  `SH_INDUCTION` open ring A's transfer closures in memory; the shot cuts through the same
  views with captions from the sequence.
- **Route graph and runtime.** `human_entry.induction_graph()` writes the route into the
  rig as `induction_route` (since contract 18), with semantic IDs:
  - one camera rail of 171 waypoints over 186 m, each with its zone (entry, trunk,
    vestibule, tube, landing, aisle), leg and distance;
  - the eight stops (`WF.STOP.IND.*`), each with its rail distance, operating state and
    step, scenes and eye-level view (`characters.stop_views()`, from each stop's `view`);
  - the sequence steps (`WF.STEP.IND.*`);
  - three legs (`WF.LEG.IND.*`), each with its ladders (`WF.LADDER.A<k>.TUBE`, 65 rungs,
    and `.LANDING`, 9 rungs) and the openings it passes (`WF.OPENING.*`: the entry
    hatches, the spine port (its Q46 gate), the drum doors with the tube hatches and the
    sector hatches), each with its closure status. An opening's point is the rail waypoint at the zone boundary, not a hatch
    centre.

  The DOCKED runtime package appends the characters as static proxies, tagged with their
  scene; the Godot walk is described under Runtime representation.
- The unpicked variants live in `studies/induction_entry.py` (fit-out A–C),
  `studies/induction_characters.py` (instructors I2, I3)
  and `studies/induction_sector_fitout.py` (sector scheme B's exposed utility spine, Seraph's
  berth Sb).

## Production layer (M7)

M7 adds a generated L4 visual layer to one contiguous path: the primary port, the entry chamber and trunk node, the stationary
trunk, ring A's spin transfer, ring A's crew tube and ring A sector 1 (`[production]`, the detail packs `m7_spine`,
`ring_a_transfer` and `m7_ra1`, `production_detail.py`, `components/production.py`). Its source is the L4 definition in S&E 48!A23 (WF-022). It sits over the unchanged engineering
geometry and carries no load. It changes no pressure boundary, interface, volume or clearance.

- **Assemblies (stable IDs):** `M7.EXT.PORT`, `M7.ENT`, `M7.TRK`, `M7.XFR`, `M7.SPK` and `M7.RA1`, each a detail pack assembly in its
  own linked asset (see Modular detail). Each assembly family becomes one joined object, `Prod_<assembly>_<family>`, of
  `kind = production_detail` and `layer = PRODUCTION`, with `representation = REP_HERO`, its `m7_assembly`, its
  `surface_class` and `maturity = L4_VISUAL_ACCEPTED`. The owner accepted the six assemblies on 2026-10-20, after the M7.1 correction
  pass. The acceptance is visual and asset-level for this section only, not engineering GO. They are the production standard for later
  sections, whose new elements start as `L4_VISUAL_CANDIDATE` until reviewed. Physics-locked parts keep their PROTOTYPE labels and
  proxy grey (15!H120).
- **Scope:** only the engineering-flexible and artistic surface classes are detailed. `M7.RA1` is placed on ring A sector 1
  alone, parented to that sector's instance. The shared sector and interior components carry no production layer, so ring B
  and the other sectors stay as reviewed.
- **Switch:** `[production].enabled = false` rebuilds the assets without the layer, and the geometry diff against the baseline
  is empty. This was verified 2026-10-19 in run `runs/20261019T110757Z-quick` (0 changed, added or removed; rig changed only
  in its input hashes).
- **Built:**
  - `M7.EXT.PORT`: two flush ochre service covers beside the primary port (external hatch release and the docking umbilical), each
    with fasteners and a stencil, plus the D1 identification. They sit off the hull opening, inside the strap-free window round the
    approach aids and clear of them.
  - `M7.ENT`: replaceable wall-panel modules on dark carrier trays with quarter-turn fasteners in every free bay of the chamber and
    node walls, radial panels on the bulkhead faces, and housings round the light strips. All of it stays outside the valves' 1.08 m
    floor and off every fixture window. Stills: `presentation/m7_section.py`, before and after from one build.
  - `M7.TRK`: the same cladding component (`clad_bay`) in every free patch of every trunk bay between the route frames, off the branch
    openings (with `opening_margin_m`), handrails, lights, ladder, route stripe, placards and chevrons, plus housings round the
    light strips.
  - `M7.XFR`: ring A's drum lining, darker machinery panels on the outer wall above the crawl rail, beyond each tube opening's frame
    by `opening_margin_m` and off the rails, lights, transfer panel and placards. On the despun drum (anchor `WF-RING-A.DRUM.1`,
    `Drum_1`). The closures, door seal lands and guard rings stay physics-locked grey.
  - `M7.SPK`: ring A's sector-1 crew tube, radial run. Ring frames every 1.5 m and cladding between them, off the ladder, arrest rail,
    lights, hatch panel and fit-out. On ring A's rotor (anchor `WF-RING-A.ROTOR.1`, `Rotor_1`). The collar, elbows and sector hatch
    are unchanged.
  - `M7.RA1`: ring A sector 1's overhead. Removable service panels on trays in the bays of the route fit-out's overhead frame grid, off
    every item that reaches the overhead, the hatch opening and the landing well's column. Housings round the aisle lights. Nothing
    comes below -2.85 m. On sector instance `(1, 1)` (anchor `WF-RING-A.SECTOR.1.1`).
- **Runtime:** the production nodes (manifest v2: `layer`, `representation`, `assembly`, `maturity`, `surface_class`) are drawn
  within 28 m of the camera and fade out beyond (`godot/scripts/production_layer.gd`, in the walk). Measured cost: `references/M7_PERF_2026-10-19.md`.
- **Hologram styles (WEB-003):** the web viewer redraws the same meshes as the M5 subsystem hologram (overlay
  colour per subsystem, additive rim and scan) or the engine exposition hologram (one colour, rim glow), from `wf_holo.json`
  (`representation.py holo-style`: `shots/m5_subsystems.toml` and the SH_ENGINE_HOLOGRAM colour). Instance overrides only.
- **Value hierarchy (M7.1, owner 2026-10-20):** `[production.materials]` steps from inhabited panels (warm off-white, ~0.69 linear)
  through service panels (~0.45), machinery (~0.26) and structure and housings (~0.15) to trays and seams (0.05). Fasteners are dulled.
  No texture maps.
- **Interior light (M7.1):** in Godot the emitter lamps run at 0.65 of their manifest energy (`lamp_scale`, `-- --lamp-energy=<f>`),
  so the interiors stop washing out; the light count, range and draw calls are unchanged. Lamp shadows were measured and rejected:
  +1.6–2.0 ms, with blow-outs and hard wedges in the Compatibility renderer. The stills use AgX medium-high contrast at -0.4 EV,
  labelled. Emission is unchanged.
- **Evidence (2026-10-19):** all 49 route-sweep zones keep their pre-M7 least margins (`runs/20261019T120301Z-pipeline`).
- **Ring A safety:** ring A remains a FAIL comparator for casualty transfer (15!A221). The production layer depicts the
  healthy-crew training route and claims no rescue or pressure qualification.

## Modular detail

Production detail is organised in subsystem modules (`data/modules.toml`) and detail packs (`data/detail/*.toml`), each assembly in its
own linked asset (`assets/wayfarer/detail/WF_DETAIL_<assembly>.blend`) at a declared anchor, with its pack's own contract and publication
record (`references/modules/<pack>.json`); docs/MODULES.md. Every production assembly is a pack; the hosts build none themselves.
- Habitat engineering: each ring is its own asset, `WF_HABITAT_A` (WF-RING-A) and `WF_HABITAT_B` (WF-RING-B), with its rotor, control,
  hub, drum, crew tubes, frame, spokes and sectors. `WF_HABITAT` is the assembly that links both at the ship origin and holds the
  whole-habitat rotor actions. The split (2026-10-23) changed no geometry: every object moved verbatim (fingerprint split proof),
  evaluated geometry at every pose and the runtime manifest, node IDs included, are identical, and the stills are pixel-identical.
- `m7_spine` (M7.EXT.PORT and M7.ENT on the SERVICE origin, M7.TRK on the CREW_TRANSFER origin), `ring_a_transfer` (M7.XFR on the
  despun drum `Drum_1`, M7.SPK on `Rotor_1`) and `m7_ra1` (M7.RA1 on sector `(1, 1)`): the M7 section, `L4_VISUAL_ACCEPTED`, scope M7.
  Migrated without change (2026-10-22 and 2026-10-23): identical generated elements, a fingerprint relocation proof, identical evaluated
  geometry with the rings turned, the drum synchronized, HIGH_POWER and DOCKED with every closure open, an identical runtime manifest
  (frames included; the XFR/SPK node IDs changed with the lineage) and pixel-identical stills.
- `m8_forward` (M8.BROW.AFT, M8.CROWN.RIM on the FORWARD_SHIELD origin): M8.1, `L4_VISUAL_CANDIDATE`, scope M8, static with the Crown
  in every state; migrated with the same proofs and an unchanged `m8_readback`.
- `rad_frame` (RAD.FRAME, WF-THERMAL, L4_VISUAL_CANDIDATE): band clamps on the blade's 11 transverse frames (both truss faces, five
  across), gusset plates at the truss nodes on both edges and an aft edge guard, 155 elements in one detail asset linked once into the
  blade component, so all three blades share it. Every footprint lies inside a 0.125 m non-emitting bay joint or beyond the blade's ends:
  the cells, their planform (radiator area) and the health overlays are unchanged. Revised in Phase 4 S5 (owner: REVISE): the fittings
  stay the close-up tier in the shared families (clamps graphite, gussets and edge guard structure); the ship-scale frame rhythm is
  carried by value: the blade frames and edge chords have their own display material `BladeFrame` (same review colour as `Structure`)
  and, with the joint beads (`ExpansionJoint`), take the light `xf_frame` family over the dark COAST sheet in the grammar look.
- `ra2_equip` (RA2.EQP, WF-RING-A, L4_VISUAL_CANDIDATE): a transverse cable tray down the centre of each of the four fit-out frame bays of
  ring A sector 2 (WORK_MEDICAL_OPS), broken round every item within 2 cm of the overhead, the hatch opening and the landing well, with
  a junction box at each run's ends (45 elements), all in the overhead band (-2.90 to -2.85 m), on sector instance (1, 2) only.
- `ra3_garden` (RA3.GDN, WF-RING-A, L4_VISUAL_CANDIDATE): the first cultural pass (S8b Z1) of ring A sector 3
  (LIFE_SUPPORT_GARDEN_COMMON), 57 elements on sector instance (1, 3) only. Mess: seat and back cushions on both benches and a fiddle
  rail round the table (a spill lip for Coriolis and burn transients); on the outer wall above the far bench a mug rail with one colour
  per booth place and a six-cubby personal shelf with matching tabs; two daylight panels over the table in the overhead frame bays,
  clear of the supply diffuser. Garden rack: two grow-light bars under the lid and under each tray. ECLSS bay, in its 0.06 m service
  recess: a GU-standard LIFE SUPPORT resource board with WATER, O2 and CO2 gauges (illustrative levels; the hook for the UJ-004
  learning station), an ochre access panel with quarter-turn fasteners and an orange maintenance tag. Its screen keeps every part off
  the aisle, the access strips, the through-passage and the landing well (unless in the overhead band), off the leaning outer wall and
  out of every whitebox part and fit-out item; no clearance, interface, light level or growing area changes.
- `ra2_work` (RA2.WRK, L4_VISUAL_CANDIDATE, S8b Z2) on sector instance (1, 2), below the `ra2_equip` trays: an ops screen with a
  bezel and an "OPS k" number per chair on the display wall and a keyboard on the desk (one exported node per station, `Ops_1–3`);
  chest and thigh restraint straps over the medical mattress; a drawer-line front, the red cross and a MEDICAL label on the medical
  stowage; on both tool walls a shadow board of outlined tools with each tool on a tether, and a maintenance tag (`Tools_<bench>`).
- `rb_fitout` (RB1.BRT, RB2.WRK, RB3.GDN, L4_VISUAL_CANDIDATE): ring B's three sectors take ring A's berth, work/medical/ops and
  Garden/mess passes by one definition (ring A's builders and checks, names RB*, berth numbers B1-k); every crew member keeps a berth,
  mug and cubby in each ring in the same colour, so a lost ring costs no one their place.
- `ra1_berths` (RA1.BRT, L4_VISUAL_CANDIDATE, S8b Z3) on sector instance (1, 1): per berth a mattress, a sleep-restraint strap, a
  pillow, a curtain on a rail across the berth mouth drawn back, a stencilled "A1-k" number, a name tab and a photo card; pillows,
  curtains and tabs in the six crew colours shared with the `ra3_garden` mugs and cubbies; the hygiene cubicle's door skin, pull and
  label. Soft goods stay within 0.14 m of their berth's walls and platform; every pack keeps the aisle, strips, passage and well clear.
Both candidates were built in parallel on separate branches that touched only their own packs, then merged without conflict.
Approved hand-authored meshes can be committed as glTF data under their pack (`data/detail/<pack>/*.glb`) and are then rebuilt from a
clean checkout; none is committed yet.

## Exterior production layer (M8.2)

M8 applies the accepted M7 production system to the exterior, starting with the Brow's aft face and the Aegis Crown rim
(`[production.m8]`, same pure module and generator as M7, user brief 2026-10-20). Owner evidence and its limits are in source
`m8_exterior_identity`. M8.2 (Phase 4 S3, 2026-10-24) is the owner-requested revision of M8.1 in the selected exterior grammar
(`[production.exterior]`), keeping its bay/module construction. Every M8 object is `L4_VISUAL_CANDIDATE` until the owner's art review; nothing is engineering GO, and the shield's
thickness, protection performance and structural mass stay unqualified (S&E 36, Eye 40).

- **Switch:** `[production.m8].enabled` is independent of `[production].enabled`. Off rebuilds the assets with an empty geometry diff
  against the accepted M7 baseline (verified 2026-10-20, `runs/20261020T1300Z-m8-off-quick`: 0 changed, added or removed).
- **Assemblies:** `M8.BROW.AFT` and `M8.CROWN.RIM`, the detail pack `m8_forward`, linked into `WF_FORWARD_SHIELD` at its origin. Objects `Prod_BROW_AFT_<family>` and
  `Prod_CROWN_RIM_<family>` (panels, frames, closeouts, caps, boundary, fasteners, markings, lane_lines, trays): one joined mesh per
  family, 12 objects,
  `kind = production_detail`, `design_class = ARTISTIC` (the layer over the shield), `production_scope = M8`, their own maturity and a
  Godot draw range (`detail_range_m`: 1500 m for panels and frames, 160 m for fasteners and lettering).
- **Brow aft face:** panel modules on the skin's aft face between the existing joints (`brow_panel_joints`), 30 mm aft of it, inside the
  truss envelope and off the forward chords by member radius plus the shared clearance. Each Crown bay's 30 deg of Brow is one module:
  a 10 deg service lane on the bay azimuth (the crawler side, 50!AG-A02) between two structural columns of light shell cladding, and a
  graphite protected-equipment band over the hub, EYE mounts and Lance root inside r 11.2 m with a dark closeout groove at its edge.
  The lane is a mid-value deck with a GU deep-blue boundary line along each edge (functional wayfinding) and an exposed graphite utility
  tray (0.30 × 0.14 m, power and data to the Crown bay, routing PROTOTYPE) on brackets inside each line, broken at the ring-chord
  keep-outs. Ochre inspection caps at the forward-chord nodes; quarter-turn fasteners only on the lane deck (the cladding fields stay
  calm); stencils `S01..S12` (1.06 m, off-white on the graphite band) and `Cnn SERVICE LANE` (0.48 m, off-white on the deck).
  The panels depict the existing aft-face panelization; they add no plate, mass or access commitment.
- **Crown rim:** a sector module per bay on the housing's aft plate and the rim girder. A graphite doubler frame round the existing ochre
  carriage-service hatch, three replaceable access panels on each side in light shell value against the graphite housing, off the
  partition ribs, with fasteners; thermal-break closeouts at the plate's joints with the inner wall and the rim girder; and markings: a
  charcoal boundary half-stripe (0.24 m) at each partition (two modules make one stripe, split round the rim beacons), the sector number
  `Cnn` (1.38 m) wrapped on the rim girder and the hatch stencil (off-white, 0.28 m: the service-stencil height capped by the band above
  the doubler). Bay 1 was built and
  gated first; then all twelve. The shutters, port covers, carriages, emitters, launchers and their travel, the windows and the Crown
  ports are unchanged; repeating the module qualifies no sector mechanism.
- **Silhouette and clearances:** M8 reaches r 45.0043 m (marking film on the rim girder; the engineering rim is 45.0002 m), so the 90 m
  silhouette is unchanged. Nothing lies on the sunward side of the skin's aft face (closest 30 mm aft). The BVH readback finds no overlap
  with any of the 440 forward engineering meshes (`validation/m8_readback.py`). The EYE wells, ports and shutters, the Dust Lance, the
  disruptor layer and the Crown housing volume are untouched.
- **Exterior materials:** the shared families `[production.exterior.families]`: shell cladding and access panels, structure lane deck and
  tray brackets, graphite protected band, doubler and trays, ochre caps, blue lane lines, dark closeouts, charcoal and off-white marks.
  No livery and no registry; GU WAYFARER 001 stays a provisional casing and dock stencil (15!A216, A225), not used here.
- **Stills:** `presentation/m8_exterior.py` renders each view with the layer off and on under the same camera, one 1 AU-class sun
  from the aft hemisphere (direction a labelled presentation choice) and the COAST editorial +2 EV of 15!A222, plus an x-ray cutaway
  (engineering clay, M8 amber).

## Habitat ring exteriors (Phase 4 S4)

The detail packs `ring_a_exterior` (WF-RING-A) and `ring_b_exterior` (WF-RING-B) put the selected exterior grammar on both rings so they
read as assembled, maintained, inhabited pressure structures by value and rhythm, never by size or position. One shared pure module,
`ring_exterior.py` (WF-HABITAT), builds the 15° segment module in the rotor frame (anchors `WF-RING-A.ROTOR.1`, `WF-RING-B.ROTOR.2`), so
the detail turns with its ring; each ring has a forward (+u) and an aft (−u) flank assembly (`R<A|B>.EXT.FWD`, `.AFT`), each claiming
only the slab between the frame flank and the 2.15 m sweep. All `L4_VISUAL_CANDIDATE`, PROTOTYPE: no load, shielding, mass, balance,
pressure boundary or mechanism.

- **Segment module (24 per ring, both flanks):** light shell cassettes 20–60 mm off the flank between the joints; a mid-value joint cap
  either side of every 15° joint over a dark 80 mm joint gap (the frame rhythm); at each structural spoke a graphite node housing with
  an ochre service cover; over each pressurized segment a calm shell panel on the pressure face in its 0.25 m recess (10 mm off the
  sector skin), a muted amber occupancy band, the text-only sector ID (`A1..A3`, `B1..B3`, 1.06 m) and a GU deep-blue identifier bar.
  246 elements per ring; accents blue 0.06 %, amber 1.3 %, ochre 0.6 % of the detail area.
- **Screens** (`ring_exterior.check`): every vertex inside r 24.5–30.0 m and |u| ≤ 2.15 m, outside the frame body except the recess
  panels, and no part in a sector pressure envelope; the envelope screen keeps each flank assembly off ring A's crew-tube pack. The
  M4 construction inside the frame (joints, webs, cassettes, covers, nodes, rim band), the spokes, crew tubes and hub are unchanged.

## Continuous ring circulation (CIRC-001)

The owner's design direction of 2026-10-26 (no owner row yet) makes continuous circulation a requirement: every crew member can walk the
whole circumference of either ring and back. `ring_circulation.py` (`[ring_circulation]`, all PROTOTYPE) joins each ring's three
pressurized sectors into one walking circuit while every sector stays an independently closable compartment. Plan:
`references/RING_CIRCULATION_PLAN.svg`; fit screen `python3 src/wayfarer/ring_circulation.py` (`references/p1_ring_circulation.json`);
renders `presentation/circulation_preview.py` (whole ring with the fill cut away, eye level in a corridor and in the through-passages).

- **Through-passage.** Every sector has a tangential passage at x −1.15..−0.50 m (sector frame), between the aft couch row and the
  berths, stations, Garden rack and landing well, from side wall to side wall across the aisle. It is the only band free in all three
  functions; the work and Garden couch-2 lockers now end at x −1.15 m like the habitation ones and the Garden rack and mess start at
  −0.50 m (0.05 m shorter). Seraph's habitation niche (Q51 slot) lay in that band: it moves to a reserved alcove (0.80 × 0.55 m) on the
  corridor side of that sector's −z door, still beside the berths but outside the sector boundary, and is not built (owner to confirm).
- **Doors.** A sliding pressure door in each sector side wall (0.65 × 1.95 m clear, the width beside the landing well; it passes the
  0.44 m body with 0.10 m each side, not a stretcher or the 0.70 m suited envelope) and one in a pressure bulkhead at each structural
  spoke node, half way along each fill. Leaves slide aft into pockets in the flank frame and the bulkhead, seat on their frames and are
  normally closed. Per ring 9 doors and 9 compartments (3 sectors, 6 corridor halves of 56 m³).
- **Corridors.** One per fill, from the side wall of one sector to the next (about 53 m each, 159 m per ring), 0.90 m clear (the sector
  aisle) × 2.10 m (interior.min_headroom_m), centred on the door band, so aft of the ring plane. The floor is the cylinder through the
  sector deck plate's edge (r 28.152 m): the threshold is flush and the corridor is level in spin gravity (0.504 g). Inside the liner
  0.15 m of utilities over the ceiling and under the deck; the tunnel cut in the fill keeps 0.10 m round the liner. The fill's
  construction (`habitat_ring.frame_mesh`) is split round the tunnel: the web frames become portals and the spoke-node housing splits
  round it. Light strips every 3 m (the route's cabin light class) and a handrail on the forward wall. Shirt-sleeve only: suited crew
  keep the crew tubes.
- **Interior language.** The corridors take the sectors' scheme A grammar (`ring_circulation.fitout`, depiction only): the sector deck
  and overhead finishes, flush dark frame strips across walls and ceiling at the sectors' 0.70 m overhead-frame pitch, the blue route
  band along the floor by the forward wall and safety-orange trim round both faces of every door opening. In the runtime each door
  carries a sign on both faces, "here > beyond" by compartment (A1, AC1a, ...). The cultural pass (31_ARCHITECTURE) waits for the
  whitebox review.
- **Consequences (budget(), PROTOTYPE estimates).** Pressurized volume +338 m³ per ring: both rings 434 → 1,111 m³ gross, 2.4 × the
  BASELINE 400–460 m³ maximum; atmosphere +641 kg at 80 kPa and 295 K. Mass about 40 t for both rings (liner 15 kg/m², deck, 18
  doors, fit-out), 12 % of the 330 t rotating allowance and not budgeted; at the sectors' areal mass it would be 301 t. Spoke axial load
  and spin energy grow with it (+49 kN per spoke at 1.5 g). The tunnel takes 507 m³ of each ring's 2,249 m³ fill, leaving room for the
  80 m³ of rotating water per ring. Aft down (rings stopped) a corridor is a 0.9 m high tunnel, so it is not one of Q47's essential
  1.5 g routes: those stay the crew tubes and the spine.
- **Conflicts (conflicts()):** 12!A13 (BASELINE: pressurized rooms only in sectors), the 400–460 m³ gross envelope (BASELINE), the
  330 t rotating allowance (PROVISIONAL), Seraph's niche slot (Q51 ACCEPTED, dimensions OPEN), the frame load path (OD-016 OPEN), the
  re-blocked lockers and Garden rack (PROTOTYPE, Q50 tray area). The docked rule (14!A8) means a ring walk from the station needs
  undocking first. Nothing here is canon.
- **Benefits weighed.** Each sector gains two level exits besides its crew tube (egress and fire isolation by door), the crew can move
  between sectors of a ring without two crew-tube ladder climbs (about 20 m each), and the fill cassettes become reachable in shirt sleeves. Against them:
  the volume, gas, mass and leak paths above, through-traffic in the habitation sector's sub-aisle (between the other two sectors the
  shorter way avoids it; a full circuit cannot) and less water beside the crew in a corridor than in a sector.

## Ring B route in the M7 grammar (Phase 4 S8a)

The detail pack `ring_b_transfer` (WF-RING-B) gives ring B's route the accepted M7 standard (owner P4-INT zone Z4: ring B transfer and
first sector): `RB.XFR` lines ring B's despun transfer drum (`WF-RING-B.DRUM.2`), `RB.SPK` clads the radial run of the crew tube to
sector 2, the sector of ring B's spine port (`WF-RING-B.ROTOR.2`), and `RB.SEC` is sector 2's overhead service layer
(`WF-RING-B.SECTOR.2.2`, WORK_MEDICAL_OPS: its fit-out sets the keep-outs). One definition serves both rings: the shared pure module
`m7_route.py` (WF-HABITAT) holds the drum, tube and sector layers parameterised by ring, sector and function, moved unchanged from ring A's
packs, whose output is identical (fingerprint: no object changed). Drum 66 elements (the 0.90 m openings leave more lining than ring A's
1.6 m), tube 841, overhead 88; every M7 screen passes. `L4_VISUAL_CANDIDATE`: the M7 acceptance does not extend to these assets. Ring
B's closures and rescue path stay HOLD (15!A197, OD-032/034/040) and physics-locked proxies; the 0.90 m port, necks and bulkheads are
unchanged.

## Spine casing (Phase 4 S6)

The detail pack `spine_casing` (WF-SPINE, assembly `SP.CASING` on `WF-SPINE.HULL.ORIGIN`, vehicle frame) makes the aft body casing
read as a serviced keel in the selected grammar. `L4_VISUAL_CANDIDATE`, PROTOTYPE: no load, mass, shielding, pressure boundary,
opening, interface or mechanism.

- **Casing modules:** five modules (K1–K5, aft to forward, about 36 m each) between the casing ends and the four primary-cage frames
  the radiator bay stays bear on (bays 2, 4, 6, 8), so the blade frame rhythm continues round the body. Each boundary carries a 0.60 m
  mid-value frame band, broken across the keel lanes like the hoop straps. In the grammar the raised casing straps take the light-mid
  frame value (`xf_frame`), so the panel fields stay calm and the module bands lead.
- **Followable route:** each blade's SP-51 crawler track (graphite rails and stops in the grammar) runs on a 0.70 m mid-value rail bed
  from the thrust ring to the blade front; each of its seven stops has a GU deep-blue approach marker either side of the bed and a
  text ID (`C<track>-<stop>`, 0.48 m). The DS-13 track (operations HOLD) and its docks are unchanged and undressed.
- **Module numbers:** `K1`–`K5` (1.38 m) at each module's aft end on the three bisectors between the blades; the ship name runs
  along K3 (S9, next section).
- **Screens** (`pack_spine_casing.check`): every element inside the casing x range and within 0.12 m of the casing, off every hull
  opening (plus 0.25 m) and access panel, and at least 0.05 m from every fixed exterior part (survival masts, terminals, trackers,
  crawler rails and stops; drone rails, docks and units; service fittings, docking corridors and the shield spokes' aft members).
  102 elements; blue 1.1 % of the detail area.
- **Exterior hardware in the families:** the SP-51 crawler hardware, the SP-53 survival terminals and the A29 star trackers map to
  graphite machinery, like the S02 RCS pods, antennas and sensors.

## Phase 4 materials, markings and wear (S9)

The grammar look (`hero_preview.dress(grammar=True)`) and the runtime exterior (Godot `flight.gd`, manifest `look.exterior.grammar`
from `look.runtime_grammar`) apply the same `[production.exterior]` data. Depiction only: no geometry, coating, capacity or canon change.

- **Library coverage:** every exterior-visible generated material has a family or keeps its own look (probe of the saved vehicle):
  the 450 K warm panels take the dark thermal depiction (no capacity credit), the coolant trunks, bellows and the hub's rotor-interface
  parts graphite, the crew tubes, transfer drums and the port neck light shell; `none` now keeps the material's own colour (the
  exterior lights' lenses). Hatches and closures stay proxy grey (physics-locked), as do the SIMPLIFIED/HOLD drive core, tanks and EYE
  optics.
- **Ram face** (`[production.exterior.ram_face]`, ILLUSTRATIVE, OWN-P4-LOCKED (b)): on the forward-facing faces of the disruptor layer and
  the Brow skin ahead of X 100 m, a running-bond tile pattern (1.6 × 0.8 m, dark 30 mm seams), each tile's value varied by ±4.5 % and 3 %
  of the tiles a fresh repair; no tile size, layer or repair-rate claim. `fractal_shield.pattern = "running_bond"` selects it; the
  default is the fractal shielding below.
- **Fractal shielding** (`[production.exterior.fractal_shield]`, PROTOTYPE, user brief 2026-10-27; reference `fractal_shield.py`): the
  same ram faces read as the replaceable facing plates of the segmented Brow laminate (`forward_defense.regenerative`). Flat-top hexagonal
  plates of 2.4 m side (one centred on the axis, projected along X; the cone is within 5° of the plane) with 80 mm dark gaps; each plate
  is six triangles (30 mm spokes) subdivided Sierpiński-fashion to depth 4 (sides 1.2, 0.6, 0.3, 0.15 m; grooves ×0.75 per level), each
  triangle subdividing with chance 0.85 from a stable integer hash. The centre triangle of every subdivision is a 1.5 mm recessed face,
  grooves are 3 mm V reliefs and the plate gaps 6 mm: 4.5 mm in all, within 10 % of the 50 mm disruptor sheet, never an opening. A
  0.11 m tri-clamp sits at every other plate corner (each clamp holds three plates, each plate hangs on three), so a plate is replaced
  alone. A plain collar of 0.35 m (0.5 m at the rim) surrounds the EYE wells and their layer ports, the Lance root and the Crown skin
  windows and layer ports. Each level fades in once its triangles span 4 px (fwidth): hexagons and plate tones from whole-ship
  distance, spokes and the first levels at subsystem distance, the finest triangles near a person. Shading and procedural normals only;
  the skin, layer, thickness, openings and clearances are unchanged and no shielding, mass or stack value is claimed
  (`forward_shield.stack` stays OPEN). One GLSL file, `godot/shaders/fractal_shield.gdshaderinc`, serves the Godot flight look
  (`p4_exterior`), the walk (`WfFractalShield.apply` on the exported Shield and DisruptorLayer materials, keeping their colour and alpha)
  and Explore Ship (`web/viewer/shield.js`, the file copied into the site as `shield_file` with build.json `shield`); the Blender grammar
  look builds the same formulas as nodes (`hero_preview.fractal_nodes`, Blender white noise for the hash, fixed footprint, Bump node).
  `python3 src/wayfarer/fractal_shield.py [--png out.png --centre y z --half m]` prints the fit screen and draws a preview raster.
- **Wear layer** (`[production.exterior.wear]`, off for the Y155 launch baseline): handling grime on service covers, heat staining on the
  root boots and blade frames, load marks on structure and machinery, faint weathering on shells; on the ram face denser repairs, more
  tile variation and pitting. A world-space noise with a soft threshold per family; Blender and Godot use their own noise, so the
  pattern differs in detail but not in where or how strongly it appears.
- **Ship name:** `G.U. WAYFARER 001` (text only, no G.U.C. or crest; the provisional casing stencil of 15!A216/A225) along casing module
  K3 on the three bisectors, 3.06 m cap height (the 300 m class, capped by the module length), bent onto the casing like the module
  numbers and stop IDs (`spine_casing`).
- **Runtime:** X in the timeline cycles the exterior looks: the grammar (Y155 baseline), the grammar with wear, the FUT-003 proxy grey,
  off. `godot/shaders/p4_exterior.gdshader` carries the ram face and the wear; plain families are standard materials; pack (`Prod_`)
  materials keep their exported finishes. Exterior packs draw each family to its scale tier (`detail_tiers`: segment rhythm, module
  bands, routes and numbers to 6 km, covers and markers to 1.5 km, clamps to 160 m); interior detail keeps 28 m.
  `flight.gd --capture-p4=<p4_review.json>,<dir>` renders the Blender review cameras in the runtime for the parity check (under
  Xvfb with the Compatibility renderer: same families and markings; more tile contrast and no bounce light than Cycles). The look
  materials draw both sides, like the exported materials they replace. The headless runtime check `flight-grammar` binds every look.

## Phase 4 hero set (S10)

`presentation/p4_hero.py` renders the five hero moments of the plan from the saved master assets in the grammar look: S004 induction
(DOCKED, primary port), departure (COAST, Y155 baseline), First Ignition (1800 K hot faces at matched exposure, plume not drawn),
survival (ram face with the wear layer) and return (wear layer). Posed and dressed in memory only; each still is captioned with its
configuration, look, sun (presentation choice, pointing OPEN) and exposure; `p4_hero.json` records every camera.

## Phase 4 grammar study (S1)

The NONCANON S1 experiment of [PHASE4_PLAN.md](PHASE4_PLAN.md) (owner P4-EXP, 2026-10-24) compared six exterior variants on Crown
bay 1 and one ring A segment; the owner selected VC+ with moderated values (next section). Its script is retired with the other
studies (commit 038ae90, reproduces the S1 images at 88ab15a).

## Phase 4 exterior grammar (S2)

The owner's S1 selection, **VC+ Expressive Hybrid with moderated values** (Art Style Bible Spacecraft row 19, source
`p4_exterior_grammar`; depiction only, S&E 15 `OWN-P4-LOCKED-2026-10-24`), is the shared production system `[production.exterior]`
that every exterior pack and the grammar look read. It changes no geometry and no accepted M7 value (`[production.materials]` stays the
interior standard).

- **Material families** (`[production.exterior.families]`, keys `xf_*`, linear base colour, roughness, metallic; glTF-safe, so Godot gets
  the same finish): light shell 0.73, structure 0.25, graphite machinery 0.05, dark thermal depiction 0.028, off-white root boots 0.68,
  ochre service, muted amber occupancy, GU deep-blue wayfinding, dark joints, charcoal and off-white marks, metallic fasteners. Starting
  points inside the owner's ranges, tuned under matched COAST/IGNITION; no reflectance or coating claim. `production_detail.material_value`
  resolves them like the M7 and pack materials.
- **Allocation:** pressure and protected volumes in calm light shells; load-bearing members mid value where they meet something;
  machinery and articulated interfaces graphite with readable assembly; ochre only for maintenance access; amber only over occupied
  sectors; blue only for service-lane boundaries, pressure-segment identifiers and navigation references; thermal surfaces dark with the
  frame and joint hierarchy visible.
- **Scale tiers** (`tier_range_m`, `tier_min_feature_m`, `tier_bevel_m`, `production_detail.tier_of`): MACRO assembly rhythm (bays, 15°
  segments, blade frames, casing modules; drawn to 6 km), MESO panels, caps, trays and covers (1.5 km), MICRO fasteners, small stencils and
  placards (160 m). Below 3 cm a feature is a value change or a seam, not geometry. Detail at distance comes from rhythm and value, never
  from enlarged small parts.
- **Panels, joints, negative space:** shell modules 2.0–6.5 m between joints, 30 mm dark seams, exposed mid-value joint caps over an
  80 mm dark gap; a shell zone keeps at least 35 % of its area free of meso and micro detail (`calm_field_min`, a review rule); fasteners
  only where a panel is serviced.
- **Markings** (text only): `production_detail.marking_height(s, class)` sizes the cap height so it spans 20 px in the reference camera
  (54° horizontal field, 1920 px) at the class's reading distance: ship name 3.2 m (300 m), bay numeral 1.38 m (130 m), sector ID 1.06 m
  (100 m), lane label 0.48 m (45 m), service stencil 0.32 m (30 m), handling 0.13 m (12 m), placard 0.03 m (3 m).
- **Accent budget:** `production_detail.accent_report` measures each accent's share of a pack's detail area against `accent_area_max`
  (blue ≤ 3 %, amber ≤ 10 %, ochre ≤ 8 %).
- **Blender/Godot mapping:** `[[production.exterior.ship_families]]` maps generated engineering materials by name prefix to a family
  (`production_detail.ship_family`; `none` keeps the material's own display look); production materials keep their pack finishes;
  unmatched materials (interiors, display layers, the SIMPLIFIED/HOLD drive core, tanks and EYE optics) keep the hero proxy grey. The
  grammar look `hero_preview.dress(grammar=True)` applies it in memory for stills, including the dark COAST blade depiction; the 1800 K
  IGNITION emission is unchanged. The runtime exterior applies the same mapping (S9).
- **Review set:** `presentation/p4_review.py` renders the matched cameras from the saved assets in the grammar look (or the pre-Phase-4
  hero look): whole ship (three-quarter, side, rings), forward (Brow sector, Crown bay, human scale), ring A (segment, human scale),
  radiator 1 (clamp, aft edge, 35 m, root) and the spine (between the blades, a module boundary, a crawler stop at human scale),
  with the matched COAST/IGNITION pair; `--pairs` makes before/after sheets.

## Characters

The two induction characters, the instructor (trainer) and the newcomer (trainee) of Tale S004A–D, derive from one MPFB 2.0.17
human system (C1–C3; [CHARACTERS.md](CHARACTERS.md)): recipes in `data/characters.toml`, one 53-bone `game_engine` skeleton, five shared
PROTOTYPE actions (idle, walk, sit, crawl, climb), the S004A greeting pose and eight driven corrective shape keys (knees, hips, elbows,
shoulders), assets `assets/characters/WF_CHAR_HUMAN_<ID>.blend`,
separate from the vehicle, with two technical fixtures. Bodies, clay skin and the S004 outfits (material zones; [CHARACTERS.md](CHARACTERS.md) "Outfits") are PROTOTYPE (roles fixed by Q49; identity OPEN in Tale WTF-16). The IND-001 proxies
stage the induction in Blender; in the Godot boarding walk the MPFB pair replaces them at the S004A greeting and the S004B couch. The six crew of the tale get
no character assets and no proxies. The generic mannequins stay the scale gauge.

## EVA suit and guided spacewalk

WAYFARER_EVA_Y155 ([EVA.md](EVA.md)) is the induction pair's guided-EVA suit: a conventional gas-pressure suit (cooling garment, continuous
bladder, restraint and thermal/MMOD outer layer as offset shells of each body; hard upper torso, torso-fixed helmet, dorsal PLSS with
cutaway internals, bearings, gloves, soles, two tether reels, sockets) on the unchanged MPFB rigs, with twelve PROTOTYPE EVA actions,
assets `assets/characters/WF_EVA_<WEARER>.blend`, separate from the vehicle. It is PROTOTYPE and NOT CERTIFIED; every unreleased
physical value (suit pressure setpoint, prebreathe, consumables, heat rejection, tether length, keep-outs, exposure inputs) is OPEN, and
the 40 kPa pure-O₂ case appears only as S&E 45's WORKING TRADE CASE. The interior induction is shirt-sleeve: suits are donned in SP-12
beside SP-11 and serviced in SP-13 (43 EVA-040), and the legacy 0.70 m `suited_envelope_diameter_m` is the UNSUITED route-control envelope
(EVA-041). The SP-11 door and chamber candidates (1.00/1.10/1.20 m, two-person and sequential) and the SP-12/13 rooms are a STUDY measured
against the vehicle, never ship geometry (EVA-043). The exterior route is a TRAINING SIMULATION on the stationary forward collar along the
SP-11 airlock's azimuth (X 95.6–106.0 m): every hold is SIMULATION_ONLY and FLIGHT_EVA is HOLD (locked, 45 O-07) because the ring,
thermal, debris, radiation and anchor gates have OPEN inputs; nothing in the vehicle changed. Its Godot drift scene is retired (commit 038ae90); the suit assets and `eva_*.py` screens remain.

## Crew physics

PHYS-001 ([PHYSICS.md](PHYSICS.md)) moves crew and loose objects as free bodies in Godot/Jolt from the owner rows of S&E 46/47,
Technology 54 and Tale 27 (WORKING). `crew_dynamics.py` writes the rig's `dynamics` block (contract 32): the SHIP frame (non-rotating,
`a = −a_ship`) for the spine, vestibule, airlock and exterior, and one RING frame per ring (centrifugal, Coriolis and Euler terms, geometry
static in the frame); a body changing frame transforms position and velocity together. It reproduces the 08/11 values (0.50097 g floor,
0.46519 g head, 0.0854 g Coriolis at 1 m/s, 11.29° LOW_THRUST tilt, HIGH_POWER rings locked and aft down). Ring A (aft) turns +4 rpm and ring B
(forward) −4 rpm about +X (08 ring_sign_convention, owner 2026-10-11). The three actor profiles are owner test fixtures (DYN-024); the
2.0 m training tether is tension-only with every impulse logged (DYN-025; stiffness, damping and loads `known = false`). Mode transitions
follow the owner sequence (drive off, occupants secured, spin down, lock, then HIGH_POWER; DYN-026, WORKING scenario, no event time) and
hold fail-closed; the rotary vestibule opens only the side the drum matches, with the occupant restrained and pressure equalized, and
hands over position and velocity with ω×r (DYN-027). Mode transitions are SIMULATION_ONLY, the drive's acceleration under thrust is the mode's envelope bound
(labelled, never a flight value), FLIGHT_EVA and the casualty route stay HOLD, and no key accelerates an unpowered body. The walk (below)
moves the trainee through these frames; its colliders come from the shared route and hull formulas (rig `dynamics.stages`), never from
the visual meshes. Blender bakes recorded traces onto proxies
(`shots/physics_traces.py`); a character there is an ARTISTIC layer.

## Station-to-ring excursion (EXC-001)

`godot/scenes/excursion.tscn` (`scripts/excursion/`) is one continuous, player-controlled run from the development station into Wayfarer,
round a whole habitat ring and back to the station, for either ring and as often as wanted without a reset. It reads the DOCKED
package and the rig (contract 43: `dynamics.stages.boarding`, `trunk`, `access` / `access_b`, `tube` / `tube_b`, `circuit`); Godot
computes no spacecraft geometry. It is SIMULATION_ONLY. It is the main interactive experience: the web launcher's Start opens it
and it is the Godot project's main scene (`godot --path godot`). On a touch device (MOB-001) the left thumb's stick moves along the body line (1-D) or
on the deck (2-D), the right thumb drags to look, and Use (labelled with what it works, e.g. "Use · open outer hatch"), Ops at a
trunk panel, View and Map appear when they apply; a phone layout keeps the goal and prompt top left and the ring map under the
utility row.

- **The station (STN-001, `station.py`, `[station]`, PROTOTYPE, not part of Wayfarer).** A docking adapter mated to Dock_Primary through
  the common soft-capture standard (Q33, 1.6 m passage) with the station's own hatch, a 3 m boarding tunnel and a 4 m boarding node
  (3.2 m diameter) inside the 3 m docking corridor: handrails, light strips, a boarding panel, two windows looking at the collar and the
  closed hatch to the station core (not modelled). Docked, station and ship are one rigid stack in free fall: the SHIP frame, zero field,
  no floor to stand on (the painted band is an orientation convention). Godot builds its whitebox and colliders from the rig.
- **Moving.** Weightless (station, airlock, trunk, drums, crew tubes) the trainee moves hand over hand along the rig's body lines (the M2
  technique): W/S pull toward the view; where no rail is in reach the body coasts at its push-off speed and cannot stop, so a push-off
  into a stretch with a shut closure is refused. A push-off brings the body to the line's pace before the hands let go; E within 0.8 m
  of the ring B junction lets the hands carry the body to it and turn in; the ladder taken from the deck draws the body onto it at no
  more than the line's pace. In a ring the trainee walks the deck (friction-limited foot contact, 1 m/s) with the
  mouse to look; the crew-tube and landing-well ladders are climbed rung by rung on the same line. E operates what is in reach (a hatch
  from its panel at the nearest rail stop, a corridor or sector door, the drum's cycle at its restraint station, the ladder, the ring B
  branch at its spine port); O asks for the operating change at a trunk panel; V outside view; M ring map.
- **The boarding line** (`station.boarding_line`): a push-off from the node's handrail straight to the port axis at the tunnel mouth,
  then down the axis through the station hatch, Wayfarer's outer hatch, the entry chamber (the stop for the airlock cycle), the inner
  hatch and a pivot head-aft into the trunk (least clearance 0.126 m), then aft along the trunk axis to ring B's and ring A's access
  starts. Every coast is straight: a free-flying body cannot turn, so each turn lies where a grip is in reach. Wayfarer's chamber and
  trunk node have rails only at their walls (1.23 m off the axis, out of reach), so the station's boarding kit rigs a webbing strap
  on the axis in each, clipped to the hatch frames and never across a hatch plane (PROTOTYPE; hatch-rim handholds would be the ship's
  alternative). The station opens its own hatch while docked and shuts
  it before separating; the airlock's two hatches are never open together.
- **Operating modes.** Docked, the rings are stopped and locked (14!A8): O at a trunk panel runs DOCKED → COAST in the owner's order
  (UNDOCK, OCCUPANTS_SECURED, RINGS_UNLOCKED, RINGS_SPIN_UP) and, on the way back, COAST → DOCKED (spin down timed to end at the
  index, lock, DOCK). The trainee holding still on a rail is the secured occupant; the 1800 s study ramp runs ×90 and the station
  stands off 25 m while undocked (display choices, PROTOTYPE).
- **Transfer.** Both rings' access lines and tube runs come from the rig; ring B's (`crew_dynamics.access_stage(s, 2)`): its
  0.90 m spine port opens into a drum annulus 0.95 m deep and 1.2 m long, where a rigid 1.75 m body turns at most 5° with 0.10 m
  clearance, so the trainee tucks to a 1.0 m body there (`[excursion] tuck`, PROTOTYPE technique, 1.1 m does not pass) and is guided
  on the port's frame into the restraint pose (least clearance 0.101 m), unfolding at the top of the crew tube. At the restraint pose E
  cycles the drum through the DYN-027 interlock: shut the open side, wait for the ring's phase, the 4 s ramp (MEC-019 OPEN), open the
  matched side; the same on the way back. Frames change only where they coincide (despun drum at the index, synchronized drum on the
  ring), so the body never jumps.
- **The circuit** (`ring_circulation.stage`): the sectors' deck, overhead (open round the hatch), bulkheads, interior blocks, landing
  chase and side walls with the door openings as boxes; the corridors' clear surfaces as a two-sided trimesh; each door a closed-leaf
  collider, disabled only when the leaf is fully open (mesh and collider move together). 177 m round each ring. The HUD records the
  circumference walked (72 bins) and the checklist per ring: boarded, circuit, back aboard the station.
- **Learning stations (UJ-013, `learning_stations.py`, `wf_learning.json` in the package; `scripts/excursion/learning.gd`).** A GU
  instructor (no identity defined, UJ-001) greets the trainee at spawn. At a learning point Use steps WHAT, WHY and SHOW ME and closes;
  walking away closes it. Two points in ring A sector 3: spin gravity at the mess table (UJ-003: 4 rpm at 28 m gives 0.50 g; the
  Coriolis push on a walker and a lifted mug; SHOW ME switches to the outside view) and life support at the ECLSS board (UJ-004: the
  owner's STUDY daily O2, CO2, water and food flows for the five human consumers, Seraph using none; the Garden credited with no food or
  O2; the stores' status, O2 and water makeup OPEN; SHOW ME a stock/flow overlay). Each finds its exported node by name and follows its
  ring; every number comes from the spec or data/life_support.toml with its source and status. The HUD counts the points learned.
  Six more points in sector 2 (internal teaching stops, S&E 15 Q48; placement PROTOTYPE): the Eyes (UJ-006, OPS 1: four facets, 2.5 m
  apertures, a 1 mg grain at 0.016 c carries 11.5 MJ), Aegis (UJ-007, OPS 2: microdust / cm / metre hazards and their answers), the
  mission preview (UJ-010, OPS 3: 0.016 c, 6 years, the planned state sequence), radiators (UJ-008, lab bench: three blades at 1800 K,
  26,882 m² effective area, drive waste heat OPEN), the drive (UJ-009, workbench: one core, four nozzles, 29.4 MN design load) and the
  debrief (UJ-011, medical couch), and the drones (UJ-014, under the sector-2 cable trays: the interior and exterior drone classes,
  every route HOLD). `wf_learning.json` carries the UJ-014 coverage matrix. Each SHOW ME except life support and the preview (overlays)
  is a remote camera: a fixed ship-frame eye and target per station (`show_me.camera`), shown from the stationary ship while the step
  is open; the walk resumes where the trainee stood. The open station stays in reach until 1.5 reaches; stations not yet learned are
  offered first.
- **Check** (`-- --check-excursion`, WF_GODOT_EXCURSION, in `runtime-export`): both excursions driven through the player's own actions:
  the shut outer hatch and spine-port gate stop the body, the inner hatch refuses while the outer is open, a shut corridor door blocks a
  body walking into it, both circuits are walked completely (72 of 72 bins, out of the landing well onto the passage and back), the
  rings lock at their index, every learning point is found and stepped through on the ring A circuit, the station is reached again, and no step moves the body more than 0.05 m beyond its own velocity (0.04 m
  measured, at spawn). Both excursions take 88,000 physics frames, about 100 s headless natively; the same check passes in the
  WebAssembly build in headless Chromium with drawing off (about 1,470 s), and the scene draws there without errors.

## Retired runtime scenes

The Godot review menu, the ship inspector, the guided induction walk, Demonstrator 01 with the Ship Navigator, its SPACE view and the
forward defense explorer, the First Ignition timeline player and thermal explorer, the life-support simulator, the physics lab, the EVA
drift and the M5/M6 hologram scenes are retired; commit 038ae90 holds them. The pure modules and data they
read stay as engineering screens with their tests: `ship_navigator.py` and `data/ship_navigator.toml`, `space_navigator.py`,
`forward_explorer.py` and `forward_scenario.py`, `life_support.py` and `data/life_support.toml`. No runtime scene consumes them now;
the export still packages the First Ignition timeline (`flight_timeline.py`) in the manifest. The walk's action registry still lists
the retired scenes' contexts (below) until it is pruned.

## Maintenance drones (DRONE-001)

S&E 51–54, Eye 46 and Tale 29 (TOC route keys `ignition.wayfarer.drones.*`) give a STUDY fleet: seven task classes, 11 IVA + 13 EVA = 24
mobile units (20 active, 4 reserve) and two fixed arms outside the 24. Every mass, power, speed, reach, load and latch rating is OPEN and every
station is UNPLACED / CAD OPEN, so `[drones]` holds the owner counts and envelope classes as OPEN and each station as a PROTOTYPE anchor on
existing geometry. `drone_fleet.py` resolves them; `WF_DRONES` (`Assembly_DRONES`, kind `drone_proxy`) holds the stationary docks, units,
rails and arm bases; the ring rover and duct cassettes are sector fit-out (`Drone_Dock_FloorCassette`, `Drone_Dock_DuctCassette`), so they
turn with their ring; the DS-11 radiator crawlers sit on the existing SP-51 root docks. The owner's answers of 2026-10-13 (S&E
15!A182:A187, source `owner_drones_2026_10_13`) are applied: the first root dock of each blade is the only powered HOME dock and the other
SP-51 positions are unpowered track / tool stops (same envelopes, relabelled); DS-01 and DS-09 sit in the bay next to SP-49; DS-13 is an
accepted L2 route with operations HOLD; every class carries its DGT-016 precedent with the owner's 54 DGT-SRC-01..08 status, as provenance only (DR-IVA-03 and DR-EVA-04: NO
DIRECT FLIGHT PRECEDENT IDENTIFIED); the latch (F_axial = m x 1.5 g0) and energy (Wh = P x h) formulas are carried with their inputs OPEN.

| Where | Stations |
| --- | --- |
| SP-45 storeroom racks | DS-02..04 reserves in the SP-49 bay (Outer bay 1.1); DS-01 survey flyers (shelves 1–2) and DS-09 micro crawler cassettes (shelves 3–4) in the bay next to it (Outer 1.2), as the owner's SP-49 service area; the stationary spine alcove itself is CAD HOLD. No illustrative containers in drone cells |
| Ring sectors (both rings) | DS-05/07 rover floor cassette (WORK_MEDICAL_OPS); DS-06/08 duct crawler door on the ECLSS bay (Garden) |
| Shield truss, aft side | DS-10 four Brow crawler docks on spokes 15/105/195/285° with radial rails; DS-15 forward arm base |
| Casing | DS-11 (SP-51 first-root HOME docks), DS-12 reserve, DS-13 spine crawler track at 110° with three docks (operations HOLD: no traversal while hot blades operate), DS-14 aft cradles, DS-16 aft arm base |

The fit screen covers DGT-002 counts, DGT-003 clearance to existing hardware, fittings, corridors and shield spokes, the 14 m maximum
body, DGT-005 ring sweeps (0.5 m margin), DGT-006 truss aft face, EYE ports for r4/r16/r24 and Crown ports, DGT-007 blades and DGT-008 the
casing's aft end; a geometric blade gap is not a radiant heat duty (15!A184). The rig block `drones` carries the fleet (`WF_DRONE_FLEET` v3, with precedent, operations and formulas), its keep-outs and `WF_DRONE_SCENARIO` v1: the DR-EVA-03-U03 service run on the
DS-13 track (inspect the SP-53 mast foot, tool-changer latch check) and three fault replays (power loss, rail jam, lost link), on explainer
time, gated by the 53 configuration rules (HIGH_POWER LOCKED). The keep-outs (`drone_fleet.keepouts`) bind DGT-005/006/007/008 to the
rig's existing massless volumes (`WF_SIMPROXY_RING_n_SWEEP`, `_SHIELD`, `_RADIATOR_nn`, `_PLUME_STUDY`) with the drone margin and measured
gap; they are not duplicated as drone meshes. The Ship Navigator's drones hotspot SHOW ME plays it (`drone_demo.gd`:
X run, K what-if configuration, Z/Y by guidance mode; check `nav_drone_demo`). `drone_routes.py` maps DGT-009: per class the 51 J jobs onto existing geometry as ROUTED / CARRIED / HOLD / PROHIBITED edges, the swept
clearance of each routed unit to existing hardware and the reach each job needs from its route (rig `drones.routes`, `WF_DRONE_ROUTES` v1;
reach OPEN, so no job passes). DGT-019 (owner 2026-10-17, 15!A201 / 54!A29 / 98!A111): `drone_routes.dgt019` turns the five route
choices into a per-job gap matrix (WF_DRONE_ROUTES v2): (a) DS-16 arm for aft utilities and DS-14 recovery, roots by DR-EVA-02 from DS-11
(no 94 m root service from DS-16); (b) ring rovers sector-bound, crew carry between sectors; (c) the one-sided 110° spine track, the far
side (19.3 m) by arm or crew EVA; (d) remote dock recovery by fixed arms or crew (9.3–12.3 m, a geometry demand); (e) Brow rail + arm
first. 29 jobs, 0 pass: each keeps a reach, payload or route deficit; no rail, station or drone is added. On the drones card C overlays it (OFF, all with the DGT-019 summary, one class at a time): routed legs, each target coloured by status
with a dashed reach line and its length, the interior classes on the card text (check `nav_drone_routes`). Every 54 gate stays HOLD; the gate register, conflicts and
the owner answers are in [references/DRONE_001_2026-10-13.md](../references/DRONE_001_2026-10-13.md). Evidence: full pipeline
`runs/20261013T193251Z-pipeline` (baseline `drones_l2_owner`), close-ups `preview.py --views drone_spine_detail drone_brow_detail drone_root_detail`,
navigator stills `drone_stills/` in `runs/20261013T142915069047Z-runtime`. Body candidates for every class (mechanisms, GU-SIF fittings,
actions, GLBs) are accessory assets outside the ship and replace no proxy (DGT-017 HOLD): [docs/ACCESSORIES.md](ACCESSORIES.md).

## Player controls (ACI)

The Godot runtime has one player-action registry, the autoload `WfInput` (`godot/scripts/controls/wf_input.gd`). Actions are bound
through Godot's InputMap, one context per scene; the walk sets `excursion` beside the always-active `ui` (Confirm, Back, Codex, details).
The registry still lists the retired scenes' contexts and actions (`walk`, `body`, `demo`, `nav`, `explorer`, `space`, `inspector`,
`flight`, `thermal`, `life`, `lab`, `eva`, `holo`); no scene activates them. Movement follows the keyboard position (W/S/A/D on QWERTY,
Z/S/Q/D on AZERTY); the others follow the printed key. Each handler asks `WfInput.key_of(event, its contexts)`, which names the
triggered action by its default key, so a rebind changes the input and not the handler. HUD key lines show the player's actual binding
for the device last used (`WfInput.label`, `WfInput.keys("{action}: …")`). Bindings change which input triggers an action, never
forces, speeds or permissions (S&E 46 DYN-007, 47 SIM-010, 49 NAV-003). On a touch-first device `controls/wf_touch.gd` (MOB-001) adds
the stick, the look drag and the contextual buttons.

- **Conflicts.** A conflict is the same input on two actions whose contexts can be active together (`ui` with everything). No two
  shipped defaults clash; Confirm, Back and Codex always keep a keyboard input, and Esc stays locked on Back.
- **Accessibility.** In the Codex any hold action can latch; the stick dead zone (0.2–0.65), sensitivity (×0.75–×2, never past full
  speed) and the 2-D panel size (100/125/150 %) are set there. Prompts never time out; every modal has a mouse route.
- **Profile.** `user://wayfarer_controls.cfg` (schema 3): bindings, preference, discovered actions, lessons, accessibility and touch
  settings. Unknown actions are dropped; a required action with no keyboard input is repaired. Nothing is written to `data/` or
  `generated/`.
- **Control Codex.** F10 or the codex action: this scene's actions (Tab: every context), each with its inputs, availability, function
  and physics note; rebind, restore defaults, switch hold/toggle, set text size, dead zone and sensitivity. The first-launch flow and
  the lesson cards remain in `control_overlay.gd`, but nothing opens the first-launch flow since the review menu was retired.

Controller prompts are text, not glyphs. The keyboard-layout labels were checked only on a US layout. The controller and
accessibility review stays OPEN (49 NAV-019). Audit, library decision and stages:
[references/ACI_PLAN_2026-10-17.md](../references/ACI_PLAN_2026-10-17.md).

## Limits

- The owner ring comparisons 08!C37 and C41:C45 (1.581 g at ~71.5° from radial if a ring kept
  spinning under 1.5 g; 88 N·m at 0.1°/s; 100.8 MN·m·s single ring; 1925 rpm / 1008 m/s / 10.2 GJ
  for a 20 t, 5 m flywheel, recalculated for 330 t) are DIAGNOSTIC comparisons that motivate stop-and-lock and
  counter-rotation. They are not limits, and the atmosphere does not size any airlock, refuge or sector.
- The radiators' 14,935 m² as-built net area stays whatever view factor is assumed; at
  factors 0.6/0.75/0.9 the effective area would be 17,921/22,402/26,882 m². The
  sampled sky-escape fraction (0.9028) is a geometric screen, not a validated
  thermal factor.
- The radiator health display changes colour and visibility only. The available-cell
  fraction is DIAGNOSTIC display, never multiplied into the 14,935 m² net area or
  the root-calibration margin; the 480-cell count, the fault order and the preset
  thermal states are PROTOTYPE, and the glow colours are not temperatures, emissivity or flux.
- The root-calibration margin is −1.60 GW (`thermal_budget.py`, DIAGNOSTIC, 40!B73):
  ideal rejection at the as-built 26,882 m², ε 0.90 and 1800 K (14.40 GW) minus the 16 GW calibration
  heat, before EYE, Crown, machinery and other ship loads. The deliberately reduced radiator
  is short at that load (the First Ignition overrun, OD-028); neither number is an operating
  load, and the 1e-4 heat fraction behind the 16 GW is itself DIAGNOSTIC (P1).
- The nozzle relies on magnetic plasma standoff first (Q40, 15!A103). `PFC_NOZZLE_STRIKE_02/03` are local, replaceable
  strike modules (8 per coil station) only at the two throat-side coils, a PROTOTYPE choice of contact zone (OPEN); they
  keep the 0.02 m envelope the coil-to-plasma gap allows, and their liner performance, active cooling, heat flux and life
  are unknown. Thickening them or the coils waits for a field/plasma/thermal study of the 0.09 m clearance and the Q26 offsets. The warm
  yoke sections, the cold-mass supports inside them, the terminated hub's local
  shielding, and the bulkhead's sizing and load shares are PROTOTYPE or OPEN (15!G67,
  G70, 07!H16). The stepped cryo sleeves and the optical bores block direct sight
  lines only: scattered dose and heat into the tanks and optics, and the sleeve and
  bore materials, are OPEN (OD-025, OD-026). So are the nuclear and radiant heating
  and the boil-off of the hydrogen lines along their hot-side corridor beside the
  core. The hydrogen injector ports, their count and the mixing are OPEN; only the
  injection ring's station is drawn. The corridor routing and the head positions are
  PROTOTYPE (15!G73, G83).
- With one axial fixed point per blade, the whole 1.5 g axial blade load passes
  through the aft root boom and its lugs; its share and sizing are OPEN (07!A29, A34).
  The feed and return now leave the hull aft of the mount block and clear the post, truss
  and block by at least 0.24 m with their chases (sampled screen). If the ~1.5 m aggregate
  free growth (Q12) accumulated from the aft-root datum rather than closing up at the joints,
  the leading edge would move about 0.80 m forward, past the Q45 collar's 0.675 m, and the
  trailing edge about 0.70 m aft against 1.0 m to the thrust ring; actual growth, CTE and
  the temperature map are OPEN (OD-007), and where the datum belongs is the owner question
  2026-10-09T15:05.
- The blades lie wholly ahead of the nozzle exit plane (aft edge 11.5 m ahead), so no
  hypothetical 5–20° cone reaches them. The actual propulsion plume and strong-field
  exclusion boundary is OPEN, and the roots and coolant feed may still cross it.
- Casualty movement and the integrated access architecture (HUM-002, ACCESS-005, OD-032/OD-040): full-length supported transport
  and care from every occupied sector in 0 g, spin, stopped and locked 1.5 g are REQUIRED; no hatch, port, guard, pin or pressure
  boundary changes yet. `studies/access_integrated.py` composes the worst-case segment studies (ring B `ringb_unified.py`, SP-11/12
  `eva_sp11*.py` and `eva3_exits.py`, SP-13/L1-A `eva3_sp13_l1a.py`, hatch step `char_step2.py`, in-sector care
  `ringb_insector_care.py`, L1-A stile `l1a_stile.py`) into route chains, sector coverage and closure families
  (references/ACCESS_INTEGRATED_2026-10-11.md). The chains follow the owner's 2026-10-13 answers (S&E 15!A169:A180): ring A at its
  worst-case re-run, SP-12 N2 fwd45 with its complete route and single faults, the SP-13 hinged dogged leaf with the shared-extension
  failure tree, the L1-A port at 205–215° with the stile candidates, the thrust step as B3H2, care at the in-sector points with the 1.5 g
  aids as options. No chain passes in any state: ring A fails (−0.171 to −0.455 m), in-sector care covers 0 of 24 sector states (the
  six Garden-couch passes needed Garden_Rack_1 removed, which 15!A174 keeps; best 1.5 g aid −0.066 m), SP-12 is MARGINAL behind the failing
  SP-11 limp casualty and fails single faults, an SP-12 fault blocks SP-13's trunk exit (−0.373 m); the D03 gallery study
  (`studies/d03_sp13_gallery.py`, [D03_SP13_GALLERY](../references/D03_SP13_GALLERY_2026-10-16.md)) gives SP-13 a second, separately
  pressurized exit to the refuge outside the trunk (az 125°, r 3.8 m, D 1.20 m: suited crew, litter and kit PASS, suited casualty
  MARGINAL +0.021 m; nothing built, owner approval of the pressure architecture pending), L1-A clears +0.064 m with the CB2J6 stile but stays OPEN on loads, B3H2 is MARGINAL (+0.049 m);
  31 of 32 closures lack a qualified two-way load path.
  Owner 2026-10-17 (15!A197:A199, 98!A109:A110): under locked 1.5 g a nonambulant casualty is restrained and stabilized at the rated burn
  couch and moved only after a safe thrust reduction (a disposition in the composer's `operating_rule_1_5g`, never a PASS; hold time and
  trigger HOLD); ring A stays a FAIL comparator and its port and spin-port turn are a reversible L2 whitebox
  (`studies/ringa_port_whitebox.py`, [RINGA_PORT_WHITEBOX](../references/RINGA_PORT_WHITEBOX_2026-10-17.md): deeper chamber variants
  under the same worst-case sweep: a 0.20 / 0.40 m deeper chamber lifts the unsuited annulus legs to MARGINAL +0.012 / +0.033 m; with the 0.40 m chamber, the trunk ladder and arrest rail joggled 30° or cut above the port window (PROTOTYPE, in-memory) lift the unsuited trunk legs A1 / A2 / A3 to −0.033…−0.050 m, still FAIL, limited by the cut rail end, trunk handrail 2 and the port rim; a couch-side transfer space (litter alongside the couch, Lab_Bench relocated) removes the Medical_Couch limit; the suited casualty fails every leg (−0.113 to −0.344 m; best −0.114…−0.169 m); with the cut 1.00 m above the port, trunk handrail 2 cut and
  the tube floor-ladder-2 arrest rails folded, A1 unsuited reaches MARGINAL +0.012 m and the 1.60 m port rim alone limits the spin-port turn
  (−0.013 m unsuited, −0.165…−0.169 m suited); rail, stile, bracket and couch ratings stay OPEN; a port wider than the 1.6 m trunk is not buildable without a trunk-side flare); B3H2 links stay ≤ 0.206 m;
  the SP-13 side gallery is the preferred L2 topology study (no cutout, no pressure facility).
  The M3 trade (`studies/ringb_rescue_trade.py`, references/RINGB_RESCUE_TRADE_2026-10-12.md, a study, nothing released) finds:
  - ring B's 0.9 m port is set by hub 1's forward cartridge withdrawal path, and a 1.6 m port needs 0.70 m of it;
  - a ring stop means both rings, since one ring stopped leaves 1000 times the allowed residual momentum;
  - the "24/24 sector-states with a Garden fold-down couch" was a zone screen only; the worst-case care study gives 0 of 24 with the rack kept.

  It recommends distributed care plus refuge in place. That waits on the owner's answer to where the ring water sits: 25.1 g/cm² on
  the sector shells, or 3.3 g/cm² round the frame.
- The primary entry is PROTOTYPE human-scale geometry, not a pressure design. Leaf
  latches, seals, the equalization and leak-check procedure, the chamber's
  pressurization and atmosphere, and the hinge hardware are OPEN (14!G32). The
  mannequin, eye height 1.65 m, suited envelope 0.70 m and reach 0.65 m are review
  selections, not anthropometric canon. The secondary port `Dock_Service` is still a
  solid proxy.
- The docking corridor (3.0 m radius) is a PROTOTYPE keep-out; the 3 m corridor is a WORKING value, not a docking-loads analysis, and the capture-ring diameter and mechanism are OPEN.
- The body is 225 m × 13 m; the radiators (r 37 m), rings (r 30 m) and forward
  shield (r 45 m) are wider. The Lance tip is at 237.0 m overall (the envelope includes the Lance).
- The shield's conical skin, truss, keels, ties, posts, disruptor layer, wells, load path and Lance are PROTOTYPE display geometry: the shield stack, mass and strength are OPEN (OD-014), and the spine column, struts, keels and ties carry no sized load. The disruptor layer's count, thickness, spacing and material are OPEN (Eye 40!E33), and its translucency is a display choice (checks treat it as opaque). The diversion-field zone is a display, not a field solution, and the damage cells show a state, not a repair rate.
- The engaged Crown hardware stays within r 43.353 m (inside the 45 m limit); its stroke, shutters and ports are PROTOTYPE and the Crown's range, power closure and effector performance are OPEN.
- **Bypass collar (Q45).** Its radii, depth, lacing and member sizes are PROTOTYPE and carry no sized load; the load split between collar and spine, the stiffness and the FEA are OPEN. Its aft frame stands in ring A's aft service gap in front of each blade's leading edge (0.675 m to each). The blade's datum stays at its aft root (AFT-009), so the gap holds only if the joints absorb the growth locally; the datum's place is the owner question 2026-10-09T15:05.
- The ring cross-section, spokes, frame, lock sizing and flexible modes are OPEN
  (08!A53, OD-016): the frame, sector arc, spoke rails and hatch position are
  PROTOTYPE display geometry, and the 2.427 MN per-ring axial load is not carried by
  any sized member.
- **Owner targets.** Every Q1–Q33 target the geometry is checked against is met (`owner_targets.pending` is empty); the rim axial
  deflection target (≤ 0.05 m) is an FEA target and is not checked.
- The 1.5 m ring/spar clearance is nominal (cold); the blade's thermal growth is unknown. The capture ring keeps
  only ~8 mm to the 7 m body maximum, a proxy fit, not a soft-capture mechanism. The refuge's inner-bore streaming
  and full areal-density map are not checked, so its shell is no radiation certification.
- HUM-001 zone 2 opens a 1.7 m hole in the 1.9 m spine core at X 99.40 m for the
  primary branch, so most of the spine section is cut there. That station is on the
  Brow's hub load path, which the spine shares with the Q45 bypass collar. The framed spine opening or node frame that
  must carry the load around it is not sized (OPEN), and neither is the 0.10 m
  residual spine shell around the trunk.
- HUM-001 zone 3 opens ring A's 1.7 m spine port at X 82.60 m, beside hub 1, across
  127° (35 %) of the spine core; that framed opening is not sized either. Its rim is a
  saddle on the 1.9 m core, so no hinged leaf fits; since Q46 a PROTOTYPE gate slides in a
  pocket of the 0.10 m spine shell, which slots the shell for 1.80 m forward of the port
  (3.5 m of slotted shell at ring A, 2.1 m at ring B; pocket framing, seal and drive
  OPEN). Ring B's 0.90 m spine port opens 64° (18 %) of the core at X 88.95 m, between
  the hubs; its framed opening is open in the same way. Ring B's port is the route's narrowest point
  (0.10 m around the suited envelope), and its guard ring sits exactly on the 0.15 m
  clearance to hub 1's withdrawal paths, so any growth of those paths or of the guards
  shrinks the port. The vestibule and spoke mannequins and cameras assume the rotors at
  their index angle. The despun transfer (Q46) is built as geometry and display controls
  only: the drum's sync cycle, despin drive, bearings, seals, latch collar and every
  closure's drive and seal are OPEN, and the route sweep proves the open, indexed pose
  (with the rings spinning the drum carries the crew between the same two poses; no
  sweep of the motion).
- Thrust review (aft down, rings locked): the trunk ladder and its rail make the shaft
  climbable from the floor to the primary branch. An unarrested fall from the refuge
  port's sill (13.45 m) reaches the floor at 19.9 m/s at the 1.5 g First Ignition peak
  (a 20 m fall at 1 g) and 5.1 m/s at the 0.1 g LOW_THRUST limit. The arrester must lock on
  speed across 0.04–1.5 g; its arrest distance and loads are OPEN, like the tubes'.
  Q47 (2026-10-07, `[habitat.thrust_movement]`, MEC-020) requires every essential route
  passable aft-down to 1.5 g, with the same hardware safe in spin and weightless; the
  footing below is built, every size PROTOTYPE (rung spacing, arrest threshold, distance
  and load, stretcher movement and certification OPEN):
  - Each crew-tube leg that rises with aft down carries a floor ladder
    (`Crew_Tube_j_k_Floor_Ladder_i_*`, `human_entry.floor_ladders`) on the line its floor
    takes, 90° round the tube from the side-wall ladder: the tube ladders' width and
    standoff, a rung every 0.30 m of rise from the leg's floor, its stiles the handholds.
    The 53° leg (52° on ring B) gets 5 rungs (4 on ring B) and the 20° ramp leg 3; the
    top rung of the steep leg is 0.11 m (0.07 m) below the run's floor. The run is
    level with aft down: 1.6 m high, walked stooped on its aft wall, the side-wall
    ladder's rungs standing upright beside it and the fall-arrest rail running 0.80 m
    above its floor as a handrail. A climber on the steep leg reaches the floor
    ladder's stiles (0.62 m). Each floor ladder carries its own fall-arrest rail on its
    centre line, resting on its rungs and bracketed to the wall at both ends, so the
    climber clips beside the body with a 0.21 m link. Nothing is fitted for resting on the
    run: the walker sits on its floor (0.66 m above a seated 1.8 m figure's head) and
    rises by the handrail.
  - Below each sector hatch (in a side wall with aft down, its sill 0.90 m above the aft
    skin) a step ladder on the overhead (`Sector_Thrust_Step_*`, `human_entry.thrust_step`),
    0.20 m off the hatch axis toward the landing ladder, rungs 0.25 m and 0.55 m above
    the aft wall, stopping below the leaf's guide rails; from it the landing ladder's
    stiles, which cross the opening at chest height, are the handholds (0.41 m and
    0.48 m reach). The last step to the sill is 0.35 m. In HABITATION the upper
    stowage forward of the hatch leaves 1.73 m above the top rung, so crew lean into the
    hatch from it; the other functions leave 2.83 m.
  - In each drum chamber a crawl rail (`Crew_Vestibule_j_Crawl_Rail_*`) runs round the
    outer wall 0.10 m above the aft end wall, between the openings and below the axial
    handrails, 10.4 m of rail with 0.40 m bare beside each opening. Ring B's chamber
    stays 1.10 m long (the height with aft down, a crawl; it cannot grow without moving
    hub 1's withdrawal paths, 15!H86); ring A's is 1.80 m, a stoop.
  A ring-A crew member reaching the refuge drops 2.45 m from the deck's level to the spine
  port and climbs 13.30 m (45 rungs) up the trunk; from ring B it is 2.10 m and 6.60 m
  (22 rungs). `Human_Elbow_Climber_*` stands on ring A's sector-1 steep floor ladder and
  `Human_Thrust_Step_*` on the step below that sector's hatch, with `CAM_HUM_THRUST_ELBOW`
  and `CAM_HUM_THRUST_STEP`. The route sweep is unchanged. The service dock and the
  airlock lie above the trunk ladder's top.
- HUM-001 zone 4 moved every sector's overhead hatch to the sector centre, 1.15 m
  beside the crew spoke, and zone 5 cleared a landing well under it by moving the
  side −1 blocks. Counts and functions are kept (12 bunks, 12 couches, Garden racks at
  their volume), but some blocks shrank: crew stowage 5.53 → 3.05 m³ with the new
  shelf, the lab rack 3.76 → 1.77 m³, medical 4.57 → 3.27 m³ and the common table
  2.11 → 0.67 m³. Ring B's sectors carry the same landing under their hollow tubes. Ring B's 0.90 m tube
  necks, like its spine port, leave 0.10 m around the suited envelope, and their flat
  bulkheads under cabin pressure are not sized (OPEN).
  The mitered elbows are a display choice. The framed openings in the inner hoop
  (1.7 m of its 4 m width beside each crew spoke), the tube-to-skin joint, the elbow
  shells and the bracket loads are not designed (OPEN). The sector leaf's seal, drive,
  latching and equalization are OPEN, and the vestibule hatch frames (1.6 m on ring A,
  0.90 m on ring B) carry no leaf.
- Each tube run lies 1.15 m off its sector's radial, so spin gravity leans a climber
  0.027 g toward the ladder on both rings. The Coriolis push of moving along the run
  (0.085 g per m/s) pulls a climber off the rungs climbing out of ring A and descending
  into ring B. The two cancel at 0.32 m/s, about one rung a second. At 0.5 m/s the net
  is 0.016 g off the rungs: the ladder feels 9° overhung at the top of the run (0.10 g)
  and 2° at the tip. Ring B keeps the shared ladder side. Mirroring ring B (tubes on the
  other side of the spokes, mirrored sectors) would only move its exposure from the
  descent to the climb, and is worth it only if crew climb the tubes while the rings
  spin (Q46). An unobstructed fall from the top of the run would reach the deck radius at
  up to 11.5 m/s, like a 6.7 m fall at 1 g, so each tube ladder carries a fall-arrest
  rail. The arrester's locking (spin gravity varies 0.04–0.45 g along the rail, so it must
  lock on speed, not weight), its arrest distance and loads, and the rail's bends through
  the mitered elbows are OPEN. The 9-rung sector ladder below the hatch has no rail.
- The refuge leg makes the storm refuge reachable at human scale from every sector with
  the rings stopped: 38–47 m and 74 rungs from each aisle, 1.3–1.6 min at the 0.5 m/s
  review pace (not a procedure). The owner's I4 (15!I20) requires it reachable with the
  rings rotating too: since Q46 crew cross from a spinning ring in the despun transfer
  drum (Hull and service fittings, "Despun transfer"), which carries them from the
  tube to the spine port, so nobody grabs a wall passing at 0.61 m/s; a controlled ring
  stop is the backup, whose spin-down duration is OPEN. The refuge port has no
  closure and the refuge has one egress: the hatch, its side and a second egress are OPEN
  (OD-011; the Q46 answer leaves them OPEN). Its 64° opening in the spine core at X 95.55 m, between the hubs and
  the primary branch, is a third framed spine opening that is not sized. The
  inner wall is an unsized pressure wall on the unshielded inner face. The twelve occupant
  stations are a PROTOTYPE layout, not restraints: sleep and thrust restraints (under
  thrust the occupants would stand on the aft wall), air, water, food, hygiene,
  communications and the endurance for 12 are OPEN (OD-011).
- The sector skin is a 0.05 m PROTOTYPE thickness inside the envelope; the gross
  volume is read as the envelope's (molded to the skin's outer face, 434.3 m³). Read as
  the volume inside the skin, the six sectors hold 403.1 m³, still inside the BASELINE
  400–460 m³, but near its floor.
- Preview success and geometry checks do not certify structural strength, thermal
  performance or radiation protection.

## Evidence

Each area's sources, checks and open questions are in its review:
[P1 engineering](../references/P1_ENGINEERING_REVIEW.md),
[P1B owner answers](../references/P1B_REVIEW.md),
[P1A schema, rig and hull](../references/P1_REVIEW.md),
[radiator hinges](../references/P1C_REVIEW.md),
[interiors](../references/P1D_REVIEW.md),
[simulation proxies](../references/P1E_REVIEW.md),
[drive manifold](../references/P1F_OPTICAL_MANIFOLD_REVIEW.md),
[power storage](../references/P1_007_POWER_STORAGE_REVIEW.md),
[rotor interface](../references/P1_008_ROTOR_INTERFACE_REVIEW.md),
[crew transfer](../references/P1_001_CREW_TRANSFER_REVIEW.md),
[HUM-001 eye-level review](../references/HUM001_EYE_REVIEW.md) and [its ring-B part](../references/HUM001_EYE_REVIEW_RING_B.md),
[shots](../references/FUT002_SHOTS_REVIEW.md),
[radiator measurements (V3)](../references/V3_REVIEW.md) and
[radiator trade](../references/MODEL_ADJUSTMENT_PLAN.md).
