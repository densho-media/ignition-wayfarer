# T00 handoff: Phase 0, integration baseline

| | |
| --- | --- |
| Thread | T00, integration and coordination |
| Date | 2026-11-09 |
| Status | DONE (Phase 0). Phase 4 waits for the thread handoffs. |

## A. Mission and scope
- Investigated: (1) the FDP-1 guard failure and the Atlas guard's `work/` problem; (2) Atlas, FDP-1 and four-burn validation;
  (3) reproducibility of `convergence.py` and the generated pages; (4) an independent check of the Atlas arithmetic; (5) the CI question;
  (6) the Phase 1 base; (7) ownership; (8) merge readiness.
- Deliberately excluded: any registry, generation, calculator or physics change (none needed); launching other threads (the coordinator
  does that); T05 (not in this launch); the stale `fdp1-requirements` validation page (pre-existing on `main`, not a Vertex file).

## B. Repository state
| Item | Value |
| --- | --- |
| Starting commit | `aae4924` (planning branch `claude/project-thread-9uz2qd`); live hashes matched the plan: `main` 279a612, Atlas d9602da |
| Branch | `claude/project-thread-9rsgog` |
| Phase 1 base | `8de3ffa` (guard fix, arithmetic tests, owner rulings, `MERGE_READINESS.md`) |
| Resulting commit | the commit adding this file and `BASE.md`, on top of `8de3ffa` (documentation only) |
| Changed paths | `lab/variants/fdp1/tests/test_fdp1.py` (guard only), `lab/variants/vertex-drive/tests/test_vertex_atlas.py`, `lab/variants/vertex-drive/planning/{DECISIONS,DEPENDENCIES,MERGE_READINESS,BASE,HANDOFF_T00_PHASE0}.md` |
| Rerun | the four commands in `BASE.md` (about 12 s); `python3 lab/variants/vertex-drive/convergence.py` (about 6-8 min on 4 cores) |

## C. Research findings
### Published evidence
none new.
### Calculated results
- Guard: `test_no_tracked_change_outside_work` failed with 28 paths on aae4924 (17 Atlas + 11 planning). Fixed by one rule shared by both
  guards: only `lab/` and `work/` may change; the Atlas guard also protects `lab/variants/fdp1/{engineering,config,run.py}` and
  `lab/studies/four-burn-mission/{fourburn,scenarios}`. Chosen over the planned denylist because an allowlist also refuses new top-level
  paths (`shots/`, `.gitignore`, `LICENSE`, `.claude/` were absent from the denylist). Negative check: touching `data/wayfarer_3d.toml`
  makes both guards fail.
- Reproducibility: `convergence.json` numerically identical at zero tolerance (only 7 timing fields differ); `ATLAS.md`, `READINESS.md`,
  `dependency_map.svg` byte-identical; `CONVERGENCE.md` differs only in its runtime line.
- Arithmetic: ledger closure, a0, jet power, burn time, rocket equation and warm radiator area hold for V0-V2 (table in
  `MERGE_READINESS.md`); quoted swirl torque (2.8e5 N m, CMGs full in 0.36 s against the canon 100,770 N m s) and trim power (about
  340 GW) confirmed.
### Engineering extrapolations
none.
### Fictional assumptions
none added.
### Unknowns
none new.
### Negative results
The single 700 K warm loop of V1 is a stand-in for a 600/773 K split; whether it over- or under-states area depends on the heat split
(T01 to replace it).

## D. Quantitative effects
none (no generation or record changed).

## E. Model and geometry implications
none; no geometry, canon or lore changed.

## F. Dependencies
| Needed from | What | Status |
| --- | --- | --- |
| T01-T04, T06 | `studies/<thread>/HANDOFF.md`, `registry_proposal.toml` | not started |

## G. Decisions
- Owner rulings 2026-11-09 recorded in `planning/DECISIONS.md` (D-T00-1, D-PLAN-1 approved; D-09, D-11, D-08 not approved; D-10 in
  principle). Registry entries stay OPEN until Phase 4.
- Proposed new decisions: none.

## H. Validation
- `atlas.py validate` 0 errors; Atlas tests 21 OK; FDP-1 tests 45 OK; four-burn tests 18 OK; `workflow.py checks` selects nothing.
- Unresolved failures: none on this branch. Pre-existing on `main`: `lab/problems/fdp1-requirements/VALIDATION_V3.md` is stale
  (127/127 here without Blender vs 128/128 committed; two data-file hashes differ).

## I. Integration instructions for T00 (Phase 4)
1. Bring in each `studies/<thread>/` by merge or path-limited cherry-pick; reject paths outside it.
2. Assign final IDs from `registry_proposal.toml` in one pass; record the 2026-11-09 rulings in `registry/decisions.toml`.
3. Re-run the four commands, `convergence.py` and `atlas.py render`; update `MERGE_READINESS.md`.
4. Watch VTX-02C recovery (booked once by T01 at T03's fraction) and the T01 split-loop area.

## J. Recommended next experiment
T02's D-06 braking-dust options: the highest-priority open issue, and it blocks any Vertex adoption.
