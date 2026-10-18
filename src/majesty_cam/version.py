"""Application version, shared by packaging and the visible Manager header."""

__version__ = "0.3.10"
BUILD_CHANNEL = "release"
MANAGER_VERSION = __version__ + (" (development)" if BUILD_CHANNEL == "development" else "")
