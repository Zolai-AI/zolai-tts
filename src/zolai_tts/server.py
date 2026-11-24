"""Zolai-TTS web API (FastAPI) — backend for the React studio in ``web/``.

One origin serves the JSON API and the built frontend, so
``http://127.0.0.1:7860`` is the whole studio.

Routes
    ``GET  /api/health``                     service, DB, storage, provider status
    ``GET  /api/providers``                  registry + tier policy (+ ``?tier=``)
    ``GET  /api/meta``                       everything the UI needs in one call
    ``GET  /api/providers/{name}/catalog``   live models/voices/formats, tier-filtered
    ``POST /api/catalog/refresh``            re-fetch and persist catalogs
    ``POST /api/synthesize``                 real synthesis or dry-run plan (+cost gate)
    ``GET  /api/runs`` / ``/api/runs/{id}``  persisted synthesis history
    ``GET  /api/audio/{id}``                 stored object (local file or bucket bytes)
    ``POST /api/recordings``                 mic/upload capture
    ``POST /api/contributions``              consented voice contribution
    ``POST /api/reviews``                    sound-check verdicts on a run
    ``GET  /api/usage``                      cost rollups vs. budget
    ``GET/POST /api/secrets``                session API keys (masked, in-memory)
    ``GET/POST /api/settings``               tier policy, budget, storage backend
    ``GET  /``                               ``web/dist`` when built

Persistence: SQLModel (SQLite by default, PostgreSQL by URI swap) for metadata,
and the object storage hub (local disk or Cloudflare R2 over the S3 API) for
audio bytes. API key values are never persisted, logged, or returned.
"""

from __future__ import annotations

import io
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import soundfile as sf
from fastapi import Body, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from zolai_tts.ai_sdk.config import provider_api_key_present
from zolai_tts.catalog import (
    MODEL_TEXT_LIMITS,
    PROVIDER_LIMITS,
    fetch_catalog,
    known_providers,
    model_tier,
)
from zolai_tts.costing import BudgetLimits, check_budget, estimate_cost
from zolai_tts.db import Repository, get_database, new_id
from zolai_tts.inference.base import ProviderError, get_provider, list_providers, provider_meta
from zolai_tts.paths import store_dir, web_dist_path
from zolai_tts.providers import gemini as gemini_provider  # noqa: F401  (registers)
from zolai_tts.providers import openrouter as openrouter_provider  # noqa: F401
from zolai_tts.providers import piper as piper_provider  # noqa: F401
from zolai_tts.secrets import set_secret
from zolai_tts.secrets import status as secrets_view
from zolai_tts.storage import build_storage, key_for

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,80}$")
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,512}$")

MAX_TEXT = int(os.getenv("ZOLAI_TTS_MAX_TEXT", "8000"))
MAX_UPLOAD_BYTES = int(os.getenv("ZOLAI_TTS_MAX_UPLOAD", "104857600"))
DEFAULT_LANGUAGE = "ted"
MIME_BY_EXT = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "opus": "audio/opus",
    "flac": "audio/flac",
    "aac": "audio/aac",
    "webm": "audio/webm",
    "pcm": "audio/L16",
}
RECording_MIMES = ("audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav")

SETTINGS_TIER = "tier_policy"
SETTINGS_BUDGET = "budget"
SETTINGS_STORAGE = "storage"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _err(message: str | dict[str, Any], status: int = 400) -> JSONResponse:
    body = message if isinstance(message, dict) else {"ok": False, "error": message}
    return JSONResponse(status_code=status, content=body)


def _validate_name(value: str, what: str) -> str | None:
    if not value or not _NAME_RE.match(value):
        return f"Invalid {what}."
    return None


