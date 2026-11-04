"""Production F8 proof scheduling must advance native directed receiver coverage.

The schedule only selects contiguous ordinals from the existing, complete
native GPS proposal ledger. It cannot create connector candidates, collapse
roads or claim verified handoffs based on a replayed Valhalla route shape.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_native_f8_pair_evidence import source_scans
from discover_native_f8_crossings import generate, sha_file
from probe_native_f8_journey import (
    inspect, ordinal_proposal_page, eligible_manifest,
)
from test_native_f8_pair_evidence import identity, edge, scan, capture


START = {"lat": 46.50, "lng": 13.59}
END = {"lat": 46.59, "lng": 13.85}
MATCHED = "TWO_GRAPH_LOCAL_LEGS_B_EDGE_WALK_REPLAY_MATCHED_ONLY"


class NativeF8OrderedBatchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.pair = identity()
        a, b, _ = source_scans(
            self.pair,
            capture=capture(
                self.pair,
                scan([edge(50, 111, 46.50, 13.59)]),
                scan([
                    edge(201, 777, 46.52, 13.70),
                    edge(202, 777, 46.53, 13.71),
                    edge(203, 777, 46.54, 13.72),
                    edge(204, 999, 46.55, 13.73),
                    edge(205, 999, 46.56, 13.74),
                ]),
            ),
        )
        self.catalog = self.root / "native-gps"
        self.manifest = generate(
            self.pair, a, b, self.catalog, {"source": "ordered-test"}
        )
        self.input = self.catalog / "from-to.jsonl.gz"

    def test_contiguous_batches_cover_all_original_directed_edges_without_way_collapse(self):
        results = [
            ordinal_proposal_page(self.input, start, 2, "from-to", self.pair)
            for start in (0, 2, 4)
        ]
        self.assertEqual([total for _, total in results], [5, 5, 5])
        flattened = [row for page, _ in results for row in page]
        self.assertEqual([row["receiverGraphId"] for row in flattened],
                         [201, 202, 203, 204, 205])
        self.assertEqual(len({r["id"] for r in flattened}), 5)
        self.assertEqual(len({r["receiverWayId"] for r in flattened}), 2)
        # None of these have matching physical peer IDs, yet all are scheduled.
        self.assertTrue(all(not r["physicalPeerOriginGraphIds"] for r in flattened))
        self.assertTrue(all(r["gpsProposalState"] == "UNPROVEN" for r in flattened))

    def test_first_success_never_locks_out_later_better_proof(self):
        calls = []
        def route_fn(config, start, end, mode):
            if str(config) == "A":
                return {"status":"SUCCEEDED", "startActual":start,
                        "endActual":end,"startOffsetMeters":0.0,
                        "endOffsetMeters":0.0, "encodedShape":"A",
                        "durationSeconds":10.0,"distanceKm":1.0}
            i = round(start["lat"]*100)
            calls.append(i)
            durations = {47:100.0, 46:50.0, 45:25.0, 44:15.0}
            return {"status":"SUCCEEDED", "startActual":start,
                    "endActual":end,"startOffsetMeters":0.0,
                    "endOffsetMeters":0.0,"encodedShape":str(i),
                    "durationSeconds":durations.get(i, 5.0),
                    "distanceKm":float(i%10+1)}
        # Return the original B candidate by encoding the GPS latitude.
        direct = {}
        for page_start in (0, 2, 4):
            entries, _ = ordinal_proposal_page(
                self.input, page_start, 2, "from-to", self.pair)
            direct.update({
                str(round(x["coordinate"]["lat"]*100)):
                    x["receiverGraphId"] for x in entries
            })
        all_ids = []
        all_succ = []
        cursors = []
        for page_start in (0, 2, 4):
            result = inspect(
                self.pair, self.manifest, self.catalog,
                Path("A"), Path("B"), START, END, "auto", "from-to",
                2, route_fn,
                lambda cfg, shape, mode, where: direct[shape],
                selection="ordered-native-ledger", start_ordinal=page_start,
            )
            all_ids.extend(x["receiverGraphId"] for x in result["results"])
            all_succ.extend(x for x in result["results"] if x["status"] == MATCHED)
            cursors.append(result["nextOrderedStartOrdinal"])
            self.assertEqual(result["selectionMethod"], "ordered-native-ledger")
            self.assertTrue(result["orderedBatchIsContiguous"])
            self.assertEqual(result["orderedBatchStartOrdinal"], page_start)
            self.assertEqual(result["orderedBatchEndExclusive"],
                             min(page_start + 2, 5))
            self.assertEqual(result["originalSourceCatalogSha256"],
                             self.manifest["files"]["from-to.jsonl.gz"]["sha256"])
            self.assertEqual(result["batchProofScope"],
                             "SELECTED_CANDIDATES_ONLY_NOT_GLOBAL_ROAD_COVERAGE")
            self.assertEqual(result["completeness"],
                             "INCOMPLETE_BOUNDED_JOURNEY_PROBES")
            self.assertEqual(result["physicalLastRetainedRoadEdges"], "NOT_VERIFIED")
            self.assertEqual(result["crossGraphLegalTransfer"], "NOT_VERIFIED")
            self.assertEqual(result["originalRouteEdgeIdentity"], "NOT_VERIFIED")
            self.assertEqual(result["androidF8Parity"], "NOT_VERIFIED")
            self.assertEqual(result["productionConnectivity"], "BLOCKED")
            self.assertTrue(all(x["originalRouteEdgeIdentity"] == "NOT_VERIFIED"
                                for x in result["results"]))
            self.assertTrue(all(
                x["receiverTraceOrigin"]
                == "SEPARATE_TRACE_ATTRIBUTES_EDGE_WALK_REPLAY"
                for x in result["results"]
            ))
        self.assertEqual(all_ids, [201, 202, 203, 204, 205])
        self.assertEqual(len(all_succ), 5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(cursors, [2, 4, None])

    def test_no_cursor_reuse_or_implicit_ranked_sample_start(self):
        for value in (-1, True, 5, 5000, 0.5):
            with self.assertRaises(ValueError):
                ordinal_proposal_page(self.input, value, 2, "from-to", self.pair)
        with self.assertRaisesRegex(ValueError, "requires ordered"):
            inspect(
                self.pair,self.manifest,self.catalog,
                Path("A"),Path("B"),START,END,"auto","from-to",2,
                selection="ranked-sample",start_ordinal=2)
        with self.assertRaisesRegex(ValueError, "Unknown native"):
            inspect(
                self.pair,self.manifest,self.catalog,
                Path("A"),Path("B"),START,END,"auto","from-to",2,
                selection="geometry-matched",start_ordinal=0)
        with self.assertRaises(ValueError):
            ordinal_proposal_page(self.input, 0, 33, "from-to", self.pair)

    def test_corrupt_stream_and_forged_manifest_count_fails_closed(self):
        filepath = self.input
        with gzip.open(filepath, "rt", encoding="utf-8") as src:
            rows = [json.loads(line) for line in src]
        rows[1]["receiverGraphId"] = rows[0]["receiverGraphId"]
        with gzip.open(filepath, "wt", encoding="utf-8") as dst:
            for row in rows:
                dst.write(json.dumps(row) + "\n")
        self.manifest["files"]["from-to.jsonl.gz"]["sha256"] = sha_file(filepath)
        with self.assertRaisesRegex(ValueError,"Duplicate/invalid"):
            inspect(
                self.pair, self.manifest,self.catalog,
                Path("A"),Path("B"),START,END,"auto","from-to",2,
                selection="ordered-native-ledger", start_ordinal=2)
        self.manifest["files"]["from-to.jsonl.gz"]["records"] = 50
        with self.assertRaises(ValueError):
            inspect(
                self.pair, self.manifest,self.catalog,
                Path("A"),Path("B"),START,END,"auto","from-to",2,
                selection="ordered-native-ledger", start_ordinal=0)

    def test_forged_distinct_native_receiver_id_fails_pair_provenance_even_if_rehashed(self):
        with gzip.open(self.input, "rt", encoding="utf-8") as reader:
            rows=[json.loads(line) for line in reader]
        rows[0]["id"]="nf8gps-"+"e"*24
        with gzip.open(self.input, "wt", encoding="utf-8") as stream:
            for item in rows:stream.write(json.dumps(item)+"\n")
        self.manifest["files"]["from-to.jsonl.gz"]["sha256"]=sha_file(self.input)
        with self.assertRaisesRegex(ValueError,"not bound"):
            inspect(
                self.pair,self.manifest,self.catalog,Path("A"),Path("B"),
                START,END,"auto","from-to",2,
                selection="ordered-native-ledger",start_ordinal=2)

    def test_each_direction_has_its_own_original_graph_local_cursor(self):
        fwd, total_fwd = ordinal_proposal_page(
            self.input, 0, 2, "from-to", self.pair)
        rev, total_rev = ordinal_proposal_page(
            self.catalog/"to-from.jsonl.gz", 0, 2, "to-from", self.pair)
        self.assertEqual(total_fwd, 5)
        self.assertEqual(total_rev, 1)
        self.assertNotEqual(fwd[0]["id"], rev[0]["id"])
        self.assertEqual(rev[0]["receiverGraphId"], 50)
        self.assertEqual(
            self.manifest["counts"]["to-from"]["receiverDirectedEdges"], 1)

if __name__ == "__main__":
    unittest.main()
