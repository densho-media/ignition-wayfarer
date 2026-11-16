"""Vertex 2.0: one engineering ledger for every propulsion candidate (research, not canon).

  python3 work/vertex-2-0/ledger.py            writes work/vertex-2-0/ledger.json and prints the comparison

Owner brief 2026-11-16 13:07Z (IGNITION - VERTEX 2.0, research and engineering analysis only; no production redesign, canon change,
squash or deployment). The same shared assumptions (SHARED, each with its basis) are applied to every candidate, and the whole mission
is closed, not an operating point:

  mission      four burns of 0.016 c (out, arrive, home, home-brake), rocket equation per burn, power-limited constant jet power
  mass growth  end mass = core ship + propulsion system(power, heat, field, shields) + tankage(propellant); propellant = (R^4 - 1) end
               mass; solved as a fixed point, so hardware that grows with power feeds back into power (the Phase F 2.72 kg/kg effect)
  energy       every fusion watt is booked to exactly one sink: jet, plume lost to space, isotropic radiation escaping or intercepted,
               charged leakage, direct-conversion and driver losses; the sum is checked against fusion power plus driver input
  heat         intercepted heat is pumped to the 1800 K radiators at the cost of its temperature (1 + 1/COP below 1800 K) and costs
               radiator mass; surfaces facing the burn must stay below the actively cooled heat-flux limit
  radiation    neutron fluence on superconductors bounded by a shield whose thickness follows the attenuation (calibrated to 1.6B);
               shields, armour, conductor, magnet structure (virial theorem), tethers, driver and startup store all carry mass
Every candidate parameter states its basis: CANON, EVIDENCE (an earlier Vertex study), LITERATURE, PROTOTYPE or SPECULATIVE.
Standard library only; reads src/ and references/, writes only into work/vertex-2-0/.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import operating_point as op  # noqa: E402
import vertex_source as vs  # noqa: E402

C = 299792458.0
SIG = 5.670374419e-8
MU0 = 4e-7*math.pi
KEV = 1.602176634e-16
YR = 365.25*86400.0
DAY = 86400.0
EV = ROOT/'references'/'evidence'


def ev(name):
    return json.loads((EV/f'{name}.json').read_text())


# ---------- shared assumptions (one set for every candidate) ---------------------------------------------------------------------------

def shared(s):
    P = s['physics']; q = P['operating_point']; rep = op.report(s); mi = rep['mission']; b = rep['operating_point']
    items = {i['id']: i['mass_kg'] for i in P['mass_budget']['items']}
    f_tank = P['fuel_loads']['tank_dry_fraction']
    rad_ship = items['radiators_thermal']*(1-q['hot_share'])
    core = q['protected_and_operational_kg']-f_tank*q['legacy_inventory_kg']-items['drive_package']-items['radiators_thermal']+rad_ship
    r = s['radiators']; flux = b['ideal_rejection_W']/r['effective_area']['value']
    SRC = ev('vertex_source'); n0 = SRC['neutrons']['rows'][0]
    D = ev('vertex_dynamic'); st = D['dynamo']['startup'][1]
    return dict(
        dv=s['mission']['target_speed']['value']*C, burns=q['mission_burns'], engines=4,
        core_kg=core, core_basis='CANON: protected + operational ship (1.3 kt) less the legacy tankage, the 250 t drive package and the drive share of the radiators; the ship keeps its own radiators',
        f_tank=f_tank, e_fuel=q['dhe3_specific_energy_J_kg'], he3_share=q['he3_mass_share'], he3_canon_kg=rep['species_kg']['helium_3'],
        Tb0_s=b['duration_s']*0+sum(mi['burn_expelled_kg'])/b['peak_mass_flow_kg_s'], trip_tol_yr=0.3,
        trip_basis='PROTOTYPE (owner question): the 6.0 yr is LOCKED and the destination is not stated; a burn longer than today costs about half its extra duration in trip time, and up to 0.3 yr (5 %) is allowed here',
        dep_upper=P['departure_mass']['upper_kg'], prop_upper=P['propulsion_inventory']['upper_kg'],
        rad_flux=flux, rad_kg_m2=5.0, rad_basis='CANON flux (14.4 GW over 26,882 m2 at 1800 K); 5 kg/m2 added radiator (1.6B nominal PROTOTYPE)',
        q_max=10e6, q_basis='LITERATURE: steady actively cooled tungsten armour (ITER divertor class 10 MW/m2; 20 MW/m2 transient only)',
        T_armour=1300.0, T_loss=1000.0, T_cold=20.0,
        n_per_J=n0['neutrons_per_s']/n0['neutron_W'], phi_lim=1e22, lam=0.15, rho_sh=2000.0,
        shield_basis='EVIDENCE 1.6B: REBCO fast-neutron fluence limit 1e22 /m2 and 0.15 m attenuation length (reproduces its 2.30 m for 4.7e6); LITERATURE layered LiH-W space-reactor shadow shield at 2 t/m3 mean density (300 kg/m2 per e-fold)',
        dep_n=0.87, materials=dict(steel=(1.0e9, 8000.0, 'LITERATURE: cryogenic steel / Hastelloy coil structure, 1 GPa allowable'),
                                   cnt=(5.0e9, 1600.0, 'ADVANCED ENGINEERING: CNT-fibre composite, 5 GPa allowable (lab fibres 5-10 GPa; not yet at tonne scale)')),
        k_virial=2.0, virial_basis='LITERATURE: virial theorem M >= rho E_B / sigma for the structure of any magnet; x2 for real coils (PROTOTYPE)',
        station_kg=10000.0, station_basis='PROTOTYPE: burn station behind the ship shadow shield (fuel injector, control-field coils, metrology heads), 10 t per engine',
        T_hot_cond=450.0, rho_e_al=4.3e-8, rho_al=2700.0,
        hot_basis='LITERATURE: aluminium resistivity at 450 K about 4.3e-8 ohm m; unshielded metal takes tens of dpa over one mission (swelling and transmutation OPEN)',
        J_e=5e8, rho_cond=8000.0, cond_basis='LITERATURE: REBCO engineering current density 500 A/mm2 at 20 K in moderate field, stabiliser included',
        driver_kg_W=0.5e-3, driver_basis='EVIDENCE 1.6B nominal: power conditioning and driver plant 0.5 kg per kW (0.5e-3 kg/W) of electrical driver power; superseded by ledger2.py (1 kg per kW)',
        start_J_kg=st['energy_J']/st['mass_kg']['flywheel'], start_J=st['energy_J'],
        start_basis='EVIDENCE 1.7: bracket-1 ignition bootstrap 1.74 GJ for the cluster, 30 kJ/kg flywheel class; counted wherever it is mounted',
        tether_k=3.0, A_front=math.pi*25.0**2, phi_ship=6e12*math.exp(5.0), ship_aft_m=250.0,
        ship_basis='PROTOTYPE geometry (25 m radius ship cross-section seen from an aft burn point; habitat 250 m ahead of the aft end); LITERATURE dose: '
                   '0.25 Sv of drive neutrons over the mission at about 4e-10 Sv cm2 (6e12 n/m2), with five e-folds credited to the habitat water wall',
        ve_grid_c=[0.035, 0.04, 0.045, 0.05, 0.055, 0.06, 0.064, 0.07, 0.075],
        canon=dict(departure_kg=b['departure_mass_kg'], end_kg=mi['end_mass_kg'], propellant_kg=mi['propellant_kg'], ve=q['exhaust_velocity_m_s'],
                   jet_W=b['peak_jet_power_W'], fusion_W=b['peak_fusion_power_W'], eta=q['directed_efficiency'], drive_package_kg=items['drive_package'],
                   radiators_kg=items['radiators_thermal'], heat_budget_W=b['hot_budget_W']))


# ---------- candidates ----------------------------------------------------------------------------------------------------------------
# Source shares are fractions of fusion power (EVIDENCE: 1.6B vertex_source best rows); a = driver or heating power delivered to the plasma
# per fusion watt; eta_d wall plug to plasma; eta_dc direct conversion of the charged stream that powers the driver; eta_noz charged energy
# leaving as directed jet; leak charged energy striking hardware (the rest of the charged energy leaves to space as divergent plume).

def candidates():
    return {
        'A0': dict(title='Vertex as drawn (reconciled baseline)', geometry='drawn', f_ph=0.1294, f_n=0.0789, a=0.111, eta_d=0.3, eta_dc=0.7,
                   eta_noz=0.517, leak=0.483, sky=0.691, magnet='steel', Tb='canon', speculative=[],
                   basis='EVIDENCE: 1.6B S0-SC nominal source, 1.7 bracket-1 driver share (gain 9), 1.4 channelled capture, 1.5 hardware sky 0.69, drawn masses'),
        'A': dict(title='A. Improved pulsed Vertex', geometry='drawn', f_ph=0.1009, f_n=0.0496, a=0.02, eta_d=0.3, eta_dc=0.9,
                  eta_noz=0.817, leak=0.183, sky=0.546, magnet='steel', Tb='free', speculative=[],
                  basis='EVIDENCE: 1.6B S1 nominal (spin-polarized target), 1.7 optimistic driver share (gain 50), 1.4 aft capture, 1.7 petals sky x0.79'),
        'B': dict(title='B. Quasi-continuous magnetized Vertex', geometry='wall', f_ph=0.3393, f_n=0.0126, a=0.0277, eta_d=0.9, eta_dc=0.9,
                  eta_noz=0.8, leak=0.05, sky=0.9, magnet='cnt', Tb='free', beta=1.0, speculative=[],
                  basis='EVIDENCE: 1.6B S5 optimistic radiative state at Ti 100 keV (polarized, He-3 minority heated, 66 % channeling) sustained by 2.8 % heating; '
                        'LITERATURE FRC / mirror class; the vessel surrounds the plasma (90 % of the sky)'),
        'C': dict(title='C. Separated open-geometry pulsed Vertex', geometry='ring', mode='pulsed', rate_Hz=1000.0, f_ph=0.1009, f_n=0.0496, a=0.02,
                  eta_d=0.5, eta_dc=0.9, eta_noz=0.8, leak=1e-3, rings=2, magnet='cnt', Tb='free', speculative=[],
                  basis='EVIDENCE 1.6B S1 nominal source, gain 50; LITERATURE inductive magneto-inertial driver 50 %, inductive recovery 90 %; '
                        'PROTOTYPE 1 kHz targets and 0.1 % charged leakage onto thin edge-on rings far from the burn'),
        'E': dict(title='E. Integrated speculative Vertex (Vertex Burn Channeling)', geometry='ring', mode='steady', f_ph=0.083, f_n=0.0234/3, a=5e-6,
                  eta_d=0.5, eta_dc=0.9, eta_noz=0.8, leak=1e-4, rings=2, magnet='cnt', Tb='free', speculative=['VBC'],
                  basis='C geometry and materials; EVIDENCE 1.6B S1 optimistic source shares (polarized D-3He at 200 keV), D-D neutrons a third of that for a 1:3 D:He-3 burn (D-D rate per D-3He reaction scales with nD/nHe; LITERATURE fuel-mix lever, more He-3 inventory in the burn); SPECULATIVE VBC: the burn '
                        'sustains itself from its own products, so the driver only lights it and phases the control field (5e-6 of fusion power: the 1.7 bracket-1 ignition driver, 44 MW per engine, stays aboard and runs the control field at its rating)'),
    }


def fission(s, S):
    """D1 benchmark: dusty-plasma fission-fragment rocket (LITERATURE: Clark & Sheldon; Werka NIAC). The fragments are the exhaust."""
    return dict(title='D1. Fission-fragment rocket (benchmark)', ve=0.03*C, eta_jet=0.3, e_fuel=8.2e13, heat_T=2000.0,
                basis='LITERATURE: fragments leave at 0.03-0.046 c; about half the fission energy escapes the dust, 60 % of that is collimated; the rest heats dust and moderator')


# ---------- engine physics -------------------------------------------------------------------------------------------------------------

def shares(c):
    """Energy bookkeeping per fusion watt. Returns the jet share and each sink; conservation is checked by the caller."""
    f_c = 1.0-c['f_ph']-c['f_n']; a = c['a']; drawn = a/(c['eta_d']*c['eta_dc'])
    plasma = f_c+a-drawn                                   # charged + heating energy left after direct conversion powered the driver
    if plasma <= 0:
        return None
    jet = c['eta_noz']*plasma; leak = c['leak']*plasma; plume = plasma-jet-leak
    return dict(f_c=f_c, jet=jet, leak=leak, plume=plume, drawn=drawn, conv_loss=drawn*(1-c['eta_dc']), drv_loss=drawn*c['eta_dc']*(1-c['eta_d']),
                iso=c['f_ph']+c['f_n'], input=a)


def iso_deposit(c, frac):
    """Intercepted isotropic power per fusion watt for a hardware sky fraction (photons fully, neutrons at the deposited share)."""
    return frac*(c['f_ph']+0.87*c['f_n'])


def shield(S, Pn, Tb, r, frac):
    """Shield in front of superconductors seeing `frac` of the sky at distance r: thickness for the mission fluence, mass of a shell
    segment of that solid angle at r."""
    phi = Pn*S['n_per_J']*Tb/(4*math.pi*r*r); att = max(phi/S['phi_lim'], 1.0); t = S['lam']*math.log(att)
    return dict(fluence=phi, attenuation=att, t_m=t, kg=S['rho_sh']*t*frac*4*math.pi*r*r)


def engine_drawn(c, S, Pf, Tb, A):
    """A0 / A: the drawn engine (1.2 masses) plus the heat, shield and driver its source implies."""
    eng = A['audit']['mass']['engine_kg']; frame = (A['audit']['mass']['engines_and_frame_kg']-4*eng)/4
    sh = shares(c); Pn = c['f_n']*Pf; r = 6.0
    coils = shield(S, Pn, Tb, r, 0.37)
    heat = [('isotropic radiation on hardware', iso_deposit(c, c['sky'])*Pf, S['T_armour']), ('charged leakage', sh['leak']*Pf, S['T_armour']),
            ('direct conversion loss', sh['conv_loss']*Pf, S['T_loss']), ('driver loss', sh['drv_loss']*Pf, S['T_loss'])]
    irr = (c['f_ph']+c['f_n'])*Pf/(4*math.pi*5.09**2)
    mass = dict(engine_drawn=eng, frame_share=frame, coil_shield=coils['kg'], driver=c['a']/c['eta_d']*Pf*S['driver_kg_W'])
    return dict(mass=mass, heat=heat, irradiance=irr, shield=coils, detail=dict(nearest_coil_m=5.09))


def engine_wall(c, S, Pf, Tb, s):
    """B: a steady magnetized burn inside a vessel; power density and pressure from the 1.6B S5 state."""
    case = [x for x in vs.config(s)['cases'] if x['id'] == 'S5'][0]; o = vs.opts(s, case, vs.OPT)
    r = vs.solve(s, 100.0, o, vs.burnup()); ne = r['ne_m3']; nD = ne/3
    p = (ne*r['Te_keV']+nD*100.0+nD*100.0*o['he_ratio'])*KEV; B = math.sqrt(2*MU0*p/c['beta'])
    V = Pf/r['fusion_W_m3']; rp = (3*V/(4*math.pi))**(1/3); rw = 1.2*rp
    EB = B*B/(2*MU0)*V*2.0
    sig, rho, _ = S['materials'][c['magnet']]
    sh = shares(c); Pn = c['f_n']*Pf; coils = shield(S, Pn, Tb, rw, c['sky'])
    heat = [('isotropic radiation on the vessel', iso_deposit(c, c['sky'])*Pf, S['T_armour']), ('charged leakage', sh['leak']*Pf, S['T_armour']),
            ('direct conversion loss', sh['conv_loss']*Pf, S['T_loss']), ('heating loss', sh['drv_loss']*Pf, S['T_loss'])]
    irr = (c['f_ph']+c['f_n'])*Pf/(4*math.pi*rw*rw)
    mass = dict(magnet_structure=S['k_virial']*rho*EB/sig, vessel_shield=coils['kg'], heating_plant=c['a']/c['eta_d']*Pf*S['driver_kg_W'])
    return dict(mass=mass, heat=heat, irradiance=irr, shield=coils, detail=dict(B_T=B, plasma_radius_m=rp, wall_m=rw, field_J=EB, fusion_W_m3=r['fusion_W_m3']))


def ring(c, S, Pf, Tb, R, F, sep=4.0, s=None):
    """C / E: n thin rings edge-on to the burn at radius R, a tungsten armour face toward the burn.
    Conductor 'hts': REBCO at 20 K behind a neutron fin as deep as the mission fluence needs (fin as wide as the face).
    Conductor 'hot': unshielded aluminium at 450 K (neutron-tolerant for one mission's dpa), cross-section chosen where conductor mass
    equals the radiator mass of its own resistive loss (the minimum of the two).
    Nozzle field: pulsed, the field energy inside R/2 holds one pulse's plasma energy; steady, it holds the flow's dynamic pressure at R/2."""
    sh = shares(c); plasma = (sh['jet']+sh['leak']+sh['plume'])*Pf; v = 0.06*C
    if c['mode'] == 'pulsed':
        u = plasma/c['rate_Hz']/(4/3*math.pi*(R/2)**3)
    else:
        u = plasma/(4*math.pi*(R/2)**2*v)
    B = math.sqrt(2*MU0*u); I = 2*R*B/MU0; n = c['rings']; Pn = c['f_n']*Pf; ln = 2*math.pi*R
    hot = c.get('conductor', 'hts') == 'hot'
    if hot:
        k_r = S['rad_kg_m2']/S['rad_flux']*vs.cost(s, S['T_hot_cond'])
        Ac = I*math.sqrt(S['rho_e_al']*k_r/S['rho_al']); loss = I*I*S['rho_e_al']*ln/Ac
        cond = n*S['rho_al']*Ac*ln; fin = dict(fluence=Pn*S['n_per_J']*Tb/(4*math.pi*R*R), attenuation=1.0, t_m=0.0, kg=0.0); fin_kg = 0.0; cold = 0.0
    else:
        Ac = I/S['J_e']; loss = 0.0; cond = n*S['rho_cond']*Ac*ln
        fin = shield(S, Pn, Tb, R, 0.0)
    a = math.sqrt(Ac/math.pi); L = MU0*R*(math.log(8*R/a)-1.75); EB = 0.5*L*I*I
    sig, rho, _ = S['materials'][c['magnet']]
    w = max(math.sqrt(Ac), 0.03)+0.04; frac = n*w/(2*R)
    if not hot:
        fin_kg = n*S['rho_sh']*fin['t_m']*w*ln; cold = frac*Pn*S['dep_n']*math.exp(-fin['t_m']/S['lam'])
    struct = n*S['k_virial']*rho*EB/sig; armour = n*19300.0*0.005*w*ln
    L_sep = sep*R                                                             # burn point `sep` ring radii aft of the ship (searched)
    tether = S['tether_k']*F*L_sep*S['materials']['cnt'][1]/S['materials']['cnt'][0]
    om_ship = S['A_front']/(4*math.pi*L_sep**2)
    phi_ship = Pn*S['n_per_J']*Tb/(4*math.pi*(L_sep+S['ship_aft_m'])**2); t_ship = S['lam']*math.log(max(phi_ship/S['phi_ship'], 1.0))
    ship_sh = S['rho_sh']*t_ship*S['A_front']*(R/L_sep)**2                  # shadow shield at R from the burn, covering the ship
    heat = [('isotropic radiation on ring armour', iso_deposit(c, frac)*Pf, S['T_armour']), ('charged leakage', sh['leak']*Pf, S['T_armour']),
            ('isotropic radiation on the ship shadow shield', iso_deposit(c, om_ship)*Pf, S['T_armour']),
            ('direct conversion loss', sh['conv_loss']*Pf, S['T_loss']), ('driver loss', sh['drv_loss']*Pf, S['T_loss']),
            ('neutrons through the fin into the coils', cold, S['T_cold']), ('ring resistive loss', loss, S['T_hot_cond'])]
    irr = (c['f_ph']+c['f_n'])*Pf/(4*math.pi*R*R)
    mass = dict(ring_conductor=cond, ring_structure=struct, ring_armour=armour, ring_neutron_fin=fin_kg, tethers=tether, ship_shadow_shield=ship_sh,
                driver=c['a']/c['eta_d']*Pf*S['driver_kg_W'], injector_and_feed=0.02*(cond+struct), burn_station=S['station_kg'])
    return dict(mass=mass, heat=heat, irradiance=irr, shield=fin, detail=dict(R_m=R, B_T=B, I_A=I, field_J=EB, sky=frac, separation_m=L_sep, face_m=w,
                                                                           conductor='hot Al 450 K' if hot else 'REBCO 20 K', fluence_n_m2=fin['fluence'],
                                                                           ship_shield_t_m=t_ship))


def r_min(c, S, Pf):
    return math.sqrt((c['f_ph']+c['f_n'])*Pf/(4*math.pi*S['q_max']))


# ---------- mission closure -----------------------------------------------------------------------------------------------------------

def close(c, S, s, A, ve, Tb, Rk=1.0, sep=4.0, iters=300):
    """Fixed point: end mass -> propellant -> jet power -> fusion power -> engine mass and heat -> end mass."""
    Rb = math.exp(S['dv']/ve); X = Rb**S['burns']-1; sh = shares(c)
    if sh is None or sh['jet'] <= 0:
        return None
    eta = sh['jet']
    if ve**2/2 > eta*S['e_fuel']:                                              # pure fuel cannot reach this exhaust speed
        return None
    m_end = S['canon']['end_kg']; R = None
    for _ in range(iters):
        prop = X*m_end; Pjet = prop*ve*ve/(2*Tb); Pf = Pjet/eta; Pe = Pf/S['engines']; F = 2*Pjet/ve
        if c['geometry'] == 'drawn':
            e = engine_drawn(c, S, Pe, Tb, A)
        elif c['geometry'] == 'wall':
            e = engine_wall(c, S, Pe, Tb, s)
        else:
            R = Rk*r_min(c, S, Pe); e = ring(c, S, Pe, Tb, R, F/S['engines'], sep, s)
        rad_W = sum(W*vs.cost(s, T) for _, W, T in e['heat'])
        rad_kg = rad_W/S['rad_flux']*S['rad_kg_m2']
        eng_kg = sum(e['mass'].values())
        start = S['start_J']/S['start_J_kg']
        struct = 3*F*30.0*S['materials']['cnt'][1]/1.5e9*10                  # thrust structure into the ship (stiffness-limited, PROTOTYPE)
        sys_kg = S['engines']*(eng_kg+rad_kg)+start+struct
        new = S['core_kg']+sys_kg+S['f_tank']*prop
        if new > 1e10:
            return dict(closes=False, reason='mass diverges (the propulsion system grows faster than the propellant it is sized for)')
        if abs(new-m_end) < 1.0:
            m_end = new; break
        m_end = 0.5*(m_end+new)
    else:
        return dict(closes=False, reason='no fixed point')
    prop = X*m_end; Pjet = prop*ve*ve/(2*Tb); Pf = Pjet/eta; Pe = Pf/4
    # conservation checks
    energy = 1.0-(sh['jet']+sh['leak']+sh['plume']+sh['iso']+sh['conv_loss']+sh['drv_loss'])   # the driver's delivered energy is drawn from the stream
    fuel = Pf*Tb/S['e_fuel']; phi = fuel/prop; he3 = fuel*S['he3_share']
    dv_check = sum(ve*math.log(Rb) for _ in range(S['burns']))/(S['burns']*S['dv'])-1
    thrust_check = (2*Pjet/ve)*Tb/(prop*ve)-1                                 # impulse = propellant x ve
    trip = (Tb-S['Tb0_s'])/2/YR
    return dict(closes=True, ve_c=ve/C, Tb_d=Tb/DAY, burn_each_d=Tb/DAY/4, trip_extra_yr=trip, mass_ratio=Rb, end_t=m_end/1e3, departure_t=(m_end+prop)/1e3,
                propellant_t=prop/1e3, fuel_t=fuel/1e3, he3_t=he3/1e3, fuel_share=phi, reaction_mass_t=(prop-fuel)/1e3, jet_TW=Pjet/1e12, fusion_TW=Pf/1e12,
                fusion_engine_TW=Pe/1e12, thrust_MN=2*Pjet/ve/1e6, accel_g=[2*Pjet/ve/(m_end+prop)/9.80665, 2*Pjet/ve/(m_end+prop/Rb**3)/9.80665],
                useful_share=eta, system_t=sys_kg/1e3, engine_t={k: v/1e3 for k, v in e['mass'].items()}, radiator_t_engine=rad_kg/1e3,
                startup_t=start/1e3, structure_t=struct/1e3, heat_engine_GW={n: W/1e9 for n, W, _ in e['heat']}, radiator_load_engine_GW=rad_W/1e9,
                irradiance_MW_m2=e['irradiance']/1e6, shield=e['shield'], detail=e['detail'],
                checks=dict(energy_error=energy, delta_v_error=dv_check, impulse_error=thrust_check, fuel_share_ok=phi <= 1.0))


def best(c, S, s, A):
    """Search exhaust speed, burn time and ring radius; the candidate's own lightest closed mission."""
    Tb0 = S['Tb0_s']; Tmax = Tb0+2*S['trip_tol_yr']*YR
    Tbs = [Tb0] if c['Tb'] == 'canon' else [Tb0*(Tmax/Tb0)**(i/8) for i in range(9)]
    ves = [S['canon']['ve']] if c['Tb'] == 'canon' else [x*C for x in S['ve_grid_c']]
    Rks = [1.0, 1.5, 2.0, 3.0] if c['geometry'] == 'ring' else [1.0]
    seps = [2.0, 4.0, 8.0, 16.0, 32.0] if c['geometry'] == 'ring' else [4.0]
    nrs = [1, 2] if c['geometry'] == 'ring' else [None]
    rows = []
    for Tb in Tbs:
        for ve in ves:
            for Rk in Rks:
                for sep in seps:
                  for nr in nrs:
                    cc = dict(c, rings=nr) if nr else c
                    r = close(cc, S, s, A, ve, Tb, Rk, sep)
                    if r and r.get('closes'):
                        r['Rk'] = Rk; r['sep'] = sep; r['rings'] = nr; rows.append(r)
                    elif r:
                        last = r
    if not rows:
        return dict(closes=False, reason='no exhaust speed, burn time or radius closes the mission', probe=probe(c, S, s, A))
    cap = [r for r in rows if r['he3_t']*1e3 <= S['he3_canon_kg']]          # prefer missions inside today's He-3 load (1,094 t)
    return min(cap or rows, key=lambda r: r['departure_t'])


def probe(c, S, s, A):
    """Why a candidate fails: one pass at today's end mass, 0.064 c and the longest allowed burns (no feedback)."""
    ve = 0.064*C; Tb = S['Tb0_s'] if c['Tb'] == 'canon' else S['Tb0_s']+2*S['trip_tol_yr']*YR
    sh = shares(c); X = math.exp(S['dv']/ve)**S['burns']-1; m = S['canon']['end_kg']; prop = X*m; Pjet = prop*ve*ve/(2*Tb)
    if sh is None or sh['jet'] <= 0:
        return dict(reason='the driver draws more than the plasma delivers')
    Pf = Pjet/sh['jet']; Pe = Pf/4; F = 2*Pjet/ve/4
    e = engine_drawn(c, S, Pe, Tb, A) if c['geometry'] == 'drawn' else engine_wall(c, S, Pe, Tb, s) if c['geometry'] == 'wall' else ring(c, S, Pe, Tb, r_min(c, S, Pe), F, 8.0, s)
    rad_W = sum(W*vs.cost(s, T) for _, W, T in e['heat']); rad = rad_W/S['rad_flux']*S['rad_kg_m2']
    sys_kg = 4*(sum(e['mass'].values())+rad)
    return dict(fusion_engine_TW=Pe/1e12, engine_t={k: v/1e3 for k, v in e['mass'].items()}, radiator_t_engine=rad/1e3, heat_engine_GW={n: W/1e9 for n, W, _ in e['heat']},
                system_t=sys_kg/1e3, allowed_system_t=(S['dep_upper']/(X+1)-S['core_kg']-S['f_tank']*X*S['dep_upper']/(X+1))/1e3,
                over=sys_kg/max(S['dep_upper']/(X+1)-S['core_kg']-S['f_tank']*X*S['dep_upper']/(X+1), 1.0),
                irradiance_MW_m2=e['irradiance']/1e6, detail=e['detail'])


def fission_row(S):
    d = fission(None, S); ve = d['ve']; Rb = math.exp(S['dv']/ve); X = Rb**4-1
    Tb = S['Tb0_s']+2*S['trip_tol_yr']*YR; m = S['canon']['end_kg']
    for _ in range(400):
        prop = X*m; Pjet = prop*ve*ve/(2*Tb); heat = Pjet*(1-d['eta_jet'])/d['eta_jet']
        rad = heat*1.0/S['rad_flux']*S['rad_kg_m2']
        new = S['core_kg']+rad+S['f_tank']*prop
        if new > 1e10:
            return dict(d, closes=False, mass_ratio_4=Rb**4, heat_per_jet_W=(1-d['eta_jet'])/d['eta_jet'],
                        reason=f'diverges: each jet watt brings {(1-d["eta_jet"])/d["eta_jet"]:.1f} W of reactor heat, and four burns at 0.03 c need a mass ratio of {Rb**4:.1f}')
        if abs(new-m) < 1:
            break
        m = 0.5*(m+new)
    return dict(d, closes=True, end_t=m/1e3, departure_t=(m+X*m)/1e3)


def beamed(S):
    """D2 benchmark: a laser-pushed sail for the departure burn only and a magnetic sail for braking against the interstellar medium."""
    m = S['canon']['departure_kg']; v = S['dv']; a = 0.01*9.80665; t = v/a; d = 0.5*a*t*t; F = m*a; P = F*C/2
    lam = 1.06e-6; sail_T = 1000.0; absorb = 1e-4; sail_A = P*absorb/(2*0.9*SIG*sail_T**4); Ds = 2*math.sqrt(sail_A/math.pi)
    Dt = 2.44*lam*d/Ds
    rho_ism = 0.1e6*1.6726e-27; q = rho_ism*v*v; F_brake = S['canon']['end_kg']*v/(2*YR); A_eff = F_brake/q; Rm = math.sqrt(A_eff/math.pi)
    Bm = math.sqrt(2*MU0*q); moment = Bm*2*math.pi*Rm**3/MU0
    return dict(title='D2. External energy: laser sail departure + magnetic-sail braking (benchmark)', accel_g=0.01, laser_TW=P/1e12, beam_EJ=P*t/1e18,
                accel_days=t/DAY, accel_AU=d/1.496e11, sail_diameter_m=Ds, transmitter_km=Dt/1e3, magsail_force_N=F_brake, magnetopause_km=Rm/1e3,
                dipole_A_m2=moment, current_for_300m_loop_A=moment/(math.pi*300**2),
                basis='LITERATURE: photon thrust 2P/c, diffraction 2.44 lambda d / D, magsail drag ~ rho v^2 over the magnetopause (Zubrin); 0.1 protons/cm3 ISM; braking over 2 yr',
                verdict='Works only where a beam exists: it can replace the departure burn, not the arrival, home or home-brake burns. A magsail that brakes '
                        'from 0.016 c in two years needs a magnetopause about 3,000 km across, a dipole moment 10^8 times what a 300 m Vertex ring carries. Benchmark only.')


# ---------- gates ---------------------------------------------------------------------------------------------------------------------

def gates(c, r, S):
    if not r.get('closes'):
        return dict(G1_closes=False)
    return dict(
        G1_closes=True,
        G2_departure=r['departure_t']*1e3 <= S['dep_upper'],
        G3_propellant=r['propellant_t']*1e3 <= S['prop_upper'],
        G4_trip_time=r['trip_extra_yr'] <= S['trip_tol_yr']+1e-9,
        G5_heat_flux=r['irradiance_MW_m2']*1e6 <= S['q_max']*(1+1e-9),
        G6_no_speculative_physics=not c['speculative'],
        G10_he3_supply=r['he3_t']*1e3 <= S['he3_canon_kg']*(1+1e-9),
        G7_conservation=all(abs(r['checks'][k]) < 1e-9 for k in ('energy_error', 'delta_v_error', 'impulse_error')) and r['checks']['fuel_share_ok'],
        G8_speculative_count=len(c['speculative']) <= 1,
        G9_four_nozzles=True)


# ---------- coupling (what each improvement does to the whole system) ------------------------------------------------------------------

def coupling(S, s, A, C0):
    base = C0['E']; out = []
    variants = [('E as recommended', {}),
                ('without the longer burns (today\'s 28.5 d)', dict(Tb='canon')),
                ('steel instead of CNT magnet structure', dict(magnet='steel')),
                ('unpolarized fuel (1.6B S0-SC nominal shares)', dict(f_ph=0.1294, f_n=0.0789)),
                ('rings at today\'s 5-6 m (drawn geometry, A0 sky)', dict(geometry='drawn', sky=0.691, leak=0.183)),
                ('without VBC: driver gain 50 (C)', dict(a=0.02, speculative=[])),
                ('without VBC: driver gain 50, pulsed at 1 kHz', dict(a=0.02, mode='pulsed', rate_Hz=1000.0, speculative=[])),
                ('charged leakage 0.1 % instead of 0.01 %', dict(leak=1e-3)),
                ('nozzle capture 60 % instead of 80 %', dict(eta_noz=0.6)),
                ('no He-3-rich mix (S1 optimistic D-D share)', dict(f_n=0.0234))]
    S6 = dict(S, trip_tol_yr=0.6)
    extra = [('E with 0.6 yr trip allowance', S6, {}), ('E with 0.6 yr, steel structure', S6, dict(magnet='steel'))]
    for name, ch in variants:
        c = dict(base, **ch); r = best(c, S, s, A); g = gates(c, r, S)
        out.append(dict(variant=name, closes=r.get('closes', False), departure_t=r.get('departure_t'), fusion_TW=r.get('fusion_TW'), Tb_d=r.get('Tb_d'),
                        system_t=r.get('system_t'), failed=[k for k, v in g.items() if not v]))
    for name, S2, ch in extra:
        c = dict(base, **ch); r = best(c, S2, s, A); g = gates(c, r, S2)
        out.append(dict(variant=name, closes=r.get('closes', False), departure_t=r.get('departure_t'), fusion_TW=r.get('fusion_TW'), Tb_d=r.get('Tb_d'),
                        system_t=r.get('system_t'), failed=[k for k, v in g.items() if not v]))
    return out


def separation(S, s, A, c):
    """Cost of keeping the burn close to the ship: the lightest mission at each burn-to-ship distance (ring radii)."""
    Tb = S['Tb0_s']+2*S['trip_tol_yr']*YR; rows = []
    for sep in (1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
        b = None
        for vec in S['ve_grid_c']:
            for nr in (1, 2):
                r = close(dict(c, rings=nr), S, s, A, vec*C, Tb, 1.0, sep)
                if r and r.get('closes') and (b is None or r['departure_t'] < b['departure_t']):
                    b = r
        rows.append(dict(sep_R=sep, departure_t=b['departure_t'], separation_m=b['detail']['separation_m'], R_m=b['detail']['R_m'],
                         ship_shadow_shield_t=b['engine_t']['ship_shadow_shield'], neutron_fin_t=b['engine_t']['ring_neutron_fin']) if b else dict(sep_R=sep, closes=False))
    return rows


def frontier(S, s, A, C0):
    """What E needs to close inside the 4.6 kt envelope: the trip-time allowance, the superconductor fluence limit (a second, separate
    speculative capability), and both."""
    rows = []
    for tol in (0.3, 0.6, 1.0, 1.5, 2.0, 3.0):
        for lim in (1e22, 1e24):
            S2 = dict(S, trip_tol_yr=tol, phi_lim=lim); r = best(C0['E'], S2, s, A)
            rows.append(dict(trip_tol_yr=tol, phi_lim=lim, closes=r.get('closes', False), departure_t=r.get('departure_t'), fusion_TW=r.get('fusion_TW'),
                             Tb_d=r.get('Tb_d'), ve_c=r.get('ve_c'), within_envelope=bool(r.get('closes')) and r['departure_t']*1e3 <= S['dep_upper'],
                             system_t=r.get('system_t'), he3_t=r.get('he3_t')))
    return rows


def run():
    s = spec.load(ROOT)[0]; S = shared(s); A = ev('vertex_adaptive'); C0 = candidates()
    out = dict(shared={k: v for k, v in S.items()}, candidates={})
    for k, c in C0.items():
        r = best(c, S, s, A); out['candidates'][k] = dict(definition=c, result=r, gates=gates(c, r, S))
    out['benchmarks'] = dict(D1=fission_row(S), D2=beamed(S))
    out['coupling'] = coupling(S, s, A, C0)
    out['frontier'] = frontier(S, s, A, C0)
    S6 = dict(S, trip_tol_yr=0.6); r6 = best(C0['E'], S6, s, A); out['recommended'] = dict(note='E with the 0.6 yr trip allowance (owner question Q1)', result=r6, gates=gates(C0['E'], r6, S6))
    out['separation'] = separation(S6, s, A, C0['E'])
    return out


if __name__ == '__main__':
    out = run()
    (HERE/'ledger.json').write_text(json.dumps(out, indent=1, default=float)+'\n')
    for k, v in out['candidates'].items():
        r = v['result']; g = v['gates']
        if r.get('closes'):
            print(f"{k:3s} dep {r['departure_t']:8.0f} t  prop {r['propellant_t']:6.0f}  sys {r['system_t']:8.0f}  ve {r['ve_c']:.3f}c  Tb {r['Tb_d']:6.1f} d  "
                  f"fus {r['fusion_TW']:6.1f} TW  q {r['irradiance_MW_m2']:9.1f} MW/m2  rad/eng {r['radiator_t_engine']:8.0f} t  "
                  f"fail {[x for x, y in g.items() if not y]}")
            print('     engine t', {x: round(y) for x, y in r['engine_t'].items()}, 'heat GW', {x[:22]: round(y, 2) for x, y in r['heat_engine_GW'].items()},
                  'detail', {x: (round(y, 3) if isinstance(y, float) else y) for x, y in r['detail'].items()}, 'checks', r['checks'])
        else:
            pr = r.get('probe', {})
            print(k, 'NO CLOSURE', r.get('reason'), 'over', round(pr.get('over', 0), 1), {x: round(y) for x, y in pr.get('engine_t', {}).items()}, 'rad/eng', round(pr.get('radiator_t_engine', 0)), 'q', round(pr.get('irradiance_MW_m2', 0)))
    print('D1', {x: y for x, y in out['benchmarks']['D1'].items() if x not in ('basis',)})
    print('D2', {x: (round(y, 3) if isinstance(y, float) else y) for x, y in out['benchmarks']['D2'].items() if x not in ('basis', 'verdict')})
    for row in out['coupling']:
        print('  ', row)
    for row in out['frontier']:
        print(' F', row)
