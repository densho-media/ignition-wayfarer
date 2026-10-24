# Wayfarer EVA suit and guided spacewalk

WAYFARER_EVA_Y155 is the guided-EVA pressure suit of the induction pair, together with the exterior training route it is used on and the
stationary suit-access rooms (TODO EVA-001). The owners and their sources:

- S&E `43_EVA_SUIT_REQUIREMENTS` EVA-001…061 (EVA-040…055 are the owner's EVA-002 answers, EVA-056…061 the EVA-003 ones),
  `44_EVA_SUIT_BLENDER` (ASSET, RIG, ANIM, SIM, EXP, QA, RUN-001…020, EVA2-001…008 and EVA3-001…005) and `45_EVA_ENGINEERING_CASES` (the
  calculation register: P, H, G and O rows, with G-11…G-15 and H-14/H-15 added for EVA-003). EVA-003 also answers 15!A126:A131 (HUM-003,
  ECLSS-REC2, RAD-003, SERV-003, CHAR-STEP2, FUT-003-LOOK) and logs 98!A95:A97.
- Technology `53_EVA_SUIT_SYSTEMS` (the generic science) and Tale `26_GUIDED_EVA` (TOUR-01…11, SCRIPT-05…11: the guide's words).
- Supporting rows: S&E 11!5 (EVA configuration), 12A SP-11…13 and SP-51, 14!6, 14!13…15 and 15 E1…E4.

They were read live on 2026-10-10: the first read (S&E 19:52Z) in
[references/EVA_SOURCES_2026-10-10.md](../references/EVA_SOURCES_2026-10-10.md), the EVA-002 read (S&E 21:39Z, Tale 21:39Z) in
[references/EVA2_SOURCES_2026-10-10.md](../references/EVA2_SOURCES_2026-10-10.md). The formal xlsx capture of all four workbooks is
[references/drive_capture_2026-10-11](../references/drive_capture_2026-10-11/delta.md); the values used here match it, and its new
decision rows (S&E 98!A92:A94, Tale 98!A30) restate the EVA-002 rules. The EVA-003 rows are in
[references/drive_capture_2026-10-11b](../references/drive_capture_2026-10-11b/delta.md) (S&E 08:21Z); the work log is
[references/EVA3_LOG.md](../references/EVA3_LOG.md).

Status: the suit is **PROTOTYPE, NOT CERTIFIED**; the exterior route is a **TRAINING SIMULATION**; **FLIGHT_EVA is HOLD** (locked until a
written owner release, 45 O-07); the SP-11/12/13 geometry is a **STUDY** and not ship geometry. Every physical value the owners have not
released is null (OPEN): suit pressure setpoint and gas, prebreathe, mass, duration, consumables, heat rejection, leak rate, dose, tether
length, ring keep-out, the radiator exposure inputs, debris and radiation limits and the anchor plan. The 40 kPa pure-O₂ case is shown only
as 45's WORKING TRADE CASE. Nothing here is canon. The loop and the rules are in [AGENTS.md](../AGENTS.md).

## Layout

| Concern | Where |
| --- | --- |
| Parameters, assembly tree, OPEN telemetry contract, trade case, thermal inputs, modes, stations, access and room study inputs | `data/eva_suit.toml` |
| Contract, tether protocol, EVA motion sources (pure) | `src/wayfarer/eva_suit.py` |
| Envelope classes, route access, SP-11 door and chamber candidates, SP-12/13 rooms (pure) | `src/wayfarer/eva_access.py` → `references/p1_eva_access.json` |
| Training route, hazard gates, flight state (pure) | `src/wayfarer/eva_route.py` → `wf_eva.json` |
| Generator (Blender) | `src/wayfarer/build/eva_suit.py` → `assets/characters/WF_EVA_<WEARER>.blend` |
| Suit checks and access-pose hulls | `src/wayfarer/validation/eva_fit.py` → `references/p1_eva_fit.json`, `references/p1_eva_envelopes.json`, `renders/p1/eva/fit/` |
| SP-11/12/13 study in the vehicle | `src/wayfarer/validation/eva_airlock_study.py` → `references/p1_eva_airlock.json`, `renders/p1/eva/airlock/`, `runs/<stamp>-eva/WF_EVA_AIRLOCK_STUDY.blend` |
| EVA-003 SP-11 comparison (pure): 1.10 / 1.20 / 1.35 m, inner-hatch mechanisms, extension latch, rescue | `src/wayfarer/eva_sp11.py` → `references/p1_eva_sp11.json` |
| SP-11 1.20 m sliding plug (pure): drop and park, bidirectional retention, two-side valves, interlock table, two-person and casualty re-check | `src/wayfarer/eva_sp11_plug.py` (called by `eva_sp11.study()`, key `sliding_plug` in `references/p1_eva_sp11.json`) |
| Its check in the vehicle with the posed rigs, renders | `src/wayfarer/validation/eva_sp11_study.py` → `references/p1_eva_sp11_vehicle.json` (key `sliding_plug`: real meshes), `renders/p1/eva/eva3/`, `renders/p1/eva/airlock/sp11_120_slideplug_*.png`, `runs/<stamp>-eva/WF_EVA3_SP11_STUDY.blend`; `--plug-only` runs just the plug part (about 40 s) |
| Integrated forward district (SP-11/12/13 with the SERV district) | `src/wayfarer/studies/eva3_district.py` → `references/p1_eva_district.json`, `references/EVA3_DISTRICT_MAP.svg` (run by hand) |
| Renders | `src/wayfarer/presentation/eva_preview.py` → `renders/p1/eva/` |
| Export | `src/wayfarer/export/eva_gltf.py` → `eva_<key>.glb` + `eva_characters.json` |
| Runtime | `godot/scenes/eva.tscn`, `godot/scripts/eva.gd` (opened from the boarding walk) |
| Tests | `tests/test_eva_suit.py`: OPEN stays null, gates fail closed, FLIGHT_EVA locked, Tale stations, no suit on the interior route, leaf clear of every placed body, tether rules, mobility limits, the owner's EVA-003 apertures, no latch-only reverse-load hatch passes |

```bash
python3 tools/workflow.py eva
```

The command builds the suits, checks them, runs the access study and its vehicle check, the EVA-003 comparison and its vehicle check,
renders and exports, and prints a summary. It takes about 12 minutes (`--no-renders` about 7) and needs `workflow.py characters` first. The
district study is run by hand: `/snap/bin/blender -b --python src/wayfarer/studies/eva3_district.py -- --out runs/<stamp>-eva3-district`.

```bash
python3 tools/workflow.py runtime-export
```

This publishes the suits, the route and the access study with the ship and runs the EVA scene's headless check (`--check-eva`).

## Suit

The suit is one assembly sized to each wearer (EXP-03); only the markings differ. Its WORKING look (EVA-052, Tale 26!28): off-white and
grey shell, dark pressure joints, restrained Great Union deep-blue identifiers and a GU plate on the instructor, neutral grey on the
visitor, orange only on the tethers and the emergency actuator. Both wear the existing MPFB bodies, unchanged: the 53-bone `game_engine`
rig, the corrective shape keys and the five shared actions (RIG-02, RUN-006). The collections follow RUN-005:
`WAYFARER_EVA_Y155 / PRESSURE / PROTECTION / JOINTS / HELMET / PLSS / COOLING / TETHERS / TOOLS / MARKINGS / RIG`. Every object carries
`part_id` (`WAYFARER_EVA_Y155/<ASSEMBLY>/<PART>`), `assembly`, `job` and `geometry_status = PROTOTYPE`.

- **Soft layers.** The liquid cooling and ventilation garment (0.006 m), the continuous bladder (0.020 m) and the restraint plus
  thermal/MMOD outer layer (0.034 m) are offset shells of the wearer's own body. Each is smoothed, kept at least 80 % of its offset
  outside the skin, and skinned with the body's weights and correctives. Every existing action therefore drives them, and the pressure
  boundary is continuous by construction. Gloves (0.011 m, the fingers kept) and boot uppers (0.026 m) are regions of the outer layer.
- **Rigid parts, bone-mounted.**
  - Pressure structure: the hard upper torso, lofted from the outer layer's chest sections plus 0.045 m; the waist body-seal ring; the
    neck ring.
  - Helmet: a sealed shell fixed to the torso (the head turns inside it), with a clear pressure visor window, a raised glare visor and an
    identification band.
  - PLSS: a 0.50 × 0.22 × 0.62 m packaging envelope (45 G-08…G-10 MODEL DISPLAY ONLY, EVA-050: no capacity, mass or duration follows
    from it), drawn as two replaceable modules (upper: O₂ storage and regulation; lower: CO₂, fan/pump/separator, battery, radio) with
    an interface band, keyed latches, a heat-rejection vent, side rescue handles, two fastened access panels, umbilical and cooling
    ports and an orange emergency actuator. Its outer form is the old box's, so the measured envelopes are unchanged.
  - Helmet details: visor pivots and two light / camera pods. Its cutaway internals are two primary
    O₂ bottles, the separate emergency reserve, the regulator, the CO₂ cartridge, the fan/pump/separator, the heat exchanger, the battery
    and the radio/telemetry unit.
  - Displays: the chest display and control module, and the left forearm display.
  - Joints: scye, upper-arm, hip, thigh and ankle bearings (flat machined bands with edge races); elbow and knee convolutes (three-rib
    bellows, the outer layer charcoal over the elbow and knee, RUN-017); wrist disconnects; gauntlets.
  - Feet: rigid soles with toe hooks for foot restraints.
  - Tethers and tools: two orange waist tether reels with captive hooks, and an inspection scanner with a lanyard ring.
- **Sockets** (RIG-03/04) are bone-parented empties with stable ids. Hands: `SOCKET_HAND_L_GRIP`, `_R_GRIP`, `_R_TOOL`. Feet:
  `SOCKET_TOE_HOOK_L/R`. Tethers: `SOCKET_TETHER_A/B`. Others: `SOCKET_TOOL_STOW`, `SOCKET_PLSS_SCU`, `SOCKET_HELMET_EYE`, `SOCKET_HUD`.
  No bone is added.
- **Validation body.** The full body stays in the file, hidden, for the coverage check. The exported head (`CHAR_<ID>_Head`) is a copy of
  it with every covered face removed.

Every size is a PROTOTYPE fit choice in `[rigid]` and `[layers]`. No check shrinks the suit (RUN-010).

## Actions

Fifteen EVA actions are written in the shared retarget source format and solved onto each rig by `build/human.py`'s Solver. They are added
as NLA tracks beside the shared ones. All are PROTOTYPE motion and simplified training representations, not EVA procedures.

- `eva_suit_check`: chest display, wrist display, helmet neck-ring lock, glove locks. Feet in a restraint, 12 s.
- `eva_airlock`: panel, then the outer hatch handle. 8 s.
- `eva_translate` and `eva_abort_translate`: hand over hand along a rail at 0.20 and 0.32 m/s. These are display paces, not EVA rates.
- `eva_body_rotate`: from the rail to upright at a hold. One hand always holds.
- `eva_tether_transfer`: hook B to the next anchor, tug, release A. Events are recorded.
- `eva_tool_inspect` and `eva_guide_point`.
- EVA-002, for the access study: `eva_hatch_pass` (head first through a hatch, both hands pulling on the frame ahead in turn, held inside
  the shoulder limit so the hands land ahead of the visor), `eva_buddy_check` (in SP-12, the partner's emergency actuator, tether hooks
  and neck ring), `eva_casualty` (an unresponsive crew member in the relaxed microgravity neutral body posture) and `eva_rescue_hold`
  (the rescuer keeps a handhold and holds the casualty's pack handle).
- EVA-003 (EVA3-002/003): `eva_latch_extension` (feet in the restraint, right hand on a handhold ahead of the waist, the **left** hand
  throws the extension lever ahead of the left shoulder 90° from up to forward, then pulls the outer leaf's strap down from above the brow
  to the chest; left-handed because the two-person layout puts the partner on each crew member's right), `eva_latch_pitch` (backup only:
  the articulating foot restraint pitches the rigid body until the arm reaches straight up within the shoulder limit; on the rigs that
  takes **70°**, not the 60° the EVA-002 estimate gave) and `eva_casualty_supported` (an incapacitated crew member secured for transport:
  the supine spinal-neutral stretcher posture, body straight, arms along the sides, legs together, nothing bent or squeezed).

The travel actions are authored in place and record `travel_speed_m_s`; the runtime moves the body at that speed. A gripping hand closes
its glove (finger flexion keys). The `[mobility]` limits are PROTOTYPE pressurized-joint ranges (elbow ≤ 115°, knee ≤ 95°, shoulder flexion
≤ 120°, head turn inside the helmet ≤ 20°). They keep the actions inside a suited body's reach: a wrist target that would fold the elbow
further is stopped short. Joint torque is OPEN (EVA-033).

The interior `crawl` and `climb` are never played on a suit: the crawl takes the head out of the torso-fixed helmet. The hold actions use
a work-site handhold on a short stanchion at hip height beside the rail, a PROTOTYPE training fixture drawn by the runtime.

## Checks (`references/p1_eva_fit.json`)

**Pressure continuity** (ASSET-03). In every 6th frame of every action, each covered skin vertex must lie under the outer layer: a ray
along the posed skin normal hits it within 0.12 m, or, in a fold, the nearest shell surface faces away or an axis ray crosses the shell an
odd number of times. The head must also stay inside the helmet.

- All fifteen EVA actions, and the shared `idle`, `walk` and `sit`, pass for both suits.
- The shared `crawl` fails: the interior crawl's 35° head lift takes the head out of the torso-fixed helmet (208 and 264 vertices). The
  instructor's shared `climb` fails for 8 vertices by 2.5 mm. Interior motion is not suit motion (EVA-040/041).

**Torso envelope** (RUN-010, 45 G-01/G-02). The suited torso cross-section with the PLSS, arms along the body, about its bounding-box
centre: 0.64 × 0.80 m and a 0.91 m circle for the instructor (1.78 m), 0.60 × 0.77 m and 0.885 m for the newcomer (1.70 m). These are the
owner's quoted figures; the access study below measures the smallest circles.

**Holds in the vehicle** (QA-02). The suited bodies posed at the training route's five holds are CLEAR of the vehicle meshes, with
0.035–0.082 m least clearance. Renders are in `renders/p1/eva/fit/`.

Passing checks are not certification (EVA-033, QA-03, EVA-049).

## Suited access (EVA-002: 43 EVA-040/041, 44 EVA2-002)

The owners' direction: the induction is shirt-sleeve; the instructor and the visitor don their suits in **SP-12 beside SP-11** on the
stationary structure; **SP-13** services them; **no routine suited transit through ring B**. Ring B's ports are not widened.

**Envelope classes** (`eva_access.classes`, measured on the as-built suits' convex hulls in each access pose; `p1_eva_envelopes.json`):

| Class | Use | Instructor | Newcomer |
| --- | --- | --- | --- |
| UNSUITED | interior induction; the legacy 0.70 m key is its route-control envelope | 0.658 m (arms along the body) | 0.602 m |
| EVA_SUITED | SP-12 → SP-11 → exterior only: smallest passage circle, arms along the body | 0.857 m, 1.92 m long | 0.832 m, 1.83 m long |
| EVA_OPERATIONAL | hatch passage with the hands ahead; panel and handle work | 1.074 m; 1.217 m | 1.026 m; 1.168 m |
| RESCUE | a limp casualty (neutral body posture, best of 0–30° tilts); a rescuer holding it | 1.299 m; 1.133 m | 1.221 m; 1.088 m |

The legacy key `human_entry.mannequin.suited_envelope_diameter_m` (0.70 m) keeps its name for compatibility (EVA-041: no silent
migration; the interior route checks are unchanged) and is classified as the UNSUITED route-control envelope: it is never an EVA suit
envelope. The fit check's bottleneck rows now name the interior route shirt-sleeve.

**Route access** (`p1_eva_access.json` `route_access`): every interior bottleneck is NOT A SUITED ROUTE for the suited classes; the
geometry is still reported. Ring B's 0.90 m port: UNSUITED CLEAR; EVA_SUITED BLOCKED for the instructor (−0.009 m on the owner's torso
circle, 45 G-04) and CLEAR by 0.015 m for the newcomer (G-05, not usable); EVA_OPERATIONAL and RESCUE BLOCKED for both.

The SP-12 entrance from the trunk is the existing airlock branch (`Crew_Connector_Airlock_EVA`, a PROTOTYPE solid rod): taken
shirt-sleeve, its hollow passage is not built yet.

## SP-11 door and chamber study (43 EVA-043/044, 44 EVA2-003)

Six disposable candidates on the existing PROTOTYPE airlock axis (X 101.85 m, 50°): clear apertures 1.00, 1.10 (the 45 G-06 study
target) and 1.20 m, each as a two-person chamber and as a sequential single-person chamber. Nothing is cut into the ship (EVA-043).

**Method** (`eva_access.candidates`):
- The doors are the docking port's plug-leaf family (`[human_entry]`): leaf = aperture + 0.05 m overlap, hinge 0.10 m outside the
  aperture, 0.06 m leaf, 90° opening. Both seat from the high-pressure side: the outer leaf opens into the chamber, the inner leaf into
  SP-12.
- **Door passage**: the smallest circle of each pose's hull projected along the body axis, against the aperture with a 0.05 m PROTOTYPE
  margin (MARGINAL below it, FAIL below zero). The suited pose and a restrained casualty (limbs strapped by the rescuer: a PROTOTYPE
  assumption, strap hardware OPEN) are required; the free neutral-posture casualty is reported.
- **Chamber**: the two bodies stand head outboard side by side (the arrangement with the smallest enclosing circle, 0.05 m apart); the
  clear radius holds them and the parked outer leaf. The two-person chamber is sized for the routine pair and both rescuer/casualty
  pairings. The clear length is the shortest that keeps every body 0.05 m clear of the outer leaf's full swing (convex-hull planes against
  sampled leaf positions, the best of eight hinge azimuths), plus both frames.
- **Radial budget**: the chamber's outboard bulkhead stays 0.15 m inside the hull skin (as the docking port's), and the inner leaf's swing
  must stay above the SP-12 floor.
- **Operator reach**: from 0.15 m under the shut outer leaf, a shoulder must be within the measured suited reach (shoulder to wrist plus
  the palm) of a handle placed nearest it on the leaf; the elevation above the shoulder limit is reported as the pitch the body needs.
- **Structure** (`eva_airlock_study.py`, in the saved vehicle): every candidate's chamber, bulkheads, outer neck and leaves against all
  vehicle meshes within 7 m, at the 0.15 m mechanical clearance.

**Results** (`references/p1_eva_access.json`, `p1_eva_airlock.json`; renders `renders/p1/eva/airlock/`):

| Candidate | Chamber clear Ø × length, volume | Door passage (hands ahead) | Radial budget to SP-12 floor | Structure | Status |
| --- | --- | --- | --- | --- | --- |
| two-person 1.00 m | 2.00 × 3.15 m, 9.9 m³ | FAIL both (−0.074 / −0.026 m) | +0.31 m | CLEAR (≥ 0.31 m) | STUDY FAIL |
| sequential 1.00 m | 1.90 × 3.15 m, 8.9 m³ | FAIL both | +0.31 m | CLEAR | STUDY FAIL (+ no rescue) |
| **two-person 1.10 m** | **2.00 × 3.25 m, 10.2 m³** | instructor MARGINAL (+0.026 m), newcomer PASS (+0.074 m) | +0.11 m | CLEAR (≥ 0.31 m) | **recommended for owner review**, one MARGINAL |
| sequential 1.10 m | 2.00 × 3.25 m, 10.2 m³ | as above | +0.11 m | CLEAR | STUDY FAIL (no rescue) |
| two-person 1.20 m | 2.10 × 3.35 m, 11.6 m³ | PASS both (+0.126 / +0.174 m) | −0.09 m | CLEAR (≥ 0.29 m) | STUDY FAIL (inner leaf below the SP-12 floor) |
| sequential 1.20 m | 2.10 × 3.35 m, 11.6 m³ | PASS both | −0.09 m | CLEAR | STUDY FAIL (+ no rescue) |

What the numbers say:
- **The hatch leaf, not the bodies, sizes the chamber diameter.** The routine pair and the rescue pairs side by side need 1.86 m; the
  outer leaf parked at 90° needs 1.96 m at 1.10 m. A two-person chamber is no wider than a single-person one at 1.10 and 1.20 m, so the sequential
  layout saves nothing there and cannot cycle a casualty (EVA-044, EVA-054).
- **The leaf swing sizes the length.** The bodies stand 0.93–1.13 m under the shut outer leaf so that its swing clears their helmets;
  rescue adds 0.05 m.
- Every chamber fits inside the existing 2.2 m PROTOTYPE fitting tube (2.0–2.2 m outside) and every neck (1.3–1.5 m) inside its hull
  opening, so no candidate conflicts with the ship's structure; the nearest neighbours are the hull skin (0.29–0.35 m) and shield keel 1
  (0.48–0.57 m).
- A free limp casualty needs 1.22–1.30 m: no candidate passes one without restraint.
- **Unlatching is overhead**: the handle is within reach (0.57 m against 0.62 m for the instructor, 0.56 against 0.58 m for the
  newcomer) but straight above the shoulder, 60° beyond the suited shoulder limit: the operator pitches toward the hatch, or the hatch gets
  an extension handle or a powered latch (OPEN).
- Derived seat loads at the 80 kPa cabin (BASELINE × leaf area, not a structural release): 76, 90 and 106 kN.

The owner did not accept the EVA-002 recommendation (`two-person 1.10 m`): it is the MARGINAL benchmark now (43 EVA-056, 45 G-11), and
EVA-003 below leads with 1.20 m. EVA-003 added 1.35 m to this sweep (two-person 2.40 × 3.50 m, sequential 2.40 × 3.45 m; both STUDY FAIL
on the hinged inner leaf, −0.44 / −0.39 m).

## SP-11 EVA-003 comparison (43 EVA-056…058/061, 44 EVA3-001…003, 45 G-11…G-15)

The owner's direction: 1.10 m is the MARGINAL benchmark (instructor hands-ahead +0.026 m < 0.05 m, G-11); lead with a **two-person 1.20 m**
chamber after fixing its inner-leaf intrusion (G-12, G-13); compare **1.35 m** for the free limp casualty (1.30 m + 0.05 m, G-14); an
accessible manual extension or remote latch with an independent emergency release, powered assist optional (EVA-057); medically supportable
full-length casualty support, never a forced posture (EVA-058). All of it disposable study geometry (EVA-061). `eva_sp11.py` measures,
`validation/eva_sp11_study.py` puts it in the vehicle with the posed rigs.

**The chamber is sized for every rescue case now.** EVA-002 sized it for the routine pair and the free limp pairing. A casualty secured on a
full-length litter frame (rails 0.04 m off the suit, 0.10 m past the helmet and 0.05 m past the boots) is longer, and a vacuum mattress
adds 0.06 m all round, so the EVA-003 chambers are 0.15–0.25 m longer:

| Aperture | Role | EVA-003 chamber (EVA-002) | Volume | Length set by | Fitting / hull opening | Shell, PROTOTYPE mass |
| --- | --- | --- | --- | --- | --- | --- |
| 1.10 m | MARGINAL benchmark (G-11) | 2.00 × 3.50 m (2.00 × 3.25) | 11.0 m³ | litter frame | 2.1 m in the 2.2 m tube / 1.40 m | 30.0 m², 0.60 t |
| **1.20 m** | **lead study (G-13)** | **2.10 × 3.55 m (2.10 × 3.35)** | **12.3 m³** | litter frame | 2.2 m, exactly the tube / 1.50 m | 32.1 m², 0.64 t |
| 1.35 m | rescue comparison (G-14) | 2.40 × 3.70 m (2.40 × 3.50) | 16.7 m³ | vacuum mattress | **2.5 m: a larger fitting** / 1.65 m | 38.9 m², 0.78 t |

Shell mass is the SERV-002 PROTOTYPE 20 kg/m² (no frames, hatches or MMOD); the cycle gas is a Sheets item. Every chamber, neck and leaf
is CLEAR of the ship at the 0.15 m mechanical clearance (nearest: the hull skin 0.28–0.31 m, shield keel 1 0.33–0.52 m).

**Door passage, every pose** (smallest circle along the body axis, best of 0–30° tilts for a casualty; margin to the aperture, instructor /
newcomer; PASS ≥ 0.05 m):

| Pose | 1.10 m | 1.20 m | 1.35 m |
| --- | --- | --- | --- |
| suited, arms along the body | +0.24 / +0.27 | +0.34 / +0.37 | +0.49 / +0.52 |
| suited, hands ahead (hatch passage) | **+0.026 MARGINAL** / +0.07 | +0.13 / +0.17 | +0.28 / +0.32 |
| casualty, free limp (unrestrained) | −0.20 / −0.12 FAIL | −0.10 / −0.02 FAIL | **+0.05 / +0.13 PASS** |
| casualty secured, straight (no support) | +0.24 / +0.27 | +0.34 / +0.37 | +0.49 / +0.52 |
| casualty on the litter frame | +0.24 / +0.27 | +0.34 / +0.37 | +0.49 / +0.52 |
| casualty in a vacuum mattress | +0.12 / +0.15 | +0.22 / +0.25 | +0.37 / +0.40 |
| casualty on the frame with a med/O₂ kit | +0.09 / +0.11 | +0.19 / +0.21 | +0.34 / +0.36 |

1.20 m passes every routine pose with margin; the free limp posture needs 1.35 m (instructor +0.051 m, just over the study margin). A
casualty secured supine on a frame, in the stretcher posture of spinal immobilization, passes every aperture.

**Inner hatch** (G-12: the inner leaf swung into SP-12). Five mechanisms, radial budget = the mechanism's lowest point to the SP-12 floor
(r 1.25 m) including the 0.05 m swing clearance:

| Mechanism | 1.10 m | 1.20 m | 1.35 m | Pressure | Verdict |
| --- | --- | --- | --- | --- | --- |
| plug leaf hinged into SP-12 (EVA-002) | −0.14 | −0.29 | −0.64 | seated | FAIL at every aperture once the chamber holds the litter |
| the same over a floor well (utility layer removed, floor to the spine clearance 1.10 m) | +0.01 | −0.14 | −0.49 | seated | 1.10 m only, with no margin left |
| **parallel-linkage plug: drops 0.08 m off its seat, slides sideways in the bulkhead plane** | **+0.93** | **+0.88** | **+0.68** | **seated, no seal scrub** | **PASS at every aperture** |
| plug hinged into the chamber | −0.08 | −0.23 | −0.58 | unseated: 91 / 106 / 132 kN on the latches alone | REJECTED (15!G127) |
| bi-parting half leaves | +0.46 | +0.36 | +0.09 | a mullion (no suited body passes a half) or a latch-only seam | REJECTED |

The parallel plug (aircraft / bus plug-door kinematics) needs a parking pocket one leaf wide beside the aperture. Checked in the vehicle:
+X meets the SP-12 donning stands and buddy zone, −X the SP-45 storeroom, +az leaves SP-12's 75° bound; **−az is clear** of the ship and
of every fixture once the tool and tether checkout board moves to SP-12's aft wall (done in `[sp12]`); at 1.35 m that pocket leaves
SP-12's 5° bound. The derived seat loads at the 80 kPa cabin are 91, 106 and 132 kN (BASELINE × leaf area; no structural release).

**Extension latch** (EVA-057; the rigs' own suit meshes, every sampled frame of the lever throw and the strap pull):

| | 1.10 m | 1.20 m | 1.35 m |
| --- | --- | --- | --- |
| lever station (pivot ahead of the left shoulder) wall bracket | 0.20–0.22 m | 0.25–0.27 m | 0.40–0.42 m |
| suit to the chamber wall | 0.053 m | 0.103 m | 0.253 m |
| suit to the partner | 0.167 m | 0.167 m | 0.167 m |
| suit to the outer leaf's swing | 0.108 m | 0.105 m | 0.107 m |
| shoulder flexion (limit 120°) | 111.6° | 111.6° | 111.6° |
| torque tube up the wall to the latch drive / strap from the leaf | 1.7–1.8 / 1.22 m | 1.8 / 1.30 m | 1.9–2.0 / 1.42 m |
| backup: body pitched 70° in an articulating foot restraint | needs 1.72–1.80 m of radius: FAIL in every chamber | | |

The latch dogs are frame mounted, so the linkage never crosses the hinge. The operator unlatches and opens the outer hatch from the
routine standing position, below the leaf's sweep (EVA-002's 0.15 m under-the-leaf unlatch position goes away). Redundancy: each crew
member has a lever (two independent linkages to the same dogs) and an independent pull-cable release retracts the dog pins; an external
handle serves a returning crew; a motor on the linkage with a clutch is optional and never the only way (EVA-057). A mechanical door
interlock and a Δp interlock pin on the lever train need no power; the latch force at the release Δp and the threshold are OPEN.

**Rescue** (EVA3-003). The EVA-003 chamber holds the casualty in each secured case beside the rescuer (rig meshes: rescuer ↔ casualty
0.11–0.17 m, litter to the wall ≥ 0.22 m, all ≥ 0.10 m below the leaf's sweep):

| Case | 1.10 m | 1.20 m | 1.35 m |
| --- | --- | --- | --- |
| full-length supported (litter frame) | PASS | PASS | PASS |
| unrestrained limp | FAIL | FAIL | PASS |
| limbs secured, no support | PASS | PASS | PASS |
| vacuum mattress | PASS | PASS | PASS |
| with a med/O₂ kit | PASS | PASS | PASS |
| patient and assisting astronaut in the chamber | PASS | PASS | PASS |
| no electrical power | manual levers, strap, valves and interlock reachable from the routine positions; valve sizes, equalization time and gas: OPEN | | |

Beyond SP-11 the casualty leaves SP-12 through the existing 0.90 m trunk branch. Straight through it a litter casualty clears by only
0.043 m (instructor) / 0.068 m (newcomer); the **turn from the branch into the trunk** decides it (HUM-003,
[references/HUM003_CASUALTY_ROUTES.md](../references/HUM003_CASUALTY_ROUTES.md)): the suited litter casualty FAILS by 0.093 m at 0.90 m and
is only MARGINAL (+0.009 m) at 1.10 m. **There is no passing casualty way out of SP-12 yet** (OPEN; from the trunk on, the HUM-003 hoist
serves it).

Every inner-hatch option also carries a reverse case (ECLSS-REC2, [references/ECLSS_REC2_CLOSURES.md](../references/ECLSS_REC2_CLOSURES.md)):
if SP-12 loses pressure while the chamber is at cabin pressure, the inner closure is loaded off its seat (91 / 106 / 132 kN), so the
parallel plug needs a bidirectional rating or a second closure (`sp12_loss_reverse_kn` in `p1_eva_sp11.json`).

**Direction for owner review (not a release).** 1.20 m two-person, 2.10 × 3.55 m, with the parallel-plug inner hatch parked −az and the
wall-lever extension latch: every routine pose passes, every secured rescue case passes, the hatch hardware fits the existing 2.2 m
tube, and nothing touches the ship. Its limit is the unrestrained limp casualty (−0.10 m); that one needs 1.35 m, which needs a 2.5 m
fitting and a 1.65 m hull opening (an owner change). Open: the seal and latch structure, the plug linkage loads, Δp latch force, the gas
cycle, pump duty and wall, and the medical acceptance of the litter.

### SP-11 1.20 m sliding plug (owner direction 2026-10-11: S&E 15!A134 AIRLOCK-004, 43 EVA-062, 45 I-01…I-04)

STUDY DIRECTION ACCEPTED / STRUCTURAL FLIGHT RELEASE HOLD, pressure flight HOLD. A **NONCANON integrated study** of the 1.20 m aperture in the
existing 2.2 m tube; nothing is a rating, a certified seal or latch, a hull cutout or a gas cycle. Values in `[sp11_plug]` of
`data/eva_suit.toml`; geometry in `eva_sp11_plug.py`; the Blender check measures the real suit meshes. Report:
[references/EVA3_REPORT.md](../references/EVA3_REPORT.md) §11.

- **Kinematics.** The 1.20 m leaf lies on the SP-12 face of the frame. Its dogs retract, it drops 0.08 m along the seat normal (−a), then slides
  1.30 m toward −az on two rails and a carriage and parks beside the aperture (the parked-leaf edge 0.05 m off the bore). The swept envelope
  stays below the inner bulkhead (0.08 m) and clears every body (≥ 0.27 m), the SP-12 room (0.09 m), its fixtures (0.24 m) and the vehicle.
- **Retention in both directions.** Seat-side pressure (SP-12 high) seats the leaf on the face seal on the frame lip. The reverse load (chamber
  high or an SP-12 loss) is held by 12 radial dogs bearing on keeper ledges: 98.2 kN DERIVED / DIAGNOSTIC from the seal-line effective diameter
  (1.25 m) × 80 kPa, against the 106 kN readback, which is the leaf outer diameter (1.30 m: 106.2 kN) bound. The dog faces are normal to the axis, so
  the pressure has no component on the retraction; a drafted face is self-locking (tan 2° < 0.15); the dog cam locks over centre on a stop and two
  blocking pins hold it: the lever linkage is not a load path. The 0.08 m stroke leaves 0.04 m under the keeper lugs (dog 0.02 + ledge 0.02), MARGINAL.
- **Controls.** A manual equalization valve, a dial gauge and an emergency release (pull ring) on a plate 0.06 m proud of the wall: one cluster per crew
  position in the chamber (no single wall point is in both reaches), one on the chamber's outside wall in SP-12. Chamber side: reach margin ≥ 0.09 m
  (suited, unsuited, rescuers), body gap 0.10 m. SP-12 side: MARGINAL (reach 0.007 m for the suited newcomer's gauge; the operator stands 0.00–0.01 m from
  donning stand A; the buddy zone is overlapped by design).
- **Interlock table** (data, `eva_sp11_plug.interlock` / `permits`): unlatch only with |Δp| inside the threshold and the other closure confirmed; the
  threshold is an input and stays **OPEN** (fail closed). 0.05 kPa is 45 I-01 (study only), 50 N is the 45 I-03 lever-force target (actual OPEN),
  56.55 N is the 45 I-02 ideal Δp·A diagnostic at the 1.20 m circle (not a handle force).
- **Re-check at 1.20 m** with the pocket, the controls and the contour-following straps: routine pair, limbs secured, litter frame and vacuum mattress
  PASS; litter with a kit MARGINAL (aperture 0.036 m); the unrestrained limp casualty FAILS (door −0.099 m, as EVA-003) and was re-checked at 1.35 m
  (door +0.051 m, MARGINAL). Loose 0.25 m strap tails cut the aperture margin by up to 0.09 m (stow the tails). A vertically inserted litter stops
  1.4–1.5 m in (it is 2.0–2.1 m long): turning it in SP-12 is not modelled (OPEN, HUM-003).

## SP-12 and SP-13 (12A SP-12/13, PROPOSED / PROGRAM)

PROTOTYPE annular-sector rooms around the spine on the airlock's side of the forward collar (`[sp12]`, `[sp13]`), floor 1.25 m from the
axis (spine 0.95 + 0.15 clearance + 0.15 floor), ceiling 4.60 m (under shield keel 1), azimuth 5–75° (clear of survival reserve 1):

- **SP-12, EVA preparation**, X 100.75–104.85 m, 3.35 m clear height, about 49 m³. The SP-11 chamber rises through its outboard part and
  its inner hatch opens into it. Fixtures: two suit donning stands, the leak/pressure-check panel, the oxygen preparation interface (no
  duration or flow), the tool and tether checkout board with a tug-test fixture (on the aft wall since EVA-003, clear of the inner
  plug's parking pocket), and the buddy-check zone for two suited bodies.
- **SP-13, suit service**, X 104.95–107.10 m, about 26 m³: the drying and storage rack for two suits, the charging, O₂ recharge and
  consumables exchange panel (capacities OPEN), the pressure-shell inspection and component bench, and the spares lockers.

Measured in the vehicle: both rooms CLEAR (nearest survival reserve 1 at 0.17 m, keel 1 at 0.22 m, the forward mount at 0.23 m), every
fixture clear of the vehicle, of the SP-11 chamber and of the inner leaf's swing. No hardware capacity, mass or operating time is
modelled.

## Forward district: SP-11/12/13 with the service district (44 EVA3-004, 15!A129 SERV-003, 98!A96)

The owner's rule: one spatial allocation, no double booking of stationary volume, EVA access and protected rescue first (EVA-059 H60).
`studies/eva3_district.py` puts the SP-11 lead chamber, SP-12, SP-13, the trunk branch and the SERV-002 district (workshop, sealed cell,
SP-52 warm module, access passages) on one overlay in the vehicle; nothing is saved (`references/p1_eva_district.json`, the X-azimuth map
[references/EVA3_DISTRICT_MAP.svg](../references/EVA3_DISTRICT_MAP.svg)).

| Layout | What | Result |
| --- | --- | --- |
| L0 as proposed | SP-12/13 (5–75°) and SERV-002 A (workshop + cell 60°, warm module 240°) independently | **FAIL: 17.6 m³ double-booked** (SP-12 × workshop 8.2, SP-13 × workshop 7.5, SP-12 × cell 1.8, SP-13 × cell 0.15 m³) |
| **L1-A EVA first** | EVA rooms kept; the workshop and cell turned to **240°** behind the A trunk extension (clear angles with the EVA rooms in place: 240, 250, 290, 300°); the SP-52 warm module at **210°, X 106.3–107.9 m** (no angle is free at its old station: survival reserve 2 closes 80–220°, the workshop and the EVA rooms the rest) | **PASS**: no shared volume, every element clear of the ship and inside the hull; warm feed 30.2 m straight to Warm_Panel_3M_3 (routing OPEN); new shell 270 m², 5.4 t PROTOTYPE |
| L1-B fallback | the same with the external corridor B (a 0.90 m trunk port at X 101.85 m, 240°, and a 1.2 m corridor) | PASS; 278 m², 5.6 t |

Pressure topology of L1-A (each its own compartment): trunk; SP-12 behind the branch hatch (seats from the trunk side, so a SP-12 leak
holds it shut); SP-11 between the parallel-plug inner hatch and the outer plug; SP-13 behind the SP-12/13 door; the district passage
behind the district hatch at the trunk end; the workshop behind its port; the sealed cell (pass-through and glove ports, its own vent to
space); the non-habitable SP-52 (robot first, crew only after cooldown). Service connections per room are listed in the JSON.

Access and egress:
- **Shirt-sleeve way in**: the existing `Crew_Connector_Airlock_EVA`, opened as a 0.90 m passage from the trunk (r 0.80 m) to the SP-12
  floor (r 1.25 m). Shirt-sleeve crew clear it by 0.24–0.30 m. A suited casualty on a litter clears it straight through by only 0.043 m
  (instructor) / 0.068 m (newcomer), and the turn into the trunk FAILS (−0.093 m; +0.009 m at 1.10 m, HUM-003); a free limp casualty does
  not pass (−0.40 / −0.32 m). This is the rescue route's blocking point after SP-11.
- **Under 1.5 g aft-down** (X vertical): the trunk ladder ends at X 98.61 m, so reaching the branch sill (X 101.40 m) needs a 2.8 m
  ladder extension up the trunk (part of SERV-002's 5.0 m); the branch is a horizontal crawl 0.65 m above the SP-12 floor; SP-13 is a
  4.2 m climb up an internal ladder through a door in SP-12's forward wall. EVA itself is drive-off, so the chamber is not used under
  thrust.
- **SP-13 has one way out (through SP-12).** A second one: carry the A extension on to X 106.9 m and open a 0.90 m port up into SP-13's
  floor at X 106.0 m; clear of the ship at every SP-13 azimuth tried (15–65°), but the spine bore's contents and cut are OPEN.

Volumes (sampled): SP-12 47.9 m³ gross (the chamber rises through it), SP-13 25.2, the SP-11 chamber 13.7 with its walls, workshop 26.6,
cell 3.3, warm module 5.0 m³. Gas and mass budgets belong to the Sheets.

## Training route, gates and modes (43 EVA-045…049, 45 H and O rows)

`eva_route.py` builds the route from the ship spec. The rail runs on the stationary forward collar along the airlock's 50° azimuth, 0.15 m
off the skin, from X 95.6 m to 106.0 m, with anchors every 1.5 m (an animation/UI fixture, EVA-048). Holds: `airlock`, `rail_mid`,
`aft_hold` and `forward_hold`.

**Modes** (EVA-049): `TRAINING_SIMULATION` is the only available mode; every hold is SIMULATION_ONLY. `FLIGHT_EVA` is a separate state,
**HOLD** and unavailable (45 O-07 LOCKED UNTIL RELEASE); no software result changes it (EVA2-008).

**Gates** (each hold; training status PASS / UNKNOWN / FAIL; flight state in EVA-049's UNKNOWN / HOLD / PROTOTYPE / VALIDATED, never
VALIDATED here):

| Gate | What is measured | Training | Flight | Needs |
| --- | --- | --- | --- | --- |
| drive | EVA config drive OFF | PASS | PROTOTYPE | necessary, not sufficient (EVA-045) |
| ring | static axial gap from the suited sweep to ring B's rotating sweep | UNKNOWN | HOLD | dynamic margin with tethers, tools, vibration, damaged rotor, rescue (EVA-046, O-05) |
| thermal | blade faces in line of sight: blade 1 fully at 18–29 m, blade 2 54–72 % | UNKNOWN | HOLD | H-05…H-11: view factor, projected area, absorptivity, cooling, metabolic and other heat; blade T(t) after shutdown (EVA-045) |
| debris | inside the shield silhouette | UNKNOWN | HOLD | local flux and velocity; never at 0.016c (EVA-047, O-04) |
| radiation | — | UNKNOWN | HOLD | SPE forecast, dosimetry, refuge return (EVA-047, O-04) |
| tether_anchor | — | UNKNOWN | HOLD | crew-rated anchors and loads, tether length (EVA-048, O-05, O-06) |

Geometry readbacks for the owner's thermal model (never a gate input): a view factor from a small sphere at each hold to the visible blade
faces (0.007–0.015; `view_factor_readback`, not 45 H-05) and the suit's convex silhouette area over all view directions (0.47–1.28 m²
instructor, 0.43–1.18 m² newcomer; `projected_area`, for H-06).

Hazardous hardware is shown remotely (EVA-030/031, Tale 26!16): the ring sweep from the aft hold, a crawler camera along blade 1, a remote
view of the drive section, and a camera ahead of the Brow and EYE.

## Runtime (Godot)

Open it with **Guided EVA (training simulation)** in the boarding walk, or directly as `res://scenes/eva.tscn`.

**Phases.** PREP (suit check and buddy check in the SP-12 study room) → LOCK_CHECK (in the EVA-003 lead study chamber, 1.20 m, standing
as the study placed the pair; the parallel-plug inner hatch drawn parked or seated, the two wall lever stations in red; OPEN items
listed) → DEPRESS (the inner hatch seals first; the instructor works the wall lever and the strap, `eva_latch_extension`) → EXTERIOR → REPRESS (the outer hatch seals first) →
DEBRIEF (back in SP-12). There is no clock for depress or prebreathe.

**Stations.** Seven What / Why / Show me stations carry Tale's SCRIPT-05…11 lines verbatim (WORKING SCRIPT), with Tale's safety rule:
suit preparation (PREP), airlock operation (LOCK_CHECK, DEPRESS), the rings, heat rejection and the drive (aft hold), the Brow and EYE
(forward hold), and the return (REPRESS, DEBRIEF). Show me steps the suit cutaway, shows the two-door interlock state, or switches to a
remote view.

**Banner and HUD.** The banner shows the mode, the hold's training status, FLIGHT_EVA: HOLD and each gate's training status and flight
state. The HUD lists every telemetry field with its status, OPEN where unreleased, and the 45 trade case labelled as a study case
(40 kPa absolute, O₂ fraction 1: not a setpoint, no prebreathe, no duration). Nothing is consumed or counted down.

**Controls.** W and S move along the rail at the display pace (Shift: review pace), clamped by the tether reach (2.0 m of gameplay
tuning; the tether length is OPEN). T clips the free tether, Y tug-tests it, R releases the older one (refused unless the other is clipped
and tested). X aborts: the body returns anchor by anchor to the hatch and the chamber repressurizes. 1, 2 and 3: What / Why / Show me; N:
next topic at the hold. K toggles the ring keep-out volume, V the helmet-eye camera.

**Story boundary.** Neither the instructor nor the visitor is one of the six crew; both leave before First Ignition (S004D). The
instructor's name, gender, face and casting stay OPEN (WTF-16).

**Headless check** (`--check-eva`, run by `runtime-export`): nothing GO, no OPEN-limit gate passes and no gate is VALIDATED; FLIGHT_EVA is
HOLD and unavailable; OPEN telemetry stays null; seven stations, each with its Tale script; the access study is present, and the EVA-003
lead is shown with the parallel-plug inner hatch (no rejected mechanism); both suits load
with every EVA clip and socket; the airlock interlock holds; the tethers never drop to zero from the hatch to the aft hold; an abort from
the aft hold reaches the airlock on tethers and repressurizes.

**Performance** (EXP-02, `references/p1_eva_perf.json`). Measured on the reference RTX 3070 (Compatibility renderer, OpenGL 3.3, window
1280 × 800, VSync off, 600 frames per view after a warm-up), the six views with and without the suited pair:

| View | Mean frame with suits | p99 | Without suits | Suits add | Draw calls (max) |
| --- | --- | --- | --- | --- | --- |
| prep (SP-12, rooms and ship) | 5.65 ms (177 fps) | 7.22 ms | 5.19 ms | 0.46 ms | 2,544 |
| exterior (rail) | 2.75 ms (363 fps) | 3.92 ms | 1.85 ms | 0.90 ms | 471 |
| aft hold | 2.76 ms (363 fps) | 4.00 ms | 2.13 ms | 0.63 ms | 533 |
| radiator feed | 3.05 ms | 3.99 ms | 3.18 ms | — | 1,213 |
| forward (Brow/EYE) feed | 6.55 ms (153 fps) | 9.30 ms | 5.77 ms | 0.78 ms | 2,063 |
| suit cutaway | 6.72 ms (149 fps) | 8.63 ms | 5.51 ms | 1.21 ms | 2,075 |

Measured 2026-10-11 with the EVA-003 lead chamber, plug and lever stations in the scene. Scene load 0.36 s, video memory 93 MB. The suits
cost up to about 1.2 ms per frame; against EVA-002 the means moved by 0.0–0.5 ms (cutaway 6.24 → 6.72 ms), within run-to-run spread
plus the few added meshes. The heaviest views are those that see the whole ship, not the suits. Nothing was optimized for this
measurement. Rerun it with `godot --path godot res://scenes/eva.tscn -- --perf
[--no-suits]` after `runtime-export`.

### SP-12 / SP-13 exits and the L1-A bypass (owner direction 2026-10-11: 15!A135 RESCUE-004, 15!A136 DIST-004, 43 EVA-063)

PERFORMANCE REQUIRED / ALL PRESSURE CUTOUTS HOLD; L1-A is the preferred disposable packaging, PRESSURE+MASS OPEN. A NONCANON study
(`studies/eva3_exits.py`; `references/p1_eva_exits.json`, key `owner_2026_10_11` of `p1_eva_district.json`; report
[EVA3_REPORT.md](../references/EVA3_REPORT.md) §12; renders `renders/p1/eva/district/`). Patient + rescuer + kit, not litter only: carrier S (suited casualty
on the frame) and K (litter + kit) with a rescuer at each end, sampled found poses.

- **SP-12 straight exit.** The 0.90 m branch turn (S −0.12 m) and the 1.10 m widening (S −0.04 / −0.01 m) are not approved. The only variant with no turn
  in a narrow place is an **axial slot** 1.10 × 2.50 m over the L1-A extension (carrier lowered without turning): lowering and the aft runs PASS for S and K
  without the fit-out. It still fails at the SP-11-to-SP-12 turn under the bulkhead (S −0.003 m, −0.020 m with the fit-out; K 0.078 / 0.048), at the rescuers
  while lowering (S −0.020 / −0.122), and, with the PROTOTYPE fit-out, at the slot (S −0.070: donning stands share the 1.53 m floor). One more closure
  of 2.75 m² (220 kN ideal at 80 kPa), 2.5 m of spine-core cut, 8.6 m² / 0.17 t. A ≤ 15° oblique duct (1.10 / 1.20 m) is blocked by the vehicle (dock connector,
  store port, refuge, storeroom): clear only from 30°; its sweeps fail for S.
- **SP-13 second exit** (independent of SP-12: no shared closure or volume except the trunk extension as destination): a radial 1.10 m port into the extension
  (to X 107.4 m, +13.4 m²). Without the fit-out: unsuited PASS (0.100 m), K PASS at 45° (0.062) / MARGINAL at 35° (0.034), S MARGINAL (≤ 0.010); 0.90 m fails K and S.
  With the PROTOTYPE rack and bench it fails (the floor is 1.53 m wide). One closure, 76.0 kN ideal.
- **Dock_Primary ladder bypass.** The ladder crosses the r 0.85 m gap as a rigid bridge (1.71 m span, rungs on the 0.30 m pitch, arrest rail resting on the rungs, cheek guard):
  climber to the rim 0.106 m PASS, dock passage kept 0.273 m. Above it the 285° line is blocked by the district port (240°, X 104.1 m): clear only at 305–330°.
  The hoist (0.20–0.25 m toward 105°) is HUM-003's: S attendant gap 0.002 m at 0.20 m. A hoist is for casualty and cargo, not the sole 1.5 g egress.
- **L1-A against B.** 270.3 vs 278.3 m² (5.41 vs 5.57 t); the SP-13 exit and the slot need the extension to 107.4 m (A +13.4 m², B +26.4 m²). Coolant 30.2 m in both.
  SP-52 is 0.30 m from the workshop wall (no barrier released), 1.63 m from the cell; reserve 2 0.51 m from the workshop; no clash in either layout.

## Open

- **Owner values.** Suit pressure setpoint and gas (the 40 kPa O₂ case is a trade case only), prebreathe, consumables and duration, heat
  rejection, leak rate, dose budget, tether length, the ring dynamic margin, the thermal inputs H-05…H-11, debris and radiation limits.
- **SP-11 (EVA-003).** The owner's choice of direction (1.20 m lead with the parallel plug and the wall-lever latch, or 1.35 m with a
  larger fitting); seal, latch and plug-linkage structure; Δp latch force and interlock threshold; the gas cycle, pump duty and wall;
  medical acceptance of the litter; a casualty way out of SP-12 (the branch turn fails; the axial slot still fails the SP-11 turn-in and the lowering rescuers); the inner hatch's reverse rating; SP-13's second
  way out (needs the fit-out to give way); the Dock_Primary ladder bridge and the SP-52 separation (2026-10-11). Sliding plug (A134): the interlock threshold, the lever force, the seal-seat diameter behind the reverse load, the dog and keeper structure,
  the stroke against the keeper lugs, the SP-12-side control station against donning stand A, and the turn of a litter in SP-12.
- **Anchors.** A released exterior rail and anchor plan (SP-51) and alternate stationary, shaded paths (EVA-048).
- **Character and look.** Final markings and the instructor's identity (Tale WTF-16, Art Style, Fashion); face and hair under the helmet.
- **Not built yet.** The compact PLSS study (ASSET-10) and a contact-aware glove grasp.
