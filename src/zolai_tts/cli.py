"""Unified CLI for Zolai-TTS management and tools.

This CLI orchestrates existing modules; it does not duplicate synthesis logic.
It must not persist secrets, and it stores runtime state outside the git repo.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
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
        },
        "modules": {},
        "gpu": {"torch_installed": False, "cuda_available": False, "device_count": 0},
    }

    for mod in ("gradio", "google.genai", "piper", "openai", "litellm", "pydantic_ai", "torch"):
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
    action = args.ui_action
    if action == "start":
        res = runtime.start_ui(host=args.host, port=args.port, share=args.share, config=args.config)
        _print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 2
    if action == "stop":
        res = runtime.stop_ui()
        _print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 2
    if action == "restart":
        res = runtime.restart_ui(
            host=args.host, port=args.port, share=args.share, config=args.config
        )
        _print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res.get("ok") else 2
    if action == "status":
        _print(json.dumps(runtime.ui_status(), indent=2, sort_keys=True))
        return 0
    if action == "logs":
        state = runtime.ui_status()
        path = state.get("log_path") or str(runtime.log_path())
        _print(runtime.tail_log(path, lines=args.lines))
        return 0
    if action == "open":
        state = runtime.ui_status()
        url = state.get("url")
        if not url:
            _print("UI is not running. Start it with: zolai-tts ui start", err=True)
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


def cmd_prepare(args: argparse.Namespace) -> int:
    return _run_module("zolai_tts.data.preprocess", list(args.args))


def cmd_synth(args: argparse.Namespace) -> int:
    return _run_module("zolai_tts.inference.synthesize", list(args.args))


def cmd_ui_cmd(args: argparse.Namespace) -> int:
    return _run_module("zolai_tts.ui.app", list(args.args))


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
            "Dry smoke only. Re-run with --live to perform a real API request "
            "(uses quota/credits)."
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


def _menu_actions() -> list[tuple[str, str, Callable[[], int]]]:
    return [
        (
            "Doctor / environment check",
            "doctor",
            lambda: cmd_doctor(argparse.Namespace(json=False)),
        ),
        ("UI status", "ui status", lambda: cmd_ui(argparse.Namespace(ui_action="status"))),
        (
            "UI start (localhost:7860)",
            "ui start",
            lambda: cmd_ui(
                argparse.Namespace(
                    ui_action="start",
                    host=runtime.DEFAULT_HOST,
                    port=runtime.DEFAULT_PORT,
                    share=False,
                    config=None,
                )
            ),
        ),
        ("UI stop", "ui stop", lambda: cmd_ui(argparse.Namespace(ui_action="stop"))),
        (
            "UI restart",
            "ui restart",
            lambda: cmd_ui(
                argparse.Namespace(
                    ui_action="restart",
                    host=runtime.DEFAULT_HOST,
                    port=runtime.DEFAULT_PORT,
                    share=False,
                    config=None,
                )
            ),
        ),
        (
            "UI logs (tail 40)",
            "ui logs",
            lambda: cmd_ui(argparse.Namespace(ui_action="logs", lines=40)),
        ),
        ("Run checks (ruff+mypy+pytest)", "check", lambda: cmd_check(argparse.Namespace())),
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

    ui = sub.add_parser("ui", help="Manage local Gradio UI process")
    ui_sub = ui.add_subparsers(dest="ui_action", required=True)

    def _ui_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--host", default=runtime.DEFAULT_HOST)
        p.add_argument("--port", type=int, default=runtime.DEFAULT_PORT)
        p.add_argument("--share", action="store_true", help="Pass --share to UI (off by default).")
        p.add_argument("--config", default=None, help="Optional UI config path.")

    p_start = ui_sub.add_parser("start", help="Start UI in background")
    _ui_common(p_start)
    ui_sub.add_parser("stop", help="Stop background UI")
    p_restart = ui_sub.add_parser("restart", help="Restart background UI")
    _ui_common(p_restart)
    ui_sub.add_parser("status", help="Show UI status")
    p_logs = ui_sub.add_parser("logs", help="Tail UI logs")
    p_logs.add_argument("--lines", type=int, default=40)
    p_open = ui_sub.add_parser("open", help="Print UI URL; optionally launch browser")
    p_open.add_argument("--launch", action="store_true", help="Open with xdg-open if available.")
    ui.set_defaults(func=cmd_ui)

    doctor = sub.add_parser("doctor", help="Show environment and tool diagnostics")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    check = sub.add_parser("check", help="Run ruff, mypy, pytest")
    check.set_defaults(func=cmd_check)

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

    ui_cmd = sub.add_parser("ui-app", help="Passthrough to zolai_tts.ui.app (foreground)")
    ui_cmd.add_argument("args", nargs=argparse.REMAINDER)
    ui_cmd.set_defaults(func=cmd_ui_cmd)

    smoke = sub.add_parser(
        "gemini-smoke", help="Check Gemini key presence; optional live request"
    )
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

    return parser


def main(argv: Sequence[str] | None = None) -> int:
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
