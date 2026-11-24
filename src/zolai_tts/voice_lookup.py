"""Voice registry resolution: API-first, read-only SQLite fallback.

Resolution order for a ``voice_key``:

1. ``GET {ZOLAI_API_BASE}/api/v1/tts/voices/{voice_key}`` (skipped in
   ``offline`` mode, i.e. CLI dry-run — dry-run never touches the network).
2. Read-only SQLite at ``ZOLAI_DB_PATH`` (``file:...?mode=ro``).

Failures never fall back to a default voice: an unknown key raises
:class:`VoiceNotFoundError`, and an unreachable API *and* missing store raise
:class:`VoiceLookupError`. The caller must fail loudly.

owner/license/consent_ref are intentionally absent here — they live only in
the tracked manifest (see :mod:`zolai_tts.data.provenance`).
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_API_TIMEOUT = 3.0

#: Env var names (presence-checked by the CLI; values never printed).
API_BASE_ENV = "ZOLAI_API_BASE"
DB_PATH_ENV = "ZOLAI_DB_PATH"


class VoiceLookupError(RuntimeError):
    """Voice could not be resolved anywhere (API unreachable + no store)."""


class VoiceNotFoundError(VoiceLookupError):
    """The requested ``voice_key`` does not exist. No default is substituted."""


@dataclass(frozen=True)
class Voice:
    """A resolved voice record (plain values only — JSON/SQLite safe)."""

    voice_key: str
    provider: str
    provider_voice_id: str
    style_default: str | None
    is_active: bool
    legal_status: str
    legal_notes: str | None
    #: Where the record came from: ``"api"`` or ``"sqlite"``.
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "voice_key": self.voice_key,
            "provider": self.provider,
            "provider_voice_id": self.provider_voice_id,
            "style_default": self.style_default,
            "is_active": self.is_active,
            "legal_status": self.legal_status,
            "legal_notes": self.legal_notes,
            "source": self.source,
        }


def _voice_from_mapping(record: dict[str, Any], source: str) -> Voice:
    """Build a :class:`Voice` from an API/DB row; rejects inactive rows."""
    voice_key = str(record.get("voice_key") or "")
    if not voice_key:
        raise VoiceNotFoundError("voice record has no voice_key")
    is_active = bool(record.get("is_active", 1))
    if not is_active:
        raise VoiceNotFoundError(f"voice {voice_key!r} exists but is inactive")
    return Voice(
        voice_key=voice_key,
        provider=str(record.get("provider") or ""),
        provider_voice_id=str(record.get("provider_voice_id") or ""),
        style_default=(str(record["style_default"]) if record.get("style_default") else None),
        is_active=is_active,
        # No silent default: a missing legal_status is recorded as unverified,
        # which the publish gate treats as blocked.
        legal_status=str(record.get("legal_status") or "unverified"),
        legal_notes=(str(record["legal_notes"]) if record.get("legal_notes") else None),
        source=source,
    )


def _api_lookup(voice_key: str, api_base: str, timeout: float) -> Voice:
    """API-first lookup. 404 ⇒ :class:`VoiceNotFoundError`; transport/5xx ⇒ raise
    whatever came in so the caller can fall back."""
    url = f"{api_base.rstrip('/')}/api/v1/tts/voices/{urllib.parse.quote(voice_key)}"
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise VoiceNotFoundError(f"unknown voice_key {voice_key!r}") from exc
        raise  # 5xx / other → caller falls back to the store
    record = payload.get("voice") if isinstance(payload, dict) and "voice" in payload else payload
    if not isinstance(record, dict):
        raise VoiceLookupError(f"unexpected API payload for {voice_key!r}")
    return _voice_from_mapping(record, source="api")


def _db_lookup(voice_key: str, db_path: str) -> Voice | None:
    """Read-only SQLite fallback.

    Returns ``None`` when there is no usable store (no path, missing file, or
    table not migrated). Raises :class:`VoiceNotFoundError` when the store
    exists but has no active row for the key — that is an authoritative miss,
    not a missing store.
    """
    if not db_path or not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT voice_key, provider, provider_voice_id, style_default, "
                "is_active, legal_status, legal_notes "
                "FROM tts_voices WHERE voice_key = ?",
                (voice_key,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None  # table not migrated yet → treat as no store
    finally:
        conn.close()
    if row is None:
        raise VoiceNotFoundError(f"unknown voice_key {voice_key!r}")
    return _voice_from_mapping(dict(row), source="sqlite")


def resolve_voice(
    voice_key: str | None,
    *,
    offline: bool = False,
    api_base: str | None = None,
    db_path: str | None = None,
    timeout: float = DEFAULT_API_TIMEOUT,
) -> Voice:
    """Resolve ``voice_key`` API-first with a read-only SQLite fallback.

    Args:
        voice_key: Registry key. Empty/missing ⇒ :class:`VoiceNotFoundError`
            (there is **no** default voice).
        offline: Skip the API (CLI dry-run: no network).
        api_base: Override ``ZOLAI_API_BASE``.
        db_path: Override ``ZOLAI_DB_PATH``.
        timeout: API timeout in seconds.

    Raises:
        VoiceNotFoundError: unknown or inactive key.
        VoiceLookupError: API unreachable and no usable local store.
    """
    key = (voice_key or "").strip()
    if not key:
        raise VoiceNotFoundError(
            "voice_key is required; zolai-tts refuses to pick a default voice"
        )

    base = (api_base or os.getenv(API_BASE_ENV) or DEFAULT_API_BASE).rstrip("/")
    store = db_path if db_path is not None else (os.getenv(DB_PATH_ENV) or "")

    api_error: Exception | None = None
    if not offline:
        try:
            return _api_lookup(key, base, timeout)
        except VoiceNotFoundError:
            raise
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            api_error = exc

    voice = _db_lookup(key, store)
    if voice is not None:
        return voice

    if api_error is not None:
        raise VoiceLookupError(
            f"voice {key!r}: API {base} unreachable ({api_error}) and no "
            f"read-only store at {DB_PATH_ENV}={store or '<unset>'}"
        ) from api_error
    if offline:
        raise VoiceLookupError(
            f"voice {key!r}: offline resolution failed — no read-only store at "
            f"{DB_PATH_ENV}={store or '<unset>'}"
        )
    raise VoiceNotFoundError(f"unknown voice_key {key!r}")
