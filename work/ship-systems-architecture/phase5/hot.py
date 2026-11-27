"""ISSA Phase V-B: propulsion heat transport (STUDY, NONCANON). One spatial network model serves every topology (H1, H2, H3, H5, H6
variants) and every coolant, so the comparison is consistent. Pure Python; imported by study5.py.

Cases are CORRELATED SENSITIVITY CASES (opt / nom / cons: every uncertain input moved together toward low or high mass); they are not
statistical minima and maxima. Velocities are optimised per case on the same objective for every topology (hardware mass plus the
L1 generation mass the pump power needs), which removes the Phase IV non-monotonic H5 band.
"""
import math

G0 = 9.80665; SIG = 5.670374419e-8; R_GAS = 8.314
CASES = ('opt', 'nom', 'cons')
EPS_HOT = 0.91
T_SURF = 1800.0                      # intended mean surface temperature of the hot blades (the 14.4 GW basis)

# Fluids. Properties near 1500-2000 K; vapour pressure by Clausius-Clapeyron anchored at the 1 atm boiling point (STUDY accuracy,
# overestimates near the critical point). Sources: standard handbook values (Ohse 1985 alkali metals; IAEA liquid-metal handbook);
# Sn/Al: CRC handbook. compat = containment the fluid is known or proposed to tolerate at ~1900 K.
FLUIDS = {
    'Li': dict(rho=lambda T: 562.0-0.1*T, cp=4200.0, mu=1.6e-4, h_fg=19.5e6, M=6.94e-3, T_b=1615.0, T_m=453.7, h_f=432e3, T_crit=3223.0,
               compat='Nb-1Zr, Mo-TZM, Mo-Re, W-Re (SP-100, SNAP heritage to ~1400 K; 1800-2000 K untested for 10^4 h)',
               failure='Li burns in air/water (not present outside); Li vapour plates optics; tritium from n capture (activation)',
               trl='Li loops ~1350 K demonstrated (SP-100 components); 1900+ K loops not demonstrated'),
    'Na': dict(rho=lambda T: 1015.0-0.235*T, cp=1270.0, mu=1.4e-4, h_fg=3.87e6, M=22.99e-3, T_b=1156.0, T_m=371.0, h_f=113e3, T_crit=2503.0,
               compat='steels to ~1000 K; refractory metals above', failure='high vapour pressure above 1200 K; boiling at loss of pressure',
               trl='terrestrial fast reactors (~820 K); space heat pipes to ~1100 K'),
    'K': dict(rho=lambda T: 900.0-0.22*T, cp=800.0, mu=1.0e-4, h_fg=1.98e6, M=39.10e-3, T_b=1032.0, T_m=336.7, h_f=59.6e3, T_crit=2223.0,
              compat='refractory metals', failure='near-critical at 1900-2000 K: no stable liquid at practical pressure',
              trl='Rankine cycle studies (SNAP-50) to ~1400 K'),
    'Sn': dict(rho=lambda T: 7000.0-0.6*T, cp=240.0, mu=1.0e-3, h_fg=2.49e6, M=118.7e-3, T_b=2875.0, T_m=505.1, h_f=59.2e3, T_crit=None,
               compat='attacks most metals; W, graphite, SiC/Si3N4 ceramics proposed (MIT ceramic pump for 1470 K Sn, Amy et al. Nature 2017)',
               failure='heavy inventory; ceramic brittleness under dust impact',
               trl='ceramic-pumped Sn loop at ~1470 K demonstrated in the laboratory (2017); nothing near 1900-2000 K in flight'),
    'HeXe': dict(rho=None, cp=520.0, mu=6.0e-5, M=40e-3, gas=True, p=3.0e6, T_m=None,
                 compat='superalloys, refractory metals, C-C', failure='leak loses pressure, not liquid; no freezing',
                 trl='closed Brayton He-Xe (Prometheus/JIMO studies) to ~1150 K turbine inlet'),
}
WALL = dict(rho=10.2e3, alpha=5.5e-6, name='Mo-Re / Mo-TZM class (W-Re above 2000 K)')   # density kg/m3, expansion 1/K
SIGMA_ALLOW = (30e6, 15e6, 8e6)      # allowable hoop stress at ~1950 K for the mission's cumulative hot hours (creep-limited), per case
T_WALL_MAX = (2100.0, 2000.0, 1950.0)  # wall temperature limit per case (W-Re / Mo-Re / Mo-TZM class)
EM_ETA = (0.45, 0.35, 0.25)          # annular linear induction (EM) pump efficiency at high temperature (SP-100 class ~0.2-0.4)
PUMP_KG_PER_KW = (2.0, 4.0, 8.0)     # EM pump + power conditioning, per kW electrical
L1_KG_PER_W = (2.0e-3, 4.0e-3, 7.0e-3)  # L1 generation incl. its rejection, per W electrical (mass equivalent of pump power)
SUPPORT_FRAC = (0.10, 0.15, 0.20)
T_MIN = dict(trunk=(1.0e-3, 1.5e-3, 2.0e-3), manifold=(0.5e-3, 0.75e-3, 1.0e-3))   # minimum gauge (manufacture, dust, handling)
CORR = 0.3e-3                        # corrosion / erosion allowance on every wall
HP_FIN_KG_M2 = (0.0, 1.0, 2.0)       # heat-pipe fin increment over plain channels, per m2 of blade planform (two faces)
FIN_SPACING = 2.94                   # m between radial manifolds = 2 x the Li fin capillary limit (Phase IV)
BLADE_W = 30.0                       # m emitting height (r 6.1-36.1)
L_ROOT = 30.0                        # m drive heat exchanger to blade root
DP_HX = 1.0e5                        # Pa drive heat-exchanger loss


