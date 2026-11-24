import base64
import importlib
import os
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

import zolai_tts.providers.gemini as gemini
from zolai_tts.inference.base import ProviderError

_LIVE = os.getenv("ZOLAI_TTS_RUN_LIVE") == "1" and bool(
    os.getenv("ZOLAI_TTS_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
)


def test_import_creates_no_client_and_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def banned(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("env read or network at import time")

    monkeypatch.setattr(os, "getenv", banned)
    importlib.reload(gemini)
    assert "google" not in sys.modules


def test_build_request_uses_v1beta_interactions_payload() -> None:
    request = gemini.build_interaction_request("Pasian", voice="Kore", language="zolai")
    assert request["model"] == "gemini-3.8-flash-tts"
    assert request["response_format"] == {"type": "audio"}
    assert request["generation_config"] == {"speech_config": [{"voice": "Kore"}]}
    assert "annotations" not in request


def test_build_request_rejects_unsupported_language() -> None:
    with pytest.raises(ValueError, match="Unsupported Gemini language"):
        gemini.build_interaction_request("hi", voice="Kore", language="mizo")


def test_synthesize_without_key_raises_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZOLAI_TTS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with pytest.raises(ProviderError, match="ZOLAI_TTS_GEMINI_API_KEY"):
            gemini.GeminiProvider().synthesize("hi", "Kore", Path("/tmp/opencode/no.wav"))


def test_synthesize_decodes_base64_wav_via_fake_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZOLAI_TTS_GEMINI_API_KEY", "placeholder-not-a-real-key")
    payload = base64.b64encode(b"RIFFfake-wav").decode("ascii")
    fake = SimpleNamespace(
        interactions=SimpleNamespace(
            create=lambda **_kwargs: SimpleNamespace(
                output_audio=SimpleNamespace(data=payload)
            )
        )
    )
    monkeypatch.setattr(gemini, "_client", lambda: fake)
    with pytest.warns(UserWarning, match="Zolai"):
        result = gemini.GeminiProvider(language="zolai").synthesize(
            "Pasian", "Kore", tmp_path / "out.wav"
        )
    assert result.out_path.read_bytes() == b"RIFFfake-wav"
    assert result.metadata["experimental"] == "True"


def test_zolai_and_zomi_languages_warn_about_free_tier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gemini,
        "_client",
        lambda: SimpleNamespace(
            interactions=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    output_audio=SimpleNamespace(data="")
                )
            )
        ),
    )
    for language in ("zolai", "zomi"):
        with pytest.warns(UserWarning) as warnings_record:
            gemini.GeminiProvider(language=language).synthesize(
                "hi", "Kore", tmp_path / "out.wav"
            )
        assert "free-tier" in str(warnings_record[0].message)


def test_english_language_does_not_warn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gemini,
        "_client",
        lambda: SimpleNamespace(
            interactions=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    output_audio=SimpleNamespace(data="")
                )
            )
        ),
    )
    with warnings.catch_warnings(record=True) as caught:
        gemini.GeminiProvider(language="en").synthesize("hi", "Kore", tmp_path / "out.wav")
    assert not caught


@pytest.mark.live
@pytest.mark.skipif(not _LIVE, reason="opt-in live Gemini test; no network by default")
def test_live_gemini_smoke() -> None:
    pytest.skip("live smoke is opt-in; set ZOLAI_TTS_RUN_LIVE=1 and a key to enable")
