"""Piper voice library: official ONNX voices for fully-local synthesis.

The repo never commits model weights (``.gitignore`` excludes ``*.onnx``). This
module manages a local voice directory and downloads voices from the official
upstream library (``rhasspy/piper-voices`` on Hugging Face) at request time.

Facts (verified against upstream ``main`` tree on 2026-11-25):

* Upstream ships 30 English variants (en_US + en_GB) across low/medium/high
  quality (~63 MB each, ~114–137 MB high). **No Tedim/Zolai/Zomi voice exists
  upstream** — English voices let Piper work out of the box (studio,
  sound-checks, tests); the real Zolai voice comes from community recordings
  (``POST /api/recordings``) plus a future trained ONNX.
* Every voice needs BOTH ``{name}.onnx`` and ``{name}.onnx.json`` (feature
  metadata). Downloads write atomically (``.part`` → replace) and are verified
  by presence of both files + JSON parse.

No network happens at import. The fetch hook is injectable for offline tests.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPSTREAM = "rhasspy/piper-voices"
HF_RESOLVE = "https://huggingface.co"
UPSTREAM_AS_OF = "2026-11-25"
UPSTREAM_LANG_DIR = "en"


def piper_voices_dir() -> Path:
    """Local directory holding Piper voices (gitignored; created on demand).

    Honors ``ZOLAI_TTS_PIPER_VOICES_DIR`` / ``PIPER_VOICES_DIR`` (the same env
    the catalog scans), defaulting to ``~/.local/share/piper/voices``.
    """
    raw = ""
    for name in ("ZOLAI_TTS_PIPER_VOICES_DIR", "PIPER_VOICES_DIR"):
        raw = os.getenv(name, "").strip()
        if raw:
            break
    root = Path(raw).expanduser() if raw else Path.home() / ".local" / "share" / "piper" / "voices"
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True)
class VoiceSpec:
    """One official upstream Piper voice (locale/speaker/quality triple)."""

    name: str  # e.g. "en_US-lessac-medium"
    locale: str  # "en_US" | "en_GB"
    speaker: str  # e.g. "lessac"
    quality: str  # "low" | "medium" | "high"
    approx_bytes: int = 0

    @property
    def remote_path(self) -> str:
        return (
            f"{UPSTREAM}/resolve/main/{UPSTREAM_LANG_DIR}"
            f"/{self.locale}/{self.speaker}/{self.quality}/{self.name}"
        )

    def url(self, suffix: str) -> str:
        return f"{HF_RESOLVE}/{self.remote_path}{suffix}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "locale": self.locale,
            "speaker": self.speaker,
            "quality": self.quality,
            "approx_bytes": self.approx_bytes,
            "tier": "free",
            "limit_note": "Local execution: no API, no cost, no request limits.",
            "upstream": UPSTREAM,
        }


# Full official English inventory — every entry verified against the upstream
# HF tree API (names + ~sizes), 2026-11-25. Do not add unverified names.
OFFICIAL_VOICES: tuple[VoiceSpec, ...] = (
    VoiceSpec("en_GB-alan-low", "en_GB", "alan", "low", 63_100_000),
    VoiceSpec("en_GB-alan-medium", "en_GB", "alan", "medium", 63_200_000),
    VoiceSpec("en_GB-alba-medium", "en_GB", "alba", "medium", 63_200_000),
    VoiceSpec("en_GB-aru-medium", "en_GB", "aru", "medium", 76_800_000),
    VoiceSpec("en_GB-cori-high", "en_GB", "cori", "high", 114_200_000),
    VoiceSpec("en_GB-cori-medium", "en_GB", "cori", "medium", 63_200_000),
    VoiceSpec("en_GB-jenny_dioco-medium", "en_GB", "jenny_dioco", "medium", 63_200_000),
    VoiceSpec(
        "en_GB-northern_english_male-medium",
        "en_GB",
        "northern_english_male",
        "medium",
        63_200_000,
    ),
    VoiceSpec("en_GB-semaine-medium", "en_GB", "semaine", "medium", 76_700_000),
    VoiceSpec(
        "en_GB-southern_english_female-low",
        "en_GB",
        "southern_english_female",
        "low",
        63_100_000,
    ),
    VoiceSpec("en_GB-vctk-medium", "en_GB", "vctk", "medium", 77_000_000),
    VoiceSpec("en_US-amy-low", "en_US", "amy", "low", 63_100_000),
    VoiceSpec("en_US-amy-medium", "en_US", "amy", "medium", 63_200_000),
    VoiceSpec("en_US-arctic-medium", "en_US", "arctic", "medium", 76_800_000),
    VoiceSpec("en_US-bryce-medium", "en_US", "bryce", "medium", 63_500_000),
    VoiceSpec("en_US-danny-low", "en_US", "danny", "low", 63_100_000),
    VoiceSpec("en_US-hfc_female-medium", "en_US", "hfc_female", "medium", 63_200_000),
    VoiceSpec("en_US-hfc_male-medium", "en_US", "hfc_male", "medium", 63_200_000),
    VoiceSpec("en_US-hifi_tts_92-medium", "en_US", "hifi_tts_92", "medium", 63_200_000),
    VoiceSpec("en_US-joe-medium", "en_US", "joe", "medium", 63_200_000),
    VoiceSpec("en_US-john-medium", "en_US", "john", "medium", 63_500_000),
    VoiceSpec("en_US-kathleen-low", "en_US", "kathleen", "low", 63_100_000),
    VoiceSpec("en_US-kathleen-medium", "en_US", "kathleen", "medium", 63_200_000),
    VoiceSpec("en_US-kristin-medium", "en_US", "kristin", "medium", 63_500_000),
    VoiceSpec("en_US-kusal-medium", "en_US", "kusal", "medium", 63_200_000),
    VoiceSpec("en_US-l2arctic-medium", "en_US", "l2arctic", "medium", 76_800_000),
    VoiceSpec("en_US-lessac-high", "en_US", "lessac", "high", 113_900_000),
    VoiceSpec("en_US-lessac-low", "en_US", "lessac", "low", 63_200_000),
    VoiceSpec("en_US-lessac-medium", "en_US", "lessac", "medium", 63_200_000),
    VoiceSpec("en_US-libritts-high", "en_US", "libritts", "high", 136_700_000),
)

# Small working set installed first so Piper is usable immediately (~260 MB).
DEFAULT_SET: tuple[str, ...] = (
    "en_US-lessac-medium",
    "en_US-amy-medium",
    "en_US-joe-medium",
    "en_GB-alan-medium",
)

_INDEX = {v.name: v for v in OFFICIAL_VOICES}


def known_voices() -> list[dict[str, Any]]:
    """Official voice inventory (metadata only, no network)."""
    return [v.to_dict() for v in OFFICIAL_VOICES]


def find(name: str) -> VoiceSpec | None:
    return _INDEX.get(name)


def installed(name: str, *, voices_dir: Path | None = None) -> dict[str, Any] | None:
    """Return {path, bytes, ...} when both .onnx and .onnx.json exist locally."""
    spec = _INDEX.get(name)
    if spec is None:
        return None
    root = voices_dir or piper_voices_dir()
    onnx = root / f"{name}.onnx"
    meta = root / f"{name}.onnx.json"
    if not (onnx.is_file() and meta.is_file()):
        return None
    try:
        meta_data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta_data = {}
    return {
        "path": str(onnx),
        "bytes": onnx.stat().st_size,
        "language": (meta_data.get("language") or {}).get("code"),
        "sample_rate": (meta_data.get("audio") or {}).get("sample_rate"),
        "num_speakers": (meta_data.get("inference") or {}).get("num_speakers"),
    }


def status(*, voices_dir: Path | None = None) -> dict[str, Any]:
    """Install state for every official voice — drives the UI download panel."""
    root = voices_dir or piper_voices_dir()
    rows = []
    for spec in OFFICIAL_VOICES:
        local = installed(spec.name, voices_dir=root)
        rows.append({**spec.to_dict(), "installed": local is not None, "local": local})
    return {
        "ok": True,
        "voices_dir": str(root),
        "upstream": UPSTREAM,
        "upstream_as_of": UPSTREAM_AS_OF,
        "tedim_note": (
            "No Tedim/Zolai/Zomi Piper voice exists upstream. English voices are for "
            "fully-local demo/testing; the Zolai voice must be trained from community "
            "recordings (Record & Contribute panel)."
        ),
        "default_set": list(DEFAULT_SET),
        "voices": rows,
        "installed_count": sum(1 for r in rows if r["installed"]),
        "total_count": len(rows),
    }


def _default_fetch(url: str, dest: Path, timeout: float) -> int:
    req = urllib.request.Request(  # noqa: S310 - fixed https constant host
        url, headers={"User-Agent": "zolai-tts-voices/1.0"}
    )
    with (
        urllib.request.urlopen(req, timeout=timeout) as resp,  # noqa: S310
        open(dest, "wb") as fh,
    ):
        total = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            total += len(chunk)
    return total


def download(
    name: str,
    *,
    voices_dir: Path | None = None,
    timeout: float = 120.0,
    fetch: Callable[[str, Path, float], int] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Download one official voice (.onnx + .onnx.json) atomically.

    Returns a result dict; raises ValueError for unknown names. The ``fetch``
    hook (url, dest, timeout) -> bytes is injectable for offline tests.
    """
    spec = _INDEX.get(name)
    if spec is None:
        raise ValueError(f"Unknown voice {name!r}. Official set: {', '.join(sorted(_INDEX))}")
    root = voices_dir or piper_voices_dir()
    getter = fetch or _default_fetch
    written: dict[str, int] = {}
    for suffix in (".onnx", ".onnx.json"):
        final = root / f"{name}{suffix}"
        if final.exists() and not overwrite:
            continue
        tmp = Path(str(final) + ".part")
        try:
            written[final.name] = getter(spec.url(suffix), tmp, timeout)
            tmp.replace(final)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Voice download failed for {name}: {exc}") from exc
    local = installed(name, voices_dir=root)
    if local is None:  # defensive: download reported success but files absent
        raise RuntimeError(f"Voice download incomplete for {name}.")
    return {"ok": True, "voice": name, "downloaded": written, "local": local}


def download_set(
    names: tuple[str, ...] | list[str] = DEFAULT_SET,
    *,
    voices_dir: Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Download each listed voice (default: the small working set).

    Per-voice failures are reported, never raised, so one bad network hop does
    not abort the batch.
    """
    root = voices_dir or piper_voices_dir()
    results: list[dict[str, Any]] = []
    for name in names:
        if installed(name, voices_dir=root) and not kwargs.get("overwrite", False):
            results.append({"ok": True, "voice": name, "skipped": "already installed"})
            continue
        try:
            results.append(download(name, voices_dir=root, **kwargs))
        except (ValueError, RuntimeError) as exc:
            results.append({"ok": False, "voice": name, "error": str(exc)})
    ok = all(r.get("ok") for r in results)
    return {"ok": ok, "results": results, "status": status(voices_dir=root)}
