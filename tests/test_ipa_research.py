from zolai_tts.frontend.ipa_research import (
    DIGRAPH_IPA_RESEARCH,
    UNKNOWN,
    ipa_research,
)

ATTESTED_DIGRAPHS = ("th", "kh", "gh", "ng", "ch", "ph", "bh")


def test_all_attested_digraphs_default_to_unknown() -> None:
    assert tuple(DIGRAPH_IPA_RESEARCH) == ATTESTED_DIGRAPHS
    assert all(value == UNKNOWN for value in DIGRAPH_IPA_RESEARCH.values())
    assert all(ipa_research(digraph) == UNKNOWN for digraph in ATTESTED_DIGRAPHS)


def test_unknown_input_returns_unknown() -> None:
    for unknown in ("sh", "zz", "", "thla"):
        assert ipa_research(unknown) == UNKNOWN


def test_mapping_contains_no_literal_ipa_symbols() -> None:
    assert set(DIGRAPH_IPA_RESEARCH.values()) == {UNKNOWN}
    assert all(value.isascii() for value in DIGRAPH_IPA_RESEARCH.values())
