"""V3 scenario layer: the V2 closure scenario plus P11 geometry, shield-mass feedback and per-constraint statuses.
Standard library only. The V2 Scenario is reused unchanged: the baseline still reproduces the FDP-1 record exactly.

State levels (the brief's five):
  authoritative inputs   scenario_inputs.json, ship_geometry.json, protection_inputs.json (each value with source/status)
  derived baseline       Scenario().evaluate(a0) and Protection at the record geometry
  user target            accel, warm-loop T, scaling, arrival cone, margin, shield radius, areal density, engine-geometry law
  hypothetical           every scenario value above the record, listed in `assumptions`
  feasibility            per constraint family: PASS / FAIL / UNRESOLVED / ASSUMPTION, plus `mathematically_closed` and
                         `physically_validated` (always False here: P01, P02, P09 and the five non-geometric protection
                         categories have no validated model)

The engine geometry does not follow power unless a packaging law is chosen (engine_radius_exponent > 0). In that case
every engine part's radial coordinate is scaled by (P_fusion / P_fusion_record) ** exponent, and the result is marked
ASSUMPTION. Mass never turns into geometry.

Shield-mass feedback: an enlarged shield adds areal_density * (pi R^2 - pi R0^2) of fixed mass. This happens only when
an areal density is given, and the value is then an ASSUMPTION, because the shield stack and its mass are OPEN
(OD-014). Without one, the mass effect stays UNRESOLVED and the closure is reported without it.
"""
import math

try:
    from .protection import Protection, engine_envelope, summarize, UNRESOLVED_CATEGORIES, ENGINE_GROUPS, classify
    from .scenario import Scenario
except ImportError:  # embedded in the .blend as flat modules
    from protection import Protection, engine_envelope, summarize, UNRESOLVED_CATEGORIES, ENGINE_GROUPS, classify
    from scenario import Scenario

STATUSES = ("PASS", "FAIL", "UNRESOLVED", "ASSUMPTION")


