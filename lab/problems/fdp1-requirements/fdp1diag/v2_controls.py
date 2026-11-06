"""FDP-1 V2 sidebar controls (embedded in FDP-1_Spatial_Systems_V2.blend as the text block V2_controls.py).

The panel is in the 3D viewport sidebar (N key), tab "FDP-1 V2". It registers itself when the file opens with
Python auto-run allowed; otherwise open the Text Editor, choose V2_controls.py and press Run Script.

The panel rebuilds only the V2_20_TARGET collection from the embedded scenario.py, scenario_inputs.json, v2kit.py and
v2_target.py. It never writes to the baseline layers or to the data files.
"""
import json
import sys
import types

import bpy


def _module(text_name, mod_name):
    m = sys.modules.get(mod_name)
    if m is not None and getattr(m, "_v2_embedded", False):
        return m
    m = types.ModuleType(mod_name)
    m.__file__ = "//" + text_name
    m._v2_embedded = True
    sys.modules[mod_name] = m
    exec(compile(bpy.data.texts[text_name].as_string(), text_name, "exec"), m.__dict__)
    return m


def _scenario():
    S = _module("scenario.py", "fdp1_v2_scenario")
    raw = json.loads(bpy.data.texts["scenario_inputs.json"].as_string())
    return S.Scenario({k: v["value"] for k, v in raw["inputs"].items()})


def rebuild(scene=None, _ctx=None):
    sc = scene or bpy.context.scene
    K = _module("v2kit.py", "v2kit")
    TG = _module("v2_target.py", "v2_target")
    K.VIEW["obj"] = bpy.data.objects.get("VIEW_ALIGN")
    S = _scenario()
    T = None if sc.v2_use_base_T else sc.v2_temp
    res = S.evaluate(sc.v2_accel, T, sc.v2_scaling)
    c = bpy.data.collections["V2_20_TARGET"]
    TG.build_target(res, json.loads(sc["v2_ctx"]), c)
    st = res["closed"] or res["at_baseline_mass"]
    sc["v2_target_result"] = json.dumps({"inputs": res["inputs"], "status": res["status"], "feasible": res["feasible"],
                                         "ceiling_g": res["ceiling_g"], "loop_gain": res["loop_gain"],
                                         "fusion_W": st["fusion_W"], "thrust_N": st["thrust_N"], "area_m2": st["area_W_m2"],
                                         "tip_m": st["wings"]["tip_radius_m"], "flags": res["flags"]})
    _apply_visibility(sc)


def _lc(sc, name):
    def walk(lc):
        if lc.collection.name == name:
            return lc
        for ch in lc.children:
            r = walk(ch)
            if r:
                return r
    return walk(sc.view_layers[0].layer_collection)


def _show(sc, name, on):
    c = bpy.data.collections.get(name)
    lc = _lc(sc, name)
    if c is None or lc is None:
        return
    lc.hide_viewport = not on
    c.hide_render = not on


def _apply_visibility(sc, _ctx=None):
    _show(sc, "V2_10_BASELINE_INFO", sc.v2_show_baseline)
    _show(sc, "V2_20_TARGET", sc.v2_show_target)
    _show(sc, "V2_21_TARGET_EQUIVALENT_AREA_SQUARE", sc.v2_show_target and sc.v2_show_square)
    _show(sc, "V2_99_SUPERSEDED_FOUR_NOZZLE_DRIVE", sc.v2_show_superseded)
    _show(sc, "V2_30_REQUIREMENTS", sc.v2_show_requirements)


def _live(self, context):
    if self.v2_live:
        rebuild(self)


def _vis(self, context):
    _apply_visibility(self)


class V2_OT_apply(bpy.types.Operator):
    bl_idname = "fdp1v2.apply"
    bl_label = "Rebuild target"
    bl_description = "Recompute the scenario and rebuild the target ghosts"

    def execute(self, context):
        rebuild(context.scene)
        return {"FINISHED"}


class V2_OT_preset(bpy.types.Operator):
    bl_idname = "fdp1v2.preset"
    bl_label = "Preset"
    accel: bpy.props.FloatProperty()
    temp: bpy.props.FloatProperty(default=0.0)

    def execute(self, context):
        sc = context.scene
        live, sc.v2_live = sc.v2_live, False
        sc.v2_accel = self.accel
        sc.v2_use_base_T = self.temp <= 0
        if self.temp > 0:
            sc.v2_temp = self.temp
        sc.v2_live = live
        rebuild(sc)
        return {"FINISHED"}


