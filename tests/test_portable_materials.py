from __future__ import annotations

import json

from laser_knowledge_system.db.database import DatabaseManager
from laser_knowledge_system.db.repositories import SQLiteRepository
from laser_knowledge_system.portable_materials import (
    profile_key,
    scan_packages,
    sync_vault,
    update_package,
    write_package,
)


def _payload() -> dict:
    return {
        "id": "birch_plywood_3mm_cut",
        "material_name": "Birch Plywood",
        "conversion": "Centerline",
        "direction": "Bidirectional",
        "speed": 120,
        "power": 90,
        "quality": 15,
        "blur": 12,
        "brightness": 20,
        "contrast": 5,
        "torque": 4,
        "variant_name": "Dark",
    }


def test_material_package_is_portable_and_syncs_into_sqlite(tmp_path) -> None:
    package = write_package(tmp_path / "materials_vault", _payload())
    assert package.folder.name == "birch_plywood_3mm_cut"
    saved = json.loads((package.folder / "data.json").read_text())
    assert set(saved) == {
        "id", "material_name", "conversion", "direction", "speed", "power", "quality"
    }
    assert saved["conversion"] == "Centerline"
    assert saved["direction"] == "Bidirectional"

    database = DatabaseManager(f"sqlite:///{tmp_path / 'library.db'}")
    database.initialize()
    repo = SQLiteRepository(database)
    packages = sync_vault(repo, tmp_path / "materials_vault")

    assert [item.id for item in packages] == ["birch_plywood_3mm_cut"]
    material = repo.get_material("birch_plywood_3mm_cut")
    assert material.name == "Birch Plywood"
    assert material.properties == {}
    assert material.notes == ""


def test_profile_updates_keep_only_the_five_supported_settings(tmp_path) -> None:
    package = write_package(tmp_path / "materials_vault", _payload())
    updated = update_package(
        package,
        {
            "conversion": "Jarvis",
            "direction": "Vertical",
            "speed": 450,
            "power": 65,
            "quality": 20,
            "brightness": 30,
            "dark_light": "Dark",
        },
    )

    assert profile_key(updated.data) == (
        "birch plywood", "jarvis", "vertical", "450.0", "65.0", "20.0"
    )
    assert set(json.loads((package.folder / "data.json").read_text())) == {
        "id", "material_name", "conversion", "direction", "speed", "power", "quality"
    }


def test_profile_requires_all_five_values(tmp_path) -> None:
    payload = _payload()
    del payload["quality"]

    try:
        write_package(tmp_path / "materials_vault", payload)
    except ValueError as error:
        assert "quality" in str(error)
    else:
        raise AssertionError("Expected missing required quality to be rejected")


def test_dark_or_light_presets_are_not_converted_to_direction(tmp_path) -> None:
    payload = _payload()
    payload["variant_name"] = "Dark"
    del payload["direction"]

    try:
        write_package(tmp_path / "materials_vault", payload)
    except ValueError as error:
        assert "direction" in str(error)
    else:
        raise AssertionError("Dark must not be accepted as a direction")


def test_legacy_profiles_are_read_as_only_the_five_settings(tmp_path) -> None:
    folder = tmp_path / "materials_vault" / "legacy_profile"
    folder.mkdir(parents=True)
    (folder / "data.json").write_text(
        json.dumps(
            {
                "id": "legacy_profile",
                "material_name": "Plywood",
                "conversion_model": "Centerline",
                "variant_name": "Dark",
                "speed_mm_min": 900,
                "power_percent": 70,
                "blur": 4,
                "brightness": 5,
                "contrast": 6,
            }
        )
    )

    [package] = scan_packages(tmp_path / "materials_vault")

    assert package.data["direction"] == "Horizontal"
    assert package.data["quality"] == 15
    assert set(package.data) == {
        "id", "material_name", "conversion", "direction", "speed", "power", "quality", "scope"
    }


def test_scan_skips_invalid_dropped_folder(tmp_path) -> None:
    invalid = tmp_path / "materials_vault" / "bad_package"
    invalid.mkdir(parents=True)
    (invalid / "data.json").write_text("not json")
    assert scan_packages(tmp_path / "materials_vault") == []
