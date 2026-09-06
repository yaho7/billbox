from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "billbox.db"


@pytest.fixture
def database(database_path: Path):
    from billbox.db import Database

    db = Database(database_path, ROOT / "migrations")
    db.migrate()
    return db


@pytest.fixture
def ledger(database):
    from billbox.ledger import Ledger

    return Ledger(database)
