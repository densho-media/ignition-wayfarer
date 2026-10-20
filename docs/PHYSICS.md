# Wayfarer local physics

The crew and object physics layer (TODO PHYS-001) moves bodies in microgravity, in the turning rings, under thrust and on a tether.

## Sources and ownership

Owner sheets, captured in [references/drive_capture_2026-10-11c](../references/drive_capture_2026-10-11c/delta.md):
- S&E `46_CREW_DYNAMICS` DYN-001..022 (source record `crew_dynamics`)
- S&E `47_SIM_PRODUCTION` SIM-001..018 (`sim_production`), with S&E `15_MODEL_INTERFACES` A132:A133
- Technology `54_SPACE_MOTION_SIM` GEN-001..013 (`space_motion`)
- Tale `27_CREW_PHYSICS_STAGING` STG-001..012 (`physics_staging`)

The ring and mode numbers come from S&E 08 and 11. The owner answered Claude's physics questions on 2026-10-11 (Doc "OWNER RESPONSE
13:42"; read online, no xlsx capture): `08_ROTATING_HABITAT!A62` ring_sign_convention, 46 DYN-023..027 (A24:J28), 15 CREW-PHYS-004 /
CREW-EVA-004 / CREW-MODE-004 (A141:A143), 43 EVA-065 and 98!A99 (source records `ring_sign_convention`, `owner_release_2026_10_11`).

**The three layers** (SIM-001, DYN-021):

| Layer | Owner | Here |
| --- | --- | --- |
| Scientific state | Sheets | `data/wayfarer_3d.toml` (`[habitat]`, `[configuration.*]`), `simulations/wf_route_v1.json` (NAV-001), FRM-002 channels |
| Local interactive physics | Godot 4.7.2 with built-in Jolt (SIM-002) | `godot/scripts/physics/`, `physics_lab.tscn` |
| Cinematic representation | Blender | `src/wayfarer/shots/physics_traces.py` |

**What is and isn't modelled.** Godot integrates local contact only. Several things stay OPEN, and no game-engine run changes their status:
- No ship trajectory, thrust history, transition time or spin-down profile is solved or invented. Mode transitions are SIMULATION_ONLY and untimed.
- FLIGHT_EVA stays HOLD (DYN-013, SIM-015).
- The casualty route stays HOLD (DYN-020).

## Frames

`crew_dynamics.py` is the reference implementation, and `frame_field.gd` mirrors it. Both read the rig's `dynamics` block (contract 32).

Following GEN-003, a body uses one of two frames at a time, never both:

- **SHIP frame.** It is ship-local and non-rotating, and the ship's attitude rate (not released) is taken as 0. The field is `a = −a_ship`, along −X under thrust (aft down). It is used on the spine, in the despun vestibule, in the airlock and on the EVA exterior.
- **RING frame (Approach B).** It turns with ring k about +X through the ring centre, and the collision geometry is static in it. The field is `−ω×(ω×r) − 2ω×v − α×r − a_ship`, with r measured from the axis.
- **Frame change.** Position and velocity transform together, `v_ring = Rᵀ(v_ship − ω×r)` (`to_ring` / `to_ship`, DYN-009). Reparenting alone is never used.
- **Floating origin.** Local scenes stay in ship metres near the origin. The flight scene keeps the ship at the origin and carries the mission position as a float64 scalar (GEN-001).

**Ring signs.** Ring A (aft, `ROTOR_1`) turns +4 rpm and ring B (forward, `ROTOR_2`) −4 rpm about bowward +X, right-hand rule
(08 ring_sign_convention, OWNER-SELECTED CONVENTION; DYN-023). Coriolis and every frame handoff use these signed vectors.

**Values and statuses:**

