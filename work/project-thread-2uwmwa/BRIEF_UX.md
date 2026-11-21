# Owner brief 2026-11-21 09:30Z — WOS: Navigation, Visual Hierarchy & First-Time User Experience (condensed, wording kept where it decides)

Guiding principle: **Show first. Explain progressively. Let users explore.** WOS is "too text-heavy and insufficiently guided".

1. **Two audiences at once**: first-time visitors (never heard of Wayfarer/Ignition: what is it, what can I experience, why interesting)
   and returning/technical users (immediate access to simulations, engineering data, systems). No separate sites, no restriction by
   experience level: progressive discovery in one interface.
2. **Information architecture.** Review Overview/Ship/Simulations/Records/Aboard/System as a first-time visitor (Ship vs Aboard? System =
   ship systems, technical status or settings? Records vs Engineering? where to learn how it works? where to interact immediately?).
   Organize primary navigation around user intentions (discover, explore the spacecraft, run simulations, understand the engineering,
   check status). Proposal to evaluate (not mandatory): Overview → Explore → Simulations → Engineering → Status; Explore holds 3D Ship,
   Interior, Exterior; Engineering holds records, subsystem info, design docs. Preserve capabilities and routes. Distinguish primary,
   secondary (sections in a module), contextual (actions on the current object) and utility navigation (system info, settings, tools).
   Don't overcrowd the bar. Consistent terms and meaningful icons.
3. **Overview as an engaging entry point**, not a status report, still an onboard OS. A: compact ship identity + recognizable visual
   (no oversized marketing hero); B: featured experiences with real thumbnails (Explore the Ship, Walk Inside, Explore Exterior, Run
   Simulations, Discover the Engineering), each with visual, title, brief explanation, action, availability indicator; C: accessible
   summary of the most interesting facts first, tables/parameters/source classes in dedicated or expandable views; D: project context
   (fictional spacecraft developed through engineering worldbuilding and simulations; evolving project, not a real operating ship).
4. **Imagery and thumbnails**: authentic project imagery only (renders, rings, interior, EVA, Vertex drive, Dust, trajectory,
   schematic); generate from existing models/screenshots/diagrams where missing; illustrative previews distinct from canonical
   representations. Thumbnail conventions: consistent aspect ratios, placement, titles/actions, readable overlays, responsive sizes,
   lightweight, lazy loading. No decorative images. Thumbnails never load a simulation.
5. **Icon system**: one coherent family (stroke, size), one meaning per icon across WOS (spacecraft, interior, EVA, propulsion, power,
   thermal, habitat, navigation, engineering, simulations, records, alerts, settings). Evaluate existing icons/tokens before a library.
   Icons supplement labels; no tiny ambiguous icon-only nav without an accessible way to identify it.
6. **Visual hierarchy**: distinguish 1 location/purpose, 2 main action, 3 supporting actions, 4 context, 5 detailed data, 6 metadata/
   diagnostics, via typography, spacing, grouping, imagery, restrained colour. Not by shrinking text. Cut prose: e.g. "Explore Interior —
   Walk through the rotating habitats and discover the ship from inside. — Enter Ship".
7. **Progressive disclosure**: Level 1 discovery (short explanation + visual), 2 exploration (diagram, simulation, model), 3 engineering
   (parameters, constraints, open problems, sources). Conceptual levels, not modes; direct access to technical info always.
8. **Contextual guidance**: intro on entering a simulation, what a parameter changes, labelled presets, short 3D manipulation
   instructions, what an experiment demonstrates, help for unavailable experiences, links from results to engineering explanations.
   Optional first-visit orientation; no intrusive wizards, mandatory tutorials or popups.
9. **Wayfinding**: where am I, what am I looking at, what can I do, related info, how to return. Breadcrumbs, module titles, section
   nav, related links; no unnecessary depth.
10. **Device parity**: same functionality, different presentation; thumbnails and icons on every device class.
11. **Performance and realism**: budgets, accessibility, canon accuracy; no hero videos, animations, decorative 3D; optimized static previews.
12. **Validation**: scenarios A new visitor, B curious explorer (3D ship, interior, exterior), C simulation user (find, understand,
    modify, interpret), D technical visitor (specs, systems, docs, data), E mobile visitor. Usability-focused review, not only automated.
13. **Execution**: review current WOS + screenshots; contemplate with Fable; implement with Opus on the existing branch. Priorities:
    1 primary/secondary nav, 2 Overview first-time experience, 3 thumbnails and icons, 4 less text and better hierarchy, 5 guidance and
    progressive disclosure, 6 responsive validation. Reuse assets; no unnecessary complexity. Update docs/WOS.md and permanent
    instructions. Provide desktop, tablet, mobile and ultrawide screenshots and explain decisions. Preserve all functionality.
    **Do not squash, merge, deploy to production or modify canon without authorization.**
