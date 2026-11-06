"""Export the physical geometry of Wayfarer with FDP-1 installed into data/ship_geometry.json (pure Python, no Blender).

    python3 lab/problems/fdp1-requirements/export_geometry.py

Two sources, both read-only:
1. Wayfarer as built on main. The source is the current production geometry baseline
   (references/baselines.json -> geometry_fingerprint.json), which holds the world bounding box of every generated
   object. A blockout is drawn from the principal objects:
   - hull, collar and spine;
   - habitat rings;
   - forward shield, Crown and EYE;
   - the three hot radiator blades, plus the WARM and LOW radiator zones;
   - the existing 13-vessel tank farm;
   - the engineering envelope and Brayton trains.
   The four-nozzle drive that FDP-1 replaces is exported as SUPERSEDED.
2. FDP-1 hardware. The FDP-1 record's own procedural geometry (engineering/geometry.py on branch
   claude/project-thread-8e13aa) is run on the record (results/fdp1-v1/baseline.json).
   The record's tank option T-B moves the bow forward by its added length (the rule build_fdp1.py uses: every object whose
   box lies wholly ahead of the existing farm). The export does the same, so the ship in this file matches the
   FDP-1 review ship.

Every part keeps its source (fingerprint object or record path) and status:
- ENGINEERED: sized by a calculation or the built model;
- PLACEHOLDER: the record's provisional size;
- ILLUSTRATIVE: display only;
- SUPERSEDED: replaced by FDP-1.
Units are metres, +X bow, +Z dorsal, ship frame.
"""
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BRANCH = "origin/claude/project-thread-8e13aa"
RECORD = "lab/variants/fdp1/results/fdp1-v1/baseline.json"
OUT = os.environ.get("FDP1_GEOMETRY_OUT", os.path.join(HERE, "data", "ship_geometry.json"))


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def fingerprint():
    meta = json.load(open(os.path.join(ROOT, "references", "baselines.json")))
    path = os.path.join(ROOT, meta["current"], "geometry_fingerprint.json")
    return meta["current"], json.load(open(path))


def bbox(o):
    return o["min"], o["max"]


def part(out, name, group, func, shape, status, source, **kw):
    d = {"name": name, "group": group, "func": func, "shape": shape, "status": status, "source": source, "alpha": 1.0}
    d.update(kw)
    out.append(d)
    return d