def p_sat(f, T):
    F = FLUIDS[f]
    if F.get('gas'): return 0.0
    return 101325.0*math.exp(-F['h_fg']*F['M']/R_GAS*(1/T-1/F['T_b']))


def inlet_temperature(dT, theta):
    """Coolant inlet temperature that gives a mean emitted flux equal to a uniform T_SURF surface, for a coolant drop dT along the
    radiating path and a coolant-to-surface drop theta (wall + heat pipe + fin). Exact for radiation-limited cooling along the path:
    mean T_s^4 = 3 dT / [(T_out - theta)^-3 - (T_in - theta)^-3]."""
    lo, hi = T_SURF, T_SURF+dT+theta+400.0
    for _ in range(80):
        Ti = 0.5*(lo+hi); To = Ti-dT
        m = 3*dT/((To-theta)**-3-(Ti-theta)**-3)
        lo, hi = (Ti, hi) if m < T_SURF**4 else (lo, Ti)
    return Ti


def spatial_profile(dT, theta, n=12):
    """Surface temperature and flux along the radiating path (fraction of area), for the figure and the report."""
    Ti = inlet_temperature(dT, theta); To = Ti-dT
    # area fraction a(T) from radiation-limited cooling: da ~ dT / (T - theta)^4
    tot = ((To-theta)**-3-(Ti-theta)**-3)/3
    out = []
    for k in range(n+1):
        T = Ti-dT*k/n
        a = ((T-theta)**-3-(Ti-theta)**-3)/3/tot
        out.append(dict(area_frac=a, T_coolant=T, T_surface=T-theta, flux_W_m2=EPS_HOT*SIG*(T-theta)**4))
    return out


