"""engineering/fusion-ignition/: Fusion Ignition, From Nucleus to Nozzle (web/engineering/fusion-ignition.js), from the fusion-ignition
lab study (lab/studies/fusion-ignition). tools/story.py calls build() when a lab entry's site data carries the WF_FUSION_IGNITION contract.

Every stage's text and numbers are written into the page from the study's data, so the page reads without JavaScript or WebGL. The
script draws the stages: the schematic ship and the real engine parts (Explore Ship's engine inspection file, about 0.4 MB, loaded on Start),
the vacuum field lines (the same lazily fetched field file), the sampled particle paths, and 2-D views for the nuclear and plasma scales.
"""
import html
import json
import math

CLS = {'SPEC': ('SPEC', 'spec'), 'CALCULATED': ('CALCULATED', 'calculated'), 'SAMPLED': ('CALCULATED', 'sampled'),
       'IMPORTED': ('WORKING', 'imported'), 'MODEL-BASED': ('ASSUMED', 'model-based'), 'ILLUSTRATIVE': ('ASSUMED', 'illustrative'),
       'OPEN': ('OPEN', 'open'), 'SPECULATIVE': ('SPECULATIVE', 'speculative')}

HEAD = '''
<link rel="stylesheet" href="../ignition.css">
<link rel="stylesheet" href="../fusion.css">
<link rel="stylesheet" href="../fusion-ignition.css">
<script type="importmap">
{ "imports": { "three": "../../viewer/vendor/three/three.module.min.js", "three/addons/": "../../viewer/vendor/three/addons/" } }
</script>
<script type="module" src="../fusion-ignition.js"></script>'''


def esc(s):
    return html.escape(str(s), quote=True)


def chip(c):
    k, w = CLS[c]
    return f'<span class="st st-{k}" title="{esc(c.lower())}">{esc(w)}</span>'


def sig(v, p=3):
    if v is None:
        return '–'
    if v == 0:
        return '0'
    if abs(v) >= 1e6 or abs(v) < 1e-3:
        m, e = f'{v:.{p - 1}e}'.split('e')
        return f'{m}×10<sup>{int(e)}</sup>'
    return f'{float(f"{v:.{p}g}"):,}'.removesuffix('.0')


def W(w):
    return f'{w / 1e12:,.1f} TW' if w >= 1e11 else (f'{w / 1e9:,.1f} GW' if w >= 1e8 else f'{w / 1e6:,.0f} MW')


def X(r):
    return f'{r:,.0f}×' if r >= 100 else f'{r:.3g}×'


def T(s):
    if s < 1e-9:
        return f'{s * 1e12:.2g} ps'
    if s < 1e-6:
        return f'{s * 1e9:.2g} ns'
    if s < 1e-3:
        return f'{s * 1e6:.3g} µs'
    return f'{s * 1e3:.3g} ms' if s < 1 else f'{s:,.3g} s'


STAGES = [
    ('need', '0', 'The need', 'Why the ship needs this engine', 'ship'),
    ('hardware', '1', 'Hardware', 'What the engine is made of', 'engine'),
    ('magnets', '2', 'Magnets', 'Powering the coils', 'engine'),
    ('fuel', '3', 'Fuel', 'Target, plasma and reaction mass', 'engine'),
    ('nucleus', '4', 'One reaction', 'Inside the burn: two nuclei', 'nucleus'),
    ('many', '5', 'Many', 'From one reaction to many', 'plasma'),
    ('ignition', '6', 'Ignition', 'What it takes to burn', 'plasma'),
    ('nozzle', '7', 'Thrust', 'From products to thrust', 'engine'),
    ('losses', '8', 'Losses', 'Radiation, heat and the problems', 'engine'),
    ('thermal', '9', 'Heat', 'Mirrors, cooling and where the heat goes', 'engine'),
    ('lab', '10', 'Experiment', 'Change the design', 'engine'),
]
SCALE = {'ship': 'Spacecraft scale · metres', 'engine': 'Engine scale · metres', 'plasma': 'Plasma scale · statistical, not to scale',
         'nucleus': 'Nuclear scale · femtometres, illustrative'}


