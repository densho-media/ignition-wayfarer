# Purpose–Material Design System (PMDS)

Materials are chosen for what a part must do, not for what they are called or how they look. A component first names its engineering
purposes; the purposes name the properties and environment that matter; only then are real materials evaluated against them. One catalogue
with stable IDs serves the physics (property lookups), Blender (metadata and two material views) and future development (Level B and C
variants). It is an engineering reference and a candidate-selection system. The Drive workbooks stay the authority: no material record
is canon, no selection here is final, and the chain Drive → parameters → shared formulas → Blender → Godot is unchanged.

## Files and IDs

| File | Records | ID |
| --- | --- | --- |
| `data/materials/purposes.toml` | the 14 engineering purposes: function, required properties, environment, failure mechanisms, candidates, selection criteria, validation, systems, the engineering-view colour | `P01`…`P14` |
| `data/materials/catalogue.toml` | real materials (Level A) and their variants (Level B, C); the references they cite | `MAT-*`, `reference.<id>` |
| `data/materials/applications.toml` | purposes and candidate layers tied to existing components, their operating requirements, and the display materials that carry each layer | `APP-*` |
| `data/materials/appearances.toml` | how a material looks in Blender (Principled finish, or an existing exterior family `xf_*`) | `APP-<material>-<finish>` appearance IDs |

`src/wayfarer/materials.py` loads, validates and looks them up; `src/wayfarer/material_physics.py` evaluates properties for calculations.
Both are pure standard-library modules (system Python and Blender). Material, purpose and application IDs are stable: a material change
edits an application's layer, never the application or the component it is bound to.

### Purposes

| ID | Purpose | Reference materials |
| --- | --- | --- |
| P01 | Storage | Al-Li 2195, Al 2219, 316L, CFRP |
| P02 | Fluid transport | 316L, Inconel 718, CuCrZr |
| P03 | Flow control and injection | 316L, Inconel 718, alumina |
| P04 | Containment and sealing | 316L, alumina, Inconel 718 |
| P05 | Magnetic-field generation | REBCO, REBCO with artificial pinning, Cu stabilizer |
| P06 | Electromagnetic-force support | 316LN, Inconel 718, Ti-6Al-4V |
| P07 | Plasma and thermal protection | W, Wf/W, HfC, SiC, C/C |
| P08 | Heat conduction | Cu, CuCrZr, SiC, C/C |
| P09 | Electrical conduction and conversion | Cu, SiC electronics |
| P10 | Electrical and thermal insulation | MLI, alumina, YSZ, CFRP |
| P11 | Radiation attenuation | W, LiH, B4C, HDPE |
| P12 | Waste-heat transport | Nb-1Zr, Mo-47.5Re, Inconel 718, CuCrZr |
| P13 | Thermal radiation | C/C, SiC, AZ-93, nanophotonic emitter |
| P14 | Structural integrity | Ti-6Al-4V, 316LN, Inconel 718, SiC/SiC, C/C, CFRP |

Candidates are where an evaluation starts. They are not ranked equal: a material that survives a short plasma exposure may fail over
years, and the purpose's failure mechanisms say which life limit to check.

### Material records

Identity (name, composition, family, form), physical properties, behaviour (creep, fatigue, radiation response, chemical compatibility,
magnetic), engineering considerations (manufacturing, joining, availability and cost, repairability, durability, failure mechanisms,
limitations) and evidence references.

Rules, enforced by `materials.validate` (the loader refuses a catalogue that breaks them):
- Every core property (density, specific heat, thermal conductivity and expansion, yield strength, elastic modulus, fracture
  toughness, electrical resistivity, melting point, maximum service temperature, emissivity) is given or listed in the material's
  `open` list. Missing data stays explicitly unresolved, never zero, a convenient constant or an invented improvement.
- A property is a point (`value` at `at_K`, optionally over `valid_K`), a range across grades and sources (`min`/`max`) or a temperature
  table (`table_K`/`values`). Each has a unit, a basis (MEASURED, HANDBOOK, TYPICAL, SPECIFICATION_MINIMUM, ESTIMATE, THEORETICAL,
  FICTIONAL), a confidence and a source.
