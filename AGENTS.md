# AGENTS.md — Zolai TTS

Open-source research and development of Text-to-Speech (TTS) technology for **Tedim Zolai**.
Part of the `zolai-ai` community org. This is a separate git repo (ignored by the workspace root);
scope all reads to this repo.

## Working rules

- Focus on high-quality Tedim speech synthesis research and tooling.
- Keep datasets, models, and large artifacts out of git unless explicitly tracked via the repo's chosen artifact workflow.
- Read `README.md` and `context/` files before making architectural decisions.

## Application Building Context

Read the following files in order before implementing
or making any architectural decision:

0. `project.yaml` — project identity, version, lifecycle
   stage, team, and stack definition
1. `context/project-setup.md` — onboarding guide, version/lifecycle
   management, and daily workflow
2. `context/project-overview.md` — product definition,
   goals, features, and scope
3. `context/architecture.md` — system structure,
   boundaries, storage model, system design &
   infrastructure, and invariants
4. `context/ui-context.md` — theme, colors, typography,
   component conventions, and UI skill usage
5. `context/code-standards.md` — implementation rules
   and conventions
6. `context/ai-workflow-rules.md` — development workflow,
   scoping rules, and delivery approach
7. `context/progress-tracker.md` — current phase,
   completed work, open questions, and next steps
8. `context/specs/README.md` — optional unit specs (one file per
   feature)

### Repo type (fill in one)

- [ ] **Single repo** — all source in this directory. Scope all
      reads and globs to this root. Use project-relative paths
      (`AGENTS.md`, `context/*.md`), not `**/AGENTS.md`.
- [ ] **Monorepo** — this root contains multiple subprojects.
      Work in ONE subproject at a time. Do NOT glob `**/` from
      this root — it scans thousands of files across subprojects.
      Read the subproject's own `AGENTS.md` and `context/` instead.

### Performance scoping (both types)

- `.ignore` / `.cursorignore` / `.gitignore` at this root exclude
  `node_modules/`, `vendor/`, `venv/`, caches, and build artifacts.
  Respect them — do not use `--no-ignore` from this root.
- Use `rg` (respects `.ignore`) for search, not bare `find` or `grep -r`.
- Read only the files you need for the current task — do not
  dump-read entire directories.
- Generate or refresh scoping files:
  `bash pcore-orchestra/scripts/setup-repo-scoping.sh .`

### UI skills (when building product UI)

Prefer installed skills `ui-ux-pro-max`, `brand`, `design-system`,
and `ui-styling` for design guidance. Persist tokens and conventions
into `context/ui-context.md` (see Skills section there). Complements
`web-design-guidelines` / `shadcn` Agent Skills.

Update `context/progress-tracker.md` after each
meaningful implementation change.
Update `project.yaml` lifecycle stage and version when
the project advances through SDLC phases.

If implementation changes the architecture, scope, or
standards documented in the context files, update the
relevant file before continuing.

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
