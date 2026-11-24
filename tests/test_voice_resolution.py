"""Voice resolution tests: API success, read-only SQLite fallback, fail-loud.

Covers the resolution contract: API-first, offline/dry-run never touches the
network, unknown keys never fall back to a default voice, and the store is
opened strictly read-only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from zolai_tts.voice_lookup import (
    VoiceLookupError,
    VoiceNotFoundError,
    resolve_voice,
)


@pytest.fixture()
def voice_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "tts.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE tts_voices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voice_key TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL,
            provider_voice_id TEXT NOT NULL,
            style_default TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            legal_status TEXT NOT NULL DEFAULT 'unverified',
            legal_notes TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        INSERT INTO tts_voices (voice_key, provider, provider_voice_id,
                                style_default, is_active, legal_status)
        VALUES ('seed-voice-1', 'openrouter', 'heygen-default-1', 'narration',
                1, 'unverified');
        INSERT INTO tts_voices (voice_key, provider, provider_voice_id,
                                is_active, legal_status)
        VALUES ('retired', 'openrouter', 'heygen-old', 0, 'unverified');
        """
    )
    conn.commit()
    conn.close()
    return db_path


class TestApiSuccess:
    def test_api_first_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self) -> bytes:
                import json

                return json.dumps(
                    {
                        "voice_key": "seed-voice-1",
                        "provider": "openrouter",
                        "provider_voice_id": "heygen-default-1",
                        "style_default": "narration",
                        "is_active": True,
                        "legal_status": "verified",
                        "legal_notes": None,
                    }
                ).encode()

        seen: list[str] = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            seen.append(request.full_url)
            return FakeResponse()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        voice = resolve_voice("seed-voice-1", api_base="http://api.test")
        assert voice.source == "api"
        assert voice.provider_voice_id == "heygen-default-1"
        assert voice.legal_status == "verified"
        assert seen == ["http://api.test/api/v1/tts/voices/seed-voice-1"]

    def test_api_404_fails_loudly_no_fallback(
        self, monkeypatch: pytest.MonkeyPatch, voice_db: Path
    ) -> None:
        import urllib.error
        import urllib.request

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        # Even with a store present, an authoritative 404 must not silently
        # resolve to anything else.
        with pytest.raises(VoiceNotFoundError, match="unknown voice_key"):
            resolve_voice("seed-voice-1", api_base="http://api.test", db_path=str(voice_db))


class TestSqliteFallback:
    def test_fallback_when_api_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, voice_db: Path
    ) -> None:
        import urllib.error
        import urllib.request

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        voice = resolve_voice("seed-voice-1", api_base="http://api.test", db_path=str(voice_db))
        assert voice.source == "sqlite"
        assert voice.legal_status == "unverified"
        assert voice.provider == "openrouter"

    def test_offline_skips_api_entirely(
        self, monkeypatch: pytest.MonkeyPatch, voice_db: Path
    ) -> None:
        def banned(*_a: object, **_k: object) -> object:
            raise AssertionError("offline resolution must not touch the network")

        monkeypatch.setattr("urllib.request.urlopen", banned)
        voice = resolve_voice("seed-voice-1", offline=True, db_path=str(voice_db))
        assert voice.source == "sqlite"

    def test_store_is_opened_read_only(
        self, monkeypatch: pytest.MonkeyPatch, voice_db: Path
    ) -> None:
        opened: list[str] = []
        real_connect = sqlite3.connect

        def spy_connect(target, *args, **kwargs):  # noqa: ANN001
            opened.append(str(target))
            return real_connect(target, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", spy_connect)
        resolve_voice("seed-voice-1", offline=True, db_path=str(voice_db))
        assert opened, "expected a sqlite connection"
        assert all("mode=ro" in uri for uri in opened)

    def test_env_var_fallback_path(self, monkeypatch: pytest.MonkeyPatch, voice_db: Path) -> None:
        monkeypatch.setenv("ZOLAI_DB_PATH", str(voice_db))
        voice = resolve_voice("seed-voice-1", offline=True)
        assert voice.voice_key == "seed-voice-1"

    def test_missing_table_treated_as_no_store(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.db"
        sqlite3.connect(empty).close()
        with pytest.raises(VoiceLookupError, match="offline resolution failed"):
            resolve_voice("seed-voice-1", offline=True, db_path=str(empty))


class TestFailLoud:
    def test_unknown_key_raises_not_found(
        self, monkeypatch: pytest.MonkeyPatch, voice_db: Path
    ) -> None:
        def banned(*_a: object, **_k: object) -> object:
            raise AssertionError("no network expected")

        monkeypatch.setattr("urllib.request.urlopen", banned)
        with pytest.raises(VoiceNotFoundError):
            resolve_voice("nope", offline=True, db_path=str(voice_db))

    def test_missing_key_never_defaults(self) -> None:
        for empty in (None, "", "   "):
            with pytest.raises(VoiceNotFoundError, match="voice_key is required"):
                resolve_voice(empty, offline=True, db_path="/nonexistent.db")

    def test_inactive_voice_rejected(self, voice_db: Path) -> None:
        with pytest.raises(VoiceNotFoundError, match="inactive"):
            resolve_voice("retired", offline=True, db_path=str(voice_db))

    def test_api_down_and_no_store_is_loud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error
        import urllib.request

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            raise urllib.error.URLError("down")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(VoiceLookupError, match="unreachable"):
            resolve_voice("seed-voice-1", api_base="http://api.test", db_path="/nonexistent.db")
