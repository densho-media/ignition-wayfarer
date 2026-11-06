"""P11 collision-protection geometry for FDP-1 Spatial Systems V3. Standard library only, no Blender.

The model covers geometric coverage only, the first of the brief's six protection categories. Stopping capability,
secondary ejecta, penetration, radiation and shock transmission, and mission survival probability are reported as
UNRESOLVED; nothing here computes them.

Model:
- Particles arrive from +X (opposite the velocity) inside a cone of half-angle theta about -X. theta = 0 is the
  idealized parallel stream.
- The shield silhouette S (a circle of radius R, or any polygon in the YZ plane) sits at x_s, the aft edge of the
  shield rim. A ray traced back from a ship point p, at L = x_s - p.x behind that plane, crosses the plane at
  p_yz + L tan(theta) u, for some unit vector u.
- p is therefore covered for every direction in the cone iff p_yz lies inside S eroded by L tan(theta). The protected
  volume is the intersection of the shield shadows over the cone.
- The clearance is the distance inside S, minus L tan(theta), minus the safety margin. A negative clearance is a
  protrusion.

Components are sampled on their surfaces. Each sample carries the projected (frontal, YZ) area it represents, so a
component's exposed frontal area is the sum over its exposed samples. Overlaps between components are not
deduplicated.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INPUTS = os.path.join(ROOT, "data", "protection_inputs.json")
GEOMETRY = os.path.join(ROOT, "data", "ship_geometry.json")

UNRESOLVED_CATEGORIES = [
    ("geometric coverage", "computed here"),
    ("shield stopping capability", "UNRESOLVED: shield stack, material and areal mass OPEN (OD-014)"),
    ("secondary ejecta and fragmentation", "UNRESOLVED: no ejecta model"),
    ("particle penetration", "UNRESOLVED: no dust mass/velocity spectrum or penetration equation in the record"),
    ("radiation and shock transmission", "UNRESOLVED"),
    ("mission survival probability", "UNRESOLVED: no collision environment model"),
]


def load_inputs(path=INPUTS):
    return json.load(open(path))


# ---- shield silhouettes -----------------------------------------------------------------------------------------
class Circle:
    kind = "circle"

    def __init__(self, R, cy=0.0, cz=0.0):
        self.R, self.cy, self.cz = R, cy, cz

    def inside_distance(self, y, z):
        """Signed distance to the boundary, positive inside."""
        return self.R - math.hypot(y - self.cy, z - self.cz)

    def area(self):
        return math.pi * self.R ** 2

    def outline(self, n=96):
        return [(self.cy + self.R * math.cos(2 * math.pi * i / n), self.cz + self.R * math.sin(2 * math.pi * i / n)) for i in range(n)]


class Polygon:
    kind = "polygon"

    def __init__(self, pts):
        self.pts = [tuple(p) for p in pts]

    def _inside(self, y, z):
        c, n = False, len(self.pts)
        for i in range(n):
            (y1, z1), (y2, z2) = self.pts[i], self.pts[(i + 1) % n]
            if (z1 > z) != (z2 > z) and y < (y2 - y1) * (z - z1) / (z2 - z1) + y1:
                c = not c
        return c

    def inside_distance(self, y, z):
        d = float("inf")
        n = len(self.pts)
        for i in range(n):
            (y1, z1), (y2, z2) = self.pts[i], self.pts[(i + 1) % n]
            dy, dz = y2 - y1, z2 - z1
            t = max(0.0, min(1.0, ((y - y1) * dy + (z - z1) * dz) / (dy * dy + dz * dz or 1.0)))
            d = min(d, math.hypot(y - y1 - t * dy, z - z1 - t * dz))
        return d if self._inside(y, z) else -d

    def area(self):
        n = len(self.pts)
        return abs(sum(self.pts[i][0] * self.pts[(i + 1) % n][1] - self.pts[(i + 1) % n][0] * self.pts[i][1] for i in range(n))) / 2

    def outline(self, n=None):
        return list(self.pts)


def shield_from_geometry(geo):
    sh = [p for p in geo["parts"] if p["group"] == "bow" and p["func"] == "SHIELD"]
    R = max(p["r1"] for p in sh)
    return {"silhouette": Circle(R), "radius_m": R, "diameter_m": 2 * R, "x_aft_m": min(p["x0"] for p in sh),
            "x_fwd_m": max(p["x1"] for p in sh), "parts": [p["name"] for p in sh],
            "thickness_display_m": max(p["x1"] for p in sh) - min(p["x0"] for p in sh)}


# ---- classification --------------------------------------------------------------------------------------------
def classify(p):
    g, n = p["group"], p["name"]
    if g == "superseded":
        return "EXCLUDED"
    if g == "bow":
        return "SHIELD"
    if g == "radiators" or "Wing" in n or "Low_Loop_Panel" in n:
        return "RADIATOR"
    if g == "fdp1_service":
        return "NON_CRITICAL"
    return "CRITICAL"


SYSTEM = {"hull": "hull and spine", "engineering": "power conversion (Wayfarer)", "habitat": "habitat rings",
          "storage": "fuel and propellant storage", "fdp1_tanks": "fuel and propellant storage", "fdp1_structure": "FDP-1 thrust structure",
          "fdp1_fuel_prep": "target factory and fuel interfaces", "fdp1_power": "pulsed power and feeds", "fdp1_drivers": "driver galleries",
          "fdp1_reaction": "reaction point", "fdp1_nozzle": "magnetic nozzle loops and Fiji lattice",
          "fdp1_shield": "shadow shield and loop armour", "fdp1_thermal": "thermal lines and wings", "fdp1_sensors": "burn diagnostics",
          "fdp1_service": "service hardware", "radiators": "Wayfarer radiators", "bow": "forward shield", "superseded": "superseded drive"}


# ---- surface samples: (x, y, z, projected_area_m2) -----------------------------------------------------------
def _disc_ring(x, cy, cz, r_in, r_out, h, arc=None):
    """Annulus facing +X, sampled in polar cells; each sample carries its cell's projected area."""
    out = []
    a0, a1 = (math.radians(arc[0]), math.radians(arc[1])) if arc else (0.0, 2 * math.pi)
    nr = max(1, int(math.ceil((r_out - r_in) / h)))
    for i in range(nr):
        ra, rb = r_in + (r_out - r_in) * i / nr, r_in + (r_out - r_in) * (i + 1) / nr
        rm = rb if i == nr - 1 else (ra + rb) / 2      # the outermost row sits on the edge
        na = max(8, int(math.ceil((a1 - a0) * rb / h)))
        dA = (a1 - a0) / na * (rb * rb - ra * ra) / 2
        for j in range(na):
            t = a0 + (a1 - a0) * (j + 0.5) / na
            out.append((x, cy + rm * math.cos(t), cz + rm * math.sin(t), dA))
    return out


