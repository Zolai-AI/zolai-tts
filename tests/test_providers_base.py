import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import zolai_tts.inference.base as base
from zolai_tts.inference.base import SynthesisResult, TTSProvider, get_provider
from zolai_tts.providers import gemini, piper  # noqa: F401


def test_registry_contains_canonical_providers() -> None:
    assert {"piper", "gemini", "openrouter"}.issubset(set(base._REGISTRY))


def test_unknown_provider_error_names_canonical_keys() -> None:
    with pytest.raises(ValueError) as exc:
        get_provider("local")
    msg = str(exc.value)
    assert "gemini" in msg and "openrouter" in msg and "piper" in msg


def test_synthesis_result_is_frozen() -> None:
    result = SynthesisResult(
        out_path=Path("a.wav"), provider="piper", voice="v"
    )
    with pytest.raises(FrozenInstanceError):
        result.provider = "gemini"  # type: ignore[misc]


def test_synthesis_result_metadata_default_is_independent() -> None:
    from pathlib import Path

    first = SynthesisResult(Path("a.wav"), "piper", "v")
    second = SynthesisResult(Path("b.wav"), "piper", "v")
    first.metadata["x"] = "1"
    assert "x" not in second.metadata


def test_protocol_synthesize_signature() -> None:
    assert list(inspect.signature(TTSProvider.synthesize).parameters) == [
        "self",
        "text",
        "voice",
        "out_path",
    ]
