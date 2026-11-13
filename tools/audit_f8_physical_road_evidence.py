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
import math
import os
import tempfile
from collections import Counter
from pathlib import Path


def read_json(path: Path) -> dict:
    with (gzip.open(path, 'rt') if str(path).endswith('.gz') else path.open()) as fd:
        return json.load(fd)


def fail(message: str) -> None:
    raise ValueError(message)



def original_native_submetre_overlap_verified(entry: dict) -> bool:
    """Independently audit native sub-metre source tangent and B direction.

    X proximity alone, a neighboring road or an opposite direction never
    establishes original physical-road correspondence.
    """
    source_length = entry.get('sourceNativeApproachSegmentMetres')
    progress = entry['directedOverlapProgressMetres']
    return (type(source_length) in (int, float) and math.isfinite(source_length)
            and 0.5 <= source_length < 1.0 and progress >= 0.5
            and progress >= source_length - 0.12
            and entry['distanceXMetres'] <= 0.10
            and entry['distanceSourceApproachMetres'] <= 0.10)


def original_native_directional_overlap_verified(entry: dict) -> bool:
    return (entry['directedOverlapProgressMetres'] >= 1.0
            or original_native_submetre_overlap_verified(entry))


def original_native_incoming_at_x(row: dict) -> dict[int, dict]:
    """Independently reread directed B incoming approach, never nearest-point alone."""
    accepted = {}
    for entry in row['receiverDirectedCandidatesAtX']:
        for name in ('distanceSourceApproachMetres', 'distanceXMetres',
                     'directedOverlapProgressMetres'):
            value = entry[name]
            if (type(value) not in (int, float) or not math.isfinite(value) or
                    (name != 'directedOverlapProgressMetres' and value < 0)):
                fail("Invalid or nonfinite original native B directed distance evidence")
        if (entry['status'] != 'B_PREDECESSOR_ENDS_AT_X_NEEDS_NATIVE_SUCCESSOR'
                or entry['distanceSourceApproachMetres'] > 0.75
                or entry['distanceXMetres'] > 0.75
                or not original_native_directional_overlap_verified(entry)
                or not entry['sameLayerBridgeTunnel']):
            continue
        gid = entry['receiverDirectedGraphId']
        if gid in accepted:
            fail("Duplicate directed original B incoming approach")
        accepted[gid] = entry
    # This equality also catches a source incorrectly labelled as an excluded
    # dead end merely because its B approach was silently suppressed.
    # X may be inside a single original B edge instead of at the end of
    # an original B predecessor: either geometry representation is valid.
    interior = [
        entry for entry in row['receiverDirectedCandidatesAtX']
        if (entry['status'] == 'MATCHED_DIRECTED_SOURCE_GEOMETRY_OVERLAP'
            and entry['distanceXMetres'] <= 0.75
            and entry['distanceSourceApproachMetres'] <= 0.75
            and original_native_directional_overlap_verified(entry)
            and entry['receiverRemainingMetresAfterX'] >= 1.0
            and entry['sameLayerBridgeTunnel'])
    ]
    if (not accepted and not interior) or set(accepted) != set(row['correspondingBPredecessorAtXGraphIds']):
        fail("Native original B predecessor/interior directional road identities at X disagree")
    return accepted



def verify_original_native_conditional_mode_partition(row: dict) -> None:
    """An allowed motorcycle B turn remains routable even when car is unknown.

    Existing native reader can return e.g. car=UNRESOLVED_PATH_OR_TIME_CONTEXT
    and motorcycle=ALLOWED_NATIVE_IMMEDIATE for the *same original B edge*.
    Do not convert a partly unknown turn to all-mode denied/allowed.
    """
    allowed = {v['receiverDirectedGraphId']: v
               for v in row['receivingNativeDirectedContinuationOptions']}
    if len(allowed) != len(row['receivingNativeDirectedContinuationOptions']):
        fail("Repeated original native B legal outgoing GraphId")
    valid = {
        'UNRESOLVED_PATH_OR_TIME_CONTEXT',
        'UNRESOLVED_HIERARCHY_CONTEXT',
        'UNRESOLVED_SHORTCUT',
        'ALLOWED_NATIVE_IMMEDIATE',
        # A legal-mode unknown paired with an explicitly inaccessible or
        # statically denied other mode is still UNRESOLVED, not all-mode pass.
        'NO_MODE_ACCESS',
        'DENIED_NATIVE_IMMEDIATE',
    }
    for uncertain in row['receivingNativeUnresolvedContinuations']:
        if (uncertain.get('car') not in valid or
                uncertain.get('motorcycle') not in valid or
                not any(uncertain[mode].startswith('UNRESOLVED_')
                        for mode in ('car', 'motorcycle'))):
            fail("Original B conditional status was falsely accepted or denied")
        gid = uncertain['receiverDirectedGraphId']
        for mode, mask in (('car', 1), ('motorcycle', 1024)):
            is_allowed = uncertain[mode] == 'ALLOWED_NATIVE_IMMEDIATE'
            actually_recorded = bool(allowed.get(gid, {}).get('sharedVehicleModes', 0) & mask)
            if is_allowed and not actually_recorded:
                fail("A positive original native B mode was suppressed")
            if is_allowed:
                if (uncertain['receiverPredecessorGraphId'] not in
                        allowed[gid]['fromNativeBPredecessorGraphIds']):
                    fail("Original B motorcycle-only successor lost its native predecessor")
            elif actually_recorded:
                # Native B options may union legal access from MULTIPLE incoming
                # predecessors. Do not veto a legal mode from another original
                # B predecessor just because THIS predecessor's status is unknown.
                # With a single predecessor, claiming unknown AND legal from it
                # is an inconsistency and must fail closed.
                pred = allowed[gid]['fromNativeBPredecessorGraphIds']
                if (len(pred) == 1 and
                        pred[0] == uncertain['receiverPredecessorGraphId']):
                    fail("A conditional original B mode was incorrectly promoted")

