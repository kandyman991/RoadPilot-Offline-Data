"""Native graph-local receiver continuation audit: never promote spatial peers to route proof."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_native_f8_receiver_topology import audit_direction, incoming_near, make_receiver_index


def road(graph_id: int, way_id: int = 100):
    return {"graphId": graph_id, "wayId": way_id,
            "forwardAccess": 2031, "reverseAccess": 2031}


def endpoint(graph_id: int, lat: float, lon: float,
             *, deadend: bool = True, node_id: int | None = None):
    return {"sourceGraphId": graph_id,
            "endLat": lat, "endLon": lon,
            "endNodeGraphId": node_id or (graph_id + 5000),
            "deadend": deadend, "notThru": False,
            "forward": True, "wayId": 100,
            "forwardAccess": 2031, "reverseAccess": 2031}


class ReceiverDirectedTopologyAuditTests(unittest.TestCase):
    def test_two_distinct_source_termini_same_way_are_not_collapsed(self):
        a = [road(1), road(2)]
        ae = [endpoint(1, 46.5, 13.7), endpoint(2, 46.5001, 13.7001)]
        b = [road(11), road(22)]
        be = [endpoint(11, 46.5, 13.7, deadend=False),
              endpoint(22, 46.5001, 13.7001, deadend=False)]
        report = audit_direction(a, ae, b, be, include_observations=True)
        stats = report["classification"]
        self.assertEqual(stats["sourceNativeDeadends"], 2)
        self.assertEqual(stats["sourceWithProvisionalReceiverContinuation"], 2)
        obs = report["observations"]
        self.assertEqual([x["sourceDirectedGraphId"] for x in obs], [1, 2])
        self.assertEqual([x["nearbyReceiverIncoming"][0]["receiverDirectedGraphId"] for x in obs],
                         [11, 22])
        self.assertEqual(report["coverageClaim"], "NOT_VERIFIED")
        self.assertEqual(report["receiverContinuation"], "PROVISIONAL_NOT_VALHALLA_PROVEN")

    def test_receiver_deadend_is_unresolved_not_handoff(self):
        report = audit_direction([road(1)], [endpoint(1, 46.5, 13.7)],
                                 [road(11)], [endpoint(11, 46.5, 13.7)],
                                 include_observations=True)
        self.assertEqual(report["classification"]["sourceWithOnlyDeadEndReceiverIncoming"], 1)
        self.assertEqual(report["observations"][0]["status"], "UNRESOLVED_RECEIVER_ALSO_DEADEND")

    def test_other_osm_way_remains_reported_for_future_native_evidence(self):
        report = audit_direction([road(1)], [endpoint(1, 46.5, 13.7)],
                                 [road(11, 777)], [endpoint(11, 46.5, 13.7, deadend=False)],
                                 include_observations=True)
        self.assertEqual(report["classification"]["sourceWithOnlyDifferentWayReceiverIncoming"], 1)
        self.assertEqual(report["observations"][0]["nearbyReceiverIncoming"][0]["receiverWayId"], 777)

    def test_nearby_receiver_has_distinct_incoming_ids_and_no_budget_limit(self):
        b = [road(k) for k in range(11, 35)]
        be = [endpoint(k, 46.5, 13.7, deadend=False) for k in range(11, 35)]
        report = audit_direction([road(1)], [endpoint(1, 46.5, 13.7)],
                                 b, be, include_observations=True)
        self.assertEqual(report["classification"]["continuingSameWayIncomingOccurrences"], 24)
        self.assertEqual(report["classification"]["sourceWithAmbiguousMultipleContinuations"], 1)
        self.assertEqual(len(report["observations"][0]["nearbyReceiverIncoming"]), 24)

    def test_missing_receiver_or_source_endpoint_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            audit_direction([road(1)], [], [road(11)], [endpoint(11, 46.5, 13.7)])
        with self.assertRaisesRegex(ValueError, "mismatch"):
            audit_direction([road(1)], [endpoint(2, 46.5, 13.7)],
                            [road(11)], [endpoint(11, 46.5, 13.7)])
        with self.assertRaisesRegex(ValueError, "duplicated"):
            audit_direction([road(1)], [endpoint(1, 46.5, 13.7)],
                            [road(11), road(11)], [endpoint(11, 46.5, 13.7)])

    def test_distance_threshold_is_observation_not_f8_eligibility(self):
        receiver = {11: endpoint(11, 46.5, 13.7), 12: endpoint(12, 46.50012, 13.70012)}
        nearby = incoming_near(make_receiver_index(receiver), 46.5, 13.7)
        self.assertEqual([row[1] for row in nearby], [11])
        report = audit_direction([road(1)], [endpoint(1, 46.8, 14.1)],
                                 [road(11)], [endpoint(11, 46.5, 13.7)],
                                 include_observations=True)
        self.assertEqual(report["classification"]["sourceWithNoNearbyReceiverIncoming"], 1)
        self.assertEqual(report["observations"][0]["status"], "UNRESOLVED_NO_NEARBY_RECEIVER_INCOMING")


if __name__ == "__main__":
    unittest.main()