def samples(p, h=0.5):
    s = p["shape"]
    if s in ("ring", "frustum"):
        cy, cz = p.get("centre", (0.0, 0.0))
        if s == "ring":
            r_out, r_in, xf = p["r1"], p.get("r0", 0.0), p["x1"]
        else:
            r_out, r_in = max(p["r0"], p["r1"]), min(p.get("ri0") or 0.0, p.get("ri1") or 0.0)
            xf = p["x1"] if p["r1"] >= p["r0"] else p["x0"]
        return _disc_ring(xf, cy, cz, r_in, r_out, h, p.get("arc"))
    if s == "torus":
        a = max(p["a"], 1e-3)
        return _disc_ring(p["x"] + a, 0.0, 0.0, max(p["R"] - a, 0.0), p["R"] + a, min(h, a), p.get("arc"))
    if s == "capsule":
        cy, cz = p["centre"]
        return _disc_ring(p["x1"] - p["radius"], cy, cz, 0.0, p["radius"], h)
    if s == "box":
        c, sz = p["centre"], p["size"]
        roll = math.radians(p.get("roll", 0.0))
        ny, nz = max(1, int(math.ceil(sz[1] / h))), max(1, int(math.ceil(sz[2] / h)))
        dA = sz[1] * sz[2] / (ny * nz)
        out = []
        for i in range(ny + 1):
            for j in range(nz + 1):
                u, v = -sz[1] / 2 + sz[1] * i / ny, -sz[2] / 2 + sz[2] * j / nz
                w = dA * (0.5 if i in (0, ny) else 1) * (0.5 if j in (0, nz) else 1)
                out.append((c[0] + sz[0] / 2, c[1] + u * math.cos(roll) - v * math.sin(roll), c[2] + u * math.sin(roll) + v * math.cos(roll), w))
        return out
    if s == "tube":
        r, pts, out = p["radius"], p["points"], []
        out.append((*pts[0], math.pi * r * r))           # end cap seen head-on
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            Lyz = math.hypot(b[1] - a[1], b[2] - a[2])
            n = max(1, int(math.ceil(L / h)))
            for k in range(n + 1):
                t = k / n
                q = [a[i] + (b[i] - a[i]) * t for i in range(3)]
                rr = math.hypot(q[1], q[2])
                # the sample stands for the tube's outer edge (radial offset r): the extreme a particle can reach
                if rr > 1e-9:
                    q[1], q[2] = q[1] * (rr + r) / rr, q[2] * (rr + r) / rr
                out.append((q[0], q[1], q[2], 2 * r * Lyz / (n + 1)))
        return out
    if s == "panel":
        c = p["corners"]
        u = [c[1][i] - c[0][i] for i in range(3)]
        v = [c[3][i] - c[0][i] for i in range(3)]
        Lu, Lv = math.sqrt(sum(x * x for x in u)), math.sqrt(sum(x * x for x in v))
        nvec = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        A = math.sqrt(sum(x * x for x in nvec))
        nx = abs(nvec[0]) / (A or 1)
        nu, nv = max(1, int(math.ceil(Lu / max(h, Lu / 400)))), max(1, int(math.ceil(Lv / max(h, Lv / 400))))
        dA = A / (nu * nv) * nx
        return [tuple(c[0][k] + u[k] * (i + 0.5) / nu + v[k] * (j + 0.5) / nv for k in range(3)) + (dA,)
                for i in range(nu) for j in range(nv)]
    raise ValueError(s)


