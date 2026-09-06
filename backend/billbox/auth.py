from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import hmac
import json
import secrets
import time


def _b64encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(f"{value}{padding}")


@dataclass(frozen=True, slots=True)
class Session:
    expires_at: int
    csrf_token: str


class SessionManager:
    cookie_name = "billbox_session"

    def __init__(
        self,
        secret: str,
        *,
        ttl_seconds: int,
        clock: Callable[[], float] = time.time,
    ):
        if len(secret) < 32:
            raise ValueError("session secret must contain at least 32 characters")
        self._secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds
        self._clock = clock

    def create(self) -> tuple[str, Session]:
        session = Session(
            expires_at=int(self._clock()) + self.ttl_seconds,
            csrf_token=secrets.token_urlsafe(32),
        )
        payload = _b64encode(
            json.dumps(
                {"exp": session.expires_at, "csrf": session.csrf_token},
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        signature = _b64encode(
            hmac.new(self._secret, payload.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{payload}.{signature}", session

    def verify(self, token: str | None) -> Session | None:
        if not token:
            return None
        try:
            payload, supplied_signature = token.split(".", 1)
            expected_signature = _b64encode(
                hmac.new(
                    self._secret, payload.encode("ascii"), hashlib.sha256
                ).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return None
            decoded = json.loads(_b64decode(payload))
            session = Session(
                expires_at=int(decoded["exp"]),
                csrf_token=str(decoded["csrf"]),
            )
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None
        if session.expires_at <= int(self._clock()):
            return None
        return session


class LoginAttemptLimiter:
    def __init__(
        self,
        *,
        limit: int = 5,
        window_seconds: int = 5 * 60,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def is_limited(self, key: str) -> bool:
        now = self._clock()
        active = [stamp for stamp in self._attempts[key] if now - stamp < self._window]
        self._attempts[key] = active
        return len(active) >= self._limit

    def record_failure(self, key: str) -> None:
        self._attempts[key].append(self._clock())

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)
