"""Runtime helpers for managing the local Zolai-TTS processes.

Two managed services live here (both optional, both outside the repo tree):

* ``api``  — the FastAPI server (``python -m zolai_tts.server``) on :7860.
  Serves ``/api/*`` and, when a frontend build exists, ``web/dist``.
* ``web``  — the Vite dev server (``bun run dev`` in ``web/``) on :5174 with
  ``/api`` proxied to the api service.

This module uses only stdlib; it must not import optional UI/backend packages.
State is stored outside the git repo and must never contain secrets.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7860
WEB_DEV_PORT = 5174

_STATE_FILES = {"api": "ui.state.json", "web": "web.state.json"}
_LOG_FILES = {"api": "ui.log", "web": "web.log"}
# Substrings that identify a recorded pid as our service (checked against /proc cmdline).
_MARKERS: dict[str, tuple[str, ...]] = {
    "api": ("zolai_tts.server",),
    "web": ("vite", "run dev"),
}
# Removed/renamed entry points that may still be running from an older session
# (e.g. the deleted Gradio UI). stop/start must reclaim the port from them.
_LEGACY_MARKERS = ("zolai_tts.ui.app", "zolai_tts.ui ")


def _proc_cmdline(pid: int) -> str:
    proc = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = proc.read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def legacy_pids() -> list[int]:
    """PIDs of our own processes running a removed entry point (legacy Gradio UI)."""
    me = os.getpid()
    found: list[int] = []
    for entry in Path("/proc").iterdir() if Path("/proc").is_dir() else []:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == me or not _pid_alive(pid):
            continue
        cmd = _proc_cmdline(pid)
        if cmd and any(marker in cmd for marker in _LEGACY_MARKERS):
            found.append(pid)
    return found


def stop_legacy() -> dict[str, Any]:
    """Kill leftover legacy UI processes so the managed server can own its port."""
    killed: list[int] = []
    for pid in legacy_pids():
        _terminate(pid, signal.SIGKILL)
        killed.append(pid)
    if killed:
        time.sleep(0.2)
    return {"ok": True, "killed": killed}


def port_in_use(host: str, port: int) -> bool:
    import socket

    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((probe_host, port)) == 0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def web_dir() -> Path:
    return repo_root() / "web"


def web_dist_index() -> Path:
    return web_dir() / "dist" / "index.html"


@dataclass
class UIState:
    pid: int
    host: str
    port: int
    cmd: list[str]
    started_at: str
    log_path: str
    cwd: str
    service: str = field(default="api")

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


def state_path(service: str = "api") -> Path:
    return state_dir() / _STATE_FILES.get(service, f"{service}.state.json")


def log_path(service: str = "api") -> Path:
    return state_dir() / _LOG_FILES.get(service, f"{service}.log")


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
            service=str(data.get("service", "api")),
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
    return _classify_process(state) == "ours"


def _classify_process(state: UIState) -> str:
    """Classify the recorded pid for a service.

    Returns ``ours`` (current entrypoint), ``legacy`` (a previous incarnation of
    this app — e.g. the removed Gradio module), ``dead``, or ``foreign`` (pid
    reused by an unrelated process).
    """
    if not _pid_alive(state.pid):
        return "dead"
    markers = _MARKERS.get(state.service if state.service in _MARKERS else "api", ())
    cmd = _cmdline(state.pid) or " ".join(state.cmd)
    if any(marker in cmd for marker in markers):
        return "ours"
    if any(marker in cmd for marker in _LEGACY_MARKERS):
        return "legacy"
    # A renamed/removed module under our own package still belongs to us.
    if "zolai_tts." in cmd and state.service == "api":
        return "legacy"
    if not _cmdline(state.pid) and any(marker in " ".join(state.cmd) for marker in markers):
        return "ours"
    return "foreign"


def _terminate(pid: int, sig: int) -> None:
    """Signal the service's process group (start_new_session makes pid == pgid),
    so children (uvicorn workers, vite/node) die with the recorded pid."""
    try:
        os.killpg(os.getpgid(pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, sig)


def service_status(service: str = "api") -> dict[str, Any]:
    state = _read_state(state_path(service))
    if state is None:
        return {
            "running": False,
            "service": service,
            "reason": "no-state",
            "state_path": str(state_path(service)),
        }
    kind = _classify_process(state)
    if kind == "ours":
        return {
            "running": True,
            "service": service,
            "pid": state.pid,
            "host": state.host,
            "port": state.port,
            "url": state.url,
            "started_at": state.started_at,
            "log_path": state.log_path,
            "cwd": state.cwd,
            "state_path": str(state_path(service)),
        }
    if kind == "legacy":
        # A previous incarnation of this app (e.g. the removed Gradio UI) is
        # still alive and probably holding the port. Report it; do not clear.
        return {
            "running": False,
            "service": service,
            "reason": "legacy-process",
            "pid": state.pid,
            "port": state.port,
            "url": state.url,
            "state_path": str(state_path(service)),
            "hint": f"Run 'zolai-tts {service} stop' to reclaim the port, then start again.",
        }
    clear_state(state_path(service))
    return {
        "running": False,
        "service": service,
        "reason": "stale-pid" if kind == "dead" else "foreign-pid",
        "pid": state.pid,
        "state_path": str(state_path(service)),
    }


def ui_status() -> dict[str, Any]:
    return service_status("api")


def start_service(
    service: str,
    *,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    extra_args: list[str] | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Start a managed background process (``api`` or ``web``) and record its state."""
    if service not in _MARKERS:
        return {"ok": False, "error": f"Unknown service {service!r}."}
    current = service_status(service)
    if current.get("running"):
        return {"ok": False, "error": "already-running", "status": current}

    # Reclaim the port from our own leftovers (renamed/removed entry points such
    # as the deleted Gradio UI) before starting.
    reclaimed: list[int] = []
    if current.get("reason") == "legacy-process":
        stop_service(service)
    leftovers = legacy_pids()
    if leftovers:
        reclaimed.extend(leftovers)
        stop_legacy()

    if service == "api":
        resolved_port = port or DEFAULT_PORT
        if port_in_use(host, resolved_port):
            return {
                "ok": False,
                "error": f"Port {resolved_port} is busy (not a zolai-tts process).",
                "hint": "Stop the other process or pass --port.",
            }
        cmd = [
            sys.executable,
            "-m",
            "zolai_tts.server",
            "--host",
            host,
            "--port",
            str(resolved_port),
        ]
        workdir = cwd or os.getcwd()
    else:
        if not web_dir().is_dir():
            return {
                "ok": False,
                "error": f"Frontend not found at {web_dir()} (expected web/package.json).",
            }
        runner = shutil.which("bun") or shutil.which("npm")
        if not runner:
            return {"ok": False, "error": "Neither bun nor npm found on PATH — cannot run Vite."}
        resolved_port = port or WEB_DEV_PORT
        base = Path(runner).name
        cmd = [base, "run", "dev", "--", "--port", str(resolved_port), "--strictPort"]
        if base == "bun":
            cmd = [base, "run", "dev", "--port", str(resolved_port), "--strictPort"]
        workdir = str(web_dir())
    if extra_args:
        cmd.extend(extra_args)

    log = log_path(service)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n[{datetime.now(UTC).isoformat()}] START {service}: {' '.join(cmd)}\n")
        fh.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=workdir,
            start_new_session=True,
            env=os.environ.copy(),
        )

    state = UIState(
        pid=proc.pid,
        host=host,
        port=resolved_port,
        cmd=cmd,
        started_at=datetime.now(UTC).isoformat(),
        log_path=str(log),
        cwd=workdir,
        service=service,
    )
    _write_state(state, state_path(service))

    # Brief health check: process should still be alive after startup tick.
    time.sleep(0.4)
    if not _pid_alive(proc.pid):
        clear_state(state_path(service))
        return {
            "ok": False,
            "error": "process-exited",
            "log_path": str(log),
            "hint": tail_log(log, lines=40),
        }
    return {"ok": True, "status": service_status(service), "reclaimed": reclaimed}


