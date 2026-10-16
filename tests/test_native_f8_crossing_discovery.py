"""Discovery must retain every native receiver edge, with no OSM-way matching gate."""
from __future__ import annotations
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_native_f8_pair_evidence import identity,edge,scan,capture,A,B,C,D
from build_native_f8_pair_evidence import source_scans
from discover_native_f8_crossings import generate, validate_evidence

class NativeF8CrossingDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.pair=identity()
        self.from_edges=[edge(101,777,47.0,12),edge(102,777,47.01,12),edge(103,999,47.02,12)]
        self.to_edges=[edge(200,777,47.0,12),edge(201,777,47.01,12),edge(202,456,47.03,12)]
        self.a,self.b,_=source_scans(self.pair,capture=capture(self.pair,scan(self.from_edges),scan(self.to_edges)))
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)/'proposals'

    def read(self,name):
        with gzip.open(self.folder/(name+'.jsonl.gz'),'rt') as handle:
            return [json.loads(line) for line in handle]

    def test_both_directions_all_receiver_edges_no_first_success_or_way_gate(self):
        meta=generate(self.pair,self.a,self.b,self.folder,{'source':'test'})
        ab=self.read('from-to');ba=self.read('to-from')
        self.assertEqual(len(ab),3);self.assertEqual(len(ba),3)
        self.assertEqual({c['receiverGraphId'] for c in ab},{200,201,202})
        self.assertEqual({c['receiverGraphId'] for c in ba},{101,102,103})
        self.assertEqual(ab[0]['physicalPeerOriginGraphIds'],[101])
        self.assertEqual(ab[1]['physicalPeerOriginGraphIds'],[102])
        self.assertEqual(ab[2]['physicalPeerOriginGraphIds'],[])
        self.assertEqual(ab[2]['receiverWayId'],456)
        self.assertEqual(meta['counts']['from-to']['noExactPhysicalPeer'],1)
        self.assertEqual(meta['counts']['to-from']['noExactPhysicalPeer'],1)
        self.assertEqual(meta['crossRegionRouteProof'],'NOT_RUN')
        self.assertEqual(meta['completeGraphOverlapCoverage'],'NOT_VERIFIED')
        self.assertEqual(meta['publicationState'],'BLOCKED')
        self.assertEqual(meta['androidF8ScannerParity'],'NOT_VERIFIED')
        self.assertEqual(len({x['id'] for x in ab+ba}),6)
        self.assertEqual(ab[0]['coordinate'],{'lat':47.001,'lng':12})

    def test_evidence_gzip_is_reproducible_and_bit_identical(self):
        first=generate(self.pair,self.a,self.b,self.folder,{'source':'test'})
        duplicate=self.folder.parent/'proposals-rebuild'
        second=generate(self.pair,self.a,self.b,duplicate,{'source':'test'})
        self.assertEqual(first['files'],second['files'])
        self.assertEqual((self.folder/'manifest.json').read_bytes(),
                         (duplicate/'manifest.json').read_bytes())
        for file in first['files']:
            self.assertEqual((self.folder/file).read_bytes(),(duplicate/file).read_bytes())

    def test_multiple_graph_edges_same_way_and_coordinate_all_kept(self):
        # Distinct carriageways/direct edges with same physical location are NOT merged.
        self.to_edges.append(edge(203,777,47.01,12))
        a,b,_=source_scans(self.pair,capture=capture(self.pair,scan(self.from_edges),scan(self.to_edges)))
        meta=generate(self.pair,a,b,self.folder,{'source':'test'})
        self.assertEqual(len(self.read('from-to')),4)
        self.assertEqual(meta['counts']['from-to']['exactPhysicalPeerEvidence'],3)

    def test_stale_fingerprint_and_overwrite_rejected(self):
        meta=generate(self.pair,self.a,self.b,self.folder,{'source':'test'})
        with self.assertRaisesRegex(ValueError,'already exists'):
            generate(self.pair,self.a,self.b,self.folder,{'source':'test'})
        stale={**self.pair,'toGraphFingerprint':'sha256:'+'5'*64}
        with self.assertRaisesRegex(ValueError,'Stale peer evidence identity'):
            validate_evidence(stale,{'schema':'roadpilot.native-f8-physical-pair-evidence','version':1,
                                    **{k:meta[k] for k in ['pairId','fromGraphFingerprint','toGraphFingerprint',
                                      'fromBoundaryFingerprint','toBoundaryFingerprint','scanner',
                                      'publicationState']},'androidF8ReferenceMatched':'NOT_VERIFIED'})

    def test_direct_generate_rejects_truncated_scan_and_mismatched_windows(self):
        self.a['complete']=False
        with self.assertRaisesRegex(ValueError,'incomplete'):
            generate(self.pair,self.a,self.b,self.folder,{'source':'test'})
        self.a['complete']=True
        self.b['windows'][0]['minLat']=46.02
        with self.assertRaisesRegex(ValueError,'different window catalogs'):
            generate(self.pair,self.a,self.b,self.folder,{'source':'test'})
        self.assertFalse(self.folder.exists())

    def test_invalid_historical_peer_evidence_cannot_be_accepted(self):
        for state in ('VALIDATED','PUBLISHED'):
            with self.assertRaisesRegex(ValueError,'purported verified'):
                validate_evidence(self.pair,{'schema':'roadpilot.native-f8-physical-pair-evidence',
                    'version':1,'publicationState':state,'scanner':'GraphStudio.nativeUncappedRoadEdges',
                    'androidF8ReferenceMatched':'NOT_VERIFIED',
                    **{field:self.pair[field] for field in ['pairId','fromGraphFingerprint',
                            'toGraphFingerprint','fromBoundaryFingerprint','toBoundaryFingerprint']}})

if __name__=='__main__':unittest.main()