def stage_texts(d):
    n, e, st, f, nu, pl, ch, md = d['need'], d['engine'], d['startup'], d['fuel'], d['nuclear'], d['plasma'], d['channels'], d['modeled']
    b = pl['burn']; g = b['grid'][f'{b["rhoR_design"]:g}|{b["Ti_design"]:g}']; g10 = b['grid'][f'10|{b["Ti_design"]:g}']
    c1, c4 = ch['variants']['C1'], ch['variants']['C4']
    p = e['pulse']; pk = nu['points'][0]; p100 = nu['points'][1]
    th = {r[0]: r[1] for r in pl['lawson']['thermal']}
    noz = d['nozzle']['mult']['1']['p_14.7MeV']
    ac = d['accounting']; enc = ac['encounter']; bu = ac['burn']
    lg = d['ledger']; S_ = {x['id']: x for x in lg['states']}; R = {r['id']: r for r in lg['reconcile']}; pp = lg['design']['particles']
    lp = lg['pulse']; le = lg['design']['energy']
    out = {}
    out['need'] = (f'''<p>G.U. Wayfarer 001 leaves at {n["departure_t"]:,.0f} t and must reach {n["cruise_c"]:.3f} c ({n["delta_v_m_s"] / 1e3:,.0f} km/s),
      then turn round and brake, four burns in all. No chemical or fission engine comes close: the exhaust must leave at about
      {n["exhaust_c"]:.3f} c ({n["exhaust_m_s"] / 1e3:,.0f} km/s). At {W(n["jet_W"])} of jet power that gives {n["thrust_N"] / 1e6:.1f} MN of thrust, and
      the four engines must make {W(n["fusion_W"])} of fusion power, {W(S_["MISSION"]["fusion_W"])} each.</p>
      <p>The ship carries D–³He fusion fuel and separate hydrogen reaction mass ({n["propellant_t"]:,.0f} t in all), and it must survive
      its own engine: the design budget lets only {n["absorbed_fraction"] * 1e5:g} watts in every 100,000 of fusion stay in the hardware as heat
      ({W(n["hot_budget_W"])} for the whole drive).</p>''', ['SPEC'])
    out['hardware'] = ('''<p>Four Vertex engines sit in one cluster at the stern. Each one is a pulsed fusion engine: a small D–³He target is fired
      to a burn point behind a shadow shield, drivers heat and compress it until it burns, and a magnetic nozzle of six superconducting
      coils catches the burning plasma and throws it aft. Pick a group to see its parts; the colours are functions, not materials.</p>''', ['SPEC'])
    out['magnets'] = (f'''<p>The engine starts cold and dark. Electrical power arrives at the engine bay; the cryogenic circuit holds the windings near
      {e["cold_K"]:.0f} K; then current ramps up in six coils until the field stores {e["stored_J"] / 1e9:.1f} GJ per engine and reaches
      {e["B_burn_T"]:.2f} T at the burn point. The field is a vacuum field: it makes no plasma and no fusion by itself. It is the vessel the burn
      will push against.</p>''', ['CALCULATED', 'ILLUSTRATIVE'])
    out['fuel'] = (f'''<p>Each pulse fires one target of {lg["target_mass_kg"] * 1e6:.2f} mg of deuterium and helium-3 (1 : 1 by nuclei), about
      {sig(pp["injected"]["He3"])} pairs of nuclei, {p["Hz"]:,.0f} times a second at the engine's design point. The drivers strip the electrons
      (13.6 eV for deuterium, 79 eV for helium) and heat the target into a plasma of free nuclei and electrons.</p>
      <p>Not every nucleus fuses: the burn uses {pp["burn_fraction_mass"] * 100:.0f} % of the fuel by mass ({pp["reacted_kg"] * 1e6:.2f} mg), and the
      rest leaves with the exhaust; a pulsed target has no recovery. The mission's fuel tonnes count reacted fuel; its tanks feed 1.25 times
      that and get most of the unburned part back. Hydrogen reaction mass belongs to the mission state only: how fusion products would heat
      it is {chip("SPECULATIVE")}, so the engine ledger adds none.</p>
      <p class="meta">Energy and pulse accounting: four model states (mission, design point, coupled pulse, steady-plasma study) are kept
      apart in the <a href="#ledger">energy and particle ledger</a> below the simulation. The design point makes
      {W(S_["DESIGN"]["fusion_W"])} per engine; the mission needs {W(S_["MISSION"]["fusion_W"])} ({R["R1"]["values"]["ratio"]:.1f}×) {chip("OPEN")}.</p>''', ['CALCULATED'])
    out['nucleus'] = (f'''<p>Two nuclei, both positive: deuterium (one proton, one neutron) and helium-3 (two protons, one neutron). They repel. To touch,
      they would have to climb a Coulomb barrier of about {nu["barrier_MeV"]:.2f} MeV, but at 100 keV a typical pair carries far less. Quantum
      mechanics lets a pair fuse anyway, with a probability that falls steeply with lower energy (the Gamow factor, E<sub>G</sub> =
      {nu["gamow_keV"] / 1e3:.2f} MeV). Most reactions happen near {nu["gamow_peak_keV"]:.0f} keV, where enough pairs are fast and the chance is not
      vanishing. This is a probability, not a path through a wall.</p>
      <p>The scene shows three <b>selected</b> encounters, two misses and one fusion, not the real odds. The paths are calculated Coulomb
      trajectories (closest approach and deflection); the tunnelling wave and the brief compound nucleus are illustrative. Graphs shows the
      barrier and the Gamow window.</p>
      <p class="eq">D + ³He → ⁴He (3.67 MeV) + p (14.68 MeV) + {nu["Q_MeV"]:.1f} MeV in all</p>''', ['CALCULATED', 'ILLUSTRATIVE'])
    out['many'] = (f'''<p>A burning plasma is a crowd. At a pair energy of 100 keV one hard encounter (a 90° deflection in a single pass) fuses about
      once in {1 / enc["per_close_90"]:,.0f}; counting the many gentle passes that deflect a nucleus just as much, it is knocked off course about
      {1 / enc["per_deflection"]:,.0f} times for every fusion ({1 / enc["peak_per_deflection"]:,.0f} at {enc["peak_keV"]:.0f} keV). Every other encounter just
      deflects the nuclei and shares energy. Fusion is not a chain reaction: one fusion does not set off the next. Its charged products slow down in the plasma and keep it hot,
      while X-rays from the electrons (bremsstrahlung) and expansion cool it.</p>
      <p>The crowd moves and repels like charged particles, so you see near misses. Fusions are drawn at a display rate: 1.2 per second at
      100 keV for 1:1 fuel, scaled by the calculated reactivity ⟨σv⟩ at the chosen temperature, the fuel mix and (in Experiment) polarisation.
      Each one takes the closest D–³He pair at that moment, so fusions look far more common per encounter than they are. The products slow down,
      kick the nuclei they pass (heating) and the electrons radiate X-rays. It is not a particle simulation.</p>''', ['CALCULATED', 'ILLUSTRATIVE'])
    out['ignition'] = (f'''<p>A burn sustains itself when the energy the fusion products leave in the plasma outruns the losses. For a steady 1:1 D–³He
      plasma that needs n·τ<sub>E</sub> ≈ {sig(th[100], 2)} m⁻³ s at 100 keV, about four times D–T, and below about 35 keV it is impossible:
      bremsstrahlung alone exceeds the fusion heating.</p>
      <p>The Vertex burns a target instead. Its own burn model (R2-B) reaches the engine's {p["yield_J"] / 1e9:.2f} GJ per pulse at an areal density
      of {b["rhoR_design"]:g} g/cm², with a gain of {g["gain"]:.0f} over the heat the drivers must put in, but {g["photon_share"] * 100:.0f} % of the
      fusion energy leaves the target as X-rays and {bu["neutron"] * 100:.1f} % with neutrons. When the burn ends about {le["plasma_J"] / le["fusion_J"] * 100:.0f} % of the
      fusion energy is still in the expanding plasma, the part a nozzle could steer. The engine design point assumes {ac["charged_assumed"] * 100:.0f} % leaves as
      jet: its own burn cannot deliver that ({chip("OPEN")}, see the <a href="#ledger">ledger</a>, R3). The scene plays this burn from the model's own history (temperature, radius, energy released);
      the arrival and crushing of the target before it are drawn only as a question. Laser-driven D–T has shown about {b["nif_rhoR"]:g} g/cm²; at 10 g/cm² the gain is
      {g10["gain"]:.1f}. <b>How the target is compressed that far is not modelled:</b> {chip("OPEN")}.</p>
      <p><b>Modeled behavior:</b> the drivers must put at least {lp["heat_in_J"] / 1e6:.0f} MJ into every target: {W(lp["driver_abs_W"])} per engine at the
      design rate, {W(lp["driver_elec_W"])} of electric power at {lg["wallplug"] * 100:.0f} % efficiency, while the budgeted pulse bank delivers
      {W(st["steps"][0]["value"]["bank_W"])}. The engine takes up {X(lp["heat_over"])} the radiator share (coupled ledger). The earlier ignition-failures
      study, run at 71.6 TW, found the hardware 1000 K hotter after {T(md["melt_s"])} and the {md["coil"]} superconductor ended by neutrons in
      {T(md["coil_life_s"])} {chip("IMPORTED")}.</p>''', ['CALCULATED', 'OPEN'])
    out['nozzle'] = (f'''<p>The products leave at {nu["products"]["alpha"]["v_c"] * 100:.1f} % (⁴He) and {nu["products"]["p"]["v_c"] * 100:.1f} % (proton) of the speed of light. Each charged particle spirals round a field line (a 14.7 MeV proton on a
      {noz["larmor_burn_m"]:.2f} m circle at the burn point) and the opening field turns its motion aft; the plasma as a whole pushes the field
      out and leaves through the nozzle at {p["exhaust_m_s"] / 1e3:,.0f} km/s. The momentum it carries aft is the ship's thrust:
      {n["thrust_N"] / 1e6:.1f} MN for the four engines.</p>
      <p class="meta">Intended: that is the mission requirement. The engine's design point would give {S_["DESIGN"]["thrust_N"] * 4 / 1e6:.1f} MN at that exhaust speed.</p>
      <p><b>Modeled behavior:</b> in the vacuum field {noz["share"]["aft"] * 100:.0f} % of the sampled proton directions leave aft and
      {noz["share"]["hit"] * 100:.0f} % strike hardware {chip("SAMPLED")}; the compact study's axial efficiency is {c1["eta"]:.2f} for the drawn cluster
      ({c4["eta"]:.2f} for C4). With the burn coupled, the jet gets {lp["jet_share"] * 100:.1f} % of the fusion energy: the exhaust leaves at
      {lp["exhaust_m_s"] / 1e3:,.0f} km/s and the four engines make {lp["thrust_N"] * 4 / 1e6:.2f} MN, {n["thrust_N"] / (lp["thrust_N"] * 4):.0f}× short of the mission.</p>''', ['SAMPLED', 'IMPORTED'])
    out['losses'] = (f'''<p>Every joule of fusion goes somewhere. In the coupled ledger one pulse ({le["fusion_J"] / 1e9:.2f} GJ, {W(lp["fusion_W"])} per engine) sends
      {lp["xray_J"] / lp["fusion_J"] * 100:.0f} % out as X-rays and {lp["neutron_J"] / lp["fusion_J"] * 100:.1f} % with neutrons; of the plasma energy left, the C1 nozzle
      directs {lg["nozzle"]["C1|1"]["eta"] * 100:.0f} % and {lg["nozzle"]["C1|1"]["hit"] * 100:.0f} % strikes loops and shield. The engine takes up
      {W(lp["engine_heat_W"])} per engine against a radiator share of {W(lp["budget_W"])}: <b class="bad">{X(lp["heat_over"])}</b> (ENG-030). The windings
      take {X(c1["winding_over"])} their neutron limit (ENG-033); the burns put {W(c1["ship_lit_W"])} on the ship (ENG-032; both from the compact study).</p>
      <p class="meta">Model state: the compact study that registered these problems used the mission power and a steady-plasma radiation split (X-rays
      {(S_["STEADY"]["xray_share"] + S_["STEADY"]["sync_share"]) * 100:.1f} %), which gives {X(c1["over"])} for C1 and {X(c4["over"])} for C4. That split
      belongs to a steady plasma that does not sustain itself, not to a target ({chip("IMPORTED")}, ledger R2). Both fail.</p>''', ['CALCULATED', 'IMPORTED'])
    tm = d['thermal']; ts = tm['strategies']; th_ = tm['hot']; tc = tm['cryo']
    out['thermal'] = (f'''<p>Where does the heat go, and can mirrors or coolant change it? A component trace of the drawn engine follows every X-ray,
      neutron and charged strike of the coupled pulse to the part it meets. <b>Supermirrors</b> reflect X-rays only at grazing angles of a few
      milliradians; the engine's faces meet the burn at about {ts["A"]["median_psi_deg"]:.0f}°, so a coating returns {ts["A"]["coupled_reflected_share"]:.1e} of what
      strikes, and no deflector inside the engine can turn the 1–1000 keV spectrum clear of a coil. Mirrors help only where a surface can contain
      the burn point: cage members rebuilt as edge-on blades keep {ts["B"]["keep_share"] * 100:.0f} % of their heat, the one large cut ({W(ts["B"]["removed_W"])}),
      and this is the adopted direction; each blade must hold its plane on the burn to {ts["B"]["detail"]["alignment"]["psi_total_mrad"]:.2f} mrad.</p>
      <p>The stage starts at the source: the burn's protons and alphas heat its electrons, which radiate {d["source"]["levers"][0]["xray_share"] * 100:.0f} % of the
      fusion energy as X-rays before any mirror can act; pick a lever to follow it to thrust and heat. A thin blanket (option, {ts["C"]["thin"]["mass_t"]:.0f} t) moves
      heat into lithium but lets the neutrons through; the full {ts["C"]["mass_t"]:,.0f} t blanket is archived. The lithium circuit
      (1500 → 1800 K) as drawn carries {W(th_["drawn_line_cap_W"])} of the {W(th_["heat_W"] + th_["warm_uncooled_W"])} it would have to; the radiator for all of it is
      {th_["radiator_m2"] / 1e6:.0f} km²; a warm NaK circuit (650 → 850 K) takes the blade roots and optics. The cryogenic loop stays separate, and its refrigerators would need {W(tc["refrig_W"])}.</p>
      <p class="meta">The hardware drawn here is research (WORK), not canon. Drawing a blanket, a mirror or a pipe does not solve its problem:
      every component card names its open problems (ENG-040 to ENG-063).</p>''', ['IMPORTED', 'CALCULATED', 'MODEL-BASED'])
    out['lab'] = ('''<p>Change one thing and follow it through the engine. The target (areal density, start temperature, fuel mix) is burned by the
      model; the pulse rate turns it into power; the variant and field decide what the nozzle directs and what strikes hardware; mirrors and
      armour change the heat and the windings. Hydrogen reaction mass has no coupled model, so the result says so instead of guessing. The
      steady-plasma levers (hot-ion mode, polarisation) belong to another regime and are kept apart. Nothing here changes the ship.</p>''', ['CALCULATED', 'IMPORTED', 'MODEL-BASED'])
    return out


