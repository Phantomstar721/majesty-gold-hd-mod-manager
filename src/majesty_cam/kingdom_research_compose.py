"""Package evidence for saved kingdom research; no package-specific identities."""
import re
from copy import deepcopy
from xml.etree import ElementTree as ET
from .kingdom_research import KingdomResearch, registration
from .private_recruitment import validate_descriptions, records, control_record, _literal_clone
from .stock_controller_features import StockAp52PrivateRecruitment


def _features(inventory):
    # Ordinary source-only inputs have no typed package definition.
    package = getattr(inventory.selected, "package", None)
    definition = getattr(package, "definition", None)
    return getattr(definition, "runtime_features", ())


def declarations(inventory):
    return tuple(item for item in _features(inventory)
                 if isinstance(item, KingdomResearch))


def _owned(inventory, section, key):
    matches = [item.entry.data for item in inventory.resources
               if item.section == section and item.key == key.encode("ascii")]
    if len(matches) != 1:
        raise ValueError(f"kingdom research needs one owned {section.decode()}/{key}")
    return matches[0]


# Literal stock M_Overlays.xml/super_charge_effector. Only identity, display
# text, private artwork and muting the stock sound are author changes here.
_ACTIVE_EFFECTOR = '''<Description type="Unit" subType="Overlay" ID="WRF1"
Name="super_charge_effector" Description="Super Charge"><Engine version="1">
<Info value="Directionless"/><Info value="DontBlock"/><Menu value="11"/>
<ImageIDBase value="WRF1"/><DefaultSound value="Supercharge"/></Engine>
<Game version="1"><DialogID value="0"/><StackPriority value="0"/>
<Flags value="TransparentToMouse"/></Game></Description>'''


def _shape(element):
    return (element.tag, sorted(element.attrib.items()), (element.text or "").strip(),
            tuple(_shape(child) for child in element))


def validate_active_effector(inventory, descriptions, name):
    if not name:
        return
    matches = [item for item in descriptions if item.get("Name", "").lower() == name.lower()]
    if len(matches) != 1:
        raise ValueError("kingdom research active_effector needs one owned Overlay Description")
    item = deepcopy(matches[0])
    image = item.find("./Engine/ImageIDBase")
    identifier = item.get("ID", "")
    art = image.get("value", "") if image is not None else ""
    if (not re.fullmatch(r"[!-~]{4}", identifier) or identifier == "WRF1" or
            not re.fullmatch(r"[!-~]{4}", art) or art == "WRF1" or
            name.lower() == "super_charge_effector"):
        raise ValueError("kingdom research active_effector requires private identity and artwork")
    stock = ET.fromstring(_ACTIVE_EFFECTOR)
    for field in ("ID", "Name", "Description"):
        item.set(field, stock.get(field))
    image.set("value", "WRF1")
    sound = item.find("./Engine/DefaultSound")
    if sound is not None and sound.get("value") == "0":
        sound.set("value", "Supercharge")
    if _shape(item) != _shape(stock):
        raise ValueError("kingdom research active_effector must retain the stock Super Charge root-owned Overlay shape")
    _owned(inventory, b"IMAG", art)


