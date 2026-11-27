"""ISSA Phase II, mission architecture and modular provisioning (owner clarification 2026-11-27: the six-year duration is narrative,
not a provisioning requirement). STUDY (NONCANON). Writes ../results/phase2_mission.json.

    python3 work/ship-systems-architecture/phase2/mission.py

Kinematics use the canon first-ignition ramp (linear 0 -> 1.5 g while reaching 0.016 c: 7.548 d, 6.970 AU, mission.first_ignition_result);
each of the four burns (out, brake, return, brake) is that ramp, and a short trip that never reaches 0.016 c ramps to a lower peak at
the same jerk. Propellant scales with the mission delta-v through the B02 whole-mission mass ratio (mass_model). Relativistic terms are
below 1e-4 at 0.016 c and are ignored. Every rate here is a PROTOTYPE planning value; no duration is canon.
"""
import json
import math
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import mass_model  # noqa: E402

OUT = Path(__file__).resolve().parents[1]/'results'
C = 299792458.0; AU = 1.495978707e11; DAY = 86400.0; YR = 365.25*DAY; G0 = 9.80665

DESTINATIONS = [   # (id, name, one-way AU, destination operations d, purpose)
    ('JUPITER', 'Jupiter system (outer planets, near)', 5.2, 60, 'shakedown, moons, field and dust science'),
    ('NEPTUNE', 'Neptune / outer planets', 30.1, 60, 'ice giants, Triton'),
    ('KUIPER', 'Kuiper Belt (classical, 45 AU)', 45.0, 60, 'KBO rendezvous, survey'),
    ('TERMINATION_SHOCK', 'Termination shock (~90 AU)', 90.0, 30, 'solar wind physics'),
    ('HELIOPAUSE', 'Heliopause (~120 AU)', 120.0, 30, 'heliosphere boundary, interstellar medium'),
    ('ISM_200', 'Nearby interstellar space (200 AU)', 200.0, 30, 'pristine interstellar medium and dust'),
    ('AU_500', '500 AU', 500.0, 30, 'solar gravitational lens begins near 550 AU'),
    ('SGL_650', 'Solar gravitational lens line (650 AU)', 650.0, 90, 'SGL imaging campaign along the focal line'),
    ('AU_1000', '1,000 AU', 1000.0, 30, 'deep interstellar precursor'),
    ('OORT_INNER', 'Inner Oort Cloud (inner edge, ~2,000 AU)', 2000.0, 60, 'Oort objects, Hills-cloud survey'),
    ('NARRATIVE_6Y', 'Story mission (~3,000 AU, six years)', 3000.0, 60, 'narrative scenario only'),
]
PROFILES = [('6 months', 0.5), ('12 months standard', 1.0), ('24 months extended', 2.0), ('36 months long-duration', 3.0),
            ('5 years exceptional', 5.0), ('10 years endurance bound', 10.0)]

# Provisioning rates per person-day (kg) unless noted: low / nominal / high, PROTOTYPE planning values with their basis
RATES = dict(
    hygiene_clothing=(0.10, 0.17, 0.25),     # ISS crew provisions (wipes, clothing, hygiene) without laundry
    medical=(0.02, 0.05, 0.10),
    eclss_expendables=(0.10, 0.20, 0.35),    # filters, sorbent and cartridges, UPA/WPA expendables (ISS ~1-2 t/yr station level)
)
FOOD = {  # kg per person-day as stored (incl. packaging), from ECLSS-A (eclss_mass.py), and stored volume L
    'conventional': (1.83, 3.6), 'mixed': (1.39, 2.9), 'dehydrated': (0.95, 2.1),
}
SPARES_T_PER_YR = (2.0, 4.0, 8.0)            # ship-level spares and MRO stock, crew-independent (ISS ~ 4-6 t/yr all ORUs; Wayfarer has fabrication)
RESERVE_D = 30                               # DR-05 survival reserve, dense rations 1.0 kg/p-d + 3.5 kg water/p-d
RESERVE_KG = 1.0+3.5
CONTAINER = dict(count=54, volume_m3=2419/54, packing=0.70, rack_mass_limit_t=(4.0, 6.0, 8.0),
                 basis='docs/MODEL.md: 54 dry-store containers, 2,419 m3; rack mass limit PROTOTYPE (1.5 g axial on the rack frames)')


