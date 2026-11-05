"""Purpose–Material Design System (PMDS): load, look up and validate the material catalogue (docs/MATERIALS.md). Pure, standard library.

Four files in data/materials/ share one set of stable IDs: purposes (P01-P14), the material master catalogue (MAT-*, with its
references), applications (APP-*: purposes and candidate layers tied to existing Wayfarer components, and the display materials that
carry each layer) and appearances (how a material looks in Blender). The catalogue is an engineering reference and candidate-selection
system; the Drive workbooks stay the authority (AGENTS.md "Drive canon"). It travels outside the spec hash, like the detail packs: an edit
stales only the assets whose bound records changed (asset_hash), never the whole ship.
"""
import copy
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]
DIR = 'data/materials'
FILES = ('catalogue', 'purposes', 'applications', 'appearances')

# Every material states each CORE property as a property or in its `open` list; BEHAVIOUR are qualitative statements.
CORE = ('density', 'specific_heat', 'thermal_conductivity', 'thermal_expansion', 'yield_strength', 'elastic_modulus', 'fracture_toughness',
        'electrical_resistivity', 'melting_point', 'max_service_temperature', 'emissivity')
BEHAVIOUR = ('creep', 'fatigue', 'radiation_response', 'chemical_compatibility', 'magnetic')
UNITS = {'density': 'kg/m3', 'specific_heat': 'J/(kg K)', 'thermal_conductivity': 'W/(m K)', 'thermal_expansion': '1/K',
         'yield_strength': 'Pa', 'ultimate_strength': 'Pa', 'elastic_modulus': 'Pa', 'fracture_toughness': 'Pa m^0.5',
         'electrical_resistivity': 'ohm m', 'melting_point': 'K', 'max_service_temperature': 'K', 'ductile_brittle_transition': 'K',
         'emissivity': '1', 'solar_absorptance': '1', 'critical_temperature': 'K', 'hydrogen_content': '1',
         'min_service_temperature': 'K'}
TEMPERATURE_PROPERTIES = {'melting_point', 'max_service_temperature', 'min_service_temperature', 'ductile_brittle_transition',
                          'critical_temperature'}
# A service-temperature limit is a SCREENING_ESTIMATE (a literature threshold for screening) unless a qualified long-life rating for the
# stated grade, environment and life exists (LIFETIME_RATED). No catalogue entry is LIFETIME_RATED yet.
SERVICE_LIMITS = ('max_service_temperature', 'min_service_temperature')
RATINGS = {'SCREENING_ESTIMATE', 'LIFETIME_RATED'}
BASES = {'MEASURED', 'HANDBOOK', 'TYPICAL', 'SPECIFICATION_MINIMUM', 'ESTIMATE', 'THEORETICAL', 'FICTIONAL'}
CONFIDENCE = {'HIGH', 'MEDIUM', 'LOW'}
# Evidence strength of one catalogue number, strongest first (docs/MATERIALS.md "Verification"):
#   PRIMARY_VERIFIED    the number was read in the primary source, authoritative handbook table or original publication
#   SECONDARY_VERIFIED  the number was matched against a secondary reference, technical summary, datasheet or reproduction
#   TRANSCRIBED         a source is named, but the number has not been independently checked against it
#   UNVERIFIED          the source, or the source's support for this number, is not established
# A reference states the default for the numbers that cite it (TRANSCRIBED or UNVERIFIED). Only a property can be PRIMARY_ or
# SECONDARY_VERIFIED, and then it records `verified` (what was compared, when), `verified_against` (the reference) and `condition` (grade,
# form, temper, irradiation and test condition the number belongs to). PRIMARY_VERIFIED also needs a primary-kind reference, a `locator`
# and an applicable temperature range (_primary_fails). How many numbers are verified is a state of the catalogue, never a rule.
VERIFICATION = ('PRIMARY_VERIFIED', 'SECONDARY_VERIFIED', 'TRANSCRIBED', 'UNVERIFIED')
REFERENCE_VERIFICATION = {'TRANSCRIBED', 'UNVERIFIED'}
VERIFIED = {'PRIMARY_VERIFIED', 'SECONDARY_VERIFIED'}
# Reference kinds that can carry a PRIMARY_VERIFIED check: the original measurement, an authoritative handbook or critical-review table,
# a standard or procurement specification, an agency database or the producer's datasheet for that grade. A secondary listing, a review
# that quotes others or the project's own canon mirror can support SECONDARY_VERIFIED at most.
PRIMARY_KINDS = {'handbook', 'materials handbook', 'critical review', 'journal', 'book', 'standard', 'procurement specification', 'agency',
                 'manufacturer'}