def ledger(d):
    n, e, ch, md, pl = d['need'], d['engine'], d['channels'], d['modeled'], d['plasma']
    b = pl['burn']; g = b['grid'][f'{b["rhoR_design"]:g}|{b["Ti_design"]:g}']
    rows = [
        ('Departure mass, cruise speed', f'{n["departure_t"]:,.0f} t, {n["cruise_c"]:.3f} c', 'SPEC', 'operating_point.report'),
        ('Exhaust speed, thrust (four engines)', f'{n["exhaust_m_s"] / 1e3:,.0f} km/s, {n["thrust_N"] / 1e6:.1f} MN', 'SPEC', 'operating_point.report'),
        ('Fusion power, jet power', f'{W(n["fusion_W"])}, {W(n["jet_W"])}', 'SPEC', 'operating_point.report'),
        ('Fusion power per engine (mission)', W(n['fusion_W'] / 4), 'SPEC', 'operating_point.report'),
        ('Pulse design point: yield × rate = power per engine', f'{e["pulse"]["yield_J"] / 1e9:.2f} GJ × {e["pulse"]["Hz"]:,.0f} Hz = {W(e["pulse"]["power_W"])}', 'SPECULATIVE', 'vertex_engine C-02, C-04'),
        ('Mission power over the pulse design point', f'{d["accounting"]["gap"]["power_ratio"]:.1f}× (OPEN, ledger R1)', 'CALCULATED', 'ledger'),
        ('Coupled pulse: jet share, exhaust speed, thrust (four)', f'{d["ledger"]["pulse"]["jet_share"] * 100:.1f} %, {d["ledger"]["pulse"]["exhaust_m_s"] / 1e3:,.0f} km/s, {d["ledger"]["pulse"]["thrust_N"] * 4 / 1e6:.2f} MN', 'CALCULATED', 'ledger.py (R2-B + C1 nozzle)'),
        ('Coupled pulse: engine heat over radiator', X(d['ledger']['pulse']['heat_over']), 'CALCULATED', 'ledger.py'),
        ('Field energy per engine, field at the burn', f'{e["stored_J"] / 1e9:.1f} GJ, {e["B_burn_T"]:.2f} T', 'CALCULATED', 'vertex_magnet (NOMINAL)'),
        ('Target burn: areal density, gain, X-ray share', f'{b["rhoR_design"]:g} g/cm², {g["gain"]:.1f}, {g["photon_share"] * 100:.0f} %', 'CALCULATED', 'vertex_radiation.burn (R2-B)'),
        ('Driver power, coupled pulse (lower bound, 50 % wall-plug)', W(d['ledger']['pulse']['driver_elec_W']), 'CALCULATED', 'ledger.py'),
        ('Driver power at 71.6 TW (ignition-failures state)', f'{W(md["driver_W"])} (pulse bank empty after {T(md["bank_empty_s"])})', 'IMPORTED', 'ignition-failures'),
        ('Engine heat over radiator, C1 / C4 (steady-source study)', f'{X(ch["variants"]["C1"]["over"])} / {X(ch["variants"]["C4"]["over"])}', 'IMPORTED', 'lab/studies/vertex-compact-engine/vertex-compact'),
        ('Winding neutron fluence over limit', X(ch['variants']['C1']['winding_over']), 'IMPORTED', 'lab/studies/vertex-compact-engine/vertex-compact'),
        ('Direct burn on the ship, C1 / C4 (limit 0.1 GW)', f'{W(ch["variants"]["C1"]["ship_lit_W"])} / {W(ch["variants"]["C4"]["ship_lit_W"])}', 'IMPORTED', 'lab/studies/vertex-compact-engine/vertex-compact'),
    ]
    return ''.join(f'<tr><td>{esc(a)}</td><td class="num">{b_}</td><td>{chip(c)} <span class="meta">{esc(s)}</span></td></tr>' for a, b_, c, s in rows)


