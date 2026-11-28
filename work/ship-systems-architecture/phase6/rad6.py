"""ISSA Phase VI-E: OpenMC research workstream, Track R (STUDY, not engineering validation; surrogate source; no core design; no dose claim).

Builds on phase5/rad3d.py (same ship-frame CSG from the pure modules) and adds, kept apart:
  V6   void verification for neutrons AND photons against the point kernel (frames, placement, normalisation)
  D    deep-penetration benchmark: a 2 MeV pencil beam through the shield material (LiH + 6 vol% W, 1.9 t/m3), uncollided transmission vs
       exp(-Sigma_t x) from the same evaluated data, analog at 30 and 100 cm, and with MAGIC weight windows at the full 254 cm
  S6   shield present, source OUTSIDE the 12.5 deg cone: structural scatter + shield side-scatter
  TN   shield present, NEUTRON source INSIDE the cone, weight windows: direct transmission (uncollided) + scattered transmission, and the
       photon heating these neutrons make (shield and structure secondaries)
  TG   shield present, PHOTON source INSIDE the cone, weight windows: transmitted source photons
The bulkhead sits at the R5-A station (x 29.7; Phase V used the 700 K station 26.2). Heating is tallied per tank and per particle, then
summed by species (helium-3 on the 3 K stage, hydrogen/deuterium on the 20 K shields).

    PATH=/opt/mf/envs/omc/bin:$PATH OPENMC_CROSS_SECTIONS=/opt/nd/endfb80/cross_sections.xml \
      /opt/mf/envs/omc/bin/python work/ship-systems-architecture/phase6/rad6.py [particles]
Writes ../results/phase6_rad.json (summary only; statepoints stay in $RAD_RUNS).
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import openmc
import openmc.data

HERE = Path(__file__).resolve().parent
WORK = HERE.parent; ROOT = WORK.parents[1]
sys.path.insert(0, str(WORK/'phase5'))
import rad3d  # noqa: E402

spec, fs, habitat_ring, rt = rad3d.spec, rad3d.fs, rad3d.habitat_ring, rad3d.rt
CM = 100.0; UNITS = rad3d.UNITS; CONE = rad3d.CONE
X_BULK = 50.4-20.511-0.2
SHIELD = dict(r=1.0, x0=0.5, t=2.54, rho=1.9)          # Phase III shadow: 15.1 t, 7.97 m3 at 1.9 t/m3 (LiH + 6 vol% W), envelope PROTOTYPE
OUT = WORK/'results'/'phase6_rad.json'
RUNS = Path(os.environ.get('RAD_RUNS', '/tmp/issa_rad'))
XS = Path(os.environ.get('OPENMC_CROSS_SECTIONS', '/opt/nd/endfb80/cross_sections.xml')).parent


def shield_material():
    M = rt.mats()
    m = openmc.Material.mix_materials([M['lih'], M['w']], [0.94, 0.06], 'vo'); m.name = 'shield LiH+W'
    return m


def build(s, void=False, shield=True):
    rad3d._XP.clear(); rad3d._XC.clear(); XP, XC = rad3d.XP, rad3d.XC
    Mt = rad3d.materials(s); Mt['shield'] = shield_material()
    mat = (lambda k: None) if void else (lambda k: Mt[k])
    cells = []; tally = {}; used = []
    world = openmc.Sphere(x0=0, r=600*CM, boundary_type='vacuum')
    def add(name, region, m, t=False):
        c = openmc.Cell(name=name, region=region, fill=m); cells.append(c); used.append(region)
        if t: tally[name] = c
        return c
    xa, xb = XP(-140*CM), XP(93.4*CM); ci, co = XC(r=5.59*CM), XC(r=5.60*CM)
    sh_regs = []
    if shield:
        for k, (x, y, z) in enumerate(UNITS):
            reg = +XP((x+SHIELD['x0'])*CM) & -XP((x+SHIELD['x0']+SHIELD['t'])*CM) & -XC(y0=y*CM, z0=z*CM, r=SHIELD['r']*CM)
            add(f'shield_{k}', reg, mat('shield'), True); sh_regs.append(reg)
    cas = +xa & -xb & +ci & -co
    add('casing', cas, mat('al'))
    de = +XP(-95*CM) & -XP(-80*CM) & +XC(r=3.6*CM) & -ci
    for r_ in sh_regs: de = de & ~r_
    add('district_electronics', de, None, True)
    add('keel_lane', +XP(-75*CM) & -XP(-40*CM) & -ci, None, True)
    add('refuge', +XP(98*CM) & -XP(104*CM) & -XC(r=4.5*CM), None, True)
    r_in, r_out = XC(r=6.1*CM), XC(r=36.1*CM); bx0 = XP(-111.6*CM); blades = []
    for k, az in enumerate((90.0, 210.0, 330.0)):
        a = math.radians(az); n = (0.0, -math.sin(a), math.cos(a)); u = (0.0, math.cos(a), math.sin(a))
        p1 = openmc.Plane(a=n[0], b=n[1], c=n[2], d=-0.5); p2 = openmc.Plane(a=n[0], b=n[1], c=n[2], d=0.5); hp = openmc.Plane(a=u[0], b=u[1], c=u[2], d=0.0)
        reg = +p1 & -p2 & +hp & +r_in & -r_out & +bx0 & -xb; blades.append(reg); add(f'blade_{k}', reg, mat('blade'))
    bk = +XP(X_BULK*CM) & -XP(X_BULK*CM+0.3) & +r_in & -XC(r=37.0*CM)
    for b_ in blades: bk = bk & ~b_
    add('bulkhead', bk, mat('al'))
    rA, rB = habitat_ring.centers(s)
    for nm, xc in (('ring_A', rA), ('ring_B', rB)):
        add(nm, +XP((xc-2)*CM) & -XP((xc+2)*CM) & +XC(r=22*CM) & -XC(r=30*CM), mat('hab'), True)
    spc = {'helium-3': 'he3', 'deuterium': 'd2', 'hydrogen': 'h2'}; tk = []
    for t in fs.tanks(s):
        cy, cz, a = t['y'], t['z'], t['a']; x0, x1 = XP(t['x0']*CM), XP(t['x1']*CM)
        cin = XC(y0=cy*CM, z0=cz*CM, r=(a-0.02)*CM); cout = XC(y0=cy*CM, z0=cz*CM, r=a*CM)
        add(f'tankwall_{t["id"]}', +x0 & -x1 & +cin & -cout, mat('al'))
        add(f'tank_{t["id"]}', +x0 & -x1 & -cin, mat(spc[t['species']]), True)
        tk.append(dict(id=t['id'], species=t['species'], x0=t['x0'], x1=t['x1'], y=cy, z=cz, a=a-0.02))
    outer = -world
    for r_ in used: outer = outer & ~r_
    cells.append(openmc.Cell(name='space', region=outer))
    mats_ = openmc.Materials([] if void else list(Mt.values()))
    return openmc.Geometry(openmc.Universe(cells=cells)), mats_, tally, tk


def sources(S1, inside, particles_only=None):
    """inside=True: only the 12.5 deg cone about +x (into the shield); False: everything outside it."""
    out = []; mu_c = math.cos(math.radians(CONE))
    for kind, sp in (('neutron', S1['spectrum_n']), ('photon', S1['spectrum_g'])):
        if particles_only and kind != particles_only: continue
        p = np.array(sp); EB = np.array(S1['bounds_eV']); keep = p > 0
        ens = openmc.stats.Mixture(list(p[keep]/p[keep].sum()), [openmc.stats.Uniform(a, b) for a, b in zip(EB[:-1][keep], EB[1:][keep])])
        strength = S1['neutrons_leaking_per_fission'] if kind == 'neutron' else S1['photons_leaking_per_fission']
        lo, hi = (mu_c, 1.0) if inside else (-1.0, mu_c)
        for (x, y, z) in UNITS:
            ang = openmc.stats.PolarAzimuthal(mu=openmc.stats.Uniform(lo, hi), phi=openmc.stats.Uniform(0.0, 2*math.pi), reference_uvw=(1.0, 0.0, 0.0), reference_vwu=(0.0, 1.0, 0.0))
            out.append(openmc.IndependentSource(space=openmc.stats.Point((x*CM, y*CM, z*CM)), angle=ang, energy=ens, particle=kind, strength=strength*(hi-lo)/2))
    return out


def tallies(tc, void):
    cf = openmc.CellFilter(list(tc.values())); pf = openmc.ParticleFilter(['neutron', 'photon'])
    t1 = openmc.Tally(name='flux'); t1.filters = [cf, pf]; t1.scores = ['flux']
    t2 = openmc.Tally(name='unc'); t2.filters = [cf, pf, openmc.CollisionFilter([0])]; t2.scores = ['flux']
    T = [t1, t2]
    if not void:
        t3 = openmc.Tally(name='heat'); t3.filters = [cf, pf]; t3.scores = ['heating']; T.append(t3)
    return openmc.Tallies(T)


def ww_mesh(lo, hi, dims):
    m = openmc.RegularMesh(); m.lower_left = lo; m.upper_right = hi; m.dimension = dims; return m


def _ww(d):
    """read the generated windows and cap splitting (a vacuum-heavy mesh otherwise splits without bound)"""
    w = openmc.hdf5_to_wws(str(d/'weight_windows.h5'))
    for x in w:
        x.max_split = 20; x.weight_cutoff = 1e-38
    return w


def execute(name, model, ww=None, particle='neutron', iters=2):
    """Run; with ww=(mesh, energy bounds) first iterate MAGIC weight windows (generated at the end of each iteration, never applied uncapped
    inside it: on-the-fly windows without the split cap ran away in the ship model), then run with them fixed and capped."""
    d = RUNS/f'p6_{name}'; d.mkdir(parents=True, exist_ok=True); t0 = time.time(); info = {}
    if ww:
        mesh, eb = ww
        for k in range(iters):
            st = model.settings; st.weight_window_generators = openmc.WeightWindowGenerator(mesh, energy_bounds=eb, particle_type=particle, method='magic',
                                                                                             max_realizations=st.batches, update_interval=st.batches, on_the_fly=False)
            if k > 0:
                st.weight_windows = _ww(d); st.weight_windows_on = True
            model.run(cwd=d, threads=4, output=False)
        st = model.settings; st.weight_window_generators = []; st.weight_windows = _ww(d); st.weight_windows_on = True
        info['ww_iterations'] = iters
    if ww:
        model.settings.max_history_splits = 1000
    sp = openmc.StatePoint(model.run(cwd=d, threads=4, output=False)); info['runtime_s'] = time.time()-t0
    return sp, info


def cells_out(sp, tc, void):
    names = list(tc); res = {}
    def get(tn, score='flux'):
        t = sp.get_tally(name=tn); return t.get_values(scores=[score]).reshape(-1), t.get_values(scores=[score], value='rel_err').reshape(-1)
    fl, fe = get('flux'); un, ue = get('unc')
    if not void: hh, he = get('heat', 'heating')
    for i, n in enumerate(names):
        r = dict(flux_n=fl[2*i], flux_n_rel=fe[2*i], flux_g=fl[2*i+1], flux_g_rel=fe[2*i+1], unc_n=un[2*i], unc_n_rel=ue[2*i], unc_g=un[2*i+1], unc_g_rel=ue[2*i+1])
        if not void: r.update(heat_n_eV=hh[2*i], heat_n_rel=he[2*i], heat_g_eV=hh[2*i+1], heat_g_rel=he[2*i+1])
        res[n] = {k: float(v) for k, v in r.items()}
    return res


def ship_run(name, s, S1, inside, particles, particle=None, ww=False):
    geo, mats_, tc, tk = build(s, shield=True)
    st = openmc.Settings(); st.run_mode = 'fixed source'; st.batches = 10; st.particles = particles//10
    st.source = sources(S1, inside, particle); st.photon_transport = True; st.output = {'tallies': False}
    model = openmc.Model(geometry=geo, materials=mats_, settings=st, tallies=tallies(tc, False))
    w = (ww_mesh((-100*CM, -40*CM, -40*CM), (145*CM, 40*CM, 40*CM), (25, 8, 8)), [0.0, 1e5, 2e7]) if ww else None
    sp, info = execute(name, model, w, particle or 'neutron')
    return cells_out(sp, tc, False), info, tk


def slab_benchmark(t_cm, particles, ww):
    """2 MeV pencil beam along +x into a cylinder of shield material (r 50 cm, thickness t); a 1 cm thick, r 10 cm detector behind it.
    Uncollided track length = transmission x 1 cm, compared with exp(-Sigma_t t) from the same HDF5 data (where it is measurable);
    the total (collided) flux is what deep penetration needs: analog and weight-window runs are compared where both score, and the
    weight windows alone reach the full 254 cm."""
    m = shield_material(); E = 2.0e6
    sig = 0.0
    for nuc, N in m.get_nuclide_atom_densities().items():
        d = openmc.data.IncidentNeutron.from_hdf5(str(XS/'neutron'/f'{nuc}.h5'))
        sig += N*d[1].xs['294K'](E)                  # 1/cm (atoms/b-cm x b)
    x0 = openmc.XPlane(0.0); x1 = openmc.XPlane(t_cm); x2 = openmc.XPlane(t_cm+1.0); cyl = openmc.XCylinder(r=50.0); det = openmc.XCylinder(r=10.0)
    world = openmc.Sphere(r=t_cm+200.0, boundary_type='vacuum')
    slab = openmc.Cell(region=+x0 & -x1 & -cyl, fill=m); dc = openmc.Cell(region=+x1 & -x2 & -det)
    rest = openmc.Cell(region=-world & ~(+x0 & -x1 & -cyl) & ~(+x1 & -x2 & -det))
    geo = openmc.Geometry([slab, dc, rest])
    st = openmc.Settings(); st.run_mode = 'fixed source'; st.batches = 10; st.particles = particles//10; st.photon_transport = False
    st.source = openmc.IndependentSource(space=openmc.stats.Point((-1.0, 0, 0)), angle=openmc.stats.Monodirectional((1.0, 0, 0)), energy=openmc.stats.Discrete([E], [1.0]))
    t = openmc.Tally(name='unc'); t.filters = [openmc.CellFilter([dc]), openmc.CollisionFilter([0])]; t.scores = ['flux']
    t2 = openmc.Tally(name='tot'); t2.filters = [openmc.CellFilter([dc])]; t2.scores = ['flux']
    model = openmc.Model(geometry=geo, materials=openmc.Materials([m]), settings=st, tallies=openmc.Tallies([t, t2]))
    w = (ww_mesh((-2.0, -50.0, -50.0), (t_cm+2.0, 50.0, 50.0), (max(8, int(t_cm/5)), 1, 1)), [0.0, 1e5, 2.1e6]) if ww else None
    sp, info = execute(f'D{int(t_cm)}{"w" if ww else ""}', model, w, 'neutron', iters=6)
    def g(n):
        tt = sp.get_tally(name=n); return (float(tt.get_values(scores=['flux']).reshape(-1)[0]), float(tt.get_values(scores=['flux'], value='rel_err').reshape(-1)[0]))
    (v, e), (vt, et) = g('unc'), g('tot')
    ana = math.exp(-sig*t_cm)
    return dict(t_cm=t_cm, sigma_t_cm=sig, analytic=ana, openmc=v, rel_err=e, ratio=v/ana if ana and v else None, total=vt, total_rel_err=et,
                fom=1.0/(et**2*info['runtime_s']) if et == et and et > 0 else None, weight_windows=ww, **info)


def main():
    particles = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
    s = spec.load()[0]
    S1 = json.loads((WORK/'results'/'phase4_rad_wayfarer.json').read_text())['S1']
    out = dict(solver=f'OpenMC {openmc.__version__}', library='ENDF/B-VIII.0 (NNDC HDF5)', particles=particles, bulkhead_x=X_BULK, shield=SHIELD,
               status='3-D TRANSPORT-INFORMED, Track R (surrogate source, simplified structure); not validated; no dose or crew-safety claim',
               source_provenance=dict(spectrum='Phase IV S1: OpenMC k-eigenvalue leakage spectrum of a simplified UN / Li / Mo surrogate core (not a design)',
                                      k_eff=S1['k_eff'], k_sigma=S1['k_sigma'], neutrons_per_fission=S1['neutrons_leaking_per_fission'],
                                      photons_per_fission=S1['photons_leaking_per_fission'], mean_E_n_eV=S1['mean_leak_energy_n_eV'], mean_E_g_eV=S1['mean_leak_energy_g_eV'],
                                      placement='three isotropic point sources at the L2 unit centres (x -84, r 2.9)',
                                      normalisation='per fission in each unit; x fission rate of a 750 K unit at full power downstream'),
               runs={})
    # V6: void verification, neutrons and photons
    geo, mats_, tc, tk = build(s, void=True, shield=False); K = rad3d.kernel(tk)
    ver = {}
    for part, S in (('neutron', S1['neutrons_leaking_per_fission']), ('photon', S1['photons_leaking_per_fission'])):
        st = openmc.Settings(); st.run_mode = 'fixed source'; st.batches = 10; st.particles = particles//20
        st.source = rad3d.sources(S1, False, part); st.photon_transport = False; st.output = {'tallies': False}
        sp, info = execute(f'V6{part[0]}', openmc.Model(geometry=geo, materials=mats_, settings=st, tallies=tallies(tc, True)))
        res = cells_out(sp, tc, True); key = 'flux_n' if part == 'neutron' else 'flux_g'
        rows = [dict(tank=t['id'], ratio=res[f'tank_{t["id"]}'][key]/(len(UNITS)*S)/K[t['id']], rel_err=res[f'tank_{t["id"]}'][key+'_rel']) for t in tk]
        r_ = [r['ratio'] for r in rows]
        ver[part] = dict(rows=rows, min=min(r_), max=max(r_), mean=sum(r_)/len(r_), passes=0.95 < sum(r_)/len(r_) < 1.05, **info)
    out['runs']['V6'] = ver
    # D: deep-penetration benchmark ladder
    out['runs']['D'] = [slab_benchmark(tc, particles//4, w) for tc, w in ((10.0, False), (20.0, False), (40.0, False), (60.0, False), (60.0, True),
                                                                          (100.0, False), (100.0, True), (254.0, False), (254.0, True))]
    # ship runs
    rS, iS, tk = ship_run('S6', s, S1, False, particles)
    rTN, iTN, _ = ship_run('TN', s, S1, True, particles, 'neutron', ww=True)
    rTG, iTG, _ = ship_run('TG', s, S1, True, particles, 'photon', ww=True)
    out['runs']['S6'] = dict(cells=rS, **iS); out['runs']['TN'] = dict(cells=rTN, **iTN); out['runs']['TG'] = dict(cells=rTG, **iTG)
    out['tanks'] = tk
    OUT.write_text(json.dumps(out, indent=1, default=float))
    print('V6', {k: (round(v['mean'], 3), round(v['min'], 3), round(v['max'], 3)) for k, v in ver.items()})
    print('D', [(d['t_cm'], d['weight_windows'], f"{d['analytic']:.2e}", f"{d['openmc']:.2e}", round(d['rel_err'], 3), f"{d['total']:.2e}", round(d['total_rel_err'], 3)) for d in out['runs']['D']])
    print('times', round(iS['runtime_s']), round(iTN['runtime_s']), round(iTG['runtime_s']))


if __name__ == '__main__':
    main()
