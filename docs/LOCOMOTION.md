# Character locomotion (LOCO-001 Interior, LOCO-002 Exterior)

The two browser experiences put a real character on a physics body. **Physics owns the movement; the animation follows it.** No clip
moves a body: the walk, run and magnetic-walk clips were authored with root motion, and `WfCharacterRig`
(`godot/scripts/characters/character_rig.gd`) removes the Root bone's translation at load, keeps the travel it carried as the clip's
speed and plays the clip at *measured floor speed / clip speed*, so a planted foot keeps its place. A missing model is shown as a red
"CHARACTER MISSING" or "SUIT MODEL MISSING" label and reported to the page (`model: false`), never replaced silently.

Everything here is PROTOTYPE or SIMULATION_ONLY. FLIGHT_EVA stays HOLD. The engineering geometry and the baseline are unchanged.

## Explore Interior: ring A in spin gravity

- **Start.** `#interior` (and natively `godot --path godot`) starts on ring A's deck at the mouth of the landing well, Wayfarer
  undocked in COAST, both rings at 4 rpm, ring A's drum synchronized and open (the state the full excursion arrives in). The full
  station excursion is `#interior-excursion` (`-- --excursion`, and always for `--check-excursion`); its own check is unchanged.
- **Gravity.** Only the ring frame's field (`WfFrameField` RING_A, COAST): centrifugal ω²r plus Coriolis −2ω×v, about 0.49 g at the
  body centre (0.50 g at the floor, r 28.15 m). There is no gravity setting.
- **Body.** `WfCrewBody` (`human_iva`, 75 kg capsule) as before. The feet are a friction-limited contact (μ 0.6 × the support load):
  `walk_speed` sets the request, the contact decides what the feet achieve. A **jump** is one impulse m·dv along the body's up, taken
  only from a standing contact (`jump()`); afterwards the body is ballistic in the rotating frame until a floor contact. In the air the
  feet do nothing, so a second press does nothing (no double jump).
- **Controller** (`scripts/excursion/locomotion.gd`, `WfLocomotion`). States GROUND, TAKEOFF (the jump clip's crouch; the impulse at
  its end), AIR, LAND. W/A/S/D relative to the camera; S alone backpedals at 0.6 m/s with the walk clip reversed; the heading turns
  toward the request at up to 360°/s. The view, the camera and the model use the deck's radial up (toward the spin axis), not the
  apparent field, which a moving body's Coriolis part tilts.
- **Camera.** Third person (C toggles first person): 2.4 m behind and 0.55 m above the body centre on the ring's local up, ray-cast
  against the walk's own colliders. Where the overhead stops it, it tries the same bearing level with the follow point; with less than
  0.6 m of room (looking across a 0.9 m corridor) it switches to the eyes for that frame and hides the body rather than sit inside the head.
- **Training reset (R).** Back to the landing, standing still; labelled and counted. Only on ring A's deck.
- **Run** (LOCO-003). Run held runs in any direction but straight back. On a touch screen the stick pushed to its rim (90 % of its
  radius) runs, and a Jump button shows while walking: the phone had neither, so a phone player could only walk.
- **Doors** (LOCO-003). Use opens or closes the corridor or sector door in reach; the leaf slides aft into its pocket over 1.5 s and the
  doorway's collider is solid until it is fully open. The leaves are found through the manifest's `source_name` (the package names
  nodes by export id): looked up by source name directly they were never found, so Use only dropped an invisible wall and the shut
  leaf stayed where it was, which read as walking through a closed door.
- **Ladder** (LOCO-003). Use at the landing-well foot takes the crew-tube ladder and the trainee stays on the rungs; forward climbs and
  back climbs down (forward descends only with the view more than 60° down the tube), the choice held while moving. Before, the body
  stepped straight back onto the deck on the next frame, and a level view sent forward down rather than up. The climb clip's speed is
  its vertical travel (0.36 m/s), so it plays at the hands' 0.5 m/s, not ten times too fast. The ring has one deck: there are no stairs
  (owner, 2026-11-12: ladder only).

