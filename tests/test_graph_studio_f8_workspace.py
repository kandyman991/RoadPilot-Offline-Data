"""Native F8 GUI command engine: immutable pair binding and no false publication."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from graph_studio_f8_workspace import run,pair_workspace,retained_sources
from build_connectivity_pair_manifest import build_pair
from test_native_f8_pair_evidence import identity,edge,scan,A,B,C,D

class StudioF8EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.a=self.root/'builds'/'italy'/'italy-routing-v1-manifest.json'
        self.b=self.root/'builds'/'austria'/'austria-routing-v2-manifest.json'
        for path,region,version,graph,source,neighbor,boundary in (
            (self.a,'italy','v1',A,'italy/nord-est','austria',C),
            (self.b,'austria','v2',B,'austria','italy/nord-est',D)):
            path.parent.mkdir(parents=True,exist_ok=True)
            index=path.parent/'graph-index.json'
            index.write_text(json.dumps({'schema':'roadpilot-graph-index','schemaVersion':1,
                'boundaries':[{'sourceId':neighbor,'fingerprint':boundary}]}))
            path.write_text(json.dumps({'schema':'roadpilot-routing-pack','schemaVersion':1,
                'regionId':region,'packageVersion':version,'graphFingerprint':graph,
                'source':{'primaryGeofabrikId':source},
                'graphIndex':{'fileName':'graph-index.json'}}))
        self.args=['--workspace',str(self.root),'--from-manifest',str(self.a),
                   '--to-manifest',str(self.b)]
        self.pair=build_pair(self.a,self.b)

    def test_status_from_exact_built_pair_is_safe_and_requires_real_source(self):
        result=run(['status',*self.args])
        self.assertEqual(result['pairId'],'italy__austria')
        self.assertEqual(result['productionPublication'],'BLOCKED')
        self.assertEqual(result['androidParity'],'NOT_VERIFIED')
        self.assertFalse(result['proposalsReady'])
        self.assertIn('FRESH_NATIVE_SCAN_REQUIRED',result['source'])

    def test_reuses_valid_matching_scan_and_preserves_all_unmatched_proposals(self):
        diag=self.root/'diagnostics'/'retained';diag.mkdir(parents=True)
        first=scan([edge(1,110,47.0,12)])
        second=scan([edge(2,110,47.0,12),edge(3,111,47.1,12)])
        (diag/'italy-native-full.json').write_text(json.dumps(first))
        (diag/'austria-native-full.json').write_text(json.dumps(second))
        summary={'schema':'roadpilot.native-valhalla-overlap-diagnostics','pairId':self.pair['pairId'],
                 'f8GraphEdgeParity':'NOT_VERIFIED','nativeAndroidF8ReferenceCaptured':False,
                 'version':'3.6.3','binarySha256':A,
                 'graphs':{'italy':{'fingerprint':A},'austria':{'fingerprint':B}},
                 'stats':{'italy':{'uniqueDirectedEdges':1,'windowsTotal':1},
                          'austria':{'uniqueDirectedEdges':2,'windowsTotal':1}}}
        (diag/'native-full-summary.json').write_text(json.dumps(summary))
        self.assertIsNotNone(retained_sources(self.root,self.pair))
        result=run(['discover',*self.args])
        self.assertEqual(result['source'],'RETAINED_NATIVE_SCAN')
        self.assertTrue(result['proposalsReady'])
        self.assertEqual(result['counts']['from-to']['receiverDirectedEdges'],2)
        self.assertEqual(result['counts']['from-to']['noExactPhysicalPeer'],1)
        self.assertEqual(result['counts']['to-from']['receiverDirectedEdges'],1)
        self.assertEqual(result['productionPublication'],'BLOCKED')
        self.assertEqual(run(['discover',*self.args])['counts'],result['counts'])
        catalog=pair_workspace(self.root,self.pair)/'gps-proposals'/'manifest.json'
        self.assertTrue(catalog.is_file())
        catalog_doc=json.loads(catalog.read_text())
        self.assertEqual(catalog_doc['androidF8ScannerParity'],'NOT_VERIFIED')

    def test_stale_graph_summary_cannot_be_reused_and_old_output_is_not_overwritten(self):
        folder=self.root/'diagnostics'/'previous';folder.mkdir(parents=True)
        summary={'schema':'roadpilot.native-valhalla-overlap-diagnostics',
                 'pairId':self.pair['pairId'],'graphs':{'italy':{'fingerprint':A},
                    'austria':{'fingerprint':C}}}
        (folder/'native-full-summary.json').write_text(json.dumps(summary))
        (folder/'italy-native-full.json').write_text('{}')
        (folder/'austria-native-full.json').write_text('{}')
        self.assertIsNone(retained_sources(self.root,self.pair))
        result=run(['status',*self.args])
        self.assertFalse(result['proposalsReady'])

    def test_external_manifest_and_invalid_journey_rejected(self):
        other=self.root.parent/'illegal-graph-studio-manifest.json'
        with self.assertRaisesRegex(ValueError,'direct retained'):
            run(['status','--workspace',str(self.root),'--from-manifest',str(other),
                 '--to-manifest',str(self.b)])
        with self.assertRaisesRegex(ValueError,'Four finite'):
            run(['probe',*self.args,'--mode','auto','--direction','from-to'])
        with self.assertRaisesRegex(ValueError,'coordinate out of range'):
            run(['probe',*self.args,'--mode','auto','--direction','from-to',
                 '--start-lat','91','--start-lng','12','--end-lat','47','--end-lng','12'])

    def test_both_orderings_and_rebuilt_graphs_have_independent_evidence_paths(self):
        one=pair_workspace(self.root,self.pair)
        two=pair_workspace(self.root,build_pair(self.b,self.a))
        self.assertNotEqual(one,two)
        new={**self.pair,'toGraphFingerprint':'sha256:'+'1'*64}
        self.assertNotEqual(one,pair_workspace(self.root,new))

if __name__=='__main__':unittest.main()
