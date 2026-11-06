"""Validate FDP-1 Spatial Systems V3 without Blender and write VALIDATION_V3.md.

    python3 lab/problems/fdp1-requirements/check_v3.py [--regen]

Runs every V2 check first (check_v2.main, unchanged), then the P11 protection tests the V3 brief asks for:
geometry (synthetic parts against a synthetic shield), scaling, protection logic and regression. Exit status 1 if any
check fails.
"""
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "fdp1diag"))

import check_v2 as C2  # noqa: E402  (also stubs bpy and sets the import paths)
from protection import Circle, Polygon, Protection, classify, engine_envelope, UNRESOLVED_CATEGORIES  # noqa: E402
from scenario_v3 import ScenarioV3, STATUSES  # noqa: E402

DATA = os.path.join(HERE, "data")
V3_FILES = ["protection_inputs.json", "requirements_p11.json"]
check = C2.check


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


# ---- a synthetic world: shield r 10 m at x 0..1, particles from +X ----------------------------------------------
def synth(parts):
    shield = {"name": "TEST_Shield", "group": "bow", "func": "SHIELD", "shape": "ring", "r0": 0.0, "r1": 10.0, "x0": 0.0, "x1": 1.0}
    return Protection(geo={"parts": [shield] + parts, "meta": {}}, inputs={})


def box(name, centre, size, roll=0.0, group="fdp1_structure"):
    return {"name": name, "group": group, "func": "TEST", "shape": "box", "centre": list(centre), "size": list(size), "roll": roll}


