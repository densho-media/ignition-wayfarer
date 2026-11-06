"""FDP-1 structure: the thrust path (loops -> nozzle struts -> shield frame -> equipment module -> thrust ring -> spine), the driver
galleries and the radiator wing spars. Struts are thin-walled tubes sized by stress or Euler buckling, whichever governs, with a safety
factor. The magnetic forces between coaxial loops (order W/spacing) belong to the nozzle's virial structure mass, not to these struts."""
import math

from .config import v

G0 = 9.80665


def tube(load_N, length_m, c):
    sf = v(c['safety_factor']); sig = v(c['sigma_allow_Pa'])/sf; E = v(c['modulus_Pa']); k = v(c['tube_t_over_r'])
    P = load_N*sf
    A_s = load_N/sig
    r = (P*length_m**2/(math.pi**3*E*k))**0.25           # Euler: P = pi^2 E (pi k r^4) / L^2
    A_b = 2*math.pi*k*r*r
    A = max(A_s, A_b); r = max(r, math.sqrt(A/(2*math.pi*k)), 0.04)
    return {'area_m2': A, 'radius_m': r, 'mass_kg': v(c['density_kg_m3'])*A*length_m, 'governs': 'buckling' if A_b >= A_s else 'stress'}


def solve(cfg, r, rec, lay, noz, shield, wings, galleries):
    c = cfg['structure']; F = r['thrust_MN']*1e6
    a_peak = max(b['a_end_g'] for b in r['burns'])*G0
    n = v(cfg['nozzle']['struts_per_loop']); topo = v(cfg['nozzle'].get('strut_topology', {'value': 'star'}))
    loops = noz['loops']; N = len(loops); struts = []
    for i, L in enumerate(loops):
        x0, r0 = L['x'], L['r']
        if topo == 'chain' and i > 0:
            x1, r1 = loops[i-1]['x'], loops[i-1]['r']; carried = (N-i)/N      # this link carries the loops aft of it
        else:
            x1, r1 = lay['x_shield_aft'], shield['radius_hw_aft_m']*0.85; carried = 1.0 if topo == 'chain' else 1.0/N
        length = math.hypot(x1-x0, r1-r0); cosang = abs(x1-x0)/length
        load = F*carried/n/max(cosang, 0.2)
        t = tube(load, length, c); t.update(loop=L['name'], length_m=length, load_N=load, count=n, a=(x0, r0), b=(x1, r1))
        struts.append(t)
    m_struts = sum(t['mass_kg']*t['count'] for t in struts)
    m_module = v(c['module_frame_kg_per_m'])*lay['module_length']
    m_shield_frame = shield['mass_kg']['frame']                         # booked with the shield
    m_gal = v(c['gallery_kg_per_m'])*galleries['length_m']*galleries['count']
    m_spars = v(c['wing_spar_kg_per_m'])*wings['span_m']*wings['count']*2
    m_bays = v(c['module_frame_kg_per_m'])*lay.get('added_bay_length', 0.0)*0.5
    total = m_struts+m_module+m_gal+m_spars+m_bays
    # inter-loop magnetic force scale (stored field ~ pulse energy, spacing between loop 1 and 2)
    W = rec['yield_per_pulse_J']                                        # nozzle field energy ratio 1 (scenario v1)
    gaps = [math.hypot(a['x']-b['x'], a['r']-b['r']) for a, b in zip(noz['loops'], noz['loops'][1:])]
    return {'thrust_N': F, 'peak_accel_g': a_peak/G0, 'design_accel_g': v(c['design_accel_g']),
            'struts': struts, 'mass_kg': {'nozzle_struts': m_struts, 'equipment_module_frame': m_module, 'driver_galleries': m_gal,
                                          'radiator_wing_spars': m_spars, 'added_tank_bay_frames': m_bays, 'total': total},
            'shield_frame_kg': m_shield_frame,
            'interface_load_N': {'hull_thrust_ring': F, 'q45_collar_limit_N': 23.5e6, 'ratio_to_q45': F/23.5e6},
            'interloop_force_scale_N': W/min(gaps) if gaps else 0.0,
            'limits': ['struts carry thrust only; the GN-scale attraction between coaxial loops is inside the virial nozzle mass, its load paths are not designed',
                       'wing spars sized per metre (in-plane thrust loads are tiny); manoeuvre, deployment and habitat-spin-up loads are unresolved',
                       'no dynamic (pulse-rate) fatigue analysis: 100 Hz for 5.7 years is ~1.8e10 load cycles on the nozzle structure']}
