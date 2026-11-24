# zolai-tts

## Overview

Open-source research and development of Text-to-Speech technology for Tedim Zolai,
focusing on pronunciation, speech dataset guidelines, low-resource language synthesis
and accessible voice technology. **Status: PLANNED / EXPERIMENTAL** — repository scaffold
and research direction, not a production TTS system. Source: README.md, pyproject.toml,
project.yaml.

## Goals

1. Build a reproducible Tedim/Zolai TTS research pipeline (source: README.md).
2. Create and document speech dataset guidelines for low-resource collection (source: README.md).
3. Use established TTS frameworks and libraries instead of building synthesis from scratch (source: README.md, docs/architecture.md).
4. Support accessible voice technology for the Zomi/Tedim community (source: README.md).

## Core User Flow

The research pipeline is documented, not yet implemented in HEAD:

1. Text input is normalized with Tedim-specific rules and number handling (source: docs/architecture.md).
2. Grapheme-to-phoneme conversion applies Tedim rules with a phonemizer fallback (source: docs/architecture.md).
3. A framework adapter drives Piper, Coqui or MMS training into a model checkpoint (source: docs/architecture.md).
4. An inference adapter synthesizes WAV/OGG audio and an evaluation report (source: docs/architecture.md).

## Features

### Research design

- Framework-first pipeline with in-repo Tedim language logic and delegated synthesis (source: docs/architecture.md).
- Component boundaries for frontend, data, training, inference and evaluation (source: docs/architecture.md).
- Recorded guidance on recording, consent, metadata and dataset QA (source: README.md, docs/dataset-guidelines.md).

### Artifacts and evaluation

- Versioned JSON Schemas for metadata and utterances in the proposed `dataset/` layout (source: docs/architecture.md, README.md).
- Objective and human-evaluation templates with UTMOS, MCD and MOS (source: docs/architecture.md).
- Framework evaluation criteria in `docs/framework-selection.md` (source: README.md).

## Scope

### In Scope

- Research documentation, dataset guidelines, pronunciation notes and proposed component boundaries (source: README.md, docs/architecture.md).
- Small tracked metadata and schemas; large artifacts stay outside git (source: docs/architecture.md, AGENTS.md).

### Out of Scope

- A production TTS system; the README states the repo is PLANNED / EXPERIMENTAL (source: README.md).
- From-scratch model implementation; only adapters and configuration around frameworks are planned (source: docs/architecture.md).
- Committing audio, corpora, checkpoints, API keys, tokens or unpublished speaker data (source: docs/architecture.md, README.md, AGENTS.md).
- License decisions; code, dataset and model licensing are recorded as TBD in HEAD (source: README.md, pyproject.toml).

## Success Criteria

1. Executable pipeline success criteria are UNKNOWN — source: git ls-tree -r HEAD (the `src/` tree is empty).
2. Any added dataset metadata validates against the versioned schemas described in `docs/architecture.md`.
3. Large audio and checkpoint artifacts remain outside git (source: docs/architecture.md, AGENTS.md).
