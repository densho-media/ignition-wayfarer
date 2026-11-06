"""Fiji Drive physics budget (lab/variants/fiji-drive study, owner brief 2026-11-02). Standard library only; reads data/ and src/wayfarer/.

What it answers, with every assumption named:
1. The drive as flown today (B01 / pass 7 operating point): thrust, jet power, fusion power, mass flow per nozzle, and the acceleration of
   each of the four mission burns.
2. The owner's 1.1-1.5 g target: the power it needs at the full-return masses, and what holding today's power would cost instead.
3. Where the fusion power goes in a D-3He plasma (Bosch-Hale reactivities, relativistic bremsstrahlung, D-D side reactions): charged
   products (the only part a magnetic nozzle can direct), X-rays and neutrons (which go wherever their straight lines go).
4. How much of that radiation the drive's structure intercepts (Monte Carlo over the revision's geometry, fiji_geometry.intercept_scene).
5. The fusion power at which the absorbed heat fits the 1800 K hot loop: the radiation-limited drive.
6. The reactor shadow shield: the protected cone, the cone fraction (the floor of any shield's intercept) and the neutron attenuation the
   habitat needs.

    python3 lab/variants/fiji-drive/fiji_budget.py          # prints the summary, writes lab/variants/fiji-drive/results/budget.json
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
sys.path.insert(0, str(HERE))

import operating_point as op          # noqa: E402
from habitat_ring import G0           # noqa: E402

MEV = 1.602176634e-13
C = 299792458.0
DAY = 86400.0

# ---------- D-3He plasma: reactivities and the power split ----------------------------------------------------------------------------
# Bosch & Hale, Nucl. Fusion 32 (1992) 611, Table VII (T in keV, <sigma v> in cm^3/s). Valid D-3He 0.5-190 keV, D-D 0.2-100 keV.
BH = {
    'DHe3': dict(BG=68.7508, mrc2=1124572.0, C=(5.51036e-10, 6.41918e-3, -2.02896e-3, -1.91080e-5, 1.35776e-4, 0.0, 0.0)),
    'DDn': dict(BG=31.3970, mrc2=937814.0, C=(5.43360e-12, 5.85778e-3, 7.68222e-3, 0.0, -2.96400e-6, 0.0, 0.0)),
    'DDp': dict(BG=31.3970, mrc2=937814.0, C=(5.65718e-12, 3.41267e-3, 1.99167e-3, 0.0, 1.05060e-5, 0.0, 0.0)),
}
E_DHE3 = 18.353*MEV       # p (14.68 MeV) + alpha (3.67 MeV), all charged
E_DDN = (2.45, 0.82)      # neutron, 3He (MeV)
E_DDP = (3.02, 1.01)      # proton, triton (MeV), all charged
E_DT = (14.07, 3.52)      # neutron, alpha (MeV), if the bred tritium burns


def reactivity(kind, T_keV):
    b = BH[kind]; c1, c2, c3, c4, c5, c6, c7 = b['C']; T = T_keV
    theta = T/(1-T*(c2+T*(c4+T*c6))/(1+T*(c3+T*(c5+T*c7))))
    xi = (b['BG']**2/(4*theta))**(1/3)
    return c1*theta*math.sqrt(xi/(b['mrc2']*T**3))*math.exp(-3*xi)*1e-6      # m^3/s


def plasma_split(Ti_keV=100.0, Te_keV=100.0, he3_to_d=1.0, tritium_burn=0.0, synchrotron_fraction=0.01):
    """Fractions of gross fusion power by carrier for a D-3He plasma at ion temperature Ti and electron temperature Te.
    Bremsstrahlung: 5.35e-37 Z_eff n_e^2 sqrt(Te) W/m^3 (NRL formulary) x (1 + 1.78 (Te/511)^1.34) (relativistic correction, Gould/Dawson).
    D-D runs on both branches; the DDp triton burns with probability tritium_burn (an open mirror loses most of it in the exhaust)."""
    nD = 1.0; nHe = he3_to_d; ne = nD+2*nHe; zeff = (nD+4*nHe)/ne
    sv_dhe = reactivity('DHe3', Ti_keV); sv_n = reactivity('DDn', min(Ti_keV, 100.0)); sv_p = reactivity('DDp', min(Ti_keV, 100.0))
    r_dhe = nD*nHe*sv_dhe; r_dd_n = nD*nD/2*sv_n; r_dd_p = nD*nD/2*sv_p; r_dt = r_dd_p*tritium_burn
    p_charged = r_dhe*E_DHE3+r_dd_n*E_DDN[1]*MEV+r_dd_p*sum(E_DDP)*MEV+r_dt*E_DT[1]*MEV
    p_neutron = r_dd_n*E_DDN[0]*MEV+r_dt*E_DT[0]*MEV
    p_fus = p_charged+p_neutron
    # bremsstrahlung per unit n^2 (densities in m^-3 cancel: everything above is per n^2 too, so scale 1e40 for numerics)
    rel = 1+1.78*(Te_keV/511.0)**1.34
    p_brem = 5.35e-37*zeff*ne*ne*math.sqrt(Te_keV)*rel
    f_brem = p_brem/p_fus; f_n = p_neutron/p_fus; f_syn = synchrotron_fraction
    return dict(Ti_keV=Ti_keV, Te_keV=Te_keV, he3_to_d=he3_to_d, z_eff=zeff, sigma_v_DHe3_m3_s=sv_dhe, sigma_v_DDn_m3_s=sv_n,
                sigma_v_DDp_m3_s=sv_p, tritium_burn=tritium_burn, neutron_fraction=f_n, bremsstrahlung_fraction=f_brem,
                synchrotron_fraction=f_syn, radiated_fraction=f_n+f_brem+f_syn, charged_fraction=1-f_n-f_brem-f_syn,
                note='Fractions of gross fusion power. Bremsstrahlung and synchrotron leave the charged channel and are not directable; '
                     'the charged remainder powers the exhaust (directed efficiency 0.8 is the B01 value, inside this ceiling).')


# ---------- the drive as flown and the owner's g target ------------------------------------------------------------------------------

def flown(s):
    b = op.burn(s); m = op.mission(s); F = b['peak_thrust_N']; ve = b['exhaust_velocity_m_s']
    burns = []
    for i, (m0, m1) in enumerate(zip(m['burn_masses_kg'], m['burn_masses_kg'][1:]), 1):
        expelled = m0-m1; t = expelled/(F/ve)
        burns.append(dict(burn=i, start_mass_t=m0/1e3, end_mass_t=m1/1e3, accel_start_g=F/m0/G0, accel_end_g=F/m1/G0, duration_d=t/DAY))
    return dict(thrust_MN=F/1e6, thrust_per_nozzle_MN=F/4e6, exhaust_velocity_km_s=ve/1e3, exhaust_velocity_c=ve/C,
                mass_flow_kg_s=F/ve, mass_flow_per_nozzle_kg_s=F/ve/4, jet_power_TW=b['peak_jet_power_W']/1e12,
                fusion_power_TW=b['peak_fusion_power_W']/1e12, absorbed_GW=b['peak_absorbed_heat_W']/1e9,
                hot_budget_GW=b['hot_budget_W']/1e9, ideal_rejection_GW=b['ideal_rejection_W']/1e9, absorbed_fraction=b['absorbed_fraction'],
                delta_v_per_burn_c=b['delta_v_m_s']/C, mass_ratio_per_burn=m['mass_ratio_per_burn'], burns=burns,
                departure_mass_t=m['departure_mass_kg']/1e3, propellant_t=m['propellant_kg']/1e3)


def g_targets(s, gs=(1.1, 1.5)):
    """Power for the owner's acceleration band at today's ve, and the ve (and mass ratio) if the power stays at today's cap instead."""
    b = op.burn(s); m = op.mission(s); ve = b['exhaust_velocity_m_s']; eta = s['physics']['operating_point']['directed_efficiency']
    f_hot = b['absorbed_fraction']; budget = b['hot_budget_W']; P_jet_now = b['peak_jet_power_W']; dv = b['delta_v_m_s']
    out = []
    for g in gs:
        for label, mass in (('departure (burn 1 start)', m['burn_masses_kg'][0]), ('burn 4 end', m['burn_masses_kg'][-1])):
            F = mass*g*G0; Pj = F*ve/2; Pf = Pj/eta
            ve_alt = 2*P_jet_now/F; R_alt = math.exp(dv/ve_alt)
            out.append(dict(g=g, mass=label, mass_t=mass/1e3, thrust_MN=F/1e6, jet_power_TW=Pj/1e12, fusion_power_TW=Pf/1e12,
                            absorbed_GW_at_f_hot=f_hot*Pf/1e9, hot_budget_GW=budget/1e9, power_vs_today=Pf/(P_jet_now/eta),
                            same_power_ve_km_s=ve_alt/1e3, same_power_mass_ratio_per_burn=R_alt, same_power_mass_ratio_4_burns=R_alt**4))
    return out


