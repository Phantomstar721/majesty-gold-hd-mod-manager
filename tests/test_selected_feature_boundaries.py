"""Installed source regression matrix; never prepares or writes a Manager profile.

The package paths deliberately identify the subscribed/development inputs that
exposed the integration failures. Missing installations may skip this fixture;
changed declarations, missing callbacks and unsupported boundaries must fail.
Each result is an isolated in-memory source fixture, not a resolved mod profile.
Production-path cases use the actual inventory and source-bundle entry points;
only compiler fixtures write disposable temporary language-project outputs.
"""
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from majesty_cam import compose as production
from majesty_cam.activity_time import add_activity_service
from majesty_cam.action_callback_bridge import add_bridges
from majesty_cam.building_toggle_state import add_state_functions, selected as toggles
from majesty_cam.compose import (
    _load_effective_stock_descriptions, _load_stock_hero_quest_lifecycle_items,
    _parse_inventory_gpl_sources,
    _private_hero_bindings, _shared_bindings, _typed_provider_dispatches,
    compile_gpl, validate_gpl_feature_evidence,
)
from majesty_cam.dataset_dependencies import DestinationSources, load_dataset_symbols
from majesty_cam.descriptions import merge_descriptions, parse_descriptions
from majesty_cam.gameplay_events import EVENT_FUNCTIONS, add_gameplay_event_observers
from majesty_cam.gpl import (
    DefinitionKind, SemanticMergeResult, add_controlled_follower_movement_adjustments,
    add_hero_quest_lifecycle_callbacks, add_purchase_bazaar_tail_callbacks, parse_gpl,
)
from majesty_cam.gpl_function_merge import _Parser, _code, _render, _tokens, merge_function
from majesty_cam.kingdom_research import KingdomResearch, registration
from majesty_cam.kingdom_research_gpl import compose_service as research_service
from majesty_cam.package import DescriptionsLoad, GplLoad, load_package
from majesty_cam.potion_policy import POTIONS, compose as potion_service
from majesty_cam.potion_policy import prepare_descriptions, selected as potion_policies
from majesty_cam.private_hero_gpl import add_spell_evaluation_equivalents
from majesty_cam.script_review import group_conflicts
from majesty_cam.shared_composition import event_subscribers
from majesty_cam.shared_features import EVENT_SIGNATURES, StockGameplayEventObserver, shared_callbacks
from majesty_cam.standard_scripts import _align_parameters, for_dataset, read as read_standard


ROOT = Path(__file__).resolve().parents[1]
STEAM = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD")
GOG = Path("C:/Program Files (x86)/GOG Galaxy/Games/Majesty Gold HD")
WORKSHOP = Path("C:/Program Files (x86)/Steam/steamapps/workshop/content/73230")
PACKAGES = (
    ("adventurers", WORKSHOP / "3804026997"),
    ("bards", Path.home() / "Documents/My Games/MajestyHD/Mods/CustomGuildBards"),
    ("alchemist", WORKSHOP / "3793509198"),
    ("phantoms", ROOT / "payload/mods/CustomGuildPhantomsHauntExpanded"),
    ("exploration", WORKSHOP / "3807983988"),
    ("menagerie", WORKSHOP / "3796459696"),
)
# Relative native precedence for all owners touched by the generated stages.
# The other selected Standard components do not own these GPL definitions.
NATIVE = (
    ("1965892371", "Misc Enhancements.mmxml", "DC034C13-BB90-4AA9-ABF4-55BE8C378C93", "Misc AI"),
    ("3743606613", "Monster Kingdom.mmxml", "BFA127E5-3AE4-47BF-BEE0-BDC27BAEE50C", "Monster Kingdom"),
    ("1965892371", "Misc Enhancements.mmxml", "97781481-45AB-4F64-9B40-ED662B603AE9", "Misc Attributes 2"),
    ("1965892371", "Misc Enhancements.mmxml", "709D51C7-FC4F-4EB2-B5B1-79B764BBEF1C", "Misc Other"),
)


def key(name):
    return DefinitionKind.FUNCTION, name.casefold()


def rendered(item):
    signature, declarations, body = _Parser(item.text).function()
    text = "\n".join((
        _code(signature), "declare",
        *(f"{kind} {name};" for name, kind in sorted(declarations.items())),
        "begin", *_render(body), "end", "",
    ))
    if _Parser(text).function() != (signature, declarations, body):
        raise AssertionError("regression fixture renderer changed instructions")
    return replace(item, text=text, span=None)


def functions(result):
    return {item.normalized_name: item for item in result.items
            if item.kind is DefinitionKind.FUNCTION}


def instructions(result):
    return {name: _Parser(item.text).function() for name, item in functions(result).items()}


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.body)
        yield from walk(node.otherwise)


def parse_nodes(text):
    return _Parser("function Fixture() begin\n" + text + "\nend").function()[2]


def source_functions(result):
    return {item.normalized_name: item for item in parse_gpl(result.source_set.gpl_text).items
            if item.kind is DefinitionKind.FUNCTION}


def bundle_functions(bundle, dataset):
    return {name: item for scope, result in bundle.outputs
            if scope == "Any" or scope.casefold() == dataset
            for name, item in source_functions(result).items()}


def without_observers(text, symbols):
    for symbol in symbols:
        text, count = re.subn(r"\$" + re.escape(symbol) + r"\s*\([^;]*\);", "", text, flags=re.I)
        if count != 1:
            raise AssertionError(f"expected one inserted observer {symbol}, found {count}")
    return _tokens(text)


