# Camera and render plan (T05 Stage A)

Workbench draft (object colour, cavity, outline) for every camera while iterating; Cycles `review` quality (16 samples) only for the
handoff renders. Orthographic cameras carry a scale bar object in frame. All cameras are named `CAM_VTX_nn_<NAME>` and carry
`render_scenes` (as FDP-1). The review file opens on `COMPARE_SIDE_BY_SIDE` through `CAM_VTX_01`.

| Camera | Scene | Type, frame | Shows | Purpose |
| --- | --- | --- | --- | --- |
| 01 SIDE_COMPARE | COMPARE_SIDE_BY_SIDE | ortho side, from −Y looking +Y, width 900 m | canon, V0, V4 hulls and drives, wings cut at frame edge, V5 ghost | true-scale length comparison (289.5 / 559 / 766 m) |
| 02 TOP_COMPARE | COMPARE_SIDE_BY_SIDE | ortho top (from +Z), width 900 m | the same from above: wing roots, loops, docks | in-plane layout, ring and dock clearances |
| 03 THREEQ_COMPARE | COMPARE_SIDE_BY_SIDE | perspective 35 mm, all three ships | form at a glance | whole-ship silhouette before any detail |
| 04 SPAN_FULL | COMPARE_SPAN | ortho top, width 22 km | V4's 20.3 km wing span with canon (290 m) and V0 (7.1 km) at the same scale; tip circles for 670 K, driver 0.45, 12 km/s launcher | the handoff's required span view: the radiators dominate |
| 05 SPAN_ROOT | COMPARE_SPAN | ortho top, width 2.5 km | the hot band (r 10-847 m) and root against the hull and rings | where the 1,800 K hardware is |
| 06 AFT_ASSEMBLY | VERTEX_V4 | perspective, aft three-quarter | shield, closure coils, loops, struts, guard rings, wing roots | the nozzle and its neighbours |
| 07 CUTAWAY | VERTEX_CUTAWAY | perspective, wedge toward camera | burn point, stand-off sphere, coils, shield layers, module (launcher, catcher, ignitor, tritium store, pulse storage) | interior of the drive end |
| 08 BRAKING_EXPOSURE | BRAKING_EXPOSURE | perspective from the dust direction (engine-first) | skirt alternatives A/B/C, shadow cone, exposed loops, wing edges | T02 exposure in braking |
| 09 RADIATOR_ALTS | RADIATOR_ALTERNATIVES | ortho top, width 22 km | R0, graded R0, W3 and tandem R2 outlines | radiator architectures side by side |
| 10 RADIATOR_STATES | VERTEX_V4 | perspective at a wing root | droplet sheet on (burn) and off (coast: frame only); panel alternate | deployment / flow states |
| 11 MAINTENANCE | VERTEX_V4 | perspective 50 mm at the shield-face rail | 1.75 m figure (HUMAN from `20_HUMAN_SCALE`), sector exchange path, module hatch | human scale and access |
| 12 DOCK_HAB_CLEARANCE | VERTEX_V4 | perspective at the primary dock (X 131.65 m, az 195°) | visiting-vehicle corridor, ring A/B, wing forward edge, skirt extent | docking and habitat clearance |
| 13 RING_HOTBAND | VERTEX_V4 | ortho side, width 300 m | ring A and the hot-band forward edge, calculated against graded | T05-ISS-001 |
| 14 C1_WING | VERTEX_V4 | perspective close to C1 at the wing plane | C1 envelope, hot-band aft edge, shield | T05-ISS-002 |

Renders: 2560×1440 for the handoff set (01, 02, 04, 06, 07, 08, 09, 11, 12), 1920×1080 drafts. Copied with the review file to
`/mnt/project-files/review/vertex_blender_<YYYY-MM-DD>/`.

Scale note for camera 04: at 22 km frame width the canonical ship is 1.3 % of the frame (about 34 px of 2,560). It is drawn with a
leader label and an inset frame (camera 05 at 2.5 km) rather than enlarged. Nothing is rescaled for legibility.
