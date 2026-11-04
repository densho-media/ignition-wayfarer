"""The EVA system's numbers: the suit's life-support module and propulsion reserve, and the companion drone (docs/WAYFARER_EVA_SYSTEM.md).

Standard library only. Parameters come from data/eva_suit.toml ([form], [module], [suit_propulsion]) and data/eva_drone.toml; every value is
PROTOTYPE (no IGNITION owner row defines this equipment; suit pressure EVA-004 stays OPEN). The Blender generators (build/eva_suit.py,
build/eva_drone.py) read every dimension from here, and the system check (validation/eva_system.py) passes the built layout back to study().

    python3 src/wayfarer/eva_system.py          # budgets, arm loads, reaction study and the nominal authority as JSON

Frames. Suit: metres, the astronaut faces -Y, +Z up, +X is the astronaut's left, origin on the floor between the feet. Drone LOCAL frame:
+Y nose (sensor face), +Z dorsal, -Z ventral (dock face), +X the drone's left. Docked, local -> suit world is (x, y, z) -> (-x, z, y).

What is verified here is arithmetic (gas mass, delta-v, pure-wrench reachability by non-negative least squares, volume sums). It is not
evidence that the hardware delivers those numbers: plume interaction, valve response, thermal behaviour and life-support capacity are
outside it and stay PROVISIONAL / OPEN.
"""
import json
import math
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]
G0 = 9.80665
R_N2 = 8.314462618/0.0280134          # J/(kg K)
AXES = ('Fx', 'Fy', 'Fz', 'Tx', 'Ty', 'Tz')


def load(root=ROOT):
    suit = tomllib.loads((root/'data/eva_suit.toml').read_text())
    drone = tomllib.loads((root/'data/eva_drone.toml').read_text())
    return suit, drone


_SUIT, _DRONE = load()
SUIT = dict(_SUIT['form'])                       # suit form (soft layers, cuirass, helmet, module envelope, dock channel)
MODULE = _SUIT['module']
SUIT_PROP = _SUIT['suit_propulsion']
SUIT_RESERVE = SUIT_PROP['reserve']
LS = _SUIT['life_support']
MASSES = {f'{k}_kg': v for k, v in SUIT_PROP['masses_kg'].items()}
P = _DRONE['gas']                                 # gas physics, plume check
DRONE = dict(_DRONE['body'], dry_mass_kg=_DRONE['dry_mass_kg'])
PROP = _DRONE['propulsion']
ARMS = _DRONE['arm']
COUPLING = _DRONE['coupling']
TOOLS = _DRONE['tool']
SENSORS = _DRONE['sensors']
ANCHOR = _DRONE['anchor']
DRONE_INFO = _DRONE['drone']
UTILITY_JAW = _DRONE['utility_jaw']
ARM_POSES = {nm: {K: (tuple(v['target']), tuple(v['approach']) if 'approach' in v else None) for K, v in p.items()}
             for nm, p in _DRONE['arm_pose'].items()}
THRUST = dict(suit_n=SUIT_PROP['thrust_n'], drone_n=PROP['thrust_n'])
THRUST_N = PROP['thrust_n']


# ------------------------------------------------------------------------------------------------------------------------------- gas
def capsule_volume(outer_d, length, wall):
    r = outer_d/2-wall; L = length-2*wall
    return math.pi*r*r*max(0.0, L-2*r)+4/3*math.pi*r**3


def n2_density(p=None, t=None, z=None):
    return (p or P['tank_pressure_pa'])/((z or P['z_factor'])*R_N2*(t or P['tank_temp_k']))


def tank(spec):
    v = spec['n']*capsule_volume(spec['outer_d_m'], spec['length_m'], spec['wall_m']); m = v*n2_density()
    return dict(volume_l=round(v*1000, 2), n2_kg=round(m, 3), usable_kg=round(m*P['usable_fraction'], 3))


def nozzle(thrust):
    """Throat and exit diameter of one nozzle at the regulated feed pressure (F = Cf Pc At), area ratio 20."""
    at = thrust/(P['cf']*P['feed_pressure_pa']); dt = math.sqrt(4*at/math.pi)
    return dict(thrust_n=thrust, throat_mm=round(dt*1000, 2), exit_mm=round(dt*math.sqrt(20)*1000, 1),
                mdot_g_s=round(thrust/(P['isp_s']*G0)*1000, 2))


# ------------------------------------------------------------------------------------------------------------------------- authority
def _unit(v):
    n = math.sqrt(sum(c*c for c in v)); return tuple(c/n for c in v)


def wrench_matrix(nozzles, thrust, com):
    """Columns: force and torque about com of each nozzle at full thrust (force = -thrust x exhaust direction)."""
    cols = []
    for pos, e in nozzles:
        f = tuple(-thrust*c for c in e); r = tuple(p-q for p, q in zip(pos, com))
        cols.append(f+(r[1]*f[2]-r[2]*f[1], r[2]*f[0]-r[0]*f[2], r[0]*f[1]-r[1]*f[0]))
    return cols


def nnls(cols, target, iters=4000):
    """Non-negative least squares by projected gradient (small problems): x >= 0 minimising |A x - b|."""
    n = len(cols); x = [0.0]*n
    step = 1.0/(sum(sum(c*c for c in col) for col in cols) or 1.0)
    for _ in range(iters):
        r = [sum(cols[j][i]*x[j] for j in range(n))-target[i] for i in range(6)]
        for j in range(n):
            x[j] = max(0.0, x[j]-step*sum(cols[j][i]*r[i] for i in range(6)))
    r = [sum(cols[j][i]*x[j] for j in range(n))-target[i] for i in range(6)]
    return x, math.sqrt(sum(v*v for v in r))


