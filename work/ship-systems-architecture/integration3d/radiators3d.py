"""3D integration Stage E: radiators with internal cross-sections. STUDY, PROTOTYPE, noncanon, Track F1.

RAD-L2 (M3): the 950 K-class L2 section of each blade. Function: reject the L2 units' waste heat (two survivors at full load x 1.2 margin,
cross-strapped) while the ship accelerates in a burn and while it coasts.
Calculated here:
  1. the closed-Brayton cycle behind FT-03 (1500 K turbine inlet): the compressor inlet that actually gives eta 0.154, and from it the
     gas-cooler range, the NaK loop range and the emission-equivalent radiating temperature (Phase VI used an isothermal 950 K);
  2. the section length from the Phase IV relation with that temperature profile and the face-sheet fin efficiency;
  3. NaK transport loops (gas cooler -> section), header serpentines, pump power, insulation leak, mass;
  4. potassium heat pipes: sonic, capillary (coast) and flooding (burn, thermosyphon) limits, count, mass;
  5. failure cases: unit trip with header-flow biasing, one loop lost, pipe-loss allowance.
RAD-HOT, RAD-WL (M2): internal cross-sections; the HOT Li fins checked against burn acceleration; WARM/LOW interleaved A/B pumped panels.
TH-H6A view factor (Checkpoint 2 OPEN item): the trunks' shading of the HOT blade root, 2D parallel-cylinder view factor with shadowing.
Writes ../results/i3d_radiators.json and i3d_l2_section.svg, i3d_l2_plan.svg, i3d_blade_sections.svg.
"""
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent; W = HERE.parent; R = W/'results'
sys.path.insert(0, str(W/'phase6')); sys.argv = sys.argv[:1]
import study6 as s6  # noqa: E402

CFG = tomllib.loads((HERE/'f1_integration.toml').read_text()); C = CFG['radiators']
P6 = json.loads((R/'phase6.json').read_text()); PW = json.loads((R/'i3d_power.json').read_text())
SIG = s6.s3.SIG; EPS = s6.s3.EPS; F_SPACE = s6.s4.F_SPACE; MARGIN = s6.s3.MARGIN; BULK = s6.BULK; G0 = 9.80665
ABSORB = s6.s4.ALPHA*s6.s4.EPS_HOT*SIG*s6.s4.T_HOT**4*3e-4          # the Phase VI F_hot = 3e-4 absorption on the L2 section
RF = P6['radiators']['F1']; FT03 = dict(T_hot=1500.0, eta=RF['eta'], T_rej=RF['T_K'])
A_PEAK = P6['hot']['F1']['a_g']                                       # peak burn acceleration (g), as the H6a head uses
A_LOW = min(r['a_departure_g'] for r in P6['accel']['F1'])            # lowest burn acceleration of the three cases


# ------------------------------------------------------------------------------------------------------------- 1 cycle consistency
def cycle(Tci, et, ec, eps, dp, gen=0.95, k=0.4, Tti=1500.0):
    """Recuperated closed Brayton (He-Xe, gamma 5/3), pressure ratio optimised; returns eta_e and the gas-cooler range."""
    best = None
    for i in range(1, 600):
        x = 1+i*0.0005; PR = x**(1/k); xt = (PR*(1-dp))**k
        wt = Tti*et*(1-1/xt); wc = Tci*(x-1)/ec; Tco = Tci+wc; Tto = Tti-wt
        if wt <= wc or Tto <= Tco: continue
        hin = Tco+eps*(Tto-Tco); gci = Tto-eps*(Tto-Tco); e = (wt-wc)/(Tti-hin)*gen
        if best is None or e > best['eta']:
            best = dict(eta=e, PR=PR, T_comp_out=Tco, T_turb_out=Tto, T_gc_in=gci, T_ci=Tci)
    return best


def solve_Tci(target, **kw):
    lo, hi = 600.0, 1100.0
    for _ in range(60):
        mid = (lo+hi)/2
        if cycle(mid, **kw)['eta'] > target: lo = mid
        else: hi = mid
    return cycle(lo, **kw)


def cycles():
    cy = C['cycle']; base = dict(et=cy['eta_t'], ec=cy['eta_c'], eps=cy['recup_eff'], dp=cy['dp_frac'])
    adv = dict(et=0.94, ec=0.90, eps=0.97, dp=0.02)
    rows = []
    for tag, kw in (('contemporary-class components (eta_t 0.92, eta_c 0.88, recuperator 0.95, dp 3 %)', base),
                    ('FT-03 advanced components (eta_t 0.94, eta_c 0.90, recuperator 0.97, dp 2 %)', adv)):
        at950 = cycle(FT03['T_rej'], **kw); need = solve_Tci(FT03['eta'], **kw)
        rows.append(dict(components=tag, kw=kw, eta_at_950K=at950['eta'], Tci_for_0154=need['T_ci'], T_ci=need['T_ci'], PR=need['PR'], T_gc_in=need['T_gc_in'],
                         T_turb_out=need['T_turb_out'], T_comp_out=need['T_comp_out']))
    pick = rows[1]
    return dict(rows=rows, pick=pick, carnot_model=dict(carnot_fraction=0.42, T_reject_K=FT03['T_rej'], eta=FT03['eta']),
                finding=(f'The Carnot-fraction relation (0.42 x (1 - 950/1500) = 0.154) is not a cycle: a recuperated He-Xe Brayton at 1500 K reaches only '
                         f'{rows[0]["eta_at_950K"]:.3f} (contemporary-class) or {rows[1]["eta_at_950K"]:.3f} (advanced) with a 950 K compressor inlet. eta 0.154 '
                         f'needs the compressor inlet at {rows[0]["Tci_for_0154"]:.0f} K or {rows[1]["Tci_for_0154"]:.0f} K. The working assumption here keeps '
                         f'eta 0.154 and the waste heat, adopts the advanced component set as part of FT-03 (owner decision DR-3D-02) and lets the radiator '
                         f'run cooler: gas cooler {pick["T_gc_in"]:.0f} -> {pick["Tci_for_0154"]:.0f} K.'))


