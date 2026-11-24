"""Batch TTS tests: payload fidelity, dry-run isolation, chunking, PCM/WAV.

No network, no API keys, no live calls. Audio handling is verified against
in-memory byte fixtures; dry-run must create no files and touch no sockets.
"""

from __future__ import annotations

import io
import json
import sqlite3
import wave
from pathlib import Path

import pytest

from zolai_tts import batch
from zolai_tts.batch import (
    MAX_CHUNK_CHARS,
    PROVIDERS,
    build_payload,
    chunk_text,
    detect_audio_format,
    load_items,
    merge_wav_parts,
    pcm_to_wav,
    plan_for,
    run_batch,
    spec_for,
    write_audio_bytes,
)
from zolai_tts.data.provenance import PublishBlockedError, assert_publishable, sha256_text
from zolai_tts.voice_lookup import VoiceLookupError, VoiceNotFoundError, resolve_voice

OPENROUTER = PROVIDERS["openrouter"]
FISH = PROVIDERS["fish-audio"]
GEMINI = PROVIDERS["gemini"]

SAMPLE_TEXT = "Pasian in leitung a piangsak hi."
TAGGED_TEXT = "Hello /ðɛər/, this is tricky."


@pytest.fixture()
def voice_db(tmp_path: Path) -> Path:
    """Read-only-usable store with one active, unverified voice row."""
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
        VALUES ('inactive-voice', 'openrouter', 'heygen-default-2', 0, 'unverified');
        """
    )
    conn.commit()
    conn.close()
    return db_path


def make_args(input_path: Path, **overrides: object):
    class Args:
        pass

    args = Args()
    args.input = str(input_path)
    args.voice_key = "seed-voice-1"
    args.seed = 7
    args.live = False
    args.out_dir = str(overrides.get("out_dir", "artifacts"))
    args.provider = str(overrides.get("provider", "openrouter"))
    args.model = overrides.get("model")
    return args


def write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Provider / model selection matrix
# ---------------------------------------------------------------------------


class TestProviderSelection:
    def test_default_provider_is_openrouter_heygen(self) -> None:
        assert OPENROUTER.default_model == "heygen/heygen-voice-1-turbo:free"
        assert OPENROUTER.transport == "openai_compat"
        assert FISH.default_model == "fish-audio/s2.1-pro-free:free"
        assert FISH.config_provider == "openrouter"  # same SDK path + env key
        assert GEMINI.transport == "gemini"
        assert OPENROUTER.production_guarantee is False
        assert FISH.production_guarantee is False

    def test_cli_parser_defaults(self) -> None:
        from zolai_tts.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["batch", "--input", "s.jsonl"])
        assert args.provider == "openrouter"  # unchanged default
        assert args.model is None  # resolves to heygen free model
        assert args.live is False  # dry-run default
        assert args.out_dir == "artifacts"
        assert args.seed == 0

    def test_cli_parser_fish_audio_and_model_override(self) -> None:
        from zolai_tts.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["batch", "--input", "s.jsonl", "--provider", "fish-audio",
             "--model", "fish-audio/s2.1-pro-free:free"]
        )
        assert args.provider == "fish-audio"
        assert spec_for("fish-audio").default_model == "fish-audio/s2.1-pro-free:free"
        assert args.model == "fish-audio/s2.1-pro-free:free"

    def test_unknown_provider_fails_loudly(self) -> None:
        with pytest.raises(Exception, match="unknown provider"):
            spec_for("cleverbot")


# ---------------------------------------------------------------------------
# Payload fidelity
# ---------------------------------------------------------------------------


class TestPayloadFidelity:
    def test_openrouter_payload_is_verbatim_no_tags(self) -> None:
        body = build_payload(
            TAGGED_TEXT, spec=OPENROUTER, model=OPENROUTER.default_model,
            voice_id="heygen-default-1", tags=["whispered"], style="soft",
        )
        assert body["input"] == TAGGED_TEXT  # verbatim, tags NOT injected
        assert body["model"] == "heygen/heygen-voice-1-turbo:free"
        assert body["voice"] == "heygen-default-1"
        assert "<whispered>" not in body["input"]

    def test_fish_audio_payload_uses_free_model_id(self) -> None:
        body = build_payload(
            SAMPLE_TEXT, spec=FISH, model=FISH.default_model,
            voice_id="heygen-default-1", tags=[], style=None,
        )
        assert body["model"] == "fish-audio/s2.1-pro-free:free"
        assert body["input"] == SAMPLE_TEXT

    def test_gemini_payload_applies_tags_ipa_and_style(self) -> None:
        body = build_payload(
            TAGGED_TEXT, spec=GEMINI, model="gemini-3.8-flash-tts",
            voice_id="Kore", tags=["point-in-time"], style="calm",
        )
        text = body["input"][0]["content"][0]["text"]
        assert text.endswith(TAGGED_TEXT)  # source text verbatim at the end
        assert "<point-in-time>" in text
        assert "/ðɛər/" in text  # IPA markers preserved verbatim
        assert body["speech_metadata"] == {"style": "calm"}
        assert body["model"] == "gemini-3.8-flash-tts"

    def test_tags_applied_flag_per_provider(self) -> None:
        assert OPENROUTER.tags_applied is False
        assert FISH.tags_applied is False
        assert GEMINI.tags_applied is True


# ---------------------------------------------------------------------------
# Dry-run: no network, no files, warnings
# ---------------------------------------------------------------------------


class TestDryRun:
    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def banned(*_a: object, **_k: object) -> object:
            raise AssertionError("dry-run must not touch the network")

        import socket

        monkeypatch.setattr(socket, "socket", banned)
        monkeypatch.setattr(socket, "create_connection", banned)

    def test_dry_run_writes_no_files_and_prints_plan(
        self, tmp_path: Path, voice_db: Path, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ZOLAI_DB_PATH", str(voice_db))
        input_path = write_jsonl(
            tmp_path / "s.jsonl",
            [{"id": "a1", "text": SAMPLE_TEXT, "tags": ["x"], "style": "calm"}],
        )
        code = run_batch(make_args(input_path))

        assert code == 0
        plan = json.loads(capsys.readouterr().out)
        assert plan["mode"] == "dry-run"
        assert plan["provider"] == "openrouter"  # unchanged default
        assert plan["model"] == "heygen/heygen-voice-1-turbo:free"
        assert plan["voice"]["voice_key"] == "seed-voice-1"
        assert plan["tags_applied"] is False
        assert plan["production_guarantee"] is False
        assert plan["network"] is False
        assert plan["publishable"] is False  # legal_status unverified ⇒ blocked
        assert any("production_guarantee=false" in w for w in plan["warnings"])
        assert any("no production latency or availability guarantees" in w
                   for w in plan["warnings"])
        # No files created: no artifacts/, no manifests/.
        assert not (tmp_path / "artifacts").exists()
        assert not (tmp_path / "manifests").exists()

    def test_dry_run_fish_audio_warns_no_production_guarantee(
        self, tmp_path: Path, voice_db: Path, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ZOLAI_DB_PATH", str(voice_db))
        # fish-audio voice row for this provider
        conn = sqlite3.connect(voice_db)
        conn.execute(
            "INSERT INTO tts_voices (voice_key, provider, provider_voice_id, "
            "is_active, legal_status) VALUES ('fish-voice', 'fish-audio', "
            "'heygen-default-1', 1, 'unverified')"
        )
        conn.commit()
        conn.close()
        input_path = write_jsonl(tmp_path / "s.jsonl", [{"text": SAMPLE_TEXT}])
        args = make_args(input_path, provider="fish-audio")
        args.voice_key = "fish-voice"
        assert run_batch(args) == 0

        plan = json.loads(capsys.readouterr().out)
        assert plan["model"] == "fish-audio/s2.1-pro-free:free"
        assert plan["production_guarantee"] is False
        assert any("production_guarantee=false" in w for w in plan["warnings"])
        assert any("no production latency or availability guarantees" in w
                   for w in plan["warnings"])
        assert plan["publishable"] is False

    def test_unknown_voice_fails_loudly_no_default(
        self, tmp_path: Path, voice_db: Path, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ZOLAI_DB_PATH", str(voice_db))
        input_path = write_jsonl(tmp_path / "s.jsonl", [{"text": SAMPLE_TEXT}])
        args = make_args(input_path)
        args.voice_key = "does-not-exist"
        assert run_batch(args) == 2
        err = capsys.readouterr().err
        assert "unknown voice_key" in err or "voice" in err

    def test_missing_voice_key_fails_loudly(
        self, tmp_path: Path, voice_db: Path, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ZOLAI_DB_PATH", str(voice_db))
        input_path = write_jsonl(tmp_path / "s.jsonl", [{"text": SAMPLE_TEXT}])
        args = make_args(input_path)
        args.voice_key = None
        assert run_batch(args) == 2
        assert "voice_key is required" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Chunking (5,000-char limit) + PCM/WAV handling
# ---------------------------------------------------------------------------


class TestChunking:
    def test_short_text_single_chunk(self) -> None:
        assert chunk_text(SAMPLE_TEXT) == [SAMPLE_TEXT]

    def test_long_text_chunked_at_5000(self) -> None:
        text = " ".join(f"word{i}" for i in range(2000))  # > 5,000 chars
        chunks = chunk_text(text)
        assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
        assert len(chunks) > 1
        # No words lost: rejoin reproduces the source wording.
        assert " ".join(chunks) == text

    def test_exact_limit_not_split(self) -> None:
        text = "a" * MAX_CHUNK_CHARS
        assert chunk_text(text) == [text]

    def test_overlong_token_hard_split(self) -> None:
        text = "z" * (MAX_CHUNK_CHARS + 10)
        chunks = chunk_text(text)
        assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
        assert "".join(chunks) == text


class TestAudioHandling:
    def test_detect_formats(self) -> None:
        assert detect_audio_format(b"RIFF\x00\x00\x00\x00WAVE") == "wav"
        assert detect_audio_format(b"ID3\x04") == "mp3"
        assert detect_audio_format(b"\xff\xfb\x90\x00") == "mp3"
        assert detect_audio_format(b"\x01\x02\x03\x04") == "pcm"

    def test_pcm_wrapped_as_44100_mono_wav(self) -> None:
        pcm = b"\x01\x02" * 4410  # 0.1 s of 16-bit mono
        wav_bytes = pcm_to_wav(pcm)
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            assert wav.getframerate() == 44_100
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.readframes(wav.getnframes()) == pcm

    def test_write_audio_wraps_pcm_and_passes_wav(
        self, tmp_path: Path
    ) -> None:
        raw = b"\x03\x04" * 100
        path, fmt = write_audio_bytes(raw, tmp_path / "a1")
        assert fmt == "pcm"
        assert path.suffix == ".wav"
        assert detect_audio_format(path.read_bytes()) == "wav"

        riff = b"RIFF" + b"\x00" * 40
        path2, fmt2 = write_audio_bytes(riff, tmp_path / "a2")
        assert fmt2 == "wav"
        assert path2.read_bytes() == riff  # passthrough, no re-encode

        mp3 = b"ID3" + b"\x00" * 20
        path3, fmt3 = write_audio_bytes(mp3, tmp_path / "a3")
        assert fmt3 == "mp3"
        assert path3.suffix == ".mp3"
        assert path3.read_bytes() == mp3

    def test_merge_wav_parts(self) -> None:
        a = pcm_to_wav(b"\x01\x02" * 10)
        b = pcm_to_wav(b"\x03\x04" * 10)
        merged = merge_wav_parts([a, b])
        assert merged is not None
        with wave.open(io.BytesIO(merged), "rb") as wav:
            assert wav.getnframes() == 20
        # Mismatched shapes refuse to merge (no silent corruption).
        other = pcm_to_wav(b"\x01\x02" * 10).replace(b"AC\x01", b"8\xac\x00\x00", 1)
        assert merge_wav_parts([a, b"ID3\x00"]) is None
        assert other is not None  # sanity


# ---------------------------------------------------------------------------
# Manifest + publish gate
# ---------------------------------------------------------------------------


class TestManifestAndPublishGate:
    def test_manifest_fields_and_sha256(self, tmp_path: Path) -> None:
        from zolai_tts.data.provenance import build_manifest, write_manifest

        manifest = build_manifest(
            batch_id="abc123", seed=7, provider="openrouter",
            model="heygen/heygen-voice-1-turbo:free", voice_key="seed-voice-1",
            legal_status="unverified",
            items=[{"id": "a1", "text": SAMPLE_TEXT, "sha256": sha256_text(SAMPLE_TEXT),
                    "tags": ["x"], "style": "calm", "audio_path": "artifacts/a1.wav"}],
            input_path="s.jsonl", production_guarantee=False, tags_applied=False,
        )
        assert manifest["schema_version"] == 1
        assert manifest["seed"] == 7
        assert manifest["voice_key"] == "seed-voice-1"
        assert manifest["legal_status"] == "unverified"
        assert manifest["production_guarantee"] is False
        assert manifest["tags_applied"] is False
        assert manifest["owner"] is None and manifest["license"] is None
        out = write_manifest(tmp_path / "m.json", manifest)
        loaded = json.loads(out.read_text())
        assert loaded["items"][0]["sha256"] == sha256_text(SAMPLE_TEXT)

    def test_publish_gate_blocks_unverified(self) -> None:
        with pytest.raises(PublishBlockedError, match="publish blocked"):
            assert_publishable("unverified")
        with pytest.raises(PublishBlockedError):
            assert_publishable(None)
        assert_publishable("verified")  # only verified passes

    def test_plan_reports_publish_blocked(self, voice_db: Path) -> None:
        voice = resolve_voice("seed-voice-1", offline=True, db_path=str(voice_db))
        plan = plan_for(
            items=[{"id": "a1", "text": SAMPLE_TEXT, "tags": [], "style": None}],
            voice=voice, spec=OPENROUTER, model=OPENROUTER.default_model,
            seed=0, input_path="s.jsonl", batch_id="b", audio_dir=Path("artifacts/b"),
            manifest_path=Path("manifests/b.json"),
        )
        assert plan["publishable"] is False
        assert any("publish blocked" in w for w in plan["warnings"])


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------


class TestLoadItems:
    def test_load_valid_jsonl(self, tmp_path: Path) -> None:
        path = write_jsonl(
            tmp_path / "in.jsonl",
            [
                {"id": "x", "text": "one", "tags": ["t"], "style": "s"},
                {"text": "two"},
            ],
        )
        items = load_items(path)
        assert [i["id"] for i in items] == ["x", "item-0002"]
        assert items[1]["tags"] == []

    def test_missing_text_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.jsonl"
        path.write_text('{"id": "x"}\n', encoding="utf-8")
        with pytest.raises(batch.BatchError, match="missing non-empty 'text'"):
            load_items(path)

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        with pytest.raises(batch.BatchError, match="input not found"):
            load_items(tmp_path / "nope.jsonl")

    def test_no_default_voice_error_type(self) -> None:
        with pytest.raises(VoiceNotFoundError, match="voice_key is required"):
            resolve_voice(None, offline=True, db_path="/nonexistent.db")
        with pytest.raises(VoiceLookupError):
            resolve_voice("ghost", offline=True, db_path="/nonexistent.db")