def _redact(exc: Exception) -> str:
    text = str(exc)
    for name in ("ZOLAI_TTS_OPENROUTER_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        value = os.getenv(name)
        if value:
            text = text.replace(value, "***")
    return text[:500]


def _audio_duration_seconds(path: Path) -> float | None:
    try:
        info = sf.info(str(path))
        return round(float(info.frames) / float(info.samplerate), 3) if info.samplerate else None
    except Exception:  # noqa: BLE001  (duration is cosmetic)
        return None


class Studio:
    """Process-wide services: database, repository, storage hub."""

    def __init__(self) -> None:
        self.root = store_dir()
        self.repo = Repository(get_database())
        self.storage = build_storage(self.preferred_storage())

    def preferred_storage(self) -> str:
        stored = self.repo.get_setting(SETTINGS_STORAGE, {}) or {}
        return str(stored.get("preferred") or os.getenv("ZOLAI_TTS_STORAGE_BACKEND") or "local")

    def apply_storage(self, preferred: str) -> dict[str, Any]:
        self.storage = build_storage(preferred)
        self.repo.set_setting(SETTINGS_STORAGE, {"preferred": self.storage.preferred})
        return self.storage.info()

    def tier_policy(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in (self.repo.get_setting(SETTINGS_TIER, {}) or {}).items()}

    def budget_limits(self) -> BudgetLimits:
        return BudgetLimits.from_dict(self.repo.get_setting(SETTINGS_BUDGET, {}))

    def budget(self) -> dict[str, Any]:
        raw = self.repo.get_setting(SETTINGS_BUDGET, {}) or {}
        return {
            "daily_usd": max(0.0, float(raw.get("daily_usd") or 0.0)),
            "monthly_usd": max(0.0, float(raw.get("monthly_usd") or 0.0)),
            "free_only": bool(raw.get("free_only")),
        }

    def spend_today(self) -> float:
        now = datetime.now(UTC)
        return self.repo.spend(now.replace(hour=0, minute=0, second=0, microsecond=0))

    def spend_month(self) -> float:
        now = datetime.now(UTC)
        return self.repo.spend(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    def catalog(self, name: str, *, refresh: bool = False, api_key: str | None = None) -> Any:
        catalog = fetch_catalog(name, api_key=api_key)
        if catalog.error is None:
            self.persist_catalog(name, catalog)
        return catalog

    def persist_catalog(self, name: str, catalog: Any) -> None:
        meta = provider_meta(name)
        self.repo.sync_provider({"name": name, **meta})
        infos = []
        for info in catalog.model_infos:
            infos.append(
                {
                    "id": info.id,
                    "name": info.name or info.id,
                    "tier": info.tier or model_tier(name, info.id),
                    "formats": info.formats or catalog.formats,
                    "pricing": info.limits or {},
                    "context_length": None,
                }
            )
        if infos:
            self.repo.sync_models(name, infos, source=catalog.source)
        self.repo.sync_voices(
            name,
            model_slug="",
            voices=catalog.voices,
            origin="local" if name == "piper" else "provider",
            paths=catalog.details.get("voice_paths") or {},
        )


def create_app() -> FastAPI:
    studio = Studio()
    app = FastAPI(
        title="Zolai TTS Studio API",
        version="0.4.0",
        description="Provider-agnostic Tedim Zolai TTS studio: React UI, FastAPI, SQLModel.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "http://127.0.0.1:7860",
            "http://localhost:7860",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Any, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})

    # ------------------------------------------------------------------ health

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "time": _iso_now(),
            "service": "zolai-tts-studio",
            "version": app.version,
            "providers": known_providers(),
            "store": str(studio.root),
            "database": studio.repo.db.info(),
            "storage": studio.storage.info(),
            "frontend_built": (web_dist_path() / "index.html").is_file(),
        }

    @app.get("/api/providers")
    def providers(tier: str = "any") -> dict[str, Any]:
        policy = studio.tier_policy()
        payload = []
        for entry in list_providers():
            name = str(entry.get("name"))
            rows = studio.repo.list_models(name)
            wanted = tier.lower() if tier and tier != "any" else policy.get(name, "any")
            counts = {
                "any": len(rows),
                "free": len([r for r in rows if r["tier"] in ("free", "free-local")]),
                "paid": len([r for r in rows if r["tier"] == "paid"]),
            }
            payload.append(
                {
                    **entry,
                    "key_present": provider_api_key_present(name)[0],
                    "tier_policy": policy.get(name, "any"),
                    "models_known": counts,
                    "tier_filter_applied": wanted,
                }
            )
        return {"ok": True, "providers": payload, "tier_policy": policy}

    @app.get("/api/meta")
    def meta(tier: str = "any") -> dict[str, Any]:
        policy = studio.tier_policy()
        return {
            "ok": True,
            "version": app.version,
            "default_language": DEFAULT_LANGUAGE,
            "max_text": MAX_TEXT,
            "audio_extensions": sorted(MIME_BY_EXT),
            "recording_mimes": list(RECording_MIMES),
            "languages": [
                {"code": "ted", "label": "Tedim Zolai", "status": "primary"},
                {"code": "en", "label": "English", "status": "bridge"},
                {"code": "my", "label": "Burmese", "status": "experimental"},
                {"code": "mni", "label": "Manipuri/Meitei", "status": "experimental"},
            ],
            "providers": [
                {
                    **entry,
                    "key_present": provider_api_key_present(str(entry.get("name")))[0],
                    "tier_policy": policy.get(str(entry.get("name")), "any"),
                }
                for entry in list_providers()
            ],
            "models": studio.repo.list_models(tier=None if tier == "any" else tier),
            "voices": studio.repo.list_voices(),
            "limits": {
                "provider_limits": PROVIDER_LIMITS,
                "model_text_limits": MODEL_TEXT_LIMITS,
            },
            "storage": studio.storage.info(),
            "database": studio.repo.db.info(),
            "counts": studio.repo.counts(),
            "frontend_built": (web_dist_path() / "index.html").is_file(),
            "generated_at": _iso_now(),
        }

    # ------------------------------------------------------- secrets & settings

    @app.get("/api/secrets")
    def session_secrets() -> dict[str, Any]:
        return {"ok": True, **secrets_view()}

    @app.post("/api/secrets")
    def session_secrets_set(payload: Annotated[dict[str, Any], Body()]) -> Any:
        values = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, dict):
            return _err("Expected {values: {NAME: value}}.")
        try:
            for name, value in values.items():
                set_secret(str(name), "" if value is None else str(value))
        except ValueError as exc:
            return _err(str(exc))
        return {"ok": True, **secrets_view()}

    @app.delete("/api/secrets/{name}")
    def session_secrets_clear(name: str) -> Any:
        from zolai_tts.secrets import clear

        clear(name)
        return {"ok": True, **secrets_view()}

    @app.get("/api/settings")
    def settings_get() -> dict[str, Any]:
        return {
            "ok": True,
            "tier_policy": studio.tier_policy(),
            "budget": studio.budget(),
            "storage": studio.storage.info(),
            "database": studio.repo.db.info(),
        }

    @app.post("/api/settings")
    def settings_post(payload: Annotated[dict[str, Any], Body()]) -> Any:
        changed: list[str] = []
        if "tier_policy" in payload:
            policy = payload["tier_policy"]
            if not isinstance(policy, dict):
                return _err("tier_policy must be an object.")
            clean = {str(k): str(v) for k, v in policy.items() if str(v) in ("any", "free", "paid")}
            studio.repo.set_setting(SETTINGS_TIER, clean)
            changed.append("tier_policy")
        if "budget" in payload:
            budget = payload["budget"]
            if not isinstance(budget, dict):
                return _err("budget must be an object.")
            studio.repo.set_setting(
                SETTINGS_BUDGET,
                {
                    "daily_usd": float(budget.get("daily_usd") or 0.0),
                    "monthly_usd": float(budget.get("monthly_usd") or 0.0),
                    "free_only": bool(budget.get("free_only")),
                },
            )
            changed.append("budget")
        if "storage" in payload:
            preferred = str((payload["storage"] or {}).get("preferred", ""))
            if preferred not in ("local", "r2", "auto"):
                return _err("storage.preferred must be local, r2, or auto.")
            try:
                studio.apply_storage(preferred)
            except (RuntimeError, ValueError) as exc:
                return _err(str(exc))
            changed.append("storage")
        return {"ok": True, "changed": changed, "settings": studio.repo.all_settings()}

    # ----------------------------------------------------------------- catalog

    @app.get("/api/providers/{name}/catalog")
    def provider_catalog(
        name: str, refresh: bool = False, tier: str = "any", base_url: str | None = None
    ) -> Any:
        problem = _validate_name(name, "provider name")
        if problem:
            return _err(problem)
        if name not in known_providers():
            return _err(f"Unknown provider {name!r}.", status=404)
        catalog = studio.catalog(name, refresh=refresh)
        payload = catalog.to_dict()
        policy = studio.tier_policy().get(name, "any")
        # `any` in the query means "no explicit choice", so the stored policy wins.
        requested = tier.lower().strip()
        wanted = requested if requested in ("free", "paid") else policy.lower() or "any"
        if wanted in ("free", "paid"):
            payload["model_infos"] = [
                m for m in payload["model_infos"] if _tier_matches(m.get("tier", ""), wanted)
            ]
            payload["models"] = [m["id"] for m in payload["model_infos"]]
        payload["tier_filter"] = wanted
        payload["tier_policy"] = policy
        return {"ok": catalog.error is None, "catalog": payload, "refreshed": bool(refresh)}

    @app.post("/api/catalog/refresh")
    def catalog_refresh(payload: Annotated[dict[str, Any] | None, Body()]) -> dict[str, Any]:
        names = (payload or {}).get("providers") or known_providers()
        refreshed = {}
        for name in names:
            catalog = studio.catalog(str(name), refresh=True)
            refreshed[str(name)] = {
                "ok": catalog.error is None,
                "models": len(catalog.model_infos),
                "voices": len(catalog.voices),
                "error": catalog.error,
            }
        return {"ok": True, "refreshed": refreshed, "counts": studio.repo.counts()}

    # -------------------------------------------------------------- synthesis

    @app.post("/api/synthesize")
    def synthesize(payload: Annotated[dict[str, Any], Body()]) -> Any:
        provider = str(payload.get("provider", "")).strip().lower()
        problem = _validate_name(provider, "provider name")
        if problem:
            return _err(problem)
        registry_names = {str(p.get("name")) for p in list_providers()}
        if provider not in registry_names:
            return _err(f"Unknown provider {provider!r}.", status=404)

        text = str(payload.get("text", "")).strip()
        if not text:
            return _err("Text is required.")
        cap = MODEL_TEXT_LIMITS.get(str(payload.get("model") or ""), MAX_TEXT)
        if len(text) > cap:
            return _err(f"Text exceeds the {cap}-character limit for this model.", status=422)

        meta = provider_meta(provider)
        language = str(payload.get("language") or DEFAULT_LANGUAGE)
        voice = str(payload.get("voice") or "").strip()
        model = str(payload.get("model") or "").strip() or None
        fmt = str(payload.get("response_format") or "").strip().lower() or None
        dry_run = bool(payload.get("dry_run"))

        plan: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "voice": voice,
            "language": language,
            "response_format": fmt,
            "base_url": payload.get("base_url"),
            "mode": "dry-run" if dry_run else "synthesize",
        }
        if provider == "gemini":
            plan["request"] = gemini_provider.build_interaction_request(
                text, voice=voice, language=language, model=model
            )
        elif provider == "openrouter":
            plan["request"] = openrouter_provider.build_openrouter_request(
                text,
                voice=voice,
                language=language,
                model=model,
                base_url=str(payload.get("base_url") or "") or None,
                response_format=fmt,
            )
        if dry_run:
            return {"ok": True, "dry_run": True, "plan": plan}

        if meta.get("voice_kind") == "path" and not voice:
            return _err("A voice is required: a local .onnx path for Piper.")
        if not voice:
            return _err("A voice is required.")
        if meta.get("hosted") and not provider_api_key_present(provider)[0]:
            return _err(
                f"{provider} requires an API key. Set {provider_api_key_present(provider)[1]} "
                "in the environment or add it in Settings."
            )

        ext = fmt or ("wav" if provider in ("piper", "gemini") else "mp3")
        if not _EXT_RE.match(ext):
            return _err("Invalid audio format.")
        out_name = str(payload.get("out_name") or "").strip()
        if out_name and not _SAFE_ID_RE.match(out_name):
            return _err("out_name must be a short safe name (letters, digits, dash, underscore).")
        run_id = out_name or new_id("run").replace("_", "-")
        if not _SAFE_ID_RE.match(run_id):
            run_id = run_id.replace("run-", "r")[:80]

        # Cost gate, before any money is spent: the estimate is whatever the
        # provider actually publishes (None when nothing is published).
        model_row = studio.repo.list_models(provider)
        info = next((m for m in model_row if m["slug"] == (model or "")), None) or {
            "id": model or ""
        }
        estimate = estimate_cost(provider, text, info)
        tier = estimate.tier or model_tier(provider, model or "")
        gate = check_budget(
            studio.budget_limits(),
            studio.spend_today(),
            studio.spend_month(),
            float(estimate.usd) if estimate.usd is not None else None,
        )
        if not gate["allowed"]:
            return _err(
                {
                    "ok": False,
                    "error": "Budget limit reached",
                    "reasons": gate["reasons"],
                    "estimate": estimate.as_dict(),
                },
                status=402,
            )

        options: dict[str, Any] = {"language": language}
        if model and provider in ("gemini", "openrouter"):
            options["model"] = model
        if provider == "openrouter":
            if payload.get("base_url"):
                options["base_url"] = str(payload["base_url"])
            if fmt:
                options["response_format"] = fmt

        out_path = (studio.root / "outputs" / f"{run_id}.{ext}").resolve()
        started = time.time()
        try:
            engine = get_provider(provider, **options)
            result = engine.synthesize(text, voice, out_path)
        except (ProviderError, ValueError, OSError) as exc:
            record = studio.repo.record_run(
                {
                    "id": run_id,
                    "provider": provider,
                    "model_id": model or "",
                    "voice": voice,
                    "language": language,
                    "text": text,
                    "ok": False,
                    "error": _redact(exc),
                    "elapsed_seconds": round(time.time() - started, 3),
                    "characters": len(text),
                    "tier": tier or "unknown",
                    "dry_run": False,
                    "metadata": {},
                }
            )
            return JSONResponse(
                status_code=502, content={"ok": False, "error": _redact(exc), "run": record}
            )

        data = out_path.read_bytes() if out_path.exists() else b""
        object_key = key_for("runs", run_id, ext)
        backend_name = (
            studio.storage.put(object_key, data, content_type=MIME_BY_EXT.get(ext, "audio/wav"))
            if data
            else "none"
        )
        record = studio.repo.record_run(
            {
                "id": run_id,
                "provider": result.provider,
                "model_id": model or (result.metadata or {}).get("model") or "",
                "voice": result.voice,
                "language": language,
                "text": text,
                "ok": True,
                "format": ext,
                "bytes": len(data),
                "duration_seconds": result.duration_seconds or _audio_duration_seconds(out_path),
                "elapsed_seconds": round(time.time() - started, 3),
                "characters": len(text),
                "cost_usd": float(estimate.usd) if estimate.usd is not None else None,
                "storage_backend": backend_name,
                "object_key": object_key if data else None,
                "local_path": str(out_path),
                "tier": tier or "unknown",
                "dry_run": False,
                "metadata": (result.metadata or {}) | {"cost_note": estimate.basis},
            }
        )
        studio.repo.record_usage(
            {
                "provider": provider,
                "model_id": record["model"],
                "tier": tier or "unknown",
                "characters": len(text),
                "audio_seconds": record["duration_seconds"] or 0.0,
                "cost_usd": float(estimate.usd) if estimate.usd is not None else None,
                "run_id": run_id,
            }
        )
        return {
            "ok": True,
            "dry_run": False,
            "run": record,
            "estimate": estimate.as_dict(),
            "budget": gate,
        }

    # ------------------------------------------------------------------- audio

    @app.get("/api/audio/{run_id}")
    def audio(run_id: str, download: bool = False) -> Any:
        if not _SAFE_ID_RE.match(run_id):
            return _err("Invalid run id.")
        record = studio.repo.get_run(run_id)
        if not record:
            return _err("Run not found.", status=404)
        ext = record.get("format") or "wav"
        local = studio.root / "outputs" / f"{run_id}.{ext}"
        if local.is_file():
            return FileResponse(
                local,
                media_type=MIME_BY_EXT.get(ext, "audio/wav"),
                filename=run_id if download else None,
            )
        if not record.get("object_key"):
            return _err("No audio stored for this run.", status=409)
        return _serve(
            studio,
            record.get("storage_backend"),
            record["object_key"],
            MIME_BY_EXT.get(ext, "audio/wav"),
            download,
            f"{run_id}.{ext}",
        )

    @app.get("/api/runs")
    def runs(limit: int = 50, provider: str = "") -> dict[str, Any]:
        return {
            "ok": True,
            "runs": studio.repo.list_runs(limit=limit, provider=provider or None),
        }

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str) -> Any:
        if not _SAFE_ID_RE.match(run_id):
            return _err("Invalid run id.")
        record = studio.repo.get_run(run_id)
        if not record:
            return _err("Run not found.", status=404)
        return {"ok": True, "run": record, "reviews": studio.repo.list_reviews(run_id=run_id)}

    # -------------------------------------------------------------- recordings

    @app.post("/api/recordings")
    def recordings(
        file: Annotated[UploadFile, File()],
        source: Annotated[Literal["upload", "mic"], Form()] = "upload",
        provider: Annotated[str, Form()] = "studio",
        model: Annotated[str, Form()] = "",
        voice: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
    ) -> Any:
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            return _err(f"Recording exceeds {MAX_UPLOAD_BYTES // 1_000_000} MB.", status=413)
        if not data:
            return _err("Uploaded audio is empty.")
        rec_id = new_id("rec").replace("_", "-")
        ext, mime = _sniff(file.filename or "", file.content_type or "")
        key = key_for("recordings", rec_id, ext)
        backend_name = studio.storage.put(key, data, content_type=mime)
        record = studio.repo.record_recording(
            {
                "id": rec_id,
                "source": source,
                "provider": provider,
                "model": model,
                "voice": voice,
                "note": note,
                "mime": mime,
                "format": ext,
                "bytes": len(data),
                "duration_seconds": _probe_duration(data),
                "storage_backend": backend_name,
                "object_key": key,
                "local_path": str(studio.storage.local_object_path(key) or ""),
            }
        )
        return {"ok": True, "recording": record}

    @app.get("/api/recordings")
    def list_recordings(limit: int = 50) -> dict[str, Any]:
        return {"ok": True, "recordings": studio.repo.list_recordings(limit=limit)}

    @app.get("/api/recordings/{rec_id}/audio")
    def recording_audio(rec_id: str, download: bool = False) -> Any:
        row = studio.repo.get_recording(rec_id)
        if not row:
            return _err("Recording not found.", status=404)
        ext = row.get("format") or "wav"
        return _serve(
            studio,
            row.get("storage_backend"),
            row["object_key"],
            MIME_BY_EXT.get(ext, row.get("mime") or "application/octet-stream"),
            download,
            f"{rec_id}.{ext}",
        )

    # ----------------------------------------------------------- contributions

    @app.post("/api/contributions")
    def contributions(
        file: Annotated[UploadFile, File()],
        speaker_alias: Annotated[str, Form()] = "anonymous",
        language: Annotated[str, Form()] = DEFAULT_LANGUAGE,
        prompt: Annotated[str, Form()] = "",
        consent: Annotated[str, Form()] = "false",
        mic_device: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        license: Annotated[str, Form()] = "cc-by-4.0",
    ) -> Any:
        if consent.strip().lower() not in ("true", "1", "on", "yes"):
            return _err("Consent is required before a take can be contributed.", status=403)
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            return _err(f"Recording exceeds {MAX_UPLOAD_BYTES // 1_000_000} MB.", status=413)
        if not data:
            return _err("Recording is empty.")
        contrib_id = new_id("contrib").replace("_", "-")
        rec_id = new_id("rec").replace("_", "-")
        ext, mime = _sniff(file.filename or "", file.content_type or "")
        key = key_for("contributions", contrib_id, ext)
        backend_name = studio.storage.put(key, data, content_type=mime)
        recording = studio.repo.record_recording(
            {
                "id": rec_id,
                "source": "mic",
                "provider": "contribution",
                "note": f"contribution {contrib_id}",
                "mime": mime,
                "format": ext,
                "bytes": len(data),
                "duration_seconds": _probe_duration(data),
                "storage_backend": backend_name,
                "object_key": key,
            }
        )
        contribution = studio.repo.record_contribution(
            {
                "id": contrib_id,
                "recording_id": rec_id,
                "speaker_alias": speaker_alias,
                "consent": True,
                "license": license,
                "language": language,
                "prompt": prompt,
                "mic_device": mic_device,
                "note": note,
                "storage_backend": backend_name,
                "object_key": key,
                "bytes": len(data),
                "format": ext,
                "duration_seconds": _probe_duration(data),
                "local_path": str(studio.storage.local_object_path(key) or ""),
            }
        )
        return {"ok": True, "contribution": contribution, "recording": recording}

    @app.get("/api/contributions")
    def list_contributions(limit: int = 100, status: str = "") -> dict[str, Any]:
        return {
            "ok": True,
            "contributions": studio.repo.list_contributions(
                limit=limit,
                status=status or None,  # type: ignore[arg-type]
            ),
        }

    @app.get("/api/contributions/{contrib_id}/audio")
    def contribution_audio(contrib_id: str, download: bool = False) -> Any:
        row = studio.repo.get_contribution(contrib_id)
        if not row:
            return _err("Contribution not found.", status=404)
        ext = row.get("format") or "wav"
        return _serve(
            studio,
            row.get("storage_backend"),
            row["object_key"],
            MIME_BY_EXT.get(ext, "application/octet-stream"),
            download,
            f"{contrib_id}.{ext}",
        )

    @app.post("/api/contributions/{contrib_id}/status")
    def contribution_status(contrib_id: str, payload: Annotated[dict[str, Any], Body()]) -> Any:
        status = str(payload.get("status", "")).strip().lower()
        if status not in ("new", "reviewing", "accepted", "rejected"):
            return _err("status must be new, reviewing, accepted, or rejected.")
        row = studio.repo.set_contribution_status(contrib_id, status)  # type: ignore[arg-type]
        if not row:
            return _err("Contribution not found.", status=404)
        return {"ok": True, "contribution": row}

    # ---------------------------------------------------------------- reviews

    @app.post("/api/reviews")
    def add_review(payload: Annotated[dict[str, Any], Body()]) -> Any:
        run_id = str(payload.get("run_id", "")).strip()
        if not studio.repo.get_run(run_id):
            return _err("Run not found.", status=404)
        verdict = str(payload.get("verdict", "maybe")).strip().lower()
        if verdict not in ("pass", "maybe", "fail"):
            return _err("verdict must be pass, maybe, or fail.")
        artifacts = payload.get("artifacts") or []
        if not isinstance(artifacts, list):
            return _err("artifacts must be a list.")
        rating = payload.get("rating")
        if rating is not None and (
            not isinstance(rating, (int, float)) or not 1 <= float(rating) <= 5
        ):
            return _err("rating must be between 1 and 5.")
        review = studio.repo.add_review(
            {
                "id": new_id("rev").replace("_", "-"),
                "run_id": run_id,
                "verdict": verdict,
                "rating": int(rating) if rating is not None else None,
                "artifacts": [str(a) for a in artifacts][:12],
                "note": str(payload.get("note") or "")[:2000],
                "reviewer": str(payload.get("reviewer") or "")[:120],
            }
        )
        return {"ok": True, "review": review}

    @app.get("/api/reviews")
    def list_reviews(run_id: str = "", limit: int = 100) -> dict[str, Any]:
        return {"ok": True, "reviews": studio.repo.list_reviews(run_id=run_id or None, limit=limit)}

    # ------------------------------------------------------------------ usage

    @app.get("/api/usage")
    def usage(days: int = 30) -> dict[str, Any]:
        return {
            "ok": True,
            **studio.repo.usage_summary(days=days),
            "budget": studio.budget(),
            "spend_today_usd": round(studio.spend_today(), 6),
            "spend_month_usd": round(studio.spend_month(), 6),
            "generated_at": _iso_now(),
        }

    @app.get("/api/observer/errors")
    def observer_errors(limit: int = 20) -> dict[str, Any]:
        return {
            "ok": True,
            "errors": studio.repo.recent_errors(limit=limit),
            "counts": studio.repo.counts(),
        }

    @app.get("/api/storage/info")
    def storage_info() -> dict[str, Any]:
        return {"ok": True, **studio.storage.info()}

    # --------------------------------------------------------------- frontend

    @app.get("/")
    def index() -> Response:
        page = web_dist_path() / "index.html"
        if page.is_file():
            return FileResponse(page, headers={"Cache-Control": "no-store"})
        return HTMLResponse(_placeholder_page(), status_code=503)

    @app.get("/{requested_path:path}", include_in_schema=False)
    def spa(requested_path: str) -> Response:
        clean = requested_path.strip("/")
        if clean.startswith("api/"):
            return _err(f"No API route: /{clean}", status=404)
        dist = web_dist_path()
        if clean:
            candidate = (dist / clean).resolve()
            if str(candidate).startswith(str(dist.resolve())) and candidate.is_file():
                immutable = candidate.name != "index.html"
                return FileResponse(
                    candidate,
                    headers={
                        "Cache-Control": "public, max-age=31536000, immutable"
                        if immutable
                        else "no-store"
                    },
                )
        page = dist / "index.html"
        if page.is_file():
            return FileResponse(page, headers={"Cache-Control": "no-store"})
        return HTMLResponse(_placeholder_page(), status_code=503)

    app.state.studio = studio
    return app


