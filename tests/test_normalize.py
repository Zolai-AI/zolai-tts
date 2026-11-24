from zolai_tts.frontend.normalize import (
    NUMBER_WORDS,
    normalize,
    normalize_with_provenance,
)


def test_nfc_and_invisible_characters_removed() -> None:
    assert normalize("e\u0301") == "\u00e9"
    assert normalize("Ka\u200b ram") == "Ka ram"


def test_whitespace_collapsed_and_edges_stripped() -> None:
    assert normalize("  Ka\t ram\n a  ") == "Ka ram a"


def test_punctuation_spacing_rules_keep_apostrophe_in_word() -> None:
    assert normalize("Ka, ram.a! hi") == "Ka, ram. a! hi"
    assert normalize("Pasian' in") == "Pasian' in"


def test_digit_boundary_spacing_and_nfkc_digits() -> None:
    assert normalize("kum2026") == "kum 2026"
    assert normalize("2026kum") == "2026 kum"
    assert normalize("\uff11\uff12\uff13") == "123"


def test_normalize_with_provenance_reports_changed_flag() -> None:
    report = normalize_with_provenance(" Ka ")
    assert report.original == " Ka "
    assert report.text == "Ka"
    assert report.changed is True
    assert normalize_with_provenance("Ka").changed is False


def test_number_word_expansion_is_noop_until_reviewed() -> None:
    assert NUMBER_WORDS == {}
    assert normalize("123") == "123"