def ledger_section(d):
    """The energy and particle ledger: one coupled pulse step by step, the four model states side by side, the reconciliation."""
    lg = d['ledger']; lp = lg['pulse']; de = lg['design']; e = de['energy']; pp = de['particles']; S_ = {x['id']: x for x in lg['states']}
    F = e['fusion_J']; MJ = lambda j: f'{j / 1e6:,.0f} MJ' if j < 1e9 else f'{j / 1e9:,.2f} GJ'
    flow = [('in', 'Driver heat in the fuel (lower bound; compression OPEN)', MJ(e['heat_in_J'])),
            ('in', f'Fusion released ({pp["reactions"]["DHe3"]:.2e} D-³He reactions, {sum(v for k, v in pp["reactions"].items() if k != "DHe3"):.1e} side reactions)', MJ(F)),
            ('loss', 'Escaped as X-rays (bremsstrahlung)', f'{MJ(e["xray_J"])} · {e["xray_J"] / F * 100:.1f} %'),
            ('loss', 'Carried off by neutrons (D-D side reactions)', f'{MJ(e["neutron_J"])} · {e["neutron_J"] / F * 100:.1f} %'),
            ('', 'Left in the plasma at the end of the burn', f'{MJ(e["plasma_J"])} · {e["plasma_J"] / F * 100:.1f} %'),
            ('loss', 'Plasma striking hardware (C1 nozzle)', MJ(lp['hit_J'])),
            ('', 'Plasma leaving undirected', MJ(lp['side_J'])),
            ('out', f'Directed jet: {lp["jet_share"] * 100:.1f} % of fusion', f'{MJ(lp["jet_J"])} → {lp["impulse_Ns"]:.1f} N·s at {lp["exhaust_m_s"] / 1e3:,.0f} km/s'),
            ('loss', 'Heat taken up by the engine per pulse', f'{MJ(lp["engine_heat_J"])} → {X(lp["heat_over"])} the radiator share at {lp["Hz"]:,.0f} Hz'),
            ('', 'Bookkeeping residual of the burn model', f'{e["residual_share"] * 100:.2f} % of heat + fusion')]
    flow_html = ''.join(f'<li class="{c}"><span>{esc(a)}</span><b>{b}</b></li>' for c, a, b in flow)
    cols = [S_['MISSION'], S_['DESIGN'], S_['COUPLED'], S_['STEADY']]
    def cell(x, k):
        v = x.get(k)
        if k == 'jet_share' and v is None and 'jet_W' in x:
            v = x['jet_W'] / x['fusion_W']
        if v is None:
            return '–'
        if k.endswith('_W'):
            return W(v)
        if k == 'thrust_N':
            return f'{v * 4 / 1e6:.2f} MN'
        if k == 'exhaust_m_s':
            return f'{v / 1e3:,.0f} km/s'
        if k == 'yield_J':
            return f'{v / 1e9:.2f} GJ'
        if k == 'Hz':
            return f'{v:,.0f}'
        return f'{v * 100:.1f} %'
    xshare = lambda x: (x['xray_W'] / x['fusion_W']) if 'xray_W' in x else (x['xray_share'] + x.get('sync_share', 0.0)) if 'xray_share' in x else None
    rows = [('Fusion power per engine', 'fusion_W'), ('Energy per pulse', 'yield_J'), ('Pulse rate (Hz)', 'Hz'), ('Jet share of fusion', 'jet_share'),
            ('Exhaust speed', 'exhaust_m_s'), ('Thrust, four engines', 'thrust_N')]
    th = ''.join(f'<th>{esc(x["label"])} {chip(x["cls"])}</th>' for x in cols)
    tb = ''.join(f'<tr><td>{esc(a)}</td>' + ''.join(f'<td class="num">{cell(x, k)}</td>' for x in cols) + '</tr>' for a, k in rows)
    tb += '<tr><td>X-ray share of fusion</td>' + ''.join(f'<td class="num">{"–" if xshare(x) is None else f"{xshare(x) * 100:.1f} %"}</td>' for x in cols) + '</tr>'
    assumes = ''.join(f'<li><b>{esc(x["label"])}</b> {chip(x["cls"])}: {esc(x["assumes"])} <span class="meta">{esc(x["source"])}</span></li>' for x in cols)
    rec = ''.join(f'<details class="fi-rec" id="rec-{r["id"]}"><summary><b>{r["id"]}</b> {esc(r["title"])} · <span class="vd">{esc(r["verdict"])}</span></summary>'
                  f'<p>{esc(r["why"])}</p><p><b>Coupled ledger:</b> {esc(r["coupled"])}</p></details>' for r in lg['reconcile'])
    inj, fin = pp['injected'], pp['final']
    parts = [('Deuterium', inj['D'], fin['D']), ('Helium-3', inj['He3'], fin['He3']), ('Helium-4 (product)', 0, fin['alpha']), ('Protons (product)', 0, fin['p']),
             ('Tritium (from D-D, partly burned)', 0, fin['T']), ('Neutrons (left the target)', 0, pp['neutrons'])]
    ptab = ''.join(f'<tr><td>{esc(a)}</td><td class="num">{sig(b)}</td><td class="num">{sig(c)}</td></tr>' for a, b, c in parts)
    ck = lg['checks']
    span = lambda t: '' if t['t0'] is None or t['t1'] == t['t0'] else f' ({T(t["t1"] - t["t0"])})'
    tl = ''.join(f'<li>{chip(t["cls"])} <b>{esc(t["title"])}</b>: {esc(t["note"])}'
                 f'{span(t)}</li>' for t in lg['timeline'])
    return f"""<section id="ledger"><h2>Energy and particle ledger</h2>
<p>One bookkeeping runs through every stage: the target injected, the heat put in, the fusion released, where each joule goes and what
  thrust is left. The studies behind the page were made under different assumptions; they are kept apart here, never tuned to agree, and each
  number on the page belongs to one of these states. In the simulation, <b>Intended</b> shows the engine design point, <b>Modeled</b> the coupled
  pulse and <b>Experiment</b> the coupled pulse with your levers.</p>
<h3>One coupled pulse, step by step {chip('CALCULATED')}</h3>
<ol class="fi-flow">{flow_html}</ol>
<p class="meta">The target: {de["mass_kg"] * 1e6:.2f} mg at {de["case"]["rhoR_g_cm2"]:g} g/cm² and {de["case"]["Ti_keV"]:g} keV, radius {de["R0_m"] * 1e6:.0f} µm, burning for
  {T(de["duration_s"])}. Conservation checks: nucleons and charge before and after agree to {abs(ck["nucleons"][1] / ck["nucleons"][0] - 1):.0e} and
  {abs(ck["charge"][1] / ck["charge"][0] - 1):.0e}; mass in = ions out + neutrons + mass turned into energy to {abs(ck["mass_check"]):.0e} of the target; the
  burn's energy residual is {abs(ck["energy_residual_share"]) * 100:.2f} % (nuclei created or removed at fixed temperature).</p>
<div class="scroll" tabindex="0"><table class="fi-led2"><thead><tr><th>Nuclei in one pulse</th><th>Injected</th><th>After the burn</th></tr></thead><tbody>{ptab}</tbody></table></div>
<h3>The pulse in time</h3><ul class="plain">{tl}</ul>
<h3>Four model states side by side</h3>
<div class="scroll" tabindex="0"><table class="fi-led2"><thead><tr><th>Per engine</th>{th}</tr></thead><tbody>{tb}</tbody></table></div>
<ul class="plain">{assumes}</ul>
<h3>The reported differences</h3>{rec}
<details><summary>Limits of the ledger</summary><ul class="plain">{''.join(f'<li>{esc(x)}</li>' for x in lg['limits'])}</ul></details>
</section>"""


