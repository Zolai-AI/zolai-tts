"""Tests for the Zolai-TTS FastAPI web server (replaces the Gradio UI tests).

No network calls: catalog fetchers and providers are monkeypatched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import zolai_tts.server as server  # noqa: E402
from zolai_tts.catalog import ModelInfo, ProviderCatalog  # noqa: E402
from zolai_tts.inference.base import SynthesisResult  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ZOLAI_TTS_STORE_DIR", str(tmp_path / "store"))
    app = server.create_app()
    return TestClient(app)


def test_health_lists_dynamic_providers(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert set(body["providers"]) >= {"piper", "gemini", "openrouter"}


def test_providers_payload_is_registry_driven(client: TestClient) -> None:
    res = client.get("/api/providers")
    assert res.status_code == 200
    providers = {p["name"]: p for p in res.json()["providers"]}
    assert providers["piper"]["voice_kind"] == "path"
    assert providers["piper"]["hosted"] is False
    assert providers["gemini"]["hosted"] is True
    assert "key_present" in providers["gemini"]


def test_catalog_endpoint_uses_fetcher(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(*args: Any, **kwargs: Any) -> ProviderCatalog:
        return ProviderCatalog(
            provider="openrouter",
            models=["acme/tts-1"],
            model_infos=[ModelInfo(id="acme/tts-1", voices=["ruby"], formats=["mp3"])],
            voices=["ruby"],
            formats=["mp3"],
            source="live",
        )

    monkeypatch.setattr(server, "fetch_catalog", fake_fetch)
    res = client.get("/api/providers/openrouter/catalog")
    assert res.status_code == 200
    catalog = res.json()["catalog"]
    assert catalog["source"] == "live"
    assert catalog["model_infos"][0]["voices"] == ["ruby"]


def test_catalog_rejects_unknown_provider(client: TestClient) -> None:
    res = client.get("/api/providers/evil-provider/catalog")
    assert res.status_code == 404


def test_dry_run_gemini_builds_request(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZOLAI_TTS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = client.post(
        "/api/synthesize",
        json={
            "provider": "gemini",
            "text": "Pasian in leitung a piangsak hi.",
            "voice": "Kore",
            "language": "zolai",
            "dry_run": True,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["dry_run"] is True
    assert body["plan"]["request"]["model"] == "gemini-2.5-flash-preview-tts"


def test_hosted_provider_requires_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZOLAI_TTS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = client.post(
        "/api/synthesize",
        json={"provider": "gemini", "text": "Hi", "voice": "Kore", "dry_run": False},
    )
    assert res.status_code == 400
    assert "API key" in res.json()["error"]


def test_synthesize_saves_audio_and_run_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeProvider:
        name = "piper"

        def synthesize(self, text: str, voice: str, out_path: Path) -> SynthesisResult:
            out_path.write_bytes(b"RIFFfake")
            return SynthesisResult(
                out_path=out_path, provider="piper", voice=voice, metadata={"language": "ted"}
            )

    monkeypatch.setattr(server, "get_provider", lambda *_a, **_k: FakeProvider())
    res = client.post(
        "/api/synthesize",
        json={
            "provider": "piper",
            "text": "Pasian",
            "voice": str(tmp_path / "fake.onnx"),
            "language": "ted",
            "out_name": "testrun1",
            "dry_run": False,
        },
    )
    assert res.status_code == 200
    run = res.json()["run"]
    assert run["ok"] is True
    assert run["id"] == "testrun1"
    assert run["format"] == "wav"
    assert Path(run["out_path"]).exists()

    # run record persisted and listable
    detail = client.get("/api/runs/testrun1")
    assert detail.status_code == 200
    assert detail.json()["run"]["provider"] == "piper"
    listing = client.get("/api/runs")
    assert any(r["id"] == "testrun1" for r in listing.json()["runs"])

    # audio served
    audio = client.get("/api/audio/testrun1")
    assert audio.status_code == 200
    assert audio.content == b"RIFFfake"


def test_synthesize_error_records_run(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> Any:
        raise server.ProviderError("backend missing")

    monkeypatch.setattr(server, "get_provider", boom)
    res = client.post(
        "/api/synthesize",
        json={"provider": "piper", "text": "x", "voice": "/tmp/v.onnx", "dry_run": False},
    )
    assert res.status_code == 502
    body = res.json()
    assert "backend missing" in body["error"]
    assert body["run"]["ok"] is False


def test_recording_saved_with_sidecar(client: TestClient, tmp_path: Path) -> None:
    res = client.post(
        "/api/recordings",
        files={"file": ("mic.webm", b"audio-bytes", "audio/webm")},
        data={"provider": "piper", "note": "test take"},
    )
    assert res.status_code == 200
    rec = res.json()["recording"]
    assert rec["format"] == "webm"
    assert rec["bytes"] == len(b"audio-bytes")
    saved = Path(rec["saved_path"])
    assert saved.exists() and saved.read_bytes() == b"audio-bytes"

    listing = client.get("/api/recordings")
    assert any(r["id"] == rec["id"] for r in listing.json()["recordings"])

    audio = client.get(f"/api/recordings/{rec['id']}/audio")
    assert audio.status_code == 200
    assert audio.content == b"audio-bytes"


def test_recording_rejects_empty(client: TestClient) -> None:
    res = client.post("/api/recordings", files={"file": ("mic.webm", b"", "audio/webm")})
    assert res.status_code == 400


def test_text_length_limit(client: TestClient) -> None:
    res = client.post(
        "/api/synthesize",
        json={"provider": "piper", "text": "x" * 9000, "voice": "v", "dry_run": True},
    )
    assert res.status_code == 422


def test_main_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        server.main(["--help"])
    assert exc.value.code == 0