| Quantity | Value | Status |
| --- | --- | --- |
| Floor gravity at r 28 m | 0.50097 g | 08, BASELINE/DERIVED |
| Head gravity at 2 m inward | 0.46519 g | 08, DERIVED |
| Coriolis at 1 m/s perpendicular | 0.8378 m/s² (0.0854 g); the sign flips between rings | DYN-003 |
| LOW_THRUST tilt at 0.1 g | 11.29° | DYN-005 |
| HIGH_POWER, rings locked | −1.5 g along X, no radial term | DYN-006/008 |

**Thrust values.** With the drive active, the actual acceleration is a Sheets channel that is still OPEN. The runtime uses the mode's envelope bound (`demo_ship_accel_g`), labelled SIMULATION_ONLY. Where a released route row covers the time, `WfRouteState.ship_accel_mps2` gives the sourced value.

## Runtime (Godot)

- **`project.godot`:** Jolt Physics, default gravity 0, damping 0, 60 ticks per second.
- **`WfFreeBody`:** a RigidBody3D with a custom integrator. It adds the field to the velocity and does nothing else: no gravity, damping or braking. In free flight it evaluates the field at the half step and corrects the position, so a body follows x + vt + ½at².
- **`WfCrewBody`:** the capsule actor, one controller for every scene (lab, body tour, EVA, tethered drill). Its mass, radius, height, reach and test push Δv come from the rig profile (`human_iva`, `human_suited`, `seraph`).
  - **Input:** input selects grab, release and push, never thrust (DYN-016).
  - **Grip:** a joint to a marked `WfHandhold` within reach (DYN-011). Its linear axes lock, so the anchor impulse stops the body.
  - **Push:** an impulse J = m·Δv_test by default (1.0 m/s IVA, 0.3 m/s suited: DYN-024 test speeds, not caps; a caller may give any J), applied at the hand point after release, so an off-centre push spins the body (DYN-010).
  - **Walk:** only on a floor under a field above 0.05 g, as a contact force limited to μN.
  - **Ladder (M2, PROTOTYPE technique):** `on_ladder(v)`. Hand over hand, the hands carry the body at `ladder_v` along a line (the
    climber line, or the M2 access line through the port, the drum and the elbows) and hold its axis along `ladder_up`, in any field. The field still acts, and the hands supply the difference, logged per step as
    `hand_impulse` = m(v_set − v after the field). No hand-load limit is sourced, so the load is measured and never judged.
