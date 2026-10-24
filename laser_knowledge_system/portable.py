"""Portable experiment blocks for sharing between Laser Knowledge installations."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from laser_knowledge_system.db.repositories import SQLiteRepository
from laser_knowledge_system.domain.experiments import Experiment, ExperimentRun, ExperimentStatus, ResultRecord
from laser_knowledge_system.domain.machines import MachineProfile
from laser_knowledge_system.domain.materials import MaterialFamily, MaterialRecord
from laser_knowledge_system.domain.processes import ParameterValueType, ProcessDefinition, ProcessParameterDefinition, ProcessType

FORMAT = "laser-knowledge-experiment/v1"

def export_experiment(repo: SQLiteRepository, experiment_id: str, destination: Path) -> Path:
    """Write one self-contained ``.laserblock`` file, including its context and trial values."""
    experiment = repo.get_experiment(experiment_id)
    if experiment is None:
        raise ValueError("Experiment does not exist.")
    material, machine, process = (repo.get_material(experiment.material_id), repo.get_machine(experiment.machine_id), repo.get_process(experiment.process_id))
    payload = {"format": FORMAT, "material": asdict(material), "machine": asdict(machine), "process": asdict(process), "experiment": {
        "id": experiment.id, "material_id": experiment.material_id, "machine_id": experiment.machine_id, "process_id": experiment.process_id,
        "objective": experiment.objective, "status": experiment.status.value, "conclusion": experiment.conclusion,
        "selected_best_run_id": experiment.selected_best_run_id, "start_time": experiment.start_time.isoformat(), "end_time": experiment.end_time.isoformat() if experiment.end_time else None,
        "runs": [{"id": run.id, "experiment_id": run.experiment_id, "run_number": run.run_number, "parameters": run.parameters, "results": asdict(run.results) if run.results else None, "created_at": run.created_at.isoformat(), "notes": run.notes} for run in experiment.runs],
    }}
    # Convert enums nested in the process schema to stable string values.
    payload["material"]["family"] = material.family.value
    payload["process"]["process_type"] = process.process_type.value
    payload["process"]["supported_methods"] = [item.value for item in process.supported_methods]
    payload["process"]["parameter_schema"] = [item.to_dict() for item in process.parameter_schema]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination

def import_experiment(repo: SQLiteRepository, source: Path) -> Experiment:
    """Import a block. IDs are preserved so its source history remains traceable."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("format") != FORMAT:
        raise ValueError("This is not a Laser Knowledge experiment block.")
    material = payload["material"]; machine = payload["machine"]; process = payload["process"]; record = payload["experiment"]
    if repo.get_material(material["id"]) is None: repo.add_material(MaterialRecord(**{**material, "family": MaterialFamily(material["family"])}))
    if repo.get_machine(machine["id"]) is None: repo.add_machine(MachineProfile(**machine))
    if repo.get_process(process["id"]) is None:
        repo.add_process(ProcessDefinition(id=process["id"], name=process["name"], process_type=ProcessType(process["process_type"]), supported_methods=[], default_parameters=process["default_parameters"], parameter_schema=[ProcessParameterDefinition.from_dict(item) for item in process["parameter_schema"]]))
    experiment = Experiment(id=record["id"], material_id=record["material_id"], machine_id=record["machine_id"], process_id=record["process_id"], objective=record["objective"], status=ExperimentStatus(record["status"]), conclusion=record["conclusion"], selected_best_run_id=record["selected_best_run_id"], start_time=datetime.fromisoformat(record["start_time"]), end_time=datetime.fromisoformat(record["end_time"]) if record["end_time"] else None)
    if repo.get_experiment(experiment.id) is None: repo.add_experiment(experiment)
    for item in record["runs"]:
        if not any(run.id == item["id"] for run in repo.list_runs(experiment.id)):
            results = ResultRecord(**item["results"]) if item["results"] else None
            repo.add_run(ExperimentRun(id=item["id"], experiment_id=experiment.id, run_number=item["run_number"], parameters=item["parameters"], results=results, created_at=datetime.fromisoformat(item["created_at"]), notes=item["notes"]))
    return repo.get_experiment(experiment.id)
