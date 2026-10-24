from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .validation import (
    require_aware_datetime,
    require_non_negative_float,
    require_positive_int,
    require_score,
    require_text,
    utc_now,
)


class ExperimentStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETE = "complete"
    ARCHIVED = "archived"


@dataclass(slots=True)
class ResultRecord:
    quality: float | None = None
    contrast: float | None = None
    detail: float | None = None
    burn: float | None = None
    duration_seconds: float | None = None
    measurements: dict[str, Any] = field(default_factory=dict)
    observations: str = ""
    photo_evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.quality = require_score(self.quality, "Quality")
        self.contrast = require_score(self.contrast, "Contrast")
        self.detail = require_score(self.detail, "Detail")
        self.burn = require_score(self.burn, "Burn")
        if self.duration_seconds is not None:
            self.duration_seconds = require_non_negative_float(self.duration_seconds, "Duration")


@dataclass(slots=True)
class ExperimentRun:
    id: str
    experiment_id: str
    run_number: int
    parameters: dict[str, Any] = field(default_factory=dict)
    results: ResultRecord | None = None
    created_at: datetime = field(default_factory=utc_now)
    notes: str = ""

    def __post_init__(self) -> None:
        self.id = require_text(self.id, "Run id")
        self.experiment_id = require_text(self.experiment_id, "Experiment id")
        self.run_number = require_positive_int(self.run_number, "Run number")
        self.created_at = require_aware_datetime(self.created_at, "Run creation time")


@dataclass(slots=True)
class Experiment:
    id: str
    material_id: str
    machine_id: str
    process_id: str
    objective: str
    status: ExperimentStatus = ExperimentStatus.PLANNED
    conclusion: str = ""
    selected_best_run_id: str | None = None
    start_time: datetime = field(default_factory=utc_now)
    end_time: datetime | None = None
    runs: list[ExperimentRun] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = require_text(self.id, "Experiment id")
        self.material_id = require_text(self.material_id, "Material id")
        self.machine_id = require_text(self.machine_id, "Machine id")
        self.process_id = require_text(self.process_id, "Process id")
        self.objective = require_text(self.objective, "Experiment objective")
        self.start_time = require_aware_datetime(self.start_time, "Experiment start time")
        if self.end_time is not None:
            self.end_time = require_aware_datetime(self.end_time, "Experiment end time")
            if self.end_time < self.start_time:
                raise ValueError("Experiment end time cannot be before its start time.")