def independently_reconcile_source_roots(catalog: dict, evidence: dict,
                                          native_ids: set[int],
                                          all_source_evidence_ids: set[int]) -> dict:
    """Root observations and true final directed edges are distinct inventories.

    This attests the existing bounded root analysis without tracing another
    edge or falsely treating an unlinked root as a missing physical road.
    """
    records = evidence.get('originalSourceCutRootCoverage')
    recorded_counts = evidence.get('originalSourceCutRootCoverageCounts')
    if not isinstance(records, list) or not isinstance(recorded_counts, dict):
        fail("Missing original compiled A cut-root coverage evidence")
    valid = {
        'ROOT_HAS_NATIVE_RECEIVER_OPTIONS_SOURCE_LINEAGE_UNPROVEN',
        'ROOT_TERMINAL_CANDIDATE_NO_CONFIRMED_RECEIVER',
        'ROOT_NO_TERMINAL_CANDIDATE_WITHIN_TWO_BOUNDED_HOPS',
    }
    counter = Counter()
    ids = set()
    unlinked = set()
    candidate_ids = {
        row['sourceFinalDirectedGraphId']
        for row in catalog['connectionCandidates']
    }
    for record in records:
        gid = record.get('originalSourceCutGraphId')
        if type(gid) is not int or gid <= 0 or gid in ids:
            fail("Repeated or invalid original source cut-root GraphId")
        ids.add(gid)
        status = record.get('boundedOriginalSourceRootStatus')
        related = record.get('boundedRelatedAOriginalFinalGraphIds')
        if (status not in valid or
                record.get('physicalRoadDirectionCompleteness') != 'NOT_VERIFIED' or
                not isinstance(related, list) or
                any(type(x) is not int or x <= 0 for x in related) or
                len(set(related)) != len(related) or
                not set(related) <= all_source_evidence_ids):
            fail("Invalid bounded native source-root-to-terminal evidence")
        if status == 'ROOT_NO_TERMINAL_CANDIDATE_WITHIN_TWO_BOUNDED_HOPS':
            if related:
                fail("Unlinked bounded source root has an attached terminal")
            unlinked.add(gid)
        elif (not related or
              (status == 'ROOT_HAS_NATIVE_RECEIVER_OPTIONS_SOURCE_LINEAGE_UNPROVEN') !=
              bool(set(related) & candidate_ids)):
            fail("Native source-root B-connection evidence misclassified")
        counter[status] += 1
    if (dict(counter) != recorded_counts or
            sorted(unlinked) != sorted(catalog.get('unresolvedOriginalCutRootLineageGraphIds', [])) or
            len(unlinked) != catalog['counts'].get('originalSourceCutRootsNotLinkedWithinBoundedScope')):
        fail("Source-cut root count/missing-root list changed or suppressed")
    if not native_ids <= all_source_evidence_ids:
        fail("Source evidence missing true bounded native outer-cut final edge")
    return {
        'originalSourceRootObservations': len(ids),
        'boundedUnlinkedRootObservations': len(unlinked),
        'boundedRootDispositionCounts': dict(sorted(counter.items())),
        'unlinkedRootsAreNotProvenDistinctMissingRoads': True,
    }