def authority_cols(cols):
    """For each of the 12 signed axes, the largest pure wrench along it reachable with valve duty cycles in [0, 1] (the five other
    components held near zero). Units: N and N m."""
    res = {}
    for i, nm in enumerate(AXES):
        for sg in (1, -1):
            unit = 1.0 if i < 3 else 0.3; target = [0.0]*6; target[i] = sg*unit
            x, err = nnls(cols, target); peak = max(x) if x else 0.0; ok = err < 0.02*unit and peak > 0
            res[('+' if sg > 0 else '-')+nm] = dict(ok=ok, max=round(unit/peak, 2) if ok else 0.0, unit='N' if i < 3 else 'N m',
                                                    residual=round(err, 4))
    return res


def authority(nozzles, thrust, com):
    return authority_cols(wrench_matrix(nozzles, thrust, com))


def single_failure(cols_list, thrust_list, com):
    """Worst single valve failed closed: the number of the 12 pure axes still reachable."""
    flat = [(p, e, t) for (cs_, t) in zip(cols_list, thrust_list) for p, e in cs_]
    worst = (13, None)
    for k in range(len(flat)):
        cols = []
        for i, (p, e, t) in enumerate(flat):
            if i != k:
                cols += wrench_matrix([(p, e)], t, com)
        worst = min(worst, (sum(r['ok'] for r in authority_cols(cols).values()), k))
    return dict(worst_axes_reachable=worst[0], worst_failed_index=worst[1], nozzles=len(flat))


def axes_ok(res):
    return sum(r['ok'] for r in res.values())


def mass_centre(parts):
    m = sum(p[0] for p in parts); return tuple(sum(p[0]*p[1][i] for p in parts)/m for i in range(3))


def burnbrow(docked_kg, up_thrust_n):
    return {f'{g:.1f}g': dict(weight_n=round(docked_kg*g*G0), max_upward_cold_gas_n=round(up_thrust_n, 1),
                              fraction=round(up_thrust_n/(docked_kg*g*G0), 4)) for g in P['burn_g']}


# --------------------------------------------------------------------------------------------------------------------------- layouts
def drone_halfwidth(y):
    """Half-width of the drone plan at local y (nose +L/2, tail -L/2): constant over the nose two-thirds, tapering to the tail, rounded
    corners at both ends."""
    D = DRONE; L2 = D['length_m']/2; wn, wt = D['half_width_nose_m'], D['half_width_tail_m']
    if y >= D['taper_start_y_m']:
        w = wn
    else:
        t = (D['taper_start_y_m']-y)/(D['taper_start_y_m']+L2); w = wn+(wt-wn)*(t**1.3)
    r = D['nose_round_m']
    if y > L2-r:
        q = (y-(L2-r))/r; w = w-r+r*math.sqrt(max(0.0, 1-q*q))
    if y < -L2+.06:
        q = ((-L2+.06)-y)/.06; w = w-.06+.06*math.sqrt(max(0.0, 1-q*q))
    return max(0.0, w)


def plss_halfwidth(v):
    """Half-width of the life-support module outline at height fraction v: straight sides, rounded corners."""
    w = SUIT['plss_size_m'][0]/2
    top = 1.0 if v < 0.86 else max(0.0, 1-((v-0.86)/0.14)**3.0)**(1/3.0)
    bot = 1.0 if v > 0.10 else max(0.0, 1-((0.10-v)/0.10)**3.0)**(1/3.0)
    return w*0.97*top*bot


def suit_nozzles(clusters):
    """16 suit nozzles, four per module-corner cluster: FWD (ahead, canted up and out at the shoulders, out and down at the lumbar), AFT
    (behind, canted out past the drone), OUT (sideways), VERT (up at the shoulders, down at the lumbar, out and aft away from helmet and
    seat). clusters: {tag: (centre, sx, sz)}. Returns [(name, pos, exhaust, cluster)]."""
    out = []
    for tag, (c, sx, sz) in clusters.items():
        fwd = (sx*0.55, -1.0, 0.70) if sz > 0 else (sx*1.0, -0.45, -0.15)
        aft = (sx*0.25, 1.0, 0.12) if sz > 0 else (sx*0.30, 1.0, -0.10)
        vert = (sx*0.28, 0.12, 1.0) if sz > 0 else (sx*0.30, 0.25, -1.0)
        for nm, e, off in (('FWD', fwd, (sx*0.010, -0.022, sz*0.004)), ('AFT', aft, (sx*0.006, 0.030, 0.0)),
                           ('OUT', (sx, 0.0, 0.0), (sx*0.030, 0.0, 0.0)), ('VERT', vert, (sx*0.010, 0.004, sz*0.030))):
            out.append((f'{tag}_{nm}', tuple(p+o for p, o in zip(c, off)), _unit(e), tag))
    return out


