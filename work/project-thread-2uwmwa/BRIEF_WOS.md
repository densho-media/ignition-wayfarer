# Owner brief, 2026-11-21 07:43Z (ApeDevil): G.U. WAYFARER 001 — Wayfarer Operating System (WOS)

The owner's message from the project thread, with its bullet lists run into sentences and the wording kept, so later sessions read the same requirements.

## 1. Objective

Revise, extend and implement the proposed Crew Interfaces concept into a unified **Wayfarer Operating System (WOS)** for the entire Wayfarer web experience.

The objective is to transform the GitHub Pages website from a conventional website about the Wayfarer into an immersive interface through which the visitor accesses the Wayfarer's onboard information, engineering records, simulations, visualizations and interactive experiences.

The visitor should feel as though they are operating a digital interface belonging to the ship itself.

The fundamental principle is:

**One ship. One operating system. Multiple devices.**

WOS is the conceptual and architectural identity of the interface ecosystem, not a literal operating system kernel or a replacement for the existing technological stack.

## 2. Initial contemplation

Before implementing anything, thoroughly contemplate the existing proposal and its relationship to the current project architecture.

Review: the existing Crew Interfaces concept; the current website architecture and navigation; the existing web identity, design tokens and design guidelines; all existing simulations and interactive visualizations; engineering documentation and ship records; the three.js and Godot integrations; interior and exterior exploration experiences; existing performance requirements and validation mechanisms; the established ship architecture and available canonical information.

Determine which existing components can be reused, extended, consolidated or reorganized.

Do not introduce a new framework, dependency or architectural layer without a demonstrated benefit.

## 3. Fundamental design principles

### 3.1 Diegetic interface design

WOS should represent the technological interface ecosystem of the Wayfarer. The website should not merely contain elements styled to resemble spaceship hardware. The website itself should become the interface.

The design should communicate: engineering credibility; functional realism; operational clarity; technological consistency; scientific accuracy; immersion; information accessibility.

Take conceptual inspiration from real spacecraft interfaces, aerospace engineering software, industrial control systems, scientific visualization software and diegetic science-fiction interfaces. Do not imitate a specific existing fictional operating system. Develop a recognizable visual identity unique to the Wayfarer.

### 3.2 Functional parity across devices

This is a non-negotiable requirement.

**Desktop, tablet and mobile must provide access to the same content, information, simulations and functionality.**

Screen size and input capabilities determine how functionality is presented, not whether it is available. Do not create artificially restricted mobile versions of the Wayfarer. For example:

- A propulsion simulation available on desktop must also be accessible on mobile and tablet.
- Engineering records must contain the same information across all devices.
- Ship status must originate from the same underlying data.
- Simulation parameters and results must remain accessible regardless of device.
- Interactive models should support appropriate touch, pointer and keyboard interactions.

On desktop, multiple information panels can be displayed simultaneously. On mobile, the same panels may be organized through tabs, drawers, expandable sections, sequential views or other appropriate interaction patterns. Tablet layouts should adapt between these configurations according to orientation, available screen space and input capabilities.

Where hardware capabilities impose genuine performance limitations, optimize rendering quality or interaction methods rather than arbitrarily removing functionality.

Do not maintain separate implementations of the same simulation or business logic for different device classes.

### 3.3 Adaptive presentation rather than separate websites

Establish one coherent interface system with adaptive presentation. The interface should adapt to: available viewport dimensions; screen orientation; input capabilities; touch and pointer interaction; active functional module; current user activity; performance capabilities; user-configured workspace preferences, where appropriate.

Avoid rigid assumptions based exclusively on whether a visitor is using a phone, tablet or desktop computer. A large tablet with a keyboard may behave similarly to a workstation, while a narrow desktop window may require a compact layout.

## 4. Device ecosystem

Establish a shared family of fictional Wayfarer devices.

Personal interfaces:

| Device | Purpose |
|---|---|
| Personal Terminal | General access to the Wayfarer Operating System |
| Crew Cuff | Personal status, communication, local navigation and contextual crew information |
| Service Slate | Engineering inspections, maintenance and technical activities |
| EVA Display | Suit telemetry and exterior operations |

Stationary interfaces:

