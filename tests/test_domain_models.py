from __future__ import annotations

from datetime import UTC, datetime

import pytest

from laser_knowledge_system.domain.materials import MaterialRecord, MaterialFamily
from laser_knowledge_system.domain.processes import (
    ParameterValueType,
    ProcessDefinition,
    ProcessMethod,
    ProcessParameterDefinition,
    ProcessType,
)
from laser_knowledge_system.domain.presets import Preset, PresetStatus
from laser_knowledge_system.domain.workflow import ExperimentWorkflow
from laser_knowledge_system.domain.experiments import Experiment, ExperimentRun, ResultRecord
from laser_knowledge_system.domain.notebook import ExperimentNotebook
from laser_knowledge_system.domain.experiments import ExperimentStatus


def test_material_record_supports_family_specific_schema() -> None:
    material = MaterialRecord(
        id="mat-1",
        family=MaterialFamily.METAL,
        name="316L Stainless",
        properties={"grade": "316L", "thickness_mm": 2.0, "surface_finish": "brushed"},
    )

    assert material.family is MaterialFamily.METAL
    assert material.properties["grade"] == "316L"


def test_process_definition_accepts_method_metadata() -> None:
    process = ProcessDefinition(
        id="proc-1",
        name="Laser Engraving",
        process_type=ProcessType.ENGRAVING,
        supported_methods=[ProcessMethod.DITHERING, ProcessMethod.FLOYD_STEINBERG],
        default_parameters={"power_w": 35, "speed_mm_s": 180, "passes": 1},
    )

    assert process.process_type is ProcessType.ENGRAVING
    assert ProcessMethod.DITHERING in process.supported_methods


def test_preset_status_and_experiment_status_are_valid_enums() -> None:
    assert PresetStatus.EXPERIMENTAL.value == "experimental"
    assert ExperimentStatus.ACTIVE.value == "active"


def test_result_quality_must_be_a_score_out_of_ten() -> None:
    from laser_knowledge_system.domain.experiments import ResultRecord

    with pytest.raises(ValueError, match="between 0 and 10"):
        ResultRecord(quality=10.1)


def test_experiment_timestamps_must_be_timezone_aware() -> None:
    from laser_knowledge_system.domain.experiments import Experiment

    with pytest.raises(ValueError, match="must include a timezone"):
        Experiment(
            id="experiment-1",
            material_id="material-1",
            machine_id="machine-1",
            process_id="process-1",
            objective="Contrast test",
            start_time=datetime(2026, 9, 18, 10, 0),
        )

    experiment = Experiment(
        id="experiment-1",
        material_id="material-1",
        machine_id="machine-1",
        process_id="process-1",
        objective="Contrast test",
        start_time=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
    )
    assert experiment.start_time.tzinfo is UTC


def test_process_definition_validates_parameter_schema() -> None:
    process = ProcessDefinition(
        id="marking",
        name="Laser marking",
        process_type=ProcessType.MARKING,
        parameter_schema=[
            ProcessParameterDefinition(
                key="power_percent",
                label="Power",
                value_type=ParameterValueType.NUMBER,
                unit="%",
                minimum=0,
                maximum=100,
                required=True,
            ),
            ProcessParameterDefinition(
                key="passes",
                label="Passes",
                value_type=ParameterValueType.INTEGER,
                minimum=1,
                required=True,
            ),
        ],
    )

    process.validate_parameters({"power_percent": 25, "passes": 1})
    with pytest.raises(ValueError, match="no more than 100"):
        process.validate_parameters({"power_percent": 110, "passes": 1})
    with pytest.raises(ValueError, match="Missing required"):
        process.validate_parameters({"power_percent": 25})


def test_established_preset_retains_a_snapshot_and_revision_history() -> None:
    original_parameters = {"power_percent": 25, "passes": 1}
    preset = Preset.from_experiment_run(
        id="preset-1",
        name="Stainless steel dark mark",
        experiment_id="experiment-1",
        run_id="run-3",
        run_parameters=original_parameters,
        source_quality=8.5,
    )
    original_parameters["power_percent"] = 10

    revision = preset.create_revision(id="preset-2", name="Stainless steel dark mark v2")

    assert preset.settings_snapshot["power_percent"] == 25
    assert revision.version == 2
    assert revision.supersedes_preset_id == preset.id


def test_user_explicitly_selects_the_preferred_validated_run() -> None:
    process = ProcessDefinition(
        id="marking",
        name="Laser marking",
        process_type=ProcessType.MARKING,
        parameter_schema=[
            ProcessParameterDefinition(
                key="power_percent",
                label="Power",
                value_type=ParameterValueType.NUMBER,
                minimum=0,
                maximum=100,
                required=True,
            )
        ],
    )
    experiment = Experiment(
        id="experiment-1",
        material_id="material-1",
        machine_id="machine-1",
        process_id=process.id,
        objective="Find a dark mark",
    )

    run = ExperimentWorkflow.record_run(
        experiment=experiment,
        process=process,
        run_id="run-1",
        run_number=1,
        parameters={"power_percent": 25},
        results=ResultRecord(quality=8.5),
    )

    assert experiment.selected_best_run_id is None
    selected = ExperimentWorkflow.select_preferred_run(experiment, run.id)
    assert selected.id == run.id
    assert experiment.selected_best_run_id == run.id


def test_notebook_entry_is_linked_to_its_experiment_run_and_normalizes_tags() -> None:
    experiment = Experiment(
        id="experiment-1",
        material_id="material-1",
        machine_id="machine-1",
        process_id="process-1",
        objective="Record observations",
    )
    experiment.runs.append(
        ExperimentRun(id="run-1", experiment_id=experiment.id, run_number=1)
    )

    entry = ExperimentNotebook.record_entry(
        experiment=experiment,
        run_id="run-1",
        text="No visible heat damage.",
        tags=[" Surface ", "surface", "contrast"],
    )

    assert entry.experiment_id == experiment.id
    assert entry.run_id == "run-1"
    assert entry.tags == ["surface", "contrast"]
    with pytest.raises(ValueError, match="does not belong"):
        ExperimentNotebook.record_entry(experiment=experiment, run_id="run-2", text="Invalid link")
