"""Independent graph-local physical identity audit regression with original native sample."""
import copy
import json
import unittest
from pathlib import Path

from tools.audit_f8_physical_road_evidence import audit

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

    def test_rejects_corrupted_native_option_mode_category_count(self):
        self.catalog['counts']['branchAttributeEvidenceCounts'].clear()
        self.reject()


if __name__ == '__main__':
    unittest.main()
