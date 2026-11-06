"""Radiators and heat classes. A radiator's specific mass (kg per W rejected) is its planform areal mass over the two-sided flux
2 eps sigma T^4, plus heat-transport hardware (pumps, manifolds, heat pipes) per W. Exhaust energy and radiation escaping to space are
never radiator loads; only heat deposited in permanent hardware is."""
from .const import SIGMA
from .canon import val


def flux_W_m2(T, eps):
    return 2*eps*SIGMA*T**4


def specific_kg_per_W(T, eps, areal_kg_m2, transport_kg_per_W):
    return areal_kg_m2/flux_W_m2(T, eps)+transport_kg_per_W


def classes(sc, tier='central', hot_kind='hot'):
    """Radiator classes for a tier: hot (1800 K heat pipes, or 'droplet' 1100 K), warm (driver/electronics) and the cryo penalty."""
    r = sc['radiators']; out = {}
    for name, key in (('hot', hot_kind), ('warm', 'warm')):
        c = r[key]; T = val(c['T_K'], tier); e = val(c['emissivity'], tier)
        a = val(c['areal_kg_m2'], tier); t = val(c['transport_kg_per_W'], tier)
        out[name] = {'kind': key, 'T_K': T, 'emissivity': e, 'areal_kg_m2': a, 'flux_W_m2': flux_W_m2(T, e),
                     'kg_per_W': specific_kg_per_W(T, e, a, t)}
    out['cryo_W_per_W'] = val(r['cryo']['W_per_W'], tier)
    return out


def best_hot(sc, tier):
    """The lighter of the 1800 K heat-pipe and the 1100 K droplet radiator for the hot loop at this tier (the hot loop's armour runs
    hotter than either)."""
    a = classes(sc, tier, 'hot'); b = classes(sc, tier, 'droplet')
    return a if a['hot']['kg_per_W'] <= b['hot']['kg_per_W'] else b
