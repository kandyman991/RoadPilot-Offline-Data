"""Phase 2: every original operation remains reachable without menu duplication."""
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT/'graph-studio/src/main.ts').read_text()
CSS = (ROOT/'graph-studio/src/style.css').read_text()
AUDIT = (ROOT/'docs/GRAPH_STUDIO_UI_AUDIT.md').read_text()

class Phase2UiContract(unittest.TestCase):
    def test_all_primary_tools_grouped_and_context_tools_removed_from_dropdown(self):
        menu = UI.split('<select id="toolMenu"',1)[1].split('</select>',1)[0]
        for group in ('Build','Inspect','Test','Data','Publish','Advanced'):
            self.assertIn(f'<optgroup label="{group}">',menu)
        for tool in ('build','graph','border','f8','route','visual','search','compare','publish'):
            self.assertEqual(len(re.findall(f'<option value="{tool}">',menu)),1,tool)
        self.assertNotIn('<option value="region">',menu)
        self.assertNotIn('<option value="toolchain">',menu)
        for tool in ('build','region','graph','border','f8','route','visual','search','compare','publish','toolchain'):
            self.assertIn(f'data-tool="{tool}"',UI)

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
