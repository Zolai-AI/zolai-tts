"""Runtime helpers for managing the optional local UI process.

This module uses only stdlib; it must not import optional UI/backend packages.
State is stored outside the git repo and must never contain secrets.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7860
_STATE_FILE = "ui.state.json"
_LOG_FILE = "ui.log"


@dataclass
class UIState:
    pid: int
    host: str
    port: int
    cmd: list[str]
    started_at: str
    log_path: str
    cwd: str

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self.host in {"0.0.0.0", "::"} else self.host
        return f"http://{host}:{self.port}"


def state_dir() -> Path:
    """Return runtime state dir outside git, preferring /tmp/opencode."""
    uid = os.getuid() if hasattr(os, "getuid") else "user"
    preferred = Path("/tmp/opencode") / f"zolai-tts-{uid}"
    for candidate in (preferred, _xdg_runtime_dir(uid)):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            os.chmod(candidate, 0o700)
            return candidate
        except OSError:
            continue
    # Last resort: /tmp, still outside repo.
    fallback = Path("/tmp") / f"zolai-tts-{uid}"  # noqa: S108
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _xdg_runtime_dir(uid: int | str) -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        return Path(base) / "zolai-tts"
    return Path.home() / ".cache" / "zolai-tts" / f"run-{uid}"


def state_path() -> Path:
    return state_dir() / _STATE_FILE


def log_path() -> Path:
    return state_dir() / _LOG_FILE


def _read_state(path: Path | None = None) -> UIState | None:
    path = path or state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return UIState(
            pid=int(data["pid"]),
            host=str(data["host"]),
            port=int(data["port"]),
            cmd=[str(x) for x in data.get("cmd", [])],
            started_at=str(data.get("started_at", "")),
            log_path=str(data.get("log_path", "")),
            cwd=str(data.get("cwd", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _write_state(state: UIState, path: Path | None = None) -> None:
    path = path or state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def clear_state(path: Path | None = None) -> None:
    path = path or state_path()
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _cmdline(pid: int) -> str:
    proc = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = proc.read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def _is_ui_process(state: UIState) -> bool:
    if not _pid_alive(state.pid):
        return False
    cmd = _cmdline(state.pid)
    if not cmd:
        # If cmdline unavailable, be conservative: pid alive is weak evidence.
        # Keep only when command in state looks like ui and pid exists.
        return any("zolai_tts.server" in part for part in state.cmd)
    return "zolai_tts.server" in cmd


def ui_status() -> dict[str, Any]:
    state = _read_state()
    if state is None:
        return {"running": False, "reason": "no-state", "state_path": str(state_path())}
    if _is_ui_process(state):
        return {
            "running": True,
            "pid": state.pid,
            "host": state.host,
            "port": state.port,
            "url": state.url,
            "started_at": state.started_at,
            "log_path": state.log_path,
            "cwd": state.cwd,
            "state_path": str(state_path()),
        }
    clear_state()
    return {
        "running": False,
        "reason": "stale-pid",
        "pid": state.pid,
        "state_path": str(state_path()),
    }


def start_ui(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    share: bool = False,
    config: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    current = ui_status()
    if current.get("running"):
        return {"ok": False, "error": "already-running", "status": current}

    cmd = [sys.executable, "-m", "zolai_tts.server", "--host", host, "--port", str(port)]
    if share:
        cmd.append("--share")
    if config:
        cmd.extend(["--config", config])

    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    # Open in append mode; no secrets expected, but avoid accidental exposure.
    with log.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n[{datetime.now(UTC).isoformat()}] START {' '.join(cmd)}\n"
        )
        fh.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=cwd or os.getcwd(),
            start_new_session=True,
            env=os.environ.copy(),
        )

    state = UIState(
        pid=proc.pid,
        host=host,
        port=port,
        cmd=cmd,
        started_at=datetime.now(UTC).isoformat(),
        log_path=str(log),
        cwd=cwd or os.getcwd(),
    )
    _write_state(state)

    # Brief health check: process should still be alive after startup tick.
    time.sleep(0.4)
    if not _pid_alive(proc.pid):
        clear_state()
        return {
            "ok": False,
            "error": "process-exited",
            "log_path": str(log),
            "hint": tail_log(log, lines=40),
        }
    return {"ok": True, "status": ui_status()}


def stop_ui(*, timeout: float = 5.0) -> dict[str, Any]:
    state = _read_state()
    if state is None:
        return {"ok": True, "stopped": False, "reason": "no-state"}
    if not _is_ui_process(state):
        clear_state()
        return {"ok": True, "stopped": False, "reason": "stale-pid", "pid": state.pid}

    pid = state.pid
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        clear_state()
        return {"ok": True, "stopped": False, "reason": "already-gone", "pid": pid}

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            clear_state()
            return {"ok": True, "stopped": True, "pid": pid, "signal": "SIGTERM"}
        time.sleep(0.1)

    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)
    time.sleep(0.1)
    clear_state()
    return {"ok": True, "stopped": True, "pid": pid, "signal": "SIGKILL"}


def restart_ui(**kwargs: Any) -> dict[str, Any]:
    stopped = stop_ui()
    started = start_ui(**kwargs)
    return {"ok": bool(started.get("ok")), "stop": stopped, "start": started}


def tail_log(path: Path | str | None = None, *, lines: int = 40) -> str:
    p = Path(path) if path else log_path()
    try:
        content = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return ""
    except OSError as exc:
        return f"<log read error: {exc}>"
    if lines <= 0:
        return ""
    return "\n".join(content[-lines:])