# Neutron state a number belongs to (default UNIRRADIATED): an unirradiated number never stands for a component under a stated fluence.
IRRADIATION = {'UNIRRADIATED', 'IRRADIATED'}
# When a limit applies (default ALWAYS); an IRRADIATED limit (CuCrZr embrittlement floor) is checked only under a stated fluence.
APPLIES = {'ALWAYS', 'IRRADIATED'}
# Properties that differ with direction in a fibre composite or textured product: an `anisotropic` material names `direction` for them.
DIRECTIONAL = {'thermal_conductivity', 'thermal_expansion', 'yield_strength', 'ultimate_strength', 'elastic_modulus', 'fracture_toughness',
               'electrical_resistivity'}
PHASE = {'melting', 'decomposition', 'sublimation'}
LEVELS = {'A', 'B', 'C'}
SELECTION = {'CANDIDATE', 'PREFERRED', 'REJECTED'}
GEOMETRY = {'DRAWN', 'NOT_DRAWN', 'PROTOTYPE_STUDY'}
APPEARANCE_BASIS = {'PBR_REFERENCE', 'FAMILY', 'ARTISTIC'}
STATUSES = {'LOCKED', 'BASELINE', 'WORKING', 'PROVISIONAL', 'OPEN', 'PROTOTYPE'}

_CACHE = {}


def texts(root=ROOT):
    """{file stem: text} of the four catalogue files."""
    return {name: (Path(root)/DIR/f'{name}.toml').read_text() for name in FILES}


def parse(text_map):
    t = {k: tomllib.loads(v) for k, v in text_map.items()}
    return dict(materials=t['catalogue'].get('material', {}), references=t['catalogue'].get('reference', {}),
                purposes=t['purposes'].get('purpose', {}), applications=t['applications'].get('application', {}),
                appearances=t['appearances'].get('appearance', {}))


def load(root=ROOT, sources=None, families=None):
    """The validated catalogue (a deep copy). sources: the source map's records (checks canon_ref/open_refs); families: the exterior
    family keys appearances may name. Identical file contents are validated once per process."""
    tm = texts(root)
    key = (tuple(tm.values()), None if sources is None else tuple(sorted(sources)), None if families is None else tuple(sorted(families)))
    if key not in _CACHE:
        db = parse(tm)
        fails = validate(db, sources, families)
        if fails:
            raise ValueError('Material catalogue: ' + '; '.join(fails))
        _CACHE.clear(); _CACHE[key] = db
    return copy.deepcopy(_CACHE[key])


