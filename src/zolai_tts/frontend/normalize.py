"""Deterministic, explainable normalization for Tedim/Zolai TTS input.

ZVS 2018 is the orthographic ground truth by reference to ``zolai-core``
(``zolai/foundation/observation/normalize.py``). No rule table is copied
across repos and no number-word inventory is invented here.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Explicit no-op: Tedim number reading needs ZVS 2018 expert review sourced
# from zolai-core before any expansion table may be asserted.
NUMBER_WORDS: dict[str, str] = {}

_INVISIBLE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_WHITESPACE = re.compile(r"[ \t\r\n]+")
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([,.!?;:])")
_SPACE_AFTER_PUNCT = re.compile(r"([.!?;:])(?=[^\s.!?;:])")
# A unicode letter (word char minus digit and underscore) next to a digit.
_LETTER_DIGIT_BOUNDARY = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")


@dataclass(frozen=True)
class NormalizedText:
    """Original text, normalized text and whether normalization changed it."""

    original: str
    text: str
    changed: bool


def normalize_with_provenance(text: str, *, language: str = "ted") -> NormalizedText:
    """Normalize ``text`` and report whether any rule fired.

    ``language`` is accepted for API stability; this build implements only the
    shared Tedim/Zolai orthographic-safe rules.
    """
    normalized = unicodedata.normalize("NFC", text)
    normalized = _INVISIBLE.sub("", normalized)
    normalized = normalized.translate(_FULLWIDTH_DIGITS)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    normalized = _SPACE_BEFORE_PUNCT.sub(r"\1", normalized)
    normalized = _SPACE_AFTER_PUNCT.sub(r"\1 ", normalized)
    # Apostrophes inside words are deliberately preserved (ZVS glottal mark).
    normalized = _LETTER_DIGIT_BOUNDARY.sub(" ", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    return NormalizedText(original=text, text=normalized, changed=normalized != text)


def normalize(text: str, *, language: str = "ted") -> str:
    """Return normalized text; see :func:`normalize_with_provenance`."""
    return normalize_with_provenance(text, language=language).text
