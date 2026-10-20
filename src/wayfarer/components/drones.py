"""DRONE-001 study fleet (drone_fleet): WF_DRONES holds the stationary docks, units, rails and arm bases as PROTOTYPE proxies (REP_PROXY,
kind drone_proxy). The ring rover and duct cassettes are sector fit-out elements (route_fitout.sector_elements), so they turn with their ring;
the DS-11 radiator crawlers sit on the existing SP-51 root docks (WF_HULL). Each object carries its station, class, unit, owner source and
status; nothing here is a certified design, a mass or a power figure (S&E 51-54 STUDY / HOLD)."""
from common import cylinder_mesh, empty, line, material, mesh
import human_entry as he
import drone_fleet as df

COLORS = {'IVA': (.86, .88, .84), 'EVA': (.93, .62, .16), 'FIXED': (.80, .78, .30), 'dock': (.28, .31, .34), 'rail': (.55, .58, .60)}
FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
OWNER = 'STUDY (S&E 51/52 PROPOSED, UNPLACED / CAD OPEN): mass, power, speed, reach and latch load OPEN; placement is a Claude L2 anchor'


def _obj(c, q, mat):
    if q['shape'] == 'rod':
        return line(c, q['name'], q['points'], q['radius'], mat, kind='drone_proxy')
    if q['shape'] == 'tube':
        return mesh(c, q['name'], *cylinder_mesh(q['a'], q['b'], q['r1']), mat, kind='drone_proxy')
    return mesh(c, q['name'], he.box_corners(None, q), FACES, mat, kind='drone_proxy')


def drones(c, s):
    cl = df.classes(s); made = []
    mats = {k: material(f'Drone_{k.title()}', v) for k, v in COLORS.items()}
    for st in df.stations(s):
        if st['frame'] != 'VEHICLE':
            continue
        dom = cl[st['cls']]['domain']
        for kind, items in (('dock', st['docks']), ('unit', st['units']), ('rail', st['rails'])):
            for q in items:
                mat = mats['rail'] if kind == 'rail' else mats[dom] if kind == 'unit' or q['name'].startswith('Drone_ArmBase') else mats['dock']
                obj = _obj(c, q, mat)
                obj['station'] = st['id']; obj['drone_class'] = st['cls']; obj['drone_part'] = 'arm_base' if q['name'].startswith('Drone_ArmBase') else kind
                obj['role'] = q['role']; obj['source_ref'] = 'drone_fleet'; obj['geometry_status'] = 'PROTOTYPE'; obj['owner_status'] = OWNER
                if q.get('unit'):
                    obj['unit_id'] = q['unit']; obj['unit_role'] = q['role_state']
                if q.get('volume_m3') is not None:
                    obj['volume_m3'] = q['volume_m3']
                made.append(obj)
    r = df.spine_route(s)
    for k, d in enumerate(r['docks'], 1):      # the spine crawler's dock interfaces (L3 demonstration endpoints)
        e = empty(c, f'IF_DRONE_SPINE_DOCK_{k}', d['world_centre']); e['station'] = 'DS-13'; e['geometry_status'] = 'PROTOTYPE'
    return made
