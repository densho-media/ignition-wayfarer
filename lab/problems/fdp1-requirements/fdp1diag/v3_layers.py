"""V3 Blender layers that follow the scenario: the P11 protection envelope, exposure highlights, the shield ghost,
radiator exposure and the constraint board. bpy + math + v2kit only. The module is used by build_v3.py, and the
sidebar embeds it to rebuild these layers live.

It draws a ScenarioV3.evaluate() result and computes no physics of its own.
"""
import math

import v2kit as K

K.PAL.setdefault("protect", (0.18, 0.80, 0.72))
K.PAL.setdefault("exposed", (1.00, 0.16, 0.20))
K.TAGS.setdefault("protect", "COLOR_04")
STATUS_KEY = {"PASS": "verified", "FAIL": "infeasible", "UNRESOLVED": "unresolved", "ASSUMPTION": "dim"}


def props(component, **kw):
    d = {"layer": "information", "state": "protection", "component": component, "req_ids": "P11"}
    d.update(kw)
    return d


def part_mesh(p, inflate=0.0, radial=1.0):
    s = p["shape"]
    if s == "ring":
        cy, cz = p.get("centre", (0.0, 0.0))
        return K.ring(p["x0"] - inflate, p["x1"] + inflate, max(p.get("r0", 0.0) - inflate, 0.0) * radial, (p["r1"] + inflate) * radial,
                      p.get("arc"), (cy * radial, cz * radial))
    if s == "frustum":
        cy, cz = p.get("centre", (0.0, 0.0))
        return K.frustum(p["x0"], (p["r0"] + inflate) * radial, p["x1"], (p["r1"] + inflate) * radial, p.get("ri0"), p.get("ri1"), p.get("arc"),
                         (cy * radial, cz * radial))
    if s == "torus":
        return K.torus(p["x"], p["R"] * radial, max(p["a"], 0.12) + inflate, p.get("arc"))
    if s == "box":
        c = p["centre"]
        return K.box((c[0], c[1] * radial, c[2] * radial), [x + 2 * inflate for x in p["size"]], p.get("roll", 0.0))
    if s == "panel":
        return K.panel([(q[0], q[1] * radial, q[2] * radial) for q in p["corners"]], p.get("thickness", 0.3) + inflate)
    if s == "tube":
        return K.tube([(q[0], q[1] * radial, q[2] * radial) for q in p["points"]], max(p["radius"], 0.08) + inflate, 8)
    if s == "capsule":
        cy, cz = p["centre"]
        return K.capsule(p["x0"], p["x1"], p["radius"] + inflate, (cy * radial, cz * radial))
    raise ValueError(s)


def _clear(x, y, z, P, ctx):
    R = P["shield_radius_m"]
    L = max(ctx["x_s"] - x, 0.0)
    return R - math.hypot(y, z) - L * math.tan(math.radians(P["cone_deg"])) - P["margin_m"]


def r_prot(x, P, ctx, R=None):
    R = P["shield_radius_m"] if R is None else R
    return R - max(ctx["x_s"] - x, 0.0) * math.tan(math.radians(P["cone_deg"])) - P["margin_m"]


