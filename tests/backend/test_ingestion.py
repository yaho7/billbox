from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib


@dataclass(frozen=True)
class FakeMessage:
    uid: int = 1001
    sender: str = "招商银行 <ccsvc@message.cmbchina.com>"
    subject: str = "每日信用管家"
    received_at: datetime = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
    text: str = (
        "2026/09/06 08:30:00 CNY 18.90 "
        "尾号1234 消费 早餐店 (每日邮件)"
    )
    message_id: str = "<mail-1001@example.com>"
    content_sha256: str = hashlib.sha256(b"message-1001").hexdigest()


class FakeClient:
    uid_validity = 42

    def __init__(self, messages=None):
        self.messages = messages or {1001: FakeMessage()}
        self.closed = False
        self.fetches = []

    def connect(self):
        return self

    def close(self):
        self.closed = True

    def search(self, keyword, limit):
        del keyword, limit
        return list(self.messages)

    def fetch(self, uid):
        self.fetches.append(uid)
        value = self.messages[uid]
        if isinstance(value, Exception):
            raise value
        return value


def test_processed_uid_is_not_parsed_twice(ledger):
    from billbox.ingestion import IngestionService

    client = FakeClient()
    service = IngestionService(ledger, mailbox="owner@example.com", max_emails=50)

    first = service.run(client)
    second = service.run(client)

    assert first["processed"] == 1
    assert second["duplicate"] == 1
    assert ledger.list_transactions({})["total"] == 1
    assert client.closed is True


def test_failed_uid_is_persisted_and_retried(ledger):
    from billbox.ingestion import IngestionService

    client = FakeClient({1001: ValueError("temporary fetch failure")})
    service = IngestionService(ledger, mailbox="owner@example.com", max_emails=50)

    first = service.run(client)
    client.messages[1001] = FakeMessage()
    second = service.run(client)

    assert first["failed"] == 1
    assert second["processed"] == 1
    assert ledger.list_transactions({})["total"] == 1


def test_untrusted_sender_is_recorded_as_ignored(ledger):
    from billbox.ingestion import IngestionService

    message = FakeMessage(sender="attacker@example.com")
    client = FakeClient({1001: message})

    summary = IngestionService(
        ledger, mailbox="owner@example.com", max_emails=50
    ).run(client)

    assert summary["ignored"] == 1
    assert ledger.list_transactions({})["total"] == 0


def test_ingestion_records_bounded_job_log(ledger):
    from billbox.ingestion import IngestionService

    service = IngestionService(ledger, mailbox="owner@example.com", max_emails=50)
    service.run(FakeClient())
    latest = ledger.latest_job("mail-ingestion")

    assert latest["state"] == "succeeded"
    assert latest["summary"]["processed"] == 1
    assert "已处理 1 封" in latest["log_text"]
    assert len(latest["log_text"]) <= 20000
