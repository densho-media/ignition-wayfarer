"""The guided-EVA exterior route and its hazard gates (EVA-001 in TODO, docs/EVA.md). Standard library only.

No exterior rail, anchor, hold fixture or EVA hatch geometry is released (14_HULL_SERVICE has none; 12A SP-51 rails are HIGH / STRUCTURE
OPEN), so per S&E 44!51 RUN-011 this is a labelled TRAINING SIMULATION: a PROTOTYPE rail on the stationary forward collar along the airlock's
azimuth, from the SP-11 fitting aft toward ring B and forward toward the shield. Nothing here is added to the vehicle; the runtime draws it.

Hazard gates fail closed (RUN-012, SIM-02, EVA-010/011/012/013/015/035/038): a hazard is measured from the built geometry where that is
geometry (distance to the ring-B sweep, line of sight to the blade faces, shield shadow), but its limit is the owner's; a limit that is
OPEN makes the gate UNKNOWN, and any UNKNOWN makes the point SIMULATION_ONLY. Nothing becomes GO by default. No thermal, dose or
debris quantity is computed here (C-001, EVA-034).

  python3 src/wayfarer/eva_route.py [--out <dir>]    writes <dir>/wf_eva.json (default: print a summary)
"""
import argparse
import json
import math
from pathlib import Path

import eva_suit
import forward_shield
import habitat_ring
import hull_geometry
import layout
import spec
import thermal_geometry

ROOT = Path(__file__).resolve().parents[2]


def radial(x, r, theta):
    return (x, r*math.cos(theta), r*math.sin(theta))


def godot(p):
    return [round(p[0], 4), round(p[2], 4), round(-p[1], 4)]


def body_radius(s, x):
    """The stationary body's outer radius at x: the hull skin where it is skinned, else the spine (the open rotor bay)."""
    for _, a, b in hull_geometry.intervals(s):
        if a <= x <= b:
            return hull_geometry.radius_at(s, x)
    return layout.spine_radius_at(s, x)


def collider(s, x0=94.0, x1=108.0, step=0.25):
    """PROTOTYPE collision proxy of the stationary body for the Godot EVA drift: its outer radius sampled along X from `body_radius`
    (the shared hull formulas, never the visual mesh), plus the interval starts where the radius jumps, and the Airlock_EVA fitting as a
    cylinder. Axis +X, radius about the ship axis. Nothing here is a released collision surface."""
    xs = {round(x0+i*step, 4) for i in range(int(round((x1-x0)/step))+1)}
    jumps = []
    for _, a, b in hull_geometry.intervals(s):
        for x in (a, b):
            if x0 <= x <= x1:
                xs.add(round(x, 4)); jumps.append(round(x, 4))
    fit = next(f for f in hull_geometry.service_fittings(s) if f['name'] == 'Airlock_EVA')
    return dict(status='PROTOTYPE collision proxy from the shared hull formulas (not the visual mesh)', axis='+X, radius about the ship axis',
                x0=x0, x1=x1, step_m=step, jump_x=sorted(jumps),
                samples=[[x, round(body_radius(s, x), 4)] for x in sorted(xs)],
                fitting=dict(name=fit['name'], x=round(fit['x'], 4), theta_deg=round(math.degrees(fit['theta']), 3), radius_m=fit['radius'],
                             r_inner=fit['r0'], r_outer=fit['r1'], status='PROTOTYPE fitting cylinder (SP-11 lock size OPEN, 14!6)'))


def blade_faces(s, n_x=16, n_r=6):
    """Sample points on each radiator blade (both faces emit, `radiators.emitting_faces`) with the blade's azimuth."""
    d = thermal_geometry.blade_of(s); r0, r1 = d['root_radius_m'], d['outer_radius_m']; x0, x1 = d['aft_x_m'], d['front_x_m']
    p = s['prototype']; out = []
    for k in range(s['radiators']['count']):
        phi = math.radians(p['radiator_phase_deg']+k*s['radiators']['separation_deg'])
        pts = [radial(x0+(x1-x0)*(i+.5)/n_x, r0+(r1-r0)*(j+.5)/n_r, phi) for i in range(n_x) for j in range(n_r)]
        out.append(dict(blade=k+1, azimuth_deg=round(math.degrees(phi), 1), points=pts))
    return out


