"""Provider protocol, result model and canonical provider registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

ProviderFactory = Callable[..., "TTSProvider"]
_REGISTRY: dict[str, ProviderFactory] = {}


@dataclass(frozen=True)
class SynthesisResult:
    """Immutable description of one synthesis output."""

    out_path: Path
    provider: str
    voice: str
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Base error for provider configuration/backend failures."""


class MissingBackendError(ProviderError):
    """A required optional synthesis backend is not installed."""


class VoiceNotFoundError(ProviderError):
    """A real voice model path was not supplied or does not exist."""


@runtime_checkable
class TTSProvider(Protocol):
    """Minimal synthesis contract implemented by every adapter."""

    name: str

    def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult: ...


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register ``factory`` under the canonical key ``name``."""
    _REGISTRY[name] = factory


def get_provider(name: str, **options: Any) -> TTSProvider:
    """Build a registered provider by canonical key."""
    try:
        factory = _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown provider {name!r}. Available providers: {available}"
        ) from None
    return factory(**options)
