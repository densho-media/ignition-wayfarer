"""WSI-F remaining problems at the joint point: C-01 (shutdown bridge vs defense buffer), C-11 (He-3 storage), C-14 (LOW recovery).

    python3 work/wayfarer-systems-integration/wsi/remaining.py      # -> results/wsi_remaining.json

Every physical choice is PROTOTYPE; property data are approximate saturated-liquid values and are labelled for verification against a
reference He-3 equation of state. The shutdown transient (drive decay heat, HOT loop at part flow, Li freeze margins) stays OPEN.
"""
import json
import math

import common
from common import R, S, cs, issa_point, issa_c11
import coupled

# He-3 saturated liquid (approximate; molar volume from low-temperature tables, density = 3.016 g/mol / V). PROTOTYPE: verify vs a He-3 EOS.
HE3 = [  # T_K, rho_kg_m3, P_sat_kPa
    (1.5, 78.3, 4.8), (2.0, 74.5, 16.0), (2.5, 69.3, 38.0), (3.0, 61.6, 74.0), (3.19, 58.9, 101.3), (3.32, 41.5, 114.6)]
CP_HE3 = 4.5e3        # J/kg/K liquid He-3 near 2-3 K (order; diverges toward the critical point)
CP = dict(hydrogen=9.7e3, deuterium=5.5e3)


def he3_at(T):
    for (t0, r0, p0), (t1, r1, p1) in zip(HE3, HE3[1:]):
        if t0 <= T <= t1:
            f = (T-t0)/(t1-t0); rho = r0+f*(r1-r0); beta = -math.log(r1/r0)/(t1-t0)
            return dict(T_K=T, rho=rho, beta_per_K=beta, P_sat_kPa=p0+f*(p1-p0))
    raise ValueError(T)


def c11_options(P):
    """He-3 storage options at the joint point: density, expansion allowance, vessel volume, farm length, cooling input, hold time."""
    he3_t = P['T']['loaded_by_species_t']['helium-3']; v_he3 = [v for v in P['T']['vessels'] if v['species'] == 'helium-3']
    stage3 = next(s for s in P['C']['stages'] if s['stage'].startswith('3 K')); lift3 = stage3['lift_W']; wpw3 = stage3['W_per_W']
    base_rho = 58.61; out = []
    for oid, T, ull, ctrl in (('H0 C1.1 as built (3.0 K, 3 % ullage, density 58.61 = a 3.19 K value)', 3.0, 0.03, 0.05),
                              ('H1 3.0 K, consistent density, ullage for +0.3 K (preferred)', 3.0, None, 0.30),
                              ('H2 2.5 K, ullage for +0.3 K', 2.5, None, 0.30),
                              ('H3 2.0 K, ullage for +0.5 K', 2.0, None, 0.50),
                              ('H4 supercritical 3.5 K, 0.3 MPa (no phase boundary)', 3.5, 0.03, 1.0)):
        if T > 3.32:
            pr = dict(T_K=T, rho=46.0, beta_per_K=0.06, P_sat_kPa=300.0)
        else:
            pr = he3_at(T)
        exp_need = pr['beta_per_K']*ctrl; ullage = ull if ull is not None else max(0.03, 0.01+exp_need)
        vol_factor = (base_rho/pr['rho'])*((1+ullage)/1.03) if oid[:2] != 'H0' else 1.0
        carnot = (300.0/T-1)/(300.0/3.0-1)
        cool_in = lift3*wpw3*carnot
        e_hold = he3_t*1e3*CP_HE3*min(ctrl, 0.5)
        hold_d = e_hold/(lift3*0.375)/86400                                 # one head lost: deficit = 37.5 % of the station lift
        allowed = (ullage-0.01)/pr['beta_per_K']
        out.append(dict(id=oid, T_K=T, rho_kg_m3=pr['rho'], beta_per_K=pr['beta_per_K'], P_kPa=pr['P_sat_kPa'], ullage=ullage, allowed_warm_K=allowed,
                        he3_volume_factor=vol_factor, he3_capacity_m3=sum(v['volume_m3'] for v in v_he3)*vol_factor, cooler_input_3K_W=cool_in,
                        hold_days_one_head_lost=hold_d, control_K=ctrl,
                        notes=('as built: the 58.61 kg/m3 density belongs to ~3.19 K (NBP); at 3.0 K the liquid is ~5 % denser, and the 2 % expansion share holds only +0.1 K'
                               if oid[:2] == 'H0' else 'sub-atmospheric vapour pressure: feed by a cold pump or a He-3 gas pressurant loop (no He-4 contamination)'
                               if pr['P_sat_kPa'] < 50 else 'near-critical: expansion and compressibility large' if T >= 3.0 else '')))
    return out


