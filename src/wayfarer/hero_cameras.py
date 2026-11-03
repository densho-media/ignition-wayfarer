"""The three permanent exterior hero cameras (exterior production refinement 2026-11-01; [look.hero_cameras], presentation only,
PROTOTYPE depiction choices). Each camera is fitted to the ship's own stations, never to fixed X numbers, so a later layout change keeps
the composition: a focus on the axis, a view direction (from the focus toward the camera), a focal length, and either corners to fit
(the subject's box: the camera backs off until every corner is inside the frame plus margin) or a fixed distance. The resolved poses go
into the vehicle file as CAM_HERO_* in 30_CAMERAS (build), and presentation/hero_set.py renders each in the engineering and cinematic
modes with the same pose, sun and exposure. Review labels are anchors here, drawn only in the separate overlay.

- CAM_HERO_ENGINEERING: the whole ship from slightly forward of broadside and a little below the sun side: the ventral blade nearly
  face-on, the upper blade foreshortened, the bulkhead, both rings, the tank farm and the Brow in one long diagonal; 50 mm keeps the
  Brow from swelling.
- CAM_HERO_FORWARD: the crew end from the forward quarter: the Brow face with its EYE wells and rim, the tank farm, both rings and their
  hub, and the spine to the bulkhead.
- CAM_HERO_PROPULSION: from aft and below: the four nozzles and the thrust structure in front, the HOT blades receding to the bulkhead,
  then WARM and LOW; the camera of the later First Ignition sequence (it renders FIRST_IGNITION as well as COAST).
"""
import math


def cfg(s):
    return s['look']['hero_cameras']


def anchors(s):
    """Named points on the ship (metres, ship frame) from the shared stations."""
    import layout
    import drive_manifold
    import forward_shield
    import habitat_ring
    import radiator_zones
    import fuel_storage
    tanks = fuel_storage.tanks(s)
    fs = forward_shield.stations(s); dm = drive_manifold.stations(s); ra, rb = habitat_ring.centers(s)
    xf = layout.origin(s, 'RADIATOR_FRONT'); xa = layout.origin(s, 'RADIATOR_AFT'); xz = layout.origin(s, 'RADIATOR_ZONE_FRONT')
    secs = {x['id']: x for x in radiator_zones.placed(s)}
    ph = math.radians(s['prototype']['radiator_phase_deg']); R = s['radiators']['outer_radius']['value']
    blade = lambda x, r, k: (x, r*math.cos(ph+2*math.pi*k/3), r*math.sin(ph+2*math.pi*k/3))
    return {
        'AFT': (dm['exit'], 0.0, 0.0), 'FWD': (fs['lance_tip'], 0.0, 0.0), 'MID': ((dm['exit']+fs['lance_tip'])/2, 0.0, 0.0),
        'NOZZLES': (dm['exit'], 0.0, 0.0), 'HOT_MID': ((xa+xf)/2, 0.0, 0.0), 'BULKHEAD': (xf+1.0, 0.0, 0.0),
        'WARM': ((secs['WARM']['x0']+secs['WARM']['x1'])/2, 0.0, 0.0), 'LOW': ((secs['LOW']['x0']+secs['LOW']['x1'])/2, 0.0, 0.0),
        'ZONE_FRONT': (xz, 0.0, 0.0), 'RING_A': (ra, 0.0, 0.0), 'RING_B': (rb, 0.0, 0.0),
        'RING_A_RIM': (ra, -28.0, -10.0), 'RING_B_RIM': (rb, -24.0, 18.0), 'EYE_WELL': (fs['face'], -21.2, -21.2),
        'TANKS': ((min(t['x0'] for t in tanks)+max(t['x1'] for t in tanks))/2, 0.0, 0.0), 'TANK_SIDE': (tanks[0]['x1']-6.0, tanks[0]['y'], tanks[0]['z']),
        'BROW': (fs['face'], 0.0, 0.0), 'BROW_RIM': (fs['rim_face'], 0.0, -fs['shield_r']),
        'HOT_BLADE_TIP': blade((xa+xf)/2, R, 2), 'BULKHEAD_RIM': blade(xf+3.0, R, 1), 'WARM_SHEET': blade(anchors_x(secs, 'WARM'), R*.7, 2),
        'LOW_SHEET': blade(anchors_x(secs, 'LOW'), R*.7, 2), 'R': fs['shield_r'], 'R_BLADE': R}


def anchors_x(secs, k):
    return (secs[k]['x0']+secs[k]['x1'])/2


