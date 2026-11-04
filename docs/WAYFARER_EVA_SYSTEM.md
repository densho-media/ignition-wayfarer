# Wayfarer EVA system: suit and companion drone

The EVA system is one piece of crew equipment in two bodies. The first is the guided-EVA pressure suit **WAYFARER_EVA_Y155**, a hybrid
rear-entry suit whose life-support module is also its back hatch. The second is the companion drone **WAYFARER_EVA_DRONE**, a small
robotic service spacecraft that docks into that module. Docked, the drone is the suit's maneuvering pack and gas supply. Detached, it
works on its own with two arms and a tool cartridge. Industrial work comes first: hull inspection, maintenance and navigation aid. The
Brow Games will use the same kit later, and this repository prepares only their states.

Status: **PROTOTYPE, NOT CERTIFIED.** No IGNITION owner row defines the drone. The drone is not one of the S&E 51 fleet classes and does
not change their counts. The suit's owner rows and its OPEN values are in [EVA.md](EVA.md). Every number in this document is a PROTOTYPE
engineering choice made in the EVA system study (2026-11-02/03). They are bracketed by present-day hardware (NASA SAFER and MMU, the
ISS free-flyer Astrobee, small space manipulators) and plain physics. **None of them is IGNITION canon.** The owner question drafted at
the end asks whether to adopt them.

