"""S02 slice 1 (user brief 2026-10-18): docking guidance, airlock floodlights and position beacons outside the hull ([exterior_hardware]).

No owner row sizes or places these (S&E 37 F14-F17 name comms, trackers, RCS and momentum control only). Every size and position is PROTOTYPE
judgment with a stated function. The parts are placed in the hull's own frame around each fitting's radial axis. The screen proves the two
rules that keep them out of the existing interfaces:
- every docking aid stays below its port's visiting-vehicle corridor base (the collar tip) less mechanical_clearance_m;
- every docking aid stays outside the capture ring plus that clearance.
The rim beacons stay inside the 90 m shield diameter, away from every Crown port.

Slice 2 adds the primary comms (two Ka-band high-gain dishes, one optical terminal) and the RCS pods, and sizing() states the bounded cases
behind them (link budget, inertia bound, flip and momentum authority). Owner rows give functions only (S&E 37 F14/F16/F17, 38 S20, 15 S3):
every number there is a PROTOTYPE screening case, not a requirement.

    python3 src/wayfarer/exterior_hardware.py        # placement report and sizing (JSON)
"""
import math
from pathlib import Path
import sys

import hull_geometry as hg
import layout


def table(s):
    return s['exterior_hardware']


def frame(theta):
    """Unit axes (along X, tangential, radial) at angle theta about the ship axis (as human_entry.axes_at)."""
    return ((1.0, 0.0, 0.0), (0.0, -math.sin(theta), math.cos(theta)), (0.0, math.cos(theta), math.sin(theta)))


def on_hull(s, x0, theta, dx, dt, h):
    """Point at axial offset dx and tangential arc dt from the fitting axis (x0, theta), at height h above the hull."""
    x = x0+dx; r = hg.radius_at(s, x); a = theta+dt/r
    return (x, (r+h)*math.cos(a), (r+h)*math.sin(a)), a, r


def box(name, kind, role, centre, theta, size, **kw):
    return dict(dict(name=name, shape='box', kind=kind, role=role, world_centre=centre, axes=frame(theta), size=tuple(size)), **kw)


def disc(name, kind, role, a, b, radius, **kw):
    return dict(dict(name=name, shape='tube', kind=kind, role=role, a=a, b=b, r1=radius), **kw)


def docking(s):
    q = table(s); out = []
    for f in hg.service_fittings(s):
        if not f['name'].startswith('Dock_'):
            continue
        tag = f['name'][5:]; L, W, D = q['dock_target_m']; dx, dt = q['dock_target_offset_m']; pr, ph = q['dock_target_post']
        base, a, r = on_hull(s, f['x'], f['theta'], dx, dt, 0.0); top, _, _ = on_hull(s, f['x'], f['theta'], dx, dt, ph)
        out.append(disc(f'Ext_Dock_{tag}_Target_Post', 'exterior_hardware', 'approach target post', base, top, pr, fitting=f['name'], off=(dx, dt), top_h=ph))
        c, _, _ = on_hull(s, f['x'], f['theta'], dx, dt, ph+D/2)
        out.append(box(f'Ext_Dock_{tag}_Target', 'exterior_hardware', 'passive optical approach target and retroreflector cross for the visiting '
                       'vehicle\'s camera and lidar', c, a, (L, W, D), fitting=f['name'], off=(dx, dt), top_h=ph+D, half=max(L, W)/2, emissive=False))
        for k, (lx, lt) in enumerate(q['dock_light_offsets_m'], 1):
            b0, a, r = on_hull(s, f['x'], f['theta'], lx, lt, 0.0); b1, _, _ = on_hull(s, f['x'], f['theta'], lx, lt, q['dock_light_height_m'])
            out.append(disc(f'Ext_Dock_{tag}_Align_Light_{k}', 'exterior_hardware', 'amber alignment light (approach cue)', b0, b1, q['dock_light_radius_m'],
                            fitting=f['name'], off=(lx, lt), top_h=q['dock_light_height_m'], half=q['dock_light_radius_m'], light='amber'))
        R = q['dock_sensor_ring_m']; L, W, D = q['dock_sensor_m']
        for k, deg in enumerate((45, 135, 225, 315), 1):
            sx, st = R*math.cos(math.radians(deg)), R*math.sin(math.radians(deg))
            c, a, r = on_hull(s, f['x'], f['theta'], sx, st, D/2)
            out.append(box(f'Ext_Dock_{tag}_Proximity_{k}', 'exterior_hardware', 'proximity sensor (short-range lidar / radar) for range and rate',
                           c, a, (L, W, D), fitting=f['name'], off=(sx, st), top_h=D, half=max(L, W)/2))
    return out


