from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from copy import deepcopy
from enum import Enum
from typing import Any

from .validation import require_aware_datetime, require_positive_int, require_text, utc_now


class PresetStatus(str, Enum):
    EXPERIMENTAL = "experimental"
    ESTABLISHED = "established"
    ARCHIVED = "archived"


@dataclass(slots=True)
class Preset:
    id: str
    name: str
    status: PresetStatus
    source_experiment_id: str | None = None
    source_run_id: str | None = None
    source_quality: float | None = None
    settings_snapshot: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    supersedes_preset_id: str | None = None
    creation_date: datetime = field(default_factory=utc_now)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = require_text(self.id, "Preset id")
        self.name = require_text(self.name, "Preset name")
        self.version = require_positive_int(self.version, "Preset version")
        self.creation_date = require_aware_datetime(self.creation_date, "Preset creation time")
        if self.status is PresetStatus.ESTABLISHED and not (self.source_experiment_id and self.source_run_id):
            raise ValueError("An established preset requires its source experiment and source run.")
        if self.status is PresetStatus.ESTABLISHED and not self.settings_snapshot:
            raise ValueError("An established preset requires a settings snapshot.")
        if self.version > 1 and not self.supersedes_preset_id:
            raise ValueError("A revised preset must identify the preset it supersedes.")

    @classmethod
    def from_experiment_run(
        cls,
        *,
        id: str,
        name: str,
        experiment_id: str,
        run_id: str,
        run_parameters: dict[str, Any],
        source_quality: float | None,
        notes: str = "",
    ) -> "Preset":
        return cls(
            id=id,
            name=name,
            status=PresetStatus.ESTABLISHED,
            source_experiment_id=experiment_id,
            source_run_id=run_id,
            source_quality=source_quality,
            settings_snapshot=deepcopy(run_parameters),
            notes=notes,
        )

    def create_revision(self, *, id: str, name: str, notes: str = "") -> "Preset":
        return Preset(
            id=id,
            name=name,
            status=self.status,
            source_experiment_id=self.source_experiment_id,
            source_run_id=self.source_run_id,
            source_quality=self.source_quality,
            settings_snapshot=deepcopy(self.settings_snapshot),
            version=self.version + 1,
            supersedes_preset_id=self.id,
            notes=notes,
            metadata=deepcopy(self.metadata),
        )
