#!/usr/bin/env python3
"""Bounded *journey-scoped* Valhalla probe of native F8 GPS proposals.

F8 semantics: route origin on Graph A to receiver-side GPS X, normalize X to
Graph A's actual endpoint, then route that coordinate in Graph B to destination.
Keep testing other proposals after first complete success. Does NOT prove full
regional frontier completeness, FASTER/SHORTER optimality, or JNI F8 parity.
"""
from __future__ import annotations

import argparse
import gzip
import heapq
import os
import json
import math
from pathlib import Path
from typing import Callable
import subprocess
import tempfile

from capture_native_f8_graph_windows import read
from native_f8_inputs import graph_manifest_info
from discover_native_f8_crossings import SCHEMA, sha_file
from build_native_f8_pair_evidence import pair_identity

def decode_polyline6(encoded:str)->list[tuple[float,float]]:
    """Decode a Valhalla precision-6 leg shape as (longitude, latitude)."""
    result=[];lat=lon=0;i=0
    while i<len(encoded):
        delta=[]
        for _ in range(2):
            shift=value=0
            while True:
                if i>=len(encoded):raise ValueError('Truncated Valhalla polyline6')
                piece=ord(encoded[i])-63;i+=1
                if piece<0 or piece>63 or shift>35:
                    raise ValueError('Invalid Valhalla polyline6')
                value|=(piece&31)<<shift
                if piece<32:break
                shift+=5
            delta.append((value>>1)^-(value&1))
        lat+=delta[0];lon+=delta[1]
        if abs(lat)>90_000_000 or abs(lon)>180_000_000:
            raise ValueError('Polyline6 coordinate out of bounds')
        result.append((lon/1_000_000,lat/1_000_000))
    return result


MODES={'motorcycle','auto'}
DIRECTIONS={'from-to','to-from'}
ARRIVAL_TOLERANCE_METERS=25.0
PROBE_LIMIT=32


def distance(first:dict,second:dict)->float:
    lat1,lon1,lat2,lon2=map(math.radians,(first['lat'],first['lng'],second['lat'],second['lng']))
    a=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 12742017.6*math.asin(min(1,math.sqrt(max(0,a))))




def verify_retained_graph_identity(pair:dict,from_graph:dict,to_graph:dict)->None:
    """Never prove a route on archives unrelated to the proposal/pair fingerprints."""
    pair_identity(pair)
    for side,graph in (('from',from_graph),('to',to_graph)):
        if not isinstance(graph,dict):
            raise ValueError(f'{side}: no retained graph identity')
        for member,own in (('RegionId','regionId'),
                           ('PackageVersion','packageVersion'),
                           ('GraphFingerprint','graphFingerprint')):
            if graph.get(own)!=pair[side+member]:
                raise ValueError(f'{side}: stale graph identity {member}')
        if not isinstance(graph.get('primaryGeofabrikId'),str) or not graph['primaryGeofabrikId']:
            raise ValueError(f'{side}: missing primary Geofabrik source identity')
    if (from_graph['primaryGeofabrikId']!=pair.get('toBoundarySourceId')
            or to_graph['primaryGeofabrikId']!=pair.get('fromBoundarySourceId')):
        raise ValueError('Retained graph source IDs mismatch pair neighbor identities')


def eligible_manifest(pair:dict, manifest:dict, direction:str,base:Path)->Path:
    pair_identity(pair)
    if manifest.get('schema')!=SCHEMA or manifest.get('version')!=1:
        raise ValueError('Unsupported native GPS proposal catalog')
    for fld in ('pairId','fromGraphFingerprint','toGraphFingerprint','fromBoundaryFingerprint','toBoundaryFingerprint'):
        if manifest.get(fld)!=pair.get(fld):raise ValueError(f'Stale GPS source: {fld}')
    if manifest.get('publicationState')!='BLOCKED' or manifest.get('androidF8ScannerParity')!='NOT_VERIFIED':
        raise ValueError('Cannot probe a purported verified sidecar as native evidence')
    info=(manifest.get('files') or {}).get(direction+'.jsonl.gz')
    if not isinstance(info,dict) or not isinstance(info.get('records'),int) or info['records']<0:
        raise ValueError('Missing native directed GPS catalog or counts')
    file=(base/(direction+'.jsonl.gz')).resolve()
    if file.parent!=base.resolve() or not file.is_file():raise ValueError('Missing native GPS catalog')
    if sha_file(file)!=info.get('sha256'):raise ValueError('GPS proposal file hash mismatch')
    return file


