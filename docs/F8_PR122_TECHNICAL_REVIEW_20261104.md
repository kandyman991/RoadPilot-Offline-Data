# PR #122 — separate architecture, security and data-integrity review

Date: 2026-11-04. Reviewed original head 9ea0d251f407c0d9ea0ce89164c68483a9513af3 and its changes.
This is a dedicated technical code-review pass; no claim of separate third-party sign-off.

## Resolved findings

**R1 / High / Data integrity:** The source-cut coverage reconciler reported beyond-cut candidate counts without validating all original Valhalla TripLeg witness outcomes. Corrected by validating exact original directed first/last GraphIds, ordered cut-predecessor-to-final paths, mode-specific TripLeg sequences, original route success, snap tolerances, nonduplicated route-witness coverage and at least one exact successful witness in BOTH Car and Motorcycle for each candidate. Failed alternative branches remain explicit, not filtered away.

**R2 / Medium / Data integrity:** The direct-last-edge reconciler originally trusted a route status label plus a final GraphId without checking the actual ordered TripLeg identity. Fixed for ordinary direct edge cases and for the real 3.4-metre Austrian last edge: independently recheck its genuine original immediate-predecessor TripLeg and the exact upstream mode-specific witness ledger; do not fabricate unavailable top-level snap offsets.

**R3 / Medium / Resource safety:** The native whole-window geometry scan had an uncapped stdout line reader and could block forever inside readline before reaching the wait timeout. Added a 1-million-character per-native-record limit, a 3600-second streaming watchdog and strict integer identity/access checks to reject JSON bool/int aliasing.

**R4 / Medium / Source inventory integrity:** Enforce report counts, original branch-preservation flags and explicit bounded-depth status against exact native source IDs and complete route-witness sets. Reject missing direct final edges, forged upstream paths, duplicate witness routes and inconsistent provenance.

## Architecture gate

PRESERVED: one final ORIGINAL Valhalla directed edge per actual physical road and direction is the target. An OSM way/name or a point-cluster is NEVER used as physical-road equivalence. No old OSM-first crossing producer, intermediate points, connector matrix, GraphId equality across independent graphs, receiving-B graph lookup, native graph mutation, production sidecar or Android runtime change.

OPEN production blockers: 3,623 complete COMMON-OVERLAP windows are not a complete ORIGINAL GRAPH ARCHIVE tile census. From 658,345 window-captured directed GraphIds, 880 original directed source-buffer cut observations are retained. 331 are linked to known source final-edge or predecessor proof, 549 remain unlinked, 34 additional genuine beyond-cut predecessor IDs were absent from the window capture, and two beyond-cut branches have bounded-depth incompleteness. None of this proves 880 physical roads or one unique final edge per physical road and direction. Receiving-B correlation is NOT_STARTED, production publication BLOCKED. Graph Studio issues #73/#82 and Android #512 remain OPEN.

## Evidence

- All real SHA-bound Italy Nord-Est/Austria 2026.10.13-1 original reports and native Valhalla 3.6.3 executable evidence rechecked.
- The corrected reconciliation reproduces the existing immutable Legion source-cut coverage report byte-for-byte: SHA-256 652c3efe77ebf3d60ae3e7be24e7d454279ba5b91ac5c6225d97596db3e68ecf.
- 390/390 full local Python tests PASS; 20 focused reconciliation regressions, seven native geometry-census regressions, and compilation/diff checks PASS.
- A fresh exact-head GitHub architecture-contract, validate and Linux CI run is required before owner-authorized merge.

Disposition: merge acceptable ONLY as nonpublishing intermediate source-evidence work after the corrected exact-head CI gates are green. Next milestone: exhaustive ORIGINAL source graph tile enumeration, full source road-direction branch lineage and proof of one final retained directed GraphId per physical road/direction BEFORE receiving graph correlation.
