"""Repository layer: the only place SQL/ORM queries live.

Everything the API and CLI need is expressed here against SQLModel `select()`
so SQLite and PostgreSQL behave identically. No raw SQL, no dialect functions.
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import func
from sqlmodel import Session, select

from .engine import Database
from .models import (
    Contribution,
    Model,
    Provider,
    Recording,
    Review,
    Run,
    Setting,
    UsageEvent,
    Voice,
    dumps,
    utcnow,
)


def C(field: Any) -> Any:
    """Treat a SQLModel class attribute as its SQL column expression.

    At runtime these are ``InstrumentedAttribute`` objects (they expose
    ``.desc()``, aggregate fine, etc.); static typing only sees the declared
    Python type of the field, so queries route through this one cast.
    """
    return cast("Any", field)


def new_id(prefix: str = "") -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    token = secrets.token_hex(3)
    return f"{prefix}-{stamp}-{token}" if prefix else f"{stamp}-{token}"


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @property
    def dialect(self) -> str:
        return self.db.dialect

    # ---------------------------------------------------------------- helpers

    def _session(self) -> Session:
        return Session(self.db.engine)

    # -------------------------------------------------------------- providers

    def sync_provider(self, meta: dict[str, Any]) -> Provider:
        with self._session() as session:
            row = session.get(Provider, meta["name"])
            if row is None:
                row = Provider(name=meta["name"])
            row.label = str(meta.get("label") or meta["name"])
            row.hosted = bool(meta.get("hosted"))
            row.voice_kind = str(meta.get("voice_kind") or "name")
            row.note = str(meta.get("note") or "")
            row.updated_at = utcnow()
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_providers(self) -> list[dict[str, Any]]:
        with self._session() as session:
            rows = session.exec(select(Provider).order_by(Provider.name)).all()
            return [row.model_dump() for row in rows]

    # ----------------------------------------------------------------- models

    def sync_models(self, provider: str, infos: list[dict[str, Any]], source: str) -> int:
        """Upsert discovered models; returns the count written."""
        written = 0
        with self._session() as session:
            for info in infos:
                slug = str(info.get("id") or info.get("slug") or "")
                if not slug:
                    continue
                pk = {"provider_name": provider, "slug": slug}
                row = session.get(Model, pk)  # type: ignore[arg-type]
                if row is None:
                    row = Model(provider_name=provider, slug=slug)
                row.title = str(info.get("name") or info.get("title") or "")
                row.tier = str(info.get("tier") or "unknown")
                row.formats = dumps(list(info.get("formats") or []))
                row.pricing = dumps(info.get("pricing") or {})
                row.context_length = info.get("context_length")
                row.source = source
                row.updated_at = utcnow()
                session.add(row)
                written += 1
            session.commit()
        return written

    def list_models(
        self, provider: str | None = None, tier: str | None = None
    ) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(Model)
            if provider:
                stmt = stmt.where(Model.provider_name == provider)
            if tier and tier != "any":
                stmt = stmt.where(Model.tier == tier)
            stmt = stmt.order_by(Model.provider_name, Model.slug)
            out: list[dict[str, Any]] = []
            for row in session.exec(stmt).all():
                item = row.model_dump()
                item["formats"] = row.formats_list()
                item["pricing"] = row.pricing_dict()
                out.append(item)
            return out

    # ----------------------------------------------------------------- voices

    def sync_voices(
        self,
        provider: str,
        *,
        model_slug: str,
        voices: list[str],
        origin: str = "provider",
        paths: dict[str, str] | None = None,
    ) -> int:
        written = 0
        paths = paths or {}
        with self._session() as session:
            for name in voices:
                if not name:
                    continue
                existing = session.exec(
                    select(Voice).where(
                        Voice.provider_name == provider,
                        Voice.model_slug == model_slug,
                        Voice.slug == name,
                    )
                ).first()
                row = existing or Voice(
                    id=new_id("voice-"), provider_name=provider, model_slug=model_slug, slug=name
                )
                row.label = name
                row.origin = origin
                row.path = paths.get(name)
                row.updated_at = utcnow()
                session.add(row)
                written += 1
            session.commit()
        return written

    def list_voices(
        self,
        provider: str | None = None,
        model_slug: str | None = None,
        origin: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(Voice)
            if provider:
                stmt = stmt.where(Voice.provider_name == provider)
            if model_slug is not None:
                stmt = stmt.where((Voice.model_slug == model_slug) | (Voice.model_slug == ""))
            if origin:
                stmt = stmt.where(Voice.origin == origin)
            stmt = stmt.order_by(Voice.provider_name, Voice.model_slug, Voice.slug)
            return [row.model_dump() for row in session.exec(stmt).all()]

    # ------------------------------------------------------------------- runs

    def record_run(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._session() as session:
            row = session.get(Run, record["id"])
            if row is None:
                row = Run(id=record["id"], provider_name=record["provider"])
            row.created_at = _to_dt(record.get("created_at")) or utcnow()
            row.provider_name = record["provider"]
            row.model_slug = record.get("model_id") or ""
            row.voice_slug = record.get("voice") or ""
            row.language = record.get("language") or ""
            row.text = record.get("text") or ""
            row.status = "ok" if record.get("ok", True) else "failed"
            row.error = record.get("error")
            row.audio_format = record.get("format")
            row.storage_backend = record.get("storage_backend") or "local"
            row.object_key = record.get("object_key")
            row.local_path = record.get("out_path") or record.get("local_path")
            row.bytes = record.get("bytes")
            row.duration_seconds = record.get("duration_seconds")
            row.elapsed_seconds = record.get("elapsed_seconds")
            row.dry_run = bool(record.get("dry_run"))
            row.tier = str(record.get("tier") or "unknown")
            row.cost_usd = record.get("cost_usd")
            row.characters = record.get("characters")
            row.metadata_json = dumps(record.get("metadata") or {})
            session.add(row)
            session.commit()
            session.refresh(row)
            return self.run_to_dict(row)

    @staticmethod
    def run_to_dict(row: Run) -> dict[str, Any]:
        import json

        data = row.model_dump()
        data["provider"] = data.pop("provider_name")
        data["model"] = data.pop("model_slug")
        data["voice"] = data.pop("voice_slug")
        data["format"] = data.pop("audio_format")
        data["ok"] = data.pop("status") == "ok"
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
        data["created_at"] = data["created_at"].isoformat()
        data["audio_url"] = f"/api/audio/{row.id}"
        if row.local_path:
            data["out_path"] = row.local_path
        return data

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Run, run_id)
            return self.run_to_dict(row) if row else None

    def list_runs(self, limit: int = 50, provider: str | None = None) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(Run).where(Run.dry_run == False)  # noqa: E712
            if provider:
                stmt = stmt.where(Run.provider_name == provider)
            stmt = stmt.order_by(C(Run.created_at).desc()).limit(max(1, min(limit, 500)))
            return [self.run_to_dict(row) for row in session.exec(stmt).all()]

    # -------------------------------------------------------------- recordings

    def record_recording(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._session() as session:
            row = session.get(Recording, record["id"]) or Recording(id=record["id"])
            row.created_at = _to_dt(record.get("created_at")) or utcnow()
            row.source = record.get("source") or "upload"
            row.provider_name = record.get("provider") or ""
            row.model_slug = record.get("model") or ""
            row.voice_slug = record.get("voice") or ""
            row.note = record.get("note") or ""
            row.mime = record.get("mime") or ""
            row.audio_format = record.get("format") or ""
            row.bytes = int(record.get("bytes") or 0)
            row.duration_seconds = record.get("duration_seconds")
            row.storage_backend = record.get("storage_backend") or "local"
            row.object_key = record.get("object_key") or ""
            row.local_path = record.get("local_path") or record.get("saved_path")
            session.add(row)
            session.commit()
            session.refresh(row)
            return self.recording_to_dict(row)

    @staticmethod
    def recording_to_dict(row: Recording) -> dict[str, Any]:
        data = row.model_dump()
        data["provider"] = data.pop("provider_name")
        data["model"] = data.pop("model_slug")
        data["voice"] = data.pop("voice_slug")
        data["format"] = data.pop("audio_format")
        data["created_at"] = data["created_at"].isoformat()
        data["audio_url"] = f"/api/recordings/{row.id}/audio"
        if row.local_path:
            data["saved_path"] = row.local_path
        return data

    def list_recordings(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._session() as session:
            rows = session.exec(
                select(Recording)
                .order_by(C(Recording.created_at).desc())
                .limit(max(1, min(limit, 500)))
            ).all()
            return [self.recording_to_dict(row) for row in rows]

    def get_recording(self, rec_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Recording, rec_id)
            return self.recording_to_dict(row) if row else None

    # ----------------------------------------------------------- contributions

    def record_contribution(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._session() as session:
            row = session.get(Contribution, record["id"]) or Contribution(
                id=record["id"], recording_id=record["recording_id"]
            )
            row.created_at = _to_dt(record.get("created_at")) or utcnow()
            row.speaker_alias = record.get("speaker_alias") or "anonymous"
            row.consent = bool(record.get("consent"))
            row.license = record.get("license") or ""
            row.language = record.get("language") or "ted"
            row.prompt = record.get("prompt") or ""
            row.mic_device = record.get("mic_device") or ""
            row.note = record.get("note") or ""
            row.status = record.get("status") or "new"
            row.recording_id = record["recording_id"]
            row.storage_backend = record.get("storage_backend") or "local"
            row.object_key = record.get("object_key") or ""
            row.local_path = record.get("local_path")
            row.bytes = int(record.get("bytes") or 0)
            row.audio_format = record.get("format") or ""
            row.duration_seconds = record.get("duration_seconds")
            session.add(row)
            session.commit()
            session.refresh(row)
            return self.contribution_to_dict(row)

    @staticmethod
    def contribution_to_dict(row: Contribution) -> dict[str, Any]:
        data = row.model_dump()
        data["format"] = data.pop("audio_format")
        data["created_at"] = data["created_at"].isoformat()
        data["audio_url"] = f"/api/contributions/{row.id}/audio"
        if row.local_path:
            data["saved_path"] = row.local_path
        return data

    def list_contributions(
        self, limit: int = 100, status: str | None = None
    ) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(Contribution)
            if status:
                stmt = stmt.where(Contribution.status == status)
            stmt = stmt.order_by(C(Contribution.created_at).desc()).limit(max(1, min(limit, 500)))
            return [self.contribution_to_dict(row) for row in session.exec(stmt).all()]

    def get_contribution(self, contrib_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Contribution, contrib_id)
            return self.contribution_to_dict(row) if row else None

    def set_contribution_status(self, contrib_id: str, status: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Contribution, contrib_id)
            if row is None:
                return None
            row.status = status
            session.add(row)
            session.commit()
            session.refresh(row)
            return self.contribution_to_dict(row)

    # ---------------------------------------------------------------- reviews

    def add_review(self, review: dict[str, Any]) -> dict[str, Any]:
        with self._session() as session:
            row = session.get(Review, review["id"]) or Review(
                id=review["id"], run_id=review["run_id"]
            )
            row.created_at = _to_dt(review.get("created_at")) or utcnow()
            row.run_id = review["run_id"]
            row.verdict = review.get("verdict") or "maybe"
            row.rating = review.get("rating")
            row.artifacts = dumps(review.get("artifacts") or [])
            row.note = review.get("note") or ""
            row.reviewer = review.get("reviewer") or ""
            session.add(row)
            session.commit()
            session.refresh(row)
            return self.review_to_dict(row)

    @staticmethod
    def review_to_dict(row: Review) -> dict[str, Any]:
        import json

        data = row.model_dump()
        data["artifacts"] = json.loads(data.get("artifacts") or "[]")
        data["created_at"] = data["created_at"].isoformat()
        return data

    def list_reviews(self, run_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._session() as session:
            stmt = select(Review)
            if run_id:
                stmt = stmt.where(Review.run_id == run_id)
            stmt = stmt.order_by(C(Review.created_at).desc()).limit(max(1, min(limit, 500)))
            return [self.review_to_dict(row) for row in session.exec(stmt).all()]

    # --------------------------------------------------------------- settings

    def get_setting(self, key: str, default: Any = None) -> Any:
        import json

        with self._session() as session:
            row = session.get(Setting, key)
            if row is None:
                return default
            try:
                return json.loads(row.value)
            except (TypeError, ValueError):
                return default

    def set_setting(self, key: str, value: Any) -> None:
        with self._session() as session:
            row = session.get(Setting, key) or Setting(key=key)
            row.value = dumps(value)
            row.updated_at = utcnow()
            session.add(row)
            session.commit()

    def all_settings(self) -> dict[str, Any]:
        import json

        with self._session() as session:
            out: dict[str, Any] = {}
            for row in session.exec(select(Setting)).all():
                try:
                    out[row.key] = json.loads(row.value)
                except (TypeError, ValueError):
                    out[row.key] = row.value
            return out

    # ------------------------------------------------------------------ usage

    def record_usage(self, event: dict[str, Any]) -> None:
        with self._session() as session:
            session.add(
                UsageEvent(
                    id=event.get("id") or new_id("usage-"),
                    created_at=_to_dt(event.get("created_at")) or utcnow(),
                    provider_name=event["provider"],
                    model_slug=event.get("model_id") or "",
                    tier=event.get("tier") or "unknown",
                    characters=int(event.get("characters") or 0),
                    audio_seconds=float(event.get("audio_seconds") or 0.0),
                    cost_usd=float(event.get("cost_usd") or 0.0),
                    run_id=event.get("run_id"),
                )
            )
            session.commit()

    def usage_summary(self, days: int = 30) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=max(1, days))
        with self._session() as session:
            totals_row = session.exec(
                select(
                    func.count(C(UsageEvent.id)),
                    func.coalesce(func.sum(UsageEvent.characters), 0),
                    func.coalesce(func.sum(UsageEvent.audio_seconds), 0.0),
                    func.coalesce(func.sum(UsageEvent.cost_usd), 0.0),
                ).where(C(UsageEvent.created_at) >= since)
            ).one()
            by_provider = session.exec(
                select(
                    *[
                        C(UsageEvent.provider_name),
                        C(UsageEvent.tier),
                        func.count(C(UsageEvent.id)),
                        func.coalesce(func.sum(C(UsageEvent.characters)), 0),
                        func.coalesce(func.sum(C(UsageEvent.audio_seconds)), 0.0),
                        func.coalesce(func.sum(C(UsageEvent.cost_usd)), 0.0),
                    ]
                )
                .where(C(UsageEvent.created_at) >= since)
                .group_by(C(UsageEvent.provider_name), C(UsageEvent.tier))
                .order_by(func.coalesce(func.sum(C(UsageEvent.cost_usd)), 0.0).desc())
            ).all()
            by_model = session.exec(
                select(
                    *[
                        C(UsageEvent.provider_name),
                        C(UsageEvent.model_slug),
                        C(UsageEvent.tier),
                        func.count(C(UsageEvent.id)),
                        func.coalesce(func.sum(C(UsageEvent.cost_usd)), 0.0),
                    ]
                )
                .where(C(UsageEvent.created_at) >= since, C(UsageEvent.model_slug) != "")
                .group_by(C(UsageEvent.provider_name), C(UsageEvent.model_slug), C(UsageEvent.tier))
                .order_by(func.coalesce(func.sum(C(UsageEvent.cost_usd)), 0.0).desc())
                .limit(25)
            ).all()

        return {
            "window_days": days,
            "totals": {
                "calls": int(totals_row[0] or 0),
                "characters": int(totals_row[1] or 0),
                "audio_seconds": round(float(totals_row[2] or 0.0), 3),
                "cost_usd": round(float(totals_row[3] or 0.0), 6),
            },
            "by_provider": [
                {
                    "provider": row[0],
                    "tier": row[1],
                    "calls": int(row[2] or 0),
                    "characters": int(row[3] or 0),
                    "audio_seconds": round(float(row[4] or 0.0), 3),
                    "cost_usd": round(float(row[5] or 0.0), 6),
                }
                for row in by_provider
            ],
            "by_model": [
                {
                    "provider": row[0],
                    "model": row[1],
                    "tier": row[2],
                    "calls": int(row[3] or 0),
                    "cost_usd": round(float(row[4] or 0.0), 6),
                }
                for row in by_model
            ],
        }

    def spend(self, since: datetime) -> float:
        """Total recorded USD since a moment (aware datetimes only)."""
        with self._session() as session:
            value = session.exec(
                select(func.coalesce(func.sum(C(UsageEvent.cost_usd)), 0.0)).where(
                    C(UsageEvent.created_at) >= since
                )
            ).one()
        return float(value or 0.0)

    def reclassify_tiers(self) -> dict[str, int]:
        """Re-derive free/paid from the official signals after a rule change.

        Free tiers and pricing come and go, so the classification is a computed
        view over the stored slug/pricing rather than a one-time write. History
        rows (`usage_events`) follow the model rows they reference.
        """
        from ..catalog import model_tier
        from ..costing import classify_tier

        models_updated = 0
        usage_updated = 0
        with self._session() as session:
            tiers: dict[tuple[str, str], str] = {}
            for row in session.exec(select(Model)).all():
                tier = classify_tier(
                    {"id": row.slug, "pricing": row.pricing_dict(), "tier": row.tier},
                    row.provider_name,
                )
                if not tier or tier == "unknown":
                    tier = model_tier(row.provider_name, row.slug) or "unknown"
                tiers[(row.provider_name, row.slug)] = tier
                if tier != row.tier:
                    row.tier = tier
                    session.add(row)
                    models_updated += 1
            for event in session.exec(select(UsageEvent)).all():
                derived = tiers.get((event.provider_name, event.model_slug))
                if not derived:
                    derived = model_tier(event.provider_name, event.model_slug) or event.tier
                if derived and derived != event.tier:
                    event.tier = derived
                    session.add(event)
                    usage_updated += 1
            session.commit()
        return {"models_updated": models_updated, "usage_updated": usage_updated}

    # --------------------------------------------------------------- observer

    def recent_errors(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._session() as session:
            rows = session.exec(
                select(Run)
                .where(Run.status == "failed")
                .order_by(C(Run.created_at).desc())
                .limit(max(1, min(limit, 100)))
            ).all()
            return [
                {
                    "id": row.id,
                    "created_at": row.created_at.isoformat(),
                    "provider": row.provider_name,
                    "model": row.model_slug,
                    "voice": row.voice_slug,
                    "error": row.error,
                }
                for row in rows
            ]

    def counts(self) -> dict[str, int]:
        targets = {
            "providers": Provider,
            "models": Model,
            "voices": Voice,
            "runs": Run,
            "recordings": Recording,
            "contributions": Contribution,
            "reviews": Review,
            "usage_events": UsageEvent,
        }
        out: dict[str, int] = {}
        with self._session() as session:
            for name, model in targets.items():
                out[name] = int(session.exec(select(func.count()).select_from(model)).one())
        return out


def _to_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None