def airlock(s):
    q = table(s); f = next(f for f in hg.service_fittings(s) if f['name'] == 'Airlock_EVA'); L, W, D = q['airlock_flood_m']; out = []
    for k, (dx, dt) in enumerate(q['airlock_flood_offsets_m'], 1):
        c, a, r = on_hull(s, f['x'], f['theta'], dx, dt, D/2)
        out.append(box(f'Ext_Airlock_Flood_{k}', 'exterior_hardware', 'floodlight over the EVA hatch and its handrails', c, a, (L, W, D),
                       fitting=f['name'], off=(dx, dt), top_h=D, half=max(L, W)/2, light='white'))
    return out


def thrust_ring(s):
    """Aft mount station: the thrust ring X and the outer radius of its nodes (plus mount_gap_m), where the aft parts stand."""
    p = s['prototype']; st = s['structure']
    return layout.at(s, p['thrust_ring_x']), st['ring_node_radius_m']+0.2+table(s)['mount_gap_m']


def aft_beacons(s):
    """On top of each aft RCS pod, at its aft end: white strobes marking the aft extremity at the keel azimuths."""
    q = table(s); x0, rb = thrust_ring(s); L, W, D = q['rcs_pod_m']; x = x0-L/2+0.2; r = rb+D; out = []
    for k, deg in enumerate(q['rcs_aft_deg'], 1):
        a = math.radians(deg); u = (math.cos(a), math.sin(a))
        out.append(disc(f'Ext_Beacon_Aft_{k}', 'exterior_hardware', 'white position strobe marking the aft extremity (on the aft RCS pod)',
                        (x, r*u[0], r*u[1]), (x, (r+q['beacon_depth_m'])*u[0], (r+q['beacon_depth_m'])*u[1]), q['beacon_radius_m'], light='white'))
    return out


def rim_beacons(s):
    """Flush in the rim girder's outer face: a lens from r 45 - depth to r 45 (inside the 90 m diameter), at the rim's mid-depth."""
    import forward_shield as fs
    q = table(s); st = fs.stations(s); R = st['shield_r']; x = sum(st['rim'])/2; out = []
    for k, deg in enumerate(q['rim_beacon_deg'], 1):
        a = math.radians(deg); u = (math.cos(a), math.sin(a))
        out.append(disc(f'Ext_Beacon_Rim_{k}', 'nav_light', 'white position strobe at the widest point of the silhouette (shield rim)',
                        (x, (R-q['beacon_depth_m'])*u[0], (R-q['beacon_depth_m'])*u[1]), (x, R*u[0], R*u[1]), q['beacon_radius_m'], light='white', deg=deg))
    return out


K_DB = -228.599
AU = 1.495978707e11
G0 = 9.80665


def db(x):
    return 10*math.log10(x)


def link_budget(s):
    """Ka-band downlink of one high-gain dish to a ground-station class receiver (G/T), per range case: gain, beamwidth, C/N0 and the rate
    at the required Eb/N0. Free-space only (no atmosphere, pointing or implementation loss), so the rate is an upper screening value."""
    q = table(s); lam = 299792458.0/(q['link_band_GHz']*1e9); D = q['hga_dish_diameter_m']
    G = db(q['link_aperture_efficiency']*(math.pi*D/lam)**2); eirp = db(q['link_tx_power_W'])+G; rows = []
    for au in q['link_range_cases_AU']:
        d = au*AU; L = 20*math.log10(4*math.pi*d/lam); cn0 = eirp-L+q['link_station_G_T_dB_K']-K_DB
        rows.append(dict(range_AU=au, light_time_h=round(d/299792458.0/3600, 2), path_loss_dB=round(L, 1), C_N0_dBHz=round(cn0, 1),
                         rate_Mbps=round(10**((cn0-q['link_required_Eb_N0_dB'])/10)/1e6, 3), sun_earth_max_deg=round(math.degrees(math.asin(min(1.0, 1/au))), 2)))
    return dict(band_GHz=q['link_band_GHz'], dish_m=D, gain_dBi=round(G, 1), beamwidth_deg=round(math.degrees(1.02*lam/D), 3),
                eirp_dBW=round(eirp, 1), tx_W=q['link_tx_power_W'], station_G_T_dB_K=q['link_station_G_T_dB_K'], cases=rows)


