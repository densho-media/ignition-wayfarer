# Wayfarer accessories: EVA suit and maintenance-drone bodies

Accessories are reusable assets that live beside the ship: the WAYFARER_EVA_Y155 suit (docs/EVA.md) and the maintenance-drone body family
WF_DRONE_FAMILY_Y155. They never change ship geometry, shared parameters, the module registry or the accepted baselines. Everything here is
**PROTOTYPE**; nothing is canon, certified or a flight release. FLIGHT_EVA stays **HOLD** and every 54 drone gate stays **HOLD**.

**Owner decision (2026-10-24, chat):** approved to continue as a separate accessory prototype; **not** approved for ship integration or
canon release. DGT-017: the nine class models are permitted as isolated visual and interaction studies while the L2 integration gate stays
HOLD; they never replace the ship's proxies or imply the gate has passed. DGT-012: GU-SIF stays a proposed common interface. FLIGHT_EVA
HOLD: every EVA interaction is a training simulation. Drone mass, power, speed, payload, thermal endurance, manipulator load, latch strength
and suit life-support performance stay OPEN.
Later the same day the owner retained the overall direction as provisional design candidates (none final) and promoted the
accessories to `main` as a standalone design-review capability; that installs nothing in the ship and releases no gate.

## Sources (live Drive read 2026-10-24)

S&E (modified 2026-10-24T09:24Z), Technology, Eye, Tale, Art Style Bible (modified 2026-10-24T09:24Z). The rows used:

| Source | Rows | Status | Consequence for the accessories |
| --- | --- | --- | --- |
| S&E 51_DRONE_FLEET | DR-IVA-01..03, DR-EVA-01..04, TOTAL-MOBILE, DR-FIX-01/02, DRV-GUARD | PROPOSED / NOT SIZED; STUDY INVENTORY | one body per class; 24 mobile (20 + 4) and 2 fixed arms; stowed body within the envelope class (col G upper bound); mass OPEN for every class |
| S&E 53_DRONE_OPERATIONS | DOP-01..16 | PROPOSAL (DOP-12, DOP-15 OPEN) | docked in HIGH_POWER (latched cradles, captive trucks); hardware stop independent of Seraph; lost link → stop and retreat; stranded unit → second robot / arm retrieval (tow fittings); no hot-blade, live-drive or ram-face work |
| S&E 54_DRONE_VALIDATION | DGT-001..019, DGT-SRC-01..09 | all HOLD | **DGT-017: "L2 interface gate passed before detailed meshes"** — these bodies are review candidates, not integrated |
| S&E 56_DRONE_TECH_ANCESTRY | A1:I9 (header + DR-IVA-01..03, DR-EVA-01..04, DR-FIX-01/02; 9 columns: intended behaviour, closest ancestor, ancestry status, evidence, extrapolation NOT validated, two public sources, owner / gate) | ancestry only | the "demonstrated → extrapolated" column below; a source-map addition for the integration owner (request 4), not added here |
| S&E 43 / 44 / 45 | EVA-001..065, ASSET / RIG / RUN / EVA2 / EVA3, 45 G/H/I/O | PROTOTYPE / HOLD | EVA-064 (bidirectional closures) and EVA-065 (the 2.0 m tether is a training fixture) are new since the 2026-10-11 capture; neither changes the suit geometry |
| Technology 53_EVA_SUIT_SYSTEMS | 20 rows | WORKING / RESEARCH | gas-pressure suit, MCP not baseline, finite O₂ / CO₂ / heat, no radiation-proof suit, GU look (matte white-grey, charcoal joints, deep-blue plates, minimal orange) |
| Technology 21_ROBOTICS_EMBODIMENT | surface crawlers, docked-by-default, physical limits, size classes | Working / Established | modular serviceable bodies with visible service history; mobility chosen by environment; no hovering trope |
| Art Style Bible | Objects & Tech (GU issue), Anti-Rules | canon visual rules | standardization, service access, qualification markings; no generic sci-fi greebles, no neon, no decorative circuitry |

## Existing implementation (A0)

