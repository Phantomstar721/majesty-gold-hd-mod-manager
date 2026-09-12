from pathlib import Path
import struct
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.compose import ComposeError, _detach_private_activity_texts
from majesty_cam.gpl import merge_sources, parse_gpl
from majesty_cam.intent_text import (
    ActivityTextDiscoveryPackage,
    INTENT_ID_BASE,
    INTENT_ID_LIMIT,
    INTENT_REGISTRY_MAX_RECORDS,
    IntentTextError,
    IntegerExpressionEnvironment,
    PrivateActivityTextRecord,
    PrivateLiteralTextRecord,
    allocate_private_activity_text_ids,
    allocate_private_literal_text_id,
    audit_private_activity_text_resolver_aliases,
    collect_integer_expression_environment,
    discover_private_activity_text_bindings,
    decode_intent_registry,
    encode_intent_registry,
    rewrite_private_activity_text_resolver_calls,
    rewrite_unowned_private_activity_text_resolver_calls,
)
from majesty_cam.strt import StrtRecord, StrtTable


MOD_A = "00000000-0000-0000-0000-000000000001"
MOD_B = "00000000-0000-0000-0000-000000000002"


class PrivateIntentRegistryTests(unittest.TestCase):
    def test_ids_are_stable_when_an_independent_mod_is_selected(self):
        one = allocate_private_activity_text_ids(
            (("alchemist", MOD_B, 309, "#Intent_Oil", "Applying oil"),)
        )[0]
        combined = allocate_private_activity_text_ids(
            (
                ("haunt", MOD_A, 177, "#Warning", "Warning text"),
                ("alchemist", MOD_B, 309, "#Intent_Oil", "Applying oil"),
            )
        )
        again = next(
            item for item in combined if item.expressions == ("#Intent_Oil",)
        )

        self.assertEqual(one.runtime_id, again.runtime_id)
        self.assertTrue(INTENT_ID_BASE <= one.runtime_id < INTENT_ID_LIMIT)

    def test_binary_registry_is_sorted_round_trippable_and_strict(self):
        bindings = allocate_private_activity_text_ids(
            (
                ("haunt", MOD_A, 177, "#Warning", "Warning text"),
                ("alchemist", MOD_B, 309, "#Intent_Oil", "Applying oil"),
            )
        )
        records = tuple(
            PrivateActivityTextRecord(
                binding=binding,
                text=binding.expected_text.encode("cp1252"),
            )
            for binding in reversed(bindings)
        )

        payload = encode_intent_registry(records)
        decoded = decode_intent_registry(payload)

        self.assertEqual(payload[:4], b"MMTX")
        self.assertEqual([key for key, _text in decoded], sorted(key for key, _text in decoded))
        self.assertEqual({text for _key, text in decoded}, {b"Warning text", b"Applying oil"})
        with self.assertRaisesRegex(IntentTextError, "trailing bytes"):
            decode_intent_registry(payload + b"trash")

    def test_literal_text_ids_are_stable_and_share_the_strict_registry(self):
        name_id = allocate_private_literal_text_id(
            MOD_A, "stock.mx05-live-agent-list-panel.v1", "offers:title"
        )
        again = allocate_private_literal_text_id(
            "{00000000-0000-0000-0000-000000000001}",
            "stock.mx05-live-agent-list-panel.v1",
            "offers:title",
        )
        goal_id = allocate_private_literal_text_id(
            MOD_A, "stock.mx05-live-agent-list-panel.v1", "offers:text"
        )
        self.assertEqual(name_id, again)
        self.assertNotEqual(name_id, goal_id)
        self.assertTrue(0x68000000 <= name_id < INTENT_ID_LIMIT)
        payload = encode_intent_registry((
            PrivateLiteralTextRecord(goal_id, b"Deliver orders"),
            PrivateLiteralTextRecord(name_id, b"Royal Dispatch"),
        ))
        self.assertEqual(
            dict(decode_intent_registry(payload))[name_id], b"Royal Dispatch"
        )

    def test_empty_registry_is_valid_and_malformed_counts_or_lengths_are_not(self):
        self.assertEqual(decode_intent_registry(b"MMTX" + struct.pack("<II", 1, 0)), ())
        too_many = b"MMTX" + struct.pack("<II", 1, INTENT_REGISTRY_MAX_RECORDS + 1)
        with self.assertRaisesRegex(IntentTextError, "too many records"):
            decode_intent_registry(too_many)
        zero_length = (
            b"MMTX"
            + struct.pack("<II", 1, 1)
            + struct.pack("<II", INTENT_ID_BASE, 0)
        )
        with self.assertRaisesRegex(IntentTextError, "invalid length"):
            decode_intent_registry(zero_length)

    def test_allocator_rejects_duplicate_rows_and_non_cp1252_text(self):
        with self.assertRaisesRegex(IntentTextError, "duplicate private AITX"):
            allocate_private_activity_text_ids(
                (
                    ("one", MOD_A, 309, "#First", "one"),
                    ("one", MOD_A, 309, "#Second", "two"),
                )
            )
        with self.assertRaisesRegex(IntentTextError, "CP1252"):
            allocate_private_activity_text_ids(
                (("one", MOD_A, 309, "#First", "snowman ☃"),)
            )

    def test_same_source_row_in_two_mods_has_distinct_stable_ids(self):
        bindings = allocate_private_activity_text_ids(
            (
                ("one", MOD_A, 77, ("#Alias",), "first"),
                ("two", MOD_B, 77, ("#Alias",), "second"),
            )
        )

        self.assertEqual({item.source_index for item in bindings}, {77})
        self.assertEqual(len({item.runtime_id for item in bindings}), 2)

    def test_uuid_spelling_is_canonicalized_before_id_allocation(self):
        lower = allocate_private_activity_text_ids(
            (("one", "{abcdefab-cdef-4abc-8def-abcdefabcdef}", 77, (), "text"),)
        )[0]
        upper = allocate_private_activity_text_ids(
            (("one", "ABCDEFAB-CDEF-4ABC-8DEF-ABCDEFABCDEF", 77, (), "text"),)
        )[0]

        self.assertEqual(lower.runtime_id, upper.runtime_id)
        self.assertEqual(lower.source_mod_id, "ABCDEFAB-CDEF-4ABC-8DEF-ABCDEFABCDEF")


