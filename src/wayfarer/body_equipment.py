"""S04/S02 body framing and momentum storage around the FUEL-SPLIT body stations (owner go 2026-10-30; every size and position PROTOTYPE).

- frames(s): an internal ring frame in every gap between the nine BODY-C3 modules, outside the keel rails and inside the skin, so the
  stations hang inside a framed bay; the two 3 m utility frames add three radial beams at the lobe bisectors from the spine clearance
  to the rail circle (the equipment mounts).
- cmgs(s): six double-gimbal control-moment gyros, one per beam (three per utility frame), cradled forward of the beam. Sizing: the S02
  momentum case (exterior_hardware.sizing: twice the rings' allowed residual) shared by five of six units, so one may fail; each rotor
  I = H / omega at a PROTOTYPE rotor speed, its rim mass from I = m r^2. Not a slew-rate or attitude requirement (S&E 37 F17 names the
  function only).
- check(s): the fit screen: each unit inside its gap with clearance to the module ends, the beam and the lane lines.

    python3 src/wayfarer/body_equipment.py      # print the frames, the CMG sizing and the screen
"""
import json
import math
import sys
from pathlib import Path

import fuel_storage as fst


def cfg(s):
    return s['body_equipment']


def frames(s):
    q = cfg(s)['frames']; mods = fst.body_modules(s); rail = s['structure']['sector_radius_m']+s['prototype']['structural_rail_radius_m']
    import hull_geometry as hg
    out = []
    for i, (a, b) in enumerate(zip(mods, mods[1:]), 1):
        x = (a['x1']+b['x0'])/2; utility = b['x0']-a['x1'] > 2.0; hull = hg.radius_at(s, x)-s['hull']['shell_thickness_m']
        out.append(dict(name=f'Body_Frame_{i:02}', x=x, r0=rail+q['rail_gap_m'], r1=hull-q['skin_gap_m'], width=q['width_m'], utility=utility))
        if utility:
            for k, deg in enumerate(q['beam_deg'], 1):
                out.append(dict(name=f'Body_Frame_{i:02}_Beam_{k}', x=x+q['beam_offset_m'], deg=deg, r0=q['beam_r0_m'], r1=rail+q['rail_gap_m'],
                                width=q['width_m'], depth=q['beam_depth_m']))
    return out


def sizing(s):
    import exterior_hardware as eh
    q = cfg(s)['cmg']; need = eh.sizing(s)['momentum']['storage_N_m_s']; n = len(q['deg'])*2
    per = need/(n-1); w = q['rotor_rpm']*2*math.pi/60; inertia = per/w; mass = inertia/q['rotor_radius_m']**2
    return dict(units=n, need_N_m_s=round(need), per_unit_N_m_s=round(per), one_failed_N_m_s=round(per*(n-1)), rotor_rpm=q['rotor_rpm'],
                rotor_inertia_kg_m2=round(inertia, 1), rotor_rim_mass_kg=round(mass), status='PROTOTYPE sizing (momentum case: exterior_hardware.sizing)')


def cmgs(s):
    q = cfg(s)['cmg']; out = []
    for f in frames(s):
        if 'deg' not in f:
            continue
        a = math.radians(f['deg']); x = f['x']-cfg(s)['frames']['beam_offset_m']+q['offset_m']
        out.append(dict(name=f"Body_CMG_{f['name'][11:13]}_{f['name'][-1]}", x=x, r=q['radius_m'], deg=f['deg'],
                        housing=q['housing_diameter_m'], gimbal=q['gimbal_diameter_m'], beam_x=f['x'], a=a,
                        cradle=(f['x']+f['depth']/2, x-q['housing_diameter_m']/2)))
    return out


def check(s):
    mods = fst.body_modules(s); fails = []
    for u in cmgs(s):
        lo, hi = u['x']-u['gimbal']/2, u['x']+u['gimbal']/2
        gap = [(a['x1'], b['x0']) for a, b in zip(mods, mods[1:]) if a['x1'] <= lo and hi <= b['x0']]
        if not gap:
            fails.append(f"{u['name']}: gimbal outside its module gap")
        if u['cradle'][1]-u['cradle'][0] < 0.05:
            fails.append(f"{u['name']}: housing overlaps its beam")
        if u['r']-u['gimbal']/2 < cfg(s)['frames']['beam_r0_m']:
            fails.append(f"{u['name']}: inside the spine clearance")
        if u['r']+u['gimbal']/2 > fst.cfg(s)['transfer']['lane_r_m'] and min(abs((u['deg']-k+180) % 360-180) for k in fst.cfg(s)['body']['keel_lanes_deg']) < 30:
            fails.append(f"{u['name']}: reaches the lane lines")
    return fails


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s = load()[0]
    print(json.dumps(dict(sizing=sizing(s), cmgs=[{k: v for k, v in u.items() if k != 'a'} for u in cmgs(s)], frames=len(frames(s)), fails=check(s)), indent=1, default=str))
