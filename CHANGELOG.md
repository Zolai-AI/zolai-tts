# Changelog

All notable changes to this repository should be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Implemented `src/zolai_tts/` package: frontend normalization, ZVS-attested G2P, phonemizer fallback, dataset validation and text manifest writers, provider protocol/registry, Piper adapter, evaluation helpers and both console scripts.
- Added `zolai-tts` management CLI (`cli.py`) and runtime process control (`runtime.py`) for menu, UI start/stop/restart/status/logs/open, doctor/check/test/lint/typecheck, prepare/synth passthrough, and env-only Gemini smoke. Runtime state/logs live outside git and never persist secrets.
- Added optional `gemini` extra (`google-genai>=2.25.0`) with a Zolai/Zomi demo adapter, lazy SDK import, v1beta Interactions request builder, free-tier/consent warning and opt-in `live` test marker.
- Added OpenRouter/OpenAI-compatible TTS provider (`openrouter`) with env-only API key handling, dry-run request planning, and experimental Zolai/Zomi warnings.
- Added internal `ai_sdk` layer for CLI > config > env > default model/config resolution, redacted config views, OpenAI-compatible speech adapter, and capability-gated LiteLLM/PydanticAI adapters (lazy imports, no base dependency).
- Added CLI/UI model/base-url/response-format controls, OpenRouter smoke command, and local OSS mic/upload media wiring in the local UI (no persistence/upload by default).
- Added versioned JSON Schemas, a placeholder `sample.jsonl`, `configs/example.yaml`, offline tests and documentation updates.

- Replaced the Gradio UI with a local web studio: FastAPI API (`src/zolai_tts/server.py`) plus a React + Vite + Tailwind v4 + shadcn/ui frontend (`web/`). Dynamic provider/model/voice/format catalogs are fetched from live provider APIs using env keys (header only, never returned or stored), with curated offline fallbacks. Saved runs, audio and mic/upload recordings are local-only with sidecar metadata.

### Changed

- Corrected G2P digraph inventory to the ZVS-attested `th, kh, gh, ng, ch, ph, bh` from `zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md`.
- Replaced the unsupported MIT badge with `License: TBD` to match `LICENSE` and `pyproject.toml`.
- Removed the unsatisfiable Coqui extra; Coqui remains a documented research path requiring a separate environment.

### Notes

- No API key, audio, speaker data or model checkpoint is committed.
- Hosted providers have quota/free-tier/data-use limits; no unlimited-free claims. Do not send community data without informed consent.