def build_envelope(res, ctx, c):
    """Protected volume of the shield in this scenario, its outline rings and incoming trajectories."""
    K.clear(c)
    P = res["protection"]
    xs, xa = ctx["x_s"], ctx["x_aft"]
    t = math.tan(math.radians(P["cone_deg"]))
    R = P["shield_radius_m"] - P["margin_m"]
    x_lo = xa if t == 0 else max(xa, xs - R / t)
    r_lo = max(r_prot(x_lo, P, ctx), 0.0)
    K.obj("P11_Protected_Volume", *K.frustum(x_lo, r_lo, xs, R), K.mat("protect", 0.08), c,
          props("geometrically protected volume", encoding="intersection of the shield shadows over the arrival cone",
                cone_deg=P["cone_deg"], margin_m=P["margin_m"], shield_radius_m=P["shield_radius_m"], x_shield_m=xs), smooth=True)
    for i, x in enumerate([xs] + [xs - k * 100.0 for k in range(1, 9) if xs - k * 100.0 > x_lo] + [x_lo]):
        r = max(r_prot(x, P, ctx), 0.0)
        if r > 0.3:
            K.obj(f"P11_Boundary_Ring_{i:02d}", *K.torus(x, r, 0.35 if i else 0.6), K.mat("protect", 0.9, 1.1), c,
                  props("protection boundary", station_x_m=x, protected_radius_m=r))
    if t == 0 or x_lo == xa:
        pass
    else:
        K.label("P11_Envelope_Apex_Label", f"no protected core aft of x {x_lo:,.0f} m (cone {P['cone_deg']:.2g}°)", (x_lo, 0, 20), 8, "unresolved", c,
                props=props("label"))
    # incoming trajectories: some stop on the shield, the ones outside its silhouette run the length of the ship
    x0, xf, xe = ctx["x_fwd"] + 420.0, ctx["x_fwd"], xa - 60.0
    lines_in, lines_out = [], []
    for k in range(16):
        a = 2 * math.pi * k / 16
        for rr in (15.0, 32.0):
            y, z = rr * math.cos(a), rr * math.sin(a)
            lines_in.append(((x0, y, z + t * (x0 - xf)), (xf, y, z)))
        for rr in (60.0, 90.0, 118.0):
            y, z = rr * math.cos(a + 0.2), rr * math.sin(a + 0.2)
            lines_out.append(((x0, y, z + t * (x0 - xf)), (xe, y, z - t * (xf - xe))))
    K.obj("P11_Trajectories_Stopped", *K.cones([(p, q, 0.25, 0.25) for p, q in lines_in], 4), K.mat("dim", 0.5), c,
          props("incoming trajectories intercepted by the shield", encoding="direction only; flux and grain spectrum UNKNOWN"))
    K.obj("P11_Trajectories_Passing", *K.cones([(p, q, 0.25, 0.25) for p, q in lines_out], 4), K.mat("radiation", 0.45, 0.8), c,
          props("incoming trajectories outside the shield silhouette", encoding="direction only"))
    K.label("P11_Envelope_Label", f"PROTECTED ENVELOPE  shield r {P['shield_radius_m']:.1f} m · arrival cone {P['cone_deg']:.3g}° · margin {P['margin_m']:.3g} m",
            (xs - 20, 0, P["shield_radius_m"] + 26), 10, "protect", c, props=props("label"))
    K.label("P11_Envelope_Sub", "geometric coverage only · stopping, ejecta, penetration, shock and survival UNRESOLVED",
            (xs - 20, 0, P["shield_radius_m"] + 14), 5.5, "unresolved", c, props=props("label"))


