<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE |
| Question | What does interstellar and solar-system dust do to Wayfarer at speeds up to 0.016 c, and what would a visitor have to change? |
| Model base | main c7cca43; Vertex 2.6 dust and exposure model copied from claude/project-thread-6qwiwi @ 874dca7 |
| Open owner questions | Is the training page right? The Brow layer and skin thicknesses (OPEN in canon, 5 mm PROTOTYPE here). HIGH dust as residual risk or gate (Vertex 2.6 Q2). |
| Review | the preview artifact "Dust: what hits at speed" (thread "Simulate ignition failures and dust impacts"); Pages after the squash |

# dust-impacts: notes

Owner brief 2026-11-17 08:02Z: beside the ignition failures, show as a simulation what happens when the ship hits space dust at
different speeds, since dust becomes the main problem at high speed. Research first, then design and build. DIAGNOSTIC and not canon.

**Function.** One impact model for a single grain and the Vertex 2.6 mission exposure, both driving the page `engineering/dust/`
(`tools/story.py` writes it; `web/engineering/dust.js` draws it). The page invents no physics.

**Research (what the numbers rest on).**
- Energy grows with the square of speed. At 0.016 c (4,797 km/s) a grain carries 1.15e13 J/kg, 2.75 million times its mass in TNT:
  a 1 µg sand grain 11.5 kJ (2.75 g TNT), a 1 mg grain 11.5 MJ (2.75 kg TNT). Every atom arrives with about 119 keV per nucleon, far
  above any chemical bond (eV) and vaporisation (about 10 MJ/kg): the grain and the bumper it hits become plasma.
- Regimes by impact speed (order of magnitude): below about 3 km/s the grain stays whole; 3-7 km/s it shatters (the Whipple-shield
  range, tested in light-gas guns to about 7-10 km/s); above about 7 km/s it melts, above about 20 km/s it vaporises; above about
  100 km/s the impact makes a plasma (how Galileo, Ulysses and Cassini counted dust). Electrostatic accelerators reach about 100 km/s for
  sub-micron grains only. Giotto met Halley's dust at 68 km/s behind a 1 mm bumper. Above about 1,000 km/s nothing has been tested.
- Impact rules (Vertex T02 / 2.6, EXTRAPOLATION): crater volume k E with k 1e-11 / 3e-11 / 1e-10 m3/J (LOW / NOMINAL / HIGH); a bumper
  at least 0.25 grain diameters thick turns the grain into a cloud that spreads in a 30 deg cone over the stand-off; the wall behind
  fails above 1e4 J/m2. So the 2.0 m canon disruptor stand-off stops grains up to 3.4 g at 7 km/s but only 7.3 µg at cruise.
- Environment (T02): Grün interplanetary dust, the New Horizons Kuiper-belt dust and the Ulysses interstellar dust, with LOW / NOMINAL /
  HIGH envelopes. Neutral dust is not deflected by fields, warning times are milliseconds, the plume vaporises only grains below 1e-15 kg.

**Correction to Vertex 2.6 (MODEL fix).** `protect.mission()` places each braking burn one accelerating-burn length (155.7 AU) before
its end point, but a braking burn of the same duration covers 167.6 AU (constant thrust, the ship heaviest at the start). The home braking
burn therefore runs from 156 AU to -11 AU, through the Sun, where the dust density is held at its 0.3 AU value; 20,800 of Vertex 2.6's
43,000 engine-front breaches come from below 0 AU. `model.py mission()` ends each braking burn where it should (turn-around at 324 AU,
home at 1 AU). The import stays unchanged; `as_vertex_2_6()` reproduces its numbers for comparison.

**Result (Vertex research mission, A+ cluster, NOMINAL, corrected path).** 2,995 grains get past the 2 m disruptor over the trip,
nearly all on the way out, in the Kuiper belt's dust and beyond, where the ship is already fast (LOW 1.9, HIGH 503,000). Braking home, engine first, the four engine
fronts meet about 15,700 grains above the 2.6 kJ that breaches a bare 5 mm face (Vertex 2.6: 43,000). The radiator blades take about 50
punctures at 0.2 deg attitude error.

**Display choices (PROTOTYPE, listed on the page).** The 5 mm C/C disruptor layer and 5 mm skin (thicknesses OPEN in canon); 0.2 deg
attitude error for the trip; sparks stand for many grains each, the counters are the model numbers.

**Run.** `python3 lab/studies/dust-impacts/model.py` (about 1 s) writes `results/dust.json`; `site.py --json` refuses a stale result.
Test: `python3 lab/studies/dust-impacts/tests/test_model.py`.