def stop_service(service: str, *, timeout: float = 5.0) -> dict[str, Any]:
    if service not in _MARKERS:
        return {"ok": False, "error": f"Unknown service {service!r}."}
    state = _read_state(state_path(service))
    if state is None:
        return {"ok": True, "service": service, "stopped": False, "reason": "no-state"}
    kind = _classify_process(state)
    if kind in ("dead", "foreign"):
        clear_state(state_path(service))
        return {
            "ok": True,
            "service": service,
            "stopped": False,
            "reason": "stale-pid" if kind == "dead" else "foreign-pid",
            "pid": state.pid,
        }

    pid = state.pid
    if not _pid_alive(pid):
        clear_state(state_path(service))
        return {
            "ok": True,
            "service": service,
            "stopped": False,
            "reason": "already-gone",
            "pid": pid,
        }
    _terminate(pid, signal.SIGTERM)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            clear_state(state_path(service))
            return {
                "ok": True,
                "service": service,
                "stopped": True,
                "pid": pid,
                "signal": "SIGTERM",
            }
        time.sleep(0.1)

    # Vite (node) can ignore TERM when spawned via a package runner; escalate.
    _terminate(pid, signal.SIGKILL)
    time.sleep(0.1)
    clear_state(state_path(service))
    return {"ok": True, "service": service, "stopped": True, "pid": pid, "signal": "SIGKILL"}


def restart_service(service: str, **kwargs: Any) -> dict[str, Any]:
    stopped = stop_service(service)
    started = start_service(service, **kwargs)
    return {"ok": bool(started.get("ok")), "service": service, "stop": stopped, "start": started}


def start_ui(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    share: bool = False,
    config: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    extra: list[str] = []
    if share:
        extra.append("--share")
    if config:
        extra.extend(["--config", config])
    return start_service("api", host=host, port=port, extra_args=extra or None, cwd=cwd)


def stop_ui(*, timeout: float = 5.0) -> dict[str, Any]:
    return stop_service("api", timeout=timeout)


def restart_ui(**kwargs: Any) -> dict[str, Any]:
    stop_ui()
    return start_ui(**kwargs)


def start_web(*, port: int = WEB_DEV_PORT) -> dict[str, Any]:
    return start_service("web", host=DEFAULT_HOST, port=port)


def stop_web(*, timeout: float = 5.0) -> dict[str, Any]:
    return stop_service("web", timeout=timeout)


def web_status() -> dict[str, Any]:
    status = service_status("web")
    status["dist_ready"] = web_dist_index().is_file()
    return status


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
