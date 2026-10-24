from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class MaterialORM(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")


class MachineORM(Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    laser_type: Mapped[str] = mapped_column(String(128), nullable=False)
    rated_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    controller: Mapped[str] = mapped_column(String(128), nullable=False)
    lens_focus: Mapped[str] = mapped_column(String(255), nullable=False)
    air_assist: Mapped[bool] = mapped_column(Boolean, default=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")


class ProcessORM(Base):
    __tablename__ = "processes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    process_type: Mapped[str] = mapped_column(String(64), nullable=False)
    supported_methods: Mapped[str] = mapped_column(Text, default="")
    default_parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    parameter_schema: Mapped[list[dict]] = mapped_column(JSON, default=list)


class ExperimentORM(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    material_id: Mapped[str] = mapped_column(String(64), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(64), nullable=False)
    process_id: Mapped[str] = mapped_column(String(64), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    selected_best_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(64), nullable=True)

    runs: Mapped[list[ExperimentRunORM]] = relationship(back_populates="experiment")


class ExperimentRunORM(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    experiment: Mapped[ExperimentORM] = relationship(back_populates="runs")


class NotebookEntryORM(Base):
    __tablename__ = "notebook_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[str] = mapped_column(Text, default="")


class PresetORM(Base):
    __tablename__ = "presets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_experiment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    settings_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_preset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creation_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    preset_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
