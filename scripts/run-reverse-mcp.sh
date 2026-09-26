#!/usr/bin/env bash
# Run the vendored reverse MCP server with this browser repository's Python core.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_SRC="$ROOT/integrations/camoufox-reverse-mcp/src"
CORE_SRC="$ROOT/pythonlib"

export PYTHONPATH="$CORE_SRC:$MCP_SRC${PYTHONPATH:+:$PYTHONPATH}"

# Pick a Python that actually has the server dependencies (orjson, camoufox
# deps). A bare `python3` from PATH may be a stripped-down interpreter.
_pick_python() {
    local candidates=()
    if [[ -n "${CAMOUFOX_REVERSE_PYTHON:-}" ]]; then
        candidates+=("$CAMOUFOX_REVERSE_PYTHON")
    fi
    candidates+=(python3.13 python3.12 python3.11 python3)
    candidates+=(/usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11)
    candidates+=(/opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11)
    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c "import orjson" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    echo "run-reverse-mcp: no Python with required deps found (tried: ${candidates[*]});" >&2
    echo "  install them or set CAMOUFOX_REVERSE_PYTHON=/path/to/python" >&2
    return 1
}

PYTHON_BIN="$(_pick_python)" || exit 1
exec "$PYTHON_BIN" -m camoufox_reverse_mcp "$@"
