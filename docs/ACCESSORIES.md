# Wayfarer accessories: EVA suit and maintenance-drone bodies

Accessories are reusable assets that live beside the ship: the WAYFARER_EVA_Y155 suit (docs/EVA.md) and the maintenance-drone body family
WF_DRONE_FAMILY_Y155. They never change ship geometry, shared parameters, the module registry or the accepted baselines. Everything here is
**PROTOTYPE**; nothing is canon, certified or a flight release. FLIGHT_EVA stays **HOLD** and every 54 drone gate stays **HOLD**.

**Owner decision (2026-10-24, chat):** approved to continue as a separate accessory prototype; **not** approved for ship integration or
canon release. DGT-017: the nine class models are permitted as isolated visual and interaction studies while the L2 integration gate stays
HOLD; they never replace the ship's proxies or imply the gate has passed. DGT-012: GU-SIF stays a proposed common interface. FLIGHT_EVA
HOLD: every EVA interaction is a training simulation. Drone mass, power, speed, payload, thermal endurance, manipulator load, latch strength
and suit life-support performance stay OPEN.

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
section SVG), `accessories/viewer/` + `tools/accessory_viewer.py` (standalone Godot viewer), `tests/test_drone_bodies.py` (owner counts,
envelope classes, OPEN values).

| Class | Form | Actions (SIMULATION_ONLY) | Stowed (m) |
| --- | --- | --- | --- |
| DR-IVA-01 free-flyer | chamfered cube, two fan modules, sensor band, perching arm, rear GU-SIF-S | undock_survey, perch, fault_hold | 0.34 × 0.33 × 0.35 |
| DR-IVA-02 rover | four wheels + captive guide shoe, cartridge cradle, 4-axis arm, sensor mast | drive, arm_pick, fault_hold | 0.46 × 0.35 × 0.38 |
| DR-IVA-03 micro crawler | two tracked segments, articulated waist, probe, tether eye | crawl, probe_inspect, jam_recover | 0.20 × 0.07 × 0.06 |
| DR-EVA-01 Brow crawler | twin-rail trucks, ORU bay with clamshell latches, 4-axis arm, periscope | traverse, oru_exchange, periscope, fault_hold | 0.53 × 0.51 × 0.51 |
| DR-EVA-02 radiator crawler | twin-rail trucks, three-layer heat-shield wall, RELL-type boom, valve arm, IR camera | traverse, leak_scan, valve_service, fault_hold | 0.54 × 0.51 × 0.42 |
| DR-EVA-03 spine crawler | twin-rail trucks, radiator lid, 5-axis tool-changer arm parking a cartridge (with a crew D-handle) in a cradle, spare caddy, pan-tilt head, tow fittings both ends | traverse, inspect, tool_present, handoff, fault_hold | 0.61 × 0.51 × 0.49 |
| DR-EVA-04 aft crawler | mono-rail C-trucks, shielded vault in gold MLI, two-stage telescoping non-contact sensor boom, no manipulator | traverse, boom_survey, fault_hold | 0.39 × 0.24 × 0.35 |
| DR-FIX-01 / 02 arms | 0.80 × 0.60 m owner base drum, 7-axis arm with GU-SIF-L end effector, stow cradle; 02 adds a heat hood and a tool holster | unstow, capture, fault_hold | base 0.80 × 0.60; booms display-only |

Arm keyframes come from a small display-pose solver (coordinate descent on the forward kinematics); residuals are reported, and a reached
pose is never a reach or payload claim. Swept envelopes (keyframes, travel excluded) are in `drone_bodies.json`.

Refinement pass (2026-10-24, same classes and envelopes): every folding arm has drive housings with brake rings at its pitch joints, a
harness run along each boom and a latched stow saddle with an orange manual release under the folded booms (thrust stow, DOP-03; power
loss, DOP-13); DR-EVA-03's tool cartridge carries a 22 mm crew D-handle for the supervised handoff (DOP-04); DR-EVA-04's boom became two
overlapping telescoping stages (one stage left the head floating at full extension). The fit screen still passes and every stowed body
stays inside its owner envelope class.

