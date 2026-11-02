#!/bin/bash
# Cloud sessions: make sure the pinned Blender, Godot and MPFB are installed (cached; a no-op after the first run).
set -euo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
"${CLAUDE_PROJECT_DIR:-.}/tools/cloud_toolchain.sh"
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export WAYFARER_BLENDER=/snap/bin/blender WAYFARER_GODOT=/snap/bin/godot-4' >> "$CLAUDE_ENV_FILE"
fi
