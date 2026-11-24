"""Optional Gradio web interface for Zolai-TTS.

This module is a lightweight local research/demo surface over existing provider
contracts. It must not import Gradio or optional synthesis backends at module
import time.
"""

from __future__ import annotations

import argparse
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from zolai_tts.inference.base import ProviderError, get_provider
from zolai_tts.inference.synthesize import load_config

# Registration side effects only; neither module imports an SDK at module scope.
from zolai_tts.providers import gemini, piper  # noqa: F401

_UI_INSTALL_HINT = (
    "Gradio UI is not installed. Install with: uv sync --extra ui "
    "(or python -m pip install -e '.[ui]')."
)


def _require_gradio() -> Any:
    try:
        import gradio as gr
    except ImportError as exc:  # pragma: no cover - exercised via runtime check
        raise RuntimeError(_UI_INSTALL_HINT) from exc
    return gr


def _plan(
    *, provider: str, voice: str | None, language: str, text: str, out: str | None
) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "provider": provider,
        "voice": voice,
        "language": language,
        "text": text,
        "out": out,
        "mode": "dry-run",
    }
    if provider == "gemini":
        plan["request"] = gemini.build_interaction_request(
            text, voice=voice or "", language=language
        )
    return plan


def synthesize_ui(
    text: str,
    provider: str,
    language: str,
    voice: str,
    out_path: str,
    dry_run: bool,
) -> tuple[dict[str, Any], str | None]:
    """Run synthesis/dry-run for the UI and return (result_json, audio_path)."""
    text = (text or "").strip()
    voice = (voice or "").strip()
    out_path = (out_path or "").strip()
    if not text:
        return {"ok": False, "error": "Text is required."}, None

    if dry_run:
        plan = _plan(
            provider=provider,
            voice=voice or None,
            language=language,
            text=text,
            out=out_path or None,
        )
        return {"ok": True, "result": plan}, None

    if not voice:
        return {
            "ok": False,
            "error": "A real voice is required: provide a voice/model name or path.",
        }, None
    if not out_path:
        return {
            "ok": False,
            "error": "Output path is required for real synthesis.",
        }, None

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            selected = get_provider(provider, language=language)
            result = selected.synthesize(text, voice, Path(out_path))
        payload: dict[str, Any] = {
            "ok": True,
            "result": {
                "provider": result.provider,
                "voice": result.voice,
                "out_path": str(result.out_path),
                "metadata": result.metadata,
            },
        }
        if caught:
            payload["warnings"] = [str(item.message) for item in caught]
        return payload, str(result.out_path)
    except (OSError, ValueError, ProviderError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}, None


def build_app(*, config_path: Path | None = None) -> Any:
    """Build the Gradio Blocks app. Gradio is imported lazily here."""
    gr = _require_gradio()
    config = load_config(config_path)

    default_provider = str(config.get("provider") or "piper")
    if default_provider not in {"piper", "gemini"}:
        default_provider = "piper"
    default_language = str(config.get("language") or "ted")
    if default_language not in {"ted", "zolai", "zomi", "en"}:
        default_language = "ted"

    with gr.Blocks(title="Zolai TTS") as demo:
        gr.Markdown(
            "# Zolai TTS\n"
            "Local research/demo UI over existing Zolai-TTS providers. "
            "Piper is the real local voice path; Gemini is optional/experimental "
            "and has no native Tedim/Zolai/Zomi TTS support."
        )
        with gr.Row():
            text = gr.Textbox(
                label="Text",
                value=str(config.get("text") or ""),
                lines=4,
                placeholder="Enter Tedim/Zolai/Zomi or English text...",
            )
        with gr.Row():
            provider = gr.Dropdown(
                label="Provider",
                choices=["piper", "gemini"],
                value=default_provider,
            )
            language = gr.Dropdown(
                label="Language",
                choices=["ted", "zolai", "zomi", "en"],
                value=default_language,
            )
        with gr.Row():
            voice = gr.Textbox(
                label="Voice / model path",
                value=str(config.get("voice") or ""),
                placeholder="Piper: /path/to/voice.onnx | Gemini: voice name e.g. Kore",
            )
            out_path = gr.Textbox(
                label="Output WAV path (real synthesis)",
                value=str(config.get("out") or "/tmp/opencode/zolai-tts-ui/out.wav"),
            )
        dry_run = gr.Checkbox(label="Dry run (no audio, no key/model required)", value=True)
        run = gr.Button("Synthesize / Dry run", variant="primary")
        result_json = gr.JSON(label="Result")
        audio = gr.Audio(label="Output audio", type="filepath")
        gr.Markdown(
            "Notes: local only (`share=False`), no auth, no secrets stored. "
            "Gemini free-tier content may be used to improve Google products; "
            "do not send community data without informed consent."
        )

        run.click(
            fn=synthesize_ui,
            inputs=[text, provider, language, voice, out_path, dry_run],
            outputs=[result_json, audio],
        )
    return demo


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point for ``zolai-tts-ui``."""
    parser = argparse.ArgumentParser(
        prog="zolai-tts-ui",
        description="Launch the optional local Gradio UI for Zolai-TTS.",
    )
    parser.add_argument("--config", type=Path, help="Optional YAML config for defaults.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: localhost).")
    parser.add_argument("--port", type=int, default=7860, help="Bind port (default: 7860).")
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public Gradio share link (off by default; local research only).",
    )
    args = parser.parse_args(argv)

    app = build_app(config_path=args.config)
    app.launch(server_name=args.host, server_port=args.port, share=args.share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
