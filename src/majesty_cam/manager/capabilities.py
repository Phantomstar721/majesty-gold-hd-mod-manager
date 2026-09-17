"""Runtime capabilities understood by this Mod Manager build.

Capability names are data, not package identities.  Keeping the supported set
in one module lets package-owned v2 definitions fail closed during both catalog
discovery and the deeper build preflight.
"""

from __future__ import annotations

from ..runtime_capabilities import PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY
from ..runtime_features import (
    ENCHANTMENT_ROW_RUNTIME_CAPABILITY,
    NAME_GENERATOR_RUNTIME_CAPABILITY,
    MAP_QUERY_RUNTIME_CAPABILITY,
    MOVEMENT_QUERY_RUNTIME_CAPABILITY,
)
from ..stock_controller_registry import STOCK_CONTROLLER_RUNTIME_CAPABILITY


GENERIC_RUNTIME_CAPABILITIES = (
    "expanded-building-slots.cg-prefix",
    "freestyle-cam-rebind.v1",
)

DERIVED_RUNTIME_CAPABILITIES = frozenset(
    (
        PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY,
        ENCHANTMENT_ROW_RUNTIME_CAPABILITY,
        NAME_GENERATOR_RUNTIME_CAPABILITY,
        MAP_QUERY_RUNTIME_CAPABILITY,
        MOVEMENT_QUERY_RUNTIME_CAPABILITY,
        STOCK_CONTROLLER_RUNTIME_CAPABILITY,
    )
)

SUPPORTED_RUNTIME_CAPABILITIES = frozenset(
    (
        *GENERIC_RUNTIME_CAPABILITIES,
        "alchemist.cgbrewing-secondary-controller",
        "alchemist.ap78-private-oil-rows",
        "alchemist.nm18-name-generator",
        "generic-visitor-lists.v1",
        "phantom.nm19-name-generator",
        ENCHANTMENT_ROW_RUNTIME_CAPABILITY,
        NAME_GENERATOR_RUNTIME_CAPABILITY,
        STOCK_CONTROLLER_RUNTIME_CAPABILITY,
        *DERIVED_RUNTIME_CAPABILITIES,
    )
)


__all__ = [
    "DERIVED_RUNTIME_CAPABILITIES",
    "GENERIC_RUNTIME_CAPABILITIES",
    "SUPPORTED_RUNTIME_CAPABILITIES",
]