| Device | Purpose |
|---|---|
| OPS Console | General ship operations and monitoring |
| Engineering Workstation | Technical analysis, records and subsystem inspection |
| Simulation Workstation | Scientific and engineering simulations |
| Navigation Console | Flight planning, trajectories and navigational information |
| Burn Console | Acceleration and critical flight operations |

These device families should represent different configurations and contextual manifestations of the same operating system. They must not become independently developed interface systems. Do not implement every specialized device prematurely. Establish the architectural foundations and implement specialized profiles when justified by existing or planned functionality. Device profiles and hardware characteristics that are not yet supported by canon must remain marked as PROTOTYPE.

Default web presentation: Desktop: stationary workstation presentation. Tablet: adaptive workstation or personal terminal presentation. Mobile: Personal Terminal presentation.

The mobile website should not default to an artificially constrained Crew Cuff. The Crew Cuff is a specialized in-world device, primarily relevant to the interior exploration experience. The general-purpose Personal Terminal should provide unrestricted access to the WOS functional ecosystem.

## 5. Full-viewport desktop workspaces

A major objective of this initiative is to maximize the utilization of available screen real estate.

**The browser viewport itself should become the workstation.**

Do not place a decorative workstation inside a conventional webpage. Avoid: unnecessary outer margins; artificial hardware bezels; excessively large headers; conventional marketing hero sections; empty decorative areas; restrictive maximum-width content containers in engineering workspaces; repetitive navigation elements; unnecessary page-level scrolling.

Instead, establish application-like workspaces consisting of: a compact persistent ship status area; functional navigation; a primary workspace; contextual information panels; contextual controls; relevant alerts and notifications.

The primary workspace must occupy as much available screen area as possible. For example: during ship exploration, the 3D model should dominate the workspace; during propulsion simulation, the simulation and its results; during engineering analysis, relevant diagrams, parameters and records; during interactive exploration, the environment.

Where appropriate, support: collapsible panels; resizable panels; expandable visualizations; focus modes; fullscreen modes; contextual drawers; configurable workspace layouts; locally persisted workspace preferences.

Do not force every module into an identical three-pane layout. The active functionality should determine the optimal workspace composition.

Long-form engineering records may retain appropriate reading widths and scrolling behavior. Full-viewport optimization should improve usability rather than compromise readability.

## 6. Mobile and tablet optimization

Create a genuinely optimized handheld experience rather than a compressed desktop interface. The mobile presentation should feel like a personal technological device belonging to the Wayfarer.

Preserve the same functionality while adapting: information density; navigation patterns; panel arrangements; typography; touch targets; chart interactions; simulation controls; 3D navigation; data tables; contextual menus.

Use progressive disclosure where appropriate. For example, a desktop propulsion workspace may simultaneously display the propulsion model, simulation parameters, acceleration curves, thermal loads, propellant consumption and simulation results. On mobile, the same information and controls may be organized into selectable views or tabs. All information and functionality must remain accessible.

Tablet layouts should take advantage of additional screen space without introducing a separate application architecture. Support portrait and landscape orientations wherever technically reasonable.

## 7. Unified interface architecture

Contemplate and establish an architecture separating the following responsibilities.

- **Layer A — Shared ship data and simulation state.** Authoritative ship specifications; engineering data; subsystem information; simulation parameters; simulation results; scenario state; operational telemetry; documentation and source references. Clearly defined authoritative sources for shared information. Avoid duplicating ship specifications or computational logic across interface modules.
- **Layer B — Functional modules.** Organize existing and future functionality into coherent modules. Potential modules: Ship Overview, Ship Systems, Propulsion, Thermal Management, Power, Habitat, Life Support, Navigation, Simulations, Engineering Records, Ship Exploration, Alerts. Conceptual modules, not a mandatory navigation hierarchy. Derive the final structure from the existing functionality and project architecture. Each module should expose its functionality independently of a particular device presentation.
- **Layer C — Device and workspace profiles.** How functional modules are presented under different circumstances: information density; default workspace composition; interaction patterns; contextual controls; persistent status information; available screen arrangements; in-world visual characteristics. Profiles must not duplicate the underlying functionality. For the public website, device profiles must preserve functional parity. Specialized in-world devices may have narratively appropriate limitations, but these must not arbitrarily restrict access through the general website.
- **Layer D — Presentation and interaction.** Responsive and adaptive layouts; touch interactions; keyboard and pointer interactions; visual components; navigation; panels and drawers; fullscreen presentation; accessibility; integration with rendering engines.