| Feature | State |
| --- | --- |
| Suit contract, soft layers, rigid parts, 15 EVA actions, fit and access studies, Godot training scene | existing and reusable (docs/EVA.md) |
| Suit look: bearings as thin rings, plain PLSS box, featureless helmet | existing but incomplete → improved here |
| Fleet inventory, stations, L2 dock proxies, keep-outs, route gap matrix, crawler demo | existing and reusable (drone_fleet.py, drone_routes.py, drone_demo.py; docs/MODEL.md) |
| Drone bodies, mechanisms, tool interfaces, per-class actions, GLB | missing → added here as accessory assets |
| Mass, power, speed, reach, payload, latch rating, endurance, thermal duty | blocked by owner data (OPEN) |
| Conduits for DR-IVA-03, deck guide for DR-IVA-02, Brow/root/aft rails as released hardware | blocked (CAD / CONDUIT / HEAT HOLD) |

## Evidence: demonstrated → extrapolated → IGNITION

| Feature | Demonstrated (real) | Extrapolation here | Status |
| --- | --- | --- | --- |
| Interior fan free-flyer, perching arm, dock | NASA Astrobee (flown on ISS since 2019: cube body, fan propulsion, perching arm, dock with charging) [NTRS](https://ntrs.nasa.gov/citations/20160007769); JAXA Int-Ball2 (flown) | DR-IVA-01: two side fan modules, rear GU-SIF dock, handrail perching instead of fan hold | REFERENCE (S&E 56) |
| External leak sniffing by robot | NASA RELL: quadrupole mass spectrometer carried by Dextre, used on ISS 2016–2017 to locate an ammonia leak [NASA](https://www.nasa.gov/isam/robotic-external-leak-locator) | DR-EVA-02 carries its own RELL-type head on a boom | REFERENCE; no radiator-surface crawler precedent |
| Rail-borne worksites, positive attachment | ISS Mobile Transporter / Mobile Base; Canadarm2 and Dextre exchanging ORUs ([CSA](https://www.asc-csa.gc.ca/eng/iss/mobile-base/)) | captive three-wheel rail trucks, GU-SIF grapple fittings on ORUs and robots | REFERENCE / NO FLIGHT QUALIFICATION |
| Climbing / anchoring crawlers | JPL LEMUR (ground test) | none taken over beyond the idea of anchored mobility | analogy only |
| Gas-pressure suit, PLSS | NASA EMU (operational): primary and secondary O₂, fan/pump/separator, METOX CO₂, water sublimator [NTRS](https://ntrs.nasa.gov/citations/20120003778) | two replaceable PLSS modules, separate emergency reserve, vent, side rescue handles | 40 kPa is a 45 WORKING TRADE CASE only |
| Next-generation suit mobility | Axiom AxEMU in development (PDR done; NASA-led CDR pending in 2026; 850+ h crewed pressurized tests) [NASA](https://www.nasa.gov/missions/artemis/nasa-moon-mission-spacesuit-nears-milestone/) | low-torque bearings, banded joints, helmet lights and cameras | development hardware, not flown |

## Design grammar (shared GU language, PROTOTYPE)

- **GU-SIF** (Standard Interface Fitting), one geometry in three sizes (S 50, M 90, L 160 mm): flange, guide probe or active receptacle,
  three kinematic pins, power/data pad, positive latch, orange manual release (M, L). Used for docks, tool cartridges, ORU grapples and
  robot-to-robot recovery (DGT-012 standard HOLD: a proposal for owner review).
- **Safety kit on every class**: hardware stop (orange), status lamp, GU qualification plate with the class code, a dock, a recovery
  fitting. Orange is reserved for safety hardware; deep blue for GU identity; white beta cloth / polymer shells, graphite structure,
  silvered radiator lids on exterior bodies, gold MLI only on the cryogenic-adjacent aft crawler.
- **Movement differs by environment**: fan modules in cabin air (IVA-01), wheels with a captive guide shoe on spinning decks (IVA-02),
  tracked articulated segments in raceways (IVA-03), captive rail trucks outside (EVA-01..03 twin rail, EVA-04 mono rail), stationary
  bases with stow cradles for the arms. No class hovers in vacuum or crawls on a blade.

## Built

`data/drone_bodies.toml` (parameters), `src/wayfarer/drone_bodies.py` (pure: node trees, GU kit, actions, display-pose solver, fit screen),
`src/wayfarer/build/drone_bodies.py` (Blender assets + GLB), `src/wayfarer/presentation/drone_preview.py` and `accessory_scene.py`
(review renders and scene GLBs), `src/wayfarer/build/eva_grasp.py` (display grasp), `src/wayfarer/presentation/rail_section.py` (rail
section SVG), `tests/test_drone_bodies.py` (owner counts,
envelope classes, OPEN values).

| Class | Form | Actions (SIMULATION_ONLY) | Stowed (m) |
| --- | --- | --- | --- |
| DR-IVA-01 free-flyer | chamfered cube, two fan modules, sensor band, perching arm, rear GU-SIF-S | undock_survey, perch, fault_hold | 0.34 × 0.33 × 0.35 |
| DR-IVA-02 rover | four wheels + captive guide shoe, cartridge cradle, 4-axis arm, sensor mast | drive, arm_pick, fault_hold | 0.46 × 0.35 × 0.38 |
| DR-IVA-03 micro crawler | two tracked segments, articulated waist, probe, tether eye | crawl, probe_inspect, jam_recover | 0.20 × 0.07 × 0.06 |
| DR-EVA-01 Brow crawler | twin-rail trucks, ORU bay with clamshell latches, guide posts and seat, 4-axis arm, periscope with a Brow inspection head (stereo cameras, light bar) | traverse, oru_exchange, periscope, fault_hold | 0.53 × 0.51 × 0.48 |
| DR-EVA-02 radiator crawler | twin-rail trucks, three-layer heat-shield wall, upper deflector, silvered blade-side faces, IR radiometer turret, RELL-type boom, valve arm, IR camera | traverse, leak_scan, thermal_survey, valve_service, fault_hold | 0.54 × 0.51 × 0.39 |
| DR-EVA-03 spine crawler | twin-rail trucks, radiator lid, 5-axis tool-changer arm parking a cartridge (with a crew handle) in a cradle, three-slot tool magazine, crew handrail and tether anchor, pan-tilt head, tow fittings both ends | traverse, inspect, tool_present, handoff, fault_hold | 0.61 × 0.51 × 0.46 |
| DR-EVA-04 aft crawler | mono-rail C-trucks, shielded vault in gold MLI, two-stage telescoping non-contact sensor boom, no manipulator | traverse, boom_survey, fault_hold | 0.39 × 0.24 × 0.35 |
| DR-FIX-01 / 02 arms | 0.80 × 0.60 m owner base drum, 7-axis arm with GU-SIF-L end effector, stow cradle; 02 adds a heat hood and a tool holster | unstow, capture, fault_hold | base 0.80 × 0.60; booms display-only |

Arm keyframes come from a small display-pose solver (coordinate descent on the forward kinematics); residuals are reported, and a reached
pose is never a reach or payload claim. Swept envelopes (keyframes, travel excluded) are in `drone_bodies.json`.

Every folding arm has drive housings with brake rings at its pitch joints, a harness run along each boom and a latched stow saddle
with an orange manual release under the folded booms (thrust stow, DOP-03; power loss, DOP-13); DR-EVA-03's tool cartridge carries a
22 mm crew D-handle for the supervised handoff (DOP-04); DR-EVA-04's boom is two overlapping telescoping stages. The fit screen passes
and every stowed body stays inside its owner envelope class.

DR-EVA-01, -02 and -03 share one GU family (white vault, captive trucks, GU-SIF ends, GU stripe and plate) and read as one body with
different tools; each carries equipment for its own job:

- **DR-EVA-01 (Brow inspection, module handling)**: four guide posts with lead-in cones and a connector seat frame the ORU bay, so a
  module is led into the clamshell latches; the periscope ends in a Brow inspection head with stereo cameras and a light bar that looks
  round truss members and into EYE apertures from the safe side.
- **DR-EVA-02 (radiator shielding, thermal monitoring, leak investigation)**: an upper deflector on low-conductance standoffs shades the
  deck from the blade root, the blade-side vault faces are silvered, and an IR radiometer turret with a sunshade cone pans across root
  and blade before any approach (`thermal_survey`, DOP-08 cold-state check) beside the RELL-type leak boom. Optical properties, view
  factor and cooldown stay OPEN (DGT-007 HOLD).
- **DR-EVA-03 (tool logistics, cartridge handling, crew assistance)**: a three-slot tool magazine (spare torque, inspection probe,
  gripper cartridges on keyed GU-SIF-S seats), and the crew side carries a 25 mm handrail and an orange-tagged
  tether anchor ring (never a primary anchor; ratings OPEN).
- **Docking cradles on the review stands** (DR-EVA-01..03; not on the ship, DS-10/11/13 dock design OPEN): a pedestal between the rails
  rises to the crawler's underside GU-SIF-M, two V-guide posts with jaws centre the chassis beam, a charge / data umbilical and junction,
  a docked lamp and an orange manual undock release. Latch, charge and alignment ratings OPEN (DGT-012 HOLD).

The equipment sits below each body's arm and mast tops. Review-stand parts carry the `FIXTURE` prefix, which the fit screen excludes
from the stowed size (stowed heights 0.48 / 0.39 / 0.46 m).

### GU-SIF: what approval needs (DGT-012 HOLD)

GU-SIF is one visual candidate for docks, tool cartridges, ORU grapples and robot-to-robot recovery. Before it could be approved:

| Item | Needs |
| --- | --- |
| Structural | latch preload and retention under 1.5 g thrust and docking impact; pin and flange stresses; fatigue over the docking count; misalignment capture range (lateral, angular) of the probe and pins |
| Electrical / data | contact rating (voltage, current) for HIGH_POWER docking charge (DOP-12 power OPEN); mate / demate under load or not; connector cycle life; data protocol and isolation from Seraph (hardware stop independence) |
| Thermal / environment | vacuum cold-welding of mating faces, thermal distortion across sizes, dust and debris tolerance outside, contamination inside |
| Operations | manual release force for a gloved hand; recovery-robot release path; keying so a wrong size or polarity cannot mate; failure state on power loss (stay latched) |
| Validation | design analysis, a mate/demate test series, a thermal-vacuum test, owner review against 54 DGT-012 and the DGT-SRC rows; standard text in the owner workbook, not in this repository |

## Suit (WAYFARER_EVA_Y155)

The suit's form, look and life-support module are now those of the EVA system: a hybrid rear-entry suit with a rigid cuirass, an
integral helmet and a life-support module that is its back hatch and the companion drone's dock. Its description, the module's packaging
(volume only) and its validation are in [WAYFARER_EVA_SYSTEM.md](WAYFARER_EVA_SYSTEM.md). The earlier look pass (two-module PLSS,
bearing and gauntlet fixes) and the compact-PLSS study (ASSET-10) were superseded by it on 2026-11-03; they are in Git history. The glove
grasp pose (`build/eva_grasp.py`), boots, foot restraint and markings carried over.

### Validation semantics: EVA actions vs inherited unsuited actions

All 15 EVA actions pass the pressure-coverage check for both suits; the inherited shared `crawl` fails for both (head out of the
torso-fixed helmet). The shared actions come with the
wearer's unsuited character rig and are not suited EVA operations, so they cannot be read or played as one:

- `eva_suit.SHARED_ACTIONS` names them with the reason; a test keeps them disjoint from `EVA_ACTIONS` (the list the runtime plays).
- The suit build tags each inherited action `eva = False`, `suited_use = NOT_SUITED_EVA` with the reason, and the rig lists them in
  `eva_not_suited_actions` (the actions themselves and the MPFB rig are unchanged).
- `eva_fit` marks every coverage row `use = EVA` or `NOT_SUITED_EVA` and reports `eva_coverage_pass` and `not_suited_eva_failures` beside
  the unchanged overall `coverage_pass` (still false: nothing was relaxed to hide the failures).
- The accessory viewer shows the suit with its 15 EVA actions playable and the five inherited ones listed `LOCKED_NOT_SUITED_EVA`,
  refused with the reason when picked; its check fails if a locked action can play.

The shared `climb` passes for both suits: the scye sleeve turns with the upper arm, so the overhead reach no longer exposes the
skin under the scye bearing.

## Run

```bash
B=${WAYFARER_BLENDER:-/snap/bin/blender}; OUT=runs/$(date -u +%Y%m%dT%H%M%SZ)-accessories
python3 src/wayfarer/drone_bodies.py                     # fit screen (pure)
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/build/drone_bodies.py -- --out $OUT
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/drone_preview.py -- --out $OUT/review --views review cradles --quality review
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_suit.py      # needs `workflow.py characters` once
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/accessory_scene.py -- --out $OUT/scenes --glb --quality review
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/eva_preview.py -- --views turnaround cutaway --out $OUT/suit
python3 src/wayfarer/presentation/rail_section.py --out $OUT/rail_section.svg
# a turnaround of another build's suits (e.g. an older commit built in a git worktree) for a before / after sheet
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/eva_preview.py -- --views turnaround --assets <worktree>/assets/characters --out $OUT/before
```

The drone build takes about 25 s, the suit build about 1 min, the fit check about 2 min per suit set and the review-quality renders a few
minutes on 4 CPU cores (cloud session, Blender 5.2.2). Assets (`assets/drones/`, `assets/characters/`) are local and
ignored; GLBs and renders go to the run folder.

## Review package

The standalone accessory viewer (`accessories/viewer/`, `tools/accessory_viewer.py`) and the committed review images with the owner
review and handoff register (`accessories/review/`, `HANDOFF.md`, `review.pdf`) are retired; commit 038ae90
holds them. A new review package goes in `work/<task>/` as one REVIEW file (AGENTS.md "Where things go").

## Open and HOLD

The owner review and handoff register (`accessories/review/HANDOFF.md` at the archive tag) lists the decisions still open: visual decisions,
the engineering decisions for the canonical Drive sheets (DGT-017, DGT-012, clearances, rail section, docking stations, suit readbacks,
the deferred compact PLSS, every OPEN physics value, FLIGHT_EVA) and the ship-session requests. Also HOLD: DS-13 operations while blades
are hot, radiator cooldown and view factor (DGT-007); Brow ram face and live drive never.

- Not done: glove finger mobility limits from owner data, owner Art / Fashion markings (the lettering here is PROTOTYPE text only),
  image textures (wear is a soft vertex colour), the handoff scene's suit actions animated in the viewer (the suit entry plays them on
  its own; the scene stays static).

## Interface requests for the ship session (not applied)

The ship session owns all ship geometry, stations, anchor positions, structural rails and integration gates. These are requests only.

1. **Habitat rover deck guide** (S&E 51 DR-IVA-02 "retained surface guide"): please study a retained deck-guide path along the rover's
   service route near the DS-05/07 floor cassettes. The 40 mm channel used in the review scene is provisional, not an approved cut into
   either ring's floor. Temporary alternative: the rover runs unguided inside its sector and parks in its cassette (current proxy).
2. **External drone clearance**: the candidate bodies are taller than the current L2 placeholders. Please run a placement and keep-out
   study; this is not a request to resize proxies automatically.

   | Class | L2 proxy (m) | Candidate stowed body (m) | Over on |
   | --- | --- | --- | --- |
   | DR-EVA-01 | 0.60 × 0.60 × 0.36 | 0.53 × 0.51 × 0.48 | height +0.12 |
   | DR-EVA-02 | 0.60 × 0.60 × 0.36 | 0.54 × 0.51 × 0.39 | height +0.03 |
   | DR-EVA-03 | 0.70 × 0.70 × 0.42 | 0.61 × 0.51 × 0.46 | height +0.04 |
   | DR-EVA-04 | 0.40 × 0.40 × 0.24 | 0.39 × 0.24 × 0.35 | height +0.11 |

   All four stay inside their owner envelope classes (S&E 51 col G); the proxy depth is `drone_fleet.unit_size` (0.6 × the class for EVA).
   The interior classes fit their proxies.
3. **Crawler rail cross-section**: `rail_section.py` draws (default `runs/rail_section.svg`) the captive three-wheel truck on one rail (Ø60 mm rail,
   Ø48 × 20 mm wheels at 0° / ±120°, C-clamp R93 mm open 108° below with a 130 mm gap), the support web and the clearance a passing truck
   leaves for rail mounts: support webs within a 32 mm corridor down to 75 mm below the rail centre (5 mm running clearance to the
   under-wheels), wider brackets only below that, and a Ø206 mm swept envelope round the rail axis free of structure and harness. Please
   provide the rail section, web spacing and mount pattern from the ship side; loads and ratings are OPEN.
4. **Source map**: add S&E `56_DRONE_TECH_ANCESTRY!A1:I9` (class ancestry: demonstrated ancestor, ancestry status, evidence, unvalidated
   extrapolation, sources, owner / gate) to `data/source_map.toml` next to `[sources.drone_fleet]`. Shared source routing: integration owner.
