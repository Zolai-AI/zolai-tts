# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- IMPLEMENTED SCAFFOLD / EXPERIMENTAL — offline pipeline and CLI contracts are implemented; no trained community voice is shipped (source: README.md, `src/zolai_tts/`).

## Current Goal

- Provide a reproducible, framework-first Tedim/Zolai TTS tooling slice with versioned schemas, offline tests and an optional Zolai/Zomi Gemini demo path (source: README.md, `docs/architecture.md`).

## Completed

- 2026-11-24 — Implemented the full scaffold: `src/zolai_tts/` frontend (normalize, ZVS-attested G2P, phonemizer fallback), data validation/format writers, provider protocol and registry, Piper adapter, optional Gemini adapter, synthesis/prepare CLIs, evaluation helpers, configs, versioned JSON Schemas, placeholder fixture and six offline test modules. Corrected the G2P digraph inventory from a draft list to the ZVS-attested `th, kh, gh, ng, ch, ph, bh` (`zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md:45-55,104`).
- 2026-11-24 — Gemini adapter uses `ted`/`zolai`/`zomi`/`en` codes; Mizo is not used. Zolai-family requests emit an explicit no-native-support and free-tier/consent warning.
- 2026-11-24 — Fixed manifest resolution: removed the unsatisfiable Coqui extra (`pandas<2.0` vs base `>=2.2`); documented Coqui as a separate research environment.
- 2026-11-24 — Updated README, `docs/architecture.md`, `docs/framework-selection.md`, `docs/dataset-guidelines.md`, `docs/pronunciation.md`, `context/architecture.md`, `context/code-standards.md`, `context/project-overview.md`, this tracker, CHANGELOG, and absorbed `.ignore`.
- Prior — replaced six context scaffolds with committed HEAD evidence; aligned with canonical workspace SDLC and source-of-truth (source: git history).
- 2026-11-24 — Corrected stale HEAD-state claims in `context/ai-workflow-rules.md` (implemented `src/`, tracked `uv.lock`, committed `dataset/`/`configs/`, `docs/` status) and recorded local pytest environment divergence here. Files: `context/ai-workflow-rules.md`, `context/progress-tracker.md`. Impact: workflow rules match the implemented scaffold; no runtime behavior changed.

## In Progress

- Framework choice remains PROPOSED pending validation against dataset size and deployment targets (source: `docs/framework-selection.md`).

## Next Up

- Acquire a consented pilot dataset and validate it against `dataset/schemas/utterance.schema.json`.
- Fine-tune a real Piper Zolai voice from an external ONNX artifact; no model is committed.
- Decide code/dataset/model licenses; the README badge and manifest both say TBD.

## Open Questions

- Code, dataset and model licensing remain TBD (source: README.md, `pyproject.toml`).
- Which community speaker(s) and consent records can support a pilot recording set.
- Whether hosted-provider demos are acceptable under the free-tier data terms.

## Architecture Decisions

- Framework-first: Tedim rules in `frontend/`, synthesis in `providers/` (source: `docs/architecture.md`).
- No cross-repo code copy: `zolai-core` ZVS rules are cited, not imported (source: `docs/pronunciation.md`).
- Base install is offline, extra-free and keyless; optional backends are lazy (source: `src/zolai_tts`, `tests/test_gemini.py`).
- Large audio and checkpoints stay outside git; schemas are versioned (source: `docs/architecture.md`, AGENTS.md).

## Verification Evidence

- `uv run --extra dev python -m pytest`: 38 passed, 1 skipped (offline; live Gemini skipped).
- 2026-11-24 — Environment divergence, NOT a regression: bare `PYTHONPATH=src python3 -m pytest -q -rs` on this box reports 36 passed / 3 skipped (39 total) — 2 `importorskip` skips because `phonemizer` is not installed here, plus 1 opt-in live skip. `phonemizer>=3.2` is a base dependency (`pyproject.toml:28`), so the documented `uv run --extra dev` path is expected to report 38 passed / 1 skipped; that result was NOT observed on this box and is not claimed here.
- `uv run --extra dev python -m ruff check src tests`: all checks passed.
- `uv run --extra dev python -m mypy src`: no issues in 18 source files.
- `pytest --markers` registers `live`; `pytest -m live -rs` reports one skip with no key.

## Session Notes

- Local `docs/roadmap.md` remains deprecated in favour of the workspace-root canonical roadmap (source: AGENTS.md).
- This implementation was performed directly in-session because the orchestra subagent quota was exhausted; the design gate correction was applied from the Tech Lead's verified finding.
