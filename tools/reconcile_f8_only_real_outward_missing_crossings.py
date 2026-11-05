#!/usr/bin/env python3
"""Only reconcile verified A-last outward crossings that lack original B-first.

These are physically relevant ORIGINAL source graph road edges that cross the
source buffer cutoff into the receiving region's original core. Unlike
unrelated source graph junctions, these are actionable candidate crossings.
Require original A last-TripLeg mode proof, original A local terminal mode
topology, receiver FULL original archive near-edge search, physically forward
B road geometry, and exact Valhalla B FIRST TripLeg. Short-B fallback uses
the exact native edge endpoint; does not relax acceptance.
"""
import argparse
from collections import Counter
import copy,json,os,tempfile
from pathlib import Path

from build_f8_final_edge_connections import (
 fingerprint,native_lines,directed_line,physical_forward_continuation,
 local_receiver_probe,prove_receiver_modes,MODES)
from gate_f8_source_final_native_topology import (
 hierarchy_rows,validate_mode,FINAL)
from complete_f8_original_receiving_archive import original_receiver_scan

def positive_receiver_proof(rec,src,point,original_receiver_graphid,
                            config,route_binary,mode_set):
    source_line=directed_line(src)
    receiver_line=directed_line(rec)
    geom=physical_forward_continuation(source_line,receiver_line)
    if not geom or geom['status']!='FORWARD_CONTINUOUS':
        return None
    probe=local_receiver_probe(receiver_line,geom['receiverProjectionMeters'])
    proofs=prove_receiver_modes(config,route_binary,point,probe,
                                original_receiver_graphid,mode_set)
    for m in mode_set:
        proofs[m]['originalReceiverProbeMethod']='INTERIOR_DIRECTED_EDGE'
    failed={m for m in mode_set if not proofs[m]['verified']}
    if failed:
        end={'lat':rec['directedGeometry'][-1][0],
             'lng':rec['directedGeometry'][-1][1]}
        alt=prove_receiver_modes(config,route_binary,point,end,
                                original_receiver_graphid,failed)
        for m,p in alt.items():
            if p['verified']:
                p['originalReceiverProbeMethod']='NATIVE_DIRECTED_EDGE_TERMINAL'
                proofs[m]=p
    passed=[m for m in MODES if m in proofs and proofs[m]['verified']]
    if not passed:return None
    return {'receiverFirstDirectedGraphId':original_receiver_graphid,
            'travelModes':passed,
            'directedPhysicalGeometry':geom,
            'originalReceiverValhallaTripLeg':proofs,
            'downstreamTestPoint':probe,
            'receiverWayIdAnnotationOnly':rec['wayId'],
            'sourceWayIdAnnotationOnly':src['wayId']}


