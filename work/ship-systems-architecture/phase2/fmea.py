"""ISSA Phase II, extended FMEA: the twelve brief scenarios against the EPS-A load model and the Gate 2-4 studies. STUDY (NONCANON).
Writes ../results/phase2_fmea.json. Times come from references/p1_power_loads.json and results/phase2_*.json; nothing is credited to
redundancy that a shared dependency defeats.

    python3 work/ship-systems-architecture/phase2/fmea.py      (after power_loads, eps_b.py, eclss_mass.py, placement.py)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parents[1]/'results'


def h(x):
    return f'{x:.2g} h' if x < 48 else f'{x/24:.2g} d'


def main():
    pl = json.loads((ROOT/'references/p1_power_loads.json').read_text())
    eb = json.loads((R/'phase2_eps_b.json').read_text())
    end = pl['storage']['endurance']; cryo = eb['cryo']; tr = eb['transitions']
    rt = lambda sid: end[sid]['ride_through_h'][1]
    wb = lambda sid: end[sid]['whole_battery_h'][1]
    hold = min(cryo['sealed_hold_h'])
    S = []

    def add(id_, name, immediate, independent, shed, keep, time, recovery, common, uncertainty, crew, ship):
        S.append(dict(id=id_, scenario=name, immediate=immediate, independent_resources=independent, sheddable=shed, must_keep=keep,
                      time_to_irreversible=time, recovery=recovery, common_mode=common, uncertainty=uncertainty,
                      crew_survival=crew, ship_and_mission=ship))
    add('F01', 'One generating plant lost (C-lean 3+1)',
        'Running set drops from 3 to 2 units (3.5 MWe); load above it rides on the battery for minutes.',
        ['standby unit (warm start hours, cold start a day)', 'main battery ride-through ' + h(rt('COAST_HV_PROACTIVE'))],
        ['hotel non-essentials', 'MRO workshop', 'Garden lighting (hours)'], ['ECLSS', 'cryocoolers', 'nav/comms', 'proactive defense at high velocity'],
        f'none while 2 units carry the mission core (0.68 MW nominal); proactive defense stays only if 2 units cover 3.3 MW',
        'start the standby unit; replace or repair the failed unit by ORU (power conversion) or retire it (reactor)',
        ['shared coolant header per blade', 'shared bus if the two units sit on one bus'],
        'unit failure rate u = 0.02-0.10 per unit-year assumed; real Brayton/reactor reliability unknown',
        'SAFE', 'SAFE with N+1; B (2 x 100 %) loses its redundancy at once')
    add('F02', 'All continuous generating plants lost',
        'L2 gone. Battery carries the coast load for ' + h(rt('COAST_HV_PROACTIVE')) + ' before touching the black-start reserve.',
        ['main battery (ride-through, then black-start reserve)', 'L3 survival source (crew + nav/comms)', 'L1 drive generators only with the drive lit'],
        ['proactive defense', 'field', 'hotel', 'Garden', 'MRO'], ['crew ECLSS (L3)', 'nav/comms beacon'],
        f'cryo: sealed He-3 hold ~{hold:.0f} h, then ~{cryo["loss_after_hold_t_per_day"]["helium_3"]:.0f} t/day of He-3 boils off; '
        'protection at high velocity: lost at once',
        'restart one L2 unit from the battery black-start reserve; if no unit restarts, the mission ends (drive propellant cannot be kept)',
        ['common fuel/design fault across identical units', 'shared heat-rejection channels', 'control software'],
        'whether identical modules share a design-level failure mode',
        f'SAFE for 30 d on L3 (crew-only {eb["L3"]["scenarios"]["1 crew only"]["P_W"][1]/1e3:.0f} kW nominal)',
        'LOST after the cryo hold unless one unit restarts: cryo preservation is an L2 job, not an L3 job')
    add('F03', 'Main drive trip during high-power operation',
        'L1 lost with hot blades and drained warm channels: burn heat pumps stop; active defense loses its supply.',
        ['WARM section (5 MW) frees up for L2 at reduced power (~1.0-1.3 MWe)', 'defense buffer (if fitted)', 'main battery'],
        ['active defense to proactive', 'MRO', 'hotel'], ['ECLSS', 'cryo', 'nav', 'drive cool-down pumps'],
        f'decay heat {tr["burn_decay_heat_W"]["60"]/1e3:.0f} kW at 60 s, {tr["burn_decay_heat_W"]["3600"]/1e3:.0f} kW at 1 h: hot loop must keep circulating; '
        'proactive defense (2.5 MW) cannot be held until the channels refill',
        'refill and re-prime warm channels, restart L2 from hot standby, then diagnose the drive',
        ['drive and L1 share the aft district (DRIVE_AFT)', 'hot-loop pumps on L1'],
        'drive standby and restart energy are OPEN (PROP.DRIVE_STANDBY)', 'SAFE', 'DEGRADED: protection gap during the burn-to-coast transition')
    add('F04', 'Loss of one electrical bus (A or B)',
        'Half the distribution lost; loads dual-fed from A and B transfer.',
        ['other bus', 'bus E for essentials'], ['non-dual-fed loads on the lost bus'], ['dual-fed ECLSS, cryo trains, nav'],
        'none if essential loads are dual-fed and each bus carries the must-keep set (3.3 MW nominal)',
        'isolate the fault, repair the switchgear ORU',
        ['bus trunks in the same keel lane (Phase I rule: never)', 'shared PMAD cold plates on LOW'],
        'bus capacity sizing; protection coordination', 'SAFE', 'SAFE if each bus is rated for the must-keep set')
    add('F05', 'Failure of the emergency bus (E)',
        'Essential loads lose their independent feed; they still run from A/B.',
        ['A/B feeds', 'L3 source can be cross-tied to A'], ['none'], ['ECLSS, refuge, nav beacon'],
        'none while A/B run; it becomes critical only in a coincident F02',
        'repair E; until then F02 becomes crew-critical',
        ['E routed with A or B', 'L3 source location beside the refuge'], 'E bus topology not designed', 'SAFE (latent)', 'SAFE (latent)')
    add('F06', 'Loss of one coolant circuit',
        'One blade warm circuit lost: the L2 units on that blade lose their sink; ECLSS loops on that ring go to the other.',
        ['other two blades (each carries ~1/3 of the warm area)', 'ring loops cross-connect'],
        ['L2 units on the lost blade', 'Garden lighting'], ['crew loops', 'cryocooler heat rejection (LOW)'],
        'ring: hours (cabin heat-up); cryo: depends on the LOW section (1 MW, already above capacity in the active bound)',
        'isolate the leak, refill from coolant spares, restart the units',
        ['shared header across blades (design must split it)', 'one LOW section for all cryocoolers'],
        'coolant inventory and leak rates OPEN', 'SAFE', 'DEGRADED: one third of L2 capacity')
    add('F07', 'Heat-pump failure',
        'In a burn, warm heat beyond the 5 MW WARM section has no sink.',
        ['WARM section (5 MW)', 'Heat Debt buffer (TMS-06, OPEN)'], ['active defense to proactive', 'MRO'], ['ECLSS, cryo'],
        'seconds to minutes for active defense heat; the base load fits the WARM section',
        'shed defense to proactive within the buffer, restart pumps', ['pumps on L1 (drive trip takes both)'],
        'pump unit size and spares', 'SAFE', 'DEGRADED: active defense not available in burns')
    add('F08', 'Cryogenic cooling failure',
        'Tanks warm; He-3 at 3 K is the critical stage.',
        ['N+1 cryocooler trains on A and B', 'sealed hold'], ['20 K stage before 3 K (it cannot: 3 K cannot lift the shield load)'], ['3 K He-3 stage'],
        f'~{hold:.0f} h sealed hold; losing only the 3 K stage costs {cryo["lose_3K_stage_only_t_per_day"]:.1f} t/day He-3',
        cryo['recovery'], ['LOW section 300 K rejection', 'both trains on one bus'], 'tank insulation performance over six years',
        'SAFE', 'MISSION-CRITICAL: He-3 losses end the braking budget')
    add('F09', 'Repeated active-defense engagements',
        'Buffer drawn per engagement; recharge from the L2 margin; heat debt accumulates.',
        ['dedicated defense buffer (not the pulse bank)', 'L2 margin above the proactive load'], ['MRO', 'Garden lighting', 'hotel'],
        ['proactive defense', 'ECLSS', 'cryo'],
        'when the recharge time exceeds the interval between engagements the buffer runs down: see the duty sweep (eps_b duty)',
        'reduce engagement duration or accept the continuous-active bound (25.8 MW design, 939 t class)',
        ['buffer and L2 margin are the same generators'], 'engagement frequency is OPEN (dust environment, detection range)',
        'SAFE', 'DEGRADED or LOST protection above the sustainable duty')
    add('F10', 'Loss of a generator during high-velocity coast',
        'As F01 but proactive defense is mandatory at this velocity.',
        ['standby unit', 'battery (' + h(rt('COAST_HV_PROACTIVE')) + ')', 'defense buffer'], ['hotel', 'MRO', 'Garden'], ['proactive defense', 'ECLSS', 'cryo'],
        'protection gap if the remaining units cannot cover 3.3 MW; a dust strike in the gap is the irreversible event',
        'start the standby unit; with B-lean (2 x 3.64) one loss leaves 3.64 MW, at the edge of the must-keep set',
        ['same as F01'], 'dust flux at 0.016 c (lab dust study uses the Vertex profile)', 'SAFE', 'AT RISK during the gap')
    add('F11', 'Exhaustion of available emergency energy',
        'Ride-through spent; the black-start reserve is protected and is not spent on loads.',
        ['L3 source', 'black-start reserve (restart only)'], ['everything except crew-only'], ['crew ECLSS on L3', 'nav beacon'],
        f'crew-only on the battery ride-through: {h(rt("SURVIVAL_CREW"))}; whole battery {h(wb("SURVIVAL_CREW"))}; L3 adds 30 d',
        'restart L2 from the reserve; if not, L3 for 30 d awaiting repair',
        ['battery shared by ride-through and reserve (one pack)'], 'battery degradation (0.5-2 %/yr) at end of life', 'SAFE for 30 d', 'LOST without an L2 restart')
    add('F12', 'Complete blackout and black start',
        'All buses dark; L3 keeps crew-only loads; the reserve restarts in steps (pulse bank charged from the main battery).',
        ['black-start reserve ' + f'{pl["storage"]["black_start_reserve_J"]/3.6e6:,.0f} kWh', 'L3 source', 'refuge packs'],
        ['all but restart loads'], ['restart services ' + f'{pl["storage"]["black_start_services_W"][1]/1e3:.0f} kW nominal', 'crew ECLSS'],
        f'cryo hold ~{hold:.0f} h sets the deadline for an L2 restart',
        'step sequence of power.black_start; the survival reserve never charges the pulse bank or restarts the drive',
        ['restart depends on one battery pack and one control path'], 'restart energy of an L2 unit and its start time',
        'SAFE', 'SAFE if an L2 unit restarts inside the cryo hold')
    res = dict(status='ISSA Phase II STUDY (NONCANON)', scenarios=S,
               summary=dict(crew='The crew survives every scenario for 30 d on L3 plus the refuge, provided the L3 source is independent of L2 and E.',
                            ship='The ship and mission depend on L2 restarting within the ~58-77 h cryo hold and on the protection gap at high '
                                 'velocity; both need N+1 modular L2 with units on different blades and buses.',
                            not_credited='Redundancy is not credited across identical units for a design-level fault, across units sharing a blade '
                                         'header, or between L1 and the drive.'))
    (R/'phase2_fmea.json').write_text(json.dumps(res, indent=1))
    for s in S:
        print(s['id'], s['scenario'][:46].ljust(46), '|', s['crew_survival'][:28].ljust(28), '|', s['ship_and_mission'][:60])


if __name__ == '__main__':
    main()