def build_exposure(res, ctx, parts, c):
    """Red: critical hardware outside the envelope (the exposed portion where it can be isolated); yellow: at the boundary."""
    K.clear(c)
    P = res["protection"]
    k_eng = P["engine_radial_scale"]
    groups = ctx["engine_groups"]
    by_sys = {}
    for r in P["rows"]:
        if r["class"] != "CRITICAL" or r["status"] == "COVERED":
            continue
        p = parts[r["name"]]
        rs = k_eng if p["group"] in groups else 1.0
        col = "unresolved" if r["status"] == "AT_BOUNDARY" else "exposed"
        meta = props(r["system"], part=r["name"], status=r["status"], protrusion_m=r["protrusion_m"],
                     exposed_frontal_area_m2=r["exposed_frontal_area_m2"], component_class=r["class"])
        if p["shape"] == "tube" and r["status"] == "PARTIAL":
            pts = []
            for a, b in zip(p["points"], p["points"][1:]):
                n = max(2, int(math.dist(a, b) / 2.0))
                for i in range(n + 1):
                    q = [a[j] + (b[j] - a[j]) * i / n for j in range(3)]
                    q[1], q[2] = q[1] * rs, q[2] * rs
                    pts.append((q, _clear(q[0], q[1], q[2], P, ctx) - p["radius"] < 0))
            seg, segs = [], []
            for q, e in pts:
                if e:
                    seg.append(q)
                elif seg:
                    segs.append(seg)
                    seg = []
            if seg:
                segs.append(seg)
            for i, sgm in enumerate(s for s in segs if len(s) > 1):
                K.obj(f"P11_Exposed_{r['name']}_{i}", *K.tube(sgm, max(p["radius"], 0.08) + 0.35, 6), K.mat(col, 0.95, 1.1, 0.5), c, meta)
        else:
            K.obj(f"P11_Exposed_{r['name']}", *part_mesh(p, 0.3, rs), K.mat(col, 0.85, 1.1, 0.5), c, meta)
        s = by_sys.setdefault(r["system"], {"n": 0, "nb": 0, "area": 0.0, "prot": 0.0, "pt": r["worst_point"]})
        s["nb" if r["status"] == "AT_BOUNDARY" else "n"] += 1
        s["area"] += r["exposed_frontal_area_m2"]
        if r["protrusion_m"] >= s["prot"]:
            s["prot"], s["pt"] = r["protrusion_m"], r["worst_point"]
    z = -150.0
    for i, (name, s) in enumerate(sorted(by_sys.items(), key=lambda kv: -kv[1]["area"])):
        pt = s["pt"]
        anchor = (pt[0], pt[1], pt[2])
        q = (ctx["x_label_exposure"], -60.0, z - 16 * i)
        col = "exposed" if s["n"] else "unresolved"
        txt = (f"{name}: {s['n']} parts outside · protrusion {s['prot']:.1f} m · {s['area']:,.0f} m² frontal exposed" if s["n"] else f"{name}:")
        if s["nb"]:
            txt += f" · {s['nb']} at the boundary (within {P['band_m']:g} m, uncertain)"
        K.obj(f"P11_Exposure_Leader_{i}", *K.tube([anchor, q], 0.25, 4), K.mat(col, 0.6), c, props("leader"))
        K.label(f"P11_Exposure_Label_{i}", txt, q, 6, col, c, align="RIGHT", props=props("label", system=name))
    S = P["summary"]
    K.label("P11_Exposure_Title", f"P11  CRITICAL HARDWARE OUTSIDE THE ENVELOPE: {S['critical_exposed']} of {S['critical_parts']} parts · "
            f"{S['exposed_frontal_area_m2']:,.0f} m² frontal · max protrusion {S['max_protrusion_m']:.1f} m",
            (ctx["x_label_exposure"], -60.0, z + 22), 8, "exposed" if S["critical_exposed"] else "protect", c, align="RIGHT", props=props("label"))
    # engine envelope vs protected radius at the station that sets the engine's maximum radius
    xe = ctx["engine_x"]
    re_, rp = P["engine_max_radius_m"], P["protected_radius_at_engine_m"]
    K.obj("P11_Engine_Max_Radius_Ring", *K.torus(xe - 3, re_, 0.8), K.mat("exposed", 0.9), c,
          props("engine maximum radius", radius_m=re_, set_by=P["engine_set_by"], engine_radial_scale=k_eng))
    if rp > 0.5:
        K.obj("P11_Protected_Radius_At_Engine", *K.torus(xe - 3, rp, 0.8), K.mat("protect", 0.95, 1.2), c,
              props("protected radius at the engine station", radius_m=rp))
    K.label("P11_Engine_Clearance_Label", f"engine r {re_:.1f} m vs protected r {rp:.1f} m → clearance {P['engine_clearance_m']:+.1f} m",
            (xe - 3, 0, -re_ - 18), 8, "exposed" if P["engine_clearance_m"] < 0 else "protect", c, props=props("label"))
    if k_eng != 1.0:
        K.label("P11_Engine_Geometry_Assumption", f"ASSUMPTION: engine radial size × {k_eng:.2f} (P^{P['engine_exp']:.2g}; no documented packaging law)",
                (xe - 3, 0, -re_ - 30), 6, "unresolved", c, props=props("label"))
        for name in ctx["engine_ghost_parts"]:
            p = parts[name]
            K.obj(f"P11_Engine_Ghost_{name}", *part_mesh(p, 0.0, k_eng), K.mat("fiji", 0.35), c, props("scaled engine (hypothetical)", part=name))