def nozzles_from_clusters(clusters, lat_cant_deg=None):
    """The drone's 26 nozzles [(name, pos, exhaust, cluster, inhibit_near_suit)] in the LOCAL frame. clusters: {tag: ((x, y, z), sx, sy)},
    sx the side (+1 left), sy +1 nose / -1 tail. Nose clusters: LAT, LATB, LAT2 (canted aft), DOR, DORB, VEN, LON. Tail clusters: LAT, LATB,
    DOR, VEN, LON, LON2. The four VEN nozzles fire straight at whatever the dock face points at, so they are valved off docked and within
    PROP['proximity_m'] of a suit. Backing away (+Z) near a suit comes from the LAT nozzles instead: each is canted `lat_cant_deg` (nose,
    tail) from the lateral axis towards the dock face, so its plume runs outboard past the suit's shoulders and hips while a pair still
    pushes the drone off (fix 4.1: the near-suit retreat / abort authority). Near-suit single-fault tolerance comes from duplicating, not
    from steeper cants: LATB is a second nozzle on the LAT line (same cant, so the same plume-clear corridor) and DORB a second dorsal
    nozzle at the nose, the one axis (pitch) a single DOR could otherwise carry alone. The nose dorsal pair is canted 45 and 54 deg outboard:
    each arm rises from its bay just behind and inboard of the nose cluster and passes over it, so a vertical dorsal plume would wash it."""
    cn, ct = (math.radians(a) for a in (PROP['lateral_ventral_cant_deg'] if lat_cant_deg is None else lat_cant_deg))
    lat = lambda sx, cant: (sx*math.cos(cant), 0.0, -math.sin(cant))
    out = []
    for tag, (c, sx, sy) in clusters.items():
        if sy > 0:
            ns = [('LAT', lat(sx, cn), (sx*.022, 0, 0), False), ('LATB', lat(sx, cn), (sx*.022, .014, -.004), False), ('LAT2', (sx, -0.55, 0.0), (sx*.016, -.020, 0), False),
                  ('DOR', (sx*1.0, 0.0, 1.0), (0, 0, .020), False), ('DORB', (sx*1.4, 0.0, 1.0), (sx*.010, .012, .018), False),
                  ('VEN', (sx*.35, .10, -1.0), (0, 0, -.018), True), ('LON', (sx*.55, 1.0, .15), (sx*.010, .022, 0), False)]
        else:
            ns = [('LAT', lat(sx, ct), (sx*.022, 0, 0), False), ('LATB', lat(sx, ct), (sx*.022, -.014, -.004), False), ('DOR', (sx*.15, 0.0, 1.0), (0, 0, .020), False),
                  ('VEN', (sx*.35, -.10, -1.0), (sx*.010, -.004, -.018), True), ('LON', (sx*.45, -1.0, .30), (sx*.010, -.022, 0), False),
                  ('LON2', (sx*.10, -1.0, .55), (0, -.020, .010), False)]
        for nm, e, off, inh in ns:
            out.append((f'{tag}_{nm}', tuple(p+o for p, o in zip(c, off)), _unit(e), tag, inh))
    return out


def dock_layout():
    """The drone's dock hardware in its LOCAL frame, from the suit's module and channel parameters alone (the suit generator places the
    matching sockets from the same numbers): latch bolts (upper / lower pair), N2 probe and power plug along the keel (local y), and the
    bolt line's depth below the dock face (local z). Docked, local y runs up the module and local -z into the channel."""
    w = SUIT['plss_size_m'][0]; bulge = SUIT['plss_rear_bulge_m']; ch = SUIT['channel']; cwh = ch['width_m']/2; k = DRONE['keel']['length_m']/2
    return dict(latch_y=(k-.07, -k+.10), probe_y=-k+.045, plug_y=k-.03, keel_mid_y=0.0,
                bolt_z=-bulge*(cwh/(w/2))**2-ch['depth_m']*.55-SUIT['dock_gap_m'], channel_half_width=cwh, channel_depth=ch['depth_m'],
                draft=math.tan(math.radians(ch['draft_deg']))*ch['depth_m'])


def local_to_docked(p, dc):
    return (dc[0]-p[0], dc[1]+p[2], dc[2]+p[1])


def dir_to_docked(e):
    return (-e[0], e[2], e[1])


def arm_ik(arm, target, approach=(0.0, 1.0, 0.0), shoulder=(0.0, 0.0, 0.0), offsets=(0.0, 0.0), yaw_off=0.0):
    """Joint angles (radians) for an arm to put its flange at `target` (drone local) with the tool axis along `approach`, elbow up.
    A yaw joint at the shoulder (about local Z), then pitch joints about the yawed X axis (shoulder, elbow, wrist), then (arm A) a wrist
    yaw joint `yaw_off` beyond the wrist pitch axis. At rest (stowed) the upper link points aft (-Y) and the forearm forward (+Y), offset by
    the stacked layers (offsets: the elbow's and the wrist's height above the shoulder axis).
    Returns dict(yaw, pitch, elbow, wrist, wrist_yaw, reach_ok)."""
    l1, l2, lw = arm['l_upper_m'], arm['l_fore_m'], arm['l_wrist_m']
    d = [target[i]-shoulder[i] for i in range(3)]
    a = _unit(approach)
    w = [d[i]-a[i]*lw for i in range(3)]
    for _ in range(4 if yaw_off else 1):
        yaw = math.atan2(-w[0], w[1]); fwd = (-math.sin(yaw), math.cos(yaw))
        ap = a[0]*fwd[0]+a[1]*fwd[1]; u = (fwd[0]*ap, fwd[1]*ap, a[2]); un = math.sqrt(sum(c*c for c in u)) or 1.0; u = [c/un for c in u]
        if yaw_off:
            y_ = [d[i]-a[i]*(lw-yaw_off) for i in range(3)]; w = [y_[i]-u[i]*yaw_off for i in range(3)]
    yaw = math.atan2(-w[0], w[1]); fwd = (-math.sin(yaw), math.cos(yaw)); side = (math.cos(yaw), math.sin(yaw))
    ap = a[0]*fwd[0]+a[1]*fwd[1]
    rh = w[0]*fwd[0]+w[1]*fwd[1]; h = w[2]
    e1, e2 = offsets; u0 = (-l1, e1); f0 = (l2, e2-e1)
    L1 = math.hypot(*u0); L2 = math.hypot(*f0)
    dd = math.hypot(rh, h); ok = abs(L1-L2) <= dd <= L1+L2
    dd = min(max(dd, abs(L1-L2)+1e-6), L1+L2-1e-6)
    base = math.atan2(h, rh); al = math.acos(max(-1, min(1, (L1*L1+dd*dd-L2*L2)/(2*L1*dd))))
    th1 = base+al
    ex, ez = L1*math.cos(th1), L1*math.sin(th1)
    th2 = math.atan2(h-ez, rh-ex)
    a_u0 = math.atan2(u0[1], u0[0]); a_f0 = math.atan2(f0[1], f0[0])
    pitch = th1-a_u0; elbow = (th2-a_f0)-pitch
    wrist = math.atan2(a[2], ap)-(th2-a_f0)
    un = math.hypot(ap, a[2]) or 1.0
    wyaw = math.atan2(-(a[0]*side[0]+a[1]*side[1]), un) if yaw_off else 0.0
    wrap = lambda x: (x+math.pi) % (2*math.pi)-math.pi
    pitch = wrap(pitch)
    if pitch > math.radians(20):
        pitch -= 2*math.pi
    return dict(yaw=yaw, pitch=pitch, elbow=wrap(elbow) % (2*math.pi), wrist=wrap(wrist), wrist_yaw=wyaw, reach_ok=ok)


