#!/usr/bin/env bash
# Ported from C:/Users/Wagur1/prism-vcm/gate0/build_gate0_stack.sh; v1 commit a34d943; port date 2026-11-04.
set -Eeuo pipefail
exec "${PRISM_PYTHON:-python3}" "$(dirname -- "${BASH_SOURCE[0]}")/build_codec.py" "$@"
