"""Synthesis CLI with canonical providers: ``piper`` (real voice) or ``gemini``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from zolai_tts.inference.base import ProviderError, get_provider

# Registration side effects only; neither module imports an SDK at module scope.
from zolai_tts.providers import gemini, piper  # noqa: F401


def load_config(path: Path | None) -> dict[str, Any]:
    """Load a small YAML config safely; ignore unknown keys at call sites."""
    if path is None:
        return {}
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def _plan(
    *, provider: str, voice: str | None, language: str, text: str, out: str | None
) -> dict[str, Any]:
    return {
        "provider": provider,
        "voice": voice,
        "language": language,
        "text": text,
        "out": out,
        "mode": "dry-run",
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point for ``zolai-tts-synth``."""
    parser = argparse.ArgumentParser(
        prog="zolai-tts-synth",
        description="Synthesize speech through a registered TTS provider.",
    )
    parser.add_argument("--text")
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--provider", choices=("piper", "gemini"))
    parser.add_argument("--voice")
    parser.add_argument("--language", choices=("ted", "zolai", "zomi", "en"))
    parser.add_argument("--out")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        if args.text is not None and args.text_file is not None:
            raise ValueError("Use only one of --text or --text-file")
        provider = args.provider or config.get("provider") or "piper"
        if provider not in ("piper", "gemini"):
            raise ValueError(
                f"Unknown provider {provider!r}. Available providers: gemini, piper"
            )
        language = args.language or config.get("language") or "ted"
        voice = args.voice or config.get("voice")
        out = args.out or config.get("out")
        if args.text_file is not None:
            text = args.text_file.read_text(encoding="utf-8")
        else:
            text = args.text if args.text is not None else config.get("text")

        if args.dry_run:
            plan = _plan(
                provider=provider, voice=voice, language=language, text=text or "", out=out
            )
            if provider == "gemini":
                plan["request"] = gemini.build_interaction_request(
                    text or "", voice=voice or "", language=language
                )
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
            return 0

        if not text:
            raise ValueError("Text is required: pass --text, --text-file or config text")
        if not voice:
            raise ValueError("A real voice is required: pass --voice or config voice")
        if not out:
            raise ValueError("Output path is required: pass --out or config out")
        selected = get_provider(provider, language=language)
        result = selected.synthesize(text, voice, Path(out))
        print(
            json.dumps(
                {
                    "provider": result.provider,
                    "voice": result.voice,
                    "out_path": str(result.out_path),
                    "metadata": result.metadata,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError, ProviderError) as exc:
        print(f"zolai-tts-synth: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
