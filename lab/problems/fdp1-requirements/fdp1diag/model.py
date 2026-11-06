"""FDP-1 engineering requirements map: derived values and validation checks.

Standard library only, so system python3 and Blender's bundled Python both run it. Inputs come from
data/fdp1_parameters.json (values from the FDP-1 record fdp1-v1, canon and SI constants); every number the
diagram prints is either an input or a derived value here, each with its formula, class and requirement IDs.
Nothing here changes FDP-1 physics: derived values are the stated equations applied to the inputs.
"""
from __future__ import annotations

import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARAMS = os.path.join(ROOT, "data", "fdp1_parameters.json")
REQUIREMENTS = os.path.join(ROOT, "data", "requirements.json")

# ---------------------------------------------------------------------------------------------------------------
# Minimal dimensional analysis: exponents of (kg, m, s, K).
DIM = {
    "kg": (1, 0, 0, 0), "m": (0, 1, 0, 0), "s": (0, 0, 1, 0), "K": (0, 0, 0, 1), "-": (0, 0, 0, 0),
    "m/s": (0, 1, -1, 0), "m/s2": (0, 1, -2, 0), "N": (1, 1, -2, 0), "W": (1, 2, -3, 0), "J": (1, 2, -2, 0),
    "kg/s": (1, 0, -1, 0), "m2": (0, 2, 0, 0), "W/m2": (1, 0, -3, 0), "W/m2/K4": (1, 0, -3, -4),
    "K4": (0, 0, 0, 4), "kg/W": (0, -2, 3, 0), "kg/m2": (1, -2, 0, 0),
}


def dmul(*units):
    out = [0, 0, 0, 0]
    for u in units:
        sign = 1
        if u.startswith("1/"):
            sign, u = -1, u[2:]
        for i, e in enumerate(DIM[u]):
            out[i] += sign * e
    return tuple(out)


