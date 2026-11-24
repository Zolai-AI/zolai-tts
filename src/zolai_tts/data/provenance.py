"""Tracked batch manifest + legal/provenance gate.

The manifest is the **only** home of owner/license/consent_ref (they are never
written to the registry database). It is tracked in git; audio is not (it lives
under the gitignored ``artifacts/`` directory).

Publish gate: anything but ``legal_status == "verified"`` is hard-blocked.
Free-tier terms are unverified today, so ``unverified`` blocks publishing —
and provider-owned default voices can never be claimed as Zolai-owned audio.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = 1

#: The only legal status that permits publishing.
VERIFIED_LEGAL_STATUS = "verified"


class PublishBlockedError(RuntimeError):
    """Raised when a publish attempt is made on a non-verified manifest."""


def sha256_text(text: str) -> str:
    """SHA-256 of the exact input text (UTF-8) — payload-fidelity anchor."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def publish_allowed(legal_status: str | None) -> bool:
    """Publishing is allowed only for ``verified`` — everything else blocks."""
    return str(legal_status or "").strip().lower() == VERIFIED_LEGAL_STATUS


def assert_publishable(legal_status: str | None, *, context: str = "") -> None:
    """Raise :class:`PublishBlockedError` unless ``legal_status`` is verified."""
    if not publish_allowed(legal_status):
        shown = legal_status or "<unset>"
        raise PublishBlockedError(
            f"publish blocked: legal_status={shown!r} (requires "
            f"{VERIFIED_LEGAL_STATUS!r})"
            + (f" — {context}" if context else "")
            + ". Free-tier terms are unverified; provider-owned default voices "
            "cannot be claimed as Zolai-owned audio."
        )


def build_manifest(
    *,
    batch_id: str,
    seed: int,
    provider: str,
    model: str,
    voice_key: str,
    legal_status: str,
    items: list[dict[str, Any]],
    input_path: str,
    production_guarantee: bool | None = None,
    tags_applied: bool = False,
) -> dict[str, Any]:
    """Assemble the tracked manifest document (pure — no disk writes).

    ``items`` entries: ``{id, text, sha256, tags, style, audio_path}``.
    ``owner``/``license``/``consent_ref`` default to ``None`` — they must be
    filled in by a human before any publish attempt can pass the gate.
    """
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "batch_id": batch_id,
        "seed": seed,
        "input_path": input_path,
        "provider": provider,
        "model": model,
        "voice_key": voice_key,
        "legal_status": legal_status,
        "legal_notes": None,
        "owner": None,
        "license": None,
        "consent_ref": None,
        "production_guarantee": production_guarantee,
        "tags_applied": tags_applied,
        "items": items,
    }


def write_manifest(path: Path | str, manifest: dict[str, Any]) -> Path:
    """Write the manifest as stable, diff-friendly JSON (2-space, sorted keys)."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
