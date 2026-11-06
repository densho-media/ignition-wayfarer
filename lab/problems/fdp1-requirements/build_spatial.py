"""Build FDP-1_Spatial_Systems.blend: FDP-1 (Fiji Drive Pulsed prototype 1) as a 3D model of its engineering problem.

Run from the repository root:
    /snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_spatial.py -- [--render] [--out DIR]

Layer A (the spatial model) is built here. Layer B (the technical support board: panels, formulas, cards) is the
phase-1 diagram from build_diagram.py, built into a hidden collection beside it. Both read the same
data/fdp1_parameters.json and data/requirements.json through fdp1diag/model.py; the build stops if a check fails.

Visual grammar (README "Visual grammar"): fusion power is a sphere whose VOLUME is proportional to power; energy
branches are tubes whose CROSS-SECTION is proportional to power; mass is a block whose VOLUME is proportional to
mass; force is an arrow whose LENGTH is proportional to force; radiator area is a plate drawn to TRUE AREA at a
stated scale. Positions inside the fusion island are schematic around the to-scale nozzle loops.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import mathutils  # noqa: E402

import build_diagram as BD  # noqa: E402  (Layer B builders; its main() does not run on import)
from fdp1diag.bkit import PALETTE, UI, Kit, mix, srgb_to_lin  # noqa: E402
from fdp1diag.model import Model, fmt_power, sig  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_BLEND = os.path.join(HERE, "FDP-1_Spatial_Systems.blend")
RENDER_DIR = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else os.path.join(HERE, "renders_spatial")
PCT = int(ARGS[ARGS.index("--pct") + 1]) if "--pct" in ARGS else 100
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None

M = Model()
bad = [c for c in M.checks if not c["ok"]]
if bad:
    raise SystemExit("validation failed: " + "; ".join(f"{c['name']}: {c['detail']}" for c in bad))
V = M.v
K = Kit()

# ---- encodings (declared in README and on the scale cards) ----------------------------------------------------
PF = V("fusion.power")
R_ORB = 10.0                                   # sphere radius of 17.3 TW; volume proportional to power
R_TUBE = 6.0                                   # tube radius that would carry 17.3 TW; area proportional to power
R_MIN = 0.12                                   # thinner tubes are drawn at this radius and flagged
MASS_T_PER_BU3 = V("mass.departure") / 1e3 / 20.0 ** 3     # 20,760 t = a 20 BU cube
MN_PER_BU = 1.0                                # force arrows: 1 BU = 1 MN
M_PER_BU_NOZZLE = 3.0                          # nozzle loops to scale, 1 BU = 3 m
M_PER_BU_HEAT = 40.0                           # radiator plates and wing plan, 1 BU = 40 m
YEARS_PER_BU = 0.05                            # mission timeline

O = (0.0, 0.0, 20.0)                           # fusion source
FLOOR = -20.0                                  # reference plane of the heat and 1 g islands
HEAT_C = (0.0, 150.0)                          # heat island centre (plan)
G1_Y = -200.0                                  # 1 g orb row
MASS_X0 = 40.0                                 # aft face of the mass block


def orb_r(p):
    return R_ORB * (p / PF) ** (1 / 3)


def tube_r(p):
    return R_TUBE * math.sqrt(p / PF)


def cube_side(mass_kg):
    return (mass_kg / 1e3 / MASS_T_PER_BU3) ** (1 / 3)


def P(w):
    return fmt_power(w)


def t_(kg):
    return f"{kg / 1e3:,.0f} t"


def km2(m2):
    return f"{sig(m2 / 1e6, 3)} km²"


# ---- properties: every Layer A object is bound to its data ----------------------------------------------------
def props(component, keys=(), reqs=None, cls=None, encoding=None, **extra):
    keys = list(keys)
    if reqs is None:
        reqs = sorted({r for k in keys for r in (M.meta(k).get("req") or [])})
    if cls is None:
        cls = ",".join(sorted({M.cls(k) for k in keys})) if keys else "SCHEMATIC"
    d = {"component": component, "classification": cls, "req_ids": ",".join(reqs), "value_keys": ",".join(keys),
         "layer": "A"}
    if encoding:
        d["encoding"] = encoding
    d.update(extra)
    return d


# ---- materials --------------------------------------------------------------------------------------------------
def cm(cat, shade=1.0, alpha=1.0):
    return K.cat_mat(cat, shade, alpha, emit=1.5 if cat in ("fusion", "exhaust") else 0.0)


def rgbm(name, rgb, alpha=1.0, emit=0.0):
    return K.mat(name, rgb, alpha, emit)


WHITE = None


def ui(key, alpha=1.0):
    return K.ui_mat(key, alpha)


# ---- collections ------------------------------------------------------------------------------------------------
ROOT_A = None
COLL = {}


def coll(key, name, tag="NONE", parent=None):
    c = K.coll(name, parent or ROOT_A, tag)
    COLL[key] = c
    return c


VIEW = None


def label(name, body, loc, size, mat=None, c=None, align="CENTER", valign="CENTER", p=None):
    o = K.text(name, body, loc[0], loc[1], size, mat or ui("text"), c, align, valign, z=loc[2],
               props=p or {"component": "label", "layer": "A"})
    o.location = loc
    con = o.constraints.new("COPY_ROTATION")
    con.target = VIEW
    return o


# =================================================================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "FDP1_SPATIAL"
    sc.unit_settings.system = "NONE"
    w = bpy.data.worlds.new("FDP1_World")
    w.color = srgb_to_lin((0.018, 0.022, 0.030))
    w.use_nodes = True
    bgn = w.node_tree.nodes.get("Background")
    if bgn:
        bgn.inputs[0].default_value = (*srgb_to_lin((0.018, 0.022, 0.030)), 1)
    sc.world = w
    return sc


def view_align(sc):
    """An empty whose rotation follows the active camera (simple drivers, no scripts): labels copy it."""
    global VIEW
    e = bpy.data.objects.new("VIEW_ALIGN", None)
    e.empty_display_size = 2
    bpy.context.scene.collection.objects.link(e)
    for i in range(3):
        fc = e.driver_add("rotation_euler", i)
        drv = fc.driver
        drv.type = "SCRIPTED"
        var = drv.variables.new()
        var.name = "r"
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "SCENE"
        var.targets[0].id = sc
        var.targets[0].data_path = f"camera.rotation_euler[{i}]"
        drv.expression = "r"
    e.hide_render = True
    VIEW = e


# =================================================================================================================
def build_reference():
    c = coll("ref", "A0_REFERENCE_GRID_AND_SCALES")
    m = ui("grid", 1.0)
    pr = props("reference grid", cls="SCHEMATIC")
    for i in range(-6, 9):
        K.box(f"A0_grid_x{i:+d}", (i * 50 - 0.12, -300, FLOOR - 0.6), (i * 50 + 0.12, 400, FLOOR - 0.5), m, c, pr)
    for j in range(-6, 9):
        K.box(f"A0_grid_y{j:+d}", (-300, j * 50 - 0.12, FLOOR - 0.6), (400, j * 50 + 0.12, FLOOR - 0.5), m, c, pr)


# ---------------------------------------------------------------------------------------------------------------
def build_fusion():
    c = coll("fusion", "A1_FUSION_SOURCE", PALETTE["fusion"][1])
    keys = ["fusion.power", "fusion.target_gain", "fusion.pellet_rate", "fusion.yield_per_pulse"]
    pr = props("fusion source", keys, encoding="sphere volume proportional to power; 17.3 TW = r 10 BU",
               value_W=PF)
    K.ball("A1_fusion_orb", O, R_ORB, rgbm("orb_core", (1.0, 0.62, 0.18), 1.0, 4.0), c, pr)
    K.ball("A1_fusion_orb_core", O, R_ORB * 0.55, rgbm("orb_hot", (1.0, 0.93, 0.70), 1.0, 8.0), c, pr)
    for i, (f, a) in enumerate(((1.12, 0.30), (1.28, 0.16), (1.5, 0.08))):
        K.ball(f"A1_fusion_glow_{i}", O, R_ORB * f, cm("fusion", 1.0, a), c, pr)
    label("A1_title", "FUSION  17.3 TW", (O[0], O[1], O[2] + 26), 4.2, cm("fusion", 1.2), c)
    label("A1_sub", f"gain {V('fusion.target_gain'):,.0f} · {V('fusion.pellet_rate'):.0f} Hz",
          (O[0], O[1], O[2] + 21.5), 2.2, ui("dim"), c)


# ---------------------------------------------------------------------------------------------------------------
def nozzle_x(xm):
    return (xm - V("layout.x_burn")) / M_PER_BU_NOZZLE


def build_propulsion():
    c = coll("prop", "A2_BRANCH_A_PROPULSION", PALETTE["exhaust"][1])
    cf = coll("fiji", "A2.Fiji magnetic nozzle (to scale 1 BU = 3 m)", PALETTE["fiji"][1], c)
    for i in (1, 2, 3):
        x = nozzle_x(V(f"nozzle.loop{i}_x"))
        r = V(f"nozzle.loop{i}_r") / M_PER_BU_NOZZLE
        K.ring(f"A2_nozzle_loop_{i}", (O[0] + x, O[1], O[2]), "X", r, 0.9, cm("fiji", 1.0), cf,
               props("magnetic nozzle loop", [f"nozzle.loop{i}_r", f"nozzle.loop{i}_x", "nozzle.interloop_force"],
                     encoding="to scale, 1 BU = 3 m"))
    x3 = O[0] + nozzle_x(V("nozzle.loop3_x"))
    label("A2_nozzle_label", "magnetic nozzle", (x3, O[1], O[2] + V("nozzle.loop3_r") / 3 + 4), 2.6, cm("fiji", 1.2), cf)

    jet, unc = V("ledger.jet"), V("ledger.plume_to_space")
    r_both = tube_r(jet + unc)
    r_jet = tube_r(jet)
    K.cones("A2_jet_in_nozzle", [((O[0] - R_ORB * 0.6, O[1], O[2]), (x3, O[1], O[2]), r_both, r_both)],
            cm("exhaust", 1.0, 0.85), c,
            props("plasma leaving the source", ["ledger.jet", "ledger.plume_to_space"],
                  encoding="tube cross-section proportional to power", value_W=jet + unc), seg=48, smooth=True)
    half = math.radians(V("prop.plume_half_angle_deg"))
    L = 70.0
    K.cones("A2_exhaust_jet", [((x3, O[1], O[2]), (x3 - L, O[1], O[2]), r_jet, r_jet + L * math.tan(half))],
            cm("exhaust", 1.0, 0.42), c,
            props("directed exhaust jet", ["ledger.jet", "prop.ve", "prop.plume_half_angle_deg", "calc.eta_jet"],
                  encoding="starts at tube area of 13.5 TW, opens at the record half angle", value_W=jet),
            seg=64, smooth=True)
    K.cones("A2_exhaust_core", [((x3, O[1], O[2]), (x3 - L * 0.8, O[1], O[2]), r_jet * 0.5, 0.2)],
            cm("exhaust", 1.35, 0.9), c, props("directed exhaust jet", ["ledger.jet"]), seg=32, smooth=True)
    label("A2_jet_label", f"EXHAUST  {P(jet)}", (x3 - 50, O[1], O[2] + 30), 4.0, cm("exhaust", 1.2), c)
    label("A2_jet_sub", f"78 % of fusion · {V('prop.ve') / 1e3:,.0f} km/s", (x3 - 50, O[1], O[2] + 25.5), 2.2,
          ui("dim"), c)


# ---------------------------------------------------------------------------------------------------------------
def fib_dirs(n):
    g = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - y * y)
        out.append((y, r * math.cos(g * i), r * math.sin(g * i)))    # x first: +X is index 0
    return out


def build_radiation():
    c = coll("rad", "A4_BRANCH_C_RADIATION_AND_ESCAPE", PALETTE["radiation"][1])
    to_space, on_hw = V("ledger.radiation_to_space"), V("ledger.radiation_on_hardware")
    total = to_space + on_hw
    N = 240
    dirs = fib_dirs(N)
    n_shield = round(N * V("geom.solid_angle_shield"))
    n_loops = round(N * V("geom.solid_angle_loops"))
    n_struts = round(N * V("geom.solid_angle_struts"))
    by_x = sorted(range(N), key=lambda i: -dirs[i][0])
    shield_ids = set(by_x[:n_shield])
    by_eq = sorted((i for i in range(N) if i not in shield_ids), key=lambda i: abs(dirs[i][0]))
    loop_ids = set(by_eq[:n_loops])
    x_sh = nozzle_x(V("layout.x_shield_aft"))
    r_l2 = V("nozzle.loop2_r") / M_PER_BU_NOZZLE
    free, hits = [], []
    for i, d in enumerate(dirs):
        p = (O[0] + d[0] * R_ORB * 1.05, O[1] + d[1] * R_ORB * 1.05, O[2] + d[2] * R_ORB * 1.05)
        if i in shield_ids:
            s = x_sh / d[0]
            hits.append((p, (O[0] + d[0] * s, O[1] + d[1] * s, O[2] + d[2] * s), 0.22, 0.16))
        elif i in loop_ids:
            s = r_l2 / math.hypot(d[1], d[2])
            hits.append((p, (O[0] + d[0] * s, O[1] + d[1] * s, O[2] + d[2] * s), 0.22, 0.16))
        else:
            q = (O[0] + d[0] * 34, O[1] + d[1] * 34, O[2] + d[2] * 34)
            free.append((p, q, 0.16, 0.015))
    K.cones("A4_rays_to_space", free, cm("radiation", 1.05, 0.9), c,
            props("radiation leaving to space", ["ledger.radiation_to_space", "shield.xray_escape", "shield.neutron_escape"],
                  encoding=f"{N} rays share the escaping {P(total)}; ray count per target proportional to solid angle",
                  rays=len(free)), seg=6)
    K.cones("A4_rays_on_hardware", hits, cm("radiation", 1.2), c,
            props("radiation hitting hardware", ["ledger.radiation_on_hardware", "geom.solid_angle_total",
                                                 "geom.solid_angle_shield", "geom.solid_angle_loops"],
                  rays=len(hits), struts_rays_rounded=n_struts), seg=6)
    for k, (p, q, _, _) in enumerate(hits):
        K.ball(f"A4_hit_{k}", q, 0.9, cm("radiation", 1.25, 0.8), c, props("radiation hit", ["ledger.radiation_on_hardware"]),
               u=12, v=6)
    # shadow shield (schematic size: the hardware cone at its position)
    r_sh = x_sh * math.tan(math.radians(V("shield.hw_half_angle_deg")))
    K.cones("A6_shadow_shield", [((O[0] + x_sh, O[1], O[2]), (O[0] + x_sh + 1.6, O[1], O[2]), r_sh, r_sh * 1.12)],
            cm("structure", 0.9), c,
            props("shadow shield", ["shield.mass", "shield.hw_half_angle_deg", "shield.neutron_decades"],
                  encoding="radius = hardware shadow cone at its position (1 BU = 3 m)"), seg=40)
    label("A4_label", f"RADIATION  {P(total)}", (O[0] - 14, O[1] - 30, O[2] + 40), 3.2, cm("radiation", 1.2), c)
    label("A4_sub", f"{V('geom.solid_angle_total') * 100:.2f} % hits hardware", (O[0] - 14, O[1] - 30, O[2] + 36),
          2.0, ui("dim"), c)
    label("A4_unc", f"+ {P(V('ledger.plume_to_space'))} uncollimated plasma", (O[0] - 40, O[1] - 30, O[2] - 24), 2.2,
          cm("exhaust", 0.9), COLL["prop"])
    # the uncollimated share of the plume, drawn as a faint shell around the jet; its spread angle is not modelled
    x3 = O[0] + nozzle_x(V("nozzle.loop3_x"))
    r0 = tube_r(V("ledger.jet") + V("ledger.plume_to_space"))
    K.cones("A4_uncollimated_plume", [((x3, O[1], O[2]), (x3 - 28, O[1], O[2]), r0, r0 + 28 * math.tan(math.radians(50)))],
            cm("exhaust", 0.8, 0.10), COLL["prop"],
            props("uncollimated plume to space", ["ledger.plume_to_space"], cls="ASSUMED",
                  encoding="spread angle schematic (not in the record)", value_W=V("ledger.plume_to_space")),
            seg=48, smooth=True)


# ---------------------------------------------------------------------------------------------------------------
def heat_xy(xm, ym):
    """Heat-island plan position for metres (x along the ship, y across)."""
    return (HEAT_C[0] + xm / M_PER_BU_HEAT, HEAT_C[1] + ym / M_PER_BU_HEAT)


def bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, cc, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append(tuple(a * p0[k] + b * p1[k] + cc * p2[k] + d * p3[k] for k in range(3)))
    return out


def tr(p):
    r = tube_r(p)
    return max(r, R_MIN), r < R_MIN


def build_heat():
    c = coll("heat", "A3_BRANCH_B_WASTE_HEAT", PALETTE["thermal"][1])
    hot_T, warm_T = V("rad.hot_T"), V("rad.warm_T")
    man_hot = (O[0] - 4, 48.0, 2.0)
    man_warm = (O[0] + 6, 52.0, -4.0)
    x_l3 = O[0] + nozzle_x(V("nozzle.loop3_x"))
    x_sh = O[0] + nozzle_x(V("layout.x_shield_aft"))
    r_l2 = V("nozzle.loop2_r") / 3
    srcs = [  # (key, start point, manifold)
        ("hot.plume_on_hardware", (x_l3, 18, O[2] + 30), man_hot),
        ("hot.radiation_on_nozzle_loops", (O[0], r_l2 * 0.7, O[2] + r_l2 * 0.7), man_hot),
        ("hot.radiation_on_shadow_shield", (x_sh, 1.5, O[2] + 2.5), man_hot),
        ("hot.radiation_on_nozzle_struts", (8, 10, O[2] + 14), man_hot),
        ("hot.recovery_conversion_loss", (-14, -16, 1.0), man_hot),
        ("warm.power_and_target_systems", (-14, -16, 1.0), man_warm),
        ("warm.driver_waste", (6, -16, 1.0), man_warm),
        ("warm.cryoplant_input", (6, -12, 0.0), man_warm),
        ("warm.coil_conductor_heating", (O[0], r_l2 * 0.5, O[2] - r_l2 * 0.8), man_warm),
    ]
    flagged = []
    for k, (key, a, b) in enumerate(srcs):
        r, thin = tr(V(key))
        mid1 = (a[0], (a[1] + b[1]) / 2, a[2] + 8)
        mid2 = (b[0], b[1] - 12, b[2] + 4)
        cat_shade = 1.1 if key.startswith("hot") else 0.8
        K.tube(f"A3_heat_{key.split('.')[1]}", bez(a, mid1, mid2, b), r, cm("thermal", cat_shade, 0.95), c,
               props("waste-heat filament", [key], encoding="tube cross-section proportional to power"
                     + ("; below minimum width, drawn at minimum" if thin else ""), value_W=V(key), drawn_min=thin))
        if thin:
            flagged.append(key)
    # manifolds -> radiators
    for name, p, key, T in (("hot", man_hot, "thermal.hot_total", hot_T), ("warm", man_warm, "thermal.warm_total", warm_T)):
        K.ball(f"A3_manifold_{name}", p, max(tube_r(V(key)) * 2.2, 0.8), cm("thermal", 1.1 if name == "hot" else 0.8), c,
               props(f"{name} heat loop manifold", [key, f"rad.{name}_T"], value_W=V(key)), u=16, v=8)
    label("A3_title", f"WASTE HEAT  {P(V('calc.heat_total'))}", (O[0] + 14, 58, 10), 3.4, cm("thermal", 1.15), c)
    label("A3_sub", f"{P(V('thermal.hot_total'))} at {hot_T:.0f} K · {P(V('thermal.warm_total'))} at {warm_T:.0f} K",
          (O[0] + 14, 58, 6), 2.0, ui("dim"), c)
    return man_hot, man_warm


def build_radiators(man_hot, man_warm):
    c = coll("radiators", "A3.radiator wings and plates (true area, 1 BU = 40 m)", PALETTE["thermal"][1], COLL["heat"])
    z = FLOOR
    # FDP-1 plan to scale: ship body, nozzle loops, two radiator wings across the ship axis
    Ls = V("canon.ship_body_length_m")
    (x0, y0), (x1, y1) = heat_xy(-Ls / 2, -8), heat_xy(Ls / 2, 8)
    K.box("A3_plan_ship_body", (x0, y0, z), (x1, y1, z + 1.0), cm("structure", 1.0), c,
          props("ship body to scale", ["canon.ship_body_length_m"], encoding="1 BU = 40 m"))
    for i in (1, 2, 3):
        cx, cy = heat_xy(V(f"nozzle.loop{i}_x") - V("layout.x_attach") - Ls / 2, 0)
        K.ring(f"A3_plan_nozzle_loop_{i}", (cx, cy, z + 1.0), "X", V(f"nozzle.loop{i}_r") / M_PER_BU_HEAT, 0.12,
               cm("fiji", 1.0), c, props("nozzle loop to scale", [f"nozzle.loop{i}_r"], encoding="1 BU = 40 m"),
               seg=48, rseg=6)
    ch = V("rad.wing_chord") / M_PER_BU_HEAT
    r_root, r_tip = V("rad.wing_root_radius"), V("rad.wing_tip_radius")
    r_hot = r_root + V("rad.hot_band")
    for side, sgn in (("port", 1), ("stbd", -1)):
        for part, ra, rb, shade in (("hot", r_root, r_hot, 1.15), ("warm", r_hot, r_tip, 0.75)):
            (xa, ya), (xb, yb) = heat_xy(-V("rad.wing_chord") / 2, sgn * ra), heat_xy(V("rad.wing_chord") / 2, sgn * rb)
            K.box(f"A3_wing_{side}_{part}", (min(xa, xb), min(ya, yb), z), (max(xa, xb), max(ya, yb), z + 0.5),
                  cm("thermal", shade), c,
                  props(f"radiator wing ({part} loop)", [f"rad.{part}_area", f"rad.{part}_T", "rad.wing_span",
                                                          "rad.wing_tip_radius", "rad.wing_chord"],
                        encoding="planform to scale, 1 BU = 40 m"))
    _, ytip = heat_xy(0, r_tip)
    label("A3_wings_label", f"wings tip to tip {2 * r_tip / 1e3:.2f} km", (HEAT_C[0] + 10, ytip + 6, z + 4), 3.0,
          cm("thermal", 1.1), c)
    label("A3_ship_label", f"ship {Ls:.0f} m", (HEAT_C[0] + 14, HEAT_C[1], z + 4), 2.2, ui("dim"), c)
    # supply lines from the manifolds to the wing roots
    for name, m, sgn in (("hot", man_hot, 1), ("warm", man_warm, 1)):
        rx, ry = heat_xy(0, sgn * r_root)
        key = f"thermal.{name}_total"
        K.tube(f"A3_supply_{name}", bez(m, (m[0], m[1] + 20, m[2]), (rx, ry - 25, z + 8), (rx, ry, z + 0.6)),
               tube_r(V(key)), cm("thermal", 1.1 if name == "hot" else 0.8), c,
               props(f"{name} loop transport", [key, "calc.transport_mass"], encoding="tube cross-section proportional to power",
                     value_W=V(key)))
    # FDP-1 today: hot and warm plates standing, true area
    def plate(name, area, x, cat_rgb, keys, comp, text, sub):
        s = math.sqrt(area) / M_PER_BU_HEAT
        y = HEAT_C[1] + 30
        K.quad(name, [(x, y, z), (x + s, y, z), (x + s, y, z + s), (x, y, z + s)], rgbm(name, cat_rgb), c,
               props(comp, keys, encoding="square of the true area, 1 BU = 40 m", area_m2=area), thick=0.4)
        label(name + "_label", text, (x + s / 2, y - 1, z + s + 3.5), 2.4, ui("text"), c)
        label(name + "_sub", sub, (x + s / 2, y - 1, z + s + 1.4), 1.7, ui("dim"), c)
        return s
    s_w = plate("A3_plate_today_warm", V("rad.warm_area"), -78, mix(PALETTE["thermal"][0], (0.1, 0.02, 0.02), 0.45),
                ["rad.warm_area", "rad.warm_T"], "today's warm radiator", f"{V('rad.warm_T'):.0f} K", km2(V("rad.warm_area")))
    plate("A3_plate_today_hot", V("rad.hot_area"), -78 + s_w + 4, (1.0, 0.45, 0.12), ["rad.hot_area", "rad.hot_T"],
          "today's hot radiator", f"{V('rad.hot_T'):.0f} K", km2(V("rad.hot_area")))
    label("A3_today_title", "FDP-1 TODAY", (-78 + s_w / 2, HEAT_C[1] + 30, z + s_w + 9), 3.2, cm("thermal", 1.15), c)


def build_temperatures():
    parent = coll("temps", "A8_RADIATOR_TEMPERATURE_PROGRESSION", PALETTE["thermal"][1])
    z = FLOOR
    x = 30.0
    y = HEAT_C[1] + 30
    ramp = {800: (0.55, 0.08, 0.05), 1000: (0.80, 0.16, 0.06), 1500: (1.0, 0.42, 0.10), 2000: (1.0, 0.70, 0.30),
            2500: (1.0, 0.92, 0.72)}
    for row in M.temp_rows:
        T = int(row["T"])
        c = K.coll(f"A8.radiator at {T} K", parent, PALETTE["thermal"][1])
        s = math.sqrt(row["area_total"]) / M_PER_BU_HEAT
        nm = f"A8_plate_{T}K"
        K.quad(nm, [(x, y, z), (x + s, y, z), (x + s, y, z + s), (x, y, z + s)], rgbm(nm, ramp.get(T, (1, 0.5, 0.2))),
               c, props("radiator area at one temperature", ["calc.heat_total", "rad.emissivity"], cls="CALC",
                        encoding="square of the area that rejects all 101.5 GW at this temperature, 1 BU = 40 m",
                        T_K=T, area_m2=row["area_total"], area_1g_m2=row["area_1g"]), thick=0.4)
        label(nm + "_label", f"{T} K", (x + s / 2, y - 1, z + s + 3.6), 2.6, ui("text"), c)
        label(nm + "_sub", km2(row["area_total"]), (x + s / 2, y - 1, z + s + 1.4), 1.8, ui("dim"), c)
        x += s + 5
    label("A8_title", "HOTTER = SMALLER", (60, y, z + 56), 3.4, cm("thermal", 1.15), parent)
    label("A8_sub", "area that rejects all 101.5 GW, ε 0.9", (60, y, z + 52), 2.0, ui("dim"), parent)
    label("A8_tbd", "material limits 1,500-2,500 K: TBD", (60, y, z + 49), 1.9, cm("unresolved"), parent)


# ---------------------------------------------------------------------------------------------------------------
def build_driver():
    c = coll("driver", "A5_BRANCH_D_DRIVER_RECIRCULATION", PALETTE["fusion"][1])
    x_l3 = O[0] + nozzle_x(V("nozzle.loop3_x"))
    conv = (-14.0, -16.0, 1.0)
    drv = (6.0, -16.0, 1.0)
    K.box("A5_power_conversion", (conv[0] - 3, conv[1] - 2.5, conv[2] - 2), (conv[0] + 3, conv[1] + 2.5, conv[2] + 2),
          cm("structure", 0.85), c, props("plume energy recovery and power conversion",
                                          ["power.recovered", "power.electric_load", "ledger.electric_house"]))
    K.box("A5_driver_hall", (drv[0] - 3.5, drv[1] - 3, drv[2] - 2), (drv[0] + 3.5, drv[1] + 3, drv[2] + 2),
          cm("structure", 0.85), c, props("heavy-ion drivers", ["driver.wall_plug_power", "driver.mass", "driver.beams",
                                                                "driver.reliability"]))
    r, thin = tr(V("power.recovered"))
    K.tube("A5_recovered_power", bez((x_l3, -14, O[2] - 6), (x_l3 + 2, -18, 4), (conv[0] - 8, conv[1], conv[2] + 3), conv),
           r, cm("fusion", 0.7), c, props("power recovered from the plume", ["power.recovered"], value_W=V("power.recovered"),
                                          drawn_min=thin, encoding="tube cross-section proportional to power"))
    r, thin = tr(V("driver.wall_plug_power"))
    K.tube("A5_driver_feed", [conv, (0, -16, 1), drv], r, cm("fusion", 0.7), c,
           props("driver wall-plug power", ["driver.wall_plug_power"], value_W=V("driver.wall_plug_power"), drawn_min=thin))
    nb = int(V("driver.beams"))
    beams = []
    r, thin = tr(V("driver.beam_power") / nb)
    for k in range(nb):
        a = 2 * math.pi * k / nb
        p = (drv[0] + 2.2 * math.cos(a), drv[1] + 2.2 * math.sin(a) * 0.6, drv[2] + 2)
        q = (O[0] + 0.0, O[1], O[2])
        beams.append((p, q, r, r))
    K.cones("A5_driver_beams", beams, cm("fusion", 1.15), c,
            props("driver beams into the target", ["driver.beam_power", "driver.beams", "driver.energy_per_pulse_beam"],
                  value_W=V("driver.beam_power"), drawn_min=thin), seg=6)
    label("A5_label", f"DRIVER LOOP  {P(V('power.recovered'))} recovered", (-4, -24, -6.5), 2.4, cm("fusion", 0.95), c)
    label("A5_sub", f"{P(V('driver.wall_plug_power'))} to drivers · reliability TBD", (-4, -24, -9.6), 1.8, ui("dim"), c)


# ---------------------------------------------------------------------------------------------------------------
def build_mass():
    c = coll("mass", "A6_STRUCTURE_AND_MASS", "NONE")
    x_sh = O[0] + nozzle_x(V("layout.x_shield_aft"))
    K.cones("A6_spine", [((x_sh + 1.6, O[1], O[2]), (MASS_X0, O[1], O[2]), 0.8, 0.8)], cm("structure", 0.8), c,
            props("thrust structure (schematic)", ["structure.total", "structure.q45_limit"]), seg=12)
    for i, (dy, dz) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        r_l1 = V("nozzle.loop1_r") / M_PER_BU_NOZZLE
        x_l1 = O[0] + nozzle_x(V("nozzle.loop1_x"))
        K.cones(f"A6_strut_{i}", [((x_l1, O[1] + dy * r_l1 * 0.7, O[2] + dz * r_l1 * 0.7), (x_sh, O[1] + dy * 2, O[2] + dz * 2),
                                   0.3, 0.3)], cm("structure", 0.75), c,
                props("nozzle struts (schematic)", ["geom.solid_angle_struts", "nozzle.interloop_force"]), seg=8)
    # the ship as a block: volume proportional to mass, 20 x 20 footprint, layers by mass
    side = 20.0
    y0, y1 = O[1] - side / 2, O[1] + side / 2
    z = O[2] - side / 2
    area = side * side
    layers = []
    starts = [V("burn1.start_mass")] + [V(f"burn{i}.end_mass") for i in (1, 2, 3)]
    ends = [V(f"burn{i}.end_mass") for i in (1, 2, 3, 4)]
    for i in (4, 3, 2, 1):
        layers.append((f"propellant burn {i}", starts[i - 1] - ends[i - 1], "propellant", 1.0 - 0.1 * (4 - i),
                       [f"burn{i}.start_mass", f"burn{i}.end_mass", "mass.propellant"]))
    layers.append(("reserve", V("mass.reserve"), "propellant", 0.55, ["mass.reserve"]))
    cat_of = {"payload": "structure", "drivers": "fusion", "nozzle": "fiji", "loop armour": "fiji", "target factory": "fusion",
              "shadow shield": "radiation", "FDP-1 structure": "structure", "hot radiators": "thermal",
              "warm radiators": "thermal", "low loop": "thermal", "tankage": "propellant", "idle hydrogen": "propellant"}
    for name, kg in M.mass_items.items():
        if kg <= 0 or name.startswith(("propellant", "warm-wing")):
            continue
        cat = next((v for k2, v in cat_of.items() if name.startswith(k2)), "structure")
        layers.append((name, kg, cat, 0.55, [f"mass.{name}"]))
    for name, kg, cat, shade, keys in layers:
        h = kg / 1e3 / MASS_T_PER_BU3 / area
        nm = "A6_mass_" + name.replace(" ", "_").replace(",", "").replace("(", "").replace(")", "")[:40]
        K.box(nm, (MASS_X0, y0, z), (MASS_X0 + side, y1, z + h * 0.999), cm(cat, shade), c,
              props("ship mass layer", keys, encoding=f"volume proportional to mass, 1 BU³ = {MASS_T_PER_BU3:.3f} t",
                    mass_kg=kg, label=name))
        z += h
    lx = MASS_X0 + side / 2
    label("A6_title", f"SHIP  {t_(V('mass.departure'))}", (lx, O[1], O[2] + side / 2 + 7), 4.0, ui("text"), c)
    label("A6_sub", f"propellant {t_(V('mass.propellant'))} (blue) · dry {t_(V('mass.dry'))}", (lx, O[1], O[2] + side / 2 + 3),
          2.0, ui("dim"), c)


def build_thrust():
    c = coll("thrust", "A2.thrust vs mass (1 BU = 1 MN)", PALETTE["exhaust"][1], COLL["prop"])
    F = V("prop.thrust")
    x0 = MASS_X0 + 20.0
    L = F / 1e6 / MN_PER_BU
    K.cones("A2_thrust_arrow_shaft", [((x0, O[1], O[2]), (x0 + L * 0.45, O[1], O[2]), 0.45, 0.45)], cm("exhaust", 1.2), c,
            props("thrust", ["prop.thrust", "calc.thrust_ma", "prop.a0_g"], encoding="arrow length proportional to force, 1 BU = 1 MN",
                  value_N=F), seg=16)
    K.cones("A2_thrust_arrow_head", [((x0 + L * 0.45, O[1], O[2]), (x0 + L, O[1], O[2]), 1.0, 0.0)], cm("exhaust", 1.2), c,
            props("thrust", ["prop.thrust"]), seg=16)
    label("A2_thrust_label", f"THRUST {F / 1e6:.2f} MN", (x0 + 6, O[1], O[2] + 6), 3.0, cm("exhaust", 1.2), c, align="LEFT")
    label("A2_thrust_sub", f"= {V('prop.a0_g'):.4f} g at departure", (x0 + 6, O[1], O[2] + 3), 2.0, ui("dim"), c, align="LEFT")


# ---------------------------------------------------------------------------------------------------------------
def build_1g():
    c = coll("g1", "A7_1G_COMPARISON", "NONE")
    cg = K.coll("A7.ghost thrust at 1 g", c, PALETTE["exhaust"][1])
    F1 = V("calc.1g.thrust")
    x0 = MASS_X0 + 20.0
    L1 = F1 / 1e6 / MN_PER_BU
    ghost = cm("exhaust", 1.0, 0.16)
    K.cones("A7_1g_thrust_ghost", [((x0, O[1], O[2]), (x0 + L1 - 6, O[1], O[2]), 0.9, 0.9)], ghost, cg,
            props("thrust needed for 1 g", ["calc.1g.thrust", "calc.1g.factor"], encoding="1 BU = 1 MN", value_N=F1), seg=24)
    K.cones("A7_1g_thrust_ghost_head", [((x0 + L1 - 6, O[1], O[2]), (x0 + L1, O[1], O[2]), 2.6, 0.0)], ghost, cg,
            props("thrust needed for 1 g", ["calc.1g.thrust"]), seg=24)
    label("A7_1g_thrust_label", f"1 g NEEDS {F1 / 1e6:.0f} MN", (x0 + L1 - 2, O[1], O[2] + 9), 4.0, cm("exhaust", 1.2), cg)
    label("A7_1g_thrust_sub", f"×{V('calc.1g.factor'):.0f} today", (x0 + L1 - 2, O[1], O[2] + 5), 2.4, ui("dim"), cg)
    for row in M.accel_rows[1:]:
        a = row["a_g"]
        if a > 1.0:
            continue
        x = x0 + row["thrust_N"] / 1e6 / MN_PER_BU
        K.ring(f"A7_tick_{a:g}g", (x, O[1], O[2]), "X", 1.7, 0.18, cm("exhaust", 1.0, 0.7), cg,
               props("acceleration step", ["target.accel_steps_g"], cls="CALC", a_g=a, thrust_N=row["thrust_N"]), seg=24, rseg=6)
        if a < 1.0:
            label(f"A7_tick_{a:g}g_label", f"{a:g} g", (x, O[1], O[2] - 4), 2.0, ui("dim"), cg)
    # ceiling at any size (record)
    ac = V("goal1g.max_a0_any_size_g")
    xc = x0 + ac / V("prop.a0_g") * V("prop.thrust") / 1e6 / MN_PER_BU
    K.ring("A7_ceiling_any_size", (xc, O[1], O[2]), "X", 2.2, 0.22, cm("unresolved"), cg,
           props("acceleration ceiling at any size", ["goal1g.max_a0_any_size_g", "goal1g.deficit_factor"]), seg=24, rseg=6)
    label("A7_ceiling_label", f"ceiling {ac:.4f} g at any size", (xc + 2, O[1], O[2] - 6.5), 2.0, cm("unresolved"), cg,
          align="LEFT")

    # the orb row: fusion power needed for each acceleration (same volume scale as the source)
    co = K.coll("A7.fusion power per acceleration (sphere volume ∝ power)", c, PALETTE["fusion"][1])
    x = -40.0
    prev = None
    for i, row in enumerate(M.accel_rows):
        a = row["a_g"]
        if a > 1.0:
            continue
        r = orb_r(row["fusion_W"])
        if prev is not None:
            x += prev + r + 6
        prev = r
        ctr = (x, G1_Y, FLOOR + r)
        today = i == 0
        last = abs(a - 1.0) < 1e-9
        alpha = 1.0 if today else (0.35 if last else 0.14)
        nm = "A7_orb_today" if today else f"A7_orb_{a:g}g"
        K.ball(nm, ctr, r, cm("fusion", 1.0 if (today or last) else 0.8, alpha), co,
               props("fusion power for an acceleration", ["calc.1g.fusion_power", "calc.1g.factor"] if last else ["fusion.power"],
                     cls="CALC" if not today else None, encoding="sphere volume proportional to power",
                     a_g=a, fusion_W=row["fusion_W"], factor=row["factor"]))
        txt = f"TODAY {a:.4f} g" if today else f"{a:g} g"
        label(nm + "_label", txt, (x, G1_Y, FLOOR + 2 * r + 4.5), 3.4 if (today or last) else 2.6,
              cm("fusion", 1.2) if (today or last) else ui("dim"), co)
        label(nm + "_sub", f"{P(row['fusion_W'])} · ×{row['factor']:.0f}" if not today else P(row["fusion_W"]),
              (x, G1_Y, FLOOR + 2 * r + 1.6), 2.0, ui("dim"), co)
    # the 1 g fusion ghost around the source (wire shells only, so the scene stays readable)
    r1 = orb_r(V("calc.1g.fusion_power"))
    pg = props("fusion power for 1 g around the source", ["calc.1g.fusion_power"], encoding="same sphere-volume scale")
    K.ball("A7_1g_ghost_source", O, r1, cm("fusion", 0.9, 0.05), co, pg, u=64, v=32)
    K.ring("A7_1g_ghost_equator", O, "Z", r1, 0.14, cm("fusion", 0.9, 0.55), co, pg, seg=128, rseg=6)
    label("A7_1g_ghost_label", f"1 g source {P(V('calc.1g.fusion_power'))}", (O[0], O[1], O[2] + r1 + 3), 2.8,
          cm("fusion", 1.0), co)

    # mass the 1 g hardware would need (power-scaled), same mass-volume scale as the ship
    cmass = K.coll("A7.power-scaled hardware mass at 1 g (block volume ∝ mass)", c, "NONE")
    s_ship = cube_side(V("mass.departure"))
    s_hw = cube_side(V("calc.power_scaled_mass"))
    s_1g = cube_side(V("calc.1g.scaled_mass"))
    xg = MASS_X0 + 20.0 + V("calc.1g.thrust") / 1e6 / MN_PER_BU + 10
    y = -s_1g / 2
    xs = xg
    ys = y - s_ship - 6
    K.box("A7_ship_block", (xs, ys, FLOOR), (xs + s_ship, ys + s_ship, FLOOR + s_ship), cm("structure", 1.0), cmass,
          props("ship departure mass", ["mass.departure"], encoding="volume proportional to mass", mass_kg=V("mass.departure")))
    K.box("A7_hardware_today", (xs + s_ship + 6, ys, FLOOR), (xs + s_ship + 6 + s_hw, ys + s_hw, FLOOR + s_hw),
          cm("structure", 0.75), cmass, props("power-scaled propulsion hardware today", ["calc.power_scaled_mass", "mass.alpha_jet"],
                                              mass_kg=V("calc.power_scaled_mass")))
    K.box("A7_hardware_1g_ghost", (xg, y, FLOOR), (xg + s_1g, y + s_1g, FLOOR + s_1g), cm("structure", 1.0, 0.18), cmass,
          props("power-scaled propulsion hardware at 1 g", ["calc.1g.scaled_mass", "calc.1g.scaled_mass_over_ship",
                                                            "mass.alpha_jet"], mass_kg=V("calc.1g.scaled_mass")))
    for (a, b) in _cube_edges(xg, y, FLOOR, s_1g):
        K.cones(f"A7_hardware_1g_edge_{len(cmass.objects)}", [(a, b, 0.25, 0.25)], cm("structure", 1.1), cmass,
                props("power-scaled propulsion hardware at 1 g", ["calc.1g.scaled_mass"]), seg=6)
    label("A7_ship_block_label", f"ship {t_(V('mass.departure'))}", (xs + s_ship / 2, ys, FLOOR + s_ship + 4), 2.6, ui("text"), cmass)
    label("A7_hw_today_label", f"engine today {t_(V('calc.power_scaled_mass'))}", (xs + s_ship + 6 + s_hw / 2, ys, FLOOR + s_hw + 4),
          2.0, ui("dim"), cmass)
    label("A7_hw_1g_label", f"1 g ENGINE ALONE  {t_(V('calc.1g.scaled_mass'))}",
          (xg + s_1g / 2, 0, FLOOR + s_1g + 8), 4.0, ui("text"), cmass)
    label("A7_hw_1g_sub", f"×{V('calc.1g.scaled_mass_over_ship'):.1f} the whole ship · needs ×{V('goal1g.deficit_factor'):.0f} lighter per watt",
          (xg + s_1g / 2, 0, FLOOR + s_1g + 3.5), 2.4, ui("dim"), cmass)

    # 1 g heat on the floor: the radiator area needed at today's temperatures
    a1 = V("calc.1g.warm_area") + V("calc.1g.hot_area")
    s = math.sqrt(a1) / M_PER_BU_HEAT
    cx, cy = HEAT_C[0], HEAT_C[1] + 60
    ch = K.coll("A7.radiator area at 1 g (true area, 1 BU = 40 m)", c, PALETTE["thermal"][1])
    pr = props("radiator area needed at 1 g", ["calc.1g.warm_area", "calc.1g.hot_area", "calc.1g.heat"],
               encoding="square of the true area, 1 BU = 40 m", area_m2=a1)
    K.quad("A7_1g_radiator_fill", [(cx - s / 2, cy - s / 2, FLOOR - 0.3), (cx + s / 2, cy - s / 2, FLOOR - 0.3),
                                   (cx + s / 2, cy + s / 2, FLOOR - 0.3), (cx - s / 2, cy + s / 2, FLOOR - 0.3)],
           cm("thermal", 0.6, 0.06), ch, pr)
    w = 1.2
    for nm, lo, hi in (("s", (cx - s / 2, cy - s / 2), (cx + s / 2, cy - s / 2 + w)), ("n", (cx - s / 2, cy + s / 2 - w), (cx + s / 2, cy + s / 2)),
                       ("w", (cx - s / 2, cy - s / 2), (cx - s / 2 + w, cy + s / 2)), ("e", (cx + s / 2 - w, cy - s / 2), (cx + s / 2, cy + s / 2))):
        K.box(f"A7_1g_radiator_edge_{nm}", (lo[0], lo[1], FLOOR - 0.2), (hi[0], hi[1], FLOOR + 0.3), cm("thermal", 1.0), ch, pr)
    label("A7_1g_radiator_label", f"1 g RADIATORS  {km2(a1)}", (cx + s / 2 - 10, cy + s / 2 - 14, FLOOR + 16), 7.0,
          cm("thermal", 1.15), ch, align="RIGHT")
    label("A7_1g_radiator_sub", f"{math.sqrt(a1) / 1e3:.1f} km square at today's temperatures · heat {P(V('calc.1g.heat'))}",
          (cx + s / 2 - 10, cy + s / 2 - 14, FLOOR + 9), 3.6, ui("dim"), ch, align="RIGHT")


def _cube_edges(x, y, z, s):
    P_ = [(x + i * s, y + j * s, z + k * s) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    out = []
    for a in range(8):
        for b in range(a + 1, 8):
            if sum(abs(P_[a][t] - P_[b][t]) > 1e-6 for t in range(3)) == 1:
                out.append((P_[a], P_[b]))
    return out


# ---------------------------------------------------------------------------------------------------------------
def build_mission():
    c = coll("mission", "A9_MISSION_FOUR_BURNS", PALETTE["propellant"][1])
    y, z = -38.0, FLOOR + 6
    x = MASS_X0
    h = 3.0
    for i in (1, 2, 3, 4):
        d = V(f"burn{i}.days")
        L = d / 365.25 / YEARS_PER_BU
        K.box(f"A9_burn_{i}", (x, y, z), (x + L - 0.4, y + 4, z + h), cm("exhaust", 1.0 - 0.08 * (i - 1)), c,
              props("burn", [f"burn{i}.days", f"burn{i}.start_mass", f"burn{i}.end_mass"], encoding=f"length proportional to time, 1 BU = {YEARS_PER_BU} y",
                    days=d))
        label(f"A9_burn_{i}_label", f"burn {i}  {d:.0f} d", (x + L / 2, y, z + h + 2.2), 1.9, ui("text"), c)
        x += L
    Lc = V("mission.coast_years_min") / YEARS_PER_BU
    K.box("A9_coast", (x, y, z), (x + Lc, y + 4, z + h * 0.5), cm("structure", 0.7), c,
          props("coast (total; how it splits between legs is not drawn)", ["mission.coast_years_min"]))
    x += Lc
    label("A9_end_label", f"{V('mission.min_round_trip_years'):.2f} y", (x + 1, y, z + h + 2.2), 2.4, ui("text"), c, align="LEFT")
    xl = MASS_X0 + V("canon.mission_duration_y") / YEARS_PER_BU
    K.box("A9_locked_6y", (xl - 0.3, y - 2, z - 1), (xl + 0.3, y + 6, z + h + 6), cm("unresolved"), c,
          props("canon LOCKED mission duration", ["canon.mission_duration_y", "calc.round_trip_vs_canon"]))
    label("A9_locked_label", f"LOCKED {V('canon.mission_duration_y'):.1f} y (conflict)", (xl, y, z + h + 8.5), 2.0, cm("unresolved"), c)
    L1g = V("calc.1g.total_days") / 365.25 / YEARS_PER_BU
    K.box("A9_1g_burns", (MASS_X0, y - 6, z), (MASS_X0 + max(L1g, 0.3), y - 2, z + h), cm("exhaust", 1.0, 0.5), c,
          props("all four burns at 1 g", ["calc.1g.total_days", "calc.1g.burn_days"]))
    label("A9_1g_label", f"at 1 g: {V('calc.1g.total_days'):.1f} d of burning", (MASS_X0 + 2, y - 4, z - 2.5), 1.9, ui("dim"), c,
          align="LEFT")
    label("A9_title", f"FOUR BURNS · Δv {V('calc.dv_total_c'):.3f} c", (MASS_X0, y, z + h + 13), 3.0, cm("propellant", 1.2), c,
          align="LEFT")


# ---------------------------------------------------------------------------------------------------------------
SAT = {  # requirement satellite: anchor point (on its object) and satellite offset
    "P01": ((0, 0, 30), (-20, -4, 4)),
    "P02": ((6, -16, 3), (8, -8, -12)),
    "P03": ((MASS_X0 + 20, 0, 20), (14, -6, 14)),
    "P04": ((nozzle_x(V("nozzle.loop3_x")), 0, 20 + V("nozzle.loop3_r") / 3), (-10, 0, 8)),
    "P05": ((nozzle_x(V("layout.x_shield_aft")), 0, 23), (4, -10, 16)),
    "P06": ((-4, 48, 2), (-14, -6, 12)),
    "P07": ((30, HEAT_C[1] + 30, FLOOR + 50), (0, -6, 14)),
    "P08": ((MASS_X0, -10, 14), (-8, -12, -10)),
    "P09": ((25, 0, 20.8), (0, 8, 14)),
    "P10": ((MASS_X0 + 60, -38, FLOOR + 9), (0, -4, 14)),
}


def build_satellites():
    c = coll("req", "A10_REQUIREMENT_SATELLITES", PALETTE["unresolved"][1])
    for rq in M.requirements:
        rid = rq["id"]
        anchor, off = SAT[rid]
        s = (anchor[0] + off[0], anchor[1] + off[1], anchor[2] + off[2])
        cc = K.coll(f"A10.{rid} {rq['title']}", c, PALETTE["unresolved"][1])
        p = {"component": "requirement satellite", "req_ids": rid, "classification": ",".join(rq["classification"]),
             "value_keys": ",".join(rq["params"]), "status": rq["status"], "title": rq["title"],
             "description": M.render(rq["description"]), "target": M.render(rq["target"]), "gap": M.render(rq["gap"]),
             "current": " | ".join(M.render(x) for x in rq["current"]), "depends": ",".join(rq["depends"]), "layer": "A"}
        shade = 1.0 if rq["status"] in ("unresolved", "speculative") else 0.75
        bm_mat = cm("unresolved", shade)
        o = K.ball(f"REQ_{rid}_satellite", s, 1.5, bm_mat, cc, p, u=4, v=2, smooth=False)   # an octahedron
        K.cones(f"REQ_{rid}_tether", [(s, anchor, 0.08, 0.08)], cm("unresolved", 0.8, 0.8), cc, p, seg=5)
        K.ball(f"REQ_{rid}_anchor", anchor, 0.45, cm("unresolved", 1.0), cc, p, u=8, v=4)
        label(f"REQ_{rid}_label", rid, (s[0], s[1], s[2] + 2.8), 2.2, cm("unresolved", 1.1), cc, p=p)
        short = {"P01": "fusion gain", "P02": "driver", "P03": "power per mass", "P04": "nozzle", "P05": "radiation",
                 "P06": "heat transport", "P07": "radiator area", "P08": "fuel", "P09": "structure", "P10": "mission"}[rid]
        label(f"REQ_{rid}_short", f"{short} · {rq['status']}", (s[0], s[1], s[2] - 2.6), 1.3, ui("dim"), cc, p=p)


# ---------------------------------------------------------------------------------------------------------------
def build_layer_b(sc):
    """The phase-1 technical board, hidden by default, parked beside Layer A."""
    root = K.coll("LAYER_B_TECHNICAL_SUPPORT", None, "NONE")
    before = set(c.name for c in sc.collection.children)
    for key in BD.SECTIONS:
        BD.section(key)
    BD.build_title()
    BD.build_legend()
    BD.build_overview()
    BD.build_fusion()
    BD.build_magnifier()
    BD.build_rocket()
    BD.build_mass()
    BD.build_gap()
    BD.build_split()
    BD.build_geometry()
    BD.build_tarea()
    BD.build_scale()
    BD.build_mission()
    BD.build_requirements()
    anchor = bpy.data.objects.new("LAYER_B_BOARD_ORIGIN", None)
    root.objects.link(anchor)
    anchor.location = (700.0, 0.0, 0.0)
    for c in list(sc.collection.children):
        if c.name in before or c.name == root.name or c.name == ROOT_A.name:
            continue
        sc.collection.children.unlink(c)
        root.children.link(c)
    for o in root.all_objects:
        if o is not anchor and o.parent is None:
            o.parent = anchor
            o["layer"] = "B"
    root.hide_render = True
    return root, anchor


# ---------------------------------------------------------------------------------------------------------------
CAMERAS = []


def camera(name, loc, target, lens=35.0, res=(3840, 2160), ortho=None, light="STUDIO", note=""):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start, cam.clip_end = 0.5, 6000
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    o = bpy.data.objects.new(name, cam)
    COLL["cams"].objects.link(o)
    o.location = loc
    d = mathutils.Vector(target) - mathutils.Vector(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    o["resolution"] = list(res)
    o["light"] = light
    o["note"] = note
    CAMERAS.append(o)
    return o


def build_cameras(sc, board_anchor):
    COLL["cams"] = K.coll("CAMERAS_AND_LIGHTING", None, "NONE")
    camera("CAM_01_MAIN_OVERVIEW", (-195, -420, 260), (100, -55, -15), 30, note="whole spatial model")
    camera("CAM_02_FUSION_TRANSFORMATION", (-60, -160, 55), (0, 5, 14), 35, note="source and its four branches")
    camera("CAM_03_THRUST_VS_MASS", (150, -250, 80), (175, 0, 10), 30, note="1.40 MN against 20,760 t; the 1 g arrow")
    camera("CAM_04_HEAT_MANAGEMENT", (-75, 40, 75), (15, 150, -20), 30, note="heat filaments, wings to scale, plates")
    camera("CAM_05_1G_COMPARISON", (110, -520, 170), (150, -110, 10), 30, note="power and mass needed for 1 g")
    camera("CAM_06_REQUIREMENT_OVERLAY", (-110, -150, 110), (20, 0, 10), 34, note="P01-P10 satellites on their objects")
    camera("CAM_07_ISOMETRIC", (300, -300, 300), (40, 0, 0), 50, ortho=620, note="axonometric whole model")
    camera("CAM_08_MISSION_AND_PROPELLANT", (95, -120, 40), (85, -20, 5), 35, note="four burns, propellant layers, 6.0 y conflict")
    camera("CAM_09_TEMPERATURE_PROGRESSION", (88, 45, 38), (88, 180, 0), 35, note="800-2500 K radiator areas")
    bx, by = board_anchor.location.x, board_anchor.location.y
    W, H = 5 * BD.PW + 4 * BD.G, 3 * BD.PH + 2 * BD.G + BD.TOP
    camera("CAM_10_LAYER_B_TECHNICAL_BOARD", (bx + W / 2 - 3, by - H / 2 + BD.TOP + 2, 500), (bx + W / 2 - 3, by - H / 2 + BD.TOP + 2, 0),
           ortho=W + 10, light="FLAT", note="technical support board (Layer B, shown only for this camera)")
    sc.frame_start, sc.frame_end = 1, len(CAMERAS)
    for i, o in enumerate(CAMERAS):
        mk = sc.timeline_markers.new(o.name, frame=i + 1)
        mk.camera = o
    sc.camera = CAMERAS[0]
    sun = bpy.data.lights.new("SUN_key", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("SUN_key", sun)
    so.rotation_euler = (math.radians(40), math.radians(15), math.radians(-35))
    COLL["cams"].objects.link(so)


# ---------------------------------------------------------------------------------------------------------------
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
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "SOLID"
                        sp.shading.light = "STUDIO"
                        sp.shading.color_type = "MATERIAL"
                        sp.shading.background_type = "WORLD"
                        sp.overlay.show_floor = False
                        sp.overlay.show_axis_x = False
                        sp.overlay.show_axis_y = False
                        sp.overlay.show_relationship_lines = False
                        sp.clip_end = 6000
                        sp.region_3d.view_perspective = "CAMERA"


def set_layer_b_visible(sc, root, on):
    root.hide_render = not on
    lc = sc.view_layers[0].layer_collection.children[root.name]
    lc.hide_viewport = not on
    a = sc.view_layers[0].layer_collection.children[ROOT_A.name]
    a.hide_viewport = on
    ROOT_A.hide_render = on


def render_all(sc, broot):
    os.makedirs(RENDER_DIR, exist_ok=True)
    for i, o in enumerate(CAMERAS):
        if ONLY and not any(o.name.startswith("CAM_" + k) for k in ONLY):
            continue
        sc.frame_set(i + 1)
        sc.camera = o
        VIEW.rotation_euler = o.rotation_euler          # same as the driver; explicit for the render
        b = "LAYER_B" in o.name
        set_layer_b_visible(sc, broot, b)
        rx, ry = o["resolution"]
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        sc.render.resolution_percentage = PCT
        sc.display.shading.light = o["light"]
        sc.render.filepath = os.path.join(RENDER_DIR, o.name + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", o.name, rx, ry)
    set_layer_b_visible(sc, broot, False)
    sc.frame_set(1)
    sc.camera = CAMERAS[0]
    sc.render.resolution_x, sc.render.resolution_y = 3840, 2160
    sc.render.resolution_percentage = 100
    sc.display.shading.light = "STUDIO"


def write_texts():
    for fname, tname in (("README.md", "README_FDP1"), ("VISUAL_GRAMMAR.md", "VISUAL_GRAMMAR")):
        p = os.path.join(HERE, fname)
        if os.path.exists(p):
            bpy.data.texts.new(tname).write(open(p).read())
    bpy.data.texts.new("VALIDATION").write(
        "\n".join(("PASS " if c["ok"] else "FAIL ") + f"[{c['kind']}] {c['name']}: {c['detail']}" for c in M.checks))


def main():
    global ROOT_A
    sc = reset_scene()
    view_align(sc)
    ROOT_A = K.coll("LAYER_A_SPATIAL_MODEL", None, "NONE")
    build_reference()
    build_fusion()
    build_propulsion()
    build_radiation()
    man_hot, man_warm = build_heat()
    build_radiators(man_hot, man_warm)
    build_temperatures()
    build_driver()
    build_mass()
    build_thrust()
    build_1g()
    build_mission()
    build_satellites()
    n_a = len(ROOT_A.all_objects)
    broot, anchor = build_layer_b(sc)
    build_cameras(sc, anchor)
    setup_display(sc)
    write_texts()
    set_layer_b_visible(sc, broot, False)
    sc["fdp1_record"] = M.doc["meta"]["record"]
    sc["checks_passed"] = sum(c["ok"] for c in M.checks)
    sc["checks_total"] = len(M.checks)
    print(f"layer A objects: {n_a}, layer B objects: {len(broot.all_objects)}, cameras: {len(CAMERAS)}")
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    if "--render" in ARGS:
        render_all(sc, broot)
    setup_viewports()
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print("saved", OUT_BLEND)


main()
