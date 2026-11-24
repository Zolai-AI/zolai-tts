"""Rule-based, provisional grapheme segmentation for Tedim/Zolai.

Ground truth: ``zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md`` sections 2.1, 4.3
and 4.4 (lines 45-55, 104). The attested digraph inventory is used verbatim.
Output is segmented graphemes, NOT IPA, and is not claimed as phonemic truth.
"""

from __future__ import annotations

SOURCE = "zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md:45-55,104"

# Attested ZVS digraphs: th, kh, gh, ng, ch, ph, bh.
# Research TODO (unattested; not ZVS ground truth): sh, hm, hn.
DIGRAPHS: tuple[str, ...] = ("th", "kh", "gh", "ng", "ch", "ph", "bh")


def _segment(token: str) -> list[str]:
    pieces: list[str] = []
    index = 0
    while index < len(token):
        pair = token[index : index + 2].lower()
        if len(pair) == 2 and pair in DIGRAPHS:
            pieces.append(token[index : index + 2])
            index += 2
        else:
            pieces.append(token[index])
            index += 1
    return pieces


def g2p(text: str, *, language: str = "ted") -> str:
    """Segment each whitespace token into space-separated graphemes."""
    pieces: list[str] = []
    for token in text.split():
        if not any(character.isalnum() for character in token):
            pieces.append(token)
        else:
            pieces.extend(_segment(token))
    return " ".join(pieces)
