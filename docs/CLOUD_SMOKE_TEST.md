# Cloud smoke test: Blender build in Claude Code cloud

Date: 2026-10-20. Branch `claude/blender-smoke-test`, from `main` at `5c54b1e`.
This was a measurement only. No geometry, parameters, baselines or Drive content changed.

Labels: **[measured]** values come from `/usr/bin/time -v`, `du`, `df`, `free` or tool
output. **[guess]** marks an interpretation that was not verified.

## Summary

| Step | Result | Wall time | Peak RSS |
| --- | --- | --- | --- |
| 1 Environment | 4 vCPU, 15 GiB RAM, no GPU | — | — |
| 2 Blender 5.2.2 LTS download, SHA-256 check and unpack | PASS, no host blocked | 16 s download + 32 s unpack | 14 MB |
| 3 Unit tests | **FAIL**: 139 tests, 1 error, 1 skip | 2:08.5 | 58 MB |
| 4 `build.py --target RADIATOR` | Component written, but **exit code 1** in a fresh clone | 13.2 s | 478 MB |
| 5a `pipeline --quick` | **FAIL** at the previews only; spec, build and fingerprint PASS; geometry diff 0 | 1:52.6 | 1.09 GB |
| 5b `pipeline --quick --previews none` | **PASS**, geometry diff 0 | 1:54.3 | 0.82 GB |
| 5c Install Mesa EGL, then render draft previews from the saved assets | PASS: 4 views rendered | 6.6 s apt + 54.4 s render | 1.54 GB |
| 6 `deps install` (MPFB and MakeHuman assets) | PASS | 3:52.6 | 31 MB |

Peak RSS comes from `time -v`: it is the largest single process in the tree, not the
sum. A 5 s `free` sampler during step 5a peaked at 1198 MB used system-wide. **[measured]**

## 1. Environment [measured]

- CPU: 4 × Intel Xeon @ 2.80 GHz (`nproc` = 4)
- RAM: 15 GiB, no swap
- Disk: 252 GB volume. The session had 30 GB available at the start and 28 GB at the end.
- OS: Ubuntu 24.04.5 LTS, kernel 6.18.44
- Python: 3.13.16
- GPU, OpenGL and EGL: no `/dev/dri` and no NVIDIA tools. `libGL.so.1` was present;
  `libEGL.so.1` was **absent** until step 5c. `Xvfb` and `xvfb-run` are installed but
  were not used.
- `/usr/bin/time` was missing. It was installed with `apt-get install time`, and the
  apt mirror was reachable.

## 2. Blender install [measured]

```
mkdir -p ~/blender-dl && cd ~/blender-dl
curl -sS -O https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz \
         -O https://download.blender.org/release/Blender5.2/blender-5.2.2.sha256
grep linux-x64 blender-5.2.2.sha256 | sha256sum -c -     # blender-5.2.2-linux-x64.tar.xz: OK
tar -xf blender-5.2.2-linux-x64.tar.xz -C ~
export WAYFARER_BLENDER=/root/blender-5.2.2-linux-x64/blender   # "Blender 5.2.2 LTS", build 2026-09-15
```

- Tarball: `blender-5.2.2-linux-x64.tar.xz`, 383 MB. It downloaded in 16.4 s and
  unpacked in 31.7 s to 1.2 GB.
- No host was blocked: `download.blender.org` passed through the agent proxy.
- `tools/pipeline.py` reads `WAYFARER_BLENDER` and falls back to `/snap/bin/blender`.

## 3. Unit tests [measured]

```
python3 -m unittest discover -s tests
Ran 139 tests in 127.342s   FAILED (errors=1, skipped=1)
```

- The count is **139, not the expected 135**. **[guess]** Tests were added after the
  135 figure was recorded.
- The skip is the expected maintainer-only check of Drive-capture freshness.
- The error is in
  `test_hooks.DriveInboxTests.test_watched_export_is_kept_on_disk_and_replaced_by_a_summary`.
  - The hook prints nothing, so `output` is `None`.
  - Running the hook directly shows the cause. `drive_sync.export_bytes()`
    (`tools/drive_sync.py:667`) calls `Path(response).is_file()` on the 2.9 kB JSON
    response string. On Python 3.13 that raises
    `OSError: [Errno 36] File name too long`.
  - The hook fails open and logs `drive_inbox hook error (ignored)`.
  - **[guess]** It passes on the workstation because a newer Python's
    `Path.is_file()` returns False for any `OSError`, or because the response there is
    shorter than the filename limit. It is environment-dependent and unrelated to
    Blender. It was not fixed here.

## 4. Single-assembly build [measured]

```
$WAYFARER_BLENDER --background --factory-startup --python-exit-code 1 \
  --python src/wayfarer/build/build.py -- --target RADIATOR
```

- `assets/wayfarer/components/WF_RADIATOR.blend` was written: **528,483 bytes,
  353 objects** (198 MESH, 151 CURVE, 4 EMPTY). `WF_THERMAL.blend` was written too:
  1,283,951 bytes, 1,524 objects.
