"""Objective helpers with no heavy imports at module scope."""

from __future__ import annotations

from pathlib import Path


def duration_seconds(path: Path) -> float:
    """Read audio duration with soundfile (optional backend)."""
    import soundfile as sf

    info = sf.info(str(path))
    return float(info.duration)


def pcm_duration_seconds(num_frames: int, *, sample_rate: int = 24000) -> float:
    """Pure duration calculation for PCM frames."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    return num_frames / sample_rate
