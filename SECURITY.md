# Security Policy

## Reporting

Please report security issues privately to the Zolai-AI maintainers. Do not open public issues for sensitive vulnerabilities.

## Scope

This repo may handle:
- Audio recordings and speaker metadata (potentially sensitive/personal data).
- Dataset manifests and provenance records.
- Model checkpoints and training configs.

## Rules

- Never commit secrets, tokens, private keys, or credentials.
- Never commit private/unconsented recordings.
- Treat speaker identity, voice samples, and consent records as sensitive.
- Validate and sanitize file paths and user-provided metadata in scripts/tools.
- Pin and review ML/audio dependencies before production use.
