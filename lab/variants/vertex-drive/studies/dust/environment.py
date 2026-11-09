"""T02 environment model: dust and gas along the mission path, per leg, for the FDP-1/Vertex ships and the canon four-nozzle ship.

Standard library only. Research, not canon. Run from the repo root:
    python3 lab/variants/vertex-drive/studies/dust/environment.py      # writes environment.json beside this file

Every input carries a label (PUBLISHED, TRANSCRIBED, MODEL, EXTRAPOLATION, ASSUMPTION, CANON, UNKNOWN) and a source ID
(registry/sources.toml or S-T02-* in registry_proposal.toml). Three cases (LOW, NOMINAL, HIGH) bracket the environment; they are
envelopes of the literature, not probabilities.

Physics kept deliberately simple:
- grains are at rest compared with the ship (their 5-30 km/s is at most 0.4 deg of aberration at 4,797 km/s); the impact speed is
  sqrt(v_ship^2 + v_grain^2), so near the start and end of a burn the grains' own speed is kept.
- the number of grains a frontal area A meets on a leg is A * integral N(>m, r) dl and does not depend on speed; the energy of each
  grain does (E = m v^2 / 2). Energy fluence = integral rho v^2 / 2 dl.
- path: straight and radial from or to the ignition point (heliocentric 1 AU, ASSUMPTION: canon ignition position OPEN, wf_route_v1.json
  absolute_ignition_position). Gravity is ignored (solar escape speed at 1 AU, 42 km/s, is under 1 % of cruise).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "environment.json")

AU = 1.495978707e11
C = 299792458.0
V_CRUISE = 0.016 * C                         # CANON mission.target_speed (LOCKED)
VE = 19201.17208e3                           # MODEL FDP-1 exhaust speed (results/convergence.json V0..V2); canon ship uses the same ve
YEAR = 365.25 * 86400

MASS_EDGES = [10.0 ** k for k in range(-18, 0)]            # kg, decade bins 1e-18 .. 1e-1
ENERGY_THRESHOLDS_J = [1.0, 10.0, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10]
CASES = ("LOW", "NOMINAL", "HIGH", "NOMINAL_HILAT")


# ---- populations ------------------------------------------------------------------------------------------------------
def grun_flux(m_kg):
    """Grun et al. (1985) interplanetary cumulative flux of grains heavier than m at 1 AU onto a spinning flat plate, m^-2 s^-1.
    TRANSCRIBED (S-T02-GRUN-1985): constants reproduce the published 1 AU spatial mass density of order 1e-19 kg/m3 (9.6e-20 here)."""
    m = m_kg * 1e3
    return ((2.2e3 * m ** 0.306 + 15.0) ** -4.38 + 1.3e-9 * (m + 1e11 * m ** 2 + 1e27 * m ** 4) ** -0.36
            + 1.3e-16 * (m + 1e6 * m ** 2) ** -0.85)


GRUN_V = 20e3            # m/s, Grun model's single impact speed (TRANSCRIBED)
SDC_M0 = 2.62e-15        # kg, New Horizons SDC threshold r >= 0.63 um (PUBLISHED, S-T02-SDC)
SDC_PEAK = 3.5e-8        # m^-3 for m >= SDC_M0 near 42 AU ("~35 km^-3", Bernardoni et al. 2022; SECONDARY via search snippet)
ISD_M1, ISD_M2 = 1e-18, 1e-13   # kg, Ulysses/Galileo detected range of the interstellar population (S-ULYSSES-ISD)
ISD_MEAN = 3e-16                # kg, mean interstellar grain mass (S-ULYSSES-ISD, already in the registry)


def _isd_beta():
    """Cumulative power-law index beta, N(>m) ~ m^-beta between ISD_M1 and ISD_M2, that gives the published mean mass (MODEL fit)."""
    def mean(b):
        num = b / (1 - b) * (ISD_M2 ** (1 - b) - ISD_M1 ** (1 - b))
        den = ISD_M1 ** -b - ISD_M2 ** -b
        return num / den
    lo, hi = 0.05, 0.95
    for _ in range(80):
        mid = (lo + hi) / 2
        if mean(mid) > ISD_MEAN:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


ISD_BETA = _isd_beta()

CASE = {
    # IPD: Grun scale factor. KB: SDC density scale, cumulative mass index alpha, upper mass. ISD: dust mass density, large-grain tail.
    "LOW":     {"ipd_scale": 0.5, "kb_scale": 1 / 3, "kb_alpha": 1.0, "kb_mmax": 1e-8, "isd_rho": 1.5e-24, "isd_tail": "NONE"},
    "NOMINAL": {"ipd_scale": 1.0, "kb_scale": 1.0, "kb_alpha": 0.83, "kb_mmax": 1e-6, "isd_rho": 2.1e-24, "isd_tail": "EXTRAPOLATED"},
    "HIGH":    {"ipd_scale": 2.0, "kb_scale": 3.0, "kb_alpha": 0.70, "kb_mmax": 1e-3, "isd_rho": 6.2e-24, "isd_tail": "RADAR"},
    # NOMINAL with a high-ecliptic-latitude path (heading OPEN in canon): Kuiper-belt dust x0.1, zodiacal dust x0.3 (ASSUMPTION; both clouds
    # are concentrated near the ecliptic). Not a canon path; an owner question.
    "NOMINAL_HILAT": {"ipd_scale": 0.3, "kb_scale": 0.1, "kb_alpha": 0.83, "kb_mmax": 1e-6, "isd_rho": 2.1e-24, "isd_tail": "EXTRAPOLATED"},
}
CASE_NOTES = {
    "ipd_scale": "x0.5 / x1 / x2 on Grun (1985); EXTRAPOLATION of the model's stated factor-2 accuracy",
    "kb_scale": "x1/3 / x1 / x3 on the SDC peak density; Doner et al. (2024) report fluxes above models to 55-60 AU",
    "kb_alpha": "cumulative mass index of the Kuiper-belt collisional dust above the SDC threshold; 0.83 = Dohnanyi (1969) cascade (EXTRAPOLATION: SDC does not measure grains above ~10 um)",
    "kb_mmax": "largest Kuiper-belt dust grain kept (ASSUMPTION)",
    "isd_rho": "interstellar dust mass density: 1.5e-24 (below Kruger & Strub 2015 1-sigma), 2.1e-24 (Kruger & Strub 2015), 6.2e-24 kg/m3 (Frisch et al. 1999)",
    "isd_tail": "NONE = no interstellar grain above 1e-13 kg; EXTRAPOLATED = the in-situ distribution extrapolated, taken at its stated upper bound (Landgraf et al. 2000: under 1e-10 m-2 s-1 above 3e-10 kg at Earth); RADAR = the AMOR hyperbolic-meteor flux 2e-9 m-2 s-1 above 3e-10 kg (Baggaley 1999/2000; disputed by later radar surveys)",
}


def ipd_N(m, r_au, cs):
    """Inner interplanetary dust, cumulative number density m^-3 (Grun at 1 AU, r^-1.3 radial law; EXTRAPOLATION beyond 5 AU; cut at 30 AU)."""
    if r_au > 30:
        return 0.0          # beyond 30 AU the Kuiper-belt population (kb_N) replaces the inner cloud (ASSUMPTION)
    return cs["ipd_scale"] * 4.0 * grun_flux(m) / GRUN_V * max(r_au, 0.3) ** -1.3


def kb_density_profile(r_au):
    """SDC-normalised outer-solar-system density for m >= SDC_M0, m^-3 (shape: ASSUMPTION fitted to Bernardoni 2022 / Doner 2024 statements:
    rising from the inner-IPD level at 10 AU to the 42 AU peak, flat to 60 AU, falling to zero at 100 AU)."""
    if r_au < 10:
        return 0.0
    if r_au < 42:
        f = math.log(r_au / 10) / math.log(4.2)
        return SDC_PEAK * (0.1 ** (1 - f))
    if r_au < 60:
        return SDC_PEAK
    if r_au < 100:
        return SDC_PEAK * (100 - r_au) / 40
    return 0.0


def kb_N(m, r_au, cs):
    n0 = cs["kb_scale"] * kb_density_profile(r_au)
    if n0 == 0 or m > cs["kb_mmax"]:
        return 0.0
    mm = max(m, SDC_M0)
    base = n0 * (mm / SDC_M0) ** -cs["kb_alpha"]
    cap = n0 * (cs["kb_mmax"] / SDC_M0) ** -cs["kb_alpha"]
    if m < SDC_M0:   # below the SDC threshold continue with the same index (EXTRAPOLATION, small effect on energy)
        base = n0 * (m / SDC_M0) ** -cs["kb_alpha"]
    return base - cap


def isd_N(m, r_au, cs):
    """Interstellar dust: Ulysses-calibrated power law between 1e-18 and 1e-13 kg, normalised to the case mass density, plus the tail case.
    Present everywhere beyond 4 AU (ASSUMPTION: heliospheric filtering of the smallest grains ignored; beyond the heliopause the filtered
    sub-0.1 um grains add surface erosion only)."""
    if r_au < 4:
        return 0.0
    b = ISD_BETA
    # N(>m) = K (m^-b - ISD_M2^-b) on [M1, M2]; mass density = K b/(1-b) (M2^(1-b) - M1^(1-b))
    K = cs["isd_rho"] / (b / (1 - b) * (ISD_M2 ** (1 - b) - ISD_M1 ** (1 - b)))
    core = K * (max(m, ISD_M1) ** -b - ISD_M2 ** -b) if m < ISD_M2 else 0.0
    tail = isd_tail_N(m, cs, K)
    return core + tail


def isd_tail_N(m, cs, K):
    """Large interstellar grains above the in-situ range. Both non-NONE cases are anchored on a flux at Earth above 3e-10 kg,
    turned into a spatial density with 40 km/s (ASSUMPTION, hyperbolic meteors), with cumulative index 1.1 above 3e-10 kg to 1e-5 kg
    (radar fit, Landgraf et al. 2000) and a log-linear bridge of index 0.5 down to 1e-13 kg (ASSUMPTION).
    EXTRAPOLATED: 1e-10 m^-2 s^-1, the upper bound Landgraf et al. (2000) give for the in-situ distribution extrapolated.
    RADAR: 2e-9 m^-2 s^-1, the AMOR hyperbolic-meteor flux (Baggaley 2000), disputed by later surveys."""
    kind = cs["isd_tail"]
    if kind == "NONE":
        return 0.0
    flux = {"EXTRAPOLATED": 1e-10, "RADAR": 2e-9}[kind]
    n3, s, mx = flux / 40e3, 1.1, 1e-5
    n_mt = n3 * (1e-13 / 3e-10) ** -0.5
    cap = n3 * (mx / 3e-10) ** -s
    mm = max(m, 1e-13)
    if mm < 3e-10:
        val = n_mt * (mm / 1e-13) ** (math.log(n3 / n_mt) / math.log(3e-10 / 1e-13))
    elif mm < mx:
        val = n3 * (mm / 3e-10) ** -s
    else:
        return 0.0
    return max(val - cap, 0.0)


POPULATIONS = {"IPD": ipd_N, "KB": kb_N, "ISD": isd_N}
POP_SPEED = {"IPD": 20e3, "KB": 5e3, "ISD": 26e3}    # m/s grain speed (Grun; Keplerian at 40 AU; Ulysses ISD inflow 26 km/s)


def mass_density(pop, r_au, cs, edges=None):
    """kg/m3 of one population at r, summed over decade bins with the bin's geometric-mean mass."""
    fn = POPULATIONS[pop]
    tot = 0.0
    for a, b in zip(_fine(), _fine()[1:]):
        dn = fn(a, r_au, cs) - fn(b, r_au, cs)
        if dn > 0:
            tot += dn * math.sqrt(a * b)
    return tot