class ScenarioV3:
    def __init__(self, scenario=None, protection=None):
        self.sc = scenario or Scenario()
        self.pr = protection or Protection()
        self.R0 = self.pr.shield["radius_m"]
        self.engine0 = engine_envelope(self.pr.geo)
        self._crit = None

    # ---- mass feedback with an added fixed mass (the V2 law, m_fix + dm) ---------------------------------------
    def evaluate_mass(self, a_g, T=None, scaling="baseline_closure", dm=0.0):
        sc = self.sc
        if not dm:
            return sc.evaluate(a_g, T, scaling)
        m_fix, m0 = sc.m_fix, sc.m0_base
        try:
            sc.m_fix, sc.m0_base = m_fix + dm, m0 + dm
            r = sc.evaluate(a_g, T, scaling)
        finally:
            sc.m_fix, sc.m0_base = m_fix, m0
        if r["status"] == "BASELINE":
            r["status"] = "CLOSES"
        return r

    def critical_points(self, h=0.5, radial_scale=1.0):
        out = []
        for p in self.pr.geo["parts"]:
            if classify(p) != "CRITICAL":
                continue
            s = radial_scale if p["group"] in ENGINE_GROUPS else 1.0
            out += [(x, y * s, z * s) for x, y, z, _ in self.pr.part_samples(p, h)]
        return out

    def evaluate(self, a_g=None, T=None, scaling="baseline_closure", cone_deg=0.0, margin=0.0, band=1.0,
                 shield="baseline", shield_radius=None, areal_density=None, engine_exp=0.0, h=0.5):
        """shield: 'baseline' (canon 45 m), 'required' (covers every critical part), or 'custom' (shield_radius)."""
        sc = self.sc
        a_g = sc.a0_base if a_g is None else a_g
        v2 = sc.evaluate(a_g, T, scaling)
        st = v2["closed"] or v2["at_baseline_mass"]
        k_eng = (st["fusion_W"] / sc.powers(sc.m0_base, sc.a0_base, sc.warm_T)["fusion_W"]) ** engine_exp if engine_exp else 1.0
        # shield geometry for this scenario
        pts = self.critical_points(h, k_eng)
        R_req = self.pr.required_radius(pts, cone_deg, margin)
        R = {"baseline": self.R0, "required": R_req, "custom": shield_radius or self.R0}[shield]
        sil = type(self.pr.sil)(R) if R != self.R0 else self.pr.sil
        rows = self.pr.assess(cone_deg, margin, band, h, sil=sil, engine_radial_scale=k_eng)
        summ = summarize(rows)
        rad = self.pr.radiators(cone_deg, margin) if R == self.R0 else self._radiators_at(R, cone_deg, margin)
        dA = math.pi * (R * R - self.R0 * self.R0)
        dm = areal_density * dA if (areal_density is not None and dA > 0) else 0.0
        mass_effect = ("NONE" if dA <= 0 else ("ASSUMPTION" if areal_density is not None else "UNRESOLVED"))
        v3 = self.evaluate_mass(a_g, T, scaling, dm) if dm else v2
        prot = {"cone_deg": cone_deg, "margin_m": margin, "band_m": band, "shield_mode": shield,
                "shield_radius_m": R, "shield_radius_baseline_m": self.R0, "shield_radius_required_m": R_req,
                "shield_area_m2": math.pi * R * R, "shield_area_baseline_m2": math.pi * self.R0 ** 2, "shield_added_area_m2": max(dA, 0.0),
                "shield_added_mass_kg": dm if dm else None, "shield_mass_effect": mass_effect, "areal_density_kg_m2": areal_density,
                "x_shield_m": self.pr.x_s, "engine_radial_scale": k_eng, "engine_exp": engine_exp,
                "engine_max_radius_m": self.engine0["max_radius_m"] * k_eng, "engine_set_by": self.engine0["set_by"],
                "engine_clearance_m": self.pr.protected_radius(self.engine0["at_x_m"], cone_deg, margin, R) - self.engine0["max_radius_m"] * k_eng,
                "protected_radius_at_engine_m": self.pr.protected_radius(self.engine0["at_x_m"], cone_deg, margin, R),
                "rows": rows, "summary": summ, "radiators": rad, "radiator_summary": _rad_summary(rad),
                "categories": UNRESOLVED_CATEGORIES}
        out = {"v2": v2, "v3": v3, "protection": prot}
        out["assumptions"] = self.assumptions(a_g, T, scaling, prot, v2)
        out["constraints"] = self.constraints(v2, v3, prot, T)
        out["mathematically_closed"] = v3["closed"] is not None
        out["physically_validated"] = False
        return out

    def _radiators_at(self, R, cone, margin):
        sil0 = self.pr.sil
        try:
            self.pr.sil = type(sil0)(R)
            return self.pr.radiators(cone, margin)
        finally:
            self.pr.sil = sil0

    def assumptions(self, a_g, T, scaling, prot, v2):
        A = []
        if abs(a_g - self.sc.a0_base) > 1e-12:
            A.append(f"target acceleration {a_g:.4g} g (record {self.sc.a0_base:.4g} g)")
        if T is not None and abs(T - self.sc.warm_T) > 1e-9:
            A.append(f"warm loop {T:.0f} K; areal mass and transport per W held at record values")
        if scaling != "baseline_closure":
            A.append("scaling: record goal-1g specific mass")
        if prot["cone_deg"] == 0:
            A.append("idealized parallel particle stream along -X")
        else:
            A.append(f"arrival cone {prot['cone_deg']:.3g} deg (attitude envelope OPEN, OD-015)")
        if prot["margin_m"]:
            A.append(f"safety margin {prot['margin_m']:.3g} m")
        if prot["shield_mode"] != "baseline":
            A.append(f"hypothetical shield radius {prot['shield_radius_m']:.1f} m (canon 45 m unchanged)")
        if prot["areal_density_kg_m2"] is not None:
            A.append(f"shield areal density {prot['areal_density_kg_m2']:g} kg/m2 (stack OPEN, OD-014)")
        if prot["engine_exp"]:
            A.append(f"engine radial size scales as P^{prot['engine_exp']:.3g} (no documented packaging law)")
        return A

    def constraints(self, v2, v3, prot, T):
        C = {}
        closed = v3["closed"] is not None
        st = v3["closed"] or v3["at_baseline_mass"]
        C["Propulsion"] = ("ASSUMPTION", "closes under record assumptions (P01 gain, P02 drivers unproven)") if closed else \
            ("FAIL", f"no departure mass closes: loop gain {v3['loop_gain']:.2f}, ceiling {v3['ceiling_g']:.4f} g (scaling assumption, not a physical law)")
        if prot["shield_mass_effect"] == "UNRESOLVED":
            C["Mass"] = ("UNRESOLVED", f"enlarged shield adds {prot['shield_added_area_m2']:,.0f} m2; areal density unknown (OD-014), mass effect not computed"
                         + ("" if closed else "; and no closure without it"))
            if not closed:
                C["Mass"] = ("FAIL", C["Mass"][1])
        elif closed:
            C["Mass"] = ("PASS", f"budget closes mathematically at {st['departure_kg'] / 1e3:,.0f} t")
        else:
            C["Mass"] = ("FAIL", "engine and spacecraft mass do not close (power-to-mass feedback)")
        w = st["wings"]
        if w["beyond_designed_wing"] or (T is not None and abs(T - self.sc.warm_T) > 1e-9):
            C["Thermal"] = ("UNRESOLVED", f"{st['area_W_m2'] / 1e6:,.2f} km2 needed, wing tip {w['tip_radius_m'] / 1e3:,.2f} km"
                            + (" beyond the designed 3.57 km" if w["beyond_designed_wing"] else "")
                            + ("; warm-loop transport/material limits TBD (P06, P07)" if T is not None and T > self.sc.warm_T else ""))
        else:
            C["Thermal"] = ("ASSUMPTION", "record radiators reject the heat (areal mass, emissivity assumed; 3.57 km wing deployment unverified)")
        k = st["fusion_W"] / self.sc.powers(self.sc.m0_base, self.sc.a0_base, self.sc.warm_T)["fusion_W"]
        C["Radiation"] = ("UNRESOLVED", "neutron production fraction UNKNOWN; shadow shield sized for the record power"
                          + (f"; target radiation x{k:,.1f} with the shield not resized" if k > 1.0001 else ""))
        s = prot["summary"]
        if s["critical_exposed"]:
            top = sorted(s["by_system"].items(), key=lambda kv: -kv[1]["exposed_frontal_area_m2"])[:3]
            C["Geometry"] = ("FAIL", f"{s['critical_exposed']} critical parts outside the envelope, {s['exposed_frontal_area_m2']:,.0f} m2 exposed, "
                             f"max protrusion {s['max_protrusion_m']:.1f} m ({', '.join(k for k, _ in top)})")
        else:
            C["Geometry"] = ("UNRESOLVED", "every critical part is geometrically covered; stopping, ejecta and penetration unmodelled (P11)")
        C["Structures"] = ("UNRESOLVED", "loads, fatigue (~1.8e10 pulses) and wing deployment unverified (P09)")
        C["Mission"] = ("FAIL", "four burns not achievable at this acceleration (no closure)") if not closed else \
            ("UNRESOLVED", "computed minimum 6.35 y vs canon LOCKED 6.0 y; reserve policy UNKNOWN (P10)")
        return C


def _rad_summary(rad):
    tot = sum(r["planform_m2"] for r in rad)
    prot = sum(r["protected_m2"] for r in rad)
    return {"planform_m2": tot, "protected_m2": prot, "exposed_m2": tot - prot, "fraction_exposed": (tot - prot) / tot if tot else 0.0,
            "frontal_aligned_m2": sum(r["frontal_aligned_m2"] for r in rad),
            "frontal_worst_in_cone_m2": sum(r["frontal_worst_in_cone_m2"] for r in rad),
            "fdp1_wings_exposed_m2": sum(r["exposed_m2"] for r in rad if r["name"].startswith("FDP1_Wing")),
            "wayfarer_exposed_m2": sum(r["exposed_m2"] for r in rad if r["name"].startswith("WF_"))}