# ------------------------------------------------------------------------------------------------------------- 2 section sizing
def fin_eff(T, k, t, pitch, D, eps=EPS):
    h = 4*eps*SIG*T**3; m = math.sqrt(h/(k*t)); L = (pitch-D)/2; ef = math.tanh(m*L)/(m*L) if L > 0 else 1.0
    return dict(fin=ef, overall=(D+ef*(pitch-D))/pitch, mL=m*L, h_rad=h)


def k_props(T):
    """Potassium, approximate correlations (+-15 %): liquid density, surface tension, viscosity, latent heat, vapour pressure (Clausius-
    Clapeyron from the 1032 K normal boiling point, 79.1 kJ/mol)."""
    p = 101325.0*math.exp(-79100/8.314*(1/T-1/1032.0)); M = 0.0391
    return dict(rho_l=909.0-0.243*T, sigma=0.1157-6.4e-5*(T-336.0), mu=1.5e-4*(900.0/T), hfg=2.0e6, p_v=p, rho_v=p*M/(8.314*T), Rv=8.314/M)


def hp_limits(T, hp, L_cond, a_g):
    k = k_props(T); Di = hp['od_m']-2*hp['wall_m']-2*hp['wick_m']; Av = math.pi*Di**2/4; g = 1.67
    sonic = Av*k['rho_v']*k['hfg']*math.sqrt(g*k['Rv']*T/(2*(g+1)))
    KA = hp['arteries']*math.pi*hp['artery_d_m']**4/128; Leff = 0.2+L_cond/2; dPc = 2*k['sigma']/hp['r_pore_m']
    cap = dPc*KA*k['rho_l']*k['hfg']/(k['mu']*Leff)
    # burn: aft evaporator, the condensate drains aft (thermosyphon); counter-current flooding limit (Faghri, Kutateladze form)
    ga = a_g*G0; Bo = Di*math.sqrt(ga*(k['rho_l']-k['rho_v'])/k['sigma']); Kk = (k['rho_l']/k['rho_v'])**0.14*math.tanh(Bo**0.25)**2
    flood = Kk*k['hfg']*Av*(ga*k['sigma']*(k['rho_l']-k['rho_v']))**0.25*(k['rho_v']**-0.25+k['rho_l']**-0.25)**-2
    entr = Av*k['hfg']*math.sqrt(k['sigma']*k['rho_v']/(2*hp['r_pore_m']))       # wicked pipe: the liquid returns in screen and arteries
    return dict(T_K=T, sonic_W=sonic, capillary_coast_W=cap, entrainment_W=entr, flooding_wickless_W=flood, capillary_head_Pa=dPc, p_v_Pa=k['p_v'], core_d_m=Di)


def section(cyc):
    hp = C['heat_pipe']; fc = C['face']; nk = C['nak']; pc = C['cycle']['pinch_K']
    T_hot_nak = cyc['T_gc_in']-pc; T_cold_nak = cyc['T_ci']-pc                      # counter-flow gas cooler, pinch at both ends
    Tv1, Tv0 = T_hot_nak-hp['dT_K'], T_cold_nak-hp['dT_K']
    Q_des = RF['capacity_W']/3                                                       # per blade, two survivors at full load x 1.2
    # emission-equivalent temperature over the serpentine (sensible heat in, radiation out)
    n = 400; A = 0.0; mcp = Q_des/(Tv1-Tv0); fe = []
    for i in range(n):
        Tv = Tv1-(i+0.5)*(Tv1-Tv0)/n; f = fin_eff(Tv, fc['k_W_mK'], fc['t_m'], hp['pitch_m'], hp['od_m']); fe.append(f['overall'])
        q = 2*(EPS*SIG*Tv**4*F_SPACE*f['overall']-ABSORB)                           # W per m2 of blade planform (two faces)
        A += mcp*(Tv1-Tv0)/n/q
    A_iso = Q_des/(2*(EPS*SIG*FT03['T_rej']**4*F_SPACE-ABSORB))
    T_eff = (Q_des/(A*2*EPS*SIG*F_SPACE))**0.25
    L = A/C['span_active_m']; L6 = RF['length_m']
    per_m_hot = RF['hot_capacity_W']/RF['hot_length_m']
    return dict(T_nak_hot=T_hot_nak, T_nak_cold=T_cold_nak, T_vapour=(Tv1, Tv0), Q_design_per_blade_W=Q_des, planform_m2=A, planform_iso950_m2=A_iso,
                T_emission_equivalent_K=T_eff, fin_overall=(min(fe), max(fe)), length_m=L, length_phase6_m=L6, delta_m=L-L6, x0=BULK-L, x1=BULK,
                hot_headroom_change_W=-(L-L6)*per_m_hot, per_m_hot_W=per_m_hot, area_total_faces_m2=2*3*A)


def heat_pipes(S):
    hp = C['heat_pipe']; nb = C['bays']; bay = S['length_m']/nb; Lc = bay-0.45; Lp = bay-0.15
    n_row = int(C['span_active_m']/hp['pitch_m']); n = 2*nb*n_row
    Tv1, Tv0 = S['T_vapour']; f1 = fin_eff(Tv1, C['face']['k_W_mK'], C['face']['t_m'], hp['pitch_m'], hp['od_m'])['overall']
    load = lambda T: EPS*SIG*T**4*F_SPACE*fin_eff(T, C['face']['k_W_mK'], C['face']['t_m'], hp['pitch_m'], hp['od_m'])['overall']*hp['pitch_m']*Lc
    rows = []
    for T in (Tv1, (Tv1+Tv0)/2, Tv0):
        for a, tag in ((0.0, 'coast'), (A_LOW, 'burn, lowest acceleration'), (A_PEAK, 'burn, peak acceleration')):
            lim = hp_limits(T, hp, Lc, a if a else 1e-6); Q = load(T)
            governing = min(lim['sonic_W'], lim['entrainment_W'], lim['capillary_coast_W'] if a == 0.0 else math.inf)
            rows.append(dict(T_K=T, state=tag, a_g=a, load_W=Q, sonic_W=lim['sonic_W'], capillary_W=lim['capillary_coast_W'] if a == 0.0 else None,
                             entrainment_W=lim['entrainment_W'], flooding_wickless_W=lim['flooding_wickless_W'] if a else None, margin=governing/Q))
    mass_t = n*Lp*hp['kg_per_m']/1e3
    gravity_fwd = k_props(Tv0)['rho_l']*A_PEAK*G0*Lc
    return dict(per_blade=n, per_row=n_row, rows_per_blade=2*nb, length_m=Lp, condenser_m=Lc, bay_chord_m=bay, mass_t_per_blade=mass_t, limits=rows,
                min_margin=min(r['margin'] for r in rows), load_max_W=load(Tv1),
                wickless_rejected=(f'A wickless thermosyphon would be simpler, but its counter-current flooding limit at this vapour density is only '
                                   f'{min(r["flooding_wickless_W"] for r in rows if r["flooding_wickless_W"])/1e3:.1f}-{max(r["flooding_wickless_W"] for r in rows if r["flooding_wickless_W"])/1e3:.1f} kW '
                                   f'against {load(Tv0)/1e3:.1f}-{load(Tv1)/1e3:.1f} kW per pipe: the screen wick and arteries carry the liquid in burns as well as in coast.'),
                orientation=(f'Evaporators at the AFT edge of each bay: in a burn the acceleration ({A_LOW:.2f}-{A_PEAK:.2f} g) drains the condensate back to '
                             f'them (thermosyphon). A forward evaporator would need {gravity_fwd/1e3:.1f} kPa of capillary head against '
                             f'{hp_limits(Tv0, hp, Lc, 0)["capillary_head_Pa"]/1e3:.1f} kPa available: it would dry out in every burn.'))


