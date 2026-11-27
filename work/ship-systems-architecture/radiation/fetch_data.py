"""Fetch the ENDF/B-VIII.0 (NNDC processing, OpenMC HDF5) nuclides the ISSA radiation workflow needs and write cross_sections.xml.
Data are NOT committed (643 MB); the manifest (names, sizes, sha256) is. Run with the OpenMC environment's python:

    /opt/mf/envs/omc/bin/python work/ship-systems-architecture/radiation/fetch_data.py /opt/nd/endfb80

Source: openmc-data-storage/ENDF-B-VIII.0-NNDC on GitHub (raw.githubusercontent.com; large files via media.githubusercontent.com LFS).
The official openmc.org / anl.box.com libraries are the same evaluation but were not reachable from the cloud container."""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

NEUTRON = ['H1', 'H2', 'He3', 'He4', 'Li6', 'Li7', 'Be9', 'B10', 'B11', 'C12', 'C13', 'N14', 'N15', 'O16', 'Al27', 'Cr52', 'Fe54', 'Fe56',
           'Fe57', 'Ni58', 'Mo92', 'Mo95', 'Mo96', 'Mo98', 'W182', 'W183', 'W184', 'W186', 'U234', 'U235', 'U238']
PHOTON = ['H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'Al', 'Cr', 'Fe', 'Ni', 'Mo', 'W', 'U']
RAW = 'https://raw.githubusercontent.com/openmc-data-storage/ENDF-B-VIII.0-NNDC/main/h5_files'
LFS = 'https://media.githubusercontent.com/media/openmc-data-storage/ENDF-B-VIII.0-NNDC/main/h5_files'


def get(kind, name, out):
    p = out/kind/f'{name}.h5'; p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists() or p.read_bytes()[:4] != b'\x89HDF':
        urllib.request.urlretrieve(f'{RAW}/{kind}/{name}.h5', p)
        if p.read_bytes()[:4] != b'\x89HDF':                       # a Git LFS pointer: fetch the media object
            urllib.request.urlretrieve(f'{LFS}/{kind}/{name}.h5', p)
    b = p.read_bytes(); return dict(file=f'{kind}/{name}.h5', bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def main(out):
    import openmc.data
    out = Path(out); man = [get('neutron', n, out) for n in NEUTRON]+[get('photon', e, out) for e in PHOTON]
    lib = openmc.data.DataLibrary()
    for m in man:
        lib.register_file(out/m['file'])
    lib.export_to_xml(out/'cross_sections.xml')
    (Path(__file__).parent/'data_manifest.json').write_text(json.dumps(dict(library='ENDF/B-VIII.0 (NNDC, OpenMC HDF5)', files=man), indent=1))
    print(len(man), 'files', sum(m['bytes'] for m in man)/1e6, 'MB')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/opt/nd/endfb80')
