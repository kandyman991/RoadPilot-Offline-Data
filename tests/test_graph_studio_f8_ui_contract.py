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

    def test_discovery_validation_tabs_keep_shared_pair_and_job_state(self):
        source=(ROOT/'graph-studio/src/main.ts').read_text()
        f8=source.split('<section class="section tool-panel" data-tool="f8" hidden>',1)[1].split('<section class="section tool-panel" data-tool="route" hidden>',1)[0]
        discovery=f8.split('id="f8DiscoveryPanel"',1)[1].split('id="f8ValidationPanel"',1)[0]
        validation=f8.split('id="f8ValidationPanel"',1)[1]
        shared=f8.split('id="f8DiscoveryPanel"',1)[0]
        for component in ('f8RegionA','f8RegionB','f8JobSummary','f8CancelBtn','f8DiscoveryTab','f8ValidationTab'):
            self.assertIn('id="'+component+'"',shared)
        for component in ('f8RefreshBtn','f8DiscoverBtn','f8PairSummary'):
            self.assertIn('id="'+component+'"',discovery)
            self.assertNotIn('id="'+component+'"',validation)
        for component in ('f8Direction','f8Mode','f8StartLat','f8StartLng','f8EndLat',
                          'f8EndLng','f8ProbeCount','f8ProbeBtn','f8RecentProofs','f8CopyRouteBtn'):
            self.assertIn('id="'+component+'"',validation)
            self.assertNotIn('id="'+component+'"',discovery)
        for text in ('role="tablist"','role="tab"','role="tabpanel"','aria-controls="f8DiscoveryPanel"',
                     'aria-controls="f8ValidationPanel"','aria-selected="false"',
                     'aria-live="polite"','id="f8ValidationReadiness"'):
            self.assertIn(text,f8)
        for logic in ('activateF8Tab(', 'F8_TAB_STORAGE_KEY', 'ArrowRight', 'ArrowLeft',
                      'event.key === "Home"', 'event.key === "End"',
                      'f8DiscoveryPanel.hidden', 'f8ValidationPanel.hidden',
                      'updateF8ValidationReadiness()', 'f8RecentProofs.replaceChildren()'):
            self.assertIn(logic,source)
        stylesheet=(ROOT/'graph-studio/src/style.css').read_text()
        for style in ('.f8-tabs', '.f8-tab:focus-visible', '.f8-subpanel[hidden]', '.f8-job-bar'):
            self.assertIn(style,stylesheet)

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