def _property_fails(where, name, p):
    out = []
    unit = UNITS.get(name)
    if unit is None:
        return [f'{where}: unknown property {name}']
    if p.get('unit') != unit:
        out.append(f'{where}: unit {p.get("unit")!r}, expected {unit!r}')
    if p.get('basis') not in BASES:
        out.append(f'{where}: basis {p.get("basis")!r}')
    if p.get('confidence') not in CONFIDENCE:
        out.append(f'{where}: confidence {p.get("confidence")!r}')
    if not p.get('source'):
        out.append(f'{where}: no source')
    shapes = [('value' in p), ('min' in p or 'max' in p), ('table_K' in p or 'values' in p)]
    if sum(shapes) != 1:
        return out + [f'{where}: give exactly one of value, min/max or table_K/values']
    if 'value' in p and name not in TEMPERATURE_PROPERTIES and 'at_K' not in p:
        out.append(f'{where}: a point value needs at_K')
    if ('min' in p or 'max' in p) and not (isinstance(p.get('min'), (int, float)) and isinstance(p.get('max'), (int, float)) and p['min'] <= p['max']):
        out.append(f'{where}: range needs min <= max')
    if 'table_K' in p or 'values' in p:
        T, v = p.get('table_K', []), p.get('values', [])
        if len(T) < 2 or len(T) != len(v) or any(b <= a for a, b in zip(T, T[1:])):
            out.append(f'{where}: table needs >= 2 strictly increasing temperatures with one value each')
    if 'valid_K' in p and not (len(p['valid_K']) == 2 and p['valid_K'][0] <= p['valid_K'][1]):
        out.append(f'{where}: valid_K needs [low, high]')
    if name == 'melting_point' and p.get('phase_change') not in PHASE:
        out.append(f'{where}: melting_point needs phase_change in {sorted(PHASE)}')
    if name in ('emissivity', 'solar_absorptance', 'hydrogen_content'):
        vals = [p.get('value'), p.get('min'), p.get('max'), *p.get('values', [])]
        if any(x is not None and not 0.0 <= x <= 1.0 for x in vals):
            out.append(f'{where}: {name} must lie in [0, 1]')
    else:
        vals = [p.get('value'), p.get('min'), p.get('max'), *p.get('values', [])]
        if any(x is not None and x < 0 for x in vals):
            out.append(f'{where}: negative {name}')
    return out


def verification(p, db):
    """The evidence state of one property entry: its own, else its source's default."""
    return p.get('verification') or db['references'][p['source']]['verification']


def evidence_counts(db, level=None):
    """{verification: number of catalogue property entries} (optionally one level), strongest first."""
    out = {v: 0 for v in VERIFICATION}
    for m in db['materials'].values():
        if level is None or m['level'] == level:
            for p in m.get('properties', {}).values():
                out[verification(p, db)] += 1
    return out


def bound(p, upper=False):
    """The low (or high) end of a property entry, None for an unknown one."""
    if p is None:
        return None
    if 'value' in p:
        return p['value']
    if 'min' in p:
        return p['max'] if upper else p['min']
    return max(p['values']) if upper else min(p['values'])


def _primary_fails(where, name, p, R):
    """A PRIMARY_VERIFIED claim is traceable: a primary-kind reference, the table/figure/dataset that holds the number, the grade and
    test condition, and the temperature range the number applies to (units and value shape are checked with every property)."""
    out, ref = [], R.get(p.get('verified_against'), {})
    if ref.get('kind') not in PRIMARY_KINDS:
        out.append(f'{where}: PRIMARY_VERIFIED needs verified_against a primary source (kind in {sorted(PRIMARY_KINDS)}), '
                   f'not {ref.get("kind")!r}')
    if not p.get('locator'):
        out.append(f'{where}: PRIMARY_VERIFIED names the `locator` (table, figure, page or dataset) holding the verified number')
    if name not in TEMPERATURE_PROPERTIES and 'table_K' not in p and 'valid_K' not in p:
        out.append(f'{where}: PRIMARY_VERIFIED states the temperature range it applies to (valid_K or a table)')
    return out


