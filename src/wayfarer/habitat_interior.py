"""Rough PROTOTYPE ring-sector interiors (P1-004, FGR-003): the deck section and zone blocks in the sector frame.

Sector frame (WF_RING_SECTOR): origin on the sector centreline at the deck (ring radius habitat.floor_radius), +X along the ring
axis (the aft bulkhead is at -X), +Y radially outward (the floor in coast; no room turns), -Y toward the spin axis, +Z tangential.
Heights are measured up from the deck, so a zone's top has the smaller Y. The side walls are the two radial planes at +-arc/2, so the
half-width at height y is (deck radius + y) * tan(arc/2) minus the wall allowance. Owner data fixes the 40 m3 usable per sector, the three
mirrored functions and the Garden (habitat.layout, WORKING); rooms stay OPEN (habitat.layout.rooms), and the 12 bunks and 12 aft
couches are PROTOTYPE blocking. Shared by spec, the interior recipe, inspect and the tests, so standard library only.
"""
from pathlib import Path
import argparse
import json
import math
import habitat_ring


def tan_half(s):
    return math.tan(habitat_ring.sector_arc(s)/2)


def wall_half_width(s, y):
    """Half-width of the pressurized sector at height y (before the wall allowance)."""
    return (habitat_ring.floor(s)+y)*tan_half(s)


def section(s):
    """Deck at y = 0; the overhead panel hangs under the pressure skin (HUM-001 zone 5), so its underside sits at the sector inner radius
    plus the skin and the panel thickness."""
    h, r = s['habitat'], s['habitat_ring']
    deck = 0.0
    ceiling = r['sector_inner_radius_m']-habitat_ring.floor(s)+r['sector_skin_m']+s['interior']['deck_thickness_m']
    wall = s['interior']['wall_allowance_m']
    return {'radius_m': habitat_ring.floor(s), 'length_m': r['sector_axial_m'], 'deck_y_m': deck, 'ceiling_y_m': ceiling, 'headroom_m': deck-ceiling,
            'arc_deg': math.degrees(habitat_ring.sector_arc(s)), 'deck_width_m': 2*(wall_half_width(s, deck)-wall), 'overhead_width_m': 2*(wall_half_width(s, ceiling)-wall),
            'half_width_deck_m': wall_half_width(s, deck)-wall, 'half_width_ceiling_m': wall_half_width(s, ceiling)-wall,
            'deck_to_overhead_m3': habitat_ring.deck_to_overhead_m3(s), 'usable_m3': h['layout']['usable_per_ring_m3']/r['sectors_per_ring'],
            'target_usable_m3': h['layout']['usable_per_ring_m3']/r['sectors_per_ring'],
            'subfloor_m3': habitat_ring.sector_gross_m3(s)-habitat_ring.deck_to_overhead_m3(s)}


def zones(s, function):
    """Zone blocks on either side of the clear centre aisle, each as an axis-aligned box in the sector frame. A block spans from the aisle to
    the wall unless it gives `z` = [inner] or [inner, outer], its distances from the centreline (outer stops at the wall); `open` names a
    berth's open face (aisle, fore or aft; IND-001 sector_whitebox)."""
    i, sec = s['interior'], section(s)
    wall = i['wall_allowance_m']
    out = []
    for z in i['layouts'][function]:
        bottom = sec['deck_y_m']-z['lift_m']; top = bottom-z['height_m']
        outer = min(wall_half_width(s, bottom), wall_half_width(s, top))-wall
        inner = i['aisle_m']/2
        if 'z' in z:
            inner, outer = z['z'][0], min([outer, *z['z'][1:]])
        lo, hi = sorted((z['side']*inner, z['side']*outer))
        out.append({'name': z['name'], 'zone': z['zone'], 'function': function, 'side': z['side'], 'open': z.get('open', 'aisle'),
                    'min': (z['x'][0], top, lo), 'max': (z['x'][1], bottom, hi), 'depth_m': outer-inner})
    return out