def geometry_tests():
    G = "P11 geometry"
    P = synth([box("covered", (-50, 0, 0), (2, 4, 4)), box("partial", (-50, 10, 0), (2, 4, 4)), box("exposed", (-50, 20, 0), (2, 4, 4)),
               {"name": "boundary", "group": "fdp1_structure", "func": "TEST", "shape": "ring", "r0": 0.0, "r1": 9.5, "x0": -60, "x1": -59},
               box("corner", (-50, 7, 7), (2, 4, 4)), box("wide", (-50, 0, 0), (2, 30, 2)), box("wide_rolled", (-50, 0, 0), (2, 30, 2), roll=90.0),
               box("offset_wide", (-50, 4, -3), (2, 30, 2), roll=30.0)])
    parts = {p["name"]: p for p in P.geo["parts"]}
    st = {n: P.assess_part(parts[n], h=0.1) for n in ("covered", "partial", "exposed", "boundary", "wide", "wide_rolled", "offset_wide")}
    check(G, "shield read from the shield parts (r 10 m, aft plane x 0)", P.shield["radius_m"] == 10 and P.x_s == 0.0, f"r {P.shield['radius_m']}, x_s {P.x_s}")
    a, b = P.clearance(-1000, 5, 0), P.clearance(-1, 5, 0)
    check(G, "aligned stream: clearance independent of distance behind the shield", abs(a - b) < 1e-12 and abs(a - 5) < 1e-12, f"{a:.6f} vs {b:.6f}")
    th = 2.0
    c = P.clearance(-100, 5, 0, th)
    check(G, "cone: clearance shrinks by L·tanθ", abs(c - (5 - 100 * math.tan(math.radians(th)))) < 1e-12, f"{c:.6f} m at L 100 m, θ {th}°")
    check(G, "fully covered component", st["covered"]["status"] == "COVERED" and st["covered"]["exposed_frontal_area_m2"] == 0,
          f"min clearance {st['covered']['min_clearance_m']:.3f} m")
    pa = st["partial"]
    check(G, "partially exposed component: status PARTIAL, 0 < exposed < total", pa["status"] == "PARTIAL" and 0 < pa["exposed_frontal_area_m2"] < pa["frontal_area_m2"],
          f"{pa['exposed_frontal_area_m2']:.2f} of {pa['frontal_area_m2']:.2f} m²")
    # analytic exposed area of the partial box: y in [8,12], z in [-2,2], outside the r 10 circle
    ex = sum(max(0.0, 12 - max(8.0, math.sqrt(max(0.0, 100 - z * z)))) * 0.001 for z in [(-2 + 0.001 * (k + 0.5)) for k in range(4000)])
    check(G, "partial exposed area matches the analytic value (±3 %)", C2.rel(pa["exposed_frontal_area_m2"], ex) < 0.03,
          f"{pa['exposed_frontal_area_m2']:.3f} vs {ex:.3f} m²")
    e = st["exposed"]
    check(G, "fully exposed component", e["status"] == "EXPOSED" and C2.rel(e["exposed_frontal_area_m2"], 16) < 1e-9, f"{e['exposed_frontal_area_m2']:.2f} m², protrusion {e['protrusion_m']:.2f} m")
    check(G, "protrusion = farthest point outside the silhouette", abs(e["protrusion_m"] - (math.hypot(22, 2) - 10)) < 1e-9, f"{e['protrusion_m']:.4f} m")
    bd = st["boundary"]
    check(G, "component at the boundary (clearance inside the uncertainty band)", bd["status"] == "AT_BOUNDARY", f"min clearance {bd['min_clearance_m']:.3f} m")
    w, wr = st["wide"], st["wide_rolled"]
    exw = 2 * sum(max(0.0, 15 - math.sqrt(max(0.0, 100 - z * z))) * 0.001 for z in [(-1 + 0.001 * (k + 0.5)) for k in range(2000)])
    check(G, "non-axisymmetric component: exposed area of a 30 × 2 m plate (±3 %)", C2.rel(w["exposed_frontal_area_m2"], exw) < 0.03,
          f"{w['exposed_frontal_area_m2']:.3f} vs {exw:.3f} m²")
    check(G, "rolling the plate 90° about X gives the same exposure (circle symmetry)", C2.rel(wr["exposed_frontal_area_m2"], w["exposed_frontal_area_m2"]) < 1e-6,
          f"{wr['exposed_frontal_area_m2']:.3f} m²")
    o = st["offset_wide"]
    check(G, "off-axis rolled plate is worse than the centred one", o["exposed_frontal_area_m2"] > w["exposed_frontal_area_m2"] and o["status"] == "PARTIAL",
          f"{o['exposed_frontal_area_m2']:.2f} m²")
    sq = Polygon([(-10, -10), (10, -10), (10, 10), (-10, 10)])
    check(G, "noncircular shield: polygon area", abs(sq.area() - 400) < 1e-9, f"{sq.area():.1f} m²")
    d1, d2 = sq.inside_distance(9.5, 9.5), Circle(10).inside_distance(9.5, 9.5)
    check(G, "noncircular shield: a corner point is covered by the square, not by the r 10 circle", abs(d1 - 0.5) < 1e-12 and d2 < 0, f"square {d1:+.3f} m, circle {d2:+.3f} m")
    pc, ps = P.assess_part(parts["corner"], h=0.1), P.assess_part(parts["corner"], h=0.1, sil=sq)
    check(G, "noncircular shield: a corner box exposed by the r 10 circle is covered by the 20 m square", pc["status"] == "PARTIAL" and ps["status"] in ("COVERED", "AT_BOUNDARY") and ps["exposed_frontal_area_m2"] == 0,
          f"{ps['status']}, min clearance {ps['min_clearance_m']:.3f} m")
    m0, m3 = P.assess_part(parts["covered"], h=0.1), P.assess_part(parts["covered"], margin=3.0, h=0.1)
    check(G, "safety margin lowers every clearance by exactly the margin", abs(m0["min_clearance_m"] - m3["min_clearance_m"] - 3.0) < 1e-12,
          f"{m0['min_clearance_m']:.3f} → {m3['min_clearance_m']:.3f} m")
    m8 = P.assess_part(parts["covered"], margin=8.0, h=0.1)
    check(G, "a large margin turns a covered part into an exposed one", m8["status"] in ("PARTIAL", "EXPOSED"), m8["status"])
    pts = [(x, y, z) for n in ("partial", "exposed", "wide") for x, y, z, _ in P.part_samples(parts[n], 0.1)]
    Rq = P.required_radius(pts, 1.0, 2.0)
    worst = min(P.clearance(x, y, z, 1.0, 2.0, sil=Circle(Rq)) for x, y, z in pts)
    check(G, "required radius covers every sample with zero slack", abs(worst) < 1e-9, f"R {Rq:.3f} m, worst clearance {worst:.2e} m")