def nak(S):
    nk = C['nak']; lp = C['loop']; dT = S['T_nak_hot']-S['T_nak_cold']; cp = nk['cp']; rho = nk['rho']
    gc = next(p for p in PW['unit']['parts'] if p['key'] == 'gas_cooler'); x_gc = PW['district'][0]['centre'][0]+gc['u']
    Q_unit = RF['waste_per_unit_full_W']                                    # a survivor at full load
    def pipe(Q, v):
        md = Q/(cp*dT); V = md/rho; D = math.sqrt(4*V/(math.pi*v)); kgm = math.pi*D*nk['wall_m']*nk['wall_rho']+math.pi*D**2/4*rho+nk['insul_kg_m']
        return dict(mdot=md, D=D, kg_m=kgm, V=V)
    tr = pipe(Q_unit, nk['v_m_s']); run = S['x0']-x_gc; L_tr = 2*run; br = pipe(Q_unit/2, nk['v_m_s']); L_br = 2*2*lp['branch_m']
    # header serpentine per loop per blade: out along bay-1 aft edge, back along bay-2 aft edge; sized for the biased case (one loop carries the blade)
    Qb = 2*Q_unit/3; hd = pipe(Qb, nk['v_m_s']); L_hd = 2*(C['tip_r_m']-C['root_r_m'])
    f = 0.014; dp_tr = f*(L_tr+L_br)/tr['D']*rho*nk['v_m_s']**2/2+lp['dp_fixed_Pa']; pump = dp_tr*tr['V']/nk['pump_eff']
    Tm = (S['T_nak_hot']+S['T_nak_cold'])/2; leak = nk['eps_eff']*SIG*(Tm**4-nk['env_K']**4)*math.pi*(tr['D']+0.06)*L_tr
    m_tr = (tr['kg_m']*L_tr+br['kg_m']*L_br)/1e3; m_hd = 2*hd['kg_m']*L_hd/1e3
    rbus = CFG['electrical']['bus_radius_m']; rl = lp['radius_m']; off = math.radians(lp['offset_deg'])
    clr_bus = math.sqrt(rl**2+rbus**2-2*rl*rbus*math.cos(off))-tr['D']/2-0.03-C['bus_duct_radius_m']
    gap = (CFG['district']['hull_radius_m']-0.4, CFG['district']['hull_radius_m'])         # casing (5.6) to hull (6.0)
    fits = tr['D']+0.06 <= gap[1]-gap[0]
    return dict(x_gas_cooler=x_gc, run_m=run, transport=dict(D_m=tr['D'], mdot=tr['mdot'], kg_m=tr['kg_m'], length_m=L_tr+L_br, mass_t_per_loop=m_tr),
                header=dict(D_m=hd['D'], mdot=hd['mdot'], length_m=L_hd, mass_t_per_blade=m_hd, sized_for_W=Qb),
                pump_W_per_loop=pump, dp_Pa=dp_tr, leak_W_per_loop=leak, clear_to_bus_m=clr_bus, annulus=gap, fits_annulus=fits,
                v_nominal_m_s=nk['v_m_s']*(2/3), dT_K=dT,
                route='casing-hull annulus at the azimuth between the unit\'s two blades (150 / 270 / 30), supply and return at +-20 deg (clear of the bus ducts); branches '
                      'through the hull at the two blade roots')


def failures(S):
    Q_unit = RF['waste_per_unit_full_W']; Q_des = S['Q_design_per_blade_W']
    eta_p = s6.eta_part(2/3); q23 = 3.5e6*2/3*(1/(FT03['eta']*eta_p)-1)
    rows = [dict(case='normal: three units at 2/3 load (strategy C)', blade_W=[q23]*3, header_split='50/50', ok=True),
            dict(case='unit trip, survivors at 100 %, fixed 50/50 split', blade_W=[Q_unit/2, Q_unit/2, Q_unit], header_split='50/50', ok=Q_unit <= Q_des),
            dict(case='unit trip, survivors at 100 %, header biasing 67/33', blade_W=[2*Q_unit/3]*3, header_split='67/33 (flow control valves)', ok=2*Q_unit/3 <= Q_des),
            dict(case='one NaK loop lost (unit runs on its other loop only: derated to its single-blade share)', blade_W=[Q_unit/2+Q_unit/2*0, Q_unit, Q_unit],
                 header_split='100/0 on the faulted unit', ok=Q_unit <= Q_des)]
    for r in rows: r['max_W'] = max(r['blade_W']); r['use'] = r['max_W']/Q_des
    pipe_loss = 1-2*Q_unit/3/Q_des
    return dict(rows=rows, design_W=Q_des, pipe_loss_allowance=pipe_loss,
                note=('Each unit feeds loop A of its own blade and loop B of the next blade. A trip with a fixed split overloads the blade shared by '
                      'the survivors; flow-control valves on each unit\'s two branches bias the split 67/33 and bring every blade to '
                      f'{2*Q_unit/3/1e6:.1f} MW of {Q_des/1e6:.1f} MW. The {pipe_loss*100:.0f} % left is the heat-pipe loss allowance (MMOD, freeze, '
                      'priming) in that case.'))


