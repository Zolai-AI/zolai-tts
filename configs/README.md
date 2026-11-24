# Configuration examples

`example.yaml` is loaded with `yaml.safe_load` only; it is not schema-validated.
CLI flags override config keys, which override built-in defaults.

- `provider`: `piper` (real local Zolai voice) or `gemini` (optional hosted demo).
- `voice`: path to a real ONNX voice for Piper, or a Gemini voice name.
- `language`: `ted`, `zolai`, `zomi`, `en`.
- `text`, `out`: synthesis input and output path.

Never put an API key in this file. Use `ZOLAI_TTS_GEMINI_API_KEY` or
`GEMINI_API_KEY` in the environment instead.