def thermal_section(d):
    """Supermirrors, cooling mesh and the per-component heat (thermal study): benefit against mass, components, circuits, limits."""
    tm = d['thermal']; ts = tm['strategies']; h = tm['hot']; c = tm['cryo']; rc = tm['reconcile']
    cmp_ = ''.join(f'<tr><td><b>{esc(x["id"])}</b> {esc(x["title"])}<small>{esc(x.get("acts", ""))}</small></td>'
                   f'<td class="num">{W(x.get("removed_W", 0)) if x.get("removed_W") else "–"}</td><td class="num">{W(x["moved_W"]) if x.get("moved_W") else "–"}</td>'
                   f'<td class="num">{W(x["cryo_saved_W"]) if x.get("cryo_saved_W") else "–"}</td><td class="num">{x["mass_t"]:,.1f} t</td>'
                   f'<td>{esc(x["verdict"].lower())}</td></tr>' for x in tm['comparison'] if x['id'] != 'BASE')
    comps = ''.join(f'<tr><td>{esc(x["id"])}</td><td class="num">{x["sky"] * 100:.1f} %</td><td class="num">{x["psi_median_deg"]:.0f}°</td><td class="num">{W(x["hot_W"]) if x["hot_W"] else "–"}</td>'
                    f'<td class="num">{W(x["warm_W"]) if x["warm_W"] else "–"}</td><td class="num">{W(x["cryo_W"]) if x["cryo_W"] else "–"}</td>'
                    f'<td class="num">{x["armoured_share"] * 100:.0f} %</td></tr>' for x in tm['components'])
    hot = ''.join(f'<tr><td>{esc(x["id"])}</td><td class="num">{x["flux_W_m2"] / 1e6:,.0f}</td><td class="num">{x["flux_W_m2"] / x["q_limit_W_m2"]:,.0f}×</td>'
                  f'<td class="num">{x["v_needed_m_s"] / 1e3:.1f} km/s</td><td class="num">{x["B_T"]:.1f} T</td><td class="num">{x["dp_mhd_bare_Pa"] / 1e6:.1f} / {x["dp_mhd_fci_Pa"] / 1e6:.2f} MPa</td></tr>'
                  for x in h['rows'])
    mats = ''.join(f'<tr><td>{esc(m["material"].replace("C_diamond", "carbon (CFC)"))}</td><td class="num">{m["dT_surface_K"]:,.0f} K</td><td class="num">{m["mean_depth_m"] * 1e3:.1f} mm</td>'
                   f'<td class="num">{m["melt_K"]:,.0f} K</td><td>{"survives" if m["survives"] else "fails"}</td></tr>' for m in tm['pulsed']['materials'])
    bc = next(x for x in tm['comparison'] if x['id'] == 'B+Ct')
    sr = d['source']; bd = ts['B']['detail']; wm = tm['warm']
    lev = ''.join(f'<tr><td>{esc(x["label"])}</td><td class="num">{x["fusion_J"] / sr["levers"][0]["fusion_J"]:.2f}×</td><td class="num">{x["xray_share"] * 100:.0f} %</td>'
                  f'<td class="num">{x["extract_share"] * 100:.0f} %</td><td class="num">{x["engine"]["exhaust_m_s"] / 1e3:,.0f} km/s</td><td class="num">{x["engine"]["heat_over"]:,.0f}×</td>'
                  f'<td>{chip(x["cls"])}</td></tr>' for x in sr['levers'])
    tw = ''.join(f'<tr><td>{esc(t["material"].replace("C_diamond", "carbon"))} {t["sigma_g_cm2"]} g/cm²</td><td class="num">{t["absorbed"] * 100:.1f} %</td>'
                 f'<td class="num">{t["xray_left_share"] * 100:.0f} %</td><td class="num">{t["exhaust_m_s"] / 1e3:,.0f} km/s</td><td class="num">{t["impulse_ratio"]:.2f}×</td></tr>'
                 for t in sr['tamper'] if t['sigma_g_cm2'] in (0.1, 1.0, 3.0))
    tech = ''.join(f'<li><b>{esc(t["lever"])}</b>: {esc(t["physics"])}. Enablers: {esc(t["enabler"])} ({esc(t["status"].lower())}).</li>' for t in sr['tech'])
    algn = ''.join(f'<li>{esc(a["term"])}: {a["mrad"]:.3f} mrad ({esc(a["source"])})</li>' for a in bd['alignment']['budget'])
    return f'''<section id="source"><h2>At the source: where the fusion energy goes</h2>
<p>The burn decides most of the heat before any mirror, blanket or pipe can act {chip("CALCULATED")}. The design target ({sr["design"]["mass_kg"] * 1e6:.2f} mg,
  ρR {sr["design"]["rhoR_g_cm2"]} g/cm²) is so dense that its 14.7 MeV protons and 3.6 MeV alphas stop inside it and give most of their energy to
  electrons, which radiate: {sr["levers"][0]["xray_share"] * 100:.0f} % of the fusion energy leaves as X-rays, {sr["levers"][0]["extract_share"] * 100:.0f} % stays as plasma the nozzle can use (ENG-061).</p>
<ul class="plain">{''.join(f'<li>{esc(f)}</li>' for f in sr['findings'])}</ul>
<details><summary>Every lever, followed to the engine</summary><div class="scroll" tabindex="0"><table class="fi-led"><thead><tr><th>Case</th><th>Yield</th><th>X-rays</th><th>Usable plasma</th><th>Exhaust</th><th>Heat over budget</th><th>Class</th></tr></thead>
<tbody>{lev}</tbody></table></div></details>
<details><summary>X-ray trapping tamper</summary><p>A heavy shell round the fuel absorbs X-rays and turns them into plasma the field can direct (cold opacity, an upper bound {chip("MODEL-BASED")}).
  With every source lever and a tungsten tamper the X-ray share falls to {sr["best"]["xray_left_share"] * 100:.0f} % and thrust doubles, but the engine still takes
  {sr["best"]["engine"]["heat_over"]:,.0f}× its radiator share, now mostly from charged strikes (ENG-062).</p>
<div class="scroll" tabindex="0"><table class="fi-led"><thead><tr><th>Tamper</th><th>Absorbs</th><th>X-rays left</th><th>Exhaust</th><th>Impulse</th></tr></thead><tbody>{tw}</tbody></table></div></details>
<details><summary>Pickup audit: 63.1 % against 54.6 %</summary><ul class="plain">{''.join(f'<li>{esc(f)}</li>' for f in sr['audit']['findings'])}
  <li>The energy residual of the burn is now booked: ions lost in D-D and D-T reactions carry {sr["levers"][0]["number_change_share"] * 100:.2f} % of the yield; {sr["levers"][0]["residual_share"] * 100:.3f} % remains as integration error.</li></ul></details>
<details><summary>Technology that could help, within physics</summary><ul class="plain">{tech}</ul></details></section>
<section id="thermal"><h2>Supermirrors, cooling and the heat in each part</h2>
<p>Every number here is per engine at the coupled pulse ({W(tm["powers"]["fusion_W"])} fusion, {W(tm["powers"]["xray_W"])} of X-rays) {chip("IMPORTED")}. The study
  (<code>lab/studies/vertex-thermal</code>) traced the burn's sky through every drawn part: the hardware covers {rc["geometry_sky"] * 100:.1f} % of it, which the coupled
  ledger now uses (it replaced the compact study's {rc["ledger_pickup"] * 100:.1f} %, see the audit above).</p>
<p class="fi-status"><span class="st st-WORKING">visually complete</span> blades, cones, mirrors, blankets, hot, warm and cryogenic circuits, manifolds and service interfaces are drawn and inspectable.
  <span class="st st-OPEN">scientifically unresolved</span> none of them closes the heat: the engine still takes {bc["over_budget_after"]:,.0f}× its radiator share.</p>
<h3>Benefit against mass</h3>
<div class="scroll" tabindex="0"><table class="fi-led"><thead><tr><th>Strategy</th><th>Heat off the engine</th><th>Heat moved to lithium</th><th>20 K load saved</th><th>Mass per engine</th><th>Verdict</th></tr></thead>
<tbody>{cmp_}</tbody></table></div>
<p>{esc(bc["why"])}</p>
<details><summary>Edge-on blades (adopted): alignment, vibration, edge</summary><p>{esc(bd["alignment"]["note"])}</p><ul class="plain">{algn}</ul>
<p>{esc(bd["vibration"]["note"])} {esc(bd["edge"]["note"])} {esc(bd["integration"]["note"])}</p></details>
<details><summary>What each part takes</summary><div class="scroll" tabindex="0"><table class="fi-led"><thead><tr><th>Part</th><th>Sky</th><th>Faces at (median)</th><th>Into lithium</th><th>No coolant drawn</th><th>20 K winding</th><th>Behind armour</th></tr></thead>
<tbody>{comps}</tbody></table></div></details>
<details><summary>Hot circuit: lithium 1500 → 1800 K</summary><p>Heat-flux limit {tm["params"]["q_limit_W_m2"] / 1e6:.0f} MW/m² (lithium-cooled tungsten, PROTOTYPE).
  The drawn feeder and panel lines carry {W(h["drawn_line_cap_W"])}; the canon radiator share alone ({W(h["budget_W"])}) needs {h["budget_line_area_m2"]:.2f} m² of flow area.
  The radiator for all the heat is {h["radiator_m2"] / 1e6:.1f} km² ({X(h["radiator_over_ship"])} the ship's); Brayton recovery would make {W(h["brayton"]["electric_W"])},
  enough for the driver, and grow the radiator {h["brayton"]["radiator_over_direct"]:.0f}-fold.</p>
<div class="scroll" tabindex="0"><table class="fi-led"><thead><tr><th>Part</th><th>Mean flux, MW/m²</th><th>Over limit</th><th>Lithium speed needed</th><th>Field</th><th>MHD loss bare / SiC insert</th></tr></thead><tbody>{hot}</tbody></table></div></details>
<details><summary>One pulse on the hottest face</summary><p>The X-rays of one pulse ({tm["pulsed"]["hottest"]["fluence_J_m2"] / 1e6:.1f} MJ/m²) arrive far faster than heat can
  conduct, so the surface layer takes them at once, {tm["pulsed"]["cycles_per_hour"]:.1e} times an hour.</p>
<div class="scroll" tabindex="0"><table class="fi-led"><thead><tr><th>Face</th><th>Surface jump</th><th>Mean depth</th><th>Melts at</th><th>From 1800 K</th></tr></thead><tbody>{mats}</tbody></table></div></details>
<details><summary>Warm circuit: {esc(wm["fluid"])} {wm["inlet_K"]:.0f} → {wm["outlet_K"]:.0f} K</summary><p>{esc(wm["note"])} Load {W(wm["load_W"])};
  radiator {wm["radiator_m2"] / 1e6:.2f} km² ({wm["radiator_t"] / 1e3:,.1f} kt) (ENG-060).</p></details>
<details><summary>Cryogenic circuit</summary><p>{esc(c["separation"])} The windings take {W(c["stage20_W"])} at 20 K; at {c["cop20_W_per_W"]:.0f} W of input per watt the
  refrigerators need {W(c["refrig_W"])}. The thin blanket leaves it unchanged (neutrons pass, ENG-059); the archived full blanket would cut it to {W(ts["C"]["cryo_after_W"])}. Quench: {c["quench"]["stored_J"] / 1e9:.1f} GJ dumped over
  {c["quench"]["dump_s"]:.0f} s into warm resistors, never into the lithium.</p></details>
<details><summary>Assumptions and limits</summary><ul class="plain">
  <li>Mirrors: Fresnel reflection with the best of ten coatings at each energy, 0.5 nm roughness, as new. The R2-B burn spectrum. Neutrons and charged particles are not reflected.</li>
  <li>Charged strikes are shared out in proportion to each part's sky (MODEL-BASED); the nozzle sends them mostly to the shield and closure coils.</li>
  <li>Neutrons: W/B4C attenuation length 0.08 m with a scattered floor of 1e-4, LiH 0.12 m; half of what reaches a winding pack deposits there.</li>
  <li>Edge-on blades: alignment, first mode and edge heating are estimated (PROTOTYPE amplitudes and tolerances); no structural dynamics model yet (ENG-052, ENG-058).</li>
  <li>The Review file <code>REVIEW_THERMAL.blend</code> and its renders show the hardware; they are research, not canon.</li></ul></details></section>'''


