from __future__ import annotations

from datetime import UTC, datetime

from laser_knowledge_system.db.database import DatabaseManager
from laser_knowledge_system.db.repositories import SQLiteRepository
from laser_knowledge_system.domain.experiments import Experiment, ExperimentRun, ExperimentStatus, ResultRecord
from laser_knowledge_system.domain.machines import MachineProfile
from laser_knowledge_system.domain.materials import MaterialFamily, MaterialRecord
from laser_knowledge_system.domain.notebook import NotebookEntry
from laser_knowledge_system.domain.presets import Preset, PresetStatus
from laser_knowledge_system.domain.processes import ProcessDefinition, ProcessMethod, ProcessType


def test_repository_tracks_experiment_lifecycle(tmp_path) -> None:
    db_path = tmp_path / "workflow.sqlite"
    manager = DatabaseManager(database_url=f"sqlite:///{db_path}")
    manager.initialize()
    repo = SQLiteRepository(manager)

    material = MaterialRecord(
        id="mat-100",
        family=MaterialFamily.METAL,
        name="316L Stainless",
        properties={"grade": "316L", "thickness_mm": 2.0, "surface_finish": "brushed"},
    )
    machine = MachineProfile(
        id="machine-100",
        name="Fiber 40W",
        laser_type="fiber",
        rated_power_w=40.0,
        controller="Ruida",
        lens_focus="2 inch lens",
        air_assist=True,
        parameters={"frequency_khz": 20},
    )
    process = ProcessDefinition(
        id="process-100",
        name="Engraving",
        process_type=ProcessType.ENGRAVING,
        supported_methods=[ProcessMethod.DITHERING],
        default_parameters={"power_w": 25, "speed_mm_s": 200},
    )

    repo.add_material(material)
    repo.add_machine(machine)
    repo.add_process(process)

    experiment = Experiment(
        id="exp-100",
        material_id=material.id,
        machine_id=machine.id,
        process_id=process.id,
        objective="Evaluate contrast on stainless",
        status=ExperimentStatus.ACTIVE,
    )
    repo.add_experiment(experiment)

    run = ExperimentRun(
        id="run-100",
        experiment_id=experiment.id,
        run_number=1,
        parameters={"power_w": 25, "speed_mm_s": 200},
        results=ResultRecord(quality=8.5, contrast=7.0, observations="Good definition"),
        created_at=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
    )
    repo.add_run(run)

    note = NotebookEntry(
        id="note-100",
        experiment_id=experiment.id,
        timestamp=datetime(2026, 9, 18, 10, 5, tzinfo=UTC),
        text="Surface stayed stable during first pass.",
        run_id=run.id,
        tags=["surface", "contrast"],
    )
    repo.add_notebook_entry(note)

    preset = Preset.from_experiment_run(
        id="preset-100",
        name="316L Engrave Standard",
        experiment_id=experiment.id,
        run_id=run.id,
        run_parameters=run.parameters,
        source_quality=run.results.quality,
        notes="Selected best run from first trial",
    )
    repo.create_preset(preset)

    loaded = repo.get_experiment(experiment.id)
    assert loaded is not None
    assert loaded.runs[0].id == run.id
    assert repo.list_notebook_entries(experiment.id)[0].text.startswith("Surface stayed stable")
    assert repo.list_notebook_entries(experiment.id)[0].tags == ["surface", "contrast"]
    loaded_preset = repo.get_preset(preset.id)
    assert loaded_preset is not None
    assert loaded_preset.settings_snapshot == {"power_w": 25, "speed_mm_s": 200}

    loaded.selected_best_run_id = run.id
    repo.update_experiment_selection(loaded)
    assert repo.get_experiment(experiment.id).selected_best_run_id == run.id
