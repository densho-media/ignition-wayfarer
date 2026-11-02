#!/bin/bash
# Installs the Wayfarer pipeline toolchain in a Linux container (Claude Code cloud sessions, any fresh Ubuntu box):
#   Blender  - the CI pin in .github/workflows/web-explorer.yml (BLENDER_VERSION / BLENDER_SHA256), linked as /snap/bin/blender
#   Godot    - the editor pin in tools/web_play.py (GODOT), linked as /snap/bin/godot-4
#   MPFB     - the required character dependencies of assets/external/manifest.toml (workflow.py deps fetch + install)
# Every download is checksum-verified and cached under ~/.cache/wayfarer, so a second run only re-links and returns.
# Runs from the SessionStart hook (.claude/hooks/session-start.sh) or as the cloud environment's setup script.
# WAYFARER_SKIP_CHARACTERS=1 leaves out MPFB.
set -euo pipefail

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$root"
cache="${WAYFARER_TOOL_CACHE:-$HOME/.cache/wayfarer}"
bindir="${WAYFARER_BIN_DIR:-/snap/bin}"
mkdir -p "$cache" "$bindir"
log() { echo "[wayfarer-toolchain] $*" >&2; }
sudo=""; [ "$(id -u)" = 0 ] || sudo="sudo"

# 1. Runtime libraries Blender and headless Godot load (the same list CI installs).
libs=(libegl1 libgl1 libxi6 libxkbcommon0 libxxf86vm1 libxfixes3 libxrender1 libsm6 libfontconfig1)
missing=()
for p in "${libs[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
if [ ${#missing[@]} -gt 0 ]; then
  log "apt: ${missing[*]}"
  export DEBIAN_FRONTEND=noninteractive
  $sudo apt-get install -y -qq --no-install-recommends "${missing[@]}" >/dev/null 2>&1 \
    || { $sudo apt-get update -qq >/dev/null && $sudo apt-get install -y -qq --no-install-recommends "${missing[@]}" >/dev/null; }
fi

# 2. Blender, pinned by CI.
wf=.github/workflows/web-explorer.yml
bv=$(sed -n 's/^ *BLENDER_VERSION: *//p' "$wf" | tr -d "'\" ")
bs=$(sed -n 's/^ *BLENDER_SERIES: *//p' "$wf" | tr -d "'\" ")
bh=$(sed -n 's/^ *BLENDER_SHA256: *//p' "$wf" | tr -d "'\" ")
bdir="$cache/blender-$bv-linux-x64"
if [ ! -x "$bdir/blender" ]; then
  tarball="$cache/blender-$bv-linux-x64.tar.xz"
  log "downloading Blender $bv"
  curl -sSfL --retry 4 -o "$tarball.part" "https://download.blender.org/release/Blender$bs/blender-$bv-linux-x64.tar.xz"
  echo "$bh  $tarball.part" | sha256sum -c --status - || { rm -f "$tarball.part"; log "Blender SHA-256 mismatch"; exit 1; }
  rm -rf "$bdir.part"; mkdir -p "$bdir.part"
  tar -xf "$tarball.part" -C "$bdir.part" --strip-components=1
  mv "$bdir.part" "$bdir"; rm -f "$tarball.part"
fi
ln -sfn "$bdir/blender" "$bindir/blender"

# 3. Godot editor, pinned by tools/web_play.py (same cache folder and SHA-512; export templates stay on demand there).
python3 - <<'PY'
import sys, zipfile
sys.path.insert(0, 'tools')
import web_play as w
editor = w.CACHE / f"Godot_v{w.GODOT['tag']}_linux.x86_64"
if not editor.exists():
    name, digest = w.GODOT['editor']; w.CACHE.mkdir(parents=True, exist_ok=True); archive = w.CACHE / name
    print(f'[wayfarer-toolchain] downloading Godot {w.GODOT["version"]}', file=sys.stderr)
    w.fetch(w.GODOT['release'] + name, archive)
    if w.sha(archive, 'sha512') != digest:
        archive.unlink(); sys.exit(f'{name}: SHA-512 mismatch (deleted)')
    with zipfile.ZipFile(archive) as z:
        z.extract(editor.name, w.CACHE)
    editor.chmod(0o755); archive.unlink()

PY
gdir="${WAYFARER_GODOT_CACHE:-$HOME/.cache/wayfarer/godot-4.7.2}"
ln -sfn "$(ls "$gdir"/Godot_v*_linux.x86_64 | head -1)" "$bindir/godot-4" >/dev/null

# 4. MPFB and the CC0 asset pack for the character loop.
if [ "${WAYFARER_SKIP_CHARACTERS:-}" != 1 ]; then
  python3 tools/workflow.py deps fetch >/dev/null && python3 tools/workflow.py deps install >/dev/null \
    || log "character dependencies failed (non-fatal): run python3 tools/workflow.py deps fetch"
fi

log "$("$bindir/blender" --version 2>/dev/null | head -1) at $bindir/blender; Godot $("$bindir/godot-4" --headless --version 2>/dev/null | tail -1) at $bindir/godot-4"
