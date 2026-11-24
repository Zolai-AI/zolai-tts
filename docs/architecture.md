# Zolai-TTS Architecture

**Status:** IMPLEMENTED SCAFFOLD — framework-first pipeline contract; no trained voice shipped.

## Design Principle

Implement Tedim-specific language logic (normalization, G2P, pronunciation rules) in-repo; delegate speech synthesis to established frameworks. No from-scratch model code.

## High-Level Pipeline

```text
Text (Tedim/Zolai/Zomi)
  -> Frontend normalization (ZVS 2018-safe rules + number stub)
  -> G2P / phonemization (attested digraphs + phonemizer fallback)
  -> Preprocess / schema validation -> text manifest
  -> Provider (Piper real voice | optional Gemini demo)
  -> Audio output (WAV) + evaluation report
```

## Components

| Component | Path | Responsibility | Framework/Library |
|-----------|------|----------------|-------------------|
| Frontend normalization | `src/zolai_tts/frontend/normalize.py` | NFC, whitespace, punctuation, digit boundaries, apostrophe preservation | custom rules; numbers are an explicit no-op stub |
| G2P / phonemization | `src/zolai_tts/frontend/g2p.py`, `phonemize.py` | Provisional grapheme segmentation with ZVS 2018 digraphs; phonemizer fallback | custom rules + `phonemizer` |
| Dataset preparation | `src/zolai_tts/data/` | JSON Schema validation, LJSpeech/Piper text manifests | `jsonschema`, `pyyaml` |
| Provider protocol | `src/zolai_tts/inference/base.py` | `TTSProvider`, frozen `SynthesisResult`, canonical registry (`piper`, `gemini`) | stdlib |
| Inference CLI | `src/zolai_tts/inference/synthesize.py` | Provider selection, config precedence, dry-run planning | `argparse`, `pyyaml` |
| Piper adapter | `src/zolai_tts/providers/piper.py` | Real Zolai voice through a supplied ONNX model | lazy `piper-tts` |
| Gemini adapter | `src/zolai_tts/providers/gemini.py` | Optional Zolai/Zomi demo, v1beta Interactions, consent warning | lazy `google-genai>=2.25.0` |
| Optional local UI | `src/zolai_tts/ui/app.py` | Local Gradio demo over existing synth/provider contracts; dry-run supported | lazy `gradio` (optional `ui` extra) |
| Evaluation | `src/zolai_tts/evaluation/` | Duration helper and dependency-free Markdown report | `soundfile`, stdlib |

## Boundary Rules

- Tedim-specific linguistic knowledge lives in `frontend/` and `docs/pronunciation.md`; ZVS 2018 is cited from `zolai-core` by reference, never copied.
- Framework-specific code stays in `providers/` and `configs/`. Optional local UI code lives in `ui/` and is an optional extra.
- Large audio/checkpoints stay outside git; versioned schemas live in `dataset/schemas/`.
- Base imports make no network call, read no key and import no optional backend/UI package.
- `piper` is the real Zolai voice; Gemini is optional, experimental, and never a substitute.
- The Gradio UI is a local research/demo interface only (`share=False` default, localhost bind); it is not a hosted production service.

## External Integrations

- `zolai-core`: ZVS 2018 rules (`zolai/zvs/`, `docs/ZOLAI_SYLLABLE_DESIGN.md`) and normalization references.
- `zolai-datasets`: potential source/target for curated speech metadata.
- Hugging Face / Kaggle: model and dataset hosting for large artifacts.
