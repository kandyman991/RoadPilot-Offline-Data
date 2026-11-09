"""D-017 native A->exact X->B BLOCKED catalog: no legacy TripLeg requirement."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from extract_f8_region_final_edges import (
    build_nonpublishing_native_handoff_catalog,
    write_nonpublishing_native_catalog,
    validate_native_receiver_successor_at_x,
)


def sha(char):
    return 'sha256:' + char*64


def sample_evidence():
    common = {
        'sourceOriginalEndNodeGraphId': 500,
        'sourceVehicleModes':1025, 'sourceNativeRoadClass':6,
        'sourceNativeRoadUse':0, 'sourceNativeLayer':0,
        'sourceNativeBridge':False,'sourceNativeTunnel':False,
        'sourcePhysicalRoadFinalCompleteness':'NOT_VERIFIED',
        'sourceCutGraphIds':[],'correspondingBPredecessorAtXGraphIds':[99],
        'receivingNativeUnresolvedContinuations':[],
    }
    outgoing = {
        'sharedVehicleModes':1025,
        'fromNativeBPredecessorGraphIds':[99],
        'status':'VERIFIED_B_ORIGINAL_SAME_NODE_LEGAL_BRANCH',
        'originalPhysicalRoadIdentityStatus':'NOT_VERIFIED',
        'originalNativeBranchRelationshipEvidence':
            'CONSISTENT_NATIVE_ROAD_ATTRIBUTES_PHYSICAL_IDENTITY_UNVERIFIED',
        'receiverNativeRoadClass':6,'receiverNativeRoadUse':0,
        'receiverNativeLayer':0,'receiverNativeBridge':False,
        'receiverNativeTunnel':False,'nativeReceiverStartGapMetres':0.02,
        'nativeSameClassAsBPredecessor':True,
        'nativeSameUseAsBPredecessor':True,
        'nativeSameStructureAsBPredecessor':True,
    }
    good = {**common,'sourceFinalDirectedGraphId':101,
            'x':{'lat':45.,'lon':10.},
            'receiverCorrelationStatus':'B_NATIVE_DIRECTIONAL_CONTINUATIONS_IDENTIFIED',
            'receivingNativeDirectedContinuationOptions':[
                {**outgoing,'receiverDirectedGraphId':201},
                {**outgoing,'receiverDirectedGraphId':202,
                 'sharedVehicleModes':1024,
                 'nativeSameStructureAsBPredecessor':False,
                 'originalNativeBranchRelationshipEvidence':
                 'NATIVE_STRUCTURE_CHANGE_PHYSICAL_IDENTITY_UNVERIFIED'}]}
    bad = {**common, 'sourceFinalDirectedGraphId':102,
           'x':{'lat':45.0001,'lon':10.0001},
           'receiverCorrelationStatus':'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED',
           'receivingNativeDirectedContinuationOptions':[],
           'receivingNativeUnresolvedContinuations':[{
              'receiverPredecessorGraphId':99,'receiverDirectedGraphId':301,
              'car':'UNRESOLVED_SHORTCUT',
              'motorcycle':'UNRESOLVED_PATH_OR_TIME_CONTEXT'}]}
    nothing = {**common, 'sourceFinalDirectedGraphId':103,
               'x':{'lat':45.0002,'lon':10.0002},
               'receiverCorrelationStatus':'NO_PROVEN_B_NATIVE_OUTGOING_AFTER_X',
               'receivingNativeDirectedContinuationOptions':[]}
    return {
        'schema':'roadpilot.f8-paired-native-receiver-correlation-evidence',
        'schemaVersion':1,'productionPublication':'BLOCKED',
        'sourcePhysicalRoadDirectionCompleteness':'NOT_VERIFIED',
        'androidFullJourneyValidation':'NOT_RUN',
        'approvedBoundaryExteriorTerminalInventory':{
            'allPairBoundaryOuterTerminalGraphIds':[101,102,103],
            'originalSourceTerminalEdgesOutsideAWithinB':3,
            'terminalEndpointDomainTileCoverage':'COMPLETE_FOR_ORIGINAL_INDEX_BOUNDS',
            'nativeLongEdgeOriginCoverage':'VERIFIED_FOR_ORIGINAL_PAIR_ENDPOINT_DOMAIN',
            'nativeIncomingOriginOutsideSelectedPairTilesCount':0,
            'wholeGraphCensusPerformed':False,
        },
        'sourceGraphFingerprint':sha('a'),'receiverGraphFingerprint':sha('b'),
        'sourceBufferFingerprint':sha('c'),'receiverBufferFingerprint':sha('d'),
        'sourceIndexFingerprint':sha('e'),'receiverIndexFingerprint':sha('f'),
        'sourceEvidenceSha256':sha('0'),
        'reciprocalBoundaryFingerprints':{'pairedA':sha('1'),'pairedB':sha('2')},
        'sourceRegionId':'region-a','receiverRegionId':'region-b',
        'sourceFinalCandidateCount':3,
        'sourceToReceiverCandidates':[good,bad,nothing],
        'sourceUnresolvedNonterminalRootGraphIds':[5,6],
        'sourceUnresolvedNonterminalRootCount':2,
        'originalSourceCutRootCoverage':[{'originalSourceCutGraphId':5,
                'boundedOriginalSourceRootStatus':
                 'ROOT_NO_TERMINAL_CANDIDATE_WITHIN_TWO_BOUNDED_HOPS'},
              {'originalSourceCutGraphId':6,
                'boundedOriginalSourceRootStatus':
                 'ROOT_HAS_NATIVE_RECEIVER_OPTIONS_SOURCE_LINEAGE_UNPROVEN'}],
        'originalSourceCutRootCoverageCounts':{
            'ROOT_NO_TERMINAL_CANDIDATE_WITHIN_TWO_BOUNDED_HOPS':1,
            'ROOT_HAS_NATIVE_RECEIVER_OPTIONS_SOURCE_LINEAGE_UNPROVEN':1},
    }


class NativeFinalConnectionCatalogTests(unittest.TestCase):
    def test_bundled_schema_is_blocked_and_never_legacy_tripleg(self):
        schema_path=Path(__file__).resolve().parents[1]/'schemas'/            'f8-final-directed-connection-candidates.schema.json'
        schema=json.loads(schema_path.read_text(encoding='utf-8'))
        self.assertEqual(schema['$schema'],
                         'https://json-schema.org/draft/2020-12/schema')
        self.assertEqual(schema['properties']['version']['const'],1)
        self.assertEqual(schema['properties']['productionPublication']['const'],
                         'BLOCKED')
        self.assertEqual(schema['properties']['androidFullJourneyAcceptance']['const'],
                         'NOT_RUN')
        self.assertEqual(schema['properties']['physicalRoadIdentityAcceptance']['const'],
                         'NOT_VERIFIED')
        self.assertIn('reciprocalBoundaryFingerprints',schema['required'])
        self.assertNotIn('originalReceiverValhallaTripLeg',json.dumps(schema))

    def test_one_source_record_preserves_two_distinct_directed_b_branches_and_modes(self):
        catalog=build_nonpublishing_native_handoff_catalog(sample_evidence())
        self.assertEqual(catalog['schema'],
                         'roadpilot.f8-final-directed-connection-candidates')
        self.assertEqual(catalog['version'],1)
        self.assertEqual(catalog['pairId'],'region-a__region-b')
        self.assertEqual(catalog['graphFingerprints'],{'from':sha('a'),'to':sha('b')})
        self.assertEqual(catalog['productionPublication'],'BLOCKED')
        self.assertFalse(catalog['sourceDiscoveryComplete'])
        self.assertFalse(catalog['receiverMatchingComplete'])
        self.assertEqual(catalog['androidFullJourneyAcceptance'],'NOT_RUN')
        self.assertEqual(catalog['counts']['eligibleSourceFinals'],3)
        self.assertEqual(catalog['counts']['candidateSourcesWithBOptions'],1)
        self.assertEqual(catalog['counts']['unresolvedEligibleSourceFinals'],2)
        self.assertEqual(catalog['counts']['nativeOriginalBDirectedOptions'],2)
        self.assertEqual(catalog['counts']['originalSourceCutRootsNotLinkedWithinBoundedScope'],1)
        self.assertEqual(catalog['unresolvedOriginalCutRootLineageGraphIds'],[5])
        self.assertEqual([r['sourceFinalDirectedGraphId'] for r in catalog['connectionCandidates']],[101])
        self.assertEqual([r['sourceFinalDirectedGraphId'] for r in catalog['unresolvedSourceFinalEdges']],[102,103])
        a=catalog['connectionCandidates'][0]
        self.assertEqual([o['receiverFirstDirectedGraphId'] for o in a['receiverOptions']],[201,202])
        self.assertEqual([o['travelModes'] for o in a['receiverOptions']],
                         [['auto','motorcycle'],['motorcycle']])
        self.assertTrue(all(not option['samePhysicalRoadVerified']
                            for option in a['receiverOptions']))
        self.assertEqual([r['reason'] for r in catalog['unresolvedSourceFinalEdges']],
             ['ORIGINAL_B_CONDITIONAL_HIERARCHY_OR_PATH_CONTEXT_UNRESOLVED',
              'NO_ORIGINAL_B_NATIVE_ALLOWED_FORWARD_CONTINUATION'])
        self.assertTrue(all(row['mustNotCreateConnection']
                            for row in catalog['unresolvedSourceFinalEdges']))
        self.assertNotIn('originalReceiverValhallaTripLeg',json.dumps(catalog))

    def test_catalog_rejects_incomplete_coverage_or_unproven_original_sources(self):
        for change in (
                lambda e:e['approvedBoundaryExteriorTerminalInventory'].update(
                    nativeIncomingOriginOutsideSelectedPairTilesCount=1),
                lambda e:e['approvedBoundaryExteriorTerminalInventory'].update(
                    wholeGraphCensusPerformed=True),
                lambda e:e.update(productionPublication='READY'),
                lambda e:e.update(sourcePhysicalRoadDirectionCompleteness='VERIFIED'),
                lambda e:e['approvedBoundaryExteriorTerminalInventory'].update(
                    allPairBoundaryOuterTerminalGraphIds=[101,102,104]),
                lambda e:e['sourceToReceiverCandidates'].append(
                    e['sourceToReceiverCandidates'][0]),
                lambda e:e.update(receiverGraphFingerprint=sha('g')),
                lambda e:e['sourceToReceiverCandidates'][0].update(
                    sourcePhysicalRoadFinalCompleteness='COMPLETE'),
                lambda e:e['sourceToReceiverCandidates'][0].update(
                    sourceVehicleModes=0),
                lambda e:e.pop('reciprocalBoundaryFingerprints')):
            data=sample_evidence()
            change(data)
            with self.subTest(change=change):
                with self.assertRaises((ValueError, KeyError)):
                    build_nonpublishing_native_handoff_catalog(data)

    def test_catalog_rejects_duplicate_receiver_or_invalid_mode_or_falsified_identity(self):
        for change in (
                lambda e:e['sourceToReceiverCandidates'][0]
                    ['receivingNativeDirectedContinuationOptions'][1].update(
                        receiverDirectedGraphId=201),
                lambda e:e['sourceToReceiverCandidates'][0]
                    ['receivingNativeDirectedContinuationOptions'][0].update(
                        sharedVehicleModes=2),
                lambda e:e['sourceToReceiverCandidates'][0]
                    ['receivingNativeDirectedContinuationOptions'][0].update(
                        originalPhysicalRoadIdentityStatus='VERIFIED'),
                lambda e:e['sourceToReceiverCandidates'][0]
                    ['receivingNativeDirectedContinuationOptions'][0].update(
                        originalNativeBranchRelationshipEvidence='TRIPLEG_ROUTE_PROOF'),
                lambda e:e['sourceToReceiverCandidates'][0]
                    ['receivingNativeDirectedContinuationOptions'][0].update(
                        nativeReceiverStartGapMetres=1.0),
                lambda e:e['sourceToReceiverCandidates'][0]
                    ['receivingNativeDirectedContinuationOptions'][0].update(
                        nativeSameClassAsBPredecessor=False)):
            data=sample_evidence();change(data)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    build_nonpublishing_native_handoff_catalog(data)

    def test_same_original_b_node_must_start_at_exact_x(self):
        predecessor={'roadClass':6,'roadUse':0,'layer':0,
                     'bridge':False,'tunnel':False}
        same={**predecessor,'startLat':45.,'startLon':10.}
        valid=validate_native_receiver_successor_at_x({'lat':45.,'lon':10.},
                                                       predecessor,same)
        self.assertEqual(valid['nativeReceiverStartGapMetres'],0.)
        self.assertEqual(valid['originalPhysicalRoadIdentityStatus'],'NOT_VERIFIED')
        self.assertEqual(valid['originalNativeBranchRelationshipEvidence'],
                         'CONSISTENT_NATIVE_ROAD_ATTRIBUTES_PHYSICAL_IDENTITY_UNVERIFIED')
        for bad in ({**same,'startLat':45.0001},
                    {**same,'startLat':float('nan')},
                    {**same,'startLat':None}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    validate_native_receiver_successor_at_x(
                        {'lat':45.,'lon':10.},predecessor,bad)
        different={**same,'roadUse':3}
        self.assertIn('CLASS_OR_USE_CHANGE',
            validate_native_receiver_successor_at_x(
                {'lat':45.,'lon':10.},predecessor,different)
                ['originalNativeBranchRelationshipEvidence'])
        layered={**same,'layer':2}
        self.assertIn('STRUCTURE_CHANGE',
            validate_native_receiver_successor_at_x(
                {'lat':45.,'lon':10.},predecessor,layered)
                ['originalNativeBranchRelationshipEvidence'])

    def test_writer_is_immutable_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'blocked-candidates.json'
            counts=write_nonpublishing_native_catalog(evidence=sample_evidence(),
                                                       output_path=path)
            result=json.loads(path.read_text())
            self.assertEqual(counts,result['counts'])
            self.assertEqual(result['productionPublication'],'BLOCKED')
            original=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'already exists'):
                write_nonpublishing_native_catalog(evidence=sample_evidence(),
                                                   output_path=path)
            self.assertEqual(original,path.read_bytes())

if __name__=='__main__':
    unittest.main()
