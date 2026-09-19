"""Opt-in movement distance scaling owned by a native attached overlay."""
from dataclasses import asdict, dataclass

MOVEMENT_SCALE_TYPE = "manager.overlay-movement-scale.v1"
MAX_MOVEMENT_SCALES = 256


@dataclass(frozen=True)
class OverlayMovementScale:
    overlay_id: str
    percent: int


def parse_movement_scale(value):
    from .runtime_features import _fourcc_bytes
    if set(value) != {"type", "overlay_id", "percent"} or value.get("type") != MOVEMENT_SCALE_TYPE:
        raise ValueError("overlay movement scale requires exactly type, overlay_id and percent")
    _fourcc_bytes(value["overlay_id"])
    if type(value["percent"]) is not int or not 1 <= value["percent"] <= 1000:
        raise ValueError("overlay movement percent must be an integer from 1 to 1000")
    return OverlayMovementScale(value["overlay_id"], value["percent"])


def movement_scale_mapping(record):
    value = dict(type=MOVEMENT_SCALE_TYPE, **asdict(record))
    parse_movement_scale(value)
    return value


def validate_movement_scale_evidence(inventory, record):
    from .compose import _parse_description_file
    movement_scale_mapping(record)
    matches = [item.to_element() for path in inventory.descriptions
               for item in _parse_description_file(path).records
               if item.key == ("Unit", record.overlay_id)]
    if len(matches) != 1 or matches[0].get("subType") != "Overlay":
        raise ValueError(f"movement scale {record.overlay_id} requires exactly one package-owned Unit/Overlay Description")
