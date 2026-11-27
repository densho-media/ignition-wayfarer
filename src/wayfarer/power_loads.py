"""EPS-A electrical load foundation (ISSA Phase II, owner brief 2026-11-27): the whole-ship electrical load model. PROTOTYPE.

The table lives in data/wayfarer_3d.toml [power.loads]; values owned elsewhere are referenced, never copied (`spec:` paths read the
spec, `calc:` names ask the owner module through CALC). Nothing here is a rating: power.rating and power.hotel_source stay OPEN.

Per load: a (low, nominal, high) band of electrical input while it runs, the connected rating, standby power, startup energy, peak
power and duration, duty (a number, or "PARAM": an operating doctrine the caller supplies, OPEN otherwise), bus, priority, the loop
that receives its heat, energy that leaves the ship (optical, RF), heat it lifts between loops, and its evidence class. known = false
keeps an unresolved load OPEN: its planning band is reported apart and never enters a known total.

Per state (operating, bounding and survival states; fault scenarios modify a state and are not states):
- continuous_W: every running continuous load at its level, engaged loads included (the instantaneous demand the sources must carry);
- peak_W: continuous plus the PEAK and START loads (store-fed transients);
- time_averaged_W: duty-weighted, a load that replaces another taking the other's time; None while a PARAM duty is not supplied;
- generation_W: continuous plus conversion and distribution losses (what the sources must deliver);
- heat ledger by loop: dissipated electrical energy, heat moved by heat pumps, energy exported and energy stored. Conservation:
  sum(loops) + exported + stored = electrical input + heat lifted from outside the loops (the tank farm's leak).
- open: the OPEN loads that would run, with their planning bands.
Storage: the 2 MWh main battery (WORKING) less the protected black-start reserve gives ride-through energy; endurance per state at
discharge efficiency. The survival reserve never charges the pulse bank (power.storage.rules) and is not counted as restart energy.
engagement(): the parameterized active-defense duty model (storage, recharge, heat debt) for EPS-B sweeps.

    python3 src/wayfarer/power_loads.py      # prints the summary and writes references/p1_power_loads.json
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_power_loads.json'
WH = 3600.0
PRIORITIES = ('ESSENTIAL', 'MISSION', 'NOMINAL', 'DISCRETIONARY')
BUSES = {'A', 'B', 'AB', 'E', 'L1'}
LOOPS = ('RING_COLD', 'WARM', 'LOW', 'HOT')
EXTERNAL = ('TANKS',)                         # heat taken from outside the loops (the tank farm's environmental leak)
ROLES = {'CONT', 'PEAK', 'START'}
CLASSES = {'SPEC', 'DERIVED', 'PROTO', 'STUDY'}
KINDS = {'OPERATING', 'BOUNDING', 'SURVIVAL'}


def q(s):
    return s['power']['loads']


def _path(s, path):
    node = s
    for part in path.split('.'):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


# ---------- references to owner modules ---------------------------------------------------------------------------------------

def _ring(ids):
    import ring_services
    eq = {e['id']: e['W'] for e in ring_services.EQUIPMENT}
    return 2*sum(eq[i] for i in ids)


def _cryo(s):
    import fuel_loads
    return fuel_loads.cooling(s)


def _burn(s):
    import heat_rejection
    return heat_rejection.report(s)['burn'][-1]


CALC = {
    'ring_core_W': lambda s: _ring(('CO2', 'CHX', 'P1', 'P2', 'TCC', 'VENT', 'AV')),
    'ring_hotel_W': lambda s: _ring(('LIGHT', 'GALLEY', 'LAB')),
    'o2_electrolysis_W': lambda s: q(s)['o2_kg_per_person_day']*occupancy(s)*q(s)['o2_electrolysis_kWh_kg'][1]*1000.0/24.0,
    'cryo_input_W': lambda s: _cryo(s)['rejected_W'],          # fuel_loads: input work (lift x W/W) is what reaches the rejector
    'cryo_lift_W': lambda s: _cryo(s)['shield_lift_W']+_cryo(s)['he3_stage_lift_W'],
    'burn_pump_work_W': lambda s: _burn(s)['pump_work_W'],
    'burn_pump_lift_W': lambda s: _burn(s)['warm_load_W'],
    'warm_section_W': lambda s: next(x['load_W'] for x in s['radiators']['zones']['sections'] if x['id'] == 'WARM'),
}


def pump_factor(s):
    """Heat-pump work per watt lifted from the warm loop to the hot loop: (T_hot/T_warm - 1)/eta_II (thermal.loops, F02)."""
    a = s['thermal']['loops']
    return (s['radiators']['temperature']['value']/a['warm']['temperature_K']-1.0)/a['architecture']['heat_pump_second_law_efficiency']


def occupancy(s):
    return float(ref(s, q(s)['rated_occupancy_ref']))


def ref(s, r, memo=None):
    kind, _, name = r.partition(':')
    if kind == 'spec':
        return _path(s, name)
    if kind == 'calc':
        if memo is None:
            return CALC[name](s)
        if name not in memo:
            memo[name] = CALC[name](s)
        return memo[name]
    raise KeyError(r)


def band(v, spread=None):
    """A (low, nominal, high) band from a scalar (x spread), a [low, high] pair (nominal at the middle) or a triple."""
    if isinstance(v, (int, float)):
        lo, hi = spread or (1.0, 1.0)
        return (v*lo, float(v), v*hi)
    if len(v) == 2:
        return (float(v[0]), (v[0]+v[1])/2.0, float(v[1]))
    return tuple(float(x) for x in v)


def scale(b, f):
    return tuple(x*f for x in b)


def add(a, b):
    return tuple(x+y for x, y in zip(a, b))


ZERO = (0.0, 0.0, 0.0)


# ---------- items -----------------------------------------------------------------------------------------------------------

def items(s):
    """Resolved load items keyed by id: W band (None when OPEN), planning band, rating, export and heat-pump lift bands."""
    out = {}; memo = {}
    for it in q(s)['items']:
        r = dict(it)
        r['role'] = it.get('role', 'CONT')
        r['known'] = it.get('known', True)
        if r['known']:
            r['W'] = band(ref(s, it['ref'], memo), it.get('spread')) if 'ref' in it else band(it['W'])
            r['planning_W'] = None
        else:
            r['W'] = None
            pl = it.get('planning_W') or (ref(s, it['planning_ref']) if 'planning_ref' in it else None)
            r['planning_W'] = band(pl) if pl is not None else None
        base = r['W'] or r['planning_W']
        r['rated_W'] = it.get('rated_W', base[2] if base else None)
        r['standby_W'] = it.get('standby_W', 0.0)
        r['startup_J'] = it.get('startup_J')
        if 'energy_ref' in it:
            r['energy_J'] = float(ref(s, it['energy_ref']))*WH
            r['peak_s'] = r['energy_J']/r['W'][1]
        if 'exported_ref' in it:
            r['exported_W'] = float(ref(s, it['exported_ref']))
        r['exported_fraction'] = it.get('exported_fraction', 0.0)
        if 'moves' in it:
            src, dst, rr = it['moves']
            lift = float(ref(s, rr, memo))
            r['moves'] = (src, dst, (lift*r['W'][0]/r['W'][1], lift, lift*r['W'][2]/r['W'][1]))
        if 'lift' in it:
            r['lift'] = dict(it['lift'], sink_W=float(ref(s, it['lift']['sink_ref'], memo)), factor=pump_factor(s))
        out[it['id']] = r
    return out


# ---------- states ----------------------------------------------------------------------------------------------------------

def state_defs(s):
    return {st['id']: st for st in q(s)['states']}


def expand(s, sid):
    """Levels and duties of a state with its base chain applied (the state's own entries win)."""
    defs = state_defs(s); chain = []
    node = defs[sid]
    while node is not None:
        chain.append(node); node = defs.get(node.get('base'))
    levels, duty = {}, {}
    for node in reversed(chain):
        levels.update(node.get('levels', {})); duty.update(node.get('duty', {}))
    return {k: v for k, v in levels.items() if v}, duty


def _export(it, consumption):
    if 'exported_W' in it:
        return tuple(min(c, it['exported_W']*(c/it['W'][1])) for c in consumption)
    return scale(consumption, it['exported_fraction'])


def ledger(s, sid, duty=None, I=None):
    """The state's demand, heat and supply ledger (bands in W). duty: {load id: fraction} for PARAM duties."""
    I = I or items(s); st = state_defs(s)[sid]; levels, sduty = expand(s, sid)
    duty = {**sduty, **(duty or {})}
    pm = q(s)['pmad_loss_fraction']
    cont = peak = avg_known = exported = stored = ZERO
    heat = {k: ZERO for k in LOOPS+EXTERNAL}
    supply = {}; rows = []; open_rows = []; params = []
    replaced = {I[k]['replaces']: k for k in levels if I[k].get('replaces') and I[k]['replaces'] in levels}
    lifters = [k for k in levels if 'lift' in I[k]]
    for k, lvl in levels.items():
        it = I[k]
        if k in lifters:
            continue
        if not it['known']:
            open_rows.append(dict(id=k, level=lvl, planning_W=scale(it['planning_W'], lvl) if it['planning_W'] else None,
                                  basis=it['basis']))
            continue
        c = scale(it['W'], lvl)
        d = duty.get(k, it.get('duty', 1.0))
        if k in replaced:                                      # the engaged load takes this one's time
            d2 = duty.get(replaced[k], I[replaced[k]].get('duty', 1.0))
            d = None if d2 == 'PARAM' else 1.0-d2
        if d == 'PARAM':
            d = None; params.append(k)
        if it['role'] == 'CONT':
            if k not in replaced:
                cont = add(cont, c)
            if d is not None:
                avg_known = add(avg_known, scale(c, d))
        else:
            peak = add(peak, c)
        bus = it['bus']; src = it.get('supply') or ('L1' if bus == 'L1' else st['supply'][0])
        if k in replaced:                                      # engaged: the replacing load runs instead (instantaneous ledger)
            rows.append(dict(id=k, level=lvl, role=it['role'], duty=d if k not in params else 'PARAM', W=c, bus=bus,
                             priority=it['priority'], heat=it['heat'], exported_W=ZERO, replaced_by=replaced[k]))
            continue
        supply[src] = add(supply.get(src, ZERO), c if it['role'] == 'CONT' else ZERO)
        e = _export(it, c)
        if it.get('stored'):
            eta = band(q(s)['storage']['charge_efficiency'])
            sto = tuple(x*y for x, y in zip(c, eta)); stored = add(stored, sto)
            heat[it['heat']] = add(heat[it['heat']], tuple(x-y for x, y in zip(c, sto)))
        else:
            exported = add(exported, e)
            heat[it['heat']] = add(heat[it['heat']], tuple(x-y for x, y in zip(c, e)))
        if 'moves' in it:
            src_l, dst_l, lift = it['moves']; lift = scale(lift, lvl)
            heat[src_l] = add(heat[src_l], scale(lift, -1.0)); heat[dst_l] = add(heat[dst_l], lift)
        rows.append(dict(id=k, level=lvl, role=it['role'], duty=d if k not in params else 'PARAM', W=c, bus=bus, priority=it['priority'],
                         heat=it['heat'], exported_W=e, replaced_by=replaced.get(k)))
    for k in lifters:                                          # heat pumps lift what the sink cannot take, after every other load
        it = I[k]; lf = it['lift']
        lift = tuple(max(0.0, h-lf['sink_W']) for h in heat[lf['from']])
        work = scale(lift, lf['factor'])
        if any(w > r*(1+1e-9) for w, r in zip(work, (it['rated_W'],)*3)):
            raise ValueError(f'{sid}: {k} needs more than its rating')
        cont = add(cont, work); supply['L1'] = add(supply.get('L1', ZERO), work)
        heat[lf['from']] = add(heat[lf['from']], scale(lift, -1.0)); heat[lf['to']] = add(heat[lf['to']], add(lift, work))
        rows.append(dict(id=k, level=levels[k], role='CONT', duty=1.0, W=work, lift_W=lift, bus=it['bus'], priority=it['priority'],
                         heat=it['heat'], exported_W=ZERO, replaced_by=None))
        avg_known = add(avg_known, work)
    loss = tuple(c*f for c, f in zip(cont, pm))
    l1 = tuple(c*f for c, f in zip(supply.get('L1', ZERO), pm))
    # conversion losses: ship-bus electronics on LOW cold plates; burn-bus (L1) conversion sits with the drive generators (hot loop, OPEN)
    heat['LOW'] = add(heat['LOW'], tuple(a-b for a, b in zip(loss, l1))); heat['HOT'] = add(heat['HOT'], l1)
    electrical = add(add(cont, peak), loss)
    return dict(id=sid, kind=st['kind'], supply_levels=st['supply'], note=st['note'], legacy=st.get('legacy'),
                continuous_W=cont, peak_W=add(cont, peak), pmad_loss_W=loss, generation_W=add(cont, loss),
                time_averaged_W=None if params else add(avg_known, loss_avg(avg_known, pm)),
                time_averaged_without_param_W=avg_known, param_duties=params,
                by_supply_W=supply, heat_W=heat, exported_W=exported, stored_W=stored, electrical_W=electrical,
                open=open_rows, loads=rows)


def loss_avg(avg, pm):
    return tuple(a*f for a, f in zip(avg, pm))


def ledgers(s, duty=None, I=None):
    I = I or items(s)
    return {sid: ledger(s, sid, duty, I) for sid in state_defs(s)}


def by_priority(L):
    out = {p: ZERO for p in PRIORITIES}
    for r in L['loads']:
        if r['role'] == 'CONT' and not r['replaced_by']:
            out[r['priority']] = add(out[r['priority']], r['W'])
    return out


def fault(s, sid, fid, Ls=None):
    """Loads that lose their supply path under a fault, and the priority demand that must still be met (shedding to a capacity is EPS-B)."""
    f = next(x for x in q(s)['faults'] if x['id'] == fid); L = Ls[sid] if Ls else ledger(s, sid); lost = []
    for r in L['loads']:
        if 'BUS_A' in f['removes'] and r['bus'] == 'A' or 'BUS_E' in f['removes'] and r['bus'] == 'E' or 'L1' in f['removes'] and r['bus'] == 'L1':
            lost.append(r['id'])
    need = by_priority(L)
    return dict(fault=fid, state=sid, removes=f['removes'], note=f['note'], loads_without_path=lost,
                must_keep_W=add(need['ESSENTIAL'], need['MISSION']), sheddable_W=add(need['NOMINAL'], need['DISCRETIONARY']))


# ---------- storage ---------------------------------------------------------------------------------------------------------

def storage(s, Ls=None, I=None):
    I = I or items(s); Ls = Ls or ledgers(s, I=I); st = s['power']['storage']; sp = q(s)['storage']
    E = st['main_battery']['usable_energy_Wh']*WH; pulse = st['pulse_bank']
    eta_d = band(sp['discharge_efficiency']); eta_c = band(sp['charge_efficiency'])
    BS = Ls['BLACK_START']; charger = ZERO; I = I or items(s)
    for r in BS['loads']:
        if I[r['id']].get('stored'):
            charger = add(charger, r['W'])
    bs = tuple((g-c)*(1+f) for g, c, f in zip(BS['continuous_W'], charger, q(s)['pmad_loss_fraction']))
    pulse_J = pulse['energy_Wh']*WH
    # reserve: the pulse-bank charge (worst charge efficiency) plus the other black-start services through the hold, high band
    reserve = pulse_J/eta_c[0] + bs[2]*sp['black_start_hold_h']*3600.0/eta_d[0]
    ride = E-reserve
    fade = band(sp['calendar_fade_per_year']); eol = [E*(1-f*sp['end_of_life_years']) for f in (fade[2], fade[1], fade[0])]
    endurance = {}
    for sid, L in Ls.items():
        g = L['generation_W']
        if g[1] > 0 and L['kind'] != 'BOUNDING':
            endurance[sid] = dict(ride_through_h=tuple(ride*e/gw/3600.0 for e, gw in zip(eta_d, reversed(g))),
                                  whole_battery_h=tuple(E*e/gw/3600.0 for e, gw in zip(eta_d, reversed(g))))
    mb = st['main_battery']
    pulse_part = pulse_J/eta_c[0]; services_part = reserve-pulse_part
    return dict(main_usable_J=E, black_start_services_W=bs, black_start_reserve_J=reserve, ride_through_J=ride, end_of_life_usable_J=tuple(eol),
                reserve_breakdown_J=dict(pulse_bank_recharge=pulse_part, restart_services_hold=services_part),
                reserve_fraction=reserve/E, ride_through_at_end_of_life_J=tuple(e-reserve for e in eol),
                kWh=dict(main_usable=E/3.6e6, black_start_reserve=reserve/3.6e6, ride_through=ride/3.6e6, pulse_bank_recharge=pulse_part/3.6e6,
                         restart_services_hold=services_part/3.6e6),
                pack_mass_kg=E/WH/mb['specific_energy_Wh_kg'], pack_mass_basis=mb['specific_energy_basis'],
                installed_mass='OPEN (power.storage.main_battery.installed_mass): the 800 Wh/kg figure is already pack-level, so no '
                               'packaging factor is applied to it; containment, thermal and switching remain unsized',
                pulse_J=pulse_J, pulse_discharge_s=pulse_J/pulse['power_W'], pulse_charge_s=tuple(pulse_J/(1e6*x) for x in (2.0, 1.0, 0.5)),
                pulse_charges_per_battery=E/pulse_J, endurance=endurance,
                survival_reserve='capacity OPEN (power.storage.survival_reserve.capacity); never a restart source')


# ---------- the active-defense duty model -----------------------------------------------------------------------------------

def engagement(P_pro, P_act, t_eng_s, interval_s, P_gen_def, E_buf_J, P_export=0.0, Q_reject_def=None, Q_pro_heat=None,
               eta_c=1.0, eta_d=1.0, P_dis_max=math.inf):
    """One repeating engagement cycle: proactive between engagements, the active band during one (t_eng_s every interval_s).
    P_gen_def: generation available to defense (W); E_buf_J: dedicated defense buffer; P_export: energy leaving the ship while
    engaged (optical); Q_reject_def: heat rejection available to defense (W); Q_pro_heat: defense heat between engagements.
    Returns the average demand, the buffer draw per engagement, recharge time, whether the cycle repeats indefinitely and the heat debt."""
    if not (0 < t_eng_s <= interval_s):
        raise ValueError('engagement shorter than its interval')
    avg = P_pro + (P_act-P_pro)*t_eng_s/interval_s
    # eta_d: stored energy per delivered joule is 1/eta_d; eta_c: recharge takes 1/eta_c of the stored energy from the generators;
    # P_dis_max: the buffer cannot deliver more than this, so the shortfall above it is unserved (the cycle fails)
    draw = max(0.0, (P_act-P_gen_def)*t_eng_s)/eta_d
    spare = P_gen_def-P_pro
    recharge = draw/(spare*eta_c) if draw and spare > 0 else (0.0 if not draw else math.inf)
    power_ok = P_act-P_gen_def <= P_dis_max
    sustainable = draw <= E_buf_J and recharge <= interval_s-t_eng_s and P_gen_def >= P_pro and power_ok
    out = dict(average_W=avg, buffer_draw_J=draw, buffer_ok=draw <= E_buf_J, recharge_s=recharge, sustainable=sustainable, power_ok=power_ok,
               max_engagement_s=(E_buf_J*eta_d/(P_act-P_gen_def) if P_act > P_gen_def else math.inf),
               storage_loss_heat_J=draw*(1-eta_d)+(draw/eta_c-draw if draw else 0.0))
    if Q_reject_def is not None:
        Qp = P_pro if Q_pro_heat is None else Q_pro_heat
        debt = max(0.0, (P_act-P_export-Q_reject_def)*t_eng_s)
        cool = Q_reject_def-Qp
        out.update(heat_debt_J=debt, thermal_recovery_s=(debt/cool if debt and cool > 0 else (0.0 if not debt else math.inf)))
        out['sustainable'] = out['sustainable'] and out['thermal_recovery_s'] <= interval_s-t_eng_s
    return out


# ---------- audit and checks ------------------------------------------------------------------------------------------------

def audit(s, Ls=None, I=None):
    """What each borrowed number is (electrical input, heat, optical, stored) and where the old estimates stand."""
    I = I or items(s); Ls = Ls or ledgers(s, I=I); fd = s['forward_defense']['power']; fl = s['physics']['fuel_loads']['cooling']
    low = next(x for x in s['radiators']['zones']['sections'] if x['id'] == 'LOW')
    cl = Ls['COAST_HV_PROACTIVE']
    low_e = cl['heat_W']['LOW']
    return {
        'cryocoolers': dict(electrical_W=I['TMS.CRYOCOOLERS']['W'], lift_W=I['TMS.CRYOCOOLERS']['moves'][2],
                            rejected_W=add(I['TMS.CRYOCOOLERS']['W'], I['TMS.CRYOCOOLERS']['moves'][2]),
                            note='fuel_loads.cooling.rejected_W is the input work; the lifted ~3.8 kW adds to it at the rejector (1 %).'),
        'avionics_allowance': dict(allowance_W=fl['avionics_W'], low_loop_heat_coast_W=low_e, low_section_W=low['load_W'],
                                   note='LOW carries cryocoolers, computing, GNC, comms and the conversion losses; the 0.3 MW allowance '
                                        'is about ten times the computing estimate but covers the PMAD losses at proactive coast.'),
        'eye': dict(quiet_W=I['PROT.EYE_QUIET']['W'], burn_watch_W=I['PROT.EYE_BURN_WATCH']['W'], ablation_W=I['PROT.EYE_ABLATION']['W'],
                    ablation_optical_W=I['PROT.EYE_ABLATION'].get('exported_W'),
                    note='EYE values are electrical inputs (laser input plus non-laser load); the ablation laser sends 1 MW out of the ship.'),
        'crown': dict(normal=fd['crown_normal'], heavy=fd['crown_heavy'], extreme=fd['crown_extreme'],
                      note='Crown rows split electrical = optical + heat (wall-plug 0.5). The normal active band (15-30 MW electrical) '
                           'includes the 10 MW Crown normal; 5 MW of it leaves the ship as light.'),
        'defense_bands': dict(electrical_W=fd['bands_W'], thermal_normal_W=s['thermal']['loops']['architecture']['defense_normal_W'],
                              note='17_POWER_STORAGE bands are electrical inputs; 40_THERMAL routes 15-30 MW of normal active defense heat to '
                                   'the warm loop: the same numbers, so the thermal band gives no credit for the Crown light that leaves '
                                   'the ship (conservative by up to 5 MW).'),
        'field_services': dict(range_W=fd['field_services_W']['range'], status=fd['field_services_W']['canon_status'],
                               note='OPEN planning allowance from the thermal sheet; possibly inside the proactive band; kept OPEN.'),
        'repair_bus': dict(W=fd['repair_bus_W']['value'], status=fd['repair_bus_W']['canon_status'],
                           note='Intermittent maintenance load after engagements; its duty is a doctrine (PARAM).'),
        'burn_heat_pumps': dict(rated_work_W=I['TMS.BURN_HEAT_PUMPS']['rated_W'], factor=I['TMS.BURN_HEAT_PUMPS']['lift']['factor'],
                                high_thrust_lift_W=next(r['lift_W'] for r in Ls['HIGH_THRUST']['loads'] if r['id'] == 'TMS.BURN_HEAT_PUMPS'),
                                high_thrust_work_W=next(r['W'] for r in Ls['HIGH_THRUST']['loads'] if r['id'] == 'TMS.BURN_HEAT_PUMPS'),
                                note='F02 sized 210 MW of drive electric work for 35 MW lifted (5 MW machinery + 30 MW defense heat at burnout). '
                                     'Since the Graded Thermal Blade the WARM section takes 5 MW of warm heat in every mode, and the Crown light '
                                     'leaves the ship, so the pumps lift only the warm heat beyond the section: the running work is computed here.'),
        'drive_standby_startup': dict(standby='OPEN', seed_coils='OPEN', pulse_bank_W=I['PROP.PULSE_DISCHARGE']['W'],
                                      note='Startup power comes from the pulse bank; standby and seed-coil power are OPEN.'),
        'phase1_reconciliation': dict(
            ship_service_without_defense_W=tuple(c-p for c, p in zip(cl['continuous_W'], I['PROT.DEF_PROACTIVE']['W'])),
            proactive_coast_W=cl['continuous_W'],
            continuous_active_W=Ls['COAST_HV_CONTINUOUS_ACTIVE']['continuous_W'],
            note='Phase I: 0.8 MW ship service, 3.6 MW proactive coast, 26 MW active coast. Field services and drive standby are now OPEN '
                 'items (planning bands apart), so the known totals fall by ~1.35 MW nominal.'),
    }


def check(s):
    fails = []
    try:
        I = items(s)
    except (KeyError, TypeError) as e:
        return [f'unresolved reference {e}']
    for k, it in I.items():
        if it['priority'] not in PRIORITIES or it['bus'] not in BUSES or it['heat'] not in LOOPS or it['role'] not in ROLES or it['class'] not in CLASSES:
            fails.append(f'{k}: priority/bus/heat/role/class vocabulary')
        b = it['W'] or it['planning_W']
        if it['known']:
            if not (0 <= b[0] <= b[1] <= b[2]):
                fails.append(f'{k}: band must be ordered and non-negative')
        elif any('W' in x or 'ref' in x for x in q(s)['items'] if x['id'] == k):
            fails.append(f'{k}: an OPEN load carries no known value')
        if it.get('replaces') and it['replaces'] not in I:
            fails.append(f'{k}: replaces an unknown load')
    if len(I) != len(q(s)['items']):
        fails.append('load ids must be unique')
    defs = state_defs(s)
    for sid, st in defs.items():
        if st['kind'] not in KINDS:
            fails.append(f'{sid}: kind')
        if st.get('base') and st['base'] not in defs:
            fails.append(f'{sid}: unknown base')
        lv, du = expand(s, sid)
        for k in list(lv)+list(du):
            if k not in I:
                fails.append(f'{sid}: unknown load {k}')
        for k, d in du.items():
            if not (isinstance(d, (int, float)) and 0 <= d <= 1):
                fails.append(f'{sid}: duty of {k} must be a fraction')
    if fails:
        return fails
    Ls = ledgers(s, I=I)
    for sid, L in Ls.items():
        for i in range(3):
            lifted = sum(-L['heat_W'][e][i] for e in EXTERNAL)
            lhs = sum(L['heat_W'][k][i] for k in LOOPS) + L['exported_W'][i] + L['stored_W'][i]
            rhs = L['electrical_W'][i] + lifted
            if not math.isclose(lhs, rhs, rel_tol=1e-9, abs_tol=1e-6):
                fails.append(f'{sid}: energy not conserved ({lhs} vs {rhs})')
        if any(L['heat_W'][k][1] < -1e-6 for k in ('RING_COLD', 'LOW', 'HOT')):
            fails.append(f'{sid}: a loop cannot lose more heat than it receives')
        if L['kind'] == 'SURVIVAL' and any(r['bus'] == 'L1' or r['role'] != 'CONT' for r in L['loads']):
            fails.append(f'{sid}: survival states draw no burn or transient power')
    st = s['power']['storage']
    if 'SURVIVAL_RESERVE' in st['pulse_bank']['charge_sources']:
        fails.append('the survival reserve never charges the pulse bank')
    for step in s['power']['black_start']['steps']:
        if 'SURVIVAL_RESERVE' in step['supplied_by'] and (step['charges'] or step['reactor'] != 'OFF'):
            fails.append(f'black start step {step["step"]}: the survival reserve wakes services only, never restart')
    sto = storage(s, Ls, I)
    if not 0 < sto['black_start_reserve_J'] < sto['main_usable_J']:
        fails.append('the black-start reserve must lie inside the main battery')
    return fails


def report(s):
    I = items(s); Ls = ledgers(s, I=I)
    return dict(status='PROTOTYPE (EPS-A, ISSA Phase II): load bands, not ratings; power.rating OPEN',
                units=dict(power='W', energy='J', time='s unless _h'), occupancy=occupancy(s),
                items=I, states=Ls, storage=storage(s, Ls, I), audit=audit(s, Ls, I),
                priorities={k: by_priority(L) for k, L in Ls.items()},
                faults=[fault(s, 'COAST_HV_PROACTIVE', f['id'], Ls) for f in q(s)['faults']], failures=check(s))


if __name__ == '__main__':
    from spec import load
    s = load()[0]; r = report(s)
    OUTPUT.write_text(json.dumps(r, indent=1, default=lambda x: None if isinstance(x, float) and not math.isfinite(x) else x)+'\n')
    MW = lambda b: '—' if b is None else '/'.join(f'{v/1e6:7.3f}' for v in b)
    print(f'{"state":28s} {"continuous MW lo/nom/hi":28s} {"generation MW":28s} open')
    for k, L in r['states'].items():
        print(f'{k:28s} {MW(L["continuous_W"]):28s} {MW(L["generation_W"]):28s} {len(L["open"])} {L["param_duties"] or ""}')
    st = r['storage']
    print(f"\nblack-start reserve {st['black_start_reserve_J']/WH/1e3:.0f} kWh, ride-through {st['ride_through_J']/WH/1e3:.0f} kWh, pack {st['pack_mass_kg']:.0f} kg")
    for k, e in st['endurance'].items():
        print(f"  {k:28s} ride-through h {'/'.join(f'{x:.2f}' for x in e['ride_through_h'])}")
    print('failures:', r['failures'] or 'none')
