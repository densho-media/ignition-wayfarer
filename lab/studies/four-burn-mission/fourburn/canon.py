"""Scenario and canon access. The scenario TOML holds study inputs with a status each; canon numbers are read from
data/wayfarer_3d.toml and the as-built evidence, never typed twice."""
import json
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
TIERS = ('optimistic', 'central', 'pessimistic')


def scenario(name='v1'):
    return tomllib.loads((HERE/'scenarios'/f'{name}.toml').read_text())


def spec():
    return tomllib.loads((ROOT/'data/wayfarer_3d.toml').read_text())


def operating_point_json():
    return json.loads((ROOT/'references/p1_operating_point.json').read_text())


def tanks_json():
    return json.loads((ROOT/'references/evidence/longitudinal_tanks.json').read_text())


def val(p, tier='central'):
    """A scenario entry's value for a tier: {optimistic, central, pessimistic} tables, {value} tables or bare numbers."""
    if isinstance(p, dict):
        if tier in p:
            return p[tier]
        if 'value' in p:
            return p['value']
        if 'central' in p:
            return p['central']
        raise KeyError(p)
    return p


def reference():
    """The current working design numbers (canon) used as the comparison baseline."""
    s = spec(); op = s['physics']['operating_point']; fs = s['fuel_storage']; j = operating_point_json(); t = tanks_json()
    return {'ve_m_s': op['exhaust_velocity_m_s'], 'eta': op['directed_efficiency'], 'burnup': op['burnup'], 'recovery': op['recovery'],
            'absorbed_fraction': op['absorbed_fraction'], 'eps_J_kg': op['dhe3_specific_energy_J_kg'], 'he3_share': op['he3_mass_share'],
            'tank_dry_fraction': s['physics']['fuel_loads']['tank_dry_fraction'], 'protected_and_operational_kg': op['protected_and_operational_kg'],
            'legacy_inventory_kg': op['legacy_inventory_kg'], 'owner_case_e_departure_kg': op['owner_case_e_departure_mass_kg'],
            'density_kg_m3': fs['density_kg_m3'], 'op': j, 'tanks': t,
            'radiator_T_K': s['radiators']['temperature']['value'], 'radiator_emissivity': s['radiators']['emissivity']['value'],
            'radiator_effective_area_m2': s['radiators']['effective_area']['value'],
            'mass_budget': {i['id']: i['mass_kg'] for i in s['physics']['mass_budget']['items']},
            'fuel_storage_open_text': fs.get('open', '')}