This document replaces the three study notes (V1 study, V2 suit and shield drone, V3 robotic drone). Their decisions are recorded under
[Decisions carried from the studies](#decisions-carried-from-the-studies). The study scripts and files are archived outside the
repository.

## Architecture

| Concern | Where |
| --- | --- |
| Suit parameters, `[form]`, `[module]` (life-support packaging), `[suit_propulsion]` | `data/eva_suit.toml` |
| Drone parameters: gas, body, mass model, propulsion, arms, poses, tools, sensors, anchor | `data/eva_drone.toml` |
| Shared pure formulas: gas budget, nozzle sizing, nozzle layouts, 6-DOF authority, single failures, arm IK, life-support volume | `src/wayfarer/eva_system.py` |
| Shared mesh helpers (lathe, capsule, nozzle, materials) | `src/wayfarer/build/eva_geometry.py` |
| Suit generator | `src/wayfarer/build/eva_suit.py` → `assets/characters/WF_EVA_<WEARER>.blend` |
| Drone generator | `src/wayfarer/build/eva_drone.py` → `assets/characters/WF_EVA_DRONE.blend` |
| System scene: dock, states, sequences, props, cameras, lights | `src/wayfarer/build/eva_scene.py` → `assets/characters/WF_EVA_SYSTEM.blend` (packed) |
| System validation | `src/wayfarer/validation/eva_system.py` → `references/p1_eva_system.json` |
| Tests (owner-free physical invariants: budgets, authority, single failures, IK) | `tests/test_eva_system.py` |

One entry point builds everything: `python3 tools/workflow.py eva`. It runs build (suits) → drone → system → system_checks → fit →
access and the rest of the EVA loop ([EVA.md](EVA.md)). Each Blender step can also run alone:

```bash
blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_suit.py -- [--only instructor]
blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_drone.py
blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/build/eva_scene.py
blender --background --factory-startup --python-exit-code 1 --python src/wayfarer/validation/eva_system.py
```

The review file is `assets/characters/WF_EVA_SYSTEM.blend`. It opens on the hero camera with everything packed and nothing to run. Its
timeline holds the 13 states (one per 10 frames, named markers), and its NLA holds the dock and undock sequences.

The drone is crew equipment of the suit. The ship's drone fleet (`data/drone_bodies.toml`, `drone_fleet.py` and the DR-* classes) is a
separate system and is untouched. The EVA drone reuses only the fleet's GU-SIF interface for its tool flanges and its anchoring keel.

## Suit

### Pressure architecture

The suit is a hybrid: gas pressure everywhere in one continuous bladder, and a rigid composite **cuirass** over the chest and back with
an integral helmet bonded on. The rear-entry hatch is the life-support module. The limbs carry a slim patterned restraint (lines of
non-extension, shown as helical cords) and low-profile bearings at the scye, upper arm, wrist, hip and ankle. This is the right answer
for a fast-don suit that carries a drone on its back.

- **Pressure.** Sizing uses 40 kPa, the upper end of the 30-40 kPa trade, with proof 1.5 and burst 2.0. This is a sizing assumption,
  never a setpoint: EVA-004 `suit_pressure_kpa` stays OPEN.
- **Cuirass.** Its superellipse section (exponent 2.15) follows the anatomy of chest and back. The shell stops in an arch over the
  abdomen (±104°, 20 mm above spine_03) with a rolled graphite edge, so the waist bends and the chest stays rigid.
- **Helmet.** An asymmetric superellipsoid (exponent 2.25) fitted separately at the front, back and crown. It sits closer at the face
  and is fuller at the back for the head sweep. One wrap-around visor covers ±108° azimuth with a 10° side drop. A graphite brow carries
  two work lights and two cameras, and a low dorsal crest carries the harness. Design clearance is 22 mm around the head over its whole
  motion envelope (yaw 25°, pitch −15/+20°, roll 10°).
- **Layers**, outward along the body normal: cooling garment 4 mm, bladder 11 mm, restraint plus thermal/MMOD outer 20 mm, gloves 8 mm,
  boots 16 mm. They are skinned with the wearer's MPFB weights, so every existing action drives them. The outer layer stands 6 mm
  prouder at the crotch and knees and 22 mm at the elbows, where the restraint gathers into a fold.

### Pressure boundary

Every soft-to-rigid junction is a modelled pressure-bearing component, and the coverage check sees each one's real geometry:

- **Neck ring.** The helmet bonds to a titanium neck ring (16 × 10 mm flange, 6 mm lock collar) that seats on the cuirass yoke. The
  head moves inside the fixed helmet, and nothing of the neck reaches the junction.
- **Cuirass seal skirt** (`Cuirass_Seal`). Where the fabric ends at the cuirass rim, a clamped skirt runs from each fabric edge vertex
  to the shell 2.5 mm proud of it. It takes the fabric's weights on its fabric side and the torso's on its shell side, so it stretches
  with the waist rather than leaving a crack between the abdomen and the rolled edge.
- **Scye sleeve.** A six-convolute sleeve (rib 4 mm, 22 mm clear of the arm) runs from the scye bearing to the upper-arm bearing. Its
  weights rise smoothly over the first 18 % of its length, so the sleeve turns with the upper arm and the bearing takes the rotation.
  The gap between bearing race and arm is 18 mm.
- **Elbow limit and hinge.** Flexion is held to 115°. Beyond it the restraint fold closes on the forearm faster than the 22 mm fold
  allowance. The elbow also bends only about its hinge: where an action's IK plane would bend it more than 45° off the hinge axis (the
  instructor's body rotation bent the left elbow backwards for about a second, and the forearm skin passed through the soft elbow layer),
  the suit solver swivels the elbow round the shoulder-wrist axis until it bends within 45° of the hinge, moving it at most 3 cm a frame.
  The hand path is unchanged (`human.Solver(hinge_elbows=True)`, EVA suits only).

**Coverage check** (`validation/eva_fit.py`). Each body vertex casts a ray along its normal. It is covered if a pressure surface (the
soft layers, cuirass, helmet, neck ring, seal skirt, scye bearings and sleeves, module and gloves; listed in `PRESSURE_PARTS`) lies within
0.12 m, or if all 96 rays of a sphere hit one before 3.0 m (the vertex is enclosed). 3.0 m is longer than any chord through the suit: a ray
from the neck can run inside the suit to the boots, so the old 1.2 m flagged enclosed vertices as exposed. A ray that escapes to open
space is still an exposure. The check runs every frame and every body vertex of the 15 EVA actions, the five inherited ones, the nine system poses and
intermediate frames (0.25, 0.5, 0.75) of 14 transitions between them. Its negative control removes faces from the thigh, upper arm and
sternum and must find the hole.

**Result, both wearers:** 0 exposed vertices in every EVA action, every system pose and every intermediate sweep frame; the negative
control finds all three planted holes in both suits. The inherited interior `crawl` still fails (the head lifts out of the torso-fixed helmet: 1680 and
1872 head-vertex frames outside it, plus 7 newcomer pelvis vertices at the hip break): it is unsuited motion, marked NOT_SUITED_EVA, and no suited state uses it ([ACCESSORIES.md](ACCESSORIES.md)).

### Articulation (fix 4.2)

A pressurised arm cannot fold against a rigid torso. Three measures keep this true in the built file, and no invisible intersection
stands in for articulation. The validation finds no contact of the soft layer with the cuirass, module or helmet in any of the 13
states.

- **Soft layer trimmed at the shell.** Wherever the built cuirass passes through the outer layer, or comes within 4 mm of it (the seam
  allowance under the rolled edge), the outer layer is cut: fabric does not run under a rigid shell. Islands left under 80 faces are
  removed.
- **Fabric stitched to the rigid parts.**
  - The scye bearing's race and sleeve clamp hold the first 4.5 cm of the sleeve root on the torso. From there the weights hand over to
    the upper arm over 8 cm, so the convolute bends outboard of the bearing.
  - Torso fabric beside the cuirass rim and round the armpit follows only the torso.
  - The body's corrective shape keys (which bulge the unsuited deltoid, waist and hips) are removed from that fabric.
- **Shoulder clearance.** `clear_arms` runs after the poses are baked. For every system pose, an arm whose soft layer, including the
  faces at the arm's boundary, meets the cuirass or the module is turned at the shoulder: outward 0-48° and forward or back ±40°. Of the
  turns that clear it, the one that moves the hand least is chosen, and its keys are rewritten. The result per pose is in the suit report
  (`shoulder_clearance`).
  - The corrections are 6° and 54 mm at the hand for ready, and 12-18° and 44 mm for Burnbrow.
  - The other poses need 12-36° and move the hands by 136-316 mm.
  - A cross-body reach cannot be cleared at any turn in range. The left hand on the right forearm's drone keys is an example, so that
    pose was dropped. The forearm keys are for short presses, not a held control pose.

### Life-support module (fix 4.6)

The module is the hatch: 0.43 × 0.125 × 0.60 m, with a convex cylindrical rear face (30 mm bulge) that the drone's dock face mirrors. It
replaces the earlier 0.50 × 0.22 × 0.62 m PLSS display envelope. Its packaging is computed **by volume only**, using 2020s-class
technology:

| Item | Litres | Basis |
| --- | --- | --- |
| Primary O₂ COPVs | 3.0 | 2 × 1.1 L water volume at 30 MPa, about 0.8 kg O₂ |
| Secondary (emergency) O₂ | 2.2 | 1.6 L water volume at 30 MPa (0.60 kg O₂), own regulator: the 30 min purge below |
| CO₂ and humidity swing bed | 4.5 | two-bed amine (ISS / xEMU class) |
| Membrane evaporator | 2.0 | SWME class; heat rejection OPEN |
| Fan, pump, separator | 1.5 | one integrated unit |
| Battery 1 kWh | 2.5 | Li-ion at 400 Wh/L; duration OPEN |
| Avionics and radio | 1.0 | |
| N₂ reserve COPV | 2.9 | the suit's maneuvering reserve |
| Valves, regulators, lines | 2.0 | |

The items total 21.6 L, or 27.0 L with a 1.25 packaging factor, against a usable envelope of 27.7 L (bounding box × 0.86). The margin is
0.7 L. The module grew 5 mm in depth when the emergency O₂ was sized for the purge. Feedwater (3.6 L) lies in a conformal bladder in the
hatch wall.

### Life-support budget (PROVISIONAL)

`eva_system.life_support_budget()` balances the module's stores against metabolic and environmental loads. Its targets are **design
targets of this study**, not IGNITION canon: EVA-004 (suit pressure), EVA-008/009 (consumables) and EVA-028 (mass) stay OPEN in S&E.
Rates are present-day physiology and hardware (NASA HIDH, EMU, xEMU): 14.1 MJ per kg O₂, RQ 0.85, SWME latent heat 2.45 MJ/kg.

Targets: **8 h nominal plus 1 h reserve** on every consumable, and a **30 min emergency return** on the secondary O₂ alone.

| Case | Metabolic / environment | O₂ | Feedwater (SWME) | Battery (60 W + fan/pump) | Limit |
| --- | --- | --- | --- | --- | --- |
| Low | 150 W / −40 W | 18.3 h | 17.5 h | 13.3 h | 13.3 h, battery |
| Nominal | 250 W / 0 W | 10.8 h | **9.4 h** | 13.3 h | 9.4 h, feedwater: meets 8 + 1 h |
| High | 350 W / +60 W | 7.3 h | 6.1 h | 13.3 h | 6.1 h, feedwater: **below the 9 h target** |

- **Stores.** Primary O₂ 0.82 kg usable, secondary 0.60 kg, feedwater 3.6 kg, battery 800 Wh usable (1 kWh at 80 % depth), suit leak
  0.005-0.02 kg/h, repress 0.027 kg.
- **CO₂ and humidity.** CO₂ follows O₂ use at RQ 0.85 (0.075 kg/h nominal) through the two-bed swing; 20 % of the metabolic heat leaves
  as vapour through the same bed. Peaks of 600 W for 15 min (climb, ingress) sit inside the nominal profile; the SWME and fan are sized
  for 540 W.
- **Thermal.** The SWME rejects the sensible load (260 W nominal) by evaporating 0.38 kg/h of feedwater; the cooling garment loop
  carries it from the body.
- **Emergency.** With the swing bed lost, an open-loop purge holds ppCO₂ under 2 kPa at 1.13 kg/h: the secondary O₂ lasts **31.9 min**.
- **Sensitivity.** O₂ duration over metabolic rate: 16.4 h at 150 W, 10.8 h at 250 W, 8.0 h at 350 W, 7.1 h at 400 W. The high case
  is a hard, hot EVA: it ends on feedwater at 6.1 h, so such a profile is planned at 6 h or takes a second feedwater bladder.
- **Monitoring.** Dual ppO₂ and ppCO₂ sensors, dual suit pressure, vent-loop humidity and temperature, O₂ pressure and temperature per
  vessel, feedwater quantity, cooling inlet and outlet temperature, battery charge, and one time-remaining figure (the minimum over every
  consumable) on the cuff, relayed by the drone.
- **Plumbing.** Vent loop: fan, swing bed, helmet inlet over the visor, returns at the wrists and ankles. Water loop: pump, SWME, gas
  trap, garment. O₂: primary and secondary vessels on separate regulators into the vent loop; the secondary also feeds the purge valve.
- **Breathing gas and propulsion gas never meet.** The N₂ reserve vessel and the drone's dock probe have their own manifold. No line,
  valve or regulator is shared with the O₂ system.

Limits: steady-state rates only, with no transient thermal model, CO₂ bed sizing or condensation model.

### Controls and safety without the drone

- Chest display and a fold-out hand controller (below).
- Glove-sized forearm keys: the right forearm commands the drone; the left carries suit status, the emergency switch (red, guarded) and
  tether control.
- A suit N₂ reserve with 16 thrusters.
- Two waist tether reels and rated tether hardpoints.
- A red manual N₂ isolation valve and gauge.
- A mechanical drone release T-handle (a Bowden cable to the dock bolts, which works unpowered).
- Handholds on the drone.

### Hand controller (fix 3)

The translation / rotation hand controller is a fold-out arm of the MMU-armrest class, on the module's left front corner:

- **Mechanism.** A hinge housing carries an outer tube (`HCM_Link_1`) and a telescoping inner tube (`HCM_Link_2`) whose end carries the
  vertical rubber grip and a thumb puck. One skewed hinge axis, perpendicular to both end positions, swings it from stowed to deployed.
- **Stowed.** The arm stands upright along the module's front edge: behind the hanging arm, clear of the dock and out of the lumbar
  thrusters' plumes.
- **Deployed.** It swings forward and down (150.6° about the hinge for the instructor) and telescopes out 0.195 m, so the grip stands vertical
  beside the left palm of the free-flight pose. The grip is seated against the evaluated glove: its axis is the nearest vertical line to
  the palm centre that clears the glove by 3 mm along the grip's whole height. The hand reaches it in flight, drone-deployed and chase
  without moving the arm.
- **Stops and animation.** Two hard stops on the hinge (stowed and deployed) and two on the telescope. `HCM_Link_1` rotation about its Z
  is the swing and `HCM_Link_2` location along X the telescope; `EVA_SYSTEM_POSES` keys them per pose and `<link>_STATES` per system
  state. The values and stops are in the suit's `eva_hand_controller` property and the runtime manifest.
- **Release.** The yellow mechanical drone-release T-handle sits below the hinge, never under the folding arm (49 mm from it).
- **Checked** (`hand_controller`, every state): deployed in flight, drone-deployed and chase with the grip axis 52-53 mm from the palm
  centre and the glove 7 mm from the grip; stowed otherwise; no contact with the suit or the drone; inside its stops.

## Companion drone

### Body

The body measures 0.468 × 0.548 × 0.197 m stowed. In plan, a broad nose (the shoulders, when docked) tapers to a narrower tail (the
lumbar region), with no wings. In section it has:

- a concave dock face that mirrors the module;
- a raised graphite core spine from nose to tail, carrying the keel, regulator, battery, avionics and the tool trough;
- a low crown over each N₂ vessel;
- a lateral arm bay on each side under a two-leaf gull-wing cover, which carries the outer surface when closed.

The three lobes show what is inside. Docked, the drone stands 0.162 m beyond the module's rear face.

**Mass model.** The dry mass is 24.8 kg, made up of:

| Item | kg |
| --- | --- |
| Shell and core | 4.6 |
| COPV pair | 3.8 |
| Regulator and manifold | 1.5 |
| 26 thrusters | 2.6 |
| Battery (400 Wh) | 2.0 |
| Avionics and sensors | 2.6 |
| Dock mechanism | 1.4 |
| Arm A | 1.9 |
| Arm B | 2.6 |
| Tools carried | 1.1 |
| Tool cartridge | 0.3 |
| Bay covers | 0.4 |

The wet mass is 26.36 kg. Each item is placed on the built drone, which gives a local CoM of (−4, 14, 57) mm.

### Manipulators (fixes 4.3, 4.4, 4.5)

| | Arm A (precision) | Arm B (utility) |
| --- | --- | --- |
| Joints | shoulder yaw, shoulder pitch, elbow, wrist pitch, wrist yaw, wrist roll (6) | the same without wrist yaw (5) |
| Links | upper 0.200, forearm 0.165, wrist 0.045 m | upper 0.200, forearm 0.165, wrist 0.040 m |
| Ranges | yaw −95/+120°, pitch −215/+15°, elbow 0/200°, wrist ±115°, wrist yaw ±90°, roll ±270° | the same, no wrist yaw |
| Tip force (rated) | 20 N: 10.1 / 6.1 / 2.5 N·m at shoulder / elbow / wrist | 60 N: 30 / 18 / 7.2 N·m |
| Sensing | six-axis force/torque at the flange, macro wrist camera with ring light | joint torque sensing (motor current and output encoders) |
| Drives | strain-wave, hollow shafts (power and data pass through every joint), brakes | the same, larger frames |

- **Bays.** Each shoulder sits at the nose end of its bay. Stowed (the rig's rest pose), the upper link lies aft in the low layer and
  the forearm folds 180° forward over it, 46 mm above. With the cover open (150°), the bay is also open outboard. The shoulder can then
  yaw 95° outboard and pitch to −215°, which lets a docked drone reach beside the helmet. The arms are folded before docking, and the
  dock sequence folds them first.
- **Utility gripper.** It is clocked 90° on arm B's flange, so stowed it stands on edge under the cover. Working poses roll arm B −90°.
- **Grasp.** A grasp counts only if it is physically achievable. Both jaw-pad pairs of the utility gripper close on the 19 mm grapple
  post as line contacts. The gap is measured from the post axis (nearest pad point minus post radius) and must be under 1.5 mm, with no
  pad or jaw cutting into the post or the body. The driver bit must engage a fastener (≤ 3 mm) without entering the flange.
- **IK.** The drone's analytic IK (`eva_system.arm_ik`: yaw, a planar two-link arm, wrist pitch, wrist yaw with its 16 mm offset)
  solves every named pose. In the file, the `ik_A` / `ik_B` bones are IK targets for the animator (pole, 2000 iterations, limits
  clipped at ±180°). They are switched on by the `ik_A` / `ik_B` properties. Starting from the deployed pose, they reach every named
  target. A pose that needs shoulder pitch below −180° is reachable by the analytic solver only, so the named poses keep pitch above
  −180°.

### Sensors

Every sensor has a job, and none is decorative. One recessed dark nose window protects the forward sensors and can be replaced.

- **Navigation.** A stereo pair (0.196 m baseline, depth useful to about 3 m), flash lidar / ToF (0.1-30 m; cyan only on the emitter
  edge), the IMU in the avionics, four ToF proximity rangefinders and a star tracker on the dorsal tail.
- **Docking.** Two docking cameras on the dock face read the module's three retroreflector targets. After that, alignment is mechanical:
  the keel enters the channel.
- **Inspection.** A gimballed high-resolution camera with macro focus behind the window, thermal IR (8-14 µm, germanium window), task
  lights either side, and arm A's wrist camera for close range.
- **Embedded.** Dosimeter and magnetometer windows on the core, force/torque in the arms, N₂ pressure and temperature in the regulator.
  There are no antennas: communication uses a flush UWB / S-band patch.

The validation checks that, with the arms folded, no forward sensor's 30° cone out to 1 m meets the drone itself.

### Tools

One common coupling, GU-SIF-S: Ø40 mm, three kinematic pins, six sealed contacts, 600 N preload, roll key and manual release.

| Tool | Modelled | Use |
| --- | --- | --- |
| Precision gripper | yes | connectors, small parts, samples; 2 × 12 mm stroke, 25 N |
| Utility gripper | yes | larger objects, stabilising, handrail anchoring; 2 × 22 mm, 150 N, rated 300 N pull |
| Powered driver | yes | ¼ in hex, 0.5-5 N·m, reaction tab |
| Inspection probe | interface only | borescope for narrow gaps |
| Sampling head | interface only | particulate and scraping samples, sealed canister |
| Cleaning head | interface only | approved optical and radiator surfaces: microfibre and CO₂ snow |
| Anchor interface | interface only | clamps a standard hardpoint pin |

Arm A carries one tool and the core's trough holds two (the driver and the spare gripper). Arm B keeps the utility gripper. The
interface-only tools live on the airlock tool board and are swapped there.

## N₂ cold-gas propulsion

**Gas.** GN₂ in 30 MPa type IV COPVs (Z = 1.10, 313.6 kg/m³, 90 % usable). Delivered Isp is 65 s (the ideal vacuum value is about
73 s). The drone regulates to 1.4 MPa, which is carried across the dock coupling. The suit reserve regulates to 1.2 MPa, so with two
check valves the drone's feed has passive priority and no software is needed. N₂ never meets breathable gas: the suit's propulsion
manifold is a separate loop, and gas transfers only through the physical probe and poppet.

**Nozzles.** F = Cf·Pc·At with Cf 1.55 and area ratio 20:

- drone: 26 × 4 N, throat 1.53 mm, exit 6.9 mm, 6.3 g/s;
- suit: 16 × 8 N, throat 2.17 mm, exit 9.7 mm, 12.6 g/s.

**Budget.** Usable N₂ is 1.41 kg in the drone (2 × Ø104 × 400 mm, 4.98 L) and 0.63 kg in the suit reserve (Ø100 × 380 mm, 2.22 L).
Masses: crew 75 kg, suit 46, module 26, reserve hardware 1.6. The suit's dry mass is OPEN (EVA-028), so these are assumptions.

| Configuration | Mass | Δv | Total impulse |
| --- | --- | --- | --- |
| Drone alone | 26.4 kg | 34.9 m/s | 896 N·s |
| Docked, on drone gas | 175.7 kg | 5.12 m/s | 896 N·s |
| Suit reserve alone (drone away) | 149.3 kg | 2.67 m/s | 398 N·s |

For comparison, SAFER carries about 1.4 kg GN₂ on 24 × 3.6 N for about 3 m/s, and MMU 2 × 5.9 kg GN₂ on 24 × 7.6 N for about 20 m/s.

**Layout.**

- **Drone.** Four corner clusters: seven nozzles at the nose (LAT, LATB, LAT2 canted aft, DOR, DORB, VEN, LON) and six at the tail
  (LAT, LATB, DOR, VEN, LON, LON2). The nose clusters fire up and outboard, away from the helmet; the tail clusters fire down, outboard
  and aft, away from the seat. The LAT nozzles lean towards the dock face, 30° at the nose and 15° at the tail, and each has a twin
  (LATB) on the same line. The nose dorsal pair (DOR, DORB) is canted 45° and 54° outboard, because each arm rises from its bay just
  behind the nose cluster and passes over it.
- **Suit.** Four module-corner clusters of four: FWD, AFT, OUT and VERT. The FWD nozzles are canted up and out at the shoulders, and out
  and down at the lumbar. The AFT nozzles are canted out past the drone, and the VERT nozzles fire up at the shoulders and down at the
  lumbar, clear of the helmet and the seat.

**Authority (fix 4.1).** Authority is computed with non-negative least squares on each configuration's real nozzle positions (built
meshes) about its own CoM. All twelve signed pure axes are required, with no cross-coupling residual.

| Configuration | Live nozzles | Axes | Weakest force / torque | After any single valve failure |
| --- | --- | --- | --- | --- |
| Drone free flight | 26 | 12 / 12 | 7.0 N / 2.87 N·m | 12 / 12 |
| Docked (the drone flies the pair, suit reserve isolated) | 22 | 12 / 12 | 4.7 N / 1.74 N·m | 12 / 12 |
| Near-suit mode (within 1.5 m, VEN valved off) | 22 | 12 / 12 | 6.9 N / 1.73 N·m | 12 / 12 |
| Suit reserve alone | 16 | 12 / 12 | 6.9 N / 2.81 N·m | 9 / 12 |

Near a suit every +Z (back-away) source would be blocked if it fired along the dock axis. The canted LAT nozzles and their LATB twins
give the near-suit set full 6-DOF, including retreat, with any one nozzle lost, and their plume fringes pass outboard of the shoulders,
hips and hands on the whole approach (checked from 2 m to 0.03 m). **The suit reserve alone keeps 9 of 12 axes after a single
failure.** It is a rescue system, used to stop and return, not for routine flight.

**One propulsion system at a time.** Docked, the drone flies the pair on its own nozzles (VEN valved off) and the suit reserve is
isolated: its 16 plumes would cross the drone's nozzles and shell. During a docking approach the suit is the passive target, in free
drift. The reserve is armed only with the drone away (detached, arms deployed).

**Arming.** The drone's thrusters are armed in ready, flight, detached, arms, chase and approach. They are safed on a deck, ladder or
hull, under ship thrust (Burnbrow) and in the docked-arm assistance. Plume checks apply to whatever is armed in each state.

**Standoff.** A free-flying drone stays 2 m or more from crew (a 4 N plume falls to 1 Pa on its axis at 1.6 m), except on the docking
corridor in near-suit mode. Near-suit mode (VEN valved off) starts at 1.5 m.

### Near-suit fault tolerance

`eva_system.near_suit_faults()` stages the approach with the drone's real mass (26.4 kg) and inertia (slab model, [0.74, 0.56, 1.13]
kg·m²) and the built nozzle positions about the built CoM:

