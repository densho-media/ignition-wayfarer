"""UJ-013 learning stations for the walk (Tale of Wayfarer 30_UNIFIED_JOURNEY UJ-003, UJ-004, UJ-013; owner brief 2026-10-29).

One shared interaction: at a station the trainee opens WHAT (identify the thing), WHY (the constraint that shapes it) and SHOW ME (a view
or an overlay), each optional and skippable, framed by the GU instructor (no name: UJ-001 defines no instructor identity). Every station
has a stable ID, the exported node it stands at (the walk finds it by name and follows it as the ring turns), its reach, the objective
it completes and its numbers with their source and status. Numbers come from the spec and data/life_support.toml through this module;
Godot computes none and adds none (UJ-013: every numeric claim has its owning workbook, source and status). Standard library only.

    python3 src/wayfarer/learning_stations.py        # print the stations
"""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
FILE = 'wf_learning.json'
SCHEMA = 'WF_LEARNING_STATIONS'
G0 = 9.80665


def spin(s):
    """Spin gravity and the Coriolis push at the deck: rate, radius, field and the sideways push on a walker at 1 m/s and on a hand
    lifting a mug at 0.5 m/s (2 omega v)."""
    h = s['habitat']; w = h['rpm']*2*math.pi/60; r = h['floor_radius']['value']
    return dict(rpm=h['rpm'], radius_m=r, g=w*w*r/G0, rim_speed_m_s=w*r, coriolis_walk_g=2*w*1.0/G0, coriolis_lift_g=2*w*0.5/G0,
                sources=[f"rpm: habitat.rpm ({h['canon_status']}, {h['source_ref']})",
                         f"floor radius: habitat.floor_radius ({h['floor_radius']['canon_status']}, {h['floor_radius']['source_ref']})"])


def resources(root=ROOT):
    """Daily life-support flows for the story crew from the owner's 41_SURVIVAL_RESOURCES study (STUDY, not canon) and the stores' status."""
    import life_support
    reg = life_support.load(root); r = life_support.rates(reg); n = reg['consumers']['story']
    src = {q['id']: q['source'] for q in reg['rate']}
    flows = [(k, label, r[k], r[k]*n, src[k]) for k, label in (('O2', 'oxygen breathed'), ('CO2_REMOVED', 'CO2 to remove'),
                                                               ('WATER_TURNOVER', 'water turned over'), ('FOOD', 'food eaten'))]
    stores = [(q['id'], q['value'] if q['known'] else None, q.get('status', ''), q['source']) for q in reg['store']]
    return dict(consumers=n, consumers_source=reg['consumers']['story_source'], status=reg['life_support']['status'],
                notice=reg['life_support']['notice'], flows=flows, stores=stores)


def space_map(root=ROOT):
    """UJ-010's map: the Space Navigator chart (space_navigator.contract) in its PRESENTATION transform (square-root distances, log glyphs),
    bodies on one layout ray because no epoch is released; the ship is not placed (its course is drawn as a schematic arrow only)."""
    import space_navigator as sn
    c = sn.contract(sn.load(root)); kb = next(r for r in c['regions'] if r['id'] == 'KUIPER_BELT_MAIN')
    glyph = lambda r_km: round(max(2.0, 3+2.4*math.log10(max(r_km, 1000.0)/1000)), 2)
    return dict(notice=c['schematic_notice'], disclosure=c['transforms']['PRESENTATION']['disclosure'], a_ref_au=kb['outer_au'],
                sun_px=glyph(next(b for b in c['bodies'] if b['kind'] == 'star')['radius_km'])/2,
                bodies=[dict(name=b['name'], a_au=round(b['a_au'], 3), q_au=round(b['perihelion_au'], 3), Q_au=round(b['aphelion_au'], 3),
                             glyph_px=glyph(b['radius_km'])) for b in c['bodies'] if b['kind'] == 'planet'],
                region=dict(name=kb['name'], inner_au=kb['inner_au'], outer_au=kb['outer_au']),
                course='Planned crossing: outward past the Kuiper Belt. Direction and timing schematic (no epoch released).')