def bindings(inventories):
    from .compose import _parse_description_file, _parse_inventory_gpl_sources
    from .gpl import DefinitionKind, _mask_non_code
    declared = [(inventory, declarations(inventory)) for inventory in inventories]
    if not any(features for _inventory, features in declared):
        return ()
    result = []
    used_controls, used_attributes, used_families = set(), set(), set()
    # AP99 command IDs are global, including existing private building research.
    for inventory in inventories:
        for feature in _features(inventory):
            if not isinstance(feature, KingdomResearch):
                command = getattr(feature, "action_control_id", None)
                if command is not None:
                    used_controls.add(command)
                attribute = getattr(feature, "attribute_id", None)
                if attribute is not None:
                    used_attributes.add(attribute)
    for inventory, features in declared:
        if not features:
            continue
        definition = inventory.selected.package.definition
        descriptions = [item.to_element() for path in inventory.descriptions
                        for item in _parse_description_file(path).records]
        items = [item for source in _parse_inventory_gpl_sources(inventory) for item in source.items]
        blocks = {item.normalized_name: item for item in items if item.kind is DefinitionKind.DAT_BLOCK}
        prototypes = {item.normalized_name: item for item in items if item.kind is DefinitionKind.PROTOTYPE}
        for feature in features:
            parents = [item for item in definition.custom_buildings
                       if item.local_name == feature.parent_building]
            if len(parents) != 1 or (parents[0].controller_base, parents[0].panel_resource_template) != ("AP52", "AP52"):
                raise ValueError("kingdom research requires an owned AP52/AP52 parent")
            recruitment = [item for item in definition.runtime_features
                           if isinstance(item, StockAp52PrivateRecruitment)
                           and item.parent_building == feature.parent_building]
            if len(recruitment) != 1:
                raise ValueError("kingdom research requires one private AP52 recruitment declaration")
            chain = validate_descriptions(descriptions, feature.parent_building)
            if len(chain) < feature.required_level:
                raise ValueError("kingdom research required level is absent from its building chain")
            titles = set()
            for level, stage in enumerate(chain, 1):
                block = blocks.get(stage.get("Name", "").lower())
                if block is None:
                    raise ValueError("kingdom research requires its package-owned stage DAT templates")
                title = re.findall(r'\(\s*title\s+([A-Za-z_][A-Za-z0-9_]{0,63})\s*\)', block.text, re.I)
                levels = re.findall(r'\(\s*level\s+(\d+)\s*\)', block.text, re.I)
                if len(title) != 1 or levels != [str(level)]:
                    raise ValueError("kingdom research requires explicit consistent DAT title and stage Level values")
                prototype_names = re.findall(r'\{\s*([A-Za-z_][A-Za-z0-9_]*)', block.text)
                if len(prototype_names) != 1:
                    raise ValueError("kingdom research stage DAT must instantiate one prototype")
                prototype_name = prototype_names[0].lower()
                if prototype_name != "guild":
                    prototype = prototypes.get(prototype_name)
                    if prototype is None:
                        raise ValueError("kingdom research needs its private GPL prototype source")
                    declaration = re.split(r'\bbegin\b', _mask_non_code(prototype.text), flags=re.I)[0]
                    fields = {name.strip().lower(): kind.lower()
                              for kind, names in re.findall(r'\b(string|integer)\s+([\w\s,]+);', declaration, re.I)
                              for name in names.split(',')}
                    if fields.get("title") != "string" or fields.get("level") != "integer":
                        raise ValueError("kingdom research private prototype must declare string title and integer Level; DAT values alone do not create them")
                titles.add(title[0])
            if len(titles) != 1:
                raise ValueError("kingdom research stages must share one GPL title")
            family = chain[0].get("ID")[:3]
            record = registration(inventory.selected.package.mod_id, feature, family)
            validate_active_effector(inventory, descriptions, feature.active_effector)
            if record.action_control_id in used_controls or record.completion_attribute in used_attributes:
                raise ValueError("kingdom research collides with another research command or saved attribute")
            if record.building_family in used_families:
                raise ValueError("kingdom research supports one research row per building family")
            used_controls.add(record.action_control_id)
            used_attributes.add(record.completion_attribute)
            used_families.add(record.building_family)
            dialog = chain[0].find("./Game/DialogID").get("value")
            panel = records(_owned(inventory, b"SMNU", dialog))
            _owned(inventory, b"STRT", dialog)
            for control in (feature.action_control_id, feature.price_control_id,
                            feature.icon_control_id, feature.progress_control_id,
                            feature.active_display_control_id):
                control_record(panel, control)
                if control in (recruitment[0].third_price_control_id,
                               getattr(recruitment[0], "open_command_id", 0)):
                    raise ValueError("kingdom research overlaps a recruitment control")
                for other in definition.runtime_features:
                    if other is feature or getattr(other, "parent_building", None) != feature.parent_building:
                        continue
                    if any(value == control for name, value in vars(other).items()
                           if name.endswith(("_control_id", "_command_id"))):
                        raise ValueError("kingdom research overlaps another feature's parent control")
            result.append((record, next(iter(titles))))
    return tuple(result)