def inertia_case(s, propellant_kg=0.0):
    """Transverse and roll inertia (kg m2) of the mass budget spread over the PROTOTYPE spans of [exterior_hardware].inertia_items, plus
    propellant_kg in the BODY-001 train. Returns (mass, x_cm, I_transverse, I_roll)."""
    q = table(s); m = {i['id']: i['mass_kg'] for i in s['physics']['mass_budget']['items']}
    parts = [(m[i['id']], i['x'], i['model']) for i in q['inertia_items']]
    if propellant_kg:
        parts.append((propellant_kg, q['propellant_x'], ['cyl', q['propellant_r_m']]))
    M = sum(p[0] for p in parts); xc = sum(p[0]*sum(p[1])/2 for p in parts)/M; It = Ix = 0.0
    for mk, (x0, x1), mod in parts:
        if mod[0] == 'blade':
            r2 = (mod[1]**2+mod[1]*mod[2]+mod[2]**2)/3; rx, rt = mk*r2, mk*r2/2           # three blades at 120 deg: axisymmetric on average
        elif mod[0] == 'ring':
            rx, rt = mk*mod[1]**2, mk*mod[1]**2/2
        else:
            rx, rt = mk*mod[1]**2/2, mk*mod[1]**2/4
        It += mk*(x1-x0)**2/12+mk*((x0+x1)/2-xc)**2+rt; Ix += rx
    return M, xc, It, Ix


def sizing(s):
    """The bounded cases behind the RCS and momentum-control choices (all PROTOTYPE except the sourced masses and ring momentum)."""
    q = table(s); ph = s['physics']; burn = ph['protected_burnout_mass']['value']
    cases = [('burnout', 0.0), ('inventory_lower', ph['propulsion_inventory']['lower_kg']), ('inventory_upper', ph['propulsion_inventory']['upper_kg']),
             ('departure_upper', ph['departure_mass']['upper_kg']-burn)]
    F = q['rcs_thrust_N']; lever = layout.at(s, {'datum': 'FWD', 'offset_m': 0.0})-3.0-thrust_ring(s)[0]
    tau_pitch = F*math.cos(math.radians(q['rcs_aft_jet_aft_cant_deg']))*lever; Rr = forward_shield_r(s); tau_roll = 2*F*math.cos(math.radians(q['rcs_rim_cant_deg']))*Rr
    rows = []
    for name, prop in cases:
        M, xc, It, Ix = inertia_case(s, prop)
        flips = []
        for T in q['flip_case_s']:
            tau = 4*math.pi*It/T**2; flips.append(dict(flip_min=T/60, torque_N_m=round(tau), peak_H_N_m_s=round(tau*T/2)))
        T = math.sqrt(4*math.pi*It/tau_pitch); J = 2*F*T        # bang-bang: one nozzle at each end fires through the whole flip
        rows.append(dict(case=name, mass_t=round(M/1e3), x_cm_m=round(xc, 1), I_transverse=f'{It:.3e}', I_roll=f'{Ix:.3e}', flip_requirements=flips,
                         flip_at_rcs_min=round(T/60, 1), propellant_per_flip_kg={f'isp_{int(i)}': round(J/(i*G0)) for i in q['rcs_isp_s']},
                         roll_accel_deg_s2=f'{math.degrees(2*tau_roll/Ix):.2e}'))
    Hres = ph['rotor_dynamics']['allowed_residual_momentum_N_m_s']
    return dict(status='PROTOTYPE bounding cases (owner: data rate, band, aperture, thrust, slew, flip time NOT FOUND)', link=link_budget(s),
                rcs=dict(thrust_per_nozzle_N=F, pitch_yaw_lever_m=round(lever, 1), pitch_yaw_couple_N_m=round(tau_pitch), roll_couple_two_pods_N_m=round(2*tau_roll),
                         cases=rows),
                momentum=dict(ring_residual_H_N_m_s=Hres, source='08 allowed residual (0.1 %, WORKING)', storage_N_m_s=round(q['momentum_storage_factor']*Hres),
                              dump_at_rcs_s=round(q['momentum_storage_factor']*Hres/tau_pitch, 1),
                              note='momentum storage (CMG / wheels) is internal and waits on BODY-001 (equipment bay); not built'))


def forward_shield_r(s):
    import forward_shield as fs
    return fs.stations(s)['shield_r']


def unit(v):
    n = math.sqrt(sum(c*c for c in v)); return tuple(c/n for c in v)