def joint_limits_ok(arm, ang):
    """Joint angles (radians, from arm_ik) against the arm's ranges; yaw is inboard-positive, mirrored for the right-hand arm (side -1)."""
    J = arm['joints']; s = arm['side']; deg = math.degrees
    checks = dict(shoulder_yaw=deg(ang['yaw'])*s, shoulder_pitch=deg(ang['pitch']), elbow=deg(ang['elbow']), wrist_pitch=deg(ang['wrist']))
    if 'wrist_yaw' in J:
        checks['wrist_yaw'] = deg(ang['wrist_yaw'])
    return {k: dict(deg=round(v, 1), ok=J[k][0]-1e-6 <= v <= J[k][1]+1e-6) for k, v in checks.items()}


# --------------------------------------------------------------------------------------------------------------------------- budgets
def budget():
    d = tank(DRONE['vessels']); r = tank(SUIT_RESERVE)
    dry = sum(DRONE['dry_mass_kg'].values()); drone_wet = dry+d['n2_kg']
    suit_wet = MASSES['crew_kg']+MASSES['suit_kg']+MASSES['plss_kg']+MASSES['reserve_hw_kg']+r['n2_kg']
    ve = P['isp_s']*G0; dv = lambda m0, mp: ve*math.log(m0/(m0-mp))
    return dict(n2_density_kg_m3=round(n2_density(), 1), drone_vessels=d, suit_reserve=r, drone_dry_kg=round(dry, 1),
                drone_wet_kg=round(drone_wet, 2), suited_crew_wet_kg=round(suit_wet, 2), docked_kg=round(drone_wet+suit_wet, 2),
                dv_docked_drone_gas_m_s=round(dv(drone_wet+suit_wet, d['usable_kg']), 2), dv_drone_alone_m_s=round(dv(drone_wet, d['usable_kg']), 1),
                dv_suit_reserve_alone_m_s=round(dv(suit_wet, r['usable_kg']), 2),
                total_impulse_drone_ns=round(d['usable_kg']*ve), total_impulse_reserve_ns=round(r['usable_kg']*ve),
                drone_nozzle=nozzle(THRUST_N), suit_nozzle=nozzle(THRUST['suit_n']),
                reference=dict(SAFER='about 1.4 kg GN2, 24 x 3.6 N, about 3 m/s (NASA)', MMU='2 x 5.9 kg GN2, 24 x 7.6 N, about 20 m/s (NASA)'))


def life_support_volume(module_l=None):
    """Packaging volume of the module's items with the packaging factor against the module envelope (bounding box x fill, or a measured
    `module_l`). This is a VOLUME check only: capacity, duration, heat rejection and power stay OPEN or PROVISIONAL per item."""
    items = MODULE['items_l']; s = sum(items.values()); need = s*MODULE['packaging_factor']
    w, d, h = SUIT['plss_size_m']; box = w*d*h*1000; avail = module_l if module_l else box*MODULE['envelope_fill']
    return dict(items_l=items, basis=MODULE['basis'], sum_l=round(s, 1), with_packaging_l=round(need, 1), module_envelope_l=round(avail, 1),
                envelope_method='measured closed module volume' if module_l else f"bounding box x {MODULE['envelope_fill']}",
                margin_l=round(avail-need, 1), feedwater_in_hatch_l=MODULE['feedwater_in_hatch_l'],
                verified='packing volume only; no capability is verified')


def _o2_kg(water_l):
    o = LS['o2']; return o['pressure_pa']/(o['z']*8.314462/0.0319988*o['temp_k'])*water_l/1000*o['usable']


