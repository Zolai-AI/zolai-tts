"""Zolai-TTS: framework-first speech tooling for Tedim Zolai.

The base package is importable with no optional backend, no API key and no
network access.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("zolai-tts")
except PackageNotFoundError:  # pragma: no cover - local/uninstalled dev
    __version__ = "0.0.0+local"
