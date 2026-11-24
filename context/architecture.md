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
| Synthesis backends | Piper (local), OpenRouter (default hosted), Gemini (optional alternate), Fish Audio via OpenRouter (hosted/OpenAI-compatible) | Real local voice path and experimental hosted demos | pyproject.toml, README.md, `src/zolai_tts/batch.py` |
| AI SDK layer | internal `ai_sdk` + optional `openai`/`litellm`/`pydantic-ai-slim` | Config resolution and capability-gated adapters | pyproject.toml, src/zolai_tts/ai_sdk |
| Testing | pytest, ruff, mypy | Dev tooling declared in the manifest | pyproject.toml |

`google-genai>=2.25.0` is an optional extra; `piper-tts` is guarded to Python <3.13. Coqui TTS is deliberately not an extra because it hard-pins `pandas<2.0`.

## System Boundaries

- `src/zolai_tts/frontend/` — implemented ZVS 2018-safe normalization, provisional G2P and phonemizer fallback (source: `docs/architecture.md`, `tests/test_normalize.py`, `tests/test_g2p.py`).
- `src/zolai_tts/data/` — implemented JSON Schema validation and LJSpeech/Piper text manifest writers (source: `dataset/schemas/`, `src/zolai_tts/data/`).
- `src/zolai_tts/inference/` — implemented `TTSProvider` protocol, frozen `SynthesisResult`, canonical registry and synthesis CLI (source: `src/zolai_tts/inference/`).
- `src/zolai_tts/providers/` — implemented Piper adapter, optional Gemini adapter, and optional OpenRouter/OpenAI-compatible adapter (source: `src/zolai_tts/providers/`).
- `src/zolai_tts/batch.py` — batch TTS: JSONL → per-item audio + tracked manifest. **Dry-run is the default (no network, no audio, no files); `--live` opts in.** Provider matrix (A7): `openrouter` (DEFAULT, `heygen/heygen-voice-1-turbo:free`, streams 44.1 kHz mono PCM, 39 languages, max 5,000 chars/request, 10 default provider voices, optional bring-your-own HeyGen key for consented clones), `fish-audio` (`fish-audio/s2.1-pro-free:free`, same OpenRouter SDK path + same env key, no-cost/low-volume testing tier), `gemini` (optional alternate, `interactions.create` v1beta `gemini-3.8-flash-tts`). Free models carry `production_guarantee=false` and print that warning in dry-run; no SLA claims either way. Requests are chunked to ≤5,000 chars; streamed raw PCM is wrapped into a proper 44.1 kHz mono WAV header (already-WAV/MP3 bytes pass through untouched — no silent corruption) (source: `src/zolai_tts/batch.py`, `tests/test_batch_tts.py`).
- `src/zolai_tts/voice_lookup.py` — voice resolution: API-first (`GET /api/v1/tts/voices/{voice_key}`), read-only SQLite fallback via `ZOLAI_DB_PATH` (`file:...?mode=ro`). Dry-run resolves offline (never touches the network). Unknown/inactive/missing `voice_key` fails loudly — there is no silent default voice (source: `src/zolai_tts/voice_lookup.py`, `tests/test_voice_resolution.py`).
- `src/zolai_tts/data/provenance.py` — tracked batch manifest (`schema_version`, `seed`, `provider`, `model`, `voice_key`, `legal_status`, `production_guarantee`, `tags_applied`, per-item `id`/`text`/`sha256`/`tags`/`style`/`audio_path`) plus the publish gate: only `legal_status == 'verified'` is publishable; `unverified` (free-tier terms) hard-blocks. `owner`/`license`/`consent_ref` live in the tracked manifest only, never in the registry DB (source: `src/zolai_tts/data/provenance.py`, `tests/test_batch_tts.py`).
- `src/zolai_tts/ai_sdk/` — internal AI SDK layer for config/model/base-url/response-format resolution, redacted config views, OpenAI-compatible speech adapter, and capability-gated LiteLLM/PydanticAI adapters (source: `src/zolai_tts/ai_sdk/`).
- `src/zolai_tts/ui/` — optional local Gradio research/demo UI over existing provider contracts; lazy Gradio import, localhost/`share=False` default, model/base-url/format inputs, mic/upload local media wiring, not a hosted production service (source: `src/zolai_tts/ui/app.py`, `pyproject.toml`).
- `src/zolai_tts/cli.py`, `src/zolai_tts/runtime.py` — management CLI and UI process runtime control (start/stop/restart/status/logs/doctor/check/passthroughs, gemini/openrouter smoke). Orchestrates existing modules only; runtime state/logs outside git; no secret persistence (source: `src/zolai_tts/cli.py`, `src/zolai_tts/runtime.py`).
- `src/zolai_tts/evaluation/` — implemented duration helper and Markdown report renderer (source: `src/zolai_tts/evaluation/`).
- `configs/`, `dataset/schemas/`, `dataset/metadata/` — committed example config, versioned schemas and placeholder metadata (source: `configs/`, `dataset/`).
- `tests/` — offline pytest suite plus opt-in `live` marker (source: `pyproject.toml`, `tests/`).