def proposal_order(file:Path,start:dict,end:dict,max_probes:int,
                   expected_direction:str|None=None)->tuple[list[dict],int]:
    """Only bound the *probe*, never the retained source enumeration."""
    if not 1<=max_probes<=PROBE_LIMIT:raise ValueError('Probe budget out of range')
    total=0
    # Each score is an *ordering heuristic*, not proof that all untested trips
    # are slower. Broad geographic diversity prevents one known road dominating.
    nearest=[]
    with gzip.open(file,'rt',encoding='utf-8') as input:
        for line in input:
            item=json.loads(line)
            if expected_direction is not None and item.get('direction')!=expected_direction:
                raise ValueError('Native GPS proposal direction is inconsistent')
            gps=item['coordinate']
            val=distance(start,gps)+distance(gps,end)
            if not math.isfinite(val):raise ValueError('Nonfinite GPS proposal lower-bound')
            nearest.append((val,item['id'],item))
            total+=1
    if len({x[1] for x in nearest})!=total:raise ValueError('Duplicate native proposal ID')
    heap=heapq.nsmallest(min(total,max(100,max_probes*200)),nearest)
    chosen=[];cells={}
    for score,_,item in heap:
        c=item['coordinate']
        cell=(math.floor(c['lat']/0.015),math.floor(c['lng']/0.015))
        if cells.get(cell,0)>=2:continue
        cells[cell]=cells.get(cell,0)+1
        chosen.append(item)
        if len(chosen)==max_probes:break
    return chosen,total


def service_payload(stdout:str)->dict:
    """Reject extra data except the known installed launcher INFO tail."""
    data=stdout.lstrip()
    obj,pos=json.JSONDecoder().raw_decode(data)
    suffix=data[pos:].strip()
    if suffix and not all(line.startswith('[INFO] Running ') for line in suffix.splitlines()):
        raise ValueError('Unexpected trailing text after Valhalla JSON')
    if not isinstance(obj,dict):raise ValueError('Valhalla response must be an object')
    return obj


def route(config:Path,start:dict,end:dict,mode:str,timeout:int=45)->dict:
    req={'locations':[{'lat':start['lat'],'lon':start['lng']},
                      {'lat':end['lat'],'lon':end['lng']}],
         'costing':mode,'units':'kilometers',
         'directions_options':{'units':'kilometers'}}
    run=subprocess.run(['valhalla_service',str(config),'route',json.dumps(req,separators=(',',':'))],
                       capture_output=True,text=True,timeout=timeout,check=False)
    if run.returncode:
        return {'status':'FAILED','reason':(run.stderr.strip() or run.stdout.strip())[-450:]}
    try:
        response=service_payload(run.stdout)
        trip=response['trip']
        if trip.get('status',0)!=0:raise ValueError(f"Trip status {trip.get('status')}")
        legs=trip['legs']
        if len(legs)!=1:raise ValueError('Expected one complete graph-local leg')
        shape=decode_polyline6(legs[0]['shape'])
        if len(shape)<2:raise ValueError('Valhalla returned short geometry')
        start_actual={'lat':shape[0][1],'lng':shape[0][0]}
        end_actual={'lat':shape[-1][1],'lng':shape[-1][0]}
        summary=trip['summary']
        seconds=float(summary['time']); km=float(summary['length'])
        if not(math.isfinite(seconds) and seconds>=0 and math.isfinite(km) and km>=0):
            raise ValueError('Invalid trip metrics')
        return {'status':'SUCCEEDED','startActual':start_actual,'endActual':end_actual,
                'startOffsetMeters':round(distance(start,start_actual),2),
                'endOffsetMeters':round(distance(end,end_actual),2),
                'durationSeconds':seconds,'distanceKm':km,
                'encodedShape':legs[0]['shape']}
    except (KeyError,IndexError,TypeError,ValueError) as exc:
        return {'status':'INCONCLUSIVE','reason':str(exc)}