class AutomaticActivityTextDiscoveryTests(unittest.TestCase):
    def test_arbitrary_package_rows_symbols_and_text_are_discovered(self):
        source = _gpl(
            """expression #Completely_Custom_Label 47
function Show_Custom(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Completely_Custom_Label);
end
"""
        )

        binding = discover_private_activity_text_bindings(
            (
                ActivityTextDiscoveryPackage(
                    owner="arbitrary-mod",
                    source_mod_id="91234567-89AB-4CDE-8F01-23456789ABCD",
                    changes=((47, b"An entirely arbitrary message"),),
                    stock_rows=((47, b""),),
                    gpl_sources=(source,),
                ),
            )
        )[0]

        self.assertEqual(binding.source_index, 47)
        self.assertEqual(binding.expressions, ("#Completely_Custom_Label",))
        self.assertEqual(
            binding.package_expressions, ("#Completely_Custom_Label",)
        )
        self.assertEqual(binding.expected_text, "An entirely arbitrary message")

    def test_multiple_aliases_and_all_three_stock_consumers_share_one_id(self):
        source = _gpl(
            """expression #First_Alias 211
expression #Second_Alias 211
function Show_Custom(agent ThisAgent) is
begin
    $SpecifyIntent
    (
        ThisAgent,
        #First_Alias
    );
    $MessageFlag(ThisAgent, #Second_Alias);
    $LocalChatMessage($GetUnitPlayerNumber(ThisAgent), #First_Alias, ThisAgent);
end
"""
        )
        binding = _discover(source, 211)

        self.assertEqual(
            binding.expressions, ("#First_Alias", "#Second_Alias")
        )
        rewritten = rewrite_private_activity_text_resolver_calls(
            {"mod": [source]}, (binding,)
        )["mod"]
        self.assertTrue(
            rewritten[0].items[0].text.startswith("expression #MMM_AITX_")
        )
        rendered = "".join(item.text for value in rewritten for item in value.items)
        self.assertNotIn("expression #First_Alias 211", rendered)
        self.assertNotIn("expression #Second_Alias 211", rendered)
        self.assertEqual(rendered.count(binding.generated_expression), 4)
        self.assertIn(
            f"expression {binding.generated_expression} {binding.runtime_id}",
            rendered,
        )

    def test_exact_numeric_resolver_argument_needs_no_package_expression(self):
        source = _gpl(
            """function Show_Custom(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, 73);
end
"""
        )
        binding = _discover(source, 73)

        self.assertEqual(binding.expressions, ())
        rewritten = rewrite_private_activity_text_resolver_calls(
            {"mod": [source]}, (binding,)
        )["mod"]
        rendered = "".join(item.text for value in rewritten for item in value.items)
        self.assertIn(
            f"$SpecifyIntent(ThisAgent, {binding.generated_expression})", rendered
        )

    def test_stock_defined_symbol_fallback_supports_owner_call_localization(self):
        source = _gpl(
            """function Capture(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #intent_from_stock);
end
"""
        )
        binding = discover_private_activity_text_bindings(
            (
                ActivityTextDiscoveryPackage(
                    owner="mod",
                    source_mod_id=MOD_A,
                    changes=((117, b"Capturing a monster"),),
                    stock_rows=((117, b""),),
                    gpl_sources=(source,),
                ),
            ),
            stock_integer_expressions={"#Intent_From_Stock": 117},
        )[0]

        self.assertEqual(binding.expressions, ("#intent_from_stock",))
        self.assertEqual(binding.package_expressions, ())

    def test_two_mods_may_reuse_one_owner_local_alias_for_distinct_rows(self):
        first_source = _gpl(
            """expression #Shared_Private_Text 401
function First_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Shared_Private_Text);
end
""",
            name="first.gpl",
        )
        second_source = _gpl(
            """expression #Shared_Private_Text 402
function Second_Show(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, #Shared_Private_Text);
end
""",
            name="second.gpl",
        )
        bindings = discover_private_activity_text_bindings(
            (
                ActivityTextDiscoveryPackage(
                    owner="first-mod",
                    source_mod_id=MOD_A,
                    changes=((401, b"First private text"),),
                    stock_rows=((401, b""),),
                    gpl_sources=(first_source,),
                ),
                ActivityTextDiscoveryPackage(
                    owner="second-mod",
                    source_mod_id=MOD_B,
                    changes=((402, b"Second private text"),),
                    stock_rows=((402, b""),),
                    gpl_sources=(second_source,),
                ),
            )
        )

        rewritten = rewrite_private_activity_text_resolver_calls(
            {"first-mod": [first_source], "second-mod": [second_source]},
            bindings,
        )
        merged = merge_sources([], rewritten)
        merged.require_clean()
        rendered = "".join(item.text for item in merged.items)

        self.assertEqual(len({binding.runtime_id for binding in bindings}), 2)
        self.assertNotIn("expression #Shared_Private_Text", rendered)
        for binding in bindings:
            self.assertIn(
                f"expression {binding.generated_expression} {binding.runtime_id}",
                rendered,
            )

    def test_package_alias_removal_rejects_cross_owner_nonresolver_dependency(self):
        first_source = _gpl(
            """expression #First_Private_Text 411
function First_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #First_Private_Text);
end
""",
            name="first.gpl",
        )
        second_source = _gpl(
            """expression #Second_Private_Text 412
function Second_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Second_Private_Text);
    if (#First_Private_Text == 411)
        $NoOp();
end
""",
            name="second.gpl",
        )
        bindings = discover_private_activity_text_bindings(
            (
                ActivityTextDiscoveryPackage(
                    owner="first-mod",
                    source_mod_id=MOD_A,
                    changes=((411, b"First private text"),),
                    stock_rows=((411, b""),),
                    gpl_sources=(first_source,),
                ),
                ActivityTextDiscoveryPackage(
                    owner="second-mod",
                    source_mod_id=MOD_B,
                    changes=((412, b"Second private text"),),
                    stock_rows=((412, b""),),
                    gpl_sources=(second_source,),
                ),
            )
        )

        with self.assertRaisesRegex(IntentTextError, "cannot be safely removed"):
            rewrite_private_activity_text_resolver_calls(
                {"first-mod": [first_source], "second-mod": [second_source]},
                bindings,
            )

    def test_nonblank_stock_row_repurposing_is_not_auto_accepted(self):
        source = _gpl(
            """function Capture(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #intent_from_stock);
end
"""
        )
        with self.assertRaisesRegex(IntentTextError, "non-placeholder stock text"):
            discover_private_activity_text_bindings(
                (
                    ActivityTextDiscoveryPackage(
                        owner="mod",
                        source_mod_id=MOD_A,
                        changes=((117, b"Capturing a monster"),),
                        stock_rows=((117, b"Arresting a hooligan"),),
                        gpl_sources=(source,),
                    ),
                ),
                stock_integer_expressions={"#Intent_From_Stock": 117},
            )

        placeholder = ActivityTextDiscoveryPackage(
            owner="mod",
            source_mod_id=MOD_A,
            changes=((177, b"Private warning"),),
            stock_rows=((177, b"empty"),),
            gpl_sources=(
                _gpl(
                    """expression #Private_Warning 177
function Warn(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, #Private_Warning);
end
"""
                ),
            ),
        )
        self.assertEqual(
            discover_private_activity_text_bindings((placeholder,))[0].source_index,
            177,
        )

    def test_dynamic_only_or_missing_mapping_is_rejected(self):
        dynamic = _gpl(
            """function Show_Custom(agent ThisAgent) is
declare
    integer Which_Text;
begin
    Which_Text = $GetDynamicText();
    $SpecifyIntent(ThisAgent, Which_Text);
end
"""
        )
        with self.assertRaisesRegex(IntentTextError, "dynamic-only"):
            _discover(dynamic, 88)

        mixed_direct_and_dynamic = _gpl(
            """function Show_Custom(agent ThisAgent) is
declare
    integer Which_Text;
begin
    $SpecifyIntent(ThisAgent, 88);
    Which_Text = 88;
    $SpecifyIntent(ThisAgent, Which_Text);
end
"""
        )
        with self.assertRaisesRegex(IntentTextError, "decimal AITX row 88"):
            _discover(mixed_direct_and_dynamic, 88)

    def test_nonresolver_symbol_use_is_rejected_but_comments_and_strings_are_ignored(self):
        unsafe = _gpl(
            """expression #Private_Text 91
function Show_Custom(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Private_Text);
    if (#Private_Text == 91)
        $NoOp();
end
"""
        )
        with self.assertRaisesRegex(IntentTextError, "non-resolver"):
            _discover(unsafe, 91)

        safe = _gpl(
            """expression #Private_Text 91
function Show_Custom(agent ThisAgent) is
begin
    // #Private_Text is documentation, not a use.
    $Log("#Private_Text");
    $SpecifyIntent(ThisAgent, #Private_Text);
end
"""
        )
        binding = _discover(safe, 91)
        rewritten = rewrite_private_activity_text_resolver_calls(
            {"mod": [safe]}, (binding,)
        )["mod"]
        rendered = "".join(item.text for value in rewritten for item in value.items)
        self.assertIn("// #Private_Text is documentation", rendered)
        self.assertIn('$Log("#Private_Text")', rendered)

    def test_final_resolution_call_sites_are_rewritten_and_ambiguous_rows_reject(self):
        source = _gpl(
            """expression #Private_Text 101
function Show_Custom(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Private_Text);
end
"""
        )
        binding = _discover(source, 101)
        resolution = _gpl(
            """function Resolution(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, #Private_Text);
end
""",
            name="resolution.gpl",
        ).items[0]
        rewritten = rewrite_unowned_private_activity_text_resolver_calls(
            (resolution,), (binding,)
        )
        self.assertIn(binding.generated_expression, rewritten[0].text)

        other = allocate_private_activity_text_ids(
            (("other", MOD_B, 101, (), "other text"),)
        )[0]
        numeric_resolution = _gpl(
            """function Resolution(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, 101);
end
"""
        ).items[0]
        with self.assertRaisesRegex(IntentTextError, "ambiguous"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (numeric_resolution,), (binding, other)
            )

        colliding_resolution = _gpl(
            f"expression {binding.generated_expression} {binding.runtime_id}\n",
            name="colliding-resolution.gpl",
        ).items[0]
        with self.assertRaisesRegex(IntentTextError, "reserved generated"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (colliding_resolution,), (binding,)
            )

        alias_identity_resolution = _gpl(
            """function Resolution(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, #Private_Text);
    if (#Private_Text == 101)
        $NoOp();
end
"""
        ).items[0]
        with self.assertRaisesRegex(IntentTextError, "non-resolver use"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (alias_identity_resolution,), (binding,)
            )

        numeric_identity_resolution = _gpl(
            """function Resolution(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, 101);
    if (101 == 101)
        $NoOp();
end
"""
        ).items[0]
        with self.assertRaisesRegex(IntentTextError, "private AITX row 101"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (numeric_identity_resolution,), (binding,)
            )

    def test_resolution_uses_complete_environment_for_alternative_exact_alias(self):
        owner_source = _gpl(
            """expression #Original_Private_Alias 121
function Owner_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Original_Private_Alias);
end
"""
        )
        binding = _discover(owner_source, 121)
        alternative_definition = _gpl(
            "expression #Alternative_Stock_Alias 121\n",
            name="stock-defines.gpl",
        )
        environment = collect_integer_expression_environment(
            (owner_source, alternative_definition)
        )
        resolution = _gpl(
            """function Resolution(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, #Alternative_Stock_Alias);
end
""",
            name="resolution.gpl",
        ).items[0]

        rewritten = rewrite_unowned_private_activity_text_resolver_calls(
            (resolution,),
            (binding,),
            integer_expression_environment=environment,
        )

        self.assertIn(binding.generated_expression, rewritten[0].text)
        self.assertNotIn("#Alternative_Stock_Alias", rewritten[0].text)

        identity_use = _gpl(
            """function Resolution(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, #Alternative_Stock_Alias);
    if (#Alternative_Stock_Alias == 121)
        $NoOp();
end
"""
        ).items[0]
        with self.assertRaisesRegex(IntentTextError, "non-resolver use"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (identity_use,),
                (binding,),
                integer_expression_environment=environment,
            )

    def test_resolution_rejects_ambiguous_nonexact_or_unknown_aliases(self):
        owner_source = _gpl(
            """expression #Private_Alias 131
function Owner_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Private_Alias);
end
"""
        )
        binding = _discover(owner_source, 131)
        ambiguous_environment = collect_integer_expression_environment(
            (
                _gpl("expression #Other_Alias 131\n", name="one.gpl"),
                _gpl("expression #Other_Alias 55\n", name="two.gpl"),
            )
        )
        ambiguous_resolution = _gpl(
            """function Resolution(agent ThisAgent) is
begin
    $MessageFlag(ThisAgent, #Other_Alias);
end
"""
        ).items[0]
        with self.assertRaisesRegex(IntentTextError, "ambiguous"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (ambiguous_resolution,),
                (binding,),
                integer_expression_environment=ambiguous_environment,
            )

        nonexact_environment = collect_integer_expression_environment(
            (_gpl("expression #Other_Alias 130 + 1\n"),)
        )
        with self.assertRaisesRegex(IntentTextError, "non-exact"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (ambiguous_resolution,),
                (binding,),
                integer_expression_environment=nonexact_environment,
            )

        with self.assertRaisesRegex(IntentTextError, "no exact definition"):
            rewrite_unowned_private_activity_text_resolver_calls(
                (ambiguous_resolution,),
                (binding,),
                integer_expression_environment=IntegerExpressionEnvironment(
                    exact_values={}, nonexact_names=frozenset()
                ),
            )

    def test_unrelated_owner_numeric_resolver_is_not_hijacked(self):
        owner_source = _gpl(
            """expression #Private_Text 141
function Owner_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Private_Text);
end
""",
            name="owner.gpl",
        )
        unrelated_source = _gpl(
            """function Other_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, 141);
end
""",
            name="unrelated.gpl",
        )
        binding = _discover(owner_source, 141)
        rewritten = rewrite_private_activity_text_resolver_calls(
            {"mod": [owner_source], "unrelated": [unrelated_source]},
            (binding,),
        )

        unrelated_text = "".join(
            item.text for source in rewritten["unrelated"] for item in source.items
        )
        self.assertIn("$SpecifyIntent(ThisAgent, 141)", unrelated_text)
        self.assertNotIn(binding.generated_expression, unrelated_text)

        final_items = tuple(
            item for sources in rewritten.values() for source in sources for item in source.items
        )
        # Numeric equality is deliberately owner-local, but an exact private
        # alias left in another owner's resolver call must fail the final audit.
        alias_user = _gpl(
            """function Alias_User(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Private_Text);
end
"""
        ).items[0]
        with self.assertRaisesRegex(IntentTextError, "cross-owner resolver"):
            audit_private_activity_text_resolver_aliases(
                (*final_items, alias_user), (binding,)
            )

    def test_generated_expression_collision_in_any_owner_is_rejected(self):
        owner_source = _gpl(
            """expression #Private_Text 151
function Owner_Show(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Private_Text);
end
""",
            name="owner.gpl",
        )
        binding = _discover(owner_source, 151)
        unrelated_source = _gpl(
            f"expression {binding.generated_expression} {binding.runtime_id}\n",
            name="unrelated.gpl",
        )

        with self.assertRaisesRegex(IntentTextError, "preexisting GPL reference"):
            rewrite_private_activity_text_resolver_calls(
                {"mod": [owner_source], "unrelated": [unrelated_source]},
                (binding,),
            )

        reference_only = _gpl(
            f"""function Other_Show(agent ThisAgent) is
begin
    $NoOp({binding.generated_expression});
end
""",
            name="reference-only.gpl",
        )
        with self.assertRaisesRegex(IntentTextError, "preexisting GPL reference"):
            rewrite_private_activity_text_resolver_calls(
                {"mod": [owner_source], "unrelated": [reference_only]},
                (binding,),
            )

        stock_collision = IntegerExpressionEnvironment(
            exact_values={
                binding.generated_expression.casefold(): (binding.runtime_id,)
            },
            nonexact_names=frozenset(),
        )
        with self.assertRaisesRegex(IntentTextError, "selected/stock GPL"):
            rewrite_private_activity_text_resolver_calls(
                {"mod": [owner_source]},
                (binding,),
                integer_expression_environment=stock_collision,
            )

    def test_empty_or_malformed_private_text_is_rejected(self):
        source = _gpl(
            """expression #Private_Text 12
function Show_Custom(agent ThisAgent) is
begin
    $SpecifyIntent(ThisAgent, #Private_Text);
end
"""
        )
        with self.assertRaisesRegex(IntentTextError, "invalid length/content"):
            discover_private_activity_text_bindings(
                (
                    ActivityTextDiscoveryPackage(
                        owner="mod",
                        source_mod_id=MOD_A,
                        changes=((12, b""),),
                        stock_rows=((12, b""),),
                        gpl_sources=(source,),
                    ),
                )
            )

        with self.assertRaisesRegex(IntentTextError, "invalid length/content"):
            discover_private_activity_text_bindings(
                (
                    ActivityTextDiscoveryPackage(
                        owner="mod",
                        source_mod_id=MOD_A,
                        changes=((12, b"embedded\x00nul"),),
                        stock_rows=((12, b""),),
                        gpl_sources=(source,),
                    ),
                )
            )


