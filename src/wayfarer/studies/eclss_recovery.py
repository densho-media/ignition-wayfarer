"""ECLSS-REC-2026-10-10 (S&E 15!A124, 09 OD-033, 98!A90; 12A SP-15/16/19/48): map the pressure compartments, their closures and the paths
by which a depressurized sector is isolated, verified and repressurized without entering its own 0.60 m shirt-sleeve-only strips.

The owner asks Claude to map valves, pressure paths and failure modes and to record any function that relies on entering a decompressed
strip; gas inventory, flow, tank size and repressurization time stay with Sheets (15!G124, I124). Everything here is read from the built
PROTOTYPE geometry (pressure_volumes, crew_transfer, human_entry, storeroom, service_strips): compartments with their gross and net free
volume, each closure between two compartments with the side whose pressure seats it and the load its latches carry against the other side.
The valves and gas stores in PROPOSED are a NONCANON study layout, not model geometry. Pure standard library.

    python3 src/wayfarer/studies/eclss_recovery.py [--svg <path>]
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies')]
from spec import load
import crew_transfer
import human_entry
import pressure_volumes
import service_strips
import storeroom


def compartments(s):
    """{compartment: dict(gross_m3, net_m3, zone, category)} from pressure_volumes, the small passages merged into the room they open from:
    the spine ports into their vestibule, the dock necks into the entry chamber, the connector into the trunk node, the refuge and store
    ports into the trunk (none of them has a closure of its own in the model)."""
    rooms = pressure_volumes.rooms(s); merge = {}
    for name in rooms:
        if name.startswith('Crew_Port_'):
            merge[name] = f'Crew_Vestibule_{name.split("_")[2]}'
        elif name in ('Dock_Primary', 'Dock_Primary_Inboard_Neck'):
            merge[name] = 'Dock_Primary_Entry_Chamber' if name == 'Dock_Primary' else 'Dock_Primary_Trunk_Node'
        elif name in ('Crew_Connector_Dock_Primary',):
            merge[name] = 'Dock_Primary_Trunk_Node'
        elif name in ('Crew_Refuge_Port', 'Crew_Store_Port'):
            merge[name] = 'Crew_Trunk'
    out = {}
    for name, r in rooms.items():
        k = merge.get(name, name); o = out.setdefault(k, dict(gross_m3=0.0, net_m3=None, zone=r['zone'], category=r['category']))
        o['gross_m3'] += r['gross_m3']
        if k == name:
            o.update(net_m3=r['net_m3'], zone=r['zone'], category=r['category'])
    return {k: {**v, 'gross_m3': round(v['gross_m3'], 1), 'net_m3': None if v['net_m3'] is None else round(v['net_m3'], 1)} for k, v in out.items()}


def closures(s):
    """Every modelled closure between two compartments: (a, b), the compartment whose pressure presses the leaf onto its seat ('seats_from',
    None where the model leaves the closure or its seat side OPEN), the leaf radius and the load its latches must hold when only the other
    side is pressurized (cabin pressure x leaf area). Sources: [human_entry] (entry and sector hatches, storeroom), crew_transfer.transfer_stack
    (drum doors outside the drum wall and tube hatches on the ring face, both seated from the tube side), the stationary gate (seat side not
    modelled) and the refuge port (no closure modelled, OPEN: OD-011, Q46(d))."""
    p = s['habitat']['atmosphere']['cabin_pressure_kpa']*1e3; h = s['human_entry']; lap = s['crew_transfer']['transfer_closure_lap_m']
    load = lambda r: None if r is None else round(p*math.pi*r*r/1e3, 1)
    out = []
    def add(name, a, b, seats_from, r, source):
        out.append(dict(name=name, a=a, b=b, seats_from=seats_from, leaf_r_m=None if r is None else round(r, 3), unseating_load_kN=load(r), source=source))
    dock = s['prototype']['dock_clear_radius_m']+h['hatch_leaf_overlap_m']
    add('Dock outer hatch', 'OUTSIDE', 'Dock_Primary_Entry_Chamber', 'Dock_Primary_Entry_Chamber', dock, '[human_entry] both dock hatches seat from the ship side')
    add('Dock inner hatch', 'Dock_Primary_Entry_Chamber', 'Dock_Primary_Trunk_Node', 'Dock_Primary_Trunk_Node', dock, '[human_entry] both dock hatches seat from the ship side')
    add('Storeroom hatch', 'Crew_Trunk', 'Storeroom_Shell', 'Storeroom_Shell', storeroom.port(s)['clear']+h['hatch_leaf_overlap_m'], 'SP-45 leaf on the room side (storeroom)')
    add('Refuge port closure', 'Crew_Trunk', 'Refuge_Storm_Shelter', None, None, 'not modelled: refuge hatch and second egress OPEN (OD-011, Q46(d))')
    L = human_entry.landing(s)
    for j in h['vestibule_rotors']:
        v = crew_transfer.vestibule(s, j); neck = crew_transfer.tube_neck(s, j); rc = (neck or {}).get('clear', crew_transfer.tube_radii(s, j)[1])
        tag = 'AB'[j-1]
        add(f'Spine port gate {tag}', 'Crew_Trunk', f'Crew_Vestibule_{j}', None, v['port_clear']+lap, 'stationary gate slides forward in the spine shell; seat side not modelled (MEC-019 hatch_actuation OPEN)')
        for k, _ in crew_transfer.sectors(s):
            add(f'Drum door {tag}{k}', f'Crew_Vestibule_{j}', f'Crew_Tube_{j}_{k}', f'Crew_Tube_{j}_{k}', rc+lap, 'crew_transfer.transfer_stack: door slides round the outside of the drum wall')
            add(f'Tube hatch {tag}{k}', f'Crew_Vestibule_{j}', f'Crew_Tube_{j}_{k}', f'Crew_Tube_{j}_{k}', rc+lap, 'crew_transfer.transfer_stack: hatch on the ring-side face, tube side')
            add(f'Sector hatch {tag}{k}', f'Crew_Tube_{j}_{k}', f'Sector_{j}_{k}', f'Sector_{j}_{k}', L['leaf_r'], '[human_entry] landing leaf seats from the sector side')
    return out


def neighbours(cl, room):
    return [(c, c['b'] if c['a'] == room else c['a']) for c in cl if room in (c['a'], c['b'])]


def isolation(cl, rooms):
    """Per compartment that loses pressure: each closure that must hold the healthy neighbour against it, and whether the neighbour's
    pressure seats it (assisted) or only its latches hold (latch_only), with the load; OPEN where the seat side is not modelled."""
    out = {}
    for room in rooms:
        rows = []
        for c, other in neighbours(cl, room):
            if other == 'OUTSIDE':
                continue
            state = 'OPEN' if c['seats_from'] is None else 'assisted' if c['seats_from'] == other else 'latch_only'
            rows.append(dict(closure=c['name'], holds=other, state=state, load_kN=c['unseating_load_kN'] if state == 'latch_only' else None))
        out[room] = rows
    return out


# NONCANON study layout (15!G124: map valves, pressure paths, failure modes). Nothing here is model geometry or a sized component.
PROPOSED = {
    'sensors': 'Total pressure, ppO2, ppCO2, smoke and a leak-rate (pressure-decay) reading in every compartment, read out remotely and on '
               'the panel on the healthy side of each closure (the tube-side hatch panel above every sector hatch exists in the model).',
    'sector_injection': 'One remotely operated, manually overridable injection/equalization valve per sector hatch, on the tube side (the '
                        'existing tube-side hatch panel and chase), fed by a make-up gas line in the tube: the sector is repressurized '
                        'from outside, never through its own ECLSS bay.',
    'sector_relief': 'A sector relief/vent valve to space with a remote and a tube-side manual control, for overpressure and for venting a '
                     'contaminated sector before refill.',
    'eclss_isolation': 'Remote isolation valves on each sector ECLSS loop where it crosses the sector boundary (12A I18/I19), so a failed '
                       'bay is bypassed, not repaired, until its sector is back at pressure.',
    'duct_dampers': 'Ventilation and any utility line crossing a sector, tube or vestibule boundary gets a remotely closed damper or valve '
                    'on both sides of the closure (duct routing is not modelled).',
    'gas_sources': {
        'R1 ring-local store': 'Protected O2/N2 (or approved mixture) per ring in the rotating structure, piped to that ring\'s three tube lines: '
                               'serves a sector while the ring spins, no rotary fluid coupling (MEC-019: only essential rotary fluid interfaces).',
        'R2 drum batch transfer': 'Stationary or other-ring gas passed through the despun vestibule: pressurize the drum, synchronize, open '
                                  'to the tube line; no rotary gas union, slow, and it needs the drum cycle (MEC-019 synchronization OPEN).',
        'R3 rotary gas union': 'A continuous stationary-to-ring gas coupling at the drum bearing: a new essential rotary fluid interface; '
                               'seal and bearing OPEN (OD-002).',
        'R4 stop and index': 'Stop and index the ring, open the stationary gate, drum door and tube hatch and feed from the stationary side; '
                             'the ring\'s gravity is lost meanwhile.',
    },
}


def strips(s):
    """service_strips.inventory with, per strip, whether recovery of its own sector needs anyone inside it (with the PROPOSED layout)."""
    need = {'LIFE_SUPPORT_GARDEN_COMMON': 'No, if the ECLSS loop has remote isolation and the sector is refilled through its hatch valve; the bay '
                                          'stays failed until the sector is back at pressure.',
            'WORK_MEDICAL_OPS': 'No: the other ring\'s operations row and the couch armrest consoles take over.',
            'HABITATION': 'No.'}
    return [dict(**q, recovery_needs_entry=need[q['function']] if not q['strip'].startswith('Burn_Couch') else
                 'Couch strips: a normal burn needs every crew member in a pressurized station before ignition (15!C124); a suited '
                 'occupant in a 0.45 m strip is a separate emergency contingency (15!H124), not covered here.') for q in service_strips.inventory(s)]


def report(s):
    rooms = compartments(s); cl = closures(s)
    return dict(contract='ECLSS-REC-2026-10-10', status='NONCANON STUDY (map only; sizing and timing are Sheets)',
                cabin_pressure_kpa=s['habitat']['atmosphere']['cabin_pressure_kpa'], compartments=rooms, closures=cl,
                isolation=isolation(cl, rooms), proposed=PROPOSED, strips=strips(s))


def svg(r):
    """A schematic of the compartments and closures: each closure carries an arrow pointing at the compartment it holds pressure in."""
    W, H = 1180, 680; out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
                             '<rect width="100%" height="100%" fill="#ffffff"/>',
                             '<text x="20" y="24" font-size="15" font-weight="bold">ECLSS-REC-2026-10-10: pressure compartments and closures (NONCANON study map)</text>',
                             '<text x="20" y="42" fill="#555">Closures: green = a loss further from the trunk is held by pressure; orange = only latches hold it; grey = closure or seat side OPEN. Volumes: gross / net m3.</text>']
    rooms = r['compartments']; pos = {}
    def box(name, x, y, label, w=150, h=44, fill='#eef2f7'):
        pos[name] = (x, y, w, h); g = rooms.get(name, {})
        vol = f"{g.get('gross_m3', '')} / {g.get('net_m3') if g.get('net_m3') is not None else '-'}" if g else ''
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#334"/>')
        out.append(f'<text x="{x+w/2}" y="{y+18}" text-anchor="middle" font-weight="bold">{label}</text>')
        out.append(f'<text x="{x+w/2}" y="{y+34}" text-anchor="middle" fill="#444">{vol}</text>')
    box('OUTSIDE', 20, 300, 'Docked vehicle / space', fill='#f4f4f4')
    box('Dock_Primary_Entry_Chamber', 200, 300, 'Entry chamber')
    box('Dock_Primary_Trunk_Node', 380, 300, 'Trunk node')
    box('Crew_Trunk', 560, 300, 'Trunk (17 m)')
    box('Storeroom_Shell', 560, 400, 'Storeroom SP-45')
    box('Refuge_Storm_Shelter', 560, 200, 'Storm refuge')
    for j, y0 in ((1, 70), (2, 470)):
        tag = 'AB'[j-1]
        box(f'Crew_Vestibule_{j}', 760, y0+70, f'Vestibule {tag} (despun)', fill='#f7f1e6')
        for k in (1, 2, 3):
            box(f'Crew_Tube_{j}_{k}', 940, y0+(k-1)*55, f'Tube {tag}{k}', w=100, h=44, fill='#eaf5ea')
            box(f'Sector_{j}_{k}', 1060, y0+(k-1)*55, f'Sector {tag}{k}', w=110, h=44, fill='#eaf5ea')
    depth = lambda n: 3 if n in ('OUTSIDE',) or n.startswith('Sector') else 2 if n.startswith(('Crew_Tube', 'Dock_Primary_Entry')) else 0 if n == 'Crew_Trunk' else 1
    seen = {}
    for c in r['closures']:
        a, b = sorted((c['a'], c['b']), key=lambda n: (depth(n) if n != 'OUTSIDE' else 4))   # a: nearer the trunk
        if c['a'] == 'OUTSIDE':
            a, b = c['b'], c['a']
        n = seen.get((a, b), 0); seen[(a, b)] = n+1
        ax, ay, aw, ah = pos[a]; bx, by, bw, bh = pos[b]
        if abs(bx-ax) > 1:
            (x1, y1), (x2, y2) = ((ax+aw, ay+ah/2), (bx, by+bh/2)) if bx > ax else ((ax, ay+ah/2), (bx+bw, by+bh/2))
        else:
            (x1, y1), (x2, y2) = ((ax+aw/2, ay), (bx+bw/2, by+bh)) if by < ay else ((ax+aw/2, ay+ah), (bx+bw/2, by))
        off = 4*n if a.startswith('Crew_Vestibule') else 0
        # green: the side nearer the trunk seats it, so a loss further out is held by pressure; orange: only latches hold it then
        col = '#888' if c['seats_from'] is None else '#2a8a3a' if c['seats_from'] == a else '#e07a10'
        out.append(f'<line x1="{x1}" y1="{y1+off}" x2="{x2}" y2="{y2+off}" stroke="{col}" stroke-width="3"/>')
        if a.startswith('Crew_Tube'):
            out.append(f'<text x="{(x1+x2)/2}" y="{(y1+y2)/2-6}" text-anchor="middle" font-size="10" fill="{col}">{c["unseating_load_kN"]:.0f} kN</text>')
    out.append('<text x="20" y="646" fill="#555">Sector hatches seat from the sector side; drum doors and tube hatches from the tube side. A sector or tube that loses pressure is therefore isolated by latches alone</text>')
    out.append('<text x="20" y="662" fill="#555">(sector hatch ~182 kN at 80 kPa), while a loss on the hub side is held by pressure. Refuge port closure and the spine gates\' seat side are OPEN.</text>')
    out.append('</svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--svg', type=Path); a = p.parse_args()
    r = report(load(ROOT)[0])
    if a.svg:
        a.svg.write_text(svg(r))
    print(json.dumps(r, indent=1))