def validate(db, sources=None, families=None):
    """Referential and physical-plausibility checks; returns the list of failures."""
    fails = []
    M, R, P, A, X = db['materials'], db['references'], db['purposes'], db['applications'], db['appearances']
    for rid, r in R.items():
        if not r.get('title') or r.get('verification') not in REFERENCE_VERIFICATION:
            fails.append(f'reference {rid}: needs title and a default verification in {sorted(REFERENCE_VERIFICATION)}')
    for mid, m in M.items():
        w = f'material {mid}'
        if not mid.startswith('MAT-'):
            fails.append(f'{w}: IDs start with MAT-')
        for k in ('name', 'level', 'family', 'composition'):
            if not m.get(k):
                fails.append(f'{w}: missing {k}')
        if m.get('level') not in LEVELS:
            fails.append(f'{w}: level {m.get("level")!r}')
        props, opened = m.get('properties', {}), m.get('open', [])
        for name in set(props) & set(opened):
            fails.append(f'{w}: {name} is both given and open')
        for name in CORE:
            if name not in props and name not in opened:
                fails.append(f'{w}: {name} neither given nor open (unknown data must stay explicit)')
        for name in opened:
            if name not in UNITS:
                fails.append(f'{w}: open names unknown property {name}')
        for name, p in props.items():
            fails += _property_fails(f'{w}.{name}', name, p)
            if p.get('source') and p['source'] not in R:
                fails.append(f'{w}.{name}: unknown source {p["source"]}')
            if p.get('basis') == 'FICTIONAL' and m.get('level') != 'C':
                fails.append(f'{w}.{name}: FICTIONAL data only in Level C materials')
            if 'verification' in p and p['verification'] not in VERIFICATION:
                fails.append(f'{w}.{name}: verification {p["verification"]!r} not in {VERIFICATION}')
            if p.get('verification') in VERIFIED and not (p.get('verified') and p.get('condition') and p.get('verified_against')):
                fails.append(f'{w}.{name}: a {p["verification"]} number records `verified` (what, when), `verified_against` and `condition`')
            if p.get('verification') == 'SECONDARY_VERIFIED' and p.get('verified_against') == p.get('source'):
                fails.append(f'{w}.{name}: a secondary check is independent of the cited source (verified_against != source)')
            if p.get('verification') == 'PRIMARY_VERIFIED':
                fails += _primary_fails(f'{w}.{name}', name, p, R)
            if name in SERVICE_LIMITS and p.get('rating') not in RATINGS:
                fails.append(f'{w}.{name}: a service limit states rating in {sorted(RATINGS)}')
            if p.get('verified_against') and p['verified_against'] not in R:
                fails.append(f'{w}.{name}: unknown verified_against {p["verified_against"]}')
            if p.get('irradiation', 'UNIRRADIATED') not in IRRADIATION:
                fails.append(f'{w}.{name}: irradiation {p.get("irradiation")!r} not in {sorted(IRRADIATION)}')
            if p.get('applies', 'ALWAYS') not in APPLIES:
                fails.append(f'{w}.{name}: applies {p.get("applies")!r} not in {sorted(APPLIES)}')
            if m.get('anisotropic') and name in DIRECTIONAL and not p.get('direction'):
                fails.append(f'{w}.{name}: an anisotropic material names the direction of a directional property')
            if p.get('rating') == 'LIFETIME_RATED' and not (p.get('life') and p.get('verification') in VERIFIED):
                fails.append(f'{w}.{name}: LIFETIME_RATED needs the rated `life` and verified evidence')
        beh = m.get('behaviour', {})
        for k in BEHAVIOUR:
            if not beh.get(k):
                fails.append(f'{w}: behaviour {k} missing (write OPEN when unknown)')
        for ref in m.get('evidence_refs', []):
            if ref not in R:
                fails.append(f'{w}: unknown evidence ref {ref}')
        if not m.get('evidence_refs'):
            fails.append(f'{w}: no evidence_refs')
        # A melting/decomposition point is never a service rating.
        tm, ts = props.get('melting_point'), props.get('max_service_temperature')
        if tm and ts and bound(ts, upper=True) >= bound(tm):
            fails.append(f'{w}: max_service_temperature reaches the {tm["phase_change"]} point')
        tl = props.get('min_service_temperature')
        if tl and ts and bound(tl, upper=True) >= bound(ts):
            fails.append(f'{w}: min_service_temperature reaches max_service_temperature')
        if m.get('level') in ('B', 'C'):
            parent = m.get('parent')
            if parent not in M:
                fails.append(f'{w}: Level {m.get("level")} variant needs an existing parent')
            elif M[parent].get('level') != 'A':
                fails.append(f'{w}: parent {parent} must be Level A')
            for k in ('improvement', 'mechanism', 'modified_properties', 'validation_required', 'manufacturing', 'tradeoffs', 'applicability'):
                if not m.get(k):
                    fails.append(f'{w}: variant needs {k}')
            for k in m.get('inherits', []):
                if parent in M and k not in M[parent].get('properties', {}):
                    fails.append(f'{w}: inherits {k}, which the parent does not give')
                if k in props:
                    fails.append(f'{w}: {k} both inherited and given')
            if m.get('level') == 'C' and (not m.get('speculative_claims') or not m.get('conservation_check')):
                fails.append(f'{w}: Level C needs speculative_claims and conservation_check')
        elif 'parent' in m or m.get('inherits'):
            fails.append(f'{w}: only Level B/C variants have a parent')
        if sources is not None and m.get('canon_ref') and m['canon_ref'] not in sources:
            fails.append(f'{w}: canon_ref {m["canon_ref"]} not in the source map')
    for pid, p in P.items():
        w = f'purpose {pid}'
        for k in ('name', 'function', 'required_properties', 'environment', 'failure_mechanisms', 'candidates', 'selection_criteria', 'validation', 'systems', 'view_color'):
            if not p.get(k):
                fails.append(f'{w}: missing {k}')
        for name in p.get('required_properties', []):
            if name not in UNITS and name not in BEHAVIOUR and name != 'erosion':
                fails.append(f'{w}: unknown required property {name}')
        for mid in p.get('candidates', []):
            if mid not in M:
                fails.append(f'{w}: unknown candidate {mid}')
        if len(p.get('view_color', [])) != 3:
            fails.append(f'{w}: view_color needs linear RGB')
    for xid, x in X.items():
        w = f'appearance {xid}'
        if x.get('material') not in M:
            fails.append(f'{w}: unknown material {x.get("material")}')
        if x.get('basis') not in APPEARANCE_BASIS:
            fails.append(f'{w}: basis {x.get("basis")!r}')
        own = all(k in x for k in ('base_color', 'roughness', 'metallic'))
        if bool(x.get('family')) == own:
            fails.append(f'{w}: give either family or base_color/roughness/metallic')
        if x.get('family') and x.get('basis') != 'FAMILY':
            fails.append(f'{w}: a family appearance has basis FAMILY')
        if x.get('family') and families is not None and x['family'] not in families:
            fails.append(f'{w}: unknown exterior family {x["family"]}')
        if own and (len(x['base_color']) != 3 or not all(0 <= c <= 1 for c in [*x['base_color'], x['roughness'], x['metallic']])):
            fails.append(f'{w}: base_color/roughness/metallic out of [0, 1]')
        if x.get('emission'):
            fails.append(f'{w}: solid appearances carry no emission (hot glow stays with the look and display layers)')
    seen = {}
    for aid, a in A.items():
        w = f'application {aid}'
        if not aid.startswith('APP-'):
            fails.append(f'{w}: IDs start with APP-')
        for k in ('title', 'component_ids', 'purposes', 'layers', 'engineering_status', 'chain'):
            if not a.get(k):
                fails.append(f'{w}: missing {k}')
        if a.get('engineering_status') not in STATUSES:
            fails.append(f'{w}: engineering_status {a.get("engineering_status")!r}')
        for pid in a.get('purposes', []):
            if pid not in P:
                fails.append(f'{w}: unknown purpose {pid}')
        if sources is not None:
            for ref in [a.get('canon_ref'), *a.get('open_refs', [])]:
                if ref and ref not in sources:
                    fails.append(f'{w}: source ref {ref} not in the source map')
        roles = [l.get('role') for l in a.get('layers', [])]
        if len(set(roles)) != len(roles):
            fails.append(f'{w}: duplicate layer roles')
        for l in a.get('layers', []):
            lw = f'{w}.{l.get("role")}'
            if l.get('material') not in M:
                fails.append(f'{lw}: unknown material {l.get("material")}')
            for mid in l.get('alternatives', []):
                if mid not in M:
                    fails.append(f'{lw}: unknown alternative {mid}')
            if l.get('appearance') not in X:
                fails.append(f'{lw}: unknown appearance {l.get("appearance")}')
            if l.get('selection') not in SELECTION:
                fails.append(f'{lw}: selection {l.get("selection")!r} (canon selections live in the Drive workbooks)')
            if l.get('geometry') not in GEOMETRY:
                fails.append(f'{lw}: geometry {l.get("geometry")!r}')
            for pid in l.get('purposes', []):
                if pid not in a.get('purposes', []):
                    fails.append(f'{lw}: purpose {pid} not among the application purposes')
            if l.get('material') in M and M[l['material']].get('level') == 'C' and l.get('selection') != 'CANDIDATE':
                fails.append(f'{lw}: a Level C material is at most a CANDIDATE alternative')
        for b in a.get('bindings', []):
            if b.get('layer') not in roles:
                fails.append(f'{w}: binding to unknown layer {b.get("layer")}')
            k = (b.get('asset'), b.get('material'))
            if k in seen:
                fails.append(f'{w}: {k[0]} WF_MAT_{k[1]} already carries {seen[k]}')
            seen[k] = f'{aid}.{b.get("layer")}'
    return fails


