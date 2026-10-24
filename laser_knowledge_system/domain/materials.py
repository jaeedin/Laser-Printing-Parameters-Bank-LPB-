from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .validation import require_text


class MaterialFamily(str, Enum):
    METAL = "metal"
    WOOD = "wood"
    PLASTIC = "plastic"
    COMPOSITE = "composite"
    OTHER = "other"


MATERIAL_FAMILY_SCHEMAS: dict[MaterialFamily, dict[str, str]] = {
    MaterialFamily.METAL: {
        "material_type": "text",
        "grade": "text",
        "thickness_mm": "float",
        "surface_finish": "text",
        "hardness": "float",
    },
    MaterialFamily.WOOD: {
        "species": "text",
        "thickness_mm": "float",
        "moisture_percent": "float",
        "grain_direction": "text",
        "finish": "text",
    },
    MaterialFamily.PLASTIC: {
        "material_type": "text",
        "thickness_mm": "float",
        "softening_temp_c": "float",
        "surface_finish": "text",
    },
    MaterialFamily.COMPOSITE: {
        "composition": "text",
        "thickness_mm": "float",
        "fiber_orientation": "text",
        "surface_finish": "text",
    },
    MaterialFamily.OTHER: {
        "material_type": "text",
        "notes": "text",
    },
}


@dataclass(slots=True)
class MaterialRecord:
    id: str
    family: MaterialFamily
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        self.id = require_text(self.id, "Material id")
        self.name = require_text(self.name, "Material name")
        self.validate_properties()

    def validate_properties(self) -> None:
        schema = get_material_family_schema(self.family)
        unsupported = set(self.properties) - set(schema)
        if unsupported:
            raise ValueError(
                f"Material family '{self.family.value}' does not support properties: "
                f"{', '.join(sorted(unsupported))}"
            )
        for name, value in self.properties.items():
            expected_type = schema[name]
            if expected_type == "text" and not isinstance(value, str):
                raise ValueError(f"Material property '{name}' must be text.")
            if expected_type == "float" and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ValueError(f"Material property '{name}' must be numeric.")


def get_material_family_schema(family: MaterialFamily) -> dict[str, str]:
    return MATERIAL_FAMILY_SCHEMAS.get(family, MATERIAL_FAMILY_SCHEMAS[MaterialFamily.OTHER]).copy()
