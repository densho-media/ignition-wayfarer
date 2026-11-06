"""Rocket equation, four-burn ledger and the split of the expelled mass into fusion fuel and reaction mass.

Mass bookkeeping per kg of ship mass lost (tank draw):
  fused  x = e_jet / (eta_jet * eps)            fuel that reacts (its rest-mass defect x*eps/c^2 leaves as energy)
  fed    x / b                                   fuel injected (burn fraction b)
  unburned x (1-b)/b, of which a share r is recovered to the tanks and (1-r) leaves in the exhaust
  inert  1 - x - lost                            hydrogen (or other inert mass) added to the exhaust; must be >= 0
Energy: jet = eta_jet * fusion = e_jet per kg. The energy-equivalent mass (0.39 % of x) is counted in the tank draw, so the rocket
equation's mass loss is exactly the tank draw (Newtonian bookkeeping; exhaust kinetic energy relativistic error 0.2 % at 0.064 c).
"""
import math

from .const import C, EPS_DHE3, MASS_DEFECT_DHE3, he3_mass_share


def mass_ratio(dv, ve, relativistic=False):
    """m0/mf for one burn. Relativistic form for a constant rocket-frame exhaust speed: exp((c/ve) atanh(dv/c))."""
    return math.exp(C/ve*math.atanh(dv/C)) if relativistic else math.exp(dv/ve)


def jet_energy_per_kg(ve, relativistic=False):
    if relativistic:
        return (1/math.sqrt(1-(ve/C)**2)-1)*C**2
    return ve**2/2


def ledger(m_end, ve, dv, burns=4, relativistic=False):
    """Masses before each burn and propellant used per burn, ending exactly at m_end."""
    R = mass_ratio(dv, ve, relativistic)
    masses = [m_end*R**(burns-i) for i in range(burns+1)]
    return {'mass_ratio_per_burn': R, 'mass_ratio_total': R**burns, 'masses_kg': masses,
            'burn_propellant_kg': [a-b for a, b in zip(masses, masses[1:])], 'propellant_kg': masses[0]-masses[-1],
            'departure_kg': masses[0], 'end_kg': masses[-1]}


def max_fused_share(b, r=0.0):
    """Largest fused share of the tank draw (no inert mass): x (1 + (1-b)(1-r)/b) = 1."""
    return b/(b+(1-b)*(1-r))


def ve_max(eta_jet, b, r=0.0, inert_per_fuel=0.0, eps=EPS_DHE3):
    """Highest effective exhaust velocity at directed efficiency eta_jet, burn fraction b, recovery r and an obligatory inert
    mass (liner, ablator) per kg of fuel fed."""
    x = 1/(1+(1-b)*(1-r)/b+inert_per_fuel/b)
    return math.sqrt(2*eta_jet*eps*x)


def split(draw_kg, ve, eta_jet, b, r=0.0, he3_to_d=1.0, eps=EPS_DHE3, he3_share=None, relativistic=False):
    """Split a tank draw (ship mass lost) into fused fuel, lost unburned fuel, recovered fuel and inert hydrogen.
    Returns None when ve is not reachable (inert would be negative)."""
    e = jet_energy_per_kg(ve, relativistic)
    x = e/(eta_jet*eps)
    unburned = x*(1-b)/b; lost = unburned*(1-r); recovered = unburned*r
    inert = 1-x-lost
    if inert < -1e-9:
        return None
    inert = max(0.0, inert)
    s = he3_mass_share(he3_to_d) if he3_share is None else he3_share
    fuel = (x+lost)*draw_kg
    out = {'draw_kg': draw_kg, 'fused_kg': x*draw_kg, 'fed_kg': x/b*draw_kg, 'unburned_kg': unburned*draw_kg,
           'recovered_kg': recovered*draw_kg, 'lost_unburned_kg': lost*draw_kg, 'hydrogen_kg': max(0.0, inert)*draw_kg,
           'fuel_draw_kg': fuel, 'helium_3_kg': fuel*s, 'deuterium_kg': fuel*(1-s),
           'products_kg': x*draw_kg*(1-eps/C**2), 'energy_mass_kg': x*draw_kg*eps/C**2,
           'fusion_energy_J': x*draw_kg*eps, 'jet_energy_J': e*draw_kg, 'exhaust_rest_mass_kg': draw_kg-x*draw_kg*eps/C**2,
           'fused_share': x, 'eta_jet': eta_jet, 'burn_fraction': b, 'recovery': r}
    return out


def check_split(s, tol=1e-9):
    """Mass and energy conservation of a split: draw = fused + lost + inert; exhaust = products + lost + inert; jet = eta * fusion."""
    errs = []
    if abs(s['fused_kg']+s['lost_unburned_kg']+s['hydrogen_kg']-s['draw_kg']) > tol*s['draw_kg']:
        errs.append('tank draw != fused + lost + hydrogen')
    if abs(s['products_kg']+s['lost_unburned_kg']+s['hydrogen_kg']-s['exhaust_rest_mass_kg']) > tol*s['draw_kg']:
        errs.append('exhaust rest mass != products + lost + hydrogen')
    if abs(s['jet_energy_J']-s['eta_jet']*s['fusion_energy_J']) > tol*s['jet_energy_J']:
        errs.append('jet energy != eta * fusion energy')
    if abs(s['fed_kg']-s['fused_kg']-s['unburned_kg']) > tol*s['draw_kg']:
        errs.append('fed != fused + unburned')
    return errs


def ve_matrix(m_end, dv, ves, tank_kg_per_kg, burns=4):
    """Matrix B rows: per exhaust velocity, the mass ratio and propellant for a fixed end mass, and with tank mass that grows with
    the propellant (dry = m_end + k P; diverges when k (R^4 - 1) >= 1)."""
    rows = []
    for ve in ves:
        L = ledger(m_end, ve, dv, burns); RN = L['mass_ratio_total']
        g = tank_kg_per_kg*(RN-1)
        if g < 1:
            P = (RN-1)*m_end/(1-g); tanks = tank_kg_per_kg*P; m0 = m_end+tanks+P
            first = m0*(1-1/L['mass_ratio_per_burn'])
        else:
            P = tanks = m0 = first = None
        rows.append({'ve_km_s': ve/1e3, 'mass_ratio_per_burn': L['mass_ratio_per_burn'], 'mass_ratio_total': RN,
                     'first_burn_propellant_t_fixed_end': L['burn_propellant_kg'][0]/1e3, 'propellant_t_fixed_end': L['propellant_kg']/1e3,
                     'departure_t_fixed_end': L['departure_kg']/1e3, 'tank_feedback_gain': g,
                     'propellant_t_with_tanks': None if P is None else P/1e3, 'tank_t': None if tanks is None else tanks/1e3,
                     'departure_t_with_tanks': None if m0 is None else m0/1e3,
                     'first_burn_propellant_t_with_tanks': None if first is None else first/1e3})
    return rows
