"""HR-001 / TODO E03: state machine, telemetry gate and fault demonstrations for the selected heat-recovery branch (NONCANON study).

Sources: S&E 15!A194 HR-002 (state labels, default BYPASS, no fabricated W/K/clock, import only approved time series), 40!A105 (COAST
bypass + cooldown circulation; LOW_THRUST / HIGH_POWER preheat only after validation; EVA propulsion OFF; HOT shutdown keeps cooling;
DAMAGED isolates the HX; timing OPEN), 40!A106 and Fiji 30!A17 (required faults; "preserve original cooling in safe fallback wherever
possible"; no closed-thermal safety GO until faults are bounded), Model Status HR-P07 / P13 (handoff). Topology and valve table:
hr001_packaging (MODES, candidate B).

PROTOTYPE choices (judgment, this file): each valve's unpowered position (branch valves fail closed, the built-line bypass fails open,
the hot isolation fails closed) so that loss of actuation power lands in BYPASS; the response of each fault; which sensor sees it. Every
trip limit, delay and duty stays OPEN, so a detection reads "sensor beyond its OPEN limit", never a number.

    python3 src/wayfarer/studies/hr001_states.py                          # state + fault report (JSON)
    /snap/bin/blender -b --python src/wayfarer/studies/hr001_states.py -- --out runs/<stamp>-hr001-states
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
import hr001_packaging as hp

VALVES = ('H2_In', 'H2_Out', 'H2_Bypass', 'Hot_Isolation')
FAIL_POSITION = dict(H2_In='C', H2_Out='C', H2_Bypass='O', Hot_Isolation='C')          # PROTOTYPE: unpowered = BYPASS
# 40!A105: ship configuration -> the HR state it may command now. Preheat needs validation that does not exist, so it is a labelled study
# state only; nothing in flight leaves BYPASS until the owner releases it.
CONFIG_STATE = {'DOCKED': 'BYPASS', 'COAST': 'BYPASS', 'EVA': 'BYPASS', 'LOW_THRUST': 'BYPASS', 'HIGH_POWER': 'BYPASS',
                'FIRST_IGNITION': 'BYPASS', 'HOT_SHUTDOWN': 'BYPASS', 'DAMAGED': 'HX_FAULT_ISOLATED'}
CONFIG_NOTE = {'COAST': 'bypass + cooldown circulation on the existing hot loop', 'EVA': 'propulsion OFF',
               'LOW_THRUST': 'preheat only after validation (OPEN): PREHEAT_STUDY is a labelled study state, not a flight command',
               'HIGH_POWER': 'preheat only after validation (OPEN): PREHEAT_STUDY is a labelled study state, not a flight command',
               'HOT_SHUTDOWN': 'existing radiator cooling continues; HR branch closed', 'DAMAGED': 'HX isolated'}
# Channels the HR display may show (HR-P08 / HR-P10). Units are the only fixed facts; every value needs an owner-approved sample.
CHANNELS = {'hot_source_power': 'W', 'hot_source_temperature': 'K', 'h2_mass_flow': 'kg/s', 'h2_inlet_pressure': 'Pa',
            'h2_inlet_temperature': 'K', 'h2_outlet_temperature': 'K', 'h2_enthalpy_rise': 'J/kg', 'hx_transfer': 'W',
            'hx_pressure_drop': 'Pa', 'brayton_electric_output': 'W', 'brayton_sink_heat': 'W', 'radiator_load': 'W'}


def telemetry(sample=None):
    """Display values for one time sample. Only a sample with approved=True, a source reference, a mission time and finite values in the
    expected unit is shown; everything else is UNKNOWN with its reason (HR-002: no fabricated W/K/clock; invalid input rejected)."""
    out = {}
    ok_sample = isinstance(sample, dict) and sample.get('approved') is True and sample.get('source_ref') and isinstance(sample.get('t_s'), (int, float))
    for ch, unit in CHANNELS.items():
        v = (sample or {}).get('values', {}).get(ch) if isinstance(sample, dict) else None
        if not ok_sample:
            out[ch] = dict(known=False, unit=unit, reason='NO_DATA: no owner-approved time sample (C-020)' if sample is None else 'REJECTED: sample not approved / no source / no mission time')
        elif not (isinstance(v, dict) and v.get('unit') == unit and isinstance(v.get('value'), (int, float)) and math.isfinite(v['value'])):
            out[ch] = dict(known=False, unit=unit, reason='OPEN: channel missing or invalid in the approved sample')
        elif unit in ('W', 'K', 'kg/s', 'Pa') and v['value'] < 0 and ch not in ('hx_pressure_drop',):
            out[ch] = dict(known=False, unit=unit, reason='REJECTED: negative value for a non-negative quantity')
        else:
            out[ch] = dict(known=True, unit=unit, value=v['value'], source_ref=sample['source_ref'], t_s=sample['t_s'])
    return out


def go_status(tel):
    """Preheat GO needs every channel known AND an owner release; with no release the answer is HOLD however good the data looks."""
    missing = [c for c, v in tel.items() if not v['known']]
    return dict(preheat='HOLD', reason=('owner release absent (40!A109, OD-041 FLIGHT HOLD)' if not missing else
                                         f'{len(missing)} channel(s) UNKNOWN and owner release absent'), missing=missing)


def h2_reaches_injector(v):
    """Hydrogen reaches the injection ring if the built line (bypass open or modulating) or the whole branch (both branch valves) is open."""
    return v['H2_Bypass'] in ('O', 'M') or (v['H2_In'] == 'O' and v['H2_Out'] == 'O')


# Faults (40!A106, Fiji 30!A17, HR-P13). Each: the state it starts from, what breaks (stuck valves override the commanded position), the
# sensor that sees it, the commanded response, and what stays unresolved. 'fail' marks lost actuation power (every valve to FAIL_POSITION).
FAULTS = [
    dict(id='HR-F01', name='H2 underflow / flow loss', start='PREHEAT_STUDY', stuck={}, sensor='H2 flow in (Sensor_H2_In)',
         respond='HX_FAULT_ISOLATED', unresolved='source of the underflow is upstream (tank / conditioning, OPEN); drive throttling is Fiji-owned'),
    dict(id='HR-F02', name='H2 leak in the branch', start='PREHEAT_STUDY', stuck={}, sensor='H2 in/out flow mismatch',
         respond='HX_FAULT_ISOLATED', unresolved='leak class, H2 detection and venting in the drive annulus OPEN (HR-P12)'),
    dict(id='HR-F03', name='HX overtemperature', start='PREHEAT_STUDY', stuck={}, sensor='H2 outlet T (Sensor_H2_Out)',
         respond='HX_FAULT_ISOLATED', unresolved='material limit and trip temperature OPEN'),
    dict(id='HR-F04', name='Branch inlet valve stuck open', start='PREHEAT_STUDY', stuck=dict(H2_In='O'), sensor='valve position',
         respond='HX_FAULT_ISOLATED', unresolved='with the outlet closed the cassette holds trapped H2 at the hot side: relief OPEN'),
    dict(id='HR-F05', name='Bypass valve stuck closed', start='BYPASS', stuck=dict(H2_Bypass='C'), sensor='valve position / H2 flow in',
         respond='CROSS_FEED', unresolved='H2 then passes the cold, isolated cassette: its pressure drop at full flow is OPEN'),
    dict(id='HR-F06', name='Bypass valve stuck closed while preheating', start='PREHEAT_STUDY', stuck=dict(H2_Bypass='C'), sensor='valve position',
         respond='CROSS_FEED', unresolved='cannot return to the built line; preheat ends by closing the hot side only'),
    dict(id='HR-F07', name='Excessive HX pressure drop', start='PREHEAT_STUDY', stuck={}, sensor='H2 in/out pressure',
         respond='HX_FAULT_ISOLATED', unresolved='allowable Δp against injector demand OPEN'),
    dict(id='HR-F08', name='Hot-loop loss (pump / supply)', start='PREHEAT_STUDY', stuck={}, sensor='hot isolation valve / H2 outlet T',
         respond='HX_FAULT_ISOLATED', unresolved='drive cooling after a hot-loop loss is the existing system’s fault, not HR-001'),
    # HR-F09..F11: the owner's supplemental register (S&E 39!A32:I36, 2026-10-17, OWN-HR 15!A203); distinct from the older F09/F10/F11 rows of 39.
    # `replay` is the owner's response as ordered steps; every load, energy and endurance stays OPEN / UNSIZED and the gate HOLD.
    dict(id='HR-F09', residual=True, name='Brayton A/B trip during hybrid', start='HYBRID_STUDY', stuck={}, sensor='Brayton status (existing)',
         respond='HX_FAULT_ISOLATED', unresolved='the heat Brayton no longer converts returns to the radiators: margin OPEN (−1.60 GW DIAGNOSTIC already)',
         owner=dict(row='39!A34:I34', trigger='Brayton electrical conversion off; diverted hot energy remains', routing='40_THERMAL; 17_POWER_STORAGE; OD-041; Fiji 15',
                    gate='HOLD; existing 16 GW vs 14.401 GW diagnostic deficit unresolved', load_W='OPEN', energy_J='OPEN', endurance_h='UNSIZED'),
         replay=['HYBRID_STUDY: Brayton A/B converting (no W credited)', 'Brayton trip detected (existing Brayton status)',
                 'isolate or derate the HX: hot isolation closed, H2 back on the built bypass', 'return the energy to the qualified hot radiator or throttle the drive (Fiji-owned)',
                 'assess load shedding and the cooling transition (17_POWER_STORAGE)', 'HOLD: the heat does not disappear; radiator margin OPEN']),
    dict(id='HR-F10', residual=True, name='HX breach contaminates H2 injection', start='PREHEAT_STUDY', stuck={}, sensor='intermediate loop pressure / H2 purity (OPEN)',
         respond='HX_FAULT_ISOLATED', unresolved='contamination already in the H2 line and injector: consequence and purge OPEN; bypass cannot un-contaminate the line',
         owner=dict(row='39!A35:I35', trigger='Cross-leak of hot/intermediate coolant into downstream H2 feed', routing='06_PROPULSION_ARCHITECTURE; Fiji 30; S&E 39; OD-041',
                    gate='HOLD; bypass cannot un-contaminate already affected line', load_W='OPEN', energy_J='OPEN', endurance_h='UNSIZED'),
         replay=['PREHEAT_STUDY: H2 through the cassette', 'cross-leak detected (intermediate pressure / H2 purity: sensor OPEN)',
                 'fast isolated bypass: branch valves closed, H2 on the built line', 'purge and propellant-quality interlock (purge path OPEN)',
                 'evaluate the injector, manifold and nozzle; drive shutdown before any restart (Fiji 30)', 'HOLD: restart blocked until the owner clears the line']),
    dict(id='HR-F11', residual=True, name='Field / plume / dose or optical interference', start='PREHEAT_STUDY', stuck={}, sensor='drive optics / manifold monitors (existing)',
         respond='HX_FAULT_ISOLATED', unresolved='magnetic, thermal-lensing, plume and dose envelopes undefined; geometric gaps 0.21 m (reactor envelope) and 0.43 m (optical leg) are not hazard evidence (HOLD)',
         owner=dict(row='39!A36:I36', trigger='HX/line/valve encroaches on manifold/optical/field hazard envelope', routing='14_HULL_SERVICE; 36_DEFENSE_INTEGRATION; Fiji 25; OD-041',
                    gate='HOLD; 0.21 m geometry clearance is insufficient magnetic/radiation evidence', load_W='OPEN', energy_J='OPEN', endurance_h='UNSIZED'),
         replay=['PREHEAT_STUDY: candidate B in the aft drive annulus', 'encroachment flagged (field / plume / dose envelope UNKNOWN)',
                 'mark the exclusion UNKNOWN; fault-isolate the branch', 'disable preheat; the removable candidate-B overlay may be rerouted (study only)',
                 'HOLD until a quantitative field / plume / dose envelope is approved']),
    dict(id='HR-F12', name='Actuation power loss', start='PREHEAT_STUDY', stuck={}, sensor='bus status', respond='FAIL', unresolved='none in the branch; valve stroke time OPEN'),
    dict(id='HR-F13', name='Drive shutdown (hot)', start='PREHEAT_STUDY', stuck={}, sensor='drive state', respond='BYPASS',
         unresolved='cooldown duration OPEN; existing radiator cooling carries the shutdown heat'),
    dict(id='HR-F14', name='Cold start', start='NO_DATA', stuck={}, sensor='-', respond='BYPASS', unresolved='none: the branch stays closed until a validated release'),
]


def apply_fault(f):
    """Resulting valves, HR state label, H2 delivery and hot-branch isolation after the response, with stuck valves holding position."""
    if f['respond'] == 'FAIL':
        v = dict(FAIL_POSITION); label = 'BYPASS (unpowered)'
    elif f['respond'] == 'CROSS_FEED':
        v = dict(H2_In='O', H2_Out='O', H2_Bypass='C', Hot_Isolation='C'); label = 'HX_FAULT_ISOLATED (cold pass-through)'
    else:
        v = dict(hp.MODES[f['respond']]); label = f['respond']
    v.update(f['stuck'])
    reaches = h2_reaches_injector(v); hot_isolated = v['Hot_Isolation'] == 'C'
    outcome = 'ISOLATED' if reaches and hot_isolated and f['respond'] != 'CROSS_FEED' else 'FALLBACK' if reaches and hot_isolated else 'UNRESOLVED'
    if f.get('residual'):
        outcome += ' / CONSEQUENCE UNRESOLVED'          # isolation stops the branch, not the consequence (contamination, heat, field)
    elif f['unresolved'] and outcome != 'UNRESOLVED' and any(k in f['unresolved'] for k in ('OPEN', 'HOLD')):
        outcome += ' / HOLD'
    return dict(id=f['id'], fault=f['name'], start=f['start'], stuck=f['stuck'], detected_by=f['sensor'], state=label, valves=v,
                h2_reaches_injector=reaches, hot_branch_isolated=hot_isolated, radiator_cooling='existing path unaffected (branch is parallel)',
                outcome=outcome, unresolved=f['unresolved'], owner=f.get('owner'), replay=f.get('replay'))


def report(s=None):
    modes = {m: dict(valves=v, h2_reaches_injector=h2_reaches_injector(v), path=hp.h2_paths(s, hp.SELECTED, hp.H2_LINES[0])[m]['path'] if s else None)
             for m, v in hp.MODES.items()}
    faults = [apply_fault(f) for f in FAULTS]
    tel_none = telemetry(None)
    bad = telemetry(dict(approved=False, source_ref='x', t_s=1.0, values={'hx_transfer': dict(value=5e6, unit='W')}))
    checks = dict(
        fail_position_is_bypass=FAIL_POSITION == hp.MODES['BYPASS'],
        every_fault_keeps_h2=all(r['h2_reaches_injector'] for r in faults),
        every_fault_isolates_hot=all(r['hot_branch_isolated'] for r in faults),
        no_data_is_unknown=all(not v['known'] for v in tel_none.values()),
        unapproved_rejected=all(not v['known'] for v in bad.values()),
        preheat_never_go=go_status(tel_none)['preheat'] == 'HOLD',
        config_never_preheats=all(st in ('BYPASS', 'HX_FAULT_ISOLATED') for st in CONFIG_STATE.values()),
        owner_faults_routed=all(r['owner'] and r['owner']['gate'].startswith('HOLD') and r['replay'] and 'UNRESOLVED' in r['outcome']
                                for r in faults if r['id'] in ('HR-F09', 'HR-F10', 'HR-F11')),
    )
    return dict(study='HR-001 E03 states and faults (NONCANON; every limit, delay and duty OPEN)', candidate=hp.SELECTED,
                fail_position=FAIL_POSITION, configurations={c: dict(state=st, note=CONFIG_NOTE.get(c, '')) for c, st in CONFIG_STATE.items()},
                modes=modes, telemetry_no_data=tel_none, go=go_status(tel_none), faults=faults, checks=checks,
                result='PASS' if all(checks.values()) else 'FAIL')


# ---------- Blender: one still per state / selected fault on the selected candidate -------------------------------------------------------

VALVE_COLOUR = dict(O=(.15, .85, .3), C=(.85, .12, .1), M=(.95, .75, .1))


def stills(s, out, size):
    import bpy
    from mathutils import Vector, Matrix
    cases = [(m, v, m) for m, v in hp.MODES.items()]
    cases += [(r['id'], r['valves'], f"{r['id']}: {r['state']}") for r in map(apply_fault, FAULTS) if r['id'] in ('HR-F05', 'HR-F10', 'HR-F12')]
    paths = []
    for name, valves, title in cases:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        for sub in hp.SUBSYSTEMS:
            path = ROOT/'assets/wayfarer/subsystems'/f'{sub}.blend'
            with bpy.data.libraries.load(str(path), link=False) as (src, dst):
                dst.objects = list(src.objects)
            for ob in dst.objects:
                if ob is None or ob.type not in ('MESH', 'CURVE'):
                    continue
                pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
                lo, hi = min(p.x for p in pts), max(p.x for p in pts); rad = max(max(abs(p.y), abs(p.z)) for p in pts)
                if hi > -100 and lo < -80 and rad < 5.95 and not any(k in ob.name for k in ('Hull', 'Skin', 'Shell', 'Engineering_Envelope')):
                    sc.collection.objects.link(ob)
        hp.apply(s, which=(hp.SELECTED,))
        # Dim the parts of the branch that carry nothing in this state.
        branch_on = valves['H2_In'] == 'O' and valves['H2_Out'] == 'O'; hot_on = valves['Hot_Isolation'] == 'O'
        from common import material
        dim = material('ART_HR_inactive', (.25, .27, .3))
        for ob in sc.objects:
            n = ob.name
            if n.startswith('HR_') and ((('H2_Preheat' in n or 'HX_Core' in n) and not branch_on) or (('Hot_' in n or 'Intermediate' in n) and not hot_on)):
                if ob.data and hasattr(ob.data, 'materials'):
                    ob.data.materials.clear(); ob.data.materials.append(dim)
        for vname, pos in valves.items():
            mat = material(f'ART_HR_valve_{pos}', VALVE_COLOUR[pos])
            for ob in sc.objects:
                if ob.name.startswith(f'HR_{hp.SELECTED}_L') and ob.name.endswith(f'_Valve_{vname}'):
                    ob.data.materials.clear(); ob.data.materials.append(mat); ob.scale = (1.6, 1.6, 1.6)
        txt = bpy.data.curves.new('ART_HR_Title', 'FONT'); txt.body = title; txt.size = 0.28
        t = bpy.data.objects.new('ART_HR_Title', txt); sc.collection.objects.link(t); txt.materials.append(material('ART_HR_text', (.95, .95, .95)))
        sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True
        sc.world = sc.world or bpy.data.worlds.new('ART_HR_World'); sc.world.color = (.055, .075, .10)
        sc.render.resolution_x, sc.render.resolution_y = size, round(size*.75); sc.render.image_settings.file_format = 'PNG'
        cam = bpy.data.objects.new('ART_HR_Camera', bpy.data.cameras.new('ART_HR_Camera')); sc.collection.objects.link(cam); sc.camera = cam
        cam.data.clip_start = 0.05; cam.data.lens = 30
        loc, look = Vector(hp.radial(-80, 13, 270)), Vector(hp.radial(-90.5, 3.2, 270))
        z = (loc-look).normalized(); x = Vector((1, 0, 0)).cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        t.location = loc-z*6+y*1.55-x*2.3; t.rotation_euler = cam.rotation_euler
        p = out/f'hr001_state_{name}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
        print('WF_HR001_STATE', name, flush=True)
    return paths


def main(out=None, size=1024):
    s = load(ROOT)[0]; r = report(s)
    if out is None:
        print(json.dumps(r, indent=1)); return r
    out.mkdir(parents=True, exist_ok=True); r['renders'] = stills(s, out, size)
    (out/'hr001_states.json').write_text(json.dumps(r, indent=1)+'\n'); print('WF_HR001_STATE done', out, r['result'], flush=True)
    return r


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path); ap.add_argument('--size', type=int, default=1024)
    a = ap.parse_args(argv)
    main(None if a.out is None else (a.out if a.out.is_absolute() else ROOT/a.out), a.size)