def _tier_matches(value: str, wanted: str) -> bool:
    if wanted == "free":
        return value in ("free", "free-local")
    return value == wanted


def _sniff(filename: str, content_type: str) -> tuple[str, str]:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in MIME_BY_EXT:
        guess = {
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mpeg": "mp3",
            "audio/mp4": "mp3",
            "audio/ogg": "ogg",
            "audio/webm": "webm",
            "audio/flac": "flac",
            "audio/opus": "opus",
        }.get(content_type.split(";")[0].strip(), "")
        if not guess:
            raise HTTPException(400, f"Unsupported audio format: {ext or content_type}")
        ext = guess
    return ext, MIME_BY_EXT[ext]


def _probe_duration(data: bytes) -> float | None:
    try:
        info = sf.info(io.BytesIO(data))
        return round(float(info.frames) / float(info.samplerate), 3) if info.samplerate else None
    except Exception:  # noqa: BLE001
        return None


def _serve(
    studio: Studio, backend: str | None, key: str, mime: str, download: bool, name: str
) -> Any:
    if not key or not _KEY_RE.match(key):
        return _err("Malformed object key.")
    local = studio.storage.local_path(backend, key)
    if local is not None:
        return FileResponse(local, media_type=mime, filename=name if download else None)
    try:
        data, _served = studio.storage.read(backend, key)
    except FileNotFoundError:
        return _err("Audio object not found.", status=404)
    except Exception as exc:  # noqa: BLE001
        return _err(f"Storage read failed: {_redact(exc)}", status=502)
    disposition = "attachment" if download else "inline"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'{disposition}; filename="{name}"'},
    )


