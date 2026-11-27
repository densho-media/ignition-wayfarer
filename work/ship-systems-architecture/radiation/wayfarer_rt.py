"""ISSA Phase IV-B first Wayfarer radiation workflow (STUDY, not engineering validation). Three simplified 1-D/compact problems:

S1 surrogate space-reactor leakage: a homogenised SP-100-class fast core (UN 93 % fuel, Li-7 coolant, Mo structure; SURROGATE, not a core
   design) in a BeO reflector, k-eigenvalue run; tallies neutron and photon leakage per fission and their spectra.
S2 shield transmission: the S1 leakage spectra as a broad planar source on W (5 cm) + LiH (natural Li) of thickness t; neutron and photon
   energy transmission vs t -> effective relaxation lengths that replace the Phase II/III assumption (lambda 0.10-0.15 m).
S3 cryogenic tank layer: the S1 leakage (and, separately, its photons) incident on a 2 cm aluminium wall + 50 cm liquid He-3 (0.082 g/cm3);
   heating per incident particle in the wall and in the He-3 (incl. the He-3(n,p)T reaction, Q = 764 keV).

    PATH=/opt/mf/envs/omc/bin:$PATH OPENMC_CROSS_SECTIONS=/opt/nd/endfb80/cross_sections.xml \
      /opt/mf/envs/omc/bin/python work/ship-systems-architecture/radiation/wayfarer_rt.py
Writes ../results/phase4_rad_wayfarer.json. Limits: 1-D slabs, surrogate core, no streaming, no blade scatter, no structure; results are
transport-informed estimates, not a spacecraft radiation assessment.
"""
import json
import math
import os
import time
from pathlib import Path

import numpy as np
import openmc

OUT = Path(__file__).resolve().parents[1]/'results'
RUNS = Path(os.environ.get('RAD_RUNS', '/tmp/issa_rad'))
EB = np.logspace(-3, np.log10(2e7), 61)               # eV group bounds for spectra
EB_G = np.logspace(4, np.log10(2e7), 41)


def run(model, name, threads=4):
    d = RUNS/name; d.mkdir(parents=True, exist_ok=True); model.settings.output = {'tallies': False}
    t0 = time.time(); sp = model.run(cwd=d, threads=threads, output=False); return openmc.StatePoint(sp), time.time()-t0


def mats():
    un = openmc.Material(name='UN'); un.add_nuclide('U235', 0.93); un.add_nuclide('U238', 0.07); un.add_nuclide('N14', 1.0); un.set_density('g/cm3', 13.6)
    li = openmc.Material(name='Li7'); li.add_nuclide('Li7', 1.0); li.set_density('g/cm3', 0.47)
    mo = openmc.Material(name='Mo'); [mo.add_nuclide(n, f) for n, f in (('Mo92', .25), ('Mo95', .25), ('Mo96', .25), ('Mo98', .25))]; mo.set_density('g/cm3', 10.2)
    core = openmc.Material.mix_materials([un, li, mo], [0.45, 0.30, 0.25], 'vo', name='core')
    beo = openmc.Material(name='BeO'); beo.add_nuclide('Be9', 1.0); beo.add_nuclide('O16', 1.0); beo.set_density('g/cm3', 2.85)
    lih = openmc.Material(name='LiH'); lih.add_nuclide('Li6', 0.0759); lih.add_nuclide('Li7', 0.9241); lih.add_nuclide('H1', 1.0); lih.set_density('g/cm3', 0.78)
    w = openmc.Material(name='W'); [w.add_nuclide(n, f) for n, f in (('W182', .265), ('W183', .143), ('W184', .307), ('W186', .285))]; w.set_density('g/cm3', 19.3)
    al = openmc.Material(name='Al'); al.add_nuclide('Al27', 1.0); al.set_density('g/cm3', 2.7)
    he3 = openmc.Material(name='He3liq'); he3.add_nuclide('He3', 1.0); he3.set_density('g/cm3', 0.082)
    void = openmc.Material(name='void'); void.add_nuclide('He4', 1.0); void.set_density('g/cm3', 1e-10)
    return dict(core=core, beo=beo, lih=lih, w=w, al=al, he3=he3, void=void)