def wayfarer_parts(fp, base):
    out = []
    obj = {}
    for f, v in fp.items():
        for k, o in v.get("objects", {}).items():
            obj.setdefault(k, (f, o))
    src = lambda k: f"{base}: {obj[k][0]} :: {k}"   # noqa: E731

    def cyl(k, name, group, func, r=None, status="ENGINEERED"):
        lo, hi = bbox(obj[k][1])
        rr = r if r is not None else max(hi[1] - lo[1], hi[2] - lo[2]) / 2
        part(out, name, group, func, "ring", status, src(k), x0=lo[0], x1=hi[0], r0=0.0, r1=rr)

    cyl("Hull_Aft_Body", "WF_Hull_Aft_Body", "hull", "STRUCTURE")
    cyl("Hull_Forward_Collar", "WF_Hull_Forward_Collar", "hull", "STRUCTURE")
    lo, hi = bbox(obj["Structural_Spine"][1])
    part(out, "WF_Structural_Spine", "hull", "STRUCTURE", "tube", "ENGINEERED", src("Structural_Spine"),
         points=[(lo[0], 0, 0), (hi[0], 0, 0)], radius=(hi[1] - lo[1]) / 2)
    cyl("Engineering_Envelope", "WF_Engineering_Envelope", "engineering", "POWER")
    for k in ("Brayton_Train_1", "Brayton_Train_2"):
        lo, hi = bbox(obj[k][1])
        part(out, "WF_" + k, "engineering", "POWER", "box", "ENGINEERED", src(k),
             centre=[(a + b) / 2 for a, b in zip(lo, hi)], size=[b - a for a, b in zip(lo, hi)])
    # habitat rings: ring meshes are local (x -2..2); the rotor axes place them
    for i, ax in ((1, "WF_SIM_ROTOR_1_AXIS"), (2, "WF_SIM_ROTOR_2_AXIS")):
        x = obj[ax][1]["matrix_world"][0][3]
        lo, hi = bbox(obj[f"Ring_{i}_Hoop_Outer"][1])
        _, hi_in = bbox(obj[f"Ring_{i}_Hoop_Inner"][1])
        part(out, f"WF_Habitat_Ring_{i}", "habitat", "HABITAT", "ring", "ENGINEERED",
             src(f"Ring_{i}_Hoop_Outer") + f" placed at {ax}", x0=x + lo[0], x1=x + hi[0], r0=hi_in[1], r1=hi[1])
    lo, hi = bbox(obj["Fuel_Deck_Ring_Lacing"][1])
    part(out, "WF_Fuel_Deck_Lacing", "storage", "STRUCTURE", "ring", "ENGINEERED", src("Fuel_Deck_Ring_Lacing"),
         x0=lo[0], x1=hi[0], r0=hi[1] - 1.0, r1=hi[1])
    # forward shield (moves with the bow)
    for k, func in (("Shield_Rim", "SHIELD"), ("Shield_Skin", "SHIELD"), ("Disruptor_Layer_01", "SHIELD")):
        lo, hi = bbox(obj[k][1])
        part(out, "WF_" + k, "bow", func, "ring", "ENGINEERED", src(k), x0=lo[0], x1=hi[0], r0=0.0, r1=hi[1])
    lo, hi = bbox(obj["Crown_Housing_Inner_Wall"][1])
    part(out, "WF_Crown_Housing", "bow", "SENSORS_COMMS", "ring", "ENGINEERED", src("Crown_Housing_Inner_Wall"),
         x0=lo[0] - 1.0, x1=hi[0], r0=hi[1], r1=bbox(obj["Crown_Housing_Aft_Plate"][1])[1][1])
    for i in range(1, 5):
        k = f"EYE_Facet_{i:02d}"
        lo, hi = bbox(obj[k][1])
        part(out, "WF_" + k, "bow", "SENSORS_COMMS", "box", "ENGINEERED", src(k),
             centre=[(a + b) / 2 for a, b in zip(lo, hi)], size=[max(b - a, 0.3) for a, b in zip(lo, hi)])
    # hot radiator blades: component mesh (local x along the ship, local y radial) placed by the Radiator_0n matrices
    rad = fp["components/WF_RADIATOR.blend"]["objects"]
    lx0 = min(o["min"][0] for o in rad.values() if "min" in o)
    lx1 = max(o["max"][0] for o in rad.values() if "max" in o)
    ly1 = max(o["max"][1] for o in rad.values() if "max" in o)
    for i in (1, 2, 3):
        k = f"Radiator_0{i}"
        m = obj[k][1]["matrix_world"]

        def W(x, y):
            return [m[r][0] * x + m[r][1] * y + m[r][3] for r in range(3)]
        part(out, f"WF_Hot_Radiator_Blade_{i}", "radiators", "HOT_RADIATOR", "panel", "ENGINEERED",
             f"{base}: components/WF_RADIATOR.blend blade cells placed by {k}",
             corners=[W(lx0, 0), W(lx1, 0), W(lx1, ly1), W(lx0, ly1)], thickness=0.15)
    # WARM and LOW radiator zones: three sectors each
    cells = {}
    for k, (f, o) in obj.items():
        mm = re.match(r"Radiator_Zone_(LOW|WARM)_(\d)_Cell", k)
        if mm and "min" in o:
            cells.setdefault((mm.group(1), mm.group(2)), []).append(o)
    for (zone, s), v in sorted(cells.items()):
        x0, x1 = min(o["min"][0] for o in v), max(o["max"][0] for o in v)
        rs = [math.hypot(*o["centroid"][1:]) for o in v]
        az = math.degrees(math.atan2(sum(o["centroid"][2] for o in v), sum(o["centroid"][1] for o in v)))
        r0, r1 = min(rs) - 3.3, max(rs) + 3.3

        def pol(x, r):
            return [x, r * math.cos(math.radians(az)), r * math.sin(math.radians(az))]
        part(out, f"WF_{zone.title()}_Radiator_Zone_{s}", "radiators", f"{zone}_RADIATOR", "panel", "ENGINEERED",
             f"{base}: subsystems/WF_THERMAL.blend Radiator_Zone_{zone}_{s}_Cell_* ({len(v)} cells)",
             corners=[pol(x0, r0), pol(x1, r0), pol(x1, r1), pol(x0, r1)], thickness=0.15)
    # superseded four-nozzle drive (FDP-1 replaces it: build_fdp1.py SUPERSEDED_INSTANCES)
    for k in ("Fusion_Core", "Magnetic_Manifold", "Common_Plasma_Region"):
        cyl(k, "SUP_" + k, "superseded", "MAIN_PROPULSION", status="SUPERSEDED")
    cyl("Reactor_Shadow_Shield_Envelope", "SUP_Reactor_Shadow_Shield", "superseded", "SHIELD", status="SUPERSEDED")
    for i in range(4):
        lo, hi = bbox(obj[f"Nozzle_Yoke_{i}_0"][1])
        cy, cz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2
        part(out, f"SUP_Nozzle_{i + 1}", "superseded", "MAIN_PROPULSION", "frustum", "SUPERSEDED",
             src(f"Nozzle_Yoke_{i}_0") + " (yoke envelope of nozzle %d)" % (i + 1),
             x0=lo[0], x1=-136.8, r0=(hi[1] - lo[1]) / 2, r1=(hi[1] - lo[1]) / 4, centre=[cy, cz])
        k = f"LATTICE_SECTOR_{i + 1}"
        lo, hi = bbox(obj[k][1])
        part(out, "SUP_Fiji_" + k, "superseded", "HELIUM3", "box", "SUPERSEDED", src(k),
             centre=[(a + b) / 2 for a, b in zip(lo, hi)], size=[b - a for a, b in zip(lo, hi)])
    return out


