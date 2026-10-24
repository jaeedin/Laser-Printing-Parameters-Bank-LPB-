from __future__ import annotations

from typing import Any
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from laser_knowledge_system.domain.experiments import Experiment, ExperimentRun, ExperimentStatus, ResultRecord
from laser_knowledge_system.domain.machines import MachineProfile
from laser_knowledge_system.domain.materials import MaterialFamily, MaterialRecord
from laser_knowledge_system.domain.notebook import NotebookEntry
from laser_knowledge_system.domain.presets import Preset, PresetStatus
from laser_knowledge_system.domain.processes import ProcessDefinition, ProcessMethod, ProcessParameterDefinition, ProcessType
from .database import DatabaseManager
from .models import (
    ExperimentORM,
    ExperimentRunORM,
    MachineORM,
    MaterialORM,
    NotebookEntryORM,
    PresetORM,
    ProcessORM,
)


class RepositoryError(RuntimeError):
    pass


class SQLiteRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def _insert(self, row: Any, entity_name: str) -> None:
        """Insert a record atomically and turn database errors into useful messages."""
        try:
            with self.database.SessionLocal.begin() as session:
                if session.get(type(row), row.id) is not None:
                    raise RepositoryError(f"{entity_name} '{row.id}' already exists.")
                session.add(row)
        except IntegrityError as error:
            raise RepositoryError(f"Could not save {entity_name.lower()} '{row.id}'.") from error

    def list_materials(self) -> list[MaterialRecord]:
        with self.database.SessionLocal() as session:
            rows = session.execute(select(MaterialORM)).scalars().all()
        return [
            MaterialRecord(
                id=row.id,
                family=MaterialFamily(row.family),
                name=row.name,
                properties=row.properties,
                notes=row.notes,
            )
            for row in rows
        ]

    def add_material(self, material: MaterialRecord) -> MaterialRecord:
        self._insert(
            MaterialORM(
                id=material.id,
                family=material.family.value,
                name=material.name,
                properties=material.properties,
                notes=material.notes,
            ),
            "Material",
        )
        return material

    def get_material(self, material_id: str) -> MaterialRecord | None:
        with self.database.SessionLocal() as session:
            row = session.get(MaterialORM, material_id)
        if row is None:
            return None
        return MaterialRecord(
            id=row.id,
            family=MaterialFamily(row.family),
            name=row.name,
            properties=row.properties,
            notes=row.notes,
        )

    def add_machine(self, machine: MachineProfile) -> MachineProfile:
        self._insert(
            MachineORM(
                id=machine.id,
                name=machine.name,
                laser_type=machine.laser_type,
                rated_power_w=machine.rated_power_w,
                controller=machine.controller,
                lens_focus=machine.lens_focus,
                air_assist=machine.air_assist,
                parameters=machine.parameters,
                notes=machine.notes,
            ),
            "Machine",
        )
        return machine

    def list_machines(self) -> list[MachineProfile]:
        with self.database.SessionLocal() as session:
            rows = session.execute(select(MachineORM)).scalars().all()
        return [
            MachineProfile(row.id, row.name, row.laser_type, row.rated_power_w, row.controller, row.lens_focus,
                           row.air_assist, row.parameters, row.notes)
            for row in rows
        ]

    def get_machine(self, machine_id: str) -> MachineProfile | None:
        with self.database.SessionLocal() as session:
            row = session.get(MachineORM, machine_id)
        if row is None:
            return None
        return MachineProfile(
            id=row.id,
            name=row.name,
            laser_type=row.laser_type,
            rated_power_w=row.rated_power_w,
            controller=row.controller,
            lens_focus=row.lens_focus,
            air_assist=row.air_assist,
            parameters=row.parameters,
            notes=row.notes,
        )

    def add_process(self, process: ProcessDefinition) -> ProcessDefinition:
        self._insert(
            ProcessORM(
                id=process.id,
                name=process.name,
                process_type=process.process_type.value,
                supported_methods=",".join(method.value for method in process.supported_methods),
                default_parameters=process.default_parameters,
                parameter_schema=[parameter.to_dict() for parameter in process.parameter_schema],
            ),
            "Process",
        )
        return process

    def list_processes(self) -> list[ProcessDefinition]:
        with self.database.SessionLocal() as session:
            rows = session.execute(select(ProcessORM)).scalars().all()
        return [
            ProcessDefinition(
                id=row.id, name=row.name, process_type=ProcessType(row.process_type),
                supported_methods=[ProcessMethod(item) for item in row.supported_methods.split(",") if item],
                default_parameters=row.default_parameters,
                parameter_schema=[ProcessParameterDefinition.from_dict(item) for item in row.parameter_schema],
            )
            for row in rows
        ]

    def get_process(self, process_id: str) -> ProcessDefinition | None:
        with self.database.SessionLocal() as session:
            row = session.get(ProcessORM, process_id)
        if row is None:
            return None
        methods = [
            ProcessMethod(method_name.strip()) for method_name in row.supported_methods.split(",") if method_name.strip()
        ]
        return ProcessDefinition(
            id=row.id,
            name=row.name,
            process_type=ProcessType(row.process_type),
            supported_methods=methods,
            default_parameters=row.default_parameters,
            parameter_schema=[ProcessParameterDefinition.from_dict(item) for item in row.parameter_schema],
        )

    def update_process(self, process: ProcessDefinition) -> ProcessDefinition:
        with self.database.SessionLocal.begin() as session:
            row = session.get(ProcessORM, process.id)
            if row is None:
                raise RepositoryError(f"Process '{process.id}' does not exist.")
            row.default_parameters = process.default_parameters
            row.parameter_schema = [parameter.to_dict() for parameter in process.parameter_schema]
        return process

    def add_experiment(self, experiment: Experiment) -> Experiment:
        self._insert(
            ExperimentORM(
                id=experiment.id,
                material_id=experiment.material_id,
                machine_id=experiment.machine_id,
                process_id=experiment.process_id,
                objective=experiment.objective,
                status=experiment.status.value,
                conclusion=experiment.conclusion,
                selected_best_run_id=experiment.selected_best_run_id,
                start_time=experiment.start_time.isoformat(),
                end_time=experiment.end_time.isoformat() if experiment.end_time else None,
            ),
            "Experiment",
        )
        return experiment

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        with self.database.SessionLocal() as session:
            experiment_row = session.get(ExperimentORM, experiment_id)
            if experiment_row is None:
                return None
            run_rows = session.execute(
                select(ExperimentRunORM).where(ExperimentRunORM.experiment_id == experiment_id)
            ).scalars().all()

        runs = [self._row_to_run(row) for row in sorted(run_rows, key=lambda row: row.run_number)]
        return Experiment(
            id=experiment_row.id,
            material_id=experiment_row.material_id,
            machine_id=experiment_row.machine_id,
            process_id=experiment_row.process_id,
            objective=experiment_row.objective,
            status=ExperimentStatus(experiment_row.status),
            conclusion=experiment_row.conclusion,
            selected_best_run_id=experiment_row.selected_best_run_id,
            start_time=datetime.fromisoformat(experiment_row.start_time),
            end_time=datetime.fromisoformat(experiment_row.end_time) if experiment_row.end_time else None,
            runs=runs,
        )

    def list_experiments(self) -> list[Experiment]:
        """Return experiments newest first, including their trial runs."""
        with self.database.SessionLocal() as session:
            ids = session.execute(
                select(ExperimentORM.id).order_by(ExperimentORM.start_time.desc())
            ).scalars().all()
        return [experiment for experiment_id in ids if (experiment := self.get_experiment(experiment_id))]

    def update_experiment_selection(self, experiment: Experiment) -> Experiment:
        with self.database.SessionLocal.begin() as session:
            row = session.get(ExperimentORM, experiment.id)
            if row is None:
                raise RepositoryError(f"Experiment '{experiment.id}' does not exist.")
            if experiment.selected_best_run_id is not None:
                run = session.get(ExperimentRunORM, experiment.selected_best_run_id)
                if run is None or run.experiment_id != experiment.id:
                    raise RepositoryError("The selected run does not belong to this experiment.")
            row.selected_best_run_id = experiment.selected_best_run_id
        return experiment

    def add_run(self, run: ExperimentRun) -> ExperimentRun:
        try:
            with self.database.SessionLocal.begin() as session:
                if session.get(ExperimentORM, run.experiment_id) is None:
                    raise RepositoryError(f"Experiment '{run.experiment_id}' does not exist.")
                if session.get(ExperimentRunORM, run.id) is not None:
                    raise RepositoryError(f"Run '{run.id}' already exists.")
                duplicate_number = session.scalar(
                    select(ExperimentRunORM.id).where(
                        ExperimentRunORM.experiment_id == run.experiment_id,
                        ExperimentRunORM.run_number == run.run_number,
                    )
                )
                if duplicate_number is not None:
                    raise RepositoryError(
                        f"Run number {run.run_number} already exists in experiment '{run.experiment_id}'."
                    )
                session.add(
                    ExperimentRunORM(
                        id=run.id,
                        experiment_id=run.experiment_id,
                        run_number=run.run_number,
                        parameters=run.parameters,
                        results=self._result_to_dict(run.results),
                        created_at=run.created_at.isoformat(),
                        notes=run.notes,
                    )
                )
        except IntegrityError as error:
            raise RepositoryError(f"Could not save run '{run.id}'.") from error
        return run

    def list_runs(self, experiment_id: str) -> list[ExperimentRun]:
        with self.database.SessionLocal() as session:
            rows = session.execute(
                select(ExperimentRunORM).where(ExperimentRunORM.experiment_id == experiment_id)
            ).scalars().all()
        return [self._row_to_run(row) for row in sorted(rows, key=lambda row: row.run_number)]

    def delete_run(self, run_id: str) -> None:
        """Remove one trial so a corrected variable set can replace it."""
        with self.database.SessionLocal.begin() as session:
            row = session.get(ExperimentRunORM, run_id)
            if row is None:
                raise RepositoryError(f"Run '{run_id}' does not exist.")
            experiment = session.get(ExperimentORM, row.experiment_id)
            if experiment and experiment.selected_best_run_id == run_id:
                experiment.selected_best_run_id = None
            session.delete(row)

    def update_run(self, run: ExperimentRun) -> ExperimentRun:
        with self.database.SessionLocal.begin() as session:
            row = session.get(ExperimentRunORM, run.id)
            if row is None:
                raise RepositoryError(f"Run '{run.id}' does not exist.")
            row.parameters = run.parameters
            row.results = self._result_to_dict(run.results)
            row.notes = run.notes
        return run

    def delete_experiment(self, experiment_id: str) -> None:
        """Remove an experiment and its dependent local records."""
        with self.database.SessionLocal.begin() as session:
            if session.get(ExperimentORM, experiment_id) is None:
                raise RepositoryError(f"Experiment '{experiment_id}' does not exist.")
            session.execute(delete(NotebookEntryORM).where(NotebookEntryORM.experiment_id == experiment_id))
            session.execute(delete(PresetORM).where(PresetORM.source_experiment_id == experiment_id))
            session.execute(delete(ExperimentRunORM).where(ExperimentRunORM.experiment_id == experiment_id))
            session.execute(delete(ExperimentORM).where(ExperimentORM.id == experiment_id))

    def add_notebook_entry(self, entry: NotebookEntry) -> NotebookEntry:
        self._insert(
            NotebookEntryORM(
                id=entry.id,
                experiment_id=entry.experiment_id,
                timestamp=entry.timestamp.isoformat(),
                text=entry.text,
                run_id=entry.run_id,
                tags=",".join(entry.tags),
            ),
            "Notebook entry",
        )
        return entry

    def list_notebook_entries(self, experiment_id: str) -> list[NotebookEntry]:
        with self.database.SessionLocal() as session:
            rows = session.execute(
                select(NotebookEntryORM)
                .where(NotebookEntryORM.experiment_id == experiment_id)
                .order_by(NotebookEntryORM.timestamp)
            ).scalars().all()
        return [
            NotebookEntry(
                id=row.id,
                experiment_id=row.experiment_id,
                timestamp=datetime.fromisoformat(row.timestamp),
                text=row.text,
                run_id=row.run_id,
                tags=[tag.strip() for tag in row.tags.split(",") if tag.strip()],
            )
            for row in rows
        ]

    def create_preset(self, preset: Preset) -> Preset:
        self._insert(
            PresetORM(
                id=preset.id,
                name=preset.name,
                status=preset.status.value,
                source_experiment_id=preset.source_experiment_id,
                source_run_id=preset.source_run_id,
                source_quality=preset.source_quality,
                settings_snapshot=preset.settings_snapshot,
                version=preset.version,
                supersedes_preset_id=preset.supersedes_preset_id,
                creation_date=preset.creation_date.isoformat(),
                notes=preset.notes,
                preset_metadata=preset.metadata,
            ),
            "Preset",
        )
        return preset

    def list_presets(self) -> list[Preset]:
        with self.database.SessionLocal() as session:
            ids = session.execute(select(PresetORM.id).order_by(PresetORM.creation_date.desc())).scalars().all()
        return [preset for preset_id in ids if (preset := self.get_preset(preset_id))]

    def get_preset(self, preset_id: str) -> Preset | None:
        with self.database.SessionLocal() as session:
            row = session.get(PresetORM, preset_id)
        if row is None:
            return None
        return Preset(
            id=row.id,
            name=row.name,
            status=PresetStatus(row.status),
            source_experiment_id=row.source_experiment_id,
            source_run_id=row.source_run_id,
            source_quality=row.source_quality,
            settings_snapshot=row.settings_snapshot,
            version=row.version,
            supersedes_preset_id=row.supersedes_preset_id,
            creation_date=datetime.fromisoformat(row.creation_date),
            notes=row.notes,
            metadata=row.preset_metadata,
        )

    def _row_to_run(self, row: ExperimentRunORM) -> ExperimentRun:
        return ExperimentRun(
            id=row.id,
            experiment_id=row.experiment_id,
            run_number=row.run_number,
            parameters=row.parameters,
            results=self._dict_to_result(row.results),
            created_at=datetime.fromisoformat(row.created_at),
            notes=row.notes,
        )

    @staticmethod
    def _result_to_dict(result: ResultRecord | None) -> dict[str, Any] | None:
        if result is None:
            return None
        return {
            "quality": result.quality,
            "contrast": result.contrast,
            "detail": result.detail,
            "burn": result.burn,
            "duration_seconds": result.duration_seconds,
            "measurements": result.measurements,
            "observations": result.observations,
            "photo_evidence": result.photo_evidence,
        }

    @staticmethod
    def _dict_to_result(data: dict[str, Any] | None) -> ResultRecord | None:
        if data is None:
            return None
        return ResultRecord(
            quality=data.get("quality"),
            contrast=data.get("contrast"),
            detail=data.get("detail"),
            burn=data.get("burn"),
            duration_seconds=data.get("duration_seconds"),
            measurements=data.get("measurements", {}),
            observations=data.get("observations", ""),
            photo_evidence=data.get("photo_evidence", []),
        )

    def list(self) -> list[Any]:
        return self.list_materials()