def _sub(a, b): return tuple(x-y for x, y in zip(a, b))
def _add(a, b): return tuple(x+y for x, y in zip(a, b))
def _mul(a, k): return tuple(x*k for x in a)
def _dot(a, b): return sum(x*y for x, y in zip(a, b))
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _unit(a):
    n = math.sqrt(_dot(a, a)); return tuple(x/n for x in a)


def basis(direction):
    """Camera axes (right, up, back) for a camera looking from the focus along -direction; up follows world +Z."""
    back = _unit(direction); right = _unit(_cross((0.0, 0.0, 1.0), back)); up = _cross(back, right)
    return right, up, back


def resolve(s, name):
    """Pose of one hero camera: location, the rotation matrix columns (right, up, back), lens (mm), sensor (mm), focus, distance,
    sun (from_aft_deg, azimuth_deg), editorial EV, the configurations it renders and its label anchors."""
    c = cfg(s); q = c['cameras'][name]; A = anchors(s)
    fx = A[q['focus'][0]][0]+q['focus'][1]; focus = (fx, q['focus'][2], q['focus'][3])
    right, up, back = basis(q['direction']); lens = q['lens_mm']; sensor = c['sensor_mm']; aspect = c['aspect'][0]/c['aspect'][1]
    tanx = sensor/2/lens; tany = tanx/aspect
    x0 = A[q['fit'][0]][0]+q['fit'][1]; x1 = A[q['fit'][2]][0]+q['fit'][3]; r = q['fit'][4] if isinstance(q['fit'][4], (int, float)) else A[q['fit'][4]]
    # The subject is the ship's cylindrical envelope from x0 to x1 at radius r (24 points per end), not its bounding box: a box's corners
    # stand far outside a round ship seen obliquely and leave black space. The camera keeps its view direction and slides sideways
    # (pan, no rotation) until the envelope is centred in the frame, then backs off until it fills the frame to the margin.
    pts = [(x, r*math.cos(2*math.pi*k/24), r*math.sin(2*math.pi*k/24)) for x in (x0, x1) for k in range(24)]
    loc = focus; d = 0.0
    for p in pts:
        v = _sub(p, focus); lx, ly, lz = _dot(v, right), _dot(v, up), _dot(v, back)
        d = max(d, abs(lx)/tanx+lz, abs(ly)/tany+lz)
    for _ in range(40):
        cam = _add(focus, _mul(back, d))
        uv = []
        for p in pts:
            v = _sub(p, cam); z = -_dot(v, back)
            uv.append((_dot(v, right)/(z*tanx), _dot(v, up)/(z*tany)))
        u0, u1 = min(a for a, b in uv), max(a for a, b in uv); v0, v1 = min(b for a, b in uv), max(b for a, b in uv)
        cu, cv = (u0+u1)/2, (v0+v1)/2
        ext = max((u1-u0)/2, (v1-v0)/2)
        focus = _add(focus, _add(_mul(right, cu*d*tanx), _mul(up, cv*d*tany)))
        d *= 1+.6*(ext*q['margin']-1)
    loc = _add(focus, _mul(back, d))
    return dict(name=name, location=loc, right=right, up=up, back=back, lens_mm=lens, sensor_mm=sensor, focus=focus, distance_m=d,
                sun=tuple(q['sun']), ev=q['editorial_ev'], states=list(q['states']), purpose=q['purpose'],
                labels=[dict(text=t, at=A[k] if isinstance(A[k], tuple) else None) for t, k in q['labels']],
                clip=(1.0, 4000.0))


def all_cameras(s):
    return [resolve(s, n) for n in cfg(s)['cameras']]


def check(s):
    """Composition rules: every camera keeps the ship inside the frame and is far enough that the nearest part of the ship is not
    closer than min_distance_ratio x the ship length (no extreme perspective swelling of the Brow)."""
    errs = []; A = anchors(s); length = A['FWD'][0]-A['AFT'][0]
    for cam in all_cameras(s):
        near = cam['distance_m']-A['R']
        if near < cfg(s)['min_near_ratio']*length:
            errs.append(f"{cam['name']}: nearest ship part {near:.0f} m, closer than {cfg(s)['min_near_ratio']} x ship length")
    return errs


if __name__ == '__main__':
    import json
    import spec
    s = spec.load()[0]
    for cam in all_cameras(s):
        print(cam['name'], [round(v, 1) for v in cam['location']], f"{cam['lens_mm']} mm", f"{cam['distance_m']:.0f} m", cam['states'])
    print('check', check(s) or 'PASS')