def comms(s):
    """Two gimballed Ka-band dishes and one optical terminal on radial booms at X comms_x_m, COAST pose: boresight aft (-X), Earth during
    outbound coast. Each part carries its gimbal centre and sweep radius for the screen."""
    q = table(s); x = q['comms_x_m']; xm, rm = thrust_ring(s)      # each boom stands on the thrust-ring node at its azimuth
    br = q['boom_radius_m']; g = q['hga_gimbal_m']; out = []
    D = q['hga_dish_diameter_m']; f = q['hga_focal_ratio']*D; depth = D*D/(16*f)
    for k, deg in enumerate(q['hga_deg'], 1):
        a = math.radians(deg); top = q['hga_boom_top_r_m']; c = radial(x, top+g/2, a); sweep = math.hypot(D/2, depth+g/2)
        tag = dict(gimbal=c, sweep=max(sweep, f-g/2), antenna=f'HGA_{k}')
        out.append(disc(f'Ext_HGA_{k}_Boom', 'comms_antenna', 'boom from the thrust ring carrying the high-gain dish clear of the hull and blades', radial(xm, rm, a), radial(x, top, a), br, **tag))
        out.append(box(f'Ext_HGA_{k}_Gimbal', 'comms_antenna', 'two-axis gimbal (azimuth / elevation) of the high-gain dish', c, a, (g, g, g), **tag))
        v = (c[0]-g/2, c[1], c[2])
        out.append(dict(name=f'Ext_HGA_{k}_Dish', shape='dish', kind='comms_antenna', role=f'{D:.0f} m Ka-band high-gain dish (primary downlink); boresight aft in COAST',
                        vertex=v, axis=(-1.0, 0.0, 0.0), radius=D/2, depth=depth, **tag))
        out.append(disc(f'Ext_HGA_{k}_Feed', 'comms_antenna', 'feed and subreflector support on the dish axis', v, (v[0]-f, v[1], v[2]), 0.09, **tag))
    a = math.radians(q['optical_deg']); top = q['optical_boom_top_r_m']; c = radial(x, top+g/2, a); d0, L = q['optical_tube_m']
    tag = dict(gimbal=c, sweep=math.hypot(L+g/2, d0/2), antenna='OPT')
    out.append(disc('Ext_Optical_Boom', 'comms_antenna', 'boom of the primary optical terminal, from the thrust ring', radial(xm, rm, a), radial(x, top, a), br, **tag))
    out.append(box('Ext_Optical_Gimbal', 'comms_antenna', 'coarse gimbal of the optical terminal (fine pointing inside)', c, a, (g, g, g), **tag))
    out.append(disc('Ext_Optical_Telescope', 'comms_antenna', f'primary optical terminal: {q["optical_aperture_m"]:.1f} m aperture telescope with sunshade; '
                    'high-rate path beside the independent survival terminal (Eye A25)', (c[0]-g/2, c[1], c[2]), (c[0]-g/2-L, c[1], c[2]), d0/2, **tag))
    return out


def radial(x, r, a):
    return (x, r*math.cos(a), r*math.sin(a))


def rcs_aft(s):
    """Three aft pods on the hull at the bisectors: per pod a housing, one radial-outward nozzle and two tangential nozzles."""
    q = table(s); x, rh = thrust_ring(s); L, W, D = q['rcs_pod_m']; nr, nl = q['rcs_nozzle_radius_m'], q['rcs_nozzle_length_m']; out = []
    back = math.radians(q['rcs_aft_jet_aft_cant_deg'])   # every aft jet canted aft: its cone never reaches the blades' aft edge (and settles ullage)
    for k, deg in enumerate(q['rcs_aft_deg'], 1):
        a = math.radians(deg); c = radial(x, rh+D/2, a); t = (0.0, -math.sin(a), math.cos(a)); u = (0.0, math.cos(a), math.sin(a))
        out.append(box(f'Ext_RCS_Aft_{k}', 'exterior_hardware', 'RCS pod on a thrust-ring node: valves, thrusters and feed from the internal bottles', c, a, (L, W, D), rcs=True))
        xr = x+L/2-0.25; j = (-math.sin(back), u[1]*math.cos(back), u[2]*math.cos(back)); b0 = radial(xr, rh+D, a); b1 = tuple(b0[i]+j[i]*nl for i in range(3))
        out.append(disc(f'Ext_RCS_Aft_{k}_Radial', 'exterior_hardware', 'radial-outward thruster canted aft (pitch / yaw couple, ullage)', b0, b1, nr, jet=j, exit=b1))
        cant = math.radians(q['rcs_aft_cant_deg'])         # canted outward so the jet cone clears the hull it runs along
        for side, sg in (('Pos', 1), ('Neg', -1)):
            h = tuple(sg*t[i]*math.cos(cant)+u[i]*math.sin(cant) for i in range(3)); j = (-math.sin(back), h[1]*math.cos(back), h[2]*math.cos(back))
            p0 = tuple(c[i]+sg*t[i]*(W/2-nr)+u[i]*(D/2-nr) for i in range(3)); p1 = tuple(p0[i]+j[i]*nl for i in range(3))
            out.append(disc(f'Ext_RCS_Aft_{k}_Tan_{side}', 'exterior_hardware', 'tangential thruster canted outward (roll)', p0, p1, nr, jet=j, exit=p1))
    return out


