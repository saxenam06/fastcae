"""Geometry: B-rep in, face-tagged triangle surface out, with a health gate over it."""

from .brep import (
    DISPLAY_ANGLE_DEG,
    ExactProperties,
    Tessellation,
    declared_unit,
    exact_properties,
    faces_of,
    load_cad,
    load_step,
    tessellate,
)
from .health import HealthReport, check

__all__ = [
    "DISPLAY_ANGLE_DEG",
    "ExactProperties",
    "HealthReport",
    "Tessellation",
    "check",
    "declared_unit",
    "exact_properties",
    "faces_of",
    "load_cad",
    "load_step",
    "tessellate",
]
