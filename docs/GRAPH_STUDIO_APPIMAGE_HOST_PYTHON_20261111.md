# Graph Studio Linux AppImage: host Python bootstrap / UI acceptance

Date: 2026-11-11. Scope: Graph Studio Tauri startup environment only.

## Failure reproduced on Legion

The AppImage bootloader populates `APPDIR=/tmp/.mount_...`,
`PYTHONHOME=$APPDIR/usr/` and
`PYTHONPATH=$APPDIR/usr/share/pyshared/:`. Graph Studio invokes the
machine's system Python for Geofabrik catalog, Python venv prerequisites
and native F8 tools. Under the inherited environment, the system
interpreter immediately fails with:

    Fatal Python error: Failed to import encodings module
    ModuleNotFoundError: No module named 'encodings'

In the application, **New region → Retry catalog** remains unavailable
even when the Geofabrik CLI runs successfully outside the AppImage.
**Native F8 → Inspect pair** fails with "pip upgrade failed".
The build queue remains disabled because the embedded Python toolchain
prerequisite check reports incomplete.

## Fix and safety scope

At Tauri initialization, strip `PYTHONHOME` only when it points inside
the current `APPDIR`. Strip only paths under the same `APPDIR` from
`PYTHONPATH`; preserve legitimate external user Python module paths.
Non-AppImage sessions are untouched, and the routing graph, Android
handoffs, on-disk build packages, user configs, release metadata and R2
publication commands are unchanged.

## Regression and acceptance

- Rust tests: AppImage-only `PYTHONPATH` is removed; unrelated entries
  survive; lexical sibling-prefix paths are not removed.
- 490 Python tests passed on Legion before and after the source-only fix.
- For the real packaged AppImage, rerun the UI accessibility audit:
  the Geofabrik catalog must load, the existing region editor must open,
  toolchain prerequisites must report ready, one safely queued region
  must enable Build selected (then unqueue without building), and the
  existing Italy Nord-Est/Austria F8 Inspect pair must not fail from
  Python bootstrap/pip environment interference.
- Record any unrelated limitations separately; never publish or create
  production READY catalogs to validate this fix.
- Download installation packages from a nonpublishing manual GitHub
  workflow run, verify artifact SHA-256 and source commit, keep old AppImage
  backup, then relaunch the actual GUI on Legion for acceptance.

The PR architecture checklist preserves the entire existing A → X → B
contract, with no changes to boundary final-edge matching or production gates.
