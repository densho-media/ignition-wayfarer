# Wayfarer character system

The shared production system for the two characters the ship is experienced through: the trainer, a dedicated Wayfarer flight
instructor, and the trainee, the first-time arrival the player follows (Tale `11_SCENE_LEDGER` S004A–D, `22_REVEALS_EXPOSITION` rows 16
and 18, `98_DECISION_LOG` row 22, all WORKING; S&E `98!A36`). The six Wayfarer crew of the tale are out of scope for character assets
(user direction 2026-10-08), and the IND-001 staging no longer shows them. Pipeline canon: S&E `15_MODEL_INTERFACES` C1–C3,
`98_DECISION_LOG` "Wayfarer character-production foundation", `99_SOURCES` (SRC-MPFB2 … SRC-BLENDER-STORM), Tale `12_WAYFARER_CREW`
"3D CHARACTER PRODUCTION INTERFACE" (TOC route `ignition.wayfarer.characters`), which this system applies to the induction pair. The loop
and the rules are in [AGENTS.md](../AGENTS.md); this file describes the system as built.

## Ownership

Tale owns identity and roles. The role is fixed (Q49, 15!A104, Tale 98!A26): a Y155 Great Union flight-safety instructor in
Spacer-close occupational test gear, and a configurable newcomer POV in a GU-issued induction undersuit; both leave before First
Ignition and neither joins the six crew. The instructor's name, sex and gender, body, face, hair and Burnmod profile are OPEN in Tale
`80_OPEN_VARIABLES` WTF-16 ("Nadia Varga" is only a candidate), so the 1.78 m male instructor mesh is a PROTOTYPE technical rig, not casting; Art Style owns depiction; Fashion owns clothing; S&E owns this pipeline. Nothing here is
character canon. Every body, face, skin, hair, clothing and facial choice is **PROTOTYPE** until its owner defines it, and MPFB's
phenotype defaults are never canon. The generic mannequins (`human_entry`) stay the independent scale gauge and the suited sweep in
`inspect` stays the clearance authority.

## Layout

| Concern | Where |
| --- | --- |
| External dependencies (one manifest) | `assets/external/manifest.toml`; tool `tools/external.py` (`workflow.py deps`) |
| Shared contract (`_human_system`) | `data/characters.toml` `[human_system]`, `[actions]`; `src/wayfarer/human_system.py` |
| Per person (`characters/<name>`) | `data/characters.toml` `[human.<id>]` recipes (fixtures `test_a`, `test_b`; induction pair `instructor`, `newcomer`) |
| Generator (Blender) | `src/wayfarer/build/human.py` → `assets/characters/WF_CHAR_HUMAN_<ID>.blend` (Git-ignored, regenerated) |
| Checks | `validation/human_rig.py`, `validation/human_fit.py`, `godot/scripts/check_characters.gd` |
| Export | `src/wayfarer/export/human_gltf.py` → `<out>/<id>.glb` + `characters.json` |
| Evidence | `references/p1_human_system.json`, `p1_human_rig.json`, `p1_human_fit.json`; renders in `runs/renders/p1/human_system/` |

The suggested `characters/_human_system/…` tree maps onto the repository's existing split (parameters in `data/`, pure modules in
`src/wayfarer/`, Blender generators, generated assets in `assets/`) instead of adding a new top-level convention.

## Dependencies

`python3 tools/workflow.py deps install` downloads the automatic entries, checks each SHA-256 and unpacks MPFB and its system assets into
an isolated Blender user-resource tree in the cache (`~/.cache/wayfarer/external`, override `WAYFARER_EXTERNAL`). Character scripts run
Blender with `BLENDER_USER_RESOURCES` pointing there, so the user's own Blender configuration is never touched, and they enable MPFB
explicitly (`--factory-startup` loads no add-ons). Nothing third-party is committed; a clean checkout plus `deps install` rebuilds the
same characters (verified 2026-10-07: identical content fingerprints from an empty cache).

