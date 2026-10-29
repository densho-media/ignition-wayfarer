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
| Scientific state | Sheets | `data/wayfarer_3d.toml` (`[habitat]`, `[configuration.*]`), `data/simulations/wf_route_v1.json` (NAV-001), FRM-002 channels |
| Local interactive physics | Godot 4.7.2 with built-in Jolt (SIM-002) | `godot/scripts/physics/`, the walk (`excursion.tscn`) |
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
- **`WfCrewBody`:** the capsule actor, the one controller the walk uses. Its mass, radius, height, reach and test push Δv come from the rig profile (`human_iva`, `human_suited`, `seraph`).
  - **Input:** input selects grab, release and push, never thrust (DYN-016).
  - **Grip:** a joint to a marked `WfHandhold` within reach (DYN-011). Its linear axes lock, so the anchor impulse stops the body.
  - **Push:** an impulse J = m·Δv_test by default (1.0 m/s IVA, 0.3 m/s suited: DYN-024 test speeds, not caps; a caller may give any J), applied at the hand point after release, so an off-centre push spins the body (DYN-010).
  - **Walk:** only on a floor under a field above 0.05 g, as a contact force limited to μN.
  - **Ladder (M2, PROTOTYPE technique):** `on_ladder(v)`. Hand over hand, the hands carry the body at `ladder_v` along a line (the
    climber line, or the M2 access line through the port, the drum and the elbows) and hold its axis along `ladder_up`, in any field. The field still acts, and the hands supply the difference, logged per step as
    `hand_impulse` = m(v_set − v after the field). No hand-load limit is sourced, so the load is measured and never judged.