| Stage | Requirement (× 2 control margin) |
| --- | --- |
| Approach | 0.10 m/s from 0.5 m, lateral correction |
| Braking | 0.10 → 0.03 m/s between 0.12 and 0.05 m: 1.7 N along the dock axis |
| Alignment | 2° and 2°/s tip-off removed: 0.02 N·m on every axis |
| Capture | 0.02 m at 0.03 m/s into the tongue spring (0.15 J capacity) |
| Abort / retreat | back away at 0.05 m/s and stop, 1.7 N |

With every live nozzle failed closed in turn, every stage keeps its force and torque. Losing braking altogether puts 0.13 J into the
tongue spring, inside its 0.15 J. Uncommanded thrust (a nozzle stuck open) needs two failures: each valve has two seats with independent
drivers. A cluster's two parallel latch legs keep it fed if one sticks closed. Manifolds and vessels are design-for-minimum-risk (proof
1.5, burst 2.5, leak before burst), not failure tolerant. A stuck-open nozzle (the double failure) is detected in 0.25 s and
shut by its isolation valve: by then the drone has picked up 0.04 m/s and 2° (0.06 J if it hits the suit). The procedure, with a
threefold allocation for inefficient jet selection, uses 0.05 kg of the 1.41 kg usable N₂.

### Plume impingement

