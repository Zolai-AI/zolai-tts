"""Batch TTS: JSONL input → per-item audio + tracked manifest.

Dry-run is the default: no network, no audio, no files — only a printed plan.
``--live`` opts in to real synthesis.

Default provider is OpenRouter with the free HeyGen Voice Turbo model
(``heygen/heygen-voice-1-turbo:free``, 44.1 kHz mono PCM, max 5,000 chars per
request). ``fish-audio`` (``fish-audio/s2.1-pro-free:free``) reuses the same
OpenAI-compatible OpenRouter path with the same env key. ``gemini`` remains an
optional alternate (``interactions.create`` v1beta).

Neither free model carries a production latency/availability guarantee, and
free-tier terms are unverified: ``legal_status`` stays ``unverified`` and the
publish gate blocks. Gemini ``<...>`` point-in-time tags and
``speech_metadata.style`` are Gemini-only — for OpenRouter/Fish Audio runs the
tags/style stay manifest source annotations with ``tags_applied=false`` and are
never injected into the provider ``input``.

Secrets are env-only (``ZOLAI_TTS_OPENROUTER_API_KEY`` / ``OPENROUTER_API_KEY``,
``ZOLAI_TTS_GEMINI_API_KEY`` / ``GEMINI_API_KEY``); never commit a key.
Audio lands under the gitignored ``artifacts/``; the manifest is tracked.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zolai_tts.ai_sdk.config import provider_api_key_present, resolve_audio_config
from zolai_tts.ai_sdk.openai_compat import synthesize_speech
from zolai_tts.ai_sdk.types import AudioRequest
from zolai_tts.data.provenance import (
    build_manifest,
    publish_allowed,
    sha256_text,
    write_manifest,
)
from zolai_tts.voice_lookup import Voice, VoiceLookupError, resolve_voice

#: HeyGen Voice Turbo hard limit — chunk every request to stay at or below it.
MAX_CHUNK_CHARS = 5_000

#: Streamed PCM shape we wrap into a WAV header (44.1 kHz mono, 16-bit LE).
PCM_SAMPLE_RATE = 44_100
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2  # bytes per sample (16-bit)

DEFAULT_OUT_DIR = "artifacts"
DEFAULT_MANIFEST_DIR = "manifests"


@dataclass(frozen=True)
class ProviderSpec:
    """One selectable ``--provider`` entry. Plain strings only (no enums)."""

    name: str
    #: ``resolve_audio_config`` provider key for the transport path.
    config_provider: str
    default_model: str
    transport: str  # "openai_compat" | "gemini"
    #: Whether Gemini ``<...>`` tags / style are injected into the payload.
    tags_applied: bool
    #: ``False`` ⇒ free/no-cost tier with no production guarantee (warn).
    #: ``None`` ⇒ guarantee not asserted either way (no SLA claim either way).
    production_guarantee: bool | None
    caveat: str


PROVIDERS: dict[str, ProviderSpec] = {
    "openrouter": ProviderSpec(
        name="openrouter",
        config_provider="openrouter",
        default_model="heygen/heygen-voice-1-turbo:free",
        transport="openai_compat",
        tags_applied=False,
        production_guarantee=False,
        caveat=(
            "HeyGen Voice Turbo free tier via OpenRouter: streams 44.1 kHz mono "
            "PCM, 39 languages, max 5,000 chars/request. Terms unverified; no "
            "production latency/availability guarantee. Provider-owned default "
            "voices cannot be claimed as Zolai-owned audio."
        ),
    ),
    "fish-audio": ProviderSpec(
        name="fish-audio",
        config_provider="openrouter",
        default_model="fish-audio/s2.1-pro-free:free",
        transport="openai_compat",
        tags_applied=False,
        production_guarantee=False,
        caveat=(
            "Fish Audio S2.1 Pro Free via OpenRouter: no-cost variant for "
            "testing, prototyping and low-volume applications only — no "
            "production latency or availability guarantees. Same env key as "
            "OpenRouter; terms unverified."
        ),
    ),
    "gemini": ProviderSpec(
        name="gemini",
        config_provider="gemini",
        default_model="gemini-2.5-flash-preview-tts",
        transport="gemini",
        tags_applied=True,
        production_guarantee=None,
        caveat=(
            "Optional Gemini alternate (interactions.create v1beta); "
            "experimental for Tedim/Zolai/Zomi, terms unverified."
        ),
    ),
}

PROVIDER_NAMES: tuple[str, ...] = tuple(PROVIDERS)


class BatchError(RuntimeError):
    """Batch input/config problem — the CLI fails loudly on it."""


def spec_for(provider: str) -> ProviderSpec:
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise BatchError(
            f"unknown provider {provider!r}; choose one of: {', '.join(PROVIDER_NAMES)}"
        )
    return spec


def load_items(path: Path | str) -> list[dict[str, Any]]:
    """Load JSONL items: ``{id?, text, tags?, style?, source_ref?}`` per line."""
    source = Path(path)
    if not source.is_file():
        raise BatchError(f"input not found: {source}")
    items: list[dict[str, Any]] = []
    with source.open(encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BatchError(f"{source}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise BatchError(f"{source}:{lineno}: expected a JSON object")
            text = record.get("text")
            if not isinstance(text, str) or not text.strip():
                raise BatchError(f"{source}:{lineno}: missing non-empty 'text'")
            tags = record.get("tags") or []
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                raise BatchError(f"{source}:{lineno}: 'tags' must be a list of strings")
            item_id = str(record.get("id") or f"item-{lineno:04d}")
            items.append(
                {
                    "id": item_id,
                    "text": text,
                    "tags": [str(t) for t in tags],
                    "style": (str(record["style"]) if record.get("style") else None),
                    "source_ref": (str(record["source_ref"]) if record.get("source_ref") else None),
                }
            )
    if not items:
        raise BatchError(f"no items in {source}")
    return items


def chunk_text(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split ``text`` into chunks of at most ``limit`` characters.

    Greedy split on whitespace (falls back to hard split for long tokens);
    joining the chunks with single spaces reproduces the source wording — no
    words are dropped or rewritten.
    """
    if limit <= 0:
        raise BatchError(f"chunk limit must be positive, got {limit}")
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for word in text.split():
        if len(word) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(word[i : i + limit] for i in range(0, len(word), limit))
            continue
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks or [text]


