"""Unified CLI for Zolai-TTS management and tools.

This CLI orchestrates existing modules; it does not duplicate synthesis logic.
It must not persist secrets, and it stores runtime state outside the git repo.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from zolai_tts import __version__, runtime

GEMINI_KEY_NAMES = ("ZOLAI_TTS_GEMINI_API_KEY", "GEMINI_API_KEY")
OPENROUTER_KEY_NAMES = ("ZOLAI_TTS_OPENROUTER_API_KEY", "OPENROUTER_API_KEY")


def _print(text: str = "", *, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    print(text, file=stream)


def _mask_present(name: str) -> str:
    value = os.getenv(name)
    if not value:
        return f"{name}: missing"
    # Never reveal value; show only minimal non-sensitive metadata.
    return f"{name}: present ({len(value)} chars)"


def _run_module(module: str, args: list[str]) -> int:
    cmd = [sys.executable, "-m", module, *args]
    return subprocess.call(cmd)


# (intentionally no helper for external tool version reporting; doctor uses shutil.which)


def _doctor_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "state_dir": str(runtime.state_dir()),
        "env_keys": {
            **{name: bool(os.getenv(name)) for name in GEMINI_KEY_NAMES},
            **{name: bool(os.getenv(name)) for name in OPENROUTER_KEY_NAMES},
        },
        "tools": {
            "uv": shutil.which("uv") is not None,
            "ruff": shutil.which("ruff") is not None,
            "mypy": shutil.which("mypy") is not None,
            "pytest": shutil.which("pytest") is not None,
            "git": shutil.which("git") is not None,
            "xdg-open": shutil.which("xdg-open") is not None,
            "bun": shutil.which("bun") is not None,
            "node": shutil.which("node") is not None,
        },
        "web": {
            "dir": str(runtime.web_dir()),
            "package_json": (runtime.web_dir() / "package.json").is_file(),
            "node_modules": (runtime.web_dir() / "node_modules").is_dir(),
            "dist": runtime.web_dist_index().is_file(),
        },
        "services": {
            "api": runtime.ui_status(),
            "web": runtime.web_status(),
        },
        "modules": {},
        "gpu": {"torch_installed": False, "cuda_available": False, "device_count": 0},
    }

    for mod in (
        "fastapi",
        "uvicorn",
        "google.genai",
        "piper",
        "openai",
        "litellm",
        "pydantic_ai",
        "torch",
    ):
        try:
            __import__(mod)
            report["modules"][mod] = True
        except Exception:
            report["modules"][mod] = False

    try:
        import torch

        report["gpu"]["torch_installed"] = True
        cuda = bool(torch.cuda.is_available())
        report["gpu"]["cuda_available"] = cuda
        report["gpu"]["device_count"] = int(torch.cuda.device_count()) if cuda else 0
    except Exception:
        pass

    if shutil.which("git"):
        try:
            proc = subprocess.run(
                ["git", "status", "--porcelain"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                dirty = [line for line in proc.stdout.splitlines() if line.strip()]
                report["git"] = {"dirty": bool(dirty), "changes": len(dirty)}
        except (OSError, subprocess.SubprocessError):
            report["git"] = {"dirty": None, "changes": None}
    return report


def cmd_db(args: argparse.Namespace) -> int:
    """Studio data-layer maintenance. Secrets are never printed."""
    from .db import Repository, get_database

    action = getattr(args, "db_action", "status")
    repo = Repository(get_database())

    if action == "status":
        info = repo.db.info()
        _print(f"dialect: {info['dialect']}")
        _print(f"url:     {info['url']}")
        for name, count in sorted(repo.counts().items()):
            _print(f"  {name:15} {count}")
        return 0

    if action == "reclassify-tiers":
        result = repo.reclassify_tiers()
        _print(f"models updated: {result['models_updated']}")
        _print(f"usage rows updated: {result['usage_updated']}")
        return 0

    if action == "storage":
        from .storage import build_storage

        for key, value in _flatten(build_storage().info()).items():
            _print(f"{key}: {value}")
        return 0

    if action == "storage-copy":
        from .paths import objects_dir
        from .storage import build_storage, copy_local_to_r2

        hub = build_storage("r2")
        root = Path(args.root) if args.root else objects_dir()
        count = copy_local_to_r2(hub, root)
        _print(f"uploaded {count} object(s) to bucket {hub.r2.bucket}")
        return 0

    if action == "migrate":
        return _migrate_legacy_store(repo, Path(args.store) if args.store else None, args.dry_run)

    _print(f"Unknown db action: {action}")
    return 2


def _flatten(info: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in info.items():
        if isinstance(value, dict):
            for inner, inner_value in value.items():
                out[f"{key}.{inner}"] = inner_value
        else:
            out[key] = value
    return out


def _migrate_legacy_store(repo: object, root: Path | None, dry_run: bool) -> int:
    """Import the pre-database JSON sidecars (runs/, recordings/) into SQLModel."""
    import json

    from .paths import store_dir

    root = root or store_dir()
    runs = 0
    recordings = 0
    for folder, kind in (("runs", "run"), ("recordings", "recording")):
        for path in sorted((root / folder).glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                _print(f"skip {path.name}: {exc}")
                continue
            if not isinstance(payload, dict) or not payload.get("id"):
                continue
            if dry_run:
                _print(f"would import {kind}: {path.name}")
            else:
                if kind == "run":
                    repo.record_run(payload)  # type: ignore[attr-defined]
                    runs += 1
                else:
                    repo.record_recording(payload)  # type: ignore[attr-defined]
                    recordings += 1
    _print(
        f"dry run: {runs or recordings or 0} file(s) would import"
        if dry_run
        else f"imported {runs} run(s), {recordings} recording(s)"
    )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = _doctor_report()
    if args.json:
        _print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    _print(f"zolai-tts {report['version']}")
    _print(f"Python: {report['python']}  Platform: {report['platform']}")
    _print(f"State dir: {report['state_dir']}")
    _print("Env keys (presence only):")
    for name in (*GEMINI_KEY_NAMES, *OPENROUTER_KEY_NAMES):
        _print(f"  - {_mask_present(name)}")
    _print("Tools:")
    for name, ok in report["tools"].items():
        _print(f"  - {name}: {'yes' if ok else 'no'}")
    web = report["web"]
    _print(
        "Web frontend: "
        f"dir={web['dir']} pkg={web['package_json']} "
        f"deps={web['node_modules']} built_dist={web['dist']}"
    )
    for svc in ("api", "web"):
        status = report["services"][svc]
        if status.get("running"):
            _print(f"Service {svc}: running (pid={status['pid']} url={status['url']})")
        else:
            _print(f"Service {svc}: stopped ({status.get('reason', 'no-state')})")
    _print("Optional modules:")
    for name, ok in report["modules"].items():
        _print(f"  - {name}: {'installed' if ok else 'missing'}")
    gpu = report["gpu"]
    _print(
        "GPU: "
        f"torch={gpu['torch_installed']} "
        f"cuda_available={gpu['cuda_available']} "
        f"devices={gpu['device_count']}"
    )
    if "git" in report:
        git = report["git"]
        _print(f"Git dirty: {git['dirty']} (changes={git['changes']})")
    _print("Tip: use `uv run --extra dev ...` for lint/test/typecheck commands.")
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    """Lifecycle for managed services: ``api`` (FastAPI) or ``web`` (Vite dev)."""
    service = getattr(args, "service", "api") or "api"
    action = args.ui_action
    default_port = runtime.DEFAULT_PORT if service == "api" else runtime.WEB_DEV_PORT
    if action == "start":
        if service == "api":
            res = runtime.start_ui(
                host=args.host, port=args.port or default_port, share=args.share, config=args.config
            )
        else:
            res = runtime.start_web(port=args.port or default_port)
        _print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 2
    if action == "stop":
        res = runtime.stop_ui() if service == "api" else runtime.stop_web()
        _print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 2
    if action == "restart":
        if service == "api":
            res = runtime.restart_ui(
                host=args.host, port=args.port or default_port, share=args.share, config=args.config
            )
        else:
            res = runtime.restart_service("web", port=args.port or default_port)
        _print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 2
    if action == "status":
        res = runtime.ui_status() if service == "api" else runtime.web_status()
        _print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if action == "logs":
        state = runtime.service_status(service)
        path = state.get("log_path") or str(runtime.log_path(service))
        _print(runtime.tail_log(path, lines=args.lines))
        return 0
    if action == "open":
        state = runtime.service_status(service)
        url = state.get("url")
        if not url:
            _print(f"{service} is not running. Start it with: zolai-tts {service} start", err=True)
            return 2
        _print(url)
        if args.launch:
            opener = shutil.which("xdg-open")
            if not opener:
                _print("xdg-open not found; URL printed above.", err=True)
                return 2
            subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0
    _print(f"Unknown ui action: {action}", err=True)
    return 2


def cmd_web_build(args: argparse.Namespace) -> int:
    """Build the React frontend (``web/dist``), served by the API at :7860."""
    web = runtime.web_dir()
    if not web.is_dir():
        _print(f"Frontend not found at {web}", err=True)
        return 2
    runner = shutil.which("bun") or shutil.which("npm")
    if not runner:
        _print("Neither bun nor npm found on PATH — cannot build the frontend.", err=True)
        return 2
    base = Path(runner).name
    cmd = [base, "install"] if not (web / "node_modules").is_dir() else None
    if cmd:
        _print(f"==> {' '.join(cmd)} (in {web})")
        rc = subprocess.call(cmd, cwd=str(web))
        if rc != 0:
            return rc
    cmd = [base, "run", "build"]
    _print(f"==> {' '.join(cmd)} (in {web})")
    rc = subprocess.call(cmd, cwd=str(web))
    if rc != 0:
        return rc
    index = runtime.web_dist_index()
    if index.is_file():
        _print(
            f"Built. Start the API to serve it: zolai-tts ui start → "
            f"{runtime.DEFAULT_HOST}:{runtime.DEFAULT_PORT}"
        )
    else:
        _print(f"Build finished but {index} missing — check vite config.", err=True)
        return 1
    return 0


def cmd_up(args: argparse.Namespace) -> int:
    """Start both servers: API (FastAPI :7860) then the Vite dev server (:5174)."""
    api = runtime.start_ui(host=args.host, port=args.port, share=args.share, config=None)
    web = runtime.start_web(port=args.web_port)
    _print(json.dumps({"api": api, "web": web}, indent=2, sort_keys=True))

    api_ok = bool(api.get("ok")) or api.get("error") == "already-running"
    api_url = (api.get("status") or {}).get("url") or f"http://{args.host}:{args.port}"
    web_url = (web.get("status") or {}).get("url")
    if api_ok:
        _print(f"API  {api_url} (health: /api/health)")
    else:
        _print(f"API  not started: {api.get('error', 'unknown')}", err=True)
    if web.get("ok"):
        _print(f"Web  {web_url} (Vite dev, proxies /api to the API)")
    else:
        _print(f"Web  not started: {web.get('error', 'unknown')}", err=True)
    return 0 if api_ok else 2


def cmd_down(_args: argparse.Namespace) -> int:
    """Stop both managed servers (web first, then API)."""
    web = runtime.stop_web()
    api = runtime.stop_ui()
    _print(json.dumps({"api": api, "web": web}, indent=2, sort_keys=True))
    return 0 if web.get("ok") and api.get("ok") else 2


def cmd_both_status(_args: argparse.Namespace) -> int:
    api = runtime.ui_status()
    web = runtime.web_status()
    _print(json.dumps({"api": api, "web": web}, indent=2, sort_keys=True))
    dist = "built" if web.get("dist_ready") else "not built"
    for name, status in (("api", api), ("web", web)):
        if status.get("running"):
            _print(f"{name}: running → {status['url']}")
        else:
            _print(f"{name}: stopped ({status.get('reason', 'no-state')})")
    _print(
        f"web/dist: {dist}"
        + ("  (API serves the app on one port)" if web.get("dist_ready") else "")
    )
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    return _run_module("zolai_tts.data.preprocess", list(args.args))


def cmd_synth(args: argparse.Namespace) -> int:
    return _run_module("zolai_tts.inference.synthesize", list(args.args))


def cmd_ui_cmd(args: argparse.Namespace) -> int:
    return _run_module("zolai_tts.server", list(args.args))


def cmd_test(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "pytest", *args.args]
    return subprocess.call(cmd)


def cmd_lint(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "ruff", "check", "src", "tests", *args.args]
    return subprocess.call(cmd)


def cmd_typecheck(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "mypy", "src", *args.args]
    return subprocess.call(cmd)


def cmd_check(args: argparse.Namespace) -> int:
    steps = [
        ("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests"]),
        ("mypy", [sys.executable, "-m", "mypy", "src"]),
        ("pytest", [sys.executable, "-m", "pytest"]),
    ]
    for name, cmd in steps:
        _print(f"==> {name}")
        rc = subprocess.call(cmd)
        if rc != 0:
            _print(f"{name} failed with exit code {rc}", err=True)
            return rc
    _print("All checks passed.")
    return 0


def cmd_gemini_smoke(args: argparse.Namespace) -> int:
    key_name = next((n for n in GEMINI_KEY_NAMES if os.getenv(n)), None)
    if not key_name:
        _print(
            "No Gemini API key in environment. Set ZOLAI_TTS_GEMINI_API_KEY or GEMINI_API_KEY.",
            err=True,
        )
        return 2
    _print(f"Gemini key detected: {key_name} (present, value redacted)")
    if not args.live:
        _print("Dry smoke only. Re-run with --live to perform a real API request (uses quota).")
        return 0

    try:
        from zolai_tts.providers.gemini import build_interaction_request
    except Exception as exc:
        _print(f"Gemini provider unavailable: {exc}", err=True)
        return 2

    req = build_interaction_request(
        "Pasian", voice=args.voice, language=args.language, model=args.model
    )
    _print(f"Live smoke request prepared for model={req['model']}; sending...")
    try:
        from zolai_tts.providers import gemini as gemini_mod

        client = gemini_mod._client()  # noqa: SLF001 - intentional opt-in smoke path
        interaction = client.interactions.create(**req)
        audio = getattr(interaction, "output_audio", None)
        data = getattr(audio, "data", None) if audio else None
        size = len(data) if isinstance(data, (str, bytes, bytearray)) else 0
        _print(f"Live smoke ok. output_audio present={bool(data)} encoded_size={size}")
        return 0
    except Exception as exc:
        msg = str(exc)
        for name in GEMINI_KEY_NAMES:
            val = os.getenv(name)
            if val:
                msg = msg.replace(val, f"<{name}:redacted>")
        _print(f"Live smoke failed: {msg}", err=True)
        return 1


def cmd_env(args: argparse.Namespace) -> int:
    action = args.env_action
    root = Path.cwd()
    template = root / ".env.example"
    target = Path(args.path)
    if not target.is_absolute():
        target = root / target

    if action == "show":
        _print(f"template={template} exists={template.exists()}")
        _print(f"target={target} exists={target.exists()}")
        if template.exists():
            _print("Template keys:")
            for line in template.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key = line.split("=", 1)[0].strip()
                if key:
                    present = bool(os.getenv(key))
                    _print(f"  - {key}: {'present' if present else 'missing'}")
        _print(
            "No secret values are printed. Edit the target file locally and keep it uncommitted."
        )
        return 0

    if action == "init":
        if not template.exists():
            _print(f"Missing template: {template}", err=True)
            return 2
        if target.exists() and not args.force:
            _print(
                f"Refusing to overwrite existing {target}. Use --force to overwrite.",
                err=True,
            )
            return 2
        target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        with contextlib.suppress(OSError):
            os.chmod(target, 0o600)
        _print(f"Generated {target} from .env.example")
        _print("Next: edit the file, fill placeholders, keep it local (never commit real secrets).")
        _print("Keys are read from environment at runtime; export/source as needed in your shell.")
        return 0

    _print(f"Unknown env action: {action}", err=True)
    return 2


def cmd_openrouter_smoke(args: argparse.Namespace) -> int:
    key_name = next((n for n in OPENROUTER_KEY_NAMES if os.getenv(n)), None)
    if not key_name:
        _print(
            "No OpenRouter API key in environment. "
            "Set ZOLAI_TTS_OPENROUTER_API_KEY or OPENROUTER_API_KEY.",
            err=True,
        )
        return 2
    _print(f"OpenRouter key detected: {key_name} (present, value redacted)")
    try:
        from zolai_tts.providers.openrouter import build_openrouter_request
    except Exception as exc:
        _print(f"OpenRouter provider unavailable: {exc}", err=True)
        return 2

    req = build_openrouter_request(
        "Hello from Zolai-TTS smoke test.",
        voice=args.voice,
        language=args.language,
        model=args.model,
        base_url=args.base_url,
        response_format=args.response_format,
    )
    _print(json.dumps({"mode": "dry-run", "request": req}, indent=2, sort_keys=True))
    if not args.live:
        _print(
            "Dry smoke only. Re-run with --live to perform a real API request (uses quota/credits)."
        )
        return 0

    try:
        from pathlib import Path

        from zolai_tts.ai_sdk.config import resolve_audio_config
        from zolai_tts.ai_sdk.openai_compat import synthesize_speech
        from zolai_tts.ai_sdk.types import AudioRequest

        config = resolve_audio_config(
            provider="openrouter",
            cli={
                "model": args.model,
                "base_url": args.base_url,
                "voice": args.voice,
                "language": args.language,
                "response_format": args.response_format,
            },
        )
        out = Path(args.out)
        result = synthesize_speech(
            AudioRequest(
                text="Hello from Zolai-TTS smoke test.",
                voice=args.voice,
                out_path=out,
                config=config,
            )
        )
        _print(f"Live smoke ok. out_path={result.out_path} bytes={out.stat().st_size}")
        return 0
    except Exception as exc:
        msg = str(exc)
        for name in OPENROUTER_KEY_NAMES:
            val = os.getenv(name)
            if val:
                msg = msg.replace(val, f"<{name}:redacted>")
        _print(f"Live smoke failed: {msg}", err=True)
        return 1


def _ui_ns(action: str, service: str = "api", **overrides: Any) -> argparse.Namespace:
    ns = argparse.Namespace(
        ui_action=action,
        service=service,
        host=runtime.DEFAULT_HOST,
        port=runtime.DEFAULT_PORT if service == "api" else runtime.WEB_DEV_PORT,
        share=False,
        config=None,
        lines=40,
        launch=False,
    )
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


def _menu_actions() -> list[tuple[str, str, Callable[[], int]]]:
    return [
        (
            "Doctor / environment check",
            "doctor",
            lambda: cmd_doctor(argparse.Namespace(json=False)),
        ),
        (
            "Generate .env from .env.example",
            "env init",
            lambda: cmd_env(argparse.Namespace(env_action="init", path=".env", force=False)),
        ),
        (
            "Show env template/status",
            "env show",
            lambda: cmd_env(argparse.Namespace(env_action="show", path=".env", force=False)),
        ),
        (
            "Studio database status",
            "db status",
            lambda: cmd_db(argparse.Namespace(db_action="status")),
        ),
        (
            "Re-derive free/paid tiers (tiers change often)",
            "db reclassify-tiers",
            lambda: cmd_db(argparse.Namespace(db_action="reclassify-tiers")),
        ),
        (
            "Object storage status (local + R2)",
            "db storage",
            lambda: cmd_db(argparse.Namespace(db_action="storage")),
        ),
        ("Servers status (API + Web)", "status", lambda: cmd_both_status(argparse.Namespace())),
        (
            "Run both (API :7860 + Web dev :5174)",
            "up",
            lambda: cmd_up(
                argparse.Namespace(
                    host=runtime.DEFAULT_HOST,
                    port=runtime.DEFAULT_PORT,
                    web_port=runtime.WEB_DEV_PORT,
                    share=False,
                )
            ),
        ),
        ("Stop both", "down", lambda: cmd_down(argparse.Namespace())),
        ("API status (FastAPI :7860)", "ui status", lambda: cmd_ui(_ui_ns("status"))),
        ("API start (FastAPI :7860)", "ui start", lambda: cmd_ui(_ui_ns("start"))),
        ("API stop", "ui stop", lambda: cmd_ui(_ui_ns("stop"))),
        ("API restart", "ui restart", lambda: cmd_ui(_ui_ns("restart"))),
        ("API logs (tail 40)", "ui logs", lambda: cmd_ui(_ui_ns("logs"))),
        ("Web UI status (Vite dev :5174)", "web status", lambda: cmd_ui(_ui_ns("status", "web"))),
        (
            "Web UI dev start (:5174, proxies API)",
            "web start",
            lambda: cmd_ui(_ui_ns("start", "web")),
        ),
        ("Web UI dev stop", "web stop", lambda: cmd_ui(_ui_ns("stop", "web"))),
        ("Web UI dev restart", "web restart", lambda: cmd_ui(_ui_ns("restart", "web"))),
        ("Web UI dev logs (tail 40)", "web logs", lambda: cmd_ui(_ui_ns("logs", "web"))),
        (
            "Web UI build (bun run build → dist)",
            "web build",
            lambda: cmd_web_build(argparse.Namespace()),
        ),
        (
            "Open app (API URL, or dev if running)",
            "open",
            lambda: _cmd_open_app(),
        ),
        ("Run checks (ruff+mypy+pytest)", "check", lambda: cmd_check(argparse.Namespace())),
        ("Run tests (pytest)", "test", lambda: cmd_test(argparse.Namespace(args=[]))),
        ("Run lint (ruff)", "lint", lambda: cmd_lint(argparse.Namespace(args=[]))),
        ("Run typecheck (mypy)", "typecheck", lambda: cmd_typecheck(argparse.Namespace(args=[]))),
        (
            "Prepare --help",
            "prepare --help",
            lambda: cmd_prepare(argparse.Namespace(args=["--help"])),
        ),
        (
            "Synth --help",
            "synth --help",
            lambda: cmd_synth(argparse.Namespace(args=["--help"])),
        ),
        (
            "Server foreground (--help)",
            "ui-app --help",
            lambda: cmd_ui_cmd(argparse.Namespace(args=["--help"])),
        ),
        (
            "Gemini smoke (env-only, no live call)",
            "gemini-smoke",
            lambda: cmd_gemini_smoke(
                argparse.Namespace(live=False, voice="Kore", language="zolai", model=None)
            ),
        ),
        (
            "OpenRouter smoke (env-only, no live call)",
            "openrouter-smoke",
            lambda: cmd_openrouter_smoke(
                argparse.Namespace(
                    live=False,
                    voice="alloy",
                    language="en",
                    model=None,
                    base_url=None,
                    response_format="mp3",
                    out="/tmp/opencode/zolai-tts-openrouter-smoke.mp3",
                )
            ),
        ),
        ("Exit", "exit", lambda: 0),
    ]


def _cmd_open_app() -> int:
    """Print (and optionally launch) the most appropriate app URL."""
    web = runtime.web_status()
    api = runtime.ui_status()
    if web.get("running"):
        return cmd_ui(_ui_ns("open", "web", launch=True))
    if api.get("running"):
        return cmd_ui(_ui_ns("open", "api", launch=True))
    _print("No server running. Start one: Web UI dev start (5174) or API start (7860).", err=True)
    return 2


def cmd_menu(_args: argparse.Namespace) -> int:
    actions = _menu_actions()
    _print("Zolai-TTS menu")
    for i, (label, _, _) in enumerate(actions, start=1):
        _print(f"  {i}. {label}")
    _print("Select an item number, or empty to exit:")
    try:
        choice = input("> ").strip()
    except EOFError:
        return 0
    if not choice:
        return 0
    if not choice.isdigit():
        _print("Invalid selection.", err=True)
        return 2
    idx = int(choice) - 1
    if idx < 0 or idx >= len(actions):
        _print("Selection out of range.", err=True)
        return 2
    label, _, fn = actions[idx]
    if label == "Exit":
        return 0
    return int(fn())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zolai-tts",
        description="Zolai-TTS management CLI: UI lifecycle, checks, and common tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    menu = sub.add_parser("menu", help="Interactive menu")
    menu.set_defaults(func=cmd_menu)

    ui = sub.add_parser("ui", help="Manage the API server process (FastAPI + built web app)")
    ui_sub = ui.add_subparsers(dest="ui_action", required=True)

    def _ui_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--host", default=runtime.DEFAULT_HOST)
        p.add_argument("--port", type=int, default=runtime.DEFAULT_PORT)
        p.add_argument("--share", action="store_true", help="Bind 0.0.0.0 (off by default).")
        p.add_argument("--config", default=None, help="Optional config path (compat flag).")

    p_start = ui_sub.add_parser("start", help="Start the API server in background")
    _ui_common(p_start)
    ui_sub.add_parser("stop", help="Stop the background API server")
    p_restart = ui_sub.add_parser("restart", help="Restart the background API server")
    _ui_common(p_restart)
    ui_sub.add_parser("status", help="Show API server status")
    p_logs = ui_sub.add_parser("logs", help="Tail API server logs")
    p_logs.add_argument("--lines", type=int, default=40)
    p_open = ui_sub.add_parser("open", help="Print API URL; optionally launch browser")
    p_open.add_argument("--launch", action="store_true", help="Open with xdg-open if available.")
    ui.set_defaults(func=cmd_ui, service="api")

    web = sub.add_parser("web", help="Manage the React dev server (Vite) and frontend build")
    web_sub = web.add_subparsers(dest="ui_action", required=True)

    def _web_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--host", default=runtime.DEFAULT_HOST)
        p.add_argument("--port", type=int, default=runtime.WEB_DEV_PORT)
        p.add_argument("--share", action="store_true", help="(unused for web dev)")
        p.add_argument("--config", default=None, help="(unused for web dev)")

    p_wstart = web_sub.add_parser("start", help="Start Vite dev server (:5174, proxies /api)")
    _web_common(p_wstart)
    web_sub.add_parser("stop", help="Stop the Vite dev server")
    p_wrestart = web_sub.add_parser("restart", help="Restart the Vite dev server")
    _web_common(p_wrestart)
    web_sub.add_parser("status", help="Show dev server + build status")
    p_wlogs = web_sub.add_parser("logs", help="Tail Vite dev logs")
    p_wlogs.add_argument("--lines", type=int, default=40)
    p_wopen = web_sub.add_parser("open", help="Print dev URL; optionally launch browser")
    p_wopen.add_argument("--launch", action="store_true")
    p_wbuild = web_sub.add_parser("build", help="Build web/dist (served by the API server)")
    p_wbuild.set_defaults(func=cmd_web_build)
    web.set_defaults(func=cmd_ui, service="web")

    doctor = sub.add_parser("doctor", help="Show environment and tool diagnostics")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    env_cmd = sub.add_parser("env", help="Generate or inspect local .env from .env.example")
    env_sub = env_cmd.add_subparsers(dest="env_action", required=True)
    env_init = env_sub.add_parser(
        "init", help="Generate .env from .env.example (placeholders only)"
    )
    env_init.add_argument("--path", default=".env", help="Target env file path (default: .env)")
    env_init.add_argument("--force", action="store_true", help="Overwrite target if it exists")
    env_init.set_defaults(func=cmd_env)
    env_show = env_sub.add_parser("show", help="Show .env.example and target status (no values)")
    env_show.add_argument("--path", default=".env", help="Target env file path (default: .env)")
    env_show.set_defaults(func=cmd_env)

    db_cmd = sub.add_parser("db", help="Studio database: status, migrations, tier refresh")
    db_sub = db_cmd.add_subparsers(dest="db_action", required=True)
    db_sub.add_parser("status", help="Dialect, masked URL and row counts").set_defaults(func=cmd_db)
    db_reclass = db_sub.add_parser(
        "reclassify-tiers", help="Re-derive free/paid from official signals (tiers change often)"
    )
    db_reclass.set_defaults(func=cmd_db)
    db_migrate = db_sub.add_parser(
        "migrate", help="Import legacy JSON run/recording sidecars into the database"
    )
    db_migrate.add_argument(
        "--store", default=None, help="Legacy store root (default: env store dir)"
    )
    db_migrate.add_argument("--dry-run", action="store_true")
    db_migrate.set_defaults(func=cmd_db)
    db_storage = db_sub.add_parser("storage", help="Object storage status (local + R2)")
    db_storage.set_defaults(func=cmd_db)
    db_copy = db_sub.add_parser("storage-copy", help="Upload local objects to R2")
    db_copy.add_argument("--root", default=None, help="Local object root (default: store/objects)")
    db_copy.set_defaults(func=cmd_db)

    check = sub.add_parser("check", help="Run ruff, mypy, pytest")
    check.set_defaults(func=cmd_check)

    up = sub.add_parser("up", help="Run both servers (API + Vite dev)")
    up.add_argument("--host", default=runtime.DEFAULT_HOST)
    up.add_argument("--port", type=int, default=runtime.DEFAULT_PORT)
    up.add_argument("--web-port", type=int, default=runtime.WEB_DEV_PORT)
    up.add_argument("--share", action="store_true", help="Bind API on 0.0.0.0 as well.")
    up.set_defaults(func=cmd_up)

    down = sub.add_parser("down", help="Stop both managed servers")
    down.set_defaults(func=cmd_down)

    both = sub.add_parser("status", help="Show API + Web server status")
    both.set_defaults(func=cmd_both_status)

    test = sub.add_parser("test", help="Run pytest (passes extra args through)")
    test.add_argument("args", nargs=argparse.REMAINDER)
    test.set_defaults(func=cmd_test)

    lint = sub.add_parser("lint", help="Run ruff check (passes extra args through)")
    lint.add_argument("args", nargs=argparse.REMAINDER)
    lint.set_defaults(func=cmd_lint)

    typecheck = sub.add_parser("typecheck", help="Run mypy src (passes extra args through)")
    typecheck.add_argument("args", nargs=argparse.REMAINDER)
    typecheck.set_defaults(func=cmd_typecheck)

    prep = sub.add_parser("prepare", help="Passthrough to zolai_tts.data.preprocess")
    prep.add_argument("args", nargs=argparse.REMAINDER)
    prep.set_defaults(func=cmd_prepare)

    synth = sub.add_parser("synth", help="Passthrough to zolai_tts.inference.synthesize")
    synth.add_argument("args", nargs=argparse.REMAINDER)
    synth.set_defaults(func=cmd_synth)

    ui_cmd = sub.add_parser("ui-app", help="Passthrough to zolai_tts.server (foreground)")
    ui_cmd.add_argument("args", nargs=argparse.REMAINDER)
    ui_cmd.set_defaults(func=cmd_ui_cmd)

    smoke = sub.add_parser("gemini-smoke", help="Check Gemini key presence; optional live request")
    smoke.add_argument(
        "--live", action="store_true", help="Perform a real API request (uses quota)."
    )
    smoke.add_argument("--voice", default="Kore")
    smoke.add_argument("--language", default="zolai", choices=["ted", "zolai", "zomi", "en"])
    smoke.add_argument("--model", default=None, help="Optional Gemini model override")
    smoke.set_defaults(func=cmd_gemini_smoke)

    or_smoke = sub.add_parser(
        "openrouter-smoke", help="Check OpenRouter key presence; optional live request"
    )
    or_smoke.add_argument(
        "--live", action="store_true", help="Perform a real API request (uses quota/credits)."
    )
    or_smoke.add_argument("--voice", default="alloy")
    or_smoke.add_argument("--language", default="en", choices=["ted", "zolai", "zomi", "en"])
    or_smoke.add_argument("--model", default=None, help="Optional OpenRouter model id")
    or_smoke.add_argument("--base-url", default=None, help="Optional OpenAI-compatible base URL")
    or_smoke.add_argument("--response-format", default="mp3")
    or_smoke.add_argument("--out", default="/tmp/opencode/zolai-tts-openrouter-smoke.mp3")
    or_smoke.set_defaults(func=cmd_openrouter_smoke)

    # Batch TTS (dry-run default; --live opt-in) — see zolai_tts.batch.
    from zolai_tts.batch import add_batch_parser

    add_batch_parser(sub)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Pick up provider keys/config from the project .env before dispatching
    # (no-op without a .env; exported vars are never overridden).
    from zolai_tts.env import ensure_loaded

    ensure_loaded()

    parser = build_parser()
    argv = list(argv) if argv is not None else sys.argv[1:]
    if not argv:
        return cmd_menu(argparse.Namespace())
    # Allow `zolai-tts --help` as normal; argparse handles it.
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    # Normalize REMAINDER args: they may include leading '--'
    for attr in ("args",):
        if hasattr(args, attr) and isinstance(getattr(args, attr), list):
            val = getattr(args, attr)
            if val and val[0] == "--":
                setattr(args, attr, val[1:])
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
