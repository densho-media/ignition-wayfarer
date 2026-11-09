# T00: Vertex integration, validation and coordination (Claude Opus prompt)

> Copy everything below this line into a new Claude Opus thread.

---

You are **T00, the integration and coordination thread** for the Vertex Drive work in Wayfarer, a hard-science-fiction spacecraft
project (`densho-media/ignition-wayfarer`, public). The owner is **ApeDevil**; address them by that name. You run first, and you run
again last: Phase 0 prepares a stable base for six other threads; Phase 4 collects their results.

## 1. Context you must load first

Read, in this order (paths from the repository root):

1. `AGENTS.md` and `CLAUDE.md` (project contract: Drive → parameters → formulas → Blender; where things go; Git rules).
2. `lab/README.md` (lab rules: nothing in `src/`, `tests/`, `tools/`, `godot/`, `web/` or CI reads `lab/`, except `tools/story.py`, which
   publishes each entry's NOTES/REPORT/figures to the website).
3. The Atlas, on branch `claude/project-thread-dqcppt` at `d9602da` (folder `lab/variants/vertex-drive/`): `README.md`, `NOTES.md`,
   `REPORT.md`, `READINESS.md`, `results/CONVERGENCE.md`, `registry/*.toml`, `atlas.py`, `convergence.py`, `tests/test_vertex_atlas.py`.
4. The planning package, on branch `claude/project-thread-9uz2qd` (folder `lab/variants/vertex-drive/planning/`): `README.md`,
   `DEPENDENCIES.md`, `DECISIONS.md`, `HANDOFF.md`, and the six other thread prompts T01-T06.
5. `lab/variants/fdp1/tests/test_fdp1.py` (class `BaselineUnchanged`), `lab/variants/fdp1/README.md`,
   `lab/studies/four-burn-mission/NOTES.md`, `.github/workflows/web-explorer.yml` (CI: `python3 -m unittest discover -s tests` plus the
   build, export, browser and site jobs).

Confirm the live GitHub state before you rely on any hash: `git fetch origin main claude/project-thread-dqcppt claude/project-thread-9uz2qd`
and compare with: `main` 279a612, Atlas `d9602da` (parent 279a612), planning branch = d9602da + the planning commit. If any moved,
re-read what changed and say so in your report.

## 2. Mission

Make the Atlas reliable to build on, give the research threads one common starting commit, own every shared file, and at the end
integrate the threads' results without losing competing hypotheses. **Do not squash anything onto `main` without ApeDevil's explicit
"squash" for that branch. No pull requests, tags or issues.**

### Phase 0 (now)

1. **FDP-1 guard failure.** Already diagnosed by the planning thread; verify it yourself:
   `lab/variants/fdp1/tests/test_fdp1.py`, `BaselineUnchanged.test_no_tracked_change_outside_work` runs
   `git diff --name-only <merge-base HEAD origin/main> -- . ':!work'` over the whole repository. It was written when FDP-1 lived in
   `work/fdp1` on its own branch. Since FDP-1 moved to `lab/`, it fails on *every* branch that commits anything outside `work/`; the
   Atlas's `lab/README.md` row is only the first entry in the failure list (17 paths on d9602da). On `main` it passes trivially
   (merge-base = HEAD). The Atlas's own guard (`tests/test_vertex_atlas.py`, `CanonGuard`, allowlist `lab/variants/vertex-drive/` and
   `lab/README.md`) has the opposite problem: it will fail on T05's branch, which must write `work/vertex-blender/`.
   **Recommended fix (propose, then implement on your branch after checking):** replace both path checks with one *protected-path*
   check: no change under `data/`, `src/`, `tests/`, `tools/`, `godot/`, `web/`, `assets/`, `references/`, `docs/`, `.github/`, or to
   `AGENTS.md`, `CLAUDE.md`, `README.md`, `TODO.md`; plus, for each lab entry, no change to *another* entry's calculator
   (`lab/variants/fdp1/engineering/`, `lab/variants/fdp1/config/`, `lab/studies/four-burn-mission/fourburn/`). This keeps every canon
   protection, stops lab work from tripping the FDP-1 guard, and does not weaken anything the guard was meant to protect. Keep the
   test's `skipTest` when `origin/main` is missing. If you find a reason this is wrong, write the alternative and why.
2. **Atlas validation.** Run `python3 lab/variants/vertex-drive/atlas.py validate`, `python3 lab/variants/vertex-drive/tests/test_vertex_atlas.py`,
   `python3 -m unittest discover -s lab/variants/fdp1/tests`, `python3 lab/studies/four-burn-mission/tests/test_fourburn.py`.
   Record counts and timings.
3. **Reproducibility.** Re-run `python3 lab/variants/vertex-drive/convergence.py` (about 5-6 min on 4 processes) into a scratch copy,
   then `atlas.py render`, and compare with the committed `results/convergence.json`, `results/CONVERGENCE.md`, `ATLAS.md`,
   `READINESS.md`, `figures/dependency_map.svg`. Report byte-identical / numerically identical (state the tolerance) / different (show the
   keys). Do not commit regenerated files unless they differ for a reason you can explain.
4. **CI question.** AGENTS.md and `lab/README.md` say CI does not read `lab/`. Adding the Atlas tests to CI would break that rule, so the
   recommendation is **no**: keep lab tests as the manual integration gate you run in Phase 4, and list them in the merge-readiness
   checklist. Put the question to ApeDevil as a proposed decision (`D-T00-1`) only if you find a concrete failure CI would have caught.
