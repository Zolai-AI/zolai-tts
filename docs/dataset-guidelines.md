# Dataset Guidelines

**Status:** PROPOSED — must be reviewed before any recording/collection.

## Principles

- **Consent first:** Every speaker must provide informed consent for recording, storage, training, and distribution (as applicable).
- **Provenance:** Record source, speaker metadata (with privacy safeguards), date, license, and collection method.
- **Quality:** Prefer clean, single-speaker, consistent microphone/environment recordings.
- **ZVS 2018:** Transcripts use Tedim/Zolai orthography consistent with ZVS 2018.

## Audio Requirements (Pilot)

| Field | Target |
|-------|--------|
| Format | WAV, mono, 16-bit PCM |
| Sample rate | 22050 Hz (Piper common) or 44100 Hz (archive; downsample for training) |
| Duration | 3-10 seconds per utterance |
| Speaker | Single speaker per file; document speaker ID |
| Environment | Quiet room, minimal reverb/noise |
| Loudness | Normalize consistently during preprocessing; avoid clipping |

## Transcript Requirements

- UTF-8 text, Tedim/Zolai orthography.
- Include punctuation as spoken naturally.
- Normalize whitespace; avoid invisible characters.
- Keep original and normalized forms when normalization changes text.
- Flag uncertain pronunciations for review.

## Metadata Schema

See `dataset/schemas/utterance.schema.json`. Minimum fields:

- `id` - stable utterance ID
- `speaker_id` - pseudonymous speaker identifier
- `audio_path` - relative path in dataset package
- `text` - raw transcript
- `text_normalized` - normalized training text
- `language` - `ted`/`zolai` (confirm project code)
- `sample_rate` - integer Hz
- `duration_sec` - float seconds
- `source` - recording source/provenance
- `license` - dataset/license identifier
- `consent` - consent status/reference

## Splits

- Provide deterministic train/dev/test manifests.
- No speaker leakage across splits unless explicitly documented for speaker-adaptation experiments.
- Keep test set human-reviewed.

## Do Not Commit

- Raw/private recordings without release clearance.
- Personally identifying speaker information.
- Large audio blobs in git; use shared storage/HF/Kaggle/DVC/LFS as decided.
