"""UI Phase 3 contract: separate legacy evidence, preserve manual proof and map provenance."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'graph-studio/src/main.ts').read_text()
CSS=(ROOT/'graph-studio/src/style.css').read_text()
AUDIT=(ROOT/'docs/GRAPH_STUDIO_UI_AUDIT.md').read_text()

class Phase3BorderAndMapControlsContract(unittest.TestCase):
    def test_border_manual_saved_and_legacy_workflows_preserved(self):
        border=UI.split('data-tool="border" hidden>',1)[1].split('data-tool="f8" hidden>',1)[0]
        for name in ('Manual','Evidence','Legacy'):
            self.assertIn(f'id="border{name}Tab"',border)
            self.assertIn(f'id="border{name}Panel"',border)
        self.assertIn('role="tablist"',border)
        self.assertIn('role="tabpanel"',border)
        manual=border.split('id="borderManualPanel"',1)[1].split('id="borderEvidencePanel"',1)[0]
        evidence=border.split('id="borderEvidencePanel"',1)[1].split('id="borderLegacyPanel"',1)[0]
        legacy=border.split('id="borderLegacyPanel"',1)[1]
        for id in ('loadBorderPairBtn','pickHandoffABtn','pickHandoffBBtn',
                   'handoffASummary','handoffBSummary','validateHandoffBtn',
                   'saveHandoffBtn','clearHandoffBtn','handoffProbeList'):
            self.assertIn(f'id="{id}"',manual)
            self.assertEqual(border.count(f'id="{id}"'),1)
        for id in ('refreshHandoffArtifactsBtn','handoffArtifactList',
                   'handoffOverrideList','exportBorderDiagnosticsBtn'):
            self.assertIn(f'id="{id}"',evidence)
        for id in ('refreshBorderDiffBtn','borderDiffSummary','connectorRegion','connectorMode',
                   'refreshConnectorMatrixBtn','connectorMatrixList'):
            self.assertIn(f'id="{id}"',legacy)
        self.assertIn('not native F8 proof',legacy)
        self.assertIn('BORDER_TAB_KEY',UI)
        self.assertIn('editingHandoffId = item.id;\n        activateBorderTab("manual");',UI)

        for token in ('event.key === "ArrowRight"','event.key === "ArrowLeft"',
                      'activateBorderTab(', 'borderPanels.legacy.hidden'):
            self.assertIn(token,UI)
        self.assertIn('.border-subpanel[hidden]',CSS)
        self.assertIn('Legacy diagnostics — not native F8 proof',UI)

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

    def test_clear_only_visual_provenance_not_user_data_or_native_f8(self):
        start=UI.index('function clearTransientMapOverlays(): void {')
        end=UI.index('clearToolOverlaysBtn.addEventListener(',start)
        body=UI[start:end]
        for token in ('removeBuildDiffOverlay()','removeVisualComparison()',
                      'removeConnectorMatrixOverlay()','removeBorderPairLayers()',
                      'removeRouteLayers()','removeLocateEdgeOverlay()'):
            self.assertIn(token,body)
        for forbidden in ('deleteManualOverride','delete_manual_override','unlink(',
                          'removeRegionConfig(', 'clearHandoffSelection(',
                          'removeVisualBuildLayer(', 'clearEditorPinMarkers(',
                          'localStorage.clear(', 'clearSearchOverlay()'):
            self.assertNotIn(forbidden,body)
        self.assertIn('visualComparisonGeneration += 1',UI)
        self.assertIn('buildComparisonGeneration += 1',body)
        self.assertIn('generation !== visualComparisonGeneration',UI)
        self.assertIn('if (borderPanels.legacy.hidden || !map.getSource',UI)

    def test_issue_register_and_architecture_guards_remain(self):
        for i in range(1,14):self.assertIn(f'UI-{i:02d}',AUDIT)
        for marker in ('NOT_VERIFIED','BLOCKED'):
            self.assertIn(marker,AUDIT)
        for endpoint in ('f8_pair_overview','f8_start_workflow','f8_cancel_workflow',
                         'snap_handoff_point','validate_handoff','save_handoff_override',
                         'inspect_handoff_artifacts','inspect_region_connector_matrix',
                         'export_border_diagnostics'):
            self.assertIn(endpoint,UI)
        self.assertIn('Native F8 connectivity',UI)
        self.assertIn('NOT VERIFIED',UI)
        self.assertIn('UNPROBED',UI)

if __name__=='__main__':unittest.main()
