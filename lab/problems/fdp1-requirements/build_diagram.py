"""Build FDP-1_Engineering_Requirements.blend: an engineering problem map of FDP-1 (Fiji Drive Pulsed prototype 1).

Run from the repository root:
    /snap/bin/blender -b --factory-startup -P lab/problems/fdp1-requirements/build_diagram.py -- [--render] [--out DIR]

It reads data/fdp1_parameters.json and data/requirements.json, derives every printed number in fdp1diag/model.py,
stops if a validation check fails, builds the scene from scratch in an empty file, saves the .blend next to this
script and, with --render, writes PNG previews of every camera. It never opens or writes a Wayfarer asset.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from fdp1diag.bkit import PALETTE, UI, Kit, srgb_to_lin, text_w, wrap  # noqa: E402
from fdp1diag.model import Model, fmt_power, sig  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_BLEND = os.path.join(HERE, "FDP-1_Engineering_Requirements.blend")
RENDER_DIR = ARGS[ARGS.index("--out") + 1] if "--out" in ARGS else os.path.join(HERE, "renders")

PW, PH, G = 100.0, 75.0, 4.0          # panel width/height and gutter, diagram units (BU)
TOP = 34.0                            # title band height above the panel grid
S_T, S_SUB, S_B, S_S, S_XS = 2.6, 1.15, 1.05, 0.88, 0.74   # text sizes

M = Model()
bad = [c for c in M.checks if not c["ok"]]
if bad:
    raise SystemExit("validation failed: " + "; ".join(f"{c['name']}: {c['detail']}" for c in bad))
V, R = M.v, M.render
K = Kit()


def P(s):
    return fmt_power(s)


# ---------------------------------------------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "FDP1_REQUIREMENTS"
    sc.unit_settings.system = "NONE"
    w = bpy.data.worlds.new("FDP1_World")
    w.color = srgb_to_lin(UI["bg"])
    w.use_nodes = True
    bgn = w.node_tree.nodes.get("Background")
    if bgn:
        bgn.inputs[0].default_value = (*srgb_to_lin(UI["bg"]), 1)
        bgn.inputs[1].default_value = 1.0
    sc.world = w
    return sc


SECTIONS = {
    "00": ("00_REFERENCES_AND_LEGEND", "NONE"),
    "01": ("01_SYSTEM_OVERVIEW", "NONE"),
    "02": ("02_FUSION_ENERGY", PALETTE["fusion"][1]),
    "03": ("03_THRUST_AND_PROPELLANT", PALETTE["propellant"][1]),
    "04": ("04_MASS_AND_ACCELERATION", "NONE"),
    "05": ("05_RADIATION_AND_THERMAL", PALETTE["thermal"][1]),
    "06": ("06_MISSION_PROFILE", PALETTE["exhaust"][1]),
    "07": ("07_REQUIREMENTS", PALETTE["unresolved"][1]),
    "08": ("08_CAMERAS_AND_LIGHTING", "NONE"),
}
CAT_LABEL = {"fusion": "fusion energy (orange)", "exhaust": "directed exhaust (cyan)", "propellant": "propellant (blue)",
             "thermal": "waste heat (red)", "radiation": "radiation (magenta)", "structure": "mass & structure (grey)",
             "fiji": "Fiji magnetics (violet)", "unresolved": "unresolved (yellow)", "verified": "verified (green)"}


def section(key):
    name, tag = SECTIONS[key]
    return K.coll(name, None, tag)


def sub(key, cat, label=None):
    parent = section(key)
    name = f"{key}.{label or CAT_LABEL[cat]}"
    return K.coll(name, parent, PALETTE[cat][1] if cat in PALETTE else "NONE")


def sub_ui(key, label):
    return K.coll(f"{key}.{label}", section(key), "NONE")


# ---------------------------------------------------------------------------------------------------------------
class Panel:
    """A framed diagram panel at grid cell (c, r), spanning cw columns and rh rows."""

    def __init__(self, key, pid, title, subtitle, c, r, cw=1, rh=1, accent="structure", headline=None, head_cat=None):
        self.key, self.pid = key, pid
        self.x0 = c * (PW + G)
        self.y0 = -r * (PH + G)
        self.W = cw * PW + (cw - 1) * G
        self.H = rh * PH + (rh - 1) * G
        self.frame_coll = sub_ui(key, f"panel {pid} frame and labels")
        self.lab = self.frame_coll
        x0, y0 = self.x0, self.y0
        K.rect(f"{pid}_bg", x0, y0 - self.H, x0 + self.W, y0, K.ui_mat("panel"), self.frame_coll, -0.6, -0.4,
               {"panel": pid})
        K.frame(f"{pid}_edge", x0, y0 - self.H, x0 + self.W, y0, 0.18, K.ui_mat("panel_edge"), self.frame_coll, -0.4, -0.3)
        K.rect(f"{pid}_accent", x0 + 2, y0 - 2.0, x0 + 2.5, y0 - 5.6, K.cat_mat(accent), self.frame_coll, -0.3, 0.0)
        self.t(f"{pid}_title", title, 3.4, 2.0, S_T, "text")
        if subtitle:
            self.t(f"{pid}_subtitle", subtitle, 3.4, 5.4, S_SUB, "dim")
        if headline:
            self.t(f"{pid}_headline", headline, self.W - 2.5, 1.6, 3.6, None, align="RIGHT",
                   mat=K.cat_mat(head_cat or accent, 1.15))
        K.rect(f"{pid}_rule", x0 + 2, y0 - 8.1, x0 + self.W - 2, y0 - 8.22, K.ui_mat("grid"), self.frame_coll, -0.3, -0.2)
        self.bounds = (x0, y0 - self.H, x0 + self.W, y0)

    def w(self, px, py):
        return (self.x0 + px, self.y0 - py)

    def t(self, name, body, px, py, size, ui="text", align="LEFT", mat=None, coll=None, valign="TOP", props=None, z=0.6):
        x, y = self.w(px, py)
        return K.text(name, body, x, y, size, mat or K.ui_mat(ui), coll or self.lab, align, valign, z, props)

    def rect(self, name, px0, py0, px1, py1, mat, coll, z0=0.0, z1=0.2, props=None):
        (x0, y0), (x1, y1) = self.w(px0, py0), self.w(px1, py1)
        return K.rect(name, x0, y0, x1, y1, mat, coll, z0, z1, props)

    def rrect(self, name, px0, py0, px1, py1, r, mat, coll, z0=0.0, z1=0.2, props=None):
        (x0, y0), (x1, y1) = self.w(px0, py0), self.w(px1, py1)
        return K.rrect(name, x0, y0, x1, y1, r, mat, coll, z0, z1, props)

    def frame(self, name, px0, py0, px1, py1, wd, mat, coll, z0=0.0, z1=0.15, props=None, dashed=0.0):
        (x0, y0), (x1, y1) = self.w(px0, py0), self.w(px1, py1)
        return K.frame(name, x0, y0, x1, y1, wd, mat, coll, z0, z1, props, dashed)

    def seg(self, name, a, b, wd, mat, coll, z0=0.0, z1=0.15, props=None):
        return K.seg(name, self.w(*a), self.w(*b), wd, mat, coll, z0, z1, props)

    def poly(self, name, pts, wd, mat, coll, z0=0.0, z1=0.15, props=None):
        return K.polyline(name, [self.w(*p) for p in pts], wd, mat, coll, z0, z1, props)

    def prism(self, name, pts, mat, coll, z0=0.0, z1=0.2, props=None):
        return K.prism(name, [self.w(*p) for p in pts], z0, z1, mat, coll, props)

    def arrow(self, name, pts, wd, mat, coll, z0=0.0, z1=0.2, props=None, head=None, head_len=None):
        return K.arrow(name, [self.w(*p) for p in pts], wd, mat, coll, z0, z1, props, head, head_len)

    def dash(self, name, a, b, wd, d, mat, coll, z0=0.0, z1=0.12, props=None, gap=None):
        return K.dashes(name, self.w(*a), self.w(*b), wd, d, mat, coll, z0, z1, props, gap)

    def disc(self, name, px, py, r, mat, coll, z0=0.0, z1=0.2, props=None):
        x, y = self.w(px, py)
        return K.disc(name, x, y, r, mat, coll, z0, z1, props)


# glyphs for the five classifications ------------------------------------------------------------------------------
CLS_NAME = {"EST": "Established", "CALC": "Calculated", "ASSUMED": "Assumed", "UNKNOWN": "Unknown (TBD)",
            "PROPOSED": "Proposed"}


def glyph(p, name, px, py, cls, s=0.8, coll=None):
    coll = coll or p.lab
    cx, cy = px + s / 2, py + s / 2
    white = K.ui_mat("text")
    if cls == "EST":
        p.rect(name, px, py, px + s, py + s, white, coll, 0.2, 0.4)
    elif cls == "CALC":
        p.frame(name, px, py, px + s, py + s, s * 0.17, white, coll, 0.2, 0.4)
    elif cls == "ASSUMED":
        h = s * 0.62
        pts = [(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy), (cx, cy - h)]
        p.poly(name, pts, s * 0.15, K.ui_mat("dim"), coll, 0.2, 0.4)
    elif cls == "UNKNOWN":
        p.disc(name, cx, cy, s * 0.5, K.cat_mat("unresolved"), coll, 0.2, 0.4)
    elif cls == "PROPOSED":
        h = s * 0.6
        pts = [(cx - h, cy + h * 0.8), (cx + h, cy + h * 0.8), (cx, cy - h * 0.9), (cx - h, cy + h * 0.8)]
        p.poly(name, pts, s * 0.12, K.cat_mat("fiji", 1.2), coll, 0.2, 0.4)


def kv(p, name, px, py, label, value, cls, vx=None, vcat=None, size=S_S, coll=None, keys=(), req=()):
    """One value line: classification glyph, dim label, coloured value."""
    coll = coll or p.lab
    props = {"value_keys": ",".join(keys), "req_ids": ",".join(req), "classification": cls}
    glyph(p, f"{name}_g", px, py + size * 0.08, cls, size * 0.78, coll)
    p.t(f"{name}_l", label, px + size * 1.25, py, size, "dim", coll=coll, props=props)
    vm = K.cat_mat(vcat, 1.12) if vcat else (K.cat_mat("unresolved") if "TBD" in value else K.ui_mat("text"))
    p.t(f"{name}_v", value, vx if vx is not None else px + size * 1.25 + text_w(label, size) + size * 0.8, py, size,
        mat=vm, coll=coll, props=props)


def tag(p, rid, px, py, coll=None, s=1.0):
    """Yellow requirement tag (P01..P10) placed on a component."""
    coll = coll or sub(p.key, "unresolved", "requirement tags (yellow)")
    w = s * 3.3
    p.rrect(f"TAG_{rid}_{p.pid}_{int(px)}_{int(py)}", px, py, px + w, py + s * 1.55, s * 0.35, K.cat_mat("unresolved"),
            coll, 0.9, 1.1, {"req_ids": rid})
    p.t(f"TAGT_{rid}_{p.pid}_{int(px)}_{int(py)}", rid, px + w / 2, py + s * 0.27, s * 0.98, mat=K.ui_mat("dark"),
        align="CENTER", coll=coll, z=1.2, props={"req_ids": rid})


def para(p, name, s, px, py, size, chars, ui="dim", mat=None, coll=None, line=1.2):
    lines = wrap(s, chars)
    p.t(name, "\n".join(lines), px, py, size, ui, mat=mat, coll=coll)
    return py + len(lines) * size * line


# ===============================================================================================================
def build_title():
    coll = sub_ui("00", "title band")
    x0, y0 = 0.0, TOP
    Wt = 5 * PW + 4 * G
    K.text("TITLE", "FDP-1 ENGINEERING REQUIREMENTS MAP", x0 + 1, y0 - 2, 6.2, K.ui_mat("text"), coll)
    K.text("TITLE_sub", "GU Wayfarer 01 · Fiji Drive Pulsed prototype 1 · why it reaches 0.016 c on four burns but not 1 g"
           " · a map of the problems, not a solution", x0 + 1.2, y0 - 10.2, 2.0, K.ui_mat("dim"), coll)
    K.text("TITLE_src", "Source: FDP-1 record fdp1-v1 (speculative tier, not canon), branch claude/project-thread-8e13aa"
           " @ ec5717d · canon data/wayfarer_3d.toml · every number derived in fdp1diag/model.py from"
           " data/fdp1_parameters.json", x0 + 1.2, y0 - 13.6, 1.25, K.ui_mat("faint"), coll)
    # answer banner
    bx0, by1, by0 = 0.0, TOP - 17.0, 3.0
    K.rect("ANSWER_bg", bx0, by0, Wt, by1, K.ui_mat("dark"), coll, -0.6, -0.4)
    K.rect("ANSWER_bar", bx0, by0, bx0 + 0.8, by1, K.cat_mat("unresolved"), coll, -0.4, -0.2)
    K.text("ANSWER_h", "THE ANSWER", bx0 + 2.5, by1 - 1.6, 2.2, K.cat_mat("unresolved"), coll)
    ans = R("Reaching 0.016 c four times is a propellant question: the mission's 0.064 c is "
            "{calc.burn_fraction_of_ve:.2f} × v_e, so a mass ratio of {calc.mass_ratio:.2f} closes it whatever the "
            "acceleration. Acceleration is a power-per-kilogram question: 1 g at {mass.departure!t} needs "
            "{calc.1g.fusion_power!P} of fusion ({calc.1g.factor:.0f}×), and hardware that scales with power would weigh "
            "{calc.1g.scaled_mass_over_ship:.0f}× the whole ship. No FDP-1 of any size closes above "
            "{goal1g.max_a0_any_size_g:.4f} g.")
    K.text("ANSWER_t", "\n".join(wrap(ans, 150)), bx0 + 2.5, by1 - 5.0, 1.55, K.ui_mat("text"), coll, line=1.25)
    # headline gauges
    gx = 352.0
    for i, (big, small, cat) in enumerate((
            (R("{prop.a0_g:.4f} g"), "FDP-1 departure acceleration", "exhaust"),
            (R("×{calc.1g.factor:.0f}"), "fusion power for 1 g, same mass", "fusion"),
            (R("×{goal1g.deficit_factor:.0f}"), "lighter per watt needed for 1 g", "unresolved"),
            (R("{calc.heat_total!P}"), "waste heat to radiators", "thermal"))):
        x = gx + i * 41.0
        K.text(f"GAUGE_{i}", big, x, by1 - 1.2, 5.0, K.cat_mat(cat, 1.12), coll)
        K.text(f"GAUGE_{i}_s", small, x + 0.1, by1 - 8.2, 1.25, K.ui_mat("dim"), coll)


# ===============================================================================================================
def build_legend():
    p = Panel("00", "P00", "LEGEND, CLASSES AND CHECKS", "colour = function · glyph = how well the number is known", 0, 0)
    c = sub_ui("00", "legend items")
    y = 10.5
    p.t("LEG_hc", "FUNCTIONAL COLOURS (objects and Outliner collections)", 3, y, S_S, "dim", coll=c)
    y += 2.0
    names = [("fusion", "Fusion energy generation"), ("exhaust", "Directed exhaust / useful propulsion"),
             ("propellant", "Propellant and fuel"), ("thermal", "Waste heat / thermal systems"),
             ("radiation", "Neutrons / X-rays / radiation"), ("structure", "Spacecraft mass / structure"),
             ("fiji", "Fiji magnetic systems"), ("unresolved", "Unresolved requirements"),
             ("verified", "Verified or satisfied requirements")]
    for i, (cat, lab) in enumerate(names):
        col, row = i % 2, i // 2
        px, py = 3 + col * 48, y + row * 2.3
        p.rrect(f"LEG_sw_{cat}", px, py, px + 3.2, py + 1.4, 0.3, K.cat_mat(cat), c, 0.0, 0.4)
        p.t(f"LEG_t_{cat}", lab, px + 4.2, py + 0.15, S_S, coll=c)
    y += 5 * 2.3 + 1.0
    p.t("LEG_tag", "Outliner: no cyan tag exists, so cyan shares blue; grey = untagged", 3, y, S_XS, "faint", coll=c)
    y += 2.4
    p.t("LEG_hk", "CLASSIFICATION OF EVERY NUMBER", 3, y, S_S, "dim", coll=c)
    y += 2.0
    desc = {"EST": "canon, owner target or SI constant", "CALC": "derived here by the stated formula",
            "ASSUMED": "FDP-1 model output on provisional assumptions", "UNKNOWN": "no validated figure: shown as TBD",
            "PROPOSED": "future candidate, not FDP-1 (none used)"}
    for i, k in enumerate(("EST", "CALC", "ASSUMED", "UNKNOWN", "PROPOSED")):
        glyph(p, f"LEG_g_{k}", 3, y + i * 1.9, k, 1.0, c)
        p.t(f"LEG_gt_{k}", f"{CLS_NAME[k]}: {desc[k]}", 5.0, y + i * 1.9, S_S, coll=c)
    y += 5 * 1.9 + 1.0
    p.t("LEG_ha", "ARROWS AND BARS", 3, y, S_S, "dim", coll=c)
    y += 2.0
    p.arrow("LEG_arrow_scaled", [(3, y + 0.8), (14, y + 0.8)], 1.2, K.cat_mat("exhaust"), c)
    p.t("LEG_arrow_scaled_t", "solid width ∝ a stated, known magnitude (scale printed on the panel)", 16, y + 0.2, S_S,
        coll=c)
    y += 2.2
    p.dash("LEG_arrow_unscaled", (3, y + 0.8), (12.5, y + 0.8), 0.35, 0.9, K.cat_mat("radiation"), c)
    p.prism("LEG_arrow_unscaled_h", [(12.5, y + 0.1), (14, y + 0.8), (12.5, y + 1.5)], K.cat_mat("radiation"), c)
    p.t("LEG_arrow_unscaled_t", "dashed = direction only, not to width scale", 16, y + 0.2, S_S, coll=c)
    y += 2.2
    tag(p, "P05", 3, y, c, 0.8)
    p.t("LEG_tag_t", "requirement tag: the problem this element feeds (panel 07)", 6.6, y + 0.15, S_S, coll=c)
    y += 2.6
    # checks
    kinds = {}
    for ch in M.checks:
        kinds.setdefault(ch["kind"], [0, 0])
        kinds[ch["kind"]][0] += ch["ok"]
        kinds[ch["kind"]][1] += 1
    ok = sum(ch["ok"] for ch in M.checks)
    cv = sub("00", "verified", "validation (green)")
    p.rrect("CHK_bg", 3, y - 0.4, 97, y + 4.2, 0.6, K.cat_mat("verified", 0.25), cv, -0.2, 0.0)
    p.t("CHK_h", f"VALIDATION  {ok}/{len(M.checks)} checks pass", 4.2, y + 0.1, S_B, mat=K.cat_mat("verified", 1.1),
        coll=cv)
    p.t("CHK_t", "   ".join(f"{k} {a}/{b}" for k, (a, b) in kinds.items()) + "   (fdp1diag/model.py; build stops on a failure)",
        4.2, y + 2.0, S_XS, coll=cv)
    y += 5.6
    para(p, "LEG_nav", "Views: Numpad 0 shows the active camera; scrub the timeline (frames 1-15) to step through the "
         "cameras, or pick one in 08_CAMERAS_AND_LIGHTING. Hide a section with its collection's eye toggle.", 3, y,
         S_XS, 150, "faint", coll=c)


# ===============================================================================================================
def build_overview():
    p = Panel("01", "P01", "FDP-1 FUNCTIONAL SCHEMATIC",
              "side view, not to scale · flows run left (bow) to right (aft); thrust pushes the ship to the left",
              1, 0, cw=2, accent="structure")
    cs = sub("01", "structure")
    cp = sub("01", "propellant")
    cf = sub("01", "fusion")
    ce = sub("01", "exhaust")
    ct = sub("01", "thermal")
    cr = sub("01", "radiation")
    cj = sub("01", "fiji")
    cu = sub("01", "unresolved", "requirement tags (yellow)")
    lab = sub_ui("01", "labels")
    cy = 41.0
    X = lambda px: p.w(px, 0)[0]
    Y = lambda py: p.w(0, py)[1]
    gray = K.cat_mat("structure")
    gray_d = K.cat_mat("structure", 0.55)

    def comp(name, cat):
        return {"component": name, "category": cat}

    # spine and payload
    K.cylinder_x("OV_spine", X(5), X(137), Y(cy), 0, 1.0, gray_d, cs, comp("spine", "structure"))
    K.cylinder_x("OV_payload_hull", X(5), X(26), Y(cy), 0, 3.2, gray, cs, comp("ship and payload", "structure"))
    K.torus_x("OV_hab_ring_A", X(12), Y(cy), 0, 8.0, 0.55, gray, cs, comp("habitat ring", "structure"))
    K.torus_x("OV_hab_ring_B", X(19), Y(cy), 0, 8.0, 0.55, gray, cs, comp("habitat ring", "structure"))
    p.t("OV_payload_t", "Ship & payload\n" + sig(V("mass.payload (non-propulsion ship)") / 1e3, 3) + " t (canon mass model)", 5, 52.5, S_S,
        coll=lab)
    # tanks
    for i, (dy, shade, nm) in enumerate(((-3.6, 1.0, "He-3"), (3.6, 1.0, "He-3"), (-3.6, 0.7, "D"), (3.6, 0.7, "D"))):
        x0 = 29 if i < 2 else 47
        K.cylinder_x(f"OV_tank_{i}", X(x0), X(x0 + 16), Y(cy + dy), 0, 3.0, K.cat_mat("propellant", shade), cp,
                     comp("tanks", "propellant"))
    p.t("OV_tank_t", R("D–³He propellant {mass.propellant!t}\nHe-3 {mass.he3!t:4} · D {mass.d!t:4}\n"
                       "tanks ×{calc.tank_ratio_he3:.1f} the existing farm"), 29, 47.5, S_S, coll=lab)
    tag(p, "P08", 56.5, 31.5, cu)
    # radiator wings (red) with break marks
    for sgn in (-1, 1):
        y_root, y_tip = cy + sgn * 4.0, cy + sgn * 27.5
        p.rect(f"OV_wing_hot_{sgn}", 67, y_root, 87, y_root + sgn * 3.5, K.cat_mat("thermal", 1.18), ct, -0.1, 0.25,
               comp("radiators", "thermal"))
        p.rect(f"OV_wing_warm_{sgn}", 67, y_root + sgn * 3.5, 87, y_tip, K.cat_mat("thermal", 0.72), ct, -0.1, 0.25,
               comp("radiators", "thermal"))
        yb = y_root + sgn * 15
        for k in range(2):
            p.prism(f"OV_wing_break_{sgn}_{k}", [(66, yb + k * 1.2 - 0.25), (88, yb + k * 1.2 - 1.1),
                                                (88, yb + k * 1.2 - 0.6), (66, yb + k * 1.2 + 0.25)],
                    K.ui_mat("panel"), ct, 0.25, 0.3)
    p.t("OV_wing_t", R("Radiator wings: 2 × {rad.wing_span:,.0f} m span\nwarm {rad.warm_area!km2} at {rad.warm_T:.0f} K, "
                       "hot band at {rad.hot_T:.0f} K\ntip radius {rad.wing_tip_radius!s} m (drawn ~1:130)"),
        89, 10.5, S_S, coll=lab)
    tag(p, "P07", 89, 17.0, cu)
    # thermal collection manifolds (hot loop from nozzle/shield, warm from drivers) to wing roots
    hot = K.cat_mat("thermal", 1.18)
    p.poly("OV_manifold_hot", [(150.5, cy + 6.2), (132, cy + 6.2), (88, cy + 6.2), (88, cy + 4.2)], 0.45, hot, ct, 0.3, 0.6,
           comp("thermal collection", "thermal"))
    p.poly("OV_manifold_warm", [(120, cy - 6.0), (88, cy - 6.0), (88, cy - 4.2)], 0.45, K.cat_mat("thermal", 0.8), ct,
           0.3, 0.6, comp("thermal collection", "thermal"))
    p.t("OV_manifold_t", R("Thermal collection: hot loop {thermal.hot_total!P} (plume and\nradiation on hardware), "
                           "warm loop {thermal.warm_total!P} (drivers, house)"), 91, 63.0, S_S, coll=lab)
    tag(p, "P06", 91, 59.5, cu)
    # equipment module and drivers
    K.cylinder_x("OV_equipment", X(119), X(136), Y(cy), 0, 3.0, gray, cs, comp("equipment module", "structure"))
    for i, dy in enumerate((-7.5, 7.5)):
        p.rect(f"OV_driver_{i}", 100, cy + dy - 1.0, 136, cy + dy + 1.0, K.cat_mat("fusion", 0.85), cf, 0.0, 1.6,
               comp("drivers", "fusion"))
    burn = (155.0, cy)
    for i, dy in enumerate((-7.5, -7.0, 7.0, 7.5)):
        p.seg(f"OV_beam_{i}", (136, cy + dy), burn, 0.16, K.cat_mat("fusion", 1.2), cf, 0.9, 1.0,
              comp("driver beams", "fusion"))
    p.t("OV_driver_t", R("Ignition drivers: {driver.beams:.0f} heavy-ion beams\n{fusion.pellet_rate:.0f} Hz × ") +
        f"{V('driver.energy_per_pulse_beam') / 1e6:.1f} MJ beam, " + R("wall-plug {calc.driver_efficiency!pct:0}"),
        100, 23.0, S_S, coll=lab)
    tag(p, "P02", 100, 19.5, cu)
    p.t("OV_equip_t", "Equipment module:\ntarget factory, power,\ncryoplant", 113, 52.5, S_S, coll=lab)
    # pellet injection
    p.arrow("OV_pellets", [(118, cy), (153.2, cy)], 0.35, K.cat_mat("propellant", 1.1), cp, 1.0, 1.2,
            comp("pellet injection", "propellant"), head=1.1, head_len=1.2)
    p.t("OV_pellet_t", R("Pellet injection: {fusion.pellet_mass:.2f} g D₂/³He\npellets at 400 m/s"), 113, 57.0, S_XS,
        coll=lab)
    p.seg("OV_pellet_lead", (128, 56.6), (128, cy + 0.6), 0.08, K.ui_mat("faint"), lab, 0.3, 0.35)
    # radiation shield (magenta-grey) and shadow
    shx = 155.0 - V("calc.standoff") * 0.25
    p.rect("OV_shield", shx - 1.6, cy - 6.6, shx, cy + 6.6, K.cat_mat("radiation", 0.55), cr, -2.0, 2.0,
           comp("shield", "radiation"))
    p.t("OV_shield_t", R("Shadow shield {shield.mass!t:3}\nLiH + W, {fusion.xray_standoff:.0f} m from burn"), 124, 64.5,
        S_XS, coll=lab)
    p.seg("OV_shield_lead", (133.5, 64.1), (shx - 0.8, cy + 6.6), 0.08, K.ui_mat("faint"), lab, 0.3, 0.35)
    tag(p, "P05", shx - 4.6, cy + 7.5, cu)
    # burn point
    bx, by = p.w(*burn)
    K.sphere("OV_burn", (bx, by, 0), 1.35, K.cat_mat("fusion", 1.3, emit=6.0), cf, comp("burn point", "fusion"))
    K.sphere("OV_burn_halo", (bx, by, 0), 2.4, K.cat_mat("fusion", 1.0, 0.25, emit=1.0), cf, comp("burn point", "fusion"))
    p.t("OV_burn_t", R("Reaction zone: open, no chamber\n{fusion.yield_per_pulse_tTNT:.1f} t TNT per pellet, "
                       "{fusion.power!P}"), 118.0, 13.0, S_S, mat=K.cat_mat("fusion", 1.15), coll=lab)
    tag(p, "P01", 114.0, 13.0, cu)
    p.seg("OV_burn_lead", (140.0, 15.6), (154.2, cy - 1.4), 0.08, K.ui_mat("faint"), lab, 0.3, 0.35)
    # Fiji nozzle loops at 0.25 BU per metre around the burn point
    s = 0.25
    loops = [(V(f"nozzle.loop{i}_x") - V("layout.x_burn"), V(f"nozzle.loop{i}_r")) for i in (1, 2, 3)]
    for i, (dx, r) in enumerate(loops):
        lx = burn[0] - dx * s
        K.torus_x(f"OV_loop_{i + 1}", X(lx), Y(cy), 0, r * s, 0.42, K.cat_mat("fiji"), cj, comp("nozzle", "fiji"))
        K.torus_x(f"OV_loop_{i + 1}_lattice", X(lx + 0.5), Y(cy), 0, r * s + 0.55, 0.22, K.cat_mat("fiji", 1.3, emit=1.5),
                  cj, comp("Fiji lattice band", "fiji"), arc=(55, 125))
        K.torus_x(f"OV_loop_{i + 1}_lattice_b", X(lx + 0.5), Y(cy), 0, r * s + 0.55, 0.22,
                  K.cat_mat("fiji", 1.3, emit=1.5), cj, comp("Fiji lattice band", "fiji"), arc=(235, 305))
    # struts chain loop3 -> loop2 -> loop1 -> shield
    pts = [(burn[0] - dx * s, cy - r * s) for dx, r in loops[::-1]] + [(shx, cy - 6.4)]
    p.poly("OV_struts_top", pts, 0.22, gray, cs, -0.5, -0.2, comp("nozzle struts", "structure"))
    pts = [(burn[0] - dx * s, cy + r * s) for dx, r in loops[::-1]] + [(shx, cy + 6.4)]
    p.poly("OV_struts_bot", pts, 0.22, gray, cs, -0.5, -0.2, comp("nozzle struts", "structure"))
    p.t("OV_nozzle_t", R("Fiji magnetic nozzle: 3 superconducting loops\nr {nozzle.loop1_r:.0f} / {nozzle.loop2_r:.0f} / "
                         "{nozzle.loop3_r:.0f} m, 4 trim sectors each; Fiji lattice\nband (violet glow) amplifies and "
                         "stabilises only"), 140, 73.6, S_XS, mat=K.cat_mat("fiji", 1.25), coll=lab, valign="BOTTOM")
    tag(p, "P04", 165.0, 9.6, cu)
    # directed exhaust plume (cyan), 20 deg half angle
    half = math.radians(V("prop.plume_half_angle_deg"))
    L = 46.0
    K.cylinder_x("OV_plume", X(burn[0]), X(burn[0] + L), Y(cy), 0, 0.01, K.cat_mat("exhaust", 1.0, 0.22, emit=0.6), ce,
                 comp("directed jet", "exhaust"), r2=L * math.tan(half), seg=48)
    jet_w = 6.0
    p.arrow("OV_jet_arrow", [(burn[0] + 3, cy), (burn[0] + 44, cy)], jet_w, K.cat_mat("exhaust", 1.05), ce, 1.6, 2.0,
            comp("directed jet", "exhaust"), head=9.0, head_len=4.0)
    p.t("OV_jet_t", R("DIRECTED JET {prop.jet_power!P}"), burn[0] + 5, cy - 2.1, S_S, mat=K.ui_mat("dark"), coll=lab,
        z=2.2)
    p.t("OV_jet_t2", R("{prop.eta_jet!pct} of fusion · v_e {prop.ve!kms} · {prop.plume_half_angle_deg:.0f}° cone"),
        176, 12.0, S_XS, mat=K.cat_mat("exhaust", 1.15), coll=lab)
    # undirected plume (dimmer, wider)
    for sgn in (-1, 1):
        p.arrow(f"OV_plume_space_{sgn}", [(burn[0] + 2, cy + sgn * 2.0), (burn[0] + 30, cy + sgn * 16.5)],
                V("ledger.plume_to_space") / V("prop.jet_power") * jet_w / 2, K.cat_mat("exhaust", 0.6), ce, 0.5, 0.8,
                comp("undirected plume", "exhaust"))
    p.t("OV_plume_space_t", R("undirected plume to space\n{ledger.plume_to_space!P} (no thrust)"), 189.0, 59.0, S_XS,
        coll=lab)
    # thrust arrow on the ship
    p.arrow("OV_thrust", [(30, 13.5), (6, 13.5)], 1.5, K.ui_mat("text"), cs, 0.4, 0.8, comp("thrust", "structure"),
            head=3.0, head_len=2.5)
    p.t("OV_thrust_t", R("THRUST {prop.thrust!MN} → a0 {prop.a0_g:.4f} g at {mass.departure!t}"), 6, 10.0, S_S,
        coll=lab)
    tag(p, "P03", 52.0, 9.9, cu)
    tag(p, "P10", 52.0, 12.6, cu)
    p.t("OV_tags_t", "power-to-mass · four-burn mission", 56.0, 10.6, S_XS, "faint", coll=lab)
    # neutral radiation: straight rays, some absorbed by shield and loops
    rays = [(150, 18), (145, 13.5), (162, 15), (172, 70), (147, 69), (166, 71), (199, 20), (199, 66)]
    for i, (qx, qy) in enumerate(rays):
        p.dash(f"OV_ray_{i}", burn, (qx, qy), 0.16, 0.9, K.cat_mat("radiation", 1.05), cr, 0.7, 0.8,
               comp("neutral radiation", "radiation"))
    for i, qy in enumerate((cy - 5.0, cy + 5.0)):
        p.dash(f"OV_ray_shield_{i}", burn, (shx + 0.1, qy), 0.16, 0.9, K.cat_mat("radiation", 1.05), cr, 0.7, 0.8,
               comp("neutral radiation", "radiation"))
        p.disc(f"OV_ray_hit_{i}", shx + 0.25, qy, 0.45, K.cat_mat("thermal", 1.2), ct, 0.8, 1.0)
    # charged products follow field lines into the jet
    for sgn in (-1, 1):
        pts = []
        for k in range(14):
            t = k / 13
            pts.append((burn[0] + 1.0 + t * 12.0, cy + sgn * (1.6 + 5.5 * math.sin(math.pi * t) * (1 - 0.6 * t))))
        p.poly(f"OV_charged_{sgn}", pts, 0.18, K.cat_mat("exhaust", 1.25), ce, 0.9, 1.0,
               comp("charged products", "exhaust"))
    p.t("OV_phys_t", "X-rays and neutrons (dashed magenta) fly straight: fields cannot steer them,\nonly mass in the "
        "path stops them. Charged products (cyan) follow the field into the jet.", 89, 70.0, S_XS, "dim", coll=lab,
        valign="BOTTOM")
    # reaction-mass note
    c_note = sub_ui("01", "notes")
    p.frame("OV_rm_box", 172.5, 63.2, 202.5, 73.4, 0.12, K.cat_mat("propellant", 0.9), c_note, 0.0, 0.2)
    para(p, "OV_rm_t", R("Reaction-mass injection: none separate. Unburned D/³He ({mass.unburned!t}, "
                         "{calc.unburned_share!pct:0} of propellant) is the reaction mass; H tamper ≈ 0."),
         173.3, 63.8, S_XS, 52, "text", coll=c_note)
    p.t("OV_stand_t", "BOW", 1.8, cy - 0.6, S_S, "faint", coll=lab)


# ===============================================================================================================
def sankey_band(p, name, x0, ya0, ya1, x1, yb0, yb1, mat, coll, props=None, z=0.0):
    pts = [(x0, ya0), (x1, yb0), (x1, yb1), (x0, ya1)]
    return p.prism(name, pts, mat, coll, z, z + 0.25, props)


def build_fusion():
    p = Panel("02", "P02A", "A · FUSION ENERGY AND POWER FLOW",
              "fuel → ignition → fusion products → directed exhaust → thrust (power in W; energy in J)", 3, 0,
              accent="fusion", headline=R("{calc.non_jet_power!P} not in jet"), head_cat="unresolved")
    cf, ce, cr, ct, cp = sub("02", "fusion"), sub("02", "exhaust"), sub("02", "radiation"), sub("02", "thermal"), sub("02", "propellant")
    lab = sub_ui("02", "labels A")
    Pf = V("fusion.power")
    k = 2.3e-12                     # BU per W (2.3 BU per TW)
    top = 15.0
    H = Pf * k
    # fuel and ignition (not to power scale)
    p.rrect("FE_fuel", 3, 30, 14, 41, 0.6, K.cat_mat("propellant"), cp, 0, 0.6, {"component": "fuel"})
    p.t("FE_fuel_t", R("FUEL\n{prop.mass_flow:.4f} kg/s\nD–³He"), 8.5, 31.0, S_S, mat=K.ui_mat("dark"), align="CENTER",
        coll=lab, z=0.9)
    p.arrow("FE_fuel_arrow", [(14, 35.5), (19, 35.5)], 0.5, K.cat_mat("propellant", 1.1), cp, 0, 0.3)
    p.rrect("FE_ign", 19, 28, 31, 43, 0.6, K.cat_mat("fusion", 0.8), cf, 0, 0.6, {"component": "ignition"})
    p.t("FE_ign_t", R("IGNITION\n{driver.beams:.0f} beams\n{fusion.pellet_rate:.0f} Hz\ngain {fusion.target_gain:,.0f}"),
        25, 29.2, S_S, mat=K.ui_mat("dark"), align="CENTER", coll=lab, z=0.9)
    p.arrow("FE_ign_arrow", [(31, 35.5), (36, 35.5)], 0.5, K.cat_mat("fusion", 1.1), cf, 0, 0.3)
    # fusion bar
    p.rect("FE_fusion_bar", 36, top, 41, top + H, K.cat_mat("fusion", 1.0, emit=0.5), cf, 0, 0.8,
           {"component": "fusion power", "value_keys": "fusion.power"})
    p.t("FE_fusion_t", R("FUSION {fusion.power!P}"), 38.5, top - 2.6, S_B, mat=K.cat_mat("fusion", 1.15),
        align="CENTER", coll=lab)
    L = M.ledger
    flows = [("jet", L["jet"], "exhaust", 1.0, "Directed jet", R("{ledger.jet!P} · {prop.eta_jet!pct}"),
              R("→ thrust {prop.thrust!MN}")),
             ("plume", L["plume_to_space"], "exhaust", 0.55, "Undirected plume → space",
              R("{ledger.plume_to_space!P}"), "no thrust"),
             ("radesc", L["radiation_to_space"], "radiation", 1.0, "X-rays/neutrons → space",
              R("{ledger.radiation_to_space!P}"), "escapes, unabsorbed"),
             ("heat", V("calc.heat_total"), "thermal", 1.0, "Heat → radiators", R("{calc.heat_total!P}"),
              R("hot {thermal.hot_total!P} + warm {thermal.warm_total!P}"))]
    ys = top
    dests = [15.0, 43.6, 49.0, 54.4]
    for (key, w, cat, shade, title, val, note), yd in zip(flows, dests):
        h = w * k
        hv = max(h, 0.22)
        mat = K.cat_mat(cat, shade, 0.85)
        sankey_band(p, f"FE_band_{key}", 41, ys, ys + h, 64, yd, yd + hv, mat,
                    sub("02", cat), {"value_keys": f"ledger.{key}", "width_scaled": h >= 0.22})
        p.rect(f"FE_dest_{key}", 64, yd, 66.5, yd + hv, K.cat_mat(cat, shade * 1.1 if shade < 1 else 1.1), sub("02", cat),
               0, 0.5)
        p.t(f"FE_dest_{key}_t", title, 67.5, yd - 0.1, S_S, coll=lab)
        p.t(f"FE_dest_{key}_v", val, 67.5, yd + 1.3, S_B, mat=K.cat_mat(cat, 1.15), coll=lab)
        p.t(f"FE_dest_{key}_n", note + ("" if h >= 0.22 else "  (band below width scale)"), 67.5, yd + 2.8, S_XS,
            "faint", coll=lab)
        ys += h
    # recirculating power loop (not to width scale)
    p.dash("FE_recirc_1", (38.5, top + H + 0.3), (38.5, 49.0), 0.3, 0.8, K.cat_mat("fusion", 1.1), cf)
    p.dash("FE_recirc_2", (38.5, 49.0), (25, 49.0), 0.3, 0.8, K.cat_mat("fusion", 1.1), cf)
    p.prism("FE_recirc_h", [(25.3, 47.9), (25.3, 50.1), (24.0, 49.0)], K.cat_mat("fusion", 1.1), cf, 0, 0.15)
    p.seg("FE_recirc_3", (25, 49.0), (25, 43.2), 0.3, K.cat_mat("fusion", 1.1), cf)
    p.t("FE_recirc_t", R("recovered electric {power.recovered!P} → drivers {driver.wall_plug_power!P}, "
                         "house {ledger.electric_house!P}\n(recirculates; its losses join the heat branch)"),
        3, 50.2, S_XS, coll=lab)
    # scale and conservation
    p.rect("FE_scale", 3, 57.4, 3 + 2.3, 57.8, K.ui_mat("text"), lab, 0, 0.2)
    p.t("FE_scale_t", "band height: 2.3 BU = 1 TW (linear); the GW branches are magnified in panel A2", 6.5, 57.0,
        S_XS, "dim", coll=lab)
    cv = sub("02", "verified", "conservation check (green)")
    p.rrect("FE_cons_bg", 3, 60.0, 97, 73.5, 0.6, K.cat_mat("verified", 0.22), cv, -0.2, 0.0)
    p.t("FE_cons_h", "ENERGY CONSERVATION CHECK  ✓", 4.5, 60.7, S_B, mat=K.cat_mat("verified", 1.1), coll=cv)
    eq = R("{ledger.jet!P} jet + {ledger.plume_to_space!P} plume + {ledger.radiation_to_space!P} radiation + "
           "{calc.heat_total!P} radiators = {calc.outflow_sum!P} = P_fusion (residual {calc.outflow_residual:.1e} W)")
    para(p, "FE_cons_t", eq, 4.5, 62.6, S_S, 108, "text", coll=cv)
    para(p, "FE_cons_t2", R("Not in the jet: {calc.non_jet_power!P}. Of it, {calc.space_escape!P} leaves the ship and "
                            "only {calc.heat_total!P} becomes onboard heat. The split comes from the FDP-1 model "
                            "(20° plume, 1.95 % hardware solid angle): ASSUMED, not measured. Integrated over "
                            "{mission.engine_years:.2f} y: E_fusion {calc.fusion_energy:.2e} J, E_jet "
                            "{calc.jet_energy:.2e} J."), 4.5, 66.4, S_XS, 128, "dim", coll=cv)
    glyph(p, "FE_cls", 93.5, 60.8, "ASSUMED", 1.0, lab)


def build_magnifier():
    p = Panel("02", "P02B", "A2 · THE GIGAWATT BRANCHES (×100 MAGNIFIER)",
              "radiator heat by source, recirculating power and radiation leaving the pellet", 4, 0, accent="thermal",
              headline=R("{calc.heat_total!P}"), head_cat="thermal")
    lab = sub_ui("02", "labels A2")
    ct, cr, cf = sub("02", "thermal"), sub("02", "radiation"), sub("02", "fusion")
    k = 0.85e-9                    # BU per W (0.85 BU per GW)
    y = 11.0
    p.t("MG_hot_h", R("HOT LOOP {rad.hot_T:.0f} K · {thermal.hot_total!P}"), 3, y, S_S, mat=K.cat_mat("thermal", 1.2),
        coll=lab)
    y += 1.8
    parts = [("plume on hardware", V("hot.plume_on_hardware"), "exhaust", 0.75),
             ("radiation on loops", V("hot.radiation_on_nozzle_loops"), "radiation", 1.0),
             ("radiation on shield", V("hot.radiation_on_shadow_shield"), "radiation", 0.8),
             ("radiation on struts", V("hot.radiation_on_nozzle_struts"), "radiation", 0.6),
             ("recovery loss", V("hot.recovery_conversion_loss"), "fusion", 0.9)]
    x = 3.0
    for i, (nm, w, cat, sh) in enumerate(parts):
        p.rect(f"MG_hot_{i}", x, y, x + w * k, y + 3.0, K.cat_mat(cat, sh), sub("02", cat), 0, 0.8,
               {"value_W": w})
        x += w * k
    p.frame("MG_hot_frame", 3, y, x, y + 3.0, 0.12, K.cat_mat("thermal", 1.2), ct, 0.8, 0.9)
    p.t("MG_hot_t1", R("plume striking hardware {hot.plume_on_hardware!P} ({calc.deposited_hardware!P} deposited in all)"),
        3, y + 3.6, S_XS, coll=lab)
    p.t("MG_hot_t2", R("radiation on loops {hot.radiation_on_nozzle_loops!P}, shield {hot.radiation_on_shadow_shield!P}, "
                       "struts {hot.radiation_on_nozzle_struts!P}; recovery loss {hot.recovery_conversion_loss!P}"),
        3, y + 4.9, S_XS, coll=lab)
    y += 8.2
    p.t("MG_warm_h", R("WARM LOOP {rad.warm_T:.0f} K · {thermal.warm_total!P}"), 3, y, S_S, mat=K.cat_mat("thermal", 0.9),
        coll=lab)
    y += 1.8
    parts = [("target factory and controls", V("warm.power_and_target_systems"), "fusion", 0.65),
             ("driver waste", V("warm.driver_waste"), "fusion", 0.95),
             ("cryoplant input", V("warm.cryoplant_input"), "propellant", 0.8)]
    x = 3.0
    for i, (nm, w, cat, sh) in enumerate(parts):
        p.rect(f"MG_warm_{i}", x, y, x + w * k, y + 3.0, K.cat_mat(cat, sh), sub("02", cat), 0, 0.8, {"value_W": w})
        x += w * k
    p.frame("MG_warm_frame", 3, y, x, y + 3.0, 0.12, K.cat_mat("thermal", 0.9), ct, 0.8, 0.9)
    p.t("MG_warm_t1", R("target factory and controls {warm.power_and_target_systems!P} · driver waste "
                        "{warm.driver_waste!P} · cryo {warm.cryoplant_input!P}"), x + 1.5, y + 0.2, S_XS, coll=lab)
    p.t("MG_warm_t2", "every watt of house power ends as 600 K heat", x + 1.5, y + 1.6, S_XS, "faint", coll=lab)
    p.rect("MG_scale", 3, y + 4.4, 3 + 0.85 * 10, y + 4.75, K.ui_mat("text"), lab, 0, 0.2)
    p.t("MG_scale_t", "10 GW (bar length 0.85 BU per GW, linear)", 3 + 9.5, y + 4.0, S_XS, "dim", coll=lab)
    y += 7.5
    # recirculating power chain
    p.t("MG_rc_h", "RECIRCULATING POWER (the drivers run on power taken from the burn)", 3, y, S_S, "dim", coll=lab)
    y += 2.2
    boxes = [("recovered\nfrom burn", R("{power.recovered!P}")), ("electric\nbus", R("{power.electric_load!P}")),
             ("drivers\nwall-plug", R("{driver.wall_plug_power!P}")), ("beam into\ntarget", R("{driver.beam_power!P}"))]
    for i, (nm, val) in enumerate(boxes):
        bx = 3 + i * 24
        p.rrect(f"MG_rc_{i}", bx, y, bx + 19, y + 7.5, 0.6, K.cat_mat("fusion", 0.35), cf, 0, 0.3)
        p.t(f"MG_rc_{i}_t", nm, bx + 1, y + 0.6, S_XS, coll=lab)
        p.t(f"MG_rc_{i}_v", val, bx + 1, y + 4.8, S_B, mat=K.cat_mat("fusion", 1.15), coll=lab)
        if i < 3:
            p.arrow(f"MG_rc_a{i}", [(bx + 19.3, y + 3.7), (bx + 23.7, y + 3.7)], 0.3, K.cat_mat("fusion", 1.1), cf, 0, 0.3)
    p.t("MG_rc_loss", R("losses → heat: recovery {ledger.recovery_loss!P} (hot) · drivers {ledger.driver_loss!P} "
                        "(warm, efficiency {calc.driver_efficiency!pct:0}) · house {ledger.electric_house!P} (warm)"),
        3, y + 8.4, S_XS, coll=lab)
    y += 11.5
    p.t("MG_rad_h", "RADIATION LEAVING THE PELLET", 3, y, S_S, "dim", coll=lab)
    y += 1.9
    esc = V("shield.xray_escape") + V("shield.neutron_escape")
    p.rect("MG_rad_space", 3, y, 3 + V("ledger.radiation_to_space") * k * 0.4, y + 2.2, K.cat_mat("radiation"), cr, 0, 0.6)
    x1 = 3 + V("ledger.radiation_to_space") * k * 0.4
    p.rect("MG_rad_hw", x1, y, x1 + max(V("ledger.radiation_on_hardware") * k * 0.4, 0.25), y + 2.2,
           K.cat_mat("thermal", 1.15), ct, 0, 0.6)
    p.t("MG_rad_t", R("X-rays {shield.xray_escape!P} + neutrons {shield.neutron_escape!P} = " + fmt_power(esc) +
                      " → space {ledger.radiation_to_space!P}, absorbed by hardware {ledger.radiation_on_hardware!P}"),
        3, y + 2.7, S_XS, coll=lab)
    p.t("MG_rad_s", "(bar at 0.34 BU per GW)", x1 + 1.5, y + 0.5, S_XS, "faint", coll=lab)
    y += 4.8
    cu = sub("02", "unresolved", "unresolved (yellow)")
    p.rrect("MG_flag_bg", 3, y, 97, y + 7.0, 0.5, K.cat_mat("unresolved", 0.18), cu, -0.2, 0.0)
    glyph(p, "MG_flag_g", 4, y + 0.7, "UNKNOWN", 1.0, cu)
    para(p, "MG_flag_t", R("Booking note: gain = yield / beam energy, so each pellet releases yield + beam. The FDP-1 "
                           "ledger books outputs as shares of gross fusion only, so the {driver.beam_power!P} beam "
                           "re-deposited in the target (0.033 % of fusion) is not booked as an output. Neutron "
                           "production share before self-absorption: TBD (not reported)."), 5.8, y + 0.6, S_XS, 124,
         "text", coll=cu)


# ===============================================================================================================
def node(p, name, px, py, w, h, title, value, cat, coll, cls="ASSUMED", keys=()):
    p.rrect(name, px, py, px + w, py + h, 0.7, K.cat_mat(cat, 0.32), coll, 0, 0.4, {"value_keys": ",".join(keys)})
    p.frame(f"{name}_f", px, py, px + w, py + h, 0.12, K.cat_mat(cat, 1.0), coll, 0.4, 0.5)
    p.t(f"{name}_t", title, px + 1.0, py + 0.7, S_XS, "dim", coll=coll)
    p.t(f"{name}_v", value, px + 1.0, py + 2.2, S_B, mat=K.cat_mat(cat, 1.15), coll=coll)
    glyph(p, f"{name}_g", px + w - 1.6, py + 0.7, cls, 0.8, coll)


def build_rocket():
    p = Panel("03", "P03", "B1 · THRUST, EXHAUST VELOCITY AND THE ROCKET EQUATION",
              "how mass, thrust, exhaust velocity, power, propellant and acceleration constrain each other", 0, 1,
              accent="propellant", headline=R("R = {calc.mass_ratio:.2f}"), head_cat="propellant")
    c = sub("03", "propellant")
    ce = sub("03", "exhaust")
    cf = sub("03", "fusion")
    cs = sub("03", "structure")
    lab = sub_ui("03", "labels")
    w, h = 21, 5.2
    N = {"m": (3, 12), "a": (3, 22), "F": (39, 12), "mdot": (75, 12), "ve": (75, 22), "Pj": (39, 32), "Pf": (75, 32),
         "dv": (3, 32)}
    node(p, "RK_m", *N["m"], w, h, "departure mass m0", R("{mass.departure!t}"), "structure", cs)
    node(p, "RK_a", *N["a"], w, h, "acceleration a0", R("{prop.a0_g:.4f} g"), "structure", cs)
    node(p, "RK_F", *N["F"], w, h, "thrust F", R("{prop.thrust!MN}"), "exhaust", ce, "CALC")
    node(p, "RK_mdot", *N["mdot"], w, h, "mass flow ṁ", R("{prop.mass_flow:.4f} kg/s"), "propellant", c)
    node(p, "RK_ve", *N["ve"], w, h, "exhaust velocity v_e", R("{prop.ve!kms}"), "exhaust", ce)
    node(p, "RK_Pj", *N["Pj"], w, h, "jet power P_jet", R("{calc.jet_power!P}"), "exhaust", ce, "CALC")
    node(p, "RK_Pf", *N["Pf"], w, h, "fusion power P_fus", R("{fusion.power!P}"), "fusion", cf)
    node(p, "RK_dv", *N["dv"], w, h, "Δv, four burns", R("{calc.dv_total_c:.3f} c"), "exhaust", ce, "CALC")
    arrow_m = K.ui_mat("dim")

    def edge(name, a, b, label, lx, ly, align="LEFT"):
        p.arrow(name, [a, b], 0.22, arrow_m, lab, 0, 0.2, head=1.0, head_len=1.0)
        p.t(f"{name}_t", label, lx, ly, S_S, coll=lab, align=align)

    edge("RK_e1", (24.3, 14.6), (38.6, 14.6), "F = m × a", 25.0, 12.0)
    p.seg("RK_e1b", (14, 22), (14, 17.6), 0.22, arrow_m, lab)
    p.seg("RK_e1c", (14, 17.6), (24.0, 15.3), 0.22, arrow_m, lab)
    edge("RK_e2", (74.6, 14.6), (60.4, 14.6), "F = ṁ × v_e", 61.0, 12.0)
    p.seg("RK_e2b", (85.5, 22.0), (85.5, 17.4), 0.22, arrow_m, lab)
    edge("RK_e3", (49.5, 17.4), (49.5, 31.6), "P_jet = ½ × F × v_e", 50.5, 23.0)
    p.seg("RK_e3b", (75, 24.6), (54, 31.6), 0.22, arrow_m, lab)
    edge("RK_e4", (74.6, 34.6), (60.4, 34.6), R("P_jet = η P_fus, η {prop.eta_jet:.3f}"), 61.0, 38.2)
    edge("RK_e5", (14, 27.4), (14, 31.6), "", 0, 0)
    p.t("RK_e5_t", "Δv = v_e × ln(m0 / mf)", 15.5, 28.4, S_S, coll=lab)
    # rocket equation chart
    gx0, gy0, gw, gh = 10.0, 45.0, 52.0, 24.0    # chart box: x = dv/ve 0..1.2, y = R 1..3.4
    xr, yr = (0.0, 1.2), (1.0, 3.4)
    X = lambda u: gx0 + (u - xr[0]) / (xr[1] - xr[0]) * gw
    Y = lambda r: gy0 + gh - (r - yr[0]) / (yr[1] - yr[0]) * gh
    grid = K.ui_mat("grid")
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        p.seg(f"RK_gx_{u}", (X(u), gy0), (X(u), gy0 + gh), 0.08, grid, lab, -0.2, -0.1)
        p.t(f"RK_gx_{u}_t", f"{u:.2f}", X(u), gy0 + gh + 0.6, S_XS, "faint", align="CENTER", coll=lab)
    for r in (1.0, 1.5, 2.0, 2.5, 3.0):
        p.seg(f"RK_gy_{r}", (gx0, Y(r)), (gx0 + gw, Y(r)), 0.08, grid, lab, -0.2, -0.1)
        p.t(f"RK_gy_{r}_t", f"{r:.1f}", gx0 - 1.0, Y(r) - 0.45, S_XS, "faint", align="RIGHT", coll=lab)
    p.t("RK_ax_x", "Δv / v_e", gx0 + gw, gy0 + gh + 1.9, S_XS, "dim", align="RIGHT", coll=lab)
    p.t("RK_ax_y", "mass ratio m0/mf", gx0, gy0 - 2.0, S_XS, "dim", coll=lab)
    curve = [(X(u / 40 * 1.2), Y(math.exp(u / 40 * 1.2))) for u in range(41)]
    p.poly("RK_curve", curve, 0.3, K.cat_mat("propellant", 1.1), c, 0, 0.2)
    ve = V("prop.ve")
    u = 0.0
    for i in range(1, 5):
        du = V(f"calc.burn{i}.dv") / ve
        u1 = u + du
        p.disc(f"RK_pt_{i}", X(u1), Y(math.exp(u1)), 0.7, K.cat_mat("exhaust", 1.1), ce, 0.2, 0.5)
        p.t(f"RK_pt_{i}_t", f"burn {i}", X(u1) - 1.2, Y(math.exp(u1)) - 2.2, S_XS, coll=lab, align="RIGHT")
        u = u1
    p.dash("RK_pt_drop", (X(u), Y(math.exp(u))), (X(u), gy0 + gh), 0.12, 0.6, K.cat_mat("exhaust"), ce)
    tx = 66.0
    para(p, "RK_note1", R("Four burns of {calc.dv_burn_required!kms} = {calc.dv_total_c:.3f} c = "
                          "{calc.burn_fraction_of_ve:.3f} v_e. The rocket equation then fixes R = {calc.mass_ratio:.3f}: "
                          "{calc.propellant_share!pct} of departure mass is propellant."), tx, 44.5, S_XS, 44, "text",
         coll=lab)
    para(p, "RK_note2", "Acceleration does not enter the rocket equation: v_e alone sets the propellant. "
         "Acceleration enters through power:", tx, 52.5, S_XS, 44, "dim", coll=lab)
    p.t("RK_eq", "a = 2 η P_fus / (m v_e)", tx, 57.3, S_B, mat=K.cat_mat("unresolved"), coll=lab)
    para(p, "RK_note3", "At fixed m and v_e, a rises only in proportion to fusion power. Lowering v_e buys thrust per "
         "watt but costs propellant (R = e^(Δv/v_e)).", tx, 59.8, S_XS, 44, "dim", coll=lab)
    tag(p, "P03", tx, 68.5)
    tag(p, "P08", tx + 4, 68.5)
    tag(p, "P10", tx + 8, 68.5)


def build_mass():
    p = Panel("04", "P04A", "B2 · DEPARTURE MASS BUDGET",
              "segmented to scale · every tonne of dry mass costs more at departure", 1, 1, accent="structure",
              headline=R("{mass.departure!t}"), head_cat="structure")
    cm = {cat: sub("04", cat) for cat in ("propellant", "thermal", "fusion", "fiji", "radiation", "structure")}
    lab = sub_ui("04", "labels B2")
    items = M.mass_items
    m0 = V("mass.departure")
    spec = [("propellant (four burns)", "propellant", 1.0, "propellant"),
            ("propellant reserve and allowances", "propellant", 0.62, "reserve"),
            ("tankage (required volume)", "propellant", 0.45, "tankage"),
            ("idle hydrogen vessels", "propellant", 0.3, "idle H₂ vessels"),
            ("warm radiators", "thermal", 0.8, "warm radiators"),
            ("hot radiators", "thermal", 1.15, "hot radiators"),
            ("low loop radiator", "thermal", 0.5, "low loop"),
            ("drivers (heavy-ion linacs, storage)", "fusion", 1.0, "drivers"),
            ("target factory, injectors, cryo-targets, misc", "fusion", 0.65, "target factory etc."),
            ("nozzle loops (virial structure)", "fiji", 1.0, "nozzle loops"),
            ("loop armour", "fiji", 0.6, "loop armour"),
            ("shadow shield", "radiation", 0.75, "shadow shield"),
            ("FDP-1 structure", "structure", 0.7, "FDP-1 structure"),
            ("payload (non-propulsion ship)", "structure", 1.0, "payload (canon)")]
    known = {s[0] for s in spec} | {"warm-wing view-factor area"}
    assert set(items) <= known, set(items) - known
    x0, wbar = 3.0, 94.0
    y0 = 13.5

    def bar(prefix, y, h, total, subset, labels_below):
        x = x0
        segs = []
        for key, cat, sh, short in subset:
            m = items.get(key, 0.0)
            if m <= 0:
                continue
            wseg = m / total * wbar
            p.rect(f"{prefix}_{short}", x, y, x + wseg, y + h, K.cat_mat(cat, sh), cm[cat], 0, 1.4,
                   {"value_kg": m, "item": key, "classification": "ASSUMED"})
            segs.append((x, wseg, short, m, cat, sh))
            x += wseg
        p.frame(f"{prefix}_frame", x0, y, x0 + wbar, y + h, 0.1, K.ui_mat("panel_edge"), lab, 1.4, 1.5)
        return segs

    segs = bar("MB", y0, 5.0, m0, spec, True)
    big = [s for s in segs if s[1] > 9]
    for xs, wseg, short, m, cat, sh in big:
        p.t(f"MB_in_{short}", f"{short}\n{sig(m / 1e3, 4)} t · {m / m0 * 100:.1f} %", xs + 0.8, y0 + 0.6, S_XS,
            mat=K.ui_mat("text"), coll=lab, z=1.8)
    small = [s for s in segs if s[1] <= 9]
    for i, (xs, wseg, short, m, cat, sh) in enumerate(small):
        lx = 30.0 + (i % 3) * 23.0
        ly = y0 + 7.0 + (i // 3) * 2.2
        p.seg(f"MB_lead_{short}", (xs + wseg / 2, y0 + 5.0), (xs + wseg / 2, y0 + 6.0), 0.08, K.ui_mat("faint"), lab,
              0.2, 0.3)
        p.rect(f"MB_key_{short}", lx, ly + 0.15, lx + 1.1, ly + 0.95, K.cat_mat(cat, sh), cm[cat], 0, 0.3)
        p.t(f"MB_lab_{short}", f"{short} {sig(m / 1e3, 3)} t", lx + 1.5, ly, S_XS, coll=lab)
    p.t("MB_ticks", "small segments, left to right:", 3, y0 + 7.0, S_XS, "faint", coll=lab)
    # dry mass expanded
    y1 = 31.5
    dry = V("mass.dry")
    p.t("MB_dry_h", R("DRY MASS {mass.dry!t} (expanded ×{calc.mass_ratio:.2f}) + reserve {mass.reserve!t:3} = end mass "
                      "{mass.end!t}"), 3, y1 - 2.2, S_S, "dim", coll=lab)
    dspec = [s for s in spec if s[0] not in ("propellant (four burns)", "propellant reserve and allowances")]
    segs = bar("MD", y1, 3.6, dry, dspec, False)
    for i, (xs, wseg, short, m, cat, sh) in enumerate(segs):
        if wseg > 6.5:
            p.t(f"MD_in_{short}", f"{sig(m / 1e3, 3)} t", xs + 0.5, y1 + 1.1, S_XS, mat=K.ui_mat("text"), coll=lab, z=1.8)
    # 3D volume comparison (cube volume proportional to mass)
    y2 = 39.0
    p.t("MB_cube_h", "VOLUME COMPARISON (cube volume ∝ mass)", 3, y2, S_XS, "dim", coll=lab)
    cubes = [("propellant", V("mass.propellant"), "propellant", 1.0), ("dry mass", dry, "structure", 0.8),
             ("power-scaled hardware", V("calc.power_scaled_mass"), "fusion", 1.0),
             ("payload", items["payload (non-propulsion ship)"], "structure", 1.0)]
    cx = 4.0
    for i, (nm, m, cat, sh) in enumerate(cubes):
        s = (m / 1e3) ** (1 / 3) * 0.42
        x, yb = p.w(cx, y2 + 2 + 10.5)
        K.prism(f"MB_cube_{i}", [(x, yb), (x + s, yb), (x + s, yb + s), (x, yb + s)], 0, s, K.cat_mat(cat, sh), cm[cat],
                {"value_kg": m})
        p.t(f"MB_cube_{i}_t", f"{nm}\n{sig(m / 1e3, 3)} t", cx, y2 + 13.3, S_XS, coll=lab)
        cx += max(s, 9.0) + 4.0
    # notes
    y3 = 57.0
    para(p, "MB_n1", R("Power-scaled hardware (drivers, nozzle, target factory, radiators) {calc.power_scaled_mass!t} "
                       "= {mass.alpha_jet:.2e} kg/W × P_jet; it grows with power at any acceleration. Fixed FDP-1 "
                       "masses: {mass.fixed_added!t}."), 3, y3, S_XS, 120, "text", coll=lab)
    para(p, "MB_n2", R("Leverage: +1 t of dry mass → +{mass.leverage:.1f} t at departure."), 3, y3 + 3.8, S_XS, 120,
         mat=K.cat_mat("unresolved"), coll=lab)
    cu = sub("04", "unresolved", "unresolved (yellow)")
    glyph(p, "MB_flag_g", 3, y3 + 6.6, "UNKNOWN", 0.9, cu)
    para(p, "MB_n3", R("Brief check: the 'remaining dry mass 7,643 t' is the end mass; it holds the {mass.reserve!t:3} "
                       "reserve. The dry mass is {mass.dry!t}."), 4.6, y3 + 6.4, S_XS, 116, "dim", coll=cu)
    para(p, "MB_n4", "Subsystem masses come from the FDP-1 record (ASSUMED); none are invented here.", 3, y3 + 10.4,
         S_XS, 120, "faint", coll=lab)
    tag(p, "P03", 88.0, y2 + 0.2)
    tag(p, "P08", 88.0, y2 + 2.4)


def build_gap():
    p = Panel("04", "P04B", "C · THE 1 g PERFORMANCE GAP",
              "fixed mass, fixed exhaust velocity, fixed jet share: an engineering comparison, not an optimised design",
              2, 1, accent="unresolved", headline=R("×{calc.1g.factor:.0f} power"), head_cat="unresolved")
    cf = sub("04", "fusion")
    ct = sub("04", "thermal")
    cu = sub("04", "unresolved", "unresolved (yellow)")
    lab = sub_ui("04", "labels C")
    rows = M.accel_rows
    gx0, gy0, gw, gh = 11.0, 12.0, 84.0, 30.0
    d0, d1 = 1.0, 4.0                       # log10(TW)
    Y = lambda P: gy0 + gh - (math.log10(P / 1e12) - d0) / (d1 - d0) * gh
    grid = K.ui_mat("grid")
    for d in range(1, 5):
        yy = gy0 + gh - (d - d0) / (d1 - d0) * gh
        p.seg(f"GP_g{d}", (gx0, yy), (gx0 + gw, yy), 0.08, grid, lab, -0.2, -0.1)
        p.t(f"GP_g{d}_t", f"{10 ** d:,} TW", gx0 - 0.8, yy - 0.45, S_XS, "faint", align="RIGHT", coll=lab)
    p.t("GP_ax", "fusion power (log scale)", gx0 - 8.0, gy0 - 2.6, S_XS, "dim", coll=lab)
    bw, step = 6.2, 12.0
    for i, r in enumerate(rows):
        cx = gx0 + 4 + i * step
        top = Y(r["fusion_W"])
        base = gy0 + gh
        first = i == 0
        mat = K.cat_mat("fusion", 1.0, emit=0.4) if first else K.cat_mat("fusion", 0.55, 0.8)
        p.rect(f"GP_bar_{i}", cx, top, cx + bw, base, mat, cf, 0, 1.2 if first else 0.8,
               {"a_g": r["a_g"], "fusion_W": r["fusion_W"], "classification": "ASSUMED" if first else "CALC"})
        if not first:
            p.frame(f"GP_bar_{i}_f", cx, top, cx + bw, base, 0.12, K.cat_mat("unresolved"), cu, 0.8, 0.9)
        p.t(f"GP_bar_{i}_v", P(r["fusion_W"]), cx + bw / 2, top - 2.7, S_XS, mat=K.cat_mat("fusion", 1.15),
            align="CENTER", coll=lab)
        p.t(f"GP_bar_{i}_x", f"×{r['factor']:,.0f}" if not first else "FDP-1", cx + bw / 2, top - 1.4, S_XS,
            align="CENTER", coll=lab)
        p.t(f"GP_bar_{i}_a", f"{r['a_g']:.4f} g" if first else f"{r['a_g']:.2f} g", cx + bw / 2, base + 0.6, S_S,
            align="CENTER", coll=lab)
        p.t(f"GP_bar_{i}_F", sig(r["thrust_N"] / 1e6, 3) + " MN", cx + bw / 2, base + 2.1, S_XS, "dim", align="CENTER",
            coll=lab)
        ratio = r["mass_over_ship"]
        p.t(f"GP_bar_{i}_m", f"{ratio:.2f}" if ratio < 1 else f"{ratio:.1f}", cx + bw / 2, base + 3.5, S_XS,
            mat=K.cat_mat("thermal", 1.2) if ratio >= 1 else K.cat_mat("verified"), align="CENTER", coll=lab)
    base = gy0 + gh
    p.t("GP_rowF", "thrust", gx0 - 0.8, base + 2.1, S_XS, "faint", align="RIGHT", coll=lab)
    p.t("GP_rowm", "hw/ship", gx0 - 0.8, base + 3.5, S_XS, "faint", align="RIGHT", coll=lab)
    p.t("GP_rowa", "target", gx0 - 0.8, base + 0.6, S_XS, "faint", align="RIGHT", coll=lab)
    # ceiling line between bars 0 and 1
    xc = gx0 + 4 + bw + (step - bw) / 2
    p.dash("GP_ceiling", (xc, gy0 - 1.0), (xc, base), 0.22, 0.8, K.cat_mat("thermal", 1.2), ct)
    p.t("GP_ceiling_t", R("FDP-1 ceiling\nat any size\n{goal1g.max_a0_any_size_g:.4f} g"), xc + 0.7, gy0 - 0.8, S_XS,
        mat=K.cat_mat("thermal", 1.2), coll=lab)
    p.t("GP_15", "1.5 g = operational ceiling (canon)", gx0 + 4 + 6 * step + bw, base - 6.5, S_XS, "faint",
        align="RIGHT", coll=lab)
    # comparison table
    r1 = next(r for r in rows if abs(r["a_g"] - 1.0) < 1e-9)
    ty = 50.5
    cols = (3.0, 40.0, 60.0, 80.0)
    p.t("GT_h0", "quantity", cols[0], ty, S_XS, "dim", coll=lab)
    p.t("GT_h1", "FDP-1", cols[1], ty, S_XS, "dim", coll=lab)
    p.t("GT_h2", "1 g requirement", cols[2], ty, S_XS, "dim", coll=lab)
    p.t("GT_h3", "factor", cols[3], ty, S_XS, "dim", coll=lab)
    p.rect("GT_rule", 3, ty + 1.3, 97, ty + 1.4, K.ui_mat("grid"), lab, 0, 0.1)
    f = V("calc.1g.factor")
    table = [("initial acceleration", R("{prop.a0_g:.4f} g"), "1.0 g", f"×{f:.0f}"),
             ("initial thrust", R("{prop.thrust!MN}"), R("{calc.1g.thrust!MN}"), f"×{f:.0f}"),
             ("fusion power", R("{fusion.power!P}"), R("{calc.1g.fusion_power!P}"), f"×{f:.0f}"),
             ("jet power", R("{prop.jet_power!P}"), R("{calc.1g.jet_power!P}"), f"×{f:.0f}"),
             ("heat to radiators (same fractions)", R("{calc.heat_total!P}"), R("{calc.1g.heat!P}"), f"×{f:.0f}"),
             ("warm radiator area at 600 K", R("{rad.warm_area!km2}"), R("{calc.1g.warm_area!km2:0}"), f"×{f:.0f}"),
             ("power-scaled hardware / ship", f"{V('calc.power_scaled_mass') / V('mass.departure'):.2f}",
              R("{calc.1g.scaled_mass_over_ship:.1f}"), f"×{f:.0f}"),
             ("propellant per 0.016 c burn", "unchanged", "unchanged", "×1 (rocket eq.)"),
             ("time per 0.016 c burn", R("{burn1.days:.0f} d (burn 1)"), R("{calc.1g.burn_days:.2f} d"),
              f"÷{V('burn1.days') / V('calc.1g.burn_days'):.0f}")]
    for i, row in enumerate(table):
        yy = ty + 2.0 + i * 1.75
        for j, cell in enumerate(row):
            ui = "text" if j else "dim"
            mat = K.cat_mat("unresolved") if j == 2 else None
            p.t(f"GT_{i}_{j}", cell, cols[j], yy, S_XS, ui, mat=mat, coll=lab)
    glyph(p, "GT_g", 92.5, ty, "CALC", 0.8, lab)
    para(p, "GT_note", "Reduced-mass and other future designs remain open scenarios; this table only scales today's "
         "FDP-1. 'hw/ship' = power-scaled hardware ÷ departure mass (red ≥ 1: the engine alone outweighs the ship).",
         3, ty + 18.0, S_XS, 125, "faint", coll=lab)
    tag(p, "P03", 88.5, 9.2, cu)


# ===============================================================================================================
def logbar(p, name, px, py, w_W, x0, xper, h, mat, coll, lo=1e8):
    L = max(math.log10(max(w_W, lo)) - math.log10(lo), 0.05) * xper
    p.rect(name, x0, py, x0 + L, py + h, mat, coll, 0, 0.8, {"value_W": w_W})
    return x0 + L


def build_split():
    p = Panel("05", "P05A", "D1 · WHERE THE NON-JET POWER GOES",
              "five destinations of fusion power · four separate engineering functions", 3, 1, accent="thermal",
              headline=R("{calc.non_jet_power!P}"), head_cat="thermal")
    lab = sub_ui("05", "labels D1")
    L = M.ledger
    x0, xper = 37.0, 10.5                 # log axis: 0.1 GW at x0, 10.5 BU per decade
    lo = 1e8
    y = 12.0
    for d in range(8, 14):
        xx = x0 + (d - 8) * xper
        p.seg(f"SP_g{d}", (xx, y), (xx, y + 33.5), 0.07, K.ui_mat("grid"), lab, -0.2, -0.1)
        p.t(f"SP_g{d}_t", fmt_power(10 ** d, 0), xx, y + 34.0, S_XS, "faint", align="CENTER", coll=lab)
    p.t("SP_axis", "bar length: log10(power) from 0.1 GW", x0, y - 1.6, S_XS, "faint", coll=lab)
    rows = [("1", "Directed exhaust", L["jet"], "exhaust", 1.0, "useful: thrust", "ASSUMED"),
            ("2", "Radiation escaping to space", L["radiation_to_space"], "radiation", 1.0, "X-rays and neutrons that miss the ship",
             "ASSUMED"),
            ("3", "Radiation deposited in hardware", V("calc.deposited_hardware") - L["plume_to_hardware"], "radiation",
             0.7, "loops, shield, struts, conductor", "ASSUMED"),
            ("3b", "Plume striking hardware", L["plume_to_hardware"], "exhaust", 0.6, "charged plume on loops and struts",
             "ASSUMED"),
            ("4", "Heat removed by cooling", V("calc.heat_total"), "thermal", 1.0, "hot + warm loops → radiators", "ASSUMED"),
            ("5a", "Other: undirected plume to space", L["plume_to_space"], "exhaust", 0.4, "escapes, gives no thrust",
             "ASSUMED"),
            ("5b", "Other: beam re-deposited in target", V("driver.beam_power"), "fusion", 0.8, "not booked by the ledger",
             "UNKNOWN"),
            ("5c", "Other: neutron production share", None, "unresolved", 1.0, "TBD (record gives escape only)",
             "UNKNOWN")]
    for i, (rid, nm, w, cat, sh, note, cls) in enumerate(rows):
        yy = y + 0.5 + i * 4.1
        glyph(p, f"SP_r{i}_g", 3, yy + 0.2, cls, 0.8, lab)
        p.t(f"SP_r{i}_n", f"{rid}  {nm}", 4.6, yy, S_S, coll=lab)
        p.t(f"SP_r{i}_d", note, 4.6, yy + 1.4, S_XS, "faint", coll=lab)
        coll = sub("05", cat)
        if w is None:
            p.frame(f"SP_r{i}_bar", x0, yy + 0.1, x0 + 12, yy + 2.3, 0.12, K.cat_mat("unresolved"), coll, 0, 0.3,
                    dashed=0.8)
            p.t(f"SP_r{i}_v", "TBD", x0 + 13.2, yy + 0.4, S_S, mat=K.cat_mat("unresolved"), coll=lab)
        else:
            xe = logbar(p, f"SP_r{i}_bar", 0, yy + 0.1, w, x0, xper, 2.2, K.cat_mat(cat, sh), coll, lo)
            p.t(f"SP_r{i}_v", fmt_power(w), xe + 1.0, yy + 0.4, S_S, mat=K.cat_mat(cat, 1.15) if cat != "fusion"
                else K.cat_mat("fusion", 1.1), coll=lab)
    # four functions
    fy = 50.5
    p.t("SP_fn_h", "FOUR DIFFERENT ENGINEERING FUNCTIONS (each its own problem)", 3, fy, S_S, "dim", coll=lab)
    fns = [("REDUCE GENERATION", "fusion", ["house load {ledger.electric_house!P}", "driver loss {ledger.driver_loss!P}",
                                            "plume on hardware {ledger.plume_to_hardware!P}",
                                            "halve house load → departure −{calc.sens_house_saving!pct:0}"], ["P02", "P04"]),
           ("PREVENT ABSORPTION", "radiation", ["hardware solid angle {geom.solid_angle_total!pct:2}",
                                                "= ×{calc.solid_angle_ratio:.1f} the study's 0.20 %",
                                                "shield {shield.mass!t:3}; hardware", "decades {shield.hardware_decades:.0f} (placeholder)"],
            ["P05"]),
           ("TRANSPORT HEAT", "thermal", ["hot {thermal.hot_total!P} at {rad.hot_T:.0f} K", "warm {thermal.warm_total!P} at {rad.warm_T:.0f} K",
                                          "over wings {rad.wing_span:,.0f} m long", "booked {calc.transport_mass!t:2}; design TBD"],
            ["P06"]),
           ("RADIATE TO SPACE", "thermal", ["warm {rad.warm_area!km2}, hot {rad.hot_area!km2:3}", "{calc.radiator_mass!t:4}",
                                            "600 → 800 K: departure −{calc.sens_800K_saving!pct:0}", "P = 2 ε σ A T⁴, ε {rad.emissivity}"],
            ["P07"])]
    for i, (h, cat, lines, req) in enumerate(fns):
        bx = 3 + i * 23.6
        c = sub("05", cat)
        p.rrect(f"SP_fn{i}", bx, fy + 2.0, bx + 22.4, fy + 21.5, 0.6, K.cat_mat(cat, 0.22), c, -0.2, 0.0)
        p.rect(f"SP_fn{i}_bar", bx, fy + 2.0, bx + 22.4, fy + 2.5, K.cat_mat(cat), c, 0.0, 0.1)
        p.t(f"SP_fn{i}_h", h, bx + 1.0, fy + 3.2, S_S, mat=K.cat_mat(cat, 1.15), coll=lab)
        p.t(f"SP_fn{i}_t", "\n".join(R(s) for s in lines), bx + 1.0, fy + 5.3, S_XS, coll=lab, )
        for j, rid in enumerate(req):
            tag(p, rid, bx + 1.0 + j * 4.0, fy + 18.6, s=0.85)


def build_geometry():
    p = Panel("05", "P05B", "D2 · RADIATION GEOMETRY AND SHIELDING",
              "side view, 0.55 BU per metre · straight-line radiation · shadow cones", 4, 1, accent="radiation",
              headline=R("{geom.solid_angle_total!pct:2}"), head_cat="radiation")
    lab = sub_ui("05", "labels D2")
    cr, cs, cj, cf, ct = sub("05", "radiation"), sub("05", "structure"), sub("05", "fiji"), sub("05", "fusion"), sub("05", "thermal")
    s = 0.55
    bx, by = 86.0, 32.0
    d = V("calc.standoff")
    shx = bx - d * s
    # shadow cones (forward of the shield)
    for nm, ang, sh in (("hw", V("shield.hw_half_angle_deg"), 0.35), ("crew", V("shield.crew_half_angle_deg"), 0.6)):
        t = math.tan(math.radians(ang))
        xL = 3.0
        r_sh = d * t * s
        r_L = (bx - xL) * t
        p.prism(f"GE_cone_{nm}", [(shx, by - r_sh), (xL, by - r_L), (xL, by + r_L), (shx, by + r_sh)],
                K.cat_mat("structure", sh, 0.55), cs, -0.3, -0.25 + (0.02 if nm == "crew" else 0))
    p.t("GE_cone_crew_t", R("crew shadow cone {shield.crew_half_angle_deg:.2f}°"), 4, by - 1.0, S_XS, coll=lab)
    p.t("GE_cone_hw_t", R("hardware cone {shield.hw_half_angle_deg:.2f}° (set by driver galleries)"), 4, by - 9.3,
        S_XS, "dim", coll=lab)
    # shield
    rsh = 8.48 * s
    p.rect("GE_shield", shx - 3.6 * s, by - rsh, shx, by + rsh, K.cat_mat("radiation", 0.55), cr, -0.2, 0.6,
           {"component": "shield"})
    p.t("GE_shield_t", R("shield {shield.mass!t:3}"), shx - 3.0, by + rsh + 0.6, S_XS, coll=lab, align="CENTER")
    # burn point
    x, y = p.w(bx, by)
    K.sphere("GE_burn", (x, y, 0), 1.0, K.cat_mat("fusion", 1.3, emit=5.0), cf)
    p.t("GE_burn_t", "burn", bx + 1.4, by + 1.0, S_XS, mat=K.cat_mat("fusion", 1.15), coll=lab)
    # loop 1 (fits), loops 2/3 as clipped marks
    lx1 = bx - (V("nozzle.loop1_x") - V("layout.x_burn")) * s
    r1 = V("nozzle.loop1_r") * s
    p.disc("GE_loop1_top", lx1, by - r1, 0.6, K.cat_mat("fiji"), cj, 0, 0.6)
    p.t("GE_loop1_t", R("loop 1, r {nozzle.loop1_r:.0f} m"), lx1 + 1.0, by - r1 - 0.5, S_XS, mat=K.cat_mat("fiji", 1.2),
        coll=lab)
    p.t("GE_loops_t", R("loops 2, 3 (r {nozzle.loop2_r:.0f}, {nozzle.loop3_r:.0f} m)\nlie off this view"), 72.0,
        44.0, S_XS, mat=K.cat_mat("fiji", 1.2), coll=lab)
    # straight rays
    for i, (ax, ay) in enumerate(((shx + 0.1, by - 3.0), (shx + 0.1, by + 4.0), (lx1, by - r1), (3.0, by - 19.0),
                                  (3.0, by + 15.5), (60.0, 12.0), (52.0, 47.0))):
        p.dash(f"GE_ray_{i}", (bx, by), (ax, ay), 0.18, 0.9, K.cat_mat("radiation", 1.05), cr, 0.3, 0.4)
    for i, (ax, ay) in enumerate(((shx + 0.25, by - 3.0), (shx + 0.25, by + 4.0), (lx1, by - r1))):
        p.disc(f"GE_hit_{i}", ax, ay, 0.5, K.cat_mat("thermal", 1.2), ct, 0.4, 0.6)
    p.t("GE_stand_t", R("{fusion.xray_standoff:.1f} m stand-off"), (shx + bx) / 2, by + 2.0, S_XS, "dim", align="CENTER",
        coll=lab)
    p.seg("GE_stand", (shx, by + 1.6), (bx - 1.2, by + 1.6), 0.08, K.ui_mat("dim"), lab)
    # text block
    ty = 50.5
    kv(p, "GE_kv1", 3, ty, "intercepted by hardware:", R("{geom.solid_angle_total!pct:2} of 4π (study {geom.solid_angle_study!pct:1})"),
       "ASSUMED", vcat="radiation", coll=lab)
    kv(p, "GE_kv2", 3, ty + 1.7, "  loops / shield / struts:", R("{geom.solid_angle_loops!pct:2} / {geom.solid_angle_shield!pct:2} / "
                                                                  "{geom.solid_angle_struts!pct:2}"), "ASSUMED", coll=lab)
    kv(p, "GE_kv3", 3, ty + 3.4, "escape: X-ray / neutron", R("{shield.xray_escape!P} / {shield.neutron_escape!P}"), "ASSUMED",
       vcat="radiation", coll=lab)
    kv(p, "GE_kv4", 3, ty + 5.1, "neutron production share", "TBD", "UNKNOWN", coll=lab)
    kv(p, "GE_kv5", 3, ty + 6.8, "crew budget from the drive", R("{shield.crew_dose_budget_Sv_y:.3f} Sv/y · "
                                                                 "{shield.neutron_decades:.1f} neutron decades"), "ASSUMED",
       coll=lab)
    kv(p, "GE_kv6", 3, ty + 8.5, "hardware attenuation", R("{shield.hardware_decades:.0f} decades = placeholder, TBD"),
       "UNKNOWN", coll=lab)
    # shield layers
    sx, sy = 58.0, 50.5
    p.t("GE_layers_h", "shield layers (t)", sx, sy, S_XS, "dim", coll=lab)
    layers = [("LiH crew core", "shield.lih_core", 0.8), ("LiH annulus", "shield.lih_annulus", 0.65),
              ("W X-ray face", "shield.w_face", 1.1), ("frame", "shield.frame", 0.45), ("axial plug", "shield.axial_plug", 0.55)]
    yy = sy + 1.7
    for nm, key, sh in layers:
        wseg = V(key) / 1e3 * 0.085
        p.rect(f"GE_layer_{nm}", sx, yy, sx + wseg, yy + 1.1, K.cat_mat("radiation", sh), cr, 0, 0.4)
        p.t(f"GE_layer_{nm}_t", f"{nm} {sig(V(key) / 1e3, 3)}", sx + wseg + 0.6, yy - 0.05, S_XS, coll=lab)
        yy += 1.6
    p.t("GE_layers_n", R("study placeholder 100 t → {shield.mass!t:3}"), sx, yy + 0.2, S_XS, "faint", coll=lab)
    cu = sub("05", "unresolved", "unresolved (yellow)")
    p.rrect("GE_rule_bg", 3, 61.0 + 9.0, 97, 73.5, 0.4, K.cat_mat("radiation", 0.2), cr, -0.2, 0.0)
    p.t("GE_rule", "Magnetic fields redirect charged particles only. Neutrons and X-ray photons are not deflected: "
        "only mass in their path stops them.", 4, 70.6, S_XS, coll=lab)
    tag(p, "P05", 89.0, 9.4, cu)


def build_tarea():
    p = Panel("05", "P05C", "D3 · RADIATOR AREA vs TEMPERATURE (idealised)",
              "squares drawn to true area, 1 BU = 45 m · all heat at one temperature · P = 2 ε σ A T⁴ (both faces)",
              3, 2, accent="thermal", headline=R("A ∝ 1/T⁴"), head_cat="thermal")
    lab = sub_ui("05", "labels D3")
    s = 1 / 45.0
    base = 50.0
    x = 3.0
    Q = V("calc.heat_total")
    for r in M.temp_rows:
        T = int(r["T"])
        c = K.coll(f"05.radiator example {T} K", section("05"), PALETTE["thermal"][1])
        side = math.sqrt(r["area_total"]) * s
        shade = 0.55 + 0.6 * (T - 800) / 1700
        p.rect(f"TA_sq_{T}", x, base - side, x + side, base, K.cat_mat("thermal", shade), c, 0, 0.5,
               {"T_K": T, "area_m2": r["area_total"], "classification": "CALC"})
        p.t(f"TA_sq_{T}_t", f"{T:,} K", x + side / 2, base + 0.6, S_S, align="CENTER", coll=c)
        p.t(f"TA_sq_{T}_a", f"{r['area_total'] / 1e6:.3f} km²", x + side / 2, base + 2.1, S_XS, "dim", align="CENTER",
            coll=c)
        x += side + 2.6
    # Wayfarer at the same scale
    L = V("canon.ship_body_length_m") * s
    p.rect("TA_ship", 3, base + 4.6, 3 + L, base + 5.2, K.cat_mat("structure", 1.1), sub("05", "structure"), 0, 0.4)
    p.t("TA_ship_t", R("Wayfarer body {canon.ship_body_length_m:.1f} m at the same scale"), 3 + L + 1.0, base + 4.3, S_XS,
        "dim", coll=lab)
    # table
    ty = 57.5
    cols = (3, 18, 36, 58, 78)
    for j, h in enumerate(("T", "flux (2 faces)", R("all {calc.heat_total!P}"), R("warm {thermal.warm_total!P} only"),
                           R("1 g, {calc.1g.heat!P}"))):
        p.t(f"TA_h{j}", h, cols[j], ty, S_XS, "dim", coll=lab)
    for i, r in enumerate(M.temp_rows):
        yy = ty + 1.6 + i * 1.45
        cells = (f"{r['T']:,.0f} K", f"{r['flux'] / 1e3:,.1f} kW/m²", f"{r['area_total'] / 1e6:.3f} km²",
                 f"{r['area_warm'] / 1e6:.3f} km²", f"{r['area_1g'] / 1e6:,.1f} km²")
        for j, cell in enumerate(cells):
            p.t(f"TA_c{i}_{j}", cell, cols[j], yy, S_XS, mat=K.cat_mat("unresolved") if j == 4 else None, coll=lab)
    para(p, "TA_ref", R("FDP-1 design: hot {rad.hot_area!km2:3} at {rad.hot_T:.0f} K + warm {rad.warm_area!km2} at "
                        "{rad.warm_T:.0f} K = {calc.area_total!km2} (ε {rad.emissivity}, 0 K sink, isothermal panels). "
                        "Idealised: these are not validated material operating temperatures; 1,500-2,500 K panels, "
                        "their coolant and structure are TBD."), 3, 66.0, S_XS, 125, "faint", coll=lab)
    glyph(p, "TA_g", 93.5, ty, "CALC", 0.8, lab)
    tag(p, "P07", 88.5, 10.0)


def build_scale():
    p = Panel("05", "P05D", "D4 · RADIATOR SCALE vs WAYFARER (plan view)",
              "1 BU = 140 m · the warm wings of the selected layout W2, port and starboard", 4, 2, accent="thermal",
              headline=R("{calc.wing_tip_to_tip:,.0f} m"), head_cat="thermal")
    lab = sub_ui("05", "labels D4")
    ct, cs = sub("05", "thermal"), sub("05", "structure")
    s = 1 / 140.0
    cx, cy = 29.0, 43.0
    xb, xa = 267.15 + 12.0, V("nozzle.loop3_x")     # FDP-1 bow (T-B +122.4 m, + 12 m Lance) to loop 3
    bow_px = lambda x: cx - x * s
    p.rect("SC_ship", bow_px(xb), cy - 0.3, bow_px(xa), cy + 0.3, K.cat_mat("structure", 1.1), cs, 0, 0.6)
    tip = V("rad.wing_tip_radius")
    root = V("rad.wing_root_radius")
    band = V("rad.hot_band")
    xf, xa_w = 88.0, 88.0 - V("rad.wing_chord")
    for sgn in (-1, 1):
        p.rect(f"SC_hot_{sgn}", bow_px(xf), cy + sgn * 10 * s, bow_px(xa_w), cy + sgn * root * s, K.cat_mat("thermal", 1.18),
               ct, 0, 0.4)
        p.rect(f"SC_warm_{sgn}", bow_px(xf), cy + sgn * root * s, bow_px(xa_w), cy + sgn * tip * s,
               K.cat_mat("thermal", 0.75), ct, 0, 0.4, {"component": "radiators"})
    K.ring2d("SC_tip_circle", *p.w(cx, cy), tip * s, 0.1, K.ui_mat("faint"), lab, 0.0, 0.1, n=96)
    p.t("SC_tip_t", R("tip radius {rad.wing_tip_radius:,.0f} m"), cx + 3.0, cy - tip * s - 0.2, S_XS, "dim", coll=lab)
    p.t("SC_ship_lab", "ship", cx + 2.6, cy - 0.9, S_XS, coll=lab)
    # scale bar
    p.rect("SC_bar", 3, 72.0, 3 + 1000 * s, 72.4, K.ui_mat("text"), lab, 0, 0.2)
    p.t("SC_bar_t", "1 km", 3 + 1000 * s + 0.8, 71.6, S_XS, "dim", coll=lab)
    # inset 1 BU = 12 m
    ix0, iy0, iw, ih = 56.0, 11.0, 41.0, 30.0
    si = 1 / 12.0
    p.frame("SC_inset", ix0, iy0, ix0 + iw, iy0 + ih, 0.12, K.ui_mat("panel_edge"), lab, 0, 0.15)
    p.t("SC_inset_t", "inset ×10: 1 BU = 12 m", ix0 + 1, iy0 + 0.6, S_XS, "dim", coll=lab)
    icx = ix0 + iw / 2 + 2
    icy = iy0 + ih / 2 + 1.5
    ipx = lambda x: icx - x * si
    p.rect("SC_i_hull", ipx(144.75), icy - 6.5 * si, ipx(-144.75), icy + 6.5 * si, K.cat_mat("structure", 1.0), cs, 0, 0.5)
    p.rect("SC_i_tb", ipx(267.15), icy - 34.5 * si, ipx(144.75), icy + 34.5 * si, K.cat_mat("propellant", 0.5),
           sub("05", "propellant"), 0, 0.3)
    for xr in (95.15, 70.0):
        p.rect(f"SC_i_ring_{xr}", ipx(xr) - 0.3, icy - 30 * si, ipx(xr) + 0.3, icy + 30 * si, K.cat_mat("structure", 1.2),
               cs, 0, 0.6)
    for sgn in (-1, 1):
        p.rect(f"SC_i_hot_{sgn}", ipx(xf), icy + sgn * 10 * si, ipx(xa_w), icy + sgn * min(root * si, ih / 2 - 1.2),
               K.cat_mat("thermal", 1.18), ct, 0, 0.4)
    p.t("SC_i_t1", R("wing roots: 1800 K band {rad.hot_band:.0f} m, then 600 K field"), ix0 + 1, iy0 + ih - 1.6, S_XS,
        coll=lab)
    p.t("SC_i_t2", "hull + tank bays (T-B)", ipx(267.15), icy + 3.2, S_XS, "dim", coll=lab)
    # comparison squares
    ty = 45.0
    sq = 1 / 800.0
    a_now = V("calc.area_total")
    a_1g = V("calc.1g.warm_area") + V("calc.1g.hot_area")
    s1, s2 = math.sqrt(a_now) * sq, math.sqrt(a_1g) * sq
    p.rect("SC_sq_now", 58, ty + 22.0 - s1, 58 + s1, ty + 22.0, K.cat_mat("thermal", 1.0), ct, 0, 0.4)
    p.frame("SC_sq_1g", 62, ty + 22.0 - s2, 62 + s2, ty + 22.0, 0.14, K.cat_mat("unresolved"), sub("05", "unresolved"),
            0, 0.3, dashed=0.8)
    p.t("SC_sq_h", "radiator planform, 1 BU = 800 m:", 58, ty - 0.2, S_XS, "dim", coll=lab)
    p.t("SC_sq_now_t", R("FDP-1 {calc.area_total!km2}"), 58, ty + 22.7, S_XS, mat=K.cat_mat("thermal", 1.15), coll=lab)
    p.t("SC_sq_1g_t", R("1 g at the same\ntemperatures:\n" + f"{a_1g / 1e6:,.0f} km²\n" +
                        f"({math.sqrt(a_1g) / 1e3:.1f} km square)"), 62 + s2 - 0.5, ty + 23.3, S_XS,
        mat=K.cat_mat("unresolved"), coll=lab)
    para(p, "SC_note", R("Tip to tip {calc.wing_tip_to_tip:,.0f} m = {calc.wing_span_over_ship:.0f}× the "
                         "{canon.ship_body_length_m:.0f} m body. Deployment, dynamics and micrometeoroid design: TBD."),
         3, 10.0, S_XS, 64, "faint", coll=lab)
    tag(p, "P07", 89.0, 9.4)
    tag(p, "P09", 85.0, 9.4)


# ===============================================================================================================
def build_mission():
    p = Panel("06", "P06", "MISSION PROFILE · FOUR BURNS",
              "speed against time, minimum round trip (1,716 AU stopping-distance destination)", 0, 2,
              accent="exhaust", headline=R("{mission.engine_years:.2f} y thrust"), head_cat="exhaust")
    ce, cs, cp, cu = sub("06", "exhaust"), sub("06", "structure"), sub("06", "propellant"), sub("06", "unresolved")
    lab = sub_ui("06", "labels")
    gx0, gy0, gw, gh = 10.0, 15.0, 84.0, 20.0
    T_end = 6.6
    X = lambda t: gx0 + t / T_end * gw
    vc = V("canon.target_speed_c")
    Y = lambda b: gy0 + gh - b / vc * gh
    for t in range(0, 7):
        p.seg(f"MP_gx{t}", (X(t), gy0), (X(t), gy0 + gh), 0.07, K.ui_mat("grid"), lab, -0.2, -0.1)
        p.t(f"MP_gx{t}_t", f"{t} y", X(t), gy0 + gh + 0.6, S_XS, "faint", align="CENTER", coll=lab)
    for b in (0.0, 0.008, 0.016):
        p.seg(f"MP_gy{b}", (gx0, Y(b)), (gx0 + gw, Y(b)), 0.07, K.ui_mat("grid"), lab, -0.2, -0.1)
        p.t(f"MP_gy{b}_t", f"{b:.3f} c", gx0 - 0.8, Y(b) - 0.45, S_XS, "faint", align="RIGHT", coll=lab)
    ve, mdot, c = V("prop.ve"), V("prop.mass_flow"), V("const.c")
    t = 0.0
    yr = V("const.year_s")
    coast = V("mission.coast_years_min")
    names = ["1 accelerate out", "2 brake at destination", "3 accelerate home", "4 brake home"]
    for i in range(1, 5):
        ms, me, days = V(f"burn{i}.start_mass"), V(f"burn{i}.end_mass"), V(f"burn{i}.days")
        if i == 4:
            p.dash("MP_coast", (X(t), Y(vc)), (X(t + coast), Y(vc)), 0.35, 0.8, K.cat_mat("structure"), cs)
            p.t("MP_coast_t", R("coast {mission.coast_years_min:.2f} y"), X(t + coast / 2), Y(vc) - 1.8, S_XS, "dim",
                align="CENTER", coll=lab)
            t += coast
        pts = []
        dur = days * 86400.0
        for k in range(31):
            tt = dur * k / 30
            dv = ve * math.log(ms / (ms - mdot * tt))
            b = dv / c if i in (1, 3) else vc - dv / c
            pts.append((X(t + tt / yr), Y(min(max(b, 0.0), vc))))
        p.prism(f"MP_band_{i}", [(X(t), gy0), (X(t + dur / yr), gy0), (X(t + dur / yr), gy0 + gh), (X(t), gy0 + gh)],
                K.cat_mat("exhaust", 0.16), ce, -0.35, -0.3)
        p.poly(f"MP_burn_{i}", pts, 0.42, K.cat_mat("exhaust", 1.1), ce, 0, 0.3,
               {"burn": i, "days": days, "start_mass_kg": ms, "end_mass_kg": me})
        p.t(f"MP_burn_{i}_t", f"{names[i - 1]}\n{days:,.0f} d\n{sig(ms / 1e3, 4)} → {sig(me / 1e3, 4)} t",
            X(t) + 0.5, gy0 + gh + 2.2, S_XS, coll=lab)
        t += dur / yr
    # canon duration line
    td = V("canon.mission_duration_y")
    p.dash("MP_canon", (X(td), gy0 - 2.5), (X(td), gy0 + gh), 0.25, 0.7, K.cat_mat("unresolved"), cu)
    p.t("MP_canon_t", R("canon LOCKED mission\nduration {canon.mission_duration_y:.1f} y"), X(td) - 0.6, gy0 - 2.6, S_XS,
        mat=K.cat_mat("unresolved"), align="RIGHT", coll=lab)
    p.t("MP_end_t", R("{mission.min_round_trip_years:.2f} y"), X(t) + 0.6, Y(0) - 2.0, S_XS, mat=K.cat_mat("exhaust", 1.15),
        coll=lab)
    # 1 g track
    y1 = 46.5
    p.t("MP_1g_h", R("IDEAL 1 g: four burns of {calc.1g.burn_days:.2f} d = {calc.1g.total_days:.1f} d of propulsion "
                     "(same Δv, same propellant per burn)"), 3, y1, S_XS, "dim", coll=lab)
    for i in range(4):
        x = X(i * 1.6)
        p.rect(f"MP_1g_{i}", x, y1 + 1.8, x + max(V("calc.1g.burn_days") / 365.25 / T_end * gw, 0.25), y1 + 3.2,
               K.cat_mat("unresolved"), cu, 0, 0.3)
    p.t("MP_1g_n", "(drawn at true width on the time axis above; spacing illustrative)", X(6.4), y1 + 1.8, S_XS, "faint",
        align="RIGHT", coll=lab)
    # fuel budget bar
    y2 = 53.0
    p.t("MP_fuel_h", R("ONE PROPELLANT LOAD FOR ALL FOUR BURNS, NO REFUELLING: {mass.propellant!t} + reserve "
                       "{mass.reserve!t:3}"), 3, y2, S_XS, "dim", coll=lab)
    x = 3.0
    tot = V("mass.propellant") + V("mass.reserve")
    for i in range(1, 5):
        m = V(f"burn{i}.start_mass") - V(f"burn{i}.end_mass")
        wseg = m / tot * 94.0
        p.rect(f"MP_fuel_{i}", x, y2 + 1.8, x + wseg - 0.2, y2 + 4.6, K.cat_mat("propellant", 1.0 - 0.15 * (i - 1)), cp, 0, 0.8)
        p.t(f"MP_fuel_{i}_t", f"burn {i}: {sig(m / 1e3, 4)} t", x + 0.6, y2 + 2.6, S_XS, mat=K.ui_mat("text"), coll=lab,
            z=1.0)
        x += wseg
    p.rect("MP_fuel_res", x, y2 + 1.8, 97.0, y2 + 4.6, K.cat_mat("propellant", 0.45), cp, 0, 0.8)
    p.t("MP_fuel_res_t", "reserve", 97.0, y2 + 5.0, S_XS, "dim", align="RIGHT", coll=lab)
    y3 = 61.0
    para(p, "MP_n1", R("Engine operation {mission.engine_years:.2f} y is not mission duration: the minimum round trip "
                       "is {mission.min_round_trip_years:.2f} y with {mission.coast_years_min:.2f} y of coast; a 10,000 AU "
                       "destination takes {mission.total_years_10kAU:.1f} y. Total Δv {calc.dv_total_c:.3f} c."),
         3, y3, S_XS, 125, "text", coll=lab)
    glyph(p, "MP_flag_g", 3, y3 + 4.6, "UNKNOWN", 0.9, cu)
    para(p, "MP_n2", R("Conflict (not resolved here): the minimum round trip exceeds the canon LOCKED "
                       "{canon.mission_duration_y:.1f} y (02_SHIP_INPUTS A6:H6) by {calc.round_trip_vs_canon:.2f} y. "
                       "Margin policy for the {calc.reserve_share!pct:1} reserve: TBD."), 4.6, y3 + 4.4, S_XS, 120,
         mat=K.cat_mat("unresolved"), coll=cu)
    tag(p, "P10", 88.0, 9.4)


# ===============================================================================================================
STATUS_COLOR = {"known": ("verified", 1.0), "calculated": ("structure", 1.2), "assumed": ("unresolved", 0.75),
                "unresolved": ("unresolved", 1.0), "speculative": ("unresolved", 1.0)}
LINKS = {"P01": "01 burn point · A · A2", "P02": "01 drivers · A2", "P03": "01 · B1 · B2 · C",
         "P04": "01 nozzle · D1", "P05": "01 shield · D1 · D2", "P06": "01 manifolds · A2 · D1",
         "P07": "01 wings · D1 · D3 · D4", "P08": "01 tanks · B1 · B2", "P09": "D4 · 01 struts",
         "P10": "01 · B1 · mission"}


def build_requirements():
    p = Panel("07", "P07", "E · ENGINEERING REQUIREMENTS AND UNRESOLVED PROBLEMS",
              "each problem: parameters, current value, target, gap, classification, status, dependencies · "
              "yellow = unresolved · TBD = no adequate source", 1, 2, cw=2, accent="unresolved",
              headline=f"{len(M.requirements)} open problems", head_cat="unresolved")
    lab = sub_ui("07", "card text")
    cu = sub("07", "unresolved", "unresolved cards (yellow)")
    cv = sub("07", "verified", "satisfied parts (green)")
    cw, ch = 38.4, 30.8
    for i, rq in enumerate(M.requirements):
        col, row = i % 5, i // 5
        x0 = 2.4 + col * (cw + 1.6)
        y0 = 10.0 + row * (ch + 1.4)
        st = rq["status"]
        cat, sh = STATUS_COLOR[st]
        props = {"req_ids": rq["id"], "status": st, "classification": ",".join(rq["classification"]),
                 "depends": ",".join(rq["depends"]), "params": ",".join(rq["params"])}
        unresolved = True   # every listed problem still has an open gap
        p.rrect(f"REQ_{rq['id']}_card", x0, y0, x0 + cw, y0 + ch, 0.7, K.cat_mat("unresolved" if unresolved else "structure",
                                                                                      0.13), cu, -0.3, -0.1, props)
        p.frame(f"REQ_{rq['id']}_edge", x0, y0, x0 + cw, y0 + ch, 0.14,
                K.cat_mat("unresolved", 0.85) if unresolved else K.ui_mat("panel_edge"), cu, -0.1, 0.0, props)
        p.t(f"REQ_{rq['id']}_id", rq["id"], x0 + 1.0, y0 + 0.8, 2.2, mat=K.cat_mat("unresolved"), coll=lab, props=props)
        para(p, f"REQ_{rq['id']}_title", rq["title"], x0 + 7.4, y0 + 0.9, 1.0, 46, "text", coll=lab)
        p.rrect(f"REQ_{rq['id']}_st", x0 + cw - 9.6, y0 + ch - 2.3, x0 + cw - 0.8, y0 + ch - 0.7, 0.4,
                K.cat_mat(cat, sh), cu, 0.0, 0.2, props)
        p.t(f"REQ_{rq['id']}_st_t", st.upper(), x0 + cw - 5.2, y0 + ch - 2.05, S_XS, mat=K.ui_mat("dark"), align="CENTER",
            coll=lab, z=0.8)
        y = y0 + 4.2
        y = para(p, f"REQ_{rq['id']}_desc", R(rq["description"]), x0 + 1.0, y, 0.92, 70, "dim", coll=lab) + 0.6
        fields = [("Params", ", ".join(rq["params"]), "faint"), ("Now", " · ".join(R(c) for c in rq["current"]), "text"),
                  ("Need", R(rq["target"]), "text"), ("Gap", R(rq["gap"]), "gap"),
                  ("Class", ", ".join(rq["classification"]), "dim"), ("Depends", ", ".join(rq["depends"]) or "none", "dim"),
                  ("Drawn", LINKS.get(rq["id"], ""), "faint")]
        for f, txt, ui in fields:
            lines = wrap(txt, 58)
            p.t(f"REQ_{rq['id']}_{f}_k", f, x0 + 1.0, y, 0.84, "faint", coll=lab)
            if ui == "gap":
                mat = K.cat_mat("unresolved")
                p.t(f"REQ_{rq['id']}_{f}_v", "\n".join(lines), x0 + 6.6, y, 0.92, mat=mat, coll=lab, props=props)
            else:
                mat = K.cat_mat("unresolved") if "TBD" in txt else None
                p.t(f"REQ_{rq['id']}_{f}_v", "\n".join(lines), x0 + 6.6, y, 0.92, ui if mat is None else "text", mat=mat,
                    coll=lab, props=props)
            y += len(lines) * 0.92 * 1.18 + 0.4
        if y > y0 + ch - 2.4:
            print(f"WARNING: card {rq['id']} text reaches {y - y0:.1f} of {ch}")


# ===============================================================================================================
CAMERAS = []


def camera(name, x0, y0, x1, y1, res, ortho=True, frame=None, rot=None, loc=None, scale=None):
    coll = section("08")
    cam = bpy.data.cameras.new(name)
    o = bpy.data.objects.new(name, cam)
    coll.objects.link(o)
    aspect = res[0] / res[1]
    if ortho:
        cam.type = "ORTHO"
        w, h = (x1 - x0), (y1 - y0)
        cam.ortho_scale = max(w, h * aspect) * 1.02
        o.location = ((x0 + x1) / 2, (y0 + y1) / 2, 200.0)
        o.rotation_euler = (0, 0, 0)
    else:
        cam.type = "ORTHO"
        cam.ortho_scale = scale
        o.location = loc
        o.rotation_euler = rot
    cam.clip_start, cam.clip_end = 1.0, 2000.0
    o["resolution"] = list(res)
    o["region"] = [x0, y0, x1, y1]
    CAMERAS.append(o)
    return o


def cell(c, r, cw=1, rh=1, m=1.0):
    x0 = c * (PW + G) - m
    y1 = -r * (PH + G) + m
    x1 = c * (PW + G) + cw * PW + (cw - 1) * G + m
    y0 = -r * (PH + G) - (rh * PH + (rh - 1) * G) - m
    return x0, y0, x1, y1


def region_res(reg, long=3840):
    w, h = reg[2] - reg[0], reg[3] - reg[1]
    if w >= h:
        return (long, int(round(long * h / w / 2) * 2))
    return (int(round(long * w / h / 2) * 2), long)


def build_cameras():
    allr = (-3.0, -(3 * PH + 2 * G) - 3.0, 5 * PW + 4 * G + 3.0, TOP + 2.0)
    spec = [("CAM_01_OVERVIEW", allr, (3840, 2160)),
            ("CAM_02_FUSION_ENERGY", cell(3, 0, 2), None),
            ("CAM_03_MASS_THRUST_ACCELERATION", cell(0, 1, 3), None),
            ("CAM_04_RADIATION_THERMAL", cell(3, 1, 2, 2), None),
            ("CAM_05_REQUIREMENTS", cell(1, 2, 2), None),
            ("CAM_06_SYSTEM_SCHEMATIC", cell(1, 0, 2), None),
            ("CAM_07_MISSION_PROFILE", cell(0, 2), (2880, 2160)),
            ("CAM_08_LEGEND", cell(0, 0), (2880, 2160)),
            ("CAM_09_ROCKET_EQUATION", cell(0, 1), (2880, 2160)),
            ("CAM_10_MASS_BUDGET", cell(1, 1), (2880, 2160)),
            ("CAM_11_1G_GAP", cell(2, 1), (2880, 2160)),
            ("CAM_12_HEAT_SPLIT", cell(3, 1), (2880, 2160)),
            ("CAM_13_RADIATION_GEOMETRY", cell(4, 1), (2880, 2160)),
            ("CAM_14_RADIATOR_TEMPERATURE", cell(3, 2), (2880, 2160)),
            ("CAM_15_RADIATOR_SCALE", cell(4, 2), (2880, 2160))]
    for name, reg, res in spec:
        camera(name, *reg, res or region_res(reg))
    # isometric view of the 3D schematic
    x0, y0, x1, y1 = cell(1, 0, 2)
    cx, cyy = (x0 + x1) / 2, (y0 + y1) / 2
    rot = (math.radians(58), 0, math.radians(-28))
    import mathutils
    d = mathutils.Euler(rot).to_matrix() @ mathutils.Vector((0, 0, 1))
    loc = (cx + d.x * 300, cyy + d.y * 300, d.z * 300)
    camera("CAM_16_ISOMETRIC_SCHEMATIC", x0, y0, x1, y1, (3840, 2160), ortho=False, rot=rot, loc=loc, scale=215.0)
    # timeline markers switch cameras (scrub frames 1..N)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, len(CAMERAS)
    for i, o in enumerate(CAMERAS):
        mk = sc.timeline_markers.new(o.name, frame=i + 1)
        mk.camera = o
    sc.camera = CAMERAS[0]
    sun = bpy.data.lights.new("SUN_key", "SUN")
    sun.energy = 2.0
    so = bpy.data.objects.new("SUN_key", sun)
    so.rotation_euler = (math.radians(35), math.radians(10), math.radians(-30))
    section("08").objects.link(so)


# ===============================================================================================================
def setup_display(sc):
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT"
    sh.color_type = "MATERIAL"
    sh.show_object_outline = False
    sh.show_cavity = False
    sh.background_type = "WORLD"
    sc.display.render_aa = "16"
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 3840, 2160
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"


def setup_viewports():
    """Make the saved file open on the overview camera in flat material colours (readable without a render)."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "SOLID"
                        sp.shading.light = "FLAT"
                        sp.shading.color_type = "MATERIAL"
                        sp.shading.background_type = "WORLD"
                        sp.overlay.show_floor = False
                        sp.overlay.show_axis_x = False
                        sp.overlay.show_axis_y = False
                        sp.overlay.show_relationship_lines = False
                        sp.clip_end = 5000
                        r3 = sp.region_3d
                        r3.view_perspective = "CAMERA"


