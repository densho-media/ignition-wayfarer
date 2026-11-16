"""Vertex Engine 1.7: Dynamic Lattice Drive Mechanism (owner brief 2026-11-16 09:23Z). Research model, not canon.

Question: can moving mechanical and electromagnetic assemblies (rotating field crowns, rotary storage and induction, variable-geometry
flux petals, a dynamic Fiji lattice) do better than the static Compact Vertex nozzle on mass, useful thrust, hardware heat, radiators,
magnetic performance per mass and the 0.016 c mission? The model reads the engine (vertex_engine, vertex_structure), the 1.3 magnet, the
1.5-1.6B evidence and canon and changes none of them. Every candidate is screened by Level 1 physics first (timescales, conservation,
induction, rotor mechanics, thermodynamics), then costed at the mission point on the 1.6B budget (vertex_source.budget, unchanged) with
explicit factors for what the mechanism changes. Speculative values are never inserted: where a channel cannot close, the value that would
close it is solved for and reported beside its nearest real precedent.

Sections (brief section in brackets):
  audit        A  the current engine, loads, field, pulse timing, power points, radiators, the ratio ledger, Fiji, mass, animation hooks
  timescales   4  plasma, product and radiation transit against the pulse period, mechanical motion and electronic switching
  crown        9.1  C1 Rotary Field Crown: field invariance, ripple, eddy loss in the cluster field, rotor stress, angular momentum, burst
  dynamo       9.2  C2 Pulsed Lattice Dynamo: storage need and mass, recirculating power, switched-coil recovery, HTS dynamo, Fiji cycle
  petals       9.3  C3 Variable Geometry Flux Nozzle: deployed scale k, sky, fluence, forces, field energy, mass, envelope
  tread        9.4  C4 Armour Tread (added candidate): poloidal tile circulation, peak flux, self-radiation, mass
  radiation    6  the five radiation approaches with numbers
  budget       7, 13  mission-point heat ledger per candidate and the hybrid; what still has to be supplied to close
  compare, sequence, failures, integration, verdict   9, 10, 12-E, 13, 14

python3 src/wayfarer/vertex_dynamic.py [--evidence]   prints the summary (and writes references/evidence/vertex_dynamic.json).
"""
import cmath
import hashlib
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import operating_point as op  # noqa: E402
import vertex_cluster as vc  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_fiji as vf  # noqa: E402
import vertex_fiji_a as va  # noqa: E402
import vertex_source as vso  # noqa: E402
import vertex_structure as vs  # noqa: E402

EVIDENCE_PATH = ROOT/'references'/'evidence'/'vertex_dynamic.json'
MAGNET_PATH = ROOT/'references'/'evidence'/'vertex_magnet.json'
STRUCTURE_PATH = ROOT/'references'/'evidence'/'vertex_structure.json'
MU0 = 4e-7*math.pi; QE = 1.602176634e-19; MP = 1.67262192e-27; MN_KG = 1.67492750e-27; ME = 9.1093837015e-31; C0 = 2.99792458e8
SIGMA_SB = 5.670374419e-8; SIGMA_T = 6.6524587e-29; NA = 6.02214076e23; MEV = 1.602176634e-13; TNT_J = 4.184e9
OPT, NOM, PES = 0, 1, 2
OUTCOMES = {'A': 'DYNAMIC_CLOSES', 'B': 'DYNAMIC_MOVES_A_GATE', 'C': 'DYNAMIC_HELPS_LOCALLY', 'D': 'DYNAMIC_WORSE_THAN_STATIC'}


def config(s):
    return s['vertex_dynamic']


def _j(p):
    return json.loads(Path(p).read_text())


def speed(m_kg, E_J):
    """Relativistic speed of a particle of rest mass m and kinetic energy E."""
    g = 1.0+E_J/(m_kg*C0**2)
    return C0*math.sqrt(1.0-1.0/g**2)


# ---------- A: audit -------------------------------------------------------------------------------------------------------------------

def audit(s):
    """Phase A: the engine as the repository has it, every figure from its owning module or evidence (nothing re-derived differently)."""
    g = ve.config(s)['geometry']; st = ve.stations(s); cs = vs.coils(s); m = ve.mass_estimate(s); M = _j(MAGNET_PATH)
    SR = _j(STRUCTURE_PATH)['report']; SO = _j(vso.EVIDENCE_PATH); q = s['physics']['operating_point']; rad = s['radiators']
    m0 = M['candidates'][0]; pl = M['plasma']; mag = m0['magnet']; loads = {x['id']: x for x in SR['load_cases']}
    pw = vso.power_points(s); A = vso.allocation(s); mi = op.mission(s); b = op.burn(s)
    area = rad['effective_area']['value']; T = rad['temperature']['value']; e = rad['emissivity']['value']
    recomputed = area*e*SIGMA_SB*T**4
    pulse_mission = pw['mission']/pl['yield_J']
    fig = SO['geometry']; fh = vf.r15()['cluster']['first_hit']
    FA = _j(va.EVIDENCE_PATH); fg2 = FA['geometries']['FG-2']
    best = min((r for r in SO['combined']['rows'] if r.get('point') == 'mission' and 'ratio' in r), key=lambda r: r['ratio'])
    frame = SR['mass'].get('frame_1_2_kg') or vs.frame_mass(s)
    engine_four = 4*m['total_kg']; ship = s['physics']['protected_burnout_mass']['value']
    import drive_manifold as dm
    return dict(
        geometry=dict(burn_x=st['burn'], shield_aft_x=st['shield_aft'], exit_x=st['exit'], standoff_m=g['standoff_m'],
                      shield_aft_radius_m=g['shield_aft_radius_m'], max_radius_m=g['max_radius_m'], maintenance_m=g['maintenance_clearance_m'],
                      coils=[dict(name=c['name'], group=c['group'], x=c['x'], r=c['r'], winding=c['a'], cryostat=c['cryostat'], dz_burn=c['x']-st['burn'],
                                  d_burn=math.hypot(c['x']-st['burn'], c['r'])) for c in cs],
                      engines=4, cluster_radius_m=math.hypot(*vc.placements(s)[0]['origin'][1:]), adjacent_m=SR['dipole']['adjacent_m'],
                      diagonal_m=SR['dipole']['diagonal_m']),
        mass=dict(engine_kg=m['total_kg'], by_category=SR['mass']['by_category_1_2'], by_material=m['by_material'], frame_kg=frame,
                  engines_and_frame_kg=engine_four+frame, protected_ship_kg=ship, departure_kg=mi['departure_mass_kg'],
                  departure_upper_kg=s['physics']['departure_mass']['upper_kg'],
                  margin_kg=s['physics']['departure_mass']['upper_kg']-mi['departure_mass_kg'],
                  consistent=engine_four+frame <= ship,
                  note='The 1.2 engine and frame estimate is not read by the ship mass budget (docs/MODEL.md): four engines and the frame are '
                       f'{(engine_four+frame)/1e6:.1f} kt against a {ship/1e6:.1f} kt protected ship. Every mass change below is reported against '
                       'both the static engine and the 174 t departure margin.'),
        loads=dict(coil_force_N={k: v for k, v in zip(('NOMINAL', 'CONSERVATIVE', 'EXTREME'), [x[1]*1e6 for x in loads['LC-02']['size']])},
                   inter_engine_N=loads['LC-03']['value_N'], thrust_demonstrator_N=loads['LC-01']['value_N'], pulse_impulse_Ns=loads['LC-04']['value_N'],
                   thrust_mission_N=b['peak_thrust_N']/4, dipole_Am2=SR['dipole']['moment_Am2'], single_engine_moment_Nm=loads['LC-06']['value_N']),
        field=dict(stored_J=mag['energy_J'], rows=mag['rows'], stop_field_T=vs.stop_field(s), currents_At=m0['eval']['currents_At'],
                   lead_current_A=mag['lead_current_A'], ramp_supply_V=mag['ramp_supply_V'], skin_depth_m=mag['pulse']['skin_depth_m'],
                   flux_compression_valid=mag['pulse']['compression_valid'], max_current_swing=mag['pulse']['max_current_swing']),
        pulse=dict(yield_J=pl['yield_J'], charged_J=pl['energy_J']['design'], rate_demonstrator_Hz=pl['pulse_Hz'], period_demonstrator_s=pl['period_s'],
                   rate_mission_Hz=pulse_mission, period_mission_s=1.0/pulse_mission, exhaust_m_s=pl['exhaust_m_s'], plasma_mass_kg=pl['mass_kg'],
                   note='The mission rate holds the 1.3 yield per pulse and raises the rate to the canon mission power (VTX-S1/S2 unchanged).'),
        power=dict(demonstrator_W=pw['demonstrator'], mission_W=pw['mission'], mission_four_W=4*pw['mission'], jet_four_W=b['peak_jet_power_W'],
                   ve_m_s=b['exhaust_velocity_m_s'], mdot_four_kg_s=b['peak_mass_flow_kg_s'], burn_d=b['duration_d'], burns=q['mission_burns'],
                   canon_absorbed_fraction=q['absorbed_fraction'], max_absorbed_fraction=b['max_absorbed_fraction']),
        radiators=dict(installed_W=A['installed_W'], recomputed_W=recomputed, area_m2=area, T_K=T, emissivity=e, drive_W=A['drive_W'],
                       per_engine_W=A['per_engine_W'], thermal_system_allowance_t=100.0,
                       supported='CALCULATED from WORKING canon (area x emissivity x sigma T^4); conditional on an 1800 K hot face (OD-023). The '
                                 '14.4 GW is a consequence of the radiator canon, not an arbitrary cap. What actually binds is the canon absorbed '
                                 'fraction 4e-5: at the mission power the drive share allows 4e-5 of the fusion power into hardware.'),
        exposure=dict(hardware_sky_mesh=fig['hardware_sky_mesh'], own_engine_first_hit=fh['OWN_ENGINE'], space=fh['SPACE'],
                      coil_sky=next(x['coil_sky'] for x in fig['shifts'] if x['shift_m'] == 0.0), behind_first=vf.r15()['cluster']['behind_first']),
        ledger=SO['ledger']['rows'],
        best_1_6b=dict(case=best['case'], bracket=best['bracket'], shield=best['shield'], ratio=best['ratio'], neutron_alone_ratio=best['neutron_alone_ratio'],
                       nonphoton_ratio=best['nonphoton_ratio']),
        fiji=dict(T_K={k: s['vertex_fiji'][k] for k in ('T_release_K', 'T_activation_K', 'T_operating_K', 'T_saturation_K', 'T_quench_K')},
                  mu0_Ms_T=s['vertex_fiji']['mu0_Ms_T'], A_max=s['vertex_fiji']['A_max'], fg2_kg=fg2['mass_kg'], fg2_four_kg=4*fg2['mass_kg'],
                  best_seeded_share=FA['answers']['best_seeded_share'], best_oriented=FA['answers']['best_oriented'],
                  note='1.6A: field-following (SEEDED, the one property) adds at most 3 % of the stop field; ORIENTED needs coercivity at 1000 K '
                       '(a second property). FG-2 adds about 1.1 kt per engine.'),
        animation=dict(control_variables=sorted(dm.VARIABLES.values()), states=list(vc.STATES), drivers=len(vc.drivers(s)),
                       note='One DRIVE_MANIFOLD_CTRL object drives per-engine effects through Blender drivers that the viewer evaluates '
                            '(vertex_cluster.drivers / display); named states OFF..SHUTDOWN. No moving engine part and no Godot mechanism '
                            'binding exists for the engines (the export is static).'))