| `data/characters.toml [locomotion]` (PROTOTYPE) | value | reason |
| --- | --- | --- |
| player | newcomer | the trainee |
| walk / run / backpedal | 1.0 / 2.4 / 0.6 m/s | Froude number v²/(g·leg): a walk at 0.5 g stays below about 0.25, the run at about 1.2 |
| jump dv | 1.4 m/s | a moderate standing jump; rises dv²/2g ≈ 0.20 m at 0.5 g |
| turn rate | 360 °/s | |
| camera distance / height | 2.4 / 0.55 m | fits the 2.1 m corridors |

New newcomer clips (`human_system.py`, 30 fps, contact slip 0.0 mm): `run` (2.4 m/s, 150 steps/min, root motion), `jump` (0.27 s
crouch and extension), `fall` (loop), `land` (0.5 s), `step` (turning in place). The suit carries them as unsuited shared actions.

**Check** `-- --check-locomotion` (`check_locomotion.gd`, WF_GODOT_LOCOMOTION, runtime-export check `locomotion`, and the web
package's native reference), measured on 2026-11-08:

| check | result |
| --- | --- |
| start, model, every clip | ring A deck, newcomer loaded, 8 clips |
| field at the body | 0.486 g |
| walk request 1.0 m/s | 1.00 m/s, walk clip at rate 0.82 (authored 1.21 m/s) |
| run request 2.4 m/s (Shift) | 2.40 m/s, run clip at rate 1.00 |
| jump 1.4 m/s | rose 0.202 m (rotating-frame ballistics 0.203 m), landed after 0.85 s, 57 mm Coriolis drift; a second press in the air refused |
| camera, 6 views along the corridor | room in all 6; across the corridor it falls back to the eyes |
| training reset, body jump | back at the landing; at most 0.035 m beyond the body's own motion per step |
| doors (LOCO-003, 2026-11-12) | the shut door ahead blocks; Use slides its leaf open (every opened leaf moved) |
| ladder (LOCO-003, 2026-11-12) | Use at the foot keeps the trainee on the rungs; forward climbs 1.75 m in 4 s (climb clip); back returns to the deck, standing |

## Movement design (LOCO-003): why the first walk read as a robot

The owner found the trainee robotic (2026-11-12). The first clips moved the legs correctly but left out what the eye reads as a
person, and the runtime switched clips by speed thresholds. What was changed, and the reason for each:

| finding | change | source |
| --- | --- | --- |
| The pelvis travelled as a rigid block: no rotation, no drop, no side shift | walk and run carry the gait determinants: pelvic rotation ±4° (run ±6°), pelvic list ±4° (swing hip drops in single support), lateral shift over the stance foot 2.0 cm (run 1.0 cm) | Saunders, Inman & Eberhart, *J Bone Joint Surg* 35-A (1953), the six determinants of gait |
| Flat feet planted and lifted like stamps | heel strike rolling down about the heel (10° toes up), flat foot, heel rise about the ball to 22° at toe-off (run 8° / 28°); the source holds a foot still only while flat, so contact slip stays 0.0 mm | Perry & Burnfield, *Gait Analysis* (2010), ankle rockers |
| The arms swung a quarter cycle late (a sine against the legs' cosine) | each arm swings with the opposite leg, further forward than back; the elbow bends as the arm comes forward; the thorax turns against the pelvis (4.5°, run 8°); the head keeps facing ahead | Perry & Burnfield; Collins et al., *Proc R Soc B* 276 (2009), arm swing |
| The pelvis dipped 9 cm in double support (knees bent, a crouching walk) | the flat foot passes under the hip at 25 % of the walk cycle, so the leading heel and the trailing toe are equally far from it: 2.7 cm of vertical travel, in the range of normal walking; the run rides higher with less tuck | inverted-pendulum walking, Kuo, *Science* 309 (2005) |
| Walk and run were swapped at 1.28 m/s with a crossfade: two cycles of different length crossfaded scissor the legs, and the run played in slow motion just above the switch | an AnimationTree blends idle, walk and run by floor speed (walk→run over 1.3–1.9 m/s, around the Froude 0.5 walk-run change of 1.5 m/s at 0.50 g) with one shared gait phase that advances by distance over the blended stride, so the feet of both cycles strike together | the dynamic similarity of gaits, Alexander, *Physiol Rev* 69 (1989); Kram, Domingo & Ferris, *J Exp Biol* 200 (1997) for reduced gravity |
| The body stayed bolt upright while speeding up, braking and turning | the model leans about its soles into its horizontal acceleration, tan θ = a / g with g the deck's support load, × 0.7, at most 12°, smoothed over 0.15 s: at 0.5 g the same push leans twice as far as on Earth, which is physics the visitor can see | |

The values are PROTOTYPE display values (`GAIT` in `src/wayfarer/human_system.py`, `[locomotion]` in `data/characters.toml`),
within normal adult ranges, not motion capture. The EVA suit keeps the plain clip player; its one walk pose for the suit fit uses
the new walk.

Not done, and the next steps if the walk still reads stiff: foot IK on the curved deck (the stance follows the clip, not the
surface); the head turning toward where the camera looks (a LookAtModifier3D on the head bone); start and stop clips (a first step
and a settling step instead of the blend from idle); motion-captured clips retargeted through the existing solver
(`build/human.py` reads any armature through a bone map), for example a CC0 library, which would replace the procedural source.

## Explore Exterior: magnetic boots in drift

- **Start.** `#exterior` starts on the **magnetic walkway** (below) in DRIFT (no field at all): standing, both boots attached, the
  drone docked, the tether clipped to rail anchor ANC_AFT_00. `#exterior-hatch` (`-- --hatch`, the EVA check) is the old start at the
  airlock hold; `#exterior-first-flight` starts the guided First Flight. F5 resets to the start you came from.
- **Boots** (`scripts/eva/mag_boots.gd`, `WfMagBoots`; `data/eva_ops.toml [mag_boots]`). Each boot has its own state: OFF, SEEK (pad
  on, attaches when its sole is within 20 mm of the plate, closing below 0.30 m/s and within 25° of it), ATTACHED, SWING (lifted by the
  gait). The pad pull is a **bounded force**, 200 N per attached boot, added to the body like a field (`WfEvaBody`), never a joint. The
  feet's grip is that load times the sole friction 0.5, so a shear beyond it slides the boots (`slipping`), and a pull beyond it
  separates them: a boot more than 30 mm off the plate has broken away. The plate's contact takes the pull (no rebound).
- **Gait.** Driven by distance walked over the eva_mag_walk clip's stride (0.6 m), stance fraction 0.62. A boot lifts only while the
  other is attached; a stepping boot that would land off the plate stops the walk at the yellow edge. Walking speed is the clip's
  0.24 m/s. W/S walk, A/D side step, J/L turn.
- **Release.** V switches both pads off (the body keeps its velocity; with no field nothing moves it); Space releases and pushes off the
  plate with the legs (0.30 m/s, the same push as at a hold). From then on everything is the existing EVA physics: thrusters and gas,
  holds, tether, drone, rescue. V again re-arms the pads; drifting slowly back onto the plate they catch.
- **The walkway.** A ferritic steel plate bonded to the hull collar (the collar skin is not magnetic): x 128.6–138.2 m, 18–30° round
  the hull from the rail line, 3 mm. It clears the airlock fitting, ends before the Brow truss (x 138.7 m) and lies outside every
  keep-out (`tests/test_eva_ops.py MagneticWalkway`). The runtime draws it (grey plate, yellow edge band); it is not in the engineering model.
- **Suit clips** (`eva_suit.py`, `[mag_gait]` in `data/eva_suit.toml`): eva_mag_stand, eva_mag_walk (root motion, 0.24 m/s, 0.30 m
  steps, 45 mm lift), eva_mag_attach, eva_mag_release, eva_float. Pressure coverage and suit mobility pass for all of them
  (`workflow.py eva`: largest knee angle 54.6° in the walk against the 105° limit). On the walkway the suit plays stand or walk at
  floor speed / clip speed, attach and release once at each boot event, and floats otherwise.
  The drone glTF is exported docked in the suit frame; the runtime undoes that pose so the docked drone sits on the suit's back.

| `[mag_boots]` (PROTOTYPE) | value |
| --- | --- |
| attach force per boot | 200 N |
| sole friction | 0.5 (holds up to 0.116 g of shear on the suit with the drone docked) |
| capture gap / speed / angle | 20 mm / 0.30 m/s / 25° |
| break-away gap | 30 mm |

**Checks** (`eva_check.gd`, 10 added to the 34; 44 of 44 PASS on 2026-11-08): attached at the start in drift; holds 3 s with no
gas and no rotation (the uprighting moment follows the plate's smooth normal, not the faceted hull contact); walks 0.24 m/s with at least one boot down and 7 lifts in 8 s, no gas; stops at the walkway's edge 0.24 m short of its end; the
suit's own up-thrust (about 6 N) leaves both boots on; half the friction limit moves the body 0 m, twice the limit slides it 0.79 m;
V releases and the body then flies away on thrust; Space pushes off at 0.300 m/s with the tether still clipped; drifting back at
0.08 m/s the boots catch and stop it; on the bare collar beside the plate nothing attaches.

## Controls and conflicts (WfInput)

The keys below are the **suggested** inputs (CTRL-001, docs/MODEL.md "Player controls"): on a first visit the player chooses
every key marked *setup* themselves, and the suggestion applies only when they press "Use suggested controls".

| context | key | action | note |
| --- | --- | --- | --- |
| excursion | W/A/S/D | walk (camera-relative, *setup*) (camera-relative) | `player.move_*` |
| excursion | Shift | run (*setup*) | `exc.run`, held, pad L3; touch: the stick at its rim |
| excursion | Space | jump (*setup*) | `exc.jump`, pad RB: pad A is `ui.confirm`; touch: Jump button |
| excursion | C (also V) | third / first person | `exc.view`; the brief's camera key stays C, V kept for old habits |
| excursion | R | training reset | `exc.reset` |
| evaops | W/A/S/D | walk on the boots, thrust when flying | `evaops.fwd/back/left/right` share the excursion moves |
| evaops | J / L | turn on the walkway, yaw when flying (*setup*) | `evaops.yaw_left/right` |
| evaops | V | magnetic boots on / off (*setup*) | `evaops.boots`, new; V was free |
| evaops | Space | push off a hold, or off the walkway | `evaops.push`, one key for both |
| evaops | F5 | training reset | R is "thrust up" in EVA, so the reset stays on F5 |

Controls (the bottom-left button or F10) changes every row. E stays Use in both scenes.

## Web package

`workflow.py play-characters --out DIR` builds the player (character loop without the in-vehicle fit) and the Y155 instructor suit and
drone (suit build, drone, system, glTF export) from a clean checkout; `workflow.py web --characters DIR` copies them into the play
package's `generated/characters/`. CI runs both (`.github/workflows/web-explorer.yml`), and the web build runs the locomotion,
excursion and EVA checks natively on the same package before exporting Web. `tools/web_check.py` checks in the browser that each
experience starts where it should with its model loaded, that W walks (with the walk clip), that Space jumps and lands, and that the
boots walk, release and hand over to thrust.

## Open

- Every value in both tables, the walkway and the boot pad are PROTOTYPE: no owner row defines crew locomotion speeds, suit boots or
  a magnetic walkway. FLIGHT_EVA HOLD.
- The LOCO-003 gait and lean values (above) await the owner's hands-on review.
- Foot IK on the curved deck and a per-boot foot placement: the stance follows the clip, not the surface, so a foot on a facet edge can
  float up to the 8 mm chord sag of the 64-sided colliders.
- The suit has no run or jump of its own (it uses the unsuited shared actions under the burn presets); a suited hop needs suit mobility data.
- Touch controls for Explore Exterior.