- **Exit code 1.** After a targeted build, `build.py` always rebuilds the vehicle file
  and links every subsystem `.blend`. In a fresh clone those files do not exist yet:
  `OSError: load: .../subsystems/WF_STRUCTURE.blend failed to open blend file`.
  `--target` therefore needs one prior full build. This is expected in a fresh
  checkout, not a cloud limitation.
- Object counts came from a small `bpy` script, run with Blender on each file.
  `python3 tools/workflow.py report` also worked (exit 0). It summarizes the spec
  rather than the partial build.

## 5. Whole ship: `pipeline --quick` [measured]

### 5a. Default run with draft previews

```
python3 tools/workflow.py pipeline --quick        # run dir runs/20261020T140805Z-quick
steps: spec:PASS(5.5s) build:PASS(82.0s) fingerprint:PASS(9.1s) preview-coast:FAIL(15.5s)
geometry_diff vs references/baseline_m8_exterior: PASS, changed 0, added 0, removed 0, links_changed 0
```

- The draft Workbench previews **did not render headless**. Blender aborted with exit
  code -6 (SIGABRT) after `Couldn't open libEGL.so.1: libEGL.so.1: cannot open shared object file`.
- Blender 5.x headless Workbench needs an EGL library. Software rendering through Mesa
  is enough; no X server is needed.
- Disk: `assets/` held 27 `.blend` files and 19 MB after the build. Each run directory
  is about 3.4 MB.

### 5b. Without previews

```
python3 tools/workflow.py pipeline --quick --previews none
result PASS — spec:PASS(5.6s) build:PASS(99.3s) fingerprint:PASS(8.7s); geometry diff changed 0
```

The build took 99 s instead of 82 s because the apt install below ran at the same time.

### 5c. One display-stack attempt with Mesa EGL, no X server

```
apt-get install -y --no-install-recommends libegl1 libegl-mesa0 libgl1-mesa-dri   # 6.6 s, Mesa 25.2.8
$WAYFARER_BLENDER --background --factory-startup --python-exit-code 1 \
  --python src/wayfarer/presentation/preview.py -- --root $PWD --state COAST --size 512 --quality draft --out <scratch>
```

- Exit 0 in 54.4 s, peak RSS 1.54 GB.
- It rendered side, top, three-quarter and body_detail, at 217–254 kB per PNG.
- The three-quarter image was opened and shows the ship correctly.
- The log shows harmless `EGL_BAD_MATCH` warnings. **[guess]** Rendering ran on Mesa
  llvmpipe on the CPU.
- This used `preview.py` on the saved assets; the pipeline was not rerun with previews
  after installing EGL. **[guess]** A rerun of `pipeline --quick` would now PASS end to
  end in about 2:50.
- The renders stayed in the session scratch directory and were not committed.

## 6. `deps install` [measured]

```
python3 tools/workflow.py deps install
{"mpfb": "installed into ~/.cache/wayfarer/external/blender/user/extensions/user_default/mpfb",
 "makehuman_system_assets": "installed into .../mpfb/data"}
```

- 3:52.6 wall time; `~/.cache/wayfarer` grew to 676 MB.
- Hosts reached: `extensions.blender.org` and `files2.makehumancommunity.org`.
  None were refused.
- The character build and the full pipeline were skipped, as instructed.

## Disk use [measured]

| Item | Size |
| --- | --- |
| Blender unpacked | 1.2 GB |
| Blender tarball | 366 MB (can be deleted) |
| `~/.cache/wayfarer` (MPFB) | 676 MB |
| `assets/` after builds, including milestone backups | 36 MB |
| `runs/` with two quick runs | 6.7 MB |
| Session total | about 3.2 GB of the per-session allowance, including the apt packages (`df` Used went from 8.8 to 12 GB) |

## Blocked hosts

None. All of these were reachable: `download.blender.org`, the Ubuntu apt mirror,
`extensions.blender.org` and `files2.makehumancommunity.org`. **[measured]**

## Recommendation

- **Quick loop: yes.** **[measured]** Each whole-ship `pipeline --quick` took about
  1:53 on 4 vCPUs with under 1.6 GB RSS and a few tens of MB of output. It needs
  Blender 5.2.2 from the official tarball plus `libegl1 libegl-mesa0 libgl1-mesa-dri`
  for the draft previews. Put both in the environment setup script so every session
  has them.
- **`--target` builds** work only after one full build in the same container.
  Containers are ephemeral, so every session begins with a full build, about 1.5 min.
- **Previews:** draft Workbench works with Mesa software EGL. **[guess]** `material`
  (Eevee) will probably work but slowly. Cycles `review` and `look` on 4 CPU cores will
  be slow, likely several minutes per view. Not measured.
- **Full pipeline: probably yes, but not measured.** **[guess]** The added inspection
  and Cycles COAST and HIGH_POWER previews fit in RAM, but CPU-only Cycles makes it the
  slowest step. Measure it in a later session before relying on it.
- **Before trusting cloud runs**, fix or explain the `test_hooks` failure under
  Python 3.13 so the unit-test step is green.
