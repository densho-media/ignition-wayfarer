"""ISSA Phase V-E: first 3-D OpenMC model of Wayfarer in the ship frame (STUDY, not engineering validation; no core or fuel design).

Geometry from the shared pure modules (fuel_storage.tanks, habitat_ring, the EPS-G1 district, radiator stations), never from visual meshes:
casing shell, three radiator blades (hot and forward sections) as thin slabs, the relocated graded bulkhead, 13 cryogenic tanks with Al walls
and their liquids, rings A/B as habitat-averaged annuli, and tally regions for the district electronics, the keel maintenance lane and the
refuge. Sources: the Phase IV S1 surrogate leakage spectra (neutron and photon) at the three L2 unit positions.

Three runs, kept apart:
  V  verification: every cell void; the track-length flux in each tank volume must equal the point kernel 1/(4 pi d^2) averaged over
     that volume (checks coordinate frames, cell placement and tally normalisation).
  B  bare: full materials, isotropic sources; total and uncollided (CollisionFilter bin 0) flux and heating per region.
  S  shadowed: the forward shadow-cone (12.5 deg about +x) is removed from the source; what reaches the tanks, rings and refuge is
     radiation that left OUTSIDE the shield cone and scattered from structure (the through-shield part is analytic, S2 relaxation).
     The shield's own side-scatter is not modelled (stated limitation).

    PATH=/opt/mf/envs/omc/bin:$PATH OPENMC_CROSS_SECTIONS=/opt/nd/endfb80/cross_sections.xml \
      /opt/mf/envs/omc/bin/python work/ship-systems-architecture/phase5/rad3d.py [particles]
Writes ../results/phase5_rad3d.json (small summary only; statepoints stay in $RAD_RUNS).
"""
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import openmc

HERE = Path(__file__).resolve().parent
WORK = HERE.parent; ROOT = WORK.parents[1]
sys.path.insert(0, str(ROOT/'src/wayfarer')); sys.path.insert(0, str(WORK/'radiation'))
import spec  # noqa: E402
import fuel_storage as fs  # noqa: E402
import habitat_ring  # noqa: E402
import wayfarer_rt as rt  # noqa: E402

OUT = WORK/'results'/'phase5_rad3d.json'
RUNS = Path(os.environ.get('RAD_RUNS', '/tmp/issa_rad'))
CM = 100.0
UNITS = [(-84.0, 2.9*math.cos(math.radians(a)), 2.9*math.sin(math.radians(a))) for a in (90.0, 210.0, 330.0)]
CONE = 12.5
X_BULK = 26.2


def materials(s):
    M = rt.mats()
    dens = s['fuel_storage']['density_kg_m3']
    he3 = openmc.Material(name='He3'); he3.add_nuclide('He3', 1.0); he3.set_density('g/cm3', dens['helium_3']/1e3)
    d2 = openmc.Material(name='D2'); d2.add_nuclide('H2', 1.0); d2.set_density('g/cm3', dens['deuterium']/1e3)
    h2 = openmc.Material(name='H2'); h2.add_nuclide('H1', 1.0); h2.set_density('g/cm3', dens['hydrogen']/1e3)
    cc = openmc.Material(name='blade'); cc.add_nuclide('C12', 0.9); cc.add_nuclide('Mo96', 0.02); cc.add_nuclide('Li7', 0.08); cc.set_density('g/cm3', 1.9)
    hab = openmc.Material(name='habitat'); hab.add_nuclide('Al27', 0.4); hab.add_nuclide('H1', 0.4); hab.add_nuclide('O16', 0.2); hab.set_density('g/cm3', 0.25)
    return dict(al=M['al'], he3=he3, d2=d2, h2=h2, blade=cc, hab=hab)


_XP = {}


def XP(x):
    """one XPlane per station: coincident duplicate surfaces trap particles in OpenMC"""
    k = round(x, 4)
    if k not in _XP: _XP[k] = openmc.XPlane(k)
    return _XP[k]


_XC = {}


def XC(r, y0=0.0, z0=0.0):
    k = (round(y0, 4), round(z0, 4), round(r, 4))
    if k not in _XC: _XC[k] = openmc.XCylinder(y0=k[0], z0=k[1], r=k[2])
    return _XC[k]


