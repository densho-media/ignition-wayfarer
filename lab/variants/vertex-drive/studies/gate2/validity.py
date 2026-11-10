"""Gate 2 Task D: validity range of the analytical plasma (thin-shell) model on the V4 nozzle (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate2/validity.py     # writes results/validity.json (seconds)

The thin-shell model treats the pulse as a fluid shell stopped by magnetic pressure on a sharp surface. That needs, at the stopping
surface: a magnetised, flux-excluding plasma (ion Larmor radius << stopping radius), a shell thin against that radius, field frozen in
(magnetic Reynolds number >> 1), and surface structure no finer than the plasma can follow (the G1 kinks). This evaluates each from the
V4 pulse and the T03 surface field along the stopping surface; it is a consistency screen, not a plasma calculation.
"""
import math

import numpy as np

import g2
import axis as AX
import shell
G = g2.G

AMU = 1.66053906660e-27; QE = 1.602176634e-19; MU0 = 4e-7 * math.pi; KEV = 1.602176634e-16


def main():
    v = G.v4(); T = shell.WorkTable(v['loops'], n_th=721, n_rho=AX.N_RHO)
    E = v['E_plasma_J']; m = v['mass_per_pulse_kg']
    R = T.stopping(1.0, E / (4 * math.pi)); th = T.th
    ok = np.isfinite(R)
    Bt = np.abs(np.array([np.interp(R[j], T.rho, T.Bt[:, j]) if ok[j] else np.nan for j in range(len(th))]))
    vbulk = math.sqrt(2 * E / m)
    rows = {}
    for name, A, Z, v_ion in (('bulk ion (mean 2.5 amu, Z 1.5)', 2.5, 1.5, vbulk), ('14.7 MeV proton', 1.00728, 1.0, math.sqrt(2 * 14.7e3 * KEV / (1.00728 * AMU))),
                              ('3.6 MeV alpha', 4.0026, 2.0, math.sqrt(2 * 3.6e3 * KEV / (4.0026 * AMU)))):
        rL = A * AMU * v_ion / (Z * QE * np.where(ok, Bt, np.nan))
        rows[name] = {'speed_m_s': v_ion, 'larmor_m_median': float(np.nanmedian(rL)), 'larmor_m_max': float(np.nanmax(rL)),
                      'larmor_over_R_median': float(np.nanmedian(rL / R)), 'larmor_over_R_max': float(np.nanmax(rL / R))}
    # shell thickness (velocity spread 10-30 %) and the G1 regularisation scale
    Rs = float(np.nanmedian(R))
    shell_m = [0.1 * Rs, 0.3 * Rs]
    # magnetic Reynolds number with Spitzer resistivity at an adiabatically cooled shell (T_e 10-1000 eV), L = shell thickness
    rm = {}
    for Te in (10.0, 100.0, 1000.0):
        eta = 5.2e-5 * 1.5 * 10.0 / Te ** 1.5               # ohm m (Spitzer, Z 1.5, ln Lambda 10)
        rm[f'{Te:g} eV'] = MU0 * vbulk * shell_m[0] / eta
    # beta at the stopping surface (dynamic pressure vs field) -> the surface is where they balance; check the Bt range
    out = {'study': 'Gate 2 Task D: thin-shell validity screen (T00)', 'status': 'MODEL, research only, NON-CANON',
           'pulse': {'E_plasma_J': E, 'mass_kg': m, 'bulk_speed_m_s': vbulk, 'stopping_radius_median_m': Rs,
                     'stopping_radius_range_m': [float(np.nanmin(R)), float(np.nanmax(R))], 'Bt_at_surface_T_median': float(np.nanmedian(Bt)),
                     'Bt_at_surface_T_range': [float(np.nanmin(Bt)), float(np.nanmax(Bt))]},
           'larmor': rows, 'shell_thickness_m_10_30pc': shell_m, 'magnetic_Reynolds_shell': rm,
           'g1_regularisation_scale_m': 2.0,
           'reading': ['bulk-ion Larmor radii at the surface field (median about 0.4 m, at most 7.5 % of the stopping radius) are small: '
                       'the flux-excluding fluid picture holds in the bulk; fast products are marginal (14.7 MeV protons up to 11 % of R '
                       'where the field is weak) and kinetic effects there are a PIC-class question',
                       'the shell is thick against the G1 kinks: a 10-30 % velocity spread gives 5-15 m at the 48 m median stopping radius, '
                       'against 0.5-2 m kinks. A shell that thick cannot reflect specularly off them, so the ledger regularised on the '
                       'shell scale (2-8 m smoothing: eta_T 0.80-0.82) is the meaningful thin-shell value and the fine-grid 0.67 is an '
                       'artefact of an infinitely thin shell; neither is a plasma result',
                       'outside the model: lateral flow toward field zeros (funnelling), Rayleigh-Taylor at the decelerating surface, the '
                       'shell velocity spread itself and detachment (MHD: D-21)',
                       'magnetic Reynolds numbers are large (5e6 or more) for any electron temperature above a few eV: frozen-in flux is not '
                       'the weak point']}
    g2.write('validity.json', out)
    print({k: (round(x['larmor_m_median'], 3), round(x['larmor_over_R_max'], 3)) for k, x in rows.items()}, out['pulse'], rm)


if __name__ == '__main__':
    main()
