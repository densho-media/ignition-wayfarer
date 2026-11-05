"""Purpose–Material Design System: material properties for engineering calculations (docs/MATERIALS.md). Pure, standard library.

get_property() evaluates one catalogue property at a temperature and returns a quantity that keeps its unit, basis, confidence, source,
verification, validity range and known/unknown status. It interpolates a temperature table only inside its range and never extrapolates;
a point value holds only at its stated temperature or inside its stated valid_K; an OPEN property, a Level C (speculative) material or a
variant's un-inherited parent value comes back unknown. require() turns an unknown quantity into an error, so a missing property cannot
produce an apparently validated result. The screens here evaluate candidates against the physics; they never adjust a physics model, a
canon value or a budget to make a material look viable, and their best verdict is 'within known limits', never 'approved'.

    python3 src/wayfarer/material_physics.py      # plasma-armor screen, ITER reference conduction case and the spec cross-check
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import materials as mats

TOLERANCE_K = 0.5


class UnknownProperty(ValueError):
    """A calculation asked for a property that is OPEN, out of its validated range or speculative."""


def _quantity(material_id, name, m, p, T, **kw):
    return dict(material_id=material_id, property=name, level=m['level'], unit=mats.UNITS.get(name), temperature_K=T,
                known=kw.pop('known', True), status=kw.pop('status', 'OK'), value=kw.pop('value', None), low=kw.pop('low', None),
                high=kw.pop('high', None), basis=(p or {}).get('basis'), confidence=(p or {}).get('confidence'),
                source=(p or {}).get('source'), verification=kw.pop('verification', None), valid_K=kw.pop('valid_K', None),
                verified=(p or {}).get('verified'), verified_against=(p or {}).get('verified_against'),
                condition=(p or {}).get('condition'), irradiation=(p or {}).get('irradiation', 'UNIRRADIATED') if p else None,
                rating=(p or {}).get('rating'), applies=(p or {}).get('applies', 'ALWAYS') if p else None,
                note=kw.pop('note', (p or {}).get('note', '')), **kw)


def _valid(p):
    if 'table_K' in p:
        return [p['table_K'][0], p['table_K'][-1]]
    if 'valid_K' in p:
        return list(p['valid_K'])
    if 'at_K' in p:
        return [p['at_K'], p['at_K']]
    return None


def get_property(material_id, property_name, temperature_K=None, db=None, allow_speculative=False):
    """One property of one material at temperature_K (K). Temperature-type properties (melting point, service limit, Tc) take none.
    Returns a quantity dict: known, status (OK, OPEN, OUT_OF_RANGE, NEEDS_TEMPERATURE, SPECULATIVE_BLOCKED, NOT_INHERITED), value or
    low/high, unit and provenance."""
    db = db or mats.load(); m = mats.get_material(material_id, db); T = temperature_K
    if property_name not in mats.UNITS:
        raise KeyError(f'unknown property {property_name}')
    if m['level'] == 'C' and not allow_speculative:
        return _quantity(material_id, property_name, m, None, T, known=False, status='SPECULATIVE_BLOCKED',
                         note='Level C (speculative) data never feeds a calculation unless explicitly allowed')
    props = m.get('properties', {}); p = props.get(property_name); via = None
    if p is None and property_name in m.get('inherits', []):
        p = db['materials'][m['parent']]['properties'][property_name]; via = m['parent']
    if p is None:
        if m.get('parent') and property_name in db['materials'][m['parent']].get('properties', {}):
            return _quantity(material_id, property_name, m, None, T, known=False, status='NOT_INHERITED',
                             note=f'the parent {m["parent"]} value is not transferable to this variant until measured')
        return _quantity(material_id, property_name, m, None, T, known=False, status='OPEN', note='OPEN in the catalogue')
    verification = mats.verification(p, db); valid = _valid(p)
    extra = dict(verification=verification, valid_K=valid, inherited_from=via)
    if property_name in mats.TEMPERATURE_PROPERTIES:
        return _quantity(material_id, property_name, m, p, T, value=p.get('value'), low=mats.bound(p), high=mats.bound(p, True),
                         phase_change=p.get('phase_change'), **extra)
    if T is None:
        if 'table_K' in p:
            return _quantity(material_id, property_name, m, p, T, known=False, status='NEEDS_TEMPERATURE', **extra)
        T = p.get('at_K')
    if valid is None or not valid[0]-TOLERANCE_K <= T <= valid[1]+TOLERANCE_K:
        return _quantity(material_id, property_name, m, p, T, known=False, status='OUT_OF_RANGE',
                         note=f'{T} K is outside the validated range {valid} K; no extrapolation', **extra)
    if 'table_K' in p:
        xs, ys = p['table_K'], p['values']; T = min(max(T, xs[0]), xs[-1])
        k = next(i for i in range(len(xs)-1) if T <= xs[i+1])
        v = ys[k]+(ys[k+1]-ys[k])*(T-xs[k])/(xs[k+1]-xs[k])
        return _quantity(material_id, property_name, m, p, temperature_K, value=v, low=v, high=v, **extra)
    if 'value' in p:
        return _quantity(material_id, property_name, m, p, T, value=p['value'], low=p['value'], high=p['value'], **extra)
    return _quantity(material_id, property_name, m, p, T, value=None, low=p['min'], high=p['max'], **extra)


def require(q, bound='value'):
    """The number of a known quantity: 'value' (a point or table), 'low' or 'high' (the conservative end of a range). Raises
    UnknownProperty for anything unknown, and for 'value' on a range (pick the conservative end explicitly)."""
    if not q['known']:
        raise UnknownProperty(f"{q['material_id']}.{q['property']}: {q['status']} ({q['note']})")
    v = q[bound]
    if v is None:
        raise UnknownProperty(f"{q['material_id']}.{q['property']}: a range ({q['low']}..{q['high']} {q['unit']}); ask for 'low' or 'high'")
    return v


def conductivity_integral(material_id, T1_K, T2_K, db=None):
    """Integral of k dT (W/m) from T1 to T2 over a tabulated conductivity, exact for its piecewise-linear table. Unknown (raises) outside it."""
    db = db or mats.load(); m = mats.get_material(material_id, db); p = m.get('properties', {}).get('thermal_conductivity')
    if p is None or 'table_K' not in p:
        raise UnknownProperty(f'{material_id}.thermal_conductivity: no temperature table')
    xs, ys = p['table_K'], p['values']; lo, hi = sorted((T1_K, T2_K))
    if lo < xs[0]-TOLERANCE_K or hi > xs[-1]+TOLERANCE_K:
        raise UnknownProperty(f'{material_id}.thermal_conductivity: {lo}-{hi} K outside the table {xs[0]}-{xs[-1]} K; no extrapolation')
    k = lambda T: require(get_property(material_id, 'thermal_conductivity', min(max(T, xs[0]), xs[-1]), db))
    pts = [lo, *[x for x in xs if lo < x < hi], hi]
    total = sum((b-a)*(k(a)+k(b))/2 for a, b in zip(pts, pts[1:]))
    return total if T2_K >= T1_K else -total


def conduction_drop(material_id, heat_flux_W_m2, thickness_m, cold_side_K, db=None):
    """Steady 1-D conduction through a slab of temperature-dependent conductivity: the hot-side temperature that carries heat_flux through
    thickness from cold_side_K (solves the Kirchhoff integral, bisection). Raises UnknownProperty when the answer leaves the table."""
    db = db or mats.load(); target = heat_flux_W_m2*thickness_m
    xs = mats.get_material(material_id, db)['properties']['thermal_conductivity']['table_K']
    if conductivity_integral(material_id, cold_side_K, xs[-1], db) < target:
        raise UnknownProperty(f'{material_id}: the hot side would exceed the conductivity table ({xs[-1]} K); no extrapolation')
    lo, hi = cold_side_K, xs[-1]
    for _ in range(80):
        mid = (lo+hi)/2
        lo, hi = (mid, hi) if conductivity_integral(material_id, cold_side_K, mid, db) < target else (lo, mid)
    return (lo+hi)/2


VERDICTS = ('EXCEEDS_LIMIT', 'NOT_EVALUABLE', 'WITHIN_CHECKED_LIMITS')     # worst first; there is no 'approved' verdict
# Application requirement keys that make a condition mandatory for a screen.
LIFE_REQUIREMENTS = {'replacement_interval', 'service_life', 'life'}
RADIATION_REQUIREMENTS = {'neutron_fluence', 'dose_limits', 'source_spectrum', 'radiation_heating'}
EVIDENCE_ORDER = {v: i for i, v in enumerate(mats.VERIFICATION)}          # 0 strongest


def _limit(name, mid, T, dpa, db, allow_speculative):
    """One applicable limit at T: (state, record). state: None (not applicable), 'violated', 'passed' or 'unknown'."""
    q = get_property(mid, name, db=db, allow_speculative=allow_speculative)
    if not q['known']:
        return 'unknown', dict(limit=name, status=q['status'])
    if q.get('applies') == 'IRRADIATED' and not (dpa or 0) > 0:
        return None, None
    rec = dict(limit=name, low=q['low'], high=q['high'], unit='K', rating=q.get('rating'), basis=q['basis'], verification=q['verification'])
    if name == 'min_service_temperature':
        bad, rec['rule'] = T < q['high'], f"requires T >= {q['high']} K (conservative upper end of the floor)"
    else:
        bad, rec['rule'] = T >= q['low'] if name in ('melting_point', 'critical_temperature') else T > q['low'], \
            f"requires T {'<' if name in ('melting_point', 'critical_temperature') else '<='} {q['low']} K (conservative low end)"
    return ('violated' if bad else 'passed'), rec


def screen_application(application_id, conditions=None, db=None, allow_speculative=False):
    """Screen each layer of an application against its purposes' required properties at the supplied operating conditions:
    {role or '*': {'temperature_K': T, 'neutron_fluence_dpa': dose, 'life_h': hours}}.

    Verdict per layer and for the application (worst layer):
      EXCEEDS_LIMIT          a known limit (phase change, service limit, superconducting Tc, irradiated floor) is violated at the stated
                             conditions; reported even when other data are missing.
      NOT_EVALUABLE          something needed is missing: an operating condition (temperature, fluence where radiation matters, life where
                             the application has a life requirement), a required property, a value valid at the operating temperature,
                             evidence better than UNVERIFIED, irradiated data under a stated fluence, a lifetime-rated limit, an OPEN
                             application requirement, or speculative data without allow_speculative.
      WITHIN_CHECKED_LIMITS  every required numeric property is known at the operating temperature and every applicable known limit passes.
                             The result lists what was checked and what (qualitative requirements) was not. It is a screen: never
                             qualification, never approval (a Drive canon decision with an evaluated environment and life).
    Missing data never counts as safe; a screening estimate never counts as a lifetime rating."""
    db = db or mats.load(); a = mats.get_application(application_id, db); conditions = conditions or {}
    reqs_app = a.get('requirements', {})
    open_reqs = {k: v for k, v in reqs_app.items() if str(v).startswith('OPEN')}
    out = []
    for l in a['layers']:
        mid = l['material']; m = db['materials'][mid]
        c = {**conditions.get('*', {}), **conditions.get(l['role'], {})}
        T, dpa, life = c.get('temperature_K'), c.get('neutron_fluence_dpa'), c.get('life_h')
        reqs = {r for pid in l['purposes'] for r in db['purposes'][pid]['required_properties']}
        numeric = sorted(r for r in reqs if r in mats.UNITS)
        radiation = 'radiation_response' in reqs or bool(RADIATION_REQUIREMENTS & set(reqs_app))
        life_required = bool(LIFE_REQUIREMENTS & set(reqs_app))
        missing_conditions = [k for k, need in (('temperature_K', True), ('neutron_fluence_dpa', radiation), ('life_h', life_required))
                              if need and c.get(k) is None]
        missing, out_of_range, weak, unirradiated, blocked, evaluated = [], [], [], [], [], {}
        for r in numeric:
            if r in mats.TEMPERATURE_PROPERTIES:
                continue                                                    # limits, below
            if T is None:
                out_of_range.append(dict(property=r, status='NO_OPERATING_TEMPERATURE')); continue
            q = get_property(mid, r, T, db, allow_speculative)
            if q['status'] == 'SPECULATIVE_BLOCKED':
                blocked.append(r)
            elif not q['known'] and q['status'] in ('OPEN', 'NOT_INHERITED'):
                missing.append(r)
            elif not q['known']:
                out_of_range.append(dict(property=r, status=q['status'], valid_K=q['valid_K']))
            elif q['verification'] == 'UNVERIFIED':
                weak.append(dict(property=r, verification=q['verification']))
            elif dpa and q['irradiation'] != 'IRRADIATED':
                unirradiated.append(r)
            else:
                evaluated[r] = {k: q[k] for k in ('value', 'low', 'high', 'unit', 'basis', 'confidence', 'verification', 'condition')}
        limits = [n for n in ('melting_point', 'max_service_temperature', 'min_service_temperature', 'critical_temperature')
                  if n in reqs or n in ('melting_point', 'min_service_temperature') or (n == 'max_service_temperature' and n in m.get('properties', {}))]
        violations, checked_limits, unknown_limits, unchecked_limits = [], [], [], []
        if T is not None:
            for n in limits:
                state, rec = _limit(n, mid, T, dpa, db, allow_speculative)
                if state == 'violated':
                    violations.append(rec)
                elif state == 'passed':
                    checked_limits.append(rec)
                elif state == 'unknown' and n in reqs:
                    (blocked if rec['status'] == 'SPECULATIVE_BLOCKED' else unknown_limits).append(n)
                if n == 'min_service_temperature' and state is None and radiation and dpa is None:
                    unchecked_limits.append(n)                               # an irradiated floor cannot be checked without the dose
        for rec in checked_limits + violations:
            if rec['verification'] == 'UNVERIFIED':
                weak.append(dict(property=rec['limit'], verification='UNVERIFIED'))
        rated = [r for r in checked_limits if r['limit'] == 'max_service_temperature' and r['rating'] == 'LIFETIME_RATED']
        life_gap = life_required and not rated
        reasons = []
        if violations:
            reasons += [f"{v['limit']} violated at {T} K: {v['rule']} ({v['basis']}, {v['rating'] or 'material constant'}, {v['verification']})"
                        for v in violations]
        if open_reqs:
            reasons.append('application requirements OPEN: ' + ', '.join(f'{k} ({v})' for k, v in open_reqs.items()))
        if missing_conditions:
            reasons.append('operating conditions missing: ' + ', '.join(missing_conditions))
        if missing or unknown_limits:
            reasons.append('required properties OPEN: ' + ', '.join(missing + unknown_limits))
        if unchecked_limits:
            reasons.append('limits not checkable without the neutron dose: ' + ', '.join(unchecked_limits))
        if out_of_range:
            reasons.append('no value valid at the operating temperature: ' + ', '.join(o['property'] for o in out_of_range))
        if weak:
            reasons.append('evidence UNVERIFIED: ' + ', '.join(w['property'] for w in weak))
        if unirradiated:
            reasons.append(f'only unirradiated data at {dpa} dpa: ' + ', '.join(unirradiated))
        if blocked or (m['level'] == 'C' and not allow_speculative):
            reasons.append('Level C (speculative) data blocked: pass allow_speculative=True for a labelled speculative screen')
        if life_gap:
            reasons.append('life requirement present but no LIFETIME_RATED service limit (screening estimates only)')
        if any(r['rating'] == 'SCREENING_ESTIMATE' for r in checked_limits + violations):
            reasons.append('service limits are SCREENING_ESTIMATE thresholds, not lifetime ratings')
        incomplete = (open_reqs or missing_conditions or missing or unknown_limits or unchecked_limits or out_of_range or weak or unirradiated or blocked
                      or life_gap or (m['level'] == 'C' and not allow_speculative))
        verdict = 'EXCEEDS_LIMIT' if violations else 'NOT_EVALUABLE' if incomplete else 'WITHIN_CHECKED_LIMITS'
        ev = [x['verification'] for x in evaluated.values()] + [r['verification'] for r in checked_limits]
        out.append(dict(role=l['role'], material=mid, level=m['level'], selection=l['selection'], geometry=l['geometry'], verdict=verdict,
                        reasons=reasons, conditions=c, missing_conditions=missing_conditions, missing_properties=missing + unknown_limits,
                        out_of_range=out_of_range, unverified=weak, unirradiated=unirradiated, speculative=m['level'] == 'C',
                        speculative_allowed=bool(allow_speculative), violations=violations, checked_limits=checked_limits, unchecked_limits=unchecked_limits,
                        evaluated_properties=evaluated, unchecked_requirements=sorted(r for r in reqs if r not in mats.UNITS),
                        weakest_evidence=max(ev, key=EVIDENCE_ORDER.get) if ev else None, lifetime_evaluated=bool(rated)))
    worst = min((l['verdict'] for l in out), key=VERDICTS.index)
    return dict(application=application_id, title=a['title'], engineering_status=a['engineering_status'], verdict=worst, layers=out,
                approved=False, qualification='NOT_QUALIFIED',
                note='A screen against the catalogue, not component qualification: approval is a Drive canon decision with an evaluated '
                     'operating environment and lifetime.')


# Physics integration boundary (docs/MATERIALS.md "Physics integration"). Canon keeps authority: a material-specific spec value is compared
# with the catalogue, a difference becomes a review item, and nothing here edits the spec. usage: CROSS_CHECK (compared on every run),
# NOT_LINKED (the catalogue cannot check it yet: OPEN property, no material named, or no value at that temperature), DIRECT_LOOKUP (the
# calculation reads the catalogue itself). Row: (module, spec path, material, property, temperature_K or None, tolerance, usage, next step).
INTEGRATION = [
    ('fuel_loads', ('physics', 'fuel_loads', 'strut_E_Pa'), 'MAT-TI6AL4V', 'elastic_modulus', None, 0.02, 'CROSS_CHECK',
     'keep the spec value; read it through reference_value() once the strut temperature and allowables are sourced'),
    ('fuel_loads', ('physics', 'fuel_loads', 'strut_yield_Pa'), 'MAT-TI6AL4V', 'yield_strength', None, 0.02, 'CROSS_CHECK',
     'a room-temperature typical yield is used as a design value: needs an allowable at the strut temperature (MMPDS class)'),
    ('fuel_loads', ('physics', 'fuel_loads', 'strut_density_kg_m3'), 'MAT-TI6AL4V', 'density', None, 0.02, 'CROSS_CHECK', 'safe to link'),
    ('fuel_loads', ('physics', 'fuel_loads', 'shell', 'density_kg_m3'), 'MAT-ALLI-2195', 'density', None, 0.02, 'CROSS_CHECK', 'safe to link'),
    ('fuel_loads', ('physics', 'fuel_loads', 'shell', 'yield_Pa'), 'MAT-ALLI-2195', 'yield_strength', None, 0.02, 'CROSS_CHECK',
     'the spec takes the low end of a thickness/direction-dependent range; a weld and cryogenic allowable is OPEN'),
    ('fuel_loads', ('physics', 'fuel_loads', 'shell', 'E_Pa'), 'MAT-ALLI-2195', 'elastic_modulus', None, 0.02, 'CROSS_CHECK', 'safe to link'),
    ('fuel_loads', ('physics', 'fuel_loads', 'skirt', 'density_kg_m3'), 'MAT-CFRP', 'density', None, 0.02, 'CROSS_CHECK', 'safe to link'),
    ('fuel_loads', ('physics', 'fuel_loads', 'skirt', 'E_Pa'), 'MAT-CFRP', 'elastic_modulus', None, 0.02, 'NOT_LINKED',
     'deferred: CFRP modulus is layup- and direction-specific (OPEN); name the layup first'),
    ('fuel_loads', ('physics', 'fuel_loads', 'skirt', 'strength_Pa'), 'MAT-CFRP', 'yield_strength', None, 0.02, 'NOT_LINKED',
     'deferred: laminate strength is layup-specific (OPEN)'),
    ('fuel_loads', ('physics', 'fuel_loads', 'skirt', 'conductivity_integral_W_m'), 'MAT-CFRP', 'thermal_conductivity', None, 0.02, 'NOT_LINKED',
     'review item: the spec comment calls the integral G-10-class (glass-epoxy) for a CFRP skirt; source a CFRP or G-10 k(T) table'),
    ('radiator_zones / heat_rejection', ('radiators', 'zones', 'emissivity'), 'MAT-AZ93', 'emissivity', None, 0.01, 'CROSS_CHECK',
     'beginning-of-life value; the spec margin covers end of life through solar absorptance, not emissivity'),
    ('spec / thermal_budget / operating_point', ('radiators', 'emissivity', 'value'), 'MAT-RAD-NPE01', 'emissivity', 1800.0, 0.01, 'NOT_LINKED',
     'deferred: the 0.90 hot-face emissivity is WORKING canon (OD-023); the nano-emitter variant has no measured value'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'layers', 0, 'emissivity'), 'MAT-TZM', 'emissivity', 1204.0, 0.01, 'NOT_LINKED',
     'deferred: polished Mo/TZM emissivity at about 1200 K is OPEN in the catalogue'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'layers', 1, 'emissivity'), 'MAT-TI-CP', 'emissivity', 805.0, 0.01, 'NOT_LINKED',
     'deferred: polished Ti / superalloy foil emissivity is OPEN in the catalogue'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'layers', 2, 'emissivity'), 'MAT-AU', 'emissivity', 493.0, 0.01, 'CROSS_CHECK',
     'review item: the spec 0.05 lies above polished gold (0.02-0.03); it may hold a degradation or film margin that should be stated'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'foil', 0, 'density'), 'MAT-TZM', 'density', None, 0.02, 'CROSS_CHECK', 'safe to link'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'foil', 1, 'density'), 'MAT-TI6AL4V', 'density', None, 0.02, 'CROSS_CHECK', 'safe to link'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'foil', 2, 'density'), 'MAT-TI-CP', 'density', None, 0.02, 'CROSS_CHECK',
     'gold-coated Ti foil: the film adds mass the catalogue does not model'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'foil', 0, 'cte'), 'MAT-TZM', 'thermal_expansion', 1204.0, 0.05, 'NOT_LINKED',
     'deferred: mean CTE 300-1204 K is not in the catalogue'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'foil', 1, 'cte'), 'MAT-TI6AL4V', 'thermal_expansion', 805.0, 0.05, 'CROSS_CHECK',
     'the catalogue holds only a room-temperature CTE: add a mean-CTE table before linking'),
    ('radiator_zones', ('radiators', 'zones', 'bulkhead', 'standoff', 'k_W_mK'), 'MAT-YSZ', 'thermal_conductivity', None, 0.02, 'CROSS_CHECK',
     'room-temperature dense YSZ; the standoff runs hot and may be C/C: needs k(T) of the chosen standoff material'),
    ('heat_rejection', ('thermal', 'loops', 'warm', 'example', 'emissivity'), None, 'emissivity', None, 0.0, 'NOT_LINKED',
     'deferred: the warm-loop example names no surface material'),
    ('forward_shield', ('forward_shield', 'bumper_facing', 'seam_cte_per_K'), None, 'thermal_expansion', None, 0.0, 'NOT_LINKED',
     'deferred: the bumper facing material is not named; 2.3e-5 /K is aluminium-class'),
    ('material_physics.iter_reference_case', None, 'MAT-W', 'thermal_conductivity', None, 0.0, 'DIRECT_LOOKUP',
     'a published ITER reference case only; no Wayfarer calculation reads the catalogue yet'),
]
SPEC_LINKS = [(path, mid, name, tol) for _, path, mid, name, T, tol, usage, _ in INTEGRATION if usage == 'CROSS_CHECK' and T is None]


def reference_value(material_id, property_name, temperature_K=None, bound='value', db=None, allow_speculative=False):
    """Read-only adapter for an engineering module: the catalogue number at temperature_K (require() semantics: raises UnknownProperty when
    it is OPEN, out of range or speculative) together with its quantity, so the caller can record unit, basis, evidence and condition."""
    q = get_property(material_id, property_name, temperature_K, db, allow_speculative)
    return require(q, bound), q


def compare_to_reference(value, material_id, property_name, temperature_K=None, tolerance=0.02, db=None):
    """Compare a canon or spec value with the catalogue without changing either: CONSISTENT (inside the catalogue value or range plus a
    relative tolerance), DIFFERS (a review item) or NOT_CHECKABLE (the catalogue has no value valid there)."""
    q = get_property(material_id, property_name, temperature_K, db)
    row = dict(material=material_id, property=property_name, value=value, temperature_K=temperature_K, catalogue_low=q['low'],
               catalogue_high=q['high'], unit=q['unit'], basis=q['basis'], confidence=q['confidence'], verification=q['verification'],
               catalogue_status=q['status'])
    row['status'] = 'NOT_CHECKABLE' if not q['known'] else \
        'CONSISTENT' if q['low']*(1-tolerance) <= value <= q['high']*(1+tolerance) else 'DIFFERS'
    return row


def _at_path(s, path):
    for k in path:
        s = s[k]
    return s


def spec_crosscheck(s, db=None):
    """The integration table evaluated on the current spec: one row per INTEGRATION entry with its usage, status (CONSISTENT, DIFFERS,
    NOT_CHECKABLE, NOT_LINKED, DIRECT_LOOKUP) and next step. A DIFFERS row is an engineering review item; the spec keeps authority."""
    db = db or mats.load(); out = []
    for module, path, mid, name, T, tol, usage, step in INTEGRATION:
        base = dict(module=module, spec_key=None if path is None else '.'.join(map(str, path)), material=mid, property=name, usage=usage,
                    next_step=step)
        if usage == 'CROSS_CHECK':
            row = compare_to_reference(_at_path(s, path), mid, name, T, tol, db)
            row.update(base); row['spec_value'] = row.pop('value'); row['consistent'] = {'CONSISTENT': True, 'DIFFERS': False}.get(row['status'])
        else:
            row = dict(base, status=usage, spec_value=None if path is None else _at_path(s, path), consistent=None)
        out.append(row)
    return out


def iter_reference_case(db=None):
    """A worked conduction example on ITER's published divertor reference (not Wayfarer data, whose heat flux is OPEN, OD-025): the W
    temperature rise across a 6 mm armour at the ITER steady 10 MW/m2 above an assumed 600 K interface. Shows the lookup and the
    no-extrapolation rule; it says nothing about Wayfarer's armour."""
    db = db or mats.load(); q, L, Tc = 10.0e6, 0.006, 600.0
    Th = conduction_drop('MAT-W', q, L, Tc, db)
    lim = get_property('MAT-W', 'max_service_temperature', db=db)
    return dict(label='REFERENCE_CASE (ITER divertor class; not Wayfarer data)', heat_flux_W_m2=q, armour_m=L, interface_K=Tc,
                surface_K=round(Th, 1), rise_K=round(Th-Tc, 1), w_service_limit_K=[lim['low'], lim['high']],
                source='pitts2019 heat flux; hpl1972 conductivity', note='1-D slab, no contact resistance, unirradiated W')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s, *_ = load(); db = mats.load()
    example = {'hot_face': {'temperature_K': 1100.0}, 'cooling_conduit': {'temperature_K': 450.0}}
    print(json.dumps(dict(evidence=mats.evidence_counts(db), plasma_armor_no_conditions=screen_application('APP-DRV-PFC', db=db),
                          plasma_armor_example=screen_application('APP-DRV-PFC', example, db=db), iter_reference_case=iter_reference_case(db),
                          integration=spec_crosscheck(s, db)), indent=1, default=str))