def life_support_budget():
    """Consumables, heat and power for the [life_support] design targets in the low / nominal / high cases (PROVISIONAL engineering
    estimate, not a qualification): O2 from metabolic rate (14.1 MJ per kg O2) plus leakage and one repress, CO2 at RQ 0.85 (regenerable
    swing bed, no consumable), SWME feedwater for the sensible load, battery energy. Each case gives the duration every consumable allows;
    the shortest one sets the EVA. The secondary O2 is sized for the open-loop purge that keeps ppCO2 under the emergency limit."""
    t = LS['nominal_h']+LS['reserve_h']; e_w = sum(LS['electronics_w'].values()); o2p = _o2_kg(LS['o2']['primary_water_l'])
    o2s = _o2_kg(LS['o2']['secondary_water_l']); bat = MODULE_BATTERY_WH*LS['battery_depth']
    rep = LS['suit_pressure_kpa']*1e3*LS['suit_free_volume_m3']*0.0319988/(8.314462*293.0)
    cases = {}
    for i, nm in enumerate(('low', 'nominal', 'high')):
        met = LS['metabolic_w'][i]; leak = LS['leak_kg_h'][i]; env = LS['environment_w'][i]
        o2_h = met*3600/14.1e6; co2_h = o2_h*0.85*44.01/32.0; vap_h = met*LS['latent_fraction']*3600/2.45e6
        swme_w = max(0.0, met*(1-LS['latent_fraction'])+e_w+env); fw_h = swme_w*3600/2.45e6
        need = dict(o2_kg=round((o2_h+leak)*t+rep, 3), feedwater_kg=round(fw_h*t, 2), energy_wh=round(e_w*t, 0))
        dur = dict(o2_h=round((o2p-rep)/(o2_h+leak), 2), feedwater_h=round(LS['feedwater_kg']/fw_h, 2) if fw_h else 99.0,
                   battery_h=round(bat/e_w, 2))
        cases[nm] = dict(metabolic_w=met, environment_w=env, leak_kg_h=leak, o2_kg_h=round(o2_h, 4), co2_kg_h=round(co2_h, 4),
                         vapour_kg_h=round(vap_h, 3), swme_load_w=round(swme_w, 1), feedwater_kg_h=round(fw_h, 3), need_for_nominal_plus_reserve=need,
                         duration_h=dur, limiting=min(dur, key=dur.get), duration_limit_h=min(dur.values()), meets_target=min(dur.values()) >= t)
    # emergency: swing bed or fan lost, open-loop purge through the helmet at the flow that holds ppCO2 at the limit (high metabolic case)
    co2_mol_h = cases['high']['co2_kg_h']/0.04401; frac = LS['purge']['ppco2_limit_kpa']/LS['suit_pressure_kpa']
    purge_kg_h = co2_mol_h/frac*0.0319988; purge_min = o2s/purge_kg_h*60
    peak = dict(peak_w=LS['peak_w'], o2_kg_h=round(LS['peak_w']*3600/14.1e6, 3), swme_load_w=round(LS['peak_w']*(1-LS['latent_fraction'])+e_w, 0),
                note='15 min peaks are inside the nominal profile; the SWME and fan are sized for the peak load')
    sens = {f'metabolic_{w:.0f}w': round((o2p-rep)/(w*3600/14.1e6+LS['leak_kg_h'][1]), 2) for w in (150, 200, 250, 300, 350, 400)}
    return dict(status='PROVISIONAL design targets (data/eva_suit.toml [life_support]); not IGNITION canon, not a qualification',
                target_h=dict(nominal=LS['nominal_h'], reserve=LS['reserve_h'], emergency_return_min=LS['emergency_return_min']),
                stores=dict(o2_primary_usable_kg=round(o2p, 3), o2_secondary_usable_kg=round(o2s, 3), feedwater_kg=LS['feedwater_kg'],
                            battery_usable_wh=round(bat, 0), repress_o2_kg=round(rep, 4), suit_pressure_kpa=LS['suit_pressure_kpa']),
                electronics_w=round(e_w, 1), cases=cases, peak=peak,
                emergency=dict(purge_kg_h=round(purge_kg_h, 3), purge_minutes=round(purge_min, 1), meets=purge_min >= LS['emergency_return_min'],
                               ppco2_limit_kpa=LS['purge']['ppco2_limit_kpa']),
                o2_duration_sensitivity_h=sens, heat_rejection_nominal_w=cases['nominal']['swme_load_w'],
                consumable_mass_kg=round(o2p/LS['o2']['usable']+o2s/LS['o2']['usable']+LS['feedwater_kg'], 2),
                separation='breathing O2 and propulsion N2 have separate vessels, regulators and manifolds; no shared line or cross-connect',
                monitoring=LS['monitoring'], plumbing=LS['plumbing'],
                limits='steady-state rates; no transient thermal model, no CO2 bed sizing or humidity condensation model; suit pressure EVA-004 OPEN')


MODULE_BATTERY_WH = 1000.0


def drone_inertia(m=None, size=None):
    """Principal inertias (kg m^2) of the drone as a uniform slab of its stowed bounding box (a conservative low estimate)."""
    m = m or budget()['drone_wet_kg']; x, y, z = size or (.468, .548, .197)
    return (m/12*(y*y+z*z), m/12*(x*x+z*z), m/12*(x*x+y*y))