def rcs_rim(s):
    """Four pods on the shield rim's aft face between Crown bays: a radial-outward nozzle flush inside r 45 and two tangential nozzles canted
    aft by rcs_rim_cant_deg so no jet reaches the rim girder or the shield."""
    import forward_shield as fs
    q = table(s); st = fs.stations(s); R = st['shield_r']; L, W, D = q['rcs_pod_m']; nr, nl = q['rcs_nozzle_radius_m'], q['rcs_nozzle_length_m']
    x = st['rim'][0]-L/2; rc = R-0.3-D/2; cant = math.radians(q['rcs_rim_cant_deg']); out = []
    for k, deg in enumerate(q['rcs_rim_deg'], 1):
        a = math.radians(deg); c = radial(x, rc, a); t = (0.0, -math.sin(a), math.cos(a)); u = (0.0, math.cos(a), math.sin(a))
        out.append(box(f'Ext_RCS_Rim_{k}', 'rcs_thruster', 'RCS pod on the rim: roll and pitch / yaw authority at the largest lever', c, a, (L, W, D), rcs=True, deg=deg))
        b0 = radial(x, rc+D/2, a); b1 = radial(x, min(rc+D/2+nl, R-0.02), a)
        out.append(disc(f'Ext_RCS_Rim_{k}_Radial', 'rcs_thruster', 'radial-outward thruster (pitch / yaw couple with the aft pods)', b0, b1, nr, jet=u, exit=b1, deg=deg))
        for side, sg in (('Pos', 1), ('Neg', -1)):
            j = (-math.sin(cant), sg*t[1]*math.cos(cant), sg*t[2]*math.cos(cant)); p0 = tuple(c[i]+sg*t[i]*W/2 for i in range(3)); p1 = tuple(p0[i]+j[i]*nl for i in range(3))
            out.append(disc(f'Ext_RCS_Rim_{k}_Tan_{side}', 'rcs_thruster', 'tangential thruster canted aft (roll)', p0, p1, nr, jet=j, exit=p1, deg=deg))
    return out


def nav_sensors(s):
    """Slice 3: per bisector azimuth a pedestal on the hull at nav_tracker_x_m, a star-tracker head with its sun baffle on a radial
    boresight, and a coarse sun sensor on the pedestal's forward face looking forward and out."""
    q = table(s); x = q['nav_tracker_x_m']; L, W, D = q['nav_pedestal_m']; br, bl = q['nav_baffle_m']; cr, ch = q['nav_css_m']; out = []
    for k, deg in enumerate(q['nav_tracker_deg'], 1):
        a = math.radians(deg); rh = hg.radius_at(s, x); u = (0.0, math.cos(a), math.sin(a)); tag = dict(tracker=k, boresight=u)
        out.append(box(f'Ext_Nav_Tracker_{k}_Pedestal', 'exterior_hardware', 'star-tracker pedestal: thermally stable mount on the hull frame',
                       radial(x, rh+D/2, a), a, (L, W, D), **tag))
        out.append(disc(f'Ext_Nav_Tracker_{k}_Head', 'exterior_hardware', f'primary star tracker {k} (attitude to arcseconds) with its sun baffle; radial boresight',
                        radial(x, rh+D, a), radial(x, rh+D+bl, a), br, **tag))
        c0 = (x+L/2, (rh+D*.6)*u[1], (rh+D*.6)*u[2]); n = unit((1.0, u[1], u[2]))
        out.append(disc(f'Ext_Nav_Sun_Sensor_{k}', 'exterior_hardware', 'coarse sun sensor (sun-safe attitude, wide field)', c0,
                        tuple(c0[i]+n[i]*ch for i in range(3)), cr, css=n, tracker=k))
    return out


def nav_screen(s):
    """Rows per head: the stray-light keep-out cone and the FOV clear of blades, rings, shield, hull and the plume; and over the whole sky
    the share of sun directions that leave at least two heads outside their sun exclusion (must be 1)."""
    q = table(s); o = obstacles(s); rows = []; heads = [p for p in nav_sensors(s) if p['name'].endswith('_Head')]
    for p in heads:
        c = p['b']; b = p['boresight']
        keep = [ray_hit(o, c, r, plume=math.radians(max(q['plume_half_angle_deg']))) for r in cone(b, math.radians(q['nav_keepout_half_deg']), 8)]
        clear = sum(h is None for h in keep)/len(keep)
        rows.append(dict(name=p['name'], keepout_clear=round(clear, 3), hits=sorted({h for h in keep if h}), ok=clear == 1.0))
    sky = cone((1.0, 0.0, 0.0), math.pi, 24); ex = math.cos(math.radians(q['nav_sun_exclusion_deg']))
    two = sum(sum(sum(d[m]*h['boresight'][m] for m in range(3)) < ex for h in heads) >= 2 for d in sky)/len(sky)
    sep = min(math.degrees(math.acos(max(-1.0, min(1.0, sum(a['boresight'][m]*b['boresight'][m] for m in range(3))))))
              for i, a in enumerate(heads) for b in heads[i+1:])
    rows.append(dict(name='nav_sun_availability', two_heads_unblinded_share=round(two, 4), min_boresight_separation_deg=round(sep, 1),
                     ok=two == 1.0 and sep > 2*q['nav_sun_exclusion_deg']))
    return rows


