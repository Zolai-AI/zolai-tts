"""Versioned JSON Schema validation for utterance metadata."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema


@dataclass(frozen=True)
class ValidationReport:
    """Count of checked records plus ordered validation errors."""

    checked: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def load_schema(path: Path) -> Mapping[str, Any]:
    """Load a JSON Schema from ``path``."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_record(record: Any, schema: Mapping[str, Any]) -> tuple[str, ...]:
    """Return deterministic error strings for one record."""
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
    return tuple(
        f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in errors
    )


def validate_jsonl(path: Path, schema_path: Path) -> ValidationReport:
    """Validate every non-blank line of a JSONL file against a schema."""
    schema = load_schema(schema_path)
    errors: list[str] = []
    checked = 0
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        checked += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
            continue
        for error in validate_record(record, schema):
            errors.append(f"line {line_number}: {error}")
    return ValidationReport(checked=checked, errors=tuple(errors))
