"""T02 impact physics, erosion, protection options, detection, plume screening, gas and radiation for the two orientations.

Standard library only. Reads environment.json and exposure.json (run environment.py and exposure.py first). Research, not canon.
    python3 lab/variants/vertex-drive/studies/dust/impacts.py           # writes impacts.json beside this file

The impact model is deliberately an order-of-magnitude bracket. No equation used here is validated at 4,797 km/s: dust accelerators reach
~100 km/s at most (S-T02-HIGGINS-2018), Whipple ballistic-limit equations ~7-10 km/s (S-WHIPPLE-BLE). Every coefficient is labelled.

Regimes at 0.016 c (each grain atom carries ~120 keV per nucleon, a carbon atom ~1.4 MeV):
- ATOMIC (grain diameter below ~2 um, m < ~1e-14 kg): the grain is thinner than the ~1-2 um range of its own MeV atoms in solids; it
  acts as a cluster-ion burst that heats a micrometre-deep spot (explosive evaporation and cratering, Hoang et al. 2017).
- HYDRODYNAMIC (d above ~2 um): a collective shock; the grain penetrates about its own length times sqrt(rho_p / rho_t) and its energy
  is released there as a point explosion. Crater volume taken proportional to energy (energy scaling, EXTRAPOLATION):
  V = k E with k = 1e-11 (LOW damage) .. 3e-11 (NOMINAL) .. 1e-10 (HIGH) m3/J for metals and C/C (thermodynamic bound for Al:
  ~3e-10 m3/J if all energy melted; vaporisation and radiation take most of it at these speeds).
- Behind a bumper: the grain and the bumper mass it meets become a plasma that expands while it crosses the stand-off S; the wall
  survives if the cloud's energy fluence g E / (pi (S tan a)^2) stays below F_allow. NOMINAL g = 0.5, a = 30 deg, F_allow = 1 J/cm2
  (melt onset of W under short pulses, VTX-06B); band: a 15-45 deg, F_allow 0.3-3 J/cm2.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = json.load(open(os.path.join(HERE, "environment.json")))
EXP = json.load(open(os.path.join(HERE, "exposure.json")))
OUT = os.path.join(HERE, "impacts.json")

C = 299792458.0
V = 0.016 * C
AMU = 1.66053907e-27
E_T = ENV["meta"]["energy_thresholds_J"]
M_E = ENV["meta"]["mass_edges_kg"]
CASES = ("LOW", "NOMINAL", "HIGH", "NOMINAL_HILAT")

K_CRATER = {"LOW": 1e-11, "NOMINAL": 3e-11, "HIGH": 1e-10}     # m3/J, EXTRAPOLATION
PERF_RATIO = 1.5            # wall thickness perforated / crater depth (spall), ASSUMPTION
BUMPER = {"g": 0.5, "alpha_deg": 30.0, "F_allow_J_m2": 1e4}     # NOMINAL; band below
BUMPER_BAND = {"low": {"g": 0.5, "alpha_deg": 15.0, "F_allow_J_m2": 3e3}, "high": {"g": 0.5, "alpha_deg": 45.0, "F_allow_J_m2": 3e4}}


def grain(m, rho=2500.0):
    d = 2 * (3 * m / (4 * math.pi * rho)) ** (1 / 3)
    return {"mass_kg": m, "diameter_m": d, "energy_J_at_cruise": 0.5 * m * V * V, "tnt_kg": 0.5 * m * V * V / 4.184e6,
            "regime": "ATOMIC" if d < 2e-6 else "HYDRODYNAMIC"}


def crater_depth(E, k):
    return (3 * k * E / (2 * math.pi)) ** (1 / 3)


def perforation_energy(t_wall, k):
    """Energy whose crater perforates (with spall) a monolithic wall of thickness t."""
    p = t_wall / PERF_RATIO
    return 2 * math.pi * p ** 3 / (3 * k)


def bumper_defeat_energy(S, b=BUMPER):
    return b["F_allow_J_m2"] * math.pi * (S * math.tan(math.radians(b["alpha_deg"]))) ** 2 / b["g"]


def interp_col(colE, E):
    """Column N(>E) per m2 at an arbitrary energy, log-log between the thresholds (0 beyond the last positive value)."""
    if E <= E_T[0]:
        return colE[0]
    for (e0, c0), (e1, c1) in zip(zip(E_T, colE), zip(E_T[1:], colE[1:])):
        if e0 <= E <= e1:
            if c0 <= 0:
                return 0.0
            if c1 <= 0:
                # fall off: linear in log E to zero
                return c0 * (math.log(e1) - math.log(E)) / (math.log(e1) - math.log(e0))
            return math.exp(math.log(c0) + (math.log(c1) - math.log(c0)) * (math.log(E) - math.log(e0)) / (math.log(e1) - math.log(e0)))
    return 0.0


def leg_colE(leg, case):
    c = leg["cases"][case]["column_N_gt_E_per_m2"]
    return [sum(c[p][k] for p in c) for k in range(len(E_T))]


def leg_energy_fluence(leg, case):
    return sum(leg["cases"][case]["energy_fluence_J_m2"].values())


# ---- protection options and their failure energy ---------------------------------------------------------------------
def options(k):
    """E_fail per protection class (J). Thin walls: cryostat / tank / ring pressure wall taken as 5 mm metal (ASSUMPTION)."""
    return {
        "bare_5mm_wall": perforation_energy(0.005, k),
        "bumper_S1m": bumper_defeat_energy(1.0),
        "bumper_S2m": bumper_defeat_energy(2.0),
        "bumper_S10m": bumper_defeat_energy(10.0),
        "skirt_or_shield_S100m": bumper_defeat_energy(100.0),
    }


def hits_table(ship_key, legs, area_by_orient, case, k):
    """Expected number of grains above each failure energy, per leg, for an exposed area (m2) chosen per orientation."""
    rows = []
    for leg in legs:
        A = area_by_orient[leg["orientation"]]
        colE = leg_colE(leg, case)
        r = {"leg": leg["id"], "name": leg["name"], "orientation": leg["orientation"], "area_m2": round(A, 1)}
        for oname, Ef in options(k).items():
            r[oname] = A * interp_col(colE, Ef)
        rows.append(r)
    return rows


def required_standoff(legs, areas, case, target=0.1):
    """Smallest bumper stand-off S (m) for which the expected number of grains above the bumper's defeat energy, over all legs,
    stays below `target`; None if even 1 km does not."""
    def n(S):
        Ef = bumper_defeat_energy(S)
        return sum(areas[l["orientation"]] * interp_col(leg_colE(l, case), Ef) for l in legs)
    lo, hi = 0.1, 1000.0
    if n(lo) <= target:
        return 0.0          # nothing exposed, or already below the target without a bumper stand-off
    if n(hi) > target:
        return None
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if n(mid) > target:
            lo = mid
        else:
            hi = mid
    return hi


def survival(rows, key):
    n = sum(r[key] for r in rows)
    return {"expected_failures": n, "p_no_failure": math.exp(-n)}


# ---- erosion and gas --------------------------------------------------------------------------------------------------
def erosion(legs, case):
    out = []
    for leg in legs:
        Phi = leg_energy_fluence(leg, case)
        g = leg["cases"][case]["gas_column_per_m2"]
        Nh = g["p"] + g["H0"]
        out.append({"leg": leg["id"], "orientation": leg["orientation"], "dust_energy_fluence_J_m2": Phi,
                    "dust_erosion_um": {kk: K_CRATER[kk] * Phi * 1e6 for kk in K_CRATER},
                    "gas_H_column_per_cm2": Nh * 1e-4, "gas_He_column_per_cm2": g["He"] * 1e-4,
                    "gas_sputter_erosion_nm": {"Y=1e-3": 1e-3 * (Nh + g["He"]) * 1.6e-29 * 1e9, "Y=1e-2": 1e-2 * (Nh + g["He"]) * 1.6e-29 * 1e9},
                    "gas_energy_fluence_J_m2": leg["cases"][case]["gas_energy_fluence_J_m2"]})
    return out


def gas_physics():
    ep = 0.5 * 1.007 * AMU * V * V
    eh = 0.5 * 4.0026 * AMU * V * V
    rho_lic = (0.195e6 + 0.07e6) * 1.007 * AMU + 0.015e6 * 4.0026 * AMU
    return {"proton_energy_keV": ep / 1.602e-16, "helium_energy_keV": eh / 1.602e-16,
            "lic_mass_density_kg_m3": rho_lic, "lic_power_flux_W_m2": 0.5 * rho_lic * V ** 3,
            "proton_larmor_radius_m_at_1mT": 1.007 * AMU * V / (1.602e-19 * 1e-3),
            "grain_larmor_radius_m_at_1mT": V / (0.6 * 1e-3),
            "dipole_bubble_energy_J_r100m_1mT": (1e-3) ** 2 / (2 * 4e-7 * math.pi) * 4 / 3 * math.pi * 100 ** 3,
            "notes": ["120 keV protons stop within ~1 um of a surface (implantation, not penetration)",
                      "neutral H (~75 % of the LIC gas by number) cannot be deflected magnetically without first being ionised",
                      "blistering thresholds for H in metals are ~1e17-1e18 H/cm2 (EXTRAPOLATION from fusion-materials data; S-T02-BLISTER)"]}


# ---- detection and active clearing ------------------------------------------------------------------------------------
def detection():
    rows = []
    h_nu = 6.626e-34 * C / 1.064e-6
    for d_mm in (0.1, 1.0, 10.0):
        a = d_mm * 1e-3 / 2
        m = 2500 * 4 / 3 * math.pi * a ** 3
        for R in (1e3, 1e4, 1e5, 1e6):
            # 1 J pulse, 10 urad full divergence, grain albedo 0.1 Lambertian, 1 m2 receiver
            spot = R * 10e-6 / 2
            frac = min(1.0, a * a / (spot * spot))
            n_ph = 1.0 * frac * 0.1 * 1.0 / (math.pi * R * R) / h_nu
            t = R / V
            # energy to vaporise the grain (1e7 J/kg) delivered on the grain from the same beam
            e_need = m * 1e7 / frac
            dv_needed = 120.0 / t        # m/s sideways to miss a 112 m engine envelope by the time it arrives
            rows.append({"grain_d_mm": d_mm, "mass_kg": m, "range_m": R, "warning_s": t, "photons_back_per_J": n_ph,
                         "beam_energy_to_vaporise_J": e_need, "sideways_dv_to_miss_engine_m_s": dv_needed})
    return {"assumptions": "1 J, 1.064 um pulse, 10 urad beam, albedo 0.1, 1 m2 receiver; vaporisation 1e7 J/kg; grain density 2500 kg/m3 (ASSUMPTION)",
            "rows": rows,
            "search_rate_note": "covering a 112 m radius at 100 km needs ~(112/0.5)^2 = 5e4 beam spots per 21 ms frame: ~2.4e6 pulses/s",
            "verdict": "Grains are detectable only at ranges giving milliseconds of warning, and no beam can vaporise or deflect them in that time; "
                       "the only workable 'clearing' is a physical screen that turns each grain into plasma far enough ahead (the stand-off physics above)."}


# ---- plume screening (braking) ---------------------------------------------------------------------------------------
def plume():
    out = {}
    gens = {"V0": (0.0731, 112.2), "V1": (0.0731 * 0.7044 / 1.4039, 112.0), "CANON": (1.134, 5.6)}
    ve = 19201.17208e3
    for g, (mdot, r_exit) in gens.items():
        for th in (10.0, 20.0, 40.0):
            t = math.tan(math.radians(th))
            sigma = mdot / (ve * math.pi * t * r_exit)                 # kg/m2 along the axis from the exit to infinity (conical plume)
            res = []
            for m in (1e-15, 1e-12, 1e-9, 1e-6):
                a = (3 * m / (4 * math.pi * 2500)) ** (1 / 3)
                m_int = sigma * math.pi * a * a
                e_dep = 0.5 * m_int * (ve + V) ** 2
                res.append({"grain_kg": m, "intercepted_plume_kg": m_int, "energy_deposited_J": e_dep,
                            "ratio_to_vaporisation": e_dep / (m * 1e7), "momentum_ratio": m_int * (ve + V) / (m * V)})
            out[f"{g}_half_angle_{th:g}"] = {"mass_flow_kg_s": mdot, "exit_radius_m": r_exit, "axial_column_kg_m2": sigma, "grains": res}
    return {"cases": out, "model": "steady conical plume, column from the exit plane to infinity on the axis; the grain meets plume ions at ve + v; "
                                   "pulsed bursts (FDP-1 pellets at ~100-200 Hz) are diluted by the same geometry",
            "verdict": "The plume can vaporise grains below ~1e-15 kg; their vapour keeps its momentum and energy (momentum ratio < 1e-6). "
                       "It removes far less than 1 % of the hazardous (> 1 ug) fluence. No credit."}


# ---- skirt (T02-NEW-1) -----------------------------------------------------------------------------------------------
def skirt_geometry(gen):
    gp = EXP["meta"]["generations"][gen]
    th = math.radians(gp["hardware_cone_deg"])
    r0, r1 = gp["shadow_shield_r"], 45.0
    slant = (r1 - r0) / math.sin(th)
    area = math.pi * (r0 + r1) * slant
    x0 = -227.53981167687354 + r0 / math.tan(th)
    x1 = -227.53981167687354 + r1 / math.tan(th)
    eff = 1 / math.sin(th)
    rows = {}
    for sig in (0.5, 1.0, 2.0):
        rows[f"{sig:g}_kg_m2"] = {"mass_t": area * sig / 1e3, "sheet_C_C_mm_equiv": sig / 1.8, "effective_thickness_along_track_mm": sig / 1.8 * eff}
    return {"half_angle_deg": gp["hardware_cone_deg"], "r_from_m": r0, "r_to_m": r1, "x_from_m": x0, "x_to_m": x1, "slant_m": slant,
            "surface_m2": area, "projected_m2": math.pi * (r1 ** 2 - r0 ** 2), "grazing_angle_deg": gp["hardware_cone_deg"],
            "track_thickness_gain": eff, "areal_density_options": rows,
            "burn_solid_angle": "zero for a point source (the sheet contains the burn's rays) and inside the shadow shield's umbra if set "
                                "at or below the hardware cone; finite-source and scatter terms UNKNOWN (needs T04 source size)"}


def canon_skirt():
    r0, r1 = 5.7, 45.0
    return {"x_m": -98.0, "r_from_m": r0, "r_to_m": r1, "projected_m2": math.pi * (r1 ** 2 - r0 ** 2),
            "shadow_check": {"reactor_shield_half_angle_deg": math.degrees(math.atan(5.7 / 2.0)),
                             "radius_in_shadow_at_x_m": (-98.0 + 114.8) * 5.7 / 2.0},
            "mass_t_at_kg_m2": {s: math.pi * (r1 ** 2 - r0 ** 2) * s / 1e3 for s in (1.0, 2.0, 5.0)},
            "note": "flat annulus 16.8 m forward of the canon fusion core; the 5.7 m reactor shadow shield 2 m forward of the core shadows it to r 47.9 m"}


def main():
    res = {"meta": {"title": "T02 impact, erosion and protection estimates (research, not canon)", "k_crater_m3_J": K_CRATER,
                    "perforation_ratio": PERF_RATIO, "bumper_nominal": BUMPER, "bumper_band": BUMPER_BAND,
                    "validated_speed_limit_km_s": {"whipple_ble": 10, "dust_accelerators": 100},
                    "ratio_cruise_to_lab_speed": V / 1e5, "ratio_specific_energy_to_lab": (V / 1e5) ** 2}}
    res["grains"] = [grain(m) for m in (1e-18, 1e-16, 1e-14, 1e-12, 1e-9, 1e-6, 1e-3)]
    res["failure_energies_J"] = {kk: options(K_CRATER[kk]) for kk in K_CRATER}
    res["bumper_defeat_vs_standoff"] = [{"S_m": S, "E_nominal_J": bumper_defeat_energy(S),
                                         "E_low_J": bumper_defeat_energy(S, BUMPER_BAND["low"]), "E_high_J": bumper_defeat_energy(S, BUMPER_BAND["high"]),
                                         "grain_mass_at_cruise_kg": 2 * bumper_defeat_energy(S) / V ** 2,
                                         "grain_d_mm": grain(2 * bumper_defeat_energy(S) / V ** 2)["diameter_m"] * 1e3}
                                        for S in (0.5, 1, 2, 5, 10, 20, 50, 100, 200)]
    # exposed areas (cone 0.4 deg = aberration envelope) by orientation for each ship and option
    def A(ship, orient, opt, cone="0.4"):
        return EXP["cases"][ship][orient][opt][cone]["exposed_frontal_area_m2"]
    configs = {
        # name: (ship, env ship, {orientation: area}, description)
        "V1_as_drawn": ("V1", "FDP1_VERTEX", {"BOW_FIRST": A("V1", "BOW_FIRST", "canon_forward_shield"), "ENGINE_FIRST": A("V1", "ENGINE_FIRST", "engine_side_only")},
                        "V1 geometry, canon forward shield only, nothing on the engine side"),
        "V1_skirt": ("V1", "FDP1_VERTEX", {"BOW_FIRST": A("V1", "BOW_FIRST", "canon_forward_shield"), "ENGINE_FIRST": A("V1", "ENGINE_FIRST", "with_skirt")},
                     "V1 with the shadow-cone skirt (engine-first residual = bore-visible engine hardware)"),
        "V0_as_drawn": ("V0", "FDP1_VERTEX", {"BOW_FIRST": A("V0", "BOW_FIRST", "canon_forward_shield"), "ENGINE_FIRST": A("V0", "ENGINE_FIRST", "engine_side_only")}, "FDP-1 as drawn"),
        "CANON_as_drawn": ("CANON", "CANON", {"BOW_FIRST": A("CANON", "BOW_FIRST", "canon_forward_shield"), "ENGINE_FIRST": A("CANON", "ENGINE_FIRST", "engine_side_only")}, "canon four-nozzle ship"),
        "CANON_skirt": ("CANON", "CANON", {"BOW_FIRST": A("CANON", "BOW_FIRST", "canon_forward_shield"), "ENGINE_FIRST": A("CANON", "ENGINE_FIRST", "with_skirt")}, "canon ship with the flat aft skirt"),
    }
    res["hits"] = {}
    for name, (ship, env_ship, areas, desc) in configs.items():
        legs = ENV["ships"][env_ship]
        res["hits"][name] = {"description": desc, "areas_m2": areas, "cases": {}}
        for case in CASES:
            rows = hits_table(name, legs, areas, case, K_CRATER["NOMINAL"])
            res["hits"][name]["cases"][case] = {"legs": rows,
                                                "total": {k: survival(rows, k) for k in options(K_CRATER["NOMINAL"])},
                                                "standoff_for_0p1_failures_m": required_standoff(legs, areas, case),
                                                "standoff_engine_first_only_m": required_standoff(legs, {"BOW_FIRST": 0.0, "ENGINE_FIRST": areas["ENGINE_FIRST"]}, case),
                                                "standoff_bow_first_only_m": required_standoff(legs, {"BOW_FIRST": areas["BOW_FIRST"], "ENGINE_FIRST": 0.0}, case)}
    # the forward shield seen from behind during braking (canon ship): aft face of the Brow
    # the canon Brow facing (bow-first): grains beyond the 2 m disruptor stand-off and beyond 10 m
    brow = 6361.7
    res["brow_bow_first"] = {}
    for env_ship in ("CANON", "FDP1_VERTEX"):
        legs = [l for l in ENV["ships"][env_ship] if l["orientation"] == "BOW_FIRST"]
        res["brow_bow_first"][env_ship] = {case: {"beyond_disruptor_2m": sum(brow * interp_col(leg_colE(l, case), bumper_defeat_energy(2.0)) for l in legs),
                                                  "beyond_10m": sum(brow * interp_col(leg_colE(l, case), bumper_defeat_energy(10.0)) for l in legs),
                                                  "beyond_1MJ": sum(brow * interp_col(leg_colE(l, case), 1e6) for l in legs),
                                                  "beyond_100MJ": sum(brow * interp_col(leg_colE(l, case), 1e8) for l in legs)} for case in CASES}
    res["forward_shield_aft_face"] = {s: EXP["cases"][s]["ENGINE_FIRST"]["engine_side_only"]["0.4"].get("forward_shield_parts_exposed_frontal_m2")
                                      for s in ("V0", "V1", "CANON")}
    res["erosion"] = {s: {c: erosion(ENV["ships"][s], c) for c in CASES} for s in ENV["ships"]}
    res["gas"] = gas_physics()
    res["detection"] = detection()
    res["plume"] = plume()
    res["skirt"] = {g: skirt_geometry(g) for g in ("V0", "V1", "V2")}
    res["canon_skirt"] = canon_skirt()
    json.dump(res, open(OUT, "w"), indent=1)
    return res


if __name__ == "__main__":
    r = main()
    print("failure energies (NOMINAL k):", {k: f"{v:.3g}" for k, v in r["failure_energies_J"]["NOMINAL"].items()})
    for name, h in r["hits"].items():
        for case in CASES:
            t = h["cases"][case]["total"]
            print(f"{name:15s} {case:8s} " + "  ".join(f"{k}: {v['expected_failures']:9.3g}" for k, v in t.items()))
    print("skirt V1:", {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r["skirt"]["V1"].items() if k != "areal_density_options"})
