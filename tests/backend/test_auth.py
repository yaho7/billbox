from __future__ import annotations


def test_signed_session_round_trip_and_tamper_rejection():
    from billbox.auth import SessionManager

    manager = SessionManager("s" * 32, ttl_seconds=3600, clock=lambda: 1000)
    token, session = manager.create()
    replacement = "x" if token[-1] != "x" else "y"

    assert manager.verify(token) == session
    assert manager.verify(f"{token[:-1]}{replacement}") is None


def test_expired_session_is_rejected():
    from billbox.auth import SessionManager

    current = [1000]
    manager = SessionManager("s" * 32, ttl_seconds=60, clock=lambda: current[0])
    token, _ = manager.create()
    current[0] = 1061

    assert manager.verify(token) is None


def test_login_sets_http_only_strict_cookie(client):
    response = client.post(
        "/api/auth/login", json={"password": "correct horse battery staple"}
    )

    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_wrong_password_does_not_create_session(client):
    response = client.post("/api/auth/login", json={"password": "wrong"})

    assert response.status_code == 401
    assert "密码" in response.json()["detail"]
    assert client.get("/api/session").json() == {"authenticated": False}


def test_logout_clears_session(authenticated_client):
    response = authenticated_client.post("/api/auth/logout")

    assert response.status_code == 204
    assert authenticated_client.get("/api/session").json() == {
        "authenticated": False
    }
