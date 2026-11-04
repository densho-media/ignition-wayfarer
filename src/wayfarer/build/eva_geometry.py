"""Mesh, material and measurement helpers shared by the EVA system generators (build/eva_suit.py, build/eva_drone.py, build/eva_scene.py)
and its checks (validation/eva_system.py). Blender only; no Wayfarer data is read here.

Every builder returns a new object linked to the scene collection; the caller files it with its own `put`. world_mesh_bvh / overlap /
overlap_names / plume_hits work on evaluated world-space meshes and record which object owns each BVH face (OWNERS).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

OWNERS = {}          # id(BVHTree) -> [object name per polygon]
KEEP_EXISTING = False  # True: mat() returns an existing WF_EVA_ material unchanged (scenes that append built assets)


# ---------------------------------------------------------------------------------------------------------------------- materials
# Functional viewport colour per system (Solid view, Object colour): the colour tells what a part does; render materials stay restrained.
SYSTEM = {'body': (0.78, 0.62, 0.52, 1), 'suit': (0.88, 0.88, 0.84, 1), 'frame': (0.16, 0.16, 0.18, 1), 'helmet': (0.42, 0.56, 0.72, 1),
          'life': (0.44, 0.62, 0.44, 1), 'suit_thr': (1.00, 0.56, 0.10, 1), 'n2': (0.12, 0.38, 0.95, 1), 'emergency': (0.90, 0.10, 0.08, 1),
          'dock': (0.98, 0.84, 0.08, 1), 'sensor': (0.08, 0.85, 0.90, 1), 'tether': (0.90, 0.10, 0.08, 1), 'tool': (0.55, 0.55, 0.52, 1),
          'rig': (0.50, 0.50, 0.50, 1), 'mark': (0.30, 0.40, 0.70, 1),
          'drone': (0.84, 0.84, 0.80, 1), 'drone_frame': (0.16, 0.16, 0.18, 1), 'drone_thr': (1.00, 0.56, 0.10, 1), 'arm': (0.58, 0.40, 0.80, 1),
          'efx': (0.55, 0.55, 0.52, 1), 'present': (0.40, 0.40, 0.40, 1), 'ref': (0.90, 0.90, 0.90, 1)}



def mat(name, rgb, rough=.5, metal=0.0, view=None, alpha=1.0, emit=0.0, coat=0.0, trans=0.0, ior=1.5, owner=None):
    """A Principled material WF_EVA_<name>; `view` is the Workbench (functional) colour, `rgb` the render colour."""
    m = bpy.data.materials.get(f'WF_EVA_{name}')
    if m is not None and KEEP_EXISTING:
        return m
    m = m or bpy.data.materials.new(f'WF_EVA_{name}')
    m.use_nodes = True; m.diffuse_color = (*(view or rgb), 1.0)
    if owner:
        m['wf_owner'] = owner
    bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (*rgb, 1); bs.inputs['Roughness'].default_value = rough; bs.inputs['Metallic'].default_value = metal
    if coat:
        bs.inputs['Coat Weight'].default_value = coat
    if trans:
        bs.inputs['Transmission Weight'].default_value = trans; bs.inputs['IOR'].default_value = ior
    if alpha < 1:
        bs.inputs['Alpha'].default_value = alpha; m.surface_render_method = 'BLENDED'
    if emit:
        bs.inputs['Emission Color'].default_value = (*rgb, 1); bs.inputs['Emission Strength'].default_value = emit
    return m


def fabric(m, scale=520.0, strength=.06):
    """A fine woven-textile bump (procedural, no image) on the Normal input only: the base colour stays a plain value for glTF."""
    nt = m.node_tree; bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    if bs.inputs['Normal'].is_linked:
        return m
    tc = nt.nodes.new('ShaderNodeTexCoord'); wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'DIAGONAL'
    wv.inputs['Scale'].default_value = scale; wv.inputs['Distortion'].default_value = 0.0
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = strength
    nt.links.new(tc.outputs['Object'], wv.inputs['Vector']); nt.links.new(wv.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], bs.inputs['Normal'])
    return m


def materials(pal, band_rgb, band_name='Band', owner=None):
    """Restrained render materials (matte textile outer, satin composite shells, graphite protective parts, dark flex zones, titanium
    interfaces); the role colour of the variant marks its bands and plate. PROTOTYPE colours until Art Style and Fashion define them."""
    S = SYSTEM; o = owner
    M = dict(
        shell=fabric(mat('Pressure_Garment_OffWhite', (.79, .78, .74), .74, 0.0, S['suit'][:3], owner=o)),
        fabric_grey=fabric(mat('Technical_Grey_Textile', (.50, .50, .48), .78, 0.0, S['suit'][:3], owner=o)),
        joint=fabric(mat('Flex_Joint_Dark', (.075, .078, .086), .82, 0.0, (.25, .25, .27), owner=o), 700, .10),
        glove=fabric(mat('Glove_Warm_Grey', (.46, .46, .44), .72, 0.0, S['suit'][:3], owner=o), 900, .05),
        grip=mat('Glove_Grip_Rubber', (.045, .045, .05), .9, owner=o),
        hut=mat('Torso_Composite_OffWhite', (.76, .745, .71), .46, 0.0, S['suit'][:3], coat=.25, owner=o),
        graphite=mat('Protective_Graphite', (.15, .155, .165), .48, .15, S['frame'][:3], coat=.15, owner=o),
        joint_hw=mat('Bearing_Anodised_Dark', (.10, .105, .115), .38, .7, (.25, .25, .27), owner=o),
        metal=mat('Interface_Titanium', (.56, .56, .57), .30, 1.0, owner=o), steel=mat('Fastener_Steel', (.52, .53, .54), .28, 1.0, owner=o),
        blue=mat('Accent_Muted_Blue', (.12, .21, .36), .55, 0.0, S['n2'][:3], owner=o),
        band=mat(f'Role_{band_name}', tuple(band_rgb), .6, 0.0, S['mark'][:3], owner=o),
        amber=mat('Propulsion_Amber', (.55, .33, .09), .45, .4, S['suit_thr'][:3], owner=o),
        nozzle=mat('Nozzle_Inconel', (.36, .35, .33), .32, 1.0, S['suit_thr'][:3], owner=o),
        visor=mat('Visor_Polycarbonate', (.90, .93, .95), .03, 0.0, S['helmet'][:3], trans=.96, ior=1.58, owner=o),
        visor_tint=mat('Sunshade_Gold', (.42, .32, .12), .12, 1.0, S['helmet'][:3], owner=o),
        lens=mat('Sensor_Lens', (.006, .008, .010), .04, 0.0, S['sensor'][:3], coat=1.0, owner=o),
        lens_light=mat('Light_Lens', (.42, .43, .43), .12, 0.0, S['sensor'][:3], owner=o),
        cyan=mat('Sensor_Cyan', (.06, .42, .46), .35, 0.0, S['sensor'][:3], emit=.4, owner=o),
        display=mat('Display_Glass', (.008, .014, .017), .10, 0.0, S['sensor'][:3], coat=.6, owner=o),
        copv=mat('COPV_Overwrap', (.18, .23, .32), .38, 0.0, S['n2'][:3], coat=.5, owner=o),
        n2line=mat('N2_Line_Stainless', (.50, .55, .62), .3, 1.0, S['n2'][:3], owner=o),
        red=mat('Emergency_Red', (.46, .07, .05), .5, 0.0, S['emergency'][:3], owner=o),
        orange=mat('Tether_Orange', (.70, .26, .05), .55, 0.0, S['tether'][:3], owner=o),
        yellow=mat('Dock_Marking_Yellow', (.60, .48, .10), .5, 0.0, S['dock'][:3], owner=o),
        dockmetal=mat('Dock_Hard_Anodised', (.30, .30, .29), .32, .9, S['dock'][:3], owner=o),
        rubber=mat('Bumper_Elastomer', (.035, .035, .04), .9, owner=o),
        text=mat('Marking_Dark', (.04, .04, .045), .6, owner=o), text_light=mat('Marking_Light', (.78, .78, .76), .6, owner=o),
        sole=mat('Boot_Sole', (.06, .06, .065), .85, owner=o),
        ls=mat('Life_Support_Internal', (.30, .36, .32), .5, .2, S['life'][:3], owner=o),
        lcvg=mat('LCVG', tuple(pal['lcvg']), .55, 0.0, S['life'][:3], owner=o),
        bladder=mat('Bladder', tuple(pal['bladder']), .5, 0.0, S['suit'][:3], owner=o))
    # the drone shares the suit's language: the same off-white composite and graphite, a darker bay floor and core, glossy-dark windows
    M.update(drone=M['hut'], drone_dark=mat('Drone_Core_Graphite', (.085, .088, .095), .42, .2, S['frame'][:3], coat=.2, owner=o),
             floor=mat('Studio_Floor', (.20, .205, .21), .6, owner=o), rail=mat('Prop_Rail_Grey', (.36, .37, .38), .45, .5, owner=o),
             hull=mat('Prop_Hull_Panel', (.55, .56, .57), .55, .3, owner=o), handrail=mat('Prop_Handrail_Yellow', (.62, .50, .10), .5, owner=o),
             ref=mat('Scale_Reference', (.9, .9, .9), .5, owner=o))
    M['worn'] = M['graphite']; M['boot'] = M['graphite']
    return M


def link(o):
    bpy.context.scene.collection.objects.link(o); return o


def mesh(name, verts, faces, m, smooth=True):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update(); me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    return link(bpy.data.objects.new(name, me))


def frame3(z, hint=Vector((0, 0, 1))):
    z = Vector(z).normalized(); x = Vector(hint).cross(z)
    if x.length < 1e-4:
        x = Vector((1, 0, 0)).cross(z)
    x.normalize(); return x, z.cross(x), z


def bx(name, c, half, m, axes=((1, 0, 0), (0, 1, 0), (0, 0, 1)), bevel=0.0):
    """A box; a live Bevel modifier (non-destructive) softens the edges."""
    ax = [Vector(a).normalized() for a in axes]; c = Vector(c); v = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                v.append(c+ax[0]*sx*half[0]+ax[1]*sy*half[1]+ax[2]*sz*half[2])
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    o = mesh(name, v, f, m, smooth=False)
    if bevel:
        b = o.modifiers.new('Bevel', 'BEVEL'); b.width = bevel; b.segments = 2; b.limit_method = 'ANGLE'; b.harden_normals = False
    return o


def lathe(name, origin, axis, profile, m, n=20, close_start=True, close_end=True, hint=Vector((0, 0, 1))):
    """Revolve a profile [(t along axis, r)] about axis: tubes, nozzles, bottles, knobs."""
    x, y, z = frame3(axis, hint); o0 = Vector(origin); v = []; f = []
    for t, r in profile:
        for i in range(n):
            a = 2*math.pi*i/n; v.append(o0+z*t+(x*math.cos(a)+y*math.sin(a))*r)
    k = len(profile)
    for j in range(k-1):
        f += [(j*n+i, j*n+(i+1) % n, (j+1)*n+(i+1) % n, (j+1)*n+i) for i in range(n)]
    if close_start and profile[0][1] > 0:
        f.append(tuple(reversed(range(n))))
    if close_end and profile[-1][1] > 0:
        f.append(tuple(range((k-1)*n, k*n)))
    return mesh(name, v, f, m)


def cyl(name, a, b, r, m, n=20, r_b=None):
    a, b = Vector(a), Vector(b); L = (b-a).length
    return lathe(name, a, b-a, [(0, r), (L, r if r_b is None else r_b)], m, n)


def capsule(name, a, b, r, m, n=32, rings=8):
    a, b = Vector(a), Vector(b); L = (b-a).length; prof = []
    prof = [(r-r*math.sin(math.pi/2*(1-k/rings)), r*math.cos(math.pi/2*(1-k/rings))) for k in range(rings+1)]
    prof += [(L-r+r*math.sin(math.pi/2*k/rings), r*math.cos(math.pi/2*k/rings)) for k in range(rings+1)]
    prof[0] = (0.0, 1e-4); prof[-1] = (L, 1e-4)
    return lathe(name, a, b-a, prof, m, n, False, False)


def tube_path(name, pts, r, m, n=10):
    """A pipe along a polyline with mitred corners (plumbing, cables)."""
    pts = [Vector(p) for p in pts]; v = []; f = []
    for i, p in enumerate(pts):
        d = (pts[min(i+1, len(pts)-1)]-pts[max(i-1, 0)]).normalized()
        x, y, z = frame3(d, Vector((0.37, 0.21, 0.9)))
        for k in range(n):
            a = 2*math.pi*k/n; v.append(p+(x*math.cos(a)+y*math.sin(a))*r)
    for i in range(len(pts)-1):
        f += [(i*n+k, i*n+(k+1) % n, (i+1)*n+(k+1) % n, (i+1)*n+k) for k in range(n)]
    f += [tuple(reversed(range(n))), tuple(range((len(pts)-1)*n, len(pts)*n))]
    return mesh(name, v, f, m)


def torus(name, c, axis, R, r, m, n=32, k=8):
    x, y, z = frame3(axis); c = Vector(c); v = []; f = []
    for i in range(n):
        a = 2*math.pi*i/n; d = x*math.cos(a)+y*math.sin(a)
        for j in range(k):
            b = 2*math.pi*j/k; v.append(c+d*R+(d*math.cos(b)+z*math.sin(b))*r)
    for i in range(n):
        for j in range(k):
            f.append((i*k+j, i*k+(j+1) % k, ((i+1) % n)*k+(j+1) % k, ((i+1) % n)*k+j))
    return mesh(name, v, f, m)


def text(name, s, c, right, normal, size, m, extrude=.0003):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = s; cu.size = size; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.extrude = extrude
    tmp = link(bpy.data.objects.new('tmp_text', cu)); bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get())); bpy.data.objects.remove(tmp); bpy.data.curves.remove(cu)
    r = Vector(right).normalized(); nrm = Vector(normal).normalized(); u = nrm.cross(r); c = Vector(c)
    me.transform(Matrix(((r.x, u.x, nrm.x, c.x), (r.y, u.y, nrm.y, c.y), (r.z, u.z, nrm.z, c.z), (0, 0, 0, 1))))
    me.materials.clear(); me.materials.append(m); me.name = name
    return link(bpy.data.objects.new(name, me))


def nozzle_mesh(name, pos, e, scale, M):
    """One cold-gas thruster: valve body behind the mounting face, throat, conical bell, an amber collar; plus an Empty at the exit
    whose +Z is the exhaust axis (the runtime thruster socket and the plume-check origin)."""
    s = scale; e = Vector(e); p = Vector(pos)
    body = lathe(name+'_Valve', p-e*0.018*s, e, [(0, .0075*s), (.012*s, .0075*s), (.016*s, .0045*s)], M['amber'], 16)
    bell = lathe(name+'_Bell', p-e*0.002*s, e, [(0, .0045*s), (.004*s, .0026*s), (.022*s, .0060*s), (.022*s, .0052*s), (.006*s, .0022*s)],
                 M['nozzle'], 16, True, False)
    em = link(bpy.data.objects.new(name, None)); em.empty_display_type = 'SINGLE_ARROW'; em.empty_display_size = .05
    x, y, z = frame3(e); em.matrix_world = Matrix((x, y, z)).transposed().to_4x4(); em.location = p+e*0.022*s
    return body, bell, em


# ---------------------------------------------------------------------------------------------------------------------- shapes
def sgnpow(c, p):
    return math.copysign(abs(c)**p, c)


def ring(z, a, bf, bb, yc, n, N=64):
    """A superellipse section: half-width a, front (-Y) and back (+Y) half-depths, centre yc, exponent n."""
    out = []
    for i in range(N):
        t = 2*math.pi*i/N; c, s = math.cos(t), math.sin(t)
        out.append(Vector((a*sgnpow(c, 2/n), yc+(bb if s > 0 else bf)*sgnpow(s, 2/n), z)))
    return out


def smooth3(xs):
    return [xs[0]]+[(xs[i-1]+2*xs[i]+xs[i+1])/4 for i in range(1, len(xs)-1)]+[xs[-1]]


def smoothstep(t):
    t = max(0.0, min(1.0, t)); return t*t*(3-2*t)


def grid_shell(name, us, vs, xz, y_front, y_back, m, weld=True):
    """A closed shell over a (u, v) grid: front surface y_front(x, z), back surface y_back(x, z, u, v), joined by a rim at the grid's
    boundary. xz(u, v) -> (x, z). Normals are recomputed outward."""
    nu, nv = len(us), len(vs); F = []; Bk = []
    for v in vs:
        for u in us:
            x, z = xz(u, v); F.append(Vector((x, y_front(x, z), z))); Bk.append(Vector((x, y_back(x, z, u, v), z)))
    verts = F+Bk; off = len(F); faces = []
    idx = lambda i, j: j*nu+i
    for j in range(nv-1):
        for i in range(nu-1):
            faces.append((idx(i, j), idx(i+1, j), idx(i+1, j+1), idx(i, j+1)))
            faces.append((off+idx(i, j), off+idx(i, j+1), off+idx(i+1, j+1), off+idx(i+1, j)))
    loop = [idx(i, 0) for i in range(nu)]+[idx(nu-1, j) for j in range(1, nv)]+[idx(i, nv-1) for i in range(nu-2, -1, -1)]+[idx(0, j) for j in range(nv-2, 0, -1)]
    for k in range(len(loop)):
        a, b = loop[k], loop[(k+1) % len(loop)]
        faces.append((a, off+a, off+b, b))
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    if weld:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    o = link(bpy.data.objects.new(name, me))
    return o


def boundary_loops(o, indices=False):
    """The open boundary loops of a mesh object (its data coordinates, which are world coordinates for the parts built here)."""
    me = o.data; ec = {}
    for p in me.polygons:
        vs = list(p.vertices)
        for e in zip(vs, vs[1:]+vs[:1]):
            k = tuple(sorted(e)); ec[k] = ec.get(k, 0)+1
    nbr = {}
    for (a, b), c in ec.items():
        if c == 1:
            nbr.setdefault(a, []).append(b); nbr.setdefault(b, []).append(a)
    seen = set(); loops = []
    for st in list(nbr):
        if st in seen:
            continue
        lp = [st]; seen.add(st); prev = None
        while True:
            nx = [q for q in nbr[lp[-1]] if q != prev and q not in seen]
            if not nx:
                break
            prev = lp[-1]; lp.append(nx[0]); seen.add(nx[0])
        if len(lp) > 8:
            loops.append(lp if indices else [me.vertices[q].co.copy() for q in lp])
    return loops


def smooth_loop(o, lp, it=8, w=.5):
    """Laplacian smoothing of one closed boundary loop of a grid-built mesh: removes the stair steps a per-face selection leaves."""
    co = o.data.vertices
    for _ in range(it):
        P_ = [co[q].co.copy() for q in lp]; n_ = len(P_)
        for k, q in enumerate(lp):
            co[q].co = P_[k]*(1-w)+(P_[k-1]+P_[(k+1) % n_])*(w/2)
    o.data.update()


def lin(a, b, n):
    return [a+(b-a)*k/(n-1) for k in range(n)]


def merged(*lists):
    return sorted(set(round(x, 6) for l in lists for x in l))

def world_mesh_bvh(objs, dg):
    verts = []; polys = []; owner = []
    for o in objs:
        if o.type not in ('MESH',) or o.hide_render:
            continue
        ev = o.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world; base = len(verts)
        verts += [mw @ v.co for v in me.vertices]; polys += [[base+i for i in p.vertices] for p in me.polygons]; owner += [o.name]*len(me.polygons)
        ev.to_mesh_clear()
    if not polys:
        return None
    t = BVHTree.FromPolygons(verts, polys); OWNERS[id(t)] = owner; return t


def overlap_names(a, b):
    if a is None or b is None:
        return {}
    out = {}
    for i, j in a.overlap(b):
        k = f'{OWNERS[id(a)][i]} x {OWNERS[id(b)][j]}'; out[k] = out.get(k, 0)+1
    return dict(sorted(out.items(), key=lambda kv: -kv[1])[:12])


def plume_hits(nozzles, blockers, dg, half_deg, length):
    """Rays along each nozzle axis and on a cone at the plume half-angle; a hit on any blocker (not the nozzle's own pod) is impingement."""
    out = {}
    for em in nozzles:
        mw = em.matrix_world; o = mw.translation; z = mw.col[2].xyz.normalized(); x = mw.col[0].xyz.normalized(); y = mw.col[1].xyz.normalized()
        dirs = [z]+[(z*math.cos(math.radians(half_deg))+(x*math.cos(a)+y*math.sin(a))*math.sin(math.radians(half_deg))).normalized() for a in
                    [2*math.pi*k/8 for k in range(8)]]
        tag = em.get('pod'); hits = []
        for name, bvh in blockers.items():
            if tag and name == tag:
                continue
            for d in dirs:
                h = bvh.ray_cast(o+d*.003, d, length)
                if h[0] is not None:
                    hits.append(dict(blocker=name, object=OWNERS[id(bvh)][h[2]], distance_m=round(h[3], 3))); break
        if hits:
            out[em.name] = hits
    return out


def simons_norm(theta_lim_deg, n=5.0):
    """Normalisation of the Simons far-field plume model, p(r, th) = F / (K r^2) cos^n(pi th / (2 th_lim)): the integral of the
    pressure over a sphere equals the thrust (n = 2 / (gamma - 1) = 5 for N2)."""
    tl = math.radians(theta_lim_deg); k = 0.0; N = 400
    for i in range(N):
        th = tl*(i+.5)/N; k += math.cos(math.pi*th/(2*tl))**n*math.cos(th)*2*math.pi*math.sin(th)*tl/N
    return k


def plume_envelope(nozzles, blockers, dg, thrust, core_deg, fringe_deg, length, theta_lim_deg=130.0, rings=5, az=16):
    """Conservative sampled 3D plume envelope: per nozzle, rays on the axis and on `rings` cones out to the fringe half-angle (`az`
    azimuths each), to `length`. Every first hit is reported with its cone angle, distance and a Simons-model impingement pressure
    (cold N2, n = 5, limiting angle theta_lim). Hits inside the core angle are core impingement. Not a flow solution: no reflection,
    no shadowing by the plume's own shock structure, no contamination transport."""
    K = simons_norm(theta_lim_deg); tl = math.radians(theta_lim_deg); out = {}
    angs = [0.0]+[fringe_deg*(k+1)/rings for k in range(rings)]
    for em in nozzles:
        mw = em.matrix_world; o = mw.translation; z = mw.col[2].xyz.normalized(); x = mw.col[0].xyz.normalized(); y = mw.col[1].xyz.normalized()
        tag = em.get('pod'); hits = {}
        for th in angs:
            t_ = math.radians(th)
            for a in ([0.0] if th == 0 else [2*math.pi*k/az for k in range(az)]):
                d = (z*math.cos(t_)+(x*math.cos(a)+y*math.sin(a))*math.sin(t_)).normalized(); best = None
                for name, bvh in blockers.items():
                    if bvh is None or (tag and name == tag):
                        continue
                    h = bvh.ray_cast(o+d*.003, d, length)
                    if h[0] is not None and (best is None or h[3] < best[3]):
                        best = (name, OWNERS[id(bvh)][h[2]], h[0], h[3])
                if best:
                    r_ = max(best[3], .02); pr = thrust/(K*r_*r_)*math.cos(min(math.pi/2, math.pi*t_/(2*tl)))**5
                    k_ = (best[0], best[1])
                    if k_ not in hits or pr > hits[k_]['pressure_pa']:
                        hits[k_] = dict(blocker=best[0], object=best[1], angle_deg=round(th, 1), distance_m=round(best[3], 3),
                                        pressure_pa=round(pr, 3), core=th <= core_deg)
        if hits:
            out[em.name] = sorted(hits.values(), key=lambda h: -h['pressure_pa'])
    return out


def overlap(a, b):
    if a is None or b is None:
        return 0
    return len(a.overlap(b))