def _placeholder_page() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Zolai TTS Studio</title>
<style>body{font-family:system-ui;background:#0b0f0d;color:#e6f0ea;display:grid;place-items:center;
min-height:100vh;margin:0;padding:24px}main{max-width:40rem;text-align:center}h1{font-size:1.6rem}
code{background:#16211a;padding:2px 6px;border-radius:4px}
a{color:#34d399}</style></head><body><main>
<h1>Zolai TTS Studio API is running</h1>
<p>The React workspace has not been built into <code>web/dist</code> yet.</p>
<p>Run <code>bun run web:build</code> (or <code>./menu.sh</code> &rarr; <code>Build web app</code>),
or start the Vite dev server on <code>http://127.0.0.1:5174</code>.</p>
<p><a href="/api/health">API health</a> &middot; <a href="/docs">OpenAPI docs</a></p>
</main></body></html>"""


def main(argv: list[str] | None = None) -> int:
    """Console entry point for ``zolai-tts-ui``."""
    import argparse

    # Load the project .env before serving, so provider keys written to the
    # file are visible to per-request env/session readers. Exported vars
    # always win; values are never logged. See zolai_tts/env.py.
    from zolai_tts.env import ensure_loaded

    ensure_loaded()

    parser = argparse.ArgumentParser(
        prog="zolai-tts-ui", description="Serve the Zolai-TTS web app + API."
    )
    parser.add_argument("--host", default=os.getenv("ZOLAI_TTS_UI_HOST", "127.0.0.1"))
    try:
        default_port = int(os.getenv("ZOLAI_TTS_UI_PORT", "7860"))
    except ValueError as exc:
        raise ValueError("ZOLAI_TTS_UI_PORT must be an integer.") from exc
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument(
        "--share", action="store_true", help="Bind 0.0.0.0 instead of localhost only."
    )
    parser.add_argument(
        "--config", help="Optional YAML defaults file (accepted for CLI compatibility)."
    )
    parser.add_argument("--reload", action="store_true", help="Dev reload (uvicorn).")
    args = parser.parse_args(argv)
    if args.config:
        os.environ["ZOLAI_TTS_CONFIG"] = args.config
    import uvicorn

    host = "0.0.0.0" if args.share else args.host
    uvicorn.run("zolai_tts.server:app", host=host, port=args.port, reload=args.reload)
    return 0


app = create_app()


if __name__ == "__main__":
    # `python -m zolai_tts.server` (used by runtime.start) must actually serve;
    # without this guard the module import builds the app and exits.
    raise SystemExit(main())
