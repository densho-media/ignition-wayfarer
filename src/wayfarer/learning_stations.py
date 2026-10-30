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
             show_me=dict(kind='outside', text='Outside view: watch the two rings turn in opposite directions. Press Use again to come back.'),
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
    ]


def document(s, root=ROOT):
    return {'schema': SCHEMA, 'version': 1, 'status': 'SIMULATION_ONLY / PROTOTYPE learning content; numbers carry their sources',
            'instructor': {'role': 'GU instructor', 'identity': 'not defined (UJ-001)',
                           'welcome': 'Welcome aboard. I am your GU instructor for the induction. Where you see a learning '
                                      'point, press Use: WHAT it is, WHY it is built so, and SHOW ME. Skip any of them.'},
            'stations': stations(s, root)}


def write(root, path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s, *_ = load(root)
    Path(path).write_text(json.dumps(document(s, root), indent=1)+'\n')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    print(json.dumps(document(load()[0]), indent=1))
