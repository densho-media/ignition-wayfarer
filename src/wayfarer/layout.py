"""Axial datums for ship-frame X positions (FGR-004/005). Pure stdlib; no spec import at module level.

AFT = -L/2 and FWD = +L/2 follow ship.length. RADIATOR_AFT and RADIATOR_FRONT are DERIVED: the blade aft edge sits a PROTOTYPE gap
ahead of the thrust-ring forward face and the front follows from the blade length (thermal_geometry); neither is ever typed.
RING_A is DERIVED too (HAB-001): RADIATOR_FRONT plus ring_a_offset_m, so the ring/spar clearance of the owner (Q29) follows any blade growth. Every ship-frame X in the spec is {datum, offset_m}:
metres along +X from that datum's origin."""
import math

DATUMS = ('AFT', 'RADIATOR_AFT', 'RADIATOR_FRONT', 'RING_A', 'FWD')
FIXED = ('AFT', 'FWD')
DERIVED = ('RADIATOR_AFT', 'RADIATOR_FRONT', 'RING_A')
NAMED = ()
REF_KEYS = {'datum', 'offset_m'}


def _datums(s):
    return s.get('layout', {}).get('datums', {})


def ring_a_offset_m(s):
    """Offset of RING_A from RADIATOR_FRONT: leading spar radius + the owner's ring/spar service clearance (07!A47, 08!A59) + the ring half sweep,
    so the ring-A aft sweep face sits exactly `habitat.ring_service_clearance.min_m` from the front of the spar (HSFP class L for the 1.5 m)."""
    import habitat_ring                      # lazy: habitat_ring imports this module
    return s['prototype']['radiator_leading_spar_radius_m']+s['habitat']['ring_service_clearance']['min_m']+habitat_ring.sweep_half(s)


def origins(s):
    import thermal_geometry                  # lazy: thermal_geometry imports this module
    L = s['ship']['length']['value']
    out = {'AFT': -L/2, 'FWD': L/2}
    table = _datums(s)
    tr = s['prototype']['thrust_ring_x']
    if tr['datum'] not in FIXED:
        raise ValueError(f'prototype.thrust_ring_x must be anchored to {FIXED}, not {tr["datum"]!r}')
    ring_x = out[tr['datum']] + tr['offset_m']
    # Blade aft edge: the gap ahead of the thrust-ring forward face; the front follows from the equivalent blade length.
    out['RADIATOR_AFT'] = ring_x + s['structure']['ring_depth_m']/2 + table['radiator_aft_gap_m']
    out['RADIATOR_FRONT'] = thermal_geometry.blade_at(s, out['RADIATOR_AFT'])['front_x_m']
    out['RING_A'] = out['RADIATOR_FRONT']+ring_a_offset_m(s)
    for name in NAMED:                       # base must already be resolved, so cycles and forward references cannot occur
        entry = table[name]
        base = entry['datum']
        if base not in out:
            raise ValueError(f'layout datum {name}: base {base!r} unknown or not yet resolved')
        out[name] = out[base] + entry['offset_m']
    return out


def origin(s, datum):
    try:
        return origins(s)[datum]
    except KeyError:
        raise ValueError(f'unknown layout datum {datum!r}') from None


def x(s, datum, offset_m=0.0):
    return origin(s, datum) + offset_m


def is_ref(v):
    return isinstance(v, dict) and set(v) == REF_KEYS


def at(s, ref):
    if not is_ref(ref):
        raise ValueError(f'position must be exactly {{datum, offset_m}}: {ref!r}')
    off = ref['offset_m']
    if isinstance(off, bool) or not isinstance(off, (int, float)) or not math.isfinite(off):
        raise ValueError(f'offset_m must be a finite number: {ref!r}')
    return x(s, ref['datum'], off)


def ref(s, datum, x_m):
    """Inverse of `at`, for tests: the reference that resolves to ship X x_m."""
    return {'datum': datum, 'offset_m': x_m - origin(s, datum)}


def spine_core(s):
    """HUM-001 zone 2 (PROTOTYPE): the forward spine core that carries the crew trunk and the hub bearings, as (x_core, x_cone, r_core). From x_core
    to the spine's forward end the spine has spine_core_radius_m; aft of x_cone it keeps spine_radius_m down to the terminated drive hub; a cone of
    spine_core_transition_m joins them."""
    p = s['prototype']; x = at(s, p['spine_core_aft_x'])
    return x, x-p['spine_core_transition_m'], p['spine_core_radius_m']


def spine_radius_at(s, x):
    x_core, x_cone, r_core = spine_core(s); r = s['prototype']['spine_radius_m']
    return r_core if x >= x_core else r if x <= x_cone else r+(r_core-r)*(x-x_cone)/(x_core-x_cone)


def check(s):
    out = []
    table = _datums(s)
    if not table:
        return ['layout.datums missing']
    if table.get('status') != 'PROTOTYPE':
        out.append('layout.datums must stay PROTOTYPE')
    if table.get('unit') != 'm':
        out.append('layout.datums unit must be m')
    for name in FIXED:
        if name in table:
            out.append(f'layout datum {name} cannot be redefined')
    for name in DERIVED:
        if name in table:
            out.append(f'layout datum {name} is derived from the blade (layout.py) and cannot be typed')
    gap = table.get('radiator_aft_gap_m')
    if isinstance(gap, bool) or not isinstance(gap, (int, float)) or not math.isfinite(gap) or gap <= 0:
        out.append('layout.datums.radiator_aft_gap_m must be a finite positive number')
    tr = s.get('prototype', {}).get('thrust_ring_x')
    if not is_ref(tr) or tr['datum'] not in FIXED:
        out.append(f'prototype.thrust_ring_x must be {{datum, offset_m}} anchored to one of {FIXED}')
    resolved = set(FIXED) | set(DERIVED)
    for name in NAMED:
        entry = table.get(name)
        if not is_ref(entry):
            out.append(f'layout datum {name} must be {{datum, offset_m}}')
            continue
        if entry['datum'] not in DATUMS:
            out.append(f'layout datum {name}: unknown base {entry["datum"]!r}')
        elif entry['datum'] not in resolved:
            out.append(f'layout datum {name}: base {entry["datum"]} is a cycle or forward reference')
        off = entry['offset_m']
        if isinstance(off, bool) or not isinstance(off, (int, float)) or not math.isfinite(off):
            out.append(f'layout datum {name}: offset_m must be finite')
        resolved.add(name)
    for key in table:
        if key not in ('status', 'unit', 'rationale', 'radiator_aft_gap_m', *NAMED, *FIXED, *DERIVED):
            out.append(f'layout.datums: unexpected key {key!r}')
    if not out:
        try:
            o = origins(s)
        except (ValueError, KeyError, ZeroDivisionError) as e:
            return [f'layout datums cannot be resolved: {e}']
        order = ('AFT', 'RADIATOR_AFT', 'RADIATOR_FRONT', 'RING_A', 'FWD')
        if not all(o[a] < o[b] for a, b in zip(order, order[1:])):
            out.append('layout datum order must be AFT < RADIATOR_AFT < RADIATOR_FRONT < RING_A < FWD')
    return out
