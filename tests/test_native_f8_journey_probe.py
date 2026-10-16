"""F8 arrival/graph-local directed proof is required; bounded results never optimal."""
from __future__ import annotations
import tempfile
import gzip
import json
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_native_f8_pair_evidence import identity,edge,scan,capture,A,B,C
from build_native_f8_pair_evidence import source_scans
from discover_native_f8_crossings import generate
from probe_native_f8_journey import (inspect,check_one, distance,
    proposal_order,decode_polyline6,service_payload,ARRIVAL_TOLERANCE_METERS,
    verify_retained_graph_identity)

START={'lat':46.50,'lng':13.59}
END={'lat':46.59,'lng':13.85}


def success(start,end,mode,time=10,km=1):
    return {'status':'SUCCEEDED','startActual':start,'endActual':end,
            'startOffsetMeters':0,'endOffsetMeters':0,
            'durationSeconds':time,'distanceKm':km,'encodedShape':'sample'}

class NativeF8JourneyProofTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.pair=identity()
        self.a,self.b,_=source_scans(self.pair,capture=capture(self.pair,
                  scan([edge(10,1,46.5,13.6)]),
                  scan([edge(20,1,46.5,13.6),edge(21,2,46.56,13.75),
                        edge(22,3,46.57,13.8)])))
        self.proposals=self.root/'proposals'
        self.meta=generate(self.pair,self.a,self.b,self.proposals,{'source':'test'})

    def test_polyline6_is_graph_local_and_rejects_malformed_geometry(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):
            decode_polyline6('~')
        self.assertEqual(decode_polyline6('??'),[(0.0,0.0)])

    def test_valhalla_launcher_info_suffix_does_not_break_json_and_extra_is_rejected(self):
        self.assertEqual(service_payload('{"trip":{}}\n[INFO] Running /path/to/valhalla with args: []...')['trip'],{})
        with self.assertRaisesRegex(ValueError,'Unexpected trailing text'):
            service_payload('{"trip":{}}\n{"trip":{}}')

    def test_retained_graph_manifest_identity_must_match_pair_for_both_sides(self):
        left={'regionId':'italy','packageVersion':'v1','graphFingerprint':A,
              'primaryGeofabrikId':'italy/nord-est'}
        right={'regionId':'austria','packageVersion':'v2','graphFingerprint':B,
               'primaryGeofabrikId':'austria'}
        self.pair['toBoundarySourceId']='italy/nord-est'
        self.pair['fromBoundarySourceId']='austria'
        verify_retained_graph_identity(self.pair,left,right)
        for attribute,value in (('graphFingerprint',C),('packageVersion','stale'),
                                ('regionId','wrong')):
            invalid={**right,attribute:value}
            with self.assertRaisesRegex(ValueError,'stale graph identity'):
                verify_retained_graph_identity(self.pair,left,invalid)
        with self.assertRaisesRegex(ValueError,'source IDs mismatch'):
            verify_retained_graph_identity(self.pair,{**left,'primaryGeofabrikId':'unknown'},right)
        with self.assertRaisesRegex(ValueError,'no retained graph identity'):
            verify_retained_graph_identity(self.pair,left,None)

    def test_exact_success_requires_graph_b_trace_but_preserves_other_candidates(self):
        item={'id':'test1','receiverGraphId':200,'coordinate':{'lat':46.55,'lng':13.7}}
        def mockroute(config,start,end,mode):return success(start,end,mode)
        passed=check_one(item,Path('a'),Path('b'),START,END,'motorcycle',mockroute,
                         lambda c,s,m,p:200)
        self.assertEqual(passed['status'],'VALIDATED_FOR_THIS_JOURNEY')
        self.assertEqual(passed['handoffGapMeters'],0)
        not_traced=check_one(item,Path('a'),Path('b'),START,END,'motorcycle',mockroute,
                             lambda c,s,m,p:201)
        self.assertEqual(not_traced['status'],'UNPROVEN')

    def test_invalid_A_end_or_B_begin_must_not_count_as_crossing(self):
        item={'id':'t','receiverGraphId':10,'coordinate':{'lat':46.54,'lng':13.73}}
        def snapped(config,start,end,mode):
            result=success(start,end,mode)
            if str(config)=='a': result['endOffsetMeters']=ARRIVAL_TOLERANCE_METERS+1
            return result
        rejected=check_one(item,Path('a'),Path('b'),START,END,'auto',snapped,lambda c,s,m,p:10)
        self.assertEqual(rejected['status'],'UNPROVEN')
        self.assertIn('First graph',rejected['reason'])
        def off_B(config,start,end,mode):
            result=success(start,end,mode)
            if str(config)=='b': result['startActual']={'lat':start['lat']+.01,'lng':start['lng']}
            return result
        rejected2=check_one(item,Path('a'),Path('b'),START,END,'auto',off_B,lambda c,s,m,p:10)
        self.assertEqual(rejected2['status'],'UNPROVEN')

    def test_budgeted_probe_keeps_alternatives_after_first_and_ranks_both_styles(self):
        # Three independent receiver graph IDs; even if first works, search
        # does not terminate and a later complete trip may be faster.
        candidates,total=proposal_order(self.proposals/'from-to.jsonl.gz',START,END,3)
        self.assertEqual(total,3)
        self.assertGreaterEqual(len(candidates),2)
        legs=[]
        def mockroute(config,start,end,mode):
            if str(config)=='a':return success(start,end,mode,time=1,km=1)
            # Different candidate locations produce different route costs
            idx=round(start['lat']*1000)
            return success(start,end,mode,time=idx%11+1,km=idx%7+1)
        observed=[]
        def mocktrace(config,shape,mode,position):
            # Candidate may vary; use check_one calls separately for exact ID.
            return None
        for item in candidates:
            result=check_one(item,Path('a'),Path('b'),START,END,'auto',mockroute,
                             lambda c,s,m,p,expected=item['receiverGraphId']:expected)
            observed.append(result)
        self.assertEqual(len(observed),len(candidates))
        self.assertTrue(all(r['status']=='VALIDATED_FOR_THIS_JOURNEY' for r in observed))
        self.assertEqual(min(observed,key=lambda r:r['durationSeconds'])['candidateId'],
                         sorted(observed,key=lambda r:r['durationSeconds'])[0]['candidateId'])

    def test_bounded_search_still_compares_second_faster_and_first_shorter(self):
        ordered,total=proposal_order(self.proposals/'from-to.jsonl.gz',START,END,3)
        self.assertEqual(len(ordered),3)
        info={str(item['coordinate']['lat']):item['receiverGraphId'] for item in ordered}
        timings={str(item['coordinate']['lat']):val
                 for item,val in zip(ordered,(100,10,20))}
        lengths={str(item['coordinate']['lat']):val
                 for item,val in zip(ordered,(4,30,20))}
        def simulate(config,start,end,mode):
            reply=success(start,end,mode)
            if str(config)=='b':
                k=str(start['lat']);reply['durationSeconds']=timings[k]
                reply['distanceKm']=lengths[k];reply['encodedShape']=k
            return reply
        report=inspect(self.pair,self.meta,self.proposals,Path('a'),Path('b'),
                       START,END,'auto','from-to',3,simulate,
                       lambda config,shape,mode,pos:info[shape])
        self.assertEqual(report['successfulJourneyProbes'],3)
        self.assertEqual(report['bestOfProbedOnly']['FASTER'],ordered[1]['id'])
        self.assertEqual(report['bestOfProbedOnly']['SHORTER'],ordered[0]['id'])
        self.assertEqual(report['probesAttempted'],3)
        self.assertEqual(report['completeness'],'INCOMPLETE_BOUNDED_JOURNEY_PROBES')

    def test_truncated_catalog_fails_even_if_manifest_hash_is_updated(self):
        filepath=self.proposals/'from-to.jsonl.gz'
        with gzip.open(filepath,'rt') as f:rows=f.readlines()
        with gzip.open(filepath,'wt') as f:f.writelines(rows[:-1])
        with filepath.open('rb') as f: self.meta['files'][filepath.name]['sha256']=            'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
        with self.assertRaisesRegex(ValueError,'proposal count mismatch'):
            inspect(self.pair,self.meta,self.proposals,Path('a'),Path('b'),
                    START,END,'auto','from-to',1,lambda *args:{'status':'FAILED'},lambda *args:None)

    def test_wrong_direction_catalog_is_rejected_even_if_file_hash_is_current(self):
        filepath=self.proposals/'from-to.jsonl.gz'
        with gzip.open(filepath,'rt') as f:rows=[json.loads(x) for x in f]
        rows[0]['direction']='to-from'
        with gzip.open(filepath,'wt') as f:
            for row in rows:f.write(json.dumps(row)+'\n')
        with filepath.open('rb') as f:self.meta['files'][filepath.name]['sha256']=            'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
        with self.assertRaisesRegex(ValueError,'direction is inconsistent'):
            inspect(self.pair,self.meta,self.proposals,Path('a'),Path('b'),
                    START,END,'auto','from-to',1,lambda *args:{'status':'FAILED'},lambda *args:None)

    def test_full_bounded_report_declares_unprobed_and_cannot_publish(self):
        def fake(config,start,end,mode):return {'status':'FAILED','reason':'unreachable'}
        doc=inspect(self.pair,self.meta,self.proposals,Path('a'),Path('b'),
                    START,END,'motorcycle','from-to',1,fake,lambda *a:None)
        self.assertEqual(doc['probesAttempted'],1)
        self.assertEqual(doc['totalNativeReceiverProposals'],3)
        self.assertEqual(doc['remainingUnprobed'],2)
        self.assertEqual(doc['completeness'],'INCOMPLETE_BOUNDED_JOURNEY_PROBES')
        self.assertEqual(doc['androidF8Parity'],'NOT_VERIFIED')
        self.assertEqual(doc['productionConnectivity'],'BLOCKED')
        self.assertIsNone(doc['bestOfProbedOnly']['FASTER'])

if __name__=='__main__':unittest.main()
