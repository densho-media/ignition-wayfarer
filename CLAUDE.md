# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

# Claude Code

Follow the loop in AGENTS.md. The parent Densho application's CLAUDE.md and
tooling don't apply to this Blender project. There are no project skills or hooks.
Work on a task branch (AGENTS.md step 5): `local/<task>` on the workstation,
`claude/<task>` in Claude Code Cloud. Never commit to `main` directly. Open no
pull requests or issues; after the owner's approval, squash the branch onto `main`.

## Development flow

Apply AGENTS.md's development-flow controls. Start a change with
`python3 tools/workflow.py checks` when its scope is unclear, use
`pipeline --quick` (selected tests, draft previews) while iterating, add
`--inspect auto` for clearances, pressure boundaries, mechanisms and interfaces,
and keep the full pipeline as the pre-commit gate. Use `runtime-check` for
Godot-only work and `runtime-export` when it reports STALE. Keep Python and
physical-invariant coverage; report measured savings rather than estimates.

## Drive delegation

Use `wayfarer-drive-reader` (Sonnet) for substantial Drive retrieval and owner-row
discovery. Batch related reads into one bounded request; a tiny known-range read
may stay in the main conversation when delegation would add overhead. Supply the
question, known file IDs/ranges, and the required evidence. Keep the main agent
responsible for interpreting canon, engineering decisions, parameter/source-map
edits, and the build/check loop. Do not delegate the entire modeling task.

Use `wayfarer-drive-writer` (Sonnet) only for exact Drive edits already authorized
by the user. Supply the authorization scope, target file/tab/range or document
anchor, expected current contents, exact replacement, and verification criteria.
Existing authorization remains valid within its scope; configuring these agents
does not authorize future Drive writes. Only one writer may touch a given file at
a time. The worker checks current contents and reads back its changes; the main
agent reviews the receipt before claiming completion.

Both workers return source evidence, uncertainties and incomplete results, not
new canon. On missing tools, ambiguous sources, stale write preconditions or a
failed verification, bring the issue back to the main agent; do not broaden tool
access or silently fall back to another source. Read their definitions under
`.claude/agents/` for the handoff contract. They use the connected Claude Drive,
Sheets and Docs tools; Codex connections are not a substitute.

Start with Sonnet. Before enabling Haiku for exact-range retrieval, compare a few
representative reads against direct source evidence for values, units, formulas,
status, provenance and omissions; record elapsed time, usage and any retries.
Use existing captures for mechanical processing rather than asking a model to
transcribe whole workbooks. Do not claim cost or speed gains without measurements.

Commands and architecture are in `docs/IMPLEMENTATION.md`; read only the section
you need. Run everything from the project root. System `python3` runs the pure
modules and tests; anything that imports `bpy` runs under `/snap/bin/blender`.
A single test runs by name substring:
`python3 -m unittest discover -s tests -k <substring>`.