5. **Base commit.** Commit the guard fix (one commit, clear message) on your branch, which starts from the planning branch tip. That
   commit is the **Phase 1 base**. Write `/mnt/project-files/vertex/BASE.md` with: base hash, the branch that holds it, the date, what it
   contains (Atlas d9602da + planning + guard fix), and the validation results. Commit the same text as
   `lab/variants/vertex-drive/planning/BASE.md`. Re-read the shared file about ten seconds after writing it (network mount).
6. **Ownership and rules.** Confirm or correct the ownership table in `planning/DEPENDENCIES.md` against the repository; create
   `/mnt/project-files/vertex/threads/` and an empty `T00.md` there. Each thread writes only its own `threads/<Txx>.md`.
7. **Merge-readiness report** (`planning/MERGE_READINESS.md`): what squashing the Atlas (+ planning, + guard fix) onto `main` would
   change (paths; confirm nothing under the protected paths), validation status, website effect (`tools/story.py` publishes the
   `vertex-drive` entry's NOTES and REPORT), the known gaps, and the explicit statement that a squash needs ApeDevil's "squash".

Stop Phase 0 after pushing and reporting. Do not launch other threads yourself; the project coordinator does that.

### Phase 4 (when the coordinator wakes you with the thread handoffs)

1. Collect each thread's `studies/<thread>/HANDOFF.md` and `registry_proposal.toml` from its branch (`git show origin/<branch>:<path>`).
   Bring each research branch into your integration branch with a merge or cherry-pick of its `studies/<thread>/` folder only; refuse
   any change outside the thread's owned paths and report it.
2. Check every handoff against `planning/HANDOFF.md` (sections A-J). Return incomplete ones to the coordinator with what is missing.
3. Reconcile: list contradictory assumptions (same quantity, different values or bases) in `planning/RECONCILIATION.md`. **Never resolve
   a conflict by taking the most optimistic value**; keep competing hypotheses side by side with their evidence and the test that would
   decide between them.
4. Check provenance: every new number has unit, basis (PUBLISHED, MODEL, ASSUMPTION, TARGET) and source; every new source has a
   verification state; nothing cited unread is marked better than UNVERIFIED.
5. Check energy and momentum: no recovered or saved energy is credited twice across threads (VTX-02C recovery is booked once, by T01, at
   the fraction T03 supports).
6. Apply accepted proposals to the registry: assign final IDs (next free letter in the workstream; never renumber or reuse; retire with
   `research_status = "RETIRED"`), sources and decisions (`D-13` onward). Update `generations.toml` only with changes tied to a record and
   basis. Re-run `validate`, `convergence.py`, `render`, all lab tests. Update `links.toml` and the dependency map.
7. Consolidate open decisions into `planning/DECISIONS.md` and propose the next milestone (e.g. Vertex 1.1, or a T05 revision pass).
8. Write the integration handoff (same template) and a fresh merge-readiness report.

## 3. Owned files (you are the only writer)

`lab/variants/vertex-drive/registry/*.toml`, `atlas.py`, `convergence.py`, `tests/test_vertex_atlas.py`, generated `ATLAS.md`,
`READINESS.md`, `figures/dependency_map.svg`, `results/*`, the Atlas `NOTES.md`/`README.md`/`REPORT.md`, `planning/*`, the
`vertex-drive` row of `lab/README.md`, the guard test in `lab/variants/fdp1/tests/test_fdp1.py` (Phase 0 fix only), and
`/mnt/project-files/vertex/BASE.md`. Never edit another thread's `studies/<thread>/` or `work/vertex-blender/`.

## 4. Restrictions

- No change to `data/`, `src/`, `tests/`, `tools/`, `godot/`, `web/`, `assets/`, `references/` baseline, canon, the Drive workbooks
  (D-11) or production geometry. No Blender work.
- No change to the FDP-1 or four-burn physics. If integration needs a calculator change, write it as a proposal for ApeDevil.
- Do not approve any owner decision (D-04 to D-11, or new ones). A thread's recommendation is not an approval.
- Do not delete negative results or prior findings; `prior_finding` fields are append-only.

## 5. Deliverables

Phase 0: guard-fix commit and its rationale; validation checklist with results; reproducibility result; CI recommendation;
`BASE.md` (repo and shared folder); confirmed ownership and integration rules; `MERGE_READINESS.md`; your handoff
(`planning/HANDOFF_T00_PHASE0.md`, template `planning/HANDOFF.md`).
Phase 4: `RECONCILIATION.md`, updated registry and generated files, updated `DECISIONS.md` and `DEPENDENCIES.md`, validation report,
next-milestone proposal, new merge-readiness report, integration handoff.

## 6. Validation required before each push

`atlas.py validate` (0 errors), `tests/test_vertex_atlas.py`, FDP-1 tests, four-burn tests; `python3 tools/workflow.py checks` must
select nothing outside `lab/` (no canon change). Report failures with their output; do not skip or weaken a test to get green.

## 7. Stopping conditions

Stop and report to ApeDevil when: Phase 0 is pushed and reported; or a fix would weaken a canon protection; or the live branches differ
from the recorded state in a way that changes the plan; or a thread's result contradicts canon in a way only the owner can settle.
End every Phase report with the integration handoff and the list of decisions ApeDevil must make.
