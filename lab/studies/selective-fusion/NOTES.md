<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE |
| Question | Selective Fusion Engineering: how far can selective fuelling, spin polarisation, hot-ion operation and burn geometry make the Vertex D-3He burn cleaner, and how do we show the engine's energy channels to visitors? |
| Model base | main 3866ebf + accelerator-fusion (5a2152e); reactivities and radiation from src/wayfarer/vertex_radiation.py, vertex_source.py |
| Branch | claude/project-thread-ae02qr, owner brief 2026-11-22 |
| Open owner questions | S1 is the explainer right for the public pages; S2 run SFE-1 (Fokker-Planck hybrid with polarisation) next; S3 a Breakthrough Lab entry for D-D quintet suppression; S4 open a burn-geometry study for photon avoidance |
| Review | engineering/fusion/ on Pages after the squash; branch preview https://claude.ai/artifact/BDCoSgMNZ9BFWab9YzNkFN; report https://claude.ai/artifact/Q4nZWXiVz6izTYAMtcCvy1 |

# selective-fusion: notes

Owner brief 2026-11-22 07:19Z. Working decisions: Vertex stays the baseline; the accelerator engine is a grounded negative result
(`lab/studies/accelerator-fusion`); selective fuelling and spin polarisation continue; canon numbers by default; Vertex is not solved.

**Selective Fusion Engineering (SFE)** is the family of techniques that make the Wayfarer's D-3He burn cleaner, more selective and
more useful without new physics: selective fuelling (D-lean), spin-polarised D and 3He, hot-ion / cooler-electron windows, selective
injection by micro-accelerator arrays, AI-assisted control of collective plasma, injector and field modes, preferential handling of
fast ions, fewer neutron side reactions and less radiation seen by hardware. Future technology improves control within physics; it
does not change cross sections.

**Function.** One zero-dimensional energy-channel model (`model.py`) over the explainer's controls, read by the page
`engineering/fusion/` (`tools/story.py` writes it, `web/engineering/fusion.js` draws it). The page looks values up and applies the
same linear ledger; it computes no new physics.

**Fixed constraints.** Canon operating point (209 TW jet, 261 TW fusion), directed efficiency 0.8, B01 absorbed fraction 4e-5,
14.4 GW hot radiator x hot share 0.75. Engine studies: photon exposure 0.62 (Vertex 1.5), neutron absorption 0.87 (Engine 1.4).

**Assumptions (each shown on the page).** Te = Ti or 0.7 Ti; D-D triton burn-up 0.5; polarised D-3He rate x1.5 (full polarisation,
nuclear-physics expectation); D-D suppression x0.25 SPECULATIVE (one 1999 partial-wave analysis gives 0.22 at 90 keV, data
parametrisations give none; PolFusion has not reported); injector chain efficiency 0.765 (advanced technology). Not modelled:
synchrotron radiation, transport, burn dynamics, 3He from D-D burning, polarisation loss.

**Results.** Thermal 1:1 at 100 keV: 96.6 % of the fusion power is born in charged products, 22 % is then radiated as bremsstrahlung and 3.4 % leaves in neutrons, so 74.6 % reaches the nozzle and 59.7 % becomes thrust; at
62 % photon exposure the hardware heat is ~5,400x the drive radiator share. Every lever together (polarised with assumed D-D
suppression, 5 % photon exposure) is still ~350x; with zero photon exposure neutrons alone leave ~37x. The burn cannot close B01 by
prevention alone: it needs prevention, avoidance (photons escaping past hardware) and tolerance together.

**Tests.** `python3 -m unittest discover -s lab/studies/selective-fusion/tests` (ledger closure, D-lean and polarisation trends,
hot-ion trade, B01 not closed). Lab tests stay outside CI (D-T00-1).

## Implementation note: the Fusion engine explainer

**What it teaches.** One wanted reaction (D + 3He -> 4He + p, all charged, steerable by the nozzle field) and the problems around
it: D-D side reactions (half give a 2.45 MeV neutron, half a triton that may burn into a 14.1 MeV D-T neutron), bremsstrahlung
X-rays from hot electrons, and the heat both leave in hardware. Three views share one state: Reactions (which nuclei fuse, at the
model's relative rates; D-D drawn 3x as often so it stays visible, as the caption says), Engine (where each product goes:
nozzle, shield, coils, space) and Energy budget (a two-stage flow from fusion power to thrust, sideways exhaust, heat in the ship
and escape). The verdict line and the Wayfarer scale line put the ledger in the ship's own numbers.

**Controls.** Fuel mix (10-70 % D), ion temperature (40-200 keV), thermal or hot-ion (MODEL-BASED), polarisation (none
ESTABLISHED, aligned MODEL-BASED, aligned with D-D suppression SPECULATIVE), X-ray exposure of hardware (0-100 %). Reset to the
reference point and copy-a-link (URL hash `d= t= m= p= x= v=`).

**Simplifications.** Zero-dimensional and steady; no synchrotron, transport, burn dynamics, polarisation loss or 3He breeding;
fixed triton burn-up 0.5; neutron absorption 0.87 and nozzle directed efficiency 0.8 fixed; the sliders snap to the study grid
(546 points), so the page never interpolates physics. Particle motion is a picture of shares, not a particle simulation.

**Data classes.** Ledger numbers are SIM (this study, not canon); the operating point, B01 and radiator are SPEC and labelled with
their sources; polarisation options carry their evidence class chips.

**Extension points.** A new fuel cycle or lever is a new entry in `POL` or a new axis in `model.py` plus its button in
`tools/story.py` `fusion_page`; the page reads axes and labels from `fusion.json`. A new ledger term (for example synchrotron or
a direct-conversion stage) goes into `ledger()` and the mirrored `evaluate()` in `web/engineering/fusion.js`; the five study
check points in `fusion.json` must still be reproduced by the page (`tools/web_check.py` "fusion" checks, `site.py` refuses a
stale `inputs_hash`). A comparison mode (two settings side by side) fits as a fourth tab using the same `evaluate()`.

**Validation (2026-11-22, cloud, software rendering).** Lab tests 5/5; the page reproduces all five study check points; no console
errors; no horizontal overflow at 390x844, 844x390, 820x1180, 1366x768 and 1600x900; axe-core WCAG 2.1 A/AA: no
violations on desktop and phone; reduced motion draws a static frame; offscreen or hidden tabs stop drawing. Frame rates are SW and
relative only. Cost: 2D canvas, no WebGL and no model download; page JS ~30 kB, CSS ~4 kB, study table 57 kB, loaded only on this page.
