# Contributing to Zolai-TTS

Thanks for helping build Tedim/Zolai speech technology.

## Ground Rules

- **Scope:** Speech synthesis, dataset tooling, evaluation, and Tedim/Zolai pronunciation/front-end work for this repo.
- **No secrets:** Never commit API keys, tokens, private credentials, or unpublished/private speaker data.
- **Data provenance:** Do not add audio, transcripts, or derived datasets without clear permission, consent, and license/provenance notes.
- **Framework-first:** Prefer adapting established libraries (Piper, Coqui, MMS/Transformers, librosa, etc.) before implementing from scratch.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Install optional backend deps only as needed:

```bash
pip install -e ".[piper]"   # Piper/ONNX path
pip install -e ".[mms]"     # MMS/Transformers path
```

## Checks

```bash
ruff check .
pytest
```

## Pull Requests

- Keep PRs focused and small.
- Add/update tests for normalization, G2P, schema validation, or data transforms.
- Document dataset/model/license assumptions.
- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

## Reporting Issues

Include: OS, Python version, installed extras, command run, expected behavior, actual behavior, and logs (redact secrets/PII).