def occluded(s, a, b, steps=32):
    """Whether the stationary body (hull skin or spine) blocks the segment a-b. The rings, spokes and fittings are not credited as
    shields: partial blockage is not a released exposure budget (fail closed)."""
    for i in range(1, steps):
        t = i/steps; p = tuple(a[k]+(b[k]-a[k])*t for k in range(3))
        if math.hypot(p[1], p[2]) < body_radius(s, p[0])-1e-6:
            return True
    return False


def blade_sight(s, p, faces):
    """Line of sight from p to each blade: the fraction of sample points visible and the nearest visible one (m). Geometry only."""
    out = []
    for f in faces:
        vis = [q for q in f['points'] if not occluded(s, p, q)]
        out.append(dict(blade=f['blade'], azimuth_deg=f['azimuth_deg'], visible_fraction=round(len(vis)/len(f['points']), 3),
                        nearest_visible_m=round(min(math.dist(p, q) for q in vis), 2) if vis else None))
    return out


def gate(id_, measured, unit, limit, status, source, note='', inputs=None, state=None):
    """One hazard gate. `status` is the training check (PASS / UNKNOWN / FAIL); `state` is EVA-049's vocabulary for the flight gate
    (UNKNOWN, HOLD, PROTOTYPE, VALIDATED): nothing here is ever VALIDATED. `inputs` lists what the release needs, with each input's status."""
    return dict(id=id_, measured=measured, unit=unit, limit=limit, status=status, source=source, note=note, inputs=inputs or [],
                state=state or ('HOLD' if status != 'FAIL' else 'HOLD'))


def view_factor_readback(s, p, faces):
    """DIAGNOSTIC READBACK for 45 H-05 (not a release): the view factor from a small sphere at p to the visible blade faces, summed over
    the samples (dF = cos(theta_blade) dA / (4 pi d^2), both faces radiate). A geometry readback for the owner's thermal model only; it
    never enters a gate (EVA-045: no fictional safe distance)."""
    d = thermal_geometry.blade_of(s); dA = (d['front_x_m']-d['aft_x_m'])*(d['outer_radius_m']-d['root_radius_m'])/(16*6); out = []
    for f in faces:
        phi = math.radians(f['azimuth_deg']); n = (0.0, -math.sin(phi), math.cos(phi)); F = 0.0
        for q in f['points']:
            if occluded(s, p, q):
                continue
            v = tuple(a-b for a, b in zip(p, q)); r2 = sum(x*x for x in v); c = abs(sum(a*b for a, b in zip(v, n)))/math.sqrt(r2)
            F += c*dA/(4*math.pi*r2)
        out.append(dict(blade=f['blade'], view_factor=round(F, 5)))
    return dict(status='DIAGNOSTIC READBACK (sphere model, not 45 H-05)', blades=out, total=round(sum(b['view_factor'] for b in out), 5))


