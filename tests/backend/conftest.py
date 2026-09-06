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


@pytest.fixture
def settings(database_path: Path):
    from billbox.config import Settings

    return Settings(
        database_path=database_path,
        migrations_dir=ROOT / "migrations",
        frontend_dist=ROOT / "frontend" / "dist",
        app_password="correct horse battery staple",
        session_secret="test-session-secret-that-is-long-enough",
        session_cookie_secure=False,
    )


@pytest.fixture
def app(settings):
    from billbox.api import create_app

    return create_app(settings)


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client):
    response = client.post(
        "/api/auth/login", json={"password": "correct horse battery staple"}
    )
    assert response.status_code == 204
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is True
    client.csrf_token = session.json()["csrf_token"]
    return client
