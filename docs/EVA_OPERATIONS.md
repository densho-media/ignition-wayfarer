# EVA Operations (EVA-OPS-001)

A playable, physics-based training experience in the interactive Wayfarer. The player flies the canonical suited astronaut
(WAYFARER_EVA_Y155) and the companion drone (WAYFARER_EVA_DRONE) outside the hull. Both exist the whole time, both keep moving under
physics while the other is controlled, and switching control resets nothing. It is a **TRAINING SIMULATION**: FLIGHT_EVA stays HOLD
(S&E 45 O-07), every hold is SIMULATION_ONLY, and nothing here is a flight procedure.

- Scene: `godot/scenes/eva_ops.tscn` (`godot/scripts/eva/`). On the website it is **Explore Exterior** (`/exterior/`, Start opens the
  shared Godot page with `#exterior`; the older `#eva` still works); from the walk **F9** opens it, natively `godot --path godot -- --eva`.
  **F8** goes inside to the walk (Explore Interior); the page's title, Exit link and hash follow the scene (`godot/scripts/web_page.gd`).
  It starts standing on the magnetic training walkway (LOCO-002, [LOCOMOTION.md](LOCOMOTION.md)); `#exterior-hatch` (`-- --hatch`)
  starts in free exploration at the hatch, and **F4** (or `#exterior-first-flight`) starts the guided First Flight.
- Package: `data/simulations/wf_eva_ops.json` (contract `wf_eva_ops v1`), written by `src/wayfarer/eva_ops.py` from the canonical EVA
  system (`data/eva_suit.toml`, `data/eva_drone.toml`, `validation/eva_system.py` and its `runtime_layout`), the Brow
  (`forward_shield.py`), the training route (`eva_route.py`), the rig (`wf_sim_rig.json`) and the operations choices in
  `data/eva_ops.toml` (all PROTOTYPE). Godot computes no spacecraft geometry and no nozzle layout.

## Bodies, frames and thrusters

- **Frame.** The ship frame of the rig (`dynamics`, `WfFrameField` SHIP): weightless with the drive off (DRIFT, rig mode EVA, 0 g), or
  the burn presets, which are training only: **BURN_HP** at the rig's HIGH_POWER demonstration bound (1.5 g) and **BURNBROW_11** at
  1.1 g. Under a burn the astronaut stands on the Brow's ram face. Cold gas cannot lift the pair: about 1900 N of weight against about
  18 N of thrust.
- **Bodies.** Each body is a `WfEvaBody` (a `WfFreeBody`: Jolt for contact only, no gravity, no damping). The origin sits at the mass
  centre. Mass is the dry mass plus the gas carried. The inertia tensor comes from `eva_system.drone_inertia` for the drone and a box
  estimate for the suit (PROTOTYPE). Rotation integrates Euler's equations with the gyroscopic term.
- **Nozzles.** The built layout comes from the canonical system check (`references/p1_eva_system.json` `runtime_layout`, Blender to
  Godot axes `(x, z, −y)`). There are four configurations:

  | Configuration | Nozzles | Used when |
  | --- | --- | --- |
  | `drone_free` | 26 × 4 N | the drone flies alone |
  | `drone_near_suit` | 22 × 4 N | the four ventral nozzles are inhibited within 1.5 m of the suit |
  | `docked` | the live drone set, about the pair's mass centre | the drone is on the suit's back; the suit reserve is isolated |
  | `suit_reserve` | 16 × 8 N | the astronaut alone |

- **Allocation.** Per signed pure axis, `eva_ops.py` solves the duty cycles with the canonical NNLS (`eva_system.nnls`). Godot mixes
  them linearly. When any duty would pass 1, all duties scale down together. Failed valves are forced shut. The body receives the
  wrench the duties actually produce, never the one commanded.
- **Gas.** Each step draws ṁ = Σ Fᵢ / ve (ve = Isp·g₀ = 637 m/s) from the body's feeds. A body short of gas gets the scaled-down
  wrench, never a refill. Canted nozzles waste part of every pulse. The drone's free-flight set turns about 0.67 of its valve thrust
  into net force, and delta-v planning uses that figure.
- **Modes.** In **MANUAL**, the keys are direct body-axis thrust and torque. **ASSISTED** adds the flight software: rate damping,
  attitude hold, brake and position hold. All four fire the same valves and use gas. Nothing is damped unless gas is spent to damp it.