def stations(s, root=ROOT):
    sp = spin(s); rs = resources(root)
    flow_lines = [f"{label}: {per:.2f} kg per person-day, {total:.1f} kg/day for {rs['consumers']} ({src})" for _, label, per, total, src in rs['flows']]
    store_lines = [f"{k}: " + (f"{v:,.0f} kg ({st})" if v is not None else f"OPEN, sizing not released ({src})") for k, v, st, src in rs['stores']]
    return [
        dict(id='LS-UJ003-SPIN', journey='UJ-003', title='Spin gravity at the mess table', ring='RING_A', node='Prod_RA3_GDN_Mess', reach_m=2.6,
             objective='Know why the deck pulls you down and why the table has a rail.',
             instructor='You are standing on the inside of a turning wheel. Nothing pulls you outward; the deck keeps pushing you inward.',
             what=['Ring A, sector 3: the mess booth for six beside the Garden.',
                   'The table carries a low fiddle rail; the mugs hang on a rail, not loose on a shelf.'],
             why=[f"The rings turn at {sp['rpm']:g} rpm. At the deck, {sp['radius_m']:g} m from the axis, that gives {sp['g']:.2f} g.",
                  f"The deck moves at {sp['rim_speed_m_s']:.1f} m/s. Anything that moves inside the ring is pushed sideways (Coriolis): "
                  f"{sp['coriolis_walk_g']:.3f} g when you walk at 1 m/s, {sp['coriolis_lift_g']:.3f} g on a mug lifted at 0.5 m/s.",
                  'So liquids slosh sideways and loose things drift: spill lips, rails and closed trays everywhere.'],
             show_me=dict(kind='remote', text='Remote camera on the rings: they turn in opposite directions, so the ship does not. Press Use again to come back.', camera=dict(eye=[55.0, 75.0, 35.0], target=[88.0, 0.0, 0.0])),
             sources=sp['sources']+['Coriolis: 2 x omega x v, derived', 'mess fit-out: ra3_garden (PROTOTYPE, L4_VISUAL_CANDIDATE)'],
             status='rates WORKING/BASELINE; derived values; fit-out PROTOTYPE'),
        dict(id='LS-UJ004-LIFE', journey='UJ-004', title='Life support and the Garden', ring='RING_A', node='Prod_RA3_GDN_ECLSS', reach_m=2.8,
             objective='Know what the crew uses every day and which stores are still open.',
             instructor='Everything you breathe, drink and eat goes round this bay. Watch the numbers, not the plants.',
             what=['The life-support service bay (air revitalization, water recovery) and its resource board: WATER, O2, CO2.',
                   'The Garden rack beside the aisle: four pull-out tray levels under grow lights, 4 m2 of trays in each ring.'],
             why=[f"Daily flows for the {rs['consumers']} people aboard ({rs['status']}, not canon; Seraph eats and breathes none of it):"]+flow_lines+[
                  'The Garden is credited with no food and no oxygen yet (41!B20, 38 S02): it is food support and morale, not the air supply.'],
             show_me=dict(kind='overlay', title='Stock and flow, per day',
                          text=['CREW -> O2 in, CO2 and water out', 'CO2 -> removed by the bay (recovery to O2 not credited)',
                                'WATER -> recovered and made up from the makeup store', 'FOOD -> drawn from the launch store']+store_lines,
                          note=rs['notice']),
             sources=[rs['consumers_source'], *[f[4] for f in rs['flows']], 'Garden trays: 12!A28 (owner Q50)', 'board: ra3_garden (PROTOTYPE)'],
             status='STUDY rates; stores partly OPEN; board levels illustrative'),
    ]+ops_stations(s)


def _v(q):
    return f"{q['value']:,.0f} {q.get('unit', '')}".strip()


