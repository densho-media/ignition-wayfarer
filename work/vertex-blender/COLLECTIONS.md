# Collections, colours and properties (T05 Stage A)

## Scenes

| Scene | Contents |
| --- | --- |
| `CANON_WAYFARER` | the built ship, appended, untouched (four-nozzle drive, idle H2 vessels shown) |
| `VERTEX_V4` | canonical ship linked into the scene, superseded drive and idle H2 vessels hidden; bow assembly offset +275.4 m in this scene only (T-B); `VAR_VERTEX_V4` |
| `VERTEX_V0` | the same with `VAR_VERTEX_V0` (bow +122.4 m) |
| `COMPARE_SIDE_BY_SIDE` | canon, V0, V4 at true scale on parallel axes (Y offsets 0 / −500 / −1,000 m for the hull cameras); `VAR_VERTEX_V5` as a wire ghost over V4's lane |
| `COMPARE_SPAN` | canon, V0 and V4 wings at full span, the V5 and band tip circles as outlines, a 1 km scale bar |
| `VERTEX_CUTAWAY` | V4 aft assembly only, 120° wedge removed toward −Y |
| `BRAKING_EXPOSURE` | V4 turned engine-first, dust stream and shadow overlays |
| `RADIATOR_ALTERNATIVES` | R0 (calculated), R0-graded, R1-W3 and R2 tandem as outlines on one V4 hull |

The ship is linked as one collection instance per scene from a single appended copy, so canon objects exist once and are never edited.
The bow offset is a second instance of the bow-assembly collections with a transform, the original instance's bow collections hidden
(same as `build_fdp1.py`).

## Collection tree (per generation g = V0, V4, V5)

```
VAR_VERTEX_<g>                    pink (COLOR_07)
  VAR_VERTEX_<g>_01_REACTION_ZONE   burn point, stand-off sphere, density ghosts, injection path
  VAR_VERTEX_<g>_02_NOZZLE          loops (sectors, cryostats, lattice, armour shoes), closure coils, guard rings, sector split lines, sector clock
  VAR_VERTEX_<g>_03_SHIELD          shadow shield layers, ports, plug, beam dumps
  VAR_VERTEX_<g>_04_DRIVERS         galleries, beam lines, final focus, fast-ignitor line
  VAR_VERTEX_<g>_05_THERMAL         wings (hot band, circuit bands, spars, droplet bars), low-loop panels, headers
  VAR_VERTEX_<g>_06_POWER           pulse storage, conditioning, feeds
  VAR_VERTEX_<g>_07_FUEL            target factory, launcher, catcher, tritium store, T-B (or T-A) vessels, feed lines
  VAR_VERTEX_<g>_08_STRUCTURE       module skin and frames, thrust adapter, struts, coil struts
  VAR_VERTEX_<g>_09_MAINTENANCE     rails, hatches, crawler, sector exchange path, human figures (linked from 20_HUMAN_SCALE)
  VAR_VERTEX_<g>_10_DUST_PROTECTION skirt (three extents), bumpers, edge bumpers (alternatives as child collections _A/_B/_C)
  VAR_VERTEX_<g>_11_KEEP_OUT        hardware and crew cones, plume keep-out, X-ray sphere
VAR_VERTEX_OVERLAYS               pink; every object ILLUSTRATIVE
  OVL_FIELD_LINES  OVL_PLASMA  OVL_DUST_STREAM  OVL_DROPLET_SHEET  OVL_SECTOR_CLOCK  OVL_HELICITY  OVL_TIP_BRACKETS  OVL_LABELS
```

V5 gets only `_01`, `_02`, `_03`, `_05` and `_11`, drawn as wireframe (display type WIRE), named `GHOST_`.

## Colours

Hardware takes `src/wayfarer/functional_colors.py` PALETTE keys through the Atlas record's `colour` (READINESS tables): MAIN_PROPULSION
(loops, coils, launcher, drivers), SHIELD (shield, armour, skirt, bumpers), WARM_RADIATOR, HOT_RADIATOR, LOW_RADIATOR (cryostats, low
panels), POWER, HELIUM3, DEUTERIUM, HYDROGEN, STRUCTURE, SENSORS_COMMS, SERVICE. Overlays use the FDP-1 VIS colours (PLASMA, XRAY,
SAFE, BEAM). Evidence status shows in the viewport by alpha: ES opaque, PP 0.6 alpha with a dashed edge (wire overlay), CI 0.15 alpha,
GHOST wire. Materials are simple functional ones, never production materials.

## Custom properties (every VAR object)

| Key | Values |
| --- | --- |
| `vtx_id` | Atlas record (`VTX-03D`) or `T05-PR-n` for a T05 PROTOTYPE object |
| `generation` | V0 / V4 / V5 |
| `evidence_status` | ENGINEERING_SUPPORTED / PARAMETRIC_PLACEHOLDER / CONCEPTUAL_ILLUSTRATION (from `geometry.status`) |
| `representation` | HARDWARE / VISUALIZATION / MIXED |
| `source` | `solve:V4 layout.x_burn`, `case:V4_warm_band`, or `studies/<thread>/<file>.json@<commit>` |
| `unbooked` | names the unbooked mass when the object carries one (closure-coil structure, skirt, launcher, tritium store) |
| `alternative` | `R0`, `R0G`, `R1-W3`, `R2`, `SKIRT_A` ... for alternative geometry |
| `revision` | integer, raised by each Stage B revision pass (`NOTES.md` log) |
| `wf_owner` | `wayfarer.t05` (never `wayfarer.p0`, so no generator claims it) |

Geometry stays `REP_PROXY`. Text blocks in the review file: `README_VERTEX`, `VERTEX_PARAMS_<g>.json`, `VERTEX_PART_STATUS`,
`VERTEX_COLOR_LEGEND`.
