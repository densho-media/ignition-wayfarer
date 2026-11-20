# EXT-01 External Pulse Propulsion Architecture: report

Owner brief 2026-11-15 ("WAYFARER: Post-Vertex 1.5 Architecture Decision"). Research only, NOT canon. The Wayfarer model, the four
deployed Vertex engines, mission physics, fuel cycle and lore are unchanged. Every number below comes from
`python3 lab/studies/external-pulse/ext01.py` (inputs `params.toml`, the operating point and mission from `data/`, the fusion-source
shares from the released Vertex 1.5 evidence). Output: `results/ext01.json`, `figures/`.

## Summary

- **No external pulse concept closes Wayfarer's 0.016 c four-burn mission on established physics.** With an isotropic pulse (the only
  kind any fusion micro-pulse is known to give) the pusher plate (A) has no solution at any departure mass, and the magnetic pusher (B)
  and remote field coupling (C) miss the 4.6 kt envelope by 6x and 15x in departure mass while overloading the radiator 4-5x.
- **A pusher plate makes the Vertex thermal problem worse, not better.** The plate sees 7-33 % of the burn's sky and absorbs the
  stagnation heat: at least 132x the radiator's hot budget at the most favourable corner (about 2,500x on the canon burn schedule), against
  Vertex 1.5's 854x. Cooled by ablation instead it reaches about 20 km/s (Isp about 2,000 s), the range Orion's own studies claim and about
  1,000x short of the 18,700 km/s the mission needs.
- **A magnetic pusher really does shrink the photon load, then moves the heat to the plasma-field interface.** A coil can present
  0.015-1.25 % of the sky against Vertex's 62 %, so photon heat drops by orders of magnitude. But plasma leaking along the field onto the
  coil decides the result: at the smallest leak the project has evidence for (1 %, Vertex 1.4) the radiator is overloaded 222x. B closes in
  6 of 314,928 cases, all at one corner where four UNVERIFIED best cases hold at once. A coil could tolerate a leak of about 0.005 %.
- **Remote coupling trades heat for magnet mass.** Farther fields cut the coil's sky share to 1e-6-0.25 %, but the stored field energy
  grows with the cube of the reach (dipole fall-off), and the magnetic virial theorem turns that energy into structure mass. No case closes.
- **The burn being outside the ship does not help by itself.** At 19,200 km/s every watt of jet power comes with heat in some hardware;
  with the canon radiator the hardware may absorb about 4e-5 of the yield, whatever the architecture. External placement changes which
  hardware absorbs it.
