"""Pure radiator heat-budget formulas (40_THERMAL B10, B45). No Blender and no spec import: callers pass the spec mapping.

The root margin reads radiators.emissivity (the 0.90 conservative root baseline) and never the 0.95-0.98 nano-skin target
(radiators.emissivity_target), which is unqualified (OD-023)."""
SIGMA = 5.670374419e-8  # Stefan-Boltzmann, 01_CONSTANTS (Locked)


def ideal_rejection_W(area_m2, emissivity, temperature_K):
    """Stefan-Boltzmann rejection of an area facing space."""
    return emissivity * SIGMA * area_m2 * temperature_K ** 4


def ideal_area_m2(heat_W, emissivity, temperature_K):
    """Emitting area that rejects heat_W at the given emissivity and temperature."""
    return heat_W / (emissivity * SIGMA * temperature_K ** 4)


def root_calibration_margin_W(s):
    """DIAGNOSTIC ideal rejection of the effective area minus the root-calibration absorbed drive heat."""
    r = s['radiators']
    return ideal_rejection_W(r['effective_area']['value'], r['emissivity']['value'], r['temperature']['value']) - r['drive_heat_calibration']['absorbed_heat_W']


def y155(s):
    """OWN-RAD-Y155 (40!A110:F123): per case, the relative ideal per-area uplift (eps/eps_root)*(F/F_root) at the same 1800 K, the
    same-geometry ideal rejection (40!B10 x uplift), the equal-ideal-load area fraction 1-1/uplift and the residual against the 16 GW
    root calibration (positive = deficit). All DIAGNOSTIC / UNQUALIFIED: no resize, no actual heat closure."""
    r = s['radiators']; sc = r['y155_scenario']
    eps0, f0 = r['emissivity']['value'], r['view_factor']['value']
    base = ideal_rejection_W(r['effective_area']['value'], eps0, r['temperature']['value'])
    heat = r['drive_heat_calibration']['absorbed_heat_W']
    out = [dict(id='BASELINE', emissivity=eps0, view_factor=f0, status=r['emissivity']['canon_status'], uplift=1.0, rejection_W=base,
                area_reduction=0.0, residual_W=heat - base)]
    for c in sc['cases']:
        if not (0.0 < c['emissivity'] <= 1.0 and 0.0 < c['view_factor'] <= 1.0):
            raise ValueError(f"{c['id']}: emissivity and view factor must lie in (0, 1]")
        u = (c['emissivity'] / eps0) * (c['view_factor'] / f0)
        out.append(dict(id=c['id'], emissivity=c['emissivity'], view_factor=c['view_factor'], status=c['status'], uplift=u,
                        rejection_W=base * u, area_reduction=1.0 - 1.0 / u, residual_W=heat - base * u))
    return out
