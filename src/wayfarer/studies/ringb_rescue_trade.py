"""M3 (SIM-033, WF-012/017/024): ring B rescue architecture trade, L2 study. NONCANON DISPOSABLE STUDY; no geometry, closure, port, rail or
room is released. It compares three whole-route concepts for a ring B casualty from the measured segments (references/p1_access_seg_ringb.json,
references/p1_access_integrated.json) and the shared formulas:

  1. a dedicated rescue-capable transfer interface (a ring-A-class 1.6 m spine port on ring B);
  2. distributed in-sector care plus refuge in place (care at a sector care point, the casualty sheltered in the sector);
  3. rescue at a stopped, indexed ring B.

Run under Blender's Python (numpy, for the care screen of ringb_unified.distributed):
  /snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/ringb_rescue_trade.py
It writes references/p1_ringb_rescue_trade.json; the review is references/RINGB_RESCUE_TRADE_2026-10-12.md."""
from pathlib import Path
import contextlib
import io
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies')]
import crew_transfer
import habitat_interior
import habitat_ring
import rotor_interface
import ringb_unified
from spec import load

OUT = ROOT/'references/p1_ringb_rescue_trade.json'
CABIN_KPA = 80.0            # CALC-R02 diagnostic closure load: ideal clear area x 80 kPa, either way
GARDEN = 'LIFE_SUPPORT_GARDEN_COMMON'
GARDEN_SWAP = ('Garden_Rack_1', 'Mess')    # PROTOTYPE fit-out swap: these two blocks yield their deck to a fold-down care couch
SHELTER_M = (2.2, 1.5, 1.9)                # PROTOTYPE casualty + attendant storm shelter round the care couch (length, width, height)


def root_cause(s):
    """Why ring B's port is 0.9 m: crew_transfer.vestibule stops ring B's vestibule one mechanical clearance short of hub 1's forward
    cartridge withdrawal paths. A ring-A-class port (the 1.6 m docking passage) needs the vestibule further aft; the intrusion is measured."""
    c, p = s['crew_transfer'], s['prototype']; a, b = crew_transfer.vestibule(s, 1), crew_transfer.vestibule(s, 2)
    rot = {r['index']: r for r in rotor_interface.rotors(s)}
    u0 = b['cu1']-2*(p['dock_clear_radius_m']+c['passage_wall_m']+c['seal_allowance_m'])-c['vestibule_guard_m']
    ext = rotor_interface.withdrawal_extent(s, 1)
    return dict(ring_a_port_clear_m=2*a['port_clear'], ring_b_port_clear_m=2*b['port_clear'], ring_a_chamber_m=a['cu1']-a['cu0'],
                ring_b_chamber_m=b['cu1']-b['cu0'], ring_b_window_u_m=list(b['window']), hub1_withdrawal_x_m=list(ext),
                ring_b_x_m=rot[2]['x'], mechanical_clearance_m=p['mechanical_clearance_m'],
                ring_b_u0_for_1_6_m_port=u0, intrusion_m=b['window'][0]-u0,
                closure_load_kn={'ring_a_port': math.pi*a['port_clear']**2*CABIN_KPA, 'ring_b_port': math.pi*b['port_clear']**2*CABIN_KPA,
                                 'ring_b_at_1_6_m': math.pi*p['dock_clear_radius_m']**2*CABIN_KPA},
                basis='crew_transfer.vestibule (window from rotor_interface.withdrawal_extent of hub 1 plus mechanical_clearance_m)')


def momentum(s):
    """Stopping one ring leaves the other's angular momentum on the ship: compared with the allowed residual (habitat_ring.dynamics)."""
    d = habitat_ring.dynamics(s)
    return dict(each_n_m_s=d['angular_momentum_each_N_m_s'], allowed_residual_n_m_s=d['allowed_residual_momentum_N_m_s'],
                one_ring_stopped_ratio=d['angular_momentum_each_N_m_s']/d['allowed_residual_momentum_N_m_s'],
                spin_ramp_s=s['physics']['rotor_operations']['spin_up_time_s'],
                note='both rings stop together (DYN-026 sequence); the ship inertia is unknown (physics.mass_distribution), so a one-ring stop is not quantified')