def he3_farm(P, T_K, ullage):
    """Re-solve the joint point with the He-3 density and ullage of an option (effective density carries the ullage difference)."""
    import fuel_storage as fs
    pr = he3_at(T_K); orig = fs.cfg
    def cfg(s):
        c = orig(s); c = dict(c); d = dict(c['density_kg_m3']); d['helium_3'] = pr['rho']*1.03/(1+ullage); c['density_kg_m3'] = d; return c
    fs.cfg = cfg
    try:
        Q = issa_point(P['L']['structure_t'])
    finally:
        fs.cfg = orig
    return dict(departure_t=Q['L']['departure_t'], farm_added_m=Q['T']['added_length_m'], ship_length_m=Q['T']['ship_length_m'], tankage_t=Q['L']['tankage_t'],
                shell_area_m2=Q['T']['shell_area_m2'])


def c01(P, C11):
    """Shutdown bridge after an L1 pickup fault vs the defense buffer. EM-pump electrical power at part flow: P = P0 (a + (1-a) q^3)
    (hydraulic ~ q^3, fixed coil/eddy/excitation share a). Bridge = energy above the L2 surplus during the 30 s ramp and after it."""
    PF = C11['pickup_fault']; P0 = PF['part_flow_W']/0.15; sur_c11 = PF['surplus_EOL_W']
    d_cryo = P['C']['operating_input_W']-C11['cryo']['operating_input_W']
    sur = sur_c11-d_cryo; buf = PF['buffer_J']; rows = []
    for a in (0.0, 0.1, 0.2, 0.3):
        q = 0.15; Pp = P0*(a+(1-a)*q**3) if a > 0 else 0.15*P0
        ramp = 30.0; n = 300; E = 0.0
        for i in range(n):
            t = (i+0.5)/n; qq = 1-(1-q)*t; Pt = P0*(a+(1-a)*qq**3) if a > 0 else P0*qq
            E += max(0.0, Pt-sur)*ramp/n
        steady_deficit = max(0.0, Pp-sur)
        rows.append(dict(fixed_share=a, model='linear (C1.1)' if a == 0 else f'q^3 hydraulic + {a:.0%} fixed', part_flow_power_W=Pp, bridge_J=E,
                         steady_deficit_W=steady_deficit, closes=steady_deficit == 0))
    worst = max(rows, key=lambda r: r['bridge_J'])
    store_J = 2*worst['bridge_J']; e_spec = 0.15e6; p_spec = 3.0e3
    store_t = max(store_J/e_spec, (P0-sur)/p_spec)/1e3
    return dict(P0_W=P0, surplus_EOL_W=sur, surplus_change_W=-d_cryo, buffer_J=buf, cases=rows,
                shared_doctrine=dict(reserve_J=2*rows[0]['bridge_J'], defense_left_J=buf-2*rows[0]['bridge_J'],
                                     verdict='C1.1 shared doctrine leaves the defense only 44 MJ of 209 MJ while the drive runs; with the q^3 + fixed-loss pump model the '
                                             'reserve can exceed the buffer: not acceptable as the only bridge'),
                dedicated=dict(energy_J=store_J, power_W=P0-sur, mass_t=store_t, tech='high-power Li-ion / hybrid capacitor pack on the essential services bus (Track R, '
                               '150 kJ/kg, 3 kW/kg pack level)', location='services bus beside the L2 tie, x -92..-80 (LOW-cooled, cell limit 330 K)',
                               verdict=f'recommended: {store_t:.1f} t dedicated shutdown store; the defense buffer keeps its full {buf/1e6:.0f} MJ'),
                transfer_path=['L1 isolators open (fault)', 'services bus transfers to L2 tie (>= 3 MW, < 50 ms) + dedicated store', 'H6a pump drives ramp 30 s',
                               'store recharges from L2 surplus after the ramp'],
                flow_vs_power='flow fraction is not the pump-power fraction: hydraulic power falls ~q^3 but EM-pump coil/excitation losses do not, so electrical '
                              'power at 15 % flow is 0.3-30 % of full power depending on the fixed share; the pump vendor curve decides (OPEN)',
                open='drive decay heat, HOT loop at part flow and Li freeze margins in the transient: NOT verified (C-01 transient OPEN)')


