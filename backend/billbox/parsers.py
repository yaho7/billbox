from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import re

from .ledger import amount_to_minor


@dataclass(frozen=True, slots=True)
class ParsedTransaction:
    account_id: str
    kind: str
    amount_minor: int
    merchant: str
    note: str
    channel: str
    occurred_at: str
    category_id: str | None = None


def _clean(value: str) -> str:
    return " ".join(value.split()).strip(" ,，。")


def _resolve_date(month: int, day: int, received_at: datetime) -> date:
    candidate = date(received_at.year, month, day)
    received_date = received_at.date()
    if candidate - received_date > timedelta(days=45):
        candidate = date(received_at.year - 1, month, day)
    elif received_date - candidate > timedelta(days=320):
        candidate = date(received_at.year + 1, month, day)
    return candidate


def _occurred_at(day: date, value: str, received_at: datetime) -> str:
    parsed_time = time.fromisoformat(value)
    combined = datetime.combine(day, parsed_time, tzinfo=received_at.tzinfo)
    return combined.isoformat()


def _channel(merchant: str) -> str:
    for name in ("支付宝", "微信", "财付通", "美团", "京东", "云闪付"):
        if merchant.startswith(name):
            return name
    return "招商银行"


class CMBCreditParser:
    name = "cmb-credit-daily-v1"
    search_keyword = "每日信用管家"
    allowed_senders = {
        "ccsvc@message.cmbchina.com",
        "95555@message.cmbchina.com",
    }

    _pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2})\s+CNY\s+([+-]?\d+(?:\.\d+)?)\s+"
        r"(.*?)(?=\s*(?:\d{2}:\d{2}:\d{2}|\(每日邮件\)|\(Daily Email\)|$))",
        re.DOTALL,
    )

    def parse(self, text: str, received_at: datetime) -> list[ParsedTransaction]:
        date_match = re.search(r"(\d{4})/(\d{2})/(\d{2})", text)
        if date_match:
            transaction_date = date(*(int(value) for value in date_match.groups()))
        else:
            transaction_date = received_at.date()

        transactions: list[ParsedTransaction] = []
        for match in self._pattern.finditer(text):
            raw_amount = Decimal(match.group(2))
            if not raw_amount:
                continue
            note = _clean(match.group(3))
            is_refund = raw_amount < 0 or any(
                marker in note for marker in ("退货", "退款", "冲正")
            )
            merchant = re.sub(
                r"^尾号\d+\s*(?:消费|退货|退款|冲正|预授权完成)\s*",
                "",
                note,
            )
            merchant = _clean(merchant)
            transactions.append(
                ParsedTransaction(
                    account_id="cmb-credit",
                    kind="refund" if is_refund else "expense",
                    amount_minor=amount_to_minor(abs(raw_amount)),
                    merchant=merchant,
                    note=note,
                    channel=_channel(merchant),
                    occurred_at=_occurred_at(
                        transaction_date, match.group(1), received_at
                    ),
                )
            )
        return transactions


class CMBDebitParser:
    name = "cmb-debit-notice-v1"
    search_keyword = "通知"
    allowed_senders = {"95555@message.cmbchina.com"}

    _rules = (
        (
            re.compile(
                r"于(\d{2})月(\d{2})日(\d{2}:\d{2})[^\n。]*?在([^\n。]*?)"
                r"(?:快捷支付|支付|消费)(?:人民币)?([\d.]+)元",
            ),
            "expense",
        ),
        (
            re.compile(
                r"于(\d{2})月(\d{2})日(\d{2}:\d{2})[^\n。]*?向([^\n。]*?)"
                r"(?:转账|汇款)(?:人民币)?([\d.]+)元",
            ),
            "transfer",
        ),
        (
            re.compile(
                r"于(\d{2})月(\d{2})日(\d{2}:\d{2})([^\n。]*?)"
                r"(入账|存入|退款)(?:人民币)?([\d.]+)元",
            ),
            "inflow",
        ),
    )

    def parse(self, text: str, received_at: datetime) -> list[ParsedTransaction]:
        matches: list[tuple[int, ParsedTransaction]] = []
        occupied: list[tuple[int, int]] = []
        for pattern, rule_kind in self._rules:
            for match in pattern.finditer(text):
                if any(
                    not (match.end() <= start or match.start() >= end)
                    for start, end in occupied
                ):
                    continue
                try:
                    transaction_date = _resolve_date(
                        int(match.group(1)), int(match.group(2)), received_at
                    )
                    if rule_kind == "inflow":
                        marker = match.group(5)
                        merchant = _clean(match.group(4)) or "招商银行入账"
                        amount_text = match.group(6)
                        kind = "refund" if marker == "退款" else "income"
                    else:
                        merchant = _clean(match.group(4)) or "招商银行"
                        amount_text = match.group(5)
                        kind = rule_kind
                    amount = amount_to_minor(Decimal(amount_text))
                except (InvalidOperation, ValueError):
                    continue
                occupied.append(match.span())
                note = _clean(match.group(0))
                matches.append(
                    (
                        match.start(),
                        ParsedTransaction(
                            account_id="cmb-debit",
                            kind=kind,
                            amount_minor=amount,
                            merchant=merchant,
                            note=note,
                            channel=_channel(merchant),
                            occurred_at=_occurred_at(
                                transaction_date, f"{match.group(3)}:00", received_at
                            ),
                        ),
                    )
                )
        return [transaction for _, transaction in sorted(matches, key=lambda item: item[0])]
