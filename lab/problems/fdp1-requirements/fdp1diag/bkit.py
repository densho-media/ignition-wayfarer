"""Small Blender geometry kit for the FDP-1 requirements diagram: flat-shaded prisms, ribbons, arrows, text and
collections. Every element is a real object in the scene; nothing is drawn in a compositor or overlay.

Coordinates: the diagram lies in the world XY plane, seen from +Z. Panel code works in panel-local units
(px to the right, py downward from the panel's top-left corner) and converts with Panel.w().
"""
import math
import textwrap

import bmesh
import bpy

# Functional colours (the owner's brief). Blender's Outliner offers 8 colour tags: cyan has no tag of its own and
# shares blue (COLOR_05) with propellant; structure grey is the untagged default.
PALETTE = {
    "fusion": ((1.00, 0.55, 0.10), "COLOR_02"),
    "exhaust": ((0.13, 0.83, 0.93), "COLOR_05"),
    "propellant": ((0.23, 0.44, 0.96), "COLOR_05"),
    "thermal": ((0.94, 0.25, 0.18), "COLOR_01"),
    "radiation": ((0.88, 0.25, 0.78), "COLOR_07"),
    "structure": ((0.60, 0.64, 0.68), "NONE"),
    "fiji": ((0.61, 0.42, 1.00), "COLOR_06"),
    "unresolved": ((1.00, 0.82, 0.12), "COLOR_03"),
    "verified": ((0.24, 0.86, 0.52), "COLOR_04"),
}
UI = {
    "bg": (0.035, 0.043, 0.055),
    "panel": (0.060, 0.072, 0.090),
    "panel_edge": (0.17, 0.20, 0.24),
    "grid": (0.13, 0.15, 0.18),
    "text": (0.91, 0.93, 0.95),
    "dim": (0.55, 0.59, 0.64),
    "faint": (0.34, 0.38, 0.43),
    "dark": (0.10, 0.12, 0.15),
}


def srgb_to_lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


