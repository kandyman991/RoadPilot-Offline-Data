#!/usr/bin/env python3
"""Enumerate exhaustive *native-edge GPS proposals* for cross-graph F8.

Android F8 proposes receiver-side GPS points then normalizes/validates with
independent graph-local Valhalla. Thus an OSM way match, graphId match, heading,
road class, or physical proximity is NEVER a precondition to become a proposal.
This is full scanner-source proposal enumeration, NOT complete handoff discovery.
Proof and actual JNI parity are separate, required steps before publication.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

from build_native_f8_pair_evidence import (
    EVIDENCE_SCHEMA, PORT, pair_identity, physical_key, source_scans,
)
from capture_native_f8_graph_windows import read

SCHEMA = 'roadpilot.native-f8-gps-crossing-proposals'
SIDES = (('from-to','to','from'), ('to-from','from','to'))


def validate_evidence(pair: dict, evidence: dict) -> None:
    if evidence.get('schema') != EVIDENCE_SCHEMA or evidence.get('version') != 1:
        raise ValueError('Unsupported native peer evidence')
    for field in ('pairId', 'fromGraphFingerprint', 'toGraphFingerprint',
                  'fromBoundaryFingerprint', 'toBoundaryFingerprint'):
        if evidence.get(field) != pair.get(field):
            raise ValueError(f'Stale peer evidence identity: {field}')
    if evidence.get('scanner') != PORT:
        raise ValueError('Physical peer inventory did not originate from native graph scan')
    if (evidence.get('publicationState') != 'BLOCKED' or
            evidence.get('androidF8ReferenceMatched') != 'NOT_VERIFIED'):
        raise ValueError('A purported verified runtime sidecar is not native scan evidence')


def candidate(pair: dict, direction: str, receiver: dict,
              physical_peers: list[int]) -> dict:
    """Propose receiver-side inner GPS, NOT an asserted handoff or legal edge."""
    coordinate = {'lat':receiver['innerLat'], 'lng':receiver['innerLon']}
    provenance = f"{pair['pairId']}|{pair['fromGraphFingerprint']}|{pair['toGraphFingerprint']}|{direction}|{receiver['graphId']}"
    return {
        'id':'nf8gps-'+hashlib.sha256(provenance.encode()).hexdigest()[:24],
        'direction':direction, 'receiverGraphId':receiver['graphId'],
        'receiverWayId':receiver['wayId'],
        'coordinate':coordinate,
        'receiverEdgeStart':{'lat':receiver['lat'], 'lng':receiver['lon']},
        'receiverForwardAccess':receiver['forwardAccess'],
        'receiverReverseAccess':receiver['reverseAccess'],
        'physicalPeerOriginGraphIds':physical_peers,
        'gpsProposalState':'UNPROVEN',
        'originGraphCorrelation':'NOT_RUN',
        'receiverGraphCorrelation':'NOT_RUN',
        'motorcycle':{'fromTo':'NOT_RUN','toFrom':'NOT_RUN'},
        'auto':{'fromTo':'NOT_RUN','toFrom':'NOT_RUN'},
    }


def sha_file(path:Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda:f.read(1024*1024),b''):
            digest.update(buf)
    return 'sha256:'+digest.hexdigest()


def generate(pair:dict, a:dict, b:dict, output:Path, provenance:dict,
             prior_evidence:dict|None=None) -> dict:
    pair_identity(pair)
    if output.exists():
        raise ValueError('Native crossing proposal output already exists; do not overwrite evidence')
    if prior_evidence is not None:validate_evidence(pair, prior_evidence)
    # Underlying source scans were checked for fingerprints, overlapping window
    # catalog alignment, edge ID uniqueness and typed access by source_scans().
    source={'from':a,'to':b}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.native-f8-gps-') as root:
        stage=Path(root)/'staged';stage.mkdir()
        files={}
        counts={}
        for direction,receiver_side,origin_side in SIDES:
            origin=source[origin_side]
            peers={}
            for edge in origin['edges']:
                peers.setdefault(physical_key(edge),[]).append(edge['graphId'])
            for ids in peers.values():ids.sort()
            target=stage/(direction+'.jsonl.gz')
            count=0;with_peer=0;all_receiver=set()
            with target.open('wb') as raw, gzip.GzipFile(
                    filename='', mode='wb', fileobj=raw, compresslevel=5, mtime=0) as compressed, \
                    io.TextIOWrapper(compressed, encoding='utf-8', newline='\n') as f:
                for edge in sorted(source[receiver_side]['edges'],key=lambda e:e['graphId']):
                    same=peers.get(physical_key(edge),[])
                    record=candidate(pair,direction,edge,same)
                    if record['receiverGraphId'] in all_receiver:
                        raise ValueError('Repeated receiver GraphId would suppress an alternative')
                    all_receiver.add(record['receiverGraphId'])
                    count+=1
                    if same:with_peer+=1
                    f.write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
            files[target.name]={'sha256':sha_file(target),'records':count}
            counts[direction]={'receiverDirectedEdges':count,
                               'exactPhysicalPeerEvidence':with_peer,
                               'noExactPhysicalPeer':count-with_peer}
        meta={
            'schema':SCHEMA,'version':1,'pairId':pair['pairId'],
            'fromGraphFingerprint':pair['fromGraphFingerprint'],
            'toGraphFingerprint':pair['toGraphFingerprint'],
            'fromBoundaryFingerprint':pair['fromBoundaryFingerprint'],
            'toBoundaryFingerprint':pair['toBoundaryFingerprint'],
            'scanner':PORT,'evidence':provenance,
            'proposalSourceCoverage':'ALL_RETAINED_DIRECTED_NATIVE_SCAN_EDGES',
            'scannerWindowCoverage':'SOURCE_REPORTED_COMPLETE_MATCHING_WINDOW_CATALOG',
            'completeGraphOverlapCoverage':'NOT_VERIFIED',
            'crossRegionRouteProof':'NOT_RUN',
            'androidF8ScannerParity':'NOT_VERIFIED',
            'routeAlternativeOptimality':'NOT_VERIFIED',
            'publicationState':'BLOCKED',
            'counts':counts,'files':files,
            'knownGaps':[
                'All eligible scanned receiver edges are included, even with no physical peer; GPS proposals alone are not crossings.',
                'Exact matched ways are supporting evidence, never an eligibility filter.',
                'Native scans have not been matched to actual Android F8 scanner or their full geometric overlap proven.',
                'Unproven Valhalla leg directions/modes and route-alternative optimality must not be inferred from candidate enumeration.',
            ],
        }
        (stage/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
        os.rename(stage,output)
    return meta


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pair-manifest',type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--capture',type=Path)
    group.add_argument('--from-scan',type=Path)
    p.add_argument('--to-scan',type=Path)
    p.add_argument('--scan-summary',type=Path)
    p.add_argument('--physical-evidence',type=Path,help='Optional existing native peer manifest for identity check')
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    pair=read(args.pair_manifest)
    if args.capture:
        a,b,provenance=source_scans(pair,capture=read(args.capture))
    else:
        if args.to_scan is None or args.scan_summary is None:
            p.error('--from-scan requires --to-scan and --scan-summary')
        a,b,provenance=source_scans(pair,from_scan=read(args.from_scan),
                                   to_scan=read(args.to_scan),scan_summary=read(args.scan_summary))
    prev=read(args.physical_evidence) if args.physical_evidence else None
    m=generate(pair,a,b,args.output_dir,provenance,prev)
    print(m['pairId'],m['counts'],'GPS proposals UNPROVEN; Android/Valhalla parity NOT_VERIFIED; publication BLOCKED.')
    return 0

if __name__=='__main__':raise SystemExit(main())