# ---------- radiation intercept (Monte Carlo) ----------------------------------------------------------------------------------------

def intercept(scene, rays=200000, seed=7):
    """Fraction of isotropic radiation from the plasma source volume that first meets each absorber; the rest leaves to space."""
    rnd = random.Random(seed); src = scene['source']; hits = {}
    for _ in range(rays):
        r = src['radius']*math.sqrt(rnd.random()); a = 2*math.pi*rnd.random()
        p = (src['x0']+(src['x1']-src['x0'])*rnd.random(), r*math.cos(a), r*math.sin(a))
        mu = 2*rnd.random()-1; ph = 2*math.pi*rnd.random(); st = math.sqrt(1-mu*mu)
        d = (mu, st*math.cos(ph), st*math.sin(ph))
        best, name = math.inf, None
        for obj in scene['absorbers']:
            t = obj['hit'](p, d)
            if t is not None and 1e-6 < t < best:
                best, name = t, obj['name']
        if name:
            hits[name] = hits.get(name, 0)+1
    groups = {}
    for obj in scene['absorbers']:
        groups.setdefault(obj['group'], 0)
        groups[obj['group']] += hits.get(obj['name'], 0)
    return dict(rays=rays, total=sum(hits.values())/rays, by_group={k: v/rays for k, v in sorted(groups.items(), key=lambda kv: -kv[1])})


