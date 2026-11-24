# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- PLANNED / EXPERIMENTAL — repository scaffold and research direction; not a production TTS system (source: README.md).

## Current Goal

- Define a reproducible, framework-first Tedim/Zolai TTS research pipeline and dataset guidance (source: README.md, docs/architecture.md).

## Completed

- 2026-11-24 — Replaced the six context scaffolds with committed HEAD evidence: live status, stack, boundaries, tokens and conventions are now sourced from tracked files. Files: `context/project-overview.md`, `context/architecture.md`, `context/ui-context.md`, `context/code-standards.md`, `context/ai-workflow-rules.md`, `context/progress-tracker.md`. Impact: documentation only; no application code changed.
- `docs/architecture.md` is committed with status PROPOSED, including the pipeline and component boundaries (source: docs/architecture.md).
- `docs/roadmap.md`, `docs/dataset-guidelines.md`, `docs/pronunciation.md` and `docs/framework-selection.md` are committed research docs (source: git ls-tree -r HEAD -- docs).
- Alignment pass changed no dependencies and ran no training (source: AGENTS.md).

## In Progress

- Framework choices remain PROPOSED pending validation against dataset size and deployment targets (source: README.md).

## Next Up

- No next implementation unit is documented in HEAD; UNKNOWN — source: docs/roadmap.md.

## Open Questions

- Code, dataset and model licensing are TBD (source: README.md, pyproject.toml).
- No executable pipeline exists in HEAD: `src/` is empty (source: git ls-tree -r HEAD -- src).

## Architecture Decisions

- Framework-first: implement Tedim rules in-repo and delegate synthesis to established frameworks (source: docs/architecture.md).
- Keep large audio and checkpoints outside git; version dataset schemas (source: docs/architecture.md, AGENTS.md).
- Python remains authoritative for language tooling; no NestJS or Rust service layer added (source: AGENTS.md).

## System Design Checklist

Refer to `architecture.md` > System Design & Infrastructure when adopting new
infrastructure concepts. Each row documents a decision point with service choice
and trade-offs.

## Session Notes

- Local `docs/roadmap.md` is deprecated in favour of the canonical workspace roadmap (source: AGENTS.md).
- All source paths in `architecture.md` are marked PROPOSED because `src/` is empty in HEAD.
