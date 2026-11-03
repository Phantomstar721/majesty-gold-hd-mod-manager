"""Exercise the final validator's actual placement branch with serialized proofs.

The rest of package admission is deliberately outside this focused fixture.
The branch is taken from production source, not a duplicated validation rule.
"""
import ast
from dataclasses import replace
import inspect
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from majesty_cam import compose
from majesty_cam.checked_placement import CheckedPlacement, encode, PRESENTED_FEATURE_TYPE, LEARNED_FEATURE_TYPE
from majesty_cam.descriptions import parse_descriptions
from test_placement_art import image

class FinalPlacementValidationTests(unittest.TestCase):
    def test_final_consumer_accepts_v2_v3_and_rejects_wrong_image_and_wire(self):
        tree = ast.parse(inspect.getsource(compose.validate_composed_package))
        branches = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                    and isinstance(n.test, ast.BoolOp)
                    and any(isinstance(x, ast.Attribute) and x.attr == "arrival_action" for x in ast.walk(n.test))]
        self.assertEqual(len(branches), 1, "Final placement consumer must remain covered")
        code = compile(ast.fix_missing_locations(ast.Module(body=[branches[0]], type_ignores=[])),
                       "<production final placement branch>", "exec")
        entry = image()
        record = parse_descriptions('<Majesty><Description type="Unit" Name="FixtureHero" ID="FH01"><Engine><ImageIDBase value="PRIV"/></Engine></Description></Majesty>').records[0]
        view = SimpleNamespace(resources=(SimpleNamespace(section=b"IMAG", key=b"PRIV", entry=entry),))
        base = CheckedPlacement("fixture", "Fixture", "FixtureHero", "FixtureCast", "FixtureRelease", "FixtureMove",
                                type=PRESENTED_FEATURE_TYPE, arrival_action="FixtureArrival")
        with tempfile.TemporaryDirectory() as tmp, patch("majesty_cam.scoped_descriptions.inventory_records", return_value={"actor": record}):
            proof = Path(tmp) / "placement.bin"
            for feature in (base, replace(base, type=LEARNED_FEATURE_TYPE, required_level=1),
                            replace(base, type=LEARNED_FEATURE_TYPE, required_level=1000)):
                namespace = dict(placement_path=proof, placement=feature, view=view, scope="Majesty",
                                 ComposeError=compose.ComposeError, __package__='majesty_cam', __name__='majesty_cam.compose')
                valid = encode(feature, b"observer fixture", image_id=int.from_bytes(b"PRIV", "little"))
                proof.write_bytes(valid)
                exec(code, namespace)
                for wrong in (encode(feature, b"observer fixture", image_id=int.from_bytes(b"NOPE", "little")), valid[:-1]):
                    proof.write_bytes(wrong)
                    with self.assertRaises(compose.ComposeError):
                        exec(code, namespace)

