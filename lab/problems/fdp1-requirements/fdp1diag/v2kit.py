"""Self-contained Blender mesh kit for FDP-1 Spatial Systems V2 (bpy + math only, so it can also run inside the .blend
as an embedded text module). World units are metres; +X bow, +Z dorsal.

Every object gets semantic custom properties through `props`; information geometry is marked layer = 'information' and
physical hardware layer = 'physical'.
"""
import math

import bpy

PAL = {  # functional colours (sRGB): information palette of the phase-1/2 diagrams + Wayfarer hardware functions
    "fusion": (1.00, 0.55, 0.10), "exhaust": (0.13, 0.83, 0.93), "propellant": (0.23, 0.44, 0.96),
    "thermal": (0.94, 0.25, 0.18), "radiation": (0.88, 0.25, 0.78), "structure": (0.60, 0.64, 0.68),
    "fiji": (0.61, 0.42, 1.00), "unresolved": (1.00, 0.82, 0.12), "verified": (0.24, 0.86, 0.52),
    "infeasible": (1.00, 0.18, 0.22), "text": (0.92, 0.94, 0.96), "dim": (0.58, 0.62, 0.67),
    # physical hardware (muted so the information layer reads on top)
    "STRUCTURE": (0.52, 0.55, 0.58), "HABITAT": (0.45, 0.62, 0.48), "SHIELD": (0.50, 0.46, 0.52),
    "MAIN_PROPULSION": (0.62, 0.40, 0.36), "HOT_RADIATOR": (0.62, 0.34, 0.24), "WARM_RADIATOR": (0.46, 0.27, 0.24),
    "LOW_RADIATOR": (0.36, 0.40, 0.48), "POWER": (0.62, 0.56, 0.36), "SENSORS_COMMS": (0.40, 0.52, 0.62),
    "SERVICE": (0.58, 0.56, 0.44), "HELIUM3": (0.38, 0.48, 0.70), "DEUTERIUM": (0.34, 0.44, 0.62),
    "HYDROGEN": (0.40, 0.52, 0.66),
}
TAGS = {"fusion": "COLOR_02", "exhaust": "COLOR_05", "propellant": "COLOR_05", "thermal": "COLOR_01",
        "radiation": "COLOR_07", "fiji": "COLOR_06", "unresolved": "COLOR_03", "verified": "COLOR_04",
        "infeasible": "COLOR_01"}
_MATS = {}
VIEW = {"obj": None}


def lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def shade(rgb, k):
    return tuple(min(1.0, x * k) for x in rgb) if k >= 1 else tuple(x * k for x in rgb)


def mat(key, alpha=1.0, k=1.0, emit=0.0):
    name = f"V2_{key}_{alpha:.2f}_{k:.2f}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    rgb = shade(PAL.get(key, PAL["STRUCTURE"]), k)
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*lin(rgb), alpha)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*lin(rgb), 1)
        b.inputs["Alpha"].default_value = alpha
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (*lin(rgb), 1)
            b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            try:
                setattr(m, attr, val)
            except (AttributeError, TypeError):
                pass
    return m


def coll(name, parent=None, tag="NONE"):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    c.color_tag = tag
    return c


