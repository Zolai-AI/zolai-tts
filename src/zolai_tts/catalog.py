"""Dynamic, env-aware TTS provider/model/voice catalog.

No network call or key read happens at import time. Catalogs are fetched only
when :func:`fetch_catalog` is called (web API catalog route / Refresh action).
API keys are read from the environment at fetch time and sent only as request
headers - key values are never logged, returned, cached, or stored in the UI.
A failed fetch degrades to a curated fallback with a non-secret error summary.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zolai_tts.ai_sdk.config import PROVIDER_DEFAULTS

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

OPENROUTER_API_KEY_ENVS = ("ZOLAI_TTS_OPENROUTER_API_KEY", "OPENROUTER_API_KEY")
OPENROUTER_BASE_URL_ENVS = ("ZOLAI_TTS_OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL")
GEMINI_API_KEY_ENVS = ("ZOLAI_TTS_GEMINI_API_KEY", "GEMINI_API_KEY")
GEMINI_BASE_URL_ENVS = ("ZOLAI_TTS_GEMINI_BASE_URL",)
PIPER_VOICE_DIR_ENVS = ("ZOLAI_TTS_PIPER_VOICES_DIR", "PIPER_VOICES_DIR")

FALLBACK_OPENROUTER_MODELS = (
    "fish-audio/s2.1-pro-free:free",
    "heygen/heygen-voice-1-turbo:free",
    "openai/gpt-4o-mini-tts",
)
FALLBACK_OPENROUTER_VOICES = ("alloy", "echo", "fable", "onyx", "nova", "shimmer")
FALLBACK_OPENROUTER_FORMATS = ("mp3", "wav", "opus", "aac", "flac", "pcm")
FALLBACK_GEMINI_MODELS = ("gemini-3.8-flash-tts",)
FALLBACK_GEMINI_VOICES = (
    "Kore", "Puck", "Charon", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr",
)
GEMINI_FORMATS = ("wav",)
PIPER_FORMATS = ("wav",)
_SPEECH_MODALITIES = frozenset({"speech", "audio"})


def known_providers() -> list[str]:
    """Canonical provider names, derived from the config layer."""
    return sorted(PROVIDER_DEFAULTS)


@dataclass
class ModelInfo:
    """One TTS model and the voices/formats it actually supports."""

    id: str
    name: str = ""
    voices: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "voices": list(self.voices),
            "formats": list(self.formats),
        }


@dataclass
class ProviderCatalog:
    """A provider's discoverable TTS models, voices and output formats."""

    provider: str
    models: list[str] = field(default_factory=list)
    model_infos: list[ModelInfo] = field(default_factory=list)
    voices: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    source: str = "fallback"
    error: str | None = None
    key_env: str | None = None
    key_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe view containing no secret values."""
        return {
            "provider": self.provider,
            "models": list(self.models),
            "model_infos": [m.to_dict() for m in self.model_infos],
            "voices": list(self.voices),
            "formats": list(self.formats),
            "source": self.source,
            "error": self.error,
            "key_env": self.key_env,
            "key_present": self.key_present,
        }


def _env_first(names: tuple[str, ...], env: Any = None) -> str | None:
    source = os.environ if env is None else env
    for name in names:
        value = source.get(name)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _env_key(names: tuple[str, ...], env: Any = None) -> tuple[str | None, bool]:
    """Return (env var name, present) without exposing the value."""
    source = os.environ if env is None else env
    for name in names:
        if source.get(name):
            return name, True
    return (names[0] if names else None), False


def _dedupe(values: Any, *, limit: int = 500) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _get_json(url: str, *, headers: dict[str, str] | None = None, timeout: float) -> Any:
    req = urllib.request.Request(  # noqa: S310 - fixed https base from config
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "zolai-tts-catalog/0.3",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset, errors="replace"))


def _speech_params(item: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extract voice names and response formats from one model record."""
    voices: list[str] = []
    formats: list[str] = []
    modalities = item.get("output_modalities")
    if not isinstance(modalities, list):
        return voices, formats
    for modality in modalities:
        if not isinstance(modality, dict):
            continue
        if modality.get("type") not in _SPEECH_MODALITIES:
            continue
        params = modality.get("supported_parameters")
        if not isinstance(params, dict):
            continue
        for spec, sink in (
            (params.get("voice"), voices),
            (params.get("response_format"), formats),
        ):
            if isinstance(spec, dict):
                sink.extend(spec.get("values") or [])
            elif isinstance(spec, list):
                sink.extend(spec)
    return voices, formats


