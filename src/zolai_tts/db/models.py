"""SQLModel tables for the Zolai-TTS studio.

Portable by construction so the same code runs on SQLite (default, zero-setup)
and PostgreSQL (shared deployments) — switching is a URI change only:

    sqlite:///<store_dir>/studio.db
    postgresql+psycopg://user:pass@host:5432/zolai_tts

Rules that keep both dialects identical:
  * JSON columns (`sa.JSON`) instead of dialect-specific text blobs;
  * timezone-aware UTC datetimes, no SQL date functions in queries;
  * integers/floats/booleans only — no SERIAL/IDENTITY assumptions (ids are
    strings generated in Python);
  * relationships declared but queried through explicit selects, so no dialect
    specific eager-loading behaviour leaks into the API.

Secrets are never stored here: API keys live in the environment or in the
in-memory session store (`zolai_tts.secrets`).
"""

import json
from datetime import UTC, datetime
from typing import Any, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    """Timezone-aware UTC now (SQLModel's DateTime requires tz info)."""
    return datetime.now(UTC)


def _json_default() -> str:
    return "{}"


class Provider(SQLModel, table=True):
    __tablename__ = "providers"

    name: str = Field(primary_key=True)
    label: str = ""
    hosted: bool = False
    voice_kind: str = Field(
        default="name", sa_column=sa.Column("voice_kind", sa.String, nullable=False)
    )
    note: str = ""
    updated_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)

    # Catalog rows follow the provider; history rows (runs/usage) deliberately
    # keep only a plain `provider_name` string so deleting a catalog row can
    # never erase recorded output.
    models: list["Model"] = Relationship(back_populates="provider", cascade_delete=True)
    voices: list["Voice"] = Relationship(back_populates="provider", cascade_delete=True)


class Model(SQLModel, table=True):
    __tablename__ = "models"

    provider_name: str = Field(foreign_key="providers.name", primary_key=True)
    slug: str = Field(primary_key=True)
    title: str = ""
    tier: str = "unknown"  # free | paid | unknown
    formats: str = Field(default="[]", sa_column=sa.Column("formats", sa.Text, nullable=False))
    pricing: str = Field(default="{}", sa_column=sa.Column("pricing", sa.Text, nullable=False))
    context_length: int | None = None
    source: str = "fallback"  # live | fallback | local
    updated_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)

    provider: Provider | None = Relationship(back_populates="models")

    def formats_list(self) -> list[str]:
        return _loads(self.formats, [])

    def pricing_dict(self) -> dict[str, Any]:
        return _loads(self.pricing, {})


class Voice(SQLModel, table=True):
    __tablename__ = "voices"

    id: str = Field(primary_key=True)
    provider_name: str = Field(foreign_key="providers.name", index=True)
    model_slug: str = ""
    slug: str = Field(index=True)
    label: str = ""
    origin: str = "provider"  # provider | local | contribution
    path: str | None = None
    gender: str = ""
    locale: str = ""
    preview_key: str | None = None
    contributed: bool = False
    updated_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)

    provider: Provider | None = Relationship(back_populates="voices")


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    # Deliberately not a foreign key: history must survive catalog churn.
    provider_name: str = Field(index=True)
    model_slug: str = ""
    voice_slug: str = ""
    language: str = "ted"
    text: str = ""
    status: str = "ok"  # ok | failed
    error: str | None = None
    audio_format: str | None = Field(default=None, sa_column=sa.Column("format", sa.String))
    storage_backend: str = "local"
    object_key: str | None = None
    local_path: str | None = None
    bytes: int | None = None
    duration_seconds: float | None = None
    elapsed_seconds: float | None = None
    dry_run: bool = False
    cost_usd: float | None = None
    characters: int | None = None
    tier: str = "unknown"  # free | paid | free-local | unknown (at run time)
    metadata_json: str = Field(
        default="{}", sa_column=sa.Column("metadata", sa.Text, nullable=False)
    )

    reviews: list["Review"] = Relationship(back_populates="run", cascade_delete=True)

    def meta(self) -> dict[str, Any]:
        return _loads(self.metadata_json, {})


class Recording(SQLModel, table=True):
    __tablename__ = "recordings"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    source: str = "upload"  # upload | mic
    provider_name: str = ""
    model_slug: str = ""
    voice_slug: str = ""
    note: str = ""
    mime: str = ""
    audio_format: str = Field(default="", sa_column=sa.Column("format", sa.String, nullable=False))
    bytes: int = 0
    duration_seconds: float | None = None
    storage_backend: str = "local"
    object_key: str = ""
    local_path: str | None = None

    contribution: Optional["Contribution"] = Relationship(back_populates="recording")


class Contribution(SQLModel, table=True):
    __tablename__ = "contributions"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    speaker_alias: str = "anonymous"
    consent: bool = False
    license: str = ""
    language: str = "ted"
    prompt: str = ""
    mic_device: str = ""
    note: str = ""
    status: str = Field(default="new", index=True)  # new | reviewed | accepted | rejected
    recording_id: str = Field(foreign_key="recordings.id", unique=True)
    storage_backend: str = "local"
    object_key: str = ""
    local_path: str | None = None
    bytes: int = 0
    audio_format: str = Field(default="", sa_column=sa.Column("format", sa.String, nullable=False))
    duration_seconds: float | None = None

    recording: Recording | None = Relationship(back_populates="contribution")


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    run_id: str = Field(foreign_key="runs.id", index=True)
    verdict: str = "maybe"  # pass | fail | maybe
    rating: int | None = None
    artifacts: str = Field(default="[]", sa_column=sa.Column("artifacts", sa.Text, nullable=False))
    note: str = ""
    reviewer: str = ""

    run: Run | None = Relationship(back_populates="reviews")

    def artifacts_list(self) -> list[str]:
        return _loads(self.artifacts, [])


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value: str = Field(default="null", sa_column=sa.Column("value", sa.Text, nullable=False))
    updated_at: datetime = Field(default_factory=utcnow)


class UsageEvent(SQLModel, table=True):
    __tablename__ = "usage_events"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    # Deliberately not a foreign key: history must survive catalog churn.
    provider_name: str = Field(index=True)
    model_slug: str = ""
    tier: str = "unknown"
    characters: int = 0
    audio_seconds: float = 0.0
    cost_usd: float = 0.0
    run_id: str | None = None


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def dumps(value: Any) -> str:
    """Public JSON encoder used by the repository layer."""
    return _dumps(value)


__all__ = [
    "Contribution",
    "Model",
    "Provider",
    "Recording",
    "Review",
    "Run",
    "Setting",
    "SQLModel",
    "UsageEvent",
    "Voice",
    "dumps",
    "utcnow",
]
