"""Revision 4 check of two T05 geometry proposals (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/rev4/proposals.py     # writes results/proposals.json (seconds)

1. AXIS_PLUG_LI: a renewable liquid-lithium droplet sheet across the axis about 35 m from the burn (r about 3.7 m, polar 0-6 deg) that
   stops the unstopped axial plasma. Checked here: the fluence on it, whether condensed lithium can take it without vaporising, and the
   lithium consumption if it vaporises.
2. B-ray: launcher B-modified along a burn ray at polar 12 deg (az 120 deg), tip 45 m from the burn, 30,000 g, about 132 m long. Checked:
   the V4 stopping radius near 12 deg, the vacuum field along the ray, the kinematics and the alignment drift.
"""
import math

import injection as IN
import ledger as LG
from common import G0, MU0, solve_full, v4_overrides, write_json

LI = {'rho': 480.0, 'c': 4200.0, 'T0': 800.0, 'Tb': 1615.0, 'Lv': 19.6e6}


def loop_B(I, a, zc, r, z, n=720):
    """|B| of a circular loop (radius a at axial position zc) at (r, z), by Biot-Savart quadrature."""
    Br = Bz = 0.0
    for k in range(n):
        p = 2 * math.pi * (k + 0.5) / n
        dlx, dly = -a * math.sin(p) * 2 * math.pi / n, a * math.cos(p) * 2 * math.pi / n
        rx, ry, rz = r - a * math.cos(p), -a * math.sin(p), z - zc
        d3 = (rx * rx + ry * ry + rz * rz) ** 1.5
        cx = dly * rz; cz = dlx * ry - dly * rx; cy = -dlx * rz
        Br += cx / d3; Bz += cz / d3
    return MU0 * I / (4 * math.pi) * math.hypot(Br, Bz)


def plug(R):
    f = R['fusion']
    Ep = f['yield_per_pulse_J'] * (1 - f['xray_escape_fraction'] - f['neutron_escape_fraction'])
    d = 35.0
    F = Ep / (4 * math.pi * (d * 100) ** 2)                          # J/cm2 per pulse on the plug
    share = (0.0023, 0.0032)                                          # geometric 6.4-deg cone, T03 thin-shell shield strike
    E_pulse = [s * Ep for s in share]
    h_vap = LI['c'] * (LI['Tb'] - LI['T0']) + LI['Lv']
    # a droplet heats through if it is smaller than the ion range; its specific energy is 3F/(4 rho r)
    r_safe = 3 * F * 1e4 / (4 * LI['rho'] * LI['c'] * (LI['Tb'] - LI['T0']))
    mdot_prop = f['mass_flow_kg_s']
    rows = []
    for vap_share, lab in ((1.0, 'all absorbed energy vaporises lithium (no re-radiation)'),
                           (0.1, 'vapour shielding: 10 % of the energy vaporises (90 % re-radiated)'),
                           (0.01, 'strong vapour shielding: 1 %')):
        m = [e * vap_share / h_vap for e in E_pulse]
        rows.append({'case': lab, 'li_kg_per_pulse': m, 'li_kg_s': [x * f['pellet_rate_Hz'] for x in m],
                     'times_propellant_flow': [x * f['pellet_rate_Hz'] / mdot_prop for x in m],
                     'mission_t': [x * f['pellet_rate_Hz'] * 5.685 * 3.15576e7 / 1e3 for x in m]})
    return {'distance_m': d, 'raw_plasma_J_cm2_per_pulse': F, 'intercepted_J_per_pulse': E_pulse,
            'intercepted_W': [e * f['pellet_rate_Hz'] for e in E_pulse], 'li_h_to_vapour_J_kg': h_vap,
            'droplet_radius_to_stay_liquid_m': r_safe,
            'ion_range_note': 'MeV/u D, He, p ions stop in about 0.1-1 mm of lithium; a droplet larger than that vaporises its front layer, '
                              f'and one smaller than that heats through: it stays liquid only above r = {r_safe * 100:.1f} cm, which is above the range',
            'consumption': rows, 'propellant_flow_kg_s': mdot_prop,
            'verdict': 'NOT PLAUSIBLE as a renewable consumable: even with 99 % re-radiation it vaporises far more lithium than the ship '
                       'carries as propellant, and the vapour expands back toward the shield and the coils'}