_FINE = None


def _fine():
    global _FINE
    if _FINE is None:
        _FINE = [10 ** (k / 10) for k in range(-180, 1)]
    return _FINE


# ---- gas --------------------------------------------------------------------------------------------------------------
HELIOPAUSE_AU = 120.0      # PUBLISHED: Voyager 1 121.6 AU (2012), Voyager 2 119 AU (2018) (S-T02-VOYAGER-HP)


def gas(r_au):
    """Number densities m^-3: solar-wind protons, neutral H, ionised H, neutral He. Sources: S-T02-LIC (Slavin & Frisch 2008:
    n(H0) 0.19-0.20, n_e 0.07 cm^-3 at the Sun), solar wind 5 cm^-3 at 1 AU (r^-2, textbook), He 0.015 cm^-3 (ASSUMPTION, LIC typical)."""
    if r_au < HELIOPAUSE_AU:
        sw = 5e6 * r_au ** -2
        h0 = 0.1e6 if r_au > 5 else 0.1e6 * (r_au / 5) ** 2     # ASSUMPTION: filtration to ~half the LIC value; ionised close to the Sun
        return {"p": sw, "H0": h0, "He": 0.015e6 if r_au > 5 else 0.0}
    return {"p": 0.07e6, "H0": 0.195e6, "He": 0.015e6}


