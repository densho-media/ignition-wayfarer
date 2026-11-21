| Work entry | |
| --- | --- |
| Kind | Study (research only) |
| Status | ACTIVE (awaiting owner Q1-Q4) |
| Question | Could the Wayfarer use its structure as an accelerator-driven, selective D-3He fusion system that beats the Vertex Drive on energy, radiation and thrust? |
| Model base | main 3866ebf (Vertex 1.6-2.11 and EXT-01 in lab/studies/vertex-closure; FPS V1.1) |
| Branch | claude/project-thread-ae02qr, owner brief 2026-11-21 |
| Open owner questions | Q1 accept the negative result for A-C and keep Vertex; Q2 carry selective fuelling into the R2 fuel-cycle comparison (settles FPS `he3_per_d_molar`); Q3 register polarised D with quintet suppression as a Breakthrough Lab item; Q4 briefs use the canon length (289.5 m body, 301.5 m overall), not 80-90 m |
| Review | Claude Doc https://claude.ai/artifact/RycBWQ7mB16DmvnJAX9uYy |

# accelerator-fusion: notes

**Function.** Screen accelerator-driven, non-thermal D-3He architectures against the Vertex baseline and the ship's own budgets.

**Fixed constraints (canon, read by `asf.py`).** Operating point 261 TW fusion / 209 TW jet / four engines (docs/FUEL_SYSTEM.md 10.3);
B01 absorbed fraction 4e-5 and hot share 0.75 of the 14.4 GW hot radiator; ve 19,201 km/s; exhaust per reacted fuel 1.53; ship 289.5 m
body, 301.5 m overall (the brief's 80-90 m is outdated); engine envelope 31.9 m x r 11.44 m; 250 t drive allowance.

**Unknowns.** Spin-polarisation survival and the quintet D-D suppression factor; burn geometry that hides photons from hardware;
fast-ion pitch-angle dynamics (D-D bracket ~8x); cross section above 900 keV (held); synchrotron and secondaries (not modelled).

**Design freedom.** Fuel mix (`he3_per_d_molar`, open in FPS), injector type, Ti/Te.

**Method (`asf.py`, stdlib, <1 s).** Bosch-Hale D-3He cross section (validated against the reactivity fit to 1-3 % at 10-100 keV;
peak 0.82 b at 260 keV), D-D from vertex_source; kinematics by arrangement; Coulomb momentum-transfer vs fusion cross section;
Brillouin density limit for non-neutral beams; Stix slowing down of a D beam in 3He (burn-up P, gain F = Y P / E0); bremsstrahlung
(vertex_radiation.brems_W_m3); D-D Monte Carlo over the slowing-down distribution; hot-ion e-i exchange (vertex_source.tau_ex);
three declared maturity levels (present / advanced / speculative) for converter, recovery, intercept, absorption and nozzle.

**Results (results/asf.json).**
- 61 Coulomb scatterings per fusion at 400 keV c.m. (44-75 over 300-900 keV); class 1.
- Non-neutral beams at 40 T: 233 W/m3, 2e7 engine volumes per engine; class 1.
- Beam-target F <= 0.6 for Te 2-120 keV (0.67 at 200 keV with a held cross section): never self-powering; vented D gives 5-54 kg
  exhaust per kg reacted (mission 1.53).
- Ion-only collider needs 99.997 % recovery per pass for B01; entropy floor 1.6e-6 of fusion energy (not binding).
- Selectivity: neutron power share 0.06-1.4 % (beam-target) vs 3.6-4.1 % thermal 1:1.
- Heat vs drive radiator (advanced / speculative): collider 6x / 2x (at impossible density), hybrid 2,050x / 670x, thermal 2,070x / 750x;
  Vertex 1.5: >= 854x. Bremsstrahlung burns need <= 0.02 % photon intercept.
- Power processing 87-137 TW per engine; at 10 MW/kg 9-14 kt per engine.

**Decision.** Keep Vertex. Accelerator-as-engine (A-C): negative result. Selective fuelling (D): carry into R2 as a fuel-cycle lever.
No canon, geometry or Drive change.
