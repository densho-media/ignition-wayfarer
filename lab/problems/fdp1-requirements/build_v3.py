"""Build FDP-1_Spatial_Systems_V3.blend: V2 plus exploration modes, two camera families and P11 collision protection.

Run from the repository root:
    /snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_v3.py -- \
        [--accel 0.05] [--temp 1500] [--cone 0] [--margin 0] [--shield baseline|required] \
        [--render] [--shots] [--gltf] [--pct 50] [--only F1,S3] [--out DIR] [--no-board]

V2's builders are reused unchanged: import build_v2 does not build anything. V3 adds:
    V3_60_PROTECTION   envelope, exposure highlights, shield ghost, radiator exposure (fdp1diag/v3_layers.py)
    V3_70_CONSTRAINTS  per-family status board (fdp1diag/scenario_v3.py)
    P11 marker         from data/requirements_p11.json (data/requirements.json stays P01-P10)
    mission extras     delta-v, propellant per burn, reserve
    *__DETAIL          small labels moved into child collections, hidden unless "Detail labels" is on
Modes (sidebar or --mode): CLEAN, ENERGY, THERMAL, MASS_THRUST, MISSION, PROTECTION, ALL. Each camera carries its mode.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "fdp1diag"))

import bpy  # noqa: E402

import build_v2 as B2  # noqa: E402
import v2kit as K  # noqa: E402
import v3_layers as L3  # noqa: E402
from fdp1diag.protection import ENGINE_GROUPS, Protection  # noqa: E402
from fdp1diag.scenario_v3 import ScenarioV3  # noqa: E402

arg = B2.arg
ARGS = B2.ARGS
OUT_BLEND = os.path.join(HERE, "FDP-1_Spatial_Systems_V3.blend")
RENDER_DIR = arg("--out", os.path.join(HERE, "renders_v3"))
B2.RENDER_DIR = RENDER_DIR
PCT = arg("--pct", 100, int)
ONLY = arg("--only", None, lambda s: s.split(","))
ACCEL = arg("--accel", 0.05, float)
TEMP = arg("--temp", None, float)
CONE = arg("--cone", 0.0, float)
MARGIN = arg("--margin", 0.0, float)
SHIELD = arg("--shield", "baseline")

PR = Protection(geo=B2.GEO)
S3 = ScenarioV3(B2.SC, PR)
PARTS = {p["name"]: p for p in B2.GEO["parts"]}
P11 = json.load(open(os.path.join(HERE, "data", "requirements_p11.json")))["requirements"][0]
LOOP3 = B2.LOOPS[2]
CTX3 = {"x_s": PR.x_s, "x_fwd": PR.shield["x_fwd_m"], "x_aft": -300.0, "engine_groups": sorted(ENGINE_GROUPS),
        "engine_x": S3.engine0["at_x_m"], "x_label_exposure": -340.0, "board_x": -700.0, "board_z": 420.0,
        "engine_ghost_parts": [p["name"] for p in B2.GEO["parts"] if p["group"] in ("fdp1_nozzle", "fdp1_shield") and p["shape"] == "torus"]}
COLL3 = {}

MODES = {   # collections shown per mode (everything else hidden); requirement markers per mode
    "CLEAN": {"show": ["V2_00_PHYSICAL"], "req": []},
    "ENERGY": {"show": ["V2_00_PHYSICAL", "V2_10_BASELINE_INFO", "V2_11_FUSION_SOURCE", "V2_12_JET_AND_PLUME", "V2_13_RADIATION",
                        "V2_14_WASTE_HEAT", "V2_16_DRIVER_LOOP", "V2_30_REQUIREMENTS"], "req": ["P01", "P02", "P04", "P05"]},
    "THERMAL": {"show": ["V2_00_PHYSICAL", "V2_10_BASELINE_INFO", "V2_14_WASTE_HEAT", "V2_15_RADIATOR_REJECTION", "V2_20_TARGET",
                         "V2_30_REQUIREMENTS"], "req": ["P06", "P07"]},
    "MASS_THRUST": {"show": ["V2_00_PHYSICAL", "V2_10_BASELINE_INFO", "V2_17_THRUST", "V2_18_MASS_BUDGET", "V2_19_EQUIVALENT_MASS_CUBE",
                             "V2_20_TARGET", "V3_60_PROTECTION", "V3_61_PROTECTED_ENVELOPE", "V3_63_SHIELD_GHOST", "V3_70_CONSTRAINTS",
                             "V2_30_REQUIREMENTS"], "req": ["P03", "P09", "P11"]},
    "MISSION": {"show": ["V2_00_PHYSICAL", "V2_40_MISSION", "V2_30_REQUIREMENTS"], "req": ["P08", "P10"]},
    "PROTECTION": {"show": ["V2_00_PHYSICAL", "V3_60_PROTECTION", "V3_61_PROTECTED_ENVELOPE", "V3_62_CRITICAL_EXPOSURE",
                            "V3_63_SHIELD_GHOST", "V3_64_RADIATOR_EXPOSURE", "V2_30_REQUIREMENTS"], "req": ["P11", "P05"]},
}


# ---- V3 additions ------------------------------------------------------------------------------------------------
def build_p11_marker(root):
    p = (PR.x_s, 0.0, PR.shield["radius_m"])
    q = (PR.x_s + 40, -40.0, 120.0)
    B2.REQ_ANCHOR["P11"] = p
    c = K.coll("V2_3Y_REQ_P11", root)
    props = {"layer": "requirement", "req_ids": "P11", "title": P11["title"], "status": P11["status"],
             "classification": ",".join(P11["classification"]), "unresolved": "; ".join(P11["unresolved"]), "anchor": str(p)}
    K.obj("REQ_P11_Marker", *K.sphere(p, 3.2, 4, 2), K.mat("unresolved", 1.0, 1.1, 0.4), c, props)
    K.obj("REQ_P11_Leader", *K.tube([p, q], 0.3, 4), K.mat("unresolved", 0.8), c, props)
    K.label("REQ_P11_Label", f"P11  {P11['title']}", q, 7, "unresolved", c, props=props)
    K.label("REQ_P11_Status", "unresolved · geometric coverage only; stopping, ejecta, penetration TBD", (q[0], q[1], q[2] - 9), 4, "dim", c,
            props=props)


def build_mission_extras(c):
    V = B2.V
    s, x, Z = 0.4, -300.0, B2.MISSION_Z
    d1, d2, d3, d4 = (V(f"burn{i}.distance_AU") * s for i in (1, 2, 3, 4))
    mids = {"burn1": (x + d1 / 2, 40.0, "accelerate outbound"), "burn2": (x + d1 + d2 / 2, 40.0, "brake at the destination"),
            "burn3": (x + d1 + d2 - d3 / 2, -40.0, "accelerate home"), "burn4": (x + d4 / 2, -40.0, "brake at home")}
    for b, (xm, y, what) in mids.items():
        used = V(f"{b}.start_mass") - V(f"{b}.end_mass")
        side = TG_cube(used)
        K.obj(f"V3_Mission_{b}_Propellant", *K.box((xm, y, Z + 26 + side / 2), (side, side, side)), K.mat("propellant", 0.6), c,
              B2.info(f"{b} propellant used", [f"{b}.start_mass", f"{b}.end_mass"], "cube volume proportional to mass", mass_kg=used))
        K.label(f"V3_Mission_{b}_What", f"{what} · Δv 0.016 c · {used / 1e3:,.0f} t propellant", (xm, y, Z + 34 + side), 6, "propellant", c,
                props=B2.info("label"))
    res = V("mass.reserve")
    side = TG_cube(res)
    K.obj("V3_Mission_Reserve", *K.box((x - 40, 0, Z + side / 2), (side, side, side)), K.mat("unresolved", 0.7), c,
          B2.info("propellant reserve kept at the end", ["mass.reserve"], "cube volume proportional to mass", mass_kg=res))
    K.label("V3_Mission_Reserve_Label", f"reserve {res / 1e3:,.0f} t · margin policy UNKNOWN (P10)", (x - 40, 0, Z + side + 8), 5, "unresolved", c,
            props=B2.info("label", ["mass.reserve", "mission.margin_policy"]))
    K.label("V3_Mission_Velocity", "velocity 0 → 0.016 c → 0 → 0.016 c → 0  (four burns, Δv 0.064 c in all)", (x + 330, 0, Z - 70), 7, "exhaust", c,
            props=B2.info("label"))


def TG_cube(kg):
    return B2.TG.cube_side(kg, B2.M0)


def split_detail(roots):
    """Move small labels into <collection>__DETAIL children: numbers and sub-lines are an overlay, headlines stay."""
    for root in roots:
        for c in [root] + list(root.children_recursive):
            if c.name.endswith("__DETAIL"):
                continue
            small = [o for o in c.objects if o.type == "FONT" and o.data.size < 5.5]
            if not small:
                continue
            d = K.coll(c.name + "__DETAIL", c)
            for o in small:
                c.objects.unlink(o)
                d.objects.link(o)


def rebuild_scenario(sc, a, T, cone, margin, shield):
    res = S3.evaluate(a, T, "baseline_closure", cone, margin, 1.0, shield)
    B2.TG.build_target(res["v3"], B2.ctx(), B2.COLL["target"])
    sc["v2_target_result"] = json.dumps(B2.summary(res["v3"]))
    L3.build_envelope(res, CTX3, COLL3["env"])
    L3.build_exposure(res, CTX3, PARTS, COLL3["exp"])
    L3.build_shield_ghost(res, CTX3, COLL3["ghost"])
    L3.build_radiator_exposure(res, CTX3, PARTS, COLL3["rad"])
    L3.build_constraints(res, CTX3, COLL3["con"])
    sc["v3_result"] = json.dumps(L3.summary(res))
    return res


# ---- cameras -----------------------------------------------------------------------------------------------------
def build_cameras(sc, board):
    B2.COLL["cams"] = K.coll("V3_90_CAMERAS", None)
    cams = [  # name, loc, target, lens, ortho, mode, note
        ("CAM_F1_SHIP_OVERVIEW", (420, -560, 230), (-10, 0, 0), 30, None, "CLEAN", "spacecraft focus: the ship alone"),
        ("CAM_F2_ENERGY", (-620, -560, 160), (-170, 0, -10), 30, None, "ENERGY", "where the 17.3 TW goes"),
        ("CAM_F3_THERMAL", (-640, -720, -380), (-90, -120, -20), 30, None, "THERMAL", "deposits, manifolds, loops, wing roots"),
        ("CAM_F4_MASS_THRUST", (40, -4200, 0.15), (40, 0, 120), 100, None, "MASS_THRUST", "mass, thrust, feedback, constraints"),
        ("CAM_F5_MISSION", (50, -950, -330), (50, 0, -440), 42, None, "MISSION", "four burns, propellant, reserve, duration"),
        ("CAM_F6_FORWARD_SHIELD", (640, -330, 170), (235, 0, 0), 32, None, "PROTECTION", "the 90 m shield and what its shadow covers"),
        ("CAM_F7_PROPULSION_PROTECTION", (-760, -640, 250), (-250, 0, -40), 30, None, "PROTECTION", "engine hardware against the envelope"),
        ("CAM_S1_FULL_SPAN_TOP", (-45, 0, 6000), None, 50, 7900, "PROTECTION", "full physical scale: 7.15 km of wing from above"),
        ("CAM_S2_RADIATOR_ENVELOPE", (60, 700, 6000), None, 50, 2300, "PROTECTION", "radiator deployment envelope: the shadow strip on the wings"),
        ("CAM_S3_PROTECTION_SIDE", (-10, -6000, 0.15), (-10, 0, 0.15), 50, 1250, "PROTECTION", "full ship elevation: envelope vs engine"),
        ("CAM_S4_ACCELERATION_FEEDBACK", (480, -4200, 0.15), (480, 0, 120), 70, None, "MASS_THRUST", "baseline vs target, mass feedback"),
    ]
    for name, loc, tgt, lens, ortho, mode, note in cams:
        o = B2.camera(name, loc, tgt if tgt else (loc[0], loc[1], 0), lens, ortho=ortho, note=note)
        if tgt is None:
            o.rotation_euler = (0.0, 0.0, math.pi / 2)
        o["mode"] = mode
    if board is not None:
        bx, by, bz, W, H = board
        o = B2.camera("CAM_X_TECHNICAL_BOARD", (bx + W / 2 - 3, by - H / 2 + 36, bz + 500), (bx + W / 2 - 3, by - H / 2 + 36, bz), ortho=W + 10,
                      note="phase-1 technical support board")
        o["mode"] = "BOARD"
    sc.frame_start, sc.frame_end = 1, len(B2.CAMERAS)
    for i, o in enumerate(B2.CAMERAS):
        mk = sc.timeline_markers.new(o.name, frame=i + 1)
        mk.camera = o
    sc.camera = B2.CAMERAS[0]


def render(sc, tag="", only=None, detail=False):
    os.makedirs(RENDER_DIR, exist_ok=True)
    for i, o in enumerate(B2.CAMERAS):
        key = o.name.split("_")[1]
        if only and key not in only:
            continue
        sc.frame_set(i + 1)
        sc.camera = o
        K.VIEW["obj"].rotation_euler = o.rotation_euler
        L3.set_mode(sc, o["mode"], detail)
        sc.render.resolution_percentage = PCT
        sc.display.shading.light = "FLAT" if o["mode"] == "BOARD" else "STUDIO"
        sc.render.filepath = os.path.join(RENDER_DIR, f"{o.name}{tag}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", sc.render.filepath)
    sc.frame_set(1)
    sc.camera = B2.CAMERAS[0]
    sc.render.resolution_percentage = 100
    sc.display.shading.light = "STUDIO"
    L3.set_mode(sc, "CLEAN", False)


def embed(sc):
    B2.embed_texts()   # v2kit, v2_target, scenario, scenario_inputs, README, VISUAL_GRAMMAR, V2_controls (not registered in V3)
    t = bpy.data.texts.get("V2_controls.py")
    if t:
        bpy.data.texts.remove(t)
    for fn, tn in (("fdp1diag/protection.py", "protection.py"), ("fdp1diag/scenario_v3.py", "scenario_v3.py"),
                   ("fdp1diag/v3_layers.py", "v3_layers.py"), ("data/protection_inputs.json", "protection_inputs.json"),
                   ("data/ship_geometry.json", "ship_geometry.json"), ("data/requirements_p11.json", "requirements_p11.json"),
                   ("VALIDATION_V3.md", "VALIDATION_V3")):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            tx = bpy.data.texts.get(tn) or bpy.data.texts.new(tn)
            tx.clear()
            tx.write(open(p).read())
    t = bpy.data.texts.new("V3_controls.py")
    t.write(open(os.path.join(HERE, "fdp1diag", "v3_controls.py")).read())
    t.use_module = True
    return t


def main():
    sc = B2.reset_scene()
    sc.name = "FDP1_SPATIAL_V3"
    B2.view_align(sc)
    B2.build_physical()
    B2.COLL["base"] = base = K.coll("V2_10_BASELINE_INFO", None)
    B2.build_fusion(K.coll("V2_11_FUSION_SOURCE", base, "COLOR_02"))
    B2.build_jet(K.coll("V2_12_JET_AND_PLUME", base, "COLOR_05"))
    B2.build_radiation(K.coll("V2_13_RADIATION", base, "COLOR_07"))
    B2.build_heat(K.coll("V2_14_WASTE_HEAT", base, "COLOR_01"))
    B2.build_radiator_info(K.coll("V2_15_RADIATOR_REJECTION", base, "COLOR_01"))
    B2.build_driver_loop(K.coll("V2_16_DRIVER_LOOP", base, "COLOR_02"))
    B2.build_thrust(K.coll("V2_17_THRUST", base, "COLOR_05"))
    req = K.coll("V2_30_REQUIREMENTS", None, "COLOR_03")
    B2.build_requirements(req)
    build_p11_marker(req)
    B2.build_mass(K.coll("V2_18_MASS_BUDGET", base))
    mis = K.coll("V2_40_MISSION", None)
    B2.build_mission(mis)
    build_mission_extras(mis)
    B2.build_scale_key(K.coll("V2_50_SCALE_KEY", None))
    B2.COLL["target"] = K.coll("V2_20_TARGET", None, "COLOR_01")
    prot = K.coll("V3_60_PROTECTION", None, "COLOR_04")
    COLL3.update(env=K.coll("V3_61_PROTECTED_ENVELOPE", prot, "COLOR_04"), exp=K.coll("V3_62_CRITICAL_EXPOSURE", prot, "COLOR_01"),
                 ghost=K.coll("V3_63_SHIELD_GHOST", prot), rad=K.coll("V3_64_RADIATOR_EXPOSURE", prot, "COLOR_01"),
                 con=K.coll("V3_70_CONSTRAINTS", None, "COLOR_03"))
    res = rebuild_scenario(sc, ACCEL, TEMP, CONE, MARGIN, SHIELD)
    split_detail([base, req, mis, bpy.data.collections["V2_50_SCALE_KEY"]])
    board = None
    if "--no-board" not in ARGS:
        _, board = B2.build_layer_b(sc)
    build_cameras(sc, board)
    B2.setup_display(sc)
    ctl = embed(sc)
    sc["v2_ctx"] = json.dumps(B2.ctx())
    sc["v3_ctx"] = json.dumps(CTX3)
    sc["v3_modes"] = json.dumps(MODES)
    sc["fdp1_record"] = B2.GEO["meta"]["fdp1_record"] + " @ " + B2.GEO["meta"]["fdp1_record_commit"][:7]
    exec(compile(ctl.as_string(), ctl.name, "exec"), {"__name__": "__main__"})
    sc.v3_live = False
    sc.v2_accel, sc.v2_use_base_T, sc.v2_temp = ACCEL, TEMP is None, TEMP or 1500.0
    sc.v3_cone, sc.v3_margin, sc.v3_shield = CONE, MARGIN, SHIELD
    sc.v3_live = True
    L3.set_mode(sc, "CLEAN", False)
    print("objects", {c: len(bpy.data.collections[c].all_objects) for c in ("V2_00_PHYSICAL", "V2_10_BASELINE_INFO", "V3_60_PROTECTION")},
          res["constraints"]["Geometry"][0])
    if "--gltf" in ARGS:
        B2.export_gltf(sc)
    if "--render" in ARGS:
        render(sc, only=ONLY)
    if "--shots" in ARGS:
        for tag, kw, cams in (("__shield_required", dict(shield="required"), ["F6", "F7", "S3"]),
                              ("__cone_2.29deg", dict(cone=2.290610043), ["F7", "S3"]),
                              ("__1g_2500K", dict(a=1.0, T=2500.0), ["F4", "S4", "S2"])):
            a = kw.get("a", ACCEL)
            rebuild_scenario(sc, a, kw.get("T", TEMP), kw.get("cone", CONE), MARGIN, kw.get("shield", SHIELD))
            render(sc, tag, only=ONLY or cams)
        rebuild_scenario(sc, ACCEL, TEMP, CONE, MARGIN, SHIELD)
    B2.setup_viewports()
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print("saved", OUT_BLEND)


if __name__ == "__main__":
    main()
