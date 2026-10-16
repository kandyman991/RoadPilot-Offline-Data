"""Phase 1 safety contract: retain all Graph Studio tools in a responsive shell."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'graph-studio/src/main.ts').read_text()
CSS = (ROOT / 'graph-studio/src/style.css').read_text()
AUDIT = (ROOT / 'docs/GRAPH_STUDIO_UI_AUDIT.md').read_text()


class GraphStudioUiFoundationContractTests(unittest.TestCase):
    def test_responsive_region_map_tools_and_persisted_selection(self):
        for id in ('workspaceSwitcher', 'showRegionsPane', 'showMapPane', 'showToolsPane'):
            self.assertIn(f'id="{id}"', UI)
        for attr in ('aria-label="Workspace panes"', 'aria-pressed="true"',
                     'setCompactPane(', 'applyResponsiveWorkspace(', 'COMPACT_PANE_KEY',
                     'reconcileDesktopPanes()', 'map.resize()'):
            self.assertIn(attr, UI)
        self.assertIn('@media (max-width: 1100px)', CSS)
        self.assertIn('.compact-workspace[data-workspace-pane="tools"] .workspace > .inspector { display: flex; }', CSS)
        self.assertIn('.compact-workspace[data-workspace-pane="regions"] .workspace > .sidebar { display: block; }', CSS)
        self.assertIn('.compact-workspace[data-workspace-pane="map"] .workspace > .map-wrap { display: block; }', CSS)
        self.assertIn('.workspace > .pane-splitter { display: none; }', CSS)
        self.assertNotIn('@media (max-width: 1000px)', CSS)
        self.assertIn('workspace.clientWidth - 420 - 10', UI)

    def test_compact_map_picks_return_to_tool_form(self):
        # Picking GPS in a hidden Map pane is not usable; switch to Map to pick,
        # then return to the form with preserved input after the click.
        for marker in ('pickRouteStartBtn.addEventListener', 'pickRouteEndBtn.addEventListener',
                       'pickHandoffABtn.addEventListener', 'pickHandoffBBtn.addEventListener',
                       'setEditorPinMode(kind:', 'setCompactPane("map")', 'setCompactPane("tools")'):
            self.assertIn(marker, UI)

    def test_console_toggle_keeps_running_status_and_log_accessible(self):
        for piece in ('id="consoleToggle"', 'aria-expanded="false"', 'CONSOLE_COLLAPSED_KEY',
                      'setConsoleCollapsed(', 'consoleCollapsed', 'consoleToggle.addEventListener'):
            self.assertIn(piece, UI)
        for selector in ('.console-collapsed #consoleSplitter', '.console-collapsed .console-log',
                         '.console-collapsed #statusStage', '.app.console-collapsed'):
            self.assertIn(selector, CSS)
        self.assertIn('"Show log" : "Hide log"', UI)

    def test_build_and_route_buttons_require_valid_inputs(self):
        self.assertIn('id="buildBtn" class="btn primary" type="button" disabled', UI)
        self.assertIn('id="buildPrerequisite"', UI)
        self.assertIn('id="routePrerequisite"', UI)
        for text in ('updateBuildButtonState()', 'updateRouteButtonState()',
                     'selected.size > 0 || pendingCatalogSelection.size > 0',
                     'latestBuildRunning', 'buildSubmitting',
                     'coordinatesValid', 'routeSubmitting', 'packageVersionInput.addEventListener'):
            self.assertIn(text, UI)
        self.assertIn('activeRegion && artifacts.some(', UI)
        self.assertIn('class="check-row route-expansion-row"', UI)

    def test_no_critical_tools_or_engine_guards_deleted(self):
        for tool in ('build', 'region', 'graph', 'border', 'f8', 'route', 'visual',
                     'search', 'compare', 'publish', 'toolchain'):
            self.assertIn(f'data-tool="{tool}"', UI)
        for endpoint in ('f8_pair_overview', 'f8_start_workflow', 'f8_cancel_workflow',
                         'start_build_queue', 'plan_route'):
            self.assertIn(endpoint, UI)
        for token in ('NOT VERIFIED', 'BLOCKED', 'UNPROBED'):
            self.assertIn(token, UI)

    def test_full_ux_issue_register_survives_future_chats(self):
        for i in range(1, 14):
            self.assertIn(f'UI-{i:02d}', AUDIT)
        self.assertIn('Phase 1', AUDIT)
        self.assertIn('Phase 4', AUDIT)
        self.assertIn('NOT_VERIFIED', AUDIT)


if __name__ == '__main__':
    unittest.main()
