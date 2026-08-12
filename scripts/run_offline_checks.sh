#!/usr/bin/env bash
# Run offline pytest, ruff, and mypy using the project venv.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VENV_BIN="${REPO_ROOT}/.venv/bin"
if [[ ! -x "${VENV_BIN}/pytest" ]]; then
  echo "Virtualenv not found. Run ./scripts/setup_ubuntu.sh first." >&2
  exit 1
fi

"${VENV_BIN}/pytest" tests/unit tests/rest -v
"${VENV_BIN}/ruff" check src tests
"${VENV_BIN}/mypy" src