Two checks run on the evaluated (posed) meshes:

- **Core rays** (`plumes_all_states`): each armed nozzle's axis and a 12° cone out to 1.2 m. Nothing may be hit.
- **3D envelope** (`plume_envelope`, `eva_geometry.plume_envelope`): the axis plus five rings out to 30° × 16 azimuths, run out to the
  distance where the nozzle's on-axis pressure falls to 1 Pa (1.6 m for 4 N, 2.3 m for 8 N). Each first hit gets a Simons far-field
  pressure (cold N₂, n = 5, limiting angle 130°, normalised so the pressure integrates to the thrust). Limits: no core hit; visor,
  helmet, optics and sensors ≤ 1 Pa; anything else ≤ 5 Pa.

The envelope runs in every armed state for the live set of that state. It also runs on the approach from 2 m to 0.03 m (the free set
beyond 1.5 m, the near-suit set inside it) and through the drone arms' deploy sweeps (0.25, 0.5, 0.75) where that motion happens with
thrusters armed. The drone's own arms, tools, sensors and bay covers count as targets.

Limits of the model: far-field only, no reflection, no plume-plume interaction, no rarefied transition and no contamination transport.
The pressures are order-of-magnitude estimates. This is not a qualification. Cold gas is invisible. The plume cones in the scene
(collection `EVA_PLUME_VIZ`, excluded from renders) are diagnostic only.