# ------------------------------------------------------------------------------------------------------------- HOT / WARM / LOW
def hot_fins():
    h = C['hot']; dPc = 2*h['sigma_li']/h['r_pore_m']; L0 = s6.hot.FIN_SPACING/2
    c = dPc/L0**2; rg = h['rho_li']*A_PEAK*G0
    L = (-rg+math.sqrt(rg**2+4*c*dPc))/(2*c)
    derate = (1+L/L0)/2
    loss = (1-derate)*RF['hot_capacity_W']
    return dict(fin_half_m=L0, capillary_head_Pa=dPc, gravity_Pa_per_m=rg, aft_half_effective_m=L, aft_half_share=L/L0, capacity_factor=derate,
                capacity_loss_W=loss, mitigation_manifolds_per_blade=2*int(round(RF['hot_length_m']/s6.hot.FIN_SPACING)),
                manifold_walls_extra_t=P6['hot']['F1']['by_item_t']['manifold_walls'][1],
                note=('Each radial manifold feeds Li heat-pipe fins 1.47 m fore and aft. In a burn the aft-pointing half returns its condensate against the '
                      f'acceleration: at {A_PEAK:.2f} g it carries heat only over {L:.2f} m of {L0:.2f} m, so the blade loses {(1-derate)*100:.1f} % '
                      f'({loss/1e9:.2f} GW) at peak acceleration. Mitigation: forward-pointing fins only (manifold at the aft end of every fin, pitch 1.47 m): '
                      f'{2*int(round(RF["hot_length_m"]/s6.hot.FIN_SPACING))} manifolds per blade and about +{P6["hot"]["F1"]["by_item_t"]["manifold_walls"][1]:.0f} t of manifold walls.'))


def panels(key, T, Q, x0, x1):
    p = C[key]; f1 = fin_eff(T, p['k_W_mK'], p['t_m'], p['pitch_m'], p['tube_od_m']); f2 = fin_eff(T, p['k_W_mK'], p['t_m'], 2*p['pitch_m'], p['tube_od_m'])
    L = x1-x0; n_tubes = int(L/p['pitch_m'])
    md = Q/(p['cp']*p['dT_K'])
    return dict(T_K=T, design_W=Q, x=(x0, x1), fluid=p['fluid'], tubes_per_face=n_tubes, pitch_m=p['pitch_m'], eta_both_loops=f1['overall'], eta_one_loop=f2['overall'],
                capacity_after_loop_loss=f2['overall']/f1['overall'], mdot_kg_s=md,
                note=(f'Interleaved A/B U-tubes from two root manifolds; with one loop lost the fin pitch doubles and the panel keeps '
                      f'{f2["overall"]/f1["overall"]*100:.0f} % of its capacity at the same temperature (margin {MARGIN:.1f} covers '
                      f'{"all" if f2["overall"]/f1["overall"] >= 1/MARGIN else "not all"} of it).'))


# ------------------------------------------------------------------------------------------------------------- H6a trunk view factor
def trunk_view():
    H = json.loads((R/'i3d_h6a.json').read_text()); G = H['geometry']; n = H['network']
    a = n['D_trunk']/2+n['t_trunk']; h_list = [G['t_supply']-0.225, G['t_return']-0.225]; rt = G['r_trunk_axis']
    span = C['tip_r_m']-C['root_r_m']; N = 3000; tot = 0.0; tot_one = 0.0
    for i in range(N):
        r = C['root_r_m']+(i+0.5)*span/N; s = r-rt
        iv = []
        for h in h_list:
            d = math.hypot(s, h); al = math.asin(min(1.0, a/d)); th = math.atan2(h, s)      # angle above the face, from the +r direction
            phi_c = math.pi/2-th                                                           # from the face normal
            iv.append((phi_c-al, phi_c+al))
        iv.sort(); u = []
        for lo, hi in iv:
            lo, hi = max(lo, -math.pi/2), min(hi, math.pi/2)
            if u and lo <= u[-1][1]: u[-1] = (u[-1][0], max(u[-1][1], hi))
            else: u.append((lo, hi))
        F = sum(0.5*(math.sin(hi)-math.sin(lo)) for lo, hi in u); tot += F*span/N
        tot_one += 0.5*(math.sin(iv[0][1])-math.sin(iv[0][0]))*span/N
    frac = tot/span; loss = frac*RF['hot_capacity_W']
    return dict(shade_equiv_m=tot, span_m=span, fraction=frac, loss_bound_W=loss, supply_only_fraction=tot_one/span,
                note=('2D view factor from each HOT blade face to its own trunk pair (supply and return, return partly hidden behind the supply), '
                      'integrated over the span. The bound counts that solid angle as lost to space; it holds for insulated trunks (refractory '
                      'multi-foil, which keeps the network model\'s adiabatic trunks and keeps the hull at the root from seeing 1990 K). Bare trunks '
                      'would add radiating area but cool the supply before the sections (network model OPEN).'))


