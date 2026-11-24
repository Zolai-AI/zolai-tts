"""Phonemizer wrapper that always degrades gracefully on a base install."""

from __future__ import annotations

import warnings
from collections.abc import Mapping

from zolai_tts.frontend.g2p import g2p

# No Tedim/Zolai eSpeak voice is asserted; English is the documented fallback.
_ESPEAK_LANG: Mapping[str, str] = {
    "ted": "en",
    "zolai": "en",
    "mizo": "en",
    "my": "my",
    "en": "en",
}


def phonemize(text: str, *, language: str = "ted", backend: str = "espeak") -> str:
    """Return phonemizer output, falling back to rule-based ``g2p``."""
    try:
        from phonemizer import phonemize as _phonemize

        return _phonemize(
            text,
            language=_ESPEAK_LANG.get(language, "en"),
            backend=backend,
            with_boundaries=False,
            strip=True,
        )
    except Exception as exc:  # missing eSpeak binary, import or runtime error
        warnings.warn(
            f"phonemizer backend unavailable ({exc}); using rule-based g2p fallback",
            RuntimeWarning,
            stacklevel=2,
        )
        return g2p(text, language=language)