def scaling_tests(S3, base):
    G = "P11 scaling"
    P0 = base["protection"]
    r = S3.evaluate(shield="custom", shield_radius=90.0)
    check(G, "shield area ∝ R² (r 90 m = 4 × the canon r 45 m area)", C2.rel(r["protection"]["shield_area_m2"] / P0["shield_area_baseline_m2"], 4.0) < 1e-12,
          f"{r['protection']['shield_area_m2']:,.0f} m²")
    sig = 50.0
    r = S3.evaluate(shield="custom", shield_radius=60.0, areal_density=sig)
    dA = math.pi * (60 ** 2 - 45 ** 2)
    check(G, "added shield mass = areal density × added area", C2.rel(r["protection"]["shield_added_mass_kg"], sig * dA) < 1e-12,
          f"{r['protection']['shield_added_mass_kg'] / 1e3:,.1f} t at {sig:g} kg/m² (test value)")
    v2, v3 = r["v2"]["closed"], r["v3"]["closed"]
    ok = v2 and v3 and v3["thrust_N"] > v2["thrust_N"] and v3["fusion_W"] > v2["fusion_W"]
    check(G, "added mass raises the thrust and fusion power needed at the same acceleration", ok,
          f"thrust {v2['thrust_N'] / 1e6:.3f} → {v3['thrust_N'] / 1e6:.3f} MN" if ok else "no closure")
    gain = (v3["departure_kg"] - v2["departure_kg"]) / r["protection"]["shield_added_mass_kg"] if ok else 0
    check(G, "added mass propagates through the power-to-mass feedback (departure grows by more than the added mass)", gain > 1,
          f"departure +{(v3['departure_kg'] - v2['departure_kg']) / 1e3:,.1f} t for +{r['protection']['shield_added_mass_kg'] / 1e3:,.1f} t (×{gain:.2f})")
    r0 = S3.evaluate(a_g=1.0, T=2500.0)
    check(G, "engine geometry does not follow power or mass without a packaging law", abs(r0["protection"]["engine_max_radius_m"] - P0["engine_max_radius_m"]) < 1e-9,
          f"r {r0['protection']['engine_max_radius_m']:.2f} m at 1 g")
    r1 = S3.evaluate(a_g=0.05, engine_exp=1 / 3)
    k = r1["protection"]["engine_radial_scale"]
    check(G, "a chosen packaging law scales the engine radially and is listed as an assumption",
          k > 1 and abs(r1["protection"]["engine_max_radius_m"] - k * P0["engine_max_radius_m"]) < 1e-9 and any("P^" in a for a in r1["assumptions"]),
          f"×{k:.3f} → r {r1['protection']['engine_max_radius_m']:.1f} m")