def run(args):
    files={'catalog':args.catalog,'bilateral':args.bilateral,
        'source':args.native_endpoints,'receiverScan':args.native_full_receiver,
        'routes':args.native_route,'italy':args.from_graph,'austria':args.to_graph}
    hashes={k:fingerprint(v) for k,v in files.items()}
    assert hashes['source']==args.expected_endpoints_sha256
    assert hashes['receiverScan']==args.expected_receiver_sha256
    assert hashes['routes']==args.expected_route_sha256
    ledger=json.loads(args.catalog.read_text())
    bilateral=json.loads(args.bilateral.read_text())
    assert ledger['sourceDiscoveryComplete'] is False
    assert ledger['productionPublication']=='BLOCKED'
    assert ledger['graphFingerprints']=={'from':hashes['italy'],'to':hashes['austria']}
    assert bilateral['sourceLedgerSha256']==hashes['catalog']
    assert bilateral['pairId']==ledger['pairId']
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('Refuse to overwrite original source audit')
    result=copy.deepcopy(ledger)
    known={(x['sourceRegionId'],x['sourceFinalDirectedGraphId']):x
           for x in result['connections']}
    unresolved={(x['sourceRegionId'],x['sourceFinalDirectedGraphId']):x
           for x in result['unresolvedSourceFinalEdges']}
    counts=Counter()
    for side,from_region,to_region,from_config,to_config in (
        ('from-to','italy-nord-est','austria',args.from_config,args.to_config),
        ('to-from','austria','italy-nord-est',args.to_config,args.from_config)):
        candidates={
            x['originalOutwardSourceCutDirectedGraphId']
            for x in bilateral['regions'][side]['actualPeerCoreOriginalDirectedRoadCutCandidates']
            if x['status']=='ORIGINAL_SOURCE_CUT_GRAPHID_PREVIOUSLY_UNRESOLVED'
               and x['unresolvedReason']=='NO_VALHALLA_VERIFIED_FORWARD_RECEIVING_ROAD'}
        counts[side+'_candidateOutboundCutRoadGraphIds']=len(candidates)
        if not candidates:continue
        if not all((from_region,gid) in unresolved for gid in candidates):
            raise ValueError('Original source candidate audit not grounded in ledger')
        with tempfile.TemporaryDirectory(prefix='f8-only-missing-outward-peer-') as folder:
            tmp=Path(folder)
            src=native_lines(args.native_endpoints,from_config,candidates,tmp)
            hierarchy=hierarchy_rows(args.native_endpoints,from_config,candidates,tmp)
            outgoing={r['graphId'] for x in hierarchy.values()
                for n in x['nativeAllHierarchyContinuationNodes']
                for r in n['allOutgoingDirectedEdges']
                if r['graphId'] != x['opposingGraphId']}
            src_neighbors=native_lines(args.native_endpoints,from_config,
                  outgoing,tmp)
            terminal={}
            for gid in sorted(candidates):
                row=unresolved[(from_region,gid)]
                good={}
                for m in row['sourceValhallaProvedModes']:
                    proof=row['sourceRouteProofs'][m]
                    if not proof['verified']:continue
                    # An A-LAST TripLeg alone does not establish that a road
                    # genuinely ends at this graph edge. Validate mode-specific
                    # original native terminal topology separately.
                    verdict=validate_mode(src[gid],hierarchy[gid],src_neighbors,m)
                    if verdict['status']==FINAL:
                        good[m]=verdict
                    else:
                        counts[side+'_actualCutCandidatesAContinuesOrAmbiguous']+=1
                if good:
                    terminal[gid]=good
            counts[side+'_AOriginalTerminalModeProvedIds']=len(terminal)
            if not terminal:continue
            points={gid:unresolved[(from_region,gid)]['sourceFinalCoordinate']
                    for gid in terminal}
            recscan=original_receiver_scan(args.native_full_receiver,to_config,
                                           points,tmp)
            tilecount=338 if to_region=='austria' else 367
            if recscan['summary']['originalReceiverTileCount']!=tilecount:
                raise ValueError('Receiving original all-tile census not complete')
            receivers=native_lines(args.native_endpoints,to_config,
                {id for ids in recscan['pairs'].values() for id in ids},tmp)
            counts[side+'_BAllOriginalDirectedShapeCandidates']=sum(
                len(ids) for ids in recscan['pairs'].values())
            for gid,modes in terminal.items():
                opts=[]
                for b_gid in sorted(recscan['pairs'][gid]):
                    opt=positive_receiver_proof(receivers[b_gid],src[gid],points[gid],
                       b_gid,to_config,args.native_route,set(modes))
                    counts[side+'_BOriginalDirectedOptionsChecked']+=1
                    if opt:
                        opt['receiverGraphFingerprint']=ledger['graphFingerprints'][
                            'to' if from_region=='italy-nord-est' else 'from']
                        opts.append(opt)
                if not opts:
                    counts[side+'_NoOriginalBFirstRouteProved']+=1
                    continue
                original=unresolved[(from_region,gid)]
                item={
                    'sourceRegionId':from_region,'receiverRegionId':to_region,
                    'sourceFinalDirectedGraphId':gid,
                    'sourceFinalCoordinate':points[gid],
                    'sourceValhallaProvedModes':list(modes),
                    'originalSourceValhallaTripLeg':original['sourceRouteProofs'],
                    'originalSourceFinalTopologyProof':modes,
                    'receiverOptions':opts,
                    'receiverCandidateCensusComplete':True,
                    'originalReceiverAllTileGeometryScan':
                        'EXHAUSTIVE_GETTILESET_FOR_SOURCE_END',
                    'physicalRoadDirectionIdentity':{
                        'sourceFinalDirectedGraphId':gid,
                        'notOsMNameOrProximityDeduplication':True}}
                key=(from_region,gid)
                if key in known:raise ValueError('Duplicate final directed source GraphId')
                result['connections'].append(item)
                known[key]=item
                counts[side+'_additionalExactSourceLastMatchedIds']+=1
                counts[side+'_additionalExactBFirstDirectedOptions']+=len(opts)
    result['unresolvedSourceFinalEdges']=[
       x for x in result['unresolvedSourceFinalEdges']
       if (x['sourceRegionId'],x['sourceFinalDirectedGraphId']) not in known]
    result['targetedActualBilateralMissingCrossingReconciliation']={
       'scope':'ONLY_ALREADY_A_LAST_PROVED_OUTWARD_SOURCE_CUT_ROADS_TOUCHING_PEER_CORE',
       'counts':dict(counts),'inputHashes':hashes,
       'sourceCrossingCoverageComplete':False,
       'unrelatedNativeContinuationBranchesAreNotAReleaseRequirement':True}
    result['sourceDiscoveryComplete']=False
    result['physicalRoadPerDirectionGlobalUniqueness']='NOT_VERIFIED'
    result['productionPublication']='BLOCKED'
    allkeys=[(x['sourceRegionId'],x['sourceFinalDirectedGraphId'])
        for x in result['connections']+result['unresolvedSourceFinalEdges']]
    assert len(allkeys)==len(set(allkeys))
    for k,v in files.items():
        if fingerprint(v)!=hashes[k]:raise ValueError('Source evidence or graph changed')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',delete=False,dir=args.output.parent,
        prefix='.f8-outward-only-',encoding='utf8') as f:
        stage=Path(f.name)
        json.dump(result,f,separators=(',',':'),allow_nan=False);f.write('\n')
    try:os.link(stage,args.output)
    finally:stage.unlink(missing_ok=True)
    print('TARGETED_REAL_OUTWARD_CROSSING_COUNTS',dict(counts),flush=True)
    print('TOTAL_VERIFIED',len(result['connections']),
       sum(len(x['receiverOptions']) for x in result['connections']),
       'FILE',args.output,'SHA',fingerprint(args.output),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','bilateral','from-config','to-config','from-graph',
                 'to-graph','native-endpoints','native-full-receiver',
                 'native-route','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('endpoints','receiver','route'):
        p.add_argument('--expected-'+name+'-sha256',required=True)
    run(p.parse_args())

if __name__=='__main__':
    main()
