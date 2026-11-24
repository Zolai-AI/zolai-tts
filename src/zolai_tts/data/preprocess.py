"""Dataset preparation CLI: validate JSONL metadata and emit a text manifest."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from zolai_tts.data.formats import to_ljspeech, to_piper
from zolai_tts.data.validate import validate_jsonl

DEFAULT_SCHEMA = "dataset/schemas/utterance.schema.json"


def _read_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def preprocess(
    input_path: Path,
    out_dir: Path,
    schema_path: Path,
    fmt: str = "piper",
) -> int:
    """Validate ``input_path`` and write a manifest into ``out_dir``."""
    report = validate_jsonl(input_path, schema_path)
    if not report.valid:
        raise ValueError("metadata validation failed:\n" + "\n".join(report.errors))
    records = _read_records(input_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "piper":
        written = to_piper(records, out_dir / "metadata.jsonl")
    elif fmt == "ljspeech":
        written = to_ljspeech(records, out_dir / "metadata.csv")
    else:
        raise ValueError(f"Unknown format {fmt!r}; expected 'piper' or 'ljspeech'")
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point for ``zolai-tts-prepare``."""
    parser = argparse.ArgumentParser(
        prog="zolai-tts-prepare",
        description="Validate utterance JSONL and write a text-only manifest.",
    )
    parser.add_argument("--input", required=True, type=Path, help="input JSONL metadata")
    parser.add_argument("--schema", type=Path, default=Path(DEFAULT_SCHEMA))
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--format", choices=("piper", "ljspeech"), default="piper")
    args = parser.parse_args(argv)
    try:
        count = preprocess(args.input, args.out_dir, args.schema, args.format)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"zolai-tts-prepare: {exc}", file=sys.stderr)
        return 2
    print(f"zolai-tts-prepare: wrote {count} records to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
