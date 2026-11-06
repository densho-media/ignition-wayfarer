"""FDP-1 scenario layer: what a chosen departure acceleration and warm-radiator temperature would require.
Standard library only. It never changes the baseline files; it reads data/scenario_inputs.json and data/fdp1_parameters.json.

Model (the FDP-1 record's own closure law, four_burn_mission closure.py, written out):

  m_end = m_fix + alpha_jet * P_jet + c * D            P_jet = a * g0 * m0 * ve / 2,  D = m0 (1 - 1/RN)
  m0 = RN * m_end   =>   m0 * B = RN * m_fix,   B = 1 - RN * alpha_jet * a * g0 * ve / 2 - c (RN - 1)

- RN is the four-burn mass ratio. It is fixed by delta-v and ve, so it does not depend on acceleration.
- c is tankage plus reserve per kg of propellant.
- m_fix is the mass that does not scale with power.
- alpha_jet is the drive plus radiator mass per W of jet power: (alpha_hw + alpha_rad(T)) / eta_jet.

B <= 0 means no departure mass closes: every added kilogram of engine needs more than a kilogram of engine to push it.
The model reports that state as INFEASIBLE under these scaling assumptions. It is not a law of physics: the ceiling moves if
alpha, ve or the tank fraction change.

Temperature: only the warm loop moves (the hot loop stays at the record's 1800 K). The warm radiator's mass per W of heat
is recomputed as areal_mass / flux(T) + transport. The flux is 2 * emissivity * sigma * T^4 per m2 of planform (two faces,
0 K sink, as in the record). Areal mass and transport per W are held at the record's values; that is an assumption, and
the scenario lists it.

Baseline check: with a = record a0 and T = 600 K this reproduces the record's departure mass, thrust and power (check_v2.py).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIGMA = 5.670374419e-8
G0 = 9.80665
C_LIGHT = 299792458.0


def load_inputs(path=os.path.join(ROOT, "data", "scenario_inputs.json")):
    return {k: v["value"] for k, v in json.load(open(path))["inputs"].items()}


class Scenario:
    """Baseline constants plus derived calibration (m_fix and the c coefficient) from the record."""

    SCALINGS = ("baseline_closure", "goal_1g_variant")

    def __init__(self, inputs=None):
        I = self.I = inputs or load_inputs()
        self.ve = I["closure.ve_km_s"] * 1e3
        self.RN = I["closure.mass_ratio"]
        self.eta = I["closure.eta_jet"]
        self.c = (I["closure.tank_t"] + I["closure.reserve_t"]) / I["closure.propellant_t"]
        self.m0_base = I["closure.departure_t"] * 1e3
        self.a0_base = I["closure.a0_g"]
        self.hot_T, self.warm_T = I["closure.hot_T"], I["closure.warm_T"]
        self.eps = I["closure.emissivity"]
        # transport allowance per W of heat (record kg_per_W minus the bare plate)
        self.tr_hot = I["closure.hot_kg_per_W"] - I["closure.hot_areal"] / I["closure.hot_flux"]
        self.tr_warm = I["closure.warm_kg_per_W"] - I["closure.warm_areal"] / I["closure.warm_flux"]
        # mass that does not scale with power, calibrated so the law reproduces the record baseline exactly
        B0 = self.bracket(self.a0_base, self.alpha_jet(self.warm_T, "baseline_closure"))
        self.m_fix = self.m0_base * B0 / self.RN

    # ------------------------------------------------------------------------------------------------------------
    def flux(self, T):
        return 2 * self.eps * SIGMA * T ** 4

    def warm_kg_per_W(self, T):
        return self.I["closure.warm_areal"] / self.flux(T) + self.tr_warm

    def alpha_rad(self, T):
        I = self.I
        return I["closure.heat_hot"] * I["closure.hot_kg_per_W"] + I["closure.heat_warm"] * self.warm_kg_per_W(T)

    def alpha_jet(self, T, scaling="baseline_closure"):
        a = (self.I["closure.alpha_hw"] + self.alpha_rad(T)) / self.eta
        if scaling == "goal_1g_variant":
            a += self.I["goal1g.alpha_jet"] - (self.I["closure.alpha_hw"] + self.alpha_rad(self.warm_T)) / self.eta
        return a

    def bracket(self, a_g, alpha):
        return 1 - self.RN * alpha * a_g * G0 * self.ve / 2 - self.c * (self.RN - 1)

    def ceiling_g(self, T, scaling="baseline_closure"):
        lin = 1 - self.c * (self.RN - 1)
        return 2 * lin / (self.RN * self.alpha_jet(T, scaling) * self.ve) / G0

    def gain(self, a_g, alpha):
        return self.RN * alpha * a_g * G0 * self.ve / 2 / (1 - self.c * (self.RN - 1))

    # ------------------------------------------------------------------------------------------------------------
    def powers(self, m0, a_g, T):
        I = self.I
        F = m0 * a_g * G0
        Pj = F * self.ve / 2
        Pf = Pj / self.eta
        hot, warm = I["closure.heat_hot"] * Pf, I["closure.heat_warm"] * Pf
        A_hot, A_warm = hot / self.flux(self.hot_T), warm / self.flux(T)
        return {"departure_kg": m0, "thrust_N": F, "jet_W": Pj, "fusion_W": Pf, "non_jet_W": Pf - Pj,
                "heat_hot_W": hot, "heat_warm_W": warm, "heat_W": hot + warm,
                "area_hot_m2": A_hot, "area_warm_m2": A_warm, "area_W_m2": A_hot + A_warm,
                "drive_hw_kg": I["closure.alpha_hw"] * Pf, "radiator_kg": self.alpha_rad(T) * Pf,
                "power_scaled_kg": self.alpha_jet(T) * Pj,
                "wings": self.wings(A_hot, A_warm),
                "burn_days_const_accel": 4 * 0.016 * C_LIGHT / (a_g * G0) / 86400.0}

    def wings(self, A_hot, A_warm):
        """Planform needed on the record's two coplanar wings (chord fixed, span grows)."""
        I = self.I
        ch, n = I["wings.chord_m"], I["wings.count"]
        base_r = I["wings.warm_root_m"] - I["wings.hot_band_m"]
        hot_band = max(A_hot - I["wings.reused_hot_m2"], 0.0) / (n * ch)
        root = base_r + hot_band
        tip = root + A_warm / (n * ch)
        return {"hot_band_m": hot_band, "warm_root_m": root, "tip_radius_m": tip, "span_m": tip - base_r,
                "beyond_designed_wing": tip > I["wings.tip_m"] * (1 + 1e-9),
                "equivalent_square_side_m": math.sqrt(A_hot + A_warm)}

    def evaluate(self, a_g, T=None, scaling="baseline_closure", iterations=5):
        """Everything the scene needs for one target. T None = record temperatures."""
        T = self.warm_T if T is None else float(T)
        alpha = self.alpha_jet(T, scaling)
        B = self.bracket(a_g, alpha)
        g = self.gain(a_g, alpha)
        out = {"inputs": {"accel_g": a_g, "warm_T_K": T, "hot_T_K": self.hot_T, "scaling": scaling},
               "alpha_jet_kg_per_W": alpha, "loop_gain": g, "bracket": B,
               "ceiling_g": self.ceiling_g(T, scaling), "feasible": B > 0,
               "at_baseline_mass": self.powers(self.m0_base, a_g, T)}
        if B > 0:
            m0 = self.RN * self.m_fix / B
            st = self.powers(m0, a_g, T)
            D = m0 * (1 - 1 / self.RN)
            st.update({"propellant_kg": D, "tank_and_reserve_kg": self.c * D, "fixed_kg": self.m_fix,
                       "end_kg": m0 / self.RN})
            out["closed"] = st
            out["status"] = "BASELINE" if abs(a_g - self.a0_base) < 1e-9 and abs(T - self.warm_T) < 1e-9 else "CLOSES"
        else:
            out["closed"] = None
            out["status"] = "INFEASIBLE"
        # the feedback the scene animates: start at today's mass and add the engine each pass
        seq, m = [], self.m0_base
        A0 = self.RN * self.m_fix / (1 - self.c * (self.RN - 1))
        for _ in range(iterations):
            m = A0 + g * m
            seq.append(m)
        out["feedback_departure_kg"] = seq
        out["flags"] = self.flags(a_g, T, out)
        return out

    def flags(self, a_g, T, r):
        f = []
        if not r["feasible"]:
            f.append(("INFEASIBLE", f"no departure mass closes: loop gain {r['loop_gain']:.2f} >= 1; ceiling "
                                    f"{r['ceiling_g']:.4f} g under these scaling assumptions (not a physical law)"))
        if T > self.warm_T + 1e-9:
            f.append(("P06", f"warm loop at {T:.0f} K: driver and power-system heat must be rejected at {T:.0f} K "
                             "(heat lift or high-temperature electronics; pumping power TBD)"))
            f.append(("ASSUMPTION", "warm radiator areal mass and transport per W held at record values (1 kg/m2)"))
        if T >= 1500:
            f.append(("P07", "radiator material limits at 1,500-2,500 K TBD (speculative)"))
        if T > self.hot_T:
            f.append(("P06", f"warm loop above the hot loop ({self.hot_T:.0f} K): loop roles would swap; not modelled"))
        w = (r["closed"] or r["at_baseline_mass"])["wings"]
        if w["beyond_designed_wing"]:
            f.append(("P09", f"wing tip radius {w['tip_radius_m'] / 1e3:.2f} km exceeds the designed {self.I['wings.tip_m'] / 1e3:.2f} km: "
                             "deployment, structure and dynamics unverified"))
        return f


def table(sc, cases):
    rows = []
    for a, T in cases:
        r = sc.evaluate(a, T)
        st = r["closed"] or r["at_baseline_mass"]
        rows.append({"accel_g": a, "warm_T_K": r["inputs"]["warm_T_K"], "status": r["status"], "ceiling_g": r["ceiling_g"],
                     "loop_gain": r["loop_gain"], "departure_t": st["departure_kg"] / 1e3,
                     "basis": "closed design" if r["closed"] else "at today's mass (lower bound; no closure)",
                     "thrust_MN": st["thrust_N"] / 1e6, "fusion_TW": st["fusion_W"] / 1e12, "heat_GW": st["heat_W"] / 1e9,
                     "area_km2": st["area_W_m2"] / 1e6, "tip_km": st["wings"]["tip_radius_m"] / 1e3,
                     "power_scaled_t": st["power_scaled_kg"] / 1e3, "flags": [k for k, _ in r["flags"]]})
    return rows
