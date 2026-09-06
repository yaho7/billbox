from __future__ import annotations

import threading
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from .config import Settings
from .imap_client import ImapClient
from .ingestion import IngestionService
from .ledger import Ledger


class RunController:
    def __init__(self, run: Callable[[], object]):
        self._run = run
        self._lock = threading.Lock()
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._lock.locked()

    def run_blocking(self) -> bool:
        if not self._lock.acquire(blocking=False):
            return False
        try:
            self.last_error = None
            self._run()
            return True
        except Exception as error:
            self.last_error = str(error)
            raise
        finally:
            self._lock.release()

    def trigger(self) -> bool:
        if not self._lock.acquire(blocking=False):
            return False

        def target() -> None:
            try:
                self.last_error = None
                self._run()
            except Exception as error:
                self.last_error = str(error)
            finally:
                self._lock.release()

        threading.Thread(target=target, name="billbox-ingestion", daemon=True).start()
        return True


def create_scheduler(
    settings: Settings, run: Callable[[], object]
) -> BackgroundScheduler | None:
    if not settings.schedule_enabled or not settings.mail_configured:
        return None
    scheduler = BackgroundScheduler(timezone=settings.schedule_timezone)
    scheduler.add_job(
        run,
        "cron",
        id="mail-ingestion",
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
        timezone=settings.schedule_timezone,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=15 * 60,
        replace_existing=True,
    )
    return scheduler


def create_runtime(
    settings: Settings, ledger: Ledger
) -> tuple[RunController | None, BackgroundScheduler | None]:
    if not settings.mail_configured:
        return None, None
    service = IngestionService(
        ledger, mailbox=settings.mail_user, max_emails=settings.max_emails
    )

    def run() -> dict[str, int]:
        client = ImapClient(
            settings.mail_user,
            settings.mail_password,
            settings.imap_server,
            settings.imap_port,
        )
        return service.run(client)

    controller = RunController(run)
    return controller, create_scheduler(settings, controller.run_blocking)
