# Zolai TTS Studio (web)

Local React + Vite + Tailwind v4 + shadcn/ui frontend for the Zolai-TTS FastAPI server.

## Run

```bash
bun install
bun run dev        # http://127.0.0.1:5174 ; proxies /api to 127.0.0.1:7860
bun run build      # TypeScript check + production bundle in dist/
bun run lint       # oxlint
```

Set `ZOLAI_TTS_API` to point the dev proxy at a different API host.

In production, `uv run zolai-tts-ui` serves `dist/` from the FastAPI app at
`http://127.0.0.1:7860`. No Node server is needed at runtime.

## Behavior

- Provider list comes from `/api/providers` (the Python provider registry).
- Models, voices and formats come from `/api/providers/{name}/catalog`, fetched live
  from each provider using env keys (header only). Key values never reach the browser.
- Selecting a model narrows the voice/format lists to that model's capabilities;
  custom values are supported for compatible endpoints.
- Dry run is the default and produces a redacted plan. Real synthesis saves audio and
  a run record under the server's local store.
- Mic/upload files stay local with a metadata sidecar. Do not send community data
  without informed consent. Hosted providers have no native Tedim/Zolai/Zomi support.
