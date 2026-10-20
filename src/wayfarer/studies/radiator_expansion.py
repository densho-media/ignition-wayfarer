"""RAD-DATUM-2026-10-10 (S&E 15!A116, 40!A64:A65): diagnostic multi-temperature growth rig for the ten hot blade cassettes. Pure, writes JSON,
never edits canon or geometry.

The owner keeps the global datum at the aft root boom and every as-built station PROVISIONALLY and asks whether the ~1.5 m free growth can be
taken locally: ten individually guided hot cassettes, each on its own local support reference, nine 0.125 m seams, 0.20 m guided travel and
flexible feed/return. This rig is a 1-D thermo-elastic kinematics screen (free strain only, no stiffness, friction or load), not a qualification.

Model (all PROTOTYPE unless sourced):
- Bays and seams are the built ones (thermal_geometry.bay_joints, seam_width). Cassette i is the sheet between its two seam edges (the end
  cassettes run to the blade ends). Each cassette grows freely from its LOCAL DATUM, a guided shoe that is fixed axially on the carrier: at
  mid-bay (scheme MID_BAY, proposed here; no mid-bay datum is built) or, for the two root bays, at the root booms (scheme ROOT_BOOMS).
- The carrier is the continuous truss (chords unbroken through the joints, 07!A37). It grows from the global datum (the aft root boom, built)
  at the carrier temperature; the hull side is held at the installation temperature. Its temperature and material are OPEN, so three carrier
  states are run: (a) at the installation temperature (all growth local, the owner's intent), (a') warm at WARM_CARRIER_K, and (b) the failure
  case: every cassette locked to its neighbour (or the carrier as hot as the sheet), so the growth accumulates from the global datum; joint
  shoe slip is then not defined (null) and the global slides take the root-edge growth.
- Strain = mean CTE x (T - T_INSTALL). The mean CTE over ~300-1800 K is applied at every temperature (secant approximation).
- Joint closure = forward growth of the aft cassette's edge - forward growth of the fore cassette's edge; the gap is the seam width minus it.
  A negative closure opens the seam. Shoe slip = cassette edge motion relative to the carrier frame at the joint (the built joint shoes).
  Global slides (forward root, stays 2/4/6/8) slip by the carrier motion relative to the hull.

Usage: python3 src/wayfarer/studies/radiator_expansion.py [--out runs/<stamp>-radiator-expansion]
"""
from pathlib import Path
import argparse
import datetime
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
from spec import load
import forward_shield
import habitat_ring
import layout
import thermal_geometry as tg

T_INSTALL_K = 293.0         # PROTOTYPE: zero-strain installation temperature (OPEN)
T_HOT_K = 1800.0            # radiators.temperature (WORKING)
COLD_SOAK_K = 100.0         # PROTOTYPE: non-operating deep-space cold soak
WARM_CARRIER_K = 450.0      # PROTOTYPE: carrier truss at the ~450 K warm-loop level (thermal.loops), not a sourced truss temperature
ROOT_EDGE_K = 900.0         # PROTOTYPE: root edge of the 3 m root transition (40!A65), linear to T_HOT_K across the band
AXIAL_FRONT_K = 1400.0      # PROTOTYPE: front end of a linear aft-hot/front-cool gradient (aft edge at T_HOT_K)
ISOLATED_BAY = 9            # PROTOTYPE: one isolated cassette (bays 1..10 from aft) cold-soaked while its neighbours run hot
FACE_DT_K = (10.0, 50.0, 100.0)
STEPS = 200                 # Simpson intervals per integration span (the profiles are piecewise linear; exact to rounding)

# DIAGNOSTIC literature mean CTE over ~300-1800 K, 1/K (approximate ranges; the blade material is OPEN, 15!G61, OD-007).
MATERIALS = {
    'CC_composite': dict(alpha=1.5e-6, range=[1.0e-6, 2.0e-6], note='carbon/carbon, in-plane, layup dependent'),
    'SiC': dict(alpha=4.8e-6, range=[4.5e-6, 5.0e-6], note='monolithic SiC'),
    'W': dict(alpha=5.0e-6, range=[4.5e-6, 5.5e-6], note='tungsten'),
    'Mo_TZM': dict(alpha=6.2e-6, range=[5.8e-6, 6.5e-6], note='Mo / TZM'),
    'Nb_C103': dict(alpha=8.0e-6, range=[7.5e-6, 8.5e-6], note='niobium alloy C-103'),
}


