"""Application version, shared by packaging and the visible Manager header."""

__version__ = "0.3.14"
BUILD_CHANNEL = "development"
MANAGER_VERSION = __version__ + (" (beta)" if BUILD_CHANNEL == "development" else "")

import os
if os.environ.get("MAJESTY_MANAGER_EDITION") == "panel-engine-alpha":
    MANAGER_VERSION = __version__ + " (panel engine alpha)"