def hazards(s, p, data, faces, suit_r):
    """The six hazard gates of one route point (vehicle frame; S&E 43 EVA-045..049, 45 H/O rows). `suit_r` is the suited body's swept
    radius about its hold point. Each gate fails closed: an OPEN limit makes it UNKNOWN for training and HOLD for flight."""
    tel = data['telemetry']; th = data['thermal_case']; cfg = s['configuration'][data['route']['configuration']]
    rc = habitat_ring.centers(s); half = habitat_ring.sweep_half(s)
    sweep_fwd = max(rc)+half
    ring_gap = round(p[0]-sweep_fwd-suit_r, 3)
    sight = blade_sight(s, p, faces); seen = [b for b in sight if b['visible_fraction'] > 0]
    sh = forward_shield.stations(s); shadow = math.hypot(p[1], p[2]) < sh['shield_r'] and p[0] < sh['skin_aft']
    inp = lambda *rows: [dict(id=i, status=st) for i, st in rows]
    thermal_inputs = [dict(id=k, value=v['value'], status=v['status'], source=v['source']) for k, v in th.items() if k != 'go_flag']
    out = [
        gate('drive', cfg['drive'], '', 'OFF', 'PASS' if cfg['drive'] == 'OFF' else 'FAIL',
             'S&E 43 EVA-011 (BASELINE SHIP CONFIG); 11!5', 'main propulsion OFF in the EVA configuration: necessary, not sufficient (drive OFF does not '
             'make the blades safe, EVA-045)', inp(('11!5 EVA config', 'WORKING')), state='PROTOTYPE'),
        gate('ring', ring_gap, 'm', tel['ring_keepout_m']['value'],
             'FAIL' if ring_gap <= 0 else ('UNKNOWN' if tel['ring_keepout_m']['value'] is None else
                                           ('PASS' if ring_gap >= tel['ring_keepout_m']['value'] else 'FAIL')),
             'S&E 43 EVA-015, EVA-046 (RELEASE HOLD); 45 O-05', f'static axial gap from the suited sweep (r {suit_r:.2f} m) to ring B\'s rotating sweep '
             f'(X {sweep_fwd:.2f} m); rings ROTATING at +/-4 rpm in EVA. A static gap alone is never a margin: tether sweep, tools, vibration, a damaged '
             'rotor and rescue are not modelled', inp(('ring_keepout_m', 'OPEN'), ('45 O-05 dynamic GO', 'OPEN'))),
        gate('thermal', [dict(b) for b in sight], '', th['go_flag']['value'],
             'UNKNOWN' if seen else 'PASS', 'S&E 43 EVA-010, EVA-035, EVA-045 (RELEASE HOLD); 45 H-01..H-13',
             'blade faces in line of sight; the blade temperature history after shutdown, view factor, suit area and absorptivity, cooling and '
             'return time are not released: no safe distance exists' if seen else 'no blade face visible past the stationary body',
             thermal_inputs),
        gate('debris', shadow, '', tel['debris_condition']['value'], 'UNKNOWN' if shadow else 'FAIL',
             'S&E 43 EVA-012, EVA-038, EVA-047; 14!13; 45 O-04',
             ('inside the forward-shield silhouette; ' if shadow else 'outside the shield silhouette; ')+'EVA at 0.016c relative dust is NO-GO; '
             'only protected DOCKED or verified very-low-relative-speed operations can be studied', inp(('debris_condition', 'OPEN'), ('45 O-04', 'OPEN'))),
        gate('radiation', None, '', tel['radiation_dose_budget']['value'], 'UNKNOWN', 'S&E 43 EVA-013, EVA-047; Technology 53!13; 45 O-04',
             'SPE forecast, dosimetry and a safe refuge return required; the suit is never credited as a refuge',
             inp(('radiation_dose_budget', 'OPEN'), ('45 O-04', 'OPEN'))),
        gate('tether_anchor', None, '', None, 'UNKNOWN', 'S&E 43 EVA-014, EVA-048; 44 SIM-03; 12A SP-51; 45 O-05, O-06',
             'no crew-rated anchor plan: the 1.5 m rail anchors are an animation/UI fixture; dual independent tethers are enforced by the trainer, '
             'their structural attachment and loads are unqualified', inp(('tether_length_m', 'OPEN'), ('SP-51 anchors', 'OPEN'), ('45 O-06', 'TRAINING ONLY'))),
    ]
    st = 'NO_GO' if any(g['status'] == 'FAIL' for g in out) else ('SIMULATION_ONLY' if any(g['status'] == 'UNKNOWN' for g in out) else 'GO')
    if st == 'GO':                                             # unreachable while any input is OPEN; a training route is never more than this
        st = 'SIMULATION_ONLY'
    return out, st


def flight_status(data, holds):
    """FLIGHT_EVA (EVA-049, 45 O-07): a separate state, LOCKED. It reads HOLD until the owners release every gate in writing; no software
    result can change it (EVA2-008)."""
    m = data['modes']['flight']
    gates = sorted({g['id'] for h in holds.values() for g in h['gates']})
    return dict(mode=m['id'], available=False, state='HOLD', lock=m['lock'],
                blocking=[g for g in gates if any(x['id'] == g and x['state'] != 'VALIDATED' for h in holds.values() for x in h['gates'])])


