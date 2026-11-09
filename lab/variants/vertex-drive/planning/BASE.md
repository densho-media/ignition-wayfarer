# Vertex Phase 1 base

Written by T00 only. Every Phase 1 thread starts from exactly this commit.

| | |
| --- | --- |
| Base commit | `8de3ffa189b47ce9a1212b550b7ea75f8c36314a` (short `8de3ffa`) |
| Held on branch | `claude/project-thread-9rsgog` (T00's branch; pushed) |
| Date | 2026-11-09 |
| Parent chain | `main` 279a612 → Atlas d9602da → planning aae4924 → T00 guard fix 8de3ffa |
| Contains | the Vertex Technology Atlas, the planning package, the shared canon guard for the lab tests, the result-arithmetic tests, the 2026-11-09 owner rulings (`DECISIONS.md`), `MERGE_READINESS.md` |
| Not on `main` | nothing is squashed; a squash needs ApeDevil's "squash" for a named branch |

## Validation at the base

| Check | Result |
| --- | --- |
| `python3 lab/variants/vertex-drive/atlas.py validate` | 34 records, 24 sources, 29 links, 12 decisions; 0 errors |
| `python3 lab/variants/vertex-drive/tests/test_vertex_atlas.py` | 21 tests OK |
| `python3 -m unittest discover -s lab/variants/fdp1/tests` | 45 tests OK |
| `python3 lab/studies/four-burn-mission/tests/test_fourburn.py` | 18 tests OK |
| `convergence.py` re-run + `atlas.py render` | reproduces the committed results exactly (only run times differ); V0 = FDP-1, 20,760 t |
| `python3 tools/workflow.py checks` | selects nothing (no canon change) |

## How each thread starts

```bash
git fetch origin claude/project-thread-9rsgog
git checkout -B <your session's branch> 8de3ffa189b47ce9a1212b550b7ea75f8c36314a
python3 lab/variants/vertex-drive/atlas.py validate     # must print 0 errors before you change anything
```

Then write `/mnt/project-files/vertex/threads/<Txx>.md` (branch, start commit `8de3ffa`, status). Write only your owned folder
(`planning/DEPENDENCIES.md`, Ownership). The lab guards refuse any change outside `lab/` and `work/` and any change to the FDP-1
calculator or the four-burn engine; run the four validation commands above before every push.

| Thread | Prompt | Owned folder | Ready to start | Applicable rulings (2026-11-09) |
| --- | --- | --- | --- | --- |
| T01 thermal | `planning/T01-THERMAL.md` | `studies/thermal/` | yes | D-04 open (report V1 with and without H2 vessels); D-05 open (wings experimental only); D-11 no Drive writes |
| T02 dust and braking | `planning/T02-DUST.md` | `studies/dust/` | yes | D-06 open, highest priority; no mission, speed or orientation change; D-11 |
| T03 nozzle and fields | `planning/T03-NOZZLE.md` | `studies/nozzle/` | yes | D-PLAN-1 approved: analytical, vacuum-field, field-line and test-particle work allowed; D-09 not approved: no MHD/PIC run, plan only; D-07 open; D-11 |
| T04 ignition and targets | `planning/T04-IGNITION.md` | `studies/ignition/` | yes | D-07 open; D-04 (low gear) argued, not decided; D-11 |
| T06 convergence and futures | `planning/T06-CONVERGENCE.md` | `studies/futures/` | yes | D-08 not approved: no canonical engine replacement; D-11 |
| T05 Blender | `planning/T05-BLENDER.md` | `work/vertex-blender/` | not in this launch | D-10 approved in principle: Stage A (geometry requirements review) first; Stage B only in isolated experimental files after that review, never canon geometry |

All threads: D-08 not approved, D-11 not approved (Drive read only), no change to canon geometry or lore, no pull requests, tags or
issues, no squash. Only ApeDevil approves decisions; a recommendation or a passing test is not an approval.
