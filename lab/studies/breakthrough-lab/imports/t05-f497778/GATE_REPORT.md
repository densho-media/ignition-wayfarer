# Vertex propulsion feasibility gate: T05 report

Kind: study. Status: FOR OWNER EVALUATION, research only, NON-CANON. Brief: "WAYFARER: Vertex Propulsion Feasibility Gate"
(2026-11-09). Base: T05 Revision 4 at `08f3c8d` (kept whole as the reference assembly `ASM_V4`); T00 gate results from
9rsgog `43fac75`. No canonical geometry, Drive, lore or production physics changed. Nothing goes onto `main`.

**Verdict: the Vertex architecture stays BLOCKED.** One field topology (A1, tilted closure) is analytically promising in a
vacuum-field thin-shell model and fits the drawn V4 ship at chosen tilt azimuths. It is not a demonstrated plasma solution, it
fails once the coupled ship's shadow cone grows to 9.4°, and the structure that carries it misses its stiffness target in FE.

## 1. Phase 1: the axial plasma (ISS-022), T05 geometry support

- **The 6° cone is not physical.** It is the angular radius of the shield seen from the burn point (6.37°). T00's channel
  half-angle is 3.5° (band 3.05-6.35°), 342 J/cm² per pulse at the shield face; recommended keep-out 4°.
- **What receives the energy** (T05 ray cast, 600,000 rays, 0.5° bins, `axis_kernel.json`):

  | polar angle | first hit |
  | --- | --- |
  | 0-0.9° | launcher B snout tip and chopper (45-47 m) |
  | 1.0-6.4° | shield W face (64.7-66 m); beam ports at 3.5-4°, fast-ignitor port at 1-2° |
  | 5.2-5.4° | loop-1 strut feet, loop-1 hot and cryo lines, crawler rail, 4 trackers |
  | beyond 6.4° | 64-84 % escapes; the rest hits loop-1 struts, coil struts, wing aft spars |

- **Relocation:** the launcher snout, the beam ports and the fast-ignitor port are on the axis because they must reach the target;
  they cannot leave the channel, only be protected or retimed. Loop-1 strut feet, lines, rail and trackers can be moved outside 4°.
- **Alternatives (T00 analysis):** E shadow coil REJECTED (only narrows the channel, hoop up to 2,311 MN at 81 MA); A2 transverse
  plug REJECTED (static torque tens of GN·m); S centre insert REJECTED (needs a 197.5x reduction); B target cap research only;
  C twin splayed nozzles open, not analysed; **A1 tilted closure RETAINED: ANALYTICALLY PROMISING (vacuum-field thin shell), NOT a
  demonstrated plasma solution.**

## 2. Phase 4: layouts drawn (T05)

All in the gate build of `REVIEW_VERTEX_BLENDER.blend` (review copy `REVIEW_VERTEX_GATE.blend`); Rev 4 is untouched and shown beside every lane.

| collection / scene | content |
| --- | --- |
| `GATE_A1_TILTED` | C1 (R 22.13 m, 162 MA) and C2 (R 41.59 m, 13 MA) tilted 14° as a rigid pair: assembly envelopes at T00 half-widths 1.58 / 0.39 m, windings, turned loop ghosts L1-L3, six C1 struts re-landed on the reaction ring at ship az 30+60°·k, C2 ties, Li supply and return lines in tandem behind the struts, turned nozzle axis |
| `GATE_A1_KEEPOUT` | the leak cone, centre polar 10.83°, radius 2.99°, drawn to 700 m: 23.7 GW, 339 J/cm² at 65 m, 8.95 J/cm² at 400 m |
| `GATE_REJECTED` | E, A2 and S lanes, labelled REJECTED |
| `GATE_COUPLED_GHOST` | T00 coupled ship: tank farm envelope r 57 m, N9 ring at 51.2 m, shield r 11.4 m, 9.4° shadow cone, failed B-ray at 459 Hz |
| scenes `GATE_COMPARE`, `GATE_COUPLED` | Rev 4 reference above, A1 below, rejected lanes below that; the coupled ghost over V4 |

**A1 on the drawn ship** (`checks.json` `gate_A1`): a leak-cone ray sweep over the tilt azimuth (72 azimuths, 5° steps) against the
whole V4 assembly and the canon working copy finds the leak clear of all hardware at 25-40, 80-100, 140-155, 205-220, 260-280 and
320-335°. Near 0/180° it hits the wing aft spars and loop-1 struts; near 60°·k it hits loop-1 struts (about 16 % of the rays).
Chosen azimuth 90°, the middle of the 80-100° window. Findings:

- the tilted C1 envelope reaches polar 7.31° against the shield rim at 6.37° (T00 conductor minimum 8.68°): clear;
- **clash:** the tilted C1 envelope and winding overlap loop-1 struts 4 and 5; they must be re-landed (not done; FDP-1 loop hardware
  belongs to T00's field model);
- the nozzle turns 2.68° off the ship axis: the thrust line is offset, a steady torque nothing books (trim, gimbal or a mirrored
  pair, which is lane C);
- A1 only works while the shadow cone stays at or below about 7.5°; the coupled ship's 9.4° shadow breaks it (ISS-024).

Exposed and protected components are coloured by function and labelled with their evidence status; no cosmetic detail was added.

## 3. Phase 5: S5N and the J1/J3 joints

**Beam model (Rev 4, unchanged):** S5N 2.06 kt, f1 0.2 Hz cantilever, 0.72 Hz free-free, J1 350 MN·m at 0.01 g.

**Finite-element result (new, `fe_s5n.py` → `fe_s5n.json`):** Euler-Bernoulli 3D frame of the drawn S5N, 557 nodes, 975 elements,
rigid joints and saddles, lumped tank mass, CFRP 120 GPa, 600 MPa at SF 2. This is a frame FE, not a shell or joint FE.

| case | structure | total | first global bending (cantilever) | lowest mode | root moment 0.01 g | worst member |
| --- | --- | --- | --- | --- | --- | --- |
| V4 full tanks | 1,864 t | 29.6 kt | 0.110 Hz (beam 0.2) | 0.047 Hz torsion-like | 385 MN·m (beam 350) | keel ring 0.61 |
| V4 dry | 1,864 t | 4.6 kt | 0.274 Hz | 0.115 Hz | 64 MN·m | keel ring 0.12 |
| coupled mass on V4 geometry | 1,864 t | 83.1 kt | 0.066 Hz | 0.028 Hz (in slosh band) | 1,069 MN·m | keel ring 1.64 (fails) |

Sensitivity (full tanks): rings and spokes ×4 area, 2,897 t → 0.132 Hz; lacing ×4, 2,564 t → 0.119 Hz; longerons ×2, 2,852 t →
0.114 Hz; rings, spokes and lacing ×4, 3,598 t → 0.148 Hz.

- The beam model is unconservative by about 1.8x. Frame and ring shear flexibility governs; adding area does not reach 0.2 Hz.
- The full-tank lowest mode (0.047 Hz) lies within a factor of two of the 0.022-0.040 Hz slosh band, and with coupled mass it falls
  inside it (0.028 Hz).
- **The roughly 2 kt package is not sufficient under the revised coupled mass**: it overstresses the keel ring and is far below the
  stiffness target. (The coupled case hangs 117 kt-class tank mass on the V4 geometry; the coupled tank stretch is not drawn.)
- J1 and J3 joints were not modelled as joints; the frame assumes them rigid, so a real joint makes these frequencies lower still.

## 4. What remains unresolved

1. A plasma check of A1 (MHD or PIC): needs D-21; nothing here demonstrates the tilted leak in a real plasma.
2. Target physics: no layered D/3He target survives launch (ISS-023); B-modified stays TARGET PHYSICS UNPROVEN.
3. Mass closure: the coupled ship converges only on a relaxed free-free spine at 117 kt (ISS-024); on the T05 cantilever basis it
   does not converge.
4. A spine that reaches 0.2 Hz: needs a new frame concept (deep rings or continuous shear walls), then shell FE of J1/J3.
5. A1 integration: loop-1 strut re-landing, thrust-line torque, and the 7.5° shadow limit against a growing shield.
6. Lane C (twin splayed nozzles) is unanalysed.

## 5. Most decisive next experiment

**A coupled-mass closure of the A1 ship at a shadow cone ≤ 7.5°.** If no converged ship keeps the shield's shadow under 7.5°, A1
fails on geometry alone and no plasma run is worth authorising. If one exists, a single D-21 MHD run of the A1 tilted leak at that
point decides the rest. On the T05 side, the parallel test is a frame FE of one redesigned spine section (shear-wall frames) to see
whether 0.2 Hz is reachable at all at coupled mass.

## Files

`build_vertex.py` (gate lanes, sweep, scenes, cameras CAM_VTX_47-50), `t00_gate_handoff.json` (copy of T00's gate handoff),
`axis_kernel.json`, `checks.json` (`gate_A1`), `fe_s5n.py`, `fe_s5n.json`, `ISSUES.md` (gate register). Renders and the review
`.blend` are in the project review folder, not in Git.