def plates(s):
    """Deck plate (top surface on the deck) and overhead panel (underside on the overhead), spanning the skin's inner faces wall to wall."""
    i, sec, m = s['interior'], section(s), s['habitat_ring']['sector_skin_m']
    t, x = i['deck_thickness_m'], sec['length_m']/2-m
    deck, ceiling = sec['deck_y_m'], sec['ceiling_y_m']
    dz = wall_half_width(s, deck)-m
    cz = wall_half_width(s, ceiling-t)-m
    return [{'name': 'Interior_Deck', 'zone': 'deck', 'min': (-x, deck, -dz), 'max': (x, deck+t, dz)},
            {'name': 'Interior_Overhead', 'zone': 'overhead', 'min': (-x, ceiling-t, -cz), 'max': (x, ceiling, cz)}]


def hatch(s):
    """Overhead hatch on the overhead panel, directly below where the crew tube meets the pressure wall: on the ring plane, beside the crew
    spoke (HUM-001 zone 4), above the landing well on side -1 (zone 5, human_entry.landing)."""
    c = s['crew_transfer']
    return (c['overhead_hatch_x_m'], section(s)['ceiling_y_m'], c['overhead_hatch_z_m'])


def hatch_opening(s):
    """HUM-001 zone 5: centre (x, z) and radius of the overhead panel's opening, flush with the hatch frame around the 1.6 m clear passage."""
    c = s['crew_transfer']
    return c['overhead_hatch_x_m'], c['overhead_hatch_z_m'], s['prototype']['dock_clear_radius_m']+s['human_entry']['hatch_frame_width_m']


def volume(block):
    return math.prod(b-a for a, b in zip(block['min'], block['max']))


def overlap(a, b):
    return all(a['min'][k] < b['max'][k]-1e-9 and b['min'][k] < a['max'][k]-1e-9 for k in range(3))


def count(s, zone):
    """Number of blocks of a zone type across every sector of every ring (one sector of each function per ring)."""
    return sum(sum(1 for b in zones(s, f) if b['zone'] == zone) for f in s['habitat']['layout']['functions'])*habitat_ring.ring_count(s)


