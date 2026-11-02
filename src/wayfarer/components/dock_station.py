"""STN-002 recipe: the development station's docking context (station.context_parts, [station.context]) in its own asset
assets/station/WF_STATION.blend, never linked into the vehicle (the station is not Wayfarer). Built docked, in the vehicle frame, so it
appends onto the ship as is. The boom's moving stages hang from the mechanism empties STN_BOOM_STAGE_<k> (the inner one carries the
head); STN_BOOM_CTRL['retract'] 0..1 drives them out along the port axis by their share of the stroke, saved 0 (docked). PROTOTYPE,
REP_PROXY; station palette: warm off-white blankets, bare-metal stages, EVA-yellow aids, so it never reads as part of the ship."""
import math

import bmesh
import bpy
from mathutils import Vector

from common import cylinder_mesh, empty, group, material, mesh, revolve_mesh, tag
import human_entry as he
import station as stn

FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
# group -> (outliner sub-group, colour); grey helpers stay uncoloured
GROUPS = {'HEAD': '11_HEAD', 'BOOM': '12_BOOM', 'HUB': '13_HUB', 'TRUSS': '14_TRUSS', 'SERVICE': '15_SERVICE', 'ACCESS': '16_ACCESS'}


def palette():
    return dict(blanket=material('Stn_Blanket', (.74, .71, .64)), metal=material('Stn_Metal', (.56, .58, .60)),
                seal=material('Stn_Seal', (.20, .21, .22)), rail=material('Stn_EVA_Yellow', (.85, .62, .08)),
                umb=material('Stn_Umbilical', (.05, .05, .055)), glass=material('Stn_Window', (.02, .03, .04)),
                truss=material('Stn_Truss', (.62, .63, .64)), deck=material('Stn_Platform', (.30, .31, .33)),
                lens=material('Stn_Lamp', (1.0, .95, .85), emission=12.0), suit=material('Stn_Suit', (.86, .86, .84)),
                visor=material('Stn_Visor', (.55, .42, .12)), iva=material('Stn_IVA', (.085, .095, .12)),
                skin=material('Stn_Skin', (.58, .47, .40)), strap=material('Stn_Strap', (.90, .38, .07)))


def pick(M, name):
    for keys, key in ((('Window',), 'glass'), (('SealRing', 'CaptureRing', 'Gimbal', 'Utility_Panel'), 'seal'),
                      (('Boom_Stage', 'Clip', 'Reel'), 'metal'), (('Umbilical',), 'umb'),
                      (('Hoop', 'Rail', 'PFR', 'Floodlight_Post'), 'rail'), (('Truss',), 'truss'), (('Platform',), 'deck')):
        if any(k in name for k in keys):
            return M[key]
    return M['blanket']