def _extract_openrouter_speech(
    payload: Any,
) -> tuple[list[str], list[str], list[str], list[ModelInfo]]:
    """Parse OpenRouter's dedicated TTS catalog response.

    Real payload shape::

        {"data": [{"id": "...", "name": "...", "output_modalities": [
            {"type": "speech", "supported_parameters": {
                "voice": {"type": "enum", "values": [...]},
                "response_format": {"type": "enum", "values": [...]}}}}],
          "endpoints": [{"output_modalities": [...]}]}]}
    """
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return [], [], [], []
    models: list[str] = []
    all_voices: list[str] = []
    all_formats: list[str] = []
    infos: list[ModelInfo] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("model") or item.get("name")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        modalities = item.get("output_modalities")
        if isinstance(modalities, list) and modalities:
            types = {m.get("type") for m in modalities if isinstance(m, dict)}
            if not types & _SPEECH_MODALITIES:
                continue
        voices, formats = _speech_params(item)
        for endpoint in item.get("endpoints") or []:
            if isinstance(endpoint, dict):
                ev, ef = _speech_params(endpoint)
                voices.extend(ev)
                formats.extend(ef)
        clean_formats = [str(f).lower().lstrip(".") for f in formats]
        voices = _dedupe(voices)
        clean_formats = _dedupe(clean_formats)
        models.append(model_id.strip())
        all_voices.extend(voices)
        all_formats.extend(clean_formats)
        infos.append(
            ModelInfo(
                id=model_id.strip(),
                name=str(item.get("name") or ""),
                voices=voices,
                formats=clean_formats,
            )
        )
    return (
        _dedupe(models),
        _dedupe(all_voices),
        _dedupe(all_formats),
        infos,
    )


def fallback_catalog(provider: str) -> ProviderCatalog:
    """Return curated, offline catalog data (used before a live fetch)."""
    if provider == "openrouter":
        return ProviderCatalog(
            provider=provider,
            models=list(FALLBACK_OPENROUTER_MODELS),
            model_infos=[
                ModelInfo(
                    id=model_id,
                    voices=list(FALLBACK_OPENROUTER_VOICES),
                    formats=list(FALLBACK_OPENROUTER_FORMATS),
                )
                for model_id in FALLBACK_OPENROUTER_MODELS
            ],
            voices=list(FALLBACK_OPENROUTER_VOICES),
            formats=list(FALLBACK_OPENROUTER_FORMATS),
        )
    if provider == "gemini":
        return ProviderCatalog(
            provider=provider,
            models=list(FALLBACK_GEMINI_MODELS),
            model_infos=[
                ModelInfo(
                    id=model_id,
                    voices=list(FALLBACK_GEMINI_VOICES),
                    formats=list(GEMINI_FORMATS),
                )
                for model_id in FALLBACK_GEMINI_MODELS
            ],
            voices=list(FALLBACK_GEMINI_VOICES),
            formats=list(GEMINI_FORMATS),
        )
    if provider == "piper":
        return ProviderCatalog(
            provider=provider, models=[], model_infos=[], voices=[],
            formats=list(PIPER_FORMATS),
        )
    return ProviderCatalog(provider=provider, source="unknown", error="Unknown provider")


def fetch_openrouter_catalog(
    *, timeout: float = 8.0, base_url: str | None = None, api_key: str | None = None,
    env: Any = None,
) -> ProviderCatalog:
    """Fetch live OpenRouter TTS models/voices/formats using env config.

    ``api_key``/``env`` are injectable for tests; production callers omit them.
    """
    base = (
        base_url
        or _env_first(OPENROUTER_BASE_URL_ENVS, env)
        or DEFAULT_OPENROUTER_BASE_URL
    ).rstrip("/")
    key = api_key if api_key is not None else _env_first(OPENROUTER_API_KEY_ENVS, env)
    key_name, present = _env_key(OPENROUTER_API_KEY_ENVS, env)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    candidates = [f"{base}/audio/speech/models"]
    if key:
        candidates.append(f"{base}/models/user")
    candidates.append(f"{base}/models?output_modalities=speech")

    errors: list[str] = []
    for url in candidates:
        try:
            payload = _get_json(url, headers=headers, timeout=timeout)
            models, voices, formats, infos = _extract_openrouter_speech(payload)
            if models or voices or formats:
                return ProviderCatalog(
                    provider="openrouter",
                    models=models or list(FALLBACK_OPENROUTER_MODELS),
                    model_infos=infos,
                    voices=voices or list(FALLBACK_OPENROUTER_VOICES),
                    formats=formats or list(FALLBACK_OPENROUTER_FORMATS),
                    source=url.split("?")[0],
                    key_env=key_name,
                    key_present=present,
                )
        except Exception as exc:  # noqa: BLE001 - degrade, never leak details
            errors.append(type(exc).__name__)

    fallback = fallback_catalog("openrouter")
    fallback.error = "; ".join(dict.fromkeys(errors)) if errors else "no speech models returned"
    fallback.key_env = key_name
    fallback.key_present = present
    return fallback


