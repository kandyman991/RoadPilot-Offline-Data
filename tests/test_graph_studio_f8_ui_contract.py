"""GUI/native bridge must expose safe resumable operations, not publish unproven F8."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class GraphStudioF8UiContractTests(unittest.TestCase):
    def test_user_visible_native_f8_tool_and_proof_actions_exist(self):
        js=(ROOT/'graph-studio/src/main.ts').read_text()
        for expected in ('value="f8"','data-tool="f8"',
                         'f8_pair_overview','f8_start_workflow','f8_cancel_workflow',
                         'f8_start_workflow','F8 connectivity','NOT VERIFIED',
                         'data-f8-point','best of probed only'):
            self.assertIn(expected.lower(),js.lower())
        self.assertIn('"discover"',js)
        self.assertIn('"probe"',js)

    def test_native_backend_does_not_publish_runtime_or_reintroduce_osm_correlation(self):
        rust=(ROOT/'graph-studio/src-tauri/src/lib.rs').read_text()
        py=(ROOT/'tools/graph_studio_f8_workspace.py').read_text()
        for name in ('f8_pair_overview','f8_start_workflow','f8_cancel_workflow',
                     'f8_workflow_status','f8_manifests','process_group(0)'):
            self.assertIn(name,rust)
        self.assertIn("'productionPublication':'BLOCKED'",py)
        self.assertIn('pair_identity(pair)',py)
        self.assertIn('verify_retained_graph_identity',py)
        self.assertIn('source_scans(',py)
        self.assertNotIn('build_frontier_road_inventory',py)
        self.assertNotIn('publish_connectivity',py)

if __name__=='__main__':unittest.main()