## Dock

The dock runs along the upper and central back: the drone's keel drops into the module's recessed channel (70 mm wide, 26 mm deep, 15°
draft). The hardware is:

- a capture tongue for soft capture;
- four bolts for the hard lock;
- a power/data plug;
- an N₂ probe that enters a poppet;
- four elastomer load pads (8 mm design gap);
- three retroreflector targets;
- a red manual isolation valve;
- the mechanical release T-handle.

Nothing stands proud of the module when the drone is away.

**Docking sequence** (NLA `DRONE_DOCK_SEQUENCE`):

1. The arms fold.
2. Approach to 0.26 m in near-suit mode.
3. Alignment to 0.02 m on the docking cameras.
4. Contact, then capture.
5. Lock.
6. Electrical connection.
7. N₂ connection.
8. Propulsion hand-over.

`DRONE_UNDOCK_SEQUENCE` reverses it. The gas path is closed before the structure lets go, and release works with a dead drone.
Validation confirms that the drone touches the astronaut only through mating hardware (bolts, keel, load pads) and that the release
path is clear from 5 mm to 0.6 m. The bolt bores are not modelled at proxy detail.

## Structural assessment (preliminary)

`eva_system.structure()` takes limit loads × 1.5 against the ratings, with closed-form sections. **This is a preliminary analytical
estimate: no FE, no test, not a qualification.**

