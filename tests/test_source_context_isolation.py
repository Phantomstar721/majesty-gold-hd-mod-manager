"""Isolated synchronous adapters retain the entry source through helper calls."""
import hashlib
import unittest

from majesty_cam.gpl import SemanticMergeResult, parse_gpl
from majesty_cam.source_context import SourceContextDispatch, compose
from gpl_sampler_harness import Agent, SamplerHarness


FEATURE = SourceContextDispatch("reward", "give_gold", ("agent", "integer"), "ObservedGold")
SOURCE = '''function FlagEntry(agent Flag, integer Amount)
declare begin
    $FlagDistribution(Flag, Amount);
end
function FlagDistribution(agent ThisAgent, integer Amount)
declare agent Target;
begin
    if ($ListSize(ThisAgent's "guysnearby") > 0)
        $Pay(ThisAgent's "recipient", Amount);
    else if (ThisAgent's "gotguys" == False)
        begin
            Target = ThisAgent's "target";
            if ($IsValidGamePiece(Target) == False)
                $Radius(ThisAgent, Amount);
            else
                $Radius(Target, Amount);
        end
end
function Radius(agent ThisAgent, integer Amount)
declare begin
    $Pay(ThisAgent's "recipient", Amount);
end
function Pay(agent Recipient, integer Amount)
declare begin
    $give_gold(Recipient, Amount);
end
function give_gold(agent Recipient, integer Amount)
declare begin
end
function ObservedGold(agent OriginalFlag, agent Recipient, integer Amount)
declare begin
    $give_gold(Recipient, Amount);
    $Notify(OriginalFlag, Recipient, Amount);
end
function OrdinaryLoot(agent Source, integer Amount)
declare begin
    $Radius(Source, Amount);
end
'''


def parsed(text=SOURCE):
    return SemanticMergeResult(parse_gpl(text).items, ())


def clone_name(name, namespace="MM_EG"):
    return namespace + "_" + hashlib.sha256(name.casefold().encode("ascii")).hexdigest()[:24]