def simpson(f, a, b, n=STEPS):
    if a == b:
        return 0.0
    h = (b-a)/n
    return h/3*(f(a)+f(b)+sum((4 if k % 2 else 2)*f(a+k*h) for k in range(1, n)))


def integrate(f, a, b, breaks):
    """Integral a->b (signed), split at the frame stations so stepped profiles integrate exactly."""
    lo, hi = min(a, b), max(a, b)
    pts = [lo]+sorted(x for x in breaks if lo < x < hi)+[hi]
    total = sum(simpson(f, p, q) for p, q in zip(pts, pts[1:]))
    return total if b >= a else -total


def geometry(s, seam=None, bays=None):
    """The built blade, or (RAD-002 options) the same blade cut into `bays` equal cassettes with `seam` wide seams: same length, ends, datum,
    slides and feeds; the joints then leave the built frames and stays (not rebuilt)."""
    d = tg.blade_of(s); w = seam if seam is not None else tg.seam_width(s); h = w/2
    built = s['radiators']['geometry']['major_bays']; bays = bays or built
    aft, front = d['aft_x_m'], d['front_x_m']; Lb = d['blade_length_m']/bays
    frames = [aft+k*Lb for k in range(bays+1)]
    if bays == built:
        joints = [j['x'] for j in tg.bay_joints(s, d)]
        assert all(abs(a-b) < 1e-9 for a, b in zip(joints, frames[1:-1]))
    cassettes = [dict(bay=i+1, x0=frames[i]+(h if i > 0 else 0.0), x1=frames[i+1]-(h if i < bays-1 else 0.0), mid=(frames[i]+frames[i+1])/2)
                 for i in range(bays)]
    ms = tg.mounts(s, d); datum = next(m for m in ms if m['role'] == 'FIXED_DATUM')
    roots = tg.stations(s, d)['roots']
    collar = forward_shield.bypass_collar(s); spar = s['prototype']['radiator_leading_spar_radius_m']
    hoop_aft_face = collar['stations']['aft']-collar['member_radius']
    ring_face = layout.at(s, s['prototype']['thrust_ring_x'])+s['structure']['ring_depth_m']/2
    ring_a_sweep = min(habitat_ring.centers(s))-habitat_ring.sweep_half(s)
    p = s['prototype']; hull_v = s['structure']['sector_radius_m']-d['center_radius_m']
    top = tg.FEED_TRUNK_V+p['coolant_feed_loop_rise_m']
    return dict(d=d, seam=w, bays=bays, bay_length=Lb, frames=frames, cassettes=cassettes, datum_x=datum['x'], roots=roots,
                slides=[m for m in ms if m['role'] == 'AXIAL_SLIDE'], width=d['ribbon_width_m'], trunk_v=tg.FEED_TRUNK_V,
                travel=s['radiators']['thermal_expansion']['distributed_compliance']['local_travel_m'],
                aggregate=s['radiators']['thermal_expansion']['distributed_compliance']['aggregate_envelope_m'],
                band=s['radiators']['root_band']['width_m'], sheet_depth=p['radiator_thickness_m'], truss_depth=s['radiators']['geometry']['truss_depth_m'],
                bellows_length=p['coolant_trunk_bellows_length_m'], line_d=2*p['coolant_feed_radius_m'],
                loop_legs=[top-hull_v, top-tg.FEED_TRUNK_V], casing_gap=s['radiators']['root_radius']['value']-tg.casing_radius(s),
                ends=dict(collar_hoop_to_blade_front=hoop_aft_face-front, collar_hoop_to_spar_front=hoop_aft_face-(front+spar),
                          ring_A_sweep_to_spar_front=ring_a_sweep-(front+spar), ring_A_min=s['habitat']['ring_service_clearance']['min_m'],
                          thrust_ring_face_to_blade_aft=aft-ring_face, thrust_ring_face_to_aft_frame=aft-tg.FRAME_R-ring_face,
                          thrust_ring_outer_r=s['structure']['ring_od_m']/2, blade_root_r=d['root_radius_m']))


