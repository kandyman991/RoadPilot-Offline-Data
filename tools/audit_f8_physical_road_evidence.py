#!/usr/bin/env python3
"""Independent, read-only D-017 audit: no connection promotion or new discovery.

Checks original native A -> X -> B candidate evidence against Graph Studio's
paired original graph readback. This cannot certify physical-road identity:
valid adjacency and identical class/use are NOT proof of the same road.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


def read_json(path: Path) -> dict:
    with (gzip.open(path, 'rt') if str(path).endswith('.gz') else path.open()) as fd:
        return json.load(fd)


def fail(message: str) -> None:
    raise ValueError(message)


def audit(catalog: dict, evidence: dict) -> dict:
    if (catalog.get('schema') != 'roadpilot.f8-final-directed-connection-candidates'
            or catalog.get('version') != 1
            or catalog.get('productionPublication') != 'BLOCKED'
            or catalog.get('physicalRoadIdentityAcceptance') != 'NOT_VERIFIED'
            or catalog.get('sourceDiscoveryComplete') is not False
            or catalog.get('receiverMatchingComplete') is not False
            or evidence.get('schema') != 'roadpilot.f8-paired-native-receiver-correlation-evidence'
            or evidence.get('productionPublication') != 'BLOCKED'):
        fail("Unexpected publication or producer evidence state")
    for k1, k2 in [('sourceGraphFingerprint', 'from'),
                    ('receiverGraphFingerprint', 'to')]:
        if evidence[k1] != catalog['graphFingerprints'][k2]:
            fail("Original archive fingerprint mismatch")
    for evidence_k, catalog_k in [
        ('sourceBufferFingerprint', 'sourceBufferFingerprint'),
        ('receiverBufferFingerprint', 'receiverBufferFingerprint'),
        ('sourceIndexFingerprint', 'sourceGraphIndexFingerprint'),
        ('receiverIndexFingerprint', 'receiverGraphIndexFingerprint'),
        ('sourceEvidenceSha256', 'originalSourceEvidenceSha256'),
        ('reciprocalBoundaryFingerprints', 'reciprocalBoundaryFingerprints')]:
        if evidence[evidence_k] != catalog[catalog_k]:
            fail("Native source/receiver evidence mismatch: " + catalog_k)
    if (evidence['sourceRegionId'] != catalog['fromRegionId']
            or evidence['receiverRegionId'] != catalog['toRegionId']):
        fail("Wrong region pair")
    by_source = {}
    for row in evidence['sourceToReceiverCandidates']:
        sid = row['sourceFinalDirectedGraphId']
        if sid in by_source:
            fail("Duplicate original native evidence source")
        by_source[sid] = row
    options_by_evidence = {}
    class_counts = Counter()
    source_ids = set()
    status_counts = Counter()
    # The audit has an intentionally *stronger* standard than native turn legality.
    # Never mark a branch physical-road VERIFIED without a separate approved proof.
    for candidate in catalog['connectionCandidates']:
        sid = candidate['sourceFinalDirectedGraphId']
        if sid in source_ids or sid not in by_source:
            fail("Duplicate or missing source-native readback")
        source_ids.add(sid)
        row = by_source[sid]
        x = candidate['sourceFinalCoordinate']
        if (abs(x['lat'] - row['x']['lat']) > 0.00000001
                or abs(x['lng'] - row['x']['lon']) > 0.00000001):
            fail("Source original X changed")
        if (candidate['sourceOriginalNativeEndNodeGraphId'] !=
                row['sourceOriginalEndNodeGraphId']):
            fail("Source original terminal node changed")
        if (candidate['sourcePhysicalRoadIdentity'] != 'NOT_VERIFIED'
                or candidate['status'] != 'NATIVE_CANDIDATE_NOT_PUBLISHED'):
            fail("Source incorrectly approved")
        refs = {o['receiverDirectedGraphId']: o
                for o in row['receivingNativeDirectedContinuationOptions']}
        if len(refs) != len(row['receivingNativeDirectedContinuationOptions']):
            fail("Repeated native B branch readback")
        published = {o['receiverFirstDirectedGraphId']: o
                     for o in candidate['receiverOptions']}
        if len(published) != len(candidate['receiverOptions']) or set(refs) != set(published):
            fail("Suppressed, invented, or duplicate original B branches")
        for oid, option in published.items():
            original = refs[oid]
            if (option['samePhysicalRoadVerified'] is not False
                    or option['androidJourneyVerified'] is not False
                    or original['originalPhysicalRoadIdentityStatus'] != 'NOT_VERIFIED'):
                fail("Unapproved native edge promoted")
            if (option['nativePhysicalBranchEvidence'] !=
                    original['originalNativeBranchRelationshipEvidence']):
                fail("Native physical-branch descriptor changed")
            if option['nativeOriginalBPredecessorDirectedGraphIds'] != original['fromNativeBPredecessorGraphIds']:
                fail("Original B predecessor changed")
            if abs(option['nativeReceiverStartGapMetres'] -
                   original['nativeReceiverStartGapMetres']) > 0.000001:
                fail("B original X entry moved")
            if option['nativeReceiverStartGapMetres'] > 0.75:
                fail("B original directed edge does not start at X")
            for field in ('receiverNativeRoadClass', 'receiverNativeRoadUse',
                          'receiverNativeLayer', 'receiverNativeBridge',
                          'receiverNativeTunnel', 'nativeSameClassAsBPredecessor',
                          'nativeSameUseAsBPredecessor',
                          'nativeSameStructureAsBPredecessor'):
                if option[field] != original[field]:
                    fail("B original native attribute mismatch: " + field)
            if option['nativeCorrespondenceEvidence'] != original['status']:
                fail("Native B directional/turn status changed")
            key = option['nativePhysicalBranchEvidence']
            class_counts[key] += 1
            status_counts[tuple(sorted(option['travelModes']))] += 1
            options_by_evidence[(sid, oid)] = key
        # The B predecessor of each source must have original A approach
        # geometrical overlap; B junction successors alone do not prove identity.
        incoming = {entry['receiverDirectedGraphId']
                    for entry in row['receiverDirectedCandidatesAtX']
                    if (entry['status'] == 'B_PREDECESSOR_ENDS_AT_X_NEEDS_NATIVE_SUCCESSOR'
                        and entry['distanceSourceApproachMetres'] <= 0.75
                        and entry['directedOverlapProgressMetres'] > 0
                        and entry['sameLayerBridgeTunnel'])}
        if not incoming or not set(candidate['nativeBOriginalPredecessorGraphIds']) & incoming:
            fail("No independently read-back original B incoming approach to X")
        for option in candidate['receiverOptions']:
            if not set(option['nativeOriginalBPredecessorDirectedGraphIds']) <= incoming:
                fail("Receiver continuation is not attached to independently verified B incoming physical approach")
            if option['nativeCorrespondenceEvidence'] != 'VERIFIED_B_ORIGINAL_SAME_NODE_LEGAL_BRANCH':
                fail("Unverified original B outgoing relation")
        # Preserve the original Valhalla motorized access mask per branch,
        # rather than copying a source or sibling branch's access rights.
        for oid, option in published.items():
            raw_modes = refs[oid]['sharedVehicleModes']
            expected_modes = set()
            if raw_modes & 1:
                expected_modes.add('auto')
            if raw_modes & 1024:
                expected_modes.add('motorcycle')
            if set(option['travelModes']) != expected_modes:
                fail("Original receiving-road car/motorcycle permissions changed")
    unresolved = catalog['unresolvedSourceFinalEdges']
    for exception in unresolved:
        sid = exception['sourceFinalDirectedGraphId']
        if (sid in source_ids or sid not in by_source or
                exception['mustNotCreateConnection'] is not True or
                exception['sourcePhysicalRoadIdentity'] != 'NOT_VERIFIED'):
            fail("Missing or incorrectly approved unresolved final")
        original = by_source[sid]
        if (exception['sourceOriginalNativeEndNodeGraphId'] !=
                original['sourceOriginalEndNodeGraphId'] or
                abs(exception['sourceFinalCoordinate']['lat'] - original['x']['lat']) > 0.00000001 or
                abs(exception['sourceFinalCoordinate']['lng'] - original['x']['lon']) > 0.00000001):
            fail("Unresolved final lost original native endpoint/node")
        if (exception['nativeBOriginalPredecessorGraphIds'] !=
                original['correspondingBPredecessorAtXGraphIds']):
            fail("Unresolved original B predecessor identities were altered")
        source_ids.add(sid)
    # Independent original source inventory: catalog self-counts alone cannot
    # prove that a missing A final edge was not silently omitted from BOTH the
    # records and their own counts.
    native_inventory = evidence.get('approvedBoundaryExteriorTerminalInventory')
    if not isinstance(native_inventory, dict):
        fail("Missing independent original Valhalla terminal source inventory")
    authoritative_ids = native_inventory.get('allPairBoundaryOuterTerminalGraphIds')
    if (not isinstance(authoritative_ids, list) or
            len(authoritative_ids) != len(set(authoritative_ids)) or
            any(type(x) is not int or x <= 0 for x in authoritative_ids) or
            source_ids != set(authoritative_ids) or
            native_inventory.get('originalSourceTerminalEdgesOutsideAWithinB') != len(source_ids) or
            native_inventory.get('nativeIncomingOriginOutsideSelectedPairTilesCount') != 0 or
            native_inventory.get('terminalEndpointDomainTileCoverage') !=
                'COMPLETE_FOR_ORIGINAL_INDEX_BOUNDS' or
            native_inventory.get('sourceTerminalInventoryScope') !=
                'PAIR_SHARED_OUTER_CUTOFF_TILES_ONLY' or
            native_inventory.get('wholeGraphCensusPerformed') is not False):
        fail("Catalog source IDs do not exactly match independent bounded native A terminal census")
    counts = catalog['counts']
    if (len(source_ids) != counts['eligibleSourceFinals']
            or len(catalog['connectionCandidates']) != counts['candidateSourcesWithBOptions']
            or len(unresolved) != counts['unresolvedEligibleSourceFinals']
            or len(options_by_evidence) != counts['nativeOriginalBDirectedOptions']):
        fail("Suppressed or invented source/branch candidates")
    if dict(class_counts) != counts['branchAttributeEvidenceCounts']:
        fail('Original B attribute categories changed or suppressed')
    return {
        'schema': 'roadpilot.f8-pr127-independent-physical-identity-audit-v1',
        'pairId': catalog['pairId'],
        'originalArchiveFingerprints': catalog['graphFingerprints'],
        'eligibleOriginalSourceFinals': len(source_ids),
        'sourceCandidatesWithNativeBOptions': len(catalog['connectionCandidates']),
        'explicitUnresolvedFinalSources': len(unresolved),
        'preservedDirectedBOptions': len(options_by_evidence),
        'originalNativeBBranchEvidenceCategories': dict(sorted(class_counts.items())),
        'modesForOriginalBOptions': {'+'.join(k): n for k, n in status_counts.items()},
        'originalSourceFinalIdsCheckedAgainstIndependentNativeInventory': True,
        'originalBIncomingApproachReadbackVerified': True,
        'originalBOutgoingAtXNativeAdjacencyVerified': True,
        'fullPhysicalRoadIdentityApproval': 'NOT_VERIFIED',
        'reason': 'Native incoming overlap and legal outgoing directed adjacency do not alone prove identical physical-road lineage across all junction branches',
        'productionPublication': 'BLOCKED',
    }


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fd:
        while chunk := fd.read(4 * 1024 * 1024):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--from-archive', type=Path, required=True)
    p.add_argument('--to-archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    c = read_json(a.catalog)
    e = read_json(a.evidence)
    result = audit(c, e)
    if digest(a.from_archive) != c['graphFingerprints']['from']:
        fail("Real original A archive SHA-256 mismatch")
    if digest(a.to_archive) != c['graphFingerprints']['to']:
        fail("Real original B archive SHA-256 mismatch")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
