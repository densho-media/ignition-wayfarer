"""ISSA Phase II, Gate 4 spatial refinement: assembly-specific envelopes, candidate layouts, reactor dose to every occupied region
(direct, shadow-cone and blade scatter), plant separation. STUDY (NONCANON), pure. Writes ../results/phase2_placement.json.

    python3 work/ship-systems-architecture/phase2/placement.py      (after eps_b.py)

Dose model (order of magnitude, labelled): a bare fission core emits 2.43 neutrons per 200 MeV fission; fast-neutron fluence-to-effective-
dose 4.0e-10 Sv cm2 (ICRP 116 near 1 MeV) plus ~10 % for prompt and capture gammas. Shield attenuation is exp(-t / lambda) with an
effective deep-penetration relaxation length lambda = 0.10 / 0.12 / 0.15 m (LiH with a tungsten gamma layer, buildup included).
Single scatter off a radiator blade: albedo 0.02 / 0.05 / 0.15 (dose albedo of fast neutrons and gammas on metal and composite).
None of this is a transport calculation; it decides which layouts deserve one.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE/'results'
MEV = 1.602e-13
K_SV_M2_H_PER_W = 2.43/(200*MEV)*4.0e-10/(4*math.pi*1e4)*3600*1.10     # Sv/h at 1 m per thermal watt, bare core
LAM = (0.10, 0.12, 0.15)
ALBEDO = (0.02, 0.05, 0.15)
RHO_SHIELD = 1.6e3            # kg/m3, LiH (0.78) with a ~6 % tungsten fraction by volume, smeared

# Occupied and sensitive regions (built model stations, docs/MODEL.md; occupancy and allotments PROTOTYPE)
TARGETS = [
    dict(id='RING_A', x=97.3, r=(25.0, 30.0), hours_yr=8766*0.9, allot_Sv_yr=0.010, who='crew, 6 + 6 people (habitat sectors)'),
    dict(id='RING_B', x=103.3, r=(25.0, 30.0), hours_yr=8766*0.9, allot_Sv_yr=0.010, who='crew'),
    dict(id='REFUGE', x=107.8, r=(0.0, 2.9), hours_yr=200, allot_Sv_yr=0.010, who='crew in storms, survival'),
    dict(id='FWD_SERVICE', x=120.0, r=(0.0, 5.0), hours_yr=500, allot_Sv_yr=0.005, who='airlock, storeroom, docks'),
    dict(id='BROW_EYE', x=141.5, r=(0.0, 45.0), hours_yr=8766, allot_Sv_yr=None, gy_mission=1e3, who='EYE electronics and optics (unmanned)'),
    dict(id='TANK_FARM', x=123.5, r=(13.5, 27.75), hours_yr=8766, allot_Sv_yr=None, heat_W_max=50.0, who='cryogenic propellant (neutron heating)'),
    dict(id='KEEL_LANE_AT_PLANT', x=None, r=(4.5, 5.5), hours_yr=50, allot_Sv_yr=0.005, who='crew transit along the spine lanes past a plant'),
    dict(id='EVA_HULL_AT_PLANT', x=None, r=(6.4, 7.6), hours_yr=20, allot_Sv_yr=0.005, who='EVA on the casing beside a plant'),
    dict(id='PLANT_MAINTENANCE', x=None, r=(2.0, 3.0), hours_yr=10, allot_Sv_yr=0.010, who='hands-on work at a plant at decay power'),
]

# Blades: three radial plates at 90/210/330 deg, root 6.5 m, tip 37 m, x -133.25..48.9 (radiators.*; RAD-ZONE origins)
BLADE = dict(x=(-133.25, 48.9), r=(6.5, 37.0), count=3)

# Assembly envelopes per unit (STUDY): equipment volume from specific volumes, then assembly-specific clearance rules
ASSY = {
    'reactor + shadow shield': dict(m3_per_MWe=(1.0, 1.6, 2.5), clearance='no hands-on access; 0.3 m gap for thermal growth; '
                                    'remote removal path along x to the casing hatch', insulation_m=0.15, mount='thrust-rated frame (1.5 g axial)'),
    'Brayton turbo-alternator-compressor': dict(m3_per_MWe=(1.5, 2.5, 4.0), clearance='0.8 m service side; removal envelope = rotor '
                                                'assembly diameter + 0.5 m along a straight path', insulation_m=0.10, mount='isolated (rotor dynamics, CMG coupling)'),
    'recuperator + gas cooler + manifolds': dict(m3_per_MWe=(3.0, 5.0, 8.0), clearance='0.6 m inspection, 1.2 m at isolation valves',
                                                 insulation_m=0.10, mount='sliding supports (thermal expansion 550-1100 K)'),
    'power conditioning + switchgear': dict(m3_per_MWe=(1.0, 1.5, 2.5), clearance='1.0 m front access (ORU drawers), cold plates on LOW',
                                            insulation_m=0.0, mount='shock-isolated rack'),
}
MODULE = dict(gross_m3=10.2*2.8*3.2, note='one M-pair (two dry-store modules, one sector): 10.2 x 2.8 x 3.2 m (Phase I make_review envelope)')


def bare(Pt_W, d):
    return K_SV_M2_H_PER_W*Pt_W/max(d, 0.5)**2


def efolds(Pt_W, d, allow_Sv_h):
    return max(0.0, math.log(bare(Pt_W, d)/allow_Sv_h))


def target_geo(t, xp, rp=3.0):
    """nearest distance and the off-axis angle seen from a plant at (xp, rp) on the spine axis side."""
    if t['x'] is None:
        d = t['r'][0]-rp+0.5 if t['id'] != 'PLANT_MAINTENANCE' else 2.0
        return d, 90.0
    dx = t['x']-xp; r_far = t['r'][1]
    return math.hypot(dx, max(0.0, t['r'][0]-rp)), math.degrees(math.atan2(r_far+rp, dx))


def blade_scatter_ratio(xp, xt, rt, i, rp=3.0, n=60):
    """single-scatter dose at a target from all three blades, per unit bare direct dose at the target (numerical, Lambertian re-emission)."""
    tot = 0.0; d_direct = math.hypot(xt-xp, rt)
    xs = [BLADE['x'][0]+(k+0.5)*(BLADE['x'][1]-BLADE['x'][0])/n for k in range(n)]
    rs = [BLADE['r'][0]+(k+0.5)*(BLADE['r'][1]-BLADE['r'][0])/20 for k in range(20)]
    dA = (BLADE['x'][1]-BLADE['x'][0])/n*(BLADE['r'][1]-BLADE['r'][0])/20
    for az in (90.0, 210.0, 330.0):
        a = math.radians(az)
        for x in xs:
            for r in rs:
                # plant at azimuth 90 deg (worst case for the 90-deg blade), target ring point at azimuth 90+180 (sees the far blades)
                py, pz = 0.0, rp; by, bz = r*math.cos(a), r*math.sin(a); ty, tz = 0.0, -rt
                d1 = math.dist((xp, py, pz), (x, by, bz)); d2 = math.dist((x, by, bz), (xt, ty, tz))
                n_ = (-math.sin(a), math.cos(a))     # blade face normal (in y-z)
                c1 = abs(n_[0]*(by-py)+n_[1]*(bz-pz))/max(d1, 1e-6); c2 = abs(n_[0]*(ty-by)+n_[1]*(tz-bz))/max(d2, 1e-6)
                tot += c1*dA/(4*math.pi*d1**2)*ALBEDO[i]*c2/(math.pi*d2**2)
    return tot/(1/(4*math.pi*d_direct**2))


LAYOUTS = {
    'L-A mid-body M3/M4 (Phase I)': dict(x=(-60.25, -46.25), sectors=(90, 210), districts='D3 dry-store modules',
                                         repurposes_dry_store=True, note='Phase I candidate; two plants 14 m apart, different sectors'),
    'L-B aft bay with the drive (one nuclear district)': dict(x=(-108.0, -100.0), sectors=(90, 330), districts='D2 aft engineering bay',
                                                              repurposes_dry_store=False, note='all fission and the drive in one exclusion district; D2 usable 75 m3'),
    'L-C distributed 3+1 (C-lean)': dict(x=(-82.0, -60.25, -46.25, -24.0), sectors=(90, 210, 330, 90), districts='D3 M1, M3, M4, M7',
                                         repurposes_dry_store=True, note='one unit per module group; blade sectors separate units'),
    'L-E aft cluster M1-M2 (3+1, aft of all crew spaces)': dict(x=(-86.6, -81.1, -75.6, -70.1), sectors=(90, 210, 330, 210),
                                                             districts='D3 M1-M2 (aftmost dry-store modules)', repurposes_dry_store=True,
                                                             note='crew boundary at the M2/M3 frame; D2 and M1-M2 drone-only while units run'),
    'L-D RAD-ZONE casing (rejected Phase I)': dict(x=(66.0,), sectors=(90,), districts='D5', repurposes_dry_store=False,
                                                   note='25-45 m from ring A; shadow cone would have to open to ~40 deg'),
}


def shield_check(a, L):
    eb = [u['parts_kg']['shield'] for u in a['unit']]
    delta = [(s-e)*a['units'] for s, e in zip(L['per_unit_shield_kg'], eb)]
    return dict(eps_b_shadow_kg_unit=eb, placement_shadow_plus_scatter_kg_unit=L['per_unit_shield_kg'], delta_kg_architecture=delta,
                c_lean_mass_with_scatter_kg=[m+d for m, d in zip(a['mass_kg'], delta)],
                note='eps_b sized a shadow shield only; the blade-facing side band against single scatter is new at Gate 4')


def main():
    eb = json.loads((OUT/'phase2_eps_b.json').read_text())
    archs = {a['name']: a for a in eb['architectures']}
    unit_MWe = {'B': 5.62, 'C': 2.88, 'C-lean': 1.75}
    eta = 0.219
    # 1. envelopes
    env = {}
    for k, u in unit_MWe.items():
        rows = {}; total = [0.0, 0.0, 0.0]
        for n, a in ASSY.items():
            v = [m*u for m in a['m3_per_MWe']]
            side = v[1]**(1/3); ins = 4*side*side*a['insulation_m']           # insulation shell on a cube of the nominal volume
            cl = {'reactor + shadow shield': 0.3, 'Brayton turbo-alternator-compressor': 0.8, 'recuperator + gas cooler + manifolds': 0.6,
                  'power conditioning + switchgear': 1.0}[n]
            serv = [vv + side*side*cl for vv in v]                             # one service face per assembly
            rows[n] = dict(equipment_m3=v, insulation_m3=ins, with_access_m3=[s+ins for s in serv], **{kk: a[kk] for kk in ('clearance', 'mount')})
            total = [t+s+ins for t, s in zip(total, serv)]
        removal = 1.4*1.4*12.0                                                 # a 1.4 m square straight removal lane, 12 m to a hatch
        env[k] = dict(unit_MWe=u, assemblies=rows, unit_total_m3=total, removal_lane_m3=removal,
                      modules_needed=[(t+removal)/MODULE['gross_m3'] for t in total],
                      note='The Phase I 1-m clearance was one generic margin; these are per assembly. Removal lanes may be shared by units in a row.')
    # 2. dose per layout and target, for the nominal C-lean unit (1.75 MWe -> 8.0 MWt)
    Pt = unit_MWe['C-lean']*1e6/eta
    lay = {}
    for name, L in LAYOUTS.items():
        rows = []
        for t in TARGETS:
            worst = None
            for xp in L['x']:
                d, ang = target_geo(t, xp)
                if t.get('allot_Sv_yr'):
                    allow = t['allot_Sv_yr']/t['hours_yr']
                elif 'gy_mission' in t:
                    allow = t['gy_mission']/(6*8766)          # Gy ~ Sv for this screen (electronics: total ionising + displacement proxy)
                else:
                    allow = None
                ef = efolds(Pt, d, allow) if allow else None
                heat = None
                if t['id'] == 'TANK_FARM':
                    # fast-neutron heating of a tank-farm cross-section ~ 2 MeV deposited per neutron intercepted
                    frac = (math.pi*(t['r'][1]**2-t['r'][0]**2))/(4*math.pi*d**2)
                    heat = Pt/(200*MEV)*2.43*frac*2*MEV
                    ef = math.log(max(1.0, heat/t['heat_W_max']))
                row = dict(target=t['id'], who=t['who'], plant_x=xp, d_m=d, off_axis_deg=ang, bare_Sv_h=bare(Pt, d),
                           allow_Sv_h=allow, efolds_needed=ef, unshielded_tank_heat_W=heat,
                           in_shadow_cone=ang <= 12.5)
                if t['x'] is not None and t['id'] in ('RING_A', 'RING_B', 'REFUGE'):
                    row['blade_scatter_over_bare_direct'] = [blade_scatter_ratio(xp, t['x'], t['r'][1], i) for i in range(3)]
                if worst is None or (ef or 0) > (worst['efolds_needed'] or 0):
                    worst = row
            rows.append(worst)
        ring = next(r for r in rows if r['target'] == 'RING_A')
        cone = max(r['off_axis_deg'] for r in rows if r['target'] in ('RING_A', 'RING_B', 'REFUGE', 'FWD_SERVICE', 'TANK_FARM'))
        t_shadow = [ring['efolds_needed']*lam for lam in LAM]
        sc = ring.get('blade_scatter_over_bare_direct', [0, 0, 0])
        # scatter path: unshielded towards the blades, so the side shield must take the scatter dose below the allowance too
        side_ef = [max(0.0, ring['efolds_needed']+math.log(max(s, 1e-30))) for s in sc]
        # shield masses: shadow frustum (core radius 0.45 m, opening at the cone angle) and a blade-facing side band
        def frustum(t, half):
            r0 = 0.6; r1 = r0+t*math.tan(math.radians(half)); return math.pi*t/3*(r0*r0+r0*r1+r1*r1)*RHO_SHIELD
        shadow_kg = [frustum(t, max(12.5, cone)) for t in t_shadow]
        band_kg = [4*math.pi*1.0**2*0.6*ef*lam*RHO_SHIELD for ef, lam in zip(side_ef, LAM)]   # 60 % of 4 pi at 1.0 m radius
        lane = next(r for r in rows if r['target'] == 'KEEL_LANE_AT_PLANT')
        lay[name] = dict(**L, targets=rows, cone_half_angle_needed_deg=cone, shadow_thickness_m=t_shadow, shadow_shield_kg=shadow_kg,
                         blade_scatter=sc, side_efolds=side_ef, side_band_kg=band_kg, per_unit_shield_kg=[a+b for a, b in zip(shadow_kg, band_kg)],
                         keel_lane_efolds=lane['efolds_needed'], keel_lane_shield_m=[lane['efolds_needed']*lam for lam in LAM],
                         units=len(L['x']))
    # 3. plant separation (redundancy credited only where domains differ)
    sep = []
    for name, L in LAYOUTS.items():
        xs = L['x']
        if len(xs) > 1:
            dmin = min(abs(a-b) for i, a in enumerate(xs) for b in xs[i+1:])
            sep.append(dict(layout=name, min_axial_m=dmin, sectors=L['sectors'], separate_blades=len(set(L["sectors"])) == len(L["sectors"]), shared_blade_units=len(L["sectors"])-len(set(L["sectors"])),
                            shared=['spine keel structure', 'coolant headers if not split per blade', 'one cone axis (all shields look forward)'] +
                                   (['drive exclusion district and the drive fault domain (DRIVE_AFT)'] if 'aft' in name else [])))
    res = dict(status='ISSA Phase II STUDY (NONCANON)', dose_model=dict(K_Sv_m2_h_per_Wt=K_SV_M2_H_PER_W, lam_m=LAM, albedo=ALBEDO, rho_shield=RHO_SHIELD),
               module=MODULE, envelopes=env, layouts=lay, separation=sep,
               eps_b_shield_check=shield_check(archs['C-lean: 3+1 at nominal demand'], lay['L-E aft cluster M1-M2 (3+1, aft of all crew spaces)']))
    (OUT/'phase2_placement.json').write_text(json.dumps(res, indent=1))
    print('shield check', {k: [round(x) for x in v] if isinstance(v, list) else v for k, v in res['eps_b_shield_check'].items()})
    for k, e in env.items():
        print(f"unit {k:7s} {e['unit_MWe']:.2f} MWe: {'/'.join(f'{v:.0f}' for v in e['unit_total_m3'])} m3 + lane {e['removal_lane_m3']:.0f}; modules {'/'.join(f'{v:.2f}' for v in e['modules_needed'])}")
    for n, L in lay.items():
        print(n, f"cone {L['cone_half_angle_needed_deg']:.1f} deg, shadow t {[round(x, 2) for x in L['shadow_thickness_m']]}, kg {[round(x) for x in L['shadow_shield_kg']]}, "
              f"scatter {['%.2e' % x for x in L['blade_scatter']]}, side ef {[round(x, 1) for x in L['side_efolds']]}, band kg {[round(x) for x in L['band_kg']] if 'band_kg' in L else [round(x) for x in L['side_band_kg']]}, lane ef {L['keel_lane_efolds']:.1f}")
        for r in L['targets']:
            print(f"   {r['target']:20s} d {r['d_m']:6.1f} ang {r['off_axis_deg']:5.1f} bare {r['bare_Sv_h']:.2e} Sv/h ef {r['efolds_needed'] if r['efolds_needed'] is None else round(r['efolds_needed'], 1)} heat {r['unshielded_tank_heat_W'] and round(r['unshielded_tank_heat_W'])}")


if __name__ == '__main__':
    main()
