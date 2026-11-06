"""D-3He plasma physics for the drive models.

- Reactivities: Bosch & Hale, Nucl. Fusion 32 (1992) 611 (valid to ~190 keV for D-3He, 100 keV for D-D).
- Bremsstrahlung with relativistic and electron-electron terms: Rider, Phys. Plasmas 2 (1995) 1853 / Wesson, Tokamaks.
- Burn fraction: continuous feed b = tau_p / (tau_p + tau_f); pulsed (inertial) b = rhoR / (rhoR + H_B), with H_B calibrated on D-T.
Written for this study, independently of the v3/v4 scripts (compared against them in the report).
"""
import math
from functools import lru_cache

from .const import KEV, MEV, U, M_D, M_HE3, Q_MEV, E_NEUTRON_MEV

BH = {'DT': (34.3827, 1124656, 1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3, 1.35e-2, -1.0675e-4, 1.366e-5),
      'DHe3': (68.7508, 1124572, 5.51036e-10, 6.41918e-3, -2.02896e-3, -1.91080e-5, 1.35776e-4, 0.0, 0.0),
      'DDn': (31.3970, 937814, 5.43360e-12, 5.85778e-3, 7.68222e-3, 0.0, -2.964e-6, 0.0, 0.0),
      'DDp': (31.3970, 937814, 5.65718e-12, 3.41267e-3, 1.99167e-3, 0.0, 1.05060e-5, 0.0, 0.0)}


def sigv(reaction, T_keV):
    """Maxwellian reactivity <sigma v> in m3/s at ion temperature T_keV."""
    BG, mrc2, c1, c2, c3, c4, c5, c6, c7 = BH[reaction]
    T = T_keV
    th = T/(1-T*(c2+T*(c4+T*c6))/(1+T*(c3+T*(c5+T*c7))))
    xi = (BG**2/(4*th))**(1/3)
    return c1*th*math.sqrt(xi/(mrc2*T**3))*math.exp(-3*xi)*1e-6


def brems_W_m3(ne, Te_keV, Zeff):
    """Bremsstrahlung power density (W/m3), electron-ion with relativistic correction plus electron-electron."""
    x = Te_keV/511.0
    ei = Zeff*(1+0.7936*x+1.874*x**2)
    ee = 3/math.sqrt(2)*x*(1+1.1*x+x**2-1.25*x**2.5)
    return 5.35e-37*ne**2*math.sqrt(Te_keV)*(ei+ee)


@lru_cache(maxsize=4096)
def partition(Ti_keV, Te_keV, he3_to_d=1.0, tritium_burn=0.5, sync_fraction=0.0):
    """Fractions of gross fusion power: neutron, bremsstrahlung, synchrotron (net, given) and the charged remainder that heats the plasma.
    Ion densities cancel; the ratio He-3:D is molar. Tritium from D-D(p) burns in place with share `tritium_burn` (14.1 MeV neutrons)."""
    nD, nHe = 1.0, he3_to_d; n0 = 1e20
    ne = (nD+2*nHe)*n0; Zeff = (nD+4*nHe)/(nD+2*nHe)
    r_dhe = nD*nHe*n0**2*sigv('DHe3', Ti_keV)
    r_ddn = 0.5*(nD*n0)**2*sigv('DDn', Ti_keV)
    r_ddp = 0.5*(nD*n0)**2*sigv('DDp', Ti_keV)
    r_dt = r_ddp*tritium_burn
    p_fus = (r_dhe*Q_MEV['DHe3']+r_ddn*Q_MEV['DDn']+r_ddp*Q_MEV['DDp']+r_dt*Q_MEV['DT'])*MEV
    p_n = (r_ddn*E_NEUTRON_MEV['DDn']+r_dt*E_NEUTRON_MEV['DT'])*MEV
    p_b = brems_W_m3(ne, Te_keV, Zeff)
    f_n = p_n/p_fus; f_b = p_b/p_fus
    return {'Ti_keV': Ti_keV, 'Te_keV': Te_keV, 'he3_to_d': he3_to_d, 'Zeff': Zeff, 'neutron': f_n, 'brems': f_b,
            'sync': sync_fraction, 'charged_to_exhaust': max(0.0, 1-f_n-f_b-sync_fraction),
            'dhe3_share_of_reactions': r_dhe/(r_dhe+r_ddn+r_ddp+r_dt)}


def fusion_power_density(n_e, Ti_keV, he3_to_d=1.0):
    """D-3He fusion power density (W/m3) at electron density n_e."""
    nD = n_e/(1+2*he3_to_d); nHe = he3_to_d*nD
    return nD*nHe*sigv('DHe3', Ti_keV)*Q_MEV['DHe3']*MEV


def fuel_burn_time_s(n_e, Ti_keV, he3_to_d=1.0):
    """Mean time for a He-3 ion to fuse (the scarcer partner sets it for 1:1): 1 / (n_D <sv>)."""
    nD = n_e/(1+2*he3_to_d)
    return 1/(nD*sigv('DHe3', Ti_keV))


def continuous_burn_fraction(tau_p, tau_f):
    return tau_p/(tau_p+tau_f)


def tau_p_needed(b, tau_f):
    return tau_f*b/(1-b)


def burn_parameter_kg_m2(T_keV, reaction='DHe3', calib_DT_g_cm2=7.0):
    """H_B in b = rhoR/(rhoR+H_B), H_B = K m_ion c_s / <sv>, K calibrated so D-T at 20 keV gives calib_DT_g_cm2."""
    def raw(T, r):
        if r == 'DT':
            m = 2.5*U; z = 1.0; partner = 0.5
        else:
            m = (M_D+M_HE3)/2*U; z = 1.5; partner = 0.5
        cs = math.sqrt(5/3*(1+z)*T*KEV/m)
        return m*cs/(sigv(r, T)*partner)
    K = calib_DT_g_cm2*10.0/raw(20.0, 'DT')
    return K*raw(T_keV, reaction)


def pulsed_burn_fraction(rhoR_kg_m2, H_B):
    return rhoR_kg_m2/(rhoR_kg_m2+H_B)


def rhoR_needed(b, H_B):
    return H_B*b/(1-b)


def escape_probability(tau):
    """Mean escape probability of radiation born uniformly in a slab of optical depth tau ((1 - e^-tau)/tau)."""
    return 1.0 if tau < 1e-9 else (1-math.exp(-tau))/tau
