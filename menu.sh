#!/usr/bin/env bash
set -euo pipefail

# Zolai-TTS local menu launcher.
# Usage:
#   ./menu.sh                  # interactive menu
#   ./menu.sh env [path]       # generate .env from .env.example (safe, no overwrite)
#   ./menu.sh env --force      # overwrite target .env
#   ./menu.sh <zolai-tts args> # passthrough to zolai-tts CLI

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

if [ "${1:-}" = "env" ]; then
  shift
  generate_env "$@"
  exit $?
fi

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
