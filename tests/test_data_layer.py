"""Data-layer tests: SQLModel repositories, portability, storage, secrets, costing.

No network, no provider calls. Portability is checked by compiling the same
ORM statements against the SQLite *and* PostgreSQL dialects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlmodel import select

from zolai_tts import costing, secrets, storage
from zolai_tts.db import Repository, new_id
from zolai_tts.db.engine import Database, dialect_of, resolve_database_url
from zolai_tts.db.models import Run, UsageEvent, Voice


@pytest.fixture()
def repo(tmp_path: Path) -> Repository:
    db = Database(f"sqlite:///{tmp_path / 'studio.db'}")
    return Repository(db)


# --------------------------------------------------------------- url handling


def test_resolve_database_url_forms() -> None:
    assert dialect_of(resolve_database_url("sqlite:////tmp/a.db")) == "sqlite"
    assert resolve_database_url("postgres://u:p@h/db").startswith("postgresql+psycopg://")
    assert resolve_database_url("/tmp/plain.db").startswith("sqlite:////tmp/plain.db")


def test_url_resolution_prefers_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOLAI_TTS_DB_URL", f"sqlite:///{tmp_path / 'from-env.db'}")
    assert resolve_database_url(None).endswith("from-env.db")
    assert resolve_database_url("sqlite:////other.db").endswith("other.db")


def test_invalid_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported database URL"):
        resolve_database_url("mysql://user@host/db")


def test_database_info_masks_credentials() -> None:
    info = Database("postgresql://alice:sup3rs3cret@example.com:5432/zolai", create=False).info()
    assert info["dialect"] == "postgresql"
    assert "sup3rs3cret" not in info["url"] and "alice" not in info["url"]


# ----------------------------------------------------------------- portability


def test_queries_compile_on_both_dialects() -> None:
    """The same statements must render on SQLite and PostgreSQL (no dialect SQL)."""
    from sqlalchemy import func
    from sqlalchemy.dialects import sqlite

    statements = [
        select(Run).where(Run.dry_run == False).order_by(Run.created_at.desc()).limit(10),  # noqa: E712
        select(Voice).where(Voice.provider_name == "piper"),
        select(UsageEvent.provider_name, UsageEvent.tier, func.count(UsageEvent.id)).group_by(
            UsageEvent.provider_name, UsageEvent.tier
        ),
    ]
    for stmt in statements:
        sqlite_sql = str(stmt.compile(dialect=sqlite.dialect()))
        pg_sql = str(stmt.compile(dialect=postgresql.dialect()))
        # Same tables and filters on both engines; only quoting/binds differ.
        assert "strftime" not in pg_sql.lower() and "datetime(" not in sqlite_sql.lower()
        assert sqlite_sql.split()[0].upper() == pg_sql.split()[0].upper() == "SELECT"
    assert "LIMIT" in str(statements[0].compile(dialect=postgresql.dialect()))


def test_varchar_columns_have_no_length_limit(repo: Repository) -> None:
    """Portable schema: no VARCHAR(n) truncation surprises between dialects."""
    from sqlalchemy.schema import CreateTable

    ddl = str(CreateTable(Run.__table__).compile(dialect=postgresql.dialect()))
    assert "VARCHAR(" not in ddl.upper(), ddl


# ------------------------------------------------------------- catalog tables


def test_provider_model_voice_roundtrip(repo: Repository) -> None:  # noqa: D103
    repo.sync_provider({"name": "openrouter", "label": "OpenRouter", "hosted": True})
    repo.sync_models(
        "openrouter",
        [
            {
                "id": "openai/gpt-4o-mini-tts",
                "name": "4o-mini TTS",
                "tier": "paid",
                "formats": ["mp3"],
            },
            {
                "id": "google/gemini-2.5-flash-preview-tts:free",
                "name": "Gemini TTS free",
                "tier": "free",
                "formats": ["mp3"],
            },
        ],
        source="live",
    )
    repo.sync_voices("openrouter", model_slug="openai/gpt-4o-mini-tts", voices=["alloy", "nova"])

    assert [p["name"] for p in repo.list_providers()] == ["openrouter"]
    free = repo.list_models("openrouter", tier="free")
    assert [m["slug"] for m in free] == ["google/gemini-2.5-flash-preview-tts:free"]
    assert free[0]["formats"] == ["mp3"]
    assert {v["slug"] for v in repo.list_voices("openrouter")} == {"alloy", "nova"}

    # upsert twice keeps one row per key
    repo.sync_models(
        "openrouter", [{"id": "openai/gpt-4o-mini-tts", "tier": "paid"}], source="live"
    )
    assert len(repo.list_models("openrouter")) == 2


def test_voice_paths_survive_for_local_providers(repo: Repository) -> None:
    repo.sync_provider({"name": "piper", "voice_kind": "path"})
    repo.sync_voices(
        "piper",
        model_slug="",
        voices=["/voices/zolai.onnx"],
        origin="local",
        paths={"/voices/zolai.onnx": "/voices/zolai.onnx"},
    )
    row = repo.list_voices("piper")[0]
    assert row["path"] == "/voices/zolai.onnx"
    assert row["origin"] == "local"


# -------------------------------------------------------------- runs/recordings


def test_run_roundtrip_shape(repo: Repository) -> None:
    created = repo.record_run(
        {
            "id": "run-1",
            "provider": "piper",
            "model_id": "zed",
            "voice": "/v.onnx",
            "language": "ted",
            "text": "Dam maw kongzong",
            "ok": True,
            "format": "wav",
            "bytes": 3200,
            "duration_seconds": 1.2,
            "elapsed_seconds": 0.4,
            "characters": 17,
            "cost_usd": 0.0,
            "storage_backend": "local",
            "object_key": "runs/2026/11/run-1.wav",
            "out_path": "/store/outputs/run-1.wav",
            "metadata": {"engine": "piper"},
        }
    )
    assert created["audio_url"] == "/api/audio/run-1"
    assert created["out_path"] == "/store/outputs/run-1.wav"
    assert created["metadata"] == {"engine": "piper"}
    assert created["format"] == "wav"
    assert repo.get_run("run-1")["text"] == "Dam maw kongzong"
    assert [r["id"] for r in repo.list_runs()] == ["run-1"]


def test_failed_run_is_persisted_and_listed_by_observer(repo: Repository) -> None:
    repo.record_run({"id": "run-bad", "provider": "gemini", "ok": False, "error": "429 slow down"})
    assert repo.get_run("run-bad")["ok"] is False
    errors = repo.recent_errors()
    assert errors[0]["error"] == "429 slow down"


def test_dry_runs_are_not_listed(repo: Repository) -> None:
    repo.record_run({"id": "run-dry", "provider": "piper", "ok": True, "dry_run": True})
    repo.record_run({"id": "run-real", "provider": "piper", "ok": True})
    assert [r["id"] for r in repo.list_runs()] == ["run-real"]


def test_recording_and_contribution_link(repo: Repository) -> None:
    rec = repo.record_recording(
        {
            "id": "rec-1",
            "source": "mic",
            "provider": "contribution",
            "format": "webm",
            "bytes": 999,
            "object_key": "recordings/2026/11/rec-1.webm",
            "local_path": "/store/recordings/rec-1.webm",
        }
    )
    assert rec["saved_path"] == "/store/recordings/rec-1.webm"
    contrib = repo.record_contribution(
        {
            "id": "contrib-1",
            "recording_id": "rec-1",
            "speaker_alias": "pa-khoi",
            "consent": True,
            "license": "cc-by-4.0",
            "format": "webm",
            "object_key": "contributions/2026/11/contrib-1.webm",
        }
    )
    assert contrib["audio_url"] == "/api/contributions/contrib-1/audio"
    assert repo.list_contributions()[0]["status"] == "new"
    updated = repo.set_contribution_status("contrib-1", "accepted")
    assert updated["status"] == "accepted"
    assert repo.set_contribution_status("missing", "accepted") is None


def test_reviews_store_artifact_tags(repo: Repository) -> None:
    repo.record_run({"id": "run-r", "provider": "piper", "ok": True})
    review = repo.add_review(
        {
            "id": "rev-1",
            "run_id": "run-r",
            "verdict": "fail",
            "rating": 2,
            "artifacts": ["vowel", "speed"],
            "note": "second vowel clipped",
        }
    )
    assert review["artifacts"] == ["vowel", "speed"]
    assert repo.list_reviews(run_id="run-r")[0]["rating"] == 2


def test_settings_roundtrip_and_types(repo: Repository) -> None:
    assert repo.get_setting("missing", {"fallback": 1}) == {"fallback": 1}
    repo.set_setting("tier_policy", {"openrouter": "free"})
    repo.set_setting("budget", {"daily_usd": 2.5, "free_only": True})
    assert repo.all_settings() == {
        "tier_policy": {"openrouter": "free"},
        "budget": {"daily_usd": 2.5, "free_only": True},
    }


# --------------------------------------------------------------------- usage


def test_usage_summary_and_spend(repo: Repository) -> None:
    repo.record_usage(
        {
            "provider": "openrouter",
            "model_id": "m1",
            "tier": "paid",
            "characters": 100,
            "cost_usd": 0.002,
        }
    )
    repo.record_usage(
        {
            "provider": "openrouter",
            "model_id": "m1",
            "tier": "paid",
            "characters": 50,
            "cost_usd": 0.001,
        }
    )
    repo.record_usage(
        {
            "provider": "piper",
            "model_id": "",
            "tier": "free-local",
            "characters": 10,
            "cost_usd": 0.0,
        }
    )
    summary = repo.usage_summary(days=1)
    assert summary["totals"]["calls"] == 3
    assert summary["totals"]["characters"] == 160
    assert summary["totals"]["cost_usd"] == pytest.approx(0.003)
    assert summary["by_provider"][0]["provider"] == "openrouter"
    assert summary["by_model"][0]["calls"] == 2
    assert repo.spend(datetime.now(UTC).replace(year=2000)) == pytest.approx(0.003)
    assert repo.spend(datetime.now(UTC).replace(year=2999)) == 0.0


def test_ids_are_unique_and_prefixed() -> None:
    ids = {new_id("run") for _ in range(50)}
    assert len(ids) == 50
    assert all(i.startswith("run-") for i in ids)


# ------------------------------------------------------------------- storage


def test_local_storage_roundtrip_and_escape(tmp_path: Path) -> None:
    hub = storage.StorageHub(
        local=storage.LocalStorage(tmp_path),
        r2=storage.R2Storage(bucket="", account_id="", access_key_id="", secret_access_key=""),
        preferred="local",
    )
    key = storage.key_for("runs", "abc123", "wav")
    assert key.startswith("runs/") and key.endswith(".wav")
    assert hub.put(key, b"RIFFdata", content_type="audio/wav") == "local"
    data, served = hub.read("local", key)
    assert (data, served) == (b"RIFFdata", "local")
    assert hub.local_path("local", key) is not None
    hub.delete("local", key)
    assert not hub.local.exists(key)

    with pytest.raises(ValueError, match="escapes"):
        hub.local.get("../../etc/passwd")


def test_r2_requires_configuration(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not configured"):
        storage.build_storage("r2", store_root=tmp_path)


def test_r2_client_uses_s3_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class FakeClient:
        def put_object(self, **kwargs: object) -> None:
            seen.update(kwargs)

        def generate_presigned_url(self, *_a: object, **_k: object) -> str:
            return "https://r2.example/presigned"

    r2 = storage.R2Storage(
        bucket="zolai-audio",
        account_id="abc123def456",
        access_key_id="AKIAxxxxxxxxxxxx",
        secret_access_key="secret",
    )
    assert r2.configured and r2.endpoint_url == "https://abc123def456.r2.cloudflarestorage.com"
    r2._client = FakeClient()
    r2.put("runs/2026/11/x.wav", b"bytes", content_type="audio/wav")
    assert seen["Bucket"] == "zolai-audio" and seen["Key"] == "runs/2026/11/x.wav"
    assert r2.presign("runs/2026/11/x.wav") == "https://r2.example/presigned"
    info = r2.info()
    assert "secret" not in str(info) and "AKIAxxxxxxxxxxxx" not in str(info)


def test_hub_falls_back_to_local_mirror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class BrokenR2(storage.R2Storage):
        def put(self, key: str, data: bytes, content_type: str = "audio/wav") -> None:
            return None  # claims success so the hub records the r2 backend

        def get(self, key: str) -> bytes:
            raise RuntimeError("bucket offline")

    local = storage.LocalStorage(tmp_path)
    hub = storage.StorageHub(
        local=local,
        r2=BrokenR2(bucket="b", account_id="a", access_key_id="k", secret_access_key="s"),
        preferred="r2",
    )
    key = "runs/2026/11/fallback.wav"
    assert hub.put(key, b"RIFFmirror") == "r2"
    data, served = hub.read("r2", key)
    assert served == "local" and data == b"RIFFmirror"


# -------------------------------------------------------------------- secrets


def test_secret_names_are_allowlisted() -> None:
    secrets.clear()
    with pytest.raises(ValueError, match="not settable"):
        secrets.set_secret("AWS_SECRET_ACCESS_KEY", "nope")
    secrets.set_secret("OPENROUTER_API_KEY", "sk-or-v1-secretvalue")
    assert secrets.get_secret("OPENROUTER_API_KEY") == "sk-or-v1-secretvalue"
    status = secrets.status()
    blob = str(status)
    assert "sk-or-v1-secretvalue" not in blob
    assert status["secrets"]["OPENROUTER_API_KEY"]["source"] == "session"
    secrets.clear("OPENROUTER_API_KEY")
    assert not secrets.get_secret("OPENROUTER_API_KEY")


def test_secret_resolution_prefers_session_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-value")
    secrets.clear()
    assert secrets.resolve(("GEMINI_API_KEY",)) == ("env-value", "environment")
    secrets.set_secret("GEMINI_API_KEY", "session-value")
    value, source = secrets.resolve(("GEMINI_API_KEY",))
    assert (value, source) == ("session-value", "session")
    secrets.clear()


# -------------------------------------------------------------------- costing


def test_tier_classification() -> None:
    assert costing.classify_tier({"id": "google/gemini-2.5-flash-tts:free"}) == "free"
    assert (
        costing.classify_tier({"id": "openai/gpt-4o-mini-tts", "pricing": {"audio": "0.006"}})
        == "paid"
    )
    assert costing.classify_tier({"id": "x", "pricing": {"text": "0"}}) == "free"
    assert costing.classify_tier({"id": "x"}) == "unknown"
    # provider rules apply when the catalog carries no pricing block
    assert costing.classify_tier({"id": "piper-zolai"}, provider="piper") == "free-local"


def test_estimate_uses_published_prices_and_never_invents_one() -> None:
    priced = costing.estimate_cost("openrouter", "a" * 100, {"pricing": {"characters": "0.000015"}})
    assert priced.usd is not None and float(priced.usd) == pytest.approx(0.0015)
    assert priced.basis == "catalog per-character price"

    free = costing.estimate_cost("openrouter", "hello", {"id": "x:free"})
    assert free.usd == 0 and "free tier" in free.basis

    curated = costing.estimate_cost("openrouter", "b" * 400, {"id": "openai/gpt-4o-mini-tts"})
    assert curated.usd is not None and float(curated.usd) > 0
    assert "estimate" in curated.basis or "input" in curated.basis

    unknown = costing.estimate_cost("openrouter", "hello", {"id": "some/new-tts"})
    assert unknown.usd is None
    assert "not published" in unknown.basis or "no published price" in unknown.basis


def test_budget_gate_blocks_paid_when_free_only() -> None:
    limits = costing.BudgetLimits(daily_usd=1.0, monthly_usd=5.0, free_only=False)
    assert costing.check_budget(limits, 0.1, 0.2, 0.5)["allowed"] is True
    assert costing.check_budget(limits, 0.9, 0.2, 0.5)["allowed"] is False
    blocked = costing.check_budget(costing.BudgetLimits(free_only=True), 0.0, 0.0, 0.01)
    assert "free-only" in blocked["reasons"][0]
    assert costing.check_budget(costing.BudgetLimits(), 99.0, 99.0, 5.0)["allowed"] is True
    # unknown price: allowed normally, blocked in free-only mode
    assert costing.check_budget(limits, 0.0, 0.0, None)["allowed"] is True
    unknown = costing.check_budget(costing.BudgetLimits(free_only=True), 0.0, 0.0, None)
    assert not unknown["allowed"] and "no published price" in unknown["reasons"][0]


def test_actual_cost_reads_provider_usage() -> None:
    assert float(costing.actual_cost({"cost_usd": "0.004"})) == pytest.approx(0.004)
    assert float(costing.actual_cost({"usage": {"total_usd": 0.01}})) == pytest.approx(0.01)
    assert costing.actual_cost({}) is None
