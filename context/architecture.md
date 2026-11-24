# Architecture Context

## Stack

Stack names come from `pyproject.toml`, `project.yaml` and `docs/architecture.md`.

| Layer | Technology | Role | Source |
|-------|-----------|------|--------|
| Language | Python | Research tooling language | project.yaml, pyproject.toml |
| Packaging | Hatchling | Build backend | pyproject.toml |
| Package manager | uv | Declared package manager | project.yaml |
| Audio | librosa, soundfile, pydub | Resampling, trimming, feature extraction | pyproject.toml, README.md |
| Text | phonemizer (fallback), custom rules | G2P fallback and ZVS 2018-safe normalization | pyproject.toml, docs/pronunciation.md |
| Data | jsonschema, pyyaml, pandas | Metadata validation and config loading | pyproject.toml, docs/architecture.md |
| CLI | argparse, tqdm, rich | Console scripts and terminal output | pyproject.toml, src/zolai_tts |
| Synthesis backends | Piper (local), optional Gemini (hosted) | Real voice path and experimental demos | pyproject.toml, README.md |
| Testing | pytest, ruff, mypy | Dev tooling declared in the manifest | pyproject.toml |

`google-genai>=2.25.0` is an optional extra; `piper-tts` is guarded to Python <3.13. Coqui TTS is deliberately not an extra because it hard-pins `pandas<2.0`.

## System Boundaries

- `src/zolai_tts/frontend/` — implemented ZVS 2018-safe normalization, provisional G2P and phonemizer fallback (source: `docs/architecture.md`, `tests/test_normalize.py`, `tests/test_g2p.py`).
- `src/zolai_tts/data/` — implemented JSON Schema validation and LJSpeech/Piper text manifest writers (source: `dataset/schemas/`, `src/zolai_tts/data/`).
- `src/zolai_tts/inference/` — implemented `TTSProvider` protocol, frozen `SynthesisResult`, canonical registry and synthesis CLI (source: `src/zolai_tts/inference/`).
- `src/zolai_tts/providers/` — implemented Piper adapter (real voice) and optional Gemini adapter (source: `src/zolai_tts/providers/`).
- `src/zolai_tts/ui/` — optional local Gradio research/demo UI over existing provider contracts; lazy Gradio import, localhost/`share=False` default, not a hosted production service (source: `src/zolai_tts/ui/app.py`, `pyproject.toml`).
- `src/zolai_tts/cli.py`, `src/zolai_tts/runtime.py` — management CLI and UI process runtime control (start/stop/restart/status/logs/doctor/check/passthroughs). Orchestrates existing modules only; runtime state/logs outside git; no secret persistence (source: `src/zolai_tts/cli.py`, `src/zolai_tts/runtime.py`).
- `src/zolai_tts/evaluation/` — implemented duration helper and Markdown report renderer (source: `src/zolai_tts/evaluation/`).
- `configs/`, `dataset/schemas/`, `dataset/metadata/` — committed example config, versioned schemas and placeholder metadata (source: `configs/`, `dataset/`).
- `tests/` — offline pytest suite plus opt-in `live` marker (source: `pyproject.toml`, `tests/`).

## Storage Model

- Versioned schemas and small metadata live in `dataset/schemas/` and `dataset/metadata/` (source: `docs/architecture.md`).
- Large audio, corpora and checkpoints stay outside git in shared storage, Hugging Face or Kaggle (source: `docs/architecture.md`, AGENTS.md).
- Application database: N/A (source: `pyproject.toml`).

## Auth and Access Model

- No application authentication or access-control model exists (source: `pyproject.toml`, `docs/architecture.md`).
- API keys are read only inside the optional Gemini adapter at synthesis time, from `ZOLAI_TTS_GEMINI_API_KEY` or `GEMINI_API_KEY` (source: `src/zolai_tts/providers/gemini.py`).
- Never commit API keys, tokens, private speaker data or unpublished recordings (source: README.md, AGENTS.md).

## System Design & Infrastructure

| Concept | Service / Tech | Notes | Source |
|---------|---------------|-------|--------|
| Compute | N/A | Offline CLI tooling; optional local Gradio UI is localhost-only research/demo | pyproject.toml, src/zolai_tts/ui/app.py |
| Database | N/A | No database dependency | pyproject.toml |
| Object Storage | Shared storage / Hugging Face / Kaggle | Home for large artifacts | docs/architecture.md |
| CDN / Cache / Queue | N/A | No hosted service endpoint | docs/architecture.md |
| Microservices | zolai-core integration | ZVS rules referenced, not imported | docs/architecture.md |
| Observability | Local logs / optional experiment tracking | No hosted service in this slice | README.md |
| Streaming / Realtime | N/A | Batch CLI/UI form design only | docs/architecture.md |

## Scaling & Performance Constraints

- Traffic volume, latency target, data growth, availability and budget: UNKNOWN (source: `docs/architecture.md`).

## Invariants

1. Framework-first: Tedim language logic in `frontend/`, synthesis delegated to adapters (source: `docs/architecture.md`).
2. Framework-specific code stays in `providers/` and `configs/`; optional local UI stays in `ui/`; management CLI/runtime orchestrates existing modules and does not duplicate synthesis logic. No from-scratch model implementation (source: `docs/architecture.md`).
3. Large audio and checkpoints stay outside git (source: `docs/architecture.md`, AGENTS.md).
4. Dataset schemas are versioned in `dataset/schemas/` (source: `docs/architecture.md`).
5. ZVS 2018 is ground truth by reference to `zolai-core`; no cross-repo copy or invented phonology/numerals (source: `docs/pronunciation.md`).
6. Base imports make no network call, read no key and import no optional backend/UI package (source: `src/zolai_tts`, `tests/test_gemini.py`, `src/zolai_tts/ui/app.py`).
7. Canonical provider keys are exactly `piper` and `gemini`; there is no `local` alias (source: `src/zolai_tts/inference/base.py`).
8. Piper is the real Zolai voice; Gemini uses `ted`/`zolai`/`zomi` only as experimental demos with a free-tier/consent warning (source: `src/zolai_tts/providers/gemini.py`, README.md).
9. Optional UI is local research/demo only: localhost bind, `share=False` default, no auth/production claims (source: `src/zolai_tts/ui/app.py`, README.md).
10. Runtime/process state and logs live outside git (preferred `/tmp/opencode/zolai-tts-<uid>/`, fallback XDG runtime/cache) and must never persist API keys, tokens, or secret values (source: `src/zolai_tts/runtime.py`, `src/zolai_tts/cli.py`).