def fetch_gemini_catalog(
    *, timeout: float = 8.0, base_url: str | None = None, api_key: str | None = None,
    env: Any = None,
) -> ProviderCatalog:
    """Fetch live Gemini models using the env API key (header, never in URL)."""
    base = (
        base_url
        or _env_first(GEMINI_BASE_URL_ENVS, env)
        or DEFAULT_GEMINI_BASE_URL
    ).rstrip("/")
    key = api_key if api_key is not None else _env_first(GEMINI_API_KEY_ENVS, env)
    key_name, present = _env_key(GEMINI_API_KEY_ENVS, env)
    fallback = fallback_catalog("gemini")
    fallback.key_env = key_name
    fallback.key_present = present
    if not key:
        fallback.source = "curated"
        fallback.error = "no env API key; showing curated models"
        return fallback

    try:
        payload = _get_json(f"{base}/models", headers={"x-goog-api-key": key}, timeout=timeout)
        models: list[str] = []
        infos: list[ModelInfo] = []
        for item in (payload.get("models") or []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            short = name.split("/", 1)[-1] if "/" in name else name
            supported = " ".join(str(x) for x in (item.get("supportedActions") or []))
            if ("tts" in short.lower() or "speech" in supported.lower()) and short:
                models.append(short)
                infos.append(
                    ModelInfo(
                        id=short,
                        name=short,
                        voices=list(FALLBACK_GEMINI_VOICES),
                        formats=list(GEMINI_FORMATS),
                    )
                )
        if models:
            return ProviderCatalog(
                provider="gemini",
                models=_dedupe(models),
                model_infos=infos,
                voices=list(FALLBACK_GEMINI_VOICES),
                formats=list(GEMINI_FORMATS),
                source=f"{base}/models",
                key_env=key_name,
                key_present=present,
            )
        fallback.error = "API returned no TTS models; showing curated models"
    except Exception as exc:  # noqa: BLE001 - degrade, never leak details
        fallback.error = f"fetch failed ({type(exc).__name__}); showing curated models"
    return fallback


def fetch_piper_catalog(*, voices_dir: str | None = None, env: Any = None) -> ProviderCatalog:
    """List local Piper ``.onnx`` voices from configured/local directories."""
    catalog = fallback_catalog("piper")
    dirs: list[Path] = []
    configured = voices_dir or _env_first(PIPER_VOICE_DIR_ENVS, env)
    if configured:
        dirs.append(Path(configured).expanduser())
    dirs.extend([
        Path.home() / ".local" / "share" / "piper" / "voices",
        Path("voices"),
        Path("models"),
    ])
    voices: list[str] = []
    for directory in dirs:
        try:
            if directory.is_dir():
                voices.extend(p.name for p in sorted(directory.glob("*.onnx")))
        except OSError:
            continue
    if voices:
        catalog.voices = _dedupe(voices, limit=100)
        catalog.source = "local-filesystem"
    return catalog


def fetch_catalog(
    provider: str, *, timeout: float = 8.0, env: Any = None,
    base_url: str | None = None, refresh: bool = False,
) -> ProviderCatalog:
    """Fetch live catalog data for one canonical provider."""
    if provider == "openrouter":
        return fetch_openrouter_catalog(timeout=timeout, base_url=base_url, env=env)
    if provider == "gemini":
        return fetch_gemini_catalog(timeout=timeout, base_url=base_url, env=env)
    if provider == "piper":
        return fetch_piper_catalog(env=env)
    return fallback_catalog(provider)
