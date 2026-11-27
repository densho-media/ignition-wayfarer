# ISSA radiation-transport capability (Phase IV-B)

Status: **capability established, not validated for Wayfarer.** Nothing here approves a shield, a district or a crew dose.
Results are labelled TRANSPORT-INFORMED on the ISSA page: one-dimensional, surrogate source, no structure.

## What runs

| Item | Pinned version | Where |
| --- | --- | --- |
| Solver | OpenMC 0.15.3 (commit 27e38e8), MIT licence | conda-forge, env `omc` under Miniforge (`/opt/mf`) |
| Python stack | Python 3.12.16, numpy 2.5.5, h5py 3.16.0 | same env |
| Nuclear data | ENDF/B-VIII.0, NNDC evaluation in OpenMC HDF5 (public) | `/opt/nd/endfb80`, 46 files, ~643 MB, sha256 in `data_manifest.json` |
| Hardware used | 4 CPU threads, 15 GB RAM | cloud container |

Install time ~3 min (env ~0.9 GB), data fetch ~2 min. Godiva runs in 5 s; the Wayfarer workflow (`wayfarer_rt.py`) in ~3 min.

## Procedure (cloud container, workstation or CI)

```bash
# 1. solver (no pip wheel exists for OpenMC; use conda-forge)
curl -L -o mf.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash mf.sh -b -p /opt/mf
/opt/mf/bin/mamba create -y -n omc -c conda-forge "openmc=0.15.3" python=3.12
# 2. data (openmc.org and anl.box.com are blocked in the cloud container; the GitHub mirror works)
/opt/mf/envs/omc/bin/python work/ship-systems-architecture/radiation/fetch_data.py /opt/nd/endfb80   # data + cross_sections.xml
git diff --exit-code work/ship-systems-architecture/radiation/data_manifest.json                     # rewritten manifest must match (sha256)
# 3. run
export PATH=/opt/mf/envs/omc/bin:$PATH OPENMC_CROSS_SECTIONS=/opt/nd/endfb80/cross_sections.xml
python work/ship-systems-architecture/radiation/bench.py         # -> results/phase4_rad_bench.json
python work/ship-systems-architecture/radiation/wayfarer_rt.py   # -> results/phase4_rad_wayfarer.json
python3 work/ship-systems-architecture/phase4/study4.py          # consumes both
```

Run directories go to `$RAD_RUNS` (default `/tmp/issa_rad`). Nuclear data, statepoints and run directories never enter Git
(the repository is public and the library is 0.6 GB); only the small JSON summaries and the manifest are committed. CI does not run
transport: it is a study tool, run on demand, outside the production pipeline (AGENTS.md: nothing in CI reads `work/`).

## Five levels, kept apart

| Level | Status | Evidence |
| --- | --- | --- |
| 1 Installation | done | versions above, manifest hashes |
| 2 Benchmark execution | done | B1 Godiva (ICSBEP HEU-MET-FAST-001) k = 0.99994 ± 0.00049 (−6 pcm); B2 uncollided 2 MeV n through 10 cm Fe vs the library Σt, +0.01 %; B3 uncollided 1 MeV γ through 5 cm Fe vs NIST XCOM, −0.3 % against the no-coherent attenuation (Rayleigh events are not collisions in the tally) |
| 3 Convergence | partial | eigenvalue σ 49 pcm; slab tallies < 1 %; deep-penetration points (80 cm LiH) are statistics-limited: weight windows or a mesh-based variance reduction are needed before deep shields are quoted |
| 4 Applicability | limited | surrogate homogenised fast core (UN 93 %, Li-7, Mo, BeO; not a design), 1-D slabs with reflective sides, no blades, casing, tank structure or streaming paths |
| 5 Engineering validation | not done | needs a 3-D model of the district, blades and tank farm, a real core description, shielding benchmarks (SINBAD / ICSBEP shielding sets) and independent review |

## Wayfarer interface

- Geometry comes from the shared pure modules (`fuel_storage.tanks`, `radiator_zones`, `thermal_geometry`, the EPS-G1 envelopes), never from
  visual Blender meshes. A 3-D model builds CSG cells from those numbers.
- Engineering materials (UN, Li-7, Mo, BeO, LiH, W, Al, liquid He-3 in `wayfarer_rt.mats()`) are separate from the PMDS visual appearances.
- Applications in reach with the same workflow: crew dose behind the shadow shield, scatter from the blades toward the tank farm and the
  rings, electronics dose in the district, He-3 3 K heating, activation and shutdown dose for maintenance.

## First results (TRANSPORT-INFORMED)

- Surrogate core: k 1.134; 0.94 neutrons and 1.01 photons leak per fission; mean leak energies 0.65 and 0.88 MeV.
- W 5 cm + LiH: neutron number relaxes over ~7.7 cm of LiH, secondary capture gammas over ~33 cm: beyond ~40 cm the gamma term dominates,
  so a shield needs a heavy layer behind the LiH, not only in front.
- He-3 tank layer (2 cm Al + 50 cm liquid He-3): each incident leakage neutron deposits 1.01 MeV in the He-3 (He-3(n,p)T, Q 764 keV,
  essentially every neutron captured); photons leave ~55 % of their energy in the warm wall and ~45 % in the He-3.

## Not claimed

No validated dose, no shield approval, no core design, no final district. Transport is the mandatory gate for those claims (owner, DR3-06).
