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

    def test_retired_legacy_osm_ui_does_not_remove_read_only_compatibility(self):
        # Old OSM-way overlay and connector-matrix UI were retired after
        # dependency audit, not the original saved evidence/read-only readers.
        for removed in ('borderLegacyPanel','refreshBorderDiffBtn',
                        'refreshConnectorMatrixBtn','connectorMatrixSummary'):
            self.assertNotIn(f'id="{removed}"',UI)
        for saved in ('borderManualPanel','borderEvidencePanel',
                      'handoffOverrideList','exportBorderDiagnosticsBtn'):
            self.assertIn(f'id="{saved}"',UI)
        for command in ('inspect_handoff_artifacts', 'inspect_region_connector_matrix',
                        'list_handoff_overrides', 'export_border_diagnostics',
                        'f8_pair_overview','f8_private_catalog_overview',
                        'f8_start_workflow','f8_workflow_status','f8_cancel_workflow'):
            self.assertIn(command,RUST)
        self.assertIn('fn transition_artifact_dirs(', RUST)
        self.assertIn('fn collect_json_files(', RUST)


if __name__ == '__main__':
    unittest.main()
