# Graph Studio — original-native A to X to B GUI and legacy UI retirement

13 November 2026. This feature replaces outdated GPS-proposal controls
with the owner-approved original-native D-017 producer in the simplified
Cross-region Connections screen, while retaining saved data and external
diagnostic compatibility.

## Final workflow

Select two original retained regional Valhalla graph versions, inspect
the native proof, then generate an immutable owner-private catalog. Each
catalog contains the last original Graph A directed GraphId for each bounded
eligible road/direction, exact original native endpoint X and corresponding
original B directed GraphId options with car/motorcycle access restrictions.
An actual B branch is preserved rather than artificially deduplicated.

The GUI invokes only the canonical original D-017 extractor, original B
matching, independent native audit, preflight and private schema validation.
The original C++ final-edge native reader is pinned to Valhalla 3.6.3 and
compiled from its existing project if needed; missing version, reader,
original graph, original index or 25-km buffer fails closed. The original
archive and source SHA-256 hashes are checked before promotion. Outputs are
atomically saved under the owner's Graph Studio private catalog workspace,
and reused only when retained source, preflight, archive and catalog digests
still agree. User does not need to enter internal candidate/path filenames.

An optional advanced evidence-directory input can replay previously retained
native readback; otherwise the tool automatically generates original
A-final and B-directed evidence. It never switches to old GPS proposal
matching, OSM names, arbitrary graph walks, outgoing-turn acceptance or a
new global physical-road lineage algorithm.

Private schema status is GRAPH_STUDIO_PRIVATE_READY and the output retains
notForRoadPilotRuntime=true and
sourcePhysicalRoadDirectionCompleteness=NOT_VERIFIED. Neither Android
consumer readiness nor full global physical-road semantic lineage is
claimed. User can click a directed A to B row to see exact X on the map.

## Old UI, actual dependencies and what was retained

| Former UI component | Disposition | Preserved |
| --- | --- | --- |
| GPS proposal Discovery and sample Journey Proof tabs | Removed from everyday F8 UI | Original diagnostic CLI engine, corresponding Rust F8 status/discover/probe commands and saved evidence remain for external compatibility |
| OSM way overlap color panel and layer | Retired from historical Border GUI | Independent, useful Routing build comparison still retains its own OSM way-based version diff |
| Historical connector matrix panel/overlay | Retired from Border GUI | Existing read-only Rust inspect_region_connector_matrix and its JSON compatibility readers remain callable |
| Manual directed-edge validation and handoff editing | Still accessible in Advanced | Saved overrides, original source data and Tauri commands unchanged |
| Saved historical handoffs/evidence, export | Still accessible in Advanced | Historical files, read-only provenance and compatibility schema kept intact |
| Graph inspector, original route planner, R2 publication, Map/POI, Build comparison | Unchanged | No migrations, Android changes, graph writes or public publication |

Historical scripts that relied on the old diagnostic command interfaces
may still use them. A future destructive backend removal requires independent
caller inventory and explicit owner approval; none is included here.

## Tested on actual original graph data (Legion, isolated workspaces)

- Replayed existing independent original Italy Nord-Est to Austria evidence:
  original A source 454, native B directed receivers 454, privately validated.
- Fresh source cutting and original B native directed matching from the two
  retained Valhalla archives, independent audit and private catalog: 454/454.
- Full automatic generation (no existing input evidence required), including
  compiling the original version-pinned native reader with libvalhalla
  3.6.3, and SHA-verifying the retained original TARs, index and buffers:
  454/454 private catalog. Subsequent read-only status independently
  rechecked original archives, retained preflight and private artifact hashes.
- Italy Sud to Centro existing original readback: 299 original A directed
  finals and 300 original B directed receivers, proving the one-to-two
  receiving branch was retained in the private catalog.
- New negative unit tests cover missing original prerequisites, index/buffer
  tampering, manifest/archive mismatch, unsafe path, symlink evidence,
  identical A/B regions and rejecting RoadPilot/public READY.
- Full repository Python tests: 527/527 pass. TypeScript/Vite compiles.
  Native Tauri/AppImage/DEB CI and installed desktop button-by-button
  acceptance must still be checked independently.

The actual local QA evidence stays outside Git in the following Legion
diagnostic workspaces: native-catalog-gui-qa-20261113,
native-catalog-gui-fresh-e2e-qa-20261113,
native-catalog-gui-autobuild-qa-20261113,
native-catalog-gui-branch-qa-20261113.

No installed Graph Studio process, retained graph archive, RoadPilot Android
app, R2 bucket or production pointer was altered. Source and legacy readers
remain available.


## Packaged desktop resource guard

Graph Studio Linux CI now verifies that both AppImage and Debian outputs
contain the original D-017 C++ native reader source, this new GUI bridge
producer and the existing private catalog schema. A green Python or TS test
alone is insufficient to claim an installed application can build native
catalogs. The original reader is compiled on the owner's machine against
the pinned Valhalla 3.6.3 native development package; if absent, fresh native
catalog generation fails with an explicit dependency error, never with an
invented graph match.
