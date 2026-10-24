from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .validation import require_text


class ProcessType(str, Enum):
    ENGRAVING = "engraving"
    MARKING = "marking"
    CUTTING = "cutting"
    SCORING = "scoring"
    CLEANING = "cleaning"
    ANNEALING = "annealing"


class ProcessMethod(str, Enum):
    ONE_BIT = "one-bit"
    TWO_BIT = "two-bit"
    GRAYSCALE = "grayscale"
    DITHERING = "dithering"
    FLOYD_STEINBERG = "floyd-steinberg"
    JARVIS = "jarvis"
    STUCKI = "stucki"
    ATKINSON = "atkinson"
    VECTORIZE = "vectorize"
    CENTERLINE = "centerline"
    LINE_TO_LINE_RASTER = "line-to-line-raster"


class ParameterValueType(str, Enum):
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    TEXT = "text"
    CHOICE = "choice"


@dataclass(slots=True)
class ProcessParameterDefinition:
    key: str
    label: str
    value_type: ParameterValueType
    unit: str = ""
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None
    choices: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.key = require_text(self.key, "Parameter key")
        self.label = require_text(self.label, "Parameter label")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Parameter minimum cannot be greater than its maximum.")
        if self.value_type is ParameterValueType.CHOICE and not self.choices:
            raise ValueError("A choice parameter requires at least one choice.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value_type": self.value_type.value,
            "unit": self.unit,
            "required": self.required,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "choices": self.choices,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessParameterDefinition":
        return cls(
            key=data["key"],
            label=data["label"],
            value_type=ParameterValueType(data["value_type"]),
            unit=data.get("unit", ""),
            required=data.get("required", False),
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
            choices=data.get("choices", []),
        )


@dataclass(slots=True)
class ProcessDefinition:
    id: str
    name: str
    process_type: ProcessType
    supported_methods: list[ProcessMethod] = field(default_factory=list)
    default_parameters: dict[str, Any] = field(default_factory=dict)
    parameter_schema: list[ProcessParameterDefinition] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = require_text(self.id, "Process id")
        self.name = require_text(self.name, "Process name")
        keys = [parameter.key for parameter in self.parameter_schema]
        if len(keys) != len(set(keys)):
            raise ValueError("A process parameter schema cannot contain duplicate keys.")
        if self.parameter_schema:
            self.validate_parameters(self.default_parameters, require_required=False)

    def supports_method(self, method: ProcessMethod | str) -> bool:
        if isinstance(method, str):
            candidate = ProcessMethod(method)
        else:
            candidate = method
        return candidate in self.supported_methods

    def validate_parameters(self, parameters: dict[str, Any], *, require_required: bool = True) -> None:
        if not self.parameter_schema:
            return

        definitions = {parameter.key: parameter for parameter in self.parameter_schema}
        unknown = set(parameters) - set(definitions)
        if unknown:
            raise ValueError(f"Unsupported process parameters: {', '.join(sorted(unknown))}.")

        if require_required:
            missing = [parameter.key for parameter in self.parameter_schema if parameter.required and parameter.key not in parameters]
            if missing:
                raise ValueError(f"Missing required process parameters: {', '.join(sorted(missing))}.")

        for key, value in parameters.items():
            self._validate_parameter_value(definitions[key], value)

    @staticmethod
    def _validate_parameter_value(definition: ProcessParameterDefinition, value: Any) -> None:
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if definition.value_type is ParameterValueType.NUMBER and not numeric:
            raise ValueError(f"{definition.label} must be numeric.")
        if definition.value_type is ParameterValueType.INTEGER and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"{definition.label} must be an integer.")
        if definition.value_type is ParameterValueType.BOOLEAN and not isinstance(value, bool):
            raise ValueError(f"{definition.label} must be true or false.")
        if definition.value_type in {ParameterValueType.TEXT, ParameterValueType.CHOICE} and not isinstance(value, str):
            raise ValueError(f"{definition.label} must be text.")
        if definition.value_type is ParameterValueType.CHOICE and value not in definition.choices:
            raise ValueError(f"{definition.label} must be one of: {', '.join(definition.choices)}.")
        if numeric and definition.minimum is not None and value < definition.minimum:
            raise ValueError(f"{definition.label} must be at least {definition.minimum}.")
        if numeric and definition.maximum is not None and value > definition.maximum:
            raise ValueError(f"{definition.label} must be no more than {definition.maximum}.")


