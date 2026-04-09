#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PYTHONPATH="${ROOT_DIR}/.python_deps${PYTHONPATH:+:${PYTHONPATH}}"
export HOME="${ROOT_DIR}"
export DOTNET_CLI_HOME="${ROOT_DIR}"
export PATH="${ROOT_DIR}/.dotnet:${PATH}"

exec python3 "${ROOT_DIR}/evoflow/operator_search_main.py" "$@"
