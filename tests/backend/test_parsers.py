from __future__ import annotations

from datetime import datetime, timezone


def test_credit_purchase_becomes_positive_minor_expense():
    from billbox.parsers import CMBCreditParser

    text = """
    2026/09/06
    08:30:00
    CNY 18.90
    尾号1234 消费 早餐店
    (每日邮件)
    """
    rows = CMBCreditParser().parse(text, datetime(2026, 9, 6))

    assert len(rows) == 1
    assert rows[0].kind == "expense"
    assert rows[0].amount_minor == 1890
    assert rows[0].account_id == "cmb-credit"
    assert rows[0].merchant == "早餐店"


def test_credit_negative_amount_or_refund_copy_becomes_refund():
    from billbox.parsers import CMBCreditParser

    text = """
    2026/09/06
    10:20:30 CNY -17.90 尾号1234 退货 早餐店
    (Daily Email)
    """
    row = CMBCreditParser().parse(text, datetime(2026, 9, 6))[0]

    assert row.kind == "refund"
    assert row.amount_minor == 1790


def test_debit_purchase_and_income_keep_economic_kind():
    from billbox.parsers import CMBDebitParser

    text = """
    您的账户于09月06日08:30在支付宝-早餐店快捷支付人民币18.90元。
    您的账户于09月06日09:00工资入账人民币5000.00元。
    """
    rows = CMBDebitParser().parse(text, datetime(2026, 9, 6, tzinfo=timezone.utc))

    assert [(row.kind, row.amount_minor) for row in rows] == [
        ("expense", 1890),
        ("income", 500000),
    ]
    assert all(row.account_id == "cmb-debit" for row in rows)


def test_debit_transfer_is_not_counted_as_expense():
    from billbox.parsers import CMBDebitParser

    text = "您的账户于09月06日12:00向张三转账人民币100.00元。"
    row = CMBDebitParser().parse(text, datetime(2026, 9, 6))[0]

    assert row.kind == "transfer"
    assert row.amount_minor == 10000


def test_parser_uses_previous_year_for_december_notice_received_in_january():
    from billbox.parsers import CMBDebitParser

    text = "您的账户于12月31日23:50在便利店消费人民币12.00元。"
    row = CMBDebitParser().parse(text, datetime(2027, 1, 1, 8, 0))[0]

    assert row.occurred_at.startswith("2026-12-31T23:50")
