# UI Context

## Theme

Lightweight local research/demo UI. Minimal, no custom brand assets; default Gradio theme (source: `src/zolai_tts/ui/app.py`).

## Colors

Default Gradio/system palette. No custom brand colors committed (source: `src/zolai_tts/ui/app.py`).

## Typography

System/default Gradio fonts. No custom font assets (source: `src/zolai_tts/ui/app.py`).

## Border Radius

Default Gradio component radius (source: `src/zolai_tts/ui/app.py`).

## Component Library

Gradio Blocks (optional `ui` extra, `gradio>=6.32,<7`) for a local-only synth/dry-run form (source: `pyproject.toml`, `src/zolai_tts/ui/app.py`). Includes optional OSS mic/upload `Audio` wiring for local media (not persisted/uploaded by default).

## Layout Patterns

Single-page form: text input, provider/language selectors, voice/model/base-url/response-format fields, output path, optional mic/upload audio input (OSS/local), dry-run checkbox, run button, JSON result, audio output. Localhost bind, `share=False` by default; no auth, no persistent queue (source: `src/zolai_tts/ui/app.py`).

## Icons

No custom icon set; Gradio defaults only (source: `src/zolai_tts/ui/app.py`).

## Skills (UI / UX)

Use these installed skills when designing or implementing UI. They complement
`web-design-guidelines` and `shadcn` (Agent Skills) — do not replace them.

| Skill | When to use |
| ----- | ----------- |
| `ui-ux-pro-max` | Product/page UI reasoning, stack-aware patterns, UX guidelines; optional `search.py` (Python 3) for CSV design data |
| `brand` | Logo, voice, color/type identity, brand guideline sync |
| `design-system` | Tokens, component specs, Tailwind integration; hierarchical pages via `design-system/MASTER.md` when needed |
| `ui-styling` | Tailwind/shadcn theming, responsive utilities, canvas fonts |
| `web-design-master` | Page/section/layout design, color systems, typography scale, accessibility, design QA review |

**Persist → this file:** When a skill (or `--persist` / design-system output) produces tokens,
colors, typography, or component conventions, write the durable choices into
`context/ui-context.md` (project source of truth). Keep long hierarchical design
docs in `design-system/` only when the project needs multi-page token trees.
