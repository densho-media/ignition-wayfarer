"""Cryogenic propellant storage: capacity per species, tank mass, vessel count, farm length, axial load and cooling, compared with the
as-built TANK-AXIAL farm (13 vessels). Species are stored separately; a vessel built for one species is not assumed to hold another
(He-3 needs the 3 K stage, D2 and H2 the ~20 K shield; densities and wall loads differ)."""
import math

from .const import G0
from .canon import val

SPECIES = ('helium_3', 'deuterium', 'hydrogen')


def need(loaded_kg, sc, density):
    """Vessel capacity (m3) each species needs: loaded liquid (mission + reserve + allowances) plus ullage."""
    u = val(sc['tanks']['ullage'])
    return {k: loaded_kg.get(k, 0.0)/density[k]*(1+u) for k in SPECIES}


def mass_kg(capacity_m3, sc, tier='central'):
    return val(sc['tanks']['mass_per_m3'], tier)*sum(capacity_m3.values())


def compare(loaded_kg, sc, density, accel_g=1.5, tier='central'):
    """Required against existing capacity per species, the vessels and farm length needed, the axial load at accel_g and cooling."""
    t = sc['tanks']; cap = {k: t['capacity_m3'][k] for k in SPECIES}; v = t['vessel_m3']
    req = need(loaded_kg, sc, density)
    out = {'required_m3': req, 'existing_m3': cap, 'surplus_m3': {k: cap[k]-req[k] for k in SPECIES},
           'ratio': {k: (req[k]/cap[k]) for k in SPECIES}}
    out['vessels_L_equivalent'] = sum(req.values())/v['L']
    existing_vessels = 13; existing_L_eq = sum(cap.values())/v['L']
    out['farm_length_m'] = t['bay_length_m']['value']*max(1.0, out['vessels_L_equivalent']/existing_L_eq)
    out['farm_bays'] = out['vessels_L_equivalent']/existing_L_eq
    total_kg = sum(loaded_kg.get(k, 0.0) for k in SPECIES)
    out['axial_load_N'] = (total_kg+mass_kg(req, sc, tier))*accel_g*G0
    out['axial_load_ratio'] = out['axial_load_N']/t['existing_axial_limit_N']['value']
    out['cooling_W'] = t['cooling_W_per_m3']['value']*sum(req.values())
    out['tank_mass_kg'] = mass_kg(req, sc, tier)
    out['outcome'] = outcome(out)
    return out


def outcome(c):
    """The owner brief's six outcomes, judged per species and in total."""
    r = c['ratio']; tot = sum(c['required_m3'].values())/sum(c['existing_m3'].values())
    if all(x <= 1.0 for x in r.values()):
        return 'existing tanks sufficient' if max(r.values()) > 0.6 else 'tanks can be reduced'
    if tot <= 1.0:
        return 'existing tanks sufficient with changed allocation (re-rated vessels; He-3 3 K stage only on He-3 vessels)'
    if tot <= 2.0:
        return 'additional tanks required'
    if tot <= 20.0:
        return 'complete storage redesign required'
    return 'mission infeasible regardless of reasonable tank enlargement'


def vessel_dimensions(capacity_m3, radius_m=6.45):
    """Length of a cylinder with 2:1 heads holding capacity_m3 at the L-class inner radius (envelope 6.75 m less the 0.3 m wall)."""
    heads = 2*(2/3*math.pi*radius_m**2*radius_m/2)
    return max(0.0, (capacity_m3-heads)/(math.pi*radius_m**2))+radius_m