# ---------- 4: timescales --------------------------------------------------------------------------------------------------------------

def timescales(s, A):
    """Can motion act on the plasma? Transit of exhaust, products and radiation to each coil against the pulse period, a rim's travel in
    those times, the field modulation a segmented rotor can make, the voltage a superconducting coil needs to follow a pulse, and the
    rotating-field window (ion to electron cyclotron frequency) that real plasma current drive uses."""
    c = config(s); P = A['pulse']; coils = A['geometry']['coils']; L2 = next(x for x in coils if x['name'] == 'L2')
    sp = dict(exhaust=P['exhaust_m_s'], proton_14_7=speed(MP, 14.7*MEV), alpha_3_6=speed(4.00151*1.66053907e-27, 3.6*MEV),
              neutron_2_45=speed(MN_KG, 2.45*MEV), neutron_14_1=speed(MN_KG, 14.1*MEV), photon=C0)
    transit = {k: {x['name']: x['d_burn']/v for x in coils} for k, v in sp.items()}
    t_ex = transit['exhaust']['L2']; mech = []
    for v in c['rim_speed_m_s']:
        f_rot = v/(2*math.pi*L2['r']); fm = c['crown_segments']*f_rot
        mech.append(dict(rim_m_s=v, travel_in_transit_m=v*t_ex, travel_in_period_m=v*P['period_mission_s'], rotation_Hz=f_rot,
                         modulation_Hz=fm, modulation_over_pulse=fm/P['rate_mission_Hz'], omega_rad_s=c['crown_segments']*v/L2['r']))
    fl = A['field']; rows = []
    for r in fl['rows']:
        L = fl['ramp_supply_V']*r['ramp_s']/fl['lead_current_A']
        rows.append(dict(name=r['name'], L_H=L, V_follow_10pc=L*0.1*fl['lead_current_A']/P['period_mission_s']))
    B = fl['stop_field_T']; wci = QE*B/MP; wce = QE*B/ME
    worst = max(m['modulation_over_pulse'] for m in mech)
    return dict(speeds_m_s=sp, transit_s=transit, pulse_period_s=dict(demonstrator=P['period_demonstrator_s'], mission=P['period_mission_s']),
                mechanical=mech, switch_s=c['switch_time_s'], coil_slew=rows,
                rmf=dict(B_T=B, omega_ci=wci, omega_ce=wce, omega_mech_max=max(m['omega_rad_s'] for m in mech),
                         gap=wci/max(m['omega_rad_s'] for m in mech)),
                verdict=dict(motion_over_pulse=worst, plasma_transit_s=t_ex,
                             statement=f'The exhaust reaches L2 in {t_ex*1e9:.0f} ns; a 1 km/s rim moves {1000*t_ex*1e3:.2f} mm in that time and a '
                                       f'segmented crown modulates the field at {worst:.1e} of the mission pulse rate. Motion can only set the geometry '
                                       'between pulses (quasi-static); it cannot shape a pulse. Electronic switching is 10-100 times faster than the '
                                       'transit, a superconducting coil is not (it needs ~1e8 V to follow a pulse), and the flux the pulse compresses '
                                       'into the static coils is already the lossless dynamic coupling.'))


# ---------- C1: Rotary Field Crown -----------------------------------------------------------------------------------------------------

def _dipole_field(m_vec, r_vec):
    rr = math.sqrt(sum(x*x for x in r_vec)); u = [x/rr for x in r_vec]; md = sum(a*b for a, b in zip(m_vec, u))
    return [MU0/(4*math.pi*rr**3)*(3*md*ui-mi) for ui, mi in zip(u, m_vec)]


def cluster_ripple(s, A, n=64, harmonics=8):
    """Field of the three other engines (point dipoles at their coil-set moment and polarity) round the crown ring of engine N1, in N1's
    frame: azimuthal Fourier amplitudes of each component. A crown rotating through it sees harmonic m at m times its rotation rate."""
    pls = vc.placements(s); me = A['loads']['dipole_Am2']; L2 = next(x for x in A['geometry']['coils'] if x['name'] == 'L2')
    p0 = pls[0]; ax = p0['axes']; o = p0['origin']
    def world(lx, ly, lz):
        return [o[i]+lx*ax[0][i]+ly*ax[1][i]+lz*ax[2][i] for i in range(3)]
    def local(v):
        return [sum(v[i]*ax[k][i] for i in range(3)) for k in range(3)]
    comps = [[0j]*(harmonics+1) for _ in range(3)]; Bmax = 0.0
    for j in range(n):
        ph = 2*math.pi*j/n; P = world(L2['x'], L2['r']*math.cos(ph), L2['r']*math.sin(ph)); Bw = [0.0, 0.0, 0.0]
        for p in pls[1:]:
            mv = [me*p['polarity']*p['axes'][0][i] for i in range(3)]
            # moment sits at the coil-set centre near the burn of each engine (engine frame x of L2)
            cen = [p['origin'][i]+L2['x']*p['axes'][0][i] for i in range(3)]
            b = _dipole_field(mv, [P[i]-cen[i] for i in range(3)]); Bw = [Bw[i]+b[i] for i in range(3)]
        Bl = local(Bw); Bmax = max(Bmax, math.sqrt(sum(x*x for x in Bl)))
        for k in range(3):
            for h in range(harmonics+1):
                comps[k][h] += Bl[k]*cmath.exp(-1j*h*ph)/n
    amp = [math.sqrt(sum((2*abs(comps[k][h]))**2 for k in range(3))) for h in range(harmonics+1)]
    return dict(B_max_T=Bmax, mean_T=math.sqrt(sum(abs(comps[k][0])**2 for k in range(3))), harmonic_T=amp)


