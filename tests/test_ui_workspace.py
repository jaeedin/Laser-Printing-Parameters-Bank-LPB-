from __future__ import annotations

from PySide6.QtWidgets import QApplication

from laser_knowledge_system.ui.workspace import ExperimentWorkspaceWidget, create_main_window


def test_workspace_exposes_experiment_sections() -> None:
    app = QApplication.instance() or QApplication([])
    widget = ExperimentWorkspaceWidget()

    assert hasattr(widget, "material_combo")
    assert hasattr(widget, "machine_combo")
    assert hasattr(widget, "process_combo")
    assert hasattr(widget, "objective_input")
    assert widget.notebook is not None
    assert create_main_window().windowTitle() == "Laser Variable Library"
    app.processEvents()
