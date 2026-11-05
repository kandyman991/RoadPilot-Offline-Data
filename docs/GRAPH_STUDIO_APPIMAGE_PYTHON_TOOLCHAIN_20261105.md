# Graph Studio AppImage host Python toolchain repair — 2026-11-05

## Symptoms and exact native cause

When the installed Linux AppImage (PR #125 head `27b8fe2`) started,
Graph Studio displayed **Toolchain incomplete** even though Valhalla 3.6.3,
osmium, tilemaker v3.2.0 and `python3-venv` were installed on the Legion.

The AppImage runtime sets these inherited process environment variables:

```text
APPIMAGE=.../RoadPilot-Graph-Studio-Linux.AppImage
APPDIR=/tmp/.mount_RoadPi.../
PYTHONHOME=/tmp/.mount_RoadPi.../usr/
PYTHONPATH=/tmp/.mount_RoadPi.../usr/share/pyshared/
```

That AppImage contains no complete Python standard library at its `usr`
prefix. Consequently its actual `python3 -m venv --help` check
fails with `Fatal Python error: Failed to import encodings module`.
The same inherited variables also break the host `valhalla_build_config`
and `valhalla_service` pyvalhalla launchers. Binary presence is insufficient.

## Narrow startup fix

At Tauri application startup, before any toolchain checks or routing process
spawns, `normalize_process_path()` now removes **only**
`PYTHONHOME` and `PYTHONPATH` when launched from an AppImage
(`APPIMAGE` present). Native `PATH` normalization, original graph tiles,
installed Python virtual environments and all original routing architecture
are unchanged. A Debian installation does not clear user-supplied Python vars.

Rust unit tests lock both decisions: sanitize AppImage, preserve normal
non-AppImage environment. Exact Legion regression run is a host Python/
Valhalla subprocess check with the AppImage's original environment, first
showing the crash, then proving that removing just the two keys restores:

- `python3 -m venv --help` (exit 0)
- cached Graph Studio Python-env import of `shapely` and `pyproj` (exit 0)
- `valhalla_build_config --help` (exit 0)
- `valhalla_service --help` (exit 0)
- `tilemaker --help`, version v3.2.0 (exit 0)

## Release discipline

This is a **PR preview installation correction**, not approval to merge the
incomplete F8 original source-graph catalog. Full original road/direction
completeness and unrestricted Android planner acceptance remain blocked.
