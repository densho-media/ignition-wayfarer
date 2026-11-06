"""Build FDP-1_Spatial_Systems_V2.blend: Wayfarer with FDP-1 as the centrepiece, information geometry attached to the hardware.

Run from the repository root:
    /snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_v2.py -- \
        [--accel 0.25] [--temp 2000] [--scaling baseline_closure|goal_1g_variant] \
        [--render] [--cases] [--gltf] [--pct 50] [--only 01,05] [--out DIR] [--no-board]

Inputs (read only, never written):
    data/ship_geometry.json    physical blockout (export_geometry.py: Wayfarer baseline fingerprint + FDP-1 record geometry)
    data/scenario_inputs.json  closure inputs copied from the FDP-1 record, each with its record path
    data/fdp1_parameters.json  the FDP-1 parameter set of phases 1 and 2 (ledger, masses, radiation, mission)
    data/requirements.json     P01-P10
Layers:
    V2_00_PHYSICAL             hardware, 1 BU = 1 m, muted colours (the superseded four-nozzle drive is hidden)
    V2_10_BASELINE_INFO        today's FDP-1 numbers as information geometry on the hardware that makes or carries them
    V2_20_TARGET               ghosts for the selected acceleration and warm-loop temperature (fdp1diag/v2_target.py)
    V2_30_REQUIREMENTS         P01-P10, one child collection each
    V2_40_MISSION              the four-burn trajectory (secondary)
    V2_50_SCALE_KEY            the encoding key
    LAYER_B_TECHNICAL_SUPPORT  the phase-1 board, hidden, for its own camera
Encodings are declared in VISUAL_GRAMMAR.md (V2 section), on the scale key and on every information object.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "fdp1diag"))

import bpy  # noqa: E402
import mathutils  # noqa: E402

import v2kit as K  # noqa: E402
import v2_target as TG  # noqa: E402
from fdp1diag.model import Model  # noqa: E402
from fdp1diag.scenario import Scenario  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None, cast=str):
    return cast(ARGS[ARGS.index(name) + 1]) if name in ARGS else default


OUT_BLEND = os.path.join(HERE, "FDP-1_Spatial_Systems_V2.blend")
RENDER_DIR = arg("--out", os.path.join(HERE, "renders_v2"))
PCT = arg("--pct", 100, int)
ONLY = arg("--only", None, lambda s: s.split(","))
ACCEL = arg("--accel", None, float)
TEMP = arg("--temp", None, float)
SCALING = arg("--scaling", "baseline_closure")
CASES = [(None, None), (0.05, None), (0.10, 1500.0), (0.25, 2000.0), (1.00, 2500.0)]   # None = the record a0, 0.0069 g

M = Model()
bad = [c for c in M.checks if not c["ok"]]
if bad:
    raise SystemExit("validation failed: " + "; ".join(f"{c['name']}: {c['detail']}" for c in bad))
V = M.v
SC = Scenario()
CASES[0] = (SC.a0_base, None)
GEO = json.load(open(os.path.join(HERE, "data", "ship_geometry.json")))
REQ = {r["id"]: r for r in json.load(open(os.path.join(HERE, "data", "requirements.json")))["requirements"]}
LAY = GEO["meta"]["layout"]
LOOPS = GEO["meta"]["nozzle_loops"]
WINGS = GEO["meta"]["wings"]
XB = LAY["x_burn"]
BASE = SC.evaluate(SC.a0_base)
B0 = BASE["closed"]
P0 = B0["fusion_W"]
M0 = B0["departure_kg"]
COLL = {}

# ---- layout of the information layer (metres, ship frame) -------------------------------------------------------
MASS_RAIL_Z = 190.0            # per-component mass cubes sit on this plane above their hardware
CMP_FLOOR_Z = -30.0            # comparison bay ahead of the bow: departure, engine and feedback cubes
CMP_X_DEPART, CMP_X_ENGINE, CMP_X_FEEDBACK = 360.0, 455.0, 520.0
ARROW_X, ARROW_Z, ARROW_Z_TGT = -100.0, -150.0, -178.0
HOT_MAN = (-186.0, 0.0, -34.0)   # hot-loop manifold node (where the record's hot lines meet behind the shield)
WARM_MAN = (-140.0, 0.0, -34.0)  # warm-loop manifold node (aft ends of the gallery warm headers)
BANNER = (-20.0, 450.0)
MISSION_Z = -470.0


def ctx():
    return {"fusion_W": P0, "departure_kg": M0, "x_burn": XB, "arrow_x": ARROW_X, "arrow_z": ARROW_Z_TGT,
            "wing_x0": LAY["wing_aft_x"], "wing_x1": LAY["wing_forward_x"],
            "wing_base_r": WINGS["warm_root_radius_m"] - WINGS["hot_band_m"], "wing_az": WINGS["azimuths_deg"],
            "mass_rail_z": CMP_FLOOR_Z, "mass_rail_x_engine": CMP_X_ENGINE, "mass_rail_x_feedback": CMP_X_FEEDBACK,
            "banner_x": BANNER[0], "banner_z": BANNER[1], "req_anchor": REQ_ANCHOR,
            "wing_tip_design_m": WINGS["tip_radius_m"], "tgt_rad_label_y": 700.0}


def fmtP(w):
    return TG.fmtP(w)


def t_(kg):
    return f"{kg / 1e3:,.0f} t"


def info(component, keys=(), encoding="", reqs=None, **kw):
    reqs = reqs if reqs is not None else sorted({r for k in keys for r in M.meta(k).get("req", [])})
    d = {"layer": "information", "state": "baseline", "component": component, "encoding": encoding,
         "param_keys": ",".join(keys), "req_ids": ",".join(reqs),
         "classes": ",".join(sorted({M.cls(k) for k in keys})) if keys else ""}
    d.update(kw)
    return d


# ================================================================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "FDP1_SPATIAL_V2"
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    w = bpy.data.worlds.new("V2_World")
    bg = K.lin((0.016, 0.019, 0.026))
    w.color = bg
    w.use_nodes = True
    n = w.node_tree.nodes.get("Background")
    if n:
        n.inputs[0].default_value = (*bg, 1)
    sc.world = w
    return sc


def view_align(sc):
    e = bpy.data.objects.new("VIEW_ALIGN", None)
    sc.collection.objects.link(e)
    for i in range(3):
        drv = e.driver_add("rotation_euler", i).driver
        drv.type = "SCRIPTED"
        v = drv.variables.new()
        v.name = "r"
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "SCENE"
        v.targets[0].id = sc
        v.targets[0].data_path = f"camera.rotation_euler[{i}]"
        drv.expression = "r"
    e.hide_render = True
    K.VIEW["obj"] = e
    return e


# ---- physical layer ---------------------------------------------------------------------------------------------
GROUP_COLL = {"hull": "V2_01_WAYFARER_HULL_AND_SPINE", "engineering": "V2_01_WAYFARER_HULL_AND_SPINE",
              "habitat": "V2_02_WAYFARER_HABITAT_RINGS", "storage": "V2_03_WAYFARER_PROPELLANT_STORAGE",
              "bow": "V2_04_FORWARD_SHIELD_AND_BOW", "radiators": "V2_05_WAYFARER_RADIATORS",
              "fdp1_tanks": "V2_03_WAYFARER_PROPELLANT_STORAGE",
              "fdp1_structure": "V2_06_FDP1_THRUST_STRUCTURE", "fdp1_service": "V2_06_FDP1_THRUST_STRUCTURE",
              "fdp1_fuel_prep": "V2_07_FDP1_TARGET_FACTORY_AND_POWER", "fdp1_power": "V2_07_FDP1_TARGET_FACTORY_AND_POWER",
              "fdp1_sensors": "V2_07_FDP1_TARGET_FACTORY_AND_POWER",
              "fdp1_drivers": "V2_08_FDP1_DRIVER_GALLERIES", "fdp1_reaction": "V2_09_FDP1_REACTION_POINT",
              "fdp1_nozzle": "V2_09_FDP1_MAGNETIC_NOZZLE_LOOPS", "fdp1_shield": "V2_09_FDP1_SHADOW_SHIELD",
              "fdp1_thermal": "V2_05_FDP1_THERMAL_WINGS_AND_LINES", "superseded": "V2_99_SUPERSEDED_FOUR_NOZZLE_DRIVE"}


def part_mesh(p):
    s = p["shape"]
    if s == "ring":
        return K.ring(p["x0"], p["x1"], p.get("r0", 0.0), p["r1"], p.get("arc"), tuple(p.get("centre", (0.0, 0.0))))
    if s == "frustum":
        return K.frustum(p["x0"], p["r0"], p["x1"], p["r1"], p.get("ri0"), p.get("ri1"), p.get("arc"),
                         tuple(p.get("centre", (0.0, 0.0))))
    if s == "torus":
        return K.torus(p["x"], p["R"], max(p["a"], 0.12), p.get("arc"))
    if s == "box":
        return K.box(p["centre"], p["size"], p.get("roll", 0.0))
    if s == "panel":
        return K.panel(p["corners"], p.get("thickness", 0.3))
    if s == "tube":
        return K.tube(p["points"], max(p["radius"], 0.08), 8)
    if s == "capsule":
        return K.capsule(p["x0"], p["x1"], p["radius"], tuple(p["centre"]))
    raise ValueError(s)


def build_physical():
    root = K.coll("V2_00_PHYSICAL", None)
    COLL["phys"] = root
    for p in GEO["parts"]:
        cname = GROUP_COLL[p["group"]]
        c = COLL.get(cname) or K.coll(cname, root)
        COLL[cname] = c
        func = p["func"] if p["func"] in K.PAL else "STRUCTURE"
        k = {"ENGINEERED": 1.0, "PLACEHOLDER": 1.18, "SUPERSEDED": 0.8, "ILLUSTRATIVE": 1.25}.get(p["status"], 1.0)
        wing = p["group"] == "fdp1_thermal" and p["shape"] == "panel"
        alpha = 0.6 if wing else p.get("alpha", 1.0)
        K.obj(p["name"], *part_mesh(p), K.mat(func, alpha, k * (0.6 if wing else 1.0)), c,
              {"layer": "physical", "group": p["group"], "function": p["func"], "status": p["status"],
               "source": p.get("source", ""), "units": "m"}, smooth=p["shape"] in ("capsule", "torus"))
    sup = COLL["V2_99_SUPERSEDED_FOUR_NOZZLE_DRIVE"]
    sup.hide_render = True
    # the FDP-1 record moves the bow 122.4 m forward (tank option T-B); the bay between is not designed (P08)
    c = COLL["V2_03_WAYFARER_PROPELLANT_STORAGE"]
    K.obj("V2_Bow_Shift_Undesigned_Bay", *K.ring(144.75, 144.75 + GEO["meta"]["bow_shift_m"] - 6.0, 0.0, 6.5),
          K.mat("unresolved", 0.12), c, {"layer": "physical", "status": "UNRESOLVED", "group": "bow",
                                         "note": "bow moved +122.4 m for the T-B tank farm; bay frames not designed (P08)"})


# ---- geometry helpers ------------------------------------------------------------------------------------------
def group_bbox(groups, names=None):
    xs, rs = [], []
    for p in GEO["parts"]:
        if p["group"] not in groups or (names and not any(n in p["name"] for n in names)):
            continue
        s = p["shape"]
        if s in ("ring", "frustum", "capsule"):
            xs += [p["x0"], p["x1"]]
            rs.append(max(p.get("r1", 0), p.get("r0", 0), p.get("radius", 0)) + math.hypot(*p.get("centre", (0, 0))))
        elif s == "torus":
            xs.append(p["x"])
            rs.append(p["R"])
        elif s == "box":
            xs += [p["centre"][0] - p["size"][0] / 2, p["centre"][0] + p["size"][0] / 2]
            rs.append(math.hypot(p["centre"][1], p["centre"][2]) + max(p["size"][1:]) / 2)
        elif s in ("tube", "panel"):
            pts = p["points"] if s == "tube" else p["corners"]
            xs += [q[0] for q in pts]
            rs += [math.hypot(q[1], q[2]) for q in pts]
    return min(xs), max(xs), max(rs)


# ---- fusion, jet and plume -------------------------------------------------------------------------------------
def build_fusion(c):
    r = TG.sphere_r(P0, P0)
    K.obj("V2_Fusion_Sphere", *K.sphere((XB, 0, 0), r), K.mat("fusion", 0.22, 1.0, 0.4), c,
          info("gross fusion power at the reaction point", ["fusion.power"], "sphere volume proportional to power",
               value_W=P0, radius_m=r), smooth=True)
    K.obj("V2_Fusion_Sphere_Equator", *K.torus(XB, r, 0.35), K.mat("fusion", 1.0), c, info("fusion sphere equator"))
    K.label("V2_Fusion_Label", f"FUSION  {fmtP(P0)}", (XB, 0, r + 14), 8, "fusion", c, props=info("label"))
    K.label("V2_Fusion_Sub", "D-³He pulses at the burn point · power in W", (XB, 0, r + 6), 4, "dim", c, props=info("label"))


def build_jet(c):
    Pj = V("ledger.jet")
    r, thin = TG.tube_r(Pj, P0)
    x_end = XB - 520
    K.obj("V2_Jet_Collimated", *K.tube([(XB, 0, 0), (LOOPS[2]["x"], 0, 0), (x_end, 0, 0)], r, 32), K.mat("exhaust", 0.38, 1.0, 0.3), c,
          info("collimated jet through the magnetic nozzle", ["ledger.jet", "prop.jet_power", "prop.eta_jet"],
               "tube cross-section proportional to power", value_W=Pj, radius_m=r, drawn_min=int(thin)), smooth=True)
    K.label("V2_Jet_Label", f"JET  {fmtP(Pj)}", (XB - 330, 0, r + 20), 9, "exhaust", c, props=info("label"))
    K.label("V2_Jet_Sub", f"makes the thrust: F = 2·P_jet / v_e = {V('prop.thrust') / 1e6:.2f} MN", (XB - 330, 0, r + 10), 4.5, "dim", c,
            props=info("label"))
    # the uncollimated plasma: 8 schematic lobes (spread angle not in the record), total cross-section = its power
    Pu = V("ledger.plume_to_space")
    ru = TG.tube_r(Pu, P0)[0] / math.sqrt(8)
    items = []
    for k in range(8):
        az = math.radians(22.5 + 45 * k)
        d = (-math.cos(math.radians(55)), math.sin(math.radians(55)) * math.cos(az), math.sin(math.radians(55)) * math.sin(az))
        p = (XB + d[0] * 30, d[1] * 30, d[2] * 30)
        q = (XB + d[0] * 300, d[1] * 300, d[2] * 300)
        items.append((p, q, ru, ru * 1.6))
    K.obj("V2_Plume_Uncollimated", *K.cones(items, 12), K.mat("exhaust", 0.16, 0.85), c,
          info("uncollimated plasma to space (no thrust)", ["ledger.plume_to_space"],
               "total cross-section of the 8 lobes proportional to power; spread angle schematic (not in the record)",
               value_W=Pu))
    K.label("V2_Plume_Label", f"UNCOLLIMATED PLASMA  {fmtP(Pu)}  · disperses, no thrust", (XB - 140, 0, -250), 6, "exhaust", c,
            props=info("label"), k=0.85)


def fib_dirs(n):
    g = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        x = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - x * x)
        out.append((x, r * math.cos(g * i), r * math.sin(g * i)))
    return out


def build_radiation(c):
    N = 600
    dirs = fib_dirs(N)
    to_space, on_hw = V("ledger.radiation_to_space"), V("ledger.radiation_on_hardware")
    sh_n = round(N * V("geom.solid_angle_shield"))
    used = set(sorted(range(N), key=lambda i: -dirs[i][0])[:sh_n])
    hits, free = [], []
    xs = LAY["x_shield_aft"]
    for i in used:
        d = dirs[i]
        s = (xs - XB) / d[0]
        hits.append(("shadow shield", (XB + d[0] * 26, d[1] * 26, d[2] * 26), (XB + d[0] * s, d[1] * s, d[2] * s)))
    for L in LOOPS:
        n = max(1, round(N * L["solid_angle_share"]))
        ph = math.radians(L["phi_deg"])
        cand = sorted((i for i in range(N) if i not in used), key=lambda i: abs(math.acos(max(-1, min(1, dirs[i][0]))) - ph))[:n]
        for i in cand:
            used.add(i)
            az = math.atan2(dirs[i][2], dirs[i][1])
            u = (math.cos(ph), math.sin(ph) * math.cos(az), math.sin(ph) * math.sin(az))
            hits.append((L["name"], (XB + u[0] * 26, u[1] * 26, u[2] * 26), (XB + u[0] * L["d"], u[1] * L["d"], u[2] * L["d"])))
    n_st = round(N * V("geom.solid_angle_struts"))
    for i in sorted((i for i in range(N) if i not in used), key=lambda i: abs(dirs[i][0] + 0.3))[:n_st]:
        used.add(i)
        d = dirs[i]
        hits.append(("nozzle struts", (XB + d[0] * 26, d[1] * 26, d[2] * 26), (XB + d[0] * 80, d[1] * 80, d[2] * 80)))
    for i in range(N):
        if i in used:
            continue
        d = dirs[i]
        free.append(((XB + d[0] * 26, d[1] * 26, d[2] * 26), (XB + d[0] * 115, d[1] * 115, d[2] * 115), 0.22, 0.03))
    per = (to_space + on_hw) / N
    K.obj("V2_Radiation_To_Space", *K.cones(free, 5), K.mat("radiation", 0.4, 1.0, 0.3), c,
          info("X-rays and neutrons escaping to space", ["ledger.radiation_to_space", "shield.xray_escape", "shield.neutron_escape"],
               f"{N} straight rays share {fmtP(to_space + on_hw)}; one ray = {fmtP(per)}; rays per target proportional to solid angle",
               rays=len(free), value_W=to_space))
    K.obj("V2_Radiation_On_Hardware", *K.cones([(p, q, 0.45, 0.45) for _, p, q in hits], 6), K.mat("radiation", 1.0, 1.15, 0.6), c,
          info("radiation intercepted by hardware", ["ledger.radiation_on_hardware", "geom.solid_angle_total", "geom.solid_angle_shield",
                                                    "geom.solid_angle_loops", "geom.solid_angle_struts"],
               "rays ending on the hardware they hit (shield, three loops, struts) by the record's solid-angle shares",
               rays=len(hits), value_W=on_hw, targets=",".join(sorted({h[0] for h in hits}))))
    for k, (_, _, q) in enumerate(hits):
        K.obj(f"V2_Radiation_Hit_{k:02d}", *K.sphere(q, 1.6, 12, 6), K.mat("radiation", 1.0, 1.25, 0.8), c, info("radiation hit"))
    K.label("V2_Radiation_Label", f"RADIATION  {fmtP(to_space + on_hw)}", (XB + 20, 0, -140), 7, "radiation", c, props=info("label"))
    K.label("V2_Radiation_Sub", f"{V('geom.solid_angle_total') * 100:.2f} % of the sphere hits hardware ({fmtP(on_hw)}) · "
            "straight lines: magnetic fields do not bend photons or neutrons", (XB + 20, 0, -149), 3.6, "dim", c, props=info("label"))


# ---- heat, manifolds, radiators --------------------------------------------------------------------------------
def heat_tube(name, P, pts, c, comp, keys, loop):
    r, thin = TG.tube_r(P, P0)
    path = K.bez(*pts) if len(pts) == 4 else pts
    K.obj(name, *K.tube(path, r, 10), K.mat("thermal", 0.85 if loop == "hot" else 0.6, 1.1 if loop == "hot" else 0.8), c,
          info(comp, keys, "tube cross-section proportional to power", value_W=P, radius_m=r, drawn_min=int(thin), loop=loop),
          smooth=True)


def build_heat(c):
    L1, L2, L3 = LOOPS
    src_hot = [
        ("plume on nozzle loops", "hot.plume_on_hardware", (L2["x"], 0, -L2["r"])),
        ("radiation on nozzle loops", "hot.radiation_on_nozzle_loops", (L1["x"], 0, -L1["r"])),
        ("radiation on nozzle struts", "hot.radiation_on_nozzle_struts", (L3["x"], 0, -L3["r"])),
        ("radiation on shadow shield", "hot.radiation_on_shadow_shield", (LAY["x_shield_aft"] + 1.8, 0, -20.0)),
        ("power recovery conversion loss", "hot.recovery_conversion_loss", (-150.75, 0, -5.7)),
    ]
    src_warm = [
        ("power and target systems", "warm.power_and_target_systems", (-155.75, 0, -4.2)),
        ("driver waste heat", "warm.driver_waste", (-40.0, -5.5, -10.0)),
        ("cryoplant input", "warm.cryoplant_input", (-160.25, 0, -5.7)),
        ("coil conductor heating", "warm.coil_conductor_heating", (L2["x"], 0, -L2["r"] + 2)),
    ]
    for comp, key, p in src_hot:
        m = HOT_MAN
        heat_tube(f"V2_Heat_Hot_{comp.replace(' ', '_').title()}", V(key), [p, (p[0], 0, m[2] - 8), (m[0] - 6, 0, m[2]), m], c,
                  comp, [key], "hot")
    for comp, key, p in src_warm:
        m = WARM_MAN
        heat_tube(f"V2_Heat_Warm_{comp.replace(' ', '_').title()}", V(key), [p, (p[0], p[1], m[2] - 6), (m[0] + 6, 0, m[2]), m], c,
                  comp, [key], "warm")
    for name, m, key, loop in (("Hot", HOT_MAN, "thermal.hot_total", "hot"), ("Warm", WARM_MAN, "thermal.warm_total", "warm")):
        r = TG.tube_r(V(key), P0)[0] * 1.6
        K.obj(f"V2_Manifold_{name}", *K.sphere(m, r, 20, 10), K.mat("thermal", 1.0, 1.2 if loop == "hot" else 0.85), c,
              info(f"{loop}-loop manifold (collection node)", [key], "node; the outgoing tubes carry the loop total",
                   value_W=V(key), loop=loop), smooth=True)
    # manifolds -> radiators: hot to the two wing hot bands and the existing Wayfarer hot blades; warm to the wing warm fields
    Ah, reuse = V("rad.hot_area"), V("rad.existing_hot_blades_area")
    f_blade = reuse / Ah
    Ph, Pw = V("thermal.hot_total"), V("thermal.warm_total")
    x0 = LAY["wing_aft_x"]
    hb, wr = WINGS["warm_root_radius_m"] - WINGS["hot_band_m"], WINGS["warm_root_radius_m"]
    for s, side in ((1, "Port"), (-1, "Starboard")):
        heat_tube(f"V2_Heat_Hot_To_Wing_{side}", Ph * (1 - f_blade) / 2,
                  [HOT_MAN, (HOT_MAN[0] + 4, s * 4, HOT_MAN[2] + 20), (x0 + 6, s * (hb + 4), 0), (x0 + 10, s * (hb + 30), 0)], c,
                  f"hot loop to the {side.lower()} wing hot band", ["thermal.hot_total", "rad.hot_area"], "hot")
        heat_tube(f"V2_Heat_Warm_To_Wing_{side}", Pw / 2,
                  [WARM_MAN, (WARM_MAN[0], s * 30, WARM_MAN[2] + 10), (WARM_MAN[0], s * (wr - 30), 0), (WARM_MAN[0], s * (wr + 40), 0)], c,
                  f"warm loop to the {side.lower()} wing warm field", ["thermal.warm_total", "rad.warm_area"], "warm")
    heat_tube("V2_Heat_Hot_To_Wayfarer_Blades", Ph * f_blade,
              [HOT_MAN, (HOT_MAN[0] + 30, 0, -40), (-140, 0, -30), (-120, 0, -24)], c,
              "hot loop to the existing Wayfarer hot blades (reused area)", ["thermal.hot_total", "rad.existing_hot_blades_area"], "hot")
    K.label("V2_Heat_Label", f"WASTE HEAT  hot {fmtP(Ph)}  ·  warm {fmtP(Pw)}", (-175, 0, -96), 7, "thermal", c, props=info("label"))
    K.label("V2_Heat_Sub", "deposits → manifolds → radiators · separate loops (hot 1,800 K, warm 600 K)", (-175, 0, -104), 3.6, "dim", c,
            props=info("label"))


def build_radiator_info(c):
    eps, sig = V("rad.emissivity"), V("const.sigma")
    x0, x1 = LAY["wing_aft_x"], LAY["wing_forward_x"]
    Ah, Aw = V("rad.hot_area"), V("rad.warm_area")
    hb, wr, tip = WINGS["warm_root_radius_m"] - WINGS["hot_band_m"], WINGS["warm_root_radius_m"], WINGS["tip_radius_m"]
    # rejection check P = eps sigma (2A) T^4 printed on the wing (two emitting faces, 0 K sink, no mutual view)
    for loop, A, T, ypos, key in (("HOT", Ah, V("rad.hot_T"), (hb + wr) / 2, "thermal.hot_total"),
                                  ("WARM", Aw, V("rad.warm_T"), 1700.0, "thermal.warm_total")):
        P = eps * sig * 2 * A * T ** 4
        K.label(f"V2_Radiator_{loop}_Label", f"{loop} {T:,.0f} K  ·  planform {A / 1e6:,.3g} km²  ·  emitting 2 × {A / 1e6:,.3g} km²",
                ((x0 + x1) / 2, ypos, -300 if loop == "WARM" else 6), 24 if loop == "WARM" else 6, "thermal", c,
                props=info("radiator rejection", ["rad.hot_area" if loop == "HOT" else "rad.warm_area"], "true planform area",
                           check_W=P, heat_W=V(key)))
        K.label(f"V2_Radiator_{loop}_Sub", f"P = ε σ (2A) T⁴ = {fmtP(P)}  (heat {fmtP(V(key))})  · ε {eps}  · sink 0 K",
                ((x0 + x1) / 2, ypos, -328 if loop == "WARM" else -2), 14 if loop == "WARM" else 3.6, "dim", c, props=info("label"))
    K.label("V2_Radiator_Tip", f"wing tip  r = {tip / 1e3:.2f} km  (designed envelope)", ((x0 + x1) / 2, tip - 60, 10), 30, "thermal", c,
            props=info("wing tip", ["rad.wing_tip_radius"]))
    K.label("V2_Radiator_Mutual", "two coplanar wings: no mutual view (record) · wings ↔ Wayfarer blades: view factor not modelled (P07)",
            ((x0 + x1) / 2, 560, -120), 10, "unresolved", c, props=info("label", reqs=["P07"]))
    K.obj("V2_Radiator_Tip_Marker_Port", *K.tube([(x0, tip, 0), (x1, tip, 0)], 3.0), K.mat("thermal", 1.0), c, info("wing tip", ["rad.wing_tip_radius"]))
    # (the starboard tip is drawn only by the wing itself: the side cameras look across it)


def build_driver_loop(c):
    """The recirculating driver loop, drawn thinner and dimmer: it is subordinate to the main energy flow."""
    Pw, Pb, Prec = V("driver.wall_plug_power"), V("driver.beam_power"), V("power.recovered")
    L1 = LOOPS[0]
    mat = K.mat("fusion", 0.55, 0.7)
    r, thin = TG.tube_r(Prec, P0)
    K.obj("V2_Driver_Loop_Recovery", *K.tube(K.bez((L1["x"], 0, L1["r"]), (L1["x"] + 8, 0, 48), (-160, 0, 26), (-151, 0, 6)), r, 8), mat, c,
          info("plasma energy recovered by the nozzle loops", ["power.recovered"], "tube cross-section proportional to power",
               value_W=Prec, drawn_min=int(thin), subordinate=1), smooth=True)
    r, thin = TG.tube_r(Pw, P0)
    K.obj("V2_Driver_Loop_Wall_Plug", *K.tube(K.bez((-149, 0, 6), (-146, 0, 14), (-140, 0, 16), (-60, 0, 16)), r, 8), mat, c,
          info("electric power into the heavy-ion drivers", ["driver.wall_plug_power"], "tube cross-section proportional to power",
               value_W=Pw, drawn_min=int(thin), subordinate=1), smooth=True)
    r, thin = TG.tube_r(Pb, P0)
    K.obj("V2_Driver_Loop_Beams", *K.tube(K.bez((-60, 0, 18.5), (-150, 0, 18.5), (-200, 0, 10), (XB + 26, 0, 1)), r, 8),
          K.mat("fusion", 0.8, 1.1), c,
          info("ion beams into the target (9 beams)", ["driver.beam_power", "driver.beams"], "tube cross-section proportional to power",
               value_W=Pb, drawn_min=int(thin), subordinate=1), smooth=True)
    K.label("V2_Driver_Loop_Label", f"driver loop {fmtP(Pw)} in · {fmtP(Pb)} beams · {fmtP(Prec)} recovered", (-120, 0, 40), 4, "fusion", c,
            props=info("label"), k=0.8)


# ---- thrust and mass --------------------------------------------------------------------------------------------
def build_thrust(c):
    F = V("prop.thrust")
    L = F * TG.ENC["M_PER_N"]
    K.obj("V2_Thrust_Arrow", *K.tube([(ARROW_X, 0, ARROW_Z), (ARROW_X + L - 30, 0, ARROW_Z)], 2.5), K.mat("exhaust", 1.0), c,
          info("thrust on the ship", ["prop.thrust"], "arrow length proportional to force, 1 m = 5 kN", value_N=F, length_m=L))
    K.obj("V2_Thrust_Arrow_Head", *K.tube([(ARROW_X + L - 30, 0, ARROW_Z), (ARROW_X + L, 0, ARROW_Z)], 8, 10, 0.01), K.mat("exhaust", 1.0), c,
          info("thrust on the ship", ["prop.thrust"]))
    K.label("V2_Thrust_Label", f"THRUST {F / 1e6:.2f} MN → {V('prop.a0_g'):.4f} g at {t_(M0)}", (ARROW_X + L / 2, 0, ARROW_Z + 14), 8,
            "exhaust", c, props=info("label"))
    K.obj("V2_Thrust_Leader", *K.tube([(XB, 0, -LOOPS[2]["r"] * 0.0 - 20), (XB, 0, ARROW_Z), (ARROW_X, 0, ARROW_Z)], 0.4), K.mat("dim", 0.6), c,
          info("thrust acts at the nozzle loops"))


MASS_ITEMS = [  # mass.<item> of the record budget -> the hardware it belongs to (x of the anchor, z of the tether foot)
    ("payload (non-propulsion ship)", "Wayfarer ship (habitat, hull, shields)", 20.0, 30.0, "structure"),
    ("drivers (heavy-ion linacs, storage)", "driver galleries", -33.6, 13.0, "fusion"),
    ("nozzle loops (virial structure)", "magnetic nozzle loops", LOOPS[1]["x"], LOOPS[1]["r"], "fiji"),
    ("loop armour", "magnetic nozzle loops", LOOPS[2]["x"], LOOPS[2]["r"], "fiji"),
    ("target factory, injectors, cryo-targets, misc", "target factory and injectors", -158.0, 6.0, "fusion"),
    ("shadow shield", "shadow shield", -182.5, 43.0, "radiation"),
    ("FDP-1 structure", "FDP-1 thrust structure and spars", -162.0, 8.0, "structure"),
    ("hot radiators", "wing hot bands", -110.0, 3.0, "thermal"),
    ("warm radiators", "wing warm fields", -45.0, 3.0, "thermal"),
    ("low loop radiator", "low-loop panels", 196.0, 3.0, "thermal"),
    ("tankage (required volume)", "propellant tank farm", 205.0, 30.0, "propellant"),
    ("idle hydrogen vessels", "Wayfarer hydrogen vessels", 123.0, 30.0, "propellant"),
    ("propellant reserve and allowances", "propellant tank farm", 225.0, 30.0, "propellant"),
    ("propellant (four burns)", "propellant tank farm", 160.0, 30.0, "propellant"),
]


def build_mass(c):
    items = []
    for key, comp, x, zf, col in MASS_ITEMS:
        kg = V("mass." + key)
        s = TG.cube_side(kg, M0)
        items.append([x, s, key, comp, zf, col, kg, x])
    zero = [k for k in M.doc["parameters"] if k.startswith("mass.") and " " in k and M.v(k) == 0.0]
    items.sort(key=lambda it: it[0])
    for _ in range(400):  # relax overlaps along X, keep each cube as close to its hardware as possible
        moved = False
        for a, b in zip(items, items[1:]):
            gap = (a[1] + b[1]) / 2 + 6 - (b[0] - a[0])
            if gap > 0:
                a[0] -= gap / 2
                b[0] += gap / 2
                moved = True
        if not moved:
            break
    for x, s, key, comp, zf, col, kg, x_hw in items:
        nm = "V2_Mass_" + key.split(" (")[0].replace(",", "").replace(" ", "_").title()
        K.obj(nm, *K.box((x, 0, MASS_RAIL_Z + s / 2), (s, s, s)), K.mat(col, 0.55, 0.9), c,
              info(comp, ["mass." + key], "cube volume proportional to mass (60 m cube = 20,760 t)", mass_kg=kg, side_m=s,
                   budget_item=key))
        K.obj(nm + "_Edges", *K.wire_cube((x, 0, MASS_RAIL_Z + s / 2), s, 0.35), K.mat(col, 1.0, 1.2), c, info(comp))
        K.obj(nm + "_Tether", *K.tube([(x, 0, MASS_RAIL_Z), (x_hw, 0, zf)], 0.22, 4), K.mat("dim", 0.45), c,
              info("tether to its hardware", ["mass." + key]))
        K.label(nm + "_Label", f"{t_(kg)}", (x, 0, MASS_RAIL_Z + s + 5), max(3.0, min(7.0, s * 0.18)), "text", c, props=info("label"))
        K.label(nm + "_Name", key.split(" (")[0], (x, 0, MASS_RAIL_Z + s + 5 + max(3.0, min(7.0, s * 0.18)) * 1.2), 2.6, "dim", c,
                props=info("label"))
    K.label("V2_Mass_Title", f"MASS BUDGET  departure {t_(M0)}  (record items; cube volume ∝ mass)", (0, 0, MASS_RAIL_Z + 92), 8, "text", c,
            props=info("label", ["mass.departure"]))
    if zero:
        K.label("V2_Mass_Zero_Items", "zero in the record: " + ", ".join(k[5:] for k in zero), (0, 0, MASS_RAIL_Z + 84), 3.4, "dim", c,
                props=info("label"))
    # comparison bay ahead of the bow: equivalent departure-mass cube and today's power-scaled engine
    ce = K.coll("V2_19_EQUIVALENT_MASS_CUBE", COLL["base"])
    s0 = TG.ENC["MASS_SIDE0"]
    K.obj("V2_Equivalent_Departure_Mass", *K.box((CMP_X_DEPART, 0, CMP_FLOOR_Z + s0 / 2), (s0, s0, s0)), K.mat("structure", 0.18), ce,
          info("whole ship at departure", ["mass.departure"], "cube volume proportional to mass", mass_kg=M0, side_m=s0))
    K.obj("V2_Equivalent_Departure_Mass_Edges", *K.wire_cube((CMP_X_DEPART, 0, CMP_FLOOR_Z + s0 / 2), s0, 0.5), K.mat("structure", 1.0, 1.3), ce,
          info("whole ship at departure", ["mass.departure"]))
    K.label("V2_Equivalent_Departure_Label", f"DEPARTURE {t_(M0)}", (CMP_X_DEPART, 0, CMP_FLOOR_Z + s0 + 8), 6, "text", ce, props=info("label"))
    pe = B0["power_scaled_kg"]
    s = TG.cube_side(pe, M0)
    K.obj("V2_Engine_Mass_Baseline", *K.wire_cube((CMP_X_ENGINE, 0, CMP_FLOOR_Z + s / 2), s, 0.45), K.mat("fusion", 1.0), ce,
          info("power-scaled engine today (drive + radiators per W of jet)", ["mass.alpha_jet", "prop.jet_power"],
               "cube volume proportional to mass", mass_kg=pe, side_m=s))
    K.label("V2_Engine_Mass_Baseline_Label", f"ENGINE TODAY {t_(pe)}", (CMP_X_ENGINE, 0, CMP_FLOOR_Z - 9), 5, "fusion", ce, props=info("label"))


# ---- requirements, mission, key ------------------------------------------------------------------------------
REQ_ANCHOR = {}


def build_requirements(root):
    L2 = LOOPS[1]
    t0, t1, rt = group_bbox({"fdp1_tanks"})
    anchors = {
        "P01": ((XB, 0, 25), (XB - 60, -40, 80)),
        "P02": ((-33.6, 0, 13), (-33.6, -40, 70)),
        "P03": ((CMP_X_ENGINE, 0, CMP_FLOOR_Z + 20), (CMP_X_ENGINE + 20, -40, 90)),
        "P04": ((L2["x"], 0, L2["r"]), (L2["x"] - 40, -40, 130)),
        "P05": ((LAY["x_shield_aft"], 0, 40), (LAY["x_shield_aft"] + 30, -40, 110)),
        "P06": (HOT_MAN, (HOT_MAN[0] + 40, -40, -80)),
        "P07": ((-45, -60, 0), (-20, -110, -60)),
        "P08": (((t0 + t1) / 2, 0, rt), ((t0 + t1) / 2, -40, 90)),
        "P09": ((LAY["wing_aft_x"], 10, 0), (LAY["wing_aft_x"] + 30, -40, -60)),
        "P10": ((-300, 0, MISSION_Z + 20), (-300, -40, MISSION_Z + 70)),
    }
    status_col = {"speculative": "infeasible", "unresolved": "unresolved", "assumed": "unresolved", "calculated": "verified",
                  "known": "verified"}
    for rid, (p, q) in anchors.items():
        REQ_ANCHOR[rid] = p
        r = REQ[rid]
        c = K.coll(f"V2_3{int(rid[1:]) % 10}_REQ_{rid}" if rid != "P10" else "V2_3X_REQ_P10", root)
        col = status_col.get(r.get("status"), "unresolved")
        props = {"layer": "requirement", "req_ids": rid, "title": r["title"], "status": r.get("status", ""),
                 "classification": ",".join(r.get("classification", [])), "anchor": str(p)}
        K.obj(f"REQ_{rid}_Marker", *K.sphere(p, 3.2, 4, 2), K.mat(col, 1.0, 1.1, 0.4), c, props)
        K.obj(f"REQ_{rid}_Leader", *K.tube([p, q], 0.3, 4), K.mat(col, 0.8), c, props)
        K.label(f"REQ_{rid}_Label", f"{rid}  {r['title']}", q, 7, col, c, props=props)
        K.label(f"REQ_{rid}_Status", f"{r.get('status', '')} · {', '.join(r.get('classification', []))}", (q[0], q[1], q[2] - 9), 4,
                "dim", c, props=props)


def build_mission(c):
    s = 0.4  # m per AU along the track
    x = -300.0
    legs = [("burn1", "out", 1), ("burn2", "out", -1), ("burn3", "back", 1), ("burn4", "back", -1)]
    d_out = V("burn1.distance_AU") + V("burn2.distance_AU")
    y_of = {"out": 40.0, "back": -40.0}
    pos = {"out": x, "back": x + d_out * s}
    for b, leg, sign in legs:
        d = V(f"{b}.distance_AU") * s
        y = y_of[leg]
        if leg == "out":
            p, q = (pos[leg], y, MISSION_Z), (pos[leg] + d, y, MISSION_Z)
            pos[leg] += d
        else:
            if b == "burn4":
                pos[leg] = x + V("burn4.distance_AU") * s
            p, q = (pos[leg], y, MISSION_Z), (pos[leg] - d, y, MISSION_Z)
            pos[leg] -= d
        K.obj(f"V2_Mission_{b.title()}", *K.tube([p, q], 3.0), K.mat("exhaust", 0.9), c,
              info(f"{b}: {V(b + '.days'):.0f} days", [f"{b}.distance_AU", f"{b}.days", f"{b}.start_mass", f"{b}.end_mass"],
                   "track length proportional to distance, 1 m = 2.5 AU"))
        K.label(f"V2_Mission_{b.title()}_Label", f"{b} {V(b + '.days'):.0f} d · {t_(V(b + '.start_mass'))} → {t_(V(b + '.end_mass'))}",
                ((p[0] + q[0]) / 2, y, MISSION_Z + (12 if leg == "out" else -12)), 6, "exhaust", c, props=info("label"))
    # the return coast between burn 3 and burn 4 (the outbound legs meet at the destination)
    xc0 = x + d_out * s - V("burn3.distance_AU") * s
    xc1 = x + V("burn4.distance_AU") * s
    K.obj("V2_Mission_Return_Coast", *K.tube([(xc0, -40, MISSION_Z), (xc1, -40, MISSION_Z)], 1.2), K.mat("dim", 0.8), c,
          info("return coast", ["mission.coast_years_min"]))
    K.obj("V2_Mission_Turnaround", *K.tube([(x + d_out * s, 40, MISSION_Z), (x + d_out * s, -40, MISSION_Z)], 1.2), K.mat("dim", 0.8), c,
          info("destination"))
    K.label("V2_Mission_Title", f"FOUR-BURN MISSION  0.016 c · destination ≥ {V('mission.min_destination_AU'):,.0f} AU", (x + 330, 0, MISSION_Z + 70),
            9, "text", c, props=info("label", ["mission.min_destination_AU"]))
    K.label("V2_Mission_Years", f"engines {V('mission.engine_years'):.2f} y + coast {V('mission.coast_years_min'):.2f} y = "
            f"{V('mission.min_round_trip_years'):.2f} y minimum  vs canon {V('canon.mission_duration_y'):.1f} y (open conflict)",
            (x + 330, 0, MISSION_Z + 56), 6, "unresolved", c, props=info("label", ["mission.min_round_trip_years", "canon.mission_duration_y"]))


def build_scale_key(c):
    x, z = -520.0, 140.0
    K.label("V2_Key_Title", "ENCODINGS", (x, 0, z + 40), 8, "text", c, props=info("key"))
    one = 1e12
    r = TG.sphere_r(one, P0)
    K.obj("V2_Key_Sphere_1TW", *K.sphere((x - 40, 0, z), r, 24, 12), K.mat("fusion", 0.6), c,
          info("key: 1 TW", encoding="sphere volume ∝ power", value_W=one), smooth=True)
    K.label("V2_Key_Sphere_Label", f"sphere 1 TW (r {r:.1f} m)", (x - 40, 0, z - 16), 3.4, "dim", c, props=info("key"))
    rt = TG.tube_r(1e11, P0)[0]
    K.obj("V2_Key_Tube_100GW", *K.tube([(x - 10, 0, z), (x + 30, 0, z)], rt), K.mat("thermal", 1.0), c,
          info("key: 100 GW", encoding="tube cross-section ∝ power", value_W=1e11))
    K.label("V2_Key_Tube_Label", f"tube 100 GW (r {rt:.2f} m)", (x + 10, 0, z - 10), 3.4, "dim", c, props=info("key"))
    s = TG.cube_side(1e6, M0)
    K.obj("V2_Key_Cube_1000t", *K.wire_cube((x + 60, 0, z), s, 0.3), K.mat("structure", 1.0, 1.3), c,
          info("key: 1,000 t", encoding="cube volume ∝ mass", mass_kg=1e6))
    K.label("V2_Key_Cube_Label", f"cube 1,000 t ({s:.1f} m)", (x + 60, 0, z - 16), 3.4, "dim", c, props=info("key"))
    L = 1e5 * TG.ENC["M_PER_N"]
    K.obj("V2_Key_Arrow_100kN", *K.tube([(x - 50, 0, z - 34), (x - 50 + L, 0, z - 34)], 1.0), K.mat("exhaust", 1.0), c,
          info("key: 100 kN", encoding="arrow length ∝ force (1 m = 5 kN)", value_N=1e5))
    K.label("V2_Key_Arrow_Label", "arrow 100 kN (20 m)", (x - 50 + L / 2, 0, z - 42), 3.4, "dim", c, props=info("key"))
    lines = ["radiators and hardware: true size (1 BU = 1 m)", "magenta rays: straight, count ∝ solid angle",
             "translucent = information · opaque muted = hardware", "red-outlined = infeasible under current scaling"]
    for i, t in enumerate(lines):
        K.label(f"V2_Key_Line_{i}", t, (x, 0, z - 58 - 7 * i), 3.6, "dim", c, props=info("key"))


# ---- target, controls, cameras --------------------------------------------------------------------------------
def build_target(a, T, scaling):
    res = SC.evaluate(a, T, scaling)
    TG.build_target(res, ctx(), COLL["target"])
    sc = bpy.context.scene
    sc["v2_target_result"] = json.dumps(summary(res))
    return res


def summary(res):
    st = res["closed"] or res["at_baseline_mass"]
    keep = ("departure_kg", "thrust_N", "jet_W", "fusion_W", "heat_hot_W", "heat_warm_W", "area_hot_m2", "area_warm_m2",
            "area_W_m2", "power_scaled_kg", "drive_hw_kg", "radiator_kg")
    return {"inputs": res["inputs"], "status": res["status"], "feasible": res["feasible"], "ceiling_g": res["ceiling_g"],
            "loop_gain": res["loop_gain"], "basis": "closed" if res["closed"] else "lower_bound_at_baseline_mass",
            "state": {k: st[k] for k in keep}, "wings": st["wings"], "flags": res["flags"],
            "feedback_departure_kg": res["feedback_departure_kg"]}


def embed_texts():
    for fn, tn in (("fdp1diag/v2kit.py", "v2kit.py"), ("fdp1diag/v2_target.py", "v2_target.py"),
                   ("fdp1diag/scenario.py", "scenario.py"), ("data/scenario_inputs.json", "scenario_inputs.json"),
                   ("README.md", "README_FDP1"), ("VISUAL_GRAMMAR.md", "VISUAL_GRAMMAR")):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            t = bpy.data.texts.get(tn) or bpy.data.texts.new(tn)
            t.clear()
            t.write(open(p).read())
    t = bpy.data.texts.new("V2_controls.py")
    t.write(open(os.path.join(HERE, "fdp1diag", "v2_controls.py")).read())
    t.use_module = True
    return t


CAMERAS = []


def camera(name, loc, target, lens=35.0, ortho=None, note="", clip=20000.0):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start, cam.clip_end = 1.0, clip
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    o = bpy.data.objects.new(name, cam)
    COLL["cams"].objects.link(o)
    o.location = loc
    o.rotation_euler = (mathutils.Vector(target) - mathutils.Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    o["note"] = note
    CAMERAS.append(o)
    return o


def build_cameras(sc, board=None):
    COLL["cams"] = K.coll("V2_90_CAMERAS", None)
    # side cameras sit in the wing plane (z = 0.15, mid-thickness) and outside the wing planform, so the 3.6 km wings
    # project to a line and hide nothing; the long side views are telephoto, close to an elevation drawing
    camera("CAM_01_MAIN_OVERVIEW", (520, -900, 520), (-40, 0, 10), 26, note="the ship with every layer attached")
    camera("CAM_02_FUSION_ENERGY", (-420, -330, 0.15), (-235, 0, -15), 32, note="fusion sphere, jet, uncollimated plasma, radiation")
    camera("CAM_03_THERMAL_MANAGEMENT", (-430, -340, -250), (-160, -20, -40), 32, note="heat deposits, manifolds, wings to scale")
    camera("CAM_04_THRUST_AND_MASS", (60, -4200, 0.15), (60, 0, 30), 115, note="thrust arrow, mass rail, comparison bay")
    camera("CAM_05_ACCELERATION_COMPARISON", (300, -4200, 0.15), (300, 0, 80), 85, note="baseline vs target: sphere, arrow, cubes, banner")
    camera("CAM_06_REQUIREMENTS", (-40, -4200, 0.15), (-40, 0, -100), 100, note="P01-P10 on their hardware; mission track below")
    camera("CAM_07_ISOMETRIC", (1500, -1500, 1500), (0, 0, 0), 50, ortho=1250, note="axonometric whole model")
    if board is not None:
        bx, by, bz, W, H = board
        camera("CAM_08_TECHNICAL_BOARD", (bx + W / 2 - 3, by - H / 2 + 36, bz + 500), (bx + W / 2 - 3, by - H / 2 + 36, bz), ortho=W + 10,
               note="phase-1 technical support board (Layer B, shown only for this camera)")
    sc.frame_start, sc.frame_end = 1, len(CAMERAS)
    for i, o in enumerate(CAMERAS):
        mk = sc.timeline_markers.new(o.name, frame=i + 1)
        mk.camera = o
    sc.camera = CAMERAS[0]


def build_layer_b(sc):
    import build_diagram as BD
    root = K.coll("LAYER_B_TECHNICAL_SUPPORT", None)
    before = {c.name for c in sc.collection.children}
    for key in BD.SECTIONS:
        BD.section(key)
    for f in ("build_title", "build_legend", "build_overview", "build_fusion", "build_magnifier", "build_rocket", "build_mass",
              "build_gap", "build_split", "build_geometry", "build_tarea", "build_scale", "build_mission", "build_requirements"):
        getattr(BD, f)()
    anchor = bpy.data.objects.new("LAYER_B_BOARD_ORIGIN", None)
    root.objects.link(anchor)
    anchor.location = (-400.0, -5000.0, -3000.0)
    for c in list(sc.collection.children):
        if c.name in before or c.name == root.name:
            continue
        sc.collection.children.unlink(c)
        root.children.link(c)
    for o in root.all_objects:
        if o is not anchor and o.parent is None:
            o.parent = anchor
            o["layer"] = "B"
    root.hide_render = True
    W, H = 5 * BD.PW + 4 * BD.G, 3 * BD.PH + 2 * BD.G + BD.TOP
    return root, (anchor.location.x, anchor.location.y, anchor.location.z, W, H)


def setup_display(sc):
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_object_outline = False
    sh.show_cavity = False
    sh.show_specular_highlight = True
    sh.background_type = "WORLD"
    sc.display.render_aa = "16"
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 3840, 2160
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"


def setup_viewports():
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for sp in area.spaces:
                if sp.type == "VIEW_3D":
                    sp.shading.type = "SOLID"
                    sp.shading.light = "STUDIO"
                    sp.shading.color_type = "MATERIAL"
                    sp.shading.background_type = "WORLD"
                    sp.overlay.show_floor = False
                    sp.overlay.show_axis_x = sp.overlay.show_axis_y = False
                    sp.overlay.show_relationship_lines = False
                    sp.clip_start, sp.clip_end = 1.0, 20000.0
                    sp.region_3d.view_perspective = "CAMERA"


def layer_visible(sc, name, on):
    c = bpy.data.collections.get(name)
    if c is None:
        return

    def walk(lc):
        if lc.collection == c:
            return lc
        for ch in lc.children:
            r = walk(ch)
            if r:
                return r
    lc = walk(sc.view_layers[0].layer_collection)
    if lc:
        lc.hide_viewport = not on
    c.hide_render = not on


def board_mode(sc, on):
    for n in ("V2_00_PHYSICAL", "V2_10_BASELINE_INFO", "V2_20_TARGET", "V2_30_REQUIREMENTS", "V2_40_MISSION", "V2_50_SCALE_KEY"):
        layer_visible(sc, n, not on)
    layer_visible(sc, "V2_99_SUPERSEDED_FOUR_NOZZLE_DRIVE", False)
    layer_visible(sc, "V2_21_TARGET_EQUIVALENT_AREA_SQUARE", False)
    layer_visible(sc, "LAYER_B_TECHNICAL_SUPPORT", on)


def render_cams(sc, tag="", only=None, target_cams=("05",)):
    os.makedirs(RENDER_DIR, exist_ok=True)
    out = []
    for i, o in enumerate(CAMERAS):
        if only and not any(o.name.startswith("CAM_" + k) for k in only):
            continue
        sc.frame_set(i + 1)
        sc.camera = o
        K.VIEW["obj"].rotation_euler = o.rotation_euler
        board_mode(sc, "TECHNICAL_BOARD" in o.name)
        if "TECHNICAL_BOARD" not in o.name:
            layer_visible(sc, "V2_20_TARGET", any(o.name.startswith("CAM_" + k) for k in target_cams))
        sc.render.resolution_percentage = PCT
        sc.display.shading.light = "FLAT" if "BOARD" in o.name else "STUDIO"
        sc.render.filepath = os.path.join(RENDER_DIR, f"{o.name}{tag}.png")
        bpy.ops.render.render(write_still=True)
        out.append(sc.render.filepath)
        print("rendered", sc.render.filepath)
    board_mode(sc, False)
    sc.frame_set(1)
    sc.camera = CAMERAS[0]
    sc.render.resolution_percentage = 100
    sc.display.shading.light = "STUDIO"
    return out


def export_gltf(sc):
    d = os.path.join(RENDER_DIR, "web")
    os.makedirs(d, exist_ok=True)
    board_mode(sc, False)
    bpy.ops.export_scene.gltf(filepath=os.path.join(d, "fdp1_spatial_v2.glb"), export_format="GLB", export_extras=True,
                              use_visible=True, export_cameras=True, export_apply=True)
    json.dump({"scene": "FDP1_SPATIAL_V2", "units": "m, +X bow, +Z dorsal", "baseline": summary(BASE),
               "target": json.loads(sc["v2_target_result"]), "encodings": {k: v for k, v in TG.ENC.items() if v is not None},
               "inputs": ["data/ship_geometry.json", "data/scenario_inputs.json", "data/fdp1_parameters.json", "data/requirements.json"],
               "object_properties": ["layer", "state", "component", "encoding", "param_keys", "req_ids", "value_W", "value_N",
                                     "mass_kg", "area_m2", "status", "source"]},
              open(os.path.join(d, "fdp1_spatial_v2_manifest.json"), "w"), indent=1)
    print("exported", d)


def main():
    sc = reset_scene()
    view_align(sc)
    build_physical()
    COLL["base"] = base = K.coll("V2_10_BASELINE_INFO", None)
    build_fusion(K.coll("V2_11_FUSION_SOURCE", base, "COLOR_02"))
    build_jet(K.coll("V2_12_JET_AND_PLUME", base, "COLOR_05"))
    build_radiation(K.coll("V2_13_RADIATION", base, "COLOR_07"))
    build_heat(K.coll("V2_14_WASTE_HEAT", base, "COLOR_01"))
    build_radiator_info(K.coll("V2_15_RADIATOR_REJECTION", base, "COLOR_01"))
    build_driver_loop(K.coll("V2_16_DRIVER_LOOP", base, "COLOR_02"))
    build_thrust(K.coll("V2_17_THRUST", base, "COLOR_05"))
    build_requirements(K.coll("V2_30_REQUIREMENTS", None, "COLOR_03"))
    build_mass(K.coll("V2_18_MASS_BUDGET", base))
    build_mission(K.coll("V2_40_MISSION", None))
    build_scale_key(K.coll("V2_50_SCALE_KEY", None))
    COLL["target"] = K.coll("V2_20_TARGET", None, "COLOR_01")
    a = ACCEL if ACCEL is not None else 0.05
    res = build_target(a, TEMP, SCALING)
    board = None
    broot = None
    if "--no-board" not in ARGS:
        broot, board = build_layer_b(sc)
    build_cameras(sc, board)
    setup_display(sc)
    ctl = embed_texts()
    sc["v2_ctx"] = json.dumps(ctx())
    sc["fdp1_record"] = GEO["meta"]["fdp1_record"] + " @ " + GEO["meta"]["fdp1_record_commit"][:7]
    sc["checks_passed"] = sum(c["ok"] for c in M.checks)
    sc["checks_total"] = len(M.checks)
    exec(compile(ctl.as_string(), ctl.name, "exec"), {"__name__": "__main__"})
    sc.v2_live = False
    sc.v2_accel, sc.v2_use_base_T, sc.v2_temp, sc.v2_scaling = a, TEMP is None, TEMP or 1500.0, SCALING
    sc.v2_live = True
    board_mode(sc, False)
    n = {c.name: len(c.all_objects) for c in (COLL["phys"], base, COLL["target"])}
    print("objects", n, "target", res["status"], f"{a} g", TEMP)
    if "--gltf" in ARGS:
        export_gltf(sc)
    if "--render" in ARGS:
        render_cams(sc, only=ONLY)
    if "--cases" in ARGS:
        for ca, cT in CASES:
            build_target(ca, cT, SCALING)
            tag = f"__case_{ca:.2g}g_{'base' if cT is None else int(cT)}K"
            render_cams(sc, tag, only=ONLY or ["01", "05"], target_cams=("01", "05"))
        build_target(a, TEMP, SCALING)
    setup_viewports()
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print("saved", OUT_BLEND)


if __name__ == "__main__":   # build_v3.py imports these builders
    main()
