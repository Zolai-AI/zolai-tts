# Changelog

All notable changes to this repository should be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Implemented `src/zolai_tts/` package: frontend normalization, ZVS-attested G2P, phonemizer fallback, dataset validation and text manifest writers, provider protocol/registry, Piper adapter, evaluation helpers and both console scripts.
- Added `zolai-tts` management CLI (`cli.py`) and runtime process control (`runtime.py`) for menu, UI start/stop/restart/status/logs/open, doctor/check/test/lint/typecheck, prepare/synth passthrough, and env-only Gemini smoke. Runtime state/logs live outside git and never persist secrets.
- Added optional `gemini` extra (`google-genai>=2.25.0`) with a Zolai/Zomi demo adapter, lazy SDK import, v1beta Interactions request builder, free-tier/consent warning and opt-in `live` test marker.
- Added versioned JSON Schemas, a placeholder `sample.jsonl`, `configs/example.yaml`, offline tests and documentation updates.

### Changed

- Corrected G2P digraph inventory to the ZVS-attested `th, kh, gh, ng, ch, ph, bh` from `zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md`.
- Replaced the unsupported MIT badge with `License: TBD` to match `LICENSE` and `pyproject.toml`.
- Removed the unsatisfiable Coqui extra; Coqui remains a documented research path requiring a separate environment.

### Notes

- No API key, audio, speaker data or model checkpoint is committed.