# ---- the model ------------------------------------------------------------------------------------------------
class Protection:
    def __init__(self, geo=None, inputs=None, silhouette=None, x_shield=None):
        self.geo = geo or json.load(open(GEOMETRY))
        self.inp = inputs or load_inputs()
        sh = shield_from_geometry(self.geo)
        self.shield = sh
        self.sil = silhouette or sh["silhouette"]
        self.x_s = sh["x_aft_m"] if x_shield is None else x_shield
        self._cache = {}

    # clearance of one point
    def clearance(self, x, y, z, cone_deg=0.0, margin=0.0, sil=None, x_s=None):
        sil = sil or self.sil
        x_s = self.x_s if x_s is None else x_s
        L = max(x_s - x, 0.0)
        return sil.inside_distance(y, z) - L * math.tan(math.radians(cone_deg)) - margin

    def protected_radius(self, x, cone_deg=0.0, margin=0.0, R=None):
        """Circle shields: radius of the protected volume at station x (may be negative = no protected core)."""
        R = self.sil.R if R is None else R
        return R - max(self.x_s - x, 0.0) * math.tan(math.radians(cone_deg)) - margin

    def part_samples(self, p, h):
        k = (p["name"], h)
        if k not in self._cache:
            self._cache[k] = samples(p, h)
        return self._cache[k]

    def assess_part(self, p, cone_deg=0.0, margin=0.0, band=1.0, h=0.5, sil=None, x_s=None, radial_scale=1.0):
        smp = self.part_samples(p, h)
        tot = exp = 0.0
        cmin = float("inf")
        worst = None
        for x, y, z, w in smp:
            yy, zz = y * radial_scale, z * radial_scale
            w2 = w * radial_scale ** 2
            c = self.clearance(x, yy, zz, cone_deg, margin, sil, x_s)
            tot += w2
            if c < 0:
                exp += w2
            if c < cmin:
                cmin, worst = c, (x, yy, zz)
        if cmin >= band:
            st = "COVERED"
        elif cmin >= 0:
            st = "AT_BOUNDARY"
        elif all(self.clearance(x, y * radial_scale, z * radial_scale, cone_deg, margin, sil, x_s) < 0 for x, y, z, _ in smp):
            st = "EXPOSED"
        else:
            st = "PARTIAL"
        return {"name": p["name"], "group": p["group"], "system": SYSTEM.get(p["group"], p["group"]), "class": classify(p),
                "shape": p["shape"], "min_clearance_m": cmin, "protrusion_m": max(0.0, -cmin), "worst_point": worst,
                "frontal_area_m2": tot, "exposed_frontal_area_m2": exp, "status": st}

    def assess(self, cone_deg=0.0, margin=0.0, band=1.0, h=0.5, sil=None, x_s=None, engine_radial_scale=1.0, classes=("CRITICAL", "NON_CRITICAL")):
        rows = []
        for p in self.geo["parts"]:
            cl = classify(p)
            if cl not in classes:
                continue
            rs = engine_radial_scale if p["group"] in ENGINE_GROUPS else 1.0
            rows.append(self.assess_part(p, cone_deg, margin, band, h, sil, x_s, rs))
        return rows

    # -- radiators: planform inside the envelope, frontal (projected) area, exposure
    def radiators(self, cone_deg=0.0, margin=0.0, h=None):
        out = []
        th = math.radians(cone_deg)
        for p in self.geo["parts"]:
            if classify(p) != "RADIATOR" or p["shape"] != "panel":
                continue
            c = p["corners"]
            u = [c[1][i] - c[0][i] for i in range(3)]
            v = [c[3][i] - c[0][i] for i in range(3)]
            nvec = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            A = math.sqrt(sum(x * x for x in nvec))
            n = [x / A for x in nvec]
            Lu, Lv = math.sqrt(sum(x * x for x in u)), math.sqrt(sum(x * x for x in v))
            hh = h or max(0.5, max(Lu, Lv) / 2000)
            nu, nv = max(1, int(Lu / hh)), max(1, int(Lv / hh))
            dA = A / (nu * nv)
            prot = 0.0
            for i in range(nu):
                for j in range(nv):
                    q = [c[0][k] + u[k] * (i + 0.5) / nu + v[k] * (j + 0.5) / nv for k in range(3)]
                    if self.clearance(*q, cone_deg, margin) >= 0:
                        prot += dA
            # frontal area seen by the stream: |n.x| for the aligned stream; inside a cone the worst direction adds sin(theta)
            nx = abs(n[0])
            frontal_worst = A * min(1.0, nx * math.cos(th) + math.sqrt(max(0.0, 1 - nx * nx)) * math.sin(th))
            out.append({"name": p["name"], "planform_m2": A, "protected_m2": prot, "exposed_m2": A - prot,
                        "fraction_exposed": (A - prot) / A, "frontal_aligned_m2": A * nx, "frontal_worst_in_cone_m2": frontal_worst,
                        "edge_on": nx < 1e-6, "survivability_class": "UNKNOWN (record gives none)",
                        "note": "edge-on to the aligned stream: frontal area = leading-edge thickness x span; thickness UNKNOWN" if nx < 1e-6 else ""})
        return out

    # -- envelope a component set needs, and the shield it implies
    def required_radius(self, rows_or_samples, cone_deg=0.0, margin=0.0):
        """Circle shield radius (same station) that covers every given sample: max(|p_yz| + L tan + margin)."""
        t = math.tan(math.radians(cone_deg))
        return max(math.hypot(y, z) + max(self.x_s - x, 0.0) * t + margin for x, y, z in rows_or_samples)


