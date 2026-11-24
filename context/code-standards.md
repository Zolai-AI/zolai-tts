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
- Base imports must not import optional backends, read API keys or make network calls. `piper` and `google-genai` are imported lazily inside provider methods.
- Canonical provider keys are `piper` and `gemini`; do not add aliases such as `local`.
- Default tests run offline; network tests use the `live` marker and require both `ZOLAI_TTS_RUN_LIVE=1` and a key.
- `NUMBER_WORDS` is an explicit no-op stub; do not invent Tedim numerals or copy ZVS tables across repos.
- Python remains authoritative for language tooling; no NestJS or Rust service layer is added (source: AGENTS.md).

## Styling

- N/A — no UI (source: `docs/architecture.md`).

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
