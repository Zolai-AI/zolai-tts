"""Zolai-TTS web API (FastAPI) — replaces the old Gradio-only UI surface.

Endpoints are the single source the React frontend (``web/``) talks to:

* ``GET  /api/health``
* ``GET  /api/providers``                — dynamic, from the provider registry
* ``GET  /api/providers/{name}/catalog`` — live models/voices/formats per provider
* ``POST /api/synthesize``               — real synthesis or dry-run plan
* ``GET  /api/runs`` / ``GET /api/runs/{id}`` / ``GET /api/audio/{id}``
* ``POST /api/recordings``               — mic/upload audio, saved with sidecar metadata
* ``GET  /api/recordings`` / ``GET /api/recordings/{id}/audio``
* ``/`` static — serves ``web/dist`` when a frontend build exists.

Storage lives under ``ZOLAI_TTS_STORE_DIR`` (default ``~/.local/share/zolai-tts``):
``outputs/`` audio, ``runs/`` one JSON record per synthesis, ``recordings/``
captured audio + ``.json`` sidecars. API keys are never read into responses,
stored, or logged — presence only, values always redacted.
"""

import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from zolai_tts.ai_sdk.config import provider_api_key_present
from zolai_tts.catalog import fetch_catalog, known_providers
from zolai_tts.inference.base import ProviderError, get_provider, list_providers, provider_meta
from zolai_tts.providers import gemini as gemini_provider  # noqa: F401  (registers)
from zolai_tts.providers import openrouter as openrouter_provider  # noqa: F401
from zolai_tts.providers import piper as piper_provider  # noqa: F401

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,80}$")
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")
_MAX_TEXT = 8000
_MAX_UPLOAD = 100 * 1024 * 1024


