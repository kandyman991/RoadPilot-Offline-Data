# Graph Studio private F8 catalog acceptance

**Owner decision, 13 November 2026:** Graph Studio is a private project
currently tested only by its owner. Android journey, JNI parity, normal
route-preview UI, signed APK and catalog-pin requirements are NOT release
or completion gates for Graph Studio itself. RoadPilot's Android consumer
integration will have its own separate acceptance phase.

## Output and interface

The existing tools/build_f8_native_auto_catalog.py has an explicit
--graph-studio-private-ready option. When a complete original SHA-pinned
Valhalla native source/receiving audit and independently reproducible
preflight pass, this produces:

- Schema: roadpilot.f8-graph-studio-private-validated-catalog v1.
- Publication: GRAPH_STUDIO_PRIVATE_READY.
- Intended use: OWNER_ONLY_GRAPH_STUDIO_TESTING.
- Field notForRoadPilotRuntime = true. The artifact never impersonates
  a RoadPilot Android READY release or APK-pinned consumer catalog.
- Original A/B graph archive and native/preflight evidence SHA-256 hashes,
  every source final directed GraphId, its exact X and matching B directed
  GraphIds with original car/motorcycle mode restrictions and branch options.
- Native scope: VERIFIED_WITHIN_ORIGINAL_PAIR_ENDPOINT_DOMAIN.
- Explicit truthful limitation: sourcePhysicalRoadDirectionCompleteness
  remains NOT_VERIFIED globally. This does not bar private original-native
  graph-pair testing after exact scoped inventory checks pass.

The existing default builder mode remains BLOCKED_TEST_ONLY for legacy test
consumers and compatibility. It has not been relabelled or silently published.
The future RoadPilot public-consumer READY schema is unchanged.

## Native integrity conditions that remain mandatory

1. Verify both compiled original Valhalla archives and graph manifest SHA-256s,
   immutable source index and the paired 25-km buffer identities.
2. Independently enumerate exact original A directed *terminal* edges in
   the eligible B-covered outside-A endpoint tile domain, including any
   required exact original native GetOpposingEdgeId owning tiles.
   No whole-graph scan or invented road tracing. Fail on missing owners.
3. Match every selected original A final directed GraphId by compiled
   Valhalla directed approach geometry and exact native endpoint X to all
   B directed GraphIds, preserving mode permissions and branch alternatives.
   No road names, proximity-only acceptance or B-outgoing continuation gates.
4. Recompute the independent native source disposition and preflight against
   unchanged source evidence and original TAR SHA-256s; fail closed on
   dropped/duplicate edges, forged identity, modes, missing B direction,
   archive mismatch or altered preflight bytes.
5. Validate the separate private artifact JSON Schema before atomic output.
   Never overwrite an existing evidence file.

**Not a private acceptance condition:** Android app/device validation,
signed APK pin, external public release approval, or a globally proven
one-per-physical-road/direction semantic lineage (reported as NOT_VERIFIED).

## How to produce the private catalog

After generating the ordinary original F8 candidates, native receiver evidence
and independently verified dispositions, run the existing preflight script
(tools/preflight_f8_approved_directed_catalog.py) with flags:
--catalog, --native-evidence, --dispositions, --from-archive, --to-archive,
--output. This generates a new uniquely named preflight JSON containing
graphStudioPrivateTestingReady=true after full native reconciliation.

Run tools/build_f8_native_auto_catalog.py with the SAME five source paths,
--preflight pointing to that immutable preflight, a new --output filename,
and --graph-studio-private-ready. It independently recomputes preflight
before accepting its exact saved contents and generates a new private-ready
catalog. Retain the original graph fingerprints with the output.

Removing --graph-studio-private-ready reproduces the existing
BLOCKED_TEST_ONLY output for old consumers. On any original graph change,
regenerate evidence instead of reusing an old private-ready catalog.

## Verified six original Valhalla 3.6.3 regional pairs

| Directed original pair | A directed source finals | Original B road matches | Graph Studio status |
| --- | ---: | ---: | --- |
| Italy Nord-Est → Austria | 454 | 454 | GRAPH_STUDIO_PRIVATE_READY |
| Austria → Italy Nord-Est | 253 | 253 | GRAPH_STUDIO_PRIVATE_READY |
| Italy Nord-Est → Italy Nord-Ovest | 716 | 716 | GRAPH_STUDIO_PRIVATE_READY |
| Italy Nord-Ovest → Italy Nord-Est | 779 | 779 | GRAPH_STUDIO_PRIVATE_READY |
| Italy Centro → Italy Sud | 257 | 257 | GRAPH_STUDIO_PRIVATE_READY |
| Italy Sud → Italy Centro | 299 | 300 | GRAPH_STUDIO_PRIVATE_READY |
| **Total** | **2,758** | **2,759** | **6/6 private-ready** |

Six separate CLI runs independently reran native audit/preflight against the
real original SHA-pinned graph archives and validated the private JSON schema.
The reverse Centro/Sud pair retains its legitimate A source → two B directed
edges (END_NODE + INTERIOR). No graph archives, installed AppImage, saved user
overrides or Android sources were changed.

Evidence on Legion, retained outside Git:
~/RoadPilotGraphStudio/diagnostics/f8-production/20261113-graph-studio-private-acceptance/

## Separate future RoadPilot public release

The earlier F8_APPROVED_DIRECTED_CATALOG_PUBLICATION_CONTRACT_20261110.md
describes the later RoadPilot consumer/public-release READY schema, not a
Graph Studio acceptance gate. Any Android JNI, device, APK signing or pinning
decisions should be tested when RoadPilot development is resumed. The
private-ready Graph Studio schema cannot be substituted for the Android READY
schema, which remains unchanged.
