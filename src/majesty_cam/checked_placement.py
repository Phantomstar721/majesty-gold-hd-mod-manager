"""Bounded stock-cast/checked-placement declarations; no package-supplied code."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import copy
import hashlib
import re
import struct
from .attack_observation import _description_index, _shape, require_exact_profile
from .gameplay_events import stock_tokens
from .gpl import DefinitionKind
from .spell_policy import signature

FEATURE_TYPE = "stock.checked-placement.v1"
PRESENTED_FEATURE_TYPE = "stock.checked-placement.v2"
LEARNED_FEATURE_TYPE = "stock.checked-placement.v3"
CAPABILITY = "manager.checked-placement.v1"
# Covers the diagonal of the native adapter's maximum 65535-tile square.
MAXIMUM_RANGE = 2 * 65535 * 16
RELATIVE_PATH = "DataMX/majesty_mod_manager_checked_placement.bin"
_FIELDS = ("feature_key", "api_prefix", "actor", "action", "release_callback_symbol", "movement_callback_symbol")
_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")

@dataclass(frozen=True)
class CheckedPlacement:
    feature_key: str
    api_prefix: str
    actor: str
    action: str
    release_callback_symbol: str
    movement_callback_symbol: str
    maximum_range: int = 600
    type: str = FEATURE_TYPE
    arrival_action: str | None = None
    required_level: int = 0

EXPORT_ARGUMENTS = (("Ready",("out integer","agent")),
    ("Boundary",("out integer","agent","agent","integer")),
    ("Begin",("out integer","agent","agent")),
    ("Commit",("out integer","agent","agent")))

def exports(feature):
    return tuple((feature.api_prefix+"_"+name,args) for name,args in EXPORT_ARGUMENTS)

def parse_feature(value):
    learned=isinstance(value,dict) and value.get("type")==LEARNED_FEATURE_TYPE
    presented=isinstance(value,dict) and value.get("type") in (PRESENTED_FEATURE_TYPE,LEARNED_FEATURE_TYPE)
    fields=set(CheckedPlacement.__dataclass_fields__)
    if not presented:fields.remove("arrival_action")
    if not learned:fields.remove("required_level")
    if not isinstance(value,dict) or set(value)!=fields or value.get("type") not in (FEATURE_TYPE,PRESENTED_FEATURE_TYPE,LEARNED_FEATURE_TYPE):
        raise ValueError("checked placement requires exact versioned fields; offsets and code are forbidden")
    if learned and (type(value["required_level"]) is not int or not 1<=value["required_level"]<=1000):
        raise ValueError("learned placement requires an explicit level in 1..1000")
    for field in _FIELDS+(("arrival_action",) if presented else ()):
        name=value[field]
        if not isinstance(name,str) or not _SYMBOL.fullmatch(name) or name.lower().startswith("mm_"):
            raise ValueError("checked placement names must be bounded unreserved identifiers")
    if len(value["api_prefix"])>46 or type(value["maximum_range"]) is not int or not 1<=value["maximum_range"]<=MAXIMUM_RANGE:
        raise ValueError("checked placement range/prefix is outside its bounded contract")
    feature=CheckedPlacement(**value)
    if presented and feature.arrival_action.casefold()==feature.action.casefold():
        raise ValueError("placement departure and arrival must be distinct private actions")
    names=[n.casefold() for n,_ in exports(feature)]+[feature.release_callback_symbol.casefold(),feature.movement_callback_symbol.casefold()]
    if len(set(names))!=len(names):raise ValueError("checked placement callback/export collision")
    return feature

def feature_mapping(feature):
    value=asdict(feature)
    if feature.type!=LEARNED_FEATURE_TYPE:
        if feature.required_level!=0:raise ValueError("legacy placement cannot declare a learned level")
        value.pop("required_level")
    if feature.type==FEATURE_TYPE:
        if feature.arrival_action is not None:raise ValueError("placement v1 cannot declare an arrival action")
        value.pop("arrival_action")
    parse_feature(value);return value

def declared(definition):
    return any(isinstance(f,CheckedPlacement) for f in getattr(definition,"runtime_features",()))

def selected(inventories):
    return any(declared(i.selected.package.definition) for i in inventories if i.selected.package.definition)

def release_source(feature):
    # Literal Teleport_Effect ordering/ownership, with the approved captured
    # target replacing Teleport_DoMove's mutable current-target lookup.
    return f"""function {feature.release_callback_symbol}(agent thisagent, agent target)