| Dependency | Pinned | SHA-256 | License | Role |
| --- | --- | --- | --- | --- |
| MPFB | 2.0.17 (latest stable: GitHub release 2026-07-22, tag commit 80919fa; Blender extensions platform; master's 2.0.18 is unreleased) | `4f0a879d…48239a87` | code GPL-3.0-or-later; bundled assets CC0; output unrestricted | required |
| MakeHuman system assets | `makehuman_system_assets_cc0.zip`, unversioned, Last-Modified 2024-04-14 | `b542127a…a0107` | CC0 (each of its 140 asset files carries the CC0 header) | required |
| Blender Human Base Meshes | 1.4.1 | `811f43ac…b3515` | CC0 | optional reference, nothing incorporated |
| Quaternius UAL / UAL2 (Standard) | not acquired: manual entry | — | CC0 per pack page | optional animation source |
| Blender Studio Storm | studied only | — | CC-BY | optional reference, nothing incorporated |

MPFB requires Blender 4.2+; it runs headless under the installed Blender 5.2.2 (`HumanService` scripting API). Quaternius serves its free
downloads from itch.io behind a Cloudflare bot challenge, so the manifest marks both packs `acquisition = "manual"`: download the Standard
zip by hand into the cache's `downloads/`, then pin its file name, size and SHA-256 in the manifest. Paid tiers are not used. MakeHuman
community assets are not used; any added later needs its own license check (not assumed CC0).

**mpfb-mcp: not adopted.** Evaluated at master `fccd20bd18` (2026-10-03): no release or tag, self-described early beta, 34 tools that
wrap MPFB's own `HumanService` through a companion add-on and a live interactive Blender session over a socket. This repository drives
Blender only as headless CLI runs, and every operation the system needs (create, phenotype, rig, body parts, skin, bake) is a direct
`HumanService`/`ExportService` call there. The bridge would add a second, non-reproducible control path and nothing deterministic; it stays
replaceable later because the recipes are plain MPFB `human_info` data.

## Generation

`python3 tools/workflow.py characters [--only <ids>] [--no-fit]` runs the whole loop (about 3 minutes for four humans) and prints a
compact summary: build → rig review → glTF export (into `runs/<stamp>-characters/glb`) → Godot check → in-ship fit (under the write
lock, because it reads the vehicle asset). For each recipe `build/human.py`:

1. bisects MPFB's `height` macro until the baked body is within 5 mm of `stature_m` (sole to crown, rest pose);
2. generates the human from an MPFB `human_info` dict (`human_system.human_info`: phenotype, the `game_engine` rig, eyes, eyebrows,
   eyelashes, skin), then bakes it: helpers removed, targets and masks applied, shape keys flattened, at most four deform weights per
   vertex, renormalized;
3. applies the review materials: `clay` (flat neutral, for a character whose skin no owner has defined) or an MPFB `GAMEENGINE` texture skin,
   and with `suit = true` the PROTOTYPE body-close under-suit on every face outside the skin groups (head, hands), or, with `outfit`,
   the outfit's zones (below);
4. checks the rig contract, adds the driven corrective shape keys (`build/correctives.py`, "Validation") and bakes the shared actions; for the induction pair it also bakes the S004A greeting pose
   (`stage_S004A`, `characters.greeting`) and stores its vehicle-frame placement on the rig;
5. saves `WF_CHAR_HUMAN_<ID>.blend` with `GEN_`/`ART_` collections (`common.begin/save`, milestones backup) and writes a content
   fingerprint (vertex positions, weights, corrective offsets and drivers, bone heads, every key) to `references/p1_human_system.json`.

Regeneration is deterministic: rebuilding gives the same fingerprints, and the reopened saved file matches the build.

## Outfits (FUT-003 S004 pass)

The induction pair wears a representative outfit (ART-S004-2026-10-10; roles Q49; Fashion Y155 through the local brief
`docs/SURFACE_BRIEF.md`). It dresses the role, not a cast person, and every colour is PROTOTYPE. `data/characters.toml` `[outfit.*]` lists
material zones, and `build/human.dress` paints each body face with the last zone it matches. A face belongs to its vertices' most common
dominant deform bone, and zones select by bone, rest height between two bone heads, |x|, the fraction along the bone, the limb's outer side
or an upward normal. There is no added geometry, so the rig, the weights, the actions, the content fingerprints and the in-ship fit are
unchanged (rebuilt 2026-10-10: all four fingerprints and `p1_human_rig.json` / `p1_human_fit.json` identical).

- **Instructor:** a Great Union flight-safety instructor in Spacer-close test gear. Charcoal Spacer suit with grey outer panels on the
  limbs, a fitted Great Union deep-blue vest from waist to shoulders with white shoulder boards, a safety-orange harness (chest straps and
  belt), a silver seal collar, a dark wrist unit on the left forearm, dark flight gloves and boots.
- **Newcomer:** a Great Union-issued induction undersuit. Light grey with muted-navy outer and side panels, the same harness and seal collar,
  a high-visibility yellow visitor band on the left upper arm, bare hands to a clean cuff, and boots.

Limits: zone edges follow the base mesh's faces, so they are stepped up close. The boots follow the base mesh's toes. The kit's volumes
(the instructor's vest thickness, the newcomer's kit pack, mask, comms) stay on the IND-001 proxies. A garment mesh or a texture would
need its own fit check. Evidence: `runs/20261010T130000Z-s004-outfit` (Cycles lineup, Godot greeting and couch views).

## Rig contract

| Item | Contract |
| --- | --- |
| Skeleton | MPFB 2.0.17 `game_engine`: 53 bones, UE-style names (`Root`, `pelvis`, `spine_01..03`, `neck_01`, `head`, `clavicle/upperarm/lowerarm/hand_*`, `thigh/calf/foot/ball_*`, three bones per finger), all flagged deform (`Root` carries no weights); listed in `human_system.BONES`, a build fails on any difference |
| Units, axes | metres; +Z up; the character faces −Y (Blender); glTF/Godot +Z front (`MODEL_FRONT`), +Y up |
| Origin, root | floor, centred between the feet; `Root` bone at the origin carries root motion (ground translation; vertical for the climb) |
| Rest pose | MPFB A-pose, arms about 45° down |
| Stature | sole to crown of the baked body, rest pose, ±5 mm of the recipe |
| Skinning | linear blend, ≤ 4 influences, normalized, plus the corrective shape keys below |
| Control rig, IK/FK | none in the runtime asset; poses come from the solver below. An animator control layer (MPFB Rigify) is optional and never exported |
| Face | no facial rig or shape keys yet; the planned representation is MPFB's ARKit face-unit targets as shape keys (CC0), not generated |
| Shape keys | MPFB targets are applied at build; the only shape keys are the eight driven correctives (`corrective_<joint>_<l|r>`, below), exported as glTF morph targets with their weights sampled into every clip |
| Materials | one body material (clay or texture skin) plus the under-suit or the outfit's zone materials; eyes, eyebrows, eyelashes as separate meshes |
| LOD | one level (body 13,380 vertices); MPFB's CC0 proxy meshes are the LOD path when the runtime needs one |
| Frame rate | 30 fps; actions start at frame 0, so Blender frame f is glTF time f/30 |

## Actions and retargeting

Shared actions, PROTOTYPE motion authored procedurally in `human_system` (not mocap): `idle` (4 s loop), `walk` (1.2 m/s, 108 steps/min,
root motion), `sit` (onto the sector seat height, `sector_whitebox.seat_height_m`), `crawl` (hands and knees, 0.35 m/s, the drum
chambers' crawl rail), `climb` (vertical ladder at the tubes' rung pitch, `human_entry.spoke_rung_pitch_m`, root motion up). Each frame
also lists the limbs held still (feet, hands, knees), which the checks use.

Every motion source goes through one retarget layer, the source format in `human_system`: per frame, world joint positions (the keys of
`characters.skeleton`), the head's up and facing, the root and the held contacts, plus the source's rest frame. `build/human.py`
`Solver` poses a `game_engine` rig from it: arms and legs by two-bone IK to the source's wrists and ankles with the elbows and knees as
poles (so bone-roll differences between rigs never matter), pelvis, spine and head by the change of their source frames from rest, feet
by the ankle-flexion change, fingers and clavicles held at rest. A differently sized source maps by the leg-length ratio about the ankle
height, so straight legs stay straight and planted feet stay planted. The solver's matrices equal Blender's evaluated pose (1 µm).

- The procedural library is generated at each character's own stature and segment proportions (measured on its rig), so its contacts
  are reachable by that body.
- `test_b`'s actions are retargeted rig to rig from `test_a`'s baked actions (read back as joints, scale 0.870): the path an external
  library such as Quaternius UAL takes, with its own bone map into the same joint keys (to write when the archive is acquired).
- Held-contact drift on the target rig: 0 mm (walk, climb), ≤ 2.4 mm (crawl hands), ≤ 4.8 mm (`test_b` idle and sit, retargeted).

## Validation (2026-10-08)

**Blender.** `test_a` (1.800 m, MPFB defaults), `test_b` (1.618 m, female, older, lighter, textured skin), the instructor (1.780 m,
male, heavier) and the newcomer (1.700 m, MPFB's neutral body) build from one system with an identical 53-bone contract, ≤ 4 weights
and no unweighted vertex; the fixtures' fingerprints are unchanged from 2026-10-07. The rig review poses each body through seven test
postures and samples every action: shoulders, elbows, spine, neck and hips deform without collapse at everyday angles; the extreme
postures (arms overhead, elbows at 140°, trunk forward 45°, deep squat, knee 120°) are flagged for linear-blend artefacts: volume loss up
to 9 % in the deep squat and up to 0.8 % of edges stretched beyond 1.6×, at the groin, armpits and knees. Review sheets:
`runs/renders/p1/human_system/<id>_sheet.png`.

**Corrective shape keys** (`build/correctives.py`, CHAR-001, PROTOTYPE). Each body gets eight, one per side for the knee, hip, elbow and
shoulder. Each is generated, not sculpted: the body is posed at the joint's flagged angle with the shared solver (knee 120°, hip 100°,
elbow 140°, arms overhead), a delta mush (Blender's Corrective Smooth against the bind shape, 10 iterations at 0.5) restores the local
shape, and the difference goes back through each vertex's skinning matrix into a rest-space key, limited to the joint's bone weights and
side. A driver on the bone's swing off its rest direction (the knee and elbow through the lower bone, the hip and shoulder through the
upper) ramps the key from 35 % of the way to the flagged angle (about 33–45°) to full at it (95–128°). The review's trunk posture needs no
key of its own: the solver turns the pelvis with the trunk, so it bends the hips. Against plain skinning, on the four bodies: the knee-120°
high step is no longer flagged; the worst stretched edge drops from 4.2–8.4× to 2.5–4.9× in the deep squat and from 4.3–5.4× to 2.8–3.2×
arms overhead, and the worst crushed edge in the folded elbow from 0.10–0.17 to 0.16–0.30 of its length; in the actions the worst edge
falls in sit (up to 6.8× to 3.7×), crawl (7.8× to 4.7×) and climb (6.0× to 4.4×). The deep squat, arms overhead, the elbows at 140° and
(for three bodies) the trunk posture stay flagged; the squat's closed-mesh volume drops a further 0.7–0.9 points (it counts the thigh
pressing into the calf); `test_a` and the newcomer cross the stretch flag at arms-side-90 by 0.02 ‰; `test_b` keeps one crushed edge
(0.10) arms overhead. Delta mush halves the visible pinching; it doesn't model contact. Evidence:
`runs/20261010T160000Z-correctives` (close-ups with the keys muted and active).

