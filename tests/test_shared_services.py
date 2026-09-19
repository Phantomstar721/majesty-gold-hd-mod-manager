"""Shared declarations, source boundaries, and isolated stock-compiler checks."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from majesty_cam.activity_time import activity_source, add_activity_service, MAX_ACTIVITIES, RECORD_WIDTH
from majesty_cam.compose import compile_gpl, _load_stock_gameplay_event_items
from majesty_cam.gameplay_events import (add_gameplay_event_observers, event_stock_paths, stock_tokens,
                                        _early_consumption_returns, _stock_preserving_prelude)
from majesty_cam.gpl import (DefinitionKind, SemanticMergeResult, find_foreach_return_violations,
                            merge_sources, parse_gpl, require_complete_semantic_coverage)
from majesty_cam.package import parse_mod_definition, mod_definition_mapping
from majesty_cam.shared_composition import SharedBinding, validate_shared_bindings, event_subscribers
from majesty_cam.shared_features import (StockActivityDuration, StockGameplayEventObserver,
                                        EVENT_SIGNATURES, parse_shared_feature, shared_feature_mapping)
from gpl_sampler_harness import Agent, SamplerHarness

GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD")
MOD = "12345678-1234-1234-1234-123456789abc"
ACTIVITY = StockActivityDuration("activity", "Example_Duty", "Example_Qualifies",
                                 "Example_Complete", "Example_Cancelled")
ACTIVITY_CALLBACKS = '''
function Example_Qualifies(agent Owner, agent Subject, agent Context, integer Key) is boolean
declare
begin
    return True;
end
function Example_Complete(agent Owner, agent Subject, agent Context, integer Key)
declare
begin
end
function Example_Cancelled(agent Owner, agent Subject, agent Context, integer Key, integer Reason)
declare
begin
end
'''


def events():
    return tuple(StockGameplayEventObserver("observer" + str(i), event, "Example_Event" + str(i))
                 for i, event in enumerate(EVENT_SIGNATURES))


def event_callbacks():
    return "\n".join("function " + feature.callback_symbol + "(" + ", ".join(
        kind + " Param" + str(i) for i, kind in enumerate(EVENT_SIGNATURES[feature.event]))
        + ")\ndeclare\nbegin\nend\n" for feature in events())


class AttackFlagCompletionTests(unittest.TestCase):
    event = "attack-flag-completed"
    feature = StockGameplayEventObserver("bounty", event, "Example_Completed")
    callbacks = '''function Example_Completed(agent Flag, agent Target)
declare
begin
end
function Other_Completed(agent Flag, agent Target)
declare
begin
end
function Example_Paid(agent Flag, agent Recipient, integer Share)
declare
begin
end
'''

    def test_contract_requires_two_agents_and_void_return(self):
        self.assertEqual(parse_shared_feature(shared_feature_mapping(self.feature)), self.feature)
        for args, returns in (("agent Flag", ""), ("agent Flag, integer Target", ""),
                              ("agent Flag, agent Target", " is boolean")):
            source = parse_gpl(f"function Example_Completed({args}){returns}\ndeclare\nbegin\nend\n", "invalid")
            with self.assertRaisesRegex(ValueError, "requires"):
                validate_shared_bindings([(MOD, (self.feature,), (source,))])
        callbacks = parse_gpl(self.callbacks, "example")
        second = replace(self.feature, feature_key="another", callback_symbol="Other_Completed")
        bindings = validate_shared_bindings([(MOD, (self.feature, second), (callbacks,))])
        self.assertEqual(event_subscribers(bindings)[self.event], ("Other_Completed", "Example_Completed"))
        self.assertEqual(event_stock_paths((self.feature,)), (
            Path("SDK/OriginalQuests/GPLMx/DecisionTrees/Modules/mx_check_rewards.gpl"),))

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "requires installed stock SDK")
    def test_completion_and_payout_preserve_both_entire_stock_owners(self):
        callbacks = parse_gpl(self.callbacks, "example")
        owners = ("attack_flag_poll", "attack_flag_death_callback")
        for paid in (False, True):
            for reverse in (False, True):
                with self.subTest(paid=paid, reverse=reverse):
                    subscribers = {self.event: ("Example_Completed", "Other_Completed")}
                    if paid:
                        subscribers["reward-flag-paid"] = ("Example_Paid",)
                    if reverse:
                        subscribers = dict(reversed(tuple(subscribers.items())))
                    stock = _load_stock_gameplay_event_items(GAME, subscribers)
                    final = add_gameplay_event_observers(SemanticMergeResult(callbacks.items, ()), subscribers, stock)
                    functions = {item.normalized_name: item.text for item in final.items}
                    for name in owners:
                        text = functions[name]
                        notify = "$Example_Completed(ThisAgent, target);\n\t$Other_Completed(ThisAgent, target);\n"
                        self.assertEqual(text.count(notify), 1)
                        self.assertRegex(text[text.index(notify) + len(notify):], r'^\$playsound\s*\(')
                        before = stock_tokens(text[:text.index(notify)])
                        self.assertIn(("if", "(", "$", "isdead", "(", "target", ")", ")", "begin"),
                                      [before[i:i+9] for i in range(len(before)-8)])
                        self.assertIn(('"gavereward"', '!', '=', 'true'),
                                      [before[i:i+4] for i in range(len(before)-3)])
                        # Remove ONLY our addition and restore the known payout
                        # call identity: every original stock token must survive.
                        restored = text.replace(notify, "").replace("$MM_Event_AttackGold", "$dropgoldinradius")
                        self.assertEqual(stock_tokens(restored), stock_tokens(stock[name].text))
                        self.assertEqual(text.count("$MM_Event_AttackGold"), int(paid))
                    if paid:
                        self.assertEqual(functions["mm_event_attackgold"].count("$Example_Paid("), 1)
                        self.assertNotIn("Example_Completed", functions["explore_flag_poll"])
                    else:
                        self.assertEqual(set(functions), {"example_completed", "other_completed", "example_paid", *owners})

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "requires installed stock SDK")
    def test_shared_owner_keeps_authored_prelude_but_rejects_gameplay_rewrites(self):
        subscribers = {self.event: ("Example_Completed",), "reward-flag-paid": ("Example_Paid",)}
        stock = _load_stock_gameplay_event_items(GAME, subscribers)
        callbacks = parse_gpl(self.callbacks, "example")
        owner = stock["attack_flag_poll"]
        prelude = replace(owner, text=re.sub(r'\bbegin\b', 'begin\n$PrivatePrelude(thisagent);',
                                            owner.text, count=1, flags=re.IGNORECASE))
        initial = SemanticMergeResult((*callbacks.items, prelude), ())
        final = add_gameplay_event_observers(initial, subscribers, stock)
        text = next(item.text for item in final.items if item.normalized_name == "attack_flag_poll")
        self.assertEqual(text.count("$PrivatePrelude("), 1)
        self.assertEqual(text.count("$Example_Completed("), 1)
        self.assertEqual(text.count("$MM_Event_AttackGold"), 1)
        for name in ("attack_flag_poll", "attack_flag_death_callback"):
            changed = replace(stock[name], text=stock[name].text.replace('"gavereward" != TRUE', '"gavereward" == TRUE'))
            with self.assertRaisesRegex(ValueError, "stock gameplay-event owner"):
                add_gameplay_event_observers(SemanticMergeResult((*callbacks.items, changed), ()), subscribers, stock)


class EarnedExperienceEventTests(unittest.TestCase):
    subscribers = {
        "combat-experience-awarded": ("Example_Combat",),
        "exploration-experience-awarded": ("Example_Explore",),
    }
    callbacks = '''function Example_Combat(agent Hero, integer Base)
declare
begin
end
function Example_Explore(agent Hero, integer Base)
declare
begin
end
'''

    def test_contract_is_two_typed_arguments_without_a_return(self):
        for event in self.subscribers:
            feature = StockGameplayEventObserver("xp", event, "Example_Award")
            self.assertEqual(parse_shared_feature(shared_feature_mapping(feature)), feature)
            for args, returns in (("agent Hero", ""), ("agent Hero, string Base", ""),
                                  ("agent Hero, integer Base", " is boolean")):
                source = parse_gpl(f"function Example_Award({args}){returns}\nbegin\nend\n")
                with self.assertRaisesRegex(ValueError, "requires"):
                    validate_shared_bindings([(MOD, (feature,), (source,))])

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "requires installed stock SDK")
    def test_stock_owners_preserved_and_other_rewards_not_intercepted(self):
        stock = _load_stock_gameplay_event_items(GAME, self.subscribers)
        final = add_gameplay_event_observers(
            SemanticMergeResult(parse_gpl(self.callbacks).items, ()), self.subscribers, stock)
        functions = {item.normalized_name: item.text for item in final.items}
        for name, wrapper in (("attack_end", "MM_Event_CombatXP"),
                              ("travel_to_exp", "MM_Event_ExploreXP")):
            text = functions[name]
            self.assertEqual(text.count("$" + wrapper), 1)
            self.assertEqual(stock_tokens(text.replace("$" + wrapper, "$give_exp")),
                             stock_tokens(stock[name].text))
        self.assertIn("$give_exp(leader,#familiar_fight_exp);", functions["attack_end"])
        self.assertNotIn("give_exp", functions)
        self.assertEqual(set(functions), {"example_combat", "example_explore", "attack_end",
                                        "travel_to_exp", "mm_event_combatxp", "mm_event_explorexp"})
        with TemporaryDirectory(prefix="manager-xp-events-compiler-") as tmp:
            compile_gpl(final.emit_project_source_set("Fixture.gpl", "Fixture.dat"),
                        GAME / "SDK/Gplbcc.exe", Path(tmp) / "compiler", stem="Fixture")

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "requires installed stock SDK")
    def test_generated_wrappers_pay_first_and_recursive_give_exp_is_not_an_event(self):
        stock = _load_stock_gameplay_event_items(GAME, self.subscribers)
        final = add_gameplay_event_observers(
            SemanticMergeResult(parse_gpl(self.callbacks).items, ()), self.subscribers, stock)
        wrappers = "\n".join(item.text for item in final.items
                              if item.normalized_name.startswith("mm_event_"))
        vm = SamplerHarness(wrappers)
        for wrapper, observer in (("MM_Event_CombatXP", "example_combat"),
                                   ("MM_Event_ExploreXP", "example_explore")):
            for base in (-1, 0, 120):
                with self.subTest(wrapper=wrapper, base=base):
                    leader, follower = Agent(), Agent()
                    trace = []
                    vm.calls["give_exp"] = lambda hero, amount: trace.append(("award", hero, amount))
                    def observe(hero, amount):
                        trace.append(("notify", hero, amount))
                        vm.calls["give_exp"](follower, amount // 2)
                    vm.calls[observer] = observe
                    vm.call(wrapper, leader, base)
                    expected = [("award", leader, base)]
                    if base > 0:
                        expected += [("notify", leader, base), ("award", follower, base // 2)]
                    self.assertEqual(trace, expected)

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "requires installed stock SDK")
    def test_incompatible_source_and_double_insertion_fail_closed(self):
        stock = _load_stock_gameplay_event_items(GAME, self.subscribers)
        callbacks = parse_gpl(self.callbacks).items
        for name in stock:
            changed = replace(stock[name], text=stock[name].text.replace("$give_exp", "$CustomXP"))
            with self.assertRaisesRegex(ValueError, "stock gameplay-event owner"):
                add_gameplay_event_observers(
                    SemanticMergeResult((*callbacks, changed), ()), self.subscribers, stock)
        final = add_gameplay_event_observers(SemanticMergeResult(callbacks, ()), self.subscribers, stock)
        with self.assertRaisesRegex(ValueError, "stock gameplay-event owner"):
            add_gameplay_event_observers(final, self.subscribers, stock)


class SharedServiceTests(unittest.TestCase):
    def harness(self):
        harness = SamplerHarness(activity_source((SharedBinding(MOD, ACTIVITY),)))
        harness.calls["example_qualifies"] = lambda *args: True
        harness.calls["example_complete"] = lambda *args: completed.append(args)
        harness.calls["example_cancelled"] = lambda *args: cancelled.append(args)
        completed, cancelled = [], []
        return harness, Agent(), Agent(), completed, cancelled

    def test_emitted_start_calls_null_agent_before_initializing_activity_root(self):
        for context in (None, Agent()):
            with self.subTest(required_context=context is not None):
                vm, owner, subject, _, _ = self.harness()
                native_calls = []
                def null_agent():
                    native_calls.append(())
                    return None
                vm.calls["nullagent"] = null_agent
                self.assertEqual(vm.root.fields, {})
                self.assertEqual(vm.call("Example_Duty_Start", owner, subject, context, 1, 1000), 1)
                self.assertEqual(native_calls, [()])
                records = vm.root["MM_ActivityRecords_v1"]
                self.assertEqual(len(records), RECORD_WIDTH)
                self.assertIs(records[3], context)
                self.assertIs(records[9], context is not None)
                self.assertTrue(vm.scheduled)
                self.assertTrue(callable(vm.root["MM_ActivityThread_v1"]))

    def test_emitted_service_bare_function_values_are_only_scheduler_callback(self):
        # GPL's compiler accepts a function reference where a runtime agent
        # comparison will fail. Audit actual emitted tokens, not just syntax.
        tokens = stock_tokens(activity_source((SharedBinding(MOD, ACTIVITY),)))
        bare = [tokens[i + 1] for i, token in enumerate(tokens[:-2])
                if token == "$" and tokens[i + 2] != "("]
        self.assertEqual(bare, ["mm_ad_tick"])
        self.assertIn(('"MM_ActivityThread_v1"', ',', '"function"', ',', '$', 'mm_ad_tick', ')'),
                      [tokens[i:i + 7] for i in range(len(tokens) - 6)])

    def test_emitted_timer_counts_only_sampled_qualification_and_completes_once(self):
        vm, owner, subject, done, cancelled = self.harness()
        self.assertEqual(vm.call("Example_Duty_Start", owner, subject, None, 1, 2000), 1)
        self.assertEqual(vm.call("Example_Duty_Start", owner, subject, None, 1, 9000), 0)
        vm.tick()  # Establish eligibility; do not credit a partial first interval.
        self.assertEqual(vm.call("Example_Duty_Elapsed", owner, 1), 0)
        vm.tick()
        self.assertEqual(vm.call("Example_Duty_Elapsed", owner, 1), 1000)
        vm.calls["example_qualifies"] = lambda *args: False
        vm.tick()
        vm.tick()
        self.assertEqual(vm.call("Example_Duty_State", owner, 1), 2)
        self.assertEqual(vm.call("Example_Duty_Elapsed", owner, 1), 1000)
        vm.calls["example_qualifies"] = lambda *args: True
        vm.tick()
        vm.tick()
        vm.tick()
        self.assertEqual(done, [(owner, subject, None, 1)])
        self.assertEqual(cancelled, [])
        self.assertEqual(vm.call("Example_Duty_State", owner, 1), 0)
        self.assertFalse(vm.scheduled)

    def test_emitted_pause_resume_cancel_and_independent_owners(self):
        vm, owner, subject, done, cancelled = self.harness()
        other = Agent()
        vm.call("Example_Duty_Start", owner, subject, None, 7, 3000)
        vm.call("Example_Duty_Start", other, subject, None, 7, 3000)
        vm.tick()
        vm.tick()
        self.assertEqual(vm.call("Example_Duty_Pause", owner, 7), 1)
        self.assertEqual(vm.call("Example_Duty_State", owner, 7), 3)
        vm.tick()
        vm.tick()
        self.assertEqual(done, [(other, subject, None, 7)])
        self.assertEqual(vm.call("Example_Duty_Elapsed", owner, 7), 1000)
        vm.call("Example_Duty_Resume", owner, 7)
        vm.tick()
        vm.tick()
        self.assertEqual(vm.call("Example_Duty_Elapsed", owner, 7), 2000)
        vm.call("Example_Duty_Cancel", owner, 7)
        vm.tick()
        self.assertEqual(cancelled, [(owner, subject, None, 7, 1)])
        self.assertEqual(vm.call("Example_Duty_Cancel", owner, 7), 0)

    def test_emitted_destruction_and_reentrant_terminal_callbacks(self):
        for lost, reason in (("owner", 2), ("subject", 3), ("context", 4)):
            vm, owner, subject, done, cancelled = self.harness()
            context = Agent()
            vm.call("Example_Duty_Start", owner, subject, context, 1, 1000)
            {"owner": owner, "subject": subject, "context": context}[lost].alive = False
            vm.tick()
            self.assertEqual(cancelled, [(owner, subject, context, 1, reason)])
            self.assertEqual(done, [])
        vm, owner, subject, done, cancelled = self.harness()
        vm.call("Example_Duty_Start", owner, subject, None, 1, 1000)
        vm.call("Example_Duty_Start", owner, subject, None, 2, 9000)
        def finish(*args):
            done.append(args)
            self.assertEqual(vm.call("Example_Duty_Cancel", owner, 2), 1)
            self.assertEqual(vm.call("Example_Duty_Start", owner, subject, None, 1, 5000), 1)
        vm.calls["example_complete"] = finish
        vm.tick()
        vm.tick()
        self.assertEqual(len(done), 1)
        self.assertEqual(cancelled, [(owner, subject, None, 2, 1)])
        self.assertEqual(vm.call("Example_Duty_Elapsed", owner, 1), 0)
        self.assertTrue(vm.scheduled)
        self.assertEqual(vm.stops, 0)

    def test_emitted_bounds_and_condition_cannot_mutate_ledger(self):
        vm, owner, subject, _, _ = self.harness()
        self.assertEqual(vm.call("Example_Duty_Start", owner, subject, None, 1, 0), -1)
        self.assertEqual(vm.call("Example_Duty_Start", None, subject, None, 1, 1000), -1)
        for key in range(1, MAX_ACTIVITIES + 1):
            self.assertEqual(vm.call("Example_Duty_Start", owner, subject, None, key, 2147483647), 1)
        self.assertEqual(vm.call("Example_Duty_Start", owner, subject, None, 999, 1000), -2)
        vm.calls["example_qualifies"] = lambda *args: (
            self.assertEqual(vm.call("Example_Duty_Cancel", owner, args[3]), -3) or True)
        vm.tick()
        self.assertEqual(vm.call("Example_Duty_State", owner, 1), 1)

    def test_round_trip_through_public_definition_and_fingerprint(self):
        features = (*events(), ACTIVITY)
        value = {"schema_version": 3, "mod_id": "{" + MOD + "}",
                 "internal_name": "Example", "display_name": "Example", "custom_buildings": [],
                 "runtime_features": [shared_feature_mapping(f) for f in features]}
        parsed = parse_mod_definition(value)
        self.assertEqual(parsed.runtime_features, features)
        self.assertEqual(mod_definition_mapping(parsed), value)

    def test_strict_fields_and_reserved_names(self):
        for update in ({"unexpected": True}, {"api_prefix": "MM_Fake"},
                       {"completion_callback_symbol": "Example_Qualifies"},
                       {"feature_key": 'x";bad'}, {"api_prefix": "a" * 49}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                parse_shared_feature({**shared_feature_mapping(ACTIVITY), **update})
        with self.assertRaises(ValueError):
            parse_shared_feature({**shared_feature_mapping(events()[0]), "event": "item-disappeared"})

    def test_callback_signature_ownership_duplicates_and_api_collisions(self):
        source = parse_gpl(ACTIVITY_CALLBACKS, "example")
        bindings = validate_shared_bindings([(MOD, (ACTIVITY,), (source,))])
        self.assertEqual(bindings[0].identity, MOD + ":activity")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            validate_shared_bindings([(MOD, (ACTIVITY,), ())])
        with self.assertRaisesRegex(ValueError, "requires"):
            validate_shared_bindings([(MOD, (ACTIVITY,), (parse_gpl(
                ACTIVITY_CALLBACKS.replace(" is boolean", ""), "bad"),))])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_shared_bindings([(MOD, (ACTIVITY, ACTIVITY), (source,))])
        collision = parse_gpl("function Example_Duty_Start()\nbegin\nend\n", "collision")
        with self.assertRaisesRegex(ValueError, "collides"):
            validate_shared_bindings([(MOD, (ACTIVITY,), (source, collision))])

    def test_empty_has_no_service_or_stock_file_inputs(self):
        empty = SemanticMergeResult((), ())
        self.assertIs(add_activity_service(empty, ()), empty)
        self.assertIs(add_gameplay_event_observers(empty, {}, {}), empty)
        self.assertEqual(event_stock_paths((ACTIVITY,)), ())

    def test_service_is_shared_bounded_and_uses_stock_scheduler(self):
        other = replace(ACTIVITY, feature_key="different", api_prefix="Other_Duty")
        bindings = (SharedBinding(MOD, ACTIVITY), SharedBinding(MOD, other))
        source = parse_gpl(activity_source(bindings), "service")
        require_complete_semantic_coverage(source)
        text = source.text
        self.assertEqual(text.count("$NewThread("), 1)
        self.assertEqual(text.count("function MM_AD_Tick("), 1)
        self.assertIn(str(MAX_ACTIVITIES * RECORD_WIDTH), text)
        self.assertIn('"function", $MM_AD_Tick', text)
        for forbidden in ("$RunThread", "$ListObjects", "$PathCost", "$SpawnUnit", "$CreateEffector"):
            self.assertNotIn(forbidden, text)
        self.assertFalse(find_foreach_return_violations(source.text))
        tick = source.require(DefinitionKind.FUNCTION, "MM_AD_Tick").text
        self.assertLess(tick.index('Root\'s "MM_ActivityRecords_v1" = Kept;'), tick.index("$MM_AD_Notify("))
        self.assertIn("Duration - Elapsed", tick)
        self.assertIn('"MM_ActivityBusy_v1") return -3', text)
        self.assertIn(MOD + ":different", text)
        with self.assertRaisesRegex(ValueError, "collides"):
            add_activity_service(SemanticMergeResult(source.items, ()), bindings)

    def test_stock_boundary_comparison_preserves_strings(self):
        self.assertEqual(stock_tokens('A = "item"; // x'), stock_tokens(' a="item";'))
        self.assertNotEqual(stock_tokens('A = "item";'), stock_tokens('A = "Item";'))

    def test_consume_only_branch_proof_is_generic_and_keeps_stock_guard_and_effects(self):
        pair = '$DeleteInventoryItem(#AnItem, ThisAgent); $ForgetSpell(ThisAgent, "AnItem");'
        baseline = ('function Sample(agent ThisAgent)\ndeclare\nbegin\n'
                    'if ($IsDead(ThisAgent)) return;\n'
                    '$CreateEffector(ThisAgent, "Effect", 0);\n' + pair + '\nend\n')
        branch = 'if (ThisAgent\'s "Title" == "AnyPrivateType") begin ' + pair + ' return; end\n'
        modified = baseline.replace('$CreateEffector', branch + '$CreateEffector')
        offsets = _early_consumption_returns(baseline, modified)
        self.assertEqual(len(offsets), 1)
        self.assertTrue(modified[offsets[0]:].startswith('return; end'))
        self.assertEqual(len(_early_consumption_returns(
            baseline, baseline.replace('$CreateEffector', branch + branch + '$CreateEffector'))), 2)
        for bad in (modified.replace('"Effect"', '"DifferentEffect"'),
                    modified.replace('if ($IsDead(ThisAgent)) return;', ''),
                    modified.replace('#AnItem', '#OtherItem', 1),
                    modified.replace('return; end', '$ExtraEffect(ThisAgent); return; end'),
                    baseline.replace('if ($IsDead', branch + 'if ($IsDead')):
            self.assertIsNone(_early_consumption_returns(baseline, bad))

    def test_private_callback_prelude_proof_preserves_the_entire_stock_body(self):
        baseline = 'function Award(agent Actor)\ndeclare\nbegin\n$StockPay(Actor, 4);\nend\n'
        wrapped = baseline.replace('begin\n', 'begin\n$PrivateAward(Actor);\n')
        self.assertTrue(_stock_preserving_prelude(baseline, wrapped))
        self.assertTrue(_stock_preserving_prelude(baseline, wrapped.replace(
            '$PrivateAward(Actor);', '$First(Actor); $Second(Actor, "Value");')))
        self.assertFalse(_stock_preserving_prelude(baseline, wrapped.replace('Actor, 4', 'Actor, 5')))
        self.assertFalse(_stock_preserving_prelude(baseline, wrapped.replace(
            '$PrivateAward(Actor);', 'if (True) return;')))
        self.assertFalse(_stock_preserving_prelude(baseline, wrapped.replace(
            '$PrivateAward(Actor);', '$dropgoldinradius(Actor, 4);')))

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "requires installed stock SDK")
    def test_observers_preserve_existing_consumption_branch_and_reward_prelude(self):
        import re
        callbacks = parse_gpl(event_callbacks(), "example")
        bindings = validate_shared_bindings([(MOD, events(), (callbacks,))])
        subscribers = event_subscribers(bindings)
        stock = _load_stock_gameplay_event_items(GAME, subscribers)
        potion = stock['regeneration_elixer_effect']
        branch = '''if (ThisAgent's "Title" == "PrivateType")
begin
    $DeleteInventoryItem(#Bazaar_Item_Four, ThisAgent);
    $ForgetSpell(ThisAgent, "Regeneration_Elixer");
    return;
end
'''
        potion = replace(potion, text=re.sub(r'\$createeffector\b',
            lambda m: branch + m.group(), potion.text, count=1, flags=re.IGNORECASE))
        gold = stock['dropgoldinradius']
        gold = replace(gold, text=re.sub(r'\bbegin\b',
            'begin\n$PrivateReagentAward(ThisAgent);', gold.text, count=1, flags=re.IGNORECASE))
        initial = SemanticMergeResult((*callbacks.items, potion, gold), ())
        final = add_gameplay_event_observers(initial, subscribers, stock)
        functions = {item.normalized_name: item.text for item in final.items}
        self.assertEqual(functions['dropgoldinradius'], gold.text)
        self.assertEqual(functions['mm_event_attackgold'].count('$PrivateReagentAward('), 1)
        self.assertEqual(functions['regeneration_elixer_effect'].count('$Example_Event0('), 2)
        self.assertNotIn('Phantom', functions['regeneration_elixer_effect'])
        with TemporaryDirectory(prefix="manager-event-wrapper-compiler-") as tmp:
            compile_gpl(final.emit_project_source_set("Fixture.gpl", "Fixture.dat"),
                        GAME / "SDK/Gplbcc.exe", Path(tmp) / "compiler", stem="Fixture")

    @unittest.skipUnless((GAME / "SDK/Gplbcc.exe").is_file(), "requires installed stock SDK")
    def test_real_stock_boundaries_and_compiler_in_isolated_fixture(self):
        callbacks = parse_gpl(ACTIVITY_CALLBACKS + event_callbacks(), "example")
        bindings = validate_shared_bindings([(MOD, (*events(), ACTIVITY), (callbacks,))])
        subscribers = event_subscribers(bindings)
        stock = _load_stock_gameplay_event_items(GAME, subscribers)
        initial = SemanticMergeResult(callbacks.items, ())
        observed = add_gameplay_event_observers(initial, subscribers, stock)
        final = add_activity_service(observed, bindings)
        functions = {item.normalized_name: item.text for item in final.items}
        self.assertNotIn("dropgoldinradius", functions)
        self.assertNotIn("exit_fair", functions)
        self.assertNotIn("dump_contestants", functions)
        self.assertIn("$MM_Event_FairFinished", functions["enter_tourney"])
        self.assertLess(functions["mm_event_fairfinished"].index("$Exit_Fair("),
                        functions["mm_event_fairfinished"].index("$Example_Event3("))
        for name in ("heal_self", "heal_self_fleeing"):
            self.assertEqual(functions[name].count("$Example_Event0("), 1)
        caravan = functions["caravan_go_trade"]
        self.assertLess(caravan.casefold().index("$transfer_gold"), caravan.index("$Example_Event2("))
        self.assertLess(caravan.index("$Example_Event2("), caravan.casefold().index("$henchman_dead"))
        self.assertFalse(find_foreach_return_violations(final.emit_project_source_set().gpl_text))
        changed = stock["heal_self"]
        changed = replace(changed, text=changed.text.replace("#ATTRIB_NumHealingPotions", "#ATTRIB_HitPoints"))
        with self.assertRaisesRegex(ValueError, "success/cleanup boundary"):
            add_gameplay_event_observers(SemanticMergeResult((*callbacks.items, changed), ()), subscribers, stock)
        # This compiles only a disposable language fixture, not a mod/profile.
        with TemporaryDirectory(prefix="manager-shared-compiler-") as tmp:
            compile_gpl(final.emit_project_source_set("Fixture.gpl", "Fixture.dat"),
                        GAME / "SDK/Gplbcc.exe", Path(tmp) / "compiler", stem="Fixture")


if __name__ == "__main__":
    unittest.main()