def crown(s, A, T):
    """C1: counter-rotating segmented crowns at L2. (1) An axisymmetric current or magnetization turned about its own axis makes the same
    field at every instant (exact); a segmented crown adds an N-fold ripple ~ (rho/R)^N that rotates at N times its rotation rate. (2) Eddy
    heating of a conducting crown sweeping the cluster's non-axisymmetric field (thin-section formula pi^2 f^2 B^2 t^2 sigma / 6). (3) Rim
    stress rho_eff v^2 on the CFRP band, angular momentum, gyroscopic torque at the ship's slew rate, kinetic (burst) energy. (4) A
    magnetized (Fiji) crown in the coil's own gradient: the pull its bearings carry."""
    c = config(s); L2 = next(x for x in A['geometry']['coils'] if x['name'] == c['crown_loop'])
    R = L2['r']; Asec = c['crown_section_m2']; rho = c['crown_density_kg_m3']; mass = 2*math.pi*R*Asec*rho
    rho_eff = rho/c['crown_band_share']; v_max = math.sqrt(c['cfrp_allowable_Pa']/rho_eff); tsec = math.sqrt(Asec)
    rip = cluster_ripple(s, A); rows = []
    for v in c['rim_speed_m_s']+[v_max]:
        Om = v/R; Iz = mass*R**2; H = Iz*Om; KE = 0.5*mass*v**2; f = Om/(2*math.pi)
        eddy = {f'{sig:g}': sum(math.pi**2*(h*f)**2*rip['harmonic_T'][h]**2*tsec**2*sig/6.0 for h in range(1, len(rip['harmonic_T'])))*2*math.pi*R*Asec
                for sig in c['crown_conductivity_S_m']}
        gyro = {f'{w:g}': H*math.radians(w) for w in c['slew_rate_deg_s']}
        rows.append(dict(rim_m_s=v, omega=Om, stress_Pa=rho_eff*v**2, stress_ok=rho_eff*v**2 <= c['cfrp_allowable_Pa']*1.0000001, H_Nms=H,
                         KE_J=KE, KE_t_TNT=KE/TNT_J, gyro_Nm=gyro, eddy_W=eddy, ripple_half_radius=0.5**c['crown_segments'],
                         modulation_Hz=c['crown_segments']*f))
    I2 = abs(A['field']['currents_At'][[x['name'] for x in A['geometry']['coils']].index(c['crown_loop'])])
    B_surf = MU0*I2/(2*math.pi*L2['cryostat']); grad = B_surf/L2['cryostat']
    fiji_pull = {f'{b:g}': b/MU0*grad*2*math.pi*R*Asec for b in s['vertex_fiji']['mu0_Ms_T']}
    return dict(mass_kg_each=mass, pair_kg=2*mass, v_max_m_s=v_max, rows=rows, ripple=rip, B_surface_T=B_surf, gradient_T_m=grad, fiji_pull_N=fiji_pull,
                field_change='none: the crown field is axisymmetric at every instant; rotation adds nothing a static ring does not give',
                fiji='1.6A: a field-following (SEEDED) lattice aligns with the local field whatever the crown angle, so turning it changes nothing; '
                     'ORIENTED magnetization would need coercivity (a second property).',
                heat='axisymmetric engine: the burn load is uniform in azimuth, so turning about the engine axis spreads nothing',
                verdict='REJECT for the drive: no field, confinement or heat benefit; it adds ~{:.0f} t per pair, burst energy, gyroscopic loads and a '
                        'synchronization failure mode. Kept only as a negative result.'.format(2*mass/1e3))


# ---------- C2: Pulsed Lattice Dynamo --------------------------------------------------------------------------------------------------

def _enthalpy_T(tab, h_kJ):
    for (t0, h0), (t1, h1) in zip(tab, tab[1:]):
        if h_kJ <= h1:
            return t0+(t1-t0)*(h_kJ-h0)/(h1-h0)
    return None


def dynamo(s, A, T):
    """C2: rotary storage and induction at the engine root. Startup energy (coil charge + a buffered driver pulse train) by storage type;
    the reductio of buffering sustained power; the driver's recirculating power (it must come from direct conversion of the pulse, not from
    stored energy); the recovery an actively switched pulse coil needs; the HTS dynamo (flux pump) that charges the coils without current
    leads; the persistent-mode internal dump; and a Fiji thermomagnetic cycle (work per cycle, rate, efficiency, the radiator theorem)."""
    c = config(s); F = A['field']; P = A['pulse']; W = F['stored_J']; Pm = A['power']['mission_W']
    start = []; g = ve.config(s)['geometry']; pod_m3 = g['pulse_pods']*g['pulse_pod_size_m'][0]*g['pulse_pod_size_m'][1]*g['pulse_pod_size_m'][2]
    for k in (OPT, NOM, PES):
        Ed = P['yield_J']/c['target_gain'][k]/c['driver_efficiency'][k]; E = c['startup_pulses']*Ed; Pw = c['bootstrap_rate_Hz']*Ed
        mass = {t: max(E/c[f'{t}_J_kg'][k], Pw/c[f'{t}_W_kg'][k]) for t in ('flywheel', 'battery', 'capacitor')}
        start.append(dict(bracket=k, driver_J=Ed, energy_J=E, power_W=Pw, duration_s=c['startup_pulses']/c['bootstrap_rate_Hz'], mass_kg=mass,
                          best=min(mass, key=mass.get), pods_J=pod_m3*c['capacitor_J_m3'][k], pods_hold_pulses=pod_m3*c['capacitor_J_m3'][k]/Ed))
    sustained = {f'{t:g}': Pm*t/c['flywheel_J_kg'][OPT] for t in (1e-3, 1.0, 600.0)}
    recirc = []; conv = vso.config(s)['conversion']; kl = vso.cost(s, vso.config(s)['loss_K']); Be0 = A['radiators']['per_engine_W']
    for k in (OPT, NOM, PES):
        wp = Pm/c['target_gain'][k]/c['driver_efficiency'][k]; heat_ = wp*(1-c['driver_efficiency'][k])+wp*(1-conv[k])/conv[k]
        per_gain = Pm/c['driver_efficiency'][k]*((1-c['driver_efficiency'][k])+(1-conv[k])/conv[k])*kl
        recirc.append(dict(bracket=k, driver_W=wp, share=wp/Pm, heat_W=heat_, reject_W=heat_*kl, ratio_to_drive_share=heat_*kl/Be0,
                           gain_to_fit=per_gain/Be0))
    Be = A['radiators']['per_engine_W']; exch = P['charged_J']*P['rate_mission_Hz']
    switched = dict(exchange_W=exch, required_recovery=1-Be/exch, literature=c['recovery_efficiency'],
                    loss_W={f'{e:g}': (1-e)*exch for e in c['recovery_efficiency']}, ratio_to_drive_share={f'{e:g}': (1-e)*exch/Be for e in c['recovery_efficiency']})
    leads = []
    k20 = vso.cost(s, s['vertex_radiation']['cold_K']); I_kA = F['lead_current_A']/1e3; n = len(F['rows'])
    for w in c['lead_W_per_kA']:
        cold = 2*n*I_kA*w; leads.append(dict(W_per_kA=w, cold_W=cold, radiator_W=cold*k20, share_of_engine=cold*k20/Be))
    charge = []
    for V in c['dynamo_voltage_V']:
        t = max(F['ramp_supply_V']*r['ramp_s']/V for r in F['rows'])
        charge.append(dict(V=V, hours=t/3600.0))
    cold_mass = A['mass']['by_material']['coil']; h = W/cold_mass/1e3
    dump = dict(energy_J=W, cold_mass_kg=cold_mass, kJ_kg=h, final_K=_enthalpy_T(c['steel_enthalpy'], h))
    fi = s['vertex_fiji']; B = F['stop_field_T']; dT = fi['T_saturation_K']-fi['T_release_K']; Th, Tc = fi['T_saturation_K'], fi['T_release_K']
    rate = c['fiji_diffusivity_m2_s']/c['fiji_cycle_thickness_m']**2
    cyc = []
    for k, ms in enumerate(fi['mu0_Ms_T']):
        w = B*ms*(1-1/fi['A_max'])/MU0; q = c['fiji_density_kg_m3']*c['fiji_cp_J_kgK']*dT*(1-c['regeneration'][k])
        cyc.append(dict(mu0_Ms_T=ms, work_J_m3=w, power_W_m3=w*rate, heat_J_m3=q, efficiency=w/(q+w), carnot=1-Tc/Th))
    th = dict(Th_K=Th, radiator_K=A['radiators']['T_K'], cost_at_Th=vso.cost(s, Th),
              statement=f'Fiji works between {Tc:.0f} and {Th:.0f} K, below the {A["radiators"]["T_K"]:.0f} K radiators: its heat must be pumped up '
                        f'(cost {vso.cost(s, Th):.2f} radiator W per W). Converting a share of it to work removes at most that share; it can never '
                        'lower the heat that reaches the radiators below what rejecting at the hot end would need (a heat engine feeding a radiator '
                        'needs area (Th/Tc)^3 >= 1 times the direct rejection).')
    return dict(startup=start, sustained_flywheel_kg=sustained, recirculating=recirc, switched=switched, leads=leads, dynamo_charge=charge, dump=dump,
                homopolar_V=c['rim_speed_m_s'][NOM]*math.sqrt(config(s)['crown_section_m2'])*B,
                fiji_cycle=cyc, fiji_rate_Hz=rate, thermodynamics=th,
                pod_m3=pod_m3,
                verdict='KEEP TWO SMALL PARTS: (1) an ignition bootstrap store (flywheel motor-generator) that charges the pulse pods for the '
                        'first pulses until direct conversion of the burn feeds the driver; (2) leadless persistent coils (HTS dynamo or retractable '
                        'leads). Rejected: storage for sustained or kHz power, a separate coil-charging store (the coils are the 9.7 GJ SMES), '
                        'switched pulse coils (they would have to recover all but 5e-5 of the pulse energy) and the Fiji heat engine.')


