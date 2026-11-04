# PR #112 — Pinned native extractor build provenance and smoke results

**Review finding addressed:** The repository's hosted Linux Graph Studio/Tauri
workflow does not compile the native Valhalla GraphReader extractor. The
review explicitly allows instead **archived SHA-bound compilation commands
and exact binary/build provenance**. This file records that alternative;
do not misrepresent hosted CI as a native C++ build.

## Environment and exact build

On Legion `mircea-gitmachine`, Ubuntu 26.04, with installed Valhalla
**3.6.3** headers and static library:
- Source revision at build: `9bd2e730f6d35db02222d4855dbaf34b3993224f`
- C++ compiler: `c++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0`
- CMake: `4.2.3`; `pkg-config libvalhalla`: `3.6.3`

The PR review amendments change Python diagnostics, tests and documents
only. Native extractor and CMake inputs remain identical to that revision.

~~~bash
set -euo pipefail
cd /home/mircea/graphstudio-m6-directed-chain
PREFIX="$HOME/.local/opt/valhalla-3.6.3-native"
E="$HOME/RoadPilotGraphStudio/diagnostics/m6/pr112-review/native-build-20261104"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
test "$(pkg-config --modversion libvalhalla)" = "3.6.3"
cmake -S tools/native-f8-edge-scan -B "$E/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DCMAKE_CXX_COMPILER=/usr/bin/c++
cmake --build "$E/build" --target native_f8_directed_endpoints --parallel 2
"$E/build/native_f8_directed_endpoints" --version
sha256sum tools/native-f8-edge-scan/native_f8_directed_endpoints.cpp \
  tools/native-f8-edge-scan/CMakeLists.txt \
  "$PREFIX/lib/libvalhalla.a" \
  "$PREFIX/lib/pkgconfig/libvalhalla.pc" \
  "$E/build/native_f8_directed_endpoints" \
  "$E/build/CMakeCache.txt" "$E/build/compile_commands.json"
~~~

### Captured SHA-256 — actual clean native build

| File | SHA-256 |
| --- | --- |
| `native_f8_directed_endpoints.cpp` | `937faf761b50c92f58f278fbfd235b852a9fc8abe7daea8daa068dbaffb35889` |
| `tools/native-f8-edge-scan/CMakeLists.txt` | `29061da623381f5ce6e7f2bcc38e6ed768cef30db2da08c885bc7de8fb2355a7` |
| `libvalhalla.a` (pinned 3.6.3) | `5f5d917229dcf79bd4bcf618e312e365892f5d47f6dfff88160a5085618c4bb9` |
| `libvalhalla.pc` | `41f5a9359705ec09835ed331899d87fa69b8281e5740a2973adc80f88cbbf4b4` |
| Compiled `native_f8_directed_endpoints` | `14455ad673c464c3715f2e0b96adfa3aa1f1ecf2a99d347f59920a6a9cc91c6f` |
| Generated `CMakeCache.txt` | `fa6724908abae07582ac3be1b2a0b6a0d06a62d679865cd61fae6ceb87c83dcd` |
| Generated `compile_commands.json` | `dea5cf24a40f390bc1491163b083f1d5b5ad410cb2feab7a54c7920fb9e5ff99` |

The compiled executable was invoked with `--version` and returned **3.6.3**.
Hashes capture exact local toolchain/input/binary provenance, **not** a
cross-machine reproducible-build guarantee. The native library is static.

## Exact compiled-binary smoke: real Italy–Austria graphs

The new compiled binary, the PR's updated Python diagnostic and the
immutable `2026.10.13-1` Italy Nord-Est/Austria region pair were used
together. The CLI verifies exact graph archive and boundary manifests,
checks real Graph B native outgoing degree, and tests the selected
B-directed chain with Valhalla for Car and Motorcycle.

Seven real probe JSONs were recorded, all parsed and individually checked
for expected `selectedNextIsOpposingReverse` values. The findings:

- Four Italy→Austria probes were **not** immediate reverse and all had a
  matching *B-local* Valhalla directed chain.
- Italy→Austria Car chain ending `670054737218` had the immediate
  opposing reverse, `selectedNextIsOpposingReverse=true`; Valhalla was
  **INCONCLUSIVE** for that selected B-local path.
- Austria→Italy Car and Motorcycle chain `1482679618 → 1012917570`
  likewise had the selected immediate reverse, and the B native node
  had **outdegree 1**; both route results were **INCONCLUSIVE**.
- The final nominated B edge has no selected successor and reports
  `selectedNextIsOpposingReverse=null`; this must not imply false.
- Every output retained all native B outgoing edges and reported
  `crossSeamTurnLegality=NOT_VERIFIED` and
  `productionPublication=BLOCKED`. No candidate was excluded from
  discovery merely because it reversed.

### Retained archive and integrity checks

All native compilation logs and smoke JSONs remain outside the repository:

`~/RoadPilotGraphStudio/diagnostics/m6/pr112-review/native-build-20261104/`

The directory holds `build-log.txt`, compiled executable, native
`CMakeCache.txt`, `compile_commands.json`, plus `smoke/summary.json`,
`smoke/SHA256SUMS` and **seven** raw JSON outputs.

| Evidence | SHA-256 |
| --- | --- |
| `build-log.txt` | `dc788a5e84901e76f4f467e735599baeb1e3e55225da36d0a0ce988bf5f5cacb` |
| `smoke/SHA256SUMS` | `eee80cc7408f55974d3d1c18b75ef1213dc0ae5a93b8d2796ce9b16d70fd9801` |
| `smoke/summary.json` | `45c90d2a0d8eef4fbfd92fb42ab651433d96944c7c47cf745282ba627d374313` |

Verification: `cd "$E/smoke" && sha256sum -c SHA256SUMS` checks all
seven JSON outputs. That manifest binds individual real-graph reports
to the archived compiler/build evidence and binary SHA-256.

**Limitations:** This is an explicitly selected B-local diagnostic, not
complete F8 crossing discovery, legal A→B physical transfer, Android JNI
parity, global route optimality or production publication.