def validate_panels(inventories, templates):
    from .compose import _parse_description_file
    stock = {key: records(value) for key, value in templates.items()}
    for inventory in inventories:
        if not declarations(inventory):
            continue
        descriptions = [item.to_element() for path in inventory.descriptions
                        for item in _parse_description_file(path).records]
        for feature in declarations(inventory):
            chain = validate_descriptions(descriptions, feature.parent_building)
            dialog = chain[0].find("./Game/DialogID").get("value")
            panel = records(_owned(inventory, b"SMNU", dialog))
            # These are existing native widget layouts, not arbitrary resizing.
            # AP24 is presentation only; no timed spell behavior is borrowed.
            groups = (
                ((feature.action_control_id, b"AP99", 0x1388),
                 (feature.price_control_id, b"AP99", 0x1770),
                 (feature.progress_control_id, b"AP52", 0x1F56),
                 (feature.active_display_control_id, b"AP52", 0x1F57)),
                ((feature.action_control_id, b"AP24", 0x1F49),
                 (feature.price_control_id, b"AP24", 0x1184),
                 (feature.progress_control_id, b"AP24", 0x2009),
                 (feature.active_display_control_id, b"AP24", 0x227A)),
            )
            def matches(group):
                return all(_literal_clone(control_record(panel, control),
                    control_record(stock[template], original), control=control,
                    template_control=original, artwork_set=True)
                    for control, template, original in group)
            if not any(matches(group) for group in groups):
                raise ValueError("kingdom research needs one coherent stock AP99 or compact AP24 action/quote/progress/display group")
            for control, template, original in (
                (feature.icon_control_id, b"AP99", 0x157C),
            ):
                if not _literal_clone(control_record(panel, control),
                        control_record(stock[template], original), control=control,
                        template_control=original, artwork_set=True):
                    raise ValueError(f"kingdom research control 0x{control:X} must retain its literal {template.decode()}/0x{original:X} widget")


def validate_generated(inventory, record):
    from .compose import _parse_description_file, _parse_inventory_gpl_sources
    from .gpl import DefinitionKind
    family = record.building_family.to_bytes(3, "little").decode("ascii")
    descriptions = [item.to_element() for path in inventory.descriptions
                    for item in _parse_description_file(path).records]
    validate_active_effector(inventory, descriptions, record.active_effector)
    stages = [item for item in descriptions if item.get("subType") == "Building"
              and item.get("ID", "")[:3] == family]
    if not any(item.get("ID") == family + str(record.required_level) for item in stages):
        raise ValueError("generated kingdom research is missing its required building stage")
    dialogs = set()
    for stage in stages:
        dialog = stage.find("./Game/DialogID")
        if dialog is None or not dialog.get("value"):
            raise ValueError("generated kingdom research stage is missing its parent dialog")
        dialogs.add(dialog.get("value"))
    if len(dialogs) != 1:
        raise ValueError("generated kingdom research parent is ambiguous")
    panel = records(_owned(inventory, b"SMNU", next(iter(dialogs))))
    for control in (record.action_control_id, record.action_control_id+500,
                    record.action_control_id+1000, record.progress_control_id,
                    record.active_display_control_id):
        control_record(panel, control)
    functions = {item.normalized_name for source in _parse_inventory_gpl_sources(inventory)
                 for item in source.items if item.kind is DefinitionKind.FUNCTION}
    if record.callback_symbol.lower() not in functions or not {"mm_kr_gold", "mm_kr_xp"} <= functions:
        raise ValueError("generated kingdom research lacks its saved-state/award service")
    if record.active_effector and not {record.callback_symbol.lower()+suffix
                                     for suffix in ("_visual", "_visuals")} <= functions:
        raise ValueError("generated kingdom research lacks its active-effector service")