# --- lookups -------------------------------------------------------------------------------------------------------------------------------

def get_material(material_id, db=None):
    db = db or load()
    if material_id not in db['materials']:
        raise KeyError(f'unknown material {material_id}')
    return db['materials'][material_id]


def get_purpose(purpose_id, db=None):
    return (db or load())['purposes'][purpose_id]


def get_application(application_id, db=None):
    return (db or load())['applications'][application_id]


def get_appearance(appearance_id, db=None):
    return (db or load())['appearances'][appearance_id]


def candidates_for(purpose_id, db=None):
    """The purpose's candidate materials and every material an application layer of that purpose names (sorted IDs)."""
    db = db or load(); out = set(db['purposes'][purpose_id]['candidates'])
    for a in db['applications'].values():
        for l in a['layers']:
            if purpose_id in l.get('purposes', []):
                out.update([l['material'], *l.get('alternatives', [])])
    return sorted(out)


def applications_for(material_id, db=None):
    """[(application ID, layer role, 'primary'|'alternative')] that name a material."""
    db = db or load(); out = []
    for aid, a in sorted(db['applications'].items()):
        for l in a['layers']:
            if l['material'] == material_id:
                out.append((aid, l['role'], 'primary'))
            elif material_id in l.get('alternatives', []):
                out.append((aid, l['role'], 'alternative'))
    return out