AMU = 1.66053907e-27


# ---- mission legs -----------------------------------------------------------------------------------------------------
def burn_track(distance_au, accel_ratio, decel, n=6000):
    """Speed against distance for a constant-thrust burn whose mass falls linearly in time (power-limited, constant exhaust speed).
    accel_ratio = a_end / a_start = m_start / m_end. Returns list of (s_m, v_mps) with s along the leg, normalised so the burn
    covers the given distance (the shape is exact; the scale is the calculator's). decel: speed falls from cruise to 0."""
    mu1 = 1.0 / accel_ratio
    # parameter: mass fraction mu from 1 to mu1; v = VE ln(1/mu); dt ~ -dmu (constant mass flow); ds = v dt
    pts, s = [], 0.0
    dmu = (1 - mu1) / n
    prev_v = 0.0
    for i in range(n + 1):
        mu = 1 - i * dmu
        v = VE * math.log(1 / mu)
        if i:
            s += 0.5 * (v + prev_v) * dmu
        pts.append((s, v))
        prev_v = v
    vmax = pts[-1][1]
    scale = distance_au * AU / pts[-1][0]
    track = [(si * scale, vi * V_CRUISE / vmax) for si, vi in pts]
    if decel:
        S = track[-1][0]
        track = [(S - si, vi) for si, vi in reversed(track)]
    return track, vmax