def corners(q):
    c = Vector(q['world_centre']); ax = [Vector(a)*(sz/2) for a, sz in zip(q['axes'], q['size'])]
    return [tuple(c+sx*ax[0]+sy*ax[1]+sz*ax[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def part(c, q, M):
    n = 48 if q['r1'] > .5 else 20 if q['r1'] > .05 else 10
    if q.get('r_in'):
        L = (Vector(q['b'])-Vector(q['a'])).length
        vs, fs = revolve_mesh(q['a'], q['b'], [(0.0, q['r_in']), (L, q['r_in']), (L, q['r1']), (0.0, q['r1'])], n=n)
    else:
        vs, fs = cylinder_mesh(q['a'], q['b'], q['r1'], n=n)
    return mesh(c, q['name'], vs, fs, pick(M, q['name']), kind='station')


def figure(c, fd, M):
    """A 1.8 m scale proxy (suited white for EVA, the ship's dark coverall for IVA): capsules, head, visor and pack."""
    eva = fd['kind'] == 'EVA'; up = Vector(fd['up']).normalized(); fw = Vector(fd['facing']); fw = (fw-up*fw.dot(up)).normalized(); side = fw.cross(up)
    feet = Vector(fd['feet']); H = 1.8; P = lambda h, sd=0.0, f=0.0: feet+up*h*H+side*sd+fw*f
    body = M['suit'] if eva else M['iva']; made = []

    def cap(name, a, b, r, m):
        vs, fs = cylinder_mesh(a, b, r, n=14); made.append(mesh(c, name, vs, fs, m, kind='scale_reference'))
        for k, e in enumerate((a, b)):
            bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=r); bmesh.ops.translate(bm, vec=Vector(e), verts=bm.verts)
            me = bpy.data.meshes.new(f'{name}_End{k}_Mesh'); bm.to_mesh(me); bm.free(); me.materials.append(m)
            ob = bpy.data.objects.new(f'{name}_End{k}', me); c.objects.link(ob); made.append(tag(ob, ob.name, 'scale_reference'))
    cap(fd['name']+'_Torso', P(.53), P(.72), .19 if eva else .15, body)
    cap(fd['name']+'_Hips', P(.47), P(.53), .17 if eva else .14, body)
    for sd in (-1, 1):
        cap(f"{fd['name']}_Leg_{'L' if sd < 0 else 'R'}", P(.04, .10*sd), P(.46, .10*sd), .085 if eva else .065, body)
        cap(f"{fd['name']}_Arm_{'L' if sd < 0 else 'R'}", P(.78, .24*sd), P(.50, .27*sd, .10), .07 if eva else .05, body)
    cap(fd['name']+'_Head', P(.86 if eva else .88), P(.86 if eva else .88)+up*1e-3, .17 if eva else .11, M['suit'] if eva else M['skin'])
    for name, centre, size, m in ([(fd['name']+'_Visor', P(.865, 0, .12), (.22, .13, .06), M['visor']), (fd['name']+'_Pack', P(.62, 0, -.27), (.50, .62, .22), M['suit'])]
                                  if eva else [(fd['name']+'_Harness', P(.64, 0, .12), (.30, .06, .04), M['strap'])]):
        made.append(mesh(c, name, corners(dict(world_centre=centre, axes=(side, up, fw), size=size)), FACES, m, kind='scale_reference'))
    for ob in made:
        ob['role'] = fd['role']; ob['geometry_status'] = 'scale figure, not anthropometric canon'
    return made


def build(c, s):
    """WF_STATION: 10_STATION (11_HEAD .. 16_ACCESS), 20_HUMAN_SCALE, 30_MECHANISM (the boom control and stage empties)."""
    M = palette(); P = s['station']['context']; f = stn.port(s); u, _ = he.axes(f); n = P['stage_count']
    top = group(c, '10_STATION', 'COLOR_03'); sub = {g: group(top, name) for g, name in GROUPS.items()}
    mech = group(c, '30_MECHANISM'); figs = group(c, '20_HUMAN_SCALE')
    ctrl = empty(mech, 'STN_BOOM_CTRL', stn.world(s, stn.context_geometry(s)['hub_face']), kind='mechanism_control')
    ctrl['retract'] = 0.0; ctrl['role'] = 'IMPLEMENTATION display control: boom retraction 0 docked .. 1 retracted by the full stroke, saved 0'
    ctrl['stroke_m'] = stn.context_geometry(s)['stroke']
    movers = {}
    for k in range(2, n+1):
        e = empty(mech, f'STN_BOOM_STAGE_{k}', (0, 0, 0), kind='mechanism')
        share = (k-1)*(P['stage_length_m']-P['stage_overlap_m'])
        e['retract_m'] = share; e['axis'] = (0.0, u[1], u[2]); e['role'] = 'boom stage mover' + (' (carries the head)' if k == n else '')
        for i in (1, 2):
            fc = e.driver_add('location', i); d = fc.driver; d.type = 'SCRIPTED'
            var = d.variables.new(); var.name = 'r'; var.targets[0].id = ctrl; var.targets[0].data_path = '["retract"]'
            d.expression = f'r*{share*u[i]:.6f}'
        movers[k] = e
    for q in stn.context_parts(s):
        if q['shape'] == 'light':
            ld = bpy.data.lights.new(q['name'], 'SPOT'); ld.energy = 2500.0; ld.spot_size = math.radians(28); ld.spot_blend = .35; ld.color = (1.0, .96, .90)
            ob = bpy.data.objects.new(q['name'], ld); sub['SERVICE'].objects.link(ob); ob.location = q['at']
            ob.rotation_euler = (Vector(q['target'])-Vector(q['at'])).to_track_quat('-Z', 'Y').to_euler(); tag(ob, q['name'], 'station_light')
            vs, fs = cylinder_mesh(q['at'], tuple(Vector(q['at'])+(Vector(q['target'])-Vector(q['at'])).normalized()*.18), .14, n=16)
            lamp = mesh(sub['SERVICE'], q['name']+'_Lamp', vs, fs, M['lens'], kind='station'); lamp.visible_shadow = False
            ob['role'] = lamp['role'] = q['role']
            continue
        if q['shape'] == 'tube':
            ob = part(sub[q['group']], q, M)
        else:
            ob = mesh(sub[q['group']], q['name'], corners(q), FACES, pick(M, q['name']), kind='station')
        ob['role'] = q['role']; ob['station_group'] = q['group']; ob['mover'] = q['mover']; ob['evidence_ref'] = 'docking_standard'
        ob['owner_status'] = 'PROTOTYPE (STN-002, owner approval 2026-11-02): not part of Wayfarer, not canon; loads, seals and connectors OPEN'
        if q['mover'] >= 2:
            ob.parent = movers[q['mover']]
    for fd in stn.context_figures(s):
        for ob in figure(figs, fd, M):
            if fd['name'] in ('STN_Figure_Trainee', 'STN_Figure_Inspector'):
                ob.parent = movers[n]
    cams = group(c, '40_CAMERAS')
    for name, eye, target, lens in cameras(s):
        cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = .3; cd.clip_end = 3000
        ob = bpy.data.objects.new(name, cd); cams.objects.link(ob); ob.location = eye
        ob.rotation_euler = (Vector(target)-Vector(eye)).to_track_quat('-Z', 'Y').to_euler(); tag(ob, name, 'camera')
    bpy.context.scene.camera = bpy.data.objects['CAM_STN_CONTEXT']


def cameras(s):
    """(name, eye, target, lens) of the station's review cameras in the vehicle frame (the owner-reviewed framings of 2026-11-02)."""
    P = s['station']['context']; g = stn.context_geometry(s); hc, R = g['hub_centre_a'], P['hub_radius_m']; px = sum(P['platform_x_m'])/2
    W = lambda a, rho=0.0, phi=0.0, dx=0.0: tuple(v+(dx if i == 0 else 0.0) for i, v in enumerate(stn.world(s, a, rho, phi)))
    return [('CAM_STN_CONTEXT', W(118, 34, math.radians(110), -30), W(30, 0, 0, -6), 30.0),
            ('CAM_STN_PLATFORM', W(hc-R-4.5, 3.5, -math.pi/2, px-11.0), W(49.5, 0, 0, -4.0), 24.0),
            ('CAM_STN_HEAD', W(15.5, 7.5, math.radians(145)), W(8.6), 30.0),
            ('CAM_STN_GAP', W(78, 0, 0, -46), W(24), 30.0)]
