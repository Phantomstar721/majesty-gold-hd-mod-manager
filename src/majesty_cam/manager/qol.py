"""Legacy status view retained for older controller and UI adapters.

All inspection, installation, removal, and elevation behavior belongs to
``qol_service``. Keeping only this small value object prevents launch behavior
from drifting away from the Manager's declarative QOL registry.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QolPatchStatus:
    name: str
    available: bool
    installed: bool
    detail: str


__all__ = ["QolPatchStatus"]
