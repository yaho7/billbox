from __future__ import annotations

from dataclasses import replace
import threading
import time


def test_scheduler_is_disabled_without_mail_credentials(settings):
    from billbox.scheduler import create_scheduler

    assert create_scheduler(settings, lambda: None) is None


def test_scheduler_uses_configured_timezone_and_clock(settings):
    from billbox.scheduler import create_scheduler

    configured = replace(
        settings,
        mail_user="owner@example.com",
        mail_password="secret",
        imap_server="imap.example.com",
        schedule_hour=4,
        schedule_minute=15,
        schedule_timezone="Asia/Shanghai",
    )
    scheduler = create_scheduler(configured, lambda: None)
    job = scheduler.get_job("mail-ingestion")

    assert str(job.trigger.timezone) == "Asia/Shanghai"
    assert "hour='4'" in str(job.trigger)
    assert "minute='15'" in str(job.trigger)


def test_run_controller_rejects_overlapping_runs():
    from billbox.scheduler import RunController

    started = threading.Event()
    release = threading.Event()

    def slow_run():
        started.set()
        release.wait(timeout=2)

    controller = RunController(slow_run)

    assert controller.trigger() is True
    assert started.wait(timeout=1)
    assert controller.trigger() is False
    release.set()
    deadline = time.monotonic() + 1
    while controller.running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert controller.running is False
