import pytest

from zolai_tts.frontend.g2p import DIGRAPHS, g2p
from zolai_tts.frontend.phonemize import phonemize


def test_digraph_segmentation_keeps_zvs_clusters() -> None:
    assert g2p("kham") == "kh a m"
    assert g2p("gham") == "gh a m"
    assert g2p("ngai") == "ng a i"
    assert g2p("thla") == "th l a"
    assert g2p("chim") == "ch i m"
    assert g2p("phah") == "ph a h"
    assert g2p("bhal") == "bh a l"


def test_unattested_digraphs_are_not_zvs_ground_truth() -> None:
    assert DIGRAPHS == ("th", "kh", "gh", "ng", "ch", "ph", "bh")
    for unattested in ("sh", "hm", "hn"):
        assert unattested not in DIGRAPHS


def test_punctuation_is_separate_token() -> None:
    assert g2p("hi.") == "h i ."
    assert g2p("a, b") == "a , b"


def test_phonemize_falls_back_when_backend_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    phonemizer = pytest.importorskip("phonemizer")

    def boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("no espeak voice")

    monkeypatch.setattr(phonemizer, "phonemize", boom)
    with pytest.warns(RuntimeWarning, match="fallback"):
        assert phonemize("kham") == g2p("kham")


def test_phonemize_never_raises_on_missing_espeak(monkeypatch: pytest.MonkeyPatch) -> None:
    phonemizer = pytest.importorskip("phonemizer")
    monkeypatch.setattr(
        phonemizer,
        "phonemize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("espeak missing")),
    )
    with pytest.warns(RuntimeWarning):
        assert phonemize("ngai") == g2p("ngai")
