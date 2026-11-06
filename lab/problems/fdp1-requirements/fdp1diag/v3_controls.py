"""FDP-1 V3 sidebar (embedded in FDP-1_Spatial_Systems_V3.blend as V3_controls.py): exploration modes, the V2 scenario
controls and the P11 protection controls. Open the 3D viewport sidebar (N) and the tab "FDP-1 V3". The panel registers
when the file opens with Python auto-run allowed; otherwise run V3_controls.py once from the Text Editor.

Every rebuild recomputes the scenario from the embedded modules (scenario.py, protection.py, scenario_v3.py). Only these
collections are rewritten: V2_20_TARGET, V3_61..V3_64 and V3_70. Baseline layers and data are never written.
"""
import json
import sys
import types

import bpy

_STATE = {}


def _module(text_name, mod_name):
    m = sys.modules.get(mod_name)
    if m is not None and getattr(m, "_v3_embedded", False):
        return m
    m = types.ModuleType(mod_name)
    m.__file__ = "//" + text_name
    m._v3_embedded = True
    sys.modules[mod_name] = m
    try:
        exec(compile(bpy.data.texts[text_name].as_string(), text_name, "exec"), m.__dict__)
    except BaseException:
        sys.modules.pop(mod_name, None)   # never cache a half-loaded module
        raise
    return m


ORDER = (("v2kit.py", "v2kit"), ("scenario.py", "scenario"), ("v2_target.py", "v2_target"), ("protection.py", "protection"),
         ("scenario_v3.py", "scenario_v3"), ("v3_layers.py", "v3_layers"))


def _load_all():
    return {mod: _module(txt, mod) for txt, mod in ORDER}


def _js(name):
    return json.loads(bpy.data.texts[name].as_string())


def _models():
    if "s3" not in _STATE:
        M = _load_all()
        S, PRm, S3 = M["scenario"], M["protection"], M["scenario_v3"]
        sc = S.Scenario({k: v["value"] for k, v in _js("scenario_inputs.json")["inputs"].items()})
        pr = PRm.Protection(geo=_js("ship_geometry.json"), inputs=_js("protection_inputs.json"))
        _STATE["s3"] = S3.ScenarioV3(sc, pr)
        _STATE["parts"] = {p["name"]: p for p in pr.geo["parts"]}
    return _STATE["s3"], _STATE["parts"]


def rebuild(sc=None):
    sc = sc or bpy.context.scene
    s3, parts = _models()
    M = _load_all()
    K, TG, L3 = M["v2kit"], M["v2_target"], M["v3_layers"]
    K.VIEW["obj"] = bpy.data.objects.get("VIEW_ALIGN")
    T = None if sc.v2_use_base_T else sc.v2_temp
    dens = sc.v3_density if sc.v3_use_density else None
    res = s3.evaluate(sc.v2_accel, T, sc.v2_scaling, sc.v3_cone, sc.v3_margin, sc.v3_band, sc.v3_shield, sc.v3_shield_radius, dens,
                      float(sc.v3_engine_exp))
    ctx3 = json.loads(sc["v3_ctx"])
    D = bpy.data.collections
    TG.build_target(res["v3"], json.loads(sc["v2_ctx"]), D["V2_20_TARGET"])
    L3.build_envelope(res, ctx3, D["V3_61_PROTECTED_ENVELOPE"])
    L3.build_exposure(res, ctx3, parts, D["V3_62_CRITICAL_EXPOSURE"])
    L3.build_shield_ghost(res, ctx3, D["V3_63_SHIELD_GHOST"])
    L3.build_radiator_exposure(res, ctx3, parts, D["V3_64_RADIATOR_EXPOSURE"])
    L3.build_constraints(res, ctx3, D["V3_70_CONSTRAINTS"])
    sc["v3_result"] = json.dumps(L3.summary(res))
    apply_mode(sc)


def apply_mode(sc, _ctx=None):
    L3 = _load_all()["v3_layers"]
    L3.set_mode(sc, sc.v3_mode, sc.v3_detail, sc.v3_show_superseded, sc.v3_show_square)


def _live(self, context):
    if self.v3_live:
        rebuild(self)


def _mode(self, context):
    apply_mode(self)


class V3_OT_rebuild(bpy.types.Operator):
    bl_idname = "fdp1v3.rebuild"
    bl_label = "Rebuild scenario"

    def execute(self, context):
        rebuild(context.scene)
        return {"FINISHED"}


