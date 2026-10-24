from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .validation import require_non_negative_float, require_text


@dataclass(slots=True)
class MachineProfile:
    id: str
    name: str
    laser_type: str
    rated_power_w: float
    controller: str
    lens_focus: str
    air_assist: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        self.id = require_text(self.id, "Machine id")
        self.name = require_text(self.name, "Machine name")
        self.laser_type = require_text(self.laser_type, "Laser type")
        self.controller = require_text(self.controller, "Controller")
        self.lens_focus = require_text(self.lens_focus, "Lens focus")
        self.rated_power_w = require_non_negative_float(self.rated_power_w, "Rated power")