def build_shield_ghost(res, ctx, c):
    K.clear(c)
    P = res["protection"]
    R, R0 = P["shield_radius_m"], P["shield_radius_baseline_m"]
    if abs(R - R0) < 1e-6:
        return
    xs, xf = ctx["x_s"], ctx["x_fwd"]
    K.obj("P11_Shield_Ghost", *K.ring(xs, xf, 0.0, R), K.mat("structure", 0.16, 1.3), c,
          props("hypothetical enlarged shield (canon 45 m unchanged)", radius_m=R, area_m2=P["shield_area_m2"]))
    K.obj("P11_Shield_Ghost_Rim", *K.torus(xf, R, 0.8), K.mat("text", 0.9), c, props("hypothetical shield rim", radius_m=R))
    ratio = P["shield_area_m2"] / P["shield_area_baseline_m2"]
    if P["shield_mass_effect"] == "ASSUMPTION":
        m = f"+{P['shield_added_mass_kg'] / 1e3:,.0f} t at {P['areal_density_kg_m2']:g} kg/m² (ASSUMPTION) → fed into the mass closure"
    else:
        m = "added mass UNRESOLVED: shield stack and areal density OPEN (OD-014)"
    K.label("P11_Shield_Ghost_Label", f"HYPOTHETICAL SHIELD r {R:.1f} m · area ×{ratio:.2f} (+{P['shield_added_area_m2']:,.0f} m²)",
            (xf + 10, 0, -R - 14), 11, "text", c, props=props("label"))
    K.label("P11_Shield_Ghost_Mass", m, (xf + 10, 0, -R - 28), 7, "unresolved" if P["shield_mass_effect"] != "ASSUMPTION" else "dim", c,
            props=props("label"))
    K.label("P11_Shield_Ghost_Note", "larger area also intercepts more grains and needs more structure (not modelled)",
            (xf + 10, 0, -R - 38), 5, "dim", c, props=props("label"))


def build_radiator_exposure(res, ctx, parts, c):
    K.clear(c)
    P = res["protection"]
    S = P["radiator_summary"]
    for r in P["radiators"]:
        if not r["name"].startswith("FDP1_Wing"):
            continue
        p = parts[r["name"]]
        cs = p["corners"]
        side = 1 if cs[2][1] > 0 else -1
        y0, y1 = abs(cs[0][1]), abs(cs[2][1])
        # protected strip: up to the protected radius at the wing's forward edge (the radius shrinks aft inside a cone)
        rp = max(0.0, r_prot(max(cs[0][0], cs[1][0]), P, ctx))
        x0, x1 = cs[0][0], cs[1][0]
        if rp > y0:
            yy = min(rp, y1)
            K.obj(f"P11_Radiator_Protected_{r['name']}", *K.panel([(x0, side * y0, 0.4), (x1, side * y0, 0.4), (x1, side * yy, 0.4), (x0, side * yy, 0.4)], 0.1),
                  K.mat("protect", 0.55), c, props("radiator planform inside the envelope", area_m2=r["protected_m2"]))
        ya = max(y0, rp)
        K.obj(f"P11_Radiator_Exposed_{r['name']}", *K.panel([(x0, side * ya, 0.45), (x1, side * ya, 0.45), (x1, side * y1, 0.45), (x0, side * y1, 0.45)], 0.1),
              K.mat("exposed", 0.10), c, props("radiator planform outside the envelope", area_m2=r["exposed_m2"],
                                                 survivability=r["survivability_class"], note=r["note"]))
    K.label("P11_Radiator_Title", f"RADIATORS  {S['planform_m2'] / 1e6:,.2f} km² planform · {S['protected_m2']:,.0f} m² inside the envelope · "
            f"{S['fraction_exposed'] * 100:.1f} % outside", (175.0, 900.0, 250), 24, "thermal", c, props=props("label"))
    K.label("P11_Radiator_Sub", ("edge-on to an aligned stream: frontal = edge thickness × span (thickness UNKNOWN)" +
             (f" · up to {S['frontal_worst_in_cone_m2']:,.0f} m² frontal inside the {P['cone_deg']:.3g}° cone" if P["cone_deg"] else "") +
             " · survivability class UNKNOWN · retraction would need heat storage (not modelled)"),
            (175.0, 900.0, 222), 11, "unresolved", c, props=props("label"))


