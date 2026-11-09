# T05 Stage B Revision 4: coils, launcher, structure, thermal and the review package

| | |
| --- | --- |
| Thread | T05, mechanical architecture and spacecraft geometry |
| Date | 2026-11-09 |
| Status | DONE (Revision 4); stops here, no further phase, nothing on `main` |
| Base | `735f9b6` on `claude/project-thread-ctwplp`; T00 inputs from `claude/project-thread-9rsgog` `f180b63` (handoff v1) and `853b867` (proposal checks), read only |
| Review file | `REVIEW_VERTEX_BLENDER.blend` (packed; not in Git); copy, renders and contact sheet in `review/vertex_blender_rev4_2026-11-09/` |
| Numbers | `rev4.py` → `rev4.json` (standard library); placements, ray cast and interference in `checks.json` (`rev4`, `rev4_launcher`, `rev4_raycast`) and `rev4_geometry.json` (handoff to T00) |

NON-CANON. Canon, Drive, production geometry, the FDP-1 and four-burn physics and the story are unchanged. Every Rev 4 part is
PROTOTYPE, PARAMETRIC_PLACEHOLDER or CONCEPTUAL_ILLUSTRATION. Masses and frequencies are beam-model and budget numbers, not
finite-element results. V4 is not shown to be feasible: three major blockers stay open (§6).

## 1. What changed in the drawn V4 (Rev 3 → Rev 4)

| Area | Rev 3 chosen | Rev 4 chosen | Kept as alternatives |
| --- | --- | --- | --- |
| Closure coils | P2 armour on C1's copied envelope (C2 too fat) | T00 shadowed build `COIL_ASM_T00` (winding, case tail, cryostat, LiH nose, Li channel, CFC) | R4_NOMINAL, R4_COMPACT, R4_STEEL_CASE, T03_3X, REV3_COPIED (scene `COIL_ASSEMBLY_SECTION`) |
| Coil cooling | tin loop to the hot root | Li loop, supply and return in tandem in each strut's shadow, Li/Sn HX and EM pumps at the hot root (`COIL_PLANT_LI`) | tin direct (`COIL_PLANT_SN`), Rev 3 `COIL_COOLING` |
| Coil supports | reaction ring at r 8.2 m (in the beam), no C2 ties | ring inside the shield shadow (outer edge 7.08 m vs shadow 7.33 m), T00 strut widths, six C2→C1 ties (`COIL_SUP_R4`) | `COIL_SUP_SIZED` |
| Dust guards | Rev 2 torus bumpers | cone bands edge-on to the burn (`DUST_GUARDS_R4`) | `DUST_GUARDS_REV2` |
| Stretch structure | S5 (S2 + 6 outer longerons r 34.8 m) | S5N: S2 + 9 longerons in the inter-tank gaps at r 31 m, T00 sizing, gap-plane lacing, spoked frames, isolated saddles, J1/J3 (`STRUCT_S5N`) | S1-S4, S5 |
| Access | K2 corridor | K2 on sliding mounts, robot stations, bay crawlways, outer robot rail, service tray on keel 150 (`ACCESS_R4`) | K1 |
| Launcher | B | B + B-modified overlay (`LAUNCH_BMOD`) | A, C, REV1, B-long, B-ray (`LAUNCH_BRAY`), rejected axis plug |
| Keep-outs | — | unstopped axis plasma channel (`AXIS_KEEPOUT`, VIS only) | — |
| Thermal | graded hot band, skirt B2 | unchanged: graded band at full area and true scale, R2 alternatives, B2 preferred | A, B, C skirts |
| Coupled ship | — | ghost only (`GHOST_COUPLED`) | — |

## 2. Coils (brief §7.1)

C2's thin winding (r 0.10 m) is now drawn apart from its case, cryostat and armour; Rev 3 had C1's 4.8 m envelope copied onto it.
T00's shadowed build puts the hoop case behind the winding (a tail of area 5.38 m² for C1, 0.08 m² for C2), so only the winding,
0.2 m of cryostat, a 0.56 m LiH neutron nose and the 30 mm Li channel with 5 mm CFC face the burn. Projected half-widths are 1.58 m (C1)
and 0.39 m (C2). Handling posts, manifolds and the service rail sit on the tail inside the half-width; the first build placed C2's
manifolds 0.6 m off the centreline, outside its 0.39 m shadow, and the ray cast caught them (fixed).