def protection_tests(S3, base):
    G = "P11 protection"
    P0 = base["protection"]
    rows = P0["rows"]
    check(G, "radiators are not mixed into the critical-part assessment", all(r["class"] != "RADIATOR" for r in rows) and P0["radiators"]
          and all(classify({"group": "x", "name": r["name"]}) == "RADIATOR" or r["name"].startswith("WF_") for r in P0["radiators"]),
          f"{len(rows)} assessed parts, {len(P0['radiators'])} radiator panels")
    r = S3.evaluate(shield="required")
    p = r["protection"]
    check(G, "no areal density: shield-mass effect UNRESOLVED, no mass invented", p["shield_mass_effect"] == "UNRESOLVED" and p["shield_added_mass_kg"] is None
          and r["v3"] is r["v2"] and r["constraints"]["Mass"][0] in ("UNRESOLVED", "FAIL"), f"{p['shield_mass_effect']}; Mass {r['constraints']['Mass'][0]}")
    r2 = S3.evaluate(shield="required", areal_density=50.0)
    check(G, "a supplied areal density is labelled ASSUMPTION", r2["protection"]["shield_mass_effect"] == "ASSUMPTION" and any("areal density" in a for a in r2["assumptions"]),
          r2["protection"]["shield_mass_effect"])
    check(G, "enlarged shield covers every critical part geometrically", r["protection"]["summary"]["critical_exposed"] == 0,
          f"r {p['shield_radius_m']:.2f} m: {r['protection']['summary']['critical_exposed']} exposed")
    check(G, "covered ≠ safe: Geometry is UNRESOLVED (not PASS) when every part is covered", r["constraints"]["Geometry"][0] == "UNRESOLVED", r["constraints"]["Geometry"][1])
    cats = UNRESOLVED_CATEGORIES
    check(G, "six protection categories; only geometric coverage is computed", len(cats) == 6 and cats[0][1] == "computed here"
          and all(c[1].startswith("UNRESOLVED") for c in cats[1:]), ", ".join(c[0] for c in cats))
    seen_pass, bad = set(), []
    for kw in (dict(), dict(shield="required"), dict(shield="required", areal_density=50.0), dict(a_g=0.05), dict(a_g=1.0, T=2500.0),
               dict(cone_deg=5.0), dict(margin=15.0)):
        rr = S3.evaluate(**kw)
        for fam, (s, _) in rr["constraints"].items():
            if s not in STATUSES:
                bad.append((fam, s))
            if s == "PASS":
                seen_pass.add(fam)
        if rr["physically_validated"]:
            bad.append(("physically_validated", True))
    check(G, "no false PASS: Geometry, Radiation, Structures, Thermal never PASS; physically validated never claimed",
          not bad and not (seen_pass & {"Geometry", "Radiation", "Structures", "Thermal"}), f"PASS only for {sorted(seen_pass) or 'none'}; {bad or 'statuses valid'}")
    check(G, "the ghost shield never modifies the canonical shield", S3.pr.sil.R == 45.0 and S3.pr.shield["radius_m"] == 45.0 and S3.R0 == 45.0, f"r {S3.pr.sil.R} m")
    c5 = S3.evaluate(cone_deg=5.0)["protection"]["summary"]
    c0 = P0["summary"]
    check(G, "a wider arrival cone never protects more", c5["critical_exposed"] >= c0["critical_exposed"] and c5["max_protrusion_m"] >= c0["max_protrusion_m"],
          f"{c0['critical_exposed']} → {c5['critical_exposed']} parts, {c0['max_protrusion_m']:.1f} → {c5['max_protrusion_m']:.1f} m")


def regression_tests(S3, base, before):
    G = "P11 regression"
    P = base["protection"]
    eng = engine_envelope(S3.pr.geo)
    check(G, "baseline shield r 45 m (90 m canon), aft plane x 260.55 m", P["shield_radius_m"] == 45.0 and abs(P["x_shield_m"] - 260.55) < 1e-3,
          f"r {P['shield_radius_m']} m, x {P['x_shield_m']:.2f} m")
    check(G, "engine maximum radius 112.55 m, set by loop 3", abs(eng["max_radius_m"] - 112.5467) < 1e-3 and "Loop_3" in eng["set_by"],
          f"{eng['max_radius_m']:.3f} m ({eng['set_by']})")
    check(G, "baseline violation reported, not hidden: engine clearance −67.5 m, Geometry FAIL",
          P["engine_clearance_m"] < 0 and base["constraints"]["Geometry"][0] == "FAIL", f"{P['engine_clearance_m']:+.2f} m")
    rs = P["radiator_summary"]
    check(G, "radiators ~97.9 % of planform outside the envelope", abs(rs["fraction_exposed"] - 0.979) < 0.002, f"{rs['fraction_exposed'] * 100:.2f} %")
    v2b = C2.Scenario().evaluate(C2.Scenario().a0_base)["closed"]
    check(G, "the V3 scenario at the record reproduces the V2 baseline closure", base["v3"]["closed"] and C2.rel(base["v3"]["closed"]["departure_kg"], v2b["departure_kg"]) < 1e-12,
          f"{base['v3']['closed']['departure_kg'] / 1e3:,.1f} t")
    req = json.load(open(os.path.join(DATA, "requirements.json")))
    ids = [r["id"] for r in req["requirements"]]
    p11 = json.load(open(os.path.join(DATA, "requirements_p11.json")))["requirements"][0]
    check(G, "P11 kept separate and UNRESOLVED; requirements.json still P01–P10", ids == [f"P{i:02d}" for i in range(1, 11)] and p11["id"] == "P11"
          and p11["status"] == "unresolved", f"{ids[0]}–{ids[-1]} + {p11['id']} ({p11['status']})")
    after = {f: sha(os.path.join(DATA, f)) for f in V3_FILES}
    check(G, "V3 scenario inputs unchanged by the checks", after == before, "hashes stable")