def actual_edge(config:Path,shape:str,mode:str,position:str)->int|None:
    req={'encoded_polyline':shape,'costing':mode,'shape_match':'edge_walk',
         'filters':{'attributes':['edge.id','edge.way_id'],'action':'include'}}
    try:
        run=subprocess.run(['valhalla_service',str(config),'trace_attributes',
                           json.dumps(req,separators=(',',':'))],capture_output=True,
                           text=True,timeout=45,check=False)
        if run.returncode:return None
        edges=service_payload(run.stdout).get('edges',[])
        row=edges[0 if position=='START' else -1]
        graph_id=row.get('id')
        return int(graph_id) if graph_id is not None and int(graph_id)>0 else None
    except (ValueError,TypeError,IndexError,KeyError,subprocess.TimeoutExpired):
        return None


def check_one(candidate:dict,config_a:Path,config_b:Path,
              start:dict,end:dict,mode:str,
              route_fn=route,trace_fn=actual_edge)->dict:
    gps=candidate['coordinate']
    base={'candidateId':candidate['id'],'receiverGraphId':candidate['receiverGraphId'],
          'mode':mode,'coordinate':gps}
    try:
        first=route_fn(config_a,start,gps,mode)
        if first['status']!='SUCCEEDED':return {**base,'status':'UNPROVEN','firstLeg':first}
        if first['startOffsetMeters']>ARRIVAL_TOLERANCE_METERS or first['endOffsetMeters']>ARRIVAL_TOLERANCE_METERS:
            return {**base,'status':'UNPROVEN','reason':'First graph leg does not reach candidate exactly','firstLeg':first}
        normalized=first['endActual']
        second=route_fn(config_b,normalized,end,mode)
        if second['status']!='SUCCEEDED':return {**base,'status':'UNPROVEN','firstLeg':first,'secondLeg':second}
        handoff_gap=distance(normalized,second['startActual'])
        if (second['startOffsetMeters']>ARRIVAL_TOLERANCE_METERS or
                second['endOffsetMeters']>ARRIVAL_TOLERANCE_METERS or
                handoff_gap>ARRIVAL_TOLERANCE_METERS):
            return {**base,'status':'UNPROVEN','reason':'Graph B snapped away or destination not reached',
                    'handoffGapMeters':round(handoff_gap,2),'firstLeg':first,'secondLeg':second}
        actual=trace_fn(config_b,second['encodedShape'],mode,'START')
        exact=actual==candidate['receiverGraphId']
        return {**base,'status':'VALIDATED_FOR_THIS_JOURNEY' if exact else 'UNPROVEN',
                'receiverTraceGraphId':actual,'receiverEdgeMatches':exact,
                'handoffGapMeters':round(handoff_gap,2),
                'durationSeconds':first['durationSeconds']+second['durationSeconds'],
                'distanceKm':first['distanceKm']+second['distanceKm'],
                'firstLeg':first,'secondLeg':second,
                'reason':None if exact else 'Receiver graph edge mismatch or trace unavailable'}
    except (OSError,subprocess.TimeoutExpired,ValueError) as exc:
        return {**base,'status':'INCONCLUSIVE','reason':str(exc)[:500]}


