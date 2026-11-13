"""Phase 3 after owner-approved retirement: manual proof preserved, old OSM UI gone."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'graph-studio/src/main.ts').read_text()
CSS=(ROOT/'graph-studio/src/style.css').read_text()
RUST=(ROOT/'graph-studio/src-tauri/src/lib.rs').read_text()
AUDIT=(ROOT/'docs/GRAPH_STUDIO_UI_AUDIT.md').read_text()


class Phase3BorderAndMapControlsContract(unittest.TestCase):
    def test_saved_manual_evidence_survives_old_osm_and_matrix_ui_retirement(self):
        border=UI.split('data-tool="border" hidden>',1)[1].split('data-tool="f8" hidden>',1)[0]
        self.assertIn('role="tablist"',border)
        for name in ('Manual','Evidence'):
            for tag in ('Tab','Panel'):
                self.assertIn(f'id="border{name}{tag}"',border)
        manual=border.split('id="borderManualPanel"',1)[1].split('id="borderEvidencePanel"',1)[0]
        evidence=border.split('id="borderEvidencePanel"',1)[1]
        for element in ('loadBorderPairBtn','pickHandoffABtn','pickHandoffBBtn',
                        'handoffASummary','handoffBSummary','validateHandoffBtn',
                        'saveHandoffBtn','clearHandoffBtn','handoffProbeList'):
            self.assertIn(f'id="{element}"',manual)
        for element in ('refreshHandoffArtifactsBtn','handoffArtifactList',
                        'handoffOverrideList','exportBorderDiagnosticsBtn'):
            self.assertIn(f'id="{element}"',evidence)
        for gone in ('borderLegacyTab','borderLegacyPanel','refreshBorderDiffBtn',
                     'borderDiffSummary','connectorRegion','connectorMode',
                     'refreshConnectorMatrixBtn','connectorMatrixList'):
            self.assertNotIn(f'id="{gone}"',UI)
        self.assertIn('BORDER_TAB_KEY',UI)
        self.assertIn('activateBorderTab("manual")',UI)
        self.assertIn('["manual", "evidence"]',UI)
        self.assertIn('.border-subpanel[hidden]',CSS)
        # Read-only old JSON/connector readers remain callable by external clients.
        for endpoint in ('inspect_region_connector_matrix','inspect_handoff_artifacts',
                         'export_border_diagnostics','list_handoff_overrides'):
            self.assertIn(endpoint,RUST)

    def test_map_presets_and_custom_switches_preserve_individual_layers(self):
        for val in ('map','routing','borders','all','custom'):
            self.assertIn(f'<option value="{val}"',UI)
        self.assertIn('data-layer-toggle="graphEdges"',UI)
        self.assertIn('MAP_LAYER_KEY',UI)
        self.assertIn('MAP_PRESET_KEY',UI)
        self.assertIn('persistLayerSelection()',UI)
        self.assertIn('initializeMapLayerPreset()',UI)
        self.assertIn('"custom"',UI)
        self.assertIn('localStorage.setItem(MAP_LAYER_KEY, JSON.stringify(saved))',UI)
        self.assertIn('mapLayerPreset.addEventListener("change"',UI)
        self.assertIn('layerKeys.every(key => typeof',UI)
        self.assertIn('Detailed map layers (advanced)',UI)

    def test_clear_only_renders_not_user_data_or_native_proof(self):
        start=UI.index('function clearTransientMapOverlays(): void {')
        end=UI.index('clearToolOverlaysBtn.addEventListener(',start)
        body=UI[start:end]
        for token in ('removeBuildDiffOverlay()','removeVisualComparison()',
                      'removeBorderPairLayers()','removeRouteLayers()',
                      'removeLocateEdgeOverlay()'):
            self.assertIn(token,body)
        for forbidden in ('deleteManualOverride','delete_manual_override','unlink(',
                          'removeRegionConfig(','clearHandoffSelection(',
                          'removeVisualBuildLayer(','clearEditorPinMarkers(',
                          'localStorage.clear(','clearSearchOverlay(',
                          'removeConnectorMatrixOverlay()'):
            self.assertNotIn(forbidden,body)
        self.assertIn('visualComparisonGeneration += 1',UI)
        self.assertIn('buildComparisonGeneration += 1',body)
        self.assertIn('generation !== visualComparisonGeneration',UI)

    def test_issue_register_guards_and_stable_backend_legacy_api(self):
        for i in range(1,14):
            self.assertIn(f'UI-{i:02d}',AUDIT)
        for marker in ('NOT_VERIFIED','BLOCKED'):
            self.assertIn(marker,AUDIT)
        for endpoint in ('f8_private_catalog_overview','f8_start_workflow',
                         'f8_cancel_workflow'):
            self.assertIn(endpoint,UI)
        for endpoint in ('snap_handoff_point','validate_handoff','save_handoff_override',
                         'inspect_handoff_artifacts','inspect_region_connector_matrix',
                         'export_border_diagnostics'):
            self.assertIn(endpoint,RUST)
        self.assertIn('GRAPH_STUDIO_PRIVATE_READY',UI)


if __name__=='__main__':
    unittest.main()