**Godot.** `check_characters.gd` loads each GLB at run time (`GLTFDocument`): skeleton equals the contract, mesh top equals the stature,
every action is present with the right length, every check bone lands where Blender evaluated it (0.0 mm), each body carries its eight
corrective blend shapes and every clip drives them as Blender evaluated them (deviation 0.000), and held contacts drift
≤ 7.1 mm (the newcomer's crawl hands). The exporter keys every bone in every clip (no channel optimisation), because Godot does not
reset untracked bones between clips. The in-ship swap check (`induction_swap.gd`) is retired with the boarding walk
(tag `archive/pre-cleanup-2026-10-29`).

**Human scale.** `human_fit.py` poses the four bodies at every generic-mannequin station (same feet stations, same rail and rung grips,
same body axis: floating with the rings stopped, radial-down in ring A, aft-down under thrust), at both greeting poses and on the
S004B treatment couch, and intersects the posed body with the vehicle meshes nearby. Hands and feet may sit 3 cm in what they hold or
stand on. Results (`references/p1_human_fit.json`, cutaways in `runs/renders/p1/human_system/fit/`, the proxy at the same camera as
`<id>_greeting_<id>_proxy.png`):

- FIT for all four bodies: entry chamber, trunk, ring-A despun vestibule, refuge (floating); sector landing (radial-down); the tube
  elbow floor ladder under thrust (aft-down); both greeting poses (the instructor on the deck band, the newcomer through the outer hatch).
- Ladders (ring-A tube ladder radial-down, the 17 m trunk ladder aft-down): with the mannequin's stance (ankle 7 cm short of the rung
  axis, body straight above it) a real torso, head and thighs sit 2.4–4.2 cm in the rungs, stiles and arrest rail. Standing on the ball
  of the foot on the rung, hips 0.13–0.17 m further off the ladder (the instructor, the broadest, 0.16–0.17 m) and knees flexed, every
  body clears with the hands still on the stiles (least clearance: head 0–7 mm to the arrest rail, torso 9–40 mm) and stays inside the
  tube. The tube and trunk geometry is not the problem; the climbing posture is.
