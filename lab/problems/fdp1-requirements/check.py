"""Validate the FDP-1 requirements-map inputs without Blender, and write the requirements register.

    python3 lab/problems/fdp1-requirements/check.py            # checks + record comparison + register
    python3 lab/problems/fdp1-requirements/check.py --sync     # also copy changed record values into the JSON

1. Runs the model checks (dimensions, mass, energy, performance) in fdp1diag/model.py.
2. Compares every parameter that has a record_path with the FDP-1 record on branch claude/project-thread-8e13aa
   (git show, read-only). With --sync it writes the record's current values into data/fdp1_parameters.json.
3. Compares the owner brief's quoted figures with the derived values.
4. Writes results/derived.json and REQUIREMENTS.md (the register linking problems to scene objects).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fdp1diag.model import PARAMS, Model, fmt_power  # noqa: E402

BRANCH = "origin/claude/project-thread-8e13aa"
RECORD = "lab/variants/fdp1/results/fdp1-v1/"

# Figures quoted in the owner brief (2026-11-04) and the derived value each should match, with a rounding tolerance.
BRIEF = [
    ("fusion power 17.3 TW", 17.3e12, "fusion.power", 0.005),
    ("effective exhaust velocity ~19.2e6 m/s", 19.2e6, "prop.ve", 0.005),
    ("directed jet power ~13.5 TW", 13.5e12, "calc.jet_power", 0.005),
    ("energy not in jet ~3.8 TW", 3.8e12, "calc.non_jet_power", 0.01),
    ("departure mass 20,760 t", 20760e3, "mass.departure", 0.0005),
    ("propellant ~13,117 t", 13117e3, "mass.propellant", 0.0005),
    ("remaining dry mass ~7,643 t", 7643e3, "mass.dry", 0.0005),
    ("initial acceleration 0.0069 g", 0.0069, "prop.a0_g", 0.01),
    ("maximum acceleration ~0.019 g", 0.019, "calc.burn4.a_end_g", 0.03),
    ("initial thrust ~1.4 MN", 1.4e6, "calc.thrust_ma", 0.01),
    ("1 g thrust ~204 MN", 204e6, "calc.1g.thrust", 0.005),
    ("1 g fusion power ~2,507 TW", 2507e12, "calc.1g.fusion_power", 0.001),
    ("power increase ~145x", 145.0, "calc.1g.factor", 0.005),
    ("high-temperature heat ~77 GW", 77e9, "thermal.hot_total", 0.01),
    ("intermediate heat ~24 GW", 24e9, "thermal.warm_total", 0.02),
    ("combined heat ~101 GW", 101e9, "calc.heat_total", 0.01),
    ("warm radiator area 1.84 km2", 1.84e6, "rad.warm_area", 0.005),
    ("wing tip radius 3.57 km", 3.57e3, "rad.wing_tip_radius", 0.002),
    ("total ideal dv ~0.064 c", 0.064, "calc.dv_total_c", 0.002),
    ("engine operating time ~5.69 y", 5.69, "mission.engine_years", 0.002),
    ("minimum round trip ~6.35 y", 6.35, "mission.min_round_trip_years", 0.002),
    ("1 g: ~5.66 d per 0.016 c burn", 5.66, "calc.1g.burn_days", 0.002),
    ("1 g: ~22.6 d cumulative", 22.6, "calc.1g.total_days", 0.002),
    ("target gain 3,000", 3000.0, "fusion.target_gain", 1e-9),
]


def record_value(path, cache):
    f, p = path.split(":", 1)
    if f not in cache:
        try:
            out = subprocess.run(["git", "show", f"{BRANCH}:{RECORD}{f}.json"], cwd=HERE, capture_output=True,
                                 text=True, check=True).stdout
            cache[f] = json.loads(out)
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
            cache[f] = None
    d = cache[f]
    if d is None:
        return None
    for k in p.split("."):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def main():
    sync = "--sync" in sys.argv
    with open(PARAMS) as f:
        doc = json.load(f)
    cache, diffs, missing = {}, [], False
    for key, e in doc["parameters"].items():
        if "record_path" not in e:
            continue
        rv = record_value(e["record_path"], cache)
        if rv is None:
            missing = True
            continue
        rv = rv * e.get("record_scale", 1.0)
        if rv != e["value"]:
            diffs.append((key, e["value"], rv))
            if sync:
                e["value"] = rv
    if missing:
        print(f"record: {BRANCH} not available (git fetch origin claude/project-thread-8e13aa); comparison skipped")
    else:
        print(f"record: {len(diffs)} parameter(s) differ from {BRANCH}")
        for k, a, b in diffs:
            print(f"  {k}: file {a!r} record {b!r}")
    if sync and diffs:
        with open(PARAMS, "w") as f:
            json.dump(doc, f, indent=1)
        print("  synced into", PARAMS)

    m = Model()
    fails = 0
    for c in m.checks:
        print(("PASS " if c["ok"] else "FAIL ") + f"[{c['kind']}] {c['name']}: {c['detail']}")
        fails += not c["ok"]
    print("brief figures against the derived values:")
    brief_rows = []
    for label, q, key, tol in BRIEF:
        x = m.v(key)
        rel = abs(x - q) / abs(q)
        ok = rel <= tol
        brief_rows.append({"brief": label, "quoted": q, "key": key, "derived": x, "rel_diff": rel, "within_rounding": ok})
        print(f"  {'ok ' if ok else 'DIFF'} {label}: derived {x:.6g} ({key}), {rel * 100:.2f} %")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "derived.json"), "w") as f:
        json.dump({"checks": m.checks, "derived": m.d, "accel_rows": m.accel_rows, "temp_rows": m.temp_rows,
                   "brief_comparison": brief_rows, "record_diffs": [list(d) for d in diffs]}, f, indent=1, default=str)
    write_register(m)
    return 1 if fails else 0


def write_register(m):
    links = {
        "P01": ["OV_burn", "OV_burn_halo", "FE_ign", "FE_fusion_bar", "GP_bar_*"],
        "P02": ["OV_driver_0", "OV_driver_1", "OV_beam_*", "MG_rc_*", "MG_warm_1"],
        "P03": ["OV_thrust", "RK_*", "MB_*", "MD_*", "GP_*", "GT_*"],
        "P04": ["OV_loop_1..3", "OV_loop_*_lattice*", "OV_plume", "OV_jet_arrow", "SP_r3_bar", "SP_fn0"],
        "P05": ["OV_shield", "OV_ray_*", "GE_*", "MG_rad_*", "SP_r1_bar", "SP_r2_bar", "SP_fn1"],
        "P06": ["OV_manifold_hot", "OV_manifold_warm", "MG_hot_*", "MG_warm_*", "SP_r4_bar", "SP_fn2"],
        "P07": ["OV_wing_hot_*", "OV_wing_warm_*", "TA_sq_800..2500", "SC_*", "SP_fn3"],
        "P08": ["OV_tank_0..3", "OV_pellets", "MB_propellant (four burns)", "MP_fuel_*", "RK_mdot"],
        "P09": ["OV_struts_top", "OV_struts_bot", "OV_spine", "SC_warm_*"],
        "P10": ["MP_*", "RK_dv", "RK_curve", "RK_pt_*"],
    }
    lines = ["# FDP-1 requirements register", "",
             "Generated by `check.py` from `data/requirements.json` and `data/fdp1_parameters.json`. Each problem lists the",
             "scene objects that draw it (names in `FDP-1_Engineering_Requirements.blend`; `*` = a family). Every object",
             "also carries a `req_ids` custom property where it feeds a problem, and the yellow `TAG_Pxx_*` objects mark it",
             "in the schematic and the analysis panels.", "",
             f"Record: {m.doc['meta']['record']}.", ""]
    for rq in m.requirements:
        lines += [f"## {rq['id']} {rq['title']}", "", m.render(rq["description"]), "",
                  f"- **Status:** {rq['status']} · **Classification:** {', '.join(rq['classification'])}",
                  f"- **Depends on:** {', '.join(rq['depends']) or 'none'}",
                  f"- **Parameters:** {', '.join('`' + p + '`' for p in rq['params'])}",
                  f"- **Current:** {' · '.join(m.render(c) for c in rq['current'])}",
                  f"- **Target / requirement:** {m.render(rq['target'])}",
                  f"- **Gap:** {m.render(rq['gap'])}",
                  f"- **Card:** `REQ_{rq['id']}_card` (panel E) · **Tags:** `TAG_{rq['id']}_*`",
                  f"- **Drawn by:** {', '.join('`' + o + '`' for o in links.get(rq['id'], []))}", ""]
    with open(os.path.join(HERE, "REQUIREMENTS.md"), "w") as f:
        f.write("\n".join(lines))
    print("wrote REQUIREMENTS.md")


if __name__ == "__main__":
    sys.exit(main())