# ---------- C3: Variable Geometry Flux Nozzle -----------------------------------------------------------------------------------------

def sky_parts(s, A, k):
    """Sky shares seen from the burn with the nozzle loops and cage deployed by k (closure coils and shield fixed). Loops scale self-similarly
    (position, radius); winding section ~ ampere-turns ~ k^-1/2 so winding minor radius ~ k^-1/4 (cryostat wall kept); cage members sized
    by force ~ k^-1 and length ~ k give sky ~ k^-3/4. Rays the own engine no longer stops hit other hardware at the 1.5 'behind' share."""
    g = A['geometry']; ex = A['exposure']
    def coil_sky(kk):
        out = 0.0
        for c in g['coils']:
            f = kk if c['group'] == 'loop' else 1.0
            a = c['winding']*f**-0.25+(c['cryostat']-c['winding']) if c['group'] == 'loop' else c['cryostat']
            out += vso.band(c['dz_burn']*f, c['r']*f, a)
        return out
    th = math.atan2(g['shield_aft_radius_m'], g['standoff_m']); shield = 0.5*(1-math.cos(th))
    c1 = coil_sky(1.0); cage1 = max(ex['own_engine_first_hit']-c1-shield, 0.0)
    others = ex['hardware_sky_mesh']-ex['own_engine_first_hit']; pb = sum(ex['behind_first'].values())/ex['own_engine_first_hit']
    ck = coil_sky(k); cagek = cage1*k**-0.75; own = ck+shield+cagek; freed = ex['own_engine_first_hit']-own
    hw = own+others+pb*freed
    return dict(k=k, coil=ck, shield=shield, cage=cagek, own=own, others=others, behind_share=pb, hardware=hw, coil_factor=ck/c1,
                hardware_factor=hw/(ex['own_engine_first_hit']+others))


def petals(s, A):
    """C3: deployable petals carry L1-L4 and the cage out by k for the burn and fold back for service. Scaling at the 1.3 stop rule (field
    energy in the loop volume equal to the pulse): B ~ k^-3/2, ampere-turns ~ k^-1/2, loop forces ~ k^-1, stored energy constant, dipole
    ~ k^3/2 (inter-engine pull ~ k^3), fluence per area at the loops ~ k^-2, conductor mass ~ k^1/2; hinges per kg deployed."""
    c = config(s); g = A['geometry']; M = A['mass']; cat = M['by_category']
    kmax = (g['adjacent_m']-g['maintenance_m'])/2/g['max_radius_m']
    loops = [x for x in g['coils'] if x['group'] == 'loop']; I = A['field']['currents_At']; names = [x['name'] for x in g['coils']]
    wsum = sum(abs(I[i])*x['r'] for i, x in enumerate(g['coils'])); wloop = sum(abs(I[names.index(x['name'])])*x['r'] for x in loops)
    coil_loop_kg = M['by_material']['coil']*wloop/wsum; deployed = cat['MAGNETIC_NOZZLE']+cat['STRUCTURE']
    rows = []
    for k in c['deploy_k']:
        sp = sky_parts(s, A, k)
        dm_ = [coil_loop_kg*(k**0.5-1)+(h*deployed if k > 1 else 0.0) for h in c['hinge_share']]
        rows.append(dict(sp, envelope_m=g['max_radius_m']*k, fits=k <= kmax+1e-9, cluster_outer_m=g['cluster_radius_m']+g['max_radius_m']*k,
                         stop_field_factor=k**-1.5, current_factor=k**-0.5, loop_force_factor=1/k, stored_factor=1.0, inter_engine_factor=k**3,
                         inter_engine_N=A['loads']['inter_engine_N']*k**3, fluence_factor=k**-2, added_kg=dm_,
                         added_four_kg=[4*x for x in dm_], margin_ok=[4*x <= M['margin_kg'] for x in dm_],
                         field_per_mass=1.0/(1+dm_[NOM]/(deployed+M['by_material']['coil']))))
    best = max((r for r in rows if r['fits']), key=lambda r: r['k'])
    return dict(k_max=kmax, rows=rows, best=best, deployed_kg=deployed, coil_loop_kg=coil_loop_kg, deploy_time_s=c['deploy_time_s'],
                vectoring='cluster differential throttle already gives 17.4 MN m per engine (LC-06); petal tilt is not needed for steering',
                evidence='SCALING_ESTIMATE: self-similar field scaling at the 1.3 stop rule, not a field or plasma solution; the capture and '
                         'leakage of a deployed nozzle are assumed unchanged (self-similar ideal MHD) and stay OPEN',
                verdict=f'KEEP as the geometry lever: deployed to k {best["k"]:.2f} (the cluster spacing allows {kmax:.2f}) the coils take '
                        f'{best["coil_factor"]:.0%} of their sky and {best["fluence_factor"]:.0%} of their fluence; field energy unchanged, loop '
                        f'forces /{1/best["loop_force_factor"]:.2f}, inter-engine pull x{best["inter_engine_factor"]:.1f}; +{best["added_kg"][NOM]/1e3:.0f} t '
                        'per engine (hinges, longer conductor). Static during the burn.')


# ---------- C4: Armour Tread ----------------------------------------------------------------------------------------------------------