- Hatch step under thrust: the thigh sits 2.9–3.6 cm in the sector hatch frame in the mannequin's stance. No tried stance clears it:
  hips up to 0.12 m back, knees bent up to 0.20 m, and the body slid up to 0.12 m either way along the rungs. Sliding away from the
  frame puts the legs into the step's own rungs, and the hand on the far stile is 0.11–0.24 m short. Open for the next HUM-001/Q47
  review (a step further from the frame is a route-hardware change, not a character one).
- Greeting: S004A happens with both entry hatches open, as in the stills, so the fit opens them (`DOCK_ENTRY_CTRL` in memory; every
  other station keeps the saved, closed state). Coming
  head-first and facing fore, the newcomer's left is +w: the right hand takes the instructor's right, and the left takes the near (+w) hatch
  rim, elbow inboard so the forearm reaches the rim from the chamber side and not across the frame. The hands meet 0.09 m inboard of the
  proxies' point, where the MPFB instructor's right hand reaches from the deck band. The pair reaches every grip in its own role (0.0 m); of the
  other bodies only the fixture `test_b`, the tallest, misses the handshake (0.04 m as instructor, 0.06 m as newcomer; fixtures aren't cast). Least clearance as newcomer: head
  0.43–0.45 m, torso 0.30–0.34 m, the rim arm 9–12 mm to the hatch frame. `human_fit.py --restage` still searches a newcomer offset and
  handshake point for a body that doesn't fit.
- Couch (S004B): FIT. The staging lays the body on the mattress (`sector_whitebox.MATTRESS_M`, 0.08 m on the `medical_table_m` top;
  it used to use the bare table top). The back depth is measured on the posed body (`build/human.py posed_back_depth`, the newcomer
  0.102 m), so the lowest point of the back touches the mattress (least clearance 0.0 m). The fixture `test_a` keeps 1.1 cm of
  torso in it; the fixtures aren't staged there.

## Blender to Godot

`human_gltf.py` exports each character with its skeleton, skinned meshes and one glTF animation per NLA track (the five shared actions
and the `stage_S004A` pose), and writes `characters.json` (contract, actions with loop, root-motion and held-contact data, Blender's
check-bone positions in Godot axes `(x, z, −y)`, and the stage placement). `runtime-export` exports the characters into its disposable
package when `assets/characters/WF_CHAR_HUMAN_*.blend` exist and runs `check_characters.gd` before publishing.
`characters.json` carries every stage (`stages`: S004A for both, S004B for the newcomer, each with its placement, action and check
bones; `stage` stays S004A). No runtime scene swaps the proxies for the MPFB bodies since the boarding walk was retired; the walk keeps its proxy body.

## Licenses

Generated characters contain only CC0 material: MPFB's bundled base mesh, targets, `game_engine` rig and weights, and the system-asset
skin, eye, eyebrow and eyelash files named in the recipes. MPFB's GPL code runs as a Blender extension and is not part of any output
(MPFB LICENSE.md section D). No Storm, Quaternius or community material is incorporated. Attribution owed: none today. When material
from a CC-BY source is reused, record it here and in its manifest entry before committing.

## EVA suit

The pair also wears WAYFARER_EVA_Y155, the guided-EVA pressure suit ([EVA.md](EVA.md)). It is built on the saved character files without
changing them: the same rig, the same body, the same correctives and the same shared actions. Each suited asset
(`assets/characters/WF_EVA_<ID>.blend`) adds suit layers, bone-mounted parts and sockets, and twelve EVA actions solved by this file's Solver.

## Open

- Quaternius UAL/UAL2: acquire the Standard archives by hand, pin them, write the UAL bone map into the joint keys, retarget 3–5 actions.
- Facial setup (ARKit face units), hair, clothing and skin: wait for Art Style and Fashion; the S004 outfits are a PROTOTYPE material pass.
- Contact-aware correctives (thigh on calf in the deep squat) if a shot needs them; an animator control layer.
- The ladder stance and the hatch-step clash above.
- The instructor's identity, body and outfit (Tale WTF-16) and the newcomer's configurable body; every body value is PROTOTYPE until
  Tale, Art Style and Fashion supply them. If the newcomer becomes player-chosen, the recipe becomes a set of allowed phenotype ranges over the same contract.