def fdp1_parts():
    """Run the record's own geometry module on the record (read-only, from the FDP-1 branch)."""
    R = json.loads(git("show", f"{BRANCH}:{RECORD}"))
    src = git("show", f"{BRANCH}:lab/variants/fdp1/engineering/geometry.py")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "fdp1_geometry.py")
        open(p, "w").write(src)
        spec = importlib.util.spec_from_file_location("fdp1_geometry", p)
        G = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(G)
        parts = G.parts(R)
        sel = R["tanks"]["selected"]
        tanks = [t for t in G.tank_parts(R) if t["coll"] == f"10:{sel}"]
    groups = {"00": "fdp1_structure", "01": "fdp1_fuel_prep", "02": "fdp1_drivers", "03": "fdp1_reaction",
              "04": "fdp1_nozzle", "05": "fdp1_shield", "06": "fdp1_thermal", "07": "fdp1_power", "08": "fdp1_sensors",
              "09": "fdp1_service", "10": "fdp1_tanks", "11": "fdp1_keepout", "12": "fdp1_labels"}
    out = []
    for p in parts + tanks:
        if p["shape"] == "text" or p["coll"] in ("11", "12"):
            continue          # labels and keep-out displays are redrawn by the spatial model
        if p["coll"] == "03" and p["status"] == "ILLUSTRATIVE":
            continue          # the exhaust/plasma displays are replaced by the information layer
        q = dict(p)
        q["group"] = groups[p["coll"].split(":")[0]]
        q["source"] = f"{BRANCH} lab/variants/fdp1/engineering/geometry.py on {RECORD}"
        q.pop("coll")
        out.append(q)
    existing = R["tanks"]["existing"]
    ex = []
    for t in existing:
        ex.append({"name": "WF_" + t["name"], "group": "storage", "func": {"helium_3": "HELIUM3", "deuterium": "DEUTERIUM",
                                                                        "hydrogen": "HYDROGEN"}[t["key"]],
                   "shape": "capsule", "status": "ENGINEERED", "alpha": 1.0, "x0": t["x0"], "x1": t["x1"],
                   "centre": [t["y"], t["z"]], "radius": t["a_env"],
                   "source": f"{RECORD} tanks.existing (Wayfarer farm as built), {t['liquid_m3']:.0f} m3 {t['key']}"})
    bow_dx = R["tanks"]["options"][sel].get("added_length_m", 0.0) if sel == "T-B" else 0.0
    x_from = max(t["x1"] for t in existing) + 0.05
    return out, ex, bow_dx, x_from, R


def shift_bow(parts, dx, x_from):
    moved = []
    for p in parts:
        if p["group"] != "bow":
            continue
        for key in ("x0", "x1"):
            if key in p:
                p[key] += dx
        if "centre" in p and len(p["centre"]) == 3:
            p["centre"][0] += dx
        p["moved_by_m"] = dx
        moved.append(p["name"])
    return moved


def main():
    base, fp = fingerprint()
    wf = wayfarer_parts(fp, base)
    fd, ex, dx, x_from, R = fdp1_parts()
    moved = shift_bow(wf, dx, x_from)
    lay = R["layout"]
    doc = {
        "meta": {
            "units": "metres; +X bow, +Z dorsal; ship frame of data/wayfarer_3d.toml",
            "wayfarer_baseline": base,
            "fdp1_record": f"{BRANCH}:{RECORD}",
            "fdp1_record_commit": git("rev-parse", BRANCH).strip(),
            "tank_option": R["tanks"]["selected"],
            "bow_shift_m": dx,
            "bow_shift_rule": f"objects wholly ahead of x = {x_from:.2f} m (existing farm) move forward, as build_fdp1.py does",
            "bow_moved": moved,
            "superseded": "four-nozzle drive, its Fiji lattice sectors and reactor shadow shield (FDP-1 replaces them)",
            "layout": lay,
            "nozzle_loops": R["nozzle"]["loops"],
            "wings": R["thermal"]["layouts"][R["thermal"]["selected_layout"]],
            "statuses": "ENGINEERED sized by a calculation or the built model; PLACEHOLDER provisional (record); "
                        "ILLUSTRATIVE display only; SUPERSEDED replaced by FDP-1",
        },
        "parts": wf + ex + fd,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=0, separators=(",", ":"))
    print(f"wrote {OUT}: {len(wf)} Wayfarer + {len(ex)} tank + {len(fd)} FDP-1 parts; bow +{dx:.1f} m ({len(moved)} parts)")


if __name__ == "__main__":
    sys.exit(main())
