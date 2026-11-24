# Code Standards

## General

- Focus on Tedim speech synthesis research and tooling (source: AGENTS.md).
- Read `README.md` and `context/` files before architectural decisions (source: AGENTS.md).
- Keep datasets, models and large artifacts out of git unless explicitly tracked through the chosen artifact workflow (source: AGENTS.md).
- ZVS 2018 is language ground truth; this is RAG/embeddings-first research, not raw fine-tuning (source: workspace AGENTS.md recorded in repo AGENTS.md).

## TypeScript

- N/A — no TypeScript source (source: `pyproject.toml`).

## Python

- `pyproject.toml` declares the package, dependency groups, console scripts, Hatchling backend and Ruff/pytest/mypy configuration; follow it rather than a separate config file.
- Use `uv` for all environments. Run `uv run --extra dev python -m pytest` (not an external `pytest` binary), plus Ruff and mypy.
- Base imports must not import optional backends, read API keys or make network calls. Optional packages (`piper`, `google-genai`, `openai`, `litellm`, `pydantic-ai-slim`, `gradio`) are imported lazily inside methods/functions.
- Canonical provider keys are `piper`, `gemini`, and `openrouter`; do not add aliases such as `local`. The batch CLI's `--provider fish-audio` reuses the `openrouter` transport/config key (a model choice, not a new registry key) (source: `src/zolai_tts/batch.py`).
- Config precedence is CLI > config YAML > environment > defaults. Use `ai_sdk.config.resolve_audio_config`; never persist or log secret values. Redacted config views may expose only key presence/env name.
- Hosted providers (Gemini/OpenRouter/Fish Audio via OpenRouter/OpenAI-compatible) are experimental for Tedim/Zolai/Zomi and have no native support claims. No unlimited-free claims; document quota/free-tier/data-use limits and require informed consent before sending community data.
- Provider matrix (A7): default `openrouter` → `heygen/heygen-voice-1-turbo:free` (HeyGen Voice Turbo; 44.1 kHz mono PCM, 39 languages, 5,000 chars/request max, 10 default voices, optional consented bring-your-own HeyGen clone key); `fish-audio` → `fish-audio/s2.1-pro-free:free` (same OpenRouter SDK path and env key, no-cost tier for testing/prototyping/low-volume use, no production latency/availability guarantees); `gemini` → `gemini-3.8-flash-tts` (optional `interactions.create` v1beta alternate). `--provider` choices are `openrouter|fish-audio|gemini`, default `openrouter`; `--model` overrides. Free-tier `production_guarantee=false` is recorded in the manifest and warned in dry-run; no SLA claims either way.
- Batch discipline: dry-run default (no network, no files), `--live` opt-in; requests chunked to ≤5,000 chars; raw PCM wrapped with a proper 44.1 kHz mono WAV header (existing RIFF/MP3 bytes pass through — never silent corruption); Gemini `<...>` tags and `speech_metadata.style` are Gemini-only — for OpenRouter/Fish Audio runs tags/style stay manifest source annotations with `tags_applied=false` and are never injected into provider `input`.
- Legal gate: `legal_status` defaults to `unverified` (free-tier terms unverified) and anything but `verified` is publish-blocked; provider-owned default voices are never claimed as Zolai-owned audio; `owner`/`license`/`consent_ref` live only in the tracked manifest (source: `src/zolai_tts/data/provenance.py`, `src/zolai_tts/batch.py`).
- Optional AI adapters are capability-gated: LiteLLM/PydanticAI are not canonical TTS execution paths unless explicitly implemented and tested; prefer OpenRouter/OpenAI-compatible adapter for `/audio/speech`.
- Default tests run offline; network tests use the `live` marker and require both `ZOLAI_TTS_RUN_LIVE=1` and a key. Mock SDKs for 4xx/5xx/error mapping; no live network/quota in default tests.
- `NUMBER_WORDS` is an explicit no-op stub; do not invent Tedim numerals or copy ZVS tables across repos.
- Python remains authoritative for language tooling; no NestJS or Rust service layer is added (source: AGENTS.md).

## Styling / UI

- Optional local UI lives in `src/zolai_tts/ui/` and uses Gradio Blocks via the optional `ui` extra. Gradio must be imported lazily inside `build_app()`/`main()`; base imports must not import Gradio or optional synthesis backends (source: `src/zolai_tts/ui/app.py`, `pyproject.toml`).
- UI is local research/demo only: bind localhost, default `share=False`, no auth/production claims, no persistent queue. Do not add cloud sharing by default (source: `src/zolai_tts/ui/app.py`).
- UI tests must `pytest.importorskip("gradio")`, must not launch a server, and must not make network calls (source: `tests/test_ui.py`).

## CLI / Runtime

- `zolai-tts` is the management CLI (`src/zolai_tts/cli.py`) with subcommands for `menu`, `ui start|stop|restart|status|logs|open`, `doctor`, `check|test|lint|typecheck`, `prepare`, `synth`, `ui-app`, and `gemini-smoke`. It orchestrates existing modules via subprocess/module calls; it must not duplicate synthesis logic.
- Runtime state/logs are stored outside git (preferred `/tmp/opencode/zolai-tts-<uid>/`, fallback XDG runtime/cache). State JSON contains only PID/host/port/cmd/started_at/log_path/cwd; never store API keys, tokens, or secret values.
- `doctor` and `*-smoke` commands report environment key presence only and must never print or persist secret values. `gemini-smoke --live` and `openrouter-smoke --live` are opt-in and use quota/network/credits.
- UI process management must validate PID and cmdline contains `zolai_tts.ui.app` before trusting state; clean stale state.
- CLI/runtime tests must be offline: mock subprocess, os.kill, xdg-open, env, and time; use temp state dirs.

## API Routes

- N/A — no service endpoints; this is an offline CLI/tooling slice (source: `docs/architecture.md`).

## Data and Storage

- Version dataset schemas in `dataset/schemas/`; track only small metadata examples (source: `docs/architecture.md`).
- Keep large audio, corpora and checkpoints in shared storage or external dataset hosts (source: `docs/architecture.md`, AGENTS.md).
- Never commit API keys, tokens, private speaker data or unpublished recordings (source: README.md).

## File Organization

- `src/zolai_tts/frontend/`, `data/`, `inference/`, `providers/`, `evaluation/` — implemented package (source: `src/`).
- `configs/`, `dataset/schemas/`, `dataset/metadata/`, `tests/` — committed config, schemas, placeholder metadata and tests (source: repository tree).
- `docs/` — architecture, dataset, pronunciation, framework and deprecated roadmap notes.
- `pyproject.toml` — package metadata and tooling configuration.
