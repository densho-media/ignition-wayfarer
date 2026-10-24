# Wayfarer accessories: EVA suit and maintenance-drone bodies

Accessories are reusable assets that live beside the ship: the WAYFARER_EVA_Y155 suit (docs/EVA.md) and the maintenance-drone body family
WF_DRONE_FAMILY_Y155. They never change ship geometry, shared parameters, the module registry or the accepted baselines. Everything here is
**PROTOTYPE**; nothing is canon, certified or a flight release. FLIGHT_EVA stays **HOLD** and every 54 drone gate stays **HOLD**.

## Sources (live Drive read 2026-10-24)

S&E (modified 2026-10-24T09:24Z), Technology, Eye, Tale, Art Style Bible (modified 2026-10-24T09:24Z). The rows used:

| Source | Rows | Status | Consequence for the accessories |
| --- | --- | --- | --- |
| S&E 51_DRONE_FLEET | DR-IVA-01..03, DR-EVA-01..04, TOTAL-MOBILE, DR-FIX-01/02, DRV-GUARD | PROPOSED / NOT SIZED; STUDY INVENTORY | one body per class; 24 mobile (20 + 4) and 2 fixed arms; stowed body within the envelope class (col G upper bound); mass OPEN for every class |
| S&E 53_DRONE_OPERATIONS | DOP-01..16 | PROPOSAL (DOP-12, DOP-15 OPEN) | docked in HIGH_POWER (latched cradles, captive trucks); hardware stop independent of Seraph; lost link → stop and retreat; stranded unit → second robot / arm retrieval (tow fittings); no hot-blade, live-drive or ram-face work |
| S&E 54_DRONE_VALIDATION | DGT-001..019, DGT-SRC-01..09 | all HOLD | **DGT-017: "L2 interface gate passed before detailed meshes"** — these bodies are review candidates, not integrated |
| S&E 56_DRONE_TECH_ANCESTRY | one row per class | ancestry only | the "demonstrated → extrapolated" column of each class below (new tab; not yet in data/source_map.toml) |
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
(review renders), `tests/test_drone_bodies.py` (owner counts, envelope classes, OPEN values).

| Class | Form | Actions (SIMULATION_ONLY) | Stowed (m) |
| --- | --- | --- | --- |
| DR-IVA-01 free-flyer | chamfered cube, two fan modules, sensor band, perching arm, rear GU-SIF-S | undock_survey, perch, fault_hold | 0.34 × 0.33 × 0.35 |
| DR-IVA-02 rover | four wheels + captive guide shoe, cartridge cradle, 4-axis arm, sensor mast | drive, arm_pick, fault_hold | 0.46 × 0.35 × 0.38 |
| DR-IVA-03 micro crawler | two tracked segments, articulated waist, probe, tether eye | crawl, probe_inspect, jam_recover | 0.20 × 0.07 × 0.06 |
| DR-EVA-01 Brow crawler | twin-rail trucks, ORU bay with clamshell latches, 4-axis arm, periscope | traverse, oru_exchange, periscope, fault_hold | 0.53 × 0.53 × 0.52 |
| DR-EVA-02 radiator crawler | twin-rail trucks, three-layer heat-shield wall, RELL-type boom, valve arm, IR camera | traverse, leak_scan, valve_service, fault_hold | 0.54 × 0.53 × 0.43 |
| DR-EVA-03 spine crawler | twin-rail trucks, radiator lid, 5-axis tool-changer arm parking a cartridge in a cradle, spare caddy, pan-tilt head, tow fittings both ends | traverse, inspect, tool_present, handoff, fault_hold | 0.59 × 0.53 × 0.45 |
| DR-EVA-04 aft crawler | mono-rail C-trucks, shielded vault in gold MLI, telescoping non-contact sensor boom, no manipulator | traverse, boom_survey, fault_hold | 0.39 × 0.24 × 0.37 |
| DR-FIX-01 / 02 arms | 0.80 × 0.60 m owner base drum, 7-axis arm with GU-SIF-L end effector, stow cradle; 02 adds a heat hood and a tool holster | unstow, capture, fault_hold | base 0.80 × 0.60; booms display-only |

