#!/usr/bin/env python3
"""Stage native graph-directed physical peers; DO NOT publish these as F8 handoffs.

This stage only correlates exact directed physical way/coordinate evidence from
independent native GraphReader scans. Physical peers are NOT route proofs, and
unmatched edges are explicitly retained for future geometric/Valhalla discovery.
No road name, heading, direction, road class, access or distance is an eligibility
filter. This is a checkpointable data foundation, not a claim of F8 parity.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from capture_native_f8_graph_windows import PORT, SCHEMA as CAPTURE_SCHEMA, read

EVIDENCE_SCHEMA = 'roadpilot.native-f8-physical-pair-evidence'
SUMMARY_SCHEMA = 'roadpilot.native-valhalla-overlap-diagnostics'
SHA256 = re.compile(r'^sha256:[0-9a-f]{64}$')


def pair_identity(pair: dict) -> None:
    if pair.get('schema') != 'roadpilot.cross-region-connectivity' or pair.get('version') != 1:
        raise ValueError('Source pair must use cross-region-connectivity v1')
    if pair.get('validationState') != 'UNPROVEN':
        raise ValueError('Physical-only pairing requires UNPROVEN source identity')
    if pair.get('pairId') != f"{pair.get('fromRegionId')}__{pair.get('toRegionId')}":
        raise ValueError('Invalid region pair identity')
    for field in ('fromGraphFingerprint', 'toGraphFingerprint',
                  'fromBoundaryFingerprint', 'toBoundaryFingerprint'):
        if not SHA256.fullmatch(str(pair.get(field))):
            raise ValueError(f'Invalid/missing {field}')
    if pair['fromGraphFingerprint'] == pair['toGraphFingerprint']:
        raise ValueError('Independent regions cannot share an assumed graph identity')


def source_scans(pair: dict, *, capture: dict | None = None,
                 from_scan: dict | None = None, to_scan: dict | None = None,
                 scan_summary: dict | None = None) -> tuple[dict, dict, dict]:
    """Bind direct native port capture or preexisting read-only Legion scan evidence."""
    pair_identity(pair)
    if capture is not None:
        if any(x is not None for x in (from_scan, to_scan, scan_summary)):
            raise ValueError('Use either a native capture or retained scan+summary, not both')
        if capture.get('schema') != CAPTURE_SCHEMA or capture.get('scanner') != PORT:
            raise ValueError('Only uncapped native GraphReader capture is accepted')
        if capture.get('nativeF8ReferenceCaptured') is not False or capture.get('f8GraphEdgeParity') != 'NOT_VERIFIED':
            raise ValueError('Native port may not impersonate Android F8 parity')
        if capture.get('pairId') != pair['pairId']:
            raise ValueError('Native capture pairId mismatch')
        for side in ('from', 'to'):
            graph = capture.get(side+'Graph') or {}
            if (graph.get('graphFingerprint') != pair[side+'GraphFingerprint']
                    or graph.get('regionId') != pair[side+'RegionId']
                    or graph.get('packageVersion') != pair[side+'PackageVersion']):
                raise ValueError(f'Stale {side} native graph fingerprint/version')
            if capture.get(side+'BoundaryFingerprint') != pair[side+'BoundaryFingerprint']:
                raise ValueError(f'Stale {side} native boundary')
        scans = capture.get('scans') or {}
        a, b = scans.get('from'), scans.get('to')
        return validated_scan(a, 'from'), validated_scan(b, 'to'), {
            'source': 'FINGERPRINT_BOUND_NATIVE_CAPTURE',
            'sourceBindingLevel': 'CAPTURE_DECLARED_EXACT_GRAPH',
            'scannerBuild': capture.get('scannerBuild'),
        }
    if any(x is None for x in (from_scan, to_scan, scan_summary)):
        raise ValueError('Both retained scans AND matching native scan summary are required')
    if scan_summary.get('schema') != SUMMARY_SCHEMA or scan_summary.get('pairId') != pair['pairId']:
        raise ValueError('Retained native scan summary pair mismatch')
    if scan_summary.get('f8GraphEdgeParity') != 'NOT_VERIFIED' or scan_summary.get('nativeAndroidF8ReferenceCaptured') is not False:
        raise ValueError('Retained summary must not claim Android reference parity')
    graph_provenance = scan_summary.get('graphs') or {}
    observed_stats = scan_summary.get('stats') or {}
    for side, scan in (('from', from_scan), ('to', to_scan)):
        region = pair[side+'RegionId']
        evidence = graph_provenance.get(region) or {}
        if evidence.get('fingerprint') != pair[side+'GraphFingerprint']:
            raise ValueError(f'Stale {side} native scan graph fingerprint')
        stats = observed_stats.get(region) or {}
        if stats.get('uniqueDirectedEdges') != len(scan.get('edges', [])):
            raise ValueError(f'{side} native edge count inconsistent with summary')
        if stats.get('windowsTotal') != len(scan.get('windows', [])):
            raise ValueError(f'{side} native window count inconsistent with summary')
    return validated_scan(from_scan, 'from'), validated_scan(to_scan, 'to'), {
        'source': 'RETAINED_UNCAPPED_NATIVE_PORT_EVIDENCE',
        'sourceBindingLevel': 'SUMMARY_DECLARED_ONLY_COUNTS_CHECKED',
        'scannerBuild': {'binarySha256': scan_summary.get('binarySha256'),
                         'compiledValhallaVersion': scan_summary.get('version')},
    }


def validated_scan(scan: Any, side: str) -> dict:
    if not isinstance(scan, dict) or scan.get('complete') is not True:
        raise ValueError(f'{side}: native scan is incomplete')
    windows = scan.get('windows')
    edges = scan.get('edges')
    if not isinstance(windows, list) or not windows or not isinstance(edges, list):
        raise ValueError(f'{side}: missing native windows or edges')
    for window in windows:
        if (not isinstance(window, dict) or window.get('complete') is not True
                or window.get('truncated') is not False or window.get('maxResults') is not None
                or not isinstance(window.get('visitedTiles'), int) or window.get('visitedTiles') < 1):
            raise ValueError(f'{side}: source window missing, truncated or unscanned')
    ids: set[int] = set()
    for edge in edges:
        if not isinstance(edge, dict) or not isinstance(edge.get('graphId'), int) or isinstance(edge['graphId'], bool) or edge['graphId'] <= 0:
            raise ValueError(f'{side}: invalid directed graph ID')
        if edge['graphId'] in ids:
            raise ValueError(f'{side}: duplicate directed GraphId')
        ids.add(edge['graphId'])
        physical_key(edge)  # Validate physical geometry before any output.
    return scan


def physical_key(edge: dict) -> tuple[int, int, int, int, int]:
    """Conservative exact-6-decimal directed physical match, NOT a viability test."""
    way = edge.get('wayId')
    if not isinstance(way, int) or isinstance(way, bool) or way <= 0:
        raise ValueError('Native edge has no valid OSM way identity')
    nums = []
    for field, limit in (('lat', 90), ('lon', 180), ('innerLat', 90), ('innerLon', 180)):
        value = edge.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not (-limit <= value <= limit):
            raise ValueError(f'Native edge has invalid {field}')
        nums.append(round(value * 1000000))
    return way, *nums


def make_record(pair: dict, from_edge: dict, to_edge: dict) -> dict:
    identity = f"{pair['pairId']}|{pair['fromGraphFingerprint']}|{pair['toGraphFingerprint']}|{from_edge['graphId']}|{to_edge['graphId']}"
    return {
        'id': 'nf8peer-' + hashlib.sha256(identity.encode()).hexdigest()[:24],
        'physicalWayId': from_edge['wayId'],
        'matchingEvidence': 'SAME_WAY_DIRECTED_START_AND_INNER_6DP',
        'state': 'UNPROVEN', 'directionalValhallaProof': 'NOT_RUN',
        'fromEdge': from_edge, 'toEdge': to_edge,
    }


def produce(pair: dict, a: dict, b: dict, output: Path, provenance: dict) -> dict:
    """Write complete per-edge ledger to an atomic new directory, never publish runtime."""
    if output.exists():
        raise ValueError(f'Output already exists; cannot replace evidence: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    by_identity: dict[tuple, list[dict]] = defaultdict(list)
    for edge in b['edges']:
        by_identity[physical_key(edge)].append(edge)
    paired_a: set[int] = set()
    paired_b: set[int] = set()
    pairs = 0
    with tempfile.TemporaryDirectory(prefix='.native-f8-pairs-', dir=output.parent) as temp:
        staged = Path(temp) / 'results'
        staged.mkdir()
        peers = staged / 'physical-peers.jsonl'
        a_lost = staged / 'unpaired-from.jsonl'
        b_lost = staged / 'unpaired-to.jsonl'
        with peers.open('w', encoding='utf-8') as handle:
            for edge in sorted(a['edges'], key=lambda e: e['graphId']):
                for receiver in sorted(by_identity.get(physical_key(edge), []), key=lambda e: e['graphId']):
                    handle.write(json.dumps(make_record(pair, edge, receiver), separators=(',', ':'))+'\n')
                    pairs += 1
                    paired_a.add(edge['graphId'])
                    paired_b.add(receiver['graphId'])
        for filename, source, paired in ((a_lost, a['edges'], paired_a), (b_lost, b['edges'], paired_b)):
            with filename.open('w', encoding='utf-8') as handle:
                for edge in sorted(source, key=lambda e: e['graphId']):
                    if edge['graphId'] not in paired:
                        handle.write(json.dumps(edge, separators=(',', ':'))+'\n')
        def digest_file(file: Path) -> str:
            digest = hashlib.sha256()
            with file.open('rb') as source:
                for part in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(part)
            return 'sha256:' + digest.hexdigest()

        meta = {
            'schema': EVIDENCE_SCHEMA, 'version': 1,
            'pairId': pair['pairId'], 'fromGraphFingerprint': pair['fromGraphFingerprint'],
            'toGraphFingerprint': pair['toGraphFingerprint'],
            'fromBoundaryFingerprint': pair['fromBoundaryFingerprint'],
            'toBoundaryFingerprint': pair['toBoundaryFingerprint'],
            'scanner': PORT, 'provenance': provenance,
            'sourceWindowCoverage': 'NATIVE_GRAPH_SCAN_COMPLETE',
            'physicalMatchScope': 'EXACT_SAME_WAY_DIRECTED_COORDINATES_ONLY',
            'frontierCorrelations': 'NOT_VERIFIED',
            'valhallaLegsProven': 'NOT_RUN',
            'androidF8ReferenceMatched': 'NOT_VERIFIED',
            'routingOptimalityChecked': 'NOT_VERIFIED',
            'publicationState': 'BLOCKED',
            'counts': {
                'fromDirectedEdges': len(a['edges']), 'toDirectedEdges': len(b['edges']),
                'fromWindows': len(a['windows']), 'toWindows': len(b['windows']),
                'physicalPeerPairs': pairs,
                'fromEdgesWithPhysicalPeer': len(paired_a),
                'toEdgesWithPhysicalPeer': len(paired_b),
                'unpairedFromEdges': len(a['edges'])-len(paired_a),
                'unpairedToEdges': len(b['edges'])-len(paired_b),
            },
            'files': {f.name: digest_file(f) for f in (peers, a_lost, b_lost)},
            'knownGaps': [
                'Exact directed physical peer geometry is evidence, not a Valhalla-connected handoff.',
                'Differently encoded/resegmented roads remain in unpaired ledgers, not rejected.',
                'Nominal/buffer seam relevance and all other plausible nonmatching crossings are unverified.',
                'Neither mode/direction proof nor real Android JNI scanner parity has been run.',
                'Retained standalone side files have summary-declared graph hashes, not cryptographic scan-to-graph attestation.',
            ],
        }
        (staged / 'manifest.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf-8')
        os.rename(staged, output)  # one new directory; never overwrite old/verified artifacts
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair-manifest', required=True, type=Path)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--capture', type=Path, help='Native Graph Studio full pair capture')
    inputs.add_argument('--from-scan', type=Path, help='Preexisting native side scan (requires summary)')
    parser.add_argument('--to-scan', type=Path)
    parser.add_argument('--scan-summary', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    pair = read(args.pair_manifest)
    if args.capture:
        a,b,source=source_scans(pair,capture=read(args.capture))
    else:
        if not args.to_scan or not args.scan_summary:
            parser.error('--from-scan requires --to-scan and --scan-summary')
        a,b,source=source_scans(pair,from_scan=read(args.from_scan),
                                to_scan=read(args.to_scan),scan_summary=read(args.scan_summary))
    result=produce(pair,a,b,args.output_dir,source)
    print(f"{result['pairId']}: {result['counts']['physicalPeerPairs']} unproven directed physical peers; "
          f"{result['counts']['unpairedFromEdges']} / {result['counts']['unpairedToEdges']} unresolved edges. "
          'Valhalla/Android F8 parity NOT_VERIFIED; publication BLOCKED.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
