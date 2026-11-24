# TTS Framework Selection for Zolai-TTS

**Status:** PROPOSED — review and decide before locking in.

This project uses a **framework-first** approach: established TTS libraries provide synthesis; Tedim-specific logic stays in-repo.

## Candidate Frameworks / Providers

| Framework | License | Role | Low-Resource Fit | Notes |
|-----------|---------|------|------------------|-------|
| **[Piper](https://github.com/rhasspy/piper)** | Apache-2.0 | Real deployable Tedim/Zolai voice | **Excellent** | ONNX runtime, small footprint, fine-tunable with ~1-2 hrs audio. Adapter implemented; supply your own ONNX voice. |
| **[MMS-TTS (Meta)](https://huggingface.co/facebook/mms-tts)** | Apache-2.0 | Documented research baseline | Good | No adapter in this slice; evaluate separately. |
| **Coqui TTS / VITS** | MPL-2.0 | Research experiments | Good | Requires a **separate environment**: it hard-pins `pandas<2.0`, incompatible with this project's base install. Not an extra here. |
| **Gemini TTS (`gemini-2.5-flash-preview-tts`)** | Proprietary / hosted | Optional Zolai/Zomi demo requests | **Poor as a voice** | Key + network + `google-genai>=2.25.0` + `v1beta`. No native Tedim/Zolai/Zomi support; experimental warning emitted. Free-tier content may improve Google products; consent required. Never replaces Piper. |

## Decision Checklist

- [ ] License compatibility for code, data and checkpoints.
- [ ] Dataset feasibility (~1-2 hrs clean audio + ZVS 2018 transcriptions).
- [ ] Inference target: edge/embedded (Piper ONNX) vs server-side.
- [ ] Community review of voice quality and consent terms.
- [ ] Whether any hosted demo is acceptable under the free-tier data terms.

## Next Steps

1. Validate `dataset/schemas/` against the chosen framework's metadata format.
2. Fine-tune a Piper voice on a consented pilot dataset.
3. Compare objective metrics and a small human MOS against the MMS research baseline.
4. Keep Gemini limited to optional demos with the documented warning.

---
*This file is PROPOSED. Do not finalize without reviewing with the team and community partners.*