def build_constraints(res, ctx, c):
    K.clear(c)
    x, z = ctx["board_x"], ctx["board_z"]
    closed = res["mathematically_closed"]
    K.label("V3_Constraint_Title", f"CONSTRAINTS · mathematically {'closed' if closed else 'NOT closed'} · physically validated: NO",
            (x, 0, z), 14, "verified" if closed else "infeasible", c, align="LEFT", props=props("constraint board", req_ids=""))
    for i, (fam, (st, why)) in enumerate(res["constraints"].items()):
        K.label(f"V3_Constraint_{fam}", f"{fam:<11} {st:<10} {why[:120]}", (x, 0, z - 22 - 15 * i), 8, STATUS_KEY[st], c, align="LEFT",
                props=props("constraint", family=fam, status=st, detail=why, req_ids=""))


# ---- modes and the compact result the sidebar shows -------------------------------------------------------------
CONTROLLED = ("V2_00_", "V2_1", "V2_20_", "V2_30_", "V2_40_", "V2_50_", "V3_6", "V3_70_", "LAYER_B")


def set_mode(sc, mode, detail=False, show_superseded=False, show_square=False):
    import json as _j
    modes = _j.loads(sc.get("v3_modes", "{}"))
    show = set(modes.get(mode, {}).get("show", []))
    reqs = set(modes.get(mode, {}).get("req", []))

    def want(n):
        if n.endswith("__DETAIL"):
            return detail and mode != "BOARD"
        if n == "V2_99_SUPERSEDED_FOUR_NOZZLE_DRIVE":
            return show_superseded and mode != "BOARD"
        if n == "V2_21_TARGET_EQUIVALENT_AREA_SQUARE":
            return show_square and mode != "BOARD"
        if n.startswith("LAYER_B"):
            return mode == "BOARD"
        if "_REQ_" in n:
            return mode == "ALL" or n.rsplit("_", 1)[-1] in reqs
        if n.startswith(CONTROLLED):
            if mode == "BOARD":
                return False
            return mode == "ALL" or n in show
        return True

    def walk(lc):
        for ch in lc.children:
            on = want(ch.collection.name)
            ch.hide_viewport = not on
            ch.collection.hide_render = not on
            walk(ch)
    walk(sc.view_layers[0].layer_collection)
    sc["v3_mode"] = mode


def summary(res):
    P = res["protection"]
    st = res["v3"]["closed"] or res["v3"]["at_baseline_mass"]
    return {"status": res["v3"]["status"], "ceiling_g": res["v3"]["ceiling_g"], "loop_gain": res["v3"]["loop_gain"],
            "fusion_W": st["fusion_W"], "thrust_N": st["thrust_N"], "departure_kg": st["departure_kg"], "area_m2": st["area_W_m2"],
            "tip_m": st["wings"]["tip_radius_m"], "constraints": res["constraints"], "assumptions": res["assumptions"],
            "mathematically_closed": res["mathematically_closed"], "physically_validated": res["physically_validated"],
            "shield_radius_m": P["shield_radius_m"], "shield_radius_required_m": P["shield_radius_required_m"],
            "shield_added_area_m2": P["shield_added_area_m2"], "shield_added_mass_kg": P["shield_added_mass_kg"],
            "shield_mass_effect": P["shield_mass_effect"], "engine_max_radius_m": P["engine_max_radius_m"],
            "engine_clearance_m": P["engine_clearance_m"], "critical": {k: v for k, v in P["summary"].items() if k != "by_system"},
            "by_system": P["summary"]["by_system"], "radiators": P["radiator_summary"]}