def write_texts():
    t = bpy.data.texts.new("README_FDP1_DIAGRAM")
    t.write(open(os.path.join(HERE, "README.md")).read() if os.path.exists(os.path.join(HERE, "README.md")) else "")
    t = bpy.data.texts.new("VALIDATION")
    t.write("\n".join(("PASS " if c["ok"] else "FAIL ") + f"[{c['kind']}] {c['name']}: {c['detail']}" for c in M.checks))


def render_all(sc):
    os.makedirs(RENDER_DIR, exist_ok=True)
    for i, o in enumerate(CAMERAS):
        sc.frame_set(i + 1)          # the timeline marker binds this camera
        sc.camera = o
        rx, ry = o["resolution"]
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        sc.display.shading.light = "STUDIO" if "ISOMETRIC" in o.name else "FLAT"
        sc.render.filepath = os.path.join(RENDER_DIR, o.name + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", o.name, rx, ry)
    sc.frame_set(1)
    sc.camera = CAMERAS[0]
    sc.render.resolution_x, sc.render.resolution_y = 3840, 2160
    sc.display.shading.light = "FLAT"


def main():
    sc = reset_scene()
    for key in SECTIONS:
        section(key)
    build_title()
    build_legend()
    build_overview()
    build_fusion()
    build_magnifier()
    build_rocket()
    build_mass()
    build_gap()
    build_split()
    build_geometry()
    build_tarea()
    build_scale()
    build_mission()
    build_requirements()
    build_cameras()
    setup_display(sc)
    write_texts()
    sc["fdp1_record"] = M.doc["meta"]["record"]
    sc["checks_passed"] = sum(c["ok"] for c in M.checks)
    sc["checks_total"] = len(M.checks)
    print(f"objects: {K.count}, materials: {len(K.mats)}, collections: {len(K.colls)}")
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    if "--render" in ARGS:
        render_all(sc)
    setup_viewports()
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print("saved", OUT_BLEND)


if __name__ == "__main__":
    main()