def route(s, data, suit_r=0.55):
    """The training route: the airlock's outer hatch, rail runs aft and forward on the collar, anchors, holds, gates and feed views."""
    r = data['route']; fit = next(f for f in hull_geometry.service_fittings(s) if f['name'] == 'Airlock_EVA')
    th = math.radians(r['rail_azimuth_deg']); xa, rad = fit['x'], fit['radius']
    rail_r = body_radius(s, xa)+r['rail_standoff_m']; clr = s['prototype']['mechanical_clearance_m']
    aft0, fwd0 = xa-rad-clr, xa+rad+clr                    # the rail starts one clearance off the fitting's tube
    runs = dict(aft=(aft0, r['aft_hold_x_m']), forward=(fwd0, r['forward_hold_x_m']))
    for name, (a, b) in runs.items():
        assert all(body_radius(s, x) > layout.spine_radius_at(s, x) for x in (a, b)), f'{name} rail leaves the forward collar'
    up = (0.0, math.cos(th), math.sin(th))
    anchors = []
    for name, (a, b) in runs.items():
        n = max(1, int(abs(b-a)//r['anchor_spacing_m'])); sgn = 1 if b > a else -1
        for i in range(n+1):
            x = a+sgn*min(abs(b-a), i*r['anchor_spacing_m'])
            anchors.append(dict(id=f'ANC_{name.upper()}_{i:02d}', run=name, x=round(x, 3), p=radial(x, rail_r, th)))
    hatch = radial(xa, fit['r1'], th)
    holds = dict(airlock=dict(x=xa, p=radial(xa, fit['r1']+.55, th)),
                 rail_mid=dict(x=round((aft0+r['aft_hold_x_m'])/2, 3), p=radial((aft0+r['aft_hold_x_m'])/2, rail_r+.55, th)),
                 aft_hold=dict(x=r['aft_hold_x_m'], p=radial(r['aft_hold_x_m'], rail_r+.55, th)),
                 forward_hold=dict(x=r['forward_hold_x_m'], p=radial(r['forward_hold_x_m'], rail_r+.55, th)))
    faces = blade_faces(s); worst = {}
    for k, h in holds.items():
        h['gates'], h['status'] = hazards(s, h['p'], data, faces, suit_r); worst[k] = h['status']
        h['flight'] = 'HOLD'; h['view_factor_readback'] = view_factor_readback(s, h['p'], faces)
    # the rail positions along X the runtime moves on: 1-D coordinate u = X (both runs share the airlock at X = xa)
    d = thermal_geometry.blade_of(s); sh = forward_shield.stations(s)
    feeds = dict(  # simulated remote views (EVA-030/031, RUN-015): presentation cameras, not crew positions
        ring_sweep=dict(eye=radial(r['aft_hold_x_m']+1.5, rail_r+2.2, th+.05), look=radial(max(habitat_ring.centers(s)), 26.0, th-.25),
                        label='Hold view aft: ring B (rotating) and its keep-out sweep'),
        radiator_feed=dict(eye=radial(d['front_x_m']-6.0, 9.0, math.radians(s['prototype']['radiator_phase_deg'])+.22),
                           look=radial(d['front_x_m']-60.0, 22.0, math.radians(s['prototype']['radiator_phase_deg'])),
                           label='CRAWLER CAMERA FEED (simulated): radiator blade 1 from its root rail'),
        drive_cutaway=dict(eye=radial(-70.0, 22.0, th), look=radial(-108.0, 0.0, th), label='REMOTE VIEW (simulated): drive section, nozzles aft'),
        forward_feed=dict(eye=(sh['lance_tip']+18.0, 12.0, 20.0), look=(sh['face'], 0.0, 0.0),
                          label='REMOTE CAMERA (simulated): Brow, Dust Lance and EYE from ahead; no person goes here'),
        suit_cutaway=dict(eye=None, look=None, label='Suit cutaway: layers and backpack'),
        tether_handoff=dict(eye=None, look=None, label='Tether handoff demonstration'),
        repress=dict(eye=None, look=None, label='Airlock repressurization'))
    chamber = dict(  # the simulated SP-11 chamber inside the solid PROTOTYPE fitting (no airlock interior is released, 14!6, EVA-007)
        axis_x=xa, theta_deg=r['rail_azimuth_deg'], r_inner=fit['r0'], r_outer=fit['r1'], fitting_radius_m=rad,
        status='SIMULATED: SP-11 lock size, doors and interior OPEN (14!6, 43 EVA-007, EVA-037)')
    return dict(mode=r['mode'], flight=flight_status(data, holds), configuration=r['configuration'], rail_azimuth_deg=r['rail_azimuth_deg'], rail_radius_m=round(rail_r, 3),
                up=up, hatch=hatch, runs={k: [round(a, 3), round(b, 3)] for k, (a, b) in runs.items()}, anchors=anchors, holds=holds,
                status=worst, feeds=feeds, chamber=chamber, suit_sweep_radius_m=suit_r,
                tether_reach_m=r['tether_reach_m'], tether_reach_status='PROTOTYPE gameplay tuning; tether_length_m OPEN (SIM-03)',
                ring_sweep=dict(x0=min(habitat_ring.centers(s))-habitat_ring.sweep_half(s), x1=max(habitat_ring.centers(s))+habitat_ring.sweep_half(s),
                                r_outer=s['habitat_ring']['sector_outer_radius_m']+.5),
                docking_corridors=[dict(name=f['name'], azimuth_deg=round(math.degrees(f['theta']), 1),
                                        separation_deg=round(abs((math.degrees(f['theta'])-r['rail_azimuth_deg']+180) % 360-180), 1))
                                   for f in hull_geometry.service_fittings(s) if f['name'].startswith('Dock_')])


def runtime(root=ROOT, suit_r=0.55, access=None, sp11=None):
    """wf_eva.json for Godot: the route in Godot axes plus the vehicle-frame values, the stations and the telemetry contract."""
    s = spec.load(root)[0]; data = eva_suit.load(root); rt = route(s, data, suit_r)
    G = lambda p: godot(p) if p is not None else None
    out = dict(contract='wf_eva v2', mode=rt['mode'], modes=data['modes'], flight=rt['flight'], reference_case=data['reference_case'],
               configuration=rt['configuration'], axes='Godot (x, z, -y) of the vehicle frame',
               suit=dict(id=data['suit']['id'], status=data['suit']['status'], certification=data['suit']['certification']),
               telemetry=eva_suit.telemetry_contract(data), stations=data['station'], rail_up=G(rt['up']), hatch=G(rt['hatch']),
               runs=rt['runs'], rail_radius_m=rt['rail_radius_m'], rail_azimuth_deg=rt['rail_azimuth_deg'],
               anchors=[dict(a, p=G(a['p'])) for a in rt['anchors']],
               holds={k: dict(h, p=G(h['p'])) for k, h in rt['holds'].items()}, status=rt['status'],
               feeds={k: dict(v, eye=G(v['eye']), look=G(v['look'])) for k, v in rt['feeds'].items()},
               chamber=rt['chamber'], collider=collider(s), tether_reach_m=rt['tether_reach_m'], tether_reach_status=rt['tether_reach_status'],
               ring_sweep=rt['ring_sweep'], docking_corridors=rt['docking_corridors'], suit_sweep_radius_m=suit_r,
               mobility=data['mobility'], protocol=eva_suit.handoff_plan([a['x'] for a in rt['anchors'] if a['run'] == 'aft'], 0, 2))
    acc = Path(access) if access else root/'references/p1_eva_access.json'
    if acc.exists():                                             # the SP-11/12/13 study, for display as STUDY geometry (eva_access.py)
        a = json.loads(acc.read_text()); rec = next(r for r in a['sp11'] if r['id'] == a['recommendation']['id'])
        out['access'] = dict(status=a['status'], suited_route=a['suited_route'], legacy_envelope=a['legacy_envelope'],
                             envelopes=a['envelopes'], recommendation=a['recommendation'],
                             candidates=[dict(id=r['id'], status=r['status'], aperture_m=r['aperture_m'], layout=r['layout'],
                                              clear_diameter_m=r['chamber']['clear_diameter_m'], clear_length_m=r['chamber']['clear_length_m'],
                                              volume_m3=r['chamber']['volume_m3'], fails=r['geometry_fail']) for r in a['sp11']],
                             chamber=dict(id=rec['id'], axis_x=rec['fitting']['x'], theta_deg=rec['fitting']['theta_deg'], a0=rec['chamber']['inner_bulkhead_a_m'],
                                          a1=rec['chamber']['outer_bulkhead_a_m'], radius=rec['chamber']['clear_radius_m'], aperture_m=rec['aperture_m'],
                                          occupants=rec['occupants']),
                             rooms={k: dict(id=a[k]['id'], x_m=a[k]['x_m'], az_deg=a[k]['az_deg'], r_m=a[k]['r_m'],
                                            fixtures=[dict(id=f['id'], job=f['job'], x=f['x'], az=f['az'], r0=f['r0'], size=f['size']) for f in a[k]['fixtures']])
                                    for k in ('sp12', 'sp13')})
    sp = Path(sp11) if sp11 else root/'references/p1_eva_sp11.json'
    if sp.exists() and 'access' in out:                           # EVA-003: the 1.20 m lead replaces the EVA-002 recommendation on screen
        e3 = json.loads(sp.read_text()); lead = next(r for r in e3['rows'] if abs(r['aperture_m']-data['sp11_eva3']['lead_m']) < 1e-9)
        m = lead['mechanisms']['parallel_plug_slide']; park = m['parking'][m['lead_direction']]; ch = lead['chamber']
        out['access']['eva3'] = dict(
            status=e3['status'], id=lead['id'], role=lead['role'], aperture_m=lead['aperture_m'],
            chamber=dict(axis_x=lead['fitting']['x'], theta_deg=lead['fitting']['theta_deg'], a0=ch['inner_bulkhead_a_m'], a1=ch['outer_bulkhead_a_m'],
                         radius=ch['clear_radius_m'], clear_diameter_m=ch['clear_diameter_m'], clear_length_m=ch['clear_length_m'], volume_m3=ch['volume_m3'],
                         occupants=lead['occupants']),
            inner_hatch=dict(mechanism='parallel_plug_slide', direction=m['lead_direction'], park_corners_chamber=park['corners_chamber'],
                             seat_centre_chamber=[park['centre_chamber'][0]+m['stroke_m'], 0.0, 0.0],
                             radial_budget_m=m['radial_budget_m'], hinged_budget_m=lead['mechanisms']['hinged_into_sp12']['radial_budget_m']),
            latch=[dict(variant=k, pivot_chamber=l['lever_pivot_chamber'], grip_radius_m=l['lever_grip_radius_m'], top_a_m=ch['leaf_face_a_m']+lead['door']['t'])
                   for k, l in lead['latch'].items()],
            comparison=[dict(id=r['id'], aperture_m=r['aperture_m'], role=r['role'], routine_door_ok=r['routine_door_ok'],
                             chamber=[r['chamber']['clear_diameter_m'], r['chamber']['clear_length_m'], r['chamber']['volume_m3']],
                             mechanisms={k: v['status'] for k, v in r['mechanisms'].items()},
                             rescue={k: v['status'] for k, v in r['rescue'].items() if k != 'no_power'}) for r in e3['rows']])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path); ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--suit-radius', type=float, default=None); ap.add_argument('--access', type=Path, default=None)
    ap.add_argument('--sp11', type=Path, default=None)
    a = ap.parse_args()
    r = a.suit_radius
    if r is None:                                            # the measured suited sweep radius when the fit report exists
        fit = a.root/'references/p1_eva_fit.json'
        r = json.loads(fit.read_text())['sweep_radius_m'] if fit.exists() else .55
    out = runtime(a.root, r, a.access, a.sp11)
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True); (a.out/'wf_eva.json').write_text(json.dumps(out, indent=1)+'\n')
    print(json.dumps(dict(status=out['status'], anchors=len(out['anchors']), runs=out['runs'],
                          gates={k: {g['id']: g['status'] for g in h['gates']} for k, h in out['holds'].items()},
                          flight=out['flight']['state'], view_factor={k: h['view_factor_readback']['total'] for k, h in out['holds'].items()},
                          ring_gap={k: next(g['measured'] for g in h['gates'] if g['id'] == 'ring') for k, h in out['holds'].items()},
                          blades={k: [(b['blade'], b['visible_fraction'], b['nearest_visible_m']) for b in next(g['measured'] for g in h['gates']
                                                                                                        if g['id'] == 'thermal')]
                                  for k, h in out['holds'].items()}), indent=1))


if __name__ == '__main__':
    main()