# Topologies. n_paths: primary trunk pairs per blade; rating: flow share each path is sized for (1/n_paths = shared, >1/n = redundant);
# n_sec: isolatable sections along the blade; indep: each section a separate loop with its own trunks and pumps (H5);
# secondary: intermediate heat exchanger per section (shared trunk feeds isolated secondaries); hp: heat-pipe fins; xfeed: cross-feed
# valves between paths; channels: coolant in panel channels over the whole area (no heat pipes).
TOPOLOGIES = [
    dict(key='H1', name='H1 one pumped loop per blade, panel channels', n_paths=1, rating=1.0, n_sec=1, indep=False, secondary=False,
         hp=False, xfeed=False, dT=200.0, theta=10.0, maturity='TRL 3-4 (SP-100 class loop, temperature far beyond heritage)'),
    dict(key='H2', name='H2 one loop per blade, dT 400 K, tapered headers', n_paths=1, rating=1.0, n_sec=1, indep=False, secondary=False,
         hp=False, xfeed=False, dT=400.0, theta=10.0, maturity='TRL 3'),
    dict(key='H3', name='H3 one pumped trunk per blade, radial manifolds, Li heat-pipe fins', n_paths=1, rating=1.0, n_sec=1, indep=False,
         secondary=False, hp=True, xfeed=False, dT=300.0, theta=30.0, maturity='TRL 3 (heat pipes TRL 5 at <=1400 K)'),
    dict(key='H5', name='H5 six independent loops per blade (own trunks and pumps), fins', n_paths=6, rating=1/6, n_sec=6, indep=True,
         secondary=False, hp=True, xfeed=False, dT=300.0, theta=30.0, maturity='TRL 3'),
    dict(key='H6a', name='H6a two redundant trunk pairs (each 60 %), 6 isolatable sections, fins, cross-feed', n_paths=2, rating=0.6, n_sec=6,
         indep=False, secondary=False, hp=True, xfeed=True, dT=300.0, theta=30.0, maturity='TRL 2-3'),
    dict(key='H6b', name='H6b two redundant trunk pairs (each 100 %), 8 isolatable sections, fins', n_paths=2, rating=1.0, n_sec=8,
         indep=False, secondary=False, hp=True, xfeed=True, dT=300.0, theta=30.0, maturity='TRL 2-3'),
    dict(key='H6c', name='H6c shared trunk pair feeding 6 isolated secondaries (section heat exchangers)', n_paths=2, rating=0.6, n_sec=6,
         indep=False, secondary=True, hp=True, xfeed=True, dT=300.0, theta=30.0, maturity='TRL 2'),
    dict(key='H6d', name='H6d three trunk pairs (each 50 %), 12 isolatable sections, fins, cross-feed', n_paths=3, rating=0.5, n_sec=12,
         indep=False, secondary=False, hp=True, xfeed=True, dT=300.0, theta=30.0, maturity='TRL 2-3'),
    dict(key='H6e', name='H6e two trunk pairs (each 60 %), 4 isolatable sections, fins, cross-feed', n_paths=2, rating=0.6, n_sec=4,
         indep=False, secondary=False, hp=True, xfeed=True, dT=300.0, theta=30.0, maturity='TRL 2-3'),
]


def _tube(mdot, rho, v, L, p, i, kind, sigma):
    A = mdot/(rho*v); D = math.sqrt(4*A/math.pi)
    t = max(T_MIN[kind][i], p*D/(2*sigma)+CORR)
    return dict(A=A, D=D, t=t, vol=A*L, wall_kg=math.pi*(D+t)*t*L*WALL['rho'])


