"""Offline tests for the zolai-tts management CLI and UI runtime helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import zolai_tts.cli as cli
import zolai_tts.runtime as runtime


def test_cli_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "zolai-tts" in out
    assert "ui" in out
    assert "doctor" in out


def test_menu_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["menu", "--help"])
    assert exc.value.code == 0
    assert "menu" in capsys.readouterr().out


def test_doctor_reports_env_presence_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "TOPSECRET_GEMINI_KEY_VALUE"
    monkeypatch.setenv("ZOLAI_TTS_GEMINI_API_KEY", secret)
    code = cli.main(["doctor", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["env_keys"]["ZOLAI_TTS_GEMINI_API_KEY"] is True
    assert secret not in out


def test_gemini_smoke_dry_without_key_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ZOLAI_TTS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    code = cli.main(["gemini-smoke"])
    assert code == 2
    err = capsys.readouterr().err
    assert "No Gemini API key" in err
    assert "TOPSECRET" not in err


def test_gemini_smoke_dry_with_key_redacts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "super-secret-key-1234"
    monkeypatch.setenv("GEMINI_API_KEY", secret)
    code = cli.main(["gemini-smoke"])
    assert code == 0
    out = capsys.readouterr().out
    assert "present, value redacted" in out
    assert secret not in out


def test_prepare_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_call(cmd: list[str]) -> int:
        called["cmd"] = cmd
        return 7

    monkeypatch.setattr(cli.subprocess, "call", fake_call)
    code = cli.main(["prepare", "--", "--help"])
    assert code == 7
    cmd = called["cmd"]
    assert cmd[1:3] == ["-m", "zolai_tts.data.preprocess"]
    assert "--help" in cmd


def test_runtime_status_no_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    status = runtime.ui_status()
    assert status["running"] is False
    assert status["reason"] == "no-state"


def test_runtime_start_stop_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)

    class FakeProc:
        pid = 4242

    def fake_popen(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runtime, "_pid_alive", lambda pid: pid == 4242)
    monkeypatch.setattr(
        runtime, "_cmdline", lambda _pid: "python -m zolai_tts.ui.app --host 127.0.0.1"
    )
    monkeypatch.setattr(runtime.time, "sleep", lambda *_: None)

    started = runtime.start_ui(host="127.0.0.1", port=7861)
    assert started["ok"] is True
    status = runtime.ui_status()
    assert status["running"] is True
    assert status["pid"] == 4242
    assert status["url"] == "http://127.0.0.1:7861"

    kills: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kills.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError()

    monkeypatch.setattr(runtime.os, "kill", fake_kill)
    stopped = runtime.stop_ui(timeout=0.1)
    assert stopped["ok"] is True
    assert stopped["stopped"] is True
    assert runtime.ui_status()["running"] is False


def test_runtime_stale_pid_cleaned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    state = runtime.UIState(
        pid=99999,
        host="127.0.0.1",
        port=7860,
        cmd=["python", "-m", "zolai_tts.ui.app"],
        started_at="now",
        log_path=str(tmp_path / "ui.log"),
        cwd=str(tmp_path),
    )
    runtime._write_state(state)
    monkeypatch.setattr(runtime, "_pid_alive", lambda _pid: False)
    status = runtime.ui_status()
    assert status["running"] is False
    assert status["reason"] == "stale-pid"
    assert not (tmp_path / "ui.state.json").exists()


def test_menu_dispatch(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("builtins.input", lambda *_: "1")
    called = {"doctor": False}

    def fake_doctor(_args):
        called["doctor"] = True
        return 0

    monkeypatch.setattr(cli, "cmd_doctor", fake_doctor)
    code = cli.main(["menu"])
    assert code == 0
    assert called["doctor"] is True
    assert "Zolai-TTS menu" in capsys.readouterr().out


def test_ui_open_prints_url_without_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(
        runtime,
        "ui_status",
        lambda: {
            "running": True,
            "url": "http://127.0.0.1:7860",
            "log_path": str(tmp_path / "ui.log"),
        },
    )
    code = cli.main(["ui", "open"])
    assert code == 0
    assert "http://127.0.0.1:7860" in capsys.readouterr().out
