"""The TARGET layer of FDP-1 Spatial Systems V2: ghost geometry for a chosen acceleration and warm-radiator temperature.
It is used by build_v2.py and, embedded as a text block, by the sidebar controls in the .blend. The module needs only bpy,
math, v2kit and a scenario result dict from fdp1diag/scenario.py.

A target is never drawn as a working design:
- When the scenario closes, the ghosts show the closed design.
- When it does not close, the ghosts show the lower bound at today's departure mass. Red feedback cubes show the
  departure mass growing each pass, and a banner reads INFEASIBLE under the current scaling assumptions.
"""
import math

import v2kit as K

ENC = {  # information-geometry encodings, metres in the scene (declared on every object and in VISUAL_GRAMMAR_V2.md)
    "sphere_r_per_cbrt_TW": None,     # filled from the baseline: 17.29 TW -> radius SPHERE_R0
    "SPHERE_R0": 25.0,                # m, radius of the baseline fusion sphere (volume proportional to power)
    "TUBE_R0": 15.0,                  # m, tube radius that would carry the whole fusion power (area proportional to power)
    "TUBE_MIN": 0.4,                  # m, thinner tubes are drawn at this radius and flagged drawn_min
    "M_PER_N": 1.0 / 5000.0,          # thrust arrows: 1 m per 5 kN
    "MASS_KG_PER_M3": None,           # filled: 20,760 t -> MASS_SIDE0 cube
    "MASS_SIDE0": 60.0,
    "FEEDBACK_MAX_SIDE": 400.0,       # m, larger feedback cubes are named, not drawn               # m, cube side of today's departure mass (volume proportional to mass)
}


def sphere_r(P, P0):
    return ENC["SPHERE_R0"] * (P / P0) ** (1 / 3)


def tube_r(P, P0):
    r = ENC["TUBE_R0"] * math.sqrt(max(P, 0.0) / P0)
    return max(r, ENC["TUBE_MIN"]), r < ENC["TUBE_MIN"]


def cube_side(kg, m0):
    return ENC["MASS_SIDE0"] * (kg / m0) ** (1 / 3)


def fmtP(w):
    for s, u in ((1e15, "PW"), (1e12, "TW"), (1e9, "GW"), (1e6, "MW")):
        if abs(w) >= s:
            v = w / s
            return f"{v:,.3g} {u}" if v < 100 else f"{v:,.0f} {u}"
    return f"{w:,.0f} W"


def t_(kg):
    return f"{kg / 1e3:,.0f} t"


def info(component, encoding="", basis="", **kw):
    d = {"layer": "information", "state": "target", "component": component, "encoding": encoding, "basis": basis}
    d.update(kw)
    return d


