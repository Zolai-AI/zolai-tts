#!/usr/bin/env bash
set -euo pipefail

# Zolai-TTS local menu launcher.
#
# Stack (Gradio dropped): FastAPI API server (:7860) + React/Vite web studio
# (web/, dev server :5174). `menu.sh` only orchestrates the Python CLI; it
# never duplicates synthesis or server logic.
#
# Usage:
#   ./menu.sh                    # interactive menu (both servers)
#   ./menu.sh env [path]         # generate .env from .env.example (safe, no overwrite)
#   ./menu.sh env --force        # overwrite target .env
#   ./menu.sh status             # API + Web status (JSON + summary)
#   ./menu.sh up [--build]       # run BOTH: API (:7860) + Vite dev (:5174), or web/dist + API
#   ./menu.sh down               # stop BOTH servers
#   ./menu.sh build              # bun run build -> web/dist (served by the API)
#   ./menu.sh open               # print the live app URL (dev first, then API)
#   ./menu.sh db status          # studio database: dialect, masked URL, row counts
#   ./menu.sh db storage         # object backend status (local + Cloudflare R2)
#   ./menu.sh db reclassify-tiers# re-derive free/paid after a provider tier change
#   ./menu.sh db migrate         # import legacy JSON run/recording sidecars
#   ./menu.sh <zolai-tts args>   # passthrough to zolai-tts CLI
#
# Interactive menu items (from `zolai-tts menu`):
#   Doctor/env, Servers status, Run both (API+Web), Stop both,
#   API status|start|stop|restart|logs, Web status|start|stop|restart|logs|build,
#   database status / reclassify tiers / storage info,
#   open app, checks/tests/lint/typecheck, prepare/synth help, provider smokes.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

generate_env() {
  local target=".env"
  local force="0"
  for arg in "$@"; do
    case "$arg" in
      --force|-f) force="1" ;;
      -h|--help)
        echo "Usage: ./menu.sh env [path=.env] [--force]"
        echo "Generates env file from .env.example with placeholders only. No secrets written."
        return 0
        ;;
      *) target="$arg" ;;
    esac
  done

  local template="$ROOT_DIR/.env.example"
  if [ ! -f "$template" ]; then
    echo "Missing template: $template" >&2
    return 1
  fi
  if [ -f "$target" ] && [ "$force" != "1" ]; then
    echo "Refusing to overwrite existing $target. Use --force to overwrite." >&2
    echo "Template: $template" >&2
    return 2
  fi
  cp "$template" "$target"
  chmod 600 "$target" 2>/dev/null || true
  echo "Generated $target from .env.example"
  echo "Next: edit $target, fill placeholders, keep it local (never commit real secrets)."
  echo "Keys are read from environment at runtime; export/source as needed in your shell."
}

cli() {
  if command -v uv >/dev/null 2>&1; then
    uv run zolai-tts "$@"
  elif command -v zolai-tts >/dev/null 2>&1; then
    zolai-tts "$@"
  else
    echo "uv not found. Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
    echo "Fallback: python3 -m zolai_tts.cli $*" >&2
    python3 -m zolai_tts.cli "$@"
  fi
}

case "${1:-}" in
  env)
    shift
    generate_env "$@"
    exit $?
    ;;
  status)
    shift || true
    cli status "$@"
    exit $?
    ;;
  up)
    # ./menu.sh up [--build]  ->  API + Vite dev together; --build: web/dist + API only
    shift || true
    for arg in "$@"; do
      case "$arg" in
        --build)
          cli web build
          cli ui start
          exit $?
          ;;
        -h|--help)
          echo "Usage: ./menu.sh up [--build]"
          echo "  default   run BOTH: API (:7860) + Vite dev server (:5174)"
          echo "  --build   build web/dist first, then start API only (single-port app)"
          exit 0
          ;;
      esac
    done
    cli up
    exit $?
    ;;
  down)
    shift || true
    cli down "$@"
    exit $?
    ;;
  build)
    shift || true
    cli web build "$@"
    exit $?
    ;;
  open)
    if pgrep -f "zolai_tts.server" >/dev/null 2>&1 || pgrep -f vite >/dev/null 2>&1; then
      cli web status 2>/dev/null | grep -q '"running": true' && cli web open --launch
      cli ui open --launch 2>/dev/null || true
    else
      echo "No server running. Try: ./menu.sh up" >&2
      exit 2
    fi
    exit 0
    ;;
esac

if command -v uv >/dev/null 2>&1; then
  if [ "$#" -eq 0 ]; then
    exec uv run zolai-tts menu
  fi
  exec uv run zolai-tts "$@"
fi

echo "uv not found. Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
echo "Fallback: python -m zolai_tts.cli menu" >&2
if [ "$#" -eq 0 ]; then
  exec python3 -m zolai_tts.cli menu
fi
exec python3 -m zolai_tts.cli "$@"