def eva_rails(s):
    """Slice 4 (owner brief 2026-10-30, PROTOTYPE): the guided-EVA route's handrail built as hardware on the stationary forward collar
    (eva_route.route: the airlock's azimuth, aft to the aft hold and forward to the forward hold). One handrail per run on a standoff at
    every anchor station, a tether anchor ring beside each standoff, and a foot-restraint plate at each hold. The aft body is crawler
    territory (DS-10 rail): no crew rail crosses the rotor bay, which the rings sweep."""
    import eva_route
    import eva_suit
    q = table(s); rt = eva_route.route(s, eva_suit.load()); a = math.radians(rt['rail_azimuth_deg']); rr = q['eva_rail_radius_m']
    u, t = (0.0, math.cos(a), math.sin(a)), (0.0, -math.sin(a), math.cos(a)); out = []
    for name, (x0, x1) in rt['runs'].items():
        hull = hg.radius_at(s, (x0+x1)/2)
        out.append(disc(f'Ext_EVA_Rail_{name.title()}', 'eva_rail', 'EVA handrail (hand-over-hand translation, tether slide)',
                        radial(x0, rt['rail_radius_m'], a), radial(x1, rt['rail_radius_m'], a), rr, eva=True))
    for anc in rt['anchors']:
        x = anc['x']; hull = hg.radius_at(s, x); k = anc['id'][4:].title()
        out.append(disc(f'Ext_EVA_Standoff_{k}', 'eva_rail', 'handrail standoff on the collar frame', radial(x, hull, a), radial(x, rt['rail_radius_m']-rr, a),
                        q['eva_standoff_radius_m'], eva=True))
        c = tuple(radial(x, hull, a)[i]+t[i]*q['eva_anchor_offset_m'] for i in range(3))
        out.append(disc(f'Ext_EVA_Anchor_{k}', 'eva_anchor', 'tether anchor ring (one of two tethers clipped at all times)', c,
                        tuple(c[i]+u[i]*q['eva_anchor_m'][1] for i in range(3)), q['eva_anchor_m'][0], eva=True))
    for name in ('aft_hold', 'forward_hold'):
        x = rt['holds'][name]['x']; hull = hg.radius_at(s, x); L, W, D = q['eva_foot_plate_m']
        c = tuple(radial(x, hull+s['casing_panels']['seam_height_m']+.005+D/2, a)[i]-t[i]*q['eva_anchor_offset_m']*2.5 for i in range(3))   # seated on the collar straps
        out.append(box(f'Ext_EVA_Foot_Restraint_{name.split("_")[0].title()}', 'eva_anchor', 'portable foot-restraint socket at the hold point', c, a, (L, W, D), eva=True))
    return out


def service_parts(s):
    return docking(s)+airlock(s)+aft_beacons(s)+comms(s)+rcs_aft(s)+nav_sensors(s)+eva_rails(s)


def forward_parts(s):
    return rim_beacons(s)+rcs_rim(s)


def obstacles(s):
    import habitat_ring
    import thermal_geometry as tg
    d = tg.blade_of(s)
    return dict(blade=d, blades=[math.radians(s['prototype']['radiator_phase_deg']+j*120) for j in range(s['radiators']['count'])],
                rings=[(x, habitat_ring.sweep_half(s), habitat_ring.outer(s)) for x in habitat_ring.centers(s)], shield=(105.9, forward_shield_r(s)),
                hull=[(layout.at(s, {'datum': 'AFT', 'offset_m': 0.0}), 80.0, hg.radius_at(s, 0.0)), (80.0, layout.at(s, {'datum': 'FWD', 'offset_m': 0.0}), hg.radius_at(s, 100.0))])