def layer(application, role):
    return next(l for l in application['layers'] if l['role'] == role)


def bound_assets(db=None):
    db = db or load()
    return sorted({b['asset'] for a in db['applications'].values() for b in a.get('bindings', [])})


def asset_bindings(asset, db=None):
    """{display material name (without WF_MAT_): binding} for one asset. A binding carries the application, the layer and the IDs a
    Blender object or material needs (common.bind_materials)."""
    db = db or load(); out = {}
    for aid, a in sorted(db['applications'].items()):
        for b in a.get('bindings', []):
            if b['asset'] == asset:
                out[b['material']] = layer_binding(aid, b['layer'], db)
    return out


def layer_binding(application_id, role, db=None):
    """The IDs and status of one application layer, as a Blender object or material carries them."""
    db = db or load(); a = db['applications'][application_id]; l = layer(a, role); m = db['materials'][l['material']]
    return dict(application_id=application_id, layer=l['role'], material_id=l['material'], purpose_ids=list(l['purposes']),
                application_purpose_ids=list(a['purposes']), variant_id=l['material'] if m['level'] != 'A' else '',
                parent_id=m.get('parent', ''), level=m['level'], appearance_id=l['appearance'], selection=l['selection'],
                geometry=l['geometry'], engineering_status=f"{a['engineering_status']} / {l['selection']}",
                evidence_ref=','.join(m.get('evidence_refs', [])), canon_ref=a.get('canon_ref', ''), open_refs=','.join(a.get('open_refs', [])),
                stack=' > '.join(f"{x['role']}:{x['material']}" + ('' if x['geometry'] == 'DRAWN' else f"[{x['geometry']}]") for x in a['layers']),
                verification=' '.join(f'{k}={v}' for k, v in evidence_counts({'materials': {l['material']: m}, 'references': db['references']}).items() if v)
                or 'NO_NUMBERS')


