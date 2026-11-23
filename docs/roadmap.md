# Zolai-TTS Roadmap

**Status:** PROPOSED

## Phase 0 — Scaffold & Decisions
- [x] Create repository structure.
- [ ] Finalize code/dataset/model license strategy.
- [ ] Confirm framework choice (Piper primary, Coqui/MMS for experiments).
- [ ] Define initial Tedim pronunciation/G2P rules from ZVS 2018 and zolai-wiki/zolai-core resources.

## Phase 1 — Dataset Foundation
- [ ] Define recording and consent guidelines.
- [ ] Create metadata schema and validation tooling.
- [ ] Collect pilot dataset: 30-60 min clean single-speaker Tedim audio + transcripts.
- [ ] Build dataset preparation script (LJSpeech/Piper format).

## Phase 2 — Baseline Model
- [ ] Run MMS-TTS baseline (no fine-tuning) for reference.
- [ ] Fine-tune Piper VITS on pilot dataset.
- [ ] Evaluate with objective metrics + small human MOS.
- [ ] Document baseline results in `research/baselines/`.

## Phase 3 — Quality & Coverage
- [ ] Expand dataset (multiple speakers, styles, domain coverage).
- [ ] Improve normalization and Tedim G2P rules.
- [ ] Add evaluation dashboard/report generation.
- [ ] Publish reproducible training recipe.

## Phase 4 — Packaging & Access
- [ ] Export deployable ONNX voice model.
- [ ] Provide simple inference CLI/API example.
- [ ] Document model card, limitations, and ethical use.
- [ ] Evaluate integration path with zolai-web/zolai-tauri.

## Decision Gates

| Gate | Question | Exit Criteria |
|------|----------|---------------|
| G1 | License | Code/data/model licenses documented |
| G2 | Data | Pilot dataset validated and consented |
| G3 | Baseline | At least one intelligible baseline model |
| G4 | Release | Reproducible recipe + model card + license |