# ---------- shadow shield and dose ---------------------------------------------------------------------------------------------------

def shadow(s, scene, split, P_fus):
    """Protected cone from the core to the forward structures, the cone's solid-angle fraction (no shield can intercept less while it
    shadows them), and the neutron attenuation that keeps a crew member on ring A under 1 mSv per burn-day."""
    src = scene['source']; xc = (src['x0']+src['x1'])/2
    targets = scene['protected']
    worst = max(targets, key=lambda t: math.atan2(t['r'], t['x']-xc))
    half = math.atan2(worst['r'], worst['x']-xc); cone = (1-math.cos(half))/2
    ring = next(t for t in targets if t['name'] == 'ring A rim'); d = ring['x']-xc
    P_n = split['neutron_fraction']*P_fus; flux = P_n/(E_DDN[0]*MEV)/(4*math.pi*d*d)/1e4      # n/cm^2/s (2.45 MeV dominant)
    h = 3.9e-10                                                                                   # Sv cm^2, ICRP-74 ambient dose, ~2.5 MeV
    rate = flux*h; allowed = 1e-3/DAY; attenuation = allowed/rate
    lam_LiH = 0.11; lam_W = 0.06                                                                  # m, fast-neutron removal lengths (approx.)
    return dict(source_center_x=xc, governing_target=worst['name'], protected_half_angle_deg=math.degrees(half), cone_fraction=cone,
                cone_floor_absorbed_GW=cone*split['radiated_fraction']*P_fus/1e9, ring_A_distance_m=d,
                unshielded_neutron_flux_n_cm2_s=flux, unshielded_dose_Sv_s=rate, required_attenuation=attenuation,
                lih_thickness_m=-math.log(attenuation)*lam_LiH, w_lih_thickness_m=-math.log(attenuation)/(1/lam_LiH*0.6+1/lam_W*0.4),
                note='Point-kernel removal estimate for 2.45 MeV D-D neutrons; secondary gammas, D-T 14 MeV neutrons, scatter round the '
                     'shield edge and the H2/D tank moderation are not included (OPEN: a transport calculation).')


def radiation_limit(s, split, total_intercept, cone):
    """Fusion power whose absorbed radiation fits the drive's share of the hot loop, for the revision's geometry and for an ideal one
    (only the protected cone intercepts), and the acceleration and burn time that power gives at today's ve."""
    b = op.burn(s); m = op.mission(s); ve = b['exhaust_velocity_m_s']; eta = s['physics']['operating_point']['directed_efficiency']
    budget = b['hot_budget_W']; out = {}
    for label, frac in (('revision geometry', total_intercept), ('ideal (cone only)', cone)):
        f_abs = split['radiated_fraction']*frac
        P = budget/f_abs; F = 2*eta*P/ve; m0 = m['burn_masses_kg'][0]; m1 = m['burn_masses_kg'][1]
        out[label] = dict(absorbed_fraction=f_abs, fusion_power_TW=P/1e12, thrust_MN=F/1e6, accel_departure_g=F/m0/G0,
                          burn_1_days=(m0-m1)/(F/ve)/DAY, vs_today_power=P/b['peak_fusion_power_W'])
    out['absorbed_fraction_required_by_today'] = b['absorbed_fraction']
    out['radiated_fraction_that_today_needs_with_ideal_geometry'] = b['absorbed_fraction']/cone
    return out