Evaluate the existing architecture before deciding how explicitly these layers need to be represented in the codebase. Avoid unnecessary abstraction and overengineering.

## 8. Operational state and telemetry

The Wayfarer should have a coherent representation of its operational state across WOS. Contemplate a shared ship status model that can represent: mission elapsed time; flight phase; propulsion state; electrical power; thermal conditions; habitat rotation; artificial gravity; atmospheric conditions; life support; system alerts; active simulation scenarios.

Clearly distinguish between: 1. canonical engineering specifications; 2. nominal ship operating conditions; 3. active simulation state; 4. interactive scenario state; 5. illustrative or prototype information.

Running a simulation must not accidentally modify authoritative ship information or unrelated operational states. For example, a reactor failure within a Deadship scenario must not cause the general website to report a failed reactor outside that scenario. Never present fabricated telemetry as authoritative or canonical. Example values must be identifiable as such.

## 9. Visual identity and functional realism

Preserve and evolve the existing Wayfarer visual identity. Review and extend the existing WEB-005 design system and associated token generation mechanisms.

Establish shared standards for: typography; colours; information hierarchy; iconography; status indicators; warning levels; numerical displays; engineering units; charts and diagrams; interactive controls; navigation; panels; component states; device-specific presentation.

The aesthetic should emerge from functionality. Avoid: decorative circuitry; unnecessary glowing elements; excessive neon; artificial scan lines; non-functional futuristic controls; decorative hardware casings that waste screen space; visual noise that interferes with information readability.

Use colour primarily to communicate meaningful information, system states and operational hierarchy. Physical controls and hardware characteristics may be represented when contextually appropriate, particularly inside Godot experiences. Website controls should remain optimized for the actual device being used.

## 10. Integration with interactive experiences

The website and the interactive Wayfarer experiences should gradually converge toward the same technological ecosystem. The activity-based interface selection proposed in the original concept is approved in principle. For example: walking aboard the ship may expose Crew Cuff functionality; interacting with an OPS station may expose the corresponding stationary interface; performing maintenance may expose Service Slate functionality; exterior exploration may expose the EVA suit display; participating in a burn scenario may expose the Burn Console.

This contextual behavior should apply independently of the physical device used by the visitor. However, distinguish between the fictional device within the experience and the actual presentation required by the user's physical screen. An OPS console accessed during a mobile exploration experience must still be adapted for mobile interaction.

Preserve consistency between the website and Godot implementations wherever practical through shared design specifications, terminology, tokens and functional concepts. Do not force incompatible rendering environments to share implementation details unnecessarily.

## 11. Performance and accessibility

WOS must improve the interface without compromising the existing performance objectives. Preserve and extend the established web graphics optimization strategies. Prioritize: lightweight interface components; efficient rendering; lazy loading of expensive modules; appropriate resource disposal; adaptive rendering quality; minimal unnecessary JavaScript; avoidance of duplicated computational work; responsive interaction; efficient data loading; preservation of existing three.js and Godot performance budgets.

Do not load every simulation or 3D environment when the operating system initializes. Load functionality when required.

Preserve existing accessibility standards and validation mechanisms, including: text contrast requirements; keyboard navigation; visible focus indicators; accessible labels; appropriate touch targets; reduced-motion preferences; existing axe-core checks. Do not sacrifice accessibility for fictional realism.

## 12. Permanent project instructions

This initiative must become a permanent part of the Wayfarer development principles. Update the appropriate project documentation, architectural records, web identity documentation and Claude instructions.

Future functionality must follow these principles by default: integration into WOS; shared functional architecture; functional parity across devices; adaptive presentation; full-viewport optimization where appropriate; functional realism; consistent ship data; performance awareness; accessibility; canonical accuracy.

When a new simulation, visualization, subsystem or interactive experience is introduced, evaluate how it integrates into the operating system rather than treating it as an isolated webpage. Avoid introducing redundant documentation or conflicting instructions. Update existing authoritative documents wherever appropriate.