| Item | Limit load | Rating / capacity | Result |
| --- | --- | --- | --- |
| Dock moment | 167 N·m (a 556 N crew kick 0.30 m out on the drone; Burnbrow 27, arm B 30, arm A 10, crew push 2, driver 5) | 260 N·m | 1.5 × 167 = 250 ≤ 260 |
| Dock pull | 556 N (kick; Burnbrow 385, anchor gripper 300) | 2000 N | 834 ≤ 2000 |
| Latch bolts (4, 13 × 9 mm, 580 MPa shear) | 752 N ultimate per bolt | 67.9 kN | margin 89 |
| Arm A root | 10.1 N·m, 11.4 MPa | 430 MPa yield, 2 mm wall | margin 37 |
| Arm B root | 30.0 N·m, 20.8 MPa | 430 MPa | margin 20 |
| Tool coupling A | 1.36 N·m | 9.6 N·m gap-opening (600 N preload) | margin 3.7 |
| Tool coupling B | 4.92 N·m | 9.6 N·m | margin 0.3 |
| Anchor gripper | 300 N pull | holds within 15° of the tool axis | beyond 15° anchored work uses the keel socket |
| Emergency release | 69 N loaded (15 N spring, friction 0.15, 4:1 lever) | 90 N glove pull | passes |

The 150 N·m dock and hull-anchor target of the earlier studies is **too low**: a crew kick on the docked drone alone needs 250 N·m at
ultimate. Both ratings are now 260 N·m with the 2000 N pull unchanged (the hull socket copies the suit channel). Unknown: the channel
wall in bearing, the module-to-cuirass mount and the composite laminates. The moment reaches the wearer only through the hard torso.

## Operating configurations

| # | State | Dock | Suit pose | Drone |
| --- | --- | --- | --- | --- |
| 1 | EVA ready | docked | standing | arms stowed |
| 2 | Walk on a deck | docked | mid-stride (gravity) | stowed |
| 3 | Reach overhead | docked | right hand up | stowed |
| 4 | Crouch | docked | hands low | stowed |
| 5 | Climb a ladder | docked | on rungs | stowed |
| 6 | Free flight | docked (drone propulsion) | pitched 12° into travel, arms forward | stowed |
| 7 | Drone detached, arms folded | free | upright float, arms forward | stowed |
| 8 | Drone detached, arms deployed | free | the same | ready |
| 9 | Anchored maintenance | keel in a hull service socket | the same | A drives a fastener, B holds the grapple post |
| 10 | Braced under thrust (Burnbrow, 1.1-1.5 g) | docked | crouched in a foot rail, hands on a grab bar | stowed, carried by the dock |
| 11 | Free-flight chase (Brow Games placeholder) | docked | head-first glide, arms before the chest (an overhead arm sits in the shoulder FWD plume) | stowed |
| 12 | Docking approach | near-suit mode, 0.26 m out | standing | stowed |
| 13 | Docked-arm assistance (study) | docked | standing | assist |

**Reaction loads.** In free flight the drone can hold station against only a few newtons of steady tool force. Light inspection,
cleaning and connector work happen in free flight. Torqued fasteners and anything heavier need anchoring: the drone locks its keel into a
hull service socket that copies the suit channel (same bolts and probe, rated 2000 N pull and 260 N·m). The driver's 5 N·m and the
gripper's 60 N sit well inside that rating ([Structural assessment](#structural-assessment-preliminary)).

**Burnbrow.** Cold gas cannot hover at 1.1-1.5 g. The crew member stands on a rear-facing surface in a foot rail and holds on, and the
drone's weight goes through the dock frame into the legs.

**Brow Games (prepared, not implemented).** The chase state, a gate placeholder and the arming rules are in the file. A racer flying on
a detached drone has only the emergency reserve, so spending it for sport is unsafe. A proposed race rule ends a run below a reserve
floor. Rules, speeds, gate spacing and safety-officer roles are open.

### Docked-arm assistance (study)

With the drone docked, can its arms help the wearer? The prototype pose puts both flanges 0.40 m outboard beside the helmet, tools
pointing forward. Arm A holds a work light or camera over the shoulder, and arm B holds a part where the glove can take it. The pose was
found by a search over reach, joint ranges, arm-to-drone and arm-to-suit contact. Nothing nearer the face passes all of these.

| Check | Result |
| --- | --- |
| Reach | only beside and above the helmet; below the dock-face plane is unreachable without touching the shell |
| Helmet clearance | 264 mm (rule: ≥ 30 mm) |
| Emergency equipment (release handle, reserve valve and gauge, tether reels and hooks) | 221 mm (rule: ≥ 50 mm) |
| Contact with the astronaut | none |
| In view | tool working points at 102° and 101° azimuth, inside the 108° visor edge (peripheral, not central) |
| Reaction loads | arm A 20 N × 0.58 m = 11.6 N·m, arm B 60 N × 0.58 m = 34.7 N·m at the dock: inside the 260 N·m rating. A free-floating wearer would spin at up to 44 and 132 °/s² |
| Thrusters | both sets inhibited while the arms work |

