"""Filesystem locations shared by the server, CLI and storage layer.

Everything runtime-generated lives outside the repository:
  * state/logs  -> `/tmp/opencode/zolai-tts-<uid>/` (see `runtime.state_dir`)
  * data objects-> `$XDG_DATA_HOME/zolai-tts` (default `~/.local/share/zolai-tts`)

No secrets are ever written here: API keys stay in the environment or the
in-memory session store (`zolai_tts.secrets`).
"""

from __future__ import annotations

import os
from pathlib import Path


def store_dir() -> Path:
    """Root for the database, audio objects and run sidecars."""
    raw = os.getenv("ZOLAI_TTS_STORE_DIR", "").strip()
    root = Path(raw).expanduser() if raw else Path.home() / ".local" / "share" / "zolai-tts"
    for sub in ("objects", "outputs", "runs", "recordings", "contributions"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def objects_dir() -> Path:
    return store_dir() / "objects"


def web_dist_path() -> Path:
    """Built React frontend, served by the API at `/`."""
    override = os.getenv("ZOLAI_TTS_WEB_DIST", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def web_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "web"