class SelectedSourceFixture:
    """Explicit candidate views, with compiled native ownership and lazy helpers."""

    def __init__(self, game):
        self.game = game
        self.symbols = load_dataset_symbols(game)
        self.destinations = {dataset: DestinationSources(self.symbols, dataset)
                             for dataset in ("majesty", "majestyexpansion")}
        self.inventories = []
        self.authored = defaultdict(list)
        self.by_owner = {}
        self.records = {k: v[0] for k, v in _load_effective_stock_descriptions(game).items()}
        for alias, root in PACKAGES:
            package = load_package(root)
            directives = [x for dataset in package.datasets for block in dataset.loads
                          for x in block.directives]
            inventory = SimpleNamespace(
                selected=SimpleNamespace(alias=alias, package=package),
                gpl_loads=[x for x in directives if isinstance(x, GplLoad)],
                descriptions=[x.file.absolute_path for x in directives if isinstance(x, DescriptionsLoad)],
            )
            self.inventories.append(inventory)
            owned = {}
            for parsed in _parse_inventory_gpl_sources(inventory):
                for item in parsed.items:
                    if item.kind is DefinitionKind.FUNCTION:
                        self.authored[item.normalized_name].append(item)
                        owned[item.normalized_name] = item
            self.by_owner[alias] = owned
            for path in inventory.descriptions:
                self.records.update(parse_descriptions(path.read_bytes()).index)
        self.inventories = tuple(self.inventories)
        self.native = tuple(read_standard(SimpleNamespace(
            package_root=WORKSHOP / directory,
            manifest_path=WORKSHOP / directory / manifest,
            content_id=identifier, display_name=label,
        )) for directory, manifest, identifier, label in NATIVE)
        self.shared = _shared_bindings(self.inventories)
        self.subscribers = event_subscribers(self.shared)
        _, self.potions = prepare_descriptions(
            merge_descriptions(b"<Descriptions/>", ()), self.records,
            potion_policies(self.inventories),
        )
        self.callbacks = {symbol.casefold()
                          for binding in self.shared
                          for symbol, _, _ in shared_callbacks(binding.feature)}
        self.stock_names = {name for names in EVENT_FUNCTIONS.values() for name in names}
        self.stock_names.update(("shapeshift_potion_end", "give_gold", "give_exp"))
        self.potion_names = {action.effect.casefold() for action in self.potions.actions}
        self.potion_names.update(action.validation.casefold() for action in self.potions.actions
                                 if action.validation)
        self.potion_names.update(("bazaar_item_check", "alchemist_purchase_bazaar",
                                 "alchemist_purchase_nearby_bazaar"))
        self.potion_names.update("purchase_bazaar_item_" + number.casefold()
                                 for number, _ in POTIONS.values())
        self.early_evidence = validate_gpl_feature_evidence(self.inventories)
        self.hero_templates = _load_stock_hero_quest_lifecycle_items(
            game, sources=self.destinations["majestyexpansion"])[0]
        self.private_trees, self.equivalents = _private_hero_bindings(self.inventories)

    def stock(self, dataset, name):
        # Individual transformer fixtures share production's stock resolver;
        # production-path tests below additionally cover who supplies each map.
        return self.destinations[dataset].function(name, allow_expansion=True)

    def effective_native(self, dataset, name):
        for provider in reversed(for_dataset(self.native, dataset)):
            owned = provider.owner(key(name))
            if owned:
                if owned[1] is None:
                    raise ValueError(f"{provider.name}: selected native body unavailable: {name}")
                return owned[1]
        return self.stock(dataset, name)

    def authored_one(self, name):
        candidates = {_tokens(item.text): item for item in self.authored.get(name.casefold(), ())}
        if len(candidates) > 1:
            raise ValueError("fixture needs an explicit candidate for shared authored function: " + name)
        return next(iter(candidates.values()), None)

    def view(self, dataset, variant, render=False):
        stock = {name: self.stock(dataset, name) for name in self.stock_names}
        if any(item is None for item in stock.values()):
            raise ValueError("installed stock event source is incomplete")
        items = {}
        for name in self.stock_names | self.potion_names | self.callbacks:
            item = self.authored_one(name) or self.effective_native(dataset, name)
            if item:
                items[item.key] = item
        native_drop = self.effective_native(dataset, "dropgoldinradius")
        authored_drop = self.by_owner["alchemist"]["dropgoldinradius"]
        if variant == "native":
            items[key("dropgoldinradius")] = native_drop
        elif variant == "combined":
            ancestor = self.symbols.function_loader("dropgoldinradius")
            text = merge_function(ancestor.text, {
                "selected native distribution": native_drop.text,
                "Alchemist reagent prelude": authored_drop.text,
            })
            items[key("dropgoldinradius")] = replace(authored_drop, text=text, span=None)
        elif variant == "authored-stock-flags":
            # A legitimate alternate choice preserves the stock flag callers
            # while selecting the authored reagent/drop body.
            for name in ("explore_flag_poll", "attack_flag_poll", "attack_flag_death_callback"):
                items[key(name)] = stock[name]
        else:
            raise ValueError("unknown candidate view: " + variant)
        if render:
            items = {identity: rendered(item) for identity, item in items.items()}

        def loader(name):
            name = name.casefold()
            item = items.get(key(name)) or self.authored_one(name) or self.effective_native(dataset, name)
            return rendered(item) if render and item is not None else item

        stock_loader = lambda names: {key(name): self.stock(dataset, name) for name in names
                                      if self.stock(dataset, name) is not None}
        native_loader = lambda names: {key(name): self.effective_native(dataset, name) for name in names
                                       if self.effective_native(dataset, name) is not None}
        return SemanticMergeResult(tuple(items.values()), ()), stock, loader, stock_loader, native_loader

    def early_input(self, initial, dataset, variant, render=False):
        """Materialize competing candidates without resolving a whole profile."""
        names = {"purchase_bazaar", "control_monster", "controlled_monster_death", "leader_dead",
                 "reset_tasks", "unit_call_deathscript", "spell_extra_value"}
        names.update(item.normalized_name for item in self.hero_templates.values())
        names.update(self.private_trees)
        for evidence in self.early_evidence:
            names.update(symbol.casefold() for symbol in (
                evidence.callback_symbol, evidence.resume_callback_symbol,
                evidence.consider_callback_symbol, evidence.reset_callback_symbol,
                evidence.death_callback_symbol,
            ) if symbol)
        items = {i.key: i for i in initial.items}
        for name in names:
            native = self.effective_native(dataset, name)
            # The two source-choice views exercise every shared-tree/death
            # candidate separately. Multi-author spell scoring has its own
            # independent candidate matrix below, so use the native candidate.
            authored = None if name == "spell_extra_value" else self.authored_one(name)
            item = ((native or authored) if variant == "native" else (authored or native))
            if item is None:
                raise ValueError("earlier feature source is missing: " + name)
            items[item.key] = rendered(item) if render else item
        return SemanticMergeResult(tuple(items.values()), ())

    def purchase(self, initial, dataset):
        symbols = [e.callback_symbol for e in self.early_evidence if e.lifecycle == "bazaar"]
        reserved = {name for provider in self.native for kind, name in provider.compiled_keys
                    if kind is DefinitionKind.FUNCTION}
        return add_purchase_bazaar_tail_callbacks(initial, symbols,
            stock_purchase_bazaar=self.stock(dataset, "purchase_bazaar"),
            reserved_function_names=reserved)

    def movement(self, initial, dataset):
        hooks = [(e.callback_symbol, e.movement_rate_modifier_per_tier, e.marker_effectors)
                 for e in self.early_evidence if e.lifecycle == "controlled_follower_speed_sync"]
        return add_controlled_follower_movement_adjustments(initial, hooks,
            stock_control_monster=self.stock(dataset, "control_monster"),
            stock_controlled_monster_death=self.stock(dataset, "controlled_monster_death"),
            stock_leader_dead=self.stock(dataset, "leader_dead"))

    def hero_quests(self, initial, dataset):
        hooks = [(e.hero_scripts, e.resume_callback_symbol, e.consider_callback_symbol,
                  e.reset_callback_symbol, e.death_callback_symbol)
                 for e in self.early_evidence if e.lifecycle == "hero_quest"]
        trees = {script: self.stock(dataset, item.normalized_name)
                 for script, item in self.hero_templates.items()}
        return add_hero_quest_lifecycle_callbacks(initial, hooks,
            stock_hero_trees=trees, private_hero_trees=self.private_trees,
            stock_reset_tasks=self.stock(dataset, "reset_tasks"),
            stock_unit_death=self.stock(dataset, "unit_call_deathscript"))

    def policies_then_events(self, dataset, variant, render=False, subscribers=None, *, earlier=False):
        initial, stock, loader, stock_loader, native_loader = self.view(dataset, variant, render)
        result = initial
        if earlier:
            result = self.early_input(result, dataset, variant, render)
            result = self.purchase(result, dataset)
            result = self.movement(result, dataset)
            result = self.hero_quests(result, dataset)
            result = add_spell_evaluation_equivalents(result, self.equivalents,
                self.symbols.function_loader("spell_extra_value"))
        result, evidence = potion_service(result, self.potions, stock_loader, stock,
                                          native_loader=native_loader)
        aliases = {action.effect.casefold(): POTIONS[action.potion][1].casefold()
                   for action in self.potions.actions
                   if action.effect.casefold() != POTIONS[action.potion][1].casefold() + "_effect"}
        result = add_gameplay_event_observers(
            result, self.subscribers if subscribers is None else subscribers,
            evidence, potion_aliases=aliases, source_loader=loader,
        )
        return result, initial

    def research(self, result, dataset):
        bindings = []
        for inventory in self.inventories:
            for feature in inventory.selected.package.definition.runtime_features:
                if isinstance(feature, KingdomResearch):
                    parents = [r.to_element() for r in self.records.values()
                               if r.to_element().get("Name") == feature.parent_building + "1"]
                    if len(parents) != 1:
                        raise ValueError("research fixture needs one parent Description")
                    bindings.append((registration(inventory.selected.package.mod_id, feature,
                                                  parents[0].get("ID")[:3]), feature.parent_building))
        awards = {name: self.effective_native(dataset, name) for name in ("give_gold", "give_exp")}
        return research_service(result, bindings, awards)


class SelectedFeatureBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [str(path) for _, path in PACKAGES if not path.is_dir()]
        missing.extend(str(WORKSHOP / directory / manifest) for directory, manifest, _, _ in NATIVE
                       if not (WORKSHOP / directory / manifest).is_file())
        games = [game for game in (STEAM, GOG) if (game / "SDK/OriginalQuests").is_dir()]
        if missing or not games:
            raise unittest.SkipTest("selected-source installations unavailable: " + ", ".join(missing or [str(STEAM)]))
        cls.fixtures = tuple(SelectedSourceFixture(game) for game in games)

    def test_installed_declarations_cover_all_selected_families_and_private_actions(self):
        for fixture in self.fixtures:
            with self.subTest(game=str(fixture.game)):
                self.assertEqual(set(fixture.subscribers), set(EVENT_SIGNATURES))
                self.assertEqual({p.hero_title for p in fixture.potions.policies},
                                 {"Troubadour", "Spellsinger", "Blade_Dancer", "Alchemist", "Phantom"})
                private = {a.effect.casefold() for a in fixture.potions.actions
                           if a.name.casefold().startswith("alchemist_")}
                self.assertEqual(private, {"alchemist_" + name + "_effect" for name in (
                    "strength_potion", "shapeshift_potion", "fire_balm", "regeneration_elixer")})
                self.assertTrue(all("3793509198" in fixture.authored_one(name).source_name for name in private))

    def test_every_independent_event_has_a_diagnostic_row_for_each_candidate_view(self):
        failures = []
        for fixture in self.fixtures:
            for dataset in ("majesty", "majestyexpansion"):
                for variant in ("native", "combined", "authored-stock-flags"):
                    for render in (False, True):
                        for event, subscribers in fixture.subscribers.items():
                            label = f"{fixture.game.name}/{dataset}/{variant}/{'rendered' if render else 'raw'}/{event}"
                            try:
                                fixture.policies_then_events(dataset, variant, render, {event: subscribers})
                            except Exception as exc:
                                failures.append(label + ": " + str(exc))
        if failures:
            self.fail("generated boundary matrix:\n" + "\n".join(failures))

    def test_earlier_purchase_movement_and_hero_stages_have_independent_candidate_rows(self):
        failures = []
        for fixture in self.fixtures:
            hooks = {e.lifecycle: e for e in fixture.early_evidence}
            self.assertTrue({"bazaar", "controlled_follower_speed_sync", "hero_quest"} <= hooks.keys())
            hero = hooks["hero_quest"]
            callbacks = {"$" + symbol.casefold() for symbol in (
                hero.resume_callback_symbol, hero.consider_callback_symbol,
                hero.reset_callback_symbol, hero.death_callback_symbol,
            )}
            movement = hooks["controlled_follower_speed_sync"]
            markers = {'"' + marker + '"' for marker in movement.marker_effectors}

            def strip_hero(nodes):
                kept = []
                for node in nodes:
                    if callbacks.intersection(node.head):
                        if node.kind == "if":
                            kept.extend(strip_hero(node.body))
                    else:
                        kept.append(replace(node, body=strip_hero(node.body),
                                            otherwise=strip_hero(node.otherwise)))
                return tuple(kept)

            def strip_movement(nodes):
                return tuple(replace(node, body=strip_movement(node.body),
                                     otherwise=strip_movement(node.otherwise))
                             for node in nodes
                             if not (node.kind == "if" and (
                                 "$" + movement.callback_symbol.casefold() in node.head
                                 or "$checkeffector" in node.head and markers.intersection(node.head))))

            for dataset in ("majesty", "majestyexpansion"):
                for variant in ("native", "authored-stock-flags"):
                    for render in (False, True):
                        source, _, _, _, _ = fixture.view(dataset, variant, render)
                        source = fixture.early_input(source, dataset, variant, render)
                        original = functions(source)
                        for stage, transform in (("purchase", fixture.purchase),
                                                 ("controlled-follower", fixture.movement),
                                                 ("hero-quest", fixture.hero_quests)):
                            label = f"{fixture.game.name}/{dataset}/{variant}/{render}/{stage}"
                            try:
                                result = functions(transform(source, dataset))
                                if stage == "purchase":
                                    copied = result["cam_purchase_bazaar_beforetail"].text
                                    name = re.match(r"\s*function\s+(\w+)", original["purchase_bazaar"].text, re.I)[1]
                                    restored = re.sub(r"\bCAM_Purchase_Bazaar_BeforeTail\b", name,
                                                      copied, count=1, flags=re.I)
                                    self.assertEqual(restored, original["purchase_bazaar"].text)
                                    public = _tokens(result["purchase_bazaar"].text)
                                    self.assertEqual(public.count("$" + hooks["bazaar"].callback_symbol.casefold()), 1)
                                    self.assertLess(public.index("$cam_purchase_bazaar_beforetail"),
                                                    public.index("$" + hooks["bazaar"].callback_symbol.casefold()))
                                elif stage == "controlled-follower":
                                    for name in ("control_monster", "controlled_monster_death", "leader_dead"):
                                        signature, locals_, body = _Parser(result[name].text).function()
                                        self.assertEqual((signature, locals_, strip_movement(body)),
                                                         _Parser(original[name].text).function())
                                else:
                                    names = {item.normalized_name for item in fixture.hero_templates.values()}
                                    names.update(fixture.private_trees)
                                    names.update(("reset_tasks", "unit_call_deathscript"))
                                    for name in names:
                                        signature, locals_, body = _Parser(result[name].text).function()
                                        self.assertEqual((signature, locals_, strip_hero(body)),
                                                         _Parser(original[name].text).function(), name)
                                        self.assertTrue(callbacks.intersection(_tokens(result[name].text)), name)
                            except Exception as exc:
                                failures.append(label + ": " + str(exc))
        if failures:
            self.fail("earlier generated feature matrix:\n" + "\n".join(failures))

    def test_potion_policy_preserves_all_actual_shopping_candidates_and_purchase_bodies(self):
        failures = []
        for fixture in self.fixtures:
            for dataset in ("majesty", "majestyexpansion"):
                native = fixture.effective_native(dataset, "bazaar_item_check")
                authored = fixture.authored_one("bazaar_item_check")
                ancestor = fixture.symbols.function_loader("bazaar_item_check")
                combined = replace(authored, text=merge_function(ancestor.text,
                    {"native shopping": _align_parameters(ancestor.text, native.text),
                     "private hero shopping": _align_parameters(ancestor.text, authored.text)}), span=None)
                for variant, candidate in (("native", native), ("authored", authored), ("combined", combined)):
                    for render in (False, True):
                        label = f"{fixture.game.name}/{dataset}/{variant}/{render}/potion-shopping"
                        try:
                            initial, stock, _, stock_loader, native_loader = fixture.view(dataset, "combined", render)
                            candidate = rendered(candidate) if render else candidate
                            original = {i.key: i for i in initial.items}
                            original[candidate.key] = candidate
                            prepared, _ = potion_service(SemanticMergeResult(tuple(original.values()), ()),
                                fixture.potions, stock_loader, stock, native_loader=native_loader)
                            actual = functions(prepared)
                            body = _Parser(actual["bazaar_item_check"].text).function()[2]
                            restored = []
                            for node in body:
                                if "$mm_bp_eligibility" not in node.head:
                                    restored.append(node)
                                elif node.body != parse_nodes("return False;"):
                                    restored.extend(node.body)
                            self.assertEqual(tuple(restored), _Parser(candidate.text).function()[2])
                            for name in ("alchemist_purchase_bazaar", "alchemist_purchase_nearby_bazaar"):
                                self.assertIn("$bazaar_item_check", _tokens(actual[name].text))
                                self.assertEqual(actual[name].text, original[key(name)].text)
                            names = {"purchase_bazaar_item_" + number.casefold() for number, _ in POTIONS.values()}
                            for name in names:
                                before = _Parser(original[key(name)].text).function()[2]
                                after = _Parser(actual[name].text).function()[2]
                                self.assertIn("$mm_bp_eligibility", after[0].head, name)
                                self.assertEqual(after[1:], before, name)
                        except Exception as exc:
                            failures.append(label + ": " + str(exc))
        if failures:
            self.fail("potion shopping matrix:\n" + "\n".join(failures))

    def test_earlier_stages_reject_changed_abi_decision_and_cleanup_boundaries(self):
        fixture = self.fixtures[0]
        dataset = "majestyexpansion"
        base, _, _, _, _ = fixture.view(dataset, "native")
        initial = fixture.early_input(base, dataset, "native")
        originals = functions(initial)
        cases = (
            ("purchase-bazaar", "purchase_bazaar", r"\bis\s+boolean\b", "is integer", fixture.purchase),
            ("hero-resume", "rogue_tree", r"\$Check_Nearby\b", "$Check_Nearby_Changed", fixture.hero_quests),
            ("hero-reset", "reset_tasks", r"\$StopMoving\s*\(\s*ThisAgent\s*\)\s*;", "", fixture.hero_quests),
            ("hero-death", "unit_call_deathscript", r"\$DeleteAllEffectors\s*\(\s*ThisAgent\s*\)\s*;", "", fixture.hero_quests),
            ("follower-ownership", "control_monster", r"\$setunitplayernumber\s*\(\s*target\s*,", "$setunitplayernumber(thisagent,", fixture.movement),
        )
        for label, name, pattern, replacement, transform in cases:
            original = originals[name]
            text, count = re.subn(pattern, lambda _: replacement, original.text, count=1, flags=re.I)
            self.assertEqual(count, 1, "fixture boundary no longer exists: " + label)
            for render in (False, True):
                changed = replace(original, text=text, span=None)
                if render:
                    changed = rendered(changed)
                result = SemanticMergeResult(tuple(changed if i.key == changed.key else i for i in initial.items), ())
                with self.subTest(label=label, render=render), self.assertRaises(ValueError):
                    transform(result, dataset)

    def test_potion_shopping_changed_stock_restriction_is_rejected_in_both_scopes(self):
        fixture = self.fixtures[0]
        for dataset in ("majesty", "majestyexpansion"):
            initial, stock, _, stock_loader, native_loader = fixture.view(dataset, "native")
            original = fixture.effective_native(dataset, "bazaar_item_check")
            restriction = parse_nodes('''
                if ((ThisAgent's "title" == "cultist") && (item == #Bazaar_Item_Six)) return False;
            ''')[0]
            from majesty_cam.gpl_function_merge import _SourceParser
            parser = _SourceParser(original.text)
            nodes = parser.function()[2]
            matches = [node for node in nodes if node == restriction]
            self.assertEqual(len(matches), 1, "native shopping lost its stock title restriction")
            start, end = parser.node_spans[id(matches[0])]
            replacement = re.sub(r"\breturn\s+false\b", "return True", original.text[start:end], flags=re.I)
            text = original.text[:start] + replacement + original.text[end:]
            for render in (False, True):
                changed = replace(original, text=text, span=None)
                if render:
                    changed = rendered(changed)
                result = SemanticMergeResult(tuple(changed if i.key == changed.key else i for i in initial.items), ())
                with self.subTest(dataset=dataset, render=render), self.assertRaisesRegex(ValueError, "boundary"):
                    potion_service(result, fixture.potions, stock_loader, stock, native_loader=native_loader)

    def test_combined_events_then_research_and_private_services_preserve_source_views(self):
        failures = []
        for fixture in self.fixtures:
            for dataset in ("majesty", "majestyexpansion"):
                for variant in ("native", "combined", "authored-stock-flags"):
                    outputs = []
                    for render in (False, True):
                        stage = "potion-policy and gameplay events"
                        label = f"{fixture.game.name}/{dataset}/{variant}/{'rendered' if render else 'raw'}"
                        try:
                            result, initial = fixture.policies_then_events(dataset, variant, render, earlier=True)
                            original = functions(initial)
                            observed = functions(result)
                            self.assertEqual(observed["dropgoldinradius"].text, original["dropgoldinradius"].text)
                            routed = [item for name, item in observed.items() if name.startswith("mm_eg_")]
                            self.assertTrue(routed, "reward delivery must use the selected distribution call graph")
                            if variant != "native":
                                self.assertTrue(any("$alchemist_award_monster_part" in _tokens(item.text)
                                                    for item in routed), "routed payout dropped the reagent prelude")
                            if variant != "authored-stock-flags":
                                self.assertTrue(any(
                                    _tokens("$MM_Event_RewardPaid(MM_SourceContext, guy, goldper);")
                                    == node.head
                                    for item in routed for node in walk(_Parser(item.text).function()[2])),
                                    "nested native payout lost the original flag or actual recipient/amount")
                            # The extra MK guard XP award is a separate branch:
                            # only the stock combat-success award becomes observed.
                            if dataset == "majestyexpansion":
                                self.assertIn("MK_Veteran_Guards.gpl", original["attack_end"].source_name)
                                self.assertEqual(_tokens(observed["attack_end"].text).count("$mm_event_combatxp"), 1)
                                self.assertEqual(_tokens(original["attack_end"].text).count("$give_exp") - 1,
                                                 _tokens(observed["attack_end"].text).count("$give_exp"))
                            stage = "activity service"
                            result = add_activity_service(result, fixture.shared)
                            stage = "kingdom research"
                            result = fixture.research(result, dataset)
                            stage = "action bridges"
                            result = add_bridges(result, fixture.inventories)
                            stage = "toggle state"
                            result = add_state_functions(result, toggles(fixture.inventories))
                            stage = "typed dispatch"
                            result = SemanticMergeResult((*result.items, *_typed_provider_dispatches(fixture.inventories)), ())
                            for name in ("mm_kr_gold", "mm_kr_xp", "mm_ad_start", "mm_event_rewardpaid"):
                                self.assertIn(name, functions(result))
                            outputs.append(instructions(result))
                        except Exception as exc:
                            failures.append(label + "/" + stage + ": " + str(exc))
                    if len(outputs) == 2:
                        self.assertEqual(outputs[0], outputs[1], label + ": source rendering changed the generated instructions")
        if failures:
            self.fail("dependent feature matrix:\n" + "\n".join(failures))

    def test_rendered_combined_earlier_stages_compile_with_each_installed_sdk(self):
        compilers = [(fixture, fixture.game / "SDK/Gplbcc.exe") for fixture in self.fixtures
                     if (fixture.game / "SDK/Gplbcc.exe").is_file()]
        if not compilers:
            self.skipTest("installed stock SDK compiler unavailable")
        # Compiler acceptance catches tokenization defects invisible when both
        # sides of an AST comparison share the same lexer (notably ++ and --).
        # These are disposable language fixtures, never a Manager output.
        with TemporaryDirectory(prefix="selected-feature-source-") as temporary:
            for index, (fixture, compiler) in enumerate(compilers):
                for dataset in ("majesty", "majestyexpansion"):
                    with self.subTest(compiler=str(compiler), dataset=dataset):
                        result, _ = fixture.policies_then_events(dataset, "combined", True, earlier=True)
                        compile_gpl(result.emit_project_source_set(), compiler,
                                    Path(temporary) / f"{index}-{dataset}")

    def test_installed_sources_use_production_inventory_review_and_feature_wiring(self):
        # Do not reconstruct the winning function map or feature reference map.
        # Read actual inventories, use the production review/resume path, and
        # inspect the real inputs at the observer boundary without replacing it.
        for fixture in self.fixtures:
            inventories = tuple(production.inventory_package(production.SelectedMod(
                inventory.selected.alias, inventory.selected.package))
                for inventory in fixture.inventories)
            authored = [i.selected.package.mod_id.strip("{}").casefold() for i in inventories]
            native = [i.package.mod_id.strip("{}").casefold() for i in fixture.native]
            for preference in ("authored-first", "native-first", "without-standard"):
                standard = () if preference == "without-standard" else fixture.native
                priority = list(dict.fromkeys(native + authored if preference == "native-first"
                                             else authored + native))
                observed, reviews, prepared = [], [], []
                real_merge = production.merge_gpl_resources

                def choose(conflicts):
                    reviews.extend(conflicts)
                    return {pair.identity: min((pair.left.owner, pair.right.owner), key=priority.index)
                            for pair in group_conflicts(conflicts)}

                def observe(result, subscribers, stock, **kwargs):
                    output = add_gameplay_event_observers(result, subscribers, stock, **kwargs)
                    observed.append((result, output, subscribers, stock))
                    return output

                def construct(*args, **kwargs):
                    prepared.append(kwargs)
                    return real_merge(*args, **kwargs)

                with self.subTest(game=str(fixture.game), preference=preference):
                    with patch("majesty_cam.compose.add_gameplay_event_observers", side_effect=observe), \
                            patch("majesty_cam.compose.merge_gpl_resources", side_effect=construct):
                        bundle = production.prepare_gpl_bundle(fixture.game, inventories,
                            standard_script_inputs=standard, script_conflict_resolver=choose)
                    self.assertEqual(len(observed), 2, "both destinations must reach generated features")
                    self.assertEqual({c.dataset for c in reviews}, {"majesty", "majestyexpansion"})
                    self.assertEqual([p["script_dataset"] for p in prepared], ["majesty", "majestyexpansion"])
                    for inputs in prepared:
                        dataset = inputs["script_dataset"]
                        references = [inputs[name] for name in (
                            "stock_control_monster", "stock_controlled_monster_death", "stock_leader_dead",
                            "stock_reset_tasks", "stock_unit_death", "stock_spell_evaluation")]
                        references.extend(inputs["stock_hero_trees"].values())
                        references.extend(inputs["stock_gameplay_event_items"].values())
                        references.append(inputs["stock_purchase_bazaar_source"].require(
                            DefinitionKind.FUNCTION, "purchase_bazaar"))
                        for reference in references:
                            # Assert against the captured SDK's raw per-dataset
                            # loader, independently of DestinationSources itself.
                            name = reference.normalized_name
                            loader = (fixture.symbols.base_function_loader
                                      if dataset == "majesty" and name in fixture.symbols.base_functions
                                      else fixture.symbols.function_loader)
                            expected = loader(name)
                            self.assertEqual(reference.source_name, expected.source_name, (dataset, name))
                            self.assertEqual(_tokens(reference.text), _tokens(expected.text), (dataset, name))
                    for dataset, (before, after, subscribers, references) in zip(
                            ("majesty", "majestyexpansion"), observed):
                        original, generated = functions(before), functions(after)
                        expected = fixture.stock(dataset, "caravan_go_trade")
                        self.assertEqual(references["caravan_go_trade"].source_name, expected.source_name,
                                         "production must select the destination's lifecycle evidence")
                        self.assertEqual(without_observers(generated["caravan_go_trade"].text,
                            subscribers["caravan-delivered"]),
                            _tokens(original.get("caravan_go_trade", references["caravan_go_trade"]).text))
                        for name, wrapper in (("attack_end", "MM_Event_CombatXP"),
                                              ("travel_to_exp", "MM_Event_ExploreXP")):
                            restored, count = re.subn(r"\$" + wrapper + r"\b", "$give_exp",
                                                      generated[name].text, flags=re.I)
                            self.assertEqual(count, 1, name)
                            self.assertEqual(_tokens(restored), _tokens(original.get(name, references[name]).text), name)
                        self.assertEqual(_tokens(generated["dropgoldinradius"].text),
                                         _tokens(original["dropgoldinradius"].text))
                        self.assertIn("$alchemist_award_monster_part",
                                      _tokens(original["dropgoldinradius"].text))
                        if dataset == "majestyexpansion" and standard:
                            self.assertIn("MK_Veteran_Guards.gpl", original["attack_end"].source_name)
                        final = bundle_functions(bundle, dataset)
                        self.assertEqual(_tokens(final["caravan_go_trade"].text),
                                         _tokens(generated["caravan_go_trade"].text))
                    compiler = fixture.game / "SDK/Gplbcc.exe"
                    # Compile the production combined view once per SDK;
                    # alternate preferences still exercise every source stage.
                    if compiler.is_file() and preference == "authored-first":
                        with TemporaryDirectory(prefix="selected-production-source-") as temporary:
                            for scope, output in bundle.outputs:
                                if output.source_set.files:
                                    compile_gpl(output.source_set, compiler, Path(temporary) / scope)

    def test_downstream_services_are_audited_even_if_an_event_stage_is_blocked(self):
        failures = []
        for fixture in self.fixtures:
            _, equivalents = _private_hero_bindings(fixture.inventories)
            for dataset in ("majesty", "majestyexpansion"):
                candidates = (*fixture.authored.get("spell_extra_value", ()),
                              fixture.effective_native(dataset, "spell_extra_value"))
                for render in (False, True):
                    initial, _, _, _, _ = fixture.view(dataset, "combined", render)
                    for label, transform in (
                        ("kingdom-research", lambda: fixture.research(initial, dataset)),
                        ("activity", lambda: add_activity_service(initial, fixture.shared)),
                        ("action-bridges", lambda: add_bridges(initial, fixture.inventories)),
                        ("toggle-state", lambda: add_state_functions(initial, toggles(fixture.inventories))),
                        ("typed-dispatch", lambda: _typed_provider_dispatches(fixture.inventories)),
                    ):
                        try:
                            transform()
                        except Exception as exc:
                            failures.append(f"{fixture.game.name}/{dataset}/{render}/{label}: {exc}")
                    for candidate in candidates:
                        item = rendered(candidate) if render else candidate
                        try:
                            add_spell_evaluation_equivalents(SemanticMergeResult((item,), ()), equivalents,
                                fixture.symbols.function_loader("spell_extra_value"))
                        except Exception as exc:
                            failures.append(f"{fixture.game.name}/{dataset}/{render}/spell-equivalent/{candidate.source_name}: {exc}")
        if failures:
            self.fail("independent downstream matrix:\n" + "\n".join(failures))

    def test_changed_combat_recipient_and_flag_payout_arguments_remain_blocked(self):
        fixture = self.fixtures[0]
        for dataset in ("majesty", "majestyexpansion"):
            initial, stock, loader, _, _ = fixture.view(dataset, "combined")
            for event, name, pattern, replacement in (
                ("combat-experience-awarded", "attack_end", r"\$give_exp\s*\(\s*thisagent\s*,\s*exp_given\s*/\s*new_exp_div", "$give_exp(target, exp_given / new_exp_div"),
                ("reward-flag-paid", "attack_flag_poll", r"\$getattribute\s*\(\s*thisagent\s*,\s*#ATTRIB_RewardCost\s*\)", "$GetAttribute(thisagent, #ATTRIB_Gold)"),
            ):
                original = functions(initial)[name]
                text, count = re.subn(pattern, lambda _: replacement, original.text, count=1, flags=re.I)
                self.assertEqual(count, 1, "fixture no longer contains the boundary to corrupt: " + name)
                for render in (False, True):
                    changed = replace(original, text=text, span=None)
                    if render:
                        changed = rendered(changed)
                    result = SemanticMergeResult(tuple(changed if i.key == changed.key else i for i in initial.items), ())
                    with self.subTest(dataset=dataset, event=event, render=render), self.assertRaises(ValueError):
                        add_gameplay_event_observers(result, {event: fixture.subscribers[event]}, stock, source_loader=loader)

    def test_private_potion_wrong_item_and_missing_forget_are_not_valid_consumption(self):
        fixture = self.fixtures[0]
        initial, stock, loader, stock_loader, native_loader = fixture.view("majesty", "combined")
        prepared, evidence = potion_service(initial, fixture.potions, stock_loader, stock,
                                            native_loader=native_loader)
        name = "alchemist_strength_potion_effect"
        original = functions(prepared)[name]
        changes = (
            (r"\$DeleteInventoryItem\s*\(\s*#Bazaar_Item_Three", "$DeleteInventoryItem(#Bazaar_Item_Two"),
            (r'\$ForgetSpell\s*\(\s*ThisAgent\s*,\s*"[^"]+"\s*\)\s*;', ""),
        )
        aliases = {a.effect.casefold(): POTIONS[a.potion][1].casefold() for a in fixture.potions.actions
                   if a.effect.casefold() != POTIONS[a.potion][1].casefold() + "_effect"}
        for pattern, replacement in changes:
            text, count = re.subn(pattern, lambda _: replacement, original.text, count=1, flags=re.I)
            self.assertEqual(count, 1, "private potion fixture changed its consumption boundary")
            for render in (False, True):
                changed = replace(original, text=text, span=None)
                if render:
                    changed = rendered(changed)
                result = SemanticMergeResult(tuple(changed if i.key == changed.key else i for i in prepared.items), ())
                with self.subTest(pattern=pattern, render=render), self.assertRaises(ValueError):
                    add_gameplay_event_observers(result, {"potion-consumed": fixture.subscribers["potion-consumed"]},
                        evidence, potion_aliases=aliases, source_loader=loader)


