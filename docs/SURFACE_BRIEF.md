# Wayfarer surface and asset brief (local implementation aid)

ART-S004-2026-10-10 (S&E 15!A120, 98!A85) asks for a short local brief derived from the owners. This is that brief: an implementation aid,
**not canon**, and it doesn't compete with the bibles. Where it disagrees with them, the owner text wins:

- Art Style Bible: Core Rules, Spacecraft, Objects & Tech, Anti-Rules.
- Culture `31_ARCHITECTURE` and request Doc §13.
- Fashion Bible Y155 / Spacer / Great Union.

It is implemented as `[look]` in `data/wayfarer_3d.toml` (`look.py`; docs/MODEL.md "Look"), and for the exterior as `[look.exterior]`
(`presentation/hero_preview.py`; docs/MODEL.md "First Ignition exterior").

## Order of work (15!C120)

1. The playable S004A–D induction (DOCKED and COAST): the boarding route, the crew-transfer walk, and close-ups of the instructor's and the
   newcomer's technical gear. This includes a representative outfit, material and lighting pass for the pair.
2. The First Ignition exterior hero views: Brow/EYE, drive, radiators and the fixed silhouette.
3. Later: other interior hero zones, the remaining crew, survival damage over the six years, and route scenes. There is no six-crew
   production this sprint.

## Three surface classes (15!I120)

| Class | What it covers | Surface rule |
|---|---|---|
| Physics-locked | pressure shells, radiator blades and joints, rotor interface, drive, shield, hatches and seals, everything AFT-009 / Q46 / OD-007 leaves unqualified | Stays REP_PROXY grey with its status label. **No hero finish** on a thermally or structurally unqualified interface (15!H120). Show construction (seams, load paths) only where the geometry already has it. |
| Engineering-flexible | the route fit-out (`route_fitout` elements already carry `ENGINEERING_FLEXIBLE`): frames, stringers, bezels, handholds, service lines, lockers, placards | The fit-out palette (`components/fitout.py`): greys for structure, Great Union deep blue for wayfinding, orange for safety, line colours only in the service chase. Matte, controlled microtexture. Wear only at touch and load points. A repair is history, never random grime (CR-09). |
| Artistic freedom | lighting, camera, the characters' outfits within the Fashion grammar, set dressing that carries no load | Restrained base palette with localized functional accents (Anti-Rules A6, A24). One dominant force and one focal point per view (CR-05, CR-06). Leave negative space in corridors (CR-15). |

## Materials and light for the S004 pass

- **Great Union issue** (instructor's occupational layer, hatch bezels, placards): deep blue, white, silver and grey. Precision-bonded,
  matte, with qualification and service marks.
- **Spacer** (the instructor's test-flight gear, the newcomer's GU-issued undersuit): close-fitting modular panels in compression and
  pressure textile, thermal membrane, radiation weave. Charcoal, grey, muted navy and white with safety accents. Light only at interfaces.
- **Ship interior:** quiet greys and off-whites under cool, even, diffuse cabin light. Warm light only where people live (galley, berths).
  Saturated colour goes to the functional accents only: wayfinding, safety, the service lines in the open chase.
- **Synthetic Residue** is a subdued property of the depiction (image organization). It is never a physical surface, overlay, texture or
  glow (CR-12, CR-13; Anti-Rules A9–A11).
- Avoid generic glossy sci-fi, neon, decorative circuitry, panoramic windows and uniform micro-detail (Anti-Rules A5–A7, A10, A15).

## Characters

The instructor's identity (name, sex and gender, body, face, hair, Burnmod profile) is OPEN in Tale `80_OPEN_VARIABLES` WTF-16. The 1.78 m
male MPFB instructor is a PROTOTYPE technical rig, not casting, and "Nadia Varga" is only a candidate name (15!A104, Tale 98!A26). The
outfit pass therefore dresses the role (Y155 Great Union flight-safety instructor in Spacer-close test gear) and the configurable newcomer
POV (GU induction undersuit). It does not dress a cast person. Both depart before First Ignition.
