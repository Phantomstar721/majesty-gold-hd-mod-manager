from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.runtime_features import (
    EnchantmentRowFeature,
    NameGeneratorFeature,
    RuntimeFeatureRegistry,
    decode_runtime_feature_registry,
    derive_feature_runtime_capabilities,
    encode_runtime_feature_registry,
    normalize_runtime_features,
    write_runtime_feature_registry,
)
from majesty_cam.gpl_features import StockHeroQuestLifecycle
from majesty_cam.cam import CamEntry, pad_name
from majesty_cam.compose import (
    CamResource,
    ComposeError,
    PackageInventory,
    SelectedMod,
    resolve_runtime_feature_registry,
)


class RuntimeFeatureRegistryTests(unittest.TestCase):
    def test_hero_quest_lifecycle_never_enters_overlay_registry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            description = root / "description.xml"
            description.write_text("<Majesty/>", encoding="utf-8")
            lifecycle = StockHeroQuestLifecycle(
                feature_key="quests",
                hero_scripts=("mx_ranger",),
                decision_callback_symbol="Quest_Decide",
                reset_callback_symbol="Quest_Reset",
                death_callback_symbol="Quest_Death",
            )
            inventory = _feature_inventory(
                "quest-owner", root, description, (lifecycle,)
            )

            self.assertEqual(
                resolve_runtime_feature_registry((inventory,)),
                RuntimeFeatureRegistry(),
            )

    def test_round_trip_is_deterministic_and_cp1252_exact(self):
        features = (
            EnchantmentRowFeature("ZZ99", "Crème brûlée"),
            NameGeneratorFeature("NM19", ("HN73", "HN74", "HN75", "HN76")),
            EnchantmentRowFeature("AA01", "First row"),
            NameGeneratorFeature("NM18", ("HN69", "HN70", "HN71", "HN72")),
        )
        forward = encode_runtime_feature_registry(features)
        reverse = encode_runtime_feature_registry(tuple(reversed(features)))
        self.assertEqual(forward, reverse)
        self.assertEqual(
            decode_runtime_feature_registry(forward),
            RuntimeFeatureRegistry(
                (
                    NameGeneratorFeature(
                        "NM18", ("HN69", "HN70", "HN71", "HN72")
                    ),
                    NameGeneratorFeature(
                        "NM19", ("HN73", "HN74", "HN75", "HN76")
                    ),
                ),
                (
                    EnchantmentRowFeature("AA01", "First row"),
                    EnchantmentRowFeature("ZZ99", "Crème brûlée"),
                ),
            ),
        )

    def test_legacy_v2_capabilities_translate_byte_for_byte(self):
        legacy = (
            "phantom.nm19-name-generator",
            "alchemist.ap78-private-oil-rows",
            "alchemist.nm18-name-generator",
        )
        explicit = (
            NameGeneratorFeature("NM18", ("HN69", "HN70", "HN71", "HN72")),
            NameGeneratorFeature("NM19", ("HN73", "HN74", "HN75", "HN76")),
            EnchantmentRowFeature(
                "ALo1", "Paralytic Oil - brief stun on weapon hit"
            ),
            EnchantmentRowFeature(
                "ALo2", "Transmutation Oil - +5 gold on weapon hit"
            ),
            EnchantmentRowFeature(
                "ALo3", "Poisoned Weapon - poison on weapon hit"
            ),
        )
        self.assertEqual(
            encode_runtime_feature_registry((), legacy_capabilities=legacy),
            encode_runtime_feature_registry(explicit),
        )
        registry = normalize_runtime_features((), legacy_capabilities=legacy)
        self.assertEqual(
            derive_feature_runtime_capabilities(legacy, registry),
            (
                "stock.ap78-enchantment-row.v1",
                "stock.name-generator.v1",
            ),
        )

    def test_legacy_alias_requires_its_exact_record_even_with_generic_data(self):
        registry = normalize_runtime_features(
            (
                NameGeneratorFeature(
                    "NM20", ("HN81", "HN82", "HN83", "HN84")
                ),
            )
        )
        with self.assertRaisesRegex(ValueError, "exact translated MMFR"):
            derive_feature_runtime_capabilities(
                ("phantom.nm19-name-generator",), registry
            )

    def test_generic_hook_names_are_derived_only_from_typed_records(self):
        generic_names = "stock.name-generator.v1"
        generic_rows = "stock.ap78-enchantment-row.v1"
        self.assertEqual(
            derive_feature_runtime_capabilities(
                (generic_names, generic_rows), RuntimeFeatureRegistry()
            ),
            (),
        )
        registry = normalize_runtime_features(
            (
                NameGeneratorFeature(
                    "NM20", ("HN81", "HN82", "HN83", "HN84")
                ),
                EnchantmentRowFeature("EF01", "A row"),
            )
        )
        self.assertEqual(
            derive_feature_runtime_capabilities((), registry),
            (generic_rows, generic_names),
        )

    def test_conflicting_duplicate_owners_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "conflicting name-generator"):
            normalize_runtime_features(
                (
                    NameGeneratorFeature(
                        "NM20", ("HN81", "HN82", "HN83", "HN84")
                    ),
                    NameGeneratorFeature(
                        "NM20", ("HN85", "HN86", "HN87", "HN88")
                    ),
                )
            )
        with self.assertRaisesRegex(ValueError, "conflicting enchantment-row"):
            normalize_runtime_features(
                (
                    EnchantmentRowFeature("EF01", "One"),
                    EnchantmentRowFeature("EF01", "Two"),
                )
            )

    def test_invalid_fourcc_text_and_count_are_rejected(self):
        invalid_names = (
            NameGeneratorFeature("AB01", ("HN81", "HN82", "HN83", "HN84")),
            NameGeneratorFeature("NM1", ("HN81", "HN82", "HN83", "HN84")),
            NameGeneratorFeature("NM17", ("HN81", "HN82", "HN83", "HN84")),
            NameGeneratorFeature("NM20", ("XX01", "HN82", "HN83", "HN84")),
            NameGeneratorFeature("NM20", ("HN81", "HN82", "HN81", "HN84")),
            NameGeneratorFeature("NM20", ("HN01", "HN82", "HN83", "HN84")),
        )
        for feature in invalid_names:
            with self.subTest(feature=feature):
                with self.assertRaises(ValueError):
                    encode_runtime_feature_registry((feature,))
        invalid_rows = (
            EnchantmentRowFeature("ABC", "text"),
            EnchantmentRowFeature("AB\x00D", "text"),
            EnchantmentRowFeature("ABCD", ""),
            EnchantmentRowFeature("ABCD", "nul\x00text"),
            EnchantmentRowFeature("ABCD", "snowman \u2603"),
            EnchantmentRowFeature("ABCD", "x" * 513),
        )
        for feature in invalid_rows:
            with self.subTest(feature=feature):
                with self.assertRaises(ValueError):
                    encode_runtime_feature_registry((feature,))

    def test_complete_stock_hn_range_is_reserved_but_legacy_range_remains_valid(self):
        for index in range(1, 69):
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, "stock Majesty HN01-HN68"):
                    normalize_runtime_features(
                        (
                            NameGeneratorFeature(
                                "NM42",
                                (
                                    f"HN{index:02d}",
                                    "HN81",
                                    "HN82",
                                    "HN83",
                                ),
                            ),
                        )
                    )
        self.assertEqual(
            normalize_runtime_features(
                (
                    NameGeneratorFeature(
                        "NM18", ("HN69", "HN70", "HN71", "HN72")
                    ),
                )
            ).name_generators[0].generator_id,
            "NM18",
        )

    def test_decoder_rejects_every_truncation_and_trailing_data(self):
        payload = encode_runtime_feature_registry(
            (
                NameGeneratorFeature(
                    "NM20", ("HN81", "HN82", "HN83", "HN84")
                ),
                EnchantmentRowFeature("EF01", "A row"),
            )
        )
        for size in range(len(payload)):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    decode_runtime_feature_registry(payload[:size])
        with self.assertRaisesRegex(ValueError, "trailing"):
            decode_runtime_feature_registry(payload + b"x")
        with self.assertRaisesRegex(ValueError, "exceeds"):
            decode_runtime_feature_registry(b"x" * (1024 * 1024 + 1))

    def test_decoder_rejects_header_bounds_and_noncanonical_records(self):
        with self.assertRaisesRegex(ValueError, "magic"):
            decode_runtime_feature_registry(struct.pack("<4sIII", b"NOPE", 1, 0, 0))
        with self.assertRaisesRegex(ValueError, "version"):
            decode_runtime_feature_registry(struct.pack("<4sIII", b"MMFR", 2, 0, 0))
        with self.assertRaisesRegex(ValueError, "name generators"):
            decode_runtime_feature_registry(struct.pack("<4sIII", b"MMFR", 1, 257, 0))
        with self.assertRaisesRegex(ValueError, "enchantment rows"):
            decode_runtime_feature_registry(struct.pack("<4sIII", b"MMFR", 1, 0, 1025))

        stock_generator = struct.pack(
            "<4sIIIIIIII",
            b"MMFR",
            1,
            1,
            0,
            *(int.from_bytes(value.encode("ascii"), "little") for value in (
                "NM17", "HN81", "HN82", "HN83", "HN84"
            )),
        )
        with self.assertRaisesRegex(ValueError, "collides with stock"):
            decode_runtime_feature_registry(stock_generator)

        invalid_cp1252 = (
            struct.pack("<4sIII", b"MMFR", 1, 0, 1)
            + struct.pack("<II", int.from_bytes(b"EF01", "little"), 1)
            + b"\x81"
        )
        with self.assertRaisesRegex(ValueError, "Windows-1252"):
            decode_runtime_feature_registry(invalid_cp1252)

    def test_decoder_rejects_duplicates_and_noncanonical_order(self):
        header = struct.pack("<4sIII", b"MMFR", 1, 2, 0)
        record = struct.pack(
            "<IIIII",
            *(
                int.from_bytes(value.encode("ascii"), "little")
                for value in ("NM20", "HN81", "HN82", "HN83", "HN84")
            ),
        )
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            decode_runtime_feature_registry(header + record + record)

        duplicate_parts = struct.pack(
            "<4sIIIIIIII",
            b"MMFR",
            1,
            1,
            0,
            *(int.from_bytes(value.encode("ascii"), "little") for value in (
                "NM20", "HN81", "HN82", "HN81", "HN84"
            )),
        )
        with self.assertRaisesRegex(ValueError, "distinct"):
            decode_runtime_feature_registry(duplicate_parts)

        row_header = struct.pack("<4sIII", b"MMFR", 1, 0, 2)
        high = int.from_bytes(b"ZZ99", "little")
        low = int.from_bytes(b"AA01", "little")
        noncanonical = (
            row_header
            + struct.pack("<II", high, 1)
            + b"a"
            + struct.pack("<II", low, 1)
            + b"b"
        )
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            decode_runtime_feature_registry(noncanonical)

    def test_empty_registry_and_atomic_writer(self):
        payload = encode_runtime_feature_registry(())
        self.assertEqual(
            decode_runtime_feature_registry(payload), RuntimeFeatureRegistry()
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "DataMX" / "features.mmfr"
            canonical = write_runtime_feature_registry(
                path,
                (EnchantmentRowFeature("EF01", "A row"),),
            )
            self.assertEqual(
                decode_runtime_feature_registry(path.read_bytes()), canonical
            )

    def test_compose_proves_package_owned_resources_and_description_use(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            description = root / "features.xml"
            description.write_text(
                """<Majesty>
<Description type="Unit" subType="Character" ID="H001">
  <Game><NameGenType value="NM20"/></Game>
</Description>
<Description type="Unit" subType="Overlay" ID="EF01"/>
</Majesty>
""",
                encoding="utf-8",
            )
            features = (
                NameGeneratorFeature(
                    "NM20", ("HN81", "HN82", "HN83", "HN84")
                ),
                EnchantmentRowFeature("EF01", "A private row"),
            )
            inventory = _feature_inventory("owner", root, description, features)
            self.assertEqual(
                resolve_runtime_feature_registry((inventory,)),
                normalize_runtime_features(features),
            )

            missing_table = PackageInventory(
                selected=inventory.selected,
                cams=inventory.cams,
                descriptions=inventory.descriptions,
                gpl_loads=inventory.gpl_loads,
                resources=inventory.resources[:-1],
            )
            with self.assertRaisesRegex(ComposeError, "STRT/HN84"):
                resolve_runtime_feature_registry((missing_table,))

            description.write_text(
                "<Majesty><Description type=\"Unit\" subType=\"Overlay\" "
                "ID=\"EF02\"/></Majesty>",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ComposeError, "NameGenType"):
                resolve_runtime_feature_registry((inventory,))

    def test_compose_rejects_cross_package_feature_ownership(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            description = root / "one.xml"
            description.write_text(
                "<Majesty><Description type=\"Unit\" subType=\"Overlay\" "
                "ID=\"EF01\"/></Majesty>",
                encoding="utf-8",
            )
            feature = EnchantmentRowFeature("EF01", "Shared")
            first = _feature_inventory("first", root, description, (feature,))
            second = _feature_inventory("second", root, description, (feature,))
            with self.assertRaisesRegex(ComposeError, "claimed by both"):
                resolve_runtime_feature_registry((first, second))

    def test_legacy_ap78_group_cannot_split_evidence_across_packages(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_description = root / "first.xml"
            first_description.write_text(
                '<Majesty><Description type="Unit" subType="Overlay" '
                'ID="ALo1"/><Description type="Unit" subType="Overlay" '
                'ID="ALo2"/></Majesty>',
                encoding="utf-8",
            )
            second_description = root / "second.xml"
            second_description.write_text(
                '<Majesty><Description type="Unit" subType="Overlay" '
                'ID="ALo3"/></Majesty>',
                encoding="utf-8",
            )
            first = _feature_inventory(
                "first", root, first_description, ()
            )
            second = _feature_inventory(
                "second", root, second_description, ()
            )
            with self.assertRaisesRegex(
                ComposeError,
                "alchemist.ap78-private-oil-rows.*indivisible feature group",
            ):
                resolve_runtime_feature_registry(
                    (first, second),
                    runtime_capabilities=(
                        "alchemist.ap78-private-oil-rows",
                    ),
                )

            complete_description = root / "complete.xml"
            complete_description.write_text(
                '<Majesty><Description type="Unit" subType="Overlay" '
                'ID="ALo1"/><Description type="Unit" subType="Overlay" '
                'ID="ALo2"/><Description type="Unit" subType="Overlay" '
                'ID="ALo3"/></Majesty>',
                encoding="utf-8",
            )
            complete = _feature_inventory(
                "complete", root, complete_description, ()
            )
            registry = resolve_runtime_feature_registry(
                (first, second, complete),
                runtime_capabilities=(
                    "alchemist.ap78-private-oil-rows",
                ),
            )
            self.assertEqual(
                tuple(row.overlay_id for row in registry.enchantment_rows),
                ("ALo1", "ALo2", "ALo3"),
            )

    def test_v3_requires_every_private_name_selection_to_be_declared(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            description = root / "private-name.xml"
            description.write_text(
                '<Majesty><Description type="Unit" subType="Character" '
                'ID="H001"><Game><NameGenType value="NM42"/></Game>'
                '</Description></Majesty>',
                encoding="utf-8",
            )
            inventory = _feature_inventory("owner", root, description, ())
            inventory.selected.package.definition.schema_version = 3
            with self.assertRaisesRegex(ComposeError, "NM42"):
                resolve_runtime_feature_registry((inventory,))

            description.write_text(
                '<Majesty><Description type="Unit" subType="Character" '
                'ID="H001"><Game><NameGenType value="NM17"/></Game>'
                '</Description></Majesty>',
                encoding="utf-8",
            )
            self.assertEqual(
                resolve_runtime_feature_registry((inventory,)),
                RuntimeFeatureRegistry(),
            )

    def test_v2_punctuation_name_generators_cannot_bypass_closed_world_scan(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for generator in ("NM_1", "NM-1"):
                with self.subTest(generator=generator):
                    description = root / f"{generator}.xml"
                    description.write_text(
                        '<Majesty><Description type="Unit" '
                        'subType="Character" ID="H001"><Game>'
                        f'<NameGenType value="{generator}" />'
                        '</Game></Description></Majesty>',
                        encoding="utf-8",
                    )
                    inventory = _feature_inventory(
                        generator, root, description, ()
                    )
                    inventory.selected.package.definition.schema_version = 2
                    with self.assertRaisesRegex(ComposeError, generator):
                        resolve_runtime_feature_registry((inventory,))

                    feature = NameGeneratorFeature(
                        generator, ("HN81", "HN82", "HN83", "HN84")
                    )
                    declared = _feature_inventory(
                        generator + "-declared", root, description, (feature,)
                    )
                    declared.selected.package.definition.schema_version = 3
                    self.assertEqual(
                        resolve_runtime_feature_registry((declared,)).name_generators,
                        (feature,),
                    )


def _feature_inventory(
    owner: str,
    root: Path,
    description: Path,
    features,
) -> PackageInventory:
    definition = SimpleNamespace(
        runtime_features=tuple(features), runtime_capabilities=()
    )
    package = SimpleNamespace(definition=definition)
    resources = tuple(
        CamResource(
            owner=owner,
            source=root / f"{table}.cam",
            cam_order=0,
            section_order=0,
            entry_order=index,
            section=b"STRT",
            entry=CamEntry(name=pad_name(table.encode("ascii")), data=b"table"),
        )
        for index, table in enumerate(
            part
            for feature in features
            if isinstance(feature, NameGeneratorFeature)
            for part in feature.name_part_ids
        )
    )
    return PackageInventory(
        selected=SelectedMod(owner, package),
        cams=(),
        descriptions=(description,),
        gpl_loads=(),
        resources=resources,
    )


if __name__ == "__main__":
    unittest.main()