def tread(s, A):
    """C4 (added): armour tiles circulate poloidally round the burn-facing cryostats like a track: each tile crosses the lit half, then
    the shadow half where it radiates and can be exchanged. Peak flux on a cosine-lit circumference falls by pi; the shadow half radiates
    to space; the loop's net angular momentum is zero (local poloidal moments cancel round the ring)."""
    c = config(s); g = A['geometry']; vg = ve.config(s)['geometry']; rows = []; area = 0.0; mass = 0.0
    for name in c['tread_coils']:
        x = next(q for q in g['coils'] if q['name'] == name); a = x['cryostat']+vg['armour_offset_m']
        Aa = 4*math.pi**2*x['r']*a; area += Aa; mass += Aa*c['tread_tile_m']*c['tread_tile_density_kg_m3']*(1+c['tread_overhead'])
        rows.append(dict(name=name, area_m2=Aa, period_s=2*math.pi*a/c['tread_speed_m_s']))
    static_kg = 0.5*area*c['tread_tile_m']*c['tread_tile_density_kg_m3']
    sinks = [dict(bracket=k, T_K=c['tread_T_K'][k], emissivity=c['tread_emissivity'][k],
                  W=0.5*area*c['tread_emissivity'][k]*SIGMA_SB*c['tread_T_K'][k]**4*c['tread_space_view']) for k in (OPT, NOM, PES)]
    vtx = next(r['compact'] for r in ve.calculations(s) if r['id'] == 'C-05')
    return dict(coils=rows, area_m2=area, mass_kg=mass, static_shoe_kg=static_kg, added_kg=mass-static_kg, peak_factor=1/math.pi,
                vtx_s3_static=vtx, vtx_s3_tread=vtx/math.pi, sinks=sinks, per_engine_share=[x['W']/A['radiators']['per_engine_W'] for x in sinks],
                angular_momentum='zero by symmetry (poloidal circulation; the local moments point along the ring and cancel)',
                verdict='KEEP: a real, bounded gain (peak flux /pi, renewable surface, a shadow-side radiating face); total heat is unchanged '
                        'and the added sink is a few per cent of the drive share at most.')


# ---------- 6: radiation approaches ---------------------------------------------------------------------------------------------------

def radiation(s, A, PT):
    """The five approaches of brief section 6, each with its number: (1) avoidance (C3 sky), (2) propellant as absorber (the column the
    per-pulse propellant can make, against the column photons and neutrons need), (3) cold hardware farther away (fluence and REBCO life),
    (4) plasma energy use (charged leakage, the dominant best-case channel) against the magnetic-shielding precedent, (5) the source."""
    c = config(s); P = A['pulse']; mdot = A['power']['mdot_four_kg_s']/4; mp = mdot/P['rate_mission_Hz']
    kT = NA*1e3/1.00794*SIGMA_T      # Thomson opacity of hydrogen, m2/kg
    kn = NA*1e3/1.00794*c['np_barn']*1e-28
    ph = []
    for E in c['photon_keV']:
        tau = math.sqrt(511.0/E); col = tau/kT
        ph.append(dict(keV=E, tau_needed=tau, column_kg_m2=col, radius_with_pulse_mass_m=math.sqrt(mp/(4*math.pi*col)),
                       mass_at_1m_kg=4*math.pi*col, mass_flow_at_1m_kg_s=4*math.pi*col*P['rate_mission_Hz'],
                       ve_factor_at_1m=math.sqrt(mp/(mp+4*math.pi*col))))
    neu = dict(opacity_m2_kg=kn, radius_tau1_m=math.sqrt(mp*kn/(4*math.pi)), note='a few collisions with protons are needed to absorb a neutron')
    best = PT['best']; SO = _j(vso.EVIDENCE_PATH); th = SO['feasibility']['thresholds']; allow = SO['interface']['allowable']
    need = SO['interface']['best_computed_leak']/max(x['mission']['allowed_share'] for x in allow)
    return dict(
        avoidance=dict(coil_factor=best['coil_factor'], hardware_factor=best['hardware_factor'], k=best['k']),
        propellant=dict(pulse_mass_kg=mp, photons=ph, neutrons=neu, trapping_1_6b='1.6B: dense-target Compton trapping lowers photons at most 3.3x',
                        verdict='The propellant of one pulse forms an absorbing layer only within millimetres of the burn, which is the target '
                                'itself (already in the 1.6B source). A shell at 1 m would add hundreds of kg per pulse and cut the exhaust '
                                'speed by orders of magnitude; absorbed energy also leaves isotropically, not as thrust.'),
        cold=dict(fluence_factor=best['fluence_factor'], rebco_1_6b_s=1.0, rebco_deployed_s=1.0/best['fluence_factor'],
                  note='1.6B: unshielded REBCO lasts ~1 s at mission power; deployment buys a factor ~2, shields still 43-45 kt'),
        plasma=dict(leak_computed=SO['interface']['best_computed_leak'], leak_allowed=max(x['mission']['allowed_share'] for x in allow),
                    reduction_needed=need, precedent=c['shielding_precedent'], precedent_gap=need/c['shielding_precedent'][OPT],
                    note='Charged leakage (1.4 ledger) dominates the best 1.6B budget. Motion cannot act in the ~100 ns transit; magnetic '
                         'shielding of walls (Hall thrusters) reduced erosion by 2-3 orders in a much gentler plasma.'),
        source=dict(photon=th['photon'], neutron=th['neutron'], note='unchanged: no mechanism here changes the burn physics (1.6B); a quieter '
                                                                       'source is a separate speculative principle (SP-17B)'))


# ---------- 7, 13: mission-point budget ----------------------------------------------------------------------------------------------

def _row(s, C, cid, br):
    r = C[cid]['brackets'][br]['best']; k = vso.BRACKETS.index(br)
    o = vso.opts(s, next(x for x in vso.config(s)['cases'] if x['id'] == cid), k); U = vso.useful(s, r, o, k)
    return r, U, k


def heat(s, C, cid, br, shield, f_hot=1.0, f_coil=1.0, leak=None, sink=0.0, src=1.0):
    """One engine at the mission point: the 1.6B budget (vso.budget, unchanged) with the photon/neutron deposition scaled by the mechanism's
    hardware and coil sky factors (shielded: everything sits behind the liner, so the hardware factor), leakage at its 1.4 share or `leak`,
    an added radiating sink, and `src` scaling the photon/neutron output (a requirement screen, not an energy-consistent source case)."""
    r, U, k = _row(s, C, cid, br); A = vso.allocation(s); Pf = op.burn(s)['peak_jet_power_W']/4/U['useful_share']
    B = vso.budget(s, r, U, Pf, k, shield, leak); lo = B['brackets']['low']
    cold = 0.0 if shield else lo['cryo_W']+lo['refrigeration_W']; hot = lo['photon_neutron_W']-cold
    pn = src*(hot*f_hot+cold*f_coil); rej = pn+lo['leak_reject_W']+lo['loss_reject_W']; cap = A['per_engine_W']+sink
    return dict(case=cid, bracket=br, shield=shield, Pf_W=Pf, photon_neutron_W=pn, leak_W=lo['leak_reject_W'], loss_W=lo['loss_reject_W'],
                reject_W=rej, capacity_W=cap, ratio=rej/cap, energy_error=B['energy_error'])


def budget(s, A, PT, TR, DY):
    """Mission-point ledger for the static baseline and each candidate on the best defensible 1.6B sources (S1 optimistic and nominal,
    with and without the 1.6 liner), the hybrid, and what still has to be supplied: the leakage that would close with the source as computed,
    and the source factor that would close with perfect capture."""
    C = vso.cases(s); best = PT['best']; sink = TR['sinks'][NOM]['W']; lead = DY['leads'][NOM]['radiator_W']
    cands = dict(static=dict(), C1=dict(), C2=dict(sink=lead), C3=dict(f_hot=best['hardware_factor'], f_coil=best['coil_factor']),
                 C4=dict(sink=sink), HYBRID=dict(f_hot=best['hardware_factor'], f_coil=best['coil_factor'], sink=sink+lead))
    rows = []
    for cid in ('S1',):
        for br in ('optimistic', 'nominal'):
            for sh in (False, True):
                base = heat(s, C, cid, br, sh)
                for name, kw in cands.items():
                    h = heat(s, C, cid, br, sh, **kw); rows.append(dict(h, candidate=name, improvement=base['ratio']/h['ratio']))
    ref = min((r for r in rows if r['candidate'] == 'static'), key=lambda r: r['ratio'])
    hy = next(r for r in rows if r['candidate'] == 'HYBRID' and (r['bracket'], r['shield']) == (ref['bracket'], ref['shield']))
    kw = cands['HYBRID']; args = (s, C, ref['case'], ref['bracket'], ref['shield'])
    h0 = heat(*args, leak=0.0, **kw); h1 = heat(*args, leak=1e-3, **kw)
    per = (h1['reject_W']-h0['reject_W'])/1e-3; room = h0['capacity_W']-h0['reject_W']
    leak_req = room/per if room > 0 else None
    src_req = (h0['capacity_W']-h0['loss_W'])/h0['photon_neutron_W'] if h0['photon_neutron_W'] > 0 else None
    SO = _j(vso.EVIDENCE_PATH); match = next(r for r in SO['combined']['rows'] if r.get('point') == 'mission' and r['case'] == ref['case']
                                                 and r['bracket'] == ref['bracket'] and r['shield'] == ref['shield'])
    rc = DY['recirculating'][OPT]
    driver = dict(reject_W=rc['reject_W'], ratio=rc['ratio_to_drive_share'], hybrid_with_driver=hy['ratio']+rc['reject_W']/hy['capacity_W'],
                  gain_to_fit=rc['gain_to_fit'], note='Not in the 1.6B ledger: the driver of an inertial burn draws Pf/(G eta) and its losses '
                  'and the conversion losses that feed it are rejected at loss_K. Shown at the optimistic bracket (G 100, eta 0.5, conversion 0.9).')
    return dict(rows=rows, reference=ref, hybrid=hy, driver=driver, reproduces_1_6b=abs(ref['ratio']/match['ratio']-1) < 1e-4, ratio_1_6b=match['ratio'],
                requirement=dict(leak_to_close=leak_req, leak_computed=SO['interface']['best_computed_leak'],
                                 leak_factor=(SO['interface']['best_computed_leak']/leak_req) if leak_req else None,
                                 perfect_capture_ratio=h0['ratio'], source_factor_to_close=src_req,
                                 source_reduction=(1/src_req) if src_req else None),
                note='Ratios are radiator watts over the drive share per engine (all four engines alike). Only the deposition geometry, the '
                     'added sinks and the leakage term change; the source, jet, thrust and exhaust speed are the 1.6B mission point.')


