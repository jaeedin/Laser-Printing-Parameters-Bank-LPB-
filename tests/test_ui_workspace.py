from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel

from laser_knowledge_system.db.database import DatabaseManager
from laser_knowledge_system.db.repositories import SQLiteRepository
from laser_knowledge_system.ui.workspace import (
    ExperimentPage,
    ExperimentWorkspaceWidget,
    MaterialFormDialog,
    create_main_window,
)
from laser_knowledge_system.portable_materials import load_open_record


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


def test_material_editor_collects_only_the_five_print_settings(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = MaterialFormDialog(tmp_path)

    draft = load_open_record(tmp_path)
    assert draft is not None
    assert set(draft) == {
        "scope", "material_name", "conversion", "direction", "speed", "power", "quality", "batch_profiles"
    }
    dialog.name.setText("Plywood")
    payload = dialog.payload()

    assert set(payload) == {
        "scope", "material_name", "conversion", "direction", "speed", "power", "quality"
    }
    labels = [label.text() for label in dialog.findChildren(QLabel)]
    assert all(term not in label for label in labels for term in ("Blur", "Brightness", "Contrast", "Torque", "Preset"))
    app.processEvents()


def test_experiment_collection_rows_contain_only_the_five_print_settings(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    database = DatabaseManager(f"sqlite:///{tmp_path / 'library.db'}")
    database.initialize()
    page = ExperimentPage(SQLiteRepository(database), tmp_path)

    page.material.setText("Plywood")
    params = page._parameters()
    page.add_test()

    assert set(params) == {"conversion", "direction", "speed", "power", "quality"}
    assert page.tests.columnCount() == 5
    assert [page.tests.horizontalHeaderItem(index).text() for index in range(5)] == [
        "Conversion", "Direction", "Speed", "Power", "Quality"
    ]
    assert set(page._batch_rows()[0]) == {"conversion", "direction", "speed", "power", "quality"}
    app.processEvents()
