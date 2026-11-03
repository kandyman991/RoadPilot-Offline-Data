#!/usr/bin/env python3
"""Compatibility wrapper for an archived historical validator (D-016).

The unchanged implementation was moved to
tools/legacy_archive/connectivity/validate_region_connector_matrix.py. This file keeps the original
command-line entry point (flags, output, exit codes) so existing callers and the
installed packages keep working. It adds no behaviour. The schema family it checks
is historical and is not evidence of native F8 completeness; see
docs/RETIRED_ARCHITECTURE.md.
"""
import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "legacy_archive" / "connectivity" / "validate_region_connector_matrix.py"

if __name__ == "__main__":
    # sys.argv[0] stays this file, so argparse usage text is unchanged.
    runpy.run_path(str(TARGET), run_name="__main__")
    sys.exit(0)