- **Contact.** The colliders come from the package, never from the visual mesh:
  - the hull collar, the Brow's front, aft face and rim, its 412 truss members (as capsules) and the Dust Lance;
  - the airlock fitting, the rail, the station rack.

  Standing exists only when the apparent acceleration presses the body into a surface. Walking is a friction-limited foot force, not
  a set speed. A hand grip holds the body to the ship. The tether is an inextensible line that removes the outward velocity at full
  length.

## Nitrogen

There are four separate inventories, each a `WfN2Tank` with a ledger: contents plus gas used minus reset gas equals the first fill.

| Inventory | Contents |
| --- | --- |
| Suit reserve | 0.695 kg (0.625 kg usable, feed 1.2 MPa) |
| Drone | 1.561 kg in two COPVs (1.405 kg usable) |
| RC-1 cartridges | 0.507 kg usable each; four in the station rack |
| Station | holds cartridges only; it refills nothing |

- **Status.** The HUD shows NOMINAL, LOW PROPELLANT, RESERVE ONLY (the drone is away), EMERGENCY ONLY (at or below the 30 % emergency
  floor; the thrusters stay live) and MANEUVERING UNAVAILABLE. Below the readout it shows Δv and both inventories side by side.
- **Docked.** The pair flies on the drone's gas through the dock line. The suit reserve stays isolated, as in the canonical system.
  Docking creates no gas.
- **RC-1 cartridge** (PROTOTYPE accessory, `data/eva_ops.toml [cartridge]`): a shortened drone COPV on a keel adapter.
  - It seats in the suit's empty dock channel on the canonical latch bolts and probe.
  - It feeds the suit's thrusters through a 1.4 MPa regulator, which wins over the reserve's 1.2 MPa at the check valves. The
    cartridge is spent first and the reserve last.
  - It never refills a vessel: no canonical line transfers gas between tanks.
  - Arm B grips it by its lug. The canonical suit and drone are unchanged.
- **Training.** F5 is a labelled training reset: every vessel is refilled and the rack restocked, and the ledger counts it. Stage 7 of
  First Flight vents the reserve to its emergency level and counts the vented gas as used. Operational rules (F3) allow no reset, only
  DRIFT, and keep the ram face and the keep-outs enforced.

## The drone

The drone has six modes: MANUAL, HOLD, FOLLOW (a station beside the astronaut), RETURN TO ASTRONAUT (docking), RETURN TO SHIP (the
station socket) and RESCUE.

- **Docking.** The drone flies to an approach gate 0.50 m behind the suit, then straight in. Capture requires ≤ 20 mm, ≤ 0.03 m/s and
  ≤ 2°. Capture conserves momentum and merges mass and inertia about the pair's mass centre. Release separates the pair with the
  tongue spring at 0.05 m/s.
- **Manipulators.** The arms deploy in 2 s. The arm B gripper picks up, carries, releases and re-grips a cartridge, which keeps the
  drone's velocity when released.
- **Transit.** Transits fly at the economy speed of 0.3 m/s. The drone never builds more speed than its gas can take off twice, with
  the nozzle losses included. A ray look-ahead puts in a detour waypoint before the Brow, the truss or the hull.
- **Rescue state machine.** The astronaut presses Q to request it. The drone then:
  1. Checks its gas, the cartridges and the astronaut's speed.
  2. Chooses one of two plans:
     - **FETCH**: fly to the station, acquire an RC-1 with arm B, carry it to the astronaut and seat it in the empty channel.
     - **SHARE**: dock, so the pair flies on the drone's gas.

  The rescue succeeds only when the astronaut's available Δv has actually risen. Failure cases, each with its reason:
  - the drone is docked;
  - more than three valves have failed;
  - the astronaut moves faster than 0.8 m/s;
  - the station is empty and the drone's gas is too low to share;
  - the gas check fails;
  - the route is obstructed for 45 s;
  - the drone's gas runs out on the way.

  When gas is short, the plan slows to an economy cruise (down to 0.15 m/s) if that fits.

## Experience

- **Cameras.** Astronaut: third person or helmet. Drone: chase, sensor (nose) or stabilized inspection. C cycles them. Right mouse
  looks around.