| Build | C1 h (m) | C2 h (m) | X-ray on rings (GW) | Note |
| --- | --- | --- | --- | --- |
| REV3_COPIED | 4.80 | 4.80 | 30.1 | Rev 3 drawn upper case |
| T03_3X | | | 11.9 | T03 winding only |
| R4_STEEL_CASE | | | 12.1 | layered, steel case |
| R4_NOMINAL | 2.99 | 0.85 | 10.0 | layered, T05 Rev 4 first draft |
| R4_COMPACT | | | 8.6 | thinner layers |
| **R4_T00_SHADOWED** | **1.58** | **0.39** | **5.04** (6.14 with struts) | T00 preferred, drawn as chosen |

Masses (T00 components, t): C1 case 1,196, winding 1,052, LiH 192, cryostat 109, struts 153, armour 4; C2 case 35, winding 159,
LiH 89, cryostat 47, struts 45, armour 2. Together about 3.1 kt; FDP-1 books none of the case (no double counting). Li plant
(T05 sizing on T00's 300 K rise, 5 m/s): 11.4 m³/s, 128 t Li, 85 t pipe, 123 t HX, 23 t pumps, 359 t plant, 22.8 MWe.

## 3. Interception, ray-cast on the drawn parts

Fibonacci sphere, 2,000,000 rays (1,600,000 cast toward the hardware hemisphere), first hit, T05 hardware of the chosen set only (canon parts not included), at T00's 412 GW escape X-ray.

| Category | Rev 3 chosen (4π share) | Rev 3 (GW) | Rev 4 chosen (4π share) | Rev 4 (GW) |
| --- | --- | --- | --- | --- |
| loop_bumpers_rev2 | 0.07600 | 31.31 | 0.00000 | 0.00 |
| closure_winding_drawn_by_nozzle | 0.03614 | 14.89 | 0.00000 | 0.00 |
| other:C2 | 0.02207 | 9.09 | 0.00000 | 0.00 |
| nozzle_loops | 0.00000 | 0.00 | 0.01992 | 8.21 |
| other:C1 | 0.01193 | 4.92 | 0.00000 | 0.00 |
| nozzle_struts | 0.00990 | 4.08 | 0.01062 | 4.37 |
| C1_armour_face | 0.00000 | 0.00 | 0.00812 | 3.35 |
| loop_guard_rings_rev2 | 0.00570 | 2.35 | 0.00000 | 0.00 |
| C2_armour_face | 0.00000 | 0.00 | 0.00395 | 1.63 |
| coil_struts_and_ties | 0.00347 | 1.43 | 0.00229 | 0.94 |
| wing | 0.00237 | 0.97 | 0.00312 | 1.28 |
| shield | 0.00289 | 1.19 | 0.00297 | 1.22 |
| loop_dust_guards_r4 | 0.00000 | 0.00 | 0.00070 | 0.29 |
| other:Cryo | 0.00042 | 0.17 | 0.00049 | 0.20 |
| launcher | 0.00006 | 0.03 | 0.00006 | 0.03 |
| other:Target | 0.00006 | 0.02 | 0.00006 | 0.02 |
| other:Burn | 0.00000 | 0.00 | 0.00004 | 0.02 |
| other:Beam | 0.00002 | 0.01 | 0.00002 | 0.01 |
| other:Fast | 0.00000 | 0.00 | 0.00000 | 0.00 |
| **total** | **0.1711** | **70.5** | **0.0524** | **21.6** |

The drawn T00 coils give C1 0.00812 and C2 0.00395 of 4π against T00's analytic 0.00836 and 0.00387 (within 3 %). Nozzle loops, nozzle struts and the shield are FDP-1/V4 parts already booked by T00; coil struts and ties (0.9 GW) and the wing aft spars (1.3 GW) are not (ISS-020). The first Rev 4 build caught C2 manifolds and side-by-side coolant pairs outside the thin C2 and strut shadows; both were moved (pairs now in tandem) and take nothing.

## 4. Launcher (brief §7.2)

T00: B (Rev 3) and B-long are NOT DEFENSIBLE: no layered D/3He target survives 13,700 g. B-modified keeps B's kinematics (289 m,
8.81 km/s, 196 Hz, 45 m open flight) with a 30 K gas-filled HDC capsule (wall 17 µm, limit 102,000 g), a contactless coilgun, a
split EM sabot caught in the shadow cone (28 MW) and a chopper at the snout tip: CANDIDATE, TARGET PHYSICS UNPROVEN. It stays the
preferred layout candidate and is drawn as an overlay on B: kinematic flexure mounts (not spine members), sabot catcher, CFC 2.5 mm
snout face, a capsule placeholder marker, and a red marker where the chopper rim sits in the axis plasma.