class PrivateAitxDetachmentTests(unittest.TestCase):
    def test_discovered_stock_override_and_append_are_removed(self):
        stock = _table("stock zero", "stock one")
        modified = _table("stock zero", "private warning", "private visit")
        bindings = allocate_private_activity_text_ids(
            (
                ("mod", MOD_A, 1, "#Warning", "private warning"),
                ("mod", MOD_A, 2, "#Visit", "private visit"),
            )
        )

        sanitized, detached = _detach_private_activity_texts(
            stock, (("mod", modified),), bindings
        )

        self.assertEqual(sanitized[0][1], stock)
        self.assertEqual({record.text for record in detached}, {b"private warning", b"private visit"})

    def test_undiscovered_or_stale_rows_fail_closed(self):
        stock = _table("stock")
        modified = _table("stock", "private")
        with self.assertRaisesRegex(ComposeError, "not discovered"):
            _detach_private_activity_texts(stock, (("mod", modified),), ())

        stale = allocate_private_activity_text_ids(
            (
                ("mod", MOD_A, 1, "#Visit", "private"),
                ("mod", MOD_A, 2, "#Missing", "missing"),
            )
        )
        with self.assertRaisesRegex(ComposeError, "unchanged/missing"):
            _detach_private_activity_texts(stock, (("mod", modified),), stale)

    def test_discovered_text_must_match_exactly(self):
        stock = _table("stock")
        modified = _table("stock", "actual")
        binding = allocate_private_activity_text_ids(
            (("mod", MOD_A, 1, "#Visit", "stale metadata"),)
        )
        with self.assertRaisesRegex(ComposeError, "does not match"):
            _detach_private_activity_texts(stock, (("mod", modified),), binding)

    def test_truncated_provider_is_rejected_as_incomplete(self):
        stock = _table("stock zero", "stock one")
        truncated = _table("stock zero")

        with self.assertRaisesRegex(ComposeError, "AITX provider is truncated"):
            _detach_private_activity_texts(stock, (("mod", truncated),), ())


def _table(*texts: str) -> StrtTable:
    return StrtTable(
        version=b"\x00\x00",
        records=tuple(
            StrtRecord(index, text.encode("cp1252"))
            for index, text in enumerate(texts)
        ),
    )


def _gpl(text: str, *, name: str = "fixture.gpl"):
    return parse_gpl(text, name)


def _discover(source, row: int):
    return discover_private_activity_text_bindings(
        (
            ActivityTextDiscoveryPackage(
                owner="mod",
                source_mod_id=MOD_A,
                changes=((row, b"private text"),),
                stock_rows=((row, b""),),
                gpl_sources=(source,),
            ),
        )
    )[0]


if __name__ == "__main__":
    unittest.main()
