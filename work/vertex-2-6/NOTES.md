# Vertex 2.6: compact propulsion architecture and high-velocity flight protection

Research only (owner brief 2026-11-17 06:54Z). No canon, no production geometry, no squash, no deployment.
Study Doc: "Compact Vertex Architecture & Flight Protection Study" (Claude Docs, linked in the thread).

## Function

Find a compact four-engine Vertex architecture (A+ reference) that keeps every critical part protected at 0.016 c in every
phase, including braking, and test it on the same mass/heat ledger as Halo Vertex (archived in `lab/variants/halo-vertex`).

## Fixed constraints

- Ledger: `lab/variants/halo-vertex/ledger2.py` with the 2.0 corrections (dep 4.6 kt canon, 7 kt research envelope, q_max 10 MW/m^2,
  radiators 535.7 kW/m^2, four burns, ve 0.072 c).
- Dust: the T02 environment (`t02_environment.py`, copied from claude/project-thread-uwi5pl 3c665ec), LOW/NOMINAL/HIGH and an
  out-of-ecliptic case. No magnetic credit for neutral dust; no invented probabilities.
- Shield r 45 m; rim aft x 115.9 m; theta_max = atan((45 - r) / (115.9 - x_aft)).

## Code

- `protect.py` -> `protect.json`, `protect.log` (~10 s): dust events, bumper/armour sizing, shadow margins, flips, protection mass per architecture.
- `compact.py` -> `compact.json`, `compact.log` (~12 s): candidates A-D on the ledger, requirement grid, minimum speculative sets, sensitivities.

## Results

- Home braking dominates dust: engine fronts take ~43,000 events above 2.6 kJ. Protection NOMINAL: Halo 2.7 kt, A+ 1.8 kt, C 217 t.
- Shadow margins: rings 15.0 deg, body 7.65, blades 2.03, A+ engines 1.95, C engines 1.14. Blades: 140 punctures at 1 deg attitude error, 6,085 at 2 deg.
- No candidate closes. A: no closure even at driver gain 5e4. B: heat passes only at isotropic x0.01 (11.8-13.5 kt). D: heat never passes.
- C (200 m spines, stern annulus) with VBC + SR-26A (isotropic loss <= 0.39 % of fusion power) + SR-26F (forward stream 2.4e-4):
  6,271 t departure, He-3 1,988 t; fails canon 4.6 kt, propellant 3.0 kt, speculative count, He-3 supply, HIGH dust (44 kt).

## Decisions (PROTOTYPE, research)

- Recommend C as the compact reference; not closed.

## Open owner questions

1. Accept C as the compact reference. 2. HIGH dust as residual risk or gate. 3. Next lever: He-3 supply or ve.