def bray(R, ov):
    cg = LG.coils_v4(R)
    s, fI = cg['scale'], cg['current_factor']
    loops = LG.T03['designs']['C_W15']['loops']
    stop = LG.T03['designs']['C_W15']['thin_shell']['stopping_radius_m_by_polar_deg']
    stop_v4 = {k: (v * s if v else None) for k, v in stop.items()}
    th = math.radians(12.0)
    field = []
    for dd in (5, 10, 20, 30, 40, 45, 50, 58, 70, 90, 120, 177):
        r, z = dd * math.sin(th), dd * math.cos(th)
        B = 0.0
        Bv = [loop_B(l['current_MA'] * 1e6 * fI, l['radius_m'] * s, l['z_m'] * s, r, z) for l in loops]
        field.append({'distance_m': dd, 'B_T_upper': sum(Bv)})
    s10, s20 = stop_v4['10'], stop_v4['20']
    s12 = s10 + (s20 - s10) * 0.2
    out = {'stopping_radius_V4_m': {'10': s10, '12_interp': s12, '20': s20, 'basis': 'T03 thin shell (V1) x stand-off scale 1.501'},
           'field_along_ray': field, 'field_note': 'sum of loop magnitudes: an upper bound on |B| (directions not combined)'}
    for tip in (45.0, round(1.3 * s12, 1)):
        a_g = 30000.0
        k = IN.kin(R, tip, a_g)
        out[f'tip_{tip:g}m'] = {'open_flight_m': tip, 'muzzle_m_s': k['muzzle_m_s'], 'accelerator_m': k['accelerator_m'],
                                'tip_xray_J_cm2': k['tip_xray_J_cm2'], 'tip_MW_m2': k['tip_xray_MW_m2'],
                                'margin_to_stopping_surface_m': tip - s12, 'gas_capsule_SF': 102282 / a_g,
                                'far_end_distance_m': tip + k['accelerator_m']}
    tf = 45.0 / IN.kin(R, 45.0, 30000.0)['muzzle_m_s']
    a_ship = 0.018730006731935773 * G0
    out['alignment'] = {'ship_drift_transverse_um': 0.5 * a_ship * tf * tf * math.sin(th) * 1e6,
                        'ship_drift_axial_component_um': 0.5 * a_ship * tf * tf * math.cos(th) * 1e6,
                        'pointing_urad_untracked': 0.1e-3 / 45.0 * 1e6,
                        'note': 'the barrel is off the spine: mount it on the shield frame or the C1 strut ring, track the target and steer '
                                'the driver; drift is negligible'}
    out['verdict'] = ('KINEMATICS PLAUSIBLE (gas capsule SF 3.4 at 30,000 g; armature and sabot at 30,000 g not demonstrated). The 45 m '
                      'tip sits on the V4 stopping surface near 12 deg (T05 used the V1 radius 29.7 m), so the tip must move out to about '
                      f'{1.3 * s12:.0f} m; the barrel then grows and the tip fluence falls. Off-axis it no longer needs the plug, but the '
                      'shield-face centre is still in the axial channel.')
    return out


def main():
    ov = v4_overrides(); R = solve_full(ov)
    out = {'study': 'Revision 4: check of T05 proposals AXIS_PLUG_LI and B-ray (T00)', 'status': 'MODEL, research only, NON-CANON',
           'axis_plug': plug(R), 'b_ray': bray(R, ov)}
    write_json('proposals.json', out)
    p = out['axis_plug']; b = out['b_ray']
    print(f"plug: {p['raw_plasma_J_cm2_per_pulse']:.0f} J/cm2, {[x / 1e9 for x in p['intercepted_W']]} GW, safe r {p['droplet_radius_to_stay_liquid_m']:.3f} m")
    for c in p['consumption']:
        print(' ', c['case'][:40], [round(x, 2) for x in c['li_kg_per_pulse']], 'kg/pulse', [round(x) for x in c['times_propellant_flow']], 'x prop',
              [round(x) for x in c['mission_t']], 't')
    print(b['stopping_radius_V4_m']); print([(f['distance_m'], round(f['B_T_upper'], 2)) for f in b['field_along_ray']])
    for k in b:
        if k.startswith('tip_'):
            print(k, {x: round(v, 1) for x, v in b[k].items()})
    print(b['alignment'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
