"""EVA Operations runtime package (EVA-OPS-001, docs/EVA_OPERATIONS.md): data/simulations/wf_eva_ops.json for the Godot EVA scene.

Standard library only. It gathers, in Godot axes, everything the interactive EVA needs and computes nothing the canonical modules already
compute: masses, gas, tanks, delta-v and drone inertia from eva_system.py; the nozzle layout and mass centres the system check used
(references/p1_eva_system.json `runtime_layout`, written by validation/eva_system.py from the built sockets); the Brow, truss and hull
from forward_shield.py and eva_route.py (shared formulas, never the visual mesh); hazards from the rig proxies and anchors; the
RC-1 cartridge, station, presets, rules and assist gains from data/eva_ops.toml. Values the EVA system leaves PROTOTYPE stay PROTOTYPE;
the suited crew inertia is a box estimate made here and labelled so.

    python3 src/wayfarer/eva_ops.py            # writes data/simulations/wf_eva_ops.json and prints the delta-v parity line
    python3 src/wayfarer/eva_ops.py --check    # exits 1 if the committed file differs from a fresh build

Axes: Godot (x, y, z) = Blender (x, z, -y), for the ship (vehicle frame, +X bow) and for both bodies. Suit body frame: the astronaut
faces +Z, +Y up, +X left, origin between the feet. Drone body frame: nose -Z, dorsal +Y, dock face -Y, +X left. Positions in a body
are measured from that body's mass centre.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import tomllib

import eva_route
import eva_system as ev
import forward_shield
import spec

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/simulations/wf_eva_ops.json'
LAYOUT = ROOT/'references/p1_eva_system.json'


def g(p):
    """Blender (x, y, z) -> Godot (x, z, -y)."""
    return [round(p[0], 5), round(p[2], 5), round(-p[1], 5)]


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def box_inertia(m, size):
    x, y, z = size
    return [round(m/12*(y*y+z*z), 4), round(m/12*(x*x+z*z), 4), round(m/12*(x*x+y*y), 4)]


def cartridge(c):
    v = ev.DRONE['vessels']; spec_ = dict(n=1, outer_d_m=v['outer_d_m'], length_m=c['vessel_length_m'], wall_m=v['wall_m'])
    t = ev.tank(spec_)
    return dict(c, volume_l=t['volume_l'], n2_kg=t['n2_kg'], usable_kg=t['usable_kg'], wet_kg=round(c['hardware_kg']+t['n2_kg'], 3),
                vessel=spec_, status='PROTOTYPE accessory (data/eva_ops.toml [cartridge]); the canonical suit and drone are unchanged')


def bodies(layout):
    """Suit and drone in Godot body frames from the built layout (Blender suit frame / drone LOCAL frame)."""
    b = ev.budget(); M = ev.MASSES
    crew_kg = M['crew_kg']+M['suit_kg']; pack_kg = M['plss_kg']+M['reserve_hw_kg']+b['suit_reserve']['n2_kg']
    com_s = ev.mass_centre([(crew_kg, tuple(layout['suit_body_com'])), (pack_kg, tuple(layout['suit_pack_centre']))])
    cs = g(com_s); cd = g(layout['drone_com_local'])
    suit_dry = M['crew_kg']+M['suit_kg']+M['plss_kg']+M['reserve_hw_kg']
    suit = dict(id='WAYFARER_EVA_Y155', status='PROTOTYPE, NOT CERTIFIED', dry_kg=round(suit_dry, 3), com_suit_frame=cs,
                inertia_kg_m2=box_inertia(b['suited_crew_wet_kg'], (0.60, 1.78, 0.56)),
                inertia_status='PROTOTYPE estimate made here: uniform box 0.60 x 1.78 x 0.56 m (width, height, depth) of the suited crew; '
                               'no measured suited-crew inertia exists',
                thrust_n=ev.THRUST['suit_n'], reserve=dict(b['suit_reserve'], feed_pa=ev.P['reserve_feed_pressure_pa']),
                nozzles=[dict(name=n['name'], p=[round(v, 5) for v in sub(g(n['p']), cs)], e=g(n['e'])) for n in layout['suit_nozzles']])
    drone = dict(id='WAYFARER_EVA_DRONE', status='PROTOTYPE', dry_kg=b['drone_dry_kg'], com_local=cd,
                 inertia_kg_m2=[round(v, 4) for v in (lambda I: (I[0], I[2], I[1]))(ev.drone_inertia(b['drone_wet_kg']))],
                 inertia_status='eva_system.drone_inertia: uniform slab of the stowed bounding box (conservative low estimate)',
                 thrust_n=ev.THRUST_N, vessels=dict(b['drone_vessels'], feed_pa=ev.P['feed_pressure_pa']), proximity_m=ev.PROP['proximity_m'],
                 near_suit=ev.PROP['near_suit'], approach_speed_max_m_s=ev.PROP['approach_speed_max_m_s'],
                 nozzles=[dict(name=n['name'], p=[round(v, 5) for v in sub(g(n['p']), cd)], e=g(n['e']), inhibit_near_suit=n['inhibit_near_suit'])
                          for n in layout['drone_nozzles']],
                 arms={K: dict(role=a['role'], shoulder_local=g((a['side']*a['shoulder_x_m'], a['shoulder_y_m'], 0.0)),
                               reach_m=round(a['l_upper_m']+a['l_fore_m']+a['l_wrist_m'], 3), tip_force_n=a['tip_force_n']) for K, a in ev.ARMS.items()})
    # the docked drone pose in the suit frame: Blender 4x4 (suit frame <- drone LOCAL) -> Godot basis columns and origin
    Mb = layout['dock_matrix']; C = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]          # Godot = C @ Blender
    R = [[Mb[i][j] for j in range(3)] for i in range(3)]
    Rg = [[sum(C[i][k]*R[k][l]*C[j][l] for k in range(3) for l in range(3)) for j in range(3)] for i in range(3)]   # C R C^T
    dock = dict(origin=g([Mb[i][3] for i in range(3)]), basis_columns=[[round(Rg[i][j], 6) for i in range(3)] for j in range(3)],
                note='drone body frame (LOCAL) in the suit frame while docked, from SOCKET_DRONE_DOCK of the built system scene')
    return suit, drone, dock


def alloc_table(nozzles, thrust, com, iters=4000):
    """Per signed pure axis, the valve duty cycles that give a unit wrench along it (1 N, or 0.3 N m as in eva_system.authority_cols), by
    the canonical non-negative least squares (eva_system.nnls). Godot body frame; positions already measured from the mass centre `com`.
    The runtime mixes these columns linearly and scales the mix down if any duty passes 1 (the allocation keeps its direction)."""
    cols = ev.wrench_matrix([(tuple(n['p']), tuple(n['e'])) for n in nozzles], thrust, com)
    out = {}
    for i, nm in enumerate(ev.AXES):
        for sg in (1, -1):
            unit = 1.0 if i < 3 else 0.3; target = [0.0]*6; target[i] = sg*unit
            x, err = ev.nnls(cols, target, iters); peak = max(x) if x else 0.0; ok = err < 0.02*unit and peak > 0
            out[('+' if sg > 0 else '-')+nm] = dict(ok=ok, max=round(unit/peak, 4) if ok else 0.0, duty_per_unit=[round(v/unit, 6) for v in x] if ok else [0.0]*len(x),
                                                   residual=round(err, 5))
    return out


def tables(suit, drone, dock):
    """The four flight configurations of the canonical study, each with its own nozzle set and mass centre (Godot body frames)."""
    d_all = drone['nozzles']; d_near = [n for n in d_all if not n['inhibit_near_suit']]
    b = ev.budget(); m_s = b['suited_crew_wet_kg']; m_d = b['drone_wet_kg']
    B = dock['basis_columns']; o = dock['origin']; cs = suit['com_suit_frame']
    to_suit = lambda v: [B[0][i]*v[0]+B[1][i]*v[1]+B[2][i]*v[2] for i in range(3)]
    # docked: drone nozzles (live set) in the suit frame measured from the suit's mass centre, then the pair's mass centre
    cd_suit = [o[i]+to_suit(drone['com_local'])[i]-cs[i] for i in range(3)]          # drone CoM from the suit CoM, suit frame
    pair = [cd_suit[i]*m_d/(m_s+m_d) for i in range(3)]                             # pair CoM from the suit CoM
    docked = [dict(name=n['name'], p=[round(o[i]+to_suit([n['p'][k]+drone['com_local'][k] for k in range(3)])[i]-cs[i]-pair[i], 5) for i in range(3)],
                   e=[round(v, 6) for v in to_suit(n['e'])]) for n in d_near]
    z = (0.0, 0.0, 0.0)
    return dict(
        drone_free=dict(nozzles=[n['name'] for n in d_all], axes=alloc_table(d_all, ev.THRUST_N, z), thrust_n=ev.THRUST_N),
        drone_near_suit=dict(nozzles=[n['name'] for n in d_near], axes=alloc_table(d_near, ev.THRUST_N, z), thrust_n=ev.THRUST_N),
        docked=dict(nozzles=[n['name'] for n in docked], axes=alloc_table(docked, ev.THRUST_N, z), thrust_n=ev.THRUST_N, nozzle_layout=docked,
                    pair_com_from_suit_com=[round(v, 5) for v in pair], drone_com_from_suit_com=[round(v, 5) for v in cd_suit],
                    feed='drone vessels (suit reserve isolated: one propulsion system at a time)'),
        suit_reserve=dict(nozzles=[n['name'] for n in suit['nozzles']], axes=alloc_table(suit['nozzles'], ev.THRUST['suit_n'], z), thrust_n=ev.THRUST['suit_n'],
                          feed='dock line first (drone or RC-1 cartridge, check valves), then the reserve'))


def ship(s):
    """Brow, truss, body and hull route in Godot axes from the shared formulas."""
    st = forward_shield.stations(s); p = forward_shield.prototype(s); R = st['shield_r']
    prof = [0.0, st['hub_opening_r'], st['cone_r']]+[st['cone_r']+(R-st['cone_r'])*k/8 for k in range(1, 9)]
    face = [[round(r, 4), round(forward_shield.face_x_at(s, r), 4), round(forward_shield.skin_aft_at(s, r), 4)] for r in prof]
    t = forward_shield.truss(s); segs = []
    for sp in t['spokes']:
        for role, pts in sp['members']:
            if f"Truss_Spoke_{sp['index']:02}_{role}" in t['removed']:
                continue
            for a, b in zip(pts, pts[1:]):
                segs.append([g(a), g(b)])
    for a in t['alternate']:
        for A, B in zip(a['pts'], a['pts'][1:]):
            segs.append([g(A), g(B)])
    fixtures = []
    for f in forward_shield.brow_panel_fixtures(s):
        v = f['vertices']
        for k in range(0, len(v), 48):                    # one fixture: post (2 x 12) then flange (2 x 12); the grip is the flange's far ring
            ring = v[k+36:k+48]; c = [sum(q[i] for q in ring)/12 for i in range(3)]
            fixtures.append(g(c))
    rt = eva_route.runtime(ROOT)
    route = {k: rt[k] for k in ('mode', 'modes', 'flight', 'configuration', 'rail_up', 'hatch', 'runs', 'rail_radius_m', 'rail_azimuth_deg', 'anchors',
                                'collider', 'tether_reach_m', 'tether_reach_status', 'ring_sweep', 'suit_sweep_radius_m')}
    route['holds'] = {k: dict(p=h['p'], status=h['status'], flight=h['flight']) for k, h in rt['holds'].items()}
    return dict(axes='Godot (x, z, -y) of the vehicle frame; radii about the ship axis +X',
                shield=dict(radius_m=R, face_profile_r_xface_xskinaft=face, truss_aft_rim_x=st['truss_aft'], truss_aft_hub_x=st['truss_aft_hub'],
                            spine_end_x=st['spine_end'], hub_r=st['hub_r'], lance=dict(x0=st['face'], x1=st['lance_tip'], r0=p['lance_base_radius_m'],
                                                                                     r1=p['lance_tip_radius_m']),
                            truss_member_radius_m=t['member_radius'], truss_segments=segs, fixtures=fixtures,
                            fixture_status='S04 Brow panel handling fixtures on the skin aft face (forward_shield.brow_panel_fixtures, PROTOTYPE)',
                            service_rule='Brow service only from the protected aft side (14 regenerative_brow, 50!AG-A02); the ram face is never a work site'),
                route=route)


def hazards(rig, sh, route):
    """Keep-out volumes (Godot axes): from the rig proxies and anchors and the route's ring sweep. Warning-and-recovery only."""
    A = {a['name']: a for a in rig['anchors']}; out = []
    for p in rig['proxies']:
        n = p['name']
        if p['shape'] == 'box' and n.startswith('WF_SIMPROXY_RADIATOR'):
            a = A[p['anchor']]; c = p['center_m']
            w = [a['position_m'][i]+c[0]*a['axis'][i]+c[1]*a['side'][i]+c[2]*a['up'][i] for i in range(3)]
            out.append(dict(id=n.replace('WF_SIMPROXY_', ''), kind='box', centre=g(w), axis=g(a['axis']), side=g(a['side']), up=g(a['up']),
                            size=p['size_m'], label='Radiator blade: hot surface, do not approach'))
    rs = route['ring_sweep']
    out.append(dict(id='RING_SWEEP', kind='annulus', x0=rs['x0'], x1=rs['x1'], r_in=6.5, r_out=rs['r_outer'],
                    label='Habitat rings: rotating structure, keep out'))
    for a in rig['anchors']:
        if a['name'].startswith('WF_SIM_EYE_FACET'):
            out.append(dict(id=a['name'].replace('WF_SIM_', ''), kind='sphere', centre=g(a['position_m']), r=4.0,
                            label='EYE optics: sensitive, keep plumes and hands off'))
    L = sh['shield']['lance']
    out.append(dict(id='DUST_LANCE', kind='cylinder_x', x0=L['x0'], x1=L['x1'], r=L['r0']+1.0, label='Dust Lance and field zone: keep out'))
    out.append(dict(id='RAM_FACE', kind='ahead_of_face', label='Brow ram face: exposed to incoming dust in flight; training simulation only',
                    operational=False))
    th = next(a for a in rig['anchors'] if a['name'] == 'WF_SIM_THRUST_CENTER')['position_m'][0]
    out.append(dict(id='DRIVE_PLUME', kind='behind_x', x=th-8.0, label='Drive exhaust: lethal, keep out'))
    return out


