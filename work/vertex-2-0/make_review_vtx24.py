"""Vertex 2.4: Halo Vertex 3D variant review file (work, noncanonical; owner choice 2026-11-16 18:35Z: about 7 kt research envelope).

  /snap/bin/blender -b work/vertex-1-8/REVIEW_VTX18.blend --python work/vertex-2-0/make_review_vtx24.py [-- --no-render]

Starts from the A+ review (the approved ship with the A+ engines in WORK_VTX18) and adds WORK_VTX24: the deployed Halo Vertex at the
2.5 all-lever closure (levers.json 'all_stretch': 6.9 kt, 33 TW, 0.072 c). Saves work/vertex-2-0/REVIEW_VTX24.blend (packed) and
Workbench previews in work/vertex-2-0/figures/. The file opens on the deployed state; press play for the deployment (stowed in the A+
housings, booms extend, rings unfurl by their own hoop force, burn).
Per engine: one REBCO ring (armoured face, neutron fin), burn point 2 R aft on the ring axis, ring canted 9 degrees inward, burn
station inside the shadow of its plug, three neighbour strips, a braced compression boom to the engine housing; bracing cables at 8
stations; repulsion ties between rings; translucent envelopes for the plume and the forward-escape stream. Visual thicknesses of
cables and envelopes are exaggerated for legibility (noted in the labels); dimensions of rings, booms and positions follow the ledger.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
RENDER = '--no-render' not in sys.argv
L = json.loads((HERE/'levers.json').read_text())['results']['all_stretch']['result']
D = L['detail']
R = D['R_m']; Z0 = D['z0_R']*R; A_CL = D['cluster_radius_m']; SEP = D['separation_m']; FIN = D['fin_t_m']; FACE = D['face_m']
CANT = math.radians(9.0); S_STRIP = D['cross']['strip_distance_m']; T_SHIP = D['ship_shield_t_m']
HOUSINGS = [(-153.39, 17.43, 17.43), (-153.39, -17.43, 17.43), (-153.39, 17.43, -17.43), (-153.39, -17.43, -17.43)]
X_AFT = -165.0
F_STOW, F_BOOM, F_RING, F_BURN, F_END = 1, 48, 240, 300, 360
PINK = 'COLOR_07'


def mat(name, rgba, emit=0.0, alpha=1.0, metal=0.0, rough=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (rgba[0], rgba[1], rgba[2], alpha); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgba[:3], 1.0); b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*rgba[:3], 1.0); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            m.blend_method = 'BLEND'
    return m


M = dict(armour=mat('VTX24_TUNGSTEN_ARMOUR', (0.35, 0.33, 0.31), metal=0.9, rough=0.35),
         fin=mat('VTX24_LIH_W_FIN', (0.55, 0.56, 0.58), rough=0.7),
         boom=mat('VTX24_CFRP_BOOM', (0.08, 0.08, 0.09), rough=0.4),
         cable=mat('VTX24_CNT_CABLE', (0.85, 0.82, 0.7), rough=0.6),
         station=mat('VTX24_BURN_STATION', (0.75, 0.62, 0.2), metal=0.5),
         plug=mat('VTX24_SHADOW_PLUG', (0.4, 0.42, 0.46), rough=0.8),
         plume=mat('VTX24_PLUME_ENVELOPE', (0.25, 0.6, 1.0), emit=0.4, alpha=0.05),
         fwd=mat('VTX24_FORWARD_STREAM', (1.0, 0.45, 0.15), emit=0.6, alpha=0.10),
         burn=mat('VTX24_BURN_POINT', (0.7, 0.85, 1.0), emit=40.0),
         text=mat('VTX24_LABEL', (1.0, 0.85, 0.95), emit=3.0))


def coll(name, parent):
    c = bpy.data.collections.new(name); parent.children.link(c); c.color_tag = PINK
    return c


def obj(name, data, c, m=None):
    o = bpy.data.objects.new(name, data); c.objects.link(o)
    if m is not None and data is not None:
        data.materials.append(m)
    o['wf_owner'] = 'work.vertex-2-4'; o['wf_status'] = 'NONCANONICAL_RESEARCH_VARIANT'
    return o


def mesh_from(name, vs, fs):
    d = bpy.data.meshes.new(name); d.from_pydata(vs, [], fs); d.update()
    return d


def torus(name, Rm, r, n=192, m=10):
    vs = []; fs = []
    for i in range(n):
        a = 2*math.pi*i/n
        for j in range(m):
            b = 2*math.pi*j/m
            vs.append(((Rm+r*math.cos(b))*math.cos(a), (Rm+r*math.cos(b))*math.sin(a), r*math.sin(b)))
    for i in range(n):
        for j in range(m):
            fs.append((i*m+j, ((i+1) % n)*m+j, ((i+1) % n)*m+(j+1) % m, i*m+(j+1) % m))
    return mesh_from(name, vs, fs)


def annulus(name, r0, r1, h, n=192):
    vs = []; fs = []
    for i in range(n):
        a = 2*math.pi*i/n; c, s = math.cos(a), math.sin(a)
        vs += [(r0*c, r0*s, -h/2), (r1*c, r1*s, -h/2), (r1*c, r1*s, h/2), (r0*c, r0*s, h/2)]
    for i in range(n):
        k, q = 4*i, 4*((i+1) % n)
        for j in range(4):
            fs.append((k+j, k+(j+1) % 4, q+(j+1) % 4, q+j))
    return mesh_from(name, vs, fs)


def cylinder(name, r, h, n=24, cap=True):
    """Along +Z from 0 to h."""
    vs = [(r*math.cos(2*math.pi*i/n), r*math.sin(2*math.pi*i/n), z) for z in (0.0, h) for i in range(n)]
    fs = [(i, (i+1) % n, n+(i+1) % n, n+i) for i in range(n)]
    if cap:
        fs += [tuple(range(n))[::-1], tuple(range(n, 2*n))]
    return mesh_from(name, vs, fs)


def cone(name, half, length, n=48):
    """Apex at origin, opening along +Z."""
    rr = length*math.tan(half)
    vs = [(0, 0, 0)]+[(rr*math.cos(2*math.pi*i/n), rr*math.sin(2*math.pi*i/n), length) for i in range(n)]
    fs = [(0, 1+(i+1) % n, 1+i) for i in range(n)]
    return mesh_from(name, vs, fs)


def truss(name, r, L, bay=50.0):
    """Triangular truss along +Z: three longerons and battens every `bay` metres (member radius 0.12 m)."""
    vs = []; fs = []

    def bar(p, q, rad=0.12, n=6):
        p, q = Vector(p), Vector(q); ax = (q-p).normalized(); t = ax.orthogonal().normalized(); u = ax.cross(t)
        base = len(vs)
        for z in (p, q):
            for i in range(n):
                a = 2*math.pi*i/n; vs.append(tuple(z+rad*(math.cos(a)*t+math.sin(a)*u)))
        for i in range(n):
            fs.append((base+i, base+(i+1) % n, base+n+(i+1) % n, base+n+i))
    corners = [(r*math.cos(2*math.pi*k/3), r*math.sin(2*math.pi*k/3)) for k in range(3)]
    for (x, y) in corners:
        bar((x, y, 0.0), (x, y, L), 0.18)
    nb = int(L//bay)
    for b in range(nb+1):
        z = min(b*bay, L)
        for k in range(3):
            (x0, y0), (x1, y1) = corners[k], corners[(k+1) % 3]
            bar((x0, y0, z), (x1, y1, z))
            if b < nb:
                bar((x0, y0, z), (x1, y1, min(z+bay, L)), 0.08)
    return mesh_from(name, vs, fs)


def look(o, target, up=Vector((0, 0, 1))):
    d = (Vector(target)-o.location).normalized()
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def align_z(direction):
    return Vector(direction).normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()


def text(name, body, loc, size, c, rot=None):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.align_x = 'LEFT'
    o = obj(name, cu, c, M['text']); o.location = loc
    o.rotation_euler = rot or (math.radians(90), 0, 0)
    return o


def key_scale(o, frames_values):
    for f, v in frames_values:
        o.scale = v; o.keyframe_insert('scale', frame=f)


def key_loc(o, frames_values):
    for f, v in frames_values:
        o.location = v; o.keyframe_insert('location', frame=f)


def build():
    sc = bpy.context.scene
    root = bpy.data.collections.new('WORK_VTX24'); sc.collection.children.link(root); root.color_tag = PINK
    cr = coll('WORK_VTX24_RINGS', root); cb = coll('WORK_VTX24_BOOMS_AND_FRAME', root); cs = coll('WORK_VTX24_SHIELDS_AND_STATIONS', root)
    ce = coll('WORK_VTX24_ENVELOPES', root); cl = coll('WORK_VTX24_LABELS', root)
    for nm in ('WORK_VTX18_HUD',):
        c = bpy.data.collections.get(nm)
        if c:
            c.hide_viewport = True; c.hide_render = True
    heads = []; centres = []; burns = []
    for k, h in enumerate(HOUSINGS):
        u = Vector((0, h[1], h[2])).normalized()                         # radial direction of this engine
        centre = Vector((X_AFT-SEP, 0, 0))+A_CL*u
        ax = Vector((-math.cos(CANT), 0, 0))-math.sin(CANT)*u            # exhaust direction: aft, leaning inward
        burn = centre+Z0*ax; centres.append(centre); burns.append(burn)
        tilt = align_z(ax)
        # ring group, parented to a head empty that rides the boom tip
        head = bpy.data.objects.new(f'VTX24_E{k+1}_HEAD', None); cr.objects.link(head); head.empty_display_size = 6
        inner = centre-R*u                                                # boom attaches at the inner rim
        key_loc(head, [(F_STOW, Vector(h)), (F_BOOM, Vector(h)), (F_RING, inner)])
        grp = bpy.data.objects.new(f'VTX24_E{k+1}_RING_FRAME', None); cr.objects.link(grp); grp.parent = head
        grp.matrix_parent_inverse = Matrix.Identity(4); grp.rotation_euler = tilt.to_euler()
        key_loc(grp, [(F_STOW, Vector((0, 0, 0))), (F_RING, Vector((0, 0, 0))), (F_BURN, R*u)])
        key_scale(grp, [(F_STOW, (0.02,)*3), (F_RING, (0.02,)*3), (F_BURN, (1, 1, 1))])
        ring = obj(f'VTX24_E{k+1}_RING_ARMOUR_FACE', torus(f'VTX24_E{k+1}_RING', R, max(FACE, 0.3)), cr, M['armour']); ring.parent = grp
        fin = obj(f'VTX24_E{k+1}_NEUTRON_FIN', annulus(f'VTX24_E{k+1}_FIN', R+0.3, R+0.3+FIN, FACE), cr, M['fin']); fin.parent = grp
        # burn point, station and shadow plug (in the ring frame: burn on +Z at Z0)
        bp = obj(f'VTX24_E{k+1}_BURN_POINT', cylinder('bp', 1.2, 2.4, 16), ce, M['burn']); bp.parent = grp; bp.location = (0, 0, Z0-1.2)
        key_scale(bp, [(F_STOW, (0, 0, 0)), (F_BURN, (0, 0, 0)), (F_BURN+12, (1, 1, 1))])
        to_ship = (Vector((X_AFT, 0, 0))-burn).normalized()
        plug_pos = burn+S_STRIP*to_ship
        plug = obj(f'VTX24_E{k+1}_SHIP_SHADOW_PLUG', cylinder('plug', 1.4, T_SHIP, 32), cs, M['plug'])
        plug.matrix_world = Matrix.Translation(plug_pos)@align_z(to_ship)
        st = obj(f'VTX24_E{k+1}_BURN_STATION', cylinder('st', 2.0, 4.0, 24), cs, M['station'])
        st.matrix_world = Matrix.Translation(plug_pos+(T_SHIP+1.0)*to_ship)@align_z(to_ship)
        heads.append((head, inner, Vector(h), plug, st))
    # neighbour strips: near each burn toward the three other rings (thin plates, 0.49 m thick)
    for k, b in enumerate(burns):
        for j, c in enumerate(centres):
            if j == k:
                continue
            d = (c-b).normalized(); pos = b+S_STRIP*d
            area = D['cross']['strip_area_m2_per_burn']/3; side = math.sqrt(area)
            pl = obj(f'VTX24_E{k+1}_STRIP_TO_E{j+1}', cylinder('strip', side/2, D['cross']['strip_thickness_m'], 4), cs, M['plug'])
            pl.matrix_world = Matrix.Translation(pos)@align_z(d)
            key_scale(pl, [(F_STOW, (0, 0, 0)), (F_RING, (0, 0, 0)), (F_BURN, (1, 1, 1))])
    # envelopes: plume (aft, 25 deg) and forward escape stream (15 deg, toward the ship side but leaning outward)
    for k, (b, c) in enumerate(zip(burns, centres)):
        ax = (b-c).normalized()
        pl = obj(f'VTX24_E{k+1}_PLUME_ENVELOPE', cone('plume', math.radians(25), 450.0), ce, M['plume']); pl.matrix_world = Matrix.Translation(b)@align_z(ax)
        fw = obj(f'VTX24_E{k+1}_FORWARD_STREAM', cone('fwd', math.radians(D['forward_stream']['stream_half_angle_deg']), 450.0), ce, M['fwd'])
        fw.matrix_world = Matrix.Translation(b)@align_z(-ax)
        for o in (pl, fw):
            o.hide_viewport = False; o.keyframe_insert('scale', frame=F_STOW)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=F_STOW); o.keyframe_insert('scale', frame=F_BURN)
            o.scale = (1, 1, 1); o.keyframe_insert('scale', frame=F_BURN+24)
    # booms: housing to inner rim, scaled out along their axis
    tips = []
    for k, (head, inner, h, plug, st) in enumerate(heads):
        d = inner-h; Lb = d.length
        bm = obj(f'VTX24_E{k+1}_COMPRESSION_BOOM', truss(f'VTX24_E{k+1}_BOOM', 4.0, Lb), cb, M['boom'])
        bm.matrix_world = Matrix.Translation(h)@align_z(d)
        key_scale(bm, [(F_STOW, (0.001, 0.001, 0.001)), (F_BOOM, (0.05, 0.05, 0.002)), (F_BOOM+12, (1, 1, 0.004)), (F_RING, (1, 1, 1))])
        tips.append((h, inner))
        for o in (plug, st):                                              # plug and station appear with the ring
            key_scale(o, [(F_STOW, (0, 0, 0)), (F_RING, (0, 0, 0)), (F_BURN, (1, 1, 1))])
    # bracing cables between neighbouring booms at 8 stations; repulsion ties between neighbouring rings
    order = [0, 1, 3, 2]
    for sta in range(1, 9):
        f = sta/8.0
        for i in range(4):
            a, b = order[i], order[(i+1) % 4]
            pa = tips[a][0].lerp(tips[a][1], f); pb = tips[b][0].lerp(tips[b][1], f); d = pb-pa
            cbl = obj(f'VTX24_BRACE_S{sta}_E{a+1}_E{b+1}', cylinder('brace', 0.25, d.length, 6, cap=False), cb, M['cable'])
            cbl.matrix_world = Matrix.Translation(pa)@align_z(d)
            key_scale(cbl, [(F_STOW, (0, 0, 0)), (F_RING, (0, 0, 0)), (F_RING+20, (1, 1, 1))])
    for i in range(4):
        a, b = order[i], order[(i+1) % 4]
        pa, pb = centres[a], centres[b]; d = pb-pa; u = d.normalized()
        pa2 = pa+R*u; d2 = (pb-R*u)-pa2
        t = obj(f'VTX24_TIE_E{a+1}_E{b+1}', cylinder('tie', 0.25, d2.length, 6, cap=False), cb, M['cable'])
        t.matrix_world = Matrix.Translation(pa2)@align_z(d2)
        key_scale(t, [(F_STOW, (0, 0, 0)), (F_BURN, (0, 0, 0)), (F_BURN+20, (1, 1, 1))])
    # labels
    xm = X_AFT-SEP/2
    lines = ['HALO VERTEX 2.4  research variant, NONCANONICAL (~7 kt envelope)',
             f"departure {L['departure_t']:.0f} t   He-3 {L['he3_t']:.0f} t   {L['fusion_TW']:.1f} TW   exhaust {L['ve_c']:.3f} c   trip +{L['trip_extra_yr']:.1f} yr",
             f"ring R {R:.1f} m, {D['I_MA']:.1f} MA, {D['B0_T']:.2f} T   burn {Z0:.0f} m aft of ring   cant 9 deg inward   pulses {D['rate_Hz']/1e3:.1f} kHz",
             f"booms {SEP/1000:.0f} km, compression, braced at 8 stations   cluster radius {A_CL:.0f} m   leakage {D['leak']:.1e}",
             'cables and envelopes drawn thicker than real for legibility']
    for i, ln in enumerate(lines):
        text(f'VTX24_LABEL_{i}', ln, (xm-900, -A_CL-250, A_CL+420-i*48), 32 if i == 0 else 24, cl)
    sc.frame_start = F_STOW; sc.frame_end = F_END; sc.frame_set(F_END)
    return centres, burns


def cameras(centres, burns):
    sc = bpy.context.scene; c30 = bpy.data.collections.get('30_CAMERAS') or sc.collection
    out = {}
    for name, loc, tgt, lens in (('CAM_VTX24_DEPLOYED', (X_AFT-1100, -3600, 1500), (X_AFT-1000, 0, 0), 30),
                                 ('CAM_VTX24_CLUSTER', (X_AFT-SEP+700, -1100, 700), (X_AFT-SEP-60, 0, 0), 40),
                                 ('CAM_VTX24_RING', tuple(centres[1]+Vector((260, -320, 160))), tuple((centres[1]+burns[1])/2), 35),
                                 ('CAM_VTX24_STOWED', (-40, -150, 70), (-150, 0, 0), 35)):
        cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.5; cd.clip_end = 20000
        o = bpy.data.objects.new(name, cd); c30.objects.link(o); o.location = loc; look(o, tgt); out[name] = o
    sc.camera = out['CAM_VTX24_DEPLOYED']
    c30.hide_viewport = False
    return out


def render(cams):
    sc = bpy.context.scene; figs = HERE/'figures'; figs.mkdir(exist_ok=True)
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_shadows = False; sc.display.shading.background_type = 'WORLD' if False else 'VIEWPORT'
    sc.render.resolution_x = 1600; sc.render.resolution_y = 900; sc.render.film_transparent = False
    for name, frame in (('CAM_VTX24_DEPLOYED', F_END), ('CAM_VTX24_CLUSTER', F_END), ('CAM_VTX24_RING', F_END), ('CAM_VTX24_STOWED', F_STOW)):
        sc.camera = cams[name]; sc.frame_set(frame)
        sc.render.filepath = str(figs/f'{name.lower()}.png'); bpy.ops.render.render(write_still=True)
    sc.camera = cams['CAM_VTX24_DEPLOYED']; sc.frame_set(F_END)


if __name__ == '__main__':
    centres, burns = build(); cams = cameras(centres, burns)
    if RENDER:
        render(cams)
    try:
        bpy.ops.file.pack_all()
    except Exception:
        pass
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'REVIEW_VTX24.blend'), compress=True)
    print('SAVED', HERE/'REVIEW_VTX24.blend')
