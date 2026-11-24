"""Optional OpenAI-compatible adapter for TTS endpoints (OpenRouter etc.).

Imports `openai` lazily. No network calls at import time.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zolai_tts.inference.base import MissingBackendError, ProviderError

from .types import AudioRequest, AudioResult


def _require_openai() -> Any:
    try:
        import openai  # type: ignore
    except Exception as exc:  # pragma: no cover - import failure path tested via monkeypatch
        raise MissingBackendError(
            "OpenAI-compatible backend requires the optional 'openai' package. "
            "Install with: uv sync --extra openrouter (or pip install -e '.[openrouter]')."
        ) from exc
    return openai


def build_speech_request(request: AudioRequest) -> dict[str, Any]:
    """Build an OpenAI-compatible /audio/speech request body. Pure/no network."""
    if not request.config.model:
        raise ValueError("Model is required for OpenAI-compatible TTS requests")
    if not request.voice:
        raise ValueError("Voice is required for OpenAI-compatible TTS requests")
    body: dict[str, Any] = {
        "model": request.config.model,
        "input": request.text,
        "voice": request.voice,
    }
    if request.config.response_format:
        body["response_format"] = request.config.response_format
    body.update(request.config.extra)
    return body


def synthesize_speech(request: AudioRequest) -> AudioResult:
    """Synthesize via OpenAI-compatible SDK. Reads key from env at call time only."""
    openai = _require_openai()
    if not request.config.api_key_present:
        env_name = request.config.api_key_env or "OPENROUTER_API_KEY"
        raise ProviderError(
            f"{request.config.provider} requires an API key. Set {env_name} in the environment; "
            "never commit a key."
        )
    if not request.out_path:
        raise ValueError("Output path is required for synthesis")
    body = build_speech_request(request)

    import os

    env_name = request.config.api_key_env or "OPENROUTER_API_KEY"
    api_key = (
        os.getenv(env_name)
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("ZOLAI_TTS_OPENROUTER_API_KEY")
    )
    if not api_key:
        raise ProviderError(
            f"{request.config.provider} requires an API key. Set {env_name} in the environment; "
            "never commit a key."
        )

    try:
        client = openai.OpenAI(api_key=api_key, base_url=request.config.base_url)
        response = client.audio.speech.create(**body)
        # openai SDK returns a response object with write_to_file/stream_to_file/content
        out = Path(request.out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(response, "write_to_file"):
            response.write_to_file(out)
        else:
            content = getattr(response, "content", None)
            if content is None:
                # try read()
                read = getattr(response, "read", None)
                content = read() if callable(read) else bytes(response)
            out.write_bytes(content)
    except ProviderError:
        raise
    except Exception as exc:
        msg = str(exc)
        for name in (
            request.config.api_key_env,
            "ZOLAI_TTS_OPENROUTER_API_KEY",
            "OPENROUTER_API_KEY",
            "ZOLAI_TTS_GEMINI_API_KEY",
            "GEMINI_API_KEY",
        ):
            if not name:
                continue
            val = os.getenv(name)
            if val:
                msg = msg.replace(val, f"<{name}:redacted>")
        raise ProviderError(f"{request.config.provider} synthesis failed: {msg}") from exc

    return AudioResult(
        out_path=Path(request.out_path),
        provider=request.config.provider,
        voice=request.voice,
        model=request.config.model,
        response_format=request.config.response_format,
        metadata={
            "base_url": request.config.base_url,
            "experimental": str(request.config.language in {"ted", "zolai", "zomi"}),
        },
    )