def inspect(pair:dict,manifest:dict,base:Path,config_a:Path,config_b:Path,
            start:dict,end:dict,mode:str,direction:str,max_probes:int,
            route_fn=route,trace_fn=actual_edge,
            on_progress:Callable[[int,int,dict],None]|None=None)->dict:
    if mode not in MODES or direction not in DIRECTIONS:raise ValueError('Unsupported mode/direction')
    file=eligible_manifest(pair,manifest,direction,base)
    chosen,total=proposal_order(file,start,end,max_probes,direction)
    if total!=manifest['files'][direction+'.jsonl.gz']['records']:
        raise ValueError('Native proposal count mismatch; incomplete source stream')
    results=[]
    for index, item in enumerate(chosen):
        outcome=check_one(item,config_a,config_b,start,end,mode,route_fn,trace_fn)
        results.append(outcome)
        if on_progress is not None:
            on_progress(index+1,len(chosen),outcome)
    successes=[r for r in results if r['status']=='VALIDATED_FOR_THIS_JOURNEY']
    return {'schema':'roadpilot.native-f8-journey-probe','version':1,
            'pairId':pair['pairId'],'direction':direction,'mode':mode,
            'fromGraphFingerprint':pair['fromGraphFingerprint'],
            'toGraphFingerprint':pair['toGraphFingerprint'],
            'fromBoundaryFingerprint':pair['fromBoundaryFingerprint'],
            'toBoundaryFingerprint':pair['toBoundaryFingerprint'],
            'start':start,'destination':end,
            'probesAttempted':len(results),'totalNativeReceiverProposals':total,
            'remainingUnprobed':total-len(results),
            'successfulJourneyProbes':len(successes),'results':results,
            'bestOfProbedOnly':{
                style:(min(successes,key=lambda r:(r['durationSeconds'] if style=='FASTER' else r['distanceKm'],r['candidateId']))['candidateId']
                       if successes else None)
                for style in ('FASTER','SHORTER')},
            'completeness':'INCOMPLETE_BOUNDED_JOURNEY_PROBES',
            'androidF8Parity':'NOT_VERIFIED',
            'productionConnectivity':'BLOCKED'}


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pair-manifest',required=True,type=Path)
    p.add_argument('--proposal-dir',required=True,type=Path)
    p.add_argument('--from-manifest',required=True,type=Path)
    p.add_argument('--to-manifest',required=True,type=Path)
    p.add_argument('--direction',choices=sorted(DIRECTIONS),required=True)
    p.add_argument('--mode',choices=sorted(MODES),required=True)
    for f in ('start-lat','start-lng','end-lat','end-lng'):
        p.add_argument('--'+f,required=True,type=float)
    p.add_argument('--max-probes',type=int,default=8)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    pair=read(args.pair_manifest)
    manifest=read(args.proposal_dir/'manifest.json')
    start={'lat':args.start_lat,'lng':args.start_lng}
    end={'lat':args.end_lat,'lng':args.end_lng}
    for pos in (start,end):
        if not (-90<=pos['lat']<=90 and -180<=pos['lng']<=180 and all(math.isfinite(x) for x in pos.values())):
            p.error('Invalid start/end coordinate')
    with tempfile.TemporaryDirectory(prefix='native-f8-probe-') as temp:
        root=Path(temp)
        to_primary=read(args.to_manifest)['source']['primaryGeofabrikId']
        from_primary=read(args.from_manifest)['source']['primaryGeofabrikId']
        identity_a,config_a=graph_manifest_info(args.from_manifest,pair['fromRegionId'],
                                               to_primary,pair['fromBoundaryFingerprint'],root,'from')
        identity_b,config_b=graph_manifest_info(args.to_manifest,pair['toRegionId'],
                                               from_primary,pair['toBoundaryFingerprint'],root,'to')
        verify_retained_graph_identity(pair,identity_a,identity_b)
        if args.direction=='to-from':config_a,config_b=config_b,config_a
        result=inspect(pair,manifest,args.proposal_dir,config_a,config_b,
                       start,end,args.mode,args.direction,args.max_probes)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():p.error('Output exists; refusing to overwrite prior evidence')
    with tempfile.NamedTemporaryFile('w',dir=args.output.parent,prefix='.native-f8-proof-',
                                     suffix='.json',delete=False) as f:
        temp_file=Path(f.name)
        json.dump(result,f,indent=2,allow_nan=False)
        f.write('\n')
    try:
        # Exclusive hard-link creation fails if another producer created the
        # output between the earlier exists check and this point.
        os.link(temp_file,args.output)
    finally:
        temp_file.unlink(missing_ok=True)
    print('F8 journey probe:',result['successfulJourneyProbes'],'validated among',
          result['probesAttempted'],'sampled of',result['totalNativeReceiverProposals'],
          'source proposals; other alternatives UNPROBED, parity NOT_VERIFIED.')
    return 0

if __name__=='__main__':raise SystemExit(main())
