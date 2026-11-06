# FDP-1 spatial model: visual grammar

`FDP-1_Spatial_Systems.blend` (built by `build_spatial.py`) shows FDP-1's engineering problem as objects in space.
The data, derived values and checks are the same as in the phase-1 diagram (`data/*.json`, `fdp1diag/model.py`).
Only the representation changed.

## Layers

- **Layer A, `LAYER_A_SPATIAL_MODEL`** (visible). This is the model you walk around.
- **Layer B, `LAYER_B_TECHNICAL_SUPPORT`** (hidden). This is the phase-1 board with its panels, formulas, charts and P01-P10 cards, parked at x = 700.
  - Show it with the Outliner eye.
  - Camera 10 shows it on its own.

## Encodings (each one is stated in the object's `encoding` property)

| quantity | object | rule |
| --- | --- | --- |
| fusion power | glowing orange sphere | volume ∝ power; 17.3 TW = radius 10 BU |
| power in a branch | tube | cross-section ∝ power, on the same scale (17.3 TW would be radius 6 BU). Tubes below 0.12 BU are drawn at 0.12 and flagged `drawn_min` |
| mass | grey block | volume ∝ mass; 20,760 t = a 20 BU cube. The ship block is stacked from its real mass items, coloured by function |
| force | cyan arrow | length ∝ force; 1 BU = 1 MN |
| radiator area | plate or square | true area at 1 BU = 40 m (wings, plates, the 1 g square) |
| nozzle loops | violet rings | to scale, 1 BU = 3 m, with the burn point at the centre of loop 2 |
| time | timeline bar | length ∝ years; 1 BU = 0.05 y |
| radiation | magenta rays | 240 rays share the escaping 199 GW. The number of rays that stop on hardware follows the record's solid angles (shield, loops) |

Colours follow the phase-1 functional palette:

- orange: fusion
- cyan: exhaust
- blue: propellant
- red: heat
- magenta: radiation
- grey: mass and structure
- violet: Fiji magnetics
- yellow: unresolved or requirement

Translucent objects are **ghosts**: what 1 g, or another hypothetical state, would need.

## Islands

1. **Fusion source.** The orb sits inside the nozzle loops and has four branches:
   - A: plasma into the jet (13.5 TW) and the uncollimated 3.51 TW. Its spread angle is schematic and flagged as such.
   - B: red heat filaments from each heat source in the ledger to the hot and warm manifolds.
   - C: magenta radiation rays, most leaving into space and 1.95 % ending on the shield and loops.
   - D: the driver loop, a subordinate branch. The plume returns 31.7 GW, 12.8 GW goes to the drivers, and 9 beams run back into the target.
2. **Thrust vs mass.** The ship is a 20,760 t block. Its propellant layers are one per burn. The 1.40 MN thrust arrow is barely longer than its head.
   A ghost arrow shows the 204 MN that 1 g needs, with rings at 0.05-0.5 g and the record's 0.0112 g ceiling at any size.
   At its tip stands the power-scaled 1 g propulsion hardware (555,302 t, ×26.7 the ship) next to a ship-sized block.
