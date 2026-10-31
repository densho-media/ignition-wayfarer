# Pass 6 (2026-10-31): attitude, F01 torus loads, G01 allocation, D03 SP-13 exit

Owner 2026-10-31 13:43Z: "execute as you see it fit" (the four slices proposed in the thread). Science decisions under the owner's
delegation (HSFP; research-based); values PROTOTYPE unless sourced.

## D03 — SP-13 independent exit (study, no production geometry)

- **Function:** a second exit from SP-13 (suit service) that does not share the SP-12 / trunk path, ending in the storm refuge.
- **Fixed:** the 2026-10-16 gallery topology (owner-preferred L2 study, 15!A199): 1.20 m bore at az 125°, r 3.8 m, outside the trunk;
  refuge X 94.15–96.95, 20 g/cm² water; SP-13 X 104.95–107.10 (25.7 m³); 80 kPa both ways as an analysis input.
- **Unknowns:** leaf/dog ratings, seals, the antechamber water-jacket stack, routing past survival reserve 1.
- **Decision (`d03_sp13_exit.py`):** an isolation antechamber at the refuge end (2.6 m, 4.0 m³) with two pressure-seated plugs seating
  in opposite directions, equalisation valve and manual override at each leaf from both sides. 80 kPa either way seats a leaf (106 kN
  on the 1.30 m seal) instead of loading dogs (13.3 kN each on 8 dogs for a single hinged leaf). Antechamber equalises from vacuum in
  80 s through a 25 mm valve. It keeps the refuge sealed and shielded in all 6 studied single faults (the single stepped closure: 2 of 5),
  for 509 kg against 140 kg. At locked 1.5 g the 9 m gallery is a shaft: ladder + protected fall arrest, casualty care in place, hoist
  only after thrust reduction.
- **Design freedom:** antechamber placement inside the refuge's water envelope, leaf hinge sides, valve positions.
