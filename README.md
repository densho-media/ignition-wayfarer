# G.U. Wayfarer 001

A parametric, physics-first spacecraft from the **IGNITION** universe, built procedurally in Blender
and explored interactively in Godot. A **[Densho](https://densho.media)** production.

| | |
| --- | --- |
| Asset | G.U. WAYFARER 001 |
| Universe | IGNITION |
| Canonical identity | `wayfarer.ignition.densho` |
| Publisher | Densho — https://densho.media |

## The ship and the universe

Wayfarer carries the experimental Fiji/Lattice fusion drive. In IGNITION, a hard-science-fiction
universe, it is the setting of a story about six people who accidentally set out on a years-long
journey aboard it. The design follows a simple order: physics first, engineering second, aesthetics
third. Fictional technology can extend what engineering does, but it never removes physical limits.
Major shapes are explained by what they do: shielding, radiators, thrust structure, crew protection
and service access.

Densho turns worldbuilding like this into multimedia storytelling. Wayfarer is its reference
project: cinema, scientific visualization, interactive exploration and reusable assets, all from
one reproducible, AI-assisted production pipeline.

## How it is made

**engineering workbooks → parameters → shared formulas → Blender geometry → validation → Godot**

- The engineering authority is a set of private IGNITION workbooks. This repository publishes the
  inputs derived from them: `data/*.toml` holds the parameters and their source records, and
  `data/simulations/*.json` holds the imported scenario data. Unknown physics stays unknown, and a local
  design choice without a source is marked PROTOTYPE.
- Pure-Python modules (`src/wayfarer/`) validate the parameters and compute the geometry.
  Blender scripts (`src/wayfarer/components/`) generate linked `.blend` libraries for components,
  subsystems and the whole vehicle.
- A pipeline rebuilds the ship, diffs its geometry against the committed baseline
  (`references/baseline_*`), inspects clearances and interfaces, and renders previews.
- Godot (`godot/`) loads the exported model for the walk: from the development station into the
  ship and round a habitat ring, with crew physics in the ship's frames.
- GitHub Actions rebuilds the ship from a clean checkout on every push to `main` or a task branch
  and checks a browser version of it. Each passing push to `main` publishes that version to the
  **[Wayfarer website](https://densho-media.github.io/ignition-wayfarer/)**: Explore Ship (a 3D
  engineering viewer for desktop and phone) or Enter Wayfarer (the walk from the development station
  round a habitat ring and back, under your own control),
  each loaded only when chosen ([web/README.md](web/README.md)).
- Geometry is proxy-level. Passing checks and previews are not engineering proof.

## Build and explore

Requirements:
- Linux, Python 3.11 or later (standard library only).
- [Blender 5.2 LTS](https://www.blender.org/download/).
- Optionally [Godot 4.7.2](https://godotengine.org/download/) for interactive scenes.

Set `WAYFARER_BLENDER` and `WAYFARER_GODOT` if the executables are not at `/snap/bin/blender` and
`/snap/bin/godot-4`.

```bash
python3 tools/workflow.py deps install        # pinned, checksummed third-party add-ons (characters)
python3 tools/workflow.py status              # check the inputs
python3 tools/workflow.py pipeline --quick    # build, selected tests, geometry diff, draft previews
python3 tools/workflow.py pipeline            # full gate: all tests, whole-ship inspection, Cycles previews
python3 tools/workflow.py runtime-export      # export the static model and check it in Godot
godot-4 --path godot                          # the walk: WASD and the mouse, E use, O ship operations, M map
```

The `.blend` files, renders, runs and Godot imports are generated and are not in Git. Open
`assets/wayfarer/WF_WAYFARER_001.blend` after a build. Unit tests run without Blender:
`python3 -m unittest discover -s tests`.

## Repository

| Path | Contents |
| --- | --- |
| `data/`, `data/simulations/` | Production inputs: parameters, source records, scenario data |
| `src/wayfarer/` | Validation, pure geometry, Blender generators, inspection, previews, shots, export |
| `tools/` | Workflow command line, build pipeline, runtime export |
| `tests/` | Unit tests for owner numbers and physical invariants, with their own synthetic fixtures |
| `references/` | Current geometry baseline, generated validation reports and kept study results (`evidence/`) |
| `godot/` | The walk and its runtime checks |
| `web/`, `.github/workflows/` | Website (start page, viewer, Godot launcher and shell, status page) and the workflows that build, check, publish and roll it back |
| `work/` | Unapproved work, one folder per task branch ([work/README.md](work/README.md)) |
| `docs/` | [Model](docs/MODEL.md), [implementation](docs/IMPLEMENTATION.md) and subsystem notes |

[AGENTS.md](AGENTS.md) describes the development loop that human and AI contributors follow.

## Branches

- `main` is the approved, validated baseline.
- Work happens on `local/<task>` (workstation) or `claude/<task>` (Claude Code Cloud) branches.
- After validation and the owner's approval, a branch is squashed onto `main` as one commit.
  The project uses no pull requests, GitHub issues or tags.

## Licence

- **Code** (`src/`, `tools/`, `tests/`, `godot/` scripts and scenes, `.claude/`): [Apache-2.0](LICENSE).
- **IGNITION content** (lore, names, story, ship design, parameters and data, documentation,
  generated models and images): © Densho, all rights reserved. See [NOTICE](NOTICE).
- "IGNITION", "Wayfarer", "G.U.", "G.U.C." and "Densho" are not licensed for reuse.