def s1(M, r_core=14.0, h_core=30.0, t_refl=8.0):
    c1 = openmc.ZCylinder(r=r_core); p1, p2 = openmc.ZPlane(-h_core/2), openmc.ZPlane(h_core/2)
    c2 = openmc.ZCylinder(r=r_core+t_refl); p3, p4 = openmc.ZPlane(-h_core/2-t_refl), openmc.ZPlane(h_core/2+t_refl)
    sph = openmc.Sphere(r=80.0, boundary_type='vacuum')
    core = openmc.Cell(fill=M['core'], region=-c1 & +p1 & -p2)
    refl = openmc.Cell(fill=M['beo'], region=-c2 & +p3 & -p4 & ~(-c1 & +p1 & -p2))
    out = openmc.Cell(fill=M['void'], region=-sph & ~(-c2 & +p3 & -p4))
    m = openmc.Model(geometry=openmc.Geometry([core, refl, out]), materials=openmc.Materials([M['core'], M['beo'], M['void']]))
    st = openmc.Settings(); st.batches = 80; st.inactive = 20; st.particles = 20000; st.photon_transport = True
    st.source = openmc.IndependentSource(space=openmc.stats.Box((-r_core/2, -r_core/2, -h_core/4), (r_core/2, r_core/2, h_core/4))); m.settings = st
    tf = openmc.Tally(name='fiss'); tf.filters = [openmc.CellFilter([core])]; tf.scores = ['fission', 'heating']
    tl = openmc.Tally(name='leak'); tl.filters = [openmc.SurfaceFilter([sph]), openmc.ParticleFilter(['neutron', 'photon']), openmc.EnergyFilter(EB)]; tl.scores = ['current']
    m.tallies = openmc.Tallies([tf, tl])
    sp, dt = run(m, 's1_core')
    f = sp.get_tally(name='fiss'); fiss = float(f.get_values(scores=['fission']).ravel()[0])
    l = sp.get_tally(name='leak'); v = l.mean.reshape(2, len(EB)-1); e = l.std_dev.reshape(2, len(EB)-1)
    mid = np.sqrt(EB[1:]*EB[:-1])
    n_per_f = v[0].sum()/fiss; g_per_f = v[1].sum()/fiss
    En = (v[0]*mid).sum()/v[0].sum(); Eg = (v[1]*mid).sum()/max(v[1].sum(), 1e-30)
    return dict(k_eff=sp.keff.nominal_value, k_sigma=sp.keff.std_dev, core=dict(r_cm=r_core, h_cm=h_core, reflector_cm=t_refl, fuel='UN 93 %, 45 vol %',
                coolant='Li-7 30 vol %', structure='Mo 25 vol %', reflector='BeO'), neutrons_leaking_per_fission=n_per_f, photons_leaking_per_fission=g_per_f,
                mean_leak_energy_n_eV=En, mean_leak_energy_g_eV=Eg, rel_err_n=float(np.sqrt((e[0]**2).sum())/v[0].sum()),
                spectrum_n=(v[0]/v[0].sum()).tolist(), spectrum_g=(v[1]/max(v[1].sum(), 1e-30)).tolist(), bounds_eV=EB.tolist(), runtime_s=dt)


def spectrum_source(sp_frac, particle, x0):
    p = np.array(sp_frac); keep = p > 0
    e = openmc.stats.Tabular(EB[:-1], np.append(p[:-1]/np.diff(EB)[:-1], 0)[:len(EB)-1], interpolation='histogram') if False else None
    lo = EB[:-1][keep]; hi = EB[1:][keep]; w = p[keep]
    ens = openmc.stats.Mixture(list(w/w.sum()), [openmc.stats.Uniform(a, b) for a, b in zip(lo, hi)])
    return openmc.IndependentSource(space=openmc.stats.Box((x0, -50, -50), (x0, 50, 50)), angle=openmc.stats.Monodirectional((1, 0, 0)), energy=ens,
                                    particle=particle)


