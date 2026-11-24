# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- IMPLEMENTED SCAFFOLD / EXPERIMENTAL — offline pipeline and CLI contracts are implemented; no trained community voice is shipped (source: README.md, `src/zolai_tts/`).

## Current Goal

- Provide a reproducible, framework-first Tedim/Zolai TTS tooling slice with versioned schemas, offline tests and an optional Zolai/Zomi Gemini demo path (source: README.md, `docs/architecture.md`).

## Completed

- 2026-11-24 — Implemented the full scaffold: `src/zolai_tts/` frontend (normalize, ZVS-attested G2P, phonemizer fallback), data validation/format writers, provider protocol and registry, Piper adapter, optional Gemini adapter, synthesis/prepare CLIs, evaluation helpers, configs, versioned JSON Schemas, placeholder fixture and six offline test modules. Corrected the G2P digraph inventory from a draft list to the ZVS-attested `th, kh, gh, ng, ch, ph, bh` (`zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md:45-55,104`).
- 2026-11-24 — Gemini adapter uses `ted`/`zolai`/`zomi`/`en` codes; Mizo is not used. Zolai-family requests emit an explicit no-native-support and free-tier/consent warning.
- 2026-11-24 — Fixed manifest resolution: removed the unsatisfiable Coqui extra (`pandas<2.0` vs base `>=2.2`); documented Coqui as a separate research environment.
- 2026-11-24 — Updated README, `docs/architecture.md`, `docs/framework-selection.md`, `docs/dataset-guidelines.md`, `docs/pronunciation.md`, `context/architecture.md`, `context/code-standards.md`, `context/project-overview.md`, this tracker, CHANGELOG, and absorbed `.ignore`.
- Prior — replaced six context scaffolds with committed HEAD evidence; aligned with canonical workspace SDLC and source-of-truth (source: git history).
- 2026-11-24 — Corrected stale HEAD-state claims in `context/ai-workflow-rules.md` (implemented `src/`, tracked `uv.lock`, committed `dataset/`/`configs/`, `docs/` status) and recorded local pytest environment divergence here. Files: `context/ai-workflow-rules.md`, `context/progress-tracker.md`. Impact: workflow rules match the implemented scaffold; no runtime behavior changed.
- 2026-11-24 — Added an UNKNOWN-by-default IPA research scaffold for the seven ZVS-attested digraphs; no IPA values asserted and G2P/phonemizer left unchanged. Files: `src/zolai_tts/frontend/ipa_research.py`, `tests/test_ipa_research.py`, `context/progress-tracker.md`. Impact: research-only placeholder mapping with offline tests; linguist verification required before any canonical use.
- 2026-11-24 — Replaced Gradio with FastAPI + React/Vite/shadcn web studio and dynamic catalog. Files: `pyproject.toml`, `uv.lock`, `src/zolai_tts/catalog.py`, `src/zolai_tts/server.py`, `tests/test_ui.py`, `web/`, `README.md`, `docs/architecture.md`, `context/*.md`. Impact: `zolai-tts-ui` console script + `ui` extra; FastAPI + React/Vite/shadcn studio; registry-driven dynamic catalogs with env keys header-only; localhost default; dry-run supported; no torch/CUDA/secrets/hosted service added.
- 2026-11-24 — Added `zolai-tts` menu/management CLI and UI runtime controls. Files: `pyproject.toml`, `src/zolai_tts/cli.py`, `src/zolai_tts/runtime.py`, `tests/test_cli_menu.py`, `README.md`, `docs/architecture.md`, `context/architecture.md`, `context/code-standards.md`, `context/project-overview.md`, `context/progress-tracker.md`, `CHANGELOG.md`. Impact: menu + ui start/stop/restart/status/logs/open + doctor/check/test/lint/typecheck + prepare/synth passthrough + env-only gemini-smoke; runtime state/logs outside git (`/tmp/opencode/zolai-tts-<uid>/` preferred); no secret persistence.
- 2026-11-24 — Continued dirty OpenRouter/AI SDK/model-config/media wiring implementation. Files: `src/zolai_tts/ai_sdk/*`, `src/zolai_tts/providers/openrouter.py`, `src/zolai_tts/providers/gemini.py`, `src/zolai_tts/inference/synthesize.py`, `src/zolai_tts/cli.py`, `src/zolai_tts/ui/app.py`, `tests/test_ai_sdk_config.py`, `tests/test_openrouter_provider.py`, `tests/test_gemini.py`, `tests/test_cli.py`, `tests/test_cli_menu.py`, `tests/test_ui.py`, `tests/test_providers_base.py`, `README.md`, `docs/architecture.md`, `context/architecture.md`, `context/code-standards.md`, `context/ui-context.md`, `configs/example.yaml`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`. Impact: canonical `openrouter` provider added; AI SDK config resolution (CLI > config > env > defaults) + redaction; optional capability-gated LiteLLM/PydanticAI adapters; OpenRouter smoke/menu/CLI/UI dry-run wiring; mic/upload OSS local media wiring; no secrets, no live network in tests, no unlimited-free claims.
- 2026-11-24 — Batch TTS CLI with three selectable providers (A7). Files: `src/zolai_tts/batch.py` (NEW), `src/zolai_tts/voice_lookup.py` (NEW), `src/zolai_tts/data/provenance.py` (NEW), `src/zolai_tts/cli.py` (additive `batch` subcommand), `src/zolai_tts/providers/gemini.py` (additive `build_batch_interaction_request`), `.gitignore` (+`artifacts/`), `tests/test_batch_tts.py` (NEW), `tests/test_voice_resolution.py` (NEW), `context/architecture.md`, `context/code-standards.md`, `context/progress-tracker.md`. Impact: `zolai-tts batch --input x.jsonl [--voice-key K] [--seed N] [--live] [--out-dir D] [--provider openrouter|fish-audio|gemini] [--model M]` — **dry-run default (no network, no files), `--live` opt-in**; default provider `openrouter` → `heygen/heygen-voice-1-turbo:free` (HeyGen Voice Turbo; 44.1 kHz mono PCM, 39 languages, 5,000 chars/request, 10 default voices, optional consented bring-your-own HeyGen clone key, env-only); selectable `fish-audio` → `fish-audio/s2.1-pro-free:free` (same OpenRouter SDK path + same env key `ZOLAI_TTS_OPENROUTER_API_KEY`/`OPENROUTER_API_KEY`, no-cost testing/prototyping/low-volume tier, no production latency/availability guarantees); optional `gemini` alternate (`interactions.create` v1beta `gemini-3.8-flash-tts`). Requests chunked ≤5,000 chars; raw PCM wrapped into a proper 44.1 kHz mono WAV header (RIFF/MP3 pass through, no silent corruption); manifest tracked under `manifests/` (schema_version, seed, provider, model, voice_key, legal_status, `production_guarantee=false` for free models, `tags_applied`, per-item id/text/sha256/tags/style/audio_path) while audio is gitignored under `artifacts/`; Gemini `<...>` tags + `speech_metadata.style` are Gemini-only — OpenRouter/Fish Audio keep tags/style as manifest source annotations with `tags_applied=false`. Voice resolution API-first (`/api/v1/tts/voices/{key}`), read-only SQLite fallback via `ZOLAI_DB_PATH`; unknown/inactive/missing voice_key fails loudly (no silent default voice). `owner`/`license`/`consent_ref` live in the tracked manifest only; `legal_status` stays `unverified` ⇒ publish hard-blocked. No ownership claim; no SLA claims; secrets env-only.
  - Companion zolai-core commit: `zolai/data/migrations.py` `create_tts_tables()` (`tts_voices` + `tts_generations`, IF NOT EXISTS) registered in `run_all_migrations()` dict; NEW `zolai/api/tts.py` read-only routes behind `require_role("member")` (unknown voice_key → 404, DB unreachable → 503, plain scalars, no write/publish route); `rbac.py` MEMBER_PREFIXES `+ /api/v1/tts`; `server.py` router include; `tests/test_tts_api.py` (migration idempotence + wiring, bulk_upsert audit log, RBAC anon 401/member 200, no internal enums, publish gate blocked).

## In Progress

- Framework choice remains PROPOSED pending validation against dataset size and deployment targets (source: `docs/framework-selection.md`).

## Next Up

- Acquire a consented pilot dataset and validate it against `dataset/schemas/utterance.schema.json`.
- Fine-tune a real Piper Zolai voice from an external ONNX artifact; no model is committed.
- Decide code/dataset/model licenses; the README badge and manifest both say TBD.
- Confirm bun/Vite build and FastAPI `ui` extra install in CI/maintainer environments; keep frontend deps pinned in `web/bun.lock`.

## Open Questions

- Code, dataset and model licensing remain TBD (source: README.md, `pyproject.toml`).
- Which community speaker(s) and consent records can support a pilot recording set.
- Whether hosted-provider demos are acceptable under the free-tier data terms.
- UI scope confirmation: current implementation is local research/demo only (no auth, no hosted deployment, no persistent jobs). Maintainer/product confirmation needed before expanding scope.

### OPEN gates (stay OPEN — do not trade, do not claim ownership, do not publish)

- Sentence-source owner unnamed — provenance `owner` stays `None` in the tracked manifest.
- Google TTS terms unverified — `legal_status` stays `unverified` for free-tier voices ⇒ publish hard-blocked (`verified` is the only passing status).
- Initial `voice_key` is a provisional seed (e.g. `seed-voice-1`), not a final registry name.

## Architecture Decisions

- Framework-first: Tedim rules in `frontend/`, synthesis in `providers/` (source: `docs/architecture.md`).
- No cross-repo code copy: `zolai-core` ZVS rules are cited, not imported (source: `docs/pronunciation.md`).
- Base install is offline, extra-free and keyless; optional backends are lazy (source: `src/zolai_tts`, `tests/test_gemini.py`).
- Large audio and checkpoints stay outside git; schemas are versioned (source: `docs/architecture.md`, AGENTS.md).

## Verification Evidence

- `uv run --extra dev python -m pytest`: 38 passed, 1 skipped (offline; live Gemini skipped).
- 2026-11-24 — Environment divergence, NOT a regression: bare `PYTHONPATH=src python3 -m pytest -q -rs` on this box reports 39 passed / 3 skipped (42 total, 0 failures) at current HEAD — 2 `importorskip` skips because `phonemizer` is not installed here, plus 1 opt-in live skip. Before the IPA scaffold commit the same bare command reported 36 passed / 3 skipped (39 total). `phonemizer>=3.2` is a base dependency (`pyproject.toml:28`), so the documented `uv run --extra dev` path is expected to report 38 passed / 1 skipped at the scaffold's parent commit; that result was NOT observed on this box and is not claimed here.
- `uv run --extra dev python -m ruff check src tests`: all checks passed.
- `uv run --extra dev python -m mypy src`: no issues in 19 source files (observed locally: `python3 -m mypy src`, 19 files).
- `pytest --markers` registers `live`; `pytest -m live -rs` reports one skip with no key.
- 2026-11-24 — Lightweight non-GPU setup verified on Python 3.14.7 / uv 0.10.5 (Intel HD 620, no CUDA): `uv sync --extra dev --extra gemini --extra eval` completed; 21 packages installed (incl. `google-genai`, `jiwer`, `pydantic`). A prior `uv sync ... --extra mms` was intentionally aborted on user direction (SIGTERM 143) before heavy torch/CUDA install completed; post-sync check confirmed no `torch/nvidia/cuda/triton/transformers/accelerate/datasets/pyarrow/sympy/networkx/hf-xet/tokenizers` in `.venv`. Verification: `uv run --extra dev python -m pytest -q` → 38 passed, 1 skipped; `uv run --extra dev python -m ruff check src tests` → all checks passed; `uv run --extra dev python -m mypy src` → no issues in 19 source files; `uv run zolai-tts-prepare --help`/`uv run zolai-tts-synth --help` exit 0; `uv run zolai-tts-prepare --input dataset/metadata/sample.jsonl --out-dir /tmp/opencode/zolai-tts/out --format piper` wrote 3 records; `uv run zolai-tts-synth --text "Lawm Aw Zomi" --provider piper --out /tmp/opencode/zolai-tts/out/sample.wav --dry-run` exited 0 with JSON dry-run output (no model/key/network). `uv.lock` unchanged. Piper runtime (`piper-tts`) remains marker-blocked on Python >=3.13; MMS intentionally not installed on this non-GPU laptop.
- 2026-11-24 — Web studio (FastAPI + React) added and verified (Python 3.14.7, uv 0.10.5, no CUDA/torch). `uv sync --extra dev --extra ui` succeeded; `uv.lock` updated with FastAPI/uvicorn (no torch/CUDA/nvidia packages); `web/bun.lock` pins frontend deps. `uv run --extra dev python -m pytest` → all tests pass (1 skipped live test). `uv run --extra dev python -m ruff check src tests` → passed. `uv run --extra dev python -m mypy src` → passed. `bun run --cwd web build` → passed; `bun run --cwd web lint` → no errors.
- 2026-11-24 — OpenRouter/AI SDK continuation verified (Python 3.14.x, uv). `uv run --extra dev python -m ruff check src tests` → all checks passed. `uv run --extra dev python -m mypy src` → no issues in 30 source files. `uv run --extra dev python -m pytest -q` → 82 passed, 1 skipped. Targeted: `tests/test_ai_sdk_config.py tests/test_openrouter_provider.py tests/test_gemini.py tests/test_cli.py tests/test_cli_menu.py tests/test_ui.py tests/test_providers_base.py` → 56 passed, 1 skipped. No live network/quota used; OpenRouter/Gemini smokes covered as env-only/dry-run with secret redaction.
- 2026-11-24 — Batch TTS CLI (3 providers) verified (Python 3.14.x, uv). zolai-tts: `uv run --extra dev python -m ruff check src tests` → all checks passed; `uv run --extra dev python -m mypy src` → no issues in 33 source files; `uv run --extra dev python -m pytest` → **116 passed, 1 skipped** (exit 0; includes `tests/test_batch_tts.py` + `tests/test_voice_resolution.py` — dry-run no-network/no-files, payload fidelity verbatim/tags/IPA/style, 5,000-char chunking, PCM→WAV 44.1 kHz mono header, provider/model matrix, `production_guarantee=false` warning, resolver API-success/SQLite-fallback/fail-loud). zolai-core targeted: `uv run python -m pytest tests/test_rbac_public_matrix.py tests/test_api_auth.py tests/test_api_keys_migration.py tests/test_tts_api.py -q` → **85 passed**; `mypy zolai/api/tts.py zolai/data/migrations.py` → no issues; targeted `ruff check` on the changed core files → all checks passed. No live network/quota; no secrets in tracked files; dry-run tests assert zero socket use.

## Session Notes

- Local `docs/roadmap.md` remains deprecated in favour of the workspace-root canonical roadmap (source: AGENTS.md).
- This implementation was performed directly in-session because the orchestra subagent quota was exhausted; the design gate correction was applied from the Tech Lead's verified finding.
