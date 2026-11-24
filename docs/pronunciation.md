# Tedim/Zolai Pronunciation Notes

**Status:** DRAFT — validate with language experts/community.

## Ground Rules

- Follow **ZVS 2018** orthography.
- Document exceptions and dialect variation explicitly; do not silently normalize away meaningful variation.
- Prefer rule-based, explainable G2P for core Tedim patterns before ML G2P.
- No invented phonology or number words: unattested material stays a research TODO.

## Attested Digraph Inventory

`zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md` sections 2.1, 4.3 and 4.4 (lines 45-55, 104) attest:

**`th, kh, gh, ng, ch, ph, bh`**

Examples from that source: `thla`, `kham`, `gham`, `ngai`, `chim`, `phah`, `bhal`.
`frontend/g2p.py` uses this inventory verbatim. `sh`, `hm`, `hn` are **not** attested there and are not treated as ZVS ground truth.

## Areas to Document

| Area | Notes | Status |
|------|-------|--------|
| Alphabet & digraphs | Attested inventory above; phoneme mapping pending expert review | PARTIAL |
| Tone/intonation | Document whether/how tone is represented in orthography or needs annotation | TODO |
| Glottal stop / punctuation | Apostrophe is preserved by normalization; mapping pending review | PARTIAL |
| Numbers & dates | `NUMBER_WORDS` is an explicit no-op until ZVS expert review | TODO |
| Loanwords | English/Burmese loanword pronunciation policy | TODO |
| Abbreviations | Common abbreviations and expansions | TODO |
| Case & punctuation | Normalization for TTS input implemented; pronunciation impact pending review | PARTIAL |

## Implementation Mapping

- Rules documented here are implemented in `src/zolai_tts/frontend/normalize.py` and `src/zolai_tts/frontend/g2p.py`.
- `tests/test_normalize.py` and `tests/test_g2p.py` cover the implemented rules.

## Sources

- `zolai-core/docs/ZOLAI_SYLLABLE_DESIGN.md` §2.1, §4.3, §4.4 (lines 45-55, 104) — digraph inventory.
- `zolai-core/zolai/zvs/` — ZVS 2018 validation rules (reference only; no cross-repo import).
- `zolai-core/zolai/foundation/observation/normalize.py` — normalization reference.
- Zolai-Wiki pronunciation/grammar pages and community language expert review.