3. **1 g comparison.** A row of fusion spheres shows the power for 0.0069, 0.05, 0.1, 0.25, 0.5 and 1 g on the source's volume scale (×145 at 1 g).
   A faint 1 g ghost sphere surrounds the real source.
   The 1 g radiator square (278 km², 16.7 km side, at today's temperatures) lies on the floor under the whole scene.
4. **Heat management.** The wings, ship and nozzle loops are drawn to scale in plan, alongside today's 600 K and 1800 K radiator plates.
   The 800/1000/1500/2000/2500 K plates show the area that rejects all 101.5 GW at each temperature (hotter = smaller). The material limits above 1500 K are marked TBD.
5. **Mission.** The four burns and the coast make 6.35 y. The yellow bar at the canon LOCKED 6.0 y marks the open conflict. The 22.6 days of burning at 1 g is the sliver below.
6. **Requirement satellites.** Each P01-P10 problem is a yellow octahedron tethered to the object it constrains. Its collection (`A10.Pxx …`) toggles it.
   Each satellite carries the full register entry as custom properties: description, current, target, gap, status and depends.

## Cameras (timeline frames 1-10, markers bind them)

01 main overview · 02 fusion transformation · 03 thrust vs mass · 04 heat management · 05 1 g comparison ·
06 requirement overlay · 07 isometric (orthographic) · 08 mission and propellant · 09 temperature progression ·
10 Layer B technical board.

Labels copy the rotation of `VIEW_ALIGN`, an empty whose rotation is driven by the active camera through simple drivers (no scripts), so labels face whichever camera is active.

## Toward an interactive experience

The file is already structured for an interactive viewer such as Godot, three.js or a Blender add-on:

- Every Layer A object has a semantic name.
- Every Layer A object carries `component`, `classification`, `req_ids` and `value_keys`, plus the bound value (`value_W`, `mass_kg`, `area_m2`, `a_g`).

A viewer could do the following:

- **Hover and pick.** Read the properties and show the parameter rows from `data/fdp1_parameters.json` with source and class.
- **Acceleration slider.** Drive orb radius, thrust-arrow length, hardware-block size and radiator-square side from `Model.accel_rows`. All four follow closed formulas, so the ghosts become one continuous object.
- **Temperature slider.** Resize the radiator plate from σεT⁴.
- **Requirement focus.** Clicking a satellite dims every object whose `req_ids` lacks it.

These need the export to keep the custom properties (glTF extras do) and to treat each tube, block and plate as its own node. The generator already does both.


## V2 encoding rules (FDP-1_Spatial_Systems_V2.blend)

Hardware is opaque and muted, drawn at true size (1 BU = 1 m). Information geometry is translucent or emissive and
carries `layer = information`. Each information object states its encoding in its `encoding` property.

| quantity | form | rule | scale |
| --- | --- | --- | --- |
| power at a point (fusion) | sphere at the burn point | volume ∝ power | 17.29 TW = radius 25 m |
| power in transit (jet, plume, heat, driver loop) | tube along its path | cross-section ∝ power | 17.29 TW = radius 15 m; below 0.4 m drawn at 0.4 m with `drawn_min = 1` |
| force (thrust) | arrow along +X | length ∝ force | 1 m = 5 kN (1.40 MN = 281 m) |
| mass (budget items, departure, engine, feedback) | cube | volume ∝ mass | 20,760 t = 60 m cube |
| radiator area | the wing itself, target ghost wings, equivalent-area square | true area | 1 m² = 1 m² |
| radiation | straight rays from the burn point | ray count ∝ solid angle; rays end on the hardware they hit (shield, loops 1–3, struts) | 600 rays share 199 GW |
| requirement | marker, leader and label on the responsible hardware | one collection per problem | — |

- **Powers are in W.** The jet (13.5 TW) makes the thrust; the 3.51 TW of uncollimated plasma leaves in eight lobes.
  The spread angle of those lobes is schematic.
- **Rays are straight.** Magnetic fields do not bend photons or neutrons.
- **Heat flows from deposits to manifolds to radiators.** The hot loop (1,800 K) and the warm loop (600 K) stay
  separate. About 20.7 % of the hot heat goes to the existing Wayfarer hot blades (14,934 m², reused by the record).
- **Each radiator label prints P = εσ(2A)T⁴.** Planform A is drawn and emits on two faces (0 K sink). The record
  gives the two wings no mutual view. Wing ↔ Wayfarer-blade view factors are not modelled (P07).
- **The target layer is a ghost.** It is drawn red when no departure mass closes. It then shows the lower bound at
  today's mass, plus the mass-feedback passes. A cube bigger than 400 m is named, not drawn.
- **Target wings beyond the designed 3.57 km tip are flagged** (P09: deployment, structure and dynamics unverified).
- **Mass cubes sit on a rail 190 m above the ship.** Each one is tethered to its hardware and taken from the
  record's 15 budget items. Zero items are listed, not drawn.

## V3 encoding rules (FDP-1_Spatial_Systems_V3.blend)

Hierarchy, strongest first: ship, phenomenon, consequence, marker, text. Labels are selective; the small print sits in
`__DETAIL` collections behind the *Detail labels* toggle.

| element | form | colour |
| --- | --- | --- |
| canonical shield | the hardware, opaque | muted grey |
| protected volume | translucent frustum from the shield's aft plane, shrinking by L·tanθ + margin | blue-green |
| envelope boundary | thin outline rings every 100 m | blue-green |
| particle trajectories | thin lines; stopped ones end on the shield, passing ones run past the ship | grey and translucent magenta |
| critical hardware outside the envelope | the part (or the exposed run of a tube) re-drawn slightly inflated | red |
| hardware within the uncertain band | same, at the boundary | yellow |
| engine maximum radius vs protected radius | two rings at the station that sets the engine radius | red / blue-green |
| radiator planform inside / outside the envelope | overlay on the FDP-1 wings | blue-green / faint red |
| hypothetical shield | ghost disc and its envelope | translucent grey, labelled HYPOTHETICAL |
| P11 requirement | marker on the shield, collection `V2_3Y_REQ_P11` | requirement yellow |
| constraint board | one line per family, PASS / FAIL / UNRESOLVED / ASSUMPTION | green / red / yellow / grey |

- Exposed is not failed: each exposure label gives protrusion, exposed frontal area and the component class.
- Radiators are measured on planform; the FDP-1 wings are edge-on to an aligned stream, so their frontal area is
  edge thickness × span, and the thickness is UNKNOWN.
- Every P11 object carries `layer = information`, `component` and, where relevant, `status`, `protrusion_m`,
  `exposed_frontal_area_m2` and `component_class`.
