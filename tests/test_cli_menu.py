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


def test_openrouter_smoke_dry_without_key_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ZOLAI_TTS_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    code = cli.main(["openrouter-smoke"])
    assert code == 2
    err = capsys.readouterr().err
    assert "No OpenRouter API key" in err


def test_openrouter_smoke_dry_with_key_redacts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "super-secret-openrouter-key-1234"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    code = cli.main(["openrouter-smoke"])
    assert code == 0
    out = capsys.readouterr().out
    assert "present, value redacted" in out
    assert secret not in out
    assert "Dry smoke only" in out


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
    web = runtime.web_status()
    assert web["running"] is False
    assert web["service"] == "web"
    assert "dist_ready" in web


def test_runtime_services_have_separate_state_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    assert runtime.state_path("api") != runtime.state_path("web")
    assert runtime.log_path("api") != runtime.log_path("web")

    state = runtime.UIState(
        pid=1234,
        host="127.0.0.1",
        port=5174,
        cmd=["bun", "run", "dev", "--port", "5174"],
        started_at="now",
        log_path=str(runtime.log_path("web")),
        cwd=str(tmp_path),
        service="web",
    )
    runtime._write_state(state, runtime.state_path("web"))
    monkeypatch.setattr(runtime, "_pid_alive", lambda _pid: True)
    monkeypatch.setattr(
        runtime, "_cmdline", lambda _pid: "/usr/bin/node /app/web/node_modules/vite/bin/vite.js"
    )
    assert runtime.web_status()["running"] is True
    # api service is unaffected by web state
    assert runtime.ui_status()["running"] is False


def test_runtime_web_start_requires_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(runtime, "web_dir", lambda: tmp_path / "web")
    monkeypatch.setattr(runtime.shutil, "which", lambda _name: None)
    # Missing frontend dir is reported first.
    res = runtime.start_web()
    assert res["ok"] is False
    assert "Frontend not found" in res["error"]
    (tmp_path / "web").mkdir()
    res = runtime.start_web()
    assert res["ok"] is False
    assert "bun" in res["error"]


def test_runtime_web_start_stop_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(runtime, "web_dir", lambda: tmp_path)
    monkeypatch.setattr(runtime.shutil, "which", lambda _name: "/usr/bin/bun")

    class FakeProc:
        pid = 3131

    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr(runtime, "_pid_alive", lambda pid: pid == 3131)
    monkeypatch.setattr(
        runtime,
        "_cmdline",
        lambda _pid: "bun run dev --port 5174 --strictPort",
    )
    monkeypatch.setattr(runtime.time, "sleep", lambda *_: None)

    started = runtime.start_web(port=5174)
    assert started["ok"] is True
    status = runtime.web_status()
    assert status["running"] is True
    assert status["url"] == "http://127.0.0.1:5174"

    kills: list[tuple[int, int]] = []

    def fake_killpg(pgid: int, sig: int) -> None:
        kills.append((pgid, sig))

    monkeypatch.setattr(runtime.os, "getpgid", lambda _pid: _pid)
    monkeypatch.setattr(runtime.os, "killpg", fake_killpg)
    monkeypatch.setattr(runtime, "_pid_alive", lambda pid: False if kills else pid == 3131)

    stopped = runtime.stop_web(timeout=0.1)
    assert stopped["ok"] is True
    assert stopped["stopped"] is True
    assert kills and kills[0][1] == runtime.signal.SIGTERM
    assert runtime.web_status()["running"] is False


def test_cli_web_status_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    code = cli.main(["web", "status"])
    assert code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["service"] == "web"
    assert body["running"] is False


def test_cli_web_start_uses_dev_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    captured: dict[str, object] = {}

    def fake_start_web(*, port: int = runtime.WEB_DEV_PORT) -> dict:
        captured["port"] = port
        return {"ok": True, "status": {"running": True, "url": f"http://127.0.0.1:{port}"}}

    monkeypatch.setattr(runtime, "start_web", fake_start_web)
    code = cli.main(["web", "start"])
    assert code == 0
    assert captured["port"] == runtime.WEB_DEV_PORT
    assert "5174" in capsys.readouterr().out


def test_cli_web_stop_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        runtime, "stop_web", lambda **k: calls.append("stop") or {"ok": True, "stopped": False}
    )
    code = cli.main(["web", "stop"])
    assert code == 0
    assert calls == ["stop"]

    log = runtime.log_path("web")
    log.write_text("line1\nline2\n", encoding="utf-8")
    code = cli.main(["web", "logs", "--lines", "5"])
    assert code == 0
    assert "line2" in capsys.readouterr().out


