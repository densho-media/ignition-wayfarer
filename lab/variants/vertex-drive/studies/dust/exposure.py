"""T02 two-orientation exposure map: which critical parts the dust stream reaches, bow-first and engine-first.

Standard library only; reads the P11 geometry and code read-only (lab/problems/fdp1-requirements). Research, not canon.
    python3 lab/variants/vertex-drive/studies/dust/exposure.py          # writes exposure.json beside this file (~1 min)

Frame: metres, +X bow, +Z dorsal (ship_geometry.json). Bow-first (acceleration and coast): grains travel -X relative to the ship and the
canon 90 m forward shield (r 45 m) shadows the ship; this case uses protection.Protection unchanged and must reproduce P11 (112.55 m,
50 critical parts, 1,492 m2). Engine-first (braking): grains travel +X; the leading silhouettes are the engine-side shadow shield
(FDP-1 r 8.5 m at x -184.3 m; canon reactor shadow shield r 5.7 m at x -112.8 m) and, as an option, a proposed skirt (see SKIRTS).

Ships: V0 = the FDP-1 geometry as built for P11; V1 / V2 = V0 with the driver galleries folded to r <= 6.5 m, the shadow shield scaled to
the 7.9 deg hardware cone and the wings cut to their tip radius (results/convergence.json); the loops differ by < 0.2 m and are kept.
CANON = the canon four-nozzle ship parts in the same file (hull, engineering, habitat rings, canon tanks, blades, forward shield moved
back by the 122.4 m T-B bow shift, and the four-nozzle drive the file calls 'superseded').
Limits: surfaces are sampled as their stream-facing projections (P11 method); overlaps are not deduplicated (ring 2 behind ring 1 is
counted); arrival cones are an attitude/aberration envelope, not a dust property.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
P11 = os.path.join(ROOT, "lab", "problems", "fdp1-requirements")
sys.path.insert(0, P11)
from fdp1diag import protection as PR  # noqa: E402  (read-only import, as the T02 prompt requires)

OUT = os.path.join(HERE, "exposure.json")
CONV = json.load(open(os.path.join(HERE, "..", "..", "results", "convergence.json")))
H = 0.5
CONES = [0.0, 0.4, 2.290610043, 5.0]   # deg: aligned; max dust aberration at 4,797 km/s (30 km/s grains); P11 diagnostic; P11 prototype
X_BURN = -227.53981167687354           # FDP-1 burn point (ship_geometry.json meta.layout.x_burn)
SS_X_AFT, SS_R_V0 = -184.34909396754733, 8.5   # FDP-1 shadow shield aft (burn-facing) face and outer radius (ship_geometry.json)
SHIELD_GROUP_PARTS = ("FDP1_Shield_W_Xray_Face", "FDP1_Shield_LiH_Crew_Core", "FDP1_Shield_LiH_Hardware_Annulus")
WING_ROOT = 118.92093614714142
WING_TIP_V0 = 3573.0613558988957
CANON_SS = {"r": 5.7, "x": -112.8}     # SUP_Reactor_Shadow_Shield (ship_geometry.json), the canon engine-side silhouette
CANON_CORE_X = -114.8                   # SUP_Fusion_Core station


def gen_params(g):
    x = CONV["generations"][g]
    cone = x["hardware_cone_deg"]
    d = x["burn_aft_of_shield_m"]
    margin = SS_R_V0 - 43.19071770932621 * math.tan(math.radians(CONV["generations"]["V0"]["hardware_cone_deg"]))
    return {"hardware_cone_deg": cone, "shadow_shield_r": d * math.tan(math.radians(cone)) + margin,
            "wing_tip_r": x["summary"]["wing_tip_radius_m"], "gallery_r": 6.5 if g != "V0" else None,
            "loops_r": x["loop_radii_m"]}


def classify(p):
    c = PR.classify(p)
    if p["group"] == "superseded":
        return "CRITICAL"   # in the CANON ship this is the live four-nozzle drive
    return c


SYSTEM = dict(PR.SYSTEM)
SYSTEM["superseded"] = "canon four-nozzle drive"


def ship_samples(geo, ship):
    """[(x, y, z, w, part_index)] for one ship, with the generation's transformations applied to the samples."""
    meta = geo["meta"]
    out, parts = [], []
    gp = gen_params(ship) if ship in ("V1", "V2") else None      # V0 is the P11 geometry unchanged
    for p in geo["parts"]:
        g = p["group"]
        if ship == "CANON":
            if g.startswith("fdp1_"):
                continue
        elif g == "superseded":
            continue
        idx = len(parts)
        parts.append(p)
        dx = -meta["bow_shift_m"] if (ship == "CANON" and p["name"] in meta["bow_moved"]) else 0.0
        for x, y, z, w in PR.samples(p, H):
            r = math.hypot(y, z)
            k = 1.0
            if gp:
                if g == "fdp1_drivers" and r > 1e-9:
                    k = min(1.0, gp["gallery_r"] / 12.4)
                elif p["name"] in SHIELD_GROUP_PARTS and r > 1e-9:
                    k = gp["shadow_shield_r"] / SS_R_V0
                elif "Wing" in p["name"] and r > WING_ROOT:
                    f = (gp["wing_tip_r"] - WING_ROOT) / (WING_TIP_V0 - WING_ROOT)
                    rn = WING_ROOT + (r - WING_ROOT) * f
                    out.append((x + dx, y * rn / r, z * rn / r, w * f, idx))
                    continue
            out.append((x + dx, y * k, z * k, w * k * k, idx))
    return parts, out