class IsolatedSourceContextTests(unittest.TestCase):
    def compose(self, text=SOURCE, roots=("FlagEntry",), **kwargs):
        return compose(parsed(text), (FEATURE,), roots, kwargs.pop("loader", None),
                       namespace="MM_EG", strict=True, **kwargs)

    def vm(self, result):
        vm = SamplerHarness("\n".join(item.text for item in result.items))
        seen = []
        vm.calls["give_gold"] = lambda *args: seen.append(("gold", *args))
        vm.calls["notify"] = lambda *args: seen.append(("event", *args))
        return vm, seen

    def test_original_flag_survives_target_fallback_and_public_loot_stays_public(self):
        result = self.compose()
        items = {item.key: item for item in result.items}
        for item in parsed().items:
            if item.normalized_name != "flagentry":
                self.assertEqual(item.text, items[item.key].text)
        vm, seen = self.vm(result)
        flag, target, hero = Agent(), Agent(), Agent()
        flag.fields.update(guysnearby=[], gotguys=False, target=target, recipient=hero)
        target.fields["recipient"] = hero
        vm.call("FlagEntry", flag, 7)
        self.assertEqual(seen, [("gold", hero, 7), ("event", flag, hero, 7)])
        seen.clear()
        vm.call("OrdinaryLoot", target, 7)
        self.assertEqual(seen, [("gold", hero, 7)])

    def test_cached_invalid_target_empty_and_zero_share_paths_keep_cardinality(self):
        vm, seen = self.vm(self.compose())
        flag, hero = Agent(), Agent()
        flag.fields.update(guysnearby=[hero], gotguys=True, target=None, recipient=hero)
        vm.call("FlagEntry", flag, 0)
        self.assertEqual(seen, [("gold", hero, 0), ("event", flag, hero, 0)])
        seen.clear()
        flag.fields.update(guysnearby=[], gotguys=False)
        vm.call("FlagEntry", flag, 3)
        self.assertEqual(seen, [("gold", hero, 3), ("event", flag, hero, 3)])
        seen.clear()
        flag.fields["gotguys"] = True
        vm.call("FlagEntry", flag, 3)
        self.assertEqual(seen, [])

    def test_namespaces_keep_independent_adapters_over_the_same_public_helper(self):
        extra = '''function OtherEntry(agent Source, integer Amount)
declare begin $Radius(Source, Amount); end
function OtherGold(agent Source, agent Recipient, integer Amount)
declare begin $give_gold(Recipient, Amount); $OtherNotify(Source, Recipient, Amount); end
'''
        first = self.compose(SOURCE + extra)
        second = compose(first, (SourceContextDispatch("other", "give_gold", ("agent", "integer"),
                         "OtherGold"),), ("OtherEntry",), None, namespace="MM_Other", strict=True)
        first_items = {item.key: item.text for item in first.items}
        for item in second.items:
            if item.key in first_items and item.normalized_name != "otherentry":
                self.assertEqual(item.text, first_items[item.key])
        vm, seen = self.vm(second)
        vm.calls["othernotify"] = lambda *args: seen.append(("other", *args))
        flag, hero = Agent(), Agent()
        flag.fields.update(guysnearby=[hero], gotguys=True, recipient=hero)
        vm.call("FlagEntry", flag, 2)
        vm.call("OtherEntry", flag, 4)
        self.assertEqual(seen, [("gold", hero, 2), ("event", flag, hero, 2),
                                ("gold", hero, 4), ("other", flag, hero, 4)])

    def test_recursive_no_argument_helpers_and_side_effect_arguments_run_once(self):
        text = SOURCE.replace("$FlagDistribution(Flag, Amount);", "$Recur(Flag, $Next(), Amount);")
        text += '''function Recur(agent Recipient, integer Count, integer Amount)
declare begin
    if (Count > 0) $Recur(Recipient, Count - 1, Amount);
    else $give_gold(Recipient, Amount + $NoArgs());
end
function NoArgs() is integer
declare begin
    $give_gold($NullAgent(), 1);
    return 2;
end
'''
        result = self.compose(text)
        vm, seen = self.vm(result)
        evaluations = []
        vm.calls["next"] = lambda: evaluations.append(1) or 2
        flag = Agent()
        vm.call("FlagEntry", flag, 5)
        self.assertEqual(evaluations, [1])
        self.assertEqual(seen, [("gold", None, 1), ("event", flag, None, 1),
                                ("gold", flag, 7), ("event", flag, flag, 7)])

    def test_strict_rejects_dynamic_scheduled_and_function_value_routes(self):
        additions = (
            '(Flag\'s "Payment")(Flag, Amount);',
            '$RunThread(Flag\'s "Payment", 1, Flag);',
            'Flag\'s "Payment" = $Pay;',
            '$CreateEffector(Flag, "PaymentEffect", 0);',
        )
        for addition in additions:
            with self.subTest(addition=addition), self.assertRaisesRegex(ValueError, "dispatch"):
                self.compose(SOURCE.replace("$FlagDistribution(Flag, Amount);",
                                           addition + "$FlagDistribution(Flag, Amount);"))
        # Inspect side helpers too, even if another direct call reaches the target.
        text = SOURCE.replace("$FlagDistribution(Flag, Amount);", "$Side(Flag); $FlagDistribution(Flag, Amount);")
        text += 'function Side(agent Flag) declare begin $RunThread(Flag\'s "Payment", 1, Flag); end'
        with self.assertRaisesRegex(ValueError, "asynchronous dispatch.*Side"):
            self.compose(text)

    def test_strict_requires_each_root_and_valid_target_adapter_signatures(self):
        cases = (
            (SOURCE.replace("function give_gold(agent Recipient, integer Amount)\ndeclare begin\nend\n", ""),
             "target has no verifiable"),
            (SOURCE.replace("function give_gold(agent Recipient, integer Amount)",
                            "function give_gold(agent Recipient, string Amount)"), "expected"),
            (SOURCE.replace("function ObservedGold(agent OriginalFlag, agent Recipient, integer Amount)",
                            "function ObservedGold(agent Recipient, integer Amount)"), "expected"),
            (SOURCE.replace("$FlagDistribution(Flag, Amount);", "$NoPayment(Flag);"), "not synchronously reachable"),
            (SOURCE.replace("$FlagDistribution(Flag, Amount);", "Flag = $NullAgent(); $FlagDistribution(Flag, Amount);"),
             "reassigns its source"),
        )
        for text, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.compose(text)
        with self.assertRaisesRegex(ValueError, "distinct verifiable source root"):
            self.compose(roots=("MissingRoot",))
        with self.assertRaisesRegex(ValueError, "at least one verifiable source root"):
            self.compose(roots=())
        missing_adapter = SOURCE.replace("function ObservedGold(agent OriginalFlag, agent Recipient, integer Amount)\n"
                                         "declare begin\n    $give_gold(Recipient, Amount);\n"
                                         "    $Notify(OriginalFlag, Recipient, Amount);\nend\n", "")
        with self.assertRaisesRegex(ValueError, "adapter has no verifiable"):
            self.compose(missing_adapter)
        text = SOURCE + "function EmptyRoot(agent Flag) declare begin end"
        with self.assertRaisesRegex(ValueError, "not synchronously reachable.*emptyroot"):
            self.compose(text, roots=("FlagEntry", "EmptyRoot"))

    def test_generated_collisions_include_helpers_only_available_from_loader(self):
        collision = parse_gpl("function " + clone_name("Pay") +
                              "(agent Source) declare begin end").items[0]
        with self.assertRaisesRegex(ValueError, "generated symbol collision"):
            self.compose(SOURCE + collision.text)
        with self.assertRaisesRegex(ValueError, "generated symbol collision"):
            self.compose(loader=lambda name: collision if name == collision.normalized_name else None)
        text = SOURCE.replace("function Pay(agent Recipient, integer Amount)\ndeclare begin",
                              "function Pay(agent Recipient, integer Amount)\ndeclare agent MM_SourceContext; begin")
        with self.assertRaisesRegex(ValueError, "reserved parameter collision"):
            self.compose(text)

    def test_default_mode_and_clone_names_remain_compatible(self):
        original = parsed()
        result = compose(original, (FEATURE,), ("FlagEntry",), None)
        self.assertIn(clone_name("Pay", "MM_SC"), {item.name for item in result.items})
        no_route = parsed(SOURCE.replace("$FlagDistribution(Flag, Amount);", "$NoPayment(Flag);"))
        self.assertIs(compose(no_route, (FEATURE,), ("FlagEntry",), None), no_route)


if __name__ == "__main__":
    unittest.main()
