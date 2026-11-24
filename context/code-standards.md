# Code Standards

## General

- Focus on Tedim speech synthesis research and tooling (source: AGENTS.md).
- Read `README.md` and `context/` files before architectural decisions (source: AGENTS.md).
- Keep datasets, models and large artifacts out of git unless explicitly tracked through the chosen artifact workflow (source: AGENTS.md).
- Keep language ground truth at ZVS 2018 orthography; this is RAG/embeddings-first research, not raw fine-tuning (source: workspace AGENTS.md recorded in repo AGENTS.md).

## TypeScript

- N/A — no TypeScript source in HEAD (source: git ls-tree -r HEAD, pyproject.toml).

## Python

- `pyproject.toml` declares the package, dependency groups, console scripts, Hatchling build backend and Ruff/pytest/mypy configuration (source: pyproject.toml).
- Ruff line length and lint selection, pytest test path and mypy settings are defined in `pyproject.toml`; follow the manifest rather than a separate config file (source: pyproject.toml).
- Install the dev extra and validate with the documented scaffold command; no build script exists in HEAD (source: README.md, pyproject.toml).
- Python remains authoritative for language tooling; no NestJS or Rust service layer is added (source: AGENTS.md).

## Styling

- N/A — no UI in HEAD (source: git ls-tree -r HEAD).

## API Routes

- N/A — no service endpoints exist in HEAD; the architecture document is PROPOSED (source: git ls-tree -r HEAD, docs/architecture.md).

## Data and Storage

- Version dataset schemas in `dataset/schemas/`; track only small metadata and examples (source: docs/architecture.md).
- Keep large audio, corpora and checkpoints in shared storage or external dataset hosts (source: docs/architecture.md, AGENTS.md).
- Never commit API keys, tokens, private speaker data or unpublished recordings (source: README.md).

## File Organization

- `docs/` — committed architecture, dataset, pronunciation, framework and roadmap notes (source: git ls-tree -r HEAD -- docs).
- `src/` — empty in HEAD; the `zolai_tts` package layout is PROPOSED (source: git ls-tree -r HEAD -- src, docs/architecture.md).
- `configs/`, `dataset/`, `research/`, `scripts/`, `tests/`, `examples/` — PROPOSED layout from README.md, not present in HEAD (source: README.md, git ls-tree -r HEAD).
- `pyproject.toml` — package metadata and tooling configuration (source: pyproject.toml).
