"""Physical constants (CODATA 2018) and D-3He reaction data."""
import math

C = 299792458.0                 # m/s
G0 = 9.80665                    # m/s2
AU = 1.495978707e11             # m
DAY = 86400.0                   # s
YEAR = 365.25*DAY               # Julian year, s
SIGMA = 5.670374419e-8          # W/m2/K4
MEV = 1.602176634e-13           # J
KEV = 1.602176634e-16           # J
U = 1.66053906660e-27           # kg
MU0 = 4e-7*math.pi              # H/m (to 1e-10)
LY = C*YEAR                     # m

M_D = 2.01410178                # u (atomic)
M_HE3 = 3.01602932              # u
Q_MEV = {'DHe3': 18.353, 'DDn': 3.269, 'DDp': 4.033, 'DT': 17.589}
E_NEUTRON_MEV = {'DDn': 2.449, 'DT': 14.07}
DHE3_PAIR_KG = (M_D+M_HE3)*U
EPS_DHE3 = Q_MEV['DHe3']*MEV/DHE3_PAIR_KG         # J per kg of reacted D+He3 (3.52e14)
MASS_DEFECT_DHE3 = EPS_DHE3/C**2                   # rest mass converted per kg reacted (0.39 %)


def he3_mass_share(he3_to_d):
    """Mass share of He-3 in a fuel with molar ratio He-3:D = he3_to_d."""
    return he3_to_d*M_HE3/(he3_to_d*M_HE3+M_D)
