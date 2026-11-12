"""UI issue #89 Phase 4: legacy inspection remains available but nonproductive."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUST = (ROOT / 'graph-studio/src-tauri/src/lib.rs').read_text()
UI = (ROOT / 'graph-studio/src/main.ts').read_text()


class LegacyReadOnlyInspectionContract(unittest.TestCase):
    def test_history_lookup_does_not_create_old_producer_directories(self):
        start = RUST.index('fn transition_artifact_search_paths(')
        end = RUST.index('fn collect_json_files(', start)
        search = RUST[start:end]
        for location in (
            'transitions', 'imports/handoffs', 'connectivity',
            'imports/connectivity', 'connector-matrices', 'imports/connector-matrices',
        ):
            self.assertIn(f'"{location}"', search)
        self.assertNotIn('fs::create_dir_all', search)
        self.assertIn('transition_artifact_search_paths(&workspace_root(app)?)', search)
        self.assertIn('empty_legacy_search_does_not_create_missing_folders', RUST)
        self.assertIn('legacy_search_preserves_existing_paths_without_modifying_them', RUST)

    def test_legacy_is_opt_in_and_not_native_f8_routing(self):
        self.assertIn('Legacy diagnostics — not native F8 proof', UI)
        self.assertIn('borderPanels.legacy.hidden', UI)
        for command in ('inspect_handoff_artifacts', 'inspect_region_connector_matrix',
                        'list_handoff_overrides', 'export_border_diagnostics'):
            self.assertIn(command, UI)
        for command in ('f8_pair_overview', 'f8_start_workflow',
                        'f8_workflow_status', 'f8_cancel_workflow'):
            self.assertIn(command, RUST)
        self.assertIn('fn transition_artifact_dirs(', RUST)
        self.assertIn('fn collect_json_files(', RUST)


if __name__ == '__main__':
    unittest.main()
