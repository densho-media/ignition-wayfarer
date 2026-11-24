"""Build data/optics.json: photon interaction data for the MPN mirror and shield materials.

Run once, outside the stdlib study model, with xraylib 4.3.0 (Schoonjans et al., Spectrochim. Acta B 66 (2011) 776; photoionisation
from Scofield/EPDL97, Compton and Rayleigh from Hubbell et al. form factors and incoherent scattering functions, f1/f2 anomalous
scattering from Kissel/Henke). Requires: pip install xraylib (a venv is enough):

    <venv>/bin/python lab/studies/vertex-compact-engine/magneto-photonic-nozzle/optics_data.py

mpn.py reads only the JSON it writes, so the study itself stays standard-library only and reproducible without xraylib.
"""
import json
import math
from pathlib import Path

import xraylib as xrl

OUT = Path(__file__).resolve().parent/'data'/'optics.json'
R_E = 2.8179403262e-15
N_A = 6.02214076e23
HC_KEV_M = 1.23984198e-9          # lambda (m) = 1.2398e-9 / E(keV)

# name: (formula, density g/cm3, role)
MATERIALS = {
    'Be': ('Be', 1.848, 'lowest-Z metal: Compton-dominated'),
    'C_diamond': ('C', 3.515, 'densest low-Z solid: highest electron density per unit photoabsorption'),
    'cBN': ('BN', 3.45, 'cubic boron nitride, diamond-like alternative'),
    'SiC': ('SiC', 3.21, 'refractory low-Z ceramic'),
    'Si': ('Si', 2.329, 'crystal optics reference'),
    'Ni': ('Ni', 8.908, 'X-ray and neutron mirror reference'),
    'Mo': ('Mo', 10.22, 'refractory mid-Z'),
    'W': ('W', 19.25, 'refractory high-Z; current armour material'),
    'Ir': ('Ir', 22.56, 'highest-density coating metal in use (Chandra)'),
    'Pt': ('Pt', 21.45, 'hard X-ray mirror coating (NuSTAR Pt/C)'),
    'Au': ('Au', 19.30, 'classic X-ray mirror coating'),
    'Os': ('Os', 22.59, 'densest element'),
    'LiH': ('LiH', 0.78, 'neutron shield'),
}

ENERGIES = sorted(set([round(x, 4) for x in
                       [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 120, 150, 200, 250, 300,
                        400, 500, 600, 800, 1000, 1500, 2000, 3000, 5000, 8000, 10000, 15000, 20000]]))


def sigma_kn(E):
    """Klein-Nishina total cross section per free electron (cm2)."""
    k = E/510.99895; re2 = (R_E*100)**2
    return 2*math.pi*re2*((1+k)/k**2*(2*(1+k)/(1+2*k)-math.log(1+2*k)/k)+math.log(1+2*k)/(2*k)-(1+3*k)/(1+2*k)**2)


def mass_cs(formula, E):
    """Mass cross sections (cm2/g) photo, Compton, Rayleigh for a compound. xraylib's splines end at 999 keV (photo) and 800 keV
    (Compton, Rayleigh); above that photo falls as 1/E from 800 keV, Compton is Z free electrons (Klein-Nishina, binding negligible)
    and Rayleigh falls as 1/E^2 from 800 keV."""
    cd = xrl.CompoundParser(formula)
    ph = co = ra = 0.0
    for Z, w in zip(cd['Elements'], cd['massFractions']):
        A = xrl.AtomicWeight(Z)
        ph += w*(xrl.CS_Photo(Z, E) if E <= 800 else xrl.CS_Photo(Z, 800)*800/E)
        co += w*(xrl.CS_Compt(Z, E) if E <= 800 else Z*sigma_kn(E)*N_A/A)
        ra += w*(xrl.CS_Rayl(Z, E) if E <= 800 else xrl.CS_Rayl(Z, 800)*(800/E)**2)
    return ph, co, ra


def electrons_per_g(formula):
    cd = xrl.CompoundParser(formula)
    return sum(w*Z/xrl.AtomicWeight(Z) for Z, w in zip(cd['Elements'], cd['massFractions']))*N_A


def material_rows(name):
    formula, rho, role = MATERIALS[name]
    ne = electrons_per_g(formula)*rho*1e6            # electrons per m3
    rows = []
    for E in ENERGIES:
        ph, co, ra = mass_cs(formula, E)
        lam = HC_KEV_M/E
        delta = 1.0-xrl.Refractive_Index_Re(formula, E, rho) if E <= 800 else R_E*lam**2*ne/(2*math.pi)
        delta_free = R_E*lam**2*ne/(2*math.pi)
        mu_loss = (ph+co)*rho*100.0                   # 1/m, everything that removes a photon from the coherent wave except Rayleigh
        beta = mu_loss*lam/(4*math.pi)
        rows.append(dict(E_keV=E, photo_cm2_g=ph, compton_cm2_g=co, rayleigh_cm2_g=ra, mu_loss_m=mu_loss,
                         mu_total_m=(ph+co+ra)*rho*100.0, delta=delta, delta_free_electron=delta_free, beta=beta,
                         beta_xraylib=xrl.Refractive_Index_Im(formula, E, rho) if E <= 800 else None))
    return dict(formula=formula, density_g_cm3=rho, role=role, electrons_m3=ne, rows=rows)


def darwin(crystal, hkl, E):
    """Darwin width (rad, full) and Bragg angle of a perfect crystal reflection at E (keV), from xraylib structure factors."""
    c = xrl.Crystal_GetCrystal(crystal)
    th = xrl.Bragg_angle(c, E, *hkl)
    if th == 0:
        return None
    FH = xrl.Crystal_F_H_StructureFactor(c, E, *hkl, 1.0, 1.0)
    lam = HC_KEV_M/E
    V = xrl.Crystal_UnitCellVolume(c)*1e-30           # m3
    w = 2*R_E*lam**2*abs(FH)/(math.pi*V*math.sin(2*th))
    d = xrl.Crystal_dSpacing(c, *hkl)*1e-10
    return dict(crystal=crystal, hkl=list(hkl), E_keV=E, bragg_rad=th, darwin_full_rad=w, d_m=d, bandwidth_dE_E=w/math.tan(th))


def main():
    out = dict(source='xraylib ' + xrl.__version__ + ' (Scofield/EPDL97 photoionisation, Hubbell form factors; f1 from Kissel)',
               note='mu_loss = photoabsorption + incoherent (Compton) attenuation; beta = mu_loss lambda / 4 pi. Rayleigh is coherent and '
                    'kept out of beta. Pair production is omitted (below 1.6 % of attenuation under 3 MeV).',
               materials={k: material_rows(k) for k in MATERIALS},
               crystals=[r for r in (darwin(cr, hkl, E) for cr, hkl in (('Si', (1, 1, 1)), ('Ge', (1, 1, 1)), ('Copper', (1, 1, 1)),
                                                                        ('Si', (2, 2, 0)), ('Diamond', (1, 1, 1)))
                                     for E in (30, 100, 300, 1000)) if r])
    OUT.write_text(json.dumps(out, indent=1))
    print('wrote', OUT, len(ENERGIES), 'energies')


if __name__ == '__main__':
    main()
