"""Studio data layer (SQLModel).

Default engine is SQLite (no setup, offline-friendly); PostgreSQL is a URI
change away (`ZOLAI_TTS_DB_URL=postgresql://…`) with no code change.
"""

from __future__ import annotations

from .engine import Database, dialect_of, get_database, reset_database, resolve_database_url
from .models import (
    Contribution,
    Model,
    Provider,
    Recording,
    Review,
    Run,
    Setting,
    UsageEvent,
    Voice,
)
from .repository import Repository, new_id

__all__ = [
    "Contribution",
    "Database",
    "Model",
    "Provider",
    "Recording",
    "Repository",
    "Review",
    "Run",
    "Setting",
    "UsageEvent",
    "Voice",
    "dialect_of",
    "get_database",
    "new_id",
    "reset_database",
    "resolve_database_url",
]


def repository(url: str | None = None) -> Repository:
    """Convenience: a Repository bound to the process-wide database."""
    return Repository(get_database(url))