def ops_stations(s):
    """UJ-006..011 at the pressurized ops, engineering and medical stations of ring A sector 2 (S&E 15 Q48: EYE, thermal and drive teaching
    stops are internal operations/representation stations; nothing hazardous is approached). The station placement is PROTOTYPE."""
    r = s['radiators']; p = s['propulsion']; fd = s['forward_defense']; e = s['eye']; m = s['mission']
    faces = r['count']*r['emitting_faces']
    eye = dict(id='LS-UJ006-EYE', journey='UJ-006', title='The Eyes: sensing before defense', ring='RING_A', node='Prod_RA2_WRK_Ops_1', reach_m=2.3,
               objective='Know what the four Eyes look through, and why the ship must see a hazard before it can do anything about it.',
               instructor='This screen is the forward station. We never go to the Brow face: we look through the Eyes from here.',
               what=[f"OPS 1 shows the {e['facet_count']} Eye facets set in wells in the forward shield (the Brow), each behind its own shutter.",
                     f"Each Eye has a {_v(e['aperture'])} aperture. There is no fifth, central Eye: the mast on the axis is the Dust Lance."],
               why=[f"At {m['target_speed']['value']:g} c a one-milligram grain arrives with {0.5e-6*(m['target_speed']['value']*299792458)**2/1e6:.1f} MJ, "
                    f"about {0.5e-6*(m['target_speed']['value']*299792458)**2/4.184e6:.1f} kg of TNT. A hazard the ship has not seen cannot be avoided, steered round or met.",
                    'Four facets far apart give a long baseline: range and direction from parallax, and the ship keeps seeing if one facet is shuttered or lost.',
                    f"The saved model sets the Eyes at r30, two thirds of the shield radius ({fd['eye_layout']['status']}: the owner rows keep r4 as a study alternative)."],
               show_me=dict(kind='remote', text='Remote camera ahead of the Brow: find the four Eye wells and the Dust Lance between them. Press Use again to come back.', camera=dict(eye=[195.0, 25.0, 30.0], target=[112.0, 0.0, 0.0])),
               sources=[f"facets: eye.facet_count ({e['canon_status']}, {e['source_ref']})", f"aperture: eye.aperture ({e['aperture']['canon_status']}, {e['aperture']['source_ref']})",
                        f"target speed: mission.target_speed ({m['target_speed']['canon_status']})", 'grain energy: 1/2 m v^2, derived', 'layout r30: user 2026-10-29 (STUDY vs owner r4)', 'Tale 30 UJ-006'],
               status='facets LOCKED; layout STUDY; station placement PROTOTYPE')
    aegis = dict(id='LS-UJ007-AEGIS', journey='UJ-007', title='Aegis: three hazard sizes, three answers', ring='RING_A', node='Prod_RA2_WRK_Ops_2', reach_m=2.3,
                 objective='Know that forward defense is a ladder for different hazard sizes, not one weapon.',
                 instructor='Next screen, same watch. Different sizes of trouble get different answers.',
                 what=['OPS 2 shows the forward defense: the Brow shield, the Crown of twelve protected bays round its rim, and the Dust Lance on the axis.',
                       f"The Dust Lance is a {_v(fd['dust_lance']['length'])} structural and field mast with a replaceable sacrificial tip."],
                 why=['Microdust: too small and too many to see one by one. The shield and its disruptor layers take it; nothing intercepts single microns.',
                      'Centimetre-class: seen early enough by the Eyes, met by the Crown inside the Brow silhouette, or simply avoided.',
                      'Metre-scale: no defense stops it. The only answer is to see it very early and change course first.',
                      'The Crown is active mitigation, not armour and not a substitute for avoidance.'],
                 show_me=dict(kind='remote', text='Remote camera at the shield rim: the Crown bays round the edge, the Lance on the axis. Press Use again to come back.', camera=dict(eye=[150.0, 62.0, 42.0], target=[108.0, 25.0, 15.0])),
                 sources=[f"Crown: forward_defense.crown ({fd['crown']['canon_status']}, {fd['crown']['source_ref']})",
                          f"Dust Lance: forward_defense.dust_lance ({fd['dust_lance']['canon_status']}, {fd['dust_lance']['source_ref']})", 'Tale 28 AVA-003..014; Tale 30 UJ-007'],
                 status='WORKING architecture; training framing PROTOTYPE')
    rad = dict(id='LS-UJ008-RADIATORS', journey='UJ-008', title='Waste heat and the three blades', ring='RING_A', node='Prod_RA2_WRK_Tools_Lab_Bench', reach_m=2.4,
               objective='Know why the ship carries three huge hot blades and why nobody walks on them.',
               instructor='In vacuum there is no air to carry heat away. The only way out is to glow.',
               what=[f"{r['count']} fixed radiator blades, {r['separation_deg']['value'] if isinstance(r['separation_deg'], dict) else r['separation_deg']:g} degrees apart, "
                     f"each radiating from both faces ({faces} faces), out to r {_v(r['outer_radius'])}.",
                     f"They run at {_v(r['temperature'])}, emissivity {r['emissivity']['value']:g}."],
               why=[f"Effective radiating area: {_v(r['effective_area'])} ({r['effective_area']['canon_status']}: as-built area x {faces} faces x view factor {r['view_factor']['value']:g}).",
                    'Radiated power grows with the fourth power of temperature: hot radiators are small radiators.',
                    'The drive\'s waste heat and the heat-debt budget are still OPEN: no rejection margin is claimed here.',
                    f"An {_v(r['temperature'])} surface glows orange-white: radiators are seen by remote camera, never approached."],
               show_me=dict(kind='remote', text='Remote camera beside the ship: the three blades, edge-on to each other at 120 degrees. Press Use again to come back.', camera=dict(eye=[-5.0, 150.0, 95.0], target=[-20.0, 0.0, 0.0])),
               sources=[f"radiators: count, temperature, emissivity ({r['canon_status']}/{r['temperature']['canon_status']}, {r['source_ref']}, {r['temperature']['source_ref']})",
                        f"effective area ({r['effective_area']['source_ref']})", 'drive waste heat: OPEN (thermal_open)', 'Tale 30 UJ-008'],
               status='BASELINE count; WORKING temperature; heat budget OPEN')
    drive = dict(id='LS-UJ009-DRIVE', journey='UJ-009', title='The drive: one core, four nozzles', ring='RING_A', node='Prod_RA2_WRK_Tools_Workbench', reach_m=2.4,
                 objective='Know the drive\'s parts in order, from fuel to the four nozzles, and why it is never visited live.',
                 instructor='Basics only. The propulsion team owns the rest; their notes come later.',
                 what=[f"{p['core_count']} reactor core, {p['manifold_count']} magnetic manifold, {p['channel_count']} channels, {p['nozzle_count']} nozzles at the aft end.",
                       'The fuel stores (He-3 in the aft body, hydrogen and deuterium in the forward torus) feed four run tanks next to the drive.'],
                 why=[f"The structure is sized for {_v(p['design_thrust'])} (a proof load at 1.5 g, {p['design_thrust']['canon_status']}), not normal flight thrust.",
                      'Field strengths, exhaust speed and waste heat are not released: no number is shown for them.',
                      'No one enters the core or a nozzle while it can be live. This bench is where the parts are explained, not touched.'],
                 show_me=dict(kind='remote', text='Remote camera behind the ship: the thrust ring and the four nozzles. Press Use again to come back.', camera=dict(eye=[-175.0, 35.0, 28.0], target=[-105.0, 0.0, 0.0])),
                 sources=[f"counts: propulsion ({p['canon_status']}, {p['source_ref']})", f"design thrust: propulsion.design_thrust ({p['design_thrust']['source_ref']})",
                          'fuel split: fuel_storage (WORKING, fuel_split)', 'Tale 30 UJ-009'],
                 status='counts LOCKED; loads DERIVED; plasma values OPEN')
    preview = dict(id='LS-UJ010-PREVIEW', journey='UJ-010', title='Mission preview: how it fits together', ring='RING_A', node='Prod_RA2_WRK_Ops_3', reach_m=2.3,
                   objective='Connect Eyes, radiators, habitat, drive, life support and trajectory into one planned mission.',
                   instructor='This is the plan for the tests ahead, not something happening now.',
                   what=['OPS 3 is the navigation station: the ship view and the space map.'],
                   why=[f"The crossing is planned at {m['target_speed']['value']:g} c for {m['duration']['value']:g} years ({m['target_speed']['canon_status']}).",
                        'The Eyes see, the shield and Crown protect, the drive pushes, the radiators carry its heat away, the rings keep the crew healthy, life support keeps them alive.',
                        'Ship positions on the map are schematic: no ephemeris is shown as real.'],
                   show_me=dict(kind='overlay', title='Planned sequence (preview, not live)',
                                text=['DOCKED: boarding, rings stopped', 'COAST: rings turning, Eyes watching', 'IGNITION: crew at the burn couches, rings managed',
                                      'BURN: drive on, radiators hot', 'COAST: the long crossing'],
                                note='Preview only. The First Ignition story starts after the visitor has left.', map=space_map()),
                   sources=[f"mission.target_speed, mission.duration ({m['target_speed']['canon_status']})", 'operating states: S&E 15 Q48', 'Tale 30 UJ-010', 'map: data/space_navigator.toml (NASA fact sheets; SCHEMATIC arrangement)'],
                   status='LOCKED mission figures; sequence WORKING; timeline and map schematic')
    debrief = dict(id='LS-UJ011-DEBRIEF', journey='UJ-011', title='Debrief before you leave', ring='RING_A', node='Prod_RA2_WRK_Medical', reach_m=2.2,
                   objective='Recap the induction and leave the ship before First Ignition.',
                   instructor='Check-out, then we leave the way we came. The six who stay are the crew; we are not.',
                   what=['The medical bay: every crossing of the ship ends with a check-out here.'],
                   why=['You have seen the spin, the air and water, the Eyes and the Crown, the radiators, the drive and the plan.',
                        'Visitors and the instructor leave before First Ignition: nobody becomes a seventh crew member.'],
                   show_me=dict(kind='remote', text='Look back at the whole ship before you leave. Press Use again to come back.', camera=dict(eye=[140.0, 170.0, 75.0], target=[0.0, 0.0, 0.0])),
                   sources=['Tale 30 UJ-011; Tale S004A-D', 'medical bay: ra2_work (PROTOTYPE)'],
                   status='narrative WORKING; placement PROTOTYPE')
    import drone_fleet as df
    cl = df.classes(s); crawler = cl['DR-IVA-03']; brow = cl['DR-EVA-01']; rads = cl['DR-EVA-02']
    drones = dict(id='LS-UJ014-DRONES', journey='UJ-014', title='Drones: the crew\'s hands where people cannot go', ring='RING_A',
                  node='Prod_RA2_EQP_Trays', reach_m=2.6,
                  objective='Know which jobs go to drones and why every drone route is still on hold.',
                  instructor='Look up at the cable trays. The smallest crawler is meant to live in spaces like these.',
                  what=[f"Inside: a survey free-flyer, a habitat rover and the {crawler['name'].lower()} "
                        f"({crawler['envelope_m'][0]:g}-{crawler['envelope_m'][1]:g} m class) for ducts and trays.",
                        f"Outside: crawlers on rails for the Brow and Eyes ({brow['envelope_m'][0]:g}-{brow['envelope_m'][1]:g} m class), "
                        f"the radiators, the spine and the drive, plus two fixed service arms."],
                  why=['Hot radiators, the Brow face and the drive are places a person should never be; a crawler on a rail can be.',
                       'Every crawl is still HOLD: the raceways, payloads and power are not designed yet, so no drone task is promised.',
                       'Drones never become the only way to fix something the crew depends on to stay alive.'],
                  show_me=dict(kind='remote', text='Remote camera on a radiator blade: the crawler track runs along its casing. Press Use again to come back.', camera=dict(eye=[5.0, 42.0, 44.0], target=[-20.0, 17.3, 10.0])),
                  sources=['drone classes: drone_fleet (S&E 51/52, PROPOSED / NOT SIZED)', 'routes: drone_routes (HOLD)', 'Tale 30 UJ-014'],
                  status='classes PROPOSED; routes HOLD; station placement PROTOTYPE')
    return [eye, aegis, rad, drive, preview, debrief, drones]