## Storage Model

- Versioned schemas and small metadata live in `dataset/schemas/` and `dataset/metadata/` (source: `docs/architecture.md`).
- Large audio, corpora and checkpoints stay outside git in shared storage, Hugging Face or Kaggle (source: `docs/architecture.md`, AGENTS.md).
- Batch audio is written under `artifacts/` (gitignored); the batch manifest is tracked under `manifests/` (source: `.gitignore`, `src/zolai_tts/batch.py`).
- Application database: none owned by this repo. The TTS voice registry is **read-only** from here — resolved API-first against zolai-core, with a `file:...?mode=ro` SQLite fallback via `ZOLAI_DB_PATH`; this repo never creates or writes that store (source: `src/zolai_tts/voice_lookup.py`, `pyproject.toml`).

## Auth and Access Model

- No application authentication or access-control model exists (source: `pyproject.toml`, `docs/architecture.md`).
- API keys are read only inside the optional Gemini adapter at synthesis time, from `ZOLAI_TTS_GEMINI_API_KEY` or `GEMINI_API_KEY` (source: `src/zolai_tts/providers/gemini.py`).
- Hosted TTS keys are env-only: OpenRouter/Fish Audio use `ZOLAI_TTS_OPENROUTER_API_KEY` or `OPENROUTER_API_KEY` (one key, no new key name per provider); a bring-your-own HeyGen key for consented voice clones is also env-only and requires a consent record — never commit any of them. `zolai-core`'s `/api/v1/tts/*` routes are read-only behind `require_role("member")` (source: `src/zolai_tts/batch.py`, `zolai-core/zolai/api/tts.py`).
- Never commit API keys, tokens, private speaker data or unpublished recordings (source: README.md, AGENTS.md).

## System Design & Infrastructure

| Concept | Service / Tech | Notes | Source |
|---------|---------------|-------|--------|
| Compute | N/A | Offline CLI tooling; optional local Gradio UI is localhost-only research/demo | pyproject.toml, src/zolai_tts/ui/app.py |
| Database | None owned; read-only view of the zolai-core TTS registry | API-first voice lookup, `mode=ro` SQLite fallback via `ZOLAI_DB_PATH` | src/zolai_tts/voice_lookup.py |
| Object Storage | Shared storage / Hugging Face / Kaggle | Home for large artifacts | docs/architecture.md |
| CDN / Cache / Queue | N/A | No hosted service endpoint | docs/architecture.md |
| Microservices | zolai-core integration | ZVS rules referenced, not imported | docs/architecture.md |
| Observability | Local logs / optional experiment tracking | No hosted service in this slice | README.md |
| Streaming / Realtime | N/A | Batch CLI/UI form design only | docs/architecture.md |

## Scaling & Performance Constraints

- Traffic volume, latency target, data growth, availability and budget: UNKNOWN (source: `docs/architecture.md`).

## Invariants

1. Framework-first: Tedim language logic in `frontend/`, synthesis delegated to adapters (source: `docs/architecture.md`).
2. Framework-specific code stays in `providers/` and `configs/`; config/model resolution and optional AI adapters live in `ai_sdk/`; optional local UI stays in `ui/`; management CLI/runtime orchestrates existing modules and does not duplicate synthesis logic. No from-scratch model implementation (source: `docs/architecture.md`).
3. Large audio and checkpoints stay outside git (source: `docs/architecture.md`, AGENTS.md).
4. Dataset schemas are versioned in `dataset/schemas/` (source: `docs/architecture.md`).
5. ZVS 2018 is ground truth by reference to `zolai-core`; no cross-repo copy or invented phonology/numerals (source: `docs/pronunciation.md`).
6. Base imports make no network call, read no key and import no optional backend/UI package (source: `src/zolai_tts`, `tests/test_gemini.py`, `src/zolai_tts/ui/app.py`).
7. Canonical provider keys are exactly `piper`, `gemini`, and `openrouter`; there is no `local` alias (source: `src/zolai_tts/inference/base.py`).
8. Piper is the real Zolai voice; Gemini/OpenRouter use `ted`/`zolai`/`zomi` only as experimental demos with explicit warnings and no native Tedim support claims (source: `src/zolai_tts/providers/gemini.py`, `src/zolai_tts/providers/openrouter.py`, README.md).
9. Optional UI is local research/demo only: localhost bind, `share=False` default, no auth/production claims; mic/upload is local OSS wiring and not persisted/uploaded by default (source: `src/zolai_tts/ui/app.py`, README.md).
10. Runtime/process state and logs live outside git (preferred `/tmp/opencode/zolai-tts-<uid>/`, fallback XDG runtime/cache) and must never persist API keys, tokens, or secret values (source: `src/zolai_tts/runtime.py`, `src/zolai_tts/cli.py`).
11. Config precedence is CLI > config YAML > environment > defaults; API keys are env-only at call time and redacted in logs/doctor/dry-run/config views (source: `src/zolai_tts/ai_sdk/config.py`).
12. Hosted providers have quotas/free-tier/data-use limits and no unlimited-free claims; do not send community data without informed consent (source: README.md).
