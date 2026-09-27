from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.typed_providers import (TypedBooleanProvider, TypedBooleanDispatch,
    compose_dispatches, parse_feature, feature_mapping)
from majesty_cam.gpl import parse_gpl, parse_dat, SemanticMergeResult
from majesty_cam.compose import compile_gpl

P = TypedBooleanProvider("provider", "ExampleEligible", ("agent", "agent"), "Example_Eligible")
C = TypedBooleanDispatch("consumer", "ExampleEligible", ("agent", "agent"), "Consumer_Dispatch")
BODY = "function Example_Eligible(agent A, agent B) is boolean\ndeclare\nbegin\nreturn True;\nend\n"


class TypedProviderTests(unittest.TestCase):
    def packages(self, binding="", providers=(P,)):
        return (("provider", providers, (parse_gpl(BODY+binding),)),
                ("consumer", (C,), (parse_gpl(""),)))

    def test_schema_roundtrip_and_rejections(self):
        for feature in (P, C):
            self.assertEqual(parse_feature(feature_mapping(feature)), feature)
            with self.assertRaises(ValueError):
                parse_feature({**feature_mapping(feature), "unused": 1})
        with self.assertRaises(ValueError):
            parse_feature({**feature_mapping(C), "parameter_types": ["arbitrary"]})
        with self.assertRaises(ValueError):
            parse_feature({**feature_mapping(C), "dispatch_symbol": "MM_Collision"})

    def test_static_calls_have_typed_signature_and_no_policy_or_dynamic_invocation(self):
        generated = compose_dispatches(self.packages())
        self.assertEqual(len(generated), 1)
        text = generated[0].text
        self.assertIn("function Provider, agent Arg0, agent Arg1", text)
        self.assertIn("Provider == $Example_Eligible", text)
        self.assertIn("return $Example_Eligible(Arg0, Arg1)", text)
        self.assertIn("return False", text)
        self.assertNotIn("Provider(", text)
        self.assertNotIn("HasAttribute", text)
        compiler = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD/SDK/Gplbcc.exe")
        if compiler.is_file():
            source = SemanticMergeResult((*parse_gpl(BODY).items, *generated), ())
            with TemporaryDirectory(prefix="manager-typed-provider-") as tmp:
                compile_gpl(source.emit_project_source_set(), compiler, Path(tmp)/"compiler")

    def test_missing_provider_is_false_and_multiple_providers_are_deterministic(self):
        generated = compose_dispatches((("consumer", (C,), (parse_gpl(""),)),))
        self.assertIn("return False", generated[0].text)
        p2 = replace(P, callback_symbol="Other_Eligible")
        row = ("other", (p2,), (parse_gpl(BODY.replace("Example_Eligible", "Other_Eligible")),))
        self.assertEqual(compose_dispatches((*self.packages(), row)),
                         compose_dispatches((row, *self.packages())))

    def test_ownership_signature_and_export_collisions(self):
        for packages in (
            (("wrong", (P,), (parse_gpl(""),)),),
            (("provider", (P,), (parse_gpl(BODY.replace("is boolean", "is integer")),)),),
            (*self.packages(), ("copy", (), (parse_gpl(BODY),))),
            (*self.packages(), ("consumer2", (C,), (parse_gpl(""),))),
            (("provider", (P,), (parse_gpl(BODY),)),
             ("consumer", (replace(C, parameter_types=("agent", "string")),), (parse_gpl(""),))),
        ):
            with self.assertRaises(ValueError):
                compose_dispatches(packages)

    def test_installed_provider_bindings_must_be_literal_owned_and_declared(self):
        def body(statement):
            return "function Install(agent A)\ndeclare\nbegin\n" + statement + "\nend\n"
        bindings = (
            'A\'s "ExampleEligible" = $Example_Eligible;',
            '$AddAttribute(A, "ExampleEligible", "function", $Example_Eligible);',
            '$AddAttribute($Lookup(A, B), "ExampleEligible", "function", $Example_Eligible);',
            '(A\'s "ExampleEligible") = $Example_Eligible;',
        )
        for binding in bindings:
            compose_dispatches(self.packages(body(binding)))
            with self.assertRaisesRegex(ValueError, "undeclared"):
                compose_dispatches(self.packages(body(binding), providers=()))
        with self.assertRaisesRegex(ValueError, "computed"):
            compose_dispatches(self.packages(body('A\'s "ExampleEligible" = A\'s "Other";')))
        dat = parse_dat('[Example]\n{Hero\n(ExampleEligible Example_Eligible)\n}\n[end]\n')
        compose_dispatches((("provider", (P,), (parse_gpl(BODY), dat)), self.packages()[1]))
        with self.assertRaisesRegex(ValueError, "undeclared"):
            compose_dispatches((("provider", (), (parse_gpl(BODY), dat)), self.packages()[1]))

    def test_read_only_comparisons_do_not_install_provider_bindings(self):
        for expression in (
            '$validfunction(A\'s "ExampleEligible") == True',
            '((A\'s "ExampleEligible")) == $Other_Eligible',
            'A\'s "ExampleEligible" != $Other_Eligible',
        ):
            source = parse_gpl('function Check(agent A) is boolean\ndeclare\nbegin\n'
                               f'if ({expression}) return True;\nreturn False;\nend\n')
            compose_dispatches((("consumer", (C,), (source,)),))
        # A nearby comparison must not hide a subsequent computed assignment.
        source = parse_gpl('function Check(agent A)\ndeclare\nbegin\n'
            'if ($validfunction(A\'s "ExampleEligible") == True)\n'
            'A\'s "ExampleEligible" = A\'s "Other";\nend\n')
        with self.assertRaisesRegex(ValueError, "computed"):
            compose_dispatches((("consumer", (C,), (source,)),))


if __name__ == "__main__":
    unittest.main()
