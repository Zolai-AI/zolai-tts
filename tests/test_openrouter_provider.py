from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from zolai_tts.inference.base import ProviderError
from zolai_tts.providers import openrouter


def test_import_no_network_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    before = set(sys.modules)
    monkeypatch.delenv("ZOLAI_TTS_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    importlib.reload(openrouter)
    # no openai imported by module import
    assert not any(m == "openai" or m.startswith("openai.") for m in sys.modules if m not in before)


def test_build_openrouter_request_dry_run() -> None:
    req = openrouter.build_openrouter_request(
        "Hello", voice="alloy", language="en", model="openai/gpt-4o-mini-tts", response_format="mp3"
    )
    assert req["provider"] == "openrouter"
    assert req["endpoint"].endswith("/audio/speech")
    assert req["body"]["model"] == "openai/gpt-4o-mini-tts"
    assert req["body"]["voice"] == "alloy"
    assert req["config"]["api_key_present"] in {True, False}


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZOLAI_TTS_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = openrouter.OpenRouterProvider(language="en")
    with pytest.raises(ProviderError, match="API key"):
        provider.synthesize("hi", "alloy", tmp_path / "out.mp3")


def test_missing_voice_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder")
    provider = openrouter.OpenRouterProvider(language="en")
    with pytest.raises(ProviderError, match="voice"):
        provider.synthesize("hi", "", tmp_path / "out.mp3")


def test_synthesize_writes_audio_with_fake_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder")

    class FakeResponse:
        def write_to_file(self, path):
            Path(path).write_bytes(b"FAKEAUDIO")

    class FakeSpeech:
        def create(self, **kwargs):
            assert kwargs["model"]
            assert kwargs["voice"] == "alloy"
            return FakeResponse()

    class FakeAudio:
        speech = FakeSpeech()

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.audio = FakeAudio()

    fake_openai = SimpleNamespace(OpenAI=FakeClient)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    provider = openrouter.OpenRouterProvider(language="en", model="openai/gpt-4o-mini-tts")
    out = tmp_path / "out.mp3"
    result = provider.synthesize("hello", "alloy", out)
    assert out.read_bytes() == b"FAKEAUDIO"
    assert result.provider == "openrouter"
    assert result.metadata["model"] == "openai/gpt-4o-mini-tts"


def test_synthesize_maps_sdk_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder")

    class FakeSpeech:
        def create(self, **kwargs):
            raise RuntimeError("boom")

    class FakeClient:
        def __init__(self, **kwargs):
            self.audio = SimpleNamespace(speech=FakeSpeech())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    provider = openrouter.OpenRouterProvider(language="en")
    with pytest.raises(ProviderError, match="synthesis failed"):
        provider.synthesize("hello", "alloy", tmp_path / "out.mp3")


def test_synthesize_maps_http_status_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder")

    class FakeStatusError(RuntimeError):
        pass

    class FakeSpeech:
        def create(self, **kwargs):
            raise FakeStatusError("Error code: 401 - invalid key")

    class FakeClient:
        def __init__(self, **kwargs):
            self.audio = SimpleNamespace(speech=FakeSpeech())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    provider = openrouter.OpenRouterProvider(language="en")
    with pytest.raises(ProviderError, match="synthesis failed"):
        provider.synthesize("hello", "alloy", tmp_path / "out.mp3")

    class FakeSpeech500:
        def create(self, **kwargs):
            raise RuntimeError("Error code: 500 - server error")

    class FakeClient500:
        def __init__(self, **kwargs):
            self.audio = SimpleNamespace(speech=FakeSpeech500())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient500))
    with pytest.raises(ProviderError, match="synthesis failed"):
        provider.synthesize("hello", "alloy", tmp_path / "out.mp3")
