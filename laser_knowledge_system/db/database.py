from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self, database_url: str = "sqlite:///laser_knowledge_system.db") -> None:
        self.database_url = database_url
        self.engine = create_engine(database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    def health_check(self) -> bool:
        with self.engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return result.scalar_one() == 1

    def dispose(self) -> None:
        """Close database connections when the application or a temporary task ends."""
        self.engine.dispose()