**Verdict: a labelled study, not an operating mode.** The geometry and loads work, but the mode is safe only under these interlocks,
none of which is implemented: the wearer anchored (foot restraint or handrail), the drone docked and latched, both thruster sets
inhibited, crew-commanded hold-to-run, a force limit at each flange, and an emergency stop on the cuff. In detail, three conditions. The astronaut must be anchored (foot
restraint or handrail), because the arm forces react into the suit through the dock. The thrusters must be inhibited. The arms must run
in a crew-commanded hold-to-run mode with a force limit, because moving parts work beside the helmet. Its usefulness is limited to
holding a light, camera or part at the edge of view. It is documented as a study state, not a certified mode, and no human-factors
evaluation has been done.

## Rigging and runtime

- **Suit.** The wearer's MPFB `game_engine` rig is unchanged (53 bones, correctives, the five shared actions). `EVA_SYSTEM_POSES`
  holds the system poses: ready, walk, reach, crouch, climb, flight, deployed, burn and chase. The existing sockets remain, plus
  `SOCKET_DRONE_DOCK`, the dock frame that the drone follows.
- **Drone.** One armature, `RIG_EVA_DRONE`: body and dock bones, two arm chains, tool sockets and IK targets. Drivers on custom
  properties:
  - `docked`, `capture`, `latch`, `elec`, `n2` drive the dock mechanism;
  - `prop_mode` selects the live nozzle set (0 free, 1 docked or within 1.5 m of a suit);
  - `bay_A`, `bay_B`, `bay_A_aft`, `bay_B_aft` drive the bay covers, `lights` the task lights;
  - `grip_A`, `grip_B`, `tool_A_driver` drive the tools;
  - `ik_A`, `ik_B` switch on the IK controls.

  `DRONE_ARM_POSES` holds stowed, ready, maintenance and assist.
- **System file.** `EVA_SYSTEM_STATES` / `DRONE_STATES` key the 13 states (one per 10 frames, named markers). The dock and undock
  sequences are muted NLA strips. A Copy Transforms (`docked`) binds the drone to the suit's dock socket. Every thruster has an empty
  at its exit with +Z along the exhaust (`exhaust`, `thrust_n`): the runtime thruster sockets.
- **Suit controls.** The hand controller's `HCM_Link_1` (swing) and `HCM_Link_2` (telescope) carry `EVA_SYSTEM_POSES` tracks and
  `<link>_STATES` actions; the stops are in the suit's `eva_hand_controller` property.
- **Runtime export** (`export/eva_gltf.py`, run by `workflow.py eva`). Beside the two suits (`eva_characters.json`) it writes:
  - `eva_system.glb`: the system scene (both bodies, the dock, the hand controller, every thruster socket) with the 13 states baked into
    one clip;
  - `eva_drone.glb`: the drone alone with its armature and its actions (arm poses, dock and undock sequences, states);
  - `eva_system.json` (contract `eva_system v1`): the states with their frames, dock place, suit and arm poses and arming; every nozzle
    with its thrust, exhaust axis and docked inhibition; the drone's control properties, arm bones and joints; the hand controller's
    nodes, deploy poses and stops.

  `godot/scripts/check_eva.gd` is the runtime smoke test. It loads the three files at run time through GLTFDocument and checks the
  skeletons (53 bones), the animations, every driven node, that the drone leaves the dock in the detached and hull states and stays on
  it otherwise, and that the hand controller is deployed exactly in the states whose pose grips it. The export is reproducible from the
  built files; the Godot step runs at the end of `workflow.py eva`.

## Visual language

Engineering colour carries the function:

- warm off-white fabric;
- pearl off-white composite (cuirass, helmet, drone covers);
- graphite joints, core and structural edges;
- titanium interfaces;
- dark optical windows;
- muted blue for N₂;
- restrained amber for propulsion;
- small red emergency items;
- cyan only on the lidar edge and the status light.

Joint bands follow the bone axes, and arbitrary plates are removed. The helical restraint cords show the load path. Markings are role
bands and identification, without decorative glow. The Solid viewport keeps object colours by system.

## Validation

`validation/eva_system.py` reads the packed system file and writes `references/p1_eva_system.json`. Every item has one of four
classes, and only PASS counts as a pass:

- **PASS**: an automated check of geometry or physics on the built file met its rule.
- **PROVISIONAL**: an analysis ran and met its own targets, but the targets are design choices of this study, not owner canon.
- **UNVERIFIED**: an engineering-review item that geometry cannot settle.
- **FAIL**: an automated check missed its rule.

**Automated (PASS when met):**

- **File health.** Mesh integrity, unit transforms, everything packed, real scale.
- **Dock.** Dock offset 0 mm; contact only through mating hardware; release path clear from 5 mm to 0.6 m.
- **Plumes.** Core rays clear in every armed state; the approach corridor clear in near-suit mode; the 3D envelope inside its limits in
  every armed state, on the approach from 2 m and through the arm deploy.
- **Drone body.** Arms against the drone in every state; tools against the drone; joint limits in every keyed pose.
- **Suit.** Articulation: no soft-to-rigid contact (outer layer against the cuirass and module, trunk against the cuirass, helmet) in
  every system pose. Helmet: the swept head stays inside with ≥ 15 mm.
- **Hand controller.** Deployed at the glove where the pose grips it, stowed otherwise, no contact, clear of the release, inside its
  stops.
- **Sensors.** Forward sensor view with the arms folded.
- **Authority.** Free, docked, suit reserve and near-suit; the near-suit stages against every single failure.
- **Manipulators.** Forward kinematics of every named pose; IK controls reaching every target; utility grasp on the post; driver
  engagement.
- **Docked assist.** Clearance and view.

**Provisional:** the life-support budget and the structural assessment. **Unverified:** life-support capability (no hardware, test or
owner rows), structural loads (no FE or test), the docked-arm assistance (its interlocks are not built) and the plume model
(order-of-magnitude far-field estimate).