def slab_stack(M, layers, src, name, particles=100000, score_heat=False):
    """layers: [(material key, thickness cm)]; reflective y/z (broad beam), vacuum front/back. Returns transmitted energy current per source
    particle (neutron, photon) and heating per layer."""
    x = 0.0; surfs = [openmc.XPlane(-1.0, boundary_type='vacuum'), openmc.XPlane(0.0)]
    for _, t in layers:
        x += t; surfs.append(openmc.XPlane(x))
    surfs.append(openmc.XPlane(x+1.0, boundary_type='vacuum'))
    sides = +openmc.YPlane(-50, boundary_type='reflective') & -openmc.YPlane(50, boundary_type='reflective') & +openmc.ZPlane(-50, boundary_type='reflective') & -openmc.ZPlane(50, boundary_type='reflective')
    cells = [openmc.Cell(fill=M['void'], region=+surfs[0] & -surfs[1] & sides)]
    for i, (k, _) in enumerate(layers):
        cells.append(openmc.Cell(fill=M[k], region=+surfs[i+1] & -surfs[i+2] & sides))
    cells.append(openmc.Cell(fill=M['void'], region=+surfs[-2] & -surfs[-1] & sides))
    used = {id(c.fill): c.fill for c in cells}
    m = openmc.Model(geometry=openmc.Geometry(cells), materials=openmc.Materials(list(used.values())))
    st = openmc.Settings(); st.run_mode = 'fixed source'; st.batches = 10; st.particles = particles; st.photon_transport = True
    st.source = src; m.settings = st
    t = openmc.Tally(name='tr'); t.filters = [openmc.SurfaceFilter([surfs[-2]]), openmc.ParticleFilter(['neutron', 'photon']), openmc.EnergyFilter(EB)]; t.scores = ['current']
    h = openmc.Tally(name='heat'); h.filters = [openmc.CellFilter(cells[1:-1])]; h.scores = ['heating']
    m.tallies = openmc.Tallies([t, h])
    sp, dt = run(m, name)
    v = sp.get_tally(name='tr').mean.reshape(2, len(EB)-1); mid = np.sqrt(EB[1:]*EB[:-1])
    hh = sp.get_tally(name='heat'); hv = hh.mean.ravel(); he = hh.std_dev.ravel()
    return dict(n_number=float(v[0].sum()), n_energy_eV=float((v[0]*mid).sum()), g_energy_eV=float((v[1]*mid).sum()),
                heating_eV=[float(a) for a in hv], heating_rel_err=[float(b/a) if a else None for a, b in zip(hv, he)], runtime_s=dt)


def main():
    os.environ.setdefault('OPENMC_CROSS_SECTIONS', '/opt/nd/endfb80/cross_sections.xml')
    M = mats(); res = dict(solver=f'OpenMC {openmc.__version__}', library='ENDF/B-VIII.0 (NNDC HDF5)', status='STUDY (transport-informed, not validated for Wayfarer)')
    S1 = s1(M); res['S1'] = S1
    print('S1 k', round(S1['k_eff'], 4), 'n/f', round(S1['neutrons_leaking_per_fission'], 3), 'g/f', round(S1['photons_leaking_per_fission'], 3),
          'En', round(S1['mean_leak_energy_n_eV']/1e6, 3), 'Eg', round(S1['mean_leak_energy_g_eV']/1e6, 3))
    src_n = lambda x0: spectrum_source(S1['spectrum_n'], 'neutron', x0)
    src_g = lambda x0: spectrum_source(S1['spectrum_g'], 'photon', x0)
    E_n0 = S1['mean_leak_energy_n_eV']; E_g0 = S1['mean_leak_energy_g_eV']
    rows = []
    for t in (0, 20, 40, 60, 80):
        layers = [('w', 5.0)] + ([('lih', float(t))] if t else [])
        a = slab_stack(M, layers, src_n(-0.5), f's2_n_{t}', particles=60000)
        b = slab_stack(M, layers, src_g(-0.5), f's2_g_{t}', particles=60000)
        rows.append(dict(lih_cm=t, n_number_T=a['n_number'], n_energy_T=a['n_energy_eV']/E_n0, n_src_g_energy_T=a['g_energy_eV']/E_n0,
                         g_energy_T=b['g_energy_eV']/E_g0))
        print('S2', rows[-1])
    res['S2'] = dict(rows=rows, note='per source particle; W 5 cm then LiH (natural Li); broad beam (reflective sides); energy transmission relative '
                     'to the incident mean energy; n_src_g = secondary photons produced by neutrons in the shield')
    def lam(key):
        a, b = rows[1], rows[-1]
        return (b['lih_cm']-a['lih_cm'])/math.log(a[key]/b[key]) if b[key] > 0 and a[key] > 0 else None
    res['S2']['relaxation_cm'] = dict(neutron_number=lam('n_number_T'), neutron_energy=lam('n_energy_T'), secondary_gamma=lam('n_src_g_energy_T'))
    print('lambda', res['S2']['relaxation_cm'])
    tank = [('al', 2.0), ('he3', 50.0)]
    a = slab_stack(M, tank, src_n(-0.5), 's3_n', particles=60000); b = slab_stack(M, tank, src_g(-0.5), 's3_g', particles=60000)
    res['S3'] = dict(layers='2 cm Al wall + 50 cm liquid He-3', per_incident_neutron=dict(wall_eV=a['heating_eV'][0], he3_eV=a['heating_eV'][1],
                     rel_err=a['heating_rel_err'], incident_mean_eV=E_n0), per_incident_photon=dict(wall_eV=b['heating_eV'][0], he3_eV=b['heating_eV'][1],
                     rel_err=b['heating_rel_err'], incident_mean_eV=E_g0))
    print('S3', res['S3'])
    OUT.mkdir(exist_ok=True); (OUT/'phase4_rad_wayfarer.json').write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
