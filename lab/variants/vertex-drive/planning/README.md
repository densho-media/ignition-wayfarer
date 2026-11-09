# Vertex Drive: multi-thread development plan

This folder is the execution package for the next phase of the Vertex Drive work. It turns the
[Technology Atlas](../README.md) (34 records VTX-01..VTX-08, generations V0/V1/V2, decisions D-01..D-12) into seven independent work
threads, each with a standalone prompt. It is a plan only: nothing here changes canon, production geometry, `data/`, `src/`, the
Drive workbooks or any Atlas file outside `planning/`.

Two tracks run in parallel, under one rule: **research informs the 3D model, and what the 3D model reveals becomes new engineering
questions.** Today's engineering limits are research inputs, not Wayfarer's final limits; conservation laws, the canon Fiji card and the
LOCKED mission stay explicit.

## State this plan was written against

| Item | Value (checked 2026-11-09) |
| --- | --- |
| Repository | `densho-media/ignition-wayfarer` (public) |
| `main` | `279a612` (CTRL-001) |
| Atlas branch | `claude/project-thread-dqcppt` at `d9602da`, one commit on top of `main` 279a612, unchanged since 2026-11-08 |
| Planning branch | `claude/project-thread-9uz2qd`: `d9602da` plus this folder |
| Atlas validation | `atlas.py validate`: 34 records, 24 sources, 29 links, 12 decisions, 0 errors; `tests/test_vertex_atlas.py`: 16/16 pass |
| FDP-1 tests on the Atlas branch | 43/44 pass; `BaselineUnchanged.test_no_tracked_change_outside_work` fails (diagnosis in [T00](T00-INTEGRATION.md)) |
| Blender in this container | not installed (the SessionStart hook installs it in Blender threads; `assets/` is built locally, not in Git) |

## The seven threads

| Thread | Prompt | Role | Atlas records owned | Starts | Priority |
| --- | --- | --- | --- | --- | --- |
| T00 | [T00-INTEGRATION.md](T00-INTEGRATION.md) | integration, validation, coordination | registry files, `atlas.py`, `convergence.py`, tests, `lab/README.md` row | first | first |
| T01 | [T01-THERMAL.md](T01-THERMAL.md) | thermal, electrical efficiency, mass | VTX-07, 07A, 07B, 07C, 07D, 01B, 01C; ledger side of 02C | after T00 base | highest scientific |
| T02 | [T02-DUST.md](T02-DUST.md) | dust, radiation exposure, braking protection | VTX-06, 06A, 06B, 08, 08A, 08B, 08C, 08D | after T00 base | highest safety |
| T03 | [T03-NOZZLE.md](T03-NOZZLE.md) | magnetic nozzle, fields, recovery | VTX-02, 02A (read-only canon card), 02B, 02C (physics), 03, 03A, 03B, 03C, 05, 05A | after T00 base | high |
| T04 | [T04-IGNITION.md](T04-IGNITION.md) | fusion ignition, targets, radiation conversion | VTX-01, 01A, 01D, 04, 04A, 04B, 04C, 04D, 05B | after T00 base | high |
| T05 | [T05-BLENDER.md](T05-BLENDER.md) | experimental Vertex Blender development | all records, through `READINESS.md` | planning any time; blockout after D-10 | parallel |
| T06 | [T06-CONVERGENCE.md](T06-CONVERGENCE.md) | technology convergence and IGNITION history | all records and links, read-only | with Phase 1; final after T01-T04 | synthesis |

Every Atlas record has exactly one owning thread (the coverage table is in [DEPENDENCIES.md](DEPENDENCIES.md#coverage)). Shared
mechanisms have one owner and named consumers: VTX-02C recovery physics belongs to T03, its booking in the energy ledger to T01;
VTX-01C target-factory energy belongs to T01, the target designs it must make to T04.

## Sequence

1. **Phase 0, T00 alone.** Fix the guard tests, confirm reproducibility, set the Phase 1 base commit and publish it in
   `/mnt/project-files/vertex/BASE.md` (and on T00's branch). Report merge readiness. No squash.
2. **Phase 1, T01-T04 in parallel** from that one base. T01 and T02 publish early outputs first (radiator envelopes, exposure map),
   because T05 and each other need them.
3. **Phase 2, T05.** Specification work may start with Phase 1. The Blender blockout starts only after the owner approves D-10.
4. **Phase 3, T06.** Gathers from the start; writes its final synthesis after T01-T04 hand off.
5. **Phase 4, T00 again.** Collects the handoffs, reconciles, applies registry changes, re-runs validation and convergence, prepares the
   next milestone and a merge-readiness report. Competing hypotheses stay visible.

The graph, critical path and exchange schedule are in [DEPENDENCIES.md](DEPENDENCIES.md); the owner gates in [DECISIONS.md](DECISIONS.md);
the handoff every thread returns in [HANDOFF.md](HANDOFF.md).

## Working rules common to every thread

- **Git.** One feature branch per thread, started from the Phase 1 base. In Claude Code Cloud use the branch the session designates
  (`claude/<...>`); where a name can be chosen, use `claude/vertex-integration`, `-thermal`, `-dust`, `-nozzle`, `-ignition`,
  `-blender`, `-convergence`. Commit and push to that branch only. **No pull requests, no tags, no GitHub issues.** Nothing is squashed
  onto `main` without the owner's explicit "squash" for that branch.
- **Where things go.** Research threads write only inside `lab/variants/vertex-drive/studies/<thread>/`. T05 writes `work/vertex-blender/`.
  T00 alone edits the Atlas registry, `atlas.py`, `convergence.py`, the Atlas tests, `planning/` and the `lab/README.md` row.
- **Exchange board.** `/mnt/project-files/vertex/` (shared project folder): `BASE.md` (T00 only) and `threads/<Txx>.md` (each thread its
  own file only: branch, latest pushed commit, early outputs, questions for other threads). Read other threads' files from their branch
  with `git fetch origin <branch>` and `git show origin/<branch>:<path>`; never edit another thread's files.
- **Proposals, not edits.** A thread that wants a registry change writes `studies/<thread>/registry_proposal.toml` in the registry
  schema, with provisional IDs (`T01-NEW-1`, `S-T01-<NAME>`, `D-T01-1`). T00 assigns the final VTX, source and decision IDs.
- **Calculators are read-only.** `lab/variants/fdp1/`, `lab/studies/four-burn-mission/`, `convergence.py` and `atlas.py` are called,
  never edited, outside T00. A needed physics change is written up as an integration proposal for T00 first.
- **Owner and review.** The owner is addressed as ApeDevil. The ship's standard crew is 12. Anything for owner review must open
  directly: committed Markdown and SVG on GitHub, a packed `.blend` in the project files `review/` folder, or a GitHub Pages page.
  Never a script to run.
- **Publication.** The repository is public; `lab/` is published on the website's Engineering pages. Drive captures, correspondence
  and internal notes stay local (AGENTS.md "Drive canon"). No Drive writes without the owner (D-11).
- **Science rules** (all threads): energy and momentum are booked once; a model target is a requirement, not a result; Fiji does only
  its canon card unless a labelled Level C proposal is written; negative results stay visible; a specific-model failure is not a
  proof of impossibility; findings do not update canon; every claim carries provenance (`registry/sources.toml` vocabulary).

## Quality checks run on this package

See [DEPENDENCIES.md](DEPENDENCIES.md#quality-checks): workstream coverage, unowned tasks, file-ownership conflicts, authorisation gates,
handoff sufficiency, canon and geometry safety, actionable questions, no assumed results.
