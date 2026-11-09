# Non-destructive build workflow (T05, for Stage B)

Nothing here runs before D-10 Stage B is approved. Stage A ran only `screen.py` (pure Python).

## Inputs and isolation

- Commit: the branch head; every build writes the commit hash into `README_VERTEX`.
- Reads (never writes): `lab/variants/vertex-drive/` (convergence, registry, thread results), `lab/variants/fdp1/engineering/`
  (solve, `geometry.parts`, `tank_parts`), `src/wayfarer/functional_colors.py`, `data/` through `layout.py`, and the built
  `assets/wayfarer/WF_WAYFARER_001.blend` (opened read-only, appended into a new file).
- Writes only `work/vertex-blender/`: `params/*.json`, `WORK_VERTEX_BLENDER.blend`, `REVIEW_VERTEX_BLENDER.blend`, `renders/`
  (the `.blend` files and renders stay out of Git), and the copy to `/mnt/project-files/review/vertex_blender_<date>/`.
- `python3 tools/workflow.py checks` must select nothing under `src/`, `data/` or `tests/`.

## Build order (`build_vertex.py`, modelled on `build_fdp1.py`)

1. If `assets/wayfarer/WF_WAYFARER_001.blend` is missing: install Blender with `tools/cloud_toolchain.sh` and run
   `python3 tools/workflow.py pipeline --quick` (generated assets only).
2. Solve V0, V4, V5 (`convergence.generations()` → `fdp1.solve`), write `params/<g>.json`.
3. Factory-start Blender, append the canonical ship's collections once; record object names, counts and transforms.
4. Create the scenes (`COLLECTIONS.md`), link the ship instance into each; hide superseded drive and idle H2 objects per scene.
5. Draw each generation with `geometry.parts(R)` and `tank_parts(R)` where FDP-1 geometry fits, then the Vertex additions (closure
   coils, guard rings, split lines, sector clock, skirt alternatives, launcher, ignitor, tritium store, circuit bands, graded hot band,
   droplet bars), each with the property schema.
6. Overlays, labels, cameras, text blocks.
7. Checks: canon object list and transforms unchanged; every VAR object has the six properties; clearances measured (ring A to hot band,
   C1 to wing, dock corridor to skirt and wing, struts to hot band) and written to `checks.json`; mismatches become `ISSUES.md` rows.
8. Save `WORK_`, pack and save `REVIEW_` opening on `CAM_VTX_01`, render the handoff set, copy to project files.

Command (Stage B):

```
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python work/vertex-blender/build_vertex.py -- \
    [--gens V0 V4 V5] [--out work/vertex-blender/REVIEW_VERTEX_BLENDER.blend] [--render DIR] [--cams ...] [--params-only]
```

## Revisions

One revision pass per incoming thread result (T01-T04, D-21 if ever run): fetch the branch, update the JSON or registry override it
changes, rebuild, compare `checks.json`, log the source commit and what moved in `NOTES.md`, raise `revision`.

## Reproduction

From a clean checkout of a T05 commit, the build gives the same object list and `params/*.json` (FDP-1 solve is deterministic; it
takes under 1 s per generation). The review file is a product of the commit plus the built canonical asset named in `README_VERTEX`.

## Stage B as built (revision 1)

- `localise_ship.py` writes a self-contained cache copy of the built vehicle (`/tmp/wayfarer_vertex_ship_local.blend`; Blender's
  `make_local(type='ALL')`, about 75 s). Appending the linked vehicle and localising IDs one by one took tens of minutes.
- The canonical ship is appended once. Working copies link its objects into new instance collections (`WF_<SUB>_<g>_AFT/_BOW`) instead
  of appending it again (a second append took 247 s and doubled the file).
- `build_vertex.py -- --render DIR [--cams ...] [--size W H] [--no-save]`; it writes `checks.json` and `REVIEW_VERTEX_BLENDER.blend`.
- Workbench colour type is MATERIAL: collection instances drop per-object colour.

## Stage B as built (revision 2)

- `python3 work/vertex-blender/rev2.py` writes `rev2.json` (launcher, thermal, coil, dust and scale screening; standard library, run
  from the project root). `axis_survey.py` (Blender) writes `axis_survey.json`, the ray survey of what sits on the canon axis.
