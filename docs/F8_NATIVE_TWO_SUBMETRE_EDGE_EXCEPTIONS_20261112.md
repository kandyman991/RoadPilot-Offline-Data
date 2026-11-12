# D-017 — original Valhalla sub-metre directed-road exceptions

12 November 2026. **Nonpublishing native acceptance report; independent PR review required.**

## Root cause and resolution

The two previously unmatched Italy Centro and Italy Sud original source final
directed GraphIds were **false negatives in the existing A-final → exact X → B
matcher**, not missing receiving graph coverage. The old >=1 m directed overlap
condition rejected valid final Valhalla 3.6.3 native segments shorter than 1 m.
The original SHA-verified receiving graph contained the matching directed road
at the unchanged exact source X in each case.

| Directed pair | Original source GraphId | Exact X (lat, lon) | Native matching B directed GraphId | Directed overlap | Distance B to X |
| --- | ---: | --- | ---: | ---: | ---: |
| Italy Centro → Italy Sud | 136975291698 | 42.2845844, 13.6598531 | 159322543410 | 0.933 m | 0.045 m |
| Italy Sud → Italy Centro | 15407561506 | 41.7707842, 13.0063595 | 23158635298 | 0.884 m | 0.023 m |

The native source shapes have 41 original Valhalla vertices each. Centro→Sud
retains the last ~0.93 m of a ~300 m source shape on a ~34 m B edge.
Sud→Centro retains a ~715 m original A final edge; in B the same approach
is split into a ~714 m edge followed by a ~0.92 m final directed edge. The
final B GraphId is the match. A native 4-metre receiver lookup returned six
B directed candidates in each case, but **only one** agreed with the original
source direction and geometry. Opposite and other nearby roads were rejected.

Only the existing classifier was adjusted. The normal >=1m directed overlap
proof is unchanged; for a native A final tangent from 0.5 to <1.0 m, an
original B candidate must agree within 0.10 m at both the original native
source approach and exact X, cover >=0.5 m of the directed tangent and at
least the native tangent length minus 0.12 m, and preserve compiled layer,
bridge, tunnel and car/motorcycle access. A native sub-metre measured tangent
is retained in raw independent audit evidence. No new road-name, OSM, GPS
handoff, scanning algorithm, outgoing-turn gate or whole-graph scan.

A separate **evidence disposition bug** was corrected: a single original A
final may match a distinct END_NODE B road and a distinct INTERIOR B road at
the same X. The existing matcher correctly reported both, but the downstream
disposition previously recorded only the B predecessor. The disposition now
keeps both original B directed identities, while the original END_NODE-only
predecessor list remains the input for B successor costing.

## Six-pair original native regression

All pairs were reprocessed on the original Valhalla 3.6.3 graph TAR archives
and independently audited against bounded native source terminal GraphIds.
The native original B incoming matches, source IDs, X, access masks,
fingerprints and all real B alternatives were retained. Six independent
audits, six production preflights (BLOCKED), six automatic test-only catalogs
(BLOCKED_TEST_ONLY) and candidate JSON Schema validation passed.

| Directed region pair | Eligible source final GraphIds | Source finals matched | Distinct B directed matches |
| --- | ---: | ---: | ---: |
| Italy Nord-Est → Austria | 454 | 454 | 454 |
| Austria → Italy Nord-Est | 253 | 253 | 253 |
| Italy Nord-Est → Italy Nord-Ovest | 716 | 716 | 716 |
| Italy Nord-Ovest → Italy Nord-Est | 779 | 779 | 779 |
| Italy Centro → Italy Sud | 257 | 257 | 257 |
| Italy Sud → Italy Centro | 299 | 299 | 300 |
| **Total** | **2,758** | **2,758** | **2,759** |

In the reverse Centro/Sud pair, source GraphId 2724032282 validly matches
B END_NODE GraphId 49264029466 and B INTERIOR GraphId 49297583898. Both
are preserved; counts of source finals and receiving directed edges are
intentionally different.

Original archive fingerprints:
- italy-centro SHA-256: 08438c4d73d6ae2e1c2d510ed42c75985763fa09ae880f39b20acb5e75502e7a
- italy-sud SHA-256: f81f6472c52bd26c1efd1a532e3c805f65caaebf36a5cc038ff202c2c4827543

Test fixture: tests/fixtures/f8_real_original_valhalla_short_edges_20261112.json
contains the original native A tangent, six original B directed native
candidate geometries for each X and graph fingerprints. Regressions reject
opposing directions, short nearby false positives, wrong layer, corrupted
native tangent and fabricated/dropped directed road identities.

## Source-edge completeness: proven boundary, unproven semantics

The existing source selector retains the pair's original shared 25-km cutoff
and the source's original SHA-indexed tiles intersecting the B-covered,
outside-A endpoint domain. It includes at most one additional exact
GetOpposingEdgeId original owning tile readback. The native original reader
fails closed if any incoming original edge owner remains outside the
approved bounded tile selection. No whole-graph scan or road walk.

- Italy Centro → Italy Sud: 52 source cutoff tiles + 28 extra original
  indexed endpoint tiles; 638 original incoming references inspected,
  zero missing owning tiles. 257 original eligible exterior A finals.
- Italy Sud → Italy Centro: 67 source cutoff tiles + 18 original indexed
  endpoint tiles + one additional exact native owner tile; 829 incoming
  references inspected, zero missing owners. 299 eligible exterior source
  finals, including two previously missed by the smaller tile selection.

Independent source audit checks the exact set of original terminal GraphIds
against the native list, zero missing incoming original owners, immutable
graph fingerprints, tile coverage and no source suppression. This proves
source-final coverage **within that native endpoint domain** only.

It does **not** establish globally unique final edge lineage for every
actual physical road and travel direction, complete original root-to-edge
path semantics, Android actual JNI parity or production READY acceptance.
The unresolved 164 and 208 bounded source-root *observations* are not
automatically missing roads. Original publication still BLOCKED by source
semantic lineage proof, device normal route-preview acceptance and first/
repeat all-mode tests, independent review, owner approval and signed APK
SHA-256 pin.

## Evidence and isolation

Original native reader: roadpilot.f8-native-source-11; compiled against
Valhalla 3.6.3. Full Python suite 508 tests PASS (see CI or local test log).
Raw immutable nonpublishing evidence, full rerun logs, six independent
audits, preflights, catalogs and SHA-256 summary:
~/RoadPilotGraphStudio/diagnostics/f8-production/20261112-short-native-overlap-fix/
Report file: six-pair-final-audited-acceptance-summary-BLOCKED.json

All work was isolated in a separate Git worktree. Compiled original
graph archives, published release objects, Android and the installed
Graph Studio AppImage were not modified.
