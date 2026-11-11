"""Schema-only D-017 future READY wire-format regressions.

Synthetic fixtures do not prove native semantic completeness or authorize READY publication.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas/f8-approved-native-directed-road-connections.schema.json").read_text()
)
HASH = "sha256:" + "a" * 64


def synthetic_approved_fixture() -> dict:
    return {
        "schema": "roadpilot.f8-approved-native-directed-road-connections",
        "version": 1,
        "pairId": "from-region__to-region",
        "fromRegionId": "from-region",
        "toRegionId": "to-region",
        "originalGraphArchives": {"from": HASH, "to": HASH},
        "producerEvidence": {
            "producerCommit": "a" * 40,
            "androidAcceptanceCommit": "b" * 40,
            "sourceInventoryProofSha256": HASH,
            "directedReceiverProofSha256": HASH,
            "androidFullJourneyReportSha256": HASH,
            "normalRoutePreviewReportSha256": HASH,
        },
        "approval": {
            "sourcePhysicalRoadDirectionCompleteness": "VERIFIED",
            "receiverDirectedRoadIdentity": "VERIFIED",
            "genuineBranchesPreserved": True,
            "normalPlannerDeviceAcceptance": "VERIFIED",
            "routePreviewDeviceAcceptance": "VERIFIED",
            "independentReview": "VERIFIED",
            "ownerProductionApproval": "GRANTED",
            "productionPublication": "READY",
        },
        "counts": {
            "eligibleOriginalSourceFinals": 2,
            "approvedSourceConnections": 1,
            "approvedReceiverRoadMatches": 2,
            "explicitlyExcludedSourceFinals": 1,
        },
        "connections": [{
            "sourceFinalDirectedGraphId": 123,
            "exactX": {"lat": 47.25, "lng": 11.4},
            "sourceModes": ["car", "motorcycle"],
            "receiverDirectedRoadsAtX": [
                {
                    "receiverDirectedGraphId": 567,
                    "receiverXPosition": "END_NODE",
                    "travelModes": ["car", "motorcycle"],
                    "nativeXGapMeters": 0.3,
                    "directedApproachOverlapMeters": 20.0,
                },
                {
                    "receiverDirectedGraphId": 568,
                    "receiverXPosition": "INTERIOR",
                    "travelModes": ["motorcycle"],
                    "nativeXGapMeters": 0.2,
                    "directedApproachOverlapMeters": 22.0,
                },
            ],
        }],
        "excludedSourceFinals": [{
            "sourceFinalDirectedGraphId": 124,
            "nativeRejectionProofSha256": HASH,
            "mustNotCreateConnection": True,
        }],
    }


class ApprovedDirectedCatalogContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Draft202012Validator.check_schema(SCHEMA)
        cls.validator = Draft202012Validator(SCHEMA)

    def assert_invalid(self, modified):
        self.assertFalse(self.validator.is_valid(modified))

    def test_synthetic_structure_and_end_node_interior_modes(self):
        sample = synthetic_approved_fixture()
        self.assertTrue(self.validator.is_valid(sample))
        self.assertEqual(2, len(sample["connections"][0]["receiverDirectedRoadsAtX"]))

    def test_pr127_blocked_candidate_is_not_production_contract(self):
        sample = synthetic_approved_fixture()
        sample["schema"] = "roadpilot.f8-final-directed-connection-candidates"
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["approval"]["productionPublication"] = "BLOCKED"
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["approval"]["ownerProductionApproval"] = "PENDING"
        self.assert_invalid(sample)

    def test_missing_device_ui_review_or_native_identity_cannot_claim_ready(self):
        for field, value in [
            ("routePreviewDeviceAcceptance", "NOT_RUN"),
            ("normalPlannerDeviceAcceptance", "NOT_VERIFIED"),
            ("receiverDirectedRoadIdentity", "NOT_VERIFIED"),
            ("sourcePhysicalRoadDirectionCompleteness", "NOT_VERIFIED"),
            ("independentReview", "PENDING"),
        ]:
            sample = synthetic_approved_fixture()
            sample["approval"][field] = value
            self.assert_invalid(sample)

    def test_native_x_graph_ids_modes_and_proof_rejections(self):
        sample = synthetic_approved_fixture()
        sample["connections"][0]["receiverDirectedRoadsAtX"][0]["nativeXGapMeters"] = 5.0
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["connections"][0]["sourceFinalDirectedGraphId"] = -1
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["connections"][0]["receiverDirectedRoadsAtX"][0]["travelModes"] = ["truck"]
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["excludedSourceFinals"][0]["mustNotCreateConnection"] = False
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["unreviewed"] = True
        self.assert_invalid(sample)


    def test_rejects_duplicate_modes_missing_receiver_and_untrusted_proof(self):
        sample = synthetic_approved_fixture()
        sample["connections"][0]["sourceModes"] = ["car", "car"]
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["connections"][0]["receiverDirectedRoadsAtX"] = []
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["producerEvidence"]["normalRoutePreviewReportSha256"] = "unverified"
        self.assert_invalid(sample)
        sample = synthetic_approved_fixture()
        sample["originalGraphArchives"]["from"] = "sha256:" + "g" * 64
        self.assert_invalid(sample)


if __name__ == "__main__":
    unittest.main()