class V2_PT_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "FDP-1 V2"
    bl_label = "FDP-1 scenario"

    def draw(self, context):
        sc = context.scene
        L = self.layout
        col = L.column(align=True)
        col.prop(sc, "v2_accel", slider=True)
        col.prop(sc, "v2_use_base_T")
        sub = col.column()
        sub.enabled = not sc.v2_use_base_T
        sub.prop(sc, "v2_temp", slider=True)
        col.prop(sc, "v2_scaling", text="")
        row = L.row(align=True)
        row.prop(sc, "v2_live", toggle=True)
        row.operator("fdp1v2.apply", icon="FILE_REFRESH")
        g = L.grid_flow(columns=3, align=True)
        for a, T in ((0.0069, 0), (0.05, 0), (0.10, 1500), (0.25, 2000), (1.0, 2500), (1.5, 2500)):
            op = g.operator("fdp1v2.preset", text=f"{a:g} g" + (f" {T}K" if T else ""))
            op.accel, op.temp = a, T
        box = L.box()
        box.prop(sc, "v2_show_baseline")
        box.prop(sc, "v2_show_target")
        box.prop(sc, "v2_show_square")
        box.prop(sc, "v2_show_requirements")
        box.prop(sc, "v2_show_superseded")
        try:
            r = json.loads(sc.get("v2_target_result", "{}"))
        except ValueError:
            r = {}
        if r:
            b = L.box()
            st = r.get("status", "")
            b.alert = st == "INFEASIBLE"
            b.label(text=f"{st}: ceiling {r.get('ceiling_g', 0):.4f} g, loop gain {r.get('loop_gain', 0):.2f}")
            s = r.get("state", r)
            b.label(text=f"fusion {s.get('fusion_W', 0) / 1e12:,.1f} TW · thrust {s.get('thrust_N', 0) / 1e6:,.1f} MN")
            area = s.get("area_W_m2", s.get("area_m2", 0))
            tip = r.get("wings", {}).get("tip_radius_m", r.get("tip_m", 0))
            b.label(text=f"radiators {area / 1e6:,.2f} km² · wing tip {tip / 1e3:,.2f} km")
            for k, t in r.get("flags", [])[:6]:
                b.label(text=f"{k}: {t[:70]}")
            if st == "INFEASIBLE":
                b.label(text="infeasible under current scaling assumptions (not a physical limit)")


CLASSES = (V2_OT_apply, V2_OT_preset, V2_PT_panel)


def register():
    S = bpy.types.Scene
    S.v2_accel = bpy.props.FloatProperty(name="Acceleration (g)", min=0.0069, max=1.5, soft_max=1.0, default=1.0,
                                         precision=4, update=_live)
    S.v2_use_base_T = bpy.props.BoolProperty(name="Record radiator temperatures", default=False, update=_live)
    S.v2_temp = bpy.props.FloatProperty(name="Warm loop (K)", min=800.0, max=2500.0, default=1500.0, precision=0, update=_live)
    S.v2_scaling = bpy.props.EnumProperty(name="Scaling", items=(
        ("baseline_closure", "Baseline closure (ceiling 0.0106 g)", "alpha_jet from today's FDP-1 record"),
        ("goal_1g_variant", "Record goal-1g variant (ceiling 0.0112 g)", "alpha_jet the record used for its 1 g study")),
        default="baseline_closure", update=_live)
    S.v2_live = bpy.props.BoolProperty(name="Live", default=True)
    S.v2_show_baseline = bpy.props.BoolProperty(name="Baseline information", default=True, update=_vis)
    S.v2_show_target = bpy.props.BoolProperty(name="Target ghosts", default=True, update=_vis)
    S.v2_show_square = bpy.props.BoolProperty(name="Equivalent-area square", default=False, update=_vis)
    S.v2_show_requirements = bpy.props.BoolProperty(name="Requirement markers", default=True, update=_vis)
    S.v2_show_superseded = bpy.props.BoolProperty(name="Superseded four-nozzle drive", default=False, update=_vis)
    for c in CLASSES:
        try:
            bpy.utils.register_class(c)
        except ValueError:
            bpy.utils.unregister_class(c)
            bpy.utils.register_class(c)


if __name__ == "__main__" or __name__ == "V2_controls":
    register()
