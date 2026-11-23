# Tedim/Zolai Pronunciation Notes

**Status:** DRAFT — validate with language experts/community.

This document captures pronunciation and orthography rules needed by the TTS frontend.

## Ground Rules

- Follow **ZVS 2018** orthography.
- Document exceptions and dialect variation explicitly; do not silently normalize away meaningful variation.
- Prefer rule-based, explainable G2P for core Tedim patterns before ML G2P.

## Areas to Document

| Area | Notes | Status |
|------|-------|--------|
| Alphabet & digraphs | Define letter inventory, digraphs, and phoneme mapping | TODO |
| Tone/intonation | Document whether/how tone is represented in orthography or needs annotation | TODO |
| Glottal stop / punctuation | Handling of apostrophe, hyphen, and word boundaries | TODO |
| Numbers & dates | Tedim number reading rules for normalization | TODO |
| Loanwords | English/Burmese loanword pronunciation policy | TODO |
| Abbreviations | Common abbreviations and expansions | TODO |
| Case & punctuation | Normalization for TTS input | TODO |

## Implementation Mapping

- Rules documented here should be implemented in `src/zolai_tts/frontend/normalize.py` and `src/zolai_tts/frontend/g2p.py`.
- Add tests in `tests/test_normalize.py` and `tests/test_g2p.py` for every rule.

## Sources

- ZVS 2018 orthography references (add canonical citation).
- Zolai-Wiki pronunciation/grammar pages.
- Community language expert review.
