"""Thin internal AI SDK layer for TTS model/config resolution.

No network calls, no API key reads at import time, no optional heavy deps.
"""

from .config import resolve_audio_config
from .types import AudioRequest, AudioResult, ModelConfig, ProviderCapabilities

__all__ = [
    "AudioRequest",
    "AudioResult",
    "ModelConfig",
    "ProviderCapabilities",
    "resolve_audio_config",
]
