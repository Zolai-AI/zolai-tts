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
| Optional hosted demos | Gemini TTS (`gemini-3.8-flash-tts`) / OpenRouter TTS (OpenAI-compatible) | Zolai/Zomi demo requests only; **experimental**, no native support |
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

# OpenRouter dry-run (no key/network; requires voice/model supported by endpoint)
uv run zolai-tts synth -- --text "Hello" --provider openrouter --voice alloy \
  --model openai/gpt-4o-mini-tts --response-format mp3 --language en \
  --out /tmp/opencode/zolai-tts/out/or.mp3 --dry-run
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
uv run zolai-tts openrouter-smoke   # env key presence only; --live is opt-in (uses quota/credits)
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
- Use **Dry run** to validate provider/language/voice/model/base-url/request planning with no key/model/network.
- Mic/Upload wiring uses OSS Gradio `Audio(sources=["microphone","upload"])` for local media; it is not persisted or uploaded by default.
- Piper real synthesis requires a local ONNX voice; `piper-tts` is unavailable on Python >=3.13, so use dry-run or an external Python <3.13 Piper environment for real Piper audio.
- Gemini/OpenRouter are optional/experimental for Tedim/Zolai/Zomi, warn on use, and read keys only from env at synthesis time. Never commit keys.

## Optional Hosted Providers / AI SDK Layer

### Gemini (optional)

```bash
# Set ZOLAI_TTS_GEMINI_API_KEY in your shell; never commit its value.
uv run --extra gemini zolai-tts-synth --text "Pasian" \
  --provider gemini --voice Kore --language zolai --model gemini-3.8-flash-tts \
  --out /tmp/opencode/zolai-tts/out/gemini.wav
```

### OpenRouter (optional, OpenAI-compatible)

```bash
# Set ZOLAI_TTS_OPENROUTER_API_KEY in your shell; never commit its value.
uv sync --extra openrouter
uv run --extra openrouter zolai-tts-synth --text "Hello" \
  --provider openrouter --voice alloy --model openai/gpt-4o-mini-tts \
  --response-format mp3 --language en \
  --out /tmp/opencode/zolai-tts/out/openrouter.mp3
```

### Optional AI SDK adapters

```bash
uv sync --extra openrouter      # OpenAI SDK / OpenAI-compatible endpoints
uv sync --extra ai-litellm      # LiteLLM adapter (capability-gated)
uv sync --extra ai-pydantic     # PydanticAI config/metadata adapter
```

- **Internal AI SDK layer:** `src/zolai_tts/ai_sdk/` resolves model/base_url/voice/format from CLI > config YAML > env > defaults and provides redaction-safe config views.
- **OpenAI-compatible layer:** uses `openai` SDK against OpenRouter or other OpenAI-compatible `/audio/speech` endpoints (`--base-url`).
- **LiteLLM/PydanticAI:** optional, lazy, capability-gated adapters for broader model/config wiring; TTS execution support depends on selected backend/model.
- **OpenCode/Ollama local wiring:** for OpenAI-compatible local endpoints, set provider `openrouter`-style base URL/model/voice via CLI or config (e.g. `--base-url http://localhost:11434/v1 --model <local-model>` where endpoint supports `/audio/speech`). Dry-run works without keys/network; live support depends on local endpoint capabilities.

- Accepted `--language` values: `ted`, `zolai`, `zomi`, `en`. **Mizo is not used.**
- Gemini/OpenRouter have **no native Tedim/Zolai/Zomi TTS support**; these requests are experimental, are not ZVS 2018 ground truth, and emit warnings. Do not ship them as the community voice — use Piper.
- Hosted provider free tiers/credits/quotas are limited and policies vary; **there is no unlimited-free path**. Gemini free-tier content may be used to improve Google products. Do not send community text or voice data without informed consent and a license decision.
- Keys are read only from environment at synthesis time (`ZOLAI_TTS_GEMINI_API_KEY`/`GEMINI_API_KEY`, `ZOLAI_TTS_OPENROUTER_API_KEY`/`OPENROUTER_API_KEY`). Imports make no network calls; dry-run makes no network calls.
- Live smoke tests are opt-in (`gemini-smoke --live`, `openrouter-smoke --live`) and use quota/credits.

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
