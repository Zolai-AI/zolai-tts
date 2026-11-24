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

from zolai_tts.ai_sdk.config import resolve_audio_config
from zolai_tts.inference.base import ProviderError, get_provider
from zolai_tts.inference.synthesize import load_config

# Registration side effects only; neither module imports an SDK at module scope.
from zolai_tts.providers import gemini, openrouter, piper  # noqa: F401

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
    *,
    provider: str,
    voice: str | None,
    language: str,
    text: str,
    out: str | None,
    model: str | None = None,
    base_url: str | None = None,
    response_format: str | None = None,
) -> dict[str, Any]:
    config = resolve_audio_config(
        provider=provider,
        cli={
            "model": model,
            "base_url": base_url,
            "voice": voice,
            "language": language,
            "response_format": response_format,
        },
    )
    plan: dict[str, Any] = {
        "provider": provider,
        "voice": voice,
        "language": language,
        "model": config.model,
        "base_url": config.base_url,
        "response_format": config.response_format,
        "config": config.redacted(),
        "text": text,
        "out": out,
        "mode": "dry-run",
    }
    if provider == "gemini":
        plan["request"] = gemini.build_interaction_request(
            text, voice=voice or "", language=language, model=model
        )
    if provider == "openrouter":
        plan["request"] = openrouter.build_openrouter_request(
            text,
            voice=voice or "",
            language=language,
            model=model,
            base_url=base_url,
            response_format=response_format,
        )
    return plan