def near_suit_faults(near, com, mass=None, inertia=None, tagged=None):
    """Staged near-suit procedure against every credible single failure. near: [(pos, e)] the drone keeps live within proximity_m of a
    suit; tagged: optional [(name, pos, e, cluster)] of the same nozzles. Stages and what each needs:
      approach  0.50-0.12 m at <= approach_speed: all 12 axes (control), else abort
      braking   approach_speed -> PROP approach_speed_max over 0.12-0.05 m: +Fz >= margin x m a (fail-safe: the capture tongue takes the
                undecelerated contact energy, which must stay inside capture_energy_j)
      alignment hold at 0.05 m: every torque axis >= margin x I alpha to null the tip-off rate inside align_tol, lateral forces both ways
      capture   last 0.02 m coasting, thrusters off: no authority needed, contact energy 1/2 m v^2 at approach_speed_max
      abort / retreat: stop from approach_speed inside the gap to 0.05 m, then back off at retreat_speed: +Fz and attitude hold
    Single failures: each nozzle failed closed (valve or driver; dual-seat valves make a failed-open nozzle a double failure, bounded
    below), one cluster latch leg failed closed (the parallel leg keeps the cluster fed). Returns the per-stage worst case."""
    ns = PROP['near_suit']; m = mass or budget()['drone_wet_kg']; I = inertia or drone_inertia(m); k = ns['control_margin']
    d_brake = ns['approach_m'][1]-ns['brake_to_m']; v0 = ns['approach_speed_m_s']; v1 = PROP['approach_speed_max_m_s']
    f_brake = m*(v0*v0-v1*v1)/(2*d_brake)
    th = math.radians(ns['align_tol_deg']); w = math.radians(ns['tipoff_deg_s']); alpha = w*w/(2*th); t_need = max(I)*alpha
    f_lat = m*.02                                                            # 0.02 m/s^2 lateral trim
    req = {'approach': {ax: (f_lat if ax[1] == 'F' else t_need) for ax in [s+a for a in AXES for s in '+-']},
           'braking': {'+Fz': f_brake},
           'alignment': {**{s+a: t_need for a in ('Tx', 'Ty', 'Tz') for s in '+-'}, **{s+a: f_lat for a in ('Fx', 'Fy') for s in '+-'}},
           'capture': {},
           'abort_retreat': {'+Fz': f_brake, **{s+a: t_need for a in ('Tx', 'Ty', 'Tz') for s in '+-'}}}
    def judge(a):
        out = {}
        for st, r in req.items():
            short = {ax: dict(need=round(v*k, 3), have=a[ax]['max']) for ax, v in r.items() if not a[ax]['ok'] or a[ax]['max'] < v*k}
            out[st] = dict(ok=not short, short=short)
        return out
    base = authority(near, THRUST_N, com); cases = {'none': judge(base)}
    for i in range(len(near)):
        a = authority([n for j, n in enumerate(near) if j != i], THRUST_N, com)
        cases[f'closed:{tagged[i][0] if tagged else i}'] = judge(a)
    worst = {st: all(c[st]['ok'] for c in cases.values()) for st in req}
    failed = {nm: [st for st, v in c.items() if not v['ok']] for nm, c in cases.items() if any(not v['ok'] for v in c.values())}
    # double-fault bound: one nozzle stuck on for detect_s before the cluster latch isolates it (both seats failed open)
    cols = wrench_matrix(near, THRUST_N, com); t = ns['detect_s']
    dv = max(math.hypot(*c[:3]) for c in cols)*t/m; suitward = max(-c[2] for c in cols)*t/m
    rot = max(max(abs(c[3])/I[0], abs(c[4])/I[1], abs(c[5])/I[2]) for c in cols)
    e_lost_brake = .5*m*v0*v0; e_capture = .5*m*v1*v1; e_double = .5*m*(v1+max(0.0, suitward))**2
    ve = P['isp_s']*G0; dv_proc = 2*v0+2*v1+2*ns['retreat_speed_m_s']+.05; gas = m*dv_proc*3.0/ve
    return dict(mass_kg=round(m, 2), inertia_kg_m2=[round(v, 3) for v in I], live_nozzles=len(near),
                requirements=dict(brake_force_n=round(f_brake, 3), torque_nm=round(t_need, 4), lateral_n=round(f_lat, 3), margin=k,
                                  braking_distance_m=round(d_brake, 3), tipoff_deg_s=ns['tipoff_deg_s'], align_tol_deg=ns['align_tol_deg']),
                authority=base, cases=cases, stage_ok_all_single_failures=worst, failures_breaking_a_stage=failed,
                energy_j=dict(capture=round(e_capture, 4), braking_lost=round(e_lost_brake, 4), double_fault_on=round(e_double, 4),
                              capture_capacity=ns['capture_energy_j'],
                              ok=max(e_capture, e_lost_brake) <= ns['capture_energy_j']),
                double_fault_bound=dict(detect_s=t, dv_m_s=round(dv, 4), suitward_dv_m_s=round(suitward, 4), spin_deg_s=round(math.degrees(rot*t), 2),
                                        angle_deg=round(math.degrees(.5*rot*t*t), 2), gas_g=round(THRUST_N/ve*t*1000, 2)),
                propellant=dict(procedure_dv_m_s=round(dv_proc, 3), allocation_factor=3.0, gas_kg=round(gas, 4),
                                usable_kg=budget()['drone_vessels']['usable_kg']),
                limits='rigid-body, steady thrust, no plume interaction forces, no sensor or navigation error model; latch and manifold rupture '
                       'are design-for-minimum-risk items, not covered by fault tolerance')


