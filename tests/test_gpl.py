from pathlib import Path
import sys
import textwrap
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.gpl import (
    ConflictKind,
    DefinitionKind,
    DuplicateDefinitionError,
    SemanticItem,
    SemanticMergeConflictError,
    find_foreach_return_violations,
    merge_semantic_items,
    merge_sources,
    add_inventory_death_drop_exclusions,
    add_purchase_bazaar_tail_callbacks,
    add_purchase_equipment_tail_callbacks,
    parse_dat,
    parse_gpl,
    require_complete_semantic_coverage,
    rewrite_integer_expression,
    semantic_key,
)


class GplParsingTests(unittest.TestCase):
    def test_foreach_return_scan_handles_blocks_single_statements_and_case(self):
        source = textwrap.dedent(
            """\
            Function Unsafe(agent ThisAgent) is agent
            Begin
                FOREACH candidate in candidates DO
                    BeGiN
                        if (candidate == ThisAgent)
                            ReTuRn candidate;
                    EnD

                foreach fallback in candidates do
                    if ($IsValidGamePiece(fallback))
                        return fallback;
            End
            """
        )

        violations = find_foreach_return_violations(source, "unsafe.gpl")

        self.assertEqual(
            [
                (item.source_name, item.return_line, item.foreach_line)
                for item in violations
            ],
            [
                ("unsafe.gpl", 6, 3),
                ("unsafe.gpl", 11, 9),
            ],
        )

    def test_foreach_return_scan_ignores_comments_strings_and_post_loop_return(self):
        source = textwrap.dedent(
            '''\
            Function Safe(agent ThisAgent) is agent
            Declare
                agent selected;
            Begin
                // foreach candidate in candidates do return candidate;
                selected's "return foreach do begin end" = "return";
                foreach candidate in candidates do
                    begin
                        selected = candidate; /* return candidate; */
                    end
                return selected;
            End
            '''
        )

        self.assertEqual(find_foreach_return_violations(source, "safe.gpl"), ())

    def test_complete_coverage_accepts_only_comments_and_whitespace_in_gaps(self):
        source = parse_gpl(
            "// prefix\n"
            + _function("First", "return 1;")
            + "/* between */\n"
            + _function("Second", "return 2;")
            + "// trailing\n",
            "comments.gpl",
        )

        require_complete_semantic_coverage(source)

    def test_complete_coverage_rejects_code_in_every_unparsed_gap(self):
        valid = _function("First", "return 1;")
        second = _function("Second", "return 2;")
        cases = {
            "prefix": "Include \"other.gpl\"\n" + valid,
            "between": valid + "UnknownDirective 7\n" + second,
            "trailing": valid + "RunThread Hidden();\n",
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                source = parse_gpl(text, f"{label}.gpl")
                with self.assertRaisesRegex(
                    ValueError, "unparsed semantic-source text"
                ):
                    require_complete_semantic_coverage(source)

    def test_complete_coverage_rejects_unterminated_block_comment(self):
        source = parse_gpl(
            _function("First", "return 1;") + "/* never closed",
            "unterminated-comment.gpl",
        )

        with self.assertRaisesRegex(ValueError, "unparsed semantic-source text"):
            require_complete_semantic_coverage(source)

    def test_rewrites_only_an_exact_declared_integer_expression(self):
        item = parse_gpl(
            "expression #Intent_Applying_Oil 309 // private AITX row\n",
            "oil.gpl",
        ).items[0]

        rewritten = rewrite_integer_expression(
            item,
            expected_value=309,
            replacement_value=0x61234567,
        )

        self.assertEqual(
            rewritten.text,
            "expression #Intent_Applying_Oil 1629701479 // private AITX row\n",
        )
        with self.assertRaisesRegex(ValueError, "expected 310"):
            rewrite_integer_expression(
                item,
                expected_value=310,
                replacement_value=0x61234567,
            )

    def test_integer_expression_rewrite_rejects_compound_numeric_source(self):
        item = parse_gpl(
            "expression #Intent_Applying_Oil 300 + 9\n", "compound.gpl"
        ).items[0]
        with self.assertRaisesRegex(ValueError, "not an exact decimal integer"):
            rewrite_integer_expression(
                item,
                expected_value=309,
                replacement_value=0x61234567,
            )

    def test_parses_functions_expressions_spans_and_nested_begin_end(self):
        source = textwrap.dedent(
            """\
            // Stock confidence value.
            expression #Spell_Confidence 10

            Function Random_Hero_Type(agent ThisAgent) is string
            Declare
                integer Roll;
            Begin
                // begin and end in a comment do not alter nesting.
                if (Roll == 1)
                    begin
                        return "the word end is data";
                    end
                return "Wizard";
            End

            function spell_extra_value(agent thisagent) is integer
            begin
                return #Spell_Confidence;
            end
            """
        )

        parsed = parse_gpl(source, "stock.gpl")

        self.assertEqual(parsed.render(), source)
        self.assertEqual(
            [item.kind for item in parsed.items],
            [
                DefinitionKind.EXPRESSION,
                DefinitionKind.FUNCTION,
                DefinitionKind.FUNCTION,
            ],
        )
        random_hero = parsed.require("FUNCTION", "random_hero_type")
        confidence = parsed.require("expression", "#SPELL_CONFIDENCE")
        self.assertEqual(random_hero.name, "Random_Hero_Type")
        self.assertEqual(random_hero.span.start_line, 4)
        self.assertEqual(random_hero.span.extract(source), random_hero.text)
        self.assertEqual(confidence.span.extract(source), confidence.text)
        self.assertIsNone(parsed.get("function", "missing"))

    def test_duplicate_gpl_names_are_case_insensitive_and_structured(self):
        source = textwrap.dedent(
            """\
            Function Damage(agent Attacker, agent Defender)
            Begin
            End

            function DAMAGE(agent attacker, agent defender)
            begin
            end
            """
        )

        with self.assertRaises(DuplicateDefinitionError) as raised:
            parse_gpl(source, "duplicate.gpl")

        self.assertEqual(
            raised.exception.key,
            semantic_key(DefinitionKind.FUNCTION, "damage"),
        )
        self.assertEqual(raised.exception.first.span.start_line, 1)
        self.assertEqual(raised.exception.duplicate.span.start_line, 5)

    def test_duplicate_expressions_are_case_insensitive(self):
        with self.assertRaises(DuplicateDefinitionError):
            parse_gpl(
                "expression #Private_Value 1\nexpression #PRIVATE_VALUE 2\n",
                "expressions.gpl",
            )

    def test_parses_dat_blocks_case_insensitively_and_reconstructs_source(self):
        source = textwrap.dedent(
            """\
            // Building data.
            [AlchemistsLaboratory1]
                {Guild
                    (title AlchemistsLaboratory)
                }
            [end]

            [Alchemist]
                {Hero
                    (title Alchemist)
                }
            [END]
            """
        )

        parsed = parse_dat(source, "Alchemist_Data.dat")

        self.assertEqual(parsed.render(), source)
        self.assertEqual(len(parsed.items), 2)
        laboratory = parsed.require("dat", "alchemistSLABORATORY1")
        self.assertEqual(laboratory.name, "AlchemistsLaboratory1")
        self.assertEqual(laboratory.span.extract(source), laboratory.text)

    def test_duplicate_dat_blocks_are_case_insensitive(self):
        source = "[Phantom]\n{Hero}\n[end]\n[PHANTOM]\n{Hero}\n[end]\n"
        with self.assertRaises(DuplicateDefinitionError):
            parse_dat(source, "heroes.dat")


class SemanticMergeTests(unittest.TestCase):
    def test_purchase_bazaar_tail_runs_after_all_bazaar_items(self):
        stock = parse_gpl(_purchase_bazaar(), "stock-bazaar.gpl")
        callback = parse_gpl(_boolean_callback("Zoo_Rental_Check"), "zoo.gpl")
        merged = merge_sources([], {"zoo": [callback]})

        result = add_purchase_bazaar_tail_callbacks(
            merged,
            ("Zoo_Rental_Check",),
            stock_purchase_bazaar=stock.require("function", "Purchase_Bazaar"),
        )

        text = result.emit_project_source_set().gpl_text
        bazaar = text[text.index("Function Purchase_Bazaar"):]
        self.assertLess(bazaar.index("#Bazaar_Item_Six"), bazaar.index("$Bazaar_Item_Check"))
        self.assertLess(bazaar.index("$Bazaar_Item_Check"), bazaar.index("$Zoo_Rental_Check"))
        self.assertLess(bazaar.index("$Zoo_Rental_Check"), bazaar.index('ActiveScript" = $Use_Building'))

    def test_purchase_bazaar_tail_fails_closed_if_item_chain_changes(self):
        malformed = parse_gpl(
            _purchase_bazaar().replace("#Bazaar_Item_Six", "#Private_Item"),
            "malformed-bazaar.gpl",
        )
        callback = parse_gpl(_boolean_callback("Zoo_Rental_Check"), "zoo.gpl")
        with self.assertRaisesRegex(ValueError, "complete recognized stock"):
            add_purchase_bazaar_tail_callbacks(
                merge_sources([], {"zoo": [callback]}),
                ("Zoo_Rental_Check",),
                stock_purchase_bazaar=malformed.require("function", "Purchase_Bazaar"),
            )

    def test_purchase_equipment_tail_runs_after_stock_chain_and_uses_stock_final(self):
        stock = parse_gpl(_purchase_equipment(), "stock-purchase.gpl")
        callbacks = parse_gpl(
            _boolean_callback("Zoo_Rental_Check")
            + _boolean_callback("Another_Mod_Check"),
            "callbacks.gpl",
        )
        merged = merge_sources([], {"custom": [callbacks]})

        result = add_purchase_equipment_tail_callbacks(
            merged,
            ("Another_Mod_Check", "Zoo_Rental_Check"),
            stock_purchase_equipment=stock.require("function", "Purchase_Equipment"),
        )

        emitted = result.emit_project_source_set().gpl_text
        self.assertLess(emitted.index("$Stat_Boost_Check"), emitted.index("$Another_Mod_Check"))
        self.assertLess(emitted.index("$Another_Mod_Check"), emitted.index("$Zoo_Rental_Check"))
        self.assertLess(emitted.index("$Zoo_Rental_Check"), emitted.index('ThisAgent\'s "ActiveScript" = $Use_Building'))
        self.assertEqual(emitted.count('ThisAgent\'s "ActiveScript" = $Use_Building'), 1)

    def test_purchase_equipment_tail_preserves_existing_package_additions(self):
        modified = _purchase_equipment().replace(
            "If ($Poison_Check (ThisAgent))",
            "If ($Alchemy_Oil_Check (ThisAgent,alchemyLabs))\n"
            "            Flag = TRUE;\n"
            "        Else\n"
            "        If ($Poison_Check (ThisAgent))",
        )
        source = parse_gpl(modified + _boolean_callback("Zoo_Rental_Check"), "combined.gpl")
        merged = merge_sources([], {"combined": [source]})

        result = add_purchase_equipment_tail_callbacks(
            merged, ("Zoo_Rental_Check",)
        )

        emitted = result.emit_project_source_set().gpl_text
        self.assertIn("$Alchemy_Oil_Check", emitted)
        self.assertLess(emitted.index("$Alchemy_Oil_Check"), emitted.index("$Stat_Boost_Check"))
        self.assertLess(emitted.index("$Stat_Boost_Check"), emitted.index("$Zoo_Rental_Check"))

    def test_purchase_equipment_tail_fails_closed_on_unknown_shape(self):
        callback = parse_gpl(_boolean_callback("Zoo_Rental_Check"), "callback.gpl")
        malformed = parse_gpl(
            _purchase_equipment().replace("$Stat_Boost_Check", "$Different_Final_Check"),
            "malformed.gpl",
        )
        merged = merge_sources([], {"callback": [callback]})

        with self.assertRaisesRegex(ValueError, "complete recognized stock"):
            add_purchase_equipment_tail_callbacks(
                merged,
                ("Zoo_Rental_Check",),
                stock_purchase_equipment=malformed.require("function", "Purchase_Equipment"),
            )

    def test_composes_private_numeric_item_into_stock_death_drop_exclusions(self):
        source = parse_gpl(
            textwrap.dedent(
                """\
                Expression #PrivateNumericItem 113

                Function Hero_Drop_Quest_Items (agent ThisAgent)
                Declare
                    integer WhatItem;
                Begin
                    If (WhatItem != #QItem_Magic_Sword &&
                        WhatItem != #MarketItem_Ring_Protection &&
                        WhatItem != #MarketItem_Market3_Item)
                        begin
                            If ($CanDropInventoryItem(WhatItem) == True)
                                $SpawnUnit(ThisAgent, "Special_Item");
                        end
                End
                """
            ),
            "stock-death.gpl",
        )
        merged = merge_sources([], {"haunt": [source]})

        result = add_inventory_death_drop_exclusions(
            merged, ("#PrivateNumericItem",)
        )

        emitted = result.emit_project_source_set().gpl_text
        self.assertIn(
            "WhatItem != #MarketItem_Market3_Item &&\n"
            "        WhatItem != #PrivateNumericItem)",
            emitted,
        )
        self.assertLess(
            emitted.index("#PrivateNumericItem", emitted.index("Function")),
            emitted.index("$CanDropInventoryItem"),
        )

    def test_death_drop_composition_rejects_undefined_numeric_expression(self):
        source = parse_gpl(
            _function("Hero_Drop_Quest_Items", "return 1;"),
            "stock-death.gpl",
        )
        merged = merge_sources([], {"custom": [source]})

        with self.assertRaisesRegex(ValueError, "missing: #MissingPrivateItem"):
            add_inventory_death_drop_exclusions(
                merged, ("#MissingPrivateItem",)
            )

    def test_death_drop_composition_fails_closed_on_non_stock_shape(self):
        source = parse_gpl(
            "Expression #PrivateNumericItem 113\n\n"
            + _function("Hero_Drop_Quest_Items", "return 1;"),
            "custom-death.gpl",
        )
        merged = merge_sources([], {"custom": [source]})

        with self.assertRaisesRegex(ValueError, "recognized stock"):
            add_inventory_death_drop_exclusions(
                merged, ("#PrivateNumericItem",)
            )

    def test_n_way_merge_unions_additions_and_accepts_identical_changes(self):
        vanilla = parse_gpl(
            _function("Stock_Only", 'return "stock";')
            + _function("Shared", 'return "stock";'),
            "vanilla.gpl",
        )
        shared_change = _function("Shared", 'return "same merged change";')
        haunt = parse_gpl(
            shared_change + _function("Phantom_Only", 'return "Phantom";'),
            "haunt.gpl",
        )
        alchemist = parse_gpl(
            shared_change + _function("Alchemist_Only", 'return "Alchemist";'),
            "alchemist.gpl",
        )

        result = merge_sources(
            [vanilla],
            {"haunt": [haunt], "alchemist": [alchemist]},
        )

        self.assertTrue(result.is_clean)
        self.assertEqual(
            [item.name for item in result.items],
            ["Stock_Only", "Shared", "Phantom_Only", "Alchemist_Only"],
        )
        self.assertIn("same merged change", result.render())

    def test_known_random_hero_and_spell_confidence_shape_is_two_conflicts(self):
        vanilla = parse_gpl(
            _function("Random_Hero_Type", 'return "Paladin";')
            + _function("spell_extra_value", "return 0;"),
            "stock.gpl",
        )
        haunt = parse_gpl(
            _function("Random_Hero_Type", 'return "Phantom";')
            + _function("spell_extra_value", "return 30;"),
            "haunt.gpl",
        )
        alchemist = parse_gpl(
            _function("Random_Hero_Type", 'return "Alchemist";')
            + _function("spell_extra_value", "return 100;"),
            "alchemist.gpl",
        )

        result = merge_sources(
            [vanilla],
            {"haunt": [haunt], "alchemist": [alchemist]},
        )

        self.assertFalse(result.is_clean)
        self.assertEqual(
            [conflict.key for conflict in result.conflicts],
            [
                semantic_key("function", "Random_Hero_Type"),
                semantic_key("function", "spell_extra_value"),
            ],
        )
        for conflict in result.conflicts:
            self.assertEqual(conflict.kind, ConflictKind.DIVERGENT_MODIFICATION)
            self.assertEqual(
                [variant.side_name for variant in conflict.variants],
                ["haunt", "alchemist"],
            )
            self.assertIsNotNone(conflict.vanilla)
        with self.assertRaises(SemanticMergeConflictError) as raised:
            result.render()
        self.assertEqual(raised.exception.conflicts, result.conflicts)

    def test_explicit_resolutions_emit_compiler_ready_gpl_and_dat(self):
        vanilla_gpl = parse_gpl(
            _function("Random_Hero_Type", 'return "Paladin";'),
            "stock.gpl",
        )
        haunt_gpl = parse_gpl(
            _function("Random_Hero_Type", 'return "Phantom";'),
            "haunt.gpl",
        )
        alchemist_gpl = parse_gpl(
            _function("Random_Hero_Type", 'return "Alchemist";'),
            "alchemist.gpl",
        )
        haunt_dat = parse_dat("[Phantom]\n{Hero}\n[end]\n", "phantom.dat")
        alchemist_dat = parse_dat("[Alchemist]\n{Hero}\n[end]\n", "alchemist.dat")
        resolved = SemanticItem.resolved(
            DefinitionKind.FUNCTION,
            "Random_Hero_Type",
            _function("Random_Hero_Type", 'return "Phantom or Alchemist";'),
            "two-mod-resolution",
        )

        result = merge_sources(
            [vanilla_gpl],
            {
                "haunt": [haunt_gpl, haunt_dat],
                "alchemist": [alchemist_gpl, alchemist_dat],
            },
            {semantic_key("function", "random_hero_type"): resolved},
        )
        emitted = result.emit_project_source_set("Combined.gpl", "Combined.dat")

        self.assertTrue(result.is_clean)
        self.assertEqual(
            emitted.project_text,
            'data="Combined.dat"\nsource="Combined.gpl"\n',
        )
        self.assertIn("Phantom or Alchemist", emitted.gpl_text)
        self.assertLess(emitted.dat_text.index("[Phantom]"), emitted.dat_text.index("[Alchemist]"))
        self.assertEqual(
            set(emitted.files),
            {"Combined.gpl", "Combined.dat"},
        )

    def test_divergent_same_name_additions_are_conflicts(self):
        left = parse_gpl(_function("New_Hook", "return 1;"), "left.gpl")
        right = parse_gpl(_function("NEW_HOOK", "return 2;"), "right.gpl")

        result = merge_semantic_items(
            [],
            {"left": left.items, "right": right.items},
        )

        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(
            result.conflicts[0].kind,
            ConflictKind.DIVERGENT_ADDITION,
        )

    def test_duplicate_definition_across_files_on_one_side_is_rejected(self):
        first = parse_gpl(_function("damage", "return 1;"), "one.gpl")
        second = parse_gpl(_function("DAMAGE", "return 1;"), "two.gpl")

        with self.assertRaises(DuplicateDefinitionError) as raised:
            merge_sources([], {"one-mod": [first, second]})

        self.assertEqual(raised.exception.side_name, "one-mod")


def _purchase_equipment() -> str:
    return textwrap.dedent(
        """\
        Function Purchase_Equipment (agent ThisAgent) is boolean
        Declare
            boolean Flag;
        Begin
            If ($BlackSmith_Check (ThisAgent))
                Flag = TRUE;
            Else If ($BlackSmith_Check (ThisAgent))
                Flag = TRUE;
            Else If ($WizGuild_Check (ThisAgent))
                Flag = TRUE;
            Else If ($WizGuild_Check (ThisAgent))
                Flag = TRUE;
            Else If ($Poison_Check (ThisAgent))
                Flag = TRUE;
            Else If ($Potion_Check (ThisAgent,shops))
                Flag = TRUE;
            Else If ($Ring_Check (ThisAgent,markets))
                Flag = TRUE;
            Else If ($Market3_Check (ThisAgent,markets))
                Flag = TRUE;
            Else If ($Stat_Boost_Check (ThisAgent,fairgrounds))
                Flag = TRUE;

            If (Flag)
                begin
                    ThisAgent's "ActiveScript" = $Use_Building;
                    return TRUE;
                end

            return False;
        End

        """
    )


def _purchase_bazaar() -> str:
    return textwrap.dedent(
        """\
        Function Purchase_Bazaar (agent ThisAgent, integer bazaar_chance) is boolean
        Declare
            boolean Flag;
            list Item_list;
            integer Item;
        Begin
            Flag = FALSE;
            If (bazaar_chance > $RandomNumber (100) + 1)
                Flag = FALSE;
            $listobjects (ThisAgent, "building", 100, bazaars);
            Item_list << #Bazaar_Item_One;
            Item_list << #Bazaar_Item_Two;
            Item_list << #Bazaar_Item_Three;
            Item_list << #Bazaar_Item_Four;
            Item_list << #Bazaar_Item_Five;
            Item_list << #Bazaar_Item_Six;
            foreach Item in Item_list do
                begin
                    Bazaars_Researched = $Researched_Item (bazaars, Item);
                    Item_Cost = $Get_Bazaar_Cost (Item);
                    If ($Bazaar_Item_Check (ThisAgent, Item, Bazaars_Researched, Item_Cost))
                        Flag = TRUE;
                end
            If (Flag)
                begin
                    ThisAgent's "ActiveScript" = $Use_Building;
                    return TRUE;
                end
            return False;
        End

        """
    )


def _boolean_callback(name: str) -> str:
    return textwrap.dedent(
        f"""\
        Function {name} (agent ThisAgent) is boolean
        Begin
            return False;
        End

        """
    )


def _function(name: str, body: str) -> str:
    return textwrap.dedent(
        f"""\
        Function {name}() is string
        Begin
            {body}
        End

        """
    )


if __name__ == "__main__":
    unittest.main()
