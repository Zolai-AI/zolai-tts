# Architecture Context

## Stack

Stack names come from `pyproject.toml`, `project.yaml` and `docs/architecture.md`;
no runtime or dependency versions are asserted here.

| Layer | Technology | Role | Source |
|-------|-----------|------|--------|
| Language | Python | Research tooling language | project.yaml, pyproject.toml |
| Packaging | Hatchling | Build backend | pyproject.toml |
| Package manager | uv | Declared package manager | project.yaml |
| Audio | librosa, soundfile, pydub | Resampling, trimming, feature extraction | pyproject.toml, README.md |
| Text | num2words, phonemizer | Number handling and phonemization | pyproject.toml, README.md |
| Data | pandas, jsonschema, pyyaml | Metadata validation and packaging | pyproject.toml, docs/architecture.md |
| CLI | tqdm, rich | Progress and terminal output | pyproject.toml |
| Training backends | Piper, Coqui TTS, Transformers/MMS | PROPOSED framework adapters | README.md, docs/architecture.md |
| Evaluation | UTMOS, MCD, MOS | PROPOSED objective and human evaluation | README.md, docs/architecture.md |
| Testing | pytest, ruff, mypy | Dev tooling declared in the manifest | pyproject.toml |

## System Boundaries

The `src/` tree is empty in HEAD (source: `git ls-tree -r --name-only HEAD -- src`), so
all source paths below are PROPOSED from `README.md` and `docs/architecture.md`.

- `docs/architecture.md` — committed PROPOSED pipeline and component boundaries (source: git ls-tree -r HEAD -- docs, docs/architecture.md).
- `docs/dataset-guidelines.md`, `docs/pronunciation.md`, `docs/framework-selection.md`, `docs/roadmap.md` — committed research documentation (source: git ls-tree -r HEAD -- docs).
- `src/zolai_tts/frontend/` — PROPOSED normalization and G2P with Tedim-specific rules (source: docs/architecture.md).
- `src/zolai_tts/data/` — PROPOSED dataset validation and format conversion (source: docs/architecture.md).
- `src/zolai_tts/training/`, `src/zolai_tts/inference/`, `src/zolai_tts/evaluation/` — PROPOSED framework adapters and evaluation helpers (source: docs/architecture.md).
- `configs/`, `dataset/schemas/`, `research/`, `scripts/`, `tests/` — PROPOSED layout documented in README.md, not present in HEAD (source: README.md, git ls-tree -r HEAD).

## Storage Model

- **Versioned schemas and small metadata**: PROPOSED in `dataset/schemas/` and `dataset/metadata/` (source: docs/architecture.md, README.md).
- **Large artifacts**: audio, corpora and checkpoints stay outside git in shared storage, Hugging Face or Kaggle (source: docs/architecture.md, AGENTS.md).
- **Application database**: N/A — source: pyproject.toml, git ls-tree -r HEAD.

## Auth and Access Model

- No application authentication, ownership or access-control model exists in HEAD (source: git ls-tree -r HEAD, docs/architecture.md).
- Do not commit API keys, tokens, private speaker data or unpublished recordings (source: README.md, AGENTS.md).

## System Design & Infrastructure

| Concept | Service / Tech | Notes | Source |
|---------|---------------|-------|--------|
| **Compute** | N/A — source: pyproject.toml | No service runtime in HEAD | pyproject.toml |
| **Database** | N/A — source: pyproject.toml | No database dependency | pyproject.toml |
| **Object Storage** | Shared storage / Hugging Face / Kaggle | PROPOSED home for large artifacts | docs/architecture.md |
| **CDN** | N/A — source: docs/architecture.md | No CDN decision documented | docs/architecture.md |
| **Caching** | N/A — source: docs/architecture.md | No cache layer documented | docs/architecture.md |
| **Queue / Async** | N/A — source: pyproject.toml | No queue dependency | pyproject.toml |
| **Rate Limiting** | N/A — source: docs/architecture.md | No service endpoint in HEAD | docs/architecture.md |
| **Load Balancing** | N/A — source: docs/architecture.md | No service endpoint in HEAD | docs/architecture.md |
| **Microservices** | zolai-core integration | PROPOSED source of shared linguistic resources | docs/architecture.md |
| **Observability** | Local logs or optional experiment tracking | PROPOSED in README.md | README.md |
| **Search** | N/A — source: docs/architecture.md | No search component documented | docs/architecture.md |
| **Streaming / Realtime** | N/A — source: docs/architecture.md | Batch pipeline design only | docs/architecture.md |

## Scaling & Performance Constraints

- Traffic volume: UNKNOWN — source: docs/architecture.md.
- Latency target: UNKNOWN — source: docs/architecture.md.
- Data growth estimate: UNKNOWN — source: docs/architecture.md.
- Availability target: UNKNOWN — source: docs/architecture.md.
- Budget constraint: UNKNOWN — source: docs/architecture.md.

## Invariants

1. Framework-first: Tedim-specific language logic in `frontend/`, synthesis delegated to established frameworks (source: docs/architecture.md).
2. Framework-specific code stays in adapters and `configs/`; no from-scratch model implementation (source: docs/architecture.md).
3. Large audio and checkpoints stay outside git (source: docs/architecture.md, AGENTS.md).
4. Dataset schemas are versioned in `dataset/schemas/` (source: docs/architecture.md).
5. Language ground truth is ZVS 2018 orthography; RAG/embeddings-first is the org strategy, not raw fine-tuning (source: workspace AGENTS.md as recorded in repo AGENTS.md alignment).