- **Recommendation: build nothing.** Keep Vertex as the documented prototype. None of the three concepts justifies development for this
  mission. If the owner wants a next propulsion milestone, the useful one is a short requirements study of the two quantities every
  concept depends on (the fusion source's photon share, SR-1, and the plasma-hardware leak a magnetic interface can reach), not a new engine.

## 1. The question and the method

The brief asks whether moving the fusion event outside the spacecraft (external pulse propulsion) can do what Vertex 1.5 showed the
compact internal burn cannot: deliver the mission's exhaust velocity without heating hardware beyond the 14.4 GW radiator. A design
cannot pass because its burn is outside; it must close on momentum, energy, heat, mass, schedule and fatigue together.

One ledger per joule of pulse yield:

- **Source.** Photons f_γ, neutrons f_n and debris kinetic energy f_k = 1 - f_γ - f_n. The shares are Vertex 1.5's three source cases
  (photons 12.5, 21.7, 84.8 %), because the burn physics does not change with its location. Optionally a share of the photons is turned
  into debris energy by absorbing matter (UNVERIFIED, granted with no mass penalty).
- **Debris speed cap.** The pulse mass is at least its fuel, so v_d^2 <= 2 f_k b ε with burnup b and D-3He energy ε = 3.53e14 J/kg:
  about 23,000 km/s at b = 0.8, 14,000 km/s at b = 0.3.
- **Momentum.** An isolated pulse has no net momentum. Isotropic debris on a cone of half-angle θ gives impulse (1+e) m v_d sin²θ / 4
  (restitution e). A directed pulse that sends a mass share β forward must send the rest back faster; at the speed cap its exhaust velocity
  is (1+e) sqrt(β(1-β)) x the isotropic cap, best at β = 1/2.
- **Heat into hardware.** Photons and neutrons in the hardware's solid angle, the stagnation share of the dissipated energy (A), plasma
  leak and the hardware's view of the dissipated energy (B, C). Coil heat that reaches the 20 K cold mass costs 1 + 1/COP at the radiator
  (COP 0.0034 at 1,800 K).
- **Mission.** The operating point's rocket equation with tank growth (15 % of added propellant), the departure envelope (4.6 kt), the
  burn-time share of the LOCKED 6 y (canon schedule 28.5 d = 1.3 %; longer burns delay arrival by half the extra burn time), the thrust
  that share needs, and the hot budget (10.8 GW).
- **Hardware mass.** Plate: per-pulse velocity jump within the shock stroke and at most 3-30 m/s. Coil: the magnetic virial theorem,
  M >= W_B ρ/σ, with stored field energy W_B = reach³ x captured debris energy.
- **Gates.** Departure mass, radiator heat, debris speed, fatigue (1e10 cycles), schedule. A case closes when every gate is at most 1.

The search runs the full product of every bracket at 20 debris speeds (104,976 cases for A, 314,928 each for B and C), then removes
the UNVERIFIED best cases one at a time (the assumption ladder).

## 2. Mission requirement (independent of Vertex)

| Quantity | Value |
| --- | --- |
| Exhaust velocity for 4.6 kt departure (canon envelope) | 18,738 km/s |
| Exhaust velocity for 46 kt / 460 kt (exploratory only) | 10,231 / 9,501 km/s |
| Tank-growth limit (no departure mass closes below it) | 9,420 km/s |
| Hardware heat allowed per joule of yield at 19,200 km/s, canon schedule | 1.1e-5 / 4.4e-5 / 1.8e-4 for momentum coupling μ = 0.5 / 1 / 2 |
| Thrust on the canon schedule at 19,200 km/s | about 21 MN, from the mission alone |

The allowed heat follows a closed form: with exhaust velocity v = μ v_d, heat per newton is κ v / (2 f_k μ²) and the thrust is P v / (φT),
so the radiator holds κ <= 2 f_k μ² φT H / (v² P). It falls with the square of the exhaust velocity: the mission's high exhaust velocity,
not the engine layout, is what makes the heat budget so tight.

## 3. The three architectures and their precedents

| Concept | How momentum reaches the ship | Precedents (claims, not demonstrations) |
| --- | --- | --- |
| A, mechanical pusher plate | Debris stagnates on a plate; shock absorbers spread the impulse | Project Orion (GA 1958-65), Isp about 2,000-6,000 s claimed; Dyson 1968 thermonuclear Orion, ship speeds of order 1,000-10,000 km/s claimed; Medusa (Solem), Isp 50,000-100,000 s claimed |
| B, magnetic pusher | A coil near the burn turns the debris; field stress pushes the coil | Mini-Mag Orion (Andrews Space; Lenard and Andrews), Isp 10,000-30,000 s claimed; MagOrion, Isp above 10,000 s claimed |
| C, remote field coupling | A far-reaching (inflated) field turns the debris far from any hardware | M2P2 (Winglee et al. 2000), field inflation for solar-wind sailing, later contested; no pulse-capture precedent |

All of them assumed fission or thermonuclear pulse units whose energy partition, debris mass and directionality do not apply to a
D-3He micro-pulse. None validates the fusion system assumed here, and this study uses none of their device designs. The highest claim
(Medusa, about 1,000 km/s) is about 19x short of the mission requirement.

## 4. Results by concept

| | A pusher plate | B magnetic pusher | C remote coupling | Vertex 1.5 (reference) |
| --- | --- | --- | --- | --- |
| Hardware share of the burn's sky | 6.7-33 % | 0.015-1.25 % | 0.00007-0.25 % | 62 % (real mesh) |
| Fastest exhaust velocity, any bracket | 17,300 km/s | 23,100 km/s | 23,100 km/s | 19,200 km/s (design) |
| Fastest, isotropic bare pulse | 7,200 km/s | 10,800 km/s | 10,800 km/s | not applicable |
| Cases that close / searched | 0 / 104,976 | 6 / 314,928 | 0 / 314,928 | blocked (Outcome C) |
| Best closure, all brackets | 132 (heat) | 1.00 | 1.07 (mass, heat) | 854x radiator at best |
| Best closure, no photon conversion | 160 (heat) | 1.02 (schedule) | 1.16 (mass) | |
| Best closure, isotropic bare pulse | no solution (below the tank limit) | 6.2 (mass; heat 5.2) | 14.7 (mass; heat 4.0) | |
| Best closure, plus leak >= 1 % | as above | 222 (heat) | 573 (heat) | |
| Nominal case (middle brackets) | 7,700 km/s; 13.5 % of the yield into hardware | 11,000 km/s; 0.30 % | 11,000 km/s; 0.25 % | 4e-5 allowed |

Closure is the largest gate ratio of the best case (1 means it closes). The figure `ext01_ladder.svg` shows the ladder, and
`ext01_velocity.svg` the velocities against the requirement and the precedent claims.

### A: mechanical pusher plate

- **Momentum.** An isotropic pulse delivers at most (1+e)/4 of the debris momentum; with a plasma that stagnates (e at most 0.5) the
  exhaust velocity stays below about 7,200 km/s, under the tank-growth limit. Only a directed pulse (UNVERIFIED) gets past it.
- **Heat.** The plate cannot be made small in the burn's sky: it must cover the debris cone. With photons 12.5 % of the yield and a
  quarter of the stagnation energy absorbed, at least 5.4 % of the yield enters the plate. That is about 965 kW per newton of thrust
  against an allowed 7.3 kW/N even on the most lenient schedule.
- **Ablation.** Losing surface mass instead of radiating caps the exhaust velocity at μ sqrt(f_k h / (2κ)): at most about 20 km/s with
  h = 1e8 J/kg. That reproduces Orion's claimed range and is the plate's real ceiling.
- **Mechanics.** The best case runs 6 t (TNT) pulses at 1 kHz; a plate jumping 30 m/s per pulse sees about 3,000 g, and the 0.7 y of
  burning gives 4.7e10 cycles, beyond any tested fatigue range. The canon 28.5-day schedule needs 28 MN and about 120 t pulses.
- **Shielding.** The neutron source per newton is 1.4x Vertex's (788 kW/N against 545 kW/N); the plate shadows only its own cone.

### B: magnetic pusher

- **Momentum.** Field reflection can be nearly elastic, so B reaches the debris speed cap: 23,100 km/s with a directed pulse at
  β = 1/2, but only about 10,800 km/s with an isotropic one. That alone fails the 4.6 kt envelope (it needs 18,700 km/s).
- **Heat.** The coil's photon intercept is small. The binding term is plasma reaching the coil: the bare-burn best case tolerates a leak
  of only about 0.005 % of the captured energy. Vertex 1.4's internal cavity leaked 1-28 %; no study shows an external coil doing 200x
  better. Cold-mass heat costs about 300 W at the radiator per watt (COP 0.0034).
- **Closing cases.** All six use, at the same time: a directed pulse at β = 1/2, 90 % photon conversion with no added mass (inconsistent
  at the fuel-only speed cap), a leak-free elastic reflection, a coil 0.5 % of its radius thick as the burn sees it, burnup 0.8 and 1 kHz.
  They then need 21 MN, 261 TW of fusion, 62 t (TNT) pulses, a 208 t magnet storing 4.2e11 J, and 2.5e9 load cycles.
- **Shielding.** The neutron source per newton equals Vertex's (542 kW/N): the shadow shield does not get lighter.

### C: remote field coupling

- **Momentum.** The same as B (same reflection physics).
- **Heat.** The coil's sky share falls with the square of the distance, so photon heat almost vanishes.
- **Mass.** The debris must be turned where the field is weak. A dipole's stored energy outside the bubble grows with reach³, so
  reach 3 needs 27x the field energy of reach 1; the virial theorem makes the magnet outgrow the ship (5.9 kt on the canon schedule).
  The best case misses by 7 %; isotropic 15x on mass.

## 5. Does external pulse propulsion reduce the thermal problem?

- **A: no.** It moves the heat from Vertex's cage into a plate that must cover a large solid angle and absorbs the stagnation energy as
  well. The best plate case is about 3x worse than Vertex's best bound on the canon schedule.
- **B and C: they reduce the photon problem, and move the heat to the plasma-field interface and the magnet.** The SR-1 gap (photons at most
  0.59 % of the yield) becomes a leak requirement (at most about 0.005 % of the captured plasma) plus a directional-pulse requirement for the
  momentum. For C it also becomes a magnet mass that grows with the cube of the reach.
- **In every concept** the heat per newton scales with the exhaust velocity times the hardware's absorbed fraction. At 19,200 km/s that
  fraction must stay near 4e-5 of the yield. Placing the burn outside changes the geometry term, not the scaling.

## 6. Technology gaps

| Gap | Needed by | Status |
| --- | --- | --- |
| Directional fusion micro-pulse (forward mass share near 1/2) | A, B, C at the mission velocity | UNVERIFIED; no source; this study gives no device design |
| Photon conversion without slowing the debris | best cases of all three | Inconsistent with the fuel-only speed cap; not modelled |
| Plasma leak onto a coil at or below about 0.005 % | B, C | No evidence; Vertex 1.4 found 1-28 % for its cavity |
| Elastic, stable field reflection of pulse plasma | B, C | Flute and Rayleigh-Taylor losses not modelled |
| Pulse rate of 100-1,000 Hz at 10-100 t (TNT) yield | B best cases | No driver established |
| Giga-cycle fatigue of the load path (1e9-1e10 cycles) | A, B | Beyond tested data |
| Pulse burnup 0.8 | all | WORKING operating-point value; no mechanism (four-burn study) |
| Photon share far below 12.5 % (SR-1) | Vertex and A | Registered as BT-008, NON_CANON |

## 7. Advantages and disadvantages

| | Advantages | Disadvantages |
| --- | --- | --- |
| A | Simplest physics; decades of design study; no superconductor; precedent claims reproduced by the model | Large sky share; stagnation heat; ablation caps it near 20 km/s; giga-cycle plate fatigue; isotropic pulse cannot reach the tank limit |
| B | Smallest heat of the three when the leak is near zero; elastic reflection doubles the momentum; photons mostly miss the coil | Needs a directional pulse and a near-perfect leak-free field; cold-mass heat is 300x expensive; 200 t magnet at kHz loads |
| C | Hardware almost invisible to the burn | Magnet mass grows with reach³; field inflation unverified for pulse capture; same momentum limits as B |

## 7a. Bounds reported per concept (the brief's list)

| Bound | A | B | C |
| --- | --- | --- | --- |
| Momentum transferred | (1+e) sin²θ/4 of the debris momentum (isotropic); (1+e)β of the forward part (directed) | (1+e) x captured, minus leak | as B |
| Energy and momentum conservation | ledger closes to 1e-12; exhaust energy >= ½ m v_eff² (tests) | same | same |
| Radiation intercepted | 6.7-33 % of photons and neutrons | 0.015-1.25 % | 0.00007-0.25 % |
| Heat deposited in hardware | >= 5.4 % of the yield (best) | 4e-6 of the yield (closing corner) to 0.3 % (nominal) | 3e-5 (best) to 0.25 % (nominal) |
| Ablation or expendable shielding | caps v_eff near 20 km/s | none | none |
| Pulse impulse and plate acceleration | 1.5 kN s at 1 kHz; about 3,000 g at 30 m/s per pulse | 21 kN s per pulse in the closing case | 6.5 kN s |
| Pulse rate and fatigue | 1 kHz, 4.7e10 cycles | 1 kHz, 2.5e9 cycles | 1 kHz, 9.5e9 cycles |
| Effective exhaust velocity and Isp | <= 17,300 km/s (1.77e6 s) directed; 7,200 km/s isotropic; 20 km/s ablative | <= 23,100 km/s (2.35e6 s); 10,800 km/s isotropic | as B |
| Propulsion-system mass | plate floor under 1 t (momentum floor only; thermal plate not sized) | 120-210 t magnet (virial) | 330 t to 5.9 kt |
| Propellant consumption | 4.4 kt at the best case | 2.3 kt at the closing case (canon 2.8 kt) | 2.9 kt |
| Crew neutron source per newton vs Vertex | 1.4x | 1.0x | 1.1x |
| 0.016 c compatibility | no (isotropic below the tank limit) | only at the UNVERIFIED corner | no |

## 8. Recommendation and next propulsion milestone

1. **Do not develop A or C for Wayfarer.** A is bounded near Orion's own claims (tens of km/s with ablation) and fails thermally
   when radiator-cooled; C's magnet mass grows faster than its heat falls.
2. **Do not build B.** It is the only concept with a non-empty region, but that region needs four UNVERIFIED best cases at once. Its
   result is a requirement, not a design: a directional fusion pulse and a magnetic interface that leaks below about 0.005 %.
3. **Keep Vertex as the documented prototype** (Outcome C) and the canon mission unchanged.
4. **Next milestone, if the owner wants one: a source-and-interface requirements study, not an engine.** Bound (a) the photon share a
   D-3He burn can have (SR-1) and (b) the plasma-hardware leak a magnetic interface can reach, with the physics already in the project
   (Vertex 1.4's plasma model and 1.5's source model). Both decide every architecture at once. Radiation transport (Geant4/OpenMC) stays
   deferred as the owner directed. The alternative the owner may prefer is an owner-level mission review (exhaust velocity, burn schedule,
   departure mass), because the heat law shows that the mission's 19,200 km/s, not the engine layout, sets the 4e-5 absorption limit.

## 9. Limits of this study

- Every bracket is PROTOTYPE unless named; the search grants the best case of each and shows what happens as they are removed.
- No device design: yield partition, directionality and photon conversion are numbers, not hardware.
- No radiation transport; photons meeting hardware are absorbed, neutrons deposit 10-100 % (the best case uses 10 %).
- The plate's thermal design, the coil's shielding and the field's plasma stability are not modelled; each would make A, B or C worse.
- Literature numbers are proponent claims from secondary sources; primary papers (Dyson 1968, GA reports) were not reachable from the
  session.
