# PR #128 — independent technical review, corrections, and merge acceptance

Date: 2026-11-11  
Scope: `feature/f8-approved-catalog-contract-20261110` against current `main`.  
Decision: **MERGEABLE as a nonpublishing, BLOCKED_TEST_ONLY implementation** after exact-head CI passes. **NOT production READY**. This is a separate code-and-evidence audit of the implementation; it is **not** an external security attestation or production catalog publication approval.

## Contract review

- D-017 remains source original final **directed GraphId → exact X → native original incoming B directed GraphId(s)**; preserves original Valhalla 3.6.3 graph and 25 km buffer fingerprints, direction, car/motorcycle permissions and distinct receiver options.
- No outgoing B turn or post-junction physical-road continuation is a matching acceptance gate; RoadPilot's normal Valhalla routing determines legal continuation.
- Neither the existing matcher nor Android JNI was rewritten. No OSM names, arbitrary GPS Y, graph-wide traversal, new road discovery algorithm, hardcoded region or favorite crossing.
- Generator rechecks the two immutable compiled original TAR hashes, independently reruns the native source/receiver audit, regenerates dispositions, verifies the retained preflight bytes, and writes a new exclusive-create JSON file.
- Actual producer output is **BLOCKED_TEST_ONLY**, with remaining review gates listed; the proposed READY schema alone cannot authorize a release. No signing, APK pin creation, public manifest, R2 production latest pointer or activation is performed.
- `main` contained later R2-test workflows from merged PRs #129/#130. The feature branch has been reconciled with `main`; those workflows and their tests are preserved.

## Review finding corrected

**F8-PR128-01 (correctness, region-independent branch preservation):** the preflight previously required the number of distinct original B incoming directed roads to equal the number of source A final approaches. This happened to hold for the Italy NE/Austria test archives, but would reject a genuinely verified source A final matching more than one distinct original B directed road at X. The independent PR127 auditor separately reports distinct B roads and matching A approaches.

**Resolution:** reconcile the distinct B road total against `catalog.counts.nativeBDirectedRoadMatchesAtX` and the independent audit's `originalBDirectRoadMatchCount`; reconcile the matched A-approach count separately against disposition `nativeBMatchedIncomingAApproaches` and source row count. Retain per-A duplicate checks, global original B identity checks, all source modes and native geometry attestation. New regressions verify two A approach records with three distinct B incoming roads are accepted and all three survive automatic catalog generation, while forged independent totals fail closed. No new matching heuristic was introduced.

## Verification, performed on Legion

- Clean isolated Git worktree and merger of latest `origin/main` into the review branch.
- Full Python test suite: **490 passed; zero failures**, including the R2 transport tests and new multi-receiver regressions (isolated Graph Studio Python environment with existing R2 cryptography dependency exposed to test process).
- Original archive regeneration with exact stored native evidence/preflight using existing `tools/build_f8_native_auto_catalog.py`:
  - Italy Nord-Est → Austria: 454 source A / 454 native B incoming; resulting catalog SHA-256 `d5225a0ed5fd691e32d3e81304c73016362b0f0e288a3ada1a228a44ee0b8f05`.
  - Austria → Italy Nord-Est: 253 source A / 253 native B incoming; resulting catalog SHA-256 `5dd70b5d9f4639a7391bbba51672a57aac18dfc13bbc9cd20d48621917221dd3`.
- Both independently regenerated JSON artifacts **exactly match the previously retained catalog SHA-256 values**. They remain isolated in Legion diagnostics under `f8-production/20261111/pr128-final-independent-review/`; they are not deployed or published.
- Verify GitHub exact-head architecture and validation CI before merging. The local tests and regeneration are the technical review; no synthetic READY fixture is treated as release evidence.

## Deliberately open production gates

- Source final-edge identity coverage is established only within the native pair endpoint domain, not a universal semantic physical-road lineage proof.
- Production signed READY catalog approval and reviewer attestation, signed APK SHA pin, immutable post-build publication and release-mode full lifecycle acceptance are absent.
- Android debug-only normal route previews were previously demonstrated in both directions/modes; they are **not** production signed-READY acceptance. The debug first-valid reverse route was slower than an alternative, so production Faster selection and performance need separate validation.
- Installer, Drive staging, R2 publication, transactional updates/rollback and physical-phone acceptance are separate downstream release work.
- The policy is to merge the safe nonpublishing producer **without** creating or approving any READY catalog or flipping Android activation gates. Explicit owner authorization and actual required evidence remain necessary before first production publication.
