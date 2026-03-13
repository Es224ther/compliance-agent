"""Configures structured JSON logging for the application."""

from __future__ import annotations

import json
import logging
from typing import Any

_LOGGER = logging.getLogger("compliance_agent")
if not _LOGGER.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    _LOGGER.addHandler(handler)
_LOGGER.setLevel(logging.INFO)


def get_logger() -> logging.Logger:
    return _LOGGER


def log_json_event(payload: dict[str, Any]) -> None:
    _LOGGER.info(json.dumps(payload, ensure_ascii=False))