def build(root=ROOT, layout_path=LAYOUT):
    s = spec.load(root)[0]
    rep = json.loads(Path(layout_path).read_text()); layout = rep['runtime_layout']
    ops = tomllib.loads((root/'data/eva_ops.toml').read_text()); rig = json.loads((root/'data/simulations/wf_sim_rig.json').read_text())
    suit, drone, dock = bodies(layout); b = ev.budget(); sh = ship(s); alloc = tables(suit, drone, dock)
    modes = {}
    for k, m in ops['modes'].items():
        a_g = m['accel_g'] if 'accel_g' in m else rig['dynamics']['modes'][m['rig_mode']]['demo_ship_accel_g']
        modes[k] = dict(m, accel_g=a_g, source=('wf_sim_rig.json dynamics.modes.'+m['rig_mode']) if 'rig_mode' in m else 'eva_drone.toml gas.burn_g')
    return dict(contract='wf_eva_ops v1', status='PROTOTYPE / TRAINING SIMULATION', generated_by='src/wayfarer/eva_ops.py',
                sources=['data/eva_suit.toml', 'data/eva_drone.toml', 'src/wayfarer/eva_system.py', 'references/p1_eva_system.json runtime_layout',
                         'src/wayfarer/forward_shield.py', 'src/wayfarer/eva_route.py', 'data/simulations/wf_sim_rig.json', 'data/eva_ops.toml'],
                gas=dict(isp_s=ev.P['isp_s'], g0=ev.G0, ve_m_s=round(ev.P['isp_s']*ev.G0, 4), tank_pressure_pa=ev.P['tank_pressure_pa'],
                         usable_fraction=ev.P['usable_fraction'], n2_density_kg_m3=b['n2_density_kg_m3']),
                suit=suit, drone=drone, dock=dock, allocation=alloc, cartridge=cartridge(ops['cartridge']), station=ops['station'], modes=modes,
                rules=ops['rules'], assist=ops['assist'],
                budget={k: b[k] for k in ('drone_wet_kg', 'suited_crew_wet_kg', 'docked_kg', 'dv_drone_alone_m_s', 'dv_docked_drone_gas_m_s',
                                          'dv_suit_reserve_alone_m_s', 'total_impulse_drone_ns', 'total_impulse_reserve_ns')},
                ship=sh, hazards=hazards(rig, sh, sh['route']), standard_gravity_m_s2=rig['dynamics']['standard_gravity_m_s2'])