def local_datums(g, scheme):
    out = [c['mid'] for c in g['cassettes']]
    if scheme == 'FRONT_FIXED':                     # RAD-002 option: the front cassette's datum at its front edge, so the front stays put
        out[-1] = g['cassettes'][-1]['x1']
    if scheme == 'ROOT_BOOMS':                      # the two root booms sit in bays 5 and 6 (built stations)
        for x in g['roots']:
            i = next((k for k, c in enumerate(g['cassettes']) if c['x0'] <= x <= c['x1']), None)
            if i is not None:
                out[i] = x
    return out


def cases(g):
    """Temperature fields T(x, v): x ship axial, v from the root edge (0) to the outer edge (ribbon width)."""
    aft, front = g['d']['aft_x_m'], g['d']['front_x_m']; band = g['band']; f0, f1 = g['frames'][ISOLATED_BAY-1], g['frames'][ISOLATED_BAY]
    root = lambda v: ROOT_EDGE_K+(T_HOT_K-ROOT_EDGE_K)*min(v, band)/band
    return {
        'COLD_SOAK': dict(T=lambda x, v: COLD_SOAK_K, note=f'uniform {COLD_SOAK_K:.0f} K, non-operating'),
        'HOT_UNIFORM': dict(T=lambda x, v: T_HOT_K, note=f'uniform {T_HOT_K:.0f} K'),
        'ROOT_BAND_COOLER': dict(T=lambda x, v: root(v), note=f'{T_HOT_K:.0f} K, root edge {ROOT_EDGE_K:.0f} K, linear across the {band:g} m band'),
        'AXIAL_GRADIENT': dict(T=lambda x, v: T_HOT_K+(AXIAL_FRONT_K-T_HOT_K)*(x-aft)/(front-aft), note=f'{T_HOT_K:.0f} K aft edge to {AXIAL_FRONT_K:.0f} K front, linear'),
        'BAY_ISOLATED_COLD': dict(T=lambda x, v: COLD_SOAK_K if f0 < x < f1 else T_HOT_K,
                                  note=f'{T_HOT_K:.0f} K, bay {ISOLATED_BAY} isolated at {COLD_SOAK_K:.0f} K'),
    }


def in_plane_curvature(alpha, T, x, width, n=STEPS):
    """Free in-plane curvature (1/m) of a cassette section from the width-wise profile; positive = outer edge longer, ends sweep toward the root."""
    e = lambda v: alpha*(T(x, v)-T_INSTALL_K)
    mean = simpson(e, 0.0, width, n)/width
    return 12*simpson(lambda v: (e(v)-mean)*(v-width/2), 0.0, width, n)/width**3


