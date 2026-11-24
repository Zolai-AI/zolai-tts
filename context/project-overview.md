# zolai-tts

## Overview

Open-source research and development of Text-to-Speech technology for Tedim Zolai,
focusing on pronunciation, speech dataset guidelines, low-resource language synthesis
and accessible voice technology. **Status: IMPLEMENTED SCAFFOLD / EXPERIMENTAL** —
offline tooling and CLI contracts exist; no production voice is shipped. Source:
README.md, `src/zolai_tts/`.

## Goals

1. Build a reproducible Tedim/Zolai TTS research pipeline (source: README.md).
2. Create and document speech dataset guidelines for low-resource collection (source: README.md).
3. Use established TTS frameworks and libraries instead of building synthesis from scratch (source: README.md, docs/architecture.md).
4. Support accessible voice technology for the Zomi/Tedim community (source: README.md).

## Core User Flow

1. Text is normalized with ZVS 2018-safe Tedim rules (source: `src/zolai_tts/frontend/normalize.py`).
2. Grapheme segmentation uses the attested digraph inventory with a phonemizer fallback (source: `src/zolai_tts/frontend/g2p.py`, `phonemize.py`).
3. `zolai-tts-prepare` validates JSONL metadata and writes a text manifest (source: `src/zolai_tts/data/`).
4. `zolai-tts-synth` selects `piper` (real voice) or optional `gemini` (experimental Zolai/Zomi demo) and writes audio plus a result (source: `src/zolai_tts/inference/`, `providers/`).
5. Evaluation helpers report duration and render a Markdown report (source: `src/zolai_tts/evaluation/`).

## Features

- Implemented frontend, dataset, provider, inference and evaluation modules (source: `src/zolai_tts/`).
- Versioned JSON Schemas and a placeholder JSONL fixture with no audio (source: `dataset/`).
- Offline pytest suite with an opt-in `live` marker for network tests (source: `tests/`, `pyproject.toml`).
- Documented guidance on recording, consent, metadata and dataset QA (source: `docs/dataset-guidelines.md`).
- ZVS 2018 digraph reference cited from `zolai-core`, not copied (source: `docs/pronunciation.md`).

## Scope

### In Scope

- Offline research tooling, schemas, small metadata, docs and tests (source: README.md, docs/architecture.md).
- Optional local Gradio UI for synth/dry-run research demos (`ui` extra, localhost, `share=False` default) (source: `src/zolai_tts/ui/app.py`, README.md).
- Optional hosted provider for Zolai/Zomi demos with explicit warning (source: README.md, `src/zolai_tts/providers/gemini.py`).

### Out of Scope

- Production/hosted TTS service, authentication, persistent job queue, or cloud sharing by default (source: README.md, `src/zolai_tts/ui/app.py`).
- Production TTS system and trained community voice (source: README.md).
- From-scratch model implementation and training runs (source: docs/architecture.md).
- Committing audio, corpora, checkpoints, API keys or unpublished speaker data (source: docs/architecture.md, AGENTS.md).
- License decisions; code, dataset and model licensing remain TBD (source: README.md, pyproject.toml).

## Success Criteria

1. `import zolai_tts` and both console scripts work without optional extras, network or key.
2. Offline tests pass; the live Gemini test reports skipped by default.
3. Added dataset metadata validates against `dataset/schemas/utterance.schema.json`.
4. Large audio and checkpoint artifacts remain outside git.