Arm keyframes come from a small display-pose solver (coordinate descent on the forward kinematics); residuals are reported, and a reached
pose is never a reach or payload claim. Swept envelopes (keyframes, travel excluded) are in `drone_bodies.json`.

The suit changes (build/eva_suit.py): bearings are flat machined bands with edge races, convolutes are three-rib bellows, elbow and knee
zones of the outer layer are charcoal (44 RUN-017), the PLSS is two replaceable modules with an interface band, latches, a vent, side
rescue handles and fastened covers, and the helmet has visor pivots and light/camera pods. The scye rings keep their old form (they set
the owner-quoted torso width). Re-measured with `eva_fit.py`: pressure continuity PASS for every action as before; the torso envelope
(0.64 × 0.80 m, 0.909 m circle; 0.60 × 0.77 m, 0.885 m) and every access class diameter (EVA_SUITED 0.857 / 0.832 m, EVA_OPERATIONAL,
RESCUE, UNSUITED) are identical to `references/p1_eva_fit.json` / `p1_eva_envelopes.json`. Only the silhouette-area readback for the
owner's thermal model moved: EVA_SUITED minimum projected area 0.467 → 0.473 m² (instructor), 0.432 → 0.439 m² (newcomer), from the side
rescue handles; it is a readback, never a gate input (45 H-06), and the committed references refresh at the next `workflow.py eva`.

## Run

```bash
B=${WAYFARER_BLENDER:-/snap/bin/blender}; OUT=runs/$(date -u +%Y%m%dT%H%M%SZ)-accessories
python3 src/wayfarer/drone_bodies.py                     # fit screen (pure)
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/build/drone_bodies.py -- --out $OUT
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/drone_preview.py -- --out $OUT/renders
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_suit.py      # needs `workflow.py characters` once
$B -b --factory-startup --python-exit-code 1 --python src/wayfarer/presentation/accessory_scene.py -- --out $OUT/scenes
```

The drone build takes about 15 s and the draft renders under a minute on 4 CPU cores (cloud session, Blender 5.2.2). Assets:
`assets/drones/WF_DRONE_<ID>.blend` (local, ignored), GLBs in the run folder. The 2026-10-24 review package (`runs/20261024T110142Z-accessories`:
GLBs, `drone_bodies.json`, lineups, class views, close-ups, suit turnaround / cutaway / exploded / poses, the interaction scenes) is local
evidence and regenerates with the commands above. A scoped `pipeline --quick` on the branch: ship geometry diff 0.

## Open and HOLD

- All owner physics: mass, power, speed, reach, payload, torque, latch rating, endurance, thermal duty (data `[open]`).
- DGT-017: the bodies are not integrated; the ship keeps its L2 proxies. The exterior bodies are taller than the L2 proxy boxes
  (`proxy_fit` in the screen), so integration means resizing a proxy or dock, never shrinking a body.
- DGT-012: the GU-SIF and cartridge standard are proposals.
- Exterior work: FLIGHT_EVA HOLD; DS-13 operations HOLD while blades are hot; radiator cooldown / view factor OPEN; Brow ram face and
  live drive never.
- Not done yet: Godot use of the GLBs (Godot is not installed in this cloud session); the compact PLSS study (ASSET-10); a glove grasp.

## Interface requests for the ship session (not applied)

1. **DR-IVA-02 deck guide channel** (S&E 51 "retained surface guide"): a recessed guide slot in the ring deck along the rover's service
   path, about 40 mm wide, near the DS-05/07 floor cassettes. Consequence: a floor feature in both rings. Temporary alternative: the
   rover runs unguided inside its sector and parks in the cassette (current proxy behaviour).
2. **L2 drone proxy depth** (`drone_fleet.unit_size`, 0.6 × class for EVA): the candidate exterior bodies measure 0.43–0.52 m tall
   (owner class 0.60–0.70 m). Consequence: dock cradle and keep-out boxes grow by up to 0.16 m. Temporary alternative: proxies unchanged;
   bodies shown only on review stands.
3. **Crawler rail cross-section**: the captive trucks need the rail's support web straight below the rail (posts or a narrow web), so
   the under-wheels pass either side. Consequence: none for the current rod rails; a rule for the detailed rail.
