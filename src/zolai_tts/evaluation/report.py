"""Dependency-free Markdown report rendering for synthesis results."""

from __future__ import annotations

from collections.abc import Mapping

from zolai_tts.inference.base import SynthesisResult


def render_report(
    result: SynthesisResult, metrics: Mapping[str, float] | None = None
) -> str:
    """Render a short Markdown evaluation report."""
    lines = [
        "# Zolai-TTS synthesis report",
        "",
        f"- Provider: `{result.provider}`",
        f"- Voice: `{result.voice}`",
        f"- Output: `{result.out_path}`",
        f"- Duration (s): {result.duration_seconds}",
    ]
    if result.metadata:
        lines += ["", "## Metadata", ""]
        lines += [f"- `{key}`: {value}" for key, value in sorted(result.metadata.items())]
    if metrics:
        lines += ["", "## Metrics", "", "| Metric | Value |", "| --- | --- |"]
        lines += [f"| {key} | {value} |" for key, value in sorted(metrics.items())]
    return "\n".join(lines) + "\n"
