"""SP-46..54 survival envelopes and the Eye 50!A25:A30 terminals (survival_fit): PROTOTYPE boxes, rods and discs of kind survival_envelope
in the refuge (with WF_CREW_TRANSFER), the storeroom and outside the hull (with WF_HULL). The ring-sector envelopes are fit-out elements
(route_fitout.sector_elements). Each object carries its SP, owner source, status and installed volume; nothing here is canon or sized."""
from mathutils import Vector
from common import cylinder_mesh, line, material, mesh
import human_entry as he
import survival_fit as sf

COLORS = {'SP-48': (.20, .45, .62), 'SP-50': (.88, .90, .92), 'SP-54': (.92, .40, .08), 'SP-49': (.93, .94, .95), 'SP-53': (.30, .32, .36),
          'A29': (.30, .32, .36), 'SP-51': (.62, .56, .20)}
FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def build(c, items):
    made = []
    for q in items:
        mat = material(f"Survival_{q['sp'].replace('-', '')}", COLORS.get(q['sp'], (.6, .6, .6)))
        if q['shape'] == 'rod':
            obj = line(c, q['name'], q['points'], q['radius'], mat, kind='survival_envelope')
        elif q['shape'] == 'tube':
            obj = mesh(c, q['name'], *cylinder_mesh(q['a'], q['b'], q['r1']), mat, kind='survival_envelope')
        else:
            obj = mesh(c, q['name'], he.box_corners(None, q), FACES, mat, kind='survival_envelope')
        obj['sp'] = q['sp']; obj['role'] = q['role']; obj['source_ref'] = q['source_ref']; obj['geometry_status'] = 'PROTOTYPE'
        obj['owner_status'] = 'OPEN: size, mass, power, heat and contents in the owner rows (12A A49:I57, Eye 50!A25:A30); envelope only (34!B110)'
        for key in ('volume_m3', 'swept_m3', 'volume_bay_m3'):
            if key in q:
                obj[key] = q[key]
        if q.get('text'):
            import fitout
            t = dict(q, centre=q['world_centre'], size=q['size'])
            fitout.wbox_text(c, t, material('Fit_text', fitout.PALETTE['text']))['kind'] = 'survival_envelope'
        made.append(obj)
    return made


def refuge(c, s):
    return build(c, sf.refuge(s))


def hull(c, s):
    return build(c, sf.storeroom(s)+sf.exterior(s))