def build(s, void=False):
    _XP.clear(); _XC.clear()
    Mt = materials(s); mat = (lambda k: None) if void else (lambda k: Mt[k])
    cells = []; tally_cells = {}
    world = openmc.Sphere(x0=0, r=600*CM, boundary_type='vacuum')
    used = []                                   # regions to subtract from the outer void
    def add(name, region, m, tally=False):
        c = openmc.Cell(name=name, region=region, fill=m); cells.append(c); used.append(region)
        if tally: tally_cells[name] = c
        return c
    # casing shell (1 cm Al) r 5.6 m, x -140 .. 93.4
    xa, xb = XP(-140*CM), XP(93.4*CM)
    ci, co = XC(r=5.59*CM), XC(r=5.60*CM)
    add('casing', +xa & -xb & +ci & -co, mat('al'))
    # tally regions inside the casing
    de_in = XC(r=3.6*CM)
    add('district_electronics', +XP(-95*CM) & -XP(-80*CM) & +de_in & -ci, None, True)
    add('keel_lane', +XP(-75*CM) & -XP(-40*CM) & -ci, None, True)
    add('refuge', +XP(98*CM) & -XP(104*CM) & -XC(r=4.5*CM), None, True)
    # blades: three 1 cm slabs (radial half-planes) r 6.1-36.1, x -111.6 .. 93.4 (hot + L2 + WARM + LOW; graded temperature irrelevant here)
    r_in, r_out = XC(r=6.1*CM), XC(r=36.1*CM)
    bx0, bx1 = XP(-111.6*CM), xb
    blades = []
    for k, az in enumerate((90.0, 210.0, 330.0)):
        a = math.radians(az); n = (0.0, -math.sin(a), math.cos(a)); u = (0.0, math.cos(a), math.sin(a))
        p1 = openmc.Plane(a=n[0], b=n[1], c=n[2], d=-0.5); p2 = openmc.Plane(a=n[0], b=n[1], c=n[2], d=0.5)
        hp = openmc.Plane(a=u[0], b=u[1], c=u[2], d=0.0)
        reg = +p1 & -p2 & +hp & +r_in & -r_out & +bx0 & -bx1; blades.append(reg)
        add(f'blade_{k}', reg, mat('blade'))
    # relocated graded bulkhead: three 1 mm Al-equivalent layers as one 3 mm disk at x 26.2, r 6.1-37
    bk = +XP(X_BULK*CM) & -XP(X_BULK*CM+0.3) & +r_in & -XC(r=37.0*CM)
    for b_ in blades: bk = bk & ~b_
    add('bulkhead', bk, mat('al'))
    # rings A/B: habitat-averaged annuli x +-2 m, r 22-30 m
    rA, rB = habitat_ring.centers(s)
    for nm, xc in (('ring_A', rA), ('ring_B', rB)):
        add(nm, +XP((xc-2)*CM) & -XP((xc+2)*CM) & +XC(r=22*CM) & -XC(r=30*CM), mat('hab'), True)
    # tanks: Al wall 2 cm + liquid, cylinders along x at their (y, z)
    tk = []
    spc = {'helium-3': 'he3', 'deuterium': 'd2', 'hydrogen': 'h2'}
    for t in fs.tanks(s):
        cy, cz, a = t['y'], t['z'], t['a']
        x0, x1 = XP(t['x0']*CM), XP(t['x1']*CM)
        cin = XC(y0=cy*CM, z0=cz*CM, r=(a-0.02)*CM); cout = XC(y0=cy*CM, z0=cz*CM, r=a*CM)
        add(f'tankwall_{t["id"]}', +x0 & -x1 & +cin & -cout, mat('al'))
        add(f'tank_{t["id"]}', +x0 & -x1 & -cin, mat(spc[t['species']]), True)
        tk.append(dict(id=t['id'], species=t['species'], x0=t['x0'], x1=t['x1'], y=cy, z=cz, a=a-0.02))
    outer = -world
    for r_ in used: outer = outer & ~r_
    cells.append(openmc.Cell(name='space', region=outer))
    geo = openmc.Geometry(openmc.Universe(cells=cells))
    mats_ = openmc.Materials([] if void else list(Mt.values()))
    return geo, mats_, tally_cells, tk


def sources(S1, shadowed, particles_only=None):
    out = []
    mu_max = math.cos(math.radians(CONE)) if shadowed else 1.0
    for kind, spec_ in (('neutron', S1['spectrum_n']), ('photon', S1['spectrum_g'])):
        if particles_only and kind != particles_only: continue
        p = np.array(spec_); EB = np.array(S1['bounds_eV']); keep = p > 0
        ens = openmc.stats.Mixture(list(p[keep]/p[keep].sum()), [openmc.stats.Uniform(a, b) for a, b in zip(EB[:-1][keep], EB[1:][keep])])
        strength = S1['neutrons_leaking_per_fission'] if kind == 'neutron' else S1['photons_leaking_per_fission']
        for (x, y, z) in UNITS:
            ang = openmc.stats.PolarAzimuthal(mu=openmc.stats.Uniform(-1.0, mu_max), phi=openmc.stats.Uniform(0.0, 2*math.pi), reference_uvw=(1.0, 0.0, 0.0), reference_vwu=(0.0, 1.0, 0.0))
            out.append(openmc.IndependentSource(space=openmc.stats.Point((x*CM, y*CM, z*CM)), angle=ang, energy=ens, particle=kind,
                                                strength=strength*(1+mu_max)/2))
    return out