# ---- coverage tests ---------------------------------------------------------------------------------------------------
def bow_cover(x, y, z, cone, sil_R, x_s):
    L = max(x_s - x, 0.0)
    return sil_R - math.hypot(y, z) - L * math.tan(math.radians(cone))


def disc_cover_engine(x, y, z, cone, R, x_b):
    """Engine-first: grains travel +X; a disc at x_b covers points forward of it."""
    if x <= x_b:
        return -1e9
    return R - math.hypot(y, z) - (x - x_b) * math.tan(math.radians(cone))


def skirt_cover_fdp1(x, y, z, cone, r_lo, r_hi, theta_deg):
    """Shadow-cone skirt: a conical sheet with its apex at the burn point and half-angle theta (the hardware cone), from r_lo (shadow shield
    rim) to r_hi. Edge-on to the burn (it contains the burn's rays) and, for grains travelling +X, it intercepts every line at radius
    r in [r_lo, r_hi] at x_i(r) = x_burn + r / tan(theta). With an arrival cone the back-traced ray drifts by L tan(cone); the point is
    counted covered only if the whole drift band stays inside [r_lo, r_hi] and forward of the intercept (conservative)."""
    r = math.hypot(y, z)
    t = math.tan(math.radians(theta_deg))
    xi = X_BURN + r / t
    if x <= xi or r < r_lo or r > r_hi:
        return -1e9
    drift = (x - xi) * math.tan(math.radians(cone))
    return min(r - drift - r_lo, r_hi - (r + drift))


def canon_skirt_cover(x, y, z, cone, r_lo=5.7, r_hi=45.0, x_k=-98.0):
    """Canon aft skirt: a flat annulus at x_k = -98 m, r 5.7-45 m, forward of the canon fusion core and (to r ~45 m) inside the reactor
    shadow shield's shadow (shield r 5.7 m, 2 m forward of the core: shadow half-angle ~70 deg)."""
    r = math.hypot(y, z)
    if x <= x_k:
        return -1e9
    drift = (x - x_k) * math.tan(math.radians(cone))
    return min(r - drift - r_lo, r_hi - (r + drift))


def assess(parts, smp, cover_fns, cone):
    """cover_fns: list of f(x,y,z,cone) -> clearance (>= 0 covered). A sample is covered if any silhouette covers it."""
    agg = {}
    for x, y, z, w, i in smp:
        c = max(f(x, y, z, cone) for f in cover_fns) if cover_fns else -1e9
        a = agg.setdefault(i, [0.0, 0.0, float("inf"), None])
        a[0] += w
        if c < 0:
            a[1] += w
        if c < a[2]:
            a[2], a[3] = c, (round(x, 2), round(y, 2), round(z, 2))
    rows = []
    for i, (tot, exp, cmin, worst) in agg.items():
        p = parts[i]
        cl = classify(p)
        if cl not in ("CRITICAL", "NON_CRITICAL"):
            continue
        rows.append({"name": p["name"], "group": p["group"], "system": SYSTEM.get(p["group"], p["group"]), "class": cl,
                     "frontal_area_m2": round(tot, 3), "exposed_frontal_area_m2": round(exp, 3),
                     "status": "COVERED" if exp == 0 else ("EXPOSED" if exp >= tot - 1e-9 else "PARTIAL"),
                     "max_protrusion_m": round(max(0.0, -cmin), 2) if cmin > -1e8 else None})
    shield_rows = []
    for i, (tot, exp, cmin, worst) in agg.items():
        p = parts[i]
        if PR.classify(p) == "SHIELD":
            shield_rows.append((tot, exp))
    crit = [r for r in rows if r["class"] == "CRITICAL"]
    exposed = [r for r in crit if r["status"] != "COVERED"]
    by = {}
    for r in exposed:
        s = by.setdefault(r["system"], {"parts": 0, "exposed_frontal_area_m2": 0.0})
        s["parts"] += 1
        s["exposed_frontal_area_m2"] = round(s["exposed_frontal_area_m2"] + r["exposed_frontal_area_m2"], 2)
    return {"critical_parts": len(crit), "critical_exposed": len(exposed),
            "exposed_frontal_area_m2": round(sum(r["exposed_frontal_area_m2"] for r in crit), 1),
            "forward_shield_parts_exposed_frontal_m2": round(max([e for _, e in shield_rows] or [0.0]), 1),
            "by_system": dict(sorted(by.items(), key=lambda kv: -kv[1]["exposed_frontal_area_m2"])),
            "parts": sorted([r for r in exposed], key=lambda r: -r["exposed_frontal_area_m2"])}