- Every number carries a verification state (see "Verification" below). A reference states the default for the numbers citing it
  (TRANSCRIBED, or UNVERIFIED for a source without a named table); only a property can be PRIMARY_VERIFIED or SECONDARY_VERIFIED, and
  then it records `verified` (what was compared, when), `verified_against` (the reference it was checked against) and `condition`
  (grade, form, temper, irradiation and test condition). A secondary check uses a reference other than the number's own source.
  PRIMARY_VERIFIED also needs `verified_against` of a primary kind (handbook, critical review, journal, book, standard, procurement
  specification, agency database or the producer's datasheet; not a secondary listing, a quoting review or the project mirror), a
  `locator` (the table, figure, page or dataset holding the number) and the temperature range it applies to (`valid_K` or a table);
  units and value shape are validated for every number. How many numbers are verified is a state of the catalogue, never a test target.
- The melting, decomposition or sublimation point is never an operating rating. `max_service_temperature` is a separate long-life limit,
  validated to lie below it, and OPEN where no credible long-life limit is recorded. Every service limit states its `rating`:
  SCREENING_ESTIMATE (a literature threshold for screening) or LIFETIME_RATED (a qualified long-life rating with its `life` and verified
  evidence). None is LIFETIME_RATED yet. `min_service_temperature` records a floor (CuCrZr's irradiation embrittlement); `applies =
  "IRRADIATED"` limits it to a stated neutron dose.
- A number belongs to one state of the material: `irradiation` UNIRRADIATED (the default) or IRRADIATED. Unirradiated data never stands
  for a part under a stated fluence. A fibre composite is `anisotropic`, and its directional properties must name a `direction` before
  they can be given (CFRP, SiC/SiC and C/C keep them OPEN until then). A coating's emissivity and absorptance are surface states that age.
- Physical emissivity lives here. Blender's emission shader is a display setting and never reads it.

### Verification

| State | Meaning | Count (property entries, snapshot 2026-11-05) |
| --- | --- | --- |
| PRIMARY_VERIFIED | read in the primary source, authoritative handbook table or original publication | 0 |
| SECONDARY_VERIFIED | matched against a secondary reproduction, datasheet or technical summary | 25 |
| TRANSCRIBED | a source is named; the number was not independently checked against it | 45 |
| UNVERIFIED | the source, or its support for this number, is not established | 31 |

`materials.evidence_counts(db)` gives the current numbers. No primary source could be opened from the cloud session that did the PMDS 1.1
review (srd.nist.gov, specialmetals.com, arxiv.org, aries.pppl.gov and the publisher sites are outside its network policy), so nothing is
PRIMARY_VERIFIED. The secondary checks of 2026-11-05 cover tungsten (density, modulus, resistivity, expansion, melting point), CuCrZr
(the ITER-grade minimum tensile properties), 316L (A240 minima), alloy 718 (density, conductivity, melting range, resistivity),
Ti-6Al-4V Grade 5 (density, modulus, yield, conductivity), Al-Li 2195 (density, modulus), AZ-93 (emissivity), LiH (density, melting
point), B4C (density, melting point) and HfC (melting point). REBCO's Tc band was read in search results for its own source study, so
it stays TRANSCRIBED (an IEEE YBCO overview, about 92 K, agrees); the CuCrZr minima were matched against a search-result reproduction
of the ITER specification (`sec_iter_cucrzr_repro`), not the document itself. They corrected four entries: B4C density 2500-2520 (was 2520),
alloy 718 resistivity 1.21-1.27 micro-ohm m (was 1.25), REBCO Tc 89.9-93.0 K with a Tc source (was cited to a coil test), and the CuCrZr
service window (below). Tungsten's and copper's conductivity tables matched secondary data at two points each and stay TRANSCRIBED.
Nothing below SECONDARY_VERIFIED is fit for canon.

Scientific consistency rules the review applied: a melting point is never a service rating; room-temperature strength does not answer
an elevated-temperature screen (a point value holds only at its `at_K` or inside its `valid_K`); conductivity is never extrapolated; data
are not transferred across grades (Ti-6Al-4V Grade 5 is not ELI, CuCrZr strength belongs to its heat treatment); cryogenic and ambient
values stay separate; unirradiated data never stand for neutron exposure; composite properties are directional; a coating ages.
The CuCrZr record had its irradiated *lower* window (about 423 K) recorded as the low end of its *upper* service limit, which made every
screen above 423 K fail; it is now a 573-623 K upper screening limit plus an irradiation-only floor of 373-423 K.

### Development levels

- **A, existing technology**: real materials with documented properties (27 in the first catalogue).
- **B, plausible development**: a variant with a Level A parent, an improvement, its scientific mechanism, modified properties,
  evidence, required validation, manufacturing implications, trade-offs and applicability: `MAT-W-ADV01` (tungsten-fibre-reinforced
  tungsten), `MAT-REBCO-APC01` (REBCO with artificial pinning centres, the WORKING conductor of 05!A37:A38), `MAT-RAD-NPE01`
  (nanophotonic refractory emitter, the WORKING hot-radiator skin of 40_THERMAL B59).
- **C, speculative**: fictional, with its speculative claims and a conservation check stated separately: `MAT-W-FIJI01`
  (Fiji-stabilized tungsten; slower microstructural damage only, no change to the energy balance).

A variant inherits no number from its parent unless it lists the key in `inherits`. A Level C value never feeds a calculation unless the
caller explicitly allows speculation, and a Level C material is at most a CANDIDATE alternative in an application. A variant states the
engineering problem it answers: if tungsten were rejected for thermal fatigue, `MAT-W-ADV01` names the property that must improve
(cyclic-crack resistance) and says its required magnitude follows from the OD-025 heat flux, cycle count and replacement interval,
which are OPEN. No variant claims to be lighter, stronger, cheaper, hotter and more radiation-resistant at once.

A variant starts from a measured deficiency, not from a wish for a better material:
1. Screen the Level A candidate (`screen_application`) at the stated conditions. Name the requirement it fails or cannot show (for
   example: the tungsten hot face cannot show a thermal-fatigue life for the OD-025 cycle count).
2. Quantify the gap: the required value, the material's value, the margin. Where the requirement is OPEN, the variant waits for it.
3. Search the literature for mechanisms that move that property (fibre toughening, pinning centres, photonic emitters) and record
   the mechanism, its evidence, the trade-offs and the validation it needs. Every other number stays OPEN (`inherits` lists only the
   properties the mechanism leaves unchanged, with a reason).
4. Only if no plausible mechanism exists may a Level C variant be written, with its speculative claims, a conservation check and no
   numbers unless the owner sets them; it feeds calculations only with `allow_speculative=True`, and the result says so.

### Applications

An application lists its purposes, its layers from the outer face inward (role, purposes, material, alternatives, appearance, `selection`
CANDIDATE/PREFERRED/REJECTED, `geometry` DRAWN/NOT_DRAWN/PROTOTYPE_STUDY), its operating requirements (an unknown one is `OPEN <ref>`),
its canon and open-item refs and its bindings: the generated display material (`WF_MAT_<name>` in an asset) that carries each layer.
No application is SELECTED; a selection becomes canon only in the Drive workbooks.

The first set covers the propulsion chain:

| Chain | Applications |
| --- | --- |
| Fusion fuel: storage, transport, injection, confinement | `APP-STO-FUEL-VESSEL` (D, 3He), `APP-FEED-CRYO`, `APP-DRV-PFC` |
| Reaction mass: storage, transport, injection, exhaust | `APP-STO-H2-VESSEL`, `APP-FEED-CRYO`, `APP-DRV-H2-INJECT`, `APP-NOZ-STRIKE` |
| Electrical and magnetic | `APP-NOZ-COIL`, `APP-NOZ-SERVICES` (leads), `APP-NOZ-CASE`, `APP-NOZ-PICKUP` |
| Radiation and thermal | `APP-SHLD-SHADOW`, `APP-NOZ-SERVICES` (coolant), `APP-THM-HOT-LOOP` (recorded, not bound), `APP-RAD-HOT`, `APP-RAD-WARMLOW`, `APP-THM-BULKHEAD`, `APP-STO-SUPPORT` |

The distinctions the records keep: D–3He fuel and hydrogen reaction mass are separate inventories with separate vessels; cryogenic feed
lines are plumbing, not plasma transport; magnetic flux and the field envelope are not pipes and get no material; charged particles hit
the armour, neutrons and photons the shield, and the shield turns what it stops into heat that must be carried away; conduction (P08,
P12) and radiative rejection (P13) are different purposes with different materials.

## Physics

```python
import material_physics as mp
q = mp.get_property('MAT-W', 'thermal_conductivity', temperature_K=1000)   # 118 W/(m K), HANDBOOK, HIGH, hpl1972, TRANSCRIBED
mp.require(q)                       # the number, or UnknownProperty if OPEN / out of range / speculative / a range
mp.require(mp.get_property('MAT-CFRP', 'density', 293), 'low')   # a range: ask for the conservative end explicitly
```

A quantity keeps its unit, basis, confidence, source, verification, validity range and status (OK, OPEN, OUT_OF_RANGE,
NEEDS_TEMPERATURE, SPECULATIVE_BLOCKED, NOT_INHERITED). Tables interpolate linearly inside their range only; nothing extrapolates.
`conductivity_integral()` and `conduction_drop()` solve steady 1-D conduction with temperature-dependent conductivity.
### Screening

`screen_application(app, conditions, allow_speculative=False)` checks each layer against its purposes' required properties at the
operating conditions `{role or '*': {'temperature_K', 'neutron_fluence_dpa', 'life_h'}}`:

| Verdict | When |
| --- | --- |
| EXCEEDS_LIMIT | a known limit is violated at the stated conditions: the phase change, the conservative (low) end of the upper service limit, the conservative (high) end of an applicable floor, or a superconductor's Tc. Shown even when other data are missing. |
| NOT_EVALUABLE | anything needed is missing: the temperature; the neutron dose where a purpose needs radiation response or the application has a fluence requirement; the life where the application has a life requirement; a required property (OPEN, not inherited); a value valid at the operating temperature; evidence better than UNVERIFIED; irradiated data under a stated dose; a LIFETIME_RATED limit when a life is required; an OPEN application requirement; or permission for Level C data. |
| WITHIN_CHECKED_LIMITS | every required numeric property is known at the operating temperature from evidence at least TRANSCRIBED and every applicable known limit passes. |

Each layer returns the structured reasons: `missing_conditions`, `missing_properties`, `out_of_range`, `unverified`, `unirradiated`,
`violations`, `checked_limits` (with rating, basis and verification), `evaluated_properties` (value, basis, verification, condition),
`unchecked_requirements` (the qualitative ones: radiation response, creep, fatigue, erosion), `weakest_evidence` and
`lifetime_evaluated`. The application verdict is its worst layer. A screen is never qualification and never approval
(`approved = False`, `qualification = 'NOT_QUALIFIED'`); it replaced PMDS 1.0's WITHIN_KNOWN_LIMITS, which a material could earn
with its required properties unknown.

The plasma armour today: with no conditions every layer is NOT_EVALUABLE (OD-025 requirements OPEN, no temperature, dose or life).
With the hot face at 1100 K and the CuCrZr conduit at 900 K the application is EXCEEDS_LIMIT (CuCrZr's 573 K screening limit) and the
W face still NOT_EVALUABLE (no expansion value at 1100 K, its 1300 K recrystallization threshold UNVERIFIED, no lifetime rating).

`python3 src/wayfarer/material_physics.py` prints the evidence counts, both armour screens, the ITER reference case (10 MW/m² through
6 mm of W above 600 K: about 1080 K at the surface; ITER's published load, not Wayfarer's, whose heat flux is OPEN) and the integration
table. No existing physics model was changed for this system, and none may be changed to make a material look viable.

### Physics integration

Canon keeps authority: a material-specific spec value is compared with the catalogue, a difference becomes an engineering review item,
and approved changes travel through the source process (Drive → spec → formulas). `material_physics.INTEGRATION` is the dependency table;
`spec_crosscheck(s)` evaluates it on every run (`test_materials` names the known differences, so a new one fails). No Wayfarer
calculation reads the catalogue directly yet. The table's `usage` keeps four kinds of interface apart:

- DIRECT_LOOKUP: the calculation takes the catalogue value through `get_property`/`reference_value` (today only the ITER reference
  conduction case in `material_physics`).
- CROSS_CHECK: a read-only comparison of a spec value with the catalogue (CONSISTENT, DIFFERS or NOT_CHECKABLE); the spec value is used.
- NOT_LINKED: a calculation that uses a material number but does not consume PMDS yet; the row names what must exist before it can.
- Requirements still awaiting validation are not in this table: they are `OPEN <ref>` entries in the applications (OD-024/025/026),
  and a screen reports them as NOT_EVALUABLE.

| Module | Spec value | PMDS reference | Usage | Next step |
| --- | --- | --- | --- | --- |
| fuel_loads | strut E, yield, density (Ti-6Al-4V) | MAT-TI6AL4V | cross-check: consistent | yield is a room-temperature typical value used as a design value: needs an allowable at the strut temperature |
| fuel_loads | shell density, yield, E (Al-Li 2195) | MAT-ALLI-2195 | cross-check: consistent | yield is the low end of a thickness/direction range; weld and cryogenic allowables OPEN |
| fuel_loads | skirt density (CFRP) | MAT-CFRP | cross-check: consistent | safe to link |
| fuel_loads | skirt E, strength, conductivity integral | MAT-CFRP | not linked (OPEN, layup-specific) | review item: the integral is called G-10-class (glass-epoxy) for a CFRP skirt |
| radiator_zones, heat_rejection | WARM/LOW emissivity 0.91 | MAT-AZ93 | cross-check: consistent | beginning of life; end of life is in absorptance |
| spec, thermal_budget, operating_point | hot-face emissivity 0.90 (WORKING, OD-023) | MAT-RAD-NPE01 | not linked (no measured value) | deferred |
| radiator_zones | bulkhead foil densities (TZM, Ti-6Al-4V, Ti) | MAT-TZM, MAT-TI6AL4V, MAT-TI-CP | cross-check: consistent | safe to link |
| radiator_zones | bulkhead layer 3 emissivity 0.05 | MAT-AU | cross-check: **differs** (polished gold 0.02-0.03) | review item: state the degradation or film margin the 0.05 holds |
| radiator_zones | bulkhead layer 1-2 emissivity, foil CTE at 805-1204 K | MAT-TZM, MAT-TI-CP, MAT-TI6AL4V | not linked / not checkable (no hot values) | add emissivity and mean-CTE tables first |
| radiator_zones | standoff k 2.0 W/(m K) | MAT-YSZ | cross-check: consistent (room temperature) | needs k(T) of the chosen standoff material |
| heat_rejection, forward_shield | warm-loop example emissivity, bumper seam CTE | none named | not linked | name the material |
| material_physics | ITER reference conduction case | MAT-W | direct lookup | reference case only |

`reference_value(material, property, T, bound)` is the read-only adapter a module uses when a value is linked (it raises on OPEN,
out-of-range or speculative data and returns the quantity with its provenance); `compare_to_reference(value, ...)` is the comparison the
table uses. Linking a value means the spec value is retired through the source process, never overwritten here.

Screening the bulkhead with the spec's own layer temperatures shows a second review item: layer 2 is Ti-6Al-4V foil at about 805 K
(870 K end of life), above Ti-6Al-4V's 673 K screening limit, so the screen reports EXCEEDS_LIMIT. The limit is a SCREENING_ESTIMATE
for strength-critical parts; the foil is lightly loaded, and an appropriate vacuum operating-temperature and lifetime assessment
(creep, microstructural and vacuum stability) is OPEN. The material is not replaced on the strength of the screen. The CuCrZr conduit
result (EXCEEDS_LIMIT at 900 K) is conditional on that stated temperature, which is a screening case, not a Wayfarer operating value. The application layer now names Ti-6Al-4V, as the spec's foil
table does (it named CP titanium before).

### What the catalogue claims

1. Supported by verified evidence: the SECONDARY_VERIFIED entries (none primary).
2. Awaiting verification: TRANSCRIBED and UNVERIFIED entries; they may be used in screens (UNVERIFIED blocks a favourable verdict) but
   never in canon.
3. Used in calculations: none directly; the ITER reference case only.
4. Cross-checked against the spec: the CROSS_CHECK rows above.
5. Candidate assignments: every application layer (`selection` CANDIDATE or PREFERRED).
6. Approved choices: none. Approval is a Drive decision.
7. Physically modelled versus metadata-only: a layer is DRAWN only where an existing mesh represents it; the plasma-armour stack's
   Cu, CuCrZr and steel layers are NOT_DRAWN on the ship and were drawn only in the PMDS review study (ITER-reference proportions, PROTOTYPE_STUDY), which is not part of the ship.
8. Fictional developments: Level C (`MAT-W-FIJI01`), blocked from calculations without `allow_speculative`.

## Blender

**Metadata (saved).** `common.bind_materials`, run by `common.save` after the functional colours, writes each bound display material's and
each object's PMDS IDs as custom properties: `material_id`, `material_purpose_ids`, `material_application_id`, `material_variant_id`,
`material_engineering_status`, `material_evidence_ref`, plus layer, appearance, selection, geometry, level, the whole stack
(`material_layer_stack`, with `[NOT_DRAWN]` on layers no mesh represents; the drive's own `material_stack` is untouched), the canon and
open refs and `material_verification` (the bound material's evidence counts, e.g. `SECONDARY_VERIFIED=5 TRANSCRIBED=3 UNVERIFIED=1`). An object with several material slots also carries `material_slots`, a JSON map of slot index to binding, so a mesh is
never declared one material. Component IDs, geometry status, source refs, functional colours and the materials' shading are untouched;
the geometry fingerprint is unchanged. The build refuses a binding whose display material the asset does not make, or an application
bound in an asset but on no object.

**Two views (in memory, never saved into a production asset).** `common.material_views(s)` adds two view layers that share every mesh:

| View layer | Shows |
| --- | --- |
| `PHYSICAL_APPEARANCE` | bound materials in their PBR appearance (appearances.toml; family appearances reuse the exterior grammar's `xf_*` finish), with a restrained, process-derived surface cue (`common.SURFACE_CUES`: anisotropic specular for machined lay, a weak bump for helium fuzz, cloth weave, MLI crinkle and foil waviness) |
| `ENGINEERING_MATERIAL` | bound materials in their layer's first purpose colour (purposes.toml `view_color`); unbound solids neutral grey |

The switch is one Mix Shader per material driven by an Attribute node of type View Layer (`pmds_view`), so it needs no script and works in
Material Preview, Eevee and Cycles. Plasma, fields, photon paths, glows and debug layers (emissive, transparent or driver-made
materials) are representations of phenomena, not solids: both views leave them as they are. Object colours (Solid shading), Outliner tags,
render materials and engineering identity stay four separate things. The 14 purpose colours are never Outliner colours.

## Dependencies and staleness

The catalogue travels outside the spec hash, like the detail packs. Each asset with bindings records `materials_hash`, the hash of exactly
the records its bindings use (applications, their layer and alternative materials and parents, appearances, purposes, cited references);
`inspect.py` fails a saved asset whose hash differs (`Stale material bindings`). `tools/checks.py` compares the catalogue with the base
revision record by record (`materials.affected_assets`), selects `test_materials` and builds only the affected assets: a change to the
AZ-93 emissivity rebuilds THERMAL, not the ship. The pipeline's accepted inputs, the loop stage identities and the runtime package
identity include `data/materials/*.toml`. The files are published production inputs like `data/*.toml` (no Drive capture, no
correspondence). Ownership: WF-CORE (`data/modules.toml`).

### Research backlog

Scientific qualification of individual materials is ongoing work that does not block using PMDS; TODO F05 holds the list: primary-source
verification; fusion plasma-facing materials (OD-025 heat flux, coolant, fluence, erosion, life); high-field superconductors (Jc at the
operating point, OD-024); radiation shielding; long-life high-temperature structures; radiator materials and coatings (hot emissivity,
aging); temperature- and radiation-dependent property tables; aging, creep, fatigue and replacement intervals.

## Design workflow

Every new significant component follows Purpose → Requirements → Candidate materials → Physical evaluation → Application → Blender
representation, in these steps:

1. Identify its engineering purposes (P01–P14).
2. Determine the environment and physical requirements: temperatures, heat flux, loads, fluids, radiation, life. Record unknown ones as
   `OPEN <source ref>`.
3. Identify candidate real materials (the purpose's candidates first; add Level A records with cited data where needed).
4. Evaluate their known limits and failure mechanisms against the requirements, for continuous long-life operation: creep, fatigue,
   vaporization in vacuum, thermal cycling, irradiation, compatibility, maintenance. Never a melting point.
5. Compare candidates on mass, lifetime, manufacturability and performance.
6. Record unknown properties and unresolved engineering questions in the catalogue (`open`) and the application (`requirements`).
7. Assign provisional application and layer IDs (`selection` CANDIDATE or PREFERRED).
8. Use the properties in supported calculations through `material_physics`, never by copying numbers into modules.
9. Generate the Blender appearance and bind the layer to a display material.
10. Validate: `test_materials`, `materials.validate`, the change-selected build and inspection (stale hashes, complete bindings), and a
    look at both views in the review file.
11. Take selections and open questions to the owner workbooks (the request Doc queue, OD items). Only a Drive answer makes a
    material canon; then the spec and source map record it as usual.
12. If a material is rejected, record why (the failing property and by how much) before proposing a Level B or C variant.

Steps 10–12 complete a list the owner's brief left cut off after "10. Valida…". Step 12 follows the
deficiency-driven variant workflow under "Development levels".

Add a new purpose only when none of the 14 describes the function. Do not force solid records onto visualization layers, and do not add
detailed geometry for a layer whose physical requirements are unknown: a layered form is developed first as a labelled study in
`work/<task>/`.
