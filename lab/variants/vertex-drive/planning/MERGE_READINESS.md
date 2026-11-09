# Vertex Drive: merge readiness (T00 Phase 0, 2026-11-09)

**A squash onto `main` needs ApeDevil's explicit "squash" for the named branch.** This report recommends nothing beyond saying what a
squash would do; it is not a request to squash.

## What a squash of the Phase 1 base would change

Branch `claude/project-thread-9rsgog`, Phase 1 base = the T00 guard-fix commit (hash in `planning/BASE.md`), compared with `main` 279a612:
30 paths, all under `lab/`; 28 added, 2 modified.

| Group | Paths |
| --- | --- |
| Atlas (from d9602da) | `lab/variants/vertex-drive/`: `README.md`, `NOTES.md`, `REPORT.md`, `READINESS.md`, `ATLAS.md`, `atlas.py`, `convergence.py`, `registry/{technologies,sources,links,decisions,generations}.toml`, `results/{convergence.json,CONVERGENCE.md}`, `figures/dependency_map.svg`, `tests/test_vertex_atlas.py` |
| Lab index (modified) | `lab/README.md`: one added `vertex-drive` row |
| Planning (from aae4924, + T00) | `lab/variants/vertex-drive/planning/`: `README.md`, `DEPENDENCIES.md`, `DECISIONS.md`, `HANDOFF.md`, `T00`-`T06` prompts, `MERGE_READINESS.md` |
| Guard fix (modified) | `lab/variants/fdp1/tests/test_fdp1.py`: `BaselineUnchanged` only |

Protected paths: **no change** under `data/`, `src/`, `tests/`, `tools/`, `godot/`, `web/`, `assets/`, `references/`, `docs/`,
`.github/`, `shots/`, nor to `AGENTS.md`, `CLAUDE.md`, `README.md`, `TODO.md`, `.gitignore`. `python3 tools/workflow.py checks` selects
no test, build, inspection or runtime check. No FDP-1 or four-burn physics changed. No Drive change.

## Validation (on the base tree, Python 3.13, 4 cores)

| Check | Result | Time |
| --- | --- | --- |
| `python3 lab/variants/vertex-drive/atlas.py validate` | 34 records (8 workstreams), 24 sources, 29 links, 12 decisions; 0 errors | 0.1 s |
| `python3 lab/variants/vertex-drive/tests/test_vertex_atlas.py` | 21 tests OK (16 before T00; + 4 result-arithmetic, + 1 guard-rule) | 0.1 s |
| `python3 -m unittest discover -s lab/variants/fdp1/tests` | 45 tests OK (was 44 with 1 FAIL: the guard) | 11 s |
| `python3 lab/studies/four-burn-mission/tests/test_fourburn.py` | 18 tests OK | 0.2 s |
| Guard negative test (touch `data/wayfarer_3d.toml`, run both guards, restore) | both guards FAIL as intended | - |
| `convergence.py` re-run in a scratch worktree, then `atlas.py render` | `ATLAS.md`, `READINESS.md`, `figures/dependency_map.svg` byte-identical; `convergence.json` numerically identical at zero tolerance (every physics value equal; only the 7 run-time fields differ); `CONVERGENCE.md` differs only in the runtime line; V0 reproduces FDP-1 (20,760 t) | 7 min 52 s (471 s compute, 4 processes) |

Regenerated files were not committed (no difference except wall-clock time).

## Independent check of the Atlas arithmetic

Recomputed outside the FDP-1 calculator for V0, V1 and V2 (now `ResultArithmetic` in the Atlas tests):

| Identity | V0 | V1 | V2 |
| --- | --- | --- | --- |
| Energy ledger shares sum to 1 | 1.000000 | 1.000000 | 1.000000 |
| a0 = F / (m0 g0) | 0.00690 g | 0.00690 g | 0.00690 g |
| Jet power = F ve / 2 | 13.48 TW | 6.76 TW | 6.02 TW |
| Burn time = m_prop / (F / ve) | 5.685 y | 5.685 y | 5.685 y |
| m0 / m_end = exp(4 x 0.016 c / ve) | 2.7162 | 2.7162 | 2.7162 |
| Warm area = Q / (2 x 0.9 x sigma T^4) | 1.84 km2 at 600 K | 0.32 km2 at 700 K | 0.17 km2 at 800 K |

Spot checks of quoted figures: 1 % swirl, 0.073 kg/s x 0.01 x 19,201 km/s x 20 m = 2.8e5 N m (10.8x the 26 kN m RCS couple; the canon
CMG storage 100,770 N m s, `exterior_hardware.sizing`, fills in 0.36 s): confirmed. 1 % loop trim in 5 ms: about 2 % of the ~8e10 J
stored field energy in 5 ms = 320-340 GW: confirmed to the stated precision.

Note, not an error: V1's warm loop is one 700 K radiator standing for a split 600 K / 773 K loop. For the same heat split two loops need
`Q1/T1^4 + Q2/T2^4` of area, which is larger or smaller than one 700 K panel depending on the split; T01 should replace the single
temperature with the split when it sizes the package.

## CI (D-T00-1, approved 2026-11-09)

Lab tests stay outside ordinary CI (CI runs `tests/` only). No failure was found that CI would have caught: the one failing lab test was
the FDP-1 guard, a branch-state check, and no physics test failed. The suites above are the required integration gate; each integration
run records them here.

## Website effect of a squash

`tools/story.py` (run to scratch, 10.7 s) publishes a new page `engineering/variants/vertex-drive/` from the entry's `NOTES.md` and
`REPORT.md`, with `figures/dependency_map.svg`, and lists it in the Engineering index. Nothing else on the site changes.

## Known gaps

- D-06 (engine-first braking through dust at 0.016 c) is open for the canon ship as well; it blocks any Vertex adoption.
- D-04, D-05, D-07 open; D-08, D-09 (full MHD/PIC) and D-11 not approved; D-10 approved in principle only (see `DECISIONS.md`).
- The registry still shows the 2026-11-09 rulings as OPEN; T00 records them at Phase 4 so the generated pages change once.
- Outside this branch, pre-existing on `main` (847713b): `lab/problems/fdp1-requirements/VALIDATION_V3.md` is stale. Re-running
  `check_v3.py` gives 127/127 (the committed file says 128/128; the byte-for-byte geometry export check needs Blender and is absent here)
  and different hashes for `fdp1_parameters.json` and `scenario_inputs.json`. Not touched by Vertex; left for the problem map's owner.