# ---- radiators (planar panels: wings, blades, low-loop panels) -------------------------------------------------------
def radiator_panels(geo, ship):
    gp = gen_params(ship) if ship in ("V1", "V2") else None
    out = []
    for p in geo["parts"]:
        if p["shape"] != "panel":
            continue
        if PR.classify(p) != "RADIATOR":
            continue
        g = p["group"]
        if ship == "CANON" and g.startswith("fdp1_"):
            continue
        c = [list(q) for q in p["corners"]]
        if gp and "Wing" in p["name"]:
            for q in c:
                r = math.hypot(q[1], q[2])
                if r > WING_ROOT + 1:
                    f = gp["wing_tip_r"] / r
                    q[1], q[2] = q[1] * f, q[2] * f
        out.append({"name": p["name"], "group": g, "corners": c})
    return out


def panel_exposure(panel, cover_fns, cone, lead_x_max):
    c = panel["corners"]
    u = [c[1][i] - c[0][i] for i in range(3)]
    v = [c[3][i] - c[0][i] for i in range(3)]
    nvec = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    A = math.sqrt(sum(x * x for x in nvec))
    nx = abs(nvec[0]) / A
    Lu, Lv = math.sqrt(sum(x * x for x in u)), math.sqrt(sum(x * x for x in v))
    nu, nv = 120, 120
    exp = 0.0
    for i in range(nu):
        for j in range(nv):
            q = [c[0][k] + u[k] * (i + 0.5) / nu + v[k] * (j + 0.5) / nv for k in range(3)]
            cc = max(f(*q, cone) for f in cover_fns) if cover_fns else -1e9
            if cc < 0:
                exp += A / (nu * nv)
    # leading edge: the panel edge with the extreme x facing the stream
    edges = [(c[0], c[1]), (c[1], c[2]), (c[2], c[3]), (c[3], c[0])]
    key = (lambda e: max(e[0][0], e[1][0])) if lead_x_max else (lambda e: -min(e[0][0], e[1][0]))
    lead = max([e for e in edges if abs(e[0][0] - e[1][0]) < 1e-6] or edges, key=key)
    lead_len = math.dist(lead[0], lead[1])
    lead_exp = 0.0
    for k in range(400):
        q = [lead[0][m] + (lead[1][m] - lead[0][m]) * (k + 0.5) / 400 for m in range(3)]
        cc = max(f(*q, cone) for f in cover_fns) if cover_fns else -1e9
        if cc < 0:
            lead_exp += lead_len / 400
    th = math.radians(cone)
    return {"name": panel["name"], "planform_m2": round(A, 1), "exposed_planform_m2": round(exp, 1),
            "edge_on": nx < 1e-6, "frontal_aligned_m2": round(A * nx, 2),
            "frontal_worst_in_cone_m2": round(exp * min(1.0, nx * math.cos(th) + math.sqrt(max(0.0, 1 - nx * nx)) * math.sin(th)), 1),
            "leading_edge_exposed_m": round(lead_exp, 1),
            "note": "frontal = exposed planform x sin(cone) for an edge-on panel, plus exposed leading-edge length x edge thickness (UNKNOWN)"}


