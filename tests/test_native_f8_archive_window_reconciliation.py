"""Original full-archive vs common-overlap-window cut ledger audit."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from reconcile_native_f8_archive_window_coverage import reconcile

SHA = "sha256:" + "a"*64
GRAPH = {"from":SHA,"to":"sha256:"+"b"*64}
FILES = {"pair":SHA,"from-manifest":SHA,"to-manifest":SHA,
         "from-buffer":SHA,"to-buffer":SHA}


def reports():
    side_full = {
        "archiveTileCount":1,
        "allOriginalDirectedEdgesEnumerated":3,
        "originalArchiveTiles":[{
            "tileGraphId":802,"originalDirectedCount":3}],
        "originalGeometryBoundaryEnvelopeCandidates":3,
        "originalDirectedCutShapeCount":2,
        "allOriginalDirectedCutObservations":[
            {"originalDirectedGraphId":802},
            {"originalDirectedGraphId":802+(1<<25)}],
        "unresolvedOriginalNativeZeroLengthGeometryCount":1,
        "unresolvedOriginalNativeZeroLengthGeometries":[
            {"originalDirectedGraphId":802+(2<<25)}],
        "noSourceDirectedRoadSuppressedByNameWayOrMode":True,
        "physicalRoadDirectionFinalEdge":"NOT_VERIFIED",
        "crossGraphMatching":"NOT_STARTED",
    }
    side_old = {
        "originalSourceDirectedCutShapeCount":1,
        "allOriginalDirectedCutObservations":[
            {"originalDirectedGraphId":802}],
    }
    side_prior = {
        "beyondCutPredecessorsMissingFromWindowScan":[802+(1<<25)],
    }
    archive={
        "schema":"roadpilot.f8-all-original-source-archive-tile-cut-census",
        "version":1,"pairId":"it-at",
        "productionPublication":"BLOCKED",
        "originalGraphArchiveTileInventory":"ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED",
        "sourceGraphFingerprints":dict(GRAPH),
        "immutableOriginalSourceSHA256":dict(FILES),
        "directions":{side:copy.deepcopy(side_full) for side in ("from-to","to-from")},
    }
    window={
        "schema":"roadpilot.f8-original-all-source-native-directed-cut-census",
        "pairId":"it-at","productionPublication":"BLOCKED",
        "sourceGraphFingerprints":dict(GRAPH),
        "originalSourceInputSHA256":dict(FILES),
        "directions":{side:copy.deepcopy(side_old) for side in ("from-to","to-from")},
    }
    previous={
        "schema":"roadpilot.f8-source-cut-window-coverage-reconciliation",
        "pairId":"it-at","productionPublication":"BLOCKED",
        "originalGraphFingerprints":dict(GRAPH),
        "directions":{side:copy.deepcopy(side_prior) for side in ("from-to","to-from")},
    }
    return archive,window,previous


class OriginalArchiveWindowReconciliationTests(unittest.TestCase):
    def test_actual_full_source_graphid_ranges_preserved_and_missing_recovered(self):
        result=reconcile(*reports())
        self.assertEqual(result["productionPublication"],"BLOCKED")
        self.assertEqual(result["receivingGraphCorrelation"],"NOT_STARTED")
        for side in ("from-to","to-from"):
            d=result["directions"][side]
            self.assertEqual(d["allOriginalArchiveDirectedEdgeIndicesEnumerated"],3)
            self.assertEqual(d["newCutDirectedGraphIdsNotInWindowCount"],1)
            self.assertEqual(d["originalPreviouslyAbsentCutPredecessorsRecoveredCount"],1)
            self.assertEqual(d["unresolvedZeroLengthOriginalNativeGraphIdCount"],1)
            self.assertEqual(d["physicalRoadDirectionToOneFinalOriginalGraphId"],"NOT_VERIFIED")

    def test_never_merge_equal_ids_across_independent_source_graphs(self):
        d=reconcile(*reports())["directions"]
        self.assertEqual(d["from-to"]["newCutDirectedGraphIdsNotInWindow"],
                         d["to-from"]["newCutDirectedGraphIdsNotInWindow"])
        self.assertNotIn("globallyDeduplicatedGraphIds",d)

    def test_previous_source_cut_disappearance_is_hard_error(self):
        source=reports()
        source[0]["directions"]["from-to"]["allOriginalDirectedCutObservations"][0][
            "originalDirectedGraphId"]=900
        with self.assertRaisesRegex(ValueError,"window cut GraphIds absent"):
            reconcile(*source)

    def test_old_native_missing_predecessor_remains_missing_fails(self):
        source=reports()
        source[2]["directions"]["from-to"]["beyondCutPredecessorsMissingFromWindowScan"]=[
            333 << 25 | 802]
        with self.assertRaisesRegex(ValueError,"still missing"):
            reconcile(*source)

    def test_mutated_original_graph_or_buffer_identity_is_hard_error(self):
        source=reports()
        source[0]["sourceGraphFingerprints"]["from"]="sha256:"+"c"*64
        with self.assertRaisesRegex(ValueError,"fingerprints mismatch"):
            reconcile(*source)
        source=reports()
        source[0]["immutableOriginalSourceSHA256"]["from-buffer"]="sha256:"+"c"*64
        with self.assertRaisesRegex(ValueError,"provenance mismatch"):
            reconcile(*source)

    def test_missing_original_archive_tiles_rejected(self):
        source=reports()
        source[0]["directions"]["to-from"]["archiveTileCount"]=2
        with self.assertRaisesRegex(ValueError,"tile ledger incomplete"):
            reconcile(*source)

    def test_native_geometry_without_spatial_cut_is_unresolved_not_suppressed(self):
        source=reports()
        source[0]["directions"]["from-to"]["unresolvedOriginalNativeZeroLengthGeometries"][0][
            "originalDirectedGraphId"]=802
        with self.assertRaisesRegex(ValueError,"incorrectly claimed"):
            reconcile(*source)

    def test_source_only_publication_gate_never_succeeds(self):
        source=reports()
        source[0]["productionPublication"]="READY"
        with self.assertRaisesRegex(ValueError,"publishable"):
            reconcile(*source)


if __name__=="__main__":
    unittest.main()
