"""T00 Phase 4 (2026-11-09): fold the T01-T04 and T06 registry proposals into registry/*.toml, once.

  python3 lab/variants/vertex-drive/planning/integrate_phase4.py      # rewrites registry/*.toml from the 8de3ffa registry + proposals

Kept as the provenance of the integration: every final ID, every normalisation and every correction T00 made to a proposal is in this
file (see RECONCILIATION.md for why). It starts from the Phase 1 base registry (git show 8de3ffa:...), so running it twice gives the
same result. After it runs, registry/*.toml is the source again and this script is not needed by atlas.py or convergence.py.

Rules applied: provisional IDs get the next free letter in their workstream (never renumbered); prior_finding, limitations and
uncertainties are appended to, never replaced; a source cited from abstracts or snippets is never better than SECONDARY_VERIFIED, and
UNVERIFIED where the thread's own handoff says so; numbers keep their unit and basis; owner rulings are recorded with their date.
"""
import copy
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATLAS = HERE.parent
ROOT = ATLAS.parents[2]
REG = ATLAS / 'registry'
ST = ATLAS / 'studies'
BASE = '8de3ffa'
DATE = '2026-11-09'

FINAL = {'T04-NEW-1': 'VTX-01E', 'T04-NEW-2': 'VTX-01F', 'T04-NEW-3': 'VTX-01G', 'T01-NEW-1': 'VTX-01H', 'T04-NEW-4': 'VTX-01H',
         'T04-NEW-5': 'VTX-01I', 'T06-NEW-2': 'VTX-02D', 'T03-NEW-1': 'VTX-03D', 'T02-NEW-3': 'VTX-03E', 'T02-NEW-4': 'VTX-03F',
         'T01-NEW-2': 'VTX-07E', 'T06-NEW-1': 'VTX-07F', 'T02-NEW-1': 'VTX-08E', 'T02-NEW-2': 'VTX-08F'}
DEC = {'D-T01-1': 'D-13', 'D-T01-2': 'D-14', 'D-T02-1': 'D-15', 'D-T02-2': 'D-16', 'D-T02-3': 'D-17', 'D-T02-4': 'D-18',
       'D-T03-1': 'D-19', 'D-T03-2': 'D-20', 'D-T03-3': 'D-21', 'D-T04-1': 'D-22', 'D-T06-1': 'D-22', 'D-T04-2': 'D-23',
       'D-T06-2': 'D-24', 'D-T06-3': 'D-25'}
KIND = {'paper': 'journal', 'experiment': 'journal'}          # T03 kinds mapped onto the register's kinds
VERIFY_DOWN = {'S-T06-NIF-DENSITY': 'UNVERIFIED', 'S-T06-CNTF-2024': 'UNVERIFIED'}   # T06 handoff: "UNVERIFIED snippet"
MODEL_SOURCES = {'S-T01-LEDGER', 'S-T02-STUDY'}               # reproduced byte for byte by T00 (MERGE_READINESS.md)