- **Hazards.** Each hazard warns at 2 m and again inside it, by name:
  - radiator keep-outs and the ring sweep annulus;
  - the EYE facets and the Dust Lance;
  - the ram face (operational rules only) and the drive plume.
- **EVA — First Flight (F4).** Eight stages that advance on the scene's real state, never on a timer:
  1. Preparation.
  2. Surface: tether, then hand over hand to the forward hold.
  3. Free flight to a Brow aft-face fixture.
  4. Drone deployment.
  5. Drone flight and inspection.
  6. Propellant: back within 3 m on ≤ 0.20 kg.
  7. Resupply: emergency reserve, then a drone fetch or a manual cartridge.
  8. Return: stow, dock and grip the hatch.

  Free exploration has everything open. F6 sets a checkpoint, which stores positions only and never gas.
- **Controls** (WfInput context `evaops`, rebindable with F10):

  | Keys | Action |
  | --- | --- |
  | W/S/A/D/R/F | translate |
  | I/K/J/L/U/O | rotate |
  | Shift | fine control |
  | B | brake |
  | M | assisted or manual |
  | H / P | attitude hold / position hold |
  | 1 / 2 | control the astronaut / the drone |
  | G | grab |
  | Space | push off (a hold, or the walkway on the boots) |
  | V | magnetic boots on or off |
  | T | tether |
  | X | dock or undock |
  | Y | drone mode |
  | Z | arms |
  | N | gripper |
  | E | use, seat or inspect |
  | Q | ask the drone for nitrogen |
  | F2 | drift or burn |
  | F3 | operational or training rules |
  | F5 | training reset |
  | F7 | valve fault |

## Checks

- `python3 src/wayfarer/eva_ops.py`: writes the package and prints the Δv parity against the canonical budget (drone 34.9, docked
  5.12, reserve 2.67 m/s). `--check` reports CURRENT or STALE. The `eva` loop's `ops` stage regenerates it.
- `tests/test_eva_ops.py` covers the physical invariants:
  - Δv parity and the canonical nozzle counts;
  - non-negative duties within one valve;
  - finite resupply and the regulator order;
  - burn presets that cold gas cannot fly off.
- `godot --headless --fixed-fps 60 --path godot res://scenes/eva_ops.tscn -- --check-eva-ops` (`eva_check.gd`; runtime-export check
  `eva-ops`; the web build's native reference and the browser equivalence session) runs 44 checks in the real scene (34, plus 10
  for the magnetic boots: [LOCOMOTION.md](LOCOMOTION.md)). It prints one
  `WF_GODOT_EVA_OPS` line:
  - **Physics:** momentum and angular momentum conserved, F = m a with the rocket equation at the allocation efficiency, Euler
    torque, braking and assistance spend gas, no invisible damping, ship acceleration seen relative, standing and walking under 1.1 g
    without lift-off, and switching control keeps all state.
  - **Gas:** gas = Σ F / ve, consumption scales with thrust, separate inventories, never below the residual, the emergency floor,
    depletion, docking creates no gas, the cartridge feeds first, and a conserved ledger over every vessel.
  - **Drone:** undock and autonomous dock, follow, obstacle avoidance, arms, pickup, release and re-grip, a FETCH rescue that raises
    the astronaut's Δv, and the four refusals.
  - **First Flight:** a complete scripted run, all eight stages through the same actions as the keys (about 1100 s simulated, 50 s
    wall).
- `-- --shots=<dir>` (needs a display): stills of the five camera modes.

## Limits and status

- PROTOTYPE throughout: the RC-1 accessory and station rack, the suit inertia box, the assist gains, the hand reach (0.9 m), grab speed,
  push-off, tether length and walking friction.
- The suit glove loads, tether length and keep-outs are OPEN in canon (`eva_suit.toml`).
- The astronaut is the Y155 instructor model with its clips (`WfCharacterRig`); runtime-export and `workflow.py play-characters` export
  it. Without the exported GLBs the astronaut is a proxy labelled SUIT MODEL MISSING and the page reports `model: false`. Without
  the DOCKED ship GLB, the colliders are drawn as grey surfaces.
- The truss is simplified to capsules on the member centre lines.
- The same bodies, gas, allocation, frames and drone are meant for the Brow Games. Their rules (reserve floor, gates) belong to that
  task.
