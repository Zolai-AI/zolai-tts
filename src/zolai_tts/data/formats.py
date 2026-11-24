"""Text-only manifest writers (no audio is generated or committed here)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def to_ljspeech(records: Iterable[Mapping[str, Any]], out_path: Path) -> int:
    """Write ``id|text_normalized|`` lines and return the record count."""
    lines = [f"{record['id']}|{record['text_normalized']}|" for record in records]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
    )
    return len(lines)


def to_piper(records: Iterable[Mapping[str, Any]], out_path: Path) -> int:
    """Write a JSONL manifest of id/text/audio_path and return the count."""
    lines = [
        json.dumps(
            {
                "id": record["id"],
                "text": record["text_normalized"],
                "audio_path": record["audio_path"],
            },
            ensure_ascii=False,
        )
        for record in records
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
    )
    return len(lines)
