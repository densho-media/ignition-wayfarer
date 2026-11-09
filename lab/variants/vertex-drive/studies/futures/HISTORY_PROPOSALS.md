# T06 IGNITION technology-history proposals

> **NON-CANON PROPOSAL TEXT.** Nothing here is IGNITION lore or canon. It is offered to ApeDevil to accept, change or reject. It edits no
> culture, lore or Drive workbook (D-11), and it names no date, person, institution or faction, because the IGNITION timeline could not
> be read in this session (ASSUMPTIONS.md A-27). Where canon later supplies names and dates, these proposals should be fitted to it, not
> the reverse (D-T06-3).

Status: FINAL proposal, 2026-11-09, after the T01-T04 handoffs. Each proposal names the breakthroughs it narrates and the credibility of
each. The rule throughout: the story may make engineering happen; it may not make physics different. Where a step is a declared
breakthrough, the text says so.

## H-1 "The cadence problem" (era E1)

**Narrates:** VTX-01C target factory, VTX-01B rep-rated drivers, VTX-05A engagement. Credibility **B**.

The first ignitions were single events, a shot a day. The hard part of fusion propulsion turned out not to be lighting a target but
lighting a hundred and seventy of them a second for years, each one engaged to a few hundredths of a millimetre, each one launched fast
enough to outrun the wreckage of the last. A proposed history: the industry that solved this was the terrestrial inertial-fusion power
plant, whose economics needed hundreds of thousands of targets a day; the drive inherited its factories, its injectors and its control
software. The Vertex target factory is that plant's descendant, spending about 0.6 MJ per target, a few hundred-thousandths of the
fusion power.

*Physical manifestation (for T05):* target factory and magazines in the equipment module; two injectors with launchers of several km/s;
tracking stations along the pellet path. All PARAMETRIC_PLACEHOLDER.

## H-2 "Hot iron" (era E2)

**Narrates:** VTX-07A split warm loop, VTX-07C house load. Credibility **B**.

Every ship before the Vertex line carried radiator wings kilometres wide, because its machinery could not tolerate heat. The quiet
revolution was in power electronics and magnetic cores that run hot, where a radiator sheds far more per square metre than at 400 K.
A proposed history: this came from industries with no interest in space (deep geothermal, hypersonic flight, Venus landers), and the
shipwrights adopted it late, one component at a time. The model is sober about how far it got: with each of fourteen component types at
its own target temperature, the warm loop behaves like one at 628 K, not 800 K, and that shortfall is the largest single correction in
T06's synthesis (T01). With today's components, 489 K, no Vertex ship closes.

*Physical manifestation:* split warm manifolds and radiator bands per component class; warm wings of about 2.7 km (V4) to 8.3 km (V3).

## H-3 "The coupling threshold" (era E3) — declared breakthrough

**Narrates:** VTX-01D D-T spark, VTX-01A fuel-only D-³He target, VTX-01. Credibility **B in kind, declared in degree** (D-T06-1).

Physics allows D-³He to burn, but squeezing fuel costs energy, so a driver can only win as much gain as its compression efficiency
allows. A proposed history in two steps, both consistent with known physics. First came D-T sparks that light D-³He burn waves,
accepting a little tritium (tens of kilograms per voyage) for the sake of ignition at all. Second, and slower, came the long climb in
coupling: the share of driver energy that ends up in the fuel at the lowest entropy. The story must say plainly that the coupling
reached at least half of the physical ideal. That is an event in the Vertex history that is chosen, not derived. The model shows why it
matters: at a half the ship is about 38 kt, at a third about 110 kt, at a fifth about 360 kt.

*Physical manifestation:* nothing visible at the burn. A target-formation coil sits at the injector muzzle (CONCEPTUAL_ILLUSTRATION).
The pulses are larger than FDP-1's: about 43 t TNT at 173 Hz in V3, against 19.5 t at 212 Hz.

*Not narrated:* where kilotonnes of ³He come from. That is a fuel-economy history (lunar regolith, gas-giant atmospheres) for the owner
to place.

## H-4 "Rings that remember" (era E4) — declared in degree

**Narrates:** VTX-02A canon Fiji card, VTX-02B no-insulation REBCO loops, VTX-03 pulsed nozzle, T03-NEW-1 closure coils. Credibility
**C** (Fiji, canon) and **B**; nozzle at its ideal model **declared** (D-T06-2).

Fiji does in this history exactly what canon says and nothing more: it amplifies a slowly applied seed field up to thirty-fold and holds
the shape of the field between pulses. Its meaning for a pulsed drive is practical: loops a hundred metres and more across need far
fewer ampere-turns, and the field geometry does not wander between bursts. Canon's own start sequence already tells the moment: first
fusion, then "the lattice enters activation range", then "field lock develops". A proposed history: field lock is what the crews listen
for. What Fiji does not do is make the nozzle efficient. That came from closure coils that shut the field behind each expanding burn,
and from stored fields fifteen times the pulse energy. The history should say the nozzle reached its ideal model only if the owner
declares it (D-T06-2), because published thrust efficiencies reach 0.30-0.64 against the 0.79 the ship needs.

*Physical manifestation:* three loops in twelve sectors plus closure coils, Fiji carriers on the burn-shadowed outer band. T03 found
that clocking the sectors loop to loop gives no useful shear, so no visible helix is narrated.

## H-5 "Convergence" (era E5)

**Narrates:** VTX-01B, T06-NEW-1, T06-NEW-2, VTX-07B, VTX-06B. Credibility **B**.

No single invention made the Vertex ship possible. A proposed history: in each generation the shipwrights took one more improvement
from another industry (lighter drivers, nanotube laminates, liquid radiators, thinner refractory pipes), and each one saved only a few
per cent. Then the sum crossed a line: at the same compression coupling, the old engineering could not close a ship at all and the new
engineering closed one. The model is honest about the limit: payload, propellant and tanks set a floor of about 5.7 kt at the mission
exhaust velocity, and no drive improvement moves it.

*Physical manifestation:* in V3 the outer nozzle loop sits at r 168 m (FDP-1 112 m); in V4 the loops match FDP-1's.

## H-6 "The unfinished problem" (all eras)

**Narrates:** VTX-08, 08A, 08B, 08D. Credibility **B / UNRESOLVED**.

Every history above ends with the same open question: a ship braking at 0.016 c flies engine-first into interstellar dust at 4,800 km/s,
and no shield physics has been tested within a factor of hundreds of that speed. T02 found that clearing the path with the plume and
deflecting grains with fields both fail, and that an engine skirt and lithium-hydride loop shoes still leave hundreds of damaging
events per voyage (central 540, range 3.4-17,300), with the loops' neutron dose far above what their superconductor tolerates. The
history should either declare a shield breakthrough (D-06) or tell this as the risk every crew accepts.