def synthesize_ui(
    text: str,
    provider: str,
    language: str,
    voice: str,
    model: str,
    base_url: str,
    response_format: str,
    out_path: str,
    dry_run: bool,
) -> tuple[dict[str, Any], str | None]:
    """Run synthesis/dry-run for the UI and return (result_json, audio_path)."""
    text = (text or "").strip()
    voice = (voice or "").strip()
    model = (model or "").strip()
    base_url = (base_url or "").strip()
    response_format = (response_format or "").strip()
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
            model=model or None,
            base_url=base_url or None,
            response_format=response_format or None,
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
            options: dict[str, Any] = {"language": language}
            if provider in {"gemini", "openrouter"} and model:
                options["model"] = model
            if provider == "openrouter":
                if base_url:
                    options["base_url"] = base_url
                if response_format:
                    options["response_format"] = response_format
            selected = get_provider(provider, **options)
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
    if default_provider not in {"piper", "gemini", "openrouter"}:
        default_provider = "piper"
    default_language = str(config.get("language") or "ted")
    if default_language not in {"ted", "zolai", "zomi", "en"}:
        default_language = "ted"

    provider_meta: dict[str, dict[str, Any]] = {
        "piper": {
            "label": "Piper (local, real voice path)",
            "voice_label": "Voice model path (.onnx)",
            "voice_placeholder": "/path/to/your-zolai-voice.onnx",
            "model_placeholder": "Not used by Piper (local ONNX voice)",
            "base_url_placeholder": "Not used by Piper",
            "format_placeholder": "wav",
            "default_format": "wav",
            "default_model": "",
            "default_base_url": "",
            "languages": ["ted", "zolai", "zomi", "en"],
            "needs_key": False,
            "note": (
                "Piper is the real local Zolai voice path. "
                "Python <3.13 for piper-tts; dry-run works."
            ),
        },
        "gemini": {
            "label": "Gemini (optional hosted, experimental)",
            "voice_label": "Voice name",
            "voice_placeholder": "Kore (or another Gemini voice)",
            "model_placeholder": "gemini-3.8-flash-tts",
            "base_url_placeholder": "Optional Gemini-compatible base URL",
            "format_placeholder": "wav",
            "default_format": "wav",
            "default_model": "gemini-3.8-flash-tts",
            "default_base_url": "",
            "languages": ["ted", "zolai", "zomi", "en"],
            "needs_key": True,
            "note": (
                "Gemini is experimental for Tedim/Zolai/Zomi. "
                "Env key only; free-tier quota applies."
            ),
        },
        "openrouter": {
            "label": "OpenRouter (optional OpenAI-compatible)",
            "voice_label": "Voice name (model-specific)",
            "voice_placeholder": "alloy (check selected model docs)",
            "model_placeholder": (
                "openai/gpt-4o-mini-tts | fish-audio/s2.1-pro-free:free | "
                "heygen/heygen-voice-1-turbo:free"
            ),
            "base_url_placeholder": (
                "https://openrouter.ai/api/v1 (or local OpenAI-compatible endpoint)"
            ),
            "format_placeholder": "mp3",
            "default_format": "mp3",
            "default_model": "openai/gpt-4o-mini-tts",
            "default_base_url": "https://openrouter.ai/api/v1",
            "languages": ["ted", "zolai", "zomi", "en"],
            "needs_key": True,
            "note": (
                "OpenRouter/OpenAI-compatible. Env key only; quotas/credits/data-use vary. "
                "Free-tagged models are not unlimited-free."
            ),
        },
    }

    def _provider_defaults(name: str, current: dict[str, Any] | None = None) -> dict[str, Any]:
        meta = provider_meta.get(name, provider_meta["piper"])
        current = current or {}
        return {
            "voice_label": meta["voice_label"],
            "voice_placeholder": meta["voice_placeholder"],
            "model_placeholder": meta["model_placeholder"],
            "base_url_placeholder": meta["base_url_placeholder"],
            "format_placeholder": meta["format_placeholder"],
            "default_model": meta["default_model"],
            "default_base_url": meta["default_base_url"],
            "default_format": meta["default_format"],
            "languages": meta["languages"],
            "needs_key": meta["needs_key"],
            "note": meta["note"],
        }

    def _on_provider_change(
        selected_provider: str,
        current_language: str,
        current_model: str,
        current_base_url: str,
        current_format: str,
    ):
        meta = provider_meta.get(selected_provider, provider_meta["piper"])
        languages = [str(x) for x in meta.get("languages", ["en"])]
        lang = current_language if current_language in languages else languages[0]
        model_val = (
            current_model
            if (current_model or "").strip()
            else str(meta.get("default_model", ""))
        )
        base_val = (
            current_base_url
            if (current_base_url or "").strip()
            else str(meta.get("default_base_url", ""))
        )
        fmt_val = (
            current_format
            if (current_format or "").strip()
            else str(meta.get("default_format", "wav"))
        )
        key_note = (
            "Requires env API key (never stored in repo/UI state)."
            if bool(meta.get("needs_key"))
            else "No API key required."
        )
        return (
            gr.update(
                label=str(meta.get("voice_label", "Voice")),
                placeholder=str(meta.get("voice_placeholder", "")),
            ),
            gr.update(value=model_val, placeholder=str(meta.get("model_placeholder", ""))),
            gr.update(
                value=base_val,
                placeholder=str(meta.get("base_url_placeholder", "")),
                visible=selected_provider != "piper",
            ),
            gr.update(value=fmt_val, placeholder=str(meta.get("format_placeholder", ""))),
            gr.update(choices=languages, value=lang),
            gr.update(value=f"**Provider note:** {meta.get('note', '')}  \n**Key:** {key_note}"),
        )

    defaults = _provider_defaults(default_provider)
    with gr.Blocks(title="Zolai TTS") as demo:
        gr.Markdown(
            "# Zolai TTS\n"
            "Local research/demo UI over existing Zolai-TTS providers. "
            "Piper is the real local voice path; Gemini/OpenRouter are optional hosted "
            "paths and have no native Tedim/Zolai/Zomi TTS support.\n\n"
            "**Quick start:** choose provider, language, voice/model. "
            "Use Dry run for a safe plan; disable it for real synthesis "
            "(hosted providers need env key)."
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
                choices=["piper", "gemini", "openrouter"],
                value=default_provider,
            )
            language = gr.Dropdown(
                label="Language",
                choices=defaults["languages"],
                value=(
                    default_language
                    if default_language in defaults["languages"]
                    else defaults["languages"][0]
                ),
            )
        with gr.Row():
            voice = gr.Textbox(
                label=defaults["voice_label"],
                value=str(config.get("voice") or ""),
                placeholder=defaults["voice_placeholder"],
            )
            model = gr.Textbox(
                label="Model (optional)",
                value=str(config.get("model") or defaults["default_model"]),
                placeholder=defaults["model_placeholder"],
            )
        with gr.Row():
            base_url = gr.Textbox(
                label="Base URL (optional, OpenAI-compatible)",
                value=str(config.get("base_url") or defaults["default_base_url"]),
                placeholder=defaults["base_url_placeholder"],
                visible=default_provider != "piper",
            )
            response_format = gr.Textbox(
                label="Response format (optional)",
                value=str(config.get("response_format") or defaults["default_format"]),
                placeholder=defaults["format_placeholder"],
            )
        key_note = (
            "Requires env API key (never stored in repo/UI state)."
            if defaults["needs_key"]
            else "No API key required."
        )
        provider_note = gr.Markdown(
            f"**Provider note:** {defaults['note']}  \n**Key:** {key_note}"
        )
        with gr.Row():
            out_path = gr.Textbox(
                label="Output audio path (real synthesis)",
                value=str(config.get("out") or "/tmp/opencode/zolai-tts-ui/out.wav"),
            )
        with gr.Accordion("Mic / Upload (OSS, local only)", open=False):
            gr.Audio(
                label="Mic/Upload (not persisted by default; not sent anywhere by this UI)",
                sources=["microphone", "upload"],
                type="filepath",
            )
            gr.Markdown(
                "Browser mic permission is required for recording. "
                "If no mic is found, check OS/browser permissions.\n\n"
                "Captured audio is local UI input only; "
                "no STT/transcription is wired in this build."
            )
        dry_run = gr.Checkbox(label="Dry run (no audio, no key/model required)", value=True)
        run = gr.Button("Synthesize / Dry run", variant="primary")
        result_json = gr.JSON(label="Result")
        audio = gr.Audio(label="Output audio", type="filepath")
        gr.Markdown(
            "Notes: local only (`share=False`), no auth, no secrets stored. "
            "Mic/upload is optional local media wiring and is not sent anywhere by this UI. "
            "Hosted providers may have quota/free-tier/data-use limits; no unlimited-free claims. "
            "Do not send community data without informed consent."
        )

        provider.change(
            fn=_on_provider_change,
            inputs=[provider, language, model, base_url, response_format],
            outputs=[voice, model, base_url, response_format, language, provider_note],
        )
        run.click(
            fn=synthesize_ui,
            inputs=[
                text, provider, language, voice, model,
                base_url, response_format, out_path, dry_run,
            ],
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
