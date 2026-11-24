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
- 2026-11-24 — Added an UNKNOWN-by-default IPA research scaffold for the seven ZVS-attested digraphs; no IPA values asserted and G2P/phonemizer left unchanged. Files: `src/zolai_tts/frontend/ipa_research.py`, `tests/test_ipa_research.py`, `context/progress-tracker.md`. Impact: research-only placeholder mapping with offline tests; linguist verification required before any canonical use.
- 2026-11-24 — Added optional local Gradio UI over existing provider contracts. Files: `pyproject.toml`, `uv.lock`, `src/zolai_tts/ui/__init__.py`, `src/zolai_tts/ui/app.py`, `tests/test_ui.py`, `README.md`, `docs/architecture.md`, `context/architecture.md`, `context/ui-context.md`, `context/project-overview.md`, `context/code-standards.md`, `context/progress-tracker.md`. Impact: `zolai-tts-ui` console script + `ui` extra; lazy Gradio import; localhost/`share=False` default; dry-run supported; no torch/CUDA/secrets/hosted service added.

## In Progress

- Framework choice remains PROPOSED pending validation against dataset size and deployment targets (source: `docs/framework-selection.md`).

## Next Up

- Acquire a consented pilot dataset and validate it against `dataset/schemas/utterance.schema.json`.
- Fine-tune a real Piper Zolai voice from an external ONNX artifact; no model is committed.
- Decide code/dataset/model licenses; the README badge and manifest both say TBD.
- Confirm Gradio 6.32.x py3.14 wheel/runtime compatibility in CI/maintainer environments; pin a compatible 5.x/6.x if regressions appear.

## Open Questions

- Code, dataset and model licensing remain TBD (source: README.md, `pyproject.toml`).
- Which community speaker(s) and consent records can support a pilot recording set.
- Whether hosted-provider demos are acceptable under the free-tier data terms.
- UI scope confirmation: current implementation is local research/demo only (no auth, no hosted deployment, no persistent jobs). Maintainer/product confirmation needed before expanding scope.

## Architecture Decisions

- Framework-first: Tedim rules in `frontend/`, synthesis in `providers/` (source: `docs/architecture.md`).
- No cross-repo code copy: `zolai-core` ZVS rules are cited, not imported (source: `docs/pronunciation.md`).
- Base install is offline, extra-free and keyless; optional backends are lazy (source: `src/zolai_tts`, `tests/test_gemini.py`).
- Large audio and checkpoints stay outside git; schemas are versioned (source: `docs/architecture.md`, AGENTS.md).

## Verification Evidence

- `uv run --extra dev python -m pytest`: 38 passed, 1 skipped (offline; live Gemini skipped).
- 2026-11-24 — Environment divergence, NOT a regression: bare `PYTHONPATH=src python3 -m pytest -q -rs` on this box reports 39 passed / 3 skipped (42 total, 0 failures) at current HEAD — 2 `importorskip` skips because `phonemizer` is not installed here, plus 1 opt-in live skip. Before the IPA scaffold commit the same bare command reported 36 passed / 3 skipped (39 total). `phonemizer>=3.2` is a base dependency (`pyproject.toml:28`), so the documented `uv run --extra dev` path is expected to report 38 passed / 1 skipped at the scaffold's parent commit; that result was NOT observed on this box and is not claimed here.
- `uv run --extra dev python -m ruff check src tests`: all checks passed.
- `uv run --extra dev python -m mypy src`: no issues in 19 source files (observed locally: `python3 -m mypy src`, 19 files).
- `pytest --markers` registers `live`; `pytest -m live -rs` reports one skip with no key.
- 2026-11-24 — Lightweight non-GPU setup verified on Python 3.14.7 / uv 0.10.5 (Intel HD 620, no CUDA): `uv sync --extra dev --extra gemini --extra eval` completed; 21 packages installed (incl. `google-genai`, `jiwer`, `pydantic`). A prior `uv sync ... --extra mms` was intentionally aborted on user direction (SIGTERM 143) before heavy torch/CUDA install completed; post-sync check confirmed no `torch/nvidia/cuda/triton/transformers/accelerate/datasets/pyarrow/sympy/networkx/hf-xet/tokenizers` in `.venv`. Verification: `uv run --extra dev python -m pytest -q` → 38 passed, 1 skipped; `uv run --extra dev python -m ruff check src tests` → all checks passed; `uv run --extra dev python -m mypy src` → no issues in 19 source files; `uv run zolai-tts-prepare --help`/`uv run zolai-tts-synth --help` exit 0; `uv run zolai-tts-prepare --input dataset/metadata/sample.jsonl --out-dir /tmp/opencode/zolai-tts/out --format piper` wrote 3 records; `uv run zolai-tts-synth --text "Lawm Aw Zomi" --provider piper --out /tmp/opencode/zolai-tts/out/sample.wav --dry-run` exited 0 with JSON dry-run output (no model/key/network). `uv.lock` unchanged. Piper runtime (`piper-tts`) remains marker-blocked on Python >=3.13; MMS intentionally not installed on this non-GPU laptop.
- 2026-11-24 — Optional Gradio UI added and verified (Python 3.14.7, uv 0.10.5, no CUDA/torch). `uv sync --extra dev --extra ui` succeeded; `uv.lock` updated with Gradio 6.32.0 and transitive deps (no torch/CUDA/nvidia packages). `uv run --extra ui zolai-tts-ui --help` exit 0. `uv run --extra ui python -c "from zolai_tts.ui.app import build_app; build_app()"` exit 0. `uv run --extra dev python -m pytest` → 48 passed, 1 skipped (includes 7 UI tests in this env; `tests/test_ui.py` uses `pytest.importorskip("gradio")` so it skips cleanly when gradio absent). `uv run --extra dev python -m ruff check src tests` → all checks passed. `uv run --extra dev python -m mypy src` → no issues in 21 source files. `uv run --extra dev --extra ui python -c "from zolai_tts.ui.app import synthesize_ui; print(synthesize_ui('Pasian','piper','zolai','/tmp/no.onnx','',True)[0]['ok']); print(synthesize_ui('Pasian','gemini','zomi','Kore','',True)[0]['result']['request']['model'])"` → `True`, `gemini-3.8-flash-tts`.

## Session Notes

- Local `docs/roadmap.md` remains deprecated in favour of the workspace-root canonical roadmap (source: AGENTS.md).
- This implementation was performed directly in-session because the orchestra subagent quota was exhausted; the design gate correction was applied from the Tech Lead's verified finding.
