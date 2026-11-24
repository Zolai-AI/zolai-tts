from __future__ import annotations

from zolai_tts.ai_sdk.config import resolve_audio_config


def test_openrouter_config_precedence_cli_over_env_and_defaults(monkeypatch) -> None:
    monkeypatch.setenv("ZOLAI_TTS_OPENROUTER_MODEL", "openai/env-model")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://env.example/v1")
    cfg = resolve_audio_config(
        provider="openrouter",
        cli={"model": "openai/cli-model", "base_url": "https://cli.example/v1", "voice": "alloy"},
        config={"model": "openai/config-model", "base_url": "https://cfg.example/v1"},
    )
    assert cfg.model == "openai/cli-model"
    assert cfg.base_url == "https://cli.example/v1"
    assert cfg.voice == "alloy"
    assert cfg.api_key_env in {"ZOLAI_TTS_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"}


def test_openrouter_defaults_and_redaction(monkeypatch) -> None:
    monkeypatch.delenv("ZOLAI_TTS_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cfg = resolve_audio_config(provider="openrouter", cli={"voice": "alloy"})
    redacted = cfg.redacted()
    assert cfg.provider == "openrouter"
    assert cfg.model == "openai/gpt-4o-mini-tts"
    assert cfg.base_url == "https://openrouter.ai/api/v1"
    assert cfg.response_format == "mp3"
    assert "api_key" not in redacted
    assert redacted["api_key_present"] is False


def test_gemini_default_model_preserved() -> None:
    cfg = resolve_audio_config(provider="gemini", cli={"voice": "Kore", "language": "zolai"})
    assert cfg.model == "gemini-3.8-flash-tts"


def test_openrouter_env_base_url_and_format_precedence(monkeypatch) -> None:
    monkeypatch.setenv("ZOLAI_TTS_OPENROUTER_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("ZOLAI_TTS_OPENROUTER_RESPONSE_FORMAT", "wav")
    cfg = resolve_audio_config(
        provider="openrouter",
        cli={"voice": "alloy"},
        config={"response_format": "opus"},
    )
    assert cfg.base_url == "https://env.example/v1"
    assert cfg.response_format == "opus"


def test_resolve_audio_config_redacts_no_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret")
    cfg = resolve_audio_config(provider="openrouter", cli={"voice": "alloy"})
    redacted = cfg.redacted()
    assert redacted["api_key_present"] is True
    assert "super-secret" not in str(redacted)
    assert "api_key" not in redacted