declare
    integer theTimePeriod;
begin
    theTimePeriod = $GetSpellAttribute("{feature.action}", "effector_duration");
    $createeffector(thisagent, "teleport_effector", theTimePeriod);
    thisagent's "teleportScript" = ${feature.movement_callback_symbol};
    $RunThread(thisagent's "teleportScript", theTimePeriod / 2, thisagent, target);
end
"""

@dataclass(frozen=True)
class Binding:
    owner: str
    feature: CheckedPlacement

def validate_bindings(packages,effective_descriptions,effective_functions,stock_descriptions, *, spell_policy_plan=None):
    packages=tuple(packages)
    effective_descriptions=tuple(effective_descriptions)
    stock_descriptions=tuple(stock_descriptions)
    relevant={(kind,name.casefold()) for _,features,_,_ in packages for f in features
              for kind,name in (("unit",f.actor),("action",f.action),("action","teleport"),
                                ("action",f.arrival_action or "standup"),("action","standup"))}
    # Inspect only the release's overlay identity, not unrelated overlay names
    # which may legitimately repeat across stock scopes.
    relevant.add(("unit","teleport_effector"))
    for _,features,_,sources in packages:
        for feature in features:
            slot=stock_tokens(release_source(feature)).index('"teleport_effector"')
            for source in sources:
                for item in source.items:
                    if item.kind is DefinitionKind.FUNCTION and item.normalized_name==feature.release_callback_symbol.casefold():
                        tokens=stock_tokens(item.text)
                        if len(tokens)>slot and re.fullmatch(r'"[A-Za-z_][A-Za-z0-9_]{0,63}"',tokens[slot]):
                            relevant.add(("unit",tokens[slot][1:-1].casefold()))
    effective=_description_index(effective_descriptions,relevant)
    stock=_description_index(stock_descriptions,relevant)
    functions={}
    for item in effective_functions:
        if item.kind is DefinitionKind.FUNCTION:
            if item.normalized_name in functions:raise ValueError("ambiguous effective placement function")
            functions[item.normalized_name]=item
    result=[];all_owned={}
    for owner,features,records,sources in packages:
        for source in sources:
            for item in source.items:
                if item.kind is DefinitionKind.FUNCTION:all_owned.setdefault(item.normalized_name,[]).append((owner,item))
    for owner,features,records,sources in packages:
        own=_description_index(records,relevant)
        for feature in features:
            parse_feature(feature_mapping(feature))
            policy_action = next((a for a in getattr(spell_policy_plan, "actions", ())
                                  if a.name.casefold() == feature.action.casefold() and a.native_begin), None)
            if policy_action:
                from .spell_policy import suppress_cast, SUPPRESS
                if (policy_action.native_begin != feature.api_prefix + "_Begin" or
                        policy_action.cast.casefold() != feature.release_callback_symbol.casefold()):
                    raise ValueError("placement spell policy differs from its typed declaration")
                wrapper = functions.get(policy_action.wrapper("Begin").casefold())
                if (wrapper is None or stock_tokens(wrapper.text) != stock_tokens(policy_action.begin_source())
                        or SUPPRESS.casefold() not in functions):
                    raise ValueError("placement spell admission guard missing or changed")
            actor=effective.get(("unit",feature.actor.casefold()))
            action=effective.get(("action",feature.action.casefold()))
            reference=stock.get(("action","teleport"))
            if actor is None or action is None or reference is None:raise ValueError("checked placement actor/action/stock teleport missing")
            action_key=("action",feature.action.casefold())
            if action_key not in own or _shape(own[action_key])!=_shape(action):raise ValueError("placement action must be private, owned and unchanged in composed output")
            if action_key in stock:raise ValueError("placement action must not replace a stock action")
            actor_xml=actor.to_element();engine=actor_xml.find("Engine")
            if actor_xml.get("subType")!="Character" or engine is None or engine.find("Info") is None or engine.find("Info").get("value")!="BlockGround":
                raise ValueError("placement actor must use a supported ground Character descriptor")
            moves=[a for a in engine.findall("Attachment") if a.get("kind")=="Movement"]
            if len(moves)!=1 or moves[0].get("type")!="Walk":raise ValueError("placement actor needs one normal Walk attachment")
            expected=copy.deepcopy(reference.to_element());actual=action.to_element()
            for field in ("ID","Name","Description"):
                if field in actual.attrib:expected.set(field,actual.get(field))
                else:expected.attrib.pop(field,None)
            expected.find("Engine/Script").set("GPLFunction",feature.release_callback_symbol)
            expected.find("Game/TimeoutDuration").set("value","0")
            if feature.type==LEARNED_FEATURE_TYPE:
                # Stock named None maps to category zero on all three profiles.
                # The normal list1..4 selector skips it before validation.
                expected.find("Game/SpellType").set("value","None")
                expected.find("Game/CharacterLevel").set("value",str(feature.required_level))
            if feature.arrival_action:
                expected.find("Engine/ImageSet").set("value","Special-2")
            # Compare every remaining element, order and attribute to WRd1.
            from .descriptions import parse_descriptions
            import xml.etree.ElementTree as ET
            expected_record=parse_descriptions("<Majesty>"+ET.tostring(expected,encoding="unicode")+"</Majesty>").records[0]
            if _shape(expected_record)!=_shape(action):raise ValueError("placement action differs from the permitted stock teleport clone")
            if feature.arrival_action:
                key=("action",feature.arrival_action.casefold())
                arrival=effective.get(key);standup=stock.get(("action","standup"))
                if arrival is None or standup is None or key not in own or key in stock or _shape(own[key])!=_shape(arrival):
                    raise ValueError("placement arrival must be private, owned and unchanged in composed output")
                expected=copy.deepcopy(standup.to_element());actual=arrival.to_element()
                for field in ("ID","Name","Description"):
                    if field in actual.attrib:expected.set(field,actual.get(field))
                    else:expected.attrib.pop(field,None)
                if expected.find("Engine/ImageSet").get("value")!="Special-3" or expected.find("Engine/CompletionImageSet").get("value")!="Stand":
                    raise ValueError("placement stock Standup selectors differ from the audited lifecycle")
                record=parse_descriptions("<Majesty>"+ET.tostring(expected,encoding="unicode")+"</Majesty>").records[0]
                if _shape(record)!=_shape(arrival):raise ValueError("placement arrival must retain the literal stock Standup action")
            for name in (feature.release_callback_symbol,feature.movement_callback_symbol):
                key=name.casefold();owned=all_owned.get(key,[]);item=functions.get(key)
                if len(owned)!=1 or owned[0][0]!=owner or item is None:raise ValueError("placement callback must be uniquely owned and emitted")
                signature(item,("agent","agent"))
                expected_item = owned[0][1]
                if policy_action and key == feature.release_callback_symbol.casefold():
                    expected_item = suppress_cast(expected_item, feature.action)
                if stock_tokens(item.text)!=stock_tokens(expected_item.text):raise ValueError("placement callback overridden in composed output")
            original_release = all_owned[feature.release_callback_symbol.casefold()][0][1]
            actual_tokens=stock_tokens(original_release.text)
            expected_tokens=stock_tokens(release_source(feature))
            overlay_slot=expected_tokens.index('"teleport_effector"')
            if (len(actual_tokens)!=len(expected_tokens) or
                    actual_tokens[:overlay_slot]!=expected_tokens[:overlay_slot] or
                    actual_tokens[overlay_slot+1:]!=expected_tokens[overlay_slot+1:]):
                raise ValueError("placement release must retain the stock effector/function-value/RunThread sequence")
            overlay_token=actual_tokens[overlay_slot]
            if overlay_token!='"teleport_effector"':
                if not re.fullmatch(r'"[A-Za-z_][A-Za-z0-9_]{0,63}"',overlay_token):
                    raise ValueError("placement transition must name a stock overlay or private clone")
                key=("unit",overlay_token[1:-1].casefold())
                overlay=effective.get(key)
                reference=stock.get(("unit","teleport_effector"))
                if (overlay is None or reference is None or key not in own or key in stock
                        or _shape(own[key])!=_shape(overlay)):
                    raise ValueError("placement transition overlay must be private, owned and unchanged")
                expected=copy.deepcopy(reference.to_element())
                actual=overlay.to_element()
                for field in ("ID","Name","Description"):
                    if field in actual.attrib:expected.set(field,actual.get(field))
                    else:expected.attrib.pop(field,None)
                # Existing stock hidden overlays use this rendering flag. No
                # script, timing, attachment, sound or lifecycle edits allowed.
                hidden=actual.findall('./Engine/Info[@value="NotVisibleInISOView"]')
                if len(hidden)==1:
                    ET.SubElement(expected.find("Engine"),"Info",{"value":"NotVisibleInISOView"})
                expected_record=parse_descriptions("<Majesty>"+ET.tostring(expected,encoding="unicode")+"</Majesty>").records[0]
                if _shape(expected_record)!=_shape(overlay):
                    raise ValueError("placement transition overlay differs from stock visual clone")
            for name,_ in exports(feature):
                if name.casefold() in all_owned or name.casefold() in functions:raise ValueError("placement native alias collision")
            result.append(Binding(owner,feature))
    if len(result)>1:raise ValueError("checked placement v1 supports exactly one binding")
    return tuple(result)

def encode(feature,observation_bytes, *, image_id=0):
    value=feature_mapping(feature)
    version=3 if feature.type==LEARNED_FEATURE_TYPE else (2 if feature.arrival_action else 1)
    chunks=[struct.pack("<4sII",b"MMPL",version,feature.maximum_range),hashlib.sha256(observation_bytes).digest()]
    for field in _FIELDS+(("arrival_action",) if feature.arrival_action else ()):
        text=value[field].encode("ascii");chunks.extend((struct.pack("<I",len(text)),text))
    if feature.arrival_action:
        if not 0<image_id<=0xFFFFFFFF:raise ValueError("placement v2 requires a certified effective actor image")
        chunks.append(struct.pack("<I",image_id))
    if version==3:chunks.append(struct.pack("<I",feature.required_level))
    return b"".join(chunks)

def _decode(data):
    if not isinstance(data,bytes) or not 44<=len(data)<=512:raise ValueError("invalid placement proof size")
    magic,version,distance=struct.unpack_from("<4sII",data)
    if magic!=b"MMPL" or version not in (1,2,3):raise ValueError("invalid placement proof version")
    value={"type":{1:FEATURE_TYPE,2:PRESENTED_FEATURE_TYPE,3:LEARNED_FEATURE_TYPE}[version],"maximum_range":distance};pos=44
    for field in _FIELDS+(("arrival_action",) if version>=2 else ()):
        if pos+4>len(data):raise ValueError("truncated placement name")
        size,=struct.unpack_from("<I",data,pos);pos+=4
        if not 1<=size<=64 or pos+size>len(data):raise ValueError("invalid placement name")
        value[field]=data[pos:pos+size].decode("ascii");pos+=size
    image_id=0
    if version>=2:
        if pos+(8 if version==3 else 4)!=len(data) or not struct.unpack_from('<I',data,pos)[0]:
            raise ValueError("missing placement actor image identity")
        image_id,=struct.unpack_from('<I',data,pos)
        pos+=4
    if version==3:
        value["required_level"],=struct.unpack_from('<I',data,pos);pos+=4
    if pos!=len(data):raise ValueError("trailing placement proof data")
    return parse_feature(value),data[12:44],image_id

def decode(data):
    return _decode(data)[:2]

def image_identity(data):
    """Read the certified image field, not the version-dependent final word."""
    return _decode(data)[2]