def kinematics(D_AU, v_frac=0.016):
    s = spec.load()[0]
    fi = s['mission']['first_ignition_result']
    T0 = fi['duration_d']*DAY; x0 = fi['distance_AU']*AU; v0 = 0.016*C
    k = 2*v0/T0**2                               # jerk of the canon ramp (a = k t; v = k t^2/2; x = k t^3/6)
    v = v_frac*C; T = math.sqrt(2*v/k); xr = k*T**3/6
    D = D_AU*AU
    if 2*xr > D:                                 # never reaches v: ramp to the peak that fits, then brake
        T = (3*(D/2)/k)**(1/3); v = k*T**2/2; xr = D/2
    coast = (D-2*xr)/v
    return dict(v_peak_c=v/C, ramp_d=T/DAY, ramp_AU=xr/AU, coast_d=coast/DAY, one_way_d=(2*T+coast)/DAY, check_T0_d=T0/DAY, check_x0_AU=x0/AU)


def propellant(s, dv_total):
    m = mass_model.report(s); dep = m['departure']['mass_kg']; prop = m['departure']['propellant_kg']
    ve = 4*0.016*C/math.log(dep/(dep-prop))     # effective whole-mission exhaust speed from the B02 four-burn loading
    dry = dep-prop
    return dry*(math.exp(dv_total/ve)-1), ve, prop


def provisioning(people, days, food='conventional', recovery=0.98, life=None, case=1):
    life = life or tomllib.loads((ROOT/'data/life_support.toml').read_text())
    rate = {r['id']: r['value'] for r in life['rate']}
    f_kg, f_L = FOOD[food]
    pd = people*days
    deg = 0.0 if days <= 3*365 else 0.05      # nutrient-loss allowance beyond ~3 yr (extra stock for supplements / spoilage)
    o2_water = rate['O2']*18.0/16.0             # O2 from electrolysis of stored water, O2 recovery credited 0 (life_support process)
    items = dict(
        food=pd*f_kg*(1+deg), water_makeup=pd*rate['WATER_TURNOVER']*(1-recovery), o2_water=pd*o2_water,
        hygiene_clothing=pd*RATES['hygiene_clothing'][case], medical=pd*RATES['medical'][case],
        eclss_expendables=pd*RATES['eclss_expendables'][case], spares=SPARES_T_PER_YR[case]*1e3*days/365.25,
        reserve=people*RESERVE_D*RESERVE_KG)
    vol = (pd*f_L/1e3+(items['water_makeup']+items['o2_water'])/1e3+(items['hygiene_clothing']+items['medical']+items['eclss_expendables'])/250
           + items['spares']/400 + items['reserve']/700)/CONTAINER['packing']
    tot = sum(items.values())
    cont = max(math.ceil(tot/1e3/CONTAINER['rack_mass_limit_t'][case]), math.ceil(vol/CONTAINER['volume_m3']))
    return dict(people=people, days=days, food=food, recovery=recovery, items_kg=items, total_kg=tot, volume_m3=vol, containers=cont,
                crew_consumables_kg=tot-items['spares'])


def endurance(people, loaded_kg_crew, food='conventional', recovery=0.98, ration=1.0, garden_calories=0.0, life=None):
    """days a crew can live on a given crew-consumable load (spares excluded)."""
    life = life or tomllib.loads((ROOT/'data/life_support.toml').read_text())
    rate = {r['id']: r['value'] for r in life['rate']}
    per = (FOOD[food][0]*ration*(1-garden_calories)+rate['WATER_TURNOVER']*(1-recovery)+rate['O2']*18/16
           + RATES['hygiene_clothing'][1]+RATES['medical'][1]+RATES['eclss_expendables'][1])
    return (loaded_kg_crew-people*RESERVE_D*RESERVE_KG)/(people*per)


