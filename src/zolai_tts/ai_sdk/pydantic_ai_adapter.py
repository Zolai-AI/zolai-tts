"""Optional PydanticAI adapter for model/config metadata/validation.

This is intentionally lightweight: PydanticAI is primarily agent-oriented; we use
it for model string/config validation and metadata wiring where available.
Lazy import, no base dependency.
"""
from __future__ import annotations

from typing import Any

from zolai_tts.inference.base import MissingBackendError

from .types import ModelConfig, ProviderCapabilities


def capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_tts=False,
        supported_formats=(),
        requires_voice=True,
        supports_base_url=True,
    )


def _require_pydantic_ai() -> Any:
    try:
        import pydantic_ai  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise MissingBackendError(
            "PydanticAI backend requires optional 'pydantic-ai-slim'. Install with: "
            "uv sync --extra ai-pydantic (or pip install -e '.[ai-pydantic]')."
        ) from exc
    return pydantic_ai


def validate_model_config(config: ModelConfig) -> dict[str, Any]:
    """Validate/normalize model config metadata using PydanticAI when installed."""
    _require_pydantic_ai()
    # PydanticAI model identifiers are typically provider:model; we keep our provider field.
    model = config.model or ""
    if config.provider == "openrouter" and model and "/" not in model and ":" not in model:
        # allow plain model but report normalized hint
        normalized = f"openrouter:{model}"
    elif ":" in model or "/" in model or not model:
        normalized = model
    else:
        normalized = f"{config.provider}:{model}"
    return {
        "provider": config.provider,
        "model": config.model,
        "normalized_model": normalized,
        "base_url": config.base_url,
        "api_key_present": config.api_key_present,
        "supported_tts": False,
        "execution": "unsupported; metadata/config validation only",
        "note": (
            "PydanticAI adapter provides config/metadata validation; "
            "use openrouter/openai-compatible path for TTS execution."
        ),
    }