def test_cli_menu_lists_both_servers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_input(_prompt: str) -> str:
        return ""

    monkeypatch.setattr("builtins.input", fake_input)
    code = cli.main(["menu"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Run both (API :7860 + Web dev :5174)" in out
    assert "Stop both" in out
    assert "Servers status (API + Web)" in out
    assert "API status" in out
    assert "API start" in out
    assert "API stop" in out
    assert "Web UI dev start" in out
    assert "Web UI dev stop" in out
    assert "Web UI build" in out
    assert "Gradio" not in out


def test_cli_up_starts_both_servers(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        runtime,
        "start_ui",
        lambda **kw: (
            calls.append("api") or {"ok": True, "status": {"url": "http://127.0.0.1:7860"}}
        ),
    )
    monkeypatch.setattr(
        runtime,
        "start_web",
        lambda **kw: (
            calls.append("web") or {"ok": True, "status": {"url": "http://127.0.0.1:5174"}}
        ),
    )
    code = cli.main(["up"])
    assert code == 0
    assert calls == ["api", "web"]
    out = capsys.readouterr().out
    assert "http://127.0.0.1:7860" in out
    assert "http://127.0.0.1:5174" in out


def test_cli_up_tolerates_already_running(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        runtime,
        "start_ui",
        lambda **kw: {"ok": False, "error": "already-running", "status": {"url": "http://x"}},
    )
    monkeypatch.setattr(runtime, "start_web", lambda **kw: {"ok": True, "status": {"url": "u"}})
    assert cli.main(["up"]) == 0
    assert "already-running" not in capsys.readouterr().err


def test_cli_up_reports_api_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "start_ui", lambda **kw: {"ok": False, "error": "process-exited"})
    monkeypatch.setattr(runtime, "start_web", lambda **kw: {"ok": True, "status": {"url": "u"}})
    assert cli.main(["up"]) == 2
    assert "process-exited" in capsys.readouterr().err


def test_cli_down_stops_both(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        runtime, "stop_web", lambda **kw: calls.append("web") or {"ok": True, "stopped": True}
    )
    monkeypatch.setattr(
        runtime, "stop_ui", lambda **kw: calls.append("api") or {"ok": True, "stopped": True}
    )
    assert cli.main(["down"]) == 0
    assert calls == ["web", "api"]


def test_cli_status_summarizes_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    code = cli.main(["status"])
    assert code == 0
    out = capsys.readouterr().out
    body = json.loads(out.split("api: ")[0])
    assert body["api"]["running"] is False
    assert body["web"]["running"] is False
    assert "api: stopped" in out
    assert "web: stopped" in out


def test_cli_open_app_prefers_running_web(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(
        runtime, "web_status", lambda: {"running": True, "url": "http://127.0.0.1:5174"}
    )
    monkeypatch.setattr(runtime, "ui_status", lambda: {"running": False})
    opened: list[str] = []
    monkeypatch.setattr(cli, "cmd_ui", lambda args: opened.append(args.service) or 0)
    assert cli._cmd_open_app() == 0
    assert opened == ["web"]


def test_cli_open_app_no_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "web_status", lambda: {"running": False})
    monkeypatch.setattr(runtime, "ui_status", lambda: {"running": False})
    assert cli._cmd_open_app() == 2
    assert "No server running" in capsys.readouterr().err


def test_runtime_start_stop_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)

    class FakeProc:
        pid = 4242

    def fake_popen(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runtime, "_pid_alive", lambda pid: pid == 4242)
    monkeypatch.setattr(
        runtime, "_cmdline", lambda _pid: "python -m zolai_tts.server --host 127.0.0.1"
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
        cmd=["python", "-m", "zolai_tts.server"],
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


def test_menu_dispatch_openrouter_smoke(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Menu item index can shift as features are added; select by label.
    actions = cli._menu_actions()
    idx = next(i for i, (label, _, _) in enumerate(actions, start=1) if "OpenRouter smoke" in label)
    monkeypatch.setattr("builtins.input", lambda *_: str(idx))
    called = {"openrouter": False}

    def fake_openrouter(_args):
        called["openrouter"] = True
        return 0

    monkeypatch.setattr(cli, "cmd_openrouter_smoke", fake_openrouter)
    code = cli.main(["menu"])
    assert code == 0
    assert called["openrouter"] is True
    assert "OpenRouter smoke" in capsys.readouterr().out


def test_ui_open_prints_url_without_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(
        runtime,
        "service_status",
        lambda service="api": {
            "running": True,
            "url": "http://127.0.0.1:7860",
            "log_path": str(tmp_path / "ui.log"),
        },
    )
    code = cli.main(["ui", "open"])
    assert code == 0
    assert "http://127.0.0.1:7860" in capsys.readouterr().out