def run_case(g, alpha, T, carrier, scheme, eps=None, carrier_eps=None, Tc=None):
    """Joint closures, slips, end motions and feed take-up for one material, temperature field, carrier state and datum scheme. eps(T): the
    sheet's free strain from T_INSTALL (default the secant alpha x dT; RAD-002 passes the integral of alpha(T)); carrier_eps: the carrier's
    (default eps); carrier 'a_carrier_T' runs the carrier at Tc."""
    xg = g['datum_x']; breaks = g['frames']
    eps = eps or (lambda t: alpha*(t-T_INSTALL_K)); carrier_eps = carrier_eps or eps
    if carrier == 'b_accumulated':
        U = lambda x, v: integrate(lambda q: eps(T(q, v)), xg, x, breaks)
        carrier_U = lambda x: U(x, 0.0)                # stays and root booms meet the blade at its root edge
        edge = lambda i, x, v: U(x, v)
    else:
        Tc = {'a_carrier_install': T_INSTALL_K, 'a_carrier_warm': WARM_CARRIER_K}.get(carrier, Tc)
        carrier_U = lambda x: carrier_eps(Tc)*(x-xg)
        dat = local_datums(g, scheme)
        edge = lambda i, x, v: carrier_U(dat[i])+integrate(lambda q: eps(T(q, v)), dat[i], x, breaks)
    cs = g['cassettes']; vs = {'root_edge': 0.0, 'trunk': g['trunk_v'], 'outer_edge': g['width']}
    joints = []
    for i, (a, b) in enumerate(zip(cs, cs[1:])):
        xj = g['frames'][i+1]
        closure = {k: edge(i, a['x1'], v)-edge(i+1, b['x0'], v) for k, v in vs.items()}
        slip = None if carrier == 'b_accumulated' else max(abs(edge(k, x, v)-carrier_U(xj)) for k, x in ((i, a['x1']), (i+1, b['x0'])) for v in vs.values())
        joints.append(dict(joint=i+1, x=xj, closure_m=closure, gap_m=g['seam']-max(closure.values()),
                           max_open_gap_m=g['seam']-min(closure.values()), shoe_slip_m=slip))
    aft = min(edge(0, cs[0]['x0'], v) for v in vs.values()); front = max(edge(len(cs)-1, cs[-1]['x1'], v) for v in vs.values())
    slides = [dict(name=m['name'], x=m['x'], slip_m=carrier_U(m['x'])) for m in g['slides']]
    e = g['ends']
    clear = dict(collar_hoop_to_blade_front=e['collar_hoop_to_blade_front']-front, collar_hoop_to_spar_front=e['collar_hoop_to_spar_front']-front,
                 ring_A_sweep_to_spar_front=e['ring_A_sweep_to_spar_front']-front,
                 thrust_ring_face_to_blade_aft=e['thrust_ring_face_to_blade_aft']+aft, thrust_ring_face_to_aft_frame=e['thrust_ring_face_to_aft_frame']+aft)
    takeup = [j['closure_m']['trunk'] for j in joints]
    loop = edge(next(k for k, c in enumerate(cs) if c['x0'] <= xg <= c['x1']), xg, g['trunk_v'])-carrier_U(xg)
    if carrier == 'b_accumulated':
        takeup = [0.0]*len(joints); loop = 0.0
    legs = g['loop_legs']; k3 = sum(L**3 for L in legs)
    leg_strain = lambda delta: max(3*g['line_d']*abs(delta)*L**3/k3/L**2 for L in legs)     # legs in series, guided cantilevers
    hot_trunk = abs(integrate(lambda q: eps(T(q, g['trunk_v'])), g['d']['aft_x_m'], g['d']['front_x_m'], breaks))
    feed = dict(per_joint_takeup_m=takeup, max_bellows_takeup_m=max(abs(t) for t in takeup), bellows_axial_strain=max(abs(t) for t in takeup)/g['bellows_length'],
                loop_deflection_local_m=loop, loop_leg_bending_strain_local=leg_strain(loop),
                loop_deflection_if_sum_m=hot_trunk, loop_leg_bending_strain_if_sum=leg_strain(hot_trunk))
    flags = []
    for j in joints:
        if j['gap_m'] <= 0:
            flags.append(f"joint {j['joint']} closes ({j['gap_m']:+.3f} m)")
        if j['shoe_slip_m'] is not None and j['shoe_slip_m'] > g['travel']:
            flags.append(f"joint {j['joint']} shoe slip {j['shoe_slip_m']:.3f} m > {g['travel']} m")
    for m in slides:
        if abs(m['slip_m']) > g['travel']:
            flags.append(f"{m['name']} slip {abs(m['slip_m']):.3f} m > {g['travel']} m")
    for k, v in clear.items():
        if k.startswith('ring_A'):
            if v < e['ring_A_min']-1e-9 and front > 1e-9:
                flags.append(f'{k} {v:.3f} m < WORKING {e["ring_A_min"]} m minimum')
        elif v <= 0:
            flags.append(f'{k} {v:+.3f} m')
    return dict(joints=joints, max_closure_m=max(max(j['closure_m'].values()) for j in joints), min_gap_m=min(j['gap_m'] for j in joints),
                max_open_gap_m=max(j['max_open_gap_m'] for j in joints), max_shoe_slip_m=None if carrier == 'b_accumulated' else max(j['shoe_slip_m'] for j in joints),
                max_global_slide_m=max(abs(m['slip_m']) for m in slides), global_slides=slides,
                aft_motion_m=aft, front_motion_m=front, clearances_m=clear, feed=feed, flags=flags)


