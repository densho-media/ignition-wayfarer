"""ISSA Phase III-C, EPS-G1: parametric envelope model of one modular L2 power unit, its inspection envelopes, candidate power districts in
the M1-M2 dry-store bays and preliminary thermal-machinery envelopes. Pure Python (no bpy); make_review3.py draws the result.
STUDY / PROTOTYPE: every envelope is labelled; nothing here is a reactor design. Writes ../results/phase3_eps_g1.json.

    python3 work/ship-systems-architecture/phase3/eps_g1.py

Frame: ship metres, +X bow. A unit sits in one dry-store bay: a sector box between r 1.5 and 4.3 m, 3.2 m wide, centred on a blade azimuth
(90, 210, 330 deg; +Y = 0 deg, +Z = 90 deg), between the module end gaps. Unit-local coordinates: u along +X (aft to forward), v radial
outward, w tangential. The reactor sits at the aft end; its shadow shield faces forward (crew); the conversion machinery sits in the shadow.
Shield masses are computed from their envelope volume and a smeared density, so mass and volume agree by construction.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
OUT = HERE/'results'
RHO_SHIELD = 1.9e3      # kg/m3: LiH (0.78) with ~6 % W by volume, smeared (0.94*0.78 + 0.06*19.3)
LAM = (0.10, 0.12, 0.15)
BAY = dict(r0=1.5, r1=4.3, width=3.2, casing_r=5.6, module_len=11.0, end_gap=0.4, bay_aft_x=-89.75, module_offsets=(0.0, 12.0),
           sectors=(90.0, 210.0, 330.0), keel_lanes=(30.0, 150.0, 270.0), basis='[fuel_storage.body] dry_store, module_offsets; survey.json casing radius')

# specific volumes and masses (STUDY bands; see phase2/eps_b.py COMP for the mass anchors)
SPEC = dict(
    core_MWt_per_m3=(9.0, 6.0, 4.0),              # vessel + reflector + control drums envelope (SP-100 ~2.4 MWt in ~0.35 m3 envelope incl. drums)
    tac_m3_per_MWe=(0.3, 0.5, 0.8),               # turbo-alternator-compressor
    recuperator_m3_per_MWe=(1.5, 2.5, 4.0),
    gas_cooler_m3_per_MW=(0.08, 0.12, 0.2),       # per MW of rejected heat
    ihx_m3_per_MWt=(0.08, 0.12, 0.2),
    pumps_m3_per_MWt=(0.04, 0.06, 0.1),
    pcu_m3_per_MWe=(0.8, 1.2, 2.0),               # rectifiers, breakers, plant controller (cold plates on LOW)
)


def box(name, cls, family, u0, u1, v0, v1, w0, w1, mass=None, status='PROTOTYPE', note=''):
    return dict(name=name, cls=cls, family=family, shape='box', u=(u0, u1), v=(v0, v1), w=(w0, w1),
                volume_m3=abs((u1-u0)*(v1-v0)*(w1-w0)), mass_kg=mass, status=status, note=note)


def cyl(name, cls, family, u0, u1, vc, wc, r_aft, r_fwd=None, mass=None, status='PROTOTYPE', note=''):
    r_fwd = r_aft if r_fwd is None else r_fwd; L = u1-u0
    vol = math.pi*L/3*(r_aft**2+r_aft*r_fwd+r_fwd**2)
    return dict(name=name, cls=cls, family=family, shape='frustum', u=(u0, u1), vc=vc, wc=wc, r=(r_aft, r_fwd), volume_m3=vol,
                mass_kg=mass, status=status, note=note)


def unit(Pe_W=1.75e6, eta=0.219, T_rej=550.0, efolds_ring=19.2, n_running=3, cone_deg=12.5, side_efolds=13.3, i=1):
    """One L2 unit's envelopes in unit-local coordinates (u from the bay's aft end, v radial from the bay floor r0, w tangential centre 0)."""
    Pt = Pe_W/eta; MWt = Pt/1e6; MWe = Pe_W/1e6; waste = Pt-Pe_W
    lam = LAM[i]
    ef = efolds_ring+math.log(max(1, n_running))          # combined exposure: n units in the same cone add their doses
    t_shadow = ef*lam
    t_side = side_efolds*lam
    depth = BAY['r1']-BAY['r0']; half = BAY['width']/2
    core_v = MWt/SPEC['core_MWt_per_m3'][i]; core_r = (core_v/(math.pi*1.3))**(1/3); core_L = 2.6*core_r      # L/D ~1.3
    vc = depth/2; env = []
    u = 0.3                                                # aft clearance to the module frame
    env.append(cyl('Reactor equipment envelope (vessel, core, reflector, drums)', 'PHYSICAL', 'REACTOR', u, u+core_L, vc, 0.0, core_r,
                   mass=500+0.3*MWt*1e3, status='OPEN', note='No internal design: an envelope at an assumed power density'))
    env.append(cyl('Thermal exclusion around the hot vessel (1100-1300 K)', 'THERMAL_EXCLUSION', 'REACTOR', u-0.3, u+core_L+0.05, vc, 0.0, core_r+0.3))
    r0 = core_r+0.05; r1 = r0+t_shadow*math.tan(math.radians(cone_deg))
    sh_vol = math.pi*t_shadow/3*(r0*r0+r0*r1+r1*r1)
    u_sh = u+core_L+0.05
    env.append(cyl('Shadow shield envelope (LiH + W, smeared)', 'PHYSICAL', 'SHIELD', u_sh, u_sh+t_shadow, vc, 0.0, r0, r1,
                   mass=sh_vol*RHO_SHIELD, status='OPEN', note=f'{ef:.1f} e-folds x {lam} m (combined exposure of {n_running} running units); '
                   'simplified attenuation, not a transport result'))
    # blade-facing slab: the unit's own blade rises radially above the bay (same azimuth), so the slab sits on the outward (v) side of the core
    slab_v0 = vc+core_r+0.05; slab_v1 = min(depth+0.6, slab_v0+t_side)          # the casing gap above r1 is ~1.3 m (to r 5.6)
    slab_fit = slab_v0+t_side <= depth+1.25
    slab_L = core_L+0.6
    slab = box('Blade-facing scatter shield (outward slab)', 'PHYSICAL', 'SHIELD', u-0.3, u-0.3+slab_L, slab_v0, slab_v0+t_side, -half+0.1, half-0.1,
               status='OPEN', note=f'{side_efolds:.1f} e-folds against single scatter from the own blade; fits under the casing: {slab_fit}')
    slab['mass_kg'] = slab['volume_m3']*RHO_SHIELD; env.append(slab)
    u_m = u_sh+t_shadow+0.2                              # machinery in the shadow
    ihx = SPEC['ihx_m3_per_MWt'][i]*MWt; pumps = SPEC['pumps_m3_per_MWt'][i]*MWt
    tac = SPEC['tac_m3_per_MWe'][i]*MWe; rec = SPEC['recuperator_m3_per_MWe'][i]*MWe; gc = SPEC['gas_cooler_m3_per_MW'][i]*waste/1e6
    pcu = SPEC['pcu_m3_per_MWe'][i]*MWe
    w_eq = 2.6; v_eq = depth-0.4                          # equipment cross-section inside the bay, leaving a 0.6 m service side
    def seg(name, fam, vol, mass, status='PROTOTYPE', note=''):
        nonlocal u_m
        L = max(0.4, vol/(w_eq*v_eq))
        b = box(name, 'PHYSICAL', fam, u_m, u_m+L, 0.2, 0.2+v_eq, -w_eq/2, w_eq/2, mass=mass, status=status, note=note)
        u_m += L+0.15
        return b
    env.append(seg('Primary pumps and intermediate heat exchanger', 'HEAT_TRANSPORT', ihx+pumps, 0.6*MWt*1e3*0.6))
    env.append(seg('Brayton turbo-alternator-compressor', 'CONVERSION', tac, 1.0*MWe*1e3))
    env.append(seg('Recuperator', 'CONVERSION', rec, 1.2*MWe*1e3))
    env.append(seg('Gas cooler (to the 550 K blade channel loop)', 'HEAT_TRANSPORT', gc, 0.4*MWe*1e3, note='reject temperature not approved (DR-03)'))
    env.append(seg('Power conditioning and plant switchgear', 'ELECTRICAL', pcu, 1.0*MWe*1e3))
    eq_end = u_m
    # coolant distribution to the blade root header: a radial riser through the casing at the bay's forward end
    env.append(box('Coolant riser to the blade-root header', 'INTERFACE', 'HEAT_TRANSPORT', eq_end-0.6, eq_end-0.2, depth-0.2, BAY['casing_r']-BAY['r0']+0.9,
                   -0.25, 0.25, note='crosses the casing: an OPEN pressure/thermal penetration'))
    env.append(box('Electrical interface to bus A/B (keel-lane side)', 'INTERFACE', 'ELECTRICAL', eq_end-1.4, eq_end-0.8, 0.2, 0.8, half-0.1, half+0.6))
    env.append(box('Data and control interface', 'INTERFACE', 'ELECTRICAL', eq_end-2.0, eq_end-1.6, 0.2, 0.6, half-0.1, half+0.5))
    # structure: two ring-frame attachments at the module ends and a sliding cradle under the hot section
    for k, uu in enumerate((0.0, min(eq_end, BAY['module_len']-2*BAY['end_gap']))):
        env.append(box(f'Structural attachment {k+1} (module frame)', 'ATTACHMENT', 'STRUCTURE', uu-0.1, uu+0.1, -0.1, depth+0.1, -half, half,
                       note='thrust-rated 1.5 g axial; sliding at the hot end for thermal growth'))
    # inspection envelopes
    env.append(box('Maintenance clearance (service side, 0.6-1.0 m)', 'MAINTENANCE', 'ACCESS', u_sh+t_shadow+0.2, eq_end, 0.2, depth, -half, -w_eq/2))
    env.append(box('Robotic access lane (keel-lane face)', 'ROBOTIC', 'ACCESS', 0.0, eq_end, 0.0, 0.8, half, half+0.8,
                   note='drones and the keel-lane manipulator; no crew while any unit in line of sight runs'))
    env.append(box('ORU removal path (radial, through a casing hatch)', 'REMOVAL', 'ACCESS', u_sh+t_shadow+0.2, eq_end, depth, BAY['casing_r']-BAY['r0']+0.3,
                   -w_eq/2, w_eq/2, note='ORUs leave radially; the reactor and shields are not ORUs (module swap between missions)'))
    total_len = eq_end+0.3
    m_phys = sum(e['mass_kg'] or 0.0 for e in env if e['cls'] == 'PHYSICAL')
    v_phys = sum(e['volume_m3'] for e in env if e['cls'] == 'PHYSICAL')
    return dict(Pe_W=Pe_W, eta=eta, Pt_W=Pt, waste_W=waste, T_rej_K=T_rej, envelopes=env, length_m=total_len,
                fits_one_module=total_len <= BAY['module_len']-2*BAY['end_gap'], slab_fits=slab_fit,
                shadow_t_m=t_shadow, side_t_m=t_side, shadow_kg=env[2]['mass_kg'], slab_kg=slab['mass_kg'],
                physical_mass_kg=m_phys, physical_volume_m3=v_phys, core_r_m=core_r, core_L_m=core_L)


def to_ship(e, x_aft, az_deg):
    """Ship-frame corner points of an envelope (8 for a box, 2 rings of 16 for a frustum) for the conflict screen and the Blender build."""
    a = math.radians(az_deg); ur = (0.0, math.cos(a), math.sin(a)); ut = (0.0, -math.sin(a), math.cos(a))
    def P(u, v, w):
        r = BAY['r0']+v
        return (x_aft+u, ur[1]*r+ut[1]*w, ur[2]*r+ut[2]*w)
    if e['shape'] == 'box':
        return [P(u, v, w) for u in e['u'] for v in e['v'] for w in e['w']]
    pts = []
    for u, r in zip(e['u'], e['r']):
        for k in range(16):
            t = 2*math.pi*k/16; pts.append(P(u, e['vc']+r*math.cos(t), r*math.sin(t)))
    return pts


def samples(e, x_aft, az_deg, step=0.25):
    a = math.radians(az_deg); ur = (math.cos(a), math.sin(a)); ut = (-math.sin(a), math.cos(a))
    out = []
    def frange(lo, hi):
        n = max(1, int((hi-lo)/step)); return [lo+(k+0.5)*(hi-lo)/n for k in range(n)]
    if e['shape'] == 'box':
        for u in frange(*e['u']):
            for v in frange(*sorted(e['v'])):
                for w in frange(*sorted(e['w'])):
                    r = BAY['r0']+v; out.append((x_aft+u, ur[0]*r+ut[0]*w, ur[1]*r+ut[1]*w))
    else:
        L = e['u'][1]-e['u'][0]
        for u in frange(*e['u']):
            rr = e['r'][0]+(e['r'][1]-e['r'][0])*(u-e['u'][0])/max(L, 1e-9)
            for v in frange(e['vc']-rr, e['vc']+rr):
                for w in frange(-rr, rr):
                    if (v-e['vc'])**2+w*w <= rr*rr:
                        r = BAY['r0']+v; out.append((x_aft+u, ur[0]*r+ut[0]*w, ur[1]*r+ut[1]*w))
    return out


def grid_lookup(survey):
    secs = {round(s['x'], 2): s for s in survey['sections']}; dyz = survey['dyz']
    xs = sorted(secs)
    def cls(p):
        x = min(xs, key=lambda q: abs(q-p[0])); s = secs[x]; g = s['grid']; n = (len(g)-1)//2
        iy = int(round(p[1]/dyz)); iz = int(round(p[2]/dyz))
        if abs(iy) > n or abs(iz) > n:
            return 'X'
        c = g[iy+n][iz+n]
        return 'X' if c == ' ' else c
    return cls


def district(name, placements, U, survey_cls, note=''):
    rows = []; conflicts = {}
    for k, (mod, az) in enumerate(placements):
        x_aft = BAY['bay_aft_x']+BAY['module_offsets'][mod]+BAY['end_gap']
        c = {}
        for e in U['envelopes']:
            if e['cls'] not in ('PHYSICAL', 'REMOVAL', 'ROBOTIC', 'MAINTENANCE'):
                continue
            for p in samples(e, x_aft, az, 0.3):
                q = survey_cls(p); c.setdefault(e['cls'], {}).setdefault(q, 0); c[e['cls']][q] += 1
        rows.append(dict(unit=k+1, module=f'M{mod+1}', azimuth_deg=az, x_aft=x_aft, x_fwd=x_aft+U['length_m'],
                         bus='A' if k % 2 == 0 else 'B', blade_header=f'BLADE_{int(az)}', samples=c))
        for cl, d in c.items():
            for q, n in d.items():
                conflicts.setdefault(cl, {}).setdefault(q, 0); conflicts[cl][q] += n
    headers = {}
    for r in rows:
        headers.setdefault(r['blade_header'], []).append(r['unit'])
    zones = {}
    for r in rows:
        zones.setdefault(r['module'], []).append(r['unit'])
    phys = conflicts.get('PHYSICAL', {}); tot = sum(phys.values()) or 1
    return dict(name=name, units=rows, note=note, headers=headers, shared_headers={h: u for h, u in headers.items() if len(u) > 1},
                damage_zones=zones, physical_overlap=dict(occupied=phys.get('O', 0)/tot, reserved=phys.get('R', 0)/tot,
                                                         dry_store=phys.get('D', 0)/tot, free=(phys.get('F', 0)+phys.get('U', 0))/tot,
                                                         outside=phys.get('X', 0)/tot), samples=conflicts)


def thermal_machinery(i=1):
    """Preliminary envelopes for the thermal and burn-power machinery by architecture (capacities from phase3/study.py when present)."""
    items = []
    def add(name, fam, cap_W, m3_per_MW, kg_per_kW, where, status='PROTOTYPE'):
        items.append(dict(name=name, family=fam, capacity_W=cap_W, volume_m3=cap_W/1e6*m3_per_MW[i], mass_kg=cap_W/1e3*kg_per_kW[i],
                          district=where, status=status))
    add('Burn heat pumps, Phase II running case (82 MW work)', 'HEAT_PUMP', 82e6, (0.4, 0.8, 1.5), (0.5, 1.5, 5.0), 'D2 aft bay / M1-M2', 'STUDY')
    add('Burn heat pumps, DR-01 working doctrine (backup for 1.2 MW margin)', 'HEAT_PUMP', 7e6, (0.4, 0.8, 1.5), (0.5, 1.5, 5.0), 'D2 aft bay', 'STUDY')
    add('L1 conversion, base burn loads (4.3 MWe)', 'L1_CONVERSION', 4.3e6, (1.0, 2.0, 3.5), (1.5, 3.0, 5.0), 'D2 aft bay beside Brayton A/B')
    add('L1 conversion with OPEN hot-loop pumps (nominal 45 MWe)', 'L1_CONVERSION', 45e6, (1.0, 2.0, 3.5), (1.5, 3.0, 5.0), 'D2 aft bay', 'OPEN')
    add('Engagement thermal buffer (1 GJ PCM at ~450 K)', 'THERMAL_BUFFER', 1e9/60, (1.0, 1.5, 2.5), (0.2, 0.3, 0.5), 'D5 WARM section roots')
    add('Hot-loop circulation pumps (OPEN 10-100 MW)', 'PUMPS', 40e6, (0.05, 0.1, 0.2), (0.2, 0.5, 1.0), 'D1/D2 blade roots', 'OPEN')
    add('Warm-loop pumps and distribution (5-7 MW)', 'PUMPS', 7e6, (0.1, 0.2, 0.4), (0.5, 1.0, 2.0), 'D5 / keel lanes')
    return items


def main():
    survey = json.loads((HERE/'results/survey.json').read_text())
    cls = grid_lookup(survey)
    configs = {
        'C-lean 3+1 x 1.75 MWe (Phase II reference)': dict(Pe=1.75e6, n=4, run=3,
                                                          place=[(0, 90.0), (0, 210.0), (0, 330.0), (1, 210.0)]),
        '2+1 x 2.66 MWe (one unit per blade)': dict(Pe=2.66e6, n=3, run=2, place=[(0, 90.0), (0, 210.0), (0, 330.0)]),
        '2 x 100 % x 5.3 MWe': dict(Pe=5.3e6, n=2, run=1, place=[(0, 90.0), (1, 330.0)]),
        '4+1 x 1.33 MWe (modular, two per blade except one)': dict(Pe=1.33e6, n=5, run=4,
                                                                 place=[(0, 90.0), (0, 210.0), (0, 330.0), (1, 90.0), (1, 330.0)]),
    }
    out = dict(status='ISSA Phase III STUDY / PROTOTYPE (NONCANON)', bay=BAY, rho_shield=RHO_SHIELD, units={}, districts={},
               thermal_machinery=thermal_machinery())
    for name, c in configs.items():
        U = unit(Pe_W=c['Pe'], n_running=c['run'])
        out['units'][name] = U
        out['districts'][name] = district(name, c['place'], U, cls)
    ref = out['units']['C-lean 3+1 x 1.75 MWe (Phase II reference)']
    out['reference_unit'] = ref
    out['bands'] = {b: {k: v for k, v in unit(i=i).items() if k != 'envelopes'} for i, b in enumerate(('low', 'nominal', 'high'))}
    (OUT/'phase3_eps_g1.json').write_text(json.dumps(out, indent=1))
    for name, U in out['units'].items():
        D = out['districts'][name]
        print(f"{name:52s} L {U['length_m']:5.2f} m fits {U['fits_one_module']} slab_fits {U['slab_fits']} shadow {U['shadow_t_m']:.2f} m {U['shadow_kg']/1e3:5.1f} t "
              f"slab {U['side_t_m']:.2f} m {U['slab_kg']/1e3:5.1f} t phys {U['physical_mass_kg']/1e3:5.1f} t {U['physical_volume_m3']:5.1f} m3 | overlap {({k: round(v, 3) for k, v in D['physical_overlap'].items()})} shared {D['shared_headers']}")
    print('bands', {b: (round(v['length_m'], 1), round(v['shadow_kg']/1e3, 1), round(v['slab_kg']/1e3, 1)) for b, v in out['bands'].items()})


if __name__ == '__main__':
    main()
