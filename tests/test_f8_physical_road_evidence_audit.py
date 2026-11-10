"""Independent graph-local physical identity audit regression with original native sample."""
import copy
import json
import unittest
from pathlib import Path

from tools.audit_f8_physical_road_evidence import (
    audit, build_test_only_original_handoffs,
    build_bounded_physical_road_dispositions, atomic_write_new_json,
    verify_original_native_conditional_mode_partition)

FIXTURE = Path(__file__).parent / 'fixtures/f8_pr127_original_physical_identity_audit_sample.json'


class OriginalNativePhysicalRoadAuditTests(unittest.TestCase):
    def setUp(self):
        data = json.loads(FIXTURE.read_text())
        self.catalog = data['catalog']
        self.evidence = data['evidence']

    def reject(self):
        with self.assertRaises(ValueError):
            audit(self.catalog, self.evidence)

    def test_original_valhalla_a_x_b_approach_and_two_branches_preserved(self):
        report = audit(self.catalog, self.evidence)
        self.assertEqual(report['sourceCandidatesWithNativeBOptions'], 1)
        self.assertEqual(report['preservedDirectedBOptions'], 2)
        self.assertEqual(report['explicitUnresolvedFinalSources'], 1)
        self.assertEqual(report['fullPhysicalRoadIdentityApproval'], 'NOT_VERIFIED')
        self.assertEqual(report['productionPublication'], 'BLOCKED')

    def test_test_only_artifact_preserves_original_a_x_b_ids_and_native_branches(self):
        result = build_test_only_original_handoffs(self.catalog, self.evidence)
        self.assertEqual(result['schema'], 'roadpilot.f8-original-native-handoff-test-only')
        self.assertTrue(result['testOnly'])
        self.assertEqual(result['productionPublication'], 'BLOCKED')
        self.assertFalse(result['sourceDiscoveryComplete'])
        self.assertEqual(result['counts']['eligibleSourceFinals'], 2)
        self.assertEqual(result['counts']['nativeAWithBOptions'], 1)
        self.assertEqual(result['counts']['originalBDirectedOptions'], 2)
        self.assertEqual(result['counts']['unresolvedSourceFinals'], 1)
        row = result['nativeDirectedHandoffs'][0]
        candidate = self.catalog['connectionCandidates'][0]
        self.assertEqual(row['originalASourceFinalDirectedGraphId'],
                         candidate['sourceFinalDirectedGraphId'])
        self.assertEqual(row['nativeX'], candidate['sourceFinalCoordinate'])
        self.assertEqual(
            {b['originalBDirectedGraphId'] for b in row['originalBBranches']},
            {b['receiverFirstDirectedGraphId'] for b in candidate['receiverOptions']})
        for branch in row['originalBBranches']:
            self.assertTrue(branch['nativeBIncomingPhysicalApproachOverlapsA'])
            self.assertTrue(branch['nativeBOutgoingTurnAndDirectionVerified'])
            self.assertEqual(branch['samePhysicalRoadAfterJunction'], 'NOT_VERIFIED')
        self.assertEqual(len(result['unresolvedSourceFinals']), 1)
        self.assertTrue(result['unresolvedSourceFinals'][0]['mustNotCreateConnection'])

    def test_rejects_removed_native_conditional_b_turns(self):
        record = self.catalog['connectionCandidates'][0]
        original = self.evidence['sourceToReceiverCandidates'][0]
        conditional = {
            'car': 'UNRESOLVED_HIERARCHY_CONTEXT',
            'motorcycle': 'UNRESOLVED_HIERARCHY_CONTEXT',
            'receiverPredecessorGraphId': 999991,
            'receiverDirectedGraphId': 999992,
        }
        record['receiverCorrelationStatus'] = 'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED'
        original['receiverCorrelationStatus'] = 'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED'
        original['receivingNativeUnresolvedContinuations'] = [conditional]
        self.reject()
        record['unresolvedOriginalNativeBTransitions'] = [conditional]
        result = build_test_only_original_handoffs(self.catalog, self.evidence)
        self.assertEqual(result['nativeDirectedHandoffs'][0]['unresolvedNativeBTransitions'],
                         [conditional])
        self.assertTrue(result['nativeDirectedHandoffs'][0]['hasUnresolvedNativeBTransitions'])

    def test_rejects_removed_exception_conditional_b_turns(self):
        original = self.evidence['sourceToReceiverCandidates'][1]
        original['receivingNativeUnresolvedContinuations'] = [{
            'car': 'UNRESOLVED_PATH_OR_TIME_CONTEXT',
            'motorcycle': 'UNRESOLVED_PATH_OR_TIME_CONTEXT',
            'receiverPredecessorGraphId': 99221,
            'receiverDirectedGraphId': 99222,
        }]
        self.reject()

    def test_test_only_artifact_refuses_missing_native_input(self):
        self.evidence['sourceToReceiverCandidates'][0]['receiverDirectedCandidatesAtX'] = []
        with self.assertRaises(ValueError):
            build_test_only_original_handoffs(self.catalog, self.evidence)

    def test_test_only_artifact_cannot_overwrite_existing_catalog(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'native-test-only.json'
            data = build_test_only_original_handoffs(self.catalog, self.evidence)
            atomic_write_new_json(target, data)
            self.assertEqual(json.loads(target.read_text())['schema'], data['schema'])
            original = target.read_bytes()
            with self.assertRaises(ValueError):
                atomic_write_new_json(target, data)
            self.assertEqual(target.read_bytes(), original)

    def test_original_motorcycle_only_legal_b_while_car_time_context_unknown(self):
        catalog_branch = self.catalog['connectionCandidates'][0]['receiverOptions'][0]
        native = self.evidence['sourceToReceiverCandidates'][0]
        original_branch = native['receivingNativeDirectedContinuationOptions'][0]
        catalog_branch['travelModes'] = ['motorcycle']
        original_branch['sharedVehicleModes'] = 1024
        conditional = {
            'car': 'UNRESOLVED_PATH_OR_TIME_CONTEXT',
            'motorcycle': 'ALLOWED_NATIVE_IMMEDIATE',
            'receiverPredecessorGraphId': native['correspondingBPredecessorAtXGraphIds'][0],
            'receiverDirectedGraphId': original_branch['receiverDirectedGraphId'],
        }
        self.catalog['connectionCandidates'][0]['unresolvedOriginalNativeBTransitions'] = [
            conditional]
        self.catalog['connectionCandidates'][0]['receiverCorrelationStatus'] = (
            'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED')
        native['receivingNativeUnresolvedContinuations'] = [conditional]
        native['receiverCorrelationStatus'] = 'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED'
        report = audit(self.catalog, self.evidence)
        self.assertEqual(report['conditionalBUncertainty'][
            'nativeAllowedBOptionsWithUnknownSiblings'], 1)
        ledger = build_bounded_physical_road_dispositions(self.catalog, self.evidence)
        source = ledger['nativeOriginalASourceFinalDispositions'][0]
        self.assertEqual(source['disposition'],
                         'NATIVE_LEGAL_B_BRANCHES_WITH_CONDITIONAL_UNCERTAINTY')
        self.assertEqual(source['nativeLegalOriginalBBranches'][0][
            'sharedOriginalVehicleModeMask'], 1024)
        self.assertEqual(source['unresolvedNativeBTransitions'], [conditional])

        # Dropping the motorcycle routing permission because car is uncertain
        # is a data-integrity bug; likewise silently allowing car is a bug.
        original_branch['sharedVehicleModes'] = 0
        self.reject()
        original_branch['sharedVehicleModes'] = 1025
        self.reject()

    def test_dispositions_cannot_relabel_unknown_b_context_as_known_safe(self):
        native = self.evidence['sourceToReceiverCandidates'][1]
        unresolved = self.catalog['unresolvedSourceFinalEdges'][0]
        conditional = {
            'car': 'UNRESOLVED_HIERARCHY_CONTEXT',
            'motorcycle': 'UNRESOLVED_HIERARCHY_CONTEXT',
            'receiverPredecessorGraphId': native['correspondingBPredecessorAtXGraphIds'][0],
            'receiverDirectedGraphId': 995555,
        }
        native['receivingNativeUnresolvedContinuations'] = [conditional]
        native['receiverCorrelationStatus'] = 'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED'
        unresolved['unresolvedOriginalNativeBTransitions'] = [conditional]
        unresolved['receiverCorrelationStatus'] = 'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED'
        unresolved['reason'] = 'ORIGINAL_B_CONDITIONAL_HIERARCHY_OR_PATH_CONTEXT_UNRESOLVED'
        report = audit(self.catalog, self.evidence)
        self.assertEqual(report['eligibleSourceDispositions'][
            'nativeBPathTimeOrHierarchyUnresolvedNoAllowed'], 1)
        output = build_bounded_physical_road_dispositions(self.catalog, self.evidence)
        self.assertEqual(output['nativeOriginalASourceFinalDispositions'][1]['disposition'],
                         'NO_NATIVE_ALLOWED_B_BRANCH_WITH_CONDITIONAL_UNCERTAINTY')
        unresolved['reason'] = 'NO_ORIGINAL_B_NATIVE_ALLOWED_FORWARD_CONTINUATION'
        self.reject()

    def test_mode_union_preserves_distinct_native_b_predecessor_alternatives(self):
        # A car may be allowed from another independently matched incoming B
        # predecessor even if THIS predecessor needs time/path context.
        evidence = {
            'receivingNativeDirectedContinuationOptions': [{
                'receiverDirectedGraphId': 202,
                'sharedVehicleModes': 1025,
                'fromNativeBPredecessorGraphIds': [101, 102],
            }],
            'receivingNativeUnresolvedContinuations': [{
                'receiverDirectedGraphId': 202,
                'receiverPredecessorGraphId': 101,
                'car': 'UNRESOLVED_PATH_OR_TIME_CONTEXT',
                'motorcycle': 'ALLOWED_NATIVE_IMMEDIATE',
            }],
        }
        verify_original_native_conditional_mode_partition(evidence)

    def test_invalid_nonfinite_native_b_geometry_cannot_prove_road(self):
        original = self.evidence['sourceToReceiverCandidates'][1]
        original['receiverDirectedCandidatesAtX'][-1]['distanceXMetres'] = float('nan')
        self.reject()

    def test_native_cut_root_scope_and_no_link_not_a_new_missing_road(self):
        report = audit(self.catalog, self.evidence)
        self.assertEqual(report['verifiedNativeAOriginalBDirectedIncomingAtExactX'], 2)
        self.assertEqual(report['eligibleSourceDispositions'], {
            'nativeAllowedBSuccessorSources': 1,
            'nativeNoAllowedBSuccessorAtCheckedContext': 1,
            'nativeBPathTimeOrHierarchyUnresolvedNoAllowed': 0,
        })
        self.assertEqual(report['sourceRootLineage']['originalSourceRootObservations'], 3)
        self.assertEqual(report['sourceRootLineage']['boundedUnlinkedRootObservations'], 1)
        self.assertTrue(report['sourceRootLineage']['unlinkedRootsAreNotProvenDistinctMissingRoads'])
        self.assertEqual(report['fullPhysicalRoadIdentityApproval'], 'NOT_VERIFIED')

    def test_per_edge_disposition_does_not_suppress_exact_original_b_branches(self):
        report = build_bounded_physical_road_dispositions(self.catalog, self.evidence)
        self.assertEqual(report['schema'], 'roadpilot.f8-pr127-bounded-physical-road-dispositions')
        self.assertEqual(report['productionPublication'], 'BLOCKED')
        self.assertEqual(report['physicalRoadDirectionCompleteness'], 'NOT_VERIFIED')
        self.assertEqual(report['counts']['eligibleOriginalAExteriorTerminals'], 2)
        self.assertEqual(report['counts']['nativeLegalOriginalBOptions'], 2)
        self.assertEqual(report['counts']['unlinkedOriginalSourceCutRootObservations'], 1)
        records = report['nativeOriginalASourceFinalDispositions']
        self.assertEqual(len(records), 2)
        self.assertEqual(
            [r['originalASourceFinalDirectedGraphId'] for r in records],
            sorted([6307642, 442515258]))
        candidate = records[0]
        self.assertEqual(candidate['disposition'], 'NATIVE_LEGAL_B_BRANCHES_NO_KNOWN_UNCERTAINTY')
        self.assertEqual(len(candidate['nativeLegalOriginalBBranches']), 2)
        self.assertEqual(candidate['originalAtoBIncomingDirectedApproach'],
                         'NATIVE_GEOMETRY_TOPOLOGY_VERIFIED')
        self.assertTrue(all(b['sameRoadAfterJunction'] == 'NOT_VERIFIED'
                            for b in candidate['nativeLegalOriginalBBranches']))
        exception = records[1]
        self.assertEqual(exception['disposition'], 'NO_NATIVE_ALLOWED_B_BRANCH_AT_CHECKED_CONTEXT')
        self.assertEqual(exception['nativeLegalOriginalBBranches'], [])
        self.assertTrue(exception['mustNotCreateConnection'])
        self.assertEqual(len(report['boundedOriginalSourceCutRootObservations']), 3)

    def test_refuses_two_different_source_edges_claiming_same_b_incoming_road(self):
        native = self.evidence['sourceToReceiverCandidates'][1]
        prior = native['correspondingBPredecessorAtXGraphIds'][0]
        other = self.evidence['sourceToReceiverCandidates'][0][
            'correspondingBPredecessorAtXGraphIds'][0]
        native['correspondingBPredecessorAtXGraphIds'] = [other]
        self.catalog['unresolvedSourceFinalEdges'][0]['nativeBOriginalPredecessorGraphIds'] = [other]
        for entry in native['receiverDirectedCandidatesAtX']:
            if entry['receiverDirectedGraphId'] == prior:
                entry['receiverDirectedGraphId'] = other
        self.reject()

    def test_falsified_unmatched_native_b_incoming_approach_fails(self):
        original = self.evidence['sourceToReceiverCandidates'][1]
        original['receiverDirectedCandidatesAtX'] = []
        self.reject()

    def test_falsified_original_b_predecessor_endpoint_fails(self):
        original = self.evidence['sourceToReceiverCandidates'][1]
        original['receiverDirectedCandidatesAtX'][-1]['distanceXMetres'] = 2.0
        self.reject()

    def test_removing_unlinked_source_root_is_a_failing_census(self):
        self.evidence['originalSourceCutRootCoverage'].pop()
        self.reject()

    def test_forging_duplicate_root_provenance_fails(self):
        import copy
        duplicate = copy.deepcopy(self.evidence['originalSourceCutRootCoverage'][0])
        self.evidence['originalSourceCutRootCoverage'].append(duplicate)
        self.evidence['originalSourceCutRootCoverageCounts'][
            'ROOT_HAS_NATIVE_RECEIVER_OPTIONS_SOURCE_LINEAGE_UNPROVEN'] += 1
        self.reject()

    def test_forging_missing_root_link_to_a_terminal_fails(self):
        item = self.evidence['originalSourceCutRootCoverage'][-1]
        item['boundedRelatedAOriginalFinalGraphIds'] = [6307642]
        self.reject()

    def test_changing_cut_root_association_to_wrong_b_candidate_fails(self):
        root = self.evidence['originalSourceCutRootCoverage'][1]
        root['boundedRelatedAOriginalFinalGraphIds'] = [6307642]
        self.reject()

    def test_falsifying_long_edge_origin_scope_fails(self):
        self.evidence['approvedBoundaryExteriorTerminalInventory'][
            'nativeLongEdgeOriginCoverage'] = 'UNVERIFIED'
        self.reject()

    def test_forging_candidate_source_modes_fails(self):
        self.catalog['connectionCandidates'][0]['sourceValhallaProvedModes'] = ['motorcycle']
        self.reject()

    def test_forging_negative_b_legality_with_conditional_unknown_fails(self):
        exception = self.catalog['unresolvedSourceFinalEdges'][0]
        original = self.evidence['sourceToReceiverCandidates'][1]
        item = {
            'receiverPredecessorGraphId': 1885355834,
            'receiverDirectedGraphId': 9911223344,
            'car': 'UNRESOLVED_PATH_OR_TIME_CONTEXT',
            'motorcycle': 'UNRESOLVED_PATH_OR_TIME_CONTEXT'
        }
        exception['unresolvedOriginalNativeBTransitions'] = [item]
        original['receivingNativeUnresolvedContinuations'] = [item]
        # Even if both data copies are modified, the native status/reason
        # cannot be relabeled as a proven time-independent dead end.
        self.reject()

    def test_rejects_undetected_or_repeated_receiving_branch(self):
        self.catalog['connectionCandidates'][0]['receiverOptions'].pop()
        self.reject()

    def test_rejects_wrong_native_original_source_x(self):
        self.catalog['connectionCandidates'][0]['sourceFinalCoordinate']['lat'] += .001
        self.reject()

    def test_rejects_changed_graph_archive_or_original_evidence_sha(self):
        self.catalog['graphFingerprints']['to'] = 'sha256:' + 'a' * 64
        self.reject()

    def test_rejects_promoted_physical_road_without_real_proof(self):
        self.catalog['connectionCandidates'][0]['receiverOptions'][0]['samePhysicalRoadVerified'] = True
        self.reject()

    def test_rejects_unreviewed_publication_state(self):
        self.catalog['productionPublication'] = 'READY'
        self.reject()

    def test_rejects_falsified_b_original_attribute_evidence(self):
        self.catalog['connectionCandidates'][0]['receiverOptions'][0]['receiverNativeRoadUse'] += 1
        self.reject()

    def test_rejects_b_edge_unrelated_to_native_incoming_approach(self):
        item = self.evidence['sourceToReceiverCandidates'][0]
        item['receiverDirectedCandidatesAtX'] = []
        self.reject()

    def test_rejects_dropped_unresolved_source_or_forged_original_node(self):
        self.catalog['unresolvedSourceFinalEdges'][0]['sourceOriginalNativeEndNodeGraphId'] += 1
        self.reject()

    def test_rejects_self_consistent_catalog_with_missing_native_inventory_source(self):
        # Self-consistent catalog counts are NOT an independently proved census.
        # The original Valhalla bounded native inventory remains authoritative.
        self.catalog['unresolvedSourceFinalEdges'].clear()
        self.catalog['counts']['unresolvedEligibleSourceFinals'] = 0
        self.catalog['counts']['eligibleSourceFinals'] = 1
        self.reject()

    def test_rejects_forged_native_terminal_inventory_or_extra_source(self):
        self.evidence['approvedBoundaryExteriorTerminalInventory'][
            'allPairBoundaryOuterTerminalGraphIds'].append(999999)
        self.reject()

    def test_rejects_corrupted_native_option_mode_category_count(self):
        self.catalog['counts']['branchAttributeEvidenceCounts'].clear()
        self.reject()


if __name__ == '__main__':
    unittest.main()
