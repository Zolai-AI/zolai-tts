"""Optional LiteLLM adapter for TTS/config paths. Lazy import, no base dep.

Capability-gated: this adapter provides request/config helpers and support
metadata only. Direct TTS execution is not wired into the canonical provider
registry because LiteLLM speech support depends on the selected model/backend.
"""
from __future__ import annotations

from typing import Any

from zolai_tts.inference.base import MissingBackendError

from .types import ModelConfig, ProviderCapabilities


def capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_tts=False,
        supported_formats=("mp3", "wav", "opus", "aac", "flac", "pcm"),
        requires_voice=True,
        supports_base_url=True,
    )


def _require_litellm() -> Any:
    try:
        import litellm  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise MissingBackendError(
            "LiteLLM backend requires optional 'litellm'. Install with: uv sync --extra ai-litellm "
            "(or pip install -e '.[ai-litellm]')."
        ) from exc
    return litellm


def build_speech_kwargs(*, text: str, config: ModelConfig) -> dict[str, Any]:
    """Build kwargs for litellm.speech/text_to_speech. Pure, no import."""
    if not config.model:
        raise ValueError("Model is required for LiteLLM TTS")
    if not config.voice:
        raise ValueError("Voice is required for LiteLLM TTS")
    kwargs: dict[str, Any] = {
        "model": config.model,
        "input": text,
        "voice": config.voice,
    }
    if config.base_url:
        kwargs["api_base"] = config.base_url
    if config.response_format:
        kwargs["response_format"] = config.response_format
    kwargs.update(config.extra)
    return kwargs


def describe_support(model: str | None) -> dict[str, Any]:
    """Best-effort capability description; no network."""
    return {
        "backend": "litellm",
        "model": model,
        "tts_supported": "capability-gated; verify model supports audio/speech before execution",
        "execution": "unsupported in canonical registry; use openrouter/openai-compatible path",
        "install": "uv sync --extra ai-litellm",
    }