def shielding(s):
    """Areal density of each ring's water share on two placements (both WORKING-region readings of 'distributed around both rigid ring frames'):
    on the three sector shells only, or round the whole frame annulus; against the storm refuge's 20 g/cm2. Plus the water of a casualty shelter
    at the refuge's areal density, if the sector shells carry less."""
    r = s['habitat_ring']; R0, R1, ax = r['sector_inner_radius_m'], r['sector_outer_radius_m'], r['sector_axial_m']
    n = r['sectors_per_ring']; arc = habitat_ring.sector_arc(s)
    water = habitat_ring.water_item(s)['rotating_allowance_kg']/habitat_ring.ring_count(s)
    shells = n*(arc*(R0+R1)*ax+arc*(R1*R1-R0*R0)+2*(R1-R0)*ax)
    frame = math.tau*(R0+R1)*ax+math.tau*(R1*R1-R0*R0)
    refuge = s['shielding']['refuge']['areal_density_g_cm2']; L, W, H = SHELTER_M; area = 2*(L*W+L*H+W*H)
    return dict(water_per_ring_kg=water, refuge_g_cm2=refuge,
                sector_shells={'area_m2': shells, 'g_cm2': water/shells/10.0},
                whole_frame={'area_m2': frame, 'g_cm2': water/frame/10.0},
                casualty_shelter={'size_m': list(SHELTER_M), 'area_m2': area, 'water_kg_at_refuge_density': area*refuge*10.0,
                                  'status': 'PROTOTYPE box round the care couch and one attendant; redistributed from the ring water, not added'},
                placement_status=next(i['position_status'] for i in s['physics']['mass_regions']['items'] if i['id'] == 'water_radiation_shielding'))


def care(s):
    """The care-point screen (ringb_unified.distributed) as built, and with GARDEN_SWAP taken out of the garden sectors' fit-out."""
    orig = habitat_interior.zones
    out = {}
    for name, drop in (('as_built', ()), ('garden_swap', GARDEN_SWAP)):
        habitat_interior.zones = lambda s_, fn, d=drop: [b for b in orig(s_, fn) if not (fn == GARDEN and b['name'] in d)]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                r = ringb_unified.distributed()
        finally:
            habitat_interior.zones = orig
        g = r['functions'][GARDEN]
        best = lambda fr: max([(v['clearance_m'], v['reachable_by_0_60_path'], 'new couch '+k) for k, v in fr['new_couch'].items() if v['clearance_m'] is not None]
                              + [(e['clearance_m'], e['reachable_by_0_60_path'], e['block']) for e in fr['existing']])
        out[name] = {fr: dict(zip(('clearance_m', 'reachable', 'care_point'), best(g[fr]))) for fr in ('deck', 'aft')}
    return out


def chains(d):
    """The composed architecture-A rows (p1_access_integrated.json): status and least clearance per state."""
    rows = {}
    for k, ch in d['architecture_A'].items():
        rows[k] = {'title': ch['title'], **{st: {'status': v['status'], 'least_m': min((e['worst']['least_m'] for e in v['elements'].values()
                                                                                          if e.get('worst') and e['worst'].get('least_m') is not None), default=None)}
                                           for st, v in ch['states'].items()}}
    return rows


def status(x, reachable=True):
    return 'FAIL' if x < 0.0 or not reachable else 'PASS' if x >= 0.05 else 'MARGINAL'


def coverage(integ, cr):
    """Care in every occupied sector-state (deck frame for 0 g / spin / stopped, aft frame locked at 1.5 g), as built and with the garden swap
    (the garden sectors' care point from care(); the other sectors keep ringb_unified's result)."""
    out = {}
    for name in ('as_built', 'garden_swap'):
        rows = {}
        for sec, v in integ['distributed_alternative']['by_sector'].items():
            fr = {k: (cr[name][k] if v['function'] == GARDEN else dict(clearance_m=v[k]['clearance_m'], reachable=v[k]['reachable_by_0_60_path']))
                  for k in ('deck', 'aft')}
            st = {s_: status(fr['deck']['clearance_m'], fr['deck']['reachable']) for s_ in ('0g', 'spin', 'stopped')}
            st['locked_1.5g'] = status(fr['aft']['clearance_m'], fr['aft']['reachable'])
            rows[sec] = dict(function=v['function'], **st)
        tally = {k: sum(r[s_] == k for r in rows.values() for s_ in ('0g', 'spin', 'stopped', 'locked_1.5g')) for k in ('PASS', 'MARGINAL', 'FAIL')}
        out[name] = dict(sectors=rows, tally=tally)
    return out


