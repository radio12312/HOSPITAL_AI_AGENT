"""Structured-ish console logging shared by the API, seeding and agents."""

from __future__ import annotations

import logging
import sys

from core.config import settings

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def setup_logging() -> None:
    root = logging.getLogger()
    if any(getattr(h, "_hwa", False) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    handler._hwa = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    for noisy in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"hwa.{name}")
