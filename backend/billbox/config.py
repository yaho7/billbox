from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _as_bool(value: str, *, default: bool) -> bool:
    if not value:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    migrations_dir: Path
    frontend_dist: Path
    app_password: str
    session_secret: str
    session_cookie_secure: bool = True
    session_ttl_seconds: int = 12 * 60 * 60
    mail_user: str = ""
    mail_password: str = ""
    imap_server: str = ""
    imap_port: int = 993
    max_emails: int = 50
    schedule_enabled: bool = True
    schedule_hour: int = 3
    schedule_minute: int = 30
    schedule_timezone: str = "Asia/Shanghai"

    def __post_init__(self) -> None:
        if not self.app_password:
            raise ValueError("APP_PASSWORD is required")
        if len(self.session_secret) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        if self.session_ttl_seconds < 300:
            raise ValueError("SESSION_TTL_SECONDS must be at least 300")
        if not 1 <= self.imap_port <= 65535:
            raise ValueError("IMAP_PORT must be between 1 and 65535")
        if self.max_emails < 1:
            raise ValueError("MAX_EMAILS must be positive")
        if not 0 <= self.schedule_hour <= 23:
            raise ValueError("SCHEDULE_HOUR must be between 0 and 23")
        if not 0 <= self.schedule_minute <= 59:
            raise ValueError("SCHEDULE_MINUTE must be between 0 and 59")

    @property
    def mail_configured(self) -> bool:
        return bool(self.mail_user and self.mail_password and self.imap_server)

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parents[2]
        database_path = Path(os.getenv("DATABASE_PATH", "/data/billbox.db"))
        return cls(
            database_path=database_path,
            migrations_dir=Path(os.getenv("MIGRATIONS_DIR", root / "migrations")),
            frontend_dist=Path(os.getenv("FRONTEND_DIST", root / "frontend" / "dist")),
            app_password=os.getenv("APP_PASSWORD", ""),
            session_secret=os.getenv("SESSION_SECRET", ""),
            session_cookie_secure=_as_bool(
                os.getenv("SESSION_COOKIE_SECURE", "true"), default=True
            ),
            session_ttl_seconds=int(
                os.getenv("SESSION_TTL_SECONDS", str(12 * 60 * 60))
            ),
            mail_user=os.getenv("MAIL_USER", "").strip(),
            mail_password=os.getenv("MAIL_PASSWORD", "").strip(),
            imap_server=os.getenv("IMAP_SERVER", "").strip(),
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            max_emails=int(os.getenv("MAX_EMAILS", "50")),
            schedule_enabled=_as_bool(
                os.getenv("SCHEDULE_ENABLED", "true"), default=True
            ),
            schedule_hour=int(os.getenv("SCHEDULE_HOUR", "3")),
            schedule_minute=int(os.getenv("SCHEDULE_MINUTE", "30")),
            schedule_timezone=os.getenv(
                "SCHEDULE_TIMEZONE", "Asia/Shanghai"
            ).strip(),
        )