def trade(s):
    rc, mo, sh, cr = root_cause(s), momentum(s), shielding(s), care(s)
    integ = json.loads((ROOT/'references/p1_access_integrated.json').read_text()); ch = chains(integ)
    ring_a = ch['ringA']; cov = coverage(integ, cr)
    garden_ok = cr['garden_swap']['deck']['clearance_m'] >= 0.05 and cr['garden_swap']['deck']['reachable']
    concepts = {
        '1_dedicated_transfer': dict(
            what='a ring-A-class 1.6 m spine port and 1.9 m chamber on ring B; casualties ride ring A\'s measured chain',
            human_sweep={st: ring_a[st] for st in ('0g', 'spin', 'stopped', 'locked_1.5g')},
            human_sweep_note='ring A as built is the only measured 1.6 m chain (single-seed built_A, not the worst-case method): it FAILs while spinning, so concept 1 also needs concept 3\'s stop',
            refuge=f"through the trunk to the storm refuge (ring A's chain {ring_a['0g']['status']} in 0 g, {ring_a['stopped']['status']} stopped)",
            pressure=f"port closures {rc['closure_load_kn']['ring_b_at_1_6_m']:.0f} kN each way against {rc['closure_load_kn']['ring_b_port']:.0f} kN today (CALC-R02 diagnostic)",
            mass='a longer drum and larger closures (not estimated: no closure or drum mass is sourced)',
            ring_stop='needed for transport (ring A pattern: FAIL spinning)',
            reversibility=f"IRREVERSIBLE: the vestibule reaches {rc['intrusion_m']:.2f} m into hub 1's forward cartridge withdrawal path; hub 1's service "
                          'direction, ring B\'s station or in-situ cartridge service must change (rotor interface, owner architecture)',
            story='a hospital lock between the rings'),
        '2_distributed_care_refuge_in_place': dict(
            what='care at an in-sector care point (bunk, medical couch, aft burn couch; in the garden sectors a fold-down couch where '
                 + ' and '.join(GARDEN_SWAP) + ' stand); a casualty who cannot be moved shelters in the sector, the others go to the storm refuge',
            human_sweep={'care_tally_as_built': cov['as_built']['tally'], 'care_tally_garden_swap': cov['garden_swap']['tally'],
                         'garden_as_built': cr['as_built'], 'garden_swap': cr['garden_swap']},
            refuge=f"in place: {sh['sector_shells']['g_cm2']:.1f} g/cm2 if each ring's {sh['water_per_ring_kg']/1000:.0f} t of water sits on its three sector shells, "
                   f"{sh['whole_frame']['g_cm2']:.1f} g/cm2 if it is spread round the whole frame (storm refuge {sh['refuge_g_cm2']:.0f}); "
                   f"a casualty shelter at the refuge's density takes {sh['casualty_shelter']['water_kg_at_refuge_density']/1000:.1f} t, redistributed",
            pressure='no new closure; the sector hatch stays the boundary',
            mass='net zero if the shelter water is redistributed from the 160 t rotating allowance (placement WORKING)',
            ring_stop='none',
            reversibility='REVERSIBLE: furniture, a garden fit-out swap and water placement; no pressure boundary, port or rotor change',
            story='care comes to the casualty: the sector is where the crew lives and heals'),
        '3_stopped_indexed_ring_b': dict(
            what='stop both rings (one ring alone leaves its momentum on the ship), index ring B and carry the casualty through today\'s 0.9 m port',
            human_sweep={st: ch['ringB_to_refuge'][st] for st in ('0g', 'stopped', 'locked_1.5g')},
            human_sweep_note='stopping does not change the port: ring B stays FAIL (best G1 -0.135 m to the trunk)',
            refuge='the same failing transfer chain',
            pressure='no change',
            mass='no change',
            ring_stop=f"both rings, {mo['spin_ramp_s']:.0f} s down and up each (one ring stopped = {mo['one_ring_stopped_ratio']:.0f} x the allowed residual momentum); "
                      'the whole ship at 0 g; re-index at 1.5 g NOT ALLOWED (CALC-R05)',
            reversibility='an operating mode, not an architecture; it closes no geometry on ring B',
            story='the ship stops for one person'),
    }
    rec = dict(direction='2_distributed_care_refuge_in_place',
               why=['the only concept that passes care in every ring B sector-state with reversible changes'
                    + ('' if garden_ok else ' (garden care point NOT closed by the swap)'),
                    'concept 1 is irreversible (hub 1 service path) and still needs a stop; concept 3 closes no geometry'],
               owner_decision='Doc 2026-10-11T21:40 (a): adopt distributed care + refuge in place for ring B, and place each ring\'s water so a sector '
                              'shelter reaches the storm refuge\'s 20 g/cm2 (Sheets: water placement, P0 shield stack)',
               keeps='the care and refuge requirements; no hull cutout; ring A\'s chain unchanged')
    return dict(study='M3 ring B rescue architecture trade (SIM-033, WF-012/017/024)', status='NONCANON DISPOSABLE STUDY, L2; nothing released',
                inputs=['references/p1_access_seg_ringb.json', 'references/p1_access_integrated.json', 'crew_transfer.vestibule', 'rotor_interface',
                        'habitat_ring', 'ringb_unified.distributed'],
                root_cause=rc, momentum=mo, shielding=sh, care=cr, coverage=cov, chains=ch, concepts=concepts, recommendation=rec)


if __name__ == '__main__':
    r = trade(load(ROOT)[0])
    OUT.write_text(json.dumps(r, indent=1, default=float)+'\n')
    print('WF_RINGB_TRADE', json.dumps({'root_cause': {k: r['root_cause'][k] for k in ('ring_b_port_clear_m', 'intrusion_m')},
                                         'momentum_ratio': r['momentum']['one_ring_stopped_ratio'], 'g_cm2': [r['shielding']['sector_shells']['g_cm2'],
                                         r['shielding']['whole_frame']['g_cm2']], 'tally': [r['coverage'][k]['tally'] for k in ('as_built', 'garden_swap')], 'direction': r['recommendation']['direction']}, default=float))
