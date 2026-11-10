"""Independent graph-local physical identity audit regression with original native sample."""
import copy
import json
import unittest
from pathlib import Path

from tools.audit_f8_physical_road_evidence import (
    audit, build_test_only_original_handoffs, atomic_write_new_json)

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
