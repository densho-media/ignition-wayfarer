"""Validate FDP-1 Spatial Systems V2 without Blender and write VALIDATION_V2.md.

    python3 lab/problems/fdp1-requirements/check_v2.py [--regen]

--regen re-runs export_geometry.py into a temporary file and checks that it reproduces data/ship_geometry.json byte for
byte (needs the FDP-1 record branch fetched). Exit status 1 if any check fails.
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "fdp1diag"))
sys.modules.setdefault("bpy", types.ModuleType("bpy"))   # v2kit touches bpy only inside its functions

import v2_target as TG  # noqa: E402
from fdp1diag.model import Model  # noqa: E402
from fdp1diag.scenario import G0, SIGMA, Scenario, table  # noqa: E402

DATA = os.path.join(HERE, "data")
FILES = ["fdp1_parameters.json", "requirements.json", "scenario_inputs.json", "ship_geometry.json"]
CASES = [(None, None), (0.05, None), (0.10, 1500.0), (0.25, 2000.0), (1.00, 2500.0)]   # None = the record a0, 0.0069 g
OUT = []


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def check(group, name, ok, detail):
    OUT.append((group, name, bool(ok), detail))


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def main():
    before = {f: sha(os.path.join(DATA, f)) for f in FILES}
    M = Model()
    V = M.v
    for c in M.checks:
        check("existing", c["name"], c["ok"], c["detail"])
    SC = Scenario()
    I = SC.I
    CASES[0] = (SC.a0_base, None)
    # -- scenario inputs agree with the phase-1/2 parameter set (both copied from the same FDP-1 record)
    pairs = [("closure.departure_t", 1e3, "mass.departure"), ("closure.ve_km_s", 1e3, "prop.ve"), ("closure.eta_jet", 1, "prop.eta_jet"),
             ("closure.hot_T", 1, "rad.hot_T"), ("closure.warm_T", 1, "rad.warm_T"), ("closure.emissivity", 1, "rad.emissivity"),
             ("closure.hot_areal", 1, "rad.hot_areal"), ("closure.warm_areal", 1, "rad.warm_areal"),
             ("closure.hot_flux", 1, "rad.hot_flux"), ("closure.warm_flux", 1, "rad.warm_flux"),
             ("closure.propellant_t", 1e3, "mass.propellant"), ("closure.a0_g", 1, "prop.a0_g"), ("closure.alpha_jet", 1, "mass.alpha_jet"),
             ("wings.chord_m", 1, "rad.wing_chord"), ("wings.tip_m", 1, "rad.wing_tip_radius"), ("wings.hot_band_m", 1, "rad.hot_band"),
             ("wings.reused_hot_m2", 1, "rad.existing_hot_blades_area"), ("goal1g.max_a0_g", 1, "goal1g.max_a0_any_size_g"),
             ("goal1g.alpha_jet", 1, "goal1g.specific_mass")]
    for k, f, p in pairs:
        check("inputs", f"{k} = {p}", rel(I[k] * f, V(p)) < 1e-9, f"{I[k] * f:.6g} vs {V(p):.6g}")
    check("inputs", "heat fractions x fusion = loop totals", rel(I["closure.heat_hot"] * V("fusion.power"), V("thermal.hot_total")) < 1e-9
          and rel(I["closure.heat_warm"] * V("fusion.power"), V("thermal.warm_total")) < 1e-9, "hot and warm")
    # -- baseline reproduction
    b = SC.evaluate(SC.a0_base)
    st = b["closed"]
    for name, got, want in (("departure mass", st["departure_kg"], V("mass.departure")), ("thrust", st["thrust_N"], V("prop.thrust")),
                            ("jet power", st["jet_W"], V("prop.jet_power")), ("fusion power", st["fusion_W"], V("fusion.power")),
                            ("hot area", st["area_hot_m2"], V("rad.hot_area")), ("warm area", st["area_warm_m2"], V("rad.warm_area")),
                            ("wing tip radius", st["wings"]["tip_radius_m"], V("rad.wing_tip_radius")),
                            ("hot band", st["wings"]["hot_band_m"], V("rad.hot_band")),
                            ("end mass", st["end_kg"], V("mass.end"))):
        check("baseline", f"scenario reproduces the record {name}", rel(got, want) < 1e-6, f"{got:.6g} vs {want:.6g}")
    check("baseline", "status BASELINE and feasible", b["status"] == "BASELINE" and b["feasible"], b["status"])
    check("baseline", "ceiling 0.0106 g (baseline closure)", abs(b["ceiling_g"] - 0.0106) < 0.0002, f"{b['ceiling_g']:.5f} g")
    g1 = SC.ceiling_g(SC.warm_T, "goal_1g_variant")
    check("baseline", "goal-1g variant ceiling = record 0.011219 g", rel(g1, V("goal1g.max_a0_any_size_g")) < 1e-3, f"{g1:.6f} g")
    # -- energy accounting (power in W)
    led = sum(V(k) for k in M.doc["parameters"] if k.startswith("ledger."))
    check("energy", "ledger sums to the fusion power", rel(led, V("fusion.power")) < 1e-9, f"{led:.6g} W")
    check("energy", "thrust = 2 P_jet / v_e (jet power, not fusion power)", rel(2 * V("prop.jet_power") / V("prop.ve"), V("prop.thrust")) < 1e-9,
          f"{2 * V('prop.jet_power') / V('prop.ve') / 1e6:.4f} MN")
    check("energy", "jet + uncollimated + rest = fusion", V("ledger.jet") + V("ledger.plume_to_space") < V("fusion.power"),
          f"jet {V('ledger.jet') / 1e12:.2f} TW, uncollimated {V('ledger.plume_to_space') / 1e12:.2f} TW")
    hot = sum(V(k) for k in M.doc["parameters"] if k.startswith("hot."))
    warm = sum(V(k) for k in M.doc["parameters"] if k.startswith("warm."))
    check("energy", "hot deposits sum to the hot loop", rel(hot, V("thermal.hot_total")) < 1e-9, f"{hot / 1e9:.2f} GW")
    check("energy", "warm deposits sum to the warm loop", rel(warm, V("thermal.warm_total")) < 1e-9, f"{warm / 1e9:.2f} GW")
    # -- mass overlays
    items = [k for k in M.doc["parameters"] if k.startswith("mass.") and " " in k]
    ms = sum(V(k) for k in items)
    check("mass", f"{len(items)} budget items sum to departure", rel(ms, V("mass.departure")) < 1e-8, f"{ms / 1e3:,.1f} t")
    src = open(os.path.join(HERE, "build_v2.py")).read()
    missing = [k[5:] for k in items if V(k) > 0 and f'"{k[5:]}"' not in src]
    check("mass", "every non-zero budget item has a cube on its hardware", not missing, ", ".join(missing) or "all placed")
    # -- encodings
    P0, M0 = V("fusion.power"), V("mass.departure")
    check("encoding", "sphere volume proportional to power", rel((TG.sphere_r(8 * P0, P0) / TG.sphere_r(P0, P0)) ** 3, 8) < 1e-12, "8x power -> 8x volume")
    r1, _ = TG.tube_r(P0, P0)
    r4, _ = TG.tube_r(4 * P0, P0)
    check("encoding", "tube cross-section proportional to power", rel((r4 / r1) ** 2, 4) < 1e-12, "4x power -> 4x area")
    check("encoding", "thin tubes flagged", TG.tube_r(1e6, P0)[1] and TG.tube_r(1e6, P0)[0] == TG.ENC["TUBE_MIN"], f"min {TG.ENC['TUBE_MIN']} m")
    check("encoding", "arrow length proportional to force", abs(V("prop.thrust") * TG.ENC["M_PER_N"] - 280.77) < 0.1,
          f"1.40 MN = {V('prop.thrust') * TG.ENC['M_PER_N']:.1f} m")
    check("encoding", "cube volume proportional to mass", rel((TG.cube_side(2 * M0, M0) / TG.cube_side(M0, M0)) ** 3, 2) < 1e-12, "2x mass -> 2x volume")
    # -- geometry scale (1 BU = 1 m) against the record and canon
    G = json.load(open(os.path.join(DATA, "ship_geometry.json")))
    loops = G["meta"]["nozzle_loops"]
    for i, L in enumerate(loops, 1):
        check("scale", f"nozzle loop {i} radius and station", rel(L["r"], V(f"nozzle.loop{i}_r")) < 1e-9 and rel(L["x"], V(f"nozzle.loop{i}_x")) < 1e-9,
              f"r {L['r']:.2f} m at x {L['x']:.2f} m")
    w1 = next(p for p in G["parts"] if p["name"] == "FDP1_Wing_1_Warm_Field")
    check("scale", "wing tip drawn at the record radius", abs(w1["corners"][2][1] - V("rad.wing_tip_radius")) < 1e-6, f"{w1['corners'][2][1]:.1f} m")
    area = sum(abs(p["corners"][1][0] - p["corners"][0][0]) * abs(math.hypot(*p["corners"][2][1:]) - math.hypot(*p["corners"][1][1:]))
               for p in G["parts"] if p["name"].startswith("FDP1_Wing_") and "Field" in p["name"])
    check("scale", "drawn warm planform within 1 % of the record warm area", rel(area, V("rad.warm_area")) < 0.01,
          f"{area / 1e6:.4f} vs {V('rad.warm_area') / 1e6:.4f} km2 (the 2 m root gap)")
    xs = [p.get("x0", 0) for p in G["parts"] if p["name"] == "WF_Hull_Aft_Body"] + [p.get("x1", 0) for p in G["parts"] if p["name"] == "WF_Hull_Aft_Body"]
    check("scale", "Wayfarer hull from the baseline fingerprint (metres)", xs and xs[0] < xs[1], f"hull x {xs[0]:.1f}..{xs[1]:.1f} m")
    rings = [p for p in G["parts"] if p["group"] == "habitat"]
    check("scale", "habitat rings at canon radius 30 m", all(abs(p["r1"] - V("canon.habitat_ring_radius_m")) < 0.05 for p in rings),
          ", ".join(f"{p['r1']:.2f}" for p in rings))
    # -- radiators and temperature
    eps = V("rad.emissivity")
    for loop, A, T, P in (("hot", V("rad.hot_area"), V("rad.hot_T"), V("thermal.hot_total")),
                          ("warm", V("rad.warm_area"), V("rad.warm_T"), V("thermal.warm_total"))):
        q = eps * SIGMA * 2 * A * T ** 4
        check("radiator", f"{loop}: eps sigma (2A) T^4 rejects the loop heat", rel(q, P) < 1e-6, f"{q / 1e9:.3f} vs {P / 1e9:.3f} GW")
    Ts = [800, 1000, 1200, 1500, 2000, 2500]
    areas = [SC.powers(M0, SC.a0_base, T)["area_warm_m2"] for T in Ts]
    check("temperature", "warm area falls monotonically with T (fixed power)", all(a > b for a, b in zip(areas, areas[1:])),
          " > ".join(f"{a / 1e3:,.0f}k" for a in areas) + " m2")
    check("temperature", "area ratio follows T^-4 for the bare plate", rel(SC.flux(1000) / SC.flux(500), 16) < 1e-12, "flux(1000)/flux(500) = 16")
    ceil = [SC.ceiling_g(T) for T in Ts]
    check("temperature", "ceiling rises with T but saturates (hot loop and hardware fixed)",
          all(a < b for a, b in zip(ceil, ceil[1:])) and ceil[-1] < 0.021, " < ".join(f"{c:.4f}" for c in ceil) + " g")
    r = SC.evaluate(0.1, 1500)
    check("temperature", "T above record flags P06 transport and P07 materials", {"P06", "P07"} <= {k for k, _ in r["flags"]},
          ", ".join(sorted({k for k, _ in r["flags"]})))
    # -- feedback and infeasible marking
    for a, T in CASES + [(0.009, None), (0.0105, None)]:
        e = SC.evaluate(a, T)
        ok = (e["loop_gain"] < 1) == e["feasible"] == (e["status"] != "INFEASIBLE") == (e["closed"] is not None)
        if e["closed"]:
            m0 = e["closed"]["departure_kg"]
            ok = ok and rel(m0, SC.RN * (SC.m_fix + SC.alpha_jet(e["inputs"]["warm_T_K"]) * e["closed"]["jet_W"] + SC.c * e["closed"]["propellant_kg"])) < 1e-9
        else:
            fb = e["feedback_departure_kg"]
            ok = ok and all(b > a for a, b in zip(fb, fb[1:])) and any(k == "INFEASIBLE" for k, _ in e["flags"])
        check("feedback", f"{a:.2g} g, {('record T' if T is None else f'{T:.0f} K')}: gain, closure and marking consistent", ok,
              f"{e['status']}, gain {e['loop_gain']:.3f}")
    # -- reproducibility and untouched inputs
    e1, e2 = SC.evaluate(0.25, 2000), Scenario().evaluate(0.25, 2000)
    check("reproducible", "evaluate is deterministic", json.dumps(e1, sort_keys=True) == json.dumps(e2, sort_keys=True), "two runs identical")
    if "--regen" in sys.argv:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "g.json")
            subprocess.run([sys.executable, os.path.join(HERE, "export_geometry.py")], env={**os.environ, "FDP1_GEOMETRY_OUT": out},
                           check=True, capture_output=True)
            check("reproducible", "export_geometry.py regenerates ship_geometry.json byte for byte", sha(out) == before["ship_geometry.json"],
                  sha(out)[:12])
    after = {f: sha(os.path.join(DATA, f)) for f in FILES}
    check("baseline files", "data files unchanged by the scenario runs", before == after, ", ".join(f"{k} {v[:10]}" for k, v in after.items()))
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    diff = subprocess.run(["git", "diff", "--stat", "HEAD", "--", "lab/problems/fdp1-requirements/data/fdp1_parameters.json",
                           "lab/problems/fdp1-requirements/data/requirements.json", "data/", "src/"],
                          cwd=root, capture_output=True, text=True).stdout.strip()
    check("baseline files", "Wayfarer model, canon data and the phase-1/2 parameters untouched (git)", diff == "", diff or "no diff")
    return SC, before


def report(SC, hashes):
    n_ok = sum(o[2] for o in OUT)
    L = ["# FDP-1 Spatial Systems V2: validation", "",
         f"`python3 lab/problems/fdp1-requirements/check_v2.py` — **{n_ok}/{len(OUT)} checks pass.** Written by the script; do not edit.", "",
         "| group | check | result | detail |", "| --- | --- | --- | --- |"]
    for g, n, ok, d in OUT:
        L.append(f"| {g} | {n} | {'PASS' if ok else '**FAIL**'} | {d} |")
    L += ["", "## The five test configurations", "",
          "Scaling: baseline closure (today's FDP-1 alpha). Values for an infeasible target are the lower bound at today's "
          "20,760 t departure mass: no departure mass closes, so the real requirement is larger.", "",
          "| a (g) | warm loop | status | ceiling (g) | loop gain | basis | fusion (TW) | thrust (MN) | heat (GW) | radiators (km²) | wing tip (km) | engine (t) | flags |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in table(SC, CASES):
        L.append(f"| {r['accel_g']:.2g} | {r['warm_T_K']:.0f} K | {r['status']} | {r['ceiling_g']:.4f} | {r['loop_gain']:.2f} | {r['basis']} | "
                 f"{r['fusion_TW']:,.1f} | {r['thrust_MN']:,.2f} | {r['heat_GW']:,.0f} | {r['area_km2']:,.2f} | {r['tip_km']:,.2f} | "
                 f"{r['power_scaled_t']:,.0f} | {', '.join(dict.fromkeys(r['flags']))} |")
    L += ["", "The ceiling is a property of today's scaling assumptions (drive and radiator mass per W, exhaust velocity, tank fraction), "
          "not a physical limit. The record's own goal-1g study uses a slightly lower specific mass and reaches 0.0112 g; "
          "the panel offers it as the second scaling option.", "",
          "## Input hashes (sha256)", ""] + [f"- `data/{k}` {v}" for k, v in hashes.items()]
    open(os.path.join(HERE, "VALIDATION_V2.md"), "w").write("\n".join(L) + "\n")
    return n_ok


if __name__ == "__main__":
    sc, h = main()
    n = report(sc, h)
    for g, nm, ok, d in OUT:
        if not ok:
            print("FAIL", g, nm, d)
    print(f"{n}/{len(OUT)} checks pass; wrote VALIDATION_V2.md")
    sys.exit(0 if n == len(OUT) else 1)
