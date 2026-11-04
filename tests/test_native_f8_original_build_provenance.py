"""An unreviewed native C++ source or CMake change invalidates native proof evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NativeRouteBuildProvenanceTests(unittest.TestCase):
    def test_source_and_build_recipe_match_reviewed_legion_artifact(self):
        data=json.loads((ROOT/'docs/F8_PR117_ORIGINAL_NATIVE_BUILD_PROVENANCE.json').read_text())
        self.assertEqual(data['schema'],'roadpilot.f8-original-route-native-build-provenance')
        self.assertEqual(data['version'],1)
        self.assertEqual(data['valhallaVersion'],'3.6.3')
        for file_key,digest_key in (
            ('sourcePath','sourceSha256'),
            ('cmakePath','cmakeSha256')):
            path=ROOT/data[file_key]
            self.assertTrue(path.is_file())
            self.assertEqual(data[digest_key],
                             'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue(re.fullmatch(r'sha256:[0-9a-f]{64}',
                                      data['reviewedNativeExecutableSha256']))
        self.assertIn('native_f8_route_edges',data['buildCommand'])
        self.assertEqual(data['globalPhysicalRoadCompleteness'],'NOT_VERIFIED')
        self.assertEqual(data['androidJNIDeviceParity'],'NOT_VERIFIED')
        self.assertEqual(data['productionPublication'],'BLOCKED')
        self.assertEqual(data['sampleReportsWithSHA256SUMS'],8)


if __name__ == '__main__':
    unittest.main()