def legs_fdp1():
    """Five legs of the FDP-1 / Vertex mission (V0 = V1 = V2 kinematics: same a0 0.0069 g and ve, results/convergence.json burn_years 5.685
    for all three). Burn distances MODEL lab/variants/fdp1/results/fdp1-v1/baseline.json; destination = the minimum stopping distance."""
    b = json.load(open(os.path.join(HERE, "..", "..", "..", "fdp1", "results", "fdp1-v1", "baseline.json")))["mission"]
    burns = b["burns"]
    D = b["minimum_destination_AU"]
    r0 = 1.0
    d = [x["distance_AU"] for x in burns]
    ratio = [x["accel_end_g"] / x["accel_start_g"] for x in burns]
    coast_home = D - (d[2] + d[3])
    return [
        {"id": "F1", "name": "accelerate outbound", "orientation": "BOW_FIRST", "kind": "burn", "r_from": r0, "r_to": r0 + d[0], "dist_au": d[0], "ratio": ratio[0], "decel": False, "days": burns[0]["duration_days"]},
        {"id": "F2", "name": "brake at destination", "orientation": "ENGINE_FIRST", "kind": "burn", "r_from": r0 + d[0], "r_to": r0 + D, "dist_au": d[1], "ratio": ratio[1], "decel": True, "days": burns[1]["duration_days"]},
        {"id": "F3", "name": "accelerate home", "orientation": "BOW_FIRST", "kind": "burn", "r_from": r0 + D, "r_to": r0 + D - d[2], "dist_au": d[2], "ratio": ratio[2], "decel": False, "days": burns[2]["duration_days"]},
        {"id": "F4", "name": "coast home", "orientation": "BOW_FIRST", "kind": "coast", "r_from": r0 + D - d[2], "r_to": r0 + d[3], "dist_au": coast_home, "days": coast_home * AU / V_CRUISE / 86400},
        {"id": "F5", "name": "brake at home", "orientation": "ENGINE_FIRST", "kind": "burn", "r_from": r0 + d[3], "r_to": r0, "dist_au": d[3], "ratio": ratio[3], "decel": True, "days": burns[3]["duration_days"]},
    ], {"destination_AU_from_ignition": D, "ignition_r_AU": r0, "source": "lab/variants/fdp1/results/fdp1-v1/baseline.json mission"}