def obj(name, verts, faces, m, c, props=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    if m is not None:
        me.materials.append(m)
    for k, v in (props or {}).items():
        o[k] = v if isinstance(v, (int, float, str)) else str(v)
    return o


# ---- shapes ---------------------------------------------------------------------------------------------------
def rev(profile, a0=0.0, a1=360.0, step=2.0, centre=(0.0, 0.0)):
    """Solid of revolution about X from a closed (x, r) polygon."""
    full = abs(a1 - a0) >= 359.999
    rmax = max(r for _, r in profile) or 1.0
    n = max(12, min(160, int(abs(math.radians(a1 - a0)) * rmax / step)))
    m = len(profile)
    cols = n if full else n + 1
    vs, fs = [], []
    for i in range(cols):
        a = math.radians(a0 + (a1 - a0) * i / n)
        ca, sa = math.cos(a), math.sin(a)
        for x, r in profile:
            vs.append((x, centre[0] + r * ca, centre[1] + r * sa))
    for i in range(n):
        i2 = (i + 1) % cols if full else i + 1
        for j in range(m):
            j2 = (j + 1) % m
            fs.append([i * m + j, i * m + j2, i2 * m + j2, i2 * m + j])
    if not full:
        fs.append([j for j in range(m)][::-1])
        fs.append([n * m + j for j in range(m)])
    return vs, fs


def ring(x0, x1, r0, r1, arc=None, centre=(0.0, 0.0)):
    prof = [(x0, r0), (x1, r0), (x1, r1), (x0, r1)] if r0 > 0 else [(x0, 0.0), (x1, 0.0), (x1, r1), (x0, r1)]
    return rev(prof, *(arc or (0.0, 360.0)), centre=centre)


def frustum(x0, r0, x1, r1, ri0=None, ri1=None, arc=None, centre=(0.0, 0.0)):
    prof = [(x0, 0.0), (x1, 0.0), (x1, r1), (x0, r0)] if ri0 is None else [(x0, ri0), (x1, ri1), (x1, r1), (x0, r0)]
    return rev(prof, *(arc or (0.0, 360.0)), centre=centre)


def torus(x, R, a, arc=None, nv=10):
    prof = [(x + a * math.cos(2 * math.pi * j / nv), R + a * math.sin(2 * math.pi * j / nv)) for j in range(nv)]
    return rev(prof, *(arc or (0.0, 360.0)), step=max(2.0, R / 60))


def sphere(c, r, nu=48, nv=24):
    vs, fs = [], []
    for i in range(1, nv):
        th = math.pi * i / nv
        for j in range(nu):
            ph = 2 * math.pi * j / nu
            vs.append((c[0] + r * math.sin(th) * math.cos(ph), c[1] + r * math.sin(th) * math.sin(ph), c[2] + r * math.cos(th)))
    top, bot = len(vs), len(vs) + 1
    vs += [(c[0], c[1], c[2] + r), (c[0], c[1], c[2] - r)]
    for i in range(nv - 2):
        for j in range(nu):
            j2 = (j + 1) % nu
            fs.append([i * nu + j, i * nu + j2, (i + 1) * nu + j2, (i + 1) * nu + j])
    for j in range(nu):
        j2 = (j + 1) % nu
        fs.append([top, j2, j])
        fs.append([bot, (nv - 2) * nu + j, (nv - 2) * nu + j2])
    return vs, fs


def box(c, size, roll=0.0):
    dx, dy, dz = (s / 2 for s in size)
    ca, sa = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    vs = []
    for sx, sy, sz in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
        y, z = sy * dy, sz * dz
        vs.append((c[0] + sx * dx, c[1] + y * ca - z * sa, c[2] + y * sa + z * ca))
    fs = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return vs, fs


def panel(corners, t):
    p = corners
    u = [p[1][i] - p[0][i] for i in range(3)]
    v = [p[3][i] - p[0][i] for i in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    L = math.sqrt(sum(x * x for x in n)) or 1.0
    n = [x / L * t for x in n]
    vs = [tuple(q) for q in p] + [tuple(q[i] + n[i] for i in range(3)) for q in p]
    fs = [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return vs, fs


def _frame(d):
    L = math.sqrt(sum(x * x for x in d)) or 1.0
    d = [x / L for x in d]
    a = [0, 0, 1] if abs(d[2]) < 0.9 else [1, 0, 0]
    u = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]]
    Lu = math.sqrt(sum(x * x for x in u))
    u = [x / Lu for x in u]
    w = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
    return u, w


def tube(points, r, nv=10, r_end=None):
    """Swept circle along a polyline (radius tapering to r_end if given), capped."""
    n = len(points)
    vs, fs = [], []
    for i, p in enumerate(points):
        if i == 0:
            d = [points[1][k] - p[k] for k in range(3)]
        elif i == n - 1:
            d = [p[k] - points[i - 1][k] for k in range(3)]
        else:
            d = [points[i + 1][k] - points[i - 1][k] for k in range(3)]
        u, w = _frame(d)
        rr = r if r_end is None else r + (r_end - r) * i / (n - 1)
        for j in range(nv):
            a = 2 * math.pi * j / nv
            vs.append(tuple(p[k] + rr * (math.cos(a) * u[k] + math.sin(a) * w[k]) for k in range(3)))
    for i in range(n - 1):
        for j in range(nv):
            j2 = (j + 1) % nv
            fs.append([i * nv + j, i * nv + j2, (i + 1) * nv + j2, (i + 1) * nv + j])
    fs.append(list(range(nv))[::-1])
    fs.append([(n - 1) * nv + j for j in range(nv)])
    return vs, fs


def cones(items, nv=6):
    """Many straight tapered rods in one mesh: items = [(p, q, r0, r1)]."""
    vs, fs = [], []
    for p, q, r0, r1 in items:
        a, b = tube([p, q], r0, nv, r1)
        k = len(vs)
        vs += a
        fs += [[k + i for i in f] for f in b]
    return vs, fs


def capsule(x0, x1, r, centre):
    prof = [(x0, 0.0)]
    for k in range(1, 7):
        t = math.pi / 2 * k / 6
        prof.append((x0 + r * (1 - math.cos(t)), r * math.sin(t)))
    for k in reversed(range(0, 6)):
        t = math.pi / 2 * k / 6
        prof.append((x1 - r * (1 - math.cos(t)), r * math.sin(t)))
    prof.append((x1, 0.0))
    prof = [(x, max(rr, 1e-3)) for x, rr in prof]
    return rev(prof, centre=centre)


def wire_cube(c, s, r):
    h = s / 2
    P = [(c[0] + i * h, c[1] + j * h, c[2] + k * h) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if sum(abs(P[a][t] - P[b][t]) > 1e-9 for t in range(3)) == 1]
    return cones([(P[a], P[b], r, r) for a, b in edges], nv=4)


def bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append(tuple(a * p0[k] + b * p1[k] + c * p2[k] + d * p3[k] for k in range(3)))
    return out


def pol(x, r, az):
    a = math.radians(az)
    return (x, r * math.cos(a), r * math.sin(a))


# ---- text -----------------------------------------------------------------------------------------------------
def label(name, body, loc, size, key="text", c=None, align="CENTER", props=None, k=1.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    o = bpy.data.objects.new(name, cu)
    c.objects.link(o)
    cu.materials.append(mat(key, 1.0, k))
    o.location = loc
    if VIEW["obj"] is not None:
        con = o.constraints.new("COPY_ROTATION")
        con.target = VIEW["obj"]
    o["component"] = "label"
    for kk, v in (props or {}).items():
        o[kk] = v
    return o


def clear(c):
    for o in list(c.all_objects):
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
