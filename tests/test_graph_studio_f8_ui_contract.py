"""Current Graph Studio F8 UI runs approved private D-017 native catalogs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "graph-studio/src/main.ts").read_text()
RUST = (ROOT / "graph-studio/src-tauri/src/lib.rs").read_text()
SCRIPT = (ROOT / "tools/graph_studio_private_catalog_workflow.py").read_text()


class GraphStudioF8UiContractTests(unittest.TestCase):
    def test_owner_private_native_catalog_replaces_obsolete_gps_proposals(self):
        f8 = UI.split('data-tool="f8" hidden>', 1)[1].split('data-tool="route" hidden>', 1)[0]
        for element in ("f8RegionA","f8RegionB","f8RefreshBtn","f8BuildCatalogBtn",
                        "f8PairSummary","f8CancelBtn","f8JobSummary",
                        "f8EvidenceDirectory","f8SampleConnections"):
            self.assertEqual(f8.count(f'id="{element}"'), 1, element)
        for obsolete in ("f8DiscoveryTab","f8ValidationTab","f8DiscoverBtn",
                         "f8ProbeBtn","f8ProbeCount","f8StartLat","f8RecentProofs"):
            self.assertNotIn(f'id="{obsolete}"',f8)
        self.assertIn("Connect regions (A → X → B)",f8)
        self.assertIn("Graph A",f8)
        self.assertIn("Graph B",f8)
        self.assertIn("NOT_VERIFIED",f8)
        self.assertNotIn("Legacy diagnostics",f8)

    def test_native_private_fingerprint_status_generation_and_original_x_map(self):
        for token in ('f8_private_catalog_overview','operation:"private-build"',
                      '"READY_TO_GENERATE_NATIVE_EVIDENCE"',
                      '"READY_TO_VALIDATE_NATIVE_EVIDENCE"',
                      '"GRAPH_STUDIO_PRIVATE_READY"',
                      "notForRoadPilotRuntime",
                      "receiverGraphIds.join",
                      "point.latitude",
                      "point.longitude",
                      "f8SampleConnections.addEventListener",
                      "renderF8Job(await invoke",
                      "f8_cancel_workflow",
                      "f8EvidenceDirectory.value.trim()"):
            self.assertIn(token,UI)
        self.assertIn("f8SampleMarker?.remove()",UI)
        for gone in ("f8DiscoverBtn","f8ValidationPanel","data-f8-point",
                     "best of probed only"):
            self.assertNotIn(gone,UI)

    def test_build_and_f8_start_claim_the_same_atomic_reservation(self):
        # Both entry points must claim the shared lock BEFORE inspecting the
        # competing workflow and setting their own running state.
        for method, competing in (("f8_start_workflow", "build_state.status.lock()"),
                                  ("start_build_queue", "f8_state.status.lock()")):
            body=RUST.split("fn "+method+"(",1)[1].split("\n#[tauri::command]",1)[0]
            reservation=body.index("GRAPH_BUILD_F8_RESERVATION.lock()")
            conflict=body.index(competing)
            claim=body.index("running:true" if method == "f8_start_workflow" else "running: true")
            self.assertLess(reservation,conflict,method)
            self.assertLess(conflict,claim,method)
        self.assertIn("fn both_workflows_cannot_claim_start_together()",RUST)

    def test_changing_active_region_clears_original_x_marker(self):
        body=UI.split("function setActiveRegion(",1)[1].split("\nfunction ",1)[0]
        self.assertIn("f8SampleMarker?.remove()",body)
        invalidated=UI.split("function renderF8BuildSelectors(",1)[1].split("\nfunction ",1)[0]
        self.assertIn("++f8PairGeneration",invalidated)
        self.assertIn("f8SampleMarker?.remove()",invalidated)

    def test_existing_native_reader_and_legacy_backends_remain_readonly(self):
        for name in ('f8_pair_overview','f8_private_catalog_overview',
                     'f8_start_workflow','f8_cancel_workflow','f8_workflow_status',
                     'inspect_region_connector_matrix','inspect_handoff_artifacts',
                     'process_group(0)'):
            self.assertIn(name,RUST)
        for name in ("extract_f8_region_final_edges.py",
                     "audit_f8_physical_road_evidence.py",
                     "preflight_f8_approved_directed_catalog.py",
                     "build_f8_native_auto_catalog.py",
                     "--graph-studio-private-ready",
                     "native_f8_boundary_final_edges",
                     "roadpilot.f8-native-source-11",
                     "notForRoadPilotRuntime"):
            self.assertIn(name,SCRIPT)
        for bad in ("build_frontier_road_inventory.py","refresh_graph_connectivity.py",
                    "--publish","READY_FOR_ROADPILOT"):
            self.assertNotIn(bad,SCRIPT)


if __name__ == "__main__":
    unittest.main()