class V3_OT_preset(bpy.types.Operator):
    bl_idname = "fdp1v3.preset"
    bl_label = "Preset"
    accel: bpy.props.FloatProperty(default=-1.0)
    temp: bpy.props.FloatProperty(default=-1.0)
    cone: bpy.props.FloatProperty(default=-1.0)
    margin: bpy.props.FloatProperty(default=-1.0)
    shield: bpy.props.StringProperty(default="")

    def execute(self, context):
        sc = context.scene
        live, sc.v3_live = sc.v3_live, False
        if self.accel >= 0:
            sc.v2_accel = self.accel
        if self.temp == 0:
            sc.v2_use_base_T = True
        elif self.temp > 0:
            sc.v2_use_base_T, sc.v2_temp = False, self.temp
        if self.cone >= 0:
            sc.v3_cone = self.cone
        if self.margin >= 0:
            sc.v3_margin = self.margin
        if self.shield:
            sc.v3_shield = self.shield
        sc.v3_live = live
        rebuild(sc)
        return {"FINISHED"}


class V3_PT_main(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category = "VIEW_3D", "UI", "FDP-1 V3"
    bl_label = "Explore"

    def draw(self, context):
        sc = context.scene
        L = self.layout
        L.prop(sc, "v3_mode", expand=False)
        r = L.row(align=True)
        r.prop(sc, "v3_detail", toggle=True)
        r.prop(sc, "v3_show_superseded", toggle=True, text="Superseded")
        L.label(text="Cameras: scrub the timeline (F = spacecraft focus, S = full scale)")


class V3_PT_scenario(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category = "VIEW_3D", "UI", "FDP-1 V3"
    bl_label = "Propulsion scenario"

    def draw(self, context):
        sc = context.scene
        c = self.layout.column(align=True)
        c.prop(sc, "v2_accel", slider=True)
        c.prop(sc, "v2_use_base_T")
        s = c.column()
        s.enabled = not sc.v2_use_base_T
        s.prop(sc, "v2_temp", slider=True)
        c.prop(sc, "v2_scaling", text="")
        g = self.layout.grid_flow(columns=3, align=True)
        for a, T in ((0.0068956, 0), (0.05, 0), (0.10, 1500), (0.25, 2000), (1.0, 2500), (1.5, 2500)):
            op = g.operator("fdp1v3.preset", text=f"{a:.2g} g" + (f" {T}K" if T else ""))
            op.accel, op.temp = a, T


class V3_PT_protection(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category = "VIEW_3D", "UI", "FDP-1 V3"
    bl_label = "P11 protection"

    def draw(self, context):
        sc = context.scene
        c = self.layout.column(align=True)
        c.prop(sc, "v3_cone")
        g = c.grid_flow(columns=3, align=True)
        for t, v in (("aligned 0°", 0.0), ("2.29° diag.", 2.290610043), ("5° proto.", 5.0)):
            op = g.operator("fdp1v3.preset", text=t)
            op.cone = v
        c.prop(sc, "v3_margin")
        g = c.grid_flow(columns=3, align=True)
        for t, v in (("0 m", 0.0), ("8 m radiator", 8.0), ("15 m ring", 15.0)):
            op = g.operator("fdp1v3.preset", text=t)
            op.margin = v
        c.prop(sc, "v3_band")
        c.separator()
        c.prop(sc, "v3_shield", text="Shield")
        s = c.column()
        s.enabled = sc.v3_shield == "custom"
        s.prop(sc, "v3_shield_radius")
        c.prop(sc, "v3_use_density")
        s = c.column()
        s.enabled = sc.v3_use_density
        s.prop(sc, "v3_density")
        c.prop(sc, "v3_engine_exp", text="Engine geometry")
        r = self.layout.row(align=True)
        r.prop(sc, "v3_live", toggle=True)
        r.operator("fdp1v3.rebuild", icon="FILE_REFRESH")


class V3_PT_status(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category = "VIEW_3D", "UI", "FDP-1 V3"
    bl_label = "Constraint status"

    def draw(self, context):
        sc = context.scene
        try:
            r = json.loads(sc.get("v3_result", "{}"))
        except ValueError:
            r = {}
        if not r:
            self.layout.label(text="press Rebuild scenario")
            return
        b = self.layout.box()
        b.alert = not r["mathematically_closed"]
        b.label(text=f"{r['status']} · ceiling {r['ceiling_g']:.4f} g · gain {r['loop_gain']:.2f}")
        b.label(text=f"fusion {r['fusion_W'] / 1e12:,.1f} TW · thrust {r['thrust_N'] / 1e6:,.2f} MN · {r['departure_kg'] / 1e3:,.0f} t")
        b.label(text=f"mathematically closed: {'yes' if r['mathematically_closed'] else 'NO'} · physically validated: NO")
        for fam, (st, why) in r["constraints"].items():
            row = self.layout.row()
            row.alert = st == "FAIL"
            row.label(text=f"{fam}: {st}")
        cr = r["critical"]
        self.layout.label(text=f"P11: {cr['critical_exposed']} critical parts outside, {cr['exposed_frontal_area_m2']:,.0f} m², "
                               f"max {cr['max_protrusion_m']:.1f} m")
        self.layout.label(text=f"engine r {r['engine_max_radius_m']:.1f} m · clearance {r['engine_clearance_m']:+.1f} m · "
                               f"shield needed r {r['shield_radius_required_m']:.1f} m")
        rd = r["radiators"]
        self.layout.label(text=f"radiators {rd['fraction_exposed'] * 100:.1f} % outside the envelope")
        if r["shield_added_area_m2"] > 0:
            m = r["shield_added_mass_kg"]
            self.layout.label(text=f"shield +{r['shield_added_area_m2']:,.0f} m² · mass " +
                                   (f"+{m / 1e3:,.0f} t (ASSUMPTION)" if m else "UNRESOLVED (OD-014)"))


CLASSES = (V3_OT_rebuild, V3_OT_preset, V3_PT_main, V3_PT_scenario, V3_PT_protection, V3_PT_status)
MODE_ITEMS = (("CLEAN", "Clean ship", "the spacecraft alone"), ("ENERGY", "A  Energy", "where fusion power goes"),
              ("THERMAL", "B  Thermal", "heat paths, loops, radiators"), ("MASS_THRUST", "C  Mass & Thrust", "mass, thrust, feedback, shield"),
              ("MISSION", "D  Mission", "four burns, propellant, duration"), ("PROTECTION", "P11 Protection", "shield envelope and exposure"),
              ("ALL", "All layers", "everything at once"), ("BOARD", "Technical board", "the phase-1 board (camera X)"))


def register():
    S, P = bpy.types.Scene, bpy.props
    S.v3_mode = P.EnumProperty(name="Mode", items=MODE_ITEMS, default="CLEAN", update=_mode)
    S.v3_detail = P.BoolProperty(name="Detail labels", default=False, update=_mode)
    S.v3_show_superseded = P.BoolProperty(name="Superseded drive", default=False, update=_mode)
    S.v3_show_square = P.BoolProperty(name="Equivalent-area square", default=False, update=_mode)
    S.v3_live = P.BoolProperty(name="Live", default=True)
    S.v2_accel = P.FloatProperty(name="Acceleration (g)", min=0.0068956, max=1.5, default=0.05, precision=4, update=_live)
    S.v2_use_base_T = P.BoolProperty(name="Record radiator temperatures", default=True, update=_live)
    S.v2_temp = P.FloatProperty(name="Warm loop (K)", min=800.0, max=2500.0, default=1500.0, precision=0, update=_live)
    S.v2_scaling = P.EnumProperty(name="Scaling", items=(
        ("baseline_closure", "Baseline closure (ceiling 0.0106 g)", ""), ("goal_1g_variant", "Record goal-1g variant (0.0112 g)", "")),
        default="baseline_closure", update=_live)
    S.v3_cone = P.FloatProperty(name="Arrival cone (deg)", min=0.0, max=10.0, default=0.0, precision=3, update=_live)
    S.v3_margin = P.FloatProperty(name="Safety margin (m)", min=0.0, max=50.0, default=0.0, update=_live)
    S.v3_band = P.FloatProperty(name="Uncertain band (m)", min=0.0, max=10.0, default=1.0, update=_live)
    S.v3_shield = P.EnumProperty(name="Shield", items=(("baseline", "Canon 90 m shield", ""), ("required", "Size to cover the engine (ghost)", ""),
                                                       ("custom", "Custom radius (ghost)", "")), default="baseline", update=_live)
    S.v3_shield_radius = P.FloatProperty(name="Ghost radius (m)", min=10.0, max=400.0, default=60.0, update=_live)
    S.v3_use_density = P.BoolProperty(name="Assume shield areal density", default=False, update=_live)
    S.v3_density = P.FloatProperty(name="kg/m² (ASSUMPTION)", min=0.0, max=5000.0, default=50.0, update=_live)
    S.v3_engine_exp = P.EnumProperty(name="Engine geometry", items=(("0.0", "Fixed (no scaling law)", ""),
                                                                    ("0.3333333", "Hypothetical r ∝ P^1/3", ""),
                                                                    ("0.5", "Hypothetical r ∝ P^1/2", "")), default="0.0", update=_live)
    for c in CLASSES:
        try:
            bpy.utils.register_class(c)
        except ValueError:
            bpy.utils.unregister_class(c)
            bpy.utils.register_class(c)


if __name__ == "__main__" or __name__ == "V3_controls":
    register()
