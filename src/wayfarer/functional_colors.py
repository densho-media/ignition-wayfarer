"""Functional review colours (owner brief 2026-11-01). Pure: the palette, the Blender collection colour tag nearest each function, and the rule
that assigns every generated object to one function from its asset, name, kind and species. common.save applies it to every object's
viewport colour (obj.color, shown by Solid shading with Object colour; production materials are untouched) and to the collection tags.

Every function also has an explicit name, so identification never depends on colour alone (the legend: docs/MODEL.md "Functional review
colours", references/evidence and the review file's FUNCTIONAL_COLOR_LEGEND text).
"""

# function key -> (label, RGBA viewport colour, nearest Blender collection tag)
# Blender tags: COLOR_01 red, 02 orange, 03 yellow, 04 green, 05 blue, 06 violet, 07 pink, 08 brown; NONE uncoloured.
PALETTE = {
    'STRUCTURE': ('Primary structure and supports', (0.56, 0.56, 0.58, 1.0), 'COLOR_08'),
    'SHIELD': ('Shield and dust protection', (0.80, 0.58, 0.18, 1.0), 'COLOR_03'),
    'SENSORS_COMMS': ('EYE, sensors and communications', (0.10, 0.80, 0.86, 1.0), 'COLOR_05'),
    'HABITAT': ('Habitat and crew transfer', (0.24, 0.70, 0.30, 1.0), 'COLOR_04'),
    'HYDROGEN': ('Hydrogen storage and feed', (0.14, 0.32, 0.92, 1.0), 'COLOR_05'),
    'DEUTERIUM': ('Deuterium storage and feed', (0.02, 0.56, 0.52, 1.0), 'COLOR_05'),
    'HELIUM3': ('Helium-3 storage and feed', (0.56, 0.30, 0.88, 1.0), 'COLOR_06'),
    'HOT_RADIATOR': ('Hot radiator circuit (1800 K drive)', (0.86, 0.12, 0.10, 1.0), 'COLOR_01'),
    'WARM_RADIATOR': ('Warm radiator circuit (440 K machinery)', (0.96, 0.50, 0.10, 1.0), 'COLOR_02'),
    'LOW_RADIATOR': ('Low-temperature radiator circuit (300 K)', (0.66, 0.84, 0.98, 1.0), 'COLOR_05'),
    'MAIN_PROPULSION': ('Main propulsion', (0.86, 0.16, 0.76, 1.0), 'COLOR_07'),
    'RCS': ('RCS and manoeuvring (incl. momentum storage)', (0.96, 0.88, 0.14, 1.0), 'COLOR_03'),
    'POWER': ('Electrical power and storage', (0.27, 0.22, 0.64, 1.0), 'COLOR_06'),
    'SERVICE': ('Docking, EVA and service equipment', (0.96, 0.91, 0.76, 1.0), 'COLOR_03'),
}

ASSET_DEFAULT = {
    'STRUCTURE': 'STRUCTURE', 'HULL': 'STRUCTURE', 'PROPULSION': 'MAIN_PROPULSION', 'NOZZLE': 'MAIN_PROPULSION', 'SHIELDING': 'MAIN_PROPULSION',
    'DEBUG_MAGNETICS': 'MAIN_PROPULSION', 'DEBUG_SEPARATRICES': 'MAIN_PROPULSION', 'DEBUG_OPTICS': 'MAIN_PROPULSION',
    'POWER_STORAGE': 'POWER', 'STORAGE': 'STRUCTURE', 'THERMAL': 'HOT_RADIATOR', 'RADIATOR': 'HOT_RADIATOR',
    'FORWARD_SHIELD': 'SHIELD', 'EYE': 'SENSORS_COMMS', 'SERVICE': 'SERVICE', 'DRONES': 'SERVICE',
    'HABITAT': 'HABITAT', 'HABITAT_A': 'HABITAT', 'HABITAT_B': 'HABITAT', 'ROTOR_INTERFACE': 'HABITAT', 'CREW_TRANSFER': 'HABITAT',
    'RING_SECTOR': 'HABITAT', 'INTERIOR_GARDEN': 'HABITAT', 'INTERIOR_HABITATION': 'HABITAT', 'INTERIOR_WORK': 'HABITAT',
}
DETAIL_DEFAULT = {'M8_BROW_AFT': 'SHIELD', 'M8_CROWN_RIM': 'SHIELD', 'RAD_FRAME': 'HOT_RADIATOR', 'SP_CASING': 'STRUCTURE'}
SPECIES = {'hydrogen': 'HYDROGEN', 'deuterium': 'DEUTERIUM', 'helium-3': 'HELIUM3'}


def asset_key(collection_name):
    """'WF_STORAGE' -> 'STORAGE'; 'WF_DETAIL_M7_ENT' -> 'DETAIL_M7_ENT'."""
    return collection_name[3:] if collection_name.startswith('WF_') else collection_name