class Kit:
    def __init__(self):
        self.mats = {}
        self.colls = {}
        self.font = None
        self.count = 0

    # materials ------------------------------------------------------------------------------------------------
    def mat(self, name, rgb, alpha=1.0, emit=0.0):
        key = (name, rgb, alpha, emit)
        if key in self.mats:
            return self.mats[key]
        m = bpy.data.materials.new(f"M_{name}")
        lin = srgb_to_lin(rgb)
        m.diffuse_color = (*lin, alpha)
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.55
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*lin, 1.0)
                bsdf.inputs["Emission Strength"].default_value = emit
            bsdf.inputs["Alpha"].default_value = alpha
        if alpha < 1.0:
            for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
                try:
                    setattr(m, attr, val)
                except (AttributeError, TypeError):
                    pass
        self.mats[key] = m
        return m

    def cat_mat(self, cat, shade=1.0, alpha=1.0, emit=0.0):
        rgb = PALETTE[cat][0]
        if shade != 1.0:
            rgb = mix(UI["panel"], rgb, shade) if shade < 1 else mix(rgb, (1, 1, 1), shade - 1)
        return self.mat(f"{cat}_{shade:.2f}_{alpha:.2f}", rgb, alpha, emit)

    def ui_mat(self, key, alpha=1.0):
        return self.mat(f"ui_{key}_{alpha:.2f}", UI[key], alpha)

    # collections ----------------------------------------------------------------------------------------------
    def coll(self, name, parent=None, tag="NONE"):
        if name in self.colls:
            return self.colls[name]
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
        c.color_tag = tag
        self.colls[name] = c
        return c

    # objects --------------------------------------------------------------------------------------------------
    def _link(self, name, data, mat, coll, props):
        self.count += 1
        o = bpy.data.objects.new(name, data)
        coll.objects.link(o)
        if mat is not None and hasattr(data, "materials"):
            data.materials.append(mat)
        for k, val in (props or {}).items():
            o[k] = val
        return o

    def mesh(self, name, verts, faces, mat, coll, props=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update()
        return self._link(name, me, mat, coll, props)

    def prism(self, name, pts, z0, z1, mat, coll, props=None):
        """Extrude a simple 2D polygon (world XY, counter-clockwise or not) between z0 and z1."""
        n = len(pts)
        verts = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
        faces = [list(range(n))[::-1], list(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, n + j, n + i])
        o = self.mesh(name, verts, faces, mat, coll, props)
        # consistent normals
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(o.data)
        bm.free()
        return o

    def rect(self, name, x0, y0, x1, y1, mat, coll, z0=0.0, z1=0.2, props=None):
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        return self.prism(name, [(xa, ya), (xb, ya), (xb, yb), (xa, yb)], z0, z1, mat, coll, props)

    def rrect(self, name, x0, y0, x1, y1, r, mat, coll, z0=0.0, z1=0.2, props=None, seg=4):
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        r = min(r, (xb - xa) / 2, (yb - ya) / 2)
        pts = []
        for cx, cy, a0 in ((xb - r, ya + r, -90), (xb - r, yb - r, 0), (xa + r, yb - r, 90), (xa + r, ya + r, 180)):
            for k in range(seg + 1):
                a = math.radians(a0 + 90 * k / seg)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return self.prism(name, pts, z0, z1, mat, coll, props)

    def frame(self, name, x0, y0, x1, y1, w, mat, coll, z0=0.0, z1=0.15, props=None, dashed=0.0):
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        if dashed:
            for i, (p, q) in enumerate((((xa, ya), (xb, ya)), ((xb, ya), (xb, yb)), ((xb, yb), (xa, yb)), ((xa, yb), (xa, ya)))):
                self.dashes(f"{name}_{i}", p, q, w, dashed, mat, coll, z0, z1, props)
            return
        self.rect(f"{name}_b", xa, ya, xb, ya + w, mat, coll, z0, z1, props)
        self.rect(f"{name}_t", xa, yb - w, xb, yb, mat, coll, z0, z1, props)
        self.rect(f"{name}_l", xa, ya, xa + w, yb, mat, coll, z0, z1, props)
        self.rect(f"{name}_r", xb - w, ya, xb, yb, mat, coll, z0, z1, props)

    def seg(self, name, p, q, w, mat, coll, z0=0.0, z1=0.15, props=None, ext=0.0):
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy) or 1e-9
        ux, uy = dx / L, dy / L
        nx, ny = -uy * w / 2, ux * w / 2
        p = (p[0] - ux * ext, p[1] - uy * ext)
        q = (q[0] + ux * ext, q[1] + uy * ext)
        pts = [(p[0] + nx, p[1] + ny), (p[0] - nx, p[1] - ny), (q[0] - nx, q[1] - ny), (q[0] + nx, q[1] + ny)]
        return self.prism(name, pts, z0, z1, mat, coll, props)

    def polyline(self, name, pts, w, mat, coll, z0=0.0, z1=0.15, props=None):
        """One mesh: a ribbon along pts with mitred joins."""
        n = len(pts)
        left, right = [], []
        for i in range(n):
            if i == 0:
                d = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
            elif i == n - 1:
                d = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
            else:
                a = (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
                b = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                la, lb = math.hypot(*a) or 1, math.hypot(*b) or 1
                d = (a[0] / la + b[0] / lb, a[1] / la + b[1] / lb)
            L = math.hypot(*d) or 1
            nx, ny = -d[1] / L, d[0] / L
            scale = 1.0
            if 0 < i < n - 1:
                a = (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
                la = math.hypot(*a) or 1
                cosang = (nx * (-a[1] / la) + ny * (a[0] / la))
                scale = 1 / max(cosang, 0.3)
            hw = w / 2 * scale
            left.append((pts[i][0] + nx * hw, pts[i][1] + ny * hw))
            right.append((pts[i][0] - nx * hw, pts[i][1] - ny * hw))
        verts = []
        for z in (z0, z1):
            verts += [(x, y, z) for x, y in left] + [(x, y, z) for x, y in right]
        faces = []
        N = 2 * n
        for i in range(n - 1):
            l0, l1, r0, r1 = i, i + 1, n + i, n + i + 1
            faces.append([l0, r0, r1, l1])                          # bottom
            faces.append([N + l0, N + l1, N + r1, N + r0])          # top
            faces.append([l0, l1, N + l1, N + l0])
            faces.append([r0, N + r0, N + r1, r1])
        faces.append([0, N, N + n, n])
        faces.append([n - 1, n - 1 + n, N + n - 1 + n, N + n - 1])
        return self.mesh(name, verts, faces, mat, coll, props)

    def arrow(self, name, pts, w, mat, coll, z0=0.0, z1=0.2, props=None, head=None, head_len=None):
        """Ribbon along pts ending in a triangular head. w is the shaft width (a measured magnitude where stated)."""
        hw = head if head is not None else max(w * 2.0, w + 0.9)
        hl = head_len if head_len is not None else max(hw * 0.9, 1.0)
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        L = math.hypot(xb - xa, yb - ya) or 1e-9
        ux, uy = (xb - xa) / L, (yb - ya) / L
        base = (xb - ux * hl, yb - uy * hl)
        shaft = list(pts[:-1]) + [base]
        if math.hypot(base[0] - shaft[-2][0], base[1] - shaft[-2][1]) > 1e-6:
            self.polyline(name, shaft, w, mat, coll, z0, z1, props)
        nx, ny = -uy, ux
        tri = [(base[0] + nx * hw / 2, base[1] + ny * hw / 2), (xb, yb), (base[0] - nx * hw / 2, base[1] - ny * hw / 2)]
        return self.prism(f"{name}_head", tri, z0, z1, mat, coll, props)

    def dashes(self, name, p, q, w, dash, mat, coll, z0=0.0, z1=0.12, props=None, gap=None):
        gap = dash * 0.8 if gap is None else gap
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        if L < 1e-9:
            return
        ux, uy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
        verts, faces = [], []
        s = 0.0
        nx, ny = -uy * w / 2, ux * w / 2
        while s < L:
            e = min(s + dash, L)
            a = (p[0] + ux * s, p[1] + uy * s)
            b = (p[0] + ux * e, p[1] + uy * e)
            k = len(verts)
            quad = [(a[0] + nx, a[1] + ny), (a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), (b[0] + nx, b[1] + ny)]
            verts += [(x, y, z0) for x, y in quad] + [(x, y, z1) for x, y in quad]
            faces += [[k + 3, k + 2, k + 1, k], [k + 4, k + 5, k + 6, k + 7], [k, k + 1, k + 5, k + 4],
                      [k + 1, k + 2, k + 6, k + 5], [k + 2, k + 3, k + 7, k + 6], [k + 3, k, k + 4, k + 7]]
            s = e + gap
        return self.mesh(name, verts, faces, mat, coll, props)

    def disc(self, name, cx, cy, r, mat, coll, z0=0.0, z1=0.2, props=None, n=40):
        pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        return self.prism(name, pts, z0, z1, mat, coll, props)

    def ring2d(self, name, cx, cy, r, w, mat, coll, z0=0.0, z1=0.15, props=None, n=48):
        pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
        return self.polyline(name, pts, w, mat, coll, z0, z1, props)

    # true 3D primitives (schematic) -------------------------------------------------------------------------------
    def _bm_obj(self, name, bm, mat, coll, props):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        return self._link(name, me, mat, coll, props)

    def cylinder_x(self, name, x0, x1, cy, cz, r, mat, coll, props=None, r2=None, seg=32):
        """Cylinder (or cone frustum) whose axis runs along world X."""
        bm = bmesh.new()
        L = abs(x1 - x0)
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2,
                              depth=L)
        # cone axis is Z: rotate to X (Z -> +X)
        import mathutils
        rot = mathutils.Matrix.Rotation(math.radians(90), 4, "Y")
        bmesh.ops.transform(bm, matrix=rot, verts=bm.verts)
        bmesh.ops.translate(bm, vec=((x0 + x1) / 2, cy, cz), verts=bm.verts)
        return self._bm_obj(name, bm, mat, coll, props)

    def sphere(self, name, c, r, mat, coll, props=None):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=r)
        bmesh.ops.translate(bm, vec=c, verts=bm.verts)
        return self._bm_obj(name, bm, mat, coll, props)

    def torus_x(self, name, cx, cy, cz, R, r, mat, coll, props=None, seg=96, rseg=10, arc=None):
        """Torus with its axis along world X (a loop seen edge-on from +Z). arc=(a0, a1) degrees draws a band."""
        a0, a1 = arc if arc else (0.0, 360.0)
        closed = arc is None
        nseg = seg if closed else max(4, int(seg * (a1 - a0) / 360.0))
        verts, faces = [], []
        for i in range(nseg + (0 if closed else 1)):
            u = math.radians(a0 + (a1 - a0) * i / nseg)
            for j in range(rseg):
                v = 2 * math.pi * j / rseg
                rr = R + r * math.cos(v)
                verts.append((cx + r * math.sin(v), cy + rr * math.cos(u), cz + rr * math.sin(u)))
        rows = nseg if closed else nseg
        for i in range(rows):
            i2 = (i + 1) % nseg if closed else i + 1
            for j in range(rseg):
                j2 = (j + 1) % rseg
                faces.append([i * rseg + j, i2 * rseg + j, i2 * rseg + j2, i * rseg + j2])
        return self.mesh(name, verts, faces, mat, coll, props)

    # text -----------------------------------------------------------------------------------------------------
    def text(self, name, body, x, y, size, mat, coll, align="LEFT", valign="TOP", z=0.6, props=None, line=1.18,
             extrude=0.0):
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        cu.size = size
        cu.align_x = align
        cu.align_y = valign
        cu.space_line = line
        cu.extrude = extrude
        if self.font:
            cu.font = self.font
        o = self._link(name, cu, mat, coll, props)
        o.location = (x, y, z)
        return o