def store_dir() -> Path:
    raw = os.getenv("ZOLAI_TTS_STORE_DIR", "").strip()
    root = Path(raw).expanduser() if raw else Path.home() / ".local" / "share" / "zolai-tts"
    for sub in ("outputs", "runs", "recordings"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def _err(message: str, status: int = 400) -> Any:
    return JSONResponse(status_code=status, content={"ok": False, "error": message})


def _validate_name(value: str, what: str) -> str | None:
    if not value or not _NAME_RE.match(value):
        return f"Invalid {what}."
    return None


def _new_id() -> str:
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    tmp.replace(path)


def _audio_duration_seconds(path: Path) -> float | None:
    try:
        import soundfile as sf

        info = sf.info(str(path))
        return round(info.frames / info.samplerate, 3) if info.samplerate else None
    except Exception:  # noqa: BLE001 - best-effort metadata only
        return None


def _redact(exc: Exception) -> str:
    msg = str(exc)
    for name in (
        "ZOLAI_TTS_GEMINI_API_KEY",
        "GEMINI_API_KEY",
        "ZOLAI_TTS_OPENROUTER_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        value = os.getenv(name)
        if value:
            msg = msg.replace(value, f"<{name}:redacted>")
    return msg


def _providers_payload() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in list_providers():
        name = str(entry.get("name", ""))
        present, env_name = provider_api_key_present(name)
        out.append(
            {
                **entry,
                "key_present": present,
                "key_env": env_name,
            }
        )
    return out


def create_app() -> FastAPI:
    app = FastAPI(title="Zolai-TTS API", version="0.2.0")

    cors = os.getenv("ZOLAI_TTS_CORS", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class SynthesizeBody(BaseModel):
        provider: str
        text: str = Field(min_length=1, max_length=_MAX_TEXT)
        voice: str = ""
        model: str | None = None
        language: str = "ted"
        response_format: str | None = None
        base_url: str | None = None
        out_name: str | None = None
        dry_run: bool = False

    # ------------------------------------------------------------- meta

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "providers": known_providers(),
            "store": str(store_dir()),
        }

    @app.get("/api/providers")
    def providers() -> dict[str, Any]:
        return {"ok": True, "providers": _providers_payload()}

    @app.get("/api/providers/{name}/catalog")
    def provider_catalog(name: str, refresh: bool = False, base_url: str | None = None) -> Any:
        problem = _validate_name(name, "provider name")
        if problem:
            return _err(problem)
        if name not in known_providers():
            return _err(f"Unknown provider {name!r}.", status=404)
        catalog = fetch_catalog(name, base_url=base_url or None)
        return {"ok": True, "catalog": catalog.to_dict(), "refreshed": bool(refresh)}

    # ---------------------------------------------------------- synthesis

    @app.post("/api/synthesize")
    def synthesize(body: SynthesizeBody) -> Any:
        problem = _validate_name(body.provider, "provider name")
        if problem:
            return _err(problem)
        registry_names = {str(p.get("name")) for p in list_providers()}
        if body.provider not in registry_names:
            return _err(f"Unknown provider {body.provider!r}.", status=404)
        text = body.text.strip()
        if not text:
            return _err("Text is required.")
        meta = provider_meta(body.provider)
        voice = (body.voice or "").strip()
        fmt = (body.response_format or "").strip().lower() or None

        plan: dict[str, Any] = {
            "provider": body.provider,
            "model": body.model,
            "voice": voice,
            "language": body.language,
            "response_format": fmt,
            "base_url": body.base_url,
            "mode": "dry-run" if body.dry_run else "synthesize",
        }
        if body.provider == "gemini":
            plan["request"] = gemini_provider.build_interaction_request(
                text, voice=voice, language=body.language, model=body.model
            )
        elif body.provider == "openrouter":
            plan["request"] = openrouter_provider.build_openrouter_request(
                text,
                voice=voice,
                language=body.language,
                model=body.model,
                base_url=body.base_url,
                response_format=fmt,
            )

        if body.dry_run:
            return {"ok": True, "dry_run": True, "plan": plan}

        if not voice:
            return _err(
                "A voice is required: "
                + (
                    "a local .onnx path for Piper"
                    if meta.get("voice_kind") == "path"
                    else "a voice name"
                )
                + "."
            )
        if meta.get("hosted"):
            present, env_name = provider_api_key_present(body.provider)
            if not present:
                return _err(
                    f"{body.provider} requires an API key. Set {env_name} in the environment."
                )

        ext = fmt or ("wav" if body.provider in {"piper", "gemini"} else "mp3")
        if not _EXT_RE.match(ext):
            return _err("Invalid audio format.")
        out_name = (body.out_name or "").strip()
        if out_name and not _SAFE_ID_RE.match(out_name):
            return _err("out_name must be a short safe name (letters, digits, dash, underscore).")
        run_id = out_name or _new_id()
        root = store_dir()
        out_path = (root / "outputs" / f"{run_id}.{ext}").resolve()
        if not str(out_path).startswith(str(root.resolve())):
            return _err("Invalid output path.")

        options: dict[str, Any] = {"language": body.language}
        if body.provider == "gemini" and body.model:
            options["model"] = body.model
        if body.provider == "openrouter":
            if body.model:
                options["model"] = body.model
            if body.base_url:
                options["base_url"] = body.base_url
            if fmt:
                options["response_format"] = fmt
        if meta.get("voice_kind") != "path" and not voice:
            return _err("A voice is required for hosted providers.")

        started = time.time()
        try:
            provider = get_provider(body.provider, **options)
            result = provider.synthesize(text, voice, out_path)
        except (ProviderError, ValueError, OSError) as exc:
            record = {
                "id": run_id,
                "ok": False,
                "error": _redact(exc),
                "provider": body.provider,
                "voice": voice,
                "language": body.language,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "elapsed_seconds": round(time.time() - started, 3),
                "text": text,
            }
            _write_json(root / "runs" / f"{run_id}.json", record)
            return JSONResponse(
                status_code=502, content={"ok": False, "error": _redact(exc), "run": record}
            )

        duration = _audio_duration_seconds(out_path)
        record = {
            "id": run_id,
            "ok": True,
            "provider": result.provider,
            "voice": result.voice,
            "language": body.language,
            "model": body.model,
            "format": ext,
            "out_path": str(out_path),
            "audio_url": f"/api/audio/{run_id}",
            "duration_seconds": duration,
            "bytes": out_path.stat().st_size if out_path.exists() else None,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "elapsed_seconds": round(time.time() - started, 3),
            "metadata": result.metadata,
            "text": text,
        }
        _write_json(root / "runs" / f"{run_id}.json", record)
        return {"ok": True, "dry_run": False, "run": record}

    @app.get("/api/runs")
    def runs(limit: int = 50) -> dict[str, Any]:
        root = store_dir()
        files = sorted((root / "runs").glob("*.json"), reverse=True)[: max(1, min(limit, 200))]
        items = [_read_json(f) for f in files]
        return {"ok": True, "runs": [i for i in items if i]}

    def _find_run_audio(run_id: str) -> Path | None:
        if not _SAFE_ID_RE.match(run_id):
            return None
        root = store_dir().resolve()
        record = _read_json(root / "runs" / f"{run_id}.json") or {}
        candidate = record.get("out_path")
        if isinstance(candidate, str):
            path = Path(candidate).resolve()
            if str(path).startswith(str(root / "outputs")) and path.exists():
                return path
        for ext in ("wav", "mp3", "opus", "aac", "flac", "pcm"):
            path = root / "outputs" / f"{run_id}.{ext}"
            if path.exists():
                return path
        return None

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str) -> Any:
        if not _SAFE_ID_RE.match(run_id):
            return _err("Invalid run id.")
        record = _read_json(store_dir() / "runs" / f"{run_id}.json")
        if not record:
            return _err("Run not found.", status=404)
        return {"ok": True, "run": record}

    @app.get("/api/audio/{run_id}")
    def run_audio(run_id: str) -> Any:
        path = _find_run_audio(run_id)
        if not path:
            return _err("Audio not found.", status=404)
        return FileResponse(path)

    # -------------------------------------------------------- recordings

    _MIME_EXT = {
        "audio/webm": "webm",
        "audio/webm;codecs=opus": "webm",
        "audio/ogg": "ogg",
        "audio/mp4": "m4a",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/flac": "flac",
    }

    @app.post("/api/recordings")
    async def save_recording(
        file: UploadFile = File(...),  # noqa: B008 - FastAPI multipart dependency
        provider: str = Form(""),
        model: str = Form(""),
        voice: str = Form(""),
        note: str = Form(""),
    ) -> Any:
        raw = await file.read(_MAX_UPLOAD + 1)
        if not raw:
            return _err("Empty recording.")
        if len(raw) > _MAX_UPLOAD:
            return _err("Recording too large (100 MB max).", status=413)
        mime = (file.content_type or "audio/webm").split(";")[0]
        ext = _MIME_EXT.get(mime, (mime.rsplit("/", 1)[-1] or "bin")[:8])
        if not _EXT_RE.match(ext):
            ext = "bin"
        rec_id = _new_id()
        root = store_dir()
        audio_path = root / "recordings" / f"{rec_id}.{ext}"
        audio_path.write_bytes(raw)
        record = {
            "id": rec_id,
            "saved_path": str(audio_path),
            "audio_url": f"/api/recordings/{rec_id}/audio",
            "mime": mime,
            "format": ext,
            "bytes": len(raw),
            "duration_seconds": _audio_duration_seconds(audio_path),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_name": file.filename or "browser-recording",
            "context": {"provider": provider, "model": model, "voice": voice, "note": note},
        }
        _write_json(root / "recordings" / f"{rec_id}.json", record)
        return {"ok": True, "recording": record}

    @app.get("/api/recordings")
    def list_recordings(limit: int = 50) -> dict[str, Any]:
        root = store_dir()
        files = sorted((root / "recordings").glob("*.json"), reverse=True)[
            : max(1, min(limit, 200))
        ]
        items = [_read_json(f) for f in files]
        return {"ok": True, "recordings": [i for i in items if i]}

    @app.get("/api/recordings/{rec_id}/audio")
    def recording_audio(rec_id: str) -> Any:
        if not _SAFE_ID_RE.match(rec_id):
            return _err("Invalid recording id.")
        record = _read_json(store_dir() / "recordings" / f"{rec_id}.json") or {}
        saved = record.get("saved_path")
        if isinstance(saved, str):
            path = Path(saved).resolve()
            root = store_dir().resolve()
            if str(path).startswith(str(root / "recordings")) and path.exists():
                return FileResponse(path)
        return _err("Recording not found.", status=404)

    # ------------------------------------------------------- static web

    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")

    return app


app = create_app()


def main(argv: list[str] | None = None) -> int:
    """Console entry point for ``zolai-tts-ui``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="zolai-tts-ui", description="Serve the Zolai-TTS web app + API."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument(
        "--share", action="store_true", help="Bind 0.0.0.0 instead of localhost only."
    )
    parser.add_argument(
        "--config", help="Optional YAML defaults file (accepted for CLI compatibility)."
    )
    parser.add_argument("--reload", action="store_true", help="Dev reload (uvicorn).")
    args = parser.parse_args(argv)
    import uvicorn

    host = "0.0.0.0" if args.share else args.host
    uvicorn.run("zolai_tts.server:app", host=host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
