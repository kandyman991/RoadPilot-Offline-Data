#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROADPILOT_TRANSITION_PROBE_BUILD_DIR:-$ROOT/build/transition-probe}"

if ! pkg-config --exists libvalhalla; then
  echo "libvalhalla.pc was not found."
  echo "Build/install RoadPilot’s pinned Valhalla and expose its pkgconfig directory in PKG_CONFIG_PATH."
  exit 1
fi

cmake -S "$ROOT/native/transition-probe" -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" --target roadpilot-transition-probe

echo "$BUILD_DIR/roadpilot-transition-probe"
