from __future__ import annotations

from copy import deepcopy

from .experiments import Experiment, ExperimentRun, ResultRecord
from .processes import ProcessDefinition
from .validation import require_text


class ExperimentWorkflow:
    """Applies the rules for recording and selecting experimental runs."""

    @staticmethod
    def record_run(
        *,
        experiment: Experiment,
        process: ProcessDefinition,
        run_id: str,
        run_number: int,
        parameters: dict[str, object],
        results: ResultRecord | None = None,
        notes: str = "",
    ) -> ExperimentRun:
        if experiment.process_id != process.id:
            raise ValueError("The selected process does not belong to this experiment.")
        if any(run.id == run_id for run in experiment.runs):
            raise ValueError(f"Run id '{run_id}' already exists in this experiment.")
        if any(run.run_number == run_number for run in experiment.runs):
            raise ValueError(f"Run number {run_number} already exists in this experiment.")

        process.validate_parameters(parameters)
        run = ExperimentRun(
            id=require_text(run_id, "Run id"),
            experiment_id=experiment.id,
            run_number=run_number,
            parameters=deepcopy(parameters),
            results=results,
            notes=notes,
        )
        experiment.runs.append(run)
        return run

    @staticmethod
    def select_preferred_run(experiment: Experiment, run_id: str) -> ExperimentRun:
        for run in experiment.runs:
            if run.id == run_id:
                if run.results is None:
                    raise ValueError("A run needs recorded results before it can be selected.")
                experiment.selected_best_run_id = run.id
                return run
        raise ValueError(f"Run '{run_id}' does not belong to this experiment.")
