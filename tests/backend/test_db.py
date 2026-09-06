from __future__ import annotations

import sqlite3

import pytest


def test_migrations_create_normalized_ledger_tables(database):
    with database.connect() as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "accounts",
        "categories",
        "source_records",
        "transactions",
        "transaction_audit",
        "job_runs",
    }.issubset(names)


def test_connections_enable_foreign_keys_wal_and_busy_timeout(database):
    with database.connect() as connection:
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert foreign_keys == 1
    assert journal_mode == "wal"
    assert busy_timeout == 5000


def test_transaction_amount_must_be_positive(database):
    with database.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO transactions (
                    id, source_key, account_id, kind, amount_minor, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "invalid",
                    "manual:invalid",
                    "cash",
                    "expense",
                    -1890,
                    "2026-09-06T08:30:00+08:00",
                ),
            )


def test_migrations_are_safe_to_apply_twice(database):
    database.migrate()

    with database.connect() as connection:
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert [row[0] for row in versions] == [1, 2]
