from __future__ import annotations

from laser_knowledge_system.db.database import DatabaseManager
from laser_knowledge_system.db.repositories import RepositoryError, SQLiteRepository
from laser_knowledge_system.domain.materials import MaterialFamily, MaterialRecord
import pytest


def test_database_manager_creates_sqlite_database(tmp_path) -> None:
    db_path = tmp_path / "test_lks.sqlite"
    manager = DatabaseManager(database_url=f"sqlite:///{db_path}")

    manager.initialize()

    assert db_path.exists()
    assert manager.engine is not None
    manager.dispose()


def test_repository_can_list_entities(tmp_path) -> None:
    db_path = tmp_path / "repo.sqlite"
    manager = DatabaseManager(database_url=f"sqlite:///{db_path}")
    manager.initialize()

    repo = SQLiteRepository(manager)
    assert repo.list_materials() == []


def test_repository_rejects_duplicate_entity_ids(tmp_path) -> None:
    manager = DatabaseManager(database_url=f"sqlite:///{tmp_path / 'repo.sqlite'}")
    manager.initialize()
    repo = SQLiteRepository(manager)
    material = MaterialRecord(id="steel", family=MaterialFamily.METAL, name="Steel")

    repo.add_material(material)
    with pytest.raises(RepositoryError, match="Material 'steel' already exists"):
        repo.add_material(material)
