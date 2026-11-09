# Vertex threads: standard handoff template

Every thread ends with `HANDOFF.md` in its own folder (`lab/variants/vertex-drive/studies/<thread>/HANDOFF.md`, T05
`work/vertex-blender/HANDOFF.md`, T00 `planning/HANDOFF_T00_<phase>.md`), committed and pushed. It must let a new Claude session continue
**without the conversation**: no "as discussed", no unpublished files, no numbers without sources. Copy the skeleton below and fill every
section; write "none" rather than deleting one.

Value labels used throughout (keep them distinct):
**PUBLISHED** (a source shows it) · **MODEL** (a Wayfarer calculation, with case or script) · **EXTRAPOLATION** (engineering judgment
beyond published data, with reasoning) · **ASSUMPTION** (chosen, not derived) · **TARGET** (a requirement a technology would have to meet)
· **FICTIONAL** (an IGNITION property: the canon Fiji card, or a labelled Level C proposal) · **UNKNOWN** · **CANON** (an approved
Wayfarer value, with `data/` key or Drive range).

```markdown
# <Txx> handoff: <title>

| | |
| --- | --- |
| Thread | Txx, <role> |
| Date | YYYY-MM-DD |
| Status | DONE / PARTIAL (what is missing) / BLOCKED (on what) |

## A. Mission and scope
- Investigated: <numbered list mapped to the prompt's research questions>
- Deliberately excluded, and why: <list>

## B. Repository state
| Item | Value |
| --- | --- |
| Starting commit (Phase 1 base) | <hash> |
| Branch | <name> |
| Resulting commit | <hash> (pushed) |
| Changed paths | <list; must all be inside the thread's owned paths> |
| Rerun | <exact commands from the repo root, with run time> |

## C. Research findings
### Published evidence
<finding — source ID (registry/sources.toml or S-Txx-NEW) — verification state>
### Calculated results
<result — script and case — inputs that drive it>
### Engineering extrapolations
<claim — reasoning — what would confirm or refute it>
### Fictional assumptions
<the canon Fiji card as used; any Level C proposal, labelled>
### Unknowns
<quantity — why unknown — what would establish it>
### Negative results
<what did not work, with numbers; these stay visible>

## D. Quantitative effects
| Quantity | Value | Unit | Uncertainty / range | Label | Source |
| --- | --- | --- | --- | --- | --- |
<masses, temperatures, powers, efficiencies, dimensions, thresholds; UNKNOWN rather than invented>

## E. Model and geometry implications
<effect on the architecture; what T05 must draw, change or remove; envelopes in metres, +X bow, +Z dorsal; evidence status
ENGINEERING_SUPPORTED / PARAMETRIC_PLACEHOLDER / CONCEPTUAL_ILLUSTRATION>

## F. Dependencies
| Needed from | What | Status (received at commit / placeholder used) |
| --- | --- | --- |

## G. Decisions
- Existing register (`registry/decisions.toml`): <D-xx touched, and how; recommendation only>
- Proposed new decisions: <D-Txx-n: question, options, recommendation, who must decide>
- A recommendation is not an owner approval.

## H. Validation
- Tests and checks run, with results: <atlas.py validate; Atlas tests; FDP-1 / four-burn / problem-map tests; own reproductions>
- Model limitations: <what the model leaves out; fidelity>
- Unresolved failures: <with output>

## I. Integration instructions for T00
1. <which files to bring in>
2. <registry_proposal.toml entries: which records to add, revise, retire; provisional → final IDs>
3. <generation changes proposed, with technology and basis>
4. <conflicts with other threads known so far, and the deciding test>
5. <checks T00 must re-run after integrating>

## J. Recommended next experiment
<the single highest-value next investigation: question, method, expected output, cost, which thread>
```

## Checklist T00 applies to every handoff

- Every section A-J present; B's changed paths all inside the owned folder.
- Every number in D has a unit, a label and a source; TARGETs are not reported as results.
- No energy or momentum credited twice (check against the other handoffs, especially VTX-02C recovery).
- Negative results and competing hypotheses kept.
- Fiji used only per its canon card, or a labelled Level C proposal.
- Rerun commands reproduce the committed results.
- No owner decision presented as made.
