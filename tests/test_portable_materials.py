from __future__ import annotations

import json

from laser_knowledge_system.db.database import DatabaseManager
from laser_knowledge_system.db.repositories import SQLiteRepository
from laser_knowledge_system.portable_materials import scan_packages, sync_vault, write_package


def _payload() -> dict:
    return {
        "id": "birch_plywood_3mm_cut",
        "material_name": "Birch Plywood",
        "thickness_mm": 3.0,
        "operation": "Cut",
        "conversion_model": "Vectorizing",
        "speed_mm_min": 120,
        "power_percent": 90,
        "passes": 3,
        "laser_wattage": "10W Diode",
        "notes": "Use air assist.",
    }


def test_material_package_is_portable_and_syncs_into_sqlite(tmp_path) -> None:
    package = write_package(tmp_path / "materials_vault", _payload())
    assert package.folder.name == "birch_plywood_3mm_cut"
    assert json.loads((package.folder / "data.json").read_text())["operation"] == "Cut"

    database = DatabaseManager(f"sqlite:///{tmp_path / 'library.db'}")
    database.initialize()
    repo = SQLiteRepository(database)
    packages = sync_vault(repo, tmp_path / "materials_vault")

    assert [item.id for item in packages] == ["birch_plywood_3mm_cut"]
    assert repo.get_material("birch_plywood_3mm_cut").name == "Birch Plywood"


def test_scan_skips_invalid_dropped_folder(tmp_path) -> None:
    invalid = tmp_path / "materials_vault" / "bad_package"
    invalid.mkdir(parents=True)
    (invalid / "data.json").write_text("not json")
    assert scan_packages(tmp_path / "materials_vault") == []