The suit's own checks (`validation/eva_fit.py`, `references/p1_eva_fit.json`) add pressure coverage on every frame and every body vertex
of every action, system pose and sweep, the suited envelopes and the access study.

**Result of the 2026-11-04 build: 28 PASS, 2 PROVISIONAL, 4 UNVERIFIED, 0 FAIL.** Pressure coverage passes for both wearers in every
EVA action, system pose and sweep. The worst plume pressure on anything inside the envelope is 0.8 Pa (no core hit, nothing on a
sensitive surface). The current result is in `references/p1_eva_system.json` (`summary`).

## Limitations

- Every value is PROTOTYPE, and none is IGNITION canon. EVA-004 suit pressure, EVA-008/009 consumables and EVA-028 suit mass stay OPEN.
  The life-support targets (8 h + 1 h, 30 min purge) are this study's design targets.
- A hot, hard EVA (350 W, +60 W heat leak) ends on feedwater at 6.1 h: plan it at 6 h or carry a second bladder.
- The life-support budget is steady-state: no transient thermal model, CO₂ bed sizing or condensation model.
- The plume model is far-field only (no reflection, plume interaction, rarefied transition or contamination transport); the outer
  layer's tolerance to cold-gas impingement is unknown. A free drone keeps 2 m from crew outside the docking corridor.
- The structural figures are closed-form estimates: no FE, no test, no dynamic analysis of the arms. Tool coupling B has a margin of
  0.3; the anchor gripper holds only within 15° of its axis.
- The suit reserve alone keeps 9 of 12 axes after a single failure (rescue use only). Docked, the suit reserve is isolated, so a drone
  failure while docked is handled by releasing the drone and flying the reserve.
- The hand controller's grip sits beside the flight-pose palm (7 mm gap); the fingers are not posed around it, and no grasp force is
  claimed. In Burnbrow the palms are 47 mm from the grab bar's surface: close, but no grasp is claimed. The restraint-pattern mobility
  torques and the scye and hip limits in extreme poses are unknown.
- The inherited interior `crawl` lifts the head out of the helmet; it is not suited motion and is locked in the runtime.
- The mass model lumps each line at the centre of its parts, which is good to a centimetre or two.
- The hull panel, service socket, replaceable unit, deck rail, ladder, Burnbrow foot rail and race gate are presentation props.

## Decisions carried from the studies

| Decision | Origin | Kept because |
| --- | --- | --- |
| Cold N₂ only; momentum conserved; gas crosses only the physical dry-break coupling | V1 | inert, storable, no contamination of optics or radiators |
| Independent suit reserve with full 6-DOF | V1 | the suit must get home without the drone |
| Regulated feed 1.4 MPa (drone) over 1.2 MPa (reserve), check valves | V1 | passive priority of drone gas, no software |
| Mechanical boot restraints, not magnets | V1 | the Brow skin material is not established |
| Burnbrow: no hover, stand on a rear-facing surface and hold on | V1 | 1.1-1.5 g is beyond cold gas |
| Chase is a push-off glide; a reserve floor ends a race | V1 | the reserve is for rescue |
| Hybrid rear-entry suit: rigid torso, integral helmet, one bladder, patterned restraint | V2 | fast donning, a back that can take a dock |
| 16 × 8 N suit thrusters in the module corners | V2 | full 6-DOF on the reserve |
| Asymmetric helmet with a wrap-around visor; brow lights and cameras | V3 | head sweep at the back, view at the front |
| Cuirass with a flexible abdomen; joint bands on the bone axes | V3 | the waist bends; no arbitrary plates |
| Robotic drone with two arms in lateral bays (configuration A, not a dorsal X-stow) | V3 | sensor face clear, vessels serviceable, arms out of the plume zone |
| 20 drone nozzles (five per cluster) | V3 | single-fault tolerant in free flight and docked |
| Capture tongue, four bolts, load pads, retroreflectors | V3 | soft then hard capture; camera alignment, then mechanical |
| Anchored maintenance in a hull socket that copies the suit channel | V3 | 7 N free-flight limit |
| Canted LAT nozzles and a near-suit mode (replacing "slow approach only") | consolidation | full near-suit 6-DOF including retreat |
| Soft layer trimmed at the cuirass, shoulder clearance search | consolidation | no hidden intersections |
| Utility gripper clocked 90°, grasp measured from the post axis | consolidation | a grasp that can happen |
| Life support split into packing volume and unverified capability | consolidation | honest scope |
| Neck ring, cuirass seal skirt and a scye sleeve that turns with the arm, each a modelled pressure part | final engineering | zero exposed skin, checked against the real geometry |
| Fold-out hand controller on a skewed hinge, stowed along the module side | final engineering | in the glove in flight, clear of the plumes, the arm and the release |
| Twin LAT and nose DOR nozzles (26 in all) instead of steeper cants | final engineering | near-suit single-fault tolerance with plume-clear lines |
| One propulsion system at a time (reserve isolated docked and on approach) | final engineering | no plume crosses the other body |
| Dock and anchor rating 260 N·m | final engineering | a crew kick on the docked drone needs 250 N·m at ultimate |

Rejected along the way: V2's shield drone with no manipulation (it could not do maintenance); V3's prescribed low-speed approach
as the fix for the missing +Z authority; the dorsal X-stow arms; the V1 outrigger pods (they widened the suit, and the module corners
do the same job).

## Owner question (draft, not posted)

`2026-11-03T15:00+00:00 — EVA companion drone and suit propulsion`: Wayfarer's EVA system adds a suit-docking companion drone (26.4 kg
wet, two arms, 26 × 4 N cold N₂) and a 16 × 8 N suit reserve. Should S&E carry it as crew equipment of WAYFARER_EVA_Y155 (a new
ASSET / EVA row), and are 30 MPa N₂, 65 s Isp, the 0.43 × 0.125 × 0.60 m rear-entry module and the PROVISIONAL life-support targets
(8 h plus 1 h, 30 min emergency purge) acceptable as the working case? Until then, every value stays PROTOTYPE.
