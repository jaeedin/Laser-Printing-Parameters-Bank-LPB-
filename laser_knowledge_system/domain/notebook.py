from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from .experiments import Experiment
from .validation import require_aware_datetime, require_text, utc_now


@dataclass(slots=True)
class NotebookEntry:
    id: str
    experiment_id: str
    text: str
    timestamp: datetime = field(default_factory=utc_now)
    run_id: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = require_text(self.id, "Notebook entry id")
        self.experiment_id = require_text(self.experiment_id, "Experiment id")
        self.text = require_text(self.text, "Notebook text")
        self.timestamp = require_aware_datetime(self.timestamp, "Notebook timestamp")
        self.tags = self._normalize_tags(self.tags)

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        normalized = [require_text(tag, "Notebook tag").lower() for tag in tags]
        return list(dict.fromkeys(normalized))


class ExperimentNotebook:
    """Creates traceable notes for an experiment and its individual runs."""

    @staticmethod
    def record_entry(
        *,
        experiment: Experiment,
        text: str,
        run_id: str | None = None,
        tags: list[str] | None = None,
        timestamp: datetime | None = None,
    ) -> NotebookEntry:
        if run_id is not None and not any(run.id == run_id for run in experiment.runs):
            raise ValueError(f"Run '{run_id}' does not belong to this experiment.")
        return NotebookEntry(
            id=f"note-{uuid4()}",
            experiment_id=experiment.id,
            text=text,
            timestamp=timestamp or utc_now(),
            run_id=run_id,
            tags=tags or [],
        )