def report(base, hashes):
    OUT = C2.OUT
    n_ok = sum(o[2] for o in OUT)
    P = base["protection"]
    L = ["# FDP-1 Spatial Systems V3: validation", "",
         f"`python3 lab/problems/fdp1-requirements/check_v3.py --regen` — **{n_ok}/{len(OUT)} checks pass** "
         f"({sum(1 for o in OUT if not o[0].startswith('P11'))} V2 checks, {sum(1 for o in OUT if o[0].startswith('P11'))} P11 checks). "
         "Written by the script; do not edit.", "",
         "Geometric coverage is the only protection category computed. Stopping, ejecta, penetration, radiation/shock transmission "
         "and survival probability are UNRESOLVED; a covered part is not a safe part.", "",
         "| group | check | result | detail |", "| --- | --- | --- | --- |"]
    for g, n, ok, d in OUT:
        L.append(f"| {g} | {n} | {'PASS' if ok else '**FAIL**'} | {d} |")
    L += ["", "## P11 baseline (aligned stream, margin 0, canon 90 m shield)", "",
          f"- shield r {P['shield_radius_m']:.1f} m, aft plane x {P['x_shield_m']:.2f} m",
          f"- engine maximum radius {P['engine_max_radius_m']:.2f} m ({P['engine_set_by']}); protected radius there {P['protected_radius_at_engine_m']:.1f} m; "
          f"clearance {P['engine_clearance_m']:+.1f} m",
          f"- shield radius that would cover every critical part: {P['shield_radius_required_m']:.1f} m",
          "", "| system | parts outside | exposed frontal (m²) | max protrusion (m) |", "| --- | --- | --- | --- |"]
    for k, v in sorted(P["summary"]["by_system"].items(), key=lambda kv: -kv[1]["exposed_frontal_area_m2"]):
        L.append(f"| {k} | {v['parts']} | {v['exposed_frontal_area_m2']:,.0f} | {v['max_protrusion_m']:.1f} |")
    L += ["", "## Sensitivity (canon shield)", "", "| arrival cone | margin | critical parts outside | exposed frontal (m²) | max protrusion (m) | shield r needed (m) | radiators outside |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for cone, m in ((0.0, 0.0), (0.0, 8.0), (0.0, 15.0), (2.290610043, 0.0), (5.0, 0.0)):
        r = S3.evaluate(cone_deg=cone, margin=m)["protection"]
        s = r["summary"]
        L.append(f"| {cone:.3g}° | {m:g} m | {s['critical_exposed']} | {s['exposed_frontal_area_m2']:,.0f} | {s['max_protrusion_m']:.1f} | "
                 f"{r['shield_radius_required_m']:.1f} | {r['radiator_summary']['fraction_exposed'] * 100:.1f} % |")
    rs = P["radiator_summary"]
    L += ["", "## Radiators (assessed separately)", "",
          f"- planform {rs['planform_m2'] / 1e6:.3f} km², inside the envelope {rs['protected_m2']:,.0f} m², outside {rs['exposed_m2'] / 1e6:.3f} km² "
          f"({rs['fraction_exposed'] * 100:.1f} %)",
          "- the FDP-1 wings lie in the XY plane: edge-on to an aligned stream, so their frontal area is leading-edge thickness × span; "
          "the thickness and the survivability class are UNKNOWN",
          "- retraction under full thermal load is not assumed", "",
          "## Input hashes (sha256)", ""] + [f"- `data/{k}` {v}" for k, v in hashes.items()]
    open(os.path.join(HERE, "VALIDATION_V3.md"), "w").write("\n".join(L) + "\n")
    return n_ok


S3 = None

if __name__ == "__main__":
    before = {f: sha(os.path.join(DATA, f)) for f in V3_FILES}
    sc, h = C2.main()
    S3 = ScenarioV3()
    base = S3.evaluate()
    geometry_tests()
    scaling_tests(S3, base)
    protection_tests(S3, base)
    regression_tests(S3, base, before)
    h.update(before)
    n = report(base, h)
    for g, nm, ok, d in C2.OUT:
        if not ok:
            print("FAIL", g, nm, d)
    print(f"{n}/{len(C2.OUT)} checks pass; wrote VALIDATION_V3.md")
    sys.exit(0 if n == len(C2.OUT) else 1)