def structure(arm_reach=None):
    """Preliminary analytical structural assessment (limit loads, factor of safety, closed-form sections; no FE, no test) of the dock,
    hull anchor, arm roots, tool couplings and the emergency release. Ratings in data/eva_drone.toml [anchor]."""
    S = ANCHOR['structure']; fos = S['fos_ultimate']; b = budget(); md = b['drone_wet_kg']; g = G0
    lay = dock_layout(); span = lay['latch_y'][0]-lay['latch_y'][1]; com_h = .07       # drone CoM height above the dock plane
    al = arm_loads(); armB = al['B']['tip_force_n']*al['B']['reach_m']; armA = al['A']['tip_force_n']*al['A']['reach_m']
    dock_cases = dict(kick=S['kick_n']*S['kick_lever_m'], burn=md*g*S['burn_g']*com_h, crew_push=md*S['crew_push_n']/b['docked_kg']*com_h,
                      arm_B_tip=armB, arm_A_tip=armA, driver_reaction=5.0)
    pull_cases = dict(kick=S['kick_n'], burn=md*g*S['burn_g'], anchor_gripper=300.0, crew_push=md*S['crew_push_n']/b['docked_kg'])
    Mlim = max(dock_cases.values()); Plim = max(pull_cases.values())
    bolt_a = S['bolt_section_m'][0]*S['bolt_section_m'][1]; bolt_cap = bolt_a*S['bolt_shear_mpa']*1e6
    bolt_load = Mlim*fos/span/2+Plim*fos/4                                    # moment couple over two bolts per row + an even pull share
    def link(arm):
        D = arm['link_m']; d = D-2*S['link_wall_m']; Z = math.pi*(D**4-d**4)/(32*D); M = arm['tip_force_n']*al['A' if arm is ARMS['A'] else 'B']['reach_m']
        return dict(root_moment_nm=round(M, 1), section_modulus_cm3=round(Z*1e6, 3), stress_mpa=round(M*fos/Z/1e6, 1),
                    margin=round(S['link_yield_mpa']/(M*fos/Z/1e6)-1, 2))
    r_pin = COUPLING['outer_d_m']/2*.8; m_sep = COUPLING['preload_n']*r_pin
    tl = {t['key']: t['length_m'] for t in TOOLS}
    couple = {K: dict(tip_n=ARMS[K]['tip_force_n'], lever_m=tl[t], moment_nm=round(ARMS[K]['tip_force_n']*tl[t], 2),
                      gap_opening_moment_nm=round(m_sep, 2), margin=round(m_sep/(ARMS[K]['tip_force_n']*tl[t]*fos)-1, 2))
              for K, t in (('A', 'precision_gripper'), ('B', 'utility_gripper'))}
    anchor_side = dict(gripper_anchor_pull_n=300.0, max_off_axis_deg=round(math.degrees(math.asin(min(1.0, m_sep/fos/(300.0*tl['utility_gripper'])))), 1),
                       note='the 300 N anchor-gripper rating holds for loads within this angle of the tool axis; beyond it the GU-SIF-S '
                            'preload (fleet standard, unchanged) opens the flange: anchored work uses the keel socket instead')
    release = dict(unloaded_n=round(4*S['release_spring_n']/S['release_advantage'], 1),
                   loaded_n=round((4*S['release_spring_n']+S['release_friction']*Mlim/span*2)/S['release_advantage'], 1), advantage=S['release_advantage'],
                   glove_limit_n=S['glove_pull_n'])
    release['ok'] = release['loaded_n'] <= S['glove_pull_n']
    return dict(status='PRELIMINARY analytical estimate: limit loads x FoS, closed-form sections; no FE, no test, not a qualification',
                fos_ultimate=fos, dock=dict(moment_cases_nm={k: round(v, 1) for k, v in dock_cases.items()}, limit_moment_nm=round(Mlim, 1),
                                            rating_nm=ANCHOR['latch_moment_nm'], ok=Mlim*fos <= ANCHOR['latch_moment_nm'],
                                            pull_cases_n={k: round(v, 1) for k, v in pull_cases.items()}, limit_pull_n=round(Plim, 1),
                                            pull_rating_n=ANCHOR['latch_pull_n'], pull_ok=Plim*fos <= ANCHOR['latch_pull_n'],
                                            bolt_ultimate_load_n=round(bolt_load, 0), bolt_shear_capacity_n=round(bolt_cap, 0),
                                            bolt_margin=round(bolt_cap/bolt_load-1, 1), latch_span_m=round(span, 3)),
                anchor=dict(same_interface='the hull service socket copies the suit channel, so the dock figures apply'),
                arm_roots={K: link(ARMS[K]) for K in ARMS}, couplings=couple, anchor_gripper=anchor_side, release=release,
                unknowns='channel-wall bearing, module-to-cuirass mount and composite shell laminates need FE and test; the moment reaches the '
                         'wearer only through the hard torso')


def arm_loads():
    """Static joint torques at full reach for the rated tip force (actuator sizing check)."""
    out = {}
    longest = max(t['length_m'] for t in TOOLS if t['modelled'])
    for k, a in ARMS.items():
        reach = a['l_upper_m']+a['l_fore_m']+a['l_wrist_m']+longest
        out[k] = dict(role=a['role'], reach_m=round(reach, 3), tip_force_n=a['tip_force_n'],
                      shoulder_torque_nm=round(a['tip_force_n']*reach, 1), elbow_torque_nm=round(a['tip_force_n']*(reach-a['l_upper_m']), 1),
                      wrist_torque_nm=round(a['tip_force_n']*(a['l_wrist_m']+.08), 2),
                      actuator='strain-wave (harmonic) joint drives, 40-60 mm frame: about 20-45 N m peak each, back-drivable brake off')
    return out