ENGINE_GROUPS = {"fdp1_nozzle", "fdp1_shield", "fdp1_power", "fdp1_drivers", "fdp1_reaction", "fdp1_fuel_prep", "fdp1_sensors"}


def engine_envelope(geo):
    """Largest radial extent of the FDP-1 engine hardware (not wings), with the part that sets it."""
    best = (0.0, None)
    for p in geo["parts"]:
        if p["group"] not in ENGINE_GROUPS or classify(p) == "RADIATOR":
            continue
        for x, y, z, _ in samples(p, 0.5):
            r = math.hypot(y, z)
            if r > best[0]:
                best = (r, p["name"], x)
    return {"max_radius_m": best[0], "max_diameter_m": 2 * best[0], "set_by": best[1], "at_x_m": best[2]}


def summarize(rows):
    crit = [r for r in rows if r["class"] == "CRITICAL"]
    exposed = [r for r in crit if r["status"] in ("PARTIAL", "EXPOSED")]
    return {"critical_parts": len(crit), "critical_exposed": len(exposed),
            "critical_at_boundary": sum(r["status"] == "AT_BOUNDARY" for r in crit),
            "exposed_frontal_area_m2": sum(r["exposed_frontal_area_m2"] for r in crit),
            "max_protrusion_m": max([r["protrusion_m"] for r in crit] or [0.0]),
            "by_system": _by_system(exposed)}


def _by_system(rows):
    out = {}
    for r in rows:
        s = out.setdefault(r["system"], {"parts": 0, "exposed_frontal_area_m2": 0.0, "max_protrusion_m": 0.0})
        s["parts"] += 1
        s["exposed_frontal_area_m2"] += r["exposed_frontal_area_m2"]
        s["max_protrusion_m"] = max(s["max_protrusion_m"], r["protrusion_m"])
    return out
