# UI Context

## Theme

Local research web studio (not a hosted product). shadcn/ui `radix-nova` preset with
Tailwind CSS v4 and a light/dark semantic token set in `web/src/index.css` (source:
`web/src/index.css`, `web/components.json`). No custom brand assets are committed.

## Colors

Semantic shadcn tokens only (`bg-background`, `text-muted-foreground`, `bg-primary`,
`text-destructive`, etc.). The primary accent is an emerald tone shared with the Zolai
studio; do not use raw color utilities in components (source: `web/src/index.css`).

## Typography

Geist Variable via `@fontsource-variable/geist`, exposed as `--font-sans` and
`--font-heading` through `@theme inline`. No external font CDN (source: `web/src/index.css`).

## Border Radius

Token scale derived from `--radius` (`--radius-sm` … `--radius-4xl`). Use shadcn
component defaults rather than hardcoded radii (source: `web/src/index.css`).

## Component Library

React 19 + Vite + Tailwind v4 + shadcn/ui (Radix base, lucide icons). Reusable UI lives
in `web/src/components/ui/`; TTS-specific media components live in
`web/src/components/ai-elements/`. Install new components with
`bunx --bun shadcn@latest add <name>` from `web/` (source: `web/package.json`,
`web/components.json`). Follow shadcn rules: semantic tokens, `FieldGroup`/`Field` for
forms, `SelectItem` inside `SelectGroup`, `gap-*` instead of `space-y-*`, `size-*` for
square dimensions, and `data-icon` for icons in buttons.

## Layout Patterns

Single-page studio: header + status badges, a two-column synthesize/result grid, a
provider catalog table, and a capture/history section with Runs/Recordings tabs.
Provider, model, voice and format selectors are populated from `/api/providers` and
`/api/providers/{name}/catalog` and refresh live. Dry-run is the default. Audio
playback uses the shadcn media-chrome `AudioPlayer`. Localhost only by default; no
auth, no key values rendered (source: `web/src/App.tsx`, `src/zolai_tts/server.py`).

## Icons

`lucide-react` (shadcn `iconLibrary: lucide`). Use icon objects in components and
`data-icon="inline-start" | "inline-end"` inside buttons (source: `web/components.json`).

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
