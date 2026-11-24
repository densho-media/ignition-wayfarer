<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE (research behind the Fusion Engineering page; not canon) |
| Question | ENG-062: can early extraction, closure topology, burn position or field strength stop the nozzle hardware intercepting the burning plasma, with momentum-consistent accounting? |
| Model base | main c169a9f; compact C1 geometry (vertex-compact), R2-B source levers (vertex-source), ron.py test particles |
| Branch | claude/project-thread-1p6mtu, 2026-11-24 |
| Open owner questions | Move the burn point about 4 m aft with stronger closure rings (a drawn-geometry change, needs owner approval); recompute the X-ray pickup for a moved burn |
| Review | `engineering/fusion-ignition/` stages Products, Field and Nozzle, and the Laboratory comparison |

# vertex-extraction: notes

`extraction.py` (about 16 min on 4 cores) runs 14.7 MeV protons, 3.67 MeV alphas and D/³He debris at the coupled pulse's speed through
four closure topologies (drawn, closure x2, closure x4, wider throat), four burn positions (-1, 0, +2, +4 m aft of the drawn point) and
two field multiples (x1, x4), 24 directions per species, then every vertex-source lever through every geometry with a momentum-consistent
ledger (impulse from p cos of the particles that leave; struck particles stay in the engine as deposited mass and heat). `findings.py`
writes the findings into `results/extraction.json`; the page imports it as `lab/studies/fusion-ignition/imports/extraction_c169a9f.json`.

## Findings (2026-11-24)

- Field strength alone does nothing for the drawn topology: x4 the field leaves the struck share at 0.67. Magnetised debris from an
  on-axis burn follows the same lines at any strength.
- Topology and position decide it: the burn 4 m aft gives 0.46; with closure rings x4 their current share, 0.21. Strong closure with the
  burn at or forward of its drawn point seals the nozzle (5 of 32 geometries strike every ion, no thrust).
- Best geometry for the design target (closure x4, burn +4 m): 0.94 MN for four engines (drawn 0.44 MN in this scan, 0.41 MN in the
  page ledger), heat 1,967x the radiator share (drawn 2,188x). Interception is a thrust lever, not a heat lever.
- Early extraction (80 % of the product energy out) cuts the heat to about 300x but the thrust to 0.34-0.36 MN: fast products carry
  energy, not momentum. A heat lever, not a thrust lever.
- Nothing closes: the thrust-heat frontier runs from 300x at 0.34 MN to 7,869x at 3.78 MN (x4 target mass); the mission needs 21.8 MN at 1x.

## Accounting correction found on the way

The page ledger had used the nozzle's mean axial cosine as an energy share and let every ion leave. Momentum conservation gives
I = eta sqrt(2 m P) and leaves the struck share in the engine; coupled C1 thrust falls from 0.74 to 0.41 MN and the exhaust speed rises
from 4,914 to 8,772 km/s (fewer, faster ions). ledger.py, the page and vertex-source were corrected together (ENG-064).

## Limits

Vacuum test particles from an on-axis point source (struck-share error about +/-0.10); the X-ray pickup is the drawn engine's for every
geometry (OPEN for a moved burn); coil masses scale with the capture current and are relative only; plasma expansion, detachment and
collective effects are OPEN. A moved burn point or stronger closure rings change the drawn engine and are not adopted.
