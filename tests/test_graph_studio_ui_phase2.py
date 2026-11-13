"""Phase 2: every original operation remains reachable without menu duplication."""
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT/'graph-studio/src/main.ts').read_text()
CSS = (ROOT/'graph-studio/src/style.css').read_text()
AUDIT = (ROOT/'docs/GRAPH_STUDIO_UI_AUDIT.md').read_text()

class Phase2UiContract(unittest.TestCase):
    def test_five_core_workflows_with_advanced_and_preserved_tools(self):
        main_menu = UI.split('<select id="toolMenu"',1)[1].split('</select>',1)[0]
        core = ('build','f8','route','data','publish')
        for tool in core:
            self.assertEqual(len(re.findall(f'<option value="{tool}">',main_menu)),1,tool)
        self.assertEqual(len(re.findall('<option value="advanced">',main_menu)),1)
        for legacy in ('graph','border','compare','visual','search','region','toolchain'):
            self.assertNotIn(f'<option value="{legacy}">',main_menu)

        advanced_menu=UI.split('<select id="advancedToolMenu"',1)[1].split('</select>',1)[0]
        for tool in ('graph','border','compare'):
            self.assertEqual(advanced_menu.count(f'<option value="{tool}">'),1)
        for tool in ('build','region','graph','border','f8','route','visual','search',
                     'compare','publish','toolchain'):
            self.assertIn(f'data-tool="{tool}"',UI)

        # Search and visual are one everyday Data workspace, not two separate
        # top-level tools. The real underlying panels and handlers still exist.
        for element in ('dataWorkspaceTabs','dataVisualTab','dataSearchTab',
                        'advancedToolSelector','advancedToolMenu'):
            self.assertEqual(UI.count(f'id="{element}"'),1)
        self.assertIn('aria-label="Map and Search data tools"',UI)
        self.assertIn('aria-label="Advanced Graph Studio tools"',UI)
        for token in ('toolMenu.value === "data"',
                      'toolMenu.value === "advanced"',
                      'dataWorkspaceTabs.hidden = contextual || !dataGroup',
                      'advancedToolSelector.hidden = contextual || !advancedGroup',
                      'dataVisualTab.addEventListener("click", () => activateTool("visual"))',
                      'dataSearchTab.addEventListener("click", () => activateTool("search"))',
                      'if (advancedGroup) advancedToolMenu.value = displayedTool',
                      'if (isPrimaryTool(storedTool))'):
            self.assertIn(token,UI)
        self.assertIn('.workflow-subnav[hidden]',CSS)
        self.assertIn('.advanced-tool-selector[hidden]',CSS)
        self.assertIn('GRAPH_STUDIO_PRIVATE_READY',UI)
        self.assertNotIn('production connectivity is paused until the native F8 pipeline is verified',UI)
        # Header telemetry is available on demand in Toolchain, not across
        # the entire primary workspace at narrow desktop widths.
        header=UI.split('<header class="topbar">',1)[1].split('</header>',1)[0]
        toolchain=UI.split('id="toolchainDetailsPanel"',1)[1].split('</section>',1)[0]
        for key in ('metricCpu','metricRam','metricDisk','metricTemp'):
            self.assertNotIn(f'id="{key}"',header)
            self.assertEqual(UI.count(f'id="{key}"'),1)
            self.assertIn(f'id="{key}"',toolchain)
        self.assertIn('Advanced build options and details',UI)
        self.assertIn('Create / import a regional Search pack',UI)

    def test_comparisons_are_three_genuine_tabs_in_one_panel(self):
        compare=UI.split('data-tool="compare" hidden>',1)[1].split('</section>',1)[0]
        for title in ('Routing','Visual','Search'):
            self.assertIn(f'id="compare{title}Tab"',compare)
            self.assertIn(f'id="compare{title}Panel"',compare)
        self.assertIn('role="tablist"',compare)
        self.assertIn('role="tabpanel"',compare)
        for fid in ('compareA','compareB','comparison','visualCompareA','visualCompareB',
                    'compareVisualBuildsBtn','visualComparisonSummary',
                    'searchCompareA','searchCompareB','compareSearchBtn','searchCompareSummary'):
            self.assertEqual(UI.count(f'id="{fid}"'),1,fid)
            self.assertIn(f'id="{fid}"',compare)
        search=UI.split('data-tool="search" hidden>',1)[1].split('data-tool="visual" hidden>',1)[0]
        visual=UI.split('data-tool="visual" hidden>',1)[1].split('data-tool="graph" hidden>',1)[0]
        self.assertNotIn('id="searchCompareA"',search)
        self.assertNotIn('id="visualCompareA"',visual)
        for token in ('COMPARISON_TAB_KEY','activateComparisonTab(', 'ArrowLeft', 'ArrowRight',
                      'aria-selected', 'event.key === "Home"', 'event.key === "End"'):
            self.assertIn(token,UI)
        self.assertIn('.comparison-subpanel[hidden]',CSS)

    def test_contextual_editing_and_toolchain_not_deleted(self):
        for fid in ('contextToolNotice','contextBackBtn','contextToolTitle','toolchainBadge','openToolchainBtn',
                    'newRegionBtn','editRegionBtn','closeRegionEditorBtn','regionEditorSection','toolchainDetailsPanel','tools'):
            self.assertIn(f'id="{fid}"',UI)
        self.assertIn('contextToolNotice.hidden = !contextual',UI)
        self.assertIn('aria-controls="toolchainDetailsPanel"',UI)
        self.assertIn('openToolchainBtn.setAttribute("aria-expanded"',UI)
        self.assertIn('toolchainBadge.addEventListener("click", toggleToolchainDetails)',UI)
        self.assertIn('openToolchainBtn.addEventListener("click", toggleToolchainDetails)',UI)
        self.assertIn('if (isPrimaryTool(storedTool))',UI)
        self.assertIn('if (remember && !contextual) localStorage.setItem',UI)
        for native in ('f8_pair_overview','f8_start_workflow','f8_cancel_workflow','list_search_builds',
                       'compare_search_builds','compare_build_indexes','toolchain_status', 'load_region_config'):
            self.assertIn(native,UI)

    def test_no_lost_audit_entries_or_f8_safety(self):
        for index in range(1,14):self.assertIn(f'UI-{index:02d}',AUDIT)
        self.assertIn('NOT_VERIFIED',AUDIT)
        self.assertIn('BLOCKED',AUDIT)
        for token in ('NOT VERIFIED','BLOCKED','UNPROBED'):
            self.assertIn(token,UI)

if __name__ == '__main__': unittest.main()
