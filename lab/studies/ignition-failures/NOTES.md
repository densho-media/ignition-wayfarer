<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE |
| Question | What breaks first when the drawn Vertex cluster ignites at the mission point, and what would a visitor have to change? |
| Model base | main bbe1d7e; Vertex research records imported from claude/project-thread-6qwiwi @ b87a9c1 |
| Open owner questions | Is the training page right? Squash order with the engine studies (the import makes either order work). |
| Review | the preview artifact "Ignition: what breaks" (thread "Simulate engine ignition failures on Pages"); Pages after the squash |

# ignition-failures: notes

Owner idea 2026-11-16 17:17Z: show on the deployed Engineering site the current design beside what goes wrong at ignition, one
simulation where too much energy makes everything explode and one where everything melts, and put the energy and heat management to the
visitors as the question. DIAGNOSTIC and not canon: the Fiji canon, the mission numbers and the ship geometry are unchanged.

**Function.** One lever model and one per-part heat allocation, both on the recorded Vertex ledger, that drive the page
`engineering/ignition/` (`tools/story.py` writes it; `web/engineering/ignition.js` draws it). The page invents no physics.

**Inputs.** `imports/vertex_b87a9c1.json`: the 1.7 heat ledger (`vertex_dynamic.json` budget), the 1.6B capture, allowable and
neutron rows (`vertex_source.json`), the 1.7 failure energies, the 1.8 Phase F startup and power budgets, copied once with their key
paths because the engine branch is not squashed yet. `references/evidence/vertex_radiation.json` (1.5, on main): the 3D exposure by
part group and the engine heat capacity.

**Result (reference, the drawn design at the mission point, per engine).** Heat from the burn 18.1 TW against a 2.70 GW radiator share:
6,720x; with the target driver (gain 100, 50 %) 7,804x (the 1.7 hybrid 7,688x). The driver needs 1.43 TW, 28,630x the 50 MW pulse bank,
which it empties in 0.5 ms. The whole engine is +1000 K after 30 ms. Neutrons end the nearest superconductor (C2) after 1.7 s
unshielded, and the quench releases 9.7 GJ. Shielding for four burns needs about 2e6 attenuation and tens of kt. No lever setting on
established values holds. The page's "What holding takes" preset holds only with a burn ten million times quieter in photons and
neutrons, no plasma leakage and a target gain of 3 million, all far outside anything demonstrated.

**Display choices (PROTOTYPE, listed on the page).** cp 500 J/kg K; 20 kJ/kg to warm a winding from 20 K to 90 K; start temperatures;
melt temperatures by material; 10 % of the quench energy as fragment motion; a 4 ms display spread of the cascade; 10 kg/m2 radiators;
the 0.3 yr trip allowance of the 2.0 gate. Each part's share of its group's heat follows area over distance squared to the burn point.

**Run.** `python3 lab/studies/ignition-failures/model.py` (about 8 s) writes `results/ignition.json`; `site.py --json` refuses a stale
result. Test: `python3 lab/studies/ignition-failures/tests/test_model.py`.