def check(s, d=None):
    """Fit report: owner volume and allocation rules, headroom, walls, aisle, overlaps and occupancy. Nothing here is canon."""
    h, i = s['habitat'], s['interior']
    sec = section(s); failures = []
    fail = lambda ok, message: ok or failures.append(message)
    functions = h['layout']['functions']
    fail(set(i['components']) == set(functions) == set(i['layouts']), 'Interior components/layouts must cover every habitat function')
    fail(len(set(i['components'].values())) == len(functions), 'One interior component per function')
    fail(sec['deck_to_overhead_m3'] >= sec['usable_m3'], f'Deck-to-overhead {sec["deck_to_overhead_m3"]:.3f} m3 cannot hold the {sec["usable_m3"]:.0f} m3 usable allocation')
    fail(sec['headroom_m'] >= i['min_headroom_m'], f'Headroom {sec["headroom_m"]:.3f} m below {i["min_headroom_m"]} m')
    fail(sec['deck_width_m'] >= i['aisle_m']+2*i['min_zone_depth_m'], 'Deck too narrow for the aisle and two zone rows')
    x_limit = sec['length_m']/2-i['end_allowance_m']
    per_function = {}
    for function in i['layouts']:
        blocks = zones(s, function)
        names = [b['name'] for b in blocks]
        fail(len(names) == len(set(names)), f'{function}: duplicate zone names')
        for b in blocks:
            fail(b['side'] in (-1, 1), f'{b["name"]}: side must be +1 or -1')
            fail(-x_limit-1e-9 <= b['min'][0] < b['max'][0] <= x_limit+1e-9, f'{b["name"]}: outside the sector length')
            fail(b['max'][1] <= sec['deck_y_m']+1e-9 and b['min'][1] >= sec['ceiling_y_m']-1e-9, f'{b["name"]}: outside deck-to-overhead')
            fail(b['depth_m'] >= i['min_zone_depth_m']-1e-9, f'{b["name"]}: too shallow against the wall')
            if b['zone'] == 'burn_couch':
                # Aft-facing burn couches stand against the aft bulkhead so the burn presses the occupant into them (08!A55, 15!I1).
                fail(math.isclose(b['min'][0], -x_limit, abs_tol=1e-9), f'{b["name"]}: burn couch must sit against the aft bulkhead (x0 = {-x_limit:g})')
        fail(not [(a['name'], b['name']) for n, a in enumerate(blocks) for b in blocks[n+1:] if overlap(a, b)], f'{function}: zones overlap')
        occupied = sum(volume(b) for b in blocks)
        per_function[function] = {'component': 'WF_'+i['components'][function], 'sectors': habitat_ring.ring_count(s), 'zones': len(blocks),
                                  'zone_volume_m3': occupied, 'free_volume_m3': sec['usable_m3']-occupied,
                                  'by_zone_m3': {z: sum(volume(b) for b in blocks if b['zone'] == z) for z in sorted({b['zone'] for b in blocks})}}
    rated = s['crew']['rated_occupancy']['value']
    bunks, couches = count(s, 'bunk'), count(s, 'burn_couch')
    fail(bunks >= rated, f'{bunks} bunks for a rated occupancy of {rated}')
    fail(couches >= rated, f'{couches} burn couches for a rated occupancy of {rated}')
    garden = [f for f in i['layouts'] if any(b['zone'] == 'garden' for b in zones(s, f))]
    fail(all('GARDEN' in f for f in garden), 'Garden zones only in the life-support/Garden sectors')
    garden_sectors = len(garden)*habitat_ring.ring_count(s)
    fail(h['layout']['garden_m3'] <= garden_sectors*sec['usable_m3'], 'Garden exceeds the usable allocation of its sectors')
    report = {'status': 'PROTOTYPE_LAYOUT_NOT_CANON', 'pass': not failures, 'failures': failures, 'section': sec,
              'aisle_m': i['aisle_m'], 'bunks': bunks, 'burn_couches': couches, 'rated_occupancy': rated, 'story_manifest': s['crew']['count'],
              'garden_sectors': garden_sectors,
              'garden_zone_volume_m3': sum(sum(volume(b) for b in zones(s, f) if b['zone'] == 'garden') for f in garden)*habitat_ring.ring_count(s),
              'garden_allocation_m3': h['layout']['garden_m3'], 'functions': per_function}
    if d is not None:
        # Coast deck radius versus the owner's floor radius (08_ROTATING_HABITAT A8): the deck sits on it.
        deck_r = habitat_ring.floor(s)+sec['deck_y_m']; head = deck_r-s['prototype']['human_height_m']
        report['coast_gravity'] = {'owner_floor_radius_m': habitat_ring.floor(s), 'owner_floor_g': habitat_ring.floor_gravity_g(s),
                                   'deck_radius_m': deck_r, 'deck_g': habitat_ring.floor_gravity_g(s, deck_r), 'head_radius_m': head,
                                   'head_g': habitat_ring.floor_gravity_g(s, head)}
        report['burn_orientation'] = 'No room turn; with rings stopped and locked thrust acts along -X onto the aft-bulkhead couches (habitat.interior_orientation).'
    return report


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import ROOT, load, derived
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, default=ROOT/'references/p1_interior.json')
    a = p.parse_args()
    s, *_ = load(); r = check(s, derived(s))
    a.output.write_text(json.dumps(r, indent=2)+'\n'); print(json.dumps({k: r[k] for k in ['pass', 'bunks', 'burn_couches', 'garden_zone_volume_m3']}, indent=1), r['section'], r.get('coast_gravity'))
    if not r['pass']:
        raise SystemExit(1)