def dv(m0, mp, ve):
    return ve*math.log(m0/(m0-mp))


def parity(pkg):
    """Delta-v from the package's own masses and tanks (what the runtime integrates) against the canonical budget."""
    ve = pkg['gas']['ve_m_s']; s = pkg['suit']; d = pkg['drone']
    suit_wet = s['dry_kg']+s['reserve']['n2_kg']; drone_wet = d['dry_kg']+d['vessels']['n2_kg']
    got = dict(dv_drone_alone_m_s=dv(drone_wet, d['vessels']['usable_kg'], ve),
               dv_docked_drone_gas_m_s=dv(drone_wet+suit_wet, d['vessels']['usable_kg'], ve),
               dv_suit_reserve_alone_m_s=dv(suit_wet, s['reserve']['usable_kg'], ve))
    return {k: (round(v, 3), pkg['budget'][k]) for k, v in got.items()}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); ap.add_argument('--layout', type=Path, default=LAYOUT)
    ap.add_argument('--out', type=Path, default=OUT); a = ap.parse_args()
    text = json.dumps(build(ROOT, a.layout), indent=1)+'\n'
    if a.check:
        ok = a.out.exists() and a.out.read_text() == text
        print('WF_EVA_OPS', 'CURRENT' if ok else 'STALE'); sys.exit(0 if ok else 1)
    a.out.write_text(text); pkg = json.loads(text)
    print('WF_EVA_OPS', a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out, len(text), 'bytes', json.dumps(parity(pkg)))


if __name__ == '__main__':
    main()
