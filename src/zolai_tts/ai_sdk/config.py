"""Model/config resolution for TTS providers.

Precedence: CLI args > config YAML > environment > defaults.
No network calls. API keys are checked for presence only; values never returned.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from .types import ModelConfig

PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "piper": {
        "model": None,
        "base_url": None,
        "api_key_envs": (),
        "response_format": "wav",
        "language": "ted",
    },
    "gemini": {
        "model": "gemini-3.8-flash-tts",
        "base_url": None,
        "api_key_envs": ("ZOLAI_TTS_GEMINI_API_KEY", "GEMINI_API_KEY"),
        "response_format": "wav",
        "language": "zolai",
    },
    "openrouter": {
        "model": "openai/gpt-4o-mini-tts",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_envs": ("ZOLAI_TTS_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
        "response_format": "mp3",
        "language": "en",
    },
}

_PROVIDER_ENV_KEYS = {
    "gemini": ("ZOLAI_TTS_GEMINI_MODEL", "GEMINI_MODEL"),
    "openrouter": ("ZOLAI_TTS_OPENROUTER_MODEL", "OPENROUTER_MODEL"),
}
_PROVIDER_BASE_URL_KEYS = {
    "gemini": ("ZOLAI_TTS_GEMINI_BASE_URL",),
    "openrouter": ("ZOLAI_TTS_OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL"),
}
_PROVIDER_VOICE_KEYS = {
    "openrouter": ("ZOLAI_TTS_OPENROUTER_VOICE", "OPENROUTER_VOICE"),
    "gemini": ("ZOLAI_TTS_GEMINI_VOICE",),
}
_PROVIDER_FORMAT_KEYS = {
    "openrouter": ("ZOLAI_TTS_OPENROUTER_RESPONSE_FORMAT",),
}


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _env_first(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def provider_api_key_envs(provider: str) -> tuple[str, ...]:
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    envs = defaults.get("api_key_envs", ())
    return tuple(str(x) for x in envs)


def provider_api_key_present(provider: str) -> tuple[bool, str | None]:
    for name in provider_api_key_envs(provider):
        if os.getenv(name):
            return True, name
    envs = provider_api_key_envs(provider)
    return False, envs[0] if envs else None


def resolve_audio_config(
    *,
    provider: str,
    cli: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> ModelConfig:
    """Resolve TTS config with CLI > config > env > defaults precedence."""
    cli = dict(cli or {})
    cfg = dict(config or {})
    env_map = os.environ if env is None else env

    defaults = PROVIDER_DEFAULTS.get(provider, {})
    model_env_names = _PROVIDER_ENV_KEYS.get(provider, ())
    base_url_env_names = _PROVIDER_BASE_URL_KEYS.get(provider, ())
    voice_env_names = _PROVIDER_VOICE_KEYS.get(provider, ())
    format_env_names = _PROVIDER_FORMAT_KEYS.get(provider, ())

    model = _first_nonempty(
        cli.get("model"),
        cfg.get("model"),
        _env_first_from(model_env_names, env_map),
        defaults.get("model"),
    )
    base_url = _first_nonempty(
        cli.get("base_url"),
        cfg.get("base_url"),
        _env_first_from(base_url_env_names, env_map),
        defaults.get("base_url"),
    )
    voice = _first_nonempty(
        cli.get("voice"),
        cfg.get("voice"),
        _env_first_from(voice_env_names, env_map),
    )
    language = _first_nonempty(
        cli.get("language"),
        cfg.get("language"),
        defaults.get("language"),
    )
    response_format = _first_nonempty(
        cli.get("response_format"),
        cfg.get("response_format"),
        _env_first_from(format_env_names, env_map),
        defaults.get("response_format"),
    )

    key_present, key_env = _key_present(provider, env_map)

    extra: dict[str, Any] = {}
    for source in (cfg, cli):
        for k, v in source.items():
            if k in {
                "provider",
                "model",
                "base_url",
                "voice",
                "language",
                "response_format",
                "out",
                "text",
                "text_file",
                "config",
                "dry_run",
            }:
                continue
            if v is not None:
                extra[k] = v

    return ModelConfig(
        provider=provider,
        model=str(model) if model is not None else None,
        base_url=str(base_url).rstrip("/") if base_url is not None else None,
        api_key_env=key_env,
        api_key_present=key_present,
        voice=str(voice) if voice is not None else None,
        language=str(language) if language is not None else None,
        response_format=str(response_format) if response_format is not None else None,
        extra=extra,
    )


def _env_first_from(names: tuple[str, ...], env_map: Mapping[str, str]) -> str | None:
    for name in names:
        value = env_map.get(name)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _key_present(provider: str, env_map: Mapping[str, str]) -> tuple[bool, str | None]:
    envs = provider_api_key_envs(provider)
    for name in envs:
        if env_map.get(name):
            return True, name
    return False, envs[0] if envs else None
