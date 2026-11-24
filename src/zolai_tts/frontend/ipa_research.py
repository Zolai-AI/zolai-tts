"""UNKNOWN-by-default IPA research placeholders for ZVS-attested digraphs.

NOT canonical. This is a data-only research scaffold: every value is
``"UNKNOWN"`` until a qualified linguist verifies the pronunciation mapping.
No IPA symbols are asserted here and no invented phonology is introduced.

Ground truth is cited, not copied: ``zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md``
sections 2.1, 4.3 and 4.4 (lines 45-55, 104).
"""

from __future__ import annotations

from collections.abc import Mapping

SOURCE = "zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md:45-55,104"
UNKNOWN = "UNKNOWN"

# Attested digraph inventory only (source above); IPA values are unresolved.
DIGRAPH_IPA_RESEARCH: Mapping[str, str] = {
    "th": UNKNOWN,
    "kh": UNKNOWN,
    "gh": UNKNOWN,
    "ng": UNKNOWN,
    "ch": UNKNOWN,
    "ph": UNKNOWN,
    "bh": UNKNOWN,
}


def ipa_research(digraph: str) -> str:
    """Return the research placeholder for ``digraph``; default to UNKNOWN."""
    return DIGRAPH_IPA_RESEARCH.get(digraph.lower(), UNKNOWN)
