"""Application version, shared by packaging and the visible Manager header."""

__version__ = "0.3.12"
BUILD_CHANNEL = "development"
MANAGER_VERSION = __version__ + (" (beta)" if BUILD_CHANNEL == "development" else "")