def _closure(db, asset):
    """Every record an asset's bindings depend on, keyed (kind, id)."""
    out = {}
    for aid, a in db['applications'].items():
        if not any(b['asset'] == asset for b in a.get('bindings', [])):
            continue
        out[('application', aid)] = a
        for l in a['layers']:
            for mid in [l['material'], *l.get('alternatives', [])]:
                m = db['materials'][mid]; out[('material', mid)] = m
                if m.get('parent'):
                    out[('material', m['parent'])] = db['materials'][m['parent']]
            out[('appearance', l['appearance'])] = db['appearances'][l['appearance']]
        for pid in a['purposes']:
            out[('purpose', pid)] = db['purposes'][pid]
    for (kind, _), r in list(out.items()):
        if kind == 'material':
            for ref in {*r.get('evidence_refs', []), *(p.get('source') for p in r.get('properties', {}).values())}:
                out[('reference', ref)] = db['references'][ref]
    return out


def asset_hash(asset, db=None):
    """sha256 of the records an asset's bindings use (stable JSON): a material edit stales only the assets whose bound records changed."""
    db = db or load()
    blob = json.dumps({f'{k}:{i}': r for (k, i), r in sorted(_closure(db, asset).items())}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def affected_assets(old_texts, new_texts):
    """Assets whose bound records differ between two catalogue states ({file stem: text}); None when either cannot be parsed."""
    try:
        old, new = parse(old_texts), parse(new_texts)
    except tomllib.TOMLDecodeError:
        return None
    out = set()
    for asset in set(bound_assets(old)) | set(bound_assets(new)):
        try:
            if asset_hash(asset, old) != asset_hash(asset, new):
                out.add(asset)
        except KeyError:
            out.add(asset)
    return sorted(out)


def appearance_finish(appearance_id, s, db=None):
    """(linear RGB, roughness, metallic, surface) of an appearance, resolving a family through the exterior families (production_detail)."""
    db = db or load(); x = db['appearances'][appearance_id]
    if x.get('family'):
        import production_detail
        r, g, b, rough, metal = production_detail.material_value(s, x['family'])[:5]
        return (r, g, b), rough, metal, x.get('surface', 'none')
    return tuple(x['base_color']), x['roughness'], x['metallic'], x.get('surface', 'none')


def summary(db=None):
    db = db or load()
    lv = {}
    for m in db['materials'].values():
        lv[m['level']] = lv.get(m['level'], 0)+1
    return dict(materials=len(db['materials']), levels=lv, purposes=len(db['purposes']), applications=len(db['applications']),
                appearances=len(db['appearances']), references=len(db['references']), bound_assets=bound_assets(db))


if __name__ == '__main__':
    print(json.dumps(summary(), indent=1))
