from __future__ import annotations


def _transaction_payload(**overrides):
    payload = {
        "account_id": "cash",
        "category_id": "food",
        "kind": "expense",
        "amount": "18.90",
        "merchant": "早餐店",
        "note": "豆浆和包子",
        "channel": "现金",
        "occurred_at": "2026-09-06T08:30:00+08:00",
    }
    payload.update(overrides)
    return payload


def test_healthcheck_does_not_require_login(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ledger_requires_login(client):
    response = client.get("/api/dashboard?month=2026-09")

    assert response.status_code == 401


def test_mutation_requires_csrf(authenticated_client):
    response = authenticated_client.post(
        "/api/transactions", json=_transaction_payload()
    )

    assert response.status_code == 403
    assert "刷新" in response.json()["detail"]


def test_manual_transaction_round_trip(authenticated_client):
    created = authenticated_client.post(
        "/api/transactions",
        headers={"X-CSRF-Token": authenticated_client.csrf_token},
        json=_transaction_payload(),
    )

    assert created.status_code == 201
    assert created.json()["amount_minor"] == 1890
    result = authenticated_client.get("/api/transactions?query=早餐店")
    assert result.status_code == 200
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["category_name"] == "餐饮美食"


def test_invalid_transaction_returns_actionable_error(authenticated_client):
    response = authenticated_client.post(
        "/api/transactions",
        headers={"X-CSRF-Token": authenticated_client.csrf_token},
        json=_transaction_payload(amount="0"),
    )

    assert response.status_code == 422


def test_category_correction_is_audited(authenticated_client):
    created = authenticated_client.post(
        "/api/transactions",
        headers={"X-CSRF-Token": authenticated_client.csrf_token},
        json=_transaction_payload(category_id=None),
    ).json()

    updated = authenticated_client.patch(
        f"/api/transactions/{created['id']}",
        headers={"X-CSRF-Token": authenticated_client.csrf_token},
        json={"category_id": "food", "review_state": "confirmed"},
    )

    assert updated.status_code == 200
    assert updated.json()["category_name"] == "餐饮美食"
    assert updated.json()["review_state"] == "confirmed"


def test_dashboard_and_options_are_available_after_login(authenticated_client):
    authenticated_client.post(
        "/api/transactions",
        headers={"X-CSRF-Token": authenticated_client.csrf_token},
        json=_transaction_payload(),
    )

    dashboard = authenticated_client.get("/api/dashboard?month=2026-09")
    options = authenticated_client.get("/api/options")

    assert dashboard.status_code == 200
    assert dashboard.json()["expense_minor"] == 1890
    assert options.status_code == 200
    assert any(item["id"] == "cash" for item in options.json()["accounts"])
    assert any(item["id"] == "food" for item in options.json()["categories"])


def test_invalid_month_and_missing_transaction_return_client_errors(
    authenticated_client,
):
    dashboard = authenticated_client.get("/api/dashboard?month=September")
    update = authenticated_client.patch(
        "/api/transactions/missing",
        headers={"X-CSRF-Token": authenticated_client.csrf_token},
        json={"review_state": "confirmed"},
    )

    assert dashboard.status_code == 422
    assert update.status_code == 404


def test_job_status_is_empty_before_first_run(authenticated_client):
    response = authenticated_client.get("/api/jobs/latest")

    assert response.status_code == 200
    assert response.json() == {"state": "never", "job_name": "mail-ingestion"}


def test_manual_ingestion_reports_missing_mail_configuration(authenticated_client):
    response = authenticated_client.post(
        "/api/jobs/ingest",
        headers={"X-CSRF-Token": authenticated_client.csrf_token},
    )

    assert response.status_code == 503
    assert "邮箱" in response.json()["detail"]
