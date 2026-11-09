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
