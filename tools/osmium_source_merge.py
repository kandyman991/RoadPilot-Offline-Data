"""Merge overlapping Geofabrik snapshots into one normal (non-history) OSM PBF.

"osmium merge" only removes identical *versions*. Independently refreshed
country and thematic extracts can contain different versions of one ID, so
the resulting file is history-like and ordinary "osmium extract" fails
with "Node ID twice in input".

Pipe the merge through osmium time-filter at current time: that streaming
operation selects one current version per type/ID. It does not load the
whole Austria/DACH/Alps dataset in RAM and needs no extra giant PBF copy.
The buffered extract is still checked with osmium check-refs downstream.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def merge_current_osm_snapshot(inputs: list[Path], output: Path) -> None:
    if not inputs:
        raise ValueError("At least one OSM source is required")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".incomplete.osm.pbf")
    temporary.unlink(missing_ok=True)
    merge_cmd = ["osmium", "merge", *map(str, inputs), "-f", "pbf"]
    normalize_cmd = [
        "osmium", "time-filter", "-F", "pbf", "-",
        "-o", str(temporary),
    ]
    print("+", " ".join(merge_cmd), "|", " ".join(normalize_cmd), flush=True)
    merge_process = None
    try:
        merge_process = subprocess.Popen(merge_cmd, stdout=subprocess.PIPE)
        assert merge_process.stdout is not None
        try:
            result = subprocess.run(normalize_cmd, stdin=merge_process.stdout, check=False)
        finally:
            merge_process.stdout.close()
        merge_return = merge_process.wait()
        if merge_return != 0 or result.returncode != 0:
            raise RuntimeError(
                f"Geofabrik merge/current-snapshot normalization failed "
                f"(merge={merge_return}, time-filter={result.returncode})"
            )
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("Normalized OSM merge produced no data")
        os.replace(temporary, output)
        print("normalized OSM object versions: one current object per type/ID",
              flush=True)
    finally:
        if merge_process is not None and merge_process.poll() is None:
            merge_process.terminate()
            merge_process.wait()
        temporary.unlink(missing_ok=True)