def detect_audio_format(data: bytes) -> str:
    """Classify provider bytes: ``wav`` (RIFF), ``mp3`` (ID3/sync), else raw ``pcm``."""
    if data[:4] == b"RIFF":
        return "wav"
    if data[:3] == b"ID3":
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    return "pcm"


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap raw PCM in a 44.1 kHz mono 16-bit WAV header (no resampling)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(PCM_CHANNELS)
        wav.setsampwidth(PCM_SAMPLE_WIDTH)
        wav.setframerate(PCM_SAMPLE_RATE)
        wav.writeframes(pcm)
    return buffer.getvalue()


def write_audio_bytes(data: bytes, destination: Path) -> tuple[Path, str]:
    """Write provider bytes to ``destination`` without silent corruption.

    Already-WAV bytes are passed through, MP3 bytes get an ``.mp3`` extension,
    and raw PCM is wrapped into a proper 44.1 kHz mono WAV header.
    Returns ``(written_path, format)``.
    """
    fmt = detect_audio_format(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "pcm":
        destination = destination.with_suffix(".wav")
        destination.write_bytes(pcm_to_wav(data))
    elif fmt == "mp3":
        destination = destination.with_suffix(".mp3")
        destination.write_bytes(data)
    else:
        destination = destination.with_suffix(".wav")
        destination.write_bytes(data)
    return destination, fmt


def build_openrouter_payload(
    text: str, *, spec: ProviderSpec, model: str, voice_id: str
) -> dict[str, Any]:
    """Pure OpenAI-compatible /audio/speech body. Verbatim text, no tags injected."""
    config = resolve_audio_config(
        provider=spec.config_provider,
        cli={"model": model, "voice": voice_id, "language": "en", "response_format": "pcm"},
    )
    request = AudioRequest(text=text, voice=voice_id, out_path=None, config=config)
    from zolai_tts.ai_sdk.openai_compat import build_speech_request

    body = build_speech_request(request)
    # Payload fidelity: input stays exactly the source text (no <...> tags,
    # no style markers) — tags/style are verified for Gemini only.
    if body["input"] != text:
        raise BatchError("payload input must equal source text verbatim")
    return body


def _gemini_tags(tags: list[str]) -> str:
    """English point-in-time ``<...>`` tag prefix for the Gemini payload."""
    return " ".join(f"<{tag}>" for tag in tags)


def build_gemini_payload(
    text: str,
    *,
    spec: ProviderSpec,
    model: str,
    voice_id: str,
    tags: list[str],
    style: str | None,
) -> dict[str, Any]:
    """Gemini-only payload: verbatim source text + verified ``<...>`` tags and style."""
    from zolai_tts.providers.gemini import build_batch_interaction_request

    return build_batch_interaction_request(
        text, voice=voice_id, language="en", model=model, tags=tags, style=style
    )


def build_payload(
    text: str,
    *,
    spec: ProviderSpec,
    model: str,
    voice_id: str,
    tags: list[str],
    style: str | None,
) -> dict[str, Any]:
    """Provider payload for one chunk. Tags/style only where verified (Gemini)."""
    if spec.transport == "gemini":
        return build_gemini_payload(
            text, spec=spec, model=model, voice_id=voice_id, tags=tags, style=style
        )
    return build_openrouter_payload(text, spec=spec, model=model, voice_id=voice_id)


def _require_live_key(spec: ProviderSpec) -> None:
    """Fail loudly before any synthesis when the env key is missing (env-only)."""
    from zolai_tts.ai_sdk.config import provider_api_key_envs
    from zolai_tts.cli import GEMINI_KEY_NAMES

    if spec.transport == "gemini":
        if not any(os.getenv(name) for name in GEMINI_KEY_NAMES):
            raise BatchError(
                "no Gemini API key in environment; set ZOLAI_TTS_GEMINI_API_KEY "
                "or GEMINI_API_KEY (never commit a key)"
            )
        return
    present, env_name = provider_api_key_present(spec.config_provider)
    if not present:
        envs = provider_api_key_envs(spec.config_provider)
        raise BatchError(
            f"no OpenRouter API key in environment; set "
            f"{' or '.join(envs)} (never commit a key)"
            + (f" [expected {env_name}]" if env_name else "")
        )


def _synthesize_openrouter_chunk(
    text: str, *, spec: ProviderSpec, model: str, voice_id: str, part_path: Path
) -> bytes:
    config = resolve_audio_config(
        provider=spec.config_provider,
        cli={"model": model, "voice": voice_id, "language": "en", "response_format": "pcm"},
    )
    synthesize_speech(AudioRequest(text=text, voice=voice_id, out_path=part_path, config=config))
    data = part_path.read_bytes()
    part_path.unlink(missing_ok=True)
    return data


def _synthesize_gemini_chunk(
    text: str,
    *,
    spec: ProviderSpec,
    model: str,
    voice_id: str,
    tags: list[str],
    style: str | None,
) -> bytes:
    payload = build_gemini_payload(
        text, spec=spec, model=model, voice_id=voice_id, tags=tags, style=style
    )
    from zolai_tts.providers import gemini as gemini_mod

    client = gemini_mod._client()  # noqa: SLF001 - intentional live batch path
    interaction = client.interactions.create(**payload)
    audio = getattr(interaction, "output_audio", None)
    data = getattr(audio, "data", None) if audio else None
    if isinstance(data, str):
        return base64.b64decode(data)
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise BatchError("Gemini returned no output_audio data")


def merge_wav_parts(parts: list[bytes]) -> bytes | None:
    """Concatenate same-shape WAV parts into one WAV; ``None`` if not mergeable."""
    if not parts:
        return None
    frames: list[bytes] = []
    params: tuple[int, int, int] | None = None
    for part in parts:
        if detect_audio_format(part) != "wav":
            return None
        with wave.open(io.BytesIO(part), "rb") as wav:
            current = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
            if params is None:
                params = current
            elif current != params:
                return None
            frames.append(wav.readframes(wav.getnframes()))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        if params is None:
            return None  # unreachable (parts non-empty) — defensive, no crash
        out.setnchannels(params[0])
        out.setsampwidth(params[1])
        out.setframerate(params[2])
        for frame in frames:
            out.writeframes(frame)
    return buffer.getvalue()


def batch_id_for(*, input_path: str, seed: int, voice_key: str, provider: str, model: str) -> str:
    """Deterministic short batch id from inputs (no randomness, no secrets)."""
    material = f"{input_path}:{seed}:{voice_key}:{provider}:{model}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def plan_for(
    *,
    items: list[dict[str, Any]],
    voice: Voice,
    spec: ProviderSpec,
    model: str,
    seed: int,
    input_path: str,
    batch_id: str,
    audio_dir: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Dry-run plan (pure JSON — nothing written, no network performed)."""
    warnings: list[str] = [spec.caveat]
    if spec.production_guarantee is False:
        warnings.append(
            "production_guarantee=false: no production latency or availability "
            "guarantees for this free model."
        )
    if not publish_allowed(voice.legal_status):
        warnings.append(
            f"publish blocked: legal_status={voice.legal_status!r} (requires "
            "'verified'); free-tier terms unverified."
        )
    return {
        "mode": "dry-run",
        "provider": spec.name,
        "model": model,
        "transport": spec.transport,
        "voice": voice.as_dict(),
        "seed": seed,
        "batch_id": batch_id,
        "input": input_path,
        "tags_applied": spec.tags_applied,
        "production_guarantee": spec.production_guarantee,
        "max_chunk_chars": MAX_CHUNK_CHARS,
        "audio_dir": str(audio_dir),
        "manifest_path": str(manifest_path),
        "publishable": publish_allowed(voice.legal_status),
        "network": False,
        "warnings": warnings,
        "items": [
            {
                "id": item["id"],
                "sha256": sha256_text(item["text"]),
                "chars": len(item["text"]),
                "chunks": len(chunk_text(item["text"])),
                "tags": item["tags"],
                "style": item["style"],
            }
            for item in items
        ],
    }


def run_live(
    *,
    items: list[dict[str, Any]],
    voice: Voice,
    spec: ProviderSpec,
    model: str,
    seed: int,
    input_path: str,
    batch_id: str,
    audio_dir: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Synthesize every chunk, write audio under ``audio_dir``, save manifest."""
    if voice.provider != spec.name:
        raise BatchError(
            f"voice {voice.voice_key!r} belongs to provider {voice.provider!r}, "
            f"not {spec.name!r}; refusing to silently cross providers"
        )
    _require_live_key(spec)
    audio_dir.mkdir(parents=True, exist_ok=True)

    manifest_items: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for item in items:
        chunks = chunk_text(item["text"])
        part_bytes: list[bytes] = []
        for index, chunk in enumerate(chunks):
            tags = item["tags"] if (spec.tags_applied and index == 0) else []
            style = item["style"] if (spec.tags_applied and index == 0) else None
            if spec.transport == "gemini":
                data = _synthesize_gemini_chunk(
                    chunk,
                    spec=spec,
                    model=model,
                    voice_id=voice.provider_voice_id,
                    tags=tags,
                    style=style,
                )
            else:
                part_path = audio_dir / f"{item['id']}.{index:03d}.part"
                data = _synthesize_openrouter_chunk(
                    chunk,
                    spec=spec,
                    model=model,
                    voice_id=voice.provider_voice_id,
                    part_path=part_path,
                )
            part_bytes.append(data)

        merged = merge_wav_parts(part_bytes) if len(part_bytes) > 1 else None
        if merged is not None:
            written, fmt = write_audio_bytes(merged, audio_dir / f"{item['id']}.wav")
            audio_paths = [str(written)]
        else:
            audio_paths = []
            for index, data in enumerate(part_bytes):
                target = audio_dir / (
                    f"{item['id']}.wav" if len(part_bytes) == 1 else f"{item['id']}.{index:03d}"
                )
                written, fmt = write_audio_bytes(data, target)
                audio_paths.append(str(written))

        manifest_items.append(
            {
                "id": item["id"],
                "text": item["text"],
                "sha256": sha256_text(item["text"]),
                "tags": item["tags"],
                "style": item["style"],
                "audio_path": audio_paths[0],
                **({"audio_parts": audio_paths} if len(audio_paths) > 1 else {}),
            }
        )
        results.append(
            {"id": item["id"], "chunks": len(chunks), "format": fmt, "audio": audio_paths[0]}
        )

    manifest = build_manifest(
        batch_id=batch_id,
        seed=seed,
        provider=spec.name,
        model=model,
        voice_key=voice.voice_key,
        legal_status=voice.legal_status,
        items=manifest_items,
        input_path=input_path,
        production_guarantee=spec.production_guarantee,
        tags_applied=spec.tags_applied,
    )
    written_manifest = write_manifest(manifest_path, manifest)
    return {
        "mode": "live",
        "provider": spec.name,
        "model": model,
        "voice_key": voice.voice_key,
        "batch_id": batch_id,
        "manifest": str(written_manifest),
        "audio_dir": str(audio_dir),
        "tags_applied": spec.tags_applied,
        "production_guarantee": spec.production_guarantee,
        "publishable": publish_allowed(voice.legal_status),
        "legal_status": voice.legal_status,
        "warnings": [spec.caveat] if spec.production_guarantee is False else [],
        "items": results,
    }


def run_batch(args: argparse.Namespace) -> int:
    """CLI entry: resolve voice, then dry-run plan or (with ``--live``) synth."""
    spec = spec_for(args.provider)
    model = (getattr(args, "model", None) or "").strip() or spec.default_model
    voice_key = (getattr(args, "voice_key", None) or "").strip()
    input_path = str(args.input)
    seed = int(getattr(args, "seed", 0) or 0)

    try:
        items = load_items(input_path)
        # Dry-run never touches the network: resolve offline (read-only SQLite).
        voice = resolve_voice(voice_key, offline=not args.live)
    except (VoiceLookupError, BatchError) as exc:
        print(f"batch failed: {exc}", file=sys.stderr, flush=True)
        return 2

    batch_id = batch_id_for(
        input_path=input_path,
        seed=seed,
        voice_key=voice.voice_key,
        provider=spec.name,
        model=model,
    )
    audio_dir = Path(getattr(args, "out_dir", None) or DEFAULT_OUT_DIR) / batch_id
    manifest_path = Path(DEFAULT_MANIFEST_DIR) / f"{batch_id}.json"

    if not args.live:
        plan = plan_for(
            items=items,
            voice=voice,
            spec=spec,
            model=model,
            seed=seed,
            input_path=input_path,
            batch_id=batch_id,
            audio_dir=audio_dir,
            manifest_path=manifest_path,
        )
        print(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
        return 0

    try:
        summary = run_live(
            items=items,
            voice=voice,
            spec=spec,
            model=model,
            seed=seed,
            input_path=input_path,
            batch_id=batch_id,
            audio_dir=audio_dir,
            manifest_path=manifest_path,
        )
    except (BatchError, VoiceLookupError) as exc:
        print(f"batch failed: {exc}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def add_batch_parser(sub: Any) -> None:
    """Register the ``batch`` subcommand (additive; called from ``cli.py``)."""
    batch = sub.add_parser(
        "batch",
        help="Batch TTS from JSONL (dry-run by default; --live to synthesize)",
    )
    batch.add_argument("--input", required=True, help="JSONL input file (one item/line)")
    batch.add_argument(
        "--voice-key",
        default=None,
        help="Registry voice_key (no default voice: missing/unknown fails loudly)",
    )
    batch.add_argument("--seed", type=int, default=0, help="Batch seed (recorded in manifest)")
    batch.add_argument(
        "--live",
        action="store_true",
        help="Perform real synthesis (uses quota; default is dry-run, no network)",
    )
    batch.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Audio output root (gitignored; default: {DEFAULT_OUT_DIR})",
    )
    batch.add_argument(
        "--provider",
        default="openrouter",
        choices=list(PROVIDER_NAMES),
        help="TTS provider (default: openrouter — HeyGen Voice Turbo free)",
    )
    batch.add_argument(
        "--model",
        default=None,
        help="Model override (defaults: heygen/heygen-voice-1-turbo:free | "
        "fish-audio/s2.1-pro-free:free | gemini-2.5-flash-preview-tts)",
    )
    batch.set_defaults(func=_run_batch_command)


def _run_batch_command(args: argparse.Namespace) -> int:
    return run_batch(args)
