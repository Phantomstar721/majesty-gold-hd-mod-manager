"""Tools for reading and writing Majesty Gold HD CAM archives."""

from .cam import CamArchive, CamEntry, CamSection, read_cam, write_cam

__all__ = [
    "CamArchive",
    "CamEntry",
    "CamSection",
    "read_cam",
    "write_cam",
]
