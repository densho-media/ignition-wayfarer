<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE (research, not canon; awaiting owner review) |
| Question | Can a Magneto-Photonic Nozzle (magnetic charged exhaust, X-ray and gamma reflection, neutral release) make the Vertex drive thermally viable, and can photons add useful thrust? |
| Model base | 3866ebf; production geometry, data and canon unchanged |
| Branch | claude/project-thread-1p6mtu, 2026-11-22 |
| Open owner questions | Q-MPN-1 accept photonics as a narrow tool; Q-MPN-2 pursue edge-on remote geometry despite the Halo 2 km rejection; Q-MPN-3 magnet mass levers; Q-MPN-4 charged-leakage Monte Carlo; Q-MPN-5 V2/V3 fuel route |
| Review | REPORT.md and figures/ here; Claude Doc https://claude.ai/artifact/UmaBeez7q3xVmiWsxH7UoZ |

# magneto-photonic-nozzle: notes

**Function.** Keep the Vertex drive's photon and neutron heat in hardware below the 10.80 GW drive share of the 14.40 GW hot radiator
(allowed fraction 4.13e-5 of 261.3 TW fusion), and test whether reflecting X-rays aft adds thrust.

**Fixed constraints.** Canon operating point (references/p1_operating_point.json): 261.27 TW fusion, 209.0 TW jet, four engines, four
9.99-day burns. Sources from Vertex 1.5 (V0) and 1.6B (V1-V3). The 1.5 ray trace of the drawn engine (263 part meshes). Optical constants
from xraylib 4.3.0 (data/optics.json; regenerate with `optics_data.py` in a venv that has xraylib). Halo Vertex 2.5 ledger as the remote-ring
reference (lab/variants/halo-vertex).

**Unknowns (OPEN).** Charged leakage of a remote ring (the Halo 2.2 95 % bound, 0.82 GW per engine, is used); surface ablation and figure
life at grazing incidence; full photon and neutron transport (no Geant4/OpenMC); structural dynamics of 2 km deployed structures.

**Design freedom.** Ring radius, burn distance, engine spacing, ship distance, ribbon depth, skimmer length and material, cable form,
field-energy ratio, conductor current density. All PROTOTYPE.

**Decisions.** Photonics is booked as a narrow tool (leading edges, far-IR synchrotron), not as the thermal closure. Self-radiating hot
parts (SELF) are booked apart from piped hot-loop heat (B01). The recommended point is F at V2, R 90 m, burn 180 m aft, 2 km spacing, no
skimmer. Registered as BT-009 (skimmer) and BT-010 (edge-on remote ring) in lab/studies/breakthrough-lab, both PROPOSED, NON_CANON.

**Files.** `mpn.py` (standard library, about 13 s: `python3 lab/studies/vertex-compact-engine/magneto-photonic-nozzle/mpn.py`) writes results/mpn.json and
results/mpn.log with 17 validation checks; `figures.py` draws figures/*.svg from mpn.json; `optics_data.py` builds data/optics.json.