CANON_DEST_AU = 45.0    # ASSUMPTION: Kuiper anchorage in the main belt (30-50 AU); canon position OPEN (24_ROUTE_EVENTS, 25!F17/F19)


def legs_canon(dest_au=CANON_DEST_AU):
    """Canon four-nozzle ship: four power-limited burns at 21.77 MN (docs/MODEL.md B01, CANON WORKING): first 9.99 d, 13.3 AU, 0.50 -> 0.64 g;
    mass ratio 1.284 per burn, so later burns scale with their start mass (4,426 / 3,447 / 2,684 / 2,091 t; MODEL)."""
    m = [4426.0]
    for _ in range(4):
        m.append(m[-1] / 1.284)
    d = [13.3 * mk / m[0] for mk in m[:4]]
    days = [9.99 * mk / m[0] for mk in m[:4]]
    r0 = 1.0
    return [
        {"id": "C1", "name": "accelerate outbound", "orientation": "BOW_FIRST", "kind": "burn", "r_from": r0, "r_to": r0 + d[0], "dist_au": d[0], "ratio": 1.284, "decel": False, "days": days[0]},
        {"id": "C2", "name": "coast out", "orientation": "BOW_FIRST", "kind": "coast", "r_from": r0 + d[0], "r_to": dest_au - d[1], "dist_au": dest_au - d[1] - r0 - d[0], "days": None},
        {"id": "C3", "name": "brake at Kuiper anchorage", "orientation": "ENGINE_FIRST", "kind": "burn", "r_from": dest_au - d[1], "r_to": dest_au, "dist_au": d[1], "ratio": 1.284, "decel": True, "days": days[1]},
        {"id": "C4", "name": "accelerate home", "orientation": "BOW_FIRST", "kind": "burn", "r_from": dest_au, "r_to": dest_au - d[2], "dist_au": d[2], "ratio": 1.284, "decel": False, "days": days[2]},
        {"id": "C5", "name": "coast home", "orientation": "BOW_FIRST", "kind": "coast", "r_from": dest_au - d[2], "r_to": r0 + d[3], "dist_au": dest_au - d[2] - r0 - d[3], "days": None},
        {"id": "C6", "name": "brake at home", "orientation": "ENGINE_FIRST", "kind": "burn", "r_from": r0 + d[3], "r_to": r0, "dist_au": d[3], "ratio": 1.284, "decel": True, "days": days[3]},
    ], {"destination_AU_heliocentric": dest_au, "ignition_r_AU": r0, "source": "docs/MODEL.md First Ignition operating point (B01); destination ASSUMPTION"}


def leg_track(leg):
    if leg["kind"] == "coast":
        L = leg["dist_au"] * AU
        return [(L * i / 400, V_CRUISE) for i in range(401)]
    tr, _ = burn_track(leg["dist_au"], leg["ratio"], leg["decel"])
    return tr


