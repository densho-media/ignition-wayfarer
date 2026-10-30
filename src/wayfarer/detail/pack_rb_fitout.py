"""Detail pack rb_fitout (docs/MODULES.md): ring B's three sectors take ring A's cultural passes (RA1.BRT, RA2.WRK, RA3.GDN) by one
definition. Each builder runs ring A's builder and re-tags its elements to the ring B assembly (names RA* -> RB*); each check is ring
A's check. WF_HABITAT links the assets at ring B's sector instances (2, k). Owned with data/detail/rb_fitout.toml.
"""
import pack_ra1_berths as ra1
import pack_ra2_work as ra2
import pack_ra3_garden as ra3
import production_detail as pd

SOURCES = {'RB1.BRT': (ra1.berth_elements, ra1.berth_check, 'RA1_', 'RB1_'),
           'RB2.WRK': (ra2.work_elements, ra2.work_check, 'RA2_', 'RB2_'),
           'RB3.GDN': (ra3.garden_elements, ra3.garden_check, 'RA3_', 'RB3_')}


def retag(asm, els, old, new):
    """Ring B's copy: the assembly and names re-tagged, a berth number A1-k read B1-k."""
    out = [dict(e, assembly=asm, name=e['name'].replace(old, new, 1)) for e in els]
    for e in out:
        if e.get('text', '').startswith('A1-'):
            e['text'] = 'B1-'+e['text'][3:]
    return out


for _asm, (_build, _check, _old, _new) in SOURCES.items():
    pd.builder(_asm)(lambda s, b=_build, a=_asm, o=_old, n=_new: retag(a, b(s), o, n))
    pd.CHECKS[_asm] = lambda s, els, c=_check: c(s, els)
