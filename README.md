# Zolai-TTS
![License: TBD](https://img.shields.io/badge/License-TBD-lightgrey.svg)
![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-blue.svg)

Open-source research and development of Text-to-Speech (TTS) technology for **Tedim Zolai**, focusing on pronunciation, speech datasets, low-resource language synthesis, and accessible voice technology.

> Status: **IMPLEMENTED SCAFFOLD / EXPERIMENTAL** — offline tooling and CLI contracts are implemented; no trained community voice or production model is shipped yet.

## Goals

- Build a reproducible Tedim/Zolai TTS research pipeline.
- Create and document speech dataset guidelines for low-resource language collection.
- Use established TTS frameworks/libraries where possible instead of building synthesis from scratch.
- Support accessible voice technology for the Zomi/Tedim community.

## Repository Boundaries

| Repo | Responsibility |
|------|----------------|
| `zolai-core` | Shared language resources and linguistic infrastructure |
| `zolai-tts` | Speech synthesis, audio datasets, and voice models |
| Future `zolai-asr` | Automatic speech recognition, if needed |

## Framework-First Approach

| Area | Primary library/framework | Role |
|------|---------------------------|------|
| TTS training | [Piper](https://github.com/rhasspy/piper) (VITS-based) | Lightweight, deployable ONNX voices; real Tedim/Zolai voice path |
| TTS experimentation | Coqui TTS / VITS | Research experiments in a **separate environment** (pins `pandas<2.0`) |
| Low-resource bootstrapping | [Meta MMS-TTS](https://huggingface.co/facebook/mms-tts) | Documented research path; no adapter in this slice |
| Optional hosted demos | Gemini TTS (`gemini-3.8-flash-tts`) | Zolai/Zomi demo requests only; **experimental**, no native support |
| Audio processing | librosa, soundfile, pydub | Resampling, trimming, feature extraction |
| Text normalization | num2words + custom Tedim rules | Numbers, abbreviations, punctuation, orthography normalization |
| G2P / phonemization | phonemizer + rule-based fallback | Provisional grapheme segmentation; ZVS 2018 digraph inventory |
| Dataset format/validation | pandas, jsonschema | Metadata validation, dataset packaging |
| Evaluation | UTMOS / MCD / MOS | Objective and human evaluation (report templates implemented) |

Framework choices remain **PROPOSED** until validated against dataset size, licensing and deployment targets.

## Project Structure

```text
zolai-tts/
├── pyproject.toml              # Package, dependency groups, console scripts, tooling
├── configs/
│   ├── example.yaml            # Safe-loaded example config (no keys/models)
│   └── README.md
├── dataset/
│   ├── schemas/                # Versioned JSON Schemas (utterance, metadata)
│   └── metadata/sample.jsonl   # 3 placeholder records; no audio committed
├── docs/                       # Architecture, framework choice, dataset, pronunciation
├── src/zolai_tts/
│   ├── frontend/               # normalize.py, g2p.py, phonemize.py
│   ├── data/                   # preprocess.py, validate.py, formats.py
│   ├── inference/              # base.py (protocol/registry), synthesize.py (CLI)
│   ├── providers/              # piper.py (real voice), gemini.py (optional demo)
│   ├── ui/                     # optional local Gradio UI (lazy import)
│   └── evaluation/             # objective.py, report.py
├── tests/                      # Offline pytest suite + opt-in live marker
└── research/                   # Baselines and paper notes
```

## Quick Start

```bash
uv sync --extra dev
uv run --extra dev python -m pytest            # offline; live Gemini test skipped
uv run --extra dev python -m ruff check src tests
uv run --extra dev python -m mypy src

uv run zolai-tts --help
uv run zolai-tts doctor
uv run zolai-tts-prepare --help
uv run zolai-tts-synth --help

mkdir -p /tmp/opencode/zolai-tts/out
uv run zolai-tts prepare -- --input dataset/metadata/sample.jsonl \
  --schema dataset/schemas/utterance.schema.json \
  --out-dir /tmp/opencode/zolai-tts/out --format piper
uv run zolai-tts synth -- --text "Pasian in leitung a piangsak hi." \
  --provider piper --voice /replace/with/real/zolai-voice.onnx \
  --language zolai --out /tmp/opencode/zolai-tts/out/synth.wav --dry-run
```

`--dry-run` writes no audio and needs no key or backend. Real synthesis requires a
real ONNX voice supplied via `--voice`; none is committed.

## Menu CLI & Local UI Management

```bash
uv run zolai-tts --help
uv run zolai-tts menu
uv run zolai-tts doctor
uv run zolai-tts ui start --host 127.0.0.1 --port 7860
uv run zolai-tts ui status
uv run zolai-tts ui logs --lines 40
uv run zolai-tts ui open            # prints URL; add --launch to use xdg-open
uv run zolai-tts ui stop
uv run zolai-tts ui restart
uv run zolai-tts check              # ruff + mypy + pytest
uv run zolai-tts gemini-smoke       # env key presence only; --live is opt-in
```

- The CLI orchestrates existing modules; it does not duplicate synthesis logic.
- UI lifecycle state/logs are stored outside git in `/tmp/opencode/zolai-tts-<uid>/` (fallback: XDG runtime/cache dir). State files contain PID/host/port/cmd metadata only — **no API keys or secrets**.
- `doctor` and `gemini-smoke` report env key presence only; they never print or persist secret values. `gemini-smoke --live` is opt-in and uses quota.
- `ui start` runs `python -m zolai_tts.ui.app` in background and validates PID/cmdline on status.

## Optional Local UI (Gradio)

```bash
uv sync --extra dev --extra ui
uv run --extra ui zolai-tts-ui --help
uv run --extra ui zolai-tts-ui  # foreground, local only, share=False by default
```

- The UI is a lightweight local research/demo surface; it is not a hosted production service.
- Gradio is an optional dependency (`ui` extra) and is imported lazily — base installs/imports do not require it.
- Use **Dry run** to validate provider/language/voice/request planning with no key/model/network.
- Piper real synthesis requires a local ONNX voice; `piper-tts` is unavailable on Python >=3.13, so use dry-run or an external Python <3.13 Piper environment for real Piper audio.
- Gemini is optional/experimental for Tedim/Zolai/Zomi, warns on use, and reads keys only from env at synthesis time. Never commit keys.

## Optional Gemini Provider

```bash
# Set ZOLAI_TTS_GEMINI_API_KEY in your shell; never commit its value.
uv run --extra gemini zolai-tts-synth --text "Pasian" \
  --provider gemini --voice Kore --language zolai \
  --out /tmp/opencode/zolai-tts/out/gemini.wav
```

- Accepted `--language` values: `ted`, `zolai`, `zomi`, `en`. **Mizo is not used.**
- Gemini has **no native Tedim/Zolai/Zomi TTS support**; these requests are experimental, are not ZVS 2018 ground truth, and emit a warning. Do not ship them as the community voice — use Piper.
- Free-tier content **may be used to improve Google products**. Do not send community text or voice data without informed consent and a license decision.
- Requires `google-genai>=2.25.0` and the `v1beta` Interactions API. Keys are read only at synthesis time; imports make no network calls.
- The live smoke test is opt-in: `ZOLAI_TTS_RUN_LIVE=1` plus a key. By default it reports `SKIPPED`.

## Data and Licensing

- **Code license:** TBD — decide after reviewing dependency licenses and intended distribution.
- **Dataset license:** TBD per dataset/source. Do not commit audio or text without clear permission and provenance.
- **Model license:** TBD per trained checkpoint; document upstream base model/data licenses.

See [docs/dataset-guidelines.md](docs/dataset-guidelines.md).

## Security

See [SECURITY.md](SECURITY.md). Do not commit API keys, tokens, private speaker data, or unpublished recordings.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Related Zolai Projects

- [zolai-core](https://github.com/Zolai-AI/zolai-core) — language resources and linguistic infrastructure
- [zolai-datasets](https://github.com/Zolai-AI/zolai-datasets) — bilingual corpora and datasets
- [zolai-training](https://github.com/Zolai-AI/zolai-training) — LoRA/QLoRA fine-tuning
- [zolai-wiki](https://github.com/Zolai-AI/zolai-wiki) — grammar, vocabulary, curriculum knowledge base
