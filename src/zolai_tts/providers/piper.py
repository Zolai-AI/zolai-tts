"""Local Piper adapter — the real Tedim/Zolai voice path.

No voice model is committed. ``--voice`` must point at a real ONNX voice;
``piper-tts`` is imported lazily and is unavailable on Python >= 3.13.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from zolai_tts.inference.base import (
    MissingBackendError,
    SynthesisResult,
    VoiceNotFoundError,
    register_provider,
)

_INSTALL_HINT = (
    "Piper backend is not installed. Install with: "
    "python -m pip install -e '.[piper]' (Python <3.13). "
    "No voice model is committed; supply a real Zolai voice with --voice."
)


class PiperProvider:
    """Synthesis through a locally installed Piper voice model."""

    name = "piper"

    def __init__(
        self,
        *,
        language: str = "ted",
        load_voice: Callable[[str], Any] | None = None,
    ) -> None:
        self.language = language
        self._load_voice = load_voice

    def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult:
        """Load a real voice model and write audio to ``out_path``."""
        voice_path = Path(voice)
        if not voice_path.exists():
            raise VoiceNotFoundError(
                f"Piper voice model not found: {voice}. "
                "Supply a real Zolai ONNX voice via --voice."
            )
        if self._load_voice is not None:
            model = self._load_voice(voice)
        else:
            try:
                from piper import PiperVoice
            except ImportError as exc:
                raise MissingBackendError(_INSTALL_HINT) from exc
            model = PiperVoice.load(voice)

        destination = Path(out_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(model, "synthesize_wav"):
            model.synthesize_wav(text, str(destination))
        else:
            sample_rate, audio = model.synthesize(text)
            import soundfile as sf

            sf.write(str(destination), audio, sample_rate)
        return SynthesisResult(
            out_path=destination,
            provider=self.name,
            voice=voice,
            metadata={"language": self.language},
        )


register_provider("piper", lambda **options: PiperProvider(**options))