def mission(s, A, CR, PT, TR, DY):
    """Brief 7F: the mission is held (thrust, exhaust speed, burn time unchanged); each candidate's added mass against the 174 t departure
    margin, and the acceleration it costs at the canon thrust."""
    M = A['mass']; b = op.burn(s); m0 = M['departure_kg']; rows = []
    boot = DY['startup'][NOM]['mass_kg']['flywheel']/4      # one bootstrap store shared by the cluster (one engine ignites at a time)
    added = dict(static=0.0, C1=CR['pair_kg'], C2=boot, C3=PT['best']['added_kg'][NOM], C4=TR['added_kg'])
    added['HYBRID'] = added['C2']+added['C3']+added['C4']
    for k, v in added.items():
        dm4 = 4*v
        rows.append(dict(candidate=k, added_engine_kg=v, added_four_kg=dm4, engine_share=v/M['engine_kg'], margin_kg=M['margin_kg'],
                         within_margin=dm4 <= M['margin_kg'], accel_factor=m0/(m0+dm4), thrust_N=b['peak_thrust_N'], ve_m_s=b['exhaust_velocity_m_s']))
    return dict(rows=rows, note='Thrust, exhaust speed and burn time stay at the B01 point; added mass lowers the '
                'acceleration in proportion (power-limited burn) and must fit the departure margin, or the tanks grow.')


# ---------- 9, 13: comparison ------------------------------------------------------------------------------------------------------

def compare(s, A, T, CR, DY, PT, TR, BU, MI):
    """Section 13 acceptance table per candidate against the static engine (numbers where computed, a class where not)."""
    hy = {r['candidate']: r for r in BU['rows'] if (r['bracket'], r['shield']) == (BU['reference']['bracket'], BU['reference']['shield'])}
    mm = {r['candidate']: r for r in MI['rows']}
    def row(name, title, mass, eff, rad, heat_, radi, mag, prop, cx, vis, keep):
        return dict(id=name, title=title, mass=mass, thrust_efficiency=eff, radiation=rad, heat=heat_, radiators=radi, magnetic=mag,
                    propulsion=prop, complexity=cx, visual=vis, keep=keep, ratio=hy[name]['ratio'], improvement=hy[name]['improvement'],
                    added_four_kg=mm[name]['added_four_kg'], within_margin=mm[name]['within_margin'])
    b = PT['best']
    return [
        row('static', 'Static Compact Vertex (M0-NOMINAL, 1.6B best source)', 'reference', 'reference', 'reference', 'reference', 'reference', 'reference',
            'mission held, heat fails', 'reference', 'static open cage', 'BASELINE'),
        row('C1', 'Rotary Field Crown', f'+{CR["pair_kg"]/1e3:.0f} t per engine', 'none (field unchanged)', 'none', 'none (+eddy)', 'none',
            'worse (mass, no field)', 'unchanged', '+4 failure modes, sync control', 'strong', 'REJECT'),
        row('C2', 'Pulsed Lattice Dynamo', f'bootstrap store {4*mm["C2"]["added_engine_kg"]/1e3:.0f} t for the cluster', 'none (driver power must come from direct conversion)', 'none',
            f'-{DY["leads"][NOM]["radiator_W"]/1e6:.0f} MW lead heat', 'negligible', 'same', 'unchanged', 'charging slower, leads removed',
            'spin-up at start, then still', 'KEEP DYNAMO ONLY'),
        row('C3', 'Variable Geometry Flux Nozzle (deployed petals)', f'+{b["added_kg"][NOM]/1e3:.0f} t per engine', 'unchanged (capture OPEN)',
            f'coil sky x{b["coil_factor"]:.2f}, fluence x{b["fluence_factor"]:.2f}', f'photon/neutron deposition x{b["hardware_factor"]:.2f}', 'small',
            f'field energy same, forces /{1/b["loop_force_factor"]:.2f}, mass +', 'unchanged', 'hinges, latches, deploy sequence',
            'engine opens before ignition', 'KEEP'),
        row('C4', 'Armour Tread', f'+{TR["added_kg"]/1e3:.0f} t per engine', 'unchanged', 'none', f'peak flux /pi (VTX-S3 {TR["vtx_s3_static"]:.0f}x -> {TR["vtx_s3_tread"]:.1f}x)',
            f'+{TR["sinks"][NOM]["W"]/1e6:.0f} MW sink', 'same', 'unchanged', 'track drive, tile exchange', 'treads circulate while firing', 'KEEP'),
        row('HYBRID', 'Bloom nozzle: C3 + C4 + HTS dynamo, electronic trim', 'C3 + C4', 'unchanged', 'as C3', 'as C3 and C4', 'as C3 and C4',
            'as C3', 'unchanged', 'sum of the kept parts', 'full ignition sequence', 'RECOMMENDED (research)'),
    ]


# ---------- 10, 12E: sequence, failures, integration --------------------------------------------------------------------------------

STATE_NAMES = ('DORMANT', 'MECHANICAL_PREP', 'FIELD_INIT', 'FIJI_ACTIVATION', 'IGNITION', 'STABLE_THRUST', 'MODULATION', 'SHUTDOWN', 'FAILURE')


def sequence(s, A, DY, PT, TR):
    """The operating sequence of the recommended hybrid as control values per state (0..1 unless stated) and the duration physics sets.
    Each value is something the engine model already has or the hybrid adds: bloom (petal deployment), tread (speed), dynamo (rotor speed),
    field (coil current share), fiji (lattice temperature K), burn (fusion power share), thrust (display throttle), trim (electronic coils)."""
    fi = A['fiji']['T_K']; ch = DY['dynamo_charge'][NOM]['hours']*3600; ramp = max(r['ramp_s'] for r in A['field']['rows'])
    S = [('DORMANT', 'Fusion off; petals folded and latched, treads parked, dynamos still, coils at zero current.', None,
          dict(bloom=0, tread=0, dynamo=0, field=0, fiji=300, burn=0, thrust=0, trim=0)),
         ('MECHANICAL_PREP', 'Latches release, petals swing out to the deployed radius, treads start; the dynamo rotors spin up.', PT['deploy_time_s'],
          dict(bloom=1, tread=0.2, dynamo=1, field=0, fiji=300, burn=0, thrust=0, trim=0)),
         ('FIELD_INIT', 'The dynamos pump current into the coils (no leads) until the stop field stands; persistent switches close; dynamos stop.',
          ch, dict(bloom=1, tread=0.2, dynamo=0, field=1, fiji=300, burn=0, thrust=0, trim=0.2)),
         ('FIJI_ACTIVATION', f'Lattice heated through activation ({fi["T_activation_K"]:.0f} K) to its operating point ({fi["T_operating_K"]:.0f} K); its response rises.',
          3600.0, dict(bloom=1, tread=0.5, dynamo=0, field=1, fiji=fi['T_operating_K'], burn=0, thrust=0, trim=0.5)),
         ('IGNITION', 'Driver pulse train; first burns; the treads reach running speed as the lit faces heat.', 60.0,
          dict(bloom=1, tread=1, dynamo=0, field=1, fiji=fi['T_operating_K'], burn=0.1, thrust=0.1, trim=1)),
         ('STABLE_THRUST', 'Petals locked, coils persistent, treads circulating, trim coils holding the plume; no other motion.', None,
          dict(bloom=1, tread=1, dynamo=0, field=1, fiji=fi['T_operating_K'], burn=1, thrust=1, trim=1)),
         ('MODULATION', 'Throttle changes pulse rate; tread speed follows the lit heat; trim coils steer; diagonal pairs balance torque.', None,
          dict(bloom=1, tread=0.7, dynamo=0, field=1, fiji=fi['T_operating_K'], burn=0.6, thrust=0.6, trim=1)),
         ('SHUTDOWN', 'Pulses stop; treads run on while the faces cool; Fiji falls below release; coils ramp down by the dynamos run backwards or '
                      'stay persistent; petals fold after cool-down.', ramp, dict(bloom=0.5, tread=0.3, dynamo=0.5, field=0.5, fiji=fi['T_release_K'], burn=0, thrust=0, trim=0)),
         ('FAILURE', 'See the failure table: the visible cue is the mechanism that failed (a stopped tread glows, a petal off its latch, a quench vent).', None,
          dict(bloom=1, tread=0, dynamo=0, field=0, fiji=fi['T_quench_K'], burn=0, thrust=0, trim=0))]
    return [dict(state=n, description=d, duration_s=t, values=v) for n, d, t, v in S]


