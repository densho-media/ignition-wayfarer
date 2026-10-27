"""CIRC-001 continuous ring circulation (ring_circulation): the corridor liners, the pressure portals round each door, the door leaves (closed,
slid open by the runtime) and the handrail of every fill, parented to the rotor so they turn with the ring. The sector side-wall openings are
cut in WF_RING_SECTOR (revision.sector). PROTOTYPE whitebox: no seal, latch, drive, frame load or utility routing is designed."""
import bpy
from common import material, mesh, line
import ring_circulation as rc
import rotor_interface as ri

BASIS = 'PROTOTYPE CIRC-001 continuous circulation (owner direction 2026-10-26); conflicts with BASELINE 12!A13 and the 400-460 m3 gross envelope (ring_circulation.conflicts)'


def ring(c, s, parent, j):
    # the sectors' finishes ([look.surfaces]): deck and overhead as in the sectors, light walls, the portal grey of the frame
    mats = dict(floor=material('Interior_Deck', (.30, .32, .34)), ceiling=material('Interior_Overhead', (.62, .64, .66)),
                wall=material('CircWall', (.70, .74, .72)), step=material('CircPortal', (.46, .52, .55)))
    fit = dict(frame=material('Fit_frame', (.20, .21, .23)), band=material('Fit_band', (.07, .16, .42)), safety=material('Fit_safety', (.92, .40, .08)))
    order = list(mats)
    portal_mat, leaf_mat, rail_mat = material('CircPortal', (.46, .52, .55)), material('CircDoor', (.72, .52, .22)), material('CircRail', (.85, .62, .12))
    light_mat = material('EntryLight', (1.0, .93, .80), 12.0)
    tag = 'AB'[j-1]
    for f in rc.fills(s, j):
        vs, fs, cls = rc.liner(s, j, f['fill'])
        obj = mesh(c, f"Ring_{j}_Circ_Corridor_{f['fill']}", vs, fs, mats['floor'], kind='circulation_corridor')
        for k in order[1:]:
            obj.data.materials.append(mats[k])
        obj.data.polygons.foreach_set('material_index', [order.index(k) for k in cls])
        obj.parent = parent; obj['geometry_basis'] = BASIS; obj['evidence_ref'] = 'ring_circulation_direction'
        obj['compartments'] = f"{tag}C{f['fill']}a, {tag}C{f['fill']}b"; obj['suited_access'] = False
        obj['gross_m3'] = rc.cavity_m3(s, f['t1']-f['t0'])
        sec = rc.section(s); h = s['ring_circulation']['handrail_height_m']
        ts = rc._arc(f['t0']+0.4/sec['floor_r'], f['t1']-0.4/sec['floor_r'])
        # the interior design language (ring_circulation.fitout): frame rhythm, route band, safety-edged door frames, one mesh per class
        for cls, solids in rc.fitout(s, j, f['fill']).items():
            vs, fs = [], []
            for q in solids:
                v, fc = ri.solid(*q); fs += [tuple(len(vs)+i for i in face) for face in fc]; vs += v
            if vs:
                o = mesh(c, f"Ring_{j}_Circ_Fit_{cls.title()}_{f['fill']}", vs, fs, fit[cls], kind='circulation_fitout')
                o.parent = parent; o['layer'] = 'ARCHITECTURE'; o['geometry_basis'] = 'PROTOTYPE depiction (route_fitout scheme A grammar)'
        rail = line(c, f"Ring_{j}_Circ_Handrail_{f['fill']}", [rc.radial(sec['clear_u'][1]-.06, sec['floor_r']-h, t) for t in ts], .0175, rail_mat, kind='circulation_fixture')
        rail.parent = parent; rail['function'] = 'corridor handrail (spin transients, LOW_THRUST tilt)'
        # light strips on the ceiling's centreline every light_pitch_m (the cabin light class of the route, look.lights)
        pitch = s['ring_circulation']['light_pitch_m']; L = (f['t1']-f['t0'])*sec['floor_r']; n = max(1, int(L/pitch))
        for k in range(n):
            tm = f['t0']+(f['t1']-f['t0'])*(k+.5)/n; dt = .4/sec['ceiling_r']
            vs, fs = ri.solid(sec['u_centre']-.05, sec['u_centre']+.05, sec['ceiling_r'], sec['ceiling_r']+.02, tm-dt, tm+dt)
            lamp = mesh(c, f"Ring_{j}_Circ_Light_{f['fill']}_{k+1:02}", vs, fs, light_mat, kind='circulation_fixture')
            lamp.parent = parent; lamp['function'] = 'corridor light strip'
    for k, q in enumerate(rc.portals(s, j)):
        vs, fs = ri.solid(q['u0'], q['u1'], q['r0'], q['r1'], q['t0'], q['t1'])
        obj = mesh(c, f"Ring_{j}_Circ_Portal_{q['fill']}_{k:02}", vs, fs, portal_mat, kind='circulation_portal')
        obj.parent = parent; obj['geometry_basis'] = BASIS
    for d in rc.doors(s, j):
        vs, fs = ri.solid(*rc.leaf(s, d))
        obj = mesh(c, d['name'], vs, fs, leaf_mat, kind='circulation_door')
        obj.parent = parent; obj['door_id'] = d['id']; obj['door_kind'] = d['kind']; obj['between'] = ' | '.join(d['between'])
        obj['normally'] = d['normally']; obj['slide_m'] = d['travel']; obj['geometry_basis'] = BASIS
        obj['engineering_status'] = 'OPEN: sliding pressure door, seated on its frame; seal, latch, drive and pressure-differential rating not designed'