def run(name, geo, mats_, tcells, src, particles, void=False):
    st = openmc.Settings(); st.run_mode = 'fixed source'; st.batches = 10; st.particles = particles // 10
    st.source = src; st.photon_transport = not void; st.output = {'tallies': False}
    tl = openmc.Tallies()
    cf = openmc.CellFilter(list(tcells.values())); pf = openmc.ParticleFilter(['neutron', 'photon'])
    t1 = openmc.Tally(name='flux'); t1.filters = [cf, pf]; t1.scores = ['flux']
    t2 = openmc.Tally(name='unc'); t2.filters = [cf, pf, openmc.CollisionFilter([0])]; t2.scores = ['flux']
    tl += [t1, t2]
    if not void:
        t3 = openmc.Tally(name='heat'); t3.filters = [cf]; t3.scores = ['heating']; tl.append(t3)
    model = openmc.Model(geometry=geo, materials=mats_, settings=st, tallies=tl)
    d = RUNS/f'p5_{name}'; d.mkdir(parents=True, exist_ok=True)
    t0 = time.time(); sp = openmc.StatePoint(model.run(cwd=d, threads=4, output=False)); dt = time.time()-t0
    names = list(tcells); res = {}
    def get(tn, score='flux'):
        t = sp.get_tally(name=tn); return t.get_values(scores=[score]).reshape(-1), t.get_values(scores=[score], value='rel_err').reshape(-1)
    fl, fe = get('flux'); un, ue = get('unc')
    for i, n in enumerate(names):
        res[n] = dict(flux_n=fl[2*i], flux_n_rel=fe[2*i], flux_g=fl[2*i+1], flux_g_rel=fe[2*i+1], unc_n=un[2*i], unc_n_rel=ue[2*i],
                      unc_g=un[2*i+1], unc_g_rel=ue[2*i+1])
    if not void:
        h, he = get('heat', 'heating')
        for i, n in enumerate(names): res[n].update(heat_eV=h[i], heat_rel=he[i])
    return res, dt


def kernel(tk, n=4000, seed=3):
    """Point-kernel mean over each tank volume of sum_units 1/(4 pi d^2) (cm^-2 per unit source), the flux a void geometry must give
    (OpenMC flux tally = track length per source particle = flux x volume; we compare flux x volume / volume)."""
    rnd = random.Random(seed); out = {}
    for t in tk:
        acc = 0.0
        for _ in range(n):
            x = rnd.uniform(t['x0'], t['x1']); r = t['a']*math.sqrt(rnd.random()); ph = rnd.uniform(0, 2*math.pi)
            y = t['y']+r*math.cos(ph); z = t['z']+r*math.sin(ph)
            acc += sum(1/(4*math.pi*((x-ux)**2+(y-uy)**2+(z-uz)**2)*CM*CM) for ux, uy, uz in UNITS)/len(UNITS)
        out[t['id']] = acc/n*(math.pi*t['a']**2*(t['x1']-t['x0'])*CM**3)
    return out


def main():
    particles = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    s = spec.load()[0]
    S1 = json.loads((WORK/'results'/'phase4_rad_wayfarer.json').read_text())['S1']
    out = dict(solver=f'OpenMC {openmc.__version__}', library='ENDF/B-VIII.0 (NNDC HDF5)', frame='ship frame (m), +x bow; CSG built from the pure modules',
               status='3-D TRANSPORT-INFORMED (surrogate source, simplified structure); not validated', particles=particles, runs={})
    # V verification (void, neutrons only)
    geo, mats_, tc, tk = build(s, void=True)
    rV, dtV = run('V', geo, mats_, tc, sources(S1, False, 'neutron'), particles//2, void=True)
    K = kernel(tk)
    ver = []
    for t in tk:
        # OpenMC 0.15 multiplies tallies by the total source strength (here 3 units x neutrons per fission): compare per source particle
        ver.append(dict(tank=t['id'], openmc=rV[f'tank_{t["id"]}']['flux_n']/(len(UNITS)*S1['neutrons_leaking_per_fission']), kernel=K[t['id']],
                        rel_err=rV[f'tank_{t["id"]}']['flux_n_rel']))
    for v in ver: v['ratio'] = v['openmc']/v['kernel'] if v['kernel'] else None
    out['runs']['V'] = dict(runtime_s=dtV, rows=ver)
    geo, mats_, tc, tk = build(s)
    rB, dtB = run('B', geo, mats_, tc, sources(S1, False), particles)
    rS, dtS = run('S', geo, mats_, tc, sources(S1, True), particles)
    out['runs']['B'] = dict(runtime_s=dtB, cells=rB); out['runs']['S'] = dict(runtime_s=dtS, cells=rS)
    out['normalisation'] = ('B and S tallies are per fission in EACH of the three units (OpenMC scales by the total source strength = '
                            '3 x leakage per fission x the cone factor); V rows are per source particle')
    out['tanks'] = tk; out['units'] = UNITS; out['cone_deg'] = CONE
    OUT.write_text(json.dumps(out, indent=1, default=float))
    print('V ratios', [round(v['ratio'], 3) for v in ver], 'times', round(dtV), round(dtB), round(dtS))


if __name__ == '__main__':
    main()