class InstalledProductionDestinationTests(unittest.TestCase):
    """Production reference construction, independent of Workshop availability."""

    @classmethod
    def setUpClass(cls):
        cls.games = tuple(game for game in (STEAM, GOG) if (game / "SDK/OriginalQuests").is_dir())
        if not cls.games:
            raise unittest.SkipTest("stock SDK source installation unavailable")

    def caravan_inventory(self, source=None):
        feature = StockGameplayEventObserver("caravan", "caravan-delivered", "Fixture_CaravanDelivered")
        package = SimpleNamespace(mod_id="00000000-0000-0000-0000-000000000021", display_name="Caravan fixture",
                                  definition=SimpleNamespace(runtime_features=(feature,)))
        callback = parse_gpl("function Fixture_CaravanDelivered(agent Caravan, agent Target, integer Amount)\n"
                             "declare\nbegin\nend\n", "<caravan observer fixture>")
        sources = (callback,) if source is None else (callback, parse_gpl(source.text, source.source_name))
        return production.PackageInventory(production.SelectedMod("caravan-fixture", package),
                                            (), (), (), (), semantic_sources=sources)

    def assert_caravan_preserved(self, item, original):
        self.assertEqual(without_observers(item.text, ("Fixture_CaravanDelivered",)), _tokens(original.text))

    def test_untouched_stock_caravan_uses_actual_production_reference_selection(self):
        for game in self.games:
            symbols = load_dataset_symbols(game)
            for dataset, loader in (("majesty", symbols.base_function_loader),
                                    ("majestyexpansion", symbols.function_loader)):
                original = loader("caravan_go_trade")
                for render in (False, True):
                    source = rendered(original) if render else original
                    with self.subTest(game=str(game), dataset=dataset, rendered=render):
                        result = production.prepare_final_gpl_resources(game, (self.caravan_inventory(source),),
                            script_dataset=dataset, dataset_symbols=symbols)
                        self.assert_caravan_preserved(source_functions(result)["caravan_go_trade"], source)

    def test_no_standard_bundle_preserves_each_destination_generated_stock_body(self):
        for game in self.games:
            symbols = load_dataset_symbols(game)
            with self.subTest(game=str(game)):
                bundle = production.prepare_gpl_bundle(game, (self.caravan_inventory(),))
                self.assertEqual({scope for scope, _ in bundle.patches}, {"Majesty", "MajestyExpansion"})
                for dataset, loader in (("majesty", symbols.base_function_loader),
                                        ("majestyexpansion", symbols.function_loader)):
                    original = loader("caravan_go_trade")
                    self.assert_caravan_preserved(bundle_functions(bundle, dataset)["caravan_go_trade"], original)
                compiler = game / "SDK/Gplbcc.exe"
                if compiler.is_file():
                    with TemporaryDirectory(prefix="caravan-destination-source-") as temporary:
                        for scope, output in bundle.outputs:
                            if output.source_set.files:
                                compile_gpl(output.source_set, compiler, Path(temporary) / scope)

    def test_production_early_evidence_uses_each_destination_stock_source(self):
        for game in self.games:
            symbols = load_dataset_symbols(game)
            for dataset, loader in (("majesty", symbols.base_function_loader),
                                    ("majestyexpansion", symbols.function_loader)):
                with self.subTest(game=str(game), dataset=dataset):
                    production.validate_gpl_feature_evidence(
                        (self.caravan_inventory(loader("caravan_go_trade")),), game_path=game,
                        script_dataset=dataset, dataset_symbols=symbols)

    def test_default_early_evidence_checks_both_destinations_without_reference_overrides(self):
        for game in self.games:
            references = []

            def observe(result, subscribers, stock, **kwargs):
                references.append(stock["caravan_go_trade"])
                return add_gameplay_event_observers(result, subscribers, stock, **kwargs)

            with self.subTest(game=str(game)):
                with patch("majesty_cam.compose.add_gameplay_event_observers", side_effect=observe):
                    production.validate_gpl_feature_evidence((self.caravan_inventory(),), game_path=game)
                symbols = load_dataset_symbols(game)
                expected = [symbols.base_function_loader("caravan_go_trade"),
                            symbols.function_loader("caravan_go_trade")]
                self.assertEqual([(r.source_name, _tokens(r.text)) for r in references],
                                 [(r.source_name, _tokens(r.text)) for r in expected])

    def test_production_caravan_missing_or_ambiguous_insertion_is_rejected(self):
        for game in self.games:
            symbols = load_dataset_symbols(game)
            for dataset, loader in (("majesty", symbols.base_function_loader),
                                    ("majestyexpansion", symbols.function_loader)):
                original = loader("caravan_go_trade")
                for label, replacement in (("missing", ""), ("ambiguous", r"\g<0>\n\g<0>")):
                    text, count = re.subn(r"\$henchman_dead\s*\(\s*thisagent\s*,\s*thisagent\s*\)\s*;",
                                          replacement, original.text, flags=re.I)
                    self.assertEqual(count, 1, "installed Caravan cleanup anchor changed")
                    for render in (False, True):
                        source = replace(original, text=text, span=None)
                        if render:
                            source = rendered(source)
                        with self.subTest(game=str(game), dataset=dataset, case=label, rendered=render), \
                                self.assertRaisesRegex((ValueError, production.ComposeError),
                                                       "[Cc]aravan|henchman_dead"):
                            production.prepare_final_gpl_resources(game, (self.caravan_inventory(source),),
                                script_dataset=dataset, dataset_symbols=symbols)


if __name__ == "__main__":
    unittest.main()
