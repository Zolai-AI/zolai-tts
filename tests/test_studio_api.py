"""Tests for the studio API surface added with the SQLModel data layer.

Everything is monkeypatched: no provider network calls, no real API keys.
Each test gets its own database file and object-storage root.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
import soundfile as sf
from fastapi.testclient import TestClient

import zolai_tts.server as server
from zolai_tts.inference.base import SynthesisResult


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Isolated studio: SQLite + local object store inside tmp_path."""
    monkeypatch.setenv("ZOLAI_TTS_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("ZOLAI_TTS_DB_URL", f"sqlite:///{tmp_path / 'studio.db'}")
    monkeypatch.setenv("ZOLAI_TTS_STORAGE_BACKEND", "local")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ZOLAI_TTS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZOLAI_TTS_OPENROUTER_API_KEY", raising=False)

    from zolai_tts.db import engine as engine_module
    from zolai_tts import secrets as secrets_module

    engine_module.reset_database()
    secrets_module.clear()  # session store is process-wide; isolate per test
    server._catalog_cache_clear()
    app = server.create_app()
    with TestClient(app) as test_client:
        yield test_client
    server._catalog_cache_clear()
    secrets_module.clear()
    engine_module.reset_database()


def _wav_bytes(seconds: float = 0.25, rate: int = 22050) -> bytes:
    buffer = io.BytesIO()
    frames = int(seconds * rate)
    sf.write(buffer, [0.0] * frames, rate, format="WAV")
    return buffer.getvalue()


class FakeEngine:
    name = "piper"

    def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(_wav_bytes())
        return SynthesisResult(
            out_path=out_path, provider="piper", voice=voice, metadata={"model": "fake"}
        )


# --------------------------------------------------------------------- health


def test_health_reports_database_and_storage(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["database"]["dialect"] == "sqlite"
    assert "password" not in json.dumps(body["database"])
    assert body["storage"]["active"] == "local"
    assert body["frontend_built"] in (True, False)


def test_meta_shape_is_ui_ready(client: TestClient) -> None:
    body = client.get("/api/meta").json()
    assert {lang["code"] for lang in body["languages"]} >= {"ted", "en"}
    assert body["default_language"] == "ted"
    assert "wav" in body["audio_extensions"]
    assert "audio/webm" in body["recording_mimes"]
    assert body["limits"]["provider_limits"]["piper"]["note"]
    assert "counts" in body and "storage" in body and "database" in body
    assert isinstance(body["models"], list) and isinstance(body["voices"], list)


# ------------------------------------------------------------------- secrets


def test_secrets_are_write_only_and_masked(client: TestClient) -> None:
    status = client.get("/api/secrets").json()
    assert status["secrets"]["OPENROUTER_API_KEY"]["present"] is False

    res = client.post(
        "/api/secrets", json={"values": {"OPENROUTER_API_KEY": "session-key-not-a-real-secret"}}
    )
    body = res.json()
    assert body["ok"] is True
    assert "supersecret" not in json.dumps(body)
    entry = body["secrets"]["OPENROUTER_API_KEY"]
    assert entry["present"] is True and entry["source"] == "session"

    cleared = client.delete("/api/secrets/OPENROUTER_API_KEY").json()
    assert cleared["secrets"]["OPENROUTER_API_KEY"]["source"] == "missing"


def test_secrets_reject_unknown_names(client: TestClient) -> None:
    res = client.post("/api/secrets", json={"values": {"AWS_SECRET_ACCESS_KEY": "nope"}})
    assert res.status_code == 400
    assert "not settable" in res.json()["error"]


def test_session_key_is_used_by_catalog_fetch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key set through the API must reach the catalog fetcher, not the DB."""
    seen: dict[str, Any] = {}

    from zolai_tts import catalog

    def fake_fetch(name: str, **kwargs: Any) -> catalog.ProviderCatalog:
        seen["api_key"] = kwargs.get("api_key")
        return catalog.fallback_catalog(name)

    monkeypatch.setattr(server, "fetch_catalog", fake_fetch)
    client.post("/api/secrets", json={"values": {"OPENROUTER_API_KEY": "session-key-123"}})
    client.get("/api/providers/openrouter/catalog")
    assert seen["api_key"] == "session-key-123"


# ------------------------------------------------------------------ settings


def test_settings_roundtrip_persists_to_database(client: TestClient) -> None:
    res = client.post(
        "/api/settings",
        json={
            "tier_policy": {"openrouter": "free", "gemini": "nonsense"},
            "budget": {"daily_usd": 1.25, "monthly_usd": 10, "free_only": True},
        },
    )
    assert res.json()["changed"] == ["tier_policy", "budget"]
    body = client.get("/api/settings").json()
    assert body["tier_policy"] == {"openrouter": "free"}  # invalid value dropped
    assert body["budget"] == {"daily_usd": 1.25, "monthly_usd": 10.0, "free_only": True}


def test_settings_rejects_bad_storage_backend(client: TestClient) -> None:
    res = client.post("/api/settings", json={"storage": {"preferred": "s3"}})
    assert res.status_code == 400
    assert "local, r2, or auto" in res.json()["error"]


def test_storage_r2_requires_configuration(client: TestClient) -> None:
    res = client.post("/api/settings", json={"storage": {"preferred": "r2"}})
    assert res.status_code == 400
    assert "not configured" in res.json()["error"]


# ------------------------------------------------------------------- synthesize


def test_synthesize_persists_run_usage_and_audio(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server, "get_provider", lambda *a, **k: FakeEngine())
    res = client.post(
        "/api/synthesize",
        json={
            "provider": "piper",
            "text": "Dam maw kongzong hi.",
            "voice": "/voices/zolai.onnx",
            "language": "ted",
            "out_name": "dbtestrun",
        },
    )
    assert res.status_code == 200
    run = res.json()["run"]
    assert run["ok"] is True and run["format"] == "wav"
    assert run["object_key"].startswith("runs/")
    assert run["out_path"].endswith("dbtestrun.wav")
    assert run["duration_seconds"] and run["duration_seconds"] > 0

    audio = client.get("/api/audio/dbtestrun")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"

    usage = client.get("/api/usage").json()
    assert usage["totals"]["calls"] >= 1
    assert usage["by_provider"][0]["provider"] == "piper"
    assert usage["by_provider"][0]["tier"] == "free-local"


def test_free_only_budget_blocks_paid_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server, "get_provider", lambda *a, **k: FakeEngine())
    client.post("/api/settings", json={"budget": {"free_only": True}})
    res = client.post(
        "/api/synthesize",
        json={
            "provider": "openrouter",
            "text": "Pasian hi.",
            "voice": "alloy",
            "model": "google/gemini-2.5-flash-tts",
        },
    )
    assert res.status_code == 402
    body = res.json()
    assert body["reasons"] and body["estimate"]["estimated_usd"] is None


def test_budget_blocks_when_daily_limit_exceeded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class PricedEngine(FakeEngine):
        name = "openrouter"

        def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult:
            out_path.write_bytes(_wav_bytes())
            return SynthesisResult(
                out_path=out_path, provider="openrouter", voice=voice, metadata={}
            )

    monkeypatch.setattr(server, "get_provider", lambda *a, **k: PricedEngine())
    client.post("/api/settings", json={"budget": {"daily_usd": 0.0001}})
    res = client.post(
        "/api/synthesize",
        json={
            "provider": "openrouter",
            "text": "a" * 4000,
            "voice": "alloy",
            "model": "openai/gpt-4o-mini-tts",  # curated price -> over the limit
        },
    )
    assert res.status_code == 402
    assert "daily" in res.json()["reasons"][0]


def test_failed_run_is_recorded_and_visible(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: Any, **_k: Any) -> Any:
        raise server.ProviderError("upstream 429 slow down")

    monkeypatch.setattr(server, "get_provider", boom)
    res = client.post(
        "/api/synthesize",
        json={"provider": "piper", "text": "Hi", "voice": "/v.onnx"},
    )
    assert res.status_code == 502
    errors = client.get("/api/observer/errors").json()["errors"]
    assert errors[0]["error"] == "upstream 429 slow down"
    assert client.get("/api/observer/errors").json()["counts"]["runs"] == 1


def test_tier_policy_filters_catalog_by_default(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zolai_tts import catalog

    def fake_fetch(name: str, **kwargs: Any) -> catalog.ProviderCatalog:
        return catalog.ProviderCatalog(
            provider=name,
            models=["paid-model", "free-model:free"],
            model_infos=[
                catalog.ModelInfo(id="paid-model", name="Paid", tier="paid"),
                catalog.ModelInfo(id="free-model:free", name="Free", tier="free"),
            ],
            voices=["alloy"],
            formats=["mp3"],
            source="test",
        )

    monkeypatch.setattr(server, "fetch_catalog", fake_fetch)
    all_models = client.get("/api/providers/openrouter/catalog").json()["catalog"]
    assert len(all_models["model_infos"]) == 2

    client.post("/api/settings", json={"tier_policy": {"openrouter": "free"}})
    filtered = client.get("/api/providers/openrouter/catalog").json()["catalog"]
    assert [m["id"] for m in filtered["model_infos"]] == ["free-model:free"]
    assert filtered["tier_filter"] == "free"

    # an explicit query overrides the stored policy
    paid = client.get("/api/providers/openrouter/catalog?tier=paid").json()["catalog"]
    assert [m["id"] for m in paid["model_infos"]] == ["paid-model"]


def test_catalog_persists_models_and_voices(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zolai_tts import catalog

    def fake_fetch(name: str, **kwargs: Any) -> catalog.ProviderCatalog:
        return catalog.ProviderCatalog(
            provider=name,
            models=["m1"],
            model_infos=[
                catalog.ModelInfo(id="m1", name="Model One", tier="free", voices=["Kore"])
            ],
            voices=["Kore", "Puck"],
            formats=["wav"],
            source="test",
        )

    monkeypatch.setattr(server, "fetch_catalog", fake_fetch)
    client.get("/api/providers/gemini/catalog")
    body = client.get("/api/meta").json()
    assert [m["slug"] for m in body["models"] if m["provider_name"] == "gemini"] == ["m1"]
    assert {v["slug"] for v in body["voices"] if v["provider_name"] == "gemini"} == {"Kore", "Puck"}
    assert body["counts"]["models"] >= 1


# ---------------------------------------------------------------- recordings


def test_recording_upload_stores_object_and_row(client: TestClient) -> None:
    res = client.post(
        "/api/recordings",
        files={"file": ("take.wav", _wav_bytes(), "audio/wav")},
        data={"source": "mic", "provider": "piper", "note": "field take"},
    )
    assert res.status_code == 200
    row = res.json()["recording"]
    assert row["format"] == "wav" and row["bytes"] > 0
    assert row["duration_seconds"] and row["duration_seconds"] > 0
    assert Path(row["saved_path"]).is_file()

    listed = client.get("/api/recordings").json()["recordings"]
    assert listed[0]["id"] == row["id"]
    audio = client.get(f"/api/recordings/{row['id']}/audio")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"


def test_recording_rejects_oversize(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 16)
    res = client.post("/api/recordings", files={"file": ("big.wav", b"x" * 64, "audio/wav")})
    assert res.status_code == 413


def test_recording_rejects_unknown_format(client: TestClient) -> None:
    res = client.post("/api/recordings", files={"file": ("song.flac2", b"x", "application/x-flac")})
    assert res.status_code == 400


# -------------------------------------------------------------- contributions


def test_contribution_requires_consent(client: TestClient) -> None:
    res = client.post(
        "/api/contributions",
        files={"file": ("take.wav", _wav_bytes(), "audio/wav")},
        data={"consent": "false", "speaker_alias": "pa-khoi"},
    )
    assert res.status_code == 403
    assert "Consent" in res.json()["error"]


def test_contribution_flow_with_review_status(client: TestClient) -> None:
    res = client.post(
        "/api/contributions",
        files={"file": ("take.wav", _wav_bytes(), "audio/wav")},
        data={
            "consent": "true",
            "speaker_alias": "pa-khoi",
            "language": "ted",
            "prompt": "Kamsinlo.",
            "license": "cc-by-4.0",
            "note": "Tamwe speaker",
        },
    )
    assert res.status_code == 200
    contribution = res.json()["contribution"]
    assert contribution["status"] == "new" and contribution["consent"] is True
    assert contribution["audio_url"].startswith("/api/contributions/")

    audio = client.get(contribution["audio_url"])
    assert audio.status_code == 200

    updated = client.post(
        f"/api/contributions/{contribution['id']}/status", json={"status": "accepted"}
    ).json()["contribution"]
    assert updated["status"] == "accepted"

    bad = client.post(f"/api/contributions/{contribution['id']}/status", json={"status": "maybe"})
    assert bad.status_code == 400

    filtered = client.get("/api/contributions?status=accepted").json()["contributions"]
    assert [c["id"] for c in filtered] == [contribution["id"]]
    assert client.get("/api/contributions?status=rejected").json()["contributions"] == []


# ------------------------------------------------------------------- reviews


def _make_run(client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str) -> str:
    monkeypatch.setattr(server, "get_provider", lambda *a, **k: FakeEngine())
    res = client.post(
        "/api/synthesize",
        json={"provider": "piper", "text": "Dam maw.", "voice": "/v.onnx", "out_name": name},
    )
    assert res.status_code == 200
    return name


def test_review_verdict_artifacts_and_history(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _make_run(client, monkeypatch, "reviewrun1")
    res = client.post(
        "/api/reviews",
        json={
            "run_id": run_id,
            "verdict": "fail",
            "rating": 2,
            "artifacts": ["vowel", "tone"],
            "note": "final vowel raised",
            "reviewer": "peter",
        },
    )
    assert res.status_code == 200
    review = res.json()["review"]
    assert review["artifacts"] == ["vowel", "tone"] and review["rating"] == 2

    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["reviews"][0]["verdict"] == "fail"
    assert client.get(f"/api/reviews?run_id={run_id}").json()["reviews"]

    # validation
    assert (
        client.post("/api/reviews", json={"run_id": run_id, "verdict": "great"}).status_code == 400
    )
    assert client.post("/api/reviews", json={"run_id": run_id, "rating": 9}).status_code == 400
    assert (
        client.post("/api/reviews", json={"run_id": "missing", "verdict": "pass"}).status_code
        == 404
    )


def test_run_detail_missing_returns_404(client: TestClient) -> None:
    assert client.get("/api/runs/nosuchrun").status_code == 404
    assert client.get("/api/audio/nosuchrun").status_code == 404


# --------------------------------------------------------------------- usage


def test_usage_windows_and_budget_fields(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_run(client, monkeypatch, "usagerun01")
    client.post("/api/settings", json={"budget": {"daily_usd": 2.0, "monthly_usd": 20.0}})
    body = client.get("/api/usage?days=7").json()
    assert body["window_days"] == 7
    assert body["totals"]["calls"] == 1
    assert body["budget"] == {"daily_usd": 2.0, "monthly_usd": 20.0, "free_only": False}
    assert body["spend_today_usd"] == 0.0  # piper is free-local
    assert body["by_model"][0]["model"] == "fake"


def test_catalog_refresh_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from zolai_tts import catalog

    def fake_fetch(name: str, **kwargs: Any) -> catalog.ProviderCatalog:
        return catalog.ProviderCatalog(provider=name, models=["m"], voices=["v"], source="test")

    monkeypatch.setattr(server, "fetch_catalog", fake_fetch)
    res = client.post("/api/catalog/refresh", json={"providers": ["piper"]})
    assert res.status_code == 200
    assert res.json()["refreshed"]["piper"]["ok"] is True


# ------------------------------------------------------------------- frontend


def test_serves_built_frontend_or_placeholder(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code in (200, 503)
    if res.status_code == 503:  # dist not built in this checkout
        assert "web/dist" in res.text


def test_unknown_api_route_is_json_404(client: TestClient) -> None:
    res = client.get("/api/definitely/not/here")
    assert res.status_code == 404
    assert res.json()["ok"] is False


def test_no_secret_values_anywhere_in_responses(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: a key must never appear in any API payload."""
    fake_key = "env-key-not-a-real-secret"
    monkeypatch.setenv("OPENROUTER_API_KEY", fake_key)
    client.get("/api/health")
    for path in (
        "/api/health",
        "/api/meta",
        "/api/providers",
        "/api/settings",
        "/api/secrets",
        "/api/usage",
    ):
        body = client.get(path)
        assert fake_key not in body.text, path
