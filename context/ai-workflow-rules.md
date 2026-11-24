# AI Workflow Rules

## Approach

Read `project.yaml`, then the context files in the order recorded in
AGENTS.md, then the committed research docs before any architectural decision. Build
the research direction incrementally and spec-first: `project-overview.md` defines goals,
`architecture.md` records PROPOSED boundaries, `ui-context.md` records that there is no
UI in HEAD, `code-standards.md` defines Python conventions, and `progress-tracker.md`
records state. Do not present PROPOSED source paths as implemented. Source: AGENTS.md,
docs/architecture.md, git ls-tree -r HEAD.

## Scoping Rules

- Work on one feature unit at a time
- Prefer small, verifiable increments over large
  speculative changes
- Do not combine unrelated system boundaries in a
  single implementation step

## Performance Scoping (Monorepo)

- Use `rg` (respects `.ignore`) for search — not bare `find` or `grep -r`.
- Read only the files needed for the current task — do not dump-read directories.
- Cap tool output: `tool_output.max_lines=300, max_bytes=12288` (set via orchestra token profile).
- For monorepos: open the subproject directory, not the root, when possible.
- **Monorepo `opencode.json` `instructions` scoping**: `NARROW_INSTRUCTIONS` uses `**/AGENTS.md` etc. which match every subproject. In large monorepos, this can still inflate tokens. Best practice: scope `instructions` per subproject (e.g., `subproject1/AGENTS.md`, `subproject2/AGENTS.md`) in each subproject's `opencode.json` rather than relying on root-level globs. The `BROAD_INSTRUCTION_GLOBS` denylist (`**/**`, `**/templates/**`, `**/context/**`) is enforced by `filterBroadInstructions()` to strip known token-inflating patterns. Watcher ignores and tool output caps already bound memory/CPU.

## When to Split Work

Split an implementation step if it combines:

- Tedim normalization/G2P rules versus framework adapter configuration (source: docs/architecture.md).
- Dataset schema and metadata changes versus pipeline code (source: docs/architecture.md).
- Behaviour not defined in HEAD README.md or `docs/architecture.md` (source: README.md, docs/architecture.md).

If a change cannot be verified end to end quickly,
the scope is too broad — split it.

## System Design Triggers

When starting a new feature, check whether it triggers
any of these system design concerns. If yes, define the
approach in `architecture.md` > System Design before
implementing:

| Trigger | Consider |
|---------|----------|
| File uploads / media | Object storage + CDN + signed URLs |
| Background / deferred work | Queue, worker, retry policy |
| Expensive or repeated query | Caching layer (CDN, Redis, in-memory) |
| Global user base | CDN, multi-region, load balancing |
| Bursty traffic / abuse risk | Rate limiting, throttling, WAF |
| Independent deploy cycles | Microservice boundary, contract testing |
| Debugging production issues | Observability: logs, metrics, traces |
| Search / discovery feature | Dedicated search index vs DB query |
| Realtime UI updates | WebSocket, SSE, polling, Durable Objects |
| Data growth beyond 1M rows | Connection pooling, read replicas, sharding |

## Handling Missing Requirements

- Do not invent product behavior not defined in the
  context files
- If a requirement is ambiguous, resolve it in the
  relevant context file before implementing
- If a requirement is missing, add it as an open question
  in `progress-tracker.md` before continuing

## Protected Files

Do not modify the following unless explicitly instructed:

- `dataset/` artifacts — schemas are versioned, but large audio, corpora and checkpoints stay outside git (source: docs/architecture.md, AGENTS.md).
- `docs/` — committed architecture and guidelines are the current source of truth for the implemented scaffold; `docs/roadmap.md` is deprecated (source: `docs/architecture.md`, `git ls-files docs`).
- `src/` — the tracked files implement the package layout in HEAD (19 files at this commit; re-check with `git ls-files src` rather than relying on a fixed count); any added package layout must be recorded in `docs/architecture.md` and this context set first (source: `git ls-files src`, `docs/architecture.md`, AGENTS.md).

## Keeping Docs in Sync

Update the relevant context file whenever implementation
changes — **mandatory, not optional**:

| If you change... | Update this file |
|---|---|
| System architecture or boundaries | `context/architecture.md` |
| Storage model decisions | `context/architecture.md` |
| Code conventions or standards | `context/code-standards.md` |
| Feature scope | `context/project-overview.md` |
| Workflow or scoping rules | `context/ai-workflow-rules.md` |
| Any implementation | `context/progress-tracker.md` (add entry with date + description) |

**Progress-tracker entry format:**
```
- YYYY-MM-DD — Description. Files: `path/file1`, `path/file2`. Impact: what changed.
```

**Rule:** A commit without a progress-tracker entry is incomplete.

## Before Moving to the Next Unit

1. The current unit works end to end within its defined scope
2. No invariant defined in `architecture.md` was violated
3. `progress-tracker.md` reflects the completed work
4. The documented scaffold validation `python scripts/prepare_dataset.py --help` works once the PROPOSED `scripts/` path exists; no build script is documented in HEAD (source: README.md, git ls-tree -r HEAD).

## Environment Divergence

When a check passes in one environment but fails in another
(e.g. local vs CI vs on-box), record the delta before adjudicating:

- Runtime version — Python is declared in `project.yaml` and `pyproject.toml`; uv is the declared package manager; exact versions are UNKNOWN — source: project.yaml, pyproject.toml.
- Dependency tree — `uv.lock` is tracked in HEAD as the resolved dependency lock; local installs may still differ (source: `git ls-files uv.lock`).
- Env vars and secret presence — names only, never values: no environment variables are declared in HEAD manifests; do not commit API keys, tokens or private speaker data (source: pyproject.toml, README.md, AGENTS.md).
- Network reachability — Hugging Face and Kaggle are named as PROPOSED hosts for large artifacts (source: docs/architecture.md).
- Filesystem paths — `docs/`, `src/`, `dataset/` and `configs/` are committed; `scripts/` remains a PROPOSED path (source: `git ls-files`, README.md).

A failure explained entirely by a recorded delta is an environment gap,
not a code regression — fix the environment or pin the dependency.
Never "fix" it by weakening the check.

## Concurrent Session Guard (session-claims)

Other AI sessions may be editing the same repo at the same time. Before
implementing, and again before committing:

```bash
bash <orchestra>/scripts/session-claims.sh check "$PWD" <paths-you-will-touch>
```

- `check` → visibility only (shows other sessions working on those paths)
- `claim`/`renew`/`release` → tracking for coordination
- Multiple sessions can work in parallel; use `check` to see who's working on what

Claim your own work at phase start, renew on long operations, release when done:

```bash
bash scripts/session-claims.sh claim  "$PWD" --scope "app/,packages/" --task "goal text"
bash scripts/session-claims.sh renew  "$PWD"
bash scripts/session-claims.sh release "$PWD"
```

Claims auto-expire after 30 min without heartbeat (`gc` purges them). Set
`PCORE_SESSION_ID` in your session env for stable identity across shells.

