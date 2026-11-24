"""Load the project ``.env`` file into ``os.environ`` at process start.

Why this exists
---------------
Provider keys are read exclusively from ``os.environ`` (see ``secrets.py``,
``catalog.py``, ``ai_sdk/config.py``), but no entry point ever parsed the
``.env`` file — so a key that *is* in ``.env`` was invisible to the server and
synthesis failed with "no env API key; showing curated models". This module
closes that gap without adding a dependency.

Rules (mirrors common dotenv semantics, stdlib only):
  * Real environment variables always win — existing keys are never overridden
    unless ``override=True`` is passed explicitly.
  * ``#`` comments, blank lines and a leading ``export `` are handled.
  * Matching single/double quotes around a value are stripped.
  * ``KEY=`` (empty) is skipped, so a placeholder ``.env`` cannot blank a
    value that was exported properly.
  * Values are never logged or returned — only key names.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

_lock = threading.Lock()
_ensure_done = False

ENV_FILENAME = ".env"
ENV_PATH_VAR = "ZOLAI_TTS_DOTENV"


def _package_root() -> Path:
    # src/zolai_tts/env.py -> repo root is two parents above the package dir
    return Path(__file__).resolve().parents[2]


def dotenv_candidates(start: Path | None = None) -> list[Path]:
    """Candidate .env paths, most specific first."""
    candidates: list[Path] = []
    explicit = os.getenv(ENV_PATH_VAR, "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if start is not None:
        candidates.append(Path(start).expanduser() / ENV_FILENAME)
    candidates.append(Path.cwd() / ENV_FILENAME)
    root = _package_root()
    candidates.append(root / ENV_FILENAME)
    # also allow a parent checkout layout (repo nested in a workspace)
    candidates.append(root.parent / ENV_FILENAME)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _parse_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export ") :].lstrip()
    name, sep, value = text.partition("=")
    if not sep:
        return None
    name = name.strip()
    if (
        not name
        or not (name[0].isalpha() or name[0] == "_")
        or not all(ch.isalnum() or ch in "_." for ch in name)
    ):
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return name, value


def load_dotenv(
    path: str | os.PathLike[str] | None = None,
    *,
    override: bool = False,
) -> list[str]:
    """Parse one .env file into ``os.environ``.

    Returns the names that were set (values are never returned). A missing
    file yields an empty list — never an error, so packaged installs without
    a local .env behave exactly as before.
    """
    loaded: list[str] = []
    paths = [Path(path).expanduser()] if path is not None else dotenv_candidates()
    file = next((p for p in paths if p.is_file()), None)
    if file is None:
        return loaded
    try:
        raw = file.read_text(encoding="utf-8")
    except OSError:
        return loaded
    for line in raw.splitlines():
        parsed = _parse_line(line)
        if parsed is None:
            continue
        name, value = parsed
        if not value:
            continue
        if override or name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return loaded


def ensure_loaded(*, override: bool = False) -> list[str]:
    """Idempotent process-start hook for entry points (CLI, server, runtime)."""
    global _ensure_done
    with _lock:
        if _ensure_done:
            return []
        names = load_dotenv(override=override)
        _ensure_done = True
        return names