- `build_vertex.py` reads `rev2.json`. Anything with alternatives is an option collection `OPT_VERTEX_<g>_*` (launchers REV1/A/B/C,
  wings calculated/preferred, coil P1/P2 and supports, skirts, spine extension, dock routes, lane cores). `ASM_<g>` links the chosen
  ones; `ASM_V4_REV1_LAYOUT` keeps the Rev 1 layout. To swap an option, unlink it from `ASM_V4` and link another (scene
  `OPTIONS_LIBRARY` holds them all). The canon 1,800 K blade sections go to `WORK_VERTEX_<g>_CANON_HOT_BLADES` (V0 and the Rev 1
  layout show them; preferred V4 does not).

## Stage B as built (revision 3)

- `python3 work/vertex-blender/rev3.py` writes `rev3.json` (stretch loads, five structure layouts with strength, buckling and
  bending/axial modes, corridors, target and snout screening, coil cooling). `build_vertex.py` reads it after `rev2.json`.
- New option collections: `OPT_VERTEX_V4_STRUCT_S1..S4` (S5 = S2 + S3 linked together), `CORR_K1`, `CORR_K2`, `LAUNCH_B_LONG`,
  `COIL_COOLING`, `LANE_CORE_TB` (ghost tanks). Scenes `STRUCTURE_COMPARE` (side lanes) and `STRUCTURE_SECTION` (end view).

## Stage B as built (revision 4)

- `python3 work/vertex-blender/rev4.py` writes `rev4.json`: coil assembly builds and the X-ray ladder, the coil coolant plant (tin
  direct and Li loop), the corrected and nested structure cases, and, when the T00 copies are present, the T00 shadowed coil build,
  S5_N9_T00, launcher B-modified and B-ray, the axis plasma and the coupled-ship ghost. Inputs it reads: `t00_handoff_rev4.json`
  (copy of 9rsgog `f180b63` results/t05_handoff_rev4.json), `t00_proposals_rev4.json` (copy of 9rsgog `853b867`
  studies/rev4/results/proposals.json) and the T03 nozzle results (cached in `t03_nozzle_results_cache.json`).
- `build_vertex.py -- --rays N` (default 2,000,000) ray-casts the X-ray interception on the drawn V4 hardware for `ASM_V4` and
  `ASM_V4_REV3_CHOSEN` and writes `rev4_geometry.json` for T00. Every Rev 4 part carries `issue_id`, `parameter`, `tech_id` and
  `geom_rev = 4` besides the six Stage B properties.
- New option collections: `COIL_ASM_T00` (chosen), `COIL_ASM_R4/COMPACT/STEEL/T03`, `COIL_SUP_R4`, `COIL_PLANT_LI/SN`,
  `DUST_GUARDS_R4`, `STRUCT_S5N`, `ACCESS_R4`, `AXIS_KEEPOUT`, `AXIS_PLUG_REJECTED`, `LAUNCH_BMOD`, `LAUNCH_BRAY`, `GHOST_COUPLED`.
  New scenes `COIL_ASSEMBLY_SECTION`, `LAUNCHER_R4_COMPARE`, `REV3_VS_REV4`.
- Checks: `checks.json` `rev4` (dimensions, geometry hash, trace tags), `rev4_launcher` (BVH overlap of B-ray and B-modified against
  the drawn V4 hardware, hardware inside the 6° axis channel), `rev4_raycast`.

## Feasibility gate (2026-11-09)

- Inputs: `t00_gate_handoff.json` (copy of 9rsgog `43fac75` studies/gate/results/t05_handoff_gate.json). When present,
  `build_vertex.py` draws `GATE_A1_TILTED`, `GATE_A1_KEEPOUT`, `GATE_REJECTED`, `GATE_COUPLED_GHOST`, scenes `GATE_COMPARE` and
  `GATE_COUPLED`, and cameras CAM_VTX_47-50; the Rev 4 assembly is unchanged.
- `--kernel-rays N` (default 600,000) writes `axis_kernel.json` (first hit by polar angle, 0.5° bins to 30°). `--gate-rays N`
  (default 4,000) sweeps the A1 leak cone over tilt azimuth and writes `checks.json` `gate_A1`.
- `python3 work/vertex-blender/fe_s5n.py` (numpy, scipy) writes `fe_s5n.json`: frame FE of S5N, V4 full/dry, coupled mass,
  sensitivity cases. Report: `GATE_REPORT.md`; register rows in `ISSUES.md` "Feasibility gate register".