# ---------------------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, params_path=PARAMS, req_path=REQUIREMENTS, overrides=None):
        with open(params_path) as f:
            self.doc = json.load(f)
        self.p = self.doc["parameters"]
        for k, v in (overrides or {}).items():
            self.p[k]["value"] = v
        self.d = {}            # derived: key -> dict(value, unit, formula, cls, req)
        self.checks = []       # dict(name, ok, detail, kind)
        self.derive()
        self.validate()
        self.requirements = []
        if req_path and os.path.exists(req_path):
            with open(req_path) as f:
                self.requirements = json.load(f)["requirements"]

    # access -----------------------------------------------------------------------------------------------------
    def v(self, key):
        if key in self.d:
            return self.d[key]["value"]
        return self.p[key]["value"]

    def meta(self, key):
        return self.d.get(key) or self.p[key]

    def cls(self, key):
        return self.meta(key)["class"]

    def put(self, key, value, unit, formula, req=(), cls="CALC"):
        self.d[key] = {"value": value, "unit": unit, "formula": formula, "class": cls, "req": list(req)}
        return value

    # derived values ---------------------------------------------------------------------------------------------
    def derive(self):
        v, put = self.v, self.put
        g0, c, sig, yr = v("const.g0"), v("const.c"), v("const.sigma"), v("const.year_s")
        m0, ve, a0 = v("mass.departure"), v("prop.ve"), v("prop.a0_g")
        Pf = v("fusion.power")
        Q = v("thermal.hot_total") + v("thermal.warm_total")
        put("calc.thrust_ma", m0 * a0 * g0, "N", "F = m0 x a0", ["P03", "P04"])
        put("calc.thrust_mdot", v("prop.mass_flow") * ve, "N", "F = mdot x ve", ["P04", "P08"])
        F = v("prop.thrust")
        put("calc.jet_power", 0.5 * F * ve, "W", "P_jet = 0.5 x F x ve", ["P03", "P04"])
        put("calc.eta_jet", v("calc.jet_power") / Pf, "-", "eta = P_jet / P_fusion", ["P04"])
        put("calc.non_jet_power", Pf - v("calc.jet_power"), "W", "P_fusion - P_jet", ["P05", "P06"])
        put("calc.ve_over_c", ve / c, "-", "ve / c")
        # rocket equation
        put("calc.mass_ratio", m0 / v("mass.end"), "-", "R = m0 / m_final", ["P10"])
        put("calc.dv_total", ve * math.log(v("calc.mass_ratio")), "m/s", "dv = ve x ln(m0 / mf)", ["P10"])
        put("calc.dv_total_c", v("calc.dv_total") / c, "c", "dv / c", ["P10"])
        put("calc.dv_burn_required", v("canon.target_speed_c") * c, "m/s", "0.016 c per burn")
        dvs, tb = [], []
        for i in range(1, 5):
            ms, me = v(f"burn{i}.start_mass"), v(f"burn{i}.end_mass")
            dvs.append(ve * math.log(ms / me))
            tb.append((ms - me) / v("prop.mass_flow") / 86400.0)
            put(f"calc.burn{i}.dv", dvs[-1], "m/s", f"ve x ln(m_start/m_end), burn {i}", ["P10"])
            put(f"calc.burn{i}.days", tb[-1], "d", f"(m_start - m_end) / mdot, burn {i}", ["P10"])
            put(f"calc.burn{i}.a_start_g", F / ms / g0, "g", "F / m_start", ["P03"])
            put(f"calc.burn{i}.a_end_g", F / me / g0, "g", "F / m_end", ["P03"])
        put("calc.engine_years", sum(tb) / 365.25, "y", "sum of burn times", ["P10"])
        put("calc.burn_fraction_of_ve", v("calc.dv_total") / ve, "-", "dv_total / ve = ln R", ["P10"])
        # mass budget
        items = {k[5:]: e["value"] for k, e in self.p.items() if k.startswith("mass.") and e["unit"] == "kg"
                 and k[5:] not in ("departure", "end", "dry", "reserve", "propellant", "fused", "unburned", "he3", "d",
                                   "fixed_added")}
        self.mass_items = items
        dry_items = {k: x for k, x in items.items() if not k.startswith("propellant")}
        put("calc.mass_items_sum", sum(items.values()), "kg", "sum of departure items", ["P03"])
        put("calc.dry_sum", sum(x for k, x in dry_items.items() if "reserve" not in k), "kg", "sum of dry items")
        put("calc.propellant_share", v("mass.propellant") / m0, "-", "propellant / departure", ["P08"])
        put("calc.unburned_share", v("mass.unburned") / v("mass.propellant"), "-", "unburned / propellant", ["P08"])
        put("calc.power_scaled_mass", v("mass.alpha_jet") * v("prop.jet_power"), "kg", "alpha_jet x P_jet", ["P03"])
        # 1 g and intermediate targets at fixed mass, fixed ve, fixed eta (comparison, not a design)
        eta = v("prop.eta_jet")
        steps = [a0] + list(v("target.accel_steps_g"))
        rows = []
        for a in steps:
            Fa = m0 * a * g0
            Pj = 0.5 * Fa * ve
            Pfa = Pj / eta
            rows.append({"a_g": a, "thrust_N": Fa, "jet_W": Pj, "fusion_W": Pfa, "factor": Pfa / Pf,
                         "mdot": Fa / ve, "heat_W": (v("thermal.hot_total") + v("thermal.warm_total")) * Pfa / Pf,
                         "scaled_mass_kg": v("mass.alpha_jet") * Pj, "mass_over_ship": v("mass.alpha_jet") * Pj / m0,
                         "burn_days": v("calc.dv_burn_required") / (a * g0) / 86400.0})
        self.accel_rows = rows
        r1 = next(r for r in rows if abs(r["a_g"] - 1.0) < 1e-9)
        put("calc.1g.thrust", r1["thrust_N"], "N", "F = m0 x 1 g", ["P03"])
        put("calc.1g.jet_power", r1["jet_W"], "W", "0.5 x F x ve", ["P03"])
        put("calc.1g.fusion_power", r1["fusion_W"], "W", "P_jet / eta", ["P01", "P03"])
        put("calc.1g.factor", r1["factor"], "-", "P_fus(1 g) / P_fus(FDP-1) = 1 g / a0", ["P03"])
        put("calc.1g.heat", r1["heat_W"], "W", "radiator heat x factor (same fractions)", ["P06", "P07"])
        put("calc.1g.warm_area", v("rad.warm_area") * r1["factor"], "m2", "warm area x factor (same T)", ["P07"])
        put("calc.1g.hot_area", v("rad.hot_area") * r1["factor"], "m2", "hot area x factor (same T)", ["P07"])
        put("calc.1g.scaled_mass", r1["scaled_mass_kg"], "kg", "alpha_jet x P_jet(1 g)", ["P03"])
        put("calc.1g.scaled_mass_over_ship", r1["mass_over_ship"], "-", "scaled mass / m0", ["P03"])
        put("calc.1g.burn_days", r1["burn_days"], "d", "0.016 c / 1 g", ["P10"])
        put("calc.1g.total_days", 4 * r1["burn_days"], "d", "4 burns at constant 1 g", ["P10"])
        put("calc.1g.mdot", r1["mdot"], "kg/s", "F / ve", ["P08"])
        put("calc.alpha_mass_limit_g", 2.0 / (v("mass.alpha_jet") * g0 * ve) * 1.0, "g",
            "a at which alpha_jet x P_jet = m0 (no propellant, payload or tanks)", ["P03"])
        # heat and radiators
        put("calc.heat_total", Q, "W", "hot + warm loop heat", ["P06"])
        eps = v("rad.emissivity")
        put("calc.flux_hot", 2 * eps * sig * v("rad.hot_T") ** 4, "W/m2", "2 x eps x sigma x T^4", ["P07"])
        put("calc.flux_warm", 2 * eps * sig * v("rad.warm_T") ** 4, "W/m2", "2 x eps x sigma x T^4", ["P07"])
        put("calc.area_hot", v("thermal.hot_total") / v("calc.flux_hot"), "m2", "Q_hot / flux", ["P07"])
        put("calc.area_warm", v("thermal.warm_total") / v("calc.flux_warm"), "m2", "Q_warm / flux", ["P07"])
        put("calc.area_total", v("calc.area_hot") + v("calc.area_warm"), "m2", "hot + warm planform", ["P07"])
        put("calc.radiator_panel_mass", v("rad.hot_area") * v("rad.hot_areal") + v("rad.warm_area") * v("rad.warm_areal"),
            "kg", "area x areal mass", ["P07"])
        put("calc.radiator_mass", v("mass.hot radiators") + v("mass.warm radiators"), "kg", "record hot + warm radiators",
            ["P07"])
        put("calc.transport_mass", v("calc.radiator_mass") - v("calc.radiator_panel_mass"), "kg",
            "record radiator mass - panel mass = heat-transport allowance (kg/W)", ["P06"])
        put("calc.transport_kg_per_W", v("calc.transport_mass") / Q, "kg/W", "transport allowance / heat", ["P06"])
        self.temp_rows = []
        for T in (800.0, 1000.0, 1500.0, 2000.0, 2500.0):
            fl = 2 * eps * sig * T ** 4
            self.temp_rows.append({"T": T, "flux": fl, "area_total": Q / fl, "area_warm": v("thermal.warm_total") / fl,
                                   "area_1g": v("calc.1g.heat") / fl})
        put("calc.wings_planform", v("rad.wings") * v("rad.wing_span") * v("rad.wing_chord"), "m2",
            "wings x span x chord", ["P07"])
        put("calc.wing_tip_to_tip", 2 * v("rad.wing_tip_radius"), "m", "2 x tip radius", ["P07", "P09"])
        put("calc.wing_span_over_ship", v("rad.wing_tip_radius") * 2 / v("canon.ship_body_length_m"), "-",
            "tip-to-tip / Wayfarer body length", ["P07"])
        # energy accounting
        L = {k[7:]: e["value"] for k, e in self.p.items() if k.startswith("ledger.")}
        self.ledger = L
        put("calc.ledger_sum", sum(L.values()), "W", "sum of ledger channels", ["P06"])
        out = L["jet"] + L["plume_to_space"] + L["radiation_to_space"] + Q
        put("calc.outflow_sum", out, "W", "jet + plume to space + radiation to space + radiator heat", ["P06"])
        put("calc.outflow_residual", Pf - out, "W", "P_fusion - outflows", ["P06"])
        put("calc.space_escape", L["plume_to_space"] + L["radiation_to_space"], "W",
            "undirected plume + radiation to space", ["P05"])
        put("calc.deposited_hardware", L["plume_to_hardware"] + L["radiation_on_hardware"] + L["radiation_on_conductor"],
            "W", "plume + radiation absorbed by hardware", ["P05", "P06"])
        put("calc.recirc_house", L["electric_house"] + L["driver_loss"] + L["cryo_input"] + L["recovery_loss"], "W",
            "recirculating-power losses that become heat", ["P02", "P06"])
        put("calc.driver_efficiency", v("driver.beam_power") / v("driver.wall_plug_power"), "-",
            "beam / wall-plug", ["P02"])
        put("calc.pulses_mission", v("fusion.pellet_rate") * v("mission.engine_years") * yr, "-",
            "rep rate x engine time", ["P02", "P09"])
        put("calc.yield_check", v("fusion.target_gain") * v("driver.energy_per_pulse_beam"), "J",
            "gain x beam energy", ["P01"])
        put("calc.fusion_from_pulses", v("fusion.yield_per_pulse") * v("fusion.pellet_rate"), "W",
            "yield x rate", ["P01"])
        put("calc.fusion_energy", Pf * v("mission.engine_years") * yr, "J", "P_fusion x engine time", ["P01"])
        put("calc.jet_energy", v("prop.jet_power") * v("mission.engine_years") * yr, "J", "P_jet x engine time",
            ["P04"])
        put("calc.solid_angle_ratio", v("geom.solid_angle_total") / v("geom.solid_angle_study"), "-",
            "drawn solid angle / study allowance", ["P05"])
        put("calc.tank_ratio_he3", v("tanks.he3_required") / v("tanks.he3_existing"), "-", "required / existing",
            ["P08"])
        put("calc.tank_ratio_d", v("tanks.d_required") / v("tanks.d_existing"), "-", "required / existing", ["P08"])
        put("calc.gain_gap_demonstrated", v("sens.gain_closure_threshold") / v("research.nif_best_gain"), "-",
            "closure gain / demonstrated gain", ["P01"])
        put("calc.gain_margin", v("fusion.target_gain") / v("sens.gain_closure_threshold"), "-",
            "assumed gain / closure threshold", ["P01"])
        put("calc.round_trip_vs_canon", v("mission.min_round_trip_years") - v("canon.mission_duration_y"), "y",
            "FDP-1 minimum round trip - canon LOCKED duration", ["P10"])
        put("calc.reserve_share", v("mass.reserve") / v("mass.propellant"), "-", "reserve / propellant", ["P10"])
        put("calc.sens_800K_saving", 1 - v("sens.warm_loop_800K") / m0, "-", "1 - m0(800 K) / m0", ["P07"])
        put("calc.sens_house_saving", 1 - v("sens.house_load_half") / m0, "-", "1 - m0(house/2) / m0", ["P02"])
        put("calc.specific_mass_mismatch", v("mass.alpha_jet") / v("goal1g.specific_mass") - 1, "-",
            "closure alpha_jet / 1 g-check specific mass - 1", ["P03"])
        put("calc.deficit_check", v("goal1g.specific_mass") / v("goal1g.required_specific_mass"), "-",
            "specific mass / required", ["P03"])
        put("calc.fusion_1g_over_max", 1.0 / v("goal1g.max_a0_any_size_g"), "-", "1 g / FDP-1 ceiling", ["P03"])
        x_burn = v("layout.x_burn")
        put("calc.standoff", v("layout.x_shield_aft") - x_burn, "m", "shield aft face - burn point", ["P05"])

    # checks -----------------------------------------------------------------------------------------------------
    def check(self, name, ok, detail, kind):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail, "kind": kind})

    def validate(self):
        v = self.v
        rel = lambda a, b: abs(a - b) / max(abs(b), 1e-300)
        # dimensional consistency of every equation the diagram uses
        eqs = [
            ("F = m x a", dmul("kg", "m/s2"), dmul("N")),
            ("F = mdot x ve", dmul("kg/s", "m/s"), dmul("N")),
            ("P_jet = 0.5 x F x ve", dmul("N", "m/s"), dmul("W")),
            ("dv = ve x ln(m0/mf)", dmul("m/s"), dmul("m/s")),
            ("P = eps x sigma x A x T^4", dmul("W/m2/K4", "m2", "K4"), dmul("W")),
            ("E = P x t", dmul("W", "s"), dmul("J")),
            ("alpha x P = mass", dmul("kg/W", "W"), dmul("kg")),
        ]
        bad = [n for n, a, b in eqs if a != b]
        self.check("dimensional consistency", not bad, f"{len(eqs)} equations; mismatched: {bad or 'none'}", "dimension")
        # mass conservation
        m0 = v("mass.departure")
        self.check("departure = end + propellant", rel(v("mass.end") + v("mass.propellant"), m0) < 1e-9,
                   f"{(v('mass.end') + v('mass.propellant')) / 1e3:,.1f} t vs {m0 / 1e3:,.1f} t", "mass")
        self.check("end = dry + reserve", rel(v("mass.dry") + v("mass.reserve"), v("mass.end")) < 1e-9,
                   f"{(v('mass.dry') + v('mass.reserve')) / 1e3:,.1f} t vs {v('mass.end') / 1e3:,.1f} t", "mass")
        self.check("departure items sum to departure", rel(v("calc.mass_items_sum"), m0) < 1e-6,
                   f"{v('calc.mass_items_sum') / 1e3:,.1f} t vs {m0 / 1e3:,.1f} t", "mass")
        burns = sum(v(f"burn{i}.start_mass") - v(f"burn{i}.end_mass") for i in range(1, 5))
        chain = all(rel(v(f"burn{i}.end_mass"), v(f"burn{i + 1}.start_mass")) < 1e-9 for i in range(1, 4))
        self.check("propellant = sum of four burns, burns chain", rel(burns, v("mass.propellant")) < 1e-9 and chain,
                   f"{burns / 1e3:,.1f} t", "mass")
        self.check("propellant = fused + unburned = He-3 + D",
                   rel(v("mass.fused") + v("mass.unburned"), v("mass.propellant")) < 1e-6
                   and rel(v("mass.he3") + v("mass.d"), v("mass.propellant")) < 1e-6,
                   f"{v('mass.fused') / 1e3:,.1f} + {v('mass.unburned') / 1e3:,.1f} t (H tamper 36 g)", "mass")
        # energy conservation
        Pf = v("fusion.power")
        self.check("energy ledger sums to fusion power", rel(v("calc.ledger_sum"), Pf) < 1e-9,
                   f"{v('calc.ledger_sum'):.6e} W vs {Pf:.6e} W", "energy")
        self.check("outflows (jet, plume, radiation, radiators) = fusion", abs(v("calc.outflow_residual")) / Pf < 1e-9,
                   f"residual {v('calc.outflow_residual'):.3g} W", "energy")
        hot = sum(e["value"] for k, e in self.p.items() if k.startswith("hot."))
        warm = sum(e["value"] for k, e in self.p.items() if k.startswith("warm."))
        self.check("hot and warm loops = sum of their sources",
                   rel(hot, v("thermal.hot_total")) < 1e-9 and rel(warm, v("thermal.warm_total")) < 1e-9,
                   f"hot {hot / 1e9:.2f} GW, warm {warm / 1e9:.2f} GW", "energy")
        rec = v("power.recovered")
        self.check("recirculating power balance", rel(v("power.electric_load") + v("ledger.recovery_loss"), rec) < 1e-6
                   and rel(v("driver.beam_power") + v("ledger.driver_loss"), v("driver.wall_plug_power")) < 1e-6,
                   f"recovered {rec / 1e9:.2f} GW = load {v('power.electric_load') / 1e9:.2f} + loss "
                   f"{v('ledger.recovery_loss') / 1e9:.2f} GW", "energy")
        self.check("integrated energy E = P x t", rel(v("calc.fusion_energy"), v("mission.fusion_energy")) < 2e-3,
                   f"{v('calc.fusion_energy'):.4e} J vs record {v('mission.fusion_energy'):.4e} J", "energy")
        self.check("fusion power = yield x rate = gain x beam x rate",
                   rel(v("calc.fusion_from_pulses"), Pf) < 1e-6 and rel(v("calc.yield_check"), v("fusion.yield_per_pulse")) < 1e-6,
                   f"{v('calc.fusion_from_pulses') / 1e12:.3f} TW", "energy")
        # performance relationships
        self.check("thrust: F = m0 a0 = mdot ve = record",
                   rel(v("calc.thrust_ma"), v("prop.thrust")) < 1e-6 and rel(v("calc.thrust_mdot"), v("prop.thrust")) < 1e-6,
                   f"{v('calc.thrust_ma') / 1e6:.4f} / {v('calc.thrust_mdot') / 1e6:.4f} / {v('prop.thrust') / 1e6:.4f} MN",
                   "performance")
        self.check("P_jet = 0.5 F ve = record", rel(v("calc.jet_power"), v("prop.jet_power")) < 1e-6,
                   f"{v('calc.jet_power') / 1e12:.3f} TW", "performance")
        dv_req = v("calc.dv_burn_required")
        self.check("each burn dv = 0.016 c (rocket equation)",
                   all(rel(v(f"calc.burn{i}.dv"), dv_req) < 1e-6 for i in range(1, 5)),
                   ", ".join(f"{v(f'calc.burn{i}.dv') / 1e3:,.1f}" for i in range(1, 5)) + " km/s", "performance")
        self.check("burn times = propellant / mdot = record",
                   all(rel(v(f"calc.burn{i}.days"), v(f"burn{i}.days")) < 1e-6 for i in range(1, 5)),
                   ", ".join(f"{v(f'calc.burn{i}.days'):,.0f}" for i in range(1, 5)) + " d", "performance")
        self.check("radiator area = Q / (2 eps sigma T^4) = record",
                   rel(v("calc.area_hot"), v("rad.hot_area")) < 1e-6 and rel(v("calc.area_warm"), v("rad.warm_area")) < 1e-6,
                   f"hot {v('calc.area_hot'):,.0f} m2, warm {v('calc.area_warm') / 1e6:.4f} km2 (eps {v('rad.emissivity')})",
                   "performance")
        self.check("wing planform = warm area", rel(v("calc.wings_planform"), v("rad.warm_area")) < 1e-6,
                   f"{v('calc.wings_planform') / 1e6:.4f} km2", "performance")
        self.check("peak acceleration <= 1.5 g ceiling", v("calc.burn4.a_end_g") <= v("canon.accel_ceiling_g"),
                   f"{v('calc.burn4.a_end_g'):.4f} g", "performance")
        self.check("1 g deficit = specific mass / required", rel(v("calc.deficit_check"), v("goal1g.deficit_factor")) < 1e-6,
                   f"x{v('calc.deficit_check'):.1f}", "performance")

    # formatting helpers -----------------------------------------------------------------------------------------
    def summary(self):
        return {"derived": self.d, "checks": self.checks, "accel_rows": self.accel_rows, "temp_rows": self.temp_rows}


    # templated text ----------------------------------------------------------------------------------------------
    def render(self, text):
        """Replace {key!conv} or {key:spec} with the current value, so labels follow the parameter file."""
        def rep(mo):
            key, conv, spec = mo.group(1), mo.group(2), mo.group(3)
            x = self.v(key)
            if x is None:
                return "TBD"
            if conv == "P":
                return fmt_power(x)
            if conv == "t":
                return sig(x / 1e3, int(spec or 4)) + " t"
            if conv == "kt":
                return f"{x / 1e6:,.{int(spec or 1)}f} kt"
            if conv == "km2":
                return f"{x / 1e6:,.{int(spec or 2)}f} km2"
            if conv == "pct":
                return f"{x * 100:.{int(spec or 1)}f} %"
            if conv == "s":
                return sig(x, int(spec or 3))
            if conv == "MN":
                return sig(x / 1e6, int(spec or 3)) + " MN"
            if conv == "kms":
                return f"{x / 1e3:,.0f} km/s"
            return format(x, spec or "").replace("e+0", "e").replace("e+", "e").replace("e-0", "e-")
        return re.sub(r"\{([a-zA-Z0-9_.]+)(?:!([a-zA-Z0-9]+))?(?::([^}]*))?\}", rep, text)


# ---------------------------------------------------------------------------------------------------------------
def fmt_power(w, digits=3):
    if w is None:
        return "TBD"
    for unit, s in (("PW", 1e15), ("TW", 1e12), ("GW", 1e9), ("MW", 1e6), ("kW", 1e3)):
        if abs(w) >= s:
            return f"{w / s:,.{digits}g} {unit}" if digits else f"{w / s:,.0f} {unit}"
    return f"{w:,.3g} W"


def sig(x, n=3):
    """Round to n significant figures and format with thousands separators."""
    if x is None:
        return "TBD"
    if x == 0:
        return "0"
    d = n - 1 - int(math.floor(math.log10(abs(x))))
    r = round(x, d)
    return f"{r:,.{max(d, 0)}f}"


if __name__ == "__main__":
    m = Model()
    for c in m.checks:
        print(("PASS " if c["ok"] else "FAIL ") + f"[{c['kind']}] {c['name']}: {c['detail']}")