def c14(P, Q_low):
    """LOW with one loop lost: reduced-rate recovery and vessel hold times (design margin vs emergency capacity)."""
    lc = Q_low; C = P['C']
    st20 = next(s for s in C['stages'] if s['stage'].startswith('20 K'))
    holds = []
    for sp in ('hydrogen', 'deuterium'):
        vs = [v for v in P['T']['vessels'] if v['species'] == sp]; m = min(v['prop_t'] for v in vs)*1e3
        beta = 0.016 if sp == 'hydrogen' else 0.009; allowed = 0.02/beta
        lift_v = st20['lift_W']/len(P['T']['vessels']); deficit = 0.375*lift_v
        holds.append(dict(species=sp, smallest_vessel_t=m/1e3, allowed_warm_K=allowed, hold_days_one_head_lost=m*CP[sp]*allowed/deficit/86400))
    sig = 5.670374e-8; T = lc['T_K']; q = 2*0.85*sig*(T**4-4.0**4)            # two-sided LOW panel W/m2 at T
    have = lc['rows'][0]['capacity_W']; one = lc['rows'][2]['capacity_W']/have; load = lc['rows'][0]['load_W']; rec = lc['rows'][1]['load_W']
    need_nom = max(0.0, 1.10*load-have); need_one = max(0.0, load/one-have); need_rec_one = max(0.0, rec/one-have)
    growth = dict(panel_W_m2=q, for_nominal_10pct_W=need_nom, for_one_loop_lost_nominal_W=need_one, for_one_loop_lost_full_recovery_W=need_rec_one,
                  area_m2=dict(nominal_10pct=need_nom/q, one_loop_lost=need_one/q, one_loop_full_recovery=need_rec_one/q),
                  verdict=('at the joint point the bigger farm raises the cryo rejection: LOW must grow by the one-loop-lost amount (area above) so that '
                           'one loop lost still carries nominal; the 125 % recovery is then an operating choice, not a design case'))
    return dict(low_growth=growth, low_cases=lc, rule=('one LOW loop lost: cap the cryocooler input at the operating point (100 %), no 125 % surge; re-cool at the reduced rate '
                                    f'(<= {100*lc["recovery_limit_one_loop"]:.0f} % allowed); a 332 K float is NOT allowed (cell limit 330 K)'),
                vessel_holds=holds, design_margin_W=lc['rows'][0]['margin_W'], emergency_capacity_W=lc['rows'][2]['margin_W'],
                verdict='vessel hold times are weeks to months, so recovery does not need the 125 % rate; the LOW design margin covers nominal operation, the '
                        'emergency capacity (one loop lost) covers operation at 100 % cooler input')


def main():
    C11, _ = issa_c11()
    s14 = sum(coupled.FAM.values())
    P = issa_point(s14-common.STRUCT_LINE_T); P['L']['structure_t'] = s14-common.STRUCT_LINE_T
    opts = c11_options(P)
    for o in opts:
        if o['T_K'] <= 3.32 and not o['id'].startswith('H0'):
            o.update(farm=he3_farm(P, o['T_K'], o['ullage']))
    low = cs.low_cases(P['RAD'], P['C'])
    out = dict(point='S-COMB (WSI-0.1)', c11=dict(options=opts, recommendation='H1: keep 3.0 K, correct the density (61.6 kg/m3 at 3.0 K, not the 3.19 K value '
                                                  '58.61) and raise the He-3 ullage to 8 % so the liquid may warm +0.3 K: the denser liquid pays for the extra ullage, the farm '
                                                  'length is set by the D2/H2 classes, and no cooler input is added. H3 (2.0 K) gives more allowance but adds ~290 kW of cooler '
                                                  'input and LOW rejection, which the joint point cannot afford. Bulk hold time with one head lost is months; the residual '
                                                  'risk is stratification (mixing pump per vessel). Property data must be verified against a He-3 EOS before adoption.'),
               c01=c01(P, C11), c14=c14(P, low))
    (R/'wsi_remaining.json').write_text(json.dumps(out, indent=1, default=float))
    for o in opts:
        print(o['id'], round(o['rho_kg_m3'], 1), round(o['beta_per_K'], 3), round(o['ullage'], 3), round(o['allowed_warm_K'], 2), round(o['he3_volume_factor'], 3),
              round(o['cooler_input_3K_W']/1e3, 1), 'kW', round(o['hold_days_one_head_lost']), 'd', o.get('farm', {}))
    print('C-01', [(r['model'], round(r['part_flow_power_W']/1e6, 2), round(r['bridge_J']/1e6), r['closes']) for r in out['c01']['cases']], out['c01']['dedicated']['mass_t'],
          out['c01']['surplus_EOL_W'])
    print('C-14', out['c14']['rule'], [(h['species'], round(h['hold_days_one_head_lost'])) for h in out['c14']['vessel_holds']], [(r['case'][:30], round(r['margin_W']/1e3)) for r in low['rows']])


if __name__ == '__main__':
    main()