def network(topo, Q_blade, L_hdr, a_max, fluid='Li', i=1, v_trunk=None, accel=True):
    """One blade's network at the peak absorbed heat Q_blade. Returns masses (t), pump power (W), pressures, inventory and fault data.
    The three blades are identical; totals are x3 at the caller."""
    F = FLUIDS[fluid]; T = topo; sigma = SIGMA_ALLOW[i]
    dT = T['dT'] if fluid in ('Li', 'Na', 'K') else (T['dT'] if fluid != 'Sn' else 300.0)
    theta = T['theta']+(50.0 if T['secondary'] else 0.0)           # section heat exchanger adds ~50 K between primary and secondary
    Ti = inlet_temperature(dT, T['theta'])+(50.0 if T['secondary'] else 0.0)
    To = Ti-dT
    if F.get('gas'):
        rho = F['p']*F['M']/(R_GAS*0.5*(Ti+To)); ps = 0.0
    else:
        rho = F['rho'](0.5*(Ti+To)); ps = p_sat(fluid, Ti)
    mdot = Q_blade/(F['cp']*dT)
    head_full = rho*a_max*(L_hdr+L_ROOT) if accel else 0.0
    head_sec = rho*a_max*(L_hdr/T['n_sec']) if accel else 0.0
    subcool = 0.3e6 if not F.get('gas') else 0.0
    best = None
    grid = [(a, b) for a in [2.0+1.0*k for k in range(9)] for b in (2.0, 3.0, 4.0, 5.0, 6.0, 8.0)]
    if v_trunk: grid = [(v_trunk, 3.0)]
    if F.get('gas'): grid = [(60.0, 40.0)]
    for v, v_m in grid:
        # trunks
        if T['indep']:
            L_tr = L_ROOT+0.5*L_hdr; paths = T['n_sec']; m_path = mdot/paths; taper = 1.0
        else:
            L_tr = L_ROOT+0.5*L_hdr; paths = T['n_paths']; m_path = mdot*T['rating']; taper = 1.0
        Re = rho*v*math.sqrt(4*m_path/(rho*v)/math.pi)/F['mu']; f = 0.316*Re**-0.25
        D_tr = math.sqrt(4*m_path/(rho*v)/math.pi)
        dp_tr = f*(2*L_tr)/D_tr*rho*v**2/2
        # manifolds: radial out-and-back, 3 m/s, one per fin pitch (heat pipes) or panel channels over the whole area
        n_man = max(1, int(L_hdr/FIN_SPACING))
        m_man = mdot/n_man
        D_m = math.sqrt(4*m_man/(rho*v_m)/math.pi); Re_m = rho*v_m*D_m/F['mu']; f_m = 0.316*Re_m**-0.25
        dp_m = f_m*(2*BLADE_W)/D_m*rho*v_m**2/2 if T['hp'] else 3e5*(dT/300.0)**-1   # channel panels: Phase IV panel loss scaled by flow
        dp = dp_tr+dp_m+DP_HX+(DP_HX if T['secondary'] else 0.0)
        # walls are graded along x for the local pressure: manifolds see the mean head (or the section head behind a section HX)
        p_max = (F['p'] if F.get('gas') else ps+subcool)+dp+(head_sec if T['secondary'] else 0.5*head_full)
        p_trunk = (F['p'] if F.get('gas') else ps+subcool)+dp+head_full
        Vdot = mdot/rho
        pump_W = Vdot*dp/EM_ETA[i] if not F.get('gas') else Vdot*dp/0.85   # gas: circulator/compressor
        trunks = [_tube(m_path, rho, v, 2*L_tr, p_trunk, i, 'trunk', sigma) for _ in range(paths)]
        man = _tube(m_man, rho, v_m, 2*BLADE_W, p_max, i, 'manifold', sigma)
        vol_tr = sum(x['vol'] for x in trunks)*(0.75 if not T['indep'] else 1.0)     # tapered headers: ~25 % less than straight
        wall_tr = sum(x['wall_kg'] for x in trunks)*(0.75 if not T['indep'] else 1.0)
        vol_man = n_man*man['vol'] if T['hp'] else L_hdr*BLADE_W*0.002
        wall_man = n_man*man['wall_kg'] if T['hp'] else L_hdr*BLADE_W*2*0.6e-3*WALL['rho']*0.5   # channels: thin walls, half shared with the panel
        inv_m3 = vol_tr+vol_man+(T['n_sec']*0.05*vol_man if T['secondary'] else 0.0)
        inv_kg = inv_m3*rho*(1.10)                                      # +10 % plena, pumps, HX hold-up
        # expansion: liquid shrinks from operating to melting temperature -> accumulator for the swing
        if F.get('gas'):
            acc_kg = 0.0; frz = None
        else:
            # Phase V improvement: the loop is filled progressively during startup from a low-pressure storage tank, so the 30-35 %
            # thermal swing lives in that tank (cold side, ~0.3 MPa); the pressurised accumulator only takes transients (5 %).
            swing = F['rho'](F['T_m'])/rho-1.0
            V_acc = inv_m3*0.05*1.2
            acc_kg = 1.5*p_trunk*V_acc*WALL['rho']/sigma+50.0*max(paths, 1)
            V_store = inv_m3*swing*1.2
            acc_kg += max(1.5*0.3e6*V_store*8.0e3/100e6, V_store**(2/3)*4.84*3e-3*8.0e3)   # thin steel/Nb vessel at ~600 K
            frz = F['T_m']
        D_sec = math.sqrt(4*(mdot/T['n_sec'])/(rho*v)/math.pi)
        n_sec_valves = T['n_sec']*2*(2 if (T['n_paths'] > 1 and not T['indep']) else 1) if T['n_sec'] > 1 else 0
        n_trunk_valves = paths*2+(T['n_sec'] if T['xfeed'] else 0)
        valves = n_sec_valves+n_trunk_valves
        vk = lambda D: max(20.0, 60.0*(D/0.1)**2)                     # high-temperature Li isolation valve, PROTOTYPE scaling
        valve_kg = n_sec_valves*vk(D_sec/(2 if (T['n_paths'] > 1 and not T['indep']) else 1)**0.5)+n_trunk_valves*vk(D_tr)
        bellows = int(L_hdr*WALL['alpha']*(Ti-300.0)/0.10)+1
        bellows_kg = bellows*paths*(40.0, 60.0, 100.0)[i]
        hx_kg = 0.0
        if T['secondary']:
            U = (5e4, 3e4, 2e4)[i]; A_hx = Q_blade/(U*50.0); hx_kg = A_hx*(10.0, 15.0, 20.0)[i]
        fins_kg = L_hdr*BLADE_W*HP_FIN_KG_M2[i] if T['hp'] else 0.0
        pump_kg = pump_W/1e3*PUMP_KG_PER_KW[i]*(1.0 if paths == 1 else 1.0+0.05*paths)
        recovery_kg = (inv_kg/T['n_sec'])*0.25+200.0*T['n_sec']           # drain tank per section-volume (low pressure) + transfer pump
        maint_kg = T['n_sec']*(100.0, 200.0, 400.0)[i]
        piping = wall_tr+wall_man+valve_kg+bellows_kg+hx_kg
        supports = SUPPORT_FRAC[i]*piping
        hw = inv_kg+piping+supports+acc_kg+fins_kg+pump_kg+recovery_kg+maint_kg
        obj = hw+pump_W*L1_KG_PER_W[i]
        r = dict(v_trunk=v, v_manifold=v_m, T_in=Ti, T_out=To, rho=rho, p_sat=ps, p_trunk_max=p_trunk, p_section_max=p_max, head_full=head_full,
                 head_section=head_sec, dp=dp, mdot=mdot, D_trunk=D_tr, t_trunk=trunks[0]['t'], D_manifold=D_m, t_manifold=man['t'],
                 n_manifolds=n_man, inventory_kg=inv_kg, pump_W=pump_W, valves=valves, bellows=bellows*paths,
                 mass_kg=dict(coolant=inv_kg, trunk_walls=wall_tr, manifold_walls=wall_man, valves=valve_kg, bellows=bellows_kg,
                              section_hx=hx_kg, supports=supports, accumulators=acc_kg, heat_pipe_fins=fins_kg, pumps=pump_kg,
                              recovery=recovery_kg, maintenance=maint_kg),
                 hardware_kg=hw, objective_kg=obj, wall_over_T_limit=Ti+20.0 > T_WALL_MAX[i], freeze_K=frz)
        if best is None or obj < best['objective_kg']: best = r
    return best