### GU-SIF: what approval needs (DGT-012 HOLD)

GU-SIF is one visual candidate for docks, tool cartridges, ORU grapples and robot-to-robot recovery. Before it could be approved:

| Item | Needs |
| --- | --- |
| Structural | latch preload and retention under 1.5 g thrust and docking impact; pin and flange stresses; fatigue over the docking count; misalignment capture range (lateral, angular) of the probe and pins |
| Electrical / data | contact rating (voltage, current) for HIGH_POWER docking charge (DOP-12 power OPEN); mate / demate under load or not; connector cycle life; data protocol and isolation from Seraph (hardware stop independence) |
| Thermal / environment | vacuum cold-welding of mating faces, thermal distortion across sizes, dust and debris tolerance outside, contamination inside |
| Operations | manual release force for a gloved hand; recovery-robot release path; keying so a wrong size or polarity cannot mate; failure state on power loss (stay latched) |
| Validation | design analysis, a mate/demate test series, a thermal-vacuum test, owner review against 54 DGT-012 and the DGT-SRC rows; standard text in the owner workbook, not in this repository |

## Suit (WAYFARER_EVA_Y155) changes

Look pass (first slice): bearings are flat machined bands with edge races, convolutes are three-rib bellows, elbow and knee zones of the
outer layer are charcoal (44 RUN-017), the PLSS is two replaceable modules with an interface band, latches, a vent, side rescue handles and
fastened covers, and the helmet has visor pivots and light/camera pods. The scye rings keep their old form (they set the owner-quoted
torso width).

Second slice (2026-10-24):

- **Hip bearings**: at the thigh root the limb section took in the buttock and the ring stood off as a crossing hoop. The hip bearing now
  sits below the crotch line on the thigh (bone fraction 0.20, 70th-percentile section radius), carried by the thigh. Every rotary bearing
  has a short sleeve inside its band: the soft goods visibly clamp onto the ring instead of leaving a gap round an oval limb.
- **Gauntlet** is carried by the forearm, so wrist flexion no longer swings the rigid cuff across the palm.
- **PLSS mount**: a mounting interface (structure and pass-throughs) between the hard torso and the pack closes the visible gap.
- **Glove grasp** (`build/eva_grasp.py`): a contact-aware display pose. Two-bone arm IK puts the wrist where the palm lands on the handle,
  the hand turns so the knuckle line runs along the handle, and each finger closes joint by joint (proximal first) until a segment reaches
  the handle surface or its display limit; the thumb closes from the other side. The rig, its bones and its 15 actions are unchanged; only
  the scene pose moves. Grip force, glove torque and hand fatigue are OPEN.
- **Compact PLSS study (ASSET-10)**: `eva_suit.py --plss compact --out-dir <dir>` builds the suits with the toml `plss_compact_size_m`
  (0.58 × 0.14 × 0.56 m) beside, never over, the baseline assets; `eva_fit.py --assets <dir>` measures it.

Fit readbacks (`eva_fit.py`, instructor / newcomer; references = `references/p1_eva_fit.json`, `p1_eva_envelopes.json`):

| Readback | Committed | Baseline after this slice | Compact study |
| --- | --- | --- | --- |
| pressure coverage | 15 EVA actions PASS; shared `crawl` (head out of the helmet) and the instructor's `climb` (8 vertices, 2.5 mm) FAIL | identical | identical |
| torso width (m) | 0.640 / 0.598 | 0.640 / 0.598 | 0.664 / 0.664 |
| torso depth with PLSS (m) | 0.798 / 0.769 | 0.798 / 0.769 | 0.718 / 0.689 |
| suited circle (m) | 0.909 / 0.885 | 0.909 / 0.885 | 0.890 / 0.867 |
| 0.90 m ring-B spine port (instructor) | BLOCKED −9 mm | BLOCKED −9 mm | CLEAR +10 mm |
| EVA_SUITED access class (m) | 0.857 / 0.832 | 0.857 / 0.832 | 0.815 / 0.792 |
| EVA_SUITED minimum projected area (m²) | 0.467 / 0.432 | 0.473 / 0.439 | 0.445 / 0.410 |