# ------------------------------------------------------------------------------------------------------------- geometry for Blender
def geometry(S, HP, NK):
    """Parts in the blade frame of az: P(x, r, t). Shared meshes: one heat-pipe row mesh per bay, reused for both faces and all blades."""
    hp = C['heat_pipe']; nb = C['bays']; bay = HP['bay_chord_m']; parts = []
    r0 = C['root_r_m']+(C['tip_r_m']-C['root_r_m']-C['span_active_m'])/2; r1 = r0+C['span_active_m']; tf = C['blade_t_m']/2
    for k in range(nb):
        xa = S['x0']+k*bay
        parts.append(dict(kind='hp_row', bay=k, x0=xa+0.1, x1=xa+bay-0.05, r0=r0, r1=r1, pitch=hp['pitch_m'], d=hp['od_m'], t=tf-hp['od_m']/2-0.002))
        for j, (loop, dx) in enumerate((('A', 0.14), ('B', 0.36))):
            parts.append(dict(kind='header', bay=k, loop=loop, x=xa+dx, r0=C['root_r_m']+0.2, r1=C['tip_r_m']-0.3, d=NK['header']['D_m']))
        parts.append(dict(kind='saddle', bay=k, x0=xa+0.03, x1=xa+0.47, r0=r0, r1=r1, t=tf-0.01))
    parts.append(dict(kind='face', x0=S['x0'], x1=S['x1'], r0=C['root_r_m'], r1=C['tip_r_m'], t=tf, th=C['face']['t_m']))
    parts.append(dict(kind='spar', x0=S['x0'], x1=S['x1'], r0=C['root_r_m'], r1=C['tip_r_m']))
    parts.append(dict(kind='crossover', x0=S['x0']+0.25, x1=S['x0']+bay+0.25, r=C['tip_r_m']-0.3, d=NK['header']['D_m']))
    return dict(parts=parts, active_r=(r0, r1), blade_half_t=tf)


def loops_geometry(NK, S):
    lp = C['loop']; out = []
    for u in PW['district']:
        az_u = u['azimuth_deg']; az_l = az_u+60.0; blades = (az_u, az_u+120.0)
        for leg, sgn in (('Supply', +1), ('Return', -1)):
            a = math.radians(az_l+sgn*lp['offset_deg'])
            out.append(dict(unit=u['index'], leg=leg, kind='seg', p0=(NK['x_gas_cooler'], lp['radius_m']*math.cos(a), lp['radius_m']*math.sin(a)),
                            p1=(S['x0']-0.6, lp['radius_m']*math.cos(a), lp['radius_m']*math.sin(a)), r=NK['transport']['D_m']/2+0.03))
        for b, loop in zip(blades, ('A', 'B')):
            for leg, sgn in (('Supply', +1), ('Return', -1)):
                a0 = math.radians(az_l+sgn*lp['offset_deg']); ab = math.radians(b%360)
                xs = S['x0']-0.6; xh = S['x0']+(0.14 if loop == 'A' else 0.36)+(0.0 if leg == 'Supply' else HP_BAY[0])
                p0 = (xs, lp['radius_m']*math.cos(a0), lp['radius_m']*math.sin(a0)); p1 = (xs, 6.35*math.cos(ab), 6.35*math.sin(ab)); p2 = (xh, 6.6*math.cos(ab), 6.6*math.sin(ab))
                out.append(dict(unit=u['index'], leg=f'{leg}_{loop}{b%360:.0f}', kind='poly', points=[p0, p1, p2], r=NK['transport']['D_m']/4+0.02))
        gc = next(p for p in PW['unit']['parts'] if p['key'] == 'gas_cooler')
        out.append(dict(unit=u['index'], leg='FlowControl', kind='box', c=(NK['x_gas_cooler']+1.4, 5.25*math.cos(math.radians(az_l)), 5.25*math.sin(math.radians(az_l))),
                        half=(0.4, 0.25, 0.25), meaning='flow-control valves on the two branches (67/33 bias after a trip)'))
        out.append(dict(unit=u['index'], leg='EMPump', kind='box', c=(NK['x_gas_cooler']+2.6, 5.25*math.cos(math.radians(az_l-7)), 5.25*math.sin(math.radians(az_l-7))),
                        half=(0.6, 0.22, 0.22), meaning=f'NaK EM pump ({NK["pump_W_per_loop"]/1e3:.0f} kW), redundant pair'))
    return out


HP_BAY = [0.0]