- **`WfFrames`:** the Blender→Godot axes `(x, z, −y)`, the signed ring ω and the frame changes.
- **`WfModeController`:** the operating modes COAST / LOW_THRUST / HIGH_POWER / DOCKED / EVA (SIMULATION_ONLY, untimed). The ring steps follow the owner's sequence (DYN-026, WORKING scenario / flight event OPEN): `DRIVE_OFF` → `OCCUPANTS_SECURED` → `RINGS_SPIN_DOWN` → `RINGS_LOCKED` → `DRIVE_ON` (and `DRIVE_OFF` → `OCCUPANTS_SECURED` → `RINGS_UNLOCKED` → `RINGS_SPIN_UP` back). A ramp never starts with the drive on (the concurrent ≤ 0.1 g case is unreleased) or with an occupant not secured (`occupants_securable`, lab key O): the transition holds with `hold_reason`, fail closed, until `resume()`. `DRIVE_ON` into a locked mode waits for `RINGS_LOCKED`. A LOW_THRUST request during a ramp is refused "not released". No First Ignition event time. `request(to)` walks the ordered steps of the rig's `transitions["A>B"]`; an unknown mode, a DAMAGED state, a request while busy or a pair missing from the table is refused and logged `{status: SIMULATION_ONLY, refused: true, reason}`. The ring ramp (`spin_ramp`, 1800 s, WORKING, timing OPEN) runs at constant α = ω_full/T, and the controller writes the signed ω, α and the ship acceleration (known 0 with the drive off, else the envelope bound, labelled "not a flight value") into the `WfFrameField`. `advance(dt)` is real time; `skip(s)` advances the ramp clock with the true α (the lab's K key, PROTOTYPE presentation). `can_cross(edge)` follows the PORT_GATE gate: blocked during or before a ring ramp of the running transition, with the drum unsynchronized, or with a closure behind the crosser open.
- **`WfVestibule`:** the DYN-027 rotary vestibule (mirror of `crew_dynamics.vestibule_gate`): two closures (STATIONARY, RING) around a drum. The drum changes speed only with the occupant restrained and both closures shut (a ramp stops if either is lost); a closure opens only when the drum matches that side within the rig tolerance (`dynamics.vestibule.match_tol_rad_s`, from the rotor rpm match tolerance), the other closure is shut and the pressure is shown equalized (`dp_equalized`, threshold OPEN, so unknown refuses). The occupant's (r, v) crosses through `to_ring` / `to_ship` with ω×r. The drill (lab key V) and its check put the occupant at the real drum restraint pose, the hold point of the rig's `dynamics.stages.access` line (X 82.60 m, 1.416 m from the axis, inside the drum annulus 0.975–1.925 m, ring A at the index); a bare reparent there would carry 0.593 m/s of spurious speed. The drum cycle time is OPEN; the lab's 4 s ramp is a labelled presentation value.
- **`WfRouteState`:** the imported route sampled linearly in mission time (C-010), with a reversible log display offset (C-004).

**PROTOTYPE simplifications.** Each of these is labelled:
- **Actor profiles.** 46 DYN-024 (STUDY FIXTURES / HUMAN FACTORS OPEN): human IVA 75 kg, 1.75 m, 0.75 m reach; suited 220 kg, 0.60 m reach; Seraph a 90 kg proxy (embodiment character-owned). Test values only; colliders and CoM must come from the rigs, and the checks vary the mass.
- **Foot friction.** μ = 0.6. The engine's own surface friction is 0, and the foot model holds or walks the actor.
- **Grip and spin.** The hand removes spin while gripping, as an arm resists rotation; the grip passes no torque model.
- **Stance.** The body is kept upright (up = −field) only while it stands or grips. In free drift, angular momentum is conserved.
- **Euler term.** It acts on translation only; α is 0 outside a ramp.

## Checks

The Godot physics lab, its `--check-physics` table (DYN-001…027 fixtures on the Jolt bodies), the EVA drift check and the review
stills are retired with their scenes (tag `archive/pre-cleanup-2026-10-29`; results of 2026-10-11 there). The walk's
`--check-excursion` (docs/MODEL.md EXC-001) exercises `WfCrewBody`, `WfFrameField`, `WfModeController` and `WfVestibule` through the
player's actions; the Python reference and its invariants are in `tests/test_crew_dynamics.py`.

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

No Godot scene consumes the graph since the boarding walk and its body tour were retired; the walk follows the rig's stage lines.

## Blender

`physics_traces.py` rebuilds a trace's room and handholds, keys one LINEAR key per recorded step and re-reads every keyed frame against the trace (1e-4 m). It renders stills and saves `<scenario>.blend` under the output directory.

A character passed with `--character` is an ARTISTIC layer parented to the capsule: it poses, and never moves the capsule.

```bash
/snap/bin/blender -b --python src/wayfarer/shots/physics_traces.py -- --out runs/<stamp>-physics-shots runs/physics/push_drift_catch.json runs/physics/tool_float.json runs/physics/gravity_change.json runs/physics/eva_tether.json
```

The `gravity_change` and `eva_tether` traces were written by the retired headless checks (`check_physics.gd`, `eva.gd`); traces recorded then still bake. `gravity_change` is the SHIP-frame spine with the actor gripping rail 1 and the loose tool: the tool floats for 1 s, DRIVE_ON then applies the HIGH_POWER envelope bound (1.5 g aft, labelled "not a flight value" in the trace `scene.labels`), the tool lands on the aft wall and the actor hangs from the rail. `eva_tether` is the clipped push-off until the tether is taut plus 1 s. A `scene.tether` entry draws the tether (PROTOTYPE length) as a rod that follows the actor and a wire sphere of radius L.

Result (runs/20261011T112010Z-physics-shots): four shots, max key error 0.0 m each, `WF_PHYSICS_TRACES` PASS. Character layer: yes, in `runs/20261011T112022Z-physics-shots-character` (push with `instructor.glb`, EVA with `eva_instructor.glb`, MPFB output under the CC0 licence recorded in `docs/CHARACTERS.md` Licenses).

## Open

The 2026-10-11 answers closed the five physics questions (ring sign, actor fixtures, tether, transition order, vestibule handoff). What
stays OPEN is owned by the Sheets: the tether's stiffness, damping, load limiter and anchor rating (DYN-025, Mnemarch), actor envelopes
and CoM from the rigs (DYN-024), the flight timing of any ring transition (DYN-026), the vestibule mechanism, cycle time and pressure
threshold (DYN-027, PRESS-004). FLIGHT_EVA, the casualty route and the concurrent low-thrust ramp stay HOLD.
