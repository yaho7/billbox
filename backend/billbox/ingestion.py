from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from email.utils import parseaddr
import hashlib
import json
from typing import Any

from .ledger import Ledger
from .parsers import CMBCreditParser, CMBDebitParser, ParsedTransaction


class IngestionService:
    job_name = "mail-ingestion"

    def __init__(
        self,
        ledger: Ledger,
        *,
        mailbox: str,
        max_emails: int,
        parsers: Sequence[Any] | None = None,
    ):
        self.ledger = ledger
        self.mailbox = mailbox
        self.max_emails = max_emails
        self.parsers = tuple(parsers or (CMBCreditParser(), CMBDebitParser()))

    @staticmethod
    def _source_key(
        record_id: str, index: int, transaction: ParsedTransaction
    ) -> str:
        canonical = json.dumps(
            {
                "record_id": record_id,
                "index": index,
                "account_id": transaction.account_id,
                "kind": transaction.kind,
                "amount_minor": transaction.amount_minor,
                "merchant": transaction.merchant,
                "note": transaction.note,
                "occurred_at": transaction.occurred_at,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"imap:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    def run(self, client: Any) -> dict[str, int]:
        job_id = self.ledger.start_job(self.job_name)
        summary: Counter[str] = Counter(
            {"processed": 0, "duplicate": 0, "ignored": 0, "failed": 0}
        )
        self.ledger.append_job_log(job_id, "开始连接邮箱")
        try:
            client.connect()
            candidates: dict[int, Any] = {}
            for parser in self.parsers:
                failed_uids = self.ledger.failed_source_uids(
                    self.mailbox, parser.name
                )
                searched_uids = client.search(parser.search_keyword, self.max_emails)
                for uid in (*failed_uids, *searched_uids):
                    candidates.setdefault(int(uid), parser)

            for uid, parser in candidates.items():
                self._ingest_one(client, uid, parser, summary)

            self.ledger.append_job_log(
                job_id,
                (
                    f"已处理 {summary['processed']} 封，跳过 {summary['duplicate']} 封，"
                    f"忽略 {summary['ignored']} 封，失败 {summary['failed']} 封"
                ),
            )
            result = dict(summary)
            self.ledger.finish_job(job_id, state="succeeded", summary=result)
            return result
        except Exception as error:
            self.ledger.append_job_log(job_id, f"运行中断：{error}")
            self.ledger.finish_job(
                job_id, state="failed", summary=dict(summary), error=str(error)
            )
            raise
        finally:
            client.close()

    def _ingest_one(
        self, client: Any, uid: int, parser: Any, summary: Counter[str]
    ) -> None:
        try:
            message = client.fetch(uid)
        except Exception as error:
            record_id = self.ledger.claim_source_record(
                provider="imap",
                mailbox=self.mailbox,
                uid_validity=int(client.uid_validity),
                uid=uid,
                parser_name=parser.name,
                content_sha256="",
                subject="",
                received_at=None,
                raw={"parser": parser.name},
            )
            if record_id is None:
                summary["duplicate"] += 1
                return
            self.ledger.mark_source_record(record_id, "failed", str(error))
            summary["failed"] += 1
            return

        record_id = self.ledger.claim_source_record(
            provider="imap",
            mailbox=self.mailbox,
            uid_validity=int(client.uid_validity),
            uid=uid,
            parser_name=parser.name,
            content_sha256=message.content_sha256,
            subject=message.subject,
            received_at=message.received_at.isoformat(),
            raw={"message_id": message.message_id, "parser": parser.name},
        )
        if record_id is None:
            summary["duplicate"] += 1
            return

        sender = parseaddr(message.sender)[1].casefold()
        if sender not in {value.casefold() for value in parser.allowed_senders}:
            self.ledger.mark_source_record(record_id, "ignored", "发件人不在允许列表")
            summary["ignored"] += 1
            return

        try:
            transactions = parser.parse(message.text, message.received_at)
            if not transactions:
                self.ledger.mark_source_record(record_id, "ignored", "未识别到交易")
                summary["ignored"] += 1
                return
            for index, transaction in enumerate(transactions):
                self.ledger.create_automation_transaction(
                    {
                        "source_record_id": record_id,
                        "source_key": self._source_key(record_id, index, transaction),
                        "account_id": transaction.account_id,
                        "category_id": transaction.category_id,
                        "kind": transaction.kind,
                        "amount_minor": transaction.amount_minor,
                        "merchant": transaction.merchant,
                        "note": transaction.note,
                        "channel": transaction.channel,
                        "occurred_at": transaction.occurred_at,
                    }
                )
            self.ledger.mark_source_record(record_id, "processed")
            summary["processed"] += 1
        except Exception as error:
            self.ledger.mark_source_record(record_id, "failed", str(error))
            summary["failed"] += 1