def valid_bounded_terminal_tile_scope(inventory: dict) -> bool:
    """Fail closed on native source-census tile scope or provenance expansion.

    The original shared cut remains unchanged. Extra tiles can only be
    original indexed B-outside-A endpoint owners or exact incident owners
    returned by native Valhalla; never an entire source-graph census.
    """
    scope = inventory.get('sourceTerminalInventoryScope')
    endpoint_n = inventory.get('additionalIndexedEndpointDomainTiles', 0)
    owner_n = inventory.get('additionalNativeIncomingOwnerTiles', 0)
    if any(type(v) is not int or v < 0 for v in (endpoint_n, owner_n)):
        return False
    if scope == 'PAIR_SHARED_OUTER_CUTOFF_TILES_ONLY':
        return endpoint_n == 0 and owner_n == 0
    if scope not in (
        'PAIR_SHARED_CUTOFF_PLUS_INDEXED_B_OUTSIDE_A_ENDPOINT_TILES',
        'PAIR_SHARED_CUTOFF_PLUS_INDEXED_ENDPOINT_AND_NATIVE_OWNER_TILES',
    ):
        return False
    selected = inventory.get('originalSourceBoundaryTileCount')
    cut = inventory.get('originalSourceCutBoundaryTileCount')
    indexed = inventory.get('indexedSourceTilesIntersectingOuterXDomain')
    if (any(type(v) is not int or v <= 0 for v in (selected, cut, indexed)) or
            selected != cut + endpoint_n + owner_n or indexed > selected):
        return False
    endpoint_ids = inventory.get('additionalIndexedEndpointDomainTileIds')
    owner_ids = inventory.get('additionalNativeIncomingOwnerTileIds')
    if (not isinstance(endpoint_ids, list) or not isinstance(owner_ids, list) or
            len(endpoint_ids) != endpoint_n or len(owner_ids) != owner_n or
            any(type(x) is not int or x <= 0 for x in endpoint_ids + owner_ids) or
            len(set(endpoint_ids + owner_ids)) != len(endpoint_ids) + len(owner_ids)):
        return False
    if scope == 'PAIR_SHARED_CUTOFF_PLUS_INDEXED_B_OUTSIDE_A_ENDPOINT_TILES':
        return endpoint_n > 0 and owner_n == 0
    return owner_n > 0


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
    predecessor_owner = {}
    # The audit has an intentionally *stronger* standard than native turn legality.
    # Never mark a branch physical-road VERIFIED without a separate approved proof.
    for candidate in catalog['connectionCandidates']:
        sid = candidate['sourceFinalDirectedGraphId']
        if sid in source_ids or sid not in by_source:
            fail("Duplicate or missing source-native readback")
        source_ids.add(sid)
        row = by_source[sid]
        verify_original_native_conditional_mode_partition(row)
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
        expected_source_modes = {mode for flag, mode in ((1, 'auto'), (1024, 'motorcycle'))
                                 if row['sourceVehicleModes'] & flag}
        if (set(candidate['sourceValhallaProvedModes']) != expected_source_modes
                or candidate['sourceOriginalNativeRoadClass'] != row['sourceNativeRoadClass']
                or candidate['sourceOriginalNativeRoadUse'] != row['sourceNativeRoadUse']
                or candidate['sourceNativeLayer'] != row['sourceNativeLayer']
                or candidate['sourceNativeBridge'] != row['sourceNativeBridge']
                or candidate['sourceNativeTunnel'] != row['sourceNativeTunnel']):
            fail("Original A directed source road identity/modes changed")
        if (candidate['receiverCorrelationStatus'] != row['receiverCorrelationStatus'] or
                candidate['unresolvedOriginalNativeBTransitions'] !=
                row['receivingNativeUnresolvedContinuations']):
            fail("Conditional original B junction alternatives were changed or suppressed")
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
            is_interior = (original['status'] ==
                           'VERIFIED_B_DIRECTED_INTERIOR_SOURCE_OVERLAP')
            if is_interior:
                if (option['nativeOriginalBPredecessorDirectedGraphIds']
                        or original['originalNativeBranchRelationshipEvidence'] !=
                            'INTERIOR_B_EDGE_OVERLAP_PHYSICAL_IDENTITY_UNVERIFIED'):
                    fail("B original interior road identity incorrectly represented as a successor")
            else:
                if (abs(option['nativeReceiverStartGapMetres'] -
                        original['nativeReceiverStartGapMetres']) > 0.000001
                        or option['nativeReceiverStartGapMetres'] > 0.75):
                    fail("B original successor entry point moved away from X")
            for field in ('receiverNativeRoadClass', 'receiverNativeRoadUse',
                          'receiverNativeLayer', 'receiverNativeBridge',
                          'receiverNativeTunnel', 'nativeSameClassAsBPredecessor',
                          'nativeSameUseAsBPredecessor',
                          'nativeSameStructureAsBPredecessor'):
                if option.get(field) != original.get(field):
                    fail("B original native attribute mismatch: " + field)
            if option['nativeCorrespondenceEvidence'] != original['status']:
                fail("Native B directional/turn status changed")
            key = option['nativePhysicalBranchEvidence']
            class_counts[key] += 1
            status_counts[tuple(sorted(option['travelModes']))] += 1
            options_by_evidence[(sid, oid)] = key
        # The B predecessor of each source must have original A approach
        # geometrical overlap; B junction successors alone do not prove identity.
        incoming = original_native_incoming_at_x(row)
        if set(candidate['nativeBOriginalPredecessorGraphIds']) != set(incoming):
            fail("Candidate original B predecessor identities differ from native road approach")
        for b_incoming_gid in incoming:
            if b_incoming_gid in predecessor_owner and predecessor_owner[b_incoming_gid] != sid:
                fail("Two different A terminal directed edges claim the SAME original B incoming road")
            predecessor_owner[b_incoming_gid] = sid
        for option in candidate['receiverOptions']:
            if not set(option['nativeOriginalBPredecessorDirectedGraphIds']) <= set(incoming):
                fail("Receiver continuation is not attached to independently verified B incoming physical approach")
            if option['nativeCorrespondenceEvidence'] == 'VERIFIED_B_ORIGINAL_SAME_NODE_LEGAL_BRANCH':
                if not option['nativeOriginalBPredecessorDirectedGraphIds']:
                    fail("B successor turn without native B predecessor")
            elif option['nativeCorrespondenceEvidence'] == 'VERIFIED_B_DIRECTED_INTERIOR_SOURCE_OVERLAP':
                if (option['nativeOriginalBPredecessorDirectedGraphIds']
                        or not any(
                          raw['receiverDirectedGraphId'] == option['receiverFirstDirectedGraphId']
                          and raw['status'] == 'MATCHED_DIRECTED_SOURCE_GEOMETRY_OVERLAP'
                          and raw['sameLayerBridgeTunnel']
                          and raw['distanceXMetres'] <= 0.75
                          and original_native_directional_overlap_verified(raw)
                          for raw in row['receiverDirectedCandidatesAtX'])):
                    fail("B interior directed edge was not independently matched at X")
            else:
                fail("Unverified original B directed road relationship")
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
        verify_original_native_conditional_mode_partition(original)
        if (exception['sourceOriginalNativeEndNodeGraphId'] !=
                original['sourceOriginalEndNodeGraphId'] or
                abs(exception['sourceFinalCoordinate']['lat'] - original['x']['lat']) > 0.00000001 or
                abs(exception['sourceFinalCoordinate']['lng'] - original['x']['lon']) > 0.00000001):
            fail("Unresolved final lost original native endpoint/node")
        if (exception['nativeBOriginalPredecessorGraphIds'] !=
                original['correspondingBPredecessorAtXGraphIds']):
            fail("Unresolved original B predecessor identities were altered")
        if exception['unresolvedOriginalNativeBTransitions'] != original['receivingNativeUnresolvedContinuations']:
            fail("Conditional unresolved source B directed alternatives were changed or suppressed")
        # A "no native allowed continuation" is a negative finding about
        # the checked native costing context, not proof the road cannot
        # continue for a different path, date or vehicle costing context.
        if original['receivingNativeDirectedContinuationOptions']:
            fail("Unmatched source has an omitted original B statically permitted edge")
        expected_source_modes = {mode for flag, mode in ((1, 'auto'), (1024, 'motorcycle'))
                                 if original['sourceVehicleModes'] & flag}
        if set(exception['sourceValhallaProvedModes']) != expected_source_modes:
            fail("Unmatched original A source legal mode mask changed")
        if (exception['receiverCorrelationStatus'] != original['receiverCorrelationStatus']
                or exception['sourceOriginalNativeRoadClass'] != original['sourceNativeRoadClass']
                or exception['sourceOriginalNativeRoadUse'] != original['sourceNativeRoadUse']
                or exception['sourceNativeLayer'] != original['sourceNativeLayer']
                or exception['sourceNativeBridge'] != original['sourceNativeBridge']
                or exception['sourceNativeTunnel'] != original['sourceNativeTunnel']):
            fail("Unmatched source original-native road attributes or status changed")
        unknown = bool(original['receivingNativeUnresolvedContinuations'])
        expected_status = ('B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED' if unknown
                           else 'NO_PROVEN_B_NATIVE_OUTGOING_AFTER_X')
        expected_reason = ('ORIGINAL_B_CONDITIONAL_HIERARCHY_OR_PATH_CONTEXT_UNRESOLVED' if unknown
                           else 'NO_ORIGINAL_B_NATIVE_ALLOWED_FORWARD_CONTINUATION')
        if (exception['receiverCorrelationStatus'] != expected_status
                or exception['reason'] != expected_reason):
            fail("Incorrect disposition of a native B conditional or non-routable exception")
        incoming = original_native_incoming_at_x(original)
        if set(exception['nativeBOriginalPredecessorGraphIds']) != set(incoming):
            fail("Exception original B incoming directed geometry identity changed")
        for b_incoming_gid in incoming:
            if b_incoming_gid in predecessor_owner and predecessor_owner[b_incoming_gid] != sid:
                fail("Unmatched A source duplicates a confirmed original B directed approach")
            predecessor_owner[b_incoming_gid] = sid
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
            native_inventory.get('nativeLongEdgeOriginCoverage') !=
                'VERIFIED_FOR_ORIGINAL_PAIR_ENDPOINT_DOMAIN' or
            native_inventory.get('terminalEndpointDomainTileCoverage') !=
                'COMPLETE_FOR_ORIGINAL_INDEX_BOUNDS' or
            not valid_bounded_terminal_tile_scope(native_inventory) or
            native_inventory.get('wholeGraphCensusPerformed') is not False):
        fail("Catalog source IDs do not exactly match independent bounded native A terminal census")
    # Primary A -> exact X -> directed B road correspondence. This MUST
    # include every original A terminal regardless of whether the B matching
    # road has a statically allowed outgoing successor at X.
    primary = catalog.get('nativeDirectedRoadMatchesAtX')
    if not isinstance(primary, list):
        fail('Missing outgoing-turn-independent original B directed-road matches')
    matched_sources = set()
    matched_b_roads = set()
    total_roads = 0
    for record in primary:
        sid = record['sourceFinalDirectedGraphId']
        if sid not in source_ids or sid in matched_sources:
            fail('Duplicate or invented original A primary directed-road match')
        matched_sources.add(sid)
        native = by_source[sid]
        if (record['sourceFinalCoordinate'] !=
                {'lat':native['x']['lat'],'lng':native['x']['lon']}
                or set(record['sourceValhallaProvedModes']) !=
                   {name for bit,name in ((1,'auto'),(1024,'motorcycle'))
                    if native['sourceVehicleModes'] & bit}
                or record['productionRouteVerified'] is not False):
            fail('Primary original A GraphId, X, modes or publication evidence changed')
        observed = {}
        for entry in native['receiverDirectedCandidatesAtX']:
            if entry['status'] not in (
                    'B_PREDECESSOR_ENDS_AT_X_NEEDS_NATIVE_SUCCESSOR',
                    'MATCHED_DIRECTED_SOURCE_GEOMETRY_OVERLAP'):
                continue
            if (entry['distanceXMetres'] > 0.75
                    or entry['distanceSourceApproachMetres'] > 0.75
                    or not original_native_directional_overlap_verified(entry)
                    or not entry['sameLayerBridgeTunnel']):
                fail('Native B approach geometry cannot support matched road')
            gid = entry['receiverDirectedGraphId']
            if gid in observed:
                fail('Duplicate original B directed native match')
            observed[gid] = entry
        reported = record['receiverDirectedRoadsAtX']
        if (len(reported) != len({r['receiverDirectedGraphId'] for r in reported})
                or {r['receiverDirectedGraphId'] for r in reported} != set(observed)
                or record['status'] != (
                    'NATIVE_DIRECTED_ROAD_MATCH_AT_X' if observed
                    else 'NO_VERIFIED_DIRECTED_RECEIVER_ROAD_AT_X')):
            fail('Original B directed physical road was omitted or falsely matched')
        for r in reported:
            gid = r['receiverDirectedGraphId']
            e = observed[gid]
            expected_position = ('END_NODE' if
                e['receiverRemainingMetresAfterX'] < 1.0 else 'INTERIOR')
            if (r['receiverXPosition'] != expected_position
                    or r['nativeGeometryRelationship'] != e['status']
                    or r['nativeCommonVehicleModes'] !=
                        (e['commonVehicleModes'] & native['sourceVehicleModes'] & 1025)
                    or abs(r['distanceXMetres'] - e['distanceXMetres']) > 1e-9
                    or abs(r['directedApproachOverlapMetres'] -
                           e['directedOverlapProgressMetres']) > 1e-9
                    or r['productionRouteVerified'] is not False):
                fail('Original B road snapping geometry, direction, modes or evidence was altered')
            for attr in ('receiverNativeRoadClass','receiverNativeRoadUse',
                         'receiverNativeLayer','receiverNativeBridge',
                         'receiverNativeTunnel'):
                if r[attr] != e[attr]:
                    fail('Original B directed physical road identity/structure was altered')
            # Never deduplicate distinct A final edges based on name or road
            # attributes. A duplicate B incoming directed ID is a real conflict.
            if gid in matched_b_roads:
                fail('Original B incoming road claimed by multiple source finals')
            matched_b_roads.add(gid)
            total_roads += 1
    if matched_sources != source_ids:
        fail('A native source final was missing from the directed road match records')
    counts = catalog['counts']
    if (counts.get('sourceFinalsWithMatchedBDirectedRoadAtX') !=
            sum(bool(r['receiverDirectedRoadsAtX']) for r in primary)
            or counts.get('sourceFinalsWithoutMatchedBDirectedRoadAtX') !=
            sum(not r['receiverDirectedRoadsAtX'] for r in primary)
            or counts.get('nativeBDirectedRoadMatchesAtX') != total_roads):
        fail('Primary directed road matching counts changed or omitted')
    if (len(source_ids) != counts['eligibleSourceFinals']
            or len(catalog['connectionCandidates']) != counts['candidateSourcesWithBOptions']
            or len(unresolved) != counts['unresolvedEligibleSourceFinals']
            or len(options_by_evidence) != counts['nativeOriginalBDirectedOptions']):
        fail("Suppressed or invented source/branch candidates")
    if dict(class_counts) != counts['branchAttributeEvidenceCounts']:
        fail('Original B attribute categories changed or suppressed')
    if not source_ids <= set(by_source):
        fail('Native A exterior terminal source missing from paired evidence')
    root_report = independently_reconcile_source_roots(
        catalog, evidence, source_ids, set(by_source))
    candidate_partials = sum(bool(r['unresolvedOriginalNativeBTransitions'])
                             for r in catalog['connectionCandidates'])
    unresolved_by_reason = Counter(r['reason'] for r in unresolved)
    conditional_counts = {
        'nativeAllowedSourceFinalsWithOtherUnknownBTurns': candidate_partials,
        'nativeAllowedBOptionsWithUnknownSiblings':
            sum(len(r['unresolvedOriginalNativeBTransitions'])
                for r in catalog['connectionCandidates']),
        'nativeUnknownBOptionsOnUnmatchedSourceFinals':
            sum(len(r['unresolvedOriginalNativeBTransitions']) for r in unresolved),
    }
    return {
        'schema': 'roadpilot.f8-pr127-independent-physical-identity-audit-v1',
        'pairId': catalog['pairId'],
        'originalArchiveFingerprints': catalog['graphFingerprints'],
        'eligibleOriginalSourceFinals': len(source_ids),
        'originalASourceFinalsEvaluatedForDirectRoadMatching': len(primary),
        'originalBDirectRoadMatchCount': total_roads,
        'originalASourcesWithNoDirectedBMatch':
            counts['sourceFinalsWithoutMatchedBDirectedRoadAtX'],
        'verifiedNativeAOriginalBDirectedIncomingAtExactX': len(source_ids),
        'originalBDirectedIncomingIdentityUniqueAcrossASources': True,
        'distinctOriginalBIncomingDirectedGraphIds': len(predecessor_owner),
        'originalNativeIndependentTerminalDomain': 'EXTERIOR_A_WITHIN_ORIGINAL_B_PAIR_TILES',
        'eligibleSourceDispositions': {
            'nativeAllowedBSuccessorSources': len(catalog['connectionCandidates']),
            'nativeNoAllowedBSuccessorAtCheckedContext':
                unresolved_by_reason['NO_ORIGINAL_B_NATIVE_ALLOWED_FORWARD_CONTINUATION'],
            'nativeBPathTimeOrHierarchyUnresolvedNoAllowed':
                unresolved_by_reason['ORIGINAL_B_CONDITIONAL_HIERARCHY_OR_PATH_CONTEXT_UNRESOLVED'],
        },
        'conditionalBUncertainty': conditional_counts,
        'sourceRootLineage': root_report,
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



def build_test_only_original_handoffs(catalog: dict, evidence: dict) -> dict:
    """Expose ONLY independently audited original directed seam relations for Android acceptance.

    Not an approved physical-road catalog. Each B outgoing edge is a native
    legal branch after a verified incoming B approach; same-road status remains
    UNKNOWN (including cases where its class/use/structure happens to match).
    Unresolved A finals and unresolved conditional B turns must remain visible.
    This reuses the original PR127 A -> X -> B matcher; no new discovery stage.
    """
    report = audit(catalog, evidence)
    records = []
    for candidate in sorted(catalog['connectionCandidates'],
                            key=lambda row: row['sourceFinalDirectedGraphId']):
        modes = sorted(candidate['sourceValhallaProvedModes'])
        branches = []
        for opt in sorted(candidate['receiverOptions'],
                          key=lambda row: row['receiverFirstDirectedGraphId']):
            branches.append({
                'originalBDirectedGraphId': opt['receiverFirstDirectedGraphId'],
                'nativeBIncomingDirectedGraphIds':
                    sorted(opt['nativeOriginalBPredecessorDirectedGraphIds']),
                'nativeRelationship': opt['nativePhysicalBranchEvidence'],
                'nativeXGapMetres': opt['nativeReceiverStartGapMetres'],
                'travelModes': sorted(opt['travelModes']),
                'nativeBIncomingPhysicalApproachOverlapsA': True,
                'nativeBOutgoingTurnAndDirectionVerified': True,
                'samePhysicalRoadAfterJunction': 'NOT_VERIFIED',
            })
        records.append({
            'originalASourceFinalDirectedGraphId':
                candidate['sourceFinalDirectedGraphId'],
            'originalAEndNodeGraphId':
                candidate['sourceOriginalNativeEndNodeGraphId'],
            'nativeX': candidate['sourceFinalCoordinate'],
            'travelModes': modes,
            'originalBBranches': branches,
            'nativeIncomingRoadAndDirectionAtXVerified': True,
            'sourcePhysicalRoadFinalCompleteness': 'NOT_VERIFIED',
            'hasUnresolvedNativeBTransitions':
                bool(candidate['unresolvedOriginalNativeBTransitions']),
            'unresolvedNativeBTransitions':
                candidate['unresolvedOriginalNativeBTransitions'],
        })
    exceptions = [{
        'originalASourceFinalDirectedGraphId': row['sourceFinalDirectedGraphId'],
        'nativeX': row['sourceFinalCoordinate'],
        'reason': row['reason'],
        'travelModes': sorted(row['sourceValhallaProvedModes']),
        'mustNotCreateConnection': True,
        'unresolvedNativeBTransitions':
            row['unresolvedOriginalNativeBTransitions'],
    } for row in sorted(catalog['unresolvedSourceFinalEdges'],
                        key=lambda row: row['sourceFinalDirectedGraphId'])]
    result = {
        'schema': 'roadpilot.f8-original-native-handoff-test-only',
        'version': 1,
        'pairId': catalog['pairId'],
        'fromRegionId': catalog['fromRegionId'],
        'toRegionId': catalog['toRegionId'],
        'originalGraphArchiveSha256': catalog['graphFingerprints'],
        'originalSourceEvidenceSha256': catalog['originalSourceEvidenceSha256'],
        'sourceBufferFingerprint': catalog['sourceBufferFingerprint'],
        'receiverBufferFingerprint': catalog['receiverBufferFingerprint'],
        'sourceGraphIndexFingerprint': catalog['sourceGraphIndexFingerprint'],
        'receiverGraphIndexFingerprint': catalog['receiverGraphIndexFingerprint'],
        'originalSourceTerminalInventory':
            'VERIFIED_FOR_ORIGINAL_B_COVERED_OUTER_ENDPOINT_DOMAIN',
        'nativeBIncomingAndLegalOutgoing': 'VERIFIED_FOR_RECORDED_OPTIONS',
        'sourcePhysicalRoadIdentityAcceptance': 'NOT_VERIFIED',
        'sourceDiscoveryComplete': False,
        'receiverMatchingComplete': False,
        'androidFullJourneyAcceptance': 'NOT_RUN',
        'productionPublication': 'BLOCKED',
        'testOnly': True,
        'counts': {
            'eligibleSourceFinals': report['eligibleOriginalSourceFinals'],
            'nativeAWithBOptions': report['sourceCandidatesWithNativeBOptions'],
            'originalBDirectedOptions': report['preservedDirectedBOptions'],
            'unresolvedSourceFinals': report['explicitUnresolvedFinalSources'],
            'sourceRootsNotLinked':
                len(catalog.get('unresolvedOriginalCutRootLineageGraphIds', [])),
        },
        'nativeDirectedHandoffs': records,
        'unresolvedSourceFinals': exceptions,
        'unresolvedOriginalCutRootGraphIds':
            sorted(catalog.get('unresolvedOriginalCutRootLineageGraphIds', [])),
    }
    return result


def all_original_b_native_directed_roads_at_x(row: dict) -> dict[int, dict]:
    """Keep ALL existing original-native B matches: endpoint AND interior.

    The predecessor list is intentionally END_NODE-only for native successor
    costing. Publication dispositions must not inherit that restriction:
    the same A final may also intersect a distinct B directed edge interior.
    """
    matched = dict(original_native_incoming_at_x(row))
    for entry in row['receiverDirectedCandidatesAtX']:
        if entry['status'] != 'MATCHED_DIRECTED_SOURCE_GEOMETRY_OVERLAP':
            continue
        if (entry['distanceXMetres'] > 0.75
                or entry['distanceSourceApproachMetres'] > 0.75
                or not original_native_directional_overlap_verified(entry)
                or entry['receiverRemainingMetresAfterX'] < 1.0
                or not entry['sameLayerBridgeTunnel']):
            fail('Unverified native B interior road was promoted to disposition')
        gid = entry['receiverDirectedGraphId']
        if gid in matched:
            fail('Native B directed road repeated as both END_NODE and INTERIOR')
        matched[gid] = entry
    return matched


def build_bounded_physical_road_dispositions(catalog: dict, evidence: dict) -> dict:
    """No new discovery: reproducible per-original-GraphId M1 acceptance ledger.

    Original Valhalla A directed final incoming road *up to* X is natively
    matched to original directed B incoming road at X. A B outgoing edge is
    separately an actual statically legal branch, not necessarily the same
    physical road after the junction. Incompleteness is still explicit.
    """
    report = audit(catalog, evidence)
    by_source = {row['sourceFinalDirectedGraphId']: row
                 for row in evidence['sourceToReceiverCandidates']}
    candidate_ids = {
        r['sourceFinalDirectedGraphId']: r for r in catalog['connectionCandidates']
    }
    exceptions = {
        r['sourceFinalDirectedGraphId']: r for r in catalog['unresolvedSourceFinalEdges']
    }
    records = []
    status_counts = Counter()
    for sid in sorted(candidate_ids.keys() | exceptions.keys()):
        original = by_source[sid]
        candidate = candidate_ids.get(sid)
        exception = exceptions.get(sid)
        incoming = all_original_b_native_directed_roads_at_x(original)
        # The independent audit already checked these raw B identities
        # against the actual primary A→X→B catalog, including both modes.
        legal = sorted(original['receivingNativeDirectedContinuationOptions'],
                       key=lambda row: row['receiverDirectedGraphId'])
        conditional = sorted(original['receivingNativeUnresolvedContinuations'],
                             key=lambda row: (row['receiverPredecessorGraphId'],
                                              row['receiverDirectedGraphId']))
        if candidate:
            category = ('NATIVE_LEGAL_B_BRANCHES_WITH_CONDITIONAL_UNCERTAINTY'
                        if conditional else 'NATIVE_LEGAL_B_BRANCHES_NO_KNOWN_UNCERTAINTY')
        elif conditional:
            category = 'NO_NATIVE_ALLOWED_B_BRANCH_WITH_CONDITIONAL_UNCERTAINTY'
        else:
            category = 'NO_NATIVE_ALLOWED_B_BRANCH_AT_CHECKED_CONTEXT'
        status_counts[category] += 1
        records.append({
            'originalASourceFinalDirectedGraphId': sid,
            'originalAEndNodeGraphId': original['sourceOriginalEndNodeGraphId'],
            'exactX': {'lat': original['x']['lat'], 'lng': original['x']['lon']},
            'originalSourceCarMotorcycleModeMask': original['sourceVehicleModes'],
            'nativeBIncomingDirectedGraphIds': sorted(incoming),
            'nativeBIncomingDirectedOverlapMetres':
                {str(gid): incoming[gid]['directedOverlapProgressMetres']
                 for gid in sorted(incoming)},
            'nativeBIncomingAtXMaxDeviationMetres':
                max(incoming[gid]['distanceXMetres'] for gid in incoming),
            'originalAtoBIncomingDirectedApproach': 'NATIVE_GEOMETRY_TOPOLOGY_VERIFIED',
            'nativeLegalOriginalBBranches': [{
                'receiverDirectedGraphId': option['receiverDirectedGraphId'],
                'originalBIncomingPredecessorGraphIds':
                    sorted(option['fromNativeBPredecessorGraphIds']),
                'sharedOriginalVehicleModeMask': option['sharedVehicleModes'],
                'nativeTurnStatus': option['status'],
                'sameRoadAfterJunction': 'NOT_VERIFIED',
                'nativeStructureAndClassEvidence':
                    option['originalNativeBranchRelationshipEvidence'],
            } for option in legal],
            'unresolvedNativeBTransitions': conditional,
            'disposition': category,
            'mustNotPublishAsReady': True,
            'mustNotCreateConnection': candidate is None,
            'sourceRoadDirectionCensusCompleteness': 'NOT_VERIFIED',
        })
    roots = sorted(evidence['originalSourceCutRootCoverage'],
                   key=lambda row: row['originalSourceCutGraphId'])
    output = {
        'schema': 'roadpilot.f8-pr127-bounded-physical-road-dispositions',
        'version': 1,
        'pairId': catalog['pairId'],
        'fromRegionId': catalog['fromRegionId'],
        'toRegionId': catalog['toRegionId'],
        'originalGraphArchiveSha256': catalog['graphFingerprints'],
        'sourceBufferFingerprint': catalog['sourceBufferFingerprint'],
        'receiverBufferFingerprint': catalog['receiverBufferFingerprint'],
        'sourceGraphIndexFingerprint': catalog['sourceGraphIndexFingerprint'],
        'receiverGraphIndexFingerprint': catalog['receiverGraphIndexFingerprint'],
        'sourceEvidenceSha256': catalog['originalSourceEvidenceSha256'],
        'nativeOriginalSourceTerminalCensus': 'EXHAUSTIVE_WITHIN_PAIR_ENDPOINT_DOMAIN',
        'nativeLongEdgeOwningTileCoverage': 'VERIFIED_WITHIN_PAIR_ENDPOINT_DOMAIN',
        'physicalRoadDirectionCompleteness': 'NOT_VERIFIED',
        'samePhysicalRoadAfterJunctionAcceptance': 'NOT_VERIFIED',
        'androidProductionUIAcceptance': 'NOT_VERIFIED',
        'productionPublication': 'BLOCKED',
        'noAdditionalRoadTracingPerformed': True,
        'counts': {
            'eligibleOriginalAExteriorTerminals': report['eligibleOriginalSourceFinals'],
            'nativeBMatchedIncomingAApproaches':
                report['verifiedNativeAOriginalBDirectedIncomingAtExactX'],
            'nativeLegalOriginalBOptions': report['preservedDirectedBOptions'],
            'sourceFinalDispositions': dict(sorted(status_counts.items())),
            'nativeConditionalBOptionsOnMatchedSources':
                report['conditionalBUncertainty']['nativeAllowedBOptionsWithUnknownSiblings'],
            'nativeConditionalBOptionsOnUnmatchedSources':
                report['conditionalBUncertainty']['nativeUnknownBOptionsOnUnmatchedSourceFinals'],
            'boundedOriginalSourceCutRoots': len(roots),
            'unlinkedOriginalSourceCutRootObservations':
                report['sourceRootLineage']['boundedUnlinkedRootObservations'],
        },
        'nativeOriginalASourceFinalDispositions': records,
        'boundedOriginalSourceCutRootObservations': roots,
        'stopReason':
            'Exact exterior A terminal directed-edge inventory is bounded and exhaustive for '
            'the original B-covered endpoint tile scope. Root lineage is not a unique '
            'physical-road census; native conditional B costing and same-road-after-junction '
            'identity remain unresolved. Do not publish or label a complete physical-road '
            'connection catalog.',
    }
    return output


def atomic_write_new_json(path: Path, value: dict) -> None:
    """Immutable test output, never overwrite a prior independently audited result."""
    if path.exists():
        fail('Original F8 test-only catalog already exists')
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                 dir=path.parent, delete=False) as fd:
        temp = Path(fd.name)
        json.dump(value, fd, sort_keys=True, separators=(',', ':'))
        fd.write('\n')
    try:
        if path.exists():
            fail('Original F8 test-only catalog was created concurrently')
        os.link(temp, path)  # exclusive create; no overwrite or partial file
    finally:
        temp.unlink(missing_ok=True)


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
    p.add_argument('--test-only-catalog-output', type=Path, help='Optional nonpublishing original native directed A-X-B test artifact')
    p.add_argument('--disposition-output', type=Path,
                   help='Optional independently audited per-native-GraphId M1 uncertainty report (BLOCKED)')
    a = p.parse_args()
    c = read_json(a.catalog)
    e = read_json(a.evidence)
    result = audit(c, e)
    if digest(a.from_archive) != c['graphFingerprints']['from']:
        fail("Real original A archive SHA-256 mismatch")
    if digest(a.to_archive) != c['graphFingerprints']['to']:
        fail("Real original B archive SHA-256 mismatch")
    if a.test_only_catalog_output:
        atomic_write_new_json(a.test_only_catalog_output, build_test_only_original_handoffs(c, e))
    if a.disposition_output:
        atomic_write_new_json(a.disposition_output,
                              build_bounded_physical_road_dispositions(c, e))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
