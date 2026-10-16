"""F8 native physical peer foundations: no inferred legal handoffs or peer suppression."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_native_f8_pair_evidence as evidence

A = 'sha256:' + 'a' * 64
B = 'sha256:' + 'b' * 64
C = 'sha256:' + 'c' * 64
D = 'sha256:' + 'd' * 64


def identity():
    return {'schema':'roadpilot.cross-region-connectivity','version':1,
            'validationState':'UNPROVEN','pairId':'italy__austria',
            'fromRegionId':'italy','toRegionId':'austria',
            'fromPackageVersion':'v1','toPackageVersion':'v2',
            'fromGraphFingerprint':A,'toGraphFingerprint':B,
            'fromBoundaryFingerprint':C,'toBoundaryFingerprint':D}


def edge(graph_id, way, lat, lon, inner_lat=None, inner_lon=None, forward=2031, reverse=0):
    return {'graphId':graph_id,'wayId':way,'lat':lat,'lon':lon,
            'innerLat':lat+.001 if inner_lat is None else inner_lat,
            'innerLon':lon if inner_lon is None else inner_lon,
            'forwardAccess':forward,'reverseAccess':reverse,
            'roadClass':0,'use':0,'toll':False,'unpaved':False,'tunnel':False}


def scan(edges):
    return {'complete':True,'windows':[{'index':0,'minLat':46.0,'maxLat':46.1,
                    'minLon':12.0,'maxLon':12.1,'complete':True,'truncated':False,
                    'maxResults':None,'visitedTiles':1,'visitedNodes':1,
                    'returned':len(edges)}],'edges':edges}


def capture(pair,a,b):
    return {'schema':'roadpilot.native-f8-edge-scan','version':1,
            'scanner':'GraphStudio.nativeUncappedRoadEdges',
            'nativeF8ReferenceCaptured':False,'f8GraphEdgeParity':'NOT_VERIFIED',
            'pairId':pair['pairId'],
            'fromGraph':{'regionId':'italy','packageVersion':'v1','graphFingerprint':A},
            'toGraph':{'regionId':'austria','packageVersion':'v2','graphFingerprint':B},
            'fromBoundaryFingerprint':C,'toBoundaryFingerprint':D,
            'scans':{'from':a,'to':b}}


class NativePhysicalPeerTests(unittest.TestCase):
    def test_multiple_positions_carriageways_directions_kept_without_any_mode_filter(self):
        # Physical peers including same-way alternate positions and opposite access
        # are retained. Even inaccessible/misaligned peers are only evidence,
        # never classified as legal or discarded based on access/road class.
        from_edges=[edge(11,100,47,12,forward=0),edge(12,100,47.01,12),
                    edge(13,100,47.01,12,forward=1),edge(14,200,47.5,12.5)]
        to_edges=[edge(11,100,47,12,reverse=5),edge(21,100,47.01,12),
                  edge(22,100,47.01,12,forward=0),edge(23,201,47.5,12.5)]
        pair=identity()
        a,b,_=evidence.source_scans(pair,capture=capture(pair,scan(from_edges),scan(to_edges)))
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'native-pairs'
            manifest=evidence.produce(pair,a,b,target,{'source':'test'})
            peers=[json.loads(s) for s in (target/'physical-peers.jsonl').read_text().splitlines()]
            self.assertEqual(manifest['counts']['physicalPeerPairs'],5)
            self.assertEqual({(x['fromEdge']['graphId'],x['toEdge']['graphId']) for x in peers},
                             {(11,11),(12,21),(12,22),(13,21),(13,22)})
            self.assertEqual(manifest['counts']['unpairedFromEdges'],1)
            self.assertEqual(manifest['counts']['unpairedToEdges'],1)
            self.assertEqual(json.loads((target/'unpaired-from.jsonl').read_text())['graphId'],14)
            self.assertEqual(json.loads((target/'unpaired-to.jsonl').read_text())['graphId'],23)
            self.assertEqual(manifest['publicationState'],'BLOCKED')
            self.assertEqual(manifest['valhallaLegsProven'],'NOT_RUN')
            self.assertEqual(manifest['androidF8ReferenceMatched'],'NOT_VERIFIED')
            self.assertEqual(manifest['frontierCorrelations'],'NOT_VERIFIED')
            self.assertEqual(len({x['id'] for x in peers}),5)
            with self.assertRaisesRegex(ValueError,'already exists'):
                evidence.produce(pair,a,b,target,{'source':'test'})

    def test_matching_by_graph_id_alone_would_be_wrong(self):
        pair=identity()
        a,b,_=evidence.source_scans(pair,capture=capture(pair,scan([edge(101,5,47,12)]),
                                          scan([edge(101,7,47,12)])))
        with tempfile.TemporaryDirectory() as temp:
            manifest=evidence.produce(pair,a,b,Path(temp)/'result',{'source':'test'})
            self.assertEqual(manifest['counts']['physicalPeerPairs'],0)
            self.assertEqual(manifest['counts']['unpairedFromEdges'],1)
            self.assertEqual(manifest['counts']['unpairedToEdges'],1)

    def test_graph_fingerprint_and_boundary_and_completion_fail_closed(self):
        pair=identity()
        first,second=scan([edge(1,5,47,12)]),scan([edge(2,5,47,12)])
        for field in ('fromGraphFingerprint','toBoundaryFingerprint'):
            bad=capture(pair,first,second)
            if field=='fromGraphFingerprint':bad['fromGraph']['graphFingerprint']=D
            else:bad['toBoundaryFingerprint']=A
            with self.assertRaisesRegex(ValueError,'Stale'):
                evidence.source_scans(pair,capture=bad)
        first['windows'][0]['truncated']=True
        with self.assertRaisesRegex(ValueError,'truncated'):
            evidence.source_scans(pair,capture=capture(pair,first,second))
        first['windows'][0]['truncated']=False
        first['complete']=False
        with self.assertRaisesRegex(ValueError,'incomplete'):
            evidence.source_scans(pair,capture=capture(pair,first,second))

    def test_retained_scans_require_exact_native_summary_graph_identity(self):
        pair=identity()
        first,second=scan([edge(1,5,47,12)]),scan([edge(2,5,47,12)])
        summary={'schema':evidence.SUMMARY_SCHEMA,'pairId':pair['pairId'],
                 'f8GraphEdgeParity':'NOT_VERIFIED','nativeAndroidF8ReferenceCaptured':False,
                 'version':'3.6.3','binarySha256':A,
                 'graphs':{'italy':{'fingerprint':A},'austria':{'fingerprint':B}},
                 'stats':{'italy':{'uniqueDirectedEdges':1,'windowsTotal':1},
                          'austria':{'uniqueDirectedEdges':1,'windowsTotal':1}}}
        a,b,provenance=evidence.source_scans(pair,from_scan=first,to_scan=second,scan_summary=summary)
        self.assertEqual(len(a['edges']),len(b['edges']))
        self.assertEqual(provenance['source'],'RETAINED_UNCAPPED_NATIVE_PORT_EVIDENCE')
        summary['graphs']['austria']['fingerprint']=A
        with self.assertRaisesRegex(ValueError,'Stale'):
            evidence.source_scans(pair,from_scan=first,to_scan=second,scan_summary=summary)

    def test_rejects_missing_or_misaligned_native_spatial_windows(self):
        pair=identity()
        first,second=scan([edge(11,5,47,12)]),scan([edge(22,5,47,12)])
        second['windows'][0]['minLon']=12.02
        with self.assertRaisesRegex(ValueError, 'different window catalogs'):
            evidence.source_scans(pair,capture=capture(pair,first,second))
        second['windows'][0]['minLon']=12.0
        second['windows'][0]['index']=1
        with self.assertRaisesRegex(ValueError, 'window index'):
            evidence.source_scans(pair,capture=capture(pair,first,second))
        second['windows'][0]['index']=0
        second['windows'][0]['visitedTiles']=True
        with self.assertRaisesRegex(ValueError, 'visitedTiles'):
            evidence.source_scans(pair,capture=capture(pair,first,second))
        second['windows'][0]['visitedTiles']=1
        first['windows'].append(dict(first['windows'][0],index=1))
        second['windows'].append(dict(second['windows'][0],index=1))
        with self.assertRaisesRegex(ValueError, 'repeated spatial windows'):
            evidence.source_scans(pair,capture=capture(pair,first,second))

    def test_rejects_invalid_access_and_ambiguous_input_identity(self):
        pair=identity()
        first,second=scan([edge(11,5,47,12)]),scan([edge(22,5,47,12)])
        first['edges'][0].pop('reverseAccess')
        with self.assertRaisesRegex(ValueError,'reverseAccess'):
            evidence.source_scans(pair,capture=capture(pair,first,second))
        first['edges'][0]['reverseAccess']=0
        first['edges'][0]['forwardAccess']=True
        with self.assertRaisesRegex(ValueError,'forwardAccess'):
            evidence.source_scans(pair,capture=capture(pair,first,second))
        first['edges'][0]['forwardAccess']=2031
        pair['fromRegionId']='austria'
        pair['pairId']='austria__austria'
        with self.assertRaisesRegex(ValueError,'two different regions'):
            evidence.source_scans(pair,capture=capture(pair,first,second))

    def test_bad_scan_schema_and_nan_fields_cannot_be_published(self):
        pair=identity()
        first,second=scan([edge(11,5,47,12)]),scan([edge(22,5,47,12)])
        doc=capture(pair,first,second)
        doc['version']=2
        with self.assertRaisesRegex(ValueError,'uncapped native'):
            evidence.source_scans(pair,capture=doc)
        doc['version']=1
        first['edges'][0]['roadClass']=float('nan')
        with self.assertRaisesRegex(ValueError,'roadClass'):
            evidence.source_scans(pair,capture=doc)
        first['edges'][0]['roadClass']=0
        first['edges'][0]['toll']=0
        with self.assertRaisesRegex(ValueError,'toll'):
            evidence.source_scans(pair,capture=doc)

    def test_scan_window_completeness_is_not_overlap_completeness(self):
        pair=identity()
        a,b,_=evidence.source_scans(pair,capture=capture(pair,scan([edge(11,5,47,12)]),
                                              scan([edge(22,5,47,12)])))
        with tempfile.TemporaryDirectory() as temp:
            out=evidence.produce(pair,a,b,Path(temp)/'out',{'source':'test'})
            self.assertEqual(out['sharedBufferOverlapCoverage'],'NOT_VERIFIED')
            self.assertEqual(out['sourceWindowCoverage'],
                'SOURCE_REPORTED_COMPLETE_MATCHING_WINDOW_CATALOG')
            self.assertTrue(out['windowCatalogSha256'].startswith('sha256:'))

    def test_no_false_parity_from_matching_all_edges(self):
        pair=identity()
        a,b,_=evidence.source_scans(pair,capture=capture(pair,scan([edge(11,5,47,12)]),
                                             scan([edge(22,5,47,12)])))
        with tempfile.TemporaryDirectory() as temp:
            out=evidence.produce(pair,a,b,Path(temp)/'out',{'source':'test'})
            self.assertEqual(out['counts']['unpairedFromEdges'],0)
            self.assertEqual(out['publicationState'],'BLOCKED')
            self.assertEqual(out['routingOptimalityChecked'],'NOT_VERIFIED')

if __name__=='__main__':unittest.main()
