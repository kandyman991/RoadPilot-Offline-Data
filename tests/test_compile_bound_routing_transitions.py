import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "compiler",
    ROOT / "tools" / "compile_bound_routing_transitions.py",
)
compiler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compiler)


class CompileBoundRoutingTransitionsTest(unittest.TestCase):
    def setUp(self):
        self.proofs = json.loads(
            (
                ROOT
                / "tests/fixtures/austria-oberbayern-proof-results.json"
            ).read_text()
        )

    def test_motorcycle_promotes_only_accepted_motorcycle_proofs(self):
        artifact = compiler.compile_artifact(self.proofs, "MOTORCYCLE")
        ids = [item["sourceProofId"] for item in artifact["transitions"]]
        self.assertEqual(2, len(ids))
        self.assertTrue(any("a12a93" in proof_id for proof_id in ids))
        self.assertFalse(any("rejected" in proof_id for proof_id in ids))
        self.assertEqual("MOTORCYCLE", artifact["bindingMode"])

    def test_car_is_compiled_independently(self):
        artifact = compiler.compile_artifact(self.proofs, "CAR")
        self.assertEqual(1, len(artifact["transitions"]))
        self.assertEqual(
            "xgc1-a12a93carproof000000001",
            artifact["transitions"][0]["sourceProofId"],
        )
        self.assertEqual("CAR", artifact["bindingMode"])


if __name__ == "__main__":
    unittest.main()
