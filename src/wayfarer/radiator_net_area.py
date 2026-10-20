"""Pure net-emitting-area accounting for one radiator blade (AFT-011, AFT-012, Q12-Q14, Q52). The major bay joints
(07_PRIMARY_STRUCTURE A42, Q13) and the cooler ~3 m root band (A44, Q14) are non-emitting. The built blade is the gross planform
radiators.physical_area (thermal_geometry.blade), which the owner accepts as built (Q52 option D, 07!A58): its net area at the
narrow, working and wide seam is the as-built net area the thermal formulas use, a little under the nominal 5,000 m2
(radiators.nominal_net_area). Stdlib only; callers pass the spec mapping or plain numbers."""
import thermal_geometry


def net_area(length, width, joints, joint_w, band):
    """Emitting area of a gross length x width rectangle after `joints` full-width joint strips of joint_w and one root band of `band`
    (the strips and the band overlap once per joint, which the product form handles exactly)."""
    if not (length > joints*joint_w and width > band >= 0 and joints >= 0 and joint_w >= 0):
        raise ValueError('Joints and root band must fit inside the blade planform')
    return (length-joints*joint_w)*(width-band)


def as_built(s):
    """Net one-face hot area per blade of the built blade, ordered [narrow, working, wide] seam, and the shortfall from the nominal
    target (07!D61:D63)."""
    r = s['radiators']
    b = thermal_geometry.blade(r['physical_area']['value'], r['root_radius']['value'], r['outer_radius']['value'])
    joints, band, bj = r['geometry']['major_bays']-1, r['root_band']['width_m'], r['bay_joints']
    widths = [bj['width_low_m'], bj['width_working_m'], bj['width_high_m']]
    net = [net_area(b['length_m'], b['width_m'], joints, w, band) for w in widths]
    return {'joint_width_m': widths, 'net_area_m2': net, 'nominal_shortfall_m2': [r['nominal_net_area']['value']-n for n in net]}


def working_net_area(s):
    """As-built net one-face hot area per blade at the working seam width."""
    return as_built(s)['net_area_m2'][1]
