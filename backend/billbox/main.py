from __future__ import annotations

from .api import create_app
from .config import Settings


def create_application():
    return create_app(Settings.from_env())