def failures(s, A, CR, DY, PT, TR):
    """Failure modes that follow from the mechanisms, with the energy involved and the visible consequence."""
    W = A['field']['stored_J']; ke = max(r['KE_J'] for r in CR['rows'] if r['stress_ok']); Pm = A['power']['mission_W']
    fluxlit = Pm*0.10*0.05/(TR['area_m2']/2)      # nominal photon share x deposited share on the lit tread half (screening)
    tile = config(s)['tread_tile_m']*config(s)['tread_tile_density_kg_m3']*130.0
    return [
        dict(id='F-SYNC', mechanism='C1 crowns (rejected)', cause='counter-rotating crowns lose synchronization', energy_J=ke,
             consequence=f'net angular momentum appears; gyroscopic torque on the cradle; {ke/TNT_J:.1f} t TNT of kinetic energy per crown', visible='crown speed mismatch, cradle shake'),
        dict(id='F-OVERSPEED', mechanism='C1 crowns (rejected)', cause='drive runaway beyond the band limit', energy_J=ke, consequence='rim burst: fragments at hundreds of m/s into the cage and the neighbours', visible='fragment cloud'),
        dict(id='F-PETAL', mechanism='C3 petals', cause='a petal fails to latch or drifts', energy_J=None,
             consequence='asymmetric loops: side force and a tilted plume; inter-engine force changes; burn inhibited until latched', visible='one petal off its stop; plume bends'),
        dict(id='F-TREAD', mechanism='C4 treads', cause='a tread stops under the burn', energy_J=None,
             consequence=f'the lit tiles take the full face flux (~{fluxlit:.1e} W/m2 at mission power, nominal source): they reach Fiji/armour limits in '
                         f'~{tile*300/fluxlit*1e3:.2f} ms; the burn must trip', visible='a stationary glowing band on one coil'),
        dict(id='F-QUENCH', mechanism='coils (all)', cause='superconductor quench (neutron damage, heat leak, flux jump)', energy_J=W,
             consequence=f'{W/1e9:.1f} GJ per engine dumped into the cold mass (persistent mode: final ~{DY["dump"]["final_K"]:.0f} K) or a resistor; '
                         'unbalanced forces on the neighbours (one engine off: LC-06)', visible='cryostat vent plume, frost, field-off indicator'),
        dict(id='F-DYNAMO', mechanism='C2 dynamo', cause='flux-pump rotor stall or a persistent switch opening', energy_J=None,
             consequence='current decays slowly (hours); the burn is throttled before the stop field is lost', visible='rotor stopped, current falling'),
        dict(id='F-OVERLOAD', mechanism='coils (all)', cause='flux compression beyond the coil rating (max swing x1.86, 1.3)', energy_J=None,
             consequence='case stress beyond allowable; quench or structural yield', visible='trip, quench vent'),
        dict(id='F-LEAK', mechanism='nozzle (all)', cause='plasma leakage above the computed 18 % (detachment failure)', energy_J=None,
             consequence='hardware heat beyond any radiator; armour erosion; trip', visible='plume touching the cage, armour glow'),
        dict(id='F-FIJI', mechanism='Fiji lattice', cause='lattice above degrade/quench (1300/1400 K)', energy_J=None,
             consequence='its response collapses (bounded property); the trim coils take over or the burn trips', visible='lattice colour shift'),
        dict(id='F-TRANSFER', mechanism='dynamo / trim', cause='uncontrolled energy transfer between coil circuits (switch fault)', energy_J=W,
             consequence='coil currents redistribute: force imbalance, possible quench', visible='current indicators diverge')]


def integration(s, A, PT, TR):
    """Phase E plan (not implemented): assemblies, motion axes, states, materials, colours, hierarchy, drivers, control parameters and the
    render cost. Prototype work would live in work/<task>/ as WORK_VTX17 collections in a review file (AGENTS.md)."""
    b = PT['best']; tiles = sum(int(2*math.pi*(next(q for q in A['geometry']['coils'] if q['name'] == n)['cryostat']+0.38)/0.5)*48
                                for n in config(s)['tread_coils'])
    return dict(
        assemblies=[
            dict(id='VTX17_PETAL', parts='eight petals: L1-L4 segments and their cage longeron pairs on a root hinge at the thrust collar',
                 motion=f'rotation about a tangential hinge axis at the collar; scale 1 -> {b["k"]:.2f} radius', axis='tangential, at the collar ring',
                 material='MAT-TI6AL4V hinge, MAT-CFRP actuator housings, existing coil and cryostat materials', colour='drive red (system) with a grey hinge'),
            dict(id='VTX17_TREAD', parts='tile track round C2, L1 and L2 cryostats, drive sprockets on the shadow side, one tile exchange port',
                 motion='poloidal circulation round each cryostat minor axis', axis='local minor-circle tangent',
                 material='MAT-W-FIJI01 / MAT-W tiles on a MAT-SICSIC track', colour='armour dark grey, lit-face glow by temperature'),
            dict(id='VTX17_DYNAMO', parts='one HTS dynamo per coil at the current-lead turret position (6 per engine)', motion='rotor spin about its own axis, stopped in persistent mode',
                 axis='turret axis', material='MAT-REBCO-APC01 stator tape, magnet rotor', colour='cryogenic blue-grey'),
            dict(id='VTX17_TRIM', parts='normal-conducting trim coils at L3/L4 (electronic, no motion)', motion='none (current only)', axis='-',
                 material='MAT-CU-OF', colour='copper')],
        hierarchy=['GEN_WF_VERTEX_ENGINE (unchanged generated engine)', 'WORK_VTX17 (review file only, pink)',
                   'WORK_VTX17/PETALS', 'WORK_VTX17/TREADS', 'WORK_VTX17/DYNAMOS', 'WORK_VTX17/TRIM', 'WORK_VTX17/CAMERAS'],
        drivers=[dict(variable='bloom', property='vtx_bloom', drives='petal hinge angle (k = 1 + (k_max-1) bloom)'),
                 dict(variable='tread', property='vtx_tread_speed', drives='tile offset along the track (instanced tiles, one mesh per tread)'),
                 dict(variable='dynamo', property='vtx_dynamo_speed', drives='rotor angle'),
                 dict(variable='l', property='lattice_activation (existing)', drives='Fiji lattice emission and colour from fiji temperature'),
                 dict(variable='n', property='nozzle_field_strength (existing)', drives='field envelope and coil indicator'),
                 dict(variable='t', property='thrust_level (existing)', drives='plume length (existing) and tread speed share')],
        control=['bloom 0..1', 'tread speed 0..1', 'dynamo speed -1..1', 'coil current share 0..1', 'fiji temperature K', 'burn share 0..1', 'thrust 0..1', 'trim 0..1'],
        render=dict(objects_per_engine=8+3+6+2, tread_tiles_per_engine=tiles, tiles_instanced=True, draw_calls_added_per_engine=8+3+6+2,
                    note='Petals are the existing loop/cage meshes split in eight (no new triangles); tiles are one instanced mesh per tread; '
                         'animation is transforms only (no deformation), so the browser cost is draw calls, not geometry. Measure in Phase F.'),
        phase_f='Needs separate approval: WORK_VTX17 review file, then a state-driven viewer demo on shared parameters; no change to GEN or canon.')


