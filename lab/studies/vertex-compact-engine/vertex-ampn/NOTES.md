<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study (with variant blockouts) |
| Status | ACTIVE (research, not canon; awaiting owner review) |
| Question | Does an adaptive magneto-photonic nozzle (field and geometry that change between propulsion, braking and stowed states) beat a fixed RON nozzle with passive protection, for the canon mission? |
| Model base | 250a756 + RON (lab/studies/vertex-compact-engine/vertex-ron); production geometry, data and canon unchanged |
| Branch | claude/project-thread-1p6mtu, 2026-11-22 |
| Open owner questions | Q-AMPN-1 adopt fixed B today (10,987 t) as working point; Q-AMPN-2 NOMINAL or JUSTIFIED dust envelope; Q-AMPN-3 mission-level trade since nothing comes within 2.2x of 4,426 t; Q-AMPN-4 ripple coupling and plasma detachment next |
| Review | Claude Doc https://claude.ai/artifact/FawyE2iHGcscvpMuBXQXUA; REVIEW_AMPN.blend (local, not in Git); renders/ |

# vertex-ampn: notes

**Function.** The RON nozzle continued: magnetic exhaust guidance, radiation avoidance, cooling, braking-phase dust protection and
mechanical deployment for the four Vertex engines, at minimum whole-ship mass.

**Fixed constraints.** Canon operating point (4 burns of 4,797 km/s, canon jet power, departure 4,426 t as benchmark); dust
environment and damage rules of lab/studies/dust-impacts (imported read-only); physics never relaxed; delta-v never reduced.

**Unknowns (OPEN).** 20 kHz field-ripple coupling to the winding (0.1-1, 0.3 nominal); plasma-coupled detachment and collective effects
(vacuum test particles only); rare high-energy hits (no hit in 40,960 launches, bound 2.9e-4); impacts above 100 km/s (EXTRAPOLATION);
CFRP fatigue at 1e11-1e12 cycles.

**Design freedom.** R, kappa, D, S, current multiple, mirror share, tape class, stand-offs, armour, fences, stack. All PROTOTYPE.

**Decisions.** Exhaust dust shielding (Mode B) and EM grain deflection rejected on physics; passive stern screen + face armour adopted.
Fixed nozzle beats adaptive (+292 t, no benefit); carriage kept as a service option. B beats E. R floor about 15 m (winding fluence).

**Files** (standard library; run from the project root):
- `audit.py` - RON thermal, neutron, ripple, particle and interception audit (results/audit.*).
- `optimize.py` - Nelder-Mead over B and E x three tapes (results/optimize.*, geometry/).
- `dust.py` - braking dust physics and passive protection (results/dust.*).
- `adaptive.py` - states, ramps, forces and failures (results/adaptive.*).
- `coilpack.py` - cross-section, cooling, quench, structure and the full mass account (results/coilpack.*).
- `rscan.py` - R below 15 m.
- `trade.py` - results/tables.md, results/trade.json and figures/pareto.svg.
- `blender_ampn.py` (`/snap/bin/blender -b --factory-startup --python lab/studies/vertex-compact-engine/vertex-ampn/blender_ampn.py`) - REVIEW_AMPN.blend, renders/ and renders/anim/.
