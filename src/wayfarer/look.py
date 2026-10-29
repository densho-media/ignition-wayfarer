"""FUT-003 step 1: the S004 look ([look], ART-S004-2026-10-10, docs/SURFACE_BRIEF.md), a presentation layer over the generated materials.
surfaces() gives each overridden material its base colour, roughness and metallic by surface class; lights() gives each emitter material its
light class: the colour of its temperature, the emission strength Cycles renders from the geometry and the point light a runtime hangs off
it. Applied in memory by common.apply_look (entry_preview --look, the runtime export); the saved assets keep their review colours."""
import math


def kelvin_rgb(kelvin):
    """Linear RGB of a blackbody at kelvin, brightest channel 1 (Tanner Helland's sRGB fit, 1000-40000 K, decoded to linear)."""
    t = kelvin/100.0
    r = 255.0 if t <= 66 else 329.698727446*(t-60)**-0.1332047592
    g = 99.4708025861*math.log(t)-161.1195681661 if t <= 66 else 288.1221695283*(t-60)**-0.0755148492
    b = 255.0 if t >= 66 else 0.0 if t <= 19 else 138.5177312231*math.log(t-10)-305.0447927307
    srgb = [min(max(v, 0.0), 255.0)/255.0 for v in (r, g, b)]
    lin = [c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4 for c in srgb]
    return tuple(round(c/max(lin), 4) for c in lin)


def surfaces(s):
    """{material name (without WF_MAT_): {color, roughness, metallic, cls}} for every surface the look overrides."""
    k = s['look']; out = {}
    for name in k['physics_locked']:
        out[name] = dict(color=tuple(k['proxy_grey']), roughness=k['physics_roughness'], metallic=0.0, cls='physics_locked')
    for name in k['closures']:
        out[name] = dict(color=tuple(k['closure_grey']), roughness=k['physics_roughness'], metallic=0.0, cls='physics_locked')
    for name, (r, g, b, rough, metal) in k['surfaces'].items():
        if name in out:
            raise ValueError(f'look: {name} is both physics-locked and engineering-flexible')
        out[name] = dict(color=(r, g, b), roughness=rough, metallic=metal, cls='engineering_flexible')
    return out


def lights(s):
    """{emitter material name: {cls, color, strength, energy, range_m, offset_m}}: the light class of each emitting surface."""
    L = s['look']['lights']; out = {}
    for name, cls in L['emitters'].items():
        c = L[cls]
        out[name] = dict(cls=cls, kelvin=c['kelvin'], color=kelvin_rgb(c['kelvin']), strength=c['strength'], energy=c['energy'],
                         range_m=c['range_m'], offset_m=L['offset_m'])
    return out


def grey_body_luminance(kelvin, emissivity):
    """Luminance (cd/m2) of a grey body: 683 lm/W times Planck's spectral radiance weighted by the CIE photopic curve (Gaussian fit),
    380-780 nm in 1 nm steps."""
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23; total = 0.0
    for n in range(380, 781):
        lam = n*1e-9
        total += 2*h*c*c/lam**5/(math.exp(h*c/(lam*k*kelvin))-1)*1.019*math.exp(-285.4*(n/1000-0.559)**2)*1e-9
    return 683.0*emissivity*total


def exterior(s):
    """The First Ignition exterior light ([look.exterior]): the sun's direction (ship to sun) and strength, and the hot face's colour and
    Cycles emission strength. A white diffuse surface under a sun of strength E renders E/pi and an emission of strength S renders S, so a
    grey body of luminance L beside a sunlit surface under illuminance Ev emits S = E L / (Ev Y), Y the luminance of its unit colour."""
    x = s['look']['exterior']; r = s['radiators']
    a, z = math.radians(x['sun_from_aft_deg']), math.radians(x['sun_azimuth_deg'])
    sun = (-math.cos(a), math.sin(a)*math.cos(z), math.sin(a)*math.sin(z))
    T, eps = r['temperature']['value'], r['emissivity']['value']
    color = kelvin_rgb(T); L = grey_body_luminance(T, eps); Y = .2126*color[0]+.7152*color[1]+.0722*color[2]
    return dict(sun=sun, sun_strength=x['sun_strength'], kelvin=T, emissivity=eps, color=color, luminance_cd_m2=L,
                strength=x['sun_strength']*L/(x['sun_illuminance_lx']*Y), sunlit_ratio=L/(x['grey'][1]*x['sun_illuminance_lx']/math.pi))


def runtime_exterior(s, hot_state):
    """The same exterior light for the Godot flight timeline (manifest look.exterior): runtime axes (x, z, -y), Blender units kept so the
    runtime matches the stills. Godot's light energy E renders a white diffuse surface E (it carries the pi a Cycles sun divides by), an
    emission's energy multiplier renders itself, so the sun's energy is the Cycles strength over pi and the hot face keeps its Cycles
    strength. hot_state is the radiator thermal_state value at which the hot face emits (FIRST_IGNITION's, the WORKING 1800 K)."""
    x = s['look']['exterior']; e = exterior(s); sx, sy, sz = e['sun']
    return dict(status='PROTOTYPE', source_ref='hero_asset_order', sun_runtime=[sx, sz, -sy], sun_energy=e['sun_strength']/math.pi,
                sun_angular_deg=x['sun_angular_deg'], exposure=2.0**x['exposure_ev'], grey=x['grey'], roughness=x['roughness'],
                hot_face=x['hot_face'], hot_color=e['color'], hot_energy=e['strength'], hot_thermal_state=hot_state, kelvin=e['kelvin'],
                emissivity=e['emissivity'], sunlit_ratio=e['sunlit_ratio'], display_emitters=x['display_emitters'],
                hidden_prefixes=x['hidden_prefixes'], hidden_kinds=x['hidden_kinds'])


def runtime_grammar(s):
    """Phase 4 S9: the selected exterior grammar for the Godot runtime exterior (manifest look.exterior.grammar), the same data the
    Blender grammar look reads (hero_preview.dress(grammar=True)): families, the material-prefix rules (first match wins; 'none' keeps the
    material's own colour; unmatched stays proxy grey; Prod_ materials keep their exported pack finishes), the ILLUSTRATIVE ram-face
    tile-and-repair shading, the fractal shielding that replaces it when selected (fractal_shield.runtime) and the switchable post-voyage
    wear layer. Colours are linear. Presentation only."""
    import fractal_shield
    X = s['production']['exterior']
    return dict(status=X['status'], source_ref=X['evidence_ref'], grammar=X['grammar'], families=X['families'],
                rules=[[list(r['prefixes']), r['family']] for r in X['ship_families']], ram_face=X['ram_face'], wear=X['wear'],
                fractal_shield=fractal_shield.runtime(s))


if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s, *_ = load()
    print(json.dumps({'surfaces': len(surfaces(s)), 'lights': lights(s), 'exterior': exterior(s)}, indent=1))