def integrate_leg(leg, cs):
    """Column densities and fluences on a leg for one case."""
    tr = leg_track(leg)
    r_from, r_to = leg["r_from"], leg["r_to"]
    L = tr[-1][0]
    sgn = 1 if r_to >= r_from else -1
    out = {"path_m": L, "path_AU": L / AU}
    col = {p: [0.0] * len(MASS_EDGES) for p in POPULATIONS}          # integral N(>m_k) dl, m^-2
    efl = {p: 0.0 for p in POPULATIONS}                              # J/m2
    mfl = {p: 0.0 for p in POPULATIONS}                              # kg/m2
    hits_E = {p: [0.0] * len(ENERGY_THRESHOLDS_J) for p in POPULATIONS}   # integral N(>2E/v^2) dl
    gascol = {"p": 0.0, "H0": 0.0, "He": 0.0}
    gas_E = 0.0
    # thin the track for the integrals (burn tracks are fine-grained)
    step = max(1, len(tr) // 500)
    pts = tr[::step] + ([tr[-1]] if (len(tr) - 1) % step else [])
    for (s0, v0), (s1, v1) in zip(pts, pts[1:]):
        ds = s1 - s0
        if ds <= 0:
            continue
        sm, vm = 0.5 * (s0 + s1), 0.5 * (v0 + v1)
        r = r_from + sgn * sm / AU
        for p, fn in POPULATIONS.items():
            vrel2 = vm * vm + POP_SPEED[p] ** 2
            for k, m in enumerate(MASS_EDGES):
                col[p][k] += fn(m, r, cs) * ds
            rho = mass_density(p, r, cs) if (r > 0) else 0.0
            efl[p] += 0.5 * rho * vrel2 * ds
            mfl[p] += rho * ds
            for k, E in enumerate(ENERGY_THRESHOLDS_J):
                hits_E[p][k] += fn(2 * E / vrel2, r, cs) * ds
        g = gas(r)
        for kk in gascol:
            gascol[kk] += g[kk] * ds
        gas_E += 0.5 * (g["p"] + g["H0"]) * AMU * 1.007 * vm * vm * ds + 0.5 * g["He"] * AMU * 4.0026 * vm * vm * ds
    out.update({"column_N_gt_m_per_m2": col, "energy_fluence_J_m2": efl, "mass_fluence_kg_m2": mfl,
                "column_N_gt_E_per_m2": hits_E, "gas_column_per_m2": gascol, "gas_energy_fluence_J_m2": gas_E,
                "v_max_km_s": max(v for _, v in tr) / 1e3})
    return out


def run():
    fl, fl_meta = legs_fdp1()
    cl, cl_meta = legs_canon()
    res = {"meta": {
        "title": "T02 environment along the mission path (research, not canon)",
        "frame": "heliocentric distance r along a straight radial path; grains at rest; 0 deg arrival (aberration <= 0.4 deg)",
        "mass_edges_kg": MASS_EDGES, "energy_thresholds_J": ENERGY_THRESHOLDS_J,
        "isd_beta_fitted": ISD_BETA, "cases": CASE, "case_notes": CASE_NOTES,
        "fdp1_path": fl_meta, "canon_path": cl_meta, "heliopause_AU": HELIOPAUSE_AU,
        "labels": {"grun": "TRANSCRIBED", "sdc_peak": "PUBLISHED (secondary)", "kb_shape": "ASSUMPTION", "isd_core": "PUBLISHED",
                   "isd_tails": "EXTRAPOLATION / disputed PUBLISHED", "gas": "PUBLISHED (LIC) + ASSUMPTION (heliosphere)",
                   "path": "MODEL (FDP-1 burns) + ASSUMPTION (1 AU start, canon 45 AU destination)"}},
        "density_profile": [], "ships": {}}
    for r in (1, 3, 10, 20, 30, 42, 50, 60, 80, 100, 130, 300, 1000, 1700):
        row = {"r_AU": r}
        for c in CASES:
            cs = CASE[c]
            row[c] = {p: {"rho_kg_m3": mass_density(p, r, cs), "N_gt_1e-15kg_m3": POPULATIONS[p](1e-15, r, cs),
                          "N_gt_1e-9kg_m3": POPULATIONS[p](1e-9, r, cs), "N_gt_1e-6kg_m3": POPULATIONS[p](1e-6, r, cs)} for p in POPULATIONS}
        row["gas_m3"] = gas(r)
        res["density_profile"].append(row)
    for ship, legs in (("FDP1_VERTEX", fl), ("CANON", cl)):
        res["ships"][ship] = []
        for leg in legs:
            e = {k: v for k, v in leg.items()}
            e["cases"] = {c: integrate_leg(leg, CASE[c]) for c in CASES}
            res["ships"][ship].append(e)
    json.dump(res, open(OUT, "w"), indent=1)
    return res


if __name__ == "__main__":
    r = run()
    for ship, legs in r["ships"].items():
        for leg in legs:
            n = leg["cases"]["NOMINAL"]
            tot_e = sum(n["energy_fluence_J_m2"].values())
            k9 = MASS_EDGES.index(1e-9)
            print(f"{ship:11s} {leg['id']} {leg['name']:26s} {leg['orientation']:12s} {n['path_AU']:8.1f} AU  vmax {n['v_max_km_s']:6.0f}  "
                  f"E-fluence {tot_e:9.3g} J/m2  N(>1ug) {sum(n['column_N_gt_m_per_m2'][p][k9] for p in POPULATIONS):9.3g}/m2  "
                  f"N(>10kJ) {sum(n['column_N_gt_E_per_m2'][p][4] for p in POPULATIONS):9.3g}/m2  gas {sum(n['gas_column_per_m2'].values()):8.3g}/m2")
