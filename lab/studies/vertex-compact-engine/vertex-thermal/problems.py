"""Engineering Problems Register additions from the thermal study (ENG-040..056). Reads results/thermal.json; writes
results/problems_thermal.json and PROBLEMS.md. Hardware drawn in the review file does not mean a problem is solved.

    python3 lab/studies/vertex-compact-engine/vertex-thermal/problems.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
d = json.loads((HERE / 'results' / 'thermal.json').read_text())
h, cr, st, pw, pul = d['hot'], d['cryo'], d['strategies'], d['powers'], d['pulsed']
comp = {c['id']: c for c in d['components']}
G = lambda w: f'{w / 1e6:,.0f} MW' if w < 1e9 else f'{w / 1e9:,.1f} GW' if w < 1e12 else f'{w / 1e12:,.2f} TW'
EV = 'lab/studies/vertex-compact-engine/vertex-thermal/results/thermal.json'
coil_ids = ['C1', 'C2', 'L1', 'L2', 'L3', 'L4']
rows = h['rows']
flux_lo = min(x['flux_W_m2'] / x['q_limit_W_m2'] for x in rows); flux_hi = max(x['flux_W_m2'] / x['q_limit_W_m2'] for x in rows)
bare = sum(c['warm_W'] for k, c in comp.items() if k in coil_ids)
arm = sum(c['armoured_share'] * c['sky'] for k, c in comp.items() if k in coil_ids) / sum(c['sky'] for k, c in comp.items() if k in coil_ids)
best = max((m for m in pul['materials'] if m['melt_K'] > 1800), key=lambda m: m['margin_K'])
mhd = [x['dp_mhd_bare_Pa'] for x in rows if x['id'] != 'SHIELD']
BC = next(c for c in d['comparison'] if c['id'] == 'B+C')
BCt = next(c for c in d['comparison'] if c['id'] == 'B+Ct')
Bd = st['B']['detail']; W = d['warm']
SRC = json.loads((HERE.parent / 'vertex-source' / 'results' / 'source.json').read_text())
base = SRC['levers'][0]; bestS = SRC['best']
P = [
    dict(id='ENG-040', title='Supermirrors meet the burn at the wrong angle', categories=['SUPERMIRRORS', 'SHIELDING'], components=coil_ids + ['SHIELD'],
         mechanism=f'X-ray mirrors reflect only at grazing angles of a few mrad; the burn-facing faces of the compact engine meet its rays at a median '
                   f'{st["A"]["median_psi_deg"]:.0f} deg', required='Reflected share of the X-rays on hardware that matters for heat (at least 0.5)',
         achieved=f'{st["A"]["coupled_reflected_share"]:.1e} of the X-rays that strike ({G(st["A"]["coupled_reflected_W"])} of {G(st["A"]["coupled_xray_on_faces_W"])})',
         solutions='Edge-on structure (B) instead of coated faces; mirrors only where a surface can be made to contain the burn point',
         advances='None for hard X-rays: the critical angle is a property of matter (about 1/E)', severity='CRITICAL: no benefit'),
    dict(id='ENG-041', title='No grazing deflector can steer the spectrum clear of a coil', categories=['SUPERMIRRORS', 'MAGNETIC_NOZZLE'], components=coil_ids,
         mechanism='Clearing a coil needs a turn of about its angular width (0.09-0.26 rad); a grazing mirror turns a ray by at most twice the critical '
                   f'angle (Pt {st["D"]["rows"][0]["theta_c_1keV_mrad"]:.0f} mrad at 1 keV)',
         required='A deflection of 0.1-0.26 rad inside the 11.5 m engine envelope', achieved='Only photons below about 0.1 keV; none in the R2-B spectrum (1-1000 keV)',
         solutions='Remote geometry (MPN candidate F, RON B) where coils subtend milliradians', advances='Not reachable with reflection; geometry only',
         severity='CRITICAL: no benefit'),
    dict(id='ENG-042', title='Mirror coatings do not survive the pulse', categories=['SUPERMIRRORS', 'HOT_THERMAL'], components=['SHIELD'] + coil_ids,
         mechanism=f'Each pulse puts up to {pul["hottest"]["fluence_J_m2"] / 1e6:.1f} MJ/m2 of X-rays on the armour in about 10 ps; a 0.5 nm mirror finish ablates '
                   'on the first pulse; neutron and helium damage roughen it further', required='Roughness below 1 nm for 10^7 pulses per hour',
         achieved='Ablation every pulse (tungsten surface jump about 10^5 K)', solutions='None for a mirror face; sacrificial low-Z faces renewed in service',
         advances='Self-healing or flowing-liquid mirror surfaces (SPECULATIVE)', severity='CRITICAL'),
    dict(id='ENG-043', title='Armour shoes cover only part of each coil', categories=['SHIELDING', 'MAGNETIC_COILS'], components=coil_ids,
         mechanism=f'The drawn shoes (0.22 m section) shadow {arm:.0%} of the cryostat silhouette the burn sees; the rest strikes the bare vessel',
         required='Full silhouette armour', achieved=f'{G(bare)} on bare cryostat vessels and joints (no coolant drawn there)',
         solutions=f'Strategy C layered blankets ({st["C"]["mass_t"]:,.0f} t per engine with neutron layers, {st["C"]["thin"]["mass_t"]:,.0f} t without)',
         advances='Lighter neutron shielding (hydrides, boron carbide composites)', severity='CRITICAL'),
    dict(id='ENG-044', title='No face material survives the X-ray pulse at 1800 K', categories=['SHIELDING', 'HOT_THERMAL'], components=['SHIELD'] + coil_ids,
         mechanism='The pulse is far shorter than conduction: the surface layer takes the X-rays at once', required='Surface below melting or sublimation',
         achieved=f'Best is {best["material"].replace("C_diamond", "carbon")}: jump {best["dT_surface_K"]:,.0f} K, margin {best["margin_K"]:,.0f} K; tungsten jumps '
                  f'{next(m for m in pul["materials"] if m["material"] == "W")["dT_surface_K"]:.2g} K; Be and LiH survive the pulse but melt below the 1800 K loop',
         solutions='Low-Z sacrificial faces (carbon) at a colder loop; larger standoff (fluence falls as 1/d^2)', advances='Flowing liquid-lithium walls (SPECULATIVE)',
         severity='CRITICAL'),
    dict(id='ENG-045', title='Heat flux far above any coolant channel', categories=['HOT_THERMAL'], components=['SHIELD'] + coil_ids,
         mechanism='Lithium-cooled tungsten carries about 20 MW/m2 steady', required='Below 20 MW/m2 on every hot face',
         achieved=f'{flux_lo:.0f}-{flux_hi:,.0f} times the limit; the armour channels would need lithium at {min(x["v_needed_m_s"] for x in rows) / 1e3:.0f}-{max(x["v_needed_m_s"] for x in rows) / 1e3:.0f} km/s',
         solutions='Spread the heat (standoff, larger faces); reduce the engine\'s sky share', advances='None in the channel: the flux is set by geometry', severity='CRITICAL'),
    dict(id='ENG-046', title='Drawn lithium lines are far too small', categories=['HOT_THERMAL'], components=['HOT'],
         mechanism='The supply feeder (r 0.11 m) and panel lines (r 0.12 m) carry lithium at most 10 m/s with a 300 K rise',
         required=f'{G(h["heat_W"] + h["warm_uncooled_W"])} (all engine heat); {G(h["budget_W"])} even at the canon radiator share',
         achieved=f'{G(h["drawn_line_cap_W"])}: {h["drawn_line_over"]:,.0f} times short; the budget alone needs {h["budget_line_area_m2"]:.2f} m2 of flow area',
         solutions=f'Lines sized for the budget (several 0.2-0.3 m mains); the full heat would need a {h["pipe_radius_10ms_m"]:.0f} m pipe', advances='-', severity='HIGH'),
    dict(id='ENG-047', title='Liquid-metal MHD pressure loss in the coil field', categories=['HOT_THERMAL', 'MAGNETIC_COILS'], components=coil_ids,
         mechanism='Lithium crossing 1-2.4 T near the windings induces currents that drag the flow (dp ~ sigma v B^2 L c)',
         required='Below the 1 MPa design pressure', achieved=f'{min(mhd) / 1e6:.1f}-{max(mhd) / 1e6:.0f} MPa per armour run at 10 m/s with bare walls; '
                                                          f'{min(x["dp_mhd_fci_Pa"] for x in rows) / 1e6:.2f}-{max(x["dp_mhd_fci_Pa"] for x in rows) / 1e6:.1f} MPa with SiC inserts',
         solutions='SiC flow-channel inserts; runs along the field; helium or molten salt in the strongest field', advances='Insulating coatings qualified in lithium',
         severity='HIGH'),
    dict(id='ENG-048', title='Cryogenic refrigeration demand', categories=['CRYOGENIC', 'MAGNETIC_COILS'], components=coil_ids + ['CRYO'],
         mechanism=f'Neutrons reach the 20 K windings through the bare vessels; each watt there costs {cr["cop20_W_per_W"]:.0f} W of refrigerator input',
         required='Refrigeration within the engine\'s power budget (MW class)',
         achieved=f'{G(cr["stage20_W"])} at 20 K -> {G(cr["refrig_W"])} of input; with blankets C {G(BC["cryo_after_W"])} -> {G(BC["refrig_after_W"])}',
         solutions='Thick neutron shields on every coil; warmer superconductors (40-77 K REBCO)', advances='High-temperature operation of the windings',
         severity='CRITICAL'),
    dict(id='ENG-049', title='Hot radiator area and mass', categories=['HOT_THERMAL'], components=['HOT'],
         mechanism='Everything absorbed leaves by radiation at 1800 K', required=f'{G(h["budget_W"])} per engine (canon share)',
         achieved=f'{h["radiator_m2"]:.3g} m2 per engine ({h["radiator_over_ship"]:,.0f} times the ship\'s radiators, about {h["radiator_t"] / 1e3:,.0f} kt); Brayton recovery raises it {h["brayton"]["radiator_over_direct"]:.0f}-fold',
         solutions='Cut absorbed heat first; recovery runs the driver but enlarges the radiator', advances='-', severity='CRITICAL'),
    dict(id='ENG-050', title='Thermal fatigue at the pulse rate', categories=['HOT_THERMAL', 'SHIELDING', 'STRUCTURE'], components=['SHIELD'] + coil_ids,
         mechanism='Every face is heated and relaxed at the pulse rate', required='Fatigue life of a renewable face over one service interval',
         achieved=f'{pul["cycles_per_hour"]:.2g} cycles per hour; one burn of days is 10^9-10^10 cycles', solutions='Faces renewed between burns (exchange units)',
         advances='OPEN: no fatigue data at these cycle counts', severity='HIGH'),
    dict(id='ENG-051', title='Hot and cryogenic circuits share a narrow gap', categories=['CRYOGENIC', 'HOT_THERMAL'], components=coil_ids,
         mechanism='The 1800 K armour shoe sits 0.16 m from the cryostat; radiation across the gap and the vessels\' own heat need a warm stage',
         required='Separate hot, warm and cold circuits with no shared wall', achieved=f'{G(h["warm_uncooled_W"])} lands on warm parts drawn without a coolant; gap radiation about '
                                                                              f'{sum(x["gap_radiation_to_vessel_W"] for x in cr["rows"]) / 1e6:.1f} MW per engine',
         solutions='A third (warm, about 300-600 K) circuit for vessels, cage and optics; polished screens in the gap', advances='-', severity='HIGH'),
    dict(id='ENG-052', title='Edge-on structure needs sub-milliradian alignment', categories=['SUPERMIRRORS', 'STRUCTURE'], components=['CAGE'],
         mechanism=f'A blade works only while its plane contains the burn point to about {st["B"]["psi_mrad"]:.2f} mrad (source wander over distance); thermal growth '
                   'and coil forces move the cage by millimetres', required='Alignment held to 0.1-1 mrad through each burn',
         achieved=f'Budget {Bd["alignment"]["psi_total_mrad"]:.2f} mrad (target miss, mount, 1 K thermal bow, vibration); a {Bd["alignment"]["face_dT_allowed_K"]:.1f} K '
                  f'face-to-face difference alone uses the whole allowance; first mode {Bd["blade"]["f1_Hz"]:.0f} Hz against {Bd["blade"]["pulse_Hz"]:,.0f} Hz pulses',
         solutions='Both faces cooled together, active root trim from the edge temperature map, constrained-layer dampers, cones instead of flat hoops',
         advances='-', severity='MEDIUM'),
    dict(id='ENG-053', title='Driver final optics see the burn', categories=['TARGET_INJECTION'], components=['OPTICS'],
         mechanism='The six final-focus optics sit in the shield face with a direct view of the burn', required='Optics behind a shutter or a grazing turning mirror',
         achieved=f'{G(comp["OPTICS"]["total_W"])} on 1.9 m2 of optics', solutions='Grazing metal turning mirrors (the one place a grazing mirror fits), fast shutters',
         advances='-', severity='HIGH'),
    dict(id='ENG-054', title='Protection mass exceeds the engine', categories=['SHIELDING', 'STRUCTURE'], components=coil_ids,
         mechanism='Full-silhouette blankets with neutron layers weigh about 3 t/m2', required='Protection mass a small share of the 1,242 t drawn engine',
         achieved=f'{st["C"]["mass_t"]:,.0f} t per engine (B+C {BC["mass_t"]:,.0f} t)', solutions='Thin blankets (no neutron layers, about 250 t) with warmer windings',
         advances='Lighter shields', severity='HIGH'),
    dict(id='ENG-055', title='Lithium leak or loss of flow in a magnet', categories=['HOT_THERMAL', 'MAGNETIC_COILS'], components=['HOT'] + coil_ids,
         mechanism='Lithium runs beside the cryostats; a leak shorts or attacks the vessel, a loss of flow lets the faces melt within milliseconds',
         required='Detection and isolation faster than the face heats', achieved='OPEN: no failure analysis', solutions='Double-walled runs, segment isolation valves, burn abort',
         advances='-', severity='HIGH'),
    dict(id='ENG-056', title='Engine pickup undercounted in the ledger', categories=['SHIELDING', 'STRUCTURE'], components=['CAGE', 'LINES'],
         mechanism='The compact sky ledger counted coils, shield and loops; the cage hoops, seats, struts and lines also see the burn',
         required='One sky trace for every drawn part', achieved=f'Trace {d["reconcile"]["geometry_sky"]:.1%} vs the compact study\'s piped share {d["reconcile"]["ledger_pickup"]:.1%} (x{d["reconcile"]["ratio"]:.2f})',
         solutions='Audited 2026-11-24: the 54.6 % was a piped-heat residual from the steady source, not a geometric share; the coupled ledger now uses the trace',
         advances='-', severity='RESOLVED IN THE MODEL', status='RESOLVED'),
    dict(id='ENG-057', title='Edge-on blades concentrate the heat on their edges', categories=['STRUCTURE', 'HOT_THERMAL'], components=['EDGE', 'CAGE', 'SEAT', 'STRUT'],
         mechanism='A blade aligned with the burn shows it only its edge, so the edge takes the full X-ray flux at its distance',
         required=f'Edge flux below the {d["params"]["q_limit_W_m2"] / 1e6:.0f} MW/m2 a lithium-cooled face can take',
         achieved=f'{Bd["edge"]["steady_W_m2"] / 1e9:.1f} GW/m2 steady ({Bd["edge"]["over_limit"]:,.0f}x), {Bd["edge"]["dT_per_pulse_K"]:,.0f} K per pulse, '
                  f'{Bd["edge"]["stress_over_strength"]:.0%} of CFC strength each pulse',
         solutions='Sacrificial replaceable edge strips on lithium-cooled roots (drawn), exchange ports at the aft hoop (drawn)', advances='Self-renewing edges (SPECULATIVE)',
         severity='HIGH', stages=['thermal']),
    dict(id='ENG-058', title='Blade alignment needs active trim', categories=['STRUCTURE'], components=['ROOT', 'CAGE'],
         mechanism='Thermal bow of a 1 m blade by a few kelvin across its faces swings its plane off the burn point by more than the allowance',
         required=f'Plane held within {Bd["alignment"]["budget"][0]["mrad"]:.2f} mrad', achieved=f'{Bd["alignment"]["face_dT_allowed_K"]:.1f} K face difference allowed; '
                  f'actuators {Bd["integration"]["actuator_t"]:.0f} t per engine (PROTOTYPE)', solutions='Root actuators with an AI controller reading the edge temperature map between pulses (drawn)',
         advances='Fast learned alignment control', severity='MEDIUM', stages=['thermal']),
    dict(id='ENG-059', title='The thin blanket does not cut the cryogenic load', categories=['CRYOGENIC', 'SHIELDING'], components=coil_ids,
         mechanism='Without the W/B4C and LiH layers the neutrons reach the windings', required='20 K load near the refrigeration a ship can carry',
         achieved=f'{G(st["C"]["thin"]["cryo_after_W"])} at 20 K with the thin blanket ({st["C"]["thin"]["mass_t"]:.0f} t); the archived full blanket reached '
                  f'{G(st["C"]["cryo_after_W"])} for {st["C"]["mass_t"]:,.0f} t', solutions='Warmer superconductors (fewer watts per watt), shadow shields at the source',
         advances='High-temperature superconductors at 40-77 K', severity='HIGH', stages=['thermal']),
    dict(id='ENG-060', title='The warm circuit needs a large radiator of its own', categories=['HOT_THERMAL', 'RADIATORS'], components=['WARM_RING', 'WARM_HOOP', 'WARM_RISER'],
         mechanism='An 850 K radiator rejects about a twentieth of the heat per square metre of the hot radiator', required='Warm load small enough for the ship WARM zone',
         achieved=f'{G(W["load_W"])} needs {W["radiator_m2"]:,.0f} m2 ({W["radiator_t"]:,.0f} t)', solutions='Move blade-root heat into the hot loop; keep the warm loop for housings only',
         advances='-', severity='HIGH', stages=['thermal']),
    dict(id='ENG-061', title='The target is its own X-ray lamp', categories=['FUSION_SOURCE'], components=['TARGET'],
         mechanism='At the design density the 14.7 MeV protons stop within microns and give about 90 % of their energy to electrons, which radiate',
         required='X-ray share low enough that cooling can follow', achieved=f'{base["xray_share"]:.0%} of the fusion energy as X-rays; hot ions, '
                  'polarisation and 3He-rich fuel barely change it', solutions='Lower areal density, earlier extraction of the protons, an X-ray trapping tamper',
         advances='Polarised fuel (yield), precision targets', severity='CRITICAL', stages=['ignition', 'losses', 'thermal'], subsystem='Vertex target'),
    dict(id='ENG-062', title='Energy taken from the X-rays strikes the nozzle instead', categories=['FUSION_SOURCE', 'MAGNETIC_NOZZLE'], components=['CAGE'] + coil_ids,
         mechanism='Every lever that keeps energy in the plasma feeds the nozzle, and the compact nozzle puts about two thirds of the plasma on hardware',
         required='Hit share well below 0.1', achieved=f'Best source case: X-rays {bestS["xray_left_share"]:.0%}, thrust x{bestS["engine"]["thrust_N"] / base["engine"]["thrust_N"]:.1f}, '
                  f'engine heat still x{bestS["engine"]["heat_over"]:,.0f} its radiator share ({bestS["engine"]["hit_heat_share"]:.0%} from strikes)',
         solutions='A nozzle with a small hit share (C3/C4 field, remote geometry)', advances='Stronger, lighter coils', severity='CRITICAL', stages=['nozzle', 'losses'],
         subsystem='Vertex target and nozzle'),
    dict(id='ENG-063', title='Exhaust too slow for the mission', categories=['FUSION_SOURCE', 'PROPULSION'], components=['TARGET'],
         mechanism='The coupled pulse leaves too little directed energy per kilogram', required='19,201 km/s (the mission exhaust speed)',
         achieved=f'{base["engine"]["exhaust_m_s"] / 1e3:,.0f} km/s coupled; {bestS["engine"]["exhaust_m_s"] / 1e3:,.0f} km/s with every source lever and a tamper',
         solutions='More directed energy per kilogram: early proton extraction, smaller hit share; never more cold propellant', advances='-',
         severity='CRITICAL', stages=['need', 'nozzle'], subsystem='Vertex target'),
]
STAGE = {'ENG-040': ['thermal'], 'ENG-041': ['thermal'], 'ENG-042': ['thermal'], 'ENG-043': ['thermal'], 'ENG-044': ['thermal'], 'ENG-045': ['thermal'],
         'ENG-046': ['thermal'], 'ENG-047': ['thermal'], 'ENG-048': ['thermal'], 'ENG-049': ['thermal'], 'ENG-050': ['thermal'], 'ENG-051': ['thermal'],
         'ENG-052': ['thermal'], 'ENG-053': ['hardware', 'thermal'], 'ENG-054': ['thermal'], 'ENG-055': ['thermal'], 'ENG-056': ['losses', 'thermal']}
for p in P:
    p.setdefault('status', 'OPEN'); p.setdefault('subsystem', 'Vertex engine thermal'); p.setdefault('stages', STAGE.get(p['id'], ['thermal']))
    p.update(variants=['C1'], evidence=EV if int(p['id'][4:]) < 61 else 'lab/studies/vertex-compact-engine/vertex-source/results/source.json',
             assumptions='Coupled pulse, R2-B spectrum, drawn C1 engine, PROTOTYPE limits in thermal.py and source.py',
             next=p.get('next', 'Continue under the owner\'s 2026-11-24 direction (B adopted, thin blanket optional, source first)'))
(HERE / 'results' / 'problems_thermal.json').write_text(json.dumps(P, indent=1))
md = ['# Engineering Problems Register: thermal and source additions (ENG-040..063)', '',
      'Work, noncanonical (lab/studies/vertex-compact-engine/vertex-thermal and lab/studies/vertex-compact-engine/vertex-source, owner briefs 2026-11-23 14:18Z and 2026-11-24 06:43Z). Drawn hardware does not mean a problem is solved.', '',
      '| ID | Problem | Status | Severity | Required | Achieved | Possible solutions |', '| --- | --- | --- | --- | --- | --- | --- |']
md += [f'| {p["id"]} | {p["title"]} | {p["status"]} | {p["severity"]} | {p["required"]} | {p["achieved"]} | {p["solutions"]} |' for p in P]
(HERE / 'PROBLEMS.md').write_text('\n'.join(md) + '\n')
print(len(P), 'problems'); [print(p['id'], p['achieved']) for p in P]