B-ray (T05 concept) puts the barrel on a burn ray, so the burn sees only its tip. T00 found the first-draft 45 m tip on the V4
stopping surface (43.5 m at 12°) and moved it to 56.5 m: 208 m barrel at 30,000 g, 11.1 km/s, 5.2 J/cm² and 10.3 MW/m² at the tip,
capsule safety factor 3.4, field up to about 6 T along the barrel. Drawn at az 45, because az 120 ran through a loop-1 nozzle strut
(struts at 0+60k and 15+60k, C1 struts at 30+60k leave 15° gaps). The barrel, stages and tip are clear of every drawn part; the mounts
land on the C1 strut ring and the shield frame as intended. The breech is 55 m off axis at X 9: its support is UNSIZED and drawn as a
red ghost, and capsules are filled at a station beside the breech (a feed from the module factory crossed the module equipment).
The T05 axial Li plug is REJECTED (T00: ions stop in under 1 mm, droplets vaporise, 6-880 Mt of Li per mission) and kept as a lane.

Interference (`checks.json` `rev4_launcher`, BVH triangle overlap on drawn hardware):

- B-ray against the chosen V4 hardware, S5N and the coil supports: only its two mounts touch, as intended (V4_CI_LBR_Mount_C1_Strut_Ring). B-ray hardware inside the axis channel: none.
- B-modified overlay against the V4 hardware: 0 overlaps (the first catcher position cut the fast-ignitor line and was moved).
- Hardware inside the 6° axis keep-out cone between the burn and the shield: 34 objects, including the shield X-ray face, the nine beam ports, the pellet bore, the fast-ignitor port, all six loop-1 nozzle struts, the loop-1 hot and cryo lines, the strut crawler rail, the four target trackers and launcher B's barrel end, snout, tip cartridge and chopper. These are FDP-1/V4 parts and B; Rev 4 does not move them (no shared-physics change). They are the ISS-022 blocker list.

## 5. Structure, access, thermal and dust (brief §7.3, §7.4)

Rev 3 error: `rev3.py` divided the per-member stiffness area by the member count a second time. S5 as drawn gave f1 0.077 Hz, not
0.2 Hz; corrected it needs 1.72 kt with r 0.76 m tubes 0.23 m from the tanks and 0.44 m inside B2. Rev 4 nests nine longerons in the
inter-tank gaps at r 31 m: T00 sizing r 0.611 m (t/r 0.1), 2.06 kt (2.01-2.23 kt for a 100-1,000 t bow), f1 0.2 Hz cantilever and
0.72 Hz free-free, 1.03 m to the tanks, 4.39 m inside B2 (ISS-018 resolved). Lacing (0.25 × longeron area, r 0.26 m) runs in the gap
radial planes, because chords between longerons would cut the tanks; frames carry spokes (a free ring ovalises at 0.14 Hz); tank
saddles are isolated at 10-30 Hz. J1 carries 350 MN·m and 2.9 MN shear at 0.01 g, 3.75 MN axial (beam model). K2 rides sliding
mounts and is not primary structure; tanks leave radially between longerons.

