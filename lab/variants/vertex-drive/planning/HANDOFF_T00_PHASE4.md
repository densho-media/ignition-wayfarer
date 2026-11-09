# T00 Phase 4 handoff (2026-11-09)

| | |
| --- | --- |
| Thread | T00 integration |
| Branch | `claude/project-thread-9rsgog` |
| Base | `8de3ffa`; merge of T01 `1302708`, T02 `3c665ec`, T03 `59244a9`, T04 `fd4ff3d`, T06 `f39023a` at `80d757a` |
| Result | the Phase 4 commit on this branch (hash in `/mnt/project-files/vertex/threads/T00.md`) |
| Status | DONE: integrated research baseline validated; awaiting owner review. Not squashed. |

## Files

| File | Content |
| --- | --- |
| `planning/INTEGRATION_REPORT_PHASE4.md` | the consolidated report: mass, power, thermal, structure, mission, bands, barriers, decisions, validation |
| `planning/RECONCILIATION.md` | contradictions, unit errors and IGNITION timeline conflicts, each with its resolution |
| `planning/D21_MHD_PIC_PROPOSAL.md` | bounded 2D nozzle campaign, prepared and not launched |
| `planning/T05_HANDOFF.md` | corrected configurations and envelopes for T05 |
| `planning/integrate_phase4.py` | provenance of the registry integration (rebuilds the registry from `8de3ffa` plus the proposals) |
| `registry/*.toml`, `ATLAS.md`, `READINESS.md`, `figures/` | integrated registry and generated pages |
| `registry/generations.toml`, `convergence.py`, `results/` | V3-V5, the `vertex.` adapter inputs (coupling, density, launcher), sweeps; `--report` re-renders without solving |
| `results/history/2026-11-08_atlas/` | frozen V0-V2 results |

## Rerun

From the repository root:

```bash
python3 lab/variants/vertex-drive/convergence.py          # about 13 min on 4 cores; exits 0 only if V0 reproduces 20,760 t
python3 lab/variants/vertex-drive/atlas.py validate && python3 lab/variants/vertex-drive/atlas.py render
python3 lab/variants/vertex-drive/tests/test_vertex_atlas.py
```

## Next

- ApeDevil reviews the report and the decisions in §9.
- T05 Stage A starts from `T05_HANDOFF.md`.
- Squash only on an explicit "squash".
