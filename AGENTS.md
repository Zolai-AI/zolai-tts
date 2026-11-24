# AGENTS.md — Zolai TTS

Open-source research and development of Text-to-Speech (TTS) technology for **Tedim Zolai**.
Part of the `zolai-ai` community org. This is a separate git repo (ignored by the workspace root);
scope all reads to this repo.

## Working rules

- Focus on high-quality Tedim speech synthesis research and tooling.
- Keep datasets, models, and large artifacts out of git unless explicitly tracked via the repo's chosen artifact workflow.
- Read `README.md` and `context/` files before making architectural decisions.

## Application Building Context

Read the following files in order before implementing or making any architectural decision:

0. `project.yaml` — project identity, version, lifecycle stage, team, and stack definition
1. `context/project-setup.md` — scope, stack, structure, environments
2. `context/ui-ux.md` — design system and component standards
3. `context/code-standards.md` — coding conventions and quality rules
4. `context/workflow.md` — git, CI/CD, deployment, definition of done
5. `context/agent-role.md` — how the AI agent should behave in this project
6. `context/anti-patterns.md` — what to avoid

If any of these files is missing, incomplete, or outdated relative to the current state of the project, flag it before implementing. If implementation changes the architecture, scope, or standards documented in the context files, update the relevant file before continuing.

## Secret Hygiene (repo-specific)

- Canonical rules: workspace-root `AGENTS.md` § Secret Hygiene. Full procedure: `../context/code-standards.md` § Secret Hygiene — Prevention. Staged-change scan gate: `secret-scan` subagent; checklist: `secret-hygiene` skill. Do not duplicate that block here.

## Workspace alignment (2026-11-24)

`zolai-tts` is Python TTS research and tooling (separate git repo, ignored by the
workspace root). It follows the workspace-canonical 7-stage SDLC and document map.

### ALIGNMENT RECORD — zolai-tts

- Canonical SDLC: [`../docs/SDLC.md`](../docs/SDLC.md)
- Canonical source-of-truth: [`../docs/governance/source-of-truth.md`](../docs/governance/source-of-truth.md)
- Status: aligned 2026-11-24; local `docs/roadmap.md` is deprecated in favour of the canonical workspace roadmap.

### BACKEND/CORE ALIGNMENT RECORD — zolai-tts

- Python remains authoritative for language tooling; `no @nestjs dependency found — do not add`.
- Rust/Cargo: Cargo is Tauri native layer only (`../zolai-tauri/src-tauri/Cargo.toml`); no Rust service layer added.
- This alignment pass changed no dependencies and ran no training.
