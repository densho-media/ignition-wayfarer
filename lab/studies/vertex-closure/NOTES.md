<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | PARKED (gate failed 2026-11-18; kept as a research result) |
| Question | Can the Vertex engine cluster close the mission ledger (mass, heat, radiation, He-3, dust) at or near the 4.6 kt departure envelope, and with which nozzle, forward-stream and protection architecture? |
| Model base | main eb33a44 (Vertex Engine 1.5); results unchanged by the FPS V1.1 squash a2f9b7f |
| Branch | claude/project-thread-6qwiwi, 2026-11-16 to 2026-11-18 |
| Open owner questions | R1 accept the Vertex 2.11 gate result; R2 a broader fuel-cycle and propulsion-architecture comparison next; R3 keep A1 as the B2d nozzle setting |
| Review | The thread's report Docs (Vertex 2.6 to 2.11); Phase F browser review built by `vertex-1-8/build_page.py` |

# vertex-closure: notes

Vertex Engine 1.8 Phase F and the Vertex 2.6 to 2.11 closure studies, moved here unchanged from `work/vertex-*` when the thread
closed (2026-11-20). Each subfolder keeps its own `NOTES.md`, scripts and result JSON/logs. Run scripts from the repository root, for
example `python3 lab/studies/vertex-closure/vertex-2-11/mission211.py`. The subfolders import each other as siblings (2.11 uses 2.10
and 2.8, 2.8 uses 2.7 and 2.6, 2.6 uses `lab/variants/halo-vertex`). The departure masses here are whole-ship ledgers against the
4.6 kt envelope. They are not the drawn cluster mass (6,403 t in FPS V1.1), and the two being close is a coincidence.

| Folder | Study | Outcome |
| --- | --- | --- |
| `vertex-1-8/` | 1.8 Phase F: A+ ignition review and budget reconciliation | mass and heat do not close; the drawn cluster is 25x the 250 t allowance |
| `vertex-2-6/` | compact architectures and flight protection | C Protected Adaptive reaches 6,271 t, but only with 3 speculative items |
| `vertex-2-7/` | ve, fuel cycle, He-3, spine length, dust envelope | 4,523 t with every lever, while He-3, the speculative count and HIGH dust fail; the 200 m spine survives JUSTIFIED dust |
| `vertex-2-8/` | two-regime traced magnetic nozzle | 2.7 cosine superseded (credited 0.47); B2d 5,700 t only with SR-26F restated |
| `vertex-2-9/` | reduced 2D hybrid of B2d (not validated) | cosine holds 0.90-0.95; the forward stream fails SR-26F in 25 of 26 runs |
| `vertex-2-10/` | forward-stream architectures | the Stern Mirror relaxes SR-26F about 10x at 6.4 kt; nothing reaches 4.6 kt |
| `vertex-2-11/` | Stern Mirror verification (1D PIC, hold-off, 3D trajectories, ledger) | FAIL: hold-off x31 over data; no consistent closure below 8.1 kt |

## Findings

- No Vertex architecture studied closes on established physics. The blockers are photon share (1.5), neutrons and leakage (1.6B),
  the forward stream (2.8 to 2.10) and electrostatic hold-off (2.11).
- The best ledger points (4.5 to 6.4 kt) all need declared speculative requirements: VBC, SR-26A, SR-26F, or SR-210B, which fails.
- Raising fusion power raises neutron, photon and leakage loads roughly in proportion. Better materials alone do not close the
  7.31x power gap. The fuel cycle sets the shielding and radiator mass.
- Next (owner R2): compare fuel cycles and propulsion architectures across the whole ledger, rather than optimizing the Stern Mirror.
