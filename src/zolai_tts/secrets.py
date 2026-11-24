"""In-memory session secrets. Nothing here is ever written to disk or to the DB.

The studio runs without an auth layer (localhost, single user), so keys live in
the API process for the session and fall back to the environment. Clearing the
session, restarting the server, or `zolai-tts ui stop` wipes them.
"""

from __future__ import annotations

import os
import threading
from typing import Any

_ALLOWED_ENV_NAMES = frozenset(
    {
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "ZOLAI_TTS_R2_BUCKET",
        "ZOLAI_TTS_R2_ACCOUNT_ID",
        "ZOLAI_TTS_R2_ACCESS_KEY_ID",
        "ZOLAI_TTS_R2_SECRET_ACCESS_KEY",
        "ZOLAI_TTS_R2_REGION",
        "ZOLAI_TTS_R2_ENDPOINT_URL",
    }
)

_lock = threading.Lock()
_session: dict[str, str] = {}

STATUS_KEYS = (
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "ZOLAI_TTS_R2_BUCKET",
    "ZOLAI_TTS_R2_ACCOUNT_ID",
    "ZOLAI_TTS_R2_ACCESS_KEY_ID",
    "ZOLAI_TTS_R2_SECRET_ACCESS_KEY",
)


def set_secret(name: str, value: str) -> None:
    """Store a session secret. Unknown names are rejected (no env pollution)."""
    if name not in _ALLOWED_ENV_NAMES:
        raise ValueError(f"Secret name is not settable: {name}")
    cleaned = (value or "").strip()
    with _lock:
        if cleaned:
            _session[name] = cleaned
        else:
            _session.pop(name, None)


def get_secret(name: str) -> str | None:
    with _lock:
        if name in _session:
            return _session[name]
    return os.getenv(name) or None


def resolve(names: tuple[str, ...]) -> tuple[str | None, str]:
    """Return (value, source) where source is 'session' or 'environment'."""
    with _lock:
        for name in names:
            if _session.get(name):
                return _session[name], "session"
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value, "environment"
    return None, "missing"


def clear(name: str | None = None) -> None:
    with _lock:
        if name:
            _session.pop(name, None)
        else:
            _session.clear()


def status() -> dict[str, Any]:
    """Masked presence report — never the values."""
    with _lock:
        snapshot = dict(_session)
    out: dict[str, dict[str, Any]] = {}
    for key in STATUS_KEYS:
        session_value = snapshot.get(key)
        env_value = os.getenv(key, "").strip()
        value = session_value or env_value
        out[key] = {
            "present": bool(value),
            "source": "session" if session_value else ("environment" if env_value else "missing"),
            "hint": _hint(key, value),
        }
    return {"secrets": out, "session_count": len(snapshot)}


def _hint(name: str, value: str) -> str:
    if not value:
        return ""
    if "KEY" in name or "SECRET" in name:
        return f"{value[:3]}***{value[-3:]}" if len(value) > 10 else "***"
    return value if len(value) <= 64 else f"{value[:60]}***"
