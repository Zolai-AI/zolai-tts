"""Dataclasses and capability flags for the internal AI SDK layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderCapabilities:
    """Static capability flags for a provider/backend."""

    supports_tts: bool = True
    supports_streaming: bool = False
    supports_ssml: bool = False
    supported_formats: tuple[str, ...] = ("wav", "mp3")
    requires_voice: bool = True
    supports_base_url: bool = False
    experimental_languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelConfig:
    """Resolved model configuration. Never include secret values in repr/logs."""

    provider: str
    model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    api_key_present: bool = False
    voice: str | None = None
    language: str | None = None
    response_format: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def redacted(self) -> dict[str, Any]:
        """Return a safe view for logs/doctor/dry-run output."""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "api_key_present": self.api_key_present,
            "voice": self.voice,
            "language": self.language,
            "response_format": self.response_format,
            "extra_keys": sorted(self.extra),
        }


@dataclass(frozen=True)
class AudioRequest:
    """Provider-neutral TTS request plan."""

    text: str
    voice: str
    out_path: Path | None
    config: ModelConfig

    def to_plan(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "voice": self.voice,
            "out": str(self.out_path) if self.out_path else None,
            "config": self.config.redacted(),
        }


@dataclass(frozen=True)
class AudioResult:
    """Provider-neutral TTS result."""

    out_path: Path
    provider: str
    voice: str
    model: str | None = None
    response_format: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