# UJ-014: every mandatory component, the station that teaches it and how it is shown, or OPEN.
COVERAGE = [
    ('Brow (forward shield)', 'LS-UJ007-AEGIS', 'remote camera'), ('4 Eyes', 'LS-UJ006-EYE', 'remote camera'),
    ('Crown 12 bays', 'LS-UJ007-AEGIS', 'remote camera'), ('Dust Lance', 'LS-UJ007-AEGIS', 'remote camera'),
    ('3 radiators', 'LS-UJ008-RADIATORS', 'remote camera'), ('reactor / four nozzles', 'LS-UJ009-DRIVE', 'remote camera'),
    ('rings / spine', 'LS-UJ003-SPIN', 'remote camera; physical walk'), ('Garden', 'LS-UJ004-LIFE', 'physical + overlay'),
    ('mission map', 'LS-UJ010-PREVIEW', 'overlay + schematic Space Navigator map'), ('habitat safety', 'LS-UJ003-SPIN', 'physical'),
    ('drones', 'LS-UJ014-DRONES', 'remote camera'), ('debrief / departure', 'LS-UJ011-DEBRIEF', 'remote camera; physical egress (the walk goal turns to the way out)'),
]


def document(s, root=ROOT):
    return {'schema': SCHEMA, 'version': 1, 'status': 'SIMULATION_ONLY / PROTOTYPE learning content; numbers carry their sources',
            'instructor': {'role': 'GU instructor', 'identity': 'not defined (UJ-001)',
                           'welcome': 'Welcome aboard. I am your GU instructor for the induction. Where you see a learning '
                                      'point, press Use: WHAT it is, WHY it is built so, and SHOW ME. Skip any of them.'},
            'stations': stations(s, root),
            'coverage': [{'component': c, 'station': st, 'view': v} for c, st, v in COVERAGE]}


def write(root, path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s, *_ = load(root)
    Path(path).write_text(json.dumps(document(s, root), indent=1)+'\n')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    print(json.dumps(document(load()[0]), indent=1))
