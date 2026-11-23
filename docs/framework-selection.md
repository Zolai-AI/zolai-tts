# TTS Framework Selection for Zolai-TTS

**Status:** PROPOSED — review and decide before locking in.

This project uses a **framework-first** approach: we build on top of established TTS libraries
rather than implementing synthesis from scratch. This is critical for a low-resource language
(Tedim/Zolai) where data and engineering bandwidth are limited.

## Candidate Frameworks

| Framework | License | Maturity | Languages | Low-Resource Fit | Key Strengths | Notes |
|-----------|---------|----------|-----------|------------------|---------------|-------|
| **[Piper](https://github.com/rhasspy/piper)** | Apache-2.0 | Mature (2022+) | 70+ (via built-in) + custom | **Excellent** | ONNX runtime, fast inference, small model (~50MB), easy fine-tuning, cross-platform | Use if goal is deployable voices. Fine-tuning requires small dataset (~1-2 hrs audio). |
| **[Coqui TTS](https://github.com/idiap/coqui-ai-TTS)** | MPL-2.0 | Active | 20+ + custom | Good | Rich model zoo, VITS/GlotTTS/StyleTTS, high-quality synthesis, many configs | Heavier runtime. Good for research experiments but harder to deploy edge. |
| **[MMS-TTS (Meta)](https://huggingface.co/facebook/mms-tts)** | Apache-2.0 | Experimental | 1000+ | **Good** | Multilingual by default, multilingual fine-tuning, easy HF hub integration | Early-stage for low-resource fine-tuning. Good for baseline comparisons. |
| **[ESPnet](https://github.com/espnet/espnet)** | Apache-2.0 | Mature | 100+ | Fair | End-to-end ASR/TTS, but heavier pipeline; more ASR-focused | Consider only if ASR pipeline integration is a co-goal. |
| **[OpenSource VITS / Audio-SG](https://github.com/cocodataset/vits)** | MIT/Apache | Active | Custom | Good | VITS architecture, good quality, but needs careful data prep | Research path; less turnkey than Piper. |

## Recommended Starting Point

### **Primary choice: Piper (rhasspy/piper)**
- **Why:** Apache-2.0, production-ready ONNX runtime, small model footprint, fine-tunable with
  as little as 1-2 hours of audio, active maintenance, many language models already available.
- **Path for Tedim/Zolai:**
  1. Check if a Piper voice exists for a related language/dialect (search Piper's language list).
  2. If not, fine-tune a Piper model on the collected Tedim/Zolai dataset (target: ~2 hrs native speaker audio).
  3. Use the Piper ONNX runtime for inference; integrate with `src/zolai_tts/inference/`.
  4. For research/experiments, also test Coqui VITS and/or MMS-TTS and compare MOS/UTMOS.

### **Secondary research choice: Coqui TTS / VITS**
- Install via `pip install -e ".[coqui]"` (or `TTS` from PyPI).
- Good for comparing model architectures and training dynamics.
- Heavier runtime; use Piper as the production path unless a specific Coqui model is required.

### **Exploratory choice: MMS-TTS**
- Install via `pip install -e ".[mms]"`.
- Worth running a quick multilingual baseline to see if Meta's model already handles Tedim-like
  phonemes/tones without fine-tuning.
- Not a production path yet (API and fine-tuning stability evolving).

## Framework Decision Flow

```mermaid
flowchart TD
    A[Start: Choose TTS framework] --> B{Any Piper voice for Zolai/Tedim?}
    B -- Yes --> C[Use Piper voice + optional fine-tuning]
    B -- No --> D{Dataset ready? (<=2 hrs audio + orthography?)}
    D -- Yes --> E[Fine-tune Piper on Tedim/Zolai data]
    D -- No --> F[Gather more data / use MMS-TTS baseline]
    E --> G[Production inference via ONNX]
    F --> H[Run MMS-TTS baseline experiments]
    H --> I[Compare quality / decide on path]
```

## Decision Checklist

- [ ] **License compatibility** — Can we redistribute trained checkpoints and Piper voices?
- [ ] **Dataset feasibility** — Do we have (or can we collect) enough clean audio (~1-2 hrs) + transcriptions with Tedim orthography?
- [ ] **Inference target** — Do we need edge/embedded deployment (Piper ONNX is ideal) or server-side only?
- [ ] **Research goals** — Do we need to compare architectures (VITS vs Flow-based vs auto-regressive)? If so, include Coqui/MMS.
- [ ] **Community alignment** — Do Zolai/Tedim community partners have a preferred voice quality or style?

## Next Steps (after framework decision)

1. Update `docs/dataset-guidelines.md` for the chosen framework's data format requirements.
2. Add the corresponding dependency to `pyproject.toml` (piper / coqui / mms groups).
3. Create `configs/<framework>/` with model config templates.
4. Implement `src/zolai_tts/training/<framework>_adapter.py` as a thin wrapper around the framework's training CLI/API.
5. Implement `src/zolai_tts/inference/<framework>_adapter.py` for synthesis.

---
*This file is PROPOSED. Do not finalize without reviewing with the team and community partners.*
