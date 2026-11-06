"""Fiji Drive revision geometry (lab/variants/fiji-drive study). Pure: standard library only, no bpy.

parts(s, prm) returns every part of the revision as a plain dict: name, collection key (00..12), function key (the viewport colour),
shape and its numbers. make_review.py turns them into Blender objects; intercept_scene() turns the drive's and ship's opaque parts into
ray absorbers for fiji_budget. Stations come from drive_manifold.geometry (LOCKED/WORKING); fiji_drive.toml holds the PROTOTYPE choices.

Shapes: ring (annular solid between x0 and x1 about an X-parallel axis, optionally in segments), torus (about any axis), tube (polyline),
box (centre, size, orthonormal frame), hexcell (hexagonal prism), loft (solid of revolution about an X-parallel axis).
"""
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'src/wayfarer'))

import drive_manifold as dm   # noqa: E402
import layout                 # noqa: E402

COLLECTIONS = {
    '00': ('00_DRIVE_STRUCTURE', 'STRUCTURE'), '01': ('01_FUSION_CORE', 'CORE'), '02': ('02_CONFINEMENT_COILS', 'COIL'),
    '03': ('03_FIJI_LATTICE', 'LATTICE'), '04': ('04_PLASMA_DISTRIBUTION', 'PLASMA'), '05': ('05_ENGINE_PORT_UPPER', 'ENGINE'),
    '06': ('06_ENGINE_STARBOARD_UPPER', 'ENGINE'), '07': ('07_ENGINE_PORT_LOWER', 'ENGINE'), '08': ('08_ENGINE_STARBOARD_LOWER', 'ENGINE'),
    '09': ('09_PROPELLANT', 'PROPELLANT'), '10': ('10_THERMAL', 'THERMAL'), '11': ('11_SHIELDING', 'SHIELDING'),
    '12': ('12_VISUALIZATION', 'VIS'),
}
# The owner's Fiji Drive palette (brief section 7): viewport RGBA and the nearest Blender collection tag.
PALETTE = {
    'STRUCTURE': ('Structural assemblies', (0.56, 0.56, 0.58, 1.0), 'COLOR_08'),
    'CORE': ('Fusion core (fuelling, heating, reaction zone)', (0.98, 0.46, 0.08, 1.0), 'COLOR_02'),
    'COIL': ('Electromagnetic coils', (0.16, 0.42, 0.95, 1.0), 'COLOR_05'),
    'LATTICE': ('Fiji lattice components', (0.58, 0.30, 0.90, 1.0), 'COLOR_06'),
    'PLASMA': ('Plasma transfer systems', (0.10, 0.85, 0.90, 1.0), 'COLOR_05'),
    'PROPELLANT': ('Propellant systems', (0.22, 0.75, 0.28, 1.0), 'COLOR_04'),
    'THERMAL': ('Thermal systems', (0.88, 0.14, 0.12, 1.0), 'COLOR_01'),
    'SHIELDING': ('Radiation shielding', (0.22, 0.22, 0.24, 1.0), 'COLOR_08'),
    'DIAGNOSTIC': ('Diagnostics and sensors', (0.98, 0.86, 0.12, 1.0), 'COLOR_03'),
    'ENGINE': ('Engine assembly (collection tag only)', (0.86, 0.16, 0.76, 1.0), 'COLOR_07'),
    'VIS': ('Visualization (display only)', (0.80, 0.80, 0.85, 1.0), 'NONE'),
}


def params():
    return tomllib.loads((HERE/'fiji_drive.toml').read_text())


def rad(a):
    return math.radians(a)


def polar(x, r, a, cy=0.0, cz=0.0):
    return (x, cy+r*math.cos(a), cz+r*math.sin(a))


def norm(v):
    n = math.sqrt(sum(c*c for c in v)); return tuple(c/n for c in v)


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def sub(a, b):
    return tuple(p-q for p, q in zip(a, b))


def add(a, b):
    return tuple(p+q for p, q in zip(a, b))


def mul(a, k):
    return tuple(p*k for p in a)


def frame_from(fwd, up_hint=(1.0, 0.0, 0.0)):
    """Orthonormal frame (u, v, w) with w along fwd."""
    w = norm(fwd); h = up_hint if abs(sum(p*q for p, q in zip(w, up_hint))) < .9 else (0.0, 0.0, 1.0)
    u = norm(cross(h, w)); v = cross(w, u)
    return (u, v, w)


class Parts(list):
    def add(self, coll, func, shape, name, **kw):
        self.append(dict(coll=coll, func=func, shape=shape, name=name, **kw))
        return self[-1]


def stations(s):
    g = dm.geometry(s); st = dict(g['stations'])
    return g, st


def engine_axes(s):
    p = s['prototype']; off = p['nozzle_offset_m']
    return [(yy*off, zz*off) for yy, zz in dm.quadrants(s)]


def engine_coils(s, prm):
    """Coil stations of one engine: throat coil at the inlet, then the expansion coils to the exit plane (u = 0 inlet .. 1 exit)."""
    p = s['prototype']; e = prm['engine']; _, st = stations(s)
    rt, rx = p['nozzle_throat_radius_m'], p['nozzle_exit_radius_m']; n = e['expansion_coils']
    out = []
    for k in range(n+1):
        u = k/n; ax = e['coil_axial_m'][k]
        r_env = rt+(rx-rt)*u**e['flare_exponent']
        bore = r_env+e['bore_margin_m']
        x_c = st['inlet']+(st['exit']-st['inlet'])*u
        x_c = min(st['inlet']-ax/2, max(st['exit']+ax/2, x_c))      # whole coil between the inlet and exit planes
        out.append(dict(k=k, u=u, x0=x_c-ax/2, x1=x_c+ax/2, x=x_c, envelope=r_env, bore=bore, outer=bore+e['coil_radial_m'][k]))
    return out


