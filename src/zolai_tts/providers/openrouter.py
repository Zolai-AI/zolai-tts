"""OpenRouter TTS provider via OpenAI-compatible /audio/speech endpoint.

Experimental for Tedim/Zolai/Zomi: OpenRouter routes to underlying models that
do not have native Tedim support. Local Piper remains the real Zolai voice.
API key is read from environment only at synthesis time. No network at import.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from zolai_tts.ai_sdk.config import resolve_audio_config
from zolai_tts.ai_sdk.openai_compat import build_speech_request, synthesize_speech
from zolai_tts.ai_sdk.types import AudioRequest
from zolai_tts.inference.base import ProviderError, SynthesisResult, register_provider

OPENROUTER_DEFAULT_MODEL = "openai/gpt-4o-mini-tts"
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_LANGUAGES = frozenset({"ted", "zolai", "zomi", "en"})
OPENROUTER_ZOLAI_LANGUAGES = frozenset({"ted", "zolai", "zomi"})

_ZOLAI_WARNING = (
    "OpenRouter TTS routes to hosted models with no native Tedim/Zolai/Zomi support; "
    "this output is experimental and not ZVS 2018 ground truth. Hosted provider terms, "
    "quotas, and free-tier/data-use policies vary by model; do not send community data "
    "without informed consent. Use local Piper for the real Zolai voice."
)


def build_openrouter_request(
    text: str,
    *,
    voice: str,
    language: str = "en",
    model: str | None = None,
    base_url: str | None = None,
    response_format: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dry-run request plan. Pure: no key, import or network."""
    if language not in OPENROUTER_LANGUAGES:
        accepted = ", ".join(sorted(OPENROUTER_LANGUAGES))
        raise ValueError(f"Unsupported OpenRouter language {language!r}. Accepted: {accepted}.")
    config = resolve_audio_config(
        provider="openrouter",
        cli={
            "model": model,
            "base_url": base_url,
            "voice": voice,
            "language": language,
            "response_format": response_format,
            **(extra or {}),
        },
    )
    req = AudioRequest(text=text, voice=voice, out_path=None, config=config)
    body = build_speech_request(req)
    return {
        "provider": "openrouter",
        "endpoint": f"{config.base_url}/audio/speech",
        "body": body,
        "config": config.redacted(),
        "experimental": language in OPENROUTER_ZOLAI_LANGUAGES,
    }


class OpenRouterProvider:
    """Optional hosted provider via OpenRouter OpenAI-compatible speech endpoint."""

    name = "openrouter"

    def __init__(
        self,
        *,
        language: str = "en",
        model: str | None = None,
        base_url: str | None = None,
        response_format: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if language not in OPENROUTER_LANGUAGES:
            accepted = ", ".join(sorted(OPENROUTER_LANGUAGES))
            raise ValueError(f"Unsupported OpenRouter language {language!r}. Accepted: {accepted}.")
        self.language = language
        self.model = model
        self.base_url = base_url
        self.response_format = response_format
        self.extra = extra or {}

    def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult:
        if not voice or not str(voice).strip():
            raise ProviderError(
                "OpenRouter requires a voice supported by the selected model. "
                "Pass --voice (model-specific)."
            )
        config = resolve_audio_config(
            provider="openrouter",
            cli={
                "model": self.model,
                "base_url": self.base_url,
                "voice": voice,
                "language": self.language,
                "response_format": self.response_format,
                **self.extra,
            },
        )
        if not config.api_key_present:
            env_name = config.api_key_env or "OPENROUTER_API_KEY"
            raise ProviderError(
                f"OpenRouter requires an API key. Set {env_name} "
                "(or OPENROUTER_API_KEY) in the environment; never commit a key."
            )
        if self.language in OPENROUTER_ZOLAI_LANGUAGES:
            warnings.warn(_ZOLAI_WARNING, UserWarning, stacklevel=2)
        req = AudioRequest(text=text, voice=voice, out_path=Path(out_path), config=config)
        result = synthesize_speech(req)
        return SynthesisResult(
            out_path=result.out_path,
            provider=self.name,
            voice=voice,
            metadata={
                "language": self.language,
                "model": result.model,
                "base_url": config.base_url,
                "response_format": result.response_format,
                "experimental": str(self.language in OPENROUTER_ZOLAI_LANGUAGES),
            },
        )


register_provider(
    "openrouter",
    lambda **options: OpenRouterProvider(**options),
    label="OpenRouter (OpenAI-compatible)",
    voice_kind="name",
    hosted=True,
    note="OpenAI-compatible /audio/speech. Voices/formats depend on the selected model.",
    key_envs=("ZOLAI_TTS_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
    default_base_url=OPENROUTER_DEFAULT_BASE_URL,
)