def classify(asset, name, kind='', species='', section='', bank=''):
    """The function key of one object. Name/kind rules first (they cross assets), then the asset default."""
    n = name; k = kind or ''
    if asset.startswith('DETAIL_'):
        d = asset[len('DETAIL_'):]
        return DETAIL_DEFAULT.get(d, 'HABITAT')
    if k in ('scale_reference', 'first_person_camera') or n.startswith(('WF_SIM', 'Human_', 'CAM_')):
        return None
    # radiator sections and baffles
    if n.startswith('Radiator_Zone_'):
        return 'LOW_RADIATOR' if '_LOW_' in n else 'WARM_RADIATOR'
    if n.startswith('Radiator_Baffle_'):
        return 'STRUCTURE'
    # manoeuvring and momentum storage
    if n.startswith('Ext_RCS') or k == 'rcs_thruster' or n.startswith('Body_CMG'):
        return 'RCS'
    # sensors and communications
    if n.startswith(('Ext_HGA', 'Ext_Optical', 'Ext_Nav', 'EYE_', 'Alt_Eye', 'Eye_Service', 'Survival_RF', 'Survival_Lasercom', 'Survival_Star')) or k in ('eye_facet', 'comms_antenna'):
        if not (n.startswith('Alt_Eye') and k in ('shield_truss', 'disruptor_post')):
            return 'SENSORS_COMMS'
    # docking, EVA and service equipment
    if n.startswith(('Ext_Dock', 'Ext_Airlock', 'Ext_EVA', 'Ext_Beacon', 'Dock_', 'Airlock_', 'Storeroom_', 'Survival_Crawler', 'Drone_', 'DOCK_', 'IF_DOCK', 'IF_AIRLOCK')) or k in ('nav_light',):
        return 'SERVICE'
    if n.startswith(('Refuge_', 'Crew_Refuge', 'Survival_Refuge')):
        return 'HABITAT'
    if n.startswith(('Brayton_', 'Survival_Cartridge', 'Main_Battery', 'Pulse_Bank', 'Survival_Reserve', 'Nozzle_Pickup')) or k == 'generator_proxy':
        return 'POWER'
    if n.startswith('H2_INJECTION'):
        return 'HYDROGEN'
    # propellant storage and feed: by species; supports and body frames are structure
    if asset == 'STORAGE':
        if k in ('fuel_support', 'body_frame'):
            return 'STRUCTURE'
        if species in SPECIES:
            return SPECIES[species]
        if n.startswith(('Feed_Run_Tank_01', 'CRYO_FEED_D2', 'IF_CRYO_D2')):
            return 'DEUTERIUM'
        if n.startswith(('Feed_Run_Tank_02', 'CRYO_FEED_HE3', 'IF_CRYO_HE3')):
            return 'HELIUM3'
        if n.startswith(('Feed_Run_Tank_03', 'Feed_Run_Tank_04', 'CRYO_FEED_H2', 'IF_CRYO_H2')):
            return 'HYDROGEN'
        for tag, f in (('_He3', 'HELIUM3'), ('_D2', 'DEUTERIUM'), ('_H2', 'HYDROGEN'), ('HE3', 'HELIUM3'), ('D2', 'DEUTERIUM'), ('H2', 'HYDROGEN')):
            if tag in n:
                return f
        return 'STRUCTURE'
    if asset == 'FORWARD_SHIELD':
        if k in ('bypass_collar', 'shield_truss', 'truss_node', 'sector_frame', 'sector_keel', 'sector_tie', 'shield_mount', 'shield_spine_column', 'disruptor_post'):
            return 'STRUCTURE'
        return 'SHIELD'
    if asset == 'SERVICE' and n.startswith('Casing_'):
        return 'STRUCTURE'
    if asset == 'THERMAL' and k in ('casing_boot',):
        return 'STRUCTURE'
    return ASSET_DEFAULT.get(asset, 'STRUCTURE')


def subgroup(asset, name, function, bank=''):
    """Functional sub-collection inside the STORAGE and THERMAL assets (owner brief: forward/aft storage, hot/warm/cold circuits); None keeps
    the object where it is."""
    if asset == 'STORAGE':
        if function in ('HYDROGEN', 'DEUTERIUM', 'HELIUM3'):
            if name.startswith(('Fuel_Transfer', 'CRYO_FEED', 'Feed_Run', 'IF_')):
                return 'STORAGE_FEED_' + function
            return f"STORAGE_{(bank or 'aft').upper()}_BANK_{function}"
        return 'STORAGE_' + function
    if asset == 'THERMAL':
        return {'HOT_RADIATOR': 'THERMAL_HOT_CIRCUIT', 'WARM_RADIATOR': 'THERMAL_WARM_CIRCUIT', 'LOW_RADIATOR': 'THERMAL_LOW_CIRCUIT'}.get(function, 'THERMAL_BREAKS_AND_SUPPORTS')
    return None


def legend_rows():
    return [dict(key=k, label=v[0], rgba=v[1], collection_tag=v[2]) for k, v in PALETTE.items()]


def legend_text():
    lines = ['WAYFARER functional review colours (owner brief 2026-11-01). Viewport: Solid shading, Color = Object.',
             'Production render materials are unchanged. Collection tags use the nearest of Blender\'s eight tag colours.', '']
    for r in legend_rows():
        rgb = ', '.join(f'{c:.2f}' for c in r['rgba'][:3])
        lines.append(f"{r['key']:<16} {r['label']:<48} RGB({rgb})  tag {r['collection_tag']}")
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    print(legend_text())
