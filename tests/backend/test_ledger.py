from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest


def test_decimal_amount_uses_integer_minor_units():
    from billbox.ledger import amount_to_minor

    assert amount_to_minor("18.905") == 1891
    assert amount_to_minor(Decimal("0.01")) == 1

    with pytest.raises(ValueError, match="greater than zero"):
        amount_to_minor("0")


def test_amount_is_positive_and_kind_is_separate(ledger):
    transaction = ledger.create_manual_transaction(
        {
            "account_id": "cash",
            "kind": "expense",
            "amount": "18.90",
            "merchant": "早餐店",
            "note": "豆浆和包子",
            "occurred_at": "2026-09-06T08:30:00+08:00",
        },
        actor="owner",
    )

    assert transaction["amount_minor"] == 1890
    assert transaction["kind"] == "expense"
    assert transaction["merchant"] == "早餐店"


def test_same_source_key_is_idempotent(ledger):
    payload = {
        "source_key": "cmb:42:1001:0",
        "account_id": "cmb-credit",
        "kind": "expense",
        "amount_minor": 1890,
        "merchant": "早餐店",
        "note": "尾号1234 消费 早餐店",
        "occurred_at": "2026-09-06T08:30:00+08:00",
    }

    first = ledger.create_automation_transaction(payload)
    second = ledger.create_automation_transaction(payload)

    assert first["id"] == second["id"]
    assert ledger.list_transactions({})["total"] == 1


def test_manual_create_and_update_are_audited(ledger):
    created = ledger.create_manual_transaction(
        {
            "account_id": "cash",
            "kind": "expense",
            "amount": "32.00",
            "merchant": "书店",
            "occurred_at": "2026-09-05T18:00:00+08:00",
        },
        actor="owner",
    )
    updated = ledger.update_transaction(
        created["id"],
        {"category_id": "culture", "review_state": "confirmed"},
        actor="owner",
    )

    assert updated["category_id"] == "culture"
    assert updated["review_state"] == "confirmed"
    audit = ledger.list_audit(created["id"])
    assert [entry["action"] for entry in audit] == ["created", "updated"]
    assert audit[-1]["before"]["category_id"] is None
    assert audit[-1]["after"]["category_id"] == "culture"


def test_dashboard_treats_refunds_as_inflow(ledger):
    base = {
        "account_id": "cash",
        "merchant": "测试商户",
        "occurred_at": "2026-09-06T08:30:00+08:00",
    }
    ledger.create_manual_transaction(
        {**base, "kind": "expense", "amount": "100.00"}, actor="owner"
    )
    ledger.create_manual_transaction(
        {**base, "kind": "income", "amount": "250.00"}, actor="owner"
    )
    ledger.create_manual_transaction(
        {**base, "kind": "refund", "amount": "20.00"}, actor="owner"
    )

    summary = ledger.dashboard("2026-09")

    assert summary["expense_minor"] == 10000
    assert summary["income_minor"] == 27000
    assert summary["net_minor"] == 17000


def test_transaction_filters_are_parameterized_and_paginated(ledger):
    for index in range(28):
        ledger.create_manual_transaction(
            {
                "account_id": "cash",
                "kind": "expense",
                "amount": "1.00",
                "merchant": f"早餐店 {index}",
                "occurred_at": datetime(2026, 9, 1, 8, index % 60).isoformat(),
            },
            actor="owner",
        )

    first_page = ledger.list_transactions({"query": "早餐店", "page": 1})
    second_page = ledger.list_transactions({"query": "早餐店", "page": 2})
    injection = ledger.list_transactions({"query": "%' OR 1=1 --"})

    assert first_page["total"] == 28
    assert len(first_page["items"]) == 25
    assert len(second_page["items"]) == 3
    assert injection["total"] == 0
