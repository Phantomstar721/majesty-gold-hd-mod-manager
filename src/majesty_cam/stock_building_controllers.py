"""Verified stock primary-building controller catalog.

The catalog is deliberately static.  Package metadata selects one of these
already-audited stock controller classes; it never supplies executable
addresses or vtable sizes.  The native runtime carries the same table and
validates the selected live object before installing a scoped wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockControllerVtableProfile:
    vtable_rva: int
    entry_count: int
    destructor_rva: int
    setup_rva: int
    control_rva: int
    event_rva: int


@dataclass(frozen=True)
class StockBuildingController:
    controller_base: str
    panel_resource_templates: tuple[str, ...]
    public: StockControllerVtableProfile
    beta2: StockControllerVtableProfile


def _profile(
    vtable: int,
    count: int,
    destructor: int,
    setup: int,
    control: int,
    event: int,
) -> StockControllerVtableProfile:
    return StockControllerVtableProfile(
        vtable, count, destructor, setup, control, event
    )


# Dialogs that enter the same constructor share one immutable class profile.
# The RVAs were traced independently in the public 1.5.2.24 and beta2
# 1.5.2.28 factories; counts stop at the first non-executable vtable word.
_PUBLIC_GUILD = _profile(0x0033D184, 17, 0x00095F60, 0x00095BD0, 0x000968B0, 0x00096170)
_BETA2_GUILD = _profile(0x00355E5C, 17, 0x00096770, 0x000963E0, 0x000970C0, 0x00096980)
_PUBLIC_BASIC = _profile(0x0033D14C, 13, 0x00094EE0, 0x00095990, 0x00095790, 0x000959F0)
_BETA2_BASIC = _profile(0x00355E24, 13, 0x000956F0, 0x000961A0, 0x00095FA0, 0x00096200)


def _controller(
    controller_base: str,
    public: StockControllerVtableProfile,
    beta2: StockControllerVtableProfile,
    *alternate_templates: str,
) -> StockBuildingController:
    return StockBuildingController(
        controller_base,
        (controller_base, *alternate_templates),
        public,
        beta2,
    )


STOCK_BUILDING_CONTROLLERS = (
    _controller("AP01", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP02", _profile(0x0033D274, 13, 0x00099290, 0x00099530, 0x000992B0, 0x00099540), _profile(0x00355F4C, 13, 0x00099B70, 0x00099E10, 0x00099B90, 0x00099E20)),
    _controller("AP05", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP06", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP07", _PUBLIC_GUILD, _BETA2_GUILD, "AP10"),
    _controller("AP08", _profile(0x0033D37C, 13, 0x0009E2A0, 0x0009E5D0, 0x0009E660, 0x0009E600), _profile(0x00356054, 13, 0x0009EB80, 0x0009EEB0, 0x0009EF40, 0x0009EEE0)),
    _controller("AP10", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP14", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP17", _profile(0x0033D4A4, 13, 0x000A0370, 0x000A0320, 0x000A0330, 0x000A0360), _profile(0x0035617C, 13, 0x000A0C50, 0x000A0C00, 0x000A0C10, 0x000A0C40)),
    _controller("AP19", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP23", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("AP24", _profile(0x0033E534, 17, 0x000B17D0, 0x000B0FA0, 0x000B1090, 0x000B15A0), _profile(0x0035720C, 17, 0x000B20C0, 0x000B1890, 0x000B1980, 0x000B1E90)),
    _controller("AP25", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP26", _profile(0x0033D7B4, 13, 0x000A4D70, 0x000A4D90, 0x000A4DA0, 0x00096EB0), _profile(0x0035648C, 13, 0x000A5670, 0x000A5690, 0x000A56A0, 0x000976C0)),
    _controller("AP28", _PUBLIC_GUILD, _BETA2_GUILD),
    _controller("AP31", _profile(0x0033D804, 14, 0x000A4F00, 0x000A4F30, 0x000A5130, 0x000A4F50), _profile(0x003564DC, 14, 0x000A5800, 0x000A5830, 0x000A5A30, 0x000A5850)),
    _controller("AP39", _profile(0x0033D888, 13, 0x000A57C0, 0x000A5620, 0x000A5440, 0x000A56A0), _profile(0x00356560, 13, 0x000A60C0, 0x000A5F20, 0x000A5D40, 0x000A5FA0)),
    _controller("AP47", _profile(0x0033D8C4, 17, 0x000A5D50, 0x000A5B90, 0x000A5BA0, 0x000A5CF0), _profile(0x0035659C, 17, 0x000A6650, 0x000A6490, 0x000A64A0, 0x000A65F0)),
    _controller("AP48", _profile(0x0033E054, 17, 0x000AA1B0, 0x000AA3F0, 0x000AA400, 0x00096170), _profile(0x00356D2C, 17, 0x000AAAA0, 0x000AACE0, 0x000AACF0, 0x00096980)),
    _controller("AP51", _profile(0x0033E5BC, 13, 0x000B1D60, 0x000B1D80, 0x000B1D90, 0x000B1DC0), _profile(0x00357294, 13, 0x000B2650, 0x000B2670, 0x000B2680, 0x000B26B0)),
    _controller("AP52", _profile(0x0033E5F4, 17, 0x000B1EA0, 0x000B2010, 0x000B2170, 0x000B22C0), _profile(0x003572CC, 17, 0x000B2790, 0x000B2900, 0x000B2A60, 0x000B2BB0)),
    _controller("AP53", _profile(0x0033E674, 17, 0x000B3010, 0x000B3220, 0x000B3040, 0x000B3240), _profile(0x0035734C, 17, 0x000B3900, 0x000B3B10, 0x000B3930, 0x000B3B30)),
    _controller("AP54", _profile(0x0033E71C, 13, 0x000B3A80, 0x000B3740, 0x000B3750, 0x000B37D0), _profile(0x003573F4, 13, 0x000B4370, 0x000B4030, 0x000B4040, 0x000B40C0)),
    _controller("AP76", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("AP96", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("APa9", _profile(0x0033D784, 11, 0x000A4B90, 0x000A4C00, 0x000A4C30, 0x000A4C60), _profile(0x0035645C, 11, 0x000A5490, 0x000A5500, 0x000A5530, 0x000A5560)),
    _controller("APb2", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("APb3", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("APb7", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("APb8", _profile(0x0033D400, 11, 0x0009F240, 0x0009F670, 0x0009F7C0, 0x0009F920), _profile(0x003560D8, 11, 0x0009FB20, 0x0009FF50, 0x000A00A0, 0x000A0200)),
    _controller("APc3", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("APc4", _PUBLIC_BASIC, _BETA2_BASIC),
    _controller("MX00", _profile(0x0033E990, 13, 0x000BADD0, 0x000BAC70, 0x000BAA40, 0x000BAC80), _profile(0x00357678, 13, 0x000BB810, 0x000BB6B0, 0x000BB480, 0x000BB6C0)),
    _controller("MX02", _profile(0x0033EA34, 13, 0x000BBAC0, 0x000BBB20, 0x000BBB30, 0x000BBB60), _profile(0x0035771C, 13, 0x000BC500, 0x000BC560, 0x000BC570, 0x000BC5A0)),
    _controller("MX04", _profile(0x0033EA6C, 13, 0x000BBCC0, 0x000BBD20, 0x000BBD30, 0x000BBD60), _profile(0x00357754, 13, 0x000BC700, 0x000BC760, 0x000BC770, 0x000BC7A0)),
    _controller("MX06", _profile(0x0033EB64, 13, 0x000BCEF0, 0x000BD260, 0x000BCF50, 0x000BD220), _profile(0x0035784C, 13, 0x000BD930, 0x000BDCA0, 0x000BD990, 0x000BDC60)),
    _controller("MX08", _profile(0x0033EB2C, 13, 0x000BCD00, 0x000BCDA0, 0x000BCD20, 0x000BCDD0), _profile(0x00357814, 13, 0x000BD740, 0x000BD7E0, 0x000BD760, 0x000BD810)),
    _controller("MX09", _profile(0x0033EB9C, 13, 0x000BD390, 0x000BD270, 0x000BD280, 0x000BD290), _profile(0x00357884, 13, 0x000BDDD0, 0x000BDCB0, 0x000BDCC0, 0x000BDCD0)),
    _controller("MX22", _profile(0x0033E91C, 17, 0x000B9A30, 0x000B98A0, 0x000B9540, 0x000B98B0), _profile(0x00357604, 17, 0x000BA470, 0x000BA2E0, 0x000B9F80, 0x000BA2F0)),
)


_BY_CONTROLLER = {
    record.controller_base: record for record in STOCK_BUILDING_CONTROLLERS
}


def stock_building_controller(
    controller_base: str,
) -> StockBuildingController | None:
    return _BY_CONTROLLER.get(controller_base)


def is_stock_building_controller(controller_base: str) -> bool:
    return controller_base in _BY_CONTROLLER


def is_stock_building_controller_pair(
    controller_base: str, panel_resource_template: str
) -> bool:
    record = stock_building_controller(controller_base)
    return (
        record is not None
        and panel_resource_template in record.panel_resource_templates
    )


SUPPORTED_STOCK_BUILDING_CONTROLLER_IDS = frozenset(_BY_CONTROLLER)
SUPPORTED_STOCK_BUILDING_CONTROLLER_PAIRS = frozenset(
    (record.controller_base, template)
    for record in STOCK_BUILDING_CONTROLLERS
    for template in record.panel_resource_templates
)


__all__ = (
    "STOCK_BUILDING_CONTROLLERS",
    "SUPPORTED_STOCK_BUILDING_CONTROLLER_IDS",
    "SUPPORTED_STOCK_BUILDING_CONTROLLER_PAIRS",
    "StockBuildingController",
    "StockControllerVtableProfile",
    "is_stock_building_controller",
    "is_stock_building_controller_pair",
    "stock_building_controller",
)
