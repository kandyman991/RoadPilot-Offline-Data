#!/usr/bin/env python3
"""Opt-in native F8 workspace commands for Graph Studio, with honest evidence gates.

The UI and future AI scripts invoke the SAME engine. No graph rebuilding,
OSM substitute, publication, route-optimality claim or Android parity shortcut.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from build_connectivity_pair_manifest import build_pair
from build_native_f8_pair_evidence import source_scans, pair_identity
from capture_native_f8_graph_windows import read
from discover_native_f8_crossings import generate
from probe_native_f8_journey import eligible_manifest, inspect, verify_retained_graph_identity
from native_f8_inputs import graph_manifest_info


TOOL_ROOT = Path(__file__).resolve().parent


def emit(message: str) -> None:
    print('F8 | ' + message, flush=True)


def pair_workspace(root: Path, pair: dict) -> Path:
    # Per immutable graph/boundary identity; old evidence stays untouched.
    name = (pair['fromGraphFingerprint'][7:16] + '-' + pair['toGraphFingerprint'][7:16]
            + '-' + pair['fromBoundaryFingerprint'][7:13]
            + '-' + pair['toBoundaryFingerprint'][7:13])
    return root / 'f8-native' / pair['pairId'] / name


def valid_existing_evidence(pair: dict, directory: Path) -> bool:
    manifest_file = directory / 'manifest.json'
    if not manifest_file.is_file():
        return False
    doc = read(manifest_file)
    for direction in ('from-to', 'to-from'):
        eligible_manifest(pair, doc, direction, directory)
    return True


def retained_sources(root: Path, pair: dict) -> tuple[Path, Path, Path] | None:
    """Only reuse a scan with *matching* declared native scanner and graph IDs.

    Actual source bindings are checked again with source_scans() before creating
    results, never inferred from adjacent filenames or an old successful route.
    """
    import build_native_f8_pair_evidence as evidence
    base = root / 'diagnostics'
    if not base.is_dir():
        return None
    for summary in sorted(base.glob('*/native-full-summary.json')):
        try:
            data = read(summary)
            if data.get('schema') != evidence.SUMMARY_SCHEMA or data.get('pairId') != pair['pairId']:
                continue
            identities = data.get('graphs') or {}
            if any((identities.get(pair[side+'RegionId']) or {}).get('fingerprint') != pair[side+'GraphFingerprint']
                   for side in ('from','to')):
                continue
            filenames = []
            for side in ('from','to'):
                file = summary.parent / (pair[side+'RegionId'] + '-native-full.json')
                if not file.is_file():
                    break
                filenames.append(file)
            if len(filenames) == 2:
                return filenames[0], filenames[1], summary
        except (ValueError, OSError, TypeError):
            continue
    return None


def scanner_binary() -> Path | None:
    choices = []
    if os.environ.get('ROADPILOT_F8_SCANNER'):
        choices.append(Path(os.environ['ROADPILOT_F8_SCANNER']))
    choices.append(TOOL_ROOT/'native-f8-edge-scan'/'native_f8_edge_scan')
    choices.append(Path.home()/'valhalla-3.6.3-dev'/'exporter-build-fixed'/'native_f8_edge_scan')
    for candidate in choices:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def pair_status(root: Path, pair: dict) -> dict:
    home = pair_workspace(root, pair)
    source = retained_sources(root, pair)
    has_capture = (home/'native-capture.json').is_file()
    proposal_dir = home/'gps-proposals'
    verified = False
    error = None
    try:
        verified = valid_existing_evidence(pair, proposal_dir)
    except (ValueError, OSError, KeyError) as exc:
        error = str(exc)
    counts = None
    if verified:
        counts = read(proposal_dir/'manifest.json').get('counts')
    reports = []
    if (home/'journey-probes').is_dir():
        for file in sorted((home/'journey-probes').glob('*.json'), reverse=True)[:8]:
            try:
                report = read(file)
                if report.get('pairId') != pair['pairId']:
                    continue
                points = [dict(coordinate=row.get('coordinate'), graphId=row.get('receiverGraphId'),
                               durationSeconds=row.get('durationSeconds'), distanceKm=row.get('distanceKm'))
                          for row in report.get('results',[])[:32]
                          if isinstance(row,dict) and row.get('status')=='VALIDATED_FOR_THIS_JOURNEY']
                reports.append({'mode':report.get('mode'),'direction':report.get('direction'),
                                'sampledHandoffs':points,
                                'attempted':report.get('probesAttempted'),
                                'validated':report.get('successfulJourneyProbes'),
                                'unprobed':report.get('remainingUnprobed'),
                                'bestOfProbedOnly':report.get('bestOfProbedOnly'),
                                'file':str(file)})
            except (OSError,ValueError,TypeError):
                continue
    return {
        'pairId':pair['pairId'], 'fromVersion':pair['fromPackageVersion'],
        'toVersion':pair['toPackageVersion'], 'fromGraphFingerprint':pair['fromGraphFingerprint'],
        'toGraphFingerprint':pair['toGraphFingerprint'],
        'source':('RETAINED_NATIVE_SCAN' if source else
                  'LOCAL_NATIVE_CAPTURE' if has_capture else
                  'FRESH_NATIVE_SCAN_REQUIRED'),
        'nativeScannerAvailable':scanner_binary() is not None,
        'proposalsReady':verified,
        'proposalError':error,
        'counts':counts,
        'diagnosticDirectory':str(home),
        'recentProbes':reports,
        'androidParity':'NOT_VERIFIED','productionPublication':'BLOCKED',
    }


def stream_process(args: list[str]) -> None:
    emit('Starting: '+Path(args[1]).name)
    proc = subprocess.Popen([sys.executable, *args], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line.rstrip(),flush=True)
    status = proc.wait()
    if status:
        raise ValueError(f'Native F8 step failed (exit code {status}); no production result published')


def save_pair(path: Path, pair: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if read(path) != pair:
            raise ValueError('Retained pair manifest conflicts with current graph identities')
        return
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,
                                      prefix='.native-f8-pair-',delete=False) as handle:
        temporary=Path(handle.name)
        json.dump(pair,handle,indent=2)
        handle.write('\n')
    try:
        try:
            os.link(temporary,path)
        except FileExistsError:
            if read(path) != pair:
                raise ValueError('Concurrent pair identity mismatch; original evidence preserved')
    finally:
        temporary.unlink(missing_ok=True)


def discovery(root: Path, pair: dict, from_manifest: Path, to_manifest: Path) -> dict:
    home = pair_workspace(root,pair)
    home.mkdir(parents=True,exist_ok=True)
    save_pair(home/'pair.json',pair)
    proposals = home/'gps-proposals'
    if valid_existing_evidence(pair,proposals):
        emit('Existing exact-fingerprint native GPS proposals reused. No rediscovery.')
        return pair_status(root,pair)
    if proposals.exists():
        raise ValueError('Existing GPS catalog is incomplete or stale; refusing to overwrite evidence')
    sources = retained_sources(root,pair)
    if sources:
        emit('Reusing retained native edge scans, no expensive new scan')
        a,b,summary=sources
        src_a,src_b,provenance=source_scans(pair,from_scan=read(a),to_scan=read(b),scan_summary=read(summary))
    else:
        capture=home/'native-capture.json'
        if not capture.exists():
            scanner=scanner_binary()
            if scanner is None:
                raise ValueError('No native scanner binary: install/build matching Valhalla C++ native_f8_edge_scan before first discovery')
            from_buffer=root/'work'/pair['fromRegionId']/'build'/'buffer.geojson'
            to_buffer=root/'work'/pair['toRegionId']/'build'/'buffer.geojson'
            if not from_buffer.is_file() or not to_buffer.is_file():
                raise ValueError('Missing retained region buffer.geojson; cannot prove native scan window coverage')
            emit('Scanning complete overlap on both immutable native graphs (may require thousands of windows)…')
            stream_process([str(TOOL_ROOT/'capture_native_f8_graph_windows.py'),
                '--pair-manifest',str(home/'pair.json'),
                '--from-manifest',str(from_manifest),'--to-manifest',str(to_manifest),
                '--from-buffer',str(from_buffer),'--to-buffer',str(to_buffer),
                '--scanner-binary',str(scanner),'--output',str(capture)])
        emit('Validating captured native edge windows and graph identities')
        src_a,src_b,provenance=source_scans(pair,capture=read(capture))
    emit('Generating both complete retained-source directed GPS proposal ledgers')
    result=generate(pair,src_a,src_b,proposals,provenance,
        on_progress=lambda direction,count,total: emit(f'Enumerating {direction}: {count:,} / {total:,} native directed edges'))
    emit('Native proposals: '+json.dumps(result['counts'])+'; Android F8 parity NOT_VERIFIED')
    return pair_status(root,pair)


def probe(root: Path, pair: dict, from_manifest: Path, to_manifest: Path,
          direction: str, mode: str, start: dict, end: dict, max_probes: int) -> dict:
    home = pair_workspace(root,pair)
    proposals = home/'gps-proposals'
    if not valid_existing_evidence(pair,proposals):
        raise ValueError('Generate native GPS proposals for these exact graph versions first')
    if direction not in ('from-to','to-from') or mode not in ('motorcycle','auto'):
        raise ValueError('Invalid mode or direction')
    if not 1 <= max_probes <= 16:
        raise ValueError('Only bounded, explicitly incomplete proofs (1–16) are enabled')
    with tempfile.TemporaryDirectory(prefix='graph-studio-f8-proof-') as temp:
        tempdir=Path(temp)
        manifest_a=read(from_manifest)
        manifest_b=read(to_manifest)
        source_a=manifest_a['source']['primaryGeofabrikId']
        source_b=manifest_b['source']['primaryGeofabrikId']
        emit('Verifying actual archive SHA-256 and pair fingerprint bindings')
        identity_a, config_a = graph_manifest_info(from_manifest,pair['fromRegionId'],source_b,
                                                    pair['fromBoundaryFingerprint'],tempdir,'from')
        identity_b, config_b = graph_manifest_info(to_manifest,pair['toRegionId'],source_a,
                                                    pair['toBoundaryFingerprint'],tempdir,'to')
        verify_retained_graph_identity(pair,identity_a,identity_b)
        if direction=='to-from':
            config_a,config_b=config_b,config_a
        emit(f'Routing up to {max_probes} candidates on {direction}, {mode} (does not establish optimality)')
        doc=inspect(pair,read(proposals/'manifest.json'),proposals,config_a,config_b,
                    start,end,mode,direction,max_probes,
                    on_progress=lambda index,total,outcome: emit(
                        f"Valhalla proof {index}/{total}: {outcome['status']} (all untested alternatives retained)"))
    folder=home/'journey-probes'
    folder.mkdir(parents=True,exist_ok=True)
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path=folder/f'{timestamp}-{direction}-{mode}.json'
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=folder,
                                      prefix='.native-f8-report-',delete=False) as output:
        temporary=Path(output.name)
        json.dump(doc,output,indent=2,allow_nan=False)
        output.write('\n')
    try:
        os.link(temporary,path)  # Never publish a partially written proof file.
    finally:
        temporary.unlink(missing_ok=True)
    emit(f"Proof result: {doc['successfulJourneyProbes']}/{doc['probesAttempted']} sampled, "
         f"{doc['remainingUnprobed']} unprobed; no publication")
    return pair_status(root,pair)


def run(argv: list[str] | None = None) -> dict:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('status','discover','probe'))
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--from-manifest',required=True,type=Path)
    parser.add_argument('--to-manifest',required=True,type=Path)
    parser.add_argument('--direction',choices=('from-to','to-from'))
    parser.add_argument('--mode',choices=('auto','motorcycle'))
    parser.add_argument('--max-probes',type=int,default=6)
    for field in ('start-lat','start-lng','end-lat','end-lng'):
        parser.add_argument('--'+field,type=float)
    args=parser.parse_args(argv)
    root=args.workspace.resolve()
    if not root.is_dir():
        raise ValueError('Graph Studio workspace not found')
    for manifest in (args.from_manifest,args.to_manifest):
        expected=root/'builds'
        if not manifest.resolve().is_relative_to(expected.resolve()) or manifest.parent.resolve().parent != expected.resolve():
            raise ValueError('Routing manifest must be a direct retained Graph Studio regional build')
    pair=build_pair(args.from_manifest,args.to_manifest)
    pair_identity(pair)  # Reject malicious or non-fingerprint-bound path components.
    if args.operation=='status':
        return pair_status(root,pair)
    if args.operation=='discover':
        return discovery(root,pair,args.from_manifest,args.to_manifest)
    if not args.direction or not args.mode:
        raise ValueError('Direction and mode are required for bounded F8 proof')
    fields=(args.start_lat,args.start_lng,args.end_lat,args.end_lng)
    import math
    if any(v is None or not math.isfinite(v) for v in fields):
        raise ValueError('Four finite start/destination coordinates required')
    start={'lat':args.start_lat,'lng':args.start_lng}
    end={'lat':args.end_lat,'lng':args.end_lng}
    for c in (start,end):
        if not -90<=c['lat']<=90 or not -180<=c['lng']<=180:
            raise ValueError('Journey coordinate out of range')
    return probe(root,pair,args.from_manifest,args.to_manifest,
                 args.direction,args.mode,start,end,args.max_probes)


def main() -> int:
    try:
        result=run()
        print('F8_RESULT '+json.dumps(result,separators=(',',':')),flush=True)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('F8_ERROR '+str(exc),flush=True)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