def wrap(s, chars):
    out = []
    for para in s.split("\n"):
        out += textwrap.wrap(para, chars) or [""]
    return out


def text_w(s, size):
    """Rough rendered width of a single line in Inter (average advance ~0.53 em)."""
    return len(s) * size * 0.53


# ---------------------------------------------------------------------------------------------------------------
# 3D helpers for the spatial model (build_spatial.py). All take world coordinates (x, y, z).
def _kit_box(self, name, lo, hi, mat, coll, props=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = (hi[0] - lo[0]), (hi[1] - lo[1]), (hi[2] - lo[2])
    for v in bm.verts:
        v.co.x = lo[0] + (v.co.x + 0.5) * sx
        v.co.y = lo[1] + (v.co.y + 0.5) * sy
        v.co.z = lo[2] + (v.co.z + 0.5) * sz
    return self._bm_obj(name, bm, mat, coll, props)


def _kit_ball(self, name, c, r, mat, coll, props=None, u=48, v=24, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    if smooth:
        for f in bm.faces:
            f.smooth = True
    return self._bm_obj(name, bm, mat, coll, props)


def _cone_verts(p, q, r0, r1, seg):
    import mathutils
    p, q = mathutils.Vector(p), mathutils.Vector(q)
    d = q - p
    L = d.length or 1e-9
    rot = d.normalized().to_track_quat("Z", "Y").to_matrix()
    ring = []
    for z, r in ((0.0, r0), (L, r1)):
        ring.append([p + rot @ mathutils.Vector((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z))
                     for k in range(seg)])
    return ring


def _kit_cones(self, name, items, mat, coll, props=None, seg=12, smooth=False):
    """One mesh of capped cone frusta, items = [(p, q, r0, r1), ...]."""
    verts, faces = [], []
    for p, q, r0, r1 in items:
        a, b = _cone_verts(p, q, r0, r1, seg)
        k = len(verts)
        verts += [tuple(v) for v in a] + [tuple(v) for v in b]
        for i in range(seg):
            j = (i + 1) % seg
            faces.append([k + i, k + j, k + seg + j, k + seg + i])
        faces.append([k + i for i in range(seg)][::-1])
        faces.append([k + seg + i for i in range(seg)])
    o = self.mesh(name, verts, faces, mat, coll, props)
    if smooth:
        for poly in o.data.polygons:
            poly.use_smooth = len(poly.vertices) == 4
    return o


def _kit_tube(self, name, pts, r, mat, coll, props=None, res=4):
    """A round tube along a 3D polyline (curve object with bevel)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
    return self._link(name, cu, mat, coll, props)


def _kit_ring(self, name, c, axis, R, r, mat, coll, props=None, seg=96, rseg=10):
    """Torus of major radius R around axis 'X', 'Y' or 'Z' at centre c."""
    verts, faces = [], []
    for i in range(seg):
        u = 2 * math.pi * i / seg
        for j in range(rseg):
            v = 2 * math.pi * j / rseg
            rr = R + r * math.cos(v)
            a, b, h = rr * math.cos(u), rr * math.sin(u), r * math.sin(v)
            if axis == "X":
                p = (c[0] + h, c[1] + a, c[2] + b)
            elif axis == "Y":
                p = (c[0] + a, c[1] + h, c[2] + b)
            else:
                p = (c[0] + a, c[1] + b, c[2] + h)
            verts.append(p)
    for i in range(seg):
        i2 = (i + 1) % seg
        for j in range(rseg):
            j2 = (j + 1) % rseg
            faces.append([i * rseg + j, i2 * rseg + j, i2 * rseg + j2, i * rseg + j2])
    o = self.mesh(name, verts, faces, mat, coll, props)
    for poly in o.data.polygons:
        poly.use_smooth = True
    return o


def _kit_quad(self, name, corners, mat, coll, props=None, thick=0.0):
    """A flat plate through 4 corner points (optionally given thickness along its normal)."""
    import mathutils
    vs = [mathutils.Vector(c) for c in corners]
    if not thick:
        return self.mesh(name, [tuple(v) for v in vs], [[0, 1, 2, 3]], mat, coll, props)
    n = (vs[1] - vs[0]).cross(vs[3] - vs[0]).normalized() * thick
    verts = [tuple(v) for v in vs] + [tuple(v + n) for v in vs]
    faces = [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return self.mesh(name, verts, faces, mat, coll, props)


Kit.box = _kit_box
Kit.ball = _kit_ball
Kit.cones = _kit_cones
Kit.tube = _kit_tube
Kit.ring = _kit_ring
Kit.quad = _kit_quad
