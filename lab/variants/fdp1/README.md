# FDP-1: Fiji Drive Pulsed prototype (lab/variants/fdp1)

FDP-1 is a research prototype of a pulsed D–³He fusion drive for G.U. WAYFARER 001. It is not canon. Nothing in `src/`, `tests/`,
`tools/`, `godot/` or `web/` reads this folder. The approved ship on `main` keeps its four-nozzle drive, and the built assets are not
touched.

## Open the review

Open `REVIEW_FDP1.blend`. It is packed and needs no script. The owner copy is
`/mnt/project-files/review/fdp1_2026-11-04/REVIEW_FDP1.blend`. It opens on scene `FDP1_WAYFARER`, looking through `CAM_03_AFT_ASSEMBLY`.

| Scene | Shows |
| --- | --- |
| `FDP1_WAYFARER` | The whole built ship with FDP-1 attached (`WORK_FDP1`, collections `FDP1_00`…`FDP1_12`). The superseded four-nozzle drive is hidden, not deleted. With tank layout T-B, the bow is moved forward 122.4 m, in this file only. The keep-outs (`FDP1_11`) are hidden; click the eye to show them. |
| `FDP1_CUTAWAY` | The aft assembly alone, with a 120° wedge removed toward −Y: burn point, nozzle loops, shield layers, module interior and driver galleries |
| `BASELINE_WAYFARER` | The untouched built ship, as on `main` |
| `COMPARE_PROPULSION` | The baseline ship above, FDP-1 below, at the same scale |
| `COMPARE_TANKS` | The existing 13-vessel farm against the FDP-1 farm (13 existing vessels plus 49 proposed, translucent) |
| `FDP1_ENERGY_FLOW` | The labelled energy-flow diagram |

The cameras are `CAM_01`…`CAM_10`. Each carries the scenes it renders in `render_scenes`. Text blocks inside the file:
`README_FDP1`, `FDP1_FUNCTIONAL_COLOR_LEGEND`, `FDP1_ENGINEERING_RECORD.json` (the full record the geometry was drawn from) and
`FDP1_PART_STATUS` (ENGINEERED / PLACEHOLDER / ILLUSTRATIVE for every part).

Colours follow `src/wayfarer/functional_colors.py`, shown as object colour in Workbench Solid view. The materials are simple
functional materials, never production ones. Violet, magenta and white overlays (plasma, X-ray, beam) are illustrative.

## Rebuild

Run everything from the repository root. System `python3` is enough for the engineering; Blender only draws.

```
python3 lab/variants/fdp1/run.py                                   # all variants + sensitivities -> results/fdp1-v1/, diagrams/
python3 -m unittest discover -s lab/variants/fdp1/tests            # 44 invariant tests (baseline, low and high power, deficit, geometry)
/snap/bin/blender -b --factory-startup --python-exit-code 1 --python lab/variants/fdp1/blender/build_fdp1.py -- \
    [--variant baseline] [--out lab/variants/fdp1/REVIEW_FDP1.blend] [--render lab/variants/fdp1/renders] [--cams CAM_03_AFT_ASSEMBLY ...]
```

The build reads `assets/wayfarer/WF_WAYFARER_001.blend`. Build the ship first if that file is missing; the build takes about 10
minutes with renders.

## One pipeline

`config/fdp1.toml` (+ `config/variants/<name>.toml`) → `engineering/` → the four-burn calculator `lab/studies/four-burn-mission/fourburn`
(the only place thrust, power, propellant, radiator, tank and drive masses are computed) → the integrated record
(`results/fdp1-v1/<variant>.json`) → `engineering/geometry.py` (parts) → `blender/build_fdp1.py`. Blender and the reports read the
same record; no number is typed twice.

| File | Holds |
| --- | --- |
| `config/fdp1.toml` | Every FDP-1 input, with a status: CANON, STUDY, RESEARCH, ASSUMPTION or PROTOTYPE |
| `config/variants/` | `low_power` (0.0035 g), `high_power` (0.0085 g), `central_tier` (gain 300), `goal_1g` (owner 1 g: reports the deficit) |
| `engineering/model.py` | The integrated solve: closure ↔ shield ↔ geometry ↔ structure ↔ thermal ↔ tanks, until the departure mass repeats |
| `engineering/propulsion.py` | Four-burn closure call, pulse record, pellet |
| `engineering/shielding.py` | Crew and hardware shadow cones, dose, LiH/W layers, streaming through the ports and the bore |
| `engineering/structure.py` | Struts (stress or buckling), module, galleries, wing spars, interface load |
| `engineering/thermal.py` | Heat circuits, hot/warm/low radiators, wing layouts W2/W3/W6 |
| `engineering/tanks.py` | Existing farm, deficit, options T-A/T-B/T-C |
| `engineering/mission.py` | Per-burn history, distances, round trips |
| `engineering/geometry.py` | Parametric part list (shapes, functional colour, status) |
| `results/fdp1-v1/` | `<variant>.json`, `summary.json`, `sensitivities.json`, `TABLES.md` (generated) |
| `diagrams/` | `energy_flow_<variant>.svg` and `.png` |
| `REPORT.md` | Results, limitations, breakthroughs needed, what must improve |
| `NOTES.md` | Function, constraints, unknowns, design freedom, decisions |

Renders (`renders/`) and the `.blend` are not in Git; the owner copies are in the project files.