def reaction_study(free_force_n, free_torque_nm, drone_wet_kg):
    """What the drone may do free-flying versus anchored: a tool load must be cancelled by the RCS or the drone accelerates; anchored, the
    keel latch carries it into the structure."""
    out = dict(free_flight=dict(max_steady_tool_force_n=round(free_force_n, 1), max_steady_tool_torque_nm=round(free_torque_nm, 2),
                                note='steady-state limit while the RCS holds station; the 0.5-5 N m driver range exceeds it, so torqued '
                                     'fasteners need anchoring'))
    for tq in (0.5, 2.0, 5.0):
        alpha = tq/(drone_wet_kg*0.032)                  # I ~ m * 0.032 m^2 (0.48 x 0.48 x 0.12 m slab)
        out[f'unanchored_{tq}nm'] = dict(spin_up_deg_s_after_1s=round(math.degrees(alpha), 1), rcs_can_hold=tq <= free_torque_nm)
    out['anchored'] = dict(dock_latch_pull_rating_n=ANCHOR['latch_pull_n'], dock_latch_moment_rating_nm=ANCHOR['latch_moment_nm'],
                           note='the keel locks into a hull service socket that copies the suit channel; the 5 N m driver reaction and '
                                '60 N tip load are far inside the rating (ratings PROTOTYPE)')
    return out


def docked_arm_loads(lever_m, force_n):
    """Docked-arm assistance: a tool force at `lever_m` from the suit's spine is reacted through the dock into the astronaut. Returns the
    moment on the dock and on the astronaut's torso, and the angular acceleration of a free-floating suited crew member (I ~ 15 kg m^2
    about a transverse axis, a 1.8 m body of about 175 kg docked)."""
    m = force_n*lever_m; i_body = 15.0
    return dict(force_n=force_n, lever_m=lever_m, dock_moment_nm=round(m, 2), free_body_spin_deg_s2=round(math.degrees(m/i_body), 2),
                within_dock_rating=m <= ANCHOR['latch_moment_nm'])


def study(drone_local=None, docked=None, pc=None, body_com=None, proximity=None, module_l=None):
    """drone_local: dict(nozzles=[(name, pos, e, tag, inh)], com=(x, y, z)) in the drone frame; docked: dict(suit_nozzles=[(name, pos, e)],
    drone_nozzles=[(name, pos, e, inh)], drone_centre=(...), drone_com_world=(...)) in the suit world; proximity: the [(pos, e)] the drone
    keeps live within PROP['proximity_m'] of a suit. Without them only the budgets are returned."""
    b = budget()
    out = dict(budget=b, life_support=life_support_volume(module_l), life_support_budget=life_support_budget(), structure=structure(), arms=arm_loads(), coupling=COUPLING,
               tools=[{k: t[k] for k in ('key', 'modelled', 'mass_kg', 'function')} for t in TOOLS])
    if drone_local:
        com = drone_local['com']; noz = [(p, e) for _, p, e, _, _ in drone_local['nozzles']]
        a = authority(noz, THRUST_N, com); out['authority_drone_free'] = a
        fmin = min(v['max'] for k, v in a.items() if k[1] == 'F'); tmin = min(v['max'] for k, v in a.items() if k[1] == 'T')
        out['reaction'] = reaction_study(fmin, tmin, b['drone_wet_kg'])
        out['single_failure_drone_free'] = single_failure([noz], [THRUST_N], com)
        out['drone_nozzles'] = len(noz); out['drone_inhibited_when_docked'] = sum(1 for n in drone_local['nozzles'] if n[4])
        if proximity is not None:
            out['authority_drone_proximity'] = authority(proximity, THRUST_N, com)
            out['single_failure_drone_proximity'] = single_failure([proximity], [THRUST_N], com)
            out['near_suit_faults'] = near_suit_faults(proximity, com, b['drone_wet_kg'])
    if docked:
        dcen = docked['drone_centre']; pcv = pc or (0.0, 0.2, 1.27)
        crew = (MASSES['crew_kg']+MASSES['suit_kg'], body_com or (0.0, 0.0, 1.03))
        pack = (MASSES['plss_kg']+MASSES['reserve_hw_kg']+b['suit_reserve']['n2_kg'], pcv)
        dro = (b['drone_wet_kg'], docked.get('drone_com_world', dcen))
        com_d = mass_centre([crew, pack, dro]); com_s = mass_centre([crew, pack])
        sn = [(p, e) for _, p, e in docked['suit_nozzles']]; dn = [(p, e) for _, p, e, inh in docked['drone_nozzles'] if not inh]
        # one propulsion system at a time: docked, the suit reserve is isolated and the drone's live set flies the pair
        cols = wrench_matrix(dn, THRUST_N, com_d)
        out['com_docked'] = [round(v, 3) for v in com_d]; out['com_suit'] = [round(v, 3) for v in com_s]
        out['com_shift_vs_suit_m'] = round(math.dist(com_d, com_s), 3)
        out['authority_docked'] = authority_cols(cols)
        out['authority_suit_reserve'] = authority(sn, THRUST['suit_n'], com_s)
        out['single_failure_docked'] = single_failure([dn], [THRUST_N], com_d)
        out['single_failure_suit_reserve'] = single_failure([sn], [THRUST['suit_n']], com_s)
        up = sum(-THRUST_N*e[2] for p, e in dn if e[2] < 0)
        out['burnbrow'] = burnbrow(b['docked_kg'], up)
    return out


if __name__ == '__main__':
    print(json.dumps(study(), indent=1))