The baseline suit's envelopes, coverage results and access classes are identical to the committed references (the two shared-action coverage failures predate this work). The projected-area minimum moved
with the side rescue handles: a **thermal readback** for the owner's model (45 H-06), not a gate input and not engineering approval; the
references refresh at the next `workflow.py eva`. The compact study shows the same contents in a 33 % smaller display envelope: whether they
fit (oxygen, CO₂ removal, fan/pump/separator, heat rejection, battery, radio) is the ASSET-10 question and stays OPEN; its 10 mm margin at
the 0.90 m port is a prototype readback, not a reason to adopt it.

## Standalone accessory viewer (Godot 4.7.2)

`accessories/viewer/` is its own Godot project (GL Compatibility), independent of `godot/`, the runtime export and the module registry. It
loads the GLBs from `generated/` at run time (no editor import), lists the nine designs and the two scenes (EVA tool handoff, interior
drones), plays every action, and labels each motion SIMULATION_ONLY and each interface as unverified (DGT-017, DGT-012, FLIGHT_EVA HOLD).

```bash
python3 tools/accessory_viewer.py stage            # builds the drone GLBs and scene GLBs (Blender), fills accessories/viewer/generated/
python3 tools/accessory_viewer.py open             # interactive: pick a design or scene, pick an action; drag to orbit, wheel to zoom, F to frame
python3 tools/accessory_viewer.py check            # headless: every entry loads, every action plays, every entry carries its gate labels
python3 tools/accessory_viewer.py shots --out <dir>   # a screenshot per entry (xvfb-run when there is no display)
```

`stage --from <run>` reuses a run folder that already has `glb/` and `scenes/`. Godot is the repository's pinned 4.7.2 (tools/web_play.py
SHA-512); set `WAYFARER_GODOT` and `WAYFARER_BLENDER` when they are not at `/snap/bin/`.

## Run

```bash
B=${WAYFARER_BLENDER:-/snap/bin/blender}; OUT=runs/$(date -u +%Y%m%dT%H%M%SZ)-accessories
python3 src/wayfarer/drone_bodies.py                     # fit screen (pure)
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/build/drone_bodies.py -- --out $OUT
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/drone_preview.py -- --out $OUT/review --views review --quality review
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_suit.py      # needs `workflow.py characters` once
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_suit.py -- --plss compact --out-dir $OUT/compact
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/validation/eva_fit.py -- --assets $OUT/compact --report $OUT/compact/fit.json --renders $OUT/compact/r --no-route
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/accessory_scene.py -- --out $OUT/scenes --glb --quality review
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/eva_preview.py -- --views turnaround cutaway plss_compare \
    --out $OUT/suit --compact $OUT/compact --numbers <json>
python3 src/wayfarer/presentation/rail_section.py --out $OUT/rail_section.svg
```

The drone build takes about 25 s, the suit build about 1 min, the fit check about 2 min per suit set and the review-quality renders a few
minutes on 4 CPU cores (cloud session, Blender 5.2.2). Assets (`assets/drones/`, `assets/characters/`, the compact study) are local and
ignored; GLBs and renders go to the run folder.

## Review package (persistent)

`accessories/review/` holds the curated review images committed with the code that makes them (JPEG, about 3 MB in all; the index is
`accessories/review/README.md`): the family lineup with the suited instructor as scale, a labelled three-quarter view of each of the nine
designs in its main action, the suit turnaround (front, side, back, three-quarter) and cutaway, the baseline-vs-compact PLSS comparison
with a pack cutaway, the EVA tool handoff with a grasp close-up, the interior-drones scene, viewer screenshots and the crawler rail
section (SVG). Large intermediate files and redundant renders stay out of Git.

## Open and HOLD

