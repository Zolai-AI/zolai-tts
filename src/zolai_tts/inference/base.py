"""Provider protocol, result model and canonical provider registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

ProviderFactory = Callable[..., "TTSProvider"]
_REGISTRY: dict[str, ProviderFactory] = {}
_META: dict[str, dict[str, Any]] = {}


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


def register_provider(
    name: str,
    factory: ProviderFactory,
    *,
    label: str | None = None,
    voice_kind: str = "name",
    hosted: bool = True,
    **extra: Any,
) -> None:
    """Register ``factory`` under the canonical key ``name``.

    ``label``/``voice_kind``/``hosted`` plus any ``extra`` keys are provider
    metadata surfaced by :func:`list_providers` so UIs and CLIs build their
    provider list dynamically from the registry, not from hardcoded copies.
    """
    _REGISTRY[name] = factory
    _META[name] = {
        "name": name,
        "label": label or name,
        "voice_kind": voice_kind,  # "path" for local model files, "name" for voice ids
        "hosted": hosted,
        **extra,
    }


def list_providers() -> list[dict[str, Any]]:
    """Return metadata for every registered provider, ordered by name."""
    return [dict(_META.get(name, {"name": name, "label": name})) for name in sorted(_REGISTRY)]


def provider_meta(name: str) -> dict[str, Any]:
    """Return metadata for one registered provider."""
    try:
        return dict(_META[name])
    except KeyError:
        raise ValueError(f"Unknown provider {name!r}.") from None


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
