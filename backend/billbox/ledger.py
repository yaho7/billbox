from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import math
import re
from typing import Any, Mapping
from uuid import uuid4

from .db import Database


TRANSACTION_KINDS = {"expense", "income", "refund", "transfer", "repayment"}
REVIEW_STATES = {"pending", "confirmed"}
MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def amount_to_minor(amount: str | Decimal) -> int:
    try:
        decimal = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("amount must be a decimal number") from error
    if decimal <= 0:
        raise ValueError("amount must be greater than zero")
    return int(decimal * 100)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Mapping[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row(row: Any) -> dict[str, Any]:
    return dict(row)


class Ledger:
    def __init__(self, database: Database):
        self.database = database

    def _validate_kind(self, kind: str) -> str:
        if kind not in TRANSACTION_KINDS:
            raise ValueError("unknown transaction kind")
        return kind

    def _validate_review_state(self, state: str) -> str:
        if state not in REVIEW_STATES:
            raise ValueError("unknown review state")
        return state

    @staticmethod
    def _transaction_row(connection: Any, transaction_id: str) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT
                transactions.*,
                accounts.name AS account_name,
                categories.name AS category_name
            FROM transactions
            JOIN accounts ON accounts.id = transactions.account_id
            LEFT JOIN categories ON categories.id = transactions.category_id
            WHERE transactions.id = ?
            """,
            (transaction_id,),
        ).fetchone()
        if row is None:
            raise LookupError("transaction not found")
        return _row(row)

    @staticmethod
    def _audit(
        connection: Any,
        transaction_id: str,
        action: str,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any],
        actor: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO transaction_audit (
                transaction_id, action, before_json, after_json, actor
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (transaction_id, action, _json(before), _json(after), actor),
        )

    def create_manual_transaction(
        self, payload: Mapping[str, Any], *, actor: str
    ) -> dict[str, Any]:
        transaction_id = str(uuid4())
        now = _now()
        values = {
            "id": transaction_id,
            "source_key": f"manual:{transaction_id}",
            "account_id": str(payload["account_id"]),
            "category_id": payload.get("category_id") or None,
            "kind": self._validate_kind(str(payload["kind"])),
            "amount_minor": amount_to_minor(payload["amount"]),
            "currency": str(payload.get("currency") or "CNY").upper(),
            "merchant": str(payload.get("merchant") or "").strip(),
            "note": str(payload.get("note") or "").strip(),
            "channel": str(payload.get("channel") or "").strip(),
            "occurred_at": str(payload["occurred_at"]),
            "review_state": self._validate_review_state(
                str(payload.get("review_state") or "confirmed")
            ),
            "created_at": now,
            "updated_at": now,
        }
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO transactions (
                    id, source_key, account_id, category_id, kind, amount_minor,
                    currency, merchant, note, channel, occurred_at, review_state,
                    created_at, updated_at
                ) VALUES (
                    :id, :source_key, :account_id, :category_id, :kind, :amount_minor,
                    :currency, :merchant, :note, :channel, :occurred_at, :review_state,
                    :created_at, :updated_at
                )
                """,
                values,
            )
            created = self._transaction_row(connection, transaction_id)
            self._audit(connection, transaction_id, "created", None, created, actor)
        return created

    def create_automation_transaction(
        self, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        source_key = str(payload["source_key"])
        amount_minor = int(payload["amount_minor"])
        if amount_minor <= 0:
            raise ValueError("amount_minor must be greater than zero")
        transaction_id = str(uuid4())
        now = _now()
        values = {
            "id": transaction_id,
            "source_record_id": payload.get("source_record_id"),
            "source_key": source_key,
            "account_id": str(payload["account_id"]),
            "category_id": payload.get("category_id") or None,
            "kind": self._validate_kind(str(payload["kind"])),
            "amount_minor": amount_minor,
            "currency": str(payload.get("currency") or "CNY").upper(),
            "merchant": str(payload.get("merchant") or "").strip(),
            "note": str(payload.get("note") or "").strip(),
            "channel": str(payload.get("channel") or "").strip(),
            "occurred_at": str(payload["occurred_at"]),
            "review_state": self._validate_review_state(
                str(payload.get("review_state") or "pending")
            ),
            "created_at": now,
            "updated_at": now,
        }
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO transactions (
                    id, source_record_id, source_key, account_id, category_id,
                    kind, amount_minor, currency, merchant, note, channel,
                    occurred_at, review_state, created_at, updated_at
                ) VALUES (
                    :id, :source_record_id, :source_key, :account_id, :category_id,
                    :kind, :amount_minor, :currency, :merchant, :note, :channel,
                    :occurred_at, :review_state, :created_at, :updated_at
                )
                """,
                values,
            )
            if cursor.rowcount == 0:
                existing = connection.execute(
                    "SELECT id FROM transactions WHERE source_key = ?",
                    (source_key,),
                ).fetchone()
                if existing is None:
                    raise RuntimeError("idempotent insert did not return existing record")
                return self._transaction_row(connection, str(existing["id"]))
            created = self._transaction_row(connection, transaction_id)
            self._audit(
                connection,
                transaction_id,
                "created",
                None,
                created,
                "automation",
            )
        return created

    def update_transaction(
        self,
        transaction_id: str,
        changes: Mapping[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        allowed = {"category_id", "note", "review_state"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"fields cannot be updated: {', '.join(sorted(unknown))}")
        if not changes:
            raise ValueError("at least one change is required")

        normalized: dict[str, Any] = {}
        if "category_id" in changes:
            normalized["category_id"] = changes["category_id"] or None
        if "note" in changes:
            normalized["note"] = str(changes["note"]).strip()
        if "review_state" in changes:
            normalized["review_state"] = self._validate_review_state(
                str(changes["review_state"])
            )

        with self.database.transaction() as connection:
            before = self._transaction_row(connection, transaction_id)
            assignments = [f"{name} = ?" for name in normalized]
            assignments.append("updated_at = ?")
            connection.execute(
                f"UPDATE transactions SET {', '.join(assignments)} WHERE id = ?",
                (*normalized.values(), _now(), transaction_id),
            )
            after = self._transaction_row(connection, transaction_id)
            self._audit(connection, transaction_id, "updated", before, after, actor)
        return after

    def list_transactions(self, filters: Mapping[str, Any]) -> dict[str, Any]:
        clauses: list[str] = []
        parameters: list[Any] = []
        query = str(filters.get("query") or "").strip()
        if query:
            clauses.append("(transactions.merchant LIKE ? OR transactions.note LIKE ?)")
            parameters.extend((f"%{query}%", f"%{query}%"))
        for field, column in (
            ("account", "transactions.account_id"),
            ("category", "transactions.category_id"),
            ("kind", "transactions.kind"),
            ("review_state", "transactions.review_state"),
        ):
            value = str(filters.get(field) or "").strip()
            if value:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        date_from = str(filters.get("date_from") or "").strip()
        if date_from:
            clauses.append("transactions.occurred_at >= ?")
            parameters.append(date_from)
        date_to = str(filters.get("date_to") or "").strip()
        if date_to:
            clauses.append("transactions.occurred_at < ?")
            parameters.append(f"{date_to}T23:59:59.999999+99:99")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            page = max(1, int(filters.get("page") or 1))
        except (TypeError, ValueError):
            page = 1
        page_size = 25
        offset = (page - 1) * page_size
        with self.database.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM transactions {where}", parameters
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT
                    transactions.*,
                    accounts.name AS account_name,
                    categories.name AS category_name
                FROM transactions
                JOIN accounts ON accounts.id = transactions.account_id
                LEFT JOIN categories ON categories.id = transactions.category_id
                {where}
                ORDER BY transactions.occurred_at DESC, transactions.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*parameters, page_size, offset),
            ).fetchall()
        return {
            "items": [_row(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def dashboard(self, month: str) -> dict[str, Any]:
        if not MONTH_PATTERN.fullmatch(month):
            raise ValueError("month must use YYYY-MM")
        start = f"{month}-01"
        year, month_number = (int(part) for part in month.split("-"))
        if month_number == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month_number + 1:02d}-01"
        with self.database.connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN kind IN ('expense', 'repayment') THEN amount_minor ELSE 0 END), 0) AS expense_minor,
                    COALESCE(SUM(CASE WHEN kind IN ('income', 'refund') THEN amount_minor ELSE 0 END), 0) AS income_minor,
                    SUM(CASE WHEN review_state = 'pending' THEN 1 ELSE 0 END) AS review_count
                FROM transactions
                WHERE occurred_at >= ? AND occurred_at < ?
                """,
                (start, end),
            ).fetchone()
            category_rows = connection.execute(
                """
                SELECT
                    COALESCE(categories.id, 'uncategorized') AS category_id,
                    COALESCE(categories.name, '待分类') AS category_name,
                    SUM(transactions.amount_minor) AS amount_minor
                FROM transactions
                LEFT JOIN categories ON categories.id = transactions.category_id
                WHERE transactions.occurred_at >= ?
                  AND transactions.occurred_at < ?
                  AND transactions.kind IN ('expense', 'repayment')
                GROUP BY categories.id, categories.name
                ORDER BY amount_minor DESC
                """,
                (start, end),
            ).fetchall()
            daily_rows = connection.execute(
                """
                SELECT
                    substr(occurred_at, 1, 10) AS day,
                    SUM(CASE WHEN kind IN ('expense', 'repayment') THEN amount_minor ELSE 0 END) AS expense_minor,
                    SUM(CASE WHEN kind IN ('income', 'refund') THEN amount_minor ELSE 0 END) AS income_minor
                FROM transactions
                WHERE occurred_at >= ? AND occurred_at < ?
                GROUP BY substr(occurred_at, 1, 10)
                ORDER BY day
                """,
                (start, end),
            ).fetchall()

        expense = int(totals["expense_minor"] or 0)
        income = int(totals["income_minor"] or 0)
        return {
            "month": month,
            "expense_minor": expense,
            "income_minor": income,
            "net_minor": income - expense,
            "review_count": int(totals["review_count"] or 0),
            "categories": [_row(row) for row in category_rows],
            "daily": [_row(row) for row in daily_rows],
        }

    def list_options(self) -> dict[str, list[dict[str, Any]]]:
        with self.database.connect() as connection:
            accounts = connection.execute(
                "SELECT id, name, kind, currency FROM accounts WHERE archived_at IS NULL ORDER BY name"
            ).fetchall()
            categories = connection.execute(
                "SELECT id, name, scope FROM categories WHERE archived_at IS NULL ORDER BY name"
            ).fetchall()
        return {
            "accounts": [_row(row) for row in accounts],
            "categories": [_row(row) for row in categories],
        }

    def list_audit(self, transaction_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT action, before_json, after_json, actor, created_at
                FROM transaction_audit
                WHERE transaction_id = ?
                ORDER BY id
                """,
                (transaction_id,),
            ).fetchall()
        return [
            {
                "action": row["action"],
                "before": json.loads(row["before_json"])
                if row["before_json"]
                else None,
                "after": json.loads(row["after_json"]),
                "actor": row["actor"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def claim_source_record(
        self,
        *,
        provider: str,
        mailbox: str,
        uid_validity: int,
        uid: int,
        parser_name: str,
        content_sha256: str,
        subject: str,
        received_at: str | None,
        raw: Mapping[str, Any] | None = None,
    ) -> str | None:
        now = _now()
        with self.database.transaction() as connection:
            existing = connection.execute(
                """
                SELECT id, state
                FROM source_records
                WHERE provider = ? AND mailbox = ? AND uid_validity = ? AND uid = ?
                """,
                (provider, mailbox, uid_validity, uid),
            ).fetchone()
            if existing is not None and existing["state"] in {"processed", "ignored"}:
                return None
            if existing is not None:
                record_id = str(existing["id"])
                connection.execute(
                    """
                    UPDATE source_records
                    SET parser_name = ?, content_sha256 = ?, subject = ?,
                        received_at = ?, state = 'claimed', error = NULL,
                        raw_json = ?, attempt_count = attempt_count + 1,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        parser_name,
                        content_sha256,
                        subject,
                        received_at,
                        _json(raw or {}) or "{}",
                        now,
                        record_id,
                    ),
                )
                return record_id

            record_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO source_records (
                    id, provider, mailbox, uid_validity, uid, parser_name,
                    content_sha256, subject, received_at, state, raw_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'claimed', ?, ?, ?)
                """,
                (
                    record_id,
                    provider,
                    mailbox,
                    uid_validity,
                    uid,
                    parser_name,
                    content_sha256,
                    subject,
                    received_at,
                    _json(raw or {}) or "{}",
                    now,
                    now,
                ),
            )
        return record_id

    def mark_source_record(
        self, record_id: str, state: str, error: str | None = None
    ) -> None:
        if state not in {"processed", "ignored", "failed"}:
            raise ValueError("unknown source record state")
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE source_records
                SET state = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (state, error, _now(), record_id),
            )

    def failed_source_uids(self, mailbox: str, parser_name: str) -> list[int]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT uid
                FROM source_records
                WHERE provider = 'imap' AND mailbox = ?
                  AND parser_name = ? AND state = 'failed'
                ORDER BY updated_at
                """,
                (mailbox, parser_name),
            ).fetchall()
        return [int(row["uid"]) for row in rows]

    def start_job(self, job_name: str) -> str:
        job_id = str(uuid4())
        now = _now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE job_runs
                SET state = 'failed', finished_at = ?,
                    error = '服务重启，上一次运行未正常结束'
                WHERE job_name = ? AND state = 'running'
                """,
                (now, job_name),
            )
            connection.execute(
                """
                INSERT INTO job_runs (id, job_name, state, started_at)
                VALUES (?, ?, 'running', ?)
                """,
                (job_id, job_name, now),
            )
        return job_id

    def append_job_log(self, job_id: str, message: str) -> None:
        line = message.rstrip() + "\n"
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE job_runs
                SET log_text = substr(log_text || ?, -20000)
                WHERE id = ?
                """,
                (line, job_id),
            )

    def finish_job(
        self,
        job_id: str,
        *,
        state: str,
        summary: Mapping[str, Any],
        error: str | None = None,
    ) -> None:
        if state not in {"succeeded", "failed"}:
            raise ValueError("job state must be succeeded or failed")
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE job_runs
                SET state = ?, finished_at = ?, summary_json = ?, error = ?
                WHERE id = ?
                """,
                (state, _now(), _json(summary) or "{}", error, job_id),
            )

    def latest_job(self, job_name: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM job_runs
                WHERE job_name = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (job_name,),
            ).fetchone()
        if row is None:
            return None
        result = _row(row)
        result["summary"] = json.loads(result.pop("summary_json"))
        return result
