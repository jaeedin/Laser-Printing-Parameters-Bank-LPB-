from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from laser_knowledge_system.db.database import DatabaseManager
    from laser_knowledge_system.db.repositories import SQLiteRepository
    from laser_knowledge_system.ui.workspace import create_main_window

    app = QApplication(sys.argv)
    database_path = (Path.cwd() / "laser_knowledge_system.db").as_posix()
    database = DatabaseManager(f"sqlite:///{database_path}")
    database.initialize()
    window = create_main_window(SQLiteRepository(database))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