def main():
    s = spec.load()[0]; life = tomllib.loads((ROOT/'data/life_support.toml').read_text())
    budget = {i['id']: i['mass_kg'] for i in s['physics']['mass_budget']['items']}
    # ---- destinations
    dest = []
    for id_, name, D, ops, why in DESTINATIONS:
        rows = {}
        for vf in (0.016, 0.008, 0.004):
            k = kinematics(D, vf)
            dv = 4*k['v_peak_c']*C
            prop, ve, prop_full = propellant(s, dv)
            total = 2*k['one_way_d']+ops+30
            rows[f'{vf:g} c'] = dict(**k, constant_velocity_one_way_d=D*AU/(vf*C)/DAY, mission_d=total, mission_yr=total/365.25,
                                    propellant_t=prop/1e3, propellant_vs_full_return=prop/prop_full)
        dest.append(dict(id=id_, name=name, one_way_AU=D, ops_d=ops, purpose=why, speeds=rows))
    # ---- reach per provisioning profile at 0.016 c
    k = kinematics(1e6)
    reach = {n: dict(years=y, max_one_way_AU=k['ramp_AU']*2+(max(0.0, (y*365.25-30-60)/2-2*k['ramp_d']))*k['v_peak_c']*C*DAY/AU,
                     note='30 d departure/return margin and 60 d destination operations')
             for n, y in PROFILES}
    # ---- provisioning matrix
    prov = {}
    for n, y in PROFILES:
        d = round(y*365.25)
        prov[n] = {f'{p} crew': {f: provisioning(p, d, f, life=life) for f in FOOD} for p in (6, 12)}
    allowance = budget['food_consumables']/1e3
    fit = {}
    for f in FOOD:
        for p in (6, 12):
            # longest mission whose crew consumables (food, makeup water, O2 water, provisions, reserve) fit the 10 t line
            lo, hi = 1, 4000
            while hi-lo > 1:
                mid = (lo+hi)//2
                (lo, hi) = (mid, hi) if provisioning(p, mid, f, life=life)['crew_consumables_kg'] <= allowance*1e3 else (lo, mid)
            fit[f'{p} crew, {f}'] = dict(days=lo, months=lo/30.44)
    # food-only fit (the 10 t line read as food alone)
    food_only = {f'{p} crew, {f}': (allowance*1e3-p*RESERVE_D*1.0)/(p*FOOD[f][0]) for f in FOOD for p in (6, 12)}
    # ---- modular logistics: containers per profile, against 54
    logistics = {n: {c: dict(t=v['total_kg']/1e3, containers=v['containers'], share_of_54=v['containers']/CONTAINER['count'])
                     for c, v in ((f'{p} crew {f}', prov[n][f'{p} crew'][f]) for p in (6, 12) for f in ('conventional', 'dehydrated'))}
                 for n in prov}
    # ---- narrative: six people on a 12-person, 12-month standard load (conventional food)
    std = provisioning(12, 365, 'conventional', life=life)
    load = std['crew_consumables_kg']
    story = {
        'six crew, same rations': endurance(6, load, life=life),
        'six crew, 80 % rations': endurance(6, load, ration=0.8, life=life),
        'six crew, 80 % rations, 99 % water recovery': endurance(6, load, ration=0.8, recovery=0.99, life=life),
        'six crew, 80 % rations, 99 %, Garden 25 % of calories (UNCREDITED sensitivity)': endurance(6, load, ration=0.8, recovery=0.99, garden_calories=0.25, life=life),
        'six crew, 80 % rations, 99 %, Garden 50 % (UNCREDITED, needs a dedicated ring sector)': endurance(6, load, ration=0.8, recovery=0.99, garden_calories=0.5, life=life),
    }
    big = provisioning(12, round(3*365.25), 'conventional', life=life)['crew_consumables_kg']
    story['six crew on a 36-month 12-crew load, same rations'] = endurance(6, big, life=life)
    story['six crew on a 36-month 12-crew load, 80 % rations, 99 %'] = endurance(6, big, ration=0.8, recovery=0.99, life=life)
    story = {k: dict(days=v, years=v/365.25) for k, v in story.items()}
    need6 = provisioning(6, round(6*365.25), 'conventional', life=life)
    # ---- service life
    life_h = {f'{y} yr': y*8766 for y in (10, 15, 20)}
    service = [
        dict(system='L2 fission cores', basis='space reactor design life 7-15 full-power years (SP-100 7 yr; Kilopower-class 10-15)',
             answer='replace the reactor module (ORU) between missions; modular L2 makes this a module swap, not a ship rebuild'),
        dict(system='Brayton turbo-alternators', basis='gas-foil bearings 40,000-100,000 h demonstrated in ground tests', answer='one overhaul in 10 yr, two in 20 yr'),
        dict(system='Main battery', basis='calendar fade 0.5-2 %/yr (power.loads.storage)', answer='replace at 10 yr; sized at end of life'),
        dict(system='ECLSS hardware', basis='ISS ECLSS > 15 yr with ORU replacement', answer='12-person machinery, ORU spares per mission'),
        dict(system='Cryocoolers', basis='space Stirling/pulse-tube > 10 yr continuous', answer='N+1 trains, swap between missions'),
        dict(system='Radiator blades', basis='micrometeoroid and dust erosion per mission (lab dust study)', answer='inspect and resurface between missions'),
        dict(system='Structure', basis='fatigue from burns (4 per mission at up to 1.5 g) and spin', answer='20 yr / ~10-20 missions credible with inspection'),
        dict(system='Propellant', basis='full-return load per mission', answer='refuel at the home station between missions'),
    ]
    params = [
        ('max_design_occupancy', 12, 'engineering requirement (working)', 'crew.rated_occupancy'),
        ('mission_occupancy', '6-12 per mission', 'mission plan', 'new parameter'),
        ('nominal_mission_duration', '12 months (proposal)', 'mission plan', 'replaces the narrative 6 yr as the provisioning basis'),
        ('extended_mission_duration', '24-36 months via logistics modules', 'mission plan', 'new'),
        ('loaded_consumables', 'per mission, in dry-store containers', 'cargo', 'new'),
        ('autonomous_endurance', 'loaded consumables + reserve', 'derived', 'new'),
        ('emergency_endurance', '30 d for 12 (DR-05)', 'requirement (preliminary)', 'survival reserve'),
        ('equipment_lifetime', 'per system (service table)', 'design', 'new'),
        ('service_lifetime', '10-20 yr candidate', 'design', 'new'),
        ('narrative_duration', '~6 yr, 6 people', 'story', 'mission.duration (LOCKED in data; not changed here)'),
    ]
    # ---- L2 reliability against mission length (no in-flight reactor repair; N+1 = 4 units, 3 needed for the must-keep set)
    def p_lose(n, need, u, y):
        q = 1-math.exp(-u*y); return 1-sum(math.comb(n, k_)*q**k_*(1-q)**(n-k_) for k_ in range(n-need+1))
    rel = {n: {f'u={u}': dict(C_lean_3_of_4=p_lose(4, 3, u, y), C2_5_of_6=p_lose(6, 5, u, y), B_1_of_2=p_lose(2, 1, u, y))
               for u in (0.02, 0.05, 0.10)} for n, y in PROFILES}
    res = dict(l2_reliability=rel, status='ISSA Phase II STUDY (NONCANON)', clarification='owner 2026-11-27: six years is a narrative scenario, not a provisioning requirement',
               parameters=[dict(name=a, value=b, kind=c, note=d) for a, b, c, d in params],
               kinematics_check=kinematics(1e6), destinations=dest, reach=reach, provisioning=prov, allowance_t=allowance,
               fits_10t=fit, food_only_days_10t=food_only, logistics=logistics, container=CONTAINER, narrative=story,
               narrative_need_6x6yr=dict(t=need6['total_kg']/1e3, crew_t=need6['crew_consumables_kg']/1e3, containers=need6['containers']),
               standard_load=dict(t=std['total_kg']/1e3, crew_t=load/1e3, containers=std['containers']),
               service_life=dict(hours=life_h, systems=service),
               rates=dict(per_person_day=RATES, food=FOOD, spares_t_per_yr=SPARES_T_PER_YR, reserve_d=RESERVE_D))
    (OUT/'phase2_mission.json').write_text(json.dumps(res, indent=1))
    print('ramp check', {k_: round(v, 3) for k_, v in kinematics(1e6).items()})
    for d in dest:
        r = d['speeds']['0.016 c']; r8 = d['speeds']['0.004 c']
        print(f"{d['name'][:42]:42s} {d['one_way_AU']:6.0f} AU  0.016c: one-way {r['one_way_d']:6.1f} d (const-v {r['constant_velocity_one_way_d']:6.1f}), mission {r['mission_yr']:5.2f} yr, prop {r['propellant_t']:5.0f} t | 0.004c: {r8['mission_yr']:5.2f} yr, prop {r8['propellant_t']:4.0f} t")
    for n, v in reach.items():
        print(f'{n:26s} reach {v["max_one_way_AU"]:6.0f} AU')
    for n, v in prov.items():
        print(n, {c: {f: round(x['total_kg']/1e3, 1) for f, x in v[c].items()} for c in v})
    print('fits 10 t', {k_: round(v['months'], 1) for k_, v in fit.items()})
    print('food only', {k_: round(v/30.44, 1) for k_, v in food_only.items()})
    print('standard load', res['standard_load'], 'story', {k_: round(v['years'], 2) for k_, v in story.items()}, 'need 6x6', res['narrative_need_6x6yr'])
    print('rel', {n: {k_: round(v['C_lean_3_of_4'], 4) for k_, v in r.items()} for n, r in rel.items()})
    print('logistics 12 mo', logistics['12 months standard'])


if __name__ == '__main__':
    main()