def faults(topo, net, Q_blade, cap_blade, n_blades=3, absorbed_total=10.45e9):
    """Single-fault consequences for one topology. cap_blade: ideal hot capacity of one blade. Detection 1-5 s, valve closure 2-10 s."""
    T = topo; ns = T['n_sec']; inv = net['inventory_kg']; dp = net['p_trunk_max']
    rho = net['rho']; tot_cap = n_blades*cap_blade
    def leak(d_hole, t_iso):
        A = math.pi*d_hole**2/4; return 0.6*A*math.sqrt(2*rho*dp)*t_iso
    def remaining(frac_lost_one_blade):
        cap = tot_cap-cap_blade*frac_lost_one_blade
        return dict(capacity_W=cap, margin=cap/absorbed_total-1.0, drive_power_no_margin=min(1.0, cap/absorbed_total),
                    drive_power_with_margin=min(1.0, cap/(1.2*absorbed_total)))
    sec_frac = 1.0/ns
    fin_frac = 1.0/max(1, int(1500.0/1.0)) if T['hp'] else None
    rows = []
    isolable = ns > 1 or T['hp']
    rows.append(dict(case='fin puncture (dust, mm-class)', capacity_lost=('one heat-pipe fin (~0.01 %)' if T['hp'] else 'panel channel: whole loop unless isolated'),
                     inventory_lost_kg=(0.05 if T['hp'] else leak(2e-3, 600.0)), intervention='none in the burn; fin replaced at the next maintenance',
                     remaining=remaining(1e-4 if T['hp'] else (sec_frac if ns > 1 else 1.0)),
                     action='continue' if T['hp'] else ('isolate section' if ns > 1 else 'shut down blade loop (drive derate)')))
    for name, d, t_iso in (('channel / manifold puncture (5 mm)', 5e-3, 8.0), ('header leak (20 mm crack)', 20e-3, 8.0)):
        lost = leak(d, t_iso)
        rows.append(dict(case=name, capacity_lost=(f'one section ({100*sec_frac:.0f} % of a blade)' if ns > 1 else 'whole blade loop'),
                         inventory_lost_kg=lost+(0.0 if ns > 1 else inv*0.5), intervention='isolate in ~8 s (detect + close); drain section to recovery',
                         remaining=remaining(sec_frac if ns > 1 else 1.0),
                         action=('continue at full power' if remaining(sec_frac)['drive_power_no_margin'] >= 1 and ns > 1 else 'derate drive')))
    p_red = (T['n_paths']*T['rating'] >= 1.0+1/T['n_paths']-1e-9) if not T['indep'] else True
    rows.append(dict(case='pump failure', capacity_lost=('none (redundant path carries the flow)' if (T['n_paths'] > 1 and T['n_paths']*T['rating']-T['rating'] >= 0.999) else
                                                         (f'{100*(1-(T["n_paths"]-1)*T["rating"]):.0f} % of blade flow until cross-feed' if T['n_paths'] > 1 else
                                                          ('one zone' if T['indep'] else 'whole blade loop'))),
                     inventory_lost_kg=0.0, intervention='switch to standby pump / cross-feed in < 30 s',
                     remaining=remaining(0.0 if T['n_paths'] > 1 and (T['n_paths']-1)*T['rating'] >= 0.999 else
                                         ((1-(T['n_paths']-1)*T['rating']) if T['n_paths'] > 1 else (1/ns if T['indep'] else 1.0))),
                     action='continue' if T['n_paths'] > 1 else 'derate'))
    rows.append(dict(case='isolation-valve failure (fails open during a section leak)', capacity_lost='next valve upstream closes: two sections (or the path)',
                     inventory_lost_kg=leak(20e-3, 20.0), intervention='upstream valve in ~20 s',
                     remaining=remaining(min(1.0, 2*sec_frac) if ns > 1 else 1.0), action='derate if two sections exceed the margin'))
    rows.append(dict(case='section loss', capacity_lost=f'{100*sec_frac:.0f} % of one blade', inventory_lost_kg=inv/ns if ns > 1 else inv,
                     intervention='repair in coast (robotic, 24-72 h)', remaining=remaining(sec_frac), action='continue degraded'))
    rows.append(dict(case='whole-blade loss', capacity_lost='one third of the hot capacity', inventory_lost_kg=inv, intervention='end the burn; repair in coast',
                     remaining=remaining(1.0), action='derate drive'))
    rows.append(dict(case='drive trip', capacity_lost='none', inventory_lost_kg=0.0, intervention='flow to 25 %: pump power falls to ~1.6 % (cube law)',
                     remaining=remaining(0.0), action='cooldown circulation on L2 or ride-through storage'))
    rows.append(dict(case='total electrical outage during cooldown', capacity_lost='forced flow stops; fins keep radiating', inventory_lost_kg=0.0,
                     intervention='ride-through cells run the cooldown pumps (25 %% flow, %.0f kW per blade) for 30 min' % (net['pump_W']*0.016/1e3),
                     remaining=remaining(0.0), action='stored heat in the drive heat exchanger is the hazard: no natural circulation in 0 g'))
    return rows


def startup(net, L_hdr, fluid='Li'):
    F = FLUIDS[fluid]
    if F.get('gas'): return dict(thaw_J=0.0, note='no freezing')
    m = net['inventory_kg']
    thaw = m*(F['cp']*(F['T_m']-150.0)+F['h_f'])
    to_op = m*F['cp']*(net['T_out']-F['T_m'])
    blade_struct = L_hdr*BLADE_W*6.0                                 # kg of blade structure per blade, ~6 kg/m2 planform (STUDY)
    preheat_struct = blade_struct*900.0*(F['T_m']+50.0-150.0)
    return dict(thaw_J=thaw, heat_to_operating_J=to_op, blade_preheat_J=preheat_struct,
                hours_on_5MW=(thaw+preheat_struct)/5e6/3600.0)
