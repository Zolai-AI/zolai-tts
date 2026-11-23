# Zolai-TTS

Open-source research and development of Text-to-Speech (TTS) technology for **Tedim Zolai**, focusing on pronunciation, speech datasets, low-resource language synthesis, and accessible voice technology.

> Status: **PLANNED / EXPERIMENTAL** — repository scaffold and research direction. Not a production TTS system yet.

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

This project intentionally builds on existing TTS frameworks and libraries. Tedim/Zolai is low-resource; the fastest path to usable results is to adapt proven systems.

| Area | Primary library/framework | Role |
|------|---------------------------|------|
| TTS training | [Piper](https://github.com/rhasspy/piper) (VITS-based) | Lightweight, deployable ONNX voices; good low-resource fine-tuning path |
| TTS experimentation | [Coqui TTS](https://github.com/idiap/coqui-ai-TTS) / VITS | Research experiments, model comparison |
| Low-resource bootstrapping | [Meta MMS-TTS](https://huggingface.co/facebook/mms-tts) / Transformers | Multilingual baseline and fine-tuning experiments |
| Audio processing | [librosa](https://librosa.org/), [soundfile](https://pysoundfile.readthedocs.io/), [pydub](https://github.com/jiaaro/pydub) | Resampling, trimming, feature extraction |
| Text normalization | [num2words](https://github.com/savoirfairelinux/num2words) + custom Tedim rules | Numbers, abbreviations, punctuation, orthography normalization |
| G2P / phonemization | [phonemizer](https://github.com/bootphon/phonemizer) + custom Tedim G2P rules | Grapheme-to-phoneme; eSpeak-ng backend where useful, Tedim-specific rules as ground truth |
| Dataset format/validation | [datasets](https://huggingface.co/docs/datasets/), [pandas](https://pandas.pydata.org/), JSON Schema | Metadata validation, dataset packaging |
| Evaluation | [UTMOS](https://github.com/sarulab-speech/UTMOS22) / MCD / subjective MOS | Objective and human evaluation |
| Experiment tracking | [Weights & Biases](https://wandb.ai/) or local logs | Optional training/eval tracking |

> Framework choices are **PROPOSED** and should be validated against dataset size, licensing, and deployment targets before locking in.

## Project Structure

```text
zolai-tts/
├── README.md
├── LICENSE                     # TBD after code/model/dataset license review
├── CONTRIBUTING.md
├── SECURITY.md
├── .gitignore
├── pyproject.toml              # Python package + dependency groups
├── configs/
│   ├── piper/                  # Piper training/inference configs
│   ├── coqui/                  # Coqui/VITS experiment configs
│   └── mms/                    # MMS fine-tuning configs
├── docs/
│   ├── architecture.md         # Pipeline and component boundaries
│   ├── roadmap.md              # Milestones and decision gates
│   ├── dataset-guidelines.md   # Recording, consent, metadata, QA
│   ├── pronunciation.md        # Tedim/Zolai orthography and phonology notes
│   └── framework-selection.md  # Framework evaluation criteria
├── dataset/
│   ├── README.md
│   ├── schemas/                # JSON Schema for metadata/utterances
│   │   ├── metadata.schema.json
│   │   └── utterance.schema.json
│   ├── metadata/               # Small tracked metadata/examples only
│   └── splits/                 # Train/dev/test manifests (no large audio)
├── research/
│   ├── README.md
│   ├── baselines/              # Baseline experiment notes
│   └── papers/                 # Paper summaries / references
├── src/
│   └── zolai_tts/
│       ├── __init__.py
│       ├── frontend/           # Text normalization + G2P adapters
│       │   ├── __init__.py
│       │   ├── normalize.py
│       │   ├── g2p.py
│       │   └── phonemize.py
│       ├── data/               # Dataset prep, validation, format conversion
│       │   ├── __init__.py
│       │   ├── preprocess.py
│       │   ├── validate.py
│       │   └── formats.py
│       ├── training/           # Framework adapters/config wrappers
│       │   ├── __init__.py
│       │   ├── piper_adapter.py
│       │   └── mms_adapter.py
│       ├── inference/          # Runtime synthesis adapters
│       │   ├── __init__.py
│       │   └── synthesize.py
│       └── evaluation/         # Objective/subjective evaluation helpers
│           ├── __init__.py
│           ├── objective.py
│           └── report.py
├── scripts/
│   ├── prepare_dataset.py
│   ├── train_piper.sh
│   └── synthesize.py
├── tests/
│   ├── test_normalize.py
│   ├── test_g2p.py
│   └── test_dataset_schema.py
└── examples/
    ├── README.md
    └── sample_utterances.jsonl
```

## Design Notes

- **`src/zolai_tts/frontend/`** keeps Tedim-specific language rules (normalization, G2P) close to the codebase, while calling external libraries where appropriate.
- **`src/zolai_tts/training/`** contains adapters/configuration around frameworks, not a from-scratch TTS model implementation.
- **`configs/`** separates experiment/training configuration from Python code.
- **`dataset/`** tracks schemas and small metadata only. Large audio/corpora belong in shared data storage or external dataset releases, not git.
- **`research/`** captures experiments, baselines, and paper notes before they become stable pipeline code.

## Quick Start (Scaffold)

```bash
# Python 3.11+ recommended
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Validate dataset metadata (example)
python scripts/prepare_dataset.py --help
```

## Data and Licensing

- **Code license:** TBD — decide after reviewing dependencies (Piper/MIT, Coqui/MPL-2.0, Transformers/Apache-2.0, etc.) and intended distribution.
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
