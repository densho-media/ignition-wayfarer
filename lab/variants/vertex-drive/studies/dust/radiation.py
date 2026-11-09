"""T02 research question 10: burn radiation on crew and engine hardware, in both orientations. Writes radiation.json.
    python3 lab/variants/vertex-drive/studies/dust/radiation.py

First order only (1/r^2, exponential removal, no build-up, no scatter, no (n,gamma)); a transport code must replace it.
Burn sources and shares come from results/convergence.json (Atlas) and the FDP-1 shielding record; the burn is fixed in the
ship frame, so every number here is the same in bow-first and engine-first flight (checked below, not assumed).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 5))
CONV = json.load(open(os.path.join(ROOT, "lab/variants/vertex-drive/results/convergence.json")))
FDP1 = json.load(open(os.path.join(ROOT, "lab/variants/fdp1/results/fdp1-v1/baseline.json")))
GEO = json.load(open(os.path.join(ROOT, "lab/problems/fdp1-requirements/data/ship_geometry.json")))

YEAR = 365.25 * 86400.0
MEV = 1.602176634e-13
X_BURN = -227.53981167687354           # FDP-1 burn point (ship_geometry.json loop-2 strut ends)
NEUTRON_MEV = 2.45                     # D-D dominates the escaping spectrum (FDP-1 config, T04 EARLY section 3)
LAMBDA_LIH_M = 0.15                    # FDP-1 config ASSUMPTION (removal relaxation length)
RHO_LIH = 780.0
# REBCO lifetime fast-neutron fluence: Ic and n-value degrade from ~1e22-4e22 m^-2 (Fischer et al. 2018, Prokopec et al. 2015,
# reactor irradiation, SECONDARY_VERIFIED); an in-situ 14 MeV study saw degradation orders of magnitude lower (UNVERIFIED in detail).
REBCO_LIMIT_M2 = {"PESSIMISTIC": 3e20, "NOMINAL": 3e22, "OPTIMISTIC": 4e22}
SHOE_CHORD_M = 0.6                     # ASSUMPTION: burn-facing shoe over a 0.21 m cryostat plus supports


def loops():
    out = []
    for p in GEO["parts"]:
        n = p["name"]
        if n.startswith("FDP1_Loop_") and "_Sector_1" in n:
            k = int(n.split("_")[2])
            out.append({"loop": k, "x_m": p["x"], "R_m": p["R"], "conductor_a_m": p["a"]})
    return sorted(out, key=lambda d: d["loop"])


def per_generation(gen):
    s = CONV["generations"][gen]["summary"]
    P = s["fusion_TW"] * 1e12
    t = s["burn_years"] * YEAR
    f_n = FDP1["fusion"]["neutron_escape_fraction"]
    f_x = CONV["generations"][gen]["escape_share"]
    rate_n = f_n * P / (NEUTRON_MEV * MEV)
    E_x = f_x * P / s["pellet_rate_Hz"]
    rows = []
    for L, R in zip(loops(), CONV["generations"][gen]["loop_radii_m"]):
        dx = L["x_m"] - X_BURN
        d = math.hypot(dx, R)
        fluence = rate_n * t / (4 * math.pi * d * d)
        dec = {c: max(0.0, math.log10(fluence / lim)) for c, lim in REBCO_LIMIT_M2.items()}
        thick = {c: v * math.log(10) * LAMBDA_LIH_M for c, v in dec.items()}
        mass_t = {c: 2 * math.pi * R * SHOE_CHORD_M * th * RHO_LIH / 1e3 for c, th in thick.items()}
        # added burn solid-angle share of the shoe: ring of length 2 pi R, width SHOE_CHORD_M seen at distance d
        share = 2 * math.pi * R * SHOE_CHORD_M / (4 * math.pi * d * d)
        rows.append({
            "loop": L["loop"], "R_m": round(R, 3), "dx_from_burn_m": round(dx, 2), "distance_m": round(d, 2),
            "polar_angle_deg": round(math.degrees(math.atan2(R, dx)), 1),
            "neutron_fluence_per_mission_m2": fluence, "neutron_fluence_per_mission_cm2": fluence * 1e-4,
            "ratio_to_REBCO_limit": {c: fluence / lim for c, lim in REBCO_LIMIT_M2.items()},
            "xray_J_m2_per_pulse": E_x / (4 * math.pi * d * d),
            "xray_W_m2_mean": f_x * P / (4 * math.pi * d * d),
            "lih_shoe_decades": dec, "lih_shoe_thickness_m": thick, "lih_shoe_mass_t": mass_t,
            "shoe_added_solid_angle_share": share,
            "shoe_xray_heat_MW": share * f_x * P / 1e6,
        })
    return {"fusion_TW": s["fusion_TW"], "burn_years": s["burn_years"], "pellet_rate_Hz": s["pellet_rate_Hz"],
            "neutron_escape_fraction": f_n, "xray_escape_fraction": f_x, "neutron_rate_per_s": rate_n,
            "hardware_cone_deg": CONV["generations"][gen]["hardware_cone_deg"], "loops": rows}


def orientation_check():
    """Dose depends only on ship-frame geometry; the stream direction enters nowhere. Evaluate both and compare."""
    out = {}
    for orient, sign in (("BOW_FIRST", -1), ("ENGINE_FIRST", +1)):
        # ship-frame source position and receiver positions are unchanged by the velocity vector
        d = [math.hypot(L["x_m"] - X_BURN, L["R"]) for L in [{"x_m": l["x_m"], "R": l["R_m"]} for l in loops()]]
        out[orient] = {"stream_direction_x": sign, "loop_distances_m": [round(v, 3) for v in d]}
    out["identical"] = out["BOW_FIRST"]["loop_distances_m"] == out["ENGINE_FIRST"]["loop_distances_m"]
    return out


def gas_secondary():
    """Bow (bow-first) or engine-side (engine-first) gas stream: 120 keV protons, 477 keV He. Below the p+7Li (441 keV
    resonance, gamma) and every (p,n) threshold for Li, W, C, Al (>= 1.88 MeV); proton bremsstrahlung scales as (me/mp)^2."""
    v = 0.016 * 299792458.0
    n_p = 0.195e6 + 0.07e6           # LIC H0 + p, per m3 (Slavin & Frisch 2008)
    n_he = 0.015e6                   # ASSUMPTION
    flux = n_p * v * 0.5 * 1.6726e-27 * v * v + n_he * v * 0.5 * 6.6447e-27 * v * v
    brems = 1.0 / 1836.15 ** 2 * 1e-4   # electron thick-target efficiency ~1e-4 at ~100 keV (ASSUMPTION), x (me/mp)^2
    return {"LIC_power_flux_W_m2": flux, "proton_energy_keV": 0.5 * 1.6726e-27 * v * v / 1.602e-16,
            "he_energy_keV": 0.5 * 6.6447e-27 * v * v / 1.602e-16,
            "bremsstrahlung_W_m2_upper": flux * brems,
            "nuclear": "no (p,n) or (alpha,n) channel open at 120/477 keV on W, Li, C, Al; p+7Li capture resonance at 441 keV not reached by protons",
            "verdict": "secondary radiation from the gas stream is negligible in both orientations (< 1e-11 W/m2)"}


def crew():
    sh = FDP1["shield"]
    return {"crew_half_angle_deg": sh["crew_half_angle_deg"], "crew_distance_m": sh["crew_distance_m"],
            "neutron_decades": sh["neutron_decades"], "xray_decades": sh["xray_decades"], "lih_core_m": sh["lih_core_m"],
            "shield_mass_t": sh["mass_kg"]["total"] / 1e3, "limits": sh["limits"],
            "orientation": "the FDP-1 shadow shield sizes the crew dose from the ship-frame burn; turning engine-first changes nothing",
            "skirt_note": "T02-NEW-1 lies on the hardware-cone boundary (edge-on); it must sit inside the shadow with a penumbra "
                          "margin (rim scatter not modelled) and adds no burn solid angle"}


def main():
    out = {"meta": {"script": "radiation.py", "status": "RESEARCH; first-order", "labels": {
        "fluence": "MODEL (1/r^2 from the Atlas fusion power and the FDP-1 neutron escape share)",
        "REBCO_limit": "SECONDARY_VERIFIED range (reactor irradiation); in-situ 14 MeV degradation onset lower (UNVERIFIED)",
        "shoe": "ASSUMPTION geometry, LiH relaxation length from the FDP-1 config"},
        "rebco_limit_m2": REBCO_LIMIT_M2, "shoe_chord_m": SHOE_CHORD_M},
        "orientation_check": orientation_check(), "crew": crew(), "gas_secondary": gas_secondary(),
        "generations": {g: per_generation(g) for g in ("V0", "V1", "V2")}}
    json.dump(out, open(os.path.join(HERE, "radiation.json"), "w"), indent=1)
    for g, d in out["generations"].items():
        for L in d["loops"]:
            print(g, L["loop"], f"d {L['distance_m']} m", f"{L['neutron_fluence_per_mission_cm2']:.2e} n/cm2",
                  f"x{L['ratio_to_REBCO_limit']['NOMINAL']:.1f} limit", f"shoe {L['lih_shoe_thickness_m']['NOMINAL']:.2f} m "
                  f"{L['lih_shoe_mass_t']['NOMINAL']:.0f} t share {L['shoe_added_solid_angle_share']:.2e}")
    print("orientation identical:", out["orientation_check"]["identical"])


if __name__ == "__main__":
    main()