- **`WfFrames`:** the Blender→Godot axes `(x, z, −y)`, the signed ring ω and the frame changes.
- **`WfModeController`:** the operating modes COAST / LOW_THRUST / HIGH_POWER / DOCKED / EVA (SIMULATION_ONLY, untimed). The ring steps follow the owner's sequence (DYN-026, WORKING scenario / flight event OPEN): `DRIVE_OFF` → `OCCUPANTS_SECURED` → `RINGS_SPIN_DOWN` → `RINGS_LOCKED` → `DRIVE_ON` (and `DRIVE_OFF` → `OCCUPANTS_SECURED` → `RINGS_UNLOCKED` → `RINGS_SPIN_UP` back). A ramp never starts with the drive on (the concurrent ≤ 0.1 g case is unreleased) or with an occupant not secured (`occupants_securable`, lab key O): the transition holds with `hold_reason`, fail closed, until `resume()`. `DRIVE_ON` into a locked mode waits for `RINGS_LOCKED`. A LOW_THRUST request during a ramp is refused "not released". No First Ignition event time. `request(to)` walks the ordered steps of the rig's `transitions["A>B"]`; an unknown mode, a DAMAGED state, a request while busy or a pair missing from the table is refused and logged `{status: SIMULATION_ONLY, refused: true, reason}`. The ring ramp (`spin_ramp`, 1800 s, WORKING, timing OPEN) runs at constant α = ω_full/T, and the controller writes the signed ω, α and the ship acceleration (known 0 with the drive off, else the envelope bound, labelled "not a flight value") into the `WfFrameField`. `advance(dt)` is real time; `skip(s)` advances the ramp clock with the true α (the lab's K key, PROTOTYPE presentation). `can_cross(edge)` follows the PORT_GATE gate: blocked during or before a ring ramp of the running transition, with the drum unsynchronized, or with a closure behind the crosser open.
- **`WfTether`, `WfTetheredBody`, `WfEvaDrift`:** the EVA 3-D drift in `eva.gd` (key F at EXTERIOR). A `human_suited` body in the SHIP frame under mode EVA (field zero) starts at rest relative to the ship on the real exterior: 0.45 m out of the SP-11 outer hatch (`wf_eva.json` `hatch`, forward collar, azimuth 50°) along the collar normal, lying along X (PROTOTYPE posture), gripping the hatch anchor; the tether anchor is that hatch anchor. The drift is collided against `wf_eva.json` `collider` (PROTOTYPE collision proxy from the shared hull formulas via `eva_route.body_radius`, 0.25 m radius samples over x 94–108 m, plus the Airlock_EVA fitting cylinder; built as circumscribed convex frusta, never from the visual mesh), and the six rail anchors are `WfHandhold`s; each rail run (`runs`) is also one graspable rod through its anchors with a thin collider the body can touch (`EVA_RAIL_AFT`, `EVA_RAIL_FORWARD`; the trunk handrail's 0.0175 m section, PROTOTYPE: no exterior rail section is released), and H grabs the nearest handhold or the nearest point of a rod. Space pushes off (|J| ≤ m·0.3 m/s); nothing accelerates or brakes it. The tether (DYN-025 / EVA-065, SIMULATION_ONLY / physical loads OPEN) is a unilateral, inextensible constraint at `tether_reach_m` (2.0 m PROTOTYPE training length; `tether.known = false`): slack, or taut but moving inward, it does nothing; taut and moving outward it applies J = −m(v·n)n inside the integrator step (perfectly inelastic, PROTOTYPE) and puts the body back on the sphere. Every impulse is logged (`impulse_sum`, `peak_impulse`, `events`, anchor id) and −J goes to the anchor; the reported anchor force is the rigid-limit mean |J|/dt, a diagnostic that scales with the timestep because stiffness, damping, the load limiter and the anchor rating are OPEN. States SLACK, TAUT, UNCLIPPED; unclipped means no restraint (a check case only, no key). Two tethers A and B follow the rail protocol (EVA-014, `eva_suit.Tethers`): A starts on the hatch anchor, tested; T clips the free tether to the nearest free anchor within hand reach (one tether per anchor), Y tug-tests it, R releases the older one only while the other is clipped to a different anchor and tested, so live tethers never drop to zero. Both clipped tethers act in the same integrator step, one after the other (PROTOTYPE rigid limit), each logging its own impulses. The thruster (`experimental_thruster`) is off by default and has no key unless on. FLIGHT_EVA stays HOLD and its banner is unchanged.
- **`WfVestibule`:** the DYN-027 rotary vestibule (mirror of `crew_dynamics.vestibule_gate`): two closures (STATIONARY, RING) around a drum. The drum changes speed only with the occupant restrained and both closures shut (a ramp stops if either is lost); a closure opens only when the drum matches that side within the rig tolerance (`dynamics.vestibule.match_tol_rad_s`, from the rotor rpm match tolerance), the other closure is shut and the pressure is shown equalized (`dp_equalized`, threshold OPEN, so unknown refuses). The occupant's (r, v) crosses through `to_ring` / `to_ship` with ω×r. The drill (lab key V) and its check put the occupant at the real drum restraint pose, the hold point of the rig's `dynamics.stages.access` line (X 82.60 m, 1.416 m from the axis, inside the drum annulus 0.975–1.925 m, ring A at the index); a bare reparent there would carry 0.593 m/s of spurious speed. The drum cycle time is OPEN; the lab's 4 s ramp is a labelled presentation value.
- **`WfRecorder`:** a fixed-step trace with a `scene` block, written to `runs/physics/`.
- **`WfRouteState`:** the imported route sampled linearly in mission time (C-010), with a reversible log display offset (C-004).

**PROTOTYPE simplifications.** Each of these is labelled:
- **Actor profiles.** 46 DYN-024 (STUDY FIXTURES / HUMAN FACTORS OPEN): human IVA 75 kg, 1.75 m, 0.75 m reach; suited 220 kg, 0.60 m reach; Seraph a 90 kg proxy (embodiment character-owned). Test values only; colliders and CoM must come from the rigs, and the checks vary the mass.
- **Foot friction.** μ = 0.6. The engine's own surface friction is 0, and the foot model holds or walks the actor.
- **Grip and spin.** The hand removes spin while gripping, as an arm resists rotation; the grip passes no torque model.
- **Stance.** The body is kept upright (up = −field) only while it stands or grips. In free drift, angular momentum is conserved.
- **Euler term.** It acts on translation only; α is 0 outside a ramp.

## Checks

`--check-physics` is part of `workflow.py runtime-export`:

```bash
timeout -s KILL 180 /snap/bin/godot-4 --headless --fixed-fps 60 --path godot res://scenes/physics_lab.tscn -- --check-physics
```

It prints one `WF_GODOT_PHYSICS` line with actual, expected and tolerance for each check. Results on 2026-10-11 (PASS):

| Check | Owner | Tolerance | Result |
| --- | --- | --- | --- |
| Every rig fixture through `frame_field.gd` | DYN-022 | 1e-9 per component | pass |
| Zero-g drift, 10 s | DYN-007 | Δv 1e-6, position 1e-4 m | Δv 0, position 2.1e-5 m |
| Push Δv = J/m, two masses; centred push gives no spin, off-centre push spins | DYN-010 | 1e-3 | 0.400 / 0.136 m/s; 0 vs 0.875 rad/s |
| Push, drift, catch at rail 2; grip stops the body; repeat run identical | DYN-007/011, SIM-013 | v < 1e-2 within 0.5 s; bitwise | stopped in 1 tick; identical |
| Tool at 5 m/s against a 0.1 m wall; released tool keeps drifting | DYN-012 | no crossing | 7e-6 m penetration |
| Ring drop from 1.5 m against the analytic inertial straight line | DYN-002/003, GEN-003 | 0.02 m, 2 frames | A −0.3335 m vs −0.3327 m; B mirrored |
| Standing on the ring floor | DYN-004 | 1e-3 g | 0.50097 g, at rest |
| Ship↔ring handoff round trip | DYN-001/009 | 1e-6 | 2e-15 |
| LOW_THRUST tilt; HIGH_POWER locked field | DYN-005/006 | 0.01° | 11.2885°; −1.5 g along X |
| Mode controller: each mode's field vs the rig fixtures (COAST 0.50097 g, tilt 11.29°, HIGH_POWER −1.5 g) | DYN-005/006 | 1e-9 g, 0.01° | pass |
| COAST→HIGH_POWER: spin-down-and-lock then drive on; ω = ω₀(1−t/T), α = −ω₀/1800 s, Euler z = −ω₀R/T, both rings, sign-correct | DYN-006/008 | 1e-12, 1e-15, 1e-9 | 0; 0; 9e-16 |
| Invalid, DAMAGED and busy requests refused and logged SIMULATION_ONLY; `can_cross` false mid-ramp, unsynchronized and with a closure open | DYN-009 | flags | pass |
| Ring signs: A (aft) +0.41888, B (forward) −0.41888 rad/s about +X; spin-down Euler fixture mirrored between rings | DYN-023/026 | 1e-9 | pass; Euler ±0.00652 m/s² at the floor |
| Owner sequence: an unsecured occupant holds the transition before the ramp (rings keep turning), securing resumes it; LOW_THRUST during a ramp refused; ramp refused with the drive on; drive on only after `RINGS_LOCKED` | DYN-026 | flags | pass |
| Vestibule: drum ramp refused without restraint or with a boundary open, stops if restraint is lost; both closed mid-ramp; drum matched within the rig tolerance; only the matched side opens, unknown pressure refused, never both open | DYN-027 | flags, tolerance 4.19e-4 rad/s | pass |
| Vestibule handoff: co-rotating occupant at rest in the ring frame; inertial velocity and position continuous; again at the real drum restraint pose (in the drum annulus) | DYN-027 | 1e-12 | 0; 6e-17 m/s; 1e-16 m; at the pose 0 (bare reparent error 0.593 m/s at 1.416 m) |
| Tether fixtures (75 kg at 1.0 m/s, 220 kg at 0.3 m/s): impulse, velocity, rigid-limit force | DYN-025 | 1e-4 N s | −75 / −66 N s; 4500 / 3960 N at 1/60 s (diagnostic) |
| Tether on the Jolt body, 2 masses × 2 speeds: m·Δv = logged impulse; no impulse while slack; no outward speed; inside L | DYN-025 | 1e-3·m N s; 1e-5 m/s; 1e-4 m | pass, worst 6e-5 N s mismatch |

`--check-eva` (WF_GODOT_EVA, PASS) also runs the drift checks:

| Check | Owner | Tolerance | Result |
| --- | --- | --- | --- |
| Tether stops a 0.3 m/s outward push at L = 2.0 m | DYN-015 | overshoot 1e-3 m, outward speed 1e-6 | overshoot 0, 7.7e-9 m/s, TAUT |
| Unclipped, the same push continues unchanged | DYN-015 | Δv 1e-6, track 1e-3 m | Δv 0, track error 1e-4 m, 2.72 m out |
| Egress refused outside EXTERIOR and with no live tether; v_rel at egress; field in EVA | DYN-013, GEN-003 | 1e-6 | refused; 0; 0 g |
| FLIGHT_EVA HOLD after the drift; thruster flag default | DYN-013 | flags | HOLD; off |
| Body never inside the hull proxy (start at the real hatch, clipped and unclipped runs) | PROTOTYPE collider | clearance ≥ −0.01 m | min 0.355 m |
| A 0.3 m/s push toward the hull beside rail anchor ANC_AFT_02 (0.6 m round the collar, off the rail rod) is stopped by contact, no tunnelling | PROTOTYPE collider | clearance ≥ −0.01 m, contact made | stops at −1e-5 m, inward speed 4e-3 m/s |
| Rail contact: between two anchors the hand closes on the rod (on its line, inside the run, not at an anchor) | PROTOTYPE rail rod | 1e-4 m | grips `EVA_RAIL_AFT` |
| Two-tether protocol in the drift: release refused until the other is clipped and tested, one anchor per tether, clip out of hand reach refused, never zero live | EVA-014 | flags | pass, live ≥ 1 throughout |
| Two tethers clipped (ANC_AFT_00 / 01), push outward: inside both spheres | DYN-025, EVA-014 | 1e-3 m | overshoot 0.75 mm, both taut, impulses 61 / 21 N s |

**Review stills.** `godot --path godot res://scenes/physics_lab.tscn -- --capture-lab=<dir>` (needs a display) plays the slice on one
controller and saves six stills:
1. grip;
2. an off-centre push, so the body spins as it drifts past the loose tool;
3. the catch on rail 2;
4. the tethered drill at the taut 2 m line, with its impulse log;
5. the vestibule handoff steps;
6. standing in ring A.

The camera, key light, colours and near-wall cutaway are presentation only.

**Performance** (2026-10-11, RTX 3070, GL Compatibility, 60 Hz, the lab scene with a display): physics step 0.74 ms median, 2.27 ms p95 (`Performance.TIME_PHYSICS_PROCESS` over 600 frames). The Jolt active-body monitor reads 0 and is not used.

**Ring drop check.** It is the test for double counting. It compares a body that the rotating-frame field moves against the straight inertial path the same body would take. Python fixtures and their invariants are in `tests/test_crew_dynamics.py`.

The route check is `check_route.gd`, which prints `WF_GODOT_ROUTE`. All 900 released rows are reproduced exactly. The open validation rows (14–18: coordinate frame, ephemerides, full solve) are listed, not assumed.

## Navigation

`crew_dynamics.nav` (rig `dynamics.nav`) is a topological graph over the crew_transfer passages plus the suited EVA path (SP-12 → airlock → exterior). Each edge records:
- frame
- pressure boundary
- rotating interface
- allowed actors
- allowed modes
- the technique per mode: hand over hand, radial ladder, or aft-down ladder

Edge rules:
- A closed boundary, a disallowed mode or a disallowed actor removes the edge (DYN-018).
- Docks open only when DOCKED.
- The exterior is open only in EVA, and only to the suited profile.
- Suited bodies stay off the crew tubes, whose clearances are checked for the unsuited envelope only.
- The casualty query always answers HOLD.

Godot consumer: `godot/scripts/physics/nav_graph.gd` (`WfNavGraph`) loads the rig's `dynamics.nav`. `route(start, goal, mode, actor, closed, synced)` mirrors `crew_dynamics.route` (breadth first, neighbours in edge order, same tie-breaking) and returns the node path with the technique of each edge in the mode. A PORT_GATE edge is also removed while the drum is not synchronized with its ring (`synced` false, DYN-009; Godot side only). `casualty()` always answers HOLD (DYN-020) and never a route. `godot/scripts/check_nav.gd` compares 20 cases with the paths generated by the Python reference (ring A to ring B, closed hatches, suited actor off the tubes, EVA exterior, docks, same node, unknown node) and prints one `WF_GODOT_NAV` line: `godot --headless --path godot --script res://scripts/check_nav.gd`.

Boarding body mode: `boarding.gd` has an optional body mode (key N, or `--check-body`), built by `godot/scripts/physics/body_tour.gd` (`WfBodyTour`) on the real route geometry with the ship visible around the body. The visitor / instructor body (profile human_iva, no survivor identity, STG-001) moves with the crew physics in two beats. SPINE (stop WF.STOP.IND.SPINE, DOCKED, SHIP frame, field zero): the colliders are generated from `dynamics.stages.trunk` only (a hollow cylinder of `clear_radius_m` along `axis_m` from 64 thin static flats tangent to that radius, closed ends, with the rig's seven branch `openings` (ports, connectors) cut out, each a 0.6 m bore closed at its far end (the hatch or connector beyond); the nine `Crew_Trunk_*` rails as rod handholds along their `rail_start`..`rail_end`, the hand closing on the nearest point of the rod); the body grips `Crew_Trunk_Refuge_Rail_1`, pushes off aft (at most the profile `test_push_dv`), drifts about 5.9 m and catches `Crew_Trunk_Handrail_2_1` (no thrust, no braking, DYN-016). RING (stop WF.STOP.IND.HABITAT, COAST, RING_A or RING_B frame via `WfFrameField`): the colliders are that ring's sector-1 aisle and landing boxes (ring A from the induction route's `rooms`, ring B from `dynamics.stages.ring_rooms.rings.RING_B`, the same `sector_whitebox` clear volumes on ring B's rotor; floor at `deck_m`, walls and ceiling from `half_m`/`axes`, open where the two boxes touch); the body walks the aisle on the real deck (r 28 m, 0.50097 g at the foot) and a dropped object deflects with the sign of the rig's Coriolis fixture, with on-screen text stating the DYN-003 figure as a display of the sourced spin, not a comfort limit. No collision shape comes from an imported mesh. PROTOTYPE simplifications: the branch bores stop 0.6 m beyond the trunk wall (closed hatches; nothing past them is walkable) and the trunk is closed at both ends; the aisle is closed at its ends and ceiling; the capsule lies along the trunk axis (profile numbers, not a posture) and the push line goes through the centre of mass (no spin); start rail, catch rail, drop height (1 m) and the 0.2 m slab thickness are tour choices. Ring B's beat (key 3) runs in its own B1 boxes with the ring B field; its proxy hangs under ring B's pivot. Display: the physics runs in its own collision layer (`TOUR_LAYER`) in a world node that never moves, with ring A at its index pose in ring-frame coordinates; a visual proxy of the body and tool hangs under `view_root`, a child of this node in the SPINE beat and of ring A's pivot (at the ring centre) in the RING beat, so it and the camera turn with the real ring meshes; the rotation is shown and never added to the physics. Each beat puts the review state to its stop (`beat_changed`: rings stopped at the index for SPINE, rings at full speed at once for RING). Keys: 1 spine, 2 ring A aisle, 3 ring B aisle, G / Space / R grab, push, release, W A S D walk, T drop, V view, K colliders, N back to the review rail. The default rail walkthrough, `--check-transfer` and the free-flight WASD camera (a review tool, not a crew capability) are unchanged. `--check-body` prints one `WF_GODOT_BODY` line (push, catch on a real `Crew_Trunk_*` rail, straight drift, radial clearance inside `clear_radius_m`, each branch opening open to its closed stub (ray from the axis stops at 1.40 m, a plain wall at 0.80 m), floor g, pace, display turning with the ring, Coriolis sign); `--capture-body=<dir>` writes six stills (needs a display).

## Blender

`physics_traces.py` rebuilds a trace's room and handholds, keys one LINEAR key per recorded step and re-reads every keyed frame against the trace (1e-4 m). It renders stills and saves `<scenario>.blend` under the output directory.

A character passed with `--character` is an ARTISTIC layer parented to the capsule: it poses, and never moves the capsule.

```bash
/snap/bin/blender -b --python src/wayfarer/shots/physics_traces.py -- --out runs/<stamp>-physics-shots runs/physics/push_drift_catch.json runs/physics/tool_float.json runs/physics/gravity_change.json runs/physics/eva_tether.json
```

The `gravity_change` and `eva_tether` traces are written by the headless checks (`check_gravity_change()` in `check_physics.gd`, `check_drift()` in `eva.gd`). `gravity_change` is the SHIP-frame spine with the actor gripping rail 1 and the loose tool: the tool floats for 1 s, DRIVE_ON then applies the HIGH_POWER envelope bound (1.5 g aft, labelled "not a flight value" in the trace `scene.labels`), the tool lands on the aft wall and the actor hangs from the rail. `eva_tether` is the clipped push-off until the tether is taut plus 1 s. A `scene.tether` entry draws the tether (PROTOTYPE length) as a rod that follows the actor and a wire sphere of radius L.

Result (runs/20261011T112010Z-physics-shots): four shots, max key error 0.0 m each, `WF_PHYSICS_TRACES` PASS. Character layer: yes, in `runs/20261011T112022Z-physics-shots-character` (push with `instructor.glb`, EVA with `eva_instructor.glb`, MPFB output under the CC0 licence recorded in `docs/CHARACTERS.md` Licenses).

## Open

The 2026-10-11 answers closed the five physics questions (ring sign, actor fixtures, tether, transition order, vestibule handoff). What
stays OPEN is owned by the Sheets: the tether's stiffness, damping, load limiter and anchor rating (DYN-025, Mnemarch), actor envelopes
and CoM from the rigs (DYN-024), the flight timing of any ring transition (DYN-026), the vestibule mechanism, cycle time and pressure
threshold (DYN-027, PRESS-004). FLIGHT_EVA, the casualty route and the concurrent low-thrust ramp stay HOLD.
