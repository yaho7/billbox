from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3


MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[a-z0-9_]+\.sql$")


class Database:
    def __init__(self, path: str | Path, migrations_dir: str | Path):
        self.path = Path(path)
        self.migrations_dir = Path(migrations_dir)

    def _open(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = self._open()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def migrate(self) -> None:
        migration_paths: list[tuple[int, Path]] = []
        for path in sorted(self.migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
            match = MIGRATION_NAME.match(path.name)
            if match is None:
                continue
            migration_paths.append((int(match.group("version")), path))

        if not migration_paths:
            raise RuntimeError(f"no migrations found in {self.migrations_dir}")

        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied = {
                int(row[0])
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for version, path in migration_paths:
                if version in applied:
                    continue
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (version, path.name),
                )
                connection.commit()

    def healthcheck(self) -> bool:
        with self.connect() as connection:
            return connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
