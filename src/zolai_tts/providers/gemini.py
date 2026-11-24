"""OPTIONAL Gemini TTS adapter using Zolai/Zomi language codes.

Gemini has no native Tedim/Zolai/Zomi TTS support. Requests using those codes
are experimental and emit a warning; they are not ZVS 2018 ground truth and
must not be shipped as the community voice. Local Piper remains that path.
The SDK is imported and the API key is read only inside ``synthesize``.
"""

from __future__ import annotations

import base64
import warnings
from pathlib import Path
from typing import Any

from zolai_tts.ai_sdk.config import resolve_audio_config
from zolai_tts.inference.base import ProviderError, SynthesisResult, register_provider

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_MODEL = GEMINI_DEFAULT_MODEL  # backward-compatible constant
GEMINI_KEY_NAMES = ("ZOLAI_TTS_GEMINI_API_KEY", "GEMINI_API_KEY")
GEMINI_API_VERSION = "v1beta"
GEMINI_DIRECT_LANGUAGES = frozenset({"en"})
GEMINI_ZOLAI_LANGUAGES = frozenset({"ted", "zolai", "zomi"})
GEMINI_LANGUAGES = GEMINI_DIRECT_LANGUAGES | GEMINI_ZOLAI_LANGUAGES

_ZOLAI_WARNING = (
    "Gemini has no native Tedim/Zolai/Zomi TTS support; this output is "
    "experimental and not ZVS 2018 ground truth. Gemini free-tier content may "
    "be used to improve Google products; do not send community data without "
    "informed consent. Use local Piper for the real Zolai voice."
)


def build_interaction_request(
    text: str, *, voice: str, language: str, model: str | None = None
) -> dict[str, Any]:
    """Build the v1beta Interactions payload. Pure: no key, import or network."""
    if language not in GEMINI_LANGUAGES:
        accepted = ", ".join(sorted(GEMINI_LANGUAGES))
        raise ValueError(f"Unsupported Gemini language {language!r}. Accepted: {accepted}.")
    config = resolve_audio_config(
        provider="gemini",
        cli={"model": model, "voice": voice, "language": language},
    )
    return {
        "model": config.model or GEMINI_DEFAULT_MODEL,
        "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }


def build_batch_interaction_request(
    text: str,
    *,
    voice: str,
    language: str = "en",
    model: str | None = None,
    tags: list[str] | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    """Batch payload for the Gemini alternate: verbatim text + verified tags.

    English point-in-time tags become ``<tag>`` markers in the input; ``style``
    is carried in ``speech_metadata.style``. These two mechanisms are verified
    for Gemini ONLY — OpenRouter/Fish Audio runs must keep tags/style as
    manifest source annotations (``tags_applied=false``), never injected.
    Pure: no key, import or network.
    """
    request = build_interaction_request(text, voice=voice, language=language, model=model)
    if tags:
        tagged = " ".join(f"<{tag}>" for tag in tags)
        cell = request["input"][0]["content"][0]
        cell["text"] = f"{tagged} {cell['text']}"
    if style:
        request["speech_metadata"] = {"style": style}
    return request


def _client() -> Any:
    """Create a Gemini client at call time only."""
    from zolai_tts.secrets import get_secret

    key = get_secret("ZOLAI_TTS_GEMINI_API_KEY") or get_secret("GEMINI_API_KEY")
    if not key:
        raise ProviderError(
            "Gemini requires an API key. Set ZOLAI_TTS_GEMINI_API_KEY or "
            "GEMINI_API_KEY in the environment; never commit a key."
        )
    from google import genai

    return genai.Client(api_key=key, http_options={"api_version": GEMINI_API_VERSION})


def _redact_key_values(message: str) -> str:
    """Never let an SDK exception echo the API key into a run record."""
    from zolai_tts.secrets import get_secret

    out = message
    for name in GEMINI_KEY_NAMES:
        value = get_secret(name)
        if value:
            out = out.replace(value, f"<{name}:redacted>")
    return out


class GeminiProvider:
    """Optional hosted provider for Zolai/Zomi demos and English demos."""

    name = "gemini"

    def __init__(self, *, language: str = "zolai", model: str | None = None) -> None:
        if language not in GEMINI_LANGUAGES:
            accepted = ", ".join(sorted(GEMINI_LANGUAGES))
            raise ValueError(f"Unsupported Gemini language {language!r}. Accepted: {accepted}.")
        self.language = language
        self.model = model

    def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult:
        """Synthesize audio through the Gemini Interactions API."""
        request = build_interaction_request(
            text, voice=voice, language=self.language, model=self.model
        )
        if self.language in GEMINI_ZOLAI_LANGUAGES:
            warnings.warn(_ZOLAI_WARNING, UserWarning, stacklevel=2)
        client = _client()
        destination = Path(out_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            interaction = client.interactions.create(**request)
            audio = getattr(interaction, "output_audio", None)
            if not audio or not getattr(audio, "data", None):
                raise ProviderError(
                    "Gemini returned no audio for this request "
                    "(model may not support the voice/language combination)."
                )
            destination.write_bytes(base64.b64decode(audio.data))
        except ProviderError:
            raise
        except Exception as exc:
            # ProviderError (not the raw SDK error) so the API's error handler
            # returns a structured 502 with a redacted message.
            raise ProviderError(f"Gemini request failed: {_redact_key_values(str(exc))}") from exc
        return SynthesisResult(
            out_path=destination,
            provider=self.name,
            voice=voice,
            metadata={
                "language": self.language,
                "model": request["model"],
                "api_version": GEMINI_API_VERSION,
                "experimental": str(self.language in GEMINI_ZOLAI_LANGUAGES),
            },
        )


register_provider(
    "gemini",
    lambda **options: GeminiProvider(**options),
    label="Gemini (hosted, experimental)",
    voice_kind="name",
    hosted=True,
    note="Hosted Gemini TTS. No native Tedim/Zolai/Zomi support; experimental only.",
    key_envs=("ZOLAI_TTS_GEMINI_API_KEY", "GEMINI_API_KEY"),
)