# ---------- verdict ------------------------------------------------------------------------------------------------------------

def verdict(s, A, T, BU, PT, TR):
    c = config(s); hy = BU['hybrid']; imp = hy['improvement']
    code = 'A' if hy['ratio'] <= 1 else 'B' if imp >= 10 else 'C' if imp > 1.01 else 'D'
    rq = BU['requirement']
    sp = [dict(id='SP-17A', name='Flux-locked capture', supplies=f'charged leakage at most {rq["leak_to_close"]:.1e} of the exhaust' if rq['leak_to_close'] else
               'charged leakage near zero (the source alone already exceeds the radiators)', factor=rq['leak_factor'],
               precedent='magnetic shielding of Hall-thruster walls (2-3 orders of erosion reduction)', status='PROPOSED_FOR_AUTHOR_APPROVAL',
               note='Moving parts cannot do this (100 ns transit). It would be a property of the field topology, not of motion.'),
          dict(id='SP-17B', name='Radiation-quiet burn', supplies=f'photon and neutron output x{rq["source_factor_to_close"]:.1e} of the best computed (1.6B S1)'
               if rq['source_factor_to_close'] else '-', factor=rq['source_reduction'], precedent='none: bremsstrahlung and D-D neutrons are set by the plasma',
               status='PROPOSED_FOR_AUTHOR_APPROVAL', note='Needed even with perfect capture; a fiction about the source, not the nozzle.'),
          dict(id='SP-17D', name='High-gain ignition (extends VTX-S1)', supplies=f'target gain of at least {BU["driver"]["gain_to_fit"]:,.0f} with a 50 % driver',
               factor=None, precedent='laboratory ignition reached gain ~2-4 (NIF 2022-2025); IFE designs 30-150', status='PROPOSED_FOR_AUTHOR_APPROVAL',
               note='The driver recirculation is a new channel this audit found outside the 1.6B ledger.'),
          dict(id='SP-17C', name='Fiji coercive orientation (the 1.6A second property)', supplies='ORIENTED lattice up to +44 % of the stop field (1.6A FG-2)',
               factor=None, precedent='none at 1000 K', status='PROPOSED_FOR_AUTHOR_APPROVAL', note='Helps magnetics only; no effect on the heat gap.')]
    return dict(outcome=code, label=OUTCOMES[code], improvement=imp, hybrid_ratio=hy['ratio'], static_ratio=BU['reference']['ratio'], speculative=sp,
                statement=f'The recommended hybrid lowers the mission-point radiator ratio from {BU["reference"]["ratio"]:,.0f} to {hy["ratio"]:,.0f} '
                          f'(x{imp:.2f}); counting the driver recirculation this audit adds, {BU["driver"]["hybrid_with_driver"]:,.0f}. Mechanical motion acts '
                          'on seconds to minutes; the gap is set by a ~100 ns plasma capture (leakage), by the source and by the driver gain, so no '
                          'moving assembly can close it. Closing needs SP-17A, SP-17B and SP-17D together, each beyond any precedent.',
                matches_config=code == c['outcome'])


def answers(A, T, CR, DY, PT, TR, RA, BU, V):
    return [
        dict(q='Does rotation make a useful field?', a='No. An axisymmetric crown turned about its axis makes the same field; segments add a '
                                                         f'{CR["rows"][1]["ripple_half_radius"]:.1e} ripple at half radius at ~{CR["rows"][1]["modulation_Hz"]:.0f} Hz.'),
        dict(q='Is motion fast enough for the plasma?', a=f'No: {T["verdict"]["motion_over_pulse"]:.1e} of the pulse rate; rotating-field current drive needs '
                                                          f'{T["rmf"]["gap"]:.0e} times faster rotation than any rim.'),
        dict(q='Can flywheels power the drive?', a=f'No: one second of mission power needs {DY["sustained_flywheel_kg"]["1"]/1e6:,.0f} kt of flywheel. A '
                                                     f'flywheel can bootstrap ignition (10 pulses at 1 Hz: {DY["startup"][NOM]["mass_kg"]["flywheel"]/1e3:.0f} t nominal); '
                                                     'the coils themselves already store their 9.7 GJ.'),
        dict(q='Does a Fiji thermomagnetic cycle help?', a=f'No: about {DY["fiji_cycle"][0]["efficiency"]:.1%} of the heat at best, and Fiji works below the radiator temperature.'),
        dict(q='What does help?', a=f'Deployed petals (coil sky x{PT["best"]["coil_factor"]:.2f}, fluence x{PT["best"]["fluence_factor"]:.2f}), treads (peak flux /pi) '
                                     'and leadless HTS dynamos: real but bounded.'),
        dict(q='Does the radiator ratio move?', a=f'Barely: x{V["improvement"]:.2f}, because charged leakage dominates the best budget.'),
        dict(q='What must the fiction supply?', a=f'Near-perfect capture (SP-17A; even zero leakage leaves {BU["requirement"]["perfect_capture_ratio"]:.0f}x), a '
                                                    f'{BU["requirement"]["source_reduction"]:,.0f}x quieter source (SP-17B) and a target gain near '
                                                    f'{BU["driver"]["gain_to_fit"]:,.0f} (SP-17D), all at once.'),
        dict(q='Is the mass better?', a='No: every kept part adds mass; the static engine is already outside the canon mass budget.')]


# ---------- report ---------------------------------------------------------------------------------------------------------------

def input_hash(s):
    blob = json.dumps([s['vertex_dynamic'], s['vertex_source'], s['vertex_fiji'], s['vertex_engine'], s['physics']['operating_point'],
                       s['radiators']['temperature']], sort_keys=True, default=str)
    here = Path(__file__).resolve().parent
    src = b''.join((here/f).read_bytes() for f in ('vertex_dynamic.py', 'vertex_source.py', 'vertex_engine.py', 'operating_point.py'))
    return hashlib.sha256(blob.encode()+src+vso.EVIDENCE_PATH.read_bytes()+MAGNET_PATH.read_bytes()+STRUCTURE_PATH.read_bytes()).hexdigest()[:16]


def report(s):
    t0 = time.time(); c = config(s)
    A = audit(s); T = timescales(s, A); CR = crown(s, A, T); DY = dynamo(s, A, T); PT = petals(s, A); TR = tread(s, A)
    RA = radiation(s, A, PT); BU = budget(s, A, PT, TR, DY); MI = mission(s, A, CR, PT, TR, DY)
    CO = compare(s, A, T, CR, DY, PT, TR, BU, MI); SE = sequence(s, A, DY, PT, TR); FL = failures(s, A, CR, DY, PT, TR)
    IN = integration(s, A, PT, TR); V = verdict(s, A, T, BU, PT, TR)
    return dict(version=c['version'], input_hash=input_hash(s), evidence=c['evidence'], baseline_commit=c['baseline_commit'], audit=A,
                timescales=T, crown=CR, dynamo=DY, petals=PT, tread=TR, radiation=RA, budget=BU, mission=MI, compare=CO, sequence=SE,
                failures=FL, integration=IN, verdict=V, answers=answers(A, T, CR, DY, PT, TR, RA, BU, V), outcome=V['outcome'],
                cost=dict(seconds=time.time()-t0))


def _round(x):
    if isinstance(x, float):
        return float(f'{x:.6g}') if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v) for v in x]
    return x


def evidence(s, path=EVIDENCE_PATH):
    R = report(s)
    path.write_text(json.dumps(_round(R), indent=None, separators=(',', ':'))+'\n')
    return R


if __name__ == '__main__':
    import spec
    S = spec.load(ROOT)[0]
    R = evidence(S) if '--evidence' in sys.argv else report(S)
    print(R['timescales']['verdict']['statement'])
    for r in R['compare']:
        print(f"{r['id']:7} {r['keep']:22} ratio {r['ratio']:>10,.0f}  x{r['improvement']:.3f}  +{r['added_four_kg']/1e3:.0f} t  {r['title']}")
    print(R['budget']['requirement'])
    print(R['verdict']['statement'])
    print(f"{R['cost']['seconds']:.1f} s")