def parts(s, prm):
    P = Parts(); g, st = stations(s); p = s['prototype']
    c = prm['core']; mx = prm['mixing']; d = prm['distribution']; e = prm['engine']; pr = prm['propellant']; th = prm['thermal']
    sh = prm['shield']
    blade = [rad(p['radiator_phase_deg']+j*s['radiators']['separation_deg']) for j in range(s['radiators']['count'])]

    # ---------------- 01/02 fusion core and its coils ----------------
    core_coils = []
    x = st['core_aft']+c['coil_first_x_offset_m']
    for k in range(c['coil_count']):
        xc = x+k*c['coil_pitch_m']; core_coils.append(dict(name=f'CORE_COIL_{k+1:02}', x0=xc-c['coil_axial_m']/2, x1=xc+c['coil_axial_m']/2,
                                                           bore=c['coil_bore_m'], outer=c['coil_bore_m']+c['coil_radial_m']))
    ch = c['choke']; am = c['aft_mirror']
    core_coils.append(dict(name='CORE_CHOKE_FWD', x0=st['core_fwd']-ch['axial_m'], x1=st['core_fwd'], bore=ch['bore_m'], outer=ch['outer_m']))
    core_coils.append(dict(name='CORE_MIRROR_AFT', x0=st['core_aft'], x1=st['core_aft']+am['axial_m'], bore=am['bore_m'], outer=am['outer_m']))
    for cc in core_coils:
        P.add('02', 'COIL', 'ring', cc['name'], x0=cc['x0'], x1=cc['x1'], r0=cc['bore'], r1=cc['outer'], segments=c['segments'], gap_deg=1.5,
              role='Fiji-lattice HTS coil in a warm casing; forward choke closes the core, the aft mirror is the weaker exit (asymmetric mirror)', absorber=True)
        P.add('11', 'SHIELDING', 'ring', cc['name']+'_SHIELD_INSERT', x0=cc['x0']+.02, x1=cc['x1']-.02, r0=cc['bore']-c['coil_shield_m'], r1=cc['bore']-.005,
              role='W/B4C insert on the winding\'s plasma side: neutron and X-ray protection of the conductor', absorber=True)
        if cc['name'].startswith('CORE_COIL'):
            P.add('01', 'CORE', 'ring', cc['name']+'_LIMITER', x0=cc['x0']+.06, x1=cc['x1']-.06, r0=cc['bore']-c['coil_shield_m']-c['limiter_m'],
                  r1=cc['bore']-c['coil_shield_m']+.01, role='tungsten limiter ring: the edge strike point (no continuous first wall)', absorber=True)
        # Fiji lattice field-control inserts on the casing's forward face, outer rim
        for j in range(6):
            a = rad(30+60*j); r = cc['outer']-.18
            P.add('03', 'LATTICE', 'hexcell', f'{cc["name"]}_LATTICE_{j+1}', center=polar(cc['x1']+.05, r, a), normal=(1, 0, 0), radius=.16, height=.10,
                  role='Fiji lattice field-control insert: trims the coil field locally (fast, small corrections)')
        # coolant ring on the casing's outer edge (hot side: casing and limiter cooling, not the cryogenic winding)
        P.add('10', 'THERMAL', 'torus', cc['name']+'_COOLANT', center=((cc['x0']+cc['x1'])/2, 0, 0), axis=(1, 0, 0), radius=cc['outer']+.06, tube=.04,
              role='casing/limiter coolant ring to the drive hot loop')
    # coil cage bars
    xa, xf = st['core_aft'], st['core_fwd']
    for j in range(c['cage_bars']):
        a = rad(c['cage_phase_deg']+360/c['cage_bars']*j)
        P.add('00', 'STRUCTURE', 'tube', f'CORE_CAGE_BAR_{j+1}', points=[polar(xa, c['cage_bar_radius_m'], a), polar(xf, c['cage_bar_radius_m'], a)],
              radius=c['cage_bar_m'], role='coil-cage strongback: carries the coil-to-coil axial magnetic loads', absorber=True)
    # cage to primary rails (blade planes), pinned radial links with thermal-isolation standoffs
    for k, xs in enumerate([xa+.3, (xa+xf)/2, xf-.3]):
        for j, a in enumerate(blade):
            P.add('00', 'STRUCTURE', 'tube', f'CORE_CRADLE_LINK_{k+1}_{j+1}', points=[polar(xs, 4.52, a), polar(xs, 5.0, a)], radius=.09,
                  role='pin-jointed cradle link from the coil cage to the primary rail (core growth and cooldown slide here)')
            P.add('10', 'THERMAL', 'box', f'CORE_ISOLATOR_{k+1}_{j+1}', center=polar(xs, 4.47, a), size=(.26, .26, .12), frame=radial_frame(a),
                  role='low-conductance standoff: thermal isolation between the warm coil cage and the cradle')
    # NBI, ICRF, fueler, diagnostics
    nb = c['nbi']; xm = (xa+xf)/2
    gaps = [(core_coils[k]['x1'], core_coils[k+1]['x0']) for k in range(c['coil_count']-1)]
    mid_gap = gaps[len(gaps)//2]; xn = (mid_gap[0]+mid_gap[1])/2
    for j in range(nb['count']):
        a = rad(nb['phase_deg']+360/nb['count']*j); t = rad(nb['tangential_deg'])
        rdir = (0, math.cos(a), math.sin(a)); tdir = (0, -math.sin(a), math.cos(a))
        beam = norm(add(mul(rdir, -math.cos(t)), mul(tdir, math.sin(t))))           # pointing inward, slightly tangential
        port = polar(xn, nb['inner_r_m'], a); centre = sub(port, mul(beam, nb['length_m']/2))
        u, v, w = frame_from(beam)
        P.add('01', 'CORE', 'box', f'CORE_NBI_{j+1}', center=centre, size=(nb['width_m'], nb['height_m'], nb['length_m']), frame=(u, v, w),
              role=('neutral-beam injector (D or He-3 at ~1 MeV, tangential): fuels and heats the core and drives the FRC current; '
                    'ion source and neutraliser in the box, beam duct into the coil gap'), absorber=True)
        P.add('01', 'CORE', 'tube', f'CORE_NBI_{j+1}_DUCT', points=[sub(port, mul(beam, .25)), polar(xn, c['coil_bore_m']+.05, a)], radius=.22, role='NBI beam duct through the coil gap')
    ic = c['icrf']
    for gi, (g0, g1) in enumerate(gaps):
        if gi == len(gaps)//2:
            continue
        for j in range(ic['per_gap']):
            a = rad(45+180*j+30*gi)
            P.add('01', 'CORE', 'box', f'CORE_ICRF_{gi+1}_{j+1}', center=polar((g0+g1)/2, ic['radius_m'], a), size=(g1-g0+.04, ic['height_m']+.25, ic['depth_m']),
                  frame=radial_frame(a), role='ion-cyclotron antenna strap spanning the coil gap, carried by the two casings (core heating and hot-ion-mode control)')
    fu = c['fueler']
    P.add('01', 'CORE', 'ring', 'CORE_FUELER', x0=st['shield_aft']-fu['length_m'], x1=st['shield_aft'], r0=.18, r1=fu['radius_m'], segments=1,
          role='axial fueller: D and He-3 pellet/gas injectors fed through the shield sleeves, firing aft through the choke bore', absorber=True)
    dg = c['diagnostics']
    for cc in core_coils[:c['coil_count']]:
        for j in range(dg['per_coil']):
            a = rad(dg['phase_deg']+120*j+15)
            P.add('01', 'DIAGNOSTIC', 'box', f'{cc["name"]}_DIAG_{j+1}', center=polar(cc['x0']-.10, cc['outer']-.12, a), size=(dg['size_m'], dg['size_m'], dg['size_m']),
                  frame=radial_frame(a), role='magnetic probe / bolometer head on the casing (field, radiated power)')
    P.add('01', 'DIAGNOSTIC', 'box', 'CORE_INTERFEROMETER', center=polar(xn+.0, 5.2, rad(330)), size=(.5, .35, .7), frame=radial_frame(rad(330)),
          role='interferometer/Thomson laser head viewing the midplane through the NBI-free gap (density, temperature)')
    P.add('01', 'DIAGNOSTIC', 'box', 'CORE_NEUTRON_SPECTROMETER', center=polar(xa-.2, 4.9, rad(150)), size=(.6, .45, .45), frame=radial_frame(rad(150)),
          role='neutron/gamma spectrometer on the primary rail, aft of the core, outside the shadow cone (D-D rate, tritium burn)')

    # ---------------- mixing cell: hydrogen into the fusion-product stream ----------------
    for k, off in enumerate(mx['coils_x_offset_m']):
        xc = st['common_aft']+off
        P.add('02', 'COIL', 'ring', f'MIXING_COIL_{k+1}', x0=xc-mx['coil_axial_m']/2, x1=xc+mx['coil_axial_m']/2, r0=mx['coil_bore_m'],
              r1=mx['coil_bore_m']+mx['coil_radial_m'], segments=4, gap_deg=1.5, role='mixing-cell solenoid: guides the leaking core flux and the hydrogen plasma aft', absorber=True)
    xh = st['common_aft']+mx['h2_ring_offset_m']
    P.add('09', 'PROPELLANT', 'torus', 'H2_MAIN_INJECTION_RING', center=(xh, 0, 0), axis=(1, 0, 0), radius=mx['h2_ring_radius_m'], tube=.10,
          role='main hydrogen injection ring: reaction mass downstream of the burn (06!A54), 16 radial gas injectors')
    for j in range(mx['h2_injectors']):
        a = 2*math.pi*j/mx['h2_injectors']
        P.add('09', 'PROPELLANT', 'tube', f'H2_INJECTOR_{j+1:02}', points=[polar(xh, mx['h2_ring_radius_m'], a), polar(xh-.15, mx['coil_bore_m']-.05, a)], radius=.04,
              role='radial gas injector into the mixing cell edge (scrape-off layer)')
    offs = mx['coils_x_offset_m']
    for k in range(len(offs)-1):
        x0b = st['common_aft']+offs[k]+mx['coil_axial_m']/2-.02; x1b = st['common_aft']+offs[k+1]-mx['coil_axial_m']/2+.02
        if xh-.25 < x1b and xh+.25 > x0b:
            x1b = xh-.25
        P.add('03', 'LATTICE', 'ring', f'MIXING_COUPLING_BAND_{k+1}', x0=x0b, x1=x1b, r0=mx['coil_bore_m']+.06, r1=mx['coil_bore_m']+.20, segments=mx['coupling_bands'],
              gap_deg=12, role=('Fiji coupling band: drives field ripple at the fusion products\' gyro-frequency so their energy reaches the hydrogen '
                                'faster than collisions alone (the speculative coupling)'), absorber=True)
    for j in range(4):
        a = rad(90*j)
        P.add('00', 'STRUCTURE', 'tube', f'MANIFOLD_CAGE_BAR_{j+1}', points=[polar(st['common_fwd'], d['cage_bar_radius_m'], a), polar(st['manifold_aft']-.2, d['cage_bar_radius_m'], a)],
              radius=d['cage_bar_m'], role='mixing-cell and manifold coil cage (in the separatrix planes, clear of the four channels)', absorber=True)

    # ---------------- 04 plasma distribution ----------------
    tc = d['throat_coil']; xt = (st['throat_entry']+st['throat_exit'])/2
    saddles = [(f'MIXING_COIL_{k+1}', st['common_aft']+off, mx['coil_bore_m']+mx['coil_radial_m'], mx['coil_axial_m']) for k, off in enumerate(offs)]
    saddles.append(('THROAT_COIL', xt, tc['bore_m']+tc['radial_m'], tc['axial_m']))
    for nm_, xs_, ro_, ax_ in saddles:
        rb = d['cage_bar_radius_m']
        for j in range(4):
            a = rad(90*j)
            P.add('00', 'STRUCTURE', 'box', f'{nm_}_SADDLE_{j+1}', center=polar(xs_, (ro_+rb)/2, a), size=(ax_*.8, .22, rb-ro_+.10), frame=radial_frame(a),
                  role='coil saddle: carries the coil casing to the manifold cage bar (magnetic loads, cooldown slides on the bar)')
    P.add('02', 'COIL', 'ring', 'THROAT_COIL', x0=xt-tc['axial_m']/2, x1=xt+tc['axial_m']/2, r0=tc['bore_m'], r1=tc['bore_m']+tc['radial_m'], segments=4, gap_deg=1.5,
          role='convergence-throat coil (WORKING 1.5 m, waist ~2.4 m): compresses the mixed plasma before the split', absorber=True)
    sc = d['seed_coil']
    for k, coil in enumerate(g['coils'], 1):
        if abs(coil['x']-xt) < tc['axial_m']/2+sc['axial_m']/2+.05:
            continue
        P.add('02', 'COIL', 'ring', f'SEED_COIL_{k}', x0=coil['x']-sc['axial_m']/2, x1=coil['x']+sc['axial_m']/2, r0=sc['bore_m'], r1=sc['bore_m']+sc['radial_m'], segments=4,
              gap_deg=1.5, role='seed-manifold coil: base field and four-way topology (slow, heavy control)', absorber=True)
    for k, lat in enumerate(g['lattice'], 1):
        P.add('03', 'LATTICE', 'sector', f'LATTICE_SECTOR_L{k}', x0=min(lat['x0'], lat['x1']), x1=max(lat['x0'], lat['x1']), r0=lat['r_in'], r1=lat['r_out'],
              a0=lat['a0'], a1=lat['a1'], role='Fiji lattice sector L%d (WORKING): optically gated, shapes flux domain %d toward nozzle N%d' % (k, k, k), absorber=True)
        rows, cols = 4, 5
        for i in range(rows):
            for j in range(cols):
                xx = min(lat['x0'], lat['x1'])+(i+.5)*abs(lat['x1']-lat['x0'])/rows
                aa = lat['a0']+(j+.5)*(lat['a1']-lat['a0'])/cols+(.5/cols*(lat['a1']-lat['a0']) if i % 2 else 0)
                if aa > lat['a1']:
                    continue
                P.add('03', 'LATTICE', 'hexcell', f'LATTICE_CELL_L{k}_{i}{j}', center=polar(xx, lat['r_out']+.03, aa), normal=(0, math.cos(aa), math.sin(aa)),
                      radius=.19, height=.06, role='lattice cell face (the material\'s visible crystalline organisation)')
    sp = d['septum']; x_f = st['lattice_aft']+sp['x_fwd_offset_m']
    for j in range(4):
        a = rad(90*j)
        P.add('04', 'PLASMA', 'box', f'SEPTUM_{j+1}', center=polar((x_f+sp['x_aft_m'])/2, (sp['r0_m']+sp['r1_m'])/2, a),
              size=(sp['thickness_m'], sp['r1_m']-sp['r0_m'], x_f-sp['x_aft_m']), frame=septum_frame(a),
              role=('separatrix septum between two flux channels: X-point shaping coil inside, cooled strike faces on both sides '
                    '(the four-way split loses some edge plasma here, as a divertor does)'), absorber=True)
    for j, ((yy, zz), branch) in enumerate(zip(engine_axes(s), g['branches']), 1):
        n = len(branch)
        for i in range(d['guide_coils_per_channel']):
            k = int((i+1)*(n-1)/(d['guide_coils_per_channel']+1)); pt = branch[k]; tg = norm(sub(branch[min(k+1, n-1)], branch[max(k-1, 0)]))
            P.add('02', 'COIL', 'torus', f'CHANNEL_{j}_GUIDE_COIL_{i+1}', center=pt, axis=tg, radius=d['guide_coil']['mid_radius_m'], tube=d['guide_coil']['tube_m'],
                  role='flux-channel guide coil: holds the channel\'s flux tube on its bend toward the nozzle')
        ic_ = d['isolation_choke']; k = int(ic_['u']*(n-1)); pt = branch[k]; tg = norm(sub(branch[k+1], branch[max(k-1, 0)]))
        P.add('04', 'PLASMA', 'torus', f'CHANNEL_{j}_ISOLATION_CHOKE', center=pt, axis=tg, radius=ic_['mid_radius_m'], tube=ic_['tube_m'],
              role='emergency isolation choke: driven to full field it mirrors the channel shut (with its trim valve) for the channel-loss recovery')
        gc = d['guide_coil']; off = gc['mid_radius_m']+gc['tube_m']*.4

        def outer_pt(q, extra=0.0):
            # point radially outward of branch point q, on the guide-coil ring's outer side
            pt = branch[q]; rr = math.hypot(pt[1], pt[2]); a = math.atan2(pt[2], pt[1])
            return polar(pt[0], rr+off+extra, a), a
        P.add('00', 'STRUCTURE', 'tube', f'CHANNEL_{j}_COIL_STRONGBACK', points=[outer_pt(q)[0] for q in range(int(.05*(n-1)), int(.9*(n-1))+1, max(1, (n-1)//16))],
              radius=.07, role='guide-coil strongback along the channel\'s outer side: carries the guide coils and the field-control modules')
        for i in range(d['control_modules_per_channel']):
            k2 = int((.45+.3*i)*(n-1)); pt = branch[k2]; rr = math.hypot(pt[1], pt[2]); a = math.atan2(pt[2], pt[1])
            P.add('04', 'PLASMA', 'box', f'CHANNEL_{j}_FIELD_CONTROL_{i+1}', center=polar(pt[0], rr+off+.32, a), size=(.55, .45, .6), frame=radial_frame(a),
                  role='independent channel field-control module: power electronics for the channel\'s guide coils and lattice gate response')
        P.add('12', 'VIS', 'tube', f'VIS_CHANNEL_{j}_FLUX', points=list(branch), radius=s['drive_manifold']['plasma_branch_max_radius_m'], state='active',
              role='flux tube of channel %d (display): magnetised plasma follows field lines; no pipe' % j)

    # ---------------- 05-08 engines ----------------
    coils = engine_coils(s, prm); m = e['mount']; ring_r = s['structure']['ring_node_radius_m']
    for j, (cy, cz) in enumerate(engine_axes(s), 1):
        coll = f'{4+j:02}'; nm = e['names'][j-1]; pre = f'ENG_{j}_{nm}'
        a_eng = math.atan2(cz, cy)
        for co in coils:
            tag = 'THROAT' if co['k'] == 0 else f'EXP_{co["k"]}'
            P.add(coll, 'COIL', 'ring', f'{pre}_COIL_{tag}', x0=co['x0'], x1=co['x1'], r0=co['bore'], r1=co['outer'], cy=cy, cz=cz, segments=e['coil_segments'],
                  gap_deg=e['segment_gap_deg'], phase_deg=45.0,
                  role='magnetic-nozzle coil in a segmented annular casing; the bores open along the flare so the field diverges smoothly', absorber=True)
            if co['k'] >= 1:
                for i in range(e['trim_modules_per_coil']):
                    a = rad(360/e['trim_modules_per_coil']*i+22.5)
                    P.add(coll, 'LATTICE', 'hexcell', f'{pre}_TRIM_{co["k"]}_{i+1}', center=polar(co['x'], co['outer']+.05, a, cy, cz),
                          normal=(0, math.cos(a), math.sin(a)), radius=e['trim_module_m'], height=.10,
                          role='Fiji trim module: asymmetric field trim for thrust-vector control (5 deg normal, 8 deg emergency study)')
            P.add(coll, 'THERMAL', 'torus', f'{pre}_COOLANT_{tag}', center=(co['x1']+.05, cy, cz), axis=(1, 0, 0), radius=co['outer']-.06, tube=e['coolant_tube_m'],
                  role='casing coolant ring (strike modules and casing to the hot loop)')
        for i in range(e['tie_struts']):
            a = rad(e['tie_phase_deg']+360/e['tie_struts']*i)
            pts = [polar(co['x'], co['outer']+e['tie_m']*.6, a, cy, cz) for co in coils]
            P.add(coll, 'STRUCTURE', 'tube', f'{pre}_TIE_{i+1}', points=pts, radius=e['tie_m'],
                  role='tie strut: carries each coil\'s forward magnetic thrust to the mount collar (compression)', absorber=True)
        xin = st['inlet']
        P.add(coll, 'STRUCTURE', 'ring', f'{pre}_MOUNT_COLLAR', x0=xin, x1=xin+m['axial_m'], r0=m['collar_r0_m'], r1=m['collar_r1_m'], cy=cy, cz=cz, segments=1,
              role='mount collar: gathers the tie struts and passes the engine\'s thrust to three pinned links', absorber=True)
        # three pinned links: two to the neighbouring thrust-ring nodes, one to the central hub
        nodes = [a for a in (rad(90*q) for q in range(4)) if abs(math.remainder(a-a_eng, 2*math.pi)) < rad(50)]
        xr = st['ring']
        for q, a in enumerate(nodes, 1):
            tip = polar(xr-.9, ring_r-.4, a); base = polar(xin+m['axial_m'], m['collar_r1_m'], math.atan2(tip[2]-cz, tip[1]-cy), cy, cz)
            P.add(coll, 'STRUCTURE', 'tube', f'{pre}_LINK_RING_{q}', points=[base, tip], radius=m['link_m'], role='pinned thrust link to a thrust-ring node')
        hub = polar(xr-.9, 1.3, a_eng); base = polar(xin+m['axial_m'], m['collar_r0_m'], a_eng+math.pi, cy, cz)
        P.add(coll, 'STRUCTURE', 'tube', f'{pre}_LINK_HUB', points=[base, hub], radius=m['link_m'], role='pinned thrust link to the central thrust hub')
        ht = e['heating']; x1h = xin-ht['x0_offset_m']; x0h = x1h-ht['length_m']
        P.add(coll, 'PLASMA', 'ring', f'{pre}_INLET_ANTENNA', x0=x0h, x1=x1h, r0=ht['r0_m'], r1=ht['r1_m'], cy=cy, cz=cz, segments=6, gap_deg=8,
              role=('ion-cyclotron inlet antenna (a few MW, Brayton bus): ion anisotropy control for clean detachment and inlet stability; '
                    'not a thrust stage'), absorber=True)
        ti = e['trim_injector']; xi = xin-ti['offset_m']
        P.add(coll, 'PROPELLANT', 'torus', f'{pre}_TRIM_INJECTOR', center=(xi, cy, cz), axis=(1, 0, 0), radius=ti['radius_m'], tube=ti['tube_m'],
              role='hydrogen trim injector ring at the nozzle inlet: local mass-flow trim (thrust balance between the four nozzles)')
        for i in range(ti['stubs']):
            a = 2*math.pi*i/ti['stubs']
            P.add(coll, 'PROPELLANT', 'tube', f'{pre}_TRIM_STUB_{i+1}', points=[polar(xi, ti['radius_m'], a, cy, cz), polar(xi-.12, coils[0]['bore']-.02, a, cy, cz)], radius=.025,
                  role='trim injector stub')
        ex = coils[-1]
        for i in range(2):
            a = a_eng+rad(90+180*i)
            P.add(coll, 'DIAGNOSTIC', 'box', f'{pre}_PLUME_PROBE_{i+1}', center=polar(ex['x1']-.12, ex['outer']+e['diag']['size_m']/2-.01, a, cy, cz), size=(e['diag']['size_m'],)*3,
                  frame=radial_frame(a), role='plume imaging and Langmuir probe head at the exit coil (detachment monitor)')
        P.add(coll, 'DIAGNOSTIC', 'box', f'{pre}_FIELD_PROBE', center=polar(coils[2]['x'], coils[2]['outer']+.06, a_eng, cy, cz), size=(.14, .14, .14),
              frame=radial_frame(a_eng), role='magnetic field probe array (nozzle field shape and vector trim feedback)')
        # engine coolant / cryo header along the outer tie (a_eng side)
        a_h = a_eng+rad(e['tie_phase_deg']+30)
        P.add(coll, 'THERMAL', 'tube', f'{pre}_COOLANT_HEADER', points=[polar(co['x1']+.05, co['outer']+.22, a_h, cy, cz) for co in coils]+[polar(xin+.5, coils[0]['outer']+.22, a_h, cy, cz)],
              radius=.05, role='engine coolant header: collects the coil-casing rings, runs forward to the aft collection ring')
        # display: exhaust (active) and field-line hints
        P.add(coll, 'VIS', 'loft', f'{pre}_VIS_EXHAUST', profile=[(xin, .35), (coils[0]['x'], p['nozzle_throat_radius_m']*.7)]+[(co['x'], co['envelope']*.82) for co in coils[1:]]
              + [(st['exit']-3.0, p['nozzle_exit_radius_m']*1.25), (st['exit']-9.0, p['nozzle_exit_radius_m']*2.4)], cy=cy, cz=cz, state='active',
              role='exhaust display (active state only): follows the field envelope, then the detached plume diverges ~10 deg past the exit')
        for i in range(6):
            a = rad(60*i)
            pts = [polar(co['x'], co['envelope']*.95, a, cy, cz) for co in coils]+[polar(st['exit']-2.5, p['nozzle_exit_radius_m']*1.35, a, cy, cz)]
            P.add(coll, 'VIS', 'tube', f'{pre}_VIS_FIELD_{i+1}', points=[polar(xin+.3, coils[0]['envelope']*.8, a, cy, cz)]+pts, radius=.018, state='field',
                  role='nozzle field line (display): the solid rings make this field; the field is the nozzle wall')

    # ---------------- 09 propellant ----------------
    for name, a in (('D', rad(45)), ('HE3', rad(135))):
        xp = st['core_fwd']+.5; rf = math.hypot(2.6, 2.6)
        P.add('09', 'PROPELLANT', 'tube', f'FUEL_LINE_{name}', points=[polar(xp, rf, a), polar(xp, .9, a), polar(st['shield_aft']-.35, .5, a)],
              radius=pr['fuel_line_m'], role=(f'{name} fusion-fuel take-off: picks up the main-model cryo feed line (stepped shield sleeve) 0.5 m ahead of the '
                                              'choke face and turns it in to the axial fueller (metered separately, 15!A69)'))
    xh_ = pr['trim_header_x']
    P.add('09', 'PROPELLANT', 'torus', 'H2_TRIM_HEADER', center=(xh_, 0, 0), axis=(1, 0, 0), radius=pr['trim_header_radius_m'], tube=.08,
          role='hydrogen trim header behind the septa: feeds the four nozzle trim injectors through four isolation valves')
    P.add('09', 'PROPELLANT', 'tube', 'H2_TRIM_SUPPLY', points=[polar(xh, mx['h2_ring_radius_m'], rad(0)), polar(xh, 4.5, rad(0)), polar(xh_, 4.5, rad(0)),
                                                              polar(xh_, pr['trim_header_radius_m'], rad(0))], radius=pr['trim_line_m'],
          role='trim supply from the main injection ring (one take-off, on the septum plane)')
    for j, (cy, cz) in enumerate(engine_axes(s), 1):
        a = math.atan2(cz, cy); ti = e['trim_injector']; xi = st['inlet']-ti['offset_m']
        p0 = polar(xh_, pr['trim_header_radius_m'], a); p1 = polar(xh_-.6, 2.1, a); p2 = (xi+.25, cy+ti['radius_m']*.0, cz)
        p2 = polar(xi+.3, ti['radius_m'], a+math.pi, cy, cz)
        P.add('09', 'PROPELLANT', 'box', f'H2_TRIM_VALVE_{j}', center=p1, size=(pr['valve_m'],)*3, frame=radial_frame(a),
              role='isolation and trim valve for nozzle N%d (closes with the channel choke on a channel loss)' % j)
        P.add('09', 'PROPELLANT', 'tube', f'H2_TRIM_LINE_{j}', points=[p0, p1, p2, polar(xi, ti['radius_m'], a+math.pi, cy, cz)], radius=pr['trim_line_m'],
              role='trim line to the nozzle inlet injector')

    # ---------------- 10 thermal ----------------
    hx = th['hx']
    for j, a in enumerate(blade, 1):
        P.add('10', 'THERMAL', 'box', f'DRIVE_HX_{j}', center=polar((hx['x0']+hx['x1'])/2, (hx['r0_m']+hx['r1_m'])/2, a), size=(hx['width_m'], hx['r1_m']-hx['r0_m'], hx['x1']-hx['x0']),
              frame=septum_frame(a), role=('drive heat exchanger: core casings, limiters, coil shields and the shadow shield into the 1800 K hot loop; '
                                           'sits edge-on in the blade plane beside the blade root it feeds'), absorber=True)
        for q, xx in enumerate((hx['x0']+.6, hx['x1']-.6)):
            P.add('10', 'THERMAL', 'tube', f'DRIVE_HX_{j}_BLADE_{"FEED" if q else "RETURN"}', points=[polar(xx, hx['r1_m']-.1, a), polar(xx, 6.55, a)], radius=th['loop_m'],
                  role='hot-loop connection to the blade root trunk (feed / return)')
        P.add('10', 'THERMAL', 'tube', f'DRIVE_HX_{j}_CORE_LOOP', points=[polar(hx['x0']+.3, hx['r0_m']+.2, a-rad(5)), polar(hx['x0']+.3, 4.75, a-rad(5)), polar(st['core_aft']+.2, 4.75, a-rad(5))],
              radius=th['header_m']*1.4, role='core coolant loop to the HX')
        P.add('10', 'THERMAL', 'tube', f'DRIVE_HX_{j}_SHIELD_LOOP', points=[polar(hx['x1'], hx['r0_m']+.2, a), polar(st['shield_aft']-.2, 5.6, a)], radius=th['header_m']*1.4,
              role='shadow-shield coolant loop to the HX')
        P.add('10', 'THERMAL', 'tube', f'DRIVE_HX_{j}_AFT_LOOP', points=[polar(hx['x0']+.3, hx['r1_m']-.2, a+rad(5)), polar(hx['x0']+.3, 4.75, a+rad(5)), polar(st['common_aft'], 4.75, a+rad(5)),
                                                                     polar(th['aft_ring']['x'], th['aft_ring']['radius_m'], a+rad(6))],
              radius=th['header_m']*1.4, role='aft loop: engines, septa and manifold coils to the HX')
    ar = th['aft_ring']
    P.add('10', 'THERMAL', 'torus', 'DRIVE_AFT_COOLANT_RING', center=(ar['x'], 0, 0), axis=(1, 0, 0), radius=ar['radius_m'], tube=ar['tube_m'],
          role='aft coolant collection ring (four engines, four septa)')
    for j, (cy, cz) in enumerate(engine_axes(s), 1):
        a = math.atan2(cz, cy)+rad(e['tie_phase_deg']+30)
        P.add('10', 'THERMAL', 'tube', f'ENG_{j}_COOLANT_TO_RING', points=[polar(st['inlet']+.5, coils[0]['outer']+.22, a, cy, cz), polar(ar['x'], ar['radius_m'], math.atan2(cz, cy))],
              radius=.05, role='engine coolant to the aft ring')
    sr = th['shield_ring']
    P.add('10', 'THERMAL', 'torus', 'SHIELD_COOLANT_RING', center=(st['shield_aft']-.08, 0, 0), axis=(1, 0, 0), radius=sr['radius_m'], tube=sr['tube_m'],
          role='shadow-shield rim coolant manifold (the shield absorbs the forward cone of X-rays and neutrons)')

    # ---------------- 11 shield ----------------
    x = st['shield_aft']
    for k, layer in enumerate(sh['layers']):
        P.add('11', 'SHIELDING', 'ring', f'SHIELD_{k+1}_{layer["name"]}', x0=x, x1=x+layer['t_m'], r0=0.0 if k else 0.0, r1=p['shadow_radius_m']-(0 if k in (0, len(sh['layers'])-1) else .03),
              segments=1, role=layer['role'], absorber=(k == 0))
        x += layer['t_m']
    P.add('11', 'SHIELDING', 'ring', 'SHIELD_RIM_BAND', x0=st['shield_aft']-.02, x1=st['shield_fwd']+.02, r0=p['shadow_radius_m']-.02, r1=p['shadow_radius_m']+sh['rim_band_m'],
          segments=12, gap_deg=1.0, role='rim band: clamps the layers; bolted segments for layer replacement')

    # ---------------- 12 visualization: core plasma (active) ----------------
    P.add('12', 'VIS', 'loft', 'VIS_CORE_PLASMA', profile=[(st['core_fwd']-.6, .2), (st['core_fwd']-1.5, c['plasma_radius_m']*.85), ((xa+xf)/2, c['plasma_radius_m']),
                                                            (xa+.8, c['plasma_radius_m']*.9), (xa, 1.9), (st['common_aft'], 2.3), (st['throat_exit'], 2.0)],
          state='active', role='core plasma and the aft leak into the mixing cell (display)')
    return P


def radial_frame(a):
    """Box frame: u along X, v tangential, w radial outward."""
    return ((1, 0, 0), (0, -math.sin(a), math.cos(a)), (0, math.cos(a), math.sin(a)))


def septum_frame(a):
    """Plate in the plane through the axis at angle a: u (thickness) tangential, v radial, w along X."""
    return ((0, -math.sin(a), math.cos(a)), (0, math.cos(a), math.sin(a)), (1, 0, 0))


# ---------------- ray absorbers for the radiation-intercept Monte Carlo -------------------------------------------------------------

def _ring_hit(x0, x1, r0, r1, cy, cz):
    def hit(p, d):
        best = None
        py, pz = p[1]-cy, p[2]-cz
        for xp in (x0, x1):                                    # annulus faces
            if abs(d[0]) > 1e-12:
                t = (xp-p[0])/d[0]
                if t > 0:
                    y, z = py+t*d[1], pz+t*d[2]; rr = math.hypot(y, z)
                    if r0 <= rr <= r1 and (best is None or t < best):
                        best = t
        a = d[1]*d[1]+d[2]*d[2]
        if a > 1e-14:
            b = 2*(py*d[1]+pz*d[2]); c0 = py*py+pz*pz
            for r in (r0, r1):
                if r <= 0:
                    continue
                disc = b*b-4*a*(c0-r*r)
                if disc < 0:
                    continue
                sq = math.sqrt(disc)
                for t in ((-b-sq)/(2*a), (-b+sq)/(2*a)):
                    if t > 0 and x0 <= p[0]+t*d[0] <= x1 and (best is None or t < best):
                        best = t
        return best
    return hit


def _plane_rect_hit(a, x0, x1, r0, r1):
    n = (0, -math.sin(a), math.cos(a)); u = (0, math.cos(a), math.sin(a))
    def hit(p, d):
        dn = d[1]*n[1]+d[2]*n[2]
        if abs(dn) < 1e-12:
            return None
        t = -(p[1]*n[1]+p[2]*n[2])/dn
        if t <= 0:
            return None
        q = (p[0]+t*d[0], p[1]+t*d[1], p[2]+t*d[2]); r = q[1]*u[1]+q[2]*u[2]
        return t if (x0 <= q[0] <= x1 and r0 <= r <= r1) else None
    return hit


def _obb_hit(center, size, frame):
    def hit(p, d):
        tmin, tmax = -math.inf, math.inf; rel = sub(p, center)
        for ax, h in zip(frame, size):
            o = sum(a*b for a, b in zip(rel, ax)); dd = sum(a*b for a, b in zip(d, ax)); h = h/2
            if abs(dd) < 1e-12:
                if abs(o) > h:
                    return None
                continue
            t1, t2 = (-h-o)/dd, (h-o)/dd
            if t1 > t2:
                t1, t2 = t2, t1
            tmin, tmax = max(tmin, t1), min(tmax, t2)
            if tmin > tmax:
                return None
        return tmin if tmin > 0 else (tmax if tmax > 0 else None)
    return hit


def _segment_hit(a_pt, b_pt, radius):
    """Finite cylinder between two points (side surface only)."""
    ax = sub(b_pt, a_pt); L = math.sqrt(sum(c*c for c in ax)); w = mul(ax, 1/L)
    def hit(p, d):
        rel = sub(p, a_pt)
        dp = sub(d, mul(w, sum(x*y for x, y in zip(d, w)))); rp = sub(rel, mul(w, sum(x*y for x, y in zip(rel, w))))
        A = sum(c*c for c in dp); B = 2*sum(x*y for x, y in zip(dp, rp)); Cc = sum(c*c for c in rp)-radius*radius
        if A < 1e-14:
            return None
        disc = B*B-4*A*Cc
        if disc < 0:
            return None
        sq = math.sqrt(disc)
        for t in ((-B-sq)/(2*A), (-B+sq)/(2*A)):
            if t > 0:
                h = sum(x*y for x, y in zip(add(rel, mul(d, t)), w))
                if 0 <= h <= L:
                    return t
        return None
    return hit


def absorber(part):
    sh = part['shape']
    if sh == 'ring':
        return _ring_hit(part['x0'], part['x1'], part['r0'], part['r1'], part.get('cy', 0.0), part.get('cz', 0.0))
    if sh == 'sector':
        return _ring_hit(part['x0'], part['x1'], part['r0'], part['r1'], 0.0, 0.0) if False else _sector_hit(part)
    if sh == 'box':
        return _obb_hit(part['center'], part['size'], part['frame'])
    if sh == 'tube':
        pts = part['points']; hs = [_segment_hit(a, b, part['radius']) for a, b in zip(pts, pts[1:])]
        def hit(p, d):
            ts = [t for t in (h(p, d) for h in hs) if t is not None]
            return min(ts) if ts else None
        return hit
    return None


def _sector_hit(part):
    base = _ring_hit(part['x0'], part['x1'], part['r0'], part['r1'], 0.0, 0.0)
    def hit(p, d):
        t = base(p, d)
        if t is None:
            return None
        q = add(p, mul(d, t)); a = math.atan2(q[2], q[1]) % (2*math.pi)
        return t if part['a0'] <= a <= part['a1'] else None
    return hit


GROUPS = {'02': 'drive coils', '11': 'coil shield inserts and shadow shield', '01': 'core hardware (limiters, NBI, fueller)', '00': 'drive structure',
          '03': 'Fiji lattice', '04': 'septa and channel hardware', '10': 'heat exchangers'}


def intercept_scene(s, prm, variant='revision'):
    """Opaque parts that see the core plasma. variant 'revision' (open bay) or 'enclosed' (today's casing r 6.0 from the thrust ring to the
    shield plus a continuous core liner, the main-branch drive)."""
    p = s['prototype']; _, st = stations(s); c = prm['core']
    src = dict(x0=st['core_aft']+.3, x1=st['core_fwd']-.6, radius=c['plasma_radius_m']*.85)
    ab = []
    for part in parts(s, prm):
        if part.get('absorber'):
            h = absorber(part)
            if h:
                grp = 'engines' if part['coll'] in ('05', '06', '07', '08') else GROUPS.get(part['coll'], part['coll'])
                if part['name'].startswith('SHIELD_'):
                    grp = 'shadow shield'
                ab.append(dict(name=part['name'], group=grp, hit=h))
    # ship parts near the drive (from the built ship, 2026-11-02): hot blades (planes), blade root booms, primary frames, rails, thrust ring
    blade = [rad(p['radiator_phase_deg']+j*s['radiators']['separation_deg']) for j in range(s['radiators']['count'])]
    o = layout.origins(s)
    for j, a in enumerate(blade):
        ab.append(dict(name=f'blade_{j}', group='hot radiator blades', hit=_plane_rect_hit(a, o['RADIATOR_AFT'], o['RADIATOR_FRONT'], 6.5, 37.0)))
        ab.append(dict(name=f'rail_{j}', group='primary frames and rails', hit=_segment_hit(polar(-135.3, 5.1, a), polar(-111.2, 5.1, a), .12)))
    for k, xf in enumerate((-133.25, -130.25, -127.25, -123.25, -119.25, -115.25)):
        ab.append(dict(name=f'frame_{k}', group='primary frames and rails', hit=_ring_hit(xf-.12, xf+.12, 5.0, 7.2, 0, 0)))
    ab.append(dict(name='thrust_ring', group='thrust ring and hub', hit=_ring_hit(-136.25, -134.25, 5.0, 6.0, 0, 0)))
    ab.append(dict(name='thrust_hub', group='thrust ring and hub', hit=_ring_hit(-136.1, -134.4, 0.0, 1.8, 0, 0)))
    if variant == 'enclosed':
        ab.insert(0, dict(name='casing', group='hull casing (enclosed bay)', hit=_ring_hit(-134.0, st['shield_aft'], 6.0, 6.05, 0, 0)))
        ab.insert(0, dict(name='core_liner', group='continuous core liner (main)', hit=_ring_hit(st['core_aft']+.3, st['core_fwd']-.3, 3.8, 3.95, 0, 0)))
    return dict(source=src, absorbers=ab, protected=prm['protected'])


if __name__ == '__main__':
    from spec import load
    s = load(ROOT)[0]; ps = parts(s, params())
    from collections import Counter
    print(len(ps), Counter(p['coll'] for p in ps))