def ray_hit(o, c, r, tmax=1e9, spheres=(), plume=None):
    """First obstacle a ray from c along unit r meets within tmax: blade planes, ring and shield discs, the hull cylinder, extra spheres
    (centre, radius, name) and optionally the main plume cone (half-angle in rad, apex on the axis at the nozzle exit plane)."""
    d = o['blade']
    for a in o['blades']:
        nrm = (0.0, -math.sin(a), math.cos(a)); den = sum(r[m]*nrm[m] for m in range(3))
        if abs(den) > 1e-12:
            t = -sum(c[m]*nrm[m] for m in range(3))/den
            if 1e-6 < t < tmax:
                p = [c[m]+t*r[m] for m in range(3)]; rho = p[1]*math.cos(a)+p[2]*math.sin(a)
                if d['aft_x_m'] <= p[0] <= d['front_x_m'] and d['root_radius_m'] <= rho <= d['outer_radius_m']:
                    return 'blade'
    for xs, R, name in [(x+h*sg, ro, 'ring') for x, h, ro in o['rings'] for sg in (-1, 1)]+[(o['shield'][0], o['shield'][1], 'shield')]:
        if abs(r[0]) > 1e-12:
            t = (xs-c[0])/r[0]
            if 1e-6 < t < tmax and math.hypot(c[1]+t*r[1], c[2]+t*r[2]) <= R:
                return name
    A = r[1]**2+r[2]**2; B = 2*(c[1]*r[1]+c[2]*r[2])
    for x0, x1, rh in o['hull']:                       # the hull as two cylinders (aft body, forward body)
        C = c[1]**2+c[2]**2-rh*rh
        if A > 1e-12 and B*B-4*A*C >= 0:
            for t in sorted(((-B-math.sqrt(B*B-4*A*C))/(2*A), (-B+math.sqrt(B*B-4*A*C))/(2*A))):
                if 1e-6 < t < tmax and x0 <= c[0]+t*r[0] <= x1:
                    return 'hull'
    x0 = o['hull'][0][0]
    for sc, sr, name in spheres:
        w = [sc[m]-c[m] for m in range(3)]; t = max(0.0, min(tmax, sum(w[m]*r[m] for m in range(3))))
        if math.dist(sc, [c[m]+t*r[m] for m in range(3)]) <= sr:
            return name
    if plume is not None:
        for k in range(1, 400):
            t = min(tmax, 0.5*1.03**k); p = [c[m]+t*r[m] for m in range(3)]
            if p[0] < x0 and math.hypot(p[1], p[2]) <= (x0-p[0])*math.tan(plume):
                return 'plume'
            if t >= tmax:
                break
    return None


def cone(b, half, n=12):
    """Unit directions sampling a cone of half-angle half (rad) about unit b, the axis included."""
    h = (0.0, 0.0, 1.0) if abs(b[2]) < 0.9 else (1.0, 0.0, 0.0); e1 = unit((b[1]*h[2]-b[2]*h[1], b[2]*h[0]-b[0]*h[2], b[0]*h[1]-b[1]*h[0]))
    e2 = (b[1]*e1[2]-b[2]*e1[1], b[2]*e1[0]-b[0]*e1[2], b[0]*e1[1]-b[1]*e1[0]); out = [b]
    for i in range(1, n+1):
        th = half*i/n
        for k in range(4*i):
            ph = 2*math.pi*k/(4*i); out.append(tuple(math.cos(th)*b[m]+math.sin(th)*(math.cos(ph)*e1[m]+math.sin(ph)*e2[m]) for m in range(3)))
    return out


def pointing(s):
    """Per antenna (from its gimbal): the aft axis clear in COAST and in a burn, and the clear fraction of a pointing_cone_deg cone about
    -X in COAST and under each plume case; the two dishes' union over the aft hemisphere."""
    q = table(s); o = obstacles(s); ants = {}
    for p in comms(s):
        ants.setdefault(p['antenna'], p['gimbal'])
    dirs = cone((-1.0, 0.0, 0.0), math.radians(q['pointing_cone_deg'])); hemi = cone((-1.0, 0.0, 0.0), math.pi/2, 16); rows = {}; seen = {}
    for name, c in ants.items():
        row = dict(aft_axis_coast=ray_hit(o, c, (-1.0, 0.0, 0.0)) is None, cone_clear_coast=round(sum(ray_hit(o, c, r) is None for r in dirs)/len(dirs), 3))
        row['aft_axis_burn_15deg'] = ray_hit(o, c, (-1.0, 0.0, 0.0), plume=math.radians(min(q['plume_half_angle_deg']))) is None
        for pa in q['plume_half_angle_deg']:
            row[f'cone_clear_burn_{pa:g}deg'] = round(sum(ray_hit(o, c, r, plume=math.radians(pa)) is None for r in dirs)/len(dirs), 3)
        rows[name] = row
        if name.startswith('HGA'):
            seen[name] = [ray_hit(o, c, r) is None for r in hemi]
    union = [any(v[i] for v in seen.values()) for i in range(len(hemi))]
    return dict(antennas=rows, hga_union_aft_hemisphere_coast=round(sum(union)/len(union), 3))


def jets(s):
    """Each nozzle's jet as a cone of the smaller plume study half-angle out to 60 m: the first obstacle any sampled ray meets (rings, blades,
    shield, hull, the comms sweeps)."""
    q = table(s); o = obstacles(s); half = math.radians(min(q['plume_half_angle_deg']))
    sph = {}
    for p in comms(s):
        sph[p['antenna']] = (p['gimbal'], p['sweep'], p['antenna'])
    rows = []
    for p in rcs_aft(s)+rcs_rim(s):
        if 'jet' not in p:
            continue
        e = p['exit']; hits = {ray_hit(o, tuple(e[m]+0.05*p['jet'][m] for m in range(3)), r, 60.0, list(sph.values())) for r in cone(p['jet'], half, 6)} - {None}
        rows.append(dict(name=p['name'], hits=sorted(hits), ok=not hits))
    return rows