def report():
    from spec import load
    import fiji_geometry as fg
    s = load(ROOT)[0]; params = fg.params()
    fl = flown(s)
    splits = {name: plasma_split(**kw) for name, kw in params['plasma_cases'].items()}
    base = splits[params['plasma_baseline']]
    scene = fg.intercept_scene(s, params)
    mc = intercept(scene, rays=params['budget']['rays'])
    mc_enclosed = intercept(fg.intercept_scene(s, params, 'enclosed'), rays=params['budget']['rays']//3)
    sh = shadow(s, scene, base, fl['fusion_power_TW']*1e12)
    out = dict(flown=fl, g_targets=g_targets(s), plasma=splits, plasma_baseline=params['plasma_baseline'], intercept=mc, intercept_enclosed=mc_enclosed, shadow=sh,
               absorbed_at_today_power_TW={k: v['radiated_fraction']*mc['total']*fl['fusion_power_TW'] for k, v in splits.items()},
               radiation_limit=radiation_limit(s, base, mc['total'], sh['cone_fraction']))
    (HERE/'results').mkdir(exist_ok=True)
    (HERE/'results/budget.json').write_text(json.dumps(out, indent=1)+'\n')
    return out


if __name__ == '__main__':
    o = report(); f = o['flown']
    print(f"flown: {f['thrust_MN']:.2f} MN ({f['thrust_per_nozzle_MN']:.2f}/nozzle), ve {f['exhaust_velocity_km_s']:.0f} km/s, mdot {f['mass_flow_kg_s']:.3f} kg/s, "
          f"jet {f['jet_power_TW']:.1f} TW, fusion {f['fusion_power_TW']:.1f} TW, absorbed {f['absorbed_GW']:.2f} of {f['hot_budget_GW']:.2f} GW")
    for b in f['burns']:
        print(f"  burn {b['burn']}: {b['start_mass_t']:.0f}->{b['end_mass_t']:.0f} t, {b['accel_start_g']:.2f}-{b['accel_end_g']:.2f} g, {b['duration_d']:.1f} d")
    for g in o['g_targets']:
        print(f"  {g['g']} g at {g['mass']} ({g['mass_t']:.0f} t): {g['thrust_MN']:.1f} MN, fusion {g['fusion_power_TW']:.0f} TW (x{g['power_vs_today']:.2f}), "
              f"same-power ve {g['same_power_ve_km_s']:.0f} km/s -> 4-burn mass ratio {g['same_power_mass_ratio_4_burns']:.1f}")
    for k, p in o['plasma'].items():
        print(f"  plasma {k}: brems {p['bremsstrahlung_fraction']:.3f}, neutrons {p['neutron_fraction']:.4f}, synch {p['synchrotron_fraction']:.3f}, "
              f"radiated {p['radiated_fraction']:.3f}; DHe3 sv {p['sigma_v_DHe3_m3_s']:.3g}")
    print(f"enclosed bay intercept {o['intercept_enclosed']['total']:.4f}: " + ', '.join(f'{k} {v:.4f}' for k, v in o['intercept_enclosed']['by_group'].items()))
    print(f"intercept {o['intercept']['total']:.4f}: " + ', '.join(f'{k} {v:.4f}' for k, v in o['intercept']['by_group'].items()))
    print('absorbed at today power (TW):', {k: round(v, 2) for k, v in o['absorbed_at_today_power_TW'].items()})
    sh = o['shadow']
    print(f"shadow: {sh['governing_target']} {sh['protected_half_angle_deg']:.1f} deg, cone fraction {sh['cone_fraction']:.4f} -> floor {sh['cone_floor_absorbed_GW']:.0f} GW; "
          f"ring A unshielded {sh['unshielded_dose_Sv_s']:.3g} Sv/s, attenuation {sh['required_attenuation']:.2g} -> LiH {sh['lih_thickness_m']:.1f} m")
    for k, v in o['radiation_limit'].items():
        print(' ', k, v)