def problems_table(d):
    return ''.join(f'<tr id="p-{p["id"]}"><td><b>{esc(p["id"])}</b></td><td>{esc(p["title"])}<small>{esc(p["mechanism"])}</small></td>'
                   f'<td>{esc(p["required"])}</td><td>{esc(p["achieved"])}</td><td>{esc(", ".join(p.get("components") or []) or "–")}'
                   f'<small>{esc(", ".join(p.get("stages") or []))}</small></td><td>{esc(p.get("solutions", ""))}</td><td><span class="st st-{"OPEN" if p["status"] == "OPEN" else "WORKING"}">'
                   f'{esc(p["status"].lower())}</span></td></tr>' for p in d['problems']['items'])


def build(e, d, out_dir, revision, built, page):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'fusion_ignition.json').write_text(json.dumps(d, separators=(',', ':')))
    texts = stage_texts(d)
    tabs = ''.join(f'<button role="tab" id="t-{k}" data-stage="{k}" aria-controls="s-{k}" aria-selected="{str(i == 0).lower()}"><i>{n}</i><b>{esc(t)}</b></button>'
                   for i, (k, n, t, _, _) in enumerate(STAGES))
    panels = ''.join(f'<article class="fi-text" id="s-{k}" role="tabpanel" aria-labelledby="t-{k}" data-stage="{k}" data-scale="{sc}"{"" if i == 0 else " hidden"}>'
                     f'<h3>{n} · {esc(h)}</h3><p class="chips">{" ".join(chip(c) for c in texts[k][1])} <span class="scale-tag">{esc(SCALE[sc])}</span></p>'
                     f'{texts[k][0]}</article>' for i, (k, n, _, h, sc) in enumerate(STAGES))
    b = d['plasma']['burn']
    nf = d['need']; c1 = d['channels']['variants']['C1']
    body = f'''<header><p class="eyebrow">Simulations · flagship · open problem</p><h1>Fusion Ignition: from nucleus to nozzle</h1>
<p class="lead">How the Wayfarer's Vertex drive is built, switched on and ignited, from one D–³He reaction to {nf["thrust_N"] / 1e6:.1f} MN of
thrust, and where the design fails. The sequence shows what the engine is meant to do; each step also shows what today's models predict.
The drive does not work yet: at its coupled design pulse the engine takes up {X(d["ledger"]["pulse"]["heat_over"])} the heat its radiators can reject
({X(c1["over"])} at full mission power in the steady-plasma study), and its exhaust is {d["ledger"]["pulse"]["exhaust_m_s"] / 1e3:,.0f} of the {d["ledger"]["need"]["exhaust_m_s"] / 1e3:,.0f} km/s needed. Nothing on this page is canon.</p>
<p>{chip("OPEN")} {chip("CALCULATED")} {chip("ILLUSTRATIVE")} · <a href="../fusion/">Fusion engine</a> · <a href="../ignition/">Ignition: what breaks</a> ·
  <a href="../{e["kind_dir"]}/{e["folder"].name}/">the study behind this page</a></p></header>
<section class="ign fi" id="fi" data-stage="need" data-view="concept">
  <div class="fi-stages" role="tablist" aria-label="Stages">{tabs}</div>
  <div class="stage" id="stage">
    <canvas id="fi-view" aria-label="The Vertex drive in 3D, stage by stage; the same numbers are in the text beside it"></canvas>
    <canvas id="fi-2d" class="fi-2d" aria-hidden="true"></canvas>
    <div class="fi-scale" id="scale" aria-live="polite"></div>
    <div class="hud" id="hud" hidden></div>
    <div class="fi-tip" id="tip" hidden></div>
    <div class="evcap" id="evcap" aria-live="polite"></div>
    <div class="fi-ctl" id="fictl" hidden></div>
    <ol class="fi-ladder" id="ladder" aria-hidden="true"><li>100 m</li><li>10 m</li><li>1 m</li><li>1 cm</li><li>100 µm</li><li>1 µm</li><li>1 pm</li><li>10 fm</li><li class="note">uneven steps</li><i></i></ol>
    <div class="gate" id="gate"><button id="load" class="primary">Start the simulation</button>
      <span class="meta">Loads three.js and the engine parts of Explore Ship (about 1.2 MB before compression). The reaction, plasma and ignition stages, the text and the numbers work without it.</span></div>
    <div class="cstatus" id="cstatus" hidden></div>
  </div>
  <div class="itools">
    <span class="nav" role="toolbar" aria-label="Guided presentation"><button id="prev" aria-label="Previous stage">◀</button>
      <button id="play" aria-label="Play">▶</button><button id="next" aria-label="Next stage">▶|</button></span>
    <input type="range" id="scrub" min="0" max="1000" value="0" aria-label="Position in the stage">
    <button id="replay" hidden>Replay the reaction</button>
    <button id="graphs" aria-pressed="false" hidden title="Show the calculations behind this scene">Graphs</button>
    <span class="views" role="group" aria-label="What is shown"><button data-view="concept" aria-pressed="true" title="What the engine is meant to do">Intended</button><button data-view="model" aria-pressed="false" title="What today's models predict">Modeled</button><button data-view="exp" aria-pressed="false" title="Your experimental configuration">Experiment</button></span>
  </div>
  <div class="ign-side fi-side" role="region" aria-label="Stage text, layers and controls">
    <div class="fi-texts">{panels}</div>
    <div class="fi-tools">
      <details class="fi-layers" id="layers"><summary>Layers</summary><div class="fi-toggles">
        <label><input type="checkbox" data-layer="field" checked> Magnetic field</label>
        <label><input type="checkbox" data-layer="fuel" checked> Fuel and propellant</label>
        <label><input type="checkbox" data-layer="paths" checked> Charged-particle paths</label>
        <label><input type="checkbox" data-layer="rad" checked> Photons and neutrons</label>
        <label><input type="checkbox" data-layer="heat" checked> Heat in the hardware</label>
        <label><input type="checkbox" data-layer="problems" checked> Engineering problems</label>
        <label><input type="checkbox" data-layer="cut"> Cutaway</label>
        <label><input type="checkbox" data-layer="ship" checked> Ship (schematic)</label>
        <label><input type="checkbox" data-layer="mirrors" checked> Mirrors and blankets (Heat)</label>
        <label><input type="checkbox" data-layer="cooling" checked> Cooling circuits (Heat)</label>
        <label><input type="checkbox" data-layer="flow" checked> Coolant flow (Heat)</label></div></details>
      <div class="fi-parts" id="parts" hidden></div>
      <div class="fi-lab" id="lab" hidden></div>
      <div class="readouts" id="read" aria-live="polite"></div>
    </div>
  </div>
</section>
<section><h2>The numbers</h2>
<div class="scroll" tabindex="0"><table class="fi-led"><thead><tr><th>Quantity</th><th>Value</th><th>Class · source</th></tr></thead><tbody>{ledger(d)}</tbody></table></div></section>
{ledger_section(d)}
{thermal_section(d)}
<section id="problems"><h2>Engineering problems on this page</h2>
<p>From the compact-engine register (ENG-030 to 038, C1–C4), the thermal study (ENG-040 to 060) and the source study (ENG-061 to 063). An open problem
  stays visible in the simulation: the markers sit on the parts they concern, and each component card lists the problems that name it.</p>
<div class="scroll" tabindex="0"><table class="fi-prob"><thead><tr><th>ID</th><th>Problem</th><th>Required</th><th>Achieved</th><th>Components · stages</th><th>Directions</th><th>Status</th></tr></thead>
<tbody>{problems_table(d)}</tbody></table></div></section>
<section><h2>How the simulation works</h2>
<p>The page runs no physics code. The study's <code>model.py</code> writes every number from the project's own modules: the operating point,
  the engine stations and coils, the vacuum field, the Bosch–Hale reactivities and cross section, the Vertex target-burn model over
  {len(b["rhoR"]) * len(b["Ti"])} settings, test-particle paths in the coil field, and the compact study's energy ledger. The page draws them and
  interpolates between precomputed points. Each statement carries its class:</p>
<ul class="plain">{"".join(f"<li>{chip(k)} {esc(v)}</li>" for k, v in d["classes"].items() if k in CLS)}</ul>
<details><summary>What is not modelled</summary><ul class="plain">
  <li>The driver and the implosion that compress a target to {b["rhoR_design"]:g} g/cm² ({chip("OPEN")}). The burn model starts from an assumed
    hot, dense sphere.</li>
  <li>The plasma's response to the field (detachment, instabilities): the particle paths are test particles in a vacuum field.</li>
  <li>How fusion products heat the hydrogen reaction mass ({chip("SPECULATIVE")}).</li>
  <li>The 2-D nuclei and plasma pictures are drawings: sizes, speeds and counts are chosen to be seen, not to scale.</li>
  <li>The camera passes from metres to femtometres through a labelled change of view, not a true zoom.</li>
</ul></details>
<p class="meta">Data classes: the ship numbers are specification; everything the controls change is simulation state and never changes the
  ship. Compact variants C2–C4 move the cluster 30–36 m aft and are research, not approved geometry.</p></section>'''
    (out_dir / 'index.html').write_text(page('Fusion Ignition · Wayfarer engineering',
                                             'The flagship simulation of the Vertex fusion drive: from the need for an engine to one D-3He reaction and back to thrust, with the modeled failures shown.',
                                             body, 2, revision, built, HEAD, kind='sim', crumb=('Simulations', 'simulations/'),
                                             guide=('fusion-ignition', 'The Vertex drive from the ship down to one nuclear reaction and back to thrust, with what the models predict.',
                                                    'Start, press Play, then switch between Intended and Modeled at Ignition and Losses.', ('Open problems', '#problems'))))
    return True