def bow(g, alpha):
    """Through-thickness (face-to-face) bow, free curvature alpha*dT/depth. Per cassette: sagitta between its two joint shoes; front tip of bay 10
    (supported at its joint shoes and its mid-bay datum, front half overhanging); and the whole blade as one plate clamped at the global datum."""
    c10 = g['cassettes'][-1]; Lc = c10['x1']-c10['x0']; sd = c10['mid']-c10['x0']; se = Lc
    out = []
    for name, depth in (('sheet_display_0.15m', g['sheet_depth']), ('truss_3m', g['truss_depth'])):
        for dT in FACE_DT_K:
            k = alpha*dT/depth
            out.append(dict(depth=name, depth_m=depth, dT_K=dT, curvature_per_m=k, bay_sagitta_m=k*Lc**2/8,
                            bay10_front_tip_m=k/2*se*(se-sd), continuous_front_tip_m=k*(g['d']['front_x_m']-g['datum_x'])**2/2))
    return out


def end_sweep(g, alpha, T):
    """ROOT_BAND_COOLER in-plane bow: free sagitta per cassette and, as one continuous blade clamped at the datum, the radial sweep of each end
    toward the root edge (vs the casing gap)."""
    k = in_plane_curvature(alpha, T, 0.0, g['width'])
    Lc = g['cassettes'][1]['x1']-g['cassettes'][1]['x0']
    return dict(curvature_per_m=k, bay_sagitta_m=k*Lc**2/8, continuous_front_sweep_m=k*(g['d']['front_x_m']-g['datum_x'])**2/2,
                continuous_aft_sweep_m=k*(g['datum_x']-g['d']['aft_x_m'])**2/2, casing_gap_m=g['casing_gap'])


def options(g, eps):
    """Owner options at strain eps without moving the collar or the blade: seam width for zero closure at nine joints, cassettes needed at the
    0.125 m seam (and its net-area cost), and the carrier temperature rise that consumes the front clearance (carrier of the same material)."""
    Lb = g['bay_length']; w = g['seam']; L = g['d']['blade_length_m']
    n = math.ceil(eps*L/(w*(1+eps))+1e-12)
    return dict(seam_for_zero_closure_m=eps*Lb/(1+eps), cassettes_needed_at_working_seam=n,
                extra_seam_planform_m2=(n-g['bays'])*w*g['width'])


def carrier_limit(g, alpha, eps):
    """Carrier temperature rise above T_INSTALL that brings the front to the collar hoop / spar clearance (MID_BAY scheme, uniform sheet strain)."""
    c10 = g['cassettes'][-1]; local = eps*(c10['x1']-c10['mid']); arm = c10['mid']-g['datum_x']
    return {k: (g['ends'][k]-local)/(alpha*arm) for k in ('collar_hoop_to_blade_front', 'collar_hoop_to_spar_front')}


def run(out_dir):
    s, *_ = load(ROOT); g = geometry(s); L = g['d']['blade_length_m']; dT = T_HOT_K-T_INSTALL_K
    mats = dict(MATERIALS)
    mats['owner_equivalent'] = dict(alpha=g['aggregate']/(L*dT), range=None, note=f'alpha x {dT:.0f} K over {L:.3f} m = the owner aggregate {g["aggregate"]} m (40!A64)')
    tc = cases(g); results = {}
    for mname, m in mats.items():
        a = m['alpha']; rm = dict(alpha_per_K=a, range_per_K=m['range'], note=m['note'],
                                  free_growth_total_hot_m=a*dT*L, free_growth_total_cold_soak_m=a*(COLD_SOAK_K-T_INSTALL_K)*L, cases={})
        for cname, c in tc.items():
            rm['cases'][cname] = {f'{carrier}/{scheme}': run_case(g, a, c['T'], carrier, scheme)
                                  for carrier in ('a_carrier_install', 'a_carrier_warm', 'b_accumulated')
                                  for scheme in (('MID_BAY', 'ROOT_BOOMS') if carrier != 'b_accumulated' else ('GLOBAL',))}
        rm['face_to_face_bow'] = bow(g, a)
        rm['root_band_end_sweep'] = end_sweep(g, a, tc['ROOT_BAND_COOLER']['T'])
        rm['options_hot_uniform'] = options(g, a*dT)
        rm['carrier_dT_limit_K'] = carrier_limit(g, a, a*dT)
        results[mname] = rm
    result = dict(
        status='DIAGNOSTIC_PROTOTYPE_RIG_NOT_A_QUALIFICATION',
        request='RAD-DATUM-2026-10-10 (S&E 15!A116; 40!A64:A65)',
        scope='1-D free thermal strain of ten cassettes on a carrier; no stiffness, friction, load, creep or temperature-dependent CTE. Material, '
              'temperature map, installation temperature, carrier (truss) temperature and loads are OPEN; every temperature and datum below is PROTOTYPE.',
        assumptions=dict(T_install_K=T_INSTALL_K, T_hot_K=T_HOT_K, cold_soak_K=COLD_SOAK_K, warm_carrier_K=WARM_CARRIER_K, root_edge_K=ROOT_EDGE_K,
                         axial_front_K=AXIAL_FRONT_K, isolated_bay=ISOLATED_BAY, hull_side='held at T_install',
                         local_datum='MID_BAY: guided shoe at each mid-bay, fixed axially on the carrier (not built); ROOT_BOOMS: bays 5/6 at the built root booms',
                         shoe_travel='WORKING 0.20 m per compliant station (40!A64); flagged when one edge slips more than 0.20 m',
                         loop='feed/return U loop legs as guided cantilevers in series; bending strain 3 D delta / L^2'),
        cases={k: v['note'] for k, v in tc.items()},
        geometry=dict(blade_length_m=L, bay_length_m=g['bay_length'], seam_m=g['seam'], frames_x_m=g['frames'], global_datum_x_m=g['datum_x'],
                      cassettes=g['cassettes'], global_slides=[dict(name=m['name'], x=m['x']) for m in g['slides']], local_travel_m=g['travel'],
                      end_clearances_m=g['ends'], loop_legs_m=g['loop_legs'], bellows_length_m=g['bellows_length'], line_diameter_m=g['line_d']),
        materials=results)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/'radiator_expansion.json').write_text(json.dumps(result, indent=1)+'\n')
    return result