# ---- run --------------------------------------------------------------------------------------------------------------
def main():
    geo = json.load(open(PR.GEOMETRY))
    shield = PR.shield_from_geometry(geo)
    R_fwd, xs_fwd = shield["radius_m"], shield["x_aft_m"]
    res = {"meta": {"title": "T02 two-orientation exposure map (research, not canon)", "sample_spacing_m": H, "cones_deg": CONES,
                    "generations": {g: gen_params(g) for g in ("V0", "V1", "V2")},
                    "forward_shield": {"radius_m": R_fwd, "x_aft_fdp1_m": xs_fwd, "x_aft_canon_m": xs_fwd - geo["meta"]["bow_shift_m"]},
                    "engine_side": {"fdp1_shadow_shield": {"x_m": SS_X_AFT, "r_m_V0": SS_R_V0}, "canon_reactor_shadow_shield": CANON_SS},
                    "skirts": {"fdp1": "shadow-cone skirt: apex at the burn point, half-angle = hardware cone, from the shadow-shield rim to r 45 m (T02-NEW-1)",
                               "canon": "flat aft skirt annulus at x -98 m, r 5.7-45 m, inside the reactor shadow-shield shadow (T02-NEW-1, canon form)"},
                    "limits": "projection sampling (P11 method); overlaps not deduplicated; cones conservative for skirts; radiators separate"},
           "p11_reproduction": None, "cases": {}, "radiators": {}}
    # P11 reproduction with the unchanged class
    pr = PR.Protection(geo=geo)
    rows = pr.assess(cone_deg=0.0)
    s = PR.summarize(rows)
    env = PR.engine_envelope(geo)
    res["p11_reproduction"] = {"engine_max_radius_m": round(env["max_radius_m"], 2), "critical_exposed": s["critical_exposed"],
                               "exposed_frontal_area_m2": round(s["exposed_frontal_area_m2"], 1),
                               "matches_P11": abs(env["max_radius_m"] - 112.55) < 0.01 and s["critical_exposed"] == 50 and abs(s["exposed_frontal_area_m2"] - 1492) < 1}
    for ship in ("V0", "V1", "V2", "CANON"):
        parts, smp = ship_samples(geo, ship)
        gp = gen_params(ship) if ship != "CANON" else None
        xs = xs_fwd - (geo["meta"]["bow_shift_m"] if ship == "CANON" else 0.0)
        bow = [lambda x, y, z, c, xs=xs: bow_cover(x, y, z, c, R_fwd, xs)]
        if ship == "CANON":
            eng = [lambda x, y, z, c: disc_cover_engine(x, y, z, c, CANON_SS["r"], CANON_SS["x"])]
            eng_sk = eng + [lambda x, y, z, c: canon_skirt_cover(x, y, z, c)]
        else:
            Rss = gp["shadow_shield_r"]
            eng = [lambda x, y, z, c, R=Rss: disc_cover_engine(x, y, z, c, R, SS_X_AFT)]
            th = gp["hardware_cone_deg"]
            eng_sk = eng + [lambda x, y, z, c, R=Rss, th=th: skirt_cover_fdp1(x, y, z, c, R, 45.0, th)]
        options = {"BOW_FIRST": {"canon_forward_shield": bow},
                   "ENGINE_FIRST": {"engine_side_only": eng, "with_skirt": eng_sk}}
        res["cases"][ship] = {}
        res["radiators"][ship] = {}
        panels = radiator_panels(geo, ship)
        for orient, opts in options.items():
            res["cases"][ship][orient] = {}
            res["radiators"][ship][orient] = {}
            for oname, fns in opts.items():
                res["cases"][ship][orient][oname] = {}
                res["radiators"][ship][orient][oname] = {}
                for cone in CONES:
                    a = assess(parts, smp, fns, cone)
                    if cone != 0.0:
                        a["parts"] = a["parts"][:12]
                    res["cases"][ship][orient][oname][f"{cone:g}"] = a
                    if cone in (0.0, 0.4, 5.0):
                        res["radiators"][ship][orient][oname][f"{cone:g}"] = [
                            panel_exposure(pn, fns, cone, lead_x_max=(orient == "BOW_FIRST")) for pn in panels]
                print(f"{ship:6s} {orient:12s} {oname:22s} cone0: {res['cases'][ship][orient][oname]['0']['critical_exposed']:3d} parts "
                      f"{res['cases'][ship][orient][oname]['0']['exposed_frontal_area_m2']:9.1f} m2 | cone5: "
                      f"{res['cases'][ship][orient][oname]['5']['exposed_frontal_area_m2']:9.1f} m2", flush=True)
    json.dump(res, open(OUT, "w"), indent=1)
    return res


if __name__ == "__main__":
    r = main()
    print("P11 reproduction:", r["p11_reproduction"])