- All owner physics: drone mass, power, speed, reach, payload, manipulator load, latch strength, thermal endurance (data `[open]`); suit
  life-support performance, glove torque and grip.
- DGT-017: the bodies are isolated studies, not integrated; the ship keeps its L2 proxies.
- DGT-012: GU-SIF and the cartridge standard are proposals (approval needs: table above).
- FLIGHT_EVA HOLD; exterior work is training simulation; DS-13 operations HOLD while blades are hot; radiator cooldown / view factor
  OPEN; Brow ram face and live drive never.
- Not done: textures and wear at touch points, the boots' shell form, glove finger mobility limits from owner data, a compact PLSS packaging
  closure, runtime actions for the suit in the accessory viewer (the handoff scene is static).

## Interface requests for the ship session (not applied)

The ship session owns all ship geometry, stations, anchor positions, structural rails and integration gates. These are requests only.

1. **Habitat rover deck guide** (S&E 51 DR-IVA-02 "retained surface guide"): please study a retained deck-guide path along the rover's
   service route near the DS-05/07 floor cassettes. The 40 mm channel used in the review scene is provisional, not an approved cut into
   either ring's floor. Temporary alternative: the rover runs unguided inside its sector and parks in its cassette (current proxy).
2. **External drone clearance**: the candidate bodies are taller than the current L2 placeholders. Please run a placement and keep-out
   study; this is not a request to resize proxies automatically.

   | Class | L2 proxy (m) | Candidate stowed body (m) | Over on |
   | --- | --- | --- | --- |
   | DR-EVA-01 | 0.60 × 0.60 × 0.36 | 0.53 × 0.51 × 0.51 | height +0.15 |
   | DR-EVA-02 | 0.60 × 0.60 × 0.36 | 0.54 × 0.51 × 0.42 | height +0.06 |
   | DR-EVA-03 | 0.70 × 0.70 × 0.42 | 0.61 × 0.51 × 0.49 | height +0.07 |
   | DR-EVA-04 | 0.40 × 0.40 × 0.24 | 0.39 × 0.24 × 0.35 | height +0.11 |

   All four stay inside their owner envelope classes (S&E 51 col G); the proxy depth is `drone_fleet.unit_size` (0.6 × the class for EVA).
   The interior classes fit their proxies.
3. **Crawler rail cross-section**: `accessories/review/rail_section.svg` shows the captive three-wheel truck on one rail (Ø60 mm rail,
   Ø48 × 20 mm wheels at 0° / ±120°, C-clamp R93 mm open 108° below with a 130 mm gap), the support web and the clearance a passing truck
   leaves for rail mounts: support webs within a 32 mm corridor down to 75 mm below the rail centre (5 mm running clearance to the
   under-wheels), wider brackets only below that, and a Ø206 mm swept envelope round the rail axis free of structure and harness. Please
   provide the rail section, web spacing and mount pattern from the ship side; loads and ratings are OPEN.
4. **Source map**: add S&E `56_DRONE_TECH_ANCESTRY!A1:I9` (class ancestry: demonstrated ancestor, ancestry status, evidence, unvalidated
   extrapolation, sources, owner / gate) to `data/source_map.toml` next to `[sources.drone_fleet]`. Shared source routing: integration owner.

## Tooling note: Drive reader

`.claude/agents/wayfarer-drive-reader.md` allowlists Drive, Sheets and Docs tools under connector-instance names
(`mcp__30a42b68-…`, `mcp__4c0b4b69-…`, `mcp__92ae634d-…`). In Claude Code Cloud sessions the same connectors are exposed as
`mcp__Google_Drive__*`, `mcp__Google_Sheets__*` and `mcp__Google_Docs__*`, so the delegated agent has no Drive tool there and returns
BLOCKED. Until its owner adds the cloud names (or a name-independent allowlist), the parent session does the bounded reads (this slice:
Art Style Bible `Objects & Tech!A1:L40` and `Anti-Rules!A1:L30`; S&E `56_DRONE_TECH_ANCESTRY!A1:I9`) and passes verified extracts on.