Thermal and dust are unchanged in principle: the graded hot band at full area and true scale, R2 kept, skirt B2 preferred. The coil
hot loop now ends at the Li/Sn heat exchanger at the hot-band root (C1 assembly 23.2 m aft of the band's aft edge). Cone dust guards
replace the Rev 2 torus bumpers.

## 6. Results for the joint report

| | Result |
| --- | --- |
| Resolved in layout | C2 drawn as a thin winding; reaction ring in the shadow; C2 load path closed; dust bumpers out of the beam (31 GW → 0.3 GW); S5 stiffness error found and corrected; longerons clear of tanks and inside B2; coolant lines fully shadowed |
| Reduced | coil X-ray 30.1 → 6.1 GW (T00 build); interception of the drawn V4 set 70.5 → 21.6 GW (0.171 → 0.052 of 4π) |
| Harder | structure 1.18 kt (Rev 3, wrong) → 2.06 kt; coil hardware about 3.1 kt; coupled ship 68.5 kt (V4 42.9 kt) |
| Unproven | target survival (B-modified, B-ray), EM armature and sabot at 30,000 g, REBCO neutron life behind LiH, FE of J1/J3 |
| Open blockers | ISS-022 axis plasma on the shield face and snout; ISS-020 struts and wing spars in the beam; ISS-024 coupled-ship growth |
| Rejected | layered targets (B, B-long), axial Li plug |

Next work (not started): a field-topology or target answer for the axis channel; a converged ship solve with the Rev 4 hardware; FE of
J1/J3; B-ray breech structure.

## 7. Validation (brief §10)

| Check | Result |
| --- | --- |
| Canon preservation | 6,249 canon objects identical to the append: True |
| Repeatable generation | two clean builds from the same tree: T05 geometry hash 3226be9fa6df1b66 both times, 3,835 T05 objects |
| Traceability | 1,533 Rev 4 parts carry issue_id, parameter, tech_id, geom_rev; missing: 0; every part keeps the six Stage B properties (missing props 0) |
| Dimensions | reaction ring outer edge 7.08 m inside shadow 7.33 m; longerons 1.03 m to tanks, 4.39 m inside B2; C1 assembly 23.2 m aft of the hot band; K2 2.96 m to keel 30 |
| Energy, no double counting | coil heat 6.14 GW from T00's armour ledger (rings + struts); the ray cast books each ray once (first hit); FDP-1 books no coil case; loops, nozzle struts and shield stay in T00's existing ledger |
| Thermal | Li loop 300 K rise, 5 m/s, 11.4 m³/s into the 1,800 K hot loop via Li/Sn HX; hot band kept at full area; no radiator area reduced |
| Mass | coil hardware about 3.1 kt (T00 components), Li plant 0.36 kt, S5N 2.06 kt, B-modified launcher 73 t; coupled ship 68.5 kt is T00's approximation, drawn as a ghost |
| Structural assumptions | beam model only (FDP-1 CFRP: 600 MPa, E 120 GPa, SF 2); no FE; J1/J3 loads quoted, not verified |
| Failed or open checks kept visible | axis channel (ISS-022), unbooked struts/spars in the beam (ISS-020), B/B-long NOT DEFENSIBLE, axial plug REJECTED, B-ray breech support UNSIZED |
| Restrictions | no Drive, canon, story, timeline, production geometry, FDP-1 or four-burn physics change; nothing on `main`; `tools/workflow.py checks` selects no tests, build target or inspection (work/ only) |

## 8. Views

| Camera | Shows |
| --- | --- |
| CAM_VTX_30 / 17 | whole V4 at true scale |
| CAM_VTX_44 / 45 | Rev 3 chosen above, Rev 4 chosen below (with the coupled ghost); aft close-up |
| CAM_VTX_06 | aft assembly, shield, coils, struts |
| CAM_VTX_37 / 38c | coil builds in section; T00 C1 close-up |
| CAM_VTX_39 / 36 | coil plant and cooling routes |
| CAM_VTX_42 / 43 / 46 / 21 | launcher lanes with verdicts, snout and keep-out, B-ray, snout cutaway |
| CAM_VTX_40 / 41 / 32 / 34 / 35 | section through the spine, load paths, structure lanes, J1 and J3 |
| CAM_VTX_13 / 23 | graded hot band and thermal circuits |
| CAM_VTX_28 / 29 / 11 | skirts, docking and dust clearance, maintenance access |