def screen(s):
    """Rows: each docking aid against its corridor base and capture ring; each rim beacon against the shield radius and the Crown ports."""
    import forward_shield as fs
    p = s['prototype']; clr = p['mechanical_clearance_m']; rings = {q['fitting']: q for q in hg.capture_rings(s)}; fit = {f['name']: f for f in hg.service_fittings(s)}
    rows = []
    for q in docking(s):
        f = fit[q['fitting']]; ring = rings[q['fitting']]
        under = (f['r1']-clr)-(f['r_hull']+q['top_h'])
        d_axis = math.hypot(*q['off'])-q.get('half', q.get('r1', 0.0))
        outside = d_axis-(ring['radius']+clr)
        rows.append(dict(name=q['name'], below_corridor_base_m=round(under, 3), outside_capture_ring_m=round(outside, 3), ok=under >= 0 and outside >= 0))
    ports = fs.crown_ports(s); R = fs.stations(s)['shield_r']
    for q in rim_beacons(s):
        a = math.radians(q['deg'])
        gap = min(abs((a-pt['azimuth']+math.pi) % (2*math.pi)-math.pi)*R-pt['width']/2 for pt in ports)-q['r1']
        rows.append(dict(name=q['name'], inside_shield_radius=math.hypot(q['b'][1], q['b'][2]) <= R+1e-9, crown_port_gap_m=round(gap, 2), ok=gap >= clr))
    # Slice 2. Comms sweeps: aft of the blades, above the hull, clear of the aft beacons and RCS pods.
    d = __import__('thermal_geometry').blade_of(s); seen = {}
    others = [(p['a'], p['r1'], p['name']) for p in aft_beacons(s)]+[(p['world_centre'], math.hypot(*p['size'])/2, p['name']) for p in rcs_aft(s) if p.get('rcs')]
    for p in comms(s):
        if p['antenna'] in seen:
            continue
        c, w = p['gimbal'], p['sweep']; seen[p['antenna']] = 1
        fwd = d['aft_x_m']-(c[0]+w); lift = math.hypot(c[1], c[2])-w-hg.radius_at(s, layout.at(s, s['prototype']['thrust_ring_x'])); gap = min(math.dist(c, oc)-w-orad for oc, orad, _ in others)
        rows.append(dict(name=f"Ext_{p['antenna']}_sweep", sweep_r_m=round(w, 2), aft_of_blades_m=round(fwd, 2), above_hull_m=round(lift, 2), nearest_part_m=round(gap, 2),
                         ok=min(fwd, lift, gap) >= clr))
    for p in rcs_aft(s):
        if p.get('rcs'):
            top = max(math.hypot(v[1], v[2]) for v in __import__('human_entry').box_corners(None, p))+q_len(s)
            rows.append(dict(name=p['name'], inside_body_envelope=top <= s['ship']['body_diameter']['max']/2, ok=top <= s['ship']['body_diameter']['max']/2))
    corr = [f['theta'] for f in hg.service_fittings(s) if f['name'].startswith('Dock_')]; beacons = [math.radians(v) for v in table(s)['rim_beacon_deg']]
    for p in rcs_rim(s):
        if not p.get('rcs'):
            continue
        a = math.radians(p['deg']); arc = lambda b: abs((a-b+math.pi) % (2*math.pi)-math.pi)*R
        half = p['size'][1]/2+table(s)['rcs_nozzle_length_m']
        gp = min(arc(pt['azimuth'])-pt['width']/2 for pt in ports)-half; gd = min(arc(b) for b in corr)-1.5-half; gb = min(arc(b) for b in beacons)-half
        rows.append(dict(name=p['name'], crown_port_gap_m=round(gp, 2), dock_corridor_gap_m=round(gd, 2), rim_beacon_gap_m=round(gb, 2), ok=min(gp, gd, gb) >= clr))
    for r in jets(s):
        rows.append(r)
    return rows+nav_screen(s)


def q_len(s):
    return table(s)['rcs_nozzle_length_m']


if __name__ == '__main__':
    import json
    ROOT = Path(__file__).resolve().parents[2]
    from spec import load
    s = load(ROOT)[0]; rows = screen(s)
    print(json.dumps(dict(parts=len(service_parts(s))+len(forward_parts(s)), rows=rows, ok=all(r['ok'] for r in rows), pointing=pointing(s), sizing=sizing(s)), indent=1))