def standard_engraving_parameters() -> list[ProcessParameterDefinition]:
    """The standard image and laser controls captured for every engraving trial."""
    return [
        ProcessParameterDefinition("conversion_tool", "Conversion tool", ParameterValueType.CHOICE, required=True,
            choices=["PassThrough", "Centerline", "Vectorize", "1bit BW Dithering", "Line to Line", "Conversion Tool"]),
        ProcessParameterDefinition("resize_percent", "Resize", ParameterValueType.NUMBER, "%", True, 1, 1000),
        ProcessParameterDefinition("brightness", "Brightness", ParameterValueType.NUMBER, "", True, -255, 255),
        ProcessParameterDefinition("contrast", "Contrast", ParameterValueType.NUMBER, "", True, -255, 255),
        ProcessParameterDefinition("white_threshold", "White threshold", ParameterValueType.INTEGER, "", True, 0, 255),
        ProcessParameterDefinition("speed_mm_s", "Engraving speed", ParameterValueType.NUMBER, "mm/s", True, 1),
        ProcessParameterDefinition("power_percent", "Power", ParameterValueType.NUMBER, "%", True, 0, 100),
        ProcessParameterDefinition("line_interval_mm", "Line interval", ParameterValueType.NUMBER, "mm", True, 0.01, 10),
        ProcessParameterDefinition("passes", "Passes", ParameterValueType.INTEGER, "", True, 1, 100),
        ProcessParameterDefinition("direction", "Direction", ParameterValueType.CHOICE, required=True, choices=["HORIZ", "Vert"]),
        ProcessParameterDefinition("quality_lines", "Quality", ParameterValueType.INTEGER, "lines", True, 1, 1000),
        ProcessParameterDefinition("quality_mm", "Quality size", ParameterValueType.NUMBER, "mm", True, 0.01, 1000),
        ProcessParameterDefinition("adjustment_target", "Adjusting", ParameterValueType.CHOICE, required=True, choices=["Direction", "Quality", "Accuracy"]),
        ProcessParameterDefinition("adjustment_percent", "Adjustment", ParameterValueType.NUMBER, "%", True, 0, 100),
        ProcessParameterDefinition("dither_algorithm", "Dithering method", ParameterValueType.CHOICE, required=True,
            choices=["Floyd", "Burkes", "Jarvis", "Stucki", "Sierra", "Random"]),
        ProcessParameterDefinition("spot_removal", "Spot removal", ParameterValueType.BOOLEAN, required=True),
        ProcessParameterDefinition("smoothing", "Smoothing", ParameterValueType.BOOLEAN, required=True),
        ProcessParameterDefinition("optimize", "Optimize", ParameterValueType.BOOLEAN, required=True),
        ProcessParameterDefinition("dithering_enabled", "Dithering", ParameterValueType.BOOLEAN, required=True),
        ProcessParameterDefinition("filling", "Filling", ParameterValueType.BOOLEAN, required=True),
        ProcessParameterDefinition("filling_quality", "Filling quality", ParameterValueType.NUMBER, "%", True, 0, 100),
        ProcessParameterDefinition("corner_threshold", "Corner threshold", ParameterValueType.NUMBER, "", True, 0, 255),
        ProcessParameterDefinition("line_threshold", "Line threshold", ParameterValueType.NUMBER, "", True, 0, 255),
    ]


def standard_engraving_defaults() -> dict[str, Any]:
    return {
        "conversion_tool": "Line to Line", "resize_percent": 100, "brightness": 0, "contrast": 0,
        "white_threshold": 255, "speed_mm_s": 200, "power_percent": 50, "line_interval_mm": 0.1,
        "passes": 1, "direction": "HORIZ", "quality_lines": 1, "quality_mm": 25,
        "adjustment_target": "Accuracy", "adjustment_percent": 0, "dither_algorithm": "Floyd",
        "spot_removal": False, "smoothing": False, "optimize": False, "dithering_enabled": True,
        "filling": False, "filling_quality": 50, "corner_threshold": 0, "line_threshold": 0,
    }