def base_toml(name):
    txt = subprocess.run(['git', 'show', f'{BASE}:lab/variants/vertex-drive/registry/{name}'], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    return tomllib.loads(txt), txt


def prop(folder):
    with open(ST / folder / 'registry_proposal.toml', 'rb') as f:
        return tomllib.load(f)


def fid(x):
    return FINAL.get(x, x)


def append(t, key, text):
    old = t.get(key, '')
    t[key] = (old + ' | ' if old else '') + text


# ----------------------------------------------------------------------------------------------------------------------------------
# new technology records: proposal fields first, T00 completions where the proposal left a required field out
# ----------------------------------------------------------------------------------------------------------------------------------

def stage(present, advanced, era):
    return {'present': present, 'advanced': advanced, 'wayfarer_era': era}


def qs(a, b, c):
    return {'a': a, 'b': b, 'c': c}


def geom(status, rep, colour, components=(), envelope='', location='', connections='', loads='', radiation='', thermal='',
         maintenance='', purposes=()):
    return {'components': list(components), 'envelope': envelope or 'none', 'location': location or 'none',
            'connections': connections or 'none', 'loads': loads or 'none', 'radiation': radiation or 'none', 'thermal': thermal or 'none',
            'maintenance': maintenance or 'none', 'purposes': list(purposes), 'colour': colour, 'representation': rep, 'status': status}


def prio(f, c, i, m, u, d):
    return {'feasibility': f, 'credibility': c, 'independence': i, 'mass_thermal': m, 'unlock': u, 'design_3d': d}


COMPLETE = {
    'VTX-01E': dict(
        ancestry_note='Atzeni and Meyer-ter-Vehn: the minimum energy to compress fuel is its Fermi-degenerate energy times the adiabat; '
                      'FDP-1 supplies the pulse and burn-fraction model the ceiling is evaluated in.',
        limitations='0-D bound: no burn propagation, no hydrodynamic efficiency model; the ignitor term rests on a 3.5x dynamics factor '
                    'calibrated on D-T fast ignition (EXTRAPOLATION). Present ablative couplings are in the percent range (UNKNOWN as a number).',
        breakthrough='A driver-to-fuel compression coupling eta_c/alpha of about 0.5 (the 2026-11-09 research target, D-22), against a '
                     'percent-range coupling today. Not declared as IGNITION physics.',
        depends_on=['VTX-01'], materials=[], purposes=['P03'],
        inputs='Driver energy per pulse, coupling eta_c/alpha, compressed density, burn fraction.',
        outputs='The largest gain a target of that density can have: G <= eta_c b eps / (alpha eps_F + ignitor).',
        penalties='Lower density at fixed coupling gives larger, slower pulses: bigger X-ray stand-off and loops, longer injection path.',
        criteria='Gain at or below the ceiling; coupling needed (convergence.json consistency) at or below the declared value.',
        evidence=['S-T04-ATZENI-2004', 'S-FDP1'], uncertainties='Achievable coupling for heavy-ion direct drive of fuel-only D-3He; ignitor energy.',
        next=['1-D radiation-hydrodynamic burn of a fast-ignited, D-T-cored D-3He sphere at 1,000 and 3,000 g/cm3 (T04 J)'],
        stages=stage('Percent-range coupling in ablative implosions (engineering judgment, T04).', 'Coupling 0.2-0.3 by shaped heavy-ion direct drive.',
                     'Coupling about 0.5 at 1,000-2,000 g/cm3 (research target).'),
        questions=qs('No.', 'Plausibly, at a coupling far above today\'s.', 'Yes: it is what makes any Vertex mass energy-consistent.'),
        geometry=geom('NONE', 'NONE', 'MAIN_PROPULSION'), priority=prio(4, 3, 3, 5, 5, 1)),
    'VTX-01F': dict(
        ancestry_note='Spin-polarised fuel raises the D-3He cross-section up to 1.5x (UNVERIFIED review); Nakao gives the D-3He target context.',
        limitations='Survival of polarisation through compression is unknown; polarised He-3 at target scale is unproven.',
        breakthrough='Polarisation kept through a 1,000-fold compression.', depends_on=['VTX-01'], materials=[], purposes=['P03'],
        inputs='Polarised D and He-3 at target scale.', outputs='H_B 44.2 -> 29.5 g/cm2; fuel rhoR for the mission ve 90 -> 60 g/cm2.',
        penalties='Polariser plant mass and power (UNKNOWN).', criteria='Reactivity gain measured in a compressed target.',
        evidence=['S-T04-POLARISED'], uncertainties='All of it beyond the cross-section factor.',
        next=['Literature check of depolarisation in implosions'],
        stages=stage('Polarised He-3 for medical imaging and polarised targets in nuclear physics.', 'Polarised fuel in a laboratory implosion.',
                     'Polarised cryogenic targets made in the factory.'),
        questions=qs('No.', 'Unknown.', 'Modest: about 9 % on V1 departure (T04).'),
        geometry=geom('NONE', 'NONE', 'MAIN_PROPULSION'), priority=prio(3, 2, 3, 2, 2, 1)),
    'VTX-01G': dict(
        ancestry_note='Nakao: D-3He pellets with a D-T ignitor; Atzeni: fast-ignition energy scaling and the 0.6 g/cm2 optimum hot spot.',
        limitations='Burn propagation from a D-T core into D-3He at 1,000-3,000 g/cm3 is unmodelled; pre-ignition (Nakashima 1993, gain 3).',
        breakthrough='Propagating burn from the D-T core into the D-3He fuel at the needed density.', depends_on=['VTX-01D'], materials=[],
        purposes=['P03'], inputs='Tritium 43-144 kg loaded per mission (rhoR_DT 2-3 g/cm2); a separate fast ignitor beam.',
        outputs='Ignition of the main fuel at a 0.3-1.3 MJ D-T core.', penalties='Tritium logistics and decay (27 % over the burn); an ignitor beam line.',
        criteria='Burn fraction against b = rhoR/(rhoR + H_B) and yield per ignitor energy (1-D burn code).',
        evidence=['S-T04-NAKAO-1992', 'S-T04-ATZENI-CIAMPI-1997', 'S-T04-ATZENI-1999'],
        uncertainties='Burn propagation; ignitor coupling (0.2 ASSUMPTION).', next=['1-D burn calculation (T04 J)'],
        stages=stage('D-T fast-ignition studies.', 'Fast-ignited D-T-cored targets in a pulsed facility.', 'D-T-cored D-3He targets made per pulse.'),
        questions=qs('No.', 'Plausibly: the most credible ignition route found.', 'Yes, if the mission carries about 0.1 t of tritium.'),
        geometry=geom('PARAMETRIC_PLACEHOLDER', 'HARDWARE', 'MAIN_PROPULSION', ['fast-ignitor beam line', 'tritium store in the equipment module'],
                      'Ignitor beam on the bore axis beside the target path; tritium store volume UNKNOWN.', 'Equipment module, bore axis.',
                      'VTX-01B, VTX-01H.', 'none', 'Behind the shadow shield.', 'Warm loop.', 'Tritium handling.', ['P03']),
        priority=prio(4, 3, 3, 3, 4, 2)),
    'VTX-01H': dict(
        ancestry=['S-GA-TARGET', 'S-T01-LEDGER'],
        ancestry_note='T01 and T04 found the same constraint independently: at FDP-1\'s 400 m/s, 12.5-25 targets are in the burn\'s sky and '
                      'the next one receives 1-6 kJ of X-rays per pulse; GA target-injection work is the starting point for fast injectors.',
        limitations='No target launcher at 6 km/s or above exists for cryogenic D2/He-3 targets; a sabot must be stopped behind the shield. '
                    'Under the compression-consistent gain the pulses are larger and the path longer, so V4 needs at least 12 km/s (convergence V4_launcher_sweep).',
        breakthrough='A 12-15 km/s cryogenic target launcher at 100-200 Hz, or a shielded flight path, or targets that survive the previous pulse.',
        depends_on=['VTX-01C'], materials=[], purposes=['P03'],
        inputs='Launcher energy 0.02-0.25 MJ per target; acceleration about 1e5-1e6 g.',
        outputs='One target in the open per pulse period: f <= v / path.',
        criteria='Launcher speed at or above path x rate; target survival of the launch.',
        evidence=['S-T01-LEDGER', 'S-T04-ATZENI-2004'],
        uncertainties='Target survival at 1e5-1e6 g; alternative shielded paths (T03 field sheltering not modelled).',
        next=['Launcher threshold on the corrected generations (done: V4 needs >= 12 km/s)', 'Shielded flight path concept'],
        stages=stage('Gas-gun target injection at about 400 m/s (IFE designs).', 'Electromagnetic launch of cryogenic targets at km/s.',
                     'Fast launchers or shuttered paths on the bore axis.'),
        questions=qs('No.', 'Plausibly, at a few km/s; 12-15 km/s for cryogenic targets is unproven.', 'Yes: without it the pulse rate falls and the ship grows or does not close.'),
        geometry=geom('PARAMETRIC_PLACEHOLDER', 'HARDWARE', 'MAIN_PROPULSION', ['target launcher barrel on the bore axis', 'sabot catcher behind the shield'],
                      'Muzzle at the shield face; path to the burn 46.6 m (V0) to 68-83 m (V4).', 'Bore axis, equipment module.', 'VTX-01C, VTX-01B.',
                      'Launch recoil.', 'Muzzle inside the shadow cone.', 'Warm loop.', 'Barrel and catcher replacement.', ['P03']),
        priority=prio(5, 3, 3, 4, 5, 4)),
    'VTX-01I': dict(
        ancestry_note='Energy-ledger only, from the compression-energy bound (Atzeni and Meyer-ter-Vehn).',
        limitations='26-52 t of tritium per mission; 0.2-0.45 % of fusion as 14.1 MeV neutrons outside the main fuel; unmodelled case mass.',
        breakthrough='none (rejected)', depends_on=['VTX-01'], materials=[], purposes=['P03'], inputs='A D-T primary per pulse.',
        outputs='Removes the compression ceiling in the ledger.', penalties='Tritium and neutron cost (see limitations).',
        criteria='Tritium per mission and escaping neutron share.', evidence=['S-T04-ATZENI-2004'],
        uncertainties='Case mass; stage coupling.', next=['none: kept as a negative result'],
        stages=stage('Two-stage concepts on paper.', 'not pursued', 'not pursued'),
        questions=qs('No.', 'Possible but not practical.', 'No.'), geometry=geom('NONE', 'NONE', 'MAIN_PROPULSION'), priority=prio(1, 2, 2, 1, 1, 1)),
    'VTX-02D': dict(
        ancestry_note='Virial theorem for magnet structure (M >= rho W / sigma); dynamic CNT fibre strength up to 14 GPa (UNVERIFIED).',
        materials=['MAT-CFRP'], purposes=['P06', 'P14'], inputs='A 3 GPa laminate at 1.6 t/m3.', outputs='Half the virial nozzle structure and lighter trusses.',
        penalties='Creep under cryogenic and radiation load; joints.', criteria='kg per J stored; laminate allowable stress.',
        prior_finding='T06 2026-11-09: halves the virial nozzle structure; small for the whole ship (chain K5 -9 % on V1c).',
        evidence=['S-T06-CNTF-2024', 'S-FOURBURN'], uncertainties='Translation of fibre strength into a laminate.',
        next=['Coil-pack structure at 15 E_p with fatigue (T03 found a 7-10 % load cycle 1.9e10 times)'],
        questions=qs('No.', 'Plausibly.', 'Yes, but modest.'), priority=prio(4, 3, 4, 3, 2, 3)),
    'VTX-03D': dict(
        name='Forward closure coils on the X-ray stand-off sphere', kind='technology', workstream='VTX-03',
        purpose='Close the axial leak of the three-loop magnetic cup so the pulse plasma turns aft instead of escaping forward onto the shield.',
        principle='Two coaxial coils at polar 20 and 40 deg on the stand-off sphere; with optimised currents the vacuum-field thin-shell model gives '
                  'eta_mom 0.86-0.89 (eta_T 0.74-0.79) at 10-15 E_p of stored field and a forward leak of 0.15-0.3 % (A: 22 %).',
        ancestry=['S-MSFC-NOZZLE', 'S-T03-NAGAMINE-1999', 'S-CASSIBRY-PMN'],
        ancestry_note='Thio et al. (1999) momentum efficiency 0.80 (max 0.863); simulations 0.55-0.70; T03 vacuum-field model adds the closure.',
        limitations='Vacuum fields, elastic specular shell, no instabilities, no velocity spread, no detachment: an UPPER BOUND. Rayleigh-Taylor '
                    'grows 13-14 e-folds per pulse in linear theory. Envelope solid angle 0.040-0.051 against 0.017 (V1), not booked in the calculator.',
        breakthrough='A self-consistent pulsed-plasma simulation showing eta_T >= 0.70 with <= 2 % of plasma on hardware (D-21 campaign).',
        depends_on=['VTX-03'], materials=['MAT-REBCO', 'MAT-CFRP'], purposes=['P05', 'P06'],
        inputs='C1 80-132 MA, hoop tension 3-7 GN; stored field 10-15 E_p (0.8-1.2 TJ).', outputs='eta_T 0.74-0.79 (ideal model).',
        penalties='Coil structure 855-1,281 t (virial); solid angle x2.4-3.0 on radiation to hardware; 0.2-1.9 GN inter-coil forces; trim 3-5 TW for 1 % in 5 ms.',
        criteria='eta_T and plasma on hardware from a 2D Hall-MHD / hybrid-PIC run (D-21).', credibility='PLAUSIBLE_FUTURE', physics_verdict='UNRESOLVED',
        claims=[{'quantity': 'nozzle_thrust_efficiency_ideal_15Ep', 'value': 0.791, 'unit': '1', 'basis': 'MODEL', 'source': 'results/nozzle_results.json C_W15',
                 'range': '0.74-0.79 (10-15 E_p), vacuum-field upper bound'},
                {'quantity': 'hardware_solid_angle_closure', 'value': 0.051, 'unit': 'sr/4pi', 'basis': 'MODEL', 'source': 'results/nozzle_results.json C_W15',
                 'range': '0.040-0.051 (V1: 0.017)'}],
        research_status='UNDER_INVESTIGATION', canon_status='NON_CANON',
        prior_finding='T03 2026-11-09: preferred experimental nozzle (owner 2026-11-09), ideal efficiency not demonstrated. Coupled V1 with C at 15 E_p 22,683 t.',
        evidence=['S-T03-NAGAMINE-1999', 'S-T03-MATSUDA-2009', 'S-MSFC-NOZZLE'],
        uncertainties='Detachment, RT mixing, velocity spread (~0.94 on eta_T, not applied), eddy-screen loss 0.03-1 % of plasma.',
        next=['2D axisymmetric Hall-MHD and hybrid-PIC of the V1 pulse in A and C at 15 E_p (D-21 proposal, not launched)'],
        stages=stage('Pulsed magnetic nozzles in laboratory experiments (impulse only).', 'Shaped pulsed nozzles validated in 2D simulation.',
                     'Closure-coil nozzle with warm eddy screens.'),
        questions=qs('No.', 'Unresolved: D-21 decides.', 'Yes: the steepest mass lever (elasticity -2.9, T06).'),
        geometry=geom('PARAMETRIC_PLACEHOLDER', 'HARDWARE', 'MAIN_PROPULSION', ['closure coil C1', 'closure coil C2', 'warm eddy screens'],
                      'Nozzle frame x = x_burn + z, x_burn about -227.5 m (V1): C1 r 14.74 m at z +40.51 (envelope r 2-3.2 m), C2 r 27.71 m at z +33.03.',
                      'Forward of the burn on the stand-off sphere, inside the shadow cone.', 'VTX-03, VTX-02B, struts.', '0.2-1.9 GN axial; 3-7 GN hoop.',
                      'Inside the burn\'s sky: armour and screens.', 'Hot loop (plasma on hardware), cryogenic windings.', 'Sector replacement (VTX-03E).',
                      ['P05', 'P06']), priority=prio(5, 3, 3, 5, 5, 5)),
    'VTX-03E': dict(stages=stage('Superconducting magnets are not serviced in space.', 'Robotic exchange of magnet sectors on large structures.',
                                 'Six separable sectors per loop, exchanged between burns.'),
                    priority=prio(4, 3, 3, 3, 4, 4), purposes=['P05', 'P06']),
    'VTX-03F': dict(stages=stage('REBCO degrades from about 1-4e22 n/m2.', 'Unknown.', 'Level C need only if replacement is rejected (D-18).'),
                    priority=prio(1, 1, 2, 3, 3, 1), purposes=['P05']),
    'VTX-07E': dict(
        ancestry=['S-T01-LEDGER', 'S-T01-TFAWS-2024', 'S-T01-HIF-EFF'],
        ancestry_note='T01 split ledger over FDP-1; component temperature limits from SiC, capacitor, core-material and heat-pipe sources.',
        limitations='One equivalent radiator in the calculator; component loss shares are EXTRAPOLATION from the HIF ranking; burn-average only.',
        breakthrough='Induction cores at 640 K and MW power stages at 740 K (TARGET); near-term parts give 489 K and the ship does not close.',
        depends_on=['VTX-07A'], materials=['MAT-SIC'], purposes=['P12', 'P13'],
        inputs='Per-component loss heat and reject temperature.', outputs='Equivalent warm radiator: 628 K, 0.96 kg/m2, 2e-6 kg/W (planning case).',
        penalties='Several loops, pumps and manifolds (booked as transport mass and pumping power).',
        criteria='Booking error below 1e-6; circuit areas per component class.', credibility='PLAUSIBLE_FUTURE', physics_verdict='PLAUSIBLE_FUTURE',
        research_status='SUPPORTED', canon_status='NON_CANON',
        prior_finding='T01 2026-11-09: the 700-800 K single warm loop does not survive booking; the induction cores are about 40 % of the warm area.',
        evidence=['S-T01-LEDGER', 'S-T01-SIC-250C', 'S-T01-CAP-200C', 'S-T01-HITPERM'],
        uncertainties='FeCo nanocrystalline core loss at 600-700 K; sheet emissivity.', next=['Driver loss budget from first principles (T01 J)'],
        stages=stage('Components rated to 423-523 K.', 'Cores at 640 K, power stages at 740 K, capacitors at 550 K (TARGET).',
                     'Separate warm circuits per component class on split wings.'),
        questions=qs('No.', 'Plausibly, at TARGET component temperatures.', 'Yes: it replaces the withdrawn 700-800 K loop with a booked one.'),
        geometry=geom('PARAMETRIC_PLACEHOLDER', 'HARDWARE', 'WARM_RADIATOR', ['warm wing circuit bands (1,000 / 740 / 700 / 640 / 550 K)'],
                      'W2 wings at azimuth 0 and 180 deg, x -178.75 to +88.0 m, root r 10 m; planning tip r 1,088 m, bracket 460-1,688 m.',
                      'Wings on the equipment module.', 'VTX-07A, VTX-07B, VTX-07D.', 'Wing spars.', 'Edge-on to the burn.', 'Warm circuits.',
                      'Panel or sheet replacement.', ['P12', 'P13']), priority=prio(5, 4, 4, 5, 4, 4)),
    'VTX-07F': dict(
        ancestry_note='SP-100 Mo-13Re/Li heat pipes; space waste-heat radiators at 5-8 kg/m2 in practice (both UNVERIFIED).',
        materials=['MAT-MORE', 'MAT-CC'], purposes=['P12', 'P13'], inputs='Lithium heat pipes, thin refractory walls.',
        outputs='Hot panels at 1.5 kg/m2 (half the optimistic tier).', penalties='Creep at 1,800 K; dust puncture.',
        criteria='kg/m2 at 1,800 K with a life allowance.', prior_finding='T06 2026-11-09: saves about 4 % on V1c (chain K2).',
        evidence=['S-T06-SP100', 'S-T06-RADMASS'], uncertainties='Wall thickness under creep and dust.', next=['Creep-limited wall sizing'],
        questions=qs('No.', 'Plausibly: a requirement two to five times beyond published practice.', 'Modest.'), priority=prio(3, 3, 4, 2, 2, 2)),
    'VTX-08E': dict(priority=prio(5, 3, 4, 4, 5, 5)),
    'VTX-08F': dict(stages=stage('Whipple bumpers at 7-10 km/s.', 'Burn-facing bumpers and guard rings sized from accelerator tests.',
                                 'Guard rings forward of loops 2 and 3; local bumpers on every exposed part.'),
                    priority=prio(4, 3, 3, 3, 3, 4)),
}
COLOUR = {'VTX-08E': 'SHIELD', 'VTX-08F': 'SHIELD', 'VTX-03E': 'MAIN_PROPULSION', 'VTX-03F': 'MAIN_PROPULSION'}


def new_records():
    out = []
    t01, t02, t03, t04, t06 = prop('thermal'), prop('dust'), prop('nozzle'), prop('ignition'), prop('futures')
    raw = {}
    for pid, r in t01['new'].items():
        raw[pid] = dict(r, id=pid)
    for r in t02['technology'] + t04['technology'] + t06['technology']:
        raw[r['id']] = dict(r)
    for pid, r in raw.items():                                # claims are normalised against the thread that made them, before merging
        r['claims'] = norm_claims(r.get('claims'), pid[:3])
    for r in t03['technology']:
        raw[r['id']] = {'id': r['id']}
    merged = {}
    for pid, r in raw.items():
        f = fid(pid)
        if f in merged:                                       # T01-NEW-1 and T04-NEW-4 are the same technology: merge
            m = merged[f]
            if not m.get('prior_finding'):
                m['prior_finding'] = f'T01 {DATE}: FDP-1 flies 12.5-25 targets at once; one target in the open per period needs v >= path x rate (T01-NEW-1).'
            append(m, 'prior_finding', f'{pid}: {r.get("prior_finding", r.get("purpose", ""))}')
            m['claims'] = m.get('claims', []) + r.get('claims', [])
            continue
        m = {k: copy.deepcopy(v) for k, v in r.items() if k not in ('handoff', 'parent', 'title', 'summary', 'basis', 'cost', 'status')}
        m['id'] = f
        merged[f] = m
    for f, m in merged.items():
        for k, v in COMPLETE.get(f, {}).items():
            if k not in m or m[k] in ('', None, []) or k in ('purposes',):
                m[k] = copy.deepcopy(v)
        m.setdefault('credibility', 'PLAUSIBLE_FUTURE')
        m.setdefault('physics_verdict', 'PLAUSIBLE_FUTURE')
        m.setdefault('research_status', 'PROPOSED')
        m.setdefault('canon_status', 'NON_CANON')
        m.setdefault('prior_finding', 'New record (T00 Phase 4, 2026-11-09).')
        m.setdefault('ancestry_note', 'See the thread handoff.')
        m['depends_on'] = [fid(d) for d in m.get('depends_on', [])]
        g = m.setdefault('geometry', {})
        for k in ('components', 'purposes'):
            g.setdefault(k, [])
        for k in ('envelope', 'location', 'connections', 'loads', 'radiation', 'thermal', 'maintenance'):
            g.setdefault(k, 'none')
        g.setdefault('colour', COLOUR.get(f, 'MAIN_PROPULSION'))
        if not g.get('colour'):
            g['colour'] = COLOUR.get(f, 'MAIN_PROPULSION')
        g.setdefault('representation', 'NONE')
        g.setdefault('status', 'NONE')
        if f in ('VTX-03E', 'VTX-03F'):                          # T02 tagged loop sectors P03 (injection); they are P05 magnet hardware
            g['purposes'] = ['P05', 'P06']
        if g.get('colour') == 'THERMAL':                        # not a palette name; hot root bands are hot radiator
            g['colour'] = 'HOT_RADIATOR'
        cl = norm_claims(m.get('claims'), THREAD[f])
        m['claims'] = cl
        out.append(m)
    return out


THREAD = {'VTX-01E': 'T04', 'VTX-01F': 'T04', 'VTX-01G': 'T04', 'VTX-01H': 'T01', 'VTX-01I': 'T04', 'VTX-02D': 'T06', 'VTX-03D': 'T03',
          'VTX-03E': 'T02', 'VTX-03F': 'T02', 'VTX-07E': 'T01', 'VTX-07F': 'T06', 'VTX-08E': 'T02', 'VTX-08F': 'T02'}
STUDY_SRC = {'T01': 'S-T01-LEDGER', 'T02': 'S-T02-STUDY', 'T03': 'S-T03-STUDY', 'T04': 'S-T04-STUDY', 'T06': 'S-T06-STUDY'}
BASIS = {'EXTRAPOLATION': 'ASSUMPTION'}                         # the register's four bases; an extrapolated input is an assumption
UNIT = [('_m2', 'm2'), ('_t', 't'), ('_kg', 'kg'), ('_m', 'm'), ('_K', 'K'), ('_Hz', 'Hz'), ('_J', 'J')]


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v, None
    import re
    m = re.match(r'\s*([-+]?[0-9.]+(?:e[-+]?[0-9]+)?)', str(v))
    return float(m.group(1)), str(v)


def norm_claims(raw, who, sources=None):
    """One claim shape for every thread: quantity, number, unit, basis, a registered source and the study case it came from."""
    if not raw:
        return []
    items = [dict(v, quantity=k) for k, v in raw.items()] if isinstance(raw, dict) else [dict(c) for c in raw]
    out = []
    for c in items:
        q = c['quantity'].strip()
        for a, b in ((' ', '_'), ('(', ''), (')', ''), (',', ''), ('%', 'pct'), ('/', '_per_'), ('=', ''), ('.', 'p')):
            q = q.replace(a, b)
        val, rng = _num(c['value'])
        d = {'quantity': q, 'value': val, 'unit': c.get('unit') or next((u for sfx, u in UNIT if q.endswith(sfx)), '1'),
             'basis': BASIS.get(c.get('basis'), c.get('basis')), 'source': c.get('source', '')}
        if rng or c.get('range'):
            d['range'] = rng or c['range']
        case = c.get('case') or c.get('study_case')
        src = d['source']
        if src.startswith('case:') or src.startswith('results/') or src.startswith('REPORT') or not src.startswith('S-'):
            case = src[5:] if src.startswith('case:') else src
            d['source'] = STUDY_SRC[who]
        if case:
            d['study_case'] = case
        out.append(d)
    return out


# ----------------------------------------------------------------------------------------------------------------------------------

def main():
    T, _ = base_toml('technologies.toml'); S, _ = base_toml('sources.toml'); L, _ = base_toml('links.toml'); D, _ = base_toml('decisions.toml')
    techs = T['technology']; byid = {t['id']: t for t in techs}
    t01, t02, t03, t04, t06 = prop('thermal'), prop('dust'), prop('nozzle'), prop('ignition'), prop('futures')

    # sources
    def add_source(sid, s):
        s = {k: v for k, v in s.items() if k not in ('id', 'action')}
        s['kind'] = KIND.get(s.get('kind'), s.get('kind'))
        if sid in VERIFY_DOWN:
            s['verification'] = VERIFY_DOWN[sid]
        if sid in MODEL_SOURCES:
            s['kind'] = 'model'; s['verification'] = 'PRIMARY_VERIFIED'
            s['checked'] = s.get('checked', '') + f' T00 {DATE}: rerun reproduces the committed JSON byte for byte (only timings differ).'
        S[sid] = s
    for sid, s in t01['source'].items():
        add_source(sid, s)
    for sid, s in t02.items():
        if sid.startswith('S-'):
            add_source(sid, s)
    for s in t03['source']:
        add_source(s['id'], s)
    for sid, s in t04['source'].items():
        add_source(sid, s)
    for s in t06['source']:
        add_source(s['id'], s)
    r = t03['revise_source'][0]
    keep = S['S-MSFC-NOZZLE']
    S['S-MSFC-NOZZLE'] = {**keep, **{k: r[k] for k in ('title', 'authors', 'date', 'locator', 'finding', 'limits', 'relation', 'verification', 'checked') if k in r},
                          'kind': 'conference'}
    S['S-T04-STUDY'] = {'title': 'T04 ignition and target study (studies/ignition/ignition.py, results/ignition.json)', 'authors': 'T04 thread',
                        'date': DATE, 'locator': 'lab/variants/vertex-drive/studies/ignition/results/ignition.json', 'kind': 'model',
                        'finding': 'See studies/ignition/REPORT.md.', 'limits': '0-D boundaries; no burn calculation.',
                        'relation': 'All T04 MODEL claims (cases named in study_case).', 'verification': 'PRIMARY_VERIFIED',
                        'checked': f'T00 {DATE}: ignition.py rerun, exit 0 (Atlas cliffs and liner table reproduced).'}
    S['S-T03-STUDY'] = {'title': 'T03 nozzle study (studies/nozzle/*.py, results/*.json)', 'authors': 'T03 thread', 'date': DATE,
                        'locator': 'lab/variants/vertex-drive/studies/nozzle/results/', 'kind': 'model', 'finding': 'See studies/nozzle/REPORT.md.',
                        'limits': 'Vacuum fields, thin elastic shell, test particles: upper bounds.', 'relation': 'All T03 MODEL claims.',
                        'verification': 'PRIMARY_VERIFIED', 'checked': f'T00 {DATE}: test_nozzle.py and the three runners rerun.'}
    S['S-T06-STUDY'] = {'title': 'T06 convergence and futures study (studies/futures/futures.py, results/futures.json)', 'authors': 'T06 thread',
                        'date': DATE, 'locator': 'lab/variants/vertex-drive/studies/futures/results/futures.json', 'kind': 'model',
                        'finding': 'See studies/futures/CONVERGENCE.md.', 'limits': 'Gain bound without the T04 ignitor term (8-12 % optimistic, RECONCILIATION R-03).',
                        'relation': 'T06 MODEL claims.', 'verification': 'PRIMARY_VERIFIED', 'checked': f'T00 {DATE}: futures.py rerun.'}
    S['S-IGNITION-TIMELINE'] = {'title': 'IGNITION - Timeline (master chronology workbook)', 'authors': 'IGNITION owner (Drive)', 'date': '2026-10-21',
                                'locator': 'Google Drive file 1e7gjilGfkcOLkTKrlIPRrjjk3AMW3v7h (xlsx), tabs Master Timeline, Canon Guardrails, Open Chronology',
                                'kind': 'canon', 'finding': 'T055 First Ignition Y155; T056 Wayfarer runaway ignition to about 0.016 c; G10 out Y155, back about Y161; '
                                'G07 technology does not cancel inertia, heat or radiation; G09 Fiji lattice not synthesisable; O04 Fiji Drive performance ladder OPEN.',
                                'limits': 'Read only, 2026-11-09; not captured into the repository (Drive captures stay local).',
                                'relation': 'Historical context for the Vertex history scaffold (D-25); conflicts listed in planning/RECONCILIATION.md.',
                                'verification': 'PRIMARY_VERIFIED', 'checked': f'{DATE} read by T00 through the Drive connector (read only).'}

    # revisions
    def rev(tid, fields, who):
        t = byid[tid]
        for k, v in fields.items():
            if k in ('prior_finding', 'limitations', 'uncertainties') or k.endswith('_append'):
                key = k.replace('_append', '')
                if 'NEW (' in v:                                   # the thread re-sent the field with its addition marked NEW: keep the addition
                    v = v[v.index('NEW ('):].split(':', 1)[1].strip()
                append(t, key, f'{who} {DATE}: {v}')
            elif k.endswith('_replace'):
                key = k.replace('_replace', '')
                if key.startswith('questions_'):
                    t['questions'][key.split('_')[1]] = v
                else:
                    t[key] = v
            elif k == 'claims' or k == 'add_claims':
                t.setdefault('claims', []).extend(norm_claims(v, who))
            elif k == 'next':
                t['next'] = list(t.get('next', [])) + [x for x in v if x not in t.get('next', [])]
            else:
                t[k] = v
    for tid, f in t01['revise'].items():
        rev(tid, f, 'T01')
    for r in t02['revision']:
        f = dict(r['fields'])
        if 'uncertainties' in f:
            f['uncertainties'] = f['uncertainties'].replace('1e10 J/kg', '1.15e13 J/kg (T00 unit correction, R-01)')
        rev(r['id'], f, 'T02')
    for r in t03['revise_technology']:
        rev(r['id'], {'prior_finding': r['change'] + f' Evidence: {r["evidence"]}.'}, 'T03')
    t03_claims = {}
    for c in t03['claim']:
        t03_claims.setdefault(fid(c['technology']), []).append(c)
    for tid, cl in t03_claims.items():
        if tid in byid:
            byid[tid].setdefault('claims', []).extend(norm_claims(cl, 'T03'))
    for tid, f in t04['revise'].items():
        rev(tid, f, 'T04')
    # T00's own corrections to the 2026-11-08 text
    append(byid['VTX-03'], 'prior_finding', f'T00 {DATE}: 0.79 is a momentum efficiency (Thio 1999); the calculator books it as thrust '
                                            'efficiency, so V0-V2 overstate the nozzle (eta_T = 0.62 read consistently). Corrected generations use eta_T.')
    append(byid['VTX-01C'], 'prior_finding', f'T00 {DATE}: T01 quoted 107 Hz and 3.74 m for "FDP-1"; those are V1 figures (V0: 212 Hz, 1.88 m, T04). '
                                             'Both threads agree on the constraint.')

    new = new_records()
    techs_out = []
    for t in techs:
        techs_out.append(t)
    for n in sorted(new, key=lambda x: x['id']):
        techs_out.append(n)
    order = {t['id']: i for i, t in enumerate(techs)}
    techs_out.sort(key=lambda t: (t['id'][:6], len(t['id']), t['id']))

    # links
    links = L['link']
    for l in t01['link']:
        links.append({'from': fid(l['from']), 'to': fid(l['to']), 'kind': l['kind'], 'effect': l['effect'], 'quantified': f'study:thermal:{l["quantified"]}'})
    for l in t02['link']:
        links.append({'from': fid(l['from']), 'to': fid(l['to']), 'kind': l['kind'], 'effect': l['note'], 'quantified': 'UNKNOWN'})
    for l in t06['link']:
        links.append({'from': fid(l['from']), 'to': fid(l['to']), 'kind': l['kind'], 'effect': l['effect'], 'quantified': f'study:futures:{l["quantified"]}'})
    links.append({'from': 'VTX-03D', 'to': 'VTX-06A', 'kind': 'worsens', 'quantified': 'UNKNOWN',
                  'effect': 'Closure coils raise the hardware solid angle from 0.017 to 0.040-0.051 (x2.4-3.0 radiation on hardware); not booked in the calculator.'})
    links.append({'from': 'VTX-01E', 'to': 'VTX-01H', 'kind': 'worsens', 'quantified': 'V4_launcher_sweep',
                  'effect': 'Compression-consistent targets give larger, slower pulses and a longer injection path: V4 needs a launcher of at least 12 km/s; at 6 km/s it does not close.'})

    # decisions
    decs = D['decision']; dby = {d['id']: d for d in decs}
    def note(did, text):
        append(dby[did], 'conclusion', text)
    note('D-01', f'T03 {DATE}: supported and refined: sector clocking gives under 1 deg of shear; the harmonic is m = 2 (trim) / m = 4 (gaps, no handedness).')
    note('D-02', f'T04 {DATE} amendment: no tamper raises ve by more than about 1 % at the mission rhoR even with tamper inertia; up to 10 % only below 10 g/cm2.')
    note('D-03', f'T03 {DATE}: strengthened: at 10-15 E_p of stored field (0.8-1.2 TJ) a 1 % trim in 5 ms is 3-5 TW, not 340 GW (which assumed 1 E_p).')
    note('D-12', f'T02 {DATE}: confirmed (grain Larmor radius about 8e9 m at 1 mT).')
    rulings = {
        'D-04': ('OPEN', 'Owner 2026-11-09: keep the hydrogen low gear out of the preferred experimental configuration, without changing canon (canon keeps the vessels).'),
        'D-06': ('OPEN', 'Owner 2026-11-09: develop skirt, bumpers and replaceable sectors as competing and complementary experimental solutions; do not lock destination or heading.'),
        'D-08': ('DECIDED', 'Owner 2026-11-09: not approved. No canonical engine replacement.'),
        'D-09': ('OPEN', 'Owner 2026-11-09: full MHD/PIC not approved; analytical, vacuum-field, field-line and test-particle work allowed (D-PLAN-1); prepare the bounded 2D proposal (D-21), no HPC run.'),
        'D-10': ('DECIDED', 'Owner 2026-11-09: approved in principle, strictly non-destructive, isolated experimental files only; modelling after T00 baseline and T05 requirements review.'),
        'D-11': ('DECIDED', 'Owner 2026-11-09: not approved. No Google Drive changes.'),
    }
    for did, (state, text) in rulings.items():
        dby[did]['state'] = state; note(did, text)
    newd = [
        ('D-13', 'TECHNICAL_CONCLUSION', 'DECIDED', ['VTX-07A', 'VTX-07E'], t01['decision']['D-T01-1']['question'],
         t01['decision']['D-T01-1']['recommendation'] + ' Owner 2026-11-09: use the component-based thermal findings, not the obsolete 700-800 K loop.'),
        ('D-14', 'TECHNICAL_CONCLUSION', 'DECIDED', ['VTX-01H', 'VTX-01C'], t01['decision']['D-T01-2']['question'],
         'Owner 2026-11-09: investigate through an isolated Vertex model extension (convergence.py vertex.launcher_speed_m_s), no calculator change. '
         'Result: V4 needs >= 12 km/s; at 6 km/s it does not close (V4_launcher_sweep).'),
    ]
    for x in t02['decision']:
        did = DEC[x['id']]
        state = 'OPEN'
        concl = x['conclusion'].replace('1e10 J/kg', '1.15e13 J/kg')
        if x['id'] == 'D-T02-2':
            concl += ' Owner 2026-11-09: develop options (a) skirt or annulus, local bumpers and replaceable sectors as competing and complementary experimental solutions; destination and heading not locked.'
            state = 'DECIDED'
        if x['id'] in ('D-T02-1', 'D-T02-3'):
            concl += ' Owner 2026-11-09: do not lock the mission destination or heading.'
        newd.append((did, x['type'], state, [fid(t) for t in x['technologies']], x['question'], concl))
    q = {d['id']: d for d in t03['decision']}
    newd += [('D-19', 'TECHNICAL_CONCLUSION', 'DECIDED', ['VTX-03', 'VTX-03D'], q['D-T03-1']['question'],
              q['D-T03-1']['recommendation'] + ' T00: corrected generations V3-V5 carry eta_T; V0-V2 keep 0.79 as historical conditional cases; the FDP-1 calculator is unchanged.'),
             ('D-20', 'TECHNICAL_CONCLUSION', 'DECIDED', ['VTX-03', 'VTX-03D'], q['D-T03-2']['question'], q['D-T03-2']['recommendation'] + ' Adopted in V3-V5 (15 E_p).'),
             ('D-21', 'OWNER_APPROVAL_EXPERIMENT', 'OPEN', ['VTX-03', 'VTX-03D'], q['D-T03-3']['question'],
              q['D-T03-3']['recommendation'] + ' Owner 2026-11-09: prepare the bounded 2D proposal (planning/D21_MHD_PIC_PROPOSAL.md); do not launch HPC.')]
    q4 = {d['id']: d for d in t04['decision']}
    q6 = {d['id']: d for d in t06['decision']}
    newd += [('D-22', 'OWNER_APPROVAL_CANON', 'DECIDED', ['VTX-01', 'VTX-01A', 'VTX-01E'],
              'Compression-consistent targets or a declared compression breakthrough? (T04 D-T04-1 merged with T06 D-T06-1)',
              'Owner 2026-11-09: preserve physics-consistent target models (option A); do not declare new Level C compression physics yet; retain a '
              'coupling eta_c/alpha >= 0.5 as an advanced research target. V3-V5 set the gain at the T04 ceiling.'),
             ('D-23', 'TECHNICAL_CONCLUSION', 'DECIDED', ['VTX-04B'], q4['D-T04-2']['question'], q4['D-T04-2']['conclusion']),
             ('D-24', 'OWNER_APPROVAL_CANON', 'DECIDED', ['VTX-03', 'VTX-03D'], q6['D-T06-2']['question'],
              'Owner 2026-11-09: retain the closure-coil nozzle as the preferred experimental candidate without assuming its ideal efficiency has been '
              'demonstrated. V3-V5 use 0.791 as a TARGET upper bound with 0.740 and 0.64 reported beside it.'),
             ('D-25', 'OWNER_APPROVAL_EXPERIMENT', 'DECIDED', ['VTX-02A'], q6['D-T06-3']['question'],
              'Owner 2026-11-09: use the available IGNITION timeline as historical context and flag conflicts with the engineering. Read only; read by T00 on 2026-11-09 (S-IGNITION-TIMELINE).')]
    for did, typ, state, tech, qq, concl in newd:
        decs.append({'id': did, 'type': typ, 'state': state, 'technologies': tech, 'question': qq, 'conclusion': concl})

    write(REG / 'technologies.toml', head('technologies.toml'), {'technology': techs_out})
    write(REG / 'sources.toml', head('sources.toml'), S)
    write(REG / 'links.toml', head('links.toml'), {'link': links})
    write(REG / 'decisions.toml', head('decisions.toml'), {'decision': decs})
    print(f'{len(techs_out)} records, {len(S)} sources, {len(links)} links, {len(decs)} decisions')


def head(name):
    _, txt = base_toml(name)
    lines = []
    for ln in txt.splitlines():
        if ln.startswith('#') or not ln.strip():
            lines.append(ln)
        else:
            break
    return '\n'.join(lines).rstrip() + f'\n# Phase 4 integration {DATE}: written by planning/integrate_phase4.py from the {BASE} registry and the thread proposals.\n'


# ----------------------------------------------------------------------------------------------------------------------------------
# minimal TOML writer for this registry's shapes (strings, numbers, booleans, lists, inline tables, nested tables, arrays of tables)
# ----------------------------------------------------------------------------------------------------------------------------------

def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'


def val(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return q(v)
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            return '[\n' + ''.join(f'  {val(x)},\n' for x in v) + ']'
        return '[' + ', '.join(val(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{ ' + ', '.join(f'{key(k)} = {val(x)}' for k, x in v.items()) + ' }'
    raise TypeError(type(v))


def key(k):
    return k if all(c.isalnum() or c in '-_' for c in k) else q(k)


def table(name, d, arr=False):
    o = [f'[[{name}]]' if arr else f'[{name}]']
    sub = []
    for k, v in d.items():
        if isinstance(v, dict) and not (name == 'technology' and k == 'priority' and False):
            sub.append((k, v))
        else:
            o.append(f'{key(k)} = {val(v)}')
    for k, v in sub:
        o += [''] + table(f'{name}.{key(k)}', v)
    return o


def write(path, header, data):
    o = [header]
    for k, v in data.items():
        if isinstance(v, list):
            for item in v:
                o += [''] + table(k, item, arr=True)
        else:
            o += [''] + table(key(k), v)
    path.write_text('\n'.join(o) + '\n')


if __name__ == '__main__':
    sys.exit(main())