def summary(r):
    rows = []
    for name, m in r['materials'].items():
        a = m['cases']['HOT_UNIFORM']; loc = a['a_carrier_install/MID_BAY']; rb = a['a_carrier_install/ROOT_BOOMS']; warm = a['a_carrier_warm/MID_BAY']
        acc = a['b_accumulated/GLOBAL']; cold = m['cases']['COLD_SOAK']['a_carrier_install/MID_BAY']
        bow = {(b['depth'], b['dT_K']): b for b in m['face_to_face_bow']}
        rows.append(dict(material=name, alpha=m['alpha_per_K'], growth_hot=m['free_growth_total_hot_m'],
                         closure=loc['max_closure_m'], min_gap=loc['min_gap_m'], slip=loc['max_shoe_slip_m'], cold_gap=cold['max_open_gap_m'],
                         rb_min_gap=rb['min_gap_m'], rb_slip=rb['max_shoe_slip_m'],
                         a_aft=loc['aft_motion_m'], a_front=loc['front_motion_m'], warm_front=warm['front_motion_m'], warm_slide=warm['max_global_slide_m'],
                         b_aft=acc['aft_motion_m'], b_front=acc['front_motion_m'], b_slide=acc['max_global_slide_m'],
                         b_spar=acc['clearances_m']['collar_hoop_to_spar_front'], a_spar=loc['clearances_m']['collar_hoop_to_spar_front'],
                         loop=loc['feed']['loop_deflection_local_m'], loop_strain=loc['feed']['loop_leg_bending_strain_local'],
                         bellows=loc['feed']['max_bellows_takeup_m'], loop_sum=loc['feed']['loop_deflection_if_sum_m'],
                         sheet_bow100=bow[('sheet_display_0.15m', 100.0)]['bay_sagitta_m'], truss_bow100=bow[('truss_3m', 100.0)]['bay_sagitta_m'],
                         truss_tip100=bow[('truss_3m', 100.0)]['bay10_front_tip_m'], sweep=m['root_band_end_sweep']['continuous_front_sweep_m'],
                         seam_needed=m['options_hot_uniform']['seam_for_zero_closure_m'], n_needed=m['options_hot_uniform']['cassettes_needed_at_working_seam'],
                         carrier_dT=m['carrier_dT_limit_K']['collar_hoop_to_spar_front']))
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=None)
    args = ap.parse_args()
    out = args.out or ROOT/'runs'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-radiator-expansion')
    r = run(out)
    for row in summary(r):
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) and k != 'alpha' else v) for k, v in row.items()}))
    print(out/'radiator_expansion.json')
