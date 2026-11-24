import json
from pathlib import Path

import pytest

from zolai_tts.data import preprocess as prepare_cli
from zolai_tts.inference import synthesize as synth_cli

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "dataset/metadata/sample.jsonl"
SCHEMA = ROOT / "dataset/schemas/utterance.schema.json"


def test_prepare_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        prepare_cli.main(["--help"])
    assert exit_info.value.code == 0
    assert "zolai-tts-prepare" in capsys.readouterr().out


def test_synth_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        synth_cli.main(["--help"])
    assert exit_info.value.code == 0
    assert "zolai-tts-synth" in capsys.readouterr().out


def test_prepare_fixture_writes_manifest(tmp_path: Path) -> None:
    out_dir = tmp_path / "manifest"
    code = prepare_cli.main(
        ["--input", str(SAMPLE), "--schema", str(SCHEMA), "--out-dir", str(out_dir)]
    )
    assert code == 0
    assert len((out_dir / "metadata.jsonl").read_text().splitlines()) == 3


def test_synth_dry_run_piper_emits_plan_and_no_audio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "piper.wav"
    code = synth_cli.main(
        [
            "--text",
            "Pasian in leitung a piangsak hi.",
            "--provider",
            "piper",
            "--voice",
            "/tmp/opencode/no-real-voice.onnx",
            "--language",
            "zolai",
            "--out",
            str(out),
            "--dry-run",
        ]
    )
    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == "dry-run"
    assert plan["provider"] == "piper"
    assert not out.exists()


def test_synth_dry_run_gemini_emits_request_without_key_or_network(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ZOLAI_TTS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    code = synth_cli.main(
        [
            "--text",
            "Pasian",
            "--provider",
            "gemini",
            "--voice",
            "Kore",
            "--language",
            "zomi",
            "--out",
            str(tmp_path / "gemini.wav"),
            "--dry-run",
        ]
    )
    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["request"]["model"] == "gemini-2.5-flash-preview-tts"
    assert plan["language"] == "zomi"
    assert not (tmp_path / "gemini.wav").exists()


def test_synth_dry_run_openrouter_emits_request_without_key_or_network(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ZOLAI_TTS_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    code = synth_cli.main(
        [
            "--text",
            "Hello",
            "--provider",
            "openrouter",
            "--voice",
            "alloy",
            "--language",
            "en",
            "--model",
            "openai/gpt-4o-mini-tts",
            "--base-url",
            "https://openrouter.ai/api/v1",
            "--response-format",
            "mp3",
            "--out",
            str(tmp_path / "out.mp3"),
            "--dry-run",
        ]
    )
    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["provider"] == "openrouter"
    assert plan["model"] == "openai/gpt-4o-mini-tts"
    assert plan["base_url"] == "https://openrouter.ai/api/v1"
    assert plan["response_format"] == "mp3"
    assert plan["request"]["endpoint"].endswith("/audio/speech")
    assert plan["request"]["body"]["model"] == "openai/gpt-4o-mini-tts"
    assert plan["request"]["body"]["response_format"] == "mp3"
    assert not (tmp_path / "out.mp3").exists()


def test_synth_unknown_provider_rejected_with_canonical_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("provider: local\n", encoding="utf-8")
    code = synth_cli.main(["--config", str(config), "--dry-run"])
    assert code == 2
    err = capsys.readouterr().err
    assert "Available providers:" in err
    assert "openrouter" in err


def test_synth_missing_voice_fails_with_actionable_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = synth_cli.main(["--text", "Pasian", "--out", "/tmp/opencode/zolai-tts/no-voice.wav"])
    assert code == 2
    assert "A real voice is required" in capsys.readouterr().err


def test_config_yaml_is_safe_loaded_and_cli_overrides(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "provider: piper\nvoice: /tmp/opencode/voice.onnx\n"
        'language: "ted"\ntext: "Pasian"\n'
        'out: "/tmp/opencode/config-out.wav"\n',
        encoding="utf-8",
    )
    code = synth_cli.main(["--config", str(config), "--language", "zomi", "--dry-run"])
    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["language"] == "zomi"
    assert plan["text"] == "Pasian"