## 13. Implementation roadmap

- **Phase 0 — Architectural contemplation and planning.** Review the existing project and the original Crew Interfaces proposal. Produce: an architectural assessment; a revised WOS concept; a device and workspace taxonomy; a functional module inventory; an adaptive layout strategy; a shared state strategy; a technical implementation plan; a migration strategy for existing functionality; performance and accessibility acceptance criteria. Document architectural decisions and their reasoning.
- **Phase 1 — WOS foundation and workspace prototype.** Establish: unified design tokens and components; shared navigation; compact ship status presentation; full-viewport desktop workspaces; adaptive tablet presentation; optimized mobile Personal Terminal presentation; contextual information and control panels. Use representative existing functionality to demonstrate that the architecture works. The prototype should already demonstrate equivalent functionality across desktop, tablet and mobile. Do not build an isolated visual mockup disconnected from the actual application architecture.
- **Phase 2 — Existing functionality integration.** Progressively integrate: existing ship models; existing simulations; technical status information; engineering records; interior and exterior exploration launchers; existing scientific visualizations. Preserve functionality, source references and computational accuracy. Do not introduce regressions during migration.
- **Phase 3 — Advanced workspace optimization.** Where justified: resizable panels; collapsible panels; focus modes; fullscreen visualizations; contextual drawers; workspace preferences; adaptive information density; improved touch and keyboard interactions.
- **Phase 4 — In-world integration.** Extend the operating system identity into Godot experiences: Crew Cuff; OPS interfaces; Service Slate; EVA displays; other specialized interfaces when required. Ensure visual and conceptual consistency between the public website and the fictional ship hardware.
- **Phase 5 — Canon integration.** Identify technology and hardware concepts that should become part of the Ignition canon. Prepare proposed additions and modifications for review. Do not modify the authoritative Ignition workbooks or establish new canonical facts without explicit authorization.

## 14. Validation and acceptance criteria

The implementation must demonstrate that: the website feels like the Wayfarer's operating interface rather than a conventional website; desktop workspaces efficiently utilize available viewport space; desktop, tablet and mobile provide equivalent access to information and functionality; layouts adapt appropriately to different screen dimensions and orientations; existing simulations remain functional; existing ship models remain functional; existing engineering information remains accurate and accessible; interface modules reuse shared data and computational logic; no unnecessary duplication of functionality is introduced; performance remains within established budgets; accessibility checks pass; prototype information is not misrepresented as canon; the architecture supports future extensions without requiring device-specific reimplementation.

Test representative desktop, ultrawide, laptop, tablet and mobile viewport configurations. Test both portrait and landscape orientations where appropriate. Verify functionality rather than merely checking that layouts fit within the viewport.

## 15. Execution instructions

Begin with architectural contemplation using Fable. Critically evaluate the existing Crew Interfaces proposal and the requirements in this specification. Identify potential improvements, architectural risks, unnecessary complexity and opportunities to reuse existing implementations. Use Fable for conceptual and architectural reasoning, then use Opus for implementation.

After contemplation:

1. Establish the revised architectural direction.
2. Document the permanent WOS development principles.
3. Produce a structured implementation plan.
4. Create a dedicated development branch.
5. Begin implementation of the WOS foundation and adaptive workspace prototype.
6. Run the relevant validation, performance and accessibility checks.
7. Provide visual comparisons of desktop, tablet and mobile presentations.
8. Prepare a reviewable preview using the established deployment workflow.

You are authorized to proceed with the architectural work and the initial implementation. Do not squash, merge or deploy to production without explicit authorization. Do not modify authoritative lore or engineering canon without explicit authorization. Report architectural decisions, implementation progress, validation results, outstanding issues and recommendations.

## 16. Long-term vision

The Wayfarer Operating System should become the unified access layer to the digital representation of the Wayfarer. Engineering documentation, scientific simulations, operational information, interactive exploration and future functionality should feel like interconnected applications within the same onboard technological ecosystem. The objective is not merely to make the website look futuristic. The objective is to create the experience of accessing, studying, exploring and operating the Wayfarer through its own technological interface.

**One ship. One operating system. Multiple devices.**