# ------------------------------------------------------------------------------------------------------------- drawings
def svg_section(S, HP, NK, path):
    """Chordwise cut through one bay at mid-span (x horizontal, t vertical, exaggerated 6x in t) and the face-sheet detail."""
    w, h = 1000, 620; bay = HP['bay_chord_m']; sx = 820/(2*bay); st = 6*sx
    X = lambda x: 90+(x-S['x0'])*sx; T = lambda t: 200-t*st
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter,system-ui,sans-serif" font-size="12" role="img" aria-label="L2 blade cross-section">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>',
         f'<text x="20" y="22" class="t" font-weight="600">L2 section, chordwise cut at mid-span (one blade, t exaggerated 6x)</text>']
    tf = C['blade_t_m']/2
    o.append(f'<rect x="{X(S["x0"]):.1f}" y="{T(tf):.1f}" width="{2*bay*sx:.1f}" height="{2*tf*st:.1f}" fill="#d9d4c8" fill-opacity="0.35" stroke="#8a8478"/>')
    for k in range(2):
        xa = S['x0']+k*bay
        for sgn in (1, -1):
            o.append(f'<line x1="{X(xa+0.1):.1f}" y1="{T(sgn*(tf-0.012)):.1f}" x2="{X(xa+bay-0.05):.1f}" y2="{T(sgn*(tf-0.012)):.1f}" stroke="#c0502a" stroke-width="4"/>')
        o.append(f'<rect x="{X(xa+0.03):.1f}" y="{T(tf-0.01):.1f}" width="{0.44*sx:.1f}" height="{2*(tf-0.01)*st:.1f}" fill="#8a5a44" fill-opacity="0.55"/>')
        for dx, lab, col in ((0.14, 'A', '#e0762f'), (0.36, 'B', '#f0a050')):
            r = NK['header']['D_m']/2
            o.append(f'<ellipse cx="{X(xa+dx):.1f}" cy="{T(0):.1f}" rx="{r*sx:.1f}" ry="{r*st:.1f}" fill="{col}" stroke="#333"/>'
                     f'<text x="{X(xa+dx)-4:.1f}" y="{T(0)+4:.1f}" font-size="10">{lab}</text>')
        o.append(f'<text x="{X(xa+bay/2)-40:.1f}" y="{T(-tf)+22:.1f}" class="m">bay {k+1}: {bay:.2f} m chord</text>')
    o.append(f'<text x="{X(S["x0"])-75:.1f}" y="{T(0)+4:.1f}" class="m">aft</text><text x="{X(S["x1"])+8:.1f}" y="{T(0)+4:.1f}" class="m">fwd</text>')
    o.append(f'<line x1="{X(S["x1"])-120:.1f}" y1="{T(-tf)+44:.1f}" x2="{X(S["x0"])+120:.1f}" y2="{T(-tf)+44:.1f}" stroke="#555" marker-end="url(#ar)"/>'
             '<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#555"/></marker></defs>'
             f'<text x="{X(S["x0"])+130:.1f}" y="{T(-tf)+64:.1f}" class="m">burn acceleration drains condensate aft, to the evaporators (thermosyphon)</text>')
    # detail
    y0 = 420; o.append(f'<text x="20" y="{y0}" class="t" font-weight="600">Face detail (to scale x40): heat pipes on the face sheet, spanwise pitch {C["heat_pipe"]["pitch_m"]*1e3:.0f} mm</text>')
    k = 40*sx/10; pitch = C['heat_pipe']['pitch_m']; d = C['heat_pipe']['od_m']
    for i in range(6):
        cx = 120+i*pitch*1000*1.6
        o.append(f'<circle cx="{cx:.1f}" cy="{y0+70}" r="{d*1000*0.8:.1f}" fill="#c0502a" stroke="#333"/><circle cx="{cx:.1f}" cy="{y0+70}" r="{(d-2*C["heat_pipe"]["wall_m"]-2*C["heat_pipe"]["wick_m"])*1000*0.8:.1f}" fill="#f6d2b8"/>')
    o.append(f'<rect x="100" y="{y0+70+d*1000*0.8:.1f}" width="{6*pitch*1000*1.6:.0f}" height="3" fill="#333"/>')
    o.append(f'<text x="100" y="{y0+130}" class="m">K heat pipe OD {d*1e3:.0f} mm, wall {C["heat_pipe"]["wall_m"]*1e3:.1f} mm, screen wick + {C["heat_pipe"]["arteries"]} arteries {C["heat_pipe"]["artery_d_m"]*1e3:.0f} mm; '
             f'C-C face {C["face"]["t_m"]*1e3:.1f} mm, fin efficiency {S["fin_overall"][0]:.3f}-{S["fin_overall"][1]:.3f}</text>')
    o.append(f'<text x="100" y="{y0+150}" class="m">{HP["per_blade"]} pipes per blade ({HP["rows_per_blade"]} rows x {HP["per_row"]}), {HP["length_m"]:.2f} m long; '
             f'worst limit margin {HP["min_margin"]:.2f}; NaK headers D {NK["header"]["D_m"]*1e3:.0f} mm, serpentine out along bay 1, back along bay 2</text>')
    o.append(f'<text x="100" y="{y0+170}" class="m">NaK {S["T_nak_hot"]:.0f} -> {S["T_nak_cold"]:.0f} K, vapour {S["T_vapour"][0]:.0f} -> {S["T_vapour"][1]:.0f} K, '
             f'emission-equivalent {S["T_emission_equivalent_K"]:.0f} K; section {S["length_m"]:.2f} m (Phase VI {S["length_phase6_m"]:.2f} m)</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def svg_plan(S, HP, NK, path):
    w, h = 1000, 540; sx = 26; sr = 12
    X = lambda x: 420+(x-S['x0'])*sx; Y = lambda r: 410-(r-C['root_r_m'])*sr
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter,system-ui,sans-serif" font-size="12" role="img" aria-label="L2 section plan">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>',
         '<text x="20" y="22" class="t" font-weight="600">L2 section plan, one blade face (x along the ship, radius up)</text>']
    o.append(f'<rect x="{X(S["x0"]-1.6):.1f}" y="{Y(C["tip_r_m"]):.1f}" width="{1.6*sx:.1f}" height="{(C["tip_r_m"]-C["root_r_m"])*sr:.1f}" fill="#e14b2a" fill-opacity="0.18"/>'
             f'<text x="{X(S["x0"]-1.6)-120:.1f}" y="{Y(20):.1f}" class="m">HOT blade (1800 K)</text>')
    o.append(f'<rect x="{X(S["x1"]):.1f}" y="{Y(C["tip_r_m"]):.1f}" width="{1.6*sx:.1f}" height="{(C["tip_r_m"]-C["root_r_m"])*sr:.1f}" fill="#f0b03a" fill-opacity="0.18"/>'
             f'<text x="{X(S["x1"])+50:.1f}" y="{Y(20):.1f}" class="m">V-groove bulkhead, WARM (440 K)</text>')
    r0, r1 = C['root_r_m']+(C['tip_r_m']-C['root_r_m']-C['span_active_m'])/2, None
    r1 = r0+C['span_active_m']; bay = HP['bay_chord_m']
    for k in range(2):
        xa = S['x0']+k*bay
        o.append(f'<rect x="{X(xa):.1f}" y="{Y(C["tip_r_m"]):.1f}" width="{bay*sx:.1f}" height="{(C["tip_r_m"]-C["root_r_m"])*sr:.1f}" fill="#f2c9a8" fill-opacity="0.5" stroke="#b57a52"/>')
        for i in range(0, HP['per_row'], 12):
            r = r0+i*C['heat_pipe']['pitch_m']
            o.append(f'<line x1="{X(xa+0.1):.1f}" y1="{Y(r):.1f}" x2="{X(xa+bay-0.05):.1f}" y2="{Y(r):.1f}" stroke="#c0502a" stroke-width="0.8"/>')
        for dx, col in ((0.14, '#e0762f'), (0.36, '#f0a050')):
            o.append(f'<line x1="{X(xa+dx):.1f}" y1="{Y(C["root_r_m"]+0.2):.1f}" x2="{X(xa+dx):.1f}" y2="{Y(C["tip_r_m"]-0.3):.1f}" stroke="{col}" stroke-width="5"/>')
    o.append(f'<path d="M{X(S["x0"]+0.14):.1f},{Y(C["tip_r_m"]-0.3):.1f} L{X(S["x0"]+bay+0.14):.1f},{Y(C["tip_r_m"]-0.3):.1f}" stroke="#e0762f" stroke-width="3" fill="none"/>')
    o.append(f'<text x="{X(S["x0"])-5:.1f}" y="{Y(C["root_r_m"])+18:.1f}" class="m">x {S["x0"]:.2f}</text><text x="{X(S["x1"])-30:.1f}" y="{Y(C["root_r_m"])+18:.1f}" class="m">x {S["x1"]:.1f}</text>')
    o.append(f'<text x="20" y="478" class="m">Headers A (dark) and B (light) at the aft edge of each bay; the NaK runs out along bay 1, crosses at the tip and returns along bay 2.</text>')
    o.append(f'<text x="20" y="496" class="m">Every 12th heat pipe drawn ({HP["per_row"]} per row, both faces). Evaporator saddles clamp both headers: either loop drives every pipe.</text>')
    o.append(f'<text x="20" y="514" class="m">Transport: two NaK loops per blade (from two units), D {NK["transport"]["D_m"]*1e3:.0f} mm in the casing-hull annulus, {NK["run_m"]:.0f} m from the gas coolers.</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def svg_blades(HF, WA, LO, TV, path):
    """Three internal cross-sections (M2): HOT (manifold + Li fins + trunks), WARM and LOW pumped panels."""
    w, h = 1000, 360
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="Inter,system-ui,sans-serif" font-size="12" role="img" aria-label="Blade cross-sections">',
         '<style>.t{fill:var(--fg,#223)} .m{fill:var(--muted,#667)}</style>']
    def panel(x0, title, col, lines):
        o.append(f'<text x="{x0}" y="24" class="t" font-weight="600">{title}</text>')
        o.append(f'<rect x="{x0}" y="60" width="290" height="36" fill="{col}" fill-opacity="0.22" stroke="{col}"/>')
        for i, ln in enumerate(lines): o.append(f'<text x="{x0}" y="{130+18*i}" class="m">{ln}</text>')
    panel(20, 'HOT (M2): chordwise, 1800 K', '#e14b2a',
          [f'radial Li manifolds every {s6.hot.FIN_SPACING:.2f} m, fins +-{HF["fin_half_m"]:.2f} m', f'aft-pointing fins at {A_PEAK:.2f} g: {HF["aft_half_effective_m"]:.2f} m effective',
           f'capacity factor {HF["capacity_factor"]:.3f} ({HF["capacity_loss_W"]/1e9:.2f} GW)', f'fix: forward fins only, {HF["mitigation_manifolds_per_blade"]} manifolds/blade',
           f'trunk shading bound {TV["fraction"]*100:.1f} % ({TV["loss_bound_W"]/1e9:.2f} GW)'])
    for i in range(6): o.append(f'<rect x="{30+i*48}" y="56" width="6" height="44" fill="#8a2a1a"/><line x1="{33+i*48-20}" y1="62" x2="{33+i*48+20}" y2="62" stroke="#c0502a" stroke-width="2"/>')
    panel(350, f'WARM (M2): {WA["T_K"]:.0f} K pumped panels', '#f0b03a',
          [f'{WA["fluid"]}', f'A/B tubes interleaved, pitch {WA["pitch_m"]*1e3:.0f} mm', f'eta both loops {WA["eta_both_loops"]:.3f}, one loop {WA["eta_one_loop"]:.3f}',
           f'after a loop loss {WA["capacity_after_loop_loss"]*100:.0f} % capacity', f'{WA["tubes_per_face"]} tubes per face, x {WA["x"][0]:.1f}-{WA["x"][1]:.1f}'])
    for i in range(12): o.append(f'<circle cx="{362+i*24}" cy="78" r="4" fill="{"#c77d10" if i % 2 == 0 else "#5a7ec8"}"/>')
    panel(680, f'LOW (M2): {LO["T_K"]:.0f} K pumped panels', '#3a8fd0',
          [f'{LO["fluid"]}', f'A/B tubes interleaved, pitch {LO["pitch_m"]*1e3:.0f} mm', f'eta both loops {LO["eta_both_loops"]:.3f}, one loop {LO["eta_one_loop"]:.3f}',
           f'after a loop loss {LO["capacity_after_loop_loss"]*100:.0f} % capacity', f'{LO["tubes_per_face"]} tubes per face, x {LO["x"][0]:.1f}-{LO["x"][1]:.1f}'])
    for i in range(10): o.append(f'<circle cx="{694+i*28}" cy="78" r="4" fill="{"#c77d10" if i % 2 == 0 else "#5a7ec8"}"/>')
    o.append('<text x="20" y="340" class="m">Tube colours: loop A amber, loop B blue. Panels are pumped (no capillary or acceleration limit); HOT and L2 are heat-pipe sections.</text>')
    o.append('</svg>'); path.write_text('\n'.join(o))


