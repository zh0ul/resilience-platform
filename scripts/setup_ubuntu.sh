#!/usr/bin/env bash
# Bootstrap Ubuntu dev environment: system packages, venv, editable install.
set -euo pipefail

INSTALL_PROTOCOLS=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [--protocols]

  --protocols   Also install nfs-common and cifs-utils for live NFS/SMB tests
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --protocols)
      INSTALL_PROTOCOLS=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install it with: sudo apt-get install python3" >&2
  exit 1
fi

APT_PACKAGES=(python3 python3-venv python3-pip)
if [[ "${INSTALL_PROTOCOLS}" == "true" ]]; then
  APT_PACKAGES+=(nfs-common cifs-utils)
fi

if command -v apt-get >/dev/null 2>&1; then
  if [[ "$(id -u)" -eq 0 ]]; then
    apt-get update
    apt-get install -y "${APT_PACKAGES[@]}"
  else
    sudo apt-get update
    sudo apt-get install -y "${APT_PACKAGES[@]}"
  fi
else
  echo "apt-get not found; skipping system package install." >&2
  echo "Ensure python3, python3-venv, and python3-pip are installed." >&2
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

cat <<EOF

Setup complete.

  source .venv/bin/activate
  ./scripts/run_offline_checks.sh

For live NFS/SMB on bare metal, re-run with --protocols if needed, configure .env,
then use scripts/mount_protocols.sh (requires sudo for mount).
EOF
