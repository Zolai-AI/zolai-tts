# Zolai-TTS Architecture

**Status:** PROPOSED

## Design Principle

Build a **framework-first** Tedim/Zolai TTS pipeline. Implement Tedim-specific language logic (normalization, G2P, pronunciation rules) in-repo; delegate speech synthesis training/inference to established frameworks.

## High-Level Pipeline

```text
Text (Tedim/Zolai)
  -> Frontend normalization (custom rules + num2words)
  -> G2P / phonemization (custom Tedim rules + phonemizer fallback)
  -> TTS framework adapter (Piper/Coqui/MMS config + training)
  -> Model checkpoint / ONNX artifact
  -> Inference adapter (runtime synthesis)
  -> Audio output (WAV/OGG) + evaluation report
```

## Components

| Component | Path | Responsibility | Framework/Library |
|-----------|------|----------------|-------------------|
| Frontend normalization | `src/zolai_tts/frontend/normalize.py` | Numbers, punctuation, abbreviations, ZVS 2018 orthography cleanup | `num2words`, custom rules |
| G2P / phonemization | `src/zolai_tts/frontend/g2p.py`, `phonemize.py` | Grapheme-to-phoneme for Tedim; fallback phonemizer | `phonemizer`/eSpeak-ng, custom rules |
| Dataset preparation | `src/zolai_tts/data/` | Validate metadata, convert to LJSpeech/Piper/MMS formats, splits | `pandas`, `jsonschema`, `soundfile` |
| Training adapters | `src/zolai_tts/training/` | Wrap framework training CLIs/APIs; config generation | Piper, Coqui TTS, Transformers/MMS |
| Inference adapters | `src/zolai_tts/inference/` | Load model, synthesize text, export audio | `piper-tts`/ONNX, Coqui, Transformers |
| Evaluation | `src/zolai_tts/evaluation/` | Objective metrics and human-eval report templates | UTMOS, MCD, MOS templates |

## Boundary Rules

- **Tedim-specific linguistic knowledge** lives in `frontend/` and `docs/pronunciation.md`.
- **Framework-specific code** stays in adapter modules and `configs/`.
- **Large audio/checkpoints** stay outside git (shared storage/HF/Kaggle).
- **Dataset schemas** are versioned in `dataset/schemas/`.

## External Integrations

- `zolai-core`: shared linguistic resources, orthography rules, lexicon data.
- `zolai-datasets`: potential source/target for curated speech corpora metadata.
- Hugging Face / Kaggle: model and dataset hosting for large artifacts.
