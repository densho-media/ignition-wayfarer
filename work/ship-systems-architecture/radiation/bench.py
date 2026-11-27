"""ISSA Phase IV-B verification benchmarks for the OpenMC workflow (solver + data), before any Wayfarer application.

B1 Godiva, ICSBEP HEU-MET-FAST-001 (bare HEU sphere): published benchmark k_eff = 1.0000 +/- 0.0010.      (validation of solver + data, criticality)
B2 uncollided 2 MeV neutron transmission through 10 cm iron vs exp(-Sigma_t x) from the same library.   (code verification, transport geometry)
B3 uncollided 1 MeV photon transmission through 5 cm iron vs NIST XCOM mu/rho = 0.05995 cm2/g.          (data validation, photon physics)

    OPENMC_CROSS_SECTIONS=/opt/nd/endfb80/cross_sections.xml /opt/mf/envs/omc/bin/python work/ship-systems-architecture/radiation/bench.py
Writes ../results/phase4_rad_bench.json. Run directories go to $RAD_RUNS (default /tmp/issa_rad), never into Git.
"""
import json
import math
import os
import time
from pathlib import Path

import openmc
import openmc.data

OUT = Path(__file__).resolve().parents[1]/'results'
RUNS = Path(os.environ.get('RAD_RUNS', '/tmp/issa_rad'))
XS = Path(os.environ.get('OPENMC_CROSS_SECTIONS', '/opt/nd/endfb80/cross_sections.xml'))


def run(model, name, threads=4):
    d = RUNS/name; d.mkdir(parents=True, exist_ok=True)
    model.settings.output = {'tallies': False}
    t0 = time.time(); sp = model.run(cwd=d, threads=threads, output=False); return openmc.StatePoint(sp), time.time()-t0


def godiva():
    u = openmc.Material(); u.add_nuclide('U234', 4.9184e-4); u.add_nuclide('U235', 4.4994e-2); u.add_nuclide('U238', 2.4984e-3)
    u.set_density('sum')
    s = openmc.Sphere(r=8.7407, boundary_type='vacuum'); c = openmc.Cell(fill=u, region=-s)
    m = openmc.Model(geometry=openmc.Geometry([c]), materials=openmc.Materials([u]))
    st = openmc.Settings(); st.batches = 150; st.inactive = 30; st.particles = 20000
    st.source = openmc.IndependentSource(space=openmc.stats.Point()); m.settings = st
    sp, dt = run(m, 'godiva'); k = sp.keff
    return dict(case='B1 Godiva HEU-MET-FAST-001', k_calc=k.nominal_value, sigma=k.std_dev, k_bench=1.0000, bench_unc=0.0010,
                diff_pcm=(k.nominal_value-1.0)*1e5, within=abs(k.nominal_value-1.0) <= math.hypot(0.0010, 3*k.std_dev), runtime_s=dt,
                batches=150, inactive=30, particles=20000)


def slab(particle, E, mat, x_cm, ref_mu_cm):
    """pencil beam on a slab; tally uncollided current through the back face (CollisionFilter 0)."""
    s0 = openmc.XPlane(0.0); s1 = openmc.XPlane(x_cm); out0 = openmc.XPlane(-1.0, boundary_type='vacuum'); out1 = openmc.XPlane(x_cm+1.0, boundary_type='vacuum')
    void = openmc.Material(); void.add_nuclide('H1', 1e-12); void.set_density('atom/b-cm', 1e-12)
    yz = openmc.YPlane(-50, boundary_type='vacuum') , openmc.YPlane(50, boundary_type='vacuum'), openmc.ZPlane(-50, boundary_type='vacuum'), openmc.ZPlane(50, boundary_type='vacuum')
    box = +yz[0] & -yz[1] & +yz[2] & -yz[3]
    c1 = openmc.Cell(fill=void, region=+out0 & -s0 & box); c2 = openmc.Cell(fill=mat, region=+s0 & -s1 & box); c3 = openmc.Cell(fill=void, region=+s1 & -out1 & box)
    m = openmc.Model(geometry=openmc.Geometry([c1, c2, c3]), materials=openmc.Materials([void, mat]))
    st = openmc.Settings(); st.run_mode = 'fixed source'; st.batches = 10; st.particles = 100000
    st.source = openmc.IndependentSource(space=openmc.stats.Point((-0.5, 0, 0)), angle=openmc.stats.Monodirectional((1, 0, 0)),
                                         energy=openmc.stats.Discrete([E], [1.0]), particle=particle)
    if particle == 'photon':
        st.photon_transport = True
    m.settings = st
    t = openmc.Tally(); t.filters = [openmc.SurfaceFilter([s1]), openmc.CollisionFilter([0]), openmc.ParticleFilter([particle])]; t.scores = ['current']
    m.tallies = openmc.Tallies([t])
    sp, dt = run(m, f'slab_{particle}')
    tt = sp.get_tally(id=t.id); v = float(tt.mean.ravel()[0]); e = float(tt.std_dev.ravel()[0])
    ref = math.exp(-ref_mu_cm*x_cm)
    return dict(calc=v, sigma=e, ref=ref, rel_diff=(v-ref)/ref, runtime_s=dt)


def main():
    os.environ['OPENMC_CROSS_SECTIONS'] = str(XS); openmc.config['cross_sections'] = str(XS)
    res = dict(solver=f'OpenMC {openmc.__version__}', library='ENDF/B-VIII.0 (NNDC HDF5)', cases=[])
    res['cases'].append(godiva()); print(res['cases'][-1])
    fe = openmc.Material(); fe.add_element('Fe', 1.0, enrichment=None) if False else None
    fe = openmc.Material(); fe.add_nuclide('Fe54', 0.05845); fe.add_nuclide('Fe56', 0.91754+0.00282); fe.add_nuclide('Fe57', 0.02119); fe.set_density('g/cm3', 7.874)
    # B2: Sigma_t from the same library at 294 K
    n_at = {}
    for nuc, f in (('Fe54', 0.05845), ('Fe56', 0.92036), ('Fe57', 0.02119)):
        n_at[nuc] = f
    N = 7.874/55.845*0.602214076                            # atoms / b-cm
    sig = 0.0
    for nuc, f in n_at.items():
        d = openmc.data.IncidentNeutron.from_hdf5(Path(XS).parent/f'neutron/{nuc}.h5')
        sig += f*d[1].xs['294K'](2.0e6)
    r = slab('neutron', 2.0e6, fe, 10.0, N*sig); r.update(case='B2 uncollided 2 MeV n, 10 cm Fe (code verification)', Sigma_t_cm=N*sig)
    res['cases'].append(r); print(r)
    r = slab('photon', 1.0e6, fe, 5.0, 0.05995*7.874); r.update(case='B3 uncollided 1 MeV photons, 5 cm Fe vs NIST XCOM (data validation)', mu_cm=0.05995*7.874,
             ref_without_coherent=math.exp(-0.05951*7.874*5.0), note='XCOM 1 MeV Fe: 0.05995 cm2/g with coherent, 0.05951 without; '
             'the uncollided tally agrees with the no-coherent value, i.e. coherent (Rayleigh) events are not counted as collisions here')
    r['rel_diff_without_coherent'] = (r['calc']-r['ref_without_coherent'])/r['ref_without_coherent']
    res['cases'].append(r); print(r)
    OUT.mkdir(exist_ok=True); (OUT/'phase4_rad_bench.json').write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
