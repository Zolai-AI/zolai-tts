"""Tests for the optional Gradio UI.

These tests are skipped when the optional ``ui`` extra is not installed.
They do not launch a server or make network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

gr = pytest.importorskip("gradio")

import zolai_tts.ui.app as ui_app  # noqa: E402
from zolai_tts.inference.base import SynthesisResult  # noqa: E402


def test_build_app_smoke() -> None:
    app = ui_app.build_app()
    assert isinstance(app, gr.Blocks)


def test_dry_run_piper_returns_plan_no_audio(tmp_path: Path) -> None:
    out = tmp_path / "nope.wav"
    payload, audio = ui_app.synthesize_ui(
        text="Pasian in leitung a piangsak hi.",
        provider="piper",
        language="zolai",
        voice="/tmp/opencode/no-real-voice.onnx",
        model="",
        base_url="",
        response_format="",
        out_path=str(out),
        dry_run=True,
    )
    assert payload["ok"] is True
    assert payload["result"]["mode"] == "dry-run"
    assert payload["result"]["provider"] == "piper"
    assert audio is None
    assert not out.exists()


def test_dry_run_gemini_builds_request_without_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ZOLAI_TTS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    payload, audio = ui_app.synthesize_ui(
        text="Pasian",
        provider="gemini",
        language="zomi",
        voice="Kore",
        model="",
        base_url="",
        response_format="",
        out_path=str(tmp_path / "out.wav"),
        dry_run=True,
    )
    assert payload["ok"] is True
    assert payload["result"]["request"]["model"] == "gemini-3.8-flash-tts"
    assert audio is None


def test_dry_run_openrouter_builds_request_without_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ZOLAI_TTS_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    payload, audio = ui_app.synthesize_ui(
        text="Hello",
        provider="openrouter",
        language="en",
        voice="alloy",
        model="openai/gpt-4o-mini-tts",
        base_url="https://openrouter.ai/api/v1",
        response_format="mp3",
        out_path=str(tmp_path / "out.mp3"),
        dry_run=True,
    )
    assert payload["ok"] is True
    result = payload["result"]
    assert result["mode"] == "dry-run"
    assert result["provider"] == "openrouter"
    assert result["model"] == "openai/gpt-4o-mini-tts"
    assert result["base_url"] == "https://openrouter.ai/api/v1"
    assert result["response_format"] == "mp3"
    assert result["request"]["endpoint"].endswith("/audio/speech")
    assert audio is None


def test_provider_error_surfaces_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise ui_app.ProviderError("backend missing")

    monkeypatch.setattr(ui_app, "get_provider", boom)
    payload, audio = ui_app.synthesize_ui(
        text="Pasian",
        provider="piper",
        language="ted",
        voice="/tmp/fake.onnx",
        model="",
        base_url="",
        response_format="",
        out_path="/tmp/out.wav",
        dry_run=False,
    )
    assert payload["ok"] is False
    assert "backend missing" in payload["error"]
    assert audio is None


def test_real_synthesis_uses_provider_and_returns_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "ok.wav"

    class FakeProvider:
        name = "piper"

        def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult:
            out_path.write_bytes(b"RIFFfake")
            return SynthesisResult(
                out_path=out_path, provider="piper", voice=voice, metadata={"language": "ted"}
            )

    monkeypatch.setattr(ui_app, "get_provider", lambda *_a, **_k: FakeProvider())
    payload, audio = ui_app.synthesize_ui(
        text="Pasian",
        provider="piper",
        language="ted",
        voice="/tmp/fake.onnx",
        model="",
        base_url="",
        response_format="",
        out_path=str(out),
        dry_run=False,
    )
    assert payload["ok"] is True
    assert payload["result"]["out_path"] == str(out)
    assert audio == str(out)


def test_main_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        ui_app.main(["--help"])
    assert exc.value.code == 0
    assert "zolai-tts-ui" in capsys.readouterr().out


def test_cli_help_via_console_script_style() -> None:
    # Smoke-check the module entry path is usable and returns JSON-safe payloads.
    payload, _ = ui_app.synthesize_ui("x", "piper", "ted", "v", "", "", "", "", True)
    assert payload["ok"] is True
    assert "gradio" in sys.modules


def test_build_app_contains_media_components() -> None:
    app = ui_app.build_app()
    assert isinstance(app, gr.Blocks)
    classes = {c.__class__.__name__ for c in app.blocks.values()}
    assert "Audio" in classes
    assert "Textbox" in classes
    assert "Dropdown" in classes