def build_target(res, ctx, c, show_square=False):
    """res = Scenario.evaluate(...); ctx = scene context dict written by build_v2.py; c = the TARGET collection."""
    K.clear(c)
    P0, m0 = ctx["fusion_W"], ctx["departure_kg"]
    st = res["closed"] or res["at_baseline_mass"]
    basis = "closed design" if res["closed"] else "lower bound at today's departure mass (no design closes)"
    feasible = res["feasible"]
    bad = "infeasible"
    xb = ctx["x_burn"]
    a, T = res["inputs"]["accel_g"], res["inputs"]["warm_T_K"]
    tag = f"{a:.2g} g, warm loop {T:.0f} K"
    keyc = "fusion" if feasible else bad

    # fusion power: ghost sphere at the burn point
    r = sphere_r(st["fusion_W"], P0)
    K.obj("TGT_Fusion_Sphere", *K.sphere((xb, 0, 0), r), K.mat("fusion", 0.10), c,
          info("fusion power required", "sphere volume proportional to power", basis, value_W=st["fusion_W"]), smooth=True)
    K.obj("TGT_Fusion_Sphere_Equator", *K.torus(xb, r, max(r * 0.006, 0.6)), K.mat("fusion", 0.7), c,
          info("fusion power required", basis=basis))
    K.label("TGT_Fusion_Label", f"TARGET FUSION {fmtP(st['fusion_W'])}", (xb, 0, r + 22), max(10.0, r * 0.08), "fusion", c,
            props=info("label"))
    # thrust: ghost arrow along the propulsion axis, same scale as the baseline arrow
    x0, z0 = ctx["arrow_x"], ctx["arrow_z"]
    L = st["thrust_N"] * ENC["M_PER_N"]
    head = min(40.0, L * 0.3)
    K.obj("TGT_Thrust_Arrow", *K.tube([(x0, 0, z0), (x0 + L - head, 0, z0)], 3.0), K.mat("exhaust", 0.30), c,
          info("thrust required", "arrow length proportional to force, 1 m per 5 kN", basis, value_N=st["thrust_N"]))
    K.obj("TGT_Thrust_Arrow_Head", *K.tube([(x0 + L - head, 0, z0), (x0 + L, 0, z0)], 9.0, 10, 0.01), K.mat("exhaust", 0.5), c,
          info("thrust required", basis=basis))
    K.label("TGT_Thrust_Label", f"TARGET THRUST {st['thrust_N'] / 1e6:,.1f} MN", (x0 + min(L, 900) * 0.5, 0, z0 + 22), 12, "exhaust", c,
            props=info("label"))
    # radiators: the wing extension needed at this temperature (physical scale)
    w = st["wings"]
    ch0, ch1 = ctx["wing_x0"], ctx["wing_x1"]
    base = ctx["wing_base_r"]
    for i, az in enumerate(ctx["wing_az"]):
        if w["hot_band_m"] > 0:
            K.obj(f"TGT_Wing_{i + 1}_Hot_Band", *K.panel([K.pol(ch0, base, az), K.pol(ch1, base, az), K.pol(ch1, base + w["hot_band_m"], az),
                                                          K.pol(ch0, base + w["hot_band_m"], az)], 0.5),
                  K.mat("thermal", 0.18, 1.3), c, info("hot radiator required", "true planform area, 1 m = 1 m", basis,
                                                       area_m2=st["area_hot_m2"], T_K=res["inputs"]["hot_T_K"]))
        K.obj(f"TGT_Wing_{i + 1}_Warm_Field", *K.panel([K.pol(ch0, w["warm_root_m"], az), K.pol(ch1, w["warm_root_m"], az),
                                                        K.pol(ch1, w["tip_radius_m"], az), K.pol(ch0, w["tip_radius_m"], az)], 0.5),
              K.mat("thermal", 0.07, 0.9), c, info("warm radiator required", "true planform area (two emitting faces)", basis,
                                                   area_m2=st["area_warm_m2"], T_K=T, tip_radius_m=w["tip_radius_m"]))
        if az % 360 != 0:   # tip edge on the port wing only: the side cameras look across the starboard wing
            continue
        K.obj(f"TGT_Wing_{i + 1}_Tip_Edge", *K.tube([K.pol(ch0, w["tip_radius_m"], az), K.pol(ch1, w["tip_radius_m"], az)], 4.0),
              K.mat(bad if w["beyond_designed_wing"] else "thermal", 0.9), c,
              info("required wing tip", basis=basis, beyond_designed_wing=int(w["beyond_designed_wing"])))
    yr = ctx.get("tgt_rad_label_y", 700.0)   # fixed near the port wing root, so the label size does not grow with the wing
    K.label("TGT_Radiator_Label", f"TARGET RADIATORS {st['area_W_m2'] / 1e6:,.3g} km²  ·  wing tip {w['tip_radius_m'] / 1e3:,.2f} km",
            ((ch0 + ch1) / 2, yr, 150), 16, "thermal", c, props=info("label"), k=1.2)
    if w["beyond_designed_wing"]:
        K.label("TGT_Radiator_Envelope_Flag", f"beyond the designed {ctx.get('wing_tip_design_m', 3573) / 1e3:.2f} km wing: deployment and structure unverified",
                ((ch0 + ch1) / 2, yr, 128), 10, bad, c, props=info("label"))
    cs = K.coll("V2_21_TARGET_EQUIVALENT_AREA_SQUARE", c, "COLOR_01")
    s = w["equivalent_square_side_m"]
    K.obj("TGT_Equivalent_Area_Square", *K.panel([(-s / 2, -s / 2, -60), (s / 2, -s / 2, -60), (s / 2, s / 2, -60), (-s / 2, s / 2, -60)], 0.5),
          K.mat("thermal", 0.12), cs, info("equivalent radiator area (single plate, not a layout)", "true area", basis,
                                           area_m2=st["area_W_m2"]))
    # mass: the power-scaled engine (drive + radiators) on the mass rail, and the feedback when nothing closes
    mz, mx = ctx["mass_rail_z"], ctx["mass_rail_x_engine"]
    sh = cube_side(st["power_scaled_kg"], m0)
    K.obj("TGT_Engine_Mass", *K.box((mx, 0, mz + sh / 2), (sh, sh, sh)), K.mat(keyc if not feasible else "structure", 0.14), c,
          info("power-scaled engine mass (drive + radiators)", "cube volume proportional to mass", basis, mass_kg=st["power_scaled_kg"]))
    K.obj("TGT_Engine_Mass_Edges", *K.wire_cube((mx, 0, mz + sh / 2), sh, max(0.5, sh * 0.006)), K.mat(keyc if not feasible else "structure", 0.9), c,
          info("power-scaled engine mass", basis=basis))
    K.label("TGT_Engine_Mass_Label", f"ENGINE {t_(st['power_scaled_kg'])}", (mx, 0, mz + sh + 14), max(10.0, sh * 0.06), "text", c,
            props=info("label"))
    xf = ctx["mass_rail_x_feedback"]
    if not feasible:
        prev = m0
        x = xf
        for i, m in enumerate(res["feedback_departure_kg"]):
            s = cube_side(m, m0)
            if s > ENC["FEEDBACK_MAX_SIDE"]:
                K.label(f"TGT_Feedback_Pass_{i + 1}_Label", f"pass {i + 1}: {t_(m)} (cube {s / 1e3:,.1f} km, not drawn) · diverges",
                        (x, 0, mz + 40), 12, bad, c, align="LEFT", props=info("label", mass_kg=m, iteration=i + 1))
                break
            K.obj(f"TGT_Feedback_Pass_{i + 1}", *K.wire_cube((x + s / 2, 0, mz + s / 2), s, max(0.6, s * 0.006)), K.mat(bad, 0.8), c,
                  info("departure mass after adding the engine it needs", "cube volume proportional to mass",
                       "closure iteration from today's mass", mass_kg=m, iteration=i + 1))
            K.label(f"TGT_Feedback_Pass_{i + 1}_Label", f"pass {i + 1}: {t_(m)}", (x + s / 2, 0, mz + s + 12), max(9.0, s * 0.05), bad, c,
                    props=info("label"))
            x += s + 25
            prev = m
        K.label("TGT_Feedback_Title", f"MASS FEEDBACK  gain ×{res['loop_gain']:.2f} per pass", (xf, 0, mz - 30), 14, bad, c,
                align="LEFT", props=info("label"))
    else:
        cl = res["closed"]
        s = cube_side(cl["departure_kg"], m0)
        K.obj("TGT_Departure_Mass", *K.wire_cube((xf + s / 2, 0, mz + s / 2), s, max(0.5, s * 0.006)), K.mat("verified", 0.9), c,
              info("closed departure mass", "cube volume proportional to mass", basis, mass_kg=cl["departure_kg"]))
        K.label("TGT_Departure_Mass_Label", f"DEPARTS {t_(cl['departure_kg'])}", (xf + s / 2, 0, mz + s + 12), max(10.0, s * 0.05),
                "verified", c, props=info("label"))
    # status banner and flags
    zb = ctx["banner_z"]
    head = (f"TARGET {tag}:  " + (f"INFEASIBLE under current scaling (ceiling {res['ceiling_g']:.4f} g)" if not feasible
                                  else f"closes at {t_(res['closed']['departure_kg'])}"))
    if res["status"] == "BASELINE":
        head = f"TARGET = BASELINE ({tag})"
    K.label("TGT_Status_Banner", head, (ctx["banner_x"], 0, zb), 22, bad if not feasible else "verified", c,
            props=info("status", status=res["status"], feasible=int(feasible), ceiling_g=res["ceiling_g"], loop_gain=res["loop_gain"]))
    seen, z = set(), zb - 34
    for key, text in res["flags"]:
        if (key, text) in seen or key == "INFEASIBLE":
            continue
        seen.add((key, text))
        K.label(f"TGT_Flag_{len(seen)}", f"{key}: {text}", (ctx["banner_x"], 0, z), 11, "unresolved" if key != "ASSUMPTION" else "dim",
                c, props=info("flag", req_ids=key))
        z -= 20
    if not res["closed"]:
        K.label("TGT_Basis_Note", "ghosts show the lower bound at today's 20,760 t; the real requirement is larger and has no closure",
                (ctx["banner_x"], 0, z), 11, "dim", c, props=info("label"))
    # requirement alerts: a red halo on each marker the target trips
    hit = {k for k, _ in res["flags"]} | ({"P03"} if not feasible else set())
    for rid, p in ctx["req_anchor"].items():
        if rid in hit:
            K.obj(f"TGT_Alert_{rid}", *K.sphere(p, 11.0, 16, 8), K.mat(bad, 0.35), c,
                  info("requirement exceeded by the target", req_ids=rid), smooth=True)
    return {"basis": basis, "status": res["status"]}