def main():
    CY = cycles(); S = section(CY['pick']); HP = heat_pipes(S); HP_BAY[0] = HP['bay_chord_m']; NK = nak(S); FL = failures(S)
    HF = hot_fins(); TV = trunk_view()
    sw = s6.s3.WARM; sl = s6.s3.LOW
    WA = panels('warm', sw['T'], sw['design_W'], 50.4, 72.9); LO = panels('low', sl['T'], sl['design_W'], 73.4, 93.4)
    face_t = 2*S['planform_m2']*C['face']['t_m']*C['face']['rho_kg_m3']/1e3; core_t = 3.0*S['planform_m2']/1e3; saddle_t = 0.35*C['bays']*(C['tip_r_m']-C['root_r_m'])*0.044
    m_blade = dict(heat_pipes=HP['mass_t_per_blade'], headers=NK['header']['mass_t_per_blade'], face_sheets=face_t, core_and_spar=core_t, saddles=saddle_t)
    m_loops = 3*NK['transport']['mass_t_per_loop']; m_pumps = 3*2*0.6
    gross = 3*sum(m_blade.values())+m_loops+m_pumps
    credit = P6['hot']['F1']['by_item_t']['heat_pipe_fins'][1]*S['length_m']/RF['hot_length_m']
    led_p6 = next(v['t'][1] for k, v in P6['mass']['F1']['items'].items() if k.startswith('L2 sections'))
    budget = dict(hot_headroom_W=RF['hot_headroom_W'], l2_growth_W=S['hot_headroom_change_W'], trunk_shading_W=-TV['loss_bound_W'],
                  fins_unmitigated_W=-HF['capacity_loss_W'])
    budget['remaining_mitigated_W'] = budget['hot_headroom_W']+budget['l2_growth_W']+budget['trunk_shading_W']
    budget['remaining_unmitigated_W'] = budget['remaining_mitigated_W']+budget['fins_unmitigated_W']
    findings = [CY['finding'],
                f'L2 section: {S["length_m"]:.2f} m instead of {S["length_phase6_m"]:.2f} m (+{S["delta_m"]:.2f} m): the radiator runs at an emission-equivalent '
                f'{S["T_emission_equivalent_K"]:.0f} K (NaK {S["T_nak_hot"]:.0f} -> {S["T_nak_cold"]:.0f} K) and the face-sheet fins reach {S["fin_overall"][0]:.3f}-{S["fin_overall"][1]:.3f}. '
                f'The HOT length falls by the same amount ({S["hot_headroom_change_W"]/1e6:.0f} MW of HOT headroom).',
                HP['orientation'],
                f'Heat pipes: {HP["per_blade"]} potassium pipes per blade, worst limit margin {HP["min_margin"]:.2f} (sonic, capillary in coast, '
                f'entrainment, at the hottest and coldest pipe). The pipes are radiation-limited: losing one loop changes the header flow, not the pipe load. '+HP['wickless_rejected'],
                f'Transport: Phase VI counted only the section headers ({led_p6:.1f} t). Three NaK loops, D {NK["transport"]["D_m"]*1e3:.0f} mm, {NK["run_m"]:.0f} m from '
                f'the gas coolers through the casing-hull annulus ({"fits" if NK["fits_annulus"] else "does NOT fit"} the 0.4 m gap with insulation; '
                f'{NK["clear_to_bus_m"]:.2f} m to the bus duct) weigh {m_loops:.0f} t and leak {3*NK["leak_W_per_loop"]/1e3:.0f} kW into the annulus (a WARM-loop load).',
                f'L2 heat-rejection hardware {gross:.0f} t gross against {led_p6:.1f} t in the Phase VI ledger (credit for the HOT fins it replaces {credit:.1f} t): '
                f'+{gross-led_p6-credit:.0f} t dry in the live ledger.',
                FL['note'], HF['note'], TV['note'],
                f'HOT budget at peak burn: headroom {budget["hot_headroom_W"]/1e9:.2f} GW, L2 growth {budget["l2_growth_W"]/1e9:+.2f}, trunk shading '
                f'{budget["trunk_shading_W"]/1e9:+.2f} -> {budget["remaining_mitigated_W"]/1e9:.2f} GW with forward-pointing fins; '
                f'{budget["remaining_unmitigated_W"]/1e9:.2f} GW without them.',
                WA['note'].replace('Interleaved', 'WARM: interleaved'), LO['note'].replace('Interleaved', 'LOW: interleaved'),
                f'Alternative placement (owner question DR-3D-03): L2 sections at the AFT end of the HOT blades, beside the district, would cut the transport run from '
                f'{NK["run_m"]:.0f} m to ~20 m (about -{m_loops*(1-20/NK["run_m"]):.0f} t) but put the 950 K sections in the drive\'s radiation and plume field and '
                'remove the HOT/WARM grading at the bulkhead; not drawn.']
    decisions = [dict(id='DR-3D-02', q='Amend FT-03 adopted properties with the component set that makes eta 0.154 a cycle (eta_t 0.94, eta_c 0.90, recuperator 0.97, '
                                       f'dp 2 %), accepting a cooler L2 radiator ({S["T_emission_equivalent_K"]:.0f} K, {S["length_m"]:.1f} m)?',
                      rec='yes: keeps reactor power and waste heat; the alternative (950 K, eta ~0.09) raises reactor heat ~70 %'),
                 dict(id='DR-3D-03', q='L2 section placement: forward (drawn) or aft beside the district?', rec='keep forward until the aft drive environment is quantified'),
                 dict(id='DR-3D-04', q='HOT fins: forward-pointing only (manifold pitch 1.47 m) so that burns do not dry the aft halves?',
                      rec=f'yes: +{HF["manifold_walls_extra_t"]:.0f} t, restores {HF["capacity_loss_W"]/1e9:.2f} GW at peak acceleration')]
    out = dict(status='STUDY / PROTOTYPE / NONCANON (Track F1, M3 L2 section, M2 HOT/WARM/LOW)', cycle=CY, section=S, heat_pipes=HP, nak=NK, failures=FL,
               hot_fins=HF, trunk_view=TV, warm=WA, low=LO, hot_budget=budget,
               mass=dict(per_blade_t=m_blade, loops_t=m_loops, pumps_t=m_pumps, gross_t=gross, phase6_ledger_t=led_p6, hot_fin_credit_t=credit,
                         ledger_add_t=gross-led_p6-credit),
               ledger_add=[dict(item='L2 NaK transport loops + pumps (Stage E)', t=m_loops+m_pumps, cls='FT-03 (APPROVED), NEW line', x=[NK['x_gas_cooler'], S['x0']]),
                           dict(item='L2 section hardware above the Phase VI header line (Stage E)', t=3*sum(m_blade.values())-led_p6-credit, cls='FT-03 / FT-06', x=[S['x0'], S['x1']])],
               geometry=geometry(S, HP, NK), loops=loops_geometry(NK, S), findings=findings, decisions=decisions)
    (R/'i3d_radiators.json').write_text(json.dumps(out, indent=1))
    svg_section(S, HP, NK, R/'i3d_l2_section.svg'); svg_plan(S, HP, NK, R/'i3d_l2_plan.svg'); svg_blades(HF, WA, LO, TV, R/'i3d_blade_sections.svg')
    for f in findings: print('-', f)
    for r in HP['limits']: print(f"  {r['T_K']:.0f} K {r['state']:28s} load {r['load_W']/1e3:5.1f} kW sonic {r['sonic_W']/1e3:6.1f} cap {r['capillary_W'] and r['capillary_W']/1e3 or 0:6.1f} entr {r['entrainment_W']/1e3:6.1f} margin {r['margin']:.2f}")
    print(HP['wickless_rejected']); print(json.dumps(out['mass'], indent=1)); print(json.dumps(budget, indent=1))


if __name__ == '__main__':
    main()
